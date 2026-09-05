import asyncio
import logging
from collections.abc import AsyncGenerator

import cv2
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from api.dependencies import get_app_config
from api.stream_manager import (
    draw_tracked_overlay,
    draw_zones_overlay,
    generate_fallback_frame,
    resolve_camera_source,
    stream_manager,
)
from camera.rtsp_source import mask_rtsp_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video", tags=["video"])


class CameraStatusResponse(BaseModel):
    source: str
    is_connected: bool
    width: int
    height: int
    zones_count: int


async def frame_streamer(
    overlay_zones: bool,
    overlay_detections: bool,
    target_fps: int = 15,
) -> AsyncGenerator[bytes, None]:
    """Asynchronous generator yielding multipart/x-mixed-replace JPEG frames purely from memory."""
    delay = 1.0 / max(1, min(target_fps, 30))
    src = resolve_camera_source()

    while True:
        try:
            is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame()
            if is_conn and cached_bgr is not None:
                display_frame = cached_bgr.copy()
                if overlay_zones:
                    display_frame = draw_zones_overlay(display_frame)
                if overlay_detections:
                    display_frame = draw_tracked_overlay(display_frame, tracked)
            else:
                fallback = generate_fallback_frame(src, width=w, height=h)
                display_frame = fallback
                if overlay_zones:
                    display_frame = draw_zones_overlay(display_frame)
        except Exception as e:
            logger.warning("Degraded video stream in frame_streamer: %s", e)
            display_frame = generate_fallback_frame(src)

        ret, jpeg = cv2.imencode(".jpg", display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if ret:
            frame_bytes = jpeg.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame_bytes)).encode() + b"\r\n\r\n"
                + frame_bytes + b"\r\n"
            )

        await asyncio.sleep(delay)


@router.get("/stream")
async def video_stream(
    overlay_zones: bool = Query(True, description="Overlay configured detection zones"),
    overlay_detections: bool = Query(True, description="Overlay live YOLO person bounding boxes"),
    fps: int = Query(15, ge=1, le=30, description="Target streaming frames per second"),
) -> StreamingResponse:
    """Stream live camera feed with real-time zone polygons and YOLO detections via MJPEG."""
    return StreamingResponse(
        frame_streamer(
            overlay_zones=overlay_zones,
            overlay_detections=overlay_detections,
            target_fps=fps,
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
    overlay_zones: bool = Query(True, description="Overlay configured detection zones"),
    overlay_detections: bool = Query(True, description="Overlay live YOLO person bounding boxes"),
) -> Response:
    """Capture a single JPEG snapshot frame instantly from memory."""
    src = resolve_camera_source()
    is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame()

    if is_conn and cached_bgr is not None:
        frame = cached_bgr.copy()
        if overlay_zones:
            frame = draw_zones_overlay(frame)
        if overlay_detections:
            frame = draw_tracked_overlay(frame, tracked)
    else:
        frame = generate_fallback_frame(src, width=w, height=h)

    ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ret:
        return Response(status_code=500, content="Failed to encode frame")

    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@router.get("/status", response_model=CameraStatusResponse)
def video_status() -> CameraStatusResponse:
    """Return live camera connection status and dimensions instantly in 0ms."""
    src = resolve_camera_source()
    cfg = get_app_config()
    zones_cnt = len(cfg.zones) if cfg and cfg.zones else 0
    is_conn, _, _, w, h = stream_manager.get_latest_frame()

    return CameraStatusResponse(
        source=mask_rtsp_credentials(src),
        is_connected=is_conn,
        width=w,
        height=h,
        zones_count=zones_cnt,
    )
