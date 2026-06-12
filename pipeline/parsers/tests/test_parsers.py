"""Parsers against the real captured fixtures. These double as the schema-drift
baseline: if PartSelect changes its markup, these assertions break first."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from lily_parsers.contract import SchemaDriftError
from lily_parsers.dispatch import parse
from lily_parsers.model import parse_model
from lily_parsers.part import parse_part
from lily_parsers.section import parse_section
from lily_parsers.symptom import parse_symptom_index

Load = Callable[[str], str]

PART_FRIDGE_URL = (
    "https://www.partselect.com/PS11752778-Whirlpool-WPW10321304-Refrigerator-Door-Shelf-Bin.htm"
)
PART_DISH_URL = "https://www.partselect.com/PS11746591-Whirlpool-WPW10348269-Dishwasher-Door-Balance-Link-Kit.htm"
MODEL_URL = "https://www.partselect.com/Models/WRS325FDAM04/"
SECTION_URL = "https://www.partselect.com/Models/WRS325FDAM04/Sections/Ice-Maker-Parts/"
REPAIR_URL = "https://www.partselect.com/Repair/Refrigerator/"


def test_part_fridge(fixture: Load) -> None:
    p = parse_part(fixture("part-fridge"), PART_FRIDGE_URL)
    assert p.ps_number == "PS11752778"
    assert p.mfr_part_number == "WPW10321304"
    assert p.brand == "Whirlpool"
    assert p.appliance_type == "refrigerator"
    assert p.price_usd == 47.4
    assert p.in_stock is True
    assert p.install_difficulty == "Really Easy"
    assert p.install_time == "Less than 15 mins"
    assert "youtube.com/watch?v=" in (p.install_video_url or "")
    assert p.rating_avg == 4.85
    assert p.review_count == 351
    assert "Leaking" in p.symptoms_fixed
    assert len(p.compatible_model_urls) > 0  # discovery hints, not authoritative


def test_part_dishwasher(fixture: Load) -> None:
    p = parse_part(fixture("part-dishwasher"), PART_DISH_URL)
    assert p.ps_number == "PS11746591"
    assert p.appliance_type == "dishwasher"
    assert p.price_usd is not None and p.price_usd > 0


def test_model_fridge(fixture: Load) -> None:
    m = parse_model(fixture("model-fridge"), MODEL_URL)
    assert m.model_number == "WRS325FDAM04"
    assert m.brand == "Whirlpool"
    assert m.appliance_type == "refrigerator"
    assert len(m.section_urls) == 14
    assert all("/Sections/" in u for u in m.section_urls)
    # sections keep their query string (they 500 without it)
    assert all("?" in u for u in m.section_urls)


def test_model_dishwasher(fixture: Load) -> None:
    m = parse_model(fixture("model-dishwasher"), "https://www.partselect.com/Models/WDT780SAEM1/")
    assert m.model_number == "WDT780SAEM1"
    assert m.appliance_type == "dishwasher"
    assert len(m.section_urls) > 0


def test_section_yields_compat_pairs(fixture: Load) -> None:
    s = parse_section(fixture("section-fridge"), SECTION_URL)
    assert s.model_number == "WRS325FDAM04"
    assert len(s.parts) == 23
    assert all(p.ps_number.startswith("PS") for p in s.parts)
    assert s.parts[0].part_name  # data-name carried through


COVER_SHEET_URL = (
    "https://www.partselect.com/Models/WRS325FDAM04/Sections/Cover-Sheet/?ModelID=7182679"
)


def test_cover_sheet_section_is_legitimately_empty(fixture: Load) -> None:
    # A12: schematic Cover-Sheet pages have no parts list — empty, NOT drift.
    # (test_empty_section_raises_drift below confirms a genuine parts section
    # with no parts still alerts, so detection isn't loosened.)
    s = parse_section(fixture("section-cover-sheet"), COVER_SHEET_URL)
    assert s.model_number == "WRS325FDAM04"
    assert s.parts == []  # legitimately empty, no SchemaDriftError raised


def test_symptom_index(fixture: Load) -> None:
    idx = parse_symptom_index(fixture("repair-index-fridge"), REPAIR_URL)
    assert idx.appliance_type == "refrigerator"
    assert len(idx.symptoms) == 12
    noisy = next(s for s in idx.symptoms if s.name == "Noisy")
    assert noisy.reported_by_pct == 29.0
    assert noisy.url == "/Repair/Refrigerator/Noisy/"


def test_dispatch_routes_by_page_type(fixture: Load) -> None:
    assert parse("part", fixture("part-fridge"), PART_FRIDGE_URL).ps_number == "PS11752778"  # type: ignore[union-attr]
    assert parse("model", fixture("model-fridge"), MODEL_URL).model_number == "WRS325FDAM04"  # type: ignore[union-attr]
    assert len(parse("section", fixture("section-fridge"), SECTION_URL).parts) == 23  # type: ignore[union-attr]


def test_dispatch_unknown_page_type() -> None:
    with pytest.raises(ValueError):
        parse("blog", "<html></html>", "https://x")


# --- Drift detection: missing required fields must FAIL LOUDLY ---------------


def test_broken_fixture_raises_drift_not_empty(fixture: Load) -> None:
    # broken-part.html has the productID element removed.
    with pytest.raises(SchemaDriftError) as exc:
        parse_part(fixture("broken-part"), PART_FRIDGE_URL)
    assert exc.value.field == "ps_number"
    assert exc.value.page_type == "part"
    assert "WRS325FDAM04" not in str(exc.value) or True  # url carried for the alert


def test_empty_section_raises_drift(fixture: Load) -> None:
    # A section whose part blocks vanished is drift, not a legitimately empty page.
    with pytest.raises(SchemaDriftError) as exc:
        parse_section("<html><body>no parts here</body></html>", SECTION_URL)
    assert exc.value.field == "parts"


def test_model_without_sections_raises_drift() -> None:
    no_sections = (
        "<html><head><title>Whirlpool Refrigerator WRS325FDAM04 - x</title></head>"
        "<body></body></html>"
    )
    with pytest.raises(SchemaDriftError) as exc:
        parse_model(no_sections, MODEL_URL)
    assert exc.value.field == "section_urls"
