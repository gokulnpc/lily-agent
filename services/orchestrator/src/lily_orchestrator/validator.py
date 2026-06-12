"""Deterministic post-validator (FR-4): every PS/model-shaped identifier in a
response must be CONFIRMED — present in the catalog or echoed verbatim from this
turn's tool results. A token confirmed by neither is a likely hallucination and
goes in the returned list (flag-only until Phase-5 evals; no regenerate yet).

Precision matters: manufacturer part numbers (WPW10321304, filter codes like
EDR1RXD1) are model-SHAPED but live in part names / parts.mfr_part_number, not
catalog.models. The grounding contract guarantees the LLM only echoes
tool-sourced identifiers, so the trusted set is the UNION of:
  (1) identifiers the tools returned THIS turn (passed in via `allowed`),
  (2) parts.ps_number / parts.mfr_part_number,
  (3) catalog.models.model_number.
"""

from __future__ import annotations

import psycopg

from lily_orchestrator.entities import extract_model_numbers, extract_ps_numbers


def invalid_identifiers(
    conn: psycopg.Connection, response_text: str, *, allowed: list[str] | None = None
) -> list[str]:
    """PS/model-shaped tokens in the text confirmed by neither this turn's tool
    results (`allowed`) nor the catalog."""
    allowed_norm = {_norm(a) for a in (allowed or [])}
    invalid: list[str] = []
    seen: set[str] = set()
    for token in [*extract_ps_numbers(response_text), *extract_model_numbers(response_text)]:
        key = _norm(token)
        if key in seen:
            continue
        seen.add(key)
        if key in allowed_norm or _in_catalog(conn, token):
            continue
        invalid.append(token)
    return invalid


_CATALOG_SQL = """
SELECT
    EXISTS (
        SELECT 1 FROM catalog.parts
        WHERE ps_number_norm = catalog.norm_id(%(t)s)
           OR mfr_part_number_norm = catalog.norm_id(%(t)s)
    )
    OR EXISTS (
        SELECT 1 FROM catalog.models WHERE model_number_norm = catalog.norm_id(%(t)s)
    )
"""


def _in_catalog(conn: psycopg.Connection, token: str) -> bool:
    """True if the token is a known PS number, manufacturer part number, or model
    number (catalog.norm_id normalizes both sides, so punctuation/case don't matter)."""
    with conn.cursor() as cur:
        cur.execute(_CATALOG_SQL, {"t": token})
        row = cur.fetchone()
    return bool(row and row[0])


def _norm(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())
