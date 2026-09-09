from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_repository, is_timestamp_ge
from api.schemas_api import FootfallBucket, FootfallSummary
from core.schemas import QueueEvent, StockEvent
from storage.repository import EventRepository

router = APIRouter(prefix="/kpi", tags=["kpi"])

RepoDep = Annotated[EventRepository, Depends(get_repository)]


@router.get("/footfall", response_model=FootfallSummary)
def get_footfall_kpi(
    repo: RepoDep,
    zone_id: Annotated[str | None, Query(description="Optional zone ID filter")] = None,
    since: Annotated[
        datetime | None,
        Query(description="Filter events on or after this ISO timestamp"),
    ] = None,
    group_by: Annotated[
        Literal["none", "hour", "day"],
        Query(description="Aggregation bucket interval"),
    ] = "none",
    limit: Annotated[
        int,
        Query(ge=1, le=50000, description="Max raw detection events to fetch"),
    ] = 5000,
) -> FootfallSummary:
    """Return aggregated footfall counts and optional time buckets."""
    events = repo.get_recent_detection_events(limit=limit, zone_id=zone_id)

    if since is not None:
        events = [e for e in events if is_timestamp_ge(e.timestamp, since)]

    enters = sum(1 for e in events if e.event_type == "enter")
    exits = sum(1 for e in events if e.event_type == "exit")

    if enters > 0 or exits > 0:
        net_occupancy = max(0, enters - exits)
        total_enters = enters
    else:
        distinct_tracks = len({e.track_id for e in events})
        net_occupancy = distinct_tracks
        total_enters = distinct_tracks

    buckets: list[FootfallBucket] = []

    if group_by in ("hour", "day"):
        buckets_dict: dict[datetime, dict[str, int]] = {}
        for e in events:
            if e.event_type not in ("enter", "exit"):
                continue

            if group_by == "hour":
                bucket_ts = e.timestamp.replace(minute=0, second=0, microsecond=0)
            else:
                bucket_ts = e.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)

            if bucket_ts not in buckets_dict:
                buckets_dict[bucket_ts] = {"enters": 0, "exits": 0}

            if e.event_type == "enter":
                buckets_dict[bucket_ts]["enters"] += 1
            elif e.event_type == "exit":
                buckets_dict[bucket_ts]["exits"] += 1

        for k in sorted(buckets_dict.keys()):
            b_enters = buckets_dict[k]["enters"]
            b_exits = buckets_dict[k]["exits"]
            buckets.append(
                FootfallBucket(
                    bucket_start=k,
                    enters=b_enters,
                    exits=b_exits,
                    net=b_enters - b_exits,
                )
            )

    return FootfallSummary(
        total_enters=total_enters,
        total_exits=exits,
        net_occupancy=net_occupancy,
        zone_id=zone_id,
        since=since,
        buckets=buckets,
    )


@router.get("/queue", response_model=list[QueueEvent])
def get_queue_kpi(
    repo: RepoDep,
    counter_id: Annotated[
        str | None, Query(description="Optional counter ID filter")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=1000, description="Max raw queue events to query")
    ] = 100,
) -> list[QueueEvent]:
    """Return the latest queue length and avg wait estimate per checkout counter."""
    events = repo.get_recent_queue_events(limit=limit, counter_id=counter_id)

    seen_counters: set[str] = set()
    latest_per_counter: list[QueueEvent] = []
    for ev in events:
        if ev.counter_id not in seen_counters:
            seen_counters.add(ev.counter_id)
            latest_per_counter.append(ev)

    return latest_per_counter


@router.get("/stock", response_model=list[StockEvent])
def get_stock_kpi(
    repo: RepoDep,
    shelf_id: Annotated[
        str | None, Query(description="Optional shelf ID filter")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=1000, description="Max raw stock events to query")
    ] = 100,
) -> list[StockEvent]:
    """Return the latest stock level status (empty, low, ok) per shelf."""
    events = repo.get_recent_stock_events(limit=limit, shelf_id=shelf_id)

    seen_shelves: set[str] = set()
    latest_per_shelf: list[StockEvent] = []
    for ev in events:
        if ev.shelf_id not in seen_shelves:
            seen_shelves.add(ev.shelf_id)
            latest_per_shelf.append(ev)

    return latest_per_shelf
