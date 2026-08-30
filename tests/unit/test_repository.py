from datetime import UTC, datetime, timedelta
from pathlib import Path

from schemas import Alert, DetectionEvent, DwellEvent, QueueEvent, StockEvent
from storage.repository import EventRepository


def test_detection_event_save_and_query_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    event = DetectionEvent(
        event_id="det_01",
        track_id="tr_100",
        timestamp=now,
        bbox=(10, 20, 100, 200),
        zone_id="entry_zone",
        event_type="enter",
    )

    repo.save_detection_event(event)

    events = repo.get_recent_detection_events(limit=10)
    assert len(events) == 1
    retrieved = events[0]
    assert retrieved == event


def test_dwell_event_save_and_query_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    t1 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 30, 10, 2, 30, tzinfo=UTC)
    dwell = DwellEvent(
        event_id="dwell_01",
        zone_id="shelf_1",
        track_id="tr_42",
        start_ts=t1,
        end_ts=t2,
        duration_sec=150.0,
    )

    repo.save_dwell_event(dwell)

    events = repo.get_recent_dwell_events(limit=10)
    assert len(events) == 1
    assert events[0] == dwell


def test_stock_event_save_and_query_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    stock1 = StockEvent(
        event_id="stk_01",
        shelf_id="shelf_a",
        timestamp=now,
        status="low",
        confidence=0.92,
    )
    stock2 = StockEvent(
        event_id="stk_02",
        shelf_id="shelf_b",
        timestamp=now + timedelta(seconds=10),
        status="empty",
        confidence=0.98,
    )

    repo.save_stock_event(stock1)
    repo.save_stock_event(stock2)

    events = repo.get_recent_stock_events(limit=10)
    assert len(events) == 2
    # Should be ordered descending by timestamp
    assert events[0] == stock2
    assert events[1] == stock1


def test_queue_event_save_and_query_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    q_event = QueueEvent(
        event_id="q_01",
        counter_id="counter_1",
        timestamp=now,
        queue_length=4,
        avg_wait_est_sec=120.5,
    )

    repo.save_queue_event(q_event)

    events = repo.get_recent_queue_events(limit=10)
    assert len(events) == 1
    assert events[0] == q_event


def test_alert_save_and_query_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    alert = Alert(
        alert_id="alt_01",
        alert_type="low_stock",
        severity="warning",
        zone_id="zone_shelf_1",
        message="Shelf 1 low stock detected",
        created_at=now,
    )

    repo.save_alert(alert)

    open_alerts = repo.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0] == alert


def test_upsert_alert_updates_existing_row_without_duplicate(tmp_path: Path) -> None:
    """Slice 6 resolution pattern test: save open alert, then upsert resolved version.
    Only one row must exist, reflecting the new resolved_at."""
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    t_created = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    open_alert = Alert(
        alert_id="alt_resolution_test",
        alert_type="queue_congestion",
        severity="critical",
        zone_id="checkout_main",
        message="Queue congested",
        created_at=t_created,
        resolved_at=None,
    )

    repo.save_alert(open_alert)

    # Verify open alert is present
    open_alerts = repo.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0].alert_id == "alt_resolution_test"
    assert open_alerts[0].resolved_at is None

    # Upsert resolved alert with same alert_id
    t_resolved = datetime(2026, 8, 30, 12, 5, 0, tzinfo=UTC)
    resolved_alert = Alert(
        alert_id="alt_resolution_test",
        alert_type="queue_congestion",
        severity="critical",
        zone_id="checkout_main",
        message="Queue congested",
        created_at=t_created,
        resolved_at=t_resolved,
    )

    repo.upsert_alert(resolved_alert)

    # Must no longer be in open alerts
    assert len(repo.get_open_alerts()) == 0

    # Must be in all alerts with exactly 1 row
    all_alerts = repo.get_all_alerts()
    assert len(all_alerts) == 1
    assert all_alerts[0].alert_id == "alt_resolution_test"
    assert all_alerts[0].resolved_at == t_resolved

    # Direct query by id
    alert_by_id = repo.get_alert_by_id("alt_resolution_test")
    assert alert_by_id is not None
    assert alert_by_id == resolved_alert


def test_upsert_alert_inserts_new_row_if_not_present(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    alert = Alert(
        alert_id="alt_new_01",
        alert_type="custom",
        severity="info",
        message="System startup notice",
        created_at=now,
    )

    repo.upsert_alert(alert)

    retrieved = repo.get_alert_by_id("alt_new_01")
    assert retrieved is not None
    assert retrieved == alert


def test_query_limits_and_filtering(tmp_path: Path) -> None:
    db_path = tmp_path / "retail.db"
    repo = EventRepository(db_path)

    now = datetime.now(UTC)
    for i in range(10):
        repo.save_stock_event(
            StockEvent(
                event_id=f"stk_{i:02d}",
                shelf_id="shelf_a" if i % 2 == 0 else "shelf_b",
                timestamp=now + timedelta(seconds=i),
                status="ok",
                confidence=0.9,
            )
        )

    # Test limit
    recent_3 = repo.get_recent_stock_events(limit=3)
    assert len(recent_3) == 3
    assert recent_3[0].event_id == "stk_09"

    # Test shelf_id filter
    shelf_b_events = repo.get_recent_stock_events(limit=10, shelf_id="shelf_b")
    assert len(shelf_b_events) == 5
    assert all(e.shelf_id == "shelf_b" for e in shelf_b_events)
