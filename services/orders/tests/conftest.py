"""Order tool tests against compose Postgres, else skip. initiate_return commits,
so commerce tables are truncated around each test (like pipeline/etl/tests)."""

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
_TABLES = (
    "commerce.returns",
    "commerce.order_events",
    "commerce.order_items",
    "commerce.orders",
)


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


def _truncate(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
    conn.commit()


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn) as connection:
        _truncate(connection)
        yield connection
        _truncate(connection)
