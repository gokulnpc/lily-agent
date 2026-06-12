"""Catalog tool tests run against the local compose Postgres when reachable,
else skip (same pattern as db/ and pipeline/etl/). Tools are read-only, so each
test's seed + work is rolled back."""

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
    with psycopg.connect(dsn) as connection:
        yield connection
        connection.rollback()
