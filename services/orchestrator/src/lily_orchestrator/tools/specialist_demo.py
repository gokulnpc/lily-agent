"""Live Sonnet 4.6 specialist proof (Phase 2 step 3, Part B).

Runs the REAL graph end-to-end — live Haiku 4.5 router, live Sonnet 4.6
specialists, live Titan v2 embeddings, and the real catalog validator — over
the three brief examples plus the eval record-only case, printing each actual
response, the validator's invalid-identifier verdict (FR-4), and the trace.

What is live vs. stood-in (the OpenSearch domain is VPC-only, unreachable from a
laptop — see prove_search.py, which runs in-cluster for exactly this reason):
  - Router (Haiku), specialists (Sonnet), embeddings (Titan): LIVE Bedrock.
  - Catalog tools + validator: real SQL against compose Postgres, seeded here
    with the real PartSelect identifiers the examples reference.
  - Symptom retrieval (repair path): a LocalSymptomSearch stand-in returns the
    REAL 12-symptom refrigerator corpus (parsed from the Phase-1 repair-index
    fixture), ranked by lexical overlap, in the exact OpenSearch response shape
    diagnose_symptom expects. The hybrid ranking/scoring differs from the live
    kNN+BM25 domain, but the symptom data is real and the narration + validation
    are fully live. For the production-faithful retrieval, run in-cluster.

    AWS_PROFILE=partselect-dev LILY_DATABASE_URL=postgresql://lily:lily-local@localhost:5433/lily \
      uv run python -m lily_orchestrator.tools.specialist_demo
"""

from __future__ import annotations

import os
from typing import Any

import boto3
import psycopg
from langgraph.checkpoint.memory import MemorySaver

from lily_orchestrator.graph import build_graph
from lily_orchestrator.specialists import Deps

# Real PartSelect identifiers the examples reference (FR-13/FR-18). PS11752778 is
# a Whirlpool *refrigerator* door shelf bin; WDT780SAEM1 is a Whirlpool
# *dishwasher* — so the honest compatibility verdict for example 2 is NO.
_PART = ("PS11752778", "Refrigerator Door Shelf Bin", "refrigerator", 47.40)
_MODEL = ("WDT780SAEM1", "Whirlpool", "dishwasher")
_SRC = "https://www.partselect.com/PS11752778-demo.htm"

# The real refrigerator symptom corpus (name, repair-page URL, description),
# parsed once from the Phase-1 repair-index fixture and embedded here so this
# proof tool stays self-contained. This is the same data the live OpenSearch
# symptom index holds; the stand-in below ranks it lexically rather than via the
# domain's kNN+BM25.
_SYMPTOM_CORPUS = [
    (
        "Noisy",
        "/Repair/Refrigerator/Noisy/",
        "When your fridge is noisy, find out how to repair it by troubleshooting the location of the noise, from the evaporator fan motor in the freezer to the bottom of the fridge with the condenser fan motor.",
    ),
    (
        "Leaking",
        "/Repair/Refrigerator/Leaking/",
        "Diagnose the reason for your leaking fridge, from a faulty water inlet valve to a worn out door seal.",
    ),
    (
        "Will not start",
        "/Repair/Refrigerator/Will-Not-Start/",
        "Find out how to fix a fridge that will not start, by examining a few key parts such as the temperature control or the compressor overload relay.",
    ),
    (
        "Ice maker not making ice",
        "/Repair/Refrigerator/Not-Making-Ice/",
        "Learn how to fix your ice maker when it's not making ice and inspect the water fill tubes, water inlet valve and the icemaker.",
    ),
    (
        "Fridge too warm",
        "/Repair/Refrigerator/Refrigerator-Too-Warm/",
        "If your fridge is, too warm then troubleshooting common parts like the air inlet damper.",
    ),
    (
        "Not dispensing water",
        "/Repair/Refrigerator/Not-Dispensing-Water/",
        "If the water dispenser is not dispensing water then examine key parts such as the water inlet valve and dispenser actuator.",
    ),
    (
        "Fridge and Freezer are too warm",
        "/Repair/Refrigerator/Refrigerator-Freezer-Too-Warm/",
        "Diagnose the causes of why the fridge and freezer are too warm by checking a few key parts such as the defrost timer, defrost heater, defrost thermostat or evaporator fan motor.",
    ),
    (
        "Door Sweating",
        "/Repair/Refrigerator/Door-Sweating/",
        "When the fridge has doors that are sweating then examine key components such as the door gasket, seals and the hinges.",
    ),
    (
        "Light not working",
        "/Repair/Refrigerator/Light-Not-Working/",
        "Learn how to fix the fridge when the light won't turn on but the door is opened.",
    ),
    (
        "Fridge too cold",
        "/Repair/Refrigerator/Refrigerator-Too-Cold/",
        "Find out how to repair a fridge that's too cold by troubleshooting the common problem parts like a temperature control or thermistor.",
    ),
    (
        "Fridge runs too long",
        "/Repair/Refrigerator/Running-Too-Long/",
        "Troubleshoot why the fridge is running too long by examining some of the key parts like a faulty defrost timer or the thermostats.",
    ),
    (
        "Freezer too cold",
        "/Repair/Refrigerator/Freezer-Too-Cold/",
        "Determine why your freezer is too cold by troubleshooting parts, like the air damper or thermistor.",
    ),
]


def _seed(conn: psycopg.Connection) -> None:
    """Seed the two real identifiers (the live demo can't reach VPC-only Aurora)."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,price_usd,in_stock,"
            "source_url,scraped_at) VALUES (%s,%s,%s,%s,true,%s,now()) "
            "ON CONFLICT (ps_number_norm) DO NOTHING",
            (*_PART, _SRC),
        )
        cur.execute(
            "INSERT INTO catalog.models (model_number,brand,appliance_type,source_url,scraped_at)"
            " VALUES (%s,%s,%s,%s,now()) ON CONFLICT (model_number_norm) DO NOTHING",
            (*_MODEL, _SRC),
        )
    conn.commit()


class LocalSymptomSearch:
    """Disclosed stand-in for the VPC-only OpenSearch symptom index. Holds the
    REAL refrigerator symptom corpus (parsed live from the repair-index fixture)
    and returns OpenSearch-shaped hits ranked by lexical overlap with the query."""

    def __init__(self) -> None:
        self._corpus = [
            {"title": name, "body": desc, "source_url": url} for name, url, desc in _SYMPTOM_CORPUS
        ]

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        del index  # the stand-in holds a single corpus; index name is unused
        text = body["query"]["bool"]["should"][0]["multi_match"]["query"].lower()
        terms = {t for t in text.replace("?", " ").split() if len(t) > 2}

        def overlap(doc: dict[str, str]) -> int:
            words = (doc["title"] + " " + doc["body"]).lower().split()
            return sum(1 for t in terms if t in words)

        ranked = sorted(self._corpus, key=overlap, reverse=True)
        hits = [
            {"_score": float(overlap(d) or 0), "_source": d} for d in ranked[:3] if overlap(d) > 0
        ]
        return {"hits": {"hits": hits}}


# (utterance, session-state-before-this-turn, label). Examples 1-3 are the brief
# proofs; the 4th is the eval record-only case (vague "my fridge", model in
# session) — recorded, not asserted.
_CASES = [
    ("How can I install part number PS11752778?", {}, "1 · install (repair)"),
    (
        "Is this part compatible with my WDT780SAEM1 model?",
        {"current_part": "PS11752778"},
        "2 · compatibility (turn 2, 'this part' from session)",
    ),
    (
        "The ice maker on my Whirlpool fridge is not working. How can I fix it?",
        {},
        "3 · ice maker (repair)",
    ),
    (
        "is this part compatible with my fridge?",
        {"current_part": "PS11752778", "current_model": "WDT780SAEM1"},
        "eval · vague 'my fridge' (record-only)",
    ),
]


def main() -> int:
    region = os.environ.get("AWS_REGION", "us-east-1")
    dsn = os.environ.get("LILY_DATABASE_URL", "postgresql://lily:lily-local@localhost:5433/lily")
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    with psycopg.connect(dsn) as conn:
        _seed(conn)
        deps = Deps(conn=conn, bedrock=bedrock, os_client=LocalSymptomSearch())
        graph = build_graph(deps=deps, checkpointer=MemorySaver())

        for i, (utterance, session, label) in enumerate(_CASES):
            cfg = {"configurable": {"thread_id": f"demo-{i}"}}
            if session:  # prime the session so the pronoun/model resolves (turn 1)
                graph.update_state(cfg, session)
            out = graph.invoke({"utterance": utterance}, cfg)
            print(f"\n{'=' * 78}\nEXAMPLE {label}\n  user: {utterance}")
            print(f"  intent: {out.get('primary_intent')}   trace: {out.get('trace')}")
            print(f"\n  Lily:\n    {out.get('response_text', '').strip()}")
            bad = out.get("invalid_identifiers", [])
            verdict = "clean (zero invalid identifiers)" if not bad else f"FLAGGED: {bad}"
            print(f"\n  validator (FR-4): {verdict}")
        print(f"\n{'=' * 78}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
