import numpy as np
import numpy.typing as npt

from vision.tracker import TrackedDetection


class HeatmapAccumulator:
    """Accumulates positional dwell/traffic intensity into a 2D grid over
    the camera's frame dimensions.
    """

    def __init__(self, width: int, height: int, cell_size: int = 20) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive integers")
        if cell_size <= 0:
            raise ValueError("cell_size must be a positive integer")
        if cell_size > width or cell_size > height:
            raise ValueError("cell_size cannot exceed width or height")

        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.grid_width = width // cell_size
        self.grid_height = height // cell_size
        self._grid: npt.NDArray[np.float32] = np.zeros(
            (self.grid_height, self.grid_width), dtype=np.float32
        )

    def reset(self) -> None:
        """Reset accumulated intensity grid back to zero."""
        self._grid.fill(0.0)

    def add_point(self, x: float, y: float, weight: float = 1.0) -> None:
        """Increment the grid cell containing (x, y) by weight.

        Called once per tracked detection per frame using the bottom-center anchor.
        Points outside frame boundaries are ignored.
        """
        if x < 0.0 or y < 0.0:
            return

        col = int(x // self.cell_size)
        row = int(y // self.cell_size)

        if 0 <= col < self.grid_width and 0 <= row < self.grid_height:
            self._grid[row, col] += np.float32(weight)

    def add_detection(self, bbox: tuple[int, int, int, int], weight: float = 1.0) -> None:
        """Increment grid cell at the bottom-center anchor point of bbox (x, y, w, h)."""
        anchor_x = float(bbox[0] + bbox[2] / 2.0)
        anchor_y = float(bbox[1] + bbox[3])
        self.add_point(anchor_x, anchor_y, weight=weight)

    def add_tracked_detections(
        self, detections: list[TrackedDetection], weight: float = 1.0
    ) -> None:
        """Increment grid cells for a batch of tracked detections using bottom-center anchors."""
        for det in detections:
            self.add_detection(det.bbox, weight=weight)

    def get_grid(self) -> npt.NDArray[np.float32]:
        """Return the current accumulated grid, shape (height // cell_size, width // cell_size)."""
        return self._grid.copy()
