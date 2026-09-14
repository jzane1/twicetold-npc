"""Set L — reflection (reflection.md; migration 007, the C2 rulings dated
2026-08-15).

The seam is exercised through `ReflectionService.reflect` and the worker
through `sweep()` — the deterministic no-timer entries — against memories
and prior reflections seeded at the db layer (`Ctx.seed` /
`Ctx.seed_reflection`), so every scenario stays unmarked (no write-pass
call, no spaCy loaders). The pipeline's time basis is the request's
client_timestamp, so the clock freezes by freezing the request (the as_of
precedent). Structural-only, per the standing rule: row state, bi-temporal
chains, citation-subset membership, byte-identity of rendered documents and
prompts — never prose judgment (the fake conclusions' byte shape is a
fixture property). The route rides one HTTP-level contract scenario via
the ASGI-transport pattern (the Route-contracts convention, no lifespan,
no loaders); the served-app probes live in the console interop gate (the
C# mirror's beats).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import NOW, SEED_PROSE, V1_CONFIG, run_structural

from app.providers import (
    FakeReflectionProvider,
    FailingReflectionProvider,
    MalformedReflectionProvider,
    ProviderCallError,
    ReflectionCallResult,
    ReflectionConclusion,
)
from app.reflection import ReflectionCallError, ReflectionFloorError
from app.schemas import ReflectRequest

T1 = "Bram shattered the lantern at the ford gate."
T2 = "A grey cat took up residence in the mill loft."
T3 = "The well rope frayed and was replaced with new hemp."
T4 = "The miller paid his toll without argument."
T5 = "Rain flooded the low road past the ford."

REFLECT_CONFIG = dict(V1_CONFIG)


def _request(at=NOW, consolidate=None) -> ReflectRequest:
    return ReflectRequest(client_timestamp=at, consolidate=consolidate)


async def _reflection_rows(ctx, agent_id):
    """(content, identity_relevant, source_memory_ids, valid_at, invalid_at,
    reflection_id), insertion order."""
    return await ctx.fetchall(
        "SELECT content, identity_relevant, source_memory_ids, valid_at, "
        "invalid_at, reflection_id FROM reflections WHERE agent_id = %s "
        "ORDER BY created_at, reflection_id",
        agent_id,
    )


async def _document(ctx, agent_id, version):
    row = await ctx.fetchrow(
        "SELECT rendered_text FROM identity_documents "
        "WHERE agent_id = %s AND identity_version = %s",
        agent_id,
        version,
    )
    return row[0] if row else None


async def _seed_floor(ctx, agent, n=5, importance=0.5):
    """n live memories, an hour apart, newest last — the sampling pool."""
    seeded = []
    for i, text in enumerate((T1, T2, T3, T4, T5)[:n]):
        seeded.append(
            await ctx.seed(
                agent,
                text,
                NOW - timedelta(hours=n - i),
                importance=importance,
            )
        )
    return seeded


# ---------------------------------------------------------------------------
# The reflect verb
# ---------------------------------------------------------------------------


def test_reflect_happy_path(scene):
    """Done-when 1: grounded bi-temporal rows at the request's valid_at,
    citations a non-empty subset of the sampled ids, pressure served
    before/after, honest instrumentation, and the re-rendered document
    carrying the identity-relevant belief byte-for-byte."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-happy", REFLECT_CONFIG)
        seeded = await _seed_floor(ctx, agent)
        service = ctx.reflection()
        result = await service.reflect(agent, _request())

        assert len(result.reflections) == 2  # the fake's two conclusions
        assert set(result.sampled_memory_ids) == {s.memory_id for s in seeded}
        sampled = set(result.sampled_memory_ids)
        for out in result.reflections:
            assert out.source_memory_ids
            assert set(out.source_memory_ids) <= sampled
        assert result.dropped_ungrounded == 0

        rows = await _reflection_rows(ctx, agent)
        assert len(rows) == 2
        # One transaction stamps both rows' created_at identically, so row
        # order is id-tiebroken — assert membership, not sequence.
        assert sorted(r[1] for r in rows) == [False, True]
        for content, _rel, sources, valid_at, invalid_at, _rid in rows:
            assert valid_at == NOW  # the request timestamp is the world time
            assert invalid_at is None
            assert sources
        assert {r[5] for r in rows} == {o.reflection_id for o in result.reflections}

        # Pressure: 5 memories x 0.5 / norm 10.0 before; all memories predate
        # the new reflection rows' created_at after.
        assert result.pressure_before == pytest.approx(0.25)
        assert result.pressure_after == 0.0

        # The document re-rendered: seed + the identity-relevant content.
        belief = next(r[0] for r in rows if r[1])
        rendered = await _document(ctx, agent, result.identity_version)
        assert rendered == f"{SEED_PROSE}\n\n{belief}"
        assert result.identity_document_new is True

        inst = result.instrumentation
        assert inst.reflect_ms >= 0 and inst.insert_ms >= 0
        assert inst.total_ms >= inst.insert_ms
        assert inst.reflect_input_tokens > 0
        assert inst.consolidation_ms == 0.0  # stage not due (default knob 5)
        assert result.consolidation is None

    run_structural(scene, scenario)


def test_sampling_deterministic_topk_and_pin_plain_decay(scene):
    """The draw is a deterministic top-k by importance_norm x recency at the
    request's time basis — never a lottery — and a pinned row takes the
    PLAIN decay score (pin = decay exemption + reconstruction exclusion,
    exactly two meanings; reflection is neither), so an ancient pinned row
    falls out of the sample that a rec=1.0 arm would have topped."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-sample", REFLECT_CONFIG)
        fresh = await ctx.seed(agent, T1, NOW - timedelta(hours=1), importance=0.9)
        mid = await ctx.seed(agent, T2, NOW - timedelta(days=1), importance=0.9)
        old = await ctx.seed(agent, T3, NOW - timedelta(days=10), importance=0.9)
        pinned_old = await ctx.seed(
            agent, T4, NOW - timedelta(days=30), importance=0.9, pinned=True
        )
        service = ctx.reflection(
            defaults={"reflection_sample_k": 3.0, "reflection_min_episodes": 2.0}
        )
        first = await service.reflect(agent, _request())
        assert first.sampled_memory_ids == [
            fresh.memory_id,
            mid.memory_id,
            old.memory_id,
        ]
        assert pinned_old.memory_id not in first.sampled_memory_ids

        second = await service.reflect(agent, _request())
        assert second.sampled_memory_ids == first.sampled_memory_ids

    run_structural(scene, scenario)


def test_grounding_partial_drop(scene):
    """Done-when 2 (first half): one grounded + one ungrounded conclusion
    stores exactly the grounded one, dropped_ungrounded counts it."""

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
                        source_memory_ids=[str(uuid4())],  # not in the sample
                    ),
                ],
                input_tokens=5,
                output_tokens=5,
            )

        def consolidate(self, **_kwargs):
            raise AssertionError("consolidation must not be reached")

    async def scenario(ctx):
        agent = await ctx.make_agent("l-partial", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection(provider=PartiallyUngrounded())
        result = await service.reflect(agent, _request())
        assert result.dropped_ungrounded == 1
        assert len(result.reflections) == 1
        rows = await _reflection_rows(ctx, agent)
        assert len(rows) == 1
        assert rows[0][0] == "[fixture] grounded conclusion"

    run_structural(scene, scenario)


def test_grounding_all_drop_is_502_nothing_written(scene):
    """Done-when 2 (second half): a non-empty output whose conclusions ALL
    fail grounding (empty citations or foreign ids) is a malformed-class
    failure — ReflectionCallError (502), zero rows written."""

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

    async def scenario(ctx):
        agent = await ctx.make_agent("l-ungrounded", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection(provider=AllUngrounded())
        with pytest.raises(ReflectionCallError, match="ungrounded"):
            await service.reflect(agent, _request())
        assert await _reflection_rows(ctx, agent) == []

        # The call-failure and malformed-output rungs land the same way.
        for provider in (FailingReflectionProvider(), MalformedReflectionProvider()):
            with pytest.raises(ReflectionCallError):
                await ctx.reflection(provider=provider).reflect(agent, _request())
        assert await _reflection_rows(ctx, agent) == []

    run_structural(scene, scenario)


def test_empty_conclusions_is_valid(scene):
    """A genuinely empty conclusion list is a VALID outcome (thin evidence
    concludes nothing): success, zero rows, zero drops, document untouched."""

    class ConcludesNothing:
        def reflect(self, *, system_prompt, user_content, items):
            return ReflectionCallResult(conclusions=[], input_tokens=3, output_tokens=0)

        def consolidate(self, **_kwargs):
            raise AssertionError("consolidation must not be reached")

    async def scenario(ctx):
        from app.identity import render_identity_document

        agent = await ctx.make_agent("l-empty", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection(provider=ConcludesNothing())
        result = await service.reflect(agent, _request())
        assert result.reflections == []
        assert result.dropped_ungrounded == 0
        assert await _reflection_rows(ctx, agent) == []
        # Zero reflections => the render is the seed verbatim.
        _, expected_version = render_identity_document(SEED_PROSE)
        assert result.identity_version == expected_version

    run_structural(scene, scenario)


def test_floor_409_and_unknown_agent_404(scene):
    """Done-when 3: below reflection_min_episodes the verb refuses loudly
    with zero rows; an unknown agent is the 404 class (the route maps both
    1:1)."""

    async def scenario(ctx):
        from app.ingest import UnknownAgentError

        agent = await ctx.make_agent("l-floor", REFLECT_CONFIG)
        await ctx.seed(agent, T1, NOW - timedelta(hours=2))
        await ctx.seed(agent, T2, NOW - timedelta(hours=1))
        service = ctx.reflection()
        with pytest.raises(ReflectionFloorError, match="reflection_min_episodes"):
            await service.reflect(agent, _request())
        assert await _reflection_rows(ctx, agent) == []
        with pytest.raises(UnknownAgentError):
            await service.reflect(uuid4(), _request())

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# RRR + consolidation
# ---------------------------------------------------------------------------


def test_rrr_guard_blocks_consolidation_not_storage(scene):
    """Done-when 4: a repeat reflect over the same store emits near-duplicate
    conclusions (the deterministic fake varies only its marker — and the
    identity block shifted under it, so near- rather than byte-identical:
    measured 0.905) => rrr >= the 0.85 threshold — the consolidation stage
    is suppressed even under a consolidate=True override, and the
    reflections still store."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-rrr", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection()

        first = await service.reflect(agent, _request())
        assert first.rrr is None  # no priors existed
        assert first.rrr_blocked_consolidation is False

        second = await service.reflect(agent, _request(consolidate=True))
        assert second.rrr is not None and second.rrr >= 0.85
        assert second.rrr_blocked_consolidation is True
        assert second.consolidation is None  # suppressed, not failed
        rows = await _reflection_rows(ctx, agent)
        assert len(rows) == 4  # both calls' conclusions stored
        assert all(r[4] is None for r in rows)  # all live — nothing absorbed

    run_structural(scene, scenario)


def test_consolidation_absorbs_bitemporally(scene):
    """Done-when 5: at the trigger (forced here; RRR clear) one new
    identity-relevant reflection absorbs the live identity-relevant rows —
    invalid_at set, rows still queryable, provenance the source union, the
    version bumped, and the document carrying the consolidated belief and
    not the absorbed one."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-consolidate", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection()
        result = await service.reflect(agent, _request(consolidate=True))

        assert result.rrr is None  # first reflect: no priors, RRR clear
        assert result.consolidation is not None
        assert result.consolidation.failed is False
        consolidated_id = result.consolidation.reflection_id
        identity_written = [o for o in result.reflections if o.identity_relevant]
        assert result.consolidation.absorbed_reflection_ids == [
            o.reflection_id for o in identity_written
        ]

        rows = await _reflection_rows(ctx, agent)
        by_id = {r[5]: r for r in rows}
        absorbed = by_id[identity_written[0].reflection_id]
        assert absorbed[4] == NOW  # invalid_at = the request timestamp
        consolidated = by_id[consolidated_id]
        assert consolidated[4] is None and consolidated[1] is True
        assert sorted(consolidated[2]) == sorted(absorbed[2])  # source union

        rendered = await _document(ctx, agent, result.identity_version)
        assert rendered == f"{SEED_PROSE}\n\n{consolidated[0]}"
        assert absorbed[0] not in rendered

    run_structural(scene, scenario)


def test_consolidation_failure_is_soft(scene):
    """The ladder's soft rung: the consolidation call fails, the flag rises,
    and every step-7 write stands — reflections live, nothing absorbed, no
    consolidated row."""

    class ConsolidationFails(FakeReflectionProvider):
        def consolidate(self, **_kwargs):
            raise ProviderCallError("injected consolidation failure")

    async def scenario(ctx):
        agent = await ctx.make_agent("l-soft", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        service = ctx.reflection(provider=ConsolidationFails())
        result = await service.reflect(agent, _request(consolidate=True))
        assert result.consolidation is not None
        assert result.consolidation.failed is True
        assert result.consolidation.reflection_id is None
        rows = await _reflection_rows(ctx, agent)
        assert len(rows) == 2  # the step-7 writes stand
        assert all(r[4] is None for r in rows)  # nothing absorbed

    run_structural(scene, scenario)


def test_consolidate_false_suppresses_when_due(scene):
    """Spec ruling 1's third arm: consolidate=False suppresses the stage
    even past the threshold; absent lets the knob decide."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-suppress", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        # Past the trigger already: knob at 1, one prior identity-relevant row.
        await ctx.seed_reflection(
            agent, "[fixture] an old belief", NOW - timedelta(days=1)
        )
        # RRR pinned inert (threshold > 1 can never fire) — this scenario
        # asserts the consolidate-override arm alone, the single-cause
        # discipline (the reconstruction_theta=0 fixture-pin shape); the
        # guard itself is the RRR scenario's subject.
        service = ctx.reflection(
            defaults={
                "reflection_consolidate_at": 1.0,
                "reflection_rrr_threshold": 1.01,
            }
        )
        suppressed = await service.reflect(agent, _request(consolidate=False))
        assert suppressed.consolidation is None
        rows = await _reflection_rows(ctx, agent)
        assert all(r[4] is None for r in rows)  # nothing absorbed

        # Absent => the knob decides (1 => due): the stage runs this call.
        decided = await service.reflect(agent, _request())
        assert decided.consolidation is not None
        assert decided.consolidation.failed is False

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Component trim + eviction + constraint-follows-liveness
# ---------------------------------------------------------------------------


def test_trim_mechanical_rule_and_per_affected_eviction(scene):
    """Done-when 6 (core): under the frozen clock a component whose entire
    span evidence is stale prunes (invalid_at, never DELETE); the authored
    (zero-span) and fresh-evidence components survive; cache rows evict
    per-affected-memory only; the gate's live set shrinks; reconstruction
    sources drop the pruned component's spans."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("l-trim", REFLECT_CONFIG, components=())
        authored = await ctx.add_component(agent, "Keeper")
        stale_comp = await ctx.add_component(agent, "Miller")
        fresh_comp = await ctx.add_component(agent, "Smith")

        stale_mem = await ctx.seed(
            agent,
            T4,
            NOW - timedelta(days=30),
            importance=0.1,
            component_spans=((0, 10, stale_comp),),
        )
        fresh_mem = await ctx.seed(
            agent,
            T1,
            NOW - timedelta(hours=2),
            importance=0.2,
            component_spans=((0, 4, fresh_comp),),
        )
        top = await ctx.seed(agent, T5, NOW - timedelta(minutes=1), importance=0.9)
        await db.insert_cache_row(ctx.pool, stale_mem.memory_id, "v|b0", "stale")
        await db.insert_cache_row(ctx.pool, top.memory_id, "v|b0", "fresh")

        before = await db.fetch_reconstruction_sources(ctx.pool, [stale_mem.memory_id])
        assert before[stale_mem.memory_id].spans == [(0, 10)]

        service = ctx.reflection(
            defaults={
                "reflection_sample_k": 1.0,  # only `top` samples
                "reflection_min_episodes": 1.0,
                "reflection_trim_stale_seconds": 7 * 86400.0,
            }
        )
        result = await service.reflect(agent, _request())
        assert result.sampled_memory_ids == [top.memory_id]
        assert result.pruned_component_ids == [stale_comp]
        assert result.evicted_cache_rows == 1

        # invalid_at, never DELETE — the row stays queryable.
        row = await ctx.fetchrow(
            "SELECT invalid_at FROM identity_components WHERE component_id = %s",
            stale_comp,
        )
        assert row[0] == NOW
        live = await db.fetch_live_components(ctx.pool, agent)
        assert {c["component_id"] for c in live} == {authored, fresh_comp}

        # Per-affected eviction: the stale memory's cache row is gone, the
        # untouched memory's row stands.
        assert await ctx.cache_rows(stale_mem.memory_id) == {}
        assert await ctx.cache_rows(top.memory_id) == {"v|b0": "fresh"}

        # Constraint-follows-liveness: the pruned component's span drops out
        # of the gist constraint; the fresh memory's span is untouched.
        after = await db.fetch_reconstruction_sources(
            ctx.pool, [stale_mem.memory_id, fresh_mem.memory_id]
        )
        assert after[stale_mem.memory_id].spans == []
        assert after[fresh_mem.memory_id].spans == [(0, 4)]

    run_structural(scene, scenario)


def test_trim_active_evidence_exemption(scene):
    """Done-when 6 (exemption 3): a component whose evidence is stale by the
    window but whose evidencing memory is IN this call's sample never
    prunes — a formative old memory in active use protects its components."""

    async def scenario(ctx):
        agent = await ctx.make_agent("l-active", REFLECT_CONFIG, components=())
        formative = await ctx.add_component(agent, "Reeve")
        await ctx.seed(
            agent,
            T3,
            NOW - timedelta(days=30),
            importance=0.9,
            component_spans=((0, 8, formative),),
        )
        for i, text in enumerate((T1, T2, T4)):
            await ctx.seed(agent, text, NOW - timedelta(hours=3 - i))
        service = ctx.reflection(
            defaults={"reflection_trim_stale_seconds": 7 * 86400.0}
        )
        result = await service.reflect(agent, _request())  # k=16: all sampled
        assert result.pruned_component_ids == []
        row = await ctx.fetchrow(
            "SELECT invalid_at FROM identity_components WHERE component_id = %s",
            formative,
        )
        assert row[0] is None

    run_structural(scene, scenario)


def test_trim_disabled_is_full_parity(scene):
    """Done-when 6 (kill-switch): reflection_trim_stale_seconds 0.0 prunes
    nothing — same fixture as the prune scenario, zero prunes, zero
    evictions, sources and caches byte-identical before/after."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("l-noTrim", REFLECT_CONFIG, components=())
        stale_comp = await ctx.add_component(agent, "Miller")
        stale_mem = await ctx.seed(
            agent,
            T4,
            NOW - timedelta(days=30),
            importance=0.1,
            component_spans=((0, 10, stale_comp),),
        )
        await ctx.seed(agent, T5, NOW - timedelta(minutes=1), importance=0.9)
        await db.insert_cache_row(ctx.pool, stale_mem.memory_id, "v|b0", "kept")

        before = await db.fetch_reconstruction_sources(ctx.pool, [stale_mem.memory_id])
        service = ctx.reflection(
            defaults={
                "reflection_sample_k": 1.0,
                "reflection_min_episodes": 1.0,
                "reflection_trim_stale_seconds": 0.0,  # the kill-switch
            }
        )
        result = await service.reflect(agent, _request())
        assert result.pruned_component_ids == []
        assert result.evicted_cache_rows == 0
        after = await db.fetch_reconstruction_sources(ctx.pool, [stale_mem.memory_id])
        assert after == before
        assert await ctx.cache_rows(stale_mem.memory_id) == {"v|b0": "kept"}

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The dialogue seam (speech sees beliefs; parity without them)
# ---------------------------------------------------------------------------


def test_dialogue_seam_parity_and_identity_visibility(scene):
    """Done-when 7: with zero reflections the rendered document IS the seed
    (same bytes, same version — every pre-C2 hash and prompt holds); after
    an identity-relevant reflection and a recompile the [identity] block
    carries it; an unknown identity_version on a turn is the loud 422
    class; a version-carrying turn runs clean."""

    async def scenario(ctx):
        from app.dialogue import (
            _BLOCK_PROSE_INSTRUCTION,
            DialogueService,
            assemble_prose_prompt,
        )
        from app.identity import ensure_identity_document, render_identity_document
        from app.reconstruction import UnknownIdentityVersionError
        from app.schemas import DialogueTurnRequest
        from conftest import drain_turn

        agent = await ctx.make_agent("l-seam", REFLECT_CONFIG)
        await ctx.seed(agent, T1, NOW - timedelta(hours=1))

        # Zero reflections: seed-verbatim render, the pre-C2 version exactly.
        version0, rendered0, _ = await ensure_identity_document(
            ctx.pool, agent, SEED_PROSE
        )
        assert rendered0 == SEED_PROSE
        assert (version0, rendered0) == tuple(
            reversed(render_identity_document(SEED_PROSE))
        )
        assert assemble_prose_prompt(rendered0, []) == (
            f"[identity]\n{SEED_PROSE}\n\n{_BLOCK_PROSE_INSTRUCTION}"
        )

        # An identity-relevant belief + recompile => the block carries it.
        belief = "[fixture] I have come to distrust strangers at dusk."
        await ctx.seed_reflection(agent, belief, NOW - timedelta(minutes=30))
        version1, rendered1, created = await ensure_identity_document(
            ctx.pool, agent, SEED_PROSE
        )
        assert created is True and version1 != version0
        assert rendered1 == f"{SEED_PROSE}\n\n{belief}"
        assert assemble_prose_prompt(rendered1, []) == (
            f"[identity]\n{SEED_PROSE}\n\n{belief}\n\n{_BLOCK_PROSE_INSTRUCTION}"
        )

        # The turn resolves the caller-frozen version; an unknown one is the
        # 422 class (both turn routes map it), a real one runs clean.
        dialogue = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )
        with pytest.raises(UnknownIdentityVersionError):
            await drain_turn(
                dialogue.run_dialogue_turn(
                    DialogueTurnRequest(
                        agent_id=agent,
                        utterance="Who goes there?",
                        as_of=NOW,
                        identity_version="no-such-version",
                        scene_started_at=NOW,
                    )
                )
            )
        _prose, result = await drain_turn(
            dialogue.run_dialogue_turn(
                DialogueTurnRequest(
                    agent_id=agent,
                    utterance="Who goes there?",
                    as_of=NOW,
                    identity_version=version1,
                    scene_started_at=NOW,
                )
            )
        )
        assert result.instrumentation.degraded is False

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The worker
# ---------------------------------------------------------------------------


def test_worker_sweep_kill_switch_and_pressure_threshold(scene):
    """Done-when 8 (core): sweep() is deterministic and timer-free; the
    per-agent kill-switch gates auto-pull only; a due agent reflects once
    per sweep with a `completed` run row; agents below threshold or
    disabled are untouched; the reflected agent's pressure resets so the
    next sweep is a no-op."""

    async def scenario(ctx):
        enabled = {
            **REFLECT_CONFIG,
            "reflection_worker_enabled": 1.0,
            "reflection_pressure_norm": 1.0,
        }
        due = await ctx.make_agent("l-due", enabled)
        quiet = await ctx.make_agent(
            "l-quiet", {**enabled, "reflection_pressure_norm": 100.0}
        )
        disabled = await ctx.make_agent(
            "l-disabled", {**REFLECT_CONFIG, "reflection_pressure_norm": 1.0}
        )
        for agent in (due, quiet, disabled):
            await _seed_floor(ctx, agent, n=4)

        worker = ctx.reflection_worker()
        assert await worker.sweep() == 1
        runs = await ctx.fetchall(
            "SELECT agent_id, outcome FROM reflection_runs ORDER BY created_at"
        )
        assert runs == [(due, "completed")]
        assert len(await _reflection_rows(ctx, due)) == 2
        assert await _reflection_rows(ctx, quiet) == []
        assert await _reflection_rows(ctx, disabled) == []

        # The reflect event consumed the pressure: the next sweep is a no-op.
        assert await worker.sweep() == 0
        assert len(await _reflection_rows(ctx, due)) == 2

        # Lifecycle: idempotent start/stop (both-site wiring is the walker's).
        worker.start()
        task = worker._task
        assert task is not None
        worker.start()
        assert worker._task is task
        await worker.stop()
        assert worker._task is None
        await worker.stop()

    run_structural(scene, scenario)


def test_worker_floor_skip_writes_no_run_row(scene):
    """The ladder's floor rung for the worker: pressure past threshold but
    below the episode floor => skip, NO run row (not a failure — pressure
    normally implies volume; only adversarial knobs reach this)."""

    async def scenario(ctx):
        config = {
            **REFLECT_CONFIG,
            "reflection_worker_enabled": 1.0,
            "reflection_pressure_norm": 0.01,
        }
        agent = await ctx.make_agent("l-thin", config)
        await ctx.seed(agent, T1, NOW - timedelta(hours=2))
        await ctx.seed(agent, T2, NOW - timedelta(hours=1))
        worker = ctx.reflection_worker()
        assert await worker.sweep() == 0
        assert await ctx.fetchall("SELECT run_id FROM reflection_runs") == []
        assert await _reflection_rows(ctx, agent) == []

    run_structural(scene, scenario)


def test_worker_failed_run_row_and_natural_retry(scene):
    """Done-when 8 (failure): a failing reflect leaves a `failed` run row
    with the worker alive; the pressure that triggered it persists, so the
    next sweep retries naturally (NO attempts ledger — the deliberate
    contrast with enrichment's budget); a later good sweep completes."""

    async def scenario(ctx):
        config = {
            **REFLECT_CONFIG,
            "reflection_worker_enabled": 1.0,
            "reflection_pressure_norm": 1.0,
        }
        agent = await ctx.make_agent("l-retry", config)
        await _seed_floor(ctx, agent, n=4)

        failing = ctx.reflection_worker(provider=FailingReflectionProvider())
        assert await failing.sweep() == 1
        assert await failing.sweep() == 1  # pressure persists => retried
        runs = await ctx.fetchall(
            "SELECT outcome, error, pressure_before, pressure_after "
            "FROM reflection_runs ORDER BY created_at"
        )
        assert [r[0] for r in runs] == ["failed", "failed"]
        assert all("reflect call failed" in r[1] for r in runs)
        assert all(r[2] == pytest.approx(2.0) for r in runs)
        assert all(r[3] is None for r in runs)
        assert await _reflection_rows(ctx, agent) == []

        good = ctx.reflection_worker()
        assert await good.sweep() == 1
        outcomes = [
            r[0]
            for r in await ctx.fetchall(
                "SELECT outcome FROM reflection_runs ORDER BY created_at"
            )
        ]
        assert outcomes == ["failed", "failed", "completed"]
        assert len(await _reflection_rows(ctx, agent)) == 2

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Pressure math + the role's config shape
# ---------------------------------------------------------------------------


def test_pressure_math_exact(scene):
    """The gauge: summed COALESCE(importance_raw, neutral) over live
    memories created after the last reflect EVENT (any reflection row, live
    or absorbed; all live memories when none), divided by the norm — served,
    never stored. A NULL-importance pending row counts at the neutral."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("l-pressure", REFLECT_CONFIG)
        await ctx.seed(agent, T1, NOW - timedelta(hours=3), importance=0.8)
        await ctx.seed(agent, T2, NOW - timedelta(hours=2), importance=0.2)
        await ctx.seed_pending(agent, T3, NOW - timedelta(hours=1))  # NULL imp
        mass = await db.reflection_pressure_mass(ctx.pool, agent, neutral=0.5)
        assert mass == pytest.approx(1.5)  # 0.8 + 0.2 + 0.5(neutral)

        # An absorbed (invalidated) reflection still marks the last event.
        await ctx.seed_reflection(
            agent,
            "[fixture] absorbed belief",
            NOW - timedelta(hours=1),
            invalid_at=NOW,
        )
        assert await db.reflection_pressure_mass(
            ctx.pool, agent, neutral=0.5
        ) == pytest.approx(0.0)

        # New memories after the event accumulate again.
        await ctx.seed(agent, T4, NOW, importance=0.4)
        assert await db.reflection_pressure_mass(
            ctx.pool, agent, neutral=0.5
        ) == pytest.approx(0.4)

        # The norm guard is loud, never a silent clamp.
        bad = ctx.reflection(defaults={"reflection_pressure_norm": 0.0})
        with pytest.raises(ValueError, match="reflection_pressure_norm"):
            await bad.reflect(agent, _request())

    run_structural(scene, scenario)


def test_reflect_route_contracts(scene):
    """The route mirrors the seam 1:1 (pass-through by ruling): 200 carrying
    the seam's serialization, 404 unknown agent, 409 below the floor, 422
    naive timestamp, 502 reflect-call failure — the ASGI-transport pattern
    (no lifespan, no loaders)."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("l-route", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        thin = await ctx.make_agent("l-route-thin", REFLECT_CONFIG)
        await ctx.seed(thin, T1, NOW - timedelta(hours=1))

        api_module.app.state.reflection = ctx.reflection()
        transport = httpx.ASGITransport(app=api_module.app)
        body = {"client_timestamp": NOW.isoformat()}
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.post(f"/v1/agents/{agent}/reflect", json=body)
            assert ok.status_code == 200
            payload = ok.json()
            assert payload["agent_id"] == str(agent)
            assert len(payload["reflections"]) == 2
            assert payload["sampled_memory_ids"]
            assert payload["rrr"] is None
            assert payload["consolidation"] is None
            assert payload["instrumentation"]["reflect_input_tokens"] > 0

            r404 = await client.post(f"/v1/agents/{uuid4()}/reflect", json=body)
            assert r404.status_code == 404

            r409 = await client.post(f"/v1/agents/{thin}/reflect", json=body)
            assert r409.status_code == 409
            assert "reflection_min_episodes" in r409.json()["detail"]

            naive = {"client_timestamp": "2026-08-15T12:00:00"}  # tz-naive
            r422 = await client.post(f"/v1/agents/{agent}/reflect", json=naive)
            assert r422.status_code == 422

            api_module.app.state.reflection = ctx.reflection(
                provider=FailingReflectionProvider()
            )
            r502 = await client.post(f"/v1/agents/{agent}/reflect", json=body)
            assert r502.status_code == 502
            assert "reflect call failed" in r502.json()["detail"]

    run_structural(scene, scenario)


def test_real_mode_config_error_at_first_use(scene):
    """Done-when 10: real mode LOADS without TWICETOLD_MODEL_REFLECTION (the
    Set I amendment asserts load_settings); the first real reflect without
    it raises ConfigError NAMING the var, with nothing written. Fake mode
    runs end to end on FakeReflectionProvider (every other scenario)."""

    async def scenario(ctx):
        from app.config import ConfigError

        agent = await ctx.make_agent("l-config", REFLECT_CONFIG)
        await _seed_floor(ctx, agent)
        real_settings = replace(ctx.settings, provider_mode="real")
        from app.reflection import ReflectionService

        service = ReflectionService(ctx.pool, ctx.providers(), real_settings)
        with pytest.raises(ConfigError, match="TWICETOLD_MODEL_REFLECTION"):
            await service.reflect(agent, _request())
        assert await _reflection_rows(ctx, agent) == []

    run_structural(scene, scenario)
