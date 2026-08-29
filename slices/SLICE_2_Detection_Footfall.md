# Slice 2 — Person Detection & Footfall Count

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice turns raw
frames (Slice 1's `CameraSource` output) into anonymous person tracks and
entry/exit counts. It also introduces the `InferenceBackend` abstraction —
the second swappable seam of the "Jetson drop-in" pitch (ONNX Runtime today,
TensorRT later, same model file, one file to swap).

## FR satisfied

FR1 (count customers entering/exiting), FR2 (footfall trends — this slice
produces the raw events; aggregation into trends happens in Slice 8).

## Depends on

- Slice 0: `Frame`, `DetectionEvent`, `ZoneConfig`, `AppConfig` from `schemas.py`.
- Slice 1: `CameraSource.get_frame()` — this slice consumes `(Frame, ndarray)`
  pairs from it, does not reimplement camera capture.

## Files owned by this slice

```
detection/__init__.py
detection/inference_backend.py   # InferenceBackend interface + ONNXBackend impl
detection/detector.py             # YOLOv8n wrapper producing raw bboxes
detection/tracker.py               # ByteTrack (or equivalent) wrapper, assigns track_id
detection/footfall.py               # line-crossing / zone-entry logic -> DetectionEvent
models/yolov8n.onnx                  # pretrained, exported — do not train from scratch
tests/unit/test_detector.py
tests/unit/test_tracker.py
tests/unit/test_footfall.py
tests/fixtures/footfall_test_video.mp4   # short clip with known in/out count, OR
tests/fixtures/synthetic_tracks.json       # if a real labeled video isn't available yet
```

Do not touch `schemas.py`, `camera/`, or `config.yaml`'s existing fields.
If footfall logic needs a new `ZoneConfig` field (e.g. a directional
crossing-line definition distinct from a polygon), propose it and flag —
don't add it unilaterally.

## Interface in

- `(Frame, npt.NDArray[np.uint8])` from a `CameraSource` (Slice 1).
- `list[ZoneConfig]` from `AppConfig.zones` (Slice 0), specifically zones
  with `zone_type == "entry_exit"`.

## Interface out

```python
class InferenceBackend(ABC):
    """Swap point: ONNXBackend today, TensorRTBackend later — same model
    file, same call signature. This is the seam the Jetson-substitution
    pitch depends on; keep it thin and backend-agnostic."""

    @abstractmethod
    def infer(self, frame: npt.NDArray[np.uint8]) -> list[RawDetection]:
        """Run the detection model on one frame, return raw (unfiltered,
        untracked) detections."""
        ...

class ONNXBackend(InferenceBackend):
    def __init__(self, model_path: str, conf_threshold: float = 0.4) -> None: ...
```

`RawDetection` — an internal (non-persisted, not in `schemas.py`) dataclass
or Pydantic model local to `detection/`: `class_id, confidence, bbox(x,y,w,h)`.
Filter to `class_id == person` (COCO class 0) at the detector level — this
slice only cares about people, not general object detection.

`tracker.py`: wraps raw per-frame detections into stable `track_id`s across
frames (ByteTrack or a simpler IoU-based tracker is acceptable for POC —
state which you used). Track IDs are ephemeral strings/ints, reset on
process restart, never linked to any stored identity.

`footfall.py`: given a tracked detection's position relative to an
`entry_exit` zone's polygon (or a defined crossing line) across consecutive
frames, emit a `DetectionEvent` (from `schemas.py`) with `event_type` of
`"enter"` or `"exit"` when a track crosses the boundary. Emit `"in_zone"`
for tracks inside a `product_display`-type zone (sets up Slice 3's dwell
logic, but does NOT compute dwell duration here — that's Slice 3's job).

Top-level entry point for this slice:

```python
def process_frame(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    backend: InferenceBackend,
    tracker: Tracker,
    zones: list[ZoneConfig],
) -> list[DetectionEvent]:
    ...
```

## Acceptance tests

- [ ] `ONNXBackend.infer()` on a fixture frame containing a known number of
      people returns that many person-class detections (within reasonable
      confidence threshold) — use a real test image, assert count.
- [ ] Detector filters out non-person classes (feed a frame with e.g. a
      detected "chair" or similar, assert it's excluded from results).
- [ ] Tracker assigns a consistent `track_id` to the same person across a
      short sequence of frames (feed synthetic/real consecutive detections
      with overlapping bboxes, assert same ID persists).
- [ ] Tracker assigns different `track_id`s to two simultaneously-present,
      spatially separate detections.
- [ ] Footfall logic: given a track's positions crossing an `entry_exit`
      zone boundary inward, emits exactly one `"enter"` `DetectionEvent`
      (not one per frame — debounce/edge-trigger, not level-trigger).
- [ ] Same for `"exit"`.
- [ ] End-to-end on `footfall_test_video.mp4` (or synthetic track sequence
      if no labeled video yet): known in-count and out-count from the test
      fixture match the events produced within a small tolerance. If using
      a synthetic fixture instead of real video, say so explicitly and note
      it as a known gap to close before the live demo.
- [ ] No `DetectionEvent`, `RawDetection`, or any intermediate model in this
      slice ever carries a pixel array, image crop, or embedding field.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No dwell-time computation or heatmap (Slice 3).
- No shelf/queue detection (Slices 4, 5).
- No TensorRT backend implementation — only the `InferenceBackend`
  interface needs to exist such that one could be added later without
  touching `detector.py`/`footfall.py`.
- No face recognition, re-identification across camera restarts, or any
  form of persistent identity — tracks are session-local and anonymous by
  design; do not add anything that could de-anonymize a track.
- No API/dashboard wiring (Slice 8) — this slice's output is a list of
  `DetectionEvent`s, consumed by later slices, not exposed yet.

## Agent prompt seed

> Implement `InferenceBackend`/`ONNXBackend`, the YOLOv8n person detector,
> a tracker, and footfall zone-crossing logic exactly per
> `slices/SLICE_2_detection_footfall.md`. Use a pretrained YOLOv8n ONNX
> export (download or export one — do not train from scratch; state where
> the model file came from). Keep `InferenceBackend` genuinely thin so a
> `TensorRTBackend` could be added later by only adding a new file, never
> touching `detector.py` or callers. Write acceptance tests first. If no
> labeled test video with a known in/out count is available, build a
> synthetic fixture and say so explicitly rather than silently weakening
> the test. Do not modify schemas.py, camera/, or config.yaml's existing
> structure — if you need a new ZoneConfig field, stop and ask.