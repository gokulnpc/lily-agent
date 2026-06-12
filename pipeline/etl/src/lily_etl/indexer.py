"""Embed + index a catalog entity into OpenSearch, consistent with the
index-jobs skip-unchanged contract: if `search_sync` already has this entity at
the same content_hash and status 'indexed', we DON'T re-embed (Titan calls cost
money — NFR-7). All external clients (Aurora conn, OpenSearch, Bedrock) are
injected so the flow is testable without live services.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import psycopg

from lily_search.embeddings import embed_text
from lily_search.index import document, index_name


@dataclass(frozen=True)
class IndexDoc:
    entity_type: str
    entity_id: int
    corpus: str  # OpenSearch index suffix, e.g. "symptoms"
    title: str
    body: str
    appliance_type: str | None
    source_url: str

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}".strip()

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def load_symptom(conn: psycopg.Connection, symptom_id: int) -> IndexDoc | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT appliance_type, name, coalesce(description, ''), source_url "
            "FROM catalog.symptoms WHERE symptom_id = %s",
            (symptom_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    appliance, name, desc, src = row
    return IndexDoc(
        entity_type="symptom",
        entity_id=symptom_id,
        corpus="symptoms",
        title=name,
        body=desc,
        appliance_type=appliance,
        source_url=src,
    )


def _already_indexed(conn: psycopg.Connection, doc: IndexDoc, index: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT content_hash, status FROM ingestion.search_sync "
            "WHERE entity_type = %s AND entity_id = %s AND index_name = %s",
            (doc.entity_type, doc.entity_id, index),
        )
        row = cur.fetchone()
    return row is not None and row[0] == doc.content_hash and row[1] == "indexed"


def index_entity(
    conn: psycopg.Connection,
    os_client: Any,
    bedrock: Any,
    doc: IndexDoc,
) -> bool:
    """Embed and index `doc`, unless unchanged-and-indexed. Returns True if it
    (re)indexed, False if skipped. Marks search_sync 'indexed' on success."""
    index = index_name(doc.corpus)
    if _already_indexed(conn, doc, index):
        return False

    vector = embed_text(bedrock, doc.text)
    os_client.index(
        index=index,
        id=f"{doc.entity_type}:{doc.entity_id}",
        body=document(
            entity_type=doc.entity_type,
            entity_id=doc.entity_id,
            title=doc.title,
            body=doc.body,
            vector=vector,
            appliance_type=doc.appliance_type,
            source_url=doc.source_url,
            content_hash=doc.content_hash,
        ),
        refresh=True,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion.search_sync
                (entity_type, entity_id, index_name, content_hash, indexed_at, status)
            VALUES (%s, %s, %s, %s, now(), 'indexed')
            ON CONFLICT (entity_type, entity_id, index_name) DO UPDATE SET
                content_hash = EXCLUDED.content_hash, indexed_at = now(), status = 'indexed'
            """,
            (doc.entity_type, doc.entity_id, index, doc.content_hash),
        )
    conn.commit()
    return True
