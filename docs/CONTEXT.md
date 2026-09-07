# CONTEXT.md — Project Context for Agents

## Problem statement (source: SIH26179, Qualcomm Inc)

Build an Intelligent Retail Analytics System using smart cameras and on-device
AI to monitor retail operations in real time — shopper movement, inventory
levels, checkout queues — without requiring constant cloud processing.
Inference happens locally (edge) for low latency, privacy, and resilience to
poor/no connectivity, common in Tier-2/Tier-3 Indian retail.

## Functional requirements (from problem statement, mapped to slices)

| # | Requirement | Slice(s) |
|---|---|---|
| FR1 | Count customers entering/exiting | Slice 2 |
| FR2 | Footfall trends by time/day/zone | Slice 2, 8 |
| FR3 | Dwell time near products/displays | Slice 3 |
| FR4 | Heatmap of movement patterns | Slice 3, 8 |
| FR5 | Detect low-stock / out-of-stock | Slice 4 |
| FR6 | Planogram compliance (stretch, not POC-critical) | Slice 4 (non-goal for POC) |
| FR7 | Alert staff on replenishment need | Slice 6 |
| FR8 | Monitor checkout queue length | Slice 5 |
| FR9 | Predict congestion | Slice 5, 6 |
| FR10 | Recommend opening counters | Slice 6 |
| FR11 | Measure avg wait/service time | Slice 5 |
| FR12 | Run all CV locally on edge hardware | Slice 1, 2 (architecture-wide) |
| FR13 | Operate during internet disruption | Slice 7 |
| FR14 | Reduce cloud bandwidth | Slice 7 (architecture-wide) |
| FR15 | Anonymous detection, no PII stored | Slice 0 (schema constraint), all slices |
| FR16 | Real-time alerts + dashboard + KPIs | Slice 6, 8 |
| FR17 | Scalable, POS/ERP integration | Out of scope for POC — noted for pitch only |

## POC hardware substitution (explicit, for judges)

- **Jetson substitute:** development laptop. Model path stays portable —
  ONNX Runtime now, TensorRT engine on real Jetson later, same model file,
  same `InferenceBackend` interface, backend swap only.
- **CCTV substitute:** phone camera via IP Webcam app, streamed over RTSP/MJPEG
  on local Wi-Fi. Same `CameraSource` interface will take a CSI/USB feed on
  real deployment hardware with no pipeline change.
- This substitution is stated openly in the pitch, not hidden. Slice 9
  produces the benchmark evidence (laptop fps vs published Jetson Orin
  Nano/NX specs) that backs the "drop-in replacement" claim.

## Architecture (POC)

```
Phone (IP Webcam, RTSP) ──▶ CameraSource ──▶ Frame queue
                                                  │
                          ┌───────────────────────┼───────────────────────┐
                          ▼                        ▼                        ▼
                 Detection/Tracking        Shelf classifier          Queue detector
                 (Slice 2/3, YOLOv8n)         (Slice 4)                  (Slice 5)
                          │                        │                        │
                          └───────────────────────┼───────────────────────┘
                                                  ▼
                                         Event stream (typed)
                                                  │
                                   ┌──────────────┼──────────────┐
                                   ▼                              ▼
                          Alert engine (Slice 6)          Local storage (Slice 7,
                                   │                          SQLite, buffered sync)
                                   └──────────────┬──────────────┘
                                                  ▼
                                     Dashboard API + UI (Slice 8)
```

## Key design decisions (locked for POC — revisit only with explicit discussion)

- **Language/runtime:** Python 3.11+ everywhere (CV + backend), single
  runtime to minimize agent context-switching across slices.
- **Backend:** FastAPI + SQLite. No Postgres/Redis for POC — adds ops
  overhead with no POC benefit.
- **Detection model:** YOLOv8n, exported ONNX, run via ONNX Runtime.
  Chosen for size/speed tradeoff suited to edge deployment.
- **Tracking:** ByteTrack (or equivalent lightweight tracker) for person
  IDs — anonymous, frame-to-frame only, never persisted as identity.
- **Frontend for POC demo:** Streamlit or a minimal static page is
  acceptable — judges care about the pipeline and numbers, not UI polish.
  Do not over-invest agent time in frontend framework choice.
- **Privacy:** No raw frames, face crops, or embeddings are ever persisted.
  Enforced at the schema level (Slice 0) — persisted models physically
  cannot carry an image field.
- **Data retention:** only aggregated/derived events (counts, durations,
  zone IDs, timestamps) go to SQLite.

## What "done" means for the POC as a whole

A live demo where: phone camera streams to laptop → footfall count updates
live → a person dwelling in a marked zone shows up in dwell/heatmap data →
an empty region of a shelf triggers a low-stock alert → a queue past
threshold triggers a counter-opening recommendation → all of this is visible
on a dashboard → and a benchmark report exists showing this pipeline's
resource use maps credibly onto Jetson-class hardware specs.

## Explicit non-goals for the POC (do not build)

- Full planogram/SKU-level compliance (needs product recognition, not just
  emptiness detection)
- Any authentication/user-management system
- Production-grade horizontal scaling, load balancing, containers-at-scale

## Open questions agents should flag, not silently resolve

- Exact zone polygon definitions (store layout) — placeholder config until
  real/demo footage is chosen.
- Threshold values for "low stock" and "queue congestion" — start with
  reasonable defaults in `config.yaml`, callable out as tunable.