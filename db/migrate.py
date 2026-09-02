"""migrate.py — minimal forward-only migration runner for twicetold-npc.

Applies each ``db\\migrations\\NNN_*.sql`` not yet recorded in the
``schema_migrations`` ledger, in filename order. Each migration's DDL and its
ledger row commit inside ONE transaction: a migration and its "applied" record
land together or not at all, so a half-applied migration can never be logged as
complete. Idempotent: a second run with nothing pending is a clean no-op — this
is what the migration-01 "run twice = no-op" criterion rides on.

This runner is the seam later migrations (02+) land on.

Environment: Windows 11, global Python 3.14, psycopg v3 (sync — the async pool is
a write-path concern; this is a one-shot admin script). Reads DATABASE_URI from the
gitignored repo-root .env.

    PowerShell:  python db\\migrate.py [--database-uri <uri>]

--database-uri overrides the .env DATABASE_URI (used for the write-path
verification scratch database; added 2026-07-13, floor re-verified).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


def load_database_uri() -> str:
    """Extract DATABASE_URI from the repo-root .env (no dotenv dependency)."""
    if not ENV_PATH.exists():
        sys.exit(f"ERROR: {ENV_PATH} not found; DATABASE_URI is required.")
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "DATABASE_URI":
            return value.strip().strip('"').strip("'")
    sys.exit("ERROR: DATABASE_URI not set in .env.")


def main() -> None:
    parser = argparse.ArgumentParser(description="twicetold-npc migration runner")
    parser.add_argument(
        "--database-uri",
        default=None,
        help="override the .env DATABASE_URI (e.g. the verification scratch DB)",
    )
    args = parser.parse_args()
    uri = args.database_uri or load_database_uri()
    files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)
    if not files:
        sys.exit(f"ERROR: no migration files found in {MIGRATIONS_DIR}.")

    with psycopg.connect(uri, autocommit=False) as conn:
        # Ledger bootstrap — its own committed transaction.
        with conn.cursor() as cur:
            cur.execute(LEDGER_DDL)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cur.fetchall()}

        pending = [f for f in files if f.name not in applied]
        if not pending:
            print(f"Up to date: {len(applied)} migration(s) applied, 0 pending.")
            return

        for f in pending:
            sql = f.read_text(encoding="utf-8")
            try:
                # DDL + ledger row in one transaction: atomic apply-and-record.
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (f.name,),
                    )
                conn.commit()
            except Exception as exc:  # noqa: BLE001 — report and stop, no half-apply
                conn.rollback()
                sys.exit(
                    f"FAILED on {f.name}: {exc}\nRolled back; no ledger row written."
                )
            print(f"Applied {f.name}")

        print(f"Done: {len(pending)} migration(s) applied.")


if __name__ == "__main__":
    main()
