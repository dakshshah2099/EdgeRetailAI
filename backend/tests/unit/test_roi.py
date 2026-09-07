import numpy as np
import pytest
from analytics.roi import crop_to_zone
from core.schemas import ZoneConfig


def test_crop_to_zone_standard_rect() -> None:
    """crop_to_zone correctly crops frame to rectangular bounding box."""
    # Synthetic frame: 480x640 with distinct channel values
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    pixels[100:200, 150:350] = [10, 20, 30]

    zone = ZoneConfig(
        zone_id="shelf_1",
        zone_type="shelf",
        polygon=[(150, 100), (350, 100), (350, 200), (150, 200)],
        label="Shelf 1",
    )

    crop = crop_to_zone(pixels, zone)
    assert crop.shape == (100, 200, 3)
    assert np.all(crop == [10, 20, 30])


def test_crop_to_zone_non_axis_aligned_polygon() -> None:
    """crop_to_zone computes outer bounding box for non-rectangular polygons."""
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    # Triangle: (50, 60), (150, 60), (100, 160) -> bbox x: [50, 150], y: [60, 160]
    zone = ZoneConfig(
        zone_id="shelf_tri",
        zone_type="shelf",
        polygon=[(50, 60), (150, 60), (100, 160)],
        label="Shelf Triangle",
    )

    crop = crop_to_zone(pixels, zone)
    assert crop.shape == (100, 100, 3)  # height=100, width=100


def test_crop_to_zone_clamps_to_frame_boundaries() -> None:
    """crop_to_zone clamps coordinates that exceed frame boundaries."""
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    zone = ZoneConfig(
        zone_id="shelf_overflow",
        zone_type="shelf",
        polygon=[(-50, -30), (700, -30), (700, 520), (-50, 520)],
        label="Overflow Shelf",
    )

    crop = crop_to_zone(pixels, zone)
    assert crop.shape == (480, 640, 3)


def test_crop_to_zone_pure_function_copy() -> None:
    """Modifying returned crop does not mutate original pixel array."""
    pixels = np.ones((100, 100, 3), dtype=np.uint8) * 50
    zone = ZoneConfig(
        zone_id="shelf_copy",
        zone_type="shelf",
        polygon=[(10, 10), (30, 10), (30, 30), (10, 30)],
        label="Copy Test",
    )

    crop = crop_to_zone(pixels, zone)
    crop[:, :] = 255
    assert np.all(pixels[10:30, 10:30] == 50)


def test_crop_to_zone_grayscale() -> None:
    """crop_to_zone supports 2D grayscale frames."""
    pixels = np.zeros((200, 200), dtype=np.uint8)
    zone = ZoneConfig(
        zone_id="shelf_gray",
        zone_type="shelf",
        polygon=[(20, 30), (80, 30), (80, 90), (20, 90)],
        label="Gray Shelf",
    )

    crop = crop_to_zone(pixels, zone)
    assert crop.shape == (60, 60)


def test_crop_to_zone_out_of_bounds_error() -> None:
    """crop_to_zone raises ValueError when polygon is completely outside frame."""
    pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    zone = ZoneConfig(
        zone_id="shelf_outside",
        zone_type="shelf",
        polygon=[(200, 200), (300, 200), (300, 300), (200, 300)],
        label="Outside Shelf",
    )

    with pytest.raises(ValueError, match="outside image bounds"):
        crop_to_zone(pixels, zone)
