"""
models.py — Pydantic request/response schemas for the Delivery Agent System API.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, examples=["customer1"])
    password: str = Field(..., min_length=1, examples=["pass123"])


class TokenResponse(BaseModel):
    token: str
    role: str
    username: str


# ── Orders ──────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    customer_name:  str = Field(..., min_length=1, examples=["Alice Smith"])
    address:        str = Field(..., min_length=1, examples=["123 Main St, Springfield"])
    scheduled_date: str = Field(
        ...,
        pattern=r"^\d{2}-\d{2}-\d{4}$",
        examples=["25-12-2025"],
        description="Delivery date in DD-MM-YYYY format",
    )


class OrderResponse(BaseModel):
    order_id:       int
    customer_name:  str
    address:        str
    status:         str
    scheduled_date: str


class RescheduleRequest(BaseModel):
    scheduled_date: str = Field(
        ...,
        pattern=r"^\d{2}-\d{2}-\d{4}$",
        examples=["10-01-2026"],
        description="New delivery date in DD-MM-YYYY format",
    )


# ── Courier ──────────────────────────────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(PickedUp|InTransit|Delivered)$",
        examples=["InTransit"],
        description="One of: PickedUp, InTransit, Delivered",
    )


class CourierDetailsRequest(BaseModel):
    company_name:    str   = Field(..., min_length=1, examples=["SpeedyShip Ltd."])
    contact_number:  str   = Field(..., min_length=1, examples=["9876543210"])
    location:        str   = Field(..., min_length=1, examples=["Mumbai"])
    packaging_price: float = Field(..., gt=0,  examples=[49.99])
    discount:        float = Field(..., ge=0, le=100, examples=[10.0])


# ── Admin ────────────────────────────────────────────────────────────────────

class ReportResponse(BaseModel):
    orders:         list[OrderResponse]
    total:          int
    status_summary: dict[str, int]
