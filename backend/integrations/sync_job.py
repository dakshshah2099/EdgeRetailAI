import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from core.schemas import Alert
from storage.repository import EventRepository

from integrations.pos_connector import POSConnector, POSSalesRecord, POSStockUpdate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncJobResult:
    """Summary of a POS/ERP synchronization cycle."""

    job_id: str
    timestamp: datetime
    pushed_count: int
    pulled_count: int
    failures: list[str] = field(default_factory=list)
    pushed_updates: list[POSStockUpdate] = field(default_factory=list)
    sales_records: list[POSSalesRecord] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.failures) == 0


def _alert_to_stock_status(alert: Alert) -> Literal["empty", "low"]:
    """Maps alert severity to stock status. Severity is fully determined by
    Slice 6's AlertEngine (critical only for status=='empty', warning only
    for status=='low') — no need to parse message text."""
    return "empty" if alert.severity == "critical" else "low"


def run_sync_job(
    repo: EventRepository,
    connector: POSConnector,
    since: datetime,
) -> SyncJobResult:
    """One sync cycle: fetch open low_stock alerts from repo, push each as
    a POSStockUpdate, pull recent sales, return a summary (counts pushed/
    pulled, any failures). Callable on a schedule or manually — this slice
    does not own the scheduling mechanism.
    """
    job_id = f"sync_{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC)

    pushed_updates: list[POSStockUpdate] = []
    failures: list[str] = []

    # 1. Fetch only open alerts from repository
    open_alerts = repo.get_open_alerts()
    # Filter strictly for low_stock alerts (never raw StockEvents or other alert types)
    low_stock_alerts = [
        a for a in open_alerts if a.alert_type == "low_stock" and a.resolved_at is None
    ]

    for alert in low_stock_alerts:
        shelf_id = alert.zone_id if alert.zone_id else "unknown"
        status = _alert_to_stock_status(alert)
        update = POSStockUpdate(
            shelf_id=shelf_id,
            status=status,
            alert_id=alert.alert_id,
            timestamp=alert.created_at,
        )

        try:
            success = connector.push_stock_update(update)
            if success:
                pushed_updates.append(update)
            else:
                failures.append(
                    f"Failed to push stock update for shelf '{update.shelf_id}' "
                    f"(alert_id: {update.alert_id})"
                )
        except Exception as exc:
            logger.exception("Error pushing stock update for shelf %s", update.shelf_id)
            failures.append(
                f"Exception pushing stock update for shelf '{update.shelf_id}': {exc}"
            )

    # 2. Pull recent sales transactions from POS/ERP
    sales_records: list[POSSalesRecord] = []
    try:
        sales_records = connector.pull_recent_sales(since=since)
    except Exception as exc:
        logger.exception("Error pulling recent sales from POS")
        failures.append(f"Exception pulling sales records: {exc}")

    return SyncJobResult(
        job_id=job_id,
        timestamp=now,
        pushed_count=len(pushed_updates),
        pulled_count=len(sales_records),
        failures=failures,
        pushed_updates=pushed_updates,
        sales_records=sales_records,
    )
