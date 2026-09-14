"""Real Edge Store Node Spawner for Local Multi-Store Architecture.

Spawns genuine instances of create_app() with isolated SQLite databases
and real telemetry pipelines, transitioning away from synthetic mocks.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
import uvicorn

from api.dependencies import get_db_path, get_repository
from api.main import create_app
from central.store_registry import load_store_registry
from core.schemas import Alert, DetectionEvent, QueueEvent, StockEvent
from storage.db import init_db
from storage.repository import EventRepository

logger = logging.getLogger("store_spawner")


@dataclass
class SpawnedStore:
    store_id: str
    name: str
    port: int
    server: uvicorn.Server
    thread: threading.Thread
    db_path: Path


_spawned_stores: dict[int, SpawnedStore] = {}
_lock = threading.Lock()


def is_port_in_use(host: str, port: int) -> bool:
    """Check whether a specific host:port is currently bound and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def _seed_store_database(db_path: Path, store_id: str, port: int) -> None:
    """Seed an isolated store database with realistic retail events."""
    repo = EventRepository(db_path)
    now = datetime.now(UTC)

    # Vary seed data per store port so each store has distinct telemetry
    multiplier = (port % 10) + 1
    enters_count = 35 * multiplier
    exits_count = 20 * multiplier

    # 1. Seed footfall enters and exits
    for i in range(enters_count):
        ts = now - timedelta(minutes=enters_count - i)
        repo.add_detection_event(
            DetectionEvent(
                event_id=f"det_in_{store_id}_{i}",
                track_id=f"person_{i}",
                timestamp=ts,
                bbox=(100, 100, 50, 120),
                zone_id="zone_entrance",
                event_type="enter",
            )
        )

    for j in range(exits_count):
        ts = now - timedelta(minutes=exits_count - j)
        repo.add_detection_event(
            DetectionEvent(
                event_id=f"det_out_{store_id}_{j}",
                track_id=f"person_{j}",
                timestamp=ts,
                bbox=(100, 100, 50, 120),
                zone_id="zone_entrance",
                event_type="exit",
            )
        )

    # 2. Seed queue events
    queue_len = max(1, multiplier - 1)
    repo.add_queue_event(
        QueueEvent(
            event_id=f"q_{store_id}_01",
            counter_id="counter_1",
            timestamp=now,
            queue_length=queue_len,
            avg_dwell_sec=45.0 * queue_len,
        )
    )

    # 3. Seed stock events
    repo.add_stock_event(
        StockEvent(
            event_id=f"stk_{store_id}_01",
            shelf_id="shelf_beverages",
            timestamp=now,
            status="low" if multiplier % 2 == 1 else "ok",
            confidence=0.88,
        )
    )

    # 4. Seed an alert if applicable
    if multiplier % 2 == 1:
        repo.add_alert(
            Alert(
                alert_id=f"alert_{store_id}_01",
                alert_type="low_stock",
                severity="warning",
                message=f"Low stock detected on beverage aisle ({store_id})",
                timestamp=now,
                zone_id="shelf_beverages",
                status="open",
            )
        )


def spawn_real_store(
    store_id: str,
    name: str,
    port: int,
    host: str = "127.0.0.1",
    db_path: Path | None = None,
) -> SpawnedStore | None:
    """Launch a real instance of the EdgeRetailAI store application on the specified port."""
    with _lock:
        if port in _spawned_stores:
            return _spawned_stores[port]

        if is_port_in_use(host, port):
            logger.info("Store on port %s already running/in use. Skipping spawn.", port)
            return None

        # 1. Setup isolated SQLite DB
        if db_path is None:
            temp_dir = Path(tempfile.gettempdir()) / "edgeretail_nodes"
            temp_dir.mkdir(parents=True, exist_ok=True)
            db_path = temp_dir / f"{store_id}_{port}.db"

        init_db(db_path)
        _seed_store_database(db_path, store_id, port)

        # 2. Create real store FastAPI application
        store_app = create_app()
        store_repo = EventRepository(db_path)
        store_app.dependency_overrides[get_db_path] = lambda: db_path
        store_app.dependency_overrides[get_repository] = lambda: store_repo

        # 3. Configure uvicorn
        cfg = uvicorn.Config(
            app=store_app,
            host=host,
            port=port,
            log_level="error",
            access_log=False,
        )
        server = uvicorn.Server(cfg)

        def _run_server() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(server.serve())
            finally:
                loop.close()

        thread = threading.Thread(
            target=_run_server,
            name=f"StoreNode-{store_id}-{port}",
            daemon=True,
        )
        thread.start()

        # 4. Wait for server to become healthy
        deadline = time.time() + 4.0
        is_healthy = False
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=0.5) as client:
                    resp = client.get(f"http://{host}:{port}/health")
                    if resp.status_code == 200:
                        is_healthy = True
                        break
            except Exception:
                time.sleep(0.1)

        if not is_healthy:
            logger.warning("Store node %s on port %s took long to report healthy.", store_id, port)

        spawned = SpawnedStore(
            store_id=store_id,
            name=name,
            port=port,
            server=server,
            thread=thread,
            db_path=db_path,
        )
        _spawned_stores[port] = spawned
        logger.info("Successfully spawned real store node '%s' on %s:%s", name, host, port)
        return spawned


def spawn_configured_local_stores(
    stores_config_path: Path | str = "stores.yaml",
) -> list[SpawnedStore]:
    """Inspect store registry and automatically launch real instances for local un-spawned nodes."""
    path = Path(stores_config_path)
    if not path.is_file():
        backend_alt = Path(__file__).resolve().parent.parent / stores_config_path
        if backend_alt.is_file():
            path = backend_alt
        else:
            return []

    try:
        registry = load_store_registry(path)
    except Exception as exc:
        logger.error("Failed loading store registry for auto-spawning: %s", exc)
        return []

    spawned_list: list[SpawnedStore] = []
    for cfg in registry:
        parsed = urlparse(cfg.api_base_url)
        hostname = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80

        # Only auto-spawn loopback nodes
        if hostname in ("127.0.0.1", "localhost", "0.0.0.0") and not is_port_in_use(
            hostname, port
        ):
            spawned = spawn_real_store(
                store_id=cfg.store_id,
                name=cfg.name,
                port=port,
                host=hostname,
            )
            if spawned:
                spawned_list.append(spawned)

    return spawned_list


def stop_all_spawned_stores() -> None:
    """Shut down all running local store nodes cleanly."""
    with _lock:
        for port, store in list(_spawned_stores.items()):
            try:
                store.server.should_exit = True
            except Exception as exc:
                logger.warning("Error stopping store on port %s: %s", port, exc)
        _spawned_stores.clear()
    logger.info("All spawned edge store nodes stopped.")
