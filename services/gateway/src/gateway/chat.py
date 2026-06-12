"""SSE chat protocol (FR-7). The gateway streams the LangGraph run as
Server-Sent Events so the frontend can show live progress.

Event vocabulary (the contract the frontend builds against):
  event: status   data: {"node": "<graph node>", "label": "Checking compatibility…"}
      One per meaningful graph node as it completes — ephemeral progress.
  event: message  data: {"text", "primary_intent", "blocked",
                         "invalid_identifiers", "citations", "structured",
                         "quick_replies", "current_model", "trace"}
      The final assistant turn. `invalid_identifiers` is the deterministic
      validator's verdict (always [] in a healthy turn — FR-4). `citations` is the
      source/citation URLs, `structured` the typed UI cards (product/comparison/
      order, kind-discriminated), and `quick_replies` the suggested action chips —
      all pulled STRUCTURALLY from the tool results (never parsed from prose); the
      frontend renders them as-is. `current_model` is the inference-profile id that
      handled the turn (graph state), surfaced as a model-tier badge.
  event: done     data: {"session_id", "trace_id"}
      Terminal. `trace_id` also returned in the `x-trace-id` response header.
  event: error    data: {"message", "trace_id"}
      A safe, user-facing failure line (details go to logs/traces, not the wire).

There is NO token-level delta event, BY DESIGN: streaming text before the
deterministic validator has seen it would let an unvalidated part number reach a
user, breaking FR-4. The per-node status events carry perceived latency instead.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from gateway import telemetry

log = logging.getLogger("gateway.chat")


class ChatRequest(BaseModel):
    session_id: str
    message: str


# Internal graph nodes (entry / output_guardrail / save) emit no status — they're
# plumbing. The rest map to a customer-facing, present-tense label.
_NODE_LABELS = {
    "input_guardrail": "Checking your request…",
    "router": "Understanding your question…",
    "validator": "Verifying part numbers…",
}
_SPECIALIST_LABELS = {
    "compatibility": "Checking compatibility…",
    "product": "Looking up the part…",
    "repair": "Diagnosing the issue…",
    "order": "Looking up your order…",
    # out_of_scope: no status — the decline speaks for itself.
}


def _status_label(node: str, state: dict[str, Any]) -> str | None:
    if node == "specialist":
        return _SPECIALIST_LABELS.get(state.get("primary_intent") or "")
    return _NODE_LABELS.get(node)


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


async def stream_chat(
    graph: Any, *, session_id: str, message: str, trace_id: str
) -> AsyncIterator[bytes]:
    """Drive one turn of the graph and yield SSE frames. Per-node status events
    stream as the graph advances; a final `message` then `done` close the turn."""
    config = {"configurable": {"thread_id": session_id}}
    state: dict[str, Any] = {}
    turn_start = time.perf_counter()
    span = telemetry.tracer().start_span("chat.turn")
    span.set_attribute("lily.trace_id", trace_id)
    span.set_attribute("lily.session_id", session_id)
    try:
        last = turn_start
        async for chunk in graph.astream({"utterance": message}, config, stream_mode="updates"):
            for node, delta in chunk.items():
                now = time.perf_counter()
                telemetry.NODE_LATENCY.labels(node=node).observe(now - last)
                span.add_event(node, {"elapsed_ms": round((now - last) * 1000, 1)})
                last = now
                if delta:
                    state.update(delta)
                label = _status_label(node, state)
                if label:
                    yield _sse("status", {"node": node, "label": label})

        intent = state.get("primary_intent") or "none"
        blocked = bool(state.get("blocked"))
        invalid = state.get("invalid_identifiers", [])
        telemetry.TURNS.labels(intent=intent, blocked=str(blocked).lower()).inc()
        if blocked:
            telemetry.GUARDRAIL_BLOCKS.inc()
        if invalid:
            telemetry.INVALID_IDS.inc()
        span.set_attribute("lily.intent", intent)
        span.set_attribute("lily.blocked", blocked)
        span.set_attribute("lily.invalid_identifier_count", len(invalid))
        log.info(
            "chat turn complete",
            extra={"session_id": session_id, "intent": intent, "blocked": blocked},
        )
        yield _sse(
            "message",
            {
                "text": state.get("response_text", ""),
                "primary_intent": state.get("primary_intent"),
                "blocked": blocked,
                "invalid_identifiers": invalid,
                "citations": state.get("citations", []),
                "structured": state.get("structured", []),
                "quick_replies": state.get("quick_replies", []),
                "current_model": state.get("current_model"),
                "trace": state.get("trace", []),
            },
        )
    except Exception:
        log.exception("chat turn failed", extra={"session_id": session_id})
        span.set_attribute("error", True)
        msg = "Sorry — something went wrong on our end. Please try again."
        yield _sse("error", {"message": msg, "trace_id": trace_id})
    finally:
        telemetry.TURN_LATENCY.observe(time.perf_counter() - turn_start)
        span.end()
        yield _sse("done", {"session_id": session_id, "trace_id": trace_id})
