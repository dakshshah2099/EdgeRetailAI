from datetime import datetime
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt
import pytest
from analytics.shelf_classifier import (
    EdgeDensityShelfClassifier,
    ShelfClassifier,
    check_shelves,
)
from core.schemas import Frame, StockEvent, ZoneConfig

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SHELF_EMPTY_PATH = FIXTURES_DIR / "shelf_empty.jpg"
SHELF_LOW_PATH = FIXTURES_DIR / "shelf_low.jpg"
SHELF_STOCKED_PATH = FIXTURES_DIR / "shelf_stocked.jpg"


def test_fixtures_exist() -> None:
    """Ensure all required shelf fixtures exist."""
    assert SHELF_EMPTY_PATH.is_file(), f"Missing fixture: {SHELF_EMPTY_PATH}"
    assert SHELF_LOW_PATH.is_file(), f"Missing fixture: {SHELF_LOW_PATH}"
    assert SHELF_STOCKED_PATH.is_file(), f"Missing fixture: {SHELF_STOCKED_PATH}"


def test_classify_shelf_empty() -> None:
    """Classifier correctly identifies empty shelf fixture."""
    raw = cv2.imread(str(SHELF_EMPTY_PATH))
    assert raw is not None
    img: npt.NDArray[np.uint8] = np.asarray(raw, dtype=np.uint8)

    classifier = EdgeDensityShelfClassifier()
    status, confidence = classifier.classify(img)

    assert status == "empty"
    assert 0.0 <= confidence <= 1.0
    assert confidence >= 0.5


def test_classify_shelf_low() -> None:
    """Classifier correctly identifies low stock shelf fixture."""
    raw = cv2.imread(str(SHELF_LOW_PATH))
    assert raw is not None
    img: npt.NDArray[np.uint8] = np.asarray(raw, dtype=np.uint8)

    classifier = EdgeDensityShelfClassifier()
    status, confidence = classifier.classify(img)

    assert status == "low"
    assert 0.0 <= confidence <= 1.0
    assert confidence >= 0.5


def test_classify_shelf_stocked() -> None:
    """Classifier correctly identifies stocked shelf fixture."""
    raw = cv2.imread(str(SHELF_STOCKED_PATH))
    assert raw is not None
    img: npt.NDArray[np.uint8] = np.asarray(raw, dtype=np.uint8)

    classifier = EdgeDensityShelfClassifier()
    status, confidence = classifier.classify(img)

    assert status == "ok"
    assert 0.0 <= confidence <= 1.0
    assert confidence >= 0.5


def test_check_shelves_pipeline() -> None:
    """check_shelves processes shelf zones and returns valid StockEvents."""
    raw_stocked = cv2.imread(str(SHELF_STOCKED_PATH))
    assert raw_stocked is not None
    img_stocked = np.asarray(raw_stocked, dtype=np.uint8)

    # Construct frame with 2 shelf zones
    frame_pixels = np.zeros((480, 1280, 3), dtype=np.uint8)
    frame_pixels[:, :640] = img_stocked
    raw_empty = cv2.imread(str(SHELF_EMPTY_PATH))
    assert raw_empty is not None
    img_empty = np.asarray(raw_empty, dtype=np.uint8)
    frame_pixels[:, 640:] = img_empty

    zones = [
        ZoneConfig(
            zone_id="shelf_left",
            zone_type="shelf",
            polygon=[(0, 0), (640, 0), (640, 480), (0, 480)],
            label="Left Shelf",
        ),
        ZoneConfig(
            zone_id="shelf_right",
            zone_type="shelf",
            polygon=[(640, 0), (1280, 0), (1280, 480), (640, 480)],
            label="Right Shelf",
        ),
        # Non-shelf zone should be ignored by check_shelves
        ZoneConfig(
            zone_id="entry_main",
            zone_type="entry_exit",
            polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
            label="Entrance",
        ),
    ]

    now = datetime(2026, 8, 29, 12, 0, 0)
    frame = Frame(source_id="cam_shelf_01", timestamp=now, width=1280, height=480)
    classifier = EdgeDensityShelfClassifier()

    events = check_shelves(
        frame=frame,
        pixels=frame_pixels,
        classifier=classifier,
        shelf_zones=zones,
        threshold=0.5,
    )

    assert len(events) == 2
    by_shelf = {e.shelf_id: e for e in events}
    assert "shelf_left" in by_shelf
    assert "shelf_right" in by_shelf
    assert "entry_main" not in by_shelf

    assert by_shelf["shelf_left"].status == "ok"
    assert by_shelf["shelf_left"].timestamp == now
    assert 0.0 <= by_shelf["shelf_left"].confidence <= 1.0

    assert by_shelf["shelf_right"].status == "empty"
    assert by_shelf["shelf_right"].timestamp == now
    assert 0.0 <= by_shelf["shelf_right"].confidence <= 1.0


def test_shelf_classifier_swappability() -> None:
    """A custom ShelfClassifier subclass can be swapped in without modifying check_shelves."""

    class MockClassifier(ShelfClassifier):
        def classify(
            self, shelf_crop: npt.NDArray[np.uint8]
        ) -> tuple[Literal["empty", "low", "ok"], float]:
            return "low", 0.99

    dummy_pixels = np.zeros((100, 100, 3), dtype=np.uint8)
    zone = ZoneConfig(
        zone_id="shelf_test",
        zone_type="shelf",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        label="Test Shelf",
    )
    frame = Frame(
        source_id="cam_01",
        timestamp=datetime(2026, 8, 29, 12, 0, 0),
        width=100,
        height=100,
    )

    events = check_shelves(
        frame=frame,
        pixels=dummy_pixels,
        classifier=MockClassifier(),
        shelf_zones=[zone],
        threshold=0.5,
    )

    assert len(events) == 1
    assert events[0].status == "low"
    assert events[0].confidence == pytest.approx(0.99)


def test_stock_event_no_pii_or_pixel_storage() -> None:
    """StockEvent strictly contains metadata and status, never cropped images."""
    event = StockEvent(
        event_id="stock_123",
        shelf_id="shelf_01",
        timestamp=datetime(2026, 8, 29, 12, 0, 0),
        status="ok",
        confidence=0.95,
    )
    fields = set(event.model_dump().keys())
    prohibited = {"image", "crop", "pixels", "frame", "embedding", "face"}
    assert prohibited.isdisjoint(fields)


def test_classifier_zero_size_crop() -> None:
    """Zero-sized crop returns empty status gracefully."""
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    classifier = EdgeDensityShelfClassifier()
    status, conf = classifier.classify(empty_crop)
    assert status == "empty"
    assert conf == 0.0
