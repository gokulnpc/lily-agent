"""Indexer skip-unchanged logic against compose Postgres, with fake OpenSearch
and Bedrock clients (no AWS)."""

from __future__ import annotations

import json

import psycopg

from lily_etl.indexer import IndexDoc, index_entity, load_symptom


class FakeBedrock:
    def __init__(self) -> None:
        self.calls = 0

    def invoke_model(self, *, modelId: str, body: str, **_: object) -> dict[str, object]:
        self.calls += 1

        class _B:
            def read(self) -> bytes:
                return json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode()

        return {"body": _B()}


class FakeOpenSearch:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, object]] = {}

    def index(self, *, index: str, id: str, body: dict[str, object], **_: object) -> None:
        self.docs[f"{index}/{id}"] = body


def _seed_symptom(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalog.symptoms
                (appliance_type, name, description, source_url, scraped_at, last_seen_at)
            VALUES ('refrigerator', 'Ice maker not making ice',
                    'The ice maker stopped producing ice.', 'https://x/Repair/Refrigerator/Not-Making-Ice/',
                    now(), now())
            RETURNING symptom_id
            """
        )
        row = cur.fetchone()
    assert row is not None
    return int(row[0])


def test_indexes_then_skips_unchanged(conn: psycopg.Connection) -> None:
    sid = _seed_symptom(conn)
    doc = load_symptom(conn, sid)
    assert doc is not None and doc.title == "Ice maker not making ice"

    bedrock, os_client = FakeBedrock(), FakeOpenSearch()

    # First pass: embeds + indexes.
    assert index_entity(conn, os_client, bedrock, doc) is True
    assert bedrock.calls == 1
    assert len(os_client.docs) == 1

    # Second pass, unchanged: skipped (no re-embed — NFR-7).
    assert index_entity(conn, os_client, bedrock, doc) is False
    assert bedrock.calls == 1  # unchanged


def test_changed_text_reindexes(conn: psycopg.Connection) -> None:
    sid = _seed_symptom(conn)
    doc = load_symptom(conn, sid)
    assert doc is not None
    bedrock, os_client = FakeBedrock(), FakeOpenSearch()
    index_entity(conn, os_client, bedrock, doc)

    # Simulate the description changing on re-crawl.
    changed = IndexDoc(
        entity_type=doc.entity_type,
        entity_id=doc.entity_id,
        corpus=doc.corpus,
        title=doc.title,
        body="A completely rewritten description.",
        appliance_type=doc.appliance_type,
        source_url=doc.source_url,
    )
    assert changed.content_hash != doc.content_hash
    assert index_entity(conn, os_client, bedrock, changed) is True
    assert bedrock.calls == 2  # re-embedded because content changed
