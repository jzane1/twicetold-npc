"""reflection.py — THE reflect seam (docs\\reflection.md; the C2 rulings
dated 2026-08-15): formed beliefs over lived episodes grounded in cited
memory_ids, the non-LLM RRR repetition guard, the identity consolidation
stage, the PURELY MECHANICAL component trim, and the optional
ReflectionWorker (default OFF per agent).

One service seam — `ReflectionService.reflect` — used identically by the
route, the REPL, and the worker. No SQL lives here (repo hygiene; the
reads/writes are app\\db.py's reflection section). The model provider is
built lazily at first use via build_reflection_provider (the judge shape:
never a Providers-bundle field; a real-mode call without
TWICETOLD_MODEL_REFLECTION raises ConfigError loudly, the server having
started fine without it). Tests inject Failing/Malformed fakes through the
keyword-only `reflection_provider` seam (build ruling 2026-08-15).

Degradation ladder (every rung a Set L scenario or walker criterion):
  - below the episode floor           -> ReflectionFloorError (409), nothing
    written; the worker skips with NO run row (pressure implies volume)
  - reflect call fails / malformed /
    ALL conclusions ungrounded        -> ReflectionCallError (502), nothing
    written; the worker writes a `failed` run row and retries naturally
    next sweep (NO attempts ledger — the deliberate contrast with
    enrichment's budget: pressure persists until a reflect lands)
  - some conclusions ungrounded       -> the valid subset stores;
    dropped_ungrounded counts
  - empty conclusion list             -> a VALID outcome (200, zero rows —
    thin evidence concludes nothing)
  - consolidation call/write fails    -> SOFT (the escalation precedent):
    consolidation_failed flags, the step-7 writes stand
  - RRR at/above threshold            -> the consolidation stage is
    suppressed and flagged; the reflections still store (honest evidence
    of the agent's state).

Time basis (build ruling 2026-08-15): the pipeline's "now" — sampling age
and trim staleness — is the request's client_timestamp (the as_of /
scene-frozen-basis precedent), so identical requests against identical
stores produce identical samples, trims, and writes. The worker stamps
wall-clock now when it constructs its internal request. Pressure needs no
"now": it compares created_at columns only (service bookkeeping).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, decay, identity
from app.config import ConfigError, Settings, agent_knob
from app.ingest import UnknownAgentError
from app.providers import (
    MalformedOutputError,
    Providers,
    ProviderCallError,
    ReflectionItem,
    ReflectionProvider,
    build_reflection_provider,
)
from app.schemas import (
    ConsolidationOut,
    ReflectInstrumentation,
    ReflectionOut,
    ReflectRequest,
    ReflectResult,
)

logger = logging.getLogger(__name__)


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


class ReflectionFloorError(RuntimeError):
    """Below reflection_min_episodes — the verb refuses loudly (409),
    nothing written. Not a degradation: there is nothing to conclude from."""


class ReflectionCallError(RuntimeError):
    """The reflect stage failed (call failure, malformed output, or every
    conclusion ungrounded) — fail-loud (502), nothing written: reflection
    is derived work, so refusing to store a failed derivation loses
    nothing. Carries token counts when the spend happened (the
    MalformedOutputError convention) so a worker's `failed` run row stays
    honest."""

    def __init__(self, message: str, input_tokens: int = 0, output_tokens: int = 0):
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


# ---------------------------------------------------------------------------
# Pure prompt assembly (the dialogue/reconstruction precedent: module-level
# and byte-stable so walkers assert block order without a DB or model).
# ---------------------------------------------------------------------------

_REFLECT_SYSTEM = (
    "You are the reflection pass for a game NPC's memory. Given the NPC's "
    "identity and a sample of its episodic memories (each with a memory_id), "
    "form at most three durable conclusions the NPC would draw about itself, "
    "others, or its world. Every conclusion MUST cite the memory_ids it is "
    "grounded in; omit any conclusion you cannot ground in the listed "
    "memories. Mark identity_relevant true only for conclusions that belong "
    "in the NPC's durable self-description. Return ONLY a JSON object with "
    'the key: reflections (list of objects {"content": str, '
    '"identity_relevant": bool, "source_memory_ids": [memory_id strings]}). '
    "An empty list is valid when the evidence supports no conclusion. "
    "No other text."
)

_CONSOLIDATE_SYSTEM = (
    "You are the identity-consolidation pass for a game NPC's memory. Given "
    "the NPC's immutable seed identity, its current identity document, and "
    "its accumulated identity-relevant beliefs, restate those beliefs as ONE "
    "coherent belief the NPC now holds — absorb them, do not enumerate them. "
    "Return ONLY a JSON object with the key: content (string). No other text."
)


def assemble_reflection_prompt(
    identity_document: str, items: list[ReflectionItem]
) -> tuple[str, str]:
    """(system_prompt, user_content) — pure and byte-stable for identical
    inputs: items sorted by memory_id, the identity block omitted for an
    empty document (the NULL-seed rule). The prompt carries NO trim content
    — pruning is mechanical (spec ruling 2), so the model never sees or
    proposes prunes."""
    blocks: list[str] = []
    if identity_document:
        blocks.append(f"[identity]\n{identity_document}")
    lines = [
        f"- ({item.memory_id}) {item.telling} "
        f"(importance {'unscored' if item.importance is None else item.importance}, "
        f"{item.valid_at})"
        for item in sorted(items, key=lambda item: item.memory_id)
    ]
    blocks.append("[memories]\nA sample of what you remember:\n" + "\n".join(lines))
    return _REFLECT_SYSTEM, "\n\n".join(blocks)


def assemble_consolidation_prompt(
    seed_identity: str | None, identity_document: str, beliefs: list[str]
) -> tuple[str, str]:
    """(system_prompt, user_content) for the consolidation call — pure,
    conditioned on the immutable seed + the prior rendered document + the
    live identity-relevant beliefs (dossier ruling 3). Blocks omit empty
    members (the NULL-seed rule)."""
    blocks: list[str] = []
    if seed_identity:
        blocks.append(f"[seed identity]\n{seed_identity}")
    if identity_document:
        blocks.append(f"[current document]\n{identity_document}")
    blocks.append("[beliefs]\n" + "\n".join(f"- {belief}" for belief in beliefs))
    return _CONSOLIDATE_SYSTEM, "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Sampling + RRR (pure over fetched rows — walker-assertable)
# ---------------------------------------------------------------------------


def sample_episodes(
    candidates: list[db.CandidateRow],
    config: dict,
    settings: Settings,
    now: datetime,
) -> list[db.CandidateRow]:
    """Deterministic top-`reflection_sample_k` by importance_norm x recency
    (reflection.md Sampling): THE decay module's formula at the request's
    time basis, ties on memory_id — a weighted deterministic ranking, never
    a lottery. NULL-importance rows take the neutral fallback (the C1
    window precedent). Pinned rows take the PLAIN decay score — no
    rec = 1.0 arm: pin means exactly two things (decay exemption on reads,
    reconstruction exclusion) and reflection is neither (ruled at spec)."""
    neutral = agent_knob(config, "importance_neutral", settings)
    floor = agent_knob(config, "importance_norm_floor", settings)
    k_importance = agent_knob(config, "decay_k_importance", settings)
    k = int(agent_knob(config, "reflection_sample_k", settings))
    scored: list[tuple[float, db.CandidateRow]] = []
    for row in candidates:
        raw = row.importance_raw if row.importance_raw is not None else neutral
        imp = min(max(raw, floor), 1.0)
        tau_base = decay.resolve_tau_base(row.decay_class, config, settings)
        tau_eff = decay.tau_effective(tau_base, k_importance, raw)
        rec = decay.recency((now - row.valid_at).total_seconds(), tau_eff)
        scored.append((imp * rec, row))
    scored.sort(key=lambda entry: (-entry[0], entry[1].memory_id))
    return [row for _score, row in scored[:k]]


def compute_rrr(new_contents: list[str], prior_contents: list[str]) -> float | None:
    """RRR — self-repetition among the agent's own reflections (dossier
    ruling 5; NOT the cut cross-memory conflict detection). Per new
    conclusion: max SequenceMatcher.ratio against the recent-window
    contents; call-level = max over conclusions. None when no priors exist
    (or nothing new to compare). Non-LLM by construction, deterministic."""
    if not prior_contents or not new_contents:
        return None
    best = 0.0
    for new in new_contents:
        for prior in prior_contents:
            ratio = SequenceMatcher(None, new, prior).ratio()
            if ratio > best:
                best = ratio
    return best


# ---------------------------------------------------------------------------
# The seam
# ---------------------------------------------------------------------------


class ReflectionService:
    """THE reflect verb (pipeline steps 1-9, reflection.md). Constructed
    like every seam — (pool, providers, settings) — with the keyword-only
    `reflection_provider` test seam; None means the lazy judge-shaped
    factory at first use (where real mode without the var fails loud)."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        *,
        reflection_provider: ReflectionProvider | None = None,
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings
        self._reflection_provider = reflection_provider

    def _provider(self) -> ReflectionProvider:
        if self._reflection_provider is None:
            self._reflection_provider = build_reflection_provider(self._settings)
        return self._reflection_provider

    async def reflect(self, agent_id: UUID, request: ReflectRequest) -> ReflectResult:
        t_total = time.perf_counter()
        now = request.client_timestamp

        # (1) the agent, loudly; knobs; the current rendered document.
        agent = await db.fetch_agent(self._pool, agent_id)
        if agent is None:
            raise UnknownAgentError(f"agent {agent_id} not found")
        config = agent["config"]
        seed = agent["seed_identity"]
        neutral = agent_knob(config, "importance_neutral", self._settings)
        norm = agent_knob(config, "reflection_pressure_norm", self._settings)
        if norm <= 0.0:
            raise ValueError(
                f"reflection_pressure_norm must be > 0, got {norm} "
                "(a zero divisor is knob misuse, never a silent clamp)"
            )
        pressure_before = (
            await db.reflection_pressure_mass(self._pool, agent_id, neutral=neutral)
            / norm
        )
        _version, document, _created = await identity.ensure_identity_document(
            self._pool, agent_id, seed
        )

        # (2) sample: the live pool, floor-checked, deterministic top-k.
        candidates = await db.fetch_live_candidates(self._pool, agent_id)
        min_episodes = int(
            agent_knob(config, "reflection_min_episodes", self._settings)
        )
        if len(candidates) < min_episodes:
            raise ReflectionFloorError(
                f"agent {agent_id} has {len(candidates)} live episodes; "
                f"reflection_min_episodes is {min_episodes}"
            )
        sample = sample_episodes(candidates, config, self._settings, now)
        sampled_ids = [row.memory_id for row in sample]

        # (3) the mechanical trim set (spec ruling 2) — no model input;
        # 0.0 disables the trim entirely (the gate_enabled kill-switch shape).
        stale_seconds = agent_knob(
            config, "reflection_trim_stale_seconds", self._settings
        )
        if stale_seconds > 0.0:
            trim_ids = await db.fetch_trim_candidates(
                self._pool,
                agent_id,
                stale_before=now - timedelta(seconds=stale_seconds),
                sample_memory_ids=sampled_ids,
            )
        else:
            trim_ids = []

        # (4) ONE reflect call — fail-loud; no pool connection held across it.
        items = [
            ReflectionItem(
                memory_id=str(row.memory_id),
                telling=row.content,
                importance=row.importance_raw,
                valid_at=row.valid_at.isoformat(),
            )
            for row in sample
        ]
        system_prompt, user_content = assemble_reflection_prompt(document, items)
        provider = self._provider()  # ConfigError surfaces here, loud
        t0 = time.perf_counter()
        try:
            call = await self._providers.gate.run(
                provider.reflect,
                system_prompt=system_prompt,
                user_content=user_content,
                items=items,
            )
        except ProviderCallError as exc:
            raise ReflectionCallError(f"reflect call failed: {exc}") from exc
        except MalformedOutputError as exc:
            raise ReflectionCallError(
                f"malformed reflect output: {exc}",
                input_tokens=exc.input_tokens,
                output_tokens=exc.output_tokens,
            ) from exc
        reflect_ms = _ms(time.perf_counter() - t0)

        # (5) mechanical grounding validation: non-empty AND subset of the
        # sampled ids, else dropped and counted; ALL dropping from a
        # non-empty output is a malformed-class failure; a genuinely empty
        # list is a valid outcome.
        sampled_set = {str(memory_id) for memory_id in sampled_ids}
        surviving: list[db.ReflectionInsert] = []
        dropped = 0
        for conclusion in call.conclusions:
            cited = conclusion.source_memory_ids
            if cited and set(cited) <= sampled_set:
                surviving.append(
                    db.ReflectionInsert(
                        content=conclusion.content,
                        identity_relevant=conclusion.identity_relevant,
                        source_memory_ids=[UUID(value) for value in cited],
                    )
                )
            else:
                dropped += 1
        if call.conclusions and not surviving:
            raise ReflectionCallError(
                f"all {len(call.conclusions)} conclusions ungrounded "
                "(citations empty or outside the sampled ids); nothing written",
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
            )

        # (6) RRR over the surviving conclusions vs the recent live window.
        window = int(agent_knob(config, "reflection_rrr_window", self._settings))
        priors = await db.fetch_recent_reflections(self._pool, agent_id, window)
        rrr = compute_rrr([entry.content for entry in surviving], priors)
        rrr_threshold = agent_knob(config, "reflection_rrr_threshold", self._settings)
        rrr_blocked = rrr is not None and rrr >= rrr_threshold

        # (7) the write transaction, then the re-render (AFTER the commit —
        # build ruling: the upsert is idempotent and self-heals).
        t0 = time.perf_counter()
        applied = await db.apply_reflection(
            self._pool,
            agent_id,
            conclusions=surviving,
            valid_at=now,
            prune_component_ids=trim_ids,
        )
        (
            identity_version,
            _rendered,
            document_new,
        ) = await identity.ensure_identity_document(self._pool, agent_id, seed)
        insert_ms = _ms(time.perf_counter() - t0)

        # (8) consolidation — when due (override > knob threshold) and not
        # RRR-blocked. Failure at any point here is SOFT: flag and stand.
        consolidation: ConsolidationOut | None = None
        consolidation_ms = 0.0
        consolidation_in = 0
        consolidation_out = 0
        live_identity = await db.fetch_live_identity_reflections(self._pool, agent_id)
        consolidate_at = int(
            agent_knob(config, "reflection_consolidate_at", self._settings)
        )
        if request.consolidate is None:
            due = len(live_identity) >= consolidate_at
        else:
            due = request.consolidate
        if due and not rrr_blocked and live_identity:
            t0 = time.perf_counter()
            _doc_version, current_document, _ = await identity.ensure_identity_document(
                self._pool, agent_id, seed
            )
            cons_system, cons_user = assemble_consolidation_prompt(
                seed, current_document, [row.content for row in live_identity]
            )
            try:
                cons_call = await self._providers.gate.run(
                    provider.consolidate,
                    system_prompt=cons_system,
                    user_content=cons_user,
                )
            except (ProviderCallError, MalformedOutputError) as exc:
                consolidation_in = getattr(exc, "input_tokens", 0)
                consolidation_out = getattr(exc, "output_tokens", 0)
                consolidation = ConsolidationOut(failed=True)
                logger.warning(
                    "consolidation call failed for agent %s (soft): %s",
                    agent_id,
                    exc,
                )
            else:
                consolidation_in = cons_call.input_tokens
                consolidation_out = cons_call.output_tokens
                absorbed = [row.reflection_id for row in live_identity]
                source_union = sorted(
                    {
                        memory_id
                        for row in live_identity
                        for memory_id in row.source_memory_ids
                    }
                )
                new_id = await db.apply_consolidation(
                    self._pool,
                    agent_id,
                    content=cons_call.content,
                    source_memory_ids=source_union,
                    absorbed_ids=absorbed,
                    valid_at=now,
                )
                if new_id is None:
                    consolidation = ConsolidationOut(failed=True)
                    logger.warning(
                        "consolidation absorb raced for agent %s (soft, rolled back)",
                        agent_id,
                    )
                else:
                    (
                        identity_version,
                        _rendered,
                        re_rendered_new,
                    ) = await identity.ensure_identity_document(
                        self._pool, agent_id, seed
                    )
                    document_new = document_new or re_rendered_new
                    consolidation = ConsolidationOut(
                        reflection_id=new_id,
                        absorbed_reflection_ids=absorbed,
                        failed=False,
                    )
            consolidation_ms = _ms(time.perf_counter() - t0)

        # (9) pressure after + the result (instrumentation rides the payload;
        # run rows are the WORKER's, never written here — the C1 split).
        pressure_after = (
            await db.reflection_pressure_mass(self._pool, agent_id, neutral=neutral)
            / norm
        )
        reflections_out = [
            ReflectionOut(
                reflection_id=reflection_id,
                content=entry.content,
                identity_relevant=entry.identity_relevant,
                source_memory_ids=entry.source_memory_ids,
            )
            for reflection_id, entry in zip(
                applied.reflection_ids, surviving, strict=True
            )
        ]
        return ReflectResult(
            agent_id=agent_id,
            reflections=reflections_out,
            sampled_memory_ids=sampled_ids,
            dropped_ungrounded=dropped,
            rrr=rrr,
            rrr_blocked_consolidation=rrr_blocked,
            consolidation=consolidation,
            pruned_component_ids=applied.pruned_component_ids,
            evicted_cache_rows=applied.evicted_cache_rows,
            pressure_before=pressure_before,
            pressure_after=pressure_after,
            identity_version=identity_version,
            identity_document_new=document_new,
            instrumentation=ReflectInstrumentation(
                reflect_ms=reflect_ms,
                consolidation_ms=consolidation_ms,
                insert_ms=insert_ms,
                total_ms=_ms(time.perf_counter() - t_total),
                reflect_input_tokens=call.input_tokens,
                reflect_output_tokens=call.output_tokens,
                consolidation_input_tokens=consolidation_in,
                consolidation_output_tokens=consolidation_out,
            ),
        )


# ---------------------------------------------------------------------------
# The worker (C1's lifecycle contract verbatim; default OFF per agent)
# ---------------------------------------------------------------------------


class ReflectionWorker:
    """Idle-time reflection on C1's lifecycle contract: constructed + started
    at both sites (the api lifespan beside the deferred worker;
    SessionRunner.create), stop() (cancel + await) BEFORE the pool closes,
    a catch-log-continue poll loop, and `sweep(limit=None)` as the
    deterministic no-timer entry tests and walkers call directly.

    Per sweep: scan agents in fixed order, resolve the per-agent
    `reflection_worker_enabled` kill-switch (gates the WORKER's auto-pull
    only — the endpoint is always live), compute pressure for enabled
    agents, reflect those at/above `reflection_pressure_threshold` — at
    most one reflect per agent per sweep, at most `reflection_worker_batch`
    attempts per sweep (a cost bound, not a queue). NO attempts ledger
    (the deliberate contrast with enrichment's budget): a failed reflect
    writes a `failed` run row and the pressure that triggered it persists,
    so the next sweep retries naturally."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        *,
        reflection_provider: ReflectionProvider | None = None,
    ):
        self._pool = pool
        self._settings = settings
        self._service = ReflectionService(
            pool, providers, settings, reflection_provider=reflection_provider
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
        poll = float(self._settings.defaults["reflection_poll_seconds"])
        while True:
            try:
                await self.sweep()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("reflection sweep failed; worker continues")
            await asyncio.sleep(poll)

    async def sweep(self, limit: int | None = None) -> int:
        """One deterministic pass; returns the number of reflect ATTEMPTS
        (completed or failed — the cost bound counts model calls, not
        successes). `limit` overrides the reflection_worker_batch bound
        (tests); both are process-level reads like the poll interval — the
        sweep has no single agent context, so an agents.config override of
        the batch knob is inert by design."""
        batch = (
            int(self._settings.defaults["reflection_worker_batch"])
            if limit is None
            else limit
        )
        attempts = 0
        for agent_id, config in await db.fetch_agent_configs(self._pool):
            if attempts >= batch:
                break
            if agent_knob(config, "reflection_worker_enabled", self._settings) == 0.0:
                continue
            neutral = agent_knob(config, "importance_neutral", self._settings)
            norm = agent_knob(config, "reflection_pressure_norm", self._settings)
            if norm <= 0.0:
                logger.warning(
                    "agent %s has reflection_pressure_norm %s (must be > 0); skipped",
                    agent_id,
                    norm,
                )
                continue
            pressure = (
                await db.reflection_pressure_mass(self._pool, agent_id, neutral=neutral)
                / norm
            )
            threshold = agent_knob(
                config, "reflection_pressure_threshold", self._settings
            )
            if pressure < threshold:
                continue
            request = ReflectRequest(
                client_timestamp=datetime.now(timezone.utc), consolidate=None
            )
            try:
                result = await self._service.reflect(agent_id, request)
            except ReflectionFloorError:
                # Pressure implies volume, so this rung is normally
                # unreachable; with adversarial knobs it is a skip, NO run
                # row (the spec's ladder).
                continue
            except ReflectionCallError as exc:
                attempts += 1
                await db.insert_reflection_run(
                    self._pool,
                    _failed_run(agent_id, str(exc), pressure, exc),
                )
            except ConfigError as exc:
                # Real mode without TWICETOLD_MODEL_REFLECTION: log loud ONCE,
                # keep running, record the failed attempt (the spec's ladder).
                attempts += 1
                if not self._config_error_logged:
                    logger.error("reflection worker cannot reflect: %s", exc)
                    self._config_error_logged = True
                await db.insert_reflection_run(
                    self._pool,
                    _failed_run(agent_id, str(exc), pressure, None),
                )
            else:
                attempts += 1
                await db.insert_reflection_run(
                    self._pool, _completed_run(agent_id, result)
                )
        return attempts


def _failed_run(
    agent_id: UUID,
    error: str,
    pressure_before: float,
    exc: ReflectionCallError | None,
) -> db.ReflectionRunRecord:
    """A `failed` run row: honest spend when the error carries it, Nones
    for the stages the run never reached."""
    return db.ReflectionRunRecord(
        agent_id=agent_id,
        outcome="failed",
        error=error,
        reflections_written=0,
        dropped_ungrounded=0,
        consolidation_ran=False,
        consolidation_failed=False,
        rrr=None,
        rrr_blocked=False,
        pruned_components=0,
        evicted_cache_rows=0,
        pressure_before=pressure_before,
        pressure_after=None,
        reflect_ms=None,
        consolidation_ms=None,
        insert_ms=None,
        total_ms=None,
        reflect_input_tokens=exc.input_tokens if exc else 0,
        reflect_output_tokens=exc.output_tokens if exc else 0,
        consolidation_input_tokens=0,
        consolidation_output_tokens=0,
    )


def _completed_run(agent_id: UUID, result: ReflectResult) -> db.ReflectionRunRecord:
    """A `completed` run row mirroring the seam's payload (the worker's
    persisted accounting — a background seam has no response to ride)."""
    consolidation = result.consolidation
    return db.ReflectionRunRecord(
        agent_id=agent_id,
        outcome="completed",
        error=None,
        reflections_written=len(result.reflections),
        dropped_ungrounded=result.dropped_ungrounded,
        consolidation_ran=consolidation is not None,
        consolidation_failed=consolidation.failed if consolidation else False,
        rrr=result.rrr,
        rrr_blocked=result.rrr_blocked_consolidation,
        pruned_components=len(result.pruned_component_ids),
        evicted_cache_rows=result.evicted_cache_rows,
        pressure_before=result.pressure_before,
        pressure_after=result.pressure_after,
        reflect_ms=result.instrumentation.reflect_ms,
        consolidation_ms=result.instrumentation.consolidation_ms,
        insert_ms=result.instrumentation.insert_ms,
        total_ms=result.instrumentation.total_ms,
        reflect_input_tokens=result.instrumentation.reflect_input_tokens,
        reflect_output_tokens=result.instrumentation.reflect_output_tokens,
        consolidation_input_tokens=(result.instrumentation.consolidation_input_tokens),
        consolidation_output_tokens=(
            result.instrumentation.consolidation_output_tokens
        ),
    )
