"""verify_reconstruction.py — structural done-when walker for reconstruction v1
(docs\\reconstruction.md).

Runs the reconstruction done-when list against the SCRATCH database (default:
the .env DATABASE_URI with its database name swapped to `twicetold_test`), with
deterministic fake providers — offline, keyless, and structural-only per
tests\\CLAUDE.md: assertions touch IDs, row shapes (write_cause, read_mode),
chain shape, cache presence/absence + byte-identity of stored/served text,
flags, and counters, never generated prose. The schema-frozen criterion
(`db\\migrate.py` no-arg a clean no-op on `twicetold`) runs outside this walker.

The prior walkers keep the v1 serving contract under a per-agent
`reconstruction_theta = 0` pin; the swapped behavior verified here is this
walker's floor.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_reconstruction.py [--database-uri <scratch-uri>]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.identity import render_identity_document
from app.ingest import IngestService
from app.providers import (
    DriftingReconstructionProvider,
    FailingEmbeddingProvider,
    FailingReconstructionProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    MalformedReconstructionProvider,
    Providers,
    ReconstructionItem,
)
from app.reconstruction import (
    UnknownIdentityVersionError,
    assemble_reconstruction_prompt,
    band_index,
    build_reconstruction_item,
    compose_cache_key,
    merge_spans,
    split_gist_detail,
    thin_detail,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueInitRequest, ObserveEvent, SceneBoundaryEvent
from app.session import SessionRunner

NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
SEED_PROSE = "The ford keeper, wary of strangers."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    # gate_enabled = 0 (gate build 2026-07-19): this walker's runner beats
    # assert the reconstruction contract under v1 every-turn retrieval;
    # the gated behavior is verify_gate.py's floor. FIXTURE-ONLY pin —
    # production runs the gate at real defaults.
    "gate_enabled": 0.0,
}

# Fixture corpus. Ages are chosen so `semantic` (tau 7d) rows sit past theta
# (0.5) at 10 days for ANY hash-derived importance (band 2), and cross into
# band 3 at 40 days — the band-crossing / 60-day-beat mechanic.
T_FRESH = "Mara sharpened my blade at the forge while John watched."
T_OLD = (
    "The stranger broke the miller cart at the ford. He cursed loudly and "
    "blamed the rain. Mara helped drag it clear before nightfall. The road "
    "stayed blocked for hours."
)
T_BRIDGE = (
    "The flood carried the south bridge away one spring. Twenty families "
    "crossed at the mill for a season. The mason rebuilt the arches by "
    "autumn. Mara hauled stone for him."
)
T_PIN = (
    "Wolves took two lambs in the north pasture during the long frost. The "
    "shepherd blamed himself. Mara sat with him that evening."
)
T_DRIFT = (
    "A pedlar sold me a crooked knife at the harvest fair. The blade snapped "
    "on the first cut. Mara laughed about it for a week."
)
T_WELL = (
    "The old well ran dry in high summer. We carted water from the river for "
    "a month. Mara found the new spring by the birch grove."
)

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
        reconstruction=overrides.get("reconstruction", FakeReconstructionProvider()),
    )


async def make_agent(pool, name: str, config: dict, seed: str | None = SEED_PROSE):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, seed, "what threatens the ford", Jsonb(config)),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, category) "
            "VALUES (%s, 'Mara', %s, 'person')",
            (agent_id, ["the blacksmith"]),
        )
    return agent_id


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def execute(pool, sql: str, *params) -> None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)


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
    return result.memory_id


async def chain(pool, memory_id):
    """(write_cause, content, valid_at, invalid_at, detail_id) rows, oldest first."""
    return await fetchall(
        pool,
        "SELECT write_cause, content, valid_at, invalid_at, detail_id "
        "FROM memory_details WHERE memory_id = %s ORDER BY created_at",
        memory_id,
    )


async def cache_rows(pool, memory_id):
    return {
        row[0]: row[1]
        for row in await fetchall(
            pool,
            "SELECT identity_version, rendered_text FROM reconstruction_cache "
            "WHERE memory_id = %s",
            memory_id,
        )
    }


def request(agent_id, version, basis, **overrides) -> DialogueInitRequest:
    base = dict(
        agent_id=agent_id,
        query_text=T_OLD,
        as_of=basis,
        scene_started_at=basis,
        identity_version=version,
    )
    base.update(overrides)
    return DialogueInitRequest(**base)


def by_id(result) -> dict:
    return {item.memory_id: item for item in result.items}


async def main(database_uri: str) -> None:
    from app.config import Settings

    settings = Settings(database_uri=database_uri, provider_mode="fake")
    pool = db.build_pool(database_uri)
    await pool.open()
    ingest = IngestService(pool, fake_providers(), settings)
    retrieval = RetrievalService(pool, fake_providers(), settings)
    print(f"walker: scratch DB = {urlsplit(database_uri).path.lstrip('/')}")

    # ------------------------------------------------------------------ #
    print("\n[P] Pure functions (prompt assembly assertable without a model)")
    check(
        merge_spans([(6, 10), (2, 8), (20, 24)]) == [(2, 10), (20, 24)],
        "overlapping gist spans merge; disjoint spans stay",
    )
    sample = "First part here. Second sentence. Mara did it. Tail one. Tail two."
    m_start = sample.index("Mara")
    gist, segments = split_gist_detail(sample, [(m_start, m_start + 12)])
    check(
        gist == sample[m_start : m_start + 12] and len(segments) == 2,
        "gist is the byte-exact observation slice; detail = the remainders",
        repr(gist),
    )
    full = thin_detail(segments, 0.875)
    thin = thin_detail(segments, 0.125)
    check(
        len(thin) < len(full) and all(seg.split(". ")[0] in thin for seg in segments),
        "thinning is monotone in the band and keeps each segment's lead",
    )
    check(
        [band_index(s, 0.25) for s in (0.9, 0.6, 0.3, 0.05, 0.0001)] == [0, 1, 2, 3, 3]
        and compose_cache_key("vhash", 2) == "vhash|b2",
        "band quantization (capped) and composed cache key shape",
    )
    items = [
        ReconstructionItem(
            memory_id="m1", gist=gist, thinned_detail=thin, current_telling=sample
        )
    ]
    sys_with, user_a = assemble_reconstruction_prompt("I keep the ford.", items)
    sys_without, _ = assemble_reconstruction_prompt("", items)
    payload = json.loads(user_a)
    check(
        sys_with.startswith("[identity]\nI keep the ford.")
        and "[identity]" not in sys_without
        and payload[0]["gist"] == gist
        and payload[0]["current_telling"] == sample
        and assemble_reconstruction_prompt("I keep the ford.", items)
        == (sys_with, user_a),
        "prompt: identity block present/omitted; gist + prior telling ride the "
        "JSON; byte-stable for identical inputs",
    )
    rendered, version = render_identity_document(SEED_PROSE)
    r_null, v_null = render_identity_document(None)
    check(
        rendered == SEED_PROSE
        and version == hashlib.sha256(SEED_PROSE.encode()).hexdigest()
        and (r_null, v_null) == ("", hashlib.sha256(b"").hexdigest()),
        "identity document renders seed verbatim; sha256 versions incl. NULL seed",
    )

    # ------------------------------------------------------------------ #
    print("\n[I] Identity plumbing: scene-boundary recompile (server-side)")
    agent_a = await make_agent(pool, "recon-walker-npc-a", AGENT_CONFIG)
    s1 = await ingest.scene_boundary(
        SceneBoundaryEvent(agent_id=agent_a, client_timestamp=NOW)
    )
    check(
        s1.identity_version == version and s1.identity_document_new is True,
        "first boundary recompiles: content-hash version returned, row created",
    )
    s2 = await ingest.scene_boundary(
        SceneBoundaryEvent(agent_id=agent_a, client_timestamp=NOW)
    )
    check(
        s2.identity_version == version and s2.identity_document_new is False,
        "unchanged seed re-hashes to the same version; upsert is a no-op",
    )
    doc_row = await fetchrow(
        pool,
        "SELECT rendered_text FROM identity_documents "
        "WHERE agent_id = %s AND identity_version = %s",
        agent_a,
        version,
    )
    check(
        doc_row is not None and doc_row[0] == SEED_PROSE,
        "identity_documents row carries the seed prose verbatim",
    )

    # ------------------------------------------------------------------ #
    print("\n[1] Theta boundary + batched write-back (happy path)")
    ids = {
        "fresh": await seed_memory(ingest, agent_a, T_FRESH, NOW - timedelta(hours=1)),
        "old": await seed_memory(
            ingest, agent_a, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        ),
        "bridge": await seed_memory(
            ingest, agent_a, T_BRIDGE, NOW - timedelta(days=10), decay_class="semantic"
        ),
        "pin": await seed_memory(
            ingest,
            agent_a,
            T_PIN,
            NOW - timedelta(days=10),
            decay_class="semantic",
            pinned=True,
        ),
    }
    r1 = await retrieval.retrieve_dialogue_init(request(agent_a, version, NOW))
    m1 = by_id(r1)
    check(
        m1[ids["fresh"]].read_mode == "verbatim"
        and m1[ids["old"]].read_mode == "reconstructed"
        and m1[ids["bridge"]].read_mode == "reconstructed"
        and m1[ids["pin"]].read_mode == "verbatim",
        "three-state boundary: fresh + pinned verbatim; past-theta reconstructed",
    )
    i1 = r1.instrumentation
    check(
        i1.cache_misses == 2
        and i1.write_backs == 2
        and i1.cache_hits == 0
        and i1.reconstruction_input_tokens > 0
        and i1.reconstruction_output_tokens > 0
        and i1.reconstruction_embed_tokens > 0
        and i1.reconstruction_ms >= 0
        and i1.identity_version_effective == version
        and i1.identity_bootstrapped is False,
        "one batched call: 2 misses -> 2 write-backs; tokens + counters recorded",
    )
    old_chain = await chain(pool, ids["old"])
    check(
        len(old_chain) == 2
        and old_chain[0][0] == "original"
        and old_chain[0][3] == NOW  # superseded at the scene basis
        and old_chain[1][0] == "reconstruction"
        and old_chain[1][3] is None
        and old_chain[1][2] == NOW,  # new head valid_at = the scene basis
        "write-back chain shape: original superseded at basis; one live "
        "`reconstruction` head at basis; same memory_id",
    )
    check(
        m1[ids["old"]].content == old_chain[1][1]
        and m1[ids["old"]].detail_id == old_chain[1][4],
        "served content and detail_id are the committed new head",
    )
    old_cache = await cache_rows(pool, ids["old"])
    old_key = next(iter(old_cache))
    check(
        old_key.startswith(f"{version}|b")
        and old_cache[old_key] == m1[ids["old"]].content,
        "cache row keyed identity_version|band; rendered_text == served text "
        "(serve-only-persisted-text)",
        old_key.split("|")[-1],
    )
    row_after = await fetchrow(
        pool,
        "SELECT observation_text FROM memories WHERE memory_id = %s",
        ids["old"],
    )
    span_count = await fetchrow(
        pool,
        "SELECT count(*) FROM memory_gist_spans WHERE memory_id = %s",
        ids["old"],
    )
    check(
        row_after[0] == T_OLD and span_count[0] > 0,
        "observation_text and gist span rows untouched by the write-back",
    )

    # ------------------------------------------------------------------ #
    print("\n[2] Cache hit: call-free, byte-identical; scores independent")
    r2 = await retrieval.retrieve_dialogue_init(request(agent_a, version, NOW))
    i2 = r2.instrumentation
    check(
        i2.cache_hits == 2
        and i2.cache_misses == 0
        and i2.write_backs == 0
        and i2.reconstruction_input_tokens == 0,
        "second identical read: 2 hits, no call, no new rows",
    )
    m2 = by_id(r2)
    check(
        all(m2[mid].content == m1[mid].content for mid in ids.values())
        and all(m2[mid].read_mode == m1[mid].read_mode for mid in ids.values()),
        "served text + read_mode byte-identical across identical reads",
    )
    check(
        all(
            (
                m2[mid].score,
                m2[mid].relevance,
                m2[mid].recency,
                m2[mid].importance_norm,
            )
            == (
                m1[mid].score,
                m1[mid].relevance,
                m1[mid].recency,
                m1[mid].importance_norm,
            )
            for mid in ids.values()
        ),
        "score components identical before/after write-back — the swap never "
        "touches retrieval or scoring",
    )

    # ------------------------------------------------------------------ #
    print("\n[5] Within-scene stability: text frozen at the basis, scores move")
    r5 = await retrieval.retrieve_dialogue_init(
        request(agent_a, version, NOW, as_of=NOW + timedelta(days=40))
    )
    m5 = by_id(r5)
    check(
        all(m5[mid].content == m2[mid].content for mid in ids.values())
        and all(m5[mid].read_mode == m2[mid].read_mode for mid in ids.values())
        and r5.instrumentation.cache_misses == 0,
        "as_of advanced 40d mid-scene: basis frozen -> same keys, same text",
    )
    check(
        m5[ids["fresh"]].recency < m2[ids["fresh"]].recency,
        "score-side recency still follows per-call as_of (scores may move; "
        "text may not)",
    )

    # ------------------------------------------------------------------ #
    print("\n[4] Band crossing at the next boundary: retold on thinner detail")
    basis2 = NOW + timedelta(days=30)  # age 40d -> band 3 for the semantic rows
    r4 = await retrieval.retrieve_dialogue_init(request(agent_a, version, basis2))
    i4 = r4.instrumentation
    old_cache4 = await cache_rows(pool, ids["old"])
    bands = sorted(int(k.rsplit("|b", 1)[1]) for k in old_cache4)
    check(
        # 3 misses: the two semantic rows cross b2 -> b3, and T_FRESH
        # (episodic, 30 days old at this basis) has itself crossed theta.
        i4.cache_misses == 3 and i4.write_backs == 3 and len(old_cache4) == 2,
        "deeper basis crosses a band edge: new keys, re-reconstruction",
    )
    check(
        bands[1] > bands[0],
        "the two cache keys carry strictly deepening bands",
        f"b{bands[0]} -> b{bands[1]}",
    )
    old_chain4 = await chain(pool, ids["old"])
    check(
        len(old_chain4) == 3
        and old_chain4[2][0] == "reconstruction"
        and old_chain4[2][2] == basis2
        and old_chain4[1][3] == basis2,
        "chain grew under the same memory_id; prior retelling superseded at "
        "the new basis",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] Identity bump => cache miss; conditioning changes the telling")
    await execute(
        pool,
        "UPDATE agents SET seed_identity = %s WHERE agent_id = %s",
        "The ford keeper, older now, and tired of strangers.",
        agent_a,
    )
    s3 = await ingest.scene_boundary(
        SceneBoundaryEvent(agent_id=agent_a, client_timestamp=basis2)
    )
    version2 = s3.identity_version
    check(
        version2 != version and s3.identity_document_new is True,
        "seed change re-hashes: new identity_version, new document row",
    )
    r3 = await retrieval.retrieve_dialogue_init(request(agent_a, version2, basis2))
    i3 = r3.instrumentation
    old_cache3 = await cache_rows(pool, ids["old"])
    v1_key = compose_cache_key(version, 3)
    v2_key = compose_cache_key(version2, 3)
    check(
        # 3 again: both semantic rows + the theta-crossed T_FRESH, all under
        # the new version's keys.
        i3.cache_misses == 3 and i3.write_backs == 3 and v2_key in old_cache3,
        "identity-version bump: same band, new composed key -> miss + retell",
    )
    check(
        old_cache3[v2_key] != old_cache3[v1_key],
        "the retelling under the new identity differs from the old key's "
        "(identity conditioning is live)",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] Pin exclusion")
    pin_chain = await chain(pool, ids["pin"])
    pin_cache = await cache_rows(pool, ids["pin"])
    check(
        len(pin_chain) == 1 and pin_chain[0][0] == "original" and not pin_cache,
        "pinned memory never grew a chain row or a cache row across every read",
    )
    check(
        by_id(r3)[ids["pin"]].read_mode == "verbatim",
        "pinned serves verbatim even past theta-age",
    )

    # ------------------------------------------------------------------ #
    print("\n[8] Drift anchor: authorial correction re-anchors (db layer)")
    corrected = "The stranger's cart broke at the ford; Mara and I cleared it."
    old_head = (await chain(pool, ids["old"]))[-1]
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE memory_details SET invalid_at = %s WHERE detail_id = %s",
                    (basis2, old_head[4]),
                )
                await cur.execute(
                    "INSERT INTO memory_details (memory_id, content, write_cause, "
                    "valid_at) VALUES (%s, %s, 'authorial_correction', %s)",
                    (ids["old"], corrected, basis2),
                )
                # The correction writer's obligation (eviction invariant):
                await cur.execute(
                    "DELETE FROM reconstruction_cache WHERE memory_id = %s",
                    (ids["old"],),
                )
    sources = await db.fetch_reconstruction_sources(pool, [ids["old"]])
    check(
        sources[ids["old"]].anchor_content == corrected,
        "anchor resolves to the corrected head (derivable, no pointer)",
    )
    item8 = build_reconstruction_item(
        str(ids["old"]), sources[ids["old"]], 0.5, corrected
    )
    check(
        item8.gist == corrected and item8.thinned_detail == "",
        "constraint follows the anchor: the corrected head is the fixed "
        "constraint, no observation detail (authorial-correction build)",
    )
    r8 = await retrieval.retrieve_dialogue_init(request(agent_a, version2, basis2))
    m8 = by_id(r8)[ids["old"]]
    head8 = (await chain(pool, ids["old"]))[-1]
    check(
        head8[0] == "reconstruction"
        and m8.content == head8[1]
        and m8.read_mode == "reconstructed",
        "post-correction read reconstructs from the corrected telling "
        "(cache was evicted; write-back passes against the new anchor)",
    )

    # ------------------------------------------------------------------ #
    print("\n[13] C4 ruling 4: update_with_resentment takes the fixed-")
    print("     constraint branch; rationalization never re-anchors")
    agent_c4 = await make_agent(pool, "recon-walker-npc-c4", AGENT_CONFIG)
    t_c4u = (
        "The miller shorted me a full sack at the autumn weighing and "
        "laughed about it with the carters."
    )
    t_c4r = (
        "The reeve took my knife at the gate and never wrote it in the "
        "ledger book that evening."
    )
    accepted = (
        "The sack was full weight after all - the scale arm was bent, they "
        "say. The miller laughed at something else."
    )
    defense = (
        "The carters saw the reeve pocket it - no ledger line ever lies by accident."
    )
    up_id = await seed_memory(
        ingest, agent_c4, t_c4u, NOW - timedelta(days=10), decay_class="semantic"
    )
    ra_id = await seed_memory(
        ingest, agent_c4, t_c4r, NOW - timedelta(days=10), decay_class="semantic"
    )
    ra_orig_head = (await chain(pool, ra_id))[-1]
    for mid, verb, content in (
        (up_id, "update_with_resentment", accepted),
        (ra_id, "rationalization", defense),
    ):
        live = (await chain(pool, mid))[-1]
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE memory_details SET invalid_at = %s "
                        "WHERE detail_id = %s",
                        (basis2, live[4]),
                    )
                    await cur.execute(
                        "INSERT INTO memory_details (memory_id, content, "
                        "write_cause, valid_at) VALUES (%s, %s, %s, %s)",
                        (mid, content, verb, basis2),
                    )
                    # Chain rows + eviction ONLY — no corrections record:
                    # the anchor derives from the telling chain alone (the
                    # exact claim under test), the record obligation is
                    # verify_dissonance's scoped territory, and a record
                    # written here would trip the elder walkers'
                    # diegetic-only emptiness asserts on the shared scratch
                    # (the documented DB-global-count fragility,
                    # status.md's carried item).
                    await cur.execute(
                        "DELETE FROM reconstruction_cache WHERE memory_id = %s",
                        (mid,),
                    )
    sources13 = await db.fetch_reconstruction_sources(pool, [up_id, ra_id])
    check(
        sources13[up_id].anchor_cause == "update_with_resentment"
        and sources13[up_id].anchor_content == accepted,
        "the accepted head IS the anchor (in the anchor set since the "
        "authorial build; exercised live for the first time with C4)",
    )
    item13 = build_reconstruction_item(str(up_id), sources13[up_id], 0.5, accepted)
    check(
        item13.gist == accepted and item13.thinned_detail == "",
        "constraint follows the update anchor: the accepted account is the "
        "fixed constraint, no observation detail (C4 ruling 4, 2026-08-17)",
    )
    r13 = await retrieval.retrieve_dialogue_init(
        request(agent_c4, None, basis2, query_text=t_c4u, identity_version=None)
    )
    m13 = by_id(r13)[up_id]
    head13 = (await chain(pool, up_id))[-1]
    check(
        head13[0] == "reconstruction"
        and m13.content == head13[1]
        and m13.read_mode == "reconstructed",
        "post-event read reconstructs FROM the accepted telling (cache was "
        "evicted; write-back passes against the update anchor)",
    )
    check(
        sources13[ra_id].anchor_cause == "original"
        and sources13[ra_id].anchor_content == ra_orig_head[1],
        "rationalization never re-anchors: the anchor stays the original "
        "head (headroom spent, never blocked - 'the story has set')",
    )

    # ------------------------------------------------------------------ #
    print("\n[7] Drift refusal at the default threshold (+ refusal caching)")
    agent_d = await make_agent(pool, "recon-walker-npc-d", AGENT_CONFIG)
    drift_id = await seed_memory(
        ingest, agent_d, T_DRIFT, NOW - timedelta(days=10), decay_class="semantic"
    )
    drifting = RetrievalService(
        pool, fake_providers(reconstruction=DriftingReconstructionProvider()), settings
    )
    rd = await drifting.retrieve_dialogue_init(
        request(agent_d, None, NOW, query_text=T_DRIFT, identity_version=None)
    )
    d_item = by_id(rd)[drift_id]
    d_chain = await chain(pool, drift_id)
    d_cache = await cache_rows(pool, drift_id)
    check(
        rd.instrumentation.drift_refusals == 1
        and rd.instrumentation.write_backs == 0
        and len(d_chain) == 1,
        "over-threshold candidate refused: no chain row written",
    )
    check(
        d_item.content == d_chain[0][1] and d_item.read_mode == "verbatim",
        "prior head served under honest read_mode (head is `original`)",
    )
    check(
        len(d_cache) == 1 and next(iter(d_cache.values())) == d_chain[0][1],
        "refusal cached the served prior text under the current key",
    )
    rd2 = await drifting.retrieve_dialogue_init(
        request(agent_d, None, NOW, query_text=T_DRIFT, identity_version=None)
    )
    check(
        rd2.instrumentation.cache_hits == 1
        and rd2.instrumentation.reconstruction_input_tokens == 0
        and by_id(rd2)[drift_id].read_mode == "verbatim",
        "next same-key read is a call-free hit, still honestly verbatim",
    )

    # ------------------------------------------------------------------ #
    print("\n[9] Degradation ladder (per model call)")
    agent_f = await make_agent(pool, "recon-walker-npc-f", AGENT_CONFIG)
    well_id = await seed_memory(
        ingest, agent_f, T_WELL, NOW - timedelta(days=10), decay_class="semantic"
    )
    failing = RetrievalService(
        pool, fake_providers(reconstruction=FailingReconstructionProvider()), settings
    )
    rf = await failing.retrieve_dialogue_init(
        request(agent_f, None, NOW, query_text=T_WELL, identity_version=None)
    )
    f_chain = await chain(pool, well_id)
    check(
        rf.instrumentation.degraded
        and "reconstruction call failed" in (rf.instrumentation.degraded_reason or "")
        and len(f_chain) == 1
        and not await cache_rows(pool, well_id)
        and by_id(rf)[well_id].read_mode == "verbatim"
        and by_id(rf)[well_id].content == f_chain[0][1],
        "call failure: fail-quiet — live head served honestly, nothing written",
    )
    malformed = RetrievalService(
        pool,
        fake_providers(reconstruction=MalformedReconstructionProvider()),
        settings,
    )
    rm = await malformed.retrieve_dialogue_init(
        request(agent_f, None, NOW, query_text=T_WELL, identity_version=None)
    )
    check(
        rm.instrumentation.degraded
        and rm.instrumentation.reconstruction_input_tokens == 7
        and len(await chain(pool, well_id)) == 1,
        "malformed output: degrades soft, token spend still accounted",
    )
    embed_down = RetrievalService(
        pool, fake_providers(embedding=FailingEmbeddingProvider()), settings
    )
    re_ = await embed_down.retrieve_dialogue_init(
        request(agent_f, None, NOW, query_text=T_WELL, identity_version=None)
    )
    check(
        re_.instrumentation.drift_refusals == 1
        and re_.instrumentation.write_backs == 0
        and len(await chain(pool, well_id)) == 1
        and not await cache_rows(pool, well_id)
        and "drift-check embedding failed"
        in (re_.instrumentation.degraded_reason or ""),
        "drift-embed failure: fail-closed refusal, not cached (a transient "
        "outage never pins the key)",
    )

    # ------------------------------------------------------------------ #
    print("\n[11] Bare-read bootstrap + unknown version")
    check(
        re_.instrumentation.identity_bootstrapped is True
        and re_.instrumentation.identity_version_effective
        == hashlib.sha256(SEED_PROSE.encode()).hexdigest(),
        "a read without identity_version lazy-bootstraps and flags it",
    )
    try:
        await retrieval.retrieve_dialogue_init(
            request(agent_a, "not-a-known-version", NOW)
        )
        fail("unknown identity_version", "no exception raised")
    except UnknownIdentityVersionError:
        ok("unknown identity_version raises the loud contract error")

    # ------------------------------------------------------------------ #
    print("\n[12] Session-runner freezes the scene state")
    runner = await SessionRunner.create(
        agent_a,
        settings=settings,
        providers=fake_providers(),
        pool=pool,
        phase_tag="recon-walker",
    )
    check(
        runner.identity_version == version2 and runner.scene_started_at is not None,
        "create() freezes the current identity version + a scene basis",
    )
    runner.as_of = basis2 + timedelta(days=30)
    scene_result = await runner.scene()
    check(
        scene_result.identity_version == version2
        and runner.identity_version == version2
        and runner.scene_started_at == runner.as_of,
        "scene() re-freezes from the boundary result; basis follows :as-of",
    )
    await runner.close()

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
