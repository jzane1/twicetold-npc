# Mid-dialogue gate — v1 build target

Eighth build target, on top of migration 01, write path v1, read path v1, CLI harness v1,
reconstruction v1, authorial-correction v1, and fact-level correction v1. This specs **the
mid-dialogue gate** — immediate-queue item 1 since the 2026-07-18 fact-level build, and a
primary design decision from the project's start (the non-LLM hybrid: novelty check + entity
tripwire, `decisions.md`). The gap it closes: retrieval fires **unconditionally on every
dialogue turn** today (`app\dialogue.py`) — there is no "should we fetch" decision, no loaded
set, and no per-signal evidence for the reserved novelty kill-switch. The target also settles
three explicitly-deferred debts recorded elsewhere: the **entities fact-chain column** (the
2026-07-18 embedding-only ruling's honest deferral — entities' first read consumer is this
gate), the **block-with-"reconstructing"-signal wire shape** (deferred here by
`reconstruction.md`), and the **gate-check latency term** (§11's decomposition, emitted "no
gate term" since the CLI-harness build). Design truth is [architecture.md](architecture.md)
§6 (gate + degradation ladder + the prompt-caching boundary), §4.3 (the two identity
structures), §5 (entities at write), §7 (the mid-scene miss path), §11 (efficacy definitions);
the rulings are in `decisions.md`; the 001 schema is in
[migration-01.md](migration-01.md) and the 002 fact chain in
`fact-level-correction.md`. **A new migration is a fact of this
target — the second spec for which that is true**: migration 003 lands on the `db\migrate.py`
ledger seam. This doc points, it does not re-derive.

Five scope forks were ruled at spec time (dated "Mid-dialogue gate spec scope rulings —
2026-07-19" entry in `decisions.md`; forks 1, 2, 4, and 5 re-presented in plain prose at
Jack's request and ruled on the re-presentation — during which fork 5's recommendation was
honestly reversed, see below):

1. **Loaded-set home = caller-held scene state, reputation-style.** The loaded set — the
   scene's accumulated surfaced memories, the comparison basis for both signals — is net-new
   state with no home anywhere today. The session runner (in production: the Unity client)
   keeps the loaded memory IDs as scene state, reset at scene boundaries, populated by the
   loader turn, appended on gate fetches, and passes them per request; the server fetches
   those rows by ID each turn (one keyed SQL on live fact heads) for the novelty basis, the
   coverage check, and closed-gate serving. Absent fields ⇒ loader semantics ⇒ today's exact
   behavior. Third use of the ruled caller-freezes-scene-state contract (reputation snapshot
   2026-07-15, `identity_version` 2026-07-17). **Rejected:** server-side scene state (a
   scene-state table invents a persistent scene object + a write per turn + lifecycle
   questions in a no-DELETE store; an in-process cache breaks under the REPL-in-process +
   route-over-HTTP dual-caller topology and dies on restart mid-scene); per-turn
   approximation, no loaded set (runs the probe to decide whether to run the probe;
   already-recalled entities re-fire on every mention; contradicts §6's written design).
2. **Migration 003 entities = freeze — the fact head is the sole entities home.** The 002
   embedding precedent applied to entities: `memory_fact_versions` gains an `entities` column;
   observe writes entities to the fact head only; guarded backfill from `memories.entities`
   **before** the index; a partial GIN over live fact heads; the old `memories_entities_gin`
   dropped; `memories.entities` frozen (pre-003 rows keep their values, never written again —
   the accepted epoch split, same as the embedding's). Decisive: the gate's coverage check and
   degraded fetch **read** entities — one home makes "corrections move entities" true
   everywhere entities are read; under dual-home the gate would read the home corrections
   cannot move, and a corrected memory would keep firing/suppressing on corrected-away
   entities — the exact debt 003 exists to close. **Sanctioned backfill shape, explicitly:**
   the backfill is an UPDATE of a brand-new, never-populated column on existing fact rows —
   schema-evolution backfill in the 002 spirit, not a content mutation; the non-destructive
   invariant is untouched. **Rejected:** dual-home (two homes for one fact drift apart; the
   coverage-check incoherence above).
3. **Correction entities = mechanical NLP pass + optional operator field.** The corrected
   fact head's entities mirror observe's merge exactly: spaCy NER over the corrected text
   merged with an optional `entities` field on `CorrectionRequest`, case-insensitive dedup;
   absent field ⇒ NER alone. Non-LLM. The fact-level fork-1 rejection of an NLP re-pass
   rested on "entities feed nothing readable today" — a premise this target ends; its price
   (the write path's NLP stack enters the correction path, operator-verb latency grows) was
   restated and accepted. **Rejected:** NER-only (drops the client-supplied merge observe
   has — the operator couldn't pin an entity NER misses); operator-field-only (corrections
   without the field don't move entities); copy-forward-only (the deferral's stated purpose —
   "so fact-corrections can move entities" — would move to a future target again).
4. **Per-signal fire logs = instrumentation-only.** `signals_fired` rides the turn
   instrumentation (the write path's `escalated_by` precedent) and the load driver's
   per-100-turn aggregates; the reserved novelty kill-switch decision reads run artifacts
   (`--json` exists). Zero schema, zero per-turn DB writes. A persisted `gate_events` table
   stays **pull-forward eligible** if the kill-switch ruling later demands cross-session
   real-usage data. **Rejected:** persisted gate-event rows riding 003 (a DB write per gate
   evaluation — base rates need non-fire rows, so per-turn; the purge contract grows to a new
   memory-referencing table; more schema in a target already carrying a migration — all before
   any long-running real usage exists).
5. **Reconstructing signal = post-hoc response fields + a pre-serve callback.** The reply
   carries the pause info (derived flag + the existing reconstruction counters), AND the seam
   accepts an optional in-process callback fired the moment a blocking mid-scene serve begins —
   the REPL prints `(reconstructing…)` **during** the wait, and the queued Unity
   "reconstructing-signal hook" maps onto the same seam. No HTTP transport change; the route's
   JSON learns nothing mid-request. **Recommendation reversed at the plain-prose presentation,
   recorded honestly:** fields-only had been recommended technically (it keeps
   `app\reconstruction.py` byte-untouched), but fields-only cannot show anything *during* the
   pause — it cannot deliver §7's "latency becomes characterization" intent, which is the
   signal's entire purpose. Price accepted: one added defaulted parameter touches the serving
   path; the reconstruction floor re-opens at build and re-verifies — a step, not a cost.
   **Rejected:** fields-only (the during-the-wait effect is unreachable); SSE/streaming now (a
   real mid-request push, but a new transport class built before Unity — its only consumer —
   exists; nothing rules it out later).

The **fruitless-retrieval damper** was deliberately *not* forked: its mechanism (undesigned in
architecture §6) stays `[SETTLE-AT-BUILD]` with a full suggested default below — **flagged
promotable**: if Jack wants it ruled rather than suggested, promote it before the build.

> **Status: BUILT & floor-verified 2026-07-19** (same day as the spec). Two `[SETTLE-AT-BUILD]`
> items were ruled via explicit questions at plan approval (dated "Mid-dialogue gate build
> rulings" entry in `decisions.md`): **the damper = as suggested** (the promotable flag closed —
> fruitless = zero new IDs appended; 2 consecutive suppress the NOVELTY signal for the scene
> remainder; tripwire live; scene reset) and **correction-path NER failure = clean loud error,
> nothing written** (`CorrectionNlpFailedError` → 502, the embed precedent). The remaining
> shapes were approved with the plan, including **`gate_enabled`** as the fixture-pin /
> kill-switch-scaffold knob. New: `app\gate.py` (pure decision module),
> `db\migrations\003_fact_entities.sql` (applied to `longmem`; no-arg migrate → **"Up to date:
> 3 migration(s) applied, 0 pending"**), the gated/loader branch + `_gated` in
> `app\retrieval.py`, the freeze at observe + `GateRow` + three gate fetchers in `app\db.py`,
> the NER merge + `CorrectionNlpFailedError` in `app\ingest.py` (+ 502 in `app\api.py`), the
> pre-serve callback in `app\reconstruction.py` (one defaulted param), loaded-set/streak state
> in `app\session.py`, the prompt partition + `"Recalled just now, mid-conversation:"`
> sub-header in `app\dialogue.py`, `GateInstrumentation` + wire deltas in `app\schemas.py`,
> four knobs in `app\config.py`, the CLI gate line + `(reconstructing…)` print, and the
> load-driver `gate_check` series + gate block. Walker `tests\verify_gate.py` (**51
> assertions** — grown past the ~34 estimate, addition only); prior walkers: write-path 38 → 40
> (additive freeze pair), authorial 33 → 34 and fact 32 → 34 (additive entities-chain),
> read-path 36 **byte-untouched** (the loader-parity proof), cli-harness 36 (fixture pin + one
> ok-label edit), reconstruction 42 (fixture pin only, assertion bodies untouched).
> floor-verifier **pass** with working postgres MCP tools; `longmem` pristine. Live piped REPL
> beat: loader turn → mid-scene novelty fetch → both-signal fire with `fruitless=yes` →
> `:correct` → **`(reconstructing…)` printed DURING the blocked turn** (`blocked=yes`), the
> latency-becomes-characterization beat live. Standalone driver run emits `gate_check` p50/p95
> + the gate block with real fire/efficacy data. **Build-measured calibration correction,
> recorded honestly:** under the trigram fake, ordinary distinct prose lands ~0.45–0.75 (not
> the estimated ~1.0 — shared English trigrams); echoes ~0.04, near-copies ~0.08. The 0.5
> default stands; guaranteed-novel *fixtures* need trigram-rare wording (the walker's damper
> text was chosen by measurement, min-distance ≥ 0.73).

## Principles this build honors

- **Non-LLM, structurally.** No gate model, no gate env var, no gate pricing entry — the
  stack-constant list is unchanged. The one model touch is the existing embedding role: the
  locked 1536 model embeds the gate-time utterance (§3), and that embedding **is** the fetch
  probe — one embed per turn, never two.
- **Two identity structures, never conflated (§4.3).** The **tripwire lookup** is the live
  `identity_components` table (canonical + aliases); the **coverage check** reads the
  (post-003) live fact heads' entities via the keyed loaded-set fetch, and the **degraded
  lexical fetch** reads them through their partial GIN index (the index serves only the
  degraded rung). Distinct structures, distinct roles — the spec states both homes so the
  build cannot blur them.
- **The reserved slot stays reserved.** `DialogueInitRequest.entities` (+ location/event_time)
  is the RESERVED-inert encoding-context slot (ruled 2026-07-14). **The gate never consumes
  it** — mentions come from the utterance text against `identity_components`.
- **Every gate event logs which signal fired** — the design's own requirement (`decisions.md`),
  feeding the reserved novelty kill-switch. Named signal constants, the `TRIGGER_*` precedent.
- **Nothing integrator-configurable is hardcoded.** Every gate knob is a `SERVICE_DEFAULTS`
  float, per-agent overridable via `agents.config`, resolved by `agent_knob`.
- **IDs and scores in every payload — closed-gate turns included.** A closed gate serves the
  loaded set with IDs, scores, and recomputed relevance; the suite's load-bearing contract
  never blinks.
- **Scene state lives in the caller** — the third application of the ruled contract, and
  **caller-side only**: the loaded-set reset is a runner-side scene-state refresh; the scene
  boundary keeps exactly its three server consumers (§6).
- **Degradation is named and fail-quiet, per the ladder** (audit ruling #3): every degraded
  turn carries the rung name and reason; the gate never errors a turn.
- **Instrument at the seam.** The §11 "gate check" latency term lands with the mechanism —
  the literal "no gate term" reservations in `app\schemas.py` / `app\load_driver.py` close at
  build.
- **Non-destructive invariant untouched.** The 003 backfill populates a brand-new column
  (fork 2's sanctioned shape); the gate itself writes nothing to memory content — its only
  writes are the ones retrieval already performs (reconstruction write-backs and cache rows,
  unchanged).

## Scope boundary — do NOT build

**Prompt caching / prompt-head rebuild / any cache API** (post-August, sequenced-later): this
target lands the *structure* caching later attaches to — the loaded set served in stable
append-only order with gate-fetched items in a marked recollection sub-block — and nothing
else. **The encoding-context read term** — the reserved request slots stay inert; the gate
reads none of them. **The novelty kill-switch decision** — this target produces its evidence
(per-signal fire logs, efficacy fractions), not its ruling. **`gate_events` persistence**
(rejected in fork 4; pull-forward eligible). **SSE/streaming transport and the Unity hook
implementation** — the fork-5 callback is the seam the Unity hook will attach to; the hook
itself rides the Unity target. **Split-brain per-call weights** (sequenced-later then;
*pulled forward 2026-07-21 — `split-brain-streaming.md`*). **The
pytest suite** (immediate-queue item 2 then — Set D below was specced for it, not built here;
*built 2026-07-20*).
**Reflection-time component pruning** (post-August; until then the tripwire's lookup set only
grows). *(Expired 2026-08-15: the C2 build landed the mechanical trim — `reflection.md` — so
the lookup set can now SHRINK when a reflect call prunes a stale component; the gate needed no
change, `fetch_live_components` already followed liveness.)* If adjacent work looks necessary,
stop and report — with the correct option and its real cost stated, per the reframed contract.

## Surface (where this attaches)

The gate is a stage inside the existing read seam — no new route, no new event verb:

- **Seam:** `retrieve_dialogue_init` (`app\retrieval.py`) grows a gate stage in front of the
  probe, delegated to a gate module (`[SETTLE-AT-BUILD]` home — suggested a new `app\gate.py`,
  the `reconstruction.py` stage-module precedent). `run_dialogue_turn` (`app\dialogue.py`)
  passes the new fields through unreinterpreted (the `identity_version` precedent);
  `POST /v1/dialogue/init` inherits the gate route-is-pass-through.
- **Request deltas:** `DialogueInitRequest` and `DialogueTurnRequest` gain
  `loaded_memory_ids` (+ the damper-streak field per its settle-tag). **Absent ⇒ loader
  turn ⇒ v1 semantics, byte-parity** — existing callers and walkers stay valid unmodified.
- **Response deltas:** per-item `gate_fetched` (defaulted false) on `RetrievedMemory`; a
  nested, fully-defaulted `GateInstrumentation` on `RetrievalInstrumentation` (the
  reconstruction-fields precedent — prior construction sites stand).
- **Callback (fork 5):** an optional in-process callable rides the seam call chain (runner →
  dialogue → retrieval → serve), never the wire; fired once when a blocking mid-scene serve
  begins. `[SETTLE-AT-BUILD]` signature.
- **REPL:** the session runner grows loaded-set scene state (IDs + damper streak; reset at
  `scene()` and session start; appended from each result's `gate_fetched` items); the debug
  view (`render_debug`) grows a gate line (signals fired, min distance, fetched count, rung);
  the callback prints `(reconstructing…)` mid-wait. No new meta-commands expected (stop and
  report if the build finds otherwise).
- **Load driver:** the latency table gains the `gate_check` p50/p95 series; the aggregate
  block gains per-100-turn gate rows (fires, per-signal counts, efficacy fractions, damper
  activations).
- **Correction verb (fork 3):** `CorrectionRequest` gains optional `entities`;
  `IngestService.correct` runs the NER merge; `CorrectionResult` widens per the settle-tag.

## Mechanism — the gate pipeline

1. **Loader turn** (no `loaded_memory_ids` on the request): unconditional top-k retrieval,
   byte-identical to v1 — probe, scoring, serving all unchanged. The caller stores the
   returned memory IDs as the scene's loaded set. Dialogue init at a scene edge is the
   canonical loader; any turn without the fields behaves identically.
2. **Gated turn:** embed the utterance once (fail-quiet; failure enters the ladder). Fetch
   the loaded rows by ID — one keyed SQL on live fact heads (embedding, entities, and the
   candidate columns), `[SETTLE-AT-BUILD]` shape (`fetch_loaded_set`). Fetch the agent's live
   `identity_components` (canonical + aliases).
3. **Novelty check:** min cosine distance from the utterance embedding to the loaded set's
   non-NULL fact-head embeddings; `>= gate_novelty_threshold` ⇒ novel ⇒ fire. NULL-embedding
   loaded rows are excluded from the basis and counted in instrumentation. An empty basis
   (empty loaded set, or all-NULL) ⇒ trivially novel ("far from all" of nothing) —
   `[SETTLE-AT-BUILD]` confirmation.
4. **Entity tripwire:** case-insensitive word-boundary mention detection over the utterance
   text against live component canonicals + aliases — **no spaCy on the read path** (the
   thinning-function precedent: mechanical string work stays mechanical). A mentioned
   component **uncovered** by any loaded item's fact-head entities ⇒ fire. (Most demo-legible
   signal.)
5. **Damper:** per its settle-tag — consecutive fruitless fetches suppress further novelty
   fires this scene; the tripwire stays live.
6. **Decision — fire:** any signal fired (and the damper permits) ⇒ the standard over-fetch
   probe runs, **reusing the step-2 embedding**; loaded IDs are excluded from the results;
   the top `gate_fetch_k` *new* items are appended, served through the existing
   reconstruction serving stage — a mid-scene cache miss **blocks here**, the fork-5 callback
   fires as the block begins, and the pause rides the payload after (§7's latency-becomes-
   characterization). Fetched items are marked `gate_fetched`; the caller appends their IDs
   to its loaded set. The loaded set is **append-only within a scene** — the damper limits
   additions, never removals.
7. **Decision — closed:** no signal fired ⇒ serve the loaded set by ID: relevance recomputed
   **free** from step 3's distances (`clamp(1 − distance)`, the read-path formula — no probe
   SQL, no second embed; a NULL-embedding loaded row carries `relevance = null`, the
   read-path precedent), recency and importance per the standard scoring, deterministic
   `(−score, memory_id)` order, through the serving stage (within a scene the scene-frozen
   band makes these cache hits — byte-identical text, zero calls). `signals_fired = []`.
8. **Logging and efficacy:** every gate event records `signals_fired` (named constants);
   fire events compute the §11 efficacy booleans (`novelty_outscored`: the fetch out-scored
   the loaded set; `entity_covered`: the fetch contained the tripwire entity —
   `[SETTLE-AT-BUILD]` exact comparators); fruitlessness (a fetch appending zero new IDs)
   feeds the damper streak.

## Degradation ladder (gate) — audit ruling #3, implementation-shaped

| Condition | Behavior |
|---|---|
| utterance embedding call fails | **entity-only rung:** the tripwire still evaluates (it is lexical); on fire, fetch lexically off the (post-003) partial GIN over live fact heads, ranked `recency × importance_norm` (the read path's degraded formula; fetched items carry `relevance = null`); `degraded = true` + reason; `[SETTLE-AT-BUILD]` SQL shape (`fetch_entity_candidates` — the GIN's first reader; the predicate `invalid_at IS NULL` stated verbatim so the planner matches the partial index). |
| no live identity components, or no entities coverage basis | **novelty-only rung:** the tripwire cannot evaluate; the novelty check alone gates. Named in instrumentation. |
| both out (embedding down AND no lexical basis) | **closed rung:** gate closed, serve the loaded set, fail-quiet — never an error, never a blank turn. |
| loaded-ID fetch fails, or IDs unknown/foreign/dead | `[SETTLE-AT-BUILD]` — suggested fail-quiet: drop unknown IDs from the basis with an instrumentation count; a wholly-failed fetch degrades to the loader path with reason. |
| mid-scene serve hits reconstruction rungs | inherited unchanged from `reconstruction.md`'s ladder — the gate adds no new reconstruction behavior, only the first mid-scene caller. |

## Deltas per touched floor (each priced as the re-verification step it is)

- **Dialogue seam** (`app\dialogue.py`): pass-through of the new fields; the `[memories]`
  prompt block becomes the scene's loaded set in stable append-only order, gate-fetched items
  under a marked recollection sub-header (`[SETTLE-AT-BUILD]` exact block text) — the
  structure prompt caching later attaches to. `assemble_system_prompt` *(renamed
  `assemble_prose_prompt` at the 2026-07-21 split-brain build; noted 2026-08-07 audit)* stays a
  pure function; block order stays walker-assertable. Floor re-opens; walker re-runs.
- **Retrieval** (`app\retrieval.py` + `app\gate.py` + `app\db.py`): the gate stage in front
  of the probe; new keyed SQL `fetch_loaded_set` and degraded `fetch_entity_candidates`; the
  loader path **byte-identical to v1** — the parity claim the prior walkers prove. Floor
  re-opens.
- **Session runner** (`app\session.py`): loaded IDs + damper streak as scene state — reset at
  `scene()` and session start, populated by the loader turn, appended on fetches.
  **Caller-side only — no fourth scene-boundary server consumer.** Floor re-opens
  (CLI-harness walker; fixture-compat shape per the settle-tag).
- **Reconstruction — minimal ruled delta (fork 5), deliberately not "none":** the serving
  path accepts one optional, defaulted pre-serve callback parameter; behavior with the
  parameter absent is unchanged. The floor re-opens and re-verifies; the walker's existing
  assertions stand (expected additive growth only). This is the honest contrast with the
  fact-level build's byte-untouched claim — ruled with its price stated.
- **Write path — freeze (fork 2):** `insert_observation` writes entities to the fact head
  only; `memories.entities` is never written post-003. The write-path walker's entities
  assertions move to the fact head — a ruling-driven walker change, the 002 signal-move
  precedent. Floor re-opens.
- **Correction verb (fork 3):** `IngestService.correct` grows the NER + optional-field merge;
  the corrected fact head carries the merged entities in the same transaction. The
  authorial and fact-correction walkers grow the entities assertions (additive expected).

## Migration 003 — the entities fact-chain column

Lands on the ledger seam: one file, DDL + ledger row in one transaction, `IF NOT EXISTS`
defense-in-depth, guarded backfill **before** the index, second run a no-op, ruling-dated
comments. Sketch (all names `[SETTLE-AT-BUILD]`, suggested):

```sql
-- 003_fact_entities.sql (suggested name)
ALTER TABLE memory_fact_versions ADD COLUMN IF NOT EXISTS entities text[];

-- Backfill: populate the brand-new column from the canonical write-time record —
-- an UPDATE of a never-populated column on existing rows (sanctioned, fork 2 —
-- schema-evolution backfill in the 002 spirit, not a content mutation). Before the
-- index, only rows still NULL: the ledger is the primary idempotency, the guard the backstop.
UPDATE memory_fact_versions f
SET entities = m.entities
FROM memories m
WHERE f.memory_id = m.memory_id AND f.entities IS NULL AND m.entities IS NOT NULL;

CREATE INDEX IF NOT EXISTS memory_fact_versions_entities_gin
    ON memory_fact_versions USING gin (entities) WHERE invalid_at IS NULL;

-- Freeze arm (fork 2, ruled): the old GIN loses its readers the moment the gate's
-- reads land on the fact head; derived structure, dropped like memories_embedding_hnsw.
DROP INDEX IF EXISTS memories_entities_gin;
```

- The GIN is **partial (live heads only) — ruled with fork 2**, not a settle-tag; the degraded
  SQL must state `WHERE invalid_at IS NULL` verbatim so the planner matches (the 002
  partial-index precedent).
- After 003, the floor criterion reads **"001 + 002 + 003 applied, 0 pending"** — the build
  updates that wording wherever it is recorded.
- Superseded fact rows keep their entities exactly as superseded embedding rows keep their
  vectors — windowed SQL re-derives which entities were live at any instant.

## Immediate effect & invariants

The within-scene byte-identity invariant needs **no amendment** (contrast: the authorial
target amended it): the invariant governs served *text* per memory — **which memories are
surfaced was never under the byte-identity guarantee** (the fact-level precedent wording). A
gate-fetched item binds to the same scene-frozen basis as everything else and is byte-stable
from its first mid-scene serving onward; a closed-gate turn re-serves loaded items
byte-identically. Loader-parity is a structural claim: a request without the new fields is
byte-identical to v1 in behavior, payload shape, and SQL. CLAUDE.md is deliberately untouched
by this spec.

## Instrumentation (rides the seam)

Nested `GateInstrumentation` on `RetrievalInstrumentation`, fully defaulted
(`[SETTLE-AT-BUILD]` exact fields — suggested: `evaluated`, `fired`, `signals_fired`,
`novelty_min_distance`, `uncovered_entities`, `fetched_memory_ids`, `fetched_new_count`,
`fruitless`, `damper_active`, `degraded_rung`, `novelty_outscored`, `entity_covered`,
`gate_ms`, `reconstructing_blocked`). The §11 reservations close at build: `gate_ms` joins
the latency decomposition (`app\schemas.py`'s "no gate term" docstring), the load driver
gains the `gate_check` p50/p95 series (`app\load_driver.py`'s reserved comment) and
per-100-turn gate rows — fires, per-signal counts, **novelty efficacy** (fraction of fires
where the fetch out-scored the loaded set), **entity efficacy** (fraction where the fetch
contained the tripwire entity), damper activations. `render_debug` gains the gate line. The
gate is non-LLM: no token or USD row exists for it.

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

- **Knobs** (all `SERVICE_DEFAULTS` floats, per-agent via `agents.config` / `agent_knob`):
  `gate_novelty_threshold` — suggested **0.5** cosine min-distance (calibration honestly
  split: under the locality-sensitive *fake*, echoes sit ~0.04 and unrelated text ~1.0 — a
  fixture property; real-provider paraphrase distances run ~0.05–0.25; 0.5 sits above the
  0.35 drift threshold's "left the neighborhood" line). `gate_fetch_k` — suggested **3**
  (a full `retrieval_top_k` re-fetch would swamp the loaded set). `gate_damper_fruitless_max`
  — suggested **2**. *(**Tuning recipe added 2026-07-20** — the TARG budget-calibration
  pattern, arXiv 2511.09803 §3.4, adopted with the research slate:
  `python -m app.load_driver --gate-budget <rate>` reports the `gate_novelty_threshold` value
  at the `(1 − rate)` quantile of a run's empirical novelty-min-distance CDF — i.e. "fire on
  roughly N% of turns," a designer-legible target — plus the observed rate at the service
  default. **Report-only**: it never sets the knob, and per-agent `agents.config` overrides are
  not consulted (stated in the report). Calibrate against real-provider runs before trusting
  the number — the fake embedding's distance distribution is a fixture property.)*
- **Damper mechanism (promotable — see the fork preamble):** fruitless = a gate fetch
  appending zero new memory IDs (structural; the alternative comparator is the
  novelty-efficacy boolean); after `gate_damper_fruitless_max` consecutive, the **novelty
  signal** is suppressed for the remainder of the scene (the tripwire stays live —
  near-ground-truth); a scene boundary resets streak and suppression; the streak is
  caller-held (`gate_fruitless_streak` wire field, or folded into a small loaded-set state
  object — exact wire shape settled with the request deltas).
- **Prior-walker / fixture compatibility:** a gate-disable pin **in fixture configs only**
  (the `reconstruction_theta = 0` precedent) — the gate is **production-active at real
  defaults**; exact form (a `gate_enabled`-class knob vs threshold pinning) settled at build,
  with its interplay with the reserved kill-switch noted (per-signal disables may become the
  kill-switch's home).
- **Signal constants:** suggested `GATE_SIGNAL_NOVELTY = "novelty"`,
  `GATE_SIGNAL_ENTITY = "entity_tripwire"`; rung names `entity_only | novelty_only | closed`
  (the `TRIGGER_*` precedent, module-level named strings).
- **Module home:** suggested new `app\gate.py`, delegated to by the retrieval seam.
- **Mention detection + coverage:** case-insensitive word-boundary match against live
  component canonical + aliases; coverage = the tripwire entity present in any loaded item's
  live-fact-head entities array (exact normalization settled at build).
- **Empty/degenerate bases:** empty loaded set ⇒ trivially novel; NULL-embedding loaded rows
  excluded and counted; unknown/foreign/dead loaded IDs per the ladder row.
- **Wire shapes:** `loaded_memory_ids` (+ streak) on both requests;
  `RetrievedMemory.gate_fetched` defaulted false; the `GateInstrumentation` field list above;
  `CorrectionRequest += entities` (optional); `CorrectionResult` widening for the NER merge
  (suggested: the merged entities list + NER timing).
- **Efficacy comparators:** `novelty_outscored` — suggested top fetched score strictly
  exceeds the minimum loaded-set score under the turn's probe; `entity_covered` — suggested
  any fetched item's entities contain the tripwire entity.
- **Callback signature (fork 5):** in-process only, rides the seam call chain, never the
  wire; suggested a zero-arg callable invoked once per blocking serve; REPL rendering of
  `(reconstructing…)`.
- **DB shapes:** `fetch_loaded_set(pool, agent_id, ids)`;
  `fetch_entity_candidates(pool, agent_id, entities)`; migration physical names per the
  sketch (the partial GIN itself is ruled — fork 2).
- **Correction-verb mechanics (fork 3):** NER call site in `IngestService.correct`,
  merge/dedup shape (suggested: observe's exact case-insensitive dedup), NLP-unavailable
  behavior on the correction path (suggested: fail-loud like the embed — the operator verb's
  stance — but priced at build).
- **Walker:** suggested `tests\verify_gate.py`, scratch pattern, ~34 assertions across the
  done-when list; expected prior-walker deltas — write-path ruling-driven change (freeze),
  authorial + fact-correction additive growth, reconstruction re-run after the callback
  parameter, read-path/CLI-harness compat pins, loader-parity proven by unmodified assertion
  bodies.
- **CLI debug line + load-driver shapes:** the gate line's rendering; the `gate_check` series
  name; the per-100-turn gate row set.

## Done when

- **Loader-parity.** A request without the new fields is byte-identical to v1 across payload
  and SQL; the prior read-side walkers' unmodified assertion bodies are part of the proof.
- **Closed gate.** A covered, near-loaded utterance serves exactly the loaded IDs, zero probe
  SQL, `signals_fired == []`, relevance non-null on every embedded item (a NULL-embedding
  loaded row carries `relevance = null`), deterministic order.
- **Novelty fire.** A far utterance (the locality-sensitive fake makes distances
  deterministic — a fixture property; production uses real embeddings) fetches, appends only
  new IDs, marks them `gate_fetched`, logs exactly `["novelty"]`.
- **Tripwire fire + covered suppression.** An uncovered live-component mention in a
  near-loaded utterance logs `["entity_tripwire"]` and the fetch contains the entity; the
  same mention covered by a loaded item's fact-head entities does not fire.
- **Both-signal logging.** A far utterance with an uncovered mention logs both constants;
  every fire event carries non-empty `signals_fired`.
- **Damper.** After the ruled max of consecutive fruitless fetches, novelty is suppressed and
  the tripwire still fires; a scene boundary resets both.
- **Ladder, every rung.** Embed-failure ⇒ entity-only lexical fetch off the GIN ranked
  `recency × importance_norm` with `relevance = null`, degraded + reason; no-components agent
  ⇒ novelty-only; both out ⇒ closed, loaded set served, fail-quiet, no error.
- **Mid-scene reconstruction beat.** A gate fetch hitting a past-theta uncached memory blocks;
  the callback is observed firing before the serve resolves; the served text is persisted and
  byte-stable on subsequent same-scene reads; the pause rides the payload.
- **Migration 003.** Applies once then no-ops ("001 + 002 + 003 applied, 0 pending"); the
  backfill guard proven against a legacy-shaped row (the 002 walker precedent); the new GIN
  present, `memories_entities_gin` absent; observe writes fact-head entities only; a
  correction moves entities (NER + operator-field merge) and windowed SQL re-derives entity
  liveness at any instant; superseded fact rows keep their entities.
- **Efficacy + aggregates.** The efficacy booleans populate per the ruled comparators; the
  load driver emits the `gate_check` series and the per-100-turn gate rows.
- **Prompt structure assertable.** `assemble_system_prompt` *(renamed `assemble_prose_prompt`,
  2026-07-21 split-brain build; noted 2026-08-07 audit)* stays pure; loaded-set order
  stable; the marked recollection sub-block present exactly when gate-fetched items exist.
- **Floors re-verified.** All seven prior walkers re-run on fresh scratch (expected deltas
  per the settle-tag); `longmem` pristine via the postgres MCP; floor-verifier **pass**.
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and
  recorded in `decisions.md`.

## Propagated with this spec

`architecture.md` §6 (gate specced marker + the ladder's GIN-home under freeze), §5 (entities
freeze annotation), §4.4 (entities-follow-correction annotation), §11 (lands-with markers);
`decisions.md` (the dated rulings entry; the 2026-07-18 fork-1 deferral-closure annotation;
audit ruling #3's GIN-home annotation); `fact-level-correction.md` (deferral-closure
annotations); `reconstruction.md` (block-with-signal wire shape now settled here; the "no
gate term" pointer); `write-path.md` (entities-freeze §d annotation + GIN-reachability and
signal-home residuals); `read-path.md` + `cli-harness.md` (gate-specced pointers on their
scope-boundary and no-gate-term lines); `authorial-correction.md` (the `CorrectionRequest`
optional-entities annotation); `migration-01.md` (003 pointers); `test-suite.md` (new Set D +
the ladder row's GIN-home pointer); `status.md` (phase, log, queue annotation — no renumber
at spec time); CLAUDE.md deliberately unchanged.
