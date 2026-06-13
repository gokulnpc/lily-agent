"""Offline eval gate (Phase 5, NFR-23/24).

Runs evals/cases.jsonl through the REAL agent graph with FakeConverse (canned
router/guardrail decisions) + compose Postgres (real tools, real validator, real
compatibility SQL). The LLM's routing/narration QUALITY is a live-tier concern
(evals/live.py); this gate locks the deterministic contract:

  * compatibility verdicts match the SQL truth table (check_compatibility),
  * invalid_identifiers == [] on every answered (non-blocked) case (FR-4),
  * blocked == true for every out-of-scope/injection case, with NO specialist run,
  * citations present on every answer that should cite (FR-19),
  * the correct primary_intent / specialist ran.

All-or-nothing: any failed assertion exits non-zero (the CI gate). Failures are
findings — bring them to the owner, don't tune cases to pass.

Run: `make evals` (or `uv run python evals/run.py`). Skips cleanly (exit 0) if no
Postgres is reachable, so DB-less environments don't false-fail; CI provides one.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg

from evals.seed import seed_catalog
from lily_catalog.models import CompatibilityRequest
from lily_catalog.tools import check_compatibility
from lily_db.migrate import apply_migrations
from lily_orchestrator.graph import build_graph
from lily_orchestrator.specialists import Deps

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:  # pragma: no cover
    MemorySaver = None  # type: ignore[assignment,misc]

CASES = Path(__file__).parent / "cases.jsonl"
_DSNS = [
    os.environ.get("LILY_DATABASE_URL"),
    "postgresql://lily:lily-local@localhost:5432/lily",
    "postgresql://lily:lily-local@localhost:5433/lily",
]


# --- FakeConverse: the offline Bedrock stand-in (mirrors the orchestrator tests). ---
def _msg(text: str) -> dict[str, Any]:
    return {"output": {"message": {"content": [{"text": text}]}}}


class FakeConverse:
    def __init__(self, intents: list[str], *, scope_out: bool) -> None:
        self._intents = intents
        self._scope_out = scope_out

    def converse(self, *, system: list[Any], messages: list[Any], **_: Any) -> dict[str, Any]:
        system_text = system[0]["text"]
        user_text = messages[0]["content"][0]["text"]
        if "scope gate" in system_text:
            return _msg("OUT_OF_SCOPE" if self._scope_out else "IN_SCOPE")
        if "topicality gate" in system_text:
            return _msg("ON_TOPIC")
        if "route customer messages" in system_text:
            return _msg(json.dumps({"intents": self._intents or ["out_of_scope"]}))
        return _msg(_narrate(user_text))


def _narrate(user_text: str) -> str:
    m = re.search(r"TOOL RESULT.*?\n(\{.*\}|\[.*\])", user_text, re.DOTALL)
    if not m:
        return "Sorry, I don't have that information."
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return "Here's what I found."
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


# --- Runner ---
def _connect() -> psycopg.Connection | None:
    for dsn in _DSNS:
        if not dsn:
            continue
        try:
            conn = psycopg.connect(dsn, connect_timeout=3)
            apply_migrations(dsn)
            return conn
        except psycopg.OperationalError:
            continue
    return None


def _load_cases() -> list[dict[str, Any]]:
    cases = []
    for line in CASES.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def main() -> int:
    if MemorySaver is None:
        print("SKIP: langgraph not installed", file=sys.stderr)
        return 0
    conn = _connect()
    if conn is None:
        print("SKIP: no Postgres reachable (run `make up`); the eval gate did not run.")
        return 0
    seed_catalog(conn)

    cases = [c for c in _load_cases() if c.get("tier", "offline") == "offline"]
    # assertion_name -> [passed, total]
    matrix: dict[str, list[int]] = {}
    failures: list[str] = []

    def check(name: str, case_id: str, ok: bool, detail: str = "") -> None:
        m = matrix.setdefault(name, [0, 0])
        m[1] += 1
        if ok:
            m[0] += 1
        else:
            failures.append(f"  FAIL [{case_id}] {name}: {detail}")

    for c in cases:
        cid = c["id"]
        session = c.get("session", {})
        bedrock = FakeConverse(c.get("router_intents", []), scope_out=c.get("scope_out", False))
        graph = build_graph(deps=Deps(conn=conn, bedrock=bedrock), checkpointer=MemorySaver())
        out = graph.invoke(
            {"utterance": c["utterance"], **session},
            {"configurable": {"thread_id": f"eval-{cid}"}},
        )
        exp = c.get("expect", {})
        trace = out.get("trace", [])
        ran_specialist = any(t.startswith("specialist:") for t in trace)

        if "blocked" in exp:
            check(
                "blocked",
                cid,
                bool(out.get("blocked")) == exp["blocked"],
                f"want {exp['blocked']} got {bool(out.get('blocked'))}",
            )
        if exp.get("blocked"):
            check("no_specialist", cid, not ran_specialist, f"trace={trace}")
        else:
            # An answered turn: validator clean + correct specialist + intent.
            check(
                "invalid_identifiers",
                cid,
                out.get("invalid_identifiers", []) == [],
                f"got {out.get('invalid_identifiers')}",
            )
            if "intent" in exp:
                check(
                    "primary_intent",
                    cid,
                    out.get("primary_intent") == exp["intent"],
                    f"want {exp['intent']} got {out.get('primary_intent')}",
                )
                check(
                    "specialist_ran", cid, f"specialist:{exp['intent']}" in trace, f"trace={trace}"
                )
        if exp.get("citations"):
            check("citations", cid, bool(out.get("citations")), "no citations")
        if "current_model" in exp:
            check(
                "session_model",
                cid,
                out.get("current_model") == exp["current_model"],
                f"want {exp['current_model']} got {out.get('current_model')}",
            )
        if exp.get("no_structured"):
            check(
                "no_structured",
                cid,
                out.get("structured", []) == [],
                f"got {len(out.get('structured', []))} cards",
            )
        if "verdict" in exp:
            cp = c["compat"]
            actual = check_compatibility(
                conn, CompatibilityRequest(part=cp["part"], model=cp["model"])
            )
            check(
                "compat_verdict_sql",
                cid,
                actual.verdict == exp["verdict"],
                f"want {exp['verdict']} got {actual.verdict}",
            )

    conn.rollback()  # discard the uncommitted seed -> zero residue in the DB
    conn.close()

    total = len(cases)
    print(f"\nLily offline eval gate — {total} cases\n")
    for name in sorted(matrix):
        p, t = matrix[name]
        mark = "ok" if p == t else "XX"
        print(f"  [{mark}] {name:<20}: {p}/{t}")
    if failures:
        print("\nFailures (findings — do not tune cases to pass):")
        print("\n".join(failures))
        print(f"\nFAIL — {len(failures)} assertion failure(s) across {total} cases")
        return 1
    print(f"\nPASS — {total}/{total} cases, all assertions green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
