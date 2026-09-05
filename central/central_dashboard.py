from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from central.aggregator import CrossStoreSummary, aggregate_stores
from central.store_registry import StoreConfig, load_store_registry

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Central Retail AI Monitor</title>
  <style>
    body { font-family: sans-serif; margin: 0; background: #0f172a; color: #f8fafc; }
    header {
      padding: 1rem 2rem; background: #1e293b;
      display: flex; justify-content: space-between;
    }
    h1 { margin: 0; font-size: 1.3rem; color: #38bdf8; }
    .stats { display: flex; gap: 1rem; }
    .card-s { background: #0f172a; padding: 0.5rem 1rem; border-radius: 4px; }
    main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
    .grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1rem;
    }
    .card { background: #1e293b; border-radius: 6px; padding: 1rem; }
    .card.offline { border: 1px solid #ef4444; }
    .badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }
    .badge.online { background: #166534; color: #86efac; }
    .badge.offline { background: #991b1b; color: #fca5a5; }
    .err { color: #fca5a5; background: #450a0a; padding: 0.5rem; margin-top: 0.5rem; }
  </style>
</head>
<body>
  <header>
    <h1>Central Store Operations Monitor</h1>
    <div class="stats">
      <div class="card-s">Total: <span id="tot">-</span></div>
      <div class="card-s" style="color:#4ade80;">Online: <span id="on">-</span></div>
      <div class="card-s" style="color:#f87171;">Offline: <span id="off">-</span></div>
    </div>
  </header>
  <main>
    <div class="grid" id="grid">Loading...</div>
  </main>
  <script>
    async function refresh() {
      const res = await fetch('/api/summary');
      const data = await res.json();
      document.getElementById('tot').innerText = data.stores.length;
      document.getElementById('on').innerText = data.total_reachable;
      document.getElementById('off').innerText = data.total_unreachable;
      const grid = document.getElementById('grid');
      grid.innerHTML = data.stores.map(s => `
        <div class="card ${s.reachable ? '' : 'offline'}">
          <h3>${s.store_id} <span class="badge ${s.reachable ? 'online' : 'offline'}">
            ${s.reachable ? 'ONLINE' : 'OFFLINE'}
          </span></h3>
          ${s.reachable ? `
            <p>Occupancy: ${s.footfall ? s.footfall.net_occupancy : 0}</p>
            <p>Open Alerts: ${s.open_alert_count}</p>
          ` : `<div class="err">${s.error}</div>`}
        </div>
      `).join('');
    }
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""


def create_central_app(config_path: str | Path = "stores.yaml") -> FastAPI:
    """Create FastAPI application for centralized multi-store monitoring."""
    app = FastAPI(
        title="Central Multi-Store Retail Intelligence",
        description="Rollup monitoring across distributed edge retail store deployments",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_registry() -> list[StoreConfig]:
        path = Path(config_path)
        if not path.is_file():
            return []
        try:
            return load_store_registry(path)
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed loading store registry: {exc}"
            ) from exc

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stores", tags=["central"])
    def get_stores() -> list[dict[str, str]]:
        return [
            {"store_id": s.store_id, "name": s.name, "api_base_url": s.api_base_url}
            for s in get_registry()
        ]

    @app.get("/api/summary", tags=["central"])
    def get_cross_store_summary() -> dict[str, Any]:
        registry = get_registry()
        summary: CrossStoreSummary = aggregate_stores(registry)

        stores_data = []
        for s in summary.stores:
            stores_data.append(
                {
                    "store_id": s.store_id,
                    "reachable": s.reachable,
                    "error": s.error,
                    "footfall": (
                        {
                            "total_enters": s.footfall_summary.total_enters,
                            "total_exits": s.footfall_summary.total_exits,
                            "net_occupancy": s.footfall_summary.net_occupancy,
                        }
                        if s.footfall_summary
                        else None
                    ),
                    "open_alert_count": s.open_alert_count,
                    "queue_events_count": len(s.queue_events) if s.queue_events else 0,
                    "stock_events_count": len(s.stock_events) if s.stock_events else 0,
                }
            )

        return {
            "generated_at": summary.generated_at.isoformat(),
            "total_reachable": summary.total_reachable,
            "total_unreachable": summary.total_unreachable,
            "stores": stores_data,
        }

    @app.get("/", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_ui() -> str:
        return HTML_TEMPLATE

    return app


app = create_central_app()
