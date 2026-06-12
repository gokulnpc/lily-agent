"""Chrome-channel fetch + politeness, wired together for production.

Headless Chromium and plain HTTP are Akamai-403'd, so the fetcher drives the
real Chrome channel (the image ships it via `playwright install chrome`). This
module is the only place Playwright is touched; everything else takes the
injected `BrowserFetch` callable, so the control flow stays testable without a
browser.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from lily_common.backoff import backoff_delay
from lily_common.ratelimit import TokenBucket
from lily_crawler.fetcher import FetchResponse

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RENDER_WAIT_MS = 4000  # let lazy cross-reference / section renderers fire


class PoliteBrowser:
    """A single Chrome context with token-bucket pacing and 403/5xx backoff."""

    def __init__(
        self,
        rate_per_sec: float = 0.15,  # ~1 request / 6.7s
        burst: float = 1,
        max_attempts: int = 4,
    ) -> None:
        self._bucket = TokenBucket(rate_per_sec, burst, clock=time.monotonic)
        self._max_attempts = max_attempts

    @contextmanager
    def session(self) -> Iterator[_Session]:
        # Headed Chrome passes Akamai locally; in a pod there's no display, so
        # either run new-headless real Chrome (LILY_HEADLESS=true) or wrap the
        # process in xvfb-run for headed. Default headed for local dev.
        headless = os.environ.get("LILY_HEADLESS", "").lower() in ("1", "true", "yes")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                channel="chrome",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(user_agent=USER_AGENT, locale="en-US")
            try:
                yield _Session(context.new_page(), self._bucket, self._max_attempts)
            finally:
                browser.close()


class _Session:
    def __init__(self, page: object, bucket: TokenBucket, max_attempts: int) -> None:
        self._page = page
        self._bucket = bucket
        self._max_attempts = max_attempts

    def fetch(self, url: str) -> FetchResponse:
        result = FetchResponse(status=0, html="")
        for attempt in range(1, self._max_attempts + 1):
            wait = self._bucket.take()
            if wait > 0:
                time.sleep(wait)
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=45000)  # type: ignore[attr-defined]
            status = response.status if response else 0
            self._page.wait_for_timeout(RENDER_WAIT_MS)  # type: ignore[attr-defined]
            result = FetchResponse(status=status, html=self._page.content())  # type: ignore[attr-defined]
            # Treat denial as "slow down": back off and retry within budget.
            retriable = status in (403, 429) or status >= 500
            if retriable and attempt < self._max_attempts:
                time.sleep(backoff_delay(attempt, base=5.0, cap=120.0))
                continue
            return result
        return result
