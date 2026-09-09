import logging
from datetime import UTC, datetime
from typing import cast

import cv2
import numpy as np
import numpy.typing as npt

from core.schemas import Frame
from vision.camera_base import CameraSource

logger = logging.getLogger(__name__)


class USBSource(CameraSource):
    """USB webcam / video file capture source with optional continuous loop support."""

    def __init__(
        self,
        device_index: int | str = 0,
        source_id: str = "usb_cam",
        loop: bool = False,
    ) -> None:
        self.device_index = device_index
        self.source_id = source_id
        self.loop = loop
        self._cap: cv2.VideoCapture | None = None
        self._open_capture()

    def _open_capture(self) -> None:
        """Open the video capture device or file."""
        logger.info("Opening capture device: %s", self.device_index)
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            logger.warning("Failed to open capture device at %s", self.device_index)

    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return next available frame from USB / file capture, or None on failure/EOF."""
        if self._cap is None or not self._cap.isOpened():
            logger.warning("Capture device %s is not open", self.source_id)
            return None

        ret, frame = self._cap.read()
        if (not ret or frame is None) and self.loop:
            # Rewind video file to beginning
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()

        if not ret or frame is None:
            logger.warning("Failed to read frame from device %s", self.source_id)
            return None

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
