# Slice 8 — FastAPI Backend & Svelte Dashboard

Read `AGENTS.md` and `CONTEXT.md` before starting. This slice implements the
local HTTP API (FastAPI) and single-viewport web dashboard (Svelte 5 / Vite)
for real-time retail analytics, live camera streaming, ROI calibration, and debug control.

## FR satisfied

FR10 (real-time alerts feed), FR11 (wait time and queue metrics display),
FR12 (spatial traffic heatmap visualization), FR14 (edge local-first UI),
FR15 (zero PII exposure across all API responses).

## Depends on

- Slice 0: `schemas.py` contracts (`Alert`, `QueueEvent`, `StockEvent`, `DetectionEvent`).
- Slice 1: `CameraSource` / RTSP video streams.
- Slice 7: `EventRepository` / SQLite `retail.db`.

## Files owned by this slice

```
api/__init__.py
api/main.py
api/dependencies.py
api/env_manager.py
api/schemas_api.py
api/routes/__init__.py
api/routes/kpi.py
api/routes/alerts.py
api/routes/heatmap.py
api/routes/system.py
api/routes/video.py
dashboard/
  src/
    App.svelte
    app.css
    lib/api.js
    components/
tests/unit/test_api_kpi.py
tests/unit/test_api_alerts.py
tests/unit/test_api_heatmap.py
tests/unit/test_api_system.py
tests/unit/test_api_video.py
```

## Interface in/out

- **In:** HTTP client requests (`GET /kpi/footfall`, `GET /kpi/queue`, `GET /kpi/stock`, `GET /alerts`, `GET /heatmap`, `GET /video/stream`, `GET /video/snapshot`, `GET /system/env`, `PUT /system/env`, `PUT /system/zones`).
- **Out:** Typed Pydantic JSON responses and multipart MJPEG stream.
