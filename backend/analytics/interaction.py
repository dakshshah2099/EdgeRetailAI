"""Product interaction engine detecting proximity and engagement
between shoppers and shelf products.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import cv2
import numpy as np
import numpy.typing as npt
from core.schemas import InteractionEvent, ZoneConfig
from vision.tracker import TrackedDetection


@dataclass
class _InteractionSession:
    track_id: str
    zone_id: str
    start_ts: datetime
    last_seen_ts: datetime
    confidences: list[float] = field(default_factory=list)
    is_confirmed: bool = False


class ProductInteractionDetector:
    """Detects shopper interaction with retail shelf/product zones.

    Criteria:
    - Spatial proximity: Key points of person bbox within configurable pixel distance.
    - Temporal debouncing: Interaction must persist for min_duration_sec.
    - Occlusion & missed-frame tolerance: Brief dropouts (<= grace_period_sec) tolerated.
    - Emits typed InteractionEvent upon interaction completion or flush.
    """

    def __init__(
        self,
        proximity_margin_px: float = 60.0,
        min_duration_sec: float = 1.0,
        grace_period_sec: float = 1.5,
    ) -> None:
        self.proximity_margin_px = proximity_margin_px
        self.min_duration_sec = min_duration_sec
        self.grace_period_sec = grace_period_sec
        self._sessions: dict[tuple[str, str], _InteractionSession] = {}
        self._zone_polygons_cache: dict[str, npt.NDArray[np.int32]] = {}

    def _get_poly(self, zone: ZoneConfig) -> npt.NDArray[np.int32]:
        if zone.zone_id not in self._zone_polygons_cache:
            self._zone_polygons_cache[zone.zone_id] = np.array(
                zone.polygon, dtype=np.int32
            ).reshape((-1, 1, 2))
        return self._zone_polygons_cache[zone.zone_id]

    def _is_proximate(
        self,
        track_bbox: tuple[int, int, int, int],
        zone: ZoneConfig,
    ) -> bool:
        """Check if person is proximate to the shelf/product zone."""
        poly = self._get_poly(zone)
        x, y, w, h = track_bbox
        top_center = (float(x + w / 2.0), float(y))
        mid_point = (float(x + w / 2.0), float(y + h / 2.0))
        bottom_center = (float(x + w / 2.0), float(y + h))

        for pt in (top_center, mid_point, bottom_center):
            dist = cv2.pointPolygonTest(poly, pt, True)
            if dist >= -self.proximity_margin_px:
                return True

        return False

    def update(
        self,
        tracks: list[TrackedDetection],
        zones: list[ZoneConfig],
        timestamp: datetime,
    ) -> list[InteractionEvent]:
        """Update interactions with tracks and shelf/product zones from current frame."""
        shelf_zones = [z for z in zones if z.zone_type in ("shelf", "product_display")]
        person_tracks = [t for t in tracks if t.class_id == 0]

        current_interactions: dict[tuple[str, str], float] = {}
        for track in person_tracks:
            for zone in shelf_zones:
                if self._is_proximate(track.bbox, zone):
                    current_interactions[(track.track_id, zone.zone_id)] = track.confidence

        # Update or create sessions
        for (track_id, zone_id), conf in current_interactions.items():
            key = (track_id, zone_id)
            if key in self._sessions:
                sess = self._sessions[key]
                sess.last_seen_ts = timestamp
                sess.confidences.append(conf)
                duration = (timestamp - sess.start_ts).total_seconds()
                if duration >= self.min_duration_sec:
                    sess.is_confirmed = True
            else:
                self._sessions[key] = _InteractionSession(
                    track_id=track_id,
                    zone_id=zone_id,
                    start_ts=timestamp,
                    last_seen_ts=timestamp,
                    confidences=[conf],
                    is_confirmed=(self.min_duration_sec <= 0.0),
                )

        emitted_events: list[InteractionEvent] = []
        keys_to_remove: list[tuple[str, str]] = []

        for key, sess in self._sessions.items():
            if key not in current_interactions:
                time_since_last = (timestamp - sess.last_seen_ts).total_seconds()
                if time_since_last > self.grace_period_sec:
                    # Session finished
                    duration = (sess.last_seen_ts - sess.start_ts).total_seconds()
                    if sess.is_confirmed and duration >= self.min_duration_sec:
                        mean_conf = (
                            float(np.mean(sess.confidences)) if sess.confidences else 0.8
                        )
                        emitted_events.append(
                            InteractionEvent(
                                event_id=f"interact_{uuid.uuid4().hex[:12]}",
                                track_id=sess.track_id,
                                zone_id=sess.zone_id,
                                start_ts=sess.start_ts,
                                end_ts=sess.last_seen_ts,
                                confidence=max(0.0, min(1.0, mean_conf)),
                                interaction_type="examine" if duration > 5.0 else "touch",
                            )
                        )
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._sessions[key]

        return emitted_events

    def flush(self) -> list[InteractionEvent]:
        """Flush active confirmed sessions at end of stream."""
        emitted: list[InteractionEvent] = []
        for sess in self._sessions.values():
            duration = (sess.last_seen_ts - sess.start_ts).total_seconds()
            if sess.is_confirmed and duration >= self.min_duration_sec:
                mean_conf = float(np.mean(sess.confidences)) if sess.confidences else 0.8
                emitted.append(
                    InteractionEvent(
                        event_id=f"interact_{uuid.uuid4().hex[:12]}",
                        track_id=sess.track_id,
                        zone_id=sess.zone_id,
                        start_ts=sess.start_ts,
                        end_ts=sess.last_seen_ts,
                        confidence=max(0.0, min(1.0, mean_conf)),
                        interaction_type="examine" if duration > 5.0 else "touch",
                    )
                )
        self._sessions.clear()
        return emitted
