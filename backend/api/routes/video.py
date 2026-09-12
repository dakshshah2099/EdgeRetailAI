import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

import cv2
import numpy as np
import numpy.typing as npt
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from api.dependencies import AppConfigDep
from api.schemas_api import CameraMeshNodeConfig, CameraMeshSummary, RegisterCameraRequest
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
) -> bytes:
    """Draw configured overlays and encode frame to JPEG bytes."""
    display_frame = frame.copy()
    if overlay_zones:
        display_frame = draw_zones_overlay(display_frame)
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
) -> bytes:
    """Generate fallback canvas with optional zones overlay and encode to JPEG bytes."""
    fallback = generate_fallback_frame(src, width=width, height=height)
    if overlay_zones:
        fallback = draw_zones_overlay(fallback)
    ret, jpeg = cv2.imencode(".jpg", fallback, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    return jpeg.tobytes() if ret else b""


async def frame_streamer(
    overlay_zones: bool,
    overlay_detections: bool,
    target_fps: int = 15,
    camera_id: str | None = None,
) -> AsyncGenerator[bytes, None]:
    """Asynchronous generator yielding multipart/x-mixed-replace JPEG frames purely from memory."""
    delay = 1.0 / max(1, min(target_fps, 30))
    src = resolve_camera_source()
    last_fallback_time = 0.0
    cached_fallback_bytes: bytes = b""

    while True:
        try:
            is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame(
                camera_id=camera_id
            )
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
                )
            else:
                now = asyncio.get_event_loop().time()
                # Cache synthetic standby frame for 1s to prevent repeated OpenCV encodings
                if not cached_fallback_bytes or now - last_fallback_time > 1.0:
                    src = resolve_camera_source()
                    cached_fallback_bytes = await asyncio.to_thread(
                        process_and_encode_fallback,
                        src,
                        w,
                        h,
                        overlay_zones if camera_id != "mosaic" else False,
                        80,
                    )
                    last_fallback_time = now
                frame_bytes = cached_fallback_bytes
        except Exception as e:
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

        await asyncio.sleep(delay)


@router.get("/cameras")
def list_mesh_cameras() -> CameraMeshSummary:
    """Return live status of all camera nodes in the multi-camera mesh network."""
    return camera_mesh.get_summary()


@router.post("/cameras")
def register_mesh_camera(req: RegisterCameraRequest) -> CameraMeshNodeConfig:
    """Register and start an edge camera node in the retail camera mesh."""
    node = camera_mesh.register_camera(
        camera_id=req.camera_id,
        source=req.source,
        role=req.role,
        label=req.label,
    )
    return node.to_config()


@router.delete("/cameras/{camera_id}")
def unregister_mesh_camera(camera_id: str) -> dict[str, str]:
    """Remove and shut down a camera node from the mesh topology."""
    success = camera_mesh.unregister_camera(camera_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera node '{camera_id}' not found in mesh.",
        )
    return {"status": "ok", "unregistered": camera_id}


@router.get("/stream")
async def video_stream(
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
        frame_bytes = process_and_encode_frame(cached_bgr, tracked, eff_zones, eff_det, quality=90)
    else:
        frame_bytes = process_and_encode_fallback(
            src, width=w, height=h, overlay_zones=overlay_zones, quality=90
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
