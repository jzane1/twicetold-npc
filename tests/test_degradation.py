"""Degradation cases (docs\\test-suite.md): every ruled ladder row,
asserted structurally. Marked `nlp` where the scenario CALLS the write pass
at the service level; the retrieval/gate/dialogue rows are unmarked.

The escalation failure case asserts the ruled SOFT-DEGRADE behavior (ruled
2026-07-22, retiring the temporary 2026-07-13 fail-loud hard-stop): a
gist-escalation double failure proceeds with the base NLP-pass gist and sets
escalation_failed = true, never a lost write.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import (
    GATE_CONFIG,
    NOW,
    V1_CONFIG,
    by_id,
    drain_turn,
    item_ids,
    run_structural,
)

from app.schemas import DialogueInitRequest, ObserveEvent

T_OBS = "Mara sharpened my blade at the forge while John watched."
T_BRIDGE = (
    "The miller raised his toll at the bridge and the carters grumbled "
    "about the price of crossing all week."
)
T_FERRY = T_BRIDGE + " Aldous waited by the far bank."
T_QUARRY = (
    "Flood water filled the eastern quarry pits and the winch ropes "
    "rotted where they hung."
)

FALLBACK_LINE = "[fallback] The keeper stares into the ford."
DIALOGUE_CONFIG = {
    **V1_CONFIG,
    "dialogue_fallback_line": FALLBACK_LINE,
}


def observe(agent_id, **overrides) -> ObserveEvent:
    base = dict(
        agent_id=agent_id,
        observation_text=T_OBS,
        phase_tag="suite",
        client_timestamp=NOW,
        provenance="lived",
    )
    base.update(overrides)
    return ObserveEvent(**base)


def read_request(agent_id, **overrides) -> DialogueInitRequest:
    base = dict(agent_id=agent_id, query_text=T_OBS, as_of=NOW)
    base.update(overrides)
    return DialogueInitRequest(**base)


@pytest.mark.nlp
def test_scoring_failure_still_lands(scene):
    """Importance-scorer failure: the write lands with neutral importance
    and scoring_failed = true — never rejected."""

    async def scenario(ctx):
        from app.providers import FailingWriteProvider

        agent = await ctx.make_agent("g-scoring", V1_CONFIG)
        degraded = await ctx.ingest(write=FailingWriteProvider()).ingest_observation(
            observe(agent)
        )
        row = await ctx.fetchrow(
            "SELECT importance_raw, scoring_failed FROM memories WHERE memory_id = %s",
            degraded.memory_id,
        )
        assert row is not None
        assert abs(row[0] - 0.5) < 1e-6 and row[1] is True

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_unknown_decay_class_lands_flagged(scene):
    """An unknown decay_class label lands with the agent's default class and
    decay_class_unknown = true (ruled 2026-07-13); a known label is
    unflagged."""

    async def scenario(ctx):
        agent = await ctx.make_agent("g-decay", V1_CONFIG)
        ingest = ctx.ingest()
        unknown = await ingest.ingest_observation(
            observe(agent, decay_class="bogus-label")
        )
        row = await ctx.fetchrow(
            "SELECT decay_class, decay_class_unknown FROM memories "
            "WHERE memory_id = %s",
            unknown.memory_id,
        )
        assert row == ("episodic", True)
        known = await ingest.ingest_observation(observe(agent, decay_class="semantic"))
        assert (known.decay_class, known.decay_class_unknown) == ("semantic", False)

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_observe_embed_failure_lands_null(scene):
    """Embedding failure at observe: the write lands; the queryable signal
    is the live fact head's NULL embedding (freeze ruling 2026-07-18); the
    payload carries embedding_failed; the row is vector-unreachable but
    rides the degraded path."""

    async def scenario(ctx):
        from conftest import embed_text
        from app import db
        from app.providers import FailingEmbeddingProvider

        agent = await ctx.make_agent("g-embed", V1_CONFIG)
        failed = await ctx.ingest(
            embedding=FailingEmbeddingProvider()
        ).ingest_observation(observe(agent))
        assert failed.embedding_failed is True
        row = await ctx.fetchrow(
            "SELECT embedding IS NULL FROM memory_fact_versions "
            "WHERE memory_id = %s AND invalid_at IS NULL",
            failed.memory_id,
        )
        assert row[0] is True
        probe = embed_text(T_OBS)
        vector_rows = await db.fetch_vector_candidates(ctx.pool, agent, probe, 10)
        assert failed.memory_id not in {r.memory_id for r in vector_rows}
        degraded_rows = await db.fetch_live_candidates(ctx.pool, agent)
        assert failed.memory_id in {r.memory_id for r in degraded_rows}

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_correction_embed_failure_all_or_nothing(scene):
    """Embedding failure during an authorial correction: ALL-OR-NOTHING
    (ruled 2026-07-18) — nothing written on either chain, cache intact,
    loud error. The deliberate contrast with observe's land-with-NULL."""

    async def scenario(ctx):
        from app import db
        from app.ingest import CorrectionEmbedFailedError
        from app.providers import FailingEmbeddingProvider
        from app.schemas import CorrectionRequest

        agent = await ctx.make_agent("g-correct-embed", V1_CONFIG)
        ingest = ctx.ingest()
        seeded = await ingest.ingest_observation(observe(agent))
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached")
        chain_before = await ctx.chain(m)
        facts_before = await ctx.fact_chain(m)

        failing = ctx.ingest(embedding=FailingEmbeddingProvider())
        with pytest.raises(CorrectionEmbedFailedError):
            await failing.correct(
                m,
                CorrectionRequest(
                    content="A corrected telling that must not land.",
                    client_timestamp=NOW + timedelta(hours=1),
                ),
            )
        assert await ctx.chain(m) == chain_before
        assert await ctx.fact_chain(m) == facts_before
        assert await ctx.cache_rows(m) == {"vhash|b1": "cached"}

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_escalation_failure_soft_degrades(scene):
    """Escalation fails twice => SOFT-DEGRADE (ruled 2026-07-22): the write
    proceeds with the base NLP-pass gist, one memories row lands, and
    escalation_failed = true. Structurally assertable: row present + flag set,
    never a lost write."""

    async def scenario(ctx):
        from app.providers import FailingEscalationProvider

        agent = await ctx.make_agent("g-escdegrade", V1_CONFIG)
        failing = FailingEscalationProvider()
        service = ctx.ingest(escalation=failing)
        count_sql = "SELECT count(*) FROM memories WHERE agent_id = %s"
        before = (await ctx.fetchrow(count_sql, agent))[0]
        result = await service.ingest_observation(observe(agent))
        assert failing.calls == 2  # retried exactly once, then degraded
        assert result.escalation_failed is True  # flagged on the wire
        assert (await ctx.fetchrow(count_sql, agent))[0] == before + 1  # not lost
        row = await ctx.fetchrow(
            "SELECT escalation_failed FROM memories WHERE memory_id = %s",
            result.memory_id,
        )
        assert row[0] is True  # persisted to the dedicated column (migration 005)

    run_structural(scene, scenario)


def test_thin_gist_trigger_pure():
    """The thin_gist span-floor trigger (ruled 2026-07-23): a base NLP pass
    with fewer gist spans than escalation_min_base_spans escalates regardless
    of importance — protecting reconstruction's fixed constraint (measured
    2026-07-23: 16/80 realistic observes otherwise landed with ZERO gist
    spans). Pure function over production SERVICE_DEFAULTS — no DB, no NLP
    models, keyless."""
    from app.config import SERVICE_DEFAULTS
    from app.nlp import TRIGGER_THIN_GIST, NlpResult, evaluate_triggers
    from app.providers import GistSpanCandidate

    knobs = {
        key: SERVICE_DEFAULTS[key]  # production values, deliberately unpinned
        for key in (
            "escalation_importance_threshold",
            "escalation_affect_threshold",
            "escalation_min_base_spans",
        )
    }
    empty = NlpResult(
        spans=[],
        novel_components=[],
        entities=[],
        affect_valence=None,
        affect_arousal=None,
        affect_detail=None,
    )
    # zero spans + sub-threshold importance: thin_gist fires ALONE at the
    # shipped defaults — the pre-ruling write path landed this observe with
    # an empty gist and no escalation.
    assert evaluate_triggers(empty, 0.1, knobs) == [TRIGGER_THIN_GIST]
    # knob 0.0 is the kill-switch (span counts are never negative).
    assert (
        evaluate_triggers(empty, 0.1, {**knobs, "escalation_min_base_spans": 0.0}) == []
    )
    # the floor compares the span COUNT: one span is quiet at the shipped
    # floor (1.0) and fires at a raised floor (2.0).
    one = NlpResult(
        spans=[GistSpanCandidate(start_char=0, end_char=4)],
        novel_components=[],
        entities=[],
        affect_valence=None,
        affect_arousal=None,
        affect_detail=None,
    )
    assert evaluate_triggers(one, 0.1, knobs) == []
    assert TRIGGER_THIN_GIST in evaluate_triggers(
        one, 0.1, {**knobs, "escalation_min_base_spans": 2.0}
    )
    # the shipped default IS the gist floor (ruled 2026-07-23).
    assert SERVICE_DEFAULTS["escalation_min_base_spans"] == 1.0


def test_retrieval_fail_quiet_fallback(scene):
    """Query-embedding failure at read time (ruled ladder row): degraded
    flag + reason, every relevance null, score = recency x importance_norm,
    still ranked and non-empty, NULL-embedding rows reachable, no tokens."""

    async def scenario(ctx):
        from app.providers import FailingEmbeddingProvider

        agent = await ctx.make_agent("g-readfall", V1_CONFIG)
        await ctx.seed(agent, T_OBS, NOW - timedelta(hours=1))
        await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=2))
        null_row = await ctx.seed(
            agent, T_QUARRY, NOW - timedelta(hours=3), embedding=None
        )
        degraded = ctx.retrieval(embedding=FailingEmbeddingProvider())
        r = await degraded.retrieve_dialogue_init(read_request(agent))
        instr = r.instrumentation
        assert instr.degraded is True and bool(instr.degraded_reason)
        assert len(r.items) == 3
        assert null_row.memory_id in by_id(r)
        for item in r.items:
            assert item.relevance is None
            assert item.score == item.recency * item.importance_norm
        assert all(
            r.items[i].score >= r.items[i + 1].score for i in range(len(r.items) - 1)
        )
        assert instr.embedding_tokens == 0

    run_structural(scene, scenario)


def test_gate_degradation_ladder(scene):
    """The gate's ruled ladder: embeddings down => entity-only lexical rung
    off the fact-head GIN; no coverage basis => novelty-only; both out =>
    gate closed, loaded set served, fail-quiet; foreign loaded IDs drop out
    of the join, counted, turn intact."""

    async def scenario(ctx):
        from uuid import uuid4

        from app.gate import (
            GATE_RUNG_CLOSED,
            GATE_RUNG_ENTITY_ONLY,
            GATE_RUNG_NOVELTY_ONLY,
            GATE_SIGNAL_ENTITY,
            GATE_SIGNAL_NOVELTY,
        )
        from app.providers import FailingEmbeddingProvider

        agent = await ctx.make_agent(
            "g-ladder",
            GATE_CONFIG,
            (("Mara", ["the blacksmith"]), ("Aldous", ["the ferryman"])),
        )
        chapel = await ctx.seed(
            agent,
            "Mara left the chapel before the harvest bells rang out.",
            NOW - timedelta(hours=3),
            entities=["Mara"],
        )
        bridge = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=2))
        ferry = await ctx.seed(
            agent, T_FERRY, NOW - timedelta(minutes=10), entities=["Aldous"]
        )
        # The coverage basis is the LOADED items' fact-head entities: the
        # chapel row supplies one ("Mara") while "Aldous" stays uncovered.
        loaded = [chapel.memory_id, bridge.memory_id]

        def gate_request(query, *, loaded_ids):
            return DialogueInitRequest(
                agent_id=agent,
                query_text=query,
                as_of=NOW,
                scene_started_at=NOW,
                loaded_memory_ids=loaded_ids,
            )

        failing = ctx.retrieval(embedding=FailingEmbeddingProvider())
        entity_only = await failing.retrieve_dialogue_init(
            gate_request(T_FERRY, loaded_ids=loaded)
        )
        g = entity_only.instrumentation.gate
        assert g.degraded_rung == GATE_RUNG_ENTITY_ONLY
        assert g.signals_fired == [GATE_SIGNAL_ENTITY]
        assert entity_only.instrumentation.degraded
        fetched = [i for i in entity_only.items if i.gate_fetched]
        assert any(i.memory_id == ferry.memory_id for i in fetched)
        assert all(i.relevance is None for i in fetched)
        assert g.novelty_min_distance is None

        # Loaded rows carry no entities => no coverage basis: novelty-only.
        bare_loaded = [bridge.memory_id]
        retrieval = ctx.retrieval()
        no_basis = await retrieval.retrieve_dialogue_init(
            gate_request(T_QUARRY, loaded_ids=bare_loaded)
        )
        g = no_basis.instrumentation.gate
        assert g.degraded_rung == GATE_RUNG_NOVELTY_ONLY
        assert g.signals_fired == [GATE_SIGNAL_NOVELTY]

        # Both signals out: embeddings down + no coverage basis => closed.
        both_out = await failing.retrieve_dialogue_init(
            gate_request(T_QUARRY, loaded_ids=bare_loaded)
        )
        g = both_out.instrumentation.gate
        assert g.degraded_rung == GATE_RUNG_CLOSED and not g.fired
        assert both_out.instrumentation.degraded
        assert set(item_ids(both_out)) == set(bare_loaded)

        foreign = await retrieval.retrieve_dialogue_init(
            gate_request(T_BRIDGE, loaded_ids=loaded + [uuid4()])
        )
        assert foreign.instrumentation.gate.loaded_missing_count == 1
        assert set(item_ids(foreign)) == set(loaded)

    run_structural(scene, scenario)


def test_dialogue_never_blank(scene):
    """The dialogue seam's never-blank ladder (re-shaped by A1 2026-08-04 —
    prose is the turn's only leg). Prose failure before the first chunk =>
    the fallback line + degraded flag, with the served view still riding the
    result (retrieval is unaffected by the prose leg). A mid-stream prose
    drop KEEPS the partial (ruled 2026-07-21). The happy row streams
    prose == content, not degraded. A dialogue turn persists nothing:
    `agents.reputation` stays NULL throughout."""

    async def scenario(ctx):
        from app.dialogue import DialogueService
        from app.providers import (
            FailingProseProvider,
            MidStreamDropProseProvider,
        )
        from app.schemas import DialogueTurnRequest

        agent = await ctx.make_agent("g-dialogue", DIALOGUE_CONFIG)
        await ctx.seed(agent, T_OBS, NOW - timedelta(hours=1))
        retrieval = ctx.retrieval()

        def service(*, dialogue=None) -> DialogueService:
            overrides = {}
            if dialogue is not None:
                overrides["dialogue"] = dialogue
            return DialogueService(
                ctx.pool, ctx.providers(**overrides), ctx.settings, retrieval
            )

        def turn():
            return DialogueTurnRequest(
                agent_id=agent,
                utterance="Tell me about the forge.",
                as_of=NOW,
            )

        # (1) happy row: streamed prose == content, not degraded.
        prose_h, r_happy = await drain_turn(service().run_dialogue_turn(turn()))
        assert bool(prose_h) and r_happy.content == prose_h
        assert r_happy.content != FALLBACK_LINE
        assert not r_happy.instrumentation.degraded

        # (2) prose fails BEFORE the first chunk -> fallback line + degraded;
        # the served view still rides the result (retrieval unaffected).
        _p2, r_pfail = await drain_turn(
            service(dialogue=FailingProseProvider()).run_dialogue_turn(turn())
        )
        assert r_pfail.content == FALLBACK_LINE
        assert r_pfail.instrumentation.degraded
        assert "prose call failed" in r_pfail.instrumentation.degraded_reason
        assert [i.memory_id for i in r_pfail.items]
        assert [v.memory_id for v in r_pfail.dialogue_view]

        # (3) prose DROPS mid-stream -> keep the partial (ruled 2026-07-21).
        prose_d, r_drop = await drain_turn(
            service(dialogue=MidStreamDropProseProvider()).run_dialogue_turn(turn())
        )
        assert prose_d == "partial prose" and r_drop.content == prose_d
        assert r_drop.content != FALLBACK_LINE
        assert r_drop.instrumentation.degraded
        assert "mid-stream" in r_drop.instrumentation.degraded_reason

        # A turn persists nothing (A1): the reputation column was never
        # written — not at provisioning, not by any of the turns above.
        rep_row = await ctx.fetchrow(
            "SELECT reputation FROM agents WHERE agent_id = %s", agent
        )
        assert rep_row[0] is None

    run_structural(scene, scenario)


def test_reconstruction_fail_quiet(scene):
    """Reconstruction-call failure and malformed batched output both degrade
    soft: live heads served under honest read_mode, nothing written, no
    cache row pinned, token spend accounted on the malformed path."""

    async def scenario(ctx):
        from conftest import RECON_CONFIG
        from app.providers import (
            FailingReconstructionProvider,
            MalformedReconstructionProvider,
        )

        agent = await ctx.make_agent("g-recon", RECON_CONFIG)
        old = await ctx.seed(
            agent, T_BRIDGE, NOW - timedelta(days=10), decay_class="semantic"
        )
        failing = ctx.retrieval(reconstruction=FailingReconstructionProvider())
        r = await failing.retrieve_dialogue_init(
            read_request(agent, query_text=T_BRIDGE, scene_started_at=NOW)
        )
        assert r.instrumentation.degraded
        assert "reconstruction call failed" in (r.instrumentation.degraded_reason or "")
        chain = await ctx.chain(old.memory_id)
        assert len(chain) == 1
        item = by_id(r)[old.memory_id]
        assert item.read_mode == "verbatim" and item.content == chain[0][1]
        assert await ctx.cache_rows(old.memory_id) == {}

        malformed = ctx.retrieval(reconstruction=MalformedReconstructionProvider())
        r_mal = await malformed.retrieve_dialogue_init(
            read_request(agent, query_text=T_BRIDGE, scene_started_at=NOW)
        )
        assert r_mal.instrumentation.degraded
        assert r_mal.instrumentation.reconstruction_input_tokens == 7
        assert len(await ctx.chain(old.memory_id)) == 1

    run_structural(scene, scenario)


def test_correction_nlp_failure_all_or_nothing(scene, monkeypatch):
    """NER failure during an authorial correction: ALL-OR-NOTHING fail-loud
    (ruled 2026-07-19 with the gate build, taking the embed precedent's
    shape) — nothing written on either chain, cache intact,
    CorrectionNlpFailedError, and the route maps it to 502.

    Added 2026-07-28 (audit): this was a ruled degradation path with no test
    anywhere and no row in the spec's degradation list, while its sibling
    CorrectionEmbedFailedError had both. The failure it models is a
    broken or missing spaCy install, so it is injected at
    `nlp.extract_entities` — the correction verb's only NLP call.

    Deliberately UNMARKED: seeding is db-layer and the NER call is patched
    out, so the loaders never load and this rides the Stop-hook subset —
    which previously carried no correction-failure coverage at all."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module
        from app import db, nlp
        from app.ingest import CorrectionNlpFailedError
        from app.schemas import CorrectionRequest

        agent = await ctx.make_agent("g-correct-ner", V1_CONFIG)
        seeded = await ctx.seed(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached")
        chain_before = await ctx.chain(m)
        facts_before = await ctx.fact_chain(m)

        def _broken(_text: str):
            raise RuntimeError("injected NER failure (broken spaCy install)")

        monkeypatch.setattr(nlp, "extract_entities", _broken)

        request = CorrectionRequest(
            content="A corrected telling that must not land.",
            client_timestamp=NOW + timedelta(hours=1),
        )
        with pytest.raises(CorrectionNlpFailedError):
            await ctx.ingest().correct(m, request)

        # Nothing written on EITHER chain, and the cache is untouched — the
        # NER runs before the embed, before the transaction ever opens.
        assert await ctx.chain(m) == chain_before
        assert await ctx.fact_chain(m) == facts_before
        assert await ctx.cache_rows(m) == {"vhash|b1": "cached"}

        # The route half: 502, the embed-failure precedent.
        api_module.app.state.service = ctx.ingest()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.post(
                f"/v1/memories/{m}/correction",
                json={
                    "content": "A corrected telling that must not land.",
                    "client_timestamp": (NOW + timedelta(hours=1)).isoformat(),
                },
            )
        assert resp.status_code == 502
        assert await ctx.chain(m) == chain_before  # still nothing written

    run_structural(scene, scenario)


def test_typology_clamp_vocabulary_and_semantics():
    """The 2026-08-12 clamp ruling (a real write call echoed the prompt's
    option syntax back as `observed|told` and the DB check killed the whole
    request): in-vocabulary values pass through; a malformed value salvages
    the FIRST vocabulary member it contains; a value containing none falls
    to None — ingest's existing undeclared-typology default path. The
    vocabulary constant must match the wire Literal and the fake provider
    (migration 001's check mirrors it by the applied-migration immutability
    rule)."""
    from typing import get_args

    from app.providers import (
        TYPOLOGY_VOCABULARY,
        FakeWriteProvider,
        clamp_typology,
    )
    from app.schemas import Typology

    assert TYPOLOGY_VOCABULARY == tuple(get_args(Typology))
    assert FakeWriteProvider.TYPOLOGIES == TYPOLOGY_VOCABULARY
    for member in TYPOLOGY_VOCABULARY:
        assert clamp_typology(member) == member
    assert clamp_typology("observed|told") == "observed"  # the real crash value
    assert clamp_typology("told|observed") == "told"  # first member wins
    assert clamp_typology("Reflected.") == "reflected"  # case + punctuation
    assert clamp_typology("one of observed|told") == "observed"
    assert clamp_typology("hearsay") is None
    assert clamp_typology("") is None
