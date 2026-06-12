"""ETL worker: drain parse-jobs → read raw HTML from S3 → parse → upsert Aurora
→ enqueue discovered URLs (crawl-jobs) and index-jobs. Parsers read ONLY from
S3, so this never re-fetches the source site.

    python -m lily_etl.runner

Env: LILY_DATABASE_URL, LILY_RAW_BUCKET, LILY_PARSE_QUEUE_URL,
     LILY_CRAWL_QUEUE_URL, LILY_INDEX_QUEUE_URL.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import boto3
import psycopg

from lily_etl import upsert
from lily_parsers.dispatch import parse
from lily_parsers.dto import ParsedModel, ParsedPart, ParsedSection, ParsedSymptomIndex


def _read_s3(s3: Any, bucket: str, key: str) -> str:
    body: bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    return body.decode("utf-8")


def process(conn: psycopg.Connection, s3: Any, crawl_q: Any, *, bucket: str, url: str) -> str:
    """Parse one fetched page from S3 and apply it. Returns the page_type, or
    raises (the worker marks parse_status='failed' and lets SQS DLQ it)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_page_id, page_type, s3_key FROM ingestion.source_pages WHERE url = %s",
            (url,),
        )
        row = cur.fetchone()
    if row is None or row[2] is None:
        raise ValueError(f"no fetched source_page for {url}")
    spid, page_type, s3_key = row

    html = _read_s3(s3, bucket, s3_key)
    result = parse(page_type, html, url)

    if isinstance(result, ParsedPart):
        upsert.upsert_part(conn, result, source_url=url, source_page_id=spid)
    elif isinstance(result, ParsedModel):
        upsert.upsert_model(conn, result, source_url=url, source_page_id=spid)
        # Discover section pages (the completeness path) — cap-governed enqueue.
        for section_url in result.section_urls:
            crawl_q.enqueue(section_url, "section")
    elif isinstance(result, ParsedSection):
        upsert.upsert_section_compat(
            conn,
            result,
            model_appliance_type=_appliance_for_model(conn, result.model_number),
            source_url=url,
            source_page_id=spid,
        )
    elif isinstance(result, ParsedSymptomIndex):
        upsert.upsert_symptom_index(conn, result, source_url=url.rstrip("/"), source_page_id=spid)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingestion.source_pages SET parse_status='parsed', last_parsed_at=now() "
            "WHERE source_page_id=%s",
            (spid,),
        )
    conn.commit()
    return str(page_type)


def _appliance_for_model(conn: psycopg.Connection, model_number: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT appliance_type FROM catalog.models "
            "WHERE model_number_norm = catalog.norm_id(%s)",
            (model_number,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"model {model_number} not parsed before its section")
    return str(row[0])


class _CrawlEnqueuer:
    def __init__(self, sqs: Any, queue_url: str) -> None:
        self._sqs = sqs
        self._queue_url = queue_url

    def enqueue(self, url: str, page_type: str) -> None:
        self._sqs.send_message(
            QueueUrl=self._queue_url, MessageBody=json.dumps({"url": url, "page_type": page_type})
        )


def main() -> int:
    sqs = boto3.client("sqs")
    s3 = boto3.client("s3")
    bucket = os.environ["LILY_RAW_BUCKET"]
    parse_q = os.environ["LILY_PARSE_QUEUE_URL"]
    crawl = _CrawlEnqueuer(sqs, os.environ["LILY_CRAWL_QUEUE_URL"])
    conn = psycopg.connect(os.environ["LILY_DATABASE_URL"])

    while True:
        msgs = sqs.receive_message(QueueUrl=parse_q, MaxNumberOfMessages=1, WaitTimeSeconds=20).get(
            "Messages", []
        )
        if not msgs:
            break
        for msg in msgs:
            url = json.loads(msg["Body"])["url"]
            try:
                pt = process(conn, s3, crawl, bucket=bucket, url=url)
                sqs.delete_message(QueueUrl=parse_q, ReceiptHandle=msg["ReceiptHandle"])
                print(f"parsed {pt}: {url}")
            except Exception as exc:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE ingestion.source_pages "
                        "SET parse_status='failed', parse_error=%s WHERE url=%s",
                        (str(exc)[:500], url),
                    )
                conn.commit()
                print(f"FAILED {url}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
