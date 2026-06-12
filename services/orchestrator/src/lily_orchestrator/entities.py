"""Identifier extraction — PS numbers and model-number-shaped tokens. Used by the
entry node (session entity resolution) and the validator (FR-4 catalog check)."""

from __future__ import annotations

import re

# PS numbers: PS followed by digits.
_PS_RX = re.compile(r"\bPS\d{3,}\b", re.IGNORECASE)
# Model numbers: appliance models are alphanumeric, >=5 chars, with both letters
# and digits (e.g. WDT780SAEM1, LFSS2612TF0). Excludes pure PS numbers.
_MODEL_RX = re.compile(
    r"\b(?=[A-Z0-9-]{5,})(?=[A-Z0-9-]*[A-Z])(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9-]{4,}\b"
)


def extract_ps_numbers(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _PS_RX.finditer(text):
        seen.setdefault(m.group(0).upper(), None)
    return list(seen)


def extract_model_numbers(text: str) -> list[str]:
    """Model-shaped tokens, excluding PS numbers (those are parts, not models)."""
    ps = set(extract_ps_numbers(text))
    seen: dict[str, None] = {}
    for m in _MODEL_RX.finditer(text):
        tok = m.group(0).upper()
        if tok not in ps and not tok.startswith("PS"):
            seen.setdefault(tok, None)
    return list(seen)


_EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# An order number: digits, optionally after "order"/"#". Kept conservative.
_ORDER_RX = re.compile(r"\border\s*#?\s*(\d{4,})\b|#\s*(\d{4,})\b", re.IGNORECASE)


def extract_email(text: str) -> str | None:
    m = _EMAIL_RX.search(text)
    return m.group(0) if m else None


def extract_order_number(text: str) -> str | None:
    m = _ORDER_RX.search(text)
    if m:
        return m.group(1) or m.group(2)
    return None
