# Slice 10 — POS/ERP Integration

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice connects the
pipeline's outputs to a POS/ERP system — pushing stock/alert signals
outward so replenishment can be triggered externally, and (optionally)
pulling transaction data back to compute a footfall-to-sales conversion KPI.
Per the explicit scope decision in CONTEXT.md, this IS in scope for the POC
(not a future-work placeholder).

## FR satisfied

FR17 (POS/ERP integration — the integration half; "scalable" deployment is
addressed separately, not this slice's concern).

## Depends on

- Slice 0: `StockEvent`, `Alert`, `DetectionEvent` from `schemas.py`.
- Slice 7: `EventRepository` — this slice reads recent events from storage
  to push outward; it does not hook directly into the live camera/detection
  pipeline (same pattern as Slice 8's dashboard, reading from storage).
- Slice 6: `Alert` objects specifically — POS/ERP integration is most
  useful for triggering replenishment on low-stock alerts, not raw
  `StockEvent`s (avoid pushing every noisy classification, only actionable
  alerts).

## Files owned by this slice

```
integrations/__init__.py
integrations/pos_connector.py       # POSConnector interface + a mock/stub implementation
integrations/sync_job.py             # periodic/triggered job: pull open low_stock alerts,
                                       # push to POS, pull sales data back if available
tests/unit/test_pos_connector.py
tests/unit/test_sync_job.py
```

Do not touch `schemas.py`, `storage/`, `alerts/`, `detection/`. This slice
is an integration/adapter layer — same spirit as Slice 7's `SyncBuffer`
sink being a stubbed callable rather than a real cloud backend, since no
real POS/ERP system is available for this POC.

## Interface in

`EventRepository` (Slice 7) for reading open `Alert`s and recent
`StockEvent`s/`DetectionEvent`s. No direct camera/detection access.

## Interface out

```python
@dataclass(frozen=True)
class POSStockUpdate:
    """Outbound payload representing a stock-related event pushed to POS/ERP.
    Generic shape — real POS/ERP systems vary widely, so this models the
    common denominator (SKU/shelf reference, status, timestamp) rather than
    a specific vendor's API contract."""
    shelf_id: str
    status: Literal["empty", "low", "ok"]
    alert_id: str | None
    timestamp: datetime

@dataclass(frozen=True)
class POSSalesRecord:
    """Inbound payload representing a transaction pulled from POS/ERP, used
    to compute footfall-to-conversion KPIs. Generic shape for the same
    reason as above."""
    transaction_id: str
    timestamp: datetime
    item_count: int
    total_amount: float | None  # None if POS doesn't expose amount, or if
                                  # withholding it is a deliberate simplification —
                                  # state which

class POSConnector(ABC):
    """Swap point: a mock/stub implementation for the POC, a real vendor
    SDK/REST client for production. Same swap-point philosophy as
    InferenceBackend (Slice 2) and SyncBuffer's sink (Slice 7)."""

    @abstractmethod
    def push_stock_update(self, update: POSStockUpdate) -> bool:
        """Push a stock update to POS/ERP. Returns True on success."""
        ...

    @abstractmethod
    def pull_recent_sales(self, since: datetime) -> list[POSSalesRecord]:
        """Pull transactions since the given timestamp. Returns empty list
        if the POS/ERP system doesn't support this or none exist."""
        ...

class MockPOSConnector(POSConnector):
    """POC stub: logs pushes, returns configurable canned sales data for
    testing. Not a real integration — state this clearly, same as Slice 7's
    stub cloud sink."""
    ...

def run_sync_job(
    repo: EventRepository,
    connector: POSConnector,
    since: datetime,
) -> SyncJobResult:
    """One sync cycle: fetch open low_stock alerts from repo, push each as
    a POSStockUpdate, pull recent sales, return a summary (counts pushed/
    pulled, any failures). Callable on a schedule or manually — this slice
    does not own the scheduling mechanism (same non-goal pattern as Slice 7's
    SyncBuffer not owning periodic flush scheduling)."""
    ...
```

## Acceptance tests

- [ ] `run_sync_job()` pushes exactly one `POSStockUpdate` per open
      `low_stock` alert currently in the repository (test with a seeded
      test DB containing a mix of open/resolved alerts of different types
      — only open `low_stock` ones should be pushed).
- [ ] A failed `push_stock_update()` (mock returns `False`) is recorded in
      `SyncJobResult` as a failure, not silently swallowed or treated as
      success.
- [ ] `pull_recent_sales()` respects the `since` filter (mock returns a
      fixed set, test that only records at/after `since` are included in
      the result — or that filtering happens correctly wherever it's
      implemented, agent's choice of where, but must be tested).
- [ ] `MockPOSConnector` is clearly documented/named as non-production —
      test that its presence doesn't silently get mistaken for a real
      integration (e.g. a clear log line or return value indicating mock
      mode, tested).
- [ ] No `POSStockUpdate`/`POSSalesRecord` carries pixel data, PII, or
      anything not already present in the source `Alert`/`StockEvent`.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No real vendor POS/ERP SDK integration (e.g. Square, Shopify POS, SAP) —
  a real integration is a future engineering task once a specific vendor
  is chosen for actual deployment; this slice proves the integration
  *pattern* works, same spirit as Slice 7's mock cloud sink.
- No conversion-rate KPI computation/dashboard surfacing — that's a
  natural Slice 8 follow-up once real sales data exists, not this slice's
  job (this slice only fetches the data).
- No scheduling infrastructure (cron, background thread) — `run_sync_job`
  is a callable unit; wiring it to run periodically is deployment
  configuration, not this slice.

## Agent prompt seed

> Implement `POSConnector`, `MockPOSConnector`, `POSStockUpdate`,
> `POSSalesRecord`, and `run_sync_job` exactly per
> `slices/SLICE_10_pos_erp.md`. Only push open `low_stock`-type `Alert`s
> to POS, not raw `StockEvent`s — avoid flooding a real POS/ERP with noisy
> classification data. `MockPOSConnector` must be clearly non-production —
> document and test this. Write acceptance tests first, especially the
> failure-is-recorded-not-swallowed case. Do not modify schemas.py,
> storage/, alerts/, or detection/.