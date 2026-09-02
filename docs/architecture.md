# twicetold-npc — Architecture

This file is the current design truth. Edit it when a design decision changes. The *why* behind each
decision lives in `decisions.md` (append-only). Current state, build order, and task queues live in
`status.md`. The first build target is specced in `migration-01.md`. Test discipline is in
`test-suite.md`.

## 1. What this is

A generalizable long-term-memory service for game NPCs that others integrate into their own games or
applications: a self-hostable backend (FastAPI + PostgreSQL/pgvector) plus a Unity-embeddable client
package. We never host the backend; integrators run it themselves.

The system gives characters psychologically plausible memory: a bi-temporal, non-destructive record
underneath, with identity-conditioned reconstructive recall, believable decay, and dissonance-driven
defense above it.

**Thesis:** behavior → confabulated reason → stored → defended. *A psychology, not a database.* The
claim axis is **controlled infidelity above an immutable record** — the character's telling of a
memory can drift and be defended, while the ground-truth record underneath never lies.

## 2. Non-negotiable principles

- **Bi-temporal, non-destructive.** Every memory row carries `created_at` (when we wrote it),
  `valid_at` (when it happened in world time — wired to the client-sent timestamp, timezone-aware),
  and `invalid_at` (when it was superseded, if ever). Superseded rows survive and stay queryable.
  Reflections carry the same columns.
- **Recency decay and correction-override are structurally distinct mechanisms.** Decay is a
  read-time computation; correction is a bi-temporal invalidation. Never conflate them; the test
  suite proves the separation.
- **Importance vs relevance are independent axes.** Importance is scored once at write time (stored
  raw, normalized at read), anchored to a per-NPC, integrator-configured diagnosticity goal.
  Relevance is computed per-query at read time.
- **Write-time facts vs runtime state.** Facts about the event (typology, confidence, context
  components, decay class, provenance, gist/detail spans, importance) are populated from day one.
  Runtime state (reflection pressure, drift headroom) ships with its
  mechanism and needs no backfill. Rationale on record: importance is a write-time fact about the
  event; reconstruction drifts the *telling*, not the event's centrality, so defending by day-0
  importance is arguably correct. If dynamic salience ever enters, it enters as a separate runtime
  term.
- **Schema now, mechanism later.** Schema, caches, and pin behavior are live from day one even where
  the consuming mechanism lands later. Sequencing of the mechanisms themselves lives in
  `status.md`'s queues — and sequencing orders work, it never vetoes a design option (reframed
  2026-07-17; the 2026-07-14 reconstruction re-slating is the pull-forward template).
- **Integrator-defined vocabulary everywhere.** Observation phase tags, diagnosticity goal,
  context-match weights, scene-type vocabulary, model roles, rigidity, prose-view weights,
  decay knobs, drift threshold, habituation cap/decay *(habituation cut 2026-08-04 —
  annotated at the C2 dossier, 2026-08-15)* — none is ever hardcoded.
  Violating this anywhere makes the config surface incoherent. *(The action vocabulary and
  reputation sensitivity left the surface with the A1 re-shape, 2026-08-04.)*
- **Instrument at the seam, not after.** Timing and token accounting are added to each layer as that
  layer is built.
- **Storage before cognition** build ordering.
- **Degradation behavior is named and tested per model call.** Importance-scoring failure → store
  the memory with neutral importance plus a `scoring_failed` flag; embedding failure → the write
  lands with a NULL embedding (`embedding IS NULL` is the queryable signal; ruled 2026-07-13 —
  *since the 2026-07-18 freeze ruling the signal lives on the live fact head,
  `memory_fact_versions.embedding IS NULL`; the authorial-correction verb is the deliberate
  contrast: all-or-nothing fail-loud on embed failure, and correcting an embed-degraded memory
  re-embeds it — `fact-level-correction.md`*);
  never lose a write because a model was flaky. *(The one build-phase exception — a gist-escalation
  call that fails twice hard-stopping the write — was **re-ruled 2026-07-22 to soft-degrade**: the
  write lands with the base NLP-pass gist and `escalation_failed = true` (migration 005). No such
  exception now stands.)* The retrieval gate degrades per its ladder (section 6), fail-quiet.
  Malformed-model-response cases live in the test suite.

## 3. Environment & stack

**Environment.** Windows 11 (25H2). Always PowerShell syntax and backslash paths — never bash.
Paths in these docs are written relative to the repo root (`docs\`, `app\`, `unity\`) — no absolute
developer path is recorded anywhere, so a clone works from any location. Unity 6, flatscreen 3D
(CharacterController + mouse-look, raycast-plus-key interactables); Unity's external script editor
is VS Code. Global Python 3.14.3 on PATH. Secrets live in `.env` at repo root, never in docs.
C# root namespace `NpcMemory`; Unity scripts under `Assets\Scripts\` until the package layout
(`com.jacksonzane.npc-memory`) is settled; Unity Package Manager packaging lands at Phase F2,
BEFORE the demo video *(the 2026-08-24 re-sequencing moved the whole demo endgame after Phase F;
this line originally read "after the demo video" — corrected at F0, 2026-08-26)*.

**Backend.** FastAPI; psycopg v3 with `AsyncConnectionPool`; hand-written SQL (no ORM);
PostgreSQL 16 + pgvector in Docker (the `pgvector/pgvector` image); UUID primary keys minted
server-side; HNSW vector index (a cheaply reversible choice).

**Models.** Haiku-class for importance scoring, description rendering, typology classification,
gist escalation, reflection, reconstruction *(re-confirmed 2026-07-28 — this
line still said Sonnet-class for reconstruction until 2026-07-29, a propagation miss; §7 carries
the resolution note)*, and — **ruled 2026-07-29 off the B1 A/B** — streaming dialogue prose
(sonnet-5 held the dialogue role from the 2026-07-15 slice until then; it and the thinking-off
variants are re-assessed once the judged-eval harness can score prose. **Re-assessed
2026-08-12 on the first real compares: HAIKU CONFIRMED — latency rules.** Sonnet-5's prose is
judge-preferred 46–7, and 41–9 with thinking off, but perceived first word is the decisive
axis: 943 ms p50 for haiku vs 2626 / 2086 ms — both sonnet variants sit far over the 1 s bar.
The dated entry in `decisions.md` carries the numbers and caveats). Every model role is an
integrator knob with its own env var — nothing is hardcoded. **Six vars exist today** and real
mode requires all six: `TWICETOLD_MODEL_` + `IMPORTANCE`, `RENDER`, `TYPOLOGY`, `ESCALATION`,
`DIALOGUE`, `RECONSTRUCTION`. *(The `BEHAVIOR` role — seven vars, 2026-07-21 to 2026-08-04 —
left with the A1 re-shape.)* A seventh var, `TWICETOLD_MODEL_JUDGE` (Opus-4.8-class by the
2026-08-07 B2 ruling), is **eval-runner-only**: loaded in both modes, required by neither —
the server never carries a judge; the eval runner validates it itself on judged runs
(eval-harness.md stage 3).

One honest limit on "each upgrades independently" *(corrected 2026-07-28 — the sentence
previously over-claimed)*: v1 serves importance + render + typology from **one** write call, so
those three vars must name the same model (`load_settings` raises rather than silently picking one
— a documented v1 limitation, not a design position). Reflection's var arrives
with reflection *(shape ruled 2026-08-15 at the C2 dossier: `TWICETOLD_MODEL_REFLECTION`,
judge-shaped — loaded both modes, required by neither, loud at the first real reflect call;
`reflection.md` fork 6)*. The compiler's var landed with C3 *(2026-08-17:
`TWICETOLD_MODEL_COMPILER`, the THIRD judge-shaped var — the same contract, loud at the
worker's first real compile; C3 has no endpoint, so that call is always the worker's —
`parameter-compiler.md`)*. The retrieval gate is **non-LLM** — there is no gate model and no gate env var.

**Embeddings.** OpenAI `text-embedding-3-small` at 1536 dimensions; the column dimension is locked.
The same model embeds location names/descriptions and gate-time utterances.

**Write-time NLP (no LLM).** Ruled 2026-07-13: spaCy `en_core_web_lg` + `fastcoref` for
intra-observation coreference (never `neuralcoref` — abandonware); affect via VADER (compound →
valence) + the bundled Warriner 2013 VAD lexicon (arousal, normalized 1–9 → 0–1; dominance lives in
`affect_detail` jsonb). NRC-VAD was rejected at the license gate — research-only, incompatible with
the planned Apache-2.0 flip; Warriner is CC-BY 4.0 (`data\lexicons\` with attribution).

## 4. Data model

### 4.1 Gist and detail

Gist is a **span pointer into the immutable on-disk observation text** — not a rewritten summary.
At write time, the NLP pass matches tokens/entities/noun-chunks against the NPC's **identity
components table** (entries: canonical name + aliases + category, e.g. friend names, job title; a
category hit counts even without a named entity). Hits become gist spans; everything else is detail.

An LLM escalation pass exists for hard cases, **biased loose** (over-call — a wasted call is cheap,
a lost gist breaks the product). Six triggers, any one fires (five ruled 2026-07-13, the sixth
2026-07-23; all integrator-tunable via `agents.config`, defaults in `app\config.py`): (1) importance
above threshold; (2) an identity/category hit co-occurring with |valence| above threshold; (3) a
**novel entity** — which is also how the identity components table grows; (4) an unresolved
pronoun/noun-chunk co-occurring with an identity/category hit; (5) low NLP confidence on an
already-flagged span (confidence only ever *adds* calls, never suppresses one); (6) **thin gist** —
the base NLP pass yielded fewer spans than the `escalation_min_base_spans` floor (default 1: fire on
zero), protecting the gist floor directly — measured 2026-07-23, 16/80 realistic observes otherwise
landed with zero gist spans, leaving reconstruction's fixed constraint empty (0.0 disables).
Cross-observation coreference misses are accepted as graceful failure (the detail just decays).

### 4.2 Decay

`tau_effective = tau_base × (1 + k × importance)`; `decay = 1 − exp(−age / tau_effective)`.

Decay applies to **non-gist detail only**, which decays to fully hidden; **gist never decays**.
Decay is computed at read time; the original observation stays intact on disk forever — decay only
controls how much detail the reconstructor is shown, and any past state is re-derivable (debugging,
eval harness). Each memory carries a **decay class** (the differential-lambda class): an
integrator-vocabulary label selecting which base time-constant applies, used by both detail decay
and the recency term in retrieval scoring.

**Consequence to remember:** the identity components table is the *only* control on long-term
durable content. Its reflection-time trim (with silent cache invalidation — chosen deliberately) is
the sole mechanism that removes a durable fact.

### 4.3 Two identity structures — never conflate

1. **Identity components table** — an entity/topic index (canonical + aliases + category). Used for
   gist matching and as the entity-gate tripwire; grown by the LLM on novel entities; pruned at
   reflection time, silently invalidating reconstruction caches.
2. **Rendered identity document** — seed prose plus current identity-relevant reflections, rendered
   into the exact prompt block. `identity_version` = a content hash of the rendered document.
   Recompiled at scene edges *(plumbing ruled 2026-07-17: the scene-boundary handler recompiles
   server-side and returns `identity_version`; the caller freezes it as scene state and passes it
   per read request — the caller-frozen-scene-state contract)*.

### 4.4 The fact-version chain *(specced & **built** 2026-07-18 — `fact-level-correction.md`; migration 002 live; the build ruled **freeze**: observe writes the vector only to the fact head)*

The memories row's **semantic basis** — the text retrieval ranks by, and its embedding — gains
the same bi-temporal machinery the telling has: a child chain under the stable `memory_id`
(supersede by `invalid_at`, one live head, `write_cause` discrimination), created by migration
002 with an `original` row backfilled per existing memory. The authorial-correction verb is
**fact-following** (one combined verb, ruled 2026-07-18): the operator's corrected text becomes
both the telling head and the embedded fact basis in one transaction, so retrieval follows the
fix. Only the embedding follows the correction (ruled 2026-07-18); importance, typology, decay
class, entities, and affect stand as write-time facts about the *event*. *(Amended by the
2026-07-19 gate-spec rulings, `mid-dialogue-gate.md`, **built the same day**: **entities now
also follows** — migration 003 gives it a fact-chain home, and the correction verb re-derives
it via mechanical NER merged with an optional operator field, mirroring observe. Importance,
typology, decay class, and affect still stand as write-time facts.)* Accepted asymmetry: a
corrected memory's embedding basis is the operator's corrected text rather than
observation-class text — the same ground-truth rule as constraint-follows-anchor.

## 5. Write path

Client event → NLP span/affect pass → **single Haiku call** (prose render + importance scoring;
typology classification only when the client didn't declare it) → **atomic insert**, populating all
write-time facts from day one.

*(Amended by the C1 deferred-write build, ruled & built 2026-08-12 — `deferred-writes.md`,
migration 006: with the `deferred_writes_enabled` knob on — **default OFF** — the two LLM calls
move to an in-process worker. The NLP pass, embedding, and atomic insert stay synchronous; the
raw text lands as the live `original` head with the write-call scalars NULL and
`enrichment_pending` set; the worker's one-shot completion fills the scalars and supersedes the
head with the render, `write_cause = 'enrichment'`, which also **joins the drift-anchor set**.
"Populating all write-time facts from day one" gains its one ruled exception: a deferred row's
write-time window is stretched to the worker's completion, and the terminal-failure fill is
byte-equivalent to the sync scoring-failed end-state — deferral never adds a lost-write rung.)*

- **Evidence typology** — `observed | told | inferred | reflected`, with a 0–1 confidence. A default
  per-typology confidence table exists; the client may override per event; **client declaration
  wins**. `typology_source` records `declared | inferred` (distinct from provenance).
- **Provenance** — `lived | injected` (injected = operator-seeded backstory).
- **Context stamps** — location, entities, time, affect. All four are optional API fields with
  stated per-field degradation when absent. Stored as typed columns per component (per-component
  read weights require it); location is embedded via the same 1536 model. **Entities are captured
  at write from day one:** the entities column + GIN index serve the gate now and the planned
  encoding-context read boost later *(the read boost **landed 2026-07-20** — §6)*. *(Gate spec 2026-07-19, freeze ruling — the 002 embedding
  precedent applied: migration 003 gives entities a fact-chain home; observe writes the fact
  head only, `memories.entities` frozen, the GIN moves to live fact heads. **Built the same
  day — migration 003 live**; `mid-dialogue-gate.md`.)*

## 6. Read path

**Dialogue initialization:** top-k retrieval. Endpoints that run retrieval return **memory IDs and
scores alongside prose** — this is load-bearing; it is what makes the test suite assertable.
*(Carve-out, ruled 2026-07-27; third member 2026-07-29; **fourth member ruled 2026-08-17**: the
two **inspector reads** below, the judge-free metric read, and the **agent-state read** run no
retrieval and are unscored by contract — IDs and structured fields on every row, no scores,
because none were computed.)*

**Inspector reads** (unity-client.md fork 3, **built & floor-verified 2026-07-27**) — the record
made legible, and the Ledger's data source: `GET /v1/memories/{id}/chain` returns the immutable
observation beside BOTH version chains with superseded rows **present** (greyed client-side, never
dropped) plus gist spans and a `has_embedding` flag that never exposes the vector;
`GET /v1/agents/{id}/memories` is the per-agent index, newest `valid_at` first, each memory beside
its live telling head, `limit` a caller argument (the `k` precedent) and never a config knob.
SELECT-only end to end; 404 on unknown memory/agent.

**The judge-free metric read** (`eval-harness.md` stage 1, **built 2026-07-29**):
`GET /v1/memories/{id}/reconstruction-metrics` computes gist-precision / detail-recall /
fabrication / keyword-retention against the **live telling head** — The Ledger's on-screen
numbers and the eval harness's judge-free layer, one implementation (`app\eval_metrics.py`).
Anchor-cause-aware (a correction-anchored chain scores against the corrected head and owes no
detail), honest denominators (`None`, never a flattering 1.0), bands parsed from the
reconstruction cache's composed keys. Runs no retrieval (no scores exist — the invariant does
not bind; the two inspector reads' unscored contract is untouched) and performs **zero writes**:
the identity document is the pure render, never the `ensure_` upsert. The presence rule is the
`metric_gist_match_threshold` knob (default 1.0 — strict lexical; paraphrase slack belongs to
the judged categories).

**The agent-state read** (C5, **built & ruled 2026-08-17** — the carve-out's fourth member):
`GET /v1/agents/{id}/state` is the composed runtime snapshot three earlier builds recorded this
route as the consumer for — the reflection-pressure gauge's standing surface (`reflection.md`),
the `compiled_bundles.passthrough` integrator read (`parameter-compiler.md`), and both workers'
run logs (the enrichment-runs-on-`/chain` precedent: a background seam's accounting surfaces on
an unscored read). Payload: the stored agent row **as stored** (`config` verbatim —
SERVICE_DEFAULTS never merged; a resolved snapshot would rot), the current `identity_version`
(the newest document row, SELECT-only — never the `ensure_` upsert), the pressure gauge
(computed on demand, never stored — §2's runtime-state rule; the reflect verb's loud
non-positive-norm guard verbatim), the live beliefs in the ruled compiler-window order (the
first `compiler_window_k` rows ARE the compile window, by construction), the newest live bundle
per (belief, scene_type) with liveness DERIVED from the source reflection (§10), and the two
run logs newest-first capped by `runs_limit` (a caller argument, the `k` precedent). Zero
writes; 404 on unknown agent. The dormant reputation columns stay absent — the A1 removal
stays removed.

**Retrieval scoring** (built & floor-verified 2026-07-14, `read-path.md`; shapes ruled in the
dated `decisions.md` entry): `relevance × recency(decay class) × importance_norm`; pin exemption;
normalization; reserved slots for a future encoding-context term and per-call overrides under the
split-brain topology. importance_norm is clamp + floor (ruled over min-max so invalidation can
never move other items' scores); the decay math lives once, in `app\decay.py`, shared later by
the reconstruction theta check. *(Fact-level correction **built** 2026-07-18,
`fact-level-correction.md`: the relevance probe reads the **live fact-version head's**
embedding — scoring inputs otherwise unchanged; scores move only through relevance.)*
*(**Encoding-context term built 2026-07-20** — ruled with the research-adoption slate
(client-supplied fields; RaMem, arXiv 2606.22844): the request's `location_name`/`entities`/
`event_time` now multiply a soft context factor into the score — entity coverage over the live
fact head's entities + an event-time proximity kernel + casefold location match, each weighted by
its own integrator knob. A no-context request skips the factor — v1-byte-identical scoring; never
a filter, never a penalty; applies on loader, gated, and degraded paths. `weight_overrides`
lived on the BEHAVIOR view from 2026-07-21; **since the A1 re-shape (2026-08-04) it re-ranks the
served view feeding the PROSE prompt at the dialogue seam** (§9 — weights-on-speech). Retrieval
scoring itself stays byte-identical: the re-rank is post-cut, membership never changes, and the
init request carries no weights field (removed 2026-08-04; it had been reserved-inert since
2026-07-14). Affect stays deliberately absent. `read-path.md` carries the annotated contract.)*

*(**Hybrid lexical channel built 2026-07-20** — Target B of the same slate, **migration 004**:
a token-OR full-text candidate fetch off a partial GIN over live fact heads
(`to_tsvector('simple', basis_text)`), unioned into the vector over-fetch before scoring —
dedup by memory_id, the scoring formula untouched, lexical hits carrying their true cosine
relevance (NULL-embedding heads reachable with relevance null — exact-token recall softens the
embed-degradation consequence). `lexical_fetch_k` knob, 0 = kill-switch; `text_search_config`
string knob, `'simple'` default baked into the index expression, overrides run unindexed.
Loader-scope v1 — the gate's fire probe and the ladder's entity-only rung are noted future
consumers. This is the seeding base any future graph/PPR term builds on (SPRIG, GAAMA — the
sequenced graph-memory queue item).)*

**Mid-dialogue gate (non-LLM hybrid)** *(specced & **built** 2026-07-19,
`mid-dialogue-gate.md` — five scope forks ruled; the loaded set is caller-held scene state per
the ruled contract; migration 003 live)*:
- **Novelty check** — embed the utterance; measure distance against the loaded set; far from all →
  fetch.
- **Entity tripwire** — an uncovered mention of an identity-components entry → fetch. (Most
  demo-legible signal.)
- A fruitless-retrieval damper limits accumulation. Every gate event logs **which signal fired** —
  this feeds the reserved novelty kill-switch decision (see `decisions.md`).

**Degradation ladder:** embeddings down → entity-only, fetching lexically off the GIN index ranked
by recency × importance; no entities supplied → novelty-only; both out → gate closed, serve the
loaded set, **fail-quiet**. *(2026-07-19 freeze ruling: migration 003 moves the entities GIN to
the live fact heads — the lexical fetch reads fact-head entities; `mid-dialogue-gate.md`.)*

**Prompt caching:** within a scene, gate-fetched memories are **appended after the cached head** as
a marked recollection block; the head is **rebuilt at scene boundaries**, where the cache is cold
anyway. The **scene boundary is a load-bearing, explicit client-sent API event** with two
consumers: prompt-head rebuild and identity-document recompile. Scene edges settle
prefix and identity version in one heartbeat. *(Identity recompile **landed 2026-07-17**: the
boundary handler recompiles server-side and returns `identity_version`, which the caller freezes
as scene state (`reconstruction.md`); prompt-head rebuild / prompt caching lands with the C7
latency work. A third consumer — the reputation snapshot, landed 2026-07-15 — left with the A1
re-shape, 2026-08-04.)*

**Read-mode boundary (self-describing, not just documented):** every returned memory carries
`read_mode` (`verbatim | reconstructed`) and `pinned`, in payloads and the debug view. Three states:
pinned → verbatim always; unpinned fresher than the reconstruction threshold → verbatim for now;
unpinned past the threshold → reconstructed. A fourth enum value, `reconstruction_pending`, exists
only if an async fallback is ever adopted. **Docs purity claim:** no raw access through the
character read path, except integrator-designated pins; ground truth lives in the debug view.

## 7. Reconstruction (pre-demo scope, ruled 2026-07-14; **built & floor-verified 2026-07-17**, `reconstruction.md`)

Identity-conditioned reconstruction is the **mandatory read path** for unpinned memories past a
threshold theta, where **theta reuses the decay math** (reconstruct when decayed detail strength
falls below theta; text-affecting decay evaluations bind to a scene-frozen basis so read-mode
never flips mid-scene). The reconstructor sees the **full gist span as a fixed constraint** plus
the time-thinned detail slice **plus the current live head — "how you currently tell it" (ruled
2026-07-17: retellings compound; without the prior telling the drift budget rarely binds)** —
conditioned on the rendered identity document. *(On a chain whose drift anchor is a
correction head — `authorial_correction`, ruled 2026-07-17, **built & floor-verified
2026-07-18**, `authorial-correction.md`; extended to `update_with_resentment` by C4 ruling 4,
**built 2026-08-17**, `dissonance.md` — the fixed constraint follows the anchor: that head
replaces the stale gist constraint, and original observation detail is never re-injected.)*

**Write-back with a version chain:** one permanent `memory_id` forever; each retelling inserts a new
detail row and stamps the prior one superseded — **versioned confabulation over an immutable
record**. Chain rows carry a `write_cause` enum:
`original | reconstruction | rationalization | update_with_resentment | authorial_correction |
enrichment` *(the sixth value joined with migration 006, C1 2026-08-12; this line had omitted
it — fixed at the C4 doc pass, ruling 8, 2026-08-17)*.

**Serving:** Haiku-class *(**re-confirmed 2026-07-28.** The doc audit surfaced that the shipped
config had been running `claude-sonnet-5` since 2026-07-21 — a stopgap when the env var was found
missing from `.env`, never a class ruling, and it silently contradicted the register for a week.
Haiku stands; `.env.example` corrected. **Consequence: the real-mode reconstruction numbers taken
in that window — the 16.3 s cold figure and the cost table's reconstruction rows — were measured
against sonnet-5 and must be re-measured before they are quoted again.** *Resolved 2026-07-29:
re-measured on Haiku — 8.1 s headline cold batch, 3.3–8.6 s across the cold snaps, ~4× cheaper,
drift strictly better — and the quote embargo is lifted by ruling; the session log carries the
quotable numbers.*)*; **one structured call
batching all k cache misses per retrieval**;
pre-warm at dialogue init; on a mid-scene miss, **block and expose a "reconstructing" signal**
(latency becomes characterization). Async serve-verbatim-then-cache is **not** the design — if
latency ever forces async, the swap must be explicit state (a `reconstruction_pending` read mode),
never silent text mutation, because of the **within-scene text-stability invariant**: absent a
diegetic event, **an authorial correction** (the second sanctioned text-change cause, ruled
2026-07-17), **a deferred-enrichment completion** (the third, ruled 2026-08-12 —
`deferred-writes.md`; the window is bounded by the worker's poll interval), **or a
reflection-trim cache eviction** (the fourth, ruled 2026-08-15 and built with C2 —
`reflection.md`: a mechanically pruned component evicts the affected memories' caches
per-affected only; reflect at scene edges and the window vanishes) on that memory,
repeated reads within one scene return byte-identical text.

**Cache:** keyed `(memory_id × identity_version)`, where the version component **composes
`identity_version` with a quantized, scene-frozen decay band** (ruled 2026-07-17; the band both
keys the cache and sets the thinning level, so same key ⇒ byte-identical text, and deeper decay
re-reconstructs on thinner detail — the pre-demo drift driver while the identity document is
seed-only static). **Cache-eviction invariant (generalized):** cache
writes happen only in the reconstruction path; **any other writer to a chain — correction, diegetic
write, deferred-enrichment completion (2026-08-12, on every completion shape including
facts-only), purge — must evict all cache rows for that memory_id.**

**Drift budget:** on each reconstruction-driven write-back, embed the candidate and measure distance
from the anchor; past threshold, **refuse the write and keep the prior head**. Event-driven writes
(both diegetic paths) are exempt from the budget. **Scope of the guard (R7 resolved 2026-08-12,
measured by the stage-4 ablation):** the budget is a **topic guard** — it catches wholesale
nonsense and topic-swaps (embedding-neighborhood departure), and is **blind by construction to
fact-level drift**: retellings generated without the gist constraint drifted no further (0
over-budget in both arms, mean paired |Δ| 0.056) while gist-precision dropped 0.834 → 0.704.
Factual faithfulness is policed by the other two guards — the **fixed gist constraint +
gist-precision** (fact survival, the judge-free metric read) and the **judged faithfulness
category** (semantic support, past the agreement bar). Mechanism and threshold unchanged.
**The anchor needs no pointer:** it is the latest
chain row whose `write_cause` is `original`, `authorial_correction`, `update_with_resentment`,
or `enrichment` *(the fourth member since migration 006 — the worker's canonical render
re-anchors, `deferred-writes.md`; this line had omitted it — fixed at the C4 doc pass,
ruling 8, 2026-08-17)*.
Re-anchoring by cause: authorial → the corrected head (the authorial-correction row);
update-with-resentment → the new head;
rationalization → **never** (it spends headroom without being blocked, so a heavily defended memory
crystallizes — "the story has set"). On-camera demo artifact: one memory drifting across 60 days.

## 8. Dissonance and correction verbs

**Dissonance threshold** = importance × evidence typology × per-NPC **rigidity** scalar
(0.5 pushover → 2.0 zealot). "I saw it" resists harder than "I heard it," on both sides of a clash.
Either way **the store records the truth**; the fork only shapes the character's reaction.
Habituation guards for the future context term: **both a cap and a decay**, as integrator knobs.
*(Habituation was cut from scope 2026-08-04 — these guards are not arriving; annotated at the C2
dossier, 2026-08-15.)*

**Two correction verbs, semantically distinct:**
- **Authorial** (operator fixes wrong data): **replace model (ruled 2026-07-12)** — supersedes the
  drifted chain with a corrected head row, `write_cause = authorial_correction`. The memory stays
  retrievable under the same memory_id, now serving corrected content, and the corrected head
  becomes the drift anchor. Prior rows are invalidated by ordinary supersession; the verbs are
  discriminated by the new head's `write_cause`, not by any marker on prior rows. Takes effect
  immediately, mid-scene included, and the corrected head becomes the reconstructor's fixed
  constraint for that chain (both ruled 2026-07-17). *(Specced 2026-07-17, **built &
  floor-verified 2026-07-18**, `authorial-correction.md` — chain content only; fact-level
  correction **specced & built 2026-07-18**, `fact-level-correction.md`: the verb is now
  fact-following — the corrected text is also the embedded fact basis (migration 002), so
  retrieval follows the fix.)*
- **Diegetic** (in-world confrontation; an API event referencing a target `memory_id`): preserves
  the chain and routes through the dissonance path; the new head row is typed `rationalization` or
  `update_with_resentment`, and a correction record is present. *(Specced & **built 2026-08-17**,
  `dissonance.md` — the eight C4 rulings: the defend-vs-update fork is the §8 formula computed
  mechanically (no model call decides; every multiplier a knob); the RECONSTRUCTION role writes
  the new telling in the decided stance (no new env var); tellings-only — the fact chain never
  moves, so retrieval keeps matching the original account; `POST /v1/events/diegetic-correction`,
  no migration — the `corrections` table waited since 001.)*

**Pin semantics (final ruling — supersedes any earlier note saying pin blocks diegetic):** both
correction verbs **outrank pin**, and the resulting new head **inherits the pin**. Pin means exactly
two things: exemption from decay, and exclusion from the reconstruction process. "No reconstructed
chains" does not mean "no chains" — event-driven corrections proceed at the normal dissonance
frequency. Pin/unpin are endpoints; pinning **freezes the current head** (restoration is a
correction verb, not pin); unpinning resumes the chain from the frozen head.

## 9. Dialogue output & turn topology

**Built slice (was "August ship"):** a single Sonnet-class call emitting prose + structured
output *(built & floor-verified 2026-07-15, `cli-harness.md`; shapes ruled in the dated
`decisions.md` entry — one `run_dialogue_turn` seam in `app\dialogue.py`, REPL + load driver
on a shared session-runner core)*. *(Superseded as the SHIP topology by the 2026-07-21
split-brain pull-forward, which was itself re-shaped 2026-08-04 — below. The intermediate
split-brain topology — two concurrent calls, action directive, reputation delta, divergence
record — is retired; `split-brain-streaming.md` carries its retirement banner.)*

**The shipped topology: one streaming prose call + weights-on-speech** *(the A1 re-shape, ruled
in the 2026-08-04 "Scope consolidation + road-to-completion rulings" entry, built 2026-08-04.
It deliberately inverts the 2026-07-21 speak-honest/act-weighted design: the behavior/action
side — the concurrent behavior call and its model role, the action directive, the divergence
record, and the reputation system whole — is removed by ruling. Deciding actions belongs to the
game developer; the NPC's own actions arrive as ordinary observes — the game-authored
action-observe contract, ruled 2026-07-21, standing.)*

The seam (`app\dialogue.py`, an async generator — the 2026-07-21 shape, kept): retrieval runs
ONCE → the served top-k is **re-ranked with resolved per-call weights** → the re-ranked view
feeds the prose prompt (`[identity] [memories] [output]`) → the dialogue-role call **streams
pure prose**, chunks yielding through the seam. **Over HTTP since 2026-07-23 / 2026-07-27:**
`POST /v1/dialogue/turn` drains this generator to the terminal result, and the SSE twin
`POST /v1/dialogue/turn/stream` iterates the same generator — the no-rewrite payoff of the
generator seam. `first_word_ms` is prose TTFT at the seam; `perceived_first_word_ms` rides
beside it, clocked from turn start, so it SEES the cold-reconstruction stall the former is
blind to — the honest metric the <1 s bar is measured against. **A dialogue turn persists
nothing** — the sanctioned in-place `agents.reputation` UPDATE left with the re-shape (the
column stays in the schema, unwritten and unread; applied migrations are immutable).

**Weights-on-speech (the surviving hidden-weights idea):** per-call `weight_overrides`
`{relevance, recency, importance}` resolve request field → `agents.config`
(`weight_relevance` / `weight_recency` / `weight_importance`) → 1.0, clamped [0.0, 4.0]
(module constants, not knobs), and re-rank the served set exponent-form on the product score —
`weighted_score = item.score · rel^(w_rel−1) · rec^(w_rec−1) · imp^(w_imp−1)`, zero-base
components skipped, ties on `memory_id`. The NPC's words are shaped by weights it is unaware
of. Contracts: **membership never changes** (the re-rank is post-cut over the served top-k,
ruled at spec 2026-08-04 — weights cannot pull in a memory retrieval excluded); retrieval
scoring stays **byte-identical** (the re-rank lives at the dialogue seam; `app\retrieval.py`
untouched); at all-1.0 weights the re-rank is the identity (the parity contract: on a loader
turn `dialogue_view` equals the (id, score) projection of `items`). On gated turns the
prompt's `[memories]` block still renders the loaded set in the caller's append-only order
(the §6 byte-stable-prefix ruling) — the weighted order is fully visible on loader turns and
among gate-fetched items on gated turns; `dialogue_view` reports the weighted ranking in all
cases. The turn result carries `items` (the raw retrieval echo — the IDs+scores invariant)
beside `dialogue_view` (the weight-ranked view the prompt was built from).

## 10. Reflection & parameter bundles (design ruled 2026-08-15 — `reflection.md`; reflection BUILT the same date, the C3 compiler BUILT 2026-08-17 — `parameter-compiler.md`)

Reflection is an **endpoint** (the verb) — `POST /v1/agents/{agent_id}/reflect`,
integrator-pulled — plus, ruled 2026-08-15 (the C2 dossier, fork 1), an **optional sibling
`ReflectionWorker`** on the C1 lifecycle contract, **default OFF**, pulling the same internal
seam when **reflection pressure** (a computed, never-stored gauge — §2's runtime-state rule)
crosses a per-agent knob threshold. The store exposes the gauge; the integrator — or the
opted-in worker — pulls the trigger. Sampling: episodes weighted by **importance × recency**
(the existing diagnosticity axis), not recent-N; the sampled text is the live telling head.

Reflection writes formed beliefs to the **`reflections` table** — the sole durable home
(fork 2; citations in `source_memory_ids`) — never into retrieval. The **seed stays
immutable**: identity-relevant reflections join the rendered identity document via a
model-free concatenative render, and the periodic evidence-conditioned refresh is an LLM
**consolidation reflection** that bi-temporally absorbs the rows it summarizes (fork 3;
`identity_documents` gains rows, never mutations; since the C2 build the dialogue prompt rides
the rendered document — the raw-seed asymmetry closed). `identity_version` bumps via content
hash exactly as always. Reflection also **prunes the identity components table** by the purely
mechanical 3-clause rule (the C2 spec ruling) — since the build the gist constraint follows
component liveness and reflection-driven eviction IS the **fourth sanctioned mid-scene
text-change cause** (fork 4; §7's writer list). A non-LLM RRR repetition guard gates the
identity consolidation (fork 5). All of it landed 2026-08-15 (`app\reflection.py`; migration
007 `reflection_runs`; the worker default OFF per agent).

**Parameter compiler (BUILT 2026-08-17 — `parameter-compiler.md`; the seven C3 rulings in
`decisions.md`):** one call per (reflection × scene-type), cached in the append-only
`compiled_bundles` table (migration 008) — bundle liveness is DERIVED by joining the source
reflection's `invalid_at`, so bi-temporal reflection invalidation doubles as compiler-cache
eviction with zero bundle writes. Bundle = the fixed **typed core** — multipliers on the three
prose-view weights (relevance/recency/importance), clamped [0.25, 4.0] at write and re-clamped
at consume (module constants, mirrored by the migration CHECK) — plus **namespaced
passthrough** (stored, never interpreted server-side; C5's agent-state read is the recorded
future surface). *(The founding wording's "action-set biases" died with the A1 action-side
scrap 2026-08-04, and "stance priors" folded into the passthrough — corrected here with the
build; ruling 2.)* Scene-type vocabulary is integrator-owned (`agents.config` `scene_types`;
the reserved `default` always compiles); unknown types log-and-continue against the default
bundle, flagged in instrumentation. Compiled params are consumed **only upstream of the
dialogue call** — the composed per-axis products multiply the resolved weights before the
§9 re-rank; membership never changes, and a bundle-free turn is byte-identical to the pre-C3
seam (walker-asserted parity; no §7 amendment — ordering, never stored text). Scheduling is
the standalone **`CompilerWorker`** — the third background worker on the C1/C2 lifecycle
contract, default OFF per agent, **no endpoint and no route by ruling**; work discovery is
stateless SQL (the missing-pair join, the pressure-gauge precedent), and the generic jobs
table was surfaced with its real cost and declined as its own later task. The staleness guard
is all-mechanical — the K-window (`compiler_window_k`) enforced at discovery AND consume,
liveness-by-join, hard clamps — the downstream half of the ExpeL caution whose upstream half
is C2's RRR.

## 11. Instrumentation & load driver

- **Latency histogram:** p50/p95, decomposed into gate check, retrieval SQL, first token, total.
- **Gate efficacy, per signal:** novelty metric = fraction of fires where the fetched memory
  out-scores the loaded set; entity metric = near-ground-truth "did the retrieval contain that
  entity." Log which signal fired per gate event. *(Specced & **built** 2026-07-19 —
  instrumentation-only fire logs ruled, no `gate_events` table; the comparators live in the
  gate instrumentation + load-driver gate block; `mid-dialogue-gate.md`.)*
- **Cost:** itemized per 100-turn session.
- **Synthetic load driver:** Python, scripted sessions at volume; a first-class artifact co-built
  with the CLI harness. **No distribution exists without it.** *(Built 2026-07-15,
  `app\load_driver.py`: reuses the session-runner core; emits the latency p50/p95 decomposition —
  the gate term **landed 2026-07-19** (`gate_check` over gate-evaluated turns + the per-100-turn
  gate block; `mid-dialogue-gate.md`) — and the itemized per-100-turn token/USD table. The
  `observe_total` series **landed with C1**, 2026-08-12.)*
- **Deferred-work accounting (C1, 2026-08-12):** a background worker has no response payload to
  ride, so per-attempt timing/token accounting persists in **`memory_enrichment_runs`**
  (migration 006) — outcome, per-stage ms, token columns — surfaced on the unscored `/chain`
  read. The driver's cost table sums seam tokens; with deferral on, the run log is the
  deferred-spend source of truth (`deferred-writes.md`).

## 12. Integrator surface requirements

**The shipped HTTP surface** *(seventeen routes; five landed 2026-07-23 and 2026-07-27 —
`unity-client.md`; the metric read 2026-07-29 — `eval-harness.md`; the reflect verb
2026-08-15 — `reflection.md`; this paragraph still said "twelve" and omitted reflect until
2026-08-17, a C2 propagation miss corrected at the C3 build — C3 itself adds NO route by
ruling; the diegetic-correction event joined with C4, 2026-08-17 — `dissonance.md`; the
agent-state read with C5 the same day; the purge verb with C6, 2026-08-18 — the release-blocker
realized; the Ledger turn feed with E2, 2026-08-19)*:
`POST /v1/events/observe`,
`POST /v1/events/scene-boundary`,
**`POST /v1/events/diegetic-correction`** (the confrontation event — the dissonance path),
`PUT /v1/memories/{id}/pin`, `POST /v1/memories/{id}/correction`,
**`DELETE /v1/memories/{id}`** (the purge verb — the sole sanctioned content DELETE), `POST /v1/dialogue/init`,
**`POST /v1/dialogue/turn`** (stateless — all scene state rides the request; the runner bookkeeping
is the client's job), **`POST /v1/dialogue/turn/stream`** (its SSE twin, iterating the SAME
async-generator seam — `chunk` / `reconstructing` / `result` / `error` events), **`POST /v1/agents`**
(provisioning; UUID minted server-side), **`POST /v1/agents/{id}/reflect`** (the reflect verb),
the two **inspector reads** (§6),
**`GET /v1/memories/{id}/reconstruction-metrics`** (the judge-free metric read, §6),
**`GET /v1/agents/{id}/state`** (the agent-state read, §6 — C5),
**`GET /ledger`** (the static browser inspector, served BY the API so it shares the origin of the
routes it polls — no CORS surface, no second server), and
**`GET /v1/ledger/turns`** (E2, 2026-08-19 — The Ledger's live turn feed: both dialogue routes
tee their terminal `DialogueTurnResult` into an in-process ring buffer, cap 256, and this
schema-hidden read serves entries after a `?after=<seq>` cursor, each the turn response's
serialization verbatim. An explicit, ruled carve-out to the route pass-through contract: the
response stays byte-identical, but the dialogue routes now record the result in PROCESS MEMORY —
never the DB; a dialogue turn still persists nothing, and a restart starts the feed empty.
A demo inspector surface like `/ledger`, not integrator API).

**The client package** *(built 2026-07-27)*: `client\NpcMemory.Core` — netstandard2.1,
engine-agnostic (**zero `UnityEngine` types** by ruling), one flat `NpcMemoryClient` covering all
fourteen verbs 1:1 *(the metrics read joined 2026-07-29; the reflect verb 2026-08-15 — "eleven"
stood stale here until the 2026-08-17 correction; C3 adds no verb, its scene_type rides the
turn request; the diegetic-correct verb joined with C4 and the agent-state read with C5, both
2026-08-17 — "thirteen" missed C4's verb until the F0 audit, 2026-08-26; purge is server-only,
no client verb)*, plus `NpcSession`, the C# port
of the Python runner's turn bookkeeping *(C5 added the session's fire-and-forget observe
surface — `unity-client.md`)*. Unity gets a
thin MonoBehaviour adapter over it; a `dotnet run` console harness plays every demo beat headless.

Docs are written as though a **hostile integrator** is reading them, answering ownership questions
before they're asked: Whose Postgres is this? What happens on schema migration? What is the
retention policy? Can a player's memories be deleted?

- **Retention:** a tested **purge endpoint (per-memory `DELETE /v1/memories/{id}`, built C6
  2026-08-18), no scheduler** — the tool provides the delete verb, the schedule is the
  integrator's policy (this is the GDPR surface). Purge completeness stated honestly: the endpoint
  deletes the original, its chains (telling **and fact versions** — the latter specced 2026-07-18,
  `fact-level-correction.md`), and its caches; reflections previously derived from purged episodes
  are aggregate work-product left standing (their un-FK'd `source_memory_ids` may dangle), and the
  docs say so.
- Docs must draw the **verbatim/reconstructive read-mode boundary** (self-describing payloads carry
  it too), state per-field degradation for optional context fields, state the gate degradation
  ladder, and include a **"what this is not"** section.
- The service is disciplined by no real shipped game; the docs supply the discipline the absent
  consumer would have.

## 13. Positioning & research angle

**README positioning:** non-destructive bi-temporal storage vs destructive LLM compression, citing a
real counter-example system (still unpicked — carried by the F1 README bullet in `status.md`'s
roadmap; the old "artifact queue" structure is gone).

**Citations on record:** compressive-RAG framing (Spens & Burgess); the CoALA supersede-vs-decay gap
is answered by bi-temporal invalidation + differential decay classes; Talk of the Town's
repetition-breeds-commitment validates write-back; PSI/MicroPsi lineage for the parameter compiler;
Cite **encoding specificity as a phenomenon family, not the diving study** (its 2021
replication attempt failed, ~0.25 SD). *(Turpin and Gazzaniga backed the asymmetric-cognition
line; that leg was removed with the behavior side — kept on record as history.)*

**The signature claim** *(re-scoped 2026-08-04 — the research track is scrapped by ruling: no
write-up, no submission; the stage-4 fixed-gist ablation survives as R7's engineering evidence)*:
**identity-conditioned reconstructive memory** — the same store retold through the character.
The information-asymmetry leg died with the behavior/action side; its small surviving flavor is
weights-on-speech (§9): the NPC's words shaped by per-call weights it is unaware of.
