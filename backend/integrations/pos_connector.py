import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class POSStockUpdate:
    """Outbound payload representing a stock-related event pushed to POS/ERP.

    Generic shape — real POS/ERP systems vary widely, so this models the
    common denominator (SKU/shelf reference, status, timestamp) rather than
    a specific vendor's API contract. No PII or raw pixel data is persisted.
    """

    shelf_id: str
    status: Literal["empty", "low", "ok"]
    alert_id: str | None
    timestamp: datetime


@dataclass(frozen=True)
class POSSalesRecord:
    """Inbound payload representing a transaction pulled from POS/ERP, used
    to compute footfall-to-conversion KPIs.

    Total amount is optional (None) if the POS feed withholds financial data
    or only exposes basket unit counts.
    """

    transaction_id: str
    timestamp: datetime
    item_count: int
    total_amount: float | None = None


class POSConnector(ABC):
    """Swap point: a mock/stub implementation for the POC, a real vendor
    SDK/REST client for production. Same swap-point philosophy as
    InferenceBackend (Slice 2) and SyncBuffer's sink (Slice 7).
    """

    @abstractmethod
    def push_stock_update(self, update: POSStockUpdate) -> bool:
        """Push a stock update to POS/ERP. Returns True on success."""
        ...

    @abstractmethod
    def pull_recent_sales(self, since: datetime) -> list[POSSalesRecord]:
        """Pull transactions since the given timestamp. Returns empty list
        if the POS/ERP system doesn't support this or none exist.
        """
        ...


class MockPOSConnector(POSConnector):
    """NON-PRODUCTION stub: logs pushes and returns configurable canned sales
    data for testing. NOT A REAL INTEGRATION.

    Explicitly flagged via `is_mock=True` and `is_production=False` to prevent
    accidental deployment in live environments.
    """

    is_mock: bool = True
    is_production: bool = False

    def __init__(
        self,
        canned_sales: list[POSSalesRecord] | None = None,
        fail_push: bool = False,
    ) -> None:
        logger.warning(
            "MockPOSConnector is active: this is an in-memory stub and NOT a production "
            "POS/ERP integration."
        )
        self._canned_sales: list[POSSalesRecord] = list(canned_sales) if canned_sales else []
        self._fail_push: bool = fail_push
        self.pushed_updates: list[POSStockUpdate] = []

    def push_stock_update(self, update: POSStockUpdate) -> bool:
        """Mock push: records update in memory if fail_push is False, else returns False."""
        if self._fail_push:
            logger.warning(
                "MockPOSConnector: simulated failure pushing stock update for shelf %s",
                update.shelf_id,
            )
            return False

        self.pushed_updates.append(update)
        logger.info(
            "MockPOSConnector: pushed stock update for shelf %s: %s",
            update.shelf_id,
            update,
        )
        return True

    def pull_recent_sales(self, since: datetime) -> list[POSSalesRecord]:
        """Mock pull: returns canned sales filtered to transactions at or after `since`."""

        def _is_gte(target: datetime, threshold: datetime) -> bool:
            if threshold.tzinfo is not None and target.tzinfo is None:
                target = target.replace(tzinfo=threshold.tzinfo)
            elif threshold.tzinfo is None and target.tzinfo is not None:
                target = target.replace(tzinfo=None)
            return target >= threshold

        return [r for r in self._canned_sales if _is_gte(r.timestamp, since)]
