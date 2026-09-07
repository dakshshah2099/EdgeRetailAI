from datetime import datetime

from pydantic import BaseModel, Field


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
