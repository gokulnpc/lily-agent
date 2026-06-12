"""Validator precision (FR-4): a model-shaped token is confirmed by the UNION of
this turn's tool identifiers + parts.mfr_part_number + catalog.models/parts; a
token confirmed by none still flags. Against compose Postgres."""

from __future__ import annotations

import psycopg

from lily_orchestrator.validator import invalid_identifiers


def _seed(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number, mfr_part_number, name, appliance_type,"
            " source_url, scraped_at) VALUES "
            "('PS11752778','WPW10321304','Door Shelf Bin','refrigerator','https://x.test/p',now())"
            " ON CONFLICT (ps_number_norm) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO catalog.models (model_number, brand, appliance_type, source_url,"
            " scraped_at) VALUES ('WDT780SAEM1','Whirlpool','dishwasher','https://x.test/m',now())"
            " ON CONFLICT (model_number_norm) DO NOTHING"
        )
    # No commit: the rollback-isolated `conn` fixture sees its own uncommitted rows
    # (the validator queries this same connection).


def test_real_mpn_passes_fabricated_flags(conn: psycopg.Connection) -> None:
    _seed(conn)

    # (1) A real MPN echoed from THIS turn's tool data (allowed) — not flagged,
    # even though it isn't in the catalog at all.
    assert invalid_identifiers(conn, "Use part W10854221.", allowed=["W10854221"]) == []

    # (2) A real MPN in the catalog (parts.mfr_part_number) — not flagged, even
    # with no `allowed` (the case that previously false-flagged live).
    assert invalid_identifiers(conn, "The part is WPW10321304.") == []

    # Real PS number + real model — not flagged.
    assert invalid_identifiers(conn, "PS11752778 fits WDT780SAEM1.") == []

    # (3) A fabricated PS number — still flagged (real hallucination).
    assert invalid_identifiers(conn, "Try PS00000000.") == ["PS00000000"]

    # (4) A fabricated MPN/model-shaped token, in neither tool data nor catalog —
    # still flagged.
    bad = invalid_identifiers(conn, "Order WPW99999999 today.")
    assert "WPW99999999" in bad


def test_norm_handles_punctuation_variants(conn: psycopg.Connection) -> None:
    _seed(conn)
    # A trailing-dash capture of a real MPN normalizes to the same id -> not flagged.
    assert invalid_identifiers(conn, "part WPW10321304- here") == []
