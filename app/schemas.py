"""schemas.py: ingestion and retrieval API v1 wire models (architecture.md
§5 and §6).

The FastAPI routes are pass-throughs: for one call, the route's JSON is
exactly the serialized result the service returned (`IngestResult` /
`RetrievalResult`). These models are therefore both the wire shape and the
service return shape.

Structural notes tied to the frozen migration-01 schema:
- `phase_tag` and `event_id` are accepted but have no schema home in v1
  (passthrough / idempotency-not-enforced per the spec); they are not stored
  and not echoed in results.
- `location_description`, when supplied, is embed-only (no raw column).
- `embedding_failed` reflects that an embedding-call failure lands the write
  with a NULL embedding; the queryable signal (architecture.md §4.4) is
  `memory_fact_versions.embedding IS NULL` on the live fact head — observe
  no longer writes `memories.embedding`. This field is its payload mirror.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Typology = Literal["observed", "told", "inferred", "reflected"]
Provenance = Literal["lived", "injected"]


class AffectOverride(BaseModel):
    """Optional client-supplied affect; overrides the lexicon pass per field."""

    valence: float | None = Field(default=None, ge=-1.0, le=1.0)
    arousal: float | None = Field(default=None, ge=0.0, le=1.0)
    detail: dict | None = None


class ObserveEvent(BaseModel):
    """The core `observe` event (architecture.md §5 event contract)."""

    agent_id: UUID
    observation_text: str = Field(min_length=1)
    phase_tag: str  # integrator vocabulary; passthrough, not interpreted in v1
    client_timestamp: datetime  # world time -> valid_at; must be tz-aware
    provenance: Provenance
    typology: Typology | None = None  # client declaration wins when present
    typology_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    decay_class: str | None = None  # validated against the agent's config map
    location_name: str | None = None
    location_description: str | None = None  # embed-only; no raw column
    entities: list[str] | None = None
    event_time: datetime | None = None
    affect: AffectOverride | None = None
    pinned: bool = False
    event_id: str | None = None  # idempotency key: accepted, not enforced in v1

    @field_validator("client_timestamp", "event_time")
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class SceneBoundaryEvent(BaseModel):
    """Scene edge. Recompiles the identity document (2026-07-17); C7-B adds the
    optional probe-driven reconstruction pre-warm."""

    agent_id: UUID
    client_timestamp: datetime
    scene_type: str | None = None  # integrator vocabulary; passthrough
    event_id: str | None = None
    # Probe-driven reconstruction pre-warm (C7-B, 2026-08-18): an anticipated
    # context probe for the incoming scene. Present + non-empty => the boundary
    # runs the dialogue-init retrieval/reconstruction path at the recompiled
    # identity version + this boundary's basis, warming the cache before the
    # first on-camera turn. Absent/empty => identity-recompile-only (the off
    # state; not sending it is off).
    prewarm_context: str | None = None

    @field_validator("client_timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class DiegeticCorrectionEvent(BaseModel):
    """The in-world confrontation event — POST /v1/events/diegetic-correction
    (architecture.md §8; the third route in the
    diegetic namespace). References a target `memory_id` by contract:
    automatic conflict discovery is CUT (2026-08-04) — the game names what
    was challenged. `challenge_typology` is REQUIRED (client declaration
    wins; a default would be a hardcoded evidence class);
    `challenge_weight` omitted resolves through
    `dissonance_challenge_weight_default`. `client_timestamp` is the
    confrontation's world time t_e — every stamp in the transaction.
    `source_event` lands verbatim in `corrections.source_event`.
    `expected_detail_id` mirrors the authorial CAS (409 on a moved head)."""

    agent_id: UUID
    memory_id: UUID
    challenge_text: str = Field(min_length=1)
    challenge_typology: Typology
    challenge_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    client_timestamp: datetime
    source_event: dict | None = None
    expected_detail_id: UUID | None = None
    event_id: str | None = None  # idempotency key: accepted, not enforced in v1

    @field_validator("client_timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class PinRequest(BaseModel):
    """Body of PUT /v1/memories/{memory_id}/pin."""

    pinned: bool


class CorrectionRequest(BaseModel):
    """Body of POST /v1/memories/{memory_id}/correction — the operator's
    replace-model fix (architecture.md §8). `content` is stored byte-verbatim as the corrected head — no
    model call touches it. `client_timestamp` is the correction's world time
    t_c (prior head invalid_at = corrected head valid_at — the coherent-
    chain-timeline precedent). `expected_detail_id`, when supplied, makes the
    supersede a compare-and-swap: 409 if the live head moved since the
    operator read it (never a silent correction of an unseen telling).
    `entities` (fork 3, 2026-07-19, mid-dialogue-gate.md): optional
    operator-supplied entities merged with the mechanical NER pass over the
    corrected text — the observe-path merge mirrored; absent => NER alone."""

    content: str = Field(min_length=1)
    client_timestamp: datetime
    expected_detail_id: UUID | None = None
    entities: list[str] | None = None

    @field_validator("client_timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class AffectOut(BaseModel):
    """Stored affect facts (valence/arousal columns + jsonb detail)."""

    valence: float | None
    arousal: float | None
    detail: dict | None


class Instrumentation(BaseModel):
    """Per-stage timing + token accounting, recorded once at the seam.

    All timings and Haiku token counts are non-null (done-when 8). Escalation
    fields stay at their zero-values when no escalation fired.
    """

    nlp_ms: float
    embed_ms: float
    haiku_ms: float
    insert_ms: float
    total_ms: float
    haiku_input_tokens: int
    haiku_output_tokens: int
    embedding_tokens: int
    escalated: bool = False
    escalated_by: list[str] = Field(default_factory=list)
    escalation_ms: float = 0.0
    escalation_input_tokens: int = 0
    escalation_output_tokens: int = 0


class IngestResult(BaseModel):
    """Structured return of `ingest_observation` — IDs + computed facts.

    Surfaced verbatim by the route and the CLI debug view; the suite asserts
    on this structure, never on prose.

    Since the deferred-write build (deferred-writes.md, ruled 2026-08-12)
    the write-call scalars are Optional: a deferred-mode observe returns
    them None with `enrichment_pending` true — there is no honest non-null
    value before the worker's completion. Sync observes (the default; knob
    `deferred_writes_enabled` 0.0) still populate every field.
    """

    # Identifiers
    memory_id: UUID
    detail_id: UUID  # the `original` head
    fact_version_id: UUID  # the `original` fact head (migration 002)
    gist_span_ids: list[UUID]
    new_component_ids: list[UUID]
    # Computed facts / scores
    importance_raw: float | None
    typology: Typology | None
    typology_confidence: float | None
    typology_source: Literal["declared", "inferred"] | None
    provenance: Provenance
    affect: AffectOut
    entities: list[str]
    decay_class: str
    decay_class_unknown: bool
    scoring_failed: bool
    escalation_failed: (
        bool  # gist-escalation double-failure soft-degrade (ruled 2026-07-22)
    )
    embedding_failed: bool
    pinned: bool
    enrichment_pending: bool = False  # deferred write awaiting the worker (006)
    # Instrumentation
    instrumentation: Instrumentation


class ScenePrewarmInstrumentation(BaseModel):
    """The scene-boundary reconstruction pre-warm's per-pass record (C7-B,
    2026-08-18). Populated only when the boundary carried a probe; the fields
    are the warm-relevant slice of the reused `retrieve_dialogue_init` pass
    (`RetrievalInstrumentation`). `cache_misses == 0` with `reconstruction_ms`
    near zero on the FIRST on-camera read at the same basis is the pre-warm's
    success signal. All defaulted, so a hard warm failure returns a degraded
    all-zero record rather than raising (the boundary must survive)."""

    embed_ms: float = 0.0  # the probe embedding
    reconstruction_ms: float = 0.0
    candidate_count: int = 0  # memories scored into the warm top-k
    cache_hits: int = 0  # already-warm past-theta slots
    cache_misses: int = 0  # reconstructed this pass
    write_backs: int = 0  # new head + cache rows written
    drift_refusals: int = 0  # retellings refused (prior head cached instead)
    embedding_tokens: int = 0
    reconstruction_input_tokens: int = 0
    reconstruction_output_tokens: int = 0
    reconstruction_embed_tokens: int = 0  # drift-check embeddings
    degraded: bool = False
    degraded_reason: str | None = None


class SceneResult(BaseModel):
    """Scene boundary result. Since the reconstruction build (2026-07-17) the
    handler recompiles the identity document server-side and returns its
    version — the boundary's first server-side consumer; the caller freezes
    `identity_version` as scene state (the caller-frozen-scene-state contract).
    `identity_document_new` is True when this version's row was inserted (an
    unchanged seed re-hashes to the existing version). `prewarm` is the C7-B
    reconstruction-pre-warm record — None unless the boundary carried a probe
    (the off state)."""

    agent_id: UUID
    accepted: bool
    total_ms: float
    identity_version: str | None = None
    identity_document_new: bool = False
    prewarm: ScenePrewarmInstrumentation | None = None


class PinResult(BaseModel):
    """Result of toggling memories.pinned."""

    memory_id: UUID
    pinned: bool
    total_ms: float


class CorrectionResult(BaseModel):
    """Result of the authorial correction — both chains' head swaps + IDs +
    instrumentation. v1's "no token fields — no model calls" line is
    superseded (architecture.md §4.4): one embed call
    rides the verb, so the corrected fact basis can steer retrieval; its
    timing and tokens land here. Since the gate build (fork 3, 2026-07-19)
    the verb also re-derives entities: `entities` is the merged NER +
    operator-field list written to the corrected fact head, `nlp_ms` the
    mechanical NER pass's timing (non-LLM — no token count exists)."""

    memory_id: UUID
    detail_id: UUID  # the corrected telling head
    superseded_detail_id: UUID
    fact_version_id: UUID  # the corrected fact head (migration 002)
    superseded_fact_version_id: UUID
    evicted_cache_rows: int
    entities: list[str] = Field(default_factory=list)
    embed_ms: float
    embedding_tokens: int
    nlp_ms: float = 0.0
    total_ms: float


class DiegeticCorrectionResult(BaseModel):
    """Result of the diegetic-correction event (architecture.md §8), flat,
    instrumentation rides the response (the CorrectionResult no-runs-table
    precedent; the `corrections` row is the persistent record). Every
    resolved decision input is exposed so a structural test recomputes both
    sides from fixture values by hand. Tellings-only by ruling: no fact
    fields exist. `content` is the new head's retell — the reconstruction
    role's prose (never a test surface); `retell_*` names the call by
    function, its spend prices under the reconstruction role's keys."""

    memory_id: UUID
    agent_id: UUID
    verb: Literal["rationalization", "update_with_resentment"]
    correction_id: UUID
    detail_id: UUID  # the new diegetic head
    superseded_detail_id: UUID
    pinned: bool  # inherited — pin is outranked, never consulted
    content: str
    resistance: float
    challenge: float
    importance_norm: float
    rigidity_effective: float
    typology_mult_memory: float
    typology_mult_challenge: float
    challenge_weight_effective: float
    evicted_cache_rows: int
    retell_ms: float
    retell_input_tokens: int
    retell_output_tokens: int
    total_ms: float


# ---------------------------------------------------------------------------
# Purge (docs\architecture.md §12; the C6 rulings dated 2026-08-18)
# ---------------------------------------------------------------------------


class PurgeResult(BaseModel):
    """Result of DELETE /v1/memories/{memory_id} (C6) — the per-table row
    counts the purge removed, echoed for the caller and asserted by the
    structural tests. Reflections derived from the memory are not touched, so
    no reflection field appears; 404 (not this body) on an unknown id."""

    memory_id: UUID
    corrections_deleted: int
    cache_rows_evicted: int
    fact_versions_deleted: int
    enrichment_runs_deleted: int
    gist_spans_deleted: int
    details_deleted: int
    total_ms: float


class AgentPurgeResult(BaseModel):
    """Result of DELETE /v1/agents/{agent_id}/memories (the per-agent purge,
    ruled 2026-09-01 as the thin extension of the C6 carve-out; contract
    ruled 2026-09-02): how many memories went plus the SUMMED per-table
    child counts (PurgeResult's field names). A known agent with no memories
    returns all zeros (200, never 404); the agent row, its identity,
    reflections, bundles, and run logs are untouched, so none appears here;
    404 (not this body) on an unknown agent."""

    agent_id: UUID
    memories_deleted: int
    corrections_deleted: int
    cache_rows_evicted: int
    fact_versions_deleted: int
    enrichment_runs_deleted: int
    gist_spans_deleted: int
    details_deleted: int
    total_ms: float


# ---------------------------------------------------------------------------
# Reflection (docs\reflection.md; the C2 rulings dated 2026-08-15)
# ---------------------------------------------------------------------------


class ReflectRequest(BaseModel):
    """Body of POST /v1/agents/{agent_id}/reflect — an agent-scoped
    operator/integrator verb (`/v1/events/*` stays diegetic; the
    correction-route precedent). `client_timestamp` is the reflect event's
    world time: the written rows' valid_at AND the pipeline's single time
    basis (sampling age, trim staleness) — the as_of / scene-frozen-basis
    precedent, so tests and walkers freeze the clock by freezing the
    request. `consolidate` overrides the consolidation trigger this call:
    True forces the stage (RRR still guards), False suppresses it, absent
    lets the reflection_consolidate_at knob decide (spec ruling 1)."""

    client_timestamp: datetime
    consolidate: bool | None = None

    @field_validator("client_timestamp")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class ReflectionOut(BaseModel):
    """One stored conclusion: id, content, and the grounding citations —
    mechanically validated at the seam (non-empty AND a subset of the
    sampled ids) before anything writes."""

    reflection_id: UUID
    content: str
    identity_relevant: bool
    source_memory_ids: list[UUID]


class ConsolidationOut(BaseModel):
    """The consolidation stage's outcome when it ran. Success = the new
    consolidated reflection's id + the rows it absorbed (bi-temporally:
    invalid_at, never deleted; provenance flows by source union). `failed`
    True is the SOFT path (the escalation precedent): the stage was due and
    its call or write failed — the step-7 writes stand, id/absorbed stay
    empty."""

    reflection_id: UUID | None = None
    absorbed_reflection_ids: list[UUID] = Field(default_factory=list)
    failed: bool = False


class ReflectInstrumentation(BaseModel):
    """Per-stage timing + token accounting, recorded once at the seam. The
    ENDPOINT's accounting rides here (route-passthrough); worker runs
    persist to reflection_runs instead — the C1 endpoint/worker split.
    Consolidation fields stay at their zero-values when the stage never
    ran."""

    reflect_ms: float
    consolidation_ms: float = 0.0
    insert_ms: float
    total_ms: float
    reflect_input_tokens: int
    reflect_output_tokens: int
    consolidation_input_tokens: int = 0
    consolidation_output_tokens: int = 0


class ReflectResult(BaseModel):
    """The reflect verb's result (reflection.md wire contract).

    The IDs+scores invariant, stated: reflect is a WRITE verb — the
    weighted sampling draw is not the retrieval seam and produces no
    relevance scores; `sampled_memory_ids` and each conclusion's citations
    ride as grounding evidence, unscored by nature. `rrr` is None when the
    agent had no prior live reflections to compare against (and when zero
    conclusions survived — nothing to compare). Pressure is served, never
    stored (architecture §2's runtime-state rule)."""

    agent_id: UUID
    reflections: list[ReflectionOut]
    sampled_memory_ids: list[UUID]
    dropped_ungrounded: int
    rrr: float | None
    rrr_blocked_consolidation: bool
    consolidation: ConsolidationOut | None
    pruned_component_ids: list[UUID]
    evicted_cache_rows: int
    pressure_before: float
    pressure_after: float
    identity_version: str
    identity_document_new: bool
    instrumentation: ReflectInstrumentation


# ---------------------------------------------------------------------------
# Read path: dialogue-init retrieval (architecture.md §6)
# ---------------------------------------------------------------------------


class WeightOverrides(BaseModel):
    """Per-call scoring multipliers (reserved 2026-07-14; live for the
    split-brain behavior view 2026-07-21; moved to the PROSE view by the A1
    re-shape 2026-08-04 — weights-on-speech).

    On `DialogueTurnRequest` these resolve the turn's re-rank of the served
    top-k feeding the prose prompt (exponent-form on the product score, so
    1.0 reproduces the served ranking — the parity contract). The NPC's words
    are shaped by weights it is unaware of; retrieval scoring itself is
    byte-untouched.
    """

    relevance: float | None = None
    recency: float | None = None
    importance: float | None = None


class DialogueInitRequest(BaseModel):
    """Dialogue-init retrieval request (architecture.md §6 request contract).

    `query_text` is embedded AS-IS (ruled 2026-07-14: the integrator authors
    the probe; the service never composes prose — that ruling stands).
    `location_name`/`entities`/`event_time` are the CLIENT-SUPPLIED
    encoding-context fields (consumed since the 2026-07-20 encoding-context
    build; formerly reserved): each supplied field adds a weighted match
    component to a soft multiplicative score nudge (RaMem-shape; knobs in
    config). Absent fields => the term is skipped entirely and scoring is
    byte-identical to the pre-context read path. Affect is deliberately NOT
    a context field (ruled 2026-07-14) — its query-side shape is still
    undesigned. `as_of` is the world-time override for age computation
    (Set B / time-travel surface).
    """

    agent_id: UUID
    query_text: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    location_name: str | None = None  # context: casefold match vs the row's
    entities: list[str] | None = None  # context: fact-head entity coverage
    event_time: datetime | None = None  # context: proximity kernel
    as_of: datetime | None = None  # defaults to server now (UTC)
    # Caller-frozen scene state (reconstruction build 2026-07-17): the
    # identity version returned by the last scene boundary, and the boundary's
    # world time — the basis for every text-affecting decay evaluation (theta,
    # band, thinning), so read-mode and served text cannot flip mid-scene.
    # Absent -> the basis falls back to as_of_effective and the identity
    # document lazy-bootstraps; an unknown version is a loud contract error.
    identity_version: str | None = None
    scene_started_at: datetime | None = None
    # Caller-held loaded set (mid-dialogue-gate.md fork 1, 2026-07-19 — the
    # third application of the caller-freezes-scene-state contract): the
    # scene's already-surfaced memory IDs, append-only, reset by the caller
    # at scene boundaries. Absent -> loader turn, v1 byte-parity (the gate
    # never evaluates). `gate_fruitless_streak` is the damper's caller-held
    # consecutive-fruitless-fetch count (the caller-frozen-scene-state trust
    # class). The context `entities` field above is NOT the
    # gate's input — the tripwire reads the utterance text; the context term
    # and the gate consume the same request independently.
    loaded_memory_ids: list[UUID] | None = None
    gate_fruitless_streak: int = Field(default=0, ge=0)

    @field_validator("event_time", "as_of", "scene_started_at")
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class RetrievedMemory(BaseModel):
    """One ranked item: IDs + scores alongside prose (load-bearing — the test
    suite asserts on this structure, never on prose)."""

    memory_id: UUID
    detail_id: UUID  # the served detail row (Set A's corrected-head surface)
    content: str  # the served text: live head, or the reconstruction cache row
    read_mode: Literal["verbatim", "reconstructed"]  # three-state boundary,
    # real since the reconstruction build (2026-07-17); honest to what was
    # actually served — a failed reconstruction serves the head and says so.
    pinned: bool
    score: float  # relevance x recency x importance_norm, times the
    # encoding-context factor when the request supplied context fields
    # (2026-07-20 build; factor >= 1, absent on no-context turns)
    relevance: float | None  # null on the degraded (no-vector) path
    recency: float
    importance_norm: float
    importance_raw: float  # the debug view's raw axis (as fed to the formula)
    gate_fetched: bool = False  # appended by a mid-scene gate fetch this turn
    # (mid-dialogue-gate.md, 2026-07-19); the caller appends these IDs to its
    # loaded set. Defaulted: pre-gate construction sites stand.


class GateInstrumentation(BaseModel):
    """The mid-dialogue gate's per-turn record (mid-dialogue-gate.md, built
    2026-07-19). Fully defaulted — loader turns carry the all-default shape
    (`evaluated=False`). `signals_fired` uses the gate's named constants
    (app\\gate.py — the escalated_by precedent); instrumentation-only by
    fork 4 (no gate_events table; the load driver aggregates these fields,
    and the reserved novelty kill-switch decision reads run artifacts).
    Timing decomposition: `gate_ms` = loaded-set fetch + components fetch +
    signal evaluation + decision; the probe/lexical fetch stays in `sql_ms`
    (0.0 on closed turns — the zero-probe-SQL claim); the one utterance
    embed stays in `embed_ms` (it doubles as the fetch probe). Efficacy
    booleans are None unless their signal fired with a computable basis
    (§11 comparators, ruled with the build)."""

    evaluated: bool = False  # False = loader turn (absent fields or gate_enabled 0)
    fired: bool = False
    signals_fired: list[str] = Field(default_factory=list)
    degraded_rung: str | None = None  # entity_only | novelty_only | closed
    novelty_min_distance: float | None = None
    null_embedding_loaded_count: int = 0  # excluded from the novelty basis
    loaded_missing_count: int = 0  # unknown/foreign/dead IDs dropped by the join
    uncovered_entities: list[str] = Field(default_factory=list)  # canonicals
    fetched_memory_ids: list[UUID] = Field(default_factory=list)
    fetched_new_count: int = 0
    fruitless: bool = False  # a fire that appended zero new IDs (damper input)
    damper_active: bool = False  # novelty suppressed this turn (streak >= max)
    novelty_outscored: bool | None = None  # top fetched score > min loaded score
    entity_covered: bool | None = None  # fetch contained the tripwire entity
    gate_ms: float = 0.0
    reconstructing_blocked: bool = False  # a mid-scene serve blocked (fork 5)


class RetrievalInstrumentation(BaseModel):
    """Per-stage timing + token accounting, recorded once at the seam.

    Feeds architecture §11's latency decomposition; surfaced verbatim in the
    CLI debug view. `degraded` mirrors the ruled fail-quiet embedding
    fallback; `as_of_effective` is the age-computation timestamp actually
    used.
    """

    embed_ms: float
    sql_ms: float
    score_ms: float
    total_ms: float
    embedding_tokens: int
    candidate_count: int
    k_effective: int
    # Hybrid lexical channel (built 2026-07-20, migration 004). Defaulted:
    # pre-hybrid constructions stand. `sql_ms` stays the vector probe alone;
    # the lexical fetch's time and raw (pre-dedup) hit count get their own
    # lines — the instrument-at-the-seam decomposition. Both zero on gated,
    # degraded, tokenless, and lexical_fetch_k=0 turns.
    lexical_sql_ms: float = 0.0
    lexical_candidate_count: int = 0
    degraded: bool = False
    degraded_reason: str | None = None
    as_of_effective: datetime
    # Encoding-context term (built 2026-07-20). Defaulted: pre-context
    # constructions and payload shapes stand. Which components were active
    # is instrumentation-level by design — the scored tuple and the serving
    # stage are deliberately untouched (reconstruction byte-identical).
    context_active: bool = False
    context_components: list[str] = Field(default_factory=list)
    # Reconstruction serving stage (architecture.md §7).
    # All defaulted: pre-swap constructions and payload shapes stand. Failures
    # in the serving stage reuse degraded/degraded_reason above.
    reconstruction_ms: float = 0.0
    reconstruction_input_tokens: int = 0
    reconstruction_output_tokens: int = 0
    reconstruction_embed_tokens: int = 0  # drift-check embeddings
    cache_hits: int = 0
    cache_misses: int = 0
    write_backs: int = 0
    drift_refusals: int = 0
    identity_version_effective: str | None = None
    identity_bootstrapped: bool = False  # no version passed; ensured lazily
    # The gate stage (mid-dialogue-gate.md, built 2026-07-19). Defaulted:
    # pre-gate constructions and payload shapes stand.
    gate: GateInstrumentation = Field(default_factory=GateInstrumentation)


class RetrievalResult(BaseModel):
    """Structured return of `retrieve_dialogue_init`; the route serves it
    verbatim (route-is-pass-through). Reserved request fields are never
    echoed here."""

    items: list[RetrievedMemory]  # ranked; <= k on loader turns. Gated turns
    # serve the whole loaded set (+ any gate fetch), so the count may exceed
    # k — append-only within a scene, damper-bounded (mid-dialogue-gate.md).
    instrumentation: RetrievalInstrumentation


# ---------------------------------------------------------------------------
# Dialogue turn: the dialogue seam (architecture.md §9). Four consumers today: the REPL and the load driver call the
# seam in-process, and both HTTP routes serve these models — `POST
# /v1/dialogue/turn` (2026-07-23) and its SSE twin `POST
# /v1/dialogue/turn/stream` (2026-07-27), which the C# client mirrors
# field-for-field. Pydantic by ruling, mirroring the write/read payloads.
# ---------------------------------------------------------------------------


class ScoredRef(BaseModel):
    """One (memory_id, score) tuple in a ranked view — the unit of the turn
    result's `dialogue_view` (weights-on-speech, A1 re-shape 2026-08-04): the
    weight-ranked ordering the seam computed for the prose prompt, assertable
    structurally, prose-free."""

    memory_id: UUID
    score: float


class DialogueTurnRequest(BaseModel):
    """One dialogue turn (architecture.md §9 request contract).

    Scene state lives in the caller (identity version, scene basis time,
    loaded set, context) and rides on every request unreinterpreted.
    `weight_overrides` is the live weights-on-speech slot: per-call
    multipliers re-rank the served view feeding the prose prompt.
    `k` / `as_of` pass through to retrieval unreinterpreted; `debug` is a
    caller-side rendering hint, inert to the seam's computation.
    """

    agent_id: UUID
    utterance: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    as_of: datetime | None = None
    # Caller-held scene context (encoding-context build 2026-07-20) — passed
    # through to retrieval unreinterpreted, the k/as_of precedent. The game
    # client knows the scene's location/participants/time; the service never
    # derives them (ruled: client-supplied fields, no LLM decomposition).
    location_name: str | None = None
    entities: list[str] | None = None
    event_time: datetime | None = None
    # Caller-frozen scene state, passed through to retrieval unreinterpreted
    # (reconstruction build 2026-07-17).
    identity_version: str | None = None
    scene_started_at: datetime | None = None
    # Caller-held loaded set + damper streak (mid-dialogue-gate.md fork 1,
    # 2026-07-19) — passed through to retrieval unreinterpreted, the
    # identity_version precedent. Absent -> loader turn, v1 byte-parity.
    loaded_memory_ids: list[UUID] | None = None
    gate_fruitless_streak: int = Field(default=0, ge=0)
    # Weights-on-speech (A1 re-shape 2026-08-04; supersedes the split-brain
    # behavior view): the per-call WeightOverrides re-rank the served set
    # feeding the PROSE prompt (request field wins over agents.config wins
    # over 1.0; all-1.0 reproduces the served ranking — the parity contract).
    weight_overrides: WeightOverrides | None = None
    # The compiled-parameter scene type (parameter-compiler.md, C3
    # 2026-08-17): selects which compiled bundles multiply the resolved
    # weights. Absent -> the reserved default type; an unconfigured value ->
    # log-and-continue against the default (ruled), flagged in
    # instrumentation. Never reinterpreted beyond that resolution.
    scene_type: str | None = None
    debug: bool = False

    @field_validator("as_of", "scene_started_at", "event_time")
    @classmethod
    def _tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class DialogueTurnInstrumentation(BaseModel):
    """Per-turn timing + token accounting, recorded once at the seam.

    Feeds architecture §11's latency histogram — the gate term landed with
    the gate build (2026-07-19, `retrieval.gate.gate_ms`; the reservation is
    closed) — and the per-100-turn cost table. Token counts are unconditional;
    `cost_usd` is populated only when TWICETOLD_PRICE_* env vars are set
    (build ruling 2026-07-15 — no hardcoded model pricing), covering the
    dialogue call plus the priced share of the query embedding.
    """

    retrieval: RetrievalInstrumentation
    # The prose (dialogue-role) call. `sonnet_*` names kept for series
    # continuity; since the split-brain build this is the STREAMING PROSE call.
    sonnet_ms: float  # total prose stream duration (== prose_stream_ms)
    sonnet_first_token_ms: float  # == first_word_ms (prose TTFT at the seam)
    total_ms: float
    sonnet_input_tokens: int
    sonnet_output_tokens: int
    cost_usd: float | None = None
    degraded: bool = False  # the never-blank path was taken
    degraded_reason: str | None = None
    # Streaming terms (2026-07-21 build; the behavior/apply terms left with the
    # A1 re-shape 2026-08-04). Defaulted: pre-split constructions stand.
    # `first_word_ms` is the HEADLINE latency term (prose TTFT at the seam —
    # the <1s viability bar); `prose_stream_ms` the full stream.
    first_word_ms: float = 0.0
    prose_stream_ms: float = 0.0
    # Perceived TTFT (HTTP turn-route build, 2026-07-23 — the audit's honest
    # latency metric): first-chunk time measured from TURN START (t_total),
    # so it includes agent fetch + retrieval — everything `first_word_ms` is
    # blind to (notably a cold reconstruction stall). The <1s viability bar
    # is measured against THIS field; `first_word_ms` stays for series
    # continuity. 0.0 when no chunk ever arrived (the first_word_ms precedent).
    perceived_first_word_ms: float = 0.0
    # Concurrency-cap queue wait (C7, 2026-08-18): ms this turn's PROSE call
    # spent waiting for a ModelCallGate slot before the stream started — 0.0
    # uncontended, > 0 when the cap is saturated. perceived_first_word_ms
    # already folds this into the end-to-end TTFT; this isolates the queueing
    # component. Defaulted: pre-C7 constructions stand.
    gate_wait_ms: float = 0.0
    # Parameter-compiler consume terms (parameter-compiler.md, C3
    # 2026-08-17). Defaulted: pre-C3 constructions stand. `bundle_w_*` are
    # the COMPOSED multiplier products applied over the resolved base
    # weights (all 1.0 = zero bundles = the parity contract);
    # `bundle_reflection_ids` the contributing beliefs in window order;
    # `bundle_fetch_ms` the consume read's cost on this turn (one indexed
    # query, bundle-free agents included — recorded honestly).
    scene_type_resolved: str = "default"
    scene_type_unknown: bool = False
    bundle_w_relevance: float = 1.0
    bundle_w_recency: float = 1.0
    bundle_w_importance: float = 1.0
    bundle_reflection_ids: list[UUID] = Field(default_factory=list)
    bundle_fetch_ms: float = 0.0


class DialogueTurnResult(BaseModel):
    """Structured return of `run_dialogue_turn` — surfaced verbatim in the
    CLI debug view; the suite asserts on this structure, never on prose.
    `content` is the only unassertable field."""

    agent_id: UUID
    content: str
    items: list[RetrievedMemory]  # retrieval echo: IDs + scores invariant
    # The weight-ranked view that fed the prose prompt (weights-on-speech,
    # A1 re-shape 2026-08-04): the SAME served memories re-scored with the
    # resolved per-call weights, sorted (-score, memory_id). On a LOADER
    # turn at all-1.0 weights this equals the (id, score) projection of
    # `items` — the parity contract, carried over from the split-brain
    # build. On gated turns `items` keeps the loaded+fetched serve shape
    # while this field is the global weight ranking, and the prompt's
    # [memories] block still renders the loaded set in the caller's
    # append-only order (the byte-stable-prefix ruling, 2026-07-19).
    # Defaulted: pre-split constructions stand.
    dialogue_view: list[ScoredRef] = Field(default_factory=list)
    instrumentation: DialogueTurnInstrumentation


class LedgerTurnEntry(BaseModel):
    """One teed dialogue turn in the Ledger's live feed (E2, ruled
    2026-08-19). `result` is the DialogueTurnResult serialization VERBATIM —
    the Ledger's turn panel renders it exactly as the paste/drop path would,
    so a trimmed projection would break the page's field reads."""

    seq: int
    result: DialogueTurnResult


class LedgerTurnsResult(BaseModel):
    """Response of GET /v1/ledger/turns (E2, ruled 2026-08-19): the entries
    newer than the caller's `after` cursor, plus `last_seq` for the next
    poll. In-memory and process-local by ruling — nothing is persisted, and
    a restart starts the feed empty at seq 0."""

    entries: list[LedgerTurnEntry]
    last_seq: int


# ---------------------------------------------------------------------------
# Agent provisioning + inspector reads (docs\unity-client.md, ruled
# 2026-07-27 — forks 2 and 3: the integrator's minute-one route and The
# Ledger's product-surface data source)
# ---------------------------------------------------------------------------


class CreateAgentRequest(BaseModel):
    """Body of POST /v1/agents (unity-client.md fork 2). The UUID is minted
    server-side (stack constant); every accepted field is optional — an agent
    is viable with just a name, and knobs default through `agents.config` →
    `SERVICE_DEFAULTS` exactly as for a hand-provisioned row. `rigidity`
    bounds mirror the schema CHECK. The A1 re-shape (2026-08-04) removed the
    reputation fields from this surface; the schema columns remain, never
    written or read."""

    name: str = Field(min_length=1)
    seed_identity: str | None = None
    rigidity: float | None = Field(default=None, ge=0.5, le=2.0)
    diagnosticity_goal: str | None = None
    config: dict | None = None


class CreateAgentResult(BaseModel):
    """Result of agent provisioning — the minted ID + the stored fields."""

    agent_id: UUID
    name: str
    seed_identity: str | None
    rigidity: float | None
    diagnosticity_goal: str | None
    config: dict
    total_ms: float


class DetailVersionOut(BaseModel):
    """One row of a memory's telling chain (memory_details) — superseded
    rows ride with `invalid_at` set; `is_live` = the at-most-one head."""

    detail_id: UUID
    content: str
    write_cause: str | None
    created_at: datetime
    valid_at: datetime
    invalid_at: datetime | None
    is_live: bool


class FactVersionOut(BaseModel):
    """One row of a memory's fact chain (memory_fact_versions, migration
    002/003). The vector itself never rides the wire — `has_embedding` is
    the payload mirror of the embed-degradation signal on each row."""

    fact_version_id: UUID
    basis_text: str
    write_cause: str | None
    created_at: datetime
    valid_at: datetime
    invalid_at: datetime | None
    is_live: bool
    has_embedding: bool
    entities: list[str] = Field(default_factory=list)


class GistSpanOut(BaseModel):
    """One gist span — offsets into the immutable observation_text; the
    consumer slices the text itself (the spans ARE the gist floor The
    Ledger's gist/detail number counts)."""

    span_id: UUID
    start_char: int
    end_char: int
    matched_category: str | None


class EnrichmentRunOut(BaseModel):
    """One deferred-enrichment attempt's persisted accounting
    (memory_enrichment_runs, migration 006) — the background worker has no
    response payload to ride, so instrument-at-the-seam surfaces here, on
    the unscored inspector read."""

    attempt: int
    outcome: Literal["completed", "completed_facts_only", "failed", "terminal_degraded"]
    error: str | None
    triggers: list[str]
    escalation_failed: bool
    embedding_repaired: bool
    write_ms: float | None
    escalation_ms: float | None
    embed_ms: float | None
    insert_ms: float | None
    total_ms: float | None
    write_input_tokens: int
    write_output_tokens: int
    escalation_input_tokens: int
    escalation_output_tokens: int
    embedding_tokens: int
    created_at: datetime


class CorrectionOut(BaseModel):
    """One diegetic confrontation record (corrections, schema since 001;
    architecture.md §8): the verb, the head the confrontation
    produced, and the client's in-world reference verbatim. The unscored
    chain read is its inspector surface (the enrichment-run-log
    precedent)."""

    correction_id: UUID
    detail_id: UUID  # the head this confrontation produced
    verb: Literal["rationalization", "update_with_resentment"]
    source_event: dict | None
    created_at: datetime
    valid_at: datetime


class MemoryChainResult(BaseModel):
    """GET /v1/memories/{id}/chain — The Ledger's ground-truth-vs-telling
    read (unity-client.md fork 3, ruled 2026-07-27): the immutable
    observation beside BOTH version chains, superseded rows present (greyed
    client-side, never dropped — the non-destructive record made visible).
    An unscored inspector read: no retrieval ran, so there are no scores —
    IDs and structured fields on every row keep the read-payload discipline.
    `memories.entities` is deliberately NOT echoed (frozen at the 003
    freeze; the live fact head's entities are the current ones). Since the
    deferred-write build (006) the pending flag, attempt counter, and the
    per-attempt run log ride here — the deferred window's inspector
    surface."""

    memory_id: UUID
    agent_id: UUID
    observation_text: str
    provenance: Provenance
    typology: Typology | None
    decay_class: str | None
    pinned: bool
    scoring_failed: bool
    escalation_failed: bool
    decay_class_unknown: bool
    created_at: datetime
    valid_at: datetime
    invalid_at: datetime | None
    location_name: str | None
    event_time: datetime | None
    enrichment_pending: bool = False
    enrichment_attempts: int = 0
    enrichment_runs: list[EnrichmentRunOut] = Field(default_factory=list)
    # Diegetic confrontation records (architecture.md §8), defaulted, so
    # every pre-C4 construction stands and the read stays additive.
    corrections: list[CorrectionOut] = Field(default_factory=list)
    details: list[DetailVersionOut]
    facts: list[FactVersionOut]
    gist_spans: list[GistSpanOut]
    total_ms: float


class MemorySummaryOut(BaseModel):
    """One row of The Ledger's per-agent index: the immutable observation
    beside the live telling head (`live_content` — None only for a
    legacy-shaped row with no live head)."""

    memory_id: UUID
    observation_text: str
    live_content: str | None
    live_write_cause: str | None
    detail_count: int
    pinned: bool
    valid_at: datetime
    invalid_at: datetime | None


class AgentMemoriesResult(BaseModel):
    """GET /v1/agents/{agent_id}/memories — The Ledger's index read.
    `total_count` is the agent's full memory count; `memories` carries at
    most `limit` rows, newest valid_at first (memory_id tiebreak — the
    deterministic-order precedent)."""

    agent_id: UUID
    memories: list[MemorySummaryOut]
    total_count: int
    limit: int
    total_ms: float


class ReconstructionMetricsResult(BaseModel):
    """GET /v1/memories/{id}/reconstruction-metrics — the judge-free metric
    read (eval-harness.md stage 1, ruled 2026-07-29): gist-precision /
    detail-recall / fabrication / keyword-retention computed server-side
    against the LIVE telling head only (fork 6). Runs no retrieval (the
    IDs-and-scores invariant does not bind) and performs ZERO writes —
    identity render is pure, never the ensure_ upsert. Honest denominators:
    every ratio is None when its denominator is empty, and a chain with no
    live head reports counts with every ratio None (the degraded-path
    precedent). `gist_facts_total` counts MEASURABLE facts (merged spans —
    or anchor sentences on a correction-anchored chain — whose content-lemma
    sets are non-empty); `cache_bands` are the decay bands observed in this
    memory's reconstruction-cache keys, the ruled band-binning source."""

    memory_id: UUID
    agent_id: UUID
    live_detail_id: UUID | None
    live_write_cause: str | None
    anchor_cause: str | None
    gist_facts_total: int
    gist_facts_present: int
    gist_precision: float | None
    detail_lemmas_total: int
    detail_lemmas_present: int
    detail_recall: float | None
    telling_entities: list[str] = Field(default_factory=list)
    fabricated_entities: list[str] = Field(default_factory=list)
    fabrication_rate: float | None
    keyword_retention: float | None
    cache_bands: list[int] = Field(default_factory=list)
    metrics_ms: float
    total_ms: float


# ---------------------------------------------------------------------------
# The agent-state read (C5, ruled 2026-08-17 — the FOURTH unscored-by-contract
# member): the composed runtime snapshot that four earlier builds recorded
# this route as the consumer for — reflection.md's pressure gauge, the 007/008
# run logs, and compiled_bundles.passthrough (the future-integrator read).
# ---------------------------------------------------------------------------


class ReflectionSummaryOut(BaseModel):
    """One live belief (a reflections row) as the state read serves it —
    content + provenance. Served in the ruled compiler-window order
    (valid_at DESC, created_at DESC, reflection_id), so the first
    compiler_window_k rows ARE the compile window, by construction."""

    reflection_id: UUID
    content: str
    identity_relevant: bool
    source_memory_ids: list[UUID] = Field(default_factory=list)
    valid_at: datetime
    created_at: datetime


class CompiledBundleOut(BaseModel):
    """The newest live bundle for one (belief, scene_type) pair — liveness
    DERIVED from the source reflection being live (the §10 contract; no
    stored flag exists to echo). `passthrough` is the integrator's
    namespaced data verbatim: stored, never interpreted server-side — this
    read is its recorded surface (parameter-compiler.md)."""

    bundle_id: UUID
    reflection_id: UUID
    scene_type: str
    w_relevance: float
    w_recency: float
    w_importance: float
    passthrough: dict = Field(default_factory=dict)
    input_tokens: int
    output_tokens: int
    compile_ms: float | None
    created_at: datetime


class ReflectionRunOut(BaseModel):
    """One reflection-worker run row (migration 007), full column mirror —
    the EnrichmentRunOut precedent: a background seam has no response
    payload to ride, so its persisted accounting surfaces on an unscored
    read. Endpoint reflects write NO row (the endpoint/worker split), so an
    agent driven only through the reflect verb shows an empty log here."""

    run_id: UUID
    outcome: Literal["completed", "failed"]
    error: str | None
    reflections_written: int
    dropped_ungrounded: int
    consolidation_ran: bool
    consolidation_failed: bool
    rrr: float | None
    rrr_blocked: bool
    pruned_components: int
    evicted_cache_rows: int
    pressure_before: float | None
    pressure_after: float | None
    reflect_ms: float | None
    consolidation_ms: float | None
    insert_ms: float | None
    total_ms: float | None
    reflect_input_tokens: int
    reflect_output_tokens: int
    consolidation_input_tokens: int
    consolidation_output_tokens: int
    created_at: datetime


class CompilerRunOut(BaseModel):
    """One compiler-worker run row (migration 008), full column mirror —
    every row is worker-written (C3 has no endpoint verb by ruling); a
    skipped agent (kill-switch, or no missing pairs) writes nothing."""

    run_id: UUID
    outcome: Literal["completed", "failed"]
    error: str | None
    pairs_compiled: int
    pairs_failed: int
    passthrough_keys_dropped: int
    input_tokens: int
    output_tokens: int
    total_ms: float | None
    created_at: datetime


class AgentStateResult(BaseModel):
    """GET /v1/agents/{agent_id}/state — the agent-state read (C5, ruled
    2026-08-17): the stored agent row (`config` AS STORED — SERVICE_DEFAULTS
    are never merged in; knobs resolve per call at use time, and a resolved
    snapshot would rot), the current identity version (SELECT-only, the
    newest document row — never the ensure_ upsert), the reflection-pressure
    gauge (computed on demand, never stored — architecture §2's
    runtime-state rule; same guard as the reflect verb: a non-positive norm
    raises, never clamps), the live beliefs, the derived-liveness bundles,
    and the two workers' run logs (newest first, capped by `runs_limit` — a
    caller argument, the k precedent). The FOURTH unscored-by-contract
    member: no retrieval runs, so no scores exist — IDs + structured fields;
    ZERO writes. The dormant reputation columns are deliberately absent —
    the A1 removal stays removed."""

    agent_id: UUID
    name: str | None
    seed_identity: str | None
    rigidity: float | None
    diagnosticity_goal: str | None
    config: dict
    identity_version: str | None
    identity_compiled_at: datetime | None
    reflection_pressure: float
    reflections: list[ReflectionSummaryOut] = Field(default_factory=list)
    compiled_bundles: list[CompiledBundleOut] = Field(default_factory=list)
    reflection_runs: list[ReflectionRunOut] = Field(default_factory=list)
    compiler_runs: list[CompilerRunOut] = Field(default_factory=list)
    runs_limit: int
    total_ms: float
