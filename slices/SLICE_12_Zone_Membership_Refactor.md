# Slice 12 — Zone Membership Refactor (Cleanup)

Read `AGENTS.md` and `CONTEXT.md` before starting. This is a pure
refactor slice: extract the point-in-polygon + bottom-center-anchor logic
that's currently duplicated across `detection/footfall.py` and
`queue_intel/queue_monitor.py` into one shared module, with zero behavior
change. No new functionality, no new FR coverage — this slice exists
purely to remove the duplication flagged during Slices 5 and 6's review.

## IMPORTANT: exception to the normal cross-slice boundary rule

Every prior slice was told not to touch other slices' files. This slice is
the deliberate exception — its entire purpose is to edit `footfall.py` and
`queue_monitor.py` to use a new shared helper instead of their own
duplicated logic. This is intentional and pre-approved; do not flag it as
a boundary violation, but DO keep the edits to those two files minimal and
mechanical (swap duplicated logic for calls to the new shared module —
don't restructure anything else while you're in there).

## FR satisfied

None — this is a code-quality/maintainability slice, not a functional
requirement. The functional behavior it touches (footfall zone-crossing,
queue zone-membership) must remain byte-for-byte identical in output.

## Depends on

- Slice 2's `detection/footfall.py` (specifically its point-in-polygon +
  anchor-point computation).
- Slice 5's `queue_intel/queue_monitor.py` (same logic, duplicated).

## Files owned by this slice

```
detection/zone_membership.py      # new shared module
tests/unit/test_zone_membership.py
```

## Files modified by this slice (the explicit exception above)

```
detection/footfall.py        # replace inline point-in-polygon/anchor logic
                                # with calls to detection/zone_membership.py
queue_intel/queue_monitor.py    # same
```

Do not touch anything else — not `schemas.py`, not `dwell.py`, not
`tracker.py`, not any other slice's files beyond these two named ones.

## Interface out

```python
def anchor_point(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
    """Bottom-center anchor point of a bbox (x, y, w, h). This is the exact
    convention already used identically in footfall.py and queue_monitor.py
    — extract verbatim, do not change the formula."""
    ...

def is_inside_zone(point: tuple[float, float], zone: ZoneConfig) -> bool:
    """cv2.pointPolygonTest-based check, extracted verbatim from the
    existing duplicated implementations. Same behavior, same edge-case
    handling (boundary points, degenerate polygons) as before."""
    ...

def zone_polygon_cache(zones: list[ZoneConfig]) -> dict[str, npt.NDArray[np.int32]]:
    """Pre-converts zone polygons to cv2-compatible numpy arrays, keyed by
    zone_id — extracted from footfall.py's existing per-call conversion
    (which was recomputing this on every update() call; if queue_monitor.py
    did NOT already cache this the same way, note the discrepancy — this
    refactor should not silently introduce a behavior change by caching
    somewhere it wasn't cached before, or failing to cache somewhere it
    was. State clearly what each caller's caching behavior was before and
    after)."""
    ...
```

## Acceptance tests

- [ ] `anchor_point()` produces identical output to the pre-refactor
      inline formula for a range of test bboxes (this is really testing
      that the extraction was verbatim, not testing new logic).
- [ ] `is_inside_zone()` produces identical results to the pre-refactor
      inline `cv2.pointPolygonTest` calls for the same set of test cases
      used in Slice 2's and Slice 5's original acceptance tests (reuse
      those test fixtures/cases directly if possible, don't invent new ones
      — the point is regression-proofing, not new coverage).
- [ ] **All existing tests in `test_footfall.py` and `test_queue_monitor.py`
      still pass unchanged after the refactor** — this is the primary
      acceptance criterion for this entire slice. If any existing test's
      assertions had to change to make it pass, that indicates a behavior
      change slipped in, which is not allowed; investigate and fix the
      refactor, not the test.
- [ ] Full test suite (all slices) still passes — run the complete suite,
      not just the two modified files' tests, to catch any indirect
      regression.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No new functionality, no new zone types, no new edge-case handling
  beyond what already existed — this is deduplication only.
- No changes to `dwell.py` — it doesn't do its own point-in-polygon
  computation (it consumes `footfall.py`'s emitted events), so it has
  nothing to refactor here. Confirm this is still true and don't touch it
  if so.
- No performance optimization beyond whatever caching consolidation
  naturally falls out of having one shared implementation (see the
  `zone_polygon_cache` caching-discrepancy note above) — if a genuine
  perf improvement is found, mention it, but don't chase it as a goal.

## Agent prompt seed

> Implement `detection/zone_membership.py` exactly per
> `slices/SLICE_12_zone_membership_refactor.md`, extracting the
> point-in-polygon and anchor-point logic verbatim from `footfall.py` and
> `queue_monitor.py` — no behavior changes, no new logic. Then update
> those two files to use the shared module (this is the one slice
> explicitly allowed to touch other slices' files — don't flag it as a
> violation). Before touching anything, check whether `footfall.py` and
> `queue_monitor.py` cached zone polygon conversions differently from each
> other, and preserve/report that discrepancy explicitly rather than
> silently normalizing it. The primary success criterion is that every
> existing test in `test_footfall.py`, `test_queue_monitor.py`, and the
> full suite continues to pass with unchanged assertions — if you find
> yourself needing to change an existing test's expected value to make it
> pass, stop and investigate before proceeding, since that means the
> refactor introduced a behavior change.