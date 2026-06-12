"""Schema tests run against the local compose Postgres when reachable, else skip.

DSN resolution: LILY_DATABASE_URL env var, then localhost:5432 and :5433
(this repo's .env may remap the host port when 5432 is taken).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest

from lily_db.migrate import apply_migrations

_CANDIDATE_DSNS = [
    os.environ.get("LILY_DATABASE_URL"),
    "postgresql://lily:lily-local@localhost:5432/lily",
    "postgresql://lily:lily-local@localhost:5433/lily",
]


def _reachable_dsn() -> str | None:
    for dsn in _CANDIDATE_DSNS:
        if not dsn:
            continue
        try:
            with psycopg.connect(dsn, connect_timeout=2):
                return dsn
        except psycopg.OperationalError:
            continue
    return None


@pytest.fixture(scope="session")
def dsn() -> str:
    found = _reachable_dsn()
    if found is None:
        pytest.skip("no local Postgres reachable (run `make up` first)")
    apply_migrations(found)
    return found


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    """Connection whose work is rolled back after each test — DB stays clean."""
    with psycopg.connect(dsn) as connection:
        yield connection
        connection.rollback()
