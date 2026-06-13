"""Intent router — the one real LLM call (Haiku via Converse, D2). Classifies a
turn into one or more in-scope intents (multi-intent), primary first. Returns
['out_of_scope'] for anything outside refrigerator/dishwasher parts (FR-2)."""

from __future__ import annotations

import json
import re
from typing import Any

from lily_orchestrator.converse import DEFAULT_ROUTER_MODEL, converse
from lily_orchestrator.entities import extract_ps_numbers, strip_identifiers
from lily_orchestrator.state import INTENTS

_SYSTEM = """You route customer messages for PartSelect, a store for REFRIGERATOR \
and DISHWASHER replacement parts. Classify the message into one or more intents, \
most relevant first. Allowed intents:
- product: finding parts, prices, stock, details, comparisons (a brand or \
appliance type alone is still product, NOT compatibility). A message that is ONLY \
a part number (a PS number like "PS7784018", or a manufacturer part number) with \
no other words is product — look up that part. A bare part number is NEVER order.
- compatibility: does a part fit a model, where a SPECIFIC model number is given \
or clearly referenced (e.g. "WDT780SAEM1", or "it"/"my model" after one was stated)
- repair: symptoms, troubleshooting, "how to fix", installation help
- order: order status, tracking, returns, cancellations. REQUIRES order-context \
cues — the word "order", "shipped", "tracking", "where's my…", "return", or an \
order number (our order numbers are LILY-prefixed, e.g. "LILY-1001"). A part number \
(PS…) is NOT an order number; never route a bare part number to order.
- out_of_scope: anything not about refrigerator/dishwasher parts (other appliances, \
general chat, unrelated topics)

Reply with ONLY a JSON object: {"intents": ["..."]}. Use out_of_scope alone when \
the message is off-topic. List multiple intents only when the message genuinely \
asks for multiple distinct things."""

# Part-lookup-neutral filler: words that carry no intent of their own around a bare
# part number ("part", "number", "please", connectors). If a message reduces to ONLY
# these once its identifiers are stripped, it is an identifier-only lookup. Intent
# words ("compatible", "fit", "install", "fix", "price", "how", "where", "order", …)
# are deliberately ABSENT — their presence means the LLM should route normally.
_NEUTRAL_WORDS = frozenset(
    {
        "part",
        "parts",
        "number",
        "numbers",
        "no",
        "the",
        "a",
        "an",
        "and",
        "for",
        "please",
        "pls",
        "info",
        "information",
        "details",
        "detail",
        "show",
        "find",
        "lookup",
        "look",
        "up",
        "get",
        "about",
        "on",
        "of",
        "tell",
        "is",
        "it",
        "this",
        "that",
        "me",
        "i",
        "need",
        "want",
        "you",
        "can",
        "could",
        "would",
        "like",
        "to",
        "do",
        "have",
        "got",
        "any",
        "thanks",
        "thank",
        "hi",
        "hello",
        "hey",
    }
)
_WORD_RX = re.compile(r"[A-Za-z]+")


def _identifier_only(utterance: str) -> bool:
    """True when, after removing part/model identifiers, only neutral filler remains
    — i.e. the message is essentially just a bare identifier with no intent signal."""
    residue = strip_identifiers(utterance)
    return all(w in _NEUTRAL_WORDS for w in _WORD_RX.findall(residue.lower()))


def deterministic_route(utterance: str) -> list[str] | None:
    """Deterministic pre-route for unambiguous identifier-only messages. A message
    that is ONLY a part number (PS#) with no other intent words is a product lookup
    — NEVER order. The LLM under-signals on identifier-only input (the reported bug:
    bare "PS7784018" -> order). Order intent requires real order-context cues, not a
    bare part number. Returns None when there IS signal — the LLM decides then."""
    if extract_ps_numbers(utterance) and _identifier_only(utterance):
        return ["product"]
    return None


def classify(client: Any, utterance: str, *, model_id: str = DEFAULT_ROUTER_MODEL) -> list[str]:
    """Return the ordered intent list for an utterance (>=1 item)."""
    override = deterministic_route(utterance)
    if override is not None:
        return override
    text = converse(client, model_id=model_id, system=_SYSTEM, user_text=utterance)
    intents = _parse_intents(text)
    return intents or ["out_of_scope"]


def _parse_intents(text: str) -> list[str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    raw = data.get("intents", [])
    if not isinstance(raw, list):
        return []
    # Keep only known intents, preserve order, dedupe. out_of_scope is exclusive.
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if item in INTENTS and item not in seen:
            seen.add(item)
            out.append(item)
    if "out_of_scope" in out:
        return ["out_of_scope"]
    return out
