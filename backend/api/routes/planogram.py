from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from analytics.planogram_lite import (
    FacingStatus,
    PlanogramCompliance,
    get_latest_planogram_compliance,
    get_or_create_planogram_layout,
    save_planogram_compliance,
    score_planogram_compliance,
)
from api.dependencies import RepoDep, get_app_config
from api.stream_manager import scale_zones_to_frame, stream_manager

router = APIRouter(prefix="/kpi", tags=["kpi", "planogram"])


@router.get("/planogram", response_model=PlanogramCompliance)
def get_planogram_compliance_endpoint(
    zone_id: Annotated[
        str,
        Query(description="Shelf zone ID to evaluate planogram compliance for"),
    ],
    repo: RepoDep,
) -> PlanogramCompliance:
    """Return the most recent planogram compliance snapshot for the specified shelf zone.

    If no historical compliance events exist, attempts live evaluation against the active
    camera frame, or returns a baseline planogram matrix.
    """
    layout = get_or_create_planogram_layout(zone_id)
    compliance = get_latest_planogram_compliance(repo, zone_id, layout=layout)

    # 1. On-demand live scoring if no historical telemetry exists
    if compliance is None:
        is_conn, frame, _, w, h = stream_manager.get_latest_frame()
        if is_conn and frame is not None:
            cfg = get_app_config()
            raw_zones = cfg.zones if cfg and cfg.zones else []
            base_w = cfg.calibration_width if cfg else 640
            base_h = cfg.calibration_height if cfg else 480
            scaled_zones = scale_zones_to_frame(raw_zones, w, h, base_w=base_w, base_h=base_h)
            target_zone = next(
                (z for z in scaled_zones if z.zone_id == zone_id and z.zone_type == "shelf"),
                None,
            )
            if target_zone:
                live_comp = score_planogram_compliance(frame, target_zone, layout)
                save_planogram_compliance(repo, live_comp)
                return live_comp

    # 2. Return historical compliance if found
    if compliance is not None:
        return compliance

    # 3. Clean baseline structure so the frontend facing matrix can render without crashing
    total_facings = layout.grid_rows * layout.grid_cols
    expected_facings = layout.expected_nonempty_facings
    default_facing_statuses = [
        FacingStatus(
            zone_id=zone_id,
            facing_index=(r, c),
            status="empty",
            confidence=0.0,
        )
        for r in range(layout.grid_rows)
        for c in range(layout.grid_cols)
    ]
    return PlanogramCompliance(
        zone_id=zone_id,
        timestamp=datetime.now(),
        total_facings=total_facings,
        expected_nonempty=len(expected_facings),
        actual_nonempty=0,
        compliance_ratio=0.0,
        facing_statuses=default_facing_statuses,
        missing_facings=list(expected_facings),
    )
