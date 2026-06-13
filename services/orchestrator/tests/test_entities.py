"""Identifier extraction — pure, offline."""

from __future__ import annotations

from lily_orchestrator.entities import (
    extract_model_numbers,
    extract_order_number,
    extract_ps_numbers,
    norm_id,
)


def test_norm_id_mirrors_sql() -> None:
    # Must match catalog.norm_id (db/migrations/0001_init.sql):
    # upper(regexp_replace(raw, '[^A-Za-z0-9]', '', 'g')). One tolerance, two layers.
    assert norm_id("ps 11752778") == "PS11752778"
    assert norm_id("wrs-325-sdhz") == "WRS325SDHZ"
    assert norm_id("LILY-1001") == "LILY1001"
    assert norm_id("PS11752778") == "PS11752778"


def test_extract_ps_numbers() -> None:
    assert extract_ps_numbers("is PS11752778 ok") == ["PS11752778"]
    assert extract_ps_numbers("ps11752778 and PS99999901") == ["PS11752778", "PS99999901"]
    assert extract_ps_numbers("no parts here") == []
    # Separator tolerance (mirrors norm_id) — resolves the same forms the DB collapses.
    assert extract_ps_numbers("is ps 11752778 compatible") == ["PS11752778"]
    assert extract_ps_numbers("part PS-11752778") == ["PS11752778"]


def test_extract_model_numbers() -> None:
    assert extract_model_numbers("I have a WDT780SAEM1") == ["WDT780SAEM1"]
    assert "LFSS2612TF0" in extract_model_numbers("model LFSS2612TF0 please")
    # Case + separator tolerance (mirrors norm_id).
    assert extract_model_numbers("my wrs325sdhz fridge") == ["WRS325SDHZ"]
    assert extract_model_numbers("model WRS-325-SDHZ") == ["WRS325SDHZ"]
    # PS numbers are NOT models
    assert extract_model_numbers("PS11752778") == []
    # plain words and short tokens are excluded
    assert extract_model_numbers("does this fit my fridge") == []


def test_model_and_part_disambiguated() -> None:
    text = "is PS11752778 compatible with WDT780SAEM1"
    assert extract_ps_numbers(text) == ["PS11752778"]
    assert extract_model_numbers(text) == ["WDT780SAEM1"]


def test_extract_order_number() -> None:
    # Alphanumeric (the demo orders) and numeric (the PRD example) both work.
    assert extract_order_number("Where is my order LILY-1001, email a@b.com?") == "LILY-1001"
    assert extract_order_number("order 38123 please") == "38123"
    assert extract_order_number("track order #LILY-1004") == "LILY-1004"
    # A 'digit required' lookahead keeps non-order phrases out.
    assert extract_order_number("what is my order status?") is None
    assert extract_order_number("I want to order a shelf bin") is None
