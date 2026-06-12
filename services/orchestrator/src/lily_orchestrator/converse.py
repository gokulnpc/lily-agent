"""Thin Bedrock Converse wrapper (D1). The bedrock-runtime client is injected so
tests pass a fake; the call is retry-wrapped for throttles (A11). This is the
only place the Converse API is touched."""

from __future__ import annotations

import os
from typing import Any

from lily_common.retry import call_with_retry, is_bedrock_transient

# Model tiering (D2, amended 2026-06-12): the 3.5 generation is legacy-gated on
# Bedrock ("upgrade to an active model"), so we use current-gen profiles —
# Haiku 4.5 for router/guardrails, Sonnet 4.6 for specialists (step 3). These are
# cross-region inference profile ids (NFR-5); the Global Haiku 4.5 profile is the
# one confirmed active in the account. Override per env.
DEFAULT_ROUTER_MODEL = os.environ.get(
    "LILY_ROUTER_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
DEFAULT_SPECIALIST_MODEL = os.environ.get(
    "LILY_SPECIALIST_MODEL_ID", "global.anthropic.claude-sonnet-4-6"
)


def converse(
    client: Any,
    *,
    model_id: str,
    system: str,
    user_text: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """One-shot Converse call returning the assistant's text. Retried on throttle."""

    def _invoke() -> dict[str, Any]:
        result: dict[str, Any] = client.converse(
            modelId=model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
        )
        return result

    response = call_with_retry(_invoke, retryable=is_bedrock_transient)
    parts = response["output"]["message"]["content"]
    return "".join(block.get("text", "") for block in parts)
