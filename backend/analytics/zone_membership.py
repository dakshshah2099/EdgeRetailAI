import cv2
import numpy as np
import numpy.typing as npt

from core.schemas import ZoneConfig


def anchor_point(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    """Bottom-center anchor point of a bbox (x, y, w, h). This is the exact
    convention already used identically in footfall.py and queue_monitor.py
    — extract verbatim, do not change the formula.
    """
    anchor_x = float(bbox[0] + bbox[2] / 2.0)
    anchor_y = float(bbox[1] + bbox[3])
    return (anchor_x, anchor_y)


def zone_polygon_cache(zones: list[ZoneConfig]) -> dict[str, npt.NDArray[np.int32]]:
    """Pre-converts zone polygons to cv2-compatible numpy arrays, keyed by
    zone_id — extracted from footfall.py's existing per-call conversion
    (which was recomputing this on every update() call; if queue_monitor.py
    did NOT already cache this the same way, note the discrepancy — this
    refactor should not silently introduce a behavior change by caching
    somewhere it wasn't cached before, or failing to cache somewhere it
    was. State clearly what each caller's caching behavior was before and
    after).
    """
    return {
        z.zone_id: np.array(z.polygon, dtype=np.int32).reshape((-1, 1, 2))
        for z in zones
    }


def is_inside_zone(
    point: tuple[float, float],
    zone: ZoneConfig,
    poly_np: npt.NDArray[np.int32] | None = None,
) -> bool:
    """cv2.pointPolygonTest-based check, extracted verbatim from the
    existing duplicated implementations. Same behavior, same edge-case
    handling (boundary points, degenerate polygons) as before.
    """
    if poly_np is None:
        poly_np = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
    return bool(cv2.pointPolygonTest(poly_np, point, False) >= 0)
