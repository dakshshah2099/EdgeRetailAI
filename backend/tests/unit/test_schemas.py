from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

import core.schemas as schemas
from core.schemas import (
    Alert,
    AppConfig,
    CameraConfig,
    DetectionEvent,
    DwellEvent,
    Frame,
    QueueEvent,
    StockEvent,
    ZoneConfig,
)


def test_frame_roundtrip() -> None:
    now = datetime.now(UTC)
    frame = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)
    data = frame.model_dump()
    assert data == {
        "source_id": "cam_01",
        "timestamp": now,
        "width": 1920,
        "height": 1080,
    }
    reconstructed = Frame(**data)
    assert reconstructed == frame


def test_frame_invalid() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        Frame(source_id="cam_01", timestamp=now, width=0, height=1080)
    with pytest.raises(ValidationError):
        Frame(source_id="cam_01", timestamp=now, width=1920, height=-5)


def test_zone_config_roundtrip() -> None:
    zone = ZoneConfig(
        zone_id="entry_1",
        zone_type="entry_exit",
        polygon=[(0, 0), (100, 0), (100, 100)],
        label="Entrance Area",
    )
    data = zone.model_dump()
    assert data["zone_id"] == "entry_1"
    assert data["zone_type"] == "entry_exit"
    assert data["polygon"] == [(0, 0), (100, 0), (100, 100)]
    assert data["label"] == "Entrance Area"
    reconstructed = ZoneConfig(**data)
    assert reconstructed == zone


def test_zone_config_invalid() -> None:
    # Less than 3 points polygon
    with pytest.raises(ValidationError):
        ZoneConfig(
            zone_id="bad_zone",
            zone_type="entry_exit",
            polygon=[(0, 0), (100, 0)],
            label="Too Few Points",
        )
    # Invalid zone_type
    bad_data: dict[str, Any] = {
        "zone_id": "bad_zone",
        "zone_type": "invalid_type",
        "polygon": [(0, 0), (100, 0), (100, 100)],
        "label": "Invalid Type",
    }
    with pytest.raises(ValidationError):
        ZoneConfig(**bad_data)


def test_detection_event_roundtrip() -> None:
    now = datetime.now(UTC)
    event = DetectionEvent(
        event_id="evt_01",
        track_id="tr_100",
        timestamp=now,
        bbox=(10, 20, 100, 200),
        zone_id="entry_1",
        event_type="enter",
    )
    data = event.model_dump()
    assert data == {
        "event_id": "evt_01",
        "track_id": "tr_100",
        "timestamp": now,
        "bbox": (10, 20, 100, 200),
        "zone_id": "entry_1",
        "event_type": "enter",
    }
    reconstructed = DetectionEvent(**data)
    assert reconstructed == event


def test_detection_event_frozen() -> None:
    now = datetime.now(UTC)
    event = DetectionEvent(
        event_id="evt_01",
        track_id="tr_100",
        timestamp=now,
        bbox=(10, 20, 100, 200),
        zone_id="entry_1",
        event_type="enter",
    )
    with pytest.raises(ValidationError):
        event.track_id = "tr_200"


def test_detection_event_invalid() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        DetectionEvent(
            event_id="evt_01",
            track_id="tr_100",
            timestamp=now,
            bbox=(10, 20, -100, 200),
            event_type="enter",
        )
    bad_data: dict[str, Any] = {
        "event_id": "evt_01",
        "track_id": "tr_100",
        "timestamp": now,
        "bbox": (10, 20, 100, 200),
        "event_type": "invalid_event",
    }
    with pytest.raises(ValidationError):
        DetectionEvent(**bad_data)


def test_dwell_event_roundtrip() -> None:
    t1 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 29, 10, 2, 30, tzinfo=UTC)
    dwell = DwellEvent(
        event_id="dwell_01",
        zone_id="shelf_1",
        track_id="tr_42",
        start_ts=t1,
        end_ts=t2,
        duration_sec=150.0,
    )
    data = dwell.model_dump()
    assert data["duration_sec"] == 150.0
    reconstructed = DwellEvent(**data)
    assert reconstructed == dwell


def test_dwell_event_invalid() -> None:
    t1 = datetime(2026, 8, 29, 10, 2, 30, tzinfo=UTC)
    t2 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        # end_ts before start_ts
        DwellEvent(
            event_id="dwell_01",
            zone_id="shelf_1",
            track_id="tr_42",
            start_ts=t1,
            end_ts=t2,
            duration_sec=150.0,
        )
    with pytest.raises(ValidationError):
        # negative duration
        DwellEvent(
            event_id="dwell_01",
            zone_id="shelf_1",
            track_id="tr_42",
            start_ts=t2,
            end_ts=t1,
            duration_sec=-10.0,
        )


def test_stock_event_roundtrip() -> None:
    now = datetime.now(UTC)
    stock = StockEvent(
        event_id="stk_01",
        shelf_id="shelf_a",
        timestamp=now,
        status="low",
        confidence=0.88,
    )
    data = stock.model_dump()
    assert data["status"] == "low"
    assert data["confidence"] == 0.88
    reconstructed = StockEvent(**data)
    assert reconstructed == stock


def test_stock_event_invalid() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        # confidence > 1.0
        StockEvent(
            event_id="stk_01",
            shelf_id="shelf_a",
            timestamp=now,
            status="low",
            confidence=1.5,
        )
    with pytest.raises(ValidationError):
        # confidence < 0.0
        StockEvent(
            event_id="stk_01",
            shelf_id="shelf_a",
            timestamp=now,
            status="low",
            confidence=-0.1,
        )


def test_queue_event_roundtrip() -> None:
    now = datetime.now(UTC)
    queue = QueueEvent(
        event_id="q_01",
        counter_id="counter_1",
        timestamp=now,
        queue_length=3,
        avg_wait_est_sec=90.5,
    )
    data = queue.model_dump()
    assert data["queue_length"] == 3
    assert data["avg_wait_est_sec"] == 90.5
    reconstructed = QueueEvent(**data)
    assert reconstructed == queue


def test_queue_event_invalid() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        QueueEvent(
            event_id="q_01",
            counter_id="counter_1",
            timestamp=now,
            queue_length=-1,
        )


def test_alert_roundtrip() -> None:
    now = datetime.now(UTC)
    alert = Alert(
        alert_id="alt_01",
        alert_type="low_stock",
        severity="warning",
        zone_id="zone_shelf_1",
        message="Shelf 1 low stock detected",
        created_at=now,
    )
    data = alert.model_dump()
    assert data["alert_type"] == "low_stock"
    assert data["severity"] == "warning"
    assert data["resolved_at"] is None
    reconstructed = Alert(**data)
    assert reconstructed == alert


def test_alert_invalid() -> None:
    t1 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 29, 9, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        Alert(
            alert_id="alt_01",
            alert_type="low_stock",
            severity="warning",
            message="Resolved before creation",
            created_at=t1,
            resolved_at=t2,
        )
    bad_data: dict[str, Any] = {
        "alert_id": "alt_01",
        "alert_type": "unsupported_type",
        "severity": "warning",
        "message": "Invalid type",
        "created_at": t1,
    }
    with pytest.raises(ValidationError):
        Alert(**bad_data)


def test_camera_and_app_config_roundtrip() -> None:
    cam = CameraConfig(source="rtsp://192.168.1.100:8080/video")
    zone = ZoneConfig(
        zone_id="entry_1",
        zone_type="entry_exit",
        polygon=[(0, 0), (100, 0), (100, 100)],
        label="Entrance Area",
    )
    app_cfg = AppConfig(
        camera=cam,
        zones=[zone],
        low_stock_confidence_threshold=0.65,
        queue_congestion_length=5,
    )
    data = app_cfg.model_dump()
    assert data["low_stock_confidence_threshold"] == 0.65
    assert data["queue_congestion_length"] == 5
    assert len(data["zones"]) == 1
    reconstructed = AppConfig(**data)
    assert reconstructed == app_cfg


def test_no_pii_fields_present() -> None:
    forbidden = {"image", "frame_data", "face", "embedding"}
    for model in (Frame, ZoneConfig, DetectionEvent, DwellEvent, StockEvent, QueueEvent, Alert):
        assert forbidden.isdisjoint(model.model_fields.keys())


def test_structural_no_pii_fields() -> None:
    """Static/structural test asserting no schema has fields storing raw imagery/PII."""
    forbidden_field_substrings = {
        "image",
        "frame_data",
        "face",
        "embedding",
        "raw_frame",
        "pixels",
        "crop",
    }
    schema_classes = [
        cls
        for cls in schemas.__dict__.values()
        if isinstance(cls, type) and issubclass(cls, BaseModel) and cls is not BaseModel
    ]
    assert len(schema_classes) > 0, "No schema models found"

    for cls in schema_classes:
        fields = set(cls.model_fields.keys())
        for field in fields:
            for forbidden in forbidden_field_substrings:
                assert forbidden not in field.lower(), (
                    f"Forbidden PII/image field '{field}' detected on model '{cls.__name__}'"
                )
