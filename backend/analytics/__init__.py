"""Retail analytics module: footfall, dwell, queue, shelf, and heatmap."""

from analytics.dwell import DwellTracker
from analytics.footfall import FootfallTracker, process_frame
from analytics.heatmap import HeatmapAccumulator
from analytics.interaction import ProductInteractionDetector
from analytics.queue_monitor import QueueMonitor
from analytics.roi import crop_to_zone
from analytics.shelf_classifier import (
    EdgeDensityShelfClassifier,
    ProductOccupancyShelfClassifier,
    ShelfClassifier,
    check_shelves,
)
from analytics.zone_membership import anchor_point, is_inside_zone, zone_polygon_cache
from analytics.zone_transitions import ZoneTransition, ZoneTransitionTracker

__all__ = [
    "DwellTracker",
    "EdgeDensityShelfClassifier",
    "FootfallTracker",
    "HeatmapAccumulator",
    "ProductInteractionDetector",
    "ProductOccupancyShelfClassifier",
    "QueueMonitor",
    "ShelfClassifier",
    "ZoneTransition",
    "ZoneTransitionTracker",
    "anchor_point",
    "check_shelves",
    "crop_to_zone",
    "is_inside_zone",
    "process_frame",
    "zone_polygon_cache",
]
