"""Index-jobs enqueue. Aurora is canonical; OpenSearch is derived. A changed
entity is marked `stale` in `ingestion.search_sync` and an index job is sent —
the embed job (later step) anti-joins on `content_hash` so unchanged rows never
re-embed (NFR-7 cost guard). The queue is injected (ParseQueue-style protocol)
so the ETL stays offline-testable."""

from __future__ import annotations

from typing import Protocol

import psycopg


class IndexQueue(Protocol):
    def enqueue_index(self, entity_type: str, entity_id: int) -> None: ...


def mark_stale_and_enqueue(
    conn: psycopg.Connection,
    queue: IndexQueue,
    *,
    entity_type: str,
    entity_id: int,
    content_hash: str,
    index_name: str = "default",
) -> bool:
    """Record the entity as needing (re)indexing and enqueue a job, unless the
    content_hash already matches an 'indexed' row (nothing changed). Returns
    True if a job was enqueued."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content_hash, status FROM ingestion.search_sync
            WHERE entity_type = %s AND entity_id = %s AND index_name = %s
            """,
            (entity_type, entity_id, index_name),
        )
        row = cur.fetchone()
    if row is not None and row[0] == content_hash and row[1] == "indexed":
        return False  # unchanged and already indexed — skip

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion.search_sync
                (entity_type, entity_id, index_name, content_hash, indexed_at, status)
            VALUES (%s, %s, %s, %s, now(), 'stale')
            ON CONFLICT (entity_type, entity_id, index_name) DO UPDATE SET
                content_hash = EXCLUDED.content_hash,
                indexed_at   = now(),
                status       = 'stale'
            """,
            (entity_type, entity_id, index_name, content_hash),
        )
    queue.enqueue_index(entity_type, entity_id)
    return True
