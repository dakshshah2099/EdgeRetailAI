# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React 19 + Vite (HTML5 History API routing, 2026 standards)

## Users

- **Primary:** Retail store managers and branch operations supervisors managing on-floor staffing, queue bottlenecks, and inventory replenishment in real time.
- **Evaluators:** Technical competition judges (SIH26179) assessing on-device edge AI reliability, latency, privacy guarantees, and hardware portability.

## Product Purpose

An Intelligent Retail Analytics System that transforms ordinary CCTV/phone camera streams into actionable operational intelligence (shopper traffic, dwell heatmaps, checkout queue wait times, and shelf stock depletion) entirely at the edge without cloud bandwidth overhead or PII storage.

## Positioning

True edge-native retail analytics: all computer vision (YOLO26n person detection, ByteTrack tracking, ROI shelf vacancy classification) and event persistence run locally on edge hardware (laptop / Jetson) with zero external cloud dependencies and structural privacy protection (no raw frames or identity embeddings stored).

## Operating Context

- **Environment:** High-paced retail backoffices and store manager desks (well-lit environments), as well as live competitive demo stages.
- **Usage Scene:** Single-viewport high-density command center operating continuously on local Wi-Fi / hotspot, displaying live polling updates (every 2–5s) with immediate visual warnings for congestion and stockouts.

## Capabilities and Constraints

- **Capabilities:**
  - Real-time customer footfall counting (enters, exits, net in-store occupancy) with hourly/daily trend buckets.
  - Checkout queue length tracking, congestion threshold alerts, and wait-time forecasting.
  - Shelf vacancy/depletion status monitoring (`ok`, `low`, `empty`) with classifier confidence scoring.
  - 2D numeric traffic & dwell heatmap visualization dynamically scaled to camera viewport geometry.
  - Live alerts feed with severity categorization (critical, warning, info) and resolution lifecycle.
  - Embedded system debug console for on-the-fly `.env` and camera source switching.
- **Constraints:**
  - Strict privacy: No raw camera frames, face crops, or personal identity data persisted to disk or DB.
  - Edge isolation: Must operate fully during internet disruptions with local SQLite database store.

## Brand Commitments

- **Tone & Identity:** Crisp, authoritative, highly professional enterprise operations command center.
- **Visual Direction:** High-legibility enterprise light theme with slate/neutral foundations, high-contrast semantic indicators (Emerald green for normal, Amber for warning, Crimson for critical), and clean tabular and metric hierarchy.

## Evidence on Hand

- Slices 0 through 8 merged: contracts in `schemas.py`, local SQLite storage in `storage/repository.py`, FastAPI backend in `api/`, and Svelte dashboard in `dashboard/`.
- Pre-trained and exported edge ONNX model `models/yolo26n.onnx`.

## Product Principles

1. **Information Density with Zero Clutter:** Operators should assess whole-store health in 3 seconds; key numbers, congestion alerts, and heatmaps must remain visible without deep navigation.
2. **Actionable Over Decorative:** Visual indicators exist to drive floor action (open a counter, restock a shelf), not just display raw telemetry.
3. **Local Sovereignty:** The UI reflects purely local edge truth with clear connectivity and sync status.
4. **Legibility First:** High-contrast, well-structured tabular and metric components tailored for bright enterprise monitors.

## Accessibility & Inclusion

- WCAG AA color contrast compliance for text and operational status badges against clean light backgrounds.
- Semantic HTML tags, focus indicators for keyboard navigation, and explicit aria labels for status indicators and icon buttons.
