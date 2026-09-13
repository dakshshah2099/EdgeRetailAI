from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from core.schemas import Alert, DetectionEvent, QueueEvent, StockEvent
from reports.report_builder import (
    ReportSnapshot,
    build_daily_report,
    build_weekly_report,
)
from storage.repository import EventRepository


@pytest.fixture
def repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_report_builder.db"
    return EventRepository(db_path)


def test_empty_event_window(repo: EventRepository) -> None:
    """Empty event window produces ReportSnapshot with total_events == 0 and is_empty == True."""
    snap = build_daily_report(date(2026, 9, 12), repo)

    assert isinstance(snap, ReportSnapshot)
    assert snap.report_type == "daily"
    assert snap.total_events == 0
    assert snap.is_empty is True
    assert snap.footfall.total_enters == 0
    assert snap.footfall.total_exits == 0
    assert snap.queues == []
    assert snap.stock == []
    assert snap.alerts == []


def test_daily_report_exact_boundaries(repo: EventRepository) -> None:
    """Daily report window is [day 00:00:00, day+1 00:00:00).

    Events at start are included; events at next day 00:00:00 are excluded.
    """
    target_day = date(2026, 9, 12)
    start_ts = datetime(2026, 9, 12, 0, 0, 0, tzinfo=UTC)
    mid_ts = datetime(2026, 9, 12, 12, 30, 0, tzinfo=UTC)
    last_sec = datetime(2026, 9, 12, 23, 59, 59, tzinfo=UTC)
    next_day_ts = datetime(2026, 9, 13, 0, 0, 0, tzinfo=UTC)
    prev_day_ts = datetime(2026, 9, 11, 23, 59, 59, tzinfo=UTC)

    # Pre-boundary event (excluded)
    repo.save_detection_event(
        DetectionEvent(
            event_id="d_prev",
            camera_id="camera_main",
            track_id="t1",
            timestamp=prev_day_ts,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="enter",
        )
    )
    # Start boundary event (included)
    repo.save_detection_event(
        DetectionEvent(
            event_id="d_start",
            camera_id="camera_main",
            track_id="t2",
            timestamp=start_ts,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="enter",
        )
    )
    # Mid-day event (included)
    repo.save_detection_event(
        DetectionEvent(
            event_id="d_mid",
            camera_id="camera_main",
            track_id="t3",
            timestamp=mid_ts,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="enter",
        )
    )
    # End-boundary second (included)
    repo.save_detection_event(
        DetectionEvent(
            event_id="d_last",
            camera_id="camera_main",
            track_id="t4",
            timestamp=last_sec,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="exit",
        )
    )
    # Exactly next day 00:00:00 (excluded from [day, day+1))
    repo.save_detection_event(
        DetectionEvent(
            event_id="d_next",
            camera_id="camera_main",
            track_id="t5",
            timestamp=next_day_ts,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="enter",
        )
    )

    snap = build_daily_report(target_day, repo)

    assert snap.total_events == 3
    assert snap.footfall.total_enters == 2
    assert snap.footfall.total_exits == 1
    assert snap.footfall.net_occupancy == 1


def test_weekly_report_7_day_window(repo: EventRepository) -> None:
    """Weekly window is exactly [week_start, week_start + 7 days) â€” no eighth day."""
    start_date = date(2026, 9, 7)  # Monday
    t_start = datetime(2026, 9, 7, 0, 0, 0, tzinfo=UTC)
    t_day7 = datetime(2026, 9, 13, 23, 59, 59, tzinfo=UTC)
    t_day8 = datetime(2026, 9, 14, 0, 0, 0, tzinfo=UTC)

    # Included in week
    repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="c1", timestamp=t_start, queue_length=2)
    )
    repo.save_queue_event(
        QueueEvent(event_id="q2", counter_id="c1", timestamp=t_day7, queue_length=3)
    )
    # Excluded: 8th day
    repo.save_queue_event(
        QueueEvent(event_id="q3", counter_id="c1", timestamp=t_day8, queue_length=4)
    )

    snap = build_weekly_report(start_date, repo)

    assert snap.report_type == "weekly"
    assert snap.window_end - snap.window_start == timedelta(days=7)
    assert len(snap.queues) == 1  # get_queue_kpi returns latest per counter
    assert snap.total_events == 2


def test_event_inclusion_across_all_event_types(repo: EventRepository) -> None:
    """Ensure footfall, queues, stock, and alerts are aggregated together in the snapshot."""
    t = datetime(2026, 9, 12, 14, 0, 0, tzinfo=UTC)

    repo.save_detection_event(
        DetectionEvent(
            event_id="d1",
            camera_id="camera_main",
            track_id="t1",
            timestamp=t,
            bbox=(0, 0, 10, 10),
            zone_id="entrance",
            event_type="enter",
        )
    )
    repo.save_queue_event(QueueEvent(event_id="q1", counter_id="c1", timestamp=t, queue_length=4))
    repo.save_stock_event(
        StockEvent(
            event_id="s1",
            shelf_id="shelf_1",
            timestamp=t,
            status="low",
            confidence=0.88,
        )
    )
    repo.save_alert(
        Alert(
            alert_id="a1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="Shelf low",
            created_at=t,
            resolved_at=t + timedelta(seconds=60),
        )
    )

    snap = build_daily_report("2026-09-12", repo)

    assert snap.total_events == 4
    assert snap.footfall.total_enters == 1
    assert len(snap.queues) == 1
    assert len(snap.stock) == 1
    assert len(snap.alerts) == 1


def test_staff_efficiency_integration_when_available(repo: EventRepository) -> None:
    """When staff_efficiency is available, snapshot.staff_efficiency is populated."""
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    repo.save_queue_event(QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=1))

    snap = build_daily_report(date(2026, 9, 12), repo)

    assert snap.staff_efficiency is not None
    assert snap.staff_efficiency.counter_utilization.counters_active == 1


def test_staff_efficiency_none_when_unavailable(repo: EventRepository) -> None:
    """ReportSnapshot.staff_efficiency must be None if staff_efficiency is absent

    or unimportable.
    """
    t0 = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
    repo.save_queue_event(QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=1))

    with patch("reports.report_builder.compute_staff_efficiency", None):
        snap = build_daily_report(date(2026, 9, 12), repo)
        assert snap.staff_efficiency is None

