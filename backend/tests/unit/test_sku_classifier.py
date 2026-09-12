import time
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from analytics.sku_classifier import MIN_CADENCE_SECONDS, SKUSegregator
from api.dependencies import get_repository
from api.main import app
from core.schemas import ZoneConfig
from storage.repository import EventRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_retail_sku.db"
    return EventRepository(db_path)


@pytest.fixture
def client(test_repo: EventRepository) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_shelf_zones() -> list[ZoneConfig]:
    return [
        ZoneConfig(
            zone_id="zone_shelf_beverages",
            zone_type="shelf",
            polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
            label="Cold Soda Shelf",
        ),
        ZoneConfig(
            zone_id="zone_shelf_snacks",
            zone_type="shelf",
            polygon=[(100, 0), (200, 0), (200, 100), (100, 100)],
            label="Chips and Snacks",
        ),
    ]


# ============================================================================
# SKU Classifier Unit Tests
# ============================================================================


def test_sku_segregator_init_and_catalog() -> None:
    seg = SKUSegregator(interval_seconds=10.0)
    assert seg.interval_seconds == MIN_CADENCE_SECONDS
    catalog = seg.get_catalog()
    assert len(catalog) >= 3

    cola = seg.get_sku("sku_bev_cola_330")
    assert cola is not None
    assert cola.brand == "EdgeCola"
    assert cola.expected_zone_id == "zone_shelf_beverages"


def test_sku_register_custom_product() -> None:
    seg = SKUSegregator(interval_seconds=10.0)
    ref_crop = np.full((60, 60, 3), (0, 140, 255), dtype=np.uint8)
    seg.register_sku(
        sku_id="sku_juice_orange",
        name="Orange Juice 1L",
        brand="TropicFresh",
        expected_zone_id="zone_shelf_beverages",
        category="beverages",
        reference_crop=ref_crop,
    )

    sku = seg.get_sku("sku_juice_orange")
    assert sku is not None
    assert sku.name == "Orange Juice 1L"
    assert sku.brand == "TropicFresh"


def test_cadence_lock_enforcement(sample_shelf_zones: list[ZoneConfig]) -> None:
    seg = SKUSegregator(interval_seconds=10.0)
    canvas = np.full((200, 200, 3), 128, dtype=np.uint8)

    report1 = seg.evaluate_all_shelves([("cam1", canvas)], sample_shelf_zones)
    assert report1.total_shelves_monitored == 2
    t1 = report1.last_evaluated_at

    report2 = seg.evaluate_all_shelves([("cam1", canvas)], sample_shelf_zones)
    assert report2.last_evaluated_at == t1
    assert report2 is report1

    time.sleep(0.01)
    report3 = seg.evaluate_all_shelves([("cam1", canvas)], sample_shelf_zones, force=True)
    assert report3 is not report1


def test_empty_shelf_detection() -> None:
    seg = SKUSegregator()
    empty_crop = np.full((50, 80, 3), 40, dtype=np.uint8)
    item = seg.evaluate_shelf(empty_crop, shelf_id="zone_shelf_beverages", camera_id="cam_main")

    assert item.status == "empty"
    assert item.facing_count == 0
    assert item.fill_percentage == 0.0
    assert not item.planogram_compliant


def test_facing_count_estimation() -> None:
    seg = SKUSegregator()
    h, w = 60, 160
    shelf = np.full((h, w, 3), 180, dtype=np.uint8)
    for col in [30, 65, 100, 135]:
        shelf[:, col - 2 : col + 2] = [20, 20, 20]

    facings = seg.detect_facings(shelf)
    assert facings >= 3


def test_planogram_misplacement_detection() -> None:
    seg = SKUSegregator()
    red_crop = np.zeros((60, 80, 3), dtype=np.uint8)
    red_crop[:, :] = (20, 25, 200)
    for x in range(10, 70, 15):
        red_crop[:, x : x + 2] = (255, 255, 255)

    item = seg.evaluate_shelf(red_crop, shelf_id="zone_shelf_snacks", camera_id="cam_main")
    assert item.detected_sku_id == "sku_bev_cola_330"
    assert item.status == "misplaced"
    assert not item.planogram_compliant


def test_compliant_shelf() -> None:
    seg = SKUSegregator()
    yellow_crop = np.zeros((60, 80, 3), dtype=np.uint8)
    yellow_crop[:, :] = (30, 200, 220)
    for x in range(10, 70, 15):
        yellow_crop[:, x : x + 2] = (10, 10, 10)

    item = seg.evaluate_shelf(yellow_crop, shelf_id="zone_shelf_snacks", camera_id="cam_main")
    assert item.detected_sku_id == "sku_snack_chips_gold"
    assert item.planogram_compliant


# ============================================================================
# API Routes Tests (/kpi/sku)
# ============================================================================


def test_api_get_sku_report(client: TestClient) -> None:
    response = client.get("/kpi/sku")
    assert response.status_code == 200
    data = response.json()
    assert "interval_seconds" in data
    assert data["interval_seconds"] >= 10.0
    assert "total_shelves_monitored" in data
    assert "compliant_shelves" in data
    assert "misplaced_shelves" in data
    assert "items" in data


def test_api_get_sku_catalog(client: TestClient) -> None:
    response = client.get("/kpi/sku/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert isinstance(catalog, list)
    assert len(catalog) >= 3
    ids = [item["sku_id"] for item in catalog]
    assert "sku_bev_cola_330" in ids


def test_api_register_sku(client: TestClient) -> None:
    payload = {
        "sku_id": "sku_dairy_milk_1l",
        "name": "Farm Fresh Whole Milk 1L",
        "brand": "DairyPure",
        "expected_zone_id": "zone_shelf_dairy",
        "category": "dairy",
    }
    response = client.post("/kpi/sku/catalog", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "sku_dairy_milk_1l"
    assert data["brand"] == "DairyPure"

    get_resp = client.get("/kpi/sku/catalog")
    assert any(x["sku_id"] == "sku_dairy_milk_1l" for x in get_resp.json())
