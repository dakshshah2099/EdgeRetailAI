from pathlib import Path
from typing import Any

import yaml

from core.schemas import StoreConfig

DEFAULT_STORES_YAML = """stores:
  - store_id: "store_downtown"
    name: "Downtown Flagship"
    api_base_url: "http://127.0.0.1:8000"

  - store_id: "store_suburban"
    name: "Suburban Mall"
    api_base_url: "http://127.0.0.1:8001"

  - store_id: "store_airport"
    name: "Terminal 2 Kiosk"
    api_base_url: "http://127.0.0.1:8002"
"""

__all__ = [
    "StoreConfig",
    "add_store_to_registry",
    "ensure_default_stores",
    "load_store_registry",
    "remove_store_from_registry",
    "resolve_store_config_path",
    "save_store_registry",
]


def ensure_default_stores(path: str | Path) -> Path:
    """Ensure stores registry file exists and is populated with default configuration."""
    config_path = Path(path)
    if not config_path.is_file() or config_path.stat().st_size == 0:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(DEFAULT_STORES_YAML, encoding="utf-8")
    return config_path


def load_store_registry(path: str | Path) -> list[StoreConfig]:
    """Load known stores from stores.yaml. Fail loudly on malformed config,
    same pattern as Slice 0's load_config().
    """
    config_path = Path(path)
    if not config_path.is_file():
        if config_path.name == "stores.yaml":
            ensure_default_stores(config_path)
        else:
            raise FileNotFoundError(f"Store registry file not found: {path}")

    if config_path.stat().st_size == 0:
        ensure_default_stores(config_path)

    with config_path.open("r", encoding="utf-8") as f:
        try:
            raw_data: Any = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML from {path}: {exc}") from exc

    raw_stores: list[Any]
    if isinstance(raw_data, dict):
        if "stores" not in raw_data:
            raise ValueError(
                f"Store registry dictionary at {path} must contain a 'stores' list key"
            )
        raw_stores = raw_data["stores"]
    elif isinstance(raw_data, list):
        raw_stores = raw_data
    else:
        raise ValueError(
            f"Store registry file at {path} must contain a list of stores or a "
            "dictionary with a 'stores' key"
        )

    if not isinstance(raw_stores, list):
        raise ValueError(f"'stores' key at {path} must be a list of store objects")

    configs: list[StoreConfig] = []
    for idx, item in enumerate(raw_stores):
        if not isinstance(item, dict):
            raise ValueError(f"Store entry #{idx} in {path} must be a mapping/dict")

        for req_field in ("store_id", "name", "api_base_url"):
            if req_field not in item or not str(item[req_field]).strip():
                raise ValueError(
                    f"Store entry #{idx} in {path} is missing required field '{req_field}'"
                )

        store_id = str(item["store_id"]).strip()
        name = str(item["name"]).strip()
        api_base_url = str(item["api_base_url"]).strip()

        if not (api_base_url.startswith("http://") or api_base_url.startswith("https://")):
            raise ValueError(
                f"Store entry '{store_id}' has invalid api_base_url '{api_base_url}': "
                "must start with http:// or https://"
            )

        configs.append(
            StoreConfig(
                store_id=store_id,
                name=name,
                api_base_url=api_base_url,
            )
        )

    return configs


def resolve_store_config_path(path: str | Path = "stores.yaml") -> Path:
    """Resolve the store configuration file path across working directories."""
    config_path = Path(path)
    if config_path.is_file():
        return config_path
    backend_alt = Path(__file__).resolve().parent.parent / config_path
    if backend_alt.is_file():
        return backend_alt
    if not config_path.is_absolute() and len(config_path.parts) == 1:
        backend_dir = Path(__file__).resolve().parent.parent
        if backend_dir.is_dir():
            return backend_dir / config_path.name
    return config_path


def save_store_registry(path: str | Path, stores: list[StoreConfig]) -> None:
    """Save the list of stores back to stores.yaml."""
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "stores": [
            {
                "store_id": s.store_id,
                "name": s.name,
                "api_base_url": s.api_base_url,
            }
            for s in stores
        ]
    }
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)


def add_store_to_registry(path: str | Path, store: StoreConfig) -> list[StoreConfig]:
    """Add a new store configuration to the registry and persist to disk.

    Validates that store_id is unique and fields are non-empty.
    """
    config_path = resolve_store_config_path(path)
    current_stores = load_store_registry(config_path) if config_path.is_file() else []

    store_id = store.store_id.strip()
    name = store.name.strip()
    api_base_url = store.api_base_url.strip().rstrip("/")

    if not store_id:
        raise ValueError("Store ID cannot be empty")
    if not name:
        raise ValueError("Store name cannot be empty")
    if not (api_base_url.startswith("http://") or api_base_url.startswith("https://")):
        raise ValueError("api_base_url must start with http:// or https://")

    if any(s.store_id == store_id for s in current_stores):
        raise ValueError(f"Store with ID '{store_id}' already exists in registry")

    clean_store = StoreConfig(
        store_id=store_id,
        name=name,
        api_base_url=api_base_url,
    )
    current_stores.append(clean_store)
    save_store_registry(config_path, current_stores)
    return current_stores


def remove_store_from_registry(
    path: str | Path, store_id: str
) -> tuple[list[StoreConfig], StoreConfig]:
    """Remove a store configuration by store_id and persist to disk.

    Raises KeyError if store_id is not found.
    """
    config_path = resolve_store_config_path(path)
    current_stores = load_store_registry(config_path)

    target_id = store_id.strip()
    removed: StoreConfig | None = None
    remaining: list[StoreConfig] = []

    for s in current_stores:
        if s.store_id == target_id:
            removed = s
        else:
            remaining.append(s)

    if removed is None:
        raise KeyError(f"Store with ID '{store_id}' not found in registry")

    save_store_registry(config_path, remaining)
    return remaining, removed
