import logging
from datetime import UTC, datetime

import pytest
from integrations.pos_connector import (
    MockPOSConnector,
    POSConnector,
    POSSalesRecord,
    POSStockUpdate,
)


def test_mock_pos_connector_is_clearly_non_production(caplog: pytest.LogCaptureFixture) -> None:
    """MockPOSConnector must be explicitly recognizable as a non-production stub."""
    with caplog.at_level(logging.WARNING):
        connector = MockPOSConnector()

    # Explicit flag and property checks
    assert connector.is_mock is True
    assert connector.is_production is False
    assert issubclass(MockPOSConnector, POSConnector)
    assert "non-production" in (MockPOSConnector.__doc__ or "").lower()

    # Verified warning in logs
    assert any("not a production" in record.message.lower() for record in caplog.records)


def test_pos_stock_update_has_no_pii_or_pixels() -> None:
    """Outbound payload must not carry image, pixel, or PII attributes."""
    fields = POSStockUpdate.__annotations__.keys()
    forbidden = {"image", "frame", "pixel", "face", "embedding", "track_id", "person"}
    assert forbidden.isdisjoint(fields)


def test_pos_sales_record_has_no_pii_or_pixels() -> None:
    """Inbound payload must not carry image, pixel, or PII attributes."""
    fields = POSSalesRecord.__annotations__.keys()
    forbidden = {"image", "frame", "pixel", "face", "embedding", "customer_name", "credit_card"}
    assert forbidden.isdisjoint(fields)


def test_mock_pos_connector_push_stock_update() -> None:
    connector = MockPOSConnector()
    update = POSStockUpdate(
        shelf_id="shelf_1",
        status="low",
        alert_id="alert_001",
        timestamp=datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
    )

    success = connector.push_stock_update(update)
    assert success is True
    assert len(connector.pushed_updates) == 1
    assert connector.pushed_updates[0] == update


def test_mock_pos_connector_push_failure_simulation() -> None:
    connector = MockPOSConnector(fail_push=True)
    update = POSStockUpdate(
        shelf_id="shelf_2",
        status="empty",
        alert_id="alert_002",
        timestamp=datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
    )

    success = connector.push_stock_update(update)
    assert success is False
    assert len(connector.pushed_updates) == 0


def test_mock_pos_connector_pull_recent_sales_filters_by_since() -> None:
    sales = [
        POSSalesRecord(
            transaction_id="tx_1",
            timestamp=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
            item_count=2,
            total_amount=19.99,
        ),
        POSSalesRecord(
            transaction_id="tx_2",
            timestamp=datetime(2026, 9, 5, 11, 0, tzinfo=UTC),
            item_count=1,
            total_amount=5.50,
        ),
        POSSalesRecord(
            transaction_id="tx_3",
            timestamp=datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
            item_count=4,
            total_amount=42.00,
        ),
    ]

    connector = MockPOSConnector(canned_sales=sales)
    since = datetime(2026, 9, 5, 11, 0, tzinfo=UTC)
    results = connector.pull_recent_sales(since)

    assert len(results) == 2
    assert [r.transaction_id for r in results] == ["tx_2", "tx_3"]
