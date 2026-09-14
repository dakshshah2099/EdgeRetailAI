import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.ws import sse_telemetry_generator, ws_manager


def test_websocket_telemetry_handshake_and_ping() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws/telemetry") as websocket:
        # Handshake verification
        handshake = websocket.receive_json()
        assert handshake == {"type": "handshake", "status": "connected"}

        # Client heartbeat ping/pong
        websocket.send_text("ping")
        pong = websocket.receive_json()
        assert pong == {"type": "pong"}

        # Broadcast sync verification
        test_payload = {
            "type": "dwell_points",
            "points": [{"x": 100, "y": 200, "track_id": "trk_1"}],
        }
        ws_manager.broadcast_sync(test_payload)
        received_broadcast = websocket.receive_json()
        assert received_broadcast["type"] == "dwell_points"
        assert len(received_broadcast["points"]) == 1
        assert received_broadcast["points"][0]["track_id"] == "trk_1"


@pytest.mark.anyio
async def test_sse_telemetry_handshake_and_broadcast() -> None:
    gen = sse_telemetry_generator()
    handshake = await anext(gen)
    assert handshake.event == "telemetry"
    assert handshake.data == {"type": "handshake", "status": "connected"}

    # Broadcast event
    test_payload = {
        "type": "dwell_points",
        "points": [{"x": 100, "y": 200, "track_id": "trk_1"}],
    }
    ws_manager.broadcast_sync(test_payload)
    event = await anext(gen)
    assert event.event == "telemetry"
    assert event.data == test_payload

    await gen.aclose()


