"""Set C — identity-conditioned reconstruction (docs\\test-suite.md;
reconstruction.md, built 2026-07-17). RECON_CONFIG agents: reconstruction at
the PRODUCTION default theta 0.5; the gate FIXTURE-pinned off (see conftest).

Unmarked: seeding is db-layer; identity plumbing rides `scene_boundary`
(no NLP pass). Ages mirror the reconstruction walker's proven fixture math:
`semantic` (tau 7d) rows at 10 days sit past theta for any importance in
[0, 1]; episodic rows an hour old sit far above it; +30 days crosses the
next thinning band. Byte-identity assertions ride STORED/SERVED text —
the fake retelling is deterministic, but no assertion touches its wording.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import NOW, RECON_CONFIG, by_id, run_structural

from app import db
from app.schemas import DialogueInitRequest, SceneBoundaryEvent

T_OLD = (
    "The stranger broke the miller cart at the ford. He cursed loudly and "
    "blamed the rain. Mara helped drag it clear before nightfall. The road "
    "stayed blocked for hours."
)
T_FRESH = "Mara sharpened my blade at the forge while John watched."
T_PIN = (
    "Wolves took two lambs in the north pasture during the long frost. The "
    "shepherd blamed himself. Mara sat with him that evening."
)
T_DRIFT = (
    "A pedlar sold me a crooked knife at the harvest fair. The blade snapped "
    "on the first cut. Mara laughed about it for a week."
)
CORRECTED = "The stranger's cart broke at the ford; Mara and I cleared it."


def test_detail_thinning_has_one_budget_and_can_reach_zero():
    from app.reconstruction import thin_detail

    # Gist boundaries can leave many one-sentence segments. None is immortal.
    segments = ["The river was loud.", "A dog slept.", "The boards were wet."]
    assert thin_detail(segments, 0.0) == ""
    assert thin_detail(segments, 0.05) == ""
    assert thin_detail(segments, 0.35) == segments[0]
    assert thin_detail(segments, 1.0) == "\n".join(segments)
    assert thin_detail([], 1.0) == ""
    assert thin_detail(["A single fragment."], 0.9) == ""
    assert thin_detail(["First. Second.", "Third."], 0.7) == "First.\nSecond."
    samples = [thin_detail(segments, level) for level in (0, 0.2, 0.4, 0.8, 1)]
    assert all(
        later.startswith(earlier) for earlier, later in zip(samples, samples[1:])
    )


def test_legacy_cache_does_not_mask_new_reconstruction(scene):
    from app.eval_metrics import band_from_composed_key

    async def scenario(ctx):
        agent = await ctx.make_agent("c-legacy-cache", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        )
        for band in range(4):
            await db.insert_cache_row(
                ctx.pool, old.memory_id, f"{version}|b{band}", "legacy"
            )
        result = await ctx.retrieval().retrieve_dialogue_init(
            request(agent, version, NOW)
        )
        assert result.instrumentation.cache_misses == 1
        assert result.instrumentation.write_backs == 1
        cache = await ctx.cache_rows(old.memory_id)
        assert len(cache) == 5
        assert all(cache[f"{version}|b{band}"] == "legacy" for band in range(4))
        assert all(band_from_composed_key(key) is not None for key in cache)
        repeat = await ctx.retrieval().retrieve_dialogue_init(
            request(agent, version, NOW)
        )
        assert repeat.instrumentation.cache_hits == 1
        assert repeat.items[0].content == result.items[0].content

    run_structural(scene, scenario)


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


async def _boundary(ctx, agent, at=NOW) -> str:
    result = await ctx.ingest().scene_boundary(
        SceneBoundaryEvent(agent_id=agent, client_timestamp=at)
    )
    return result.identity_version


def test_writeback_chain_and_immutable_sources(scene):
    """Theta partition + batched write-back: past-theta rows reconstruct
    (new head under the same memory_id, prior superseded at the scene
    basis), fresh and pinned serve verbatim; gist spans and the observation
    text never move; the cache row's rendered_text IS the served text."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-writeback", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent,
            T_OLD,
            NOW - timedelta(days=10),
            decay_class="semantic",
            spans=((0, 48),),
        )
        fresh = await ctx.seed(agent, T_FRESH, NOW - timedelta(hours=1))
        pin = await ctx.seed(
            agent,
            T_PIN,
            NOW - timedelta(days=10),
            decay_class="semantic",
            pinned=True,
        )
        retrieval = ctx.retrieval()
        r1 = await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        m1 = by_id(r1)
        assert m1[old.memory_id].read_mode == "reconstructed"
        assert m1[fresh.memory_id].read_mode == "verbatim"
        assert m1[pin.memory_id].read_mode == "verbatim"
        i1 = r1.instrumentation
        assert i1.cache_misses == 1 and i1.write_backs == 1

        chain = await ctx.chain(old.memory_id)
        assert len(chain) == 2
        assert chain[0][0] == "original" and chain[0][3] == NOW
        assert chain[1][0] == "reconstruction"
        assert chain[1][2] == NOW and chain[1][3] is None
        assert m1[old.memory_id].content == chain[1][1]
        assert m1[old.memory_id].detail_id == chain[1][4]

        cache = await ctx.cache_rows(old.memory_id)
        assert len(cache) == 1
        key = next(iter(cache))
        assert key.startswith(f"{version}|r2|b")
        assert cache[key] == m1[old.memory_id].content  # serve-only-persisted

        row = await ctx.fetchrow(
            "SELECT observation_text FROM memories WHERE memory_id = %s",
            old.memory_id,
        )
        assert row[0] == T_OLD
        spans = await ctx.fetchall(
            "SELECT start_char, end_char FROM memory_gist_spans WHERE memory_id = %s",
            old.memory_id,
        )
        assert spans == [(0, 48)]

        # Pinned never grows chain or cache rows, across repeated reads.
        await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        assert len(await ctx.chain(pin.memory_id)) == 1
        assert await ctx.cache_rows(pin.memory_id) == {}
        # The write-back never touches the fact chain.
        assert len(await ctx.fact_chain(old.memory_id)) == 1

    run_structural(scene, scenario)


def test_cache_hit_call_free_byte_identical(scene):
    """Stable identity + same band => cache hit: no model call, no new
    rows, text and score components byte-identical across identical reads."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-cachehit", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        )
        retrieval = ctx.retrieval()
        r1 = await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        r2 = await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        i2 = r2.instrumentation
        assert i2.cache_hits == 1 and i2.cache_misses == 0 and i2.write_backs == 0
        assert i2.reconstruction_input_tokens == 0
        a, b = by_id(r1)[old.memory_id], by_id(r2)[old.memory_id]
        assert b.content == a.content and b.read_mode == a.read_mode
        assert (b.score, b.relevance, b.recency, b.importance_norm) == (
            a.score,
            a.relevance,
            a.recency,
            a.importance_norm,
        )
        assert len(await ctx.chain(old.memory_id)) == 2  # no third row

    run_structural(scene, scenario)


def test_within_scene_frozen_basis(scene):
    """Mid-scene as_of jumps move scores only: the scene-frozen basis keeps
    the composed key, so text stays byte-identical with zero new misses."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-frozen", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        )
        fresh = await ctx.seed(agent, T_FRESH, NOW - timedelta(hours=1))
        retrieval = ctx.retrieval()
        r1 = await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        jump = await retrieval.retrieve_dialogue_init(
            request(agent, version, NOW, as_of=NOW + timedelta(days=40))
        )
        assert jump.instrumentation.cache_misses == 0
        assert by_id(jump)[old.memory_id].content == by_id(r1)[old.memory_id].content
        assert by_id(jump)[fresh.memory_id].recency < by_id(r1)[fresh.memory_id].recency

    run_structural(scene, scenario)


def test_band_crossing_retells_on_thinner_detail(scene):
    """A deeper scene basis crosses a thinning-band edge: same identity,
    new composed key => miss + re-reconstruction; the chain grows under the
    same memory_id; the two cache keys carry strictly deepening bands."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-band", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        )
        retrieval = ctx.retrieval()
        await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        basis2 = NOW + timedelta(days=30)  # age 40d => the next band
        r2 = await retrieval.retrieve_dialogue_init(request(agent, version, basis2))
        assert r2.instrumentation.cache_misses == 1
        assert r2.instrumentation.write_backs == 1
        cache = await ctx.cache_rows(old.memory_id)
        assert len(cache) == 2
        bands = sorted(int(k.rsplit("|b", 1)[1]) for k in cache)
        assert bands[1] > bands[0]
        chain = await ctx.chain(old.memory_id)
        assert len(chain) == 3
        assert chain[2][0] == "reconstruction" and chain[2][2] == basis2
        assert chain[1][3] == basis2  # prior retelling superseded at basis2

    run_structural(scene, scenario)


def test_identity_bump_means_cache_miss(scene):
    """An identity-version bump (seed change + scene boundary) composes a
    new cache key: miss + retell under the same band; the retelling under
    the new identity differs from the old key's (conditioning is live)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-bump", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent, T_OLD, NOW - timedelta(days=10), decay_class="semantic"
        )
        retrieval = ctx.retrieval()
        await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        await ctx.execute(
            "UPDATE agents SET seed_identity = %s WHERE agent_id = %s",
            "The ford keeper, older now, and tired of strangers.",
            agent,
        )
        version2 = await _boundary(ctx, agent)
        assert version2 != version
        r2 = await retrieval.retrieve_dialogue_init(request(agent, version2, NOW))
        assert r2.instrumentation.cache_misses == 1
        assert r2.instrumentation.write_backs == 1
        cache = await ctx.cache_rows(old.memory_id)
        from app.reconstruction import compose_cache_key

        keys = set(cache)
        assert len(keys) == 2
        v1_key = next(k for k in keys if k.startswith(version))
        v2_key = next(k for k in keys if k.startswith(version2))
        # Same band, new identity component: the composed-key contract.
        band = int(v2_key.rsplit("|b", 1)[1])
        assert v1_key.rsplit("|b", 1)[1] == v2_key.rsplit("|b", 1)[1]
        assert compose_cache_key(version2, band) == v2_key
        assert cache[v2_key] != cache[v1_key]  # identity conditioning moved it

    run_structural(scene, scenario)


def test_correction_evicts_and_reanchors(scene):
    """Correction verbs evict caches; the next past-theta read misses,
    retells against the corrected anchor, and serves only persisted text."""

    async def scenario(ctx):
        agent = await ctx.make_agent("c-correct", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent,
            T_OLD,
            NOW - timedelta(days=10),
            decay_class="semantic",
            spans=((0, 48),),
        )
        retrieval = ctx.retrieval()
        await retrieval.retrieve_dialogue_init(request(agent, version, NOW))
        assert len(await ctx.cache_rows(old.memory_id)) == 1

        from conftest import embed_text

        applied = await db.apply_authorial_correction(
            ctx.pool,
            memory_id=old.memory_id,
            content=CORRECTED,
            valid_at=NOW + timedelta(hours=1),
            embedding=embed_text(CORRECTED),
        )
        assert isinstance(applied, db.CorrectionApplied)
        assert await ctx.cache_rows(old.memory_id) == {}

        sources = await db.fetch_reconstruction_sources(ctx.pool, [old.memory_id])
        assert sources[old.memory_id].anchor_content == CORRECTED
        assert sources[old.memory_id].anchor_cause == "authorial_correction"

        r2 = await retrieval.retrieve_dialogue_init(
            request(agent, version, NOW + timedelta(hours=1))
        )
        assert r2.instrumentation.write_backs == 1
        head = (await ctx.chain(old.memory_id))[-1]
        assert head[0] == "reconstruction"
        item = by_id(r2)[old.memory_id]
        assert item.content == head[1] and item.read_mode == "reconstructed"

    run_structural(scene, scenario)


def test_drift_bound_refuses_and_caches_refusal(scene):
    """An over-threshold retelling is refused: no chain row, the prior head
    served under honest read_mode, the served text cached under the current
    key so the next same-key read is call-free and byte-stable."""

    async def scenario(ctx):
        from app.providers import DriftingReconstructionProvider

        agent = await ctx.make_agent("c-drift", RECON_CONFIG)
        old = await ctx.seed(
            agent, T_DRIFT, NOW - timedelta(days=10), decay_class="semantic"
        )
        drifting = ctx.retrieval(reconstruction=DriftingReconstructionProvider())
        r1 = await drifting.retrieve_dialogue_init(
            request(agent, None, NOW, query_text=T_DRIFT)
        )
        assert r1.instrumentation.drift_refusals == 1
        assert r1.instrumentation.write_backs == 0
        chain = await ctx.chain(old.memory_id)
        assert len(chain) == 1
        item = by_id(r1)[old.memory_id]
        assert item.content == chain[0][1] and item.read_mode == "verbatim"
        cache = await ctx.cache_rows(old.memory_id)
        assert len(cache) == 1
        assert next(iter(cache.values())) == chain[0][1]

        r2 = await drifting.retrieve_dialogue_init(
            request(agent, None, NOW, query_text=T_DRIFT)
        )
        assert r2.instrumentation.cache_hits == 1
        assert r2.instrumentation.reconstruction_input_tokens == 0
        assert by_id(r2)[old.memory_id].content == item.content

    run_structural(scene, scenario)
