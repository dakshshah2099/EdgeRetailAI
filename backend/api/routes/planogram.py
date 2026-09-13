from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.planogram_lite import (
    PlanogramCompliance,
    get_latest_planogram_compliance,
    load_planogram_layouts,
)
from api.dependencies import get_repository
from storage.repository import EventRepository

router = APIRouter(prefix="/kpi", tags=["kpi", "planogram"])

RepoDep = Annotated[EventRepository, Depends(get_repository)]


@router.get("/planogram", response_model=PlanogramCompliance)
def get_planogram_compliance_endpoint(
    zone_id: Annotated[
        str,
        Query(description="Shelf zone ID to evaluate planogram compliance for"),
    ],
    repo: RepoDep,
) -> PlanogramCompliance:
    """Return the most recent planogram compliance snapshot for the specified shelf zone."""
    layouts = load_planogram_layouts()
    layout = layouts.get(zone_id)
    if layout is None:
        raise HTTPException(
            status_code=404,
            detail=f"No planogram layout configured for zone '{zone_id}'",
        )

    compliance = get_latest_planogram_compliance(repo, zone_id, layout=layout)
    if compliance is None:
        raise HTTPException(
            status_code=404,
            detail=f"No planogram compliance data found for zone '{zone_id}'",
        )

    return compliance
