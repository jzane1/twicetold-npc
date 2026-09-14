# The mid-dialogue gate

A non-LLM hybrid gate (a novelty check plus an entity tripwire) that decides whether a dialogue turn
should fetch new memories at all. Without it, retrieval fires unconditionally on every turn. The gate
is a stage inside the existing read seam, with no new route and no new event verb. Design truth is
[architecture.md](architecture.md) §6 (gate plus degradation ladder plus the prompt-caching boundary),
§4.3 (the two identity structures), §5 (entities at write), §7 (the mid-scene miss path), and §11
(efficacy definitions). The 001 schema is [migration-01.md](migration-01.md), and the fact chain is
architecture.md §4.4. A new migration (003) lands on the `db\migrate.py` ledger.

## Principles

- **Non-LLM, structurally.** No gate model, no gate env var, no gate pricing entry. The one model touch
  is the existing embedding role: the locked 1536 model embeds the gate-time utterance, and that
  embedding is the fetch probe, so it is one embed per turn, never two.
- **Two identity structures, never conflated (architecture.md §4.3).** The tripwire lookup reads the
  live `identity_components` table (canonical plus aliases); the coverage check reads the (post-003)
  live fact heads' entities via the keyed loaded-set fetch; and the degraded lexical fetch reads them
  through their partial GIN index (the index serves only the degraded rung). Distinct structures,
  distinct roles.
- **The reserved slot stays reserved.** `DialogueInitRequest.entities` (plus location and event_time) is
  the reserved-inert encoding-context slot. The gate never consumes it; mentions come from the utterance
  text against `identity_components`.
- **Every gate event logs which signal fired**, feeding the reserved novelty kill-switch, via named
  signal constants.
- **Nothing integrator-configurable is hardcoded.** Every gate knob is a `SERVICE_DEFAULTS` float,
  per-agent overridable via `agents.config`, resolved by `agent_knob`.
- **IDs and scores in every payload, closed-gate turns included.** A closed gate serves the loaded set
  with IDs, scores, and recomputed relevance; the suite's load-bearing contract never blinks.
- **Scene state lives in the caller**, and caller-side only: the loaded-set reset is a runner-side
  scene-state refresh, and the scene boundary keeps exactly its three server consumers.
- **Degradation is named and fail-quiet.** Every degraded turn carries the rung name and reason; the
  gate never errors a turn.
- **Instrument at the seam.** The gate-check latency term lands with the mechanism.
- **Non-destructive invariant untouched.** The 003 backfill populates a brand-new column; the gate
  itself writes nothing to memory content (its only writes are the ones retrieval already performs:
  reconstruction write-backs and cache rows).

## Design decisions

- **The loaded set is caller-held scene state.** The loaded set (the scene's accumulated surfaced
  memories, the comparison basis for both signals) is net-new state. The session runner (in production,
  the Unity client) keeps the loaded memory IDs as scene state, reset at scene boundaries, populated by
  the loader turn, appended on gate fetches, and passed per request; the server fetches those rows by ID
  each turn (one keyed SQL on live fact heads) for the novelty basis, the coverage check, and
  closed-gate serving. Absent fields give loader semantics, which is byte-parity with the non-gated
  path. This is the same caller-freezes-scene-state contract as the identity-version snapshot.
- **Migration 003 makes the fact head the sole entities home.** `memory_fact_versions` gains an
  `entities` column; observe writes entities to the fact head only; a guarded backfill from
  `memories.entities` runs before the index; a partial GIN covers live fact heads; the old
  `memories_entities_gin` is dropped; and `memories.entities` is frozen (pre-003 rows keep their values,
  never written again). One home makes "corrections move entities" true everywhere entities are read: the
  gate's coverage check and degraded fetch read entities, so a corrected memory must not keep firing or
  suppressing on corrected-away entities. The backfill is an UPDATE of a brand-new, never-populated
  column, a schema-evolution backfill, not a content mutation.
- **Correction entities are a mechanical NLP pass plus an optional operator field.** The corrected fact
  head's entities mirror observe's merge: spaCy NER over the corrected text merged with an optional
  `entities` field on `CorrectionRequest`, case-insensitive dedup; an absent field means NER alone.
  Non-LLM.
- **Per-signal fire logs are instrumentation-only.** `signals_fired` rides the turn instrumentation and
  the load driver's per-100-turn aggregates; the reserved novelty kill-switch reads run artifacts. There
  is no `gate_events` table and no per-turn DB write (such a table stays a possible future addition if a
  kill-switch ruling ever needs cross-session real-usage data).
- **The reconstructing signal is post-hoc response fields plus a pre-serve callback.** The reply carries
  the pause info (a derived flag plus the existing reconstruction counters), and the seam accepts an
  optional in-process callback fired the moment a blocking mid-scene serve begins. The REPL prints
  `(reconstructing...)` during the wait, and the Unity reconstructing-signal hook maps onto the same
  seam. There is no HTTP transport change; the route's JSON learns nothing mid-request. This is what
  delivers §7's intent, that latency becomes characterization.

## Surface

The gate is a stage inside the existing read seam:

- **Seam:** `retrieve_dialogue_init` (`app\retrieval.py`) grows a gate stage in front of the probe,
  delegated to `app\gate.py` (a pure decision module). `run_dialogue_turn` (`app\dialogue.py`) passes
  the new fields through uninterpreted; `POST /v1/dialogue/init` inherits the gate as route
  pass-through.
- **Request deltas:** `DialogueInitRequest` and `DialogueTurnRequest` gain `loaded_memory_ids` (plus the
  damper-streak field). Absent gives a loader turn, which is v1 semantics and byte-parity, so existing
  callers stay valid unmodified.
- **Response deltas:** a per-item `gate_fetched` (defaulted false) on `RetrievedMemory`, and a nested,
  fully-defaulted `GateInstrumentation` on `RetrievalInstrumentation`.
- **Callback:** an optional in-process callable rides the seam call chain (runner, dialogue, retrieval,
  serve), never the wire, fired once when a blocking mid-scene serve begins.
- **REPL:** the session runner grows loaded-set scene state (IDs plus damper streak; reset at `scene()`
  and session start; appended from each result's `gate_fetched` items); the debug view (`render_debug`)
  grows a gate line (signals fired, min distance, fetched count, rung); the callback prints
  `(reconstructing...)` mid-wait.
- **Load driver:** the latency table gains the `gate_check` p50/p95 series; the aggregate block gains
  per-100-turn gate rows (fires, per-signal counts, efficacy fractions, damper activations).
- **Correction verb:** `CorrectionRequest` gains an optional `entities`; `IngestService.correct` runs
  the NER merge; `CorrectionResult` widens accordingly.

## The gate pipeline

1. **Loader turn** (no `loaded_memory_ids` on the request): unconditional top-k retrieval, byte-identical
   to the non-gated path (probe, scoring, and serving all unchanged). The caller stores the returned
   memory IDs as the scene's loaded set. Dialogue init at a scene edge is the canonical loader, and any
   turn without the fields behaves identically.
2. **Gated turn:** embed the utterance once (fail-quiet; a failure enters the ladder). Fetch the loaded
   rows by ID, one keyed SQL on live fact heads (embedding, entities, and the candidate columns), via
   `fetch_loaded_set`. Fetch the agent's live `identity_components` (canonical plus aliases).
3. **Novelty check:** the min cosine distance from the utterance embedding to the loaded set's non-NULL
   fact-head embeddings; at or above `gate_novelty_threshold` the utterance is novel and fires.
   NULL-embedding loaded rows are excluded from the basis and counted in instrumentation. An empty basis
   (an empty loaded set, or all-NULL) is trivially novel.
4. **Entity tripwire:** case-insensitive word-boundary mention detection over the utterance text against
   live component canonicals and aliases, with no spaCy on the read path (mechanical string work stays
   mechanical). A mentioned component uncovered by any loaded item's fact-head entities fires. This is
   the most demo-legible signal.
5. **Damper:** consecutive fruitless fetches suppress further novelty fires this scene; the tripwire
   stays live.
6. **Decision, fire:** if any signal fired and the damper permits, the standard over-fetch probe runs,
   reusing the step-2 embedding; loaded IDs are excluded from the results; the top `gate_fetch_k` new
   items are appended and served through the existing reconstruction serving stage. A mid-scene cache
   miss blocks here, the callback fires as the block begins, and the pause rides the payload after (§7's
   latency becomes characterization). Fetched items are marked `gate_fetched`, and the caller appends
   their IDs to its loaded set. The loaded set is append-only within a scene: the damper limits
   additions, never removals.
7. **Decision, closed:** if no signal fired, serve the loaded set by ID with relevance recomputed free
   from step 3's distances (`clamp(1 - distance)`, the read-path formula, with no probe SQL and no second
   embed; a NULL-embedding loaded row carries `relevance = null`), recency and importance per the
   standard scoring, and a deterministic `(-score, memory_id)` order, through the serving stage (within a
   scene the scene-frozen band makes these cache hits, byte-identical text, zero calls).
   `signals_fired = []`.
8. **Logging and efficacy:** every gate event records `signals_fired` (named constants); fire events
   compute the efficacy booleans (`novelty_outscored`: the fetch out-scored the loaded set;
   `entity_covered`: the fetch contained the tripwire entity); a fruitless fetch (one appending zero new
   IDs) feeds the damper streak.

## Degradation ladder

| Condition | Behavior |
|---|---|
| utterance embedding call fails | Entity-only rung: the tripwire still evaluates (it is lexical); on fire, fetch lexically off the partial GIN over live fact heads, ranked `recency x importance_norm` (the read path's degraded formula; fetched items carry `relevance = null`); `degraded = true` plus reason. The degraded SQL (`fetch_entity_candidates`) states `invalid_at IS NULL` verbatim so the planner matches the partial index. |
| no live identity components, or no entities coverage basis | Novelty-only rung: the tripwire cannot evaluate; the novelty check alone gates. Named in instrumentation. |
| both out (embedding down and no lexical basis) | Closed rung: the gate closes, serves the loaded set, and fails quiet. Never an error, never a blank turn. |
| loaded-ID fetch fails, or IDs unknown, foreign, or dead | Fail-quiet: drop unknown IDs from the basis with an instrumentation count; a wholly-failed fetch degrades to the loader path with a reason. |
| mid-scene serve hits reconstruction rungs | Inherited unchanged from the reconstruction ladder (architecture.md §7); the gate adds no new reconstruction behavior, only the first mid-scene caller. |

## Migration 003: the entities fact-chain column

One file, DDL plus ledger row in one transaction, `IF NOT EXISTS` defense-in-depth, a guarded backfill
before the index, and a second run that is a no-op.

```sql
-- 003_fact_entities.sql
ALTER TABLE memory_fact_versions ADD COLUMN IF NOT EXISTS entities text[];

-- Backfill: populate the brand-new column from the canonical write-time record, an UPDATE of a
-- never-populated column on existing rows (schema-evolution backfill, not a content mutation). Before
-- the index, only rows still NULL: the ledger is the primary idempotency, the guard the backstop.
UPDATE memory_fact_versions f
SET entities = m.entities
FROM memories m
WHERE f.memory_id = m.memory_id AND f.entities IS NULL AND m.entities IS NOT NULL;

CREATE INDEX IF NOT EXISTS memory_fact_versions_entities_gin
    ON memory_fact_versions USING gin (entities) WHERE invalid_at IS NULL;

-- Freeze arm: the old GIN loses its readers the moment the gate's reads land on the fact head; a
-- derived structure, dropped like memories_embedding_hnsw.
DROP INDEX IF EXISTS memories_entities_gin;
```

The GIN is partial (live heads only), so the degraded SQL must state `WHERE invalid_at IS NULL` verbatim
to match. Superseded fact rows keep their entities exactly as superseded embedding rows keep their
vectors, and windowed SQL re-derives which entities were live at any instant.

## Immediate effect and invariants

The within-scene byte-identity invariant needs no amendment: the invariant governs served text per
memory, and which memories are surfaced was never under the byte-identity guarantee. A gate-fetched item
binds to the same scene-frozen basis as everything else and is byte-stable from its first mid-scene
serving onward; a closed-gate turn re-serves loaded items byte-identically. Loader-parity is a
structural claim: a request without the new fields is byte-identical to the non-gated path in behavior,
payload shape, and SQL.

## Instrumentation

A nested `GateInstrumentation` on `RetrievalInstrumentation`, fully defaulted: `evaluated`, `fired`,
`signals_fired`, `novelty_min_distance`, `uncovered_entities`, `fetched_memory_ids`,
`fetched_new_count`, `fruitless`, `damper_active`, `degraded_rung`, `novelty_outscored`,
`entity_covered`, `gate_ms`, and `reconstructing_blocked`. `gate_ms` joins the latency decomposition;
the load driver gains the `gate_check` p50/p95 series and per-100-turn gate rows (fires, per-signal
counts, novelty efficacy as the fraction of fires where the fetch out-scored the loaded set, entity
efficacy as the fraction where the fetch contained the tripwire entity, and damper activations).
`render_debug` gains the gate line. The gate is non-LLM, so no token or USD row exists for it.

## Knobs

All are `SERVICE_DEFAULTS` floats, per-agent via `agents.config` and `agent_knob`.

- `gate_novelty_threshold`, default **0.5** cosine min-distance. Calibration is provider-dependent: under
  the locality-sensitive fake, echoes sit around 0.04 and unrelated text near 1.0 (a fixture property),
  while real-provider paraphrase distances run about 0.05 to 0.25, and 0.5 sits above the 0.35 drift
  threshold's "left the neighborhood" line.
- `gate_fetch_k`, default **3** (a full `retrieval_top_k` re-fetch would swamp the loaded set).
- `gate_damper_fruitless_max`, default **2**.

A tuning recipe (the TARG budget-calibration pattern): `python -m app.load_driver --gate-budget <rate>`
reports the `gate_novelty_threshold` value at the `(1 - rate)` quantile of a run's empirical
novelty-min-distance CDF (that is, "fire on roughly N% of turns," a designer-legible target), plus the
observed rate at the service default. It is report-only: it never sets the knob and does not consult
per-agent overrides. Calibrate against real-provider runs, since the fake embedding's distance
distribution is a fixture property.

The damper mechanism: fruitless means a gate fetch appending zero new memory IDs; after
`gate_damper_fruitless_max` consecutive, the novelty signal is suppressed for the remainder of the scene
(the tripwire stays live); a scene boundary resets the streak and suppression; the streak is caller-held.

Signal constants: `GATE_SIGNAL_NOVELTY = "novelty"`, `GATE_SIGNAL_ENTITY = "entity_tripwire"`; rung names
`entity_only`, `novelty_only`, and `closed`.

A gate-disable pin exists in fixture configs only; the gate is production-active at real defaults. A
correction-path NER failure is a clean loud error with nothing written (`CorrectionNlpFailedError` gives
502, taking the embed precedent's all-or-nothing shape).

## Verification

- **Loader-parity.** A request without the new fields is byte-identical to the non-gated path across
  payload and SQL; the prior read-side walkers' unmodified assertion bodies are part of the proof.
- **Closed gate.** A covered, near-loaded utterance serves exactly the loaded IDs, zero probe SQL,
  `signals_fired == []`, relevance non-null on every embedded item (a NULL-embedding loaded row carries
  `relevance = null`), deterministic order.
- **Novelty fire.** A far utterance (the locality-sensitive fake makes distances deterministic, a fixture
  property; production uses real embeddings) fetches, appends only new IDs, marks them `gate_fetched`,
  and logs exactly `["novelty"]`.
- **Tripwire fire and covered suppression.** An uncovered live-component mention in a near-loaded
  utterance logs `["entity_tripwire"]` and the fetch contains the entity; the same mention covered by a
  loaded item's fact-head entities does not fire.
- **Both-signal logging.** A far utterance with an uncovered mention logs both constants; every fire
  event carries non-empty `signals_fired`.
- **Damper.** After the max of consecutive fruitless fetches, novelty is suppressed and the tripwire
  still fires; a scene boundary resets both.
- **Ladder, every rung.** Embed-failure gives an entity-only lexical fetch off the GIN ranked
  `recency x importance_norm` with `relevance = null`, degraded plus reason; a no-components agent gives
  novelty-only; both out gives closed, the loaded set served, fail-quiet, no error.
- **Mid-scene reconstruction beat.** A gate fetch hitting a past-theta uncached memory blocks; the
  callback is observed firing before the serve resolves; the served text is persisted and byte-stable on
  subsequent same-scene reads; the pause rides the payload.
- **Migration 003.** Applies once then no-ops; the backfill guard is proven against a legacy-shaped row;
  the new GIN is present and `memories_entities_gin` is absent; observe writes fact-head entities only; a
  correction moves entities (the NER plus operator-field merge) and windowed SQL re-derives entity
  liveness at any instant; superseded fact rows keep their entities.
- **Efficacy and aggregates.** The efficacy booleans populate per the comparators; the load driver emits
  the `gate_check` series and the per-100-turn gate rows.
- **Prompt structure assertable.** `assemble_prose_prompt` stays pure; the loaded-set order is stable;
  the marked recollection sub-block is present exactly when gate-fetched items exist.
- **Floors re-verified.** The prior walkers re-run on fresh scratch (expected additive deltas), and the
  independent verification passes. The walker is `tests\verify_gate.py`; see [test-suite.md](test-suite.md)
  Set D.
