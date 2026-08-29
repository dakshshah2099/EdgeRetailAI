# Slice 1 — Camera Source Abstraction

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice makes the
camera input swappable: phone-over-RTSP today, CSI/USB Jetson camera later,
with zero pipeline changes elsewhere. It produces `Frame` metadata (from
Slice 0's `schemas.py`) plus the raw pixel array, but never persists either.

## FR satisfied

FR12 (run all CV locally on edge hardware — camera input layer is the first
stage of that pipeline) and the POC's core "drop-in replacement" pitch
(phone camera substituting CCTV, same interface a Jetson deployment uses).

## Depends on

Slice 0: `Frame` model from `schemas.py`, nothing else.

## Files owned by this slice

```
camera/__init__.py
camera/base.py            # CameraSource protocol/ABC
camera/rtsp_source.py      # phone (IP Webcam) implementation
camera/usb_source.py        # laptop webcam fallback implementation
tests/unit/test_camera.py
tests/fixtures/sample_video.mp4   # short test clip, or synthetic frame generator if no video available
```

Do not touch `schemas.py`, `config.yaml` schema, or any file outside this
list. If `Frame` needs a field this slice doesn't have, stop and flag it —
don't edit Slice 0's contract unilaterally.

## Interface in

- Camera config from `AppConfig.camera` (Slice 0's `CameraConfig.source` —
  currently just a URL/device string; if this slice needs more fields
  (e.g. target_fps, resolution), propose the addition and flag it rather
  than silently extending `CameraConfig`).

## Interface out

```python
from abc import ABC, abstractmethod
from schemas import Frame
import numpy.typing as npt
import numpy as np

class CameraSource(ABC):
    """Abstract camera input. Any implementation must yield (Frame, ndarray)
    pairs. The ndarray is the raw BGR pixel buffer — it is NEVER wrapped in
    or attached to a Pydantic model, and must never be passed to anything
    in storage/ (Slice 7) or logged."""

    @abstractmethod
    def get_frame(self) -> tuple[Frame, npt.NDArray[np.uint8]] | None:
        """Return the next available frame, or None if the stream is
        temporarily unavailable (caller decides retry policy)."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release the underlying capture resource."""
        ...
```

Implementations:
- `RTSPSource(CameraSource)` — wraps `cv2.VideoCapture(rtsp_url)`. Must
  handle disconnects: on a failed read, attempt reconnect with exponential
  backoff (start 1s, cap at 10s, no infinite tight loop). Must not crash the
  process on a dropped stream — return `None` from `get_frame()` and log a
  warning instead.
- `USBSource(CameraSource)` — wraps `cv2.VideoCapture(device_index)`. Same
  interface, simpler (no network reconnect logic needed, but still handle a
  device read failure gracefully rather than raising).

Both populate `Frame.source_id`, `Frame.timestamp` (capture time, not
frame's internal PTS unless trivially available), `Frame.width`, `Frame.height`
from the actual captured frame dimensions.

## Acceptance tests

- [ ] Given a valid local test video file (`tests/fixtures/sample_video.mp4`)
      opened via `USBSource`-style path or a `cv2.VideoCapture(filepath)`
      test double, `get_frame()` yields frames until exhaustion, and each
      returned `Frame` has correct width/height matching the source video.
- [ ] `RTSPSource` against an unreachable URL: `get_frame()` returns `None`
      rather than raising or hanging; a reconnect attempt is made (assert via
      mock/spy on `cv2.VideoCapture` call count, not a real network wait).
- [ ] Reconnect backoff is capped — test that after N failed attempts, the
      wait time does not exceed the configured max (mock `time.sleep`, assert
      on call arguments rather than actually sleeping in tests).
- [ ] `close()` releases the underlying `VideoCapture` (assert `.release()`
      called on the mock).
- [ ] No test, fixture, or implementation writes a captured frame's raw
      pixel data to disk, log, or any persisted model.

## Non-goals for this slice

- No detection/tracking logic — this slice only gets frames out, doesn't
  interpret them.
- No frame queue/buffering/threading model yet — synchronous `get_frame()`
  pull is sufficient for the POC; if Slice 2 needs async/threaded capture,
  that's handled there or flagged as a follow-up, not built speculatively here.
- No `config.yaml` schema changes without flagging first.

## Agent prompt seed

> Implement the `CameraSource` abstraction and its two implementations
> exactly per `slices/SLICE_1_camera_source.md`. Use the existing `Frame`
> model from `schemas.py` as-is — do not modify `schemas.py`. Write the
> acceptance tests first (mock `cv2.VideoCapture` and `time.sleep` where
> specified so tests run fast and deterministically, no real network calls
> or real sleeps). If you need a `CameraConfig` field that doesn't exist
> yet, stop and tell me instead of editing Slice 0's schema.