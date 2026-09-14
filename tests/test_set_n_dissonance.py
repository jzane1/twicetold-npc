"""Set N — dissonance path + diegetic-correction event
(docs\\test-suite.md; docs\\dissonance.md; the eight C4 rulings 2026-08-17).
Structural pairs keyed on write_cause — no fixture modes. The Set A diegetic
pair ("chain intact; new head typed rationalization or update_with_resentment;
correction record present; cache evicted") lands HERE, with the mechanism.

Chain and record mechanics assert at the db layer through the real
`apply_diegetic_correction` (unmarked — no scenario touches the NLP write
pass). The decision formula asserts through the pure functions and the
service seam; the retell prose is never asserted (structural-only rule): the
fake reconstruction provider's output is asserted for presence and
distinctness, never content. Tellings-only by ruling: every scenario that
touches the fact chain asserts it did NOT move.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest
from conftest import NOW, V1_CONFIG, run_structural

from app import db

T_EVENT = (
    "Marta stole the silver chalice from the chapel during the harvest "
    "festival. The sexton swore he saw her leave by the north door."
)
CHALLENGE = (
    "Bram says the chalice was misplaced in the crypt by the sexton himself; "
    "Marta was never in the chapel that night."
)
UPDATE_TELLING = (
    "Fine — the sexton misplaced it in the crypt, they say. Marta was never "
    "there. I still remember the north door."
)
DEFENSE_TELLING = (
    "Bram wasn't even at the festival — the sexton SAW her leave by the "
    "north door, and sextons don't misplace chalices in crypts."
)

T_E = NOW + timedelta(hours=1)


async def _confront(ctx, memory_id, *, verb, content, valid_at=T_E, **kw):
    return await db.apply_diegetic_correction(
        ctx.pool,
        memory_id=memory_id,
        content=content,
        verb=verb,
        valid_at=valid_at,
        **kw,
    )


def test_update_with_resentment_chain_shape_and_eviction(scene):
    """The diegetic pair, update half (Set A criteria): prior head superseded
    at t_e, exactly one live head typed `update_with_resentment`, corrections
    row present (verb + detail_id = the new head + valid_at = t_e), every
    cache row evicted — and the chain PRESERVED: observation_text, gist
    spans, and the whole fact chain byte-untouched (tellings-only ruling)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-update", V1_CONFIG)
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
        facts_before = await ctx.fact_chain(m)
        spans_before = await ctx.fetchall(
            "SELECT start_char, end_char FROM memory_gist_spans "
            "WHERE memory_id = %s ORDER BY start_char",
            m,
        )

        result = await _confront(
            ctx, m, verb="update_with_resentment", content=UPDATE_TELLING
        )
        assert isinstance(result, db.DiegeticCorrectionApplied)

        chain = await ctx.chain(m)
        head, superseded = chain[-1], chain[0]
        assert len(chain) == 2
        assert head[0] == "update_with_resentment"
        assert head[1] == UPDATE_TELLING
        assert head[2] == T_E and head[3] is None
        assert superseded[3] == T_E
        assert len([r for r in chain if r[3] is None]) == 1
        assert result.detail_id == head[4]
        assert result.superseded_detail_id == superseded[4]

        assert result.evicted_cache_rows == 2
        assert await ctx.cache_rows(m) == {}

        corrections = await ctx.fetchall(
            "SELECT memory_id, detail_id, verb, source_event, valid_at "
            "FROM corrections",
        )
        assert len(corrections) == 1
        assert corrections[0][0] == m
        assert corrections[0][1] == result.detail_id
        assert corrections[0][2] == "update_with_resentment"
        assert corrections[0][3] is None
        assert corrections[0][4] == T_E

        assert (
            await ctx.fetchrow(
                "SELECT observation_text FROM memories WHERE memory_id = %s", m
            )
            == obs_before
        )
        assert await ctx.fact_chain(m) == facts_before
        assert (
            await ctx.fetchall(
                "SELECT start_char, end_char FROM memory_gist_spans "
                "WHERE memory_id = %s ORDER BY start_char",
                m,
            )
            == spans_before
        )

    run_structural(scene, scenario)


def test_rationalization_chain_shape_and_source_event_roundtrip(scene):
    """The diegetic pair, defense half — same skeleton, verb forked; the
    client's `source_event` payload round-trips the jsonb column verbatim."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-rational", V1_CONFIG)
        seeded = await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))
        m = seeded.memory_id
        payload = {"scene": "tavern", "speaker": "Bram", "beat": 3}

        result = await _confront(
            ctx,
            m,
            verb="rationalization",
            content=DEFENSE_TELLING,
            source_event=payload,
        )
        assert isinstance(result, db.DiegeticCorrectionApplied)

        chain = await ctx.chain(m)
        assert len(chain) == 2
        assert chain[-1][0] == "rationalization"
        assert chain[-1][1] == DEFENSE_TELLING
        assert chain[-1][3] is None and chain[0][3] == T_E

        row = await ctx.fetchrow(
            "SELECT verb, source_event, detail_id FROM corrections "
            "WHERE memory_id = %s",
            m,
        )
        assert row[0] == "rationalization"
        assert row[1] == payload
        assert row[2] == result.detail_id

    run_structural(scene, scenario)


def test_coherent_timeline_under_windowed_sql(scene):
    """Prior head invalid_at == new head valid_at == corrections.valid_at ==
    t_e: windowed SQL re-derives the pre-event telling with no gap or overlap
    at the boundary (the stored-coherence precedent)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-window", V1_CONFIG)
        seeded = await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))
        m = seeded.memory_id
        await _confront(ctx, m, verb="update_with_resentment", content=UPDATE_TELLING)

        async def live_at(t):
            rows = await ctx.fetchall(
                "SELECT content FROM memory_details WHERE memory_id = %s "
                "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
                m,
                t,
                t,
            )
            return [r[0] for r in rows]

        before = await live_at(T_E - timedelta(seconds=1))
        at = await live_at(T_E)
        assert before == [f"[suite seed] {T_EVENT}"]
        assert at == [UPDATE_TELLING]

        stamps = await ctx.fetchrow(
            "SELECT d_old.invalid_at, d_new.valid_at, c.valid_at "
            "FROM corrections c "
            "JOIN memory_details d_new ON d_new.detail_id = c.detail_id "
            "JOIN memory_details d_old ON d_old.memory_id = c.memory_id "
            "AND d_old.invalid_at IS NOT NULL "
            "WHERE c.memory_id = %s",
            m,
        )
        assert stamps[0] == stamps[1] == stamps[2] == T_E

    run_structural(scene, scenario)


def test_cas_stale_head_rolls_back_everything(scene):
    """An `expected_detail_id` that no longer names the live head reports
    "stale_head" and changes NOTHING: no new head, no corrections row, cache
    intact (rollback proven by row counts)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-cas", V1_CONFIG)
        seeded = await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached one")

        result = await _confront(
            ctx,
            m,
            verb="rationalization",
            content=DEFENSE_TELLING,
            expected_detail_id=uuid4(),
        )
        assert result == "stale_head"

        chain = await ctx.chain(m)
        assert len(chain) == 1 and chain[0][3] is None
        assert await ctx.fetchall("SELECT 1 FROM corrections") == []
        assert len(await ctx.cache_rows(m)) == 1

    run_structural(scene, scenario)


def test_unknown_memory(scene):
    """No live head means no such memory — nothing written."""

    async def scenario(ctx):
        await ctx.make_agent("n-unknown", V1_CONFIG)
        result = await _confront(
            ctx, uuid4(), verb="rationalization", content=DEFENSE_TELLING
        )
        assert result == "unknown_memory"
        assert await ctx.fetchall("SELECT 1 FROM corrections") == []

    run_structural(scene, scenario)


def test_pinned_memory_proceeds_and_inherits_pin(scene):
    """Both correction verbs outrank pin (§8 final ruling): the event
    proceeds on a pinned memory, `memories.pinned` is untouched, and the new
    head is the frozen head pin now protects."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-pin", V1_CONFIG)
        seeded = await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2), pinned=True)
        m = seeded.memory_id

        result = await _confront(
            ctx, m, verb="update_with_resentment", content=UPDATE_TELLING
        )
        assert isinstance(result, db.DiegeticCorrectionApplied)
        pinned = await ctx.fetchrow(
            "SELECT pinned FROM memories WHERE memory_id = %s", m
        )
        assert pinned == (True,)
        chain = await ctx.chain(m)
        assert chain[-1][0] == "update_with_resentment" and chain[-1][3] is None

    run_structural(scene, scenario)


def test_anchor_semantics_update_reanchors_rationalization_never(scene):
    """The drift-anchor rule the schema has carried since the authorial
    build: an `update_with_resentment` head IS the anchor; a
    `rationalization` head never re-anchors — the anchor stays `original`
    ("the story has set" crystallization rests on this)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-anchor", V1_CONFIG)
        updated = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        defended = (
            await ctx.seed(agent, T_EVENT + " (b)", NOW - timedelta(days=2))
        ).memory_id
        await _confront(
            ctx, updated, verb="update_with_resentment", content=UPDATE_TELLING
        )
        await _confront(ctx, defended, verb="rationalization", content=DEFENSE_TELLING)

        sources = await db.fetch_reconstruction_sources(ctx.pool, [updated, defended])
        assert sources[updated].anchor_cause == "update_with_resentment"
        assert sources[updated].anchor_content == UPDATE_TELLING
        assert sources[defended].anchor_cause == "original"
        assert sources[defended].anchor_content == f"[suite seed] {T_EVENT} (b)"

    run_structural(scene, scenario)


def test_two_sequential_events_stack(scene):
    """Confrontation over confrontation: the chain grows head over head, the
    corrections rows accumulate one per event, exactly one head stays live,
    and the anchor tracks the latest anchoring cause."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-stack", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        first = await _confront(ctx, m, verb="rationalization", content=DEFENSE_TELLING)
        second = await _confront(
            ctx,
            m,
            verb="update_with_resentment",
            content=UPDATE_TELLING,
            valid_at=T_E + timedelta(hours=1),
        )

        chain = await ctx.chain(m)
        assert [r[0] for r in chain] == [
            "original",
            "rationalization",
            "update_with_resentment",
        ]
        assert [r for r in chain if r[3] is None] == [chain[-1]]
        verbs = await ctx.fetchall(
            "SELECT verb, detail_id FROM corrections WHERE memory_id = %s "
            "ORDER BY valid_at",
            m,
        )
        assert [v[0] for v in verbs] == ["rationalization", "update_with_resentment"]
        assert verbs[0][1] == first.detail_id and verbs[1][1] == second.detail_id

        sources = await db.fetch_reconstruction_sources(ctx.pool, [m])
        assert sources[m].anchor_cause == "update_with_resentment"

    run_structural(scene, scenario)


def test_fact_chain_check_still_rejects_diegetic_verbs(scene):
    """The tellings-only ruling's schema tooth: `memory_fact_versions`'
    write_cause CHECK rejects both diegetic verbs (they were never added —
    no migration 009, ruled)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-factcheck", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        for verb in ("rationalization", "update_with_resentment"):
            with pytest.raises(psycopg.errors.CheckViolation):
                async with ctx.pool.connection() as conn:
                    await conn.execute(
                        "INSERT INTO memory_fact_versions (memory_id, "
                        "basis_text, write_cause, valid_at) "
                        "VALUES (%s, 'junk', %s, %s)",
                        (m, verb, T_E),
                    )

    run_structural(scene, scenario)


def test_dissonance_input_reads(scene):
    """`fetch_agent` now carries rigidity (NULL legal — resolves at the
    decision); `fetch_memory_dissonance_inputs` returns the formula's inputs
    joined to the live head, and None for a missing memory."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-reads", V1_CONFIG)
        seeded = await ctx.seed(
            agent, T_EVENT, NOW - timedelta(days=2), importance=0.7, typology="told"
        )
        m = seeded.memory_id

        agent_row = await db.fetch_agent(ctx.pool, agent)
        assert agent_row["rigidity"] == 1.0  # the fixture's provisioned value

        inputs = await db.fetch_memory_dissonance_inputs(ctx.pool, m)
        assert inputs["agent_id"] == agent
        assert inputs["importance_raw"] == 0.7
        assert inputs["typology"] == "told"
        assert inputs["pinned"] is False
        assert inputs["head_content"] == f"[suite seed] {T_EVENT}"
        assert inputs["head_detail_id"] == (await ctx.chain(m))[0][4]

        assert await db.fetch_memory_dissonance_inputs(ctx.pool, uuid4()) is None

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The decision (pure functions — hand math, no database)
# ---------------------------------------------------------------------------


def _decide(config=None, **kw):
    from app.config import Settings
    from app.dissonance import decide_dissonance

    settings = Settings(database_uri="postgresql://unused", provider_mode="fake")
    base = dict(
        importance_raw=0.5,
        memory_typology="observed",
        rigidity=1.0,
        challenge_typology="observed",
        challenge_weight=None,
        config=config or {},
        settings=settings,
    )
    base.update(kw)
    return decide_dissonance(**base)


def test_decision_hand_math_extremes_and_tie():
    """§8's formula with hand-recomputed rows: both extremes, the exact tie
    defending (strict >), and the resolved inputs exposed."""
    # Challenge wins: 0.5 * 1.0 * 1.0 = 0.5 resistance vs 1.0 * 1.0 = 1.0.
    d = _decide()
    assert d.verb == "update_with_resentment"
    assert d.resistance == pytest.approx(0.5)
    assert d.challenge == pytest.approx(1.0)

    # Memory holds: 0.9 * 1.0 * 2.0 = 1.8 vs told 0.6.
    d = _decide(importance_raw=0.9, rigidity=2.0, challenge_typology="told")
    assert d.verb == "rationalization"
    assert d.resistance == pytest.approx(1.8)
    assert d.challenge == pytest.approx(0.6)

    # The exact tie defends: 1.0 * 0.6 * 1.0 == 1.0 * 0.6.
    d = _decide(importance_raw=1.0, memory_typology="told", challenge_typology="told")
    assert d.resistance == d.challenge
    assert d.verb == "rationalization"


def test_decision_null_resolution_and_clamps():
    """NULLs resolve exactly like their precedents (importance_neutral; the
    dissonance_rigidity_default; the challenge-weight default), and every
    clamp mirrors its existing bound."""
    from app.config import SERVICE_DEFAULTS
    from app.ingest import TYPOLOGY_FALLBACK

    d = _decide(importance_raw=None, memory_typology=None, rigidity=None)
    assert d.importance_norm == pytest.approx(SERVICE_DEFAULTS["importance_neutral"])
    assert d.rigidity_effective == pytest.approx(
        SERVICE_DEFAULTS["dissonance_rigidity_default"]
    )
    assert d.typology_mult_memory == pytest.approx(
        SERVICE_DEFAULTS[f"dissonance_typology_{TYPOLOGY_FALLBACK}"]
    )
    assert d.challenge_weight_effective == pytest.approx(
        SERVICE_DEFAULTS["dissonance_challenge_weight_default"]
    )

    d = _decide(importance_raw=0.01, rigidity=9.0, challenge_weight=1.0)
    assert d.importance_norm == pytest.approx(SERVICE_DEFAULTS["importance_norm_floor"])
    assert d.rigidity_effective == pytest.approx(2.0)
    assert d.challenge_weight_effective == pytest.approx(1.0)


def test_decision_config_override_flips_verdict_and_kill_switch_shape():
    """A per-agent knob override flips the same fixture's verdict (the
    agent_knob contract), and a 0.0 memory-side multiplier is the
    always-folds kill-switch shape."""
    held = _decide(importance_raw=0.9, challenge_typology="told")
    assert held.verb == "rationalization"
    flipped = _decide(
        importance_raw=0.9,
        challenge_typology="told",
        config={"dissonance_typology_told": 2.0},
    )
    assert flipped.verb == "update_with_resentment"
    assert flipped.challenge == pytest.approx(2.0)

    folded = _decide(
        importance_raw=0.9,
        challenge_typology="told",
        config={"dissonance_typology_observed": 0.0},
    )
    assert folded.resistance == pytest.approx(0.0)
    assert folded.verb == "update_with_resentment"


# ---------------------------------------------------------------------------
# The service seam (fakes; the retell rides the RECONSTRUCTION role)
# ---------------------------------------------------------------------------


def _event(agent_id, memory_id, **overrides):
    from app.schemas import DiegeticCorrectionEvent

    base = dict(
        agent_id=agent_id,
        memory_id=memory_id,
        challenge_text=CHALLENGE,
        challenge_typology="observed",
        client_timestamp=T_E,
    )
    base.update(overrides)
    return DiegeticCorrectionEvent(**base)


def test_service_update_flow_hand_numbers(scene):
    """The seam end to end, update half: the response's resolved inputs
    recompute by hand from fixture values; the chain, corrections row, and
    eviction land atomically; the retell is structural-only (non-empty,
    distinct from the prior head — never a prose assert); tokens counted."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-svc-update", V1_CONFIG)
        seeded = await ctx.seed(
            agent, T_EVENT, NOW - timedelta(days=2), importance=0.2, typology="told"
        )
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached one")
        svc = ctx.dissonance()

        result = await svc.confront(_event(agent, m))

        assert result.verb == "update_with_resentment"
        assert result.resistance == pytest.approx(0.2 * 0.6 * 1.0)
        assert result.challenge == pytest.approx(1.0)
        assert result.importance_norm == pytest.approx(0.2)
        assert result.rigidity_effective == pytest.approx(1.0)
        assert result.typology_mult_memory == pytest.approx(0.6)
        assert result.typology_mult_challenge == pytest.approx(1.0)
        assert result.challenge_weight_effective == pytest.approx(1.0)
        assert result.pinned is False
        assert result.evicted_cache_rows == 1
        assert result.retell_input_tokens > 0 and result.retell_output_tokens > 0
        assert result.total_ms >= result.retell_ms >= 0.0

        chain = await ctx.chain(m)
        assert len(chain) == 2
        assert chain[-1][0] == "update_with_resentment"
        assert chain[-1][1] == result.content
        assert result.content and result.content != chain[0][1]
        assert result.detail_id == chain[-1][4]
        assert result.superseded_detail_id == chain[0][4]
        row = await ctx.fetchrow(
            "SELECT correction_id, verb FROM corrections WHERE memory_id = %s", m
        )
        assert row == (result.correction_id, "update_with_resentment")
        assert await ctx.cache_rows(m) == {}

    run_structural(scene, scenario)


def test_service_rationalization_flow_hand_numbers(scene):
    """The defense half of the pair: the memory holds (0.9 observed at
    rigidity 1.0 vs a told challenge), the head types `rationalization`,
    and the fact chain is byte-untouched (tellings-only)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-svc-defend", V1_CONFIG)
        seeded = await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2), importance=0.9)
        m = seeded.memory_id
        facts_before = await ctx.fact_chain(m)
        svc = ctx.dissonance()

        result = await svc.confront(_event(agent, m, challenge_typology="told"))

        assert result.verb == "rationalization"
        assert result.resistance == pytest.approx(0.9)
        assert result.challenge == pytest.approx(0.6)
        chain = await ctx.chain(m)
        assert [r[0] for r in chain] == ["original", "rationalization"]
        assert chain[-1][1] == result.content and result.content != chain[0][1]
        assert await ctx.fact_chain(m) == facts_before

    run_structural(scene, scenario)


def test_service_unknowns_and_ownership(scene):
    """404 shapes: unknown agent, unknown memory, and a FOREIGN memory (from
    this agent's world it does not exist) — nothing written by any of them."""
    from app.ingest import UnknownAgentError, UnknownMemoryError

    async def scenario(ctx):
        owner = await ctx.make_agent("n-owner", V1_CONFIG)
        other = await ctx.make_agent("n-other", V1_CONFIG)
        m = (await ctx.seed(owner, T_EVENT, NOW - timedelta(days=2))).memory_id
        svc = ctx.dissonance()

        with pytest.raises(UnknownAgentError):
            await svc.confront(_event(uuid4(), m))
        with pytest.raises(UnknownMemoryError):
            await svc.confront(_event(owner, uuid4()))
        with pytest.raises(UnknownMemoryError):
            await svc.confront(_event(other, m))
        assert await ctx.fetchall("SELECT 1 FROM corrections") == []
        assert len(await ctx.chain(m)) == 1

    run_structural(scene, scenario)


def test_service_cas_conflict_writes_nothing(scene):
    """The opt-in CAS at the seam: a stale expected_detail_id raises the 409
    shape and the transaction left no trace."""
    from app.ingest import CorrectionConflictError

    async def scenario(ctx):
        agent = await ctx.make_agent("n-svc-cas", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        svc = ctx.dissonance()

        with pytest.raises(CorrectionConflictError):
            await svc.confront(_event(agent, m, expected_detail_id=uuid4()))
        assert len(await ctx.chain(m)) == 1
        assert await ctx.fetchall("SELECT 1 FROM corrections") == []

    run_structural(scene, scenario)


def test_retell_failure_and_malformed_write_nothing(scene):
    """All-or-nothing (the authorial precedent): a failing or malformed
    reconstruction call raises the 502 shape and NOTHING is written — no
    head, no corrections row, cache intact."""
    from app.dissonance import DissonanceCallError
    from app.providers import (
        FailingReconstructionProvider,
        MalformedReconstructionProvider,
    )

    async def scenario(ctx):
        agent = await ctx.make_agent("n-svc-fail", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b1", "cached one")

        for provider in (
            FailingReconstructionProvider(),
            MalformedReconstructionProvider(),
        ):
            svc = ctx.dissonance(reconstruction=provider)
            with pytest.raises(DissonanceCallError):
                await svc.confront(_event(agent, m))
            assert len(await ctx.chain(m)) == 1
            assert await ctx.fetchall("SELECT 1 FROM corrections") == []
            assert len(await ctx.cache_rows(m)) == 1

    run_structural(scene, scenario)


def test_deferred_window_confrontation_head_stands(scene):
    """The C1 interaction (zero new code, dissonance.md): confronting an
    un-enriched pending row is legal — NULL importance/typology resolve via
    the neutral/default ladder — and when the worker completes afterwards,
    the already-moved guard leaves the diegetic head standing (facts-only
    completion; the one-shot scalar fill still lands)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-deferred", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_EVENT, NOW - timedelta(days=2))
        m = seeded.memory_id
        svc = ctx.dissonance()

        result = await svc.confront(_event(agent, m))
        # NULL importance -> neutral 0.5; NULL typology -> the fallback
        # class at 1.0; rigidity 1.0 => resistance 0.5 < challenge 1.0.
        assert result.verb == "update_with_resentment"
        assert result.resistance == pytest.approx(0.5)

        await ctx.worker().drain()

        chain = await ctx.chain(m)
        assert [r[0] for r in chain] == ["original", "update_with_resentment"]
        assert chain[-1][3] is None  # the diegetic head is STILL the live head
        state = await ctx.fetchrow(
            "SELECT enrichment_pending, importance_raw FROM memories "
            "WHERE memory_id = %s",
            m,
        )
        assert state[0] is False  # completion ran...
        assert state[1] is not None  # ...and the one-shot scalar fill landed
        outcome = await ctx.fetchrow(
            "SELECT outcome FROM memory_enrichment_runs WHERE memory_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            m,
        )
        assert outcome == ("completed_facts_only",)

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The route (ASGITransport; pass-through by ruling)
# ---------------------------------------------------------------------------


def test_route_pass_through_and_ladder(scene):
    """POST /v1/events/diegetic-correction over the wire: 200 serializes the
    seam result (pass-through by ruling); then the full fail-loud ladder —
    404 foreign memory, 409 stale CAS, 422 naive timestamp / unknown
    typology literal / out-of-range weight, 502 retell failure with nothing
    written."""
    import httpx

    from app import api as api_module
    from app.providers import FailingReconstructionProvider

    async def scenario(ctx):
        agent = await ctx.make_agent("n-route", V1_CONFIG)
        other = await ctx.make_agent("n-route-other", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id

        api_module.app.state.dissonance = ctx.dissonance()
        transport = httpx.ASGITransport(app=api_module.app)
        body = {
            "agent_id": str(agent),
            "memory_id": str(m),
            "challenge_text": CHALLENGE,
            "challenge_typology": "observed",
            "client_timestamp": T_E.isoformat(),
            "source_event": {"scene": "tavern"},
        }
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.post("/v1/events/diegetic-correction", json=body)
            assert ok.status_code == 200
            payload = ok.json()
            assert payload["memory_id"] == str(m)
            assert payload["verb"] == "update_with_resentment"
            assert payload["challenge"] == pytest.approx(1.0)
            assert payload["content"]
            chain = await ctx.chain(m)
            assert payload["detail_id"] == str(chain[-1][4])
            assert payload["correction_id"] == str(
                (await ctx.fetchrow("SELECT correction_id FROM corrections"))[0]
            )

            foreign = await client.post(
                "/v1/events/diegetic-correction",
                json={**body, "agent_id": str(other)},
            )
            assert foreign.status_code == 404

            stale = await client.post(
                "/v1/events/diegetic-correction",
                json={**body, "expected_detail_id": str(uuid4())},
            )
            assert stale.status_code == 409

            naive = await client.post(
                "/v1/events/diegetic-correction",
                json={**body, "client_timestamp": "2026-08-17T12:00:00"},
            )
            assert naive.status_code == 422
            bad_typology = await client.post(
                "/v1/events/diegetic-correction",
                json={**body, "challenge_typology": "rumored"},
            )
            assert bad_typology.status_code == 422
            bad_weight = await client.post(
                "/v1/events/diegetic-correction",
                json={**body, "challenge_weight": 1.5},
            )
            assert bad_weight.status_code == 422

            before = await ctx.chain(m)
            api_module.app.state.dissonance = ctx.dissonance(
                reconstruction=FailingReconstructionProvider()
            )
            r502 = await client.post("/v1/events/diegetic-correction", json=body)
            assert r502.status_code == 502
            assert "dissonance retell failed" in r502.json()["detail"]
            assert await ctx.chain(m) == before  # nothing written

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Ruling 4 — constraint follows the update_with_resentment anchor
# ---------------------------------------------------------------------------


def test_update_anchor_is_fixed_constraint_pure():
    """C4 ruling 4 (the fork the authorial spec deferred here): an
    `update_with_resentment` anchor takes the authorial branch — the head IS
    the fixed facts, no observation-derived gist or detail re-injected, and
    the ablation switch is ignored (fork 11 inherited). Original-anchored
    chains (a rationalized memory's shape — rationalization never anchors)
    still inject observation gist."""
    from app.db import ReconstructionSource
    from app.reconstruction import FIXED_CONSTRAINT_ANCHORS, build_reconstruction_item

    assert FIXED_CONSTRAINT_ANCHORS == {
        "authorial_correction",
        "update_with_resentment",
    }

    accepted = ReconstructionSource(
        observation_text=T_EVENT,
        spans=[(0, 25)],
        anchor_content=UPDATE_TELLING,
        anchor_cause="update_with_resentment",
    )
    item = build_reconstruction_item("mid", accepted, 0.5, "current telling")
    assert item.gist == UPDATE_TELLING
    assert item.thinned_detail == ""
    off = build_reconstruction_item(
        "mid", accepted, 0.5, "current telling", gist_constraint=False
    )
    assert off.gist == UPDATE_TELLING  # the switch never blanks a correction

    original = ReconstructionSource(
        observation_text=T_EVENT,
        spans=[(0, 25)],
        anchor_content="irrelevant",
        anchor_cause="original",
    )
    injected = build_reconstruction_item("mid", original, 1.0, "current telling")
    assert injected.gist == T_EVENT[0:25]
    assert injected.thinned_detail != ""


def test_read_path_sanctioned_change_then_byte_identity(scene):
    """The serving surface across the event: the read before serves the old
    head; the event lands (the FIRST sanctioned mid-scene text-change cause
    — the invariant's original carve-out); reads after serve the new head,
    and repeat byte-identically (stability restored)."""
    from conftest import by_id

    from app.schemas import DialogueInitRequest

    async def scenario(ctx):
        agent = await ctx.make_agent("n-readpath", V1_CONFIG)
        m = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        retrieval = ctx.retrieval()
        req = DialogueInitRequest(agent_id=agent, query_text=T_EVENT, as_of=T_E)

        before = await retrieval.retrieve_dialogue_init(req)
        assert by_id(before)[m].content == f"[suite seed] {T_EVENT}"

        result = await ctx.dissonance().confront(_event(agent, m))

        first = await retrieval.retrieve_dialogue_init(req)
        second = await retrieval.retrieve_dialogue_init(req)
        assert by_id(first)[m].content == result.content
        assert by_id(first)[m].detail_id == result.detail_id
        assert by_id(second)[m].content == by_id(first)[m].content

    run_structural(scene, scenario)


def test_chain_inspector_carries_corrections_block(scene):
    """The unscored chain read gains the confrontation records (additive,
    defaulted): present with verb/head/source_event after an event, empty on
    an authorial-only chain."""

    async def scenario(ctx):
        agent = await ctx.make_agent("n-inspector", V1_CONFIG)
        confronted = (await ctx.seed(agent, T_EVENT, NOW - timedelta(days=2))).memory_id
        authorial = (
            await ctx.seed(agent, T_EVENT + " (a)", NOW - timedelta(days=2))
        ).memory_id
        payload = {"scene": "tavern", "speaker": "Bram"}
        result = await ctx.dissonance().confront(
            _event(agent, confronted, source_event=payload)
        )
        # Authorial at the db layer (the Set A idiom) — the service-level
        # verb would pull the NER loaders into an unmarked scenario.
        from conftest import embed_text

        await db.apply_authorial_correction(
            ctx.pool,
            memory_id=authorial,
            content="corrected text",
            valid_at=T_E,
            embedding=embed_text("corrected text"),
        )

        chain = await ctx.retrieval().memory_chain(confronted)
        assert len(chain.corrections) == 1
        record = chain.corrections[0]
        assert record.correction_id == result.correction_id
        assert record.detail_id == result.detail_id
        assert record.verb == result.verb
        assert record.source_event == payload
        assert record.valid_at == T_E

        untouched = await ctx.retrieval().memory_chain(authorial)
        assert untouched.corrections == []

    run_structural(scene, scenario)
