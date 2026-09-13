#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$WORKDIR/frontend"

if [ -d "$FRONTEND_DIR" ]; then
    if command -v npm >/dev/null 2>&1; then
        echo "[EdgeRetailAI] Building frontend dashboard before server start..."
        cd "$FRONTEND_DIR"
        if [ ! -d "node_modules" ]; then
            npm install --prefer-offline --no-audit
        fi
        npm run build
        echo "[EdgeRetailAI] Frontend build completed successfully."
    elif [ -d "$FRONTEND_DIR/dist" ]; then
        echo "[EdgeRetailAI] npm not found; using existing frontend/dist."
    else
        echo "[EdgeRetailAI] WARNING: npm not found and frontend/dist missing."
    fi
fi
