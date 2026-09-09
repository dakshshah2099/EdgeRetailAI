import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
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


class HybridShelfClassifier(ShelfClassifier):
    """Hybrid shelf classifier fusing Canny edge density with HSV color/texture variance.

    Packaging presents varied hue and saturation gradients in addition to sharp
    edges. Plain/empty shelving surfaces exhibit low edge density AND near-zero
    color variance. Blending both signals suppresses glare, lighting shifts, and
    uniform background reflections.
    """

    def __init__(
        self,
        empty_score_threshold: float = 0.12,
        low_score_threshold: float = 0.55,
        canny_low: int = 50,
        canny_high: int = 150,
    ) -> None:
        self.empty_score_threshold = empty_score_threshold
        self.low_score_threshold = low_score_threshold
        self.canny_low = canny_low
        self.canny_high = canny_high

    def classify(
        self, shelf_crop: npt.NDArray[np.uint8]
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        if shelf_crop.size == 0 or shelf_crop.shape[0] == 0 or shelf_crop.shape[1] == 0:
            return "empty", 0.0

        # 1. Edge density component
        gray = (
            cv2.cvtColor(shelf_crop, cv2.COLOR_BGR2GRAY)
            if shelf_crop.ndim == 3
            else shelf_crop
        )
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)
        edge_density = float(np.count_nonzero(edges)) / float(max(1, edges.size))
        edge_score = min(1.0, edge_density / 0.07)

        # 2. Color texture variance component
        if shelf_crop.ndim == 3:
            hsv = cv2.cvtColor(shelf_crop, cv2.COLOR_BGR2HSV)
            sat_std = float(np.std(hsv[:, :, 1]))
            val_std = float(np.std(hsv[:, :, 2]))
            color_score = min(1.0, (sat_std / 60.0) * 0.6 + (val_std / 50.0) * 0.4)
        else:
            val_std = float(np.std(gray))
            color_score = min(1.0, val_std / 50.0)

        # 3. Combined metric (65% structural edges, 35% chromatic entropy)
        combined_score = 0.65 * edge_score + 0.35 * color_score

        if combined_score <= self.empty_score_threshold:
            ratio = combined_score / max(1e-6, self.empty_score_threshold)
            confidence = max(0.5, min(1.0, 1.0 - ratio * 0.4))
            return "empty", float(confidence)

        if combined_score < self.low_score_threshold:
            mid = (self.empty_score_threshold + self.low_score_threshold) / 2.0
            span = max(1e-6, (self.low_score_threshold - self.empty_score_threshold) / 2.0)
            confidence = max(0.5, min(1.0, 1.0 - (abs(combined_score - mid) / span) * 0.35))
            return "low", float(confidence)

        ratio = (combined_score - self.low_score_threshold) / max(
            1e-6, 1.0 - self.low_score_threshold
        )
        confidence = max(0.5, min(1.0, 0.6 + 0.4 * ratio))
        return "ok", float(confidence)


class TemporalShelfSmoother:
    """Maintains exponential moving average (EMA) stock fill scores per shelf
    and holds previous classification when a shopper occludes the shelf zone."""

    _STATUS_SCORE = {"empty": 0.0, "low": 0.5, "ok": 1.0}

    def __init__(self, alpha: float = 0.25) -> None:
        self.alpha = alpha
        # Mapping: shelf_id -> (last_status, last_confidence, smoothed_fill_score)
        self._states: dict[str, tuple[Literal["empty", "low", "ok"], float, float]] = {}

    def reset(self) -> None:
        self._states.clear()

    def is_occluded(
        self,
        shelf_zone: ZoneConfig,
        tracked_detections: Sequence[object] | None,
    ) -> bool:
        """Return True if any detected person bbox overlaps or is inside the shelf zone."""
        if not tracked_detections:
            return False

        from analytics.zone_membership import anchor_point, is_inside_zone

        for det in tracked_detections:
            bbox = getattr(det, "bbox", None)
            if bbox is None:
                continue
            # Check bottom-center feet and bbox center
            feet = anchor_point(bbox)
            center = (float(bbox[0] + bbox[2] / 2.0), float(bbox[1] + bbox[3] / 2.0))
            if is_inside_zone(feet, shelf_zone) or is_inside_zone(center, shelf_zone):
                return True
        return False

    def update(
        self,
        shelf_id: str,
        instant_status: Literal["empty", "low", "ok"],
        instant_confidence: float,
        is_occluded: bool,
    ) -> tuple[Literal["empty", "low", "ok"], float]:
        """Update EMA smoothed fill score or hold state on shopper occlusion."""
        if is_occluded and shelf_id in self._states:
            # Shopper occlusion hold: freeze previous known state
            last_status, last_conf, _ = self._states[shelf_id]
            return last_status, last_conf

        target_score = self._STATUS_SCORE[instant_status]
        if shelf_id not in self._states:
            smoothed = target_score
        else:
            _, _, prev_smoothed = self._states[shelf_id]
            smoothed = self.alpha * target_score + (1.0 - self.alpha) * prev_smoothed

        if smoothed < 0.25:
            resolved_status: Literal["empty", "low", "ok"] = "empty"
        elif smoothed < 0.75:
            resolved_status = "low"
        else:
            resolved_status = "ok"

        # Blend instant confidence with stability
        resolved_confidence = float(max(0.5, min(1.0, instant_confidence)))
        self._states[shelf_id] = (resolved_status, resolved_confidence, smoothed)
        return resolved_status, resolved_confidence


_default_shelf_smoother = TemporalShelfSmoother()


def check_shelves(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    classifier: ShelfClassifier,
    shelf_zones: list[ZoneConfig],
    threshold: float = 0.5,
    tracked_detections: Sequence[object] | None = None,
    smoother: TemporalShelfSmoother | None = None,
) -> list[StockEvent]:
    """Top-level entry point: crop each shelf zone, classify, apply occlusion
    hold and temporal smoothing, then emit StockEvents.

    threshold represents AppConfig.low_stock_confidence_threshold from Slice 0.
    """
    events: list[StockEvent] = []

    for zone in shelf_zones:
        if zone.zone_type != "shelf":
            continue

        crop = crop_to_zone(pixels, zone)
        status, confidence = classifier.classify(crop)

        if smoother is not None:
            is_occ = smoother.is_occluded(zone, tracked_detections)
            status, confidence = smoother.update(zone.zone_id, status, confidence, is_occ)

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
