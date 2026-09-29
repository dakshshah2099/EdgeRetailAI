import os
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from analytics.sku_classifier import sku_segregator
from api.dependencies import RepoDep, is_timestamp_ge
from api.schemas_api import (
    FootfallBucket,
    FootfallSummary,
    RegisterSKURequest,
    ResetTelemetryResponse,
    SKUProfile,
    SKUSegregationReport,
)
from core.schemas import QueueEvent, StockEvent

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/footfall")
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

    from api.stream_manager import stream_manager

    if (
        "PYTEST_CURRENT_TEST" not in os.environ
        and stream_manager.is_any_camera_connected()
        and zone_id is None
    ):
        net_occupancy = stream_manager.get_total_occupancy()
        total_enters = enters if enters > 0 else net_occupancy
    elif enters > 0 or exits > 0:
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


@router.get("/queue")
def get_queue_kpi(
    repo: RepoDep,
    counter_id: Annotated[str | None, Query(description="Optional counter ID filter")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Max raw queue events to query")] = 100,
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


@router.get("/stock")
def get_stock_kpi(
    repo: RepoDep,
    shelf_id: Annotated[str | None, Query(description="Optional shelf ID filter")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Max raw stock events to query")] = 100,
) -> list[StockEvent]:
    """Return the latest stock level status (empty, low, ok) per shelf."""
    if shelf_id is not None:
        events = repo.get_recent_stock_events(limit=limit, shelf_id=shelf_id)
        if events:
            return events[:1]
        all_recent = repo.get_recent_stock_events(limit=max(limit, 500))
        facing_evs = [e for e in all_recent if e.shelf_id.startswith(f"{shelf_id}:facing:")]
        if facing_evs:
            has_empty = any(e.status == "empty" for e in facing_evs)
            has_low = any(e.status == "low" for e in facing_evs)
            derived_status: Literal["empty", "low", "ok"] = (
                "empty" if has_empty else ("low" if has_low else "ok")
            )
            avg_conf = sum(e.confidence for e in facing_evs) / len(facing_evs)
            return [
                StockEvent(
                    event_id=f"rollup_{shelf_id}",
                    shelf_id=shelf_id,
                    timestamp=facing_evs[0].timestamp,
                    status=derived_status,
                    confidence=round(avg_conf, 2),
                )
            ]
        return []

    events = repo.get_recent_stock_events(limit=max(limit, 1000))
    seen_shelves: set[str] = set()
    latest_per_shelf: list[StockEvent] = []

    # 1. Direct parent shelf events
    for ev in events:
        if ":facing:" not in ev.shelf_id and ev.shelf_id not in seen_shelves:
            seen_shelves.add(ev.shelf_id)
            latest_per_shelf.append(ev)

    # 2. For shelves only having sub-facing events, synthesize a rolled-up parent event
    facings_by_shelf: dict[str, list[StockEvent]] = {}
    for ev in events:
        if ":facing:" in ev.shelf_id:
            parent_id = ev.shelf_id.split(":facing:")[0]
            if parent_id not in seen_shelves:
                facings_by_shelf.setdefault(parent_id, []).append(ev)

    for parent_id, f_list in facings_by_shelf.items():
        if parent_id not in seen_shelves:
            seen_shelves.add(parent_id)
            has_empty = any(e.status == "empty" for e in f_list)
            has_low = any(e.status == "low" for e in f_list)
            d_status: Literal["empty", "low", "ok"] = (
                "empty" if has_empty else ("low" if has_low else "ok")
            )
            avg_conf = sum(e.confidence for e in f_list) / len(f_list)
            latest_per_shelf.append(
                StockEvent(
                    event_id=f"rollup_{parent_id}",
                    shelf_id=parent_id,
                    timestamp=f_list[0].timestamp,
                    status=d_status,
                    confidence=round(avg_conf, 2),
                )
            )

    return latest_per_shelf


@router.get("/sku")
def get_sku_segregation_kpi() -> SKUSegregationReport:
    """Return latest edge SKU segregation and planogram compliance report (locked >=10s)."""
    return sku_segregator.get_latest_report()


@router.get("/sku/catalog")
def list_sku_catalog() -> list[SKUProfile]:
    """Return all catalog SKU profiles registered in the edge planogram."""
    return sku_segregator.get_catalog()


@router.post("/sku/catalog")
def register_catalog_sku(req: RegisterSKURequest) -> SKUProfile:
    """Register or update an SKU item in the edge planogram catalog."""
    sku_segregator.register_sku(
        sku_id=req.sku_id,
        name=req.name,
        brand=req.brand,
        expected_zone_id=req.expected_zone_id,
        category=req.category,
    )
    sku = sku_segregator.get_sku(req.sku_id)
    if sku is None:
        return SKUProfile(
            sku_id=req.sku_id,
            name=req.name,
            brand=req.brand,
            expected_zone_id=req.expected_zone_id,
            category=req.category,
        )
    return sku


@router.post("/reset")
def reset_telemetry(repo: RepoDep) -> ResetTelemetryResponse:
    """Purge transient detection, dwell, queue, and stock events to reset telemetry."""
    from api.stream_manager import stream_manager

    stream_manager.reset()
    cleared_count = repo.clear_detection_events()
    return ResetTelemetryResponse(
        status="ok",
        cleared_events=cleared_count,
        deleted=cleared_count,
    )

