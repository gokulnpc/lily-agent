"""Aurora connection acquisition with cold-start retry (A11).

The single place production code opens an Aurora connection, so a 0-ACU resume
is absorbed transparently rather than failing the caller. Tools take an injected
connection (testable); only the acquisition is retried here, alongside the
Bedrock call site in the retrieval tools.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg

from lily_common.retry import call_with_retry, is_aurora_transient


def connect_with_retry(
    dsn: str,
    *,
    connect_timeout: int = 10,
    max_attempts: int = 6,
    sleep: Callable[[float], None] | None = None,
    jitter: Callable[[], float] | None = None,
) -> psycopg.Connection:
    """Open a psycopg connection, retrying Aurora cold-start failures."""
    kwargs: dict[str, object] = {}
    if sleep is not None:
        kwargs["sleep"] = sleep
    if jitter is not None:
        kwargs["jitter"] = jitter
    return call_with_retry(
        lambda: psycopg.connect(dsn, connect_timeout=connect_timeout),
        retryable=is_aurora_transient,
        max_attempts=max_attempts,
        **kwargs,  # type: ignore[arg-type]
    )
