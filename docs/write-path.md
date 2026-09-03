# Write path & ingestion API — v1 build target

Second build target, on top of migration 01. This specs the **write half of the vertical slice**
(*event in → memory stored*), exposed as one ingest service. Design truth is
[architecture.md](architecture.md) §4–§5; the rulings behind it are in [decisions.md](decisions.md);
the schema it writes into is frozen in [migration-01.md](migration-01.md). This doc points, it does
not re-derive.

> **Status: BUILT & floor-verified 2026-07-13.** Every `[SETTLE-AT-BUILD]` item and open flag below
> was ruled at build time (dated "Write-path build — fork rulings" entry in `decisions.md`); the
> rulings are annotated inline. **The build added no new DB migration — the migration-01 schema
> stayed frozen.** One ruling was an explicit build-phase stance since **re-ruled 2026-07-22 to
> soft-degrade** — the escalation failure path (see the degradation ladder; migration 005 added the
> dedicated `escalation_failed` flag).
>
> **Amended 2026-08-12 (Phase C1 — `deferred-writes.md`, migration 006, the first post-freeze
> migration since 005):** the pipeline gains a knob-gated **deferred mode** (default OFF) — the
> two LLM calls move to an in-process worker; the NLP pass, embedding, and atomic insert stay
> synchronous, and the sync path is byte-unchanged. The degradation ladder gains the deferred
> rows below. The write parse also gained the `typology_confidence` salvage seat (ruled
> 2026-08-12; the clamp's sibling).

## Principles this build honors

- **Atomic, bi-temporal, non-destructive insert.** One observe event lands as one transaction:
  never a partial write. `valid_at` is the client's world time (tz-aware, NOT NULL); `created_at` is
  server write time. No UPDATE-in-place, no DELETE.
- **All write-time facts populated day one** (architecture §2) — typology + confidence + source,
  provenance, context stamps, decay class, gist spans, importance, pin — even where the consuming
  mechanism is deferred.
- **Single instrumentation seam.** Exactly one function — the ingest service — carries the timing and
  token accounting. The CLI (in-process) and the FastAPI route are both thin callers of it; neither
  duplicates the seam. (CLAUDE.md: *instrument at the seam*.)
- **Structured return, not just prose.** The service returns memory IDs **and** the computed
  scores/facts as structured data, so the CLI debug view and the scenario suite assert on structure,
  never on generated prose ([test-suite.md](test-suite.md)). This extends the read-path invariant
  (IDs + scores in every payload) to the write path.
- **Nothing integrator-configurable is hardcoded** — model roles (per-role env var), decay-class
  map, thresholds, vocabularies.
- **Degradation is named and tested per model call** (architecture §2) — a flaky model never loses a
  write. *(The escalation call was the one build-phase exception; re-ruled 2026-07-22 to soft-degrade,
  so the no-lost-write rule now holds without exception — see the degradation ladder.)*

## Scope boundary — do NOT build

Read/dialogue path & retrieval scoring; the retrieval gate; prompt caching; the reconstruction
mechanism; reflection; the diegetic-correction mechanism; purge; reputation-delta emission; Unity;
and **any new DB schema or migration**. The diegetic-correction and purge verbs are *documented*
in the contract below but their handlers are out of scope. If adjacent work looks necessary, **stop
and report** rather than expand scope.

## The ingest service (the seam)

One entry point, both callers sit on it:

```
ingest_observation(event: ObserveEvent) -> IngestResult      # observation ingestion
scene_boundary(event: SceneBoundaryEvent) -> SceneResult      # accept + instrument only (v1)
set_pin(memory_id, pinned: bool) -> PinResult                 # toggle memories.pinned
```

- The **CLI harness** calls these in-process; the **FastAPI routes** are thin wrappers over the same
  functions. The route serializes the service's result and adds nothing: for one ingest, the route's
  JSON response is exactly the `IngestResult` the service returned, and the timing + token accounting
  is recorded once, at the service seam. (Two *separate* ingests differ — each mints fresh UUIDs and
  records its own timings — so the equivalence asserted is route-is-pass-through, not two calls
  matching.)

### `IngestResult` — the structured payload

Returned by `ingest_observation`, surfaced verbatim in the CLI debug view and asserted by the suite:

- **Identifiers** — `memory_id`, `detail_id` (the `original` head), `gist_span_ids[]`,
  `new_component_ids[]` (identity components grown by this write).
- **Computed facts / scores** — `importance_raw`; `typology` + `typology_confidence` +
  `typology_source`; `provenance`; `affect` (`valence`, `arousal`, `detail`); `entities[]`;
  `decay_class` + `decay_class_unknown`; `scoring_failed`; `embedding_failed` *(payload-only
  extension ruled 2026-07-13: mirrors the NULL-embedding degradation so it is assertable without a
  DB peek)*; `pinned`.
- **Instrumentation** — per-stage timing (`nlp_ms`, `embed_ms`, `haiku_ms`, `insert_ms`, `total_ms`),
  token accounting (`haiku_input_tokens`, `haiku_output_tokens`; embedding token count), and the
  escalation record ruled 2026-07-13: `escalated`, `escalated_by[]` (which triggers fired),
  `escalation_ms`, `escalation_input_tokens`, `escalation_output_tokens` — feeds the per-100-turn
  cost table.

## Event contract (ingestion API v1)

### `observe` — the core event

| Field | Meaning |
|---|---|
| `agent_id` | target NPC (FK → agents). |
| `observation_text` | the raw observation. Stored immutable; NLP + embedding run on it. |
| `phase_tag` | integrator observation-phase vocabulary. Accepted in v1 but **not stored and not echoed** — it has no schema home yet (ruled 2026-07-13). |
| `client_timestamp` | world time → `valid_at` (tz-aware, required). |
| `provenance` | `lived` \| `injected`. |
| `typology` / `typology_confidence` | optional client declaration — **client wins**; when absent, Haiku classifies and `typology_source = inferred`. |
| `decay_class` | integrator label; validated against the agent's `config` map. |
| context (all optional) | `location_name` (stored) + its embedding → `location_embedding`; `entities[]`; `event_time`; `affect` override. A longer location *description*, if supplied, is embed-only (no raw column in the frozen schema). |
| `pinned` | optional; sets `memories.pinned` at insert. |
| `event_id` | optional idempotency key; **accepted but not enforced in v1** — not stored, not echoed (dedup needs schema; ruled 2026-07-13). |

### `scene-boundary`

The explicit, client-sent scene edge (architecture §6). Its three consumers were slated 2026-07-14:
**reputation snapshot → the dialogue turn (landed 2026-07-15 with the CLI harness — caller-side, in
the session-runner, which re-reads `agents.reputation` at each boundary)**; identity-document
recompile → reconstruction (**landed 2026-07-17**, `reconstruction.md`: the handler now
recompiles server-side — render seed → hash → `identity_documents` upsert — and returns
`identity_version`, its first server-side write); prompt-head rebuild →
post-August (see `decisions.md`). **The handler accepts the event and instruments it (timing), and
does nothing else; it writes no schema.** The contract exists now so the demo choreography and the
eventual mechanisms hook a stable, tested event.

### `pin` / `unpin`

Toggle `memories.pinned` for a `memory_id`. Pin means exactly two things (architecture §8), both
honored later at read: decay exemption + reconstruction exclusion. **Freezing the head** and
restoration-as-a-correction-verb are read/reconstruction concerns and are deferred *(pre-demo since
the 2026-07-14 re-slating)*; v1 sets the flag.

### Built since (previously deferred, documented only)

- **diegetic-correction** — an in-world confrontation event referencing a target `memory_id`; routes
  through the dissonance path. **Built C4 (2026-08-17)** — `dissonance.md`.
- **purge** — the GDPR delete verb (architecture §12). **Built C6 (2026-08-18)**: per-memory
  `DELETE /v1/memories/{id}`, the sanctioned content DELETE; reflections derived from the
  purged memory survive as aggregate work-product. **Extended 2026-09-02** by the per-agent
  `DELETE /v1/agents/{id}/memories` (ruled 2026-09-01 as the thin extension): the same
  seven-table delete over every memory of one agent, one transaction — the two verbs are the
  whole carve-out.

## Write pipeline (`observe`)

Client event → NLP pass → single Haiku call → embedding → atomic insert (architecture §5).

**a. NLP pass (no LLM).** Tokenize + NER + noun-chunk extraction; match tokens/entities/noun-chunks
against the agent's `identity_components` (canonical + aliases + category) → **gist spans as
half-open char offsets into `observation_text`** (never rewritten text); a category hit counts even
without a named entity. Affect via a cheap lexicon pass → `affect_valence` / `affect_arousal` /
`affect_detail`. Intra-observation coreference. A **novel entity grows** `identity_components`
(new row). Cross-observation coreference misses are accepted (the detail just decays) — architecture
§4.1.

An **LLM-escalation pass** exists for hard cases, **biased loose** (over-call — a wasted call is
cheap, a lost gist breaks the product). Five triggers as ruled 2026-07-13 — a sixth,
`thin_gist`, joined 2026-07-23 (annotated below and in architecture §4.1) — any one fires:
importance above threshold; an identity/category hit co-occurring with |valence| above threshold;
a novel entity; an unresolved pronoun/noun-chunk co-occurring with an identity/category hit; low
NLP confidence on an already-flagged span (confidence only ever adds calls).

**b. Single Haiku call.** Prose render + importance scoring + typology classification **only when the
client did not declare it**. Structured output → `{ rendered_content, importance_raw, typology?,
typology_confidence? }`. **Degradation:** on scoring failure the write **still lands** with neutral
importance and `scoring_failed = true` (architecture §2); on unparseable structured output → log,
apply neutral/default, the turn succeeds. *(Deferred mode, 2026-08-12: with
`deferred_writes_enabled` on, this call and the escalation call are SKIPPED here and run in
`app\deferred.py`'s worker instead — the raw text lands as the head, the scalars land NULL with
`enrichment_pending`, and the worker's completion supersedes with the render
(`write_cause = 'enrichment'`); `deferred-writes.md` owns the mechanism.)*

**c. Embedding.** OpenAI `text-embedding-3-small` at **1536** (locked) for `observation_text` →
`embedding`, and for the location name/description → `location_embedding`. The frozen schema stores
the location **name** + its embedding only; a longer description is embed-only (no new column).
*(Freeze ruling 2026-07-18, `fact-level-correction.md`: the observation vector's destination is
now the `original` fact head on `memory_fact_versions` — `memories.embedding` is no longer
written; `location_embedding` is unaffected.)*

**d. Atomic insert (one transaction).** `memories` (all write-time facts) + the `original`
`memory_details` head (`write_cause = original`) + `memory_gist_spans` + any new
`identity_components`. Validate `decay_class` against the agent `config` map; **unknown label →
default class + `decay_class_unknown = true`** (never reject — mirrors `scoring_failed`). Commit,
then return `IngestResult`. *(Fact-level correction built 2026-07-18,
`fact-level-correction.md`: this transaction also mints the `original` fact-version row, and
the build **ruled freeze** — the observation vector is written only there, never to
`memories.embedding`. This floor was deliberately re-opened and re-verified, walker 35 → 38 —
one modification ruled with the freeze: the embed-degradation signal assertion moved to the
fact head.)* *(Gate spec 2026-07-19, freeze ruling — the same precedent applied to entities:
at the gate build this transaction writes entities to the `original` fact head only;
`memories.entities` frozen post-003, its GIN replaced by a partial GIN on live fact heads —
`mid-dialogue-gate.md`.)*

### The render seam *(confirmed as specced — ruled 2026-07-13)*

`observation_text` = the client's **raw** observation, immutable forever (architecture §2, §4.1). The
Haiku render produces the **`original` detail row's `content`** (the initial telling that
reconstruction later supersedes). Gist spans point into `observation_text`, not the rendered detail.
On write-call failure the head falls back to the raw observation text — never a lost write.

## Degradation ladder (write)

| Condition | Behavior |
|---|---|
| importance-scoring model fails | write lands; neutral importance; `scoring_failed = true`. |
| unknown `decay_class` label | write lands; default class; `decay_class_unknown = true`. |
| malformed Haiku structured output | log, ignore, apply neutral/default; the write succeeds. |
| embedding call fails | write lands; NULL embedding (`embedding IS NULL` is the queryable signal; payload mirror `embedding_failed`). *(Ruled 2026-07-13; signal home since the 2026-07-18 freeze: the live fact head — `memory_fact_versions.embedding IS NULL`.)* |
| escalation call fails twice | **SOFT-DEGRADE** — retry once, then proceed with the base NLP-pass gist and set `escalation_failed = true` (the write lands, never lost). *(Re-ruled 2026-07-22, retiring the 2026-07-13 fail-loud hard-stop; the flag is the dedicated `memories.escalation_failed` column, migration 005.)* |
| model-emitted `typology_confidence` non-numeric / out-of-range | **SALVAGE** (ruled 2026-08-12, the typology clamp's sibling seat): non-numeric/NaN → None (render, importance, typology all survive; the confidence knob-defaults); out-of-range clamps into [0, 1]; WARNING logs. The client-declared value keeps its loud 422. |
| *deferred mode:* worker write call fails (attempt) | **RETRY-LATER** (deliberately different from the sync degrade-now, ruled 2026-08-12): a `failed` run row lands in `memory_enrichment_runs`; the row stays `enrichment_pending` for a later drain pass. |
| *deferred mode:* attempt budget spent (`deferred_max_attempts`) | **TERMINAL FILL** — neutral importance + `scoring_failed = true` + the config-default typology, pending cleared: **byte-equivalent to the sync scoring-failed end-state**. The raw head stays the live telling; nothing is chain-written. |
| *deferred mode:* worker embedding repair fails | write already landed; the fact head stays honestly NULL — today's end-state, retried opportunistically on any later attempt of that row. |

## Model provider interfaces

Each model role is an integrator knob with its own env var (architecture §3). The write path depends
on two provider interfaces — the **Haiku call** (render + importance + typology) and the **embedding**
(OpenAI 1536). Each ships with:

- a **real implementation** (drives the demo), and
- a **deterministic fake** (stable pseudo-embedding, fixed importance, echo render, deterministic
  typology) so the **structural suite and CI run offline, without keys, and never assert on prose**.

The provider is selected by config; the ingest service is identical under either.

## `[SETTLE-AT-BUILD]` — physical shapes, all ruled at build (2026-07-13; see `decisions.md`)

- **NLP stack** — spaCy model choice; coreference library (`fastcoref` vs `coreferee` — never
  `neuralcoref`); affect lexicon and its mapping to
  `affect_valence`/`affect_arousal`/`affect_detail`. *(Ruled 2026-07-13: spaCy `en_core_web_lg` +
  `fastcoref`; VADER compound → `affect_valence`; **Warriner 2013 VAD lexicon → `affect_arousal`**
  (1–9 normalized to 0–1), dominance + raw breakdowns in `affect_detail` jsonb. NRC-VAD rejected at
  the license gate — research-only; Warriner is CC-BY 4.0, bundled under `data\lexicons\`.)*
- **LLM-escalation** — the importance threshold value, the structural-ambiguity proxy definition, and
  novel-entity growth (the spam gate on growth is deferred). *(Ruled 2026-07-13: full escalation in
  v1 — separate provider + `LONGMEM_MODEL_ESCALATION`; five triggers, any one fires, all
  integrator-tunable via `agents.config` with defaults in `app\config.py`; novel-entity growth in,
  spam gate still deferred. Failure path: soft-degrade to the base NLP-pass gist, flagged
  `escalation_failed` — re-ruled 2026-07-22, see the degradation ladder. Grown 2026-07-23 by the
  trigger-tuning measurement: a sixth **thin_gist** trigger fires when the base NLP pass yields
  fewer spans than the `escalation_min_base_spans` floor — see the dated `decisions.md` entry.)*
- **Idempotency** — **none in v1** (the frozen schema has no dedup column). A client `event_id` +
  dedup window would need schema this build forbids, so it is deferred to a future migration unless
  Jack rules otherwise; v1 accepts `event_id` but does not enforce it. *(Ruled 2026-07-13: as
  specced — accept, don't enforce; no new schema.)*
- **Embedding-failure degradation** — fail the write vs. null embedding + flag. *(Ruled 2026-07-13:
  the write lands with a NULL embedding; `embedding IS NULL` is the queryable signal, mirrored in
  the payload as `embedding_failed`. The memory stays reachable via the entity/GIN path; vector
  backfill is future work.)* *(Gate spec 2026-07-19: the entity/GIN reachability moves to the
  fact-head partial GIN at migration 003 — `mid-dialogue-gate.md`.)*
- **Wire shape** — the `observe` request/response Pydantic models and the FastAPI route path/verb.
  *(Ruled 2026-07-13: `POST /v1/events/observe`, `POST /v1/events/scene-boundary`,
  `PUT /v1/memories/{memory_id}/pin`; models in `app\schemas.py`; the route is a pass-through.)*

*(Settled, not a fork: importance is stored **raw** at write and normalized at read — architecture §2,
`memories.importance_raw`.)*

## Open flags — all resolved at build (2026-07-13)

- **scene-boundary has no persistent schema home** and all three consumers are deferred → v1 accepts
  + instruments only. Confirms **no migration-02 is needed** for this build. *(Confirmed: built as
  accept + instrument; no schema written.)*
- **render seam** — raw `observation_text` vs. rendered `original` detail (above): confirm the
  mapping. *(Confirmed as specced — see the render-seam section.)*
- **arousal** — VADER has no arousal axis. *(Closed: Warriner supplies arousal —
  `affect_arousal` **is populated** in v1.)*

## Done when

- **Atomic happy path (fake provider).** Given an `observe` event and the deterministic fake
  providers, when `ingest_observation` runs, then exactly one `memories` row, one `original`
  `memory_details` head, and the expected `memory_gist_spans` rows exist **after a single committed
  transaction**, and the returned `IngestResult` carries their IDs + the computed scores/facts.
- **One seam, thin route.** For a single ingest, the FastAPI route's JSON response is exactly the
  serialization of the `IngestResult` the service produced (the route adds and drops nothing), and
  the timing/token accounting is recorded once at the service seam — proving both callers sit on one
  instrumented seam.
- **Importance degradation.** Given a provider that fails importance scoring, the write still lands
  with neutral importance and `scoring_failed = true`.
- **Unknown decay class.** Given a `decay_class` absent from the agent's config map, the write lands
  with the default class and `decay_class_unknown = true` (not rejected).
- **Client typology wins.** Given a client-declared `typology`, the stored row has that value and
  `typology_source = declared`; given none, Haiku classifies and `typology_source = inferred`.
- **Novel entity grows the index.** Given an observation naming an entity absent from
  `identity_components`, a new component row exists and its id appears in `new_component_ids`.
- **Pin.** `set_pin(memory_id, true)` sets `memories.pinned = true`; the `IngestResult`/read reflects
  it.
- **Instrumentation present.** Every `IngestResult` carries non-null per-stage timings and Haiku
  token counts.
- **Gist immutability holds.** Gist spans reference `observation_text` offsets; `observation_text` is
  never rewritten by the write path.

*Four criteria added by the 2026-07-13 build rulings (the walker asserts all fourteen):*

- **Escalation soft-degrade (re-ruled 2026-07-22).** Given an escalation provider that fails twice on
  a triggered event, the write **lands** with the base NLP-pass gist — one `memories` row inserted —
  and `escalation_failed = true` on both the result and the dedicated column (migration 005); never a
  lost write.
- **Arousal populated.** Given observation text covered by the Warriner lexicon, the stored
  `affect_arousal` is non-null (normalized 0–1) and dominance rides in `affect_detail`.
- **Escalation accounting.** Given a fired trigger, the `IngestResult` instrumentation carries
  `escalated = true`, the firing trigger names in `escalated_by[]`, and escalation timing + token
  counts; given no trigger, those fields sit at their zero-values.
- **Embedding degradation.** Given a failing embedding provider, the write still lands with
  `embedding IS NULL` and the payload carries `embedding_failed = true`.
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and recorded in
  `decisions.md`.
