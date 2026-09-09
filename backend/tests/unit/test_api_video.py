import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.video import frame_streamer

client = TestClient(app)


def test_video_status_endpoint() -> None:
    resp = client.get("/video/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "source" in data
    assert "is_connected" in data
    assert "width" in data
    assert "height" in data
    assert "zones_count" in data


def test_video_snapshot_endpoint() -> None:
    resp = client.get("/video/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert len(resp.content) > 100  # valid JPEG bytes


@pytest.mark.anyio
async def test_frame_streamer_generator() -> None:
    # Test generator directly to verify multipart frame format without infinite blocking
    gen = frame_streamer(overlay_zones=True, overlay_detections=True, target_fps=30)
    chunk = await anext(gen)
    assert b"--frame\r\n" in chunk
    assert b"Content-Type: image/jpeg\r\n" in chunk
    assert len(chunk) > 100
    await gen.aclose()
