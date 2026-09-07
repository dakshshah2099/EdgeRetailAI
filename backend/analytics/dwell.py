import uuid
from dataclasses import dataclass
from datetime import datetime

from core.schemas import DetectionEvent, DwellEvent


@dataclass
class _ActiveDwell:
    track_id: str
    zone_id: str
    start_ts: datetime
    last_ts: datetime


class DwellTracker:
    """Tracks how long each anonymous track stays inside product_display
    zones and emits a DwellEvent when the track leaves (or on session end
    for tracks still present).
    """

    def __init__(self, min_duration_sec: float = 0.0) -> None:
        self.min_duration_sec = min_duration_sec
        # Mapping of (track_id, zone_id) -> _ActiveDwell
        self._active_dwells: dict[tuple[str, str], _ActiveDwell] = {}

    def reset(self) -> None:
        """Clear all active dwell tracking states without emitting events."""
        self._active_dwells.clear()

    def update(self, events: list[DetectionEvent]) -> list[DwellEvent]:
        """Process DetectionEvents for the current frame and emit DwellEvents
        for any track that has exited a zone.
        """
        current_in_zone_keys: set[tuple[str, str]] = set()

        for event in events:
            if event.event_type == "in_zone" and event.zone_id is not None:
                key = (event.track_id, event.zone_id)
                current_in_zone_keys.add(key)
                if key in self._active_dwells:
                    self._active_dwells[key].last_ts = event.timestamp
                else:
                    self._active_dwells[key] = _ActiveDwell(
                        track_id=event.track_id,
                        zone_id=event.zone_id,
                        start_ts=event.timestamp,
                        last_ts=event.timestamp,
                    )

        emitted_events: list[DwellEvent] = []

        # Find any active dwells no longer present in this frame
        exited_keys = [key for key in self._active_dwells if key not in current_in_zone_keys]

        for key in exited_keys:
            session = self._active_dwells.pop(key)
            duration_sec = (session.last_ts - session.start_ts).total_seconds()
            if duration_sec >= self.min_duration_sec:
                emitted_events.append(
                    DwellEvent(
                        event_id=f"dwell_{uuid.uuid4().hex[:12]}",
                        zone_id=session.zone_id,
                        track_id=session.track_id,
                        start_ts=session.start_ts,
                        end_ts=session.last_ts,
                        duration_sec=duration_sec,
                    )
                )

        return emitted_events

    def flush(self) -> list[DwellEvent]:
        """Finalize and emit DwellEvents for all tracks still active inside zones
        at session/stream end.
        """
        emitted_events: list[DwellEvent] = []
        for session in self._active_dwells.values():
            duration_sec = (session.last_ts - session.start_ts).total_seconds()
            if duration_sec >= self.min_duration_sec:
                emitted_events.append(
                    DwellEvent(
                        event_id=f"dwell_{uuid.uuid4().hex[:12]}",
                        zone_id=session.zone_id,
                        track_id=session.track_id,
                        start_ts=session.start_ts,
                        end_ts=session.last_ts,
                        duration_sec=duration_sec,
                    )
                )
        self._active_dwells.clear()
        return emitted_events
