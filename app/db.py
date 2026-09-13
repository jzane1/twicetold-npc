"""db.py — async connection pool + hand-written SQL for the write and read paths.

psycopg v3 with AsyncConnectionPool (stack constant; no ORM, no query
builder). The observe insert is ONE transaction: memories row + `original`
memory_details head + `original` memory_fact_versions head (migration 002)
+ memory_gist_spans + any new identity_components
land together or not at all (architecture.md §5). Nothing here
ever UPDATEs stored content; the in-place writes are the runtime scalar
`set_pinned` (`memories.pinned`, write-path v1) and, since the deferred-write
build (migration 006, ruled 2026-08-12), the ONE-SHOT NULL->value completion
of a deferred row's chainless write-time scalars (importance/typology columns
+ the enrichment bookkeeping flags) in `apply_enrichment` /
`record_enrichment_failure` — the original write finishing, guarded by
`enrichment_pending`, never a mutation of a stored value — both outside the
memory-content non-destructive invariant. (`apply_reputation_delta` was a
sanctioned scalar until the A1 re-shape, 2026-08-04, removed the reputation
system; the `agents.reputation` column stays in the schema, unwritten and
unread.) DELETEs are of two kinds. The reconstruction-cache evictions in
`apply_authorial_correction`, `apply_diegetic_correction`, `apply_enrichment`,
and `apply_reflection` remove derived rows, not memory content (the standing
eviction invariant, architecture.md §7: any chain writer outside the
reconstruction path evicts). The SOLE content DELETE is the purge carve-out —
`purge_memory` (C6, ruled 2026-08-18) and its per-agent extension
`purge_agent_memories` (ruled 2026-09-01, contract 2026-09-02), both over the
ONE statement list in `_delete_memory_rows` — the one sanctioned exception
to never-DELETE: the GDPR purge verbs hard-remove a memory (or every memory
of one agent) and every row beneath it in one transaction; reflections
derived from purged memories survive as aggregate work-product (their
un-FK'd `source_memory_ids` may dangle, by design).

Two chains under one memory_id since migration 002: the telling chain
(memory_details) and the fact chain (memory_fact_versions — basis text +
embedding). Freeze ruling (2026-07-18): observe no longer writes
memories.embedding; the fact head is the sole vector home for post-002 rows,
and `memory_fact_versions.embedding IS NULL` on the live head is the
queryable embed-degradation signal (the 2026-07-13 signal, moved homes).

Read-path candidate queries (architecture.md §6) are read-only: live
memories (`memories.invalid_at IS NULL`) joined to the unique live detail
head (`memory_details.invalid_at IS NULL`; uniqueness guaranteed by the
one-live-head index) — and, for the vector probe, to the unique live fact
head, whose embedding the `<=>` distance reads (architecture.md §4.4:
retrieval follows the fix through this join). Invalidation excludes rows
here, in SQL — decay never does (the two mechanisms stay distinct).

Reconstruction (architecture.md §7) writes through
`write_back_reconstruction`: ONE transaction that supersedes the prior head
(sets invalid_at — ordinary non-destructive supersession, never an UPDATE of
content), inserts the new `reconstruction` head, and inserts the cache row —
the serve-only-persisted-text rule rides on this atomicity. The cache tables'
only writers live in the reconstruction path (the eviction invariant's
precondition); any other chain writer evicts — `apply_authorial_correction`
(architecture.md §8) supersedes the live head with the operator's text
byte-verbatim and deletes every cache row for that memory in the same
transaction. `upsert_identity_document` is insert-if-absent (versions are
content-addressed and immutable once written).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from pgvector.psycopg import register_vector_async
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.config import DB_POOL_MAX_SIZE_DEFAULT
from app.providers import NewComponent


async def _configure(conn) -> None:
    await register_vector_async(conn)


def build_pool(
    database_uri: str, *, max_size: int = DB_POOL_MAX_SIZE_DEFAULT
) -> AsyncConnectionPool:
    """Pool is opened by the caller (await pool.open()) so startup is explicit.

    `max_size` is settings.db_pool_max_size (TWICETOLD_DB_POOL_MAX_SIZE) at the
    app/runner construction sites — raise it together with the concurrency cap
    (the config.py comment pair). The keyword default keeps the walkers' bare
    build_pool(uri) calls at today's shape; min_size stays 1, not knobbed."""
    return AsyncConnectionPool(
        database_uri,
        configure=_configure,
        open=False,
        min_size=1,
        max_size=max_size,
    )


async def fetch_agent(pool: AsyncConnectionPool, agent_id: UUID) -> dict | None:
    """`rigidity` is the dissonance decision's per-NPC scalar (architecture.md
    §8; NULL resolves via dissonance_rigidity_default); `name`
    with C5 (the agent-state read echoes the stored row). Additive: every
    consumer reads this dict by key."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT agent_id, diagnosticity_goal, config, seed_identity, "
            "rigidity, name FROM agents WHERE agent_id = %s",
            (agent_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "agent_id": row[0],
        "diagnosticity_goal": row[1],
        "config": row[2] or {},
        "seed_identity": row[3],
        "rigidity": row[4],
        "name": row[5],
    }


async def insert_agent(
    pool: AsyncConnectionPool,
    *,
    name: str,
    seed_identity: str | None,
    rigidity: float | None,
    diagnosticity_goal: str | None,
    config: dict | None,
) -> UUID:
    """Provision one agent row (unity-client.md fork 2, ruled 2026-07-27).
    The UUID is minted server-side by the column default (stack constant);
    numeric knobs land NULL when unsupplied and resolve through config →
    SERVICE_DEFAULTS at read time, exactly like a hand-provisioned row.
    The reputation / reputation_sensitivity columns are deliberately absent
    from the INSERT since the A1 re-shape (2026-08-04): they stay in the
    schema (applied migrations are immutable) but are never written or
    read."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING agent_id",
            (
                name,
                seed_identity,
                rigidity,
                diagnosticity_goal,
                Jsonb(config) if config is not None else None,
            ),
        )
        row = await cur.fetchone()
    return row[0]


async def merge_agent_config(
    pool: AsyncConnectionPool, agent_id: UUID, patch: dict
) -> dict:
    """Merge `patch` into agents.config in place and return the stored
    result (E2 demo-loader ruling, 2026-08-19). agents.config is RUNTIME
    CONFIG, not memory content — like the memories.pinned toggle it sits
    outside the bi-temporal invariant, and this is the second sanctioned
    in-place write site. One transaction, row-locked, so a concurrent merge
    never loses keys. Raises LookupError on an unknown agent (the db layer
    stays below app\\ingest.py, where UnknownAgentError — a LookupError
    subclass — is defined; callers may re-wrap)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT config FROM agents WHERE agent_id = %s FOR UPDATE",
            (agent_id,),
        )
        row = await cur.fetchone()
        if row is None:
            raise LookupError(f"unknown agent_id {agent_id}")
        merged = dict(row[0] or {})
        merged.update(patch)
        await cur.execute(
            "UPDATE agents SET config = %s WHERE agent_id = %s",
            (Jsonb(merged), agent_id),
        )
    return merged


async def fetch_live_components(
    pool: AsyncConnectionPool, agent_id: UUID
) -> list[dict]:
    """The agent's live identity components (invalid_at IS NULL)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT component_id, canonical, aliases, category FROM identity_components "
            "WHERE agent_id = %s AND invalid_at IS NULL",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "component_id": r[0],
            "canonical": r[1],
            "aliases": r[2] or [],
            "category": r[3],
        }
        for r in rows
    ]


@dataclass
class SpanPlan:
    """A gist span ready for insert. component_ref is a UUID string for an
    existing component, an int index into InsertPlan.new_components for a
    component created in this same transaction, or None (category-only hit)."""

    start_char: int
    end_char: int
    component_ref: str | int | None
    matched_category: str | None


@dataclass
class InsertPlan:
    """Everything the atomic observe insert writes — all write-time facts.

    Since the deferred-write build (migration 006, ruled 2026-08-12) the
    scalar fields the write call produces are Optional: a deferred-mode
    insert stores them NULL as the pending marker (raw text is the head;
    retrieval's importance-NULL neutral fallback covers scoring) and the
    worker's one-shot completion fills them. Sync inserts still populate
    every field."""

    agent_id: UUID
    observation_text: str
    rendered_content: str  # the `original` detail head (render seam ruling)
    valid_at: datetime
    importance_raw: float | None
    scoring_failed: bool
    typology: str | None
    typology_confidence: float | None
    typology_source: str | None
    provenance: str
    pinned: bool
    decay_class: str
    decay_class_unknown: bool
    embedding: list[float] | None  # None = embedding-failure degradation
    location_name: str | None = None
    location_embedding: list[float] | None = None
    entities: list[str] | None = None
    event_time: datetime | None = None
    affect_valence: float | None = None
    affect_arousal: float | None = None
    affect_detail: dict | None = None
    new_components: list[NewComponent] = field(default_factory=list)
    spans: list[SpanPlan] = field(default_factory=list)
    escalation_failed: bool = False  # gist-escalation double-failure soft-degrade (005)
    # Deferred write processing (migration 006): pending marker + the
    # persisted non-importance trigger names (their raw material is not
    # recoverable from the DB; the worker reads them, never clears them).
    enrichment_pending: bool = False
    enrichment_pending_triggers: list[str] | None = None


@dataclass(frozen=True)
class InsertOutcome:
    memory_id: UUID
    detail_id: UUID
    fact_version_id: UUID  # the `original` fact head (migration 002)
    gist_span_ids: list[UUID]
    new_component_ids: list[UUID]


def _vector(values: list[float] | None):
    if values is None:
        return None
    from pgvector import Vector

    return Vector(values)


async def insert_observation(
    pool: AsyncConnectionPool, plan: InsertPlan
) -> InsertOutcome:
    """The atomic insert: one transaction, never a partial write."""
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                # 1. grow identity_components first so spans can reference them
                new_component_ids: list[UUID] = []
                for comp in plan.new_components:
                    await cur.execute(
                        "INSERT INTO identity_components (agent_id, canonical, aliases, "
                        "category) VALUES (%s, %s, %s, %s) RETURNING component_id",
                        (plan.agent_id, comp.canonical, comp.aliases, comp.category),
                    )
                    new_component_ids.append((await cur.fetchone())[0])

                # 2. the memories row — write-time facts. The observation
                # embedding is NOT written here (freeze ruling 2026-07-18),
                # and neither is entities (freeze ruling 2026-07-19, the same
                # precedent): both live on the `original` fact head below.
                # memories.entities is frozen — pre-003 rows keep their
                # values; post-003 rows carry NULL here forever.
                await cur.execute(
                    "INSERT INTO memories (agent_id, observation_text, "
                    "importance_raw, scoring_failed, escalation_failed, typology, "
                    "typology_confidence, "
                    "typology_source, provenance, pinned, decay_class, "
                    "decay_class_unknown, valid_at, location_name, location_embedding, "
                    "event_time, affect_valence, affect_arousal, affect_detail, "
                    "enrichment_pending, enrichment_pending_triggers) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, %s) RETURNING memory_id",
                    (
                        plan.agent_id,
                        plan.observation_text,
                        plan.importance_raw,
                        plan.scoring_failed,
                        plan.escalation_failed,
                        plan.typology,
                        plan.typology_confidence,
                        plan.typology_source,
                        plan.provenance,
                        plan.pinned,
                        plan.decay_class,
                        plan.decay_class_unknown,
                        plan.valid_at,
                        plan.location_name,
                        _vector(plan.location_embedding),
                        plan.event_time,
                        plan.affect_valence,
                        plan.affect_arousal,
                        Jsonb(plan.affect_detail)
                        if plan.affect_detail is not None
                        else None,
                        plan.enrichment_pending,
                        plan.enrichment_pending_triggers,
                    ),
                )
                memory_id = (await cur.fetchone())[0]

                # 3. the `original` detail head (write_cause = original)
                await cur.execute(
                    "INSERT INTO memory_details (memory_id, content, write_cause, valid_at) "
                    "VALUES (%s, %s, 'original', %s) RETURNING detail_id",
                    (memory_id, plan.rendered_content, plan.valid_at),
                )
                detail_id = (await cur.fetchone())[0]

                # 4. the `original` fact head (migration 002) — the semantic
                # basis retrieval ranks by: observation_text byte-verbatim +
                # the observation embedding (NULL = embed-failure degradation;
                # the queryable signal lives here since the freeze ruling) +
                # entities (migration 003, freeze ruling 2026-07-19 — the
                # gate's coverage/lexical basis, moved by corrections).
                await cur.execute(
                    "INSERT INTO memory_fact_versions (memory_id, basis_text, "
                    "embedding, entities, write_cause, valid_at) "
                    "VALUES (%s, %s, %s, %s, 'original', %s) RETURNING fact_version_id",
                    (
                        memory_id,
                        plan.observation_text,
                        _vector(plan.embedding),
                        plan.entities,
                        plan.valid_at,
                    ),
                )
                fact_version_id = (await cur.fetchone())[0]

                # 5. gist spans — offsets into the immutable observation_text
                gist_span_ids: list[UUID] = []
                for span in plan.spans:
                    if isinstance(span.component_ref, int):
                        component_id = new_component_ids[span.component_ref]
                    elif span.component_ref is not None:
                        component_id = UUID(span.component_ref)
                    else:
                        component_id = None
                    await cur.execute(
                        "INSERT INTO memory_gist_spans (memory_id, start_char, end_char, "
                        "matched_component_id, matched_category) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING span_id",
                        (
                            memory_id,
                            span.start_char,
                            span.end_char,
                            component_id,
                            span.matched_category,
                        ),
                    )
                    gist_span_ids.append((await cur.fetchone())[0])

    return InsertOutcome(
        memory_id=memory_id,
        detail_id=detail_id,
        fact_version_id=fact_version_id,
        gist_span_ids=gist_span_ids,
        new_component_ids=new_component_ids,
    )


@dataclass(frozen=True)
class CandidateRow:
    """One live memory joined to its live detail head, as retrieval reads it.
    `write_cause` (added at the reconstruction build) feeds read-mode honesty:
    a served head that is itself a reconstruction row reads as such.
    `event_time`/`location_name`/`fact_entities` (encoding-context build,
    2026-07-20) feed the context term's match components; `fact_entities` is
    the LIVE fact head's entities (migration 003 — entities follow
    correction), NULL-able on the degraded path's legacy-shaped rows.
    Field order is load-bearing: the fetchers construct positionally from
    SELECT order (…write_cause, event_time, location_name, fact_entities
    [, distance])."""

    memory_id: UUID
    detail_id: UUID
    content: str
    importance_raw: float | None
    pinned: bool
    decay_class: str | None
    valid_at: datetime
    write_cause: str
    event_time: datetime | None = None
    location_name: str | None = None
    fact_entities: list[str] | None = None
    distance: float | None = None  # cosine distance; None on the degraded path


_CANDIDATE_COLUMNS = (
    "m.memory_id, d.detail_id, d.content, m.importance_raw, m.pinned, "
    "m.decay_class, m.valid_at, d.write_cause, m.event_time, m.location_name"
)
_CANDIDATE_FROM = (
    "FROM memories m JOIN memory_details d "
    "ON d.memory_id = m.memory_id AND d.invalid_at IS NULL "
    # LEFT join (encoding-context build): fv.entities feeds the context term,
    # but a legacy-shaped row without a live fact head STAYS reachable on this
    # degraded path (the never-blank ruling outranks the join).
    "LEFT JOIN memory_fact_versions fv "
    "ON fv.memory_id = m.memory_id AND fv.invalid_at IS NULL "
    "WHERE m.agent_id = %s AND m.invalid_at IS NULL"
)
# The vector probe additionally joins the live FACT head — the embedding the
# <=> distance reads (architecture.md §4.4: retrieval follows the fix).
# `fv.invalid_at IS NULL` is stated verbatim so the planner matches the
# partial-HNSW predicate on memory_fact_versions.
#
# NAMED params (%(agent_id)s, not %s): the vector-probe queries below reference
# the 1536-dim query vector TWICE (SELECT distance + ORDER BY, the HNSW-index
# form). Positional %s sends that ~6 KB param on the wire once per placeholder;
# two large params cross a segment boundary into a ~44 ms Windows-loopback
# Nagle/delayed-ACK stall (server executes the query in ~1.3 ms). A named param
# is sent ONCE, referenced twice in SQL — measured 44 ms -> 1 ms per read, with
# the HNSW `ORDER BY embedding <=> ...` expression unchanged. So every consumer
# of this clause binds by name (all-named or all-positional, never mixed).
_VECTOR_CANDIDATE_FROM = (
    "FROM memories m JOIN memory_details d "
    "ON d.memory_id = m.memory_id AND d.invalid_at IS NULL "
    "JOIN memory_fact_versions fv "
    "ON fv.memory_id = m.memory_id AND fv.invalid_at IS NULL "
    "WHERE m.agent_id = %(agent_id)s AND m.invalid_at IS NULL"
)


async def fetch_vector_candidates(
    pool: AsyncConnectionPool, agent_id: UUID, embedding: list[float], limit: int
) -> list[CandidateRow]:
    """Over-fetched vector probe: live rows with live-fact-head embeddings,
    nearest first (partial HNSW cosine on memory_fact_versions). NULL-fact-
    embedding rows are unreachable here by design — the write path's ruled
    degradation consequence, its signal on the fact head since the freeze
    ruling; they stay reachable on the degraded path below and via the gate's
    GIN path later."""
    vec = _vector(embedding)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities, "
            f"fv.embedding <=> %(qv)s AS distance "
            f"{_VECTOR_CANDIDATE_FROM} AND fv.embedding IS NOT NULL "
            "ORDER BY fv.embedding <=> %(qv)s LIMIT %(lim)s",
            {"qv": vec, "agent_id": agent_id, "lim": limit},
        )
        rows = await cur.fetchall()
    return [CandidateRow(*row) for row in rows]


async def fetch_lexical_candidates(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    tsquery: str,
    embedding: list[float],
    limit: int,
    ts_config: str,
) -> list[CandidateRow]:
    """The hybrid lexical channel (read-path Target B, 2026-07-20): live rows
    whose live fact head's basis_text full-text-matches the prepared token-OR
    tsquery (built by retrieval.lexical_tsquery — word tokens only, so the
    to_tsquery syntax is injection-safe by construction), ranked ts_rank DESC
    with a memory_id tiebreak for a deterministic LIMIT cut. Returns the same
    CandidateRow shape as the vector probe — including the TRUE cosine
    distance (the fact head has an embedding wherever the vector probe could
    have seen it; a NULL-embedding hit carries distance NULL, the honest
    degraded-item shape) — so lexical hits flow through the shared scoring
    loop unchanged. With the service-default config the expression matches
    migration 004's partial GIN; an agent-overridden config runs the same
    predicate unindexed (correct, slower — stated behavior). All-named params
    (the vector-probe convention)."""
    from app.config import TEXT_SEARCH_CONFIG_DEFAULT

    vec = _vector(embedding)
    if ts_config == TEXT_SEARCH_CONFIG_DEFAULT:
        # Literal-baked config: textually identical to the 004 index
        # expression, so the planner matches the partial GIN.
        tsv = "to_tsvector('simple', fv.basis_text)"
        tsq = "to_tsquery('simple', %(tsq)s)"
        params: dict = {}
    else:
        tsv = "to_tsvector(%(cfg)s::regconfig, fv.basis_text)"
        tsq = "to_tsquery(%(cfg)s::regconfig, %(tsq)s)"
        params = {"cfg": ts_config}
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities, "
            f"fv.embedding <=> %(qv)s AS distance "
            f"{_VECTOR_CANDIDATE_FROM} AND {tsv} @@ {tsq} "
            f"ORDER BY ts_rank({tsv}, {tsq}) DESC, m.memory_id "
            "LIMIT %(lim)s",
            {
                **params,
                "tsq": tsquery,
                "qv": vec,
                "agent_id": agent_id,
                "lim": limit,
            },
        )
        rows = await cur.fetchall()
    return [CandidateRow(*row) for row in rows]


async def fetch_live_candidates(
    pool: AsyncConnectionPool, agent_id: UUID
) -> list[CandidateRow]:
    """Degraded-path candidates: every live memory, NULL embeddings included
    (ruled 2026-07-14: never-blank-a-dialogue). Unordered — the service ranks
    by recency x importance_norm. fv.entities rides via the LEFT join (the
    context term still applies on the degraded path — it is lexical, not
    vector); rows without a live fact head carry NULL entities and stay."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities {_CANDIDATE_FROM}",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [CandidateRow(*row) for row in rows]


@dataclass(frozen=True)
class GateRow:
    """A candidate row plus its live fact head's gate-relevant facts
    (mid-dialogue-gate.md, built 2026-07-19). `embedding` rides only on the
    loaded-set fetch (the novelty basis; NULL = the embed-degradation row,
    excluded from the basis and counted); `entities` rides on all three gate
    fetchers (the coverage basis and the entity-covered efficacy check)."""

    row: CandidateRow
    embedding: list[float] | None
    entities: list[str] | None


async def fetch_loaded_set(
    pool: AsyncConnectionPool, agent_id: UUID, memory_ids: list[UUID]
) -> list[GateRow]:
    """The gate's keyed fetch of the caller-held loaded set (fork 1,
    2026-07-19): live rows joined to their live fact heads, by ID. Unknown,
    foreign, or invalidated IDs simply don't join — the live-head predicates
    are the filter; the service counts the drop-outs. NULL fact-head
    embeddings ride (they stay in the coverage basis and closed-gate serving,
    out of the novelty basis)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities, fv.embedding "
            f"{_VECTOR_CANDIDATE_FROM} AND m.memory_id = ANY(%(ids)s)",
            {"agent_id": agent_id, "ids": memory_ids},
        )
        rows = await cur.fetchall()
    return [
        GateRow(
            row=CandidateRow(*row[:11]),
            embedding=row[11].to_list() if row[11] is not None else None,
            entities=row[10],
        )
        for row in rows
    ]


async def fetch_gate_candidates(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    embedding: list[float],
    limit: int,
    exclude_ids: list[UUID],
) -> list[GateRow]:
    """The gate's fire probe: the standard over-fetched vector probe with the
    loaded set excluded (append-only — a fetch never re-returns what the
    scene already holds) and the fact head's entities alongside (the
    entity-covered efficacy check reads them)."""
    vec = _vector(embedding)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities, "
            f"fv.embedding <=> %(qv)s AS distance "
            f"{_VECTOR_CANDIDATE_FROM} AND fv.embedding IS NOT NULL "
            "AND NOT (m.memory_id = ANY(%(exclude)s)) "
            "ORDER BY fv.embedding <=> %(qv)s LIMIT %(lim)s",
            {"qv": vec, "agent_id": agent_id, "exclude": exclude_ids, "lim": limit},
        )
        rows = await cur.fetchall()
    return [
        GateRow(row=CandidateRow(*row), embedding=None, entities=row[10])
        for row in rows
    ]


async def fetch_entity_candidates(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    terms: list[str],
    exclude_ids: list[UUID],
) -> list[GateRow]:
    """The gate ladder's entity-only rung (embeddings down): lexical fetch
    off the partial GIN over live fact heads — `fv.invalid_at IS NULL` is
    stated in the FROM verbatim so the planner matches the partial-index
    predicate (the 002 precedent). No LIMIT: the service ranks by
    recency x importance_norm in Python (the fetch_live_candidates
    precedent). The && overlap is byte-exact against stored entity strings —
    an accepted degraded-rung property (build ruling 2026-07-19)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {_CANDIDATE_COLUMNS}, fv.entities "
            f"{_VECTOR_CANDIDATE_FROM} AND fv.entities && %(terms)s::text[] "
            "AND NOT (m.memory_id = ANY(%(exclude)s))",
            {"agent_id": agent_id, "terms": terms, "exclude": exclude_ids},
        )
        rows = await cur.fetchall()
    return [
        GateRow(row=CandidateRow(*row), embedding=None, entities=row[10])
        for row in rows
    ]


async def set_pinned(pool: AsyncConnectionPool, memory_id: UUID, pinned: bool) -> bool:
    """Flip the runtime pinned flag. Returns False when the memory is unknown."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE memories SET pinned = %s WHERE memory_id = %s", (pinned, memory_id)
        )
        return cur.rowcount == 1


async def fetch_memory_chain(pool: AsyncConnectionPool, memory_id: UUID) -> dict | None:
    """The inspector read behind GET /v1/memories/{id}/chain (unity-client.md
    fork 3, ruled 2026-07-27): the memories row + BOTH version chains + the
    gist spans, read-only, superseded rows included. Chains are ordered
    (valid_at, created_at) so supersession reads top-to-bottom; the fact
    embedding never leaves the database — only its presence."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT memory_id, agent_id, observation_text, provenance, typology, "
            "decay_class, pinned, scoring_failed, escalation_failed, "
            "decay_class_unknown, created_at, valid_at, invalid_at, "
            "location_name, event_time, enrichment_pending, enrichment_attempts "
            "FROM memories WHERE memory_id = %s",
            (memory_id,),
        )
        mem = await cur.fetchone()
        if mem is None:
            return None
        await cur.execute(
            "SELECT detail_id, content, write_cause, created_at, valid_at, "
            "invalid_at FROM memory_details WHERE memory_id = %s "
            "ORDER BY valid_at, created_at",
            (memory_id,),
        )
        details = await cur.fetchall()
        await cur.execute(
            "SELECT fact_version_id, basis_text, write_cause, created_at, "
            "valid_at, invalid_at, embedding IS NOT NULL, entities "
            "FROM memory_fact_versions WHERE memory_id = %s "
            "ORDER BY valid_at, created_at",
            (memory_id,),
        )
        facts = await cur.fetchall()
        await cur.execute(
            "SELECT span_id, start_char, end_char, matched_category "
            "FROM memory_gist_spans WHERE memory_id = %s ORDER BY start_char",
            (memory_id,),
        )
        spans = await cur.fetchall()
        # Deferred-write state (migration 006): pending flag + attempts on
        # the memories row above; the per-attempt run log rides beside the
        # chains (the unscored inspector read is the run log's surface).
        await cur.execute(
            "SELECT attempt, outcome, error, triggers, escalation_failed, "
            "embedding_repaired, write_ms, escalation_ms, embed_ms, insert_ms, "
            "total_ms, write_input_tokens, write_output_tokens, "
            "escalation_input_tokens, escalation_output_tokens, "
            "embedding_tokens, created_at "
            "FROM memory_enrichment_runs WHERE memory_id = %s "
            "ORDER BY created_at, attempt",
            (memory_id,),
        )
        runs = await cur.fetchall()
        # Diegetic confrontation records (corrections, schema since 001;
        # architecture.md §8): the unscored chain read is the
        # record's inspector surface (the enrichment-run-log precedent).
        await cur.execute(
            "SELECT correction_id, detail_id, verb, source_event, "
            "created_at, valid_at FROM corrections WHERE memory_id = %s "
            "ORDER BY valid_at, created_at",
            (memory_id,),
        )
        corrections = await cur.fetchall()
    return {
        "memory_id": mem[0],
        "agent_id": mem[1],
        "observation_text": mem[2],
        "provenance": mem[3],
        "typology": mem[4],
        "decay_class": mem[5],
        "pinned": mem[6],
        "scoring_failed": mem[7],
        "escalation_failed": mem[8],
        "decay_class_unknown": mem[9],
        "created_at": mem[10],
        "valid_at": mem[11],
        "invalid_at": mem[12],
        "location_name": mem[13],
        "event_time": mem[14],
        "enrichment_pending": mem[15],
        "enrichment_attempts": mem[16],
        "enrichment_runs": [
            {
                "attempt": r[0],
                "outcome": r[1],
                "error": r[2],
                "triggers": r[3] or [],
                "escalation_failed": r[4],
                "embedding_repaired": r[5],
                "write_ms": r[6],
                "escalation_ms": r[7],
                "embed_ms": r[8],
                "insert_ms": r[9],
                "total_ms": r[10],
                "write_input_tokens": r[11],
                "write_output_tokens": r[12],
                "escalation_input_tokens": r[13],
                "escalation_output_tokens": r[14],
                "embedding_tokens": r[15],
                "created_at": r[16],
            }
            for r in runs
        ],
        "details": [
            {
                "detail_id": d[0],
                "content": d[1],
                "write_cause": d[2],
                "created_at": d[3],
                "valid_at": d[4],
                "invalid_at": d[5],
                "is_live": d[5] is None,
            }
            for d in details
        ],
        "facts": [
            {
                "fact_version_id": f[0],
                "basis_text": f[1],
                "write_cause": f[2],
                "created_at": f[3],
                "valid_at": f[4],
                "invalid_at": f[5],
                "is_live": f[5] is None,
                "has_embedding": f[6],
                "entities": f[7] or [],
            }
            for f in facts
        ],
        "gist_spans": [
            {
                "span_id": s[0],
                "start_char": s[1],
                "end_char": s[2],
                "matched_category": s[3],
            }
            for s in spans
        ],
        "corrections": [
            {
                "correction_id": c[0],
                "detail_id": c[1],
                "verb": c[2],
                "source_event": c[3],
                "created_at": c[4],
                "valid_at": c[5],
            }
            for c in corrections
        ],
    }


async def fetch_agent_memories(
    pool: AsyncConnectionPool, agent_id: UUID, limit: int
) -> tuple[int, list[dict]]:
    """The Ledger's per-agent index read: each memories row beside its live
    telling head (LEFT JOIN so a legacy-shaped row with no live head stays
    reachable — the degraded-path precedent). Newest valid_at first with the
    memory_id tiebreak (the deterministic-order precedent); returns
    (total_count, rows)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM memories WHERE agent_id = %s", (agent_id,)
        )
        total = (await cur.fetchone())[0]
        await cur.execute(
            "SELECT m.memory_id, m.observation_text, m.pinned, m.valid_at, "
            "m.invalid_at, d.content, d.write_cause, "
            "(SELECT count(*) FROM memory_details dd "
            " WHERE dd.memory_id = m.memory_id) "
            "FROM memories m "
            "LEFT JOIN memory_details d "
            "ON d.memory_id = m.memory_id AND d.invalid_at IS NULL "
            "WHERE m.agent_id = %s "
            "ORDER BY m.valid_at DESC, m.memory_id LIMIT %s",
            (agent_id, limit),
        )
        rows = await cur.fetchall()
    return total, [
        {
            "memory_id": r[0],
            "observation_text": r[1],
            "pinned": r[2],
            "valid_at": r[3],
            "invalid_at": r[4],
            "live_content": r[5],
            "live_write_cause": r[6],
            "detail_count": r[7],
        }
        for r in rows
    ]


@dataclass(frozen=True)
class DialogueAgentState:
    """The agent facts the dialogue turn consumes (architecture.md §9): seed
    identity prose for the prompt prefix and config for knob resolution."""

    agent_id: UUID
    seed_identity: str | None
    config: dict


async def fetch_dialogue_agent_state(
    pool: AsyncConnectionPool, agent_id: UUID
) -> DialogueAgentState | None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT agent_id, seed_identity, config FROM agents WHERE agent_id = %s",
            (agent_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return DialogueAgentState(
        agent_id=row[0],
        seed_identity=row[1],
        config=row[2] or {},
    )


# ---------------------------------------------------------------------------
# Reconstruction (architecture.md §7): identity documents,
# the (memory_id x composed-key) cache, retelling sources, and the write-back.
# ---------------------------------------------------------------------------


async def upsert_identity_document(
    pool: AsyncConnectionPool, agent_id: UUID, rendered_text: str, identity_version: str
) -> bool:
    """Insert-if-absent (versions are content-addressed and immutable once
    written). Returns True when this call created the row."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO identity_documents (agent_id, rendered_text, "
            "identity_version) VALUES (%s, %s, %s) "
            "ON CONFLICT (agent_id, identity_version) DO NOTHING",
            (agent_id, rendered_text, identity_version),
        )
        return cur.rowcount == 1


async def fetch_identity_document(
    pool: AsyncConnectionPool, agent_id: UUID, identity_version: str
) -> str | None:
    """rendered_text for a caller-passed version; None = unknown version
    (a loud contract error at the seam, never a silent fallback)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT rendered_text FROM identity_documents "
            "WHERE agent_id = %s AND identity_version = %s",
            (agent_id, identity_version),
        )
        row = await cur.fetchone()
    return row[0] if row is not None else None


async def fetch_current_identity_version(
    pool: AsyncConnectionPool, agent_id: UUID
) -> dict | None:
    """The agent's CURRENT identity document version — the newest row, the
    same currency rule the render follows. A pure SELECT for the agent-state
    read (C5): the read must never compile a document, so this is
    deliberately not ensure_identity_document. None = never compiled (a
    fresh agent before its first boundary/init — present-null on the
    wire)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT identity_version, created_at FROM identity_documents "
            "WHERE agent_id = %s ORDER BY created_at DESC, identity_version "
            "LIMIT 1",
            (agent_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {"identity_version": row[0], "created_at": row[1]}


async def fetch_cache_rows(
    pool: AsyncConnectionPool, pairs: list[tuple[UUID, str]]
) -> dict[tuple[UUID, str], str]:
    """Batched cache lookup: {(memory_id, composed_key): rendered_text}. The
    stored identity_version column carries the composed reconstruction key
    (identity_version + decay band — spec ruling 2026-07-17)."""
    if not pairs:
        return {}
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT c.memory_id, c.identity_version, c.rendered_text "
            "FROM reconstruction_cache c "
            "JOIN unnest(%s::uuid[], %s::text[]) AS t(memory_id, identity_version) "
            "ON c.memory_id = t.memory_id "
            "AND c.identity_version = t.identity_version",
            ([m for m, _ in pairs], [k for _, k in pairs]),
        )
        rows = await cur.fetchall()
    return {(row[0], row[1]): row[2] for row in rows}


async def fetch_cache_keys(pool: AsyncConnectionPool, memory_id: UUID) -> list[str]:
    """All composed reconstruction keys cached for one memory, read-only —
    the metrics route's band-binning source (eval-harness.md stage 1): the
    stored identity_version column carries the composed key, whose |b<N>
    tail is the decay band. Deterministic order for a stable payload."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT identity_version FROM reconstruction_cache "
            "WHERE memory_id = %s ORDER BY identity_version",
            (memory_id,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def insert_cache_row(
    pool: AsyncConnectionPool, memory_id: UUID, composed_key: str, rendered_text: str
) -> None:
    """Refusal caching (spec ruling 2026-07-17): the served prior-head text is
    cached under the current key so subsequent same-key reads are stable and
    call-free. No chain write rides with this one."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO reconstruction_cache (memory_id, identity_version, "
            "rendered_text) VALUES (%s, %s, %s) "
            "ON CONFLICT (memory_id, identity_version) DO NOTHING",
            (memory_id, composed_key, rendered_text),
        )


@dataclass(frozen=True)
class ReconstructionSource:
    """Per-memory retelling inputs: the immutable observation text, ordered
    gist span offsets, and the drift anchor's content and cause (the latest
    chain row whose write_cause is in the anchor set — derivable, no
    pointer). The cause drives the constraint: on `authorial_correction`-
    anchored chains the corrected head replaces the gist constraint
    (architecture.md §7 and §8)."""

    observation_text: str
    spans: list[tuple[int, int]]
    anchor_content: str
    anchor_cause: str


async def fetch_reconstruction_sources(
    pool: AsyncConnectionPool, memory_ids: list[UUID]
) -> dict[UUID, ReconstructionSource]:
    if not memory_ids:
        return {}
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT memory_id, observation_text FROM memories "
            "WHERE memory_id = ANY(%s)",
            (memory_ids,),
        )
        texts = {row[0]: row[1] for row in await cur.fetchall()}
        # Constraint-follows-liveness (reflection.md, ruled 2026-08-15):
        # spans whose matched component was invalidated (reflection trim)
        # drop out of the gist constraint; NULL-component spans are
        # untouched. With every component live the predicate passes for all
        # rows — byte-identical output, the no-trim parity contract.
        await cur.execute(
            "SELECT s.memory_id, s.start_char, s.end_char "
            "FROM memory_gist_spans s "
            "LEFT JOIN identity_components c "
            "ON c.component_id = s.matched_component_id "
            "WHERE s.memory_id = ANY(%s) "
            "AND (s.matched_component_id IS NULL OR c.invalid_at IS NULL) "
            "ORDER BY s.memory_id, s.start_char, s.end_char",
            (memory_ids,),
        )
        spans: dict[UUID, list[tuple[int, int]]] = {}
        for row in await cur.fetchall():
            spans.setdefault(row[0], []).append((row[1], row[2]))
        # The drift anchor: latest chain row with an anchoring write_cause
        # (original | authorial_correction | update_with_resentment |
        # enrichment — the deferred worker's canonical render re-anchors,
        # migration 006); rationalization and reconstruction rows never
        # re-anchor.
        await cur.execute(
            "SELECT DISTINCT ON (memory_id) memory_id, content, write_cause "
            "FROM memory_details WHERE memory_id = ANY(%s) "
            "AND write_cause IN "
            "('original', 'authorial_correction', 'update_with_resentment', "
            "'enrichment') "
            "ORDER BY memory_id, created_at DESC",
            (memory_ids,),
        )
        anchors = {row[0]: (row[1], row[2]) for row in await cur.fetchall()}
    return {
        memory_id: ReconstructionSource(
            observation_text=texts[memory_id],
            spans=spans.get(memory_id, []),
            anchor_content=anchors[memory_id][0],
            anchor_cause=anchors[memory_id][1],
        )
        for memory_id in texts
        if memory_id in anchors
    }


async def write_back_reconstruction(
    pool: AsyncConnectionPool,
    *,
    memory_id: UUID,
    prior_detail_id: UUID,
    content: str,
    basis: datetime,
    composed_key: str,
) -> UUID | None:
    """The retelling write-back: ONE transaction — supersede the prior head at
    the scene basis (world time; ordinary non-destructive supersession),
    insert the new `reconstruction` head (valid_at = the same basis, so the
    chain timeline is coherent under as_of time travel), and insert the cache
    row. Serve-only-persisted-text rides on this atomicity. Returns the new
    detail_id, or None when the prior head was already superseded (a
    concurrent writer won; nothing is changed)."""
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE memory_details SET invalid_at = %s "
                    "WHERE detail_id = %s AND invalid_at IS NULL",
                    (basis, prior_detail_id),
                )
                if cur.rowcount != 1:
                    return None
                await cur.execute(
                    "INSERT INTO memory_details (memory_id, content, write_cause, "
                    "valid_at) VALUES (%s, %s, 'reconstruction', %s) "
                    "RETURNING detail_id",
                    (memory_id, content, basis),
                )
                detail_id = (await cur.fetchone())[0]
                await cur.execute(
                    "INSERT INTO reconstruction_cache (memory_id, identity_version, "
                    "rendered_text) VALUES (%s, %s, %s) "
                    "ON CONFLICT (memory_id, identity_version) DO NOTHING",
                    (memory_id, composed_key, content),
                )
    return detail_id


@dataclass(frozen=True)
class CorrectionApplied:
    """Row-level outcome of `apply_authorial_correction` — both chains'
    head swaps (fact fields since the fact-level build, 2026-07-18)."""

    detail_id: UUID
    superseded_detail_id: UUID
    fact_version_id: UUID
    superseded_fact_version_id: UUID
    evicted_cache_rows: int


class _StaleHeadError(Exception):
    """Internal: aborts (rolls back) the correction transaction on a failed
    compare-and-swap; surfaced to the caller as the "stale_head" outcome."""


async def apply_authorial_correction(
    pool: AsyncConnectionPool,
    *,
    memory_id: UUID,
    content: str,
    valid_at: datetime,
    embedding: list[float],
    entities: list[str] | None = None,
    expected_detail_id: UUID | None = None,
) -> CorrectionApplied | Literal["unknown_memory", "stale_head"]:
    """The operator's replace-model correction (architecture.md §8;
    fact-following): ONE
    transaction — supersede the live telling head at the correction's world
    time, insert the corrected `authorial_correction` head (valid_at = the
    same instant; the coherent-chain-timeline precedent), supersede the live
    fact head and insert the corrected fact row (basis_text byte-verbatim +
    the pre-computed embedding — the caller embeds BEFORE this transaction;
    no network call rides inside it — + the corrected entities since
    migration 003: the NER + operator-field merge, computed by the caller,
    so corrections move entities the way they move the embedding), and evict
    every cache row for the
    memory (the standing eviction invariant). `content` is the operator's
    text byte-verbatim in both chains. With `expected_detail_id` the telling
    supersede is a compare-and-swap: a head that moved since the operator
    read it reports "stale_head" and changes nothing — the fact supersede
    needs no CAS of its own (this verb is the fact chain's only post-observe
    writer, and the telling-head CAS already serializes racing corrections).
    "unknown_memory" = no live telling head, which by the one-live-head
    construction means no such memory."""
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE memory_details SET invalid_at = %s "
                        "WHERE memory_id = %s AND invalid_at IS NULL "
                        "RETURNING detail_id",
                        (valid_at, memory_id),
                    )
                    row = await cur.fetchone()
                    if row is None:
                        return "unknown_memory"
                    superseded = row[0]
                    if (
                        expected_detail_id is not None
                        and superseded != expected_detail_id
                    ):
                        raise _StaleHeadError
                    await cur.execute(
                        "INSERT INTO memory_details (memory_id, content, "
                        "write_cause, valid_at) VALUES "
                        "(%s, %s, 'authorial_correction', %s) "
                        "RETURNING detail_id",
                        (memory_id, content, valid_at),
                    )
                    detail_id = (await cur.fetchone())[0]
                    await cur.execute(
                        "UPDATE memory_fact_versions SET invalid_at = %s "
                        "WHERE memory_id = %s AND invalid_at IS NULL "
                        "RETURNING fact_version_id",
                        (valid_at, memory_id),
                    )
                    fact_row = await cur.fetchone()
                    if fact_row is None:
                        # Post-002 invariant: every memory carries exactly one
                        # live fact head (observe mints it; the backfill
                        # guarantees pre-002 rows). Absence is a broken store,
                        # not an operator error — fail loud, roll back.
                        raise RuntimeError(
                            f"no live fact head for {memory_id}; the store "
                            "violates the one-live-fact-head invariant"
                        )
                    superseded_fact = fact_row[0]
                    await cur.execute(
                        "INSERT INTO memory_fact_versions (memory_id, "
                        "basis_text, embedding, entities, write_cause, valid_at) "
                        "VALUES (%s, %s, %s, %s, 'authorial_correction', %s) "
                        "RETURNING fact_version_id",
                        (memory_id, content, _vector(embedding), entities, valid_at),
                    )
                    fact_version_id = (await cur.fetchone())[0]
                    await cur.execute(
                        "DELETE FROM reconstruction_cache WHERE memory_id = %s",
                        (memory_id,),
                    )
                    evicted = cur.rowcount
    except _StaleHeadError:
        return "stale_head"
    return CorrectionApplied(
        detail_id=detail_id,
        superseded_detail_id=superseded,
        fact_version_id=fact_version_id,
        superseded_fact_version_id=superseded_fact,
        evicted_cache_rows=evicted,
    )


async def fetch_memory_dissonance_inputs(
    pool: AsyncConnectionPool, memory_id: UUID
) -> dict | None:
    """The dissonance decision's inputs in one read (architecture.md §8): the
    memories-row scalars (owner for the 404 ownership check; importance_raw /
    typology for the formula, NULLs legal in the deferred window; pinned rides
    the response) joined to the live telling head (the retell prompt's
    current_telling). None = no such memory or no live head — the same thing
    under the one-live-head construction."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT m.agent_id, m.importance_raw, m.typology, m.pinned, "
            "d.detail_id, d.content "
            "FROM memories m JOIN memory_details d "
            "ON d.memory_id = m.memory_id AND d.invalid_at IS NULL "
            "WHERE m.memory_id = %s",
            (memory_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return {
        "agent_id": row[0],
        "importance_raw": row[1],
        "typology": row[2],
        "pinned": row[3],
        "head_detail_id": row[4],
        "head_content": row[5],
    }


@dataclass(frozen=True)
class DiegeticCorrectionApplied:
    """Row-level outcome of `apply_diegetic_correction` — the telling-chain
    head swap plus the correction record (tellings-only by the C4 ruling:
    no fact fields exist to report)."""

    detail_id: UUID
    superseded_detail_id: UUID
    correction_id: UUID
    evicted_cache_rows: int


async def apply_diegetic_correction(
    pool: AsyncConnectionPool,
    *,
    memory_id: UUID,
    content: str,
    verb: str,
    valid_at: datetime,
    source_event: dict | None = None,
    expected_detail_id: UUID | None = None,
) -> DiegeticCorrectionApplied | Literal["unknown_memory", "stale_head"]:
    """The in-world confrontation's chain-preserving write (architecture.md §8,
    the two-verb design): ONE transaction — supersede
    the live telling head at the confrontation's world time, insert the new
    head typed by the decided verb (`rationalization` |
    `update_with_resentment`; migration 001's CHECK has admitted both since
    day one), insert the `corrections` row (the confrontation record the
    schema carried since 001 — detail_id references the new head, so its
    INSERT follows), and evict every cache row for the memory (the standing
    eviction invariant). The retell is generated by the CALLER before this
    transaction — no network call rides inside it. The fact chain is
    deliberately untouched (tellings-only, ruled 2026-08-17): the store keeps
    recording what was experienced; the confrontation changes the story. No
    drift check (event-driven writes are budget-exempt) and no pin check
    (both correction verbs outrank pin; the new head inherits it because
    memories.pinned is untouched). CAS semantics mirror the authorial verb:
    `expected_detail_id` mismatch reports "stale_head" and changes nothing;
    "unknown_memory" = no live telling head."""
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE memory_details SET invalid_at = %s "
                        "WHERE memory_id = %s AND invalid_at IS NULL "
                        "RETURNING detail_id",
                        (valid_at, memory_id),
                    )
                    row = await cur.fetchone()
                    if row is None:
                        return "unknown_memory"
                    superseded = row[0]
                    if (
                        expected_detail_id is not None
                        and superseded != expected_detail_id
                    ):
                        raise _StaleHeadError
                    await cur.execute(
                        "INSERT INTO memory_details (memory_id, content, "
                        "write_cause, valid_at) VALUES (%s, %s, %s, %s) "
                        "RETURNING detail_id",
                        (memory_id, content, verb, valid_at),
                    )
                    detail_id = (await cur.fetchone())[0]
                    await cur.execute(
                        "INSERT INTO corrections (memory_id, detail_id, verb, "
                        "source_event, valid_at) VALUES (%s, %s, %s, %s, %s) "
                        "RETURNING correction_id",
                        (
                            memory_id,
                            detail_id,
                            verb,
                            Jsonb(source_event) if source_event is not None else None,
                            valid_at,
                        ),
                    )
                    correction_id = (await cur.fetchone())[0]
                    await cur.execute(
                        "DELETE FROM reconstruction_cache WHERE memory_id = %s",
                        (memory_id,),
                    )
                    evicted = cur.rowcount
    except _StaleHeadError:
        return "stale_head"
    return DiegeticCorrectionApplied(
        detail_id=detail_id,
        superseded_detail_id=superseded,
        correction_id=correction_id,
        evicted_cache_rows=evicted,
    )


# ---------------------------------------------------------------------------
# Deferred write processing (migration 006; deferred-writes.md, ruled
# 2026-08-12). The claim/complete SQL for app\deferred.py's worker — the
# worker itself holds no SQL (repo hygiene). Concurrency contract: FOR UPDATE
# SKIP LOCKED serializes claims inside the lock window; a claimed row stays
# `enrichment_pending` while worked, so a second process CAN re-claim it
# mid-flight — the completion guard (WHERE enrichment_pending) makes the
# loser a no-op. Worst case is duplicate model spend, never duplicate rows.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrichmentClaim:
    """One claimed pending row; `attempt` is the post-increment number."""

    memory_id: UUID
    agent_id: UUID
    attempt: int


@dataclass(frozen=True)
class EnrichmentSpanRow:
    """A stored gist span, read back for the worker's add-only dedupe and
    the escalation call's candidate rebuild."""

    start_char: int
    end_char: int
    matched_component_id: UUID | None
    matched_category: str | None


@dataclass(frozen=True)
class EnrichmentSource:
    """Everything one enrichment attempt reads before its model calls."""

    observation_text: str
    valid_at: datetime
    typology: str | None
    typology_source: str | None
    typology_confidence: float | None
    pending_triggers: list[str]
    detail_id: UUID  # the live telling head
    detail_write_cause: str  # 'original' => prose supersede is eligible
    fact_version_id: UUID  # the live fact head
    fact_entities: list[str]
    fact_has_embedding: bool
    spans: list[EnrichmentSpanRow]


@dataclass(frozen=True)
class FactDelta:
    """The fact-chain supersede payload: the merged FULL entity set and, when
    the attempt repaired a NULL embedding, the new vector (None = carry the
    superseded row's embedding server-side, no vector round-trip)."""

    entities: list[str] | None
    embedding: list[float] | None


@dataclass(frozen=True)
class EnrichmentRunRecord:
    """Per-attempt instrumentation destined for memory_enrichment_runs — a
    background worker has no response payload to ride, so the seam's timing
    and token accounting persist here (instrument-at-the-seam)."""

    attempt: int
    triggers: list[str]
    escalation_failed: bool
    embedding_repaired: bool
    write_ms: float
    escalation_ms: float
    embed_ms: float
    elapsed_before_ms: float  # attempt wall time before the completion txn
    write_input_tokens: int
    write_output_tokens: int
    escalation_input_tokens: int
    escalation_output_tokens: int
    embedding_tokens: int


@dataclass(frozen=True)
class EnrichmentApplied:
    """Row-level outcome of `apply_enrichment`. Prose/fact fields are None on
    the paths that ruled them out (facts-only / no delta)."""

    detail_id: UUID | None
    superseded_detail_id: UUID | None
    fact_version_id: UUID | None
    superseded_fact_version_id: UUID | None
    gist_span_ids: list[UUID]
    new_component_ids: list[UUID]
    evicted_cache_rows: int


class _NotPendingError(Exception):
    """Internal: aborts (rolls back) the completion transaction when the
    pending guard finds the row already completed — the losing side of a
    duplicate claim, or a re-drain of finished work."""


async def _insert_run_row(
    cur,
    *,
    memory_id: UUID,
    attempt: int,
    outcome: str,
    error: str | None,
    run: EnrichmentRunRecord | None,
    insert_ms: float | None,
    total_ms: float | None,
) -> None:
    await cur.execute(
        "INSERT INTO memory_enrichment_runs (memory_id, attempt, outcome, "
        "error, triggers, escalation_failed, embedding_repaired, write_ms, "
        "escalation_ms, embed_ms, insert_ms, total_ms, write_input_tokens, "
        "write_output_tokens, escalation_input_tokens, "
        "escalation_output_tokens, embedding_tokens) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s)",
        (
            memory_id,
            attempt,
            outcome,
            error,
            (run.triggers if run else None),
            (run.escalation_failed if run else False),
            (run.embedding_repaired if run else False),
            (run.write_ms if run else None),
            (run.escalation_ms if run else None),
            (run.embed_ms if run else None),
            insert_ms,
            total_ms,
            (run.write_input_tokens if run else 0),
            (run.write_output_tokens if run else 0),
            (run.escalation_input_tokens if run else 0),
            (run.escalation_output_tokens if run else 0),
            (run.embedding_tokens if run else 0),
        ),
    )


async def claim_enrichment_batch(
    pool: AsyncConnectionPool,
    *,
    batch_size: int,
    max_attempts: int,
    exclude: list[UUID] | None = None,
) -> list[EnrichmentClaim]:
    """Claim up to batch_size pending rows, oldest first, incrementing their
    attempt counters in the same short transaction (a crash mid-work
    deliberately consumes the attempt). SKIP LOCKED keeps concurrent drains
    from double-claiming inside the lock window. Rows at or past max_attempts
    are never claimed here — `fetch_exhausted_pending` sweeps them.
    `exclude` lets one drain pass skip rows it already attempted (a failed
    row stays pending and would otherwise be re-claimed immediately,
    burning the attempt budget with zero retry spacing — the poll loop is
    the spacing)."""
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT memory_id, agent_id, enrichment_attempts "
                    "FROM memories "
                    "WHERE enrichment_pending AND enrichment_attempts < %s "
                    "AND NOT (memory_id = ANY(%s)) "
                    "ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED",
                    (max_attempts, exclude or [], batch_size),
                )
                rows = await cur.fetchall()
                if not rows:
                    return []
                await cur.execute(
                    "UPDATE memories "
                    "SET enrichment_attempts = enrichment_attempts + 1 "
                    "WHERE memory_id = ANY(%s)",
                    ([r[0] for r in rows],),
                )
    return [
        EnrichmentClaim(memory_id=r[0], agent_id=r[1], attempt=r[2] + 1) for r in rows
    ]


async def fetch_exhausted_pending(
    pool: AsyncConnectionPool, *, max_attempts: int, limit: int
) -> list[EnrichmentClaim]:
    """Orphan recovery: rows still pending with their attempt budget spent —
    a process died between claiming the final attempt and recording its
    outcome. The worker terminal-fills these WITHOUT further model calls."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT memory_id, agent_id, enrichment_attempts FROM memories "
            "WHERE enrichment_pending AND enrichment_attempts >= %s "
            "ORDER BY created_at LIMIT %s",
            (max_attempts, limit),
        )
        rows = await cur.fetchall()
    return [EnrichmentClaim(memory_id=r[0], agent_id=r[1], attempt=r[2]) for r in rows]


async def fetch_enrichment_source(
    pool: AsyncConnectionPool, memory_id: UUID
) -> EnrichmentSource | None:
    """Read-only pre-attempt snapshot: the memories scalars, the live heads
    of both chains, and the stored gist spans. Returns None when the row is
    gone or no longer pending (a concurrent drain finished it — skip
    silently)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT m.observation_text, m.valid_at, m.typology, "
            "m.typology_source, m.typology_confidence, "
            "m.enrichment_pending_triggers, m.enrichment_pending, "
            "d.detail_id, d.write_cause, "
            "f.fact_version_id, f.entities, f.embedding IS NOT NULL "
            "FROM memories m "
            "JOIN memory_details d "
            "ON d.memory_id = m.memory_id AND d.invalid_at IS NULL "
            "JOIN memory_fact_versions f "
            "ON f.memory_id = m.memory_id AND f.invalid_at IS NULL "
            "WHERE m.memory_id = %s",
            (memory_id,),
        )
        row = await cur.fetchone()
        if row is None or not row[6]:
            return None
        await cur.execute(
            "SELECT start_char, end_char, matched_component_id, "
            "matched_category FROM memory_gist_spans WHERE memory_id = %s "
            "ORDER BY start_char, end_char",
            (memory_id,),
        )
        span_rows = await cur.fetchall()
    return EnrichmentSource(
        observation_text=row[0],
        valid_at=row[1],
        typology=row[2],
        typology_source=row[3],
        typology_confidence=row[4],
        pending_triggers=row[5] or [],
        detail_id=row[7],
        detail_write_cause=row[8],
        fact_version_id=row[9],
        fact_entities=row[10] or [],
        fact_has_embedding=row[11],
        spans=[
            EnrichmentSpanRow(
                start_char=s[0],
                end_char=s[1],
                matched_component_id=s[2],
                matched_category=s[3],
            )
            for s in span_rows
        ],
    )


async def apply_enrichment(
    pool: AsyncConnectionPool,
    *,
    memory_id: UUID,
    completed_at: datetime,
    importance_raw: float,
    typology: str | None,
    typology_confidence: float | None,
    typology_source: str | None,
    escalation_failed: bool,
    rendered_content: str | None,
    raw_detail_id: UUID | None,
    fact_delta: FactDelta | None,
    new_components: list[NewComponent],
    spans: list[SpanPlan],
    run: EnrichmentRunRecord,
) -> EnrichmentApplied | Literal["not_pending"]:
    """The ONE completion transaction (all model calls happen before it):

    (a) the guarded one-shot scalar fill — COALESCE keeps any value already
        present (a declared typology is never overwritten) and the
        `WHERE enrichment_pending` guard makes a duplicate claim's loser (or
        a re-drain) a rolled-back no-op;
    (b) new identity_components from escalation novels;
    (c) the prose supersede, CAS on the captured raw `original` head — a
        rowcount of 0 (or raw_detail_id None: the head had already moved at
        fetch time) SKIPS the supersede, the ruled facts-only path;
    (d) the fact supersede, only when the caller passes a delta (entities
        grew or an embedding was repaired) — basis_text (and, un-repaired,
        the embedding) carried server-side from the superseded row;
    (e) add-only span appends (caller pre-dedupes against stored spans);
    (f) cache eviction — ALWAYS, on both the supersede and the facts-only
        path: enrichment is a chain writer, the eviction invariant binds;
    (g) the run-log row, same transaction (completion and its accounting
        land together)."""
    t_txn = time.perf_counter()
    detail_id: UUID | None = None
    superseded_detail: UUID | None = None
    fact_version_id: UUID | None = None
    superseded_fact: UUID | None = None
    gist_span_ids: list[UUID] = []
    new_component_ids: list[UUID] = []
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    # (a) the one-shot scalar fill, guarded
                    await cur.execute(
                        "UPDATE memories SET "
                        "importance_raw = COALESCE(importance_raw, %s), "
                        "typology = COALESCE(typology, %s), "
                        "typology_confidence = "
                        "COALESCE(typology_confidence, %s), "
                        "typology_source = COALESCE(typology_source, %s), "
                        "escalation_failed = escalation_failed OR %s, "
                        "enrichment_pending = false "
                        "WHERE memory_id = %s AND enrichment_pending",
                        (
                            importance_raw,
                            typology,
                            typology_confidence,
                            typology_source,
                            escalation_failed,
                            memory_id,
                        ),
                    )
                    if cur.rowcount != 1:
                        raise _NotPendingError
                    # (b) escalation-novel components
                    for comp in new_components:
                        await cur.execute(
                            "INSERT INTO identity_components (agent_id, "
                            "canonical, aliases, category) "
                            "SELECT agent_id, %s, %s, %s FROM memories "
                            "WHERE memory_id = %s RETURNING component_id",
                            (comp.canonical, comp.aliases, comp.category, memory_id),
                        )
                        new_component_ids.append((await cur.fetchone())[0])
                    # (c) prose supersede (CAS on the raw head)
                    if rendered_content is not None and raw_detail_id is not None:
                        await cur.execute(
                            "UPDATE memory_details SET invalid_at = %s "
                            "WHERE detail_id = %s AND invalid_at IS NULL",
                            (completed_at, raw_detail_id),
                        )
                        if cur.rowcount == 1:
                            superseded_detail = raw_detail_id
                            await cur.execute(
                                "INSERT INTO memory_details (memory_id, "
                                "content, write_cause, valid_at) "
                                "VALUES (%s, %s, 'enrichment', %s) "
                                "RETURNING detail_id",
                                (memory_id, rendered_content, completed_at),
                            )
                            detail_id = (await cur.fetchone())[0]
                    # (d) fact supersede, only on a real delta
                    if fact_delta is not None:
                        await cur.execute(
                            "UPDATE memory_fact_versions SET invalid_at = %s "
                            "WHERE memory_id = %s AND invalid_at IS NULL "
                            "RETURNING fact_version_id",
                            (completed_at, memory_id),
                        )
                        fact_row = await cur.fetchone()
                        if fact_row is None:
                            # One-live-fact-head invariant: absence is a
                            # broken store — fail loud, roll back (the
                            # correction precedent).
                            raise RuntimeError(
                                f"no live fact head for {memory_id}; the "
                                "store violates the one-live-fact-head "
                                "invariant"
                            )
                        superseded_fact = fact_row[0]
                        if fact_delta.embedding is not None:
                            await cur.execute(
                                "INSERT INTO memory_fact_versions (memory_id, "
                                "basis_text, embedding, entities, write_cause, "
                                "valid_at) "
                                "SELECT memory_id, basis_text, %s, %s, "
                                "'enrichment', %s FROM memory_fact_versions "
                                "WHERE fact_version_id = %s "
                                "RETURNING fact_version_id",
                                (
                                    _vector(fact_delta.embedding),
                                    fact_delta.entities,
                                    completed_at,
                                    superseded_fact,
                                ),
                            )
                        else:
                            await cur.execute(
                                "INSERT INTO memory_fact_versions (memory_id, "
                                "basis_text, embedding, entities, write_cause, "
                                "valid_at) "
                                "SELECT memory_id, basis_text, embedding, %s, "
                                "'enrichment', %s FROM memory_fact_versions "
                                "WHERE fact_version_id = %s "
                                "RETURNING fact_version_id",
                                (
                                    fact_delta.entities,
                                    completed_at,
                                    superseded_fact,
                                ),
                            )
                        fact_version_id = (await cur.fetchone())[0]
                    # (e) add-only span appends
                    for span in spans:
                        if isinstance(span.component_ref, int):
                            component_id = new_component_ids[span.component_ref]
                        elif span.component_ref is not None:
                            component_id = UUID(str(span.component_ref))
                        else:
                            component_id = None
                        await cur.execute(
                            "INSERT INTO memory_gist_spans (memory_id, "
                            "start_char, end_char, matched_component_id, "
                            "matched_category) VALUES (%s, %s, %s, %s, %s) "
                            "RETURNING span_id",
                            (
                                memory_id,
                                span.start_char,
                                span.end_char,
                                component_id,
                                span.matched_category,
                            ),
                        )
                        gist_span_ids.append((await cur.fetchone())[0])
                    # (f) cache eviction — every completion shape
                    await cur.execute(
                        "DELETE FROM reconstruction_cache WHERE memory_id = %s",
                        (memory_id,),
                    )
                    evicted = cur.rowcount
                    # (g) the run-log row
                    insert_ms = round((time.perf_counter() - t_txn) * 1000.0, 2)
                    await _insert_run_row(
                        cur,
                        memory_id=memory_id,
                        attempt=run.attempt,
                        outcome=(
                            "completed"
                            if detail_id is not None
                            else "completed_facts_only"
                        ),
                        error=None,
                        run=run,
                        insert_ms=insert_ms,
                        total_ms=round(run.elapsed_before_ms + insert_ms, 2),
                    )
    except _NotPendingError:
        return "not_pending"
    return EnrichmentApplied(
        detail_id=detail_id,
        superseded_detail_id=superseded_detail,
        fact_version_id=fact_version_id,
        superseded_fact_version_id=superseded_fact,
        gist_span_ids=gist_span_ids,
        new_component_ids=new_component_ids,
        evicted_cache_rows=evicted,
    )


async def record_enrichment_failure(
    pool: AsyncConnectionPool,
    *,
    memory_id: UUID,
    attempt: int,
    error: str,
    run: EnrichmentRunRecord | None = None,
    terminal: bool = False,
    terminal_importance: float | None = None,
    terminal_typology: str | None = None,
    terminal_typology_confidence: float | None = None,
) -> str:
    """Record a failed attempt. When `terminal`, the same transaction applies
    the guarded terminal fill — neutral importance + scoring_failed + the
    config-default typology, pending cleared — landing the row byte-equivalent
    to today's sync scoring-failed end-state (escalation_failed stays false:
    that call never ran; the run log is the honest signal). If the guard finds
    the row no longer pending (a concurrent drain completed it), the outcome
    downgrades to a plain 'failed' record. Returns the outcome written."""
    outcome = "failed"
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                if terminal:
                    await cur.execute(
                        "UPDATE memories SET "
                        "importance_raw = COALESCE(importance_raw, %s), "
                        "scoring_failed = true, "
                        "typology = COALESCE(typology, %s), "
                        "typology_confidence = "
                        "COALESCE(typology_confidence, %s), "
                        "typology_source = COALESCE(typology_source, "
                        "'inferred'), "
                        "enrichment_pending = false "
                        "WHERE memory_id = %s AND enrichment_pending",
                        (
                            terminal_importance,
                            terminal_typology,
                            terminal_typology_confidence,
                            memory_id,
                        ),
                    )
                    if cur.rowcount == 1:
                        outcome = "terminal_degraded"
                await _insert_run_row(
                    cur,
                    memory_id=memory_id,
                    attempt=attempt,
                    outcome=outcome,
                    error=error,
                    run=run,
                    insert_ms=None,
                    total_ms=(run.elapsed_before_ms if run else None),
                )
    return outcome


# ---------------------------------------------------------------------------
# Reflection (migration 007; reflection.md, the C2 rulings 2026-08-15). The
# reads/writes for app\reflection.py's seam and worker — the seam holds no
# SQL (repo hygiene). The reflections table itself is 001's, dormant until
# this build: bi-temporal rows, provenance in source_memory_ids
# (intentionally un-FK'd — purge honesty), supersession by invalid_at only.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReflectionRow:
    """One live reflection as the seam reads it: the render's ingredient
    (content, chronological order keys) and consolidation's absorb surface
    (reflection_id + the provenance union)."""

    reflection_id: UUID
    content: str
    identity_relevant: bool
    source_memory_ids: list[UUID]
    valid_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class ReflectionInsert:
    """One conclusion ready for insert (the seam's grounding validation has
    already run — every id here is a member of the sampled set)."""

    content: str
    identity_relevant: bool
    source_memory_ids: list[UUID]


@dataclass(frozen=True)
class ReflectionApplied:
    """Row-level outcome of `apply_reflection` (the step-7 transaction)."""

    reflection_ids: list[UUID]
    pruned_component_ids: list[UUID]
    evicted_cache_rows: int


class _AbsorbRaceError(Exception):
    """Internal: aborts (rolls back) the consolidation transaction when an
    absorb-set row was invalidated between the seam's fetch and this write —
    the seam degrades soft (consolidation_failed), step-7 writes stand."""


async def fetch_live_identity_reflections(
    pool: AsyncConnectionPool, agent_id: UUID
) -> list[ReflectionRow]:
    """The agent's live identity-relevant reflections in stable chronology
    (valid_at, created_at, reflection_id) — the render's order and the
    consolidation stage's absorb set. `identity_relevant IS NULL` counts as
    not identity-relevant (the write always sets it explicitly; NULL rows
    predate this build or came from elsewhere)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT reflection_id, content, identity_relevant, "
            "source_memory_ids, valid_at, created_at FROM reflections "
            "WHERE agent_id = %s AND invalid_at IS NULL AND identity_relevant "
            "ORDER BY valid_at, created_at, reflection_id",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        ReflectionRow(
            reflection_id=row[0],
            content=row[1],
            identity_relevant=row[2],
            source_memory_ids=row[3] or [],
            valid_at=row[4],
            created_at=row[5],
        )
        for row in rows
    ]


async def fetch_recent_reflections(
    pool: AsyncConnectionPool, agent_id: UUID, limit: int
) -> list[str]:
    """The RRR comparison window: the most recent live reflections' contents
    (identity-relevant or not — self-repetition is about what the agent keeps
    concluding, not where it files it), newest first, deterministic tiebreak
    (created_at DESC, reflection_id — service bookkeeping time, the ruled
    window order)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT content FROM reflections "
            "WHERE agent_id = %s AND invalid_at IS NULL "
            "ORDER BY created_at DESC, reflection_id LIMIT %s",
            (agent_id, limit),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def fetch_agent_reflections(
    pool: AsyncConnectionPool, agent_id: UUID
) -> list[dict]:
    """Every LIVE belief, both identity_relevant values, in the ruled
    compiler-window order (valid_at DESC, created_at DESC, reflection_id) —
    the agent-state read's beliefs list (C5): the first compiler_window_k
    rows are exactly the compile window, by construction. Bounded by
    mechanism (consolidation absorbs; supersession invalidates), so no
    limit. NULL identity_relevant counts as not identity-relevant (the
    fetch_live_identity_reflections rule)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT reflection_id, content, identity_relevant, "
            "source_memory_ids, valid_at, created_at FROM reflections "
            "WHERE agent_id = %s AND invalid_at IS NULL "
            "ORDER BY valid_at DESC, created_at DESC, reflection_id",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "reflection_id": row[0],
            "content": row[1],
            "identity_relevant": bool(row[2]),
            "source_memory_ids": row[3] or [],
            "valid_at": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


async def fetch_trim_candidates(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    *,
    stale_before: datetime,
    sample_memory_ids: list[UUID],
) -> list[UUID]:
    """The PURELY MECHANICAL trim rule (the C2 spec ruling 2026-08-15 — SQL
    plus the sample list, zero model input). A live component is a prune
    candidate iff ALL of:
      1. it has span evidence at all (zero-span components are authored —
         operator intent, exempt);
      2. all its evidence is stale — no LIVE memory carrying a span matched
         to it has valid_at at/after `stale_before` (the seam computes
         `now - reflection_trim_stale_seconds`; evidence living only on
         invalidated memories counts as stale);
      3. it is not active evidence — no memory in THIS call's sample
         references it.
    Deliberately NO pinned-memory clause: pin means exactly two things
    (decay exemption, reconstruction exclusion) and a trim guard would be a
    third. Deterministic order for a stable payload."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT c.component_id FROM identity_components c "
            "WHERE c.agent_id = %(agent_id)s AND c.invalid_at IS NULL "
            "AND EXISTS (SELECT 1 FROM memory_gist_spans s "
            "WHERE s.matched_component_id = c.component_id) "
            "AND NOT EXISTS (SELECT 1 FROM memory_gist_spans s "
            "JOIN memories m ON m.memory_id = s.memory_id "
            "AND m.invalid_at IS NULL "
            "WHERE s.matched_component_id = c.component_id "
            "AND m.valid_at >= %(stale_before)s) "
            "AND NOT EXISTS (SELECT 1 FROM memory_gist_spans s "
            "WHERE s.matched_component_id = c.component_id "
            "AND s.memory_id = ANY(%(sample_ids)s)) "
            "ORDER BY c.component_id",
            {
                "agent_id": agent_id,
                "stale_before": stale_before,
                "sample_ids": sample_memory_ids,
            },
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def apply_reflection(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    *,
    conclusions: list[ReflectionInsert],
    valid_at: datetime,
    prune_component_ids: list[UUID],
) -> ReflectionApplied:
    """The step-7 write transaction (reflection.md pipeline): insert the
    surviving conclusions as bi-temporal reflection rows, invalidate the
    mechanically-pruned components (CAS on invalid_at IS NULL — a component
    invalidated since the trim query simply drops out, reported honestly via
    RETURNING), and evict reconstruction_cache rows PER AFFECTED MEMORY only
    (spec ruling 3: memories having at least one gist span matched to a
    component actually pruned by this call). The cache DELETE is the
    sanctioned derived-row eviction (the correction/enrichment precedent) —
    the fourth mid-scene text-change cause lands with this build. The
    identity re-render runs AFTER this commits (build ruling 2026-08-15:
    the upsert is idempotent and self-heals at the next ensure)."""
    reflection_ids: list[UUID] = []
    pruned: list[UUID] = []
    evicted = 0
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                for conclusion in conclusions:
                    await cur.execute(
                        "INSERT INTO reflections (agent_id, content, "
                        "identity_relevant, source_memory_ids, valid_at) "
                        "VALUES (%s, %s, %s, %s, %s) RETURNING reflection_id",
                        (
                            agent_id,
                            conclusion.content,
                            conclusion.identity_relevant,
                            conclusion.source_memory_ids,
                            valid_at,
                        ),
                    )
                    reflection_ids.append((await cur.fetchone())[0])
                if prune_component_ids:
                    await cur.execute(
                        "UPDATE identity_components SET invalid_at = %s "
                        "WHERE component_id = ANY(%s) AND invalid_at IS NULL "
                        "RETURNING component_id",
                        (valid_at, prune_component_ids),
                    )
                    pruned = sorted(row[0] for row in await cur.fetchall())
                if pruned:
                    await cur.execute(
                        "DELETE FROM reconstruction_cache WHERE memory_id IN "
                        "(SELECT DISTINCT memory_id FROM memory_gist_spans "
                        "WHERE matched_component_id = ANY(%s))",
                        (pruned,),
                    )
                    evicted = cur.rowcount
    return ReflectionApplied(
        reflection_ids=reflection_ids,
        pruned_component_ids=pruned,
        evicted_cache_rows=evicted,
    )


async def apply_consolidation(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    *,
    content: str,
    source_memory_ids: list[UUID],
    absorbed_ids: list[UUID],
    valid_at: datetime,
) -> UUID | None:
    """The step-8 consolidation transaction: insert ONE identity-relevant
    reflection whose provenance is the server-computed source union, and
    absorb the summarized rows by invalid_at (bi-temporal — they stay
    queryable, never deleted). CAS on the absorb set: if any row was
    invalidated since the seam's fetch, the whole transaction rolls back and
    None returns — the seam degrades soft (consolidation_failed), the step-7
    writes stand."""
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO reflections (agent_id, content, "
                        "identity_relevant, source_memory_ids, valid_at) "
                        "VALUES (%s, %s, true, %s, %s) RETURNING reflection_id",
                        (agent_id, content, source_memory_ids, valid_at),
                    )
                    reflection_id = (await cur.fetchone())[0]
                    await cur.execute(
                        "UPDATE reflections SET invalid_at = %s "
                        "WHERE reflection_id = ANY(%s) AND invalid_at IS NULL",
                        (valid_at, absorbed_ids),
                    )
                    if cur.rowcount != len(absorbed_ids):
                        raise _AbsorbRaceError
    except _AbsorbRaceError:
        return None
    return reflection_id


async def reflection_pressure_mass(
    pool: AsyncConnectionPool, agent_id: UUID, *, neutral: float
) -> float:
    """The pressure gauge's numerator (reflection.md): summed
    COALESCE(importance_raw, neutral) over the agent's live memories created
    AFTER the most recent reflection row's created_at — any reflection row,
    live or absorbed: the last reflect EVENT; all live memories when none
    exists. `created_at`, not valid_at: pressure is service bookkeeping
    (unprocessed accumulation), not world time. Computed on demand, never
    stored (architecture §2's runtime-state rule); the seam divides by
    reflection_pressure_norm."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COALESCE(SUM(COALESCE(m.importance_raw, %(neutral)s)), 0.0) "
            "FROM memories m "
            "WHERE m.agent_id = %(agent_id)s AND m.invalid_at IS NULL "
            "AND m.created_at > COALESCE((SELECT max(r.created_at) "
            "FROM reflections r WHERE r.agent_id = %(agent_id)s), "
            "'-infinity'::timestamptz)",
            {"agent_id": agent_id, "neutral": neutral},
        )
        row = await cur.fetchone()
    return float(row[0])


async def fetch_agent_configs(
    pool: AsyncConnectionPool,
) -> list[tuple[UUID, dict]]:
    """Every agent's (agent_id, config) in deterministic order — the
    ReflectionWorker's sweep scan (build ruling 2026-08-15: the knob filter
    and pressure check run in Python; agents is small, and the fixed order
    makes sweep() walker-assertable)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT agent_id, config FROM agents ORDER BY agent_id")
        rows = await cur.fetchall()
    return [(row[0], row[1] or {}) for row in rows]


@dataclass(frozen=True)
class ReflectionRunRecord:
    """Per-run instrumentation destined for reflection_runs — the WORKER's
    persisted accounting (endpoint reflects ride the response payload and
    write no row; the C1 endpoint/worker split). Fields mirror migration
    007's columns; nullable numbers stay None on runs that died before the
    stage produced them."""

    agent_id: UUID
    outcome: str  # 'completed' | 'failed'
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


async def insert_reflection_run(
    pool: AsyncConnectionPool, run: ReflectionRunRecord
) -> None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO reflection_runs (agent_id, outcome, error, "
            "reflections_written, dropped_ungrounded, consolidation_ran, "
            "consolidation_failed, rrr, rrr_blocked, pruned_components, "
            "evicted_cache_rows, pressure_before, pressure_after, reflect_ms, "
            "consolidation_ms, insert_ms, total_ms, reflect_input_tokens, "
            "reflect_output_tokens, consolidation_input_tokens, "
            "consolidation_output_tokens) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run.agent_id,
                run.outcome,
                run.error,
                run.reflections_written,
                run.dropped_ungrounded,
                run.consolidation_ran,
                run.consolidation_failed,
                run.rrr,
                run.rrr_blocked,
                run.pruned_components,
                run.evicted_cache_rows,
                run.pressure_before,
                run.pressure_after,
                run.reflect_ms,
                run.consolidation_ms,
                run.insert_ms,
                run.total_ms,
                run.reflect_input_tokens,
                run.reflect_output_tokens,
                run.consolidation_input_tokens,
                run.consolidation_output_tokens,
            ),
        )


async def fetch_reflection_runs(
    pool: AsyncConnectionPool, agent_id: UUID
) -> list[dict]:
    """An agent's run rows, oldest first — the walker/test surface for the
    worker's accounting. The C5 agent-state read rides its own newest-first,
    limited, full-column fetcher (fetch_recent_reflection_runs below); this
    one stays the walkers' chronological surface."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT run_id, outcome, error, reflections_written, "
            "dropped_ungrounded, consolidation_ran, consolidation_failed, "
            "rrr, rrr_blocked, pruned_components, evicted_cache_rows, "
            "pressure_before, pressure_after, created_at "
            "FROM reflection_runs WHERE agent_id = %s ORDER BY created_at, run_id",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "run_id": row[0],
            "outcome": row[1],
            "error": row[2],
            "reflections_written": row[3],
            "dropped_ungrounded": row[4],
            "consolidation_ran": row[5],
            "consolidation_failed": row[6],
            "rrr": row[7],
            "rrr_blocked": row[8],
            "pruned_components": row[9],
            "evicted_cache_rows": row[10],
            "pressure_before": row[11],
            "pressure_after": row[12],
            "created_at": row[13],
        }
        for row in rows
    ]


async def fetch_recent_reflection_runs(
    pool: AsyncConnectionPool, agent_id: UUID, *, limit: int
) -> list[dict]:
    """The agent-state read's reflection-run log (C5): ALL migration-007
    columns, newest first, capped by the route's runs_limit (a caller
    argument, the k precedent) — the table is append-only, so the product
    read is bounded where the walker surface above walks full history."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT run_id, outcome, error, reflections_written, "
            "dropped_ungrounded, consolidation_ran, consolidation_failed, "
            "rrr, rrr_blocked, pruned_components, evicted_cache_rows, "
            "pressure_before, pressure_after, reflect_ms, consolidation_ms, "
            "insert_ms, total_ms, reflect_input_tokens, "
            "reflect_output_tokens, consolidation_input_tokens, "
            "consolidation_output_tokens, created_at "
            "FROM reflection_runs WHERE agent_id = %s "
            "ORDER BY created_at DESC, run_id LIMIT %s",
            (agent_id, limit),
        )
        rows = await cur.fetchall()
    return [
        {
            "run_id": row[0],
            "outcome": row[1],
            "error": row[2],
            "reflections_written": row[3],
            "dropped_ungrounded": row[4],
            "consolidation_ran": row[5],
            "consolidation_failed": row[6],
            "rrr": row[7],
            "rrr_blocked": row[8],
            "pruned_components": row[9],
            "evicted_cache_rows": row[10],
            "pressure_before": row[11],
            "pressure_after": row[12],
            "reflect_ms": row[13],
            "consolidation_ms": row[14],
            "insert_ms": row[15],
            "total_ms": row[16],
            "reflect_input_tokens": row[17],
            "reflect_output_tokens": row[18],
            "consolidation_input_tokens": row[19],
            "consolidation_output_tokens": row[20],
            "created_at": row[21],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Parameter compiler (migration 008; parameter-compiler.md, the C3 rulings
# 2026-08-17). The reads/writes for app\compiler.py's service and worker —
# the seam holds no SQL (repo hygiene). compiled_bundles is APPEND-ONLY and
# its liveness is DERIVED: a bundle applies only while its source reflection
# is live, so belief supersession/consolidation evicts compiled parameters
# with zero writes here (the §10 eviction contract — bi-temporal reflection
# invalidation doubles as compiler-cache eviction).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompilePair:
    """One unit of compiler work: a live in-window belief that has no bundle
    yet for one scene type (the compilable surface rides along so the seam
    never re-fetches)."""

    reflection_id: UUID
    content: str
    identity_relevant: bool
    scene_type: str


async def fetch_missing_bundle_pairs(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    *,
    scene_types: list[str],
    window_k: int,
) -> list[CompilePair]:
    """Work discovery — stateless, like the reflection pressure gauge: the K
    most recent live beliefs (valid_at DESC, created_at DESC, reflection_id —
    the ruled window order) crossed with the compile vocabulary, minus pairs
    that already hold at least one bundle. Deterministic output order (newest
    belief first, then scene_type) so the sweep's budget cuts a stable
    prefix."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "WITH window_beliefs AS ("
            "SELECT reflection_id, content, identity_relevant, valid_at, "
            "created_at FROM reflections "
            "WHERE agent_id = %(agent_id)s AND invalid_at IS NULL "
            "ORDER BY valid_at DESC, created_at DESC, reflection_id "
            "LIMIT %(window_k)s) "
            "SELECT w.reflection_id, w.content, w.identity_relevant, "
            "t.scene_type FROM window_beliefs w "
            "CROSS JOIN unnest(%(scene_types)s::text[]) AS t(scene_type) "
            "WHERE NOT EXISTS (SELECT 1 FROM compiled_bundles b "
            "WHERE b.reflection_id = w.reflection_id "
            "AND b.scene_type = t.scene_type) "
            "ORDER BY w.valid_at DESC, w.created_at DESC, w.reflection_id, "
            "t.scene_type",
            {
                "agent_id": agent_id,
                "scene_types": scene_types,
                "window_k": window_k,
            },
        )
        rows = await cur.fetchall()
    return [
        CompilePair(
            reflection_id=row[0],
            content=row[1],
            identity_relevant=bool(row[2]),
            scene_type=row[3],
        )
        for row in rows
    ]


@dataclass(frozen=True)
class CompiledBundleInsert:
    """One compile call's validated result (the seam has already clamped the
    multipliers to the module constants and namespace-filtered the
    passthrough — the CHECK is defense, not the validator)."""

    reflection_id: UUID
    scene_type: str
    w_relevance: float
    w_recency: float
    w_importance: float
    passthrough: dict
    input_tokens: int
    output_tokens: int
    compile_ms: float | None


async def insert_compiled_bundle(
    pool: AsyncConnectionPool, agent_id: UUID, insert: CompiledBundleInsert
) -> UUID:
    """Append-only: a re-compile of the same (reflection, scene_type) appends
    a newer row and the consume read picks it by created_at (bundle_id breaks
    the tie — same-transaction rows share one created_at)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO compiled_bundles (agent_id, reflection_id, "
            "scene_type, w_relevance, w_recency, w_importance, passthrough, "
            "input_tokens, output_tokens, compile_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING bundle_id",
            (
                agent_id,
                insert.reflection_id,
                insert.scene_type,
                insert.w_relevance,
                insert.w_recency,
                insert.w_importance,
                Jsonb(insert.passthrough),
                insert.input_tokens,
                insert.output_tokens,
                insert.compile_ms,
            ),
        )
        return (await cur.fetchone())[0]


@dataclass(frozen=True)
class DialogueBundleRow:
    """One contributing bundle as the dialogue seam consumes it."""

    reflection_id: UUID
    w_relevance: float
    w_recency: float
    w_importance: float


async def fetch_dialogue_bundles(
    pool: AsyncConnectionPool,
    agent_id: UUID,
    *,
    scene_type: str,
    window_k: int,
) -> list[DialogueBundleRow]:
    """The consume read: for each of the K most recent live beliefs (the same
    window order as discovery — the staleness guard binds both ends), the
    newest bundle for exactly the resolved scene type. A KNOWN type whose
    pair is not yet compiled contributes nothing — no cross-type fallback;
    the compile-lag window degrades toward neutral, never leaks another
    type's parameters. Outer order = belief recency, so the instrumentation
    list is stable."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "WITH window_beliefs AS ("
            "SELECT reflection_id, valid_at, created_at FROM reflections "
            "WHERE agent_id = %(agent_id)s AND invalid_at IS NULL "
            "ORDER BY valid_at DESC, created_at DESC, reflection_id "
            "LIMIT %(window_k)s) "
            "SELECT latest.reflection_id, latest.w_relevance, "
            "latest.w_recency, latest.w_importance FROM ("
            "SELECT DISTINCT ON (w.reflection_id) w.reflection_id, "
            "b.w_relevance, b.w_recency, b.w_importance, w.valid_at, "
            "w.created_at FROM window_beliefs w "
            "JOIN compiled_bundles b ON b.reflection_id = w.reflection_id "
            "AND b.scene_type = %(scene_type)s "
            "ORDER BY w.reflection_id, b.created_at DESC, b.bundle_id"
            ") latest "
            "ORDER BY latest.valid_at DESC, latest.created_at DESC, "
            "latest.reflection_id",
            {
                "agent_id": agent_id,
                "scene_type": scene_type,
                "window_k": window_k,
            },
        )
        rows = await cur.fetchall()
    return [
        DialogueBundleRow(
            reflection_id=row[0],
            w_relevance=float(row[1]),
            w_recency=float(row[2]),
            w_importance=float(row[3]),
        )
        for row in rows
    ]


async def fetch_agent_bundles(pool: AsyncConnectionPool, agent_id: UUID) -> list[dict]:
    """The newest live bundle per (reflection, scene_type) pair, passthrough
    included verbatim — the agent-state read's compiler surface (C5, the
    recorded future-integrator read; parameter-compiler.md). Liveness is
    DERIVED from the source reflection (the §10 contract). Unlike the
    consume read above this is un-windowed and cross-type: the snapshot
    shows every parameter in force, not one scene's slice. Outer order =
    the belief window order then scene_type — deterministic, consistent
    with the beliefs list. Bounded by mechanism (one row per live pair)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT latest.bundle_id, latest.reflection_id, "
            "latest.scene_type, latest.w_relevance, latest.w_recency, "
            "latest.w_importance, latest.passthrough, latest.input_tokens, "
            "latest.output_tokens, latest.compile_ms, latest.created_at "
            "FROM ("
            "SELECT DISTINCT ON (b.reflection_id, b.scene_type) b.bundle_id, "
            "b.reflection_id, b.scene_type, b.w_relevance, b.w_recency, "
            "b.w_importance, b.passthrough, b.input_tokens, b.output_tokens, "
            "b.compile_ms, b.created_at, r.valid_at AS r_valid_at, "
            "r.created_at AS r_created_at FROM compiled_bundles b "
            "JOIN reflections r ON r.reflection_id = b.reflection_id "
            "AND r.invalid_at IS NULL "
            "WHERE b.agent_id = %s "
            "ORDER BY b.reflection_id, b.scene_type, b.created_at DESC, "
            "b.bundle_id) latest "
            "ORDER BY latest.r_valid_at DESC, latest.r_created_at DESC, "
            "latest.reflection_id, latest.scene_type",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "bundle_id": row[0],
            "reflection_id": row[1],
            "scene_type": row[2],
            "w_relevance": float(row[3]),
            "w_recency": float(row[4]),
            "w_importance": float(row[5]),
            "passthrough": row[6] or {},
            "input_tokens": row[7],
            "output_tokens": row[8],
            "compile_ms": row[9],
            "created_at": row[10],
        }
        for row in rows
    ]


@dataclass(frozen=True)
class CompilerRunRecord:
    """Per-agent-per-sweep instrumentation destined for compiler_runs — the
    WORKER's persisted accounting (C3 has no endpoint verb by ruling, so
    every row is worker-written; a skipped agent writes nothing)."""

    agent_id: UUID
    outcome: str  # 'completed' | 'failed'
    error: str | None
    pairs_compiled: int
    pairs_failed: int
    passthrough_keys_dropped: int
    input_tokens: int
    output_tokens: int
    total_ms: float | None


async def insert_compiler_run(
    pool: AsyncConnectionPool, run: CompilerRunRecord
) -> None:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO compiler_runs (agent_id, outcome, error, "
            "pairs_compiled, pairs_failed, passthrough_keys_dropped, "
            "input_tokens, output_tokens, total_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run.agent_id,
                run.outcome,
                run.error,
                run.pairs_compiled,
                run.pairs_failed,
                run.passthrough_keys_dropped,
                run.input_tokens,
                run.output_tokens,
                run.total_ms,
            ),
        )


async def fetch_compiler_runs(pool: AsyncConnectionPool, agent_id: UUID) -> list[dict]:
    """An agent's run rows, oldest first — the walker/test surface for the
    worker's accounting. The C5 agent-state read rides its own newest-first,
    limited fetcher (fetch_recent_compiler_runs below); this one stays the
    walkers' chronological surface (the fetch_reflection_runs precedent)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT run_id, outcome, error, pairs_compiled, pairs_failed, "
            "passthrough_keys_dropped, input_tokens, output_tokens, "
            "total_ms, created_at "
            "FROM compiler_runs WHERE agent_id = %s ORDER BY created_at, run_id",
            (agent_id,),
        )
        rows = await cur.fetchall()
    return [
        {
            "run_id": row[0],
            "outcome": row[1],
            "error": row[2],
            "pairs_compiled": row[3],
            "pairs_failed": row[4],
            "passthrough_keys_dropped": row[5],
            "input_tokens": row[6],
            "output_tokens": row[7],
            "total_ms": row[8],
            "created_at": row[9],
        }
        for row in rows
    ]


async def fetch_recent_compiler_runs(
    pool: AsyncConnectionPool, agent_id: UUID, *, limit: int
) -> list[dict]:
    """The agent-state read's compiler-run log (C5): all migration-008
    columns, newest first, capped by the route's runs_limit — the
    fetch_recent_reflection_runs shape on the other append-only table."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT run_id, outcome, error, pairs_compiled, pairs_failed, "
            "passthrough_keys_dropped, input_tokens, output_tokens, "
            "total_ms, created_at "
            "FROM compiler_runs WHERE agent_id = %s "
            "ORDER BY created_at DESC, run_id LIMIT %s",
            (agent_id, limit),
        )
        rows = await cur.fetchall()
    return [
        {
            "run_id": row[0],
            "outcome": row[1],
            "error": row[2],
            "pairs_compiled": row[3],
            "pairs_failed": row[4],
            "passthrough_keys_dropped": row[5],
            "input_tokens": row[6],
            "output_tokens": row[7],
            "total_ms": row[8],
            "created_at": row[9],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Purge (per-memory scope, the DELETE verb, no guard, no migration). The
# release-blocker GDPR verb and the SOLE sanctioned content DELETE (the
# non-destructive invariant, architecture.md §2; this module's header). One
# memory and every row beneath it — both chains (memory_details +
# memory_fact_versions), gist spans, corrections, caches, enrichment runs —
# deleted child-before-parent in ONE transaction. No FK cascades (every
# reference is bare NO ACTION), so the order is explicit and forced: corrections
# reference memory_details AND memories, so they clear first; the six
# memory-child tables clear before the memories row. Reflections derived from
# the memory SURVIVE as aggregate work-product (their un-FK'd source_memory_ids
# may dangle — purge honesty, migration-01.md:132); the agent, its identity,
# reflections, and compiled bundles are untouched. Purge does NOT reach
# reflections (the parameter-compiler.md C6 note, closed 2026-08-18) — under
# either verb: the per-memory C6 verb, or the per-agent bulk verb added by the
# provider-path session (ruled 2026-09-01 as a thin extension of this
# carve-out; its contract ruled 2026-09-02), which runs the SAME statement
# list over every memory of one agent.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PurgeOutcome:
    """The per-table row counts one purge removed — the walker/tests assert on
    these and the endpoint echoes them. Returned only for a memory that
    existed; an unknown id yields None (a 404), never a zero-count outcome."""

    memory_id: UUID
    corrections_deleted: int
    cache_rows_evicted: int
    fact_versions_deleted: int
    enrichment_runs_deleted: int
    gist_spans_deleted: int
    details_deleted: int


@dataclass(frozen=True)
class _PurgeCounts:
    """Per-table rowcounts of one child-before-parent delete over a set of
    memory ids — the shared statement list behind both purge verbs."""

    corrections: int
    cache: int
    facts: int
    enrichment: int
    spans: int
    details: int
    memories: int


async def _delete_memory_rows(cur, memory_ids: list[UUID]) -> _PurgeCounts:
    """The seven child-before-parent DELETEs, set-scoped (`= ANY(%s)`), in
    the order the schema's bare (NO ACTION) foreign keys force: corrections
    (references memory_details AND memories) -> reconstruction_cache ->
    memory_fact_versions -> memory_enrichment_runs -> memory_gist_spans ->
    memory_details -> memories. ONE delete order in one place, reached by
    both purge verbs (the per-memory verb passes a single id); an empty set
    short-circuits to zeros without touching the database. Runs inside the
    caller's transaction, after the caller's locks."""
    if not memory_ids:
        return _PurgeCounts(0, 0, 0, 0, 0, 0, 0)
    ids = list(memory_ids)
    await cur.execute("DELETE FROM corrections WHERE memory_id = ANY(%s)", (ids,))
    corrections = cur.rowcount
    await cur.execute(
        "DELETE FROM reconstruction_cache WHERE memory_id = ANY(%s)", (ids,)
    )
    cache = cur.rowcount
    await cur.execute(
        "DELETE FROM memory_fact_versions WHERE memory_id = ANY(%s)", (ids,)
    )
    facts = cur.rowcount
    await cur.execute(
        "DELETE FROM memory_enrichment_runs WHERE memory_id = ANY(%s)", (ids,)
    )
    enrichment = cur.rowcount
    await cur.execute("DELETE FROM memory_gist_spans WHERE memory_id = ANY(%s)", (ids,))
    spans = cur.rowcount
    await cur.execute("DELETE FROM memory_details WHERE memory_id = ANY(%s)", (ids,))
    details = cur.rowcount
    await cur.execute("DELETE FROM memories WHERE memory_id = ANY(%s)", (ids,))
    memories = cur.rowcount
    return _PurgeCounts(
        corrections=corrections,
        cache=cache,
        facts=facts,
        enrichment=enrichment,
        spans=spans,
        details=details,
        memories=memories,
    )


async def purge_memory(
    pool: AsyncConnectionPool, memory_id: UUID
) -> PurgeOutcome | None:
    """Hard-delete one memory and everything beneath it in one transaction.
    Returns None when the memory is unknown (→ 404) — nothing is deleted.

    A SELECT ... FOR UPDATE opens the transaction: it is the clean unknown-id
    check before any DELETE runs, and it locks the target so a concurrent
    correction / enrichment / reconstruction on the same memory cannot
    interleave with the delete. The seven child-before-parent statements
    live in `_delete_memory_rows` (shared with the per-agent verb since the
    provider-path session, 2026-09-02) — the order the schema's bare
    (NO ACTION) foreign keys force."""
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM memories WHERE memory_id = %s FOR UPDATE",
                    (memory_id,),
                )
                if await cur.fetchone() is None:
                    return None
                counts = await _delete_memory_rows(cur, [memory_id])
    return PurgeOutcome(
        memory_id=memory_id,
        corrections_deleted=counts.corrections,
        cache_rows_evicted=counts.cache,
        fact_versions_deleted=counts.facts,
        enrichment_runs_deleted=counts.enrichment,
        gist_spans_deleted=counts.spans,
        details_deleted=counts.details,
    )


@dataclass(frozen=True)
class AgentPurgeOutcome:
    """The per-agent purge's counts: how many memories went and the SUMMED
    per-table child counts (the PurgeOutcome field names). Returned for any
    KNOWN agent — zero memories is a legal all-zero outcome (a 200), never
    None; an unknown agent yields None (a 404)."""

    agent_id: UUID
    memories_deleted: int
    corrections_deleted: int
    cache_rows_evicted: int
    fact_versions_deleted: int
    enrichment_runs_deleted: int
    gist_spans_deleted: int
    details_deleted: int


async def purge_agent_memories(
    pool: AsyncConnectionPool, agent_id: UUID
) -> AgentPurgeOutcome | None:
    """Hard-delete every memory of one agent and everything beneath each, in
    one transaction — the per-agent purge verb (ruled 2026-09-01 as the thin
    extension of the C6 carve-out; its contract ruled 2026-09-02). Returns
    None when the agent is unknown (→ 404), nothing deleted; a known agent
    with no memories returns an all-zero outcome (→ 200).

    Locks, in this order: the agents row FOR NO KEY UPDATE — the existence
    check, which also serializes concurrent agent purges and
    merge_agent_config WITHOUT conflicting with the FK KEY SHARE every
    agent-scoped writer takes (a plain FOR UPDATE would add a deadlock class
    against apply_enrichment's novel-component path: memories row held ->
    wants agents); then the agent's memory rows FOR UPDATE (the C6 rationale:
    no concurrent correction / enrichment / reconstruction interleaves with
    the delete). Consequences stated honestly: an observe already in flight
    (its KEY SHARE taken, uncommitted) is invisible to the collect and
    survives — indistinguishable from one arriving a millisecond after
    commit, so the integrator stops feeding an agent before purging it; the
    C6-era inversion against the details-first writers (they lock a
    memory_details row, then need the memories row) is inherited — Postgres
    detects the cycle and aborts one side, the purge rolling back clean with
    nothing deleted; the deferred worker's SKIP LOCKED claim skips rows this
    transaction holds, and a row it claimed earlier and completes later finds
    enrichment_pending gone and lands its not_pending no-op.

    Survival boundary (the C6 stance): the agents row, identity_components,
    identity_documents, reflections (every source_memory_ids entry may now
    dangle — purge honesty), reflection_runs, compiled_bundles, and
    compiler_runs are untouched."""
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM agents WHERE agent_id = %s FOR NO KEY UPDATE",
                    (agent_id,),
                )
                if await cur.fetchone() is None:
                    return None
                await cur.execute(
                    "SELECT memory_id FROM memories WHERE agent_id = %s "
                    "ORDER BY memory_id FOR UPDATE",
                    (agent_id,),
                )
                memory_ids = [row[0] for row in await cur.fetchall()]
                counts = await _delete_memory_rows(cur, memory_ids)
    return AgentPurgeOutcome(
        agent_id=agent_id,
        memories_deleted=counts.memories,
        corrections_deleted=counts.corrections,
        cache_rows_evicted=counts.cache,
        fact_versions_deleted=counts.facts,
        enrichment_runs_deleted=counts.enrichment,
        gist_spans_deleted=counts.spans,
        details_deleted=counts.details,
    )
