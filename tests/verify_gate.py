"""verify_gate.py — structural done-when walker for the mid-dialogue gate
target v1 (docs\\mid-dialogue-gate.md).

Runs the gate done-when list against the SCRATCH database (default: the
.env DATABASE_URI with its path swapped to /longmem_test); the product DB is
never touched. The migrate criterion (`db\\migrate.py` no-arg -> "001 + 002
+ 003 applied, 0 pending" on `longmem`) runs outside this walker.

Structural-only (tests\\CLAUDE.md): assertions ride IDs, signals-fired
constants, rung names, counts, index existence, chain stamps, and
byte-identity of text ACROSS CALLS — never model prose. Gate distances are
deterministic because the fake embedding is a pure function of text (a
FIXTURE property — production uses real embeddings): echo text => cosine
distance ~0 (far under the 0.5 threshold); trigram-distinct text =>
distance ~1 (far over it).

The walker drives the retrieval seam directly with explicit
loaded_memory_ids (each section owns its loaded set — the caller-held
contract exercised literally), plus a SessionRunner section for the
runner's bookkeeping and the scene-boundary reset.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_gate.py [--database-uri <scratch-uri>]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.dialogue import (
    _MEMORY_RECOLLECTION_SUBHEADER,
    assemble_prose_prompt,
)
from app.gate import (
    GATE_RUNG_CLOSED,
    GATE_RUNG_ENTITY_ONLY,
    GATE_RUNG_NOVELTY_ONLY,
    GATE_SIGNAL_ENTITY,
    GATE_SIGNAL_NOVELTY,
)
from app.ingest import IngestService
from app.load_driver import run_driver
from app.providers import (
    FailingEmbeddingProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import (
    CorrectionRequest,
    DialogueInitRequest,
    GateInstrumentation,
    ObserveEvent,
    RetrievedMemory,
)
from app.session import SessionRunner

NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
SEED_PROSE = "The ford keeper, wary of strangers."

# Gate at PRODUCTION defaults; reconstruction pinned off (theta 0) so the
# serving stage never mutates chains under the signal sections —
# single-cause layer isolation (the read-path/cli-harness walker precedent).
AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "reconstruction_theta": 0.0,
}
# The blocking-beat agent: reconstruction ACTIVE at the default theta.
RECON_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
}
# The kill-switch/fixture-pin shape: gate disabled entirely.
OFF_CONFIG = {**AGENT_CONFIG, "gate_enabled": 0.0}

# Trigram-distinct texts: distances between DIFFERENT texts are ~1.0 under
# the locality-sensitive fake; echoes are ~0. Component terms ('Mara',
# 'the blacksmith', 'Aldous', 'the ferryman') appear only where a section
# wants a mention.
T_CHAPEL = (
    "Mara left the chapel before the harvest bells and the sexton counted "
    "the silver twice by candlelight."
)
T_BRIDGE = (
    "The miller raised his toll at the bridge and the carters grumbled "
    "about the price of crossing all week."
)
T_STORM = (
    "A late storm flattened the barley on the south slope and the gleaners "
    "worked until dusk to save what remained."
)
T_LANTERN = "Someone left a lantern burning in the hay barn overnight."
T_QUARRY = (
    "Flood water filled the eastern quarry pits and the winch ropes "
    "rotted where they hung."
)
T_FERRY = T_BRIDGE + " Aldous waited by the far bank."
# Measured fake-mode min-distance vs every other stored text: >= 0.73 —
# comfortably over the 0.5 threshold. (Ordinary prose lands ~0.45-0.65 under
# the trigram fake; pick trigram-rare wording for guaranteed-novel fixtures.)
T_OLD_DEBT = "Nine grey herons circled the weir at dawn, quarrelling over eels."

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

    return scratch_uri(load_env()["DATABASE_URI"], "longmem_test")


def fake_providers(embedding=None) -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=embedding or FakeEmbeddingProvider(),
        reconstruction=FakeReconstructionProvider(),
    )


async def make_agent(pool, name: str, config: dict, components: list[tuple]) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED_PROSE, "what threatens the chapel", Jsonb(config)),
        )
        agent_id = (await cur.fetchone())[0]
        for canonical, aliases in components:
            await cur.execute(
                "INSERT INTO identity_components (agent_id, canonical, aliases, "
                "category) VALUES (%s, %s, %s, 'person')",
                (agent_id, canonical, aliases),
            )
    return agent_id


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def seed(ingest: IngestService, agent_id, text: str, valid_at, **kw):
    return await ingest.ingest_observation(
        ObserveEvent(
            agent_id=agent_id,
            observation_text=text,
            phase_tag="scene.action",
            client_timestamp=valid_at,
            provenance="lived",
            **kw,
        )
    )


def request(agent_id, query_text, *, loaded=None, streak=0, k=None):
    return DialogueInitRequest(
        agent_id=agent_id,
        query_text=query_text,
        k=k,
        as_of=NOW,
        scene_started_at=NOW,
        loaded_memory_ids=loaded,
        gate_fruitless_streak=streak,
    )


def item_ids(result) -> list:
    return [item.memory_id for item in result.items]


async def main(database_uri: str) -> None:
    from app.config import Settings

    settings = Settings(database_uri=database_uri, provider_mode="fake")
    pool = db.build_pool(database_uri)
    await pool.open()
    ingest = IngestService(pool, fake_providers(), settings)
    retrieval = RetrievalService(pool, fake_providers(), settings)
    print(f"walker: scratch DB = {urlsplit(database_uri).path.lstrip('/')}")

    agent = await make_agent(
        pool,
        "gate-a",
        AGENT_CONFIG,
        [("Mara", ["the blacksmith"]), ("Aldous", ["the ferryman"])],
    )
    agent_off = await make_agent(
        pool, "gate-off", OFF_CONFIG, [("Mara", ["the blacksmith"])]
    )
    agent_bare = await make_agent(pool, "gate-bare", AGENT_CONFIG, [])
    agent_recon = await make_agent(
        pool, "gate-recon", RECON_CONFIG, [("Mara", ["the blacksmith"])]
    )

    # Seed the scene store (spaCy loads here — walker cost, not turn cost).
    m1 = await seed(
        ingest, agent, T_CHAPEL, NOW - timedelta(hours=3), entities=["Mara"]
    )
    m2 = await seed(ingest, agent, T_BRIDGE, NOW - timedelta(hours=2))
    m3 = await seed(ingest, agent, T_STORM, NOW - timedelta(hours=1))

    # ------------------------------------------------------------------ #
    print("\n[1] loader parity — absent fields / gate disabled => v1")
    # ------------------------------------------------------------------ #
    loader = await retrieval.retrieve_dialogue_init(request(agent, T_BRIDGE))
    check(
        loader.instrumentation.gate == GateInstrumentation(),
        "no loaded fields => gate not evaluated, all-default instrumentation",
    )
    check(
        not any(item.gate_fetched for item in loader.items),
        "loader turn marks nothing gate_fetched",
    )
    loaded_ids = item_ids(loader)
    check(
        set(loaded_ids) == {m1.memory_id, m2.memory_id, m3.memory_id},
        "loader turn serves the seeded store (the scene's loaded set)",
    )

    off_loader = await retrieval.retrieve_dialogue_init(request(agent_off, T_BRIDGE))
    off_gated = await retrieval.retrieve_dialogue_init(
        request(agent_off, T_QUARRY, loaded=item_ids(off_loader))
    )
    check(
        not off_gated.instrumentation.gate.evaluated,
        "gate_enabled 0.0 + loaded IDs => loader path (the kill-switch pin shape)",
    )

    # ------------------------------------------------------------------ #
    print("\n[2] closed gate — covered, near-loaded utterance")
    # ------------------------------------------------------------------ #
    closed = await retrieval.retrieve_dialogue_init(
        request(agent, T_CHAPEL, loaded=loaded_ids)
    )
    g = closed.instrumentation.gate
    check(
        g.evaluated and not g.fired and g.signals_fired == [],
        "echo of a loaded memory (mention covered) => gate closed, no signals",
    )
    check(
        set(item_ids(closed)) == set(loaded_ids),
        "closed gate serves exactly the loaded IDs",
    )
    check(
        closed.instrumentation.sql_ms == 0.0,
        "closed gate ran zero probe SQL",
    )
    check(
        all(item.relevance is not None for item in closed.items),
        "closed-gate relevance recomputed free from the novelty distances",
    )
    closed_again = await retrieval.retrieve_dialogue_init(
        request(agent, T_CHAPEL, loaded=loaded_ids)
    )
    check(
        item_ids(closed_again) == item_ids(closed)
        and [i.content for i in closed_again.items]
        == [i.content for i in closed.items],
        "closed gate is deterministic (IDs + text byte-identical across calls)",
    )

    # NULL-fact-embedding loaded row: rides coverage + serving, out of the
    # novelty basis, relevance honestly null.
    failing_ingest = IngestService(
        pool, fake_providers(embedding=FailingEmbeddingProvider()), settings
    )
    m4 = await seed(failing_ingest, agent, T_LANTERN, NOW - timedelta(minutes=30))
    with_null = await retrieval.retrieve_dialogue_init(
        request(agent, T_CHAPEL, loaded=loaded_ids + [m4.memory_id])
    )
    null_items = [i for i in with_null.items if i.memory_id == m4.memory_id]
    check(
        with_null.instrumentation.gate.null_embedding_loaded_count == 1
        and null_items
        and null_items[0].relevance is None,
        "NULL-embedding loaded row: excluded from the novelty basis (counted), "
        "served with relevance null",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] novelty fire — far utterance fetches and appends")
    # ------------------------------------------------------------------ #
    m5 = await seed(ingest, agent, T_QUARRY, NOW - timedelta(minutes=20))
    novel = await retrieval.retrieve_dialogue_init(
        request(agent, T_QUARRY, loaded=loaded_ids)
    )
    g = novel.instrumentation.gate
    check(
        g.fired and g.signals_fired == [GATE_SIGNAL_NOVELTY],
        "trigram-distinct utterance => novelty fires alone",
        f"min_dist={g.novelty_min_distance}",
    )
    check(
        g.fetched_memory_ids
        and m5.memory_id in g.fetched_memory_ids
        and not set(g.fetched_memory_ids) & set(loaded_ids),
        "the fetch returns only NEW ids (loaded set excluded in SQL)",
    )
    check(
        all(
            item.gate_fetched == (item.memory_id in set(g.fetched_memory_ids))
            for item in novel.items
        ),
        "exactly this turn's appends are marked gate_fetched",
    )
    check(
        set(item_ids(novel)) == set(loaded_ids) | set(g.fetched_memory_ids),
        "served set == loaded set + this turn's appends (append-only)",
    )

    # ------------------------------------------------------------------ #
    print("\n[4] entity tripwire — uncovered mention fires; covered does not")
    # ------------------------------------------------------------------ #
    m6 = await seed(
        ingest, agent, T_FERRY, NOW - timedelta(minutes=10), entities=["Aldous"]
    )
    trip = await retrieval.retrieve_dialogue_init(
        request(agent, T_FERRY, loaded=loaded_ids)
    )
    g = trip.instrumentation.gate
    check(
        g.fired and g.signals_fired == [GATE_SIGNAL_ENTITY],
        "uncovered component mention in a near-loaded utterance => tripwire "
        "fires alone (novelty quiet)",
        f"min_dist={g.novelty_min_distance}",
    )
    check(
        g.uncovered_entities == ["Aldous"],
        "which-entity is logged (canonical)",
    )
    check(
        m6.memory_id in g.fetched_memory_ids and g.entity_covered is True,
        "the fetch contains the tripwire entity (entity efficacy true)",
    )
    covered = await retrieval.retrieve_dialogue_init(
        request(agent, T_FERRY, loaded=loaded_ids + [m6.memory_id])
    )
    check(
        not covered.instrumentation.gate.fired
        and covered.instrumentation.gate.signals_fired == [],
        "the same mention, now covered by a loaded item's entities => no fire",
    )

    # ------------------------------------------------------------------ #
    print("\n[5] both signals")
    # ------------------------------------------------------------------ #
    both = await retrieval.retrieve_dialogue_init(
        request(agent, T_QUARRY + " Aldous waited.", loaded=loaded_ids)
    )
    g = both.instrumentation.gate
    check(
        g.signals_fired == [GATE_SIGNAL_NOVELTY, GATE_SIGNAL_ENTITY],
        "far utterance + uncovered mention => both signals logged",
    )
    check(
        g.fired and len(g.signals_fired) > 0,
        "every fire event carries non-empty signals_fired",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] damper — fruitless fetches suppress novelty, not the tripwire")
    # ------------------------------------------------------------------ #
    all_ids = [
        m1.memory_id,
        m2.memory_id,
        m3.memory_id,
        m4.memory_id,
        m5.memory_id,
        m6.memory_id,
    ]
    fruitless = await retrieval.retrieve_dialogue_init(
        request(agent, T_OLD_DEBT, loaded=all_ids)
    )
    g = fruitless.instrumentation.gate
    check(
        g.fired and g.fetched_new_count == 0 and g.fruitless,
        "a fire that appends nothing new is fruitless (the damper's input)",
    )
    damped = await retrieval.retrieve_dialogue_init(
        request(agent, T_OLD_DEBT, loaded=all_ids, streak=2)
    )
    g = damped.instrumentation.gate
    check(
        g.damper_active and not g.fired and g.signals_fired == [],
        "streak >= gate_damper_fruitless_max => novelty suppressed, gate closed",
    )
    damped_trip = await retrieval.retrieve_dialogue_init(
        request(agent, T_FERRY, loaded=loaded_ids, streak=2)
    )
    g = damped_trip.instrumentation.gate
    check(
        g.damper_active and g.signals_fired == [GATE_SIGNAL_ENTITY],
        "the tripwire stays live under the damper (near-ground-truth)",
    )

    # ------------------------------------------------------------------ #
    print("\n[7] degradation ladder — every rung, fail-quiet")
    # ------------------------------------------------------------------ #
    failing_retrieval = RetrievalService(
        pool, fake_providers(embedding=FailingEmbeddingProvider()), settings
    )
    entity_only = await failing_retrieval.retrieve_dialogue_init(
        request(agent, T_FERRY, loaded=loaded_ids)
    )
    g = entity_only.instrumentation.gate
    fetched_items = [i for i in entity_only.items if i.gate_fetched]
    check(
        g.degraded_rung == GATE_RUNG_ENTITY_ONLY
        and g.signals_fired == [GATE_SIGNAL_ENTITY]
        and entity_only.instrumentation.degraded,
        "embeddings down => entity-only rung: the lexical tripwire still gates",
    )
    check(
        any(i.memory_id == m6.memory_id for i in fetched_items)
        and all(i.relevance is None for i in fetched_items),
        "entity-only fetch reads the fact-head GIN, ranked recency x "
        "importance, relevance null",
    )
    check(
        g.novelty_min_distance is None,
        "no novelty basis was computed on the entity-only rung",
    )

    bare_loader = await retrieval.retrieve_dialogue_init(request(agent_bare, T_BRIDGE))
    # (bare agent: nothing seeded — empty loaded set is the trivially-novel
    # edge AND the no-coverage-basis rung at once)
    bare_gated = await retrieval.retrieve_dialogue_init(
        request(agent_bare, T_QUARRY, loaded=item_ids(bare_loader))
    )
    g = bare_gated.instrumentation.gate
    check(
        g.degraded_rung == GATE_RUNG_NOVELTY_ONLY
        and g.signals_fired == [GATE_SIGNAL_NOVELTY],
        "no components / no coverage basis => novelty-only rung; empty loaded "
        "set is trivially novel",
    )
    no_basis = await retrieval.retrieve_dialogue_init(
        request(agent, T_FERRY, loaded=[m4.memory_id])
    )
    check(
        no_basis.instrumentation.gate.degraded_rung == GATE_RUNG_NOVELTY_ONLY,
        "components exist but no loaded entities => novelty-only (the tripwire "
        "never fires for want of a basis)",
    )
    both_out = await failing_retrieval.retrieve_dialogue_init(
        request(agent_bare, T_QUARRY, loaded=item_ids(bare_loader))
    )
    g = both_out.instrumentation.gate
    check(
        g.degraded_rung == GATE_RUNG_CLOSED
        and not g.fired
        and both_out.instrumentation.degraded,
        "both signals out => gate closed, loaded set served, fail-quiet",
    )
    foreign = await retrieval.retrieve_dialogue_init(
        request(agent, T_CHAPEL, loaded=loaded_ids + [uuid4()])
    )
    check(
        foreign.instrumentation.gate.loaded_missing_count == 1
        and set(item_ids(foreign)) == set(loaded_ids),
        "unknown/foreign loaded IDs drop out of the join, counted, turn intact",
    )

    # ------------------------------------------------------------------ #
    print("\n[8] mid-scene reconstruction beat — block + callback + stability")
    # ------------------------------------------------------------------ #
    m8 = await seed(ingest, agent_recon, T_OLD_DEBT, NOW - timedelta(days=40))
    m9 = await seed(ingest, agent_recon, T_STORM, NOW - timedelta(hours=1))
    recon_loader = await retrieval.retrieve_dialogue_init(
        request(agent_recon, T_STORM, k=1)
    )
    check(
        item_ids(recon_loader) == [m9.memory_id],
        "blocking-beat setup: the loader holds only the fresh memory "
        "(the old one stays cold)",
    )
    calls: list[int] = []
    blocked = await retrieval.retrieve_dialogue_init(
        request(agent_recon, T_OLD_DEBT, loaded=[m9.memory_id]),
        on_reconstruct=lambda: calls.append(1),
    )
    g = blocked.instrumentation.gate
    m8_items = [i for i in blocked.items if i.memory_id == m8.memory_id]
    check(
        len(calls) == 1
        and g.reconstructing_blocked
        and blocked.instrumentation.cache_misses >= 1,
        "a gate fetch hitting a cold past-theta memory blocks and fires the "
        "pre-serve callback (fork 5) exactly once",
    )
    check(
        m8_items
        and m8_items[0].read_mode == "reconstructed"
        and blocked.instrumentation.write_backs >= 1,
        "the blocked serve persisted a retelling (write-back) and says so",
    )
    stable = await retrieval.retrieve_dialogue_init(
        request(agent_recon, T_OLD_DEBT, loaded=[m9.memory_id, m8.memory_id]),
        on_reconstruct=lambda: calls.append(1),
    )
    m8_again = [i for i in stable.items if i.memory_id == m8.memory_id]
    check(
        len(calls) == 1
        and not stable.instrumentation.gate.reconstructing_blocked
        and m8_again
        and m8_again[0].content == m8_items[0].content,
        "same-scene re-read: cache hit, no second block, no callback, "
        "byte-identical text",
    )

    # ------------------------------------------------------------------ #
    print("\n[9] migration 003 + the entities freeze")
    # ------------------------------------------------------------------ #
    ledger = await fetchall(
        pool, "SELECT version FROM schema_migrations ORDER BY version"
    )
    check(
        [row[0] for row in ledger]
        == [
            "001_foundation.sql",
            "002_fact_versions.sql",
            "003_fact_entities.sql",
            # 004 joined the ledger at the hybrid-lexical build (Target B,
            # 2026-07-20) — the mechanical ledger-pin update every migration
            # makes to prior walkers (the 002/003 precedent). The gate
            # mechanics this walker verifies are untouched by 004.
            "004_lexical_index.sql",
            # 005 joined the ledger at the escalation soft-degrade build
            # (2026-07-22) — the same mechanical ledger-pin update. The gate
            # mechanics this walker verifies are untouched by 005.
            "005_escalation_failed.sql",
            # 006 joined the ledger at the deferred-write build (Phase C1,
            # 2026-08-12) — the same mechanical ledger-pin update. The gate
            # mechanics this walker verifies are untouched by 006.
            "006_deferred_writes.sql",
            # 007 joined the ledger at the reflection build (Phase C2,
            # 2026-08-15) — the same mechanical ledger-pin update. The gate
            # mechanics this walker verifies are untouched by 007.
            "007_reflection.sql",
            # 008 joined the ledger at the parameter-compiler build (Phase
            # C3, 2026-08-17) — the same mechanical ledger-pin update. The
            # gate mechanics this walker verifies are untouched by 008.
            "008_parameter_compiler.sql",
        ],
        "the ledger records 001 + 002 + 003 + 004 + 005 + 006 + 007 + 008",
    )
    indexes = {
        row[0]
        for row in await fetchall(
            pool,
            "SELECT indexname FROM pg_indexes WHERE tablename IN "
            "('memories', 'memory_fact_versions')",
        )
    }
    check(
        "memory_fact_versions_entities_gin" in indexes
        and "memories_entities_gin" not in indexes,
        "the partial GIN lives on the fact table; the old memories GIN is dropped",
    )

    # Legacy-shaped row (pre-003: memories.entities set, fact head entities
    # NULL) + re-running the 003 file => the guarded backfill repairs it;
    # a second run is a no-op (idempotent UPDATE guard).
    legacy_memory = await fetchrow(
        pool,
        "INSERT INTO memories (agent_id, observation_text, valid_at, entities) "
        "VALUES (%s, 'legacy row for the 003 guard', %s, %s) RETURNING memory_id",
        agent,
        NOW - timedelta(days=2),
        ["Legacy Name"],
    )
    legacy_id = legacy_memory[0]
    await fetchall(
        pool,
        "INSERT INTO memory_fact_versions (memory_id, basis_text, write_cause, "
        "valid_at) VALUES (%s, 'legacy row for the 003 guard', 'original', %s) "
        "RETURNING fact_version_id",
        legacy_id,
        NOW - timedelta(days=2),
    )
    sql_003 = (REPO_ROOT / "db" / "migrations" / "003_fact_entities.sql").read_text()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql_003)
    backfilled = await fetchrow(
        pool,
        "SELECT entities FROM memory_fact_versions WHERE memory_id = %s",
        legacy_id,
    )
    check(
        backfilled[0] == ["Legacy Name"],
        "003 re-run backfills a legacy-shaped fact row from memories.entities",
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql_003)
    backfilled_again = await fetchrow(
        pool,
        "SELECT entities FROM memory_fact_versions WHERE memory_id = %s",
        legacy_id,
    )
    check(
        backfilled_again[0] == ["Legacy Name"],
        "a second 003 run is a no-op (the entities IS NULL guard held)",
    )

    # Freeze at observe: entities lives on the fact head only.
    frozen = await fetchrow(
        pool,
        "SELECT m.entities, fv.entities FROM memories m "
        "JOIN memory_fact_versions fv ON fv.memory_id = m.memory_id "
        "AND fv.invalid_at IS NULL WHERE m.memory_id = %s",
        m1.memory_id,
    )
    check(
        frozen[0] is None and frozen[1] == m1.entities and "Mara" in frozen[1],
        "observe writes entities to the fact head ONLY; memories.entities "
        "stays NULL post-003 (the freeze, the 002 embedding precedent)",
    )

    # Correction moves entities: NER over the corrected text + the optional
    # operator field, merged (observe's dedup), onto the corrected fact head;
    # the superseded fact row keeps its own (non-destructive).
    correction = await ingest.correct(
        m1.memory_id,
        CorrectionRequest(
            content="The silver was counted once, in the vestry, by Mara herself.",
            client_timestamp=NOW + timedelta(hours=1),
            entities=["the vestry"],
        ),
    )
    chain = await fetchall(
        pool,
        "SELECT write_cause, entities, valid_at, invalid_at FROM "
        "memory_fact_versions WHERE memory_id = %s ORDER BY created_at",
        m1.memory_id,
    )
    check(
        chain[1][0] == "authorial_correction"
        and chain[1][1] == correction.entities
        and "the vestry" in correction.entities
        and correction.nlp_ms >= 0.0,
        "the corrected fact head carries the merged NER + operator entities "
        "(CorrectionResult echoes them + the mechanical pass's timing)",
    )
    check(
        chain[0][1] == m1.entities and chain[0][3] == chain[1][2],
        "the superseded fact row keeps ITS entities; the chain timeline is "
        "coherent (invalid_at == corrected valid_at)",
    )
    t_before = NOW + timedelta(minutes=30)
    live_before = await fetchall(
        pool,
        "SELECT write_cause FROM memory_fact_versions WHERE memory_id = %s "
        "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
        m1.memory_id,
        t_before,
        t_before,
    )
    check(
        [row[0] for row in live_before] == ["original"],
        "windowed SQL re-derives which entities-bearing fact was live at any "
        "instant (stored bi-temporal coherence, second chain)",
    )

    # ------------------------------------------------------------------ #
    print("\n[10] efficacy + runner bookkeeping + scene reset")
    # ------------------------------------------------------------------ #
    outscored = await retrieval.retrieve_dialogue_init(
        request(agent, T_QUARRY, loaded=[m2.memory_id])
    )
    g = outscored.instrumentation.gate
    check(
        g.novelty_outscored is True,
        "novelty efficacy: the fetched echo out-scores the far loaded row",
    )

    runner = await SessionRunner.create(
        agent, settings=settings, providers=fake_providers(), pool=pool
    )
    runner.as_of = NOW
    turn1 = await runner.utterance(T_BRIDGE)
    check(
        runner.loaded_memory_ids == item_ids(turn1)
        and not turn1.instrumentation.retrieval.gate.evaluated,
        "runner: the loader turn's served IDs become the scene's loaded set",
    )
    turn2 = await runner.utterance(T_OLD_DEBT + " Nobody forgave it.")
    g2 = turn2.instrumentation.retrieval.gate
    check(
        g2.evaluated
        and runner.loaded_memory_ids == item_ids(turn1) + list(g2.fetched_memory_ids),
        "runner: gate fetches append to the loaded set in order (append-only)",
    )
    runner.gate_fruitless_streak = 2
    await runner.scene()
    check(
        runner.loaded_memory_ids is None and runner.gate_fruitless_streak == 0,
        "scene boundary resets the loaded set and the damper (caller-side only)",
    )
    await runner.close()

    # ------------------------------------------------------------------ #
    print("\n[11] prompt partition — append-only order + recollection block")

    # ------------------------------------------------------------------ #
    def fake_item(memory_id, content, fetched=False) -> RetrievedMemory:
        return RetrievedMemory(
            memory_id=memory_id,
            detail_id=uuid4(),
            content=content,
            read_mode="verbatim",
            pinned=False,
            score=0.5,
            relevance=0.5,
            recency=1.0,
            importance_norm=0.5,
            importance_raw=0.5,
            gate_fetched=fetched,
        )

    id_a, id_b, id_c = uuid4(), uuid4(), uuid4()
    items = [
        fake_item(id_b, "second loaded"),
        fake_item(id_c, "the recollection", fetched=True),
        fake_item(id_a, "first loaded"),
    ]
    prompt = assemble_prose_prompt(SEED_PROSE, items, loaded_order=[id_a, id_b])
    lines = prompt.splitlines()
    # Locate memory lines by their CONTENT, not their UUID: the id rode the
    # rendered line only until the F0 audit (2026-08-26) established nothing
    # consumes it there and the strip landed — content is the stable locator.
    pos_a = next(i for i, ln in enumerate(lines) if "first loaded" in ln)
    pos_b = next(i for i, ln in enumerate(lines) if "second loaded" in ln)
    pos_sub = next(
        i for i, ln in enumerate(lines) if ln == _MEMORY_RECOLLECTION_SUBHEADER
    )
    pos_c = next(i for i, ln in enumerate(lines) if "the recollection" in ln)
    check(
        pos_a < pos_b < pos_sub < pos_c,
        "gated prompt: loaded items in the caller's append-only order, then "
        "the recollection sub-header, then this turn's fetches",
    )
    no_fetch_prompt = assemble_prose_prompt(
        SEED_PROSE,
        [fake_item(id_a, "first loaded"), fake_item(id_b, "second loaded")],
        loaded_order=[id_a, id_b],
    )
    check(
        _MEMORY_RECOLLECTION_SUBHEADER not in no_fetch_prompt,
        "the sub-header appears only when a gate fetch happened this turn",
    )
    v1_prompt = assemble_prose_prompt(SEED_PROSE, [fake_item(id_a, "first loaded")])
    v1_prompt_again = assemble_prose_prompt(
        SEED_PROSE, [fake_item(id_a, "first loaded")]
    )
    check(
        v1_prompt == v1_prompt_again
        and _MEMORY_RECOLLECTION_SUBHEADER not in v1_prompt,
        "loader rendering (loaded_order=None) is byte-stable and v1-shaped",
    )

    # ------------------------------------------------------------------ #
    print("\n[12] load-driver aggregates — the §11 closure")
    # ------------------------------------------------------------------ #
    # run_driver builds its own pool + providers from the injected scratch
    # Settings (fake mode) and creates its own driver agent — the gate runs
    # PRODUCTION-active there (no fixture pin on the driver's config).
    report = await run_driver(settings, sessions=1, turns=8, seed=7)
    check(
        "gate_check" in report["latency_ms"] and "gate" in report,
        "the driver emits the gate-check latency series + the gate block "
        "(the reserved §11 term lands)",
    )
    check(
        report["gate"]["evaluated_turns"] > 0
        and report["gate"]["fires_per_100_turns"] > 0,
        "driver turns 2+ are gated at production defaults and the gate fires",
    )

    await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(main(uri), loop_factory=asyncio.SelectorEventLoop)
