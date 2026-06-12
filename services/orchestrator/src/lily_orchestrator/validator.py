"""Deterministic post-validator (FR-4): every PS/model number in a response must
exist in the catalog. Returns the list of identifiers that do NOT — a non-empty
list flags the response for regeneration (step 3) or graceful fallback."""

from __future__ import annotations

import psycopg

from lily_catalog.tools import find_models, get_part_details
from lily_orchestrator.entities import extract_model_numbers, extract_ps_numbers


def invalid_identifiers(conn: psycopg.Connection, response_text: str) -> list[str]:
    """PS/model numbers in the text that the catalog cannot confirm."""
    invalid: list[str] = []
    for ps in extract_ps_numbers(response_text):
        if get_part_details(conn, ps) is None:
            invalid.append(ps)
    for model in extract_model_numbers(response_text):
        if not _model_exists(conn, model):
            invalid.append(model)
    return invalid


def _model_exists(conn: psycopg.Connection, model: str) -> bool:
    # find_models matches on normalized exact OR partial; require an exact-norm hit.
    matches = find_models(conn, model, limit=5)
    target = model.upper()
    return any(_norm(m.model_number) == _norm(target) for m in matches)


def _norm(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())
