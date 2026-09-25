from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api.env_manager as em
from api.env_manager import read_env_file, write_env_file
from api.main import app

pytestmark = pytest.mark.slice_8


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_env = tmp_path / ".env"
    temp_env.write_text("DEBUG_MODE=true\n", encoding="utf-8")
    monkeypatch.setattr("api.env_manager.get_default_env_path", lambda: temp_env)
    em._cached_env_mtime = -1.0
    em._cached_env = {}
    em._cached_env_path = None


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


def test_update_system_environment_when_debug_disabled_succeeds() -> None:
    # Ensure debug mode is disabled on server
    write_env_file({"DEBUG_MODE": "false"})
    try:
        # Updating system .env is allowed without debug mode
        resp = client.put(
            "/system/env",
            json={"variables": {"CAMERA_SOURCE": "rtsp://192.168.1.50:8080"}},
        )
        assert resp.status_code == 200
        assert resp.json()["variables"]["CAMERA_SOURCE"] == "rtsp://192.168.1.50:8080"
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


def test_get_and_update_zones(tmp_path: Path) -> None:
    import api.dependencies as dep

    temp_cfg = tmp_path / "config.yaml"
    temp_cfg.write_text("zones: []\n", encoding="utf-8")
    app.dependency_overrides[dep.get_config_path] = lambda: temp_cfg

    dep._cached_cfg = None
    dep._cached_cfg_mtime = -1.0
    dep._cached_cfg_path = None

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
        app.dependency_overrides.pop(dep.get_config_path, None)


def test_zones_resolution_scaling_and_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import api.dependencies as dep
    temp_cfg = tmp_path / "config.yaml"
    temp_cfg.write_text(
        "camera:\n"
        "  source: '0'\n"
        "calibration_width: 640\n"
        "calibration_height: 480\n"
        "low_stock_confidence_threshold: 0.6\n"
        "queue_congestion_length: 3\n"
        "zones:\n"
        "  - zone_id: test_box\n"
        "    zone_type: shelf\n"
        "    polygon:\n"
        "      - [100, 100]\n"
        "      - [200, 100]\n"
        "      - [200, 200]\n"
        "      - [100, 200]\n"
        "    label: Test Box\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(temp_cfg))
    app.dependency_overrides[dep.get_config_path] = lambda: temp_cfg

    dep._cached_cfg = None
    dep._cached_cfg_mtime = -1.0
    dep._cached_cfg_path = None

    try:
        # 1. Unscaled GET returns 640x480 coordinates and calibration headers
        resp = client.get("/system/zones")
        assert resp.status_code == 200
        assert resp.headers["X-Calibration-Width"] == "640"
        assert resp.headers["X-Calibration-Height"] == "480"
        zones = resp.json()
        assert zones[0]["polygon"][0] == [100, 100]

        # 2. Scaled GET (1280x960, exactly 2x) scales points to 200, 200
        resp_scaled = client.get("/system/zones?frame_w=1280&frame_h=960")
        assert resp_scaled.status_code == 200
        assert resp_scaled.headers["X-Calibration-Width"] == "1280"
        assert resp_scaled.headers["X-Calibration-Height"] == "960"
        scaled_zones = resp_scaled.json()
        assert scaled_zones[0]["polygon"][0] == [200, 200]
        assert scaled_zones[0]["polygon"][2] == [400, 400]

        # 3. Update zones calibrated at 1280x720
        write_env_file({"DEBUG_MODE": "true"})
        update_payload = {
            "calibration_width": 1280,
            "calibration_height": 720,
            "zones": [
                {
                    "zone_id": "hd_shelf",
                    "zone_type": "shelf",
                    "polygon": [[100, 200], [400, 200], [400, 500], [100, 500]],
                    "label": "HD Shelf",
                }
            ],
        }
        put_resp = client.put("/system/zones", json=update_payload)
        assert put_resp.status_code == 200
        assert put_resp.headers["X-Calibration-Width"] == "1280"
        assert put_resp.headers["X-Calibration-Height"] == "720"

        # 4. GET at 1280x720 returns 1:1 scale
        dep._cached_cfg = None
        dep._cached_cfg_mtime = -1.0
        resp_hd = client.get("/system/zones?frame_w=1280&frame_h=720")
        assert resp_hd.status_code == 200
        hd_zones = resp_hd.json()
        assert hd_zones[0]["polygon"][0] == [100, 200]
    finally:
        app.dependency_overrides.pop(dep.get_config_path, None)


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
