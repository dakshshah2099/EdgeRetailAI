from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.dependencies import get_repository
from storage.repository import EventRepository

router = APIRouter(prefix="/reports", tags=["reports"])

RepoDep = Annotated[EventRepository, Depends(get_repository)]
FormatType = Literal["csv", "pdf"]


@router.get("/daily")
def get_daily_report(
    repo: RepoDep,
    date_str: Annotated[
        str,
        Query(
            alias="date",
            description="Target report date in YYYY-MM-DD format",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
    ],
    fmt: Annotated[
        FormatType,
        Query(alias="format", description="Export format: 'csv' or 'pdf'"),
    ] = "csv",
) -> Response:
    """Download daily analytics report in CSV or PDF format.

    Window: [date 00:00:00, date+1 00:00:00).
    Returns HTTP 404 if no events occurred in the requested window.
    """
    try:
        parsed_date = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date format '{date_str}': must be YYYY-MM-DD",
        ) from exc

    from reports.exporters import to_csv, to_pdf
    from reports.report_builder import build_daily_report

    snapshot = build_daily_report(parsed_date, repo)

    if snapshot.is_empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analytics events found for date {date_str}",
        )

    filename = f"daily_report_{date_str}.{fmt}"

    if fmt == "csv":
        csv_content = to_csv(snapshot)
        return Response(
            content=csv_content.encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:  # fmt == "pdf"
        pdf_bytes = to_pdf(snapshot)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.get("/weekly")
def get_weekly_report(
    repo: RepoDep,
    week_start_str: Annotated[
        str,
        Query(
            alias="week_start",
            description="Week start date in YYYY-MM-DD format",
            pattern=r"^\d{4}-\d{2}-\d{2}$",
        ),
    ],
    fmt: Annotated[
        FormatType,
        Query(alias="format", description="Export format: 'csv' or 'pdf'"),
    ] = "csv",
) -> Response:
    """Download weekly analytics report in CSV or PDF format.

    Window: exactly [week_start, week_start + 7 days).
    Returns HTTP 404 if no events occurred in the requested window.
    """
    try:
        parsed_date = date.fromisoformat(week_start_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid week_start format '{week_start_str}': must be YYYY-MM-DD",
        ) from exc

    from reports.exporters import to_csv, to_pdf
    from reports.report_builder import build_weekly_report

    snapshot = build_weekly_report(parsed_date, repo)

    if snapshot.is_empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analytics events found for week starting {week_start_str}",
        )

    filename = f"weekly_report_{week_start_str}.{fmt}"

    if fmt == "csv":
        csv_content = to_csv(snapshot)
        return Response(
            content=csv_content.encode("utf-8"),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:  # fmt == "pdf"
        pdf_bytes = to_pdf(snapshot)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

