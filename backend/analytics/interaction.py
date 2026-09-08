"""Product interaction engine detecting proximity and engagement
between shoppers and shelf products.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

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
    detection_confidences: list[float] = field(default_factory=list)
    proximity_confidences: list[float] = field(default_factory=list)
    is_confirmed: bool = False
    start_emitted: bool = False


class ProductInteractionDetector:
    """Detects shopper interaction with retail shelf/product zones.

    Criteria:
    - Spatial proximity: Key points of person bbox within configurable pixel distance.
    - Temporal debouncing: Interaction must persist for min_duration_sec.
    - Occlusion & missed-frame tolerance: Brief dropouts (<= grace_period_sec) tolerated.
    - Emits typed InteractionEvent with event_phase "start" when confirmed,
      and event_phase "end" on completion or flush.
    - Separates detection_confidence from interaction_confidence.
    """

    def __init__(
        self,
        proximity_margin_px: float = 60.0,
        min_duration_sec: float = 1.0,
        grace_period_sec: float = 1.5,
        examine_threshold_sec: float = 5.0,
    ) -> None:
        self.proximity_margin_px = proximity_margin_px
        self.min_duration_sec = min_duration_sec
        self.grace_period_sec = grace_period_sec
        self.examine_threshold_sec = examine_threshold_sec
        self._sessions: dict[tuple[str, str], _InteractionSession] = {}
        self._zone_polygons_cache: dict[str, npt.NDArray[np.int32]] = {}

    def reset(self) -> None:
        """Reset all active sessions (use between evaluation scenarios)."""
        self._sessions.clear()
        self._zone_polygons_cache.clear()

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
    ) -> tuple[bool, float]:
        """Return (is_proximate, proximity_confidence) for person bbox vs zone polygon.

        Proximity confidence is a normalised distance-based score in [0, 1].
        """
        poly = self._get_poly(zone)
        x, y, w, h = track_bbox
        top_center = (float(x + w / 2.0), float(y))
        mid_point = (float(x + w / 2.0), float(y + h / 2.0))
        bottom_center = (float(x + w / 2.0), float(y + h))

        best_dist = float("-inf")
        for pt in (top_center, mid_point, bottom_center):
            dist = cv2.pointPolygonTest(poly, pt, True)  # +inside, -outside
            if dist > best_dist:
                best_dist = dist

        if best_dist >= -self.proximity_margin_px:
            # Normalise: 0.5 at boundary, 1.0 when well inside
            norm = (best_dist + self.proximity_margin_px) / (
                self.proximity_margin_px + max(1.0, self.proximity_margin_px)
            )
            return True, max(0.5, min(1.0, norm))
        return False, 0.0

    def _build_event(
        self,
        sess: _InteractionSession,
        phase: Literal["start", "end"],
        now_ts: datetime,
    ) -> InteractionEvent:
        duration = (sess.last_seen_ts - sess.start_ts).total_seconds()
        det_conf = (
            float(np.mean(sess.detection_confidences)) if sess.detection_confidences else 0.8
        )
        prox_conf = (
            float(np.mean(sess.proximity_confidences)) if sess.proximity_confidences else 0.8
        )
        i_type: Literal["approach", "touch", "pickup", "examine"] = (
            "examine" if duration > self.examine_threshold_sec else "touch"
        )
        end_ts = sess.last_seen_ts if phase == "end" else now_ts
        return InteractionEvent(
            event_id=f"interact_{uuid.uuid4().hex[:12]}",
            track_id=sess.track_id,
            zone_id=sess.zone_id,
            start_ts=sess.start_ts,
            end_ts=end_ts,
            event_phase=phase,
            detection_confidence=max(0.0, min(1.0, det_conf)),
            interaction_confidence=max(0.0, min(1.0, prox_conf)),
            interaction_type=i_type,
        )

    def update(
        self,
        tracks: list[TrackedDetection],
        zones: list[ZoneConfig],
        timestamp: datetime,
    ) -> list[InteractionEvent]:
        """Update interactions with tracks and shelf/product zones from current frame."""
        shelf_zones = [z for z in zones if z.zone_type in ("shelf", "product_display")]
        person_tracks = [t for t in tracks if t.class_id == 0]

        current_interactions: dict[tuple[str, str], tuple[float, float]] = {}
        for track in person_tracks:
            for zone in shelf_zones:
                proximate, prox_conf = self._is_proximate(track.bbox, zone)
                if proximate:
                    current_interactions[(track.track_id, zone.zone_id)] = (
                        track.confidence,
                        prox_conf,
                    )

        emitted_events: list[InteractionEvent] = []

        # Update or create sessions
        for (track_id, zone_id), (det_conf, prox_conf) in current_interactions.items():
            key = (track_id, zone_id)
            if key in self._sessions:
                sess = self._sessions[key]
                sess.last_seen_ts = timestamp
                sess.detection_confidences.append(det_conf)
                sess.proximity_confidences.append(prox_conf)
                duration = (timestamp - sess.start_ts).total_seconds()
                if not sess.is_confirmed and duration >= self.min_duration_sec:
                    sess.is_confirmed = True
                    # Emit start event on confirmation
                    if not sess.start_emitted:
                        sess.start_emitted = True
                        emitted_events.append(self._build_event(sess, "start", timestamp))
            else:
                confirmed_immediately = self.min_duration_sec <= 0.0
                self._sessions[key] = _InteractionSession(
                    track_id=track_id,
                    zone_id=zone_id,
                    start_ts=timestamp,
                    last_seen_ts=timestamp,
                    detection_confidences=[det_conf],
                    proximity_confidences=[prox_conf],
                    is_confirmed=confirmed_immediately,
                )

        keys_to_remove: list[tuple[str, str]] = []

        for key, sess in self._sessions.items():
            if key not in current_interactions:
                time_since_last = (timestamp - sess.last_seen_ts).total_seconds()
                if time_since_last > self.grace_period_sec:
                    # Session finished
                    duration = (sess.last_seen_ts - sess.start_ts).total_seconds()
                    if sess.is_confirmed and duration >= self.min_duration_sec:
                        emitted_events.append(self._build_event(sess, "end", timestamp))
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
                emitted.append(self._build_event(sess, "end", sess.last_seen_ts))
        self._sessions.clear()
        return emitted
