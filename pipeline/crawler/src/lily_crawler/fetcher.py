"""Fetch one page (D12). Writes raw HTML to versioned S3 and updates
source_pages; NEVER parses. Content-hash unchanged ⇒ no S3 write, no downstream
parse enqueue (the nightly-incremental skip).

Every collaborator is injected (browser fetch, store, blob, queue, robots,
clock) so the control flow — skip, write, block, fail — is unit-tested without
network, S3, or a browser.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol

from lily_common.s3keys import raw_key
from lily_crawler.sitemap import SeedUrl


class Outcome(Enum):
    FETCHED = "fetched"  # changed/new content written to S3, parse enqueued
    SKIPPED = "skipped"  # content unchanged; only last_fetched_at bumped
    BLOCKED = "blocked"  # robots disallowed at fetch time
    FAILED = "failed"  # non-200; SQS will retry / DLQ


@dataclass(frozen=True)
class FetchResponse:
    status: int
    html: str


BrowserFetch = Callable[[str], FetchResponse]


class SourcePageStore(Protocol):
    def content_hash(self, url: str) -> str | None: ...
    def record_fetch(
        self,
        *,
        url: str,
        page_type: str,
        content_hash: str,
        s3_key: str,
        http_status: int,
        changed: bool,
    ) -> None: ...
    def record_failure(self, url: str, http_status: int) -> None: ...


class BlobStore(Protocol):
    def put(self, key: str, body: str) -> None: ...


class ParseQueue(Protocol):
    def enqueue_parse(self, url: str) -> None: ...


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_page(
    seed: SeedUrl,
    *,
    browser_fetch: BrowserFetch,
    store: SourcePageStore,
    blob: BlobStore,
    queue: ParseQueue,
    robots_allowed: Callable[[str], bool],
    today: date,
) -> Outcome:
    # Re-check robots at fetch time (its TTL may have refreshed since discovery).
    if not robots_allowed(seed.url):
        return Outcome.BLOCKED

    response = browser_fetch(seed.url)
    if response.status != 200:
        store.record_failure(seed.url, response.status)
        return Outcome.FAILED

    new_hash = _sha256(response.html)
    if store.content_hash(seed.url) == new_hash:
        # Unchanged: bump last_fetched_at via record_fetch(changed=False); no S3
        # write, no parse enqueue.
        store.record_fetch(
            url=seed.url,
            page_type=seed.page_type,
            content_hash=new_hash,
            s3_key="",
            http_status=response.status,
            changed=False,
        )
        return Outcome.SKIPPED

    key = raw_key(seed.page_type, seed.url, today)
    blob.put(key, response.html)
    store.record_fetch(
        url=seed.url,
        page_type=seed.page_type,
        content_hash=new_hash,
        s3_key=key,
        http_status=response.status,
        changed=True,
    )
    queue.enqueue_parse(seed.url)
    return Outcome.FETCHED
