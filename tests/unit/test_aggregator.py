from pathlib import Path
from typing import Any

import httpx

from central.aggregator import (
    CrossStoreSummary,
    aggregate_stores,
    poll_store,
)
from central.store_registry import StoreConfig


def _make_mock_handler(store_routes: dict[str, dict[str, tuple[int, Any]]]) -> httpx.MockTransport:
    """Create a mock transport mapping base URL prefixes and path to responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        for base_url, routes in store_routes.items():
            if url_str.startswith(base_url):
                sub_path = url_str[len(base_url) :]
                # Normalize query string
                path_key = sub_path
                if "?" in path_key:
                    path_key = path_key.split("?")[0]

                # Match by sub_path or base path
                if sub_path in routes:
                    status, body = routes[sub_path]
                    if status == 0:
                        raise httpx.ConnectError("Simulated connection dropped", request=request)
                    return httpx.Response(status, json=body)
                elif path_key in routes:
                    status, body = routes[path_key]
                    if status == 0:
                        raise httpx.ConnectError("Simulated connection dropped", request=request)
                    return httpx.Response(status, json=body)

        return httpx.Response(404, json={"detail": "Not found"})

    return httpx.MockTransport(handler)


def test_poll_store_reachable_success() -> None:
    store_cfg = StoreConfig(
        store_id="store_alpha",
        name="Store Alpha",
        api_base_url="http://alpha.internal:8000",
    )

    routes: dict[str, dict[str, tuple[int, Any]]] = {
        "http://alpha.internal:8000": {
            "/kpi/footfall": (
                200,
                {
                    "total_enters": 42,
                    "total_exits": 30,
                    "net_occupancy": 12,
                    "zone_id": None,
                    "since": None,
                    "buckets": [],
                },
            ),
            "/alerts": (
                200,
                [
                    {
                        "alert_id": "alt_1",
                        "alert_type": "low_stock",
                        "severity": "warning",
                        "zone_id": "shelf_1",
                        "message": "Low stock",
                        "created_at": "2026-09-05T12:00:00Z",
                        "resolved_at": None,
                    }
                ],
            ),
            "/kpi/queue": (
                200,
                [
                    {
                        "event_id": "q1",
                        "counter_id": "counter_1",
                        "timestamp": "2026-09-05T12:00:00Z",
                        "queue_length": 3,
                        "avg_wait_est_sec": 45.0,
                    }
                ],
            ),
            "/kpi/stock": (
                200,
                [
                    {
                        "event_id": "s1",
                        "shelf_id": "shelf_1",
                        "timestamp": "2026-09-05T12:00:00Z",
                        "status": "low",
                        "confidence": 0.85,
                    }
                ],
            ),
        }
    }

    transport = _make_mock_handler(routes)
    with httpx.Client(transport=transport) as client:
        status = poll_store(store_cfg, client=client)

    assert status.reachable is True
    assert status.store_id == "store_alpha"
    assert status.error is None
    assert status.open_alert_count == 1
    assert status.footfall_summary is not None
    assert status.footfall_summary.net_occupancy == 12
    assert status.queue_events is not None
    assert len(status.queue_events) == 1
    assert status.stock_events is not None
    assert len(status.stock_events) == 1


def test_poll_store_unreachable_returns_offline_without_raising() -> None:
    store_cfg = StoreConfig(
        store_id="store_offline",
        name="Offline Store",
        api_base_url="http://offline.internal:8000",
    )

    def error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out", request=request)

    transport = httpx.MockTransport(error_handler)
    with httpx.Client(transport=transport) as client:
        status = poll_store(store_cfg, client=client)

    assert status.reachable is False
    assert status.store_id == "store_offline"
    assert status.footfall_summary is None
    assert status.open_alert_count is None
    assert status.queue_events is None
    assert status.stock_events is None
    assert status.error is not None
    assert "timed out" in status.error.lower()


def test_poll_store_500_server_error_handled_gracefully() -> None:
    store_cfg = StoreConfig(
        store_id="store_err",
        name="Error Store",
        api_base_url="http://error.internal:8000",
    )

    def server_error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(server_error_handler)
    with httpx.Client(transport=transport) as client:
        status = poll_store(store_cfg, client=client)

    assert status.reachable is False
    assert status.error is not None
    assert "500" in status.error


def test_aggregate_stores_mix_reachable_and_unreachable() -> None:
    stores = [
        StoreConfig(
            store_id="store_ok",
            name="Online Store",
            api_base_url="http://online.internal:8000",
        ),
        StoreConfig(
            store_id="store_bad",
            name="Offline Store",
            api_base_url="http://offline.internal:8000",
        ),
    ]

    routes: dict[str, dict[str, tuple[int, Any]]] = {
        "http://online.internal:8000": {
            "/kpi/footfall": (
                200,
                {
                    "total_enters": 10,
                    "total_exits": 5,
                    "net_occupancy": 5,
                    "zone_id": None,
                    "since": None,
                    "buckets": [],
                },
            ),
            "/alerts": (200, []),
            "/kpi/queue": (200, []),
            "/kpi/stock": (200, []),
        },
        "http://offline.internal:8000": {
            "/kpi/footfall": (0, {}),  # trigger ConnectError
        },
    }

    transport = _make_mock_handler(routes)
    with httpx.Client(transport=transport) as client:
        summary: CrossStoreSummary = aggregate_stores(stores, client=client)

    assert summary.total_reachable == 1
    assert summary.total_unreachable == 1
    assert len(summary.stores) == 2

    # Verify order is preserved
    assert summary.stores[0].store_id == "store_ok"
    assert summary.stores[0].reachable is True
    assert summary.stores[0].open_alert_count == 0

    assert summary.stores[1].store_id == "store_bad"
    assert summary.stores[1].reachable is False
    assert summary.stores[1].error is not None
    assert "connection" in summary.stores[1].error.lower()


def test_aggregate_stores_empty_registry() -> None:
    summary = aggregate_stores([])
    assert summary.total_reachable == 0
    assert summary.total_unreachable == 0
    assert summary.stores == []


def test_central_dashboard_app(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from central.central_dashboard import create_central_app

    cfg_file = tmp_path / "stores.yaml"
    cfg_file.write_text(
        """
stores:
  - store_id: "store_mock"
    name: "Mock Store"
    api_base_url: "http://mock.internal:8000"
""",
        encoding="utf-8",
    )

    app = create_central_app(config_path=cfg_file)
    client = TestClient(app)

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    r_stores = client.get("/api/stores")
    assert r_stores.status_code == 200
    assert len(r_stores.json()) == 1
    assert r_stores.json()[0]["store_id"] == "store_mock"

    r_ui = client.get("/")
    assert r_ui.status_code == 200
    assert "Central Store Operations Monitor" in r_ui.text
