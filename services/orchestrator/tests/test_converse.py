"""converse() extracts text and meters Bedrock token usage (NFR-7/18), tolerating
a missing `usage` field. Offline — a fake bedrock-runtime client, no AWS, no OTel
provider (spans are no-ops)."""

from __future__ import annotations

from typing import Any

from prometheus_client import REGISTRY

from lily_orchestrator.converse import converse


class _FakeClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def converse(self, **_: Any) -> dict[str, Any]:
        return self._response


def _text(content: str) -> dict[str, Any]:
    return {"output": {"message": {"content": [{"text": content}]}}}


def test_converse_returns_text_and_records_usage() -> None:
    model = "global.anthropic.claude-sonnet-4-6-convtest"

    def tok(direction: str) -> float:
        return (
            REGISTRY.get_sample_value(
                "lily_bedrock_tokens_total", {"model": model, "direction": direction}
            )
            or 0.0
        )

    in0, out0 = tok("input"), tok("output")
    client = _FakeClient({**_text("hello"), "usage": {"inputTokens": 123, "outputTokens": 45}})
    out = converse(client, model_id=model, system="s", user_text="u")

    assert out == "hello"
    assert tok("input") == in0 + 123
    assert tok("output") == out0 + 45


def test_converse_tolerates_missing_usage() -> None:
    # FakeConverse-shaped responses carry no `usage`; this must not crash.
    client = _FakeClient(_text("ok"))
    assert converse(client, model_id="m", system="s", user_text="u") == "ok"
