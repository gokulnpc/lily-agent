"""Specialist tool-augmentation against compose Postgres, with FakeConverse as
the Sonnet stand-in (grounded narration parsed from the tool result). No live AWS."""

from __future__ import annotations

import psycopg

from lily_orchestrator.specialists import (
    Deps,
    compatibility_specialist,
    deflect,
    order_specialist,
    product_specialist,
)
from lily_orchestrator.state import GraphState

SRC = "https://example.test/x"


def _seed(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,price_usd,in_stock,"
            "source_url,scraped_at) VALUES "
            "('PS11752778','Door Shelf Bin','refrigerator',47.40,true,%(s)s,now())",
            {"s": SRC},
        )
        cur.execute(
            "INSERT INTO catalog.models (model_number,brand,appliance_type,source_url,scraped_at)"
            " VALUES ('WRS325FDAM04','Whirlpool','refrigerator',%(s)s,now())",
            {"s": SRC},
        )
        cur.execute(
            "INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)"
            " SELECT p.part_id, m.model_id, %(s)s FROM catalog.parts p, catalog.models m"
            " WHERE p.ps_number='PS11752778' AND m.model_number='WRS325FDAM04'",
            {"s": SRC},
        )


def test_compatibility_narrates_from_tool(conn: psycopg.Connection, fake_converse: type) -> None:
    _seed(conn)
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    state: GraphState = {
        "utterance": "does it fit?",
        "current_part": "PS11752778",
        "current_model": "WRS325FDAM04",
    }
    out = compatibility_specialist(state, deps)
    # Grounded: only real identifiers from the tool result appear.
    assert "PS11752778" in out.text and "WRS325FDAM04" in out.text
    assert "Yes" in out.text
    # Citations pulled structurally from the tool result (FR-19), not the prose.
    assert out.citations == [SRC]


def test_compatibility_asks_when_missing(conn: psycopg.Connection, fake_converse: type) -> None:
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    out = compatibility_specialist({"utterance": "does it fit?", "current_part": "PS1"}, deps)
    assert "model number" in out.text  # no LLM call needed to ask
    assert out.citations == []


def test_product_narrates_part_details(conn: psycopg.Connection, fake_converse: type) -> None:
    _seed(conn)
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    out = product_specialist({"utterance": "how much", "current_part": "PS11752778"}, deps)
    assert "PS11752778" in out.text and "Door Shelf Bin" in out.text
    assert out.citations == [SRC]


def test_order_asks_without_credentials(conn: psycopg.Connection, fake_converse: type) -> None:
    out = order_specialist({"utterance": "where is my order"}, Deps(conn=conn))
    assert "order number" in out.text and "email" in out.text


def test_deflect_is_fixed() -> None:
    out = deflect({"utterance": "microwave?"}, Deps(conn=None))  # type: ignore[arg-type]
    assert "refrigerator and dishwasher" in out.text
