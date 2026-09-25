"""Planogram-lite compliance module: facing grid subdivision, per-facing scoring,

and expected layout compliance evaluation.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import yaml

from analytics.shelf_classifier import HybridShelfClassifier, ShelfClassifier
from core.schemas import StockEvent, ZoneConfig
from storage.repository import EventRepository

Polygon = list[tuple[int, int]]


@dataclass(frozen=True)
class FacingStatus:
    """Classification status and confidence for an individual facing sub-rectangle."""

    zone_id: str
    facing_index: tuple[int, int]  # (row, col) within the zone's grid
    status: Literal["ok", "low", "empty"]
    confidence: float


@dataclass(frozen=True)
class PlanogramCompliance:
    """Evaluated planogram compliance snapshot for a shelf zone."""

    zone_id: str
    timestamp: datetime
    total_facings: int
    expected_nonempty: int
    actual_nonempty: int
    compliance_ratio: float  # actual_nonempty / expected_nonempty, capped at 1.0
    facing_statuses: list[FacingStatus]
    missing_facings: list[tuple[int, int]]  # expected-nonempty facings currently empty/low


@dataclass(frozen=True)
class ExpectedLayout:
    """Configured planogram layout: grid size and list of expected non-empty facing indices."""

    zone_id: str
    grid_rows: int
    grid_cols: int
    expected_nonempty_facings: list[tuple[int, int]] = field(default_factory=list)


# In-memory cache for recent compliance snapshots
_latest_compliance_cache: dict[str, PlanogramCompliance] = {}


def split_zone_into_facings(
    zone: ZoneConfig,
    grid_rows: int,
    grid_cols: int,
) -> list[tuple[tuple[int, int], Polygon]]:
    """Subdivide a shelf zone's polygon bounding box into a grid_rows x

    grid_cols set of sub-rectangles. Pure geometry, no frame access.

    Produces exactly grid_rows * grid_cols non-overlapping sub-rectangles
    that together cover the zone's full bounding box with no gaps or overlaps.
    """
    if grid_rows < 1 or grid_cols < 1:
        raise ValueError("grid_rows and grid_cols must be >= 1")
    if len(zone.polygon) < 3:
        raise ValueError("Zone polygon must have at least 3 vertices")

    xs = [p[0] for p in zone.polygon]
    ys = [p[1] for p in zone.polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError(f"Zone polygon has non-positive area: width={width}, height={height}")

    facings: list[tuple[tuple[int, int], Polygon]] = []

    for r in range(grid_rows):
        y0 = min_y + (r * height) // grid_rows
        y1 = min_y + ((r + 1) * height) // grid_rows
        for c in range(grid_cols):
            x0 = min_x + (c * width) // grid_cols
            x1 = min_x + ((c + 1) * width) // grid_cols

            rect_poly: Polygon = [
                (x0, y0),
                (x1, y0),
                (x1, y1),
                (x0, y1),
            ]
            facings.append(((r, c), rect_poly))

    return facings


def score_planogram_compliance(
    frame: npt.NDArray[np.uint8],
    zone: ZoneConfig,
    layout: ExpectedLayout,
    classifier: ShelfClassifier | None = None,
    timestamp: datetime | None = None,
) -> PlanogramCompliance:
    """Score every facing via the existing shelf_classifier scorer, then

    diff actual-nonempty facings against layout.expected_nonempty_facings.
    The raw frame ndarray is used transiently for scoring only â€” never
    persisted, adhering to the non-PII/frame persistence constraints.
    """
    if classifier is None:
        classifier = HybridShelfClassifier()

    ts = timestamp if timestamp is not None else datetime.now()

    facing_geometries = split_zone_into_facings(
        zone, grid_rows=layout.grid_rows, grid_cols=layout.grid_cols
    )

    frame_h, frame_w = frame.shape[:2]
    facing_statuses: list[FacingStatus] = []

    for (r, c), poly in facing_geometries:
        poly_xs = [p[0] for p in poly]
        poly_ys = [p[1] for p in poly]
        x0 = max(0, min(frame_w, min(poly_xs)))
        x1 = max(0, min(frame_w, max(poly_xs)))
        y0 = max(0, min(frame_h, min(poly_ys)))
        y1 = max(0, min(frame_h, max(poly_ys)))

        if x1 <= x0 or y1 <= y0:
            status: Literal["empty", "low", "ok"] = "empty"
            conf = 0.0
        else:
            sub_crop = frame[y0:y1, x0:x1]
            status, conf = classifier.classify(sub_crop)

        facing_statuses.append(
            FacingStatus(
                zone_id=zone.zone_id,
                facing_index=(r, c),
                status=status,
                confidence=conf,
            )
        )

    total_facings = layout.grid_rows * layout.grid_cols
    expected_set = set(layout.expected_nonempty_facings)
    expected_nonempty = len(expected_set)

    # Actual nonempty: count of facings currently scored 'ok' (compliant with stocking)
    actual_nonempty = sum(1 for f in facing_statuses if f.status == "ok")

    # Ratio capped at 1.0; 1.0 when expected_nonempty == 0
    if expected_nonempty == 0:
        compliance_ratio = 1.0
    else:
        compliance_ratio = min(1.0, float(actual_nonempty) / float(expected_nonempty))

    # missing_facings: expected non-empty facings currently scored low or empty
    missing_facings = [
        f.facing_index
        for f in facing_statuses
        if f.facing_index in expected_set and f.status in ("low", "empty")
    ]

    return PlanogramCompliance(
        zone_id=zone.zone_id,
        timestamp=ts,
        total_facings=total_facings,
        expected_nonempty=expected_nonempty,
        actual_nonempty=actual_nonempty,
        compliance_ratio=compliance_ratio,
        facing_statuses=facing_statuses,
        missing_facings=missing_facings,
    )


def save_planogram_compliance(
    repo: EventRepository,
    compliance: PlanogramCompliance,
) -> None:
    """Persist facing statuses as StockEvents into Slice 4's existing storage path.

    Encodes facing position into shelf_id as {zone_id}:facing:{r}:{c}.
    """
    _latest_compliance_cache[compliance.zone_id] = compliance

    for fs in compliance.facing_statuses:
        r, c = fs.facing_index
        event = StockEvent(
            event_id=f"plano_{uuid.uuid4().hex[:12]}",
            shelf_id=f"{compliance.zone_id}:facing:{r}:{c}",
            timestamp=compliance.timestamp,
            status=fs.status,
            confidence=fs.confidence,
        )
        repo.save_stock_event(event)


def get_latest_planogram_compliance(
    repo: EventRepository,
    zone_id: str,
    layout: ExpectedLayout | None = None,
) -> PlanogramCompliance | None:
    """Retrieve and reconstruct the latest PlanogramCompliance for a zone from

    existing StockEvents in the EventRepository (or in-memory cache).
    """
    if layout is None:
        layout = get_or_create_planogram_layout(zone_id)

    # Query repository for latest event of each facing
    facing_statuses: list[FacingStatus] = []
    event_timestamps: list[datetime] = []

    for r in range(layout.grid_rows):
        for c in range(layout.grid_cols):
            shelf_id = f"{zone_id}:facing:{r}:{c}"
            events = repo.get_recent_stock_events(limit=1, shelf_id=shelf_id)
            if events:
                latest_ev = events[0]
                event_timestamps.append(latest_ev.timestamp)
                facing_statuses.append(
                    FacingStatus(
                        zone_id=zone_id,
                        facing_index=(r, c),
                        status=latest_ev.status,
                        confidence=latest_ev.confidence,
                    )
                )

    if not facing_statuses:
        # Fallback to cache if repository had no matching facing events
        return _latest_compliance_cache.get(zone_id)

    # Reconstruct any missing facing slots as empty
    seen_indices = {f.facing_index for f in facing_statuses}
    for r in range(layout.grid_rows):
        for c in range(layout.grid_cols):
            if (r, c) not in seen_indices:
                facing_statuses.append(
                    FacingStatus(
                        zone_id=zone_id,
                        facing_index=(r, c),
                        status="empty",
                        confidence=0.0,
                    )
                )

    facing_statuses.sort(key=lambda f: f.facing_index)

    total_facings = layout.grid_rows * layout.grid_cols
    expected_set = set(layout.expected_nonempty_facings)
    expected_nonempty = len(expected_set)
    actual_nonempty = sum(1 for f in facing_statuses if f.status == "ok")

    if expected_nonempty == 0:
        compliance_ratio = 1.0
    else:
        compliance_ratio = min(1.0, float(actual_nonempty) / float(expected_nonempty))

    missing_facings = [
        f.facing_index
        for f in facing_statuses
        if f.facing_index in expected_set and f.status in ("low", "empty")
    ]
    latest_ts = max(event_timestamps) if event_timestamps else datetime.now()

    return PlanogramCompliance(
        zone_id=zone_id,
        timestamp=latest_ts,
        total_facings=total_facings,
        expected_nonempty=expected_nonempty,
        actual_nonempty=actual_nonempty,
        compliance_ratio=compliance_ratio,
        facing_statuses=facing_statuses,
        missing_facings=missing_facings,
    )


def load_planogram_layouts(
    config_path: str | Path | None = None,
) -> dict[str, ExpectedLayout]:
    """Load expected planogram layouts from YAML configuration."""
    if config_path is None:
        candidates = [
            Path("config/planogram_layouts.yaml"),
            Path("backend/config/planogram_layouts.yaml"),
            Path(__file__).resolve().parent.parent / "config" / "planogram_layouts.yaml",
            Path(__file__).resolve().parent.parent.parent / "config" / "planogram_layouts.yaml",
        ]
        target_path: Path | None = None
        for candidate in candidates:
            if candidate.is_file():
                target_path = candidate
                break
        if target_path is None:
            return {}
    else:
        target_path = Path(config_path)
        if not target_path.is_file():
            return {}

    with open(target_path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, dict):
        return {}

    layouts: dict[str, ExpectedLayout] = {}
    for zone_id, cfg in data.items():
        if not isinstance(cfg, dict):
            continue
        grid_rows = int(cfg.get("grid_rows", 1))
        grid_cols = int(cfg.get("grid_cols", 1))
        raw_facings = cfg.get("expected_nonempty_facings") or cfg.get("expected_nonempty") or []
        expected_facings: list[tuple[int, int]] = []
        for item in raw_facings:
            if isinstance(item, list | tuple) and len(item) == 2:
                expected_facings.append((int(item[0]), int(item[1])))

        layouts[str(zone_id)] = ExpectedLayout(
            zone_id=str(zone_id),
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            expected_nonempty_facings=expected_facings,
        )

    return layouts


def get_or_create_planogram_layout(
    zone_id: str,
    config_path: str | Path | None = None,
) -> ExpectedLayout:
    """Retrieve configured layout for zone_id, or generate a 2x3 default layout."""
    layouts = load_planogram_layouts(config_path)
    if zone_id in layouts:
        return layouts[zone_id]
    return ExpectedLayout(
        zone_id=zone_id,
        grid_rows=2,
        grid_cols=3,
        expected_nonempty_facings=[(r, c) for r in range(2) for c in range(3)],
    )


