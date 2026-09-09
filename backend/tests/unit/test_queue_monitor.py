from datetime import UTC, datetime

import pytest

from analytics.queue_monitor import QueueMonitor
from core.schemas import Frame, QueueEvent, ZoneConfig
from vision.tracker import TrackedDetection


@pytest.fixture
def checkout_zone() -> ZoneConfig:
    return ZoneConfig(
        zone_id="checkout_counter_1",
        zone_type="checkout",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        label="Checkout 1",
    )


@pytest.fixture
def secondary_checkout_zone() -> ZoneConfig:
    return ZoneConfig(
        zone_id="checkout_counter_2",
        zone_type="checkout",
        polygon=[(500, 100), (700, 100), (700, 300), (500, 300)],
        label="Checkout 2",
    )


@pytest.fixture
def non_checkout_zone() -> ZoneConfig:
    return ZoneConfig(
        zone_id="shelf_1",
        zone_type="shelf",
        polygon=[(0, 0), (50, 0), (50, 50), (0, 50)],
        label="Shelf 1",
    )


def make_frame(ts: datetime) -> Frame:
    return Frame(
        source_id="cam_test",
        timestamp=ts,
        width=1280,
        height=720,
    )


def make_track(
    track_id: str,
    bbox: tuple[int, int, int, int],
    confidence: float = 0.9,
) -> TrackedDetection:
    return TrackedDetection(
        track_id=track_id,
        bbox=bbox,
        confidence=confidence,
        class_id=0,
    )


def test_queue_length_matches_inside_tracks(checkout_zone: ZoneConfig) -> None:
    monitor = QueueMonitor(service_rate_estimate_sec=90.0)
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    # Track 1 inside: bbox (150, 150, 40, 60) -> anchor (170, 210)
    # Track 2 inside: bbox (200, 180, 20, 40) -> anchor (210, 220)
    # Track 3 outside: bbox (400, 400, 50, 50) -> anchor (425, 450)
    tracks = [
        make_track("1", (150, 150, 40, 60)),
        make_track("2", (200, 180, 20, 40)),
        make_track("3", (400, 400, 50, 50)),
    ]

    events = monitor.update(frame, tracks, [checkout_zone])

    assert len(events) == 1
    event = events[0]
    assert isinstance(event, QueueEvent)
    assert event.counter_id == "checkout_counter_1"
    assert event.queue_length == 2
    assert event.timestamp == ts
    # Cold-start fallback: 2 * 90.0s = 180.0s
    assert event.avg_wait_est_sec == pytest.approx(180.0)


def test_zero_people_in_checkout_zone_emits_event(checkout_zone: ZoneConfig) -> None:
    monitor = QueueMonitor(service_rate_estimate_sec=90.0)
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    # Empty detections
    events = monitor.update(frame, [], [checkout_zone])

    assert len(events) == 1
    event = events[0]
    assert event.counter_id == "checkout_counter_1"
    assert event.queue_length == 0
    assert event.avg_wait_est_sec == 0.0
    assert event.timestamp == ts


def test_two_separate_checkout_zones_independent(
    checkout_zone: ZoneConfig,
    secondary_checkout_zone: ZoneConfig,
) -> None:
    monitor = QueueMonitor(service_rate_estimate_sec=60.0)
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    # Track 1 in Zone 1 (anchor: 150+20, 150+50 = 170, 200)
    # Track 2 & 3 in Zone 2 (anchors: 550+10, 150+30 = 560, 180 and 600+10, 200+20 = 610, 220)
    tracks = [
        make_track("1", (150, 150, 40, 50)),
        make_track("2", (550, 150, 20, 30)),
        make_track("3", (600, 200, 20, 20)),
    ]

    events = monitor.update(frame, tracks, [checkout_zone, secondary_checkout_zone])

    assert len(events) == 2
    event_by_counter = {e.counter_id: e for e in events}

    assert "checkout_counter_1" in event_by_counter
    assert "checkout_counter_2" in event_by_counter

    assert event_by_counter["checkout_counter_1"].queue_length == 1
    assert event_by_counter["checkout_counter_1"].avg_wait_est_sec == pytest.approx(60.0)

    assert event_by_counter["checkout_counter_2"].queue_length == 2
    assert event_by_counter["checkout_counter_2"].avg_wait_est_sec == pytest.approx(120.0)


def test_ignores_non_checkout_zones(
    checkout_zone: ZoneConfig,
    non_checkout_zone: ZoneConfig,
) -> None:
    monitor = QueueMonitor()
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    events = monitor.update(frame, [], [checkout_zone, non_checkout_zone])

    assert len(events) == 1
    assert events[0].counter_id == "checkout_counter_1"


def test_empty_checkout_zones_returns_empty_list() -> None:
    monitor = QueueMonitor()
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    events = monitor.update(frame, [], [])
    assert events == []


def test_avg_wait_est_sec_updates_with_empirical_completed_service(
    checkout_zone: ZoneConfig,
) -> None:
    monitor = QueueMonitor(service_rate_estimate_sec=90.0)

    # Frame 1: t = 0s - Track 1 enters
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1_track = make_track("1", (150, 150, 40, 50))
    events_1 = monitor.update(make_frame(t0), [t1_track], [checkout_zone])
    assert events_1[0].queue_length == 1
    assert events_1[0].avg_wait_est_sec == pytest.approx(90.0)

    # Frame 2: t = 20s - Track 1 still in zone
    t1 = datetime(2026, 8, 29, 10, 0, 20, tzinfo=UTC)
    events_2 = monitor.update(make_frame(t1), [t1_track], [checkout_zone])
    assert events_2[0].queue_length == 1
    assert events_2[0].avg_wait_est_sec == pytest.approx(90.0)

    # Frame 3: t = 40s - Track 1 still in zone, Track 2 arrives
    t2 = datetime(2026, 8, 29, 10, 0, 40, tzinfo=UTC)
    t2_track = make_track("2", (200, 150, 40, 50))
    events_3 = monitor.update(make_frame(t2), [t1_track, t2_track], [checkout_zone])
    assert events_3[0].queue_length == 2
    assert events_3[0].avg_wait_est_sec == pytest.approx(180.0)

    # Frame 4: t = 60s - Track 1 completes service (leaves), Track 2 and Track 3 present
    # Track 1 was in zone from t0 (0s) to t2 (40s) -> duration = 40s
    t3 = datetime(2026, 8, 29, 10, 1, 0, tzinfo=UTC)
    t3_track = make_track("3", (250, 150, 20, 20))
    events_4 = monitor.update(make_frame(t3), [t2_track, t3_track], [checkout_zone])

    assert events_4[0].queue_length == 2
    # Empirical service time is now 40.0s (from Track 1)
    # Estimated wait for 2 people = 2 * 40.0 = 80.0s
    assert events_4[0].avg_wait_est_sec == pytest.approx(80.0)

    # Frame 5: t = 90s - Track 2 leaves, Track 3 still present
    # Track 2 entered at t2 (40s) and last seen at t3 (60s) -> duration = 20s
    # Average service time = (40s + 20s) / 2 = 30.0s
    t4 = datetime(2026, 8, 29, 10, 1, 30, tzinfo=UTC)
    events_5 = monitor.update(make_frame(t4), [t3_track], [checkout_zone])

    assert events_5[0].queue_length == 1
    # Estimated wait for 1 person = 1 * 30.0s = 30.0s
    assert events_5[0].avg_wait_est_sec == pytest.approx(30.0)


def test_reset_clears_accumulated_history_and_active_tracks(
    checkout_zone: ZoneConfig,
) -> None:
    monitor = QueueMonitor(service_rate_estimate_sec=90.0)

    # Sequence with completed traversal
    t0 = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 8, 29, 10, 0, 30, tzinfo=UTC)
    t2 = datetime(2026, 8, 29, 10, 1, 0, tzinfo=UTC)

    t1_track = make_track("1", (150, 150, 40, 50))
    monitor.update(make_frame(t0), [t1_track], [checkout_zone])
    monitor.update(make_frame(t1), [t1_track], [checkout_zone])

    # Track 1 leaves, empirical service time becomes 30s
    t2_track = make_track("2", (200, 150, 40, 50))
    events = monitor.update(make_frame(t2), [t2_track], [checkout_zone])
    assert events[0].avg_wait_est_sec == pytest.approx(30.0)

    # Reset monitor
    monitor.reset()

    # After reset, new frame should fall back to 90.0s
    t3 = datetime(2026, 8, 29, 10, 2, 0, tzinfo=UTC)
    events_after_reset = monitor.update(make_frame(t3), [t2_track], [checkout_zone])
    assert events_after_reset[0].queue_length == 1
    assert events_after_reset[0].avg_wait_est_sec == pytest.approx(90.0)


def test_no_pii_in_queue_event_or_state(checkout_zone: ZoneConfig) -> None:
    monitor = QueueMonitor()
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    tracks = [make_track("1", (150, 150, 40, 50))]

    events = monitor.update(make_frame(ts), tracks, [checkout_zone])
    event = events[0]

    # Verify QueueEvent schema fields - strictly no raw images/crops/embeddings
    event_dict = event.model_dump()
    forbidden_keys = {"image", "frame", "crop", "embedding", "face", "pixels"}
    for key in event_dict:
        assert key.lower() not in forbidden_keys


def test_anchor_point_calculation(checkout_zone: ZoneConfig) -> None:
    monitor = QueueMonitor()
    ts = datetime(2026, 8, 29, 10, 0, 0, tzinfo=UTC)
    frame = make_frame(ts)

    # Box (80, 80, 40, 40) -> anchor is (100, 120) -> inside polygon
    track_inside = make_track("inside", (80, 80, 40, 40))

    # Box (150, 150, 40, 200) -> anchor is (170, 350) -> outside polygon (max y is 300)
    track_outside = make_track("outside", (150, 150, 40, 200))

    events = monitor.update(frame, [track_inside, track_outside], [checkout_zone])
    assert events[0].queue_length == 1
