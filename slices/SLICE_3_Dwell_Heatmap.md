# Slice 3 — Dwell Time & Zone Heatmap

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice consumes
Slice 2's `"in_zone"` `DetectionEvent`s and track IDs to compute how long
each anonymous shopper lingers in a zone, and accumulates that into a
heatmap of movement/dwell intensity.

## FR satisfied

FR3 (dwell time near products/displays), FR4 (heatmap of movement patterns —
raw accumulation here; rendering happens in Slice 8).

## Depends on

- Slice 0: `ZoneConfig`, `DwellEvent`, `Frame` from `schemas.py`.
- Slice 2: `DetectionEvent` stream (specifically `event_type == "in_zone"`
  entries) and `FootfallTracker`'s per-track zone membership — this slice
  does NOT re-implement zone-membership detection; it consumes Slice 2's
  events as input, or is invoked alongside `FootfallTracker.update()` in
  the same pipeline pass (agent's choice — state which approach was taken).

## Files owned by this slice

```
detection/dwell.py
detection/heatmap.py
tests/unit/test_dwell.py
tests/unit/test_heatmap.py
```

Do not touch `schemas.py`, `detection/tracker.py`, `detection/footfall.py`,
or `camera/`. If dwell computation needs something `FootfallTracker` doesn't
currently expose (e.g. a callback on zone-entry/zone-exit rather than
per-frame `in_zone` events), propose the smallest possible addition to
`footfall.py` and flag it — don't restructure Slice 2's internals.

## Interface in

Either of these two shapes is acceptable — pick one, document which:
- (a) A stream of `DetectionEvent`s (as Slice 2 emits them) fed to
  `DwellTracker.update(events: list[DetectionEvent]) -> list[DwellEvent]`.
- (b) Direct integration: `DwellTracker.update(frame, tracked_detections, zones)`
  called alongside `FootfallTracker.update()` in the same per-frame pass,
  sharing zone-membership logic rather than re-deriving it from events.

State clearly in your report which shape was implemented and why.

## Interface out

```python
class DwellTracker:
    """Tracks how long each anonymous track stays inside product_display
    zones and emits a DwellEvent when the track leaves (or on session end
    for tracks still present)."""

    def update(self, ...) -> list[DwellEvent]:
        ...

    def reset(self) -> None:
        ...
```

A `DwellEvent` (from `schemas.py`) is emitted once per zone visit, on exit
— not continuously while the track remains inside. `duration_sec` = time
between first observed `in_zone` frame and the frame where the track is no
longer inside that zone (or track disappears / session ends).

```python
class HeatmapAccumulator:
    """Accumulates positional dwell/traffic intensity into a 2D grid over
    the camera's frame dimensions."""

    def __init__(self, width: int, height: int, cell_size: int = 20) -> None: ...

    def add_point(self, x: float, y: float, weight: float = 1.0) -> None:
        """Increment the grid cell containing (x, y) by weight. Called once
        per tracked detection per frame using the same anchor point
        footfall.py uses (bottom-center of bbox)."""
        ...

    def get_grid(self) -> npt.NDArray[np.float32]:
        """Return the current accumulated grid, shape (height//cell_size,
        width//cell_size)."""
        ...

    def reset(self) -> None: ...
```

The heatmap grid itself is an in-memory numeric array — not a `schemas.py`
model, not persisted as an image. If Slice 7/8 need to store or serve
heatmap data, they'll serialize the grid as numeric values (e.g. a 2D array
of floats), never as rendered pixels — that's a later slice's concern, not
this one's, but keep the output type friendly to that (plain ndarray, not
tied to a rendering library).

## Acceptance tests

- [ ] A synthetic track that enters a `product_display` zone and stays for
      N frames (at a known fps) produces one `DwellEvent` with
      `duration_sec` ≈ N/fps within tolerance.
- [ ] A track that enters, leaves, and re-enters the same zone produces two
      separate `DwellEvent`s, not one merged event.
- [ ] A track that is still inside a zone when the session/stream ends is
      still accounted for (either emits a final `DwellEvent` on explicit
      `flush()`/session-end call, or documented as a known limitation —
      agent's choice, but must be handled deliberately, not silently dropped
      with no test coverage either way).
- [ ] `HeatmapAccumulator.add_point()` correctly increments the containing
      cell; a point exactly on a cell boundary is handled consistently
      (test both a mid-cell and boundary case).
- [ ] Accumulating many points in the same zone produces a grid whose peak
      cell corresponds to that zone's approximate location.
- [ ] `reset()` on both classes clears accumulated state (mirror the
      pattern Slice 2's `FootfallTracker.reset()` established).
- [ ] No `DwellEvent`, grid, or intermediate state ever carries a pixel
      array, image crop, or embedding.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No heatmap rendering/visualization (image output) — that's dashboard
  territory (Slice 8). This slice only accumulates numeric intensity data.
- No cross-session/persistent heatmap (e.g. "heatmap over the last 7 days")
  — that requires storage (Slice 7) aggregating multiple sessions; this
  slice's `HeatmapAccumulator` is in-memory, single-session only.
- No shelf/queue logic (Slices 4, 5).

## Agent prompt seed

> Implement `DwellTracker` and `HeatmapAccumulator` exactly per
> `slices/SLICE_3_dwell_heatmap.md`. Reuse Slice 2's zone-membership
> detection rather than reimplementing it — either consume its
> `DetectionEvent` stream or integrate directly alongside
> `FootfallTracker.update()` in the same per-frame pass; state which
> approach you took and why. Handle the "track still inside zone when
> session ends" case deliberately (flush call or documented limitation with
> a test either way) — don't let it silently disappear. Write acceptance
> tests first. Do not modify schemas.py, tracker.py, or footfall.py — if
> footfall.py needs a small addition to support this cleanly, propose it
> and flag it rather than restructuring it yourself.