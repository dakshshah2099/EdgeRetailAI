# 04 — Shopper-Product Spatio-Temporal Interaction Pipeline

**What to build:**
Correlate tracked person paths with shelf zones and product detections to establish shopper-product interactions. Detect when a customer dwells at a shelf, approaches a specific product display, and interacts with merchandise. Generate structured interaction events (`track_id`, `sku_id`, `zone_id`, `duration_sec`) to distinguish casual passersby from engaged buyers.

**Blocked by:**
01 — Multi-Class Detection & Tracker Expansion

**Status:**
ready-for-agent

## Acceptance Criteria
- [ ] Pipeline detects spatial proximity and temporal dwell between person tracks and shelf product zones.
- [ ] Generates `ProductInteractionEvent` records with customer track ID, targeted SKU, zone, and interaction duration.
- [ ] Interaction events persisted into `product_interactions` table in SQLite repository.
- [ ] Exposes API endpoint `GET /kpi/interactions` for aggregate customer engagement analytics.
- [ ] Unit tests verify interaction lifecycle (start, dwell duration, completion).
