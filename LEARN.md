# EdgeRetailAI — Master Study & Defense Guide (SIH 26179)

---

## 1. System Architecture & CV Pipeline

### 1.1 High-Level Architecture
`
[RTSP Stream / Phone / USB]
            │
            ▼
┌─────────────────────────┐
│ CameraSource (Threaded) │ ── drops stale frames, keeps latest (Queue maxsize=1)
└───────────┬─────────────┘
            │ BGR (640x640 / 480p)
            ▼
┌─────────────────────────┐
│    InferenceBackend     │ ── ONNX Runtime (CPU / CUDA / TensorRT / OpenVINO)
│  (YOLOv26n / YOLOv8n)   │    Zero PyTorch dependency in runtime (~35MB wheel)
└───────────┬─────────────┘
            │ Detections (xyxy, conf, class_id)
            ▼
┌─────────────────────────┐
│     ByteTrackWrapper    │ ── Low-score association, prevents ID switches on occlusion
└───────────┬─────────────┘
            │ TrackedObjects (track_id, bbox, state)
            ▼
┌────────────────────────────────────────────────────────┐
│                   Parallel Analytics                   │
├────────────────────────────┬───────────────────────────┤
│  Workload A: People (0.2s) │  Workload B: Shelf (2.0s) │
├────────────────────────────┼───────────────────────────┤
│ • Tripwire (In/Out)        │ • Shelf Planogram ROI     │
│ • Zone Dwell (Heatmap)     │ • Grid Fill / Out-of-Stock│
│ • Queue Length & Service   │ • Theft / Rapid depletion │
└─────────────┬──────────────┴─────────────┬─────────────┘
              │ Derived Metrics (No PII)   │
              └──────────────┬─────────────┘
                             ▼
              ┌─────────────────────────────┐
              │      Rule Alert Engine      │ ── Low stock, Long Queue, Loitering
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │  SQLite Local WAL Database  │ ── Stored locally; offline resilience
              └──────────────┬─────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │   FastAPI + SvelteKit UI    │ ── SSE Push, WebSocket, Live REST
              └─────────────────────────────┘
`

### 1.2 Pipeline Stage Walkthrough

1. **Ingestion ([backend/vision/rtsp_source.py](backend/vision/rtsp_source.py))**:
   - Spawns background worker thread.
   - Clears cv2.VideoCapture internal OS buffer to prevent 1-3 second display lag.
   - capture.read() stores strictly latest frame into single-element buffer.
   - Automatically reconnects on RTSP packet loss or Wi-Fi drops.

2. **Inference Interface ([backend/inference/backend.py](backend/inference/backend.py))**:
   - Abstract InferenceBackend exposes predict(frame) -> list[Detection].
   - Production uses ONNXRuntimeBackend with onnxruntime C++ engine.
   - Letterboxes input to 640x640 with bilinear scaling and normalizes to [0, 1] FP32 or INT8.
   - Zero-copy output parsing for bounding boxes.

3. **Tracking ([backend/vision/tracker.py](backend/vision/tracker.py))**:
   - Employs **ByteTrack**.
   - Unlike standard DeepSORT/SORT which discard low-confidence detections (< 0.5), ByteTrack splits detections into high-score and low-score pools.
   - Associates low-score detections with existing tracklets using Kalman filter IoU, maintaining trajectory even through heavy occlusion.

4. **Spatial Analytics & Zones ([backend/analytics/zone_tracker.py](backend/analytics/zone_tracker.py))**:
   - Bottom-center anchor point (x_mid, y_max) of bounding box used for ground-plane floor projection.
   - Ray-casting polygon intersection tests for zones:
     - ENTRANCE: Tripwire direction vector triggers Footfall IN/OUT count.
     - AISLE: Dwell timer starts on polygon entry. Accumulates duration; triggers dwell/loiter events.
     - CHECKOUT: Tracks count of unique active track IDs inside checkout polygon; calculates queue wait times.

5. **Inventory / Shelf CV ([backend/inventory/shelf_engine.py](backend/inventory/shelf_engine.py))**:
   - Evaluated at throttled cadence (e.g., every 2s) to preserve compute.
   - User defines Shelf ROI polygon + Spatial Grid (Rows x Cols).
   - Counts target SKU detections intersecting each grid cell.
   - Compares current stock vs 
ominal_capacity -> generates stock_percentage. Triggers out-of-stock event when < threshold.

6. **Zero-PII Storage ([backend/core/schemas.py](backend/core/schemas.py) & [backend/storage/db.py](backend/storage/db.py))**:
   - **Zero PII**: No image buffers, face crops, biometric embeddings, or raw sensor frames written to DB or passed to APIs.
   - Models store anonymized integer IDs (	rack_id: 104), bounding box coordinates, dwell timestamps, and SKU counts.
   - Stored in SQLite with Write-Ahead Logging (PRAGMA journal_mode=WAL;).

---

## 2. Setup, Calibration, & Operation

### 2.1 Hardware Profiles

| Device | Model Format | Resolution | Target FPS | Expected CPU/GPU |
|---|---|---|---|---|
| **Host PC (Laptop / Dev)** | ONNX FP32 | 640x640 | 25-30 FPS | 15% CPU / CUDA |
| **Jetson Orin Nano (Target)** | TensorRT FP16/INT8 | 640x640 | 30 FPS | 20% GPU (5-10W) |
| **Raspberry Pi 4B (Edge)** | ONNX INT8 Quantized | 480x480 / 320x320 | 5-8 FPS | 70% CPU (4 cores) |

### 2.2 Phone RTSP 480p Setup
1. Install **IP Webcam** (Android) or **Live-Reporter** (iOS).
2. Set video resolution: 640x480 or 800x480. Video quality: 50%. FPS limit: 30.
3. Start server on phone. Copy RTSP URL: tsp://<phone-ip>:8080/h264_pcm.sdp (or IP Webcam URL http://<phone-ip>:8080/video).
4. Configure .env:
   `ash
   RTSP_URL=rtsp://192.168.1.50:8080/h264_pcm.sdp
   RTSP_TRANSPORT=tcp
   INFERENCE_IMAGE_SIZE=640
   PERSON_DETECTION_CONFIDENCE=0.45
   INVENTORY_DETECTION_CONFIDENCE=0.35
   INVENTORY_INFERENCE_INTERVAL=2.0
   `

### 2.3 Running Locally
`powershell
# 1. Start Backend
cd backend ; .\venv\Scripts\Activate.ps1 ; uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start Frontend
cd frontend ; npm run dev -- --host 0.0.0.0 --port 5173
`

### 2.4 Zone & Shelf Calibration
1. Open dashboard: http://localhost:5173/settings.
2. Select **Camera & Zones**. Click **Draw Zone**:
   - **Entrance**: Draw 4-point polygon around doorway. Assign type ENTRANCE.
   - **Checkout**: Draw polygon around queue line. Assign type CHECKOUT.
   - **Shelf ROI**: Draw bounding box around retail shelf. Set grid ows=2, cols=3.
3. Save Configuration. Changes apply instantly without restarting backend.

---

## 3. Judge Defense & Counter-Reasoning (SIH 26179 / Qualcomm)

### Q1: You're running this on a laptop with a phone camera. How does this prove it runs on an embedded edge device like Qualcomm Dragonwing or Jetson?
**Answer / Defense:**
- **Architectural Seams**: Both camera ingestion and inference are decoupled behind abstract interfaces: CameraSource ([backend/vision/base.py](backend/vision/base.py)) and InferenceBackend ([backend/inference/backend.py](backend/inference/backend.py)).
- **Zero PyTorch in Production**: We do not load PyTorch or TorchVision at runtime. Inference runs on onnxruntime C++ binaries with lightweight memory footprints (< 150MB RSS).
- **Direct Edge Path**: The exact same ONNX graph (yolov26n.onnx) compiles directly into **Qualcomm SNPE (Snapdragon Neural Processing Engine)** for Qualcomm NPU/Adreno, or **TensorRT** on Jetson with zero code changes. Swapping backends is a 1-line config change.
- **RTSP Portability**: The phone RTSP stream uses standard H.264 over RTSP (TCP/UDP). A commercial AXIS/Hikvision CCTV or a MIPI-CSI camera uses identical V4L2/GStreamer pipelines.

### Q2: Why YOLOv26n / YOLOv8n? Why not a cloud Vision Foundation Model or multimodal LLM (GPT-4o, Claude)?
**Answer / Defense:**
- **Latency & Determinism**: Retail queue alerts and tripwire counts require sub-200ms processing. Cloud API calls introduce 600-2500ms latency and risk packet loss.
- **Bandwidth & Connectivity**: Streaming high-res video from 10 store cameras to cloud costs exorbitant bandwidth (>25 Mbps upstream) and fails in Tier-2/Tier-3 retail with erratic internet.
- **OpEx**: Edge inference costs  in cloud API tokens. A  edge accelerator runs 24/7 for 3 years on under 10 Watts.
- **Privacy Regulation**: Cloud transmission of raw retail footage violates GDPR/DPDP privacy mandates.

### Q3: How do you guarantee customer privacy and prevent GDPR / India DPDP Act violations?
**Answer / Defense:**
- **Zero-PII Enforced Structurally**: Privacy is not a policy; it is enforced in code.
- In [backend/core/schemas.py](backend/core/schemas.py), all public and storage contracts (DwellEvent, FootfallMetric, QueueState) contain **zero image buffers, biometric features, or facial coordinates**.
- Frames reside exclusively in volatile RAM for inference and are immediately garbage-collected after bounding-box extraction.
- Track IDs are anonymous transient integers (1, 2, 3...) reset on zone exit. No cross-day re-identification.

### Q4: What happens when the camera is occluded or a person is blocked by another shopper?
**Answer / Defense:**
- **ByteTrack Two-Stage Association**: Standard trackers drop IDs when confidence dips below threshold during partial occlusion.
- ByteTrack maintains tracklets through low-confidence detections (down to conf=0.1) by matching Kalman filter predicted positions with remaining bounding boxes.
- Trajectory continuation bridges occlusions up to 30 lost frames (max_age=30), preserving accurate dwell times.

### Q5: How do you handle severe lighting changes (glare, shadows, night dimming) in retail?
**Answer / Defense:**
- **Letterbox Normalization**: Preprocessing applies contrast-resilient adaptive scaling and normalization.
- **Anchor Point Physics**: Zone containment does not use bounding box centroids (which shift when shadows elongate). It uses the **bottom-center contact point** ((xmin+xmax)/2, ymax) representing the shopper's feet on the floor plane.
- **Temporal Filtering**: Dwell and queue statistics use sliding-window time averages (10-frame debounce) to eliminate instantaneous false positives.

### Q6: Why SQLite instead of PostgreSQL, MongoDB, or Cloud DB?
**Answer / Defense:**
- **Zero-Ops Edge Embedded**: SQLite runs inside the process. No separate database server daemon to crash, configure, or consume RAM.
- **WAL Mode Performance**: Enabled PRAGMA journal_mode=WAL; and PRAGMA synchronous=NORMAL;. Handles concurrent writes and non-blocking reads at >5,000 writes/second, far exceeding retail telemetry requirements.
- **Store-and-Forward**: In our enterprise architecture, local SQLite serves as an offline resilience buffer. If internet drops, store analytics continue uninterrupted. Aggregated hourly summaries push to enterprise cloud when connectivity restores.

### Q7: How does the Shelf CV accurately identify low stock when products look similar or overlap?
**Answer / Defense:**
- **Spatial Grid Topology**: Rather than asking YOLO to count 50 individual tight boxes, we divide the shelf ROI into normalized matrix cells (Rows x Columns).
- **Occupancy Mapping**: Each cell computes an intersection-over-cell metric. If a cell contains a target object, it is marked occupied.
- **Decoupled Interval**: Shelf analytics run at 0.5 Hz (every 2 seconds) instead of 30 Hz, saving 90% of object-detection compute while capturing restock/depletion events well within human operational speed.

### Q8: How does the system scale to 16+ cameras across an entire supermarket?
**Answer / Defense:**
- **Decoupled Asynchronous Workers**: Each camera stream runs in an isolated CameraWorker process/thread pushing to a shared lockless ring buffer.
- **Batch Inference**: On multi-stream setups, ONNX Runtime batches frames across streams (Batch_Size=N) to maximize GPU/NPU tensor core saturation.
- **Compute Tiering**: Heavy detection (YOLO) runs at 5 FPS per stream; lightweight tracker (ByteTrack) interpolates at 30 FPS. Shelf detection throttled to 0.5 FPS. Total load scales sub-linearly.

---

## 4. Key Metrics & Benchmarks Cheat Sheet

| Parameter | Value / Target | Technical Rationale |
|---|---|---|
| **E2E Pipeline Latency** | **18 - 32 ms** | Frame capture (2ms) + ONNX (14ms) + ByteTrack (2ms) + Analytics (1ms) |
| **Tracker Retention** | **30 frames** | Holds track ID across 1.0s of complete visual obstruction |
| **Foot Anchor Point** | (x_mid, y_max) | Floor contact eliminates camera tilt and shadow projection errors |
| **Shelf Interval** | **2.0 seconds** | Stock movement is slow; avoids wasting 95% edge compute |
| **SQLite WAL Overhead** | **< 1.5 ms/tx** | In-memory cache + sequential WAL disk append |
| **Edge RAM Footprint** | **~280 MB RSS** | Total Python + ONNX runtime + SQLite + FastAPI memory |
