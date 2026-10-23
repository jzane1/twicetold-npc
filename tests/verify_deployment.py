"""Keyless deployment checks used by scripts/verify-backend.ps1.

Probe failure/recovery through HTTP, or compare a quiesced demo database with
its restored copy. Only the Compose runner creates/restores databases here.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import psycopg
from psycopg import sql

from app.config import load_settings
from app.runtime import open_runtime_pool
from app.scratch_db import scratch_uri


def database_snapshot(uri: str) -> dict:
    """Hash every public table's complete rows; output contains no row content."""
    result = {}
    with psycopg.connect(uri, connect_timeout=5) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        ).fetchall()
        for (table,) in tables:
            rows = conn.execute(
                sql.SQL(
                    "SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text"
                ).format(sql.Identifier("public", table))
            )
            digest = hashlib.sha256()
            count = 0
            for (row,) in rows:
                digest.update(row.encode("utf-8") + b"\n")
                count += 1
            result[table] = {"rows": count, "sha256": digest.hexdigest()}
    return result


def compare_snapshots(source: dict, restored: dict) -> dict:
    required = (
        "memories",
        "memory_details",
        "memory_fact_versions",
        "memory_gist_spans",
        "embedding_space",
        "schema_migrations",
        "observation_receipts",
    )
    nonempty = all(source.get(table, {}).get("rows", 0) > 0 for table in required)
    return {
        "passed": nonempty and source == restored,
        "nonempty_demo": nonempty,
        "all_rows_identical": source == restored,
        "tables": source,
    }


def probe(base_url: str, ready: bool) -> dict:
    with httpx.Client(base_url=base_url, timeout=5, trust_env=False) as client:
        live = client.get("/health/live")
        status = client.get("/health/ready")
    result = {
        "expected_ready": ready,
        "live_status": live.status_code,
        "ready_status": status.status_code,
        "readiness": status.json(),
    }
    result["passed"] = (
        live.status_code == 200
        and status.status_code == (200 if ready else 503)
        and result["readiness"]["checks"]
        == {"database": "pass" if ready else "fail", "workers": "pass"}
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ready", "unavailable", "restore"))
    parser.add_argument("--base-url", default="http://api:8000")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.mode == "restore":
        settings = load_settings()
        if settings.provider_mode != "fake":
            parser.error(
                "restore verification requires the isolated fake Compose project"
            )
        restored = replace(
            settings,
            database_uri=scratch_uri(settings.database_uri, "twicetold_restore"),
        )
        # Check compatibility without modifying the restored embedding binding.
        from app.doctor import check_database

        checks = check_database(restored)
        result = compare_snapshots(
            database_snapshot(settings.database_uri),
            database_snapshot(restored.database_uri),
        )
        result["doctor_passed"] = all(c.status == "pass" for c in checks)

        async def startup():
            pool = await open_runtime_pool(restored)
            await pool.close()

        asyncio.run(startup(), loop_factory=asyncio.SelectorEventLoop)
        result["runtime_startup_passed"] = True
        result["passed"] &= result["doctor_passed"]
    else:
        result = probe(args.base_url, args.mode == "ready")
    output = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
