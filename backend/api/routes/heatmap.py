from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from analytics.heatmap import HeatmapAccumulator
from api.dependencies import (
    get_default_frame_dimensions,
    get_repository,
    is_timestamp_ge,
)
from api.schemas_api import HeatmapResponse
from storage.repository import EventRepository

router = APIRouter(prefix="/heatmap", tags=["heatmap"])

RepoDep = Annotated[EventRepository, Depends(get_repository)]


@router.get("", response_model=HeatmapResponse)
def get_heatmap(
    repo: RepoDep,
    zone_id: Annotated[str | None, Query(description="Optional zone ID filter")] = None,
    since: Annotated[
        datetime | None,
        Query(description="Filter events on or after this ISO timestamp"),
    ] = None,
    cell_size: Annotated[
        int, Query(ge=1, le=200, description="Grid cell size in pixels")
    ] = 20,
    width: Annotated[
        int | None, Query(ge=10, le=3840, description="Optional frame width override")
    ] = None,
    height: Annotated[
        int | None, Query(ge=10, le=2160, description="Optional frame height override")
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=50000, description="Max detection events to accumulate"),
    ] = 5000,
) -> HeatmapResponse:
    """Return numeric 2D grid intensity data aggregated from detection events."""
    def_w, def_h = get_default_frame_dimensions()
    resolved_width = width if width is not None else def_w
    resolved_height = height if height is not None else def_h

    if cell_size > resolved_width or cell_size > resolved_height:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cell_size cannot exceed width or height",
        )

    events = repo.get_recent_detection_events(limit=limit, zone_id=zone_id)
    if since is not None:
        events = [e for e in events if is_timestamp_ge(e.timestamp, since)]

    accumulator = HeatmapAccumulator(
        width=resolved_width, height=resolved_height, cell_size=cell_size
    )
    for ev in events:
        accumulator.add_detection(ev.bbox)

    grid_array = accumulator.get_grid()
    grid_list: list[list[float]] = grid_array.tolist()

    return HeatmapResponse(
        grid=grid_list,
        rows=accumulator.grid_height,
        cols=accumulator.grid_width,
        cell_size=cell_size,
        width=resolved_width,
        height=resolved_height,
        zone_id=zone_id,
        total_points=len(events),
    )
