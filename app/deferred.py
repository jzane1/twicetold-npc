"""deferred.py — the deferred-write enrichment worker (Phase C1;
deferred-writes.md, ruled 2026-08-12).

An in-process asyncio task owned by whoever built the services (the FastAPI
lifespan AND the REPL/load-driver SessionRunner — both construction sites
start one, so a REPL observe enriches too). Each pass drains the pending
queue: rows inserted by deferred-mode observes (`enrichment_pending`,
migration 006) get the two LLM calls the sync path would have run — the
single write call (render + importance + typology-when-undeclared) and the
escalation gist call — through the SAME module-level stage functions the
sync branch uses (app\\ingest.py), then one completion transaction
(db.apply_enrichment): the one-shot scalar fill, the 'enrichment' prose
supersede of the raw head, add-only span appends, escalation-novel
components, an opportunistic embedding repair for NULL-embedding heads, and
the cache eviction the chain-writer invariant demands.

Failure policy (deliberately different from the sync path's degrade-now,
per the C1 rulings): a failed write call records a `failed` run row and
leaves the row pending for a later drain; the attempt that spends the
budget (`deferred_max_attempts`) terminal-fills the row byte-equivalent to
the sync scoring-failed end-state. A double-failed escalation stays SOFT
(the 2026-07-22 stance): completion proceeds on the base gist with
`escalation_failed` set. A failed embedding repair stays NULL — today's
end-state.

Timing (`deferred_poll_seconds`, `deferred_batch_size`,
`deferred_max_attempts`) is process-level and reads the service defaults —
the worker has no agent context; the kill-switch (`deferred_writes_enabled`)
gates DEFERRAL at observe time only, never the drain, so flipping it off
never strands a pending row. `drain()` is the deterministic entry for tests
and walkers: no timers involved.

Instrumentation: a background worker has no response payload to ride, so
per-attempt timing and token accounting persist in memory_enrichment_runs
(written inside the completion transaction; surfaced on the unscored /chain
read). No SQL lives here — every statement is app\\db.py's (repo hygiene).

Concurrency: claims take skip-locked row locks (db.claim_enrichment_batch);
a claimed row stays pending while worked, so a second process can re-claim
it mid-flight — the completion guard makes the loser a rolled-back no-op.
Worst case is duplicate model spend, never duplicate rows. The worker holds
a pool connection only inside db calls, never across a model call.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from psycopg_pool import AsyncConnectionPool

from app import db
from app.config import Settings, agent_knob
from app.db import (
    EnrichmentClaim,
    EnrichmentRunRecord,
    EnrichmentSource,
    FactDelta,
    SpanPlan,
)
from app.ingest import (
    TYPOLOGY_FALLBACK,
    _select_gist_spans,
    plan_spans,
    resolve_typology,
    run_write_call,
)
from app.providers import (
    GistSpanCandidate,
    NewComponent,
    ProviderCallError,
    Providers,
)


logger = logging.getLogger(__name__)


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def _gist_plans(
    source: EnrichmentSource,
    write_gist: list[GistSpanCandidate],
    gist_max: int,
) -> list[SpanPlan]:
    """The gist a deferred row gets, as insert-ready is_gist=true plans: the
    write call's minimal selection, else the floor (stored evidence, else the
    first sentence) — the same `_select_gist_spans` rule the sync path uses,
    shared by the completion and the terminal fill so they cannot drift."""
    evidence = [
        GistSpanCandidate(start_char=s.start_char, end_char=s.end_char)
        for s in source.spans
    ]
    gist = _select_gist_spans(source.observation_text, write_gist, evidence, gist_max)
    return plan_spans(source.observation_text, gist, [], is_gist=True)


class DeferredWriteWorker:
    """One instance per process; started by the construction site that built
    the services, stopped (cancel + await) before the pool closes."""

    def __init__(
        self, pool: AsyncConnectionPool, providers: Providers, settings: Settings
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        """The poll loop: drain, sleep, repeat. Catch-log-continue — the
        worker task never dies to an exception; a poisoned row burns its
        attempt budget and falls to the orphan sweep's terminal fill."""
        poll = float(self._settings.defaults["deferred_poll_seconds"])
        while True:
            try:
                await self.drain()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("deferred drain pass failed; worker continues")
            await asyncio.sleep(poll)

    # ------------------------------------------------------------------ #
    # the drain — deterministic entry for tests and walkers
    # ------------------------------------------------------------------ #

    async def drain(self, limit: int | None = None) -> int:
        """Process pending rows until the queue is empty (or `limit` rows
        were handled). Returns the number of rows handled — completions,
        recorded failures, and terminal fills all count; silently-skipped
        stale claims do not. Each row gets AT MOST ONE attempt per drain
        pass — a failed row stays pending for a LATER pass (the poll loop
        is the retry spacing), never a back-to-back re-claim that would
        burn the attempt budget in one pass."""
        batch_size = int(self._settings.defaults["deferred_batch_size"])
        max_attempts = int(self._settings.defaults["deferred_max_attempts"])
        processed = 0
        attempted: set = set()
        # Orphan sweep: rows still pending with a spent attempt budget — a
        # process died between claiming the final attempt and recording its
        # outcome. Terminal-fill WITHOUT further model calls.
        for claim in await db.fetch_exhausted_pending(
            self._pool, max_attempts=max_attempts, limit=batch_size
        ):
            if limit is not None and processed >= limit:
                return processed
            await self._terminal_fill(
                claim, error="attempt budget spent (recovered orphan)", run=None
            )
            processed += 1
        while True:
            take = batch_size if limit is None else min(batch_size, limit - processed)
            if take <= 0:
                return processed
            claims = await db.claim_enrichment_batch(
                self._pool,
                batch_size=take,
                max_attempts=max_attempts,
                exclude=sorted(attempted),
            )
            if not claims:
                return processed
            for claim in claims:
                attempted.add(claim.memory_id)
                if await self._process(claim, max_attempts=max_attempts):
                    processed += 1

    # ------------------------------------------------------------------ #
    # one attempt
    # ------------------------------------------------------------------ #

    async def _terminal_fill(
        self,
        claim: EnrichmentClaim,
        *,
        error: str,
        run: EnrichmentRunRecord | None,
    ) -> None:
        """The terminal degraded completion: neutral importance +
        scoring_failed + the agent's default typology (COALESCE — a declared
        typology stands), pending cleared, and the gist FLOOR (no write call
        ever succeeded, so the floor comes from the stored evidence, else the
        first sentence — exactly what the sync path lands when its write call
        fails). Equivalent to the sync scoring-failed end-state, gist
        included."""
        agent = await db.fetch_agent(self._pool, claim.agent_id)
        config: dict = agent["config"] if agent is not None else {}
        source = await db.fetch_enrichment_source(self._pool, claim.memory_id)
        floor_gist = (
            _gist_plans(
                source,
                [],
                int(agent_knob(config, "gist_max_spans", self._settings)),
            )
            if source is not None
            else []  # no longer pending: the guard below downgrades anyway
        )
        outcome = await db.record_enrichment_failure(
            self._pool,
            memory_id=claim.memory_id,
            attempt=claim.attempt,
            error=error,
            run=run,
            terminal=True,
            terminal_importance=agent_knob(
                config, "importance_neutral", self._settings
            ),
            terminal_typology=str(config.get("typology_default", TYPOLOGY_FALLBACK)),
            terminal_typology_confidence=agent_knob(
                config, "typology_confidence_default", self._settings
            ),
            terminal_gist=floor_gist,
        )
        logger.warning(
            "deferred enrichment terminal for %s (attempt %s, outcome %s): %s",
            claim.memory_id,
            claim.attempt,
            outcome,
            error,
        )

    async def _process(self, claim: EnrichmentClaim, *, max_attempts: int) -> bool:
        """One enrichment attempt. Returns True when a run row was written
        (completion, failure, or terminal); False on a silent skip (the row
        was finished by a concurrent drain before we started)."""
        t_attempt = time.perf_counter()
        source = await db.fetch_enrichment_source(self._pool, claim.memory_id)
        if source is None:
            return False
        agent = await db.fetch_agent(self._pool, claim.agent_id)
        if agent is None:
            # agents rows are never deleted; a missing agent is a broken
            # store. Record the failed attempt loudly; the worker never dies.
            await db.record_enrichment_failure(
                self._pool,
                memory_id=claim.memory_id,
                attempt=claim.attempt,
                error=f"unknown agent {claim.agent_id}",
                run=None,
            )
            return True
        config: dict = agent["config"]

        # --- the deferred write call (retry-later failure policy) ---------
        declared = source.typology if source.typology_source == "declared" else None
        gist_max = int(agent_knob(config, "gist_max_spans", self._settings))
        t0 = time.perf_counter()
        write_outcome = await run_write_call(
            self._providers,
            observation_text=source.observation_text,
            diagnosticity_goal=agent["diagnosticity_goal"] or "",
            declared_typology=declared,
            neutral_importance=agent_knob(config, "importance_neutral", self._settings),
            gist_max_spans=gist_max,
        )
        write_ms = _ms(time.perf_counter() - t0)
        if write_outcome.scoring_failed:
            run = EnrichmentRunRecord(
                attempt=claim.attempt,
                triggers=[],
                escalation_failed=False,
                embedding_repaired=False,
                write_ms=write_ms,
                escalation_ms=0.0,
                embed_ms=0.0,
                elapsed_before_ms=_ms(time.perf_counter() - t_attempt),
                write_input_tokens=write_outcome.input_tokens,
                write_output_tokens=write_outcome.output_tokens,
                escalation_input_tokens=0,
                escalation_output_tokens=0,
                embedding_tokens=0,
            )
            error = write_outcome.failure or "write call failed"
            if claim.attempt >= max_attempts:
                await self._terminal_fill(claim, error=error, run=run)
            else:
                await db.record_enrichment_failure(
                    self._pool,
                    memory_id=claim.memory_id,
                    attempt=claim.attempt,
                    error=error,
                    run=run,
                )
            return True

        # --- typology (COALESCE downstream keeps any declared values) -----
        typology, typology_source, typology_confidence = resolve_typology(
            declared=declared,
            declared_confidence=(
                source.typology_confidence if declared is not None else None
            ),
            call_typology=write_outcome.call_typology,
            call_confidence=write_outcome.call_confidence,
            config=config,
            settings=self._settings,
        )

        # --- minimal gist: selected by the deferred write call (2026-09-27;
        # the separate escalation gist call is retired). Evidence spans were
        # stored at observe time; the worker appends only the gist spans
        # (is_gist=true). No triggers, no novel components from the worker
        # (observe-time NLP novels are already component rows). --------------
        triggers: list[str] = []
        escalation_failed = False
        esc_in = esc_out = 0
        escalation_ms = 0.0
        novel_components: list[NewComponent] = []
        span_plans = _gist_plans(source, write_outcome.gist_spans, gist_max)

        # --- opportunistic embedding repair (soft: stays NULL on failure) --
        # Fact entities are deliberately NOT grown here: the sync path's
        # entities are the NER + client merge stored at insert; escalation
        # novels become identity components, never memory entities — parity.
        embed_ms = 0.0
        embed_tokens = 0
        repaired_embedding: list[float] | None = None
        if not source.fact_has_embedding:
            t0 = time.perf_counter()
            try:
                embed_result = await self._providers.gate.run(
                    self._providers.embedding.embed, [source.observation_text]
                )
                repaired_embedding = embed_result.vectors[0]
                embed_tokens = embed_result.tokens
            except ProviderCallError:
                pass
            embed_ms = _ms(time.perf_counter() - t0)

        # --- the completion transaction -----------------------------------
        completed_at = max(datetime.now(timezone.utc), source.valid_at)
        raw_detail_id = (
            source.detail_id if source.detail_write_cause == "original" else None
        )
        run = EnrichmentRunRecord(
            attempt=claim.attempt,
            triggers=triggers,
            escalation_failed=escalation_failed,
            embedding_repaired=repaired_embedding is not None,
            write_ms=write_ms,
            escalation_ms=escalation_ms,
            embed_ms=embed_ms,
            elapsed_before_ms=_ms(time.perf_counter() - t_attempt),
            write_input_tokens=write_outcome.input_tokens,
            write_output_tokens=write_outcome.output_tokens,
            escalation_input_tokens=esc_in,
            escalation_output_tokens=esc_out,
            embedding_tokens=embed_tokens,
        )
        applied = await db.apply_enrichment(
            self._pool,
            memory_id=claim.memory_id,
            completed_at=completed_at,
            importance_raw=write_outcome.importance,
            typology=typology,
            typology_confidence=typology_confidence,
            typology_source=typology_source,
            escalation_failed=escalation_failed,
            rendered_content=(
                write_outcome.rendered_content if raw_detail_id is not None else None
            ),
            raw_detail_id=raw_detail_id,
            fact_delta=(
                FactDelta(
                    entities=source.fact_entities or None,
                    embedding=repaired_embedding,
                )
                if repaired_embedding is not None
                else None
            ),
            new_components=novel_components,
            spans=span_plans,
            run=run,
        )
        if applied == "not_pending":
            return False  # lost the duplicate-claim race; the winner completed
        return True
