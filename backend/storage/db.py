import sqlite3
from pathlib import Path

_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS detection_events (
        event_id TEXT PRIMARY KEY,
        track_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        bbox_x INTEGER NOT NULL,
        bbox_y INTEGER NOT NULL,
        bbox_w INTEGER NOT NULL,
        bbox_h INTEGER NOT NULL,
        zone_id TEXT,
        event_type TEXT NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_detection_events_ts ON detection_events(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_detection_events_zone ON detection_events(zone_id);",
    """
    CREATE TABLE IF NOT EXISTS dwell_events (
        event_id TEXT PRIMARY KEY,
        zone_id TEXT NOT NULL,
        track_id TEXT NOT NULL,
        start_ts TEXT NOT NULL,
        end_ts TEXT NOT NULL,
        duration_sec REAL NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_dwell_events_zone ON dwell_events(zone_id);",
    "CREATE INDEX IF NOT EXISTS idx_dwell_events_start ON dwell_events(start_ts);",
    """
    CREATE TABLE IF NOT EXISTS stock_events (
        event_id TEXT PRIMARY KEY,
        shelf_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_events_shelf ON stock_events(shelf_id);",
    "CREATE INDEX IF NOT EXISTS idx_stock_events_ts ON stock_events(timestamp);",
    """
    CREATE TABLE IF NOT EXISTS queue_events (
        event_id TEXT PRIMARY KEY,
        counter_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        queue_length INTEGER NOT NULL,
        avg_wait_est_sec REAL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_queue_events_counter ON queue_events(counter_id);",
    "CREATE INDEX IF NOT EXISTS idx_queue_events_ts ON queue_events(timestamp);",
    """
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id TEXT PRIMARY KEY,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        zone_id TEXT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved_at);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);",
]


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create and return a configured SQLite connection with WAL mode and busy timeout."""
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str | Path) -> None:
    """Create tables and indices if they do not exist. Idempotent on application startup."""
    path = Path(db_path)
    if path.parent and str(path.parent) != "." and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(path)
    try:
        with conn:
            for statement in _SCHEMA_STATEMENTS:
                conn.execute(statement)
    finally:
        conn.close()
