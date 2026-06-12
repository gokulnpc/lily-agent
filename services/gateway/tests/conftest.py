"""Gateway SSE tests need compose Postgres (real check_compatibility + validator)
and a FakeConverse standing in for every Bedrock call the graph makes (scope gate,
topicality gate, router, specialist narration). Skip cleanly when no DB."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest

from lily_db.migrate import apply_migrations

_CANDIDATES = [
    os.environ.get("LILY_DATABASE_URL"),
    "postgresql://lily:lily-local@localhost:5432/lily",
    "postgresql://lily:lily-local@localhost:5433/lily",
]


def _reachable() -> str | None:
    for dsn in _CANDIDATES:
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
    found = _reachable()
    if found is None:
        pytest.skip("no local Postgres reachable (run `make up` first)")
    apply_migrations(found)
    return found


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    # Commit seeds (the graph reads via a worker thread under astream); truncate after.
    with psycopg.connect(dsn) as connection:
        yield connection
        with connection.cursor() as cur:
            cur.execute(
                "TRUNCATE catalog.parts, catalog.models, "
                "catalog.part_model_compatibility RESTART IDENTITY CASCADE"
            )
        connection.commit()


def _msg(text: str) -> dict[str, Any]:
    return {"output": {"message": {"content": [{"text": text}]}}}


class FakeConverse:
    """Every graph LLM call, deterministic: scope/topicality gates PASS by default;
    router returns canned intents; specialist narrates grounded in the TOOL RESULT."""

    def __init__(
        self, intents_by_text: dict[str, list[str]], *, scope_out: set[str] | None = None
    ) -> None:
        self._by_text = intents_by_text
        self._scope_out = scope_out or set()

    def converse(self, *, system: list[Any], messages: list[Any], **_: Any) -> dict[str, Any]:
        sys_text = system[0]["text"]
        user_text = messages[0]["content"][0]["text"]
        if "scope gate" in sys_text:
            return _msg("OUT_OF_SCOPE" if user_text.strip() in self._scope_out else "IN_SCOPE")
        if "topicality gate" in sys_text:
            return _msg("ON_TOPIC")
        if "route customer messages" in sys_text:
            intents = self._by_text.get(user_text.strip(), ["out_of_scope"])
            return _msg(json.dumps({"intents": intents}))
        return _msg(_narrate(user_text))


def _narrate(user_text: str) -> str:
    m = re.search(r"TOOL RESULT.*?\n(\{.*\}|\[.*\])", user_text, re.DOTALL)
    if not m:
        return "Sorry, I don't have that information."
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return "Sorry, I don't have that information."
    if isinstance(data, dict) and data.get("verdict") == "YES":
        return f"Yes — {data.get('ps_number')} fits {data.get('model_number')}."
    if isinstance(data, dict) and "ps_number" in data:
        return f"{data['ps_number']} — {data.get('name')}."
    return "Here's what I found."


@pytest.fixture
def fake_converse() -> type[FakeConverse]:
    return FakeConverse
