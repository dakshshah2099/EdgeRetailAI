"""Multi-Store Retail Network Launcher.

Spins up genuine edge store applications (Ports 8000, 8001, 8002) with isolated
databases and the standalone Central Multi-Store Monitor (Port 8500).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn  # noqa: E402

from central.server import create_central_server  # noqa: E402
from central.store_spawner import (  # noqa: E402
    spawn_configured_local_stores,
    spawn_real_store,
    stop_all_spawned_stores,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("multi_store_launcher")


def main() -> None:
    stores_cfg = backend_dir / "stores.yaml"

    logger.info("==================================================================")
    logger.info("Starting Multi-Store Retail Edge Network (Genuine Stores)...")
    logger.info("  Primary Edge Store:       http://127.0.0.1:8000")
    logger.info("  Suburban Mall Edge Store: http://127.0.0.1:8001")
    logger.info("  Terminal 2 Kiosk Store:   http://127.0.0.1:8002")
    logger.info("  Central Operations View:  http://127.0.0.1:8500")
    logger.info("==================================================================")

    # 1. Spawn secondary stores (8001, 8002) as real edge nodes
    spawn_configured_local_stores(stores_cfg)

    # 2. Spawn primary store (8000) if not running
    spawn_real_store("store_main", "Downtown Flagship", 8000)

    # 3. Run Central Server on port 8500
    central_app = create_central_server(config_path=stores_cfg, auto_spawn=False)

    try:
        uvicorn.run(central_app, host="0.0.0.0", port=8500, log_level="info")
    except KeyboardInterrupt:
        logger.info("Terminating all store edge nodes...")
    finally:
        stop_all_spawned_stores()
        logger.info("Multi-store network cleanly shut down.")


if __name__ == "__main__":
    main()
