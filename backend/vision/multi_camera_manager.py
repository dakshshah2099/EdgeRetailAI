"""MultiCameraManager: Manages N CameraSources with parallel capture threads
feeding a single shared InferenceBackend instance with per-camera runtime telemetry,
automatic reconnect with capped exponential backoff, latest-frame-only buffering,
and round-robin inference scheduling.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import yaml

from core.schemas import Frame
from vision.camera_base import CameraSource
from vision.inference_backend import InferenceBackend, RawDetection

logger = logging.getLogger(__name__)

# Backoff schedule: 1s, 2s, 4s, 8s, 15s, 30s, then hold at 30s
BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)


def get_backoff_delay(attempt: int) -> float:
    """Return capped backoff delay in seconds for the given attempt index (0-based)."""
    if attempt < 0:
        return BACKOFF_DELAYS[0]
    if attempt < len(BACKOFF_DELAYS):
        return BACKOFF_DELAYS[attempt]
    return BACKOFF_DELAYS[-1]


def _load_inference_target_fps() -> float:
    """Read inference.target_fps from config.yaml if available, default 10.0."""
    for p in [Path("config.yaml"), Path("backend/config.yaml")]:
        if p.is_file():
            try:
                with p.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "inference" in data:
                        inf = data["inference"]
                        if isinstance(inf, dict) and "target_fps" in inf:
                            return float(inf["target_fps"])
            except Exception:
                pass
    return 10.0


CameraStatus = Literal[
    "connecting", "connected", "degraded", "disconnected", "reconnecting"
]


@dataclass
class CameraRuntimeState:
    """Live runtime health and performance telemetry tracked per camera."""

    camera_id: str
    status: CameraStatus = "connecting"
    last_frame_at: datetime | None = None
    capture_fps: float = 0.0
    inference_fps: float = 0.0
    frame_count: int = 0
    dropped_frame_count: int = 0
    reconnect_count: int = 0
    latency_ms: float = 0.0
    error: str | None = None


class MultiCameraManager:
    """Owns one CameraSource per configured camera_id.

    Runs one capture thread per camera, maintains latest-frame-only buffering,
    executes automatic reconnect with capped exponential backoff, and feeds all
    frames in round-robin order into exactly ONE shared InferenceBackend instance.
    """

    def __init__(
        self,
        sources: Mapping[str, CameraSource],
        inference_backend: InferenceBackend,
        target_fps: float | None = None,
        time_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        on_inference: (
            Callable[
                [str, Frame, npt.NDArray[np.uint8], list[RawDetection], list[Any]], None
            ]
            | None
        ) = None,
    ) -> None:
        self.sources: dict[str, CameraSource] = dict(sources)
        self.inference_backend = inference_backend
        self.target_fps = (
            target_fps if target_fps is not None else _load_inference_target_fps()
        )
        self._time_fn: Callable[[], float] = time_fn if time_fn is not None else time.time
        self._sleep_fn: Callable[[float], None] = (
            sleep_fn if sleep_fn is not None else self._default_sleep
        )
        self._on_inference = on_inference

        self.capture_threads: dict[str, threading.Thread] = {}
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frames: dict[str, tuple[Frame, npt.NDArray[np.uint8]]] = {}
        self._has_unprocessed_frame: dict[str, bool] = {}
        self._latest_inferences: dict[str, tuple[Frame, list[RawDetection], list[Any]]] = {}
        self._runtime_states: dict[str, CameraRuntimeState] = {
            cam_id: CameraRuntimeState(camera_id=cam_id, status="connecting")
            for cam_id in self.sources
        }
        self._backoff_attempts: dict[str, int] = {}
        self._last_capture_time: dict[str, float] = {}
        self._last_inference_time: dict[str, float] = {}
        self._running = False
        self._trackers: dict[str, Any] = {}

    def _default_sleep(self, duration: float) -> None:
        self._stop_event.wait(timeout=duration)

    def get_runtime_state(self, camera_id: str) -> CameraRuntimeState | None:
        """Return the current runtime state for a specific camera."""
        with self._lock:
            return self._runtime_states.get(camera_id)

    def get_all_runtime_states(self) -> dict[str, CameraRuntimeState]:
        """Return a copy of all cameras' runtime states."""
        with self._lock:
            return dict(self._runtime_states)

    def get_latest_inference(
        self, camera_id: str
    ) -> tuple[Frame, list[RawDetection], list[Any]] | None:
        """Return the most recent inference result for a specific camera."""
        with self._lock:
            return self._latest_inferences.get(camera_id)

    def start(self) -> None:
        """Start one capture thread per camera source and the shared inference scheduler."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        now = self._time_fn()
        self._last_inference_time = dict.fromkeys(self.sources, now)

        for cam_id, source in self.sources.items():
            thread = threading.Thread(
                target=self._capture_loop,
                args=(cam_id, source),
                name=f"CaptureThread-{cam_id}",
                daemon=True,
            )
            self.capture_threads[cam_id] = thread
            thread.start()
            logger.info("Started capture thread for camera '%s'", cam_id)

        self._scheduler_thread = threading.Thread(
            target=self._inference_scheduler_loop,
            name="InferenceScheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        logger.info("Started inference scheduler thread (target_fps=%.1f)", self.target_fps)

    def _capture_step(self, camera_id: str, source: CameraSource) -> None:
        """Perform a single capture attempt with buffering, reconnect, and backoff."""
        if camera_id not in self._runtime_states:
            with self._lock:
                self._runtime_states[camera_id] = CameraRuntimeState(
                    camera_id=camera_id, status="connecting"
                )

        state = self._runtime_states[camera_id]
        try:
            res = source.get_frame()
            if res is not None:
                frame_meta, frame_pixels = res
                if frame_meta.camera_id != camera_id:
                    frame_meta = frame_meta.model_copy(update={"camera_id": camera_id})

                now = self._time_fn()
                with self._lock:
                    # Latest-frame-only buffering: drop older un-inferred frame
                    if self._has_unprocessed_frame.get(camera_id, False):
                        state.dropped_frame_count += 1

                    self._latest_frames[camera_id] = (frame_meta, frame_pixels)
                    self._has_unprocessed_frame[camera_id] = True
                    state.frame_count += 1
                    state.last_frame_at = frame_meta.timestamp
                    state.status = "connected"
                    state.error = None

                    last_t = self._last_capture_time.get(camera_id, 0.0)
                    if last_t > 0:
                        dt = now - last_t
                        if dt > 0:
                            inst_fps = 1.0 / dt
                            prev_cap = state.capture_fps
                            smoothed = 0.8 * prev_cap + 0.2 * inst_fps if prev_cap > 0 else inst_fps
                            state.capture_fps = round(smoothed, 1)
                    self._last_capture_time[camera_id] = now
                    self._backoff_attempts[camera_id] = 0
            else:
                self._handle_capture_failure(camera_id)
        except Exception as e:
            logger.warning("Capture error on camera '%s': %s", camera_id, e)
            self._handle_capture_failure(camera_id, error=str(e))

    def _handle_capture_failure(self, camera_id: str, error: str | None = None) -> None:
        """Handle missing frame or error with capped exponential backoff."""
        state = self._runtime_states[camera_id]
        attempt = self._backoff_attempts.get(camera_id, 0)

        with self._lock:
            state.error = error
            delay = get_backoff_delay(attempt)
            self._backoff_attempts[camera_id] = attempt + 1
            if attempt == 0:
                state.status = "disconnected"
            else:
                state.status = "reconnecting"
                state.reconnect_count += 1

        self._sleep_fn(delay)

    def _capture_loop(self, camera_id: str, source: CameraSource) -> None:
        """Worker loop capturing frames for a single camera into the manager's buffer."""
        while not self._stop_event.is_set():
            self._capture_step(camera_id, source)

    def _run_inference_cycle(self) -> bool:
        """Run one round-robin inference cycle across all cameras."""
        camera_keys = list(self.sources.keys())
        processed_any = False
        now = self._time_fn()
        min_interval = 1.0 / max(0.1, self.target_fps)

        for cam_id in camera_keys:
            if self._stop_event.is_set():
                break

            last_t = self._last_inference_time.get(cam_id, 0.0)
            if now - last_t < min_interval:
                continue

            frame_tuple: tuple[Frame, npt.NDArray[np.uint8]] | None = None
            with self._lock:
                if self._has_unprocessed_frame.get(cam_id, False) and cam_id in self._latest_frames:
                    frame_tuple = self._latest_frames[cam_id]
                    self._has_unprocessed_frame[cam_id] = False

            if frame_tuple is not None:
                processed_any = True
                frame_meta, frame_pixels = frame_tuple
                t0 = self._time_fn()
                try:
                    raw_dets = self.inference_backend.infer(frame_pixels)
                    lat_ms = (self._time_fn() - t0) * 1000.0

                    person_dets = [d for d in raw_dets if d.class_id == 0]
                    tracker = self.get_tracker(cam_id)
                    tracked = tracker.update(person_dets)

                    with self._lock:
                        self._latest_inferences[cam_id] = (frame_meta, raw_dets, tracked)
                        state = self._runtime_states[cam_id]
                        state.latency_ms = round(lat_ms, 1)

                        if last_t > 0:
                            dt = now - last_t
                            if dt > 0:
                                inst_fps = 1.0 / dt
                                prev_inf = state.inference_fps
                                smoothed = (
                                    0.8 * prev_inf + 0.2 * inst_fps if prev_inf > 0 else inst_fps
                                )
                                state.inference_fps = round(smoothed, 1)
                        self._last_inference_time[cam_id] = now

                    if self._on_inference is not None:
                        try:
                            self._on_inference(cam_id, frame_meta, frame_pixels, raw_dets, tracked)
                        except Exception as cb_err:
                            logger.warning(
                                "on_inference callback error for camera '%s': %s",
                                cam_id,
                                cb_err,
                            )
                except Exception as e:
                    logger.warning("Inference error for camera '%s': %s", cam_id, e)
                    with self._lock:
                        if cam_id in self._runtime_states:
                            self._runtime_states[cam_id].error = str(e)

        return processed_any

    def _inference_scheduler_loop(self) -> None:
        """Background thread scheduling inference across all cameras in round-robin order."""
        while not self._stop_event.is_set():
            processed = self._run_inference_cycle()
            if not processed:
                self._sleep_fn(0.005)

    def get_next_batch(self) -> list[tuple[str, Frame, npt.NDArray[np.uint8]]]:
        """Non-blocking: returns available fresh (camera_id, Frame, ndarray) tuples."""
        batch: list[tuple[str, Frame, npt.NDArray[np.uint8]]] = []

        if self._running:
            with self._lock:
                for cam_id in list(self._latest_frames.keys()):
                    frame_meta, frame_pixels = self._latest_frames[cam_id]
                    self._has_unprocessed_frame[cam_id] = False
                    batch.append((cam_id, frame_meta, frame_pixels))
        else:
            # Synchronous direct polling when capture threads are not started
            for cam_id, source in self.sources.items():
                res = source.get_frame()
                if res is not None:
                    frame_meta, frame_pixels = res
                    if frame_meta.camera_id != cam_id:
                        frame_meta = frame_meta.model_copy(update={"camera_id": cam_id})
                    batch.append((cam_id, frame_meta, frame_pixels))

        return batch

    def process_batch(
        self,
        batch: Sequence[tuple[str, Frame, npt.NDArray[np.uint8]]] | None = None,
    ) -> list[tuple[str, Frame, list[RawDetection]]]:
        """Run inference on a batch of frames using the single shared InferenceBackend."""
        target_batch = list(batch) if batch is not None else self.get_next_batch()
        results: list[tuple[str, Frame, list[RawDetection]]] = []
        for cam_id, frame_meta, frame_pixels in target_batch:
            raw_dets = self.inference_backend.infer(frame_pixels)
            results.append((cam_id, frame_meta, raw_dets))
        return results

    def get_tracker(self, camera_id: str) -> Any:
        """Return the independent tracker instance associated with a specific camera."""
        if camera_id not in self._trackers:
            from vision.tracker import Tracker

            self._trackers[camera_id] = Tracker()
        return self._trackers[camera_id]

    def close(self) -> None:
        """Release every owned CameraSource and cleanly stop capture threads and scheduler."""
        self._stop_event.set()
        self._running = False

        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=0.4)
        self._scheduler_thread = None

        for thread in self.capture_threads.values():
            if thread.is_alive():
                thread.join(timeout=0.4)
        self.capture_threads.clear()

        for cam_id, source in self.sources.items():
            try:
                source.close()
            except Exception as e:
                logger.warning("Error closing camera '%s': %s", cam_id, e)

        with self._lock:
            self._latest_frames.clear()
            self._has_unprocessed_frame.clear()

