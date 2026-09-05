# Slice 11 — Multi-Store Centralized Monitoring

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice adds a
centralized rollup view across multiple store deployments, without
retrofitting a `store_id` into every existing schema — each store keeps
running its own independent, offline-capable pipeline (per CONTEXT.md's
edge-first philosophy); this slice adds an aggregation layer *on top*,
built from Slice 8's existing per-store dashboard APIs.

## Architecture decision (read before starting)

Two designs were considered:
(a) Retrofit `store_id` into every `schemas.py` event model and
`EventRepository` table — rejected. It would touch every prior slice's
files, violates the "don't modify other slices" boundary broadly, and
contradicts the edge-first principle that each store's pipeline must keep
working fully offline and independently — a shared `store_id`-keyed schema
implies a shared/centralized data model that doesn't match the
architecture.
(b) Each store runs its existing independent pipeline (Slices 0-10,
unmodified) exposing its own Slice 8 dashboard API. A separate central
aggregator process periodically polls each store's `/kpi/*`, `/alerts`
endpoints and combines results into a cross-store view. **This is the
required approach for this slice.** It's eventually-consistent (a store
that's offline just doesn't report in that cycle — consistent with
FR13's "operate during disruption" requirement extending naturally to
"a disrupted store's local operation is unaffected by central visibility").

## FR satisfied

FR17 (scalable deployment, multi-store centralized monitoring — the
"centralized monitoring of multiple locations" clause specifically).

## Depends on

- Slice 8: each store's `/kpi/footfall`, `/kpi/queue`, `/kpi/stock`,
  `/alerts` endpoints — this slice is an HTTP client of those, not a new
  data model.
- Nothing else. No changes to `schemas.py`, `storage/`, or any single-store
  pipeline slice.

## Files owned by this slice

```
central/__init__.py
central/store_registry.py       # StoreConfig, load list of known stores from a config file
central/aggregator.py            # polls each store's API, combines into cross-store summary
central/central_dashboard.py      # separate Streamlit app, cross-store view (distinct from
                                    # Slice 8's per-store dashboard/app.py)
stores.yaml                         # example config: list of {store_id, name, api_base_url}
tests/unit/test_store_registry.py
tests/unit/test_aggregator.py
```

Do not touch `schemas.py`, `storage/`, `api/`, `dashboard/`, or any other
slice. This slice is a client of Slice 8's HTTP API, nothing more.

## Interface in

Slice 8's REST API, called once per known store (HTTP client, e.g.
`httpx`, already a dependency per Slice 8's `TestClient` usage).

## Interface out

```python
@dataclass(frozen=True)
class StoreConfig:
    store_id: str
    name: str
    api_base_url: str  # e.g. "http://192.168.1.50:8000" — each store's own
                         # Slice 8 FastAPI instance

def load_store_registry(path: str | Path) -> list[StoreConfig]:
    """Load known stores from stores.yaml. Fail loudly on malformed config,
    same pattern as Slice 0's load_config()."""
    ...

@dataclass(frozen=True)
class StoreStatus:
    store_id: str
    reachable: bool
    footfall_summary: FootfallSummary | None   # None if unreachable
    open_alert_count: int | None
    queue_events: list[QueueEvent] | None
    stock_events: list[StockEvent] | None
    error: str | None  # populated if unreachable, explains why

@dataclass(frozen=True)
class CrossStoreSummary:
    generated_at: datetime
    stores: list[StoreStatus]
    total_reachable: int
    total_unreachable: int

def poll_store(config: StoreConfig, timeout_sec: float = 5.0) -> StoreStatus:
    """Query one store's API. On timeout/connection failure, return a
    StoreStatus with reachable=False and error populated — never raise,
    never let one unreachable store block polling the others."""
    ...

def aggregate_stores(
    registry: list[StoreConfig],
    timeout_sec: float = 5.0,
) -> CrossStoreSummary:
    """Poll all known stores (in parallel or sequentially — agent's choice,
    state which and why) and combine into a CrossStoreSummary."""
    ...
```

Central dashboard: a Streamlit app (separate from Slice 8's per-store
`dashboard/app.py`) showing a table/grid of all known stores with their
reachability status, and, for reachable stores, key KPI numbers
side-by-side (footfall, open alert count, any critical alerts flagged).
An unreachable store should be visibly marked as such (e.g. "offline" /
greyed out), not silently omitted — this is a real demo point: showing
that one store going offline doesn't crash the central view or hide the
fact that it's offline.

## Acceptance tests

- [ ] `load_store_registry()` correctly parses a valid `stores.yaml` into
      a list of `StoreConfig`.
- [ ] `load_store_registry()` raises clearly on malformed config (mirror
      Slice 0's `load_config()` pattern).
- [ ] `poll_store()` against a reachable mock API (use `httpx`'s mock
      transport or a local `TestClient`-backed store, not a real network
      call) returns `reachable=True` with populated summary data.
- [ ] `poll_store()` against an unreachable/timeout-simulated endpoint
      returns `reachable=False` with `error` populated, and does NOT raise.
- [ ] `aggregate_stores()` with a mix of reachable and unreachable stores
      in the registry returns a `CrossStoreSummary` correctly counting
      both, without one unreachable store preventing others from being
      polled (test explicitly: one unreachable store must not block or
      delay reporting on the others incorrectly — if sequential, this
      test just confirms it still completes and reports all stores; if
      parallel, additionally confirm no store's failure raises up through
      to a different store's result).
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No shared/central database — each store keeps its own local SQLite
  (Slice 7), fully independent. The central view is a read-only,
  best-effort aggregation, not a data merge.
- No historical cross-store trend storage (e.g. "compare last week's
  footfall across all stores") — this slice provides a live/current
  snapshot only; a persistent central analytics store is future work.
- No store-to-store data sharing or centralized alerting decisions — each
  store's `AlertEngine` (Slice 6) still makes its own local decisions.
- No authentication between central aggregator and store APIs (matches
  Slice 8's explicit non-goal of no auth for the POC).

## Agent prompt seed

> Implement `StoreConfig`, `load_store_registry`, `poll_store`,
> `aggregate_stores`, and the central Streamlit dashboard exactly per
> `slices/SLICE_11_multi_store.md`. This is an HTTP client of Slice 8's
> existing per-store API — do not add a `store_id` field to any
> `schemas.py` model or touch `storage/`/`api/`/`dashboard/`. One
> unreachable store must never raise an exception that blocks polling or
> reporting on the others — test this explicitly. State whether you
> polled stores sequentially or in parallel, and why. Write acceptance
> tests first, using a mocked HTTP transport (e.g. `httpx.MockTransport`)
> rather than real network calls, so tests are fast and deterministic.