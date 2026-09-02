"""verify_compiler.py — structural done-when walker for the parameter
compiler (Phase C3; parameter-compiler.md, the rulings dated 2026-08-17;
migration 008).

Runs the compiler done-when criteria against the SCRATCH database
(default: the .env DATABASE_URI with its database name swapped to
`twicetold_test`), with deterministic fake providers — offline, keyless, and
structural-only per tests\\CLAUDE.md. The service is exercised through the
worker's `sweep()` (the deterministic no-timer entry — C3 has no endpoint
verb by ruling) and the consume side through the dialogue seam; turns pin
`as_of` to the frozen NOW so recency math is reproducible. The write-path
and read-path walkers staying byte-identical at their pre-C3 criteria are
the zero-retrieval-change evidence; THIS walker owns the new mechanism: the
migration 008 shape, the compile ladder (clamp-at-write, namespace filter,
malformed/failing continue-and-retry, kill-switch, batch budget), the
all-mechanical staleness guard (the K-window at both ends, liveness by
join, the consolidation collapse), consume parity + the per-scene-type
re-rank, the worker lifecycle at both construction sites, and the
judge-shaped role/config surface.

Sections that leave an enabled agent holding UNCOMPILED pairs flip its
kill-switch off before moving on: the scratch database persists across
walker runs, and a stale enabled agent with missing pairs would perturb the
next run's deterministic sweep counts (fully-compiled agents are harmless —
they contribute zero attempts).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_compiler.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

import psycopg.errors
from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.compiler import (
    DEFAULT_SCENE_TYPE,
    CompilerWorker,
    compose_bundle_weights,
    resolve_scene_type,
)
from app.config import (
    MULTIPLIER_MAX,
    MULTIPLIER_MIN,
    SERVICE_DEFAULTS,
    ConfigError,
    Settings,
    load_settings,
    scene_types,
)
from app.db import build_pool
from app.dialogue import DialogueService, weighted_score
from app.providers import (
    CompilerCallResult,
    FailingCompilerProvider,
    FakeCompilerProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    MalformedCompilerProvider,
    Providers,
    build_compiler_provider,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueTurnRequest, DialogueTurnResult, WeightOverrides
from app.session import SessionRunner

NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
SEED = "A verification NPC, keeper of the crossing ledger."

M_OLD = "Bram shattered the lantern at the ford gate."
M_NEW = "A grey cat took up residence in the mill loft."
B1 = "Merchants have cheated the keeper twice at the ford."
B2 = "The keeper trusts the miller's word over paper."
B3 = "Storms upriver mean the toll bridge floods by dusk."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "reconstruction_theta": 0.0,
    "gate_enabled": 0.0,
}
ENABLED = {**AGENT_CONFIG, "compiler_worker_enabled": 1.0}

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


def fake_providers(**overrides) -> Providers:
    return Providers(
        write=overrides.get("write", FakeWriteProvider()),
        escalation=overrides.get("escalation", FakeEscalationProvider()),
        embedding=overrides.get("embedding", FakeEmbeddingProvider()),
        dialogue=overrides.get("dialogue", FakeProseProvider()),
        reconstruction=overrides.get("reconstruction", FakeReconstructionProvider()),
    )


def worker_for(pool, settings, *, defaults: dict | None = None, provider=None):
    if defaults:
        settings = replace(settings, defaults={**settings.defaults, **defaults})
    return CompilerWorker(pool, fake_providers(), settings, compiler_provider=provider)


class PinnedCompilerProvider:
    """Exact multipliers + junk passthrough keys — the clamp and
    namespace-filter fixture (hash-derived fakes cannot pin values)."""

    def __init__(self, w_relevance=1.0, w_recency=1.0, w_importance=1.0, keys=None):
        self._result = CompilerCallResult(
            w_relevance=w_relevance,
            w_recency=w_recency,
            w_importance=w_importance,
            passthrough=keys or {},
            input_tokens=5,
            output_tokens=5,
        )

    def compile(self, **_kwargs) -> CompilerCallResult:
        return self._result


async def make_agent(pool, name: str, config: dict) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED, "what threatens the crossing", Jsonb(config)),
        )
        return (await cur.fetchone())[0]


async def disable_compiler(pool, agent_id) -> None:
    """Flip the kill-switch off so a section's leftover missing pairs can
    never perturb a later run's sweep counts (the persistent-scratch rule
    in the module docstring)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE agents SET config = config || %s WHERE agent_id = %s",
            (Jsonb({"compiler_worker_enabled": 0.0}), agent_id),
        )


async def seed_memory(pool, agent_id, text: str, valid_at, *, importance=0.5):
    """A completed memory at the db layer — the verify_reflection seed
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
    )
    return await db.insert_observation(pool, plan)


async def seed_belief(
    pool,
    agent_id,
    content: str,
    valid_at,
    *,
    identity_relevant: bool = False,
    created_at=None,
    invalid_at=None,
):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO reflections (agent_id, content, identity_relevant, "
            "source_memory_ids, valid_at, created_at, invalid_at) "
            "VALUES (%s, %s, %s, '{}', %s, COALESCE(%s, now()), %s) "
            "RETURNING reflection_id",
            (agent_id, content, identity_relevant, valid_at, created_at, invalid_at),
        )
        return (await cur.fetchone())[0]


async def seed_bundle_row(
    pool,
    agent_id,
    reflection_id,
    *,
    scene_type: str = DEFAULT_SCENE_TYPE,
    w_relevance: float = 1.0,
    w_recency: float = 1.0,
    w_importance: float = 1.0,
    created_at=None,
):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO compiled_bundles (agent_id, reflection_id, "
            "scene_type, w_relevance, w_recency, w_importance, passthrough, "
            "created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, "
            "COALESCE(%s, now())) RETURNING bundle_id",
            (
                agent_id,
                reflection_id,
                scene_type,
                w_relevance,
                w_recency,
                w_importance,
                Jsonb({}),
                created_at,
            ),
        )
        return (await cur.fetchone())[0]


async def fetchrow(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def bundle_rows(pool, agent_id):
    """(reflection_id, scene_type, w_relevance, w_recency, w_importance,
    passthrough, input_tokens), insertion order."""
    return await fetchall(
        pool,
        "SELECT reflection_id, scene_type, w_relevance, w_recency, "
        "w_importance, passthrough, input_tokens FROM compiled_bundles "
        "WHERE agent_id = %s ORDER BY created_at, bundle_id",
        agent_id,
    )


async def run_turn(
    pool,
    settings,
    agent_id,
    utterance: str = "what news at the crossing?",
    *,
    scene_type: str | None = None,
    weight_overrides: WeightOverrides | None = None,
    defaults: dict | None = None,
) -> DialogueTurnResult:
    if defaults:
        settings = replace(settings, defaults={**settings.defaults, **defaults})
    providers = fake_providers()
    service = DialogueService(
        pool, providers, settings, RetrievalService(pool, providers, settings)
    )
    result = None
    async for item in service.run_dialogue_turn(
        DialogueTurnRequest(
            agent_id=agent_id,
            utterance=utterance,
            as_of=NOW,
            scene_type=scene_type,
            weight_overrides=weight_overrides,
        )
    ):
        if isinstance(item, DialogueTurnResult):
            result = item
    if result is None:
        fail("dialogue turn", "no terminal result")
    return result


async def run(uri: str) -> None:
    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    try:
        # ---------------- A. migration 008 shape --------------------------
        print("\n-- A. migration 008 shape")
        cols = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'compiled_bundles'",
            )
        }
        check(
            cols
            == {
                "bundle_id",
                "agent_id",
                "reflection_id",
                "scene_type",
                "w_relevance",
                "w_recency",
                "w_importance",
                "passthrough",
                "input_tokens",
                "output_tokens",
                "compile_ms",
                "created_at",
            },
            "A1 compiled_bundles carries exactly the specced columns",
        )
        cols = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'compiler_runs'",
            )
        }
        check(
            cols
            == {
                "run_id",
                "agent_id",
                "outcome",
                "error",
                "pairs_compiled",
                "pairs_failed",
                "passthrough_keys_dropped",
                "input_tokens",
                "output_tokens",
                "total_ms",
                "created_at",
            },
            "A2 compiler_runs carries exactly the specced columns",
        )
        probe_agent = await make_agent(pool, "walker-c-shape", AGENT_CONFIG)
        probe_belief = await seed_belief(pool, probe_agent, B1, NOW)
        try:
            await seed_bundle_row(pool, probe_agent, probe_belief, w_relevance=5.0)
            fail("A3 the multiplier CHECK has teeth", "5.0 was accepted")
        except psycopg.errors.CheckViolation:
            ok("A3 the multiplier CHECK rejects an out-of-range value")
        try:
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO compiler_runs (agent_id, outcome) VALUES (%s, 'junk')",
                    (probe_agent,),
                )
            fail("A4 the outcome CHECK has teeth", "'junk' was accepted")
        except psycopg.errors.CheckViolation:
            ok("A4 the outcome CHECK rejects an unknown value")
        indexes = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename IN ('compiled_bundles', 'compiler_runs')",
            )
        }
        check(
            {
                "compiled_bundles_pair_idx",
                "compiled_bundles_agent_id_idx",
                "compiler_runs_agent_id_idx",
            }
            <= indexes,
            "A5 the three specced indexes exist",
        )
        ledger = await fetchall(
            pool, "SELECT version FROM schema_migrations ORDER BY version"
        )
        check(
            [row[0] for row in ledger][-1] == "008_parameter_compiler.sql"
            and len(ledger) == 8,
            "A6 the ledger records 001-008",
        )

        # ---------------- B. the compile ladder ---------------------------
        print("\n-- B. the compile ladder")
        agent_b = await make_agent(
            pool, "walker-c-ladder", {**ENABLED, "scene_types": ["tavern"]}
        )
        b_beliefs = [
            await seed_belief(
                pool, agent_b, content, NOW + timedelta(minutes=i), created_at=NOW
            )
            for i, content in enumerate((B1, B2))
        ]
        worker = worker_for(pool, settings)
        attempts = await worker.sweep()
        check(
            attempts == 4,
            "B1 the sweep compiles every missing (belief x type) pair",
            "2 beliefs x {default, tavern}",
        )
        rows = await bundle_rows(pool, agent_b)
        check(
            len(rows) == 4
            and {(r[0], r[1]) for r in rows}
            == {(b, t) for b in b_beliefs for t in ("default", "tavern")}
            and all(
                MULTIPLIER_MIN <= v <= MULTIPLIER_MAX
                for r in rows
                for v in (r[2], r[3], r[4])
            )
            and all(list(r[5]) == ["fake.note"] and r[6] > 0 for r in rows),
            "B2 bundles land clamped, namespaced, token-accounted",
        )
        runs = await db.fetch_compiler_runs(pool, agent_b)
        check(
            len(runs) == 1
            and runs[0]["outcome"] == "completed"
            and runs[0]["pairs_compiled"] == 4
            and runs[0]["pairs_failed"] == 0
            and runs[0]["input_tokens"] > 0
            and runs[0]["total_ms"] is not None,
            "B3 one honest completed run row per attempted agent",
        )
        check(
            await worker.sweep() == 0
            and len(await db.fetch_compiler_runs(pool, agent_b)) == 1,
            "B4 a compiled pair never re-enters discovery (no-work = no row)",
        )

        agent_m = await make_agent(pool, "walker-c-malformed", dict(ENABLED))
        await seed_belief(pool, agent_m, B3, NOW)
        bad = worker_for(pool, settings, provider=MalformedCompilerProvider())
        check(
            await bad.sweep() == 1,
            "B5 a malformed pair still counts against the call budget",
        )
        runs = await db.fetch_compiler_runs(pool, agent_m)
        check(
            runs[-1]["pairs_failed"] == 1
            and runs[-1]["pairs_compiled"] == 0
            and runs[-1]["input_tokens"] == 7
            and await bundle_rows(pool, agent_m) == [],
            "B6 the failed pair records its spend and lands nothing",
        )
        check(
            await worker_for(pool, settings).sweep() == 1
            and len(await bundle_rows(pool, agent_m)) == 1,
            "B7 the missing pair persists and a good sweep retries naturally",
        )

        agent_p = await make_agent(pool, "walker-c-pinned", dict(ENABLED))
        await seed_belief(pool, agent_p, B1, NOW)
        pinned = worker_for(
            pool,
            settings,
            provider=PinnedCompilerProvider(
                w_relevance=9.0,
                w_recency=0.01,
                keys={"nokey": 1, "game.x": 2, ".bad": 3},
            ),
        )
        await pinned.sweep()
        rows = await bundle_rows(pool, agent_p)
        check(
            rows[0][2] == MULTIPLIER_MAX
            and rows[0][3] == MULTIPLIER_MIN
            and rows[0][5] == {"game.x": 2},
            "B8 clamp-at-write + the namespace filter hold at the row",
        )
        runs = await db.fetch_compiler_runs(pool, agent_p)
        check(
            runs[-1]["passthrough_keys_dropped"] == 2,
            "B9 dropped passthrough keys are counted on the run row",
        )

        agent_off = await make_agent(pool, "walker-c-off", dict(AGENT_CONFIG))
        await seed_belief(pool, agent_off, B1, NOW)
        check(
            await worker_for(pool, settings).sweep() == 0
            and await db.fetch_compiler_runs(pool, agent_off) == []
            and await bundle_rows(pool, agent_off) == [],
            "B10 the kill-switch skips the agent entirely (no calls, no rows)",
        )

        agent_cap = await make_agent(pool, "walker-c-cap", dict(ENABLED))
        cap_beliefs = [
            await seed_belief(
                pool,
                agent_cap,
                content,
                NOW + timedelta(minutes=i),
                created_at=NOW + timedelta(minutes=i),
            )
            for i, content in enumerate((B1, B2))
        ]
        capped = worker_for(pool, settings, defaults={"compiler_worker_batch": 1.0})
        check(
            await capped.sweep() == 1,
            "B11 compiler_worker_batch caps compile calls per sweep",
        )
        remaining = await db.fetch_missing_bundle_pairs(
            pool, agent_cap, scene_types=[DEFAULT_SCENE_TYPE], window_k=8
        )
        check(
            [p.reflection_id for p in remaining] == [cap_beliefs[0]],
            "B12 the budget cuts the deterministic prefix (newest first)",
        )
        check(
            await capped.sweep(limit=10) == 1,
            "B13 `limit` overrides the batch knob and the remainder completes",
        )

        agent_hard = await make_agent(pool, "walker-c-hardfail", dict(ENABLED))
        await seed_belief(pool, agent_hard, B2, NOW)
        hard = worker_for(pool, settings, provider=FailingCompilerProvider())
        await hard.sweep()
        runs = await db.fetch_compiler_runs(pool, agent_hard)
        check(
            runs[0]["pairs_failed"] == 1
            and runs[0]["input_tokens"] == 0
            and await bundle_rows(pool, agent_hard) == [],
            "B14 a hard call failure records without token spend and lands nothing",
        )
        await disable_compiler(pool, agent_hard)  # leftover missing pair

        # ---------------- C. window / liveness / eviction -----------------
        print("\n-- C. the all-mechanical staleness guard")
        agent_w = await make_agent(pool, "walker-c-window", dict(ENABLED))
        w_beliefs = [
            await seed_belief(
                pool,
                agent_w,
                content,
                NOW + timedelta(minutes=i),
                created_at=NOW + timedelta(minutes=i),
            )
            for i, content in enumerate((B1, B2, B3))
        ]
        windowed = worker_for(pool, settings, defaults={"compiler_window_k": 2.0})
        check(
            await windowed.sweep() == 2
            and {r[0] for r in await bundle_rows(pool, agent_w)} == set(w_beliefs[1:]),
            "C1 discovery windows the K most recent live beliefs",
        )
        await seed_memory(pool, agent_w, M_OLD, NOW - timedelta(hours=2))
        await seed_bundle_row(pool, agent_w, w_beliefs[0], w_recency=0.5)
        narrow = await run_turn(
            pool, settings, agent_w, defaults={"compiler_window_k": 1.0}
        )
        wide = await run_turn(
            pool, settings, agent_w, defaults={"compiler_window_k": 3.0}
        )
        check(
            w_beliefs[0] not in narrow.instrumentation.bundle_reflection_ids
            and w_beliefs[0] in wide.instrumentation.bundle_reflection_ids,
            "C2 the consume fetch honors the same window",
        )

        agent_e = await make_agent(pool, "walker-c-evict", dict(ENABLED))
        await seed_memory(pool, agent_e, M_OLD, NOW - timedelta(hours=2))
        e_belief = await seed_belief(pool, agent_e, B1, NOW)
        await seed_bundle_row(pool, agent_e, e_belief, w_recency=0.25)
        before = await run_turn(pool, settings, agent_e)
        rows_before = len(await bundle_rows(pool, agent_e))
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE reflections SET invalid_at = %s WHERE reflection_id = %s",
                (NOW + timedelta(minutes=5), e_belief),
            )
        after = await run_turn(pool, settings, agent_e)
        check(
            before.instrumentation.bundle_reflection_ids == [e_belief]
            and after.instrumentation.bundle_reflection_ids == []
            and after.instrumentation.bundle_w_recency == 1.0
            and len(await bundle_rows(pool, agent_e)) == rows_before,
            "C3 belief invalidation evicts instantly with zero bundle writes",
        )
        check(
            await db.fetch_missing_bundle_pairs(
                pool, agent_e, scene_types=[DEFAULT_SCENE_TYPE], window_k=8
            )
            == [],
            "C4 an invalidated belief's pairs leave discovery",
        )

        agent_n = await make_agent(pool, "walker-c-collapse", dict(ENABLED))
        await seed_memory(pool, agent_n, M_OLD, NOW - timedelta(hours=2))
        absorbed = [
            await seed_belief(
                pool,
                agent_n,
                content,
                NOW + timedelta(minutes=i),
                identity_relevant=True,
                created_at=NOW + timedelta(minutes=i),
            )
            for i, content in enumerate((B1, B2))
        ]
        n_worker = worker_for(pool, settings)
        await n_worker.sweep()
        survivor = await db.apply_consolidation(
            pool,
            agent_n,
            content="Taken together: tolls and trust rule the crossing.",
            source_memory_ids=[],
            absorbed_ids=absorbed,
            valid_at=NOW + timedelta(minutes=30),
        )
        collapsed = await run_turn(pool, settings, agent_n)
        pairs = await db.fetch_missing_bundle_pairs(
            pool, agent_n, scene_types=[DEFAULT_SCENE_TYPE], window_k=8
        )
        check(
            survivor is not None
            and collapsed.instrumentation.bundle_reflection_ids == []
            and [p.reflection_id for p in pairs] == [survivor],
            "C5 the consolidation collapse kills absorbed contributions "
            "and surfaces the survivor as new work",
        )
        check(
            await n_worker.sweep() == 1
            and (
                await run_turn(pool, settings, agent_n)
            ).instrumentation.bundle_reflection_ids
            == [survivor],
            "C6 the next sweep compiles the survivor and it applies",
        )

        # ---------------- D. consume parity + the re-rank -----------------
        print("\n-- D. consume parity + the per-scene re-rank")
        agent_d = await make_agent(
            pool, "walker-c-consume", {**AGENT_CONFIG, "scene_types": ["calm", "sharp"]}
        )
        await seed_memory(pool, agent_d, M_OLD, NOW - timedelta(hours=30))
        await seed_memory(pool, agent_d, M_NEW, NOW - timedelta(minutes=1))
        parity = await run_turn(pool, settings, agent_d, M_OLD)
        check(
            parity.instrumentation.scene_type_resolved == DEFAULT_SCENE_TYPE
            and parity.instrumentation.scene_type_unknown is False
            and (
                parity.instrumentation.bundle_w_relevance,
                parity.instrumentation.bundle_w_recency,
                parity.instrumentation.bundle_w_importance,
            )
            == (1.0, 1.0, 1.0)
            and parity.instrumentation.bundle_reflection_ids == [],
            "D1 a bundle-free turn carries the neutral echo",
        )
        check(
            [(r.memory_id, r.score) for r in parity.dialogue_view]
            == [(item.memory_id, item.score) for item in parity.items],
            "D2 zero bundles: dialogue_view == the served (id, score) "
            "projection — the parity contract",
        )

        d_belief = await seed_belief(pool, agent_d, B1, NOW)
        await seed_bundle_row(pool, agent_d, d_belief)  # all-1.0 neutral
        neutral = await run_turn(pool, settings, agent_d, M_OLD)
        check(
            [(r.memory_id, r.score) for r in neutral.dialogue_view]
            == [(r.memory_id, r.score) for r in parity.dialogue_view]
            and neutral.instrumentation.bundle_reflection_ids == [d_belief],
            "D3 a neutral bundle applies without moving a byte (ruling 1's license)",
        )

        await seed_bundle_row(
            pool, agent_d, d_belief, scene_type="calm", w_recency=0.25
        )
        await seed_bundle_row(
            pool, agent_d, d_belief, scene_type="sharp", w_recency=4.0
        )
        calm = await run_turn(pool, settings, agent_d, M_OLD, scene_type="calm")
        sharp = await run_turn(pool, settings, agent_d, M_OLD, scene_type="sharp")
        calm_order = [r.memory_id for r in calm.dialogue_view]
        sharp_order = [r.memory_id for r in sharp.dialogue_view]
        check(
            calm.instrumentation.bundle_w_recency == 0.25
            and sharp.instrumentation.bundle_w_recency == 4.0
            and set(calm_order) == set(sharp_order)
            and calm_order != sharp_order,
            "D4 opposite scene types re-rank the SAME served set "
            "(membership never changes)",
            f"calm top {str(calm_order[0])[:8]} vs sharp top {str(sharp_order[0])[:8]}",
        )
        hand_math_ok = True
        for result, w_rec in ((calm, 0.25), (sharp, 4.0)):
            by_id = {item.memory_id: item for item in result.items}
            for ref in result.dialogue_view:
                expected = weighted_score(by_id[ref.memory_id], 1.0, w_rec, 1.0)
                if abs(ref.score - expected) >= 1e-9:
                    hand_math_ok = False
        check(
            hand_math_ok,
            "D5 every view score equals the hand-computed exponent math",
        )

        unknown = await run_turn(pool, settings, agent_d, M_OLD, scene_type="moon")
        check(
            unknown.instrumentation.scene_type_resolved == DEFAULT_SCENE_TYPE
            and unknown.instrumentation.scene_type_unknown is True
            and unknown.instrumentation.bundle_reflection_ids == [d_belief],
            "D6 an unknown type log-and-continues onto the default bundle, flagged",
        )
        overrides = WeightOverrides(recency=4.0)
        with_bundle = await run_turn(
            pool,
            settings,
            agent_d,
            M_OLD,
            scene_type="sharp",
            weight_overrides=overrides,
        )
        check(
            with_bundle.instrumentation.bundle_w_recency == 4.0
            and [(r.memory_id, r.score) for r in with_bundle.dialogue_view]
            == [
                (r.memory_id, r.score)
                for r in (
                    await run_turn(
                        pool,
                        settings,
                        agent_d,
                        M_OLD,
                        weight_overrides=overrides,
                    )
                ).dialogue_view
            ],
            "D7 override x bundle clamps at the weight ceiling (honest echo, "
            "identical view)",
        )
        check(
            resolve_scene_type({}, None) == (DEFAULT_SCENE_TYPE, False)
            and resolve_scene_type({}, "anything") == (DEFAULT_SCENE_TYPE, True)
            and compose_bundle_weights((1.0, 2.0, 0.5), [])
            == (
                (1.0, 2.0, 0.5),
                (1.0, 1.0, 1.0),
            ),
            "D8 the pure functions hold without a DB (resolution + identity "
            "composition)",
        )

        # ---------------- E. the worker lifecycle at both sites -----------
        print("\n-- E. the worker lifecycle at both construction sites")
        direct = worker_for(pool, settings)
        direct.start()
        task = direct._task
        direct.start()
        check(
            task is not None and direct._task is task,
            "E1 start() is idempotent (one task)",
        )
        await direct.stop()
        check(direct._task is None, "E2 stop() cancels and clears the task")

        agent_s = await make_agent(pool, "walker-c-session", dict(ENABLED))
        runner = await SessionRunner.create(agent_s, settings=settings)
        try:
            check(
                runner.compiler_worker is not None
                and runner.compiler_worker._task is not None,
                "E3 SessionRunner.create wires AND starts the worker (REPL site)",
            )
            # Stop the poll loop BEFORE seeding: its startup sweep would
            # race the deterministic count below (sweep() stays callable).
            await runner.compiler_worker.stop()
            await seed_belief(pool, agent_s, B1, NOW)
            check(
                await runner.compile() == 1,
                "E4 runner.compile() drives one deterministic sweep",
            )
            check(
                await runner.compile() == 0,
                "E5 the sweep count makes a no-op visible (ruling 7)",
            )
        finally:
            await runner.close()
        check(
            runner.compiler_worker._task is None,
            "E6 runner.close() stops the worker before the pool",
        )

        # ---------------- F. the judge-shaped role/config surface ---------
        print("\n-- F. the role/config surface")
        check(
            SERVICE_DEFAULTS["compiler_worker_enabled"] == 0.0
            and SERVICE_DEFAULTS["compiler_poll_seconds"] == 60.0
            and SERVICE_DEFAULTS["compiler_worker_batch"] == 8.0
            and SERVICE_DEFAULTS["compiler_window_k"] == 8.0,
            "F1 the four knobs sit at their ruled defaults",
        )
        check(
            scene_types({}) == []
            and scene_types({"scene_types": ["a", "b"]}) == ["a", "b"]
            and (MULTIPLIER_MIN, MULTIPLIER_MAX) == (0.25, 4.0)
            and DEFAULT_SCENE_TYPE == "default",
            "F2 vocabulary accessor default + the frozen clamp constants",
        )
        real_env = {
            "DATABASE_URI": "postgresql://host/db",
            "TWICETOLD_PROVIDER_MODE": "real",
            "TWICETOLD_MODEL_IMPORTANCE": "m-write",
            "TWICETOLD_MODEL_RENDER": "m-write",
            "TWICETOLD_MODEL_TYPOLOGY": "m-write",
            "TWICETOLD_MODEL_ESCALATION": "m-esc",
            "TWICETOLD_MODEL_DIALOGUE": "m-dia",
            "TWICETOLD_MODEL_RECONSTRUCTION": "m-rec",
            "ANTHROPIC_API_KEY": "k",
            "OPENAI_API_KEY": "k",
        }
        loaded = load_settings(dict(real_env))
        check(
            loaded.model_compiler == "",
            "F3 real mode loads WITHOUT the var (judge-shaped, never required)",
        )
        loaded = load_settings({**real_env, "TWICETOLD_MODEL_COMPILER": "m-c"})
        check(loaded.model_compiler == "m-c", "F3b ...and loads it when present")
        check(
            isinstance(build_compiler_provider(settings), FakeCompilerProvider),
            "F4 fake mode builds the deterministic fake",
        )
        try:
            build_compiler_provider(replace(loaded, model_compiler=""))
            fail("F5 the loud first-use error", "no ConfigError raised")
        except ConfigError as exc:
            check(
                "TWICETOLD_MODEL_COMPILER" in str(exc),
                "F5 a real compile without the var raises ConfigError NAMING it",
            )
        agent_f = await make_agent(pool, "walker-c-config", dict(ENABLED))
        await seed_belief(pool, agent_f, B1, NOW)
        real_worker = CompilerWorker(
            pool, fake_providers(), replace(settings, provider_mode="real")
        )
        attempts = await real_worker.sweep()
        runs = await db.fetch_compiler_runs(pool, agent_f)
        check(
            attempts == 0
            and len(runs) == 1
            and runs[0]["outcome"] == "failed"
            and "TWICETOLD_MODEL_COMPILER" in runs[0]["error"]
            and real_worker._config_error_logged is True
            and await bundle_rows(pool, agent_f) == [],
            "F6 the worker's first real compile fails loud: a failed run "
            "row, logged once, nothing written",
        )
        await disable_compiler(pool, agent_f)  # leftover missing pairs
        check(
            (
                await fetchrow(
                    pool, "SELECT config FROM agents WHERE agent_id = %s", agent_f
                )
            )[0]["compiler_worker_enabled"]
            == 0.0,
            "F7 the section leaves no enabled agent with uncompiled work "
            "(the persistent-scratch rule)",
        )
    finally:
        await pool.close()

    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
