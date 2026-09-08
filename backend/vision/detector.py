import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import numpy.typing as npt
from core.schemas import Detection

from vision.inference_backend import InferenceBackend, RawDetection

# Standard COCO classes frequently encountered in retail scenes
DEFAULT_COCO_RETAIL_CLASS_MAP: dict[int, str] = {
    0: "person",
    24: "backpack",
    26: "handbag",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot dog",
    53: "pizza",
    54: "donut",
    55: "cake",
    64: "potted plant",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "toothbrush",
}

# Open retail benchmark standard classes (e.g. SKU-110K / Retail-100)
OPEN_RETAIL_CLASS_MAP: dict[int, str] = {
    0: "person",
    1: "product",
    2: "cart",
    3: "basket",
}

# COCO class 0 is 'person'
PERSON_CLASS_ID = 0
PRODUCT_CLASS_ID = 1
CART_CLASS_ID = 2


@dataclass
class DetectionDiagnostics:
    """Telemetry diagnostics for inference and detection quality."""

    frame_count: int = 0
    last_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    counts_by_class: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    confidence_sum_by_class: dict[int, float] = field(default_factory=lambda: defaultdict(float))

    def record_frame(self, latency_ms: float, detections: list[RawDetection]) -> None:
        self.frame_count += 1
        self.last_latency_ms = latency_ms
        self.latencies_ms.append(latency_ms)
        if len(self.latencies_ms) > 1000:
            self.latencies_ms = self.latencies_ms[-1000:]
        sorted_lat = sorted(self.latencies_ms)
        self.p50_latency_ms = sorted_lat[len(sorted_lat) // 2]
        p95_idx = min(len(sorted_lat) - 1, int(len(sorted_lat) * 0.95))
        self.p95_latency_ms = sorted_lat[p95_idx]

        for d in detections:
            self.counts_by_class[d.class_id] += 1
            self.confidence_sum_by_class[d.class_id] += d.confidence

    def mean_confidence(self, class_id: int) -> float:
        count = self.counts_by_class.get(class_id, 0)
        if count == 0:
            return 0.0
        return self.confidence_sum_by_class.get(class_id, 0.0) / count


class YOLODetector:
    """Generic multi-class YOLO detector with per-class filtering and diagnostics."""

    def __init__(
        self,
        backend: InferenceBackend,
        class_map: dict[int, str] | None = None,
        conf_thresholds: dict[int, float] | None = None,
        default_conf_threshold: float = 0.4,
        target_classes: set[int] | None = None,
    ) -> None:
        self.backend = backend
        self.class_map = (
            class_map if class_map is not None else DEFAULT_COCO_RETAIL_CLASS_MAP.copy()
        )
        self.conf_thresholds = conf_thresholds or {}
        self.default_conf_threshold = default_conf_threshold
        self.target_classes = target_classes
        self.diagnostics = DetectionDiagnostics()

    def detect(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run inference and return filtered multi-class detections."""
        t0 = time.perf_counter()
        raw_detections = self.backend.infer(frame)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        filtered: list[RawDetection] = []
        for det in raw_detections:
            if self.target_classes is not None and det.class_id not in self.target_classes:
                continue
            threshold = self.conf_thresholds.get(det.class_id, self.default_conf_threshold)
            if det.confidence >= threshold:
                filtered.append(det)

        self.diagnostics.record_frame(latency_ms, filtered)
        return filtered

    def detect_typed(
        self,
        frame: npt.NDArray[np.uint8],
        timestamp: datetime | None = None,
    ) -> list[Detection]:
        """Run detection and return typed Pydantic Detection models."""
        ts = timestamp or datetime.now(UTC)
        raw = self.detect(frame)
        return [
            Detection(
                class_id=d.class_id,
                class_name=self.class_map.get(d.class_id, f"class_{d.class_id}"),
                confidence=d.confidence,
                bbox=d.bbox,
                timestamp=ts,
            )
            for d in raw
        ]


class PersonDetector(YOLODetector):
    """YOLO person detector wrapper producing person-only bounding boxes."""

    def __init__(
        self,
        backend: InferenceBackend,
        target_class_id: int = PERSON_CLASS_ID,
    ) -> None:
        super().__init__(
            backend=backend,
            target_classes={target_class_id},
        )
        self.target_class_id = target_class_id
