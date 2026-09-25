import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import app
from vision.camera_mesh import CameraMesh, CameraNode

pytestmark = pytest.mark.slice_11
def test_camera_node_manual_frame_update() -> None:
    node = CameraNode(
        camera_id="cam_test_1",
        source="rtsp://dummy/test",
        role="shelf",
        label="Shelf Camera",
        auto_start=False,
    )
    assert node.camera_id == "cam_test_1"
    assert node.is_connected is False

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    node.update_frame(dummy_frame, 640, 480)

    is_conn, frame, w, h = node.get_frame()
    assert is_conn is True
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert w == 640
    assert h == 480

    cfg = node.to_config()
    assert cfg.camera_id == "cam_test_1"
    assert cfg.role == "shelf"
    assert cfg.is_connected is True

    node.stop()


def test_camera_mesh_topology_lifecycle() -> None:
    mesh = CameraMesh()
    mesh.register_camera(
        camera_id="cam_entrance",
        source="rtsp://demo/entrance",
        role="entrance",
        label="Main Door",
        auto_start=False,
    )
    mesh.register_camera(
        camera_id="cam_checkout",
        source="rtsp://demo/checkout",
        role="checkout",
        label="Billing Counter",
        auto_start=False,
    )

    summary = mesh.get_summary()
    assert summary.total_cameras == 2
    assert summary.active_cameras == 0

    # Provide synthetic frames to nodes
    frame1 = np.full((240, 320, 3), 100, dtype=np.uint8)
    frame2 = np.full((240, 320, 3), 200, dtype=np.uint8)
    mesh.get_camera("cam_entrance").update_frame(frame1)  # type: ignore[union-attr]
    mesh.get_camera("cam_checkout").update_frame(frame2)  # type: ignore[union-attr]

    summary_after = mesh.get_summary()
    assert summary_after.active_cameras == 2

    # Generate multi-cam mosaic
    mosaic = mesh.generate_mosaic(grid_cols=2, mosaic_width=800, mosaic_height=400)
    assert mosaic.shape == (400, 800, 3)

    # Unregister
    removed = mesh.unregister_camera("cam_entrance")
    assert removed is True
    assert mesh.get_camera("cam_entrance") is None
    assert mesh.get_summary().total_cameras == 1

    mesh.close()


def test_camera_mesh_api_endpoints() -> None:
    client = TestClient(app)

    # 1. Register new mesh camera
    reg_resp = client.post(
        "/video/cameras",
        json={
            "camera_id": "cam_aisle_9",
            "source": "rtsp://store-camera.local/stream1",
            "role": "shelf",
            "label": "Snack Aisle 9",
        },
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert reg_data["camera_id"] == "cam_aisle_9"
    assert reg_data["role"] == "shelf"

    # 2. List mesh cameras
    list_resp = client.get("/video/cameras")
    assert list_resp.status_code == 200
    mesh_data = list_resp.json()
    assert mesh_data["total_cameras"] >= 1
    cam_ids = [c["camera_id"] for c in mesh_data["cameras"]]
    assert "cam_aisle_9" in cam_ids

    # 3. Snapshot with mosaic mode
    snap_mosaic_resp = client.get("/video/snapshot?camera_id=mosaic")
    assert snap_mosaic_resp.status_code == 200
    assert snap_mosaic_resp.headers["content-type"] == "image/jpeg"
    assert len(snap_mosaic_resp.content) > 100

    # 4. Status for specific camera
    status_resp = client.get("/video/status?camera_id=cam_aisle_9")
    assert status_resp.status_code == 200
    assert "source" in status_resp.json()

    # 5. Unregister camera
    del_resp = client.delete("/video/cameras/cam_aisle_9")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"

    # 6. Unregister non-existent returns 404
    del_404 = client.delete("/video/cameras/cam_nonexistent")
    assert del_404.status_code == 404
