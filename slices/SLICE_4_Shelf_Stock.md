# Slice 4 — Shelf Stock Detection

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice looks at
shelf-facing camera frames and classifies shelf regions as empty, low, or
ok — no product recognition, no SKU-level planogram compliance (that's an
explicit non-goal for the POC per CONTEXT.md).

## FR satisfied

FR5 (detect low-stock / out-of-stock). FR6 (planogram compliance) is
explicitly NOT this slice — POC non-goal.

## Depends on

- Slice 0: `ZoneConfig` (zones with `zone_type == "shelf"`), `StockEvent`,
  `Frame` from `schemas.py`.
- Slice 1: `CameraSource.get_frame()` output — same camera abstraction, this
  slice does not open its own capture device.
- Slice 2's `InferenceBackend` pattern (not its person-detection code) —
  reuse the same swap-point philosophy: whatever shelf classification
  approach is used should stay swappable behind a thin interface, not
  hardcoded to one library.

## Files owned by this slice

```
inventory/__init__.py
inventory/shelf_classifier.py
inventory/roi.py                  # crops a Frame's pixels to a shelf ZoneConfig's polygon bounds
tests/unit/test_shelf_classifier.py
tests/unit/test_roi.py
tests/fixtures/shelf_empty.jpg
tests/fixtures/shelf_stocked.jpg
tests/fixtures/shelf_low.jpg      # optional third state if distinguishable; if not, document why binary-only is acceptable for POC
```

Do not touch `schemas.py`, `camera/`, `detection/`. If shelf detection needs
a `ZoneConfig` field beyond the existing `polygon`/`zone_type`/`label`
(e.g. an expected-item-count baseline), propose it and flag rather than add
unilaterally.

## Interface in

`(Frame, npt.NDArray[np.uint8])` from a `CameraSource`, plus the subset of
`AppConfig.zones` where `zone_type == "shelf"`.

## Interface out

```python
def crop_to_zone(pixels: npt.NDArray[np.uint8], zone: ZoneConfig) -> npt.NDArray[np.uint8]:
    """Crop the frame to the bounding box of the zone's polygon. Pure
    function, no side effects, no persistence of the crop."""
    ...

class ShelfClassifier(ABC):
    """Swap point, same philosophy as InferenceBackend in Slice 2 — the
    initial implementation can be simple (background subtraction / pixel
    density heuristic), a learned classifier can replace it later without
    touching callers."""

    @abstractmethod
    def classify(self, shelf_crop: npt.NDArray[np.uint8]) -> tuple[Literal["empty", "low", "ok"], float]:
        """Return (status, confidence)."""
        ...

def check_shelves(
    frame: Frame,
    pixels: npt.NDArray[np.uint8],
    classifier: ShelfClassifier,
    shelf_zones: list[ZoneConfig],
    threshold: float,
) -> list[StockEvent]:
    """Top-level entry point: crop each shelf zone, classify, emit
    StockEvents. threshold is AppConfig.low_stock_confidence_threshold
    (Slice 0) — how it's used (min confidence to report vs. some other
    role) is this slice's call, but state the interpretation clearly."""
    ...
```

For the initial `ShelfClassifier` implementation, a simple heuristic
(edge density, background-subtraction against a reference "stocked" image,
or color histogram comparison) is acceptable and preferred over standing up
a trained model for the POC — state clearly which heuristic was used and
its limitations. A learned classifier is a reasonable future slice, not
required now.

## Acceptance tests

- [ ] `crop_to_zone()` on a known polygon returns a crop of the expected
      dimensions and content region (test against a synthetic frame with a
      marked region).
- [ ] Classifier correctly labels `shelf_empty.jpg` as `"empty"` (or `"low"`
      at minimum — document the exact threshold behavior).
- [ ] Classifier correctly labels `shelf_stocked.jpg` as `"ok"`.
- [ ] `check_shelves()` produces one `StockEvent` per shelf zone per call,
      with `shelf_id` matching the zone's `zone_id`.
- [ ] Confidence values are within `[0.0, 1.0]` (schema already enforces
      this — test that the classifier's raw output stays in range before
      hitting the schema boundary too).
- [ ] No `StockEvent` or intermediate state carries the cropped image itself
      — only the classification result and metadata.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No SKU-level product recognition or planogram compliance (explicit POC
  non-goal per CONTEXT.md).
- No trained/learned classifier required — heuristic is fine, document it.
- No alerting logic (Slice 6 consumes `StockEvent`s to decide when to alert).
- No persistence (Slice 7).

## Agent prompt seed

> Implement `crop_to_zone()` and `ShelfClassifier`/`check_shelves()` exactly
> per `slices/SLICE_4_shelf_stock.md`. Use a simple heuristic classifier
> (state which — edge density, background subtraction, histogram
> comparison, etc.) rather than training a model; this is a POC-appropriate
> shortcut, not a shortcut to hide. Use real or synthetic shelf images for
> the fixtures — if synthetic, say so explicitly, same as Slice 2's gap
> flag. Write acceptance tests first. Do not modify schemas.py, camera/, or
> detection/ — if you need a new ZoneConfig field, stop and ask.