# 02 — SKU-Aware Facing Slot Planogram Engine

**What to build:**
Transform `planogram_lite.py` from fill-only grid checking into true SKU-aware planogram compliance. Each facing slot `(row, col)` in a shelf layout maps to an expected SKU (either per-facing or defaulting to the shelf's assigned SKU). The engine verifies that detected objects in each slot match the expected product profile; mismatched products are flagged as `"misplaced"`, missing items as `"empty"` / `"low"`, and only matching items as compliant.

**Blocked by:**
01 — Multi-Class Detection & Tracker Expansion

**Status:**
ready-for-agent

## Acceptance Criteria
- [ ] `FacingStatus` includes `detected_sku_id`, `detected_sku_name`, `expected_sku_id`, and `status: Literal["ok", "low", "empty", "misplaced"]`.
- [ ] `ExpectedLayout` supports per-facing expected SKU mapping.
- [ ] `score_planogram_compliance()` evaluates both spatial presence and SKU identity.
- [ ] Misplaced products are flagged and excluded from `compliance_ratio`.
- [ ] In-memory and SQLite cache reconstruct facing-level SKU states.
- [ ] Frontend `PlanogramCompliance.svelte` renders SKU labels, misplaced product alerts, and compliance score.
- [ ] Acceptance tests in `test_planogram_lite.py` pass.
