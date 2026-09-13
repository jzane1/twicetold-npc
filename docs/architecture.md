# twicetold-npc: Architecture

This is the design truth: what each layer does and why. The first schema is specced in
`migration-01.md`; test discipline is in `test-suite.md`; the integrator-facing guides are
`first-npc.md`, `shipping.md`, and `identity-authoring.md`.

## 1. What this is

A generalizable long-term-memory service for game NPCs that others integrate into their own games or
applications: a self-hostable backend (FastAPI + PostgreSQL/pgvector) plus a Unity-embeddable client
package. You never talk to a hosted service; integrators run the backend themselves.

The system gives characters psychologically plausible memory: a bi-temporal, non-destructive record
underneath, with identity-conditioned reconstructive recall, believable decay, and dissonance-driven
defense above it.

**Thesis:** behavior, then confabulated reason, then stored, then defended. *A psychology, not a
database.* The claim axis is **controlled infidelity above an immutable record**: the character's
telling of a memory can drift and be defended, while the ground-truth record underneath never lies.

## 2. Non-negotiable principles

- **Bi-temporal, non-destructive.** Every memory row carries `created_at` (when it was written),
  `valid_at` (when it happened in world time, wired to the client-sent timestamp, timezone-aware),
  and `invalid_at` (when it was superseded, if ever). Superseded rows survive and stay queryable.
  Reflections carry the same columns.
- **Recency decay and correction-override are structurally distinct mechanisms.** Decay is a
  read-time computation; correction is a bi-temporal invalidation. They are never conflated, and the
  test suite proves the separation.
- **Importance and relevance are independent axes.** Importance is scored once at write time (stored
  raw, normalized at read), anchored to a per-NPC, integrator-configured diagnosticity goal.
  Relevance is computed per-query at read time.
- **Write-time facts vs runtime state.** Facts about the event (typology, confidence, context
  components, decay class, provenance, gist/detail spans, importance) are populated at write. Runtime
  state (reflection pressure, drift headroom) ships with its mechanism and needs no backfill.
  Importance is a write-time fact about the event: reconstruction drifts the *telling*, not the
  event's centrality, so defending by day-0 importance is deliberate. If dynamic salience ever
  enters, it enters as a separate runtime term.
- **Schema now, mechanism later.** Schema, caches, and pin behavior are live even where the consuming
  mechanism lands later. Sequencing orders work; it never vetoes a design option.
- **Integrator-defined vocabulary everywhere.** Observation phase tags, diagnosticity goal,
  context-match weights, scene-type vocabulary, model roles, the model backend and its base URL, the
  embedding model name and base URL, rigidity, prose-view weights, decay knobs, drift threshold:
  none is ever hardcoded. Violating this anywhere makes the config surface incoherent.
- **Instrument at the seam, not after.** Timing and token accounting are added to each layer as that
  layer is built.
- **Storage before cognition** build ordering.
- **Degradation behavior is named and tested per model call.** Importance-scoring failure stores the
  memory with neutral importance plus a `scoring_failed` flag. Embedding failure lands the write with
  a NULL embedding on the live fact head (`memory_fact_versions.embedding IS NULL` is the queryable
  signal); a write is never lost because a model was flaky, and correcting an embed-degraded memory
  re-embeds it. The authorial-correction verb is the deliberate contrast: all-or-nothing, fail-loud
  on embed failure. A gist-escalation call that fails twice soft-degrades: the write lands with the
  base NLP-pass gist and `escalation_failed = true` (migration 005). The retrieval gate degrades per
  its ladder (section 6), fail-quiet. Malformed-model-response cases live in the test suite.

## 3. Environment & stack

**Environment.** Windows 11, PowerShell syntax and backslash paths throughout, never bash. Paths in
these docs are relative to the repo root (`docs\`, `app\`, `unity\`), so a clone works from any
location. Unity 6, flatscreen 3D (CharacterController + mouse-look, raycast-plus-key interactables).
Global Python 3.14 on PATH. Secrets live in `.env` at repo root, never in docs. C# root namespace
`NpcMemory`; the Unity client ships as an embedded Unity Package Manager package at
`unity\Packages\com.jacksonzane.twicetold-npc\` (`Runtime\Core` is the engine-agnostic core,
`Runtime\` the MonoBehaviour adapter; `NpcDemoDriver` stays under `Assets\Scripts\` as the dev rig).

**Backend.** FastAPI; psycopg v3 with `AsyncConnectionPool`; hand-written SQL (no ORM);
PostgreSQL 16 + pgvector in Docker (the `pgvector/pgvector` image); UUID primary keys minted
server-side; HNSW vector index (a cheaply reversible choice).

**Models.** A Haiku-class slate serves importance scoring, description rendering, typology
classification, gist escalation, reflection, reconstruction, and streaming dialogue prose. That
choice is measured, not assumed: a larger model's prose is judge-preferred, but perceived first word
is the decisive axis and only the Haiku-class slate sits under the sub-second bar. Every model role
is an integrator knob with its own env var, and nothing is hardcoded. **Six vars exist and real mode
requires all six:** `TWICETOLD_MODEL_` + `IMPORTANCE`, `RENDER`, `TYPOLOGY`, `ESCALATION`,
`DIALOGUE`, `RECONSTRUCTION`. A seventh, `TWICETOLD_MODEL_JUDGE`, is eval-runner-only: loaded in both
modes, required by neither, since the server never carries a judge and the eval runner validates it
itself on judged runs (`eval-harness.md`).

One honest limit on "each role upgrades independently": v1 serves importance, render, and typology
from **one** write call, so those three vars must name the same model (`load_settings` raises rather
than silently picking one). Two more vars are judge-shaped, loaded in both modes and required by
neither, loud at first real use: `TWICETOLD_MODEL_REFLECTION` (the reflect verb) and
`TWICETOLD_MODEL_COMPILER` (the compiler worker, which has no endpoint, so its first real call is
always the worker's). The retrieval gate is **non-LLM**: there is no gate model and no gate env var.

**The model backend.** One explicit selector, `TWICETOLD_MODEL_BACKEND`, carries every LLM role (the
six product roles and the judge-shaped ones): `anthropic` (the default; the locked slate's
Messages-API requests byte-for-byte) or `openai` (any OpenAI-compatible chat-completions server
behind `TWICETOLD_MODEL_BASE_URL`: OpenAI, Ollama, vLLM, LM Studio, llama.cpp server, OpenRouter,
LiteLLM; an optional `TWICETOLD_MODEL_API_KEY`, a placeholder when blank). The same six role vars
name the models on either backend. In code it is one seam: every real role keeps its prompt, its
parse, and its error wrapper and asks a `ChatBackend` for the completion (`AnthropicChatBackend` or
`OpenAIChatBackend`), so no role logic is duplicated (`app\providers.py`). On the openai backend the
token-limit field is named by `TWICETOLD_MODEL_TOKEN_LIMIT_FIELD`: `max_tokens` (the default, and the
field local servers document) or `max_completion_tokens` (the field hosted reasoning-class models
demand), with the per-role values unchanged either way. Structured calls send
`response_format=json_object` (the family's native mitigation for the small-model JSON failure mode),
the dialogue stream sends `stream_options.include_usage`, and no sampling params are sent (parity). A
server that reports no usage is counted zero with one warning per process; the Anthropic thinking
kwargs have no equivalent, so that knob is refused at load under openai and the judge's adaptive
thinking is dropped with one warning. Misconfigurations are loud at `load_settings` (a base URL or
key under anthropic, a missing base URL under openai, `max_completion_tokens` under anthropic); fake
mode constructs no client and reads no URL or key. **The small-model quality warning ships with the
knob** (`.env.example`, `SETUP.md` §4b): every measured number was taken on the locked Anthropic
slate and does not transfer, and small local models break the write call's JSON and the
drift-budgeted reconstruction first, loudly, by the documented degradation ladder.

**Embeddings.** The OpenAI embeddings API shape: hosted OpenAI by default
(`text-embedding-3-small`, the locked slate) or any OpenAI-compatible server through
`TWICETOLD_EMBEDDING_BASE_URL`, independent of the model backend. The model name is the
`TWICETOLD_EMBEDDING_MODEL` knob; the column dimension stays locked at 1536 and is enforced at the
seam. `dimensions=1536` is sent on every call (Matryoshka models emit exactly 1536); a narrower
vector is zero-padded to 1536, so cosine, L2, and inner product between padded vectors equal those of
the originals and the retrieval math is untouched (one warning per process); a wider vector is
refused loudly, because client-side truncation is unsound for non-Matryoshka models. The embedding
model is a per-database choice: switching it orphans every stored vector (no re-embed tooling in v1).
The same model embeds location names, descriptions, and gate-time utterances.

**Write-time NLP (no LLM).** spaCy `en_core_web_lg` + `fastcoref` for intra-observation coreference;
affect via VADER (compound to valence) plus the bundled Warriner 2013 VAD lexicon (arousal,
normalized 1-9 to 0-1; dominance lives in `affect_detail` jsonb). NRC-VAD was rejected at the license
gate (research-only, incompatible with the Apache-2.0 license); Warriner is CC-BY 4.0 (`data\lexicons\`
with attribution).

## 4. Data model

### 4.1 Gist and detail

Gist is a **span pointer into the immutable on-disk observation text**, not a rewritten summary. At
write time, the NLP pass matches tokens, entities, and noun-chunks against the NPC's **identity
components table** (canonical name + aliases + category, e.g. friend names, job title; a category hit
counts even without a named entity). Hits become gist spans; everything else is detail.

An LLM escalation pass exists for hard cases, **biased loose** (a wasted call is cheap; a lost gist
breaks the product). Six triggers, any one fires, all integrator-tunable via `agents.config` with
defaults in `app\config.py`: (1) importance above threshold; (2) an identity/category hit co-occurring
with |valence| above threshold; (3) a **novel entity**, which is also how the identity components
table grows; (4) an unresolved pronoun/noun-chunk co-occurring with an identity/category hit; (5) low
NLP confidence on an already-flagged span (confidence only ever adds calls, never suppresses one);
(6) **thin gist**, where the base NLP pass yielded fewer spans than the `escalation_min_base_spans`
floor (default 1: fire on zero), protecting the gist floor directly (0.0 disables). Cross-observation
coreference misses are accepted as graceful failure: the detail just decays.

### 4.2 Decay

`tau_effective = tau_base × (1 + k × importance)`; `decay = 1 − exp(−age / tau_effective)`.

Decay applies to **non-gist detail only**, which decays to fully hidden; **gist never decays**. Decay
is computed at read time; the original observation stays intact on disk forever, and decay only
controls how much detail the reconstructor is shown, so any past state is re-derivable (debugging,
eval harness). Each memory carries a **decay class**: an integrator-vocabulary label selecting which
base time-constant applies, used by both detail decay and the recency term in retrieval scoring.

**Consequence to remember:** the identity components table is the *only* control on long-term durable
content. Its reflection-time trim (with silent cache invalidation, chosen deliberately) is the sole
mechanism that removes a durable fact.

### 4.3 Two identity structures, never conflated

1. **Identity components table:** an entity/topic index (canonical + aliases + category). Used for
   gist matching and as the entity-gate tripwire; grown by the LLM on novel entities; pruned at
   reflection time, silently invalidating reconstruction caches.
2. **Rendered identity document:** seed prose plus current identity-relevant reflections, rendered
   into the exact prompt block. `identity_version` is a content hash of the rendered document,
   recompiled at scene edges: the scene-boundary handler recompiles server-side and returns
   `identity_version`, and the caller freezes it as scene state and passes it per read request (the
   caller-frozen-scene-state contract).

### 4.4 The fact-version chain

The memories row's **semantic basis** (the text retrieval ranks by, and its embedding) gains the same
bi-temporal machinery the telling has: a child chain under the stable `memory_id` (supersede by
`invalid_at`, one live head, `write_cause` discrimination), created by migration 002 with an
`original` row backfilled per existing memory. Observe writes the vector only to the fact head. The
authorial-correction verb is **fact-following**: the operator's corrected text becomes both the
telling head and the embedded fact basis in one transaction, so retrieval follows the fix. Entities
follow too: migration 003 gives them a fact-chain home, and the correction verb re-derives them via
mechanical NER merged with an optional operator field, mirroring observe. Importance, typology, decay
class, and affect stand as write-time facts about the *event*. Accepted asymmetry: a corrected
memory's embedding basis is the operator's corrected text rather than observation-class text, the
same ground-truth rule as constraint-follows-anchor.

## 5. Write path

Client event, then NLP span/affect pass, then a **single Haiku call** (prose render + importance
scoring; typology classification only when the client did not declare it), then an **atomic insert**
populating all write-time facts.

An optional deferred-write mode (the `deferred_writes_enabled` knob, **default OFF**, migration 006)
moves the two LLM calls to an in-process worker. The NLP pass, embedding, and atomic insert stay
synchronous; the raw text lands as the live `original` head with the write-call scalars NULL and
`enrichment_pending` set; the worker's one-shot completion fills the scalars and supersedes the head
with the render, `write_cause = 'enrichment'`, which also joins the drift-anchor set. This is the one
exception to "populate all write-time facts at write": a deferred row's write-time window is stretched
to the worker's completion, and the terminal-failure fill is byte-equivalent to the synchronous
scoring-failed end-state, so deferral never adds a lost-write rung.

- **Evidence typology:** `observed | told | inferred | reflected`, with a 0-1 confidence. A default
  per-typology confidence table exists; the client may override per event, and **client declaration
  wins**. `typology_source` records `declared | inferred` (distinct from provenance).
- **Provenance:** `lived | injected` (injected = operator-seeded backstory).
- **Context stamps:** location, entities, time, affect. All four are optional API fields with stated
  per-field degradation when absent. Stored as typed columns per component (per-component read weights
  require it); location is embedded via the same 1536 model. **Entities are captured at write:** the
  entities column and GIN index serve the gate and the encoding-context read boost (§6). Migration 003
  gives entities a fact-chain home; observe writes the fact head only, and the GIN lives on live fact
  heads.

## 6. Read path

**Dialogue initialization:** top-k retrieval. Endpoints that run retrieval return **memory IDs and
scores alongside prose**; this is load-bearing, and it is what makes the test suite assertable. Four
reads are unscored **by contract**, because they run no retrieval so no scores exist: the two
inspector reads below, the judge-free metric read, and the agent-state read. They carry IDs and
structured fields on every row.

**Inspector reads:** the record made legible, and the Ledger's data source.
`GET /v1/memories/{id}/chain` returns the immutable observation beside BOTH version chains with
superseded rows **present** (greyed client-side, never dropped) plus gist spans and a `has_embedding`
flag that never exposes the vector. `GET /v1/agents/{id}/memories` is the per-agent index, newest
`valid_at` first, each memory beside its live telling head, with `limit` a caller argument and never a
config knob. SELECT-only end to end; 404 on unknown memory/agent.

**The judge-free metric read** (`eval-harness.md`): `GET /v1/memories/{id}/reconstruction-metrics`
computes gist-precision, detail-recall, fabrication, and keyword-retention against the **live telling
head**, feeding both the Ledger's on-screen numbers and the eval harness's judge-free layer from one
implementation (`app\eval_metrics.py`). It is anchor-cause-aware (a correction-anchored chain scores
against the corrected head and owes no detail), uses honest denominators (`None`, never a flattering
1.0), and reads bands from the reconstruction cache's composed keys. It runs no retrieval and performs
**zero writes**: the identity document is the pure render, never an upsert. The presence rule is the
`metric_gist_match_threshold` knob (default 1.0, strict lexical; paraphrase slack belongs to the
judged categories).

**The agent-state read**: `GET /v1/agents/{id}/state` is the composed runtime snapshot. Payload: the
stored agent row **as stored** (`config` verbatim, never merged with defaults, since a resolved
snapshot would rot), the current `identity_version` (the newest document row, SELECT-only), the
reflection-pressure gauge (computed on demand, never stored, per §2's runtime-state rule), the live
beliefs in compiler-window order (the first `compiler_window_k` rows are the compile window by
construction), the newest live bundle per (belief, scene_type) with liveness derived from the source
reflection (§10), and the two worker run logs newest-first capped by `runs_limit` (a caller argument).
Zero writes; 404 on unknown agent.

**Retrieval scoring** (`relevance × recency(decay class) × importance_norm`): pin exemption;
normalization; reserved slots for per-call overrides under the dialogue topology. `importance_norm`
is clamp + floor (over min-max, so invalidation can never move other items' scores); the decay math
lives once, in `app\decay.py`, shared by the reconstruction theta check. The relevance probe reads
the **live fact-version head's** embedding, so scores move only through relevance.

An **encoding-context term** multiplies a soft context factor into the score: the request's
`location_name`, `entities`, and `event_time` contribute entity coverage over the live fact head's
entities, an event-time proximity kernel, and a casefold location match, each weighted by its own
integrator knob. A no-context request skips the factor (scoring is then byte-identical to the base
formula); it is never a filter and never a penalty, and it applies on loader, gated, and degraded
paths.

A **hybrid lexical channel** (migration 004) adds a token-OR full-text candidate fetch off a partial
GIN over live fact heads (`to_tsvector('simple', basis_text)`), unioned into the vector over-fetch
before scoring: dedup by memory_id, the scoring formula untouched, lexical hits carrying their true
cosine relevance (NULL-embedding heads reachable with relevance null, so exact-token recall softens
the embed-degradation consequence). The `lexical_fetch_k` knob (0 = kill-switch) and the
`text_search_config` string knob (`'simple'` default, baked into the index expression) govern it.
This is the seeding base any future graph/PPR term would build on.

**Mid-dialogue gate (non-LLM hybrid):** the loaded set is caller-held scene state per the read
contract (migration 003 live).
- **Novelty check:** embed the utterance, measure distance against the loaded set; far from all,
  fetch.
- **Entity tripwire:** an uncovered mention of an identity-components entry, fetch (the most
  demo-legible signal).
- A fruitless-retrieval damper limits accumulation. Every gate event logs **which signal fired**.

**Degradation ladder:** embeddings down, fall to entity-only, fetching lexically off the GIN index
ranked by recency × importance; no entities supplied, novelty-only; both out, gate closed, serve the
loaded set, **fail-quiet**.

**Prompt caching:** within a scene, gate-fetched memories are **appended after the cached head** as a
marked recollection block; the head is **rebuilt at scene boundaries**, where the cache is cold
anyway. The **scene boundary is a load-bearing, explicit client-sent API event** with two consumers:
prompt-head rebuild and identity-document recompile. Scene edges settle prefix and identity version in
one heartbeat.

**Read-mode boundary (self-describing, not just documented):** every returned memory carries
`read_mode` (`verbatim | reconstructed`) and `pinned`, in payloads and the debug view. Three states:
pinned is verbatim always; unpinned fresher than the reconstruction threshold is verbatim for now;
unpinned past the threshold is reconstructed. A fourth enum value, `reconstruction_pending`, exists
only if an async fallback is ever adopted. **Purity claim:** no raw access through the character read
path, except integrator-designated pins; ground truth lives in the debug view.

## 7. Reconstruction

Identity-conditioned reconstruction is the **mandatory read path** for unpinned memories past a
threshold theta, where **theta reuses the decay math** (reconstruct when decayed detail strength falls
below theta; text-affecting decay evaluations bind to a scene-frozen basis, so read-mode never flips
mid-scene). The reconstructor sees the **full gist span as a fixed constraint** plus the time-thinned
detail slice **plus the current live head** ("how you currently tell it": retellings compound, and
without the prior telling the drift budget rarely binds), conditioned on the rendered identity
document. On a chain whose drift anchor is a correction head (`authorial_correction`, or
`update_with_resentment` from the diegetic path), the fixed constraint follows the anchor: that head
replaces the stale gist constraint, and original observation detail is never re-injected.

**Write-back with a version chain:** one permanent `memory_id` forever; each retelling inserts a new
detail row and stamps the prior one superseded, giving **versioned confabulation over an immutable
record**. Chain rows carry a `write_cause` enum:
`original | reconstruction | rationalization | update_with_resentment | authorial_correction |
enrichment` (the sixth value joined with migration 006).

**Serving:** the Haiku-class slate; **one structured call batching all k cache misses per
retrieval**; pre-warm at dialogue init; on a mid-scene miss, **block and expose a "reconstructing"
signal** (latency becomes characterization). Async serve-verbatim-then-cache is **not** the design: if
latency ever forces async, the swap must be explicit state (a `reconstruction_pending` read mode),
never silent text mutation, because of the **within-scene text-stability invariant**. Absent a
diegetic event, an authorial correction, a deferred-enrichment completion (the window bounded by the
worker's poll interval), or a reflection-trim cache eviction (per-affected memory only; reflect at
scene edges and the window vanishes), repeated reads within one scene return byte-identical text.
Those four are the only sanctioned mid-scene text-change causes.

**Cache:** keyed `(memory_id × identity_version)`, where the version component **composes
`identity_version` with a quantized, scene-frozen decay band**: the band both keys the cache and sets
the thinning level, so the same key yields byte-identical text and deeper decay re-reconstructs on
thinner detail. **Cache-eviction invariant (generalized):** cache writes happen only in the
reconstruction path; any other writer to a chain (correction, diegetic write, deferred-enrichment
completion on every completion shape including facts-only, purge) must evict all cache rows for that
memory_id.

**Drift budget:** on each reconstruction-driven write-back, embed the candidate and measure distance
from the anchor; past threshold, **refuse the write and keep the prior head**. Event-driven writes
(both diegetic paths) are exempt. **Scope of the guard:** the budget is a **topic guard**. It catches
wholesale nonsense and topic-swaps (embedding-neighborhood departure) and is blind by construction to
fact-level drift; an ablation confirmed it (retellings generated without the gist constraint drifted
no further, 0 over-budget in both arms, mean paired |Δ| 0.056, while gist-precision dropped
0.834 to 0.704). Factual faithfulness is policed by the other two guards: the **fixed gist constraint
plus gist-precision** (fact survival, the judge-free metric read) and the **judged faithfulness
category** (semantic support, past the agreement bar). **The anchor needs no pointer:** it is the
latest chain row whose `write_cause` is `original`, `authorial_correction`,
`update_with_resentment`, or `enrichment`. Re-anchoring by cause: authorial to the corrected head;
update-with-resentment to the new head; rationalization **never** (it spends headroom without being
blocked, so a heavily defended memory crystallizes, "the story has set"). Demo artifact: one memory
drifting across 60 days.

## 8. Dissonance and correction verbs

**Dissonance threshold** = importance × evidence typology × per-NPC **rigidity** scalar
(0.5 pushover to 2.0 zealot). "I saw it" resists harder than "I heard it," on both sides of a clash.
Either way **the store records the truth**; the fork only shapes the character's reaction.

**Two correction verbs, semantically distinct:**
- **Authorial** (operator fixes wrong data): **replace model**. Supersedes the drifted chain with a
  corrected head row, `write_cause = authorial_correction`. The memory stays retrievable under the
  same memory_id, now serving corrected content, and the corrected head becomes the drift anchor.
  Prior rows are invalidated by ordinary supersession; the verbs are discriminated by the new head's
  `write_cause`, not by any marker on prior rows. It takes effect immediately, mid-scene included, and
  the corrected head becomes the reconstructor's fixed constraint for that chain. The verb is
  fact-following: the corrected text is also the embedded fact basis (migration 002), so retrieval
  follows the fix.
- **Diegetic** (in-world confrontation; an API event referencing a target `memory_id`): preserves the
  chain and routes through the dissonance path; the new head row is typed `rationalization` or
  `update_with_resentment`, and a correction record is present. The defend-vs-update fork is the §8
  formula computed mechanically (no model call decides; every multiplier is a knob); the
  RECONSTRUCTION role writes the new telling in the decided stance (no new env var); it is
  tellings-only, so the fact chain never moves and retrieval keeps matching the original account.
  `POST /v1/events/diegetic-correction`, no migration (the `corrections` table has waited since 001).

**Pin semantics:** both correction verbs **outrank pin**, and the resulting new head **inherits the
pin**. Pin means exactly two things: exemption from decay, and exclusion from the reconstruction
process. "No reconstructed chains" does not mean "no chains": event-driven corrections proceed at the
normal dissonance frequency. Pin and unpin are endpoints; pinning **freezes the current head**
(restoration is a correction verb, not pin), and unpinning resumes the chain from the frozen head.

## 9. Dialogue output & turn topology

**The shipped topology: one streaming prose call plus weights-on-speech.** Deciding actions belongs to
the game developer; the NPC's own actions arrive as ordinary observes (the game-authored
action-observe contract).

The seam (`app\dialogue.py`, an async generator): retrieval runs ONCE, the served top-k is
**re-ranked with resolved per-call weights**, the re-ranked view feeds the prose prompt
(`[identity] [memories] [output]`), and the dialogue-role call **streams pure prose**, chunks yielding
through the seam. Over HTTP, `POST /v1/dialogue/turn` drains this generator to the terminal result and
the SSE twin `POST /v1/dialogue/turn/stream` iterates the same generator, which is the no-rewrite
payoff of the generator seam. `first_word_ms` is prose TTFT at the seam; `perceived_first_word_ms`
rides beside it, clocked from turn start, so it sees the cold-reconstruction stall the former is blind
to (the honest metric the sub-second bar is measured against). **A dialogue turn persists nothing.**

**Weights-on-speech:** per-call `weight_overrides` `{relevance, recency, importance}` resolve request
field, then `agents.config` (`weight_relevance` / `weight_recency` / `weight_importance`), then 1.0,
clamped [0.0, 4.0] (module constants, not knobs), and re-rank the served set in exponent form on the
product score: `weighted_score = item.score · rel^(w_rel−1) · rec^(w_rec−1) · imp^(w_imp−1)`,
zero-base components skipped, ties on `memory_id`. The NPC's words are shaped by weights it is unaware
of. Contracts: **membership never changes** (the re-rank is post-cut over the served top-k; weights
cannot pull in a memory retrieval excluded); retrieval scoring stays **byte-identical** (the re-rank
lives at the dialogue seam; `app\retrieval.py` is untouched); at all-1.0 weights the re-rank is the
identity (on a loader turn `dialogue_view` equals the (id, score) projection of `items`). On gated
turns the prompt's `[memories]` block still renders the loaded set in the caller's append-only order;
`dialogue_view` reports the weighted ranking in all cases. The turn result carries `items` (the raw
retrieval echo, the IDs+scores invariant) beside `dialogue_view` (the weight-ranked view the prompt
was built from).

## 10. Reflection & parameter bundles

Reflection is an **endpoint** (the verb), `POST /v1/agents/{agent_id}/reflect`, integrator-pulled,
plus an **optional sibling `ReflectionWorker`**, **default OFF**, that pulls the same internal seam
when **reflection pressure** (a computed, never-stored gauge, per §2's runtime-state rule) crosses a
per-agent knob threshold. The store exposes the gauge; the integrator, or the opted-in worker, pulls
the trigger. Sampling: episodes weighted by **importance × recency** (the diagnosticity axis), not
recent-N; the sampled text is the live telling head.

Reflection writes formed beliefs to the **`reflections` table**, the sole durable home (citations in
`source_memory_ids`), never into retrieval. The **seed stays immutable**: identity-relevant
reflections join the rendered identity document via a model-free concatenative render, and the
periodic evidence-conditioned refresh is an LLM **consolidation reflection** that bi-temporally
absorbs the rows it summarizes (`identity_documents` gains rows, never mutations; the dialogue prompt
rides the rendered document). `identity_version` bumps via content hash exactly as always. Reflection
also **prunes the identity components table** by a purely mechanical 3-clause rule; the gist
constraint follows component liveness, and reflection-driven eviction is the fourth sanctioned
mid-scene text-change cause (§7's writer list). A non-LLM RRR repetition guard gates the identity
consolidation. (`app\reflection.py`; migration 007 `reflection_runs`; the worker default OFF per
agent.)

**Parameter compiler:** one call per (reflection × scene-type), cached in the append-only
`compiled_bundles` table (migration 008). Bundle liveness is derived by joining the source
reflection's `invalid_at`, so bi-temporal reflection invalidation doubles as compiler-cache eviction
with zero bundle writes. A bundle is the fixed **typed core** (multipliers on the three prose-view
weights, relevance/recency/importance, clamped [0.25, 4.0] at write and re-clamped at consume, a
module constant mirrored by the migration CHECK) plus **namespaced passthrough** (stored, never
interpreted server-side; the agent-state read is its surface). Scene-type vocabulary is
integrator-owned (`agents.config` `scene_types`; the reserved `default` always compiles); unknown
types log-and-continue against the default bundle, flagged in instrumentation. Compiled params are
consumed **only upstream of the dialogue call**: the composed per-axis products multiply the resolved
weights before the §9 re-rank, membership never changes, and a bundle-free turn is byte-identical to
the pre-compiler seam (walker-asserted parity). Scheduling is the standalone **`CompilerWorker`**, the
third background worker, default OFF per agent, with **no endpoint and no route**; work discovery is
stateless SQL (the missing-pair join). The staleness guard is all-mechanical: the K-window
(`compiler_window_k`) enforced at discovery and consume, liveness-by-join, hard clamps.

## 11. Instrumentation & load driver

- **Latency histogram:** p50/p95, decomposed into gate check, retrieval SQL, first token, total.
- **Gate efficacy, per signal:** the novelty metric is the fraction of fires where the fetched memory
  out-scores the loaded set; the entity metric is a near-ground-truth "did the retrieval contain that
  entity." Which signal fired is logged per gate event (instrumentation-only fire logs, no
  `gate_events` table).
- **Cost:** itemized per 100-turn session.
- **Synthetic load driver:** Python, scripted sessions at volume, a first-class artifact co-built with
  the CLI harness (`app\load_driver.py`); it reuses the session-runner core and emits the latency
  p50/p95 decomposition (including the gate term) and the itemized per-100-turn token/USD table.
- **Deferred-work accounting:** a background worker has no response payload to ride, so per-attempt
  timing and token accounting persist in **`memory_enrichment_runs`** (migration 006): outcome,
  per-stage ms, token columns, surfaced on the unscored `/chain` read. With deferral on, the run log
  is the deferred-spend source of truth.

## 12. Integrator surface requirements

**The shipped HTTP surface (eighteen routes):**
`POST /v1/events/observe`,
`POST /v1/events/scene-boundary`,
**`POST /v1/events/diegetic-correction`** (the confrontation event, the dissonance path),
`PUT /v1/memories/{id}/pin`, `POST /v1/memories/{id}/correction`,
**`DELETE /v1/memories/{id}`** (the purge verb, the sanctioned content DELETE) and
**`DELETE /v1/agents/{id}/memories`** (its per-agent extension: the same seven-table delete over every
memory of one agent, in one transaction; the two purge verbs are the whole carve-out),
`POST /v1/dialogue/init`,
**`POST /v1/dialogue/turn`** (stateless: all scene state rides the request; the runner bookkeeping is
the client's job), **`POST /v1/dialogue/turn/stream`** (its SSE twin, iterating the SAME
async-generator seam, with `chunk` / `reconstructing` / `result` / `error` events),
**`POST /v1/agents`** (provisioning; UUID minted server-side),
**`POST /v1/agents/{id}/reflect`** (the reflect verb),
the two **inspector reads** (§6),
**`GET /v1/memories/{id}/reconstruction-metrics`** (the judge-free metric read, §6),
**`GET /v1/agents/{id}/state`** (the agent-state read, §6),
**`GET /ledger`** (the static browser inspector, served BY the API so it shares the origin of the
routes it polls: no CORS surface, no second server), and
**`GET /v1/ledger/turns`** (the Ledger's live turn feed: both dialogue routes tee their terminal
`DialogueTurnResult` into an in-process ring buffer, cap 256, and this schema-hidden read serves
entries after a `?after=<seq>` cursor, each the turn response's serialization verbatim. It is a ruled
carve-out to the pass-through contract: the response stays byte-identical, but the dialogue routes now
record the result in PROCESS MEMORY, never the DB; a dialogue turn still persists nothing, and a
restart starts the feed empty. A demo inspector surface, not integrator API.)

**The client package:** `client\NpcMemory.Core`, netstandard2.1, engine-agnostic (**zero
`UnityEngine` types**), one flat `NpcMemoryClient` covering all fourteen verbs 1:1, plus `NpcSession`,
the C# port of the Python runner's turn bookkeeping and its fire-and-forget observe surface. Unity
gets a thin MonoBehaviour adapter over it, and a `dotnet run` console harness plays every demo beat
headless. (Both purge verbs are server-only, no client verb.)

Docs are written as though a **hostile integrator** is reading them, answering ownership questions
before they are asked: Whose Postgres is this? What happens on schema migration? What is the retention
policy? Can a player's memories be deleted?

- **Retention:** two tested **purge verbs** (per-memory `DELETE /v1/memories/{id}` and per-agent
  `DELETE /v1/agents/{id}/memories`: the same delete over every memory of one agent, one transaction,
  summed counts, a 200 with zeros for a known agent with nothing left), **no scheduler**. The tool
  provides the delete verbs; the schedule is the integrator's policy (this is the GDPR surface). Purge
  completeness is stated honestly: the verbs delete the original, its chains (telling **and fact
  versions**), and its caches; reflections previously derived from purged episodes are aggregate
  work-product left standing (their un-FK'd `source_memory_ids` may dangle), and the agent row, its
  identity, bundles, and run logs are untouched. It is not a GDPR button by itself: memories attach to
  NPC agents, not players, so the integrator owns the player-to-memory mapping.
- Docs must draw the **verbatim/reconstructive read-mode boundary** (self-describing payloads carry it
  too), state per-field degradation for optional context fields, state the gate degradation ladder,
  and include a **"what this is not"** section.
- The service is disciplined by no real shipped game; the docs supply the discipline the absent
  consumer would have.

## 13. Positioning & research angle

**Positioning:** non-destructive bi-temporal storage vs destructive LLM compression, citing a real
counter-example: LangChain's `SummarizationMiddleware` (and the classic
`ConversationSummaryBufferMemory` before it), which folds older messages into a running summary and
removes them from the agent's message state, so what the model sees afterward is the summary plus the
recent tail. The README's comparison table names it, with the claim kept at "what the agent sees."

**Citations on record:** compressive-RAG framing (Spens & Burgess); the CoALA supersede-vs-decay gap,
answered by bi-temporal invalidation plus differential decay classes; Talk of the Town's
repetition-breeds-commitment, which validates write-back; the PSI/MicroPsi lineage for the parameter
compiler; encoding specificity cited as a phenomenon family, not the diving study (its 2021
replication attempt failed, ~0.25 SD).

**The signature claim: identity-conditioned reconstructive memory**, the same store retold through the
character. Its small surviving flavor of information asymmetry is weights-on-speech (§9): the NPC's
words shaped by per-call weights it is unaware of.
