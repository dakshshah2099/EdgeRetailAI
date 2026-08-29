import logging
import time
from datetime import UTC, datetime
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from camera.base import CameraSource
from schemas import Frame

logger = logging.getLogger(__name__)


class RTSPSource(CameraSource):
    """RTSP camera stream capture source with exponential backoff reconnection and timeouts."""

    def __init__(
        self,
        source_url: str,
        source_id: str = "rtsp_cam",
        initial_backoff_sec: float = 1.0,
        max_backoff_sec: float = 10.0,
        backoff_factor: float = 2.0,
        timeout_msec: int = 5000,
    ) -> None:
        self.source_url = source_url
        self.source_id = source_id
        self._initial_backoff_sec = initial_backoff_sec
        self._max_backoff_sec = max_backoff_sec
        self._backoff_factor = backoff_factor
        self._timeout_msec = timeout_msec

        self._current_backoff = initial_backoff_sec
        self._cap: cv2.VideoCapture | None = None
        self._connect()

    def _connect(self) -> bool:
        """Attempt connecting to the RTSP stream with FFMPEG timeouts."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        logger.info("Connecting to RTSP stream: %s", self.source_url)
        cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._timeout_msec)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._timeout_msec)
        if not cap.isOpened():
            logger.warning("Failed to open RTSP stream at %s", self.source_url)
            self._cap = cap
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
            self._cap.release()
            self._cap = None

        time.sleep(self._current_backoff)
        self._current_backoff = min(
            self._current_backoff * self._backoff_factor, self._max_backoff_sec
        )
        self._connect()

    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return next available frame from RTSP stream, or None on failure."""
        if self._cap is None or not self._cap.isOpened():
            self._handle_disconnect_and_backoff()
            if self._cap is None or not self._cap.isOpened():
                return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            self._handle_disconnect_and_backoff()
            return None

        # Reset backoff on successful frame read
        self._current_backoff = self._initial_backoff_sec

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
            self._cap.release()
            self._cap = None
            logger.info("Closed RTSP stream: %s", self.source_url)
