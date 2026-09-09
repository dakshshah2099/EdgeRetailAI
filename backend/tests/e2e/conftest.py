from collections.abc import Generator
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_app_config, get_config_path, get_db_path, get_repository
from api.main import create_app
from core.schemas import load_config
from storage.db import init_db
from storage.repository import EventRepository


@pytest.fixture
def e2e_db_path(tmp_path: Path) -> Path:
    """Provide a clean, isolated SQLite database for E2E tests."""
    db_file = tmp_path / "e2e_retail.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def e2e_repo(e2e_db_path: Path) -> EventRepository:
    """Provide an EventRepository connected to the isolated E2E database."""
    return EventRepository(e2e_db_path)


@pytest.fixture
def e2e_config_file(tmp_path: Path) -> Path:
    """Create a temporary config.yaml file containing retail zones."""
    cfg_file = tmp_path / "config.yaml"
    config_data = {
        "camera": {
            "source": "0",
        },
        "zones": [
            {
                "zone_id": "zone_entrance",
                "zone_type": "entry_exit",
                "polygon": [[50, 50], [250, 50], [250, 250], [50, 250]],
                "label": "Store Main Entrance",
            },
            {
                "zone_id": "zone_display",
                "zone_type": "product_display",
                "polygon": [[300, 50], [550, 50], [550, 250], [300, 250]],
                "label": "Featured Promotional Display",
            },
            {
                "zone_id": "zone_checkout_1",
                "zone_type": "checkout",
                "polygon": [[50, 280], [250, 280], [250, 460], [50, 460]],
                "label": "Checkout Counter 1",
            },
            {
                "zone_id": "zone_shelf_beverages",
                "zone_type": "shelf",
                "polygon": [[300, 280], [550, 280], [550, 460], [300, 460]],
                "label": "Beverage Shelf Unit",
            },
        ],
        "low_stock_confidence_threshold": 0.6,
        "queue_congestion_length": 4,
    }
    with cfg_file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)
    return cfg_file


@pytest.fixture
def e2e_app(
    e2e_repo: EventRepository, e2e_config_file: Path, e2e_db_path: Path
) -> Generator[FastAPI, None, None]:
    """Create a FastAPI application instance with isolated E2E dependencies."""
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: e2e_repo
    app.dependency_overrides[get_app_config] = lambda: load_config(e2e_config_file)
    app.dependency_overrides[get_config_path] = lambda: e2e_config_file
    app.dependency_overrides[get_db_path] = lambda: e2e_db_path
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def e2e_client(e2e_app: FastAPI) -> Generator[TestClient, None, None]:
    """Provide a TestClient bound to the isolated E2E FastAPI application."""
    with TestClient(e2e_app) as client:
        yield client
