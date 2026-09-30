import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query

from api.dependencies import RepoDep
from api.routes.ws import ws_manager
from api.schemas_api import (
    ConversionSummary,
    POSTransactionRequest,
    POSTransactionResponse,
    ProductInteractionDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pos", tags=["pos", "conversion"])


@router.post("/transactions", response_model=POSTransactionResponse)
def record_pos_transaction(req: POSTransactionRequest, repo: RepoDep) -> POSTransactionResponse:
    """Ingest a real or webhook-driven POS transaction.

    Saves sales records, updates conversion calculations, and notifies clients via WebSockets.
    """
    ts = req.timestamp or datetime.now(UTC)
    item_count = sum(item.quantity for item in req.items) if req.items else 1
    total_amount = req.total_amount
    if total_amount is None and req.items:
        total_amount = sum(
            (item.price or 0.0) * item.quantity
            for item in req.items
            if item.price is not None
        )

    items_data = [item.model_dump() for item in req.items]
    repo.save_pos_transaction(
        transaction_id=req.transaction_id,
        timestamp=ts,
        item_count=item_count,
        total_amount=total_amount,
        payment_status=req.payment_status,
        items=items_data,
    )

    ws_manager.broadcast_sync({
        "type": "pos_transaction",
        "transaction_id": req.transaction_id,
        "item_count": item_count,
        "total_amount": total_amount,
    })

    return POSTransactionResponse(
        status="ok",
        transaction_id=req.transaction_id,
        item_count=item_count,
        total_amount=total_amount,
    )


@router.get("/transactions")
def list_pos_transactions(
    repo: RepoDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict[str, Any]]:
    """Retrieve recent recorded POS transactions."""
    return repo.get_recent_pos_transactions(limit=limit)


@router.get("/conversion", response_model=ConversionSummary)
def get_conversion_kpi(repo: RepoDep) -> ConversionSummary:
    """Compute store conversion rate (purchases / total enters) and basket stats."""
    transactions = repo.get_recent_pos_transactions(limit=1000)
    total_tx = len(transactions)

    # Footfall enters count from detection events
    total_footfall = 0
    try:
        from storage.db import get_connection
        c = get_connection(repo.db_path)
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM detection_events WHERE event_type = 'enter'")
        row = cur.fetchone()
        if row:
            total_footfall = int(row[0])
        c.close()
    except Exception as e:
        logger.debug("Failed querying total footfall: %s", e)

    total_revenue = sum(t.get("total_amount") or 0.0 for t in transactions)
    avg_basket = (
        sum(t.get("item_count") or 0 for t in transactions) / total_tx if total_tx > 0 else 0.0
    )
    denom_footfall = max(1, total_footfall)
    conversion_rate = (
        min(1.0, float(total_tx) / float(denom_footfall)) if total_footfall > 0 else 0.0
    )

    interactions = repo.get_recent_product_interactions(limit=1000)
    total_interactions = len(interactions)
    denom_interact = max(1, total_interactions)
    pick_to_purchase = (
        min(1.0, float(total_tx) / float(denom_interact)) if total_interactions > 0 else 0.0
    )

    return ConversionSummary(
        total_footfall=total_footfall,
        total_transactions=total_tx,
        conversion_rate=round(conversion_rate, 4),
        total_revenue=round(total_revenue, 2),
        avg_basket_size=round(avg_basket, 2),
        product_pick_to_purchase_ratio=round(pick_to_purchase, 4),
    )


@router.get("/interactions", response_model=list[ProductInteractionDTO])
def get_product_interactions(
    repo: RepoDep,
    zone_id: Annotated[str | None, Query()] = None,
    sku_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[ProductInteractionDTO]:
    """Retrieve shopper-product physical interaction logs."""
    raw_interactions = repo.get_recent_product_interactions(
        limit=limit, zone_id=zone_id, sku_id=sku_id
    )
    return [
        ProductInteractionDTO(
            interaction_id=i["interaction_id"],
            track_id=i["track_id"],
            zone_id=i["zone_id"],
            sku_id=i["sku_id"],
            start_ts=i["start_ts"],
            end_ts=i["end_ts"],
            duration_sec=i["duration_sec"],
        )
        for i in raw_interactions
    ]
