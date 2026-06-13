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
    repair_specialist,
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


def test_install_path_returns_enriched_card(conn: psycopg.Connection, fake_converse: type) -> None:
    # FR-18: an install ask for a specific part -> install attributes + a product card.
    _seed(conn)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE catalog.parts SET install_difficulty='Really Easy',"
            " install_time='15-30 mins', install_video_url='https://youtu.be/x'"
            " WHERE ps_number='PS11752778'"
        )
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    state: GraphState = {
        "utterance": "How can I install part number PS11752778?",
        "current_part": "PS11752778",
    }
    out = repair_specialist(state, deps)
    assert "PS11752778" in out.text  # grounded narration
    assert out.structured and out.structured[0]["kind"] == "product"
    assert out.structured[0]["ps_number"] == "PS11752778"
    assert out.structured[0]["install_difficulty"] == "Really Easy"
    # Part page + install video both cited (the prose no longer pastes URLs).
    assert out.citations == [SRC, "https://youtu.be/x"]
    assert out.quick_replies == ["Will this fit my model?"]


def test_install_path_part_not_in_catalog(conn: psycopg.Connection, fake_converse: type) -> None:
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    out = repair_specialist(
        {"utterance": "how do I install PS00000000?", "current_part": "PS00000000"}, deps
    )
    assert "couldn't find" in out.text
    assert out.structured == []


def test_lingering_part_does_not_hijack_symptom(
    conn: psycopg.Connection, fake_converse: type
) -> None:
    # A part lingering in session must NOT turn a symptom turn into an install turn
    # (no install cue) — it falls through to the symptom-diagnosis path.
    deps = Deps(conn=conn, bedrock=fake_converse({}))
    out = repair_specialist(
        {"utterance": "my ice maker is not working", "current_part": "PS11752778"}, deps
    )
    # os_client is None here, so the diagnosis path returns its no-search prompt
    # rather than the install card — proving the install branch was not taken.
    assert "symptom" in out.text.lower()
    assert out.structured == []


def test_order_asks_without_credentials(conn: psycopg.Connection, fake_converse: type) -> None:
    out = order_specialist({"utterance": "where is my order"}, Deps(conn=conn))
    assert "order number" in out.text and "email" in out.text


def test_deflect_is_fixed() -> None:
    out = deflect({"utterance": "microwave?"}, Deps(conn=None))  # type: ignore[arg-type]
    assert "refrigerator and dishwasher" in out.text
