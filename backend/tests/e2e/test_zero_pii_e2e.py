import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from core.schemas import Alert, DetectionEvent, DwellEvent, QueueEvent, StockEvent
from storage.db import get_connection
from storage.repository import EventRepository

FORBIDDEN_PII_TERMS = {
    "image",
    "frame",
    "face",
    "crop",
    "embedding",
    "biometric",
    "facial",
    "identity",
    "ssn",
    "aadhaar",
    "email",
    "phone",
    "person_name",
}

BASE64_IMAGE_REGEX = re.compile(
    r"(data:image\/(jpeg|png|webp);base64,|/9j/4AAQSkZJRg|iVBORw0KGgo)",
    re.IGNORECASE,
)


def _check_no_pii_recursive(data: Any, path: str = "") -> None:
    """Recursively assert that a JSON/dict structure contains no PII or raw image payloads."""
    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = str(key).lower()
            for term in FORBIDDEN_PII_TERMS:
                assert term not in key_lower, (
                    f"Forbidden PII term '{term}' discovered in API response key '{path}.{key}'"
                )
            _check_no_pii_recursive(value, f"{path}.{key}")
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            _check_no_pii_recursive(item, f"{path}[{idx}]")
    elif isinstance(data, str):
        # Assert no base64 image strings or face embedding vectors
        assert not BASE64_IMAGE_REGEX.search(data), (
            f"Base64 image payload detected in response value at '{path}'"
        )
        assert len(data) < 50_000, f"Suspiciously large serialized string at '{path}'"
    elif isinstance(data, (bytes, bytearray)):
        raise AssertionError(f"Raw binary bytes payload exposed at '{path}'")


@pytest.mark.e2e
def test_sqlite_database_has_zero_pii(e2e_db_path: Path, e2e_repo: EventRepository) -> None:
    """E2E audit of SQLite storage: verify table schemas and stored rows

    physically contain NO images, face crops, biometric embeddings, or PII.
    """
    now = datetime.now(UTC)

    # Ingest a set of populated retail events
    e2e_repo.save_detection_event(
        DetectionEvent(
            event_id="det_pii_1",
            track_id="trk_anon_99",
            timestamp=now,
            bbox=(10, 20, 50, 100),
            zone_id="zone_entrance",
            event_type="enter",
        )
    )
    e2e_repo.save_dwell_event(
        DwellEvent(
            event_id="dwell_pii_1",
            zone_id="zone_display",
            track_id="trk_anon_99",
            start_ts=now,
            end_ts=now,
            duration_sec=25.0,
        )
    )
    e2e_repo.save_queue_event(
        QueueEvent(
            event_id="q_pii_1",
            counter_id="counter_1",
            timestamp=now,
            queue_length=3,
        )
    )
    e2e_repo.save_stock_event(
        StockEvent(
            event_id="stock_pii_1",
            shelf_id="shelf_1",
            timestamp=now,
            status="ok",
            confidence=0.95,
        )
    )
    e2e_repo.save_alert(
        Alert(
            alert_id="alert_pii_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="Replenishment required",
            created_at=now,
            resolved_at=None,
        )
    )

    conn = get_connection(e2e_db_path)
    try:
        cursor = conn.cursor()

        # 1. Inspect Table Definitions (DDL)
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        assert len(tables) > 0

        for table in tables:
            table_name = table["name"]
            table_sql = table["sql"].lower()

            # Verify no table name or SQL definition includes PII columns or BLOBs
            assert "blob" not in table_sql, f"Table {table_name} declares a BLOB column"
            for term in FORBIDDEN_PII_TERMS:
                assert term not in table_sql, (
                    f"Table {table_name} DDL contains forbidden term '{term}'"
                )

        # 2. Inspect All Stored Rows
        table_names = [t["name"] for t in tables if not t["name"].startswith("sqlite_")]
        for table_name in table_names:
            cursor.execute(f"SELECT * FROM {table_name};")  # noqa: S608
            rows = cursor.fetchall()
            for row in rows:
                for val in row:
                    # No binary blobs
                    assert not isinstance(val, (bytes, bytearray)), (
                        f"Binary BLOB data found in table {table_name}"
                    )
                    if isinstance(val, str):
                        # No base64 image strings
                        assert not BASE64_IMAGE_REGEX.search(val), (
                            f"Base64 image string detected in table {table_name}"
                        )
    finally:
        conn.close()


@pytest.mark.e2e
def test_api_responses_contain_zero_pii(
    e2e_repo: EventRepository,
    e2e_client: TestClient,
) -> None:
    """E2E audit of API responses: verify JSON outputs from /kpi/*, /alerts, /heatmap

    contain only anonymous derived analytics and zero PII or image data.
    """
    now = datetime.now(UTC)

    # Populate representative retail events
    e2e_repo.save_detection_event(
        DetectionEvent(
            event_id="det_1",
            track_id="trk_123",
            timestamp=now,
            bbox=(50, 50, 40, 80),
            zone_id="zone_entrance",
            event_type="enter",
        )
    )
    e2e_repo.save_queue_event(
        QueueEvent(
            event_id="q_1",
            counter_id="counter_1",
            timestamp=now,
            queue_length=2,
            avg_wait_est_sec=60.0,
        )
    )
    e2e_repo.save_stock_event(
        StockEvent(
            event_id="s_1",
            shelf_id="shelf_1",
            timestamp=now,
            status="low",
            confidence=0.88,
        )
    )
    e2e_repo.save_alert(
        Alert(
            alert_id="a_1",
            alert_type="low_stock",
            severity="warning",
            zone_id="shelf_1",
            message="Shelf low",
            created_at=now,
            resolved_at=None,
        )
    )

    endpoints = [
        "/kpi/footfall",
        "/kpi/queue",
        "/kpi/stock",
        "/alerts?status=all",
        "/alerts?status=open",
        "/alerts?status=resolved",
        "/heatmap",
        "/system/zones",
    ]

    for endpoint in endpoints:
        resp = e2e_client.get(endpoint)
        assert resp.status_code == 200, f"Endpoint {endpoint} failed"
        payload = resp.json()
        _check_no_pii_recursive(payload, path=endpoint)


@pytest.mark.e2e
def test_pydantic_contracts_forbid_raw_frames() -> None:
    """Verify structural schema constraint: persisted Pydantic models physically

    cannot accept or serialize raw frame pixels.
    """
    models: tuple[type[BaseModel], ...] = (
        DetectionEvent,
        DwellEvent,
        QueueEvent,
        StockEvent,
        Alert,
    )
    for model_cls in models:
        for field_name, field_info in model_cls.model_fields.items():
            assert field_name not in FORBIDDEN_PII_TERMS, (
                f"Model {model_cls.__name__} has forbidden field '{field_name}'"
            )
            type_str = str(field_info.annotation).lower()
            assert "bytes" not in type_str, (
                f"Model {model_cls.__name__}.{field_name} declares bytes type"
            )
            assert "ndarray" not in type_str, (
                f"Model {model_cls.__name__}.{field_name} declares ndarray type"
            )
