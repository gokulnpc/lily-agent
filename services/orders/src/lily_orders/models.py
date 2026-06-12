"""Typed I/O for the order tools (pydantic v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class OrderLookup(BaseModel):
    order_number: str
    email: str  # required pair (NFR-13); never look up by order number alone


class OrderItem(_Frozen):
    ps_number: str
    name: str
    unit_price_usd: float
    quantity: int


class OrderEvent(_Frozen):
    event_type: str
    occurred_at: datetime
    description: str | None = None


class OrderResult(_Frozen):
    # One uniform NOT_FOUND for no-such-order and wrong-email alike (anti-enumeration).
    status: Literal["FOUND", "ORDER_NOT_FOUND"]
    order_number: str | None = None
    order_status: str | None = None
    email_masked: str | None = None
    placed_at: datetime | None = None
    carrier: str | None = None
    tracking_number: str | None = None
    shipping_city: str | None = None
    shipping_region: str | None = None
    total_usd: float | None = None
    items: list[OrderItem] = []
    timeline: list[OrderEvent] = []


class ReturnRequest(BaseModel):
    order_number: str
    email: str
    reason: str
    order_item_id: int | None = None


class ReturnResult(_Frozen):
    status: Literal["CREATED", "ORDER_NOT_FOUND"]
    reference: str | None = None
