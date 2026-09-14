#!/usr/bin/env bash
# EdgeRetailAI Raspberry Pi 4B Automated Deployment Script
# SIH 26179 Hardware POC
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$SCRIPT_DIR"

MULTI_STORE=false

for arg in "$@"; do
    case "$arg" in
        --multi-store|--expose|-m)
            MULTI_STORE=true
            ;;
        --help|-h)
            echo "Usage: ./deploy-pi.sh [--multi-store | --expose | -m]"
            echo "  --multi-store, --expose, -m : Configure edge store node for central multi-store aggregation"
            exit 0
            ;;
    esac
done

echo "=== EdgeRetailAI Pi Deployment ==="
echo "Working directory: $WORKDIR"
if [ "$MULTI_STORE" = true ]; then
    echo "Mode: Multi-Store Edge Node (Exposed for Central Aggregator)"
fi

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

# Model check and INT8 quantization
FP32_MODEL="$WORKDIR/backend/models/yolo26n.onnx"
INT8_MODEL="$WORKDIR/backend/models/yolo26n_int8.onnx"

if [ ! -f "$FP32_MODEL" ] && [ ! -f "$INT8_MODEL" ]; then
    echo "WARNING: Neither FP32 nor INT8 YOLO model found in $WORKDIR/backend/models/."
    echo "Ensure yolo26n.onnx or yolo26n_int8.onnx is placed in $WORKDIR/backend/models/ before starting."
elif [ ! -f "$INT8_MODEL" ] && [ -f "$FP32_MODEL" ]; then
    echo "Generating INT8 quantized model for Raspberry Pi hardware acceleration..."
    "$VENV_DIR/bin/python" -c "
import sys
sys.path.insert(0, '$WORKDIR/backend')
from benchmarks.quantize import quantize_model
quantize_model('$FP32_MODEL', '$INT8_MODEL')
" || echo "WARNING: INT8 quantization failed. System will fall back to FP32 model."
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

# Multi-Store configuration if flag provided
if [ "$MULTI_STORE" = true ]; then
    echo "Configuring environment for Multi-Store edge integration..."
    if [ -f "$WORKDIR/.env.pi" ]; then
        grep -q "HOST=" "$WORKDIR/.env.pi" && sed -i 's/^HOST=.*/HOST=0.0.0.0/' "$WORKDIR/.env.pi" || echo "HOST=0.0.0.0" >> "$WORKDIR/.env.pi"
        grep -q "PORT=" "$WORKDIR/.env.pi" && sed -i 's/^PORT=.*/PORT=8000/' "$WORKDIR/.env.pi" || echo "PORT=8000" >> "$WORKDIR/.env.pi"
        grep -q "MULTI_STORE_EXPOSED=" "$WORKDIR/.env.pi" || echo "MULTI_STORE_EXPOSED=true" >> "$WORKDIR/.env.pi"
        grep -q "ENABLE_CENTRAL_DASHBOARD=" "$WORKDIR/.env.pi" || echo "ENABLE_CENTRAL_DASHBOARD=false" >> "$WORKDIR/.env.pi"
    fi

    if command -v ufw &>/dev/null; then
        SUDO_CMD=""
        if [ "$EUID" -ne 0 ]; then SUDO_CMD="sudo"; fi
        if $SUDO_CMD ufw status 2>/dev/null | grep -qw "active"; then
            echo "Opening port 8000 in ufw firewall for remote central polling..."
            $SUDO_CMD ufw allow 8000/tcp comment "EdgeRetailAI Store Node" || true
        fi
    fi
fi

# Ensure ownership
if [ "$EUID" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$WORKDIR"
fi

# Install systemd service
SERVICE_TEMPLATE="$WORKDIR/deploy/edgeretailai.service.template"
TARGET_SERVICE="/etc/systemd/system/edgeretailai.service"

if [ -f "$WORKDIR/deploy/build-frontend.sh" ]; then
    chmod +x "$WORKDIR/deploy/build-frontend.sh"
fi

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
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")"
echo "EdgeRetailAI is running at: http://$LOCAL_IP:8000"

if [ "$MULTI_STORE" = true ]; then
    PUBLIC_IP="$(curl -s -m 3 https://api.ipify.org 2>/dev/null || curl -s -m 3 https://ifconfig.me 2>/dev/null || echo "$LOCAL_IP")"
    HOST_SLUG="$(hostname -s 2>/dev/null || echo "pi")"

    echo ""
    echo "=================================================================="
    echo "MULTI-STORE REGISTRATION (Paste into Central Server stores.yaml):"
    echo ""
    echo "  - store_id: \"store_$HOST_SLUG\""
    echo "    name: \"Store Node - $(hostname 2>/dev/null || echo "Pi")\""
    echo "    api_base_url: \"http://$PUBLIC_IP:8000\"  # Or http://$LOCAL_IP:8000 for LAN/VPN"
    echo ""
    echo "Internet Access Tip: If this Pi is behind NAT/firewall without a static"
    echo "public IP, port-forward 8000 on your router or use Tailscale / Cloudflare Tunnel."
    echo "=================================================================="
fi