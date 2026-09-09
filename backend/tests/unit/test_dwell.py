import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from analytics.dwell import DwellTracker
from analytics.footfall import FootfallTracker
from core.schemas import DetectionEvent, Frame, ZoneConfig
from vision.tracker import TrackedDetection

fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
SYNTHETIC_TRACKS_PATH = fixtures_dir / "synthetic_tracks.json"


def test_dwell_single_visit_duration() -> None:
    """A synthetic track entering product_display zone for N frames at known fps
    emits one DwellEvent with duration_sec ≈ N/fps.
    """
    fps = 30.0
    num_frames = 30
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker()

    # Feed N frames with in_zone detection event
    for i in range(num_frames):
        ts = start_time + timedelta(seconds=i / fps)
        events = [
            DetectionEvent(
                event_id=f"evt_{i}",
                track_id="trk_1",
                timestamp=ts,
                bbox=(100, 100, 50, 50),
                zone_id="promo_zone",
                event_type="in_zone",
            )
        ]
        dwell_events = tracker.update(events)
        assert len(dwell_events) == 0, "No DwellEvent should emit while track is still inside"

    # Frame N: track exits (empty event list)
    events_exit: list[DetectionEvent] = []
    dwell_events = tracker.update(events_exit)

    assert len(dwell_events) == 1
    dwell = dwell_events[0]
    assert dwell.track_id == "trk_1"
    assert dwell.zone_id == "promo_zone"
    assert dwell.start_ts == start_time
    assert dwell.end_ts == start_time + timedelta(seconds=(num_frames - 1) / fps)
    expected_duration = (num_frames - 1) / fps
    assert dwell.duration_sec == pytest.approx(expected_duration, abs=1e-3)
    assert dwell.duration_sec == pytest.approx(num_frames / fps, abs=1.0 / fps + 1e-3)


def test_dwell_multiple_separate_visits() -> None:
    """A track entering, leaving, and re-entering the same zone produces two
    separate DwellEvents, not one merged event.
    """
    fps = 10.0
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker()

    # Visit 1: Frames 0 to 4 (5 frames)
    for i in range(5):
        ts = start_time + timedelta(seconds=i / fps)
        events = [
            DetectionEvent(
                event_id=f"evt_v1_{i}",
                track_id="trk_1",
                timestamp=ts,
                bbox=(100, 100, 50, 50),
                zone_id="promo_zone",
                event_type="in_zone",
            )
        ]
        assert len(tracker.update(events)) == 0

    # Leave zone: Frame 5
    dwell_events1 = tracker.update([])
    assert len(dwell_events1) == 1
    d1 = dwell_events1[0]
    assert d1.track_id == "trk_1"
    assert d1.zone_id == "promo_zone"
    assert d1.start_ts == start_time
    assert d1.end_ts == start_time + timedelta(seconds=4 / fps)
    assert d1.duration_sec == pytest.approx(4 / fps, abs=1e-3)

    # Outside zone for frames 6 to 9
    for _ in range(6, 10):
        assert len(tracker.update([])) == 0

    # Visit 2: Frames 10 to 15 (6 frames)
    v2_start = start_time + timedelta(seconds=10 / fps)
    for i in range(10, 16):
        ts = start_time + timedelta(seconds=i / fps)
        events = [
            DetectionEvent(
                event_id=f"evt_v2_{i}",
                track_id="trk_1",
                timestamp=ts,
                bbox=(100, 100, 50, 50),
                zone_id="promo_zone",
                event_type="in_zone",
            )
        ]
        assert len(tracker.update(events)) == 0

    # Leave zone again: Frame 16
    dwell_events2 = tracker.update([])
    assert len(dwell_events2) == 1
    d2 = dwell_events2[0]
    assert d2.track_id == "trk_1"
    assert d2.zone_id == "promo_zone"
    assert d2.start_ts == v2_start
    assert d2.end_ts == start_time + timedelta(seconds=15 / fps)
    assert d2.duration_sec == pytest.approx(5 / fps, abs=1e-3)

    # Ensure two distinct events with different IDs and non-overlapping timestamps
    assert d1.event_id != d2.event_id
    assert d2.start_ts > d1.end_ts


def test_dwell_session_end_flush() -> None:
    """A track still inside a zone when session ends is accounted for via flush()."""
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker()

    # Track 1 and Track 2 in zone
    events = [
        DetectionEvent(
            event_id="evt_1",
            track_id="trk_1",
            timestamp=start_time,
            bbox=(100, 100, 50, 50),
            zone_id="zone_a",
            event_type="in_zone",
        ),
        DetectionEvent(
            event_id="evt_2",
            track_id="trk_2",
            timestamp=start_time,
            bbox=(200, 200, 50, 50),
            zone_id="zone_b",
            event_type="in_zone",
        ),
    ]
    tracker.update(events)

    # Second frame 10 seconds later
    t2 = start_time + timedelta(seconds=10)
    events2 = [
        DetectionEvent(
            event_id="evt_3",
            track_id="trk_1",
            timestamp=t2,
            bbox=(100, 100, 50, 50),
            zone_id="zone_a",
            event_type="in_zone",
        ),
        DetectionEvent(
            event_id="evt_4",
            track_id="trk_2",
            timestamp=t2,
            bbox=(200, 200, 50, 50),
            zone_id="zone_b",
            event_type="in_zone",
        ),
    ]
    tracker.update(events2)

    # Session ends abruptly without exit frame
    flushed_events = tracker.flush()
    assert len(flushed_events) == 2

    tracks_flushed = {e.track_id: e for e in flushed_events}
    assert "trk_1" in tracks_flushed
    assert "trk_2" in tracks_flushed
    assert tracks_flushed["trk_1"].duration_sec == pytest.approx(10.0)
    assert tracks_flushed["trk_1"].start_ts == start_time
    assert tracks_flushed["trk_1"].end_ts == t2
    assert tracks_flushed["trk_2"].duration_sec == pytest.approx(10.0)

    # Subsequent flush returns empty list
    assert len(tracker.flush()) == 0


def test_dwell_reset() -> None:
    """reset() clears all active dwell tracking state."""
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker()

    events = [
        DetectionEvent(
            event_id="evt_1",
            track_id="trk_1",
            timestamp=start_time,
            bbox=(100, 100, 50, 50),
            zone_id="zone_a",
            event_type="in_zone",
        )
    ]
    tracker.update(events)

    tracker.reset()
    # After reset, flush should return nothing
    assert len(tracker.flush()) == 0
    # And empty update should return nothing
    assert len(tracker.update([])) == 0


def test_dwell_ignores_entry_exit_events() -> None:
    """DwellTracker only processes 'in_zone' events and ignores 'enter'/'exit' events."""
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker()

    events = [
        DetectionEvent(
            event_id="evt_enter",
            track_id="trk_1",
            timestamp=start_time,
            bbox=(100, 100, 50, 50),
            zone_id="zone_entrance",
            event_type="enter",
        ),
        DetectionEvent(
            event_id="evt_exit",
            track_id="trk_1",
            timestamp=start_time + timedelta(seconds=5),
            bbox=(100, 100, 50, 50),
            zone_id="zone_entrance",
            event_type="exit",
        ),
    ]
    assert len(tracker.update(events)) == 0
    assert len(tracker.flush()) == 0


def test_dwell_min_duration_threshold() -> None:
    """Visits shorter than min_duration_sec are discarded when configured."""
    start_time = datetime(2026, 8, 29, 10, 0, 0)
    tracker = DwellTracker(min_duration_sec=3.0)

    # Short visit: 1 second
    events1 = [
        DetectionEvent(
            event_id="evt_1",
            track_id="trk_short",
            timestamp=start_time,
            bbox=(100, 100, 50, 50),
            zone_id="zone_a",
            event_type="in_zone",
        )
    ]
    tracker.update(events1)
    events2 = [
        DetectionEvent(
            event_id="evt_2",
            track_id="trk_short",
            timestamp=start_time + timedelta(seconds=1.0),
            bbox=(100, 100, 50, 50),
            zone_id="zone_a",
            event_type="in_zone",
        )
    ]
    tracker.update(events2)
    # Exit: 1.0s < 3.0s -> filtered out
    dwells = tracker.update([])
    assert len(dwells) == 0

    # Long visit: 5 seconds
    t_long = start_time + timedelta(seconds=10)
    tracker.update(
        [
            DetectionEvent(
                event_id="evt_3",
                track_id="trk_long",
                timestamp=t_long,
                bbox=(100, 100, 50, 50),
                zone_id="zone_a",
                event_type="in_zone",
            )
        ]
    )
    tracker.update(
        [
            DetectionEvent(
                event_id="evt_4",
                track_id="trk_long",
                timestamp=t_long + timedelta(seconds=5.0),
                bbox=(100, 100, 50, 50),
                zone_id="zone_a",
                event_type="in_zone",
            )
        ]
    )
    dwells_long = tracker.update([])
    assert len(dwells_long) == 1
    assert dwells_long[0].track_id == "trk_long"
    assert dwells_long[0].duration_sec == pytest.approx(5.0)


def test_dwell_no_pii_fields() -> None:
    """Verify DwellEvent has no pixel data, image crops, or embeddings."""
    tracker = DwellTracker()
    now = datetime(2026, 8, 29, 10, 0, 0)
    tracker.update(
        [
            DetectionEvent(
                event_id="evt_1",
                track_id="trk_1",
                timestamp=now,
                bbox=(100, 100, 50, 50),
                zone_id="zone_promo",
                event_type="in_zone",
            )
        ]
    )
    dwells = tracker.flush()
    assert len(dwells) == 1
    dwell = dwells[0]

    model_fields = set(dwell.model_dump().keys())
    prohibited_fields = {"image", "frame", "crop", "embedding", "pixels", "face"}
    assert prohibited_fields.isdisjoint(model_fields)


def test_dwell_synthetic_tracks_fixture_integration() -> None:
    """Integration test: feed synthetic tracks dataset through FootfallTracker
    and into DwellTracker.
    """
    assert SYNTHETIC_TRACKS_PATH.is_file()

    with SYNTHETIC_TRACKS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    zones = [ZoneConfig.model_validate(z) for z in data["zones"]]
    footfall_tracker = FootfallTracker()
    dwell_tracker = DwellTracker()

    all_dwell_events = []

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
        dwell_events = dwell_tracker.update(events)
        all_dwell_events.extend(dwell_events)

    # Flush session end
    all_dwell_events.extend(dwell_tracker.flush())

    # Track 3 was in zone_display_aisle
    display_dwells = [d for d in all_dwell_events if d.zone_id == "zone_display_aisle"]
    assert len(display_dwells) >= 1
    assert display_dwells[0].track_id == "3"
    assert display_dwells[0].duration_sec >= 0.0
