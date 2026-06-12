"""Index-jobs enqueue against compose Postgres with an in-memory queue."""

from __future__ import annotations

import psycopg

from lily_etl.index_jobs import mark_stale_and_enqueue


class FakeQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, int]] = []

    def enqueue_index(self, entity_type: str, entity_id: int) -> None:
        self.jobs.append((entity_type, entity_id))


def test_new_entity_enqueues(conn: psycopg.Connection) -> None:
    q = FakeQueue()
    enqueued = mark_stale_and_enqueue(
        conn, q, entity_type="part", entity_id=12345, content_hash="h1"
    )
    assert enqueued is True
    assert q.jobs == [("part", 12345)]


def test_unchanged_indexed_entity_skips(conn: psycopg.Connection) -> None:
    q = FakeQueue()
    mark_stale_and_enqueue(conn, q, entity_type="part", entity_id=22222, content_hash="h1")
    # mark it indexed (the embed job would do this)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion.search_sync SET status='indexed' "
            "WHERE entity_type='part' AND entity_id=22222"
        )
    q2 = FakeQueue()
    again = mark_stale_and_enqueue(conn, q2, entity_type="part", entity_id=22222, content_hash="h1")
    assert again is False  # unchanged + indexed -> skip (no re-embed, NFR-7)
    assert q2.jobs == []


def test_changed_hash_reenqueues(conn: psycopg.Connection) -> None:
    q = FakeQueue()
    mark_stale_and_enqueue(conn, q, entity_type="guide", entity_id=33333, content_hash="old")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion.search_sync SET status='indexed' "
            "WHERE entity_type='guide' AND entity_id=33333"
        )
    q2 = FakeQueue()
    again = mark_stale_and_enqueue(
        conn, q2, entity_type="guide", entity_id=33333, content_hash="new"
    )
    assert again is True  # content changed -> re-embed
    assert q2.jobs == [("guide", 33333)]
