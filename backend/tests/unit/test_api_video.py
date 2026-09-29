from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.video import frame_streamer

pytestmark = pytest.mark.slice_8
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


def test_video_cameras_and_primary_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_cfg = tmp_path / "config.yaml"
    test_cfg.write_text(
        "camera:\n  source: 'rtsp://old'\ncameras: []\ncalibration_width: 640\n"
        "calibration_height: 480\nzones: []\nlow_stock_confidence_threshold: 0.6\n"
        "queue_congestion_length: 4\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(test_cfg))

    # Update primary source
    resp = client.put("/video/primary-source", json={"source": "rtsp://new_source"})
    assert resp.status_code == 200
    assert resp.json()["source"] == "rtsp://new_source"
    assert "rtsp://new_source" in test_cfg.read_text(encoding="utf-8")

    # Get primary source
    resp_get = client.get("/video/primary-source")
    assert resp_get.status_code == 200
    assert resp_get.json()["source"] == "rtsp://new_source"

    # Register camera
    resp = client.post(
        "/video/cameras",
        json={"camera_id": "test_cam_2", "source": "0", "role": "shelf", "label": "Shelf Cam"},
    )
    assert resp.status_code == 200
    assert resp.json()["camera_id"] == "test_cam_2"
    assert "test_cam_2" in test_cfg.read_text(encoding="utf-8")

    # Unregister camera
    resp = client.delete("/video/cameras/test_cam_2")
    assert resp.status_code == 200
    assert resp.json()["unregistered"] == "test_cam_2"
    assert "test_cam_2" not in test_cfg.read_text(encoding="utf-8")


def test_update_camera_source_per_camera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_cfg = tmp_path / "config.yaml"
    test_cfg.write_text(
        "camera:\n  source: 'rtsp://primary/initial'\n"
        "cameras:\n"
        "  - camera_id: cam_sec_1\n"
        "    source: '0'\n"
        "    role: shelf\n"
        "    label: Shelf 1\n"
        "calibration_width: 640\ncalibration_height: 480\nzones: []\n"
        "low_stock_confidence_threshold: 0.6\nqueue_congestion_length: 4\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_PATH", str(test_cfg))

    # 1. Update primary camera source via per-camera endpoint
    resp = client.put(
        "/video/cameras/cam_primary/source",
        json={"source": "rtsp://phone:8080/live.sdp"},
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "rtsp://phone:8080/live.sdp"
    assert "rtsp://phone:8080/live.sdp" in test_cfg.read_text(encoding="utf-8")

    # 2. Update secondary mesh camera source
    resp = client.put(
        "/video/cameras/cam_sec_1/source",
        json={"source": "rtsp://192.168.1.105:8554/shelf"},
    )
    assert resp.status_code == 200
    assert resp.json()["camera_id"] == "cam_sec_1"
    assert resp.json()["source"] == "rtsp://192.168.1.105:8554/shelf"
    assert "rtsp://192.168.1.105:8554/shelf" in test_cfg.read_text(encoding="utf-8")

    # 3. 404 for unknown camera
    resp = client.put(
        "/video/cameras/unknown_cam/source",
        json={"source": "rtsp://nowhere"},
    )
    assert resp.status_code == 404

    # 4. 422 for empty source
    resp = client.put(
        "/video/cameras/cam_primary/source",
        json={"source": "   "},
    )
    assert resp.status_code == 422

