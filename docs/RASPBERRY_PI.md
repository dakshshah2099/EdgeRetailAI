# Raspberry Pi 4B Deployment Guide (SIH 26179 Hardware POC)

This guide documents the setup, execution, systemd daemonization, and performance benchmarking of the **EdgeRetailAI** retail analytics pipeline on a **Raspberry Pi 4B (ARM64)** running **Raspberry Pi OS (64-bit Bookworm / Debian 12)**.

---

## 1. Hardware Architecture & Requirements

- **Device**: Raspberry Pi 4 Model B (4GB or 8GB RAM).
- **OS**: Raspberry Pi OS 64-bit (`aarch64`).
- **Cooling**: Active cooling fan or aluminum heatsink case strongly recommended.
- **Camera**: USB Webcam (V4L2 `/dev/video0`), Raspberry Pi Camera via libcamera/V4L2, or IP Phone camera over RTSP (`rtsp://<ip>:<port>/live`).
- **Power**: Official 5.1V 3.0A USB-C Power Supply.

---

## 2. Quick Automated Deployment

EdgeRetailAI includes an idempotent deployment script `deploy/deploy-pi.sh` that detects your active user, installs system packages, configures permissions, builds the dashboard, and provisions a `systemd` daemon:

```bash
git clone https://github.com/dakshshah2099/EdgeRetailAI.git
cd EdgeRetailAI
chmod +x deploy/deploy-pi.sh
./deploy/deploy-pi.sh
```

---

## 3. Manual Step-by-Step Installation

### Step 3.1: System Packages & Permissions
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip libgl1 libglib2.0-0 v4l-utils curl nodejs npm

# Add user to video group for camera device access
sudo usermod -a -G video "$USER"
```
*(Log out and log back in for video group permissions to take effect).*

### Step 3.2: Python Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic pyyaml numpy onnx onnxruntime opencv-python-headless httpx
```

### Step 3.3: Frontend Dashboard Build
The Svelte 5 frontend is compiled at build time. No Node.js process runs on the Pi at runtime:
```bash
cd frontend
npm install
npm run build
cd ..
```

### Step 3.4: Configure Environment
Copy `deploy/.env.pi.example` to `.env.pi`:
```bash
cp deploy/.env.pi.example .env.pi
```

Key environment variables:
| Variable | Default | Purpose |
|:---|:---:|:---|
| `CAMERA_SOURCE` | `0` | Camera input (`0` for USB `/dev/video0`, or RTSP URL) |
| `YOLO_MODEL` | `models/yolo26n.onnx` | ONNX model file |
| `YOLO_INPUT_SIZE` | `640` | Input dimension (validated against ONNX graph) |
| `YOLO_INFERENCE_FPS` | `5` | Maximum inference rate (decoupled from capture) |
| `YOLO_INTRA_OP_THREADS`| `3` | ONNX thread pool (leaves 1 core for capture/FastAPI) |
| `SHELF_ANALYSIS_INTERVAL`| `1.0` | Seconds between shelf occupancy checks |
| `DATABASE_PATH` | `retail.db` | Local SQLite database path |
| `CONFIG_PATH` | `config.yaml` | Zone and camera configuration YAML path |
| `PORT` | `8000` | FastAPI server port |

---

## 4. Running the Application

### Direct Execution
```bash
source backend/.venv/bin/activate
cd backend
uvicorn api.main:app --host 0.0.0.0 --port 8000
```
- Dashboard UI: `http://<pi-ip>:8000/app/` (or `http://<pi-ip>:8000/` which redirects automatically)
- REST API Documentation: `http://<pi-ip>:8000/docs`
- Health Check: `http://<pi-ip>:8000/health`

### Running via Systemd (Background Service)
Template and install the service:
```bash
sed -e "s|\${SERVICE_USER}|$USER|g" \
    -e "s|\${SERVICE_GROUP}|$(id -gn)|g" \
    -e "s|\${WORKDIR}|$PWD|g" \
    deploy/edgeretailai.service.template | sudo tee /etc/systemd/system/edgeretailai.service

sudo systemctl daemon-reload
sudo systemctl enable edgeretailai.service
sudo systemctl start edgeretailai.service
```

Managing the service:
```bash
# Check status
sudo systemctl status edgeretailai.service

# View live application logs
sudo journalctl -u edgeretailai.service -f

# Restart service
sudo systemctl restart edgeretailai.service

# Stop service
sudo systemctl stop edgeretailai.service
```

---

## 5. Hardware Benchmarking & Thread Tuning

To evaluate inference throughput and thermal impact on your Pi:

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/backend"
python backend/benchmarks/pi_benchmark.py --threads 2,3,4 --iterations 50
```

### Understanding Thread Configuration:
- **`YOLO_INTRA_OP_THREADS=3` (Recommended)**:
  Consumes 3 out of 4 Cortex-A72 cores during inference. Leaves sufficient CPU headroom for the OpenCV capture thread, MJPEG stream encoder, and asynchronous FastAPI request handlers.
- **`YOLO_INTRA_OP_THREADS=4`**:
  Slightly faster isolated inference, but causes video stuttering and API latency spikes due to complete CPU core saturation.
- **`YOLO_INTRA_OP_THREADS=2`**:
  Use if running alongside other heavy background processes or on low-power battery supplies.
