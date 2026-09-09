import math
import uuid
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
from core.schemas import DetectionEvent, Frame, ZoneConfig
from vision.detector import PersonDetector
from vision.inference_backend import InferenceBackend
from vision.tracker import TrackedDetection, Tracker

from analytics.zone_membership import anchor_point, is_inside_zone, zone_polygon_cache


def _parse_direction(direction: str | tuple[float, float]) -> tuple[float, float]:
    """Parse a semantic string or 2D vector into a unit direction vector."""
    if isinstance(direction, str):
        d_lower = direction.strip().lower()
        if d_lower in ("top_to_bottom", "down", "south", "inward", "in"):
            return (0.0, 1.0)
        elif d_lower in ("bottom_to_top", "up", "north", "outward", "out"):
            return (0.0, -1.0)
        elif d_lower in ("left_to_right", "right", "east"):
            return (1.0, 0.0)
        elif d_lower in ("right_to_left", "left", "west"):
            return (-1.0, 0.0)
        return (0.0, 1.0)

    dx, dy = float(direction[0]), float(direction[1])
    mag = math.hypot(dx, dy)
    if mag > 1e-6:
        return (dx / mag, dy / mag)
    return (0.0, 1.0)


def _polygon_centroid(polygon: list[tuple[int, int]]) -> tuple[float, float]:
    """Compute (cx, cy) arithmetic centroid of polygon vertices."""
    if not polygon:
        return (0.0, 0.0)
    cx = sum(p[0] for p in polygon) / len(polygon)
    cy = sum(p[1] for p in polygon) / len(polygon)
    return (cx, cy)


class FootfallTracker:
    """Tracks person zone transitions and emits enter/exit/in_zone events.

    Modes:
    - "edge": Legacy edge-triggered debounce (default). Entering polygon emits
      'enter', exiting polygon emits 'exit'. Fully backward-compatible.
    - "directional": Trajectory-aware zone crossing. Moving through the zone from
      exterior to interior emits 'enter'. Moving through the zone from interior
      to exterior emits 'exit'. Traversal in the forward direction represents an
      entrance without false cancelling exits.
    - "line_crossing": Virtual tripwire line crossing across the zone midline
      or configured crossing line.
    """

    def __init__(
        self,
        mode: Literal["edge", "directional", "line_crossing"] = "edge",
        entry_direction: str | tuple[float, float] = (0.0, 1.0),
        zone_directions: dict[str, tuple[float, float] | str] | None = None,
        crossing_lines: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
        emit_on: Literal["zone_exit", "zone_enter"] = "zone_exit",
        directional: bool = False,
    ) -> None:
        if directional:
            self.mode: Literal["edge", "directional", "line_crossing"] = "directional"
        else:
            self.mode = mode

        self.emit_on = emit_on
        self._default_direction = _parse_direction(entry_direction)
        self._zone_directions: dict[str, tuple[float, float]] = (
            {z_id: _parse_direction(d) for z_id, d in zone_directions.items()}
            if zone_directions
            else {}
        )
        self._crossing_lines = crossing_lines or {}

        # Mapping of track_id -> set of zone_ids the track is currently inside
        self._inside_zones: dict[str, set[str]] = {}
        # Mapping of track_id -> last observed anchor point
        self._prev_positions: dict[str, tuple[float, float]] = {}
        # Mapping of track_id -> zone_id -> entry metadata
        self._track_entry_info: dict[str, dict[str, dict[str, Any]]] = {}
        # Mapping of track_id -> zone_id -> last line side (-1, 0, 1)
        self._track_line_side: dict[str, dict[str, int]] = {}
        # Mapping of track_id -> zone_id -> event emitted on entry
        self._entry_emitted: dict[str, dict[str, str]] = {}

    def reset(self) -> None:
        """Reset internal zone tracking states."""
        self._inside_zones.clear()
        self._prev_positions.clear()
        self._track_entry_info.clear()
        self._track_line_side.clear()
        self._entry_emitted.clear()

    def _get_zone_direction(self, zone: ZoneConfig) -> tuple[float, float]:
        """Resolve direction vector for a specific zone."""
        if zone.zone_id in self._zone_directions:
            return self._zone_directions[zone.zone_id]
        attr_dir = getattr(zone, "entry_direction", None) or getattr(zone, "direction", None)
        if attr_dir is not None:
            return _parse_direction(attr_dir)
        return self._default_direction

    def update(
        self,
        frame: Frame,
        tracked_detections: list[TrackedDetection],
        zones: list[ZoneConfig],
    ) -> list[DetectionEvent]:
        """Process tracked detections against zone boundaries and emit events."""
        events: list[DetectionEvent] = []
        current_track_ids = {det.track_id for det in tracked_detections}

        # Clean up tracks that have terminated
        for track_id in list(self._inside_zones.keys()):
            if track_id not in current_track_ids:
                del self._inside_zones[track_id]
                self._prev_positions.pop(track_id, None)
                self._track_entry_info.pop(track_id, None)
                self._track_line_side.pop(track_id, None)
                self._entry_emitted.pop(track_id, None)

        # Pre-convert zone polygons to cv2-compatible numpy arrays
        cached_polygons = zone_polygon_cache(zones)

        for det in tracked_detections:
            point = anchor_point(det.bbox)
            prev_point = self._prev_positions.get(det.track_id)

            previously_inside = self._inside_zones.get(det.track_id, set())
            currently_inside: set[str] = set()

            for zone in zones:
                zone_id = zone.zone_id
                poly_np = cached_polygons[zone_id]
                is_inside = is_inside_zone(point, zone, poly_np=poly_np)

                if zone.zone_type == "entry_exit":
                    if self.mode == "edge":
                        if is_inside:
                            currently_inside.add(zone_id)
                            if zone_id not in previously_inside:
                                events.append(
                                    DetectionEvent(
                                        event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                        track_id=det.track_id,
                                        timestamp=frame.timestamp,
                                        bbox=det.bbox,
                                        zone_id=zone_id,
                                        event_type="enter",
                                    )
                                )
                        elif zone_id in previously_inside:
                            events.append(
                                DetectionEvent(
                                    event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                    track_id=det.track_id,
                                    timestamp=frame.timestamp,
                                    bbox=det.bbox,
                                    zone_id=zone_id,
                                    event_type="exit",
                                )
                            )

                    elif self.mode == "directional":
                        if is_inside:
                            currently_inside.add(zone_id)
                            if zone_id not in previously_inside:
                                entry_rec: dict[str, Any] = {
                                    "entry_point": point,
                                    "outside_point": (
                                        prev_point if prev_point is not None else point
                                    ),
                                    "timestamp": frame.timestamp,
                                    "bbox": det.bbox,
                                }
                                self._track_entry_info.setdefault(det.track_id, {})[zone_id] = (
                                    entry_rec
                                )

                            if self.emit_on == "zone_enter":
                                already_emitted = self._entry_emitted.get(det.track_id, {}).get(
                                    zone_id
                                )
                                if already_emitted is None:
                                    entry_info = self._track_entry_info.get(
                                        det.track_id, {}
                                    ).get(zone_id)
                                    if entry_info is not None:
                                        entry_dir = self._get_zone_direction(zone)
                                        c = _polygon_centroid(zone.polygon)
                                        start_pt = entry_info["outside_point"]
                                        orig_pt = entry_info["entry_point"]

                                        v = (point[0] - start_pt[0], point[1] - start_pt[1])
                                        dot = v[0] * entry_dir[0] + v[1] * entry_dir[1]
                                        start_side = (start_pt[0] - c[0]) * entry_dir[0] + (
                                            start_pt[1] - c[1]
                                        ) * entry_dir[1]
                                        curr_side = (point[0] - c[0]) * entry_dir[0] + (
                                            point[1] - c[1]
                                        ) * entry_dir[1]
                                        disp_from_entry = (
                                            (point[0] - orig_pt[0]) * entry_dir[0]
                                            + (point[1] - orig_pt[1]) * entry_dir[1]
                                        )

                                        if (
                                            (dot >= 0 and start_side <= 0)
                                            or (start_pt == point and curr_side <= 0)
                                            or (disp_from_entry > 0)
                                        ):
                                            events.append(
                                                DetectionEvent(
                                                    event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                                    track_id=det.track_id,
                                                    timestamp=frame.timestamp,
                                                    bbox=det.bbox,
                                                    zone_id=zone_id,
                                                    event_type="enter",
                                                )
                                            )
                                            self._entry_emitted.setdefault(det.track_id, {})[
                                                zone_id
                                            ] = "enter"

                        elif zone_id in previously_inside:
                            entry_info = self._track_entry_info.get(det.track_id, {}).pop(
                                zone_id, None
                            )
                            already_emitted = self._entry_emitted.get(det.track_id, {}).pop(
                                zone_id, None
                            )
                            entry_dir = self._get_zone_direction(zone)
                            c = _polygon_centroid(zone.polygon)

                            start_pt = (
                                entry_info["outside_point"]
                                if entry_info and "outside_point" in entry_info
                                else (entry_info["entry_point"] if entry_info else point)
                            )
                            end_pt = point

                            disp_x = end_pt[0] - start_pt[0]
                            disp_y = end_pt[1] - start_pt[1]
                            dot = disp_x * entry_dir[0] + disp_y * entry_dir[1]

                            start_side = (start_pt[0] - c[0]) * entry_dir[0] + (
                                start_pt[1] - c[1]
                            ) * entry_dir[1]
                            end_side = (end_pt[0] - c[0]) * entry_dir[0] + (
                                end_pt[1] - c[1]
                            ) * entry_dir[1]

                            if self.emit_on == "zone_exit":
                                if dot > 0 and (start_side <= 0 or end_side > 0):
                                    events.append(
                                        DetectionEvent(
                                            event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                            track_id=det.track_id,
                                            timestamp=frame.timestamp,
                                            bbox=det.bbox,
                                            zone_id=zone_id,
                                            event_type="enter",
                                        )
                                    )
                                elif dot < 0 and (start_side >= 0 or end_side < 0):
                                    events.append(
                                        DetectionEvent(
                                            event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                            track_id=det.track_id,
                                            timestamp=frame.timestamp,
                                            bbox=det.bbox,
                                            zone_id=zone_id,
                                            event_type="exit",
                                        )
                                    )
                            elif self.emit_on == "zone_enter":
                                if already_emitted == "enter":
                                    if dot < 0 and end_side <= 0:
                                        events.append(
                                            DetectionEvent(
                                                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                                track_id=det.track_id,
                                                timestamp=frame.timestamp,
                                                bbox=det.bbox,
                                                zone_id=zone_id,
                                                event_type="exit",
                                            )
                                        )
                                else:
                                    if dot < 0 and (start_side >= 0 or end_side <= 0):
                                        events.append(
                                            DetectionEvent(
                                                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                                track_id=det.track_id,
                                                timestamp=frame.timestamp,
                                                bbox=det.bbox,
                                                zone_id=zone_id,
                                                event_type="exit",
                                            )
                                        )

                    elif self.mode == "line_crossing":
                        if is_inside:
                            currently_inside.add(zone_id)
                        entry_dir = self._get_zone_direction(zone)
                        c = _polygon_centroid(zone.polygon)

                        if prev_point is not None and (
                            is_inside or zone_id in previously_inside
                        ):
                            d_prev = (prev_point[0] - c[0]) * entry_dir[0] + (
                                prev_point[1] - c[1]
                            ) * entry_dir[1]
                            d_curr = (point[0] - c[0]) * entry_dir[0] + (
                                point[1] - c[1]
                            ) * entry_dir[1]
                            last_side = self._track_line_side.get(det.track_id, {}).get(
                                zone_id, 0
                            )

                            if d_prev < 0 and d_curr >= 0 and last_side != 1:
                                events.append(
                                    DetectionEvent(
                                        event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                        track_id=det.track_id,
                                        timestamp=frame.timestamp,
                                        bbox=det.bbox,
                                        zone_id=zone_id,
                                        event_type="enter",
                                    )
                                )
                                self._track_line_side.setdefault(det.track_id, {})[zone_id] = 1
                            elif d_prev > 0 and d_curr <= 0 and last_side != -1:
                                events.append(
                                    DetectionEvent(
                                        event_id=f"evt_{uuid.uuid4().hex[:12]}",
                                        track_id=det.track_id,
                                        timestamp=frame.timestamp,
                                        bbox=det.bbox,
                                        zone_id=zone_id,
                                        event_type="exit",
                                    )
                                )
                                self._track_line_side.setdefault(det.track_id, {})[zone_id] = -1

                elif zone.zone_type in ("product_display", "shelf") and is_inside:
                    currently_inside.add(zone_id)
                    events.append(
                        DetectionEvent(
                            event_id=f"evt_{uuid.uuid4().hex[:12]}",
                            track_id=det.track_id,
                            timestamp=frame.timestamp,
                            bbox=det.bbox,
                            zone_id=zone_id,
                            event_type="in_zone",
                        )
                    )

            self._inside_zones[det.track_id] = currently_inside
            self._prev_positions[det.track_id] = point

        return events


# Module-level default footfall tracker instance when none is passed explicitly
_default_footfall_tracker = FootfallTracker()


def process_frame(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    backend: InferenceBackend,
    tracker: Tracker,
    zones: list[ZoneConfig],
    footfall_tracker: FootfallTracker | None = None,
) -> list[DetectionEvent]:
    """Top-level frame processing pipeline for Slice 2.

    Runs person detection, assigns stable track IDs, evaluates zone boundaries,
    and returns emitted DetectionEvents.
    """
    detector = PersonDetector(backend=backend)
    raw_detections = detector.detect(pixels)
    tracked_detections = tracker.update(raw_detections)

    active_footfall_tracker = (
        footfall_tracker if footfall_tracker is not None else _default_footfall_tracker
    )
    return active_footfall_tracker.update(frame, tracked_detections, zones)
