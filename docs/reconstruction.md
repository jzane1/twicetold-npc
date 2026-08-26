# Reconstruction — v1 build target

Fifth build target, on top of migration 01, write path v1, read path v1, and CLI harness v1. This
specs **identity-conditioned reconstruction as the mandatory read path past theta** — the thesis
mechanism (*controlled infidelity above an immutable record*), re-slated pre-demo 2026-07-14. It
swaps the read path's **serving stage only**: retrieval and scoring are untouched
(`read-path.md`'s serving boundary was drawn for exactly this attach). Design truth is
[architecture.md](architecture.md) §7 (+ §4.2 decay, §4.3 identity structures, §6 read-mode
boundary); the rulings behind it are in [decisions.md](decisions.md); the schema it reads and
writes is frozen in [migration-01.md](migration-01.md) — `reconstruction_cache`,
`identity_documents`, and the `write_cause` chain enum are already live. This doc points, it does
not re-derive.

Three scope forks were ruled at spec time (dated "Reconstruction spec scope rulings" entry in
`decisions.md`): the reconstructor's input **includes the current live head** ("how you currently
tell it"); the cache key's version component **composes `identity_version` with a quantized,
scene-frozen decay band** (the pre-demo drift driver); and identity-document plumbing is
**hybrid, reputation-style** (server recompiles at the scene boundary and returns
`identity_version`; the caller freezes it as scene state and passes it per request).

> **Status: BUILT & floor-verified 2026-07-17.** Every `[SETTLE-AT-BUILD]` item below was ruled at
> build time (dated "Reconstruction build rulings" entry in `decisions.md`; the two genuine forks
> — the **locality-sensitive fake embedding** rewrite the drift budget surfaced, and the
> **`drift_budget_threshold` default 0.35** — were ruled via explicit questions at plan approval,
> the rest approved with the plan); the rulings are annotated inline. **The build added no new DB
> migration — the migration-01 schema stayed frozen** (`reconstruction_cache` and
> `identity_documents` were already live; the composed key rides the existing text column). The
> serving swap landed in `app\reconstruction.py` + `app\retrieval.py`; identity plumbing in
> `app\identity.py` + the scene-boundary handler + the session-runner; walker
> `tests\verify_reconstruction.py` (41 assertions). The two prior read-side walkers pin
> `reconstruction_theta = 0` in their fixture configs so they keep asserting the v1 serving
> contract with this stage knob-disabled (build-surfaced shape, flagged in the register).

## Principles this build honors

- **Non-destructive write-back.** A retelling **inserts** a new `memory_details` head
  (`write_cause = reconstruction`) and supersedes the prior row by setting `invalid_at` — ordinary
  supersession under one permanent `memory_id`. Never UPDATE content, never DELETE. *Versioned
  confabulation over an immutable record* (architecture §7).
- **Decay and invalidation stay distinct.** Theta and thinning are **decay consumers** (read-time
  computation over the shared math); write-back is **bi-temporal supersession**. They meet in this
  build and remain separate mechanisms — Set B's separation still asserts through scores.
- **Within-scene text stability, by construction.** Every text-affecting decay evaluation (theta,
  band, thinning level) binds to the **scene-frozen basis**, and the read path serves **only
  persisted text** (a committed cache row / chain head — never an unpersisted model response). Two
  reads in one scene are byte-identical structurally, not accidentally.
- **Honest self-description.** `read_mode` reports what actually happened: a failed reconstruction
  serves the live head and says so — never a claimed mechanism (the read-path v1 precedent).
- **IDs + scores in every payload.** Unchanged contract; `read_mode` merely becomes three-state
  real. The suite asserts on structure, never on generated prose.
- **Nothing integrator-configurable is hardcoded.** Theta, the band quantum, the drift threshold,
  the model role — service defaults in `app\config.py`, per-agent overrides via `agents.config`
  (the `agent_knob` pattern).
- **Degradation is named per model call** — the reconstruction call, the drift-check embedding,
  and the persistence step each have a stated soft path (ladder below). Never-blank-a-dialogue.
- **Instrument at the seam.** Reconstruction timing, token accounting, cache hit/miss and refusal
  counts ride the retrieval seam's existing instrumentation, feeding §11 and the CLI debug view.
- **Provider real + deterministic fake.** `LONGMEM_MODEL_RECONSTRUCTION` behind the established
  provider triad, so the structural walker and Set C run offline, keyless.

## Scope boundary — do NOT build

The mid-dialogue gate (immediate-queue item 1 since the 2026-07-18 fact-level build) — in this slice **every retrieval is dialogue init**,
so all cache misses resolve inside the pre-warm; the **block-with-"reconstructing"-signal mid-scene
miss path binds to the gate**, and the signal's wire shape is deliberately **not settled here**.
*(Settled 2026-07-19 at the gate spec: post-hoc response fields + an in-process pre-serve
callback — one defaulted parameter on the serving path, this floor re-opening at the gate
build; `mid-dialogue-gate.md`.)*
The authorial-correction endpoint (**built 2026-07-18**) — its obligations toward this layer
(evict all cache rows for the memory_id; the corrected head re-anchors the drift budget) are
stated here and built there. *(A third consequence was ruled 2026-07-17 at that target's spec: on
`authorial_correction`-anchored chains the fixed constraint follows the anchor — an assembly
change that deliberately re-opens this floor at that build; `authorial-correction.md`.)* The diegetic/dissonance path, reflection (the identity document stays **seed-prose-only**),
purge, prompt caching, and split-brain per-call weights (then post-August; *pulled forward
2026-07-21 — `split-brain-streaming.md`*). The pytest suite (Set C
rides item 2 since the 2026-07-18 renumber; this build ships the structural walker `tests\verify_reconstruction.py`). And **any
new DB schema or migration** — `reconstruction_cache` and `identity_documents` exist; the
composed cache key lives in the existing text column. If adjacent work looks necessary, **stop and
report** rather than expand scope.

## The serving swap (where this attaches)

`retrieve_dialogue_init` (`app\retrieval.py`), after top-k selection — the stage
`read-path.md` reserved. Retrieval and scoring are untouched; scores are identical to v1 for the
same store. Per returned item, serving resolves the **three-state read-mode boundary**
(architecture §6), now real:

1. **pinned** → verbatim, always (pin = decay exemption + reconstruction exclusion, §8).
2. **unpinned, detail strength ≥ theta** at the scene basis → verbatim, for now.
3. **unpinned, detail strength < theta** → **reconstructed**: cache lookup → on miss, batched
   reconstruction → drift check → persist → serve.

**Theta reuses THE decay math** (`app\decay.py`, as ruled with the read-path build): detail
strength *is* `recency(age, tau_effective)` — the same per-row value scoring already computes —
evaluated at the **scene-frozen basis** (below), not the per-call `as_of`. Reconstruct when it
falls below the `reconstruction_theta` knob. A memory therefore crosses theta at a scene edge,
never mid-scene. `as_of` time travel moves the basis at the next boundary — the 60-day drift beat
is `:as-of` jumps + `:scene` boundaries in the existing REPL.

**The route becomes a writing endpoint.** `POST /v1/dialogue/init` (and the in-process CLI turn)
now writes chain rows and cache rows on reconstruction. Read-path v1's read-only SQL was a scope
fact of verbatim-only serving, not a principle — architecture §7 mandates write-back on read. The
route stays a pass-through of the seam's `RetrievalResult`.

## Scene-frozen basis (the caller contract)

The session-runner already freezes scene state (the reputation snapshot, ruled 2026-07-15). This
build extends the same contract — scene state lives in the caller, refreshed only at a boundary:

| Frozen at scene boundary | Meaning |
|---|---|
| `identity_version` | returned by the scene-boundary handler's recompile (below); selects the identity document and keys the cache. |
| scene reference time | the boundary's effective world time (the current `as_of` under time travel, else now); **every text-affecting decay evaluation** (theta, band, thinning) computes age against this, so read-mode and served text cannot flip mid-scene. |

Both ride on `DialogueInitRequest` (and pass through `DialogueTurnRequest` untouched, like
`k`/`as_of`). Exact field names/shapes `[SETTLE-AT-BUILD]` — suggested: optional
`identity_version: str` + `scene_started_at` (tz-aware); when absent (a bare route call, no
boundary yet), the server falls back to `as_of_effective` as the basis and **lazy-bootstraps** the
identity document (below). Score-affecting recency keeps the per-call `as_of` — scores may move
within a scene; text may not.

## Identity document (hybrid plumbing, seed-prose-only)

Ruled at spec time: the **scene-boundary handler recompiles server-side and returns
`identity_version`** — the handler's first real server-side consumer (write-v1 accepted +
instrumented only; the 2026-07-14 slating lands here). Recompile = render the seed →
content-hash → upsert `identity_documents` (`(agent_id, identity_version)` PK; inserting an
existing version is a no-op) → return the version in the scene-boundary response.

- **Rendering pre-demo = `agents.seed_identity` verbatim.** No template — a decoration would be a
  hidden hardcoded authorial artifact (the query-composition rejection's reasoning). Reflections
  join the render post-August; the mechanism slot is this function.
- `identity_version` = content hash of `rendered_text`. `[SETTLE-AT-BUILD]` algorithm — suggested
  sha256 hex. NULL seed → `[SETTLE-AT-BUILD]` — suggested: render the empty string, hash it, and
  omit the identity block from the reconstruction prompt (the CLI harness's `[identity]`-omitted
  precedent).
- **Lazy bootstrap:** a read arriving with no `identity_version` ensures a current document exists
  (render + hash + upsert on demand) and proceeds under it, flagged in instrumentation. A request
  naming a version the server does not know is a **contract error, loud** (`[SETTLE-AT-BUILD]`
  exact error shape) — that is a broken caller, not a flaky model.

## The reconstruction call

**One structured call batches all k cache misses per retrieval** (pre-warm at dialogue init —
settled, register: *Reconstruction serving*). Model role `LONGMEM_MODEL_RECONSTRUCTION`
(Haiku-class — *re-confirmed 2026-07-28; the shipped config had drifted to sonnet-5 since
2026-07-21 and was corrected. See `architecture.md` §7 for the measurement consequence*),
following the provider triad exactly (`app\providers.py`): a Protocol, a real
implementation, and a **deterministic fake** (stable rendering per input, so cache/byte-identity
assertions run offline) plus failure-injection fakes for the ladder.

Per-memory input, conditioned on the **rendered identity document** (ruled at spec time — the
prior telling is included):

1. **Gist spans — fixed constraint.** The full span text, verbatim from `observation_text`
   (`memory_gist_spans` offsets). Never thinned, never dropped; the output must remain consistent
   with it. *(On `authorial_correction`-anchored chains the corrected head replaces the gist
   constraint — ruled 2026-07-17, lands with the authorial-correction build;
   `authorial-correction.md`.)*
2. **Time-thinned original detail.** The non-gist remainder of `observation_text`, thinned
   deterministically to the band's level (below) — §4.2: decay controls how much detail the
   reconstructor is shown.
3. **The current live head — "how you currently tell it."** The chain's live `content`.
   Retellings compound (Talk of the Town / Bartlett — the reason write-back exists), and the
   drift budget gets real work; without it, candidates hug the anchor and the refuse-write
   threshold never binds.

Output: a rendered retelling per `memory_id`, structured. `[SETTLE-AT-BUILD]` exact prompt-block
shape and output schema — suggested JSON-in-text keyed by memory_id (the write/dialogue
precedent), per-item salvage on partial parse (a malformed item degrades that item only). Prompt
assembly is a **pure function** (the `assemble_system_prompt` precedent) so the walker asserts
gist fidelity, thinning monotonicity, and prior-head inclusion without a model call.

## Cache contract

`reconstruction_cache`, PK `(memory_id, identity_version)` — frozen schema. The version column
stores the **composed reconstruction key** (ruled at spec time): `identity_version` ⊕ the
**decay band**, the quantized thinning level at the scene basis. `[SETTLE-AT-BUILD]` composition
format and quantum knob — suggested `{identity_version}|b{index}` with
`reconstruction_band_quantum` default 0.25 (bands: strength [1.0–0.75), [0.75–0.5), …).

- **The band both keys the cache and sets the thinning level.** Same stored key ⇒ same thinning
  input ⇒ (with the write-back below) **byte-identical served text** — the coherence that makes
  Set C's byte-identity row hold across scenes, not just within one. *(Corrected-chain input
  shape is `[SETTLE-AT-BUILD]` in `authorial-correction.md` — suggested there: on those chains
  the band keys the cache without selecting a thinning slice.)*
- **Identity bump ⇒ miss. Same identity + same band ⇒ hit** (Set C, as refined by this ruling).
  Deeper decay crosses a band edge ⇒ new key ⇒ re-reconstruction on thinner detail ⇒ the
  **progressive pre-demo drift trajectory** despite the static seed-only identity — the 60-day
  beat's mechanism.
- **Eviction invariant (standing, generalized):** cache writes happen only in the reconstruction
  path; **any other writer to a chain — correction, diegetic write, deferred-enrichment completion
  (2026-08-12, every completion shape including facts-only; this line missed the C1 member until
  the F0 audit, 2026-08-26 — architecture.md §7 had it), purge — evicts all cache rows
  for that memory_id** (application code, not triggers). The authorial endpoint inherits
  this obligation (built 2026-07-18); **purge honors it too (C6, 2026-08-18)** — the per-memory
  DELETE removes the memory's `reconstruction_cache` rows outright, as an ordered step of the
  cascade rather than a separate eviction.

## Write-back & drift budget

> **Scope note (R7 resolved 2026-08-12; the dated entry in `decisions.md`):** the budget below
> is a **topic guard** against wholesale nonsense and topic-swaps, not a fact guard — the
> stage-4 ablation measured it blind to fact-level drift (unconstrained retellings sailed
> equally far under the threshold while gist-precision dropped 0.834 → 0.704). Factual
> faithfulness is policed by the fixed gist constraint + gist-precision (fact survival) and
> the judged faithfulness category. Mechanism and threshold unchanged by the ruling.

On a cache miss, after the call returns a candidate retelling:

1. **Drift check.** Embed the candidate and the **anchor** and measure distance. The anchor is
   derivable, no pointer (register): the latest chain row with `write_cause` in
   {`original`, `authorial_correction`, `update_with_resentment`, `enrichment`} *(the fourth
   member since migration 006; C4's ruling-8 doc pass fixed architecture.md §7 but missed this
   parallel line — closed at the F0 audit, 2026-08-26)*. Both texts embed **at check
   time** — `memory_details` has no embedding column (frozen schema), and `memories.embedding`
   embeds `observation_text`, not the rendered head. `[SETTLE-AT-BUILD]` metric + knob —
   suggested cosine distance (the HNSW opclass) against integrator knob `drift_budget_threshold`
   (`agents.config` — migration 01 named it there from day one).
2. **Within budget → persist, then serve.** One transaction: insert the new head
   (`write_cause = reconstruction`), supersede the prior (`invalid_at`), insert the cache row.
   `[SETTLE-AT-BUILD]` the new row's `valid_at` — suggested the scene reference time (the
   retelling's world time; honors `as_of` time travel).
3. **Past budget → refuse the write, keep the prior head** (architecture §7). Serve the live
   head; `read_mode` stays honest to the served row (`reconstructed` if that head is a
   reconstruction row, else `verbatim`); count it (`drift_refusals`). `[SETTLE-AT-BUILD]` —
   suggested: cache the *served prior text* under the current key so subsequent same-key reads
   are stable and call-free (the reconstruction path is the cache's one writer; refusal is
   inside it).
4. **Re-anchoring by cause** (settled, register): authorial → the corrected head;
   update-with-resentment → the new head; rationalization → **never** (crystallization — "the
   story has set"). Reconstruction rows never re-anchor. Event-driven writes (both diegetic
   paths) are exempt from the budget.

**Serve only persisted text.** The served item is always a committed row (cache hit, or the row(s)
just committed, or the refusal's live head). A real model's response that failed to persist is
never served — unpersisted text could not be reproduced by the next read, silently breaking
within-scene stability.

## Degradation ladder (reconstruction)

| Condition | Behavior |
|---|---|
| reconstruction call fails (or an item's output is unsalvageable) | **fail-quiet, never-blank:** serve the live head for the affected item(s), `read_mode` honest to the served row, `degraded = true` + reason; **no write-back, no cache write** for those items. `[SETTLE-AT-BUILD]` retry — suggested single attempt (this is read-latency, not a lost write). |
| drift-check embedding fails | **fail-closed on the write:** refuse the write-back (treat as past-budget), serve the live head, reason in instrumentation. Never admit unbudgeted drift on a blind check. |
| persistence transaction fails | serve the live head, `degraded = true` — the serve-only-persisted-text rule; the next read simply retries the miss. |
| request names an unknown `identity_version` | contract error, loud (broken caller, not a flaky model). |
| no `identity_version` on the request | not degradation — the lazy bootstrap path (above), flagged in instrumentation. |
| retrieval-stage degradation (query-embedding down) | unchanged from read v1 (fail-quiet candidate ranking); serving proceeds normally on the degraded candidate set. |

## Instrumentation (rides the retrieval seam)

Result-level additions, `[SETTLE-AT-BUILD]` exact field names: reconstruction call timing +
input/output token counts (feeding the per-100-turn cost table), batch size, `cache_hits` /
`cache_misses`, `write_backs`, `drift_refusals`, lazy-bootstrap flag. Per-item: `read_mode` is
already in the payload; the debug view (`render_debug`) grows the reconstruction counters. The
load driver's aggregate table gains the reconstruction terms (`[SETTLE-AT-BUILD]` shape). No gate
term — the gate is item 1 (renumbered 2026-07-18; specced & built 2026-07-19,
`mid-dialogue-gate.md` — the term landed at its build).

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

**All ruled 2026-07-17 with the build plan** (dated "Reconstruction build rulings" entry in
`decisions.md`; the two genuine forks were ruled via explicit questions):

- **Theta knob** — **ruled as suggested:** `reconstruction_theta`, default 0.5 (strength below
  theta reconstructs), service default + per-agent override.
- **Band quantum + key composition** — **ruled as suggested:** `reconstruction_band_quantum`
  0.25; `{identity_version}|b{index}`; thinning level = the band's midpoint strength; band index
  capped at the last band.
- **Thinning function** — **ruled as suggested:** deterministic + monotone — sentence-granular
  prefix retention per contiguous non-gist segment (`(?<=[.!?])\s+`, retain `ceil(level × n)`,
  min 1), proportion = the band's level. No spaCy on the read path.
- **Reconstruction prompt block shape + batched output schema** — **ruled as suggested:**
  JSON-in-text keyed by memory_id (items sorted by memory_id for byte-stability); per-item
  salvage; pure-function assembly (`assemble_reconstruction_prompt`).
- **Retry policy** — **ruled as suggested:** single attempt, fail-quiet.
- **Drift metric + knob default** — **ruled (explicit questions):** cosine distance;
  `drift_budget_threshold` default **0.35**; and the calibration surfaced a genuine fork —
  **`FakeEmbeddingProvider` rewritten locality-sensitive** (trigram-bucket, L2-normalized), since
  the hash fake made any two texts ~orthogonal and would have refused every fake-mode write-back.
- **Write-back `valid_at`** — **ruled as suggested:** the scene basis; the superseded head's
  `invalid_at` is the same basis (coherent chain timeline under time travel).
- **Refusal caching** — **ruled as suggested**, with a build-surfaced carve-out: a drift-check
  **embedding failure** (blind check) refuses but does NOT cache, so a transient outage never
  permanently pins a key.
- **Scene-state request fields** — **ruled as suggested:** `identity_version` +
  `scene_started_at` on `DialogueInitRequest`, pass-through on `DialogueTurnRequest`; the
  session-runner freezes both at `:scene` (and at `create()`, an implicit scene start).
- **Scene-boundary response shape** — **ruled:** adds `identity_version` +
  `identity_document_new` (additive defaults).
- **Hash algorithm / NULL-seed document / unknown-version error shape** — **ruled:** sha256 full
  hex; empty render + omitted prompt block; `UnknownIdentityVersionError` → **422** at the route.
- **Wire-model + instrumentation deltas** — **ruled as listed:** `read_mode` literal widens to
  `reconstructed` (`reconstruction_pending` stays **unadopted** — async is not the design);
  result fields all defaulted, incl. `identity_version_effective` + `identity_bootstrapped`.
- **Walker shape** — **ruled:** `tests\verify_reconstruction.py`, 41 assertions, scratch-DB
  pattern per the prior walkers — which pin `reconstruction_theta = 0` in their fixture configs
  (build-surfaced shape; see the register entry).

## Done when

- **Theta boundary (fake providers, scratch DB).** Seeded memories straddling theta (injected
  `valid_at` / scene basis): fresh → `read_mode = verbatim`, original head served; past theta →
  `read_mode = reconstructed`, rendered text served; the boundary respects the knob.
- **Write-back chain shape.** The first past-theta read inserts exactly one new head
  (`write_cause = reconstruction`, `invalid_at IS NULL`), supersedes the prior row, same
  `memory_id`; `observation_text` and gist rows byte-identical before/after.
- **Cache hit is call-free.** A second read at the same composed key serves byte-identical text
  with zero reconstruction calls and zero new chain rows; an identity bump (seed change +
  boundary) misses; a band crossing (deeper decay at the next boundary) misses and re-reconstructs
  on thinner detail.
- **Byte-identity per key.** Same `(memory_id, composed key)` ⇒ byte-identical served text,
  across scenes (Set C).
- **Within-scene stability by construction.** Two reads in one scene are byte-identical even when
  wall-clock advances across a band edge mid-scene (the frozen basis holds).
- **Pin exclusion.** A pinned memory past theta-age never grows a chain row and always serves
  verbatim.
- **Drift refusal.** A failure-injection fake emitting an over-threshold candidate → no new chain
  row, prior head served, `drift_refusals` counted; the anchor resolves per the derivable rule.
- **Prompt assembly is assertable.** The pure assembly function shows gist byte-equal to the
  observation spans, thinning monotone across bands, and the live head included — no model call.
- **Serve-only-persisted-text.** The served reconstructed content equals the committed live head
  and the committed cache row.
- **Scores untouched by the swap.** For an identical store, score components equal read-path v1's
  (retrieval and scoring stages unchanged).
- **Degradation.** Per the ladder: a failing reconstruction provider yields live-head items with
  honest `read_mode` + `degraded = true` and writes nothing; a failing drift-check embedding
  refuses the write.
- **Identity plumbing.** The scene-boundary response carries `identity_version`; the
  session-runner freezes and passes it; a bare read lazy-bootstraps and flags it.
- **Schema frozen.** No new migration; `db\migrate.py` no-arg is still a clean no-op on `longmem`.
- **Floors intact.** All three prior walkers re-run clean (35/35, 34/34, 36/36).
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and recorded in
  `decisions.md`.
