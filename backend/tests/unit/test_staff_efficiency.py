from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from analytics.staff_efficiency import (
    AlertResponseStats,
    CounterUtilization,
    StaffEfficiencySummary,
    compute_staff_efficiency,
)
from core.schemas import Alert, QueueEvent
from storage.repository import EventRepository


@pytest.fixture
def repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_staff_kpi.db"
    return EventRepository(db_path)


def test_empty_event_window(repo: EventRepository) -> None:
    """Empty event window should return zero active counters, zero recommendations,

    0.0 follow rate, and no response stats."""
    summary = compute_staff_efficiency(repo)

    assert isinstance(summary, StaffEfficiencySummary)
    assert isinstance(summary.counter_utilization, CounterUtilization)
    assert isinstance(summary.alert_response, AlertResponseStats)

    assert summary.counter_utilization.counters_active == 0
    assert summary.counter_utilization.counters_recommended == 0
    assert summary.counter_utilization.recommendation_follow_rate == 0.0

    assert summary.alert_response.total_resolved == 0
    assert summary.alert_response.avg_response_time_sec is None
    assert summary.alert_response.min_response_time_sec is None
    assert summary.alert_response.max_response_time_sec is None


def test_since_equal_until(repo: EventRepository) -> None:
    """Window where since == until should query exact timestamp matching."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    repo.save_queue_event(
        QueueEvent(
            event_id="q1",
            counter_id="counter_1",
            timestamp=t0,
            queue_length=3,
        )
    )
    repo.save_queue_event(
        QueueEvent(
            event_id="q2",
            counter_id="counter_2",
            timestamp=t0 + timedelta(minutes=5),
            queue_length=1,
        )
    )

    summary = compute_staff_efficiency(repo, since=t0, until=t0)
    assert summary.counter_utilization.counters_active == 1


def test_since_greater_than_until_raises_value_error(repo: EventRepository) -> None:
    """since > until should raise ValueError in compute_staff_efficiency."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 12, 9, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="since cannot be after until"):
        compute_staff_efficiency(repo, since=t0, until=t1)


def test_multiple_queue_events_same_counter(repo: EventRepository) -> None:
    """Multiple QueueEvents for the SAME counter must only count as 1 active counter."""
    base_t = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    for i in range(5):
        repo.save_queue_event(
            QueueEvent(
                event_id=f"q_{i}",
                counter_id="counter_checkout_1",
                timestamp=base_t + timedelta(minutes=i * 2),
                queue_length=2 + i,
            )
        )

    summary = compute_staff_efficiency(
        repo,
        since=base_t - timedelta(minutes=1),
        until=base_t + timedelta(minutes=15),
    )

    assert summary.counter_utilization.counters_active == 1


def test_multiple_counters_distinct_count(repo: EventRepository) -> None:
    """Distinct active counters must count unique counter_ids with >= 1 QueueEvent."""
    base_t = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="counter_1", timestamp=base_t, queue_length=2)
    )
    repo.save_queue_event(
        QueueEvent(
            event_id="q2",
            counter_id="counter_1",
            timestamp=base_t + timedelta(minutes=1),
            queue_length=3,
        )
    )
    repo.save_queue_event(
        QueueEvent(
            event_id="q3",
            counter_id="counter_2",
            timestamp=base_t + timedelta(minutes=2),
            queue_length=1,
        )
    )
    repo.save_queue_event(
        QueueEvent(
            event_id="q4",
            counter_id="counter_3",
            timestamp=base_t + timedelta(minutes=3),
            queue_length=4,
        )
    )

    summary = compute_staff_efficiency(repo)
    assert summary.counter_utilization.counters_active == 3


def test_zero_counters_recommended(repo: EventRepository) -> None:
    """recommendation_follow_rate MUST be 0.0 when counters_recommended == 0."""
    base_t = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="counter_1", timestamp=base_t, queue_length=1)
    )

    summary = compute_staff_efficiency(repo)
    assert summary.counter_utilization.counters_recommended == 0
    assert summary.counter_utilization.recommendation_follow_rate == 0.0


def test_recommendation_with_follow_up(repo: EventRepository) -> None:
    """When a counter opening recommendation is followed by opening an additional counter,

    follow rate should be 1.0."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 12, 10, 5, 0, tzinfo=UTC)

    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="counter_1", timestamp=t0, queue_length=6)
    )
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="queue_congestion",
            severity="warning",
            zone_id="counter_1",
            message=(
                "Checkout counter counter_1 has 6 people waiting"
                " â€” consider opening another counter"
            ),
            created_at=t0,
            resolved_at=None,
        )
    )

    # Follow-up: counter_2 opens and records queue event
    repo.save_queue_event(
        QueueEvent(event_id="q2", counter_id="counter_2", timestamp=t1, queue_length=1)
    )

    summary = compute_staff_efficiency(repo)
    assert summary.counter_utilization.counters_recommended == 1
    assert summary.counter_utilization.recommendations_followed == 1
    assert summary.counter_utilization.recommendation_follow_rate == 1.0


def test_recommendation_without_follow_up(repo: EventRepository) -> None:
    """When a counter opening recommendation is not followed by any new counter opening,

    follow rate should be 0.0."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 12, 10, 5, 0, tzinfo=UTC)

    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="counter_1", timestamp=t0, queue_length=6)
    )
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="queue_congestion",
            severity="warning",
            zone_id="counter_1",
            message=(
                "Checkout counter counter_1 has 6 people waiting"
                " â€” consider opening another counter"
            ),
            created_at=t0,
            resolved_at=None,
        )
    )

    # Only counter_1 records another event; no other counter opens
    repo.save_queue_event(
        QueueEvent(event_id="q2", counter_id="counter_1", timestamp=t1, queue_length=7)
    )

    summary = compute_staff_efficiency(repo)
    assert summary.counter_utilization.counters_recommended == 1
    assert summary.counter_utilization.recommendations_followed == 0
    assert summary.counter_utilization.recommendation_follow_rate == 0.0


def test_mixed_recommendations_follow_up_rate(repo: EventRepository) -> None:
    """Multiple recommendations with some followed and some not followed."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 9, 12, 10, 5, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 12, 11, 0, 0, tzinfo=UTC)

    # Recommendation 1 on counter_1 followed by counter_2
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="queue_congestion",
            severity="warning",
            zone_id="counter_1",
            message="consider opening another counter",
            created_at=t0,
        )
    )
    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="counter_2", timestamp=t1, queue_length=1)
    )

    # Recommendation 2 on counter_2 at 11:00 with no other counter opening after 11:00
    repo.save_alert(
        Alert(
            alert_id="a2",
            alert_type="queue_congestion",
            severity="warning",
            zone_id="counter_2",
            message="consider opening another counter",
            created_at=t2,
        )
    )

    summary = compute_staff_efficiency(repo)
    assert summary.counter_utilization.counters_recommended == 2
    assert summary.counter_utilization.recommendations_followed == 1
    assert summary.counter_utilization.recommendation_follow_rate == 0.5


def test_unresolved_alerts_excluded_from_response_stats(repo: EventRepository) -> None:
    """Unresolved alerts (resolved_at is None) MUST be excluded entirely from AlertResponseStats

    and never treated as having zero response time."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="Shelf 1 is low on stock",
            created_at=t0,
            resolved_at=None,
        )
    )
    repo.save_alert(
        Alert(
            alert_id="a2",
            alert_type="queue_congestion",
            severity="critical",
            zone_id="counter_1",
            message="Counter congested",
            created_at=t0,
            resolved_at=None,
        )
    )

    summary = compute_staff_efficiency(repo)
    assert summary.alert_response.total_resolved == 0
    assert summary.alert_response.avg_response_time_sec is None
    assert summary.alert_response.min_response_time_sec is None
    assert summary.alert_response.max_response_time_sec is None


def test_resolved_alerts_response_time_calculation(repo: EventRepository) -> None:
    """Resolved alerts calculate avg, min, and max response time in seconds."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    # Alert 1: 60 seconds to resolve
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="low stock",
            created_at=t0,
            resolved_at=t0 + timedelta(seconds=60),
        )
    )
    # Alert 2: 120 seconds to resolve
    repo.save_alert(
        Alert(
            alert_id="a2",
            alert_type="queue_congestion",
            severity="critical",
            zone_id="counter_1",
            message="congestion",
            created_at=t0,
            resolved_at=t0 + timedelta(seconds=120),
        )
    )

    summary = compute_staff_efficiency(repo)
    assert summary.alert_response.total_resolved == 2
    assert summary.alert_response.min_response_time_sec == 60.0
    assert summary.alert_response.max_response_time_sec == 120.0
    assert summary.alert_response.avg_response_time_sec == 90.0


def test_mixed_resolved_and_unresolved_alerts(repo: EventRepository) -> None:
    """Unresolved alerts must NOT skew the average response time."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)

    # Resolved alert: 180s
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="low_stock",
            severity="warning",
            message="low stock",
            created_at=t0,
            resolved_at=t0 + timedelta(seconds=180),
        )
    )
    # Unresolved alert
    repo.save_alert(
        Alert(
            alert_id="a2",
            alert_type="queue_congestion",
            severity="warning",
            message="congested",
            created_at=t0,
            resolved_at=None,
        )
    )

    summary = compute_staff_efficiency(repo)
    assert summary.alert_response.total_resolved == 1
    assert summary.alert_response.avg_response_time_sec == 180.0


def test_absence_of_identity_and_staff_level_fields(repo: EventRepository) -> None:
    """Ensure no response model field contains staff names, staff IDs, employee IDs,

    or individual identity data (zero-PII / store-level only)."""
    summary = compute_staff_efficiency(repo)
    summary_dict = summary.model_dump()

    forbidden_substrings = ["employee", "staff_id", "staff_name", "user_id", "person_id"]

    def _check_keys(d: dict[str, object]) -> None:
        for k, v in d.items():
            for forbidden in forbidden_substrings:
                assert forbidden not in k.lower(), f"Forbidden key found: {k}"
            if isinstance(v, dict):
                _check_keys(v)

    _check_keys(summary_dict)

