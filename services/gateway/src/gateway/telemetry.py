"""Observability for the chat path (CLAUDE.md per-service requirement): Prometheus
metrics + OTel spans. Structured JSON logs (trace_id/session_id) come from
lily_common.logging. The OTLP exporter/collector is wired in Phase 4 — here we set
a TracerProvider with no exporter by default (spans are created, ready to export).
"""

from __future__ import annotations

import os
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Mandatory series (NFR-18): turns, full-turn + per-node latency, guardrail
# blocks, and FR-4 invalid-identifier hits.
TURNS = Counter("lily_chat_turns_total", "Chat turns", ["intent", "blocked"])
TURN_LATENCY = Histogram("lily_chat_turn_seconds", "Full chat-turn latency (s)")
NODE_LATENCY = Histogram("lily_graph_node_seconds", "Per graph-node latency (s)", ["node"])
GUARDRAIL_BLOCKS = Counter("lily_guardrail_blocks_total", "Input-guardrail blocks")
INVALID_IDS = Counter("lily_invalid_identifiers_total", "Turns with invalid identifiers (FR-4)")
FEEDBACK = Counter("lily_feedback_total", "Per-message feedback (FR-25)", ["rating"])

_TRACER_NAME = "lily.gateway"
_configured = False


def setup_tracing(service: str = "gateway") -> None:
    """Idempotently install a TracerProvider. The OTLP exporter is wired only when
    OTEL_EXPORTER_OTLP_ENDPOINT is set (so offline/dev and tests stay exporter-free
    and install their own in-memory exporter). In-cluster the env points at Jaeger's
    OTLP HTTP receiver."""
    global _configured
    if _configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        # Imported lazily so the exporter package is only needed where it's used.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def tracer() -> Any:
    return trace.get_tracer(_TRACER_NAME)


def metrics_response() -> tuple[bytes, str]:
    """(_body, content_type) for the /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
