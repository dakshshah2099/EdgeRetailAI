# 01 — Multi-Class Detection & Tracker Expansion

**What to build:**
Upgrade detection and tracking from person-only filtering (`class_id == 0`) to multi-class retail detection (person, cart, and retail product classes) using the underlying YOLO ONNX model. Tracks must be class-tagged (`class_id`, `class_name`) and maintained across frames so downstream shelf, queue, and interaction pipelines receive typed detections.

**Blocked by:**
None — can start immediately

**Status:**
ready-for-agent

## Acceptance Criteria
- [ ] `PersonDetector` generalized to `RetailDetector` (or multi-class mode supported), preserving confidence and NMS threshold configurations.
- [ ] Bounding box detections preserve class labels and IDs (e.g. `person`, `cart`, `bottle`, `cup`, `can`, `box`, `product`).
- [ ] Tracker tracks multi-class objects without cross-class ID collision.
- [ ] Primary camera and mesh camera inference paths pass multi-class tracked detections into telemetry slots.
- [ ] Backward compatibility: footfall and queue monitoring continue filtering specifically for `person` class.
- [ ] Unit tests verify multi-class detection and tracking.
