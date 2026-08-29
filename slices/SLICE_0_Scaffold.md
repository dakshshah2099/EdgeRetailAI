# Slice 0 — Contracts & Scaffold

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice has no ML/CV
logic — it exists purely to lock the typed contracts every later slice will
build against, and to set up the tooling that enforces standards automatically.

## FR satisfied

None directly (foundation slice). Enforces FR15 (no PII persistence)
structurally for every slice that follows.

## Depends on

Nothing. This is the first slice.

## Files owned by this slice

```
schemas.py
config.yaml
pyproject.toml          # ruff, mypy, pytest config
.pre-commit-config.yaml
requirements.txt (or poetry/pdm equivalent — agent's choice, state which)
tests/unit/test_schemas.py
tests/unit/test_config.py
README.md               # brief: how to install, run tests, run lint
```

Do not create files outside this list. Later slices will add their own
directories (`camera/`, `detection/`, etc.) — do not pre-create empty stubs
for them; that's scope creep into future slices.

## Interface out (this slice defines the contracts everything else uses)

Define these Pydantic v2 models in `schemas.py`. Field names/types below are
binding; do not rename without flagging. Add `model_config = ConfigDict(frozen=True)`
where a model represents an immutable event.

```python
class Frame(BaseModel):
    """A single camera frame. NOTE: this model must NEVER be persisted to
    disk/DB — it exists only in-memory for pipeline processing. Do not add
    this type as a field on any model in storage/ later."""
    source_id: str
    timestamp: datetime
    width: int
    height: int
    # actual pixel data intentionally NOT a typed field here — pipeline
    # code passes raw ndarray alongside this metadata, never serializes it.

class ZoneConfig(BaseModel):
    zone_id: str
    zone_type: Literal["entry_exit", "product_display", "shelf", "checkout"]
    polygon: list[tuple[int, int]]  # pixel coords, min 3 points
    label: str

class DetectionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    track_id: str          # anonymous, ephemeral, never linked to identity
    timestamp: datetime
    bbox: tuple[int, int, int, int]  # x, y, w, h
    zone_id: str | None = None
    event_type: Literal["enter", "exit", "in_zone"]

class DwellEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    zone_id: str
    track_id: str
    start_ts: datetime
    end_ts: datetime
    duration_sec: float

class StockEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    shelf_id: str
    timestamp: datetime
    status: Literal["empty", "low", "ok"]
    confidence: float

class QueueEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    counter_id: str
    timestamp: datetime
    queue_length: int
    avg_wait_est_sec: float | None = None

class Alert(BaseModel):
    model_config = ConfigDict(frozen=True)
    alert_id: str
    alert_type: Literal["low_stock", "queue_congestion", "custom"]
    severity: Literal["info", "warning", "critical"]
    zone_id: str | None = None
    message: str
    created_at: datetime
    resolved_at: datetime | None = None
```

**Hard constraint (do not violate):** no model above may contain an `image`,
`frame`, `face`, `embedding`, or any raw-pixel-carrying field. This is
intentional and structural, not an oversight — do not "fix" it.

## Config loader

`config.yaml` should hold: camera source config (placeholder RTSP URL),
list of `ZoneConfig` entries (can be empty/example placeholder), and
threshold defaults (`low_stock_confidence_threshold`, `queue_congestion_length`).
Write a `load_config(path: str) -> AppConfig` function where `AppConfig` is
itself a Pydantic model wrapping the above. Fail loudly (raise, don't
silently default) on a malformed config file.

## Tooling setup

- `pyproject.toml`: configure `ruff` (line length 100, reasonable default
  rule set) and `mypy` with `strict = true`.
- `.pre-commit-config.yaml`: run ruff + mypy on commit.
- `pytest` discoverable from repo root, `tests/unit/` as the test dir for
  this slice (later slices add their own test dirs under `tests/`).

## Acceptance tests (must pass before slice is done)

- [ ] Every schema round-trips: `Model(**data).model_dump()` reproduces
      equivalent data for at least one valid example per model.
- [ ] Invalid data raises `ValidationError` for at least one bad-input case
      per model (e.g. `ZoneConfig` with a 2-point polygon, `StockEvent`
      with an out-of-range confidence).
- [ ] `load_config()` successfully loads a valid example `config.yaml`.
- [ ] `load_config()` raises on a malformed `config.yaml` (missing required
      field) — write a fixture for this.
- [ ] `mypy --strict schemas.py` passes with zero errors.
- [ ] `ruff check .` passes with zero errors.
- [ ] A static/structural test asserts none of the schema classes has a
      field named `image`, `frame_data`, `face`, or `embedding` (guard so
      this can't silently regress in a future slice's edit).

## Non-goals for this slice

- No camera code, no model inference, no detection logic — this is types
  and config only.
- No FastAPI app yet (that's Slice 8).
- No SQLite/storage wiring yet (that's Slice 7) — schemas defined here are
  used by storage later, not implemented here.

## Agent prompt seed

> Implement `schemas.py` and `config.yaml`/`AppConfig` exactly per the
> models specified in `SLICE_0_scaffold.md`. Do not add fields beyond what's
> listed. Set up ruff + mypy strict + pytest + pre-commit per the tooling
> section. Write the acceptance tests first, then make them pass. Do not
> create any files or directories outside this slice's "Files owned" list —
> if you believe you need to, stop and note it instead of proceeding.