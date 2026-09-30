# 03 — Object-Evidence Shelf Stock & Replenishment Quantities

**What to build:**
Upgrade shelf inventory evaluation from heuristic pixel/Sobel gradients to concrete object detection evidence. Count actual detected product objects and visible facings inside each shelf zone. Compare discrete counts against SKU replenishment thresholds to trigger `"low"` and `"empty"` stock events and alert notifications with exact facing quantities.

**Blocked by:**
02 — SKU-Aware Facing Slot Planogram Engine

**Status:**
ready-for-agent

## Acceptance Criteria
- [ ] Shelf stock evaluation incorporates detected product counts inside shelf zone boundaries.
- [ ] Facings and unit count metrics computed from discrete product detections with heuristic fallback.
- [ ] `StockEvent` and `AlertEngine` include exact visible item quantities and SKU labels.
- [ ] UI shelf stock cards in `StockInventory.svelte` display detected unit counts vs minimum threshold.
- [ ] Low-stock replenishment alerts triggered reliably on discrete count breaches.
