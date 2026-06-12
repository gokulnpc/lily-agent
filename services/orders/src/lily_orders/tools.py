"""Order tools over the mock `commerce` schema (D18 — no real payments).
Injected psycopg connection; parameterized queries only."""

from __future__ import annotations

import psycopg

from lily_orders.models import (
    OrderEvent,
    OrderItem,
    OrderLookup,
    OrderResult,
    ReturnRequest,
    ReturnResult,
)

# Lookup requires order_number + email together (NFR-13). The query returns at
# most one row; a wrong email yields zero rows — indistinguishable from a missing
# order, which is the point (prevents order-number enumeration).
_ORDER_SQL = """
SELECT order_id, order_number, status, email, placed_at, carrier, tracking_number,
       shipping_city, shipping_region, total_usd
FROM commerce.orders
WHERE order_number_norm = catalog.norm_id(%(num)s) AND lower(email) = lower(%(email)s)
"""

_ITEMS_SQL = """
SELECT ps_number, name, unit_price_usd, quantity
FROM commerce.order_items WHERE order_id = %(oid)s ORDER BY order_item_id
"""

_EVENTS_SQL = """
SELECT event_type, occurred_at, description
FROM commerce.order_events WHERE order_id = %(oid)s ORDER BY occurred_at
"""


def get_order(conn: psycopg.Connection, lookup: OrderLookup) -> OrderResult:
    """Order status + timeline by order number + email. Uniform ORDER_NOT_FOUND
    for no-such-order and wrong-email alike."""
    with conn.cursor() as cur:
        cur.execute(_ORDER_SQL, {"num": lookup.order_number, "email": lookup.email})
        row = cur.fetchone()
    if row is None:
        return OrderResult(status="ORDER_NOT_FOUND")
    (oid, number, status, email, placed_at, carrier, tracking, city, region, total) = row

    with conn.cursor() as cur:
        cur.execute(_ITEMS_SQL, {"oid": oid})
        items = [
            OrderItem(ps_number=r[0], name=r[1], unit_price_usd=float(r[2]), quantity=r[3])
            for r in cur.fetchall()
        ]
        cur.execute(_EVENTS_SQL, {"oid": oid})
        timeline = [
            OrderEvent(event_type=r[0], occurred_at=r[1], description=r[2]) for r in cur.fetchall()
        ]

    return OrderResult(
        status="FOUND",
        order_number=number,
        order_status=status,
        email_masked=_mask_email(email),
        placed_at=placed_at,
        carrier=carrier,
        tracking_number=tracking,
        shipping_city=city,
        shipping_region=region,
        total_usd=float(total),
        items=items,
        timeline=timeline,
    )


_CREATE_RETURN_SQL = """
WITH ord AS (
    SELECT order_id FROM commerce.orders
    WHERE order_number_norm = catalog.norm_id(%(num)s) AND lower(email) = lower(%(email)s)
)
INSERT INTO commerce.returns (reference, order_id, order_item_id, reason)
SELECT %(ref)s, ord.order_id, %(item)s, %(reason)s FROM ord
RETURNING reference
"""


def initiate_return(
    conn: psycopg.Connection, request: ReturnRequest, *, reference: str | None = None
) -> ReturnResult:
    """Create a mock return record, confirmed with a reference ID (FR-22). Only
    succeeds if the order_number + email pair matches an order."""
    ref = reference or _reference(request.order_number)
    with conn.cursor() as cur:
        cur.execute(
            _CREATE_RETURN_SQL,
            {
                "num": request.order_number,
                "email": request.email,
                "ref": ref,
                "item": request.order_item_id,
                "reason": request.reason,
            },
        )
        row = cur.fetchone()
    if row is None:
        return ReturnResult(status="ORDER_NOT_FOUND")
    conn.commit()
    return ReturnResult(status="CREATED", reference=row[0])


def _reference(order_number: str) -> str:
    # Deterministic-ish reference derived from the order number (mock).
    digits = "".join(ch for ch in order_number if ch.isdigit())[:6].rjust(6, "0")
    return f"RMA-{digits}"


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    shown = local[0] if local else ""
    return f"{shown}***@{domain}" if domain else "***"
