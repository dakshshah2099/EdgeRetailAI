#!/usr/bin/env bash
# EdgeRetailAI Raspberry Pi 4B Automated Deployment Script
# SIH 26179 Hardware POC
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$SCRIPT_DIR"

echo "=== EdgeRetailAI Pi Deployment ==="
echo "Working directory: $WORKDIR"

# Detect user
SERVICE_USER="${SUDO_USER:-${USER:-pi}}"
SERVICE_GROUP="$(id -gn "$SERVICE_USER" 2>/dev/null || echo "$SERVICE_USER")"
echo "Deploying for user: $SERVICE_USER (group: $SERVICE_GROUP)"

# Architecture verification
ARCH="$(uname -m)"
echo "Detected architecture: $ARCH"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    echo "WARNING: Expected aarch64/arm64 architecture. Detected $ARCH. Proceeding anyway..."
fi

# Ensure camera access permissions
if command -v usermod &>/dev/null; then
    echo "Adding $SERVICE_USER to video group for camera device access..."
    usermod -a -G video "$SERVICE_USER" 2>/dev/null || sudo usermod -a -G video "$SERVICE_USER" 2>/dev/null || true
fi

# System packages
if command -v apt-get &>/dev/null; then
    echo "Installing required system packages (OpenCV dependencies, python3-venv, nodejs, npm, etc.)..."
    SUDO_CMD=""
    if [ "$EUID" -ne 0 ]; then
        SUDO_CMD="sudo"
    fi
    $SUDO_CMD apt-get update -qq
    $SUDO_CMD apt-get install -y -qq \
        python3 \
        python3-venv \
        python3-pip \
        libgl1 \
        libglib2.0-0 \
        curl \
        v4l-utils \
        nodejs \
        npm
fi

# Setup Python virtual environment
VENV_DIR="$WORKDIR/backend/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$WORKDIR/backend" || "$VENV_DIR/bin/pip" install fastapi uvicorn[standard] pydantic pyyaml numpy onnx onnxruntime opencv-python-headless httpx

# Build Svelte dashboard if frontend exists
if [ -d "$WORKDIR/frontend" ]; then
    echo "Checking frontend dashboard build..."
    if command -v npm &>/dev/null; then
        echo "Building frontend dashboard with Vite..."
        pushd "$WORKDIR/frontend" >/dev/null
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run build
        popd >/dev/null
    elif [ -d "$WORKDIR/frontend/dist" ]; then
        echo "Pre-built frontend/dist found. Skipping npm build."
    else
        echo "WARNING: Node.js/npm not found and frontend/dist missing."
    fi
fi

# Model check
MODEL_PATH="$WORKDIR/backend/models/yolo26n.onnx"
if [ ! -f "$MODEL_PATH" ]; then
    echo "WARNING: Model not found at $MODEL_PATH."
    echo "Ensure yolo26n.onnx is placed in $WORKDIR/backend/models/ before starting."
fi

# Environment configuration
if [ ! -f "$WORKDIR/.env.pi" ]; then
    if [ -f "$WORKDIR/deploy/.env.pi.example" ]; then
        echo "Creating .env.pi from deploy/.env.pi.example..."
        cp "$WORKDIR/deploy/.env.pi.example" "$WORKDIR/.env.pi"
    fi
fi

if [ ! -f "$WORKDIR/backend/.env" ] && [ ! -L "$WORKDIR/backend/.env" ]; then
    if [ -f "$WORKDIR/.env.pi" ]; then
        echo "Linking .env.pi to backend/.env..."
        ln -sf "$WORKDIR/.env.pi" "$WORKDIR/backend/.env" 2>/dev/null || cp "$WORKDIR/.env.pi" "$WORKDIR/backend/.env"
    fi
fi

# Ensure ownership
if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKDIR"
fi

# Install systemd service
SERVICE_TEMPLATE="$WORKDIR/deploy/edgeretailai.service.template"
TARGET_SERVICE="/etc/systemd/system/edgeretailai.service"

if [ -f "$SERVICE_TEMPLATE" ]; then
    echo "Generating systemd service from template..."
    sed -e "s|\${SERVICE_USER}|$SERVICE_USER|g" \
        -e "s|\${SERVICE_GROUP}|$SERVICE_GROUP|g" \
        -e "s|\${WORKDIR}|$WORKDIR|g" \
        "$SERVICE_TEMPLATE" > /tmp/edgeretailai.service

    SUDO_CMD=""
    if [ "$EUID" -ne 0 ]; then
        SUDO_CMD="sudo"
    fi

    $SUDO_CMD mv /tmp/edgeretailai.service "$TARGET_SERVICE"
    $SUDO_CMD chmod 644 "$TARGET_SERVICE"
    $SUDO_CMD systemctl daemon-reload
    $SUDO_CMD systemctl enable edgeretailai.service
    $SUDO_CMD systemctl restart edgeretailai.service
    echo "Service edgeretailai.service configured and restarted."
    $SUDO_CMD systemctl status edgeretailai.service --no-pager || true
fi

echo "=== Deployment Completed Successfully ==="
echo "EdgeRetailAI is running at: http://$(hostname -I | awk '{print $1}'):8000"