"""Observability for the chat path (CLAUDE.md per-service requirement): Prometheus
metrics + OTel spans. Structured JSON logs (trace_id/session_id) come from
lily_common.logging. The OTLP exporter/collector is wired in Phase 4 — here we set
a TracerProvider with no exporter by default (spans are created, ready to export).
"""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Mandatory series (NFR-18): turns, full-turn + per-node latency, guardrail
# blocks, and FR-4 invalid-identifier hits.
TURNS = Counter("lily_chat_turns_total", "Chat turns", ["intent", "blocked"])
TURN_LATENCY = Histogram("lily_chat_turn_seconds", "Full chat-turn latency (s)")
NODE_LATENCY = Histogram("lily_graph_node_seconds", "Per graph-node latency (s)", ["node"])
GUARDRAIL_BLOCKS = Counter("lily_guardrail_blocks_total", "Input-guardrail blocks")
INVALID_IDS = Counter("lily_invalid_identifiers_total", "Turns with invalid identifiers (FR-4)")

_TRACER_NAME = "lily.gateway"
_configured = False


def setup_tracing(service: str = "gateway") -> None:
    """Idempotently install a TracerProvider. No exporter by default (Phase 4
    wires OTLP→collector); tests install their own in-memory exporter."""
    global _configured
    if _configured:
        return
    trace.set_tracer_provider(TracerProvider(resource=Resource.create({"service.name": service})))
    _configured = True


def tracer() -> Any:
    return trace.get_tracer(_TRACER_NAME)


def metrics_response() -> tuple[bytes, str]:
    """(_body, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
