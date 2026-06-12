"""Bedrock token + cost metrics (NFR-7/NFR-18).

Defined in lily_common so the orchestrator's converse() can increment them while
the gateway's /metrics endpoint exposes them — both share the one process-global
prometheus_client default registry, so no cross-module wiring is needed.

Pricing is LIST price per million tokens (USD) for the current-gen tiers (D2).
Update the table if Bedrock pricing changes; an unpriced model contributes 0 cost
(logged once) so a newly-introduced model never breaks a turn.
"""

from __future__ import annotations

import logging

from prometheus_client import Counter

log = logging.getLogger("lily_common.metrics")

BEDROCK_TOKENS = Counter(
    "lily_bedrock_tokens_total",
    "Bedrock tokens consumed",
    ["model", "direction"],  # direction: input | output
)
BEDROCK_COST = Counter(
    "lily_bedrock_cost_usd_total",
    "Bedrock cost in USD (list price; see lily_common.metrics)",
    ["model"],
)

# (input_per_mtok, output_per_mtok) USD, matched by substring on the model id
# (inference-profile ids carry "haiku"/"sonnet"). List price.
# Last verified: 2026-06-12 — re-check against AWS Bedrock pricing if it drifts.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "haiku": (0.80, 4.00),
    "sonnet": (3.00, 15.00),
}
_unpriced_seen: set[str] = set()


def _rates(model_id: str) -> tuple[float, float] | None:
    low = model_id.lower()
    for key, rates in _PRICE_PER_MTOK.items():
        if key in low:
            return rates
    return None


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """List-price cost for one call. Unknown model -> 0.0 (logged once)."""
    rates = _rates(model_id)
    if rates is None:
        if model_id not in _unpriced_seen:
            _unpriced_seen.add(model_id)
            log.warning("no pricing for model %s; cost counted as 0", model_id)
        return 0.0
    in_rate, out_rate = rates
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


def record_usage(model_id: str, input_tokens: int, output_tokens: int) -> None:
    """Increment the token + cost counters for one Bedrock call."""
    BEDROCK_TOKENS.labels(model=model_id, direction="input").inc(input_tokens)
    BEDROCK_TOKENS.labels(model=model_id, direction="output").inc(output_tokens)
    BEDROCK_COST.labels(model=model_id).inc(cost_usd(model_id, input_tokens, output_tokens))
