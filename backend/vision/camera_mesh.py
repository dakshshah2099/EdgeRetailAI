import contextlib
import logging
import math
import threading
import time
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt

from api.schemas_api import CameraMeshNodeConfig, CameraMeshSummary
from vision.camera_base import CameraSource
from vision.rtsp_source import RTSPSource, mask_rtsp_credentials
from vision.usb_source import USBSource

logger = logging.getLogger(__name__)


class CameraNode:
    """Individual camera stream node in the retail mesh."""

    def __init__(
        self,
        camera_id: str,
        source: str,
        role: Literal["entrance", "checkout", "shelf", "general"] = "general",
        label: str = "",
        auto_start: bool = True,
    ) -> None:
        self.camera_id = camera_id
        self.source = source
        self.role = role
        self.label = label or camera_id

        self._lock = threading.Lock()
        self._frame: npt.NDArray[np.uint8] | None = None
        self.width = 640
        self.height = 480
        self.is_connected = False
        self.fps = 0.0
        self.last_frame_time = 0.0
        self._frame_count = 0
        self._fps_start_time = time.monotonic()

        self.camera_source: CameraSource | None = None
        self._shutdown_event = threading.Event()
        self._thread: threading.Thread | None = None

        if auto_start:
            self.start()

    def start(self) -> None:
        """Start background frame capture loop."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._shutdown_event.clear()
        self._thread = threading.Thread(
            target=self._capture_worker,
            name=f"mesh-cam-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop capture loop and release camera source."""
        self._shutdown_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

        if self.camera_source:
            with contextlib.suppress(Exception):
                self.camera_source.close()
            self.camera_source = None
        self.is_connected = False

    def update_frame(
        self, frame: npt.NDArray[np.uint8], width: int | None = None, height: int | None = None
    ) -> None:
        """Manually push a frame to this node (e.g. from shared stream manager)."""
        h, w = frame.shape[:2]
        now = time.monotonic()
        with self._lock:
            self._frame = frame.copy()
            self.width = width or w
            self.height = height or h
            self.is_connected = True
            self.last_frame_time = now
            self._frame_count += 1
            elapsed = now - self._fps_start_time
            if elapsed >= 2.0:
                self.fps = round(self._frame_count / elapsed, 1)
                self._frame_count = 0
                self._fps_start_time = now

    def get_frame(self) -> tuple[bool, npt.NDArray[np.uint8] | None, int, int]:
        """Return latest frame snapshot safely without blocking."""
        with self._lock:
            if self._frame is None:
                return self.is_connected, None, self.width, self.height
            return self.is_connected, self._frame.copy(), self.width, self.height

    def to_config(self) -> CameraMeshNodeConfig:
        """Serialize current node state into API schema."""
        return CameraMeshNodeConfig(
            camera_id=self.camera_id,
            source=mask_rtsp_credentials(self.source),
            role=self.role,
            label=self.label,
            is_connected=self.is_connected,
            fps=self.fps,
            width=self.width,
            height=self.height,
        )

    def _capture_worker(self) -> None:
        """Continuous frame ingestion loop for camera node."""
        while not self._shutdown_event.is_set():
            try:
                if self.camera_source is None:
                    src = self.source
                    if (
                        src.startswith("rtsp://")
                        or src.startswith("rtsps://")
                        or src.startswith("http://")
                    ):
                        self.camera_source = RTSPSource(
                            source_url=src,
                            timeout_msec=2000,
                            initial_backoff_sec=1.5,
                            max_backoff_sec=10.0,
                            non_blocking=True,
                        )
                    else:
                        dev_idx = int(src) if src.isdigit() else 0
                        self.camera_source = USBSource(device_index=dev_idx)

                # Attempt non-blocking frame read
                res = self.camera_source.get_frame()
                now = time.monotonic()

                if res is not None:
                    frame_meta, frame_bgr = res
                    with self._lock:
                        self._frame = frame_bgr
                        self.width = frame_meta.width
                        self.height = frame_meta.height
                        self.is_connected = True
                        self.last_frame_time = now
                        self._frame_count += 1
                        elapsed = now - self._fps_start_time
                        if elapsed >= 2.0:
                            self.fps = round(self._frame_count / elapsed, 1)
                            self._frame_count = 0
                            self._fps_start_time = now
                    time.sleep(0.015)
                else:
                    if now - self.last_frame_time > 3.0:
                        with self._lock:
                            self.is_connected = False
                    time.sleep(0.1)

            except Exception as e:
                logger.debug("Mesh camera %s capture error: %s", self.camera_id, e)
                with self._lock:
                    self.is_connected = False
                time.sleep(0.5)


class CameraMesh:
    """Multi-camera topology coordinator for edge retail deployments."""

    def __init__(self) -> None:
        self._nodes: dict[str, CameraNode] = {}
        self._lock = threading.Lock()

    def register_camera(
        self,
        camera_id: str,
        source: str,
        role: Literal["entrance", "checkout", "shelf", "general"] = "general",
        label: str = "",
        auto_start: bool = True,
    ) -> CameraNode:
        """Register and initialize a new camera node in the mesh."""
        with self._lock:
            if camera_id in self._nodes:
                # Stop and replace existing node
                self._nodes[camera_id].stop()

            node = CameraNode(
                camera_id=camera_id,
                source=source,
                role=role,
                label=label or camera_id,
                auto_start=auto_start,
            )
            self._nodes[camera_id] = node
            logger.info(
                "CameraMesh: registered node '%s' (role=%s, source=%s)",
                camera_id,
                role,
                mask_rtsp_credentials(source),
            )
            return node

    def unregister_camera(self, camera_id: str) -> bool:
        """Remove a camera node from the mesh and terminate its capture."""
        with self._lock:
            node = self._nodes.pop(camera_id, None)
            if node:
                node.stop()
                logger.info("CameraMesh: unregistered node '%s'", camera_id)
                return True
            return False

    def get_camera(self, camera_id: str) -> CameraNode | None:
        """Retrieve a camera node by ID."""
        with self._lock:
            return self._nodes.get(camera_id)

    def list_cameras(self) -> list[CameraMeshNodeConfig]:
        """Return list of all registered cameras and their live health."""
        with self._lock:
            return [node.to_config() for node in self._nodes.values()]

    def get_summary(self) -> CameraMeshSummary:
        """Return aggregated summary of the mesh network."""
        configs = self.list_cameras()
        active = sum(1 for c in configs if c.is_connected)
        return CameraMeshSummary(
            total_cameras=len(configs),
            active_cameras=active,
            cameras=configs,
        )

    def get_frame(self, camera_id: str) -> tuple[bool, npt.NDArray[np.uint8] | None, int, int]:
        """Retrieve frame for a specific camera in the mesh."""
        node = self.get_camera(camera_id)
        if node is None:
            return False, None, 640, 480
        return node.get_frame()

    def get_active_frames(self) -> list[tuple[str, npt.NDArray[np.uint8]]]:
        """Return frames for all currently connected camera nodes in the mesh."""
        frames: list[tuple[str, npt.NDArray[np.uint8]]] = []
        with self._lock:
            nodes = list(self._nodes.values())
        for node in nodes:
            is_conn, frame, _, _ = node.get_frame()
            if is_conn and frame is not None:
                frames.append((node.camera_id, frame))
        return frames

    def generate_mosaic(
        self,
        grid_cols: int = 2,
        mosaic_width: int = 1280,
        mosaic_height: int = 720,
    ) -> npt.NDArray[np.uint8]:
        """Composite all active mesh camera feeds into a unified multi-view mosaic canvas."""
        with self._lock:
            nodes = list(self._nodes.values())

        if not nodes:
            # Standby blank mosaic canvas
            canvas = np.full((mosaic_height, mosaic_width, 3), 20, dtype=np.uint8)
            cv2.putText(
                canvas,
                "CAMERA MESH - NO REGISTERED NODES",
                (mosaic_width // 4, mosaic_height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (140, 140, 140),
                2,
            )
            return canvas

        num_nodes = len(nodes)
        cols = min(grid_cols, num_nodes)
        rows = math.ceil(num_nodes / cols)
        cell_w = mosaic_width // cols
        cell_h = mosaic_height // rows

        canvas = np.full((mosaic_height, mosaic_width, 3), 16, dtype=np.uint8)

        for idx, node in enumerate(nodes):
            r = idx // cols
            c = idx % cols
            x1 = c * cell_w
            y1 = r * cell_h
            x2 = min(x1 + cell_w, mosaic_width)
            y2 = min(y1 + cell_h, mosaic_height)

            is_conn, frame, _, _ = node.get_frame()
            target_w = x2 - x1
            target_h = y2 - y1

            if is_conn and frame is not None:
                cell_img = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            else:
                cell_img = np.full((target_h, target_w, 3), 32, dtype=np.uint8)
                cv2.putText(
                    cell_img,
                    f"CONNECTING: {node.camera_id.upper()}",
                    (20, target_h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (120, 120, 120),
                    1,
                )

            # Node Badge overlay
            status_color = (46, 204, 113) if is_conn else (100, 100, 240)
            cv2.circle(cell_img, (18, 20), 6, status_color, -1)
            badge_text = f"{node.label} [{node.role.upper()}] - {node.fps} FPS"
            cv2.putText(
                cell_img,
                badge_text,
                (32, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Draw cell borders
            cv2.rectangle(cell_img, (0, 0), (target_w - 1, target_h - 1), (45, 52, 64), 1)

            canvas[y1:y2, x1:x2] = cell_img

        return canvas

    def close(self) -> None:
        """Shut down all mesh camera workers."""
        with self._lock:
            for node in self._nodes.values():
                node.stop()
            self._nodes.clear()
        logger.info("CameraMesh: all camera nodes stopped and cleared")


# Global singleton CameraMesh
camera_mesh = CameraMesh()
