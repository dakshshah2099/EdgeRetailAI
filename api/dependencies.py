from datetime import datetime
from pathlib import Path

from schemas import AppConfig, load_config
from storage.repository import EventRepository


def get_db_path() -> Path:
    """Return default database path for the repository."""
    return Path("retail.db")


def get_repository() -> EventRepository:
    """FastAPI dependency for accessing EventRepository."""
    return EventRepository(get_db_path())


def get_app_config(config_path: str | Path = "config.yaml") -> AppConfig | None:
    """Load and return application configuration if present."""
    path = Path(config_path)
    if path.is_file():
        try:
            return load_config(path)
        except Exception:
            return None
    return None


def get_default_frame_dimensions(config_path: str | Path = "config.yaml") -> tuple[int, int]:
    """Derive default frame width and height from configuration or zones."""
    cfg = get_app_config(config_path)
    if cfg and cfg.zones:
        max_x = max((x for z in cfg.zones for x, _ in z.polygon), default=640)
        max_y = max((y for z in cfg.zones for _, y in z.polygon), default=480)
        # Ensure frame dimensions at least bound configured zone polygons
        width = max(640, int(max_x))
        height = max(480, int(max_y))
        return width, height
    return 640, 480


def is_timestamp_ge(event_ts: datetime, since_ts: datetime) -> bool:
    """Compare event_ts >= since_ts handling both tz-aware and tz-naive timestamps."""
    if event_ts.tzinfo is not None and since_ts.tzinfo is None:
        since_ts = since_ts.replace(tzinfo=event_ts.tzinfo)
    elif event_ts.tzinfo is None and since_ts.tzinfo is not None:
        event_ts = event_ts.replace(tzinfo=since_ts.tzinfo)
    return event_ts >= since_ts
