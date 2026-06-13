"""Identifier extraction — PS numbers and model-number-shaped tokens. Used by the
entry node (session entity resolution) and the validator (FR-4 catalog check)."""

from __future__ import annotations

import re

# THE id format-tolerance, defined once. Mirror of the SQL `catalog.norm_id`
# (db/migrations/0001_init.sql: upper(regexp_replace(raw,'[^A-Za-z0-9]','','g'))).
# Both extraction (here) and DB lookups (norm_id) collapse the same way, so a
# user-typed "ps 11752778" / "wrs-325-sdhz" resolves identically to the stored
# normalized key. Keep this in lockstep with the SQL (test_entities locks it).
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def norm_id(raw: str) -> str:
    """Canonical id form: strip every non-alphanumeric, uppercase."""
    return _NON_ALNUM.sub("", raw).upper()


# PS numbers: PS + 3+ digits, tolerating the separators norm_id strips
# (whitespace / hyphen / dot) between the prefix and the digits.
_PS_RX = re.compile(r"\bPS[\s.\-]*\d{3,}\b", re.IGNORECASE)
# Model numbers: alphanumeric, >=5 chars, with both letters and digits (e.g.
# WDT780SAEM1, LFSS2612TF0). Case-insensitive (norm_id uppercases); excludes PS.
_MODEL_RX = re.compile(
    r"\b(?=[A-Z0-9-]{5,})(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9-]{4,}\b",
    re.IGNORECASE,
)


def extract_ps_numbers(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _PS_RX.finditer(text):
        seen.setdefault(norm_id(m.group(0)), None)
    return list(seen)


def extract_model_numbers(text: str) -> list[str]:
    """Model-shaped tokens, excluding PS numbers (those are parts, not models)."""
    ps = set(extract_ps_numbers(text))
    seen: dict[str, None] = {}
    for m in _MODEL_RX.finditer(text):
        tok = norm_id(m.group(0))
        if tok not in ps and not tok.startswith("PS"):
            seen.setdefault(tok, None)
    return list(seen)


_EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Order refs are alphanumeric (LILY-1001) or numeric (38123). After "order" or
# "#", capture a 4+-char alnum/hyphen token that contains at least one digit (the
# lookahead) so words like "order status" don't match.
_ORDER_TOKEN = r"((?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{3,})"
_ORDER_RX = re.compile(rf"\border\s*#?\s*{_ORDER_TOKEN}|#\s*{_ORDER_TOKEN}", re.IGNORECASE)


def extract_email(text: str) -> str | None:
    m = _EMAIL_RX.search(text)
    return m.group(0) if m else None


def extract_order_number(text: str) -> str | None:
    m = _ORDER_RX.search(text)
    if m:
        return m.group(1) or m.group(2)
    return None
