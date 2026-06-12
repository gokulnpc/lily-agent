from __future__ import annotations

import psycopg

from lily_orders.models import OrderLookup, ReturnRequest
from lily_orders.tools import get_order, initiate_return


def _seed_order(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO commerce.orders
                (order_number, email, status, placed_at, carrier, tracking_number,
                 shipping_city, shipping_region, total_usd)
            VALUES ('38123','jane@example.com','shipped',now(),'UPS','1Z999',
                    'Austin','TX',79.98)
            RETURNING order_id
            """
        )
        row = cur.fetchone()
        assert row is not None
        oid = int(row[0])
        cur.execute(
            "INSERT INTO commerce.order_items (order_id, ps_number, name, unit_price_usd, quantity)"
            " VALUES (%s,'PS11752778','Door Shelf Bin',47.40,1)",
            (oid,),
        )
        cur.execute(
            "INSERT INTO commerce.order_events (order_id, event_type, occurred_at, description)"
            " VALUES (%s,'placed',now() - interval '3 days','Order placed'),"
            "        (%s,'shipped',now() - interval '1 day','Shipped via UPS')",
            (oid, oid),
        )
    conn.commit()
    return oid


def test_get_order_found_with_timeline_and_masked_email(conn: psycopg.Connection) -> None:
    _seed_order(conn)
    r = get_order(conn, OrderLookup(order_number="38123", email="jane@example.com"))
    assert r.status == "FOUND"
    assert r.order_status == "shipped"
    assert r.email_masked == "j***@example.com"  # PII minimization
    assert len(r.items) == 1 and r.items[0].ps_number == "PS11752778"
    assert [e.event_type for e in r.timeline] == ["placed", "shipped"]


def test_wrong_email_is_indistinguishable_from_missing(conn: psycopg.Connection) -> None:
    _seed_order(conn)
    wrong = get_order(conn, OrderLookup(order_number="38123", email="someone@else.com"))
    missing = get_order(conn, OrderLookup(order_number="99999", email="jane@example.com"))
    assert wrong.status == "ORDER_NOT_FOUND"
    assert missing.status == "ORDER_NOT_FOUND"
    # No order details leak in either case (anti-enumeration).
    assert wrong.order_number is None and missing.order_number is None


def test_lookup_normalizes_order_number(conn: psycopg.Connection) -> None:
    _seed_order(conn)
    r = get_order(conn, OrderLookup(order_number="#38-123", email="JANE@example.com"))
    assert r.status == "FOUND"


def test_initiate_return_creates_reference(conn: psycopg.Connection) -> None:
    _seed_order(conn)
    r = initiate_return(
        conn, ReturnRequest(order_number="38123", email="jane@example.com", reason="defective")
    )
    assert r.status == "CREATED"
    assert r.reference and r.reference.startswith("RMA-")
    with conn.cursor() as cur:
        cur.execute("SELECT reason FROM commerce.returns WHERE reference = %s", (r.reference,))
        assert cur.fetchone()[0] == "defective"  # type: ignore[index]


def test_initiate_return_rejects_unmatched_order(conn: psycopg.Connection) -> None:
    _seed_order(conn)
    r = initiate_return(conn, ReturnRequest(order_number="38123", email="wrong@x.com", reason="x"))
    assert r.status == "ORDER_NOT_FOUND"
    assert r.reference is None
