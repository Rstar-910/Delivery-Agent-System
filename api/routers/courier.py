"""
routers/courier.py — Courier service endpoints.

All routes require the `courier` role (enforced via require_courier Depends).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import require_courier
from ..database import get_db
from ..models import CourierDetailsRequest, OrderResponse, StatusUpdateRequest

router = APIRouter(tags=["Courier"])


@router.post(
    "/courier/details",
    status_code=status.HTTP_201_CREATED,
    summary="Register courier company details and pricing",
)
def register_courier(req: CourierDetailsRequest, _: dict = Depends(require_courier)):
    """Saves a new courier company entry to the courier_companies table."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO courier_companies"
            "(company_name, contact_number, location, packaging_price, discount) "
            "VALUES(?, ?, ?, ?, ?)",
            (
                req.company_name,
                req.contact_number,
                req.location,
                req.packaging_price,
                req.discount,
            ),
        )

    return {"message": "Courier details registered successfully"}


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="Update delivery status for an order",
)
def update_status(
    order_id: int,
    req: StatusUpdateRequest,
    _: dict = Depends(require_courier),
):
    """
    Sets the order status to one of: PickedUp, InTransit, Delivered.
    Only the courier role may call this endpoint (customers cannot self-deliver).
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT order_id FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (req.status, order_id),
        )

        updated = conn.execute(
            "SELECT order_id, customer_name, address, status, scheduled_date "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()

    return OrderResponse(**dict(updated))
