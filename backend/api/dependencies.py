import os
from datetime import datetime
from pathlib import Path

from api.env_manager import read_env_file
from core.schemas import AppConfig, load_config
from storage.repository import EventRepository


def get_db_path() -> Path:
    """Return configured or default database path for the repository."""
    env_vars = read_env_file()
    db_str = env_vars.get("DATABASE_PATH") or os.environ.get("DATABASE_PATH", "retail.db")
    p = Path(db_str)
    if not p.is_file() and (Path("backend") / db_str).is_file():
        return Path("backend") / db_str
    return p


def get_config_path() -> Path:
    """Return configured config.yaml path, checking backend/ if executed from repo root."""
    env_vars = read_env_file()
    cfg_str = env_vars.get("CONFIG_PATH") or os.environ.get("CONFIG_PATH", "config.yaml")
    p = Path(cfg_str)
    if not p.is_file() and (Path("backend") / cfg_str).is_file():
        return Path("backend") / cfg_str
    return p


def get_repository() -> EventRepository:
    """FastAPI dependency for accessing EventRepository."""
    return EventRepository(get_db_path())


def get_app_config(config_path: str | Path | None = None) -> AppConfig | None:
    """Load and return application configuration if present."""
    path = get_config_path() if config_path is None else Path(config_path)
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
