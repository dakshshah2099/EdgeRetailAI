from pathlib import Path

import pytest
from central.store_registry import StoreConfig, load_store_registry


def test_load_store_registry_valid_dict_format(tmp_path: Path) -> None:
    yaml_content = """
stores:
  - store_id: "store_1"
    name: "Downtown Flagship"
    api_base_url: "http://127.0.0.1:8000"
  - store_id: "store_2"
    name: "Uptown Mall"
    api_base_url: "https://uptown.retail.example.com"
"""
    config_file = tmp_path / "stores.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    stores = load_store_registry(config_file)
    assert len(stores) == 2
    assert stores[0] == StoreConfig(
        store_id="store_1",
        name="Downtown Flagship",
        api_base_url="http://127.0.0.1:8000",
    )
    assert stores[1] == StoreConfig(
        store_id="store_2",
        name="Uptown Mall",
        api_base_url="https://uptown.retail.example.com",
    )


def test_load_store_registry_valid_list_format(tmp_path: Path) -> None:
    yaml_content = """
- store_id: "store_solo"
  name: "Airport Kiosk"
  api_base_url: "http://10.0.0.5:8080"
"""
    config_file = tmp_path / "stores_list.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    stores = load_store_registry(config_file)
    assert len(stores) == 1
    assert stores[0].store_id == "store_solo"


def test_load_store_registry_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_store_registry(tmp_path / "non_existent.yaml")


def test_load_store_registry_invalid_yaml_syntax(tmp_path: Path) -> None:
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("stores: [broken yaml", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to parse YAML"):
        load_store_registry(config_file)


def test_load_store_registry_non_dict_non_list(tmp_path: Path) -> None:
    config_file = tmp_path / "scalar.yaml"
    config_file.write_text("just a string", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a list of stores"):
        load_store_registry(config_file)


def test_load_store_registry_missing_fields(tmp_path: Path) -> None:
    yaml_content = """
stores:
  - store_id: "store_bad"
    name: "Incomplete Store"
"""
    config_file = tmp_path / "missing.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="missing required field 'api_base_url'"):
        load_store_registry(config_file)


def test_load_store_registry_invalid_url_protocol(tmp_path: Path) -> None:
    yaml_content = """
stores:
  - store_id: "store_ftp"
    name: "FTP Store"
    api_base_url: "ftp://127.0.0.1:21"
"""
    config_file = tmp_path / "invalid_url.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="must start with http:// or https://"):
        load_store_registry(config_file)
