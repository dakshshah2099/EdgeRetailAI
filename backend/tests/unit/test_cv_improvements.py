"""Comprehensive tests for CV Improvement Criteria: multi-class detection,
class-aware tracking, product interaction, shelf occupancy, zone transitions,
and Gate 1-8 evaluation harness.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from analytics.interaction import ProductInteractionDetector
from analytics.shelf_classifier import (
    ProductOccupancyShelfClassifier,
    check_shelves,
)
from analytics.zone_transitions import ZoneTransitionTracker
from benchmarks.cv_eval import (
    CVEvaluator,
    MockPredictorBackend,
    build_open_retail_synthetic_suite,
)
from core.schemas import (
    Detection,
    DetectionEvent,
    Frame,
    InteractionEvent,
    ShelfOccupancyResult,
    ZoneConfig,
    ZoneTransition,
)
from vision.detector import (
    OPEN_RETAIL_CLASS_MAP,
    PERSON_CLASS_ID,
    PersonDetector,
    YOLODetector,
)
from vision.inference_backend import InferenceBackend, RawDetection
from vision.tracker import TrackedDetection, Tracker


class MockBackend(InferenceBackend):
    def __init__(self, detections: list[RawDetection]) -> None:
        self.detections = detections

    def infer(self, frame: np.ndarray) -> list[RawDetection]:
        return list(self.detections)


# ============================================================================
# Gate 1 & P0.1: Multi-Class YOLODetector & Schemas
# ============================================================================


def test_yolo_detector_preserves_multiple_classes() -> None:
    dets = [
        RawDetection(class_id=0, confidence=0.85, bbox=(10, 10, 50, 100)),  # person
        RawDetection(class_id=1, confidence=0.78, bbox=(120, 150, 30, 40)),  # product
        RawDetection(class_id=2, confidence=0.65, bbox=(200, 200, 80, 80)),  # cart
    ]
    detector = YOLODetector(backend=MockBackend(dets), class_map=OPEN_RETAIL_CLASS_MAP)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    results = detector.detect(dummy_frame)
    assert len(results) == 3
    class_ids = {r.class_id for r in results}
    assert class_ids == {0, 1, 2}


def test_yolo_detector_per_class_thresholds() -> None:
    dets = [
        RawDetection(class_id=0, confidence=0.45, bbox=(10, 10, 50, 100)),
        RawDetection(class_id=1, confidence=0.45, bbox=(120, 150, 30, 40)),
    ]
    # Person threshold 0.5 (filters out), product threshold 0.4 (keeps)
    detector = YOLODetector(
        backend=MockBackend(dets),
        conf_thresholds={0: 0.5, 1: 0.4},
        default_conf_threshold=0.4,
    )
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = detector.detect(dummy_frame)

    assert len(results) == 1
    assert results[0].class_id == 1


def test_yolo_detector_typed_output() -> None:
    dets = [RawDetection(class_id=1, confidence=0.92, bbox=(10, 20, 30, 40))]
    detector = YOLODetector(backend=MockBackend(dets), class_map=OPEN_RETAIL_CLASS_MAP)
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    now = datetime.now(UTC)

    typed_dets = detector.detect_typed(dummy_frame, timestamp=now)
    assert len(typed_dets) == 1
    td = typed_dets[0]
    assert isinstance(td, Detection)
    assert td.class_id == 1
    assert td.class_name == "product"
    assert td.confidence == 0.92
    assert td.bbox == (10, 20, 30, 40)
    assert td.timestamp == now


def test_person_detector_backwards_compatibility() -> None:
    dets = [
        RawDetection(class_id=0, confidence=0.9, bbox=(10, 10, 50, 100)),
        RawDetection(class_id=1, confidence=0.9, bbox=(120, 150, 30, 40)),
    ]
    detector = PersonDetector(backend=MockBackend(dets))
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = detector.detect(dummy_frame)

    assert len(results) == 1
    assert results[0].class_id == PERSON_CLASS_ID


def test_detector_diagnostics_dropped_frame_count() -> None:
    """dropped_frame_count increments when record_frame called with dropped=True."""
    dets: list[RawDetection] = []
    detector = YOLODetector(backend=MockBackend(dets))
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detector.detect(dummy_frame)
    assert detector.diagnostics.frame_count == 1
    assert detector.diagnostics.dropped_frame_count == 0
    detector.diagnostics.record_frame(0.0, [], dropped=True)
    assert detector.diagnostics.dropped_frame_count == 1


# ============================================================================
# Gate 4 & P1.1: Class-Aware Tracking
# ============================================================================


def test_class_aware_tracking_prevents_cross_class_hijacking() -> None:
    """A person track and a product track at adjacent/overlapping locations must not switch IDs."""
    tracker = Tracker(iou_threshold=0.3, max_age=5)

    # Frame 1: Person at (100, 100) and Product at (105, 105)
    f1 = [
        RawDetection(class_id=0, confidence=0.9, bbox=(100, 100, 50, 100)),
        RawDetection(class_id=1, confidence=0.9, bbox=(105, 105, 40, 40)),
    ]
    t1 = tracker.update(f1)
    assert len(t1) == 2
    by_class_1 = {t.class_id: t.track_id for t in t1}

    # Frame 2: Slight movement
    f2 = [
        RawDetection(class_id=0, confidence=0.9, bbox=(102, 100, 50, 100)),
        RawDetection(class_id=1, confidence=0.9, bbox=(106, 105, 40, 40)),
    ]
    t2 = tracker.update(f2)
    assert len(t2) == 2
    by_class_2 = {t.class_id: t.track_id for t in t2}

    # Tracks must keep their exact original IDs and not swap
    assert by_class_1[0] == by_class_2[0]
    assert by_class_1[1] == by_class_2[1]
    assert by_class_2[0] != by_class_2[1]


# ============================================================================
# Gate 5 & P0.6: Product Interaction Engine
# ============================================================================


def test_product_interaction_detection_lifecycle() -> None:
    """Shopper dwelling near product shelf produces InteractionEvent with dual confidence."""
    shelf_zone = ZoneConfig(
        zone_id="shelf_01",
        zone_type="shelf",
        polygon=[(100, 100), (200, 100), (200, 200), (100, 200)],
        label="Shelf 1",
    )
    detector = ProductInteractionDetector(
        proximity_margin_px=50.0,
        min_duration_sec=0.5,
        grace_period_sec=0.5,
    )
    start_ts = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)

    # Shopper standing in front of shelf for 1.0s (10 frames at 100ms)
    person_near = TrackedDetection(
        track_id="trk_shopper",
        bbox=(110, 210, 40, 100),  # top edge touches shelf boundary
        confidence=0.95,
        class_id=0,
    )

    for i in range(10):
        ts = start_ts + timedelta(seconds=i * 0.1)
        events = detector.update([person_near], [shelf_zone], ts)
        # May emit a start event at confirmation, but never end events while active
        end_events = [e for e in events if e.event_phase == "end"]
        assert len(end_events) == 0, "No end event emitted while interaction is active"

    # Shopper leaves (next frame empty after grace period)
    exit_ts = start_ts + timedelta(seconds=2.0)
    events = detector.update([], [shelf_zone], exit_ts)
    end_events = [e for e in events if e.event_phase == "end"]
    assert len(end_events) == 1
    event = end_events[0]
    assert isinstance(event, InteractionEvent)
    assert event.track_id == "trk_shopper"
    assert event.zone_id == "shelf_01"
    assert event.detection_confidence >= 0.8
    assert event.interaction_confidence >= 0.5
    assert (event.end_ts - event.start_ts).total_seconds() >= 0.5


def test_product_interaction_start_event_emitted() -> None:
    """Confirmation of interaction emits a start event before the end event."""
    shelf_zone = ZoneConfig(
        zone_id="shelf_02",
        zone_type="shelf",
        polygon=[(100, 100), (200, 100), (200, 200), (100, 200)],
        label="Shelf 2",
    )
    detector = ProductInteractionDetector(
        proximity_margin_px=50.0,
        min_duration_sec=0.5,
        grace_period_sec=2.0,
    )
    start_ts = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
    person_near = TrackedDetection(
        track_id="trk_a", bbox=(110, 210, 40, 100), confidence=0.9, class_id=0
    )

    start_events: list[InteractionEvent] = []
    for i in range(8):
        ts = start_ts + timedelta(seconds=i * 0.1)
        for e in detector.update([person_near], [shelf_zone], ts):
            if e.event_phase == "start":
                start_events.append(e)

    assert len(start_events) == 1, "Exactly one start event on confirmation"
    assert start_events[0].track_id == "trk_a"


def test_product_interaction_glance_debounced() -> None:
    """A person passing by for 0.1s is debounced and emits no interaction event."""
    shelf_zone = ZoneConfig(
        zone_id="shelf_01",
        zone_type="shelf",
        polygon=[(100, 100), (200, 100), (200, 200), (100, 200)],
        label="Shelf 1",
    )
    detector = ProductInteractionDetector(min_duration_sec=1.0, grace_period_sec=0.2)
    start_ts = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)

    person_near = TrackedDetection(
        track_id="passerby",
        bbox=(110, 210, 40, 100),
        confidence=0.9,
        class_id=0,
    )
    # Only 1 frame of presence
    detector.update([person_near], [shelf_zone], start_ts)
    exit_ts = start_ts + timedelta(seconds=1.0)
    events = detector.update([], [shelf_zone], exit_ts)
    assert len(events) == 0, "Brief pass-by should not emit interaction event"


# ============================================================================
# Gate 6 & P0.7: Shelf Occupancy & Temporal Smoothing
# ============================================================================


def test_product_occupancy_shelf_classifier() -> None:
    classifier = ProductOccupancyShelfClassifier(
        capacity=5, empty_threshold=0.05, low_threshold=0.35, smoothing_window=3
    )

    # 4 products -> ok
    result = classifier.classify_occupancy("shelf_A", 4)
    assert isinstance(result, ShelfOccupancyResult)
    assert result.status == "ok"
    assert pytest.approx(result.occupancy, abs=0.01) == 0.8

    # 0 products -> empty
    result2 = classifier.classify_occupancy("shelf_B", 0)
    assert result2.status == "empty"
    assert pytest.approx(result2.occupancy, abs=0.01) == 0.0


def test_product_occupancy_temporal_smoothing() -> None:
    """A single bad frame does not immediately flip status."""
    classifier = ProductOccupancyShelfClassifier(
        capacity=5, empty_threshold=0.05, low_threshold=0.35, smoothing_window=5
    )
    # Steady stocked state (5 items)
    for _ in range(4):
        classifier.classify_occupancy("shelf_S", 5)

    # Glitch frame: detector momentarily misses items (0 items)
    result = classifier.classify_occupancy("shelf_S", 0)
    # Median of [1.0, 1.0, 1.0, 1.0, 0.0] is 1.0 -> status stays "ok"
    assert result.status == "ok"


def test_product_occupancy_classifier_reset() -> None:
    """reset() clears history so next call starts fresh."""
    classifier = ProductOccupancyShelfClassifier(capacity=5)
    for _ in range(3):
        classifier.classify_occupancy("shelf_R", 5)
    classifier.reset()
    result = classifier.classify_occupancy("shelf_R", 0)
    assert result.status == "empty"


def test_classify_occupancy_from_detections_polygon_filter() -> None:
    """Products outside the shelf ROI polygon are not counted."""
    zone = ZoneConfig(
        zone_id="shelf_01",
        zone_type="shelf",
        polygon=[(100, 100), (200, 100), (200, 200), (100, 200)],
        label="Test Shelf",
    )
    classifier = ProductOccupancyShelfClassifier(capacity=5, empty_threshold=0.05)
    # 1 product inside zone centroid at (150, 150), 1 outside at (50, 50)
    bboxes = [(130, 130, 40, 40), (30, 30, 40, 40)]
    result = classifier.classify_occupancy_from_detections("shelf_01", bboxes, zone)
    # Only 1 product inside -> occupancy 0.2 -> low
    assert result.occupancy == pytest.approx(0.2, abs=0.01)


def test_check_shelves_with_detection_occupancy() -> None:
    zone = ZoneConfig(
        zone_id="shelf_snacks",
        zone_type="shelf",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        label="Snacks",
    )
    classifier = ProductOccupancyShelfClassifier(capacity=5)
    frame = Frame(
        source_id="cam_01",
        timestamp=datetime.now(UTC),
        width=640,
        height=480,
    )
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)

    events = check_shelves(
        frame=frame,
        pixels=pixels,
        classifier=classifier,
        shelf_zones=[zone],
        product_counts_by_shelf={"shelf_snacks": 4},
    )

    assert len(events) == 1
    assert events[0].status == "ok"
    assert events[0].occupancy == pytest.approx(0.8)


# ============================================================================
# P1.2: Zone Transitions (Pydantic contract)
# ============================================================================


def test_zone_transition_tracker() -> None:
    tracker = ZoneTransitionTracker()
    now = datetime.now(UTC)

    # Person 1 enters entrance zone
    e1 = [
        DetectionEvent(
            event_id="e1",
            track_id="t1",
            timestamp=now,
            bbox=(10, 10, 20, 20),
            zone_id="entrance",
            event_type="in_zone",
        )
    ]
    tracker.update(e1)

    # Person 1 moves to shelf zone
    e2 = [
        DetectionEvent(
            event_id="e2",
            track_id="t1",
            timestamp=now + timedelta(seconds=5),
            bbox=(50, 50, 20, 20),
            zone_id="shelf_snacks",
            event_type="in_zone",
        )
    ]
    transitions = tracker.update(e2)
    assert len(transitions) == 1
    assert isinstance(transitions[0], ZoneTransition)
    assert transitions[0].from_zone_id == "entrance"
    assert transitions[0].to_zone_id == "shelf_snacks"

    # Person 1 moves to checkout
    e3 = [
        DetectionEvent(
            event_id="e3",
            track_id="t1",
            timestamp=now + timedelta(seconds=15),
            bbox=(90, 90, 20, 20),
            zone_id="checkout",
            event_type="in_zone",
        )
    ]
    tracker.update(e3)

    assert tracker.get_track_path("t1") == ["entrance", "shelf_snacks", "checkout"]
    counts = tracker.get_transition_counts()
    assert counts[("entrance", "shelf_snacks")] == 1
    assert counts[("shelf_snacks", "checkout")] == 1


# ============================================================================
# Gates 1-8 Automated Verification Suite
# ============================================================================


def test_cv_evaluator_scene_count() -> None:
    """build_open_retail_synthetic_suite must return exactly 10 scenes (A-J)."""
    scenarios = build_open_retail_synthetic_suite()
    scene_ids = {s.scene_id for s in scenarios}
    assert len(scenarios) == 10
    assert scene_ids == {
        "Scene_A", "Scene_B", "Scene_C", "Scene_D", "Scene_E",
        "Scene_F", "Scene_G", "Scene_H", "Scene_I", "Scene_J",
    }


def test_cv_evaluator_all_gates_pass() -> None:
    """Run evaluation protocol against synthetic open retail benchmark suite."""
    backend = MockPredictorBackend(simulated_latency_ms=10.0)
    evaluator = CVEvaluator(backend=backend, model_version="yolo26n_test")
    scenarios = build_open_retail_synthetic_suite()

    report = evaluator.run_suite(scenarios)

    assert report.total_frames > 0
    assert report.person_metrics.precision >= 0.90
    assert report.product_metrics.precision >= 0.85
    assert report.shelf_accuracy >= 0.90
    assert report.id_switches == 0
    assert report.p50_latency_ms <= 330.0
    assert report.all_gates_passed, f"Failed gates: {[g for g in report.gates if not g.passed]}"
