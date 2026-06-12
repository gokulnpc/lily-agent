"""symptom_parts backfill (A14 / FR-17): part.symptoms_fixed -> curated
catalog.symptom_vocab (migration 0005) -> catalog.symptoms. Covers curly-
apostrophe normalization, appliance disambiguation, and the review-count ranking
fallback (no fix %). Against compose Postgres."""

from __future__ import annotations

import psycopg

from lily_etl.upsert import upsert_symptom_parts


def _part(cur: psycopg.Cursor, ps: str, appliance: str, symptoms: list[str], reviews: int) -> None:
    cur.execute(
        "INSERT INTO catalog.parts (ps_number, name, appliance_type, review_count, in_stock,"
        " symptoms_fixed, source_url, scraped_at, last_seen_at) "
        "VALUES (%s, %s, %s, %s, true, %s, %s, now(), now())",
        (ps, f"{ps} part", appliance, reviews, symptoms, f"https://x.test/{ps}"),
    )


def _symptom(cur: psycopg.Cursor, appliance: str, name: str) -> None:
    cur.execute(
        "INSERT INTO catalog.symptoms (appliance_type, name, source_url, scraped_at, last_seen_at)"
        " VALUES (%s, %s, 'https://x.test/sym', now(), now()) ON CONFLICT DO NOTHING",
        (appliance, name),
    )


def test_backfill_maps_normalizes_and_ranks(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        _symptom(cur, "refrigerator", "Ice maker not making ice")
        _symptom(cur, "refrigerator", "Leaking")
        _symptom(cur, "dishwasher", "Door latch failure")
        # Refrigerator parts that both fix "Ice maker not making ice" — different
        # review counts drive the FR-17 display_rank.
        _part(cur, "PS100", "refrigerator", ["Ice maker not making ice", "Leaking"], reviews=10)
        _part(cur, "PS200", "refrigerator", ["Ice maker not making ice"], reviews=99)
        # Dishwasher part whose phrase uses the live curly apostrophe (U+2019) —
        # must normalize to the straight-apostrophe vocab key.
        _part(cur, "PS300", "dishwasher", ["Door won\u2019t open or close"], reviews=5)
        conn.commit()

    n = upsert_symptom_parts(conn)
    assert n >= 4  # PS100->{ice,leaking}, PS200->{ice}, PS300->{latch}

    with conn.cursor() as cur:
        # Curly-apostrophe phrase mapped via the curated vocab (normalization works).
        cur.execute(
            "SELECT 1 FROM catalog.symptom_parts sp "
            "JOIN catalog.symptoms s ON s.symptom_id = sp.symptom_id "
            "JOIN catalog.parts p ON p.part_id = sp.part_id "
            "WHERE p.ps_number = 'PS300' AND s.name = 'Door latch failure'"
        )
        assert cur.fetchone() is not None
        # FR-17 ranking: higher review_count ranks first for the shared symptom.
        cur.execute(
            "SELECT p.ps_number FROM catalog.symptom_parts sp "
            "JOIN catalog.symptoms s ON s.symptom_id = sp.symptom_id "
            "JOIN catalog.parts p ON p.part_id = sp.part_id "
            "WHERE s.name = 'Ice maker not making ice' ORDER BY sp.display_rank"
        )
        ranked = [r[0] for r in cur.fetchall()]
        assert ranked == ["PS200", "PS100"]  # 99 reviews before 10


def test_backfill_is_idempotent(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        _symptom(cur, "refrigerator", "Leaking")
        _part(cur, "PS400", "refrigerator", ["Leaking"], reviews=1)
        conn.commit()
    first = upsert_symptom_parts(conn)
    conn.commit()
    upsert_symptom_parts(conn)  # second run must not duplicate (PK symptom_id,part_id)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM catalog.symptom_parts sp "
            "JOIN catalog.parts p ON p.part_id = sp.part_id WHERE p.ps_number = 'PS400'"
        )
        row = cur.fetchone()
    assert first >= 1 and row is not None and row[0] == 1
