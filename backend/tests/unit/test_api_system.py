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


def test_update_system_environment_when_debug_disabled_rejects_bypass() -> None:
    # Ensure debug mode is disabled on server
    write_env_file({"DEBUG_MODE": "false"})
    try:
        # Attacker attempts to bypass guard by sending DEBUG_MODE=true in payload
        resp = client.put(
            "/system/env",
            json={"variables": {"DEBUG_MODE": "true", "CAMERA_SOURCE": "malicious_stream"}},
        )
        assert resp.status_code == 403
        assert "Debug mode is disabled" in resp.json()["detail"]
    finally:
        # Restore debug mode to true
        write_env_file({"DEBUG_MODE": "true"})


def test_update_system_environment_when_debug_enabled() -> None:
    # Ensure debug mode is enabled on server
    write_env_file({"DEBUG_MODE": "true"})

    # Update camera source and threshold
    payload = {"variables": {"CAMERA_SOURCE": "0", "QUEUE_CONGESTION_LENGTH": "5"}}
    resp = client.put("/system/env", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["variables"]["CAMERA_SOURCE"] == "0"
    assert data["variables"]["QUEUE_CONGESTION_LENGTH"] == "5"


def test_toggle_debug_endpoint() -> None:
    # 1. When debug mode is OFF, unauthorized toggle without token is rejected with 403
    write_env_file({"DEBUG_MODE": "false"})
    unauth_resp = client.post("/system/toggle-debug")
    assert unauth_resp.status_code == 403
    assert "Valid X-Debug-Token header required" in unauth_resp.json()["detail"]

    # 2. Invalid token is also rejected with 403
    bad_token_resp = client.post(
        "/system/toggle-debug",
        headers={"X-Debug-Token": "wrong-token"},
    )
    assert bad_token_resp.status_code == 403

    # 3. Valid token enables debug mode
    auth_resp = client.post(
        "/system/toggle-debug",
        headers={"X-Debug-Token": "retail-edge-debug-secret"},
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["debug_mode"] is True

    # 4. Once debug mode is active, disabling it is permitted
    disable_resp = client.post("/system/toggle-debug")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["debug_mode"] is False

    # Restore debug mode to true
    write_env_file({"DEBUG_MODE": "true"})


def test_get_and_update_zones() -> None:
    from api.dependencies import get_config_path

    cfg_file = get_config_path()
    orig_content = cfg_file.read_text(encoding="utf-8") if cfg_file.is_file() else ""
    created_new = not cfg_file.is_file()

    try:
        # Ensure debug mode enabled
        write_env_file({"DEBUG_MODE": "true"})

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
        # Restore original config
        if orig_content:
            cfg_file.write_text(orig_content, encoding="utf-8")
        elif created_new and cfg_file.is_file():
            cfg_file.unlink()


def test_root_endpoint_redirects_or_returns_json() -> None:
    resp = client.get("/", follow_redirects=False)
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    dist_index = repo_root / "frontend" / "dist" / "index.html"
    if not dist_index.is_file():
        dist_index = repo_root / "dashboard" / "dist" / "index.html"

    if dist_index.is_file():
        assert resp.status_code in (307, 302, 301)
        assert resp.headers["location"] == "/app/"
    else:
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

