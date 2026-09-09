from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import create_app
from central.aggregator import CrossStoreSummary, aggregate_stores
from central.central_dashboard import create_central_app
from central.store_registry import StoreConfig
from core.schemas import Alert, DetectionEvent, QueueEvent, StockEvent
from storage.db import init_db
from storage.repository import EventRepository
from storage.sync_buffer import AnyEvent, SyncBuffer


@pytest.mark.e2e
def test_edge_offline_buffering_and_recovery() -> None:
    """E2E test: Edge offline buffer retains events during network outage

    and cleanly flushes events in FIFO order once connection is restored.
    """
    now = datetime.now(UTC)
    buffer = SyncBuffer(max_buffer_size=10, overflow_strategy="drop_oldest")

    events = [
        DetectionEvent(
            event_id=f"det_{i}",
            track_id=f"trk_{i}",
            timestamp=now,
            bbox=(10, 10, 40, 80),
            zone_id="zone_a",
            event_type="enter",
        )
        for i in range(5)
    ]

    for ev in events:
        buffer.enqueue(ev)

    # 1. Simulating cloud endpoint outage: sink returns False
    outage_sink_called = False

    def failing_sink(batch: list[AnyEvent]) -> bool:
        nonlocal outage_sink_called
        outage_sink_called = True
        return False

    flushed_during_outage = buffer.flush(failing_sink)
    assert outage_sink_called is True
    assert flushed_during_outage == 0
    # All 5 events are retained
    assert len(buffer._buffer) == 5

    # 2. Network connectivity restored: sink returns True
    received_batches: list[list[AnyEvent]] = []

    def successful_sink(batch: list[AnyEvent]) -> bool:
        received_batches.append(list(batch))
        return True

    flushed_after_recovery = buffer.flush(successful_sink)
    assert flushed_after_recovery == 5
    assert len(buffer._buffer) == 0
    assert len(received_batches[0]) == 5


@pytest.mark.e2e
def test_central_multi_store_aggregation_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E test: Central headquarters aggregates multiple distributed edge stores

    in parallel, correctly tabulates enterprise footfall/alerts, and tolerates
    offline stores without blocking or crashing.
    """
    now = datetime.now(UTC)

    # -------------------------------------------------------------------------
    # Setup Store 1: Downtown Flagship
    # -------------------------------------------------------------------------
    db_store1 = tmp_path / "store1.db"
    init_db(db_store1)
    repo1 = EventRepository(db_store1)
    for i in range(5):
        repo1.save_detection_event(
            DetectionEvent(
                event_id=f"s1_det_{i}",
                track_id=f"s1_trk_{i}",
                timestamp=now,
                bbox=(10, 10, 30, 60),
                zone_id="zone_entrance",
                event_type="enter",
            )
        )
    repo1.save_alert(
        Alert(
            alert_id="s1_alert_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="Downtown shelf low",
            created_at=now,
            resolved_at=None,
        )
    )
    repo1.save_queue_event(
        QueueEvent(
            event_id="s1_q_1",
            counter_id="counter_1",
            timestamp=now,
            queue_length=2,
        )
    )

    # -------------------------------------------------------------------------
    # Setup Store 2: Suburban Mall
    # -------------------------------------------------------------------------
    db_store2 = tmp_path / "store2.db"
    init_db(db_store2)
    repo2 = EventRepository(db_store2)
    for i in range(12):
        repo2.save_detection_event(
            DetectionEvent(
                event_id=f"s2_det_{i}",
                track_id=f"s2_trk_{i}",
                timestamp=now,
                bbox=(10, 10, 30, 60),
                zone_id="zone_entrance",
                event_type="enter",
            )
        )
    repo2.save_stock_event(
        StockEvent(
            event_id="s2_stock_1",
            shelf_id="shelf_suburban",
            timestamp=now,
            status="ok",
            confidence=0.95,
        )
    )

    # Build FastAPI test apps for Store 1 and Store 2
    from api.dependencies import get_repository

    app_store1 = create_app()
    app_store1.dependency_overrides[get_repository] = lambda: repo1

    app_store2 = create_app()
    app_store2.dependency_overrides[get_repository] = lambda: repo2

    client_s1 = TestClient(app_store1)
    client_s2 = TestClient(app_store2)

    # -------------------------------------------------------------------------
    # Mock HTTP Handler routing requests to respective store apps
    # Store 3 simulates a disconnected / network-failed store
    # -------------------------------------------------------------------------
    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "store1.local" in url_str:
            rel_path = request.url.raw_path.decode()
            resp = client_s1.get(rel_path)
            return httpx.Response(status_code=resp.status_code, content=resp.content)
        elif "store2.local" in url_str:
            rel_path = request.url.raw_path.decode()
            resp = client_s2.get(rel_path)
            return httpx.Response(status_code=resp.status_code, content=resp.content)
        elif "store3.local" in url_str:
            # Simulate network timeout / connection refused
            raise httpx.ConnectError("Connection refused by target edge node")
        return httpx.Response(status_code=404, content=b"Not found")

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_transport_handler))

    registry = [
        StoreConfig(
            store_id="store_downtown",
            name="Downtown Flagship",
            api_base_url="http://store1.local",
        ),
        StoreConfig(
            store_id="store_suburban",
            name="Suburban Mall",
            api_base_url="http://store2.local",
        ),
        StoreConfig(
            store_id="store_airport",
            name="Terminal 2 Kiosk",
            api_base_url="http://store3.local",
        ),
    ]

    # 1. Test core cross-store aggregation logic
    summary = aggregate_stores(registry=registry, client=mock_client)
    assert summary.total_reachable == 2
    assert summary.total_unreachable == 1

    status_by_id = {s.store_id: s for s in summary.stores}

    # Store 1 validation
    assert status_by_id["store_downtown"].reachable is True
    assert status_by_id["store_downtown"].footfall_summary is not None
    assert status_by_id["store_downtown"].footfall_summary.total_enters == 5
    assert status_by_id["store_downtown"].open_alert_count == 1
    assert len(status_by_id["store_downtown"].queue_events or []) == 1

    # Store 2 validation
    assert status_by_id["store_suburban"].reachable is True
    assert status_by_id["store_suburban"].footfall_summary is not None
    assert status_by_id["store_suburban"].footfall_summary.total_enters == 12
    assert status_by_id["store_suburban"].open_alert_count == 0
    assert len(status_by_id["store_suburban"].stock_events or []) == 1

    # Store 3 validation (isolated failure)
    assert status_by_id["store_airport"].reachable is False
    assert status_by_id["store_airport"].error is not None
    assert "Connection refused" in status_by_id["store_airport"].error

    # 2. Test Central Dashboard API
    stores_yaml_file = tmp_path / "stores.yaml"
    with stores_yaml_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "stores": [
                    {
                        "store_id": s.store_id,
                        "name": s.name,
                        "api_base_url": s.api_base_url,
                    }
                    for s in registry
                ]
            },
            f,
        )

    central_app = create_central_app(config_path=stores_yaml_file)

    def mock_aggregate(
        reg: list[StoreConfig],
        timeout_sec: float = 5.0,
        client: httpx.Client | None = None,
        max_workers: int = 10,
    ) -> CrossStoreSummary:
        return aggregate_stores(
            reg, timeout_sec=timeout_sec, client=mock_client, max_workers=max_workers
        )

    monkeypatch.setattr("central.central_dashboard.aggregate_stores", mock_aggregate)

    central_client = TestClient(central_app)

    # Verify central /api/summary endpoint
    resp_sum = central_client.get("/api/summary")
    assert resp_sum.status_code == 200
    sum_data = resp_sum.json()
    assert sum_data["total_reachable"] == 2
    assert sum_data["total_unreachable"] == 1
    assert len(sum_data["stores"]) == 3

    # Verify central /api/stores endpoint
    resp_stores = central_client.get("/api/stores")
    assert resp_stores.status_code == 200
    assert len(resp_stores.json()) == 3
