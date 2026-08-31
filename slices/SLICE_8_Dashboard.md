# Slice 8 — Dashboard API + UI

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice exposes
everything the prior slices produced (footfall counts, dwell/heatmap,
stock status, queue state, alerts) through a FastAPI backend and a minimal
frontend — the piece judges actually look at during the live demo.

## FR satisfied

FR2 (footfall trends by time/day/zone — aggregation happens here), FR4
(heatmap rendering — Slice 3 produced the numeric grid, this slice renders
it), FR16 (real-time alerts, dashboard, KPI visualization).

## Depends on

- Slice 0: all `schemas.py` models.
- Slice 7: `EventRepository` — this slice reads from storage, it does not
  talk to camera/detection/inventory/queue_intel/alerts directly. The
  pipeline that feeds `EventRepository` is wiring, not this slice's job
  (see Non-goals).

## Files owned by this slice

```
api/__init__.py
api/main.py                 # FastAPI app, route registration
api/routes/kpi.py            # /kpi/footfall, /kpi/queue, /kpi/stock endpoints
api/routes/alerts.py          # /alerts endpoints
api/routes/heatmap.py           # /heatmap endpoint (numeric grid, not image)
api/schemas_api.py                # response models (API-facing, separate from
                                    # storage schemas.py if shapes diverge —
                                    # state whether you reused schemas.py
                                    # models directly or needed API-specific ones)
dashboard/                          # frontend — Streamlit app.py, or minimal
                                      # static HTML+JS if that's the agent's
                                      # choice; state which and why
tests/unit/test_api_kpi.py
tests/unit/test_api_alerts.py
tests/unit/test_api_heatmap.py
```

Do not touch `schemas.py`, `storage/`, or any detection/analytics slice.
If a KPI aggregation needs a new `EventRepository` query method that
doesn't exist yet, propose the smallest possible addition and flag it
rather than reaching into `storage/repository.py` and rewriting it.

## Interface in

`EventRepository` (Slice 7) as the sole data source. No direct camera or
model access from this slice.

## Interface out

REST endpoints (exact paths are this slice's call, but these are the
expected ones per CONTEXT.md's dashboard requirement):

- `GET /kpi/footfall?zone_id=&since=` — count of enter/exit events,
  optionally filtered, aggregated by hour/day as query params allow.
- `GET /kpi/queue?counter_id=` — latest queue length + avg wait per counter.
- `GET /kpi/stock?shelf_id=` — latest stock status per shelf.
- `GET /alerts?status=open|resolved|all` — list of alerts.
- `GET /heatmap?zone_id=` — numeric grid data (JSON array of arrays, or
  flattened with dimensions — agent's choice, document the shape) for the
  frontend to render, NOT a rendered image from the backend.

All response models should be Pydantic (FastAPI's normal pattern) — reuse
`schemas.py` models directly where the shape matches exactly; only
introduce new API-specific response models where aggregation changes the
shape (e.g. an hourly-bucketed footfall count isn't a `DetectionEvent`,
it's a new small model like `FootfallBucket{hour: datetime, count: int}`).

Frontend: a single dashboard view showing — live-ish KPI numbers (poll or
manual refresh is fine for POC, no need for websockets), an alerts list
with severity coloring, and a heatmap visualization (can render the numeric
grid as a simple colored grid/table in the frontend, doesn't need to be a
polished image overlay for the POC). Streamlit is explicitly acceptable
and probably fastest — don't over-invest in frontend framework choice per
`CONTEXT.md`'s existing guidance.

## Acceptance tests

- [ ] Each KPI endpoint returns a 200 with correctly-shaped data when the
      underlying `EventRepository` has relevant rows (seed test DB with
      known events, assert the endpoint's aggregation matches by hand
      calculation).
- [ ] Each KPI endpoint handles the empty-data case gracefully (empty list
      or zero counts, not a 500).
- [ ] `/alerts?status=open` excludes resolved alerts; `status=all` includes
      both.
- [ ] `/heatmap` returns data whose dimensions are internally consistent
      (documented shape matches actual response).
- [ ] Malformed query params (e.g. invalid `since` date format) return a
      4xx with a clear error, not a 500.
- [ ] API tests use FastAPI's `TestClient` against a test SQLite DB (not
      the real one) — isolated, repeatable, no shared state between test runs.
- [ ] `mypy --strict` and `ruff check` clean on the `api/` code (frontend
      code in `dashboard/` may be exempt from strict typing if it's a
      Streamlit script — state the tooling boundary clearly).

## Non-goals for this slice

- No live camera-to-dashboard pipeline wiring (i.e., no code here starts
  the camera loop, runs detection, and writes to storage — that
  orchestration is either a follow-up "glue" script outside any single
  slice's ownership, or handled when preparing the live demo). This slice
  only reads what's already in `EventRepository`.
- No websockets/real-time push — polling or manual refresh is fine.
- No authentication/user accounts (explicit non-goal in CONTEXT.md).
- No multi-store view (Slice 11).
- No production deployment config (nginx, docker, etc.) — `uvicorn` dev
  server and `streamlit run` are sufficient for the POC demo.

## Agent prompt seed

> Implement the FastAPI backend (`api/`) and a minimal dashboard frontend
> (`dashboard/`) exactly per `slices/SLICE_8_dashboard.md`, reading only
> from Slice 7's `EventRepository`. State your frontend choice (Streamlit
> recommended) and why. Reuse `schemas.py` models as API response models
> wherever the shape matches exactly; only add new response models for
> genuinely aggregated shapes (e.g. hourly footfall buckets). Use FastAPI's
> `TestClient` against an isolated test SQLite DB, not the real one. Write
> acceptance tests first, including the empty-data and malformed-query
> cases — those are the ones most likely to produce embarrassing live-demo
> crashes. Do not modify schemas.py, storage/, or any detection/analytics
> slice; if you need a new `EventRepository` query method, propose the
> smallest addition and flag it rather than rewriting the repository.