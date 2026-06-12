"""Assembles the agent StateGraph (D5 topology):

  entry → input_guardrail → router → [specialist] → validator → output_guardrail → save → END
                               ▲           │
                               └─ remaining intent, pass_count < 2 ─┘

The router (Haiku Converse) and the validator (catalog SQL) are real; the
guardrails and specialists are stubs (step 2). Bedrock client, conn, and the
checkpointer are injected so tests run offline (FakeConverse + MemorySaver) and
prod uses live Bedrock + a Redis checkpointer.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from lily_orchestrator import router as router_mod
from lily_orchestrator.converse import DEFAULT_ROUTER_MODEL
from lily_orchestrator.entities import extract_model_numbers, extract_ps_numbers
from lily_orchestrator.specialists import SPECIALISTS, Deps
from lily_orchestrator.state import GraphState
from lily_orchestrator.validator import invalid_identifiers

MAX_PASSES = 2


def build_graph(
    *,
    bedrock: Any,
    deps: Deps,
    checkpointer: Any,
    router_model: str = DEFAULT_ROUTER_MODEL,
) -> Any:
    """Compile the graph. `deps` carries the DB conn + search clients for the
    specialists/validator; `bedrock` drives the router; `checkpointer` persists
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
        return update

    def input_guardrail(state: GraphState) -> GraphState:
        # Stub: pass-through (Bedrock Guardrails + Haiku scope classifier in step 3).
        return {"trace": [*state.get("trace", []), "input_guardrail"], "blocked": False}

    def route(state: GraphState) -> GraphState:
        trace = [*state.get("trace", []), "router"]
        intents = state.get("intents")
        if not intents:  # first pass this turn — classify
            intents = router_mod.classify(bedrock, state["utterance"], model_id=router_model)
        primary = intents[0]
        return {"trace": trace, "intents": intents, "primary_intent": primary}

    def specialist(state: GraphState) -> GraphState:
        primary = state["primary_intent"]
        assert primary is not None
        text = SPECIALISTS[primary](state, deps)
        remaining = [i for i in state.get("intents", []) if i != primary]
        return {
            "trace": [*state.get("trace", []), f"specialist:{primary}"],
            "response_text": text,
            "intents": remaining,
            "pass_count": state.get("pass_count", 0) + 1,
        }

    def validator(state: GraphState) -> GraphState:
        bad = invalid_identifiers(deps.conn, state.get("response_text", ""))
        return {"trace": [*state.get("trace", []), "validator"], "invalid_identifiers": bad}

    def output_guardrail(state: GraphState) -> GraphState:
        return {"trace": [*state.get("trace", []), "output_guardrail"]}

    def save(state: GraphState) -> GraphState:
        return {"trace": [*state.get("trace", []), "save"]}

    def after_specialist(state: GraphState) -> str:
        # Multi-intent: loop back to the router for the next intent, bounded.
        if state.get("intents") and state.get("pass_count", 0) < MAX_PASSES:
            return "router"
        return "validator"

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
    g.add_edge("input_guardrail", "router")
    g.add_edge("router", "specialist")
    g.add_conditional_edges(
        "specialist", after_specialist, {"router": "router", "validator": "validator"}
    )
    g.add_edge("validator", "output_guardrail")
    g.add_edge("output_guardrail", "save")
    g.add_edge("save", END)

    return g.compile(checkpointer=checkpointer)
