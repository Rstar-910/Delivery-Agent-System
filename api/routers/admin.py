"""
routers/admin.py — Admin reporting endpoint.

Requires the `admin` role. Returns a full tabular report of all orders plus a
status-wise aggregate summary — mirroring the C++ generateReport() output in
structured JSON form.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_admin
from ..database import get_db
from ..models import OrderResponse, ReportResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/report",
    response_model=ReportResponse,
    summary="Generate a full delivery report with status summary (Admin only)",
)
def get_report(_: dict = Depends(require_admin)):
    """
    Returns all orders sorted by order_id, the total count, and a breakdown
    of how many orders are in each status. Equivalent to the C++ generateReport()
    function but structured as JSON for programmatic consumption.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT order_id, customer_name, address, status, scheduled_date "
            "FROM orders ORDER BY order_id"
        ).fetchall()

    orders = [OrderResponse(**dict(row)) for row in rows]

    status_summary: dict[str, int] = {}
    for order in orders:
        status_summary[order.status] = status_summary.get(order.status, 0) + 1

    return ReportResponse(
        orders=orders,
        total=len(orders),
        status_summary=status_summary,
    )
