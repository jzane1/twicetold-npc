"""ingest.py — THE ingest service: the write path's single instrumented seam.

Both callers (the FastAPI route and, later, the CLI harness) sit on this
module; neither duplicates the timing or token accounting recorded here
(CLAUDE.md: instrument at the seam).

Pipeline per observe event (write-path.md §pipeline):
  NLP pass -> single Haiku write call -> (escalation when triggered) ->
  embedding -> atomic insert -> IngestResult.

Deferred mode (deferred-writes.md, ruled 2026-08-12; knob
`deferred_writes_enabled`, default OFF): the two LLM calls above move to
app\\deferred.py's worker — the NLP pass, embedding, and atomic insert stay
synchronous, the row lands `enrichment_pending` with NULL write-call scalars
(raw observation text as the `original` head; retrieval's importance-NULL
neutral fallback covers scoring), and the worker's one-shot completion fills
the scalars and supersedes the head with the render ('enrichment' cause).
The write-call / typology / escalation stages are module-level functions so
the worker and the sync branch share ONE implementation.

Degradation ladder (write):
  soft — the write always lands:
    - write-call failure / malformed output -> neutral importance +
      scoring_failed = true (+ default typology when undeclared; the head
      content falls back to the raw observation text since no render exists);
    - unknown decay_class label -> default class + decay_class_unknown = true;
    - embedding failure -> NULL embedding on the `original` FACT head
      (embedding_failed in the payload; the queryable signal moved to the
      fact head with the 2026-07-18 freeze ruling — observe no longer writes
      memories.embedding at all).
    - escalation failure: retry once, then SOFT-DEGRADE — the write lands
      with the base NLP-pass gist and escalation_failed = true (the payload
      and the dedicated column, migration 005). Ruled 2026-07-22, retiring
      the 2026-07-13 build-phase hard-stop: a failed gist enrichment must
      never cost a write.
  (The observe path has NO hard rung. Every failure above lands the row.)

The authorial correction (fact-following since the fact-level build,
fact-level-correction.md) is the deliberate CONTRAST: all-or-nothing,
fail-loud — an embed failure there writes nothing (CorrectionEmbedFailedError
-> 502), because the operator surface has no soft paths and a NULL corrected
embedding would make the memory vanish from the vector probe.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, identity, nlp
from app.config import Settings, agent_knob
from app.db import InsertPlan, SpanPlan
from app.providers import (
    EscalationResult,
    GistSpanCandidate,
    MalformedOutputError,
    NewComponent,
    ProviderCallError,
    Providers,
    WriteCallResult,
)
from app.schemas import (
    AffectOut,
    AgentPurgeResult,
    CorrectionRequest,
    CorrectionResult,
    CreateAgentRequest,
    CreateAgentResult,
    DialogueInitRequest,
    IngestResult,
    Instrumentation,
    ObserveEvent,
    PinResult,
    PurgeResult,
    SceneBoundaryEvent,
    ScenePrewarmInstrumentation,
    SceneResult,
)

if TYPE_CHECKING:
    from app.retrieval import RetrievalService

logger = logging.getLogger(__name__)

# Sentinel decay class when the agent's config supplies neither a map entry
# nor a default label: the write is never rejected, only flagged unknown.
DECAY_CLASS_SENTINEL = "unclassified"
TYPOLOGY_FALLBACK = "observed"  # overridable per agent: config key "typology_default"


class UnknownAgentError(LookupError):
    """The event references an agent_id with no agents row."""


class UnknownMemoryError(LookupError):
    """set_pin / correct references a memory_id with no memories row."""


class CorrectionConflictError(RuntimeError):
    """The correction's expected_detail_id no longer names the live head —
    the operator's read is stale; nothing was changed (409, never a silent
    retry against a telling the operator did not see)."""


class CorrectionEmbedFailedError(RuntimeError):
    """The correction's embed call failed: nothing was written on either
    chain (all-or-nothing, ruled 2026-07-18 — the embed runs BEFORE the
    transaction opens). 502 at the route; the operator retries. (It took its
    502 shape from the then-current escalation hard-stop, which was itself
    retired 2026-07-22 — the operator surface keeps the fail-loud stance the
    observe path gave up.)"""


class CorrectionNlpFailedError(RuntimeError):
    """The correction's NER pass failed (broken/missing spaCy install):
    nothing was written — the NER runs before the embed, before the
    transaction (fail-loud, ruled 2026-07-19 with the gate build; the embed
    precedent's shape). 502 at the route; the operator fixes the environment
    and retries."""


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def _resolve_decay_class(label: str | None, config: dict) -> tuple[str, bool]:
    """Validate against the agent's decay-class map (never reject)."""
    decay_map = config.get("decay_classes") or {}
    default_label = config.get("decay_class_default")
    if label is not None and label in decay_map:
        return label, False
    if label is not None:  # supplied but unknown -> default + flag
        return (default_label or DECAY_CLASS_SENTINEL), True
    if default_label is not None:  # omitted -> default, not an unknown label
        return default_label, False
    return DECAY_CLASS_SENTINEL, True


def _merge_spans(
    base: list[GistSpanCandidate], extra: list[GistSpanCandidate]
) -> list[GistSpanCandidate]:
    merged = list(base)
    seen = {
        (s.start_char, s.end_char, s.matched_component_id, s.matched_category)
        for s in base
    }
    for span in extra:
        key = (
            span.start_char,
            span.end_char,
            span.matched_component_id,
            span.matched_category,
        )
        if key not in seen:
            seen.add(key)
            merged.append(span)
    return merged


def _merge_components(
    base: list[NewComponent], extra: list[NewComponent]
) -> list[NewComponent]:
    merged = list(base)
    seen = {c.canonical.lower() for c in base}
    for comp in extra:
        if comp.canonical.lower() not in seen:
            seen.add(comp.canonical.lower())
            merged.append(comp)
    return merged


# ---------------------------------------------------------------------------
# The write-call / typology / escalation stages — module-level since the
# deferred-write build (extract-only move, 2026-08-12) so the sync branch and
# app\deferred.py's worker share ONE implementation. Behavior is byte-for-byte
# the pre-move seam's; timing stays at the call sites (the seam owns it).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriteStageOutcome:
    """The single write call's outcome under the ruled soft degradation:
    on failure the fallbacks stand (raw text as render, neutral importance),
    scoring_failed is set, and any accounted tokens are carried. `failure`
    is the exception text (None on success) — the sync branch ignores it;
    the worker records it."""

    rendered_content: str
    importance: float
    call_typology: str | None
    call_confidence: float | None
    scoring_failed: bool
    input_tokens: int
    output_tokens: int
    failure: str | None


async def run_write_call(
    providers: Providers,
    *,
    observation_text: str,
    diagnosticity_goal: str,
    declared_typology: str | None,
    neutral_importance: float,
) -> WriteStageOutcome:
    """The single write model call (render + importance + typology-when-
    absent) with its ruled soft degradation."""
    scoring_failed = False
    tokens_in = tokens_out = 0
    rendered_content = observation_text  # fallback head when no render exists
    importance = neutral_importance
    call_typology: str | None = None
    call_confidence: float | None = None
    failure: str | None = None
    try:
        write_result: WriteCallResult = await providers.gate.run(
            providers.write.render_and_score,
            observation_text=observation_text,
            diagnosticity_goal=diagnosticity_goal,
            declared_typology=declared_typology,
        )
        rendered_content = write_result.rendered_content
        importance = write_result.importance_raw
        call_typology = write_result.typology
        call_confidence = write_result.typology_confidence
        tokens_in = write_result.input_tokens
        tokens_out = write_result.output_tokens
    except ProviderCallError as exc:
        scoring_failed = True
        failure = str(exc)
    except MalformedOutputError as exc:
        scoring_failed = True
        failure = str(exc)
        tokens_in = exc.input_tokens
        tokens_out = exc.output_tokens
    return WriteStageOutcome(
        rendered_content=rendered_content,
        importance=importance,
        call_typology=call_typology,
        call_confidence=call_confidence,
        scoring_failed=scoring_failed,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        failure=failure,
    )


def resolve_typology(
    *,
    declared: str | None,
    declared_confidence: float | None,
    call_typology: str | None,
    call_confidence: float | None,
    config: dict,
    settings: Settings,
) -> tuple[str, str, float]:
    """The typology ladder: client declaration wins > write-call inference >
    the agent's default (flagged upstream by scoring_failed when the call
    degraded — never a lost write). Returns (typology, source, confidence)."""
    if declared is not None:
        return (
            declared,
            "declared",
            declared_confidence
            if declared_confidence is not None
            else agent_knob(config, "typology_confidence_default", settings),
        )
    if call_typology is not None:
        return (
            call_typology,
            "inferred",
            call_confidence
            if call_confidence is not None
            else agent_knob(config, "typology_confidence_default", settings),
        )
    return (
        str(config.get("typology_default", TYPOLOGY_FALLBACK)),
        "inferred",
        agent_knob(config, "typology_confidence_default", settings),
    )


async def escalate_with_retry(
    providers: Providers,
    *,
    observation_text: str,
    known_components: list[dict],
    candidate_spans: list[GistSpanCandidate],
    candidate_components: list[NewComponent],
    triggers: list[str],
) -> EscalationResult | None:
    """Retry once; on a second failure return None so the write soft-degrades
    to the base NLP-pass gist (ruled 2026-07-22 — the fail-loud hard-stop was
    a temporary build-phase stance; a failed escalation must not halt a live
    write). The degraded gist is flagged (escalation_failed) rather than
    aborting the write."""
    for _attempt in (1, 2):
        try:
            return await providers.gate.run(
                providers.escalation.extract_gist,
                observation_text=observation_text,
                known_components=known_components,
                candidate_spans=candidate_spans,
                candidate_components=candidate_components,
                triggers=triggers,
            )
        except (ProviderCallError, MalformedOutputError):
            continue
    return None


def plan_spans(
    observation_text: str,
    spans: list[GistSpanCandidate],
    new_components: list[NewComponent],
    occupied_extra: set[tuple[int, int]] | None = None,
) -> list[SpanPlan]:
    """Convert candidates to insert-ready plans; novel-entity mentions become
    spans referencing the component row created in the same transaction.
    `occupied_extra` lets the deferred worker exclude already-stored span
    offsets from the novel-mention scan (add-only appends); the sync path
    passes nothing."""
    plans = [
        SpanPlan(
            start_char=s.start_char,
            end_char=s.end_char,
            component_ref=s.matched_component_id,
            matched_category=s.matched_category,
        )
        for s in spans
    ]
    occupied = {(p.start_char, p.end_char) for p in plans}
    if occupied_extra:
        occupied |= occupied_extra
    for index, comp in enumerate(new_components):
        for start, end in nlp._find_term_spans(observation_text, comp.canonical):
            if (start, end) not in occupied:
                occupied.add((start, end))
                plans.append(
                    SpanPlan(
                        start_char=start,
                        end_char=end,
                        component_ref=index,
                        matched_category=comp.category,
                    )
                )
    return plans


class IngestService:
    """One instance per process; both callers share it."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        retrieval: RetrievalService | None = None,
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings
        # The retrieval service (C7-B): injected so the scene-boundary handler
        # runs the probe-driven reconstruction pre-warm through the same init
        # path a dialogue turn uses. Optional (default None) so the many direct
        # IngestService(...) constructions that never pre-warm stand; both
        # production sites pass it (retrieval is constructed just before).
        self._retrieval = retrieval

    # ------------------------------------------------------------------ #
    # observe
    # ------------------------------------------------------------------ #

    async def ingest_observation(self, event: ObserveEvent) -> IngestResult:
        t_total = time.perf_counter()

        agent = await db.fetch_agent(self._pool, event.agent_id)
        if agent is None:
            raise UnknownAgentError(f"unknown agent_id {event.agent_id}")
        config: dict = agent["config"]
        components = await db.fetch_live_components(self._pool, event.agent_id)

        # --- NLP pass (no LLM) ------------------------------------------
        t0 = time.perf_counter()
        nlp_result = await asyncio.to_thread(
            nlp.run_write_pass, event.observation_text, components
        )
        nlp_ms = _ms(time.perf_counter() - t0)

        # --- deferral fork (deferred-writes.md, ruled 2026-08-12) ---------
        deferred = agent_knob(config, "deferred_writes_enabled", self._settings) != 0.0
        knobs = {
            key: agent_knob(config, key, self._settings)
            for key in (
                "escalation_importance_threshold",
                "escalation_affect_threshold",
                "escalation_min_base_spans",
            )
        }
        spans = list(nlp_result.spans)
        new_components = list(nlp_result.novel_components)
        triggers: list[str] = []
        escalation_ms = 0.0
        esc_in = esc_out = 0
        escalation_failed = False
        pending_triggers: list[str] | None = None

        if deferred:
            # Both LLM calls move to the worker. The raw observation text IS
            # the un-enriched `original` head; the write-call scalars land
            # NULL (the pending marker — the worker's one-shot completion
            # fills them, and retrieval's importance-NULL neutral fallback
            # covers scoring meanwhile). A declared typology has nothing to
            # defer and stores now. The non-importance triggers are
            # evaluated here (their NLP raw material is not recoverable from
            # the DB) and persisted for the worker; the importance trigger
            # is the worker's to add once a model importance exists — the
            # -inf below cannot clear a non-negative threshold knob.
            haiku_ms = 0.0
            haiku_in = haiku_out = 0
            scoring_failed = False
            rendered_content = event.observation_text
            importance = None
            if event.typology is not None:
                typology, typology_source, typology_confidence = resolve_typology(
                    declared=event.typology,
                    declared_confidence=event.typology_confidence,
                    call_typology=None,
                    call_confidence=None,
                    config=config,
                    settings=self._settings,
                )
            else:
                typology = typology_source = typology_confidence = None
            pending_triggers = nlp.evaluate_triggers(nlp_result, float("-inf"), knobs)
        else:
            # --- single Haiku write call (soft degradation) ---------------
            t0 = time.perf_counter()
            write_outcome = await run_write_call(
                self._providers,
                observation_text=event.observation_text,
                diagnosticity_goal=agent["diagnosticity_goal"] or "",
                declared_typology=event.typology,
                neutral_importance=agent_knob(
                    config, "importance_neutral", self._settings
                ),
            )
            haiku_ms = _ms(time.perf_counter() - t0)
            rendered_content = write_outcome.rendered_content
            importance = write_outcome.importance
            scoring_failed = write_outcome.scoring_failed
            haiku_in = write_outcome.input_tokens
            haiku_out = write_outcome.output_tokens

            # --- typology: client declaration wins ------------------------
            typology, typology_source, typology_confidence = resolve_typology(
                declared=event.typology,
                declared_confidence=event.typology_confidence,
                call_typology=write_outcome.call_typology,
                call_confidence=write_outcome.call_confidence,
                config=config,
                settings=self._settings,
            )

            # --- escalation (biased loose; SOFT-DEGRADES on double failure:
            # the write lands with the base NLP-pass gist and sets
            # escalation_failed — the 2026-07-13 hard-stop was retired
            # 2026-07-22, migration 005) -----------------------------------
            triggers = nlp.evaluate_triggers(nlp_result, importance, knobs)
            if triggers:
                t0 = time.perf_counter()
                escalation = await escalate_with_retry(
                    self._providers,
                    observation_text=event.observation_text,
                    known_components=components,
                    candidate_spans=list(nlp_result.spans),
                    candidate_components=list(nlp_result.novel_components),
                    triggers=triggers,
                )
                escalation_ms = _ms(time.perf_counter() - t0)
                if escalation is None:
                    # Soft-degrade (ruled 2026-07-22): the gist-escalation
                    # call failed twice; proceed with the base NLP-pass
                    # spans/components (no merge) and flag it. A degraded
                    # gist is never a lost write.
                    escalation_failed = True
                else:
                    esc_in = escalation.input_tokens
                    esc_out = escalation.output_tokens
                    spans = _merge_spans(spans, escalation.spans)
                    new_components = _merge_components(
                        new_components, escalation.new_components
                    )

        # --- embedding (soft degradation: NULL embedding) -----------------
        t0 = time.perf_counter()
        embedding: list[float] | None = None
        location_embedding: list[float] | None = None
        embedding_failed = False
        embed_tokens = 0
        location_text = event.location_description or event.location_name
        texts = [event.observation_text] + ([location_text] if location_text else [])
        try:
            embed_result = await self._providers.gate.run(
                self._providers.embedding.embed, texts
            )
            embedding = embed_result.vectors[0]
            if location_text:
                location_embedding = embed_result.vectors[1]
            embed_tokens = embed_result.tokens
        except ProviderCallError:
            embedding_failed = True
        embed_ms = _ms(time.perf_counter() - t0)

        # --- assemble facts -----------------------------------------------
        decay_class, decay_class_unknown = _resolve_decay_class(
            event.decay_class, config
        )

        valence = nlp_result.affect_valence
        arousal = nlp_result.affect_arousal
        affect_detail = nlp_result.affect_detail
        if event.affect is not None:  # client override wins per field
            if event.affect.valence is not None:
                valence = event.affect.valence
            if event.affect.arousal is not None:
                arousal = event.affect.arousal
            if event.affect.detail is not None:
                affect_detail = {**(affect_detail or {}), "client": event.affect.detail}

        entities: list[str] = []
        for name in [*nlp_result.entities, *(event.entities or [])]:
            if name and name.lower() not in {e.lower() for e in entities}:
                entities.append(name)

        span_plans = plan_spans(event.observation_text, spans, new_components)

        # --- atomic insert -------------------------------------------------
        t0 = time.perf_counter()
        outcome = await db.insert_observation(
            self._pool,
            InsertPlan(
                agent_id=event.agent_id,
                observation_text=event.observation_text,
                rendered_content=rendered_content,
                valid_at=event.client_timestamp,
                importance_raw=importance,
                scoring_failed=scoring_failed,
                escalation_failed=escalation_failed,
                typology=typology,
                typology_confidence=typology_confidence,
                typology_source=typology_source,
                provenance=event.provenance,
                pinned=event.pinned,
                decay_class=decay_class,
                decay_class_unknown=decay_class_unknown,
                embedding=embedding,
                location_name=event.location_name,
                location_embedding=location_embedding,
                entities=entities or None,
                event_time=event.event_time,
                affect_valence=valence,
                affect_arousal=arousal,
                affect_detail=affect_detail,
                new_components=new_components,
                spans=span_plans,
                enrichment_pending=deferred,
                enrichment_pending_triggers=pending_triggers,
            ),
        )
        insert_ms = _ms(time.perf_counter() - t0)

        return IngestResult(
            memory_id=outcome.memory_id,
            detail_id=outcome.detail_id,
            fact_version_id=outcome.fact_version_id,
            gist_span_ids=outcome.gist_span_ids,
            new_component_ids=outcome.new_component_ids,
            importance_raw=importance,
            typology=typology,
            typology_confidence=typology_confidence,
            typology_source=typology_source,
            enrichment_pending=deferred,
            provenance=event.provenance,
            affect=AffectOut(valence=valence, arousal=arousal, detail=affect_detail),
            entities=entities,
            decay_class=decay_class,
            decay_class_unknown=decay_class_unknown,
            scoring_failed=scoring_failed,
            escalation_failed=escalation_failed,
            embedding_failed=embedding_failed,
            pinned=event.pinned,
            instrumentation=Instrumentation(
                nlp_ms=nlp_ms,
                embed_ms=embed_ms,
                haiku_ms=haiku_ms,
                insert_ms=insert_ms,
                total_ms=_ms(time.perf_counter() - t_total),
                haiku_input_tokens=haiku_in,
                haiku_output_tokens=haiku_out,
                embedding_tokens=embed_tokens,
                escalated=bool(triggers),
                escalated_by=triggers,
                escalation_ms=escalation_ms,
                escalation_input_tokens=esc_in,
                escalation_output_tokens=esc_out,
            ),
        )

    # ------------------------------------------------------------------ #
    # scene boundary — accept + instrument only (v1)
    # ------------------------------------------------------------------ #

    async def scene_boundary(self, event: SceneBoundaryEvent) -> SceneResult:
        """Scene edge. Recompiles the identity document (render seed prose ->
        content hash -> upsert), returning identity_version for the caller to
        freeze as scene state (the hybrid plumbing ruling). Since C7-B
        (2026-08-18) it carries its SECOND consumer: when the event supplies a
        probe (`prewarm_context`), the reconstruction pre-warm runs the
        dialogue-init retrieval/reconstruction path at the FRESHLY recompiled
        version + this boundary's basis, so the warm's cache write-backs land
        under the exact composed keys the first on-camera turn will look up.
        Absent probe => identity-recompile only (the off state)."""
        t_total = time.perf_counter()
        agent = await db.fetch_agent(self._pool, event.agent_id)
        if agent is None:
            raise UnknownAgentError(f"unknown agent_id {event.agent_id}")
        version, _rendered, created = await identity.ensure_identity_document(
            self._pool, event.agent_id, agent["seed_identity"]
        )
        prewarm: ScenePrewarmInstrumentation | None = None
        if event.prewarm_context and self._retrieval is not None:
            prewarm = await self._prewarm_reconstruction(event, version)
        return SceneResult(
            agent_id=event.agent_id,
            accepted=True,
            total_ms=_ms(time.perf_counter() - t_total),
            identity_version=version,
            identity_document_new=created,
            prewarm=prewarm,
        )

    async def _prewarm_reconstruction(
        self, event: SceneBoundaryEvent, version: str
    ) -> ScenePrewarmInstrumentation:
        """The C7-B reconstruction pre-warm: reuse `retrieve_dialogue_init`
        (embed -> fetch -> score -> serve) with the probe as the query, at the
        recompiled identity version + the boundary basis, so serve's write-backs
        warm the cache (and inherit serve's drift-budget refusal — R8). Best-
        effort: any failure returns a degraded record, never raises, so a warm
        failure can never fail the boundary. `self._retrieval` is guaranteed
        non-None by the caller's guard."""
        assert self._retrieval is not None
        try:
            result = await self._retrieval.retrieve_dialogue_init(
                DialogueInitRequest(
                    agent_id=event.agent_id,
                    query_text=event.prewarm_context,
                    identity_version=version,
                    scene_started_at=event.client_timestamp,
                    as_of=event.client_timestamp,
                )
            )
        except Exception as exc:  # noqa: BLE001 — the boundary must survive a warm failure
            logger.warning(
                "scene-boundary pre-warm failed for agent %s: %s", event.agent_id, exc
            )
            return ScenePrewarmInstrumentation(
                degraded=True, degraded_reason=f"pre-warm failed: {exc}"
            )
        instr = result.instrumentation
        return ScenePrewarmInstrumentation(
            embed_ms=instr.embed_ms,
            reconstruction_ms=instr.reconstruction_ms,
            candidate_count=instr.candidate_count,
            cache_hits=instr.cache_hits,
            cache_misses=instr.cache_misses,
            write_backs=instr.write_backs,
            drift_refusals=instr.drift_refusals,
            embedding_tokens=instr.embedding_tokens,
            reconstruction_input_tokens=instr.reconstruction_input_tokens,
            reconstruction_output_tokens=instr.reconstruction_output_tokens,
            reconstruction_embed_tokens=instr.reconstruction_embed_tokens,
            degraded=instr.degraded,
            degraded_reason=instr.degraded_reason,
        )

    # ------------------------------------------------------------------ #
    # agent provisioning (unity-client.md fork 2, ruled 2026-07-27)
    # ------------------------------------------------------------------ #

    async def create_agent(self, request: CreateAgentRequest) -> CreateAgentResult:
        """Provision one agent over the API — the integrator's minute-one
        verb. The UUID is minted server-side (stack constant); no model
        calls, no identity-document compile (that stays the scene-boundary
        handler's job, first boundary or session start), nothing hardcoded:
        unsupplied knobs land NULL and resolve config → SERVICE_DEFAULTS at
        read time exactly like a hand-provisioned row."""
        t_total = time.perf_counter()
        agent_id = await db.insert_agent(
            self._pool,
            name=request.name,
            seed_identity=request.seed_identity,
            rigidity=request.rigidity,
            diagnosticity_goal=request.diagnosticity_goal,
            config=request.config,
        )
        return CreateAgentResult(
            agent_id=agent_id,
            name=request.name,
            seed_identity=request.seed_identity,
            rigidity=request.rigidity,
            diagnosticity_goal=request.diagnosticity_goal,
            config=request.config or {},
            total_ms=_ms(time.perf_counter() - t_total),
        )

    # ------------------------------------------------------------------ #
    # pin / unpin
    # ------------------------------------------------------------------ #

    async def set_pin(self, memory_id: UUID, pinned: bool) -> PinResult:
        t_total = time.perf_counter()
        updated = await db.set_pinned(self._pool, memory_id, pinned)
        if not updated:
            raise UnknownMemoryError(f"unknown memory_id {memory_id}")
        return PinResult(
            memory_id=memory_id,
            pinned=pinned,
            total_ms=_ms(time.perf_counter() - t_total),
        )

    # ------------------------------------------------------------------ #
    # purge — the sole sanctioned content DELETE (C6, the release-blocker)
    # ------------------------------------------------------------------ #

    async def purge_memory(self, memory_id: UUID) -> PurgeResult:
        """Hard-delete one memory and everything beneath it (C6, ruled
        2026-08-18): the GDPR delete verb and the ONLY content DELETE in the
        store. Returns the per-table counts; raises UnknownMemoryError (→ 404)
        on an unknown id, nothing deleted. Reflections derived from the memory
        survive by design (purge honesty)."""
        t_total = time.perf_counter()
        outcome = await db.purge_memory(self._pool, memory_id)
        if outcome is None:
            raise UnknownMemoryError(f"unknown memory_id {memory_id}")
        return PurgeResult(
            memory_id=outcome.memory_id,
            corrections_deleted=outcome.corrections_deleted,
            cache_rows_evicted=outcome.cache_rows_evicted,
            fact_versions_deleted=outcome.fact_versions_deleted,
            enrichment_runs_deleted=outcome.enrichment_runs_deleted,
            gist_spans_deleted=outcome.gist_spans_deleted,
            details_deleted=outcome.details_deleted,
            total_ms=_ms(time.perf_counter() - t_total),
        )

    async def purge_agent_memories(self, agent_id: UUID) -> AgentPurgeResult:
        """Hard-delete every memory of one agent (the per-agent purge verb,
        ruled 2026-09-01 — the thin extension of C6): the same seven-table
        delete, set-scoped, in one transaction. Returns the summed counts;
        raises UnknownAgentError (→ 404) on an unknown agent, nothing
        deleted; a known agent with no memories returns zeros. The agent,
        its identity, and its reflections survive by design (purge
        honesty)."""
        t_total = time.perf_counter()
        outcome = await db.purge_agent_memories(self._pool, agent_id)
        if outcome is None:
            raise UnknownAgentError(f"unknown agent_id {agent_id}")
        return AgentPurgeResult(
            agent_id=outcome.agent_id,
            memories_deleted=outcome.memories_deleted,
            corrections_deleted=outcome.corrections_deleted,
            cache_rows_evicted=outcome.cache_rows_evicted,
            fact_versions_deleted=outcome.fact_versions_deleted,
            enrichment_runs_deleted=outcome.enrichment_runs_deleted,
            gist_spans_deleted=outcome.gist_spans_deleted,
            details_deleted=outcome.details_deleted,
            total_ms=_ms(time.perf_counter() - t_total),
        )

    # ------------------------------------------------------------------ #
    # authorial correction — the operator's replace-model fix
    # ------------------------------------------------------------------ #

    async def correct(
        self, memory_id: UUID, request: CorrectionRequest
    ) -> CorrectionResult:
        """Authorial correction (authorial-correction.md; fact-following
        since the fact-level build, fact-level-correction.md): the operator's
        text byte-verbatim into BOTH chains — the corrected telling head and
        the corrected fact row with its re-derived embedding AND re-derived
        entities (fork 3, 2026-07-19: mechanical NER over the corrected text
        merged with the optional operator field, the observe-path merge
        mirrored) — in one supersede-guarded transaction with cache eviction.
        The NER and embed calls run BEFORE the transaction (never a network
        call inside one); each failure is all-or-nothing fail-loud: nothing
        written, CorrectionNlpFailedError / CorrectionEmbedFailedError -> 502,
        the operator retries. The operator surface has no soft paths."""
        t_total = time.perf_counter()
        if not request.content.strip():
            raise ValueError("corrected content must be non-empty")
        t0 = time.perf_counter()
        try:
            ner_entities = await asyncio.to_thread(
                nlp.extract_entities, request.content
            )
        except Exception as exc:  # noqa: BLE001 — any NLP-stack failure is the same operator story
            raise CorrectionNlpFailedError(
                f"correction NER failed for {memory_id}; nothing was "
                f"written — fix the NLP install and retry: {exc}"
            ) from exc
        nlp_ms = _ms(time.perf_counter() - t0)
        # The observe-path merge, byte-for-byte (ingest_observation): NER
        # first, then operator-supplied, case-insensitive dedup.
        entities: list[str] = []
        for name in [*ner_entities, *(request.entities or [])]:
            if name and name.lower() not in {e.lower() for e in entities}:
                entities.append(name)
        t0 = time.perf_counter()
        try:
            embed_result = await self._providers.gate.run(
                self._providers.embedding.embed, [request.content]
            )
        except ProviderCallError as exc:
            raise CorrectionEmbedFailedError(
                f"correction embed failed for {memory_id}; nothing was "
                f"written — retry: {exc}"
            ) from exc
        embed_ms = _ms(time.perf_counter() - t0)
        outcome = await db.apply_authorial_correction(
            self._pool,
            memory_id=memory_id,
            content=request.content,
            valid_at=request.client_timestamp,
            embedding=embed_result.vectors[0],
            entities=entities or None,
            expected_detail_id=request.expected_detail_id,
        )
        if outcome == "unknown_memory":
            raise UnknownMemoryError(f"unknown memory_id {memory_id}")
        if outcome == "stale_head":
            raise CorrectionConflictError(
                f"live head moved for {memory_id}; re-read and re-issue"
            )
        return CorrectionResult(
            memory_id=memory_id,
            detail_id=outcome.detail_id,
            superseded_detail_id=outcome.superseded_detail_id,
            fact_version_id=outcome.fact_version_id,
            superseded_fact_version_id=outcome.superseded_fact_version_id,
            evicted_cache_rows=outcome.evicted_cache_rows,
            entities=entities,
            embed_ms=embed_ms,
            embedding_tokens=embed_result.tokens,
            nlp_ms=nlp_ms,
            total_ms=_ms(time.perf_counter() - t_total),
        )
