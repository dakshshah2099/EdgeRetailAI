from pathlib import Path
from typing import Any

import yaml

from core.schemas import StoreConfig

__all__ = ["StoreConfig", "load_store_registry"]


def load_store_registry(path: str | Path) -> list[StoreConfig]:
    """Load known stores from stores.yaml. Fail loudly on malformed config,
    same pattern as Slice 0's load_config().
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Store registry file not found: {path}")

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
