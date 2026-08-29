import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from detection.tracker import TrackedDetection
from schemas import Frame, QueueEvent, ZoneConfig


@dataclass
class _ActiveQueueTrack:
    track_id: str
    zone_id: str
    start_ts: datetime
    last_ts: datetime


class QueueMonitor:
    """Counts tracked people inside each checkout zone and estimates wait
    time from a rolling average of how long tracks remain in the zone."""

    def __init__(
        self,
        service_rate_estimate_sec: float = 90.0,
        max_history: int = 50,
    ) -> None:
        """service_rate_estimate_sec: fallback average service time per
        person, used only until enough real dwell-in-queue samples exist
        to estimate it empirically. State clearly which mode is active."""
        self.service_rate_estimate_sec = float(service_rate_estimate_sec)
        self.max_history = max_history
        # Mapping of (track_id, zone_id) -> _ActiveQueueTrack
        self._active_tracks: dict[tuple[str, str], _ActiveQueueTrack] = {}
        # Mapping of zone_id -> deque of completed service durations (seconds)
        self._service_times: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.max_history)
        )

    def reset(self) -> None:
        """Clear active tracks and accumulated empirical service-time history."""
        self._active_tracks.clear()
        self._service_times.clear()

    def update(
        self,
        frame: Frame,
        tracked_detections: list[TrackedDetection],
        checkout_zones: list[ZoneConfig],
    ) -> list[QueueEvent]:
        """One QueueEvent per checkout zone per call — queue_length = count
        of tracks currently inside that zone's polygon."""
        events: list[QueueEvent] = []

        # Filter for checkout zones only
        active_zones = [z for z in checkout_zones if z.zone_type == "checkout"]

        for zone in active_zones:
            poly_np = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
            current_tracks_in_zone: list[TrackedDetection] = []

            for det in tracked_detections:
                # Bottom-center anchor point representing person ground position
                anchor_x = float(det.bbox[0] + det.bbox[2] / 2.0)
                anchor_y = float(det.bbox[1] + det.bbox[3])
                point = (anchor_x, anchor_y)

                if cv2.pointPolygonTest(poly_np, point, False) >= 0:
                    current_tracks_in_zone.append(det)

            current_track_ids = {d.track_id for d in current_tracks_in_zone}

            # Update active tracks in this zone
            for det in current_tracks_in_zone:
                key = (det.track_id, zone.zone_id)
                if key in self._active_tracks:
                    self._active_tracks[key].last_ts = frame.timestamp
                else:
                    self._active_tracks[key] = _ActiveQueueTrack(
                        track_id=det.track_id,
                        zone_id=zone.zone_id,
                        start_ts=frame.timestamp,
                        last_ts=frame.timestamp,
                    )

            # Detect completed service / track departure from this zone
            departed_keys = [
                key
                for key in self._active_tracks
                if key[1] == zone.zone_id and key[0] not in current_track_ids
            ]

            for key in departed_keys:
                active_session = self._active_tracks.pop(key)
                duration = (active_session.last_ts - active_session.start_ts).total_seconds()
                if duration > 0.0:
                    self._service_times[zone.zone_id].append(duration)

            queue_length = len(current_tracks_in_zone)

            # Estimate wait time: queue_length * empirical average service time
            if queue_length == 0:
                avg_wait_est_sec: float | None = 0.0
            else:
                zone_history = self._service_times.get(zone.zone_id)
                if zone_history and len(zone_history) > 0:
                    avg_service_time = sum(zone_history) / len(zone_history)
                else:
                    avg_service_time = self.service_rate_estimate_sec
                avg_wait_est_sec = float(queue_length * avg_service_time)

            events.append(
                QueueEvent(
                    event_id=f"queue_{uuid.uuid4().hex[:12]}",
                    counter_id=zone.zone_id,
                    timestamp=frame.timestamp,
                    queue_length=queue_length,
                    avg_wait_est_sec=avg_wait_est_sec,
                )
            )

        return events
