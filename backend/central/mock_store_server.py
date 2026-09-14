import logging
import socket
import threading
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.schemas_api import FootfallSummary
from core.schemas import Alert, QueueEvent, StockEvent

logger = logging.getLogger(__name__)


def _build_landing_page(name: str, store_id: str, port: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{name} - Edge Node ({store_id})</title>
  <style>
    body {{
      font-family: sans-serif;
      margin: 0;
      background: #0b1329;
      color: #f8fafc;
      padding: 2rem;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 1.5rem;
      max-width: 650px;
      margin: 2rem auto;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3);
    }}
    h1 {{
      margin: 0 0 0.5rem;
      font-size: 1.4rem;
      color: #38bdf8;
      display: flex;
      justify-content: space-between;
    }}
    .badge {{
      background: #065f46;
      color: #34d399;
      font-size: 0.75rem;
      font-family: monospace;
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
    }}
    p {{ color: #94a3b8; font-size: 0.9rem; line-height: 1.5; }}
    ul {{ list-style: none; padding: 0; margin: 1rem 0; }}
    li {{ margin: 0.5rem 0; font-family: monospace; font-size: 0.85rem; }}
    a {{ color: #38bdf8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .footer {{
      margin-top: 1.5rem;
      font-size: 0.75rem;
      color: #64748b;
      font-family: monospace;
      border-top: 1px solid #334155;
      padding-top: 0.75rem;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>
      <span>{name}</span>
      <span class="badge">ACTIVE EDGE NODE</span>
    </h1>
    <p>Store ID: <code>{store_id}</code> | Port: <code>{port}</code></p>
    <p>
      Autonomous retail analytics serving REST endpoints to the Central Aggregator.
    </p>
    <h3>Available Telemetry Endpoints:</h3>
    <ul>
      <li>GET <a href="/kpi/footfall">/kpi/footfall</a> &mdash; Store occupancy & footfall</li>
      <li>GET <a href="/kpi/queue">/kpi/queue</a> &mdash; Checkout queue & dwell times</li>
      <li>GET <a href="/kpi/stock">/kpi/stock</a> &mdash; Shelf inventory & stockout detection</li>
      <li>GET <a href="/alerts?status=open">/alerts</a> &mdash; Active operational alert feeds</li>
      <li>GET <a href="/health">/health</a> &mdash; Connectivity heartbeat</li>
    </ul>
    <div class="footer">
      EdgeRetailAI &bull; Independent Offline-Capable Edge Architecture
    </div>
  </div>
</body>
</html>
"""


def create_mock_store_app(store_id: str, name: str, port: int) -> FastAPI:
    """Create a lightweight edge store FastAPI application simulating live telemetry."""
    app = FastAPI(
        title=f"Edge Retail Node - {name}",
        description=f"Simulated live edge retail telemetry for {store_id}",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "store_id": store_id,
            "name": name,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @app.get("/kpi/footfall", response_model=FootfallSummary, tags=["kpi"])
    def get_footfall() -> FootfallSummary:
        if "airport" in store_id:
            return FootfallSummary(total_enters=312, total_exits=298, net_occupancy=14)
        return FootfallSummary(total_enters=184, total_exits=162, net_occupancy=22)

    @app.get("/alerts", response_model=list[Alert], tags=["alerts"])
    def get_alerts(status: str | None = None) -> list[Alert]:
        now = datetime.now(UTC)
        if "airport" in store_id:
            return []
        alerts = [
            Alert(
                alert_id=f"alt_{store_id}_1",
                alert_type="low_stock",
                severity="warning",
                message="Shelf 2 - Snacks: Low stock threshold reached",
                created_at=now,
                resolved_at=None,
            )
        ]
        if status == "resolved":
            return [a for a in alerts if a.resolved_at is not None]
        if status == "open":
            return [a for a in alerts if a.resolved_at is None]
        return alerts

    @app.get("/kpi/queue", response_model=list[QueueEvent], tags=["kpi"])
    def get_queue() -> list[QueueEvent]:
        now = datetime.now(UTC)
        if "airport" in store_id:
            return [
                QueueEvent(
                    event_id="q_kiosk_1",
                    counter_id="kiosk_checkout_1",
                    queue_length=1,
                    avg_wait_est_sec=28.5,
                    timestamp=now,
                )
            ]
        return [
            QueueEvent(
                event_id="q_lane_1",
                counter_id="checkout_lane_1",
                queue_length=3,
                avg_wait_est_sec=64.0,
                timestamp=now,
            ),
            QueueEvent(
                event_id="q_lane_2",
                counter_id="checkout_lane_2",
                queue_length=2,
                avg_wait_est_sec=42.0,
                timestamp=now,
            ),
        ]

    @app.get("/kpi/stock", response_model=list[StockEvent], tags=["kpi"])
    def get_stock() -> list[StockEvent]:
        now = datetime.now(UTC)
        if "airport" in store_id:
            return [
                StockEvent(
                    event_id="stk_kiosk_1",
                    shelf_id="kiosk_shelf_grab_go",
                    status="ok",
                    confidence=0.88,
                    timestamp=now,
                )
            ]
        return [
            StockEvent(
                event_id="stk_bev_1",
                shelf_id="shelf_beverages",
                status="ok",
                confidence=0.91,
                timestamp=now,
            ),
            StockEvent(
                event_id="stk_snack_1",
                shelf_id="shelf_snacks",
                status="low",
                confidence=0.82,
                timestamp=now,
            ),
        ]

    @app.get("/", response_class=HTMLResponse, tags=["dashboard"])
    def landing_page() -> str:
        return _build_landing_page(name=name, store_id=store_id, port=port)

    return app


class ServerThread(threading.Thread):
    """Background daemon thread running a uvicorn FastAPI server."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        try:
            self.server.run()
        except (Exception, SystemExit) as exc:
            logger.warning("Mock store server on %s:%d stopped: %s", self.host, self.port, exc)

    def stop(self) -> None:
        self.server.should_exit = True


_active_threads: list[ServerThread] = []
_threads_lock = threading.Lock()


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a local TCP port is already open or cannot be bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def start_mock_store_servers() -> list[ServerThread]:
    """Start simulated edge store nodes on ports 8001 and 8002 if not already occupied."""
    global _active_threads
    with _threads_lock:
        if _active_threads:
            return _active_threads

        configs = [
            ("store_suburban", "Suburban Mall", 8001),
            ("store_airport", "Terminal 2 Kiosk", 8002),
        ]

        for store_id, name, port in configs:
            if is_port_in_use(port):
                logger.info("Port %d is already in use; skipping mock store startup.", port)
                continue

            app = create_mock_store_app(store_id=store_id, name=name, port=port)
            thread = ServerThread(app=app, host="127.0.0.1", port=port)
            thread.start()
            _active_threads.append(thread)
            logger.info("Started mock edge store '%s' on http://127.0.0.1:%d", name, port)

        return _active_threads


def stop_mock_store_servers() -> None:
    """Terminate all active background mock edge store servers."""
    global _active_threads
    with _threads_lock:
        for t in _active_threads:
            t.stop()
        _active_threads.clear()


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)
    logger.info("Launching simulated edge store nodes on ports 8001 & 8002...")
    start_mock_store_servers()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down mock store nodes...")
        stop_mock_store_servers()
