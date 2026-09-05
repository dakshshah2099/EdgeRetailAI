import uuid

import numpy as np
import numpy.typing as npt

from detection.detector import PersonDetector
from detection.inference_backend import InferenceBackend
from detection.tracker import TrackedDetection, Tracker
from detection.zone_membership import anchor_point, is_inside_zone, zone_polygon_cache
from schemas import DetectionEvent, Frame, ZoneConfig


class FootfallTracker:
    """Tracks person zone transitions and emits enter/exit/in_zone events.

    Uses edge-triggered debounce so that entering or exiting an entry_exit
    zone emits exactly one DetectionEvent per crossing, not one per frame.
    """

    def __init__(self) -> None:
        # Mapping of track_id -> set of zone_ids the track is currently inside
        self._inside_zones: dict[str, set[str]] = {}

    def reset(self) -> None:
        """Reset internal zone tracking states."""
        self._inside_zones.clear()

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

        # Pre-convert zone polygons to cv2-compatible numpy arrays
        cached_polygons = zone_polygon_cache(zones)

        for det in tracked_detections:
            point = anchor_point(det.bbox)

            previously_inside = self._inside_zones.get(det.track_id, set())
            currently_inside: set[str] = set()

            for zone in zones:
                zone_id = zone.zone_id
                poly_np = cached_polygons[zone_id]
                is_inside = is_inside_zone(point, zone, poly_np=poly_np)

                if zone.zone_type == "entry_exit":
                    if is_inside:
                        currently_inside.add(zone_id)
                        if zone_id not in previously_inside:
                            # Edge-trigger: entered zone
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
                        # Edge-trigger: exited zone
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

                elif zone.zone_type == "product_display" and is_inside:
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
    # NOTE: PersonDetector is lightweight; can be hoisted/cached if per-frame GC churn matters.
    detector = PersonDetector(backend=backend)
    raw_detections = detector.detect(pixels)
    tracked_detections = tracker.update(raw_detections)

    active_footfall_tracker = (
        footfall_tracker if footfall_tracker is not None else _default_footfall_tracker
    )
    return active_footfall_tracker.update(frame, tracked_detections, zones)
