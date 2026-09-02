"""verify_reflection.py — structural done-when walker for reflection
(Phase C2; reflection.md, the rulings dated 2026-08-15; migration 007).

Runs the reflection done-when criteria against the SCRATCH database
(default: the .env DATABASE_URI with its database name swapped to
`twicetold_test`), with deterministic fake providers — offline, keyless, and
structural-only per tests\\CLAUDE.md. The service is exercised through
`ReflectionService.reflect` and the worker through `sweep()` (the
deterministic no-timer entries); the pipeline's time basis is the request's
client_timestamp, so the clock freezes by freezing the request. The
write-path and read-path walkers staying byte-identical at their pre-C2
criteria are the zero-retrieval-change evidence; THIS walker owns the new
mechanism: the migration 007 shape, the reflect verb ladder (grounding,
floor, empty-valid), sampling determinism incl. the pin-plain-decay rule,
prompt purity, render/consolidation/dialogue-seam parity, the RRR guard,
the mechanical trim + constraint-follows-liveness + per-affected eviction,
the worker lifecycle at both construction sites, and the judge-shaped
role/config surface.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_reflection.py [--database-uri <scratch-uri>]

The scratch database is created and dropped around this walker by the build
task; the product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

import psycopg.errors
from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.config import SERVICE_DEFAULTS, ConfigError, Settings, load_settings
from app.db import build_pool
from app.dialogue import _BLOCK_PROSE_INSTRUCTION, assemble_prose_prompt
from app.identity import ensure_identity_document, render_identity_document
from app.providers import (
    FailingReflectionProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeReflectionProvider,
    FakeWriteProvider,
    Providers,
    ReflectionCallResult,
    ReflectionConclusion,
    ReflectionItem,
    build_reflection_provider,
)
from app.reflection import (
    ReflectionCallError,
    ReflectionFloorError,
    ReflectionService,
    ReflectionWorker,
    assemble_consolidation_prompt,
    assemble_reflection_prompt,
    compute_rrr,
)
from app.schemas import ReflectRequest
from app.session import SessionRunner

NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
SEED = "A verification NPC, keeper of the forge ledger."
TEXTS = (
    "Bram shattered the lantern at the ford gate.",
    "A grey cat took up residence in the mill loft.",
    "The well rope frayed and was replaced with new hemp.",
    "The miller paid his toll without argument.",
    "Rain flooded the low road past the ford.",
)

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


def fake_providers(**overrides) -> Providers:
    return Providers(
        write=overrides.get("write", FakeWriteProvider()),
        escalation=overrides.get("escalation", FakeEscalationProvider()),
        embedding=overrides.get("embedding", FakeEmbeddingProvider()),
        dialogue=overrides.get("dialogue", FakeProseProvider()),
        reconstruction=overrides.get("reconstruction", FakeReconstructionProvider()),
    )


def service_for(pool, settings, *, defaults: dict | None = None, provider=None):
    if defaults:
        settings = replace(settings, defaults={**settings.defaults, **defaults})
    return ReflectionService(
        pool, fake_providers(), settings, reflection_provider=provider
    )


def worker_for(pool, settings, *, defaults: dict | None = None, provider=None):
    if defaults:
        settings = replace(settings, defaults={**settings.defaults, **defaults})
    return ReflectionWorker(
        pool, fake_providers(), settings, reflection_provider=provider
    )


def request(consolidate=None) -> ReflectRequest:
    return ReflectRequest(client_timestamp=NOW, consolidate=consolidate)


class AllUngrounded:
    def reflect(self, *, system_prompt, user_content, items):
        return ReflectionCallResult(
            conclusions=[
                ReflectionConclusion(
                    content="[fixture] cites nothing",
                    identity_relevant=False,
                    source_memory_ids=[],
                ),
                ReflectionConclusion(
                    content="[fixture] cites a foreign id",
                    identity_relevant=True,
                    source_memory_ids=[str(uuid4())],
                ),
            ],
            input_tokens=5,
            output_tokens=5,
        )

    def consolidate(self, **_kwargs):
        raise AssertionError("consolidation must not be reached")


class PartiallyUngrounded:
    def reflect(self, *, system_prompt, user_content, items):
        return ReflectionCallResult(
            conclusions=[
                ReflectionConclusion(
                    content="[fixture] grounded conclusion",
                    identity_relevant=False,
                    source_memory_ids=[items[0].memory_id],
                ),
                ReflectionConclusion(
                    content="[fixture] ungrounded conclusion",
                    identity_relevant=False,
                    source_memory_ids=[str(uuid4())],
                ),
            ],
            input_tokens=5,
            output_tokens=5,
        )

    def consolidate(self, **_kwargs):
        raise AssertionError("consolidation must not be reached")


class ConcludesNothing:
    def reflect(self, *, system_prompt, user_content, items):
        return ReflectionCallResult(conclusions=[], input_tokens=3, output_tokens=0)

    def consolidate(self, **_kwargs):
        raise AssertionError("consolidation must not be reached")


async def make_agent(pool, name: str, config: dict) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED, "what threatens the forge", Jsonb(config)),
        )
        return (await cur.fetchone())[0]


async def add_component(pool, agent_id, canonical: str) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, %s, %s, 'person') RETURNING component_id",
            (agent_id, canonical, []),
        )
        return (await cur.fetchone())[0]


async def seed(
    pool,
    agent_id,
    text: str,
    valid_at,
    *,
    importance: float = 0.5,
    pinned: bool = False,
    component_spans: tuple = (),
) -> db.InsertOutcome:
    """A completed (non-pending) memory at the db layer — the suite's seed
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
        pinned=pinned,
        decay_class="episodic",
        decay_class_unknown=False,
        embedding=vec,
        entities=None,
        spans=[
            db.SpanPlan(s, e, str(cid), "person") for (s, e, cid) in component_spans
        ],
    )
    return await db.insert_observation(pool, plan)


async def fetchrow(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def reflection_rows(pool, agent_id):
    return await fetchall(
        pool,
        "SELECT content, identity_relevant, source_memory_ids, valid_at, "
        "invalid_at, reflection_id FROM reflections WHERE agent_id = %s "
        "ORDER BY created_at, reflection_id",
        agent_id,
    )


async def seed_many(pool, agent_id, n=5, importance=0.5):
    seeded = []
    for i, text in enumerate(TEXTS[:n]):
        seeded.append(
            await seed(
                pool,
                agent_id,
                text,
                NOW - timedelta(hours=n - i),
                importance=importance,
            )
        )
    return seeded


async def run(uri: str) -> None:
    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    try:
        # ---------------- A. migration 007 shape --------------------------
        print("\n-- A. migration 007 shape")
        table = await fetchrow(
            pool,
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = 'reflection_runs'",
        )
        check(table[0] == 1, "A1 reflection_runs exists")
        cols = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'reflection_runs'",
            )
        }
        expected_cols = {
            "run_id",
            "agent_id",
            "outcome",
            "error",
            "reflections_written",
            "dropped_ungrounded",
            "consolidation_ran",
            "consolidation_failed",
            "rrr",
            "rrr_blocked",
            "pruned_components",
            "evicted_cache_rows",
            "pressure_before",
            "pressure_after",
            "reflect_ms",
            "consolidation_ms",
            "insert_ms",
            "total_ms",
            "reflect_input_tokens",
            "reflect_output_tokens",
            "consolidation_input_tokens",
            "consolidation_output_tokens",
            "created_at",
        }
        check(
            cols == expected_cols,
            "A2 reflection_runs carries exactly the 23 spec columns",
            f"{len(cols)} columns",
        )
        probe_agent = await make_agent(pool, "walker-r-probe", AGENT_CONFIG)
        outcome_ok = True
        try:
            async with pool.connection() as conn:
                async with conn.transaction(force_rollback=True):
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "INSERT INTO reflection_runs (agent_id, outcome) "
                            "VALUES (%s, 'bogus')",
                            (probe_agent,),
                        )
        except psycopg.errors.CheckViolation:
            outcome_ok = False
        check(not outcome_ok, "A3 the outcome CHECK rejects junk")
        idx = await fetchrow(
            pool,
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'reflection_runs_agent_id_idx'",
        )
        check(
            idx is not None and "agent_id" in idx[0],
            "A4 reflection_runs_agent_id_idx exists",
        )
        ledger = await fetchall(
            pool, "SELECT version FROM schema_migrations ORDER BY version"
        )
        check(
            # 008 joined the ledger at the parameter-compiler build (Phase
            # C3, 2026-08-17) — the mechanical ledger-pin update every
            # migration makes to prior walkers. The reflection mechanics
            # this walker verifies are untouched by 008.
            [row[0] for row in ledger][-1] == "008_parameter_compiler.sql"
            and len(ledger) == 8,
            "A5 the ledger records 001-008",
        )
        refl_cols = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'reflections'",
            )
        }
        check(
            refl_cols
            == {
                "reflection_id",
                "agent_id",
                "content",
                "identity_relevant",
                "source_memory_ids",
                "created_at",
                "valid_at",
                "invalid_at",
            },
            "A6 the dormant 001 reflections table carries the mechanism as-is",
        )

        # ---------------- B. the reflect verb ladder -----------------------
        print("\n-- B. the reflect verb ladder")
        b_agent = await make_agent(pool, "walker-r-happy", AGENT_CONFIG)
        b_seeded = await seed_many(pool, b_agent)
        service = service_for(pool, settings)
        result = await service.reflect(b_agent, request())
        check(
            len(result.reflections) == 2
            and set(result.sampled_memory_ids) == {s.memory_id for s in b_seeded},
            "B1 happy path: conclusions stored from the full sampled pool",
        )
        sampled = set(result.sampled_memory_ids)
        check(
            all(
                o.source_memory_ids and set(o.source_memory_ids) <= sampled
                for o in result.reflections
            ),
            "B2 every citation set is non-empty and inside the sampled ids",
        )
        rows = await reflection_rows(pool, b_agent)
        check(
            len(rows) == 2
            and all(r[3] == NOW and r[4] is None for r in rows)
            and sorted(r[1] for r in rows) == [False, True],
            "B3 bi-temporal rows at the request's valid_at, all live",
        )
        check(
            result.pressure_before > 0.0 and result.pressure_after == 0.0,
            "B4 pressure served before/after (consumed by the reflect event)",
        )
        inst = result.instrumentation
        check(
            inst.reflect_ms >= 0.0
            and inst.insert_ms >= 0.0
            and inst.total_ms >= inst.insert_ms
            and inst.reflect_input_tokens > 0,
            "B5 honest instrumentation rides the payload (endpoint = no run row)",
        )
        run_count = await fetchrow(pool, "SELECT count(*) FROM reflection_runs")
        check(
            run_count[0] == 0,
            "B6 the service wrote NO run row (the C1 endpoint/worker split)",
        )

        p_agent = await make_agent(pool, "walker-r-partial", AGENT_CONFIG)
        await seed_many(pool, p_agent)
        partial = await service_for(
            pool, settings, provider=PartiallyUngrounded()
        ).reflect(p_agent, request())
        check(
            partial.dropped_ungrounded == 1
            and len(partial.reflections) == 1
            and len(await reflection_rows(pool, p_agent)) == 1,
            "B7 partial grounding: the valid subset stores, the drop counts",
        )
        u_agent = await make_agent(pool, "walker-r-ungrounded", AGENT_CONFIG)
        await seed_many(pool, u_agent)
        try:
            await service_for(pool, settings, provider=AllUngrounded()).reflect(
                u_agent, request()
            )
            fail("B8 all-ungrounded raises", "no error raised")
        except ReflectionCallError:
            pass
        check(
            await reflection_rows(pool, u_agent) == [],
            "B8 all-ungrounded is the 502 class with zero rows written",
        )
        try:
            await service_for(
                pool, settings, provider=FailingReflectionProvider()
            ).reflect(u_agent, request())
            fail("B9 call failure raises", "no error raised")
        except ReflectionCallError:
            pass
        check(
            await reflection_rows(pool, u_agent) == [],
            "B9 a failed reflect call writes nothing (fail-loud)",
        )
        empty = await service_for(pool, settings, provider=ConcludesNothing()).reflect(
            u_agent, request()
        )
        check(
            empty.reflections == []
            and empty.dropped_ungrounded == 0
            and await reflection_rows(pool, u_agent) == [],
            "B10 a genuinely empty conclusion list is a valid outcome",
        )
        f_agent = await make_agent(pool, "walker-r-floor", AGENT_CONFIG)
        await seed(pool, f_agent, TEXTS[0], NOW - timedelta(hours=1))
        try:
            await service.reflect(f_agent, request())
            fail("B11 the floor raises", "no error raised")
        except ReflectionFloorError:
            pass
        check(
            await reflection_rows(pool, f_agent) == [],
            "B11 below reflection_min_episodes: the 409 class, zero rows",
        )

        s_agent = await make_agent(pool, "walker-r-sample", AGENT_CONFIG)
        fresh = await seed(
            pool, s_agent, TEXTS[0], NOW - timedelta(hours=1), importance=0.9
        )
        mid = await seed(
            pool, s_agent, TEXTS[1], NOW - timedelta(days=1), importance=0.9
        )
        old = await seed(
            pool, s_agent, TEXTS[2], NOW - timedelta(days=10), importance=0.9
        )
        pinned = await seed(
            pool,
            s_agent,
            TEXTS[3],
            NOW - timedelta(days=30),
            importance=0.9,
            pinned=True,
        )
        topk = service_for(
            pool,
            settings,
            defaults={"reflection_sample_k": 3.0, "reflection_min_episodes": 2.0},
        )
        draw1 = await topk.reflect(s_agent, request())
        check(
            draw1.sampled_memory_ids == [fresh.memory_id, mid.memory_id, old.memory_id],
            "B12 deterministic top-k by importance_norm x recency, never a lottery",
        )
        check(
            pinned.memory_id not in draw1.sampled_memory_ids,
            "B13 a pinned ancient row takes the PLAIN decay score "
            "(pin keeps exactly two meanings; reflection is neither)",
        )
        draw2 = await topk.reflect(s_agent, request())
        check(
            draw2.sampled_memory_ids == draw1.sampled_memory_ids,
            "B14 the draw reproduces byte-identically on identical inputs",
        )

        items = [
            ReflectionItem(
                memory_id=str(s.memory_id),
                telling=f"[walker seed] {TEXTS[i]}",
                importance=0.5,
                valid_at=(NOW - timedelta(hours=5 - i)).isoformat(),
            )
            for i, s in enumerate(b_seeded[:3])
        ]
        sys1, user1 = assemble_reflection_prompt(SEED, items)
        sys2, user2 = assemble_reflection_prompt(SEED, list(reversed(items)))
        check(
            (sys1, user1) == (sys2, user2),
            "B15 the reflect prompt is pure and byte-stable (items sorted "
            "by memory_id)",
        )
        no_doc_sys, no_doc_user = assemble_reflection_prompt("", items)
        check(
            "[identity]" not in no_doc_user and no_doc_sys == sys1,
            "B16 the identity block is omitted for an empty document "
            "(the NULL-seed rule)",
        )
        cons_sys, cons_user = assemble_consolidation_prompt(
            SEED, f"{SEED}\n\nbelief", ["belief one", "belief two"]
        )
        check(
            "[seed identity]" in cons_user
            and "[current document]" in cons_user
            and "[beliefs]" in cons_user
            and "No other text." in cons_sys,
            "B17 the consolidation prompt carries seed + document + beliefs",
        )
        check(
            compute_rrr(["abcd"], []) is None
            and compute_rrr([], ["abcd"]) is None
            and compute_rrr(["abcd"], ["abcd"]) == 1.0
            and compute_rrr(["abcd"], ["wxyz", "abce"]) == 0.75,
            "B18 compute_rrr: max SequenceMatcher ratio, None without priors",
        )

        # ---------------- C. render / consolidation / dialogue parity -----
        print("\n-- C. render, consolidation, and the dialogue seam")
        c_agent = await make_agent(pool, "walker-r-identity", AGENT_CONFIG)
        await seed_many(pool, c_agent)
        rendered, version = render_identity_document(SEED)
        check(
            rendered == SEED and version == hashlib.sha256(SEED.encode()).hexdigest(),
            "C1 zero reflections: the render is the seed VERBATIM, "
            "the hash contract unchanged",
        )
        v0, doc0, _ = await ensure_identity_document(pool, c_agent, SEED)
        check(
            (v0, doc0) == (version, SEED),
            "C2 ensure at zero reflections reproduces the pre-C2 document",
        )
        prompt0 = assemble_prose_prompt(doc0, [])
        check(
            prompt0 == f"[identity]\n{SEED}\n\n{_BLOCK_PROSE_INSTRUCTION}",
            "C3 the prose prompt is byte-identical to the pre-C2 shape "
            "at zero reflections",
        )
        first = await service.reflect(c_agent, request())
        belief_rows = [r for r in await reflection_rows(pool, c_agent) if r[1]]
        v1, doc1, _ = await ensure_identity_document(pool, c_agent, SEED)
        check(
            v1 == first.identity_version and doc1 == f"{SEED}\n\n{belief_rows[0][0]}",
            "C4 an identity-relevant reflection joins the render in stable chronology",
        )
        check(
            f"[identity]\n{SEED}\n\n{belief_rows[0][0]}"
            in assemble_prose_prompt(doc1, []),
            "C5 speech sees the belief: the [identity] block carries it "
            "after recompile",
        )
        second = await service.reflect(c_agent, request(consolidate=True))
        check(
            second.rrr is not None
            and second.rrr >= 0.85
            and second.rrr_blocked_consolidation is True
            and second.consolidation is None,
            "C6 RRR at/above threshold blocks consolidation, even forced",
            f"rrr={second.rrr:.3f}",
        )
        check(
            len(await reflection_rows(pool, c_agent)) == 4,
            "C7 the blocked call's reflections still stored (honest evidence)",
        )

        k_agent = await make_agent(pool, "walker-r-consolidate", AGENT_CONFIG)
        await seed_many(pool, k_agent)
        pre_version, _, _ = await ensure_identity_document(pool, k_agent, SEED)
        cons = await service.reflect(k_agent, request(consolidate=True))
        check(
            cons.consolidation is not None and cons.consolidation.failed is False,
            "C8 the consolidation stage runs when forced and RRR-clear",
        )
        k_rows = {r[5]: r for r in await reflection_rows(pool, k_agent)}
        absorbed_ids = cons.consolidation.absorbed_reflection_ids
        check(
            all(k_rows[rid][4] == NOW for rid in absorbed_ids)
            and all(rid in k_rows for rid in absorbed_ids),
            "C9 absorbed rows carry invalid_at and stay queryable "
            "(bi-temporal, never deleted)",
        )
        new_row = k_rows[cons.consolidation.reflection_id]
        union = sorted({m for rid in absorbed_ids for m in k_rows[rid][2]})
        check(
            new_row[4] is None and new_row[1] is True and sorted(new_row[2]) == union,
            "C10 the consolidated reflection is live, identity-relevant, "
            "provenance = the source union",
        )
        check(
            cons.identity_version != pre_version
            and (
                await fetchrow(
                    pool,
                    "SELECT rendered_text FROM identity_documents "
                    "WHERE agent_id = %s AND identity_version = %s",
                    k_agent,
                    cons.identity_version,
                )
            )[0]
            == f"{SEED}\n\n{new_row[0]}",
            "C11 the version bumps and the document carries the belief, "
            "not the absorbed rows",
        )

        # ---------------- D. trim + liveness + eviction --------------------
        print("\n-- D. the mechanical trim, liveness, and eviction")
        d_agent = await make_agent(pool, "walker-r-trim", AGENT_CONFIG)
        authored = await add_component(pool, d_agent, "Keeper")
        stale_comp = await add_component(pool, d_agent, "Miller")
        fresh_comp = await add_component(pool, d_agent, "Smith")
        stale_mem = await seed(
            pool,
            d_agent,
            TEXTS[3],
            NOW - timedelta(days=30),
            importance=0.1,
            component_spans=((0, 10, stale_comp),),
        )
        fresh_mem = await seed(
            pool,
            d_agent,
            TEXTS[0],
            NOW - timedelta(hours=2),
            importance=0.2,
            component_spans=((0, 4, fresh_comp),),
        )
        top_mem = await seed(
            pool, d_agent, TEXTS[4], NOW - timedelta(minutes=1), importance=0.9
        )
        await db.insert_cache_row(pool, stale_mem.memory_id, "v|b0", "stale")
        await db.insert_cache_row(pool, top_mem.memory_id, "v|b0", "fresh")
        trim = service_for(
            pool,
            settings,
            defaults={
                "reflection_sample_k": 1.0,
                "reflection_min_episodes": 1.0,
                "reflection_trim_stale_seconds": 7 * 86400.0,
            },
        )
        t_result = await trim.reflect(d_agent, request())
        check(
            t_result.sampled_memory_ids == [top_mem.memory_id]
            and t_result.pruned_component_ids == [stale_comp],
            "D1 the 3-clause rule prunes exactly the all-stale evidenced component",
        )
        pruned_row = await fetchrow(
            pool,
            "SELECT invalid_at FROM identity_components WHERE component_id = %s",
            stale_comp,
        )
        check(
            pruned_row[0] == NOW,
            "D2 prune = invalid_at at the request's time, never DELETE",
        )
        live = await db.fetch_live_components(pool, d_agent)
        check(
            {c["component_id"] for c in live} == {authored, fresh_comp},
            "D3 the authored (zero-span) and fresh-evidence components "
            "survive; the gate's live set shrinks",
        )
        check(
            t_result.evicted_cache_rows == 1
            and (
                await fetchrow(
                    pool,
                    "SELECT count(*) FROM reconstruction_cache WHERE memory_id = %s",
                    stale_mem.memory_id,
                )
            )[0]
            == 0
            and (
                await fetchrow(
                    pool,
                    "SELECT count(*) FROM reconstruction_cache WHERE memory_id = %s",
                    top_mem.memory_id,
                )
            )[0]
            == 1,
            "D4 eviction is per-affected-memory only",
        )
        srcs = await db.fetch_reconstruction_sources(
            pool, [stale_mem.memory_id, fresh_mem.memory_id]
        )
        check(
            srcs[stale_mem.memory_id].spans == []
            and srcs[fresh_mem.memory_id].spans == [(0, 4)],
            "D5 constraint-follows-liveness: the pruned component's spans "
            "drop; NULL-component and live spans stand",
        )

        a_agent = await make_agent(pool, "walker-r-active", AGENT_CONFIG)
        formative = await add_component(pool, a_agent, "Reeve")
        await seed(
            pool,
            a_agent,
            TEXTS[2],
            NOW - timedelta(days=30),
            importance=0.9,
            component_spans=((0, 8, formative),),
        )
        for i in range(3):
            await seed(pool, a_agent, TEXTS[i], NOW - timedelta(hours=3 - i))
        active = await service_for(
            pool,
            settings,
            defaults={"reflection_trim_stale_seconds": 7 * 86400.0},
        ).reflect(a_agent, request())
        check(
            active.pruned_component_ids == []
            and (
                await fetchrow(
                    pool,
                    "SELECT invalid_at FROM identity_components "
                    "WHERE component_id = %s",
                    formative,
                )
            )[0]
            is None,
            "D6 active evidence: a sampled memory's component never prunes, "
            "stale or not",
        )

        z_agent = await make_agent(pool, "walker-r-zerotrim", AGENT_CONFIG)
        z_comp = await add_component(pool, z_agent, "Miller")
        z_mem = await seed(
            pool,
            z_agent,
            TEXTS[3],
            NOW - timedelta(days=30),
            importance=0.1,
            component_spans=((0, 10, z_comp),),
        )
        await seed(pool, z_agent, TEXTS[4], NOW - timedelta(minutes=1), importance=0.9)
        before_srcs = await db.fetch_reconstruction_sources(pool, [z_mem.memory_id])
        z_result = await service_for(
            pool,
            settings,
            defaults={
                "reflection_sample_k": 1.0,
                "reflection_min_episodes": 1.0,
                "reflection_trim_stale_seconds": 0.0,
            },
        ).reflect(z_agent, request())
        after_srcs = await db.fetch_reconstruction_sources(pool, [z_mem.memory_id])
        check(
            z_result.pruned_component_ids == []
            and z_result.evicted_cache_rows == 0
            and after_srcs == before_srcs,
            "D7 trim_stale_seconds 0.0 disables the trim entirely "
            "(kill-switch shape); sources byte-identical",
        )

        # ---------------- E. worker lifecycle at both sites ----------------
        print("\n-- E. worker lifecycle at both construction sites")
        enabled = {
            **AGENT_CONFIG,
            "reflection_worker_enabled": 1.0,
            "reflection_pressure_norm": 1.0,
        }
        due = await make_agent(pool, "walker-r-due", enabled)
        quiet = await make_agent(
            pool, "walker-r-quiet", {**enabled, "reflection_pressure_norm": 1000.0}
        )
        await seed_many(pool, due, n=4)
        await seed_many(pool, quiet, n=4)
        worker = worker_for(pool, settings)
        swept = await worker.sweep()
        e_runs = await fetchall(
            pool,
            "SELECT agent_id, outcome, reflections_written FROM reflection_runs "
            "ORDER BY created_at",
        )
        check(
            swept == 1 and e_runs == [(due, "completed", 2)],
            "E1 sweep reflects the due agent once with a completed run row; "
            "below-threshold and disabled agents untouched",
        )
        check(
            await worker.sweep() == 0,
            "E2 the reflect event consumed the pressure: the next sweep no-ops",
        )
        worker.start()
        task = worker._task
        check(task is not None, "E3 start() spawns the worker task")
        worker.start()
        check(worker._task is task, "E4 start() is idempotent")
        await worker.stop()
        check(worker._task is None, "E5 stop() cancels and clears it")

        retry = await make_agent(pool, "walker-r-retry", enabled)
        await seed_many(pool, retry, n=4)
        failing = worker_for(pool, settings, provider=FailingReflectionProvider())
        check(
            await failing.sweep() == 1 and await failing.sweep() == 1,
            "E6 a failing reflect is retried naturally next sweep "
            "(no attempts ledger — pressure persists)",
        )
        retry_runs = [
            r[0]
            for r in await fetchall(
                pool,
                "SELECT outcome FROM reflection_runs WHERE agent_id = %s "
                "ORDER BY created_at",
                retry,
            )
        ]
        check(
            retry_runs == ["failed", "failed"]
            and await reflection_rows(pool, retry) == [],
            "E7 failed run rows with nothing written; the worker stays alive",
        )
        check(
            await worker_for(pool, settings).sweep() == 1
            and [
                r[0]
                for r in await fetchall(
                    pool,
                    "SELECT outcome FROM reflection_runs WHERE agent_id = %s "
                    "ORDER BY created_at",
                    retry,
                )
            ]
            == ["failed", "failed", "completed"],
            "E8 a later good sweep completes the same agent",
        )

        thin = await make_agent(
            pool,
            "walker-r-thin",
            {**enabled, "reflection_pressure_norm": 0.01},
        )
        await seed(pool, thin, TEXTS[0], NOW - timedelta(hours=1))
        pre_thin = (await fetchrow(pool, "SELECT count(*) FROM reflection_runs"))[0]
        check(
            await worker_for(pool, settings).sweep() == 0
            and (await fetchrow(pool, "SELECT count(*) FROM reflection_runs"))[0]
            == pre_thin,
            "E9 below the episode floor the worker skips with NO run row",
        )

        runner = await SessionRunner.create(
            due,
            settings=settings,
            providers=fake_providers(),
            pool=pool,
            phase_tag="walker",
        )
        check(
            runner.reflection_worker is not None
            and runner.reflection_worker._task is not None,
            "E10 SessionRunner.create wires AND starts the worker (REPL site)",
        )
        runner.as_of = NOW
        session_result = await runner.reflect()
        check(
            len(session_result.reflections) >= 1 and session_result.agent_id == due,
            "E11 runner.reflect() drives the same seam at the session's time",
        )
        await runner.close()
        check(
            runner.reflection_worker._task is None,
            "E12 runner.close() stops the worker before the pool",
        )

        # ---------------- F. the judge-shaped role/config surface ----------
        print("\n-- F. role/config shape")
        knob_expectations = {
            "reflection_worker_enabled": 0.0,
            "reflection_poll_seconds": 60.0,
            "reflection_worker_batch": 4.0,
            "reflection_pressure_threshold": 1.0,
            "reflection_pressure_norm": 10.0,
            "reflection_sample_k": 16.0,
            "reflection_min_episodes": 4.0,
            "reflection_rrr_threshold": 0.85,
            "reflection_rrr_window": 8.0,
            "reflection_consolidate_at": 5.0,
            "reflection_trim_stale_seconds": 2592000.0,
        }
        check(
            {k: SERVICE_DEFAULTS[k] for k in knob_expectations} == knob_expectations,
            "F1 the eleven reflection knobs sit in SERVICE_DEFAULTS at the "
            "ruled defaults",
        )
        real_env = {
            "DATABASE_URI": "postgresql://u:p@192.0.2.1:5432/postgres",
            "TWICETOLD_PROVIDER_MODE": "real",
            "ANTHROPIC_API_KEY": "k1",
            "OPENAI_API_KEY": "k2",
            "TWICETOLD_MODEL_IMPORTANCE": "m",
            "TWICETOLD_MODEL_RENDER": "m",
            "TWICETOLD_MODEL_TYPOLOGY": "m",
            "TWICETOLD_MODEL_ESCALATION": "m",
            "TWICETOLD_MODEL_DIALOGUE": "m",
            "TWICETOLD_MODEL_RECONSTRUCTION": "m",
        }
        loaded = load_settings(dict(real_env))
        check(
            loaded.provider_mode == "real" and loaded.model_reflection == "",
            "F2 real mode LOADS without TWICETOLD_MODEL_REFLECTION "
            "(loaded-never-required, the judge shape)",
        )
        check(
            load_settings(
                {**real_env, "TWICETOLD_MODEL_REFLECTION": "model-f"}
            ).model_reflection
            == "model-f",
            "F3 the var loads in real mode when present",
        )
        check(
            isinstance(build_reflection_provider(settings), FakeReflectionProvider),
            "F4 fake mode builds the deterministic fake",
        )
        try:
            build_reflection_provider(loaded)
            fail("F5 the loud first-use error", "no ConfigError raised")
        except ConfigError as exc:
            check(
                "TWICETOLD_MODEL_REFLECTION" in str(exc),
                "F5 a real reflect without the var raises ConfigError NAMING it",
            )
        cfg_agent = await make_agent(pool, "walker-r-config", AGENT_CONFIG)
        await seed_many(pool, cfg_agent)
        real_service = ReflectionService(
            pool, fake_providers(), replace(settings, provider_mode="real")
        )
        try:
            await real_service.reflect(cfg_agent, request())
            fail("F6 first real reflect fails loud", "no ConfigError raised")
        except ConfigError:
            pass
        check(
            await reflection_rows(pool, cfg_agent) == [],
            "F6 the loud failure fires at first use with nothing written",
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
