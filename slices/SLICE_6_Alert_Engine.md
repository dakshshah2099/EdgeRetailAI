# Slice 6 — Alerting Engine

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice consumes
event streams from Slices 3, 4, and 5 and turns threshold breaches into
`Alert`s — with debounce (no repeated firing) and resolve-on-clear.

## FR satisfied

FR7 (alert staff on replenishment need), FR9 (predict congestion — the
threshold/decision half, Slice 5 produced the raw signal), FR10 (recommend
opening additional counters), FR16 (real-time alerts, partial — this slice
produces the `Alert` objects; Slice 8 surfaces them on a dashboard).

## Depends on

- Slice 0: `Alert`, `StockEvent`, `QueueEvent`, `AppConfig` from `schemas.py`
  (specifically `low_stock_confidence_threshold`, `queue_congestion_length`).
- Slice 4: `StockEvent` stream (`status` field).
- Slice 5: `QueueEvent` stream (`queue_length` field).

This slice does not touch camera, detection, or tracking code at all — it's
a pure event-in, alert-out transformation layer.

## Files owned by this slice

```
alerts/__init__.py
alerts/alert_engine.py
tests/unit/test_alert_engine.py
```

Do not touch `schemas.py`, `inventory/`, `queue_intel/`, `detection/`. If
alert logic needs an `AppConfig` threshold field that doesn't exist yet
(e.g. a separate "critical" vs "warning" queue length), propose it and flag.

## Interface in

`StockEvent`s and `QueueEvent`s (from Slices 4 and 5), plus threshold
values from `AppConfig` (`low_stock_confidence_threshold`,
`queue_congestion_length`).

## Interface out

```python
class AlertEngine:
    """Turns threshold breaches into Alerts. Debounced: a condition that
    stays breached across many consecutive events does not re-fire a new
    Alert every time — it fires once, then stays open until the condition
    clears, at which point resolved_at is set on the existing Alert."""

    def __init__(
        self,
        low_stock_threshold: float,
        queue_congestion_length: int,
    ) -> None: ...

    def process_stock_event(self, event: StockEvent) -> Alert | None:
        """Returns a new Alert if this event causes a low_stock condition
        to newly open (not already open for this shelf_id), else None."""
        ...

    def process_queue_event(self, event: QueueEvent) -> Alert | None:
        """Returns a new Alert if queue_length >= queue_congestion_length
        and no congestion alert is currently open for this counter_id,
        else None."""
        ...

    def check_resolutions(
        self,
        latest_stock_events: dict[str, StockEvent],
        latest_queue_events: dict[str, QueueEvent],
    ) -> list[Alert]:
        """Given the latest known state per shelf_id/counter_id, return
        updated (resolved) Alert objects for any previously-open alert
        whose condition has cleared. Since Alert is frozen (schemas.py),
        'updating' means constructing a new Alert instance with the same
        alert_id and resolved_at set — document this clearly since it's a
        slightly unusual pattern forced by the frozen model."""
        ...

    def get_open_alerts(self) -> list[Alert]: ...

    def reset(self) -> None: ...
```

Severity mapping (state if you choose different, but this is a reasonable
default): `status == "empty"` → `"critical"`; `status == "low"` → `"warning"`;
queue congestion → `"warning"` at threshold, `"critical"` if queue_length
exceeds threshold by some margin (state your margin choice, e.g. 1.5x).

`message` field on `Alert` should be a short human-readable string, e.g.
`"Shelf zone_shelf_a is out of stock"` or `"Checkout counter zone_checkout_1
has 6 people waiting — consider opening another counter"` (ties FR10's
"recommend opening additional counters" into the message text itself for
POC purposes, since a full staffing-recommendation system is out of scope).

## Acceptance tests

- [ ] A single `StockEvent` with `status == "empty"` produces one `Alert`
      with `alert_type == "low_stock"`, `severity == "critical"`.
- [ ] A second consecutive `StockEvent` with `status == "empty"` for the
      *same* `shelf_id` does NOT produce a second `Alert` (debounce).
- [ ] A `StockEvent` with `status == "ok"` for a shelf that previously had
      an open alert causes `check_resolutions()` to return that alert with
      `resolved_at` now set.
- [ ] A `QueueEvent` with `queue_length` at/above `queue_congestion_length`
      produces exactly one `Alert`; subsequent events at the same or higher
      length while still open do not re-fire.
- [ ] A `QueueEvent` with `queue_length` dropping back below threshold
      resolves the previously open alert via `check_resolutions()`.
- [ ] Two different shelves/counters in breach at the same time produce
      two independent alerts, tracked independently.
- [ ] `get_open_alerts()` excludes resolved alerts.
- [ ] `reset()` clears all open-alert state.
- [ ] `mypy --strict` and `ruff check` clean.

## Non-goals for this slice

- No notification delivery (SMS/push/email) — `Alert` objects are the
  output; wiring them to a real notification channel is out of scope for
  the POC (dashboard display in Slice 8 is sufficient).
- No persistence (Slice 7 stores events/alerts to SQLite).
- No `DwellEvent`-driven alerting — dwell data feeds analytics/heatmaps,
  not alerts, per the FR mapping in CONTEXT.md.
- No staffing optimization algorithm — the alert message can *suggest*
  opening a counter in plain text, but does not compute which counter or
  how many staff.

## Agent prompt seed

> Implement `AlertEngine` exactly per `slices/SLICE_6_alerting.md`. Pay
> close attention to debounce semantics: an already-open alert for a given
> shelf_id/counter_id must not re-fire while the condition remains breached,
> and must resolve (not just silently disappear) when the condition clears.
> Since `Alert` is a frozen Pydantic model, resolving an alert means
> constructing a new instance with the same `alert_id` and `resolved_at`
> set — document this pattern clearly in your report. Write acceptance
> tests first, especially the debounce and resolution cases — those are
> the parts most likely to have subtle bugs. Do not modify schemas.py,
> inventory/, queue_intel/, or detection/.