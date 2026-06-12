"""Sonnet 4.6 specialists. Pattern (LLM narrates, DB decides): each specialist
deterministically calls ONLY its own tool(s) to get structured data, then asks
Sonnet to narrate a grounded, customer-appropriate reply. Tool calls are not
LLM-chosen, so the per-specialist tool allowlist is structural — each function
below imports and calls only its own tools.

Offline tests inject a FakeConverse for `deps.bedrock`; the tools run against
compose Postgres / fake search clients. Live demo uses the real Sonnet model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import psycopg

from lily_catalog.models import CompatibilityRequest
from lily_catalog.tools import check_compatibility, get_install_info, get_part_details
from lily_orchestrator import cards, prompts
from lily_orchestrator.converse import DEFAULT_SPECIALIST_MODEL, converse
from lily_orchestrator.entities import extract_model_numbers, extract_ps_numbers
from lily_orchestrator.state import GraphState
from lily_orders.models import OrderLookup
from lily_orders.tools import get_order
from lily_retrieval.models import DiagnoseRequest, SearchRequest
from lily_retrieval.tools import diagnose_symptom, search_parts

DEFLECTION = (
    "I can only help with refrigerator and dishwasher parts — diagnosis, "
    "compatibility, installation, and orders. Is there a part I can help you find?"
)

# An explicit install ask (vs a symptom) inside the repair route. Gated together
# with a resolved part so a lingering session part can't hijack a symptom turn.
_INSTALL_CUE = re.compile(r"\b(install|installation|installing|replace|replacing|put in)\b", re.I)


@dataclass
class Deps:
    conn: psycopg.Connection
    os_client: Any | None = None
    bedrock: Any | None = None
    model_id: str = DEFAULT_SPECIALIST_MODEL
    # Bedrock Guardrail (D6). None => the Bedrock layer is skipped and only the
    # Haiku scope/topicality gates run (offline tests + local dev).
    guardrail_id: str | None = None
    guardrail_version: str = "DRAFT"


@dataclass
class SpecialistReply:
    """A specialist's turn: the grounded narration, the source/citation URLs
    (FR-19), the PS/model-shaped identifiers the TOOL returned this turn (the
    validator's trust set, FR-4), the typed UI cards, and suggested quick-reply
    chips. `structured`/`quick_replies` are built structurally from tool results
    (never parsed from prose) for the Phase-3 frontend."""

    text: str
    citations: list[str] = field(default_factory=list)
    tool_identifiers: list[str] = field(default_factory=list)
    structured: list[dict[str, Any]] = field(default_factory=list)
    quick_replies: list[str] = field(default_factory=list)


def _dedup(urls: list[str | None]) -> list[str]:
    seen: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.append(u)
    return seen


def _ids_in(tool_json: str) -> list[str]:
    """Every PS/model-shaped identifier the tool returned (incl. MPNs inside part
    names) — the validator's trusted set for this turn."""
    return [*extract_ps_numbers(tool_json), *extract_model_numbers(tool_json)]


def _enriched_product(deps: Deps, ps: str, *, fallback: cards.ProductCard) -> dict[str, Any]:
    """A uniform ProductCard: enrich the partial source (alternative / likely-part)
    with a deterministic get_part_details lookup so every card has price/stock/
    install/rating when the catalog has it; fall back to the partial otherwise."""
    details = get_part_details(deps.conn, ps)
    card = cards.product_from_details(details) if details is not None else fallback
    return card.model_dump()


def _narrate(deps: Deps, system: str, utterance: str, tool_result: str) -> str:
    user_text = (
        f"Customer said: {utterance}\n\nTOOL RESULT (your only source of facts):\n{tool_result}"
    )
    return converse(deps.bedrock, model_id=deps.model_id, system=system, user_text=user_text)


def compatibility_specialist(state: GraphState, deps: Deps) -> SpecialistReply:
    part = state.get("current_part")
    model = state.get("current_model")
    if not part or not model:
        missing = "model number" if part else "part (PS) number"
        return SpecialistReply(f"I can check that — what's your {missing}?")
    result = check_compatibility(deps.conn, CompatibilityRequest(part=part, model=model))
    cites = _dedup([result.citation_url, *(a.source_url for a in result.alternatives)])
    tool_json = result.model_dump_json(indent=2)
    text = _narrate(deps, prompts.COMPATIBILITY, state["utterance"], tool_json)
    # On NO, the equivalent parts that DO fit become product cards (FR-14).
    structured = [
        _enriched_product(deps, a.ps_number, fallback=cards.product_from_summary(a))
        for a in result.alternatives
    ]
    quick: list[str] = []
    if result.verdict == "YES":
        quick = [f"How do I install {result.ps_number}?"]
    elif result.verdict == "NO" and result.alternatives:
        quick = [f"How do I install {result.alternatives[0].ps_number}?"]
    elif result.verdict == "MODEL_NOT_FOUND":
        quick = ["Where do I find my model number?"]
    return SpecialistReply(text, cites, _ids_in(tool_json), structured, quick)


def product_specialist(state: GraphState, deps: Deps) -> SpecialistReply:
    # Comparison (FR-11): two or three PS numbers named in the turn -> one card.
    ps_in_turn = extract_ps_numbers(state["utterance"])[:3]
    if len(ps_in_turn) >= 2:
        return _compare_specialist(state, deps, ps_in_turn)

    part = state.get("current_part")
    if part:
        details = get_part_details(deps.conn, part)
        if details is None:
            return SpecialistReply(
                f"I couldn't find {part} in our catalog. Can you double-check the PS number?"
            )
        tool_json = details.model_dump_json(indent=2)
        text = _narrate(deps, prompts.PRODUCT, state["utterance"], tool_json)
        structured = [cards.product_from_details(details).model_dump()]
        return SpecialistReply(
            text,
            _dedup([details.source_url]),
            _ids_in(tool_json),
            structured,
            ["Will this fit my model?"],
        )
    if deps.os_client is None or deps.bedrock is None:
        return SpecialistReply("What part are you looking for?")
    hits = search_parts(
        deps.os_client,
        deps.bedrock,
        deps.conn,
        SearchRequest(text=state["utterance"], appliance_type=None),
    )
    payload = "[" + ", ".join(h.model_dump_json() for h in hits) + "]"
    text = _narrate(deps, prompts.PRODUCT, state["utterance"], payload)
    structured = [
        _enriched_product(deps, h.ps_number, fallback=cards.product_from_hit(h)) for h in hits
    ]
    return SpecialistReply(text, _dedup([h.source_url for h in hits]), _ids_in(payload), structured)


def _compare_specialist(state: GraphState, deps: Deps, ps_numbers: list[str]) -> SpecialistReply:
    found = [d for ps in ps_numbers if (d := get_part_details(deps.conn, ps)) is not None]
    if len(found) < 2:
        return SpecialistReply(
            "I can compare parts, but I could only find one of those PS numbers. "
            "Can you double-check them?"
        )
    payload = "[" + ", ".join(d.model_dump_json() for d in found) + "]"
    text = _narrate(deps, prompts.PRODUCT, state["utterance"], payload)
    part_cards = [cards.product_from_details(d) for d in found]
    card = cards.ComparisonCard(parts=part_cards).model_dump()
    cites = _dedup([d.source_url for d in found])
    return SpecialistReply(text, cites, _ids_in(payload), [card])


def repair_specialist(state: GraphState, deps: Deps) -> SpecialistReply:
    # Install and diagnosis both route here (DECISIONS: install→repair). An install
    # cue + a resolved specific part (named PS, or "this part" from session) means an
    # install ask; otherwise it's a symptom to diagnose.
    part = state.get("current_part")
    if part and _INSTALL_CUE.search(state["utterance"]):
        return _install_specialist(state, deps, part)
    if deps.os_client is None or deps.bedrock is None:
        return SpecialistReply(
            "Tell me the symptom and your model number, and I'll suggest likely parts."
        )
    diagnosis = diagnose_symptom(
        deps.os_client,
        deps.bedrock,
        deps.conn,
        DiagnoseRequest(text=state["utterance"], model_number=state.get("current_model")),
    )
    tool_json = diagnosis.model_dump_json(indent=2)
    text = _narrate(deps, prompts.REPAIR, state["utterance"], tool_json)
    cites = _dedup([s.source_url for s in diagnosis.symptoms])
    # The likely parts (ranked) become enriched product cards (cap a few).
    structured: list[dict[str, Any]] = []
    seen_ps: set[str] = set()
    for symptom in diagnosis.symptoms:
        for lp in symptom.likely_parts:
            if lp.ps_number in seen_ps:
                continue
            seen_ps.add(lp.ps_number)
            structured.append(
                _enriched_product(deps, lp.ps_number, fallback=cards.product_from_likely(lp))
            )
    # PS (not name) so clicking the chip resolves current_part → the install path.
    quick = [f"How do I install {structured[0]['ps_number']}?"] if structured else []
    return SpecialistReply(text, cites, _ids_in(tool_json), structured[:6], quick)


def _install_specialist(state: GraphState, deps: Deps, ps: str) -> SpecialistReply:
    """FR-18: install guidance for one part — difficulty, time, and video, backed
    by part attributes (get_install_info). No fabricated steps; the source has none."""
    info = get_install_info(deps.conn, ps)
    if info is None:
        return SpecialistReply(
            f"I couldn't find {ps} in our catalog to pull up install info. "
            "Can you double-check the PS number?"
        )
    tool_json = info.model_dump_json(indent=2)
    text = _narrate(deps, prompts.INSTALL, state["utterance"], tool_json)
    # Full product card (price/stock/rating) alongside the install narration.
    card = _enriched_product(
        deps, ps, fallback=cards.ProductCard(ps_number=info.ps_number, name=info.name)
    )
    return SpecialistReply(
        text, _dedup([info.source_url]), _ids_in(tool_json), [card], ["Will this fit my model?"]
    )


def order_specialist(state: GraphState, deps: Deps) -> SpecialistReply:
    order_number = state.get("order_number")
    email = state.get("order_email")
    if not order_number or not email:
        return SpecialistReply(
            "I can look that up — what's your order number and the email on the order?"
        )
    result = get_order(deps.conn, OrderLookup(order_number=order_number, email=email))
    tool_json = result.model_dump_json(indent=2)
    text = _narrate(deps, prompts.ORDER, state["utterance"], tool_json)
    structured: list[dict[str, Any]] = []
    quick: list[str] = []
    if result.status == "FOUND":
        structured = [cards.order_card(result).model_dump()]
        quick = ["Start a return", "Track another order"]
    return SpecialistReply(text, [], _ids_in(tool_json), structured, quick)


def deflect(_state: GraphState, _deps: Deps) -> SpecialistReply:
    return SpecialistReply(DEFLECTION)


SPECIALISTS = {
    "compatibility": compatibility_specialist,
    "product": product_specialist,
    "repair": repair_specialist,
    "order": order_specialist,
    "out_of_scope": deflect,
}
