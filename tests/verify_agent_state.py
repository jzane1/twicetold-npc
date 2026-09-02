"""verify_agent_state.py — structural done-when walker for the agent-state
read (Phase C5; the seven rulings dated 2026-08-17; NO migration — the ruled
per-target scope fact: the pressure gauge is computed-never-stored and every
table and index the read touches was pre-laid in 001/007/008, the two newest
index comments naming this read as their consumer).

Runs the C5 backend done-when criteria against the SCRATCH database
(default: the .env DATABASE_URI with its database name swapped to
`twicetold_test`), with deterministic fake providers — offline, keyless, and
structural-only per tests\\CLAUDE.md. The seam is
`RetrievalService.agent_state` (behind GET /v1/agents/{agent_id}/state, the
FOURTH unscored-by-contract member), exercised service-side for the composed
values and route-side over httpx.ASGITransport for the wire contract. The
elder read-path walker staying byte-identical at its pre-C5 criteria is the
zero-scoring-change evidence; THIS walker owns the mechanism: the
no-migration shape, the pressure gauge's hand math + the loud norm guard,
belief/bundle liveness + the ruled orders + verbatim passthrough, the two
run-log mirrors, the 404/422 ladder + pass-through-by-ruling JSON identity +
the present-null tri-state, and the zero-writes proof. Async observes (C5's
other half) is client-side C# — the console harness's interop beats own it;
nothing here.

Persistent-scratch rule (the verify_dissonance precedent): every agent name
carries a per-run suffix and every assertion is scoped to this run's ids
(never a DB-global count), so prior green runs on the persistent scratch
cannot perturb this one. In full sweeps this walker runs LAST (the newest —
elder walkers first, fresh + serial).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_agent_state.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.config import Settings
from app.db import build_pool
from app.ingest import UnknownAgentError
from app.providers import (
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.retrieval import RetrievalService

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
WALL_FUTURE = datetime.now(timezone.utc) + timedelta(hours=6)
SEED = "A verification NPC, keeper of the crossing ledger."
RUN = uuid4().hex[:8]  # per-run fixture scoping (persistent-scratch rule)

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "reconstruction_theta": 0.0,
    "gate_enabled": 0.0,
}

PASSED: list[str] = []


def ok(criterion: str, detail: str = "") -> None:
    PASSED.append(criterion)
    print(f"  PASS  {criterion}" + (f"  ({detail})" if detail else ""))


def fail(criterion: str, detail: str) -> None:
    print(f"  FAIL  {criterion}: {detail}")
    sys.exit(1)


def check(condition: bool, criterion: str, detail: str = "") -> None:
    if not condition:
        fail(criterion, detail or "condition false")
    ok(criterion, detail)


def scratch_uri_from_env() -> str:
    from app.config import load_env

    return scratch_uri(load_env()["DATABASE_URI"], "twicetold_test")


def fake_providers() -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=FakeEmbeddingProvider(),
        dialogue=FakeProseProvider(),
        reconstruction=FakeReconstructionProvider(),
    )


async def make_agent(pool, tag: str, config: dict):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (
                f"agent-state-walker-{RUN}-{tag}",
                SEED,
                "what threatens the crossing",
                Jsonb(config),
            ),
        )
        return (await cur.fetchone())[0]


async def bare_agent(pool, tag: str):
    """Name only — every nullable column NULL, config NULL (the
    normalization + tri-state fixture)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name) VALUES (%s) RETURNING agent_id",
            (f"agent-state-walker-{RUN}-{tag}",),
        )
        return (await cur.fetchone())[0]


async def seed_memory(pool, agent_id, text: str, valid_at, *, importance=0.5):
    """A completed memory at the db layer — the verify_dissonance seed
    shape: explicit fixture facts, the pure fake embedding, no NLP pass."""
    vec = FakeEmbeddingProvider().embed([text]).vectors[0]
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=f"[walker seed] {text}",
        valid_at=valid_at,
        importance_raw=importance,
        scoring_failed=False,
        typology="observed",
        typology_confidence=0.9,
        typology_source="declared",
        provenance="lived",
        pinned=False,
        decay_class="episodic",
        decay_class_unknown=False,
        embedding=vec,
        entities=None,
        spans=[],
        event_time=None,
        location_name=None,
    )
    outcome = await db.insert_observation(pool, plan)
    return outcome.memory_id


async def seed_reflection(
    pool,
    agent_id,
    content: str,
    valid_at,
    *,
    identity_relevant=True,
    source_memory_ids=(),
    created_at=None,
    invalid_at=None,
):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO reflections (agent_id, content, identity_relevant, "
            "source_memory_ids, valid_at, created_at, invalid_at) "
            "VALUES (%s, %s, %s, %s, %s, COALESCE(%s, now()), %s) "
            "RETURNING reflection_id",
            (
                agent_id,
                content,
                identity_relevant,
                list(source_memory_ids),
                valid_at,
                created_at,
                invalid_at,
            ),
        )
        return (await cur.fetchone())[0]


async def seed_bundle(
    pool,
    agent_id,
    reflection_id,
    *,
    scene_type="default",
    w_relevance=1.0,
    passthrough=None,
    created_at=None,
):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO compiled_bundles (agent_id, reflection_id, "
            "scene_type, w_relevance, w_recency, w_importance, passthrough, "
            "created_at) VALUES (%s, %s, %s, %s, 1.0, 1.0, %s, "
            "COALESCE(%s, now())) RETURNING bundle_id",
            (
                agent_id,
                reflection_id,
                scene_type,
                w_relevance,
                Jsonb(passthrough or {}),
                created_at,
            ),
        )
        return (await cur.fetchone())[0]


def reflection_run(agent_id, *, outcome="completed", error=None, **overrides):
    fields = {
        "agent_id": agent_id,
        "outcome": outcome,
        "error": error,
        "reflections_written": 2,
        "dropped_ungrounded": 1,
        "consolidation_ran": True,
        "consolidation_failed": False,
        "rrr": 0.25,
        "rrr_blocked": False,
        "pruned_components": 0,
        "evicted_cache_rows": 3,
        "pressure_before": 1.2,
        "pressure_after": 0.0,
        "reflect_ms": 10.0,
        "consolidation_ms": 5.0,
        "insert_ms": 1.0,
        "total_ms": 16.0,
        "reflect_input_tokens": 100,
        "reflect_output_tokens": 40,
        "consolidation_input_tokens": 20,
        "consolidation_output_tokens": 10,
    }
    fields.update(overrides)
    return db.ReflectionRunRecord(**fields)


def compiler_run(agent_id, *, outcome="completed", error=None, **overrides):
    fields = {
        "agent_id": agent_id,
        "outcome": outcome,
        "error": error,
        "pairs_compiled": 2,
        "pairs_failed": 0,
        "passthrough_keys_dropped": 1,
        "input_tokens": 50,
        "output_tokens": 20,
        "total_ms": 8.0,
    }
    fields.update(overrides)
    return db.CompilerRunRecord(**fields)


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def run(uri: str) -> None:
    from urllib.parse import urlsplit

    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    print(f"walker: scratch DB = {urlsplit(uri).path.lstrip('/')}")
    try:
        svc = RetrievalService(pool, fake_providers(), settings)

        # ------------------------------------------------------------------ #
        print("\n-- A. the no-migration shape (the ruled per-target scope fact)")
        top = await fetchrow(
            pool,
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1",
        )
        check(
            top is not None and top[0].startswith("008_"),
            "A1 the migration ledger still ends at 008 (C5 adds none)",
            detail=top[0] if top else "empty ledger",
        )
        agent_cols = await fetchall(
            pool,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'agents'",
        )
        check(
            {c[0] for c in agent_cols}
            == {
                "agent_id",
                "name",
                "seed_identity",
                "reputation",
                "rigidity",
                "reputation_sensitivity",
                "diagnosticity_goal",
                "config",
            },
            "A2 agents carries exactly the 001 columns (nothing added)",
        )
        idx = await fetchall(
            pool,
            "SELECT indexname FROM pg_indexes WHERE indexname IN "
            "('reflection_runs_agent_id_idx', 'compiled_bundles_agent_id_idx')",
        )
        check(
            {i[0] for i in idx}
            == {"reflection_runs_agent_id_idx", "compiled_bundles_agent_id_idx"},
            "A3 the pre-laid 007/008 agent-id indexes this read rides exist",
        )

        # ------------------------------------------------------------------ #
        print("\n-- B. the pressure gauge (hand math; the loud norm guard)")
        gauge = await make_agent(pool, "gauge", AGENT_CONFIG)
        await seed_memory(pool, gauge, "toll dispute", NOW, importance=0.6)
        await seed_memory(pool, gauge, "wheel lost", NOW, importance=0.4)
        await seed_memory(pool, gauge, "unscored row", NOW, importance=None)
        state = await svc.agent_state(gauge, 100)
        expect = (0.6 + 0.4 + 0.5) / 10.0
        # importance_raw is float4 (real) — compare at float32 honesty, the
        # pytest.approx rel-tolerance the suite uses.
        check(
            abs(state.reflection_pressure - expect) < 1e-6,
            "B1 pressure = sum(COALESCE(importance, neutral)) / default norm",
            detail=f"{state.reflection_pressure} ~= {expect}",
        )
        norm5 = await make_agent(
            pool, "norm5", {**AGENT_CONFIG, "reflection_pressure_norm": 5.0}
        )
        await seed_memory(pool, norm5, "same mass", NOW, importance=0.6)
        state = await svc.agent_state(norm5, 100)
        check(
            abs(state.reflection_pressure - 0.12) < 1e-6,
            "B2 per-agent reflection_pressure_norm override rescales",
        )
        await seed_reflection(
            pool,
            gauge,
            "epoch marker",
            NOW,
            created_at=WALL_FUTURE,
            invalid_at=WALL_FUTURE,
        )
        state = await svc.agent_state(gauge, 100)
        check(
            state.reflection_pressure == 0.0,
            "B3 a reflection EVENT after the rows zeroes the gauge "
            "(even an invalidated one — the epoch is created_at)",
        )
        bad = await make_agent(
            pool, "norm0", {**AGENT_CONFIG, "reflection_pressure_norm": 0.0}
        )
        try:
            await svc.agent_state(bad, 100)
            fail("B4 norm <= 0 raises", "no exception")
        except ValueError:
            ok("B4 norm <= 0 raises the reflect verb's ValueError (never clamps)")

        # ------------------------------------------------------------------ #
        print("\n-- C. beliefs + bundles (liveness, ruled orders, passthrough)")
        believer = await make_agent(pool, "beliefs", AGENT_CONFIG)
        m1 = await seed_memory(pool, believer, "a lantern shattered", NOW)
        older = await seed_reflection(
            pool,
            believer,
            "strangers test the keeper",
            NOW - timedelta(days=2),
            identity_relevant=True,
            source_memory_ids=(m1,),
            created_at=NOW - timedelta(days=2),
        )
        newer = await seed_reflection(
            pool,
            believer,
            "carts break at the ford",
            NOW - timedelta(days=1),
            identity_relevant=False,
            created_at=NOW - timedelta(days=1),
        )
        dead = await seed_reflection(
            pool,
            believer,
            "an absorbed belief",
            NOW,
            created_at=NOW,
            invalid_at=NOW + timedelta(hours=1),
        )
        state = await svc.agent_state(believer, 100)
        check(
            [r.reflection_id for r in state.reflections] == [newer, older],
            "C1 live beliefs only, in the ruled compiler-window order",
        )
        by_id = {r.reflection_id: r for r in state.reflections}
        check(
            by_id[older].identity_relevant is True
            and by_id[newer].identity_relevant is False,
            "C2 both identity_relevant values carried",
        )
        check(
            by_id[older].source_memory_ids == [m1],
            "C3 source_memory_ids provenance round-trips",
        )
        stale = await seed_bundle(
            pool,
            believer,
            newer,
            scene_type="tavern",
            w_relevance=2.0,
            created_at=NOW - timedelta(hours=2),
        )
        fresh = await seed_bundle(
            pool,
            believer,
            newer,
            scene_type="tavern",
            w_relevance=3.0,
            passthrough={"studio": {"tone": "wary", "depth": 2}},
            created_at=NOW - timedelta(hours=1),
        )
        market = await seed_bundle(
            pool, believer, newer, scene_type="market", created_at=NOW
        )
        old_pair = await seed_bundle(
            pool, believer, older, scene_type="tavern", created_at=NOW
        )
        await seed_bundle(pool, believer, dead, scene_type="tavern", created_at=NOW)
        state = await svc.agent_state(believer, 100)
        got = [b.bundle_id for b in state.compiled_bundles]
        check(
            got == [market, fresh, old_pair],
            "C4 newest bundle per live pair, belief-window order then scene_type",
        )
        check(
            stale not in set(got),
            "C5 a superseded bundle and a dead belief's bundle are absent "
            "(liveness DERIVED, the §10 contract)",
        )
        winner = next(b for b in state.compiled_bundles if b.bundle_id == fresh)
        check(
            winner.passthrough == {"studio": {"tone": "wary", "depth": 2}}
            and winner.w_relevance == 3.0,
            "C6 passthrough verbatim + the winning pair's multipliers",
        )

        # ------------------------------------------------------------------ #
        print("\n-- D. the two run logs (full mirrors, newest first, limit)")
        logs = await make_agent(pool, "runs", AGENT_CONFIG)
        await db.insert_reflection_run(pool, reflection_run(logs))
        await db.insert_reflection_run(
            pool,
            reflection_run(
                logs,
                outcome="failed",
                error="provider unreachable",
                rrr=None,
                reflect_ms=None,
                consolidation_ms=None,
                insert_ms=None,
                total_ms=None,
                pressure_after=None,
            ),
        )
        await db.insert_compiler_run(pool, compiler_run(logs))
        await db.insert_compiler_run(
            pool, compiler_run(logs, outcome="failed", error="role missing")
        )
        state = await svc.agent_state(logs, 100)
        check(
            len(state.reflection_runs) == 2
            and state.reflection_runs[0].outcome == "failed"
            and state.reflection_runs[1].outcome == "completed",
            "D1 reflection runs newest first",
        )
        head, done = state.reflection_runs
        check(
            head.error == "provider unreachable"
            and head.rrr is None
            and head.reflect_ms is None
            and head.total_ms is None,
            "D2 a failed run's nullable columns come through as None",
        )
        check(
            done.reflections_written == 2
            and abs((done.rrr or 0.0) - 0.25) < 1e-6
            and done.evicted_cache_rows == 3
            and done.reflect_input_tokens == 100
            and done.consolidation_output_tokens == 10,
            "D3 the completed run's full 007 instrumentation mirrors",
        )
        check(
            len(state.compiler_runs) == 2
            and state.compiler_runs[0].outcome == "failed"
            and state.compiler_runs[1].pairs_compiled == 2
            and state.compiler_runs[1].passthrough_keys_dropped == 1,
            "D4 compiler runs newest first with the full 008 mirror",
        )
        capped = await svc.agent_state(logs, 1)
        check(
            len(capped.reflection_runs) == 1
            and len(capped.compiler_runs) == 1
            and capped.runs_limit == 1,
            "D5 runs_limit caps each list independently and echoes",
        )

        # ------------------------------------------------------------------ #
        print("\n-- E. the wire contract (ladder, tri-state, pass-through)")
        import httpx

        import app.api as api_module

        class CapturingRetrieval:
            def __init__(self, inner):
                self._inner = inner
                self.last = None

            async def agent_state(self, agent_id, runs_limit):
                self.last = await self._inner.agent_state(agent_id, runs_limit)
                return self.last

        capture = CapturingRetrieval(svc)
        api_module.app.state.retrieval = capture
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://walker"
        ) as client:
            r404 = await client.get(f"/v1/agents/{uuid4()}/state")
            check(r404.status_code == 404, "E1 unknown agent -> 404")
            low = await client.get(f"/v1/agents/{logs}/state?runs_limit=0")
            high = await client.get(f"/v1/agents/{logs}/state?runs_limit=1001")
            check(
                low.status_code == 422 and high.status_code == 422,
                "E2 runs_limit outside [1, 1000] -> 422 both ends",
            )
            bare = await bare_agent(pool, "bare")
            resp = await client.get(f"/v1/agents/{bare}/state")
            body = resp.json()
            check(
                resp.status_code == 200
                and all(
                    key in body and body[key] is None
                    for key in (
                        "seed_identity",
                        "rigidity",
                        "diagnosticity_goal",
                        "identity_version",
                        "identity_compiled_at",
                    )
                )
                and body["config"] == {}
                and body["reflection_pressure"] == 0.0,
                "E3 bare agent: present-null tri-state + {} config over the wire",
            )
            resp = await client.get(f"/v1/agents/{believer}/state?runs_limit=7")
            check(
                resp.status_code == 200
                and capture.last is not None
                and resp.json() == json.loads(capture.last.model_dump_json()),
                "E4 route JSON == service JSON (pass-through by ruling)",
            )
            check(
                resp.json()["runs_limit"] == 7,
                "E5 the runs_limit query param reaches the service and echoes",
            )
        try:
            await svc.agent_state(uuid4(), 100)
            fail("E6 service raises UnknownAgentError", "no exception")
        except UnknownAgentError:
            ok("E6 service raises UnknownAgentError (the route's 404 source)")

        # ------------------------------------------------------------------ #
        print("\n-- F. zero writes (the composed read is a pure SELECT stack)")
        tables = (
            "agents",
            "memories",
            "memory_details",
            "identity_documents",
            "reconstruction_cache",
            "reflections",
            "compiled_bundles",
            "reflection_runs",
            "compiler_runs",
        )

        async def counts():
            return [
                (await fetchrow(pool, f"SELECT count(*) FROM {t}"))[0] for t in tables
            ]

        before = await counts()
        state = await svc.agent_state(believer, 100)
        after = await counts()
        check(before == after, "F1 row counts byte-identical across the read")
        check(
            state.identity_version is None,
            "F2 a never-compiled agent STAYS never-compiled "
            "(pure SELECT — the ensure_ upsert is never called)",
        )

        print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-uri",
        default=None,
        help="scratch Postgres URI (default: .env DATABASE_URI with the "
        "database swapped to twicetold_test)",
    )
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
