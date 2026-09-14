"""verify_authorial_correction.py — structural done-when walker for the
authorial-correction endpoint v1 (docs\\authorial-correction.md).

Runs the correction done-when list against the SCRATCH database (default:
the .env DATABASE_URI with its path swapped to /twicetold_test); the product
DB is never touched. The schema-frozen criterion (`db\\migrate.py` no-arg a
clean no-op on `twicetold`) runs outside this walker.

Structural-only (tests\\CLAUDE.md): assertions ride IDs, write_cause,
read_mode, chain stamps, cache presence, and byte-identity of OPERATOR text
(which this walker authors) — never model prose.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_authorial_correction.py [--database-uri <scratch-uri>]
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
    CorrectionConflictError,
    IngestService,
    UnknownMemoryError,
)
from app.providers import (
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.reconstruction import (
    assemble_reconstruction_prompt,
    build_reconstruction_item,
    split_gist_detail,
    thin_detail,
)
from app.retrieval import RetrievalService
from app.schemas import (
    CorrectionRequest,
    DialogueInitRequest,
    ObserveEvent,
    SceneBoundaryEvent,
)
from app.session import SessionRunner

NOW = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)
SEED_PROSE = "The ford keeper, wary of strangers."

AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    # gate_enabled = 0 (gate build 2026-07-19): the correction-override beat
    # here asserts under v1 every-turn retrieval; the gated behavior is
    # verify_gate.py's floor. FIXTURE-ONLY pin — production runs the gate.
    "gate_enabled": 0.0,
}

# Semantic (tau 7d) rows at 10 days sit past theta (0.5) for ANY
# hash-derived importance; episodic rows an hour old sit far above it.
T_EVENT = (
    "The stranger broke the miller cart at the ford. He cursed loudly and "
    "blamed the rain. Mara helped drag it clear before nightfall. The road "
    "stayed blocked for hours."
)
CORRECTED = (
    "It was John's cart that broke at the ford; John and I cleared it before nightfall."
)
T_FRESH = "Mara sharpened my blade at the forge this morning."
CORRECTED_FRESH = "John sharpened my blade at the forge; Mara only watched."
T_PIN = (
    "Wolves took two lambs in the north pasture during the long frost. The "
    "shepherd blamed himself. Mara sat with him that evening."
)
CORRECTED_PIN = "One lamb was lost to the frost itself; the wolves took none."
T_CAS = "A pedlar sold me a crooked knife at the harvest fair."
T_WELL = "The old well ran dry in high summer."

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
        reconstruction=FakeReconstructionProvider(),
    )


async def make_agent(pool, name: str):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED_PROSE, "what threatens the ford", Jsonb(AGENT_CONFIG)),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, 'Mara', %s, 'person')",
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
    """(write_cause, content, valid_at, invalid_at, detail_id), oldest first."""
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
        query_text=T_EVENT,
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
    print("\n[P] Pure: constraint follows the anchor (no db, no model)")
    obs = "Alpha beta gamma. Delta epsilon. Zeta eta theta. Iota kappa."
    spans = [(0, 17)]
    src_original = db.ReconstructionSource(
        observation_text=obs,
        spans=spans,
        anchor_content="the original head",
        anchor_cause="original",
    )
    item_o = build_reconstruction_item("m1", src_original, 0.5, "the telling")
    gist, segments = split_gist_detail(obs, spans)
    check(
        item_o.gist == gist
        and item_o.thinned_detail == thin_detail(segments, 0.5)
        and item_o.current_telling == "the telling",
        "original-anchored item builds byte-identically to the v1 stage",
    )
    src_corrected = db.ReconstructionSource(
        observation_text=obs,
        spans=spans,
        anchor_content=CORRECTED,
        anchor_cause="authorial_correction",
    )
    item_c = build_reconstruction_item("m1", src_corrected, 0.5, "the telling")
    check(
        item_c.gist == CORRECTED
        and item_c.thinned_detail == ""
        and item_c.current_telling == "the telling",
        "corrected-anchored item: the corrected head IS the fixed constraint; "
        "no observation-derived detail re-injected",
    )
    check(
        build_reconstruction_item("m1", src_corrected, 0.1, "x").gist == CORRECTED,
        "the thinning level does not touch a corrected chain's constraint",
    )
    _, user_content = assemble_reconstruction_prompt("doc", [item_c])
    parsed = json.loads(user_content)
    check(
        parsed[0]["gist"] == CORRECTED and parsed[0]["detail"] == "",
        "assembly passes the corrected constraint through unchanged",
    )

    # ------------------------------------------------------------------ #
    print("\n[1] Replace-model chain shape + eviction + re-anchor")
    agent = await make_agent(pool, "corr-walker-npc")
    scene = await ingest.scene_boundary(
        SceneBoundaryEvent(agent_id=agent, client_timestamp=NOW)
    )
    version = scene.identity_version
    m_event = await seed_memory(
        ingest, agent, T_EVENT, NOW - timedelta(days=10), decay_class="semantic"
    )
    await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
    chain1 = await chain(pool, m_event)
    check(
        len(chain1) == 2 and chain1[-1][0] == "reconstruction",
        "fixture: the chain drifted first (a reconstruction head is live)",
    )
    pre_cache = await cache_rows(pool, m_event)
    check(len(pre_cache) >= 1, "fixture: cache rows exist pre-correction")
    obs_before = await fetchrow(
        pool, "SELECT observation_text FROM memories WHERE memory_id = %s", m_event
    )
    spans_before = await fetchall(
        pool,
        "SELECT start_char, end_char FROM memory_gist_spans "
        "WHERE memory_id = %s ORDER BY start_char",
        m_event,
    )
    t_c = NOW + timedelta(hours=1)
    result = await ingest.correct(
        m_event, CorrectionRequest(content=CORRECTED, client_timestamp=t_c)
    )
    chain2 = await chain(pool, m_event)
    head = chain2[-1]
    superseded = chain2[1]
    check(
        len(chain2) == 3
        and head[0] == "authorial_correction"
        and head[1] == CORRECTED
        and head[2] == t_c
        and head[3] is None,
        "exactly one live head: authorial_correction, operator text "
        "byte-verbatim, valid_at = t_c",
    )
    check(
        superseded[3] == t_c and len([r for r in chain2 if r[3] is None]) == 1,
        "prior head superseded at t_c (one-live-head holds)",
    )
    check(
        result.detail_id == head[4]
        and result.superseded_detail_id == superseded[4]
        and result.evicted_cache_rows == len(pre_cache)
        and result.total_ms >= 0,
        "CorrectionResult carries the IDs + the eviction count + timing",
    )
    check(
        await cache_rows(pool, m_event) == {},
        "every cache row for the memory evicted, atomically with the write",
    )
    check(
        await fetchall(pool, "SELECT 1 FROM corrections") == [],
        "no corrections row (that table is diegetic-only by CHECK)",
    )
    obs_after = await fetchrow(
        pool, "SELECT observation_text FROM memories WHERE memory_id = %s", m_event
    )
    spans_after = await fetchall(
        pool,
        "SELECT start_char, end_char FROM memory_gist_spans "
        "WHERE memory_id = %s ORDER BY start_char",
        m_event,
    )
    check(
        obs_after == obs_before and spans_after == spans_before,
        "observation_text and gist span rows untouched",
    )
    sources = await db.fetch_reconstruction_sources(pool, [m_event])
    check(
        sources[m_event].anchor_content == CORRECTED
        and sources[m_event].anchor_cause == "authorial_correction",
        "the drift anchor resolves to the corrected head (derivable)",
    )
    # Fact-following (fact-level-correction.md, built 2026-07-18): the same
    # verb swaps the fact head; the drift write-back above minted NO fact row.
    facts = await fetchall(
        pool,
        "SELECT write_cause, basis_text, invalid_at, fact_version_id "
        "FROM memory_fact_versions WHERE memory_id = %s ORDER BY created_at",
        m_event,
    )
    check(
        len(facts) == 2
        and facts[0][0] == "original"
        and facts[0][2] == t_c
        and facts[1][0] == "authorial_correction"
        and facts[1][1] == CORRECTED
        and facts[1][2] is None,
        "fact chain: original -> corrected only (the reconstruction "
        "write-back never touches facts); corrected basis byte-verbatim",
    )
    check(
        result.fact_version_id == facts[1][3]
        and result.superseded_fact_version_id == facts[0][3]
        and result.embed_ms >= 0
        and result.embedding_tokens > 0,
        "CorrectionResult carries the fact IDs + embed timing/tokens "
        "(widened at the fact-level build)",
    )
    # Entities follow the correction (gate build 2026-07-19, fork 3).
    corrected_entities = await fetchrow(
        pool,
        "SELECT entities FROM memory_fact_versions WHERE fact_version_id = %s",
        result.fact_version_id,
    )
    check(
        (corrected_entities[0] or []) == result.entities and result.nlp_ms >= 0.0,
        "the corrected fact head carries the re-derived entities; the result "
        "echoes them + the mechanical NER pass's timing",
    )

    # ------------------------------------------------------------------ #
    print(
        "\n[2] Bi-temporal coherence around t_c (ruled 2026-07-18: stored "
        "coherence — as_of stays an age override)"
    )
    just_before = t_c - timedelta(seconds=1)
    past = await fetchall(
        pool,
        "SELECT write_cause FROM memory_details WHERE memory_id = %s "
        "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
        m_event,
        just_before,
        just_before,
    )
    check(
        [row[0] for row in past] == ["reconstruction"],
        "a windowed query re-derives the pre-correction telling",
    )
    at_tc = await fetchall(
        pool,
        "SELECT write_cause FROM memory_details WHERE memory_id = %s "
        "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
        m_event,
        t_c,
        t_c,
    )
    check(
        [row[0] for row in at_tc] == ["authorial_correction"],
        "at t_c exactly the corrected head is in-window (no gap, no overlap)",
    )

    # ------------------------------------------------------------------ #
    print("\n[3] Past-theta read reconstructs under the corrected constraint")
    r3 = await retrieval.retrieve_dialogue_init(request(agent, version, t_c))
    m3 = by_id(r3)[m_event]
    chain3 = await chain(pool, m_event)
    check(
        chain3[-1][0] == "reconstruction"
        and m3.content == chain3[-1][1]
        and m3.read_mode == "reconstructed"
        and r3.instrumentation.write_backs == 1,
        "the evicted cache misses; the retelling write-back passes against "
        "the corrected anchor",
    )

    # ------------------------------------------------------------------ #
    print("\n[4] Immediate mid-scene effect (pre-theta corrected serving)")
    m_fresh = await seed_memory(ingest, agent, T_FRESH, t_c - timedelta(hours=1))
    r4a = await retrieval.retrieve_dialogue_init(
        request(agent, version, t_c, query_text=T_FRESH)
    )
    a = by_id(r4a)[m_fresh]
    head_fresh = (await chain(pool, m_fresh))[-1]
    check(
        a.read_mode == "verbatim" and a.content == head_fresh[1],
        "fresh memory serves its original head verbatim",
    )
    corr4 = await ingest.correct(
        m_fresh, CorrectionRequest(content=CORRECTED_FRESH, client_timestamp=t_c)
    )
    r4b = await retrieval.retrieve_dialogue_init(
        request(agent, version, t_c, query_text=T_FRESH)
    )
    b = by_id(r4b)[m_fresh]
    check(
        b.content == CORRECTED_FRESH
        and b.read_mode == "verbatim"
        and b.content != a.content
        and b.detail_id == corr4.detail_id,
        "same scene basis, next read serves the corrected text — the amended "
        "invariant's sanctioned change",
    )

    # ------------------------------------------------------------------ #
    print("\n[5] Correction outranks pin; the corrected head inherits it")
    m_pin = await seed_memory(
        ingest, agent, T_PIN, NOW - timedelta(days=10), decay_class="semantic"
    )
    await ingest.set_pin(m_pin, True)
    await ingest.correct(
        m_pin, CorrectionRequest(content=CORRECTED_PIN, client_timestamp=t_c)
    )
    r5 = await retrieval.retrieve_dialogue_init(
        request(agent, version, t_c, query_text=T_PIN)
    )
    p = by_id(r5)[m_pin]
    chain5 = await chain(pool, m_pin)
    check(
        len(chain5) == 2
        and chain5[-1][0] == "authorial_correction"
        and p.content == CORRECTED_PIN
        and p.read_mode == "verbatim"
        and p.pinned is True,
        "pinned memory corrected; serves the corrected head verbatim",
    )
    await retrieval.retrieve_dialogue_init(
        request(agent, version, t_c, query_text=T_PIN)
    )
    check(
        len(await chain(pool, m_pin)) == 2,
        "pinned + corrected never grows a reconstruction row",
    )

    # ------------------------------------------------------------------ #
    print("\n[6] Compare-and-swap: stale expected_detail_id changes nothing")
    m_cas = await seed_memory(ingest, agent, T_CAS, t_c)
    head_cas = (await chain(pool, m_cas))[-1]
    try:
        await ingest.correct(
            m_cas,
            CorrectionRequest(
                content="A straight knife after all.",
                client_timestamp=t_c + timedelta(minutes=1),
                expected_detail_id=uuid4(),
            ),
        )
        fail("stale CAS", "no exception raised")
    except CorrectionConflictError:
        ok("stale expected_detail_id raises the conflict error (409)")
    chain_cas = await chain(pool, m_cas)
    check(
        len(chain_cas) == 1
        and chain_cas[0][3] is None
        and chain_cas[0][4] == head_cas[4],
        "the conflicted transaction rolled back — nothing changed",
    )
    res_cas = await ingest.correct(
        m_cas,
        CorrectionRequest(
            content="A straight knife after all.",
            client_timestamp=t_c + timedelta(minutes=1),
            expected_detail_id=head_cas[4],
        ),
    )
    check(
        res_cas.superseded_detail_id == head_cas[4],
        "a matching expected_detail_id proceeds",
    )

    # ------------------------------------------------------------------ #
    print("\n[7] Loud errors + route pass-through")
    try:
        await ingest.correct(
            uuid4(), CorrectionRequest(content="x", client_timestamp=t_c)
        )
        fail("unknown memory", "no exception raised")
    except UnknownMemoryError:
        ok("unknown memory_id raises (404 at the route)")
    try:
        await ingest.correct(
            m_cas, CorrectionRequest(content="   ", client_timestamp=t_c)
        )
        fail("whitespace content", "no exception raised")
    except ValueError:
        ok("whitespace-only content raises (422 at the route)")

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
        transport=transport, base_url="http://localhost"
    ) as client:
        payload = json.loads(
            CorrectionRequest(
                content="A knife, and a fair price too.",
                client_timestamp=t_c + timedelta(minutes=2),
            ).model_dump_json()
        )
        response = await client.post(f"/v1/memories/{m_cas}/correction", json=payload)
        check(response.status_code == 200, "route returned 200")
        check(
            response.json() == json.loads(capturing.last.model_dump_json()),
            "route JSON is exactly the serialized CorrectionResult",
        )
        r404 = await client.post(f"/v1/memories/{uuid4()}/correction", json=payload)
        check(r404.status_code == 404, "unknown memory -> 404")
        stale_payload = dict(payload, expected_detail_id=str(uuid4()))
        r409 = await client.post(f"/v1/memories/{m_cas}/correction", json=stale_payload)
        check(r409.status_code == 409, "stale expected_detail_id -> 409")
        blank_payload = dict(payload, content="   ")
        r422 = await client.post(f"/v1/memories/{m_cas}/correction", json=blank_payload)
        check(r422.status_code == 422, "whitespace-only content -> 422")

    # ------------------------------------------------------------------ #
    print("\n[8] Session-runner :correct rides the session's effective time")
    runner = await SessionRunner.create(
        agent,
        settings=settings,
        providers=fake_providers(),
        pool=pool,
        phase_tag="corr-walker",
    )
    runner.as_of = t_c + timedelta(days=2)
    m_well = await seed_memory(ingest, agent, T_WELL, t_c)
    await runner.correct(m_well, "The well never ran dry; the pump jammed.")
    head_well = (await chain(pool, m_well))[-1]
    check(
        head_well[0] == "authorial_correction" and head_well[2] == runner.as_of,
        ":correct's t_c is the session's effective time (as_of under time travel)",
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
