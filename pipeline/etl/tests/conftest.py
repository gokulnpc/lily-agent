"""ETL tests run against the local compose Postgres when reachable, else skip
(same pattern as db/). Each test gets a clean transaction, rolled back after."""

from __future__ import annotations

import os
import pathlib
from collections.abc import Callable, Iterator

import psycopg
import pytest

from lily_db.migrate import apply_migrations

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "parsers" / "tests" / "fixtures"

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


# ETL tests must COMMIT (the staleness janitor relies on now() differing across
# transactions), so rollback can't isolate them. Truncate the tables they touch
# before and after each test instead — keeps them isolated from each other and
# from the db/ schema tests that share this database.
_TABLES = (
    "catalog.part_model_compatibility",
    "catalog.symptom_parts",
    "catalog.qna",
    "catalog.reviews",
    "catalog.symptoms",
    "catalog.parts",
    "catalog.models",
    "ingestion.search_sync",
    "ingestion.source_pages",
)


def _truncate(connection: psycopg.Connection) -> None:
    with connection.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
    connection.commit()


@pytest.fixture
def conn(dsn: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn) as connection:
        _truncate(connection)
        yield connection
        _truncate(connection)


@pytest.fixture
def fixture() -> Callable[[str], str]:
    return lambda name: (FIXTURES / f"{name}.html").read_text()
