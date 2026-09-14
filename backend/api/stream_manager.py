import contextlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt

from alerts.alert_engine import AlertEngine
from analytics.dwell import DwellTracker
from analytics.footfall import FootfallTracker
from analytics.queue_monitor import QueueMonitor
from analytics.shelf_classifier import (
    HybridShelfClassifier,
    ShelfClassifier,
    TemporalShelfSmoother,
)
from analytics.sku_classifier import sku_segregator
from api.dependencies import get_app_config, get_repository
from api.env_manager import read_env_file
from api.routes.ws import ws_manager
from core.schemas import Frame, QueueEvent, StockEvent, ZoneConfig
from vision.camera_base import CameraSource
from vision.camera_mesh import camera_mesh
from vision.detector import PersonDetector
from vision.http_source import HTTPSource
from vision.inference_backend import ONNXBackend
from vision.rtsp_source import RTSPSource, format_authenticated_rtsp_url, mask_rtsp_credentials
from vision.tracker import TrackedDetection, Tracker
from vision.usb_source import USBSource

logger = logging.getLogger(__name__)


def resolve_camera_source() -> str:
    """Resolve camera source from os.environ, .env file, then config.yaml, default to '0'."""
    if os.environ.get("CAMERA_SOURCE"):
        return os.environ["CAMERA_SOURCE"]
    env_vars = read_env_file()
    if "CAMERA_SOURCE" in env_vars and env_vars["CAMERA_SOURCE"]:
        return env_vars["CAMERA_SOURCE"]
    cfg = get_app_config()
    if cfg and cfg.camera and cfg.camera.source:
        return cfg.camera.source
    return "0"


def scale_zones_to_frame(zones: list[ZoneConfig], frame_w: int, frame_h: int) -> list[ZoneConfig]:
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


def generate_fallback_frame(src: str, width: int = 640, height: int = 480) -> npt.NDArray[np.uint8]:
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

    Uses a decoupled two-thread pipeline:
    1. _capture_loop: ingests frames from camera at native FPS into a reference slot.
    2. _inference_loop: runs throttled YOLO inference, ByteTrack, and analytics.
    """

    def __init__(self) -> None:
        self._slot_lock = threading.Lock()
        self._slot_frame: npt.NDArray[np.uint8] | None = None
        self._slot_meta: Frame | None = None
        self._frame_seq: int = 0

        self.active_src: str | None = None
        self.camera: CameraSource | None = None
        self.latest_tracked: list[TrackedDetection] = []
        self.width: int = 640
        self.height: int = 480
        self.is_connected: bool = False
        self.last_frame_time: float = 0.0

        self._shutdown_event = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._inference_thread: threading.Thread | None = None

        # Edge AI Pipeline Components
        self.detector: PersonDetector | None = None
        self.tracker: Tracker = Tracker()
        footfall_mode = os.environ.get("FOOTFALL_TRACKER_MODE", "directional")
        footfall_emit_on = os.environ.get("FOOTFALL_EMIT_ON", "zone_enter")
        self.footfall_tracker: FootfallTracker = (
            FootfallTracker(
                mode="directional",
                emit_on=("zone_enter" if footfall_emit_on == "zone_enter" else "zone_exit"),
            )
            if footfall_mode == "directional"
            else FootfallTracker(mode="edge")
        )
        self.dwell_tracker: DwellTracker = DwellTracker()
        self.queue_monitor: QueueMonitor = QueueMonitor(
            hourly_baseline_provider=lambda cid, hr: get_repository().get_hourly_queue_baseline(
                cid, hr
            )
        )
        self.shelf_classifier: ShelfClassifier = HybridShelfClassifier()
        self.shelf_smoother: TemporalShelfSmoother = TemporalShelfSmoother()
        self.alert_engine: AlertEngine = AlertEngine(
            low_stock_threshold=0.60,
            queue_congestion_length=4,
        )

        self.latest_stock_events: dict[str, StockEvent] = {}
        self.latest_queue_events: dict[str, QueueEvent] = {}
        self.latest_facings: dict[str, int] = {}

    def _ensure_workers_started(self) -> None:
        if self._capture_thread is None or not self._capture_thread.is_alive():
            self._shutdown_event.clear()
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()

        if self._inference_thread is None or not self._inference_thread.is_alive():
            self._inference_thread = threading.Thread(target=self._inference_loop, daemon=True)
            self._inference_thread.start()

    def _capture_loop(self) -> None:
        """Native-rate camera capture loop continuously updating the reference slot."""
        last_check_time = 0.0
        formatted_src = ""

        while not self._shutdown_event.is_set():
            try:
                now = time.monotonic()
                if now - last_check_time > 1.5 or not formatted_src:
                    target_src = resolve_camera_source()
                    env_vars = read_env_file()
                    rtsp_user = (
                        env_vars["RTSP_USERNAME"]
                        if "RTSP_USERNAME" in env_vars
                        else os.environ.get("RTSP_USERNAME")
                    )
                    rtsp_pass = (
                        env_vars["RTSP_PASSWORD"]
                        if "RTSP_PASSWORD" in env_vars
                        else os.environ.get("RTSP_PASSWORD")
                    )
                    formatted_src = format_authenticated_rtsp_url(target_src, rtsp_user, rtsp_pass)
                    if not camera_mesh.get_camera("cam_primary"):
                        camera_mesh.register_camera(
                            camera_id="cam_primary",
                            source=target_src,
                            role="entrance",
                            label="Primary Store Camera",
                            auto_start=False,
                        )
                    last_check_time = now

                # Initialize or swap camera if source changed
                if self.camera is None or self.active_src != formatted_src:
                    if self.camera is not None:
                        with contextlib.suppress(Exception):
                            self.camera.close()
                        self.camera = None

                    self.active_src = formatted_src
                    if formatted_src.startswith(("http://", "https://")):
                        self.camera = HTTPSource(
                            source_url=formatted_src,
                            source_id="cam_primary",
                            timeout_msec=3000,
                            initial_backoff_sec=1.5,
                            max_backoff_sec=10.0,
                            backoff_factor=2.0,
                            non_blocking=True,
                        )
                    elif (
                        formatted_src.startswith("rtsp://")
                        or formatted_src.startswith("rtsps://")
                    ):
                        self.camera = RTSPSource(
                            source_url=formatted_src,
                            source_id="cam_primary",
                            timeout_msec=2500,
                            initial_backoff_sec=2.0,
                            max_backoff_sec=15.0,
                            backoff_factor=2.0,
                            non_blocking=True,
                        )
                    elif formatted_src.isdigit():
                        self.camera = USBSource(device_index=int(formatted_src))
                    else:
                        self.camera = USBSource(device_index=formatted_src, loop=True, pace=True)

                if self._shutdown_event.is_set():
                    break

                res = self.camera.get_frame() if self.camera else None
                if self._shutdown_event.is_set():
                    break

                if res is not None:
                    meta, raw_bgr = res
                    with self._slot_lock:
                        self._slot_frame = raw_bgr
                        self._slot_meta = meta
                        self._frame_seq += 1
                        self.width = meta.width
                        self.height = meta.height
                        self.is_connected = True
                        self.last_frame_time = time.monotonic()
                    primary_node = camera_mesh.get_camera("cam_primary")
                    if primary_node:
                        primary_node.update_frame(raw_bgr, meta.width, meta.height)
                else:
                    with self._slot_lock:
                        if time.monotonic() - self.last_frame_time > 4.0:
                            self.is_connected = False
                            self._slot_frame = None
                            self._slot_meta = None
                    primary_node = camera_mesh.get_camera("cam_primary")
                    if primary_node and time.monotonic() - self.last_frame_time > 4.0:
                        primary_node.is_connected = False

                    # Responsive sleep that aborts immediately on shutdown
                    self._shutdown_event.wait(0.15)
            except Exception as e:
                if self._shutdown_event.is_set():
                    break
                logger.error("Capture loop error: %s", e)
                with self._slot_lock:
                    self.is_connected = False
                self._shutdown_event.wait(0.2)

    def _inference_loop(self) -> None:
        last_processed_seq = -1
        last_shelf_time = 0.0
        last_cfg_time = 0.0
        cached_cfg = get_app_config()
        repo = get_repository()
        env_vars = read_env_file()
        target_interval = 0.2
        shelf_interval = 30.0  # Fallback watchdog interval for event-driven shelf checks
        pending_shelf_eval_zones: set[str] = set()

        while not self._shutdown_event.is_set():
            try:
                now = time.monotonic()
                if now - last_cfg_time > 1.0:
                    cached_cfg = get_app_config()
                    env_vars = read_env_file()
                    target_fps = float(
                        env_vars.get("YOLO_INFERENCE_FPS")
                        or os.environ.get("YOLO_INFERENCE_FPS", "5.0")
                    )
                    target_interval = 1.0 / max(0.1, target_fps)
                    shelf_interval = float(
                        env_vars.get("SHELF_ANALYSIS_INTERVAL")
                        or os.environ.get("SHELF_ANALYSIS_INTERVAL", "30.0")
                    )
                    last_cfg_time = now

                # 1. Initialize YOLO detector once
                if self.detector is None:
                    model_env = env_vars.get("YOLO_MODEL") or os.environ.get("YOLO_MODEL")
                    if model_env:
                        cand_path = Path(model_env)
                        if not cand_path.is_file():
                            cand_path = Path(__file__).resolve().parent.parent / model_env
                        model_path = cand_path
                    else:
                        model_path = (
                            Path(__file__).resolve().parent.parent / "models" / "yolo26n.onnx"
                        )

                    # Fallbacks: try INT8 first, then FP32, then relative models/
                    if not model_path.is_file():
                        models_dir = Path(__file__).resolve().parent.parent / "models"
                        for fb in [
                            models_dir / "yolo26n_int8.onnx",
                            models_dir / "yolo26n.onnx",
                            Path("models/yolo26n_int8.onnx"),
                            Path("models/yolo26n.onnx"),
                        ]:
                            if fb.is_file():
                                logger.warning(
                                    "Configured YOLO model %s not found; falling back to %s",
                                    model_env,
                                    fb,
                                )
                                model_path = fb
                                break

                    if model_path.is_file():
                        input_size = int(
                            env_vars.get("YOLO_INPUT_SIZE")
                            or os.environ.get("YOLO_INPUT_SIZE", "640")
                        )
                        threads = int(
                            env_vars.get("YOLO_INTRA_OP_THREADS")
                            or os.environ.get("YOLO_INTRA_OP_THREADS", "3")
                        )
                        conf = float(
                            env_vars.get("DETECTION_CONFIDENCE_THRESHOLD")
                            or os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.40")
                        )
                        try:
                            backend = ONNXBackend(
                                model_path,
                                conf_threshold=conf,
                                input_size=(input_size, input_size),
                                intra_op_num_threads=threads,
                            )
                            self.detector = PersonDetector(backend)
                            logger.info(
                                "Initialized ONNX detector: %s (%dx%d, %d threads)",
                                model_path,
                                input_size,
                                input_size,
                                threads,
                            )
                        except Exception as e:
                            logger.error("Failed to load ONNX backend: %s", e)

                # 2. Extract latest frame reference under lock, release immediately
                curr_frame: npt.NDArray[np.uint8] | None = None
                curr_meta: Frame | None = None
                with self._slot_lock:
                    if (
                        self.is_connected
                        and self._frame_seq != last_processed_seq
                        and self._slot_frame is not None
                    ):
                        curr_frame = self._slot_frame
                        curr_meta = self._slot_meta
                        last_processed_seq = self._frame_seq

                if curr_frame is None or curr_meta is None:
                    time.sleep(0.08)
                    continue

                inf_start = time.monotonic()

                # 3. Person Detection & ByteTracking
                tracked_dets: list[TrackedDetection] = []
                if self.detector is not None:
                    try:
                        raw_dets = self.detector.detect(curr_frame)
                        tracked_dets = self.tracker.update(raw_dets)
                    except Exception as e:
                        logger.error("Detection/tracking error: %s", e)

                with self._slot_lock:
                    self.latest_tracked = tracked_dets

                # 4. Fetch zones and thresholds
                now = time.monotonic()
                if now - last_cfg_time >= 1.0:
                    last_cfg_time = now
                    cached_cfg = get_app_config()

                raw_zones = cached_cfg.zones if cached_cfg and cached_cfg.zones else []
                zones = scale_zones_to_frame(raw_zones, curr_meta.width, curr_meta.height)

                if "LOW_STOCK_CONFIDENCE_THRESHOLD" in env_vars:
                    with contextlib.suppress(Exception):
                        self.alert_engine.low_stock_threshold = float(
                            env_vars["LOW_STOCK_CONFIDENCE_THRESHOLD"]
                        )
                if "QUEUE_CONGESTION_LENGTH" in env_vars:
                    with contextlib.suppress(Exception):
                        self.alert_engine.queue_congestion_length = int(
                            env_vars["QUEUE_CONGESTION_LENGTH"]
                        )

                # 5. Workload A: People Analytics (Footfall, Dwell, Queue)
                if zones:
                    try:
                        footfall_events = self.footfall_tracker.update(
                            curr_meta, tracked_dets, zones
                        )
                        for ev in footfall_events:
                            repo.save_detection_event(ev)

                        dwell_events = self.dwell_tracker.update(footfall_events)
                        for d_ev in dwell_events:
                            repo.save_dwell_event(d_ev)
                            # Event-triggered shelf inspection: customer finished dwell in shelf
                            is_shelf = any(
                                z.zone_id == d_ev.zone_id and z.zone_type == "shelf"
                                for z in zones
                            )
                            if is_shelf:
                                pending_shelf_eval_zones.add(d_ev.zone_id)

                        if footfall_events:
                            enters = sum(1 for e in footfall_events if e.event_type == "enter")
                            exits = sum(1 for e in footfall_events if e.event_type == "exit")
                            ws_manager.broadcast_sync({
                                "type": "footfall",
                                "total_enters": enters,
                                "total_exits": exits,
                                "data": {
                                    "total_enters": enters,
                                    "total_exits": exits,
                                    "net_occupancy": max(0, enters - exits),
                                },
                            })
                    except Exception as e:
                        logger.error("Footfall/Dwell error: %s", e)

                    checkout_zones = [z for z in zones if z.zone_type == "checkout"]
                    if checkout_zones:
                        try:
                            q_events = self.queue_monitor.update(
                                curr_meta, tracked_dets, checkout_zones
                            )
                            had_q_alert = False
                            for q_ev in q_events:
                                prev_q = self.latest_queue_events.get(q_ev.counter_id)
                                q_changed = (
                                    prev_q is not None
                                    and prev_q.queue_length != q_ev.queue_length
                                )
                                self.latest_queue_events[q_ev.counter_id] = q_ev
                                if q_changed and (
                                    q_ev.queue_length > 0
                                    or (prev_q is not None and prev_q.queue_length > 0)
                                ):
                                    repo.save_queue_event(q_ev)
                                q_alert = self.alert_engine.process_queue_event(q_ev)
                                if q_alert:
                                    repo.upsert_alert(q_alert)
                                    had_q_alert = True

                            if q_events:
                                counters_payload = [
                                    {
                                        "counter_id": q.counter_id,
                                        "queue_length": q.queue_length,
                                        "avg_wait": q.avg_wait_est_sec,
                                    }
                                    for q in q_events
                                ]
                                ws_manager.broadcast_sync({
                                    "type": "queue",
                                    "counters": counters_payload,
                                    "data": counters_payload,
                                })
                                if had_q_alert:
                                    ws_manager.broadcast_sync({"type": "alerts_update"})
                        except Exception as e:
                            logger.error("Queue error: %s", e)

                # Broadcast real-time centroid coordinates for instant dwell heatmap accumulation
                if tracked_dets:
                    ws_manager.broadcast_sync({
                        "type": "dwell_points",
                        "points": [
                            {
                                "x": int(det.bbox[0] + det.bbox[2] / 2),
                                "y": int(det.bbox[1] + det.bbox[3] / 2),
                                "track_id": det.track_id,
                            }
                            for det in tracked_dets
                        ],
                    })

                # 6. Unified Shelf Stock & SKU Analysis: Event-Triggered + 30s Watchdog
                now = time.monotonic()
                shelf_zones = [z for z in zones if z.zone_type == "shelf"]
                is_watchdog_due = (now - last_shelf_time >= shelf_interval)
                has_pending = bool(pending_shelf_eval_zones)
                should_eval_shelves = bool(
                    self.is_connected
                    and curr_frame is not None
                    and shelf_zones
                    and (has_pending or is_watchdog_due)
                )

                if should_eval_shelves:
                    target_shelves = (
                        [z for z in shelf_zones if z.zone_id in pending_shelf_eval_zones]
                        if (pending_shelf_eval_zones and not is_watchdog_due)
                        else shelf_zones
                    )
                    pending_shelf_eval_zones.clear()
                    last_shelf_time = now

                    try:
                        mesh_frames = camera_mesh.get_active_frames()
                        frames_to_eval = list(mesh_frames)
                        if curr_frame is not None and not any(
                            cam_id == "cam_primary" for cam_id, _ in frames_to_eval
                        ):
                            frames_to_eval.insert(0, ("cam_primary", curr_frame))

                        if frames_to_eval:
                            sku_report = sku_segregator.evaluate_all_shelves(
                                frames_by_camera=frames_to_eval,
                                zones=target_shelves,
                                force=has_pending,
                            )
                            stock_events_emitted = []
                            for item in sku_report.items:
                                self.latest_facings[item.shelf_id] = item.facing_count
                                s_status: Literal["empty", "low", "ok"] = (
                                    "empty"
                                    if item.status == "empty"
                                    else ("low" if item.status == "low" else "ok")
                                )
                                prev_ev = self.latest_stock_events.get(item.shelf_id)
                                state_changed = prev_ev is not None and prev_ev.status != s_status

                                sku_ev = StockEvent(
                                    event_id=f"stk_ev_{item.shelf_id}_{int(time.time())}",
                                    shelf_id=item.shelf_id,
                                    timestamp=item.timestamp,
                                    status=s_status,
                                    confidence=item.confidence,
                                )
                                self.latest_stock_events[item.shelf_id] = sku_ev

                                if state_changed:
                                    repo.save_stock_event(sku_ev)
                                    stock_events_emitted.append(sku_ev)
                                    logger.info(
                                        "Shelf '%s' status transitioned: %s -> %s "
                                        "(facings: %d, confidence: %.2f)",
                                        item.shelf_id,
                                        prev_ev.status if prev_ev else "initial",
                                        s_status,
                                        item.facing_count,
                                        item.confidence,
                                    )

                                    sku_prof = sku_segregator.get_sku_for_zone(item.shelf_id)
                                    sku_name = item.detected_sku_name or (
                                        sku_prof.name if sku_prof else None
                                    )
                                    sku_id = item.detected_sku_id or (
                                        sku_prof.sku_id if sku_prof else None
                                    )
                                    # Only alert if custom SKU is registered or visually detected
                                    if sku_prof is not None or sku_id is not None:
                                        s_alert = self.alert_engine.process_stock_event(
                                            sku_ev,
                                            sku_name=sku_name,
                                            sku_id=sku_id,
                                            facing_count=item.facing_count,
                                        )
                                        if s_alert:
                                            repo.upsert_alert(s_alert)

                            resolved_alerts = self.alert_engine.check_resolutions(
                                self.latest_stock_events,
                                self.latest_queue_events,
                                latest_facings=self.latest_facings,
                            )
                            for res_alert in resolved_alerts:
                                repo.upsert_alert(res_alert)

                            if stock_events_emitted or resolved_alerts:
                                ws_manager.broadcast_sync({
                                    "type": "stock_update",
                                    "shelves": [s.shelf_id for s in stock_events_emitted],
                                    "data": [
                                        s.model_dump(mode="json")
                                        for s in self.latest_stock_events.values()
                                    ],
                                })
                                if resolved_alerts:
                                    ws_manager.broadcast_sync({"type": "alerts_update"})
                    except Exception as e:
                        logger.error("Unified shelf analysis error: %s", e)

                # 7. Flush pending audit trail events to repository
                with contextlib.suppress(Exception):
                    for audit_entry in self.alert_engine.pop_pending_audit_events():
                        repo.save_audit_event(audit_entry)

                # 9. Throttle inference loop to target FPS
                elapsed = time.monotonic() - inf_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0:
                    self._shutdown_event.wait(sleep_time)
            except Exception as e:
                if self._shutdown_event.is_set():
                    break
                logger.error("Inference loop error: %s", e)
                self._shutdown_event.wait(0.05)

    def is_stopped(self) -> bool:
        """Return whether background processing is shutting down or stopped."""
        return self._shutdown_event.is_set()

    def start(self) -> None:
        """Explicitly start background processing worker threads."""
        self._ensure_workers_started()

    def stop(self) -> None:
        """Gracefully stop background threads and release camera resources."""
        self._shutdown_event.set()
        if self.camera:
            with contextlib.suppress(Exception):
                self.camera.close()
            self.camera = None
        camera_mesh.close()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=0.5)
        self._capture_thread = None
        if self._inference_thread and self._inference_thread.is_alive():
            self._inference_thread.join(timeout=0.5)
        self._inference_thread = None

    def get_latest_frame(
        self,
        camera_id: str | None = None,
    ) -> tuple[bool, npt.NDArray[np.uint8] | None, list[TrackedDetection], int, int]:
        self._ensure_workers_started()
        if camera_id == "mosaic":
            mosaic = camera_mesh.generate_mosaic()
            return True, mosaic, [], mosaic.shape[1], mosaic.shape[0]

        if camera_id and camera_id not in ("cam_primary", "default", "primary"):
            is_conn, frame, w, h = camera_mesh.get_frame(camera_id)
            return is_conn, frame, [], w, h

        with self._slot_lock:
            frame_copy = self._slot_frame.copy() if self._slot_frame is not None else None
            return (
                self.is_connected,
                frame_copy,
                list(self.latest_tracked),
                self.width,
                self.height,
            )


# Global singleton StreamManager
stream_manager = StreamManager()
