"""Parsed DTOs → Aurora rows (the ETL write path).

Compatibility is **model-canonical (A9)**: pairs are written only from section
pages, so each pair carries one `source_page_id` (its section page) and the
per-page staleness janitor is sound.

Staleness without mid-crawl deletes: upserts bump `last_seen_at = now()`; after a
section's pairs are re-applied, `prune_section` deletes that section page's pairs
whose `last_seen_at < now()` — i.e. the ones that disappeared from the re-parsed
page. Running upsert + prune in ONE transaction means `now()` is the transaction
start for all of them: re-seen pairs (last_seen = now()) survive, vanished pairs
(last_seen from a prior, earlier transaction) are pruned.
"""

from __future__ import annotations

import psycopg

from lily_parsers.dto import ParsedModel, ParsedPart, ParsedSection, ParsedSymptomIndex


def source_page_id(conn: psycopg.Connection, url: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT source_page_id FROM ingestion.source_pages WHERE url = %s", (url,))
        row = cur.fetchone()
    return row[0] if row else None


def upsert_part(
    conn: psycopg.Connection, part: ParsedPart, *, source_url: str, source_page_id: int | None
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.parts
                (ps_number, mfr_part_number, name, brand, appliance_type, part_category,
                 price_usd, stock_status, in_stock, install_difficulty, install_time,
                 install_video_url, rating_avg, review_count, image_url,
                 source_url, source_page_id, scraped_at, last_seen_at)
            VALUES (%(ps)s, %(mpn)s, %(name)s, %(brand)s, %(appliance)s, %(category)s,
                    %(price)s, %(stock)s, %(in_stock)s, %(difficulty)s, %(time)s,
                    %(video)s, %(rating)s, %(reviews)s, %(image)s,
                    %(src)s, %(spid)s, now(), now())
            ON CONFLICT (ps_number_norm) DO UPDATE SET
                mfr_part_number    = EXCLUDED.mfr_part_number,
                name               = EXCLUDED.name,
                brand              = EXCLUDED.brand,
                appliance_type     = EXCLUDED.appliance_type,
                price_usd          = EXCLUDED.price_usd,
                stock_status       = EXCLUDED.stock_status,
                in_stock           = EXCLUDED.in_stock,
                install_difficulty = EXCLUDED.install_difficulty,
                install_time       = EXCLUDED.install_time,
                install_video_url  = EXCLUDED.install_video_url,
                rating_avg         = EXCLUDED.rating_avg,
                review_count       = EXCLUDED.review_count,
                image_url          = EXCLUDED.image_url,
                source_url         = EXCLUDED.source_url,
                source_page_id     = EXCLUDED.source_page_id,
                scraped_at         = now(),
                last_seen_at       = now(),
                updated_at         = now()
            RETURNING part_id
            """,
            {
                "ps": part.ps_number,
                "mpn": part.mfr_part_number,
                "name": part.name,
                "brand": part.brand,
                "appliance": part.appliance_type,
                "category": None,
                "price": part.price_usd,
                "stock": part.stock_status,
                "in_stock": part.in_stock,
                "difficulty": part.install_difficulty,
                "time": part.install_time,
                "video": part.install_video_url,
                "rating": part.rating_avg,
                "reviews": part.review_count,
                "image": part.image_url,
                "src": source_url,
                "spid": source_page_id,
            },
        )
        return _one(cur)


def upsert_model(
    conn: psycopg.Connection, model: ParsedModel, *, source_url: str, source_page_id: int | None
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.models
                (model_number, brand, name, appliance_type, source_url, source_page_id,
                 scraped_at, last_seen_at)
            VALUES (%(num)s, %(brand)s, %(name)s, %(appliance)s, %(src)s, %(spid)s, now(), now())
            ON CONFLICT (model_number_norm) DO UPDATE SET
                brand          = EXCLUDED.brand,
                name           = EXCLUDED.name,
                appliance_type = EXCLUDED.appliance_type,
                source_url     = EXCLUDED.source_url,
                source_page_id = EXCLUDED.source_page_id,
                scraped_at     = now(),
                last_seen_at   = now(),
                updated_at     = now()
            RETURNING model_id
            """,
            {
                "num": model.model_number,
                "brand": model.brand,
                "name": model.name,
                "appliance": model.appliance_type,
                "src": source_url,
                "spid": source_page_id,
            },
        )
        return _one(cur)


def _resolve_part_stub(
    conn: psycopg.Connection,
    ps_number: str,
    name: str,
    appliance_type: str,
    source_url: str,
    source_page_id: int | None,
) -> int:
    """Ensure a part row exists for a section-listed PS number, inserting a
    minimal stub if the part page hasn't been parsed yet. A later part-page
    upsert enriches it. ON CONFLICT keeps the existing (richer) row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.parts
                (ps_number, name, appliance_type, source_url, source_page_id,
                 scraped_at, last_seen_at)
            VALUES (%(ps)s, %(name)s, %(appliance)s, %(src)s, %(spid)s, now(), now())
            ON CONFLICT (ps_number_norm) DO UPDATE SET last_seen_at = now()
            RETURNING part_id
            """,
            {
                "ps": ps_number,
                "name": name or ps_number,
                "appliance": appliance_type,
                "src": source_url,
                "spid": source_page_id,
            },
        )
        return _one(cur)


def upsert_section_compat(
    conn: psycopg.Connection,
    section: ParsedSection,
    *,
    model_appliance_type: str,
    source_url: str,
    source_page_id: int,
) -> dict[str, int]:
    """Apply a section's compatibility pairs and prune the ones that vanished.

    Returns counts: {"upserted": n, "pruned": n}. Caller commits.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT model_id FROM catalog.models WHERE model_number_norm = catalog.norm_id(%s)",
            (section.model_number,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"model {section.model_number} not found — parse the model page first")
    model_id = row[0]

    upserted = 0
    for pair in section.parts:
        part_id = _resolve_part_stub(
            conn, pair.ps_number, pair.part_name, model_appliance_type, source_url, source_page_id
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog.part_model_compatibility
                    (part_id, model_id, source_url, source_page_id, last_seen_at)
                VALUES (%(part)s, %(model)s, %(src)s, %(spid)s, now())
                ON CONFLICT (part_id, model_id) DO UPDATE SET
                    source_url     = EXCLUDED.source_url,
                    source_page_id = EXCLUDED.source_page_id,
                    last_seen_at   = now()
                """,
                {"part": part_id, "model": model_id, "src": source_url, "spid": source_page_id},
            )
        upserted += 1

    # Janitor: same transaction, so now() == the upserts' now(). Pairs sourced
    # from THIS section page that weren't re-seen this run (last_seen from an
    # earlier transaction) are pruned.
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM catalog.part_model_compatibility
            WHERE model_id = %(model)s AND source_page_id = %(spid)s AND last_seen_at < now()
            """,
            {"model": model_id, "spid": source_page_id},
        )
        pruned = cur.rowcount

    return {"upserted": upserted, "pruned": pruned}


def upsert_symptom_index(
    conn: psycopg.Connection,
    index: ParsedSymptomIndex,
    *,
    source_url: str,
    source_page_id: int | None,
) -> int:
    count = 0
    for sym in index.symptoms:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalog.symptoms
                    (appliance_type, name, description, reported_by_pct, source_url,
                     source_page_id, scraped_at, last_seen_at)
                VALUES (%(appliance)s, %(name)s, %(desc)s, %(pct)s, %(src)s, %(spid)s,
                        now(), now())
                ON CONFLICT (appliance_type, name) DO UPDATE SET
                    description     = EXCLUDED.description,
                    reported_by_pct = EXCLUDED.reported_by_pct,
                    last_seen_at    = now(),
                    updated_at      = now()
                """,
                {
                    "appliance": index.appliance_type,
                    "name": sym.name,
                    "desc": sym.description,
                    "pct": sym.reported_by_pct,
                    "src": source_url + sym.url,
                    "spid": source_page_id,
                },
            )
        count += 1
    return count


def _one(cur: psycopg.Cursor) -> int:
    row = cur.fetchone()
    assert row is not None
    return int(row[0])
