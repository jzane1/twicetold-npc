"""compiler.py — THE parameter-compile seam (docs\\parameter-compiler.md;
the C3 rulings dated 2026-08-17): live beliefs compiled into per-scene-type
weight-multiplier bundles, an all-mechanical staleness guard (the K-window +
liveness-by-join + hard clamps), and the standalone CompilerWorker — C3's
ONLY scheduler, since the standalone-worker ruling gives this component no
endpoint verb and no route.

One service seam — `CompilerService.compile_agent` — used only by the
worker (`sweep()` is also the REPL's `:compile` and the walkers'
deterministic entry). No SQL lives here (repo hygiene; the reads/writes are
app\\db.py's parameter-compiler section). The model provider is built
lazily at first use via build_compiler_provider (the judge shape: never a
Providers-bundle field; a real-mode compile without TWICETOLD_MODEL_COMPILER
raises ConfigError loudly, the server having started fine without it).
Tests inject Failing/Malformed fakes through the keyword-only
`compiler_provider` seam (the C2 build precedent).

Degradation ladder (every rung a Set M scenario or walker criterion):
  - kill-switch (compiler_worker_enabled 0.0)  -> the sweep skips the
    agent entirely; NO run row
  - no missing pairs                           -> nothing to do; NO run row
    (missing-pair discovery IS the idempotency — a compiled pair never
    re-enters the work list)
  - one pair's call fails / malformed          -> pairs_failed counts, the
    other pairs proceed, nothing lands for the failed pair; the pair stays
    missing and the next sweep retries naturally (NO attempts ledger — the
    reflection contrast-with-enrichment stance, inherited)
  - real mode without the model role           -> ConfigError at the first
    pair: a `failed` run row, logged loud ONCE, the worker keeps running
  - budget exhausted mid-agent                 -> the remaining pairs stay
    missing; the next sweep continues them (deterministic order, so the
    budget cuts a stable prefix).

The staleness guard binds BOTH ends: work discovery and the consume fetch
window the same K most recent live beliefs (`compiler_window_k`), a belief's
bundles stop applying the instant the belief is superseded or absorbed
(liveness derived by join — zero bundle writes), and multipliers are
clamped at write AND re-clamped at consume (module constants
MULTIPLIER_MIN/MAX, frozen into migration 008's CHECK by ruling).
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db
from app.config import (
    MULTIPLIER_MAX,
    MULTIPLIER_MIN,
    WEIGHT_MAX,
    WEIGHT_MIN,
    ConfigError,
    Settings,
    agent_knob,
    scene_types,
)
from app.providers import (
    CompilerItem,
    CompilerProvider,
    MalformedOutputError,
    Providers,
    ProviderCallError,
    build_compiler_provider,
)

logger = logging.getLogger(__name__)

# The reserved scene type: always in the compile vocabulary, and the
# resolution target for an absent or unknown request type (the §10
# log-and-continue ruling). Never integrator policy — the vocabulary
# itself is the agents.config `scene_types` list.
DEFAULT_SCENE_TYPE = "default"


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Pure functions (the dialogue/reflection precedent: module-level and
# byte-stable so walkers assert them without a DB or model).
# ---------------------------------------------------------------------------

# The clamp bounds ride the prompt from the module constants — never a
# second hardcoded copy.
_COMPILE_SYSTEM = (
    "You compile ONE formed belief of a game NPC into numeric memory-"
    "weighting multipliers for ONE scene type. Return ONLY a JSON object:\n"
    '{"multipliers": {"relevance": <float>, "recency": <float>, '
    '"importance": <float>}, "passthrough": {"<namespace.key>": <value>}}\n'
    "Each multiplier scales how strongly that axis ranks the NPC's served "
    "memories while it speaks in scenes of the given type: 1.0 is neutral, "
    "above 1.0 amplifies the axis, below 1.0 dampens it; values are clamped "
    f"to [{MULTIPLIER_MIN}, {MULTIPLIER_MAX}]. Emit 1.0 for every axis the "
    "belief does not bear on — a fully neutral answer is valid. "
    '"passthrough" is optional: keys MUST be namespaced (like '
    '"game.aggression") and are stored for the game engine, never '
    "interpreted here; un-namespaced keys are dropped."
)


def assemble_compiler_prompt(
    content: str, identity_relevant: bool, scene_type: str
) -> tuple[str, str]:
    """The compile call's (system, user) pair — pure and byte-stable."""
    user_content = (
        f"[belief]\n{content}\n\n"
        f"[identity-relevant]\n{'yes' if identity_relevant else 'no'}\n\n"
        f"[scene type]\n{scene_type}"
    )
    return _COMPILE_SYSTEM, user_content


def resolve_scene_type(config: dict, requested: str | None) -> tuple[str, bool]:
    """The consume side's resolution: a configured (or the reserved) type
    resolves to itself; an unknown type resolves to the default WITH the
    unknown flag (log-and-continue is the caller's job); absent resolves to
    the default silently — absent is not unknown."""
    if not requested:
        return DEFAULT_SCENE_TYPE, False
    if requested == DEFAULT_SCENE_TYPE or requested in scene_types(config):
        return requested, False
    return DEFAULT_SCENE_TYPE, True


def clamp_multiplier(value: float) -> float:
    """The write clamp (re-applied at consume as defense): one belief moves
    one axis by at most the ruled range — migration 008's CHECK is the
    backstop, this is the validator."""
    return _clamp(float(value), MULTIPLIER_MIN, MULTIPLIER_MAX)


def sanitize_passthrough(raw: dict) -> tuple[dict, int]:
    """The mechanical namespace filter (the dropped-ungrounded precedent):
    a key survives only with a non-empty namespace, a dot, and a non-empty
    tail. Values pass through untouched — the server never interprets
    them."""
    clean: dict = {}
    dropped = 0
    for key, value in raw.items():
        name = str(key)
        head, dot, tail = name.partition(".")
        if head and dot and tail:
            clean[name] = value
        else:
            dropped += 1
    return clean, dropped


def compose_bundle_weights(
    base: tuple[float, float, float], bundles: list[db.DialogueBundleRow]
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The consume composition: per-axis product of the contributing
    bundles' multipliers (each re-clamped as defense), then the effective
    weight = clamp(base x product) into the existing [WEIGHT_MIN,
    WEIGHT_MAX] range. Zero bundles compose to the identity — the parity
    contract: without bundles the effective weights ARE the resolved base,
    byte-for-byte."""
    products = [1.0, 1.0, 1.0]
    for bundle in bundles:
        products[0] *= clamp_multiplier(bundle.w_relevance)
        products[1] *= clamp_multiplier(bundle.w_recency)
        products[2] *= clamp_multiplier(bundle.w_importance)
    effective = (
        _clamp(base[0] * products[0], WEIGHT_MIN, WEIGHT_MAX),
        _clamp(base[1] * products[1], WEIGHT_MIN, WEIGHT_MAX),
        _clamp(base[2] * products[2], WEIGHT_MIN, WEIGHT_MAX),
    )
    return effective, (products[0], products[1], products[2])


# ---------------------------------------------------------------------------
# The service and the worker
# ---------------------------------------------------------------------------


class CompilerService:
    """THE compile pass for one agent. Constructed like every seam —
    (pool, providers, settings) — with the keyword-only `compiler_provider`
    test seam; None means the lazy judge-shaped factory at first use (where
    real mode without the var fails loud). The provider is built only when
    missing pairs exist, so an idle agent never trips the ConfigError."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        *,
        compiler_provider: CompilerProvider | None = None,
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings
        self._compiler_provider = compiler_provider

    def _provider(self) -> CompilerProvider:
        if self._compiler_provider is None:
            self._compiler_provider = build_compiler_provider(self._settings)
        return self._compiler_provider

    async def compile_agent(
        self, agent_id: UUID, config: dict, *, budget: int
    ) -> db.CompilerRunRecord | None:
        """One pass: discover the missing (in-window live belief x scene
        type) pairs, compile up to `budget` of them in the deterministic
        order, land each validated bundle as it arrives. Returns the run
        record for the WORKER to persist (the reflection split: run rows
        are the worker's accounting), or None when there was no work —
        a no-work pass writes nothing."""
        if budget <= 0:
            return None
        t_total = time.perf_counter()
        window_k = int(agent_knob(config, "compiler_window_k", self._settings))
        vocabulary = sorted({DEFAULT_SCENE_TYPE, *scene_types(config)})
        pairs = await db.fetch_missing_bundle_pairs(
            self._pool, agent_id, scene_types=vocabulary, window_k=window_k
        )
        if not pairs:
            return None
        provider = self._provider()  # ConfigError surfaces here, loud

        pairs_compiled = 0
        pairs_failed = 0
        keys_dropped = 0
        input_tokens = 0
        output_tokens = 0
        for pair in pairs[:budget]:
            item = CompilerItem(
                reflection_id=str(pair.reflection_id),
                content=pair.content,
                identity_relevant=pair.identity_relevant,
                scene_type=pair.scene_type,
            )
            system_prompt, user_content = assemble_compiler_prompt(
                pair.content, pair.identity_relevant, pair.scene_type
            )
            t_call = time.perf_counter()
            try:
                call = await self._providers.gate.run(
                    provider.compile,
                    system_prompt=system_prompt,
                    user_content=user_content,
                    item=item,
                )
            except MalformedOutputError as exc:
                pairs_failed += 1
                input_tokens += exc.input_tokens
                output_tokens += exc.output_tokens
                logger.warning(
                    "compile pair (%s, %s) malformed: %s",
                    pair.reflection_id,
                    pair.scene_type,
                    exc,
                )
                continue
            except ProviderCallError as exc:
                pairs_failed += 1
                logger.warning(
                    "compile pair (%s, %s) failed: %s",
                    pair.reflection_id,
                    pair.scene_type,
                    exc,
                )
                continue
            passthrough, dropped = sanitize_passthrough(call.passthrough)
            keys_dropped += dropped
            input_tokens += call.input_tokens
            output_tokens += call.output_tokens
            await db.insert_compiled_bundle(
                self._pool,
                agent_id,
                db.CompiledBundleInsert(
                    reflection_id=pair.reflection_id,
                    scene_type=pair.scene_type,
                    w_relevance=clamp_multiplier(call.w_relevance),
                    w_recency=clamp_multiplier(call.w_recency),
                    w_importance=clamp_multiplier(call.w_importance),
                    passthrough=passthrough,
                    input_tokens=call.input_tokens,
                    output_tokens=call.output_tokens,
                    compile_ms=_ms(time.perf_counter() - t_call),
                ),
            )
            pairs_compiled += 1
        return db.CompilerRunRecord(
            agent_id=agent_id,
            outcome="completed",
            error=None,
            pairs_compiled=pairs_compiled,
            pairs_failed=pairs_failed,
            passthrough_keys_dropped=keys_dropped,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_ms=_ms(time.perf_counter() - t_total),
        )


class CompilerWorker:
    """Idle-time compilation on the C1/C2 lifecycle contract: constructed +
    started at both sites (the api lifespan beside the deferred and
    reflection workers; SessionRunner.create), stop() (cancel + await)
    BEFORE the pool closes, a catch-log-continue poll loop, and
    `sweep(limit=None)` as the deterministic no-timer entry tests, walkers,
    and the REPL's `:compile` call directly.

    Per sweep: scan agents in fixed order, resolve the per-agent
    `compiler_worker_enabled` kill-switch (C3 has no endpoint, so this
    gates the component entirely), and compile each enabled agent's missing
    pairs — at most `compiler_worker_batch` compile CALLS per sweep across
    agents (a cost bound, not a queue). NO attempts ledger (the reflection
    contrast-with-enrichment stance): a failed pair stays missing and the
    next sweep retries it naturally."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        *,
        compiler_provider: CompilerProvider | None = None,
    ):
        self._pool = pool
        self._settings = settings
        self._service = CompilerService(
            pool, providers, settings, compiler_provider=compiler_provider
        )
        self._task: asyncio.Task | None = None
        self._config_error_logged = False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        poll = float(self._settings.defaults["compiler_poll_seconds"])
        while True:
            try:
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("compile sweep failed; worker continues")
            await asyncio.sleep(poll)

    async def sweep(self, limit: int | None = None) -> int:
        """One deterministic pass; returns the number of compile CALL
        attempts (landed or failed — the cost bound counts model calls).
        `limit` overrides the compiler_worker_batch bound (tests, the
        REPL); both are process-level reads like the poll interval — the
        sweep has no single agent context, so an agents.config override of
        the batch knob is inert by design."""
        batch = (
            int(self._settings.defaults["compiler_worker_batch"])
            if limit is None
            else limit
        )
        attempts = 0
        for agent_id, config in await db.fetch_agent_configs(self._pool):
            if attempts >= batch:
                break
            if agent_knob(config, "compiler_worker_enabled", self._settings) == 0.0:
                continue
            try:
                record = await self._service.compile_agent(
                    agent_id, config, budget=batch - attempts
                )
            except ConfigError as exc:
                # Real mode without TWICETOLD_MODEL_COMPILER: log loud ONCE,
                # keep running, record the failed pass (the reflection
                # worker's ladder rung — no call was made, so the batch
                # budget is untouched).
                if not self._config_error_logged:
                    logger.error("compiler worker cannot compile: %s", exc)
                    self._config_error_logged = True
                await db.insert_compiler_run(
                    self._pool,
                    db.CompilerRunRecord(
                        agent_id=agent_id,
                        outcome="failed",
                        error=str(exc),
                        pairs_compiled=0,
                        pairs_failed=0,
                        passthrough_keys_dropped=0,
                        input_tokens=0,
                        output_tokens=0,
                        total_ms=None,
                    ),
                )
                continue
            if record is None:
                continue
            attempts += record.pairs_compiled + record.pairs_failed
            await db.insert_compiler_run(self._pool, record)
        return attempts
