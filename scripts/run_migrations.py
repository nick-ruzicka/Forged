"""
Apply SQL migrations from db/migrations/*.sql in lexical order.
Tracks applied migrations in the forge_migrations table so re-runs are
idempotent. Runs each new migration inside a transaction.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List

import psycopg2

log = logging.getLogger("forge.migrations")

_REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = _REPO_ROOT / "db" / "migrations"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://forge:forge@localhost:5432/forge"
)

TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS forge_migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT UNIQUE NOT NULL,
    applied_at  TIMESTAMP DEFAULT NOW()
);
"""


def _list_migrations() -> List[Path]:
    if not MIGRATIONS_DIR.exists():
        return []
    return sorted(p for p in MIGRATIONS_DIR.iterdir()
                  if p.is_file() and p.suffix == ".sql")


def main() -> int:
    migrations = _list_migrations()
    if not migrations:
        print(f"No migrations found in {MIGRATIONS_DIR}")
        return 0

    conn = psycopg2.connect(DATABASE_URL)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(TRACKING_DDL)
            cur.execute("SELECT filename FROM forge_migrations")
            applied = {row[0] for row in cur.fetchall()}

        ran_any = False
        for path in migrations:
            fname = path.name
            if fname in applied:
                print(f"skip  {fname} (already applied)")
                continue

            sql = path.read_text(encoding="utf-8")
            print(f"apply {fname}")
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO forge_migrations (filename) VALUES (%s)",
                        (fname,),
                    )
                conn.commit()
                ran_any = True
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True

        if not ran_any:
            print("All migrations already applied.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
