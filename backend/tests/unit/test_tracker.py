from vision.inference_backend import RawDetection
from vision.tracker import TrackedDetection, Tracker


def test_tracked_detection_has_no_pii_or_pixels() -> None:
    td = TrackedDetection(track_id="1", bbox=(10, 20, 30, 40), confidence=0.85, class_id=0)
    assert hasattr(td, "track_id")
    assert hasattr(td, "bbox")
    assert hasattr(td, "confidence")
    assert not hasattr(td, "pixels")
    assert not hasattr(td, "image")
    assert not hasattr(td, "crop")
    assert not hasattr(td, "embedding")


def test_tracker_assigns_consistent_id_across_frames() -> None:
    tracker = Tracker(iou_threshold=0.3, high_conf_threshold=0.5)

    # Frame 1: Person at (100, 100, 50, 100)
    frame1_dets = [RawDetection(class_id=0, confidence=0.9, bbox=(100, 100, 50, 100))]
    res1 = tracker.update(frame1_dets)
    assert len(res1) == 1
    track_id = res1[0].track_id

    # Frame 2: Person moved slightly to (105, 102, 50, 100)
    frame2_dets = [RawDetection(class_id=0, confidence=0.88, bbox=(105, 102, 50, 100))]
    res2 = tracker.update(frame2_dets)
    assert len(res2) == 1
    assert res2[0].track_id == track_id, "Track ID must remain stable across consecutive frames"

    # Frame 3: Person moved slightly to (110, 105, 50, 100)
    frame3_dets = [RawDetection(class_id=0, confidence=0.92, bbox=(110, 105, 50, 100))]
    res3 = tracker.update(frame3_dets)
    assert len(res3) == 1
    assert res3[0].track_id == track_id


def test_tracker_assigns_different_ids_to_spatially_separate_detections() -> None:
    tracker = Tracker(iou_threshold=0.3, high_conf_threshold=0.5)

    # Two people far apart in the same frame
    dets = [
        RawDetection(class_id=0, confidence=0.9, bbox=(50, 50, 40, 80)),
        RawDetection(class_id=0, confidence=0.85, bbox=(500, 500, 40, 80)),
    ]
    res = tracker.update(dets)

    assert len(res) == 2
    assert res[0].track_id != res[1].track_id, "Different detections must have distinct track IDs"


def test_tracker_bytetrack_low_confidence_association() -> None:
    tracker = Tracker(
        iou_threshold=0.3,
        high_conf_threshold=0.6,
        low_conf_threshold=0.2,
    )

    # Frame 1: High confidence detection -> creates track
    f1 = [RawDetection(class_id=0, confidence=0.8, bbox=(100, 100, 50, 100))]
    res1 = tracker.update(f1)
    assert len(res1) == 1
    track_id = res1[0].track_id

    # Frame 2: Person occluded, confidence drops to 0.35 (below high_conf_threshold of 0.6)
    f2 = [RawDetection(class_id=0, confidence=0.35, bbox=(102, 101, 50, 100))]
    res2 = tracker.update(f2)
    assert len(res2) == 1
    assert res2[0].track_id == track_id, "ByteTrack should associate low-confidence detection"


def test_tracker_track_expiration_after_max_age() -> None:
    tracker = Tracker(max_age=3, high_conf_threshold=0.5)

    # Frame 1: detection present
    f1 = [RawDetection(class_id=0, confidence=0.9, bbox=(100, 100, 50, 100))]
    res1 = tracker.update(f1)
    assert len(res1) == 1
    first_track_id = res1[0].track_id

    # 4 empty frames (exceeds max_age=3)
    for _ in range(4):
        tracker.update([])

    # Next frame: new detection at same position -> should be treated as a new track ID
    f_new = [RawDetection(class_id=0, confidence=0.9, bbox=(100, 100, 50, 100))]
    res_new = tracker.update(f_new)
    assert len(res_new) == 1
    assert res_new[0].track_id != first_track_id, "Expired track should not retain old ID"


def test_tracker_reset() -> None:
    tracker = Tracker()
    tracker.update([RawDetection(class_id=0, confidence=0.9, bbox=(10, 10, 20, 20))])
    assert len(tracker.tracks) > 0

    tracker.reset()
    assert len(tracker.tracks) == 0
    assert tracker._next_id == 1
