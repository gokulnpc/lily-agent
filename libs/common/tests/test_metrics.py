"""Bedrock token + cost metrics (NFR-7/18): pricing math + counter increments,
fully offline."""

from __future__ import annotations

from prometheus_client import REGISTRY

from lily_common.metrics import cost_usd, record_usage


def test_cost_usd_per_tier() -> None:
    # Haiku 4.5: $0.80 in / $4.00 out per MTok.
    assert cost_usd("global.anthropic.claude-haiku-4-5-20251001-v1:0", 1_000_000, 1_000_000) == 4.80
    # Sonnet 4.6: $3.00 in / $15.00 out per MTok.
    assert cost_usd("global.anthropic.claude-sonnet-4-6", 2_000_000, 0) == 6.00
    # Unknown model contributes 0 (never crashes a turn).
    assert cost_usd("some.unpriced.model", 1_000_000, 1_000_000) == 0.0


def test_record_usage_increments_counters() -> None:
    model = "global.anthropic.claude-haiku-4-5-metrictest"

    def tok(direction: str) -> float:
        return (
            REGISTRY.get_sample_value(
                "lily_bedrock_tokens_total", {"model": model, "direction": direction}
            )
            or 0.0
        )

    def cost() -> float:
        return REGISTRY.get_sample_value("lily_bedrock_cost_usd_total", {"model": model}) or 0.0

    in0, out0, cost0 = tok("input"), tok("output"), cost()
    record_usage(model, 1000, 500)
    assert tok("input") == in0 + 1000
    assert tok("output") == out0 + 500
    assert cost() > cost0  # priced model -> non-zero increment
