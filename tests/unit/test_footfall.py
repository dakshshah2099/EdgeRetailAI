import json
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt

from detection.footfall import FootfallTracker, _default_footfall_tracker, process_frame
from detection.inference_backend import InferenceBackend, RawDetection
from detection.tracker import TrackedDetection, Tracker
from schemas import DetectionEvent, Frame, ZoneConfig

SYNTHETIC_TRACKS_PATH = Path("tests/fixtures/synthetic_tracks.json")


class MockBackend(InferenceBackend):
    def __init__(self, detections_per_frame: list[list[RawDetection]]) -> None:
        self.detections_per_frame = detections_per_frame
        self.call_count = 0

    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        if self.call_count < len(self.detections_per_frame):
            dets = self.detections_per_frame[self.call_count]
        else:
            dets = []
        self.call_count += 1
        return dets


def test_footfall_tracker_reset() -> None:
    tracker = FootfallTracker()
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    frame_meta = Frame(
        source_id="cam_01",
        timestamp=datetime(2026, 8, 29, 10, 0, 0),
        width=1920,
        height=1080,
    )
    det = [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)]

    events1 = tracker.update(frame_meta, det, [zone])
    assert len(events1) == 1
    assert "trk_1" in tracker._inside_zones

    tracker.reset()
    assert len(tracker._inside_zones) == 0

    # After reset, same detection position emits enter again as state was cleared
    events2 = tracker.update(frame_meta, det, [zone])
    assert len(events2) == 1
    assert events2[0].event_type == "enter"


def test_footfall_edge_triggered_enter_and_exit() -> None:
    tracker = FootfallTracker()
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]

    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Frame 1: Person outside zone (bottom-center at 200, 50)
    det_f1 = [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)]
    events1 = tracker.update(frame_meta, det_f1, zones)
    assert len(events1) == 0, "Outside zone should emit no enter event"

    # Frame 2: Person moves inside zone (bottom-center at 200, 150) -> EMIT ENTER
    det_f2 = [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)]
    events2 = tracker.update(frame_meta, det_f2, zones)
    assert len(events2) == 1
    assert events2[0].event_type == "enter"
    assert events2[0].zone_id == "entrance_1"
    assert events2[0].track_id == "trk_1"

    # Frame 3: Person stays inside zone (bottom-center at 200, 180) -> MUST NOT EMIT ENTER AGAIN
    det_f3 = [TrackedDetection(track_id="trk_1", bbox=(180, 140, 40, 40), confidence=0.9)]
    events3 = tracker.update(frame_meta, det_f3, zones)
    assert len(events3) == 0, "Staying inside must not emit duplicate enter event (edge-triggered)"

    # Frame 4: Person stays inside zone -> MUST NOT EMIT
    det_f4 = [TrackedDetection(track_id="trk_1", bbox=(180, 160, 40, 40), confidence=0.9)]
    events4 = tracker.update(frame_meta, det_f4, zones)
    assert len(events4) == 0

    # Frame 5: Person moves outside zone (bottom-center at 200, 350) -> EMIT EXIT
    det_f5 = [TrackedDetection(track_id="trk_1", bbox=(180, 310, 40, 40), confidence=0.9)]
    events5 = tracker.update(frame_meta, det_f5, zones)
    assert len(events5) == 1
    assert events5[0].event_type == "exit"
    assert events5[0].zone_id == "entrance_1"
    assert events5[0].track_id == "trk_1"

    # Frame 6: Person stays outside zone -> MUST NOT EMIT EXIT AGAIN
    det_f6 = [TrackedDetection(track_id="trk_1", bbox=(180, 360, 40, 40), confidence=0.9)]
    events6 = tracker.update(frame_meta, det_f6, zones)
    assert len(events6) == 0


def test_product_display_zone_emits_in_zone() -> None:
    tracker = FootfallTracker()
    display_zone = ZoneConfig(
        zone_id="promo_display",
        zone_type="product_display",
        polygon=[(400, 100), (600, 100), (600, 300), (400, 300)],
        label="Promo Display Area",
    )
    zones = [display_zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Person inside display zone (bottom center: 500, 200)
    det = [TrackedDetection(track_id="trk_1", bbox=(480, 160, 40, 40), confidence=0.9)]
    events = tracker.update(frame_meta, det, zones)

    assert len(events) == 1
    assert events[0].event_type == "in_zone"
    assert events[0].zone_id == "promo_display"


def test_end_to_end_synthetic_tracks_fixture() -> None:
    """End-to-end acceptance test using synthetic multi-frame ground-truth tracks."""
    assert SYNTHETIC_TRACKS_PATH.is_file(), (
        f"Synthetic tracks fixture missing: {SYNTHETIC_TRACKS_PATH}"
    )

    with SYNTHETIC_TRACKS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    zones = [ZoneConfig.model_validate(z) for z in data["zones"]]
    expected = data["expected_counts"]

    footfall_tracker = FootfallTracker()
    all_events: list[DetectionEvent] = []

    for frame_data in data["frames"]:
        ts = datetime.fromisoformat(frame_data["timestamp"])
        frame_meta = Frame(source_id="cam_test", timestamp=ts, width=1280, height=720)
        tracked_dets = [
            TrackedDetection(
                track_id=d["track_id"],
                bbox=(
                    int(d["bbox"][0]),
                    int(d["bbox"][1]),
                    int(d["bbox"][2]),
                    int(d["bbox"][3]),
                ),
                confidence=d["confidence"],
                class_id=d["class_id"],
            )
            for d in frame_data["detections"]
        ]
        events = footfall_tracker.update(frame_meta, tracked_dets, zones)
        all_events.extend(events)

    # Count events by zone and type
    counts: dict[str, dict[str, int]] = {}
    for ev in all_events:
        assert ev.zone_id is not None
        zone_counts = counts.setdefault(ev.zone_id, {})
        zone_counts[ev.event_type] = zone_counts.get(ev.event_type, 0) + 1

    assert counts.get("zone_entrance", {}).get("enter", 0) == expected["zone_entrance"]["enter"]
    assert counts.get("zone_entrance", {}).get("exit", 0) == expected["zone_entrance"]["exit"]
    assert (
        counts.get("zone_display_aisle", {}).get("in_zone", 0)
        == expected["zone_display_aisle"]["in_zone"]
    )


def test_process_frame_integration() -> None:
    _default_footfall_tracker.reset()

    mock_frames = [
        [RawDetection(class_id=0, confidence=0.9, bbox=(180, 10, 40, 40))],
        [RawDetection(class_id=0, confidence=0.9, bbox=(180, 110, 40, 40))],
    ]
    backend = MockBackend(mock_frames)
    tracker = Tracker(iou_threshold=0.3, high_conf_threshold=0.5)

    zone = ZoneConfig(
        zone_id="entrance",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Store Entrance",
    )

    dummy_pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    now = datetime(2026, 8, 29, 10, 0, 0)

    # Explicit tracker instance path
    custom_ft = FootfallTracker()
    f1 = Frame(source_id="cam_01", timestamp=now, width=640, height=480)
    ev1 = process_frame(f1, dummy_pixels, backend, tracker, [zone], footfall_tracker=custom_ft)
    assert len(ev1) == 0

    f2 = Frame(source_id="cam_01", timestamp=now, width=640, height=480)
    ev2 = process_frame(f2, dummy_pixels, backend, tracker, [zone], footfall_tracker=custom_ft)
    assert len(ev2) == 1
    assert ev2[0].event_type == "enter"
    assert ev2[0].zone_id == "entrance"

    # Default module tracker path
    tracker.reset()
    backend.call_count = 0
    ev_def1 = process_frame(f1, dummy_pixels, backend, tracker, [zone])
    assert len(ev_def1) == 0
    ev_def2 = process_frame(f2, dummy_pixels, backend, tracker, [zone])
    assert len(ev_def2) == 1
    assert ev_def2[0].event_type == "enter"
