from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from core.schemas import QueueEvent
from storage.repository import EventRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> EventRepository:
    db_path = tmp_path / "test_reports_api.db"
    return EventRepository(db_path)


@pytest.fixture
def client(test_repo: EventRepository) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_repository] = lambda: test_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_daily_report_empty_returns_404(client: TestClient) -> None:
    """GET /reports/daily must return HTTP 404 when window contains zero events."""
    response = client.get("/reports/daily?date=2026-09-12&format=csv")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_weekly_report_empty_returns_404(client: TestClient) -> None:
    """GET /reports/weekly must return HTTP 404 when window contains zero events."""
    response = client.get("/reports/weekly?week_start=2026-09-07&format=csv")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_daily_report_csv_success(client: TestClient, test_repo: EventRepository) -> None:
    """GET /reports/daily with format=csv returns 200, text/csv, and attachment header."""
    t0 = datetime(2026, 9, 12, 11, 0, 0, tzinfo=UTC)
    test_repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=3)
    )

    response = client.get("/reports/daily?date=2026-09-12&format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    disp = response.headers["content-disposition"]
    assert 'attachment; filename="daily_report_2026-09-12.csv"' in disp
    assert len(response.text) > 0


def test_daily_report_pdf_success(client: TestClient, test_repo: EventRepository) -> None:
    """GET /reports/daily with format=pdf returns 200, application/pdf, and valid PDF bytes."""
    t0 = datetime(2026, 9, 12, 11, 0, 0, tzinfo=UTC)
    test_repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=3)
    )

    response = client.get("/reports/daily?date=2026-09-12&format=pdf")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    disp = response.headers["content-disposition"]
    assert 'attachment; filename="daily_report_2026-09-12.pdf"' in disp
    assert response.content.startswith(b"%PDF-")


def test_weekly_report_csv_success(client: TestClient, test_repo: EventRepository) -> None:
    """GET /reports/weekly with format=csv returns 200 and attachment header."""
    t0 = datetime(2026, 9, 8, 11, 0, 0, tzinfo=UTC)
    test_repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=2)
    )

    response = client.get("/reports/weekly?week_start=2026-09-07&format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    disp = response.headers["content-disposition"]
    assert 'attachment; filename="weekly_report_2026-09-07.csv"' in disp


def test_weekly_report_pdf_success(client: TestClient, test_repo: EventRepository) -> None:
    """GET /reports/weekly with format=pdf returns 200 and PDF bytes."""
    t0 = datetime(2026, 9, 8, 11, 0, 0, tzinfo=UTC)
    test_repo.save_queue_event(
        QueueEvent(event_id="q1", counter_id="c1", timestamp=t0, queue_length=2)
    )

    response = client.get("/reports/weekly?week_start=2026-09-07&format=pdf")
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    disp = response.headers["content-disposition"]
    assert 'attachment; filename="weekly_report_2026-09-07.pdf"' in disp
    assert response.content.startswith(b"%PDF-")


def test_invalid_date_format_returns_422(client: TestClient) -> None:
    """Malformed date query parameter should return HTTP 422."""
    response = client.get("/reports/daily?date=invalid-date&format=csv")
    assert response.status_code == 422


def test_unsupported_format_returns_422(client: TestClient) -> None:
    """Unsupported format (e.g. json or xml) should return HTTP 422."""
    response = client.get("/reports/daily?date=2026-09-12&format=json")
    assert response.status_code == 422

