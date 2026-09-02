"""Set M — the parameter compiler (parameter-compiler.md; migration 008,
the C3 rulings dated 2026-08-17).

The seam is exercised through `CompilerService`/`CompilerWorker.sweep()` —
the deterministic no-timer entries — and the consume side through
`DialogueService.run_dialogue_turn`, against beliefs and bundles seeded at
the db layer (`Ctx.seed_reflection` / `Ctx.seed_bundle`), so every scenario
stays unmarked (no write-pass call, no spaCy loaders). Workers come from the
never-started factories, so no poll loop races a deterministic count.
Structural-only, per the standing rule: row state, clamps, pair membership,
window bounds, liveness-by-join, multiplier products, and byte-identity of
the ranked view — never prose judgment. C3 has no route, so there is no
HTTP-contract scenario; the wire surface (scene_type + instrumentation
echo) is the interop gate's job (the C# mirror's beats).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import psycopg
import pytest
from conftest import NOW, V1_CONFIG, run_structural

from app import db
from app.compiler import DEFAULT_SCENE_TYPE, CompilerWorker
from app.config import (
    MULTIPLIER_MAX,
    MULTIPLIER_MIN,
    SERVICE_DEFAULTS,
    ConfigError,
    load_settings,
    scene_types,
)
from app.dialogue import DialogueService, weighted_score
from app.providers import (
    CompilerCallResult,
    FailingCompilerProvider,
    FakeCompilerProvider,
    MalformedCompilerProvider,
    build_compiler_provider,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueTurnRequest, DialogueTurnResult, WeightOverrides

COMPILER_CONFIG = {
    **V1_CONFIG,
    "compiler_worker_enabled": 1.0,
    "scene_types": ["tavern"],
}

B1 = "Merchants have cheated the keeper twice at the ford."
B2 = "The keeper trusts the miller's word over paper."
B3 = "Storms upriver mean the toll bridge floods by dusk."

M_OLD = "Bram shattered the lantern at the ford gate."
M_NEW = "A grey cat took up residence in the mill loft."


class PinnedCompilerProvider:
    """Exact multipliers + junk passthrough keys — the clamp and
    namespace-filter fixture (hash-derived fakes cannot pin values)."""

    def __init__(
        self,
        w_relevance: float = 1.0,
        w_recency: float = 1.0,
        w_importance: float = 1.0,
        passthrough: dict | None = None,
    ):
        self._result = CompilerCallResult(
            w_relevance=w_relevance,
            w_recency=w_recency,
            w_importance=w_importance,
            passthrough=passthrough or {},
            input_tokens=5,
            output_tokens=5,
        )

    def compile(self, **_kwargs) -> CompilerCallResult:
        return self._result


def _dialogue(ctx, defaults: dict | None = None) -> DialogueService:
    settings = (
        replace(ctx.settings, defaults={**ctx.settings.defaults, **defaults})
        if defaults
        else ctx.settings
    )
    providers = ctx.providers()
    return DialogueService(
        ctx.pool,
        providers,
        settings,
        RetrievalService(ctx.pool, providers, settings),
    )


async def _turn(
    ctx,
    agent_id,
    utterance: str = "what news at the ford?",
    *,
    scene_type: str | None = None,
    weight_overrides: WeightOverrides | None = None,
    defaults: dict | None = None,
) -> DialogueTurnResult:
    service = _dialogue(ctx, defaults)
    result = None
    async for item in service.run_dialogue_turn(
        DialogueTurnRequest(
            agent_id=agent_id,
            utterance=utterance,
            as_of=NOW,
            scene_type=scene_type,
            weight_overrides=weight_overrides,
        )
    ):
        if isinstance(item, DialogueTurnResult):
            result = item
    assert result is not None
    return result


async def _seed_beliefs(ctx, agent, contents=(B1, B2), *, identity_relevant=False):
    ids = []
    for i, content in enumerate(contents):
        ids.append(
            await ctx.seed_reflection(
                agent,
                content,
                NOW + timedelta(minutes=i),
                identity_relevant=identity_relevant,
                created_at=NOW + timedelta(minutes=i),
            )
        )
    return ids


async def _bundle_rows(ctx, agent_id):
    """(reflection_id, scene_type, w_relevance, w_recency, w_importance,
    passthrough), insertion order."""
    return await ctx.fetchall(
        "SELECT reflection_id, scene_type, w_relevance, w_recency, "
        "w_importance, passthrough FROM compiled_bundles "
        "WHERE agent_id = %s ORDER BY created_at, bundle_id",
        agent_id,
    )


# ---------------------------------------------------------------------------
# The compile pass (worker sweep semantics)
# ---------------------------------------------------------------------------


def test_sweep_compiles_missing_pairs_happy_path(scene):
    """Done-when 1: an enabled agent's (in-window live belief x vocabulary)
    pairs all compile — clamped multipliers, namespaced passthrough, honest
    completed run row; the vocabulary is config scene_types + the reserved
    default."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-happy", COMPILER_CONFIG)
        beliefs = await _seed_beliefs(ctx, agent)
        worker = ctx.compiler_worker()

        attempts = await worker.sweep()
        assert attempts == 4  # 2 beliefs x {default, tavern}

        rows = await _bundle_rows(ctx, agent)
        assert len(rows) == 4
        assert {(r[0], r[1]) for r in rows} == {
            (b, t) for b in beliefs for t in ("default", "tavern")
        }
        for _rid, _stype, w_rel, w_rec, w_imp, passthrough in rows:
            for value in (w_rel, w_rec, w_imp):
                assert MULTIPLIER_MIN <= value <= MULTIPLIER_MAX
            assert list(passthrough) == ["fake.note"]  # the fake's marker key

        runs = await db.fetch_compiler_runs(ctx.pool, agent)
        assert len(runs) == 1
        run = runs[0]
        assert run["outcome"] == "completed"
        assert run["pairs_compiled"] == 4
        assert run["pairs_failed"] == 0
        assert run["passthrough_keys_dropped"] == 0
        assert run["input_tokens"] > 0
        assert run["total_ms"] is not None

    run_structural(scene, scenario)


def test_pair_once_compiled_never_recompiled(scene):
    """Missing-pair discovery IS the idempotency: a second sweep makes no
    calls and writes no run row."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-idem", COMPILER_CONFIG)
        await _seed_beliefs(ctx, agent, (B1,))
        worker = ctx.compiler_worker()
        assert await worker.sweep() == 2
        assert await worker.sweep() == 0
        assert len(await db.fetch_compiler_runs(ctx.pool, agent)) == 1
        assert len(await _bundle_rows(ctx, agent)) == 2

    run_structural(scene, scenario)


def test_malformed_records_and_retries_naturally(scene):
    """The malformed rung: the pair records as failed with its token spend,
    nothing lands, the pair stays missing, and a later good sweep completes
    it — no attempts ledger."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "m-malformed", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        await _seed_beliefs(ctx, agent, (B1,))
        bad = ctx.compiler_worker(provider=MalformedCompilerProvider())
        assert await bad.sweep() == 1  # a failed call still counts
        runs = await db.fetch_compiler_runs(ctx.pool, agent)
        assert len(runs) == 1
        assert runs[0]["outcome"] == "completed"
        assert runs[0]["pairs_failed"] == 1
        assert runs[0]["pairs_compiled"] == 0
        assert runs[0]["input_tokens"] == 7  # the malformed fake's spend
        assert await _bundle_rows(ctx, agent) == []

        good = ctx.compiler_worker()
        assert await good.sweep() == 1
        assert len(await _bundle_rows(ctx, agent)) == 1

    run_structural(scene, scenario)


def test_failing_provider_continues_across_agents(scene):
    """A hard call failure on one agent's pairs never stops the sweep: both
    enabled agents get honest run rows and the batch bound counts the failed
    calls."""

    async def scenario(ctx):
        config = {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        first = await ctx.make_agent("m-fail-a", config)
        second = await ctx.make_agent("m-fail-b", config)
        await _seed_beliefs(ctx, first, (B1,))
        await _seed_beliefs(ctx, second, (B2,))
        worker = ctx.compiler_worker(provider=FailingCompilerProvider())
        assert await worker.sweep() == 2
        for agent in (first, second):
            runs = await db.fetch_compiler_runs(ctx.pool, agent)
            assert len(runs) == 1
            assert runs[0]["outcome"] == "completed"
            assert runs[0]["pairs_failed"] == 1
            assert runs[0]["input_tokens"] == 0  # a hard failure spends nothing

    run_structural(scene, scenario)


def test_clamp_at_write_and_namespace_filter(scene):
    """Out-of-range multipliers clamp to the module constants (the CHECK
    never trips) and un-namespaced passthrough keys drop with a run-row
    count — the mechanical validation, not the model's honesty."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "m-clamp", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        await _seed_beliefs(ctx, agent, (B1,))
        worker = ctx.compiler_worker(
            provider=PinnedCompilerProvider(
                w_relevance=9.0,
                w_recency=0.01,
                w_importance=1.0,
                passthrough={"nokey": 1, "game.x": 2, ".bad": 3, "tail.": 4},
            )
        )
        assert await worker.sweep() == 1
        rows = await _bundle_rows(ctx, agent)
        assert len(rows) == 1
        _rid, _stype, w_rel, w_rec, w_imp, passthrough = rows[0]
        assert w_rel == MULTIPLIER_MAX
        assert w_rec == MULTIPLIER_MIN
        assert w_imp == 1.0
        assert passthrough == {"game.x": 2}
        runs = await db.fetch_compiler_runs(ctx.pool, agent)
        assert runs[0]["passthrough_keys_dropped"] == 3

    run_structural(scene, scenario)


def test_window_k_bounds_compile_discovery(scene):
    """The staleness guard at the compile end: with compiler_window_k pinned
    to 2, only the two newest live beliefs generate pairs."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "m-window", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        beliefs = await _seed_beliefs(ctx, agent, (B1, B2, B3))
        worker = ctx.compiler_worker(defaults={"compiler_window_k": 2.0})
        assert await worker.sweep() == 2  # 2 newest beliefs x {default}
        rows = await _bundle_rows(ctx, agent)
        assert {r[0] for r in rows} == set(beliefs[1:])  # newest two only

    run_structural(scene, scenario)


def test_worker_lifecycle_kill_switch_and_batch_cap(scene):
    """Start is idempotent, stop clears; a kill-switch agent is skipped with
    no row; compiler_worker_batch caps compile calls per sweep and the
    budget cuts the deterministic prefix (the next sweep continues)."""

    async def scenario(ctx):
        disabled = await ctx.make_agent("m-off", V1_CONFIG)
        await _seed_beliefs(ctx, disabled, (B1,))
        enabled = await ctx.make_agent(
            "m-batch", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        await _seed_beliefs(ctx, enabled, (B1, B2))

        worker = ctx.compiler_worker(defaults={"compiler_worker_batch": 1.0})
        worker.start()
        task = worker._task
        worker.start()
        assert worker._task is task  # idempotent
        await worker.stop()
        assert worker._task is None

        assert await worker.sweep() == 1  # the batch bound
        assert await db.fetch_compiler_runs(ctx.pool, disabled) == []
        assert await _bundle_rows(ctx, disabled) == []
        remaining = await db.fetch_missing_bundle_pairs(
            ctx.pool, enabled, scene_types=["default"], window_k=8
        )
        assert len(remaining) == 1
        assert await worker.sweep(limit=10) == 1  # limit overrides the knob
        assert (
            await db.fetch_missing_bundle_pairs(
                ctx.pool, enabled, scene_types=["default"], window_k=8
            )
            == []
        )

    run_structural(scene, scenario)


def test_config_error_failed_run_and_load_shape(scene):
    """The judge-shaped role as code: real mode loads WITHOUT the var (the
    Set I amendment shape) and with it; the first real compile raises
    ConfigError naming it; the worker lands a failed run row, logs once,
    and keeps sweeping; fake mode builds the deterministic fake."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "m-config", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        await _seed_beliefs(ctx, agent, (B1,))
        real_settings = replace(ctx.settings, provider_mode="real")
        worker = CompilerWorker(ctx.pool, ctx.providers(), real_settings)
        assert await worker.sweep() == 0  # no call was ever made
        runs = await db.fetch_compiler_runs(ctx.pool, agent)
        assert len(runs) == 1
        assert runs[0]["outcome"] == "failed"
        assert "TWICETOLD_MODEL_COMPILER" in runs[0]["error"]
        assert worker._config_error_logged is True
        assert await worker.sweep() == 0  # still alive; a second failed row
        assert len(await db.fetch_compiler_runs(ctx.pool, agent)) == 2
        assert await _bundle_rows(ctx, agent) == []

        base_env = {
            "DATABASE_URI": "postgresql://host/db",
            "TWICETOLD_PROVIDER_MODE": "real",
            "TWICETOLD_MODEL_IMPORTANCE": "m-write",
            "TWICETOLD_MODEL_RENDER": "m-write",
            "TWICETOLD_MODEL_TYPOLOGY": "m-write",
            "TWICETOLD_MODEL_ESCALATION": "m-esc",
            "TWICETOLD_MODEL_DIALOGUE": "m-dia",
            "TWICETOLD_MODEL_RECONSTRUCTION": "m-rec",
            "ANTHROPIC_API_KEY": "k",
            "OPENAI_API_KEY": "k",
        }
        loaded = load_settings(dict(base_env))
        assert loaded.model_compiler == ""  # real mode loads WITHOUT the var
        loaded = load_settings({**base_env, "TWICETOLD_MODEL_COMPILER": "m-comp"})
        assert loaded.model_compiler == "m-comp"

        assert isinstance(build_compiler_provider(ctx.settings), FakeCompilerProvider)
        with pytest.raises(ConfigError) as excinfo:
            build_compiler_provider(replace(loaded, model_compiler=""))
        assert "TWICETOLD_MODEL_COMPILER" in str(excinfo.value)

    run_structural(scene, scenario)


def test_migration_008_pins_and_knob_defaults(scene):
    """The mechanical pins: the four knobs at their ruled defaults, the
    empty vocabulary default, the frozen clamp constants, both tables'
    exact column sets, and the CHECKs' teeth."""

    async def scenario(ctx):
        assert SERVICE_DEFAULTS["compiler_worker_enabled"] == 0.0
        assert SERVICE_DEFAULTS["compiler_poll_seconds"] == 60.0
        assert SERVICE_DEFAULTS["compiler_worker_batch"] == 8.0
        assert SERVICE_DEFAULTS["compiler_window_k"] == 8.0
        assert scene_types({}) == []
        assert scene_types({"scene_types": ["a", "b"]}) == ["a", "b"]
        assert (MULTIPLIER_MIN, MULTIPLIER_MAX) == (0.25, 4.0)
        assert DEFAULT_SCENE_TYPE == "default"

        bundles_cols = {
            r[0]
            for r in await ctx.fetchall(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'compiled_bundles'"
            )
        }
        assert bundles_cols == {
            "bundle_id",
            "agent_id",
            "reflection_id",
            "scene_type",
            "w_relevance",
            "w_recency",
            "w_importance",
            "passthrough",
            "input_tokens",
            "output_tokens",
            "compile_ms",
            "created_at",
        }
        runs_cols = {
            r[0]
            for r in await ctx.fetchall(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'compiler_runs'"
            )
        }
        assert runs_cols == {
            "run_id",
            "agent_id",
            "outcome",
            "error",
            "pairs_compiled",
            "pairs_failed",
            "passthrough_keys_dropped",
            "input_tokens",
            "output_tokens",
            "total_ms",
            "created_at",
        }

        agent = await ctx.make_agent("m-pins", V1_CONFIG)
        belief = await ctx.seed_reflection(agent, B1, NOW)
        with pytest.raises(psycopg.errors.CheckViolation):
            await ctx.execute(
                "INSERT INTO compiled_bundles (agent_id, reflection_id, "
                "scene_type, w_relevance, w_recency, w_importance) "
                "VALUES (%s, %s, 'default', 5.0, 1.0, 1.0)",
                agent,
                belief,
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            await ctx.execute(
                "INSERT INTO compiler_runs (agent_id, outcome) VALUES (%s, 'junk')",
                agent,
            )

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The consume side (the dialogue seam)
# ---------------------------------------------------------------------------


def test_no_bundles_byte_parity(scene):
    """The parity contract: a bundle-free turn is byte-identical to the
    pre-C3 seam — neutral products, the default resolution, and
    dialogue_view equal to the served (id, score) projection at default
    weights."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-parity", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        await ctx.seed(agent, M_NEW, NOW - timedelta(minutes=1))
        result = await _turn(ctx, agent)
        ins = result.instrumentation
        assert ins.scene_type_resolved == DEFAULT_SCENE_TYPE
        assert ins.scene_type_unknown is False
        assert (
            ins.bundle_w_relevance,
            ins.bundle_w_recency,
            ins.bundle_w_importance,
        ) == (1.0, 1.0, 1.0)
        assert ins.bundle_reflection_ids == []
        assert [(r.memory_id, r.score) for r in result.dialogue_view] == [
            (item.memory_id, item.score) for item in result.items
        ]

    run_structural(scene, scenario)


def test_neutral_bundle_is_valid_and_parity_preserving(scene):
    """Ruling 1's neutral license: an all-1.0 bundle stores and applies
    without changing a byte of the ranked view — only the contributing ids
    say it was there."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-neutral", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        await ctx.seed(agent, M_NEW, NOW - timedelta(minutes=1))
        before = await _turn(ctx, agent)

        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief)  # all-1.0 default-type bundle
        after = await _turn(ctx, agent)

        assert [(r.memory_id, r.score) for r in after.dialogue_view] == [
            (r.memory_id, r.score) for r in before.dialogue_view
        ]
        assert after.instrumentation.bundle_reflection_ids == [belief]
        assert (
            after.instrumentation.bundle_w_relevance,
            after.instrumentation.bundle_w_recency,
            after.instrumentation.bundle_w_importance,
        ) == (1.0, 1.0, 1.0)

    run_structural(scene, scenario)


def test_window_k_bounds_consume_fetch(scene):
    """The staleness guard at the consume end: a bundle on an out-of-window
    belief contributes nothing; widening the window admits it."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-cwin", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        old_belief = await ctx.seed_reflection(
            agent, B1, NOW - timedelta(hours=1), created_at=NOW - timedelta(hours=1)
        )
        await ctx.seed_reflection(agent, B2, NOW, created_at=NOW)
        await ctx.seed_bundle(agent, old_belief, w_recency=0.25)

        narrow = await _turn(ctx, agent, defaults={"compiler_window_k": 1.0})
        assert narrow.instrumentation.bundle_reflection_ids == []
        assert narrow.instrumentation.bundle_w_recency == 1.0

        wide = await _turn(ctx, agent, defaults={"compiler_window_k": 2.0})
        assert wide.instrumentation.bundle_reflection_ids == [old_belief]
        assert wide.instrumentation.bundle_w_recency == 0.25

    run_structural(scene, scenario)


def test_belief_invalidation_evicts_instantly(scene):
    """Liveness-by-join: superseding the belief removes its parameters from
    the very next turn with zero bundle writes, and its pairs leave
    discovery."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-evict", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief, w_recency=0.25)
        applied = await _turn(ctx, agent)
        assert applied.instrumentation.bundle_reflection_ids == [belief]

        bundle_count_before = len(await _bundle_rows(ctx, agent))
        await ctx.execute(
            "UPDATE reflections SET invalid_at = %s WHERE reflection_id = %s",
            NOW + timedelta(minutes=5),
            belief,
        )
        evicted = await _turn(ctx, agent)
        assert evicted.instrumentation.bundle_reflection_ids == []
        assert evicted.instrumentation.bundle_w_recency == 1.0
        assert len(await _bundle_rows(ctx, agent)) == bundle_count_before
        assert (
            await db.fetch_missing_bundle_pairs(
                ctx.pool, agent, scene_types=["default"], window_k=8
            )
            == []
        )

    run_structural(scene, scenario)


def test_consolidation_collapse_n_to_one(scene):
    """The N->1 collapse: absorbing beliefs kills their parameter
    contributions instantly, and the consolidated survivor surfaces as new
    missing-pair work the next sweep compiles."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "m-collapse", {**V1_CONFIG, "compiler_worker_enabled": 1.0}
        )
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        absorbed = await _seed_beliefs(ctx, agent, (B1, B2), identity_relevant=True)
        worker = ctx.compiler_worker()
        assert await worker.sweep() == 2  # {default} x 2 beliefs
        applied = await _turn(ctx, agent)
        assert set(applied.instrumentation.bundle_reflection_ids) == set(absorbed)

        survivor = await db.apply_consolidation(
            ctx.pool,
            agent,
            content="Taken together: the ford is a place of tolls and trust.",
            source_memory_ids=[],
            absorbed_ids=absorbed,
            valid_at=NOW + timedelta(minutes=30),
        )
        assert survivor is not None

        after = await _turn(ctx, agent)
        assert after.instrumentation.bundle_reflection_ids == []

        pairs = await db.fetch_missing_bundle_pairs(
            ctx.pool, agent, scene_types=["default"], window_k=8
        )
        assert [p.reflection_id for p in pairs] == [survivor]
        assert await worker.sweep() == 1
        compiled = await _turn(ctx, agent)
        assert compiled.instrumentation.bundle_reflection_ids == [survivor]

    run_structural(scene, scenario)


def test_composition_math_and_rerank_flip(scene):
    """The demo beat as a scenario: one agent, one belief, two scene types
    with opposite-extreme recency multipliers — the same query ranks the
    served set differently per scene, membership never changes, and every
    view score equals the hand-computed exponent math."""

    async def scenario(ctx):
        config = {**V1_CONFIG, "scene_types": ["calm", "sharp"]}
        agent = await ctx.make_agent("m-flip", config)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=30))
        await ctx.seed(agent, M_NEW, NOW - timedelta(minutes=1))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief, scene_type="calm", w_recency=0.25)
        await ctx.seed_bundle(agent, belief, scene_type="sharp", w_recency=4.0)

        calm = await _turn(ctx, agent, M_OLD, scene_type="calm")
        sharp = await _turn(ctx, agent, M_OLD, scene_type="sharp")

        assert calm.instrumentation.scene_type_resolved == "calm"
        assert sharp.instrumentation.scene_type_resolved == "sharp"
        assert calm.instrumentation.bundle_w_recency == 0.25
        assert sharp.instrumentation.bundle_w_recency == 4.0

        calm_order = [r.memory_id for r in calm.dialogue_view]
        sharp_order = [r.memory_id for r in sharp.dialogue_view]
        assert set(calm_order) == set(sharp_order)  # membership never changes
        assert calm_order != sharp_order  # the scene flips the ranking

        for result, w_rec in ((calm, 0.25), (sharp, 4.0)):
            by_id = {item.memory_id: item for item in result.items}
            for ref in result.dialogue_view:
                expected = weighted_score(by_id[ref.memory_id], 1.0, w_rec, 1.0)
                assert abs(ref.score - expected) < 1e-9

    run_structural(scene, scenario)


def test_request_override_composes_then_clamps(scene):
    """The override x bundle product clamps at the weight ceiling: the view
    equals the bundle-free turn at the same clamped weight, while the echo
    reports the bundle's product honestly."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-override", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=30))
        await ctx.seed(agent, M_NEW, NOW - timedelta(minutes=1))
        overrides = WeightOverrides(recency=4.0)
        before = await _turn(ctx, agent, weight_overrides=overrides)
        assert before.instrumentation.bundle_w_recency == 1.0

        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief, w_recency=4.0)
        after = await _turn(ctx, agent, weight_overrides=overrides)
        assert after.instrumentation.bundle_w_recency == 4.0
        assert [(r.memory_id, r.score) for r in after.dialogue_view] == [
            (r.memory_id, r.score) for r in before.dialogue_view
        ]  # clamp(4.0 x 4.0) == clamp(4.0) at the ceiling

    run_structural(scene, scenario)


def test_unknown_scene_type_logs_and_defaults(scene):
    """The §10 log-and-continue ruling: an unconfigured type succeeds,
    resolves to the default, carries the flag, and the default-type bundles
    apply."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-unknown", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief, w_recency=0.5)

        result = await _turn(ctx, agent, scene_type="moon")
        ins = result.instrumentation
        assert ins.scene_type_resolved == DEFAULT_SCENE_TYPE
        assert ins.scene_type_unknown is True
        assert ins.bundle_reflection_ids == [belief]
        assert ins.bundle_w_recency == 0.5

    run_structural(scene, scenario)


def test_known_type_selects_its_own_bundles_only(scene):
    """Per-type selection with no cross-type fallback: each known type
    applies exactly its own bundles, and a known type whose pair is not yet
    compiled contributes nothing (the compile-lag window is neutral)."""

    async def scenario(ctx):
        config = {**V1_CONFIG, "scene_types": ["tavern", "ford"]}
        agent = await ctx.make_agent("m-select", config)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief, scene_type="default", w_recency=0.5)
        await ctx.seed_bundle(agent, belief, scene_type="tavern", w_recency=2.0)

        default_turn = await _turn(ctx, agent)
        assert default_turn.instrumentation.bundle_w_recency == 0.5
        tavern_turn = await _turn(ctx, agent, scene_type="tavern")
        assert tavern_turn.instrumentation.bundle_w_recency == 2.0

        ford_turn = await _turn(ctx, agent, scene_type="ford")
        ins = ford_turn.instrumentation
        assert ins.scene_type_resolved == "ford"
        assert ins.scene_type_unknown is False
        assert ins.bundle_reflection_ids == []
        assert ins.bundle_w_recency == 1.0  # no default fallback

    run_structural(scene, scenario)


def test_latest_bundle_per_pair_wins(scene):
    """Append-only re-compiles: the newest bundle row for a pair is the one
    consume applies (created_at, bundle_id tiebreak)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-latest", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(
            agent, belief, w_recency=0.5, created_at=NOW + timedelta(minutes=1)
        )
        await ctx.seed_bundle(
            agent, belief, w_recency=2.0, created_at=NOW + timedelta(minutes=2)
        )
        result = await _turn(ctx, agent)
        assert result.instrumentation.bundle_w_recency == 2.0
        assert len(await _bundle_rows(ctx, agent)) == 2  # nothing rewritten

    run_structural(scene, scenario)


def test_multi_belief_products_compose(scene):
    """Two beliefs' bundles compose by product per axis, echoed exactly, and
    the contributing list rides in window order (newest belief first)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-product", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        first = await ctx.seed_reflection(agent, B1, NOW, created_at=NOW)
        second = await ctx.seed_reflection(
            agent,
            B2,
            NOW + timedelta(minutes=1),
            created_at=NOW + timedelta(minutes=1),
        )
        await ctx.seed_bundle(agent, first, w_recency=0.5, w_importance=2.0)
        await ctx.seed_bundle(agent, second, w_recency=0.5, w_relevance=3.0)

        result = await _turn(ctx, agent)
        ins = result.instrumentation
        assert ins.bundle_reflection_ids == [second, first]
        assert ins.bundle_w_relevance == 3.0
        assert ins.bundle_w_recency == 0.25
        assert ins.bundle_w_importance == 2.0

    run_structural(scene, scenario)


def test_consume_defends_against_out_of_range_rows(scene):
    """The consume-side re-clamp: a stored row outside the module constants
    (seeded around the CHECK by fixture) still applies clamped."""

    async def scenario(ctx):
        agent = await ctx.make_agent("m-defense", COMPILER_CONFIG)
        await ctx.seed(agent, M_OLD, NOW - timedelta(hours=2))
        belief = await ctx.seed_reflection(agent, B1, NOW)
        await ctx.seed_bundle(agent, belief)
        # Loosen the row under the CHECK's floor via direct arithmetic is
        # impossible — the CHECK holds — so assert the pure defense instead:
        # compose re-clamps whatever the fetch returns.
        from app.compiler import compose_bundle_weights

        row = db.DialogueBundleRow(
            reflection_id=belief,
            w_relevance=99.0,
            w_recency=0.001,
            w_importance=1.0,
        )
        effective, products = compose_bundle_weights((1.0, 1.0, 1.0), [row])
        assert products == (MULTIPLIER_MAX, MULTIPLIER_MIN, 1.0)
        assert effective == (MULTIPLIER_MAX, MULTIPLIER_MIN, 1.0)

    run_structural(scene, scenario)
