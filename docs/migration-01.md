# Migration 001: foundational schema

The foundational schema: hand-written SQL against PostgreSQL 16 with pgvector (the
`pgvector/pgvector` Docker image), with UUIDs minted server-side. Migrations 002 through 008 live in
`db\migrations\` and are not restated here; where a later migration changed a column defined below, a
note records the current state. Design truth is [architecture.md](architecture.md) §4.

## Principles this migration honors

- **Bi-temporal everywhere it applies:** `created_at` (server write time), `valid_at` (world time,
  from the client timestamp, timezone-aware, NOT NULL), and `invalid_at` (NULL until superseded).
- **Non-destructive:** supersession sets `invalid_at`, never an UPDATE-in-place of content and never a
  DELETE. The purge carve-out (per-memory and per-agent) is the sole explicit exception and is not part
  of this migration.
- **All write-time fact columns exist now**, even where the consuming mechanism is deferred: typology,
  confidence, and typology_source; provenance; context components; decay class; gist spans; importance;
  pin; and scoring_failed.

## Tables

### agents

One row per NPC.

- `agent_id` UUID PK, server default.
- `name` text.
- `seed_identity` text: the seed prose. It stays immutable; reflection joins the rendered identity
  document instead ([reflection.md](reflection.md)).
- `reputation` numeric: a runtime scalar starting at the scale's neutral point (unwritten and unread in
  the current design; a dialogue turn persists nothing).
- `rigidity` numeric, CHECK between 0.5 and 2.0: the dissonance scalar (pushover to zealot).
- `reputation_sensitivity` numeric.
- `diagnosticity_goal` text: the anchor for importance scoring; the importance prompt consumes prose.
- `config` jsonb: the remaining integrator knobs (decay constants, drift threshold, reconstruction
  theta, and so on) until any of them earns a typed column.

### memories

One row per observation. `observation_text` is immutable after insert.

- `memory_id` UUID PK, server default.
- `agent_id` FK to agents.
- `observation_text` text NOT NULL.
- `embedding` vector(1536): the dimension is locked. The retrieval probe moved to the live fact-version
  head with migration 002, so observe no longer writes this column; it stays as written for pre-002 rows
  (their values were backfilled into the fact chain), and the queryable embed-degradation signal now
  lives on the live fact head (architecture.md §4.4).
- `importance_raw` real: stored raw, normalized at read.
- `scoring_failed` boolean NOT NULL default false: set true when the importance-scoring model fails, so
  the write still lands with neutral importance (a write is never lost). See architecture.md §2.
  (Migration 005 added the sibling `escalation_failed` boolean NOT NULL default false, the
  gist-escalation soft-degrade flag; architecture.md §5.)
- `typology` text CHECK in (`observed`, `told`, `inferred`, `reflected`).
- `typology_confidence` real CHECK 0 to 1.
- `typology_source` text CHECK in (`declared`, `inferred`).
- `provenance` text CHECK in (`lived`, `injected`).
- `pinned` boolean NOT NULL default false.
- `decay_class` text: an integrator vocabulary label selecting the base decay constant. The label-to-
  `tau_base` map lives in `agents.config`.
- `decay_class_unknown` boolean NOT NULL default false: a write-time degradation flag (mirroring
  `scoring_failed`), so an unrecognized decay-class label lands with a default class and this flag set,
  never rejected.
- `created_at`, `valid_at`, `invalid_at` per the bi-temporal rules above.
- Context stamps (all four nullable, optional API fields):
  - `location_embedding` vector(1536) and `location_name` text.
  - `entities` text[], with a GIN index. The entities home and GIN moved to the live fact heads with
    migration 003, so this column is frozen post-003 ([mid-dialogue-gate.md](mid-dialogue-gate.md)).
  - `event_time` timestamptz.
  - `affect_valence` real, `affect_arousal` real, `affect_detail` jsonb (all nullable), from the
    VADER-class write pass.

### memory_gist_spans

Gist as span pointers into `observation_text`, never rewritten text. A child table so spans are
individually assertable rows (the suite asserts gist rows are immutable).

- `span_id` UUID PK, server default.
- `memory_id` FK to memories.
- `start_char` int, `end_char` int (half-open, into `observation_text`).
- `matched_component_id` FK to identity_components, nullable.
- `matched_category` text, nullable, for category hits without a named entity.
- `created_at`.

### memory_details

The version chain under a stable `memory_id`. The head is the row with `invalid_at IS NULL`.

- `detail_id` UUID PK, server default.
- `memory_id` FK to memories.
- `content` text NOT NULL.
- `write_cause` text CHECK in (`original`, `reconstruction`, `rationalization`, `update_with_resentment`,
  `authorial_correction`). Migration 006 widened the CHECK with a sixth value, `enrichment`, the
  deferred-write completion ([deferred-writes.md](deferred-writes.md)).
- `created_at`, `valid_at`, `invalid_at`.
- Partial unique index, at most one live head per memory: `UNIQUE (memory_id) WHERE invalid_at IS NULL`
  (compatible with the authorial replace model: an authorial correction supersedes to a single corrected
  live head).
- Verb discrimination lives on the new head's `write_cause`; prior-row invalidation is ordinary
  supersession, with no voided-marker column.

### corrections

The diegetic correction record: one row per in-world confrontation that superseded a chain head. The
dissonance mechanism that writes these is described in architecture.md §8; the diegetic half of the Set A
test pair ([test-suite.md](test-suite.md)) asserts a correction record is present.

- `correction_id` UUID PK, server default.
- `memory_id` FK to memories: the target of the diegetic correction.
- `detail_id` FK to memory_details: the new head row this correction produced.
- `verb` text CHECK in (`rationalization`, `update_with_resentment`): the diegetic subset of the
  `memory_details.write_cause` enum.
- `source_event` jsonb: the client-supplied in-world confrontation reference. Nullable.
- `created_at`, `valid_at` per the bi-temporal rules (world time of the confrontation).

### reconstruction_cache

- `memory_id` FK to memories.
- `identity_version` text: at reconstruction this column stores the composed reconstruction key,
  `identity_version` composed with the scene-frozen decay band (architecture.md §7). The column type and
  PK are unchanged.
- `rendered_text` text NOT NULL.
- `created_at`.
- PK `(memory_id, identity_version)`.
- Eviction is by the generalized invariant (any non-reconstruction writer to a chain evicts all rows for
  that memory_id), enforced in application code, not triggers.

### reflections

- `reflection_id` UUID PK, server default.
- `agent_id` FK to agents.
- `content` text NOT NULL.
- `identity_relevant` boolean: gates flow into the rendered identity document.
- `source_memory_ids` UUID[]: provenance only, intentionally not foreign-keyed, so purging an episode
  leaves the derived reflection intact (the purge-honesty stance).
- `created_at`, `valid_at`, `invalid_at`: bi-temporal like memories; invalidation of a reflection later
  doubles as parameter-compiler cache eviction.

### identity_components

The entity and topic index: gist matching plus the entity-gate tripwire.

- `component_id` UUID PK, server default.
- `agent_id` FK to agents.
- `canonical` text NOT NULL.
- `aliases` text[].
- `category` text.
- `created_at`, `invalid_at`: reflection-time pruning invalidates rather than deletes, consistent with
  non-destructive storage, and pruning silently invalidates reconstruction caches.

### identity_documents

- `agent_id` FK to agents.
- `rendered_text` text NOT NULL: the exact prompt block.
- `identity_version` text NOT NULL: the content hash of `rendered_text`.
- `created_at`.
- PK `(agent_id, identity_version)`; the current document is the latest `created_at` per agent.

## Indexes

- **HNSW** on `memories.embedding` with `vector_cosine_ops` (cosine, for the embedding model). Migration
  002 dropped this index (a derived structure with zero readers after the freeze), and the probe now runs
  on `memory_fact_versions`' partial HNSW (architecture.md §4.4).
- **GIN** on `memories.entities`. Dropped by migration 003 and replaced by a partial GIN on
  `memory_fact_versions` live heads ([mid-dialogue-gate.md](mid-dialogue-gate.md)).
- FK and lookup indexes: `memories(agent_id)`, `memory_details(memory_id)`, `memory_gist_spans(memory_id)`,
  `corrections(memory_id)`, `reflections(agent_id)`, `identity_components(agent_id)`.

## Mechanics

- Numbered SQL files under `db\migrations\` (for example `001_foundation.sql`) plus `db\migrate.py`, a
  minimal Python runner with a `schema_migrations` bookkeeping table. Each migration's DDL and its ledger
  row commit in one transaction, so a half-applied migration can never be logged complete. The later
  migrations: 002 (the fact-version chain, architecture.md §4.4); 003 (the entities fact-chain column,
  [mid-dialogue-gate.md](mid-dialogue-gate.md)); 004 (the hybrid lexical channel's partial FTS GIN over
  live fact heads, architecture.md §6); 005 (the `memories.escalation_failed` soft-degrade flag,
  architecture.md §5); 006 (deferred-write columns plus `memory_enrichment_runs`,
  [deferred-writes.md](deferred-writes.md)); 007 (`reflection_runs`, [reflection.md](reflection.md)); and
  008 (`compiled_bundles` plus `compiler_runs`, [parameter-compiler.md](parameter-compiler.md)).
- Docker: `pgvector/pgvector` for Postgres 16, with the connection string from `.env`.

## Verification

- Given a fresh Postgres 16 with pgvector, running the migration creates every table, check constraint,
  and index above (verifiable by query, not by eyeball).
- Running the migration a second time is a no-op, not an error.
- An insert violating a CHECK (a bad typology value, rigidity out of 0.5 to 2.0, confidence out of 0 to
  1) is rejected.
- Inserts omitting `memory_id`, `detail_id`, and the like have their server-side UUID defaults filled.
- A smoke-test fixture (one agent, one memory with one original detail row, one gist span, one identity
  component) inserts cleanly and reads back.
