"""HTTP IP Webcam and MJPEG camera capture source.

Supports IP Webcam (Android/iOS), DroidCam, ESP32-CAM, and HTTP snapshot streams.
"""

from __future__ import annotations

import contextlib
import http.client
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from core.schemas import Frame
from vision.camera_base import CameraSource
from vision.rtsp_source import format_authenticated_rtsp_url, mask_rtsp_credentials

logger = logging.getLogger(__name__)


class HTTPSource(CameraSource):
    """Robust camera source for HTTP/HTTPS IP webcam and MJPEG streams."""

    def __init__(
        self,
        source_url: str,
        source_id: str = "http_cam",
        username: str | None = None,
        password: str | None = None,
        timeout_msec: int = 4000,
        initial_backoff_sec: float = 1.0,
        max_backoff_sec: float = 10.0,
        backoff_factor: float = 2.0,
        non_blocking: bool = False,
    ) -> None:
        self.raw_url = source_url
        self.source_url = format_authenticated_rtsp_url(source_url, username, password)
        self.source_id = source_id
        self._timeout_sec = max(1.0, timeout_msec / 1000.0)
        self._timeout_msec = timeout_msec
        self._initial_backoff = initial_backoff_sec
        self._max_backoff = max_backoff_sec
        self._backoff_factor = backoff_factor

        self._current_backoff = initial_backoff_sec
        self._next_reconnect_time = 0.0
        self._cap: cv2.VideoCapture | None = None
        self._is_closed = False

        # MJPEG byte stream fallback state
        self._stream_response: http.client.HTTPResponse | None = None
        self._byte_buffer = bytearray()
        self._use_mjpeg_fallback = False

        self._lock = threading.Lock()
        self._latest_frame: tuple[Frame, npt.NDArray[np.uint8]] | None = None

        # Resolve best endpoint (e.g. append /video if user passed bare IP:port)
        self.active_url = self._resolve_stream_endpoint(self.source_url)

        if not non_blocking:
            self._connect()

    def _resolve_stream_endpoint(self, url: str) -> str:
        """Auto-detect and append stream path if user provided bare host:port."""
        parsed = urllib.parse.urlsplit(url)
        if not parsed.path or parsed.path == "/":
            # Android IP Webcam defaults to /video, DroidCam to /mjpegfeed
            candidate = urllib.parse.urlunsplit(parsed._replace(path="/video"))
            return candidate
        return url

    def _connect(self) -> bool:
        """Attempt to connect to HTTP camera source."""
        if self._is_closed:
            return False

        now = time.monotonic()
        if now < self._next_reconnect_time:
            return False

        self._release_capture()
        logger.info("Connecting to HTTP camera stream: %s", mask_rtsp_credentials(self.active_url))

        # 1. First attempt: OpenCV VideoCapture with clean HTTP options
        timeout_us = int(self._timeout_msec * 1000)
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"timeout;{timeout_us}|rw_timeout;{timeout_us}|fflags;nobuffer|flags;low_delay"
        )

        try:
            cap = cv2.VideoCapture(self.active_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._timeout_msec)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._timeout_msec)

            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret and test_frame is not None and test_frame.size > 0:
                    self._cap = cap
                    self._use_mjpeg_fallback = False
                    self._current_backoff = self._initial_backoff
                    logger.info("Connected to HTTP stream via OpenCV FFMPEG.")
                    return True
                cap.release()
        except Exception as exc:
            logger.debug("OpenCV HTTP VideoCapture failed: %s", exc)

        # 2. Second attempt: Direct MJPEG HTTP multipart stream reader
        try:
            req = urllib.request.Request(
                self.active_url,
                headers={"User-Agent": "EdgeRetailAI-CameraClient/1.0"},
            )
            resp = urllib.request.urlopen(req, timeout=self._timeout_sec)
            content_type = resp.headers.get("Content-Type", "")

            is_mjpeg = (
                "multipart" in content_type
                or "image/jpeg" in content_type
                or "video" in self.active_url
            )
            if is_mjpeg:
                self._stream_response = cast(http.client.HTTPResponse, resp)
                self._use_mjpeg_fallback = True
                self._byte_buffer = bytearray()
                self._current_backoff = self._initial_backoff
                logger.info("Connected to HTTP stream via direct MJPEG parser.")
                return True
        except Exception as exc:
            logger.warning(
                "Failed connecting to HTTP camera at %s: %s",
                mask_rtsp_credentials(self.active_url),
                exc,
            )

        # Reconnect backoff
        self._next_reconnect_time = now + self._current_backoff
        self._current_backoff = min(self._max_backoff, self._current_backoff * self._backoff_factor)
        return False

    def _read_mjpeg_frame(self) -> npt.NDArray[np.uint8] | None:
        """Read next JPEG frame from multipart MJPEG HTTP stream."""
        if not self._stream_response:
            return None

        try:
            while len(self._byte_buffer) < 2000000:
                chunk = self._stream_response.read(4096)
                if not chunk:
                    break
                self._byte_buffer.extend(chunk)

                # Find JPEG start (0xFFD8) and end (0xFFD9)
                start_idx = self._byte_buffer.find(b"\xff\xd8")
                if start_idx != -1:
                    end_idx = self._byte_buffer.find(b"\xff\xd9", start_idx)
                    if end_idx != -1:
                        jpg_data = self._byte_buffer[start_idx : end_idx + 2]
                        del self._byte_buffer[: end_idx + 2]
                        arr = np.frombuffer(jpg_data, dtype=np.uint8)
                        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                        if frame is not None and frame.size > 0:
                            return cast(npt.NDArray[np.uint8], frame)
            return None
        except Exception:
            return None

    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Fetch latest frame from HTTP camera stream."""
        if self._is_closed:
            return None

        if self._cap is None and not self._use_mjpeg_fallback and not self._connect():
            return None

        raw_bgr: npt.NDArray[np.uint8] | None = None

        if self._use_mjpeg_fallback:
            raw_bgr = self._read_mjpeg_frame()
            if raw_bgr is None:
                self._handle_read_failure()
                return None
        elif self._cap is not None:
            try:
                ret, frame = self._cap.read()
                if not ret or frame is None or frame.size == 0:
                    self._handle_read_failure()
                    return None
                raw_bgr = cast(npt.NDArray[np.uint8], frame)
            except Exception:
                self._handle_read_failure()
                return None

        if raw_bgr is None:
            return None

        height, width = raw_bgr.shape[:2]
        meta = Frame(
            source_id=self.source_id,
            timestamp=datetime.now(UTC),
            width=width,
            height=height,
        )
        return meta, raw_bgr

    def _handle_read_failure(self) -> None:
        """Mark failure and initiate reconnect with backoff."""
        self._release_capture()
        now = time.monotonic()
        self._next_reconnect_time = now + self._current_backoff
        self._current_backoff = min(self._max_backoff, self._current_backoff * self._backoff_factor)

    def _release_capture(self) -> None:
        """Release underlying stream resources."""
        if self._cap is not None:
            with contextlib.suppress(Exception):
                self._cap.release()
            self._cap = None

        if self._stream_response is not None:
            with contextlib.suppress(Exception):
                self._stream_response.close()
            self._stream_response = None

        self._byte_buffer.clear()
        self._use_mjpeg_fallback = False

    def close(self) -> None:
        """Close source permanently."""
        self._is_closed = True
        self._release_capture()
