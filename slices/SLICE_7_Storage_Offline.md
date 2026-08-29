# Slice 7 — Local Storage & Offline Resilience

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice persists
aggregated events (never raw frames/PII) to SQLite, and buffers writes
during a simulated "cloud sync" outage so nothing is lost — the concrete
proof point for FR13 (operate during internet disruption).

## FR satisfied

FR13 (operate during internet disruption), FR14 (reduce cloud bandwidth —
local-first storage, sync is batched/optional not continuous), FR15
(privacy-aware — enforced structurally, this slice cannot violate it since
`schemas.py` models have no image/PII fields to persist in the first place).

## Depends on

- Slice 0: `DetectionEvent`, `DwellEvent`, `StockEvent`, `QueueEvent`,
  `Alert` from `schemas.py` — these are exactly what gets persisted, no
  new models needed here.
- Nothing from Slices 1-6's *code* directly — this slice takes typed
  events as input regardless of which slice produced them.

## Files owned by this slice

```
storage/__init__.py
storage/db.py                # SQLite schema + connection management
storage/repository.py         # typed save/query functions per event type
storage/sync_buffer.py         # buffered outbound queue, retry-on-reconnect
tests/unit/test_db.py
tests/unit/test_repository.py
tests/unit/test_sync_buffer.py
```

Do not touch `schemas.py` or any other slice's files. This slice only
consumes the typed models Slice 0 already defined.

## Interface in

Any of `DetectionEvent`, `DwellEvent`, `StockEvent`, `QueueEvent`, `Alert`
— all already defined in `schemas.py`, all already PII-free by construction.

## Interface out

```python
def init_db(db_path: str | Path) -> None:
    """Create tables if they don't exist. Idempotent — safe to call on
    every app startup."""
    ...

class EventRepository:
    """Typed save/query layer over SQLite. One table per event type,
    columns matching the Pydantic model fields exactly — no JSON blobs
    for structured data (queryability matters for the dashboard in
    Slice 8), except for genuinely nested fields (e.g. ZoneConfig.polygon
    if ever persisted, which it currently isn't in this slice's scope)."""

    def __init__(self, db_path: str | Path) -> None: ...

    def save_detection_event(self, event: DetectionEvent) -> None: ...
    def save_dwell_event(self, event: DwellEvent) -> None: ...
    def save_stock_event(self, event: StockEvent) -> None: ...
    def save_queue_event(self, event: QueueEvent) -> None: ...
    def save_alert(self, alert: Alert) -> None: ...
    def upsert_alert(self, alert: Alert) -> None:
        """Alert resolution (Slice 6) produces a new Alert instance with
        the same alert_id — this must UPDATE the existing row (matched on
        alert_id), not insert a duplicate."""
        ...

    def get_recent_stock_events(self, limit: int = 100) -> list[StockEvent]: ...
    def get_open_alerts(self) -> list[Alert]: ...
    # add other query methods as needed for Slice 8's dashboard — keep
    # them typed, returning schemas.py models, not raw rows/dicts.

class SyncBuffer:
    """Queues events when a (simulated) cloud endpoint is unreachable,
    flushes them in order when connectivity returns. For the POC, the
    'cloud endpoint' can be a stubbed/mock callable — this slice does not
    need a real cloud backend, just the buffering/retry mechanism."""

    def __init__(self, max_buffer_size: int = 10_000) -> None: ...

    def enqueue(self, event: DetectionEvent | DwellEvent | StockEvent | QueueEvent | Alert) -> None: ...

    def flush(self, sink: Callable[[list[...]], bool]) -> int:
        """Attempt to send all buffered events via sink (returns True on
        success). Returns count successfully flushed. On sink failure,
        buffered events remain queued (not lost, not re-ordered)."""
        ...

    def pending_count(self) -> int: ...
```

## Acceptance tests

- [ ] `init_db()` creates all expected tables; calling it twice on the same
      path does not error or duplicate schema.
- [ ] Each `save_*` method persists an event such that a subsequent query
      returns an equivalent (not necessarily identical object, but
      field-equal) model instance.
- [ ] `upsert_alert()` on an alert_id that already exists updates the row
      in place (test: save an open alert, then upsert a resolved version
      with the same alert_id, assert only one row exists and it reflects
      `resolved_at`).
- [ ] Killing/mocking network mid-run: `SyncBuffer.enqueue()` continues to
      accept events while `flush()` is failing (sink returns False or
      raises); no events are dropped — `pending_count()` reflects all of
      them.
- [ ] On a subsequent successful `flush()` call, all previously buffered
      events are sent in original order and `pending_count()` returns to 0.
- [ ] `max_buffer_size` is respected — test behavior at capacity (either
      reject new events with a clear signal, or drop-oldest with a logged
      warning; agent's choice, but must be deliberate and tested, not
      silently undefined).
- [ ] No raw frame, image, or embedding field appears in any table schema
      (structural test, same spirit as Slice 0's PII guard test).
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No real cloud/remote sync target — a mock/stub sink is sufficient for
  the POC; a real HTTP endpoint integration is future work, not this slice.
- No dashboard/API (Slice 8) — this slice is the persistence layer only.
- No multi-store data model yet (Slice 11) — single-store schema for now.
- No automatic periodic flush scheduling (e.g. a background thread/cron) —
  `flush()` is called explicitly by whatever orchestrates the pipeline;
  scheduling is an integration detail for wherever the main loop lives.

## Agent prompt seed

> Implement `init_db`, `EventRepository`, and `SyncBuffer` exactly per
> `slices/SLICE_7_storage_offline.md`. One SQLite table per event type,
> typed queries returning `schemas.py` models — no raw dict/JSON blobs for
> structured fields. Pay special attention to `upsert_alert` (must update
> by `alert_id`, not duplicate) since Slice 6's resolution pattern depends
> on this working correctly. `SyncBuffer` needs a deliberate, tested
> behavior at `max_buffer_size` capacity — pick reject-new or drop-oldest
> and document which. Write acceptance tests first, especially the
> buffer-survives-outage-then-flushes-in-order case — that's the direct
> proof point for the "works offline" pitch claim. Do not modify
> schemas.py or any other slice's files.