from datetime import UTC, datetime, timedelta

import pytest

from core.schemas import Alert, DetectionEvent
from integrations.pos_connector import MockPOSConnector, POSSalesRecord
from integrations.sync_job import run_sync_job
from storage.repository import EventRepository


@pytest.mark.e2e
def test_pos_sync_and_conversion_pipeline(e2e_repo: EventRepository) -> None:
    """End-to-End test of POS/ERP bidirectional integration:

    - Vision pipeline footfall and shelf alerts persist to SQLite.
    - Sync job pushes stock replenishment updates to POS connector.
    - Sync job pulls transaction records from POS connector.
    - Correlates footfall to transactions for conversion rate and basket size KPIs.
    """
    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)

    # 1. Simulate 10 shopper enters over 30 minutes
    for i in range(10):
        t = base_time + timedelta(minutes=i * 3)
        e2e_repo.save_detection_event(
            DetectionEvent(
                event_id=f"enter_evt_{i}",
                track_id=f"shopper_{i}",
                timestamp=t,
                bbox=(100, 100, 30, 60),
                zone_id="zone_entrance",
                event_type="enter",
            )
        )

    # 2. Simulate 2 open stock replenishment alerts and 1 resolved alert
    alert_bev = Alert(
        alert_id="alert_bev_01",
        alert_type="low_stock",
        severity="warning",
        zone_id="zone_shelf_beverages",
        message="Beverage shelf running low on stock",
        created_at=base_time + timedelta(minutes=5),
        resolved_at=None,
    )
    alert_snack = Alert(
        alert_id="alert_snack_01",
        alert_type="low_stock",
        severity="critical",
        zone_id="zone_shelf_snacks",
        message="Snack shelf completely out of stock",
        created_at=base_time + timedelta(minutes=10),
        resolved_at=None,
    )
    alert_resolved = Alert(
        alert_id="alert_resolved_01",
        alert_type="low_stock",
        severity="warning",
        zone_id="zone_shelf_dairy",
        message="Dairy restocked",
        created_at=base_time,
        resolved_at=base_time + timedelta(minutes=2),
    )
    e2e_repo.save_alert(alert_bev)
    e2e_repo.save_alert(alert_snack)
    e2e_repo.save_alert(alert_resolved)

    # 3. Setup POS connector with canned sales records
    canned_sales = [
        POSSalesRecord(
            transaction_id="tx_1001",
            timestamp=base_time + timedelta(minutes=8),
            item_count=3,
            total_amount=15.50,
        ),
        POSSalesRecord(
            transaction_id="tx_1002",
            timestamp=base_time + timedelta(minutes=15),
            item_count=5,
            total_amount=42.00,
        ),
        POSSalesRecord(
            transaction_id="tx_1003",
            timestamp=base_time + timedelta(minutes=22),
            item_count=1,
            total_amount=8.75,
        ),
        POSSalesRecord(
            transaction_id="tx_1004",
            timestamp=base_time + timedelta(minutes=28),
            item_count=4,
            total_amount=25.00,
        ),
    ]
    connector = MockPOSConnector(canned_sales=canned_sales)

    # 4. Execute sync job
    sync_since = base_time - timedelta(minutes=5)
    sync_result = run_sync_job(repo=e2e_repo, connector=connector, since=sync_since)

    # Assert outbound stock updates
    assert sync_result.success is True
    assert sync_result.pushed_count == 2
    assert len(connector.pushed_updates) == 2

    pushed_shelves = {u.shelf_id: u.status for u in connector.pushed_updates}
    assert pushed_shelves["zone_shelf_beverages"] == "low"
    assert pushed_shelves["zone_shelf_snacks"] == "empty"

    # Assert inbound sales records
    assert sync_result.pulled_count == 4
    assert len(sync_result.sales_records) == 4

    # 5. Compute retail conversion and basket analytics
    events = e2e_repo.get_recent_detection_events(limit=100)
    footfall_enters = sum(1 for e in events if e.event_type == "enter")
    assert footfall_enters == 10

    total_transactions = len(sync_result.sales_records)
    conversion_rate = (total_transactions / footfall_enters) * 100.0
    assert conversion_rate == 40.0

    total_revenue = sum(
        r.total_amount for r in sync_result.sales_records if r.total_amount is not None
    )
    assert total_revenue == pytest.approx(91.25)

    avg_transaction_value = total_revenue / total_transactions
    assert avg_transaction_value == pytest.approx(22.8125)

    total_items = sum(r.item_count for r in sync_result.sales_records)
    avg_basket_size = total_items / total_transactions
    assert avg_basket_size == 3.25


@pytest.mark.e2e
def test_pos_sync_failure_resilience(e2e_repo: EventRepository) -> None:
    """Verify that network or connector failure during POS push is handled safely

    without corrupting the repository or dropping alerts.
    """
    now = datetime.now(UTC)
    e2e_repo.save_alert(
        Alert(
            alert_id="alert_fail_test",
            alert_type="low_stock",
            severity="warning",
            zone_id="zone_shelf_fail",
            message="Test failure",
            created_at=now,
            resolved_at=None,
        )
    )

    failing_connector = MockPOSConnector(fail_push=True)
    result = run_sync_job(repo=e2e_repo, connector=failing_connector, since=now)

    assert result.success is False
    assert result.pushed_count == 0
    assert len(result.failures) == 1
    assert "zone_shelf_fail" in result.failures[0]

    # Alert remains open in repository for future retry
    open_alerts = e2e_repo.get_open_alerts()
    assert any(a.alert_id == "alert_fail_test" for a in open_alerts)
