"""Retry-with-backoff for transient Aurora / Bedrock failures (A11).

Aurora at 0-ACU resumes from pause on first connect (~15-60s) and drops
in-flight transactions during the window; Bedrock can throttle. Both are
transient, so retry rides them through instead of failing the turn.

Reuses `lily_common.backoff.backoff_delay`; `sleep` and `jitter` are injected so
the logic is unit-tested without real time (same style as backoff/ratelimit).
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from functools import wraps

from lily_common.backoff import backoff_delay

# Returns True if the exception is worth retrying.
Retryable = Callable[[BaseException], bool]


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    retryable: Retryable,
    max_attempts: int = 6,
    base: float = 2.0,
    cap: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> T:
    """Call `fn()`, retrying on exceptions for which `retryable(exc)` is True.

    Non-retryable exceptions propagate immediately. After `max_attempts` the last
    exception is re-raised. Default budget ≈ 2+4+8+16+30 ≈ 60s, covering an
    Aurora cold-start resume.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    last: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:  # re-raised below unless retryable
            if not retryable(exc):
                raise
            last = exc
            if attempt == max_attempts:
                break
            sleep(backoff_delay(attempt, base=base, cap=cap, jitter=jitter))
    assert last is not None
    raise last


def with_retry[T](
    *,
    retryable: Retryable,
    max_attempts: int = 6,
    base: float = 2.0,
    cap: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator form of `call_with_retry`."""

    def decorate(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> T:
            return call_with_retry(
                lambda: fn(*args, **kwargs),
                retryable=retryable,
                max_attempts=max_attempts,
                base=base,
                cap=cap,
                sleep=sleep,
                jitter=jitter,
            )

        return wrapper

    return decorate


# ---- Predicates ------------------------------------------------------------

_BEDROCK_TRANSIENT_CODES = frozenset(
    {
        "ThrottlingException",
        "TooManyRequestsException",
        "ModelTimeoutException",
        "ServiceUnavailableException",
        "ServiceQuotaExceededException",
        "ModelNotReadyException",
        "InternalServerException",
    }
)


def is_aurora_transient(exc: BaseException) -> bool:
    """psycopg OperationalError from an Aurora resume/drop (A11): 'the database
    system is starting up', 'SSL error: unexpected eof', connection refused."""
    return type(exc).__module__.startswith("psycopg") and type(exc).__name__ in (
        "OperationalError",
        "InterfaceError",
    )


def is_bedrock_transient(exc: BaseException) -> bool:
    """botocore ClientError with a throttle/timeout/unavailable code, or any 5xx."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = response.get("Error", {}).get("Code", "")
    if code in _BEDROCK_TRANSIENT_CODES:
        return True
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    return isinstance(status, int) and status >= 500
