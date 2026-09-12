import logging
import time
from datetime import UTC, datetime
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt

from analytics.roi import crop_to_zone
from api.schemas_api import SKUProfile, SKUSegregationItem, SKUSegregationReport
from core.schemas import ZoneConfig

logger = logging.getLogger(__name__)

# Mandatory edge cadence lock: minimum 10.0 seconds between SKU passes on RPi 4B
MIN_CADENCE_SECONDS: float = 10.0


class SKURef:
    """Internal representation of a catalog SKU with computed color-texture descriptor."""

    def __init__(
        self,
        sku_id: str,
        name: str,
        brand: str,
        expected_zone_id: str,
        category: str = "general",
        hist: npt.NDArray[np.float32] | None = None,
        base_hsv: tuple[int, int, int] | None = None,
    ) -> None:
        self.sku_id = sku_id
        self.name = name
        self.brand = brand
        self.expected_zone_id = expected_zone_id
        self.category = category
        self.hist = hist if hist is not None else self._synthesize_prototype(base_hsv)

    def _synthesize_prototype(
        self, base_hsv: tuple[int, int, int] | None = None
    ) -> npt.NDArray[np.float32]:
        """Synthesize prototypical HSV histogram when no sample image provided."""
        h_bins, s_bins = 8, 8
        hist = np.zeros((h_bins, s_bins), dtype=np.float32)

        if base_hsv is not None:
            h_idx = min(h_bins - 1, int(base_hsv[0] * h_bins / 180))
            s_idx = min(s_bins - 1, int(base_hsv[1] * s_bins / 256))
        elif "bev" in self.sku_id or "cola" in self.sku_id:
            # Dark red / ruby tones
            h_idx, s_idx = 0, 6
        elif "snack" in self.sku_id or "chip" in self.sku_id:
            # Warm yellow / gold tones
            h_idx, s_idx = 1, 6
        elif "elec" in self.sku_id or "tech" in self.sku_id:
            # Cool blue / cyan tones
            h_idx, s_idx = 5, 5
        else:
            # Neutral / mid green
            h_idx, s_idx = 3, 4

        hist[h_idx, s_idx] = 1.0
        # Add smooth gaussian spread around center
        blurred = cv2.GaussianBlur(hist, (3, 3), 0.8)
        norm = float(cv2.norm(blurred))
        if norm > 0:
            return (blurred / norm).astype(np.float32)
        return blurred.astype(np.float32)


class SKUSegregator:
    """Decoupled edge SKU classifier for 480p multi-camera shelf inspection."""

    def __init__(self, interval_seconds: float = 10.0) -> None:
        self.interval_seconds = max(MIN_CADENCE_SECONDS, float(interval_seconds))
        self._catalog: dict[str, SKURef] = {}
        self._zone_expected_sku: dict[str, str] = {}
        self._last_eval_time: float = 0.0
        self._last_report: SKUSegregationReport | None = None

        self._seed_default_catalog()

    def _seed_default_catalog(self) -> None:
        """Seed retail catalog matching the default store layout."""
        self.register_sku(
            sku_id="sku_bev_cola_330",
            name="Classic Cola Can 330ml",
            brand="EdgeCola",
            expected_zone_id="zone_shelf_beverages",
            category="beverages",
            base_hsv=(0, 200, 180),
        )
        self.register_sku(
            sku_id="sku_snack_chips_gold",
            name="Artisan Potato Chips 50g",
            brand="CrunchCo",
            expected_zone_id="zone_shelf_snacks",
            category="snacks",
            base_hsv=(30, 210, 200),
        )
        self.register_sku(
            sku_id="sku_elec_cable_usbc",
            name="Braided USB-C Cable 1m",
            brand="VoltTech",
            expected_zone_id="zone_shelf_electronics",
            category="electronics",
            base_hsv=(110, 190, 160),
        )

    def register_sku(
        self,
        sku_id: str,
        name: str,
        brand: str,
        expected_zone_id: str,
        category: str = "general",
        reference_crop: npt.NDArray[np.uint8] | None = None,
        base_hsv: tuple[int, int, int] | None = None,
    ) -> None:
        """Add or update an SKU profile in the active edge planogram catalog."""
        hist = self.extract_histogram(reference_crop) if reference_crop is not None else None
        sku_ref = SKURef(
            sku_id=sku_id,
            name=name,
            brand=brand,
            expected_zone_id=expected_zone_id,
            category=category,
            hist=hist,
            base_hsv=base_hsv,
        )
        self._catalog[sku_id] = sku_ref
        self._zone_expected_sku[expected_zone_id] = sku_id
        logger.info("SKUSegregator: registered SKU %s for shelf %s", sku_id, expected_zone_id)

    def get_catalog(self) -> list[SKUProfile]:
        """Return all registered catalog SKUs."""
        return [
            SKUProfile(
                sku_id=ref.sku_id,
                name=ref.name,
                brand=ref.brand,
                expected_zone_id=ref.expected_zone_id,
                category=ref.category,
            )
            for ref in self._catalog.values()
        ]

    def get_sku(self, sku_id: str) -> SKUProfile | None:
        """Return a specific SKU profile if registered."""
        ref = self._catalog.get(sku_id)
        if ref is None:
            return None
        return SKUProfile(
            sku_id=ref.sku_id,
            name=ref.name,
            brand=ref.brand,
            expected_zone_id=ref.expected_zone_id,
            category=ref.category,
        )

    def extract_histogram(self, crop_bgr: npt.NDArray[np.uint8]) -> npt.NDArray[np.float32]:
        """Compute normalized 2D Hue-Saturation color histogram (8x8 bins)."""
        if crop_bgr.size == 0 or crop_bgr.shape[0] < 4 or crop_bgr.shape[1] < 4:
            return np.zeros((8, 8), dtype=np.float32)

        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        blurred = cv2.GaussianBlur(hist, (3, 3), 0.8)
        norm = float(cv2.norm(blurred))
        if norm > 0:
            return (blurred / norm).astype(np.float32)
        return blurred.astype(np.float32)

    def detect_facings(self, crop_bgr: npt.NDArray[np.uint8]) -> int:
        """Estimate product facing count across shelf width via vertical edge gradient peaks."""
        if crop_bgr.size == 0 or crop_bgr.shape[0] < 10 or crop_bgr.shape[1] < 20:
            return 0

        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        # Vertical Sobel filters identify packaging boundaries
        sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        vert_energy = np.mean(np.abs(sobel_x), axis=0).astype(np.float32)

        # Smooth horizontal profile with 1D Gaussian kernel
        ksize = min(15, max(5, (crop_bgr.shape[1] // 10) | 1))
        kernel = cv2.getGaussianKernel(ksize, 2.0).flatten()
        smoothed = np.convolve(vert_energy, kernel, mode="same")
        avg_energy = float(np.mean(smoothed))

        if avg_energy < 4.0:
            return 0  # Empty shelf surface has very low vertical gradient

        # Count peaks above threshold with minimal spacing
        peaks = 0
        min_spacing = max(10, crop_bgr.shape[1] // 10)
        last_peak = -min_spacing

        for x in range(1, len(smoothed) - 1):
            if (
                smoothed[x] >= smoothed[x - 1]
                and smoothed[x] > smoothed[x + 1]
                and smoothed[x] > avg_energy * 1.10
                and (x - last_peak) >= min_spacing
            ):
                peaks += 1
                last_peak = x

        # Facings is typically peaks if distinct items are bordered, or peaks + 1
        return max(1, min(10, peaks))

    def evaluate_shelf(
        self,
        shelf_crop: npt.NDArray[np.uint8],
        shelf_id: str,
        camera_id: str = "cam_primary",
    ) -> SKUSegregationItem:
        """Analyze shelf crop from 480p stream for SKU identity, facings, and planogram match."""
        now = datetime.now(UTC)
        expected_sku_id = self._zone_expected_sku.get(shelf_id)

        if shelf_crop.size == 0 or shelf_crop.shape[0] < 8 or shelf_crop.shape[1] < 8:
            return SKUSegregationItem(
                shelf_id=shelf_id,
                camera_id=camera_id,
                detected_sku_id=None,
                detected_sku_name=None,
                expected_sku_id=expected_sku_id,
                facing_count=0,
                fill_percentage=0.0,
                confidence=0.9,
                status="empty",
                planogram_compliant=False,
                timestamp=now,
            )

        # 1. Edge & color variance check for empty shelf
        gray = cv2.cvtColor(shelf_crop, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.count_nonzero(edges) / edges.size)
        color_std = float(np.std(shelf_crop))

        if edge_density < 0.009 and color_std < 18.0:
            return SKUSegregationItem(
                shelf_id=shelf_id,
                camera_id=camera_id,
                detected_sku_id=None,
                detected_sku_name=None,
                expected_sku_id=expected_sku_id,
                facing_count=0,
                fill_percentage=0.0,
                confidence=0.85,
                status="empty",
                planogram_compliant=False,
                timestamp=now,
            )

        # 2. Match crop histogram against catalog SKU profiles
        crop_hist = self.extract_histogram(shelf_crop)
        best_sku: SKURef | None = None
        best_score = -1.0

        for sku_ref in self._catalog.values():
            # Dot product / cosine similarity
            score = float(np.sum(crop_hist * sku_ref.hist))
            if score > best_score:
                best_score = score
                best_sku = sku_ref

        # Compute fill percentage based on edge texture richness
        fill_pct = float(min(1.0, max(0.1, edge_density / 0.065)))
        facings = self.detect_facings(shelf_crop)

        # Normalize correlation score to confidence [0.0, 1.0]
        confidence = float(max(0.0, min(1.0, best_score)))

        # 3. Planogram compliance & misplacement check
        if best_sku is not None and expected_sku_id is not None:
            if best_sku.sku_id != expected_sku_id and confidence > 0.60:
                # Detected SKU does not belong in this shelf section
                status: Literal["ok", "low", "empty", "misplaced"] = "misplaced"
                planogram_ok = False
            else:
                planogram_ok = True
                status = "low" if fill_pct < 0.40 else "ok"
        else:
            planogram_ok = True
            status = "low" if fill_pct < 0.40 else "ok"

        return SKUSegregationItem(
            shelf_id=shelf_id,
            camera_id=camera_id,
            detected_sku_id=best_sku.sku_id if best_sku else None,
            detected_sku_name=best_sku.name if best_sku else None,
            expected_sku_id=expected_sku_id,
            facing_count=facings,
            fill_percentage=round(fill_pct, 2),
            confidence=round(confidence, 2),
            status=status,
            planogram_compliant=planogram_ok,
            timestamp=now,
        )

    def evaluate_all_shelves(
        self,
        frames_by_camera: list[tuple[str, npt.NDArray[np.uint8]]],
        zones: list[ZoneConfig],
        force: bool = False,
    ) -> SKUSegregationReport:
        """Run SKU segregation across all shelf zones in 480p camera frames.

        Enforces >= 10-second cadence lock unless force=True.
        """
        now_mono = time.monotonic()
        elapsed = now_mono - self._last_eval_time

        if not force and self._last_report is not None and elapsed < self.interval_seconds:
            return self._last_report

        self._last_eval_time = now_mono
        shelf_zones = [z for z in zones if z.zone_type == "shelf"]
        items: list[SKUSegregationItem] = []

        for cam_id, frame in frames_by_camera:
            if frame is None or frame.size == 0:
                continue
            for zone in shelf_zones:
                crop = crop_to_zone(frame, zone)
                item = self.evaluate_shelf(crop, shelf_id=zone.zone_id, camera_id=cam_id)
                items.append(item)

        total = len(items)
        compliant = sum(1 for i in items if i.planogram_compliant and i.status == "ok")
        misplaced = sum(1 for i in items if i.status == "misplaced")
        low_empty = sum(1 for i in items if i.status in ("low", "empty"))

        report = SKUSegregationReport(
            interval_seconds=self.interval_seconds,
            total_shelves_monitored=total,
            compliant_shelves=compliant,
            misplaced_shelves=misplaced,
            low_or_empty_shelves=low_empty,
            last_evaluated_at=datetime.now(UTC),
            items=items,
        )
        self._last_report = report
        return report

    def get_latest_report(self) -> SKUSegregationReport:
        """Return the most recent computed report or an empty template."""
        if self._last_report is not None:
            return self._last_report
        return SKUSegregationReport(
            interval_seconds=self.interval_seconds,
            total_shelves_monitored=0,
            compliant_shelves=0,
            misplaced_shelves=0,
            low_or_empty_shelves=0,
            last_evaluated_at=None,
            items=[],
        )


# Global singleton SKUSegregator locked to >= 10s cadence
sku_segregator = SKUSegregator(interval_seconds=10.0)
