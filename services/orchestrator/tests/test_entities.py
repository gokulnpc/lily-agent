"""Identifier extraction — pure, offline."""

from __future__ import annotations

from lily_orchestrator.entities import extract_model_numbers, extract_ps_numbers


def test_extract_ps_numbers() -> None:
    assert extract_ps_numbers("is PS11752778 ok") == ["PS11752778"]
    assert extract_ps_numbers("ps11752778 and PS99999901") == ["PS11752778", "PS99999901"]
    assert extract_ps_numbers("no parts here") == []


def test_extract_model_numbers() -> None:
    assert extract_model_numbers("I have a WDT780SAEM1") == ["WDT780SAEM1"]
    assert "LFSS2612TF0" in extract_model_numbers("model LFSS2612TF0 please")
    # PS numbers are NOT models
    assert extract_model_numbers("PS11752778") == []
    # plain words and short tokens are excluded
    assert extract_model_numbers("does this fit my fridge") == []


def test_model_and_part_disambiguated() -> None:
    text = "is PS11752778 compatible with WDT780SAEM1"
    assert extract_ps_numbers(text) == ["PS11752778"]
    assert extract_model_numbers(text) == ["WDT780SAEM1"]
