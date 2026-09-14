import contextlib
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.schemas_api import CentralFootfallSummary, CentralStoreStatus, CentralSummaryResponse
from central.aggregator import CrossStoreSummary, aggregate_stores
from central.store_registry import StoreConfig, load_store_registry

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Central Store Operations Monitor</title>
  <style>
    :root {
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --border-dark: #cbd5e1;
      --text: #0f172a;
      --muted: #64748b;
      --primary: #0284c7;
      --primary-hover: #0369a1;
      --emerald-bg: #ecfdf5;
      --emerald-border: #a7f3d0;
      --emerald-text: #065f46;
      --rose-bg: #fff1f2;
      --rose-border: #fecdd3;
      --rose-text: #9f1239;
      --amber-bg: #fffbeb;
      --amber-border: #fde68a;
      --amber-text: #92400e;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    header {
      background: #ffffff;
      border-bottom: 1px solid var(--border);
      padding: 0.85rem 1.5rem;
      position: sticky;
      top: 0;
      z-index: 30;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03);
    }
    .header-inner {
      max-width: 1400px;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-icon {
      width: 32px;
      height: 32px;
      background: #0284c7;
      color: #ffffff;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 1rem;
    }
    .brand-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .badge-sub {
      font-size: 0.65rem;
      font-family: monospace;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      background: #f1f5f9;
      border: 1px solid #cbd5e1;
      color: #475569;
      font-weight: 600;
      letter-spacing: 0.05em;
    }
    .controls {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.75rem;
      font-family: monospace;
    }
    .refresh-select {
      background: #ffffff;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.3rem 0.6rem;
      border-radius: 4px;
      font-size: 0.75rem;
      outline: none;
      cursor: pointer;
    }
    .btn-refresh {
      background: #0284c7;
      color: #ffffff;
      border: none;
      padding: 0.35rem 0.75rem;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      font-family: monospace;
      font-size: 0.75rem;
      transition: background 0.15s;
    }
    .btn-refresh:hover { background: var(--primary-hover); }
    .last-sync {
      color: var(--muted);
      font-size: 0.72rem;
    }

    main {
      max-width: 1400px;
      margin: 1.5rem auto;
      padding: 0 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    /* Fleet KPI Ribbon */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      box-shadow: 0 1px 3px 0 rgba(0,0,0,0.02);
    }
    .kpi-label {
      font-size: 0.7rem;
      font-family: monospace;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0.05em;
      font-weight: 600;
    }
    .kpi-val {
      font-size: 1.5rem;
      font-weight: 800;
      color: var(--text);
      font-family: monospace;
    }
    .kpi-sub {
      font-size: 0.72rem;
      color: var(--muted);
    }

    /* Filters & Search */
    .filter-bar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      background: #ffffff;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    .tabs {
      display: flex;
      gap: 0.5rem;
    }
    .tab-btn {
      background: transparent;
      border: 1px solid transparent;
      padding: 0.25rem 0.65rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-family: monospace;
      color: var(--muted);
      cursor: pointer;
      font-weight: 600;
      transition: all 0.15s;
    }
    .tab-btn.active {
      background: #f1f5f9;
      border-color: #cbd5e1;
      color: var(--text);
    }
    .search-input {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 0.3rem 0.6rem;
      font-size: 0.75rem;
      outline: none;
      width: 200px;
    }
    .search-input:focus { border-color: var(--primary); }

    /* Store Grid */
    .store-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1.25rem;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      box-shadow: 0 1px 3px 0 rgba(0,0,0,0.02);
      transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
    }
    .card:hover {
      border-color: #94a3b8;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .card.offline {
      border-color: #fda4af;
      background: #fffafa;
    }
    .card-header {
      padding: 1rem 1.25rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
    }
    .card-title {
      font-size: 1rem;
      font-weight: 700;
      color: var(--text);
    }
    .card-subtitle {
      font-size: 0.72rem;
      font-family: monospace;
      color: var(--muted);
      margin-top: 0.15rem;
    }
    .badge {
      font-size: 0.65rem;
      font-family: monospace;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-weight: 700;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }
    .badge-online {
      background: var(--emerald-bg);
      border: 1px solid var(--emerald-border);
      color: var(--emerald-text);
    }
    .badge-offline {
      background: var(--rose-bg);
      border: 1px solid var(--rose-border);
      color: var(--rose-text);
    }
    .badge-alert {
      background: var(--amber-bg);
      border: 1px solid var(--amber-border);
      color: var(--amber-text);
    }
    .badge-zero-alert {
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      color: #64748b;
    }

    .card-body {
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      flex: 1;
    }
    .metrics-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
    }
    .metric-box {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.6rem 0.8rem;
    }
    .metric-box-label {
      font-size: 0.65rem;
      font-family: monospace;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }
    .metric-box-val {
      font-size: 1.15rem;
      font-weight: 800;
      font-family: monospace;
      color: var(--text);
      margin-top: 0.2rem;
    }
    .metric-sub {
      font-size: 0.68rem;
      color: var(--muted);
      margin-top: 0.1rem;
    }

    .status-strip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.4rem 0.6rem;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.72rem;
      font-family: monospace;
    }

    .err-container {
      background: var(--rose-bg);
      border: 1px solid var(--rose-border);
      color: var(--rose-text);
      padding: 0.75rem;
      border-radius: 6px;
      font-size: 0.72rem;
      font-family: monospace;
      word-break: break-all;
    }

    .card-footer {
      padding: 0.75rem 1.25rem;
      background: #fcfdfe;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .launch-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      background: #ffffff;
      border: 1px solid #cbd5e1;
      color: var(--text);
      text-decoration: none;
      font-size: 0.72rem;
      font-family: monospace;
      font-weight: 600;
      padding: 0.3rem 0.65rem;
      border-radius: 4px;
      transition: all 0.15s;
    }
    .launch-btn:hover {
      background: #f1f5f9;
      border-color: #94a3b8;
    }

    .empty-state {
      background: #ffffff;
      border: 1px dashed var(--border-dark);
      border-radius: 8px;
      padding: 3rem 2rem;
      text-align: center;
      color: var(--muted);
    }
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="brand">
        <div class="brand-icon">⚡</div>
        <div>
          <div class="brand-title">
            <span>Central Store Operations Monitor</span>
            <span class="badge-sub">FLEET OPS</span>
            <span class="badge-sub">EDGE AI</span>
          </div>
        </div>
      </div>
      <div class="controls">
        <span class="last-sync" id="last-sync">Syncing...</span>
        <div>
          Auto-refresh:
          <select id="refresh-interval" class="refresh-select" onchange="updateInterval()">
            <option value="3000">3s</option>
            <option value="5000" selected>5s</option>
            <option value="10000">10s</option>
            <option value="0">Off</option>
          </select>
        </div>
        <button class="btn-refresh" onclick="refresh()">Refresh Now</button>
      </div>
    </div>
  </header>

  <main>
    <!-- Fleet KPI Ribbon -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">Fleet Reachability</span>
        <div class="kpi-val" id="kpi-reachability">-</div>
        <div class="kpi-sub" id="kpi-reachability-sub">Checking edge nodes...</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total In-Store Occupancy</span>
        <div class="kpi-val" id="kpi-occupancy">-</div>
        <div class="kpi-sub" id="kpi-occupancy-sub">Across all active stores</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Fleet Footfall Today</span>
        <div class="kpi-val" id="kpi-footfall">-</div>
        <div class="kpi-sub" id="kpi-footfall-sub">Total enters & exits</div>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Total Open Alerts</span>
        <div class="kpi-val" id="kpi-alerts">-</div>
        <div class="kpi-sub" id="kpi-alerts-sub">Fleet incident load</div>
      </div>
    </div>

    <!-- Filters & Search -->
    <div class="filter-bar">
      <div class="tabs">
        <button class="tab-btn active" onclick="setFilter('all', this)" id="tab-all">
          All Stores (<span id="count-all">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('online', this)">
          Online (<span id="count-on">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('offline', this)">
          Offline (<span id="count-off">0</span>)
        </button>
        <button class="tab-btn" onclick="setFilter('alerting', this)">
          Alerting (<span id="count-alert">0</span>)
        </button>
      </div>
      <input
        type="text"
        id="search-input"
        class="search-input"
        placeholder="Search stores..."
        oninput="handleSearch()"
      />
    </div>

    <!-- Store Grid -->
    <div class="store-grid" id="store-grid">
      <div class="empty-state">Polling store registry...</div>
    </div>
  </main>

  <script>
    let rawStores = [];
    let currentFilter = 'all';
    let searchQuery = '';
    let refreshTimer = null;

    function setFilter(filter, el) {
      currentFilter = filter;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
      render();
    }

    function handleSearch() {
      searchQuery = (document.getElementById('search-input').value || '').toLowerCase().trim();
      render();
    }

    function updateInterval() {
      if (refreshTimer) clearInterval(refreshTimer);
      const val = parseInt(document.getElementById('refresh-interval').value, 10);
      if (val > 0) {
        refreshTimer = setInterval(refresh, val);
      }
    }

    async function refresh() {
      try {
        const basePath = window.location.pathname.replace(/\/$/, '');
        const res = await fetch(basePath + '/api/summary');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        rawStores = data.stores || [];

        // 1. Calculate Fleet KPIs
        const total = rawStores.length;
        const online = data.total_reachable;
        const offline = data.total_unreachable;
        const pct = total > 0 ? Math.round((online / total) * 100) : 0;

        let totalOccupancy = 0;
        let totalEnters = 0;
        let totalExits = 0;
        let totalAlerts = 0;
        let alertingCount = 0;

        rawStores.forEach(s => {
          if (s.reachable && s.footfall) {
            totalOccupancy += (s.footfall.net_occupancy || 0);
            totalEnters += (s.footfall.total_enters || 0);
            totalExits += (s.footfall.total_exits || 0);
          }
          if (s.open_alert_count) {
            totalAlerts += s.open_alert_count;
            alertingCount++;
          }
        });

        document.getElementById('kpi-reachability').innerText = `${online} / ${total}`;
        document.getElementById('kpi-reachability-sub').innerText = `${pct}% edge nodes online`;

        document.getElementById('kpi-occupancy').innerText = totalOccupancy;
        document.getElementById('kpi-occupancy-sub').innerText = `Across ${online} online nodes`;

        document.getElementById('kpi-footfall').innerText = `↑${totalEnters}  ↓${totalExits}`;
        document.getElementById('kpi-footfall-sub').innerText = `Net +${totalOccupancy} shoppers`;

        document.getElementById('kpi-alerts').innerText = totalAlerts;
        document.getElementById('kpi-alerts-sub').innerText =
          `${alertingCount} stores with active alerts`;

        // Update Tab Counts
        document.getElementById('count-all').innerText = total;
        document.getElementById('count-on').innerText = online;
        document.getElementById('count-off').innerText = offline;
        document.getElementById('count-alert').innerText = alertingCount;

        const now = new Date();
        document.getElementById('last-sync').innerText = 'Last sync: ' + now.toLocaleTimeString();

        render();
      } catch (err) {
        console.error('Failed fetching central summary:', err);
        document.getElementById('last-sync').innerText = 'Sync failed: ' + err.message;
      }
    }

    function render() {
      const grid = document.getElementById('store-grid');
      let list = rawStores.slice();

      if (currentFilter === 'online') list = list.filter(s => s.reachable);
      else if (currentFilter === 'offline') list = list.filter(s => !s.reachable);
      else if (currentFilter === 'alerting') {
        list = list.filter(s => s.open_alert_count && s.open_alert_count > 0);
      }

      if (searchQuery) {
        list = list.filter(s =>
          (s.store_id || '').toLowerCase().includes(searchQuery) ||
          (s.name || '').toLowerCase().includes(searchQuery)
        );
      }

      if (list.length === 0) {
        grid.innerHTML = '<div class="empty-state">No matching store nodes found.</div>';
        return;
      }

      grid.innerHTML = list.map(s => {
        const storeName = s.name || s.store_id;
        const alertCount = s.open_alert_count || 0;
        const alertBadge = alertCount > 0
          ? `<span class="badge badge-alert">${alertCount} ALERTS</span>`
          : `<span class="badge badge-zero-alert">0 ALERTS</span>`;

        return `
          <div class="card ${s.reachable ? '' : 'offline'}">
            <div class="card-header">
              <div>
                <div class="card-title">${storeName}</div>
                <div class="card-subtitle">ID: ${s.store_id}</div>
              </div>
              <span class="badge ${s.reachable ? 'badge-online' : 'badge-offline'}">
                ${s.reachable ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>

            <div class="card-body">
              ${s.reachable ? `
                <div class="metrics-row">
                  <div class="metric-box">
                    <div class="metric-box-label">In-Store Occupancy</div>
                    <div class="metric-box-val">${s.footfall ? s.footfall.net_occupancy : 0}</div>
                    <div class="metric-sub">Live Headcount</div>
                  </div>
                  <div class="metric-box">
                    <div class="metric-box-label">Today's Footfall</div>
                    <div class="metric-box-val">↑${s.footfall ? s.footfall.total_enters : 0}</div>
                    <div class="metric-sub">↓ ${s.footfall ? s.footfall.total_exits : 0} Exits</div>
                  </div>
                </div>

                <div class="status-strip">
                  <span>ACTIVE INCIDENTS:</span>
                  ${alertBadge}
                </div>

                <div class="status-strip">
                  <span>PIPELINE EVENTS:</span>
                  <span>${s.queue_events_count} Queue · ${s.stock_events_count} Stock</span>
                </div>
              ` : `
                <div class="err-container">
                  <strong>CONNECTION FAILURE:</strong><br>
                  ${s.error || 'Node unreachable. Port closed or network down.'}
                </div>
              `}
            </div>

            <div class="card-footer">
              <span class="card-subtitle">${s.api_base_url || 'Local Edge Node'}</span>
              ${s.api_base_url ? `
                <a href="${s.api_base_url}" target="_blank" rel="noopener" class="launch-btn">
                  Launch Node ↗
                </a>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');
    }

    refresh();
    updateInterval();
  </script>
</body>
</html>
"""


def create_central_app(config_path: str | Path = "stores.yaml") -> FastAPI:
    """Create FastAPI application for centralized multi-store monitoring."""
    app = FastAPI(
        title="Central Multi-Store Retail Intelligence",
        description="Rollup monitoring across distributed edge retail store deployments",
        version="0.2.0",
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
            backend_alt = Path(__file__).resolve().parent.parent / config_path
            if backend_alt.is_file():
                path = backend_alt
            else:
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

    @app.get("/api/stores", response_model=list[StoreConfig], tags=["central"])
    def get_stores() -> list[StoreConfig]:
        return get_registry()

    @app.get("/api/summary", response_model=CentralSummaryResponse, tags=["central"])
    def get_cross_store_summary() -> CentralSummaryResponse:
        registry = get_registry()
        if (
            os.environ.get("AUTO_SPAWN_LOCAL_STORES", "true").lower() == "true"
            and "PYTEST_CURRENT_TEST" not in os.environ
        ):
            with contextlib.suppress(Exception):
                from central.store_spawner import spawn_configured_local_stores

                spawn_configured_local_stores(config_path)

        summary: CrossStoreSummary = aggregate_stores(registry)

        stores_data: list[CentralStoreStatus] = []
        for s in summary.stores:
            stores_data.append(
                CentralStoreStatus(
                    store_id=s.store_id,
                    name=s.name,
                    api_base_url=s.api_base_url,
                    reachable=s.reachable,
                    error=s.error,
                    footfall=(
                        CentralFootfallSummary(
                            total_enters=s.footfall_summary.total_enters,
                            total_exits=s.footfall_summary.total_exits,
                            net_occupancy=s.footfall_summary.net_occupancy,
                        )
                        if s.footfall_summary
                        else None
                    ),
                    open_alert_count=s.open_alert_count,
                    queue_events_count=len(s.queue_events) if s.queue_events else 0,
                    stock_events_count=len(s.stock_events) if s.stock_events else 0,
                )
            )

        return CentralSummaryResponse(
            generated_at=summary.generated_at.isoformat(),
            total_reachable=summary.total_reachable,
            total_unreachable=summary.total_unreachable,
            stores=stores_data,
        )

    @app.get("/", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_ui() -> str:
        return HTML_TEMPLATE

    @app.get("/central", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_ui_central() -> str:
        return HTML_TEMPLATE

    return app


app = create_central_app()
