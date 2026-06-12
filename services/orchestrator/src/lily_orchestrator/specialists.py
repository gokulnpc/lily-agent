"""Stub specialists — each calls its REAL step-1 tool and formats a templated
(non-LLM) response. This proves tool wiring + state flow; Sonnet prompts replace
the templating in step 3. The tools/clients are carried on `Deps` (injected)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from lily_catalog.models import CompatibilityRequest
from lily_catalog.tools import check_compatibility, get_part_details
from lily_orchestrator.state import GraphState
from lily_retrieval.models import DiagnoseRequest, SearchRequest
from lily_retrieval.tools import diagnose_symptom, search_parts

DEFLECTION = (
    "I can only help with refrigerator and dishwasher parts — diagnosis, "
    "compatibility, installation, and orders. Is there a part I can help you find?"
)


@dataclass
class Deps:
    conn: psycopg.Connection
    os_client: Any | None = None
    bedrock: Any | None = None


def compatibility_specialist(state: GraphState, deps: Deps) -> str:
    part = state.get("current_part")
    model = state.get("current_model")
    if not part or not model:
        missing = "model number" if part else "part (PS) number"
        return f"I can check that — what's your {missing}?"
    r = check_compatibility(deps.conn, CompatibilityRequest(part=part, model=model))
    if r.verdict == "YES":
        cite = f" (per {r.citation_url})" if r.citation_url else ""
        return f"Yes — {r.ps_number} ({r.part_name}) fits {r.model_number}{cite}."
    if r.verdict == "NO":
        lines = [f"No — {part} does not fit {r.model_number}."]
        if r.alternatives:
            lines.append("Parts that do fit:")
            lines += [f"  • {a.ps_number} — {a.name}" for a in r.alternatives[:3]]
        return "\n".join(lines)
    if r.verdict == "PART_NOT_FOUND":
        return f"I couldn't find part {part} in our catalog. Can you double-check the PS number?"
    return (
        f"I couldn't find model {model}. It's usually on a sticker inside the "
        "door or on the back — want help locating it?"
    )


def product_specialist(state: GraphState, deps: Deps) -> str:
    part = state.get("current_part")
    if part:
        d = get_part_details(deps.conn, part)
        if d:
            price = f"${d.price_usd:.2f}" if d.price_usd is not None else "price n/a"
            stock = "in stock" if d.in_stock else "stock unknown"
            return f"{d.ps_number} — {d.name} ({price}, {stock})."
        return f"I couldn't find {part} in the catalog."
    if deps.os_client is None or deps.bedrock is None:
        return "What part are you looking for?"
    hits = search_parts(
        deps.os_client,
        deps.bedrock,
        deps.conn,
        SearchRequest(text=state.get("utterance", ""), appliance_type=None),
    )
    if not hits:
        return "I couldn't find a matching part — can you describe it differently?"
    return "Top matches:\n" + "\n".join(f"  • {h.ps_number} — {h.name}" for h in hits[:3])


def repair_specialist(state: GraphState, deps: Deps) -> str:
    if deps.os_client is None or deps.bedrock is None:
        return "Tell me the symptom and I'll suggest likely parts."
    d = diagnose_symptom(
        deps.os_client,
        deps.bedrock,
        deps.conn,
        DiagnoseRequest(
            text=state.get("utterance", ""),
            model_number=state.get("current_model"),
        ),
    )
    if not d.symptoms:
        return "I couldn't match that to a known symptom — can you describe it differently?"
    lines = ["Likely related issues:"]
    lines += [f"  • {s.name}" for s in d.symptoms[:3]]
    if d.note:
        lines.append(f"({d.note})")
    return "\n".join(lines)


def order_specialist(_state: GraphState, _deps: Deps) -> str:
    # Order lookups need order# + email, gathered conversationally in step 3.
    return "I can look that up — what's your order number and the email on the order?"


def deflect(_state: GraphState, _deps: Deps) -> str:
    return DEFLECTION


SPECIALISTS = {
    "compatibility": compatibility_specialist,
    "product": product_specialist,
    "repair": repair_specialist,
    "order": order_specialist,
    "out_of_scope": deflect,
}
