"""Inventory and shelf stock detection module."""

from inventory.roi import crop_to_zone
from inventory.shelf_classifier import (
    EdgeDensityShelfClassifier,
    ShelfClassifier,
    check_shelves,
)

__all__ = [
    "ShelfClassifier",
    "EdgeDensityShelfClassifier",
    "crop_to_zone",
    "check_shelves",
]
