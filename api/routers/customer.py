"""
routers/customer.py — Customer-facing order management endpoints.

All routes require the `customer` role (enforced via require_customer Depends).
Uses targeted UPDATE/INSERT statements rather than the C++ load-all-then-rewrite
pattern, so concurrent access from both the C++ app and the API server is safe
under SQLite WAL mode.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import require_customer
from ..database import get_db
from ..models import OrderCreate, OrderResponse, RescheduleRequest

router = APIRouter(prefix="/orders", tags=["Customer — Orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new delivery",
)
def book_delivery(req: OrderCreate, _: dict = Depends(require_customer)):
    """
    Creates a new order with status 'Booked'.
    Order ID is derived from MAX(order_id)+1 — consistent with the C++ app's
    getNextOrderId() logic and safe under SQLite's serialised write model.
    """
    with get_db() as conn:
        order_id: int = conn.execute(
            "SELECT COALESCE(MAX(order_id), 0) + 1 FROM orders"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO orders(order_id, customer_name, address, status, scheduled_date) "
            "VALUES(?, ?, ?, 'Booked', ?)",
            (order_id, req.customer_name, req.address, req.scheduled_date),
        )

    return OrderResponse(
        order_id=order_id,
        customer_name=req.customer_name,
        address=req.address,
        status="Booked",
        scheduled_date=req.scheduled_date,
    )


@router.get(
    "",
    response_model=list[OrderResponse],
    summary="View past orders for a customer",
)
def view_records(customer_name: str, _: dict = Depends(require_customer)):
    """Returns all orders for the given customer name, ordered by order ID."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT order_id, customer_name, address, status, scheduled_date "
            "FROM orders WHERE customer_name = ? ORDER BY order_id",
            (customer_name,),
        ).fetchall()

    return [OrderResponse(**dict(row)) for row in rows]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="View order status by ID",
)
def view_status(order_id: int, _: dict = Depends(require_customer)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT order_id, customer_name, address, status, scheduled_date "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found",
        )
    return OrderResponse(**dict(row))


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel an order",
)
def cancel_order(order_id: int, _: dict = Depends(require_customer)):
    """
    Cancels an order. Mirrors the C++ business rule: Delivered orders cannot
    be cancelled.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if row["status"] == "Delivered":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Delivered orders cannot be cancelled",
            )

        conn.execute(
            "UPDATE orders SET status = 'Cancelled' WHERE order_id = ?", (order_id,)
        )

    return {"message": f"Order {order_id} cancelled successfully"}


@router.patch(
    "/{order_id}/reschedule",
    response_model=OrderResponse,
    summary="Reschedule an order to a new date",
)
def reschedule_order(
    order_id: int,
    req: RescheduleRequest,
    _: dict = Depends(require_customer),
):
    """
    Updates the scheduled_date and sets status to 'Rescheduled'.
    Mirrors the C++ business rule: Cancelled or Delivered orders cannot be
    rescheduled.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found",
            )

        if row["status"] in ("Cancelled", "Delivered"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order cannot be rescheduled in its current state",
            )

        conn.execute(
            "UPDATE orders SET scheduled_date = ?, status = 'Rescheduled' WHERE order_id = ?",
            (req.scheduled_date, order_id),
        )

        updated = conn.execute(
            "SELECT order_id, customer_name, address, status, scheduled_date "
            "FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()

    return OrderResponse(**dict(updated))
