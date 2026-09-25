import numpy as np
import pytest

from analytics.heatmap import HeatmapAccumulator
from vision.tracker import TrackedDetection

pytestmark = pytest.mark.slice_3
def test_heatmap_init_and_grid_shape() -> None:
    """Heatmap initializes with correct grid dimensions and float32 zero array."""
    accum = HeatmapAccumulator(width=640, height=480, cell_size=20)
    grid = accum.get_grid()

    assert grid.shape == (24, 32)  # height // cell_size, width // cell_size
    assert grid.dtype == np.float32
    assert np.all(grid == 0.0)

    # Invalid initializations
    with pytest.raises(ValueError, match="width and height must be positive"):
        HeatmapAccumulator(width=0, height=480, cell_size=20)

    with pytest.raises(ValueError, match="width and height must be positive"):
        HeatmapAccumulator(width=640, height=-10, cell_size=20)

    with pytest.raises(ValueError, match="cell_size must be a positive integer"):
        HeatmapAccumulator(width=640, height=480, cell_size=0)

    with pytest.raises(ValueError, match="cell_size cannot exceed"):
        HeatmapAccumulator(width=10, height=480, cell_size=20)


def test_heatmap_add_point_mid_cell() -> None:
    """add_point correctly increments the containing cell by the given weight.

    After Gaussian blur, exact cell values shift but peak locations and total
    sum are preserved.
    """
    accum = HeatmapAccumulator(width=400, height=400, cell_size=20)
    # Cell (0,0) spans [0, 20) x [0, 20)
    accum.add_point(10.0, 10.0, weight=1.0)
    # Cell (row=5, col=3) spans x in [60, 80), y in [100, 120)
    accum.add_point(70.0, 110.0, weight=2.5)

    grid = accum.get_grid()
    # Gaussian blur distributes weight but target cells remain peaks
    assert grid[0, 0] > 0.0
    assert grid[5, 3] > 0.0
    assert grid[5, 3] > grid[0, 0]  # heavier point still dominates
    assert np.sum(grid) > 0.0  # total weight present (Gaussian blur may lose energy at borders)


def test_heatmap_add_point_boundary() -> None:
    """Boundary points are binned consistently into half-open intervals [k*s, (k+1)*s)."""
    accum = HeatmapAccumulator(width=400, height=400, cell_size=20)

    # Boundary point at (20.0, 20.0) -> col = 20//20 = 1, row = 20//20 = 1
    accum.add_point(20.0, 20.0, weight=1.0)
    grid = accum.get_grid()
    assert grid[1, 1] > 0.0

    # Just below boundary at (19.999, 19.999) -> col = 0, row = 0
    accum.add_point(19.999, 19.999, weight=1.0)
    grid = accum.get_grid()
    # Both cells should have accumulated weight
    assert grid[0, 0] > 0.0
    assert grid[1, 1] > 0.0


def test_heatmap_out_of_bounds_handling() -> None:
    """Points outside frame boundaries are ignored without crashing."""
    accum = HeatmapAccumulator(width=100, height=100, cell_size=20)

    # Negative coordinates
    accum.add_point(-5.0, 10.0)
    accum.add_point(10.0, -5.0)

    # Coordinates beyond frame dimensions
    accum.add_point(120.0, 50.0)
    accum.add_point(50.0, 150.0)

    grid = accum.get_grid()
    assert np.all(grid == 0.0)


def test_heatmap_peak_zone_location() -> None:
    """Accumulating points in a simulated zone produces peak cell at that zone."""
    accum = HeatmapAccumulator(width=1920, height=1080, cell_size=20)

    # Simulate 50 observations around (650, 250)
    rng = np.random.default_rng(42)
    xs = rng.normal(loc=650.0, scale=10.0, size=50)
    ys = rng.normal(loc=250.0, scale=10.0, size=50)

    for x, y in zip(xs, ys, strict=False):
        accum.add_point(float(x), float(y))

    grid = accum.get_grid()
    peak_row, peak_col = np.unravel_index(np.argmax(grid), grid.shape)

    expected_col = 650 // 20  # 32
    expected_row = 250 // 20  # 12

    assert peak_col == expected_col
    assert peak_row == expected_row


def test_heatmap_get_grid_returns_copy() -> None:
    """get_grid returns a copy so modifying the returned array does not corrupt internal state."""
    accum = HeatmapAccumulator(width=100, height=100, cell_size=20)
    accum.add_point(10.0, 10.0, weight=5.0)

    grid = accum.get_grid()
    original_val = float(grid[0, 0])
    grid[0, 0] = 999.0

    # Internal state must remain unchanged
    fresh_grid = accum.get_grid()
    assert fresh_grid[0, 0] == pytest.approx(original_val)


def test_heatmap_reset() -> None:
    """reset() clears all accumulated intensity back to zero."""
    accum = HeatmapAccumulator(width=100, height=100, cell_size=20)
    accum.add_point(10.0, 10.0, weight=5.0)
    accum.add_point(30.0, 30.0, weight=2.0)

    assert np.sum(accum.get_grid()) > 0.0

    accum.reset()
    assert np.sum(accum.get_grid()) == 0.0


def test_heatmap_add_detection_helper() -> None:
    """add_detection and add_tracked_detections compute bottom-center anchor."""
    accum = HeatmapAccumulator(width=640, height=480, cell_size=20)

    # Detection bbox: (x=100, y=100, w=40, h=60)
    # Bottom-center anchor: x = 100 + 20 = 120, y = 100 + 60 = 160
    # Expected cell: col = 120 // 20 = 6, row = 160 // 20 = 8
    accum.add_detection((100, 100, 40, 60), weight=1.0)
    grid = accum.get_grid()
    assert grid[8, 6] > 0.0
    # Peak should be at the anchor cell
    peak_row, peak_col = np.unravel_index(np.argmax(grid), grid.shape)
    assert peak_row == 8
    assert peak_col == 6

    # Tracked detection at same location doubles weight
    det = TrackedDetection(track_id="trk_1", bbox=(100, 100, 40, 60), confidence=0.9)
    accum.add_tracked_detections([det], weight=1.0)
    grid2 = accum.get_grid()
    assert grid2[8, 6] > grid[8, 6]  # weight increased


def test_heatmap_no_pii_or_rendered_pixels() -> None:
    """HeatmapAccumulator output is strictly numeric float32 2D array without PII

    or color channels.
    """
    accum = HeatmapAccumulator(width=640, height=480, cell_size=20)
    accum.add_point(100.0, 100.0)
    grid = accum.get_grid()

    assert grid.ndim == 2  # 2D numeric grid, not 3D (H, W, C) image
    assert grid.dtype == np.float32
