"""Retrieval tools: fake OpenSearch/Bedrock + real catalog enrichment."""

from __future__ import annotations

import json
from typing import Any

import psycopg

from lily_retrieval.models import DiagnoseRequest, SearchRequest
from lily_retrieval.tools import diagnose_symptom, search_parts
from lily_search.index import index_name

SRC = "https://example.test/x"


class FakeBedrock:
    """Returns a fixed vector; records call count."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke_model(self, **_: Any) -> dict[str, Any]:
        self.calls += 1

        class _Body:
            def read(self) -> bytes:
                return json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode()

        return {"body": _Body()}


class FakeOpenSearch:
    """Returns canned hits per index name."""

    def __init__(self, hits_by_index: dict[str, list[dict[str, Any]]]) -> None:
        self._hits = hits_by_index

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:
        return {"hits": {"hits": self._hits.get(index, [])}}


def _seed_part(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,price_usd,in_stock,"
            "source_url,scraped_at) VALUES "
            "('PS11752778','Door Shelf Bin','refrigerator',47.40,true,%(s)s,now())",
            {"s": SRC},
        )


def _seed_symptom(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.symptoms (appliance_type,name,description,source_url,scraped_at)"
            " VALUES ('refrigerator','Ice maker not making ice','The ice maker stopped.',"
            "%(s)s,now())",
            {"s": SRC},
        )


def test_search_parts_enriches_from_catalog(conn: psycopg.Connection) -> None:
    _seed_part(conn)
    os_client = FakeOpenSearch(
        {
            index_name("parts"): [
                {"_score": 9.1, "_source": {"ps_number": "PS11752778", "title": "x"}}
            ]
        }
    )
    bedrock = FakeBedrock()
    hits = search_parts(os_client, bedrock, conn, SearchRequest(text="door bin"))
    assert len(hits) == 1
    h = hits[0]
    assert h.ps_number == "PS11752778"
    assert h.name == "Door Shelf Bin"  # enriched from catalog, not the index title
    assert h.price_usd == 47.4 and h.in_stock is True
    assert bedrock.calls == 1  # embedded once


ICE_SRC = "https://example.test/Not-Making-Ice"
LIGHT_SRC = "https://example.test/Light-Not-Working"


def _seed_symptom_named(conn: psycopg.Connection, name: str, *, src: str = SRC) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.symptoms (appliance_type,name,description,source_url,scraped_at)"
            " VALUES ('refrigerator',%(n)s,%(n)s,%(s)s,now()) RETURNING symptom_id",
            {"n": name, "s": src},
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _seed_part_named(conn: psycopg.Connection, ps: str, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.parts (ps_number,name,appliance_type,price_usd,in_stock,"
            "source_url,scraped_at) VALUES (%(p)s,%(n)s,'refrigerator',10.0,true,%(s)s,now())"
            " RETURNING part_id",
            {"p": ps, "n": name, "s": SRC},
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _link_symptom_part(conn: psycopg.Connection, symptom_id: int, part_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO catalog.symptom_parts (symptom_id,part_id,display_rank,source_url,"
            "scraped_at,last_seen_at) VALUES (%(s)s,%(p)s,1,%(u)s,now(),now())",
            {"s": symptom_id, "p": part_id, "u": SRC},
        )


def test_diagnose_keeps_only_dominant_symptom_cluster(conn: psycopg.Connection) -> None:
    # The ice-maker blend: a sub-floor symptom's parts (and citation) must NOT
    # bleed into a clearly-dominant symptom's answer. Live scores: 9.37 vs 4.98;
    # 4.98 < 0.6 * 9.37 = 5.62 -> "Light not working" is dropped entirely.
    ice = _seed_symptom_named(conn, "Ice maker not making ice")
    light = _seed_symptom_named(conn, "Light not working")
    _link_symptom_part(conn, ice, _seed_part_named(conn, "PSICE0001", "Ice Maker Assembly"))
    _link_symptom_part(conn, light, _seed_part_named(conn, "PSLED0001", "LED Light Control Board"))
    os_client = FakeOpenSearch(
        {
            index_name("symptoms"): [
                {
                    "_score": 9.37,
                    "_source": {
                        "title": "Ice maker not making ice",
                        "body": "x",
                        "source_url": ICE_SRC,
                    },
                },
                {
                    "_score": 4.98,
                    "_source": {"title": "Light not working", "body": "y", "source_url": LIGHT_SRC},
                },
            ]
        }
    )
    d = diagnose_symptom(
        os_client, FakeBedrock(), conn, DiagnoseRequest(text="ice maker isn't working")
    )
    assert [s.name for s in d.symptoms] == ["Ice maker not making ice"]
    parts = [lp.ps_number for s in d.symptoms for lp in s.likely_parts]
    assert "PSICE0001" in parts and "PSLED0001" not in parts
    # The dropped symptom's citation disappears too.
    assert LIGHT_SRC not in [s.source_url for s in d.symptoms]


def test_diagnose_keeps_coequal_symptom_clusters(conn: psycopg.Connection) -> None:
    # A genuinely ambiguous query: two co-equal symptoms (close scores) both clear
    # the floor (6.5 >= 0.6 * 7.0 = 4.2) -> multi-symptom capability preserved.
    noisy = _seed_symptom_named(conn, "Noisy")
    leaking = _seed_symptom_named(conn, "Leaking")
    _link_symptom_part(conn, noisy, _seed_part_named(conn, "PSNOISE01", "Drain Pump"))
    _link_symptom_part(conn, leaking, _seed_part_named(conn, "PSLEAK01", "Door Gasket"))
    os_client = FakeOpenSearch(
        {
            index_name("symptoms"): [
                {"_score": 7.0, "_source": {"title": "Noisy", "body": "x", "source_url": SRC}},
                {"_score": 6.5, "_source": {"title": "Leaking", "body": "y", "source_url": SRC}},
            ]
        }
    )
    d = diagnose_symptom(os_client, FakeBedrock(), conn, DiagnoseRequest(text="loud and leaking"))
    assert sorted(s.name for s in d.symptoms) == ["Leaking", "Noisy"]
    parts = {lp.ps_number for s in d.symptoms for lp in s.likely_parts}
    assert parts == {"PSNOISE01", "PSLEAK01"}


def test_diagnose_symptom_returns_matches_with_empty_parts_note(conn: psycopg.Connection) -> None:
    _seed_symptom(conn)
    os_client = FakeOpenSearch(
        {
            index_name("symptoms"): [
                {
                    "_score": 11.1,
                    "_source": {
                        "title": "Ice maker not making ice",
                        "body": "The ice maker stopped.",
                        "source_url": SRC,
                    },
                }
            ]
        }
    )
    d = diagnose_symptom(os_client, FakeBedrock(), conn, DiagnoseRequest(text="ice maker broken"))
    assert len(d.symptoms) == 1
    assert d.symptoms[0].name == "Ice maker not making ice"
    # symptom_parts is empty (no ETL writer yet) -> no parts + an explanatory note.
    assert d.symptoms[0].likely_parts == []
    assert d.note is not None and "symptom_parts" in d.note.lower()
