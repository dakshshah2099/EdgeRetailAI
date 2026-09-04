from pathlib import Path

from fastapi.testclient import TestClient

from api.env_manager import read_env_file, write_env_file
from api.main import app

client = TestClient(app)


def test_env_file_parser_and_writer(tmp_path: Path) -> None:
    test_env = tmp_path / ".env"
    test_env.write_text(
        "DEBUG_MODE=true\nCAMERA_SOURCE=0\n# comment\nPORT=8000\n",
        encoding="utf-8",
    )

    vars_dict = read_env_file(test_env)
    assert vars_dict["DEBUG_MODE"] == "true"
    assert vars_dict["CAMERA_SOURCE"] == "0"
    assert vars_dict["PORT"] == "8000"

    # Update
    updated = write_env_file({"CAMERA_SOURCE": "rtsp://1.2.3.4", "NEW_VAR": "hello"}, test_env)
    assert updated["CAMERA_SOURCE"] == "rtsp://1.2.3.4"
    assert updated["NEW_VAR"] == "hello"
    assert updated["PORT"] == "8000"


def test_get_system_environment() -> None:
    resp = client.get("/system/env")
    assert resp.status_code == 200
    data = resp.json()
    assert "debug_mode" in data
    assert isinstance(data["variables"], dict)


def test_update_system_environment_when_debug_enabled() -> None:
    # Ensure debug mode is enabled
    client.put("/system/env", json={"variables": {"DEBUG_MODE": "true"}})

    # Update camera source and threshold
    payload = {"variables": {"CAMERA_SOURCE": "0", "QUEUE_CONGESTION_LENGTH": "5"}}
    resp = client.put("/system/env", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["variables"]["CAMERA_SOURCE"] == "0"
    assert data["variables"]["QUEUE_CONGESTION_LENGTH"] == "5"


def test_toggle_debug_endpoint() -> None:
    initial = client.get("/system/env").json()["debug_mode"]
    toggle_resp = client.post("/system/toggle-debug")
    assert toggle_resp.status_code == 200
    new_mode = toggle_resp.json()["debug_mode"]
    assert new_mode == (not initial)

    # Revert back to true for testing
    client.post("/system/toggle-debug")


def test_get_and_update_zones() -> None:
    # Backup original config.yaml
    cfg_file = Path("config.yaml")
    orig_content = cfg_file.read_text(encoding="utf-8") if cfg_file.is_file() else ""

    try:
        # Ensure debug mode enabled
        client.put("/system/env", json={"variables": {"DEBUG_MODE": "true"}})

        resp = client.get("/system/zones")
        assert resp.status_code == 200
        zones = resp.json()
        assert isinstance(zones, list)

        # Update zones
        test_zones = [
            {
                "zone_id": "test_entrance",
                "zone_type": "entry_exit",
                "polygon": [[0, 0], [1000, 0], [1000, 800], [0, 800]],
                "label": "Test Entrance",
            }
        ]
        put_resp = client.put("/system/zones", json={"zones": test_zones})
        assert put_resp.status_code == 200
        assert len(put_resp.json()) == 1
        assert put_resp.json()[0]["zone_id"] == "test_entrance"
    finally:
        # Restore original config.yaml
        if orig_content:
            cfg_file.write_text(orig_content, encoding="utf-8")
