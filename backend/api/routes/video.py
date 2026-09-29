import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path as FilePath
from typing import Annotated, Any

import cv2
import numpy as np
import numpy.typing as npt
import yaml
from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from api.dependencies import AppConfigDep, ConfigPathDep
from api.schemas_api import (
    CameraMeshNodeConfig,
    CameraMeshSummary,
    RegisterCameraRequest,
    UnregisterCameraResponse,
)
from api.stream_manager import (
    draw_tracked_overlay,
    draw_zones_overlay,
    generate_fallback_frame,
    resolve_camera_source,
    stream_manager,
)
from vision.camera_mesh import camera_mesh
from vision.rtsp_source import mask_rtsp_credentials
from vision.tracker import TrackedDetection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


def save_mesh_cameras_to_config(cfg_path: FilePath) -> None:
    """Persist all registered non-primary camera nodes into config.yaml."""
    if not cfg_path.is_file():
        return
    with cfg_path.open("r", encoding="utf-8") as f:
        raw_cfg: dict[str, Any] = yaml.safe_load(f) or {}

    mesh_cams = [
        {
            "camera_id": c.camera_id,
            "source": c.source,
            "role": c.role,
            "label": c.label,
        }
        for c in camera_mesh.list_cameras()
        if c.camera_id not in ("cam_primary", "default", "primary")
    ]
    raw_cfg["cameras"] = mesh_cams
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw_cfg, f, default_flow_style=False, sort_keys=False)


class CameraStatusResponse(BaseModel):
    source: str
    is_connected: bool
    width: int
    height: int
    zones_count: int


def process_and_encode_frame(
    frame: npt.NDArray[np.uint8],
    tracked: list[TrackedDetection],
    overlay_zones: bool,
    overlay_detections: bool,
    quality: int = 80,
    camera_id: str | None = None,
) -> bytes:
    """Draw configured overlays and encode frame to JPEG bytes."""
    display_frame = frame.copy()
    if overlay_zones:
        display_frame = draw_zones_overlay(display_frame, camera_id=camera_id)
    if overlay_detections:
        display_frame = draw_tracked_overlay(display_frame, tracked)
    ret, jpeg = cv2.imencode(".jpg", display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpeg.tobytes() if ret else b""


def process_and_encode_fallback(
    src: str,
    width: int,
    height: int,
    overlay_zones: bool,
    quality: int = 80,
    camera_id: str | None = None,
) -> bytes:
    """Generate fallback canvas with optional zones overlay and encode to JPEG bytes."""
    fallback = generate_fallback_frame(src, width=width, height=height)
    if overlay_zones:
        fallback = draw_zones_overlay(fallback, camera_id=camera_id)
    ret, jpeg = cv2.imencode(".jpg", fallback, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpeg.tobytes() if ret else b""


async def frame_streamer(
    overlay_zones: bool,
    overlay_detections: bool,
    target_fps: int = 15,
    camera_id: str | None = None,
    request: Request | None = None,
) -> AsyncGenerator[bytes, None]:
    """Asynchronous generator yielding multipart/x-mixed-replace JPEG frames purely from memory."""
    stream_manager.start()
    delay = 1.0 / max(1, min(target_fps, 30))
    src = resolve_camera_source()
    last_fallback_time = 0.0
    cached_fallback_bytes: bytes = b""

    while not stream_manager.is_stopped():
        if request is not None and await request.is_disconnected():
            break

        try:
            is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame(
                camera_id=camera_id
            )
            if stream_manager.is_stopped():
                break

            if is_conn and cached_bgr is not None:
                eff_overlay_zones = overlay_zones if camera_id != "mosaic" else False
                eff_overlay_det = overlay_detections if camera_id != "mosaic" else False
                frame_bytes = await asyncio.to_thread(
                    process_and_encode_frame,
                    cached_bgr,
                    tracked,
                    eff_overlay_zones,
                    eff_overlay_det,
                    80,
                    camera_id,
                )
            else:
                now = asyncio.get_event_loop().time()
                # Cache synthetic standby frame for 1s to prevent repeated OpenCV encodings
                if not cached_fallback_bytes or now - last_fallback_time > 1.0:
                    cam_node = (
                        camera_mesh.get_camera(camera_id)
                        if camera_id
                        and camera_id not in ("cam_primary", "default", "primary", "mosaic")
                        else None
                    )
                    src = cam_node.source if cam_node else resolve_camera_source()
                    cached_fallback_bytes = await asyncio.to_thread(
                        process_and_encode_fallback,
                        src,
                        w,
                        h,
                        overlay_zones if camera_id != "mosaic" else False,
                        80,
                        camera_id,
                    )
                    last_fallback_time = now
                frame_bytes = cached_fallback_bytes
        except Exception as e:
            if stream_manager.is_stopped():
                break
            logger.warning("Degraded video stream in frame_streamer: %s", e)
            frame_bytes = cached_fallback_bytes

        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(frame_bytes)).encode()
                + b"\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )

        if stream_manager.is_stopped():
            break

        await asyncio.sleep(delay)


@router.get("/cameras")
def list_mesh_cameras() -> CameraMeshSummary:
    """Return live status of all camera nodes in the multi-camera mesh network."""
    return camera_mesh.get_summary()


@router.post("/cameras")
def register_mesh_camera(
    req: RegisterCameraRequest,
    cfg_path: ConfigPathDep,
) -> CameraMeshNodeConfig:
    """Register and start an edge camera node in the retail camera mesh."""
    node = camera_mesh.register_camera(
        camera_id=req.camera_id,
        source=req.source,
        role=req.role,
        label=req.label,
    )
    save_mesh_cameras_to_config(cfg_path)
    return node.to_config()


@router.delete("/cameras/{camera_id}")
def unregister_mesh_camera(
    camera_id: Annotated[str, Path(description="Camera node ID to unregister from mesh")],
    cfg_path: ConfigPathDep,
) -> UnregisterCameraResponse:
    """Remove and shut down a camera node from the mesh topology."""
    success = camera_mesh.unregister_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera node '{camera_id}' not found in mesh.",
        )
    save_mesh_cameras_to_config(cfg_path)
    return UnregisterCameraResponse(status="ok", unregistered=camera_id)


class UpdatePrimarySourceRequest(BaseModel):
    source: str


@router.put("/primary-source")
def update_primary_camera_source(
    req: UpdatePrimarySourceRequest,
    cfg_path: ConfigPathDep,
) -> dict[str, str]:
    """Update primary camera stream source directly in config.yaml."""
    if not cfg_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="config.yaml not found",
        )
    with cfg_path.open("r", encoding="utf-8") as f:
        raw_cfg: dict[str, Any] = yaml.safe_load(f) or {}
    if "camera" not in raw_cfg or not isinstance(raw_cfg["camera"], dict):
        raw_cfg["camera"] = {}
    raw_cfg["camera"]["source"] = req.source
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(raw_cfg, f, default_flow_style=False, sort_keys=False)
    # Signal StreamManager to re-open with new source
    stream_manager.active_src = ""
    return {"status": "ok", "source": req.source}


@router.get("/stream")
async def video_stream(
    request: Request,
    camera_id: Annotated[
        str | None, Query(description="Camera ID filter or 'mosaic' for multi-view grid")
    ] = None,
    overlay_zones: Annotated[bool, Query(description="Overlay configured detection zones")] = True,
    overlay_detections: Annotated[
        bool, Query(description="Overlay live YOLO person bounding boxes")
    ] = True,
    fps: Annotated[int, Query(ge=1, le=30, description="Target streaming frames per second")] = 15,
) -> StreamingResponse:
    """Stream live camera feed with real-time zone polygons and YOLO detections via MJPEG."""
    return StreamingResponse(
        frame_streamer(
            overlay_zones=overlay_zones,
            overlay_detections=overlay_detections,
            target_fps=fps,
            camera_id=camera_id,
            request=request,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/snapshot")
def video_snapshot(
    camera_id: Annotated[
        str | None, Query(description="Camera ID filter or 'mosaic' for multi-view grid")
    ] = None,
    overlay_zones: Annotated[bool, Query(description="Overlay configured detection zones")] = True,
    overlay_detections: Annotated[
        bool, Query(description="Overlay live YOLO person bounding boxes")
    ] = True,
) -> Response:
    """Capture a single JPEG snapshot frame instantly from memory."""
    src = resolve_camera_source()
    is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame(camera_id=camera_id)

    if is_conn and cached_bgr is not None:
        eff_zones = overlay_zones if camera_id != "mosaic" else False
        eff_det = overlay_detections if camera_id != "mosaic" else False
        frame_bytes = process_and_encode_frame(
            cached_bgr, tracked, eff_zones, eff_det, quality=90, camera_id=camera_id
        )
    else:
        frame_bytes = process_and_encode_fallback(
            src, width=w, height=h, overlay_zones=overlay_zones, quality=90, camera_id=camera_id
        )

    if not frame_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encode frame",
        )

    return Response(content=frame_bytes, media_type="image/jpeg")


@router.get("/status")
def video_status(
    cfg: AppConfigDep,
    camera_id: Annotated[str | None, Query(description="Optional camera ID filter")] = None,
) -> CameraStatusResponse:
    """Return live camera connection status and dimensions instantly in 0ms."""
    if camera_id and camera_id not in ("cam_primary", "default", "primary"):
        node = camera_mesh.get_camera(camera_id)
        if node is not None:
            return CameraStatusResponse(
                source=mask_rtsp_credentials(node.source),
                is_connected=node.is_connected,
                width=node.width,
                height=node.height,
                zones_count=0,
            )

    src = resolve_camera_source()
    zones_cnt = len(cfg.zones) if cfg and cfg.zones else 0
    is_conn, _, _, w, h = stream_manager.get_latest_frame(camera_id=camera_id)

    return CameraStatusResponse(
        source=mask_rtsp_credentials(src),
        is_connected=is_conn,
        width=w,
        height=h,
        zones_count=zones_cnt,
    )
