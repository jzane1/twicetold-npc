"""scratch_db.py — the one safe way to point anything at a scratch database.

The verified `scratch_uri` rewrite lived in `tests\\scratch_uri.py` from
2026-07-28; eval-harness stage 2 promoted it here (2026-08-05) so the eval
runner can share it. `tests\\scratch_uri.py` is now a re-export shim, so
`conftest.py` and all seven `verify_*.py` walkers import it byte-untouched.
Every caller goes on to run something destructive against whatever URI it is
handed — a forced drop, a truncate, or a migration — so getting this wrong
once is a lost product database.

Why not `urlsplit(uri)._replace(path=f"/{name}")` on its own (the shape every
caller used before 2026-07-28): **libpq honors a `dbname` query parameter over
the URI path.** A `DATABASE_URI` of the form

    postgresql://user:pw@host:5432/postgres?dbname=twicetold

survives a path-only swap with its `dbname` intact, so the "scratch" URI still
resolves to the product database. So: strip every `dbname` key from the query
(keeping the rest — `sslmode` and friends must survive), rewrite the path,
then **prove** the result by parsing it back through
`psycopg.conninfo.conninfo_to_dict` and refusing loudly if the resolved
database is not the one asked for.

`provision_scratch` / `drop_scratch` add the eval runner's disposable-DB loop
(the suite's `tests\\conftest.py` shape): create the scratch database, apply
the full migration ledger via a `db\\migrate.py` subprocess, drop it when the
run ends. Both refuse the product database name outright, on top of
`scratch_uri`'s resolved-name proof.

This module carries database-level DDL only (create/drop database). The
repo-hygiene rule keeping row-level statements in `app\\db.py` is untouched:
its scanned statement tokens are all row-level, and this module contains none
of them.

Never prints or returns any part of the credential.
"""

from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict

from app.config import REPO_ROOT

PRODUCT_DB = "twicetold"


class ScratchUriError(RuntimeError):
    """The rewritten URI does not resolve to the requested scratch database."""


def scratch_uri(base_uri: str, name: str) -> str:
    """Rewrite `base_uri` to point at database `name`, verified.

    Raises ScratchUriError (never returning a usable URI) if the result
    resolves anywhere else. The message names only database names, never the
    URI.
    """
    if not name or not name.replace("_", "").isalnum():
        raise ScratchUriError(f"unsafe scratch database name: {name!r}")

    parts = urlsplit(base_uri)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "dbname"
    ]
    swapped = urlunsplit(parts._replace(path=f"/{name}", query=urlencode(query)))

    resolved = conninfo_to_dict(swapped).get("dbname")
    if resolved != name:
        raise ScratchUriError(
            f"refusing to proceed: rewritten URI resolves to database "
            f"{resolved!r}, not the requested scratch database {name!r}"
        )
    return swapped


def pid_scoped_name(prefix: str) -> str:
    """`<prefix>_<pid>` — the suite's per-process naming shape (`conftest.py`).

    Two overlapping runs never share a scratch database, so one run's forced
    drop can never shut down another run's connections mid-flight.
    """
    return f"{prefix}_{os.getpid()}"


def _refuse_product(name: str) -> None:
    if name == PRODUCT_DB:
        raise ScratchUriError(
            f"refusing to provision or drop the product database {PRODUCT_DB!r}"
        )


def provision_scratch(base_uri: str, name: str, *, connect_timeout: int = 3) -> str:
    """Create scratch database `name`, migrate it, return the verified URI.

    Hard refusal when `name` is the product database — checked by name here
    and re-proven by `scratch_uri`'s conninfo re-parse. Any prior database of
    the same name is dropped first (force), so the result is always freshly
    migrated. Unreachable Postgres or a failed migration raises loudly — the
    eval runner is an invoked command, not a skippable fixture.
    """
    _refuse_product(name)
    uri = scratch_uri(base_uri, name)
    admin_uri = scratch_uri(base_uri, "postgres")
    with psycopg.connect(
        admin_uri, connect_timeout=connect_timeout, autocommit=True
    ) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {name}")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "db" / "migrate.py"), "--database-uri", uri],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        # migrate.py never echoes the URI, so its output is safe to surface.
        raise RuntimeError(
            f"migrating scratch database {name!r} failed "
            f"(exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        )
    return uri


def drop_scratch(base_uri: str, name: str, *, connect_timeout: int = 3) -> None:
    """Drop scratch database `name` (force — lingering connections die).

    Same refusal pair as `provision_scratch`: the product name is refused
    outright, and the name is validated through `scratch_uri` before it is
    interpolated into DDL.
    """
    _refuse_product(name)
    scratch_uri(base_uri, name)
    admin_uri = scratch_uri(base_uri, "postgres")
    with psycopg.connect(
        admin_uri, connect_timeout=connect_timeout, autocommit=True
    ) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
