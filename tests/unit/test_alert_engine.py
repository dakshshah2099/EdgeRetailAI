from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from alerts.alert_engine import AlertEngine
from schemas import Alert, QueueEvent, StockEvent


@pytest.fixture
def alert_engine() -> AlertEngine:
    return AlertEngine(
        low_stock_threshold=0.6,
        queue_congestion_length=3,
    )


def make_stock_event(
    shelf_id: str,
    status: str,
    confidence: float = 0.9,
    ts: datetime | None = None,
) -> StockEvent:
    return StockEvent(
        event_id=f"stock_{shelf_id}_{status}",
        shelf_id=shelf_id,
        timestamp=ts or datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC),
        status=status,  # type: ignore[arg-type]
        confidence=confidence,
    )


def make_queue_event(
    counter_id: str,
    queue_length: int,
    ts: datetime | None = None,
) -> QueueEvent:
    return QueueEvent(
        event_id=f"q_{counter_id}_{queue_length}",
        counter_id=counter_id,
        timestamp=ts or datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC),
        queue_length=queue_length,
        avg_wait_est_sec=float(queue_length * 60),
    )


def test_stock_empty_produces_critical_alert(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    event = make_stock_event("shelf_a", "empty", confidence=0.85, ts=t0)

    alert = alert_engine.process_stock_event(event)

    assert alert is not None
    assert isinstance(alert, Alert)
    assert alert.alert_type == "low_stock"
    assert alert.severity == "critical"
    assert alert.zone_id == "shelf_a"
    assert alert.created_at == t0
    assert alert.resolved_at is None
    assert "out of stock" in alert.message.lower()

    open_alerts = alert_engine.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0].alert_id == alert.alert_id


def test_stock_low_produces_warning_alert(alert_engine: AlertEngine) -> None:
    event = make_stock_event("shelf_a", "low", confidence=0.8)
    alert = alert_engine.process_stock_event(event)

    assert alert is not None
    assert alert.alert_type == "low_stock"
    assert alert.severity == "warning"
    assert alert.zone_id == "shelf_a"
    assert "low on stock" in alert.message.lower()


def test_stock_escalates_from_warning_to_critical(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 2, 0, tzinfo=UTC)

    # 1. Low stock -> warning
    event_low = make_stock_event("shelf_a", "low", confidence=0.8, ts=t0)
    alert_warn = alert_engine.process_stock_event(event_low)
    assert alert_warn is not None
    assert alert_warn.severity == "warning"

    # 2. Empty stock -> escalates to critical with same alert_id
    event_empty = make_stock_event("shelf_a", "empty", confidence=0.9, ts=t1)
    alert_crit = alert_engine.process_stock_event(event_empty)
    assert alert_crit is not None
    assert alert_crit.alert_id == alert_warn.alert_id
    assert alert_crit.severity == "critical"
    assert alert_crit.created_at == t0
    assert alert_crit.resolved_at is None
    assert "out of stock" in alert_crit.message.lower()

    # Still only 1 open alert
    open_alerts = alert_engine.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0].severity == "critical"


def test_stock_below_confidence_threshold_no_alert(alert_engine: AlertEngine) -> None:
    # Threshold is 0.6; confidence 0.4 should not trigger alert
    event = make_stock_event("shelf_a", "empty", confidence=0.4)
    alert = alert_engine.process_stock_event(event)

    assert alert is None
    assert alert_engine.get_open_alerts() == []


def test_stock_debounce_consecutive_breaches(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 0, 10, tzinfo=UTC)

    event_1 = make_stock_event("shelf_a", "empty", confidence=0.9, ts=t0)
    event_2 = make_stock_event("shelf_a", "empty", confidence=0.95, ts=t1)

    alert_1 = alert_engine.process_stock_event(event_1)
    assert alert_1 is not None

    # Second event while breached should debounce and return None
    alert_2 = alert_engine.process_stock_event(event_2)
    assert alert_2 is None

    # Only 1 open alert maintained
    open_alerts = alert_engine.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0].alert_id == alert_1.alert_id


def test_stock_resolution_on_ok_status(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 5, 0, tzinfo=UTC)

    event_breach = make_stock_event("shelf_a", "empty", ts=t0)
    opened_alert = alert_engine.process_stock_event(event_breach)
    assert opened_alert is not None

    # Status clears to OK at t1
    event_ok = make_stock_event("shelf_a", "ok", ts=t1)
    resolved_alerts = alert_engine.check_resolutions(
        latest_stock_events={"shelf_a": event_ok},
        latest_queue_events={},
    )

    assert len(resolved_alerts) == 1
    resolved = resolved_alerts[0]
    assert resolved.alert_id == opened_alert.alert_id
    assert resolved.resolved_at == t1
    assert resolved.created_at == t0
    assert alert_engine.get_open_alerts() == []

    # Subsequent check when already resolved returns nothing
    subsequent_resolutions = alert_engine.check_resolutions(
        latest_stock_events={"shelf_a": event_ok},
        latest_queue_events={},
    )
    assert subsequent_resolutions == []


def test_stock_low_confidence_does_not_resolve_alert(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 5, 0, tzinfo=UTC)

    event_breach = make_stock_event("shelf_a", "empty", ts=t0)
    opened_alert = alert_engine.process_stock_event(event_breach)
    assert opened_alert is not None

    # Momentary low-confidence detection (still empty, confidence=0.3 < threshold 0.6)
    event_low_conf = make_stock_event("shelf_a", "empty", confidence=0.3, ts=t1)
    resolved_alerts = alert_engine.check_resolutions(
        latest_stock_events={"shelf_a": event_low_conf},
        latest_queue_events={},
    )

    # Must NOT resolve
    assert resolved_alerts == []
    assert len(alert_engine.get_open_alerts()) == 1


def test_stock_reopens_new_alert_after_resolution(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 5, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 29, 10, 10, 0, tzinfo=UTC)

    # 1. Breach
    alert_1 = alert_engine.process_stock_event(make_stock_event("shelf_a", "empty", ts=t0))
    assert alert_1 is not None

    # 2. Resolve
    alert_engine.check_resolutions(
        latest_stock_events={"shelf_a": make_stock_event("shelf_a", "ok", ts=t1)},
        latest_queue_events={},
    )

    # 3. Breach again
    alert_2 = alert_engine.process_stock_event(make_stock_event("shelf_a", "empty", ts=t2))
    assert alert_2 is not None
    assert alert_2.alert_id != alert_1.alert_id
    assert alert_2.created_at == t2


def test_queue_congestion_warning_and_critical(alert_engine: AlertEngine) -> None:
    # Threshold is 3; margin 1.5x -> critical threshold is >= 5 (or >= 4.5 -> 5)
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)

    # Length 3 (at threshold) -> warning
    event_warn = make_queue_event("counter_1", queue_length=3, ts=t0)
    alert_warn = alert_engine.process_queue_event(event_warn)
    assert alert_warn is not None
    assert alert_warn.alert_type == "queue_congestion"
    assert alert_warn.severity == "warning"
    assert alert_warn.zone_id == "counter_1"
    assert "consider opening another counter" in alert_warn.message

    alert_engine.reset()

    # Length 5 (exceeds 1.5x threshold) -> critical
    event_crit = make_queue_event("counter_1", queue_length=5, ts=t0)
    alert_crit = alert_engine.process_queue_event(event_crit)
    assert alert_crit is not None
    assert alert_crit.severity == "critical"


def test_queue_escalates_from_warning_to_critical(alert_engine: AlertEngine) -> None:
    # Threshold is 3; critical is >= 5
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 2, 0, tzinfo=UTC)

    # 1. Queue length 3 -> warning alert
    event_warn = make_queue_event("counter_1", queue_length=3, ts=t0)
    alert_warn = alert_engine.process_queue_event(event_warn)
    assert alert_warn is not None
    assert alert_warn.severity == "warning"

    # 2. Queue grows to 7 (critical) -> escalates existing alert
    event_crit = make_queue_event("counter_1", queue_length=7, ts=t1)
    alert_crit = alert_engine.process_queue_event(event_crit)
    assert alert_crit is not None
    assert alert_crit.alert_id == alert_warn.alert_id
    assert alert_crit.severity == "critical"
    assert alert_crit.created_at == t0
    assert alert_crit.resolved_at is None
    assert "7 people waiting" in alert_crit.message

    # 3. Queue grows further to 9 (already critical) -> debounce (returns None)
    t2 = datetime(2026, 8, 29, 10, 4, 0, tzinfo=UTC)
    event_crit2 = make_queue_event("counter_1", queue_length=9, ts=t2)
    assert alert_engine.process_queue_event(event_crit2) is None

    # Only 1 open alert maintained
    open_alerts = alert_engine.get_open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0].severity == "critical"


def test_queue_below_threshold_no_alert(alert_engine: AlertEngine) -> None:
    event = make_queue_event("counter_1", queue_length=2)
    assert alert_engine.process_queue_event(event) is None
    assert alert_engine.get_open_alerts() == []


def test_queue_debounce_consecutive_breaches(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 1, 0, tzinfo=UTC)

    event_1 = make_queue_event("counter_1", queue_length=3, ts=t0)
    event_2 = make_queue_event("counter_1", queue_length=3, ts=t1)

    alert_1 = alert_engine.process_queue_event(event_1)
    assert alert_1 is not None

    # Debounced
    alert_2 = alert_engine.process_queue_event(event_2)
    assert alert_2 is None
    assert len(alert_engine.get_open_alerts()) == 1


def test_queue_resolution_on_drop_below_threshold(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 2, 0, tzinfo=UTC)

    event_breach = make_queue_event("counter_1", queue_length=4, ts=t0)
    opened_alert = alert_engine.process_queue_event(event_breach)
    assert opened_alert is not None

    # Queue drops below threshold (2 < 3)
    event_cleared = make_queue_event("counter_1", queue_length=2, ts=t1)
    resolved_alerts = alert_engine.check_resolutions(
        latest_stock_events={},
        latest_queue_events={"counter_1": event_cleared},
    )

    assert len(resolved_alerts) == 1
    assert resolved_alerts[0].alert_id == opened_alert.alert_id
    assert resolved_alerts[0].resolved_at == t1
    assert alert_engine.get_open_alerts() == []


def test_independent_multizone_tracking(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 3, 0, tzinfo=UTC)

    # 4 independent breaches
    alert_engine.process_stock_event(make_stock_event("shelf_1", "empty", ts=t0))
    alert_engine.process_stock_event(make_stock_event("shelf_2", "low", ts=t0))
    alert_engine.process_queue_event(make_queue_event("counter_1", queue_length=3, ts=t0))
    alert_engine.process_queue_event(make_queue_event("counter_2", queue_length=4, ts=t0))

    assert len(alert_engine.get_open_alerts()) == 4

    # Resolve only shelf_1 and counter_2
    resolved = alert_engine.check_resolutions(
        latest_stock_events={
            "shelf_1": make_stock_event("shelf_1", "ok", ts=t1),
            "shelf_2": make_stock_event("shelf_2", "low", ts=t1),
        },
        latest_queue_events={
            "counter_1": make_queue_event("counter_1", queue_length=3, ts=t1),
            "counter_2": make_queue_event("counter_2", queue_length=0, ts=t1),
        },
    )

    assert len(resolved) == 2
    resolved_zones = {r.zone_id for r in resolved}
    assert resolved_zones == {"shelf_1", "counter_2"}

    # Remaining open alerts are shelf_2 and counter_1
    open_zones = {a.zone_id for a in alert_engine.get_open_alerts()}
    assert open_zones == {"shelf_2", "counter_1"}


def test_reset_clears_all_open_alerts(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    alert_engine.process_stock_event(make_stock_event("shelf_1", "empty", ts=t0))
    alert_engine.process_queue_event(make_queue_event("counter_1", queue_length=4, ts=t0))

    assert len(alert_engine.get_open_alerts()) == 2

    alert_engine.reset()
    assert alert_engine.get_open_alerts() == []

    # New event can fire immediately after reset
    new_alert = alert_engine.process_stock_event(make_stock_event("shelf_1", "empty", ts=t0))
    assert new_alert is not None


def test_no_pii_in_alert_model(alert_engine: AlertEngine) -> None:
    event = make_stock_event("shelf_a", "empty")
    alert = alert_engine.process_stock_event(event)
    assert alert is not None

    alert_dict = alert.model_dump()
    forbidden_keys = {"image", "frame", "crop", "embedding", "face", "pixels"}
    for key in alert_dict:
        assert key.lower() not in forbidden_keys


def test_frozen_alert_immutability(alert_engine: AlertEngine) -> None:
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    alert = alert_engine.process_stock_event(make_stock_event("shelf_a", "empty", ts=t0))
    assert alert is not None

    with pytest.raises(ValidationError):
        alert.resolved_at = t0 + timedelta(seconds=60)
