from datetime import UTC, datetime
from pathlib import Path

import pytest

from integrations.pos_connector import (
    MockPOSConnector,
    POSSalesRecord,
    POSStockUpdate,
)
from integrations.sync_job import run_sync_job
from schemas import Alert
from storage.repository import EventRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> EventRepository:
    db_file = tmp_path / "test_retail.db"
    return EventRepository(db_file)


def test_run_sync_job_pushes_only_open_low_stock_alerts(test_repo: EventRepository) -> None:
    now = datetime.now(UTC)

    # 1. Open low_stock warning
    test_repo.save_alert(
        Alert(
            alert_id="alt_low_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_a",
            message="Shelf shelf_a is low on stock",
            created_at=now,
            resolved_at=None,
        )
    )

    # 2. Open low_stock critical (empty)
    test_repo.save_alert(
        Alert(
            alert_id="alt_empty_2",
            alert_type="low_stock",
            severity="critical",
            zone_id="shelf_b",
            message="Shelf shelf_b is out of stock",
            created_at=now,
            resolved_at=None,
        )
    )

    # 3. Resolved low_stock alert (should be ignored)
    test_repo.save_alert(
        Alert(
            alert_id="alt_resolved_3",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_c",
            message="Shelf shelf_c is low on stock",
            created_at=now,
            resolved_at=now,
        )
    )

    # 4. Open queue_congestion alert (should be ignored)
    test_repo.save_alert(
        Alert(
            alert_id="alt_queue_4",
            alert_type="queue_congestion",
            severity="critical",
            zone_id="counter_1",
            message="Checkout congested",
            created_at=now,
            resolved_at=None,
        )
    )

    # 5. Open custom alert (should be ignored)
    test_repo.save_alert(
        Alert(
            alert_id="alt_custom_5",
            alert_type="custom",
            severity="info",
            zone_id="zone_entry",
            message="Custom event",
            created_at=now,
            resolved_at=None,
        )
    )

    connector = MockPOSConnector()
    result = run_sync_job(test_repo, connector, since=now)

    assert result.pushed_count == 2
    assert len(result.failures) == 0
    assert result.success is True
    assert len(connector.pushed_updates) == 2

    # Verify pushed details
    shelves = {u.shelf_id: u for u in connector.pushed_updates}
    assert "shelf_a" in shelves
    assert shelves["shelf_a"].status == "low"
    assert shelves["shelf_a"].alert_id == "alt_low_1"

    assert "shelf_b" in shelves
    assert shelves["shelf_b"].status == "empty"
    assert shelves["shelf_b"].alert_id == "alt_empty_2"


def test_run_sync_job_records_push_failure_not_swallowed(test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    test_repo.save_alert(
        Alert(
            alert_id="alt_fail_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_fail",
            message="Shelf low",
            created_at=now,
            resolved_at=None,
        )
    )

    # Mock connector configured to return False
    connector = MockPOSConnector(fail_push=True)
    result = run_sync_job(test_repo, connector, since=now)

    assert result.pushed_count == 0
    assert len(result.failures) == 1
    assert "shelf_fail" in result.failures[0]
    assert result.success is False


def test_run_sync_job_handles_connector_exception_as_failure(test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    test_repo.save_alert(
        Alert(
            alert_id="alt_exc_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_exc",
            message="Shelf low",
            created_at=now,
            resolved_at=None,
        )
    )

    class CrashingPOSConnector(MockPOSConnector):
        def push_stock_update(self, update: POSStockUpdate) -> bool:
            raise ConnectionError("POS network timeout")

    connector = CrashingPOSConnector()
    result = run_sync_job(test_repo, connector, since=now)

    assert result.pushed_count == 0
    assert len(result.failures) == 1
    assert "POS network timeout" in result.failures[0]
    assert result.success is False


def test_run_sync_job_pulls_sales_records(test_repo: EventRepository) -> None:
    t1 = datetime(2026, 9, 5, 10, 0, tzinfo=UTC)
    t2 = datetime(2026, 9, 5, 11, 0, tzinfo=UTC)
    t3 = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    sales = [
        POSSalesRecord(transaction_id="t1", timestamp=t1, item_count=1, total_amount=10.0),
        POSSalesRecord(transaction_id="t2", timestamp=t2, item_count=2, total_amount=20.0),
        POSSalesRecord(transaction_id="t3", timestamp=t3, item_count=3, total_amount=30.0),
    ]

    connector = MockPOSConnector(canned_sales=sales)
    result = run_sync_job(test_repo, connector, since=t2)

    assert result.pulled_count == 2
    assert [r.transaction_id for r in result.sales_records] == ["t2", "t3"]
    assert result.success is True


def test_run_sync_job_handles_sales_pull_exception(test_repo: EventRepository) -> None:
    now = datetime.now(UTC)

    class SalesCrashingConnector(MockPOSConnector):
        def pull_recent_sales(self, since: datetime) -> list[POSSalesRecord]:
            raise TimeoutError("POS API offline")

    connector = SalesCrashingConnector()
    result = run_sync_job(test_repo, connector, since=now)

    assert result.pulled_count == 0
    assert len(result.failures) == 1
    assert "POS API offline" in result.failures[0]
    assert result.success is False
