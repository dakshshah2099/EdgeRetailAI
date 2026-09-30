# 05 — Open POS REST/Webhook Gateway, Conversion Engine & Cashier Terminal

**What to build:**
Deliver a real, production-ready POS/ERP integration system. Implement live REST/Webhook endpoints to ingest actual transactions from physical barcode scanners, mobile POS apps, or external ERPs. Store transactions in SQLite, compute real-time conversion rates (`purchases / customer_enters`), basket sizes, and pick-to-purchase ratios. Provide a built-in interactive cashier checkout register in the dashboard to scan registered SKUs and trigger immediate sales.

**Blocked by:**
04 — Shopper-Product Spatio-Temporal Interaction Pipeline

**Status:**
ready-for-agent

## Acceptance Criteria
- [ ] Endpoints `POST /pos/transactions` and `POST /pos/webhook` receive, validate, and store real POS sales.
- [ ] Tables `pos_transactions` and `pos_transaction_items` added to SQLite schema and repository.
- [ ] Real-time conversion engine computes store conversion rate (`completed_transactions / footfall_enters`) and product pick-to-purchase metrics.
- [ ] `GET /kpi/conversion` returns time-bucketed conversion rates and average basket sizes.
- [ ] Outbound ERP webhook dispatches low-stock replenishment purchase orders.
- [ ] Svelte frontend includes a Cashier Checkout Register component allowing operator to ring up items and view live conversion updates.
- [ ] Unit and integration tests verify transaction ingestion, storage, and conversion math.
