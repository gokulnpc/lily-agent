"""Two-turn compatibility proof against compose Postgres: turn 1 establishes the
model, turn 2 uses a pronoun ("it") that must resolve from checkpointed session
state, and the verdict comes from the REAL check_compatibility SQL. Bedrock is
faked; the checkpointer is in-memory."""

from __future__ import annotations

import json
from typing import Any

import psycopg
from langgraph.checkpoint.memory import MemorySaver

from lily_orchestrator.graph import build_graph
from lily_orchestrator.specialists import Deps

SRC = "https://example.test/section"


class FakeConverse:
    def __init__(self, intents_by_text: dict[str, list[str]]) -> None:
        self._by_text = intents_by_text

    def converse(self, *, messages: list[Any], **_: Any) -> dict[str, Any]:
        text = messages[0]["content"][0]["text"]
        intents = self._by_text.get(text, ["out_of_scope"])
        return {"output": {"message": {"content": [{"text": json.dumps({"intents": intents})}]}}}


def _seed_compatible(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,source_url,scraped_at)"
            " VALUES ('PS11752778','Door Shelf Bin','refrigerator',%(s)s,now())",
            {"s": SRC},
        )
        cur.execute(
            "INSERT INTO catalog.models (model_number,brand,appliance_type,source_url,scraped_at)"
            " VALUES ('WDT780SAEM1','Whirlpool','dishwasher',%(s)s,now())",
            {"s": SRC},
        )
        cur.execute(
            "INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)"
            " SELECT p.part_id, m.model_id, %(s)s FROM catalog.parts p, catalog.models m"
            " WHERE p.ps_number='PS11752778' AND m.model_number='WDT780SAEM1'",
            {"s": SRC},
        )


def test_two_turn_pronoun_resolution_and_real_verdict(conn: psycopg.Connection) -> None:
    _seed_compatible(conn)
    bedrock = FakeConverse(
        {
            "I have a WDT780SAEM1": ["product"],
            "is PS11752778 compatible with it?": ["compatibility"],
        }
    )
    graph = build_graph(bedrock=bedrock, deps=Deps(conn=conn), checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "sess-1"}}

    # Turn 1: establishes the model (no part/compat answer yet).
    t1 = graph.invoke({"utterance": "I have a WDT780SAEM1"}, cfg)
    assert t1["current_model"] == "WDT780SAEM1"

    # Turn 2: "it" carries no model — it must come from the checkpointed session.
    t2 = graph.invoke({"utterance": "is PS11752778 compatible with it?"}, cfg)

    assert t2["current_part"] == "PS11752778"
    assert t2["current_model"] == "WDT780SAEM1"  # resolved from turn 1's state
    assert t2["primary_intent"] == "compatibility"
    # Verdict from the real SQL (seeded compatible) -> YES, names the model.
    assert "Yes" in t2["response_text"]
    assert "WDT780SAEM1" in t2["response_text"]
    # Real PS/model in the response pass the catalog validator.
    assert t2["invalid_identifiers"] == []
    # The trace shows the full path.
    assert t2["trace"] == [
        "entry",
        "input_guardrail",
        "router",
        "specialist:compatibility",
        "validator",
        "output_guardrail",
        "save",
    ]


def test_validator_flags_hallucinated_identifier(conn: psycopg.Connection) -> None:
    # A part not in the catalog must be flagged (FR-4). Route to compatibility
    # with a missing part so the stub emits PART_NOT_FOUND referencing it... but
    # to test the validator directly, check a response with a bogus PS number.
    from lily_orchestrator.validator import invalid_identifiers

    _seed_compatible(conn)
    bad = invalid_identifiers(conn, "Try PS00000000 — it fits WDT780SAEM1.")
    assert "PS00000000" in bad  # hallucinated part flagged
    assert "WDT780SAEM1" not in bad  # real model passes


def test_out_of_scope_deflects(conn: psycopg.Connection) -> None:
    bedrock = FakeConverse({"recommend a microwave": ["out_of_scope"]})
    graph = build_graph(bedrock=bedrock, deps=Deps(conn=conn), checkpointer=MemorySaver())
    out = graph.invoke(
        {"utterance": "recommend a microwave"}, {"configurable": {"thread_id": "s2"}}
    )
    assert out["primary_intent"] == "out_of_scope"
    assert "refrigerator and dishwasher" in out["response_text"]


def test_multi_intent_loops_bounded(conn: psycopg.Connection) -> None:
    _seed_compatible(conn)
    bedrock = FakeConverse(
        {"find a drain pump and does PS11752778 fit WDT780SAEM1": ["product", "compatibility"]}
    )
    graph = build_graph(bedrock=bedrock, deps=Deps(conn=conn), checkpointer=MemorySaver())
    out = graph.invoke(
        {"utterance": "find a drain pump and does PS11752778 fit WDT780SAEM1"},
        {"configurable": {"thread_id": "s3"}},
    )
    # Two specialists ran (product then compatibility) before the validator.
    assert out["trace"].count("router") == 2
    assert "specialist:product" in out["trace"]
    assert "specialist:compatibility" in out["trace"]
