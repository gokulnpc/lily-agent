"""Graph e2e tests need compose Postgres for the real check_compatibility +
validator; skip cleanly when absent. Bedrock + checkpointer are faked/in-memory."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from lily_db.migrate import apply_migrations

_CANDIDATE_DSNS = [
    os.environ.get("LILY_DATABASE_URL"),
    "postgresql://lily:lily-local@localhost:5432/lily",
    "postgresql://lily:lily-local@localhost:5433/lily",
]


def _reachable_dsn() -> str | None:
    for dsn in _CANDIDATE_DSNS:
        if not dsn:
            continue
        try:
            with psycopg.connect(dsn, connect_timeout=2):
                return dsn
        except psycopg.OperationalError:
            continue
    return None


@pytest.fixture(scope="session")
def dsn() -> str:
    found = _reachable_dsn()
    if found is None:
        pytest.skip("no local Postgres reachable (run `make up` first)")
    apply_migrations(found)
    return found


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn) as connection:
        yield connection
        connection.rollback()


class FakeConverse:
    """Stands in for the Bedrock Converse client for every LLM call the graph
    makes: the Haiku scope gate (IN_SCOPE/OUT_OF_SCOPE), the Haiku topicality gate
    (ON_TOPIC/OFF_TOPIC), the router (canned intents per utterance), and the
    specialist (narrates, grounded in the TOOL RESULT json — so the test response
    only ever contains real identifiers, like real Sonnet would).

    Scope/topicality default to PASS so existing tests reach the router unchanged;
    `scope_out` (utterances) and `off_topic` (responses) force a block."""

    def __init__(
        self,
        intents_by_text: dict[str, list[str]],
        *,
        scope_out: set[str] | None = None,
        off_topic: set[str] | None = None,
    ) -> None:
        self._by_text = intents_by_text
        self._scope_out = scope_out or set()
        self._off_topic = off_topic or set()
        self.calls = 0

    def converse(self, *, system: list[Any], messages: list[Any], **_: Any) -> dict[str, Any]:
        self.calls += 1
        system_text = system[0]["text"]  # Bedrock Converse passes system as [{"text": ...}]
        user_text = messages[0]["content"][0]["text"]
        if "scope gate" in system_text:  # Haiku input scope classifier
            return _msg("OUT_OF_SCOPE" if user_text.strip() in self._scope_out else "IN_SCOPE")
        if "topicality gate" in system_text:  # Haiku output topicality backstop
            return _msg("OFF_TOPIC" if user_text.strip() in self._off_topic else "ON_TOPIC")
        if "route customer messages" in system_text:  # router call
            intents = self._by_text.get(user_text.strip(), ["out_of_scope"])
            return _msg(json.dumps({"intents": intents}))
        return _msg(_narrate_from_tool_result(user_text))


def _narrate_from_tool_result(user_text: str) -> str:
    """Deterministic 'narration' grounded only in the tool result JSON — mirrors
    what a grounded Sonnet would do (never inventing identifiers)."""
    m = re.search(r"TOOL RESULT.*?\n(\{.*\}|\[.*\])", user_text, re.DOTALL)
    if not m:
        return "Sorry, I don't have that information."
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return "Sorry, I don't have that information."
    if isinstance(data, dict) and "verdict" in data:
        v = data["verdict"]
        if v == "YES":
            ps, mdl, url = data.get("ps_number"), data.get("model_number"), data.get("citation_url")
            return f"Yes — {ps} fits {mdl}. ({url})"
        if v == "NO":
            alts = ", ".join(a["ps_number"] for a in data.get("alternatives", []))
            ps, mdl = data.get("ps_number"), data.get("model_number")
            return f"No, {ps} doesn't fit {mdl}. Alternatives: {alts}"
        return f"I couldn't confirm that ({v})."
    if isinstance(data, dict) and "ps_number" in data:
        return f"{data['ps_number']} — {data.get('name')} (${data.get('price_usd')})."
    return "Here's what I found."


def _msg(text: str) -> dict[str, Any]:
    return {"output": {"message": {"content": [{"text": text}]}}}


@pytest.fixture
def fake_converse() -> type[FakeConverse]:
    """The FakeConverse class, so tests construct one with their canned intents."""
    return FakeConverse
