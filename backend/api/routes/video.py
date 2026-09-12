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
from api.stream_manager import (
    draw_tracked_overlay,
    draw_zones_overlay,
    generate_fallback_frame,
    resolve_camera_source,
    stream_manager,
)
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
) -> AsyncGenerator[bytes, None]:
    """Asynchronous generator yielding multipart/x-mixed-replace JPEG frames purely from memory."""
    delay = 1.0 / max(1, min(target_fps, 30))
    src = resolve_camera_source()
    last_fallback_time = 0.0
    cached_fallback_bytes: bytes = b""

    while True:
        try:
            is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame()
            if is_conn and cached_bgr is not None:
                frame_bytes = await asyncio.to_thread(
                    process_and_encode_frame,
                    cached_bgr,
                    tracked,
                    overlay_zones,
                    overlay_detections,
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
                        overlay_zones,
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


@router.get("/stream")
async def video_stream(
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
    overlay_zones: Annotated[bool, Query(description="Overlay configured detection zones")] = True,
    overlay_detections: Annotated[
        bool, Query(description="Overlay live YOLO person bounding boxes")
    ] = True,
) -> Response:
    """Capture a single JPEG snapshot frame instantly from memory."""
    src = resolve_camera_source()
    is_conn, cached_bgr, tracked, w, h = stream_manager.get_latest_frame()

    if is_conn and cached_bgr is not None:
        frame_bytes = process_and_encode_frame(
            cached_bgr, tracked, overlay_zones, overlay_detections, quality=90
        )
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
def video_status(cfg: AppConfigDep) -> CameraStatusResponse:
    """Return live camera connection status and dimensions instantly in 0ms."""
    src = resolve_camera_source()
    zones_cnt = len(cfg.zones) if cfg and cfg.zones else 0
    is_conn, _, _, w, h = stream_manager.get_latest_frame()

    return CameraStatusResponse(
        source=mask_rtsp_credentials(src),
        is_connected=is_conn,
        width=w,
        height=h,
        zones_count=zones_cnt,
    )
