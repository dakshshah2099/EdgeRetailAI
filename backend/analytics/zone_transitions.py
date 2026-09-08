"""Zone transition analytics tracking customer progression through retail zones."""

from collections import defaultdict

from core.schemas import DetectionEvent, ZoneTransition


class ZoneTransitionTracker:
    """Tracks ordered zone journeys (e.g. entrance -> shelf -> checkout).

    Criteria:
    - Records ordered sequence of distinct zones visited by each track.
    - Emits ZoneTransition events when a track switches active zone.
    - Aggregates transition matrix for customer flow analysis.
    """

    def __init__(self) -> None:
        # track_id -> current active zone_id
        self._current_zones: dict[str, str] = {}
        # track_id -> ordered list of zone_ids visited
        self._zone_history: dict[str, list[str]] = defaultdict(list)
        # (from_zone, to_zone) -> transition count
        self._transition_counts: dict[tuple[str, str], int] = defaultdict(int)

    def reset(self) -> None:
        """Reset all tracking states."""
        self._current_zones.clear()
        self._zone_history.clear()
        self._transition_counts.clear()

    def update(self, events: list[DetectionEvent]) -> list[ZoneTransition]:
        """Process detection events in current frame and record zone transitions."""
        transitions: list[ZoneTransition] = []

        for event in events:
            if event.event_type != "in_zone" or event.zone_id is None:
                continue

            track_id = event.track_id
            new_zone = event.zone_id
            prev_zone = self._current_zones.get(track_id)

            if prev_zone is None:
                self._current_zones[track_id] = new_zone
                self._zone_history[track_id].append(new_zone)
            elif prev_zone != new_zone:
                # Track transitioned to a different zone
                self._current_zones[track_id] = new_zone
                self._zone_history[track_id].append(new_zone)
                self._transition_counts[(prev_zone, new_zone)] += 1
                transitions.append(
                    ZoneTransition(
                        track_id=track_id,
                        from_zone_id=prev_zone,
                        to_zone_id=new_zone,
                        timestamp=event.timestamp,
                    )
                )

        return transitions

    def get_track_path(self, track_id: str) -> list[str]:
        """Return the sequence of zones visited by a specific track."""
        return list(self._zone_history.get(track_id, []))

    def get_transition_counts(self) -> dict[tuple[str, str], int]:
        """Return dictionary of (from_zone, to_zone) transition counts."""
        return dict(self._transition_counts)
