import cv2
import numpy as np
import pytest
from analytics.zone_membership import anchor_point, is_inside_zone, zone_polygon_cache
from core.schemas import ZoneConfig


def test_anchor_point_calculation() -> None:
    # Test bboxes: (x, y, w, h)
    # anchor_x = x + w / 2.0, anchor_y = y + h
    cases = [
        ((0, 0, 10, 20), (5.0, 20.0)),
        ((100, 150, 40, 60), (120.0, 210.0)),
        ((180, 110, 40, 40), (200.0, 150.0)),
        ((150, 150, 40, 50), (170.0, 200.0)),
        ((550, 150, 20, 30), (560.0, 180.0)),
        ((600, 200, 20, 20), (610.0, 220.0)),
        ((80, 80, 40, 40), (100.0, 120.0)),
        ((150, 150, 40, 200), (170.0, 350.0)),
    ]

    for bbox, expected in cases:
        assert anchor_point(bbox) == pytest.approx(expected)


def test_is_inside_zone_inside_and_outside() -> None:
    zone = ZoneConfig(
        zone_id="test_zone",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Test Zone",
    )

    # Clearly inside
    assert is_inside_zone((200.0, 200.0), zone) is True
    # Clearly outside
    assert is_inside_zone((50.0, 50.0), zone) is False
    assert is_inside_zone((200.0, 50.0), zone) is False
    assert is_inside_zone((200.0, 350.0), zone) is False
    assert is_inside_zone((350.0, 200.0), zone) is False


def test_is_inside_zone_boundary_points() -> None:
    # cv2.pointPolygonTest returns 0 on the boundary, which satisfies >= 0
    zone = ZoneConfig(
        zone_id="test_zone",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Test Zone",
    )

    # Edge points
    assert is_inside_zone((100.0, 200.0), zone) is True
    assert is_inside_zone((200.0, 100.0), zone) is True
    assert is_inside_zone((300.0, 200.0), zone) is True
    assert is_inside_zone((200.0, 300.0), zone) is True

    # Vertex points
    assert is_inside_zone((100.0, 100.0), zone) is True
    assert is_inside_zone((300.0, 300.0), zone) is True


def test_is_inside_zone_with_precomputed_poly_np() -> None:
    zone = ZoneConfig(
        zone_id="test_zone",
        zone_type="checkout",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Test Checkout",
    )
    poly_np = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))

    assert is_inside_zone((200.0, 200.0), zone, poly_np=poly_np) is True
    assert is_inside_zone((50.0, 50.0), zone, poly_np=poly_np) is False
    # Explicit comparison with direct cv2.pointPolygonTest
    assert is_inside_zone((200.0, 200.0), zone, poly_np=poly_np) == (
        cv2.pointPolygonTest(poly_np, (200.0, 200.0), False) >= 0
    )


def test_zone_polygon_cache() -> None:
    zone1 = ZoneConfig(
        zone_id="zone_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Zone 1",
    )
    zone2 = ZoneConfig(
        zone_id="zone_2",
        zone_type="checkout",
        polygon=[(500, 100), (700, 100), (700, 300), (500, 300)],
        label="Zone 2",
    )

    cache = zone_polygon_cache([zone1, zone2])
    assert set(cache.keys()) == {"zone_1", "zone_2"}
    assert cache["zone_1"].shape == (4, 1, 2)
    assert cache["zone_1"].dtype == np.int32
    assert cache["zone_2"].shape == (4, 1, 2)
    assert cache["zone_2"].dtype == np.int32

    # Verify point evaluation matches
    assert is_inside_zone((200.0, 200.0), zone1, poly_np=cache["zone_1"]) is True
    assert is_inside_zone((600.0, 200.0), zone2, poly_np=cache["zone_2"]) is True
    assert is_inside_zone((600.0, 200.0), zone1, poly_np=cache["zone_1"]) is False
