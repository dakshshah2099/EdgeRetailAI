import logging
import os
import time
from datetime import UTC, datetime
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from core.schemas import Frame
from vision.camera_base import CameraSource

logger = logging.getLogger(__name__)


class USBSource(CameraSource):
    """USB webcam / video file capture source with optional continuous loop and real-time pacing."""

    def __init__(
        self,
        device_index: int | str = 0,
        source_id: str = "usb_cam",
        loop: bool = False,
        pace: bool | None = None,
    ) -> None:
        self.device_index = device_index
        self.source_id = source_id
        self.loop = loop
        self._is_file = isinstance(self.device_index, str) and not str(self.device_index).isdigit()

        if pace is not None:
            self.pace = pace
        else:
            self.pace = self._is_file and "PYTEST_CURRENT_TEST" not in os.environ

        self._fps: float = 30.0
        self._last_frame_ts: float | None = None
        self._cap: cv2.VideoCapture | None = None
        self._open_capture()

    def _open_capture(self) -> None:
        """Open the video capture device or file and detect native frame rate."""
        logger.info("Opening capture device: %s", self.device_index)
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            logger.warning("Failed to open capture device at %s", self.device_index)
            return

        if self._is_file:
            raw_fps = self._cap.get(cv2.CAP_PROP_FPS)
            if raw_fps and 1.0 <= raw_fps <= 120.0:
                self._fps = float(raw_fps)
            else:
                self._fps = 30.0
            logger.info("Pacing video file playback at %s FPS (pace=%s)", self._fps, self.pace)

    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return next available frame from USB / file capture, or None on failure/EOF."""
        if self._cap is None or not self._cap.isOpened():
            logger.warning("Capture device %s is not open", self.source_id)
            return None

        # Real-time pacing for video files
        if self.pace and self._is_file and self._last_frame_ts is not None:
            speed_mult = float(os.environ.get("VIDEO_PLAYBACK_SPEED", "1.0"))
            target_delay = (1.0 / self._fps) / max(0.05, speed_mult)
            elapsed = time.monotonic() - self._last_frame_ts
            sleep_time = target_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        ret, frame = self._cap.read()
        if (not ret or frame is None or frame.size == 0) and self.loop:
            # Rewind video file to beginning
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret or frame is None or frame.size == 0:
                self._open_capture()
                if self._cap and self._cap.isOpened():
                    ret, frame = self._cap.read()
                else:
                    ret = False

        if not ret or frame is None or frame.size == 0:
            logger.warning("Failed to read frame from device %s", self.source_id)
            return None

        if self.pace and self._is_file:
            self._last_frame_ts = time.monotonic()

        height, width = frame.shape[:2]
        metadata = Frame(
            source_id=self.source_id,
            timestamp=datetime.now(UTC),
            width=int(width),
            height=int(height),
        )
        return metadata, cast(npt.NDArray[np.uint8], frame)

    def close(self) -> None:
        """Release capture device resource."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Closed capture device: %s", self.device_index)
