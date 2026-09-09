from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from core.schemas import Alert
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
# Alerts API Tests
# ============================================================================


def test_alerts_empty_data(client: TestClient) -> None:
    resp = client.get("/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_alerts_open_and_resolved_filtering(
    client: TestClient, test_repo: EventRepository
) -> None:
    now = datetime.now(UTC)

    # 1 open alert
    test_repo.save_alert(
        Alert(
            alert_id="alt_open",
            alert_type="low_stock",
            severity="critical",
            zone_id="shelf_1",
            message="Shelf 1 is out of stock",
            created_at=now - timedelta(minutes=10),
            resolved_at=None,
        )
    )

    # 1 resolved alert
    test_repo.save_alert(
        Alert(
            alert_id="alt_resolved",
            alert_type="queue_congestion",
            severity="warning",
            zone_id="checkout_1",
            message="Queue exceeded threshold",
            created_at=now - timedelta(minutes=30),
            resolved_at=now - timedelta(minutes=5),
        )
    )

    # Default is status=open
    resp_default = client.get("/alerts")
    assert resp_default.status_code == 200
    data_open = resp_default.json()
    assert len(data_open) == 1
    assert data_open[0]["alert_id"] == "alt_open"
    assert data_open[0]["resolved_at"] is None

    # status=open explicitly
    resp_open = client.get("/alerts?status=open")
    assert resp_open.status_code == 200
    assert len(resp_open.json()) == 1
    assert resp_open.json()[0]["alert_id"] == "alt_open"

    # status=resolved explicitly
    resp_resolved = client.get("/alerts?status=resolved")
    assert resp_resolved.status_code == 200
    data_resolved = resp_resolved.json()
    assert len(data_resolved) == 1
    assert data_resolved[0]["alert_id"] == "alt_resolved"
    assert data_resolved[0]["resolved_at"] is not None

    # status=all includes both
    resp_all = client.get("/alerts?status=all")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert len(data_all) == 2
    alert_ids = {a["alert_id"] for a in data_all}
    assert alert_ids == {"alt_open", "alt_resolved"}


def test_alerts_resolved_sql_limit_filtering(
    client: TestClient, test_repo: EventRepository
) -> None:
    """Ensure limit is applied directly to resolved alerts in SQL query."""
    now = datetime.now(UTC)

    # Save 5 older resolved alerts
    for i in range(5):
        test_repo.save_alert(
            Alert(
                alert_id=f"resolved_{i}",
                alert_type="low_stock",
                severity="warning",
                zone_id="zone_1",
                message=f"Resolved alert {i}",
                created_at=now - timedelta(hours=2, minutes=i),
                resolved_at=now - timedelta(hours=1, minutes=i),
            )
        )

    # Save 10 newer open alerts
    for i in range(10):
        test_repo.save_alert(
            Alert(
                alert_id=f"open_{i}",
                alert_type="queue_congestion",
                severity="critical",
                zone_id="zone_2",
                message=f"Open alert {i}",
                created_at=now - timedelta(minutes=i),
                resolved_at=None,
            )
        )

    # Query status=resolved with limit=3 (even though top 10 recent alerts are open)
    resp = client.get("/alerts?status=resolved&limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert all(a["resolved_at"] is not None for a in data)


def test_alerts_invalid_status(client: TestClient) -> None:
    resp = client.get("/alerts?status=pending")
    assert resp.status_code == 422


def test_alerts_limit(client: TestClient, test_repo: EventRepository) -> None:
    now = datetime.now(UTC)
    for i in range(10):
        test_repo.save_alert(
            Alert(
                alert_id=f"alt_{i}",
                alert_type="custom",
                severity="info",
                zone_id="zone_0",
                message=f"Alert {i}",
                created_at=now + timedelta(minutes=i),
                resolved_at=None,
            )
        )

    resp = client.get("/alerts?limit=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3
