import uuid
from abc import ABC, abstractmethod
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt
from core.schemas import Frame, ShelfOccupancyResult, StockEvent, ZoneConfig

from analytics.roi import crop_to_zone


class ShelfClassifier(ABC):
    """Swap point, same philosophy as InferenceBackend in Slice 2 -- the
    initial implementation can be simple (background subtraction / pixel
    density heuristic), a learned classifier can replace it later without
    touching callers.
    """

    @abstractmethod
    def classify(
        self, shelf_crop: npt.NDArray[np.uint8]
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        """Return (status, confidence)."""
        ...


class EdgeDensityShelfClassifier(ShelfClassifier):
    """Heuristic shelf classifier using Canny edge pixel density.

    Stocked shelves have rich texture and high edge count from product packaging,
    labels, and barcode lines. Empty shelves present smooth surfaces with near-zero
    edge density. Low-stock shelves present intermediate edge density.
    """

    def __init__(
        self,
        empty_threshold: float = 0.008,
        low_threshold: float = 0.035,
        canny_low: int = 50,
        canny_high: int = 150,
    ) -> None:
        self.empty_threshold = empty_threshold
        self.low_threshold = low_threshold
        self.canny_low = canny_low
        self.canny_high = canny_high

    def classify(
        self, shelf_crop: npt.NDArray[np.uint8]
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        if shelf_crop.size == 0 or shelf_crop.shape[0] == 0 or shelf_crop.shape[1] == 0:
            return "empty", 0.0

        gray = (
            cv2.cvtColor(shelf_crop, cv2.COLOR_BGR2GRAY)
            if shelf_crop.ndim == 3
            else shelf_crop
        )

        edges = cv2.Canny(gray, self.canny_low, self.canny_high)
        total_pixels = edges.size
        if total_pixels == 0:
            return "empty", 0.0

        edge_density = float(np.count_nonzero(edges)) / float(total_pixels)

        if edge_density <= self.empty_threshold:
            # Empty status: confidence near 1.0 when edge_density near 0.0
            ratio = edge_density / max(1e-6, self.empty_threshold)
            confidence = max(0.5, min(1.0, 1.0 - ratio * 0.5))
            return "empty", float(confidence)

        if edge_density < self.low_threshold:
            # Low status: confidence highest around midpoint of [empty_threshold, low_threshold]
            mid = (self.empty_threshold + self.low_threshold) / 2.0
            span = max(1e-6, (self.low_threshold - self.empty_threshold) / 2.0)
            confidence = max(0.5, min(1.0, 1.0 - (abs(edge_density - mid) / span) * 0.4))
            return "low", float(confidence)

        # OK status: confidence scales from 0.5 up to 1.0
        target = self.low_threshold * 2.0
        ratio = (edge_density - self.low_threshold) / max(1e-6, target - self.low_threshold)
        confidence = max(0.5, min(1.0, 0.5 + 0.5 * ratio))
        return "ok", float(confidence)


def _count_detections_in_zone(
    detections: list[tuple[int, int, int, int]],
    zone: ZoneConfig,
) -> int:
    """Count how many detection centroids fall within zone polygon (spatial ROI filter).

    Args:
        detections: List of (x, y, w, h) bounding boxes.
        zone: Zone whose polygon defines the spatial boundary.

    Returns:
        Count of detections whose centroid lies inside or on the polygon boundary.
    """
    if not detections:
        return 0
    poly = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
    count = 0
    for x, y, w, h in detections:
        cx = float(x + w / 2.0)
        cy = float(y + h / 2.0)
        # pointPolygonTest >= 0 means inside or on boundary
        if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
            count += 1
    return count


class ProductOccupancyShelfClassifier(ShelfClassifier):
    """Detection-based shelf classifier with temporal smoothing.

    Criteria:
    - Counts detected products whose centroids lie inside the configured shelf ROI polygon.
    - Computes occupancy = products_in_roi / capacity.
    - Applies rolling window smoothing (median) across frames to avoid single-frame flickering.
    - Emits robust ShelfOccupancyResult (empty, low, ok) with confidence.
    - Integrates with edge-density heuristic as fallback when no detections are present.
    """

    def __init__(
        self,
        capacity: int = 5,
        empty_threshold: float = 0.05,
        low_threshold: float = 0.35,
        smoothing_window: int = 5,
        fallback_classifier: ShelfClassifier | None = None,
    ) -> None:
        self.capacity = max(1, capacity)
        self.empty_threshold = empty_threshold
        self.low_threshold = low_threshold
        self.smoothing_window = max(1, smoothing_window)
        self.fallback = fallback_classifier or EdgeDensityShelfClassifier()
        self._history: dict[str, list[float]] = {}

    def reset(self) -> None:
        """Reset rolling history (use between evaluation scenarios)."""
        self._history.clear()

    def classify_occupancy(
        self,
        shelf_id: str,
        product_count: int,
        capacity: int | None = None,
    ) -> ShelfOccupancyResult:
        """Classify shelf based on product count inside ROI with temporal smoothing."""
        cap = capacity if capacity is not None and capacity > 0 else self.capacity
        raw_occupancy = min(1.0, max(0.0, float(product_count) / float(cap)))

        if shelf_id not in self._history:
            self._history[shelf_id] = []
        self._history[shelf_id].append(raw_occupancy)
        if len(self._history[shelf_id]) > self.smoothing_window:
            self._history[shelf_id] = self._history[shelf_id][-self.smoothing_window :]

        smoothed_occ = float(np.median(self._history[shelf_id]))

        # Confidence: higher when temporal variance is low
        history_len = len(self._history[shelf_id])
        variance = float(np.var(self._history[shelf_id])) if history_len > 1 else 0.0
        stability_conf = max(0.5, min(1.0, 1.0 - variance * 2.0))

        if smoothed_occ <= self.empty_threshold:
            status: Literal["empty", "low", "ok"] = "empty"
        elif smoothed_occ <= self.low_threshold:
            status = "low"
        else:
            status = "ok"

        return ShelfOccupancyResult(
            shelf_id=shelf_id,
            status=status,
            confidence=stability_conf,
            occupancy=smoothed_occ,
        )

    def classify_occupancy_from_detections(
        self,
        shelf_id: str,
        detections: list[tuple[int, int, int, int]],
        zone: ZoneConfig,
        capacity: int | None = None,
    ) -> ShelfOccupancyResult:
        """Classify shelf by spatial ROI filtering of raw detection bboxes."""
        count = _count_detections_in_zone(detections, zone)
        return self.classify_occupancy(shelf_id, count, capacity)

    def classify(
        self, shelf_crop: npt.NDArray[np.uint8]
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        """Fallback implementation using image crop."""
        return self.fallback.classify(shelf_crop)


def check_shelves(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    classifier: ShelfClassifier,
    shelf_zones: list[ZoneConfig],
    threshold: float = 0.5,
    product_counts_by_shelf: dict[str, int] | None = None,
) -> list[StockEvent]:
    """Top-level entry point: evaluate each shelf zone, classify, emit StockEvents.

    Supports both pixel-crop classification and product-occupancy detection counting.
    When classifier is ProductOccupancyShelfClassifier and product_counts_by_shelf
    is provided, uses detection-based occupancy. Otherwise falls back to pixel crop.
    """
    events: list[StockEvent] = []

    for zone in shelf_zones:
        if zone.zone_type != "shelf":
            continue

        occupancy: float | None = None
        if (
            isinstance(classifier, ProductOccupancyShelfClassifier)
            and product_counts_by_shelf is not None
            and zone.zone_id in product_counts_by_shelf
        ):
            count = product_counts_by_shelf[zone.zone_id]
            result = classifier.classify_occupancy(zone.zone_id, count)
            status, confidence, occupancy = result.status, result.confidence, result.occupancy
        else:
            crop = crop_to_zone(pixels, zone)
            status, confidence = classifier.classify(crop)

        events.append(
            StockEvent(
                event_id=f"stock_{uuid.uuid4().hex[:12]}",
                shelf_id=zone.zone_id,
                timestamp=frame.timestamp,
                status=status,
                confidence=confidence,
                occupancy=occupancy,
            )
        )

    return events
