import uuid
from abc import ABC, abstractmethod
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt

from analytics.roi import crop_to_zone
from core.schemas import Frame, StockEvent, ZoneConfig


class ShelfClassifier(ABC):
    """Swap point, same philosophy as InferenceBackend in Slice 2 — the
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


def check_shelves(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    classifier: ShelfClassifier,
    shelf_zones: list[ZoneConfig],
    threshold: float = 0.5,
) -> list[StockEvent]:
    """Top-level entry point: crop each shelf zone, classify, emit StockEvents.

    threshold represents AppConfig.low_stock_confidence_threshold from Slice 0.
    """
    events: list[StockEvent] = []

    for zone in shelf_zones:
        if zone.zone_type != "shelf":
            continue

        crop = crop_to_zone(pixels, zone)
        status, confidence = classifier.classify(crop)

        events.append(
            StockEvent(
                event_id=f"stock_{uuid.uuid4().hex[:12]}",
                shelf_id=zone.zone_id,
                timestamp=frame.timestamp,
                status=status,
                confidence=confidence,
            )
        )

    return events
