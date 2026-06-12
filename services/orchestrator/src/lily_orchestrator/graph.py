"""Assembles the agent StateGraph (D5 topology):

  entry → input_guardrail ─(blocked)─────────────────────────────────→ save → END
              │ (pass)                                                    ↑
              └→ router → [specialist] → validator → output_guardrail ────┘
                   ▲           │
                   └─ remaining intent, pass_count < 2 ─┘

All stages are real: input_guardrail (Bedrock Guardrails + Haiku scope gate,
short-circuiting to a single decline), router (Haiku), specialists (Sonnet,
grounded), the deterministic part-number validator, and output_guardrail (Bedrock
PII + Haiku topicality). Bedrock client, conn, search, and checkpointer are
injected so tests run offline (FakeConverse + MemorySaver; no guardrail id ⇒ the
Bedrock layer is skipped) and prod uses live Bedrock + a Redis checkpointer.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from lily_orchestrator import guardrails
from lily_orchestrator import router as router_mod
from lily_orchestrator.converse import DEFAULT_ROUTER_MODEL
from lily_orchestrator.entities import (
    extract_email,
    extract_model_numbers,
    extract_order_number,
    extract_ps_numbers,
)
from lily_orchestrator.specialists import SPECIALISTS, Deps
from lily_orchestrator.state import GraphState
from lily_orchestrator.validator import invalid_identifiers

MAX_PASSES = 2


def build_graph(
    *,
    deps: Deps,
    checkpointer: Any,
    router_model: str = DEFAULT_ROUTER_MODEL,
) -> Any:
    """Compile the graph. `deps` carries the DB conn + Bedrock + search clients
    (the router and specialists share `deps.bedrock`); `checkpointer` persists
    session state across turns."""

    def entry(state: GraphState) -> GraphState:
        # Reset per-turn fields (trace/intents/pass_count are not session state);
        # current_model/current_part/summary persist via the checkpointer.
        utterance = state["utterance"]
        update: GraphState = {"trace": ["entry"], "pass_count": 0, "intents": []}
        # Entity resolution: a fresh PS/model in the turn updates session; a
        # pronoun ("it") with no new entity keeps the session value.
        ps = extract_ps_numbers(utterance)
        models = extract_model_numbers(utterance)
        if ps:
            update["current_part"] = ps[0]
        if models:
            update["current_model"] = models[0]
        email = extract_email(utterance)
        order_number = extract_order_number(utterance)
        if email:
            update["order_email"] = email
        if order_number:
            update["order_number"] = order_number
        return update

    def input_guardrail(state: GraphState) -> GraphState:
        # D6 input chain: Bedrock Guardrails -> Haiku scope gate, short-circuit on
        # the first block. A block produces ONE polite decline (skips the router +
        # specialist entirely). A pass carries the PII-masked utterance forward.
        verdict = guardrails.input_guard(
            deps.bedrock,
            state["utterance"],
            guardrail_id=deps.guardrail_id,
            version=deps.guardrail_version,
            model_id=router_model,
        )
        trace = [*state.get("trace", []), "input_guardrail"]
        if verdict.blocked:
            return {"trace": trace, "blocked": True, "response_text": guardrails.DECLINE}
        return {"trace": trace, "blocked": False, "utterance": verdict.text}

    def route(state: GraphState) -> GraphState:
        trace = [*state.get("trace", []), "router"]
        intents = state.get("intents")
        if not intents:  # first pass this turn — classify
            intents = router_mod.classify(deps.bedrock, state["utterance"], model_id=router_model)
        primary = intents[0]
        return {"trace": trace, "intents": intents, "primary_intent": primary}

    def specialist(state: GraphState) -> GraphState:
        primary = state["primary_intent"]
        assert primary is not None
        reply = SPECIALISTS[primary](state, deps)
        remaining = [i for i in state.get("intents", []) if i != primary]
        # Accumulate citations + tool-returned identifiers across multi-intent
        # passes, deduped, order-preserving.
        cites = [*state.get("citations", [])]
        cites += [c for c in reply.citations if c not in cites]
        tool_ids = [*state.get("tool_identifiers", [])]
        tool_ids += [i for i in reply.tool_identifiers if i not in tool_ids]
        quick = [*state.get("quick_replies", [])]
        quick += [q for q in reply.quick_replies if q not in quick]
        # Cards: dedup product cards by ps_number; keep comparison/order singletons.
        structured = [*state.get("structured", [])]
        seen_ps = {c.get("ps_number") for c in structured if c.get("kind") == "product"}
        for card in reply.structured:
            if card.get("kind") == "product":
                if card.get("ps_number") in seen_ps:
                    continue
                seen_ps.add(card.get("ps_number"))
            structured.append(card)
        return {
            "trace": [*state.get("trace", []), f"specialist:{primary}"],
            "response_text": reply.text,
            "citations": cites,
            "tool_identifiers": tool_ids,
            "structured": structured,
            "quick_replies": quick,
            "intents": remaining,
            "pass_count": state.get("pass_count", 0) + 1,
        }

    def validator(state: GraphState) -> GraphState:
        bad = invalid_identifiers(
            deps.conn,
            state.get("response_text", ""),
            allowed=state.get("tool_identifiers", []),
        )
        return {"trace": [*state.get("trace", []), "validator"], "invalid_identifiers": bad}

    def output_guardrail(state: GraphState) -> GraphState:
        # D6 output chain (after the deterministic validator): Bedrock PII pass +
        # Haiku topicality backstop. Masks PII in the response; an off-topic
        # response is replaced by the safe decline.
        verdict = guardrails.output_guard(
            deps.bedrock,
            state.get("response_text", ""),
            guardrail_id=deps.guardrail_id,
            version=deps.guardrail_version,
            model_id=router_model,
        )
        return {
            "trace": [*state.get("trace", []), "output_guardrail"],
            "response_text": verdict.text,
        }

    def save(state: GraphState) -> GraphState:
        return {"trace": [*state.get("trace", []), "save"]}

    def after_specialist(state: GraphState) -> str:
        # Multi-intent: loop back to the router for the next intent, bounded.
        if state.get("intents") and state.get("pass_count", 0) < MAX_PASSES:
            return "router"
        return "validator"

    def after_input_guard(state: GraphState) -> str:
        # Blocked input short-circuits straight to save with the decline already
        # set — no router, no specialist LLM call, no double decline.
        return "save" if state.get("blocked") else "router"

    g = StateGraph(GraphState)
    g.add_node("entry", entry)
    g.add_node("input_guardrail", input_guardrail)
    g.add_node("router", route)
    g.add_node("specialist", specialist)
    g.add_node("validator", validator)
    g.add_node("output_guardrail", output_guardrail)
    g.add_node("save", save)

    g.set_entry_point("entry")
    g.add_edge("entry", "input_guardrail")
    g.add_conditional_edges(
        "input_guardrail", after_input_guard, {"router": "router", "save": "save"}
    )
    g.add_edge("router", "specialist")
    g.add_conditional_edges(
        "specialist", after_specialist, {"router": "router", "validator": "validator"}
    )
    g.add_edge("validator", "output_guardrail")
    g.add_edge("output_guardrail", "save")
    g.add_edge("save", END)

    return g.compile(checkpointer=checkpointer)
