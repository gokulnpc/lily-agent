"""Router classification — offline, with a FakeConverse returning canned Bedrock
Converse responses (no live Bedrock). Covers ~10 varied utterances incl. one
out-of-scope and one ambiguous (multi-intent)."""

from __future__ import annotations

import json
from typing import Any

from lily_orchestrator.router import classify, deterministic_route

# utterance -> the intents the (canned) model returns
CANNED = {
    "is PS11752778 compatible with my WDT780SAEM1?": ["compatibility"],
    "how do I install part PS11752778?": ["repair"],
    "my ice maker stopped working": ["repair"],
    "where is my order 38123": ["order"],
    "I want to return a part": ["order"],
    "do you have a door bin for my fridge": ["product"],
    "how much is PS11746591": ["product"],
    "can you recommend a good microwave?": ["out_of_scope"],
    "what's the weather today": ["out_of_scope"],
    # ambiguous / multi-intent: find the part AND check it fits
    "find me a drain pump and tell me if it fits my WDT780SAEM1": ["product", "compatibility"],
}


class FakeConverse:
    """Returns the canned intents for the user text as a Converse response."""

    def __init__(self, canned: dict[str, list[str]]) -> None:
        self._canned = canned
        self.calls = 0

    def converse(self, *, messages: list[Any], **_: Any) -> dict[str, Any]:
        self.calls += 1
        user_text = messages[0]["content"][0]["text"]
        intents = self._canned.get(user_text, ["out_of_scope"])
        body = json.dumps({"intents": intents})
        return {"output": {"message": {"content": [{"text": body}]}}}


def test_classifies_each_utterance() -> None:
    client = FakeConverse(CANNED)
    for utterance, expected in CANNED.items():
        assert classify(client, utterance) == expected, utterance
    assert client.calls == len(CANNED)


def test_out_of_scope_is_exclusive() -> None:
    # Even if the model returns extra intents alongside out_of_scope, it wins.
    class WeirdClient:
        def converse(self, **_: Any) -> dict[str, Any]:
            body = json.dumps({"intents": ["out_of_scope", "product"]})
            return {"output": {"message": {"content": [{"text": body}]}}}

    assert classify(WeirdClient(), "junk") == ["out_of_scope"]


def test_unparseable_falls_back_to_out_of_scope() -> None:
    class GarbageClient:
        def converse(self, **_: Any) -> dict[str, Any]:
            return {"output": {"message": {"content": [{"text": "sorry, no json here"}]}}}

    assert classify(GarbageClient(), "x") == ["out_of_scope"]


# --- Deterministic pre-route: a bare part identifier must go to product, never order. ---
class _AlwaysOrder:
    """Stand-in for a mis-classifying LLM that wrongly returns order for a bare PS#."""

    def __init__(self) -> None:
        self.calls = 0

    def converse(self, **_: Any) -> dict[str, Any]:
        self.calls += 1
        return {"output": {"message": {"content": [{"text": json.dumps({"intents": ["order"]})}]}}}


def test_bare_part_number_routes_to_product_not_order() -> None:
    # The reported bug: an identifier-only message under-signals; even if the LLM
    # would say "order", the deterministic pre-route corrects it to product and
    # never reaches the model.
    for utterance in ["PS7784018", "PS7784018?", "part number PS11752778", "  ps 8689951  "]:
        client = _AlwaysOrder()
        assert classify(client, utterance) == ["product"], utterance
        assert client.calls == 0, f"override should short-circuit the LLM for {utterance!r}"


def test_deterministic_route_only_fires_for_bare_identifiers() -> None:
    # Bare PS -> product.
    assert deterministic_route("PS7784018") == ["product"]
    assert deterministic_route("part PS11752778 please") == ["product"]
    # Any real intent word -> defer to the LLM (None), so normal routing applies.
    assert deterministic_route("how do I install PS11752778?") is None  # repair
    assert deterministic_route("is PS11752778 compatible with WDT780SAEM1?") is None  # compat
    assert deterministic_route("how much is PS11722128") is None  # product, but via LLM
    assert deterministic_route("where is my order LILY-1001") is None  # order
    assert deterministic_route("my ice maker stopped working") is None  # no PS at all
