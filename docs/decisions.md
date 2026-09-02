# twicetold-npc — Decision register

Append-only log of settled design decisions. Reference decisions by their **bolded names**. Do not
reopen without cause. If a newer decision conflicts with an older one, the newer wins and the older
entry gets a *superseded* note — never delete entries. Mechanics live in `architecture.md`; this
file records what was chosen, what it beat, and why (where the rationale was recorded).

## Index

*63 dated sections (recounted 2026-08-15 at the C2 build landing: 63 body entries, 63
index lines, one-to-one; prior recounts 62 at the same date's spec landing, 61 at the
dossier landing, 60 at the
2026-08-15 wrap-up sweep, 59 at the 2026-08-13 interim-README landing). Regenerated 2026-07-28 — the first hand-written pass mixed two
slug conventions and miscounted. Anchors follow GitHub's slugger: the em dash is dropped and
its surrounding spaces both become hyphens, so `Name — 2026-07-28` anchors as `#name--2026-07-28`.*

*Append-only: when you add an entry at the end, add its line here too.*

- [Primary decisions](#primary-decisions)
- [Downstream decisions](#downstream-decisions)
- [Audit rulings](#audit-rulings)
- [Tension log (summary)](#tension-log-summary)
- [Decay & gist session — 2026-07-12 (latest word; refines the migration spec)](#decay--gist-session--2026-07-12-latest-word-refines-the-migration-spec)
- [Authorial-correction ruling — 2026-07-12](#authorial-correction-ruling--2026-07-12)
- [Schema-gap rulings — 2026-07-12](#schema-gap-rulings--2026-07-12)
- [Local DB + MCP infra — 2026-07-13](#local-db--mcp-infra--2026-07-13)
- [Migration 01 build — fork rulings & schema deltas — 2026-07-13](#migration-01-build--fork-rulings--schema-deltas--2026-07-13)
- [Write-path spec scope rulings — 2026-07-13](#write-path-spec-scope-rulings--2026-07-13)
- [Write-path build — fork rulings & build notes — 2026-07-13](#write-path-build--fork-rulings--build-notes--2026-07-13)
- [Re-slating ruling — reconstruction moves pre-demo — 2026-07-14](#re-slating-ruling--reconstruction-moves-pre-demo--2026-07-14)
- [Read-path spec scope rulings — 2026-07-14](#read-path-spec-scope-rulings--2026-07-14)
- [Read-path build rulings — 2026-07-14](#read-path-build-rulings--2026-07-14)
- [CLI-harness spec scope rulings — 2026-07-14](#cli-harness-spec-scope-rulings--2026-07-14)
- [CLI-harness build rulings — 2026-07-15](#cli-harness-build-rulings--2026-07-15)
- [Full-project audit rulings — 2026-07-16](#full-project-audit-rulings--2026-07-16)
- [Reconstruction spec scope rulings — 2026-07-17](#reconstruction-spec-scope-rulings--2026-07-17)
- [Reconstruction build rulings — 2026-07-17](#reconstruction-build-rulings--2026-07-17)
- [Reconstruction flagged-shapes confirmations — 2026-07-17](#reconstruction-flagged-shapes-confirmations--2026-07-17)
- [Scope-limiter reframing — 2026-07-17](#scope-limiter-reframing--2026-07-17)
- [Authorial-correction spec scope rulings — 2026-07-17](#authorial-correction-spec-scope-rulings--2026-07-17)
- [Authorial-correction build rulings — 2026-07-18](#authorial-correction-build-rulings--2026-07-18)
- [Fact-level correction spec scope rulings — 2026-07-18](#fact-level-correction-spec-scope-rulings--2026-07-18)
- [Fact-level correction build rulings — 2026-07-18](#fact-level-correction-build-rulings--2026-07-18)
- [Mid-dialogue gate spec scope rulings — 2026-07-19](#mid-dialogue-gate-spec-scope-rulings--2026-07-19)
- [Mid-dialogue gate build rulings — 2026-07-19](#mid-dialogue-gate-build-rulings--2026-07-19)
- [Test-suite build rulings — 2026-07-20](#test-suite-build-rulings--2026-07-20)
- [Latency-fix + suite-concurrency rulings — 2026-07-20](#latency-fix--suite-concurrency-rulings--2026-07-20)
- [Research-adoption slate + encoding-context build rulings — 2026-07-20](#research-adoption-slate--encoding-context-build-rulings--2026-07-20)
- [Hybrid lexical channel build rulings — 2026-07-20](#hybrid-lexical-channel-build-rulings--2026-07-20)
- [Real-mode parse hardening ruling — 2026-07-21](#real-mode-parse-hardening-ruling--2026-07-21)
- [Latency slate + split-brain pull-forward rulings — 2026-07-21](#latency-slate--split-brain-pull-forward-rulings--2026-07-21)
- [Split-brain streaming build rulings — 2026-07-21](#split-brain-streaming-build-rulings--2026-07-21)
- [External-persona audit + pre-demo replan rulings — 2026-07-22](#external-persona-audit--pre-demo-replan-rulings--2026-07-22)
- [Escalation failure-path + pre-warm + R7 rulings — 2026-07-22](#escalation-failure-path--pre-warm--r7-rulings--2026-07-22)
- [Escalation soft-degrade build — 2026-07-22](#escalation-soft-degrade-build--2026-07-22)
- [HTTP turn route + perceived-TTFT build rulings — 2026-07-23](#http-turn-route--perceived-ttft-build-rulings--2026-07-23)
- [Escalation trigger tuning: measurement + rulings — 2026-07-23](#escalation-trigger-tuning-measurement--rulings--2026-07-23)
- [Demo-vehicle ruling — Unity, not an established-game mod — 2026-07-27](#demo-vehicle-ruling--unity-not-an-established-game-mod--2026-07-27)
- [Unity-client fork rulings + stage-0 build (three backend routes) — 2026-07-27](#unity-client-fork-rulings--stage-0-build-three-backend-routes--2026-07-27)
- [Unity-client stages 1-3 — build record — 2026-07-27](#unity-client-stages-1-3--build-record--2026-07-27)
- [Full-repo audit rulings — 2026-07-28](#full-repo-audit-rulings--2026-07-28)
- [Reconstruction model class + migration immutability — 2026-07-28](#reconstruction-model-class--migration-immutability--2026-07-28)
- [Floors-register append-only scope — 2026-07-29](#floors-register-append-only-scope--2026-07-29)
- [Haiku dialogue + quote-embargo lift — 2026-07-29](#haiku-dialogue--quote-embargo-lift--2026-07-29)
- [Stage-2 Play-mode gate verification + real-mode corroboration — 2026-07-29](#stage-2-play-mode-gate-verification--real-mode-corroboration--2026-07-29)
- [Eval-harness v1 plan rulings + stage-1 build — 2026-07-29](#eval-harness-v1-plan-rulings--stage-1-build--2026-07-29)
- [Scope consolidation + road-to-completion rulings — 2026-08-04](#scope-consolidation--road-to-completion-rulings--2026-08-04)
- [A1 split-brain removal + weights-on-speech — spec forks + build record — 2026-08-04](#a1-split-brain-removal--weights-on-speech--spec-forks--build-record--2026-08-04)
- [Eval-harness stage 2 — session rulings + build record — 2026-08-05](#eval-harness-stage-2--session-rulings--build-record--2026-08-05)
- [Eval-harness stage 3 — session rulings + build record — 2026-08-07](#eval-harness-stage-3--session-rulings--build-record--2026-08-07)
- [Unity state is ordinary repo state — 2026-08-07](#unity-state-is-ordinary-repo-state--2026-08-07)
- [Gold-label workaround + measurement-line rulings — 2026-08-12](#gold-label-workaround--measurement-line-rulings--2026-08-12)
- [Judge validation numbers — the agreement bar rules — 2026-08-12](#judge-validation-numbers--the-agreement-bar-rules--2026-08-12)
- [Eval-harness stage 4 — build record + R7's deciding data — 2026-08-12](#eval-harness-stage-4--build-record--r7s-deciding-data--2026-08-12)
- [R7 resolved — the drift budget is a topic guard, not a fact guard — 2026-08-12](#r7-resolved--the-drift-budget-is-a-topic-guard-not-a-fact-guard--2026-08-12)
- [Dialogue model re-ruled — haiku stands, latency rules — 2026-08-12](#dialogue-model-re-ruled--haiku-stands-latency-rules--2026-08-12)
- [Typology robustness ruled — clamp at the parse seam — 2026-08-12](#typology-robustness-ruled--clamp-at-the-parse-seam--2026-08-12)
- [C1 spec rulings — deferred write processing — 2026-08-12](#c1-spec-rulings--deferred-write-processing--2026-08-12)
- [typology_confidence salvage ruled — the clamp's sibling seat — 2026-08-12](#typology_confidence-salvage-ruled--the-clamps-sibling-seat--2026-08-12)
- [Phase C1 build record — deferred writes landed — 2026-08-12](#phase-c1-build-record--deferred-writes-landed--2026-08-12)
- [Interim public README — public ahead of Phase F — 2026-08-13](#interim-public-readme--public-ahead-of-phase-f--2026-08-13)
- [Em-dashes banned from public-facing prose — 2026-08-13](#em-dashes-banned-from-public-facing-prose--2026-08-13)
- [C2 design-dossier rulings — reflection — 2026-08-15](#c2-design-dossier-rulings--reflection--2026-08-15)
- [C2 spec rulings — reflection build target — 2026-08-15](#c2-spec-rulings--reflection-build-target--2026-08-15)
- [Phase C2 build record — reflection landed — 2026-08-15](#phase-c2-build-record--reflection-landed--2026-08-15)
- [Phase C3 build record — the parameter compiler landed — 2026-08-17](#phase-c3-build-record--the-parameter-compiler-landed--2026-08-17)
- [Session-effort audit — the status.md tripwire — 2026-08-17](#session-effort-audit--the-statusmd-tripwire--2026-08-17)
- [Phase C4 build record — the dissonance path landed — 2026-08-17](#phase-c4-build-record--the-dissonance-path-landed--2026-08-17)
- [Phase C5 build record — client contract completion landed — 2026-08-17](#phase-c5-build-record--client-contract-completion-landed--2026-08-17)
- [Phase C6 build record — the purge endpoint landed — 2026-08-18](#phase-c6-build-record--the-purge-endpoint-landed--2026-08-18)
- [Phase C7 fork rulings and Stage A build record — the concurrency cap landed — 2026-08-18](#phase-c7-fork-rulings-and-stage-a-build-record--the-concurrency-cap-landed--2026-08-18)
- [Phase C7 Stage B build record — the scene-boundary pre-warm landed — 2026-08-18](#phase-c7-stage-b-build-record--the-scene-boundary-pre-warm-landed--2026-08-18)
- [Phase D1 — latency, believability, and the model-slate lock — 2026-08-19](#phase-d1--latency-believability-and-the-model-slate-lock--2026-08-19)
- [Phase E1 rulings + build record — the authoring guide and demo corpus landed — 2026-08-19](#phase-e1-rulings--build-record--the-authoring-guide-and-demo-corpus-landed--2026-08-19)
- [Phase E2 rulings + build record — choreography, the code gaps, and the Ledger live feed — 2026-08-19](#phase-e2-rulings--build-record--choreography-the-code-gaps-and-the-ledger-live-feed--2026-08-19)
- [E2 rehearsal executed — blockers cleared, the recording state pinned — 2026-08-22](#e2-rehearsal-executed--blockers-cleared-the-recording-state-pinned--2026-08-22)
- [E3 first attempt — recorded and QA'd, master not cut; presentation redesign ruled — 2026-08-24](#e3-first-attempt--recorded-and-qad-master-not-cut-presentation-redesign-ruled--2026-08-24)
- [Roadmap re-sequenced — F0 audit pass added; the demo endgame moves after Phase F; Phase G re-pointed — 2026-08-24](#roadmap-re-sequenced--f0-audit-pass-added-the-demo-endgame-moves-after-phase-f-phase-g-re-pointed--2026-08-24)
- [F0 spec rulings + build record — the audit/test/improve pass landed — 2026-08-26](#f0-spec-rulings--build-record--the-audittestimprove-pass-landed--2026-08-26)
- [Consumer-context scan rulings — the pre-release market pass — 2026-09-01](#consumer-context-scan-rulings--the-pre-release-market-pass--2026-09-01)
- [The rename — longmem-npc → twicetold-npc — 2026-09-02](#the-rename--longmem-npc--twicetold-npc--2026-09-02)

## Primary decisions

**Schema now, mechanism later.** All write-time schema and population ship day one, even where the
consuming mechanism (reconstruction, dissonance, reflection) is deferred past the August demo. Pin
was promoted from schema-only to working day-one behavior for the demo. Rationale: lock schema and
API surface early so mechanisms land without migrations, and so the structural test suite can assert
shape before cognition exists.

*(Superseded in part 2026-07-14 by the re-slating ruling below: the reconstruction mechanism moves
into pre-demo scope. The schema-now stance itself and the dissonance and reflection deferrals
stand.)*

**Retrieval gate: non-LLM hybrid (novelty + entity tripwire).** Mid-dialogue fetches are gated by an
embedding-novelty check plus an identity-components entity tripwire. No LLM in the gate. A **novelty
kill-switch is reserved** — to be decided later from the per-signal fire logs, which is why every
gate event records which signal fired. The entity tripwire is the most demo-legible signal.

**Turn topology: single call ships August; split-brain is the committed target.** August: one
Sonnet-class call emits prose + structured output. Target: a Haiku-class behavior call with its own
retrieval weights chooses the action; the dialogue call sees it as observed world fact. Contracts
(especially the action directive) are written to survive the migration. *(Superseded in part
2026-07-21 by the "Latency slate + split-brain pull-forward rulings" entry: the split-brain
lands PRE-demo, the two calls run CONCURRENTLY, and the dialogue call sees only PAST actions
as world facts — never the current turn's. The contract-survival line stands, and held.)*

**Memory identity: permanent id + version chain (write-back).** One `memory_id` forever; retellings
insert new detail rows superseding the prior. This resolved the critical fork of the project —
view-only vs write-back reconstruction — as **write-back with a scoped drift budget**. Rationale:
repetition-breeds-commitment (Talk of the Town precedent) requires retellings to be stored; the
bi-temporal chain keeps ground truth intact underneath.

**Habituation guards: both cap and decay.** For the future encoding-context term; both exist as
integrator knobs; implementation deferred.

**Dissonance threshold: importance × evidence typology × per-NPC rigidity (0.5–2.0).** "I saw it"
resists harder than "I heard it," on both sides of a clash. The store records the truth either way;
the threshold only shapes the character's reaction.

**Vector index: HNSW.** Chosen as cheaply reversible.

**Retention: tested purge endpoint, no scheduler.** The tool provides the delete verb; the schedule
is the integrator's policy. Purge deletes the original, its chain, and its caches; reflections
derived from purged episodes remain as aggregate work-product, and the docs say so honestly.

**License: Apache-2.0.** Public flip deferred to an end-of-project sprint.

**Prompt caching: append within scene, rebuild at scene boundaries.** Gate-fetched memories append
after the cached head as a marked recollection block; the head rebuilds at scene edges, where the
cache is cold anyway.

## Downstream decisions

**Drift budget: embedding distance from anchor; refuse-write past threshold.** Scoped to
reconstruction-driven write-backs only; event-driven (diegetic) writes are exempt. Re-anchoring by
cause: authorial → the corrected original; update-with-resentment → the new head; rationalization →
never (spends headroom without being blocked; a heavily defended memory crystallizes — "the story
has set"). The anchor is derivable, no pointer: the latest chain row with `write_cause` in
{original, authorial_correction, update_with_resentment}.

**Two correction verbs.** Authorial (operator fixes wrong data) is **replace-model**: it supersedes
the drifted chain with a corrected head row typed `authorial_correction`; the memory stays
retrievable with corrected content, and that head becomes the drift anchor. Diegetic (in-world
confrontation referencing a target memory) extends the chain through the dissonance path
(`rationalization` or `update_with_resentment` head, plus a correction record). Any correction
evicts caches. *(Authorial semantics ruled 2026-07-12 — dated entry below.)*

**Identity document: rendered + content-hashed.** Seed prose + identity-relevant reflections
rendered into the exact prompt block; `identity_version` = content hash; recompiled at scene edges.

**Reconstruction serving: batched Haiku, pre-warm, block-with-signal.** One structured call batches
all k cache misses per retrieval; pre-warm at dialogue init; a mid-scene miss blocks and exposes a
"reconstructing" signal (latency becomes characterization). The reconstruction threshold reuses the
decay math. Async serve-verbatim-then-cache was explicitly rejected; any future async must be
explicit state, never silent text mutation (within-scene text-stability invariant).

**Reflection: endpoint + pressure gauge.** No scheduler; the integrator pulls the trigger. Sampling
weighted by importance × recency, not recent-N. *(Amended 2026-08-15 — see "C2 design-dossier
rulings": the endpoint and the gauge stand; an optional default-OFF `ReflectionWorker` on the C1
lifecycle contract may pull the same seam when pressure crosses a per-agent knob threshold.)*

**Scene-type parameter bundles: typed core + namespaced passthrough.** Integrator-owned scene-type
vocabulary; unknown types log-and-continue against a default bundle; compiled params consumed only
upstream of the dialogue call.

**Typology & confidence: client wins.** Optional client-declared typology; Haiku classifies when
absent; `typology_source` records declared vs inferred. Confidence 0–1 from a default per-typology
table with per-event client override.

**Context stamps: four optional fields, typed columns.** Location, entities, time, affect; per-field
degradation stated; typed column per component (per-component read weights require it); location
embedded via the same 1536 model. *(2026-07-19 gate-spec freeze: entities' home moves to the
fact chain at migration 003, the GIN with it — `mid-dialogue-gate.md`.)*

**Reputation: model-emitted delta.** Haiku emits a delta by default; client override wins; per-NPC
sensitivity scalar; hard clamp on a defined scale; injected from a scene-start snapshot.

**Test suite scope: structural-only.** Assertions on memory IDs, row types, and structure — never on
generated prose. Judged evals (drift-toward-identity, Bartlett-style distortion) belong to the eval
story / paper ablations, not the suite.

**Read-mode boundary: self-describing three-state.** Every payload carries `read_mode` and `pinned`.
Pin/unpin are endpoints; pinning freezes the current head; restoration is a correction verb, not
pin; unpinning resumes from the frozen head.

## Audit rulings

1. **Both correction verbs outrank pin; the new head inherits the pin.** Pin means exactly two
   things: decay exemption + reconstruction exclusion. (Final ruling — supersedes a stale earlier
   summary claiming pin blocks the diegetic verb. It does not.)
2. **Generalized cache-eviction invariant.** Cache writes happen only in the reconstruction path;
   any other writer to a chain — correction, diegetic write, purge — must evict all cache rows for
   that memory_id.
3. **Gate degradation ladder** (replaces a dead "gate parse failure" clause): embeddings down →
   entity-only lexical fetch off the GIN index ranked by recency × importance; no entities →
   novelty-only; both out → gate closed, serve the loaded set, fail-quiet. Which-signal-fired is
   logged per event; the entity gate's lookup table *is* the identity components table.
   *(2026-07-19 gate-spec freeze ruling: migration 003 moves the entities GIN to the live fact
   heads — the lexical fetch reads fact-head entities; `mid-dialogue-gate.md`.)*
4. **Within-scene text-stability invariant.** Absent a diegetic event on that memory, repeated reads
   within one scene return byte-identical text. Constrains any future async fallback. *(Amended
   2026-07-17: authorial correction added as the second sanctioned text-change cause — see the
   "Authorial-correction spec scope rulings" entry.)*
5. **`typology_source` is a distinct field from provenance** (`lived | injected`).
6. **Write-time facts vs runtime state.** Facts populate day one; runtime state rides with its
   mechanism. The `write_cause` enum
   (`original | reconstruction | rationalization | update_with_resentment | authorial_correction`)
   lives on detail rows; the drift anchor is derivable from it.

## Tension log (summary)

Four early tensions were closed by, respectively, the gate design, the turn-topology decision, the
prompt-caching policy, and the schema-now stance. One tension (does stored importance go stale as
the telling drifts?) was **deliberately disregarded**, rationale documented under write-time facts
vs runtime state in `architecture.md`. One tension was resolved as a documentation obligation
rather than a code change. One tension (how can the suite test correction behavior before the
dissonance mechanism exists?) was closed by **verb-forked structural test pairs keyed on
`write_cause`** — no fixture mode; the diegetic half of each pair lands when the dissonance
mechanism ships.

## Decay & gist session — 2026-07-12 (latest word; refines the migration spec)

Gist = span pointer into immutable observation text. Identity components table with canonical +
aliases + category. NLP write pass with loose LLM escalation (importance threshold / ambiguous
entity hit / novel entity — novel entities grow the table). VADER-class lexicon affect at write.
`tau_effective` decay on details only, down to fully hidden; gist never decays. Cross-observation
coreference misses accepted. Coreference via fastcoref or coreferee. Reflection-time component trim
silently invalidates caches. A spam gate on novel-entity growth is deferred.

*(Superseded in part 2026-07-13 by the write-path build rulings below: escalation grew from the
three triggers sketched here to five; coreference settled on fastcoref; affect settled on VADER +
Warriner 2013 VAD.)*

## Authorial-correction ruling — 2026-07-12

**Replace model adopted.** Authorial correction writes a corrected head row
(`write_cause = authorial_correction`) that supersedes the drifted chain and becomes the new drift
anchor; the memory_id stays in retrieval candidates, serving corrected content. **Rejected:**
erase-model (invalidate everything, re-ingest the fix as a new memory) — it would have left the
`authorial_correction` enum value and the authorial re-anchor branch dead.

Consequences propagated: the one-live-head index in migration 01 is confirmed compatible; the Set A
authorial assertions in `test-suite.md` now assert presence-with-corrected-head instead of absence;
no voided-marker column on prior rows — the new head's `write_cause` is the sole verb discriminator
(revisit only if the debug view ever needs retracted-vs-past-telling rendering).

## Schema-gap rulings — 2026-07-12

A doc-auditor sweep found three schema-now omissions where `architecture.md` described a mechanism
the schema doc (`migration-01.md`) never gave a home. Jack ruled:

1. **`scoring_failed` is a day-one column on `memories`.** `boolean NOT NULL default false`; set true
   when the importance-scoring model fails and the write lands with neutral importance (architecture
   §2, `test-suite.md` degradation case). It is a write-time fact — omitting it would force exactly
   the later migration **Schema now, mechanism later** exists to prevent.
2. **The diegetic "correction record" lives in a separate `corrections` table**, added to migration
   01 as schema only (the dissonance mechanism that writes it lands post-August). Columns:
   `correction_id`, `memory_id` → memories, `detail_id` → memory_details (the new head), `verb`
   CHECK in `{rationalization, update_with_resentment}` (the diegetic subset of the `write_cause`
   enum), nullable `source_event` jsonb, and bi-temporal `created_at`/`valid_at`. Chosen over
   folding it onto the head detail row so the confrontation reference and target have an explicit
   home. Backs the Set A diegetic pair's "correction record present" assertion.
3. **The `identity_components` pruning `[SETTLE-AT-BUILD]` tag is removed** — already answered by the
   non-destructive invariant (never DELETE except purge) and the decay/gist decision (component trim
   silently invalidates caches). The body text was already correct; only the confirm-tag was stale.

**Drift-anchor wording (standing phrasing):** the re-anchoring line above ("authorial → the
corrected original") reads, correctly and consistently with `architecture.md` §7, as **authorial →
the corrected head (the `authorial_correction` row)**. Same row under the derivable-anchor
definition; this entry fixes the phrasing without editing the append-only original.

## Local DB + MCP infra — 2026-07-13

The migration-01 database floor is a **committed `docker-compose.yml`** (not a bare `docker run`):
`pgvector/pgvector:pg16` as container `longmem-pg`, named volume `longmem-pgdata`, host port 5432.
All credentials interpolate from the gitignored `.env`, the single source for `DATABASE_URI`
(superuser `postgres`, db `longmem`). One full-access connection string; the Postgres MCP enforces
read-only itself via `--access-mode=restricted`, registered at **local scope** so no secret is
committed. Rationale: compose is reproducible, holds no secrets, and becomes the seam migration 02+
and the app pool reuse. pgvector 0.8.5 confirmed available; `CREATE EXTENSION` is deferred to
migration 01, not this floor.

**Runbook deviation (recorded so a rebuild reproduces it):** `postgres-mcp` → `pglast==7.2` has no
wheel for Python 3.14 and fails to build from source on Windows (no C toolchain). The MCP therefore
runs in an isolated **uv-managed Python 3.13** tool venv (`uv tool install postgres-mcp --python
3.13`). This does not touch the project's Python 3.14 stack constant — the MCP is a standalone
server process, never imported by project code. `mcp-setup.md` §1 should gain a one-line note to
this effect until `pglast` ships a 3.14 wheel (flagged to Jack; not yet applied).

## Migration 01 build — fork rulings & schema deltas — 2026-07-13

Migration 01 built and floor-verifier-passed against the live `longmem` DB. Jack ruled the seven
`[SETTLE-AT-BUILD]` forks from `migration-01.md` (status.md had said "six"; the doc carried seven):

1. **`agents.diagnosticity_goal` = `text`.** The Haiku importance prompt consumes prose.
2. **`memories.decay_class` = free-text label + config map.** The label→`tau_base` map lives in
   `agents.config`. **New column `memories.decay_class_unknown boolean NOT NULL default false`** — a
   write-time degradation flag mirroring `scoring_failed`: on an unrecognized decay-class label the
   write lands with a default class and this flag set, never rejected. Validation is write-path
   (deferred). This column was not in the original migration-01 spec; it is a consequence of the
   ruling and is now built.
3. **`memories.affect` = three columns:** `affect_valence real`, `affect_arousal real`,
   `affect_detail jsonb` (all nullable), fed by the VADER-class write pass. Richer than the suggested
   valence+jsonb default.
4. **Gist spans = child table** `memory_gist_spans` (not an int-range array on `memories`) — backs
   the suite's per-row gist-immutability assertions.
5. **`reflections.identity_relevant` = `boolean`.**
6. **HNSW distance op = cosine** (`vector_cosine_ops`), for `text-embedding-3-small`.
7. **Migration runner = Python** (`db\migrate.py`) with a `schema_migrations` bookkeeping table.
   **Atomic apply-and-record:** each migration's DDL and its ledger row commit in one transaction, so
   a half-applied migration can never be logged complete. Idempotency rides on the ledger (a second
   run is a no-op); DDL also carries `IF NOT EXISTS` as defense-in-depth.

**Schema strengthening beyond the doc's literal column lists (recorded for transparency).** Owner
foreign keys (`memories.agent_id`, `identity_components.agent_id`, `memory_gist_spans.memory_id`,
`memory_details.memory_id`, `corrections.memory_id`/`detail_id`, `reflections.agent_id`) and gist
offsets (`start_char`/`end_char`) are **NOT NULL** — a row cannot exist without its owner, nor a span
without its offsets. `valid_at` is NOT NULL per the bi-temporal invariant; `invalid_at` nullable. Per
*nothing-hardcoded*, `reputation`, `rigidity`, `reputation_sensitivity`, `diagnosticity_goal`,
`decay_class`, and `config` carry **no column default** — the write path supplies them from
integrator config (reputation → the config scale's neutral point at agent creation).

**Dependency management (backend's first Python dep).** Ruled **global Python 3.14** install (matches
the stack constant) plus a repo-root **`requirements.txt`** manifest, pinning `psycopg[binary]==3.3.4`
(a `cp314` Windows wheel exists — unlike `pglast`, no isolation was forced). The Postgres MCP keeps
its separate uv/3.13 venv.

**Infra note (flagged, not yet fixed).** The `floor-verifier` subagent could not call the `postgres`
MCP tools despite its `mcpServers: postgres` frontmatter; it verified against the same live container
via `psql` instead. Verification is sound, but the MCP-preference directive isn't yet effective for
that subagent — worth revisiting before the write-path build. *(Resolved 2026-07-13 — the fix was the
`tools` allowlist, not `mcpServers`; recorded in `status.md`.)*

## Write-path spec scope rulings — 2026-07-13

Authoring `write-path.md` (the write path & ingestion API v1 build target) required three scope
rulings; Jack ruled:

1. **Surface = one ingest service, two thin callers.** The write path is a single ingest service that
   is **the sole instrumentation seam**; the CLI harness calls it in-process and a thin FastAPI route
   wraps it — neither duplicates the seam. Its return is a **structured `IngestResult` (memory IDs +
   computed scores/facts, not just prose)**, extending the read-path "IDs + scores in every payload"
   invariant to writes so the CLI debug view and the scenario suite both assert on structure. The
   FastAPI route is a pass-through: for one ingest, its JSON is exactly the service's `IngestResult`.

2. **v1 event set = observe + scene-boundary + pin/unpin.** The observe pipeline (NLP → single Haiku
   call → embedding → atomic insert) is the meat. Scene-boundary is **accepted + instrumented only**
   in v1 — its three consumers (prompt-head rebuild, identity recompile, reputation snapshot) are
   deferred and it needs **no new schema**. Pin/unpin toggle `memories.pinned`. Diegetic-correction
   and purge are written into the contract but their handlers are **deferred** (out of v1 scope).

3. **Models = provider interfaces with real + deterministic fake.** The Haiku
   render/importance/typology call and the OpenAI 1536-d embedding are each behind a
   per-role-env-var provider interface with **both** a real implementation (drives the demo) and a
   **deterministic fake** (so the structural suite / CI run offline, keyless, and never assert on
   prose).

The spec tags the remaining physical shapes `[SETTLE-AT-BUILD]` (NLP stack, LLM-escalation
thresholds, idempotency — constrained to no-new-schema, embedding-failure degradation, wire shape)
and surfaces open flags (scene-boundary needs no migration-02; the render seam — raw
`observation_text` vs. rendered `original` detail content; VADER lacks an arousal axis). These are
ruled at the write path's build, not now.

## Write-path build — fork rulings & build notes — 2026-07-13

Write path v1 built and floor-verifier-passed (verification on scratch DB `longmem_test`; product
`longmem` confirmed untouched). Jack ruled the four majors up front; the minor shapes were approved
with the build plan.

1. **Render seam — confirmed as specced.** Raw client text → `memories.observation_text`
   (immutable); the Haiku render → the `original` detail head's `content`; gist spans point into
   `observation_text`. On write-call failure the head falls back to the raw observation text
   (never a lost write).
2. **Embedding failure → the write lands with a NULL embedding.** `embedding IS NULL` is the
   queryable degradation signal (frozen schema allows no flag column); mirrored in the payload as
   `IngestResult.embedding_failed` — a payload-only extension of the spec's field list, added so
   the degradation is assertable without a DB peek. Memory stays reachable via the entity/GIN
   path; vector backfill is future work. *(2026-07-19 gate-spec freeze: that reachability moves
   to the fact-head partial GIN at migration 003 — `mid-dialogue-gate.md`.)*
3. **NLP stack: spaCy `en_core_web_lg` + fastcoref + VADER + Warriner 2013 VAD lexicon.**
   - **License gate outcome:** NRC-VAD **rejected** — non-commercial-research-only, incompatible
     with the planned Apache-2.0 flip. The pre-ruled fallback **Warriner et al. 2013** is CC-BY
     4.0 (per its NoRaRe database entry) and is bundled, slimmed to Word/V/A/D columns, at
     `data\lexicons\warriner_2013_vad.csv` with `ATTRIBUTION.md`.
   - Affect: VADER compound → `affect_valence`; Warriner lemma-lookup means (1–9 normalized to
     0–1) → `affect_arousal`; **dominance lives in `affect_detail` jsonb** (frozen schema has no
     dominance column) alongside the raw VADER + Warriner breakdowns. Arousal is therefore
     populated in v1 — the spec's open flag is closed.
   - **Environment facts (recorded so a rebuild reproduces them):** fastcoref 2.1.6 is
     incompatible with transformers 5.x at runtime → `requirements.txt` pins `transformers<5`
     (4.57.6 verified). fastcoref internally requires `en_core_web_sm` (its tokenizer), installed
     alongside `en_core_web_lg`. spaCy model downloads must use the pip wheel URLs pinned in
     `requirements.txt`, NOT `spacy download` — spaCy's downloader shells out to uv on this
     machine (installed for the Postgres MCP) and dies outside a venv. psycopg async cannot run
     on Windows' ProactorEventLoop → the API runs via `python -m app.serve` (SelectorEventLoop
     runner), never bare `uvicorn app.api:app`; the walker passes `loop_factory` to
     `asyncio.run`.
   - Coref/NER confidence: fastcoref's public predict API exposes no per-span probability and
     `en_core_web_lg`'s greedy NER exposes none either, so v1 treats every coref-derived identity
     span as low-confidence — over-calls only (biased loose), never suppresses.
4. **LLM escalation: full in v1, gist correctness over speed/cost.** Separate provider + its own
   env var (`LONGMEM_MODEL_ESCALATION`). Five triggers, any one fires (all integrator-tunable via
   `agents.config`, defaults in `app\config.py::SERVICE_DEFAULTS`): (1) importance ≥ 0.45;
   (2) identity/category hit with |valence| ≥ 0.5; (3) any novel entity; (4) unresolved
   pronoun/noun-chunk co-occurring with an identity/category hit; (5) low NLP confidence on an
   already-flagged span. `escalated_by` + escalation token counts recorded per write in
   `IngestResult.instrumentation` (feeds the per-100-turn cost table).
   **Failure path — BUILD-PHASE STANCE, MUST BE RE-RULED BEFORE THE DEMO PUBLISHES:** retry once,
   then HARD-STOP the write (fail-loud; nothing inserted — escalation precedes the insert, so a
   client resend is safe pre-idempotency). This is deliberately not a production posture; the
   production/demo failure behavior for escalation is an **open decision** owed before the demo
   video ships.
   *(Superseded 2026-07-22 — see "Escalation failure-path + pre-warm + R7 rulings" and
   "Escalation soft-degrade build". The hard-stop is RETIRED: a double failure now proceeds with
   the base NLP-pass gist and sets `memories.escalation_failed` (migration 005);
   `EscalationHardStopError` and its 502 are gone. The owed open decision is CLOSED. Annotation
   added 2026-07-28 — the register's own convention had not been applied here.)*
   *(Trigger set grown 2026-07-23 — see "Escalation trigger tuning": a sixth trigger,
   `thin_gist`, fires when the base pass yields fewer gist spans than
   `escalation_min_base_spans`. The five above stand unchanged.)*
5. **Minor shapes (approved with the plan):** wire shape `POST /v1/events/observe`,
   `POST /v1/events/scene-boundary`, `PUT /v1/memories/{memory_id}/pin`; idempotency stays
   accept-not-enforce (spec default; needs schema); `phase_tag` and `event_id` are accepted but
   have no schema home in v1 (not stored, not echoed); per-role env vars retained with a loud
   startup check that the three write-call roles (importance/render/typology) name the same model
   (one call serves all three in v1); provider selection `LONGMEM_PROVIDER_MODE = real | fake`
   (fake = offline default); process env vars override same-named `.env` keys (lets verification
   target the scratch DB without touching `.env`); verification runs on a scratch DB
   `longmem_test` created/dropped around the walker via the new `db\migrate.py --database-uri`
   flag (floor re-verified: no-arg run on `longmem` still a clean no-op); no agent-creation
   endpoint in v1 — fixtures insert agents via SQL.
   *(Superseded 2026-07-27 — `POST /v1/agents` shipped with unity-client stage 0; provisioning is
   a real verb and fixtures no longer need hand-SQL. Annotation added 2026-07-28.)*

## Re-slating ruling — reconstruction moves pre-demo — 2026-07-14

A full pre-demo/post-demo scope audit (requested by Jack mid-session, aborting a read-path spec
attempt whose tentative scoping answers were discarded unrecorded) found that the demo as slated
demonstrated the immutable record — storage, decay, correction-override, gate-recollect — but not
the thesis: the reconstruction mechanism sat post-August, so every demo read would have been
`read_mode = verbatim`, no drift would exist, and the 60-day drift plot beat was explicitly
contingent ("when reconstruction ships"). Jack ruled:

1. **The reconstruction mechanism ships before the August demo.** In scope: identity-conditioned
   reconstruction as the mandatory read path past theta; the write-back version chain
   (`write_cause = reconstruction`); the `(memory_id × identity_version)` cache *[key refined at
   spec time — see the 2026-07-17 entry: the version component composes `identity_version` with a
   scene-frozen decay band]*; the drift budget
   with re-anchoring; batched serving with pre-warm and the block-with-"reconstructing"-signal
   miss path; a reconstruction model role (`LONGMEM_MODEL_RECONSTRUCTION`) behind a provider
   interface with a real implementation + a deterministic fake; the Set C suite scenarios.
   Rationale: the demo video is the introduction artifact and must demonstrate the claim axis —
   controlled infidelity above an immutable record — not just the record. The prior deferral
   traced to the deadline, and the standing rule is that the deadline never drives a decision.
   **Ruled with the schedule cost explicitly flagged:** pulling the largest mechanism into the
   August window may cost demo beats or the date; Jack accepted that trade. **Supersedes in
   part** the *Schema now, mechanism later* primary decision (its reconstruction clause only —
   the schema-now stance and the dissonance/reflection deferrals stand).
2. **Authorial-correction endpoint → pre-demo**, its own small build target after reconstruction
   lands. The correction-override demo beat and the Set A authorial pair require it, and it
   interacts with reconstruction (cache eviction, drift re-anchoring), so it builds on that floor.
3. **Scene-boundary consumers split:** the reputation snapshot lands with the dialogue turn
   (architecture §9's August single-call ship injects it); identity-document
   recompile-at-scene-edge lands with reconstruction (cache keying needs `identity_version`; the
   pre-demo document is **seed-prose-only**, rendered + content-hashed, since reflection stays
   deferred); **prompt-head rebuild / prompt caching → post-August** (no demo beat names it;
   revisit only if demo latency demands).
4. **Purge → post-August**, explicitly before the public flip (integrator surface; no demo beat).
5. **Reflection's "if not landed in August" hedge is resolved: explicitly post-August.**

Consequences propagated: `status.md` immediate queue re-slated (read path → CLI harness →
reconstruction → authorial correction → gate → suite session → Unity/demo); the post-August ledger
loses its reconstruction items and gains purge and prompt caching explicitly; the demo
choreography's 60-day drift plot is a planned beat, no longer contingent; `architecture.md` §2 and
§7 deferral markers updated. Docs only — no code changed with this ruling.

## Read-path spec scope rulings — 2026-07-14

Authoring `read-path.md` (the dialogue-init retrieval v1 build target) required two scope rulings.
The surface itself was already fixed by the re-slating ruling above: **retrieval-only** — one
retrieval service seam with a thin pass-through FastAPI route, mirroring the write-path surface
ruling; the Sonnet dialogue call rides with the CLI harness (immediate-queue item 2). Jack ruled:

1. **Query input = text + reserved context.** `query_text` is required and embedded **as-is** as
   the relevance probe — the integrator authors it (opening utterance or scene blurb).
   `location_name` / `entities[]` / `event_time` are accepted and shape-validated but **not
   consumed and not echoed** in v1 — reserved slots for the post-August encoding-context term,
   mirroring three of the four write-side context stamps (the phase_tag/event_id
   accept-now-consume-later precedent). **Affect is deliberately not reserved** (ruled same day,
   on a doc-auditor finding that the slot mirror was overstated): a query-side affect field's
   shape — and whose affect it would carry — is undesigned; it gets its shape with the
   encoding-context term rather than as a guessed slot, and the spec states the exclusion
   explicitly. **Rejected:** server-side composition of context into the
   probe — it would bake context into the relevance term and double-count it once the real
   encoding-context term ships (a separate weighted term is the committed design), and the
   composition template would be a hidden hardcoded authorial artifact colliding with
   nothing-hardcoded. The demo makes context matter by writing it into `query_text` explicitly —
   same effect, visible in the debug view.
2. **v1 serving = verbatim-only.** Retrieval (candidates + scoring) is specced as a separate stage
   from serving (text assembly + read-mode stamping). v1 serves the live `memory_details` head
   verbatim with `read_mode = "verbatim"` on every item — honest self-description; the three-state
   boundary collapses to one state because no reconstructor exists yet. The decay math is built
   now and surfaces as the **recency score component**, so Set B asserts decay-vs-invalidation
   distinctness through scores. The theta check, cache reads, and `reconstructed` read_mode land
   with reconstruction (immediate-queue item 3), which **swaps the serving stage only** —
   retrieval and scoring are untouched by that swap, and reconstruction's pre-warm hooks this same
   dialogue-init seam.

The spec consolidates the retrieval scoring function from the artifact queue
(relevance × recency(decay class) × importance_norm; pin exemption → recency = 1.0; reserved slots
for the context term and per-call `weight_overrides`) and tags the remaining physical shapes
`[SETTLE-AT-BUILD]` (wire shape, distance→similarity mapping + over-fetch, recency knobs +
shared-`tau_effective` confirmation, importance_norm method, k default, `as_of` override,
`weight_overrides` shape, empty/short-store behavior, query-embedding-failure fallback — suggested
fail-quiet recency × importance ranking with a `degraded` flag, the read analog of
never-lose-a-write). These are ruled at the read path's build, not now.

## Read-path build rulings — 2026-07-14

Every `[SETTLE-AT-BUILD]` shape in `read-path.md` was reported with the build plan and ruled by Jack
before being built. Two genuine forks plus one build-surfaced conflict were ruled explicitly; the
remaining shapes were approved with the plan (the write-path precedent). All knobs below are
service defaults in `app\config.py`, per-agent overridable via `agents.config` (`agent_knob`).

1. **`as_of` override — ADOPTED as specced.** Optional tz-aware timestamp on `DialogueInitRequest`;
   defaults to server now (UTC); echoed in instrumentation as `as_of_effective`. Consequence
   propagated: `tests\CLAUDE.md`'s time-travel line now names both mechanics (injected `valid_at`
   + `as_of`).
2. **Query-embedding failure — FAIL-QUIET fallback** (the spec's suggested ladder row): rank ALL
   live candidates (NULL-embedding rows included) by `recency × importance_norm`;
   `degraded = true` + reason in instrumentation. Sub-shape ruled with it: the per-item
   `relevance` component is **null** on this path — honest self-description, none was computed
   (the field is `float | None`). Never-blank-a-dialogue, the read analog of never-lose-a-write.
   **Rejected:** fail-loud — a dead embedding provider would silence every NPC.
3. **`importance_norm` = clamp + floor, superseding the spec's min-max suggestion.**
   `importance_norm = clamp(importance_raw, importance_norm_floor, 1.0)`, floor default **0.05**.
   Ruled on a conflict surfaced at build: min-max bounds over the agent's live rows would let
   invalidating an extreme row move *other* items' scores, breaking the spec's own Set B principle
   ("invalidation excludes rows without touching other items' scores"). `importance_raw` is
   already contractually 0..1 from the write call, so read-time normalization is honestly a
   floor + clamp, and the invalidation principle now holds exactly, for every row. Tradeoff
   accepted: a compressed importance distribution is not stretched to full [0,1]. NULL
   `importance_raw` (fixture-only; the write path never stores it) takes the `importance_neutral`
   knob before clamping.
4. **Wire shape:** `POST /v1/dialogue/init`, `response_model = RetrievalResult`, route
   pass-through; unknown agent → 404 (mirrors the write path). Models in `app\schemas.py`;
   reconstruction's pre-warm hooks this endpoint at item 3.
5. **Relevance mapping + SQL shape:** `relevance = clamp(1 − cosine_distance, 0, 1)`; over-fetch
   `max(k, ceil(retrieval_overfetch_factor × k))` candidates by `<=>` over live rows with
   non-NULL embeddings joined to the live detail head, re-ranked in Python by the full score.
   Knob `retrieval_overfetch_factor` default **4.0**.
6. **Recency knobs:** shared `tau_effective` **CONFIRMED** — one formula, one implementation
   (`app\decay.py`), which the reconstruction theta check imports at item 3. Knob
   `decay_k_importance` default **1.0** (named for the shared decay math, not retrieval-only).
   `age = as_of − valid_at`, clamped at ≥ 0 so a future-dated `valid_at` caps at recency 1.0.
   Label → tau resolution mirrors the write path's rule (stored label if mapped → the agent's
   default class → new knob `tau_fallback_seconds`, default **604800** — a read never fails on a
   resolvable row).
7. **k default:** knob `retrieval_top_k` = **8**; resolution order request `k` (≥ 1) →
   `agents.config` → service default; the effective value surfaces as `k_effective`.
8. **`weight_overrides` reserved shape:** optional `{relevance?, recency?, importance?}` float
   multipliers; shape-validated, not consumed, not echoed (as suggested).
9. **Empty/short store:** 0..k items, never an error — a valid young-NPC state (as suggested);
   `candidate_count` in instrumentation.

Approved with the plan, cross-cutting: component normalization as suggested (each component in
[0,1], product in [0,1], no further rescaling), and a determinism shape — final ordering
`(−score, memory_id)` so ties are stable and within-scene byte-identity holds across identical
calls.

## CLI-harness spec scope rulings — 2026-07-14

Authoring `cli-harness.md` (the CLI harness & synthetic load driver v1 build target — the remaining
piece of the vertical slice, *retrieved memories → dialogue out*, consolidating architecture §9 + §11
over the frozen schema) required two scope rulings. The surface was already fixed by prior rulings:
the harness composes the two built seams (ingest, retrieval) in-process and adds the single Sonnet
call; the reputation-snapshot scene-boundary consumer lands here per the 2026-07-14 re-slating. Jack
ruled:

1. **Reputation delta = persist in-place.** The single Sonnet call emits a per-turn
   `reputation_delta`; the harness applies
   `clamp(reputation_prev + reputation_sensitivity × delta, scale_min, scale_max)` and **UPDATEs
   `agents.reputation` in place** (a client-supplied delta override wins over the model's delta, per
   §9). The scene-start snapshot is read at the scene boundary and frozen into the prompt prefix for
   that scene; mid-scene deltas accumulate on the row but the injected snapshot does not change until
   the next boundary (freezing is a property of the seam contract — scene state lives in the caller,
   which passes the snapshot in and refreshes it only at a boundary). **Invariant note:** this is an
   in-place **UPDATE** of an agent-row *runtime scalar* — the same class of operation as the existing
   pin-flag toggle (`set_pinned` flips `memories.pinned` in place, shipped write-path v1), and
   likewise **outside** the memory-content non-destructive invariant (which governs `memories` /
   `memory_details` content; never DELETE except purge). Reputation is runtime state, not stored
   memory content (architecture §9: "a scalar on the NPC row"; the migration-01 schema gave it a
   single mutable column with no default, not a version chain). The `CLAUDE.md` invariant clarification for
   the reputation scalar rides with the *build* (when the UPDATE lands), not the spec. **Rejected:**
   compute-and-return-only (mirroring write-v1's accept-and-instrument scene-boundary) — it would
   leave the reputation-drift demo beat inoperative and the scene-start snapshot static; and
   non-destructive reputation history — it needs new schema this spec forbids (the frozen migration-01
   schema stands). The scale neutral/min/max and the sensitivity default remain integrator config
   (`agents.config` / `SERVICE_DEFAULTS`), never hardcoded.

2. **Drive surface = interactive REPL over a shared session-runner core.** The CLI is a
   human-drivable console (typed utterances + meta-commands) with a `--debug` view exposing retrieved
   memory IDs + scores, the parsed structured output (prose / action directive / reputation delta),
   and token + latency counts — the product surface whose "main file reads as documentation"
   (`status.md`). A **session-runner core beneath it is reused by the synthetic load driver**, which
   drives scripted sessions at volume through the same seams to emit §11's latency histogram and
   per-100-turn cost table. **Rejected:** scripted-transcript-replay-only (no hand-drivable product
   surface for the demo) and interactive-REPL-only with a separate load-driver script (the two paths
   would drift apart — architecture §11 makes the driver first-class, "no distribution exists without
   it").

**Reconciliation baked into the spec (a doc tension, not a new fork).** §9 reads both "August ship: a
single Sonnet-class call" and "the Haiku call emits a delta by default." The 2026-07-14 re-slating
governs the slice: the reputation snapshot injection lands with "architecture §9's August
**single-call** ship," so the **one Sonnet call** carries prose + action directive + reputation delta
together; the "Haiku call" wording describes the *post-August split-brain* behavior call. The spec
states this explicitly so no one wires a second Haiku behavior call into the vertical slice.

The spec tags the remaining physical shapes `[SETTLE-AT-BUILD]` (the `LONGMEM_MODEL_DIALOGUE` env-var
name; the dialogue structured-output schema + parse/validation; the reputation apply shape — scale
bounds/neutral/sensitivity defaults + config keys; the action-directive vocabulary source; the
prompt-assembly block shape; the never-blank fallback line; the CLI meta-command surface + entry
point + `--debug` rendering; the load-driver script format + scale knobs + aggregate output; whether
the turn payloads are Pydantic models or dataclasses). These are ruled at the harness's build, not
now. The dialogue call is a new model role behind a provider interface with a real implementation + a
deterministic fake, following the write-path triad; every retrieved memory is served **verbatim** (no
reconstruction in the slice).

## CLI-harness build rulings — 2026-07-15

*[Count correction, 2026-07-16 audit: the spec carried **ten** settle-tags (the nine-item list plus
the `reputation_snapshot`-plumbing tag inline in the request contract), and "cost units" was a
plan-raised choice implicit in the instrumentation contract, not a spec tag — so the tallies below
("nine shapes", "two genuine forks" among them) miscount; the itemized rulings themselves are the
authoritative, complete record: one spec tag ruled via explicit question (action-vocabulary
source), nine spec tags approved with the plan, plus the cost-units question.]*

The harness build (spec: `cli-harness.md`) settled the nine `[SETTLE-AT-BUILD]` shapes. Jack ruled
the two genuine forks via explicit questions at plan approval; the remaining shapes were approved
with the plan. Floor-verified the same day (structural walker `tests\verify_cli_harness.py`,
36 assertions; both prior walkers re-run clean; `longmem` pristine via the postgres MCP — **the
floor-verifier's `mcp__postgres__*` tools worked this dispatch**, resolving the 2026-07-14 flag for
this dispatch).

1. **Action-vocabulary source = per-call field → `agents.config` fallback (ruled).** A per-call
   `action_vocabulary` on `DialogueTurnRequest` wins when supplied; else
   `agents.config["action_vocabulary"]`; when neither exists, every emitted directive is dropped
   (`directive_dropped`, reason `"no vocabulary configured"`) and the turn succeeds. **No hardcoded
   default vocabulary** (nothing integrator-configurable is hardcoded). Vocabulary shape: a JSON
   array of directive `type` strings; `params` rides as a free object, unvalidated (architecture §9:
   "free type + params"). **Rejected:** config-only (no per-call variation without a config write)
   and per-call-required (boilerplate in every caller; a missing field becomes a hard error).

2. **Per-turn cost units = tokens always; USD only when priced via env (ruled).** Cost fields carry
   token counts unconditionally. USD populates only when the optional `LONGMEM_PRICE_*` env vars are
   set (USD per Mtok: `DIALOGUE_IN/OUT`, `WRITE_IN/OUT`, `ESCALATION_IN/OUT`, `EMBEDDING`); otherwise
   USD fields are null and the load-driver table reads "(unpriced)". **No model pricing is ever
   hardcoded.** **Rejected:** hardcoded price defaults (volatile vendor data in code; pricing is not
   per-agent config) and tokens-only (loses the demo's per-100-turn dollar figure).

Approved-with-plan shapes, as built:

- **Env var** — `LONGMEM_MODEL_DIALOGUE`, alongside the four existing roles in `app\config.py`;
  required in real mode; `Settings.model_dialogue`.
- **Structured output** — JSON-in-text per the write/escalation precedent: ONLY
  `{"prose": str, "directive": {"type": str, "params": object} | null, "reputation_delta": float}`.
  Parse policy: prose is required — no parseable prose → `MalformedOutputError` (token spend still
  accounted) → the seam serves the fallback line, `degraded = true`. Below prose the parse is
  field-wise (the ladder's salvage row): a malformed directive drops with `directive_dropped` +
  reason; a missing/non-numeric delta zeroes with `reputation_delta_source = "zeroed"`. Vocabulary
  validation of a well-formed directive happens at the seam, not the provider.
- **Reputation apply** — one atomic SQL statement (`app\db.py apply_reputation_delta`):
  `reputation = GREATEST(min, LEAST(max, COALESCE(reputation, neutral) + sensitivity × delta))`
  with `FOR UPDATE` old-value capture, `RETURNING (prev, after)` — the clamp lives in SQL so the
  scalar can never leave the scale even under concurrent turns. New `SERVICE_DEFAULTS` keys
  (per-agent overridable, the `agent_knob` pattern): `reputation_scale_min = -1.0`,
  `reputation_scale_max = 1.0`, `reputation_neutral = 0.0`, `reputation_sensitivity_default = 1.0`;
  the `agents.reputation_sensitivity` column wins over the knob when non-NULL. The result carries
  `reputation_delta_source` (`model | override | zeroed`) so override-wins and the degradation paths
  are structurally assertable.
- **Prompt assembly** — labeled blocks in spec order: `[identity]` (seed prose; omitted when NULL)
  → `[reputation]` (frozen snapshot + scale bounds) → `[memories]` (rank order, one line per item,
  memory_id carried) → `[output]` (the JSON contract + the turn's vocabulary; a no-vocabulary turn
  instructs `directive: null`). User message = the raw utterance. Identical inputs assemble
  byte-identical prompts; exposed as `assemble_system_prompt` so the walker asserts block order and
  byte-stability without a model call.
- **Never-blank fallback** — `DIALOGUE_FALLBACK_LINE = "..."` (a neutral beat), module constant in
  `app\dialogue.py`, overridable per agent via `agents.config["dialogue_fallback_line"]` (the
  `TYPOLOGY_FALLBACK` precedent).
- **Snapshot plumbing** — `reputation_snapshot` is a **required request field**, not a session
  handle: scene state lives in the caller (`app\session.py` freezes it; refreshes only at
  `scene()`), making "frozen within a scene" a seam-contract property the walker asserts directly.
- **CLI surface** — `python -m app.cli --agent <uuid> [--debug]` (`app\cli.py`, written to read as
  documentation). Meta-commands: `:observe`, `:scene [type]`, `:pin`/`:unpin <memory_id>`,
  `:as-of <iso8601|clear>`, `:debug [on|off]`, `:help`, `:quit`; anything else is an utterance.
  Debug rendering is a pure function (`render_debug`) over the payload so the suite can assert it.
- **Load driver** — `python -m app.load_driver --sessions N --turns M [--script p.json] [--seed S]
  [--agent <uuid>] [--database-uri <uri>] [--json out.json]` (`app\load_driver.py`), reusing
  `SessionRunner`. Script = JSON list of sessions, each a list of
  `{"kind": "observe" | "utterance" | "scene", ...}` events; omitted, a seeded deterministic
  generator supplies the mix (the generator passes its own vocabulary — callers own vocabulary).
  Emits latency p50/p95 (retrieval SQL, query embed, first token, dialogue total, turn total — no
  gate term) + the itemized per-100-turn token/USD table. Without `--agent` it creates a driver
  agent in the target DB.
- **Wire models** — Pydantic in `app\schemas.py` (`DialogueTurnRequest` / `ActionDirective` /
  `DialogueTurnResult` / `DialogueTurnInstrumentation`, the latter nesting
  `RetrievalInstrumentation`), mirroring the write/read payloads for the eventual Unity route.

**Build-surfaced interpretation (noted, not separately asked):** a client
`reputation_delta_override`, being client-authoritative and independent of the model call, **still
applies on the degraded (never-blank) path** — the ladder's "zero reputation delta" describes the
no-override default. Flagged to Jack in the build report. *(Confirmed by Jack 2026-07-16 — see the
audit-rulings entry below.)*

**Environment learnings:** (1) Windows decodes piped stdin with the ANSI codepage, so a PowerShell
here-string pipe delivers its UTF-8 BOM as mojibake — the REPL reconfigures non-tty stdin to
`utf-8-sig` (interactive consoles untouched). (2) `Providers.dialogue` carries a
`FakeDialogueProvider` default so pre-harness `Providers(...)` constructions (the write/read
walkers) stand unchanged. (3) `RealDialogueProvider` streams (the anthropic SDK `messages.stream`)
so first-token latency is measurable; the fake reports 0.0.

## Full-project audit rulings — 2026-07-16

A three-lane audit (doc-auditor full-tree sweep + code-vs-rulings review + operational checks) ran
the day after the CLI-harness build. Code and operations came back clean; the doc sweep found six
findings, all in the 2026-07-15 wrap-up prose. Jack ruled:

1. **Mechanical doc fixes applied (five findings).** The missed reconstruction renumber ref in
   `read-path.md` §Serving boundary ("Item 3" → "Item 1"); the `write-path.md` scene-boundary
   consumer note annotated with the 2026-07-15 landing (caller-side in the session-runner; the
   handler itself still writes nothing); the settle-shape count correction annotated onto the
   2026-07-15 entry above (the register's annotation convention — no ruling was rewritten); the
   CLAUDE.md invariant carve-out rewording ("the two runtime scalars" — `memories.pinned` is a
   memory-row flag, not an agent-row scalar); and the status.md known-nit sentence corrected to
   name all four stale-comment files.

2. **Override-on-degraded-path CONFIRMED.** The 2026-07-15 build-surfaced interpretation stands as
   built: a client `reputation_delta_override` is client-authoritative and applies even when the
   dialogue call fails (the never-blank path); the degradation ladder's "zero reputation delta"
   describes the no-override default. The flag is closed; no code change.

3. **Stale queue-number code comments fixed, floors re-verified.** The four comments citing
   reconstruction as "item 3" (`app\api.py`, `app\decay.py`, `app\retrieval.py`, `app\schemas.py`)
   were corrected to item 1 — comment-only changes to floor-verified files, so all three structural
   walkers were re-run on fresh scratch databases: 35/35, 34/34, 36/36, `db\migrate.py` no-arg
   still a clean no-op, scratch dropped.

Audit observations recorded without a ruling (carry as-is): `httpx` is imported directly by two
walkers but rides transitively (unpinned in `requirements.txt`); `max_tokens=1024` is hardcoded in
the three real providers (a write-path-era pattern — arguably provider implementation detail, not
integrator config); the suite-gate Stop hook stays dormant by design until `test_*.py` files land
with the pytest suite (immediate-queue item 4).

## Reconstruction spec scope rulings — 2026-07-17

Authoring `reconstruction.md` (the reconstruction v1 build target — immediate-queue item 1,
pre-demo since the 2026-07-14 re-slating; consolidates architecture §7 + §4.2/§4.3/§6 over the
frozen migration-01 schema, attaching to the read path's reserved serving stage) required three
scope rulings. Jack ruled via explicit questions:

1. **Reconstructor input = the prior head is included.** The reconstruction call sees the full
   gist spans (fixed constraint, verbatim from `observation_text`) + the time-thinned original
   detail slice + **the current live head as "how you currently tell it,"** conditioned on the
   rendered identity document. Rationale: retellings compound (the Talk-of-the-Town
   repetition-breeds-commitment precedent that motivated write-back; the Bartlett drift dynamic),
   and the drift budget gets real work — without the prior telling in the prompt, candidates stay
   near the anchor and the refuse-write threshold rarely binds. **Rejected:** original-only (the
   literal §7 reading — each reconstruction independent of the last, tellings recorded but never
   compounding) and prior-head-as-the-detail-source (gist/detail offsets exist only for
   `observation_text`; reconstructed text has no span structure to thin against §4.2's
   definition).

2. **Pre-demo drift driver = a decay band composed into the cache key.** Spec-surfaced tension:
   the identity document is seed-prose-only pre-demo, so `identity_version` is static and the
   ruled `(memory_id × identity_version)` cache would reconstruct each memory exactly **once** —
   the 60-day drift plot beat would be a single step, then flat until reflection ships
   post-August. Ruled: the cache key's version component **composes `identity_version` with a
   quantized thinning band** (the decayed detail strength, bucketed by an integrator quantum knob)
   — no schema change, the column is text. Deeper decay crosses a band edge → new key →
   re-reconstruction on thinner detail → a progressive drift trajectory under a static identity.
   The band is **frozen per scene** (caller-frozen scene state, with theta and the thinning level
   computed at the same scene basis) so within-scene byte-identity holds by construction, and the
   band **both keys the cache and sets the thinning level** so same-key ⇒ byte-identical text
   holds across scenes. Consequence: Set C's "stable identity ⇒ cache hit" refines to "stable
   identity **+ same band** ⇒ cache hit" (`test-suite.md` updated). **Rejected:**
   accept-single-step (faithful to the key as written, but the demo's drift beat loses its
   trajectory) and retell-per-scene (evict/bypass at scene edges — contradicts Set C's
   stable-identity⇒hit as written and multiplies reconstruction call volume).

3. **Identity-document plumbing = hybrid, reputation-style.** The scene-boundary handler
   recompiles **server-side** (render seed prose verbatim → content hash → upsert
   `identity_documents`) and **returns `identity_version`** in its response; the caller freezes it
   as scene state and passes it on each read request — exactly the ruled `reputation_snapshot`
   contract, making "frozen within a scene" a seam-contract property. Lazy bootstrap when no
   boundary has fired (a bare read ensures a current document and flags it); a request naming an
   unknown version is a loud contract error. This is the scene-boundary handler's **first real
   server-side consumer** (the 2026-07-14 slating's identity-recompile landing). **Rejected:**
   fully server-side (retrieval reads the latest document row per call — the effective version
   can shift mid-scene, making stability an implementation accident) and fully caller-side (every
   future client, Unity included, would reimplement rendering + hashing, and the server would no
   longer own the version its cache is keyed on).

The spec restates the settled mechanics by pointer (batched pre-warm serving,
block-with-signal deferred to the gate, the eviction invariant, the derivable drift anchor +
re-anchoring rules, `LONGMEM_MODEL_RECONSTRUCTION` behind the provider triad) and adds two derived
design lines: **serve only persisted text** (a model response that failed to persist is never
served — unpersisted text breaks within-scene stability on the next read) and **the dialogue-init
route becomes a writing endpoint** (write-back on read is §7's design; read-path v1's read-only
SQL was a scope fact of verbatim-only serving, not a principle). Remaining physical shapes are
tagged `[SETTLE-AT-BUILD]` (theta knob, band quantum + key composition, thinning function, prompt
+ batched output schema, retry policy, drift metric + threshold default, write-back `valid_at`,
refusal caching, scene-state request fields, scene-boundary response shape, hash algorithm /
NULL-seed / unknown-version shapes, wire-model + instrumentation deltas, walker shape). These are
ruled at reconstruction's build, not now. Docs only — no code, no floors changed.

## Reconstruction build rulings — 2026-07-17

Reconstruction v1 built and floor-verifier-passed the same day (structural walker
`tests\verify_reconstruction.py`, 41 assertions; all three prior walkers re-run clean on fresh
scratch — 35/35, 34/34, 36/36; `longmem` confirmed pristine via the postgres MCP, whose tools
worked this dispatch). Jack ruled the two genuine forks via explicit questions at plan approval;
the spec's remaining settle-shapes were approved with the plan.

1. **Fake-mode drift = locality-sensitive fake embedding (ruled, explicit question).**
   `FakeEmbeddingProvider` was rewritten from shake_256 hash vectors to **lowercased character
   trigrams hashed into the 1536 buckets, L2-normalized** — still deterministic, offline, keyless,
   but similar texts now get similar vectors, so fake-mode retrieval relevance and reconstruction
   drift distances are meaningful. Build-surfaced fork: the hash fake made ANY two texts nearly
   orthogonal (~1.0 cosine distance), so every fake-mode reconstruction would have been refused at
   any sane threshold — offline dev, the load driver, and the walker happy path would never
   exercise write-back at default knobs. **Rejected:** keep-orthogonal (drift observable only in
   real mode) and a provider-mode-conditional drift check (violates the cli-harness principle that
   the service is identical under either provider). Empirically: an echo-style retelling lands
   ~0.04 from its anchor; unrelated text ~1.0.
2. **`drift_budget_threshold` default = 0.35 (ruled, explicit question).** Cosine distance,
   per-agent overridable (`agents.config`, the `agent_knob` pattern; migration 01 slotted the
   drift threshold there from day one). Paraphrase-level retellings (~0.05–0.25 on real
   embeddings) pass; candidates that left the event's semantic neighborhood refuse. **Rejected:**
   0.25 (crystallizes early — flattens the 60-day beat) and 0.5 (the budget becomes a backstop
   only).

Approved-with-plan shapes, as built: knobs `reconstruction_theta` **0.5** /
`reconstruction_band_quantum` **0.25** (band = `floor((1−strength)/quantum)` capped at the last
band; thinning level = the band's midpoint strength; composed key `{identity_version}|b{index}`
in the cache's existing text column); deterministic dependency-free thinning
(sentence-split on `(?<=[.!?])\s+`, per-segment prefix retention `ceil(level × n)`, min 1 — no
spaCy on the read path); batched JSON-in-text call (system = optional `[identity]` block +
`[task]`; user = a JSON list of `{memory_id, gist, detail, current_telling}` sorted by memory_id;
response = ONLY a JSON object memory_id → retelling; per-item salvage; pure
`assemble_reconstruction_prompt`); single attempt, fail-quiet; drift check embeds candidate +
anchor **at check time** in one batched embed call (chain rows have no embedding column;
`memories.embedding` embeds the observation, not the render); write-back supersedes and inserts
**at the scene basis** (prior head `invalid_at` = new head `valid_at` = basis — a coherent chain
timeline under `as_of` time travel, and the precedent the authorial endpoint inherits); refusal
caches the served prior text under the current key; scene-state request fields
`identity_version` + `scene_started_at` (both optional; absent → basis falls back to
`as_of_effective` and the identity document lazy-bootstraps, flagged); unknown version →
`UnknownIdentityVersionError` → **422** at the route; `SceneResult` gains `identity_version` +
`identity_document_new` (additive defaults); sha256 full hex; NULL seed renders the empty string
(hashed) with the identity block omitted; `RealReconstructionProvider` max_tokens
`min(1024 × batch, 8192)` (batch-safe variant of the provider-internal 1024 pattern);
`read_mode` literal widens to `verbatim | reconstructed` (`reconstruction_pending` stays
unadopted); instrumentation deltas all defaulted (`reconstruction_ms` / input / output /
embed tokens, `cache_hits/misses`, `write_backs`, `drift_refusals`,
`identity_version_effective`, `identity_bootstrapped`); load-driver aggregates gain the
reconstruction latency + cost rows (drift-check embeds ride the embedding price); walker
`tests\verify_reconstruction.py` on the scratch pattern.

**Build-surfaced shapes (flagged for Jack's confirmation, built as follows):** *[All confirmed
as built/written 2026-07-17 — see "Reconstruction flagged-shapes confirmations" below.]*

- **Prior walkers pin `reconstruction_theta = 0.0` in their fixture agent configs** (one config
  key + comment each; assertion bodies untouched — verified by the floor-verifier against git).
  Their fixtures age past the default theta, so without the pin the swap would change what they
  serve; theta = 0 knob-disables the stage per agent, so they still assert the v1 serving
  contract byte-for-byte — which doubles as proof the swap is transparent when disabled. The
  swapped behavior is the new walker's floor.
- **Blind-check refusals are not cached:** a drift-check **embedding failure** refuses the
  write-back (fail-closed) but does NOT cache the served prior text — a transient embedding
  outage never permanently pins a key. True over-threshold refusals do cache, as ruled.
- **Cache-hit `detail_id` corner (documented):** after backwards time travel a cached telling can
  predate the current live head; the cache row is still served (same key ⇒ byte-identical text),
  `detail_id` identifies the live chain head, `content` the key's telling.
- **Pin-after-reconstruction read_mode (floor-verifier observation, spec-compliant):** a memory
  reconstructed in an earlier scene and pinned afterward serves its `reconstruction`-cause head
  as `read_mode = "verbatim"` — the spec's "pinned → verbatim, always" wins as written; noted as
  the one spot where read-mode names the pin rule rather than the served row's cause.

**Environment deviation found during verification (operational, not a ruling — needs Jack):**
`.env`'s `DATABASE_URI` now names a database `longmem_sandbox` that does not exist on the server
(the server has `longmem`, intact and pristine, and `postgres` only) — an operator-side edit some
time after the 2026-07-16 audit. Consequence: `python db\migrate.py` **no-arg** fails to connect;
the schema-frozen criterion was verified the equivalent way (`--database-uri` with the path
swapped to `/longmem` → "Up to date, 0 pending"). `.env` was not modified; whether to point it
back at `longmem` or create the sandbox DB is Jack's call. *[Resolved same day: Jack pointed the
URI back at `longmem`; no-arg `db\migrate.py` re-verified as a clean no-op — see the status.md
wrap-up entry.]*

## Reconstruction flagged-shapes confirmations — 2026-07-17

A dedicated confirmation session: Jack walked the three open reconstruction flags (the two
build-surfaced shapes plus the floor-verifier observation from the 2026-07-17 build-rulings
entry) and ruled on each. All three **confirmed as built/written — no code, no spec, no walker
changes.** The escalation hard-stop failure-path re-rule is now the sole open question.

1. **Prior-walker theta pin — CONFIRMED as built.** `tests\verify_read_path.py` and
   `tests\verify_cli_harness.py` keep `reconstruction_theta = 0.0` in their fixture agent
   configs. Ruled after a correction of understanding, recorded because the register keeps the
   why: Jack initially read the pin as "reconstruction is dormant in v1" and provisionally ruled
   rewrite-the-walkers + activate-the-knob; on review, reconstruction is **already
   production-active** (default `reconstruction_theta = 0.5` in `app\config.py`, per-agent
   overridable; the 0.0 pin exists only in the two older walkers' fixture NPCs), proven live at
   the 2026-07-17 verification (REPL drift beat with a real write-back and cache hit), and
   reconstruction owns its own dedicated 41-assertion walker. With that corrected, confirmed as
   built: staged-verification layer isolation — each walker guards one layer so a failure has a
   single cause, and the pinned pair doubles as proof the serving swap is transparent when
   knob-disabled. **Rejected:** rewriting the old walkers to run under default theta (duplicates
   `tests\verify_reconstruction.py`'s coverage, touches floor-verified assertion bodies, re-opens
   the read-path and CLI-harness floors, and blurs failure attribution).
2. **Blind-check refusals not cached — CONFIRMED as built.** A drift-check **embedding failure**
   (a blind check — no distance computable) refuses the write-back fail-closed but does NOT
   cache the served prior text (`app\reconstruction.py`), so a transient embedding outage never
   permanently pins a key — the next read retries. True over-threshold refusals cache, as ruled
   at build. **Rejected:** uniform refusal caching (an outage would pin the served text under
   that key until the identity version or decay band moved).
3. **Pin-after-reconstruction read_mode — CONFIRMED, keep as written.** Ruled after a requested
   review of pin mechanics (pins are integrator-designated only, via the observe event's flag or
   `PUT /v1/memories/{id}/pin`; §8: pin freezes the *current* head — restoration is a correction
   verb, not pin). A memory reconstructed in an earlier scene and pinned afterward serves its
   `reconstruction`-cause head as `read_mode = "verbatim"` — §6's "pinned → verbatim, always"
   holds as written: "verbatim" is the serving-stage claim (served exactly as stored, stage not
   applied, frozen from here on), and `pinned` rides alongside `read_mode` in every payload, so
   consumers retain ground truth. Floor-verifier observation closed; no spec amendment.
   **Rejected:** relabeling pinned drifted heads via `_head_mode` (a §6 amendment plus a
   serving-stage change re-opening the reconstruction floor, for a label carrying no information
   the `pinned` flag doesn't already carry).

## Scope-limiter reframing — 2026-07-17

Ruled by Jack after he flagged a standing bias in brainstorm/spec sessions: rules written as
verification discipline had hardened into design pressure — correct-but-larger options arrived
pre-labeled "blocked", "deferred", or "would re-open a floor". Surfaced live in the
authorial-correction spec session (paused mid-forks; its four scope forks are owed a fair
re-presentation under this ruling). A full sweep of every instruction surface (CLAUDE.md,
docs\, tests\CLAUDE.md, .claude\ commands and agents) found four limiter families. Four standing
changes, applied to the living rule surfaces (CLAUDE.md, status.md, architecture.md §2/§10,
.claude\commands\build-task.md); built specs, prior register entries, and session logs stand as
history:

1. **The schema freeze is retired as a standing rule.** The schema evolves by numbered
   migration: when the correct design needs a column, table, or index, the target adds
   migration `NNN` via the `db\migrate.py` ledger (built for exactly this since 2026-07-13),
   updates the schema docs, and the floor re-verifies (migrate idempotency + walkers). "No new
   migration" may appear in a spec only as a per-target scope fact Jack explicitly ruled — never
   as an inherited default. (The freeze was never tooling; it was a per-target scope fact in
   `write-path.md` that three later specs inherited as law.) What stays locked on its own
   grounds: the 1536 embedding dimension and the non-destructive invariants. The freeze's
   recorded casualties — the idempotency/dedup column, the scene-boundary schema home, the
   reputation-history schema objection, VAD dominance in jsonb, the location-description
   column — become *eligible* for re-opening; each is its own future ruling when a target
   touches it, and none is re-opened by this entry.
2. **Sequencing, not veto.** `status.md`'s "Post-August ledger" is renamed **"Sequenced-later
   ledger (pull-forward eligible)"** with the standing rule: any sequenced item may be pulled
   into the immediate queue by a dated ruling when a current target shows it is architecturally
   load-bearing — the 2026-07-14 reconstruction re-slating is the template. Sequencing orders
   work; it never rules an option out of a design discussion. The "revisit only if demo latency
   demands" phrasing (prompt caching) is struck for "revisit when a target needs it or demo
   latency demands" — the old wording forbade revisiting for correctness reasons. The dated
   deferral rulings themselves stand; this entry changes what they mean going forward.
3. **Floors are re-openable.** Re-running walkers + the floor-verifier is the normal cost of a
   design improvement, never an argument against one; options must state re-verification as the
   step it is, not as a design cost. (Staged verification itself is untouched — it is what makes
   this rule safe.)
4. **Reports carry the correct option.** The stop-and-report contract (CLAUDE.md working
   discipline; `/build-task` Phase 2) now requires the architecturally correct option to appear
   in every report even when it exceeds the task's scope, with its real cost stated — "bigger
   than this task" is a sequencing note, never a rejection reason.

Kept deliberately: "the August deadline never drives a decision" (+ `status.md`'s deadline
framing), staged verification and the verifier/auditor agents, the invariants block, and
`tests\CLAUDE.md`'s structural-only discipline — the reframe makes these enforceable rather
than replacing them.

## Authorial-correction spec scope rulings — 2026-07-17

Authoring `authorial-correction.md` (the authorial-correction endpoint build target —
immediate-queue item 1, slated pre-demo by the 2026-07-14 re-slating) required four scope
rulings. **The first spec session run under the same-day scope-limiter reframing:** the forks
were presented twice — the pre-reframing presentation was paused by Jack (it became the trigger
for that ruling); the re-presentation priced the larger options fairly, and one recommendation
flipped as a direct result.

1. **Scope = chain content now; fact-level correction slated as its own target (explicit
   questions, two rulings).** This target writes the corrected telling head only. The honest
   gap it leaves — retrieval still ranks a corrected memory by the original observation's
   embedding, and gist spans still index the original text — is closed by a slated
   **fact-level correction target** (versioned memories-row facts + corrected embedding so
   retrieval follows the fix; migration-002-class design with its own spec pass). Slating
   position ruled by a second explicit question: **immediate queue, item 2, ahead of the
   gate** — closing the operator's wrong-data story outranks demo-queue focus. **Rejected:**
   full fact correction inside this target (the fact-versioning mechanism deserves its own
   design pass, not a rider); chain-only with no slated follow-up (leaves the
   retrieval-on-wrong-semantics gap unowned).
2. **The reconstructor's fixed constraint follows the drift anchor (the flipped
   recommendation).** On a chain whose derivable anchor is an `authorial_correction` head, the
   corrected head — not the stale observation gist — is the fixed constraint: one notion of
   ground truth per chain, with constraint and drift anchor deriving from the same
   `write_cause` rule. Original-anchored chains are unchanged; the `update_with_resentment`
   mapping is decided with the dissonance path. Deliberately re-opens the reconstruction floor
   at build (anchor-cause-aware `assemble_reconstruction_prompt` + walker updates +
   re-verification) — priced as the step it is. **Rejected:** drift-budget-defends
   (reconstruction untouched): the constraint and the anchor would disagree about ground truth,
   and every gist-contradicting reconstruction would burn a model call just to be refused. *(The
   pre-reframing recommendation had been drift-budget-defends, leaning on "re-opens the floor"
   as a deterrent — recorded here as the reframing entry intends.)*
3. **Surface = memory-scoped operator verb** (the `set_pin` pattern; suggested
   `POST /v1/memories/{memory_id}/correction`, exact shape `[SETTLE-AT-BUILD]`), plus a REPL
   `:correct` meta-command so the correction-override demo beat is drivable pre-Unity.
   `/v1/events/*` stays diegetic-only. **Rejected:** an `/v1/events/correction` event — it
   blurs operator tooling into the in-world namespace, and the future diegetic-correction event
   would sit beside a differently-shaped sibling.
4. **Immediate mid-scene effect + invariant amendment.** Eviction + supersession serve the
   corrected chain on the very next read, mid-scene included. The within-scene stability
   invariant's wording gains authorial correction as the **second sanctioned text-change
   cause** (amended in CLAUDE.md, architecture §7, and `test-suite.md` Set C). **Rejected:**
   defer-to-scene-boundary — fairly priced post-reframing (a migration could house the pending
   state) and rejected on the merits: it keeps wrong data serving longer to protect the
   character from a change the operator explicitly chose.

Consequences propagated: `authorial-correction.md` written (design lines: no model calls —
operator text byte-verbatim *[superseded in part 2026-07-18: at the fact-level build the verb
gains one embed call — see the fact-level entry below]*; no `corrections` row — diegetic-only
by CHECK; one supersede-guarded transaction with cache eviction; fail-loud operator surface;
remaining physical shapes `[SETTLE-AT-BUILD]`); the invariant wording amended in CLAUDE.md + architecture
§7 + `test-suite.md` Set C; architecture §7's reconstructor-input line and §8's authorial
bullet annotated; Set A's authorial pair gains the constraint-follows-anchor and
mid-scene-immediacy assertions; the immediate queue renumbered (fact correction → 2, gate → 3,
suite → 4, Unity → 5, pre-ship gates → 6) with stale gate/suite refs updated in `read-path.md`,
`cli-harness.md`, `reconstruction.md`. Docs only — no code, no floors changed.

## Authorial-correction build rulings — 2026-07-18

Authorial-correction v1 built and floor-verifier-passed the same day (structural walker
`tests\verify_authorial_correction.py`, 31 assertions; all four prior walkers re-run clean on
fresh scratch — 42/42 with the reconstruction walker grown by one corrected-item assertion
(addition only), 36/36, 34/34, 35/35; `longmem` confirmed pristine via the postgres MCP). Jack
ruled one criterion via an explicit question at a mid-build stop-and-report; the spec's
remaining settle-shapes were approved with the plan.

1. **Done-when "time travel coherent" re-ruled to stored bi-temporal coherence (explicit
   question).** The spec's wording — "`as_of` before t_c serves the prior telling" —
   over-claimed: the candidate SQL joins the live head unconditionally
   (`d.invalid_at IS NULL`), and `as_of` is an **age-computation override** by the 2026-07-14
   read-path ruling; invalidation excluding rows in SQL is what Set B's decay-vs-invalidation
   separation asserts through. Ruled: the walker asserts the **stored** guarantee — chain
   stamps coherent around t_c (superseded `invalid_at` = corrected `valid_at` = t_c) and a
   windowed SQL query re-derives which telling was live at any instant, with no gap or overlap.
   **Rejected (presented fairly priced, not adopted, not slated):** as_of-windowed chain
   serving — the fuller bi-temporal read would rewrite the ruled `as_of` semantics, re-open the
   read-path floor, and require re-thinking the reconstruction cache for superseded heads; no
   ruling or demo beat asks for it (drift and correction-override both want current-state
   serving). If ever wanted, it is its own spec-first target.

Approved-with-plan shapes, as built: route `POST /v1/memories/{memory_id}/correction` (POST —
each call mints a chain row); `CorrectionRequest { content min_length 1, client_timestamp
required tz-aware (the ObserveEvent naming) → t_c, expected_detail_id optional }` /
`CorrectionResult { memory_id, detail_id, superseded_detail_id, evicted_cache_rows, total_ms }`
(the PinResult naming; no token fields — no model calls *[superseded in part 2026-07-18: the
fact-level build widens `CorrectionResult` and adds the one embed call — see the fact-level
entry below]*); whitespace-only content invalid
(pydantic `min_length` + a stripped check in the seam → 422); **concurrency = the spec's 409
suggestion refined to an opt-in compare-and-swap** — the supersede targets the live head by
predicate (race-safe under row locking; the one-live-head index the backstop), and a supplied
`expected_detail_id` that no longer names the live head → `CorrectionConflictError` → **409**
with the transaction rolled back (never a silent correction of a telling the operator did not
see), while an omitted CAS (the REPL default) corrects the current live head; corrected-chain
prompt shape per the pure `build_reconstruction_item` (anchor cause `authorial_correction` →
the corrected anchor text in the constraint slot, empty detail — nothing observation-derived
re-injected — `current_telling` kept, `_SYSTEM_TASK` and the JSON shape unchanged;
original-anchored chains byte-identical to the prior stage; `ReconstructionSource` gains
`anchor_cause`); CLI `:correct <memory_id> <text…>` with t_c = the session's effective time
(`as_of` under time travel); error mapping 404 / 409 / 422 / 5xx raw (fail-loud); walker
`tests\verify_authorial_correction.py` on the scratch pattern.

Environment learning (recorded for the next session): the repo `.env` now runs
`LONGMEM_PROVIDER_MODE=real`, so piped-REPL smokes must set
`$env:LONGMEM_PROVIDER_MODE = "fake"` alongside the scratch `DATABASE_URI` override.

## Fact-level correction spec scope rulings — 2026-07-18

Authoring `fact-level-correction.md` (the fact-level correction target — immediate-queue item 1,
slated by fork 1 of the 2026-07-17 authorial-correction rulings) required four scope rulings.
Presented twice at Jack's request: the technical presentation, then a plain-prose
re-introduction of all four (mechanism, issue, options); ruled on the re-presentation, each on
the recommended option. Premise corrections were surfaced during pricing and verified in code
before presenting: `entities` is **write-only today** (the read-request slot is RESERVED-inert;
its first consumer is the gate's GIN path, queue item 2); **gist re-derivation on corrected
chains would have zero consumers** (the corrected-anchor prompt branch ignores
`observation_text` and spans); **purge is a docs-only contract** (no handler exists). The
stored embedding's sole consumer is the `fetch_vector_candidates` probe — the direct target of
"retrieval follows the fix."

1. **Fact scope = embedding only.** The corrected text is re-embedded (one embedding-provider
   call); importance, typology, decay class, entities, and affect stand as write-time facts
   about the *event* — consistent with the deliberately-disregarded 2026-07-12 staleness
   tension. Honest deferral recorded: a fact-corrected memory carries its original entities
   until an additive fact-chain column rides with the gate target. *(Closed 2026-07-19 —
   migration 003 specced at the gate target, and the correction verb re-derives entities;
   `mid-dialogue-gate.md`.)* **Rejected:** +mechanical
   NLP pass (entities/affect feed nothing readable today; gist re-derivation consumer-less;
   spaCy latency on the operator verb); +Haiku re-score (a second model call; importance moves
   to the fact head, widening the candidate-SQL delta and re-opening read-path scoring
   assertions); operator per-field overrides (no model calls, but the same candidate-SQL
   widening for importance — re-openable later if operator authority over scalar facts is ever
   wanted).
2. **Version shape = a fact-version child table** (suggested `memory_fact_versions`; exact
   names `[SETTLE-AT-BUILD]`): chain rows under the stable `memory_id` — basis text, embedding,
   `write_cause`, bi-temporal stamps — with a one-live-head partial unique index and a partial
   HNSW; the `memory_details` precedent applied to the semantic basis, the non-destructive
   invariant untouched. Migration 002 creates + backfills one `original` row per existing
   memory. Read-path and write-path floors re-open at build — re-verification steps.
   **Rejected:** history table + in-place-updated live columns (candidate SQL and HNSW
   untouched, but "never UPDATE stored content in place" would narrow — an invariant rewording
   propagated through every rule doc, the weaker architecture); self-chaining the memories row
   (`memory_id` is simultaneously PK and the stable FK target of four tables and every wire
   payload — a new anchor ID for identical semantics).
3. **Surface = one combined verb.** `POST /v1/memories/{memory_id}/correction` becomes
   fact-following: the operator's corrected text is both the telling head (byte-verbatim, the
   v1 contract) and the embedded fact basis, one transaction, CAS and eviction inherited.
   Verified coupling drove this: a fact-only correction leaves an original-anchored chain whose
   reconstructor keeps re-injecting the corrected-away data from stale gist spans. **Rejected:**
   a separate fact verb (needs a second ground-truth rule keyed on fact-version state — two
   truths per chain, against the 2026-07-17 one-ground-truth-per-chain ruling — and re-opens
   the reconstruction floor); a scope field (inherits the same problem in facts-only mode,
   triples the behavior matrix).
4. **Embed failure = all-or-nothing, fail-loud.** Embed before the transaction opens (never
   hold a transaction across a network call — the reconstruction precedent); on provider
   failure nothing is written, loud 5xx-class error, operator retries. Honest price recorded:
   during an embedding outage, telling corrections are blocked too — v1 needed no model.
   **Rejected:** land-with-NULL-embedding (the memory vanishes from the vector probe — worse
   than stale — and needs a nonexistent retry verb); land-with-stale-embedding (retrieval keeps
   following the old semantics, the target's own problem statement).

Consequences propagated: `fact-level-correction.md` written (design lines: one model call
stated honestly — v1's "no model calls" purity superseded, not silently dropped; the existing
embedding role, no new model role or env var; the fact chain's `write_cause` vocabulary reuses
`original | authorial_correction`; **migration 002 is a fact of the target — the first spec for
which that is true**; remaining physical shapes `[SETTLE-AT-BUILD]`). CLAUDE.md's
non-destructive parenthetical grows the fact chain; architecture gains §4.4 + the §6 probe
marker + the §8 fact-following annotation + §12 purge prose ("its chains — telling and fact
versions"); `authorial-correction.md` annotated at five spots (fork 1 closed, no-model-calls
superseded-in-part, scope boundary, mechanism, instrumentation); `migration-01.md` 002 pointers
(embedding column, HNSW index, mechanics); `test-suite.md` Set A authorial pair grows the
fact-chain assertions + a new all-or-nothing degradation case. Docs only — no code, no floors
changed.

## Fact-level correction build rulings — 2026-07-18

Fact-level correction v1 built and floor-verifier-passed the same day as its spec (new
structural walker `tests\verify_fact_correction.py`, 32 assertions; all five prior walkers
re-run green on fresh scratch — 38/38 write (35 → 38), 36/36 read (34 → 36), 36/36 CLI harness
(untouched), 42/42 reconstruction (**untouched — the proof of the spec's no-reconstruction-delta
claim**; `app\retrieval.py` and `app\reconstruction.py` byte-identical to HEAD), 33/33 authorial
(31 → 33); `longmem` pristine via the postgres MCP; migration 002 applied to `longmem` with the
floor criterion now reading **"001 + 002 applied, 0 pending"**). Jack ruled two shapes via
explicit questions at plan approval; the remaining eight mechanical shapes were approved as
proposed.

1. **Dual-write vs freeze = FREEZE (explicit question, against the dual-write
   recommendation).** Observe no longer writes `memories.embedding` — the `original` fact head
   on `memory_fact_versions` is the sole vector home for post-002 rows. The recommendation had
   been dual-write (the 001 all-write-time-facts principle holding for every row); Jack chose
   one storage home, accepting the epoch split (pre-002 rows keep their column values — now
   also backfilled into the fact chain — post-002 rows carry NULL there forever). **Stated
   consequence, implemented with the ruling:** the queryable embed-degradation signal (ruled
   2026-07-13 as `memories.embedding IS NULL`) moves to the **live fact head**; the write-path
   walker's [14] signal assertion moved with it — the one non-additive walker change of this
   build, ruling-driven and recorded. Signal-home annotations propagated to architecture §2,
   `test-suite.md`, `write-path.md` §c, and the `app\schemas.py`/`app\ingest.py` docstrings.
2. **The old `memories_embedding_hnsw` index = DROPPED in 002 (explicit question, as
   recommended).** An index is derived structure, not stored content; after the probe moves it
   has zero readers. Reversal, if ever wanted, is one CREATE INDEX in a later migration.

Approved-with-plan shapes, as built: names `memory_fact_versions` / `fact_version_id` /
`basis_text` + index names per the spec sketch; `write_cause CHECK IN ('original',
'authorial_correction')` (column shape otherwise mirroring `memory_details`); **partial HNSW**
over live fact heads (`WHERE invalid_at IS NULL`, stated verbatim in the candidate SQL so the
planner matches); degraded-path `fetch_live_candidates` deliberately unjoined (no distance is
computed there; byte-identical to v1); backfill `INSERT…SELECT` with the `WHERE NOT EXISTS`
backstop before the indexes (the walker proves the guard by re-running the 002 file against a
legacy-shaped row); wire deltas `CorrectionResult += fact_version_id,
superseded_fact_version_id, embed_ms, embedding_tokens` and `IngestResult += fact_version_id`;
REPL `:correct` prints both head swaps + embed timing, and `CorrectionEmbedFailedError` prints
loudly (the hard-stop pattern); embed failure → **502** (the escalation-hard-stop route
precedent); the correction embeds **before** the transaction opens and a missing live fact head
inside it raises as a broken-store invariant (rollback, 5xx). A build-observed bonus recorded
by walker assertion: **correcting an embed-degraded memory re-embeds it** — the correction verb
is the sanctioned repair path for NULL-fact-embedding rows (closing the retry-verb gap the
rejected land-with-NULL option would have needed).

Verification also included a live piped REPL beat on scratch (fake mode): the `:correct` line
prints both head swaps, and the same chapel query's relevance moved 0.4686 → 0.5637 across the
correction — retrieval following the fix, visible in the debug view.

## Mid-dialogue gate spec scope rulings — 2026-07-19

Authoring `mid-dialogue-gate.md` (the mid-dialogue gate — immediate-queue item 1 since the
2026-07-18 fact-level build) required five scope rulings. Presentation mode, recorded per the
house convention: forks 1, 2, 4, and 5 were re-presented in plain prose at Jack's request
(fork 1 after distinguishing the loaded set from a per-turn top-k and detailing the
server-side option; fork 2 after a refresher on the two-chain split — retellings compound on
the telling chain while the fact chain is the ground-truth basis reconstructions never touch)
and ruled on the re-presentation, each on the recommended option; fork 3 was ruled on the
first presentation. **Fork 5's recommendation was reversed between presentations, recorded
honestly** (see below). Premises verified in code before presenting: the loaded set has **no
state home anywhere** (the session runner holds only scene-frozen scalars — no turn counter,
no last-retrieval, no history); retrieval fires **unconditionally on every turn**
(`app\dialogue.py`); `memories.entities` and its GIN index have **zero readers**; the
read-request `entities` slot is RESERVED-inert and is not the gate's input.

1. **Loaded-set home = caller-held scene state, reputation-style.** The session runner (Unity
   client in production) keeps loaded memory IDs as scene state — reset at scene boundaries,
   populated by the loader turn, appended on gate fetches — and passes them per request; the
   server fetches those rows by ID each turn (one keyed SQL on live fact heads) for the
   novelty basis, coverage check, and closed-gate serving. Absent fields ⇒ loader semantics ⇒
   v1 byte-parity. Third use of the ruled caller-freezes-scene-state contract (reputation
   snapshot 2026-07-15, `identity_version` 2026-07-17). **Rejected:** server-side scene state
   (a scene-state table invents a persistent scene object + a per-turn write + lifecycle
   questions in a no-DELETE store; an in-process cache breaks under the REPL-in-process +
   route-over-HTTP dual-caller topology and dies on restart); per-turn approximation (runs
   the probe to decide whether to run the probe; already-recalled entities re-fire on every
   mention; contradicts architecture §6).
2. **Migration 003 entities = FREEZE — the fact head is the sole entities home.** The 002
   embedding precedent applied to entities: `memory_fact_versions.entities` added; observe
   writes the fact head only; guarded backfill from `memories.entities` before the index;
   partial GIN over live fact heads; `memories_entities_gin` dropped; `memories.entities`
   frozen (the epoch split accepted, same as the embedding's). Decisive argument: the gate's
   coverage check and degraded fetch *read* entities — one home makes "corrections move
   entities" true everywhere they're read. **Sanctioned shape, explicitly:** the backfill is
   an UPDATE of a brand-new never-populated column on existing fact rows — schema-evolution
   backfill in the 002 spirit, not a content mutation. **Rejected:** dual-home (two homes
   drift; the gate would read the home corrections cannot move — the exact debt 003 closes).
3. **Correction entities = mechanical NLP pass + optional operator field.** The corrected
   fact head's entities mirror observe's merge exactly: spaCy NER over the corrected text +
   optional `CorrectionRequest.entities`, case-insensitive dedup; absent field ⇒ NER alone.
   Non-LLM. The fact-level fork-1 rejection of an NLP re-pass rested on "entities feed
   nothing readable today" — a premise this target ends; the price (the write path's NLP
   stack enters the correction path) restated and accepted. **Rejected:** NER-only (drops the
   client-supplied merge observe has); operator-field-only (fieldless corrections don't move
   entities); copy-forward-only (the deferral's stated purpose would defer again).
4. **Per-signal fire logs = instrumentation-only.** `signals_fired` rides the turn
   instrumentation (the write path's `escalated_by` precedent) + load-driver per-100-turn
   aggregates; the reserved novelty kill-switch decision reads run artifacts. Zero schema,
   zero per-turn DB writes; a persisted `gate_events` table stays pull-forward eligible if
   the kill-switch ruling later demands cross-session data. **Rejected:** persisted rows
   riding 003 (a write per gate evaluation — base rates need non-fire rows; purge-contract
   growth; more schema before any long-running real usage exists).
5. **Reconstructing signal = post-hoc response fields + a pre-serve callback.** The reply
   carries the pause info AND an optional in-process callback fires as a blocking mid-scene
   serve begins — the REPL prints `(reconstructing…)` during the wait; the queued Unity hook
   maps onto the same seam; no HTTP transport change. **Recommendation reversed at the
   plain-prose pass, recorded honestly:** fields-only had been recommended (it keeps
   `app\reconstruction.py` byte-untouched), but fields-only cannot show anything *during*
   the pause — it cannot deliver §7's "latency becomes characterization" intent, the
   signal's entire purpose. Price accepted: one defaulted parameter touches the serving
   path; the reconstruction floor re-opens at build and re-verifies — a step, not a cost.
   **Rejected:** fields-only (the during-the-wait effect is unreachable); SSE/streaming now
   (a new transport class before Unity, its only consumer, exists).

The **fruitless-retrieval damper** was deliberately not forked: its mechanism stays
`[SETTLE-AT-BUILD]` with a full suggested default in the spec, **flagged promotable** for a
ruling before the build if Jack wants it settled.

Consequences propagated: `mid-dialogue-gate.md` written (design lines: non-LLM with the one
embed reused as the probe — one embed per turn; the two identity structures kept distinct —
tripwire = live `identity_components`, coverage = post-003 fact-head entities via the keyed
fetch, degraded fetch = their partial GIN; the reserved read-request slots stay inert; loader
turn ungated with absent-fields
byte-parity; the loaded set append-only within a scene; caller-side reset — no fourth
scene-boundary server consumer; **migration 003 is a fact of the target — the second spec for
which that is true**; remaining physical shapes `[SETTLE-AT-BUILD]`). Architecture §6 specced
marker + ladder GIN-home annotation, §5 freeze annotation, §4.4 entities-now-follows
amendment note, §11 lands-with markers; audit ruling #3 GIN-home annotation + the 2026-07-18
fact-level fork-1 deferral-closure annotation (this register); `fact-level-correction.md`
closure annotations; `reconstruction.md` wire-shape-settled + no-gate-term annotations;
`write-path.md` entities-freeze + GIN-reachability annotations (+ this register's
context-stamps and write-path-ruling annotations); `read-path.md` + `cli-harness.md` specced
pointers; `authorial-correction.md`
`CorrectionRequest` optional-entities annotation; `migration-01.md` 003 pointers;
`test-suite.md` Set D + ladder-row pointer; CLAUDE.md deliberately unchanged (the
within-scene invariant needs no amendment — which memories surface was never under the
byte-identity guarantee). Docs only — no code, no floors changed.

## Mid-dialogue gate build rulings — 2026-07-19

Mid-dialogue gate v1 built and floor-verifier-passed the same day as its spec (new structural
walker `tests\verify_gate.py`, **51 assertions** — grown past the plan's ~34 estimate by
addition; all seven prior walkers re-run green, each on fresh scratch — 40/40 write (38 → 40,
the additive entities-freeze pair), 36/36 read (**byte-untouched — the loader-parity proof**),
36/36 CLI harness (fixture `gate_enabled` pin + one ok-label edit, assertion bodies untouched),
42/42 reconstruction (fixture pin only), 34/34 authorial (33 → 34 additive), 34/34
fact-correction (32 → 34 additive); migration 003 applied to `longmem`, no-arg migrate →
**"Up to date: 3 migration(s) applied, 0 pending"**; `longmem` pristine via the postgres MCP).
Jack ruled two shapes via explicit questions at plan approval; the remaining shapes were
approved with the plan.

1. **Damper = as suggested (explicit question; the spec's promotable flag closed).**
   Fruitless = a gate fetch appending zero new memory IDs; after
   `gate_damper_fruitless_max` (default 2) consecutive, the **novelty signal** is suppressed
   for the scene remainder; the entity tripwire stays live (near-ground-truth); a scene
   boundary resets streak and suppression; the streak is caller-held wire state
   (`gate_fruitless_streak`, the reputation_snapshot trust class). **Rejected:** suppressing
   both signals (silences the demo-legible near-ground-truth signal for economy); no damper
   in v1 (unlimited fruitless probes).
2. **Correction-path NER failure = clean loud error, nothing written (explicit question).**
   `CorrectionNlpFailedError` → 502 at the route, the embed-failure precedent's exact shape;
   the NER runs before the embed, before the transaction. **Rejected:** unwrapped 500 (a
   stack trace instead of guidance); degrade-with-copy-forward (silently violates
   "corrections move entities" — the freeze ruling's own target).

Approved-with-plan shapes, as built: knobs `gate_novelty_threshold` 0.5 / `gate_fetch_k` 3 /
`gate_damper_fruitless_max` 2 / **`gate_enabled` 1** (the fixture-pin shape — the
`reconstruction_theta = 0` precedent — doubling as the integrator kill-switch scaffold; the
reserved per-signal kill-switch may later grow its own knobs); signal constants
`"novelty"` / `"entity_tripwire"` + rungs `entity_only | novelty_only | closed` (the
`TRIGGER_*` precedent); `app\gate.py` as a PURE decision module (the decay.py precedent) with
retrieval owning all IO and `cosine_distance` imported from reconstruction (one
implementation); coverage semantics (component covered iff any term, canonical or alias,
case-insensitive, appears in any loaded fact-head's entities; **coverage-basis-absent ⇒
novelty_only**, never fire-on-every-mention; empty loaded set ⇒ trivially novel); timing
contract `gate_ms` = loaded/components fetch + evaluation, `sql_ms` = probe only (0.0 closed);
wire deltas (`loaded_memory_ids` + `gate_fruitless_streak` on both requests,
`RetrievedMemory.gate_fetched`, nested defaulted `GateInstrumentation`,
`CorrectionRequest.entities`, `CorrectionResult += entities, nlp_ms`); efficacy comparators
(`novelty_outscored` = top fetched score > min loaded score under the turn's probe;
`entity_covered` = any fetched fact-head's entities ∩ the uncovered terms); prompt sub-header
`"Recalled just now, mid-conversation:"` inside the single `[memories]` block, loaded items in
the caller's append-only order (payload order stays `(−score, memory_id)`); the callback as
function params only (never Pydantic fields), forwarded on gated turns, fired once before the
blocking retelling call; runner bookkeeping keyed on the server's `gate.evaluated`.

Accepted properties, recorded: the degraded GIN `&&` overlap is byte-exact against stored
entity strings (aliases never sit in entities arrays — the Python coverage check has no such
limit); gated payloads may exceed k (append-only, damper-bounded); fire-turn scores mix
Python cosine (loaded) with SQL `<=>` (fetched) — not under byte-identity;
`fetch_entity_candidates` has no LIMIT (Python-scored, the fetch_live_candidates precedent);
the damper streak is caller-trusted wire state.

Build-surfaced learnings, recorded honestly: (a) **pgvector rows need `.to_list()`** — a
selected `vector` column returns a `Vector` object, not an iterable (the first walker run
caught the loaded-set fetch failing quiet into the ladder's loader fallback — the fail-quiet
rung worked as designed while the bug hid behind it); (b) **fake-mode calibration
corrected**: under the trigram fake, ordinary distinct English prose lands ~0.45–0.75 cosine
distance (shared trigrams), not the estimated ~1.0 — echoes ~0.04, near-copies ~0.08; the 0.5
default STANDS (echoes/near-copies vs distinct prose separate cleanly), but guaranteed-novel
walker fixtures need trigram-rare wording chosen by measurement (the damper text's min
distance ≥ 0.73); the spec's calibration parenthetical and `app\config.py` comment were
corrected (comment-only). Verification also included the live piped REPL beat (loader turn →
mid-scene novelty fetch → both-signal fire with `fruitless=yes` → `:correct` →
**`(reconstructing…)` printed DURING the blocked turn**, `blocked=yes` — the
latency-becomes-characterization beat live, with the corrected fact basis also making the old
wording read as novel: retrieval-follows-the-fix visible in the gate's min-distance) and a
standalone load-driver run emitting `gate_check` p50/p95 + the gate block with real
fire/efficacy data.

## Test-suite build rulings — 2026-07-20

Structural pytest suite v1 built and floor-verifier-passed (immediate-queue item 1;
`docs\test-suite.md` was already the spec — no separate spec session). 38 scenarios in
`tests\test_*.py`: Sets A (authorial pair incl. the fact chain; the diegetic pair still lands
with the dissonance mechanism), B, C, D, + the degradation cases. `app\`, `db\`, and all
seven `verify_*.py` walkers byte-identical to HEAD — the eight floors stand by construction
(the verifier's recorded reasoning; re-running identical bytes proves nothing new). Jack
ruled three shapes via explicit questions at plan time; the remaining shapes were approved
with the plan.

1. **Stop-hook budget = fast subset (explicit question).** Scenarios that CALL the write
   pass at the service level (observe, or the correction verb with its NER merge) carry the
   pytest marker `nlp` — they trigger the lazy spaCy+fastcoref load (~75 s cold on this
   machine for the first call; the load, not the scenarios, dominates) — and
   `run-suite.ps1` now runs `python -m pytest tests -x -q -m "not nlp"` (31 scenarios,
   ~14 s). The FULL suite (38) runs on demand, at floor verification, and before any commit
   touching `app\`. **Rejected:** full suite at every turn-end (a multi-minute cold-start
   tax on every future session, docs-only ones included); measure-first-then-re-rule (the
   measurement happened at build anyway — cold 82 s / warm 30 s full, 14 s subset — and
   confirms the split).
2. **Postgres unreachable at the hook = skip cleanly, loud notice (explicit question).**
   A conftest session-fixture probe: unreachable ⇒ every DB-backed test SKIPS, a visible
   `STRUCTURAL SUITE SKIPPED: postgres unreachable` warning prints, exit code 0 — the
   hook's existing dormant-when-prerequisites-missing philosophy extended to the DB
   prerequisite. Pure no-DB scenarios still run. **Rejected:** go-red (docs-only sessions
   could not end a turn cleanly without Docker running).
3. **CI = CI-ready now, workflow later (explicit question).** The suite is one-command,
   offline, keyless (fake providers pinned in fixtures regardless of `.env`), deterministic
   (two consecutive full runs asserted), and scratch-DB self-managing; no `.github\`
   workflow this session — it lands as its own later item (natural home: the public-flip
   sprint). **Rejected:** workflow-this-session (an extra build-and-debug chunk — pgvector
   service container + ~2 GB model caching — on top of 38 scenarios). Until it lands,
   regressions are caught only on-machine; stated and accepted.

Approved-with-plan shapes, as built: runner = pytest 9.1.1 with NO pytest-asyncio — each
scenario is a sync `def` wrapping `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`
via `conftest.run_structural` (the walker idiom; the Windows psycopg constraint);
`requirements.txt` += `pytest==9.1.1`, `httpx==0.28.1` (the latter closing the 2026-07-16
unpinned-httpx audit observation — the suite is its fifth consumer); scratch DB =
**`longmem_suite`**, deliberately distinct from the walkers' `longmem_test` so a Stop-hook
run never collides with a walker loop (session fixture: DROP IF EXISTS → CREATE → migrate
001–003 by subprocess → tests → DROP; per-test TRUNCATE of product tables — fixture reset of
a disposable scratch store, outside the memory-content invariant exactly as the walkers'
DB drops are); unmarked scenarios seed at the db layer through the real
`db.insert_observation` (`InsertPlan` with explicit fixture facts + the pure fake embedding
— no NLP import path); per-set configs mirror the walker pins with production-vs-fixture
stated per key (Sets A/B: theta 0 + gate off; Set C: PRODUCTION theta, gate off; Set D:
PRODUCTION gate, theta 0); fixture texts reuse the walkers' measured trigram corpus;
`pytest.ini` registers the marker + `testpaths` + `-p no:cacheprovider` (no repo-tree
cache residue); the escalation hard-stop degradation test asserts the CURRENT build-phase
stance and says so in its docstring — the owed production re-rule changes exactly that test.

Measured at build (recorded for hook-budget honesty): full suite 82 s cold-cache /
~30 s warm; `-m "not nlp"` subset ~14 s; unreachable-skip ~3 s.

## Latency-fix + suite-concurrency rulings — 2026-07-20

Jack ordered a fake-mode latency/compute pass (offline profiling before any real-mode run),
then, on the findings, ruled: **apply the two identified pits' fixes and harden the suite
concurrency gap** ("go ahead and complete both (a) and (b)"). All measurement lived in the
scratchpad (harness + EXPLAIN ANALYZE + cProfile + a psycopg micro-benchmark); the fixes
touch three files and no floor's behavior — re-verified: full suite 38/38, all seven walkers
green (40/36/36/42/34/34/51), migrate a clean no-op, `longmem` pristine.

**Fake-mode caveat (why these are worth fixing before real mode):** fake providers make model
CALLS ~0, so the profiled costs are pure infrastructure/local-compute underneath the eventual
LLM round-trips — both pits are removable waste, not model latency.

1. **Pit #2 — the vector probe sent the query vector as a param TWICE (44 ms wire stall) →
   named param.** `fetch_vector_candidates` / `fetch_gate_candidates` (and, for the shared
   `_VECTOR_CANDIDATE_FROM` clause, `fetch_loaded_set` / `fetch_entity_candidates`) bound the
   1536-dim query vector with positional `%s` in both the SELECT-distance and ORDER-BY slots.
   Two ~6 KB params cross a segment boundary into a Windows-loopback Nagle/delayed-ACK stall:
   **server executes in ~1.3 ms (EXPLAIN ANALYZE, HNSW index used), client observed ~46 ms,
   flat across 100/1k/5k rows.** Micro-benchmark: positional-twice 44 ms, `binary`/`prepare`
   no effect, **named `%(qv)s` referenced twice → sent once on the wire → 1 ms.** Fix: those
   four queries bind by name (all-named per query; the HNSW `ORDER BY embedding <=> ...`
   expression is unchanged). Measured end-to-end: retrieval ~54 ms → ~5–10 ms; a gate fire
   ~55 ms → ~7 ms; a reconstruction cache-hit read 54 ms → 7.6 ms. **Rejected:** `TCP_NODELAY`
   alone (treats the symptom, still ships the vector twice); query rewrite to alias the
   distance in ORDER BY (breaks HNSW index use — pgvector needs the literal expression).

2. **Pit #1 — fastcoref re-fingerprints its dataset every observe (~90 ms) → tame the
   `datasets` fingerprint.** cProfile: ~90 ms of a ~136–194 ms write pass is `FCoref.predict`
   → `datasets.Dataset.map()` deriving a content fingerprint by dill-pickling the transform's
   closure, which reaches fastcoref's internal spaCy model (the `datasets` spaCy dill-reducer
   serializes the whole pipeline) — all to name a cache file never read. Lever measurements:
   `datasets.disable_caching()` alone ≈ no change (it doesn't skip fingerprint COMPUTATION);
   short-circuiting the fingerprint `Hasher.hash` → **136 ms → 48 ms (3×)**; batching amortizes
   (24 ms/text at 16) but observe is one-at-a-time. Fix (`app\nlp.py` `_tame_datasets_fingerprint`,
   called from the `_coref()` loader): `disable_caching()` + replace `Hasher.hash` with a
   constant. **Safe** because caching is off (constant fingerprints can't collide on a cache
   file) and the fingerprint otherwise only sets an ephemeral dataset's `_fingerprint`; coref
   OUTPUT is unchanged (the walkers' assertion surface — all seven still green). **Guarded:**
   wrapped so any `datasets`-internals drift is swallowed, leaving the slow-but-correct path —
   the worst case loses the optimization, never breaks a write. Measured end-to-end:
   write pass ~215 ms → ~63 ms. This is the one **library-internal monkeypatch** among the
   fixes — flagged as a version-fragility cost (benign failure mode), easy to revert.
   **Rejected:** `disable_caching()` alone (ineffective); a write-pass batching redesign
   (architectural, doesn't help single-observe latency — the demo's actual shape).

3. **Suite concurrency (b) — per-process scratch DB name.** The suite's session fixture
   DROP/CREATEs a fixed-name `longmem_suite`; the Stop hook fires a run at every turn-end, so
   rapid consecutive turns overlapped two runs and one's `DROP ... WITH (FORCE)` force-killed
   the other's live connections (`psycopg.errors.AdminShutdown` — a false-RED surfaced during
   the profiling turns). Fix (`tests\conftest.py`): `SUITE_DB = f"longmem_suite_{os.getpid()}"`
   so overlapping runs never share a DB. A hard-killed run leaks an empty `longmem_suite_<pid>`
   (dropped by the next same-pid run; never collides with a live run). **Rejected:** a global
   lockfile (serializes runs, slower, another failure mode); sweeping all `longmem_suite_*` at
   startup (would drop a concurrently-running suite's DB — reintroduces the collision).

Not fixed (secondary, recorded for later): connection-per-query churn (~5–10 `pool.connection()`
acquisitions per turn, plus one write-back transaction per aged memory) — minor next to the two
pits, a batching candidate. And a real-mode COST flag (not a latency pit): escalation fired on
24/40 observes (60%) with realistic prose — each is an extra LLM call in real mode; eyeball the
trigger thresholds before the real run.

## Research-adoption slate + encoding-context build rulings — 2026-07-20

**Context.** The research sweep (45 papers; consolidated in `docs\research\FINDINGS.md`, a
gitignored working folder) produced a prioritized shortlist. Jack ruled the adoption slate at
plan approval, then the encoding-context term (Target A) was built and floor-verified the same
session. Source papers per change are traced in `docs\research\CHANGES-FROM-RESEARCH.md`.

**Slate rulings (Jack, at plan approval — four explicit questions):**

1. **Slate scope = two build targets now, rest queued.** Target A: the encoding-context read
   term + a TARG-style gate-calibration utility. Target B: a hybrid lexical retrieval channel
   (migration 004). Each lands and floor-verifies separately. Queued as their own future
   sessions: the judged eval harness, graph/associative memory, recall-reinforced decay, and
   automatic conflict/staleness detection (see the status.md queue). **Rejected:** one-target
   minimal (leaves the cheap lexical win unbuilt); three-targets-incl-eval-harness (session
   too large for the one-floor-per-session discipline).
2. **Encoding-context source = client-supplied fields.** The reserved
   `DialogueInitRequest.location_name/entities/event_time` are consumed AS SUPPLIED — the game
   client knows the scene's place/cast/time. **Rejected:** RaMem-style LLM query decomposition
   (a new model role + per-turn call, and it would supersede the 2026-07-14
   query-embedded-as-is ruling, which stands).
3. **Eval harness (queued) = v1 includes LLM-judged categories** (judge model role + env var)
   alongside structural scenarios, with the honest constraint stated: judged signal is only
   meaningful in real provider mode. **Rejected:** structural-first-judge-later (Jack wants the
   judge surface designed in from v1).
4. **Recall-reinforced decay = its own later spec session.** It needs a migration plus a real
   ruling on what counts as "recall" (gate fetch? reconstruction serve? dialogue surface?) and
   careful handling against invariant #2 (decay ≠ invalidation) and within-scene byte-identity.
   **Rejected:** folding it into this slate.

**Encoding-context build shapes (approved with the plan; the walker + suite assert them):**

- **Soft multiplicative nudge:** `score ×= 1 + Σ w_i·match_i` over the components the request
  supplies — entity coverage (|query ∩ live-fact-head entities| / |query|, casefolded both
  sides; fact-head entities so the match follows correction, migration 003), event-time
  proximity (`exp(−|Δ|/context_time_scale_seconds)`), casefold location equality. Factor ≥ 1
  always: never a filter, never a penalty; NULL row fields contribute 0. Applies on loader,
  gated (loaded + fetched, same context), and degraded paths (the term is lexical/structural,
  not a vector dependency).
- **The parity contract:** a request with no context fields skips the term entirely — zero
  extra float ops, scoring byte-identical to v1 (the loader-parity precedent). Walker
  criterion [7] asserts the exact factors (×1.75 full match at default knobs, ×1.125 half
  entity coverage, ×1.0 bare row).
- **Knobs:** `context_weight_entities` / `context_weight_event_time` /
  `context_weight_location` (0.25 each) + `context_time_scale_seconds` (86400.0), all
  SERVICE_DEFAULTS, per-agent overridable. Conservative defaults; a build-level choice, not a
  ruling.
- **Instrumentation-level surfacing** (`context_active` + `context_components`): the scored
  tuple and the serving stage are deliberately untouched — `app\reconstruction.py` is
  byte-identical to HEAD (the fact-level build's no-delta precedent). Per-item factor
  visibility deferred until something needs it.
- **CandidateRow widening:** `_CANDIDATE_COLUMNS` + `CandidateRow` grew
  `event_time`/`location_name`/`fact_entities` (defaulted, before `distance`); every fetcher's
  positional construction moved with it; the degraded path's FROM gained a **LEFT JOIN** to
  live fact heads so a legacy-shaped row (no live fact head) stays reachable — the never-blank
  ruling outranks the join.
- **Caller surface:** `DialogueTurnRequest` gained the three passthrough fields (the k/as_of
  precedent); the session runner holds scene context (fourth application of the
  caller-holds-scene-state contract; scene boundary resets it); REPL `:context` meta-command
  (shlex-split key=value: loc/entities/time; quoted values carry spaces).
- **The one ruling-driven walker change:** read-path criterion [7] ("reserved fields inert")
  asserted the superseded contract and was re-scoped to the context contract; walker 36 → 42.
  `weight_overrides` stays reserved-inert, asserted as before. Suite 38 → 40 (Set B parity +
  exact factor; Set D gated-path factor with the gate decision proven untouched — context
  nudges scores, never opens or closes the gate).
- **TARG calibration = report-only** (`--gate-budget <rate>`): recommends the
  `gate_novelty_threshold` at the (1−rate) quantile of a run's novelty min-distance CDF;
  trivially-novel turns counted separately; reads the service default only (stated in the
  report); never writes a knob.

**Paper provenance (Target A):** RaMem (arXiv 2606.22844) — the mechanism; Position: Episodic
Memory (2502.06975) — context as a defining episodic property; TARG (2511.09803 §3.4) — the
budget-calibration recipe. Full trace: `docs\research\CHANGES-FROM-RESEARCH.md`.

## Hybrid lexical channel build rulings — 2026-07-20

**Context.** Target B of the research-adoption slate (scope ruled in the slate entry above).
Built & floor-verified the same session as Target A. Mechanism sources: the lexical/semantic
complementarity finding (Memory in the LLM Era survey, arXiv 2604.01707 §7) and Engram's
dense+lexical fusion evidence (arXiv 2606.09900); trace in
`docs\research\CHANGES-FROM-RESEARCH.md`.

**Build shapes (approved with the plan; one design correction surfaced at build):**

1. **Token-OR tsquery, not websearch/plainto AND semantics — the build-surfaced correction.**
   The plan sketched `websearch_to_tsquery`; at build it surfaced that websearch/plainto AND
   semantics would make the channel inert (a real utterance never full-AND-matches a stored
   memory). Shape built: `lexical_tsquery` — casefolded word tokens of ≥ 3 letters (letter-runs
   only: to_tsquery syntax injection-safe by construction), deduped in order, capped 16,
   OR-joined; ts_rank + memory_id orders the deterministic LIMIT cut; the read-path scoring
   formula does the real ranking after the union. The 3-letter minimum and 16-token cap are
   module constants — flagged by the floor-verifier as future knob candidates if an integrator
   ever needs them tunable.
2. **Migration 004 = index-only.** A partial GIN over live fact heads,
   `to_tsvector('simple', basis_text) WHERE invalid_at IS NULL` (the 002/003 partial-index
   precedent). No table/column changes, no data DML.
3. **The string knob follows the decay_classes precedent.** `text_search_config` is a plain
   agents.config key with `TEXT_SEARCH_CONFIG_DEFAULT = "simple"` in `app\config.py` (the
   float-only SERVICE_DEFAULTS/agent_knob contract doesn't fit a string). 'simple' is baked
   into the index expression (an expression index binds one config); the default-config SQL
   branch bakes the same literal so the planner matches the partial GIN; an override
   parameterizes `::regconfig` and runs the same predicate unindexed — correct, slower, stated
   in the migration header.
4. **Union is additive-only, scoring untouched.** Lexical candidates union into the vector
   over-fetch before scoring, dedup by memory_id (vector row kept); lexical hits carry their
   TRUE cosine distance (the all-named-params wire convention). `lexical_fetch_k` (default 8.0;
   **0.0 = the kill-switch**, pure-vector v1 — the gate_enabled shape).
5. **NULL-embedding fact heads are lexically reachable, relevance null — designed.** The fetch
   deliberately omits the `embedding IS NOT NULL` filter: exact-token recall softens the
   embed-degradation consequence (never a filter). This sharpened read-path walker criterion
   [9]: the vector-path exclusion is now asserted ON THE PROBE itself, and the healthy-path
   lexical reach of a degraded row is asserted honestly (relevance null).
6. **Loader-scope v1.** The gate's fire probe and the degradation ladder's entity-only rung are
   noted future consumers of the channel, deliberately not built (scope discipline). Degraded
   loader turns skip it (the fallback already fetches every live row).
7. **The mechanical ledger-pin update:** `verify_gate.py`'s exact-ledger assertion grew
   001+002+003 → +004 (the per-migration precedent); nothing else in that walker changed.
   Read-path walker 42 → 48 (criterion [13] + the sharpened [9]); suite 40 → 41.

## Real-mode parse hardening ruling — 2026-07-21

**Context.** The real-mode testing session (pre-ship gates b + c — the first session ever to
construct the real providers) broke on its first live smoke, in two independent ways, both
parse-side; the models' actual output was valid in every captured sample:

1. **sonnet-5 emits a leading `thinking` content block** (thinking-on-by-default model
   family), so `response.content[0].text` — the shape every real provider had used since the
   write-path build (2026-07-13, pre-dating that model behavior) — raised `AttributeError`
   on `RealReconstructionProvider`, an exception NOT in its catch tuple: the whole dialogue
   turn crashed rather than degrading. Diagnostic: content[0] = thinking block, content[1] =
   flawless JSON.
2. **haiku-4.5 wraps its escalation JSON in markdown code fences** despite the prompt's
   "No other text" (3/3 samples in the raw-response diagnostic; the write prompt on the same
   model returned bare JSON). Both parse attempts fail identically, so the seam's
   retry-once-then-hard-stop made EVERY escalating observe hard-stop in real mode.

**Ruled (Jack, via explicit question): parse-side hardening only.** Two helpers in
`app\providers.py` — `_first_text_block()` (first text-type block, "" when none => the
existing JSONDecodeError path) and `_lenient_json_text()` (strip markdown fences before
`json.loads`) — applied at the four JSON-in-text parse sites (write, escalation,
reconstruction, dialogue-accumulated-stream). Prompts, fakes, and every seam byte-untouched.
Alternatives presented and not adopted: prompt-only fence fix (relies on per-call model
obedience; one fenced reply is another hard-stopped write) and a model swap off sonnet-5
(leaves the escalation defect and the latent thinking-block fragility). Commit `1388bf6`;
re-verified suite 41/41 + all seven walkers green (40/48/36/42/34/34/51) + the gate-b smoke
end-to-end.

**Carried observations (no ruling asked):** the hardcoded `max_tokens=1024` (2026-07-16
observation) now also bounds sonnet-5's adaptive-thinking spend inside dialogue calls — no
observed truncation (30/30 turns parsed; out-tokens p50 well under budget), but it is the
first place to look if real-mode `MalformedOutputError` ever appears; a
`thinking: {"type": "disabled"}` request-side knob is a possible future lever for the
non-streaming reconstruction call (cost/latency, quality tradeoff — Jack's call if raised).

## Latency slate + split-brain pull-forward rulings — 2026-07-21

**Context.** The real-mode session's numbers put the player-facing turn at p50 ~4.1 s (first
token 1.4–2.2 s; a cold-scene reconstruction adds 9–16 s; our own layer costs ~190 ms of it —
the rest is model inference). Jack reviewed the table and ruled the latency work now.

**Rulings (Jack, via explicit questions + plain-prose gray-area review):**

1. **The viability bar: first word < ~1 s.** The product latency metric is prose
   time-to-first-token at the seam, not turn total.
2. **All four levers land before the demo ships:** A — split-brain streaming (specced this
   session, `split-brain-streaming.md`); B1/B2 — dialogue-call latency experiments
   (thinking-off one-liners + a haiku-dialogue env A/B, measured before committing); C1 —
   scene-boundary reconstruction pre-warm (background-reconstruct at scene start so first
   turns hit the ~4 ms cache; the scene-frozen cache key already supports it); D — async
   game-side observes + folding the measured 79% escalation fire rate into the owed
   escalation re-rule. Unchosen-now ≠ dropped: each is an immediate-queue pre-ship item.
3. **Split-brain pulled forward WHOLE — with a ruled topology alteration.** §9's serial
   sketch (behavior call, then prose sees that turn's action) would put ~0.8–1.5 s of
   behavior call in front of the first prose token. Jack re-read the asymmetry: the prose
   call needs **past** behaviors as world facts ("why did you do that a minute / a week
   ago"), never the current turn's — so the calls run **concurrently** and the current
   action enters the record for later turns. §9 amended (supersedes-in-part its serial
   wording).
4. **Gray area 1 — same-turn incoherence: accepted, and instrumented.** Concurrent calls
   mean one turn's words and action are chosen independently; occasional mismatch is the
   split-brain character (bounded by shared retrieval + the action vocabulary; self-aware
   from the next turn). Ruled with instrumentation from day one: the turn result records
   both calls' ranked scored views + the directive — §13's explanation-cause divergence
   measurable structurally.
5. **Gray area 2 — the world record is game-authored + a scene block.** Durable: the
   integrator reports *resolved* actions as ordinary observe events (the store never
   records unresolved intent; the endpoint exists — a documented contract, zero code).
   Within-scene: a caller-held recent-actions block in the prose prompt, reset at
   boundaries. The seam-auto-write alternative was rejected (records intent as fact even
   when the game contradicts it).
6. **Per-call weights go LIVE now, behavior view only** — the reserved `WeightOverrides`
   slot is consumed via a second scoring pass over the same candidate set; dialogue-view
   scoring stays byte-identical when no overrides ride (the context-term parity precedent).
   The read-path walker's inertness criterion re-scopes at build (ruling-driven).
7. **Streaming surface = seam + REPL + driver this slice.** The SSE/HTTP route rides with
   the Unity client item, where its consumer exists.

**Honest prices stated with the rulings:** this spec alone makes first word = TTFT
(1.4–2.2 s today) — the <1 s bar additionally needs the B-levers; the serial full-§9 shape
was presented fairly (lands the asymmetric same-turn framing, costs ~+0.8–1.5 s before the
first word) and not adopted; the single-call prose-first restructure was presented (cheapest,
no asymmetry landed) and not adopted.

## Split-brain streaming build rulings — 2026-07-21

**Context.** Immediate-queue item 1 (`split-brain-streaming.md`), built the same day it was
specced. The seam was split into two concurrent calls off one retrieval: a streaming pure-prose
call and a behavior call (directive + delta). Four forks were ruled via explicit questions at
plan approval; the mechanical settle-tags were approved with the plan (annotated onto the spec).

**Rulings (Jack, via explicit questions):**

1. **Behavior model role = a new `behavior` role.** `LONGMEM_MODEL_BEHAVIOR` +
   `LONGMEM_PRICE_BEHAVIOR_IN/OUT`; added to the CLAUDE.md role list; real-mode config validates
   it like the other roles. (Reuse of the `reputation` role name was the alternative — declined
   as under-descriptive, since the call also chooses the action.)
2. **Seam shape = async generator.** `run_dialogue_turn` yields prose chunks, then the terminal
   `DialogueTurnResult`; `first_word_ms` = time to the first yielded chunk. The chunk-callback
   alternative was presented and not adopted.
3. **Mid-stream prose drop = keep the partial + degraded flag** (partial prose is non-blank).
   Discard-and-fallback was the alternative.
4. **Behavior view = re-rank the served top-k set** (not the full over-fetch pool). Same served
   memories re-scored with resolved weights → a different salience order; reuses served text,
   zero extra SQL/model calls; divergence = order/score over the shared set. The full-pool
   variant (behavior-only items serving verbatim live heads) was presented with its plumbing
   cost and not adopted.

**Build resolutions (settle-tags, stated for the record):**

- **Exponent-form weighting.** The reserved `WeightOverrides {relevance, recency, importance}`
  applies as component-wise exponents on the product score:
  `behavior_score = item.score · rel^(w_rel−1) · rec^(w_rec−1) · imp^(w_imp−1)` (zero-component
  guard). At all-1.0 the exponents vanish so `behavior_score == item.score` — the dialogue-view
  parity contract — and any other value genuinely re-ranks. A plain per-component multiplier was
  rejected (a uniform scalar cannot re-rank a product); a weighted sum was rejected (it breaks
  product-form parity). Weights resolve request → `agents.config` → 1.0, clamped `[0.0, 4.0]`
  (module constants, not knobs). The behavior view is computed in the dialogue seam from the
  served `RetrievedMemory` fields, so retrieval stays byte-untouched; `DialogueInitRequest`
  `weight_overrides` stays inert (the read-path parity contract holds).
- **Identity in BOTH prompts.** The behavior prompt shares identity + reputation snapshot with
  the prose prompt (the §9 spec diagram omitted it; resolved to include it) so the asymmetry
  stays STATISTICAL not architectural — same character + same candidates, only the memory
  weights and the call type differ. The recent-actions block is the one ruled information
  difference and is prose-only (the behavior call chooses a new action, it does not explain a
  past one).
- **Prompt split.** `assemble_system_prompt` split into `assemble_prose_prompt` (identity +
  reputation + dialogue-view memories + recent-actions + a pure-prose instruction) and
  `assemble_behavior_prompt` (identity + reputation + behavior-view memories + the directive/delta
  JSON contract + vocabulary). The gate walker's sole change is the mechanical
  `assemble_system_prompt` → `assemble_prose_prompt` rename (its `[]` sixth positional arg is now
  `recent_actions`, so its [memories]-structure assertions stand).
- **Recent-actions block** = caller-held scene state (the fifth application of the
  caller-holds-scene-state contract): each turn's resolved directive appended as world-fact
  context for later turns' prose prompts, capped at `recent_actions_cap` (default 8), reset at
  scene boundaries, never stored server-side. `session.utterance` drains the seam and applies the
  bookkeeping in one place (`_apply_turn_result`); `session.stream_utterance` yields chunks for
  the REPL.

**Concurrency mechanism.** The behavior leg runs as an `asyncio.create_task(to_thread(...))`; the
prose leg's sync generator runs in a worker thread pushing chunks onto an `asyncio.Queue` via
`loop.call_soon_threadsafe`, drained by the async generator. Done-when 1 is proven with a
deliberately slow behavior fake: the first prose chunk arrives in ~8 ms while the behavior call
sleeps 300 ms (walker [7]).

**Environment note (flagged, NOT fixed — operator-owned `.env`).** `.env` carries a malformed
consolidated price line — `LONGMEM_PRICE_DIALOGUE_IN=3.00 / _OUT=15.00, _RECONSTRUCTION_IN=…` —
which `config.load_settings` cannot parse as a float, so any run that reads `.env` prices
(real mode, or fake mode without overriding that var) crashes at startup. The 2026-07-21
real-mode session sidestepped it by env-injecting clean prices. Jack's `.env` to fix; surfaced
for the pre-ship gates.

**Verification.** CLI-harness walker re-opened 36 → 55; read-path walker weight_overrides
criterion re-scoped (48); gate walker rename-only (51); write/reconstruction/authorial/fact
walkers byte-untouched and green (40/42/34/34); full suite 41 → 42 (twice) + keyless subset 35;
no-arg migrate "4 applied, 0 pending"; `longmem` pristine via the postgres MCP (ten product
tables 0 rows, ledger 001–004, no scratch residue); live piped REPL streaming beat + a standalone
driver run with the `first_word` + `behavior` series and the behavior cost row. No migration.

## External-persona audit + pre-demo replan rulings — 2026-07-22

An external-persona **agent-team audit** was run — four read-only personas (a Convai/Inworld-type
founder/CEO, a senior runtime engineer, a memory/cognition researcher, a skeptic) over a 3-round
critique + a solutions round; full record in `external-audit-2026-07-22.md` and
`external-audit-2026-07-22-solutions.md`, persona defs in `.claude\agents\audit-*.md`. Load-bearing
findings were confirmed against source: **`app\api.py` exposes no HTTP dialogue-turn route** (only
`dialogue/init` retrieval + observe + scene-boundary + pin + correction), so the entire cognition
layer is reachable only in-process via `app\session.py` — Unity (C# over HTTP) cannot reach a turn
today; `first_word_ms` starts its clock at the prose call, **after** retrieval, so it is blind to the
cold-reconstruction stall; and the behavior view is **byte-parity with the dialogue view at default
weights**, so the split-brain divergence record is a near-no-op until non-default weights are authored.

Jack ruled three forks and adopted the audit's plan into the immediate queue:

1. **Split-brain in the demo = a separate interview clip, not a main-video beat.** The main demo
   turn path wraps `run_dialogue_turn` at default weights (coherent by construction — no revert, no
   incoherence risk). The authored "two brains" divergence becomes a short standalone clip + the
   paper's asymmetry ablation (Turpin template). The built floor stays. (STAGE-in-video was the
   alternative — the divergence's on-camera value did not justify the extra Unity work against a
   byte-parity default.)

2. **Demo records on real providers only** (no fake-mode backup take). Rationale: the on-screen
   cost/latency table and the drift must be genuine to survive a tier-1 interview, and the fake
   embedding is calibrated to the mechanism (the 60-day fake drift is an artifact). Consequence: the
   malformed-`.env` fix (+ `LONGMEM_MODEL_BEHAVIOR`) is now a **hard prerequisite**, not a background
   flag; real-mode robustness carries no insurance take.

3. **Judged eval harness pulled PRE-demo, with three additions.** Beyond the already-ruled judge
   model role + LLM-judged categories: (i) a **judge-free gist-precision/detail-recall metric**
   (computed from existing gist spans + spaCy, no judge call) that feeds the on-screen demo panel's
   real numbers; (ii) a small **hand-labeled gold set** so the LLM judge has proven rigor
   (judge-agreement / meta-eval); (iii) the **fixed-gist-constraint ON/OFF ablation** — the decisive
   test that turns the self-referential drift-budget hole into a shown finding. The two-text
   side-by-side panel + a real gist/detail number is retained as a demo visual regardless. (This
   pulls the former research-queue item 3 into the pre-demo phase — a scope expansion Jack accepted
   with the runway cost stated: the judged harness + gold set is ~1–2 focused weeks on top of the
   plumbing + Unity estimate, parallelizable with the Unity build.)

**The Ledger.** The demo's ground-truth-vs-telling panel is promoted from a debug view to the
designer-facing hero surface (the memory inspector Convai/Inworld don't offer) — it is the
legibility layer and the judge-free measurement as one object.

**Re-sequencing note (flagged, not a new ruling).** The audit showed the demo's 9–16 s cold
reconstruction stall is removable by **off-camera cache warm-init** (a throwaway `/v1/dialogue/init`
at each scene basis during a camera cut; within-scene byte-stability guarantees identical on-camera
bytes), so the **C1 pre-warm BUILD is no longer demo-blocking** and is proposed to move post-demo.
This relaxes the 2026-07-21 latency slate's "all four levers land pre-demo" wording and is flagged
for Jack's confirmation. The perceived-TTFT metric fix (retrieval-inclusive) rides with the turn route.

**R7 — self-referential drift budget (logged open item, NOT acted on).** The drift budget is cosine
candidate-vs-anchor < 0.35; it cannot catch a retelling that stays under budget while dropping or
contradicting a gist fact, or fabricating a never-observed detail. This challenges the 2026-07-17
drift-metric/threshold ruling; the fixed-gist ON/OFF ablation (ruling 3) will produce the data, and
any metric/threshold change waits on that data. Added to open questions.

**No code, no floors, no migration this session** — audit + rulings + queue replan only. The demo's
split-brain-topology and reconstruction code are unchanged; the built floors stand.

## Escalation failure-path + pre-warm + R7 rulings — 2026-07-22

Three follow-on rulings after the external-persona audit replan (same day):

1. **Escalation failure path: retire the hard-stop — soft-degrade in production.** The v1 write path
   hard-stops a write when the gist-escalation call fails twice (the fail-loud build-phase stance,
   ruled 2026-07-13). Jack ruled that stance **temporary and now retired**: an escalation failure must
   **not halt** a live write. The write proceeds and degrades gracefully — the observation is stored,
   the escalation is skipped/flagged rather than aborting the turn. The exact soft-degrade shape
   (proceed with the base non-escalated gist + a queryable escalation-failed flag — the `scoring_failed`
   precedent — vs a bounded retry-then-proceed) is a build detail to settle when the write-path change
   is built. This is a write-path code change **plus** the structural suite's hard-stop test, which
   asserts the current build-phase stance and flips with it. Demo-relevant: under real-providers-only
   with no fake backup take, a hard-stop on an escalation hiccup would kill a recording take. **The
   trigger-set/threshold half of the widened question (escalation fires on 79% of realistic prose) is
   NOT ruled here** — it stays a separate, non-blocking cost/latency tuning item.

2. **C1 scene-boundary reconstruction pre-warm BUILD → confirmed POST-demo.** The audit's re-sequencing
   is confirmed: the demo cold-stall is covered by off-camera warm-init choreography, so the full
   pre-warm build is not demo-blocking. This relaxes the 2026-07-21 latency slate's "all four levers
   land pre-demo" wording for lever C1 specifically; the scene-frozen cache key still supports the full
   background build when it lands post-demo.

3. **R7 (self-referential drift budget) → deferred to the Unity/eval build phase.** Not acted on now;
   revisited during the pre-demo Unity + Ledger + judged-eval work, decided from the fixed-gist ON/OFF
   ablation data produced there. (Challenges the 2026-07-17 drift-metric/threshold ruling; the deferral
   holds that ruling until the data exists.)

**`.env` verification (this session).** Jack fixed the malformed consolidated `LONGMEM_PRICE_*` line in
a prior thread; verified via `config.load_env`/`load_settings` (values never printed): all eleven
`LONGMEM_PRICE_*` keys parse as floats, `LONGMEM_MODEL_BEHAVIOR` is present, provider mode is `real`,
and `load_settings()` succeeds. Immediate-queue item 0 (unblock real mode) is **done** — the 2026-07-21
flagged `.env` crash is resolved.

## Escalation soft-degrade build — 2026-07-22

Built the escalation soft-degrade ruled above. **Flag ruling: a dedicated queryable column**
(`memories.escalation_failed`, migration 005, mirroring `scoring_failed`) — chosen over a wire-only
flag (not queryable after the fact) and over reusing `scoring_failed` (which would conflate the
gist-escalation degrade with the importance/typology score degrade, losing the signal). Migration 005
is a single boolean, `NOT NULL DEFAULT false`, no backfill.

Build: `_escalate_with_retry` returns `None` on double failure instead of raising; the observe path
proceeds with the base NLP-pass spans/components and sets `escalation_failed = true`;
`EscalationHardStopError` and its observe-route 502 are removed; the flag rides `InsertPlan` →
`memories.escalation_failed` and `IngestResult.escalation_failed`. **Scope is the observe path only** —
the correction verb's own fail-loud embed/NER → 502 paths (all-or-nothing, ruled 2026-07-18/19) are a
separate ruling and stay untouched. The suite's `test_escalation_hard_stop_zero_rows` became
`test_escalation_failure_soft_degrades` (write lands + flag set on the result and the column); the
write-path walker's `[11]` flipped the same way. The trigger-set/threshold tuning (79%-fire) stays a
separate, open item.

Verification: migration 005 applied to `longmem` (idempotent — "5 migration(s) applied, 0 pending");
full structural suite 42 passed. Independent floor-verifier re-verification of the re-opened write-path
floor: see `session-log.md` + `floors.md`.

## HTTP turn route + perceived-TTFT build rulings — 2026-07-23

**Context.** Immediate-queue item 1 from the 2026-07-22 audit replan — the audit's #1 confirmed
finding was that `app\api.py` exposed no dialogue-turn route, so the cognition layer was reachable
only in-process and Unity (C# over HTTP) could not reach a turn. The design was pre-stated by the
queue entry and the audit solutions doc's engineering spec, so this was a plan-as-spec session (the
test-suite precedent): orient → one explicit-question ruling → scoped build.

**Ruling (Jack, via explicit question at plan approval): the thread-pool cap is deferred
post-demo.** The audit engineer flagged that both model calls share Python's default thread pool —
each turn holds a worker thread for the full prose stream, capping concurrent turns (~16 on this
machine) once turns arrive over HTTP — and proposed a named, explicitly-sized executor in the API
lifespan as the cheap correct fix. Ruled: the build stays exactly what the queue names (route +
metric); the demo is one NPC, so the shared pool cannot bite before then. The cap rides with the
post-demo async-native streaming work (which removes held threads entirely). Including it now
(~10 lines, touching only files this build already re-opened) was presented and not adopted.

**Build shapes (stated for the record):**

- **Route = `POST /v1/dialogue/turn`, non-streaming, stateless.** `DialogueService` joins the API
  lifespan beside the retrieval service; the handler drains `run_dialogue_turn`'s async generator
  to the terminal `DialogueTurnResult` — the drain loop from `session.utterance` minus the runner
  bookkeeping, which is deliberately the CLIENT'S job (the future C# `NpcSession` ports
  `_apply_turn_result`; all scene state already rides the request). Error maps follow the existing
  precedents: `UnknownAgentError` → 404, `UnknownIdentityVersionError` → 422. The pass-through
  ruling (2026-07-13/14) holds: the response is exactly the seam result's serialization.
  `on_reconstruct` stays `None` on this route — no during-wait signal without SSE, and the
  result's post-hoc reconstruction fields carry it honestly. A future SSE `/v1/dialogue/turn/stream`
  iterates the SAME generator (the async-generator seam ruling's payoff) — no rewrite.
- **Metric = `perceived_first_word_ms`, captured at the same first-chunk instant as
  `first_word_ms`.** One timestamp at the first yielded chunk, clocked two ways: from `t_prose`
  (the existing `first_word_ms`, kept for series continuity) and from `t_total` (turn start —
  agent fetch + retrieval included, so the field sees the cold-reconstruction stall the old metric
  is blind to). 0.0 when no chunk ever arrives (the `first_word_ms` precedent). The <1 s viability
  bar is measured against the NEW field. Surfaced beside the old one in the CLI debug line and as
  a `perceived_first_word` load-driver series.
- **No migration** — a fact of this target: an HTTP route over existing seams plus one
  instrumentation field; nothing new is stored (ledger stays 001–005). No new knobs, no new model
  roles.

**Verification.** CLI-harness walker re-opened 55 → 62 (route pass-through via ASGITransport +
capturing wrapper, 404/422, perceived > first_word > 0, both-TTFT-zero on the pre-chunk-failure
row, the driver series); suite 42 → 43 (the unmarked route-contract scenario in Set D; keyless
subset 35 → 36); the six other walkers and every other `app\` file byte-identical to HEAD; live
`python -m app.serve` HTTP beat (observe → turn → 404) + a standalone driver run. Independent
floor-verifier re-verification: see `session-log.md` + `floors.md`.

## Escalation trigger tuning: measurement + rulings — 2026-07-23

**Context.** The open trigger-set/threshold item (widened 2026-07-21 by the real-mode 79%-fire
finding; "measure, then rule"). Jack ordered the measurement this session, ahead of the Unity phase.

**The measurement** (report-only probe on scratch `longmem_esc`, real providers, the 2026-07-21
realistic corpus construction reproduced exactly — 40 texts × 2, ford-keeper agent + the Mara
component; per-observe RAW trigger inputs recorded, the piece the earlier probe aggregated away;
~$0.25 spend; artifacts scratchpad-only):

- Fire rate reproduced: **60/80 = 75%** (prior 79%; same trigger mix — importance 40, unresolved 29,
  novel 11, low_confidence 9, identity_affect 4; an offline re-computation of `evaluate_triggers`
  over the records matched the recorded fires with 0 mismatches).
- **Escalation is productive, not runaway: 85% of fires added ≥1 net gist span or identity
  component** after dedup (mean +2.17 spans, +1.30 components per fire).
- **The importance threshold is a weak lever.** Real haiku scores cluster ≥0.60 — raising the
  default 0.45 → 0.60 changes nothing on this corpus; 0.65 trims only 75% → 71%; with the trigger
  effectively disabled the rate stays 57% on the overlapping triggers. Importance p50 also moved
  0.61 → 0.47 between the two real runs — decimal-tuning it would be false precision.
- Cost/latency: ~$0.0020 and ~1.3 s per fire ⇒ ~$0.15/100 observes at the current rate; the latency
  leaves the dialogue path entirely under the ruled async-observe client contract (lever D).
- Sole-cause attribution: importance 14 (all 14 value-adding), unresolved_reference 13 (12),
  novel_entity 4 (4), low_confidence 0, identity_affect 0 (the last two only ever co-fire — free
  riders on calls that fire anyway).
- **The zero-gist hole: 16/80 observes landed with ZERO gist spans.** No trigger fires on "the base
  gist is empty," so a low-importance, no-identity-hit observation stores no gist constraint at
  all — reconstruction's fixed constraint is EMPTY for those rows (R7 at its widest) and they are
  invisible to the coming gist-precision metric. Escalation rescued 16/16 zero-base observes to
  ≥2 spans whenever it did fire.

**Rulings (Jack):**

1. **The shipped defaults stand** — the five original triggers and both thresholds (importance
   0.45, affect 0.5) unchanged. Gist capture is load-bearing for the reconstruction thesis; the
   measured rate is mostly productive; the trims save cents while losing value-adding escalations.
   (Raise-to-0.65 and drop-unresolved options presented with the data and declined; Jack's stated
   direction is toward MORE firing where gist preservation needs it, not less.)
2. **A sixth trigger: `thin_gist` — the gist floor protected directly.** Fire when the base NLP
   pass yields fewer spans than `escalation_min_base_spans` (new knob in `SERVICE_DEFAULTS`,
   default 1.0 = fire on zero spans; 0.0 disables — span counts are never negative; per-agent
   overridable like the other escalation knobs). On the measured corpus: 75% → 95% fire rate,
   ~+$0.03/100 observes, the zero-gist class eliminated. (Always-escalate — shipping
   `escalation_importance_threshold` 0.0 — was presented and not adopted as the default; it
   remains available to any integrator as pure config.)
3. **Engram-style deferred write cognition → the sequenced-later ledger** as its own spec target
   (raw text stored immediately, enrichment at the service's own timing — Engram 2606.09900 +
   the sleep-time-compute family already cited in the reflection dossier). Assessed viable and
   partially present: the async-observe client contract already covers the latency motivation,
   and the existing degradation flags (`scoring_failed`/`escalation_failed`/`embedding_failed`)
   are the natural deferred-work queue. The spec's real forks: late gist-span/component adds are
   add-only annotations, but importance/typology/entities are FROZEN write-time facts by explicit
   rulings (2026-07-18 fact scope; 003 entities freeze) — late changes need fact-version-style
   supersession or re-rules, and a new `write_cause` is a migration; plus the un-enriched-window
   retrieval contract and pre-enrichment cached retellings. With thin_gist closing the correctness
   case inline, the deferred worker is a cost/throughput optimization — pull-forward eligible.

**Build (thin_gist).** `TRIGGER_THIN_GIST = "thin_gist"` + the floor check appended last in
`nlp.evaluate_triggers`; the knob in `SERVICE_DEFAULTS` (`app\config.py`); the knob key added to the
observe path's per-agent knob fetch (`app\ingest.py`). Fake-mode consequence stated: more fixture
observes now escalate, but `FakeEscalationProvider` echoes the NLP-pass candidates unchanged, so
stored rows are byte-identical — only `escalated`/`escalated_by`/timing/token fields move; no
existing assertion broke. Walker `tests\verify_write_path.py` grown ([11b]: the pure-function
contract — thin_gist fires alone on a zero-span pass, kill-switch at 0.0, floor-compares-the-COUNT —
plus the measured sexton fixture escalating with thin_gist as the SOLE trigger at the service
level); suite +1 pure keyless scenario (`test_thin_gist_trigger_pure` over production
`SERVICE_DEFAULTS`; 43 → 44, subset 36 → 37). No migration — knob + trigger only.

## Demo-vehicle ruling — Unity, not an established-game mod — 2026-07-27

**Context.** At the state review before immediate-queue item 2 (Unity + reference scene + The
Ledger), Jack re-opened the demo-vehicle question: build the custom Unity scene, or mod the NPC
into an established game (Skyrim named) — his stated premise being that Unity scene-building has
been a time-sink and occasional roadblock in past projects. A five-agent read-only panel was run —
the four external-audit personas (`.claude\agents\audit-*.md`, the 2026-07-22 template) plus a
web-research scout on the mid-2026 LLM-NPC modding landscape.

**Panel findings (brief).**

- The time-sink premise attaches to *game* scenes (art, animation, navmesh, feel) — costs the
  gray-box aesthetic (adopted with the 2026-07-22 audit plan) already removed; the demo scene
  is a set, not a game. The remaining
  Unity cost is the C# client, which is the end-goal artifact itself, not a sink. The genuinely
  risky Unity work is runtime plumbing: the null-vs-absent JSON contract (`loaded_memory_ids`
  null = loader turn vs `[]` = an empty loaded set the gate still evaluates over — trivially
  novel, so it fires; a serializer collapsing one into the other silently changes gate
  behavior), async→main-thread marshaling, and Play-mode debugging (where MCP-for-Unity is
  partly unavailable — scene-manipulation operations fail in Play mode, `mcp-setup.md` §2).
- Skyrim is the worst instance of the mod path: Papyrus/SKSE shares zero code with the
  `NpcMemory` package; the demo lands in the Mantella/Herika/CHIM comparison class (all market
  "NPCs remember" via transcript-summary + vector recall — the differentiators have no analog
  there but are invisible in dialogue); unvoiced generated text inside a fully-voiced game reads
  as broken where gray-box reads as deliberate; the engine emits state deltas, not prose, so the
  observe corpus is hand-authored either way; game RNG breaks paired ON/OFF ablation capture; a
  published Mantella fork must be AGPL-3.0. Scout's estimate for the no-experience Mantella-fork
  path: ~1–3 weeks on a famously brittle multi-process stack. (Bethesda's fan-video policy makes
  the *video* IP-safe; the repo could never ship the mod.)
- The Ledger is engine-independent and cheapest as a browser page over the existing HTTP API —
  it would otherwise have been the single most expensive Unity UI in the plan.

**Rulings (Jack):**

1. **Demo vehicle = Unity gray-box, with three de-riskers.** (a) The C# client core is built
   engine-agnostic first — plain .NET, HTTP + JSON + the `NpcSession`/`_apply_turn_result` port,
   zero `UnityEngine` types, one flat client class (no abstraction ceremony) — driven by a
   `dotnet run` console harness that plays every demo beat headless. This moves the recorded
   Wk-2 Unity↔backend interop go/no-go into Wk-1, before Unity ever opens. (b) **The Ledger is
   a browser page**, composited beside the game view in OBS — not Unity UI. (c)
   **Established-game integration is deferred to a post-demo clip** (the split-brain
   interview-clip template), targeting a C#-moddable game — Stardew Valley (SMAPI, days-scale)
   or RimWorld (the richest observe stream the scout found: ~100 data points/interaction via
   RimDialogue) — NOT Skyrim; the engine-agnostic core gets reused there instead of rewritten.
2. **The week-3 fallback is deliberately not pre-ruled.** The skeptic proposed pre-deciding a
   CLI + browser-Ledger recording as the fallback video; Jack declined — decide later only if
   needed. (Recorded so the option isn't lost: the REPL already drives every beat today.)

**Carried into the item-2 spec (to surface there, not resolved here):** SSE `/turn/stream`
timing (the <1 s perceived-first-word beat cannot be recorded without it — real first-token
2.2 s, B1/B2 unruled); an agent-provisioning route (`POST /v1/agents` does not exist — the demo
agent is hand-SQL today); the C# serialization/packaging shape; the Ledger page stack + bound
fields (bind the same `DialogueTurnResult` fields the eval harness scores); an early one-hour
MCP-for-Unity verification (runbook-ready, never connected); and the demo-corpus register —
authored in shipped-game dialogue style, with the held-out corpus arm noted for the judged eval
(the construct-validity mitigation for the gray-box path's honest weakness: escalation fired
79% on realistic prose vs 0% on synthetic driver prose in the 2026-07-21 pre-thin_gist
measurement — ~95% on the corpus at current defaults since the 2026-07-23 thin_gist build; the
prose-dependence point is what carries).

**No code, no floors, no migration this session** — panel + rulings + docs propagation only.

## Unity-client fork rulings + stage-0 build (three backend routes) — 2026-07-27

**Context.** Same day as the demo-vehicle ruling: Jack completed the operator steps (Unity 6
project created at `unity\` — settling the spec fork-5 project-location half; uv + .NET SDK
verified) and MCP for Unity went live — **bridge verified** (read probe found the scene camera;
mutation round-trip created and deleted `McpVerificationCube` in `SampleScene.unity`; console
clean). Jack then ruled all seven `unity-client.md` open forks via explicit questions:

1. **SSE `/v1/dialogue/turn/stream` — IN scope** (fork 1; without it the <1 s
   perceived-first-word beat is unrecordable).
2. **`POST /v1/agents` — IN scope** (fork 2; the integrator's minute-one gap).
3. **The Ledger's data source = the chain read route** (fork 3; `GET /v1/memories/{id}/chain` +
   `GET /v1/agents/{agent_id}/memories` — the inspector becomes product API surface, over
   direct read-only SQL).
4. **Serializer = Newtonsoft everywhere** (fork 4; Unity-shipped package + the same library in
   the core — one serializer, one behavior in both hosts; over System.Text.Json's Unity
   AOT hazards).
5. **Targets/layout as proposed** (fork 5; netstandard2.1 `client\NpcMemory.Core`, net8.0
   `client\NpcMemory.Harness`, adapter in `unity\Assets\Scripts`, core DLL into
   `Assets\Plugins`).
6. **Ledger stack = static HTML + vanilla JS** (fork 6; no framework, no build step; the
   per-turn feed shape settles at build).
7. **Unity render shape settles at build** (fork 7, as specced).

**Stage-0 build (the three ruled-in routes; no migration — ledger stays 001–005; no new knobs
or model roles).**

- **SSE route** (`app\api.py`): iterates the SAME `run_dialogue_turn` async generator via a
  pump task bridged through an `asyncio.Queue` (the pre-serve `on_reconstruct` callback fires
  inside the awaited chain, so it enqueues a `reconstructing` event). Events: `chunk`
  (JSON-encoded str), optional `reconstructing`, terminal `result` — the seam result's
  serialization, byte-identical to the non-streaming route's body (pass-through). The FIRST
  queue item is awaited before the response starts, so unknown-agent/version still map to
  404/422; after streaming begins a failure becomes an `error` event (a 200 stream cannot
  change status). A module-level task-reference set means a client disconnect never aborts the
  turn server-side (the reputation apply stays atomic in the seam).
- **Provisioning** (`db.insert_agent` + `IngestService.create_agent` + wire models): UUID
  minted server-side; the row stores exactly the supplied fields; unsupplied knobs land NULL
  and resolve config → `SERVICE_DEFAULTS` at read time exactly like a hand-provisioned row; no
  model calls; the identity document still compiles at session start / scene boundary. The
  agents INSERT is the build's only new write surface — an agents row, not memory content,
  outside the non-destructive invariant's subject.
- **Inspector reads** (`db.fetch_memory_chain`/`fetch_agent_memories` +
  `RetrievalService.memory_chain`/`agent_memories` + wire models): read-only end to end.
  **Explicitly ruled contract: these reads are UNSCORED** — no retrieval runs, no decay
  evaluates, so no score fields exist; every row carries IDs + structured fields (the
  read-payload discipline's intent — never naked prose). Superseded rows ride with
  `valid_at`/`invalid_at` + `is_live` (greyed client-side, never dropped); the fact embedding
  never rides the wire (`has_embedding` only); `memories.entities` deliberately not echoed
  (frozen since the 003 freeze — the live fact head's entities are the current ones); the
  index LEFT JOINs the live telling head so legacy-shaped rows stay reachable; `limit` is a
  caller argument (1–1000, default 100), never a config knob.

**Verification (floor-verifier pass, independent):** write-path walker 46 → **51** (section
[15] provisioning), read-path 48 → **56** (section [14] inspector reads), CLI-harness 62 →
**67** (section [14] SSE — chunk events byte-identical to the terminal content); the four
untouched walkers green on fresh scratch (51/42/34/34) and byte-identical to HEAD; suite
44 → **48** ×2 + keyless subset 37 → **41** (the four new route-contract scenarios are
unmarked); migrate no-arg "5 applied, 0 pending"; `longmem` pristine (ledger 001–005, ten
product tables 0 rows, no scratch residue); floor economy by git diff (exactly nine files
touched). Next: stage 1 — `NpcMemory.Core` + the console harness (the Wk-1 interop gate).

## Unity-client stages 1-3 — build record — 2026-07-27

*(Entry written 2026-07-28 during the full-repo audit, which found the register stopped at stage 0
while three further same-day build sessions had settled shapes — including a shipped route and a
standing C# contract. Recorded here at its true date; the five 2026-07-27 session-log entries in
`session-log.md` carry the narrative (they lived in `status.md` until the 2026-07-28 split).)*

**Stage 1 — `NpcMemory.Core` + the console harness (the Wk-1 interop go/no-go).** Shapes settled at
build, all consistent with the ruled engine-agnostic design:

- **One serializer configuration** (`NpcJson`): SnakeCaseNamingStrategy + `NullValueHandling.Include`
  + `DateParseHandling.None` with `DateTimeOffset` end to end. `Include` is load-bearing, not a
  default: the wire contract is a **tri-state** — a *null* `loaded_memory_ids` means "loader turn",
  an *empty list* means "gated turn with nothing loaded", and collapsing null to absent would
  silently change gate behavior. The harness proves all three on the wire.
- **A flat client, no interface layer** (the ruled "no abstraction ceremony"), all ten routes 1:1,
  per-route settable timeouts, typed loud `NpcMemoryApiException`.
- **`NpcSession` ports `_apply_turn_result` field-for-field**, keyed on the SERVER's gate record
  rather than any client-side inference: loader turns seed the loaded set, gated turns append,
  closed turns leave it untouched. Boundary resets, recent-actions cap, `as_of` time travel.
- **Boundary reputation snapshot refreshes from the last turn's `reputation_after`** — exact for a
  single-client session, and noted in the artifact queue as the reason a multi-client integration
  would want a small agent-state read route (no such route exists).

**Stage 2 — the Unity adapter + gray-box set.** Fork 7 settled at build: the demo surface is an
**IMGUI dev-tool overlay**, the intended systems aesthetic rather than a game UI. Two fixes the
Play-mode gate surfaced:

- **Every `ConfigureAwait(false)` removed from the core** — a standing C# contract, not a tweak.
  The library idiom exists to prevent deadlock when a caller BLOCKS on a task; the adapter contract
  bans blocking, so the hazard does not apply, while the idiom's cost does: continuations must
  resume on Unity's `SynchronizationContext` so chunk/directive/reputation callbacks land on the
  main thread with no marshaling. Play-mode-proven (callbacks on thread 1).
  *(2026-07-28: the same contract retired `StreamReader.EndOfStream` from the SSE loop — a
  synchronous read that stalled the main thread between chunks. Same rule, one more instance.)*
- Directive-flash re-entrancy: overlapping flashes captured each other's colour as "original".

**Stage 3 — The Ledger.** Settled at build: the page is **served BY the API at `GET /ledger`**
rather than opened from disk or hosted separately — same origin as the two inspector routes it
polls, so there is no CORS surface and no second server, and the inspector ships WITH the service.
This completes fork 3's product-surface logic (the chain route, not direct SQL). One static file,
vanilla JS, no build step (fork 6). All server text reaches the DOM via `textContent` — no
innerHTML anywhere, so operator- and model-authored prose carries no injection surface.

## Full-repo audit rulings — 2026-07-28

Jack asked for a comprehensive audit of the whole repo — organization, documentation, workflows,
hygiene — then a plan, then implementation on approval. Method: seven read-only dimension
auditors (docs consistency, Python backend, tests, C#/Unity/Ledger, tooling and workflows,
organization, security and ops), each dimension's findings then handed to an adversarial verifier
instructed to refute them. 107 raw findings, 4 refuted outright, ~20 downgraded, 64 surviving
after deduplication. **Two of the four refutations were because the "problem" was an existing
dated ruling** — the absence of CI ("CI-ready now, workflow later", 2026-07-20) and the gate's
cosine import from the reconstruction module (approved with the 2026-07-19 gate build). Recorded
because it is the register working as intended: a ruling, once written down, defends itself.

**The audit's verdict on the codebase was that it is sound.** Zero assertions on generated prose
across the suite and all seven walkers; every in-place UPDATE and DELETE one of the sanctioned
exceptions; `.env` never added in any git ref; all thirty C# wire models mirroring `app\schemas.py`
field-for-field with the null-vs-`[]` tri-state intact; all SQL parameterized or composed from
module constants. Nothing found contradicted the floor claims.

### The four rulings

1. **`status.md` splits three ways.** Measured: 145,787 chars ≈ 36.4k tokens auto-loaded into
   every session, 77% of it append-only history. Ruled: `status.md` keeps live state and stays
   auto-loaded; the session log moves to `session-log.md`; the verified-floors table moves to
   `floors.md`. Both new files append-only, both moved verbatim. **Beat:** splitting the session
   log alone (keeps the 8.7k-token floors table riding into every session), and fixing in place
   (leaves the context cost). Result: ~30k tokens off every future session's baseline, no history
   lost. The counting convention is now stated in `floors.md` — its absence is what let "sixteen
   floors" stand against eighteen rows.

2. **Fix the code defects in this pass and re-verify, rather than queueing them.** Ruled with the
   cost stated: touching `app\` and `client\` re-opens verified floors and requires a
   floor-verifier pass. **Beat:** docs-only (recording the defects as queue items), and
   SSE-fix-only. The consequence was real — the verifier returned **fail** on the first pass and
   the pass was re-run after the fix, which is the discipline working, not a cost overrun.

3. **Cheap flip-prep now; the README rewrite deferred.** LICENSE, NOTICE, `.env.example`,
   `docs\SETUP.md`, and `docs\README.md` land now; README.md gets a minimal honest update naming
   `client\`, `unity\`, `ledger\` and pointing at the new index. **Beat:** doing the full README
   rewrite now — declined because the artifacts that would carry it (demo footage, the real-mode
   instrumentation table) do not exist yet, and a README written without them would be rewritten
   again at the flip. README.md says so in its own last line.

4. **The research writing moves into `docs\research\`.** `Research Papers\` was gitignored
   wholesale for its 45 source PDFs (~117 MB), which also excluded 58 KB of project work product —
   `FINDINGS.md`, `CHANGES-FROM-RESEARCH.md` (the provenance trace `status.md` calls material "for
   the future README"), the 46 per-paper reader notes, and the baseline brief — all on one machine
   and cited by eight tracked files. **Beat:** negating the two files in place inside the ignored
   folder, and leaving them untracked. The PDFs stay out of the tree.

### The defect the audit existed to find

`client\NpcMemory.Core\NpcMemoryClient.cs` drove its SSE loop off `StreamReader.EndOfStream` — a
**synchronous** read whenever the buffer is empty. This client deliberately carries no
`ConfigureAwait(false)` (the 2026-07-27 stage-2 contract) precisely so continuations resume on
Unity's `SynchronizationContext`, which means the blocking read happened **on the Unity main
thread**, between SSE chunks, on exactly the path the sub-1s perceived-first-word beat runs on. It
contradicted the "blocking is banned by the adapter contract" line in its own file header.

Worth recording for the pattern rather than the bug: **the Play-mode gate passed 8/8 with it
present.** A local fake-mode server streams fast enough to mask a main-thread stall, so the gate
that was designed to catch exactly this class of problem could not see it. The floor-verifier later
confirmed the blocking call was compiled into the shipped `NpcMemory.Core.dll`, not merely present
in source. Same rule as the ConfigureAwait removal, one more instance.

### Standing consequences

- **`ruff` is pinned** (`ruff==0.15.21`) and `ruff check` now gates on every edit alongside
  `ruff format`. Rules live in `ruff.toml`, deliberately at ruff's default set — widening it would
  be a style ruling, and style rulings are Jack's. `target-version` is deliberately **unset**: at
  py314 the formatter applies PEP 758 and strips the parentheses from `except (A, B):`, which is
  valid on 3.14, a syntax error before it, and an unrequested rewrite of floor-verified files.
  That hazard fired during this very pass and shipped one file before the floor-verifier caught
  it; `tests\test_repo_hygiene.py` now guards it mechanically, because neither `ruff check` nor
  `ruff format --check` flags it.
- **`.gitattributes` now pins line endings** (`* text=auto eol=lf`). The repo had none, so
  normalization depended on each machine's `core.autocrlf`, and a two-line docs edit rendered as a
  971-line rewrite.
- **The IDs-and-scores invariant is scoped, not weakened.** It now reads "read endpoints **that
  run retrieval**", with the two unscored inspector reads named as the ruled carve-out. It had
  been false as written since 2026-07-27 in three files, one of them auto-loaded `CLAUDE.md`.
- **The model-role claim is corrected in both CLAUDE.md and architecture.md.** Seven env vars, not
  nine roles each independently upgradable: importance/render/typology must name the same model
  (one write call serves all three; `load_settings` raises rather than picking), and
  reputation-delta emission has no role — it rides `behavior`.

## Reconstruction model class + migration immutability — 2026-07-28

Two rulings from the close of the full-repo audit session, both on findings that pass surfaced.

### 1. Reconstruction stays Haiku-class

**Decided:** `LONGMEM_MODEL_RECONSTRUCTION` is **Haiku-class**. The register was right; the
shipped configuration had drifted.

**What happened:** on 2026-07-21 the var was found missing from `.env` mid-session and set to
`claude-sonnet-5` to unblock a real-mode run. That was a stopgap, not a class decision, but it
was never revisited and never reached the register — so for a week `decisions.md`
("Reconstruction serving: batched Haiku"), `architecture.md` §7, `reconstruction.md` and
`app\config.py`'s docstring all said Haiku while the service ran Sonnet. The 2026-07-28 doc audit
caught the split; Jack confirmed Haiku.

**Rejected:** promoting the stopgap to the role's class. Batched retelling of already-selected,
gist-constrained material is a Haiku job — the quality argument for Sonnet was never made, only
inherited by accident.

**Consequence to propagate — and the reason this entry matters more than a one-line config fix:**
**every real-mode reconstruction measurement on record was taken against sonnet-5.** That includes
the **16.3 s cold-reconstruction figure** (quoted in `unity-client.md`'s timeout rationale and in
the warm-init choreography), the reconstruction rows of the `$0.44/100-turn` cost table, and the
drift-refusal rate. They are stale in the *conservative* direction — Haiku should be faster and
cheaper — so nothing built on them is unsafe, but **they must not be quoted in the demo or the
interview until re-measured.** Queued as pre-ship item **(b2)**, alongside the B1/B2 latency
experiments since it is the same harness and the same session. The one place this could be a real
regression rather than bookkeeping is drift quality: the 0.35 budget's refusal rate was measured
on Sonnet retellings, and a smaller model may sit differently against it.

*(`.env.example` corrected here. The operator's own `.env` is the one thing this repo cannot fix
for itself — that edit is Jack's, and until it lands the running service is still on sonnet-5.)*

### 2. Applied migrations are immutable

**Decided:** once a migration has been applied and recorded in `schema_migrations`, its file is
**immutable — including comments.** A correction goes in a new numbered migration, or in the docs
that reference it, never by editing the applied file.

**Why it came up:** the audit's own path rewrite edited the header comment of
`db\migrations\004_lexical_index.sql`, a file already applied. The floor-verifier flagged it:
`db\migrate.py` has no checksum, so nothing would ever detect a silent rewrite of an applied
migration, and the ledger's attestation is only as good as the bytes it attested to. The file was
restored byte-identical before this ruling was taken.

**Consequence:** the rule is now stated in `CLAUDE.md` beside the numbered-migration rule it
extends. The stale path in 004's comment stays stale on purpose, explained in
`docs\research\README.md`. Enforcement is convention, not machinery — a checksum column in
`schema_migrations` would make it mechanical, and is deliberately **not** built here: it is a
schema change to the ledger itself, which wants its own scoped task rather than riding an audit.

## Floors-register append-only scope — 2026-07-29

**Decided:** `docs\floors.md`'s append-only rule protects the **table rows** — a landed floor
row is never edited except a dated supersede note. Prose elsewhere in the file, including the
"Re-verification passes" notes, is a living record: a confirmed error there is corrected **in
place**, dated by the correcting session.

**Rejected:** dated-correction-note-only (append a note, leave the wrong figure standing) and
leave-as-is (session-log-only).

**Context:** the 2026-07-28 re-verification note records the console interop gate at 21/21;
source has 23 deterministic checks and a fresh 2026-07-29 live run measured **23/23** (the [11]
client-timing checks landed mid-audit, after that note's gate run). The correction itself rides
the re-audit continuation (status.md queue item 0.5), not this wrap-up.

**Consequences to propagate:** nothing states the old position as policy; the fix targets when
the continuation lands are `docs\floors.md` (the 21/21 figure in the re-verification note) and
`docs\SETUP.md:192` (the same stale 21).

## Haiku dialogue + quote-embargo lift — 2026-07-29

**Decided (three rulings, one measurement session):**

1. **The dialogue role ships Haiku-class for now** (`LONGMEM_MODEL_DIALOGUE=
   claude-haiku-4-5-20251001`, priced 1.00/5.00). Basis: the B1 A/B — product driver, 6×10
   turns, seed 7, same-day arms — put `perceived_first_word` (the <1 s bar's field) at p50/p95
   951/1701 ms on haiku vs 1201/2775 on sonnet-5: haiku meets the bar at p50, sonnet-5 does
   not, at $0.109 vs $0.415 dialogue cost per 100 turns.
2. **The quote embargo on real-mode reconstruction numbers is lifted.** The (b2) re-measure
   replaced every stale sonnet-5 figure with Haiku-measured ones (cold batch 8.1 s headline,
   3.3–8.6 s across the cold snaps; drift p50 0.107 / max 0.192, zero over the 0.35 budget,
   zero refusals in 32 attempts). These are the quotable demo/interview numbers.
3. **Sonnet-5 dialogue and the B2 thinking-off variants are deferred to the judged-eval
   harness** (immediate-queue item 3): re-assess both once prose quality can actually be
   scored. B2 stays unmeasured by design until then. The model-decision task is CLOSED for now.

**Rejected:** ruling on prose quality from latency/cost numbers alone (the A/B deliberately
measured no quality — the eval harness is that instrument); measuring B2 now (moot while the
bar is already met and prose can't be judged).

**Context:** the 2026-07-29 measurement session (session log). One analysis caveat rides with
the A/B: the USD gap compounds the 3× rate difference with a ~1.36× tokenizer difference —
sonnet-5 tokenizes the same prompts higher — so token columns are never comparable across
models; compare USD computed from each model's own counts at its own rates.

**Consequences to propagate:** `.env` (switched live, booleans-only script) and `.env.example`
(dated comment) — done with this entry; the `architecture.md` roles line — which was ALSO still
claiming Sonnet-class for reconstruction, a 2026-07-28 propagation miss — now dated and fixed,
plus its §7 embargo sentence resolved; `unity-client.md`'s init-timeout annotation re-pointed
at the Haiku numbers; `status.md` rows (b)/(b2). Deliberately NOT changed: the v1 `sonnet_*`
wire-instrumentation names (`app\schemas.py` keeps them by an in-line kept-names note; the C#
client mirrors them field-for-field) — renaming that contract would be its own scoped task.

## Stage-2 Play-mode gate verification + real-mode corroboration — 2026-07-29

**Decided (one ruling, one verification session):**

1. **The stage-2 Unity Play-mode gate runs fake-mode as the gate-of-record, AND a real-mode pass is
   run alongside it.** Asked at plan approval whether to run only the documented fake-mode gate or
   also a real-mode pass, Jack ruled **also a real-mode pass**. Basis: fake-mode streaming is fast
   enough to *mask* the SSE main-thread stall the plugin DLL was rebuilt to fix — check #8
   (frame-pump) passed 8/8 in fake mode even with that bug historically present — so only real
   inter-chunk gaps actually exercise the fix.

**Outcome:** both passed **8/8** through the MCP-for-Unity bridge (fake-mode gate-of-record +
independent floor-verifier live re-run; real-mode corroboration). Check #8 read +11/+12 frames in
fake mode vs **+1061 frames** in real mode — the real pass is the genuine regression test the fake
path cannot be. The gate landed as floor row 19 (`floors.md`); DLL build-identity provenance
re-proven (150 build-identity bytes vs a fresh HEAD build, no source/binary drift).

**Context:** the gate was the one verification outstanding before demo recording, reported
**blocked** on 2026-07-29 by session-start ordering (the session began before the Unity Editor
opened, so no `mcp__UnityMCP__*` tools registered). Cleared by opening Unity first — the bridge
reached both the main loop and the floor-verifier subagent. Root cause named, not worked around.

**Still surfaced (not ruled, not fixed here):** the `~\.claude.json` duplicate repo keys — the empty
backslash key is the latent re-trigger of this exact blocker (cleaning it prevents recurrence); and
the committed plugin DLL still has no automated staleness guard (it is proven current by manual
byte-diff each time). Two non-blocking gate soft spots recorded in `floors.md` row 19: check #1 is a
guarded `Check(true,…)` and directive/reputation callbacks are subscribed-but-not-asserted
(delegated to the stage-1 console floor).

## Eval-harness v1 plan rulings + stage-1 build — 2026-07-29

**Decided (four plan-time rulings at plan approval, then stage 1 built and floor-verified the
same session; spec: `eval-harness.md` — immediate-queue item 3, chosen over
choreography-first because three deferred consumers wait on the harness — The Ledger's
on-screen numbers, the sonnet-5/B2 prose re-assessments, and R7's ablation data — while
nothing new waits on choreography):**

1. **The judge model role is eval-runner-only.** `LONGMEM_MODEL_JUDGE` +
   `LONGMEM_PRICE_JUDGE_IN/OUT` will exist (stage 3), but `load_settings` real mode stays
   seven-role — the server/REPL never requires a judge; the eval runner validates the var
   itself when a judged run starts. **Rejected:** an eighth mandatory real-mode role (the API
   server refusing to start without a judge model for pure gameplay). Precedent honored:
   roles arrive with their feature; the judge provider will NOT be a field on the frozen
   `Providers` bundle.
2. **v1 judged categories = core 3 + prose quality**: selective-forgetting (single/multi-hop),
   abstention/false-premise, reconstruction-faithfulness (FactScore retargeted), plus the
   prose-quality pairwise rubric — the instrument the 2026-07-29 sonnet-5/B2 deferrals
   explicitly wait on. **Rejected:** the full starter list in v1 (FAMA stale-leakage +
   MemTrace trajectory probe deferred); core-3-only (would leave the prose re-assessment
   blocked).
3. **The Ledger binding is a new small read route** —
   `GET /v1/memories/{id}/reconstruction-metrics`, computed server-side (detail-recall needs
   spaCy lemmas; client JS cannot). **Rejected:** folding metrics into `/chain` (amends a
   route whose unscored-by-contract wording was ruled 2026-07-27); compute-and-paste (the
   on-screen number would not be live). Consequence: the unscored-reads carve-out now has a
   **third member** — the metric read runs no retrieval and returns IDs + numbers
   (CLAUDE.md wording grown in-pass).
4. **No new migration** — the explicit per-target scope fact the schema-evolution rule
   requires: scenarios/gold/corpora are repo files (`data\eval\`, stages 2–3), run artifacts
   are JSON files, nothing eval-related persists in Postgres; runs use disposable pid-scoped
   scratch DBs. **Rejected:** an `eval_runs` table (migration 006 — durable run history not
   worth re-opening the frozen ledger for v1).

**Build record (stage 1, same session):** the judge-free metric layer + the metrics route +
The Ledger binding landed and floor-verified — `floors.md` row 20 carries the evidence (suite
55 → 63 with Set G, keyless subset 48 → 53, interop gate 23 → 24, walkers 56/42, zero-write
proven three ways, live browser beat). Stage-1 physical shapes settled at build under the
spec's latitude: the wire payload omits `identity_version` (a metric input, not an output);
unmeasurable gist facts (empty lemma sets) are excluded from both sides of the ratio —
**honest denominators return `None`, never a flattering 1.0** (the thin-gist lesson made a
metric contract); keyword-retention entities are recomputed via `extract_entities` rather
than read from the stored write-time merge. Twelve forks recorded in the spec's
settle-at-build table — forks 1 (C# mirror), 2 (threshold 1.0), and 6 (live head only) closed
with stage 1; 3–5, 7–12 stay open for stages 2–4 with recommendations stated (notably fork 11,
caught at plan verification: the ablation OFF arm must exclude authorial-correction-anchored
chains, whose gist slot IS the corrected head — blanking it would delete the correction).

## Scope consolidation + road-to-completion rulings — 2026-08-04

**Decided (planning session — Jack judged the remaining scope disorganized and re-planned it end
to end from his own draft schedule; no code changed; the resulting phased roadmap lives in
`status.md`):**

1. **The research track is scrapped entirely.** No formal write-up, no submission. The end
   products are exactly three: the demo video, a Unity Package + one-command backend spin-up
   (ruling 8), and the public GitHub repo. Dies with it: the asymmetry ablation and the judged
   drift / Bartlett-style evals. **Survives it (ruled explicitly):** the eval-harness stage-4
   fixed-gist ON/OFF ablation — it answers the engineering question R7 (drift-budget
   soundness), not a research question.
2. **The behavior/action side of split-brain is scrapped entirely; reputation is scrapped with
   it.** Deciding actions belongs to the game developer, not this project; the NPC's own
   actions arrive as ordinary observes (the game-authored action-observe contract). Removed
   when the re-shape lands (roadmap A1): the behavior call and model role (real mode 7 → 6
   roles), the action directive, the divergence record (and its separate interview clip —
   accepted), and the reputation system whole — delta emission, the sanctioned in-place
   `agents.reputation` apply, wire fields, boundary snapshot, C#/Unity callbacks. The
   `agents.reputation` column stays in the schema (applied migrations are immutable) but goes
   unread. **The hidden-weights idea survives, moved to the speech side:** `weight_overrides`
   will re-rank the view feeding the *prose* prompt — the NPC's words shaped by weights it is
   unaware of. This deliberately inverts the 2026-07-21 topology (speak-honest / act-weighted);
   supersedes the split-brain portions of the 2026-07-21 latency-slate + build rulings and the
   2026-07-22 interview-clip ruling.
3. **The mid-to-late-August demo date is dropped.** The demo lands after the build phases
   (roadmap A–D). Flagged in review as colliding with the re-planned scope; Jack ruled the move
   acceptable — an explicit re-ruling of the deadline framing, not deadline-driven drift.
4. **Cut from scope:** graph/associative memory (ruled too large a task for not enough
   benefit), recall-reinforced decay, automatic conflict/staleness detection, habituation, the
   Whisper soft-steering hook + safe-default action fallback, and the optional/stretch list
   (disclosure gate, faithful-vs-reconstructive dual read modes, local-model packaging, the
   dormant-agent overseer, the full modulator suite). The reflection → parameter compiler
   itself SURVIVES (roadmap C3); only the suite extension is cut.
5. **Kept and confirmed by name:** reflection (+ compiler), Engram-style deferred write
   processing, the dissonance path + diegetic-correction event as ONE working session, the
   agent-state read route, the identity authoring guide, async observes as its own explicit
   client task (Jack had assumed it rode "deferred write processing"; ruled in explicitly), the
   purge endpoint (release-blocker reconfirmed), the latency trio (concurrency cap, background
   pre-warm, prompt caching), and eval-harness stages 2–4. The three audit-surfaced hygiene
   items — the "what this is not" auth/rate-limit paragraph, the Unity MCP pin +
   manifest/lockfile reconciliation, and the committed-DLL staleness check — are ruled INTO
   cleanup-and-packaging by name (roadmap Phase F).
6. **The real-game plug-in clip is an optional epilogue** — time-permitting, explicitly
   droppable (roadmap Phase G).
7. **Ordering is delegated to Claude on efficiency grounds — for the whole schedule.** Jack's
   stated purpose: which tasks are in, which are out, and a visible path to the end; ordering
   is not of primary concern. Resulting order (rationale recorded with the roadmap): A re-shape
   → B measurement rig → C components → D optimization → E demo → F release → G epilogue.
8. **The packaged end product is defined:** a Unity Package Manager package + a one-command
   backend spin-up.

**Not ruled (deliberately):** the walkers' shared fixed-name scratch-DB refactor stays on the
"carried, not fixed" list awaiting its own ruling — surfaced in review, left unscheduled.

**Consequences to propagate:** `status.md` rewritten around the roadmap (the superseded queues,
ledgers, deadline framing, and dated narrative moved verbatim to `session-log.md`'s archive);
CLAUDE.md's seven-role and reputation-carve-out wording deliberately NOT edited now — it stays
true until the Phase A re-shape lands, and A1 owns that edit.

## A1 split-brain removal + weights-on-speech — spec forks + build record — 2026-08-04

The A1 re-shape (ruling 2 of the scope-consolidation entry above) was specced, built, and
verified in one session. Four forks were settled by Jack at spec time (explicit questions at
plan approval), and the build settled the seam-design details below.

**The four spec rulings (Jack, 2026-08-04):**

1. **Weights are a post-cut re-rank at the dialogue seam.** The split-brain behavior view's
   exponent mechanics move over verbatim — resolution request field → `agents.config` → 1.0;
   clamp [0.0, 4.0]; `weighted_score = item.score · rel^(w_rel−1) · rec^(w_rec−1) ·
   imp^(w_imp−1)` with the zero-base guard; ties on `memory_id` — now re-ranking the served
   view that feeds the PROSE prompt. Retrieval code stays byte-identical; **membership never
   changes** (weights re-order the served top-k, they cannot pull in an excluded memory). The
   pre-cut alternative (weights inside retrieval scoring, changing which memories serve) was
   surfaced with its cost and declined.
2. **The recent-actions channel is removed entirely** — the `recent_actions` request field, the
   `[recent actions]` prose-prompt block, the `RecentAction` models (Python + C#), the
   `recent_actions_cap` knob, and the C# `RecentActions` surface. The game-authored
   action-observe contract (2026-07-21) is the ONE channel for NPC deeds; same-scene immediacy
   gets settled at C1's un-enriched-window fork, not by a second channel.
3. **The provisioning surface is stripped too.** `POST /v1/agents` stops accepting/echoing
   `reputation` + `reputation_sensitivity` (both dropped from the `insert_agent` INSERT column
   list — the columns stay in the schema, applied migrations being immutable, but are never
   written or read), and the four reputation knobs (`reputation_scale_min/max`,
   `reputation_neutral`, `reputation_sensitivity_default`) leave `SERVICE_DEFAULTS`. The
   2026-08-04 ruling's "goes unread" covers both columns.
4. **`DialogueInitRequest.weight_overrides` is removed** (reserved 2026-07-14, inert ever
   since). The turn-side field covers the whole merged view; an accepted-but-ignored field is
   the silent-no-op trap. The read-path walker's criterion [7] re-scopes to assert the field's
   absence.

**Seam-design rulings settled at build:**

- **`items` vs `dialogue_view`.** `items` stays the raw retrieval echo (served order + scores —
  the IDs+scores invariant rides on it, byte-untouched by weights). `dialogue_view` changes
  meaning: the weight-ranked view the prose prompt was built from, sorted `(-score,
  memory_id)`. On a **loader turn at all-1.0 weights** it equals the (id, score) projection of
  `items` — the parity contract carried over. On gated turns `items` keeps the loaded+fetched
  serve shape while `dialogue_view` is the global weight ranking. `behavior_view` is gone.
- **Gated-turn prompt precedence.** The prompt's `[memories]` block still renders the loaded
  set in the caller's append-only order (the 2026-07-19 byte-stable-prefix ruling stands); the
  weighted order is fully visible on loader turns and among gate-fetched items on gated turns.
- **Renames** (mechanics byte-preserved): `resolve_behavior_weights → resolve_dialogue_weights`,
  `behavior_score → weighted_score`, `rank_behavior_view → rank_dialogue_view`,
  `BEHAVIOR_WEIGHT_MIN/MAX → WEIGHT_MIN/MAX`, knobs `behavior_weight_* → weight_*` (defaults
  1.0 unchanged; pre-release, no external configs to break).
- **Wire hygiene stance:** pydantic's default `extra="ignore"` means a stale client sending the
  dead fields gets a 200 with the fields silently dropped — accepted, no 422 hardening in A1.
- **A dialogue turn persists nothing.** The sanctioned in-place `agents.reputation` UPDATE left
  with the re-shape; `apply_reputation_delta` is deleted; the invariant carve-out shrinks to
  the one runtime scalar `memories.pinned` (CLAUDE.md updated in this session, as the
  scope-consolidation entry assigned).
- **The interop gate stays at 24 checks, different composition:** the divergence beat and the
  reputation-callbacks check died; a weights-on-speech pair replaced them — [10a] parity
  (DialogueView == Items projection, loader turn by construction) and [10b] re-rank (a
  `Recency = 0.0` override over an utterance aimed at an old memory: same id set, provably new
  order — the flip is structural: the base ranking is recency-dominated at t0+92d while
  relevance favors the 94-day-old toll observe).

**Verified this session:** ruff clean; suite subset 53 green at every stage end; full suite
63/63; all seven walkers green against `longmem_test` (CLI walker rewritten 67 → 51 assertions;
read-path 56 with criterion [7] re-scoped; write-path 53 with the provisioning asserts
re-pointed; gate 51 — its three `assemble_prose_prompt` call sites updated to the new
signature; reconstruction 42 / authorial 34 / fact 34 with shrunk fixture INSERTs);
`db\smoke_test.py` green with the shrunk INSERT; the C# interop gate **24/24** live against a
served fake-mode backend; the Release DLL rebuilt and copied to
`unity\Assets\Plugins\NpcMemory\`. **Pending:** the Unity Play-mode gate re-run (the adapter
and demo driver shrank; the 8/8 beats assert nothing behavior/reputation-shaped, so compile +
re-run is the remaining proof) — blocked this session because the Unity Editor was not open, so
no `mcp__UnityMCP` tools registered; runs at the next editor session.

**Supersedes:** the split-brain portions of the 2026-07-21 "Latency slate + split-brain
pull-forward rulings" and "Split-brain streaming build rulings" entries (the streaming seam,
latency terms, and game-authored action observes stand; the behavior call, directive,
divergence record, recent-actions block, and per-call weights-on-the-behavior-view are
replaced); the 2026-07-15 reputation rulings in the CLI-harness build entry (apply formula,
snapshot plumbing, sensitivity resolution — all removed); the 2026-07-14 read-path ruling 8's
reserved init-side `weight_overrides` slot (removed). `split-brain-streaming.md` carries the
retirement banner; `architecture.md` §9 is the living seam statement.

## Eval-harness stage 2 — session rulings + build record — 2026-08-05

**Context.** Phase B1 of the road-to-completion roadmap: eval-harness stage 2 — the runner
core — built to the 2026-07-29 spec's stage-2 contract paragraph verbatim (`eval-harness.md`;
now carrying its dated BUILT banner). The session opened by closing A1's one pending proof:
the Unity Play-mode gate re-ran **8/8 GREEN** fake-mode through the MCP bridge (Editor open
before session start; the dated resolution notes on `floors.md` rows 19/21). Four forks
settled at plan approval — all recommended options taken first pass.

1. **Unity gate re-run scope: fake-mode 8/8 only.** The fake gate is the gate-of-record; the
   original real-mode pass's unique evidence (+1061 frames through real SSE chunk gaps)
   tested streaming code A1 did not change, and the committed DLL is sha256-identical to a
   fresh Release build of the tree. **Rejected:** repeating the real corroboration pass —
   spend without new evidence.

2. **`drift-validate` gates on full real provider mode, with `--plumbing`.** The verb's
   construct is real-retelling drift under real embeddings; an embeddings-only narrow path
   (OpenAI key without the six model roles) would measure fake retellings — which
   deliberately hug their anchors — under real embeddings, a construct mismatch, and the
   write pass ingesting the corpus needs the real write model anyway. `--plumbing` permits
   fake mode with the report labeled `plumbing_only: true` — the stage-3 `--judged` labeling
   pattern pulled one stage forward; no new provider mode exists. **Rejected:** the
   embeddings-only path.

3. **One real-mode `drift-validate` run this session.** Proven on the fixture corpus
   (7 authored observes aged 30 days): **7/7 items checked, 0 over budget — distance p50
   0.030 / p95 0.100 / max 0.120** against threshold 0.35, `drift_refusals` self-check
   exact. The numbers live in the stage-2 BUILT banner; the run artifact is gitignored
   (fork 7's discipline). **Rejected:** plumbing-only this session (first real numbers
   waiting on stage 3).

4. **Expected-IDs checks are membership-only.** `present`/`absent` observe ordinals scored
   against `DialogueTurnResult.items` — the raw retrieval echo; the A1 seam contract makes
   membership weight-invariant (weights re-order, never admit or evict). **Rejected for
   v1:** ordered/top-1 assertions — rank under hash-derived fake importance is fragile, and
   the schema can grow an ordering vocabulary additively later.

**Spec fork-table rows settled (stage 2).** Fork 7: run artifacts **gitignored**
(`data/eval/runs/` in `.gitignore`) + milestone numbers quoted into dated doc entries.
Fork 8: conftest adoption of `provision_scratch` **deferred** — the suite's fixture spine is
byte-untouched (the `tests\scratch_uri.py` re-export shim keeps conftest and all seven
walkers unmodified). Fork 10: the drift corpus is the scenario schema's **observe/as_of
subset through the one loader**, with `assert_corpus_shape` stating the restriction.

**Build latitude (the stage-2 [SETTLE-AT-BUILD] shapes, recorded with rationale in the
spec's settled-shapes paragraph):** argparse subparsers for verb dispatch (first use in the
repo); `extra="forbid"` + tz-aware datetime validators across the scenario schema;
`drift_observer`'s third argument = `refused` (`distance > threshold`, computed exactly
where the serving decision is made; the blind embed-failure refusal path never calls the
observer); one scratch DB per invocation with a fresh agent per scenario; exit codes
(`run` 0/1; `drift-validate` 0/1/2 with 2 = the mode-gate refusal); defaults
`--age-days 30` + a plain coverage probe; fixture scoring pinned by explicit config facts —
`importance_norm_floor: 1.0` + `decay_k_importance: 0.0` neutralize hash-derived fake
importance so expected-ID cuts ride pure fake-embedding similarity (the first fake run
exposed two k-cut flips before the pin; the pinned run is deterministic, proven twice
byte-identical).

**Floor:** the twenty-second `floors.md` row — independent floor-verifier pass (suite 72 +
keyless 61, walkers 42 + 56, fake e2e 6/6 twice, plumbing 7/7 + the exit-2 refusal, the
TEST-NET no-dial-out refusal proof, live `longmem` pristine, ledger exactly 001–005, no
scratch DB left behind).
## Eval-harness stage 3 — session rulings + build record — 2026-08-07

**Context.** Phase B2 of the road-to-completion roadmap: eval-harness stage 3 — the judge
layer — built to the 2026-07-29 spec's stage-3 contract paragraph with one API-forced
correction (below). Four forks settled at plan approval (the AskUserQuestion batch; three
recommended options taken, one re-recommended and taken).

1. **The judge model is Opus 4.8** (`LONGMEM_MODEL_JUDGE=claude-opus-4-8`, fork 3). The
   spec's sonnet-class recommendation collided with the judge's FIRST real use — the queued
   haiku-vs-sonnet-5 prose check — where a sonnet judge would grade its own model's prose.
   An Opus judge grades neither compare arm's class; verdict calls are short JSON, so the
   higher rate stays small in absolute terms. **Rejected:** sonnet-class (self-preference on
   the sonnet arm, mitigated only by position-swap/tie); haiku-class (self-grades the haiku
   arm instead, and a weaker judge risks failing the kappa bar).

2. **The dialogue thinking knob is built NOW** (`LONGMEM_DIALOGUE_THINKING`; the queued "B2
   thinking-off variants — measure or drop" resolves to MEASURE). `compare` is specced as
   "A/B over two env overlays," but thinking-off had no lever in code — the real prose
   provider never sent a `thinking` parameter. The knob (`""` = the parameter omitted, the
   pre-B2 request byte-for-byte; `"disabled"` = thinking off — sonnet-5 accepts it) makes
   the variant expressible as a pure env overlay; committed arm file
   `data\eval\arms\sonnet5-thinking-off.json`. **Rejected:** deferring the variants (leaves
   the queued measurement blocked on another scoped task); dropping them (the lever is the
   answer to "does sonnet-5 prose justify its latency?" if the pairwise verdict favors it).

3. **Sequencing: build + verify + real judged smoke + emit-gold THIS session; Jack labels
   offline; `agreement` + the real haiku-vs-sonnet `compare` open the next session.** The
   gold set needs 78 hand labels before judged numbers are quotable, and the verbs are
   built and fake-tested now either way. **Rejected:** everything-this-session (blocks
   mid-session on Jack's labeling availability); build-only (defers the one real smoke whose
   artifact IS the gold-candidate source).

4. **The three remaining spec knobs as recommended:** agreement bar kappa >= 0.6 per
   category, shipped as `agreement --kappa-bar` (default 0.6) — an undefined kappa
   (degenerate marginals) honestly fails the bar (fork 5); prose-quality dimensions
   naturalness / character-consistency / memory-grounding / brevity, each 1-5, plus an
   overall a/b/tie preference (fork 9); gold-set size ~20-30 items/category via
   `emit-gold --limit-per-category` default 30 (fork 12).

**The API-forced spec correction (dated in place in `eval-harness.md`).** The stage-3
contract specced the real judge at "temperature 0" — unimplementable on the ruled
Opus-4.8-class judge: the 4.7+ API rejects `temperature`/`top_p`/`top_k` outright (400) and
`budget_tokens` with them. `RealJudgeProvider` runs `thinking={"type": "adaptive"}` (verdict
quality matters for the kappa bar; verdicts are short so the thinking spend is small) with NO
sampling parameters; the rubric's JSON-only output contract carries determinism instead. The
same pass corrects the spec's stale "seven-role" wording (written before A1 removed the
behavior role): real mode requires six roles, the judge never among them — the substance of
the 2026-07-29 eval-runner-only ruling is unchanged and now enforced by Set I's config
regression test.

**Build latitude (the stage-3 [SETTLE-AT-BUILD] shapes, recorded with rationale in the
spec's settled-shapes paragraph):** prose capture is judged-runs-only — the plain `run`
artifact stays byte-untouched (proven against stage 2's own comparison basis), with the one
all-runs addition being the `models` provenance block (without it two compare arms are
indistinguishable after the fact; `drift-validate` deliberately unstamped — its floor is
byte-level); faithfulness judges only `live_write_cause == "reconstruction"` memories
(others counted `skipped_not_reconstructed`) and sees ALL merged-span gist facts — no
lemma-measurability filter, which is a lexical-metric artifact (the judge does semantic
support); `LONGMEM_JUDGE_MAX_TOKENS` is a Settings/env knob (default 2048), not an
`agent_knob` — service-scoped eval config, not per-agent policy; a compare arm is a JSON
file `{"name", "env"}` whose overlay may vary the six role vars, the thinking knob, and
prices — mode, database, API keys, and the judge are refused (an arm varies the system
under test, never the instrument), and each arm carries its OWN dialogue prices, honoring
the 2026-07-29 cross-model USD caveat by construction (sonnet-5's intro pricing through
2026-08-31 is noted in the committed arm files; the billed rate is Jack's env choice);
judged outcomes never change `run`/`compare` exit codes (structural-checks-only 0/1; 2 =
the gate refusal, the drift-validate pattern); `emit-gold` strips verdicts (blind labeling;
`item_id` joins back) and skips `judge_failed` items; pairwise prose is two calls per pair —
true order + position-swapped — disagreement => tie, per-arm scores averaged over both
positions, `degraded_either` flagged; Cohen's kappa is hand-rolled pure arithmetic (no
sklearn dependency) with honest-None on empty/degenerate denominators; the `JudgeProvider`
protocol carries `category`/`n_facts` structurally so the deterministic fake emits
shape-conformant verdicts (the `ReconstructionItem` precedent — a mild wart, accepted).

**The real judged smoke (the session's one intended real spend, ~$0.58 of the $2 budget).**
`run --judged` over `smoke.jsonl` + `judged.jsonl` (12 scenarios, 62 turns, 44 observes,
0 degraded, 6/6 structural checks): **0 `judge_failed` across all 78 verdict items** —
selective-forgetting 18/24 pass, abstention 23/24, reconstruction-faithfulness 88/89 facts
supported with 63 fabricated-claim flags; 7 never-reconstructed memories honestly skipped;
judge spend 36,784/8,574 tokens ($0.398), ~2.8 s per verdict. *Pre-agreement readings —
quotable only past the kappa bar.* The instrument's first run already earned it: lexical
gist-precision 0.765 vs the judge's semantic support 0.9888 (the paraphrase-slack gap the
spec predicted), and 63 judged embellishment flags where the lexical entity-detector saw 2.
Gold candidates emitted blind to `data\eval\gold\candidates-2026-08-07.jsonl` (78 rows:
24 sf / 24 abstention / 30 faithfulness facts of 89, fork-12 cap; prose-pairwise gold
arrives with the first real compare) — Jack labels from the gold file only; the artifact
holds the verdicts.

**Floor:** the twenty-third `floors.md` row — independent floor-verifier pass, 12/12 (suite
86 + keyless 74; walkers 53/56/42/51 with the other three byte-identical by git diff; fake
e2e 6/6 twice identical with the plain artifact judged-free; the exit-2 gate code-confirmed
BEFORE provisioning; plumbing + compare + agreement all exercised; the real artifact re-read
number-for-number; gold blind; `longmem` pristine, ledger 001-005, no scratch residue).

## Unity state is ordinary repo state — 2026-08-07

**Ruled (Jack, at B2 wrap-up).** Unity exists on this laptop solely to serve this project —
treat the Unity project as an extension of the repo, never a surface preserved for other
work: save, clean, edit, and commit Unity assets and scenes as the work needs, like any
other tracked file.

**Immediate consequence:** the dirty `unity\Assets\Scenes\SampleScene.unity` — A1-removal
serialization fallout from an Editor save; three stale serialized fields dropped
(`directiveFlashTarget`, `initialReputationSnapshot`, `actionVocabulary`) with `autoRun: 0`
preserved — is committed rather than held out (it had been deliberately excluded from the
B2 commit pending this call). Editor console verified clean at commit time.

**Scope note:** the earlier per-session "scene NOT saved" clauses (the stage-2 Unity gate
and A1 floor evidence cells) were verification-discipline snapshots of those sessions —
proofs that the gate run itself perturbed nothing — not a standing keep-the-scene-pristine
rule; they are superseded only to the extent anyone read them as one. Gate re-runs still
avoid *incidental* scene writes during verification, but a deliberate, inspected scene save
is now ordinary work.

## Gold-label workaround + measurement-line rulings — 2026-08-12

**Context.** The queued session-opener was Jack's offline hand-labeling of the 78 blind gold
rows. Jack ruled he cannot make time for it and directed a workaround that keeps the line
moving. Plan-approval exploration also surfaced an independent structural blocker no labeler
could have fixed: the judge's own verdicts on the emitted candidates are one-sided
(reconstruction-faithfulness 30/30 `supported`, abstention 23/24 `pass`), so Cohen's kappa for
those two categories is undefined-or-zero by arithmetic **regardless of who labels** — the
hand-labeling plan would have hit this wall too; `cohen_kappa`'s honest-None comment names the
fix ("class balance in the gold set"). Four forks settled at plan approval (the
AskUserQuestion batch; three recommended options taken, one alternative chosen).

1. **Reference labels come from a single careful model pass** (one fresh-context Claude
   Fable 5 subagent; blind — it receives the gold file and the rubric texts only, never the
   artifact, the verdicts, or the aggregate verdict distributions). The gold set's epistemic
   status changes from human-labeled to strong-model-labeled: `agreement` now measures
   judge-vs-reference-model concordance, not judge-vs-human, and the docs' "hand labels"
   wording is re-worded source-neutrally ("reference labels"). Jack's standing right to
   relabel is explicit — any row he later re-labels wins, and `agreement` re-runs in seconds.
   Rater class: Fable 5, because Opus is the judge's own class (self-agreement inflation) and
   haiku/sonnet-5 are the compare arms — the fork-3 logic applied to the rater. The
   2026-07-22 "hand-labeled gold set" intent (proven rigor for the LLM judge) is carried
   forward by ruling 2's constructed-truth rows, whose labels are independent of any model's
   judgment. **Rejected:** a three-rater panel with majority vote + inter-rater kappa (Jack
   chose the single pass); parking `agreement` until Jack can label (quotability blocked
   indefinitely).

2. **Class balance comes from a constructed-truth gold set** — a second, clearly-separated
   gold file of authored rows whose true labels are known **by construction**: perturbed
   tellings that contradict or fabricate against their gist fact (`unsupported`) beside
   faithful paraphrases (`supported`); replies that swallow a false premise (`fail`) beside
   correct abstentions/answers (`pass`). Class-BALANCED by design — one-sided construction
   would re-create the degenerate-kappa trap. A new small `judge-gold` verb (the sixth:
   gold-shaped rows in, real-judge verdicts out in an artifact-shaped JSON `agreement` can
   consume) grades them fresh; the resulting kappa measures **judge discrimination on known
   cases**, a stronger claim than concordance. Selective-forgetting is skipped — its natural
   marginals (18/6) already support a defined kappa. **Rejected:** naturals-only
   (rf/abstention stay unquotable until the system produces natural failures — the system
   passing is exactly what starves the gold set); re-emitting more facts (all 89 are still
   88/1 — no balance to be had).

3. **Scope: the full line runs in one autonomous pass** — labels → `agreement` → the
   constructed-truth round → BOTH queued compares (haiku vs sonnet-5, haiku vs
   sonnet-5-thinking-off; each vs the incumbent is the reading of the queued "± thinking-off"
   check) → the pairwise gold round → the B3 stage-4 ablation build. Stop-and-report on any
   bar failure, spec conflict, or ruling-shaped question. **R7's ruling and the
   dialogue-model re-ruling remain Jack's — this run delivers deciding data only.**
   **Rejected:** stopping after the compares (B3 held for its own session); agreement-only.

4. **Fork 11 (stage 4): correction-anchored chains are excluded from the ablation arms** —
   the spec's own recommendation — and at runtime a correction-anchored miss still
   reconstructs normally with the knob at 0 (blanking its gist would delete the correction
   itself). **Rejected:** a third arm measuring exactly that OFF behavior (answers a question
   R7 doesn't need, at ~+50% runtime); skipping those misses when OFF (correction chains
   would never reconstruct while the knob is 0, making the OFF arm less comparable).

**Preservation consequence:** the only real judged artifact —
`data\eval\runs\run_20260807T193049Z_pid_31688.json`, the file the gold labels join against —
was gitignored and single-copy (flagged at the 2026-08-07 wrap; losing it orphans the labels).
A curated copy now lives tracked at `data\eval\gold\run-2026-08-07-judged-artifact.json`;
`data\eval\runs\` itself stays gitignored (fork 7 stands).

**Supersession note:** this entry supersedes the 2026-08-07 stage-3 entry's sequencing clause
"Jack labels offline" (ruling 3 there). The substance of that ruling — labeling is blind, from
the gold file only, verdicts live in the artifact — is unchanged and enforced by the labeling
protocol above.

## Judge validation numbers — the agreement bar rules — 2026-08-12

**The instrument's meta-eval, run per the workaround entry above.** Two `agreement` runs, both
joins clean (0 unmatched, 0 unlabeled), reports under `data\eval\runs\` with the two artifacts
preserved tracked in `data\eval\gold\`.

**Naturals** (the 78-row blind gold file, single-pass Fable-5 reference labels vs the
2026-08-07 real smoke's Opus verdicts): **selective_forgetting kappa 0.7500** (n 24, raw
0.9167) — PASS; **abstention kappa 1.0000** (n 24, raw 1.0000; the reference pass and the
judge flagged the same single failure) — PASS; **reconstruction_faithfulness undefined —
degenerate marginals** (n 30, raw 1.0000, both raters all-`supported`) — FAIL by arithmetic,
the predicted outcome that motivated the constructed-truth ruling. Reference-label marginals:
sf 20/4, abstention 23/1, rf 30/0.

**Constructed truth** (`constructed-2026-08-12.jsonl`, 34 authored rows with labels true by
construction — rf 9 supported / 9 unsupported spanning contradiction, reversal, quantity
change, specifics-replacement, and omission; abstention 8 pass / 8 fail spanning invented
answers, wrong refusals, premise corrections, and correct answers — judged fresh by Opus 4.8
via `judge-gold`): **reconstruction_faithfulness kappa 1.0000 (n 18), abstention kappa 1.0000
(n 16), raw 1.0000 both — the judge discriminated every known case correctly.** Judge spend
13,654/3,779 tokens ($0.16), ~34 calls.

**Quotability, per category (the bar rules):** sf and abstention judged numbers are quotable
(naturals concordance ≥ 0.6, plus perfect abstention discrimination); rf judged numbers are
quotable **on the discrimination instrument's authority** — natural-rf concordance stays
honestly degenerate until the system produces natural failures, while the judge provably
detects contradiction, reversal, quantity drift, replacement, and omission when they exist.
The naturals `agreement` run exits 1 on the rf degeneracy by design; the constructed run
exits 0. Prose-pairwise gold has no instrument yet — it arrives with the first real compare
(fork 12), and its verdicts stay unquotable until that round's agreement passes.

**Process honesty note:** the intended fake-mode dry-run of `judge-gold` on the constructed
set became the real run — the live `.env` runs real mode and `--plumbing` *permits* fake,
never forces it. The mechanics had already been fake-verified by Set I's plumbing round-trip
test, the join check came back clean, and the spend ($0.16) sat inside the round's budget, so
the result stands as the real measurement rather than being re-bought.

## Eval-harness stage 4 — build record + R7's deciding data — 2026-08-12

**Context.** B3 of the roadmap, built the same session as the workaround entry above (scope
ruling 3 there authorized the full line). Spec: the stage-4 contract paragraph in
`eval-harness.md`; fork 11 ruled in the workaround entry (ruling 4). Floor: the twenty-fourth
`floors.md` row — independent floor-verifier pass, 7/7, every real-artifact aggregate
recomputed from the raw rows.

**Build latitude (the [SETTLE-AT-BUILD] shapes, recorded with rationale):** the runtime
knob-0 path for a correction-anchored miss is the PARTITION — serve() splits call slots into
a no-gist group and a normal group, so those chains always retell from the corrected head
(fork 11 applied to runtime, not only arm composition; the cheap skip-those-misses
alternative would leave correction chains never reconstructing while the knob is 0); the
paired report keys on `(scenario_id, memory_ref)` with both arms' memory UUIDs carried as
provenance — per-arm UUIDs differ across scratch DBs, so the contract's `memory_id` pairing
is only realizable through the ref; the knob is deliberately NOT in `compose_cache_key`
(arms live on separate scratch DBs; a live mid-process flip could serve stale-keyed text —
flip at provisioning boundaries, never mid-scene); the drift-validate replay core was
extracted as `replay_aged_probe` and shared (behavior preserved — stage-2 tests and the
42-assertion reconstruction walker re-run green by the floor-verifier); the corpus
(`ablation-fixture.jsonl`, 3 × 8 observes, two `as_of` clusters) pins BOTH decay classes to
2160000.0 + `decay_k_importance` 0.0 so bands are deterministic and identical across arms
(measured: bands 2 and 3, 0 mismatches in 24 pairs).

**R7's deciding data (the first real run; artifact numbers quoted per fork 7, re-verified by
the floor-verifier):** 24/24 paired and drift-checked in both arms. Cosine drift
candidate-vs-anchor: gist-ON p50 0.05 / p95 0.16 / max 0.1748; gist-OFF p50 0.04 / p95 0.15 /
max 0.1594; mean paired |Δ| 0.056; **zero over-budget items in either arm against the 0.35
threshold.** Gist-precision mean: **0.8335 with the constraint ON vs 0.7036 with it OFF.**
Lexical fabrication rate 0.0 in both arms (the stage-3 63-vs-2 finding already established
that detector's bluntness — semantic fabrication is the judge's surface).

**What the data says (the ruling itself stays OPEN — Jack's):** the drift budget is blind to
the gist constraint. Retellings produced WITHOUT the fixed-facts constraint drift no further
in embedding space than constrained ones — every unconstrained retelling sailed far under
the 0.35 budget — while content-level faithfulness measurably degrades (13 points of
gist-precision). R7's 2026-07-22 concern is confirmed by construction: the budget cannot
catch a retelling that stays in the anchor's semantic neighborhood while dropping or
altering fixed facts. The candidate resolutions (metric change, threshold change, or the
layered answer — budget for embedding drift + gist-precision/judged faithfulness for
content) are Jack's to weigh; every option's measurement instrument now exists and is
validated.

*(Ruled the same day — the entry below.)*

## R7 resolved — the drift budget is a topic guard, not a fact guard — 2026-08-12

**Ruled (Jack, on the stage-4 ablation's deciding data — the entry above).** The drift-budget
check STAYS, mechanism and threshold unchanged (cosine candidate-vs-anchor, refuse past 0.35,
the 2026-07-17 ruling's machinery intact) — but its CLAIM is re-scoped to what the ablation
measured it to be: **a guard against wholesale nonsense and topic-swaps** (departure from the
anchor's embedding neighborhood), never a guard for factual faithfulness. **Factual
faithfulness is policed by the fact-survival measurement (the fixed gist constraint at
generation + gist-precision at the metric read) and by the LLM judge (the judged faithfulness
category, past the agreement bar).** Cheapest resolution; nothing changes at runtime; the
documentation now states what each guard really covers.

**Propagated the same day:** `architecture.md` §7's drift-budget paragraph (the scope-of-the-
guard sentence with the ablation numbers), `reconstruction.md`'s "Write-back & drift budget"
scope note, the `drift_budget_threshold` knob comment in `app\config.py` (the integrator-facing
claim), the stage-4 banner in `eval-harness.md` (ruling recorded, "no tuning follow-up — the
ruling changes documentation, not the metric"), and `status.md` (R7 moved from open questions
to recently-closed). The 2026-07-17 drift-metric/threshold ruling is NOT superseded
mechanically — only its implied coverage claim is corrected.

**Rejected:** changing the metric (e.g., fact-survival gating write-backs at runtime — buys
fact-level refusal at the cost of a lexical gate on every write-back, redundant with the gist
constraint already steering generation); tightening the threshold (the ablation shows
unconstrained retellings sit FAR under 0.35 — no threshold separates them, so tightening only
manufactures false refusals on faithful retellings); dropping the budget (it still catches the
failure class it was built for — wholesale nonsense, topic-swaps, and the degenerate-embedding
fail-closed path).

## Dialogue model re-ruled — haiku stands, latency rules — 2026-08-12

**Ruled (Jack, closing the 2026-07-29 deferral on the first real compares' data).** The
dialogue role stays **haiku** (`claude-haiku-4-5-20251001`). Perceived time-to-first-word is
the decisive axis, and sonnet-5 takes too long: **943 ms p50 for haiku vs 2626 ms (sonnet-5)
and 2086 ms (sonnet-5 thinking-off)** — both sonnet variants sit far over the 1 s bar that has
governed the dialogue seam since the B1 A/B, and ~20% dearer per 100 turns ($0.92–0.94 vs
$1.12–1.14). This is ruled WITH sonnet-5's prose superiority on the record, not in ignorance
of it: the Opus judge preferred sonnet-5's prose **46–7** (thinking-on) and **41–9**
(thinking-off), higher on all four pp-v1 dimensions in both runs. Prose quality does not
justify the latency.

**What this closes:** the 2026-07-29 "Haiku dialogue" entry's ruling 3 (the deferral —
"re-assess both once prose quality can actually be scored") is now discharged: BOTH deferred
questions are answered by measurement. Sonnet-5 dialogue: re-assessed, rejected on latency.
The B2 thinking-off variant: MEASURED (the 2026-08-07 knob build made it a pure env overlay);
thinking-off recovers ~21% of sonnet's perceived latency (2626 → 2086 ms) and keeps the prose
edge, but still runs >2× the bar — so it neither rescues sonnet-5 nor matters for haiku (the
knob stays available for future arms). `.env` and the committed arm files already carry the
ruled state; no config change.

**Caveats on the record (stated at ruling time):** the pairwise prose verdicts are below
their agreement bar (reference-label kappa 0.37 < 0.6 — unquotable as calibrated numbers;
both instruments agree on DIRECTION, and the ruling's decisive axis is latency, which is
structural instrumentation, not judged). Judged accuracy showed single-run variance across
the two compares (0.9688/0.9688 vs 0.901/0.9738) — treated as noise, not signal, and not
load-bearing for this ruling. Phase D1's full-system pass remains the final model-slate
confirmation (unchanged).

**Rejected:** sonnet-5 as the dialogue role (prose wins, latency loses — 2.8× the bar);
sonnet-5-thinking-off (2.2× the bar; the halfway house pays most of the latency for none of
the bar); re-running the compares for tighter pairwise calibration before ruling (the
decisive axis is already quotable; more spend would not move it).

## Typology robustness ruled — clamp at the parse seam — 2026-08-12

**Ruled (Jack, closing the gap the first thinking-off compare exposed).** Model-emitted
typology is **CLAMPED to vocabulary at the write-call parse seam** before it can reach the
insert. The crash: the write prompt lists the options as
`typology (one of observed|told|inferred|reflected)`, and one real call echoed the option
syntax back (`"observed|told"`); `RealWriteProvider` passed it through as a bare `str()`,
ingest adopted it verbatim, and `memories_typology_check` — the only tooth — killed the
whole request mid-compare (~6 min of real spend, no artifact).

**The clamp's shape (build latitude, recorded):** `clamp_typology` in `app\providers.py`
beside the new module-level `TYPOLOGY_VOCABULARY` tuple — in-vocabulary values pass through
byte-untouched; otherwise the FIRST vocabulary member found in the string wins (the model's
leading choice: `"observed|told"` → `observed`); a value containing no member returns None,
which flows into ingest's **existing** undeclared-typology default path (config
`typology_default` → `TYPOLOGY_FALLBACK`) — zero new ingest logic. A clamp-to-None also
drops the parsed confidence (a label the vocabulary rejected has no meaningful confidence;
ingest's default branch knob-defaults both together). Never silent — every clamp logs the
raw value at WARNING. The clamp lives provider-side (the 2026-07-21 parse-hardening home),
NOT in ingest: the **declared** path is already safe by wire contract (`schemas.Typology` is
a `Literal` — an out-of-vocabulary client declaration 422s at the schema boundary and must
stay a loud client error, never a silent rewrite of an integrator's explicit input). The
fake provider's `TYPOLOGIES` now references the shared tuple, and the degradation suite
asserts the wire `Literal`, the vocabulary constant, and the fake stay identical
(migration 001's SQL copy is fixed by the applied-migration immutability rule). Verified:
the new structural test (the real crash value among its cases), suite `-m "not nlp"` **82**,
`verify_write_path.py` **53/53** — the write-path floor holds.

**Rejected:** re-ask the model (a retry call per malformed value — write-path latency and
cost spent on a string that is salvageable locally); degrade the observe (drops a real
observation over a label formatting slip — the observation text, render, and importance are
all good; only the label needed normalizing); leaving the DB constraint as the only guard
(the status quo that cost the run).

**Flagged in passing, not built (the same hazard class, one seat over):**
`typology_confidence` is converted with `float()` in the return expression OUTSIDE the
parse's try/except — a model emitting a non-numeric confidence (e.g. `"high"`) would still
crash the request rather than degrade to `MalformedOutputError`. Small, unruled; carried in
`status.md`.

*Closed 2026-08-12, same day — see typology_confidence salvage ruled.*

## C1 spec rulings — deferred write processing — 2026-08-12

**Ruled (Jack, at C1's plan-mode spec — the four forks presented with recommendations; all
four recommended options taken first pass).** Phase C1 builds deferred write processing per
the 2026-07-23 sequenced-later ruling (raw stored immediately, enrichment at the service's
own timing; a cost/throughput optimization). The forks:

1. **Defer ONLY the LLM calls.** The local NLP pass (gist spans + entities) and the ~0.2 s
   embedding stay in the request path; the single write call and the escalation call move to
   the worker. A fresh memory is vector- and lexically-searchable the moment the observe
   returns, with gist spans intact — until enrichment it serves raw text and scores at
   neutral importance, both already-ruled degradation shapes. This also answers the
   action-observe same-scene question A1 delegated to this fork: full retrieval reachability
   immediately. **Rejected:** full deferral (fastest return but the window would be
   vector-invisible, zero-gist — the stage-4 ablation's measured −0.13 gist-precision hole —
   and context-blind); a repair-only worker (does not match C1's ruled description).
2. **Enrichment writes by supersession via the existing chains.** The render supersedes the
   raw head as a new `memory_details` head, `write_cause = 'enrichment'`; fact-chain changes
   ride new `memory_fact_versions` rows (same cause); gist spans append add-only. Only the
   chainless `memories` scalars — importance, typology triple, plus pending/attempts
   bookkeeping — fill in place, **one-shot NULL→value, sanctioned by this ruling** (the
   `pinned` class: the original write finishing under the `enrichment_pending` guard, never
   a mutation of a stored value). Migration 006 widens BOTH write_cause CHECKs;
   `'enrichment'` joins the drift-anchor set. If a retelling or correction superseded the
   raw head first, enrichment completes facts only, skips the prose supersede, and evicts
   that memory's reconstruction cache. **Rejected:** in-place completion for embedding and
   entities on the live fact head (smaller migration, but bypasses the fact-version
   machinery the entities freeze pointed at — supersession is the path the frozen-facts
   ruling already named). **Recorded finding:** `decay_class` resolves purely from the
   client label + agent config at insert (no model input), so it never defers and the
   completion never touches it — settled explicitly, not silently.
3. **In-process async worker, default OFF.** Started at BOTH construction sites (the API
   lifespan and `SessionRunner.create`, so REPL observes enrich), governed by
   `SERVICE_DEFAULTS` knobs — `deferred_writes_enabled` kill-switch **landing at 0.0**,
   `deferred_poll_seconds`, `deferred_batch_size`, `deferred_max_attempts` — with a directly
   callable `drain()` for deterministic tests. Every existing floor stays valid as-is;
   deferral is opt-in; the default flips at Phase D if the numbers earn it. No new model
   role — the worker uses the write model; the six-role slate is untouched. The first
   self-scheduled mechanism in the system: reflection and purge stay endpoint-pulled — this
   is service-internal bookkeeping, and C2's idle-time scheduling later rides it.
   **Rejected:** default ON (a substantially bigger landing — every observe-exercising floor
   re-verifies against deferred-default in the same session); endpoint-pulled only (purest
   no-scheduler fit but not "the service's own timing", and C2 would have no machinery to
   ride).
4. **The byte-identical-within-a-scene invariant is AMENDED**: deferred-enrichment
   completion becomes the **third sanctioned cause** of mid-scene text change (after
   diegetic events and authorial correction), the exposure window bounded by the poll
   interval. **Rejected:** a min-age delay knob (only probabilistic protection — the suite
   could not assert the invariant hard); never superseding prose (preserves the invariant at
   the cost of the rendered-prose benefit entirely).

**Consequences propagated (all landed with the build):** `CLAUDE.md` (the non-destructive
bullet's one-shot completion carve-out beside `pinned`; the byte-identity third cause),
`architecture.md` §5/§7/§11 + the generalized-eviction writer list, `write-path.md` (banner,
pipeline, ladder rows), `read-path.md` (the zero-retrieval-change window note),
`test-suite.md` (Set C third cause; Set K), the new `deferred-writes.md` spec +
`docs\README.md` table row, migration `006_deferred_writes.sql`.

## typology_confidence salvage ruled — the clamp's sibling seat — 2026-08-12

**Ruled (Jack, closing the item flagged at the typology-clamp build): SALVAGE semantics,
fixed inside C1** since C1 opens the same parse seam. `salvage_confidence` in
`app\providers.py` beside `clamp_typology`: a non-numeric (or NaN) model-emitted confidence
drops to **None** while the parsed typology, render, and importance all survive (ingest
knob-defaults the confidence); a numeric out-of-range value clamps into [0, 1]; every
intervention logs the raw value at WARNING. The write lands. The client-DECLARED path is
untouched — an out-of-range declaration stays a loud 422 at the wire model. **Rejected:**
degrading the whole parse to `MalformedOutputError` (the write would land through the
scoring-failed fallback, discarding the render and importance the model returned correctly —
heavy loss for a one-field defect); leaving the seat for its own scoped task. Closes the
`status.md` carried item (flagged 2026-08-12). Verified: the Set K unit scenario (the
flagged `"high"` crash value among its cases), suite subset 94, write-path walker 53/53.

## Phase C1 build record — deferred writes landed — 2026-08-12

**Built the same session the forks were ruled** (spec → build → walkers → floor-verify, the
standing discipline). Migration 006 (both write_cause CHECKs widened to admit
`'enrichment'`; `memories` gains `enrichment_pending` / `enrichment_attempts` /
`enrichment_pending_triggers`; the `memory_enrichment_runs` per-attempt instrumentation
table + partial pending index); the four `SERVICE_DEFAULTS` knobs; `app\deferred.py`
(`DeferredWriteWorker`, started at both construction sites, stopped before the pool closes);
the ingest seam's extract-only refactor (`run_write_call` / `resolve_typology` /
`escalate_with_retry` / `plan_spans` promoted module-level so the worker and the sync branch
share ONE implementation — the sync path byte-unchanged, `verify_write_path.py` 53/53
untouched as the parity proof) + the deferred branch; `db.apply_enrichment` /
`record_enrichment_failure` / `claim_enrichment_batch` (skip-locked claims) /
`fetch_enrichment_source` / `fetch_exhausted_pending`; wire deltas (`IngestResult` nullable
scalars + `enrichment_pending`; `/chain` gains pending/attempts/runs) mirrored in
`Models.cs`; the Ledger `enrichment` badge; the load driver's `observe_total` p50/p95
series.

**Build-latitude choices, recorded:** (a) **one attempt per row per drain pass** — the
first Set K run exposed that a failed row, still pending, was re-claimed by the same drain
and burned its whole budget back-to-back with zero retry spacing; the claim SQL gained an
exclusion list and the poll loop is the spacing. (b) **Sync parity for escalation novels** —
the approved plan sketched merging novel canonicals into fact entities; built instead as
components + mention spans ONLY (the sync path never puts escalation novels into memory
entities — enrichment reproduces what the sync path would have written, nothing more), so
the fact chain supersedes only for the embedding repair. (c) **The orphan sweep** — a
process dying between claiming the final attempt and recording its outcome would strand a
pending row un-claimable forever; `drain()` opens by terminal-filling budget-spent pending
rows without model calls. (d) The terminal fill writes the NEUTRAL importance value (not
NULL) + `scoring_failed` — byte-equivalent to the sync end-state, which pre-sets the
neutral before its try block. (e) The 2026-07-28 carried note about a stale hard-stop
comment at `ingest.py:234` was found already fixed in the live file — no edit, recorded
here.

**Verified:** suite 108 scenarios (94-subset ×2 green), all EIGHT walkers on fresh
`longmem_test` — write-path **53/53 byte-untouched**, the new `verify_deferred_writes.py`
**51/51**, read-path 56, cli-harness 51, gate 51 (ledger pin mechanically bumped to 006, the
004/005 precedent), reconstruction 42, authorial 34, fact 34 — migrate idempotency
(001→006 + clean second run), both C# builds 0-warning, the 24-check console harness gate,
and the independent floor-verifier pass (floors row 25; the verdict returned **2026-08-13**
after an overnight pause interrupted the first dispatch — this entry was drafted ahead of it
and stands as verified; the verifier's non-failing flag that four docs pre-recorded its pass
is taken as a wording-habit note for future landings).

## Interim public README — public ahead of Phase F — 2026-08-13

**Ruled (Jack, 2026-08-13, session premise + plan approval):** the repo goes public NOW,
ahead of Phase F, as a portfolio surface for recruiters. An interim README describes the
current verified state and persists untouched until the demo ships; **F1's full README
rewrite at demo time stands unchanged** — this entry re-sequences the visibility flip only,
never the release (F2 packaging and F3's hygiene sweep still precede the v1 release, and C6
purge remains the ruled release-blocker; the README's what-this-is-not section says both).
Shape ruled via the session's four-question batch, all recommended options taken except the
visual, where Jack chose MORE than the recommendation (mermaid + a REAL Ledger screenshot
over diagram-only): full showcase (~210 lines) over a compact refresh; the AI-assisted build
owned in one paragraph inside the verification section (not featured, not silent — the
tracked `.claude\` apparatus is visible to any visitor regardless); stale counts propagated
alongside (SETUP.md migrations 001–006 + suite 108/94; docs\README.md eight walkers;
test-suite.md Set I sixteen — the append-only registers keep their historical "seven
walkers" mentions by design).

**Build record.** README.md rewritten; the private-stage README's thesis paragraph, layout
table, quickstart block, and reading pointers survive, and the "dissonance-driven defense"
clause was trimmed from the pitch — dissonance is unbuilt, so it sits in the roadmap section
instead. Quotability rulings respected: the 46–7 / 41–9 prose-preference counts appear
nowhere (below the 0.6 agreement bar), framed instead as "the judge preferred the slower
model's prose, and the ruling took the sub-second first word"; the natural-rf degeneracy is
reported as a failed bar beside its constructed-truth closure. No badges: no CI workflow
exists, and a lone license shield duplicates GitHub's own sidebar. **The Ledger gained two
changes in service of the capture, both beyond the strictly-named task and recorded here:**
(1) the existing `?agent=` deep-link got its `&memory=` sibling — straight to a chain view
(also a demo-choreography hook: a scene cut can land on a specific chain; dated addendum in
`unity-client.md`); (2) an overlapping-gist-span render fix — spans can overlap since
escalation landed, and the observation card rendered overlapped characters twice; each
character now renders exactly once, the mark kept on any unrendered tail. The stored record
was never wrong; the inspector's render was. Capture: real-mode seed against a throwaway
scratch DB (`longmem_readme_shot`, migrated 001–006, dropped after — the product DB stays
out of it), four observes (one pinned, one authorially corrected, two aged 35 days), one
init (2 write-backs, 0 drift refusals), headless Chrome →
`docs\media\ledger-memory-chain.png` (126 KB). No floors row — no layer landed, and the
floors count must not drift for non-layer work.

## Em-dashes banned from public-facing prose — 2026-08-13

*(Recorded at the 2026-08-15 wrap-up sweep.)* **Ruled (Jack, 2026-08-13, reviewing the landed
interim README):** zero em-dashes in the README and in any public-facing document presented in
Jack's voice — replace with colons, commas, semicolons, parentheticals, or sentence rewrites;
en-dashes (ranges like 001–006) and hyphens stay. Applied the same day (commit `78ba346`: 49
README lines swapped line-for-line, mermaid labels and tables included, U+2014 count verified
0 on the staged blob). Scope boundary set by the ask ("the sentences" of the deliverable): the
internal registers — this file, `session-log.md`, `status.md`, CLAUDE.md — keep their
long-established em-dash register. Binds **F1's demo-time README** and any future outward doc.
Two flagged residues left to Jack's later call: the Ledger UI's own labels (visible in the
README screenshot's pixels; a ~10-minute restyle + recapture with the saved rig if wanted),
and whether the ban should extend to future register entries.

## C2 design-dossier rulings — reflection — 2026-08-15

**Ruled (Jack, at the C2 design-dossier session — the six forks presented with
recommendations in two batches (4 + 2, the C1 rhythm); all six recommended options taken
first pass, plus one rider).** Phase C2's first stage: the design dossier
(`docs\reflection.md`, DESIGN banner — the same file matures into the build spec next
session, ruled at plan approval alongside the session scope). The dossier consolidates
architecture §10, the standing rulings, the banked research findings (FINDINGS #4),
migration 001's dormant `reflections` table, and C1's worker machinery. The forks:

1. **Scheduling composes: endpoint + optional worker, default OFF.** The reflect endpoint
   stays the verb (`POST /v1/agents/{agent_id}/reflect`); an optional sibling
   `ReflectionWorker` on C1's exact lifecycle contract (both construction sites, stop before
   pool close, catch-log-continue, a deterministic no-timer test entry) pulls the same
   internal seam when reflection pressure crosses a per-agent knob threshold
   (`reflection_worker_enabled` lands at 0.0 — kill-switch semantics, the
   `deferred_writes_enabled` precedent). §10's "no scheduler" and the roadmap's "idle-time
   scheduling rides C1's machinery" compose rather than conflict: the endpoint is the verb,
   the gauge is the evidence, the worker is optional automation of the same pull; §10 and
   the primary register entry carry the amendment. **Rejected:** endpoint-only (contradicts
   the roadmap line and C1's recorded "C2 would have no machinery to ride" rationale);
   worker-only (overturns the standing endpoint ruling and removes integrator control); a
   generic jobs table with work types (a migration-006-rewrite-shaped change to a verified
   floor — the enrichment queue is memory_id-keyed and structurally cannot host agent-scoped
   jobs; pays off only if a third background work type ever arrives).

2. **Reflective content lives in the `reflections` table — the sole durable home.** A
   reflection is an identity ingredient + C3 feedstock, not a retrievable memory:
   identity-relevant rows reach prompts through the rendered document; the rest wait for
   C3 (runtime-inert until then — the option's stated cost, accepted). Citations land in
   the existing `source_memory_ids` (provenance-only, deliberately un-FK'd); supersession
   by the ordinary bi-temporal verb (the C3 eviction contract); retrieval untouched — zero
   code changes, so the post-landing believability compare isolates the identity channel.
   **Rejected:** `memories` rows with `typology='reflected'` (the CHECK admits it — genuine
   schema-now evidence, weighed, not strawmanned — but `memories` has no citation column,
   §5's write-path obligations cascade onto belief text, purge semantics fork, and the
   `reflections` table stays a census corpse); dual-write (two homes for one content; the
   purge divergence — the memories twin purgeable, the reflections twin surviving).
   Retrieval-visible beliefs, if ever wanted, are a separate later ruling.

3. **Identity refresh: model-free render + LLM consolidation + the dialogue seam moves —
   ruled as a package.** (i) `render_identity_document` extends concatenatively — seed
   prose + live identity-relevant reflections, deterministic, non-LLM; the scene-edge
   recompile stays fast and the version hash stays reproducible. (ii) The periodic
   evidence-conditioned refresh is a consolidation product of reflection itself: an LLM
   rewrite conditioned on the prior document + the live identity-relevant reflections + the
   immutable seed lands as a NEW identity-relevant reflection that bi-temporally absorbs
   the rows it consolidates — `identity_documents` gains rows never mutations,
   `agents.seed_identity` is never touched. (iii) The dialogue prose prompt moves off raw
   `state.seed_identity` (`app\dialogue.py:311-315` — the asymmetry found this session:
   reconstruction reads the rendered document, dialogue reads the raw column) onto the
   rendered document fetched by the caller-frozen `identity_version` the request already
   carries; without this, NPC speech would never see a reflection. Parity contract: zero
   reflections ⇒ renders byte-identical to today ⇒ existing floors hold; the dialogue-seam
   floors re-verify at build (a step, not a cost). **Rejected:** LLM-render-at-scene-edge
   (a model call in the boundary heartbeat; a non-deterministic version);
   refresh-as-mutation of seed or document rows (violates non-destructive storage);
   dialogue staying on raw seed (a permanent speech/reconstruction identity split).

4. **Component trim gets teeth, and its eviction is the FOURTH sanctioned cause.**
   (i) Constraint-follows-liveness: reconstruction's gist constraint drops spans whose
   `matched_component_id` is invalidated. Found this session:
   `fetch_reconstruction_sources` reads spans with no liveness join (`app\db.py:916-923`),
   so a trim would currently remove nothing at the reconstruction seam and §4.2's "sole
   mechanism that removes a durable fact" would be mechanically vacuous; the gate side
   already follows liveness (`fetch_live_components`). (ii) Reflection-driven cache
   eviction becomes the fourth sanctioned cause of mid-scene text change (the C1 amendment
   pattern; the CLAUDE.md/architecture §7 invariant text amends WITH the build, when the
   mechanism exists), with integrator guidance: reflect at scene edges and the window
   vanishes. Eviction scope (per-affected-memory vs agent-wide) is spec latitude.
   **Rejected:** scene-boundary-only (unenforceable — scene state is caller-held by ruled
   design; no server-side scene registry; the worker cannot see scenes);
   trim-without-eviction (stale caches keep serving the trimmed fact);
   no-liveness-filter (the trim stays a no-op on tellings).

5. **The repetition detector is a GUARD, not telemetry.** RRR (SequenceMatcher similarity
   against the agent's recent live reflections; threshold knob, paper default 0.85;
   non-LLM) is always recorded in instrumentation; at/above threshold the new reflection
   still stores (honest evidence of the agent's state) but the identity-consolidation step
   is blocked and flagged — the "staleness check before an identity revision is trusted."
   Boundary stated in the dossier: RRR is self-repetition among the agent's own
   reflections; the cut automatic conflict/staleness detection (cross-memory, write-time)
   stays cut. **Rejected:** log-only (the measured failure mode — a stale belief
   reinforced into identity — ships unguarded).

6. **`LONGMEM_MODEL_REFLECTION` takes the judge shape.** Loaded in both modes, required by
   neither at startup; a standalone `build_reflection_provider` factory raises
   `ConfigError` at the first real reflect call without it. Reflection ships default-OFF
   and endpoint-pulled, so every existing real-mode `.env` keeps loading; the Set I
   load-rule pins amend for the new role's shape rather than break. Haiku-class per the
   ruled slate; pricing rows + the full add-a-role checklist run at build. **Rejected:**
   seventh-required (breaks every current real-mode `.env` for a verb many integrators
   never call; cuts against the logic the judge precedent established).

**Rider (same session):** architecture.md's stale habituation wording (the §2 knob list
and §8's "Habituation guards" line still read as live though habituation was cut
2026-08-04) — ruled ANNOTATE NOW: cut-parentheticals at both spots, the design text
otherwise untouched.

**Consequences propagated this session (docs only — no code, no migration, no tests, no
floors row):** `docs\reflection.md` finalized to the rulings; `architecture.md` §10
rewritten to the ruled composition + the §3 role-shape parenthetical + the two habituation
annotations; the primary register entry's amendment note (above); CLAUDE.md's role sentence
gains the ruled shape; `docs\README.md` spec-table row; `status.md`; `session-log.md`.
Deferred to the spec/build sessions per the dossier's settle ledger: the fourth-cause
invariant text (CLAUDE.md + §7), §4.2's liveness mechanics, migration 007 (worker-contingent
`reflection_runs`), knobs, wire shapes, Set L, the ninth walker.

## C2 spec rulings — reflection build target — 2026-08-15

**Ruled (Jack, at the C2 spec sitting — the same date and session as the dossier,
continued at his call; the four spec forks presented with recommendations).** Three took
the recommended option; **trim criteria was ruled AGAINST the recommendation** — the
first non-recommended ruling in the C2 line, recorded as such. `docs\reflection.md`
matured from DESIGN DOSSIER into the Phase C2 build target in the same file. The forks:

1. **Consolidation trigger — automatic threshold + explicit override** (recommended,
   taken). Consolidation runs when live identity-relevant reflections reach
   `reflection_consolidate_at` (default 5.0); the request's tri-state `consolidate`
   field forces or suppresses it per call; the RRR guard applies either way — the worker
   gets periodic refresh for free, integrators keep manual control. **Rejected:**
   explicit-only (the periodic-refresh promise would depend on integrator diligence, and
   the worker could never consolidate); every-reflect (no accumulation between rewrites;
   consolidation churn and model cost per call).

2. **Trim criteria — PURELY MECHANICAL** (ruled against the recommendation; the
   model-in-the-loop shape was presented first with its rationale and declined with its
   cost heard). No model touches the prune decision. Spec latitude then shaped the
   concrete rule — three clauses, all SQL + the sample list, executed by the reflect
   verb (so §10's "reflection prunes" stays true in the scheduling sense): a live
   component prunes iff (i) it HAS span evidence at all (zero-span components are
   authored/provisioning content — operator intent, exempt), (ii) ALL its evidence is
   stale (no live referencing memory's `valid_at` within
   `reflection_trim_stale_seconds`, default 30 days), and (iii) it is NOT referenced by
   this call's sample (active evidence never prunes — a formative old memory can sample
   on importance while sitting outside the window). 0.0 disables the trim (the
   kill-switch shape). Deliberately NO pinned-memory clause: pin keeps its ruled
   exactly-two meanings. The reflect prompt carries no prune content; the model output
   contract is conclusions-only. **Rejected:** model-proposed from mechanically-derived
   candidates (the recommendation — judgment grounded in a mechanically-safe candidate
   set); model-unrestricted (the confabulation shape the dossier was built to avoid).

3. **Eviction scope — per-affected-memory** (recommended, taken). Trim evicts
   `reconstruction_cache` rows only for `memory_id`s with a span matched to a pruned
   component. **Rejected:** agent-wide (wider fourth-cause mid-scene exposure and
   re-reconstruction cost for rows the trim never touched).

4. **C# mirror at this build** (recommended, taken). `NpcMemory.Core` mirrors the
   reflect verb + result models field-for-field; the console-harness gate extends; the
   1:1 route-mirroring attestation keeps no exceptions. **Rejected:** a dated exemption
   deferring to C5 (the attestation carries an exception for a phase; C5's scope grows).

**Spec content recorded under standing latitude** (shapes flowing from the dossier
rulings; no batch required): the reflect pipeline (sample → mechanical trim set → one
model call → mechanical citation validation → RRR → the write transaction →
threshold-gated consolidation, soft-fail); deterministic top-k sampling
(importance-norm × the decay module's recency, ties on `memory_id` — never a lottery);
the live-telling-head input; the ten-knob slate; migration 007 = `reflection_runs` only
(agent-keyed, worker runs only — endpoint runs ride the response payload, the C1 split);
the judge-shaped standalone provider factory; `sweep()` as the worker's deterministic
no-timer entry with NO attempts ledger (pressure persistence IS the retry — the
deliberate contrast with enrichment's budget); the pressure formula (importance mass
since the last reflect event / `reflection_pressure_norm`, computed on demand, never
stored); the loud-reflect / soft-consolidation degradation ladder; done-when 1–11.

**Consequences propagated this sitting:** `docs\reflection.md` (banner SPECCED, the
spec-rulings section, the mechanical-trim rework); `status.md`; `session-log.md`; this
entry + its Index line (count 61 → 62). Architecture needed no further edit — the
dossier sitting's §10 amendment makes no model-prune claim, so the mechanical ruling
contradicts nothing. Everything else lands with the build per the spec's
`[SETTLE-AT-BUILD]` ledger.

## Phase C2 build record — reflection landed — 2026-08-15

**Built the same date the spec was ruled** (dossier → spec → build → walkers →
independent floor-verify; the third C2 sitting). Migration 007 (`reflection_runs`, the
WORKER's per-run instrumentation home — endpoint reflects ride the response payload, the
C1 endpoint/worker split; 006's column-type idioms; `reflection_runs_agent_id_idx`);
`app\reflection.py` (pure prompt assemblers, `ReflectionService.reflect` = the ruled
pipeline 1–9, `compute_rrr`, `ReflectionWorker` on the C1 lifecycle contract with
`sweep()` as the deterministic no-timer entry and NO attempts ledger); the judge-shaped
role (`ENV_MODEL_REFLECTION` loaded both modes required by neither; the standalone
`build_reflection_provider` loud at first real use; Fake/Failing/Malformed/Real
providers; `LONGMEM_PRICE_REFLECTION_IN/OUT`); db.py's reflection section (the reads,
the step-7/8 transactions, the 3-clause mechanical trim query, the pressure aggregate,
run rows, the worker's agent scan) + the constraint-follows-liveness join in
`fetch_reconstruction_sources`; the extended model-free identity render (a defaulted
second parameter — every 1-arg caller stands); the dialogue-seam move (the prose prompt
rides the RENDERED DOCUMENT for the caller-frozen `identity_version`, resolved exactly
like reconstruction's — the raw-seed asymmetry closed; zero reflections render
seed-verbatim, byte parity walker-asserted); `POST /v1/agents/{agent_id}/reflect`
(404/409/422/502); the worker at BOTH construction sites, stopped before the pool
closes; the REPL `:reflect [consolidate|no-consolidate]`; **eleven** `reflection_*`
knobs in `SERVICE_DEFAULTS` (the spec table's own row count — the spec sitting's
"ten-knob" phrase was a miscount of the same table, corrected here rather than by
editing the applied entry); suite Set L (`tests\test_reflection.py`, 20 scenarios, ALL
unmarked — db-layer seeding via the new `Ctx.seed_reflection` / `add_component` /
`component_spans` helpers); the ninth walker `tests\verify_reflection.py` (60 criteria,
lettered A–F); the C# mirror field-for-field (`ReflectRequest` / `ReflectionOut` /
`ConsolidationOut` / `ReflectInstrumentation` / `ReflectResult`; `ReflectAsync` on
client + session) + four interop-gate beats (24 → 28 checks); the three migration pins
(+007, the census confirmed against real collation: `reflection_runs` sorts BEFORE
`reflections`); the Set I load-rule amendment; the fourth-cause invariant amendments
(CLAUDE.md + architecture §7) and the `mid-dialogue-gate.md` "only grows" expiry.

**Build-plan rulings (Jack, 2026-08-15, the plan-mode fork batch — four asked, all
recommended options taken):** (1) the identity re-render + upsert runs AFTER each write
transaction commits (the upsert is idempotent, content-addressed, and self-heals at the
next ensure — the spec's "then" sequencing made physical); (2) the REPL surface is the
tri-state token pair `:reflect` / `:reflect consolidate` / `:reflect no-consolidate`;
(3) tests inject failing/malformed reflection fakes through a keyword-only
`reflection_provider=None` constructor seam (None = the lazy factory; both production
call sites keep the pinned 3-arg shape); (4) the post-landing believability check is the
REAL-mode stage-2 metrics run on the existing smoke scenarios against the on-disk
baselines, fake dry-run first. **Plan-approved `[SETTLE-AT-BUILD]` resolutions** (the
spec's ledger, ruled by the approved plan): 007 column types copy 006 per class;
pydantic field names = the spec's verbatim; single-module `app\reflection.py`; the
worker scans `SELECT agent_id, config FROM agents ORDER BY agent_id` with knob/pressure
logic in Python; the error taxonomy (`ReflectionFloorError` → 409, `ReflectionCallError`
→ 502 carrying token counts so failed worker runs stay honest, `UnknownAgentError`
reused → 404, `ConfigError` unwrapped); the RRR window order `created_at DESC,
reflection_id`; **the pipeline's time basis = the request's `client_timestamp`** (the
as_of / scene-frozen-basis precedent — tests and walkers freeze the clock by freezing
the request; the worker stamps wall-clock now); the zero-norm pressure guard raises
loud, never a clamp; consolidation is a `consolidate()` protocol method returning
`{"content": str}` with the source union computed server-side; the worker's below-floor
rung is a skip with NO run row; the ninth walker prints the doc-stated `ALL CHECKS
PASSED (N assertions)` convention (walker eight stays the recorded outlier); pinned rows
take the PLAIN decay score in sampling (spec-settled: pin = exactly two meanings —
reflection is neither).

**Build-latitude choices, recorded:** (a) Set L grew to 20 from the spec's ~13 — the
trim family split into three scenarios, the route contracts rode the house
ASGI-transport convention (found mid-build in `test-suite.md`'s Route-contracts
section), and the suppress-when-due arm got its own scenario with the RRR threshold
pinned inert (>1, the fixture-pin discipline) after the deterministic fake's
near-identical repeat conclusions (measured rrr 0.905 against the shifted identity
block) tripped the guard inside a scenario that was not testing it — an honest reminder
the guard works. (b) Same-transaction reflection inserts share one `created_at`
(Postgres stamps transaction time), so row order among one call's conclusions is
id-tiebroken — Set L asserts membership, not sequence. (c) `fetch_reflection_runs`
exists as a walker/test read only (no product route — C5's agent-state read is the ruled
surface). (d) The real provider's fixed max_tokens (2048 reflect / 1024 consolidate)
follows the write-call precedent of a structural bound, not integrator policy.

**Verified (the independent floor-verifier re-ran everything itself; VERDICT pass):**
suite **128** full / **114**-subset (Set L 20/20 incl. the ASGI route contracts); all
NINE walkers on fresh scratches — write **53/53 byte-untouched** and read **56/56
byte-untouched** (the zero-retrieval-change evidence), reconstruction 42, cli-harness
51, authorial 34, fact 34, gate 51 (ledger pin +007), deferred 51/51, the new
`verify_reflection.py` **60/60**; fresh 001→007 + idempotent re-run ("Up to date: 7
applied, 0 pending"); the 13-table census; both C# builds 0-warning; the 28-check
interop gate re-run LIVE by the verifier (fake-mode served app, incl. the four reflect
beats); the product DB pristine before and after (ledger exactly 001–006, zero
reflection rows — applying 007 to the product store is Jack's action, deliberately not
the build's); believability = the real-mode stage-2 smoke vs the 2026-08-07 real
baseline: checks 6/0 both, gist_precision 0.7667 → 0.9, keyword_retention equal at
0.9375, the remaining deltas single-run real-mode noise — **no regression**
(`run_20260815T222459Z_pid_31388.json` vs `run_20260807T224423Z_pid_15844.json`).
Floors row 26. The verifier caught three stale `SETUP.md` counts (scenarios/walkers/
harness checks) — fixed before commit.

**Surfaced, not fixed (recorded under the zero-retrieval-changes ruling):** the eval
metric read (`retrieval.py` `reconstruction_metrics`) builds its fabricated-entities
baseline from the seed-only 1-arg render; once identity-relevant reflections exist, a
belief-introduced entity would count "fabricated". Reflection ships default OFF, so
nothing is wrong today — flagged for Phase D (or C5's neighborhood) as the
metric-honesty counterpart of the dialogue-seam move.

## Phase C3 build record — the parameter compiler landed — 2026-08-17

The build session (plan-mode spec + spec-to-floor in one sitting): migration 008
(`compiled_bundles` + `compiler_runs`), `app\compiler.py` (the compile service, the pure
consume functions, the standalone `CompilerWorker`), the provider quartet +
`build_compiler_provider`, the dialogue-seam consume splice (`scene_type` on the turn
request; the composed multiplier products over the walker-pinned weight resolver), the
session/CLI surface (`:compile`; `:scene <type>` extended to session state), the C# mirror
+ interop beats [13], suite Set M (21 scenarios, all unmarked — subset 114 → 135, total
128 → 149), the tenth walker (48 assertions), and the docs sweep. Spec:
`parameter-compiler.md`. Ships default OFF (`compiler_worker_enabled` 0.0); the flip is a
Phase D question beside C1's and C2's.

**The seven rulings (settled at the plan-mode fork batches, 2026-08-16/17, before any
file changed):**

1. **Feedstock: ALL live beliefs compile** — identity-relevant included (the prose
   channel and the parameter channel are orthogonal); a neutral bundle is a valid
   compile. Rejected: non-identity-only (one-belief-one-channel — it would have made any
   demo beat hostage to how the reflect model happens to flag the belief).
2. **Typed core = the three prose-view weight multipliers only.** The founding §10
   "action-set biases" clause was dead by the A1 action-side scrap (2026-08-04) and is
   corrected in `architecture.md` with this build; "stance priors" folded into the
   integrator's namespaced passthrough. Rejected: a compiled stance prompt block (a
   second text channel into speech, overlapping the identity document's job and adding
   prompt byte-stability surface).
3. **Scheduling: a standalone third background worker** — Jack took the LARGER option
   over the recommended reflect-pipeline stage, and the follow-up fork ruled it lands
   WITHOUT the generic jobs table: `CompilerWorker` on the exact C1/C2 lifecycle
   contract (both construction sites, stop before pool close LIFO, catch-log-continue,
   the deterministic `sweep()` entry), work discovery as stateless SQL (the missing
   (live belief × scene-type) pairs join — the pressure-gauge precedent), **no endpoint
   and no route**. The jobs-table unification was surfaced with its real cost (re-opens
   the C1/C2 floors; the 006 queue abandoned in place under migration immutability;
   roughly two to three sessions) and stays available as its own scoped later task.
4. **The staleness guard is the all-mechanical trio** (the C2 spec's ExpeL caution,
   downstream half): liveness-by-join (bundles have no independent life — supersession
   and the consolidation N→1 collapse evict with zero bundle writes), the K-window
   (`compiler_window_k`, enforced at discovery AND the consume fetch), hard clamps at
   write AND consume. Rejected: liveness+clamps without the window (influence saturates
   at the clamp as the never-consolidated non-identity population grows); age
   attenuation (a third time mechanism beside recency decay and bi-temporal
   invalidation, which the invariants deliberately keep distinct).
5. **`LONGMEM_MODEL_COMPILER` takes the judge shape** — the THIRD such var: loaded both
   modes, required by neither, standalone lazy factory, loud `ConfigError` at the first
   real compile (always the worker's — no endpoint exists); prices
   `LONGMEM_PRICE_COMPILER_IN/OUT` join `PRICE_ENV_KEYS`. The twice-established
   precedent applied a third time; seventh-required was not re-litigated.
6. **Multiplier clamp = [0.25, 4.0]**, frozen into migration 008's CHECK — ruled before
   the file was written, because applied migrations are immutable. One belief moves one
   axis at most ×4 either way and can never zero it (zeroing stays the caller's explicit
   weight-override privilege). Rejected: 0.5–2.0 (the rigidity-CHECK band —
   corroboration-required extremes, the more conservative reading) and 0.0–4.0 (a single
   confabulated belief could mask an axis — the exact failure the guard exists to
   bound).
7. **`:compile` = sweep semantics** — the per-agent kill-switch honored, the printed
   attempt count making a no-op visible; one code path, the REPL exercising exactly what
   production runs. Rejected: an always-live direct compile (the `:reflect` feel — but
   reflect is always-live because its ENDPOINT is; C3 has none, so the REPL would have
   exercised a verb the shipped system cannot perform).

**Build latitude (within the approved plan):** (a) the run-row split mirrors C2 — the
service returns the record, the WORKER persists it; a pass that found no work writes
nothing. (b) `compiler_runs` kept lean — no window/vocabulary-size columns (derivable
from config at read time); `passthrough_keys_dropped` included per the plan. (c) The
consume read costs one indexed query on EVERY turn, bundle-free agents included —
`bundle_fetch_ms` records it honestly; C7's latency pass sees it fresh. (d) The interop
beats are wire-contract-only — the harness cannot reach `sweep()` (no endpoint; the
served worker is default-OFF and poll-based); beat [13] opens with a bare boundary
because earlier beats' narrative boundary types now stick as session state — the
designed stickiness biting the fixture, not the code. (e) The known three mechanical
migration pins were actually FOUR — `verify_reflection.py`'s own A5 ledger assertion,
found at plan time by grepping the prior migration's filename; the census pin's
collation was confirmed on the migrated scratch ('compiled' < 'compiler' <
'corrections'). (f) `RealCompilerProvider` max_tokens 512 (the structural-bound
precedent). (g) `SessionRunner.create`'s live poll loop races deterministic sweep
counts — probes and the walker stop it before seeding; the walker's module docstring
carries this beside the persistent-scratch rule (any section leaving an enabled agent
with uncompiled pairs flips its kill-switch off, so re-runs stay deterministic on the
fixed-name scratch). (h) Stale-text corrections carried with the build: architecture
§12 still said "twelve routes"/"eleven verbs" and omitted the reflect route (a C2
propagation miss), README still said "Reflection isn't built", and `docs\README.md`'s
migration note stopped at 006.

**Verified (the independent floor-verifier re-ran everything itself; VERDICT pass):**
suite **149** full / **135**-subset (Set M 21/21); the TEN walkers — the new
`verify_compiler.py` **48/48** (lettered A–F), write **53/53 byte-untouched** and read
**56/56 byte-untouched** (the zero-retrieval-change evidence), reconstruction 42,
cli-harness 51, authorial 34, fact 34, gate 51 (ledger pin mechanically +008), deferred
51/51, reflection **60/60 on a fresh scratch** — the verifier's one substantive finding:
`verify_reflection`'s B6/E9 DB-global counts make that walker non-re-runnable on the
persistent `longmem_test` once its own prior green run has landed rows there (the
carried walker-scratch item's SECOND documented bite; root-caused airtight as
pre-existing — `app\reflection.py` byte-identical to the C2-verified HEAD, the compiler
walker incapable of writing the rows — not a C3 regression); fresh 001→008 + idempotent
re-run ("Up to date: 8 applied, 0 pending") with all three CHECKs' teeth probed; the
15-table census on the real collation; the judge-shape probe; both C# builds clean; the
**32-check** interop gate re-run LIVE (incl. the four scene-type beats); the product DB
pristine before and after (ledger exactly 001–006, zero reflection rows, no compiler
tables — applying 007 + 008 to the product store is Jack's action, deliberately not the
build's); believability = the real-mode stage-2 smoke vs the 2026-08-07 baseline:
checks **6/0 both**, keyword_retention equal at 0.9375, gist_precision 0.7667 → **0.85**
(above baseline; C2's single-run 0.9 sits in the same noise band; the compiler was
default OFF for the run), fabrication_rate mean 0.0833 → 0.1667 on the SAME single
fabricated entity (a per-telling denominator effect, not a criterion) — **no
regression** (`run_20260817T141601Z_pid_25616.json` vs
`run_20260807T224423Z_pid_15844.json`). Floors row 27. Honest close-out note: the
floors row was first appended via a Python heredoc and the backslash-escape doc trap
bit a SEVENTH time, in a new SILENT costume — `\t`/`\v` are VALID Python escapes, so
TAB/VT landed and ate the following letter with no SyntaxWarning (the invalid-escape
spots warned and preserved their bytes), and `write_text`'s newline translation CRLF'd
the file besides; the standing grep-verify-control-bytes rule caught it, the row was
rewritten byte-level from raw strings, and the file re-verified clean.

## Session-effort audit — the status.md tripwire — 2026-08-17

**Context.** Jack observed sessions growing longer, with far more in-scope riders per
queue item, and asked for a diagnosis before any fix. The session parsed the project's
own Claude Code transcripts — 58 main-thread + 202 subagent files (~172 MB, 46,755
records, zero malformed), fork-copied history deduplicated by uuid — into 27 work
sessions over 23 dates, reconciled three ways against session-log.md and all 21 commit
days (fully matched; no transcripts exist for 07-16 or pre-17:53 07-17). Tool runtimes
derive from tool_use→tool_result timestamp deltas capped at 15 min; the per-turn
Stop-hook suite cost is an estimate (turn-ends × observed same-era subset runtime — the
hook logs itself only when it blocks); token comparisons are within-model only.

**The measured findings.**

1. Per-unit efficiency did NOT degrade: hours per 100 landed insertions by week —
   0.08 (Jul 12–18), 0.33 (Jul 19–25, the profiling week), 0.08 (Jul 26–Aug 01),
   0.18 (Aug 02–08), **0.04 (Aug 09–15, the best of the project)**, 0.21 (Aug 16–17,
   the single C3 landing).
2. What grew is the arc per queue item: ~96 attributed minutes per landing on 07-21
   (four landings that day) → ~260–290 for C2/C3. Phase decomposition attributes about
   two-thirds of that growth to the PLAN phase (the settle-at-spec discipline — the C3
   arc spent 145.7 min in plan against 64.8 build + 42.2 verify) and one-third to the
   standing per-landing apparatus: since A1 every component landing touches 8 areas
   (app, tests, db, docs ×10 files, client, README, CLAUDE.md, .env.example) vs 3–5
   areas and no client in July, at roughly double the insertions.
3. Verification: 40–65% of verify events (suite/walker/floor runs) fire with zero code
   edits since the previous verify event — the re-run habit is real but costs only tens
   of minutes per week. The floor-verifier's per-landing cost tracks the stack it
   re-verifies: 2.5 min / 12k output tokens (write path, July) → 20.8 min / 119k (C3).
   Suite subset runtime grew 16 s → 45 s as the subset grew 38 → 135 scenarios.
4. The docs sweep + four-register ritual is ~10 min per arc — visually prominent in
   diffs, nearly free in wall time. No context-churn signal (repeat-reads flat, late
   re-reads down; the 5.8 h single-human-turn C3 marathon ran clean).
5. The one proven pathology was auto-loaded boot cost: ~38k tokens (07-12) → ~100k
   (07-27, status.md at 110 KB) → ~59k after the 07-28 three-way split → ~53k after the
   08-07 live-state prune → crept back to ~58.6k by 08-16 as status.md regrew
   12 → 17.5 KB. The mechanism and its fix are both demonstrated by the repo's own
   history.

**The ruling (Jack, 2026-08-17).** Of the six priced counter-measures presented, adopt
**option 1 only**: re-prune status.md to live state now, and make the size line a
standing rule — **status.md leaves every wrap-up at or under ~12 KB; anything past the
line moves verbatim into session-log.md's archive section (trimmed, never deleted).**
Recorded in CLAUDE.md's end-of-task step 1. Explicitly DECLINED: (2) walker runner +
verify-after-edits discipline (stays the carried item on its own timeline), (3) Stop-hook
scoping, (4) per-component plan-phase sizing, (5) unbundling the C# mirror rider,
(6) floor-verifier scoping. Rationale: the diagnosis shows the growth is mostly the
repo's real character — bigger queue items carrying their full apparatus, and a planning
discipline that is measurably winning (one-arc floor-verified landings, zero rework
sessions, improving lines-per-hour) — so only the cheapest lever with a proven mechanism
is worth adopting.

**Applied the same day:** the prune (status.md 17,500 B → under the line; the C3 phase
header, the recently-closed litany, and the carried-item bite parentheticals moved
verbatim to the archive; the stale "twenty-six floors" prose count replaced with the
pointer form the file's own rule asks for), the CLAUDE.md tripwire text, and this entry.
The audit's full data tables live in the audit session's scratchpad (evaporates ~5 days);
everything load-bearing is in this entry, and the parse re-derives from the transcript
store in ~2 minutes.

## Phase C4 build record — the dissonance path landed — 2026-08-17

**What landed (plan-to-floor in one session, the ONE-session scope ruled 2026-08-04):** the
dissonance path + diegetic-correction event (`dissonance.md`; NO migration — the ruled
per-target scope fact; the `corrections` table and both diegetic `write_cause` values had
waited since 001). `POST /v1/events/diegetic-correction` (the fourteenth route, the third in
the diegetic namespace) -> `DissonanceService.confront` (`app\dissonance.py`) -> the
chain-preserving one-transaction write (`db.apply_diegetic_correction`: supersede the live
telling head, insert the verb-typed head, insert the `corrections` record, evict the cache).
Surfaces: the REPL `:confront`, the chain inspector's corrections block, the C# mirror
(`DiegeticCorrectAsync` + `NpcSession.ConfrontAsync`) + interop beat [14]. Suite Set N;
the eleventh walker (`verify_dissonance.py`); `verify_reconstruction` deliberately re-opened
for ruling 4 and re-closed at 46 assertions (42 + the [13] section).

**The eight rulings (Jack, at the session's two plan-mode fork batches, before any code):**

1. **The defend-vs-update decision is mechanical** — no model call decides. `resistance =
   importance_norm × typology_mult(memory.typology) × rigidity`; `challenge =
   challenge_weight × typology_mult(challenge.typology)`; strict `>` updates, **ties
   defend**. One multiplier table serves both sides ("'I saw it' resists harder than 'I
   heard it,' on both sides"); every term a `SERVICE_DEFAULTS` knob, per-agent overridable;
   0.0 is the per-side kill-switch shape.
2. **The head text reuses the RECONSTRUCTION role** — **ruled against the recommendation**
   (a new judge-shaped `LONGMEM_MODEL_DISSONANCE` var was recommended; the second such
   divergence after the C2 trim, both rejecting new machinery where a leaner existing
   mechanism carries the behavior). One single-item call through the existing provider
   writes the stance-forked retelling; spend prices under the reconstruction keys (stated
   in the spec); result fields are function-named (`retell_*`). Fail-loud 502,
   nothing written (the authorial all-or-nothing precedent).
3. **Tellings-only; NO new migration** — the explicit per-target scope fact, and the ruling
   `fact-level-correction.md` reserved ("diegetic fact-writes need their own ruling"): they
   do not happen. The fact basis/embedding never moves; retrieval keeps matching the
   original account; a game wanting the confronter's account retrievable observes the
   confrontation as an ordinary event. The fact-chain CHECK keeps rejecting the diegetic
   verbs (walker-probed).
4. **`update_with_resentment` anchors take the authorial fixed-constraint branch** (closes
   the fork the 2026-07-17 authorial spec deferred "decided with the dissonance path"):
   `FIXED_CONSTRAINT_ANCHORS = {authorial_correction, update_with_resentment}` at the
   `build_reconstruction_item` branch and the stage-4 ablation partition; observation gist
   is never re-injected over an accepted account; the ablation switch never blanks a
   correction head (fork 11 inherited). `rationalization` still never anchors.
5. **Route: `POST /v1/events/diegetic-correction`.**
6. **Full surface scope in the one session**: C# mirror + interop beats, REPL `:confront`,
   chain-inspector corrections block — all three taken.
7. **The formula is §8 verbatim — no `typology_confidence` term** (the planning-surfaced
   refinement consciously declined; Phase-D revisitable with measurements).
8. **The two stale `architecture.md` lines fixed in the doc pass** (the `write_cause` enum
   list and the drift-anchor set, both missing `enrichment` since C1 — verified against
   migration 006 and the anchor SQL before editing).

**Consciously declined at spec (recorded in `dissonance.md`):** a `dissonance_enabled`
kill-switch (the event is client-invoked — not sending it is the off state; deliberately
unlike the `*_worker_enabled` flags); persisted decision numbers (the response carries them;
the `corrections` row is the record; widening it would be a migration).

**A third documented bite of the carried walker item (DB-global counts on the shared
scratch):** the first sweep failed at `verify_authorial_correction` — its "no corrections
row (diegetic-only by CHECK)" assert is DB-global, and the re-opened `verify_reconstruction`
[13] section had written correction records two walkers earlier. Resolved by the minimal
footprint: [13] writes chain rows + eviction only (the anchor claim under test derives from
the telling chain alone; the record obligation is `verify_dissonance`'s, scoped per-run).
The elder walkers stay byte-untouched; the global-emptiness asserts in
`verify_authorial_correction`/`verify_fact_correction` remain order-fragile by construction
— recorded here for the carried item's own future task, not fixed at this ride-along.

## Phase C5 build record — client contract completion landed — 2026-08-17

**Decided (plan-mode session, then built plan-to-floor the same day):** C5 had no spec doc —
the only Phase C item without one — so the approved plan served as the spec, with the contract
landing in `unity-client.md` (the client-contract doc) + `architecture.md` rather than a new
file. Seven forks settled at two plan-mode batches; **all seven recommended options taken**
(no divergence this time). The route's founding 2026-07-27 motivation (the multi-client
reputation snapshot) died with A1; it was built on the three later-recorded dependencies that
named it their consumer (the pressure gauge's standing surface, the passthrough integrator
read, the two orphaned run logs).

1. **Payload = the STANDARD shape**: the recorded surfaces (pressure gauge, live bundles incl.
   passthrough, both run logs) PLUS the stored agent row (name, seed_identity, rigidity,
   diagnosticity_goal, `config` **as stored** — SERVICE_DEFAULTS never merged; a resolved
   snapshot rots), the current `identity_version`, and the live-beliefs list. **Rejected:**
   LEAN (recorded surfaces only — the row and beliefs stay unreadable anywhere post-creation;
   bundles reference beliefs the client cannot resolve) and FULL (+ rendered identity text,
   effective config, memory counts — derived wire state; the counts duplicate the index read).
2. **Path = `GET /v1/agents/{agent_id}/state`** — a composed runtime snapshot, not the created
   resource; sits beside `/memories`; the plain resource URL stays free. **Rejected:**
   `GET /v1/agents/{id}` (promises "the row you created" while returning run logs).
3. **The unscored carve-out's FOURTH member** — the ruling `reflection.md` pre-assigned to this
   task. Propagated: `CLAUDE.md`, `architecture.md` §6/§12, `test-suite.md`, `tests\CLAUDE.md`,
   `unity-client.md`.
4. **NO migration — the ruled per-target scope fact** (never inherited): the gauge is
   computed-never-stored by standing rule; every table and index the read touches was pre-laid
   in 001/007/008 (both newest index comments named this read). The walker's section A asserts
   the ledger still ends at 008.
5. **Fire-and-forget shape = `ObserveAndForget` + `PendingObserves` + `DrainObservesAsync` +
   `OnObserveFailed` on `NpcSession`** (~40 lines, no queue, no pump; the session is the ruled
   home — the client stays a 1:1 verb mirror). **Rejected:** a discardable Task (a discarded
   faulted Task surfaces nowhere — swallows by construction) and an internal queue+pump (real
   new moving parts buying an arrival ordering that world-time stamping already provides: the
   event is stamped synchronously at the call, and `valid_at` + every product ordering ride
   the timestamp).
6. **No auto-drain in any verb** — drains always explicit; "drain at scene edges" ships as
   integrator guidance (the reflect-at-scene-edges shape); E2 choreography places the actual
   drains. **Rejected:** SceneBoundaryAsync draining first (a hidden multi-second await inside
   an on-camera verb).
7. **Unity face: Core + harness only** — the adapter and demo driver untouched (Play-mode
   verification suspended by ruling since 2026-08-05; the committed DLL refresh is Phase F's,
   so Unity could not see new members before then anyway; the driver's observe staging is E2
   choreography). The `_busy`-gates-the-whole-UI symptom in `NpcDemoDriver` stays for E2.

**Build-latitude choices, recorded:** `runs_limit` = `Query(default=100, ge=1, le=1000)`
governing BOTH run logs (the agent-memories `limit` precedent — a caller argument, never a
config knob); reflections and bundles carry no limit (bounded by mechanism); the beliefs list
rides the ruled compiler-window order, so its first `compiler_window_k` rows ARE the compile
window by construction; bundles = newest live row per (reflection, scene_type), liveness
derived (the §10 contract), outer order = belief window order then scene_type; the dormant
reputation columns excluded from the payload; `reflection_pressure_norm <= 0` raises the
reflect verb's ValueError verbatim (one rule at both gauges); instrumentation = `total_ms`
only (homogeneous SQL — no per-section ceremony); `seed_identity` in, rendered identity text
out (derivable by the public formula); the walker-facing oldest-first fetchers stay
byte-untouched — the route rides four new SELECT-only fetchers + a widened `fetch_agent`
(`name` joined the SELECT, the additive C4-rigidity precedent); drain failures re-throw as ONE
`AggregateException` (stable type even for a single failure) and clear on drain — an
acknowledged failure is not re-thrown twice, and an abandoned (cancelled) drain is not a
drain; the tracker task catches its own exception, so nothing reaches
`TaskScheduler.UnobservedTaskException`. One honest caveat documented in `unity-client.md`:
an observe fired before a reflect but ARRIVING after it counts toward the new pressure epoch
(the gauge thresholds on arrival-side `created_at`).

**Landed:** `GET /v1/agents/{agent_id}/state` (app\api.py, pass-through) over
`RetrievalService.agent_state` in the unscored inspector section; `AgentStateResult` + four
sub-models (schemas.py — full 007/008 column mirrors, the EnrichmentRunOut precedent);
**Set O (10 scenarios, none nlp-marked** — suite 172 → 182, subset 158 → 168); the **twelfth
walker `verify_agent_state.py` (26 assertions**, sections A–F: no-migration shape, gauge hand
math + the loud norm guard, beliefs/bundles liveness + orders + verbatim passthrough, run-log
mirrors, the wire ladder + route-JSON==service-JSON + present-null tri-state, zero-writes
proof; per-run fixture scoping, runs LAST in sweeps); the C# mirror (`AgentStateAsync` + five
DTOs in the inspector-reads section — client-only, the inspector precedent; NpcJson unchanged,
tri-state on nullable value types); the `NpcSession` fire-and-forget surface; **harness beats
[15]/[16] (36 → 50 checks)** — [15] proves the as-stored row echo, identity currency agreeing
with the session's frozen version, beat-[12]'s beliefs riding the read, and the
endpoint/worker split visible as EMPTY run logs on a live store; [16] proves fires return with
calls in flight, a dialogue turn completes WITHOUT draining, both rows land in CALL-time world
order over the wire, and the bogus-agent failure path (a harness fixture — the one
deterministic fake-mode failure) re-throws typed at drain with the event fired once.

**Verification:** Set O 10/10 on the first run; the walker 26/26 on the persistent scratch
(one tolerance fix: `importance_raw` is float4, so the hand-math compare runs at 1e-6, the
pytest.approx class, not 1e-9); both C# projects 0-warning (Release); the interop gate
**50/50 LIVE** against a served fake-mode app on the recreated `longmem_smoke` scratch; full
suite **182 passed** including the nlp-marked set. One first-run full-suite failure, honestly
recorded: the new route/model docstrings' phrase "pure SELECT " tripped
`test_no_sql_outside_the_db_module`'s token scan (the hygiene test reads docstring prose too)
— reworded to "SELECT-only", a wording fix, no rule change. **Believability non-regression:**
C5 touches zero retrieval, scoring, or dialogue code (an additive read route + client-side
machinery); the evidence is Sets A–N green + the elder walkers byte-untouched — the C3
evidence class, not a harness compare run. Flagged: if Jack wants the full harness compare
regardless, it is one command on the standing rig.

**Doc drift corrected in-pass (dated in place):** `unity-client.md`'s verb table was missing
`ReflectAsync` (a C2 propagation miss — the same miss class the C3 build fixed in
architecture.md, now corrected with C5's row and the header at fourteen);
`architecture.md` §12's client paragraph moved twelve → thirteen verbs; `SETUP.md`'s harness
line stopped pinning the check count (it said 32 while the gate stood at 36 — its second rot;
now points at the line itself).

## Phase C6 build record — the purge endpoint landed — 2026-08-18

**Decided (plan-mode session, then built plan-to-floor the same day):** C6 — the purge endpoint,
the ruled release-blocker and the SOLE sanctioned content DELETE — landed on the four plan-batch
rulings below. No spec doc (the contract lives in `architecture.md` §12); NO migration (the
ledger stays at 008 — purge only deletes from the existing 001–008 tables).

**The four forks, ruled at plan mode (one AskUserQuestion batch; all four recommended options
taken — the C5 pattern held):**
1. **Scope — per-memory (episode).** `DELETE /v1/memories/{id}` deletes one memory and its seven
   tables; reflections derived from it survive as aggregate work-product (their un-FK'd
   `source_memory_ids` may dangle). This is the literal `architecture.md` §12 contract and the
   precise answer to the hostile-integrator question "can a player's memories be deleted?".
   Per-agent (whole NPC) and both-verbs were the priced alternatives — the latter the
   architecturally complete option, its cost stated; per-memory is what the task named. This
   CLOSES the `parameter-compiler.md` C6 note: purge does NOT reach reflections, so bundle purge
   semantics never arise.
2. **HTTP shape — the `DELETE` verb.** `DELETE /v1/memories/{memory_id}`, a 200 body with
   per-table counts + total_ms. The "delete verb" the docs literally name; clean REST. (A
   `POST .../purge` sub-resource and a CLI-only script were the alternatives.)
3. **Safety — no guard.** Plain delete; the integrator owns retention safety (the documented
   stance) and REST DELETE is already deliberate — "ceremony scores below absence." (A dry-run
   preview flag and a confirm-echo were the priced alternatives.)
4. **Migration — none.** Purge only deletes from the existing 001–008 tables; recorded as the
   explicit per-target "no migration" scope fact, never inherited (a purge-audit /
   proof-of-deletion table was the priced GDPR-compliance alternative, declined as unscoped).

**Mechanics.** No FK in the schema declares ON DELETE — every reference is bare NO ACTION, so
nothing cascades and the purge is an explicit child-before-parent set of DELETEs in one
`conn.transaction()`, each scoped by the single `memory_id`, opened by a `SELECT ... FOR UPDATE`
existence-lock (the clean unknown-id → None/404 before any DELETE runs, plus race safety against
a concurrent correction/enrichment on the same row). Order: corrections (references
memory_details AND memories) → reconstruction_cache → memory_fact_versions →
memory_enrichment_runs → memory_gist_spans → memory_details → memories. The `db.py` header's
sanctioned-write enumeration gained purge as the FIRST content DELETE and, in the same edit,
reconciled its stale eviction-site list (two named → four real: `apply_reflection` and
`apply_diegetic_correction` had joined with C2/C4). Backend seam: `db.purge_memory` +
`PurgeOutcome`, `PurgeResult`, `IngestService.purge_memory` (timed), the sixteenth route.

**Verified (independent floor-verifier, PASS on all eight criteria — floors row 30).**
`verify_purge` (21 assertions, sections A–G, id-scoped) on a FRESH pid-scoped scratch;
`-m "not nlp"` 175 passed twice (Set P's 7 among them; 182 → 189 full / 168 → 175 subset);
migrate idempotent (8 applied, 0 pending; no 009); product `longmem` pristine (14 tables at 0,
ledger 001–008) before and after; the only new content DELETEs are the seven inside
`db.purge_memory`, transactional, touching nothing else (the four pre-existing DELETEs stay the
cache evictions); SQL-containment + ruff clean; a live uvicorn beat (fake mode) DELETE → 200 +
counts → `/chain` 404 → reflection survives → re-DELETE 404.

**Doc-honesty note (carried to Jack, not a ruling):** `write-path.md`'s "Deferred, documented
only" list was stale for BOTH its entries — diegetic-correction (built C4) and purge (now C6). I
reframed the whole two-item list to "Built since (previously deferred, documented only)" in the
same pass rather than flip purge alone and leave a false "no handler in v1" beside diegetic.
Recorded so the scope call is visible.

## Phase C7 fork rulings and Stage A build record — the concurrency cap landed — 2026-08-18

C7 was queued as the "latency **trio**" (concurrency cap + scene-boundary reconstruction pre-warm
+ prompt caching). Exploration surfaced one decisive fact that reshaped it, and Jack ruled three
forks in one plan-batch (the settle-at-spec `AskUserQuestion` shape). C7 is now the latency
**pair**; Stage A (the cap) landed this session, Stage B (the pre-warm) is next.

1. **Prompt caching DEFERRED (leg 3 cut from C7).** Anthropic's minimum cacheable prefix is
   **4096 tokens on Haiku 4.5** (non-monotonic: 1024 on Sonnet 5 / Opus 4.8, 512 on Opus 5), but
   the dialogue and reconstruction prompt **heads are only ~0.5–1K tokens**, so `cache_control`
   markup would **silently never cache** (`cache_creation_input_tokens: 0`, no error) on the
   ruled Haiku-class slate. Caching buys nothing until the model slate moves — a **Phase D / D1**
   question (D1 already owns "final model-slate confirmation"; a caching-capable model changes the
   math). The byte-stable head it would attach to already exists (`_render_memories(loaded_order=…)`,
   built as groundwork 2026-07-21), so the future build is small. Recommended and taken.

2. **Pre-warm target — probe-driven (for Stage B).** At a scene boundary the server has the
   incoming `identity_version` + `scene_started_at` + the agent's stored memories but NOT the next
   utterance, so retrieval's relevance term is unknown. Jack chose the client to send an
   anticipated-context probe on the boundary event (scored against it), **over my probe-free top-N
   recommendation** — a conscious divergence: it is more precise and folds today's off-camera
   warm-init trick (a throwaway `DialogueInitAsync`) into the boundary call itself. Stage B reuses
   `retrieve_dialogue_init` (embed → fetch → score → `serve`) with the probe as the query.

3. **Pre-warm cache-write guardrail — reuse `serve`'s drift-budget refusal (for Stage B).** The
   2026-07-22 audit R8 asked for a gist-precision check at the pre-warm write. Because Stage B
   reuses `ReconstructionService.serve` verbatim, it **inherits** serve's drift-budget refusal
   (embedding distance candidate-vs-anchor > threshold → refuse the write-back, cache the prior
   head), which satisfies R8's intent (don't bake in unmeasured drift) with **no new gate**. The
   "no new moving parts" recommendation, taken.

**Stage A — the concurrency cap (audit R8), built + floor-verified this session (floors row 31; NO
spec doc — the plan was the spec; NO migration — the request-path wait rides
`DialogueTurnInstrumentation`, the ledger stays 001–008).** There was no concurrency limiting
anywhere: every provider call is a sync SDK call offloaded to the default asyncio thread pool
(`min(32, cpu+4)`), and a streaming NPC holds a thread for its whole stream, so N concurrent NPCs
could exhaust the pool, the DB pool, and the provider rate limit at once. Fix: one process-level
**`ModelCallGate`** (`app\concurrency.py`) = `asyncio.Semaphore(cap)` (the exact logical cap + the
queue-wait measure) + a bounded `ThreadPoolExecutor(max_workers=cap)` (so the default pool never
binds first). It rides the **`Providers` bundle** via a default-factory (the fake-default
precedent — the direct `Providers(...)` test constructions stand unchanged, `build_providers` sizes
it from settings), so every seam + worker reaches it as `self._providers.gate` with ZERO
service-constructor churn. All **13 provider call sites** reroute `asyncio.to_thread(provider…)` →
`gate.run(provider…)`; the streaming prose leg holds one slot for its whole life (`gate.acquire()`
+ `run_in_executor(gate.executor, …)`, released in `finally`, GeneratorExit-safe). The local
spaCy/fastcoref NLP passes are deliberately **not** gated (CPU-bound, already default-pool-bounded,
and the knob names *model* calls). Knob **`LONGMEM_MAX_CONCURRENT_MODEL_CALLS`** (a `Settings` int
on the `judge_max_tokens` precedent, env-validated ≥ 1, default 8 aligned with the DB pool
`max_size`); **`gate_wait_ms`** on `DialogueTurnInstrumentation`; gate `shutdown()` at both
teardowns (`_owns_gate` mirroring `_owns_pool`).

Scope refinement recorded for honesty: the approved plan said "gate everything including NLP"; the
build scoped the cap to *provider* calls (NLP is local CPU, already default-pool-bounded, and the
knob's own name says model calls) — the floor-verifier confirmed this as sound, not a gap.

**Verified (independent floor-verifier, PASS on all seven done-when criteria — floors row 31).**
`verify_concurrency` **11/11** (the FOURTEENTH walker; A cap enforcement peak == cap, B
release-on-exception, C the `gate_wait_ms` source 0.0 uncontended / 200 ms contended, D seam wiring
`gate_wait_ms == 0.0` + byte-identical); `-m "not nlp"` **175 passed** (floor held) / 189 full; the
wiring audit (all 13 gated, every remaining `to_thread` non-provider); the knob validation (int ≥ 1
`ConfigError`, `ModelCallGate(0)` `ValueError`); no 009, ledger 008; `git diff app\` adds zero SQL
writes (the invariant untouched); ruff clean.

## Phase C7 Stage B build record — the scene-boundary pre-warm landed — 2026-08-18

Stage B completes the buildable C7 (leg 3, prompt caching, deferred to Phase D — see the Stage A
entry above). Built + floor-verified this session, plan-to-floor (floors row 32; NO spec doc — the
approved plan was the spec; **NO migration** — an optional request field + reuse of `memories` / the
vector index / `reconstruction_cache`, the ledger stays 001–008).

**What it does.** `POST /v1/events/scene-boundary` (→ `IngestService.scene_boundary`) previously
recompiled only the identity document; C7-B adds its second consumer. An optional
`SceneBoundaryEvent.prewarm_context` carries an anticipated-context probe for the incoming scene (the
probe-driven ruling). Present + non-empty => the new `_prewarm_reconstruction` runs the existing
`RetrievalService.retrieve_dialogue_init` (embed -> fetch -> score -> `serve`) with the probe as the
query, at the **freshly recompiled** `identity_version` + the boundary's `client_timestamp` as
`scene_started_at`/`as_of`, so `serve`'s reconstruction write-backs land the cache under the exact
composed keys `(identity_version, band)` the first on-camera read looks up. Warm stats fold into a new
`ScenePrewarmInstrumentation` on `SceneResult.prewarm` (None unless a probe was sent — the off state,
the C4/C5 client-invoked precedent). This folds the demo's off-camera warm-init trick (a throwaway
`DialogueInitAsync`) into the boundary call itself.

**The R8 guardrail by inheritance (the reuse-drift-budget ruling).** The pre-warm adds NO new gate:
reusing `serve` verbatim inherits its drift-budget refusal (candidate-vs-anchor cosine >
`drift_budget_threshold` -> refuse the write-back, cache the prior head), which satisfies R8's "don't
bake in unmeasured drift" with no new moving parts. The floor-verifier confirmed the warm path routes
through `serve` and adds no threshold/cosine/drift logic of its own.

**Fail-quiet + wiring.** `_prewarm_reconstruction` wraps the warm in a broad `try/except` returning a
degraded record, so a warm failure never fails the boundary (it still recompiles identity and
returns). `RetrievalService` is injected into `IngestService` (optional param, default None, so the
many direct `IngestService(...)` test constructions stand); both construction sites now build
retrieval before ingest and pass it, and a `TYPE_CHECKING` import breaks the ingest<->retrieval cycle
(`retrieval.py` imports `ingest.py` for its exception classes).

**Verified (independent floor-verifier, PASS on all five done-when criteria — floors row 32).**
`verify_prewarm` **14/14** (the FIFTEENTH walker; A a probe warms the cache cold->warm, B the next
same-basis init is CALL-FREE — zero reconstruction tokens, the honest signal since `reconstruction_ms`
still times the partition + cache fetch on a hit, C no-probe = the unchanged off state, D fail-quiet);
the drift-budget refusal confirmed inherited structurally; `-m "not nlp"` **175 passed** (the pre-C7-B
scene-boundary tests green) / 189 full; the C7-A floor re-checked (`verify_concurrency` 11/11); no
009, ledger 008; the warm adds zero new SQL writes (only `serve`'s sanctioned write-back + cache
writes); ruff clean.

## Phase D1 — latency, believability, and the model-slate lock — 2026-08-19

**Context.** Phase D1 of the road-to-completion roadmap: the full-system latency + believability
pass, knob tuning, and the final model-slate confirmation. Exit criterion: the numbers that go on
screen in the demo. The measurement rig was already built (the load driver, the harness's
`compare`/Pareto, judge-free metrics, the Opus judge), so D1 is a **measure → rule → tune →
re-verify** pass, not a new-code build. Three forks were settled at plan approval (the
settle-at-spec `AskUserQuestion` batch); Jack chose the fuller campaign on all three: **(1)**
stronger models for the batch roles (reflection + compiler); **(2)** judge-free non-regression
**and** judged believability; **(3)** authority to flip worker defaults and lock knob values in D1
from the data, no separate ruling round. All runs are real-providers-only (ruled 2026-07-22).

**The measurements (real mode, current slate; ~$2.5 total spend).**
1. **Latency (the load driver, 60 turns).** perceived-first-word **p50 938 ms** / p95 1516 ms —
   essentially identical to the ruled 943 ms and the 2026-08-07 baseline (928 ms). The Haiku slate
   holds the sub-1 s bar (query_embed p50 267 ms warm, first_word p50 599 ms). Cost ≈ $0.12/100
   turns all-in. Recorded gap: the synthetic driver stayed inside the decay band (0 reconstruction
   write-backs), so it does not exercise reconstruction latency — a scripted time-jump session is
   the follow-up if the demo needs reconstruction timing on screen.
2. **Believability non-regression (`run` on judged.jsonl).** gist_precision **0.765 → 0.823** (up),
   fabrication_rate 0.036 → 0.043 (flat, low), keyword_retention 0.887 → 0.848, detail_recall
   0.695 → 0.660, fabricated_entities 2 → 1; perceived-first-word 918 ms. No regression — the small
   down-moves are within documented real-mode single-run noise; reconstruction fired here (34
   write-backs, so its cost/latency IS measured this run: $0.028).
3. **Compare/Pareto + judged (haiku vs sonnet5, judged.jsonl).** haiku 0.913 acc / **1020 ms** /
   $0.93 vs sonnet5 0.954 acc / **2049 ms** / $1.18 (both on the frontier this run — a genuine
   trade-off). Prose pairwise: sonnet5 preferred **44–4** (4 tie), higher on all four dimensions.
   This reaffirms the 2026-08-12 dialogue ruling on fresh data: sonnet5 has the real quality edge
   (prose + slightly higher judged accuracy), haiku wins decisively on latency (2× under) at lower
   cost — **haiku stands for dialogue, latency rules.**
4. **Batch-role validation (real reflect + compile, Opus 4.8).** reflect synthesized 3 coherent,
   identity-relevant, evidence-cited beliefs in 17.8 s (~$0.033, 2.8k in / 0.7k out); compile
   produced 4 bundles in 7.8 s. Opus 4.8 is validated for both idle-time batch roles — the belief
   quality is clearly there, and seconds-scale latency does not bind (the point of "stronger batch
   roles").

**The rulings (settled from the data, per the flip-in-D1 mandate).**
1. **Model slate LOCKED.** Latency-bound roles (write triad, escalation, dialogue, reconstruction)
   stay **Haiku 4.5** — confirmed. The two blank batch roles are assigned **Opus 4.8**
   (`LONGMEM_MODEL_REFLECTION` / `LONGMEM_MODEL_COMPILER`), priced 5.00/25.00. The whole real-mode
   slate is now exactly two models — Haiku for the latency-bound path, Opus 4.8 for the judge +
   batch quality — so "stronger batch roles" adds no new moving part beyond a role assignment. The
   lock lands in the tracked `.env.example`; **syncing the live `.env` is Jack's action** (the C2
   "applying to the product store is Jack's, not the build's" precedent), and the roles are
   loud-at-first-use if left unset, never silent.
2. **The three worker defaults stay OFF — "flip on the data" resolves to per-agent opt-in.** The
   data does not earn a *global* flip: deferred-writes trades observe-return latency the demo does
   not stress, and a default-ON landing would force re-verifying every observe-exercising floor (the
   C1 "substantially bigger landing" caveat); reflection/compiler-worker-ON means continuous
   idle-time Opus spend for every agent. The demo enables reflection + compiler **per demo agent**
   in E-phase. `config.py` is unchanged.
3. **Prompt caching stays DEFERRED (the C7 deferral, D1-confirmed).** The Haiku cacheable-prefix
   minimum is 4096 tokens (re-verified this session against current Anthropic docs) while the
   dialogue/reconstruction heads are ~0.5–1K, so caching never fires on the latency-bound roles that
   would benefit; the roles moving to Opus 4.8 are batch/idle-time with no stable reusable prefix.
   Caching buys nothing on the locked slate. No `cache_control` built.
4. **Dissonance multipliers KEPT — flagged, not tuned (a plan-vs-reality note for Jack).** The plan
   slated the dissonance multipliers (`config.py` `dissonance_typology_*`) for D1 tuning "from
   measurements," but there is **no objective metric to tune them against** — the defend-vs-update
   split is a design prior (how defensible each memory type is: observed 1.0 > told 0.6 > reflected
   0.5 > inferred 0.4), not a measured quantity, and no eval scores dissonance correctness. D1 keeps
   the current principled ordering unchanged and surfaces this for Jack's ratification (the knob is
   re-tunable at any time; an eyeball run of the defend/update beat is available on request).
5. **Judged prose kappa stays unquotable (0.37 < 0.6), non-blocking.** The fresh compare's prose
   verdicts (44–4) confirm the 2026-08-12 direction, but the reference-label kappa remains below the
   0.6 bar (skewed marginals + tie-protocol at small n — the documented cause). Clearing it is
   Jack's standing offline re-labeling task; it does NOT block D1, because the on-screen
   believability numbers are judge-free (The Ledger) and the slate ruling is latency-driven
   (structural, quotable).

**Landed.** `.env.example` batch-role lock (models + prices + Phase-D1 comments); `config.py`
untouched (no default flip, no knob change); `-m "not nlp"` **175 passed** (no regression); product
`longmem` pristine (ledger 001–008, all product tables 0 rows). **No new floors row** — D1 built no
new layer; it is a measurement + configuration-decision pass. **Phases C and D are complete; Phase
E (demo) is next.**

**Pending Jack actions (recorded, non-blocking to D1's landing):** sync the live `.env` batch roles
(Opus 4.8); ratify or redirect the dissonance-multiplier defaults; the offline gold re-labeling if
calibrated judged prose numbers are wanted on screen.

## Phase E1 rulings + build record — the authoring guide and demo corpus landed — 2026-08-19

**Context.** Phase E (demo) opened. Jack delegated the phase's session-splitting; the scope
decision made and recorded: **Phase E runs as three sessions** — E1 (this session: the identity
authoring guide + demo corpus + authoring-time validation), E2 (choreography + rehearsal; it owns
the real code gaps: the corpus→demo-DB loader, the C# `prewarm_context` field, the `NpcMemoryNpc`
fire-and-forget observe passthrough, the Ledger live-feed decision), E3 (record + edit).

**Rulings (Jack, at spec — the plan-mode fork batch):**

1. **The demo NPC is a NEW character/setting** — not the gray-box ford Keeper, not
   fixture-adjacent. (Authored: **Branwen, keeper of the Waystone Inn** at the north-road
   crossroads below Harrowmere — all proper nouns checked fresh against every fixture.)
2. **Seed identity: short first-person paragraph** (4–6 sentences; on camera in the Ledger;
   seed entities are fabrication-whitelisted) over the fixture one-liner or third person.
3. **The judge-free held-out harness run happens in E1** (no `--judged` — kappa 0.37 stays
   unquotable; on-screen numbers stay judge-free per D1), not deferred to E2.
4. **E1 scope confirmed: docs + data files + validation runs only.** No code, no migration, and
   **no floors.md row** (the D1 precedent — no layer built). The corpus→demo-DB loader is E2 work.

**Landed.** `docs\identity-authoring.md` (the integrator guide, §8 = the demo NPC as worked
example, em-dash-free per the 2026-08-13 public-prose ruling; indexed in `docs\README.md`);
`data\eval\corpora\demo-waystone.jsonl` (1 scenario, 9 observes, June in-world, drift-corpus
shape); `data\eval\scenarios\demo-waystone.jsonl` (3 scenarios, ALL `held_out: true`: the Halvard
correction probe, the drovers drift probe, the nameless-lodger abstention probe — new files;
nothing in the suite pins them, verified). Validation, real providers (runs-dir artifacts are
gitignored; numbers quoted here): **coverage drift-validate** (k=9, age 60d): 9/9 reconstructed,
0 over budget vs 0.35, distance p50 0.06 / p95 0.11 / max 0.121, self-check matched;
**beat-condition drift-validate** (drovers probe, `--max-items 3`): target served top-3 on every
roll, distance 0.082 on a retell-mode roll; **held-out run** (judge-free, real): exit 0, 2/2
expected-ID checks, fabricated entities 0, fabrication_rate 0.000, keyword_retention 0.979,
gist_precision 0.720, detail_recall 0.664. Suite subset green at every turn (Stop hook).

**What the authoring loop found (five corpus revisions; each failure caught by drift-validate or
a kept scratch DB, which is E1's whole point):**

1. **Gist saturation makes a memory un-driftable and retell-flaky.** The chimney-fire observe
   (authored as maximal drama) escalated to 11 gist spans covering 66% of its text; the leftover
   detail was punctuation fragments, and on that degenerate input the Haiku retell sometimes
   returned no usable retelling (the serve path's per-item salvage soft-degraded it to its live
   head — honestly, but invisibly for a demo beat: the coverage report showed 8/9 checked).
2. **The render witness-voices the NPC's own actions.** "Branwen turned two drovers away"
   rendered as "I watched Branwen turn away those two drovers"; passive phrasing still rendered
   "I watched as...". First person in the observe ("I turned away two drovers") renders owned.
   Guide rule: first person for the NPC's own actions, third for what it witnessed — this also
   binds E2's game-authored action-observes.
3. **The diagnosticity goal couples importance AND gist.** The fire scored importance 0.32 under
   "who owes the house and what news the road brings" and lost k=3 membership to fresher gossip;
   widening the goal to "what threatens the house..." moved it to 0.72 — and simultaneously
   promoted house-flavored texture into fixed gist (the coupling is structural: both stages read
   the same signal). Texture that must drift has to be goal-orthogonal AND name/number-free.
4. **Retell behavior at the first aged read is per-call bimodal** (temp-1.0, no sampling params):
   some calls edit richly (0.05–0.20 distances), some echo the telling verbatim (distance 0.000),
   correlated within a call. No corpus prose removes this. What saves the demo: importance, spans,
   and the first retelling all FREEZE once rolled (write-time values; the reconstruction cache
   pins the take by the constancy invariant) — so E2 rehearsal inspects the provisioned roll and
   re-provisions/re-rolls until the take is good, after which it is byte-stable.
5. **The certified drift target switched from the chimney fire to the turned-away drovers**
   (the fire echoes on most rolls — an escalation magnet; the drovers memory drifted on 6 of 7
   observed rolls across all its phrasings and is her OWN action, which ties into beat 3's
   action-observe story). The fire stays in the corpus as the closing incident and remains a
   viable second take if a rehearsal roll lands rich.

**Production-vs-fixture note (explicit):** the corpus agent config carries no worker flags (the
runner needs deterministic replay); the E2-provisioned demo agent adds
`reflection_worker_enabled` / `compiler_worker_enabled` per the D1 ruling — same seed, goal,
rigidity, and decay config, diverging on exactly those flags.

**Surfaced for Jack (non-blocking):** the drift-validate report does not surface the turn's
`degraded_reasons`, so a retell dropout shows only as items_checked < observes (finding 1 was
diagnosed via a kept scratch + a forensic re-probe); a small runner improvement (echo the turn's
degraded_reasons into the report) would make the next authoring loop cheaper. Out of E1 scope by
ruling 4 — flagged, not built.

**E2 handoff (recorded):** corpus→demo-DB loader carrying the SAME agent fields as the corpus
block + the worker-enable flags; verify the provisioned roll (importance/spans/retell take) on
the demo DB before recording, re-provision if bad; the beat utterance at k=3 with the certified
drovers question (or k≥4 / a context nudge if choreography prefers the fire); Unity inspector +
nameplate sync to Branwen; C# `SceneBoundaryEvent.PrewarmContext`; `NpcMemoryNpc`
ObserveAndForget/Drain passthroughs; the Ledger live-feed decision + polish; the standing
pending-Jack items (live `.env` Opus sync binds when the demo agent's workers turn on).

## Phase E2 rulings + build record — choreography, the code gaps, and the Ledger live feed — 2026-08-19

**Context.** The E1 handoff executed: the beat script, the three code gaps, the Unity retarget,
and the rehearsal staging. Verification was ruled demo-scoped (ruling 3 below), so no floors row
and no floor-verifier dispatch; the build-time gates (suite, harness, Unity compile) all ran.

**Rulings (Jack, at spec — the plan-mode fork batch):**

1. **The Ledger live feed = server tee + poll.** The two dialogue routes tee each terminal
   `DialogueTurnResult` into an in-process module-global ring buffer (cap 256, a module constant
   — a demo inspector surface, not integrator config); the new schema-hidden
   `GET /v1/ledger/turns?after=<seq>` serves it; the Ledger polls it on its existing 2 s poll.
   **An explicit carve-out to the 2026-07-13 route pass-through ruling:** the response stays
   byte-identical, but the dialogue routes now record the result in PROCESS MEMORY — never the
   DB; a dialogue turn still persists nothing, and a restart starts the feed empty. Beat the
   Unity-push shape (client changes, REPL blind) and keep-paste-drop (a manual step in every
   take).
2. **Worker flags land at the END of the load.** The loader inserts the agent with the corpus
   config verbatim, replays deterministically (its in-process workers idle over the un-flagged
   agent), then merges `reflection_worker_enabled: 1.0` + `compiler_worker_enabled: 1.0` via the
   new **`db.merge_agent_config`** (`--no-workers` skips). **This sanctions a second in-place
   write site: `agents.config`** — runtime config, not memory content (the `memories.pinned`
   precedent); row-locked read-merge-write, in `db.py` because the SQL-containment hygiene test
   binds. Beat flags-at-insert (workers could reflect mid-replay — a non-deterministic roll) and
   the separate `--enable-workers` second step (an extra manual step per re-provision).
3. **E2 verification is demo-scoped: NO floors row, no floor-verifier dispatch** (the E1
   precedent, extended to a session that DOES land code). The new pytest coverage, the 17-beat
   harness, and the Unity gates still ran at build time (the Landed section).
4. **No new migration** (scope fact confirmed explicitly). Migrations stay 001–008; the worker
   flags ride `agents.config` jsonb and the feed is in-memory only.

**Landed (code).** `app\schemas.py` `LedgerTurnEntry`/`LedgerTurnsResult`; `app\api.py` the tee
(`_tee_turn` at both dialogue routes — the SSE pump tees even on client disconnect) + the feed
route; `app\db.py` `merge_agent_config`; **`app\demo_loader.py`** (`python -m app.demo_loader`,
`--fresh` REQUIRED to act — the only destructive path; targets `longmem_demo` via
`provision_scratch`, replays the corpus through `SessionRunner`, prints the provisioned-roll
report + the agent-id/deep-link hand-off, merges the worker flags last); C# parity —
`SceneBoundaryEvent.PrewarmContext`, the 13-field `ScenePrewarmInstrumentation`,
`SceneResult.Prewarm`, `NpcSession.SceneBoundaryAsync(sceneType, prewarmContext, ct)` (naming
falls out of the snake_case strategy, no attributes); harness beat **[17]** (verify_prewarm
A/B/C over the C# wire); `NpcMemoryNpc` ObserveAndForget / DrainObservesAsync / PendingObserves
passthroughs + the prewarm param (`OnObserveFailed` stays reachable via the public `Session` —
events have no one-line forwarder; documented, not wrapped); `NpcDemoDriver` beat controls
(correction, async observe + pending readout + explicit Drain, prewarm-carrying boundary,
`sayK`, `jumpDays=60`); the Unity scene retarget (attach-mode `autoProvision: 0`, Branwen agent
fields, nameplate `Branwen`); the Unity plugin DLL refreshed (was stale since 2026-08-04,
pre-C2 — four phases behind); `ledger\index.html` the live turn-feed poller + the
identity/state pane (`GET /v1/agents/{id}/state` — the seed identity on camera per E1 ruling 2)
+ the em-dash label sweep (the 2026-08-13 flagged residue, done — this page is on camera).

**Landed (docs).** **`docs\demo-beat-script.md`** (the E2 deliverable: three beats + close,
timeline, rig, rehearsal checklist; indexed in `docs\README.md`); `unity-client.md` drift fixes
(the prewarm contract on the verb table, the C1-pre-warm bullet + warm-init hook marked
superseded by C7-B, beat [17] in the harness chain, the drain placement resolved);
`architecture.md` route census 16 → 17 + the feed paragraph; `SETUP.md` §8 attach-mode +
gate-ordering rewrite.

**Verification (build-time, demo-scoped by ruling 3).** Suite: `tests\test_ledger_feed.py` (seq
monotonicity, `after` cursor, byte-identity vs both routes' responses, the cap) +
`tests\test_demo_loader.py` (corpus-shape pure test + nlp-marked end-to-end on the suite
scratch: five agent fields verbatim, 9 memories rolled, flags present/absent by path);
`-m "not nlp"` subset green throughout (177 at wrap). The **17-beat console harness** GREEN
against a fake-mode serve on a scratch DB (53 checks — beat [17]: probed boundary returns a
clean prewarm record, same-basis init is a call-free cache hit, probe-less boundary carries no
record). Unity: batch-mode compile + scene re-import clean (the adapter edits + refreshed DLL
compile; the interactive Play-mode gate rides the rehearsal, below). Loader: fake-mode CLI
smoke on a disposable DB (refusal path exit 2; full run printed the roll + hand-off), dropped
after. The Ledger: a LIVE browser beat against a fake-mode serve on a scratch demo DB — the
identity pane rendered Branwen's seed identity + worker flags + pressure, and a turn fired
over plain HTTP rendered into the turn panel through the 2 s poll with no paste (the feed's
end-to-end proof); scratch DB dropped after.

**Rehearsal state — staged, blocked on two Jack-side steps (honest):** the real-provider
rehearsal (beat-script checklist steps 0–6) did NOT run this session. (a) The live `.env`
carries NEITHER `LONGMEM_MODEL_REFLECTION` nor `LONGMEM_MODEL_COMPILER` (presence checked
without echoing values) — the demo agent's workers are ON by ruling, so the pending-Jack Opus
sync now BINDS; running anyway would land a `failed` compiler run row and a loud reflect error
on camera. (b) No Unity MCP bridge was connected this session, so the interactive Play-mode
gate and the on-screen dry-run need an editor session; the ordering (gate BEFORE pasting the
demo agent id — autoRun replays observes into whatever agent the adapter holds) is encoded in
the beat script and `SETUP.md` §8. Everything up to those two steps is built and verified.

**Surfaced (non-blocking):** the feed cap is a module constant by design (the C7 env-var shape
is the promotion path if the never-hardcoded invariant is ever read strictly against a demo
surface); the loader cannot probe "does a pinned take exist" without new SQL (the hygiene
test), so `--fresh` being required-to-act IS the guard — a pinned take can only be destroyed
deliberately.

## E2 rehearsal executed — blockers cleared, the recording state pinned — 2026-08-22

**Context.** Jack cleared both rehearsal blockers (the `.env` batch-role sync; the Unity MCP
bridge connected). This session verified them and ran the beat-script rehearsal end to end.
No new Jack rulings — this entry records the verification and one choreography finding made
inside the delegated beat-script authorship (the 2026-08-19 E2 entry's "Rehearsal state"
paragraph is superseded by this one; append-only, so it stands as written).

**Blockers, verified deeply.** `LONGMEM_MODEL_REFLECTION` / `LONGMEM_MODEL_COMPILER` present,
`load_settings` clean in real mode, both at `claude-opus-4-8` (the locked slate), then proven
on live calls: a real reflect wrote 3 reflections, and the compiler worker auto-ran once
reflections existed — `completed`, 3 pairs, 0 failed, 1246/175 tokens, 3 bundles. The
interactive Unity play-mode gate ran GREEN through the live bridge (8 checks; the fake-mode
serve on a scratch, autoProvision/autoRun flipped in memory and restored, the committed scene
untouched by the gate).

**The rehearsal (two real-provider provisions).** Dry-run first: all three beats + the owed
2026-07-22 beat-1 guard (ref 0's served relevance moved up across the correction; the
post-fix money answer carried the five-shillings debt verbatim-in-substance). Its beat-2
take ECHOED (the E1 bimodal case, working as documented) — discarded by re-provision, the
ruled loop. Final provision, pinned and live in `longmem_demo`: agent
`3f7355f1-fd90-4fce-8d8d-c7e652e33af9`; June layer rolled at the scene-1 prewarm + k=9 asks
(wrong-belief answers on the nose); beat-2 take a real edit — gist_precision **1.00** (3/3),
detail_recall 0.58, 0 fabricated entities, constancy byte-identical on the re-ask; the
correction and beat 3 VIRGIN for camera; no failed worker runs; the Ledger verified
camera-ready on this exact state. The scene's inspector carries the pasted ids (committed).

**The choreography finding (folded into `demo-beat-script.md`): beat-1 asks run at k=9.**
At the June-25 basis under the real corpus config, 23 days of episodic decay (tau 10 d)
buried the June-2 Halvard memory below k=3 — the E1 correction probe had certified k=3 only
under the NEUTRALIZED eval config. k = corpus size is roll-proof; beat 2 keeps its certified
k=3. Corollaries, also folded in: scene 1 carries its own prewarm probe (the June basis
already serves reconstructed for June-2 memories); the post-correction ask visibly re-forms
the telling (the correction's sanctioned cache eviction) and is kept as an on-camera beat,
with re-firing the same correction as the retake lever.

**Standing instruction until E3 records: do not run the demo loader again** — `--fresh` is
the only destructive path and it would destroy the pinned take.

## E3 first attempt — recorded and QA'd, master not cut; presentation redesign ruled — 2026-08-24

**Context.** E3 (record + edit) ran on the 2026-08-22 pinned state: forks settled at plan
approval, the recording executed end to end through a new attach-mode rig (Jack driving the
Unity overlay + OBS, Claude cueing and QA'ing each segment live over the Ledger feed and
chain reads), then footage QA found a scene flaw no edit can fix, and Jack redirected the
endgame (ruling 6).

**Rulings (Jack).**

1. **The edit is Claude + ffmpeg** (cards, captions, per-segment assembly scripted; hard
   cuts) — over an NLE hand-off or a record-only session split.
2. **Captions only, silent** — no audio track; on-screen text carries the framing and the
   close numbers.
3. **E3 scope: demo-scoped, no floors row** (the E1/E2 precedent); nothing enters the repo
   but docs. (Rulings 4–5 amended this mid-session with the sanctioned rig edits below.)
4. **`startAsOf` added to the driver** (a mid-session stop-and-report). Attach mode had NO
   operator surface for the June-25 basis: the overlay only has the +60 button, the session
   clock starts at real now, and recording as-is would have rolled fresh retells over the
   pinned June layer and put beat 2 on an unpinned basis (the echo risk returns). The
   rehearsal never hit this because it drove HTTP with explicit `as_of` per call; the beat
   script's "SetAsOf before the boundary" named a method with no control. Ruled: an ~8-line
   `NpcDemoDriver` field (default `2026-06-25T19:00:00Z`, applied via the existing
   `SetAsOf` once the adapter attaches; the autoRun gate's own timeline untouched) — over an
   off-camera bridge call per take (fragile: a missed step silently re-rolls the June layer).
5. **The overlay's on-camera em-dash fixed** (`longmem-npc · {status}`) — the E2 label
   sweep covered the Ledger page but missed the equally-on-camera Unity overlay.
6. **The retake fork: fresh provision + full re-record, but AFTER a demo-presentation
   redesign session of Jack's own.** Footage QA (full-res frame pulls) found the Branwen
   nameplate mirrored in every Unity frame — TextMesh rotY 180, facing away from the
   camera, invisible to the API-level E2 gates — plus lesser blemishes: browser tab/URL bar
   on camera, the Game-view toolbar strip captured, the input field's ford-era default
   text. Jack: the whole setup "does not make it easy to capture someone's attention"; he
   will alter the presentation in a separate session, so the flaws are **noted, not
   implemented** (they may not survive the redesign), no re-record this session, and
   `--fresh` is sanctioned for the next provision.

**Landed (code, sanctioned by rulings 4–5).** `NpcDemoDriver.cs`: `startAsOf` +
`ApplyStartAsOfAsync` (waits for the adapter, parses invariant-UTC, sets the session clock,
and statuses the overlay — attach mode previously showed "(connecting…)" forever), the `·`
label, the +60 button statusing the new date. The scene: `startAsOf` serialized;
`prewarmContext` set to the beat-1 Halvard question as the committed scene-1 start state
(both prewarm texts are cache-safe at the June basis — the pinned June layer covered all 9
memories). Verified: bridge compile clean, a live attach smoke (Play → clock exactly
2026-06-25T19:00Z with the console receipt; attach init makes zero network calls, confirmed
in `InitializeAsync`), and the pinned-state probe PASS after every editor step. One editor
lesson: the first smoke raced a pending recompile into play mode and produced an
inconsistent domain (Ready true, Session null) — enter play only when the editor is idle.

**Landed (rig, outside the repo by ruling 3).** OBS Studio + ffmpeg 9.0 installed (winget;
neither was present); `C:\Users\jacks\Videos\longmem-demo\` (raw takes, assets, final); the
close card (1920x1080, Ledger palette, the four judge-free numbers, the em-dash-free
tagline "Self-hostable: your Postgres, your models."); the recording run sheet; GET-only
pre-flight probes in the session scratchpad.

**The recording (executed 2026-08-24; every beat PASSED live QA).**

- SEG A (beat 1, k=9): the wrong belief on the nose ("eleven shillings to the farthing...
  bought a round"), the correction landed, and the money ask re-formed carrying the debt
  ("Five shillings, though I'd not expect it back anytime soon").
- SEG B (chain close-up): the same-correction re-fire lever was exercised deliberately
  before the shot — the on-camera ask order leaves the correction head superseded by the
  re-formed retell, and the ruled frame wants the amber `authorial_correction` live; one
  HTTP re-fire restored it (chain 5 rows, live = the operator text verbatim).
- SEG C (beat 2, k=3): the pinned drovers take served with no re-roll (gist 1.00, recall
  0.583, 0 fabricated); **constancy PASSED on the served retelling — byte-identical across
  the re-ask.** The streamed dialogue wrapper differed (temp-sampled per turn; a dialogue
  turn persists nothing): the invariant binds stored/served text, never conversational
  delivery — the beat script's "byte-identical text" camera line is loose on this and the
  caption must carry the precise claim. Also: the re-ask's gate fired (`entity_tripwire`,
  3 fetched), so the second ask served 6 rows vs 3 — working as designed, on camera.
- SEG D (beat 3, k=3): both action observes landed first-person owned (index 9 → 11), the
  recall served the cart memory in `verbatim` mode (fresh, below theta — correct), owned
  first-person answer. No worker runs mid-take; pressure 0.594 → 0.659.

**Found (durable, for the next version):**

1. **A provision serves beat 1 exactly once.** The correction moves ref 0's fact chain and
   evicts the June caches; afterwards the wrong-belief answer is unreproducible on that
   provision. Every beat-1 recording attempt costs a fresh provision + re-pin — which is
   also why today's footage admitted no selective re-shoot.
2. The 2026-08-22 pinned state in `longmem_demo` is now SPENT (three correction heads on
   ref 0, the two beat-3 memories present). The 2026-08-22 standing do-not-run-loader
   instruction is superseded by ruling 6: the next provision runs `--fresh`.
3. Raw takes kept as reference (A 93.5 s / B 24.5 s / C 53.7 s / D 43.5 s, 1080p30; ~215 s
   raw against the ~75 s script target — an honest cut at natural streaming speed lands
   nearer 100 s; speeding up streams was rejected out of hand as it would misrepresent the
   latency numbers the close card claims).
4. Visual QA needs frames, not gates: every flaw in ruling 6 was invisible to the compile,
   play-mode, and API-level gates and surfaced only in extracted full-res frames.

## Roadmap re-sequenced — F0 audit pass added; the demo endgame moves after Phase F; Phase G re-pointed — 2026-08-24

**Context.** Ruled by Jack at the close of the E3 first-attempt session, superseding the
ordering in the same day's E3 entry (append-only: that entry stands as written). The demo
recording pauses; release work comes first.

**The ruling — the road from here to the end, in order:**

1. **Phase F opens with a NEW F0: a whole-project audit/test/improve pass** — the latency
   numbers the best they can be, the wording at its most believable, and everything
   polished to Jack's liking. (F0 naturally inherits the deferred latency levers — prompt
   caching, deferred at C7/D1 pending the slate lock — alongside the believability wording
   work; F0's concrete scope settles at its own session spec.)
2. **F1 → F2 → F3 as already scoped** (the full README; packaging; release hygiene + the
   public flip).
3. **Then the demo endgame:** the presentation redesign (per Jack's rulings when that
   session opens) → the re-record (the E3 second attempt: fresh provision + re-pin +
   record + edit) → **the video publish.**
4. **The parked rulings stay parked** — the walker scratch-DB refactor, the
   dissonance-multiplier defaults, the offline gold re-labeling — each decided whenever it
   needs to be surfaced.
5. **Phase G stays optional but its contents are REPLACED.** The real-game plug-in clip
   (the 2026-07-27 demo-vehicle entry's epilogue) is out; the optional step is now
   **embedding the project into Jack's personal website** so people browsing it can
   interact with the system somehow. Details deliberately deferred — decided only if the
   step is ever brought forward into a working session.

**Sequencing consequence (recorded, not a fork):** the repo flips public at F3 while the
demo video does not yet exist, so the README ships without the video link; the link lands
as a small docs touch in the publish step. The finish-line end state is unchanged: repo
public + video published + package downloadable.

---

## F0 spec rulings + build record — the audit/test/improve pass landed — 2026-08-26

F0's scope settled at its own session spec (the 2026-08-24 re-sequencing's escape hatch): a
plan-mode exploration pass (three sweeps + a latency design + the doc-auditor agent) fed one
AskUserQuestion batch of four forks. Jack ruled; the approved plan is the spec (the C5
precedent). All numbers below were independently re-verified by a floor-verifier pass the
same day (**pass**; the dated floors.md Re-verification entry is the evidence record).

**The four spec rulings (Jack, at the plan batch):**

1. **Latency: "overlap + attribute"** (the recommended option). Build the safe turn-path
   overlap, the pool-size knob, and a `pre_prose` driver series; A/B-measure real; land only
   what the numbers justify. The duplicate-read dedupe (the agent row fetched twice per turn —
   `dialogue.py` + `retrieval.py` — and identity resolved twice, whose removal would also
   close the acknowledged mid-request-mutation window but touches the `/v1/dialogue/init`
   wire model) was NOT selected: recorded here as a surfaced fork, not built.
2. **The big levers: "keep locks, record ceiling"** (recommended). No cache markup, no
   embed-swap spec, no slate re-open. The recorded ceiling: the OpenAI query embed is
   ~230–270 ms ≈ 28% of the perceived median — an embed swap (a 50–100 ms embedder) would
   put the headline near **770–870 ms** but re-opens the locked embedding constant AND the
   stored-vector space (re-embed or a parallel column — its own session); prompt caching
   stays inert on the locked Haiku slate (4096-token minimum cacheable prefix vs our
   ~0.5–1K-token heads — markup would silently never fire); the dialogue slate stays Haiku
   (latency rules, settled a fourth time by declining the re-open). Also surfaced, not
   built: a driver time-jump arm for isolated reconstruction-stall timing (the existing
   believability-run number — 918 ms perceived with 34 write-backs — stands as the
   reconstruction-inclusive evidence); the retrieval-internal overlaps REJECTED at design
   (gate_ms is a ruled timing contract spanning the loaded-set/components fetches — not
   re-opened for ~2–4 ms); and the design note that under concurrency the query embed
   queues behind whole-stream prose slots on the same semaphore (invisible to the serial
   driver; a C7-shaped future question).
3. **Wording: BOTH prompt surfaces** — the dialogue-prompt UUID audit and the write-prompt
   voice clause, each gated by the ruled real-mode believability non-regression protocol.
   The beat-script constancy-line fix and the Ledger label restyle were NOT selected — they
   stay with the presentation redesign / Jack's later call.
4. **README: "leave it all to F1."** The public README's false claims (purge "without a
   handler", "still ahead" list, 25/108/eight counts) stand by explicit ruling until F1's
   full rebuild. Internal registers were separate surfaces and were reconciled (below).

**What landed (31 files, +397/−201; no migration — ledger 001–008 before and after):**

- **Register repair.** floors.md rows 28–32 moved back INSIDE the table block (they had been
  stranded after the Re-verification prose, rendering as literal text — the exact failure
  the file was split out of status.md to fix; byte-pure 5-line relocation, verifier-checked
  by sorted-multiset diff). Counts reconciled to MEASURED reality: suite **193 collected /
  178 subset** (the prior "175" in live docs derived from the C6-era floors evidence and had
  already drifted — E2's three tests included one nlp-marked; always measure, never derive);
  fifteen walkers everywhere (docs\README.md vocabulary, SETUP.md incl. the four missing
  walker names, tests\scratch_uri.py); CLAUDE.md migrations 002–008; test-suite.md's count
  register updated in place with the E2 pair folded in. Cheap doc truths: unity-client.md's
  timeout passage now leads with the current 8.1 s Haiku number; the never-committed
  `rehearse.py` reference annotated. The doc-auditor agent then swept the tree and its 16
  mechanical findings were all fixed: five CONTRADICTIONS (architecture.md "thirteen verbs"
  → fourteen incl. C4's; packaging-before-video per the re-sequencing; reconstruction.md's
  drift-anchor set + eviction list each missing a member C4's ruling-8 pass had fixed only
  in architecture.md; fact-level-correction.md's "only writers" missing migration 006's
  enrichment writer) + eleven stale current-state claims (SETUP.md 001–007/5-migrations/
  eleven-routes; mcp-setup.md through 005; migration-01.md's four un-annotated points incl.
  the seed-immutability correction; authorial-correction.md's "no mechanism writes that
  cause"; unity-client.md's six-groups list; write-path.md's five-triggers line;
  test-suite.md's "paper ablations"; docs\README.md's "four queues"). One auditor flag
  ADJUDICATED AS NOT STALE: unity-client.md's fork-2 "No route exists today" — the section
  sits under a rulings banner that says "The original fork text below stands as specced";
  left untouched by its own convention.
- **The test gap closed.** `test_init_route_error_contract` (Set B, beside init's
  byte-identity pair): unknown agent → 404, caller-passed unknown identity_version → 422.
  test-suite.md's Known-gap paragraph now records the closure. Suite 192 → 193 / subset 178.
- **The turn-path overlap** (`dialogue.py`): retrieval starts as a task; the agent-state
  fetch, a self-timed bundles task, and an identity-resolution task run under it (none
  consumes retrieval output — commented "Concurrent by design"); awaits in the original
  order so error primacy is unchanged (404/422 at all three routes byte-same); cancel-and-
  drain on BaseException (no TaskGroup — ExceptionGroup would break the routes' except
  clauses; no bare gather — it leaks pool connections on failure).
- **The pool-size knob** (`LONGMEM_DB_POOL_MAX_SIZE`, default 8, loud ConfigError shape
  cloned from the C7-A cap): closes the last hardcoded capacity number against the
  nothing-hardcoded invariant; `build_pool(uri, *, max_size=…)` keyword default keeps
  conftest + all fifteen walkers byte-untouched; threaded at the seven app construction
  sites; `.env.example` gained a Capacity section carrying BOTH this and the C7-A cap var
  (which had been missing from the template since C7). `min_size=1` stays deliberately
  un-knobbed — surfaced as a one-line sibling if Jack wants the invariant fully closed.
- **The dialogue-prompt UUID strip.** The audit established the in-prompt id was vestigial:
  it entered with the ruled 2026-07-15 prompt shape when `[output]` was a JSON contract and
  the model cited memories back; A1 removed that contract and orphaned the ids. Nothing in
  production consumes them (not the fake provider, the C# client, or the Ledger — served IDs
  ride the payload from retrieval); THREE test-apparatus sites did (two greppable helpers +
  one inline walker check that only surfaced at runtime) and were reworked to content-based
  assertions, with walker [2] now asserting the id is ABSENT. `_MEMORY_LINE` is `- {content}`;
  cli-harness.md's ruled-shape paragraph carries the dated annotation. Measured effect:
  **dialogue input 40.9–42.4k → 20.6k tokens/100 turns (−51%); all-in $0.109–0.112 →
  $0.0841/100 turns (−23%)**.
- **The write-prompt voice clause** (`_WRITE_SYSTEM`): a register clause for
  `rendered_content` encoding identity-authoring.md §5's three measured rules (the NPC's own
  actions owned in first person — the witness-voice render bug; witnessed stays witnessed;
  no invented names — the fabrication metric). JSON key list byte-identical.
- **The driver rig**: a `pre_prose` per-turn series (perceived − first_word — p50s don't
  subtract), additive to the cli-harness walker's series list.

**The measurements (real providers, D1's 60-turn shape, fresh pid-scoped scratch per arm):**

- Baseline ×2: perceived p50 **826/835 ms** (p95 1427/1314) — ~100 ms under D1's 938 at
  today's network conditions; the same-day A/B is the comparison, never cross-day.
- Overlap arms ×2: perceived p50 873/887 — the +40–50 ms is ENTIRELY provider-side
  first-word drift (534/572 → 600/583 between measurement windows; the embed and SQL
  controls are flat and the walkers prove byte-identical prompts, so the code change cannot
  be the cause). The component the overlap targets — **non-embed pre-prose — fell 27.3/27.7
  → 20.5/18.4 ms**, both runs, exactly the predicted 3–10 ms mechanism win. Kept on that
  evidence: the headline is unchanged within provider noise, the p95 tail-hiding is real,
  and the seam's data-flow is now explicit. The attribution question D1 left open is
  CLOSED: pre-prose ≈ embed (~230–250 ms, ~90%) + gate evaluation (~11–12 ms) + everything
  else (~10–15 ms); retrieval SQL p50 rounds to 0.0.
- Believability gate (the ruled protocol: fake dry-run exit 0 in 29.5 s, then real-mode
  `run` over judged.jsonl vs the D1 baseline artifact): gist_precision 0.8232 → **0.8309**,
  detail_recall 0.6603 → **0.8448**, fabrication_rate 0.0435 → **0.0159**,
  keyword_retention equal at 0.8478, fabricated entities 1 both — **no regression, three
  metrics up**; both prompt changes landed on it (artifacts
  `run_20260826T223224Z_pid_5008.json` vs `run_20260819T055215Z_pid_22240.json`).
- Final post-everything run: perceived p50 **917 / p95 1227** (the best p95 of the day),
  non-embed pre-prose 21.8 ms, and the token/cost deltas above. Real spend for the whole
  session ≈ **$0.55** (five driver runs + two believability legs), under the ~$1 plan cap.

**The incident (tooling-side, zero product code implicated):** a 3-hour double-hang in the
verification chain. Two stacked runner mistakes: a bash `pytest | tail && walkers` chain
binds `&&` to tail's exit (always 0), so a RED subset still launched a walker phase; and the
walker runner let children inherit stdin — under a backgrounded shell it never closes, and
verify_cli_harness's REPL beat blocks on it forever (foreground runs passed only because
their stdin happened to give EOF). Diagnosed by CPU-time signature (~12 CPU-seconds over
hours = blocked, not working), fixed with `stdin=DEVNULL` in every wrapper and un-piped
stage sequencing; the leaked scratch DBs dropped. The hunt also flushed out the third
in-prompt-UUID consumer. Recorded in the session log; the walker-runner cosmetic (the
deferred-writes walker's `N/N criteria passed` banner format not matching the runner's
banner scan) is noted for the carried walker-refactor task, and the verifier's DB inventory
spotted an orphaned `longmem_eval_14188` scratch from an earlier session (left in place —
Jack's call to drop).

**Floors consequence:** no new layer, so no new row — the count stays 32; the same-day
independent floor-verifier **pass** is recorded as a dated entry under floors.md's
"Re-verification passes" (cli-harness, read-path, write-path, and gate floors re-opened and
re-closed inside it).

## The rename — longmem-npc → twicetold-npc — 2026-09-02

**Context.** The consumer-context scan's Fork 3 (ruled 2026-09-01) called for a rename before
the F3 flip. This session picked the name, planned the whole-repo sweep, and landed the
in-repo half.

**The pick: `twicetold-npc`** (from "a twice-told tale" — Hawthorne's phrase; the retelling
thesis in one word). Collision check run at execution start (2026-09-02): PyPI 404, npm 404,
OpenUPM zero results, no GitHub repository of the name (a dormant zero-repo GitHub *user*
`twicetold` exists — no conflict), web search surfaces only the K-pop group TWICE and the
dictionary term. Exact-match clean in the category. Rejected at the plan batch: `retold-npc`
(Retell AI voice-agent stem clash), `bartlett-npc` (surname, mechanism invisible), and —
pre-vetted out before the batch — Memloom (taken: a memory engine for AI agents) and Waystone
(doubles the borrowed-novel exposure the demo corpus already carries).

**Scope ruled (four forks, all taken at the plan batch):** (1) the env prefix renames
`LONGMEM_` → `TWICETOLD_` (29 distinct keys — pre-release is the only cheap moment for an
integrator-facing surface); (2) full DB/infra rename (product `twicetold`, scratch
`twicetold_test`, demo `twicetold_demo`, the `twicetold_suite_`/`twicetold_eval_` pid
prefixes, container `twicetold-pg`, volume `twicetold-pgdata`); (3) the local working folder
renames too; (4) the GitHub repo renames (auto-redirects; no tracked file embeds the URL).
**The C# namespace `NpcMemory` stays** (ruled constant; it never carried the old name).

**The do-not-touch allowlist** (also the final grep-gate baseline): the immutable applied
migration `001_foundation.sql:1` header comment (one line, permanent); the three append-only
register **bodies** (`decisions`/`session-log`/`floors` — their H1 title lines DID rename); all
`docs\research\*` dated bodies (incl. this file's Fork-3 analysis and the 46 `_findings\*`
boilerplate) + both `external-audit-*` + the retired `split-brain-streaming.md`; spec docs'
**dated** sections (`## Done when`, `[SETTLE-AT-BUILD]`, `> BUILT` banners) — the history half
of history-plus-contract; every third-party string (`LongMemEval` 57+, `LongMemory`, `langmem`,
`longmem.dev` — a blanket case-insensitive replace was FORBIDDEN, every edit per-file); the
frozen `data\eval\gold\*.json` run artifacts; the committed DLL's binary PDB path (clears at
the Phase-4 rebuild). README carries a deliberate one-line continuity note ("Renamed from
longmem-npc") that keeps the old name on purpose.

**The lockstep risk, recorded:** `app\scratch_db.py`'s `PRODUCT_DB` must equal the real
`.env` `POSTGRES_DB`/`DATABASE_URI` dbname, and there is no runtime cross-check — a half-done
rename silently disarms the product-DB refusal guard. `PRODUCT_DB` is now `"twicetold"`; until
the operator `.env`/Docker swap lands, the running dev product DB is still `longmem` (so the
name-guard temporarily protects a not-yet-existing name). This is safe in the interim because
NOTHING in the suite/walker/eval/demo paths targets the bare product DB by name (they target
the `twicetold_*` scratches), and `scratch_uri`'s resolved-name proof still blocks accidents.
The floor-verifier re-checks the pairing after the swap.

**Landed and self-verified this session (the in-repo half):** 243 mechanical replacements
across 55 files via a scoped byte-level sweep (allowlist simply excluded), ruff clean, **full
suite 193 passed**, **all 15 walkers pass** fresh + serial elder-first on `twicetold_test`
(verify_concurrency's one batch-run timing blip on B2 was a load artifact — clean at 11
assertions in isolation; verify_deferred_writes' "51/51 criteria passed" is the known
non-"ALL CHECKS PASSED" banner), **C# interop harness 53 checks green** (recompiled client,
renamed exception string covered), real-mode `load_settings` boots on the `TWICETOLD_` keys
with the coupled-role constraint intact. Grep gate: `git grep -i longmem` returns exactly the
allowlist.

**Operator swap LANDED + verified 2026-09-02** (Jack ran `.env` + GitHub; Claude drove the
non-spend infra): the `.env` key/value rename (Jack, two ordered byte replaces mirroring the
`.env.example` sweep); the GitHub repo rename + `git remote set-url` (Jack); the Docker volume
recreation (`docker compose down`/`up` — old `longmem-pgdata` orphaned intact, fresh
`twicetold-pgdata` initialized with the new user/DB); migrations fresh-applied to `twicetold`
(001–008) + a no-op idempotency re-run; the **`PRODUCT_DB`↔`.env` lockstep proven** —
`PRODUCT_DB == dbname == "twicetold"`, and `provision_scratch(base, "twicetold")` now raises
(the guard protects the real product DB); `.env` parses in real mode with both keys; the
178-subset green on the recreated container. **Still pending (commit-2, after the folder
rename):** the local folder rename + Claude project-state copy (Jack's, session's-last-act);
then, in the renamed folder, the `demo_loader --fresh` rebuild (real spend) + hero-PNG
re-capture (`docs\media\ledger-memory-chain.png`) + the DLL rebuild/copy to
`unity\Assets\Plugins\` (clears the old embedded path in one build) + the **independent
floor-verifier pass**. No floors row and no re-verification entry yet — the count stays 32
until that pass returns.

## Consumer-context scan rulings — the pre-release market pass — 2026-09-01

**Context.** Jack paused the Phase F queue for one research-only session (run 2026-08-31 →
09-01): a five-stream internet scan to find load-bearing changes needed before the public
push — OSS agent-memory reception, AI-NPC platform + game-dev/player sentiment, a novelty
stress test + name check, release-hygiene norms (license chain, no-auth norms, UPM,
erasure), and a cold consumer sub-agent (a role-played Unity indie engineer evaluating the
repo read-only, no project context). Full findings, evidence links, and the negative-search
record: `docs\research\consumer-context-scan-2026-08-31.md`. Nothing was built; four forks
were surfaced and ruled at one batch.

**The four rulings:**

1. **OpenAI-compatible provider path — BUILD BEFORE RELEASE** (the recommended
   defer-and-document option was declined). A base-URL provider path for the model and
   embedding roles lands as a new pre-F1 build target (~1–2 sessions: provider
   implementation + config + tests + floor re-verify), shipped WITH the documented
   small-model quality warning. The evidence carried both halves: the knob is table stakes
   in self-hosted AI infra (every surveyed comparator ships one; local-model support is
   their loudest issue category; game-side, Mantella and LLMUnity win on it), AND small
   local models break structured-output pipelines loudly (the comparators' own docs warn of
   it — our write-path typology/importance JSON and drift-budgeted reconstruction are the
   calls that break first). The ruling takes the knob plus the warning.
2. **Per-agent bulk erase — BUILD** (recommended, taken). `DELETE /v1/agents/{id}/memories`
   as a thin transactional extension of the C6 purge carve-out (endpoint + tests + walker
   extension + purge-floor re-verify; may ride the provider-path session). Category
   evidence: Mem0/Zep/Letta all ship identity-scoped bulk erase and comparison sites grade
   the axis. The player-vs-agent attribution nuance (memories attach to NPC agents, not
   players, so even the per-agent verb is not a GDPR button — the integrator owns the
   player→memory mapping) goes into the F1 docs regardless.
3. **The name — RENAME BEFORE THE F3 FLIP** (the recommended keep-and-disambiguate option
   was declined). The facts that drove it: PyPI `longmem` is taken; longmem.dev is a live
   same-category product literally named "LongMem"; Microsoft's LongMem (NeurIPS 2023) owns
   the term academically; search results for the prefix are dominated by others —
   "longmem-npc" exact-match is clean, but the neighborhood is not. The rename gets its own
   short naming session (candidate + collision check + repo rename with GitHub redirects +
   docs sweep) BEFORE F1, so the README is written once under the final name. Nothing is
   packaged or published yet, so this is the last cheap moment.
4. **The Ledger host guard — BUILD IN F3** (recommended, taken). FastAPI's stock
   `TrustedHostMiddleware` with a localhost allowlist + tests + one honesty-section caveat
   line, slotted into the F3 hygiene sweep. Precedent: CVE-2025-49596 (MCP Inspector, June
   2025 — DNS rebinding against localhost-only tools; the fix was Host validation).

**Queue consequence** (status.md updated): two NEW pre-F1 roadmap items — the naming
session, then the provider-path + per-agent-purge build — and F3 gains the host guard. F1
inherits the scan's README input pack (report Part 3: the deployment-reality section — the
cold consumer's one BLOCKED step; the integrator quickstart; the providers section; the
prior-art citations incl. MRAgent/MemHarness/Zep-Graphiti; ONE dated cost table; the
evidence-backed no-auth paragraph + Steam live-AI disclosure note; the NOTICE f-coref
line). F2 inherits the compose + UPM conformance lists (report Part 2). The
presentation-redesign session inherits the showcase post-mortem pack (report Part 4).

**Scan verdicts worth the register** (detail and links in the report): the novelty claim
SURVIVES — nothing found, in games or out, combining identity-conditioned retelling +
persisted compounding write-back + an immutable bi-temporal record + gist/drift
constraints (~20 negative searches preserved as evidence) — but the "reconstructed, not
replayed" slogan was independently claimed twice in mid-2026 (MRAgent, ICML 2026;
MemHarness) and the bi-temporal substrate is established prior art (Zep/Graphiti; Engram
already cited), so the README cites-and-differentiates and never leads with the bare
slogan. The license chain is CLEAN for the Apache-2.0 flip — full verification including
en_core_web_lg (MIT; CC0 vectors) and the runtime-downloaded biu-nlp/f-coref weights (MIT);
the one gap is a missing NOTICE line for that runtime download (queued into F1). The cold
consumer's verdict: adopt-for-a-spike, prototype-only, exit pre-written at the missing
shipped-game deployment story; its near-walk moment was the README-vs-status ~10x cost
discrepancy — F1's priority signal.
