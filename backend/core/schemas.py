from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Frame(BaseModel):
    """A single camera frame. NOTE: this model must NEVER be persisted to
    disk/DB — it exists only in-memory for pipeline processing. Do not add
    this type as a field on any model in storage/ later."""

    source_id: str
    timestamp: datetime
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    # actual pixel data intentionally NOT a typed field here — pipeline
    # code passes raw ndarray alongside this metadata, never serializes it.


class ZoneConfig(BaseModel):
    zone_id: str
    zone_type: Literal["entry_exit", "product_display", "shelf", "checkout"]
    polygon: list[tuple[int, int]] = Field(min_length=3)  # pixel coords, min 3 points
    label: str
    camera_id: str | None = None


class DetectionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    track_id: str  # anonymous, ephemeral, never linked to identity
    timestamp: datetime
    bbox: tuple[int, int, int, int]  # x, y, w, h
    zone_id: str | None = None
    event_type: Literal["enter", "exit", "in_zone"]
    camera_id: str | None = None

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


class StockEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    shelf_id: str
    timestamp: datetime
    status: Literal["empty", "low", "ok"]
    confidence: float = Field(ge=0.0, le=1.0)


class QueueEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    counter_id: str
    timestamp: datetime
    queue_length: int = Field(ge=0)
    avg_wait_est_sec: float | None = Field(default=None, ge=0.0)
    predicted_queue_length: int | None = Field(default=None, ge=0)
    predicted_wait_sec: float | None = Field(default=None, ge=0.0)
    congested: bool = Field(default=False)


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


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    log_id: str
    timestamp: datetime
    event_type: Literal["breach_opened", "breach_escalated", "auto_cleared", "resolved"]
    alert_id: str
    alert_type: Literal["low_stock", "queue_congestion", "custom"]
    severity: Literal["info", "warning", "critical"]
    zone_id: str | None = None
    sku_id: str | None = None
    message: str
    facings: int | None = None
    cleared_reason: str | None = None


class CameraConfig(BaseModel):
    source: str


class StoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    store_id: str
    name: str
    api_base_url: str


class CameraNodeDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)
    camera_id: str
    source: str
    role: Literal["entrance", "checkout", "shelf", "general"] = "general"
    label: str = ""


class AppConfig(BaseModel):
    camera: CameraConfig
    cameras: list[CameraNodeDefinition] = Field(default_factory=list)
    zones: list[ZoneConfig] = Field(default_factory=list)
    calibration_width: int = Field(default=640, gt=0)
    calibration_height: int = Field(default=480, gt=0)
    low_stock_confidence_threshold: float = Field(ge=0.0, le=1.0)
    queue_congestion_length: int = Field(ge=1)


DEFAULT_CONFIG_YAML = """camera:
  source: "rtsp://192.168.1.100:8080/h264_pcm.sdp"
calibration_width: 640
calibration_height: 480
zones:
  - zone_id: "zone_entrance_exit"
    zone_type: "entry_exit"
    polygon:
      - [40, 360]
      - [240, 360]
      - [240, 470]
      - [40, 470]
    label: "Main Entrance / Exit"
  - zone_id: "zone_shelf_beverages"
    zone_type: "shelf"
    polygon:
      - [50, 80]
      - [220, 80]
      - [220, 240]
      - [50, 240]
    label: "Shelf 1 - Cold Beverages"
  - zone_id: "zone_shelf_snacks"
    zone_type: "shelf"
    polygon:
      - [250, 80]
      - [420, 80]
      - [420, 240]
      - [250, 240]
    label: "Shelf 2 - Snacks & Bakery"
  - zone_id: "zone_shelf_electronics"
    zone_type: "shelf"
    polygon:
      - [450, 80]
      - [610, 80]
      - [610, 240]
      - [450, 240]
    label: "Shelf 3 - Tech & Accessories"
  - zone_id: "zone_display_promo"
    zone_type: "product_display"
    polygon:
      - [220, 260]
      - [380, 260]
      - [380, 340]
      - [220, 340]
    label: "Promotional Island Display"
  - zone_id: "zone_queue_checkout_1"
    zone_type: "checkout"
    polygon:
      - [300, 350]
      - [440, 350]
      - [440, 460]
      - [300, 460]
    label: "Checkout Counter 1"
  - zone_id: "zone_queue_checkout_2"
    zone_type: "checkout"
    polygon:
      - [470, 350]
      - [610, 350]
      - [610, 460]
      - [470, 460]
    label: "Checkout Counter 2"
low_stock_confidence_threshold: 0.6
queue_congestion_length: 4
"""


def ensure_default_config(path: str | Path) -> Path:
    """Ensure config file exists and is populated with default configuration."""
    config_path = Path(path)
    if not config_path.is_file() or config_path.stat().st_size == 0:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")
    return config_path


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.is_file():
        if config_path.name == "config.yaml":
            ensure_default_config(config_path)
        else:
            raise FileNotFoundError(f"Config file not found: {path}")

    if config_path.stat().st_size == 0:
        ensure_default_config(config_path)

    with config_path.open("r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Config file at {path} must contain a YAML mapping/dictionary")

    return AppConfig.model_validate(raw_data)

