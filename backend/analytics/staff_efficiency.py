from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.schemas import Alert, QueueEvent
from storage.repository import EventRepository


def _normalize_tz(dt: datetime, reference: datetime) -> datetime:
    """Normalize timezone awareness between two datetimes for safe comparison."""
    if dt.tzinfo is None and reference.tzinfo is not None:
        return dt.replace(tzinfo=reference.tzinfo)
    if dt.tzinfo is not None and reference.tzinfo is None:
        return dt.replace(tzinfo=None)
    return dt


def _is_ge(t1: datetime, t2: datetime) -> bool:
    """Return True if t1 >= t2, safely handling tz-aware and tz-naive mixing."""
    return t1 >= _normalize_tz(t2, t1)


def _is_le(t1: datetime, t2: datetime) -> bool:
    """Return True if t1 <= t2, safely handling tz-aware and tz-naive mixing."""
    return t1 <= _normalize_tz(t2, t1)


class CounterUtilization(BaseModel):
    """Store-level counter utilization metrics.

    Zero-PII: aggregates anonymous checkout activity across counters without employee identity.
    """

    model_config = ConfigDict(frozen=True)

    counters_active: int = Field(
        default=0,
        ge=0,
        description="Count of distinct checkout counters active in the window",
    )
    counters_recommended: int = Field(
        default=0,
        ge=0,
        description="Number of counter opening recommendations triggered",
    )
    recommendations_followed: int = Field(
        default=0,
        ge=0,
        description="Number of counter opening recommendations that were followed",
    )
    recommendation_follow_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of followed recommendations (0.0 if counters_recommended is 0)",
    )

    @property
    def active_counters(self) -> int:
        """Alias for counters_active."""
        return self.counters_active


class AlertResponseStats(BaseModel):
    """Store-level operational incident resolution speed metrics.

    Zero-PII: measures system resolution lifecycle across alerts without staff identification.
    Unresolved alerts are completely excluded from these calculations.
    """

    model_config = ConfigDict(frozen=True)

    total_resolved: int = Field(
        default=0,
        ge=0,
        description="Total number of resolved alerts in the requested window",
    )
    resolved_count: int = Field(
        default=0,
        ge=0,
        description="Alias for total_resolved",
    )
    avg_response_time_sec: float | None = Field(
        default=None,
        ge=0.0,
        description="Average resolution time in seconds across resolved alerts",
    )
    min_response_time_sec: float | None = Field(
        default=None,
        ge=0.0,
        description="Minimum resolution time in seconds across resolved alerts",
    )
    max_response_time_sec: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum resolution time in seconds across resolved alerts",
    )

    @property
    def average_response_time_sec(self) -> float | None:
        """Alias for avg_response_time_sec."""
        return self.avg_response_time_sec


class StaffEfficiencySummary(BaseModel):
    """Aggregated Staff Efficiency KPI response model.

    Store-level summary of checkout counter utilization and alert response times.
    Contains no PII, staff IDs, or per-employee tracking data.
    """

    model_config = ConfigDict(frozen=True)

    counter_utilization: CounterUtilization
    alert_response: AlertResponseStats
    since: datetime | None = None
    until: datetime | None = None

    @property
    def alert_response_stats(self) -> AlertResponseStats:
        """Alias for alert_response."""
        return self.alert_response

    @property
    def counters(self) -> CounterUtilization:
        """Alias for counter_utilization."""
        return self.counter_utilization

    @property
    def alerts(self) -> AlertResponseStats:
        """Alias for alert_response."""
        return self.alert_response


def compute_staff_efficiency(
    repo: EventRepository,
    since: datetime | None = None,
    until: datetime | None = None,
) -> StaffEfficiencySummary:
    """Compute store-level Staff Efficiency KPIs from EventRepository data.

    Pure, read-only aggregation:
    - counters_active counts distinct counter_ids with >= 1 QueueEvent in window.
    - counters_recommended counts queue congestion recommendation alerts.
    - recommendation_follow_rate is recommendations_followed / counters_recommended,
      or 0.0 if counters_recommended == 0.
    - AlertResponseStats excludes unresolved alerts entirely.
    """
    if since is not None and until is not None and _is_ge(since, until) and since != until:
        raise ValueError("since cannot be after until")

    # Fetch raw queue events and alerts from repository
    raw_queue_events: list[QueueEvent] = repo.get_recent_queue_events(limit=50000)
    raw_alerts: list[Alert] = repo.get_all_alerts(limit=50000)

    # Filter queue events within requested window
    filtered_q_events: list[QueueEvent] = [
        e
        for e in raw_queue_events
        if (since is None or _is_ge(e.timestamp, since))
        and (until is None or _is_le(e.timestamp, until))
    ]

    # Filter alerts within requested window (based on creation time)
    filtered_alerts: list[Alert] = [
        a
        for a in raw_alerts
        if (since is None or _is_ge(a.created_at, since))
        and (until is None or _is_le(a.created_at, until))
    ]

    # 1. Counter Utilization calculation
    active_counter_ids: set[str] = {e.counter_id for e in filtered_q_events}
    counters_active: int = len(active_counter_ids)

    # Recommendations: queue congestion alerts recommending opening counters
    rec_alerts: list[Alert] = [
        a
        for a in filtered_alerts
        if a.alert_type == "queue_congestion" or "counter" in a.message.lower()
    ]
    counters_recommended: int = len(rec_alerts)

    recommendations_followed: int = 0
    if counters_recommended > 0:
        for rec in rec_alerts:
            # Check if an additional counter was opened / active after the recommendation
            has_counter_followup = False
            for qe in filtered_q_events:
                if _is_ge(qe.timestamp, rec.created_at):
                    is_other_counter = (
                        rec.zone_id is not None and qe.counter_id != rec.zone_id
                    ) or (rec.zone_id is None and len(active_counter_ids) > 1)
                    if is_other_counter:
                        has_counter_followup = True
                        break

            # Fallback if no queue events exist in repo: check whether alert was resolved
            if not filtered_q_events and rec.resolved_at is not None:
                has_counter_followup = True

            if has_counter_followup:
                recommendations_followed += 1

    recommendation_follow_rate: float = (
        float(recommendations_followed / counters_recommended)
        if counters_recommended > 0
        else 0.0
    )

    counter_util = CounterUtilization(
        counters_active=counters_active,
        counters_recommended=counters_recommended,
        recommendations_followed=recommendations_followed,
        recommendation_follow_rate=recommendation_follow_rate,
    )

    # 2. Alert Response Stats calculation
    # Unresolved alerts MUST be excluded entirely from AlertResponseStats
    resolved_alerts: list[Alert] = [a for a in filtered_alerts if a.resolved_at is not None]

    if not resolved_alerts:
        alert_stats = AlertResponseStats(
            total_resolved=0,
            resolved_count=0,
            avg_response_time_sec=None,
            min_response_time_sec=None,
            max_response_time_sec=None,
        )
    else:
        response_times: list[float] = []
        for a in resolved_alerts:
            assert a.resolved_at is not None
            res_at_norm = _normalize_tz(a.resolved_at, a.created_at)
            delta_sec = max(0.0, (res_at_norm - a.created_at).total_seconds())
            response_times.append(delta_sec)

        count = len(response_times)
        alert_stats = AlertResponseStats(
            total_resolved=count,
            resolved_count=count,
            avg_response_time_sec=sum(response_times) / count if count > 0 else None,
            min_response_time_sec=min(response_times) if count > 0 else None,
            max_response_time_sec=max(response_times) if count > 0 else None,
        )

    return StaffEfficiencySummary(
        counter_utilization=counter_util,
        alert_response=alert_stats,
        since=since,
        until=until,
    )

