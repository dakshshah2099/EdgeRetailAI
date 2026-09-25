from datetime import datetime
from pathlib import Path

from core.schemas import (
    Alert,
    AuditLogEntry,
    DetectionEvent,
    DwellEvent,
    QueueEvent,
    StockEvent,
)
from storage.db import get_connection, init_db


class EventRepository:
    """Typed save/query layer over SQLite.

    One table per event type, columns matching Pydantic model fields directly.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def save_detection_event(self, event: DetectionEvent) -> None:
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO detection_events (
                        event_id, track_id, timestamp,
                        bbox_x, bbox_y, bbox_w, bbox_h,
                        zone_id, event_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.track_id,
                        event.timestamp.isoformat(),
                        event.bbox[0],
                        event.bbox[1],
                        event.bbox[2],
                        event.bbox[3],
                        event.zone_id,
                        event.event_type,
                    ),
                )
        finally:
            conn.close()

    def save_dwell_event(self, event: DwellEvent) -> None:
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO dwell_events (
                        event_id, zone_id, track_id, start_ts, end_ts, duration_sec
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.zone_id,
                        event.track_id,
                        event.start_ts.isoformat(),
                        event.end_ts.isoformat(),
                        event.duration_sec,
                    ),
                )
        finally:
            conn.close()

    def save_stock_event(self, event: StockEvent) -> None:
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO stock_events (
                        event_id, shelf_id, timestamp, status, confidence
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.shelf_id,
                        event.timestamp.isoformat(),
                        event.status,
                        event.confidence,
                    ),
                )
        finally:
            conn.close()

    def save_queue_event(self, event: QueueEvent) -> None:
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO queue_events (
                        event_id, counter_id, timestamp, queue_length, avg_wait_est_sec,
                        predicted_queue_length, predicted_wait_sec
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        event.event_id,
                        event.counter_id,
                        event.timestamp.isoformat(),
                        event.queue_length,
                        event.avg_wait_est_sec,
                        event.predicted_queue_length,
                        event.predicted_wait_sec,
                    ),
                )
        finally:
            conn.close()

    def save_alert(self, alert: Alert) -> None:
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO alerts (
                        alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        alert.alert_id,
                        alert.alert_type,
                        alert.severity,
                        alert.zone_id,
                        alert.message,
                        alert.created_at.isoformat(),
                        alert.resolved_at.isoformat() if alert.resolved_at is not None else None,
                    ),
                )
        finally:
            conn.close()

    def upsert_alert(self, alert: Alert) -> None:
        """Insert or update alert matched on alert_id."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO alerts (
                        alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(alert_id) DO UPDATE SET
                        alert_type = excluded.alert_type,
                        severity = excluded.severity,
                        zone_id = excluded.zone_id,
                        message = excluded.message,
                        created_at = excluded.created_at,
                        resolved_at = excluded.resolved_at;
                    """,
                    (
                        alert.alert_id,
                        alert.alert_type,
                        alert.severity,
                        alert.zone_id,
                        alert.message,
                        alert.created_at.isoformat(),
                        alert.resolved_at.isoformat() if alert.resolved_at is not None else None,
                    ),
                )
        finally:
            conn.close()

    def get_recent_stock_events(
        self, limit: int = 100, shelf_id: str | None = None
    ) -> list[StockEvent]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            if shelf_id is not None:
                cursor.execute(
                    """
                    SELECT event_id, shelf_id, timestamp, status, confidence
                    FROM stock_events
                    WHERE shelf_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (shelf_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, shelf_id, timestamp, status, confidence
                    FROM stock_events
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                StockEvent(
                    event_id=row["event_id"],
                    shelf_id=row["shelf_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    status=row["status"],
                    confidence=float(row["confidence"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_open_alerts(self) -> list[Alert]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                FROM alerts
                WHERE resolved_at IS NULL
                ORDER BY created_at DESC;
                """
            )
            rows = cursor.fetchall()
            return [
                Alert(
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    severity=row["severity"],
                    zone_id=row["zone_id"],
                    message=row["message"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    resolved_at=None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def resolve_all_open_alerts(self, resolved_at: datetime | None = None) -> int:
        """Resolve all currently open alerts in persistence."""
        conn = get_connection(self.db_path)
        from datetime import UTC
        res_time = (resolved_at or datetime.now(UTC)).isoformat()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE alerts
                    SET resolved_at = ?
                    WHERE resolved_at IS NULL;
                    """,
                    (res_time,),
                )
                return cursor.rowcount
        finally:
            conn.close()

    def resolve_alert(self, alert_id: str, resolved_at: datetime | None = None) -> bool:
        """Resolve a specific open alert by ID."""
        conn = get_connection(self.db_path)
        from datetime import UTC
        res_time = (resolved_at or datetime.now(UTC)).isoformat()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE alerts
                    SET resolved_at = ?
                    WHERE alert_id = ? AND resolved_at IS NULL;
                    """,
                    (res_time, alert_id),
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def clean_duplicate_open_alerts(self) -> int:
        """Resolve older duplicate open alerts, preserving only the newest per zone."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE alerts
                    SET resolved_at = created_at
                    WHERE resolved_at IS NULL
                      AND alert_id NOT IN (
                        SELECT alert_id FROM (
                          SELECT alert_id, ROW_NUMBER() OVER (
                              PARTITION BY alert_type, zone_id ORDER BY created_at DESC
                          ) as rn
                          FROM alerts
                          WHERE resolved_at IS NULL
                        ) WHERE rn = 1
                      );
                    """
                )
                return cursor.rowcount
        finally:
            conn.close()

    def clear_detection_events(self) -> int:
        """Purge detection, dwell, queue, and stock events to reset store telemetry to zero."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM detection_events;")
            row = cursor.fetchone()
            count = int(row[0]) if row else 0
            cursor.execute("DELETE FROM detection_events;")
            cursor.execute("DELETE FROM dwell_events;")
            cursor.execute("DELETE FROM queue_events;")
            cursor.execute("DELETE FROM stock_events;")
            conn.commit()
            return count
        finally:
            conn.close()

    def get_resolved_alerts(self, limit: int = 100) -> list[Alert]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                FROM alerts
                WHERE resolved_at IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                Alert(
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    severity=row["severity"],
                    zone_id=row["zone_id"],
                    message=row["message"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    resolved_at=(
                        datetime.fromisoformat(row["resolved_at"])
                        if row["resolved_at"] is not None
                        else None
                    ),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_all_alerts(self, limit: int = 100) -> list[Alert]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                FROM alerts
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                Alert(
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    severity=row["severity"],
                    zone_id=row["zone_id"],
                    message=row["message"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    resolved_at=(
                        datetime.fromisoformat(row["resolved_at"])
                        if row["resolved_at"] is not None
                        else None
                    ),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_alert_by_id(self, alert_id: str) -> Alert | None:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alert_id, alert_type, severity, zone_id, message, created_at, resolved_at
                FROM alerts
                WHERE alert_id = ?;
                """,
                (alert_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Alert(
                alert_id=row["alert_id"],
                alert_type=row["alert_type"],
                severity=row["severity"],
                zone_id=row["zone_id"],
                message=row["message"],
                created_at=datetime.fromisoformat(row["created_at"]),
                resolved_at=(
                    datetime.fromisoformat(row["resolved_at"])
                    if row["resolved_at"] is not None
                    else None
                ),
            )
        finally:
            conn.close()

    def save_audit_event(self, entry: AuditLogEntry) -> None:
        """Insert operational audit log entry for threshold breach or resolution."""
        conn = get_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO audit_logs (
                        log_id, timestamp, event_type, alert_id, alert_type,
                        severity, zone_id, sku_id, message, facings, cleared_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        entry.log_id,
                        entry.timestamp.isoformat(),
                        entry.event_type,
                        entry.alert_id,
                        entry.alert_type,
                        entry.severity,
                        entry.zone_id,
                        entry.sku_id,
                        entry.message,
                        entry.facings,
                        entry.cleared_reason,
                    ),
                )
        finally:
            conn.close()

    def get_audit_events(
        self,
        limit: int = 100,
        zone_id: str | None = None,
        alert_id: str | None = None,
    ) -> list[AuditLogEntry]:
        """Query recent operational audit trail logs with optional filters."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT log_id, timestamp, event_type, alert_id, alert_type,
                       severity, zone_id, sku_id, message, facings, cleared_reason
                FROM audit_logs
            """
            conditions: list[str] = []
            params: list[object] = []

            if zone_id is not None:
                conditions.append("zone_id = ?")
                params.append(zone_id)
            if alert_id is not None:
                conditions.append("alert_id = ?")
                params.append(alert_id)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?;"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                AuditLogEntry(
                    log_id=row["log_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    event_type=row["event_type"],
                    alert_id=row["alert_id"],
                    alert_type=row["alert_type"],
                    severity=row["severity"],
                    zone_id=row["zone_id"],
                    sku_id=row["sku_id"],
                    message=row["message"],
                    facings=row["facings"] if row["facings"] is not None else None,
                    cleared_reason=row["cleared_reason"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_recent_detection_events(
        self, limit: int = 100, zone_id: str | None = None
    ) -> list[DetectionEvent]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            if zone_id is not None:
                cursor.execute(
                    """
                    SELECT event_id, track_id, timestamp,
                           bbox_x, bbox_y, bbox_w, bbox_h,
                           zone_id, event_type
                    FROM detection_events
                    WHERE zone_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (zone_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, track_id, timestamp,
                           bbox_x, bbox_y, bbox_w, bbox_h,
                           zone_id, event_type
                    FROM detection_events
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                DetectionEvent(
                    event_id=row["event_id"],
                    track_id=row["track_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    bbox=(row["bbox_x"], row["bbox_y"], row["bbox_w"], row["bbox_h"]),
                    zone_id=row["zone_id"],
                    event_type=row["event_type"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_recent_dwell_events(
        self, limit: int = 100, zone_id: str | None = None
    ) -> list[DwellEvent]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            if zone_id is not None:
                cursor.execute(
                    """
                    SELECT event_id, zone_id, track_id, start_ts, end_ts, duration_sec
                    FROM dwell_events
                    WHERE zone_id = ?
                    ORDER BY start_ts DESC
                    LIMIT ?;
                    """,
                    (zone_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, zone_id, track_id, start_ts, end_ts, duration_sec
                    FROM dwell_events
                    ORDER BY start_ts DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                DwellEvent(
                    event_id=row["event_id"],
                    zone_id=row["zone_id"],
                    track_id=row["track_id"],
                    start_ts=datetime.fromisoformat(row["start_ts"]),
                    end_ts=datetime.fromisoformat(row["end_ts"]),
                    duration_sec=float(row["duration_sec"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_recent_queue_events(
        self, limit: int = 100, counter_id: str | None = None
    ) -> list[QueueEvent]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            if counter_id is not None:
                cursor.execute(
                    """
                    SELECT event_id, counter_id, timestamp, queue_length, avg_wait_est_sec,
                           predicted_queue_length, predicted_wait_sec
                    FROM queue_events
                    WHERE counter_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (counter_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, counter_id, timestamp, queue_length, avg_wait_est_sec,
                           predicted_queue_length, predicted_wait_sec
                    FROM queue_events
                    ORDER BY timestamp DESC
                    LIMIT ?;
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                QueueEvent(
                    event_id=row["event_id"],
                    counter_id=row["counter_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    queue_length=int(row["queue_length"]),
                    avg_wait_est_sec=(
                        float(row["avg_wait_est_sec"])
                        if row["avg_wait_est_sec"] is not None
                        else None
                    ),
                    predicted_queue_length=(
                        int(row["predicted_queue_length"])
                        if "predicted_queue_length" in row
                        and row["predicted_queue_length"] is not None
                        else None
                    ),
                    predicted_wait_sec=(
                        float(row["predicted_wait_sec"])
                        if "predicted_wait_sec" in row and row["predicted_wait_sec"] is not None
                        else None
                    ),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_hourly_queue_baseline(self, counter_id: str, hour_of_day: int) -> float | None:
        """Calculate historical average queue length for this counter and hour of day."""
        conn = get_connection(self.db_path)
        try:
            cursor = conn.cursor()
            # strftime('%H', timestamp) matches the 2-digit hour 00-23
            hour_str = f"{hour_of_day:02d}"
            cursor.execute(
                """
                SELECT AVG(queue_length) as avg_q
                FROM queue_events
                WHERE counter_id = ? AND strftime('%H', timestamp) = ?;
                """,
                (counter_id, hour_str),
            )
            row = cursor.fetchone()
            if row and row["avg_q"] is not None:
                return float(row["avg_q"])
            return None
        finally:
            conn.close()
