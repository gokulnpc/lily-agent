"""Intent router — the one real LLM call (Haiku via Converse, D2). Classifies a
turn into one or more in-scope intents (multi-intent), primary first. Returns
['out_of_scope'] for anything outside refrigerator/dishwasher parts (FR-2)."""

from __future__ import annotations

import json
import re
from typing import Any

from lily_orchestrator.converse import DEFAULT_ROUTER_MODEL, converse
from lily_orchestrator.state import INTENTS

_SYSTEM = """You route customer messages for PartSelect, a store for REFRIGERATOR \
and DISHWASHER replacement parts. Classify the message into one or more intents, \
most relevant first. Allowed intents:
- product: finding parts, prices, stock, details, comparisons (a brand or \
appliance type alone is still product, NOT compatibility)
- compatibility: does a part fit a model, where a SPECIFIC model number is given \
or clearly referenced (e.g. "WDT780SAEM1", or "it"/"my model" after one was stated)
- repair: symptoms, troubleshooting, "how to fix", installation help
- order: order status, tracking, returns
- out_of_scope: anything not about refrigerator/dishwasher parts (other appliances, \
general chat, unrelated topics)

Reply with ONLY a JSON object: {"intents": ["..."]}. Use out_of_scope alone when \
the message is off-topic. List multiple intents only when the message genuinely \
asks for multiple distinct things."""


def classify(client: Any, utterance: str, *, model_id: str = DEFAULT_ROUTER_MODEL) -> list[str]:
    """Return the ordered intent list for an utterance (>=1 item)."""
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
