from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import numpy.typing as npt
import pytest
from fastapi.testclient import TestClient

from alerts.alert_engine import AlertEngine
from analytics.dwell import DwellTracker
from analytics.footfall import FootfallTracker
from analytics.heatmap import HeatmapAccumulator
from analytics.queue_monitor import QueueMonitor
from analytics.shelf_classifier import HybridShelfClassifier, TemporalShelfSmoother, check_shelves
from core.schemas import DetectionEvent, Frame, load_config
from storage.repository import EventRepository
from vision.tracker import TrackedDetection


def make_synthetic_frame(
    width: int = 640, height: int = 480
) -> npt.NDArray[np.uint8]:
    """Generate a clean synthetic BGR canvas for video pipeline tests."""
    img = np.full((height, width, 3), 30, dtype=np.uint8)
    for x in range(0, width, 40):
        cv2.line(img, (x, 0), (x, height), (45, 45, 45), 1)
    for y in range(0, height, 40):
        cv2.line(img, (0, y), (width, y), (45, 45, 45), 1)
    return img


def make_shelf_texture(
    status: Literal["empty", "low", "ok"],
    width: int = 250,
    height: int = 180,
) -> npt.NDArray[np.uint8]:
    """Generate shelf crop with high edge texture (ok), moderate (low), or smooth (empty)."""
    img = np.full((height, width, 3), 180, dtype=np.uint8)
    if status == "empty":
        return img
    elif status == "low":
        cv2.rectangle(img, (20, 20), (70, 80), (40, 40, 40), 2)
        cv2.line(img, (20, 50), (70, 50), (10, 10, 10), 2)
        return img
    else:  # status == "ok"
        for x in range(10, width - 20, 20):
            for y in range(10, height - 20, 25):
                cv2.rectangle(img, (x, y), (x + 16, y + 20), (20, 20, 80), -1)
                cv2.rectangle(img, (x, y), (x + 16, y + 20), (255, 255, 255), 1)
                cv2.putText(
                    img, "SKU", (x + 1, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 0, 0), 1
                )
        return img


@pytest.mark.e2e
def test_end_to_end_retail_lifecycle(
    e2e_repo: EventRepository,
    e2e_config_file: Path,
    e2e_client: TestClient,
) -> None:
    """Full lifecycle E2E test: Ingest simulated video sequence -> CV analytics ->

    EventRepository -> FastAPI endpoints -> Alert resolution.
    """
    config = load_config(e2e_config_file)
    zones = config.zones
    checkout_zone = next(z for z in zones if z.zone_id == "zone_checkout_1")
    shelf_zone = next(z for z in zones if z.zone_id == "zone_shelf_beverages")

    # 1. Initialize analytics pipeline components
    footfall_tracker = FootfallTracker(mode="edge")
    dwell_tracker = DwellTracker(min_duration_sec=5.0)
    queue_monitor = QueueMonitor()
    shelf_classifier = HybridShelfClassifier()
    shelf_smoother = TemporalShelfSmoother(alpha=0.5)
    alert_engine = AlertEngine(
        low_stock_threshold=config.low_stock_confidence_threshold,
        queue_congestion_length=config.queue_congestion_length,
    )
    heatmap = HeatmapAccumulator(width=640, height=480, cell_size=20)

    base_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)

    # -------------------------------------------------------------------------
    # Frame 1 (t=0s): Shopper 1 approaches entrance exterior
    # -------------------------------------------------------------------------
    f1_meta = Frame(source_id="cam_main", timestamp=base_time, width=640, height=480)
    f1_tracks = [TrackedDetection(track_id="shopper_1", bbox=(100, 10, 30, 20), confidence=0.92)]
    ff_events_1 = footfall_tracker.update(f1_meta, f1_tracks, zones)
    assert len(ff_events_1) == 0

    # -------------------------------------------------------------------------
    # Frame 2 (t=2s): Shopper 1 crosses into entrance zone -> Enter event
    # -------------------------------------------------------------------------
    t2 = base_time + timedelta(seconds=2)
    f2_meta = Frame(source_id="cam_main", timestamp=t2, width=640, height=480)
    f2_tracks = [
        TrackedDetection(track_id="shopper_1", bbox=(100, 100, 30, 60), confidence=0.94)
    ]
    ff_events_2 = footfall_tracker.update(f2_meta, f2_tracks, zones)
    for ev in ff_events_2:
        e2e_repo.save_detection_event(ev)
    heatmap.add_tracked_detections(f2_tracks)

    # -------------------------------------------------------------------------
    # Frames 3-5 (t=10s to t=30s): Shopper 1 moves to promotional display and dwells
    # -------------------------------------------------------------------------
    t3 = base_time + timedelta(seconds=10)
    f3_meta = Frame(source_id="cam_main", timestamp=t3, width=640, height=480)
    f3_tracks = [
        TrackedDetection(track_id="shopper_1", bbox=(400, 120, 30, 60), confidence=0.91)
    ]
    ff_events_3 = footfall_tracker.update(f3_meta, f3_tracks, zones)
    for ev in ff_events_3:
        e2e_repo.save_detection_event(ev)
    dwell_events_3 = dwell_tracker.update(ff_events_3)
    assert len(dwell_events_3) == 0  # Still dwelling

    t4 = base_time + timedelta(seconds=25)
    f4_meta = Frame(source_id="cam_main", timestamp=t4, width=640, height=480)
    f4_tracks = [
        TrackedDetection(track_id="shopper_1", bbox=(400, 120, 30, 60), confidence=0.93)
    ]
    ff_events_4 = footfall_tracker.update(f4_meta, f4_tracks, zones)
    for ev in ff_events_4:
        e2e_repo.save_detection_event(ev)
    dwell_events_4 = dwell_tracker.update(ff_events_4)
    assert len(dwell_events_4) == 0

    # Frame 5 (t=35s): Shopper 1 leaves display zone -> Dwell event emitted
    t5 = base_time + timedelta(seconds=35)
    f5_meta = Frame(source_id="cam_main", timestamp=t5, width=640, height=480)
    f5_tracks = [
        TrackedDetection(track_id="shopper_1", bbox=(20, 20, 30, 60), confidence=0.90)
    ]
    ff_events_5 = footfall_tracker.update(f5_meta, f5_tracks, zones)
    for ev in ff_events_5:
        e2e_repo.save_detection_event(ev)
    dwell_events_5 = dwell_tracker.update(ff_events_5)
    assert len(dwell_events_5) == 1
    assert dwell_events_5[0].zone_id == "zone_display"
    assert dwell_events_5[0].duration_sec >= 15.0
    e2e_repo.save_dwell_event(dwell_events_5[0])

    # -------------------------------------------------------------------------
    # Frame 6 (t=40s): 4 shoppers queue at checkout counter -> Queue Congestion Alert
    # -------------------------------------------------------------------------
    t6 = base_time + timedelta(seconds=40)
    f6_meta = Frame(source_id="cam_main", timestamp=t6, width=640, height=480)
    q_tracks = [
        TrackedDetection(track_id="q_person_1", bbox=(100, 350, 25, 50), confidence=0.88),
        TrackedDetection(track_id="q_person_2", bbox=(130, 350, 25, 50), confidence=0.89),
        TrackedDetection(track_id="q_person_3", bbox=(160, 350, 25, 50), confidence=0.91),
        TrackedDetection(track_id="q_person_4", bbox=(190, 350, 25, 50), confidence=0.92),
    ]
    q_events = queue_monitor.update(f6_meta, q_tracks, [checkout_zone])
    assert len(q_events) == 1
    assert q_events[0].queue_length == 4
    e2e_repo.save_queue_event(q_events[0])

    q_alert = alert_engine.process_queue_event(q_events[0])
    assert q_alert is not None
    assert q_alert.alert_type == "queue_congestion"
    e2e_repo.upsert_alert(q_alert)

    # -------------------------------------------------------------------------
    # Frame 7 (t=45s): Empty shelf observed -> Low Stock Alert (Critical)
    # -------------------------------------------------------------------------
    t7 = base_time + timedelta(seconds=45)
    f7_meta = Frame(source_id="cam_main", timestamp=t7, width=640, height=480)
    canvas = make_synthetic_frame()
    shelf_empty_patch = make_shelf_texture("empty", width=250, height=180)
    canvas[280 : 280 + 180, 300 : 300 + 250] = shelf_empty_patch

    stock_events = check_shelves(
        frame=f7_meta,
        pixels=canvas,
        classifier=shelf_classifier,
        shelf_zones=[shelf_zone],
        tracked_detections=[],
        smoother=shelf_smoother,
    )
    assert len(stock_events) == 1
    assert stock_events[0].status == "empty"
    e2e_repo.save_stock_event(stock_events[0])

    stock_alert = alert_engine.process_stock_event(stock_events[0])
    assert stock_alert is not None
    assert stock_alert.alert_type == "low_stock"
    assert stock_alert.severity == "critical"
    e2e_repo.upsert_alert(stock_alert)

    # -------------------------------------------------------------------------
    # Verify API Responses Match Real Pipeline Execution Ground Truth
    # -------------------------------------------------------------------------
    resp_ff = e2e_client.get("/kpi/footfall")
    assert resp_ff.status_code == 200
    ff_data = resp_ff.json()
    assert ff_data["total_enters"] == 1
    assert ff_data["total_exits"] == 1
    assert ff_data["net_occupancy"] == 0

    resp_q = e2e_client.get("/kpi/queue")
    assert resp_q.status_code == 200
    q_data = resp_q.json()
    assert len(q_data) == 1
    assert q_data[0]["counter_id"] == "zone_checkout_1"
    assert q_data[0]["queue_length"] == 4

    resp_stock = e2e_client.get("/kpi/stock")
    assert resp_stock.status_code == 200
    stock_data = resp_stock.json()
    assert len(stock_data) == 1
    assert stock_data[0]["shelf_id"] == "zone_shelf_beverages"
    assert stock_data[0]["status"] == "empty"

    resp_alerts_open = e2e_client.get("/alerts?status=open")
    assert resp_alerts_open.status_code == 200
    alerts_open = resp_alerts_open.json()
    assert len(alerts_open) == 2
    alert_types = {a["alert_type"] for a in alerts_open}
    assert "queue_congestion" in alert_types
    assert "low_stock" in alert_types

    resp_hm = e2e_client.get("/heatmap")
    assert resp_hm.status_code == 200
    hm_data = resp_hm.json()
    assert "grid" in hm_data
    assert len(hm_data["grid"]) > 0

    # -------------------------------------------------------------------------
    # Stage 8: Alert Resolution Cycle
    # -------------------------------------------------------------------------
    t8 = base_time + timedelta(seconds=60)
    f8_meta = Frame(source_id="cam_main", timestamp=t8, width=640, height=480)
    q_cleared_tracks = [
        TrackedDetection(track_id="q_person_1", bbox=(100, 350, 25, 50), confidence=0.88)
    ]
    q_cleared_events = queue_monitor.update(f8_meta, q_cleared_tracks, [checkout_zone])
    e2e_repo.save_queue_event(q_cleared_events[0])

    # Shelf restocked (process 2 frames so smoother reaches 'ok')
    stocked_canvas = make_synthetic_frame()
    stocked_canvas[280 : 280 + 180, 300 : 300 + 250] = make_shelf_texture("ok", 250, 180)
    check_shelves(
        frame=f8_meta,
        pixels=stocked_canvas,
        classifier=shelf_classifier,
        shelf_zones=[shelf_zone],
        tracked_detections=[],
        smoother=shelf_smoother,
    )
    t9 = base_time + timedelta(seconds=65)
    f9_meta = Frame(source_id="cam_main", timestamp=t9, width=640, height=480)
    stocked_events = check_shelves(
        frame=f9_meta,
        pixels=stocked_canvas,
        classifier=shelf_classifier,
        shelf_zones=[shelf_zone],
        tracked_detections=[],
        smoother=shelf_smoother,
    )
    assert stocked_events[0].status == "ok"
    e2e_repo.save_stock_event(stocked_events[0])

    resolved = alert_engine.check_resolutions(
        latest_stock_events={stocked_events[0].shelf_id: stocked_events[0]},
        latest_queue_events={q_cleared_events[0].counter_id: q_cleared_events[0]},
    )
    assert len(resolved) == 2
    for r in resolved:
        assert r.resolved_at is not None
        e2e_repo.upsert_alert(r)

    # -------------------------------------------------------------------------
    # Verify Open vs Resolved Alerts via API
    # -------------------------------------------------------------------------
    resp_alerts_none = e2e_client.get("/alerts?status=open")
    assert resp_alerts_none.status_code == 200
    assert len(resp_alerts_none.json()) == 0

    resp_alerts_resolved = e2e_client.get("/alerts?status=resolved")
    assert resp_alerts_resolved.status_code == 200
    resolved_data = resp_alerts_resolved.json()
    assert len(resolved_data) == 2
    for r in resolved_data:
        assert r["resolved_at"] is not None


@pytest.mark.e2e
def test_pipeline_time_window_filtering(
    e2e_repo: EventRepository,
    e2e_client: TestClient,
) -> None:
    """Verify API correctly aggregates time buckets and respects the 'since' filter."""
    t0 = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)

    # Enter at 08:00
    e2e_repo.save_detection_event(
        DetectionEvent(
            event_id="ff_evt_1",
            track_id="trk_1",
            timestamp=t0,
            bbox=(100, 100, 30, 60),
            zone_id="zone_entrance",
            event_type="enter",
        )
    )

    # Enter at 10:00
    t1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC)
    e2e_repo.save_detection_event(
        DetectionEvent(
            event_id="ff_evt_2",
            track_id="trk_2",
            timestamp=t1,
            bbox=(100, 100, 30, 60),
            zone_id="zone_entrance",
            event_type="enter",
        )
    )

    # Query with group_by=hour
    resp_hourly = e2e_client.get("/kpi/footfall?group_by=hour")
    assert resp_hourly.status_code == 200
    data_hourly = resp_hourly.json()
    assert data_hourly["total_enters"] == 2
    assert len(data_hourly["buckets"]) >= 1

    # Query with since filtering out the 08:00 event
    resp_filtered = e2e_client.get("/kpi/footfall?since=2026-09-01T09:00:00Z")
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    assert data_filtered["total_enters"] == 1
