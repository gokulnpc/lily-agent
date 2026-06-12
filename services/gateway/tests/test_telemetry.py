"""Observability (CLAUDE.md per-service requirement): the /metrics endpoint
exposes the mandatory series, and a chat turn emits an OTel `chat.turn` span with
per-node events + intent attribute."""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from gateway import telemetry
from gateway.main import create_app
from lily_orchestrator.graph import build_graph
from lily_orchestrator.specialists import Deps


def _seed_compatible(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,source_url,scraped_at)"
            " VALUES ('PS11752778','Door Shelf Bin','refrigerator','https://x.test/p',now())"
        )
        cur.execute(
            "INSERT INTO catalog.models (model_number,brand,appliance_type,source_url,scraped_at)"
            " VALUES ('WDT780SAEM1','Whirlpool','dishwasher','https://x.test/m',now())"
        )
        cur.execute(
            "INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)"
            " SELECT p.part_id, m.model_id, 'https://x.test/s'"
            " FROM catalog.parts p, catalog.models m"
            " WHERE p.ps_number='PS11752778' AND m.model_number='WDT780SAEM1'"
        )
    conn.commit()


def test_metrics_endpoint_exposes_series() -> None:
    client = TestClient(create_app(graph=object()))  # no turn needed; series are registered
    body = client.get("/metrics").text
    for series in (
        "lily_chat_turns_total",
        "lily_chat_turn_seconds",
        "lily_graph_node_seconds",
        "lily_guardrail_blocks_total",
        "lily_invalid_identifiers_total",
    ):
        assert series in body


def test_turn_emits_trace_waterfall(conn: psycopg.Connection, fake_converse: type) -> None:
    telemetry.setup_tracing()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):  # a prior test may have left a no-op
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    _seed_compatible(conn)
    msg = "is PS11752778 compatible with my WDT780SAEM1 model?"
    bedrock = fake_converse({msg: ["compatibility"]})
    graph = build_graph(deps=Deps(conn=conn, bedrock=bedrock), checkpointer=MemorySaver())
    client = TestClient(create_app(graph=graph))
    client.post("/chat", json={"session_id": "tel", "message": msg})

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    turn = [s for s in spans if s.name == "chat.turn"][-1]
    assert turn.context is not None
    attrs = dict(turn.attributes or {})
    assert attrs["lily.intent"] == "compatibility"
    assert attrs["lily.session_id"] == "tel"

    # Per-node child spans (the waterfall), each parented to chat.turn.
    assert {"graph.router", "graph.specialist", "graph.validator"} <= names
    router = [s for s in spans if s.name == "graph.router"][-1]
    assert router.parent is not None
    assert router.parent.span_id == turn.context.span_id

    # Bedrock spans carry the model id (token usage = 0 from FakeConverse's no-usage
    # response) and nest under the turn too.
    bedrock = [s for s in spans if s.name == "bedrock.converse"]
    assert bedrock, "expected bedrock.converse spans"
    assert all("gen_ai.request.model" in dict(s.attributes or {}) for s in bedrock)
    last_bedrock = bedrock[-1]
    assert last_bedrock.parent is not None
    assert last_bedrock.parent.span_id == turn.context.span_id
