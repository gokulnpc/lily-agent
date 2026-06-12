"""Fetcher control flow — fully offline with in-memory fakes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from lily_crawler.fetcher import (
    FetchResponse,
    Outcome,
    fetch_page,
)
from lily_crawler.sitemap import SeedUrl

TODAY = date(2026, 6, 12)
SEED = SeedUrl(url="https://www.partselect.com/Models/WDT780SAEM1/", page_type="model")


class FakeStore:
    def __init__(self, existing: dict[str, str] | None = None) -> None:
        self.hashes = existing or {}
        self.fetches: list[dict[str, object]] = []
        self.failures: list[tuple[str, int]] = []

    def content_hash(self, url: str) -> str | None:
        return self.hashes.get(url)

    def record_fetch(self, **kw: object) -> None:
        self.fetches.append(kw)

    def record_failure(self, url: str, http_status: int) -> None:
        self.failures.append((url, http_status))


class FakeBlob:
    def __init__(self) -> None:
        self.puts: dict[str, str] = {}

    def put(self, key: str, body: str) -> None:
        self.puts[key] = body


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[str] = []

    def enqueue_parse(self, url: str) -> None:
        self.enqueued.append(url)


def run(
    seed: SeedUrl,
    *,
    store: FakeStore,
    browser: Callable[[str], FetchResponse],
    robots: Callable[[str], bool] = lambda _u: True,
) -> tuple[Outcome, FakeBlob, FakeQueue]:
    blob, queue = FakeBlob(), FakeQueue()
    outcome = fetch_page(
        seed,
        browser_fetch=browser,
        store=store,
        blob=blob,
        queue=queue,
        robots_allowed=robots,
        today=TODAY,
    )
    return outcome, blob, queue


def test_new_page_writes_s3_and_enqueues() -> None:
    store = FakeStore()
    outcome, blob, queue = run(
        SEED, store=store, browser=lambda _u: FetchResponse(200, "<html>v1</html>")
    )
    assert outcome is Outcome.FETCHED
    assert len(blob.puts) == 1
    assert next(iter(blob.puts)).startswith("raw/model/dt=2026-06-12/")
    assert queue.enqueued == [SEED.url]
    assert store.fetches[-1]["changed"] is True


def test_unchanged_content_skips_s3_and_enqueue() -> None:
    import hashlib

    body = "<html>same</html>"
    digest = hashlib.sha256(body.encode()).hexdigest()
    store = FakeStore(existing={SEED.url: digest})
    outcome, blob, queue = run(SEED, store=store, browser=lambda _u: FetchResponse(200, body))
    assert outcome is Outcome.SKIPPED
    assert blob.puts == {}  # no S3 write
    assert queue.enqueued == []  # no parse enqueue
    assert store.fetches[-1]["changed"] is False


def test_changed_content_rewrites_and_reenqueues() -> None:
    import hashlib

    old = hashlib.sha256(b"<html>old</html>").hexdigest()
    store = FakeStore(existing={SEED.url: old})
    outcome, blob, queue = run(
        SEED, store=store, browser=lambda _u: FetchResponse(200, "<html>new</html>")
    )
    assert outcome is Outcome.FETCHED
    assert len(blob.puts) == 1
    assert queue.enqueued == [SEED.url]


def test_non_200_records_failure_no_write() -> None:
    store = FakeStore()
    outcome, blob, queue = run(SEED, store=store, browser=lambda _u: FetchResponse(503, ""))
    assert outcome is Outcome.FAILED
    assert store.failures == [(SEED.url, 503)]
    assert blob.puts == {}
    assert queue.enqueued == []


def test_robots_block_short_circuits() -> None:
    store = FakeStore()
    called = False

    def browser(_u: str) -> FetchResponse:
        nonlocal called
        called = True
        return FetchResponse(200, "x")

    outcome, blob, _ = run(SEED, store=store, browser=browser, robots=lambda _u: False)
    assert outcome is Outcome.BLOCKED
    assert not called  # never fetched
    assert blob.puts == {}
