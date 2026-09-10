---
name: EdgeRetail AI Console
description: Precision industrial command deck for real-time edge CV retail analytics (Light Operating Terminal)
colors:
  primary: "#0284c7"
  primary-hover: "#0369a1"
  neutral-bg: "#f8fafc"
  surface-base: "#ffffff"
  surface-card: "#ffffff"
  surface-hover: "#f1f5f9"
  border-subtle: "#e2e8f0"
  border-strong: "#cbd5e1"
  text-primary: "#0f172a"
  text-secondary: "#475569"
  text-muted: "#64748b"
  status-healthy: "#059669"
  status-warning: "#d97706"
  status-danger: "#e11d48"
  status-info: "#0284c7"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  caption:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "JetBrains Mono, Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  mono-sm:
    fontFamily: "JetBrains Mono, Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "normal"
rounded:
  sm: "3px"
  md: "6px"
  lg: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
---

## Overview

Precision industrial light terminal design system for EdgeRetail AI. Crisp paper-white canvas, slate-100/slate-50 structural panels, high-contrast dark text, tabular monospace telemetry, and saturated semantic status accents (emerald, amber, rose, sky).

## Colors

- **Base Surfaces**: Clean crisp canvas (#f8fafc), elevated panels & cards (#ffffff), subtle interactive hover (#f1f5f9).
- **Borders & Dividers**: Crisp structural lines (#e2e8f0), focused outlines (#0284c7).
- **Typography & Icons**: Deep slate (#0f172a), metadata secondary (#475569), subdued indicators (#64748b).
- **Telemetry Signals**:
  - Emerald (#059669): Nominal edge daemon, standard queues, healthy inventory.
  - Amber (#d97706): Warning threshold, queue surge, low stock.
  - Rose/Red (#e11d48): Critical alert, shelf out of stock, camera disconnect.
  - Sky/Cyan (#0284c7): Active camera stream, navigation focus, primary CTA.

## Typography

- **Primary UI**: Clean sans (Inter, system-ui).
- **Telemetry & Counts**: Tabular monospace (JetBrains Mono, Consolas, monospace) for metrics, timestamps, coordinate bounds, and zone IDs.

## Layout

- **Topology**: Persistent Collapsible Sidebar + Operational Command Deck.
  - Left Sidebar: Brand mark, navigation items with incident count badges, edge hardware telemetry readout.
  - Top Bar: System edge health pill, quick zone filter, time range picker, auto-refresh toggles.
  - Primary Viewport: Active stage (Live stream + incident triage, Heatmap, Footfall, Queues, Shelves, Config).

## Elevation & Depth

- Low subtle border layering with soft 1px borders (#e2e8f0) and clean card borders rather than heavy blur or fuzzy drop shadows.

## Shapes

- Clean technical radii: rounded-sm (3px) to rounded-md (6px).
