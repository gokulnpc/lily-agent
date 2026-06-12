"""Catalog tools against compose Postgres. Seeds are rolled back per test."""

from __future__ import annotations

import psycopg

from lily_catalog.models import CompatibilityRequest
from lily_catalog.tools import check_compatibility, find_models, get_part_details

SRC = "https://example.test/section"


def _seed(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.parts
                (ps_number, name, appliance_type, part_category, price_usd, in_stock,
                 rating_avg, source_url, scraped_at)
            VALUES
                ('PS11752778','Door Shelf Bin','refrigerator','Door Bin',47.40,true,4.85,
                 %(s)s,now()),
                ('PS99999901','Crisper Drawer','refrigerator','Door Bin',31.00,true,4.10,
                 %(s)s,now()),
                ('PS88888801','Drain Pump','dishwasher','Pump',62.00,false,3.9,%(s)s,now())
            """,
            {"s": SRC},
        )
        cur.execute(
            """
            INSERT INTO catalog.models (model_number, brand, appliance_type, source_url, scraped_at)
            VALUES ('WRS325FDAM04','Whirlpool','refrigerator',%(s)s,now())
            """,
            {"s": SRC},
        )
        # PS11752778 + PS99999901 fit the model; PS88888801 does not.
        cur.execute(
            """
            INSERT INTO catalog.part_model_compatibility (part_id, model_id, source_url)
            SELECT p.part_id, m.model_id, %(s)s
            FROM catalog.parts p, catalog.models m
            WHERE p.ps_number IN ('PS11752778','PS99999901')
              AND m.model_number='WRS325FDAM04'
            """,
            {"s": SRC},
        )


def test_compatibility_yes(conn: psycopg.Connection) -> None:
    _seed(conn)
    r = check_compatibility(conn, CompatibilityRequest(part="PS11752778", model="WRS325FDAM04"))
    assert r.verdict == "YES"
    assert r.brand == "Whirlpool"
    assert r.citation_url == SRC


def test_compatibility_normalizes_formatting(conn: psycopg.Connection) -> None:
    _seed(conn)
    r = check_compatibility(conn, CompatibilityRequest(part="ps 11752778", model="wrs-325fdam04"))
    assert r.verdict == "YES"


def test_compatibility_no_returns_alternatives(conn: psycopg.Connection) -> None:
    _seed(conn)
    # PS88888801 (dishwasher pump) doesn't fit this fridge -> NO, with same-
    # category alternatives that DO fit (FR-14). Use a fridge part not compatible.
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,part_category,"
            "source_url,scraped_at) VALUES "
            "('PS70000001','Other Door Bin','refrigerator','Door Bin',%(s)s,now())",
            {"s": SRC},
        )
    r = check_compatibility(conn, CompatibilityRequest(part="PS70000001", model="WRS325FDAM04"))
    assert r.verdict == "NO"
    # Alternatives are Door Bin parts that fit the model.
    assert any(a.ps_number == "PS11752778" for a in r.alternatives)
    assert all(a.part_category == "Door Bin" for a in r.alternatives)


def test_compatibility_part_and_model_not_found(conn: psycopg.Connection) -> None:
    _seed(conn)
    assert (
        check_compatibility(
            conn, CompatibilityRequest(part="PS00000000", model="WRS325FDAM04")
        ).verdict
        == "PART_NOT_FOUND"
    )
    assert (
        check_compatibility(conn, CompatibilityRequest(part="PS11752778", model="NOPE99")).verdict
        == "MODEL_NOT_FOUND"
    )


def test_get_part_details(conn: psycopg.Connection) -> None:
    _seed(conn)
    d = get_part_details(conn, "PS11752778")
    assert d is not None
    assert d.name == "Door Shelf Bin"
    assert d.price_usd == 47.4
    assert d.rating_avg == 4.85
    assert get_part_details(conn, "PS00000000") is None


def test_find_models(conn: psycopg.Connection) -> None:
    _seed(conn)
    exact = find_models(conn, "wrs325fdam04")
    assert exact and exact[0].model_number == "WRS325FDAM04"
    partial = find_models(conn, "WRS325")
    assert any(m.model_number == "WRS325FDAM04" for m in partial)
