import numpy as np
import numpy.typing as npt
from core.schemas import ZoneConfig


def crop_to_zone(pixels: npt.NDArray[np.uint8], zone: ZoneConfig) -> npt.NDArray[np.uint8]:
    """Crop the frame to the bounding box of the zone's polygon.

    Pure function, no side effects, no persistence of the crop.
    """
    if len(zone.polygon) < 3:
        raise ValueError("Zone polygon must contain at least 3 vertices")

    frame_height = pixels.shape[0]
    frame_width = pixels.shape[1]

    xs = [p[0] for p in zone.polygon]
    ys = [p[1] for p in zone.polygon]

    min_x = max(0, min(xs))
    max_x = min(frame_width, max(xs))
    min_y = max(0, min(ys))
    max_y = min(frame_height, max(ys))

    if min_x >= max_x or min_y >= max_y:
        raise ValueError(
            f"Zone polygon {zone.polygon} is outside image bounds "
            f"(width={frame_width}, height={frame_height})"
        )

    return pixels[min_y:max_y, min_x:max_x].copy()
