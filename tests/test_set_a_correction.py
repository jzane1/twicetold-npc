"""Set A — correction-override, authorial pair + fact chain
(docs\\test-suite.md; replace model ruled 2026-07-12; fact-level build
2026-07-18). Structural pairs keyed on write_cause — no fixture modes.

Chain and rank mechanics assert at the db layer through the real
`apply_authorial_correction` (unmarked — the verb's NER merge lives at the
service level and is exercised by the marked route test + Set D's
entities-follow-correction pair). The distance-0 rank mechanic is a FIXTURE
property of the pure fake embedding (probe text == stored basis => cosine
distance ~0); production uses real embeddings. Rank asserts at the db layer,
where order is pure distance (a service-level rank assertion would hang on
fixture importance — the fact-level spec's ruling).

The diegetic pair lands when the dissonance mechanism ships (out of scope).
"""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import NOW, V1_CONFIG, by_id, embed_text, run_structural

from app import db
from app.schemas import DialogueInitRequest

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
T_FRESH = "Mara sharpened my blade at the forge this morning."
CORRECTED_FRESH = "John sharpened my blade at the forge; Mara only watched."

T_C = NOW + timedelta(hours=1)


def request(agent_id, **overrides) -> DialogueInitRequest:
    base = dict(agent_id=agent_id, query_text=T_EVENT, as_of=NOW)
    base.update(overrides)
    return DialogueInitRequest(**base)


async def _correct(ctx, memory_id, content, *, valid_at=T_C, **kw):
    return await db.apply_authorial_correction(
        ctx.pool,
        memory_id=memory_id,
        content=content,
        valid_at=valid_at,
        embedding=embed_text(content),
        **kw,
    )


def test_replace_model_chain_shape_and_eviction(scene):
    """One transaction: telling head superseded at t_c, exactly one new
    `authorial_correction` head with operator text byte-verbatim; the fact
    head follows (basis + embedding + entities); every cache row evicted;
    no `corrections` row; observation_text and gist spans untouched."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-chain", V1_CONFIG)
        seeded = await ctx.seed(
            agent,
            T_EVENT,
            NOW - timedelta(days=2),
            entities=["Marta"],
            spans=((0, 25),),
        )
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached one")
        await db.insert_cache_row(ctx.pool, m, "vhash|b2", "cached two")
        obs_before = await ctx.fetchrow(
            "SELECT observation_text FROM memories WHERE memory_id = %s", m
        )
        spans_before = await ctx.fetchall(
            "SELECT start_char, end_char FROM memory_gist_spans "
            "WHERE memory_id = %s ORDER BY start_char",
            m,
        )

        result = await _correct(ctx, m, CORRECTED, entities=["the sexton"])
        assert isinstance(result, db.CorrectionApplied)

        chain = await ctx.chain(m)
        head, superseded = chain[-1], chain[0]
        assert len(chain) == 2
        assert head[0] == "authorial_correction"
        assert head[1] == CORRECTED
        assert head[2] == T_C and head[3] is None
        assert superseded[3] == T_C
        assert len([r for r in chain if r[3] is None]) == 1
        assert result.detail_id == head[4]
        assert result.superseded_detail_id == superseded[4]

        assert result.evicted_cache_rows == 2
        assert await ctx.cache_rows(m) == {}
        assert await ctx.fetchall("SELECT 1 FROM corrections") == []

        facts = await ctx.fact_chain(m)
        assert len(facts) == 2
        assert facts[0][0] == "original" and facts[0][3] == T_C
        assert facts[0][5] == ["Marta"]  # superseded fact keeps ITS entities
        assert facts[1][0] == "authorial_correction"
        assert facts[1][1] == CORRECTED and facts[1][3] is None
        assert facts[1][5] == ["the sexton"]
        assert result.fact_version_id == facts[1][4]
        assert result.superseded_fact_version_id == facts[0][4]

        # The superseded fact row still carries the ORIGINAL embedding; the
        # corrected head carries the corrected one (distance-as-structure).
        from pgvector import Vector

        dists = await ctx.fetchrow(
            "SELECT (SELECT embedding <=> %s FROM memory_fact_versions "
            "        WHERE fact_version_id = %s), "
            "       (SELECT embedding <=> %s FROM memory_fact_versions "
            "        WHERE fact_version_id = %s)",
            Vector(embed_text(T_EVENT)),
            facts[0][4],
            Vector(embed_text(CORRECTED)),
            facts[1][4],
        )
        assert dists[0] < 1e-6 and dists[1] < 1e-6

        assert (
            await ctx.fetchrow(
                "SELECT observation_text FROM memories WHERE memory_id = %s", m
            )
            == obs_before
        )
        assert (
            await ctx.fetchall(
                "SELECT start_char, end_char FROM memory_gist_spans "
                "WHERE memory_id = %s ORDER BY start_char",
                m,
            )
            == spans_before
        )

    run_structural(scene, scenario)


def test_bitemporal_windows_re_derive_both_chains(scene):
    """Stored bi-temporal coherence (re-ruled 2026-07-18): windowed SQL
    re-derives which telling and which fact were live at any instant —
    no gap, no overlap, on both chains."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-window", V1_CONFIG)
        m = (
            await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2), entities=["Marta"])
        ).memory_id
        await _correct(ctx, m, CORRECTED, entities=["the sexton"])
        just_before = T_C - timedelta(seconds=1)
        for table in ("memory_details", "memory_fact_versions"):
            past = await ctx.fetchall(
                f"SELECT write_cause FROM {table} WHERE memory_id = %s "
                "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
                m,
                just_before,
                just_before,
            )
            assert [row[0] for row in past] == ["original"], table
            at_tc = await ctx.fetchall(
                f"SELECT write_cause FROM {table} WHERE memory_id = %s "
                "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
                m,
                T_C,
                T_C,
            )
            assert [row[0] for row in at_tc] == ["authorial_correction"], table

    run_structural(scene, scenario)


def test_midscene_correction_changes_serving(scene):
    """The amended within-scene invariant's sanctioned cause: same scene,
    same as_of — the read after the correction serves the corrected head
    immediately; the memory stays present in candidates."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-midscene", V1_CONFIG)
        m = (await ctx.seed(agent, T_FRESH, NOW - timedelta(hours=1))).memory_id
        retrieval = ctx.retrieval()
        first = await retrieval.retrieve_dialogue_init(
            request(agent, query_text=T_FRESH)
        )
        again = await retrieval.retrieve_dialogue_init(
            request(agent, query_text=T_FRESH)
        )
        a, a2 = by_id(first)[m], by_id(again)[m]
        assert a.content == a2.content  # byte-identical absent a correction
        assert a.read_mode == "verbatim"

        result = await _correct(ctx, m, CORRECTED_FRESH, valid_at=NOW)
        after = await retrieval.retrieve_dialogue_init(
            request(agent, query_text=T_FRESH)
        )
        b = by_id(after)[m]
        assert b.content == CORRECTED_FRESH
        assert b.content != a.content
        assert b.read_mode == "verbatim"
        assert b.detail_id == result.detail_id

    run_structural(scene, scenario)


def test_rank_follows_the_fix_at_the_db_layer(scene):
    """Retrieval follows the fix: before the correction the corrected-text
    probe sits bounded away from the memory; after it, the memory ranks
    FIRST with distance ~0 (db layer — order is pure distance)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-rank", V1_CONFIG)
        m_event = (await ctx.seed(agent, T_EVENT, NOW - timedelta(hours=3))).memory_id
        await ctx.seed(agent, T_DECOY, NOW - timedelta(hours=2))
        probe = embed_text(CORRECTED)

        before = await db.fetch_vector_candidates(ctx.pool, agent, probe, 10)
        before_by_id = {row.memory_id: row for row in before}
        assert m_event in before_by_id
        assert before_by_id[m_event].distance > 1e-3

        await _correct(ctx, m_event, CORRECTED, valid_at=NOW)
        after = await db.fetch_vector_candidates(ctx.pool, agent, probe, 10)
        assert after[0].memory_id == m_event
        assert after[0].distance < 1e-6

        # Service layer: presence + relevance ~ 1.0 (never rank — fixture
        # importance would carry a rank assertion, not the mechanism).
        served = by_id(
            await ctx.retrieval().retrieve_dialogue_init(
                request(agent, query_text=CORRECTED)
            )
        )
        assert m_event in served
        assert served[m_event].relevance is not None
        assert served[m_event].relevance > 0.999

    run_structural(scene, scenario)


def test_constraint_follows_the_anchor_pure():
    """Post-correction reconstruction takes the corrected head as its FIXED
    constraint (ruled 2026-07-17) — pure prompt-assembly assertion, no db,
    no model."""
    from app.reconstruction import (
        assemble_reconstruction_prompt,
        build_reconstruction_item,
        split_gist_detail,
        thin_detail,
    )

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
    assert item_o.gist == gist
    assert item_o.thinned_detail == thin_detail(segments, 0.5)

    src_corrected = db.ReconstructionSource(
        observation_text=obs,
        spans=spans,
        anchor_content=CORRECTED,
        anchor_cause="authorial_correction",
    )
    item_c = build_reconstruction_item("m1", src_corrected, 0.5, "the telling")
    assert item_c.gist == CORRECTED
    assert item_c.thinned_detail == ""  # no observation detail re-injected
    assert build_reconstruction_item("m1", src_corrected, 0.1, "x").gist == CORRECTED

    _, user_content = assemble_reconstruction_prompt("doc", [item_c])
    parsed = json.loads(user_content)
    assert parsed[0]["gist"] == CORRECTED and parsed[0]["detail"] == ""


def test_drift_anchor_resolves_to_corrected_head(scene):
    """The drift anchor is derivable, never a pointer: after the correction
    it resolves to the corrected head with its cause."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-anchor", V1_CONFIG)
        m = (
            await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2), spans=((0, 25),))
        ).memory_id
        sources = await db.fetch_reconstruction_sources(ctx.pool, [m])
        assert sources[m].anchor_cause == "original"
        await _correct(ctx, m, CORRECTED)
        sources = await db.fetch_reconstruction_sources(ctx.pool, [m])
        assert sources[m].anchor_content == CORRECTED
        assert sources[m].anchor_cause == "authorial_correction"

    run_structural(scene, scenario)


def test_cas_stale_head_changes_nothing(scene):
    """Compare-and-swap: a stale expected_detail_id rolls the transaction
    back — no chain row, no fact row, no eviction; a matching one proceeds;
    an unknown memory reports itself."""

    async def scenario(ctx):
        agent = await ctx.make_agent("a-cas", V1_CONFIG)
        m = (await ctx.seed(agent, T_FRESH, NOW - timedelta(hours=1))).memory_id
        head = (await ctx.chain(m))[-1]
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached")

        stale = await _correct(ctx, m, CORRECTED_FRESH, expected_detail_id=uuid4())
        assert stale == "stale_head"
        chain = await ctx.chain(m)
        assert len(chain) == 1
        assert chain[0][3] is None and chain[0][4] == head[4]
        assert len(await ctx.fact_chain(m)) == 1
        assert await ctx.cache_rows(m) == {"vhash|b1": "cached"}

        assert await _correct(ctx, uuid4(), CORRECTED_FRESH) == "unknown_memory"

        applied = await _correct(ctx, m, CORRECTED_FRESH, expected_detail_id=head[4])
        assert isinstance(applied, db.CorrectionApplied)
        assert applied.superseded_detail_id == head[4]

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_correction_route_contract(scene):
    """The operator verb's wire contract through the real service (NER merge
    included): 200 == the serialized CorrectionResult; 404 unknown memory;
    409 stale CAS; 422 whitespace-only content."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module
        from app.schemas import CorrectionRequest

        agent = await ctx.make_agent("a-route", V1_CONFIG)
        ingest = ctx.ingest()
        from app.schemas import ObserveEvent

        seeded = await ingest.ingest_observation(
            ObserveEvent(
                agent_id=agent,
                observation_text=T_EVENT,
                phase_tag="suite",
                client_timestamp=NOW - timedelta(hours=2),
                provenance="lived",
            )
        )
        m = seeded.memory_id

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
                    content=CORRECTED, client_timestamp=T_C
                ).model_dump_json()
            )
            ok = await client.post(f"/v1/memories/{m}/correction", json=payload)
            assert ok.status_code == 200
            assert ok.json() == json.loads(capturing.last.model_dump_json())

            r404 = await client.post(f"/v1/memories/{uuid4()}/correction", json=payload)
            assert r404.status_code == 404

            stale = dict(payload, expected_detail_id=str(uuid4()))
            r409 = await client.post(f"/v1/memories/{m}/correction", json=stale)
            assert r409.status_code == 409

            blank = dict(payload, content="   ")
            r422 = await client.post(f"/v1/memories/{m}/correction", json=blank)
            assert r422.status_code == 422

    run_structural(scene, scenario)
