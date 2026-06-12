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
