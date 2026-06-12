"""Token-bucket rate limiter (D12 polite crawl rate).

The clock is injected so the bucket is testable without sleeping. `take()` is
pure arithmetic — it returns how long the caller must wait before the request
may proceed (0.0 if a token is available now) and reserves the token. The caller
sleeps that long; the limiter never sleeps itself.
"""

from __future__ import annotations

from collections.abc import Callable


class TokenBucket:
    def __init__(
        self,
        rate_per_sec: float,
        capacity: float,
        clock: Callable[[], float],
    ) -> None:
        if rate_per_sec <= 0 or capacity <= 0:
            raise ValueError("rate_per_sec and capacity must be positive")
        self._rate = rate_per_sec
        self._capacity = capacity
        self._clock = clock
        self._tokens = capacity
        self._last = clock()

    def _refill(self, now: float) -> None:
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now

    def take(self) -> float:
        """Reserve one token; return seconds the caller must wait first (>= 0)."""
        now = self._clock()
        self._refill(now)
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0
        # Reserve against future refill: wait until one token accrues.
        deficit = 1.0 - self._tokens
        wait = deficit / self._rate
        self._tokens -= 1.0  # goes negative; future takes wait proportionally longer
        return wait
