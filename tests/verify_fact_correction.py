"""verify_fact_correction.py — structural done-when walker for the
fact-level correction target v1 (docs\\fact-level-correction.md).

Runs the fact-correction done-when list against the SCRATCH database
(default: the .env DATABASE_URI with its path swapped to /twicetold_test); the
product DB is never touched. The migrate criterion (`db\\migrate.py` no-arg
-> "001 + 002 applied, 0 pending" on `twicetold`) runs outside this walker.

Structural-only (tests\\CLAUDE.md): assertions ride IDs, write_cause, chain
stamps, index existence, distances-as-structure, and byte-identity of
OPERATOR/CLIENT text (which this walker authors) — never model prose. The
"retrieval follows the fix" claim is assertable deterministically because
the fake embedding is a pure function of text (a FIXTURE property —
production uses real embeddings): probe text == stored basis  =>  cosine
distance exactly 0 (float noise ~1e-16). The ranking claim anchors at the
db layer, where order is pure distance; the service layer asserts presence
+ relevance ~ 1.0 (a service-level rank assertion would hang on
hash-derived fake importance).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_fact_correction.py [--database-uri <scratch-uri>]
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
from app.ingest import (
    CorrectionEmbedFailedError,
    IngestService,
)
from app.providers import (
    FailingEmbeddingProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import CorrectionRequest, DialogueInitRequest, ObserveEvent

NOW = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)
SEED_PROSE = "The ford keeper, wary of strangers."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
}

# Fresh episodic rows serve verbatim (far above theta), so the serving stage
# never mutates chains under this walker — single-cause layer isolation.
# Texts are trigram-distinct so fake-mode distances are meaningfully large
# between different texts and exactly 0 for identical text.
T_EVENT = (
    "Marta stole the silver chalice from the chapel during the harvest "
    "festival. The sexton swore he saw her leave by the north door."
)
CORRECTED = (
    "The chalice was misplaced in the crypt by the sexton himself; Marta "
    "was never in the chapel that night."
)
T_DECOY = (
    "The miller raised his toll at the bridge and the carters grumbled "
    "about the price of crossing all week."
)
T_EVICT = "A gray dog followed the pedlar through the market square."
CORRECTED_EVICT = "The gray dog belonged to the pedlar all along."
T_REPAIR = "Someone left a lantern burning in the hay barn overnight."
CORRECTED_REPAIR = "The lantern in the hay barn was the watchman's, doused at dawn."

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


def fake_providers(embedding=None) -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=embedding or FakeEmbeddingProvider(),
        reconstruction=FakeReconstructionProvider(),
    )


async def make_agent(pool, name: str):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED_PROSE, "what threatens the chapel", Jsonb(AGENT_CONFIG)),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, 'Marta', %s, 'person')",
            (agent_id, ["the weaver"]),
        )
    return agent_id


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def seed_memory(ingest: IngestService, agent_id, text: str, valid_at, **kw):
    result = await ingest.ingest_observation(
        ObserveEvent(
            agent_id=agent_id,
            observation_text=text,
            phase_tag="scene.action",
            client_timestamp=valid_at,
            provenance="lived",
            **kw,
        )
    )
    return result


async def fact_chain(pool, memory_id):
    """(write_cause, basis_text, valid_at, invalid_at, fact_version_id,
    embedding_is_null, embedding_text), oldest first."""
    return await fetchall(
        pool,
        "SELECT write_cause, basis_text, valid_at, invalid_at, "
        "fact_version_id, embedding IS NULL, embedding::text "
        "FROM memory_fact_versions WHERE memory_id = %s ORDER BY created_at",
        memory_id,
    )


async def detail_chain(pool, memory_id):
    return await fetchall(
        pool,
        "SELECT write_cause, content, valid_at, invalid_at, detail_id "
        "FROM memory_details WHERE memory_id = %s ORDER BY created_at",
        memory_id,
    )


def request(agent_id, query_text, as_of) -> DialogueInitRequest:
    return DialogueInitRequest(
        agent_id=agent_id, query_text=query_text, as_of=as_of, scene_started_at=as_of
    )


async def main(database_uri: str) -> None:
    from app.config import Settings

    settings = Settings(database_uri=database_uri, provider_mode="fake")
    pool = db.build_pool(database_uri)
    await pool.open()
    ingest = IngestService(pool, fake_providers(), settings)
    retrieval = RetrievalService(pool, fake_providers(), settings)
    embedder = FakeEmbeddingProvider()
    print(f"walker: scratch DB = {urlsplit(database_uri).path.lstrip('/')}")

    # ------------------------------------------------------------------ #
    print("\n[1] Migration 002 structure: indexes moved, one-live-head guard")
    agent = await make_agent(pool, "fact-walker-npc")
    index_rows = await fetchall(
        pool,
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE tablename IN ('memories', 'memory_fact_versions')",
    )
    names = {row[0] for row in index_rows}
    defs = {row[0]: row[1] for row in index_rows}
    check(
        "memory_fact_versions_one_live_head" in names
        and "WHERE" in defs.get("memory_fact_versions_one_live_head", ""),
        "one-live-fact-head partial unique index exists",
    )
    check(
        "memory_fact_versions_embedding_hnsw" in names
        and "hnsw" in defs.get("memory_fact_versions_embedding_hnsw", "")
        and "WHERE" in defs.get("memory_fact_versions_embedding_hnsw", ""),
        "fact-table HNSW is partial (live heads only)",
    )
    check(
        "memories_embedding_hnsw" not in names,
        "old memories_embedding_hnsw dropped (ruled 2026-07-18)",
    )
    dup = uuid4()
    inserted_first_head = False
    try:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO memories (memory_id, agent_id, observation_text, "
                "valid_at) VALUES (%s, %s, 'dup-guard', %s)",
                (dup, agent, NOW),
            )
            await cur.execute(
                "INSERT INTO memory_fact_versions (memory_id, basis_text, "
                "write_cause, valid_at) VALUES (%s, 'a', 'original', %s)",
                (dup, NOW),
            )
            inserted_first_head = True
            await cur.execute(
                "INSERT INTO memory_fact_versions (memory_id, basis_text, "
                "write_cause, valid_at) VALUES (%s, 'b', 'original', %s)",
                (dup, NOW),
            )
        fail("one-live-fact-head", "second live fact head was accepted")
    except SystemExit:
        raise
    except Exception:
        check(
            inserted_first_head,
            "a second live fact head is rejected by the partial unique index "
            "(the first head inserted cleanly, so the rejection is the index)",
        )

    # ------------------------------------------------------------------ #
    print("\n[2] Backfill: a pre-002-shaped row gains its `original` fact head")
    legacy_id = uuid4()
    legacy_text = "The old bell cracked in the winter of the great frost."
    legacy_vec = embedder.embed([legacy_text]).vectors[0]
    async with pool.connection() as conn, conn.cursor() as cur:
        # A legacy row exactly as migration 001 left it: embedding on the
        # memories row, no fact row (the column still exists post-002).
        await cur.execute(
            "INSERT INTO memories (memory_id, agent_id, observation_text, "
            "embedding, valid_at) VALUES (%s, %s, %s, %s, %s)",
            (legacy_id, agent, legacy_text, db._vector(legacy_vec), NOW),
        )
        await cur.execute(
            "INSERT INTO memory_details (memory_id, content, write_cause, "
            "valid_at) VALUES (%s, %s, 'original', %s)",
            (legacy_id, legacy_text, NOW),
        )
    sql_002 = (REPO_ROOT / "db" / "migrations" / "002_fact_versions.sql").read_text(
        encoding="utf-8"
    )
    pre_facts = await fetchrow(pool, "SELECT count(*) FROM memory_fact_versions")
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql_002)  # re-run: IF NOT EXISTS + guarded backfill
    backfilled = await fact_chain(pool, legacy_id)
    check(
        len(backfilled) == 1
        and backfilled[0][0] == "original"
        and backfilled[0][1] == legacy_text
        and backfilled[0][3] is None
        and backfilled[0][2] == NOW,
        "backfill minted one live `original` fact head: basis = "
        "observation_text byte-verbatim, valid_at carried",
    )
    mem_vec_text = await fetchrow(
        pool, "SELECT embedding::text FROM memories WHERE memory_id = %s", legacy_id
    )
    check(
        backfilled[0][6] == mem_vec_text[0],
        "backfill carried the stored embedding value-identically",
    )
    post_facts = await fetchrow(pool, "SELECT count(*) FROM memory_fact_versions")
    check(
        post_facts[0] == pre_facts[0] + 1,
        "backfill guard: re-running 002 minted ONLY the missing head",
    )
    counts = await fetchrow(
        pool,
        "SELECT (SELECT count(*) FROM memories), "
        "(SELECT count(*) FROM memory_fact_versions WHERE invalid_at IS NULL)",
    )
    check(
        counts[0] == counts[1],
        "every memory has exactly one live fact head",
        f"{counts[0]} memories",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] Observe mints the fact head; memories.embedding frozen")
    seeded = await seed_memory(ingest, agent, T_EVENT, NOW - timedelta(hours=2))
    m_event = seeded.memory_id
    facts_e = await fact_chain(pool, m_event)
    check(
        len(facts_e) == 1
        and facts_e[0][0] == "original"
        and facts_e[0][1] == T_EVENT
        and facts_e[0][3] is None
        and facts_e[0][5] is False,
        "observe minted one live `original` fact head: basis byte-verbatim, "
        "embedding present",
    )
    check(
        seeded.fact_version_id == facts_e[0][4],
        "IngestResult.fact_version_id names the fact head (IDs in payloads)",
    )
    frozen = await fetchrow(
        pool, "SELECT embedding IS NULL FROM memories WHERE memory_id = %s", m_event
    )
    check(
        frozen[0] is True,
        "memories.embedding not written at observe (freeze ruling 2026-07-18)",
    )

    # ------------------------------------------------------------------ #
    print("\n[4] Retrieval follows the fix (db-layer distance, service relevance)")
    await seed_memory(ingest, agent, T_DECOY, NOW - timedelta(hours=2))
    probe_vec = embedder.embed([CORRECTED]).vectors[0]
    before = await db.fetch_vector_candidates(pool, agent, probe_vec, 10)
    before_by_id = {row.memory_id: row for row in before}
    check(
        m_event in before_by_id and before_by_id[m_event].distance > 1e-3,
        "pre-correction: the memory's distance to the corrected-text probe "
        "is bounded away from 0",
        f"distance={before_by_id[m_event].distance:.4f}",
    )
    t_c = NOW - timedelta(hours=1)
    original_fact_vec_text = facts_e[0][6]
    pre_fact_entities = (
        await fetchrow(
            pool,
            "SELECT entities FROM memory_fact_versions WHERE fact_version_id = %s",
            facts_e[0][4],
        )
    )[0]
    result = await ingest.correct(
        m_event, CorrectionRequest(content=CORRECTED, client_timestamp=t_c)
    )
    after = await db.fetch_vector_candidates(pool, agent, probe_vec, 10)
    check(
        after[0].memory_id == m_event and after[0].distance < 1e-6,
        "post-correction: the memory ranks FIRST at the db layer with "
        "distance ~ 0 (pure-distance order; fake-mode fixture mechanic)",
        f"distance={after[0].distance:.2e}",
    )
    r_service = await retrieval.retrieve_dialogue_init(request(agent, CORRECTED, NOW))
    served = {item.memory_id: item for item in r_service.items}
    check(
        m_event in served
        and served[m_event].relevance is not None
        and served[m_event].relevance > 0.999,
        "service layer: the corrected memory is present with relevance ~ 1.0",
    )

    # ------------------------------------------------------------------ #
    print("\n[5] Fact-chain shape: non-destructive supersession, both stamps")
    facts_c = await fact_chain(pool, m_event)
    head = facts_c[-1]
    superseded = facts_c[0]
    check(
        len(facts_c) == 2
        and head[0] == "authorial_correction"
        and head[1] == CORRECTED
        and head[2] == t_c
        and head[3] is None
        and head[5] is False,
        "corrected fact head live: basis byte-verbatim, valid_at = t_c, "
        "embedding present",
    )
    check(
        superseded[3] == t_c
        and superseded[6] == original_fact_vec_text
        and len([r for r in facts_c if r[3] is None]) == 1,
        "superseded fact row keeps the ORIGINAL embedding value-identically "
        "(the record never lies); one live head holds",
    )
    check(
        result.fact_version_id == head[4]
        and result.superseded_fact_version_id == superseded[4]
        and result.embed_ms >= 0
        and result.embedding_tokens > 0,
        "CorrectionResult carries both fact IDs + the embed call's "
        "timing/tokens (v1's no-token line superseded)",
    )
    # Entities follow the correction (gate build 2026-07-19, fork 3): the
    # corrected fact head carries the NER merge; the superseded row keeps
    # its own (non-destructive, the embedding precedent above).
    fact_entities = await fetchall(
        pool,
        "SELECT write_cause, entities FROM memory_fact_versions "
        "WHERE memory_id = %s ORDER BY created_at",
        m_event,
    )
    check(
        (fact_entities[-1][1] or []) == result.entities and result.nlp_ms >= 0.0,
        "corrected fact head carries the merged entities; CorrectionResult "
        "echoes them + nlp_ms",
    )
    check(
        fact_entities[0][1] == pre_fact_entities,
        "the superseded fact row keeps ITS entities (non-destructive record)",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] Bi-temporal coherence on the fact chain around t_c")
    just_before = t_c - timedelta(seconds=1)
    for probe_t, expected, label in (
        (just_before, ["original"], "before t_c the original fact was live"),
        (
            t_c,
            ["authorial_correction"],
            "at t_c exactly the corrected fact is in-window (no gap, no overlap)",
        ),
    ):
        rows = await fetchall(
            pool,
            "SELECT write_cause FROM memory_fact_versions WHERE memory_id = %s "
            "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
            m_event,
            probe_t,
            probe_t,
        )
        check([r[0] for r in rows] == expected, label)

    # ------------------------------------------------------------------ #
    print("\n[7] Telling-side v1 contract intact + eviction unchanged")
    seeded_ev = await seed_memory(ingest, agent, T_EVICT, NOW - timedelta(hours=2))
    m_evict = seeded_ev.memory_id
    await db.insert_cache_row(pool, m_evict, "v1|b0", "cached text one")
    await db.insert_cache_row(pool, m_evict, "v1|b1", "cached text two")
    obs_before = await fetchrow(
        pool, "SELECT observation_text FROM memories WHERE memory_id = %s", m_evict
    )
    spans_before = await fetchall(
        pool,
        "SELECT span_id, start_char, end_char FROM memory_gist_spans "
        "WHERE memory_id = %s ORDER BY start_char",
        m_evict,
    )
    res_ev = await ingest.correct(
        m_evict, CorrectionRequest(content=CORRECTED_EVICT, client_timestamp=NOW)
    )
    details_ev = await detail_chain(pool, m_evict)
    check(
        len(details_ev) == 2
        and details_ev[0][0] == "original"
        and details_ev[0][3] == NOW
        and details_ev[-1][0] == "authorial_correction"
        and details_ev[-1][1] == CORRECTED_EVICT
        and details_ev[-1][3] is None,
        "telling chain: v1 replace-model shape unchanged by fact-following",
    )
    check(
        res_ev.evicted_cache_rows == 2
        and await fetchall(
            pool,
            "SELECT 1 FROM reconstruction_cache WHERE memory_id = %s",
            m_evict,
        )
        == [],
        "cache eviction inherited: all rows gone, count reported",
    )
    obs_after = await fetchrow(
        pool, "SELECT observation_text FROM memories WHERE memory_id = %s", m_evict
    )
    spans_after = await fetchall(
        pool,
        "SELECT span_id, start_char, end_char FROM memory_gist_spans "
        "WHERE memory_id = %s ORDER BY start_char",
        m_evict,
    )
    check(
        obs_after == obs_before and spans_after == spans_before,
        "observation_text and gist span rows untouched (immutable facts "
        "about the original observation)",
    )
    check(
        await fetchall(pool, "SELECT 1 FROM corrections") == [],
        "no corrections row (diegetic-only by CHECK)",
    )

    # ------------------------------------------------------------------ #
    print("\n[8] All-or-nothing embed failure: nothing written on either chain")
    failing_ingest = IngestService(
        pool, fake_providers(embedding=FailingEmbeddingProvider()), settings
    )
    details_pre = await detail_chain(pool, m_evict)
    facts_pre = await fact_chain(pool, m_evict)
    await db.insert_cache_row(pool, m_evict, "v2|b0", "post-correction cache")
    try:
        await failing_ingest.correct(
            m_evict,
            CorrectionRequest(content="never lands", client_timestamp=NOW),
        )
        fail("embed failure", "no exception raised")
    except CorrectionEmbedFailedError:
        ok("embed failure raises CorrectionEmbedFailedError (502 at the route)")
    check(
        await detail_chain(pool, m_evict) == details_pre
        and await fact_chain(pool, m_evict) == facts_pre,
        "telling chain and fact chain byte-identical after the failure",
    )
    cache_kept = await fetchall(
        pool, "SELECT 1 FROM reconstruction_cache WHERE memory_id = %s", m_evict
    )
    check(cache_kept == [(1,)], "cache rows intact — nothing was evicted")

    # ------------------------------------------------------------------ #
    print("\n[9] A correction repairs an embed-degraded memory")
    degraded = await failing_ingest.ingest_observation(
        ObserveEvent(
            agent_id=agent,
            observation_text=T_REPAIR,
            phase_tag="scene.action",
            client_timestamp=NOW - timedelta(hours=2),
            provenance="lived",
        )
    )
    m_repair = degraded.memory_id
    facts_d = await fact_chain(pool, m_repair)
    check(
        degraded.embedding_failed is True and facts_d[0][5] is True,
        "degraded observe: NULL embedding lives on the fact head (the "
        "queryable signal's home since the freeze ruling)",
    )
    repair_probe = embedder.embed([CORRECTED_REPAIR]).vectors[0]
    pre_repair = await db.fetch_vector_candidates(pool, agent, repair_probe, 20)
    check(
        m_repair not in {row.memory_id for row in pre_repair},
        "NULL-fact-embedding row unreachable by the vector probe",
    )
    await ingest.correct(
        m_repair,
        CorrectionRequest(content=CORRECTED_REPAIR, client_timestamp=NOW),
    )
    post_repair = await db.fetch_vector_candidates(pool, agent, repair_probe, 20)
    check(
        post_repair[0].memory_id == m_repair and post_repair[0].distance < 1e-6,
        "the correction re-embeds: the repaired memory is vector-reachable "
        "(the sanctioned re-embed path for embed-degraded rows)",
    )

    # ------------------------------------------------------------------ #
    print("\n[10] Route: 502 on embed failure; 200 pass-through of the widened result")
    import httpx

    import app.api as api_module

    class CapturingService:
        def __init__(self, inner):
            self._inner = inner
            self.last = None

        async def correct(self, memory_id, body):
            self.last = await self._inner.correct(memory_id, body)
            return self.last

        def __getattr__(self, name):
            return getattr(self._inner, name)

    capturing = CapturingService(ingest)
    api_module.app.state.service = capturing
    transport = httpx.ASGITransport(app=api_module.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://walker"
    ) as client:
        payload = json.loads(
            CorrectionRequest(
                content="The chalice is accounted for.",
                client_timestamp=NOW + timedelta(minutes=5),
            ).model_dump_json()
        )
        response = await client.post(f"/v1/memories/{m_event}/correction", json=payload)
        check(response.status_code == 200, "route returned 200")
        body = response.json()
        check(
            body == json.loads(capturing.last.model_dump_json())
            and "fact_version_id" in body
            and "embedding_tokens" in body,
            "route JSON is exactly the serialized widened CorrectionResult",
        )
        api_module.app.state.service = failing_ingest
        r502 = await client.post(f"/v1/memories/{m_event}/correction", json=payload)
        check(
            r502.status_code == 502,
            "embed failure -> 502 with nothing written (all-or-nothing)",
        )

    await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    # psycopg async cannot run on Windows' default ProactorEventLoop.
    asyncio.run(
        main(args.database_uri or scratch_uri_from_env()),
        loop_factory=asyncio.SelectorEventLoop,
    )
