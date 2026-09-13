from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from api.schemas_api import FootfallSummary
from core.schemas import Alert, DetectionEvent, DwellEvent, QueueEvent, StockEvent
from storage.repository import EventRepository

# Gracefully import staff_efficiency if available (Slice 13)
try:
    from analytics.staff_efficiency import (
        StaffEfficiencySummary,
        compute_staff_efficiency,
    )
except ImportError:
    StaffEfficiencySummary = None  # type: ignore[misc, assignment]
    compute_staff_efficiency = None  # type: ignore[assignment]


def _normalize_tz(dt: datetime, reference: datetime) -> datetime:
    """Normalize timezone awareness between two datetimes for safe comparison."""
    if dt.tzinfo is None and reference.tzinfo is not None:
        return dt.replace(tzinfo=reference.tzinfo)
    if dt.tzinfo is not None and reference.tzinfo is None:
        return dt.replace(tzinfo=None)
    return dt


def _in_window(ts: datetime, start_dt: datetime, end_dt: datetime) -> bool:
    """Check if ts is in the half-open interval [start_dt, end_dt)."""
    norm_start = _normalize_tz(start_dt, ts)
    norm_end = _normalize_tz(end_dt, ts)
    return norm_start <= ts < norm_end


class WindowedEventRepository(EventRepository):
    """Read-only view over EventRepository filtering events to [start_dt, end_dt).

    Allows existing KPI aggregation functions in api/routes/kpi.py and api/routes/alerts.py
    to be called directly without duplicating their aggregation logic.
    """

    def __init__(self, repo: EventRepository, start_dt: datetime, end_dt: datetime) -> None:
        self._repo = repo
        self._start_dt = start_dt
        self._end_dt = end_dt
        self.db_path = repo.db_path

    def get_recent_detection_events(
        self, limit: int = 50000, zone_id: str | None = None
    ) -> list[DetectionEvent]:
        events = self._repo.get_recent_detection_events(limit=limit, zone_id=zone_id)
        filtered = [e for e in events if _in_window(e.timestamp, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_recent_dwell_events(
        self, limit: int = 50000, zone_id: str | None = None
    ) -> list[DwellEvent]:
        events = self._repo.get_recent_dwell_events(limit=limit, zone_id=zone_id)
        filtered = [e for e in events if _in_window(e.start_ts, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_recent_queue_events(
        self, limit: int = 50000, counter_id: str | None = None
    ) -> list[QueueEvent]:
        events = self._repo.get_recent_queue_events(limit=limit, counter_id=counter_id)
        filtered = [e for e in events if _in_window(e.timestamp, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_recent_stock_events(
        self, limit: int = 50000, shelf_id: str | None = None
    ) -> list[StockEvent]:
        events = self._repo.get_recent_stock_events(limit=limit, shelf_id=shelf_id)
        filtered = [e for e in events if _in_window(e.timestamp, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_all_alerts(self, limit: int = 50000) -> list[Alert]:
        alerts = self._repo.get_all_alerts(limit=limit)
        filtered = [a for a in alerts if _in_window(a.created_at, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_resolved_alerts(self, limit: int = 50000) -> list[Alert]:
        alerts = self._repo.get_resolved_alerts(limit=limit)
        filtered = [a for a in alerts if _in_window(a.created_at, self._start_dt, self._end_dt)]
        return filtered[:limit]

    def get_open_alerts(self) -> list[Alert]:
        alerts = self._repo.get_open_alerts()
        return [a for a in alerts if _in_window(a.created_at, self._start_dt, self._end_dt)]


class ReportSnapshot(BaseModel):
    """Immutable, serializable snapshot aggregating KPI outputs for a time window."""

    model_config = ConfigDict(frozen=True)

    report_type: str = Field(description="Type of report: 'daily' or 'weekly'")
    window_start: datetime = Field(description="Inclusive start timestamp [start, end)")
    window_end: datetime = Field(description="Exclusive end timestamp [start, end)")
    generated_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    footfall: FootfallSummary
    queues: list[QueueEvent] = Field(default_factory=list)
    stock: list[StockEvent] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    staff_efficiency: Any | None = None
    total_events: int = Field(default=0, ge=0)

    @property
    def is_empty(self) -> bool:
        """Return True if the requested window contains zero total events."""
        return self.total_events == 0

    @property
    def start_time(self) -> datetime:
        """Alias for window_start."""
        return self.window_start

    @property
    def end_time(self) -> datetime:
        """Alias for window_end."""
        return self.window_end

    @property
    def queue_events(self) -> list[QueueEvent]:
        """Alias for queues."""
        return self.queues

    @property
    def stock_events(self) -> list[StockEvent]:
        """Alias for stock."""
        return self.stock

    @property
    def alert_events(self) -> list[Alert]:
        """Alias for alerts."""
        return self.alerts


def _parse_date(date_val: date | str) -> date:
    """Parse date object or YYYY-MM-DD string into a date."""
    if isinstance(date_val, str):
        return date.fromisoformat(date_val)
    return date_val


def build_daily_report(
    target_date: date | str,
    repo: EventRepository,
) -> ReportSnapshot:
    """Build a ReportSnapshot for [day 00:00:00, day+1 00:00:00).

    Reuses existing KPI aggregation functions directly without duplicating logic.
    """
    d = _parse_date(target_date)
    start_dt = datetime.combine(d, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)

    windowed_repo = WindowedEventRepository(repo, start_dt, end_dt)

    from api.routes.alerts import get_alerts
    from api.routes.kpi import get_footfall_kpi, get_queue_kpi, get_stock_kpi

    # Call existing aggregation functions
    footfall = get_footfall_kpi(repo=windowed_repo, since=start_dt)
    queues = get_queue_kpi(repo=windowed_repo)
    stock = get_stock_kpi(repo=windowed_repo)
    alerts = get_alerts(repo=windowed_repo, status="all", limit=1000)

    # Staff efficiency KPI (Slice 13, if available)
    staff_summary = None
    if compute_staff_efficiency is not None:
        try:
            staff_summary = compute_staff_efficiency(
                repo=windowed_repo,
                since=start_dt,
                until=end_dt - timedelta(microseconds=1),
            )
        except Exception:
            staff_summary = None

    # Count total raw events in window to determine empty window status
    raw_detections = windowed_repo.get_recent_detection_events(limit=50000)
    raw_queues = windowed_repo.get_recent_queue_events(limit=50000)
    raw_stock = windowed_repo.get_recent_stock_events(limit=50000)
    raw_alerts = windowed_repo.get_all_alerts(limit=50000)
    total_events = (
        len(raw_detections) + len(raw_queues) + len(raw_stock) + len(raw_alerts)
    )

    return ReportSnapshot(
        report_type="daily",
        window_start=start_dt,
        window_end=end_dt,
        footfall=footfall,
        queues=queues,
        stock=stock,
        alerts=alerts,
        staff_efficiency=staff_summary,
        total_events=total_events,
    )


def build_weekly_report(
    week_start: date | str,
    repo: EventRepository,
) -> ReportSnapshot:
    """Build a ReportSnapshot for exactly [week_start, week_start + 7 days).

    Reuses existing KPI aggregation functions directly without duplicating logic.
    """
    d = _parse_date(week_start)
    start_dt = datetime.combine(d, datetime.min.time())
    end_dt = start_dt + timedelta(days=7)

    windowed_repo = WindowedEventRepository(repo, start_dt, end_dt)

    from api.routes.alerts import get_alerts
    from api.routes.kpi import get_footfall_kpi, get_queue_kpi, get_stock_kpi

    footfall = get_footfall_kpi(repo=windowed_repo, since=start_dt)
    queues = get_queue_kpi(repo=windowed_repo)
    stock = get_stock_kpi(repo=windowed_repo)
    alerts = get_alerts(repo=windowed_repo, status="all", limit=1000)

    staff_summary = None
    if compute_staff_efficiency is not None:
        try:
            staff_summary = compute_staff_efficiency(
                repo=windowed_repo,
                since=start_dt,
                until=end_dt - timedelta(microseconds=1),
            )
        except Exception:
            staff_summary = None

    raw_detections = windowed_repo.get_recent_detection_events(limit=50000)
    raw_queues = windowed_repo.get_recent_queue_events(limit=50000)
    raw_stock = windowed_repo.get_recent_stock_events(limit=50000)
    raw_alerts = windowed_repo.get_all_alerts(limit=50000)
    total_events = (
        len(raw_detections) + len(raw_queues) + len(raw_stock) + len(raw_alerts)
    )

    return ReportSnapshot(
        report_type="weekly",
        window_start=start_dt,
        window_end=end_dt,
        footfall=footfall,
        queues=queues,
        stock=stock,
        alerts=alerts,
        staff_efficiency=staff_summary,
        total_events=total_events,
    )

