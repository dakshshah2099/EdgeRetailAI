from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from api.dependencies import get_repository
from api.main import app
from core.schemas import DetectionEvent, QueueEvent, StockEvent
from fastapi.testclient import TestClient
from storage.repository import EventRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_retail.db"
    return EventRepository(db_path)


@pytest.fixture
def client(test_repo: EventRepository) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Footfall KPI Tests
# ============================================================================


def test_footfall_empty_data(client: TestClient) -> None:
    response = client.get("/kpi/footfall")
    assert response.status_code == 200
    data = response.json()
    assert data["total_enters"] == 0
    assert data["total_exits"] == 0
    assert data["net_occupancy"] == 0
    assert data["buckets"] == []
    assert data["zone_id"] is None
    assert data["since"] is None


def test_footfall_with_events(client: TestClient, test_repo: EventRepository) -> None:
    base_time = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)

    # 4 enters, 1 exit in zone_a
    for i in range(4):
        test_repo.save_detection_event(
            DetectionEvent(
                event_id=f"enter_{i}",
                track_id=f"track_{i}",
                timestamp=base_time + timedelta(minutes=i * 5),
                bbox=(10, 10, 50, 100),
                zone_id="zone_a",
                event_type="enter",
            )
        )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="exit_1",
            track_id="track_0",
            timestamp=base_time + timedelta(minutes=25),
            bbox=(10, 10, 50, 100),
            zone_id="zone_a",
            event_type="exit",
        )
    )

    response = client.get("/kpi/footfall")
    assert response.status_code == 200
    data = response.json()
    assert data["total_enters"] == 4
    assert data["total_exits"] == 1
    assert data["net_occupancy"] == 3


def test_footfall_filter_zone(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e1",
            track_id="t1",
            timestamp=now,
            bbox=(0, 0, 10, 10),
            zone_id="entrance_1",
            event_type="enter",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e2",
            track_id="t2",
            timestamp=now,
            bbox=(0, 0, 10, 10),
            zone_id="entrance_2",
            event_type="enter",
        )
    )

    resp1 = client.get("/kpi/footfall?zone_id=entrance_1")
    assert resp1.status_code == 200
    assert resp1.json()["total_enters"] == 1
    assert resp1.json()["zone_id"] == "entrance_1"

    resp2 = client.get("/kpi/footfall?zone_id=nonexistent")
    assert resp2.status_code == 200
    assert resp2.json()["total_enters"] == 0


def test_footfall_filter_since(client: TestClient, test_repo: EventRepository) -> None:
    t1 = datetime(2026, 8, 30, 8, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e1",
            track_id="t1",
            timestamp=t1,
            bbox=(0, 0, 10, 10),
            zone_id="main",
            event_type="enter",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e2",
            track_id="t2",
            timestamp=t2,
            bbox=(0, 0, 10, 10),
            zone_id="main",
            event_type="enter",
        )
    )

    cutoff = "2026-08-30T10:00:00Z"
    resp = client.get(f"/kpi/footfall?since={cutoff}")
    assert resp.status_code == 200
    assert resp.json()["total_enters"] == 1


def test_footfall_group_by_hour(client: TestClient, test_repo: EventRepository) -> None:
    h10 = datetime(2026, 8, 30, 10, 15, 0, tzinfo=UTC)
    h11_1 = datetime(2026, 8, 30, 11, 5, 0, tzinfo=UTC)
    h11_2 = datetime(2026, 8, 30, 11, 45, 0, tzinfo=UTC)

    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e1",
            track_id="t1",
            timestamp=h10,
            bbox=(0, 0, 10, 10),
            zone_id="z",
            event_type="enter",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e2",
            track_id="t2",
            timestamp=h11_1,
            bbox=(0, 0, 10, 10),
            zone_id="z",
            event_type="enter",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e3",
            track_id="t3",
            timestamp=h11_2,
            bbox=(0, 0, 10, 10),
            zone_id="z",
            event_type="exit",
        )
    )

    resp = client.get("/kpi/footfall?group_by=hour")
    assert resp.status_code == 200
    buckets = resp.json()["buckets"]
    assert len(buckets) == 2

    # First bucket (10:00)
    assert buckets[0]["enters"] == 1
    assert buckets[0]["exits"] == 0
    assert buckets[0]["net"] == 1

    # Second bucket (11:00)
    assert buckets[1]["enters"] == 1
    assert buckets[1]["exits"] == 1
    assert buckets[1]["net"] == 0


def test_footfall_group_by_day(client: TestClient, test_repo: EventRepository) -> None:
    d1 = datetime(2026, 8, 29, 14, 0, 0, tzinfo=UTC)
    d2 = datetime(2026, 8, 30, 9, 0, 0, tzinfo=UTC)

    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e1",
            track_id="t1",
            timestamp=d1,
            bbox=(0, 0, 10, 10),
            zone_id="z",
            event_type="enter",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="e2",
            track_id="t2",
            timestamp=d2,
            bbox=(0, 0, 10, 10),
            zone_id="z",
            event_type="enter",
        )
    )

    resp = client.get("/kpi/footfall?group_by=day")
    assert resp.status_code == 200
    buckets = resp.json()["buckets"]
    assert len(buckets) == 2
    assert buckets[0]["enters"] == 1
    assert buckets[1]["enters"] == 1


def test_footfall_malformed_since(client: TestClient) -> None:
    resp = client.get("/kpi/footfall?since=invalid-date-format")
    assert resp.status_code == 422


def test_footfall_malformed_group_by(client: TestClient) -> None:
    resp = client.get("/kpi/footfall?group_by=invalid_group")
    assert resp.status_code == 422


# ============================================================================
# Queue KPI Tests
# ============================================================================


def test_queue_empty_data(client: TestClient) -> None:
    response = client.get("/kpi/queue")
    assert response.status_code == 200
    assert response.json() == []


def test_queue_latest_per_counter(client: TestClient, test_repo: EventRepository) -> None:
    t1 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 30, 10, 5, 0, tzinfo=UTC)

    # Counter 1: two readings, t2 is latest
    test_repo.save_queue_event(
        QueueEvent(
            event_id="q1",
            counter_id="counter_1",
            timestamp=t1,
            queue_length=2,
            avg_wait_est_sec=60.0,
        )
    )
    test_repo.save_queue_event(
        QueueEvent(
            event_id="q2",
            counter_id="counter_1",
            timestamp=t2,
            queue_length=5,
            avg_wait_est_sec=150.0,
        )
    )

    # Counter 2: one reading
    test_repo.save_queue_event(
        QueueEvent(
            event_id="q3",
            counter_id="counter_2",
            timestamp=t1,
            queue_length=1,
            avg_wait_est_sec=30.0,
        )
    )

    resp = client.get("/kpi/queue")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    # Map by counter_id
    by_counter = {item["counter_id"]: item for item in data}
    assert by_counter["counter_1"]["queue_length"] == 5
    assert by_counter["counter_1"]["avg_wait_est_sec"] == 150.0
    assert by_counter["counter_2"]["queue_length"] == 1


def test_queue_filter_counter_id(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    test_repo.save_queue_event(
        QueueEvent(
            event_id="q1",
            counter_id="counter_1",
            timestamp=now,
            queue_length=3,
            avg_wait_est_sec=90.0,
        )
    )
    test_repo.save_queue_event(
        QueueEvent(
            event_id="q2",
            counter_id="counter_2",
            timestamp=now,
            queue_length=7,
            avg_wait_est_sec=210.0,
        )
    )

    resp = client.get("/kpi/queue?counter_id=counter_1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["counter_id"] == "counter_1"
    assert data[0]["queue_length"] == 3

    resp_empty = client.get("/kpi/queue?counter_id=counter_999")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []


# ============================================================================
# Stock KPI Tests
# ============================================================================


def test_stock_empty_data(client: TestClient) -> None:
    response = client.get("/kpi/stock")
    assert response.status_code == 200
    assert response.json() == []


def test_stock_latest_per_shelf(client: TestClient, test_repo: EventRepository) -> None:
    t1 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 30, 10, 10, 0, tzinfo=UTC)

    # Shelf A: first ok, then low
    test_repo.save_stock_event(
        StockEvent(
            event_id="s1",
            shelf_id="shelf_a",
            timestamp=t1,
            status="ok",
            confidence=0.95,
        )
    )
    test_repo.save_stock_event(
        StockEvent(
            event_id="s2",
            shelf_id="shelf_a",
            timestamp=t2,
            status="low",
            confidence=0.88,
        )
    )

    # Shelf B: ok
    test_repo.save_stock_event(
        StockEvent(
            event_id="s3",
            shelf_id="shelf_b",
            timestamp=t1,
            status="ok",
            confidence=0.99,
        )
    )

    resp = client.get("/kpi/stock")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_shelf = {item["shelf_id"]: item for item in data}
    assert by_shelf["shelf_a"]["status"] == "low"
    assert by_shelf["shelf_a"]["confidence"] == 0.88
    assert by_shelf["shelf_b"]["status"] == "ok"


def test_stock_filter_shelf_id(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    test_repo.save_stock_event(
        StockEvent(
            event_id="s1",
            shelf_id="shelf_1",
            timestamp=now,
            status="empty",
            confidence=0.91,
        )
    )
    test_repo.save_stock_event(
        StockEvent(
            event_id="s2",
            shelf_id="shelf_2",
            timestamp=now,
            status="ok",
            confidence=0.85,
        )
    )

    resp = client.get("/kpi/stock?shelf_id=shelf_1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["shelf_id"] == "shelf_1"
    assert data[0]["status"] == "empty"

    resp_empty = client.get("/kpi/stock?shelf_id=shelf_unknown")
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []
