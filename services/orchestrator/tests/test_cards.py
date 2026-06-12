"""Structured UI cards (Phase 3): specialists build typed cards from tool results
(FakeConverse + compose Postgres). The order-card builder is a pure unit."""

from __future__ import annotations

from datetime import datetime

import psycopg

from lily_orchestrator import cards
from lily_orchestrator.specialists import (
    Deps,
    compatibility_specialist,
    product_specialist,
)
from lily_orchestrator.state import GraphState
from lily_orders.models import OrderEvent, OrderItem, OrderResult


def _part(cur: psycopg.Cursor, ps: str, cat: str, price: float, model_compat: str | None) -> None:
    cur.execute(
        "INSERT INTO catalog.parts (ps_number,name,appliance_type,part_category,price_usd,"
        "in_stock,source_url,scraped_at) VALUES "
        "(%s,%s,'dishwasher',%s,%s,true,%s,now()) ON CONFLICT (ps_number_norm) DO NOTHING",
        (ps, f"{ps} {cat}", cat, price, f"https://x.test/{ps}"),
    )
    if model_compat:
        cur.execute(
            "INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)"
            " SELECT p.part_id, m.model_id, 'https://x.test/s'"
            " FROM catalog.parts p, catalog.models m"
            " WHERE p.ps_number=%s AND m.model_number=%s",
            (ps, model_compat),
        )


def _model(cur: psycopg.Cursor, model: str) -> None:
    cur.execute(
        "INSERT INTO catalog.models (model_number,brand,appliance_type,source_url,scraped_at)"
        " VALUES (%s,'Whirlpool','dishwasher','https://x.test/m',now())"
        " ON CONFLICT (model_number_norm) DO NOTHING",
        (model,),
    )


def test_product_specialist_emits_product_card(
    conn: psycopg.Connection, fake_converse: type
) -> None:
    with conn.cursor() as cur:
        _part(cur, "PS1000001", "Drain Pump", 49.40, None)
    reply = product_specialist(
        {"utterance": "tell me about it", "current_part": "PS1000001"},
        Deps(conn=conn, bedrock=fake_converse({})),
    )
    assert len(reply.structured) == 1
    card = reply.structured[0]
    assert card["kind"] == "product" and card["ps_number"] == "PS1000001"
    assert card["price_usd"] == 49.40 and card["in_stock"] is True


def test_compatibility_no_emits_alternative_cards(
    conn: psycopg.Connection, fake_converse: type
) -> None:
    with conn.cursor() as cur:
        _model(cur, "MDL780SAEM1")
        _part(cur, "PS2000001", "Drain Pump", 0.0, None)  # the asked part — does NOT fit
        _part(cur, "PS2000002", "Drain Pump", 55.00, "MDL780SAEM1")  # an equivalent that fits
    reply = compatibility_specialist(
        {"utterance": "does it fit?", "current_part": "PS2000001", "current_model": "MDL780SAEM1"},
        Deps(conn=conn, bedrock=fake_converse({})),
    )
    # FR-14: the fitting equivalent becomes an (enriched) product card + a quick reply.
    assert any(
        c["kind"] == "product" and c["ps_number"] == "PS2000002" and c["price_usd"] == 55.00
        for c in reply.structured
    )
    assert reply.quick_replies and "install" in reply.quick_replies[0].lower()


def test_two_ps_numbers_emit_comparison_card(conn: psycopg.Connection, fake_converse: type) -> None:
    with conn.cursor() as cur:
        _part(cur, "PS3000001", "Spray Arm", 30.0, None)
        _part(cur, "PS3000002", "Spray Arm", 40.0, None)
    state: GraphState = {"utterance": "compare PS3000001 and PS3000002"}
    reply = product_specialist(state, Deps(conn=conn, bedrock=fake_converse({})))
    assert len(reply.structured) == 1
    card = reply.structured[0]
    assert card["kind"] == "comparison" and len(card["parts"]) == 2
    assert {p["ps_number"] for p in card["parts"]} == {"PS3000001", "PS3000002"}


def test_order_card_builder() -> None:
    result = OrderResult(
        status="FOUND",
        order_number="38123",
        order_status="Shipped",
        total_usd=99.50,
        items=[OrderItem(ps_number="PS1", name="Door Bin", unit_price_usd=10.0, quantity=2)],
        timeline=[OrderEvent(event_type="shipped", occurred_at=datetime(2026, 6, 1, 12, 0, 0))],
    )
    card = cards.order_card(result)
    assert card.kind == "order" and card.order_number == "38123"
    assert card.items[0]["ps_number"] == "PS1" and card.items[0]["quantity"] == 2
    assert card.timeline[0]["occurred_at"] == "2026-06-01T12:00:00"  # datetime -> ISO string
