from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.schemas import ZoneConfig


class FootfallBucket(BaseModel):
    bucket_start: datetime
    enters: int = Field(ge=0)
    exits: int = Field(ge=0)
    net: int


class FootfallSummary(BaseModel):
    total_enters: int = Field(ge=0)
    total_exits: int = Field(ge=0)
    net_occupancy: int
    zone_id: str | None = None
    since: datetime | None = None
    buckets: list[FootfallBucket] = Field(default_factory=list)


class HeatmapResponse(BaseModel):
    grid: list[list[float]]
    rows: int = Field(ge=0)
    cols: int = Field(ge=0)
    cell_size: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    zone_id: str | None = None
    total_points: int = Field(ge=0)


class CentralFootfallSummary(BaseModel):
    total_enters: int
    total_exits: int
    net_occupancy: int


class CentralStoreStatus(BaseModel):
    store_id: str
    name: str | None = None
    api_base_url: str | None = None
    reachable: bool
    error: str | None = None
    footfall: CentralFootfallSummary | None = None
    open_alert_count: int | None = None
    queue_events_count: int = 0
    stock_events_count: int = 0


class CentralSummaryResponse(BaseModel):
    generated_at: str
    total_reachable: int
    total_unreachable: int
    stores: list[CentralStoreStatus]


class SystemEnvResponse(BaseModel):
    debug_mode: bool
    variables: dict[str, str] = Field(default_factory=dict)


class UpdateEnvRequest(BaseModel):
    variables: dict[str, str]


class UpdateZonesRequest(BaseModel):
    zones: list[ZoneConfig]
    calibration_width: int | None = Field(default=None, gt=0)
    calibration_height: int | None = Field(default=None, gt=0)


class CameraMeshNodeConfig(BaseModel):
    camera_id: str
    source: str
    role: Literal["entrance", "checkout", "shelf", "general"] = "general"
    label: str = ""
    is_connected: bool = False
    fps: float = 0.0
    width: int = 640
    height: int = 480


class RegisterCameraRequest(BaseModel):
    camera_id: str
    source: str
    role: Literal["entrance", "checkout", "shelf", "general"] = "general"
    label: str = ""


class CameraMeshSummary(BaseModel):
    total_cameras: int
    active_cameras: int
    cameras: list[CameraMeshNodeConfig]


class SKUProfile(BaseModel):
    sku_id: str
    name: str
    brand: str
    expected_zone_id: str
    category: str = "general"


class RegisterSKURequest(BaseModel):
    sku_id: str
    name: str
    brand: str
    expected_zone_id: str
    category: str = "general"


class SKUSegregationItem(BaseModel):
    shelf_id: str
    camera_id: str
    detected_sku_id: str | None = None
    detected_sku_name: str | None = None
    expected_sku_id: str | None = None
    facing_count: int = Field(ge=0)
    fill_percentage: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["ok", "low", "empty", "misplaced"]
    planogram_compliant: bool
    timestamp: datetime


class SKUSegregationReport(BaseModel):
    interval_seconds: float
    total_shelves_monitored: int
    compliant_shelves: int
    misplaced_shelves: int
    low_or_empty_shelves: int
    last_evaluated_at: datetime | None = None
    items: list[SKUSegregationItem]


class ResolveAlertResponse(BaseModel):
    status: Literal["ok"] = "ok"
    alert_id: str


class ResolveAllAlertsResponse(BaseModel):
    status: Literal["ok"] = "ok"
    resolved_count: int = Field(ge=0)


class ResetTelemetryResponse(BaseModel):
    status: Literal["ok"] = "ok"
    cleared_events: int = Field(ge=0)


class UnregisterCameraResponse(BaseModel):
    status: Literal["ok"] = "ok"
    unregistered: str

