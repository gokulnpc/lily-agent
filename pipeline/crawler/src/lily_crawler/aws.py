"""boto3 adapters implementing the fetcher's BlobStore / ParseQueue protocols,
and the psycopg-backed SourcePageStore. Thin by design — exercised against real
AWS / compose Postgres, not in `make check`.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg


class S3BlobStore:
    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def put(self, key: str, body: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )


class SqsParseQueue:
    def __init__(self, client: Any, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    def enqueue_parse(self, url: str) -> None:
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps({"url": url}),
        )


class PgSourcePageStore:
    """source_pages reads/writes. content_hash unchanged ⇒ caller skips S3.

    The crawler IRSA role has no DB grants yet (Phase 1 wiring); the connection
    is injected so the runtime supplies ESO-synced credentials.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def content_hash(self, url: str) -> str | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT content_hash FROM ingestion.source_pages WHERE url = %s",
                (url,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def record_fetch(
        self,
        *,
        url: str,
        page_type: str,
        content_hash: str,
        s3_key: str,
        http_status: int,
        changed: bool,
    ) -> None:
        # Upsert: new pages insert; re-fetches update. last_changed_at and
        # parse_status only advance when the content actually changed.
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion.source_pages
                    (url, page_type, content_hash, s3_key, http_status,
                     last_fetched_at, last_changed_at, last_parsed_at, parse_status)
                VALUES (%(url)s, %(pt)s, %(hash)s, NULLIF(%(key)s, ''), %(status)s,
                        now(), now(), NULL, 'pending')
                ON CONFLICT (url) DO UPDATE SET
                    http_status     = EXCLUDED.http_status,
                    last_fetched_at = now(),
                    fetch_failure_count = 0,
                    content_hash    = CASE WHEN %(changed)s THEN EXCLUDED.content_hash
                                          ELSE ingestion.source_pages.content_hash END,
                    s3_key          = CASE WHEN %(changed)s THEN EXCLUDED.s3_key
                                          ELSE ingestion.source_pages.s3_key END,
                    last_changed_at = CASE WHEN %(changed)s THEN now()
                                          ELSE ingestion.source_pages.last_changed_at END,
                    parse_status    = CASE WHEN %(changed)s THEN 'pending'
                                          ELSE ingestion.source_pages.parse_status END
                """,
                {
                    "url": url,
                    "pt": page_type,
                    "hash": content_hash,
                    "key": s3_key,
                    "status": http_status,
                    "changed": changed,
                },
            )
        self._conn.commit()

    def record_failure(self, url: str, http_status: int) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingestion.source_pages
                    (url, page_type, http_status, last_fetched_at,
                     fetch_failure_count, parse_status)
                VALUES (%(url)s, 'other', %(status)s, now(), 1, 'pending')
                ON CONFLICT (url) DO UPDATE SET
                    http_status         = EXCLUDED.http_status,
                    last_fetched_at     = now(),
                    fetch_failure_count = ingestion.source_pages.fetch_failure_count + 1
                """,
                {"url": url, "status": http_status},
            )
        self._conn.commit()
