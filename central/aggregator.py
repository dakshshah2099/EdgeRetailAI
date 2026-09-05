import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from api.schemas_api import FootfallSummary
from central.store_registry import StoreConfig
from schemas import QueueEvent, StockEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoreStatus:
    store_id: str
    reachable: bool
    footfall_summary: FootfallSummary | None  # None if unreachable
    open_alert_count: int | None
    queue_events: list[QueueEvent] | None
    stock_events: list[StockEvent] | None
    error: str | None  # populated if unreachable, explains why


@dataclass(frozen=True)
class CrossStoreSummary:
    generated_at: datetime
    stores: list[StoreStatus]
    total_reachable: int
    total_unreachable: int


def poll_store(
    config: StoreConfig,
    timeout_sec: float = 5.0,
    client: httpx.Client | None = None,
) -> StoreStatus:
    """Query one store's API. On timeout/connection failure, return a
    StoreStatus with reachable=False and error populated — never raise,
    never let one unreachable store block polling the others.
    """
    base_url = config.api_base_url.rstrip("/")
    should_close = False
    http_client = client
    if http_client is None:
        http_client = httpx.Client(timeout=timeout_sec)
        should_close = True

    try:
        # 1. Fetch footfall summary
        resp_footfall = http_client.get(f"{base_url}/kpi/footfall", timeout=timeout_sec)
        resp_footfall.raise_for_status()
        footfall_summary = FootfallSummary.model_validate(resp_footfall.json())

        # 2. Fetch open alerts count
        resp_alerts = http_client.get(
            f"{base_url}/alerts", params={"status": "open"}, timeout=timeout_sec
        )
        resp_alerts.raise_for_status()
        alerts_data = resp_alerts.json()
        open_alert_count = len(alerts_data) if isinstance(alerts_data, list) else 0

        # 3. Fetch queue events
        resp_queue = http_client.get(f"{base_url}/kpi/queue", timeout=timeout_sec)
        resp_queue.raise_for_status()
        queue_json = resp_queue.json()
        queue_events = (
            [QueueEvent.model_validate(q) for q in queue_json]
            if isinstance(queue_json, list)
            else []
        )

        # 4. Fetch stock events
        resp_stock = http_client.get(f"{base_url}/kpi/stock", timeout=timeout_sec)
        resp_stock.raise_for_status()
        stock_json = resp_stock.json()
        stock_events = (
            [StockEvent.model_validate(s) for s in stock_json]
            if isinstance(stock_json, list)
            else []
        )

        return StoreStatus(
            store_id=config.store_id,
            reachable=True,
            footfall_summary=footfall_summary,
            open_alert_count=open_alert_count,
            queue_events=queue_events,
            stock_events=stock_events,
            error=None,
        )
    except Exception as exc:
        logger.warning(
            "Failed polling store %s (%s): %s",
            config.store_id,
            config.api_base_url,
            exc,
        )
        return StoreStatus(
            store_id=config.store_id,
            reachable=False,
            footfall_summary=None,
            open_alert_count=None,
            queue_events=None,
            stock_events=None,
            error=str(exc),
        )
    finally:
        if should_close:
            http_client.close()


def aggregate_stores(
    registry: list[StoreConfig],
    timeout_sec: float = 5.0,
    client: httpx.Client | None = None,
    max_workers: int = 10,
) -> CrossStoreSummary:
    """Poll all known stores in parallel using ThreadPoolExecutor.

    Parallel polling prevents cumulative timeout latency when one or more
    stores are offline, while preserving deterministic output order.
    """
    now = datetime.now(UTC)
    if not registry:
        return CrossStoreSummary(
            generated_at=now,
            stores=[],
            total_reachable=0,
            total_unreachable=0,
        )

    workers = min(max_workers, len(registry))
    should_close = False
    http_client = client
    if http_client is None:
        http_client = httpx.Client(timeout=timeout_sec)
        should_close = True

    results_by_id: dict[str, StoreStatus] = {}
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_cfg = {
                executor.submit(poll_store, cfg, timeout_sec, http_client): cfg
                for cfg in registry
            }
            for future in as_completed(future_to_cfg):
                cfg = future_to_cfg[future]
                try:
                    status = future.result()
                except Exception as exc:
                    status = StoreStatus(
                        store_id=cfg.store_id,
                        reachable=False,
                        footfall_summary=None,
                        open_alert_count=None,
                        queue_events=None,
                        stock_events=None,
                        error=f"Unexpected executor error: {exc}",
                    )
                results_by_id[status.store_id] = status
    finally:
        if should_close:
            http_client.close()

    ordered_statuses = [results_by_id[cfg.store_id] for cfg in registry]
    total_reachable = sum(1 for s in ordered_statuses if s.reachable)
    total_unreachable = len(ordered_statuses) - total_reachable

    return CrossStoreSummary(
        generated_at=now,
        stores=ordered_statuses,
        total_reachable=total_reachable,
        total_unreachable=total_unreachable,
    )
