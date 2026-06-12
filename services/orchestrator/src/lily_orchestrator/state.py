"""Graph state — a TypedDict carrying the turn, routed intents, resolved session
entities, and the deterministic-validator output. Session fields persist across
turns via the checkpointer (keyed by thread_id)."""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    # This turn
    utterance: str
    response_text: str
    citations: list[str]  # source/citation URLs from the tool results (FR-19)
    tool_identifiers: list[str]  # PS/model ids the tools returned (validator trust set, FR-4)
    structured: list[dict[str, Any]]  # typed UI cards built from tool results (Phase 3)
    quick_replies: list[str]  # suggested action chips for the turn (Phase 3)

    # Session (persisted across turns by the checkpointer)
    current_model: str | None
    current_part: str | None
    brand: str | None
    summary: str | None
    order_number: str | None
    order_email: str | None

    # Routing
    intents: list[str]  # queue: primary first, then remaining (multi-intent)
    primary_intent: str | None
    pass_count: int

    # Guardrails + validation
    blocked: bool
    invalid_identifiers: list[str]  # PS/model numbers in the response not in the catalog

    # Trace (node names visited, for the demo)
    trace: list[str]


INTENTS = ("product", "compatibility", "repair", "order", "out_of_scope")
