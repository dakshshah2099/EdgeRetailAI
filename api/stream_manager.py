import contextlib
import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from alerts.alert_engine import AlertEngine
from api.dependencies import get_app_config, get_repository
from api.env_manager import read_env_file
from camera.base import CameraSource
from camera.rtsp_source import RTSPSource, format_authenticated_rtsp_url, mask_rtsp_credentials
from camera.usb_source import USBSource
from detection.detector import PersonDetector
from detection.dwell import DwellTracker
from detection.footfall import FootfallTracker
from detection.inference_backend import ONNXBackend
from detection.tracker import TrackedDetection, Tracker
from inventory.shelf_classifier import EdgeDensityShelfClassifier, check_shelves
from queue_intel.queue_monitor import QueueMonitor
from schemas import QueueEvent, StockEvent, ZoneConfig

logger = logging.getLogger(__name__)


def resolve_camera_source() -> str:
    """Resolve camera source from .env first, then config.yaml, default to '0'."""
    env_vars = read_env_file()
    if "CAMERA_SOURCE" in env_vars and env_vars["CAMERA_SOURCE"]:
        return env_vars["CAMERA_SOURCE"]
    cfg = get_app_config()
    if cfg and cfg.camera and cfg.camera.source:
        return cfg.camera.source
    return os.environ.get("CAMERA_SOURCE", "0")


def scale_zones_to_frame(
    zones: list[ZoneConfig], frame_w: int, frame_h: int
) -> list[ZoneConfig]:
    """Proportionally scale zone polygon vertices to the actual video frame resolution."""
    if not zones or frame_w <= 0 or frame_h <= 0:
        return zones

    max_x = max((p[0] for z in zones for p in z.polygon), default=640)
    max_y = max((p[1] for z in zones for p in z.polygon), default=480)
    base_w = max(640, int(max_x))
    base_h = max(480, int(max_y))

    if base_w == frame_w and base_h == frame_h:
        return zones

    scaled_zones: list[ZoneConfig] = []
    for z in zones:
        scaled_poly = [
            (
                int(max(0, min(frame_w - 1, round(p[0] * frame_w / base_w)))),
                int(max(0, min(frame_h - 1, round(p[1] * frame_h / base_h)))),
            )
            for p in z.polygon
        ]
        scaled_zones.append(
            ZoneConfig(
                zone_id=z.zone_id,
                zone_type=z.zone_type,
                polygon=scaled_poly,
                label=z.label,
            )
        )
    return scaled_zones


def generate_fallback_frame(
    src: str, width: int = 640, height: int = 480
) -> npt.NDArray[np.uint8]:
    """Generate a clean synthetic standby canvas when camera stream is disconnected."""
    img = np.full((height, width, 3), 24, dtype=np.uint8)
    masked_src = mask_rtsp_credentials(src)

    # Draw subtle grid
    grid_size = 40
    for x in range(0, width, grid_size):
        cv2.line(img, (x, 0), (x, height), (38, 42, 53), 1)
    for y in range(0, height, grid_size):
        cv2.line(img, (0, y), (width, y), (38, 42, 53), 1)

    # Status text overlay
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(
        img,
        "EDGE RETAIL AI - CAMERA FEED",
        (30, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        img, f"Source: {masked_src}", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 175, 200), 1
    )
    cv2.putText(
        img, f"Time:   {now_str}", (30, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 175, 200), 1
    )

    # Center standby notice
    box_p1 = (width // 2 - 180, height // 2 - 35)
    box_p2 = (width // 2 + 180, height // 2 + 35)
    cv2.rectangle(img, box_p1, box_p2, (35, 40, 55), -1)
    cv2.rectangle(img, box_p1, box_p2, (220, 80, 80), 1)
    cv2.putText(
        img,
        "Connecting to video feed...",
        (width // 2 - 150, height // 2 + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (220, 220, 220),
        2,
    )

    return img


def draw_zones_overlay(
    frame_bgr: npt.NDArray[np.uint8], config_path: str = "config.yaml"
) -> npt.NDArray[np.uint8]:
    """Draw configured zone polygons and labels onto a copy of the frame."""
    cfg = get_app_config(config_path)
    if not cfg or not cfg.zones:
        return frame_bgr

    annotated = frame_bgr.copy()
    overlay = annotated.copy()
    h, w = frame_bgr.shape[:2]
    zones = scale_zones_to_frame(cfg.zones, w, h)

    for zone in zones:
        pts = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
        if zone.zone_type == "entry_exit":
            color = (34, 197, 94)  # Green
        elif zone.zone_type == "shelf":
            color = (245, 158, 11)  # Amber in BGR
        elif zone.zone_type == "checkout":
            color = (59, 130, 246)  # Orange in BGR
        else:
            color = (168, 85, 247)  # Purple

        # Fill transparent polygon
        cv2.fillPoly(overlay, [pts], color)
        # Stroke border
        cv2.polylines(annotated, [pts], isClosed=True, color=color, thickness=2)

        # Label position
        label_pos = (int(zone.polygon[0][0]), max(20, int(zone.polygon[0][1]) - 8))
        label_text = f"{zone.label} ({zone.zone_type})"
        cv2.putText(
            annotated, label_text, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
        )

    # Blend overlay with 18% alpha
    cv2.addWeighted(overlay, 0.18, annotated, 0.82, 0, annotated)
    return annotated


def draw_tracked_overlay(
    frame_bgr: npt.NDArray[np.uint8], tracked_detections: list[TrackedDetection]
) -> npt.NDArray[np.uint8]:
    """Draw tracked person bounding boxes with track IDs on a copy of the frame."""
    annotated = frame_bgr.copy()
    for det in tracked_detections:
        bx, by, bw, bh = det.bbox
        cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), (0, 255, 128), 2)
        label = f"#{det.track_id} ({det.confidence:.2f})"
        cv2.putText(
            annotated,
            label,
            (bx, max(16, by - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 128),
            1,
            cv2.LINE_AA,
        )
    return annotated


class StreamManager:
    """Background real-time AI analytics engine and thread-safe frame buffer.

    Continuously ingests camera frames, runs YOLO detection, ByteTracking,
    footfall line counting, dwell tracking, queue monitoring, shelf analysis,
    and alert generation, saving live analytics directly to retail.db.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active_src: str | None = None
        self.camera: CameraSource | None = None
        self.latest_frame: npt.NDArray[np.uint8] | None = None
        self.latest_tracked: list[TrackedDetection] = []
        self.width: int = 640
        self.height: int = 480
        self.is_connected: bool = False
        self.last_frame_time: float = 0.0
        self.running: bool = True
        self.worker_thread: threading.Thread | None = None

        # Edge AI Pipeline Components
        self.detector: PersonDetector | None = None
        self.tracker: Tracker = Tracker()
        self.footfall_tracker: FootfallTracker = FootfallTracker()
        self.dwell_tracker: DwellTracker = DwellTracker()
        self.queue_monitor: QueueMonitor = QueueMonitor()
        self.shelf_classifier: EdgeDensityShelfClassifier = EdgeDensityShelfClassifier()
        self.alert_engine: AlertEngine = AlertEngine(
            low_stock_threshold=0.60,
            queue_congestion_length=4,
        )

        self.latest_stock_events: dict[str, StockEvent] = {}
        self.latest_queue_events: dict[str, QueueEvent] = {}
        self.frame_count: int = 0
        # Worker is started lazily on first access to get_latest_frame() or explicit start()

    def _ensure_worker_started(self) -> None:
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

    def _worker_loop(self) -> None:
        while self.running:
            try:
                target_src = resolve_camera_source()
                env_vars = read_env_file()
                rtsp_user = env_vars.get("RTSP_USERNAME") or os.environ.get("RTSP_USERNAME")
                rtsp_pass = env_vars.get("RTSP_PASSWORD") or os.environ.get("RTSP_PASSWORD")
                formatted_src = format_authenticated_rtsp_url(target_src, rtsp_user, rtsp_pass)

                # Initialize or swap camera if source changed
                if self.camera is None or self.active_src != formatted_src:
                    if self.camera is not None:
                        with contextlib.suppress(Exception):
                            self.camera.close()
                        self.camera = None

                    self.active_src = formatted_src
                    if (
                        formatted_src.startswith("rtsp://")
                        or formatted_src.startswith("rtsps://")
                        or formatted_src.startswith("http://")
                    ):
                        self.camera = RTSPSource(
                            source_url=formatted_src,
                            timeout_msec=2000,
                            non_blocking=True,
                        )
                    elif formatted_src.isdigit():
                        self.camera = USBSource(device_index=int(formatted_src))
                    else:
                        self.camera = USBSource(device_index=formatted_src, loop=True)

                # Read next frame
                res = self.camera.get_frame()
                if res is not None:
                    meta, raw_bgr = res

                    # 1. Initialize YOLO detector if needed
                    if self.detector is None:
                        model_path = Path("models/yolo26n.onnx")
                        if model_path.is_file():
                            try:
                                backend = ONNXBackend(model_path)
                                self.detector = PersonDetector(backend)
                            except Exception as e:
                                logger.error("Failed to load YOLO backend: %s", e)

                    # 2. Run Person Detection and ByteTrack
                    tracked_dets: list[TrackedDetection] = []
                    if self.detector is not None:
                        try:
                            raw_dets = self.detector.detect(raw_bgr)
                            tracked_dets = self.tracker.update(raw_dets)
                        except Exception as e:
                            logger.error("Detection/tracking error: %s", e)

                    # 3. Update active zone configurations and thresholds
                    repo = get_repository()
                    cfg = get_app_config()
                    raw_zones = cfg.zones if cfg and cfg.zones else []
                    zones = scale_zones_to_frame(raw_zones, meta.width, meta.height)

                    try:
                        if "LOW_STOCK_CONFIDENCE_THRESHOLD" in env_vars:
                            self.alert_engine.low_stock_threshold = float(
                                env_vars["LOW_STOCK_CONFIDENCE_THRESHOLD"]
                            )
                        if "QUEUE_CONGESTION_LENGTH" in env_vars:
                            self.alert_engine.queue_congestion_length = int(
                                env_vars["QUEUE_CONGESTION_LENGTH"]
                            )
                    except Exception:
                        pass

                    # 4. Process Footfall & Dwell Analytics
                    if zones:
                        try:
                            footfall_events = self.footfall_tracker.update(
                                meta, tracked_dets, zones
                            )
                            for ev in footfall_events:
                                repo.save_detection_event(ev)

                            dwell_events = self.dwell_tracker.update(footfall_events)
                            for d_ev in dwell_events:
                                repo.save_dwell_event(d_ev)
                        except Exception as e:
                            logger.error("Footfall/Dwell error: %s", e)

                        # 6. Process Queue Monitoring (for checkout zones)
                        checkout_zones = [z for z in zones if z.zone_type == "checkout"]
                        if checkout_zones:
                            try:
                                q_events = self.queue_monitor.update(
                                    meta, tracked_dets, checkout_zones
                                )
                                for q_ev in q_events:
                                    repo.save_queue_event(q_ev)
                                    self.latest_queue_events[q_ev.counter_id] = q_ev
                                    q_alert = self.alert_engine.process_queue_event(q_ev)
                                    if q_alert:
                                        repo.upsert_alert(q_alert)
                            except Exception as e:
                                logger.error("Queue error: %s", e)

                        # 7. Process Shelf Stock Analytics (every 30 frames ~ 1-2 sec)
                        self.frame_count += 1
                        if self.frame_count % 30 == 0:
                            shelf_zones = [z for z in zones if z.zone_type == "shelf"]
                            if shelf_zones:
                                try:
                                    stock_events = check_shelves(
                                        frame=meta,
                                        pixels=raw_bgr,
                                        classifier=self.shelf_classifier,
                                        shelf_zones=shelf_zones,
                                    )
                                    for s_ev in stock_events:
                                        repo.save_stock_event(s_ev)
                                        self.latest_stock_events[s_ev.shelf_id] = s_ev
                                        s_alert = self.alert_engine.process_stock_event(s_ev)
                                        if s_alert:
                                            repo.upsert_alert(s_alert)
                                except Exception as e:
                                    logger.error("Shelf error: %s", e)

                            # 8. Check for Alert Resolutions
                            try:
                                resolved_alerts = self.alert_engine.check_resolutions(
                                    self.latest_stock_events, self.latest_queue_events
                                )
                                for res_alert in resolved_alerts:
                                    repo.upsert_alert(res_alert)
                            except Exception as e:
                                logger.error("Alert resolution error: %s", e)

                    # Update thread-safe latest display state
                    with self.lock:
                        self.latest_frame = raw_bgr.copy()
                        self.latest_tracked = tracked_dets
                        self.width = meta.width
                        self.height = meta.height
                        self.is_connected = True
                        self.last_frame_time = time.monotonic()
                else:
                    with self.lock:
                        if time.monotonic() - self.last_frame_time > 4.0:
                            self.is_connected = False
            except Exception as e:
                logger.error("Stream worker error: %s", e)
                with self.lock:
                    self.is_connected = False

            # Run camera loop at ~30 FPS
            time.sleep(0.033)

    def start(self) -> None:
        """Explicitly start background processing worker thread."""
        self._ensure_worker_started()

    def get_latest_frame(
        self,
    ) -> tuple[bool, npt.NDArray[np.uint8] | None, list[TrackedDetection], int, int]:
        self._ensure_worker_started()
        with self.lock:
            return (
                self.is_connected,
                self.latest_frame,
                self.latest_tracked,
                self.width,
                self.height,
            )


# Global singleton StreamManager
stream_manager = StreamManager()
