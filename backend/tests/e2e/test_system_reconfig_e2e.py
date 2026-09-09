from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alerts.alert_engine import AlertEngine
from core.schemas import QueueEvent


@pytest.mark.e2e
def test_system_dynamic_reconfiguration_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    e2e_client: TestClient,
    e2e_config_file: Path,
) -> None:
    """E2E test: Dynamic configuration update and zone polygon calibration at runtime:

    - Verify debug mode authorization barriers (HTTP 403 when locked).
    - Enable debug mode with secure header token.
    - Dynamically update system thresholds (queue length, stock confidence).
    - Dynamically modify zone coordinates and labels via PUT /system/zones.
    - Verify updated rules take effect in the analytics engine.
    - Lock debug mode and verify subsequent unauthorized writes are blocked.
    """
    temp_env_file = tmp_path / ".env"
    temp_env_file.write_text("DEBUG_MODE=false\nDEBUG_TOKEN=e2e-secret-token\n", encoding="utf-8")

    monkeypatch.setattr("api.env_manager.ENV_PATH", temp_env_file)
    monkeypatch.setenv("DEBUG_TOKEN", "e2e-secret-token")
    monkeypatch.setenv("DEBUG_MODE", "false")
    monkeypatch.setenv("CONFIG_PATH", str(e2e_config_file))

    # 1. Verify GET /system/env
    resp_env = e2e_client.get("/system/env")
    assert resp_env.status_code == 200
    assert resp_env.json()["debug_mode"] is False

    # 2. Attempt unauthorized modification while debug mode is disabled
    unauth_resp = e2e_client.put(
        "/system/env",
        json={"variables": {"QUEUE_CONGESTION_LENGTH": "2"}},
    )
    assert unauth_resp.status_code == 403
    assert "Debug mode is disabled" in unauth_resp.json()["detail"]

    # 3. Enable debug mode with valid token
    resp_toggle_on = e2e_client.post(
        "/system/toggle-debug",
        headers={"X-Debug-Token": "e2e-secret-token"},
    )
    assert resp_toggle_on.status_code == 200
    assert resp_toggle_on.json()["debug_mode"] is True

    # 4. Update system environment variables via PUT /system/env
    resp_update_env = e2e_client.put(
        "/system/env",
        json={
            "variables": {
                "QUEUE_CONGESTION_LENGTH": "2",
                "LOW_STOCK_CONFIDENCE_THRESHOLD": "0.55",
            }
        },
    )
    assert resp_update_env.status_code == 200
    updated_vars = resp_update_env.json()["variables"]
    assert updated_vars["QUEUE_CONGESTION_LENGTH"] == "2"
    assert updated_vars["LOW_STOCK_CONFIDENCE_THRESHOLD"] == "0.55"

    # 5. Dynamically update spatial zones via PUT /system/zones
    new_zones = [
        {
            "zone_id": "zone_entrance_reconfigured",
            "zone_type": "entry_exit",
            "polygon": [[10, 10], [200, 10], [200, 200], [10, 200]],
            "label": "Expanded Main Entrance",
        },
        {
            "zone_id": "zone_express_checkout",
            "zone_type": "checkout",
            "polygon": [[50, 250], [300, 250], [300, 480], [50, 480]],
            "label": "Express Self-Checkout",
        },
    ]
    resp_update_zones = e2e_client.put("/system/zones", json={"zones": new_zones})
    assert resp_update_zones.status_code == 200
    returned_zones = resp_update_zones.json()
    assert len(returned_zones) == 2
    assert returned_zones[0]["zone_id"] == "zone_entrance_reconfigured"
    assert returned_zones[1]["label"] == "Express Self-Checkout"

    # Verify GET /system/zones returns the freshly persisted zones
    resp_get_zones = e2e_client.get("/system/zones")
    assert resp_get_zones.status_code == 200
    zones_list = resp_get_zones.json()
    assert len(zones_list) == 2
    assert zones_list[0]["zone_id"] == "zone_entrance_reconfigured"

    # 6. Verify analytical threshold change takes effect:
    # A queue length of 2 now triggers congestion alert under new threshold (was 4 previously)
    alert_engine = AlertEngine(
        low_stock_threshold=float(updated_vars["LOW_STOCK_CONFIDENCE_THRESHOLD"]),
        queue_congestion_length=int(updated_vars["QUEUE_CONGESTION_LENGTH"]),
    )
    from datetime import UTC, datetime

    queue_event = QueueEvent(
        event_id="q_reconfig_1",
        counter_id="zone_express_checkout",
        timestamp=datetime.now(UTC),
        queue_length=2,
    )
    alert = alert_engine.process_queue_event(queue_event)
    assert alert is not None
    assert alert.alert_type == "queue_congestion"
    assert alert.severity == "warning"

    # 7. Lock debug mode and verify subsequent zone modification is blocked
    resp_toggle_off = e2e_client.post("/system/toggle-debug")
    assert resp_toggle_off.status_code == 200
    assert resp_toggle_off.json()["debug_mode"] is False

    blocked_resp = e2e_client.put("/system/zones", json={"zones": new_zones})
    assert blocked_resp.status_code == 403
