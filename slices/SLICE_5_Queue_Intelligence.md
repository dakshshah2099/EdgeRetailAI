# Slice 5 — Queue Intelligence

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice monitors
checkout-counter zones for queue length and estimates wait time, feeding
Slice 6's alerting engine for congestion warnings.

## FR satisfied

FR8 (monitor checkout queue length), FR9 (predict congestion — this slice
produces the raw signal; threshold-based prediction logic lives partly here,
partly in Slice 6's alerting), FR11 (measure avg wait/service time).

## Depends on

- Slice 0: `ZoneConfig` (zones with `zone_type == "checkout"`), `QueueEvent`,
  `Frame` from `schemas.py`.
- Slice 2: reuse `PersonDetector`/`InferenceBackend` and `Tracker` — queue
  length is just "how many tracked people are inside a checkout zone right
  now," not a new detection problem. Do not build a separate detector.

## Files owned by this slice

```
queue_intel/__init__.py
queue_intel/queue_monitor.py
tests/unit/test_queue_monitor.py
```

Do not touch `schemas.py`, `camera/`, `detection/`. This slice is thin by
design — it's mostly counting tracked detections inside `checkout` zones
and turning that into a `QueueEvent`, reusing Slice 2's zone/point-in-polygon
approach rather than reinventing it.

## Interface in

`list[TrackedDetection]` (from Slice 2's `Tracker.update()`) and the subset
of `AppConfig.zones` where `zone_type == "checkout"`, plus a `Frame` for
timestamp.

## Interface out

```python
class QueueMonitor:
    """Counts tracked people inside each checkout zone and estimates wait
    time from a rolling average of how long tracks remain in the zone."""

    def __init__(self, service_rate_estimate_sec: float = 90.0) -> None:
        """service_rate_estimate_sec: fallback average service time per
        person, used only until enough real dwell-in-queue samples exist
        to estimate it empirically. State clearly which mode is active."""
        ...

    def update(
        self,
        frame: Frame,
        tracked_detections: list[TrackedDetection],
        checkout_zones: list[ZoneConfig],
    ) -> list[QueueEvent]:
        """One QueueEvent per checkout zone per call — queue_length = count
        of tracks currently inside that zone's polygon."""
        ...

    def reset(self) -> None: ...
```

`avg_wait_est_sec` estimation approach is this slice's call — two
reasonable options, pick one and document it:
(a) simple: `queue_length * service_rate_estimate_sec` (naive product).
(b) better: track how long individual tracks actually spend inside the
zone before their track_id disappears (similar mechanism to Slice 3's
`DwellTracker`, but for checkout zones specifically), and use the running
average of completed service times instead of a fixed estimate. If you
have time, (b) is the stronger answer for the pitch — the naive product in
(a) is a fine POC fallback but is worth flagging as approximate rather than
measured.

## Acceptance tests

- [ ] `queue_length` in the emitted `QueueEvent` matches the count of
      tracked detections whose anchor point falls inside a `checkout` zone's
      polygon (test with a synthetic set of tracks, some inside, some
      outside).
- [ ] Zero people in a checkout zone still emits a `QueueEvent` with
      `queue_length == 0` (not silently skipped) — Slice 6's alerting needs
      a "queue cleared" signal, not just "queue exists" signal.
- [ ] `avg_wait_est_sec` is populated and non-negative; if using approach
      (b), test that it updates as tracks complete their zone traversal.
- [ ] Two separate checkout zones produce two independent `QueueEvent`s in
      the same `update()` call, not conflated into one.
- [ ] `reset()` clears any accumulated service-time history (if approach
      (b) was used).
- [ ] No pixel data, image crops, or embeddings in `QueueEvent` or any
      intermediate state.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No congestion-alert decision-making (threshold comparison, "recommend
  opening a counter") — that's Slice 6, which consumes this slice's
  `QueueEvent` stream.
- No new detection model — reuses Slice 2's person detector/tracker as-is.
- No persistence (Slice 7), no dashboard (Slice 8).

## Agent prompt seed

> Implement `QueueMonitor` exactly per `slices/SLICE_5_queue_intelligence.md`.
> Reuse Slice 2's `TrackedDetection` and point-in-polygon zone-membership
> approach (same style as `footfall.py`) rather than reinventing detection.
> Decide between the naive product estimate and the measured-average
> estimate for `avg_wait_est_sec` — state which you chose and why. Always
> emit a `QueueEvent` per checkout zone per call, including when
> `queue_length == 0`. Write acceptance tests first. Do not modify
> schemas.py, camera/, or detection/.