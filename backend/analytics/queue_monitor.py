import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from analytics.zone_membership import anchor_point, is_inside_zone
from core.schemas import Frame, QueueEvent, ZoneConfig
from vision.tracker import TrackedDetection


@dataclass
class _ActiveQueueTrack:
    track_id: str
    zone_id: str
    start_ts: datetime
    last_ts: datetime


class QueueMonitor:
    """Counts tracked people inside each checkout zone, estimates wait
    time from a rolling average of service duration, and forecasts
    congestion using arrival vs service rate dynamics blended with
    historical hourly trends (FR9/FR11)."""

    def __init__(
        self,
        service_rate_estimate_sec: float = 90.0,
        max_history: int = 50,
        rate_window_sec: float = 120.0,
        forecast_horizon_sec: float = 180.0,
        hourly_baseline_provider: Callable[[str, int], float | None] | None = None,
    ) -> None:
        """service_rate_estimate_sec: fallback average service time per person.
        rate_window_sec: rolling time window for calculating arrival and departure rates.
        forecast_horizon_sec: forward lookahead window for congestion projection (default 3m).
        hourly_baseline_provider: optional callable(counter_id, hour_of_day) -> avg_queue_length.
        """
        self.service_rate_estimate_sec = float(service_rate_estimate_sec)
        self.max_history = max_history
        self.rate_window_sec = float(rate_window_sec)
        self.forecast_horizon_sec = float(forecast_horizon_sec)
        self.hourly_baseline_provider = hourly_baseline_provider

        # Mapping of (track_id, zone_id) -> _ActiveQueueTrack
        self._active_tracks: dict[tuple[str, str], _ActiveQueueTrack] = {}
        # Mapping of zone_id -> deque of completed service durations (seconds)
        self._service_times: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.max_history)
        )
        # Tracking recent arrival and departure timestamps for rate estimation
        self._arrivals: dict[str, deque[datetime]] = defaultdict(
            lambda: deque(maxlen=self.max_history * 2)
        )
        self._departures: dict[str, deque[datetime]] = defaultdict(
            lambda: deque(maxlen=self.max_history * 2)
        )

    def reset(self) -> None:
        """Clear active tracks, history, and rate counters."""
        self._active_tracks.clear()
        self._service_times.clear()
        self._arrivals.clear()
        self._departures.clear()

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
            current_tracks_in_zone: list[TrackedDetection] = []

            for det in tracked_detections:
                point = anchor_point(det.bbox)
                if is_inside_zone(point, zone):
                    current_tracks_in_zone.append(det)

            current_track_ids = {d.track_id for d in current_tracks_in_zone}

            # Update active tracks in this zone and record arrivals
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
                    self._arrivals[zone.zone_id].append(frame.timestamp)

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
                self._departures[zone.zone_id].append(frame.timestamp)

            queue_length = len(current_tracks_in_zone)

            # Calculate empirical or fallback average service time
            zone_history = self._service_times.get(zone.zone_id)
            if zone_history and len(zone_history) > 0:
                avg_service_time = sum(zone_history) / len(zone_history)
            else:
                avg_service_time = self.service_rate_estimate_sec

            if queue_length == 0:
                avg_wait_est_sec: float | None = 0.0
            else:
                avg_wait_est_sec = float(queue_length * avg_service_time)

            # --- FR9 Congestion Prediction ---
            window_cutoff = frame.timestamp - timedelta(seconds=self.rate_window_sec)
            recent_arrivals = [
                t for t in self._arrivals[zone.zone_id] if t >= window_cutoff
            ]
            recent_departures = [
                t for t in self._departures[zone.zone_id] if t >= window_cutoff
            ]

            window_duration = max(10.0, self.rate_window_sec)
            arrival_rate_per_sec = len(recent_arrivals) / window_duration
            if recent_departures:
                service_rate_per_sec = len(recent_departures) / window_duration
            else:
                service_rate_per_sec = 1.0 / max(1.0, avg_service_time)

            # Net growth projected over forecast horizon
            net_rate_per_sec = arrival_rate_per_sec - service_rate_per_sec
            projected_dynamic_q = max(
                0.0, queue_length + net_rate_per_sec * self.forecast_horizon_sec
            )

            # Blend with historical hourly baseline if available
            hourly_baseline: float | None = None
            if self.hourly_baseline_provider is not None:
                try:
                    hourly_baseline = self.hourly_baseline_provider(
                        zone.zone_id, frame.timestamp.hour
                    )
                except Exception:
                    hourly_baseline = None

            if hourly_baseline is not None and hourly_baseline >= 0.0:
                blended_q = 0.7 * projected_dynamic_q + 0.3 * hourly_baseline
            else:
                blended_q = projected_dynamic_q

            predicted_queue_length = int(round(blended_q))
            predicted_wait_sec = float(predicted_queue_length * avg_service_time)

            events.append(
                QueueEvent(
                    event_id=f"queue_{uuid.uuid4().hex[:12]}",
                    counter_id=zone.zone_id,
                    timestamp=frame.timestamp,
                    queue_length=queue_length,
                    avg_wait_est_sec=avg_wait_est_sec,
                    predicted_queue_length=predicted_queue_length,
                    predicted_wait_sec=predicted_wait_sec,
                )
            )

        return events
