import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.routes.video import frame_streamer
from api.stream_manager import (
    StreamManager,
    draw_tracked_overlay,
    draw_zones_overlay,
    generate_fallback_frame,
)
from vision.tracker import TrackedDetection


@pytest.mark.e2e
def test_stream_manager_video_ingestion_and_streaming(
    monkeypatch: pytest.MonkeyPatch,
    e2e_client: TestClient,
    e2e_config_file: Path,
) -> None:
    """E2E test: Ingest real MP4 video into StreamManager, verify thread concurrency,

    frame extraction, overlays, and HTTP streaming endpoints.
    """
    video_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample_video.mp4"
    assert video_path.is_file(), f"Sample video not found at {video_path}"

    monkeypatch.setenv("CAMERA_SOURCE", str(video_path))
    monkeypatch.setenv("CONFIG_PATH", str(e2e_config_file))
    monkeypatch.setenv("YOLO_INFERENCE_FPS", "10")

    # Instantiate dedicated StreamManager for this test
    manager = StreamManager()
    monkeypatch.setattr("api.routes.video.stream_manager", manager)
    monkeypatch.setattr("api.stream_manager.stream_manager", manager)

    try:
        manager.start()
        assert manager._capture_thread is not None and manager._capture_thread.is_alive()
        assert manager._inference_thread is not None and manager._inference_thread.is_alive()

        # Wait for frame capture to ingest from video file
        start_t = time.monotonic()
        while time.monotonic() - start_t < 3.0:
            is_conn, frame, _, w, h = manager.get_latest_frame()
            if is_conn and frame is not None and manager._frame_seq > 0:
                break
            time.sleep(0.05)

        is_conn, frame, tracked, width, height = manager.get_latest_frame()
        assert is_conn is True
        assert frame is not None
        assert width > 0
        assert height > 0

        # Verify overlay rendering
        annotated_zones = draw_zones_overlay(frame, config_path=str(e2e_config_file))
        assert annotated_zones.shape == frame.shape

        synthetic_track = TrackedDetection(
            track_id="trk_live_1", bbox=(50, 50, 40, 80), confidence=0.95
        )
        annotated_tracks = draw_tracked_overlay(frame, [synthetic_track])
        assert annotated_tracks.shape == frame.shape

        # Verify /video/status API endpoint
        resp_status = e2e_client.get("/video/status")
        assert resp_status.status_code == 200
        status_data = resp_status.json()
        assert status_data["is_connected"] is True
        assert status_data["width"] == width
        assert status_data["height"] == height
        assert status_data["zones_count"] == 4

        # Verify /video/snapshot API endpoint
        resp_snap = e2e_client.get("/video/snapshot")
        assert resp_snap.status_code == 200
        assert resp_snap.headers["content-type"] == "image/jpeg"
        # JPEG SOI marker (0xFF, 0xD8)
        assert resp_snap.content[:2] == b"\xff\xd8"
        assert len(resp_snap.content) > 200

    finally:
        manager.stop()
        assert manager.camera is None
        if manager._capture_thread:
            assert not manager._capture_thread.is_alive()
        if manager._inference_thread:
            assert not manager._inference_thread.is_alive()


@pytest.mark.e2e
@pytest.mark.anyio
async def test_frame_streamer_mjpeg_chunks() -> None:
    """Verify frame_streamer async generator emits valid multipart MJPEG format."""
    gen = frame_streamer(overlay_zones=False, overlay_detections=False, target_fps=20)
    try:
        chunk = await anext(gen)
        assert b"--frame\r\n" in chunk
        assert b"Content-Type: image/jpeg\r\n" in chunk
        assert b"Content-Length: " in chunk
        # Extract JPEG segment
        header_end = chunk.find(b"\r\n\r\n")
        assert header_end != -1
        jpeg_data = chunk[header_end + 4 :].rstrip(b"\r\n")
        assert jpeg_data[:2] == b"\xff\xd8"
    finally:
        await gen.aclose()


@pytest.mark.e2e
def test_fallback_frame_generation() -> None:
    """Verify fallback frame is rendered when camera disconnects."""
    fallback = generate_fallback_frame(
        "rtsp://admin:secret@10.0.0.1:554/stream", width=640, height=480
    )
    assert fallback.shape == (480, 640, 3)
