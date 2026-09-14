"""Standalone Central Multi-Store Retail Operations Server.

Runs independently on a workstation, central server, or cloud VM to monitor
multiple distributed edge store nodes over HTTP/HTTPS, with optional auto-spawning
of local store nodes for development and testing.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from central.central_dashboard import create_central_app
from central.store_spawner import (
    spawn_configured_local_stores,
    stop_all_spawned_stores,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("central_server")


def create_central_server(
    config_path: str | Path = "stores.yaml",
    auto_spawn: bool = True,
) -> FastAPI:
    """Build FastAPI application for standalone Central server."""
    stores_path = Path(config_path)
    if not stores_path.is_file():
        backend_stores = BACKEND_DIR / config_path
        if backend_stores.is_file():
            stores_path = backend_stores

    @asynccontextmanager
    async def central_lifespan(app: FastAPI) -> AsyncIterator[None]:
        should_spawn = (
            auto_spawn
            and os.environ.get("AUTO_SPAWN_LOCAL_STORES", "true").lower() == "true"
            and "PYTEST_CURRENT_TEST" not in os.environ
        )
        if should_spawn:
            logger.info("Checking store registry for un-spawned nodes (%s)...", stores_path)
            spawned = spawn_configured_local_stores(stores_path)
            if spawned:
                logger.info("Spawned %d real local store nodes.", len(spawned))

        try:
            yield
        finally:
            if should_spawn:
                logger.info("Stopping all spawned local edge store nodes...")
                with contextlib.suppress(Exception):
                    stop_all_spawned_stores()

    central_app = create_central_app(config_path=stores_path)
    central_app.router.lifespan_context = central_lifespan
    return central_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EdgeRetailAI Central Multi-Store Operations Monitor",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CENTRAL_PORT", "8500")),
        help="Port to bind Central Server (default: 8500)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("CENTRAL_HOST", "0.0.0.0"),
        help="Host address to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=os.environ.get("STORES_CONFIG", "stores.yaml"),
        help="Path to stores.yaml registry configuration",
    )
    parser.add_argument(
        "--no-spawn",
        action="store_true",
        help="Disable automatic local store spawning for 127.0.0.1 nodes",
    )
    args = parser.parse_args()

    display_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    logger.info("==================================================================")
    logger.info("Launching Standalone Central Multi-Store Retail Monitor...")
    logger.info("  Host:           %s", args.host)
    logger.info("  Port:           %s", args.port)
    logger.info("  Registry:       %s", args.config)
    logger.info("  Auto-Spawn:     %s", not args.no_spawn)
    logger.info("  Dashboard URL:  http://%s:%s", display_host, args.port)
    logger.info("==================================================================")

    server_app = create_central_server(
        config_path=args.config,
        auto_spawn=not args.no_spawn,
    )

    uvicorn.run(
        server_app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
