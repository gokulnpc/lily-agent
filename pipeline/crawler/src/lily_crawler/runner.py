"""Pod entrypoints: discovery and the fetch worker. These assemble the
production adapters (Playwright Chrome, boto3 S3/SQS, psycopg) around the
injected-dependency core. The core logic is unit-tested in isolation; this file
is the thin wiring exercised end-to-end against real AWS.

    python -m lily_crawler.runner discover       # sitemap -> source_pages + crawl-jobs
    python -m lily_crawler.runner fetch-worker    # drain crawl-jobs -> S3 + parse enqueue
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import boto3
import psycopg

from lily_common.robots import RobotsCache
from lily_crawler.aws import PgSourcePageStore, S3BlobStore, SqsParseQueue
from lily_crawler.browser import USER_AGENT, PoliteBrowser
from lily_crawler.fetcher import fetch_page
from lily_crawler.sitemap import SeedUrl, child_sitemaps_for, select_seed_urls

MASTER_SITEMAP = "https://www.partselect.com/sitemaps/PartSelect.com_Sitemap_Master.xml"
SEED_CAP = int(os.environ.get("LILY_SEED_CAP", "500"))


def _robots_cache(fetch_text) -> RobotsCache:  # type: ignore[no-untyped-def]
    return RobotsCache(fetcher=fetch_text, user_agent=USER_AGENT)


def discover() -> int:
    """Seed source_pages + crawl-jobs from the sitemap (bounded by SEED_CAP)."""
    sqs = boto3.client("sqs")
    queue_url = os.environ["LILY_CRAWL_QUEUE_URL"]

    with PoliteBrowser().session() as session:

        def fetch_text(url: str) -> str:
            return session.fetch(url).html

        robots = _robots_cache(fetch_text)
        seeds, dropped = select_seed_urls(
            master_url=MASTER_SITEMAP,
            fetch=fetch_text,
            robots_allowed=robots.allowed,
            cap=SEED_CAP,
            child_filter=child_sitemaps_for(("PartDetail", "Repairs")),
        )

    for seed in seeds:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"url": seed.url, "page_type": seed.page_type}),
        )
    print(f"seeded {len(seeds)} urls; dropped {dropped} for cap {SEED_CAP}")
    return 0


def fetch_worker() -> int:
    """Drain crawl-jobs: fetch, hash-skip or write to S3, enqueue parse jobs."""
    sqs = boto3.client("sqs")
    s3 = boto3.client("s3")
    crawl_queue = os.environ["LILY_CRAWL_QUEUE_URL"]
    parse_queue = os.environ["LILY_PARSE_QUEUE_URL"]
    bucket = os.environ["LILY_RAW_BUCKET"]

    conn = psycopg.connect(os.environ["LILY_DATABASE_URL"])
    store = PgSourcePageStore(conn)
    blob = S3BlobStore(s3, bucket)
    queue = SqsParseQueue(sqs, parse_queue)

    with PoliteBrowser().session() as session:
        robots = _robots_cache(lambda u: session.fetch(u).html)
        while True:
            msgs = sqs.receive_message(
                QueueUrl=crawl_queue, MaxNumberOfMessages=1, WaitTimeSeconds=20
            ).get("Messages", [])
            if not msgs:
                break
            for msg in msgs:
                body = json.loads(msg["Body"])
                seed = SeedUrl(url=body["url"], page_type=body["page_type"])
                outcome = fetch_page(
                    seed,
                    browser_fetch=session.fetch,
                    store=store,
                    blob=blob,
                    queue=queue,
                    robots_allowed=robots.allowed,
                    today=datetime.date.today(),
                )
                # Delete only on a terminal outcome; FAILED returns to the queue
                # (SQS retry -> DLQ after maxReceiveCount).
                if outcome.value != "failed":
                    sqs.delete_message(QueueUrl=crawl_queue, ReceiptHandle=msg["ReceiptHandle"])
                print(f"{outcome.value}: {seed.url}")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "discover":
        return discover()
    if cmd == "fetch-worker":
        return fetch_worker()
    print("usage: python -m lily_crawler.runner {discover|fetch-worker}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
