"""Plain-SQL migration runner.

Migrations are numbered .sql files in db/migrations/, applied in filename order,
each inside its own transaction, tracked in public.schema_migrations. Forward-only
by design — rollback is a new forward migration (matches how Aurora is operated).

Usage:
    LILY_DATABASE_URL=postgresql://... uv run python -m lily_db.migrate
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

def _migrations_dir() -> Path:
    # Installed wheel ships migrations alongside the package (force-include);
    # local dev/editable runs from the repo's db/migrations.
    packaged = Path(__file__).resolve().parent / "migrations"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "migrations"


MIGRATIONS_DIR = _migrations_dir()


def default_dsn() -> str:
    # LILY_POSTGRES_PORT mirrors the compose host-port override in .env.
    port = os.environ.get("LILY_POSTGRES_PORT", "5432")
    return f"postgresql://lily:lily-local@localhost:{port}/lily"


_TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def pending_migrations(conn: psycopg.Connection) -> list[Path]:
    with conn.cursor() as cur:
        cur.execute(_TRACKING_DDL)
        cur.execute("SELECT filename FROM public.schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
    conn.commit()
    return [path for path in sorted(MIGRATIONS_DIR.glob("*.sql")) if path.name not in applied]


def apply_migrations(dsn: str) -> list[str]:
    """Apply all pending migrations; returns the filenames applied."""
    applied: list[str] = []
    with psycopg.connect(dsn) as conn:
        for path in pending_migrations(conn):
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO public.schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
            conn.commit()
            applied.append(path.name)
    return applied


def main() -> int:
    dsn = os.environ.get("LILY_DATABASE_URL") or default_dsn()
    applied = apply_migrations(dsn)
    if applied:
        for name in applied:
            print(f"applied {name}")
    else:
        print("up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
