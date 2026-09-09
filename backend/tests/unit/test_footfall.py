import json
from datetime import datetime
from pathlib import Path

import numpy as np
import numpy.typing as npt
from analytics.footfall import FootfallTracker, _default_footfall_tracker, process_frame
from core.schemas import DetectionEvent, Frame, ZoneConfig
from vision.inference_backend import InferenceBackend, RawDetection
from vision.tracker import TrackedDetection, Tracker

fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
SYNTHETIC_TRACKS_PATH = fixtures_dir / "synthetic_tracks.json"


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


def test_directional_enter_into_store() -> None:
    """A person walking into the store across an entry_exit zone triggers 'enter'

    and does NOT trigger 'exit' when stepping off the polygon into the store interior.
    """
    tracker = FootfallTracker(mode="directional")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Frame 1: Exterior (anchor y=50)
    det_f1 = [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)]
    ev1 = tracker.update(frame_meta, det_f1, zones)
    assert len(ev1) == 0

    # Frame 2: Stepping into zone (anchor y=150)
    det_f2 = [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)]
    ev2 = tracker.update(frame_meta, det_f2, zones)
    assert len(ev2) == 0

    # Frame 3: Inside zone center (anchor y=200)
    det_f3 = [TrackedDetection(track_id="trk_1", bbox=(180, 160, 40, 40), confidence=0.9)]
    ev3 = tracker.update(frame_meta, det_f3, zones)
    assert len(ev3) == 0

    # Frame 4: Exiting zone into store interior (anchor y=350)
    det_f4 = [TrackedDetection(track_id="trk_1", bbox=(180, 310, 40, 40), confidence=0.9)]
    ev4 = tracker.update(frame_meta, det_f4, zones)
    assert len(ev4) == 1
    assert ev4[0].event_type == "enter"
    assert ev4[0].zone_id == "entrance_1"
    assert ev4[0].track_id == "trk_1"

    # Frame 5: Further into store interior (anchor y=400)
    det_f5 = [TrackedDetection(track_id="trk_1", bbox=(180, 360, 40, 40), confidence=0.9)]
    ev5 = tracker.update(frame_meta, det_f5, zones)
    assert len(ev5) == 0

    # Overall count: 1 enter, 0 exits -> net_occupancy = 1
    all_events = ev1 + ev2 + ev3 + ev4 + ev5
    enters = sum(1 for e in all_events if e.event_type == "enter")
    exits = sum(1 for e in all_events if e.event_type == "exit")
    assert enters == 1
    assert exits == 0
    assert max(0, enters - exits) == 1


def test_directional_exit_from_store() -> None:
    """A person walking out of the store across an entry_exit zone triggers 'exit'

    and does NOT trigger 'enter'.
    """
    tracker = FootfallTracker(directional=True)
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Frame 1: Inside store interior (anchor y=350)
    det_f1 = [TrackedDetection(track_id="trk_1", bbox=(180, 310, 40, 40), confidence=0.9)]
    ev1 = tracker.update(frame_meta, det_f1, zones)
    assert len(ev1) == 0

    # Frame 2: Entering zone from inside (anchor y=250)
    det_f2 = [TrackedDetection(track_id="trk_1", bbox=(180, 210, 40, 40), confidence=0.9)]
    ev2 = tracker.update(frame_meta, det_f2, zones)
    assert len(ev2) == 0

    # Frame 3: Exiting zone towards exterior (anchor y=50)
    det_f3 = [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)]
    ev3 = tracker.update(frame_meta, det_f3, zones)
    assert len(ev3) == 1
    assert ev3[0].event_type == "exit"
    assert ev3[0].zone_id == "entrance_1"
    assert ev3[0].track_id == "trk_1"

    # Frame 4: Outside on sidewalk (anchor y=30)
    det_f4 = [TrackedDetection(track_id="trk_1", bbox=(180, 0, 40, 40), confidence=0.9)]
    ev4 = tracker.update(frame_meta, det_f4, zones)
    assert len(ev4) == 0

    all_events = ev1 + ev2 + ev3 + ev4
    enters = sum(1 for e in all_events if e.event_type == "enter")
    exits = sum(1 for e in all_events if e.event_type == "exit")
    assert enters == 0
    assert exits == 1


def test_directional_net_occupancy_lifecycle() -> None:
    """A person enters the store and later exits.

    Net occupancy is 1 while inside, 0 after leaving.
    """
    tracker = FootfallTracker(mode="directional")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Inward journey: y=50 -> y=150 -> y=350
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)],
        zones,
    )
    ev_in = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 310, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_in) == 1
    assert ev_in[0].event_type == "enter"

    # Outward journey: y=350 -> y=250 -> y=50
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 210, 40, 40), confidence=0.9)],
        zones,
    )
    ev_out = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_out) == 1
    assert ev_out[0].event_type == "exit"


def test_directional_turnaround_no_crossing() -> None:
    """A person stepping into the threshold zone and backing out to the exterior

    does not generate an enter or exit event.
    """
    tracker = FootfallTracker(mode="directional")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Start exterior (y=50), step into entrance (y=120), turn around and step back outside (y=50)
    ev1 = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )
    ev2 = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 80, 40, 40), confidence=0.9)],
        zones,
    )
    ev3 = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )

    assert len(ev1 + ev2 + ev3) == 0


def test_directional_horizontal_movement() -> None:
    """Directional tracking works with custom entry_direction ('left_to_right')."""
    tracker = FootfallTracker(mode="directional", entry_direction="left_to_right")
    zone = ZoneConfig(
        zone_id="turnstile",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Turnstile",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Person 1: moves left to right (x=50 -> x=150 -> x=350) -> enters store
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(30, 180, 40, 40), confidence=0.9)],
        zones,
    )
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(130, 180, 40, 40), confidence=0.9)],
        zones,
    )
    ev1 = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(330, 180, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev1) == 1
    assert ev1[0].event_type == "enter"

    # Person 2: moves right to left (x=350 -> x=150 -> x=50) -> exits store
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_2", bbox=(330, 180, 40, 40), confidence=0.9)],
        zones,
    )
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_2", bbox=(130, 180, 40, 40), confidence=0.9)],
        zones,
    )
    ev2 = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_2", bbox=(30, 180, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev2) == 1
    assert ev2[0].event_type == "exit"


def test_line_crossing_mode() -> None:
    """Virtual tripwire line crossing emits enter on forward crossing, exit on reverse."""
    tracker = FootfallTracker(mode="line_crossing", entry_direction="top_to_bottom")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Inward crossing across midline y=200: (y=150 -> y=250)
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)],
        zones,
    )
    ev_cross_in = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 210, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_cross_in) == 1
    assert ev_cross_in[0].event_type == "enter"

    # Staying inside: no duplicate
    ev_stay = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 230, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_stay) == 0

    # Outward crossing: (y=250 -> y=150)
    ev_cross_out = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_cross_out) == 1
    assert ev_cross_out[0].event_type == "exit"


def test_directional_emit_on_zone_enter() -> None:
    """Test emit_on='zone_enter' emits immediately upon entering from exterior."""
    tracker = FootfallTracker(mode="directional", emit_on="zone_enter")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Outside: y=50
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )
    # Entering zone: y=150 -> emits 'enter' immediately
    ev_enter = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 110, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_enter) == 1
    assert ev_enter[0].event_type == "enter"

    # Exiting into store: y=350 -> does NOT emit 'exit'
    ev_exit = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_1", bbox=(180, 310, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_exit) == 0


def test_shelf_zone_emits_in_zone() -> None:
    """A zone configured with zone_type='shelf' emits 'in_zone' events for dwell tracking."""
    tracker = FootfallTracker()
    shelf_zone = ZoneConfig(
        zone_id="shelf_dairy",
        zone_type="shelf",
        polygon=[(400, 100), (600, 100), (600, 300), (400, 300)],
        label="Dairy Shelf",
    )
    zones = [shelf_zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Person inside shelf zone (bottom center: 500, 200)
    det = [TrackedDetection(track_id="trk_shelf", bbox=(480, 160, 40, 40), confidence=0.9)]
    events = tracker.update(frame_meta, det, zones)

    assert len(events) == 1
    assert events[0].event_type == "in_zone"
    assert events[0].zone_id == "shelf_dairy"
    assert events[0].track_id == "trk_shelf"


def test_directional_emit_on_zone_enter_first_detection_inside() -> None:
    """A track whose very first detection is already inside the zone emits 'enter' immediately."""
    tracker = FootfallTracker(mode="directional", emit_on="zone_enter")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # First frame: Track appears directly inside zone on exterior half
    # (anchor y=150, centroid y=200)
    det_f1 = [TrackedDetection(track_id="trk_first_in", bbox=(180, 110, 40, 40), confidence=0.9)]
    ev1 = tracker.update(frame_meta, det_f1, zones)
    assert len(ev1) == 1
    assert ev1[0].event_type == "enter"
    assert ev1[0].zone_id == "entrance_1"

    # Subsequent frame: still inside -> no duplicate enter
    det_f2 = [TrackedDetection(track_id="trk_first_in", bbox=(180, 140, 40, 40), confidence=0.9)]
    ev2 = tracker.update(frame_meta, det_f2, zones)
    assert len(ev2) == 0

    # Stepping into store interior: y=350 -> does not emit exit
    det_f3 = [TrackedDetection(track_id="trk_first_in", bbox=(180, 310, 40, 40), confidence=0.9)]
    ev3 = tracker.update(frame_meta, det_f3, zones)
    assert len(ev3) == 0


def test_directional_emit_on_zone_enter_outward_exit() -> None:
    """A track walking from store interior towards exterior emits 'exit' upon crossing out."""
    tracker = FootfallTracker(mode="directional", emit_on="zone_enter")
    zone = ZoneConfig(
        zone_id="entrance_1",
        zone_type="entry_exit",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Main Entrance",
    )
    zones = [zone]
    now = datetime(2026, 8, 29, 10, 0, 0)
    frame_meta = Frame(source_id="cam_01", timestamp=now, width=1920, height=1080)

    # Frame 1: Person inside store interior (anchor y=350)
    tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_out", bbox=(180, 310, 40, 40), confidence=0.9)],
        zones,
    )

    # Frame 2: Entering zone from interior (anchor y=250) -> does NOT emit enter
    ev_in_zone = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_out", bbox=(180, 210, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_in_zone) == 0

    # Frame 3: Exiting zone towards exterior (anchor y=50) -> emits exit
    ev_exit = tracker.update(
        frame_meta,
        [TrackedDetection(track_id="trk_out", bbox=(180, 10, 40, 40), confidence=0.9)],
        zones,
    )
    assert len(ev_exit) == 1
    assert ev_exit[0].event_type == "exit"
    assert ev_exit[0].zone_id == "entrance_1"

