from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_repository
from schemas import Alert
from storage.repository import EventRepository

router = APIRouter(prefix="/alerts", tags=["alerts"])

RepoDep = Annotated[EventRepository, Depends(get_repository)]


@router.get("", response_model=list[Alert])
def get_alerts(
    repo: RepoDep,
    status: Annotated[
        Literal["open", "resolved", "all"],
        Query(description="Filter alerts by status: open, resolved, or all"),
    ] = "open",
    limit: Annotated[int, Query(ge=1, le=1000, description="Max alerts to return")] = 100,
) -> list[Alert]:
    """Return alerts filtered by status (open, resolved, or all)."""
    if status == "open":
        open_alerts = repo.get_open_alerts()
        return open_alerts[:limit]
    elif status == "resolved":
        return repo.get_resolved_alerts(limit=limit)
    else:  # status == "all"
        return repo.get_all_alerts(limit=limit)
