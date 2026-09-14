from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from analytics.planogram_lite import (
    PlanogramCompliance,
    get_latest_planogram_compliance,
    load_planogram_layouts,
)
from api.dependencies import RepoDep

router = APIRouter(prefix="/kpi", tags=["kpi", "planogram"])


@router.get("/planogram")
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No planogram layout configured for zone '{zone_id}'",
        )

    compliance = get_latest_planogram_compliance(repo, zone_id, layout=layout)
    if compliance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No planogram compliance data found for zone '{zone_id}'",
        )

    return compliance

