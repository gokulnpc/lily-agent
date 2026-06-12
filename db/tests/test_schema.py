"""Verifies the approved Phase 1 schema against a live Postgres:

- the FR-13 compatibility query returns all four verdicts from one round trip
- compatibility upserts bump last_seen_at without duplicating rows
- the lookup paths are servable by index probes (no required seq scans)
- norm_id normalizes the way tool code expects
"""

from __future__ import annotations

from typing import Any

import psycopg

COMPATIBILITY_QUERY = """
SELECT
  CASE
    WHEN p.part_id  IS NULL     THEN 'PART_NOT_FOUND'
    WHEN m.model_id IS NULL     THEN 'MODEL_NOT_FOUND'
    WHEN c.part_id  IS NOT NULL THEN 'YES'
    ELSE 'NO'
  END AS verdict,
  c.source_url AS compatibility_source_url
FROM (SELECT 1) AS _
LEFT JOIN catalog.parts  p ON p.ps_number_norm    = %(part)s
LEFT JOIN catalog.models m ON m.model_number_norm = %(model)s
LEFT JOIN catalog.part_model_compatibility c
       ON c.part_id = p.part_id AND c.model_id = m.model_id
"""

SRC = "https://example.test/page"


def seed(conn: psycopg.Connection) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.parts (ps_number, name, appliance_type, source_url, scraped_at)
            VALUES ('PS11752778', 'Door Shelf Bin', 'refrigerator', %(src)s, now()),
                   ('PS99999901', 'Drain Pump', 'dishwasher', %(src)s, now())
            RETURNING part_id
            """,
            {"src": SRC},
        )
        part_ids = [row[0] for row in cur.fetchall()]
        cur.execute(
            """
            INSERT INTO catalog.models (model_number, brand, appliance_type, source_url, scraped_at)
            VALUES ('WDT780SAEM1', 'Whirlpool', 'dishwasher', %(src)s, now())
            RETURNING model_id
            """,
            {"src": SRC},
        )
        model_id = cur.fetchone()[0]  # type: ignore[index]
        cur.execute(
            """
            INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)
            VALUES (%(part)s, %(model)s, %(src)s)
            """,
            {"part": part_ids[0], "model": model_id, "src": SRC},
        )
    return {"fits": part_ids[0], "other": part_ids[1], "model": model_id}


def verdict(conn: psycopg.Connection, part: str, model: str) -> str:
    with conn.cursor() as cur:
        cur.execute(COMPATIBILITY_QUERY, {"part": part, "model": model})
        rows = cur.fetchall()
    assert len(rows) == 1, "lookup must always return exactly one row"
    return str(rows[0][0])


def test_four_verdicts(conn: psycopg.Connection) -> None:
    seed(conn)
    assert verdict(conn, "PS11752778", "WDT780SAEM1") == "YES"
    assert verdict(conn, "PS99999901", "WDT780SAEM1") == "NO"
    assert verdict(conn, "PS11752778", "NOPE123") == "MODEL_NOT_FOUND"
    assert verdict(conn, "PS00000000", "WDT780SAEM1") == "PART_NOT_FOUND"


def test_lookup_normalizes_user_formatting(conn: psycopg.Connection) -> None:
    seed(conn)
    # Tool code normalizes input with the same rule as catalog.norm_id; the
    # stored generated columns make "wdt-780 saem1" find "WDT780SAEM1".
    with conn.cursor() as cur:
        cur.execute("SELECT catalog.norm_id(%s)", ("wdt-780 saem1",))
        assert cur.fetchone() == ("WDT780SAEM1",)
        cur.execute("SELECT catalog.norm_id(%s)", ("ps 11752778",))
        assert cur.fetchone() == ("PS11752778",)


def test_upsert_bumps_last_seen_without_duplicates(conn: psycopg.Connection) -> None:
    ids = seed(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE catalog.part_model_compatibility
            SET last_seen_at = now() - interval '1 day'
            WHERE part_id = %(part)s AND model_id = %(model)s
            """,
            {"part": ids["fits"], "model": ids["model"]},
        )
        cur.execute(
            """
            INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)
            VALUES (%(fits)s, %(model)s, %(src)s)
            ON CONFLICT (part_id, model_id) DO UPDATE SET last_seen_at = now()
            """,
            {"fits": ids["fits"], "model": ids["model"], "src": SRC},
        )
        cur.execute(
            """
            SELECT count(*), max(last_seen_at) >= now() - interval '1 minute'
            FROM catalog.part_model_compatibility
            WHERE part_id = %(fits)s AND model_id = %(model)s
            """,
            {"fits": ids["fits"], "model": ids["model"]},
        )
        count, bumped = cur.fetchone()  # type: ignore[misc]
    assert count == 1
    assert bumped is True


def test_lookup_is_index_servable(conn: psycopg.Connection) -> None:
    """With seq scans disabled the planner must find index paths for every leg —
    proving the unique/PK indexes exist where the hot query needs them.
    (Tiny seed data means the planner would otherwise prefer seq scans.)"""
    seed(conn)
    with conn.cursor() as cur:
        cur.execute("SET LOCAL enable_seqscan = off")
        cur.execute(
            "EXPLAIN (FORMAT TEXT) " + COMPATIBILITY_QUERY,
            {"part": "PS11752778", "model": "WDT780SAEM1"},
        )
        plan = "\n".join(str(row[0]) for row in cur.fetchall())
    assert "Seq Scan" not in plan, plan
    assert "Index" in plan, plan
