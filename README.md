# Intelligent Retail Analytics System (SIH26179) — Edge-AI POC

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.20+-005CED.svg)](https://onnxruntime.ai/)
[![Svelte](https://img.shields.io/badge/Svelte-4.2+-FF3E00.svg)](https://svelte.dev/)
[![Tests Passing](https://img.shields.io/badge/tests-228%20passed-success.svg)](#running-tests)
[![Strict Mypy](https://img.shields.io/badge/mypy-strict%20clean-blueviolet.svg)](#code-quality)
[![Privacy First](https://img.shields.io/badge/PII-Zero%20Storage-brightgreen.svg)](#zero-pii-architecture)

> **Autonomous on-device edge intelligence for shopper traffic, checkout queue congestion, and shelf depletion monitoring.** Designed for high-latency, offline, or low-bandwidth Tier-2/Tier-3 retail stores.

---

## Architecture Overview

The system runs entirely locally on edge compute (development laptop, Raspberry Pi 4B, or NVIDIA Jetson) using commodity RTSP camera feeds (IP cameras, ESP32-CAM, or phone cameras).

```
   Phone / CCTV (RTSP/USB)
              │
              ▼
    [ CameraSource (cv2) ]
              │  (Native FPS decoupled frame slot)
              ├──────────────────────────────────┐
              ▼                                  ▼
    [ _inference_loop (5 FPS) ]        [ _capture_loop (15+ FPS) ]
              │                                  │
    ┌─────────┴─────────┐                        ▼
    ▼                   ▼              [ MJPEG Video Streamer ]
[ YOLO26n (ONNX) ]  [ Shelf ROI ]                │
    │                   │                        ▼
[ ByteTrack ]           │             Web Dashboard (/app)
    │                   │
    ├─────────┬─────────┴─────────┐
    ▼         ▼                   ▼
 Footfall   Dwell / Heatmap     Queues
    │         │                   │
    └─────────┼───────────────────┘
              ▼
      [ AlertEngine ]
              │
              ▼
   [ SQLite (retail.db) ] ──▶ REST API (FastAPI) ──▶ Svelte Dashboard
```

---

## Key Features

1. **Footfall & Directional Occupancy**:
   - Virtual tripwire & polygon boundary crossing (`entry_exit`).
   - Net store occupancy tracking with cumulative enters and exits.
2. **Checkout Queue Monitoring**:
   - Real-time queue depth calculation per register counter.
   - Autonomous congestion alerts (`>4 persons` threshold) recommending counter openings.
3. **Shelf Stock Depletion**:
   - Hybrid CV analysis: HSV color variance + Sobel edge density.
   - Occlusion filtering (disregards shelf changes when shoppers are reaching).
   - Generates replenishment alerts for `low` or `empty` shelves.
4. **Customer Dwell & Spatial Heatmaps**:
   - Heatmap accumulation using feet anchor positions (bottom-center of bounding boxes).
   - Gaussian spatial density clustering across customizable retail zones.
5. **Zero-PII Compliance**:
   - No raw frames, facial crops, or biometrics are ever stored on disk or in database.
   - Tracking IDs are anonymous, temporary, and discarded upon zone exit.
6. **Decoupled Architecture**:
   - Hardware capture, YOLO inference, and UI MJPEG streaming run on separate threads.
   - Camera disconnects trigger non-blocking exponential backoff with zero backend freezing.

---

## Hardware Substitution Story (SIH26179)

| Production Target | POC Substitute | Portability Guarantee |
| :--- | :--- | :--- |
| **NVIDIA Jetson Orin Nano / NX** | Standard Laptop CPU / Raspberry Pi 4B | `InferenceBackend` interface wraps ONNX Runtime. Model path exports directly to TensorRT engines with zero code changes. |
| **Store CCTV Cameras** | Phone Camera (RTSP via IP Webcam) | `CameraSource` interface ingests RTSP, USB, or CSI identically. |
| **Retail ERP / POS** | SQLite Local Buffer + REST Endpoints | Events buffered locally in SQLite (`retail.db`) and synced upstream via buffered HTTP batches. |

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend dashboard)
- `uv` (recommended) or `pip`

### 2. Backend Installation

```bash
# Clone the repository
git clone https://github.com/dakshshah2099/EdgeRetailAI.git
cd EdgeRetailAI/backend

# Create virtual environment and install dependencies
uv sync --all-extras
# or: pip install -r requirements.txt
```

### 3. Frontend Dashboard Setup

```bash
cd ../frontend
npm install
npm run build
```
*(The production build outputs to `frontend/dist` and is automatically served by FastAPI at `/app`)*

### 4. Configuration

Copy the example configuration:
```bash
# From repository root
cp backend/.env.example backend/.env
```

Edit `backend/.env` according to your camera and deployment setup:

```env
CAMERA_SOURCE=rtsp://192.168.1.100:8080/h264_pcm.sdp
DEBUG_MODE=true
HOST=0.0.0.0
PORT=8000
```

### 5. Launch Application

```bash
# From backend directory
python -m api.main
# or: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Dashboard**: [http://localhost:8000/app](http://localhost:8000/app)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Environment Variables Reference

| Variable | Default (Dev) | Default (Pi) | Description & Recommendation |
| :--- | :---: | :---: | :--- |
| `DEBUG_MODE` | `true` | `true` | Allows zone calibration and `.env` editing from the UI. Set `false` in production. |
| `CAMERA_SOURCE` | `rtsp://...` | `0` | Camera input. Use `rtsp://<ip>:<port>/<path>` for phone/IP camera, `0` for USB webcam, or path to MP4 video. |
| `RTSP_USERNAME` | *blank* | *blank* | RTSP camera authentication username. Leave blank if unauthenticated. |
| `RTSP_PASSWORD` | *blank* | *blank* | RTSP camera authentication password. Leave blank if unauthenticated. |
| `RTSP_TRANSPORT` | `tcp` | `tcp` | RTSP network transport (`tcp` or `udp`). `tcp` recommended for Wi-Fi reliability. |
| `YOLO_MODEL` | `models/yolo26n.onnx` | `models/yolo26n_int8.onnx` | Path to ONNX weights. Use INT8 quantized model on Raspberry Pi. |
| `YOLO_INPUT_SIZE` | `640` | `640` | YOLO image input dimension. Use `640` or `320` (for ultra-low-power edge). |
| `YOLO_INFERENCE_FPS` | `5.0` | `5.0` | Execution rate limit for background AI detection loop (conserves CPU). |
| `YOLO_INTRA_OP_THREADS` | `3` | `3` | ONNX CPU worker thread count. On quad-core, use `3` to leave 1 core free for OS and capture. |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.50` | `0.40` | Person detection confidence cutoff (0.10–0.95). |
| `LOW_STOCK_CONFIDENCE_THRESHOLD` | `0.60` | `0.60` | Empty shelf detection confidence cutoff (0.10–0.95). |
| `SHELF_ANALYSIS_INTERVAL` | `1.0` | `1.0` | Seconds between shelf status re-evaluations. |
| `QUEUE_CONGESTION_LENGTH` | `4` | `4` | Person count inside checkout zone before triggering congestion alert. |
| `FOOTFALL_TRACKER_MODE` | `directional` | `directional` | Counter mode (`directional` vector crossings or `edge` ROI entry). |
| `FOOTFALL_EMIT_ON` | `zone_enter` | `zone_enter` | Event emission trigger (`zone_enter` or `zone_exit`). |
| `HEATMAP_CELL_SIZE` | `20` | `20` | Spatial grid cell size in pixels. Optimal is `20` for 480p/VGA feeds. |
| `DATABASE_PATH` | `retail.db` | `retail.db` | Path to local SQLite database. |
| `CONFIG_PATH` | `config.yaml` | `config.yaml` | Path to zone polygon coordinates file. |
| `HOST` | `127.0.0.1` | `0.0.0.0` | Server bind host. Use `0.0.0.0` to access dashboard across local LAN. |
| `PORT` | `8000` | `8000` | HTTP port for REST API and web UI. |
| `POLLING_INTERVAL_SEC` | `3` | `3` | Dashboard telemetry auto-refresh interval in seconds. |

---

## Phone IP Webcam (480p) Optimal Configuration

When using an Android/iOS smartphone running **IP Webcam** at **640x480 (480p)**:

```env
# Network RTSP Feed
CAMERA_SOURCE=rtsp://192.168.1.X:8080/h264_pcm.sdp
RTSP_USERNAME=
RTSP_PASSWORD=
RTSP_TRANSPORT=tcp

# Inference & Detection
YOLO_MODEL=models/yolo26n.onnx
YOLO_INPUT_SIZE=640
YOLO_INFERENCE_FPS=5.0
YOLO_INTRA_OP_THREADS=3
DETECTION_CONFIDENCE_THRESHOLD=0.45

# Analytics for 480p Resolution
HEATMAP_CELL_SIZE=20
LOW_STOCK_CONFIDENCE_THRESHOLD=0.60
QUEUE_CONGESTION_LENGTH=4
SHELF_ANALYSIS_INTERVAL=1.0

# Server
DEBUG_MODE=true
HOST=0.0.0.0
PORT=8000
```

> **Tip**: In IP Webcam app settings, select **Video resolution: 640x480**, **Video encoder: H.264**, and leave login/password disabled for simplest local streaming.

---

## Hardware Benchmarks & Substitution Evidence

Benchmarking performed on YOLO26n comparing development laptop baseline against published edge silicon:

| Device | Precision | Latency (Mean) | Published / Measured FPS | Storage Size |
| :--- | :---: | :---: | :---: | :---: |
| **Development Host (Laptop)** | FP32 | 28.73 ms | **34.81 FPS** *(measured)* | 9.48 MB |
| **Development Host (Laptop)** | INT8 | 48.81 ms | **20.49 FPS** *(measured)* | 2.77 MB (-70.8%) |
| **Raspberry Pi 4B (8GB)** | INT8 | ~117 ms | **8.5 FPS** *(published)* | 2.77 MB |
| **NVIDIA Jetson Orin Nano (4GB)** | TensorRT INT8 | ~20 ms | **48.0 FPS** *(published)* | ~3 MB |
| **NVIDIA Jetson Orin Nano (8GB)** | TensorRT INT8 | ~10 ms | **95.0 FPS** *(published)* | ~3 MB |
| **Raspberry Pi 5 + Hailo-8L** | HailoRT INT8 | ~6.6 ms | **150.0 FPS** *(published)* | ~3 MB |

*For complete benchmarking methodology, thermal analysis, and citations, see [BENCHMARK_REPORT.md](file:///E:/Coding/Projects/EdgeRetailAI/BENCHMARK_REPORT.md).*

---

## Code Quality & Testing

The repository enforces strict typing and linting standards across all Python code:

```bash
cd backend

# Run full test suite (228 tests)
pytest

# Strict type checking (0 errors)
mypy --strict .

# Lint check (0 warnings)
ruff check .
```

---

## License

Developed for **Smart India Hackathon (SIH26179)** under Qualcomm Inc problem statement. Distributed under the MIT License.
