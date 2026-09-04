import os
from pathlib import Path

ENV_PATH = Path(".env")


def read_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    """Parse .env file into key-value dictionary."""
    env_vars: dict[str, str] = {}
    if not path.is_file():
        return env_vars

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                clean_key = key.strip()
                clean_val = val.strip().strip("\"'")
                env_vars[clean_key] = clean_val
    return env_vars


def write_env_file(updates: dict[str, str], path: Path = ENV_PATH) -> dict[str, str]:
    """Update or append environment variables in .env file while preserving structure."""
    existing_lines: list[str] = []
    if path.is_file():
        with path.open("r", encoding="utf-8") as f:
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

    with path.open("w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return read_env_file(path)


def is_debug_mode() -> bool:
    """Check if debug mode is active from env or .env file."""
    env_vars = read_env_file()
    debug_val = os.environ.get("DEBUG_MODE", env_vars.get("DEBUG_MODE", "false"))
    return debug_val.lower() in ("true", "1", "yes")
