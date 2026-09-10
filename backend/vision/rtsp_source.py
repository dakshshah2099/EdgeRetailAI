import contextlib
import logging
import os
import time
import urllib.parse
from datetime import UTC, datetime
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from core.schemas import Frame
from vision.camera_base import CameraSource

logger = logging.getLogger(__name__)


def format_authenticated_rtsp_url(
    url: str,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Inject URL-encoded username and password into an RTSP URL if not already present.

    If password is empty or not provided, the URL is returned unmodified to allow
    connecting to unauthenticated RTSP streams without injecting unwanted credentials.
    """
    if not (url.startswith("rtsp://") or url.startswith("rtsps://") or url.startswith("http://")):
        return url

    parsed = urllib.parse.urlsplit(url)
    # If credentials are already embedded in the URL, return as-is
    if parsed.username or parsed.password:
        return url

    user_clean = (username or "").strip()
    pass_clean = (password or "").strip()
    # If either credential is empty, do not inject auth (preserves unauthenticated streams)
    if not user_clean or not pass_clean:
        return url

    user_enc = urllib.parse.quote(user_clean, safe="")
    pass_enc = urllib.parse.quote(pass_clean, safe="")
    auth_str = f"{user_enc}:{pass_enc}@"

    new_netloc = f"{auth_str}{parsed.netloc}"
    return urllib.parse.urlunsplit(parsed._replace(netloc=new_netloc))


def mask_rtsp_credentials(url: str) -> str:
    """Mask password in RTSP URL for safe logging."""
    if "@" not in url:
        return url
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.username and parsed.password is not None:
            masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                masked_netloc += f":{parsed.port}"
            return urllib.parse.urlunsplit(parsed._replace(netloc=masked_netloc))
    except Exception:
        pass
    return url


class RTSPSource(CameraSource):
    """RTSP camera capture source with auth, backoff, and socket timeouts."""

    def __init__(
        self,
        source_url: str,
        source_id: str = "rtsp_cam",
        username: str | None = None,
        password: str | None = None,
        initial_backoff_sec: float = 1.0,
        max_backoff_sec: float = 10.0,
        backoff_factor: float = 2.0,
        timeout_msec: int = 5000,
        non_blocking: bool = False,
    ) -> None:
        self.source_url = format_authenticated_rtsp_url(source_url, username, password)
        self.source_id = source_id
        self._initial_backoff_sec = initial_backoff_sec
        self._max_backoff_sec = max_backoff_sec
        self._backoff_factor = backoff_factor
        self._timeout_msec = timeout_msec
        self._non_blocking = non_blocking

        self._current_backoff = initial_backoff_sec
        self._next_reconnect_time: float = 0.0
        self._cap: cv2.VideoCapture | None = None

        if not self._non_blocking:
            self._connect()

    def _connect(self) -> bool:
        """Attempt connecting to the RTSP stream with low ffmpeg socket timeouts."""
        if self._cap is not None:
            with contextlib.suppress(Exception):
                self._cap.release()
            self._cap = None

        timeout_us = int(self._timeout_msec * 1000)
        transport = os.environ.get("RTSP_TRANSPORT", "tcp").lower()
        if transport not in ("tcp", "udp"):
            transport = "tcp"
        # Set ffmpeg socket and connection timeouts in microseconds for OpenCV,
        # with nobuffer and low delay
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"rtsp_transport;{transport}|timeout;{timeout_us}|stimeout;{timeout_us}|"
            f"rw_timeout;{timeout_us}|max_delay;500000|fflags;nobuffer|flags;low_delay|"
            "probesize;1000000|analyzeduration;1000000"
        )

        logger.info("Connecting to RTSP stream: %s", mask_rtsp_credentials(self.source_url))
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            self._timeout_msec,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            self._timeout_msec,
        ]
        cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG, params)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._timeout_msec)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._timeout_msec)
        if not cap.isOpened():
            logger.warning(
                "Failed to open RTSP stream at %s", mask_rtsp_credentials(self.source_url)
            )
            with contextlib.suppress(Exception):
                cap.release()
            self._cap = None
            return False

        self._cap = cap
        return True

    def _handle_disconnect_and_backoff(self) -> None:
        """Handle stream disconnect, release resource, sleep with backoff, and reconnect."""
        logger.warning(
            "RTSP stream %s disconnected or failed to read. Backing off for %.2fs",
            self.source_id,
            self._current_backoff,
        )
        if self._cap is not None:
            with contextlib.suppress(Exception):
                self._cap.release()
            self._cap = None

        if self._non_blocking:
            self._next_reconnect_time = time.monotonic() + self._current_backoff
            self._current_backoff = min(
                self._current_backoff * self._backoff_factor, self._max_backoff_sec
            )
        else:
            time.sleep(self._current_backoff)
            self._current_backoff = min(
                self._current_backoff * self._backoff_factor, self._max_backoff_sec
            )
            self._connect()

    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return next available frame from RTSP stream, or None on failure."""
        now = time.monotonic()
        if self._cap is None or not self._cap.isOpened():
            if self._non_blocking and now < self._next_reconnect_time:
                return None

            if self._non_blocking:
                if not self._connect():
                    self._handle_disconnect_and_backoff()
                    return None
            else:
                self._handle_disconnect_and_backoff()
                if self._cap is None or not self._cap.isOpened():
                    return None

        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None or frame.size == 0:
            self._handle_disconnect_and_backoff()
            return None

        # Reset backoff on successful frame read
        self._current_backoff = self._initial_backoff_sec
        self._next_reconnect_time = 0.0

        height, width = frame.shape[:2]
        metadata = Frame(
            source_id=self.source_id,
            timestamp=datetime.now(UTC),
            width=int(width),
            height=int(height),
        )
        return metadata, cast(npt.NDArray[np.uint8], frame)

    def close(self) -> None:
        """Release RTSP stream capture resource."""
        if self._cap is not None:
            with contextlib.suppress(Exception):
                self._cap.release()
            self._cap = None
            logger.info("Closed RTSP stream: %s", mask_rtsp_credentials(self.source_url))
