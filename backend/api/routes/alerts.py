from typing import Annotated, Literal

from fastapi import APIRouter, Query

from api.dependencies import RepoDep
from core.schemas import Alert, AuditLogEntry

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
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


@router.get("/audit")
def get_audit_trail(
    repo: RepoDep,
    limit: Annotated[int, Query(ge=1, le=1000, description="Max audit logs to return")] = 100,
    zone_id: Annotated[str | None, Query(description="Filter by zone ID")] = None,
    alert_id: Annotated[str | None, Query(description="Filter by alert ID")] = None,
) -> list[AuditLogEntry]:
    """Query recent threshold breach and resolution audit trail events."""
    return repo.get_audit_events(limit=limit, zone_id=zone_id, alert_id=alert_id)
