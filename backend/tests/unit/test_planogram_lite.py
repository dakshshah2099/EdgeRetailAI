from datetime import datetime
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt

from analytics.shelf_classifier import ShelfClassifier
from core.schemas import ZoneConfig
from storage.repository import EventRepository


class DummyClassifier(ShelfClassifier):
    """Deterministic classifier returning configured status per sub-crop coordinate."""

    def __init__(
        self,
        facing_status_map: (
            dict[tuple[int, int], tuple[Literal["empty", "low", "ok"], float]] | None
        ) = None,
        default_status: Literal["empty", "low", "ok"] = "ok",
        default_conf: float = 0.9,
    ) -> None:
        self.facing_status_map = facing_status_map or {}
        self.default_status = default_status
        self.default_conf = default_conf
        self.call_count = 0

    def classify(
        self, shelf_crop: npt.NDArray[np.uint8]
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        self.call_count += 1
        # Use pixel marker if present in top-left pixel
        if shelf_crop.size > 0 and shelf_crop.ndim >= 2:
            r = int(shelf_crop[0, 0, 0]) if shelf_crop.ndim == 3 else int(shelf_crop[0, 0])
            c = int(shelf_crop[0, 0, 1]) if shelf_crop.ndim == 3 else 0
            if (r, c) in self.facing_status_map:
                return self.facing_status_map[(r, c)]
        return self.default_status, self.default_conf


def test_split_zone_into_facings_exact_count_and_no_gaps_or_overlaps() -> None:
    """split_zone_into_facings produces exactly grid_rows * grid_cols non-overlapping

    sub-rectangles that together cover the zone's full bounding box.
    """
    from analytics.planogram_lite import split_zone_into_facings

    zone = ZoneConfig(
        zone_id="test_shelf",
        camera_id="camera_main",
        zone_type="shelf",
        polygon=[(100, 200), (300, 200), (300, 500), (100, 500)],
        label="Test Shelf",
    )
    grid_rows = 3
    grid_cols = 2

    facings = split_zone_into_facings(zone, grid_rows=grid_rows, grid_cols=grid_cols)

    # 1. Exact count check
    assert len(facings) == grid_rows * grid_cols == 6

    # 2. Check every index (r, c) exists exactly once
    indices = [f[0] for f in facings]
    expected_indices = [(r, c) for r in range(grid_rows) for c in range(grid_cols)]
    assert sorted(indices) == sorted(expected_indices)

    # 3. Check geometry coverage: bounding boxes of facings cover [100, 300] x [200, 500]
    total_area = (300 - 100) * (500 - 200)  # 200 * 300 = 60000
    sum_facing_areas = 0

    rects: list[tuple[int, int, int, int]] = []
    for (r, c), poly in facings:
        assert len(poly) == 4, f"Facing ({r}, {c}) must be a 4-vertex rectangle"
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        area = (x1 - x0) * (y1 - y0)
        assert area > 0, f"Facing ({r}, {c}) must have positive area"
        sum_facing_areas += area
        rects.append((x0, y0, x1, y1))

    # Sum of areas must exactly equal total bounding box area (no gaps, no overlaps)
    assert sum_facing_areas == total_area

    # Pairwise check for no interior overlap between distinct sub-rectangles
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ax0, ay0, ax1, ay1 = rects[i]
            bx0, by0, bx1, by1 = rects[j]
            overlap_w = max(0, min(ax1, bx1) - max(ax0, bx0))
            overlap_h = max(0, min(ay1, by1) - max(ay0, by0))
            # Interior overlap must be zero
            assert overlap_w * overlap_h == 0, f"Overlap between rect {i} and {j}"


def test_split_zone_into_facings_uneven_dimensions() -> None:
    """split_zone_into_facings handles non-divisible dimensions cleanly with full coverage."""
    from analytics.planogram_lite import split_zone_into_facings

    zone = ZoneConfig(
        zone_id="uneven_shelf",
        camera_id="camera_main",
        zone_type="shelf",
        polygon=[(10, 20), (27, 20), (27, 43), (10, 43)],  # width=17, height=23
        label="Uneven Shelf",
    )
    facings = split_zone_into_facings(zone, grid_rows=3, grid_cols=4)
    assert len(facings) == 12

    total_area = 17 * 23
    sum_areas = 0
    for _, poly in facings:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        sum_areas += (max(xs) - min(xs)) * (max(ys) - min(ys))

    assert sum_areas == total_area


def test_compliance_ratio_capped_at_one() -> None:
    """compliance_ratio must be capped at 1.0 even if actual_nonempty > expected_nonempty."""
    from analytics.planogram_lite import ExpectedLayout, score_planogram_compliance

    zone = ZoneConfig(
        zone_id="zone_beverages",
        camera_id="camera_main",
        zone_type="shelf",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        label="Beverages",
    )
    # Operator only expected 1 facing non-empty
    layout = ExpectedLayout(
        zone_id="zone_beverages",
        grid_rows=2,
        grid_cols=2,
        expected_nonempty_facings=[(0, 0)],
    )

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Classifier reports all 4 facings as 'ok'
    classifier = DummyClassifier(default_status="ok", default_conf=0.95)

    compliance = score_planogram_compliance(frame, zone, layout, classifier=classifier)

    assert compliance.total_facings == 4
    assert compliance.expected_nonempty == 1
    assert compliance.actual_nonempty == 4
    # Even though 4 / 1 = 4.0, ratio MUST be capped at 1.0
    assert compliance.compliance_ratio == 1.0
    assert compliance.missing_facings == []


def test_compliance_ratio_zero_expected_facings() -> None:
    """compliance_ratio must be 1.0, not a division error, when expected_nonempty == 0."""
    from analytics.planogram_lite import ExpectedLayout, score_planogram_compliance

    zone = ZoneConfig(
        zone_id="decorative_shelf",
        camera_id="camera_main",
        zone_type="shelf",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        label="Decorative Shelf",
    )
    layout = ExpectedLayout(
        zone_id="decorative_shelf",
        grid_rows=2,
        grid_cols=2,
        expected_nonempty_facings=[],  # 0 expected
    )

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    classifier = DummyClassifier(default_status="empty", default_conf=0.9)

    compliance = score_planogram_compliance(frame, zone, layout, classifier=classifier)

    assert compliance.expected_nonempty == 0
    assert compliance.compliance_ratio == 1.0
    assert compliance.missing_facings == []


def test_missing_facings_filtering() -> None:
    """missing_facings contains only facings that are both:

    (a) expected non-empty per the layout, AND
    (b) currently scored low or empty.
    A facing that is empty but was NOT expected to be stocked must not appear.
    """
    from analytics.planogram_lite import ExpectedLayout, score_planogram_compliance

    zone = ZoneConfig(
        zone_id="zone_snacks",
        camera_id="camera_main",
        zone_type="shelf",
        polygon=[(0, 0), (200, 0), (200, 200), (0, 200)],
        label="Snacks",
    )
    # 2x2 grid = facings (0,0), (0,1), (1,0), (1,1)
    # Expected non-empty: (0,0), (0,1), (1,0).
    # Facing (1,1) is deliberately empty/decorative in layout.
    layout = ExpectedLayout(
        zone_id="zone_snacks",
        grid_rows=2,
        grid_cols=2,
        expected_nonempty_facings=[(0, 0), (0, 1), (1, 0)],
    )

    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    # Stamp coordinates into top-left of each facing quadrant
    # (0,0) -> y: 0..100, x: 0..100
    frame[0, 0] = [0, 0, 0]
    # (0,1) -> y: 0..100, x: 100..200
    frame[0, 100] = [0, 1, 0]
    # (1,0) -> y: 100..200, x: 0..100
    frame[100, 0] = [1, 0, 0]
    # (1,1) -> y: 100..200, x: 100..200
    frame[100, 100] = [1, 1, 0]

    status_map: dict[tuple[int, int], tuple[Literal["empty", "low", "ok"], float]] = {
        (0, 0): ("ok", 0.95),  # Expected and ok -> compliant
        (0, 1): ("low", 0.70),  # Expected and low -> MISSING
        (1, 0): ("empty", 0.85),  # Expected and empty -> MISSING
        (1, 1): ("empty", 0.90),  # NOT expected -> should NOT appear in missing_facings!
    }
    classifier = DummyClassifier(facing_status_map=status_map)

    compliance = score_planogram_compliance(frame, zone, layout, classifier=classifier)

    assert compliance.total_facings == 4
    assert compliance.expected_nonempty == 3
    assert compliance.actual_nonempty == 1
    assert abs(compliance.compliance_ratio - (1.0 / 3.0)) < 1e-5

    # missing_facings must have exactly (0,1) and (1,0)
    assert set(compliance.missing_facings) == {(0, 1), (1, 0)}
    assert (1, 1) not in compliance.missing_facings
    assert (0, 0) not in compliance.missing_facings


def test_reuses_shelf_classifier_scoring() -> None:
    """planogram_lite reuses existing shelf_classifier scoring without duplicating logic."""
    import inspect

    import analytics.planogram_lite as pl_module

    # Verify ShelfClassifier is imported
    assert hasattr(pl_module, "ShelfClassifier") or hasattr(pl_module, "HybridShelfClassifier")

    # Inspect source: ensure it does not reimplement cv2.Canny or Sobel
    source = inspect.getsource(pl_module)
    assert "cv2.Canny" not in source, "Must not reimplement Canny edge detection in planogram_lite"
    assert "cv2.Sobel" not in source, "Must not reimplement Sobel edge detection in planogram_lite"


def test_save_and_retrieve_planogram_compliance(tmp_path: Path) -> None:
    """Test persistence of facing events into EventRepository and reconstruction."""
    from analytics.planogram_lite import (
        ExpectedLayout,
        FacingStatus,
        PlanogramCompliance,
        get_latest_planogram_compliance,
        save_planogram_compliance,
    )
    from storage.db import init_db

    db_file = tmp_path / "retail.db"
    init_db(db_file)
    repo = EventRepository(db_file)

    now = datetime(2026, 9, 12, 12, 0, 0)
    compliance = PlanogramCompliance(
        zone_id="shelf_test",
        timestamp=now,
        total_facings=2,
        expected_nonempty=2,
        actual_nonempty=1,
        compliance_ratio=0.5,
        facing_statuses=[
            FacingStatus(zone_id="shelf_test", facing_index=(0, 0), status="ok", confidence=0.9),
            FacingStatus(zone_id="shelf_test", facing_index=(0, 1), status="empty", confidence=0.8),
        ],
        missing_facings=[(0, 1)],
    )

    save_planogram_compliance(repo, compliance)

    layout = ExpectedLayout(
        zone_id="shelf_test",
        grid_rows=1,
        grid_cols=2,
        expected_nonempty_facings=[(0, 0), (0, 1)],
    )

    retrieved = get_latest_planogram_compliance(repo, "shelf_test", layout=layout)
    assert retrieved is not None
    assert retrieved.zone_id == "shelf_test"
    assert retrieved.total_facings == 2
    assert retrieved.expected_nonempty == 2
    assert retrieved.actual_nonempty == 1
    assert retrieved.compliance_ratio == 0.5
    assert set(retrieved.missing_facings) == {(0, 1)}
    assert len(retrieved.facing_statuses) == 2

