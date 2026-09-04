from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from schemas import DetectionEvent
from storage.repository import EventRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_retail.db"
    return EventRepository(db_path)


@pytest.fixture
def client(test_repo: EventRepository) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# Heatmap API Tests
# ============================================================================


def test_heatmap_empty_data(client: TestClient) -> None:
    resp = client.get("/heatmap?width=640&height=480&cell_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == 24  # 480 // 20
    assert data["cols"] == 32  # 640 // 20
    assert data["cell_size"] == 20
    assert data["width"] == 640
    assert data["height"] == 480
    assert data["total_points"] == 0
    assert len(data["grid"]) == 24
    assert len(data["grid"][0]) == 32
    # All zeros
    assert all(val == 0.0 for row in data["grid"] for val in row)


def test_heatmap_dynamic_dimensions_from_config(client: TestClient) -> None:
    """When width and height are omitted, dimensions are derived from config.yaml
    or minimum default.
    """
    resp = client.get("/heatmap?cell_size=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["width"] >= 640
    assert data["height"] >= 480
    assert data["rows"] == data["height"] // 50
    assert data["cols"] == data["width"] // 50
    assert len(data["grid"]) == data["rows"]
    assert len(data["grid"][0]) == data["cols"]


def test_heatmap_with_detections(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)

    # Detection 1: bbox at x=100, y=100, w=40, h=60
    # Bottom-center anchor: anchor_x = 100 + 20 = 120, anchor_y = 100 + 60 = 160
    # With cell_size=20: col = 120 // 20 = 6, row = 160 // 20 = 8
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="det_1",
            track_id="tr_1",
            timestamp=now,
            bbox=(100, 100, 40, 60),
            zone_id="zone_a",
            event_type="in_zone",
        )
    )

    resp = client.get("/heatmap?width=640&height=480&cell_size=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 1
    assert data["grid"][8][6] == 1.0


def test_heatmap_zone_filter(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)

    test_repo.save_detection_event(
        DetectionEvent(
            event_id="det_1",
            track_id="tr_1",
            timestamp=now,
            bbox=(100, 100, 40, 60),
            zone_id="zone_a",
            event_type="in_zone",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="det_2",
            track_id="tr_2",
            timestamp=now,
            bbox=(200, 200, 40, 60),
            zone_id="zone_b",
            event_type="in_zone",
        )
    )

    resp_a = client.get("/heatmap?zone_id=zone_a&width=640&height=480")
    assert resp_a.status_code == 200
    assert resp_a.json()["total_points"] == 1
    assert resp_a.json()["zone_id"] == "zone_a"

    resp_c = client.get("/heatmap?zone_id=zone_nonexistent&width=640&height=480")
    assert resp_c.status_code == 200
    assert resp_c.json()["total_points"] == 0


def test_heatmap_since_filter(client: TestClient, test_repo: EventRepository) -> None:
    t1 = datetime(2026, 8, 30, 8, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)

    test_repo.save_detection_event(
        DetectionEvent(
            event_id="det_1",
            track_id="tr_1",
            timestamp=t1,
            bbox=(100, 100, 40, 60),
            zone_id="zone_a",
            event_type="in_zone",
        )
    )
    test_repo.save_detection_event(
        DetectionEvent(
            event_id="det_2",
            track_id="tr_2",
            timestamp=t2,
            bbox=(100, 100, 40, 60),
            zone_id="zone_a",
            event_type="in_zone",
        )
    )

    cutoff = "2026-08-30T10:00:00Z"
    resp = client.get(f"/heatmap?since={cutoff}&width=640&height=480")
    assert resp.status_code == 200
    assert resp.json()["total_points"] == 1


def test_heatmap_dimensions_consistency(client: TestClient) -> None:
    resp = client.get("/heatmap?width=800&height=600&cell_size=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == 12  # 600 // 50
    assert data["cols"] == 16  # 800 // 50
    assert len(data["grid"]) == 12
    for r in data["grid"]:
        assert len(r) == 16


def test_heatmap_malformed_query_params(client: TestClient) -> None:
    # cell_size must be >= 1
    resp_bad_cell = client.get("/heatmap?cell_size=0")
    assert resp_bad_cell.status_code == 422

    # since must be valid iso date
    resp_bad_date = client.get("/heatmap?since=not-a-date")
    assert resp_bad_date.status_code == 422
