from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Frame(BaseModel):
    """A single camera frame. NOTE: this model must NEVER be persisted to
    disk/DB -- it exists only in-memory for pipeline processing. Do not add
    this type as a field on any model in storage/ later."""

    source_id: str
    timestamp: datetime
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    # actual pixel data intentionally NOT a typed field here -- pipeline
    # code passes raw ndarray alongside this metadata, never serializes it.


class ZoneConfig(BaseModel):
    zone_id: str
    zone_type: Literal["entry_exit", "product_display", "shelf", "checkout"]
    polygon: list[tuple[int, int]] = Field(min_length=3)  # pixel coords, min 3 points
    label: str


class DetectionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    track_id: str  # anonymous, ephemeral, never linked to identity
    timestamp: datetime
    bbox: tuple[int, int, int, int]  # x, y, w, h
    zone_id: str | None = None
    event_type: Literal["enter", "exit", "in_zone"]

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if len(v) != 4:
            raise ValueError("bbox must be a 4-tuple (x, y, w, h)")
        if v[2] < 0 or v[3] < 0:
            raise ValueError("bbox width and height must be non-negative")
        return v


class DwellEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    zone_id: str
    track_id: str
    start_ts: datetime
    end_ts: datetime
    duration_sec: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_timestamps(self) -> "DwellEvent":
        if self.end_ts < self.start_ts:
            raise ValueError("end_ts must be greater than or equal to start_ts")
        return self


class Detection(BaseModel):
    """Generic vision detection object for multi-class detection pipeline."""

    model_config = ConfigDict(frozen=True)
    class_id: int = Field(ge=0)
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: tuple[int, int, int, int]  # x, y, w, h
    timestamp: datetime

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if len(v) != 4:
            raise ValueError("bbox must be a 4-tuple (x, y, w, h)")
        if v[2] < 0 or v[3] < 0:
            raise ValueError("bbox width and height must be non-negative")
        return v


class ZoneTransition(BaseModel):
    """Movement of a tracked entity between retail zones (cross-slice contract)."""

    model_config = ConfigDict(frozen=True)
    track_id: str
    from_zone_id: str
    to_zone_id: str
    timestamp: datetime


class ShelfOccupancyResult(BaseModel):
    """Result of a single shelf occupancy classification (cross-slice contract)."""

    model_config = ConfigDict(frozen=True)
    shelf_id: str
    status: Literal["empty", "low", "ok"]
    confidence: float = Field(ge=0.0, le=1.0)
    occupancy: float = Field(ge=0.0, le=1.0)


class InteractionEvent(BaseModel):
    """Customer-product interaction event emitted at start and end of engagement."""

    model_config = ConfigDict(frozen=True)
    event_id: str
    track_id: str
    zone_id: str
    start_ts: datetime
    end_ts: datetime
    event_phase: Literal["start", "end"] = "end"
    detection_confidence: float = Field(ge=0.0, le=1.0)
    interaction_confidence: float = Field(ge=0.0, le=1.0)
    interaction_type: Literal["approach", "touch", "pickup", "examine"] = "touch"

    @model_validator(mode="after")
    def validate_timestamps(self) -> "InteractionEvent":
        if self.end_ts < self.start_ts:
            raise ValueError("end_ts must be greater than or equal to start_ts")
        return self


# Convenience alias so callers can be explicit about start vs. end semantics
InteractionStartEvent = InteractionEvent


class StockEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    shelf_id: str
    timestamp: datetime
    status: Literal["empty", "low", "ok"]
    confidence: float = Field(ge=0.0, le=1.0)
    occupancy: float | None = Field(default=None, ge=0.0, le=1.0)


class QueueEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    counter_id: str
    timestamp: datetime
    queue_length: int = Field(ge=0)
    avg_wait_est_sec: float | None = Field(default=None, ge=0.0)


class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)
    alert_id: str
    alert_type: Literal["low_stock", "queue_congestion", "custom"]
    severity: Literal["info", "warning", "critical"]
    zone_id: str | None = None
    message: str
    created_at: datetime
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_alert_times(self) -> "Alert":
        if self.resolved_at is not None and self.resolved_at < self.created_at:
            raise ValueError("resolved_at cannot be before created_at")
        return self


class CameraConfig(BaseModel):
    source: str


class AppConfig(BaseModel):
    camera: CameraConfig
    zones: list[ZoneConfig] = Field(default_factory=list)
    low_stock_confidence_threshold: float = Field(ge=0.0, le=1.0)
    queue_congestion_length: int = Field(ge=1)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Config file at {path} must contain a YAML mapping/dictionary")

    return AppConfig.model_validate(raw_data)
