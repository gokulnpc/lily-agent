"""End-to-end, fully offline: fixture HTML → parse → ETL upsert → Aurora → the
four-verdict compatibility query. No live crawl, no hand-seeded catalog rows.

Proves (1) PS11752778 x WRS325FDAM04 = YES through parsed-and-upserted data, and
(2) the staleness janitor: re-running bumps last_seen_at without duplicates, and
a pair that disappears from a re-parsed section is aged out.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg

from lily_etl.upsert import (
    upsert_model,
    upsert_part,
    upsert_section_compat,
)
from lily_parsers.dto import ParsedSection
from lily_parsers.model import parse_model
from lily_parsers.part import parse_part
from lily_parsers.section import parse_section

Load = Callable[[str], str]

PART_URL = (
    "https://www.partselect.com/PS11752778-Whirlpool-WPW10321304-Refrigerator-Door-Shelf-Bin.htm"
)
MODEL_URL = "https://www.partselect.com/Models/WRS325FDAM04/"
SECTION_URL = "https://www.partselect.com/Models/WRS325FDAM04/Sections/Refrigerator-Door-Parts/?ModelID=7182685&ModelNum=WRS325FDAM04"

COMPATIBILITY_QUERY = """
SELECT CASE
    WHEN p.part_id  IS NULL     THEN 'PART_NOT_FOUND'
    WHEN m.model_id IS NULL     THEN 'MODEL_NOT_FOUND'
    WHEN c.part_id  IS NOT NULL THEN 'YES'
    ELSE 'NO'
END
FROM (SELECT 1) AS _
LEFT JOIN catalog.parts  p ON p.ps_number_norm    = catalog.norm_id(%(part)s)
LEFT JOIN catalog.models m ON m.model_number_norm = catalog.norm_id(%(model)s)
LEFT JOIN catalog.part_model_compatibility c ON c.part_id = p.part_id AND c.model_id = m.model_id
"""


def _seed_source_page(conn: psycopg.Connection, url: str, page_type: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion.source_pages (url, page_type, parse_status, discovered_at)
            VALUES (%s, %s, 'parsed', now())
            ON CONFLICT (url) DO UPDATE SET parse_status = 'parsed'
            RETURNING source_page_id
            """,
            (url, page_type),
        )
        row = cur.fetchone()
    assert row is not None
    return int(row[0])


def _verdict(conn: psycopg.Connection, part: str, model: str) -> str:
    with conn.cursor() as cur:
        cur.execute(COMPATIBILITY_QUERY, {"part": part, "model": model})
        row = cur.fetchone()
    assert row is not None
    return str(row[0])


def _ingest_all(
    conn: psycopg.Connection, fixture: Load, section_name: str = "section-fridge-door"
) -> tuple[ParsedSection, int, dict[str, int]]:
    """The real pipeline order: model page -> part page -> section page."""
    model_spid = _seed_source_page(conn, MODEL_URL, "model")
    part_spid = _seed_source_page(conn, PART_URL, "part")
    section_spid = _seed_source_page(conn, SECTION_URL, "section")

    model = parse_model(fixture("model-fridge"), MODEL_URL)
    upsert_model(conn, model, source_url=MODEL_URL, source_page_id=model_spid)

    part = parse_part(fixture("part-fridge"), PART_URL)
    upsert_part(conn, part, source_url=PART_URL, source_page_id=part_spid)

    section = parse_section(fixture(section_name), SECTION_URL)
    counts = upsert_section_compat(
        conn,
        section,
        model_appliance_type=model.appliance_type,
        source_url=SECTION_URL,
        source_page_id=section_spid,
    )
    conn.commit()
    return section, section_spid, counts


def test_end_to_end_yes_from_parsed_data(conn: psycopg.Connection, fixture: Load) -> None:
    # Before ingest: part not in catalog.
    assert _verdict(conn, "PS11752778", "WRS325FDAM04") == "PART_NOT_FOUND"

    section, _, counts = _ingest_all(conn, fixture)
    assert counts["upserted"] > 0
    # The door-parts section really does list PS11752778.
    assert any(p.ps_number == "PS11752778" for p in section.parts)

    # THE proof: parsed-and-upserted data yields YES.
    assert _verdict(conn, "PS11752778", "WRS325FDAM04") == "YES"
    # Formatting-robust too (norm_id on both sides).
    assert _verdict(conn, "ps 11752778", "wrs-325-fdam04") == "YES"


def test_part_symptoms_fixed_persisted(conn: psycopg.Connection, fixture: Load) -> None:
    # 0004 / A14: the part page's "fixes the following symptoms" list is now
    # persisted (it was parsed but dropped before) — the source for the
    # symptoms_fixed -> catalog.symptoms vocab map that backfills symptom_parts.
    part_spid = _seed_source_page(conn, PART_URL, "part")
    part = parse_part(fixture("part-fridge"), PART_URL)
    assert "Leaking" in part.symptoms_fixed  # parser extracted it
    upsert_part(conn, part, source_url=PART_URL, source_page_id=part_spid)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symptoms_fixed FROM catalog.parts WHERE ps_number_norm = catalog.norm_id(%s)",
            ("PS11752778",),
        )
        row = cur.fetchone()
    assert row is not None
    assert "Leaking" in row[0]  # round-tripped through the new text[] column


def test_other_verdicts(conn: psycopg.Connection, fixture: Load) -> None:
    _ingest_all(conn, fixture)
    assert _verdict(conn, "PS11752778", "NONEXISTENTMODEL") == "MODEL_NOT_FOUND"
    assert _verdict(conn, "PS00000000", "WRS325FDAM04") == "PART_NOT_FOUND"


def test_janitor_reingest_bumps_last_seen_no_duplicates(
    conn: psycopg.Connection, fixture: Load
) -> None:
    section, section_spid, _ = _ingest_all(conn, fixture)
    n_pairs = len(section.parts)

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog.part_model_compatibility")
        before = cur.fetchone()[0]  # type: ignore[index]
        cur.execute(
            "SELECT last_seen_at FROM catalog.part_model_compatibility "
            "WHERE source_page_id = %s ORDER BY last_seen_at LIMIT 1",
            (section_spid,),
        )
        first_seen = cur.fetchone()[0]  # type: ignore[index]

    # Re-run the identical ETL.
    counts = upsert_section_compat(
        conn,
        parse_section(fixture("section-fridge-door"), SECTION_URL),
        model_appliance_type="refrigerator",
        source_url=SECTION_URL,
        source_page_id=section_spid,
    )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog.part_model_compatibility")
        after = cur.fetchone()[0]  # type: ignore[index]
        cur.execute(
            "SELECT min(last_seen_at) FROM catalog.part_model_compatibility "
            "WHERE source_page_id = %s",
            (section_spid,),
        )
        bumped = cur.fetchone()[0]  # type: ignore[index]

    assert after == before == n_pairs  # no duplicate pairs
    assert counts["pruned"] == 0  # nothing vanished
    assert bumped > first_seen  # last_seen_at advanced


def test_janitor_ages_out_vanished_pair(conn: psycopg.Connection, fixture: Load) -> None:
    _, section_spid, _ = _ingest_all(conn, fixture)
    assert _verdict(conn, "PS11752778", "WRS325FDAM04") == "YES"

    # Re-parse the section but drop PS11752778 (simulating it leaving the page).
    pruned_section = parse_section(fixture("section-fridge-door"), SECTION_URL)
    survivors = [p for p in pruned_section.parts if p.ps_number != "PS11752778"]
    object.__setattr__(pruned_section, "parts", survivors)

    counts = upsert_section_compat(
        conn,
        pruned_section,
        model_appliance_type="refrigerator",
        source_url=SECTION_URL,
        source_page_id=section_spid,
    )
    conn.commit()

    assert counts["pruned"] == 1  # the janitor removed exactly the vanished pair
    # The compatibility answer flips to NO — the part itself remains in the
    # catalog (still a real part), only the fitment was aged out.
    assert _verdict(conn, "PS11752778", "WRS325FDAM04") == "NO"
    # Survivors are untouched.
    assert counts["upserted"] == len(survivors)
