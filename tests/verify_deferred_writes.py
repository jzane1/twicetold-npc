"""verify_deferred_writes.py — structural done-when walker for deferred write
processing (Phase C1; deferred-writes.md, ruled 2026-08-12; migration 006).

Runs the deferred-write done-when criteria against the SCRATCH database
(default: the .env DATABASE_URI with its database name swapped to
`twicetold_test`), with deterministic fake providers — offline, keyless, and
structural-only per tests\\CLAUDE.md. The worker is exercised through
`drain()` (the deterministic entry, no timers). The write-path walker
staying byte-identical at its pre-C1 criteria is the deferred-OFF parity
evidence; THIS walker owns the new mechanism: the migration shape, the
deferred observe row shape, the kill-switch parity shape, the full
completion/retry/terminal/facts-only/repair/orphan ladder, the anchor-set
membership, and the worker lifecycle at both construction sites (the
DeferredWriteWorker directly, and SessionRunner.create's wiring — the API
lifespan's four-line mirror of it is covered by the console-harness gate,
which serves the real app).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_deferred_writes.py [--database-uri <scratch-uri>]

The scratch database is created and dropped around this walker by the build
task; the product `twicetold` DB is never touched.
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
from app.config import Settings
from app.db import build_pool
from app.deferred import DeferredWriteWorker
from app.ingest import IngestService
from app.providers import (
    FailingWriteProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    FlakyWriteProvider,
    NoveltyEscalationProvider,
    Providers,
)
from app.schemas import ObserveEvent
from app.session import SessionRunner

NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
T_OBS = "Mara sharpened my blade at the forge while John watched."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
}
DEFERRED_CONFIG = {**AGENT_CONFIG, "deferred_writes_enabled": 1.0}

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


def worker_for(pool, settings, *, defaults: dict | None = None, **overrides):
    if defaults:
        settings = replace(settings, defaults={**settings.defaults, **defaults})
    return DeferredWriteWorker(pool, fake_providers(**overrides), settings)


async def make_agent(pool, name: str, config: dict) -> tuple:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, "A verification NPC.", "what threatens the forge", Jsonb(config)),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, 'Mara', %s, 'person') RETURNING component_id",
            (agent_id, ["the blacksmith"]),
        )
        component_id = (await cur.fetchone())[0]
    return agent_id, component_id


async def seed_pending(pool, agent_id, text: str, **overrides) -> db.InsertOutcome:
    """A deferred-mode pending row at the db layer (the Set K seed shape)."""
    vec = (
        overrides["embedding"]
        if "embedding" in overrides
        else FakeEmbeddingProvider().embed([text]).vectors[0]
    )
    declared = overrides.get("declared_typology")
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=text,
        valid_at=overrides.get("valid_at", NOW - timedelta(hours=1)),
        importance_raw=None,
        scoring_failed=False,
        typology=declared,
        typology_confidence=(
            overrides.get("declared_confidence") if declared is not None else None
        ),
        typology_source="declared" if declared is not None else None,
        provenance="lived",
        pinned=False,
        decay_class="episodic",
        decay_class_unknown=False,
        embedding=vec,
        entities=overrides.get("entities"),
        spans=[
            db.SpanPlan(s, e, None, "person") for (s, e) in overrides.get("spans", ())
        ],
        enrichment_pending=True,
        enrichment_pending_triggers=list(overrides.get("triggers", ())) or None,
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


async def execute(pool, sql: str, *params) -> None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)


async def mem_row(pool, memory_id):
    return await fetchrow(
        pool,
        "SELECT importance_raw, typology, typology_confidence, typology_source, "
        "scoring_failed, escalation_failed, enrichment_pending, "
        "enrichment_attempts, enrichment_pending_triggers "
        "FROM memories WHERE memory_id = %s",
        memory_id,
    )


async def chain(pool, memory_id):
    return await fetchall(
        pool,
        "SELECT write_cause, content, valid_at, invalid_at FROM memory_details "
        "WHERE memory_id = %s ORDER BY created_at",
        memory_id,
    )


async def runs(pool, memory_id):
    return await fetchall(
        pool,
        "SELECT attempt, outcome, escalation_failed, embedding_repaired, "
        "write_input_tokens, total_ms FROM memory_enrichment_runs "
        "WHERE memory_id = %s ORDER BY created_at, attempt",
        memory_id,
    )


async def probe_write_cause(pool, table: str, value: str) -> bool:
    """True when the CHECK admits `value` (probe insert, always rolled back)."""
    try:
        async with pool.connection() as conn:
            async with conn.transaction(force_rollback=True):
                async with conn.cursor() as cur:
                    # Probe rows land already-invalidated so the one-live-head
                    # partial unique index never fires — only the CHECK is
                    # under test, and it binds regardless of liveness.
                    if table == "memory_details":
                        await cur.execute(
                            "INSERT INTO memory_details (memory_id, content, "
                            "write_cause, valid_at, invalid_at) "
                            "SELECT memory_id, 'probe', %s, valid_at, valid_at "
                            "FROM memories LIMIT 1",
                            (value,),
                        )
                    else:
                        await cur.execute(
                            "INSERT INTO memory_fact_versions (memory_id, "
                            "basis_text, write_cause, valid_at, invalid_at) "
                            "SELECT memory_id, 'probe', %s, valid_at, valid_at "
                            "FROM memories LIMIT 1",
                            (value,),
                        )
    except psycopg.errors.CheckViolation:
        return False
    return True


async def run(uri: str) -> None:
    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    try:
        # ---------------- A. migration 006 shape --------------------------
        print("\n-- A. migration 006 shape")
        cols = {
            r[0]
            for r in await fetchall(
                pool,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'memories' AND column_name LIKE %s",
                "enrichment%",
            )
        }
        check(
            cols
            == {
                "enrichment_pending",
                "enrichment_attempts",
                "enrichment_pending_triggers",
            },
            "A1 memories carries the three 006 bookkeeping columns",
            str(sorted(cols)),
        )
        run_table = await fetchrow(
            pool,
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = 'memory_enrichment_runs'",
        )
        check(run_table[0] == 1, "A2 memory_enrichment_runs exists")
        # A seed row so the CHECK probes have a memories row to reference.
        probe_agent, _ = await make_agent(pool, "walker-probe", AGENT_CONFIG)
        await seed_pending(pool, probe_agent, "A probe observation for checks.")
        check(
            await probe_write_cause(pool, "memory_details", "enrichment"),
            "A3 memory_details_write_cause_check admits 'enrichment'",
        )
        check(
            await probe_write_cause(pool, "memory_fact_versions", "enrichment"),
            "A4 memory_fact_versions_write_cause_check admits 'enrichment'",
        )
        check(
            not await probe_write_cause(pool, "memory_details", "junk_cause"),
            "A5 the widened CHECK still rejects out-of-vocabulary causes",
        )
        idx = await fetchrow(
            pool,
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'memories_enrichment_pending_idx'",
        )
        check(
            idx is not None and "enrichment_pending" in idx[0],
            "A6 the partial pending index exists with its predicate",
        )
        outcome_ok = True
        try:
            async with pool.connection() as conn:
                async with conn.transaction(force_rollback=True):
                    async with conn.cursor() as cur:
                        await cur.execute(
                            "INSERT INTO memory_enrichment_runs (memory_id, "
                            "attempt, outcome) "
                            "SELECT memory_id, 1, 'bogus' FROM memories LIMIT 1"
                        )
        except psycopg.errors.CheckViolation:
            outcome_ok = False
        check(not outcome_ok, "A7 the run-log outcome CHECK rejects junk")

        # ---------------- B. observe shapes (real NLP pass) ---------------
        print("\n-- B. observe shapes: kill-switch parity + deferred mode")
        sync_agent, _ = await make_agent(pool, "walker-sync", AGENT_CONFIG)
        ingest = IngestService(pool, fake_providers(), settings)
        sync_result = await ingest.ingest_observation(
            ObserveEvent(
                agent_id=sync_agent,
                observation_text=T_OBS,
                phase_tag="walker",
                client_timestamp=NOW,
                provenance="lived",
            )
        )
        check(
            sync_result.enrichment_pending is False
            and sync_result.importance_raw is not None
            and sync_result.typology is not None,
            "B1 kill-switch default: the sync observe fills every scalar",
        )
        sync_row = await mem_row(pool, sync_result.memory_id)
        check(
            sync_row[6] is False and sync_row[7] == 0 and sync_row[8] is None,
            "B2 kill-switch default: no pending state, no persisted triggers",
        )

        def_agent, _ = await make_agent(pool, "walker-deferred", DEFERRED_CONFIG)
        def_result = await ingest.ingest_observation(
            ObserveEvent(
                agent_id=def_agent,
                observation_text=T_OBS,
                phase_tag="walker",
                client_timestamp=NOW,
                provenance="lived",
            )
        )
        check(
            def_result.enrichment_pending is True
            and def_result.importance_raw is None
            and def_result.typology is None
            and def_result.typology_source is None,
            "B3 deferred observe returns pending + NULL write-call scalars",
        )
        check(
            def_result.scoring_failed is False,
            "B4 pending is the signal — scoring_failed stays false",
        )
        inst = def_result.instrumentation
        check(
            inst.haiku_ms == 0.0
            and inst.haiku_input_tokens == 0
            and inst.haiku_output_tokens == 0
            and inst.escalated is False
            and inst.escalation_ms == 0.0,
            "B5 honest zero LLM instrumentation on the deferred observe",
        )
        d_row = await mem_row(pool, def_result.memory_id)
        check(
            d_row[0] is None and d_row[1] is None and d_row[6] is True,
            "B6 the pending row: NULL scalars + enrichment_pending",
        )
        d_chain = await chain(pool, def_result.memory_id)
        check(
            [(c[0], c[3] is None) for c in d_chain] == [("original", True)]
            and d_chain[0][1] == T_OBS,
            "B7 the raw observation text IS the live `original` head",
        )
        d_fact = await fetchrow(
            pool,
            "SELECT embedding IS NOT NULL FROM memory_fact_versions "
            "WHERE memory_id = %s AND invalid_at IS NULL",
            def_result.memory_id,
        )
        check(
            d_fact[0] is True,
            "B8 embedding stays inline (ruling 1): the fact head carries it",
        )
        check(
            len(def_result.gist_span_ids) >= 1,
            "B9 the NLP pass ran inline: gist spans exist at insert",
            f"{len(def_result.gist_span_ids)} spans",
        )
        check(
            d_row[8] is not None
            and "importance_threshold" not in d_row[8]
            and len(d_row[8]) >= 1,
            "B10 persisted triggers: non-importance members only",
            str(d_row[8]),
        )
        decl_result = await ingest.ingest_observation(
            ObserveEvent(
                agent_id=def_agent,
                observation_text="John dropped the ledger by the door.",
                phase_tag="walker",
                client_timestamp=NOW,
                provenance="lived",
                typology="told",
                typology_confidence=0.7,
            )
        )
        decl_row = await mem_row(pool, decl_result.memory_id)
        check(
            (decl_row[1], decl_row[2], decl_row[3]) == ("told", 0.7, "declared")
            and decl_row[0] is None,
            "B11 a declared typology stores at insert; importance still defers",
        )

        # ---------------- C. the completion ladder ------------------------
        print("\n-- C. the completion ladder (drain is the entry — no timers)")
        worker = worker_for(pool, settings)
        # Two rows are pending from section B (the deferred + declared
        # observes) plus A's probe row: drain them all first, then assert on
        # the deferred one.
        drained = await worker.drain()
        check(
            drained == 3,
            "C1 drain processes every pending row",
            f"{drained} rows",
        )
        c_row = await mem_row(pool, def_result.memory_id)
        check(
            c_row[0] is not None
            and c_row[1] is not None
            and c_row[3] == "inferred"
            and c_row[6] is False
            and c_row[7] == 1,
            "C2 one-shot completion: scalars filled, pending cleared, 1 attempt",
        )
        c_chain = await chain(pool, def_result.memory_id)
        check(
            [(c[0], c[3] is None) for c in c_chain]
            == [("original", False), ("enrichment", True)]
            and c_chain[1][1] == f"[fake render] {T_OBS}",
            "C3 the render supersedes the raw head as the 'enrichment' cause",
        )
        check(
            c_chain[0][3] == c_chain[1][2],
            "C4 supersede instant == new head valid_at (coherent timeline)",
        )
        decl_after = await mem_row(pool, decl_result.memory_id)
        check(
            (decl_after[1], decl_after[2], decl_after[3]) == ("told", 0.7, "declared")
            and decl_after[0] is not None,
            "C5 COALESCE: the declared typology survives completion untouched",
        )
        c_runs = await runs(pool, def_result.memory_id)
        check(
            [(r[0], r[1]) for r in c_runs] == [(1, "completed")]
            and c_runs[0][4] > 0
            and c_runs[0][5] is not None,
            "C6 the run row: completed, tokens accounted, total_ms present",
        )
        check(await worker.drain() == 0, "C7 re-drain is a no-op (row-state guard)")
        check(
            await chain(pool, def_result.memory_id) == c_chain,
            "C8 the chain is byte-stable across the re-drain",
        )

        # Escalation novelty: component + add-only span, fact chain untouched.
        nov_agent, _ = await make_agent(pool, "walker-novel", AGENT_CONFIG)
        nov_text = "Bram hid the ledger stone beneath the forge gate."
        nov = await seed_pending(
            pool,
            nov_agent,
            nov_text,
            triggers=("thin_gist",),
            spans=((0, 4),),
            entities=["Bram"],
        )
        nov_worker = worker_for(pool, settings, escalation=NoveltyEscalationProvider())
        check(await nov_worker.drain() == 1, "C9 novelty drain handles the row")
        comp = await fetchrow(
            pool,
            "SELECT component_id FROM identity_components "
            "WHERE agent_id = %s AND canonical = 'ledger stone'",
            nov_agent,
        )
        check(comp is not None, "C10 the escalation novel grew identity_components")
        nov_spans = await fetchall(
            pool,
            "SELECT start_char, end_char, matched_component_id "
            "FROM memory_gist_spans WHERE memory_id = %s ORDER BY start_char",
            nov.memory_id,
        )
        start = nov_text.index("ledger stone")
        check(
            [(s[0], s[1]) for s in nov_spans if s[2] == comp[0]]
            == [(start, start + len("ledger stone"))],
            "C11 the novel mention appended as an add-only span",
        )
        nov_facts = await fetchall(
            pool,
            "SELECT write_cause, invalid_at IS NULL, entities "
            "FROM memory_fact_versions WHERE memory_id = %s ORDER BY created_at",
            nov.memory_id,
        )
        check(
            [(f[0], f[1]) for f in nov_facts] == [("original", True)]
            and nov_facts[0][2] == ["Bram"],
            "C12 sync parity: no fact supersede, entities unchanged",
        )

        # Retry ladder.
        fl_agent, _ = await make_agent(pool, "walker-flaky", AGENT_CONFIG)
        fl = await seed_pending(pool, fl_agent, "The flaky forge observation.")
        fl_worker = worker_for(pool, settings, write=FlakyWriteProvider(1))
        await fl_worker.drain()
        fl_row = await mem_row(pool, fl.memory_id)
        check(
            fl_row[0] is None and fl_row[6] is True and fl_row[7] == 1,
            "C13 a failed attempt leaves the row pending (retry-later)",
        )
        await fl_worker.drain()
        fl_row = await mem_row(pool, fl.memory_id)
        check(
            fl_row[0] is not None and fl_row[6] is False and fl_row[7] == 2,
            "C14 the next drain completes it",
        )
        check(
            [(r[0], r[1]) for r in await runs(pool, fl.memory_id)]
            == [(1, "failed"), (2, "completed")],
            "C15 the run log carries both attempts honestly",
        )

        # Terminal degrade == the sync scoring-failed end-state.
        tm_agent, _ = await make_agent(pool, "walker-terminal", AGENT_CONFIG)
        tm = await seed_pending(pool, tm_agent, "The terminal forge observation.")
        tm_worker = worker_for(
            pool,
            settings,
            write=FailingWriteProvider(),
            defaults={"deferred_max_attempts": 1.0},
        )
        await tm_worker.drain()
        tm_row = await mem_row(pool, tm.memory_id)
        check(
            tm_row[0] == settings.defaults["importance_neutral"]
            and tm_row[4] is True
            and (tm_row[1], tm_row[3]) == ("observed", "inferred")
            and tm_row[5] is False
            and tm_row[6] is False,
            "C16 terminal fill == sync scoring-failed end-state",
        )
        check(
            [(c[0], c[3] is None) for c in await chain(pool, tm.memory_id)]
            == [("original", True)],
            "C17 terminal: the raw head stays live, nothing chain-written",
        )
        check(
            [r[1] for r in await runs(pool, tm.memory_id)] == ["terminal_degraded"],
            "C18 the terminal run row",
        )

        # Facts-only: a retelling won the head before enrichment arrived.
        ro_agent, _ = await make_agent(pool, "walker-raced", AGENT_CONFIG)
        ro = await seed_pending(pool, ro_agent, "The raced forge observation.")
        await db.write_back_reconstruction(
            pool,
            memory_id=ro.memory_id,
            prior_detail_id=ro.detail_id,
            content="A drifted retelling.",
            basis=NOW - timedelta(minutes=30),
            composed_key="vhash|b1",
        )
        cache_before = await fetchrow(
            pool,
            "SELECT count(*) FROM reconstruction_cache WHERE memory_id = %s",
            ro.memory_id,
        )
        check(cache_before[0] == 1, "C19 fixture: the retelling cached its text")
        await worker_for(pool, settings).drain()
        ro_row = await mem_row(pool, ro.memory_id)
        check(
            ro_row[0] is not None and ro_row[6] is False,
            "C20 facts-only completion still fills the scalars",
        )
        check(
            [(c[0], c[3] is None) for c in await chain(pool, ro.memory_id)]
            == [("original", False), ("reconstruction", True)],
            "C21 the prose supersede is SKIPPED — the retelling stays live",
        )
        cache_after = await fetchrow(
            pool,
            "SELECT count(*) FROM reconstruction_cache WHERE memory_id = %s",
            ro.memory_id,
        )
        check(
            cache_after[0] == 0,
            "C22 the eviction invariant binds on the facts-only path too",
        )
        check(
            [r[1] for r in await runs(pool, ro.memory_id)] == ["completed_facts_only"],
            "C23 the facts-only run row",
        )

        # Embedding repair.
        rp_agent, _ = await make_agent(pool, "walker-repair", AGENT_CONFIG)
        rp = await seed_pending(
            pool, rp_agent, "The embed-degraded observation.", embedding=None
        )
        await worker_for(pool, settings).drain()
        rp_facts = await fetchall(
            pool,
            "SELECT write_cause, invalid_at IS NULL, embedding IS NOT NULL, "
            "basis_text FROM memory_fact_versions WHERE memory_id = %s "
            "ORDER BY created_at",
            rp.memory_id,
        )
        check(
            [(f[0], f[1], f[2]) for f in rp_facts]
            == [("original", False, False), ("enrichment", True, True)],
            "C24 the repair supersedes the fact head; the original stays NULL",
        )
        check(
            rp_facts[0][3] == rp_facts[1][3],
            "C25 basis_text carries byte-verbatim across the supersede",
        )
        check(
            [(r[1], r[3]) for r in await runs(pool, rp.memory_id)]
            == [("completed", True)],
            "C26 the run row records the repair",
        )

        # Orphan sweep.
        or_agent, _ = await make_agent(pool, "walker-orphan", AGENT_CONFIG)
        orp = await seed_pending(pool, or_agent, "The orphaned observation.")
        await execute(
            pool,
            "UPDATE memories SET enrichment_attempts = %s WHERE memory_id = %s",
            int(settings.defaults["deferred_max_attempts"]),
            orp.memory_id,
        )
        await worker_for(pool, settings, write=FailingWriteProvider()).drain()
        or_row = await mem_row(pool, orp.memory_id)
        check(
            or_row[4] is True and or_row[6] is False,
            "C27 the sweep terminal-fills a budget-spent row, no model call",
        )

        # Anchor-set membership.
        sources = await db.fetch_reconstruction_sources(pool, [def_result.memory_id])
        check(
            sources[def_result.memory_id].anchor_cause == "enrichment",
            "C28 the enrichment head anchors the drift check (006 anchor set)",
        )

        # ---------------- D. lifecycle at both construction sites ---------
        print("\n-- D. worker lifecycle")
        lone = worker_for(pool, settings)
        lone.start()
        check(lone._task is not None, "D1 start() spawns the worker task")
        await lone.stop()
        check(lone._task is None, "D2 stop() cancels and clears it")
        runner = await SessionRunner.create(
            def_agent,
            settings=settings,
            providers=fake_providers(),
            pool=pool,
            phase_tag="walker",
        )
        check(
            runner.deferred is not None and runner.deferred._task is not None,
            "D3 SessionRunner.create wires AND starts a worker (REPL site)",
        )
        check(
            await runner.deferred.drain() == 0,
            "D4 the runner's worker drains deterministically (empty queue)",
        )
        await runner.close()
        check(
            runner.deferred._task is None,
            "D5 runner.close() stops the worker before the pool",
        )
    finally:
        await pool.close()

    print(f"\nverify_deferred_writes: {len(PASSED)}/{len(PASSED)} criteria passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
