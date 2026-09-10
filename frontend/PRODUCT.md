# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Store operations engineers, loss-prevention leads, and retail shift supervisors monitoring real-time store telemetry, queue congestion, out-of-stock shelves, and shopper movement patterns on local networks.

## Product Purpose

An edge-AI retail analytics operator console that transforms raw on-device computer vision feeds (RTSP/CCTV) into actionable, real-time store intelligence (footfall tracking, queue length alerts, shelf stock depletion, dwell heatmaps) with zero cloud dependency and strict privacy protection.

## Positioning

Operates entirely on local edge compute (e.g. Jetson Orin / on-prem edge node) using quantized ONNX Runtime inference, processing computer vision locally and transmitting only lightweight metadata and alerts. Zero PII, zero facial recognition, zero raw frames stored.

## Operating Context

- Edge hardware setup (Jetson or dev laptop substitute) connected to local CCTV or RTSP camera streams.
- Control room / back-office wallboards and floor associate mobile/tablet devices.
- Network environments with intermittent or zero internet connectivity (Tier-2/Tier-3 retail resilient).

## Capabilities and Constraints

- **Real-time Live Monitoring**: Live stream rendering with active zone boundaries and bounding box overlays.
- **Queue Intelligence**: Queue occupancy tracking, wait time estimation, and checkout counter opening recommendations.
- **Inventory Depletion Monitoring**: Shelf vacancy rate tracking and stock replenishment alert dispatches.
- **Footfall & Heatmaps**: Hourly/daily customer counts, directional flow, and spatial dwell heatmaps.
- **Strict Privacy Rule**: Anonymous detection only; no raw frames, face crops, or biometric embeddings are persisted or displayed.
- **Sub-second Alert Triage**: Acknowledge, inspect, and dismiss operational alerts.

## Brand Commitments

- **Name**: EdgeRetail AI (SIH26179)
- **Tone**: Precision industrial, utilitarian, calm under operational stress, high-contrast readability.

## Evidence on Hand

- Problem Statement: SIH26179 (Qualcomm Inc).
- Canonical architecture: docs/CONTEXT.md.
- Active edge API endpoints: src/lib/api.js (/kpi/footfall, /kpi/queue, /kpi/stock, /alerts, /heatmap).

## Product Principles

1. **Edge-first Resilience**: The interface and alert feed remain fully functional during cloud or internet outages.
2. **Zero PII by Architecture**: Privacy is non-negotiable; telemetry conveys aggregate counts and anonymized vectors only.
3. **Operational Clarity**: High-density information hierarchy prioritizing anomaly detection and immediate action over marketing aesthetics.
4. **Latency Honesty**: Display clear edge-health signals, stream framerate, and telemetry refresh intervals.
