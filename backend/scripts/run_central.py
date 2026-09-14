#!/usr/bin/env python3
"""Run Central Multi-Store Operations Server.

Usage:
    python backend/scripts/run_central.py --port 8500 --config backend/stores.yaml
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from central.server import main  # noqa: E402

if __name__ == "__main__":
    main()
