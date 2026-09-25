from pathlib import Path

import pytest

from central.store_registry import (
    StoreConfig,
    add_store_to_registry,
    load_store_registry,
    remove_store_from_registry,
    save_store_registry,
)

pytestmark = pytest.mark.slice_11
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


def test_save_and_add_store_to_registry(tmp_path: Path) -> None:
    config_file = tmp_path / "stores.yaml"
    initial_stores = [
        StoreConfig(
            store_id="store_alpha",
            name="Alpha Mall",
            api_base_url="http://127.0.0.1:8000",
        )
    ]
    save_store_registry(config_file, initial_stores)

    loaded = load_store_registry(config_file)
    assert len(loaded) == 1
    assert loaded[0].store_id == "store_alpha"

    new_store = StoreConfig(
        store_id="store_beta",
        name="Beta Flagship",
        api_base_url="http://127.0.0.1:8001/",
    )
    updated = add_store_to_registry(config_file, new_store)
    assert len(updated) == 2
    assert updated[1].store_id == "store_beta"
    assert updated[1].api_base_url == "http://127.0.0.1:8001"

    # Reload from disk to ensure persistence
    reloaded = load_store_registry(config_file)
    assert len(reloaded) == 2


def test_add_store_to_registry_duplicate_id(tmp_path: Path) -> None:
    config_file = tmp_path / "stores.yaml"
    store1 = StoreConfig(
        store_id="store_dup",
        name="Dup 1",
        api_base_url="http://127.0.0.1:8000",
    )
    add_store_to_registry(config_file, store1)

    store2 = StoreConfig(
        store_id="store_dup",
        name="Dup 2",
        api_base_url="http://127.0.0.1:8001",
    )
    with pytest.raises(ValueError, match="already exists"):
        add_store_to_registry(config_file, store2)


def test_add_store_to_registry_invalid_fields(tmp_path: Path) -> None:
    config_file = tmp_path / "stores.yaml"
    with pytest.raises(ValueError, match="Store ID cannot be empty"):
        add_store_to_registry(
            config_file,
            StoreConfig(store_id="  ", name="Test", api_base_url="http://127.0.0.1:8000"),
        )

    with pytest.raises(ValueError, match="Store name cannot be empty"):
        add_store_to_registry(
            config_file,
            StoreConfig(store_id="valid_id", name="  ", api_base_url="http://127.0.0.1:8000"),
        )

    with pytest.raises(ValueError, match="api_base_url must start with"):
        add_store_to_registry(
            config_file,
            StoreConfig(store_id="valid_id", name="Valid", api_base_url="ftp://127.0.0.1:8000"),
        )


def test_remove_store_from_registry(tmp_path: Path) -> None:
    config_file = tmp_path / "stores.yaml"
    store1 = StoreConfig(store_id="s1", name="Store 1", api_base_url="http://127.0.0.1:8001")
    store2 = StoreConfig(store_id="s2", name="Store 2", api_base_url="http://127.0.0.1:8002")
    add_store_to_registry(config_file, store1)
    add_store_to_registry(config_file, store2)

    remaining, removed = remove_store_from_registry(config_file, "s1")
    assert len(remaining) == 1
    assert remaining[0].store_id == "s2"
    assert removed.store_id == "s1"

    # Reload from disk
    reloaded = load_store_registry(config_file)
    assert len(reloaded) == 1
    assert reloaded[0].store_id == "s2"


def test_remove_store_not_found(tmp_path: Path) -> None:
    config_file = tmp_path / "stores.yaml"
    store1 = StoreConfig(store_id="s1", name="Store 1", api_base_url="http://127.0.0.1:8001")
    add_store_to_registry(config_file, store1)

    with pytest.raises(KeyError, match="not found"):
        remove_store_from_registry(config_file, "non_existent_id")

