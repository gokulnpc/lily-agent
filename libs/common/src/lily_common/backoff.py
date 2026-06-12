"""Exponential backoff with full jitter (D12: backoff on 429/403/5xx).

Pure delay computation — the jitter source is injected so tests are
deterministic. Production passes `random.random`.
"""

from __future__ import annotations

from collections.abc import Callable


def backoff_delay(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 60.0,
    jitter: Callable[[], float] = lambda: 1.0,
) -> float:
    """Seconds to wait before retry `attempt` (1-based).

    Full-jitter: delay = jitter() * min(cap, base * 2**(attempt-1)), where
    jitter() returns a value in [0, 1). The default jitter=1.0 yields the
    deterministic exponential ceiling (useful for tests and reasoning).
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    exponential = min(cap, base * (2 ** (attempt - 1)))
    delay: float = jitter() * exponential
    return delay
