from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from analytics.staff_efficiency import (
    StaffEfficiencySummary,
    _is_ge,
    compute_staff_efficiency,
)
from api.dependencies import RepoDep

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/staff")
def get_staff_efficiency_kpi(
    repo: RepoDep,
    since: Annotated[
        datetime | None,
        Query(description="Filter events on or after this ISO timestamp"),
    ] = None,
    until: Annotated[
        datetime | None,
        Query(description="Filter events on or before this ISO timestamp"),
    ] = None,
) -> StaffEfficiencySummary:
    """Return store-level Staff Efficiency KPIs including counter utilization
    and operational alert resolution speed.
    """
    if since is not None and until is not None and _is_ge(since, until) and since != until:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="since timestamp cannot be after until timestamp",
        )

    try:
        return compute_staff_efficiency(repo, since=since, until=until)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
