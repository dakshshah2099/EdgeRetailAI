import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def get_default_env_path() -> Path:
    """Resolve backend .env file path, ensuring root directory is never polluted."""
    if "ENV_PATH" in os.environ:
        return Path(os.environ["ENV_PATH"])
    return ENV_PATH


ENV_PATH = BACKEND_DIR / ".env"

_cached_env: dict[str, str] = {}
_cached_env_mtime: float = -1.0
_cached_env_path: Path | None = None


def read_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse .env file into key-value dictionary with mtime-based in-memory caching."""
    global _cached_env, _cached_env_mtime, _cached_env_path
    target_path = path if path is not None else get_default_env_path()
    try:
        resolved_path = target_path.resolve()
    except OSError:
        return {}

    if not resolved_path.is_file():
        return {}

    try:
        current_mtime = resolved_path.stat().st_mtime
        if _cached_env_path == resolved_path and _cached_env_mtime == current_mtime:
            return dict(_cached_env)
    except OSError:
        pass

    env_vars: dict[str, str] = {}
    with resolved_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                clean_key = key.strip()
                clean_val = val.strip().strip("\"'")
                env_vars[clean_key] = clean_val

    _cached_env = env_vars
    try:
        _cached_env_mtime = resolved_path.stat().st_mtime
    except OSError:
        _cached_env_mtime = -1.0
    _cached_env_path = resolved_path
    return dict(env_vars)


def write_env_file(updates: dict[str, str], path: Path | None = None) -> dict[str, str]:
    """Update or append environment variables in .env file while preserving structure."""
    target_path = path if path is not None else get_default_env_path()
    existing_lines: list[str] = []
    if target_path.is_file():
        with target_path.open("r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                os.environ[key] = str(updates[key])
                continue
        new_lines.append(line)

    # Append any brand new keys
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}\n")
            os.environ[k] = str(v)

    with target_path.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    global _cached_env_mtime
    _cached_env_mtime = -1.0

    return read_env_file(target_path)


def is_debug_mode() -> bool:
    """Check if debug mode is active from env or .env file."""
    env_vars = read_env_file()
    debug_val = os.environ.get("DEBUG_MODE", env_vars.get("DEBUG_MODE", "false"))
    return debug_val.lower() in ("true", "1", "yes")


def get_api_prefix() -> str:
    """Resolve API route prefix, defaulting to /api/v1 (or empty during pytest unless explicit)."""
    import sys

    if "API_PREFIX" in os.environ:
        prefix = os.environ["API_PREFIX"].strip()
        return prefix if (prefix.startswith("/") or not prefix) else f"/{prefix}"
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return ""
    env_vars = read_env_file()
    if "API_PREFIX" in env_vars:
        prefix = env_vars["API_PREFIX"].strip()
        return prefix if (prefix.startswith("/") or not prefix) else f"/{prefix}"
    return "/api/v1"

