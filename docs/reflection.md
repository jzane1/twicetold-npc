# Reflection — Phase C2 build target

Formed beliefs over lived episodes: the reflect verb samples an agent's live memories by
importance × recency, writes conclusions **grounded in cited `memory_id`s** to the
`reflections` table, guards the identity revision with a non-LLM **repetition detector**
(RRR), folds identity-relevant beliefs into the **rendered identity document** (which the
dialogue prompt moves onto), and **prunes the identity-components table** with
constraint-follows-liveness teeth. Design truth: [architecture.md](architecture.md) §10
(amended 2026-08-15) plus §2/§4.2–4.3/§7; the rulings are the dated 2026-08-15 C2 entries
in `decisions.md`; the research grounding is `docs\research\FINDINGS.md` #4.
This doc points, it does not re-derive.

> **Status: BUILT + floor-verified 2026-08-15 — specced, built, and independently
> verified the same date (three sittings; the three dated C2 entries in `decisions.md`,
> the build record included).** Landed: `app\reflection.py`, migration 007
> (`reflection_runs`), suite Set L (20 scenarios, all unmarked), the ninth walker
> `tests\verify_reflection.py` (60/60), the dialogue-seam move, the C# mirror + four
> interop-gate beats (24 → 28), all nine walkers green with write/read byte-identical at
> 53/56 (the zero-retrieval-change evidence), and the post-landing believability run
> (real-mode smoke vs the 2026-08-07 baseline: checks 6/0 both, no regression). The
> independent floor-verifier returned **pass**; floors row 26. The `[SETTLE-AT-BUILD]`
> ledger below was ruled at the build plan — the build record in `decisions.md`.

## The six dossier rulings (2026-08-15, first sitting — pointers, not re-derivation)

1. **Scheduling composes**: the endpoint is the verb; an optional sibling
   `ReflectionWorker` (C1 lifecycle contract) pulls the same seam, **default OFF**.
2. **The `reflections` table is the sole durable home** — identity ingredient + C3
   feedstock; never a retrieval candidate; citations in `source_memory_ids`.
3. **Identity package**: model-free concatenative render; refresh = LLM **consolidation
   reflection** bi-temporally absorbing what it summarizes; **the dialogue prompt moves
   onto the rendered document**. Parity: zero reflections ⇒ byte-identical prompts.
4. **Component trim gets teeth**: reconstruction's gist constraint follows component
   liveness; trim-driven cache eviction is the **fourth sanctioned mid-scene text-change
   cause** (invariant text amends with this build).
5. **RRR is a guard**: at/above threshold the reflection stores but the identity
   consolidation is blocked and flagged. RRR is self-repetition among the agent's own
   reflections — NOT the cut cross-memory conflict/staleness detection.
6. **`TWICETOLD_MODEL_REFLECTION` is judge-shaped**: loaded both modes, required by
   neither, loud at the first real reflect call.

## The spec rulings (2026-08-15, second sitting)

Rulings 1, 3, and 4 took the recommended option; ruling 2 was **ruled against the
recommendation** (the model-in-the-loop shape was presented first and declined — recorded
honestly, per the register discipline).

1. **Consolidation trigger — automatic threshold + explicit override.** After a reflect
   call's writes land, consolidation runs when the count of live identity-relevant
   reflections ≥ `reflection_consolidate_at` (RRR-guarded). The request's optional
   `consolidate` field overrides: `true` forces the stage this call (RRR still guards),
   `false` suppresses it, absent = the knob decides. **Rejected:** explicit-only (the
   "periodic refresh" promise then depends entirely on integrator diligence, and the
   worker could never consolidate); every-reflect (the document never accumulates distinct
   beliefs; consolidation churn and model cost on every call).
2. **Trim criteria — PURELY MECHANICAL (ruled against the model-in-the-loop
   recommendation).** No model touches the prune decision; the rule is SQL + the sample
   list, executed by the reflect verb (so §10's "reflection prunes" stays true in the
   scheduling sense — the verb runs the rule; the selection carries no judgment). The
   concrete rule and its guardrails are specced in "Component trim and eviction" below;
   the risk the recommendation guarded (a tripwire-valuable component pruned without
   judgment) is mitigated mechanically by the staleness window, the active-evidence
   protection, and the authored-component exemption — all knob- or rule-visible, none
   model-dependent. **Rejected:** model-proposed from mechanically-derived candidates
   (the recommendation: judgment grounded in a mechanically-safe candidate set — declined
   with its cost heard); model-unrestricted (an ungrounded prune of durable content is
   the confabulation shape the dossier was built to avoid).
3. **Eviction scope — per-affected-memory.** Trim evicts `reconstruction_cache` rows
   only for `memory_id`s having at least one gist span whose `matched_component_id` was
   pruned this call. **Rejected:** agent-wide (simpler SQL, but evicts unrelated
   memories — a wider fourth-cause mid-scene exposure and re-reconstruction cost for
   rows the trim never touched).
4. **C# mirror lands with this build.** `NpcMemory.Core` gains the reflect verb + result
   models field-for-field (the eval fork-1 "Mirror" precedent keeps the 1:1 attestation
   true); the console-harness gate extends. **Rejected:** a dated exemption deferring to
   C5 (the attestation would carry an exception for a phase, and C5's scope grows).

## Principles this build honors

- **Non-destructive**: reflections are bi-temporal rows; consolidation absorbs by
  `invalid_at`, never rewrite; trim invalidates components, never deletes;
  `agents.seed_identity` is never UPDATEd; `identity_documents` only gains rows.
- **Nothing integrator-configurable hardcoded**: the full knob slate below, all in
  `SERVICE_DEFAULTS` under the `agent_knob` contract.
- **Determinism where tests stand**: top-k sampling (never a lottery), pure prompt
  assembly, content-hash versions, a no-timer worker entry.
- **Instrument at the seam**: the endpoint rides its response payload; the worker
  persists `reflection_runs` (a background seam has no payload).
- **Degradation named per call**: the reflect call is fail-loud (derived work — nothing
  is lost by refusing to store a failed derivation); consolidation failure is soft (the
  escalation precedent); the worker is catch-log-continue.
- **Zero retrieval changes** (dossier ruling 2): `app\retrieval.py` untouched, byte-parity.

## Scope boundary — do NOT build

The cut list by name (2026-08-04): graph/associative memory, recall-reinforced decay,
automatic cross-memory conflict/staleness detection, habituation, the Whisper hook, the
dormant-agent overseer (the worker must not grow wake triggers or cross-agent
orchestration), the full modulator suite. Banked, not committed: persona-lensed routing,
hierarchical consolidation, calibrated trait uncertainty. **C3 is not built here** — only
its contract (below) is left standing. **No eval-harness changes**: the post-landing
believability run uses the existing scenario suite unchanged (reflection defaults OFF and
the seam moves carry parity contracts, so the run is meaningful as-is); a reflect event
kind in the runner schema and a reflection-ON believability arm are Phase D material. No
new read route (the gauge's standing surface is C5's agent-state read, where the
unscored-carve-out ruling belongs — **BUILT and ruled 2026-08-17**:
`GET /v1/agents/{id}/state`, the fourth member). Nothing ships default-ON.

## The reflect verb

**`POST /v1/agents/{agent_id}/reflect`** — an agent-scoped operator/integrator verb
(`/v1/events/*` stays diegetic; the correction-route precedent). Stateless, like every
route. The REPL gains a `:reflect` meta-command (the CLI stays the debug surface).

**Request** (`ReflectRequest`): `client_timestamp: datetime` (tz-aware, validated like
`SceneBoundaryEvent` — becomes the written rows' `valid_at`); `consolidate: bool | None`
(spec ruling 1). Nothing else — sampling, thresholds, and cadence are knobs.

**Pipeline** (one service seam, `ReflectionService.reflect`, used identically by the
route, the REPL, and the worker):

1. Verify the agent loudly (404), resolve the current rendered identity document.
2. **Sample** (below). Below `reflection_min_episodes` → **409**, nothing written.
3. Compute the **mechanical trim set** (spec ruling 2; the rule below) — no model input.
4. **One reflect model call** (prompt below). Provider/parse failure → **502**, nothing
   written (worker: a `failed` run row).
5. **Mechanical validation**: per conclusion, `source_memory_ids` non-empty AND ⊆ the
   sampled ids, else dropped and counted (`dropped_ungrounded`); a non-empty model output
   whose conclusions ALL drop is a malformed-class failure → **502**, nothing written. A
   genuinely empty conclusion list is a valid outcome (thin evidence concludes nothing).
6. **RRR** (below) over the surviving conclusions.
7. **The write transaction**: insert `reflections` rows (`valid_at` = request timestamp);
   invalidate pruned components; evict caches per spec ruling 3. Then re-render + upsert
   the identity document (`ensure_identity_document`, extended render).
8. **Consolidation stage** — runs when due (spec ruling 1) and not RRR-blocked: a second
   model call conditioned on the prior document + the live identity-relevant reflections
   + the immutable seed; output = ONE identity-relevant reflection whose
   `source_memory_ids` is the union of the absorbed rows'; its transaction inserts it and
   invalidates the absorbed rows; the document re-renders again. Failure here is SOFT:
   `consolidation_failed` flags, everything from step 7 stands.
9. The response carries the final `identity_version`.

Exact transaction boundaries and the module split inside `app\reflection.py` are
`[SETTLE-AT-BUILD]`.

**Errors**: 404 unknown agent · 409 below the episode floor · 422 malformed request
(pydantic; naive timestamp) · 502 reflect-call failure / malformed output / all-ungrounded
(nothing written) · `ConfigError` (real mode, var missing) surfaces loud at first use.

**The IDs+scores invariant**: reflect is a write endpoint; the weighted sampling draw is
not the retrieval seam and produces no relevance scores. Sampled and cited ids ride the
response as grounding evidence, unscored by nature.

## Sampling

- **Pool**: the agent's live memories (`memories.invalid_at IS NULL`) joined to the live
  telling head. **Pinned rows included** (pin = decay exemption + reconstruction
  exclusion, exactly two meanings — reflection is neither).
- **Score** = `importance_norm × recency`, reusing THE decay module (`app\decay.py`):
  `importance_norm` = `clamp(COALESCE(importance_raw, importance_neutral),
  importance_norm_floor, 1.0)` (the read path's normalization; NULL-importance pending
  rows take the neutral fallback — the C1 window precedent); `recency` =
  `exp(-age/tau_effective)` with `tau_effective` from `resolve_tau_base` +
  `decay_k_importance`, age measured `now − valid_at`.
- **Draw**: deterministic **top-`reflection_sample_k`** by score, ties on `memory_id`
  (the house tie rule). "Weighted by importance × recency, not recent-N" (ruled) — a
  weighted deterministic ranking, never a lottery: the walkers assert on it.
- **Sampled text**: the **live telling head** — the character concludes from how they
  currently tell it (the reconstruction prior-head precedent; the eval harness can still
  diff belief against ground truth via the record).

## The reflect prompt and provider

- `assemble_reflection_prompt(identity_document, items) → (system_prompt, user_content)`
  — a **pure function**, byte-stable for identical inputs (walker-assertable without a
  DB or model): items sorted by `memory_id`, each `{memory_id, telling, importance,
  valid_at}`; the identity block omitted for an empty document (the NULL-seed rule).
  The prompt carries NO trim content — pruning is mechanical (spec ruling 2), so the
  model never sees or proposes prunes.
- **Output contract** (strict JSON-in-text, the reconstruction precedent):
  `{"reflections": [{"content": str, "identity_relevant": bool,
  "source_memory_ids": [uuid…]}]}`.
- **Provider**: `ReflectionProvider` protocol + `FakeReflectionProvider` (deterministic,
  cites the first sampled ids) + failing/malformed fake variants + `RealReflectionProvider`
  reading `settings.model_reflection`. **Standalone factory** `build_reflection_provider`
  (the judge shape): NOT a field on the frozen `Providers` bundle; the service builds it
  lazily at first use and raises `ConfigError` in real mode without the var. Pricing:
  `TWICETOLD_PRICE_REFLECTION_IN/OUT` join `PRICE_ENV_KEYS`. Full add-a-role checklist at
  build (`ENV_MODEL_REFLECTION`, the `load_env` allowlist, the `Settings` field,
  `.env.example` role + price blocks, conftest fakes, the CLAUDE.md/architecture §3 role
  text — already annotated with the ruled shape).

## The RRR guard

Per surviving conclusion, `rrr_i` = max `SequenceMatcher.ratio(new.content,
prior.content)` over the agent's most recent `reflection_rrr_window` **live** reflections;
call-level `rrr` = max over conclusions, `None` when no priors exist. Non-LLM by
construction. `rrr ≥ reflection_rrr_threshold` ⇒ the consolidation stage is suppressed
this call and `rrr_blocked_consolidation` flags; the reflections still store (honest
evidence of the agent's state). Always reported (response + run rows).

## Identity render, consolidation, and the dialogue seam

- **Render** (`render_identity_document`, extended in place — `app\identity.py` was
  written for this): `seed prose + "\n\n" + each live identity-relevant reflection's
  content`, ordered `valid_at, created_at, reflection_id` (stable chronology), joined
  `"\n\n"`. No template (the reconstruction ruling: a template is a hidden authorial
  artifact). Stays **pure**; `identity_version` = sha256 of the rendered text, exactly as
  today. `ensure_identity_document` fetches the live identity-relevant contents itself —
  both existing call sites (the scene-boundary handler, `SessionRunner.create`) keep
  their shape. `identity_relevant IS NULL` counts as not identity-relevant (the write
  always sets it explicitly).
- **Zero reflections ⇒ the render is seed-verbatim ⇒ every existing hash, cache key,
  prompt, and floor holds** — the parity contract the re-verifications assert.
- **Consolidation** is pipeline step 8 above. The absorbed rows stay queryable
  (superseded, never deleted); provenance flows through by source-union. A version bump
  "invalidates" reconstruction caches **by key construction** (the composed key) — no
  deletion; **trim is the one case that must evict** (same key, changed constraint).
- **The dialogue seam moves**: the prose prompt's identity block becomes the rendered
  document for the request's **caller-frozen `identity_version`**, resolved exactly like
  reconstruction's (present → fetch, unknown → 422; absent → lazy ensure). The raw
  `state.seed_identity` argument at `app\dialogue.py:311` leaves the prompt path.
  Re-opens the dialogue-seam floors; their walkers re-run at build (a step, not a cost).

## Component trim and eviction

- **The mechanical rule** (spec ruling 2 — SQL + the sample list, zero model input). A
  live component is pruned by this reflect call iff ALL of:
  1. **It has span evidence at all** — at least one `memory_gist_spans` row matches it.
     Zero-span components are authored (provisioning-seeded; escalation always creates
     the component WITH its mention span), and authored identity is operator intent —
     mechanically pruning it would be auto-deleting seed content. Exempt.
  2. **All its evidence is stale** — no live memory carrying a span matched to it has
     `valid_at` within `reflection_trim_stale_seconds` of now.
  3. **It is not active evidence** — no memory in THIS call's sample references it (a
     formative old memory can be low-recency yet high-importance enough to sample; its
     components are in active use and never pruned by the call that sampled them).
  `reflection_trim_stale_seconds` = 0.0 **disables the trim entirely** (the
  `gate_enabled` kill-switch shape). Deliberately NO pinned-memory clause: pin means
  exactly two things (decay exemption, reconstruction exclusion) — a trim guard would
  be a third meaning, and the ruled two-meanings contract outranks it.
- **Prune** = `invalid_at` on the component row (001's comment: invalidates, never
  deletes). Pruned ids and eviction counts ride the response
  (`pruned_component_ids`, `evicted_cache_rows`) — mechanical outcomes, fully
  walker-assertable with a frozen clock.
- **Constraint-follows-liveness** (dossier ruling 4): `fetch_reconstruction_sources`
  gains the liveness join — spans whose `matched_component_id` is invalidated drop out
  of the gist constraint; spans with NULL `matched_component_id` are untouched. With no
  trimmed components the sources are byte-identical (the reconstruction walker's parity
  assertion).
- **Eviction**: per spec ruling 3, inside the write transaction. The gate needs no
  change — `fetch_live_components` already follows liveness; the tripwire set shrinks
  (the `mid-dialogue-gate.md` "only grows" note expires at this build).
- **The invariant amendment lands with this build**: reflection-driven eviction becomes
  the fourth sanctioned mid-scene text-change cause in CLAUDE.md and architecture §7's
  writer list (reflection-trim joins correction/diegetic/enrichment/purge). Integrator
  guidance, stated in docs: reflect at scene edges and the exposure window vanishes.

## The worker

`ReflectionWorker(pool, providers, settings)` in `app\reflection.py`, delegating to the
SAME service seam the route calls — one implementation. C1's lifecycle contract verbatim:
constructed + started at **both** sites (`app\api.py` lifespan beside the deferred
worker; `SessionRunner.create`), `stop()` (cancel + await) before the pool closes,
poll loop catch-log-continue, and **`sweep(limit=None)` as the deterministic no-timer
entry** (tests and walkers call it directly).

Per sweep: scan agents, resolve `reflection_worker_enabled` per agent (`agent_knob` —
the per-agent kill-switch gates the WORKER's auto-pull only; the endpoint always works),
compute pressure for enabled agents, reflect those at/above
`reflection_pressure_threshold` — at most one reflect per agent per sweep, at most
`reflection_worker_batch` agents per sweep. **No attempts ledger**: a failed reflect
writes a `failed` run row and the pressure that triggered it persists, so the next sweep
retries naturally (the deliberate contrast with enrichment's budget — stated, not
accidental).

## The pressure gauge

`pressure = Σ COALESCE(importance_raw, importance_neutral)` over the agent's live
memories with `created_at` later than the agent's most recent reflection's `created_at`
(any reflection row, live or absorbed — the last reflect EVENT; all live memories when
none exists), divided by `reflection_pressure_norm`. One SQL aggregate, computed on
demand, **never stored** (architecture §2's runtime-state rule); served as
`pressure_before` / `pressure_after` on the reflect response and used identically by the
worker's threshold check — one implementation. `created_at`, not `valid_at`: pressure is
service bookkeeping (unprocessed accumulation), not world time. The standing read
surface for the gauge is C5's agent-state route (recorded dependency; no route here —
**BUILT 2026-08-17**: `GET /v1/agents/{id}/state` serves it as `reflection_pressure`,
same implementation, same loud norm guard).

## Degradation ladder (reflection)

| Event | Endpoint | Worker |
|---|---|---|
| below episode floor | 409, nothing written | not reached (pressure implies volume) — skip, no run row |
| reflect call fails / malformed / all-ungrounded | 502, nothing written | `failed` run row; retried naturally next sweep |
| some conclusions ungrounded | stored valid subset; `dropped_ungrounded` counts | same; count on the run row |
| model concludes nothing (empty list) | 200, zero rows, honest | `completed` run row, zero written |
| consolidation call fails | SOFT: `consolidation_failed`, step-7 writes stand | same, flagged on the run row |
| `TWICETOLD_MODEL_REFLECTION` missing (real) | `ConfigError`, loud, nothing written | log loud once; worker keeps running, run row `failed` |

Every rung is a Set L scenario or walker criterion.

## Knobs (all in `SERVICE_DEFAULTS`, floats, `agent_knob` contract)

| Knob | Default | Meaning |
|---|---|---|
| `reflection_worker_enabled` | **0.0** | Per-agent worker kill-switch; 0.0 = the worker never auto-reflects this agent. The endpoint is always live regardless. |
| `reflection_poll_seconds` | 60.0 | Worker sweep interval. Process-level (the deferred-worker precedent; an `agents.config` override is inert by design). |
| `reflection_worker_batch` | 4.0 | Max agents reflected per sweep (int at the call site) — a cost bound, not a queue. |
| `reflection_pressure_threshold` | 1.0 | The worker pulls at/above this pressure. |
| `reflection_pressure_norm` | 10.0 | The divisor defining what pressure 1.0 means (≈ the importance mass that should trigger reflection). |
| `reflection_sample_k` | 16.0 | Episodes sampled per reflect (int at the call site). |
| `reflection_min_episodes` | 4.0 | Below this live-episode count the verb 409s (int at the call site). |
| `reflection_rrr_threshold` | 0.85 | RRR at/above blocks consolidation (the paper default). |
| `reflection_rrr_window` | 8.0 | Recent live reflections compared for RRR (int at the call site). |
| `reflection_consolidate_at` | 5.0 | Live identity-relevant count that triggers consolidation (int at the call site). |
| `reflection_trim_stale_seconds` | 2592000.0 | The trim staleness window (30 days): a component prunes only when all its span evidence sits on live memories older than this. **0.0 disables the trim entirely** (kill-switch shape). |

## Migration 007 — `reflection_runs`

The worker's persisted per-run accounting (endpoint runs ride the response payload — the
C1 split exactly): `run_id` PK · `agent_id` NOT NULL FK → agents · `outcome` CHECK
(`completed` | `failed`) · `error` · `reflections_written` · `dropped_ungrounded` ·
`consolidation_ran` · `consolidation_failed` · `rrr` · `rrr_blocked` ·
`pruned_components` · `evicted_cache_rows` · `pressure_before` / `pressure_after` ·
per-stage timings (`reflect_ms` / `consolidation_ms` / `insert_ms` / `total_ms`) · token
columns (`reflect_input/output_tokens`, `consolidation_input/output_tokens`) ·
`created_at` — column types copy migration 006's idioms (`[SETTLE-AT-BUILD]`); plus
`reflection_runs_agent_id_idx`. No other schema change: the `reflections` table (001)
carries the mechanism as built. The three mechanical pins bump: the gate walker's ledger
list + criterion string (adds `007_reflection.sql`), the eval-runner migration count
(6 → 7), the table census (12 → 13, `reflection_runs`).

## Instrumentation and wire

**`ReflectResult`** (the seam's payload, route-passthrough by the house rule):
`agent_id` · `reflections: list[ReflectionOut]` (`reflection_id`, `content`,
`identity_relevant`, `source_memory_ids`) · `sampled_memory_ids` · `dropped_ungrounded` ·
`rrr: float | None` · `rrr_blocked_consolidation` · `consolidation: ConsolidationOut |
None` (`reflection_id`, `absorbed_reflection_ids`, `failed`) · `pruned_component_ids` ·
`evicted_cache_rows` · `pressure_before` / `pressure_after` · `identity_version` ·
`identity_document_new` · `instrumentation: ReflectInstrumentation` (`reflect_ms`,
`consolidation_ms`, `insert_ms`, `total_ms`, the four token counts). Exact field names
`[SETTLE-AT-BUILD]` within this shape.

**C# mirror** (spec ruling 4): `NpcMemory.Core` gains the reflect call + models
field-for-field; both projects build 0-warning; the console-harness gate extends. The
Ledger's reflection surface and any reflections inspector read stay OUT (C5's
neighborhood — unscored-carve-out territory with its own ruling; **ruled and built
2026-08-17**: the agent-state read carries the live-beliefs list — the Ledger page itself
stays E2 polish).

## The C3 contract (what this build leaves standing)

Stable addressable `reflection_id` (the compiler's cache-key component); **bi-temporal
reflection invalidation doubles as compiler-cache eviction** (consolidation and any
future supersession set `invalid_at`, never delete); `content` + `identity_relevant` +
`source_memory_ids` are the compilable surface. Carried caution for C3's own spec: a
compiled parameter layer amplifies like a confabulated rule library (the honest-lying
ExpeL note) — C3 budgets its own staleness guard; RRR here is the upstream half.

*(C3 BUILT 2026-08-17 on exactly this contract — `parameter-compiler.md`: the eviction
rides liveness-by-join with zero bundle writes, the three-field surface is consumed
verbatim, and the staleness guard landed as the all-mechanical K-window + liveness +
clamps trio.)*

## Verification

- **Suite Set L** (`tests\test_reflection.py`, ~13 scenarios, mostly unmarked — fixtures
  seed memories/reflections at the db layer; the service is exercised through the seam
  and `sweep()`, no timers): the endpoint happy path (citations ⊆ sampled, bi-temporal
  rows); grounding enforcement (partial drop; all-ungrounded → 502 nothing written);
  the empty-conclusion valid outcome; the 409 floor; the RRR guard (near-identical
  fixture blocks consolidation, reflection still stores); consolidation (absorbs by
  `invalid_at`, source union, version bump, document gains the belief); trim (the mechanical
  rule under a frozen clock: stale-window prune fires, the active-evidence and
  authored-component exemptions hold, 0.0 disables, per-affected eviction, gate set
  shrinks, reconstruction sources drop trimmed spans, no-trim parity); the dialogue seam
  (zero-reflection byte-parity + a reflection visible in the `[identity]` block after
  recompile); worker lifecycle + sweep determinism + per-agent kill-switch + the
  no-attempts retry semantics; pressure math; the role load shape (real mode loads
  WITHOUT the var — the Set I amendment — and the first real reflect without it raises
  `ConfigError` naming it); route contracts (success + 404/409/502).
- **The ninth walker** `tests\verify_reflection.py` (the Set K walker template: lettered
  fail-fast sections) — A. migration 007 shape · B. the reflect verb ladder ·
  C. render/consolidation/dialogue-seam parity · D. trim + liveness + eviction ·
  E. worker lifecycle at both construction sites · F. role/config shape. Inherits the
  walkers' carried shared-scratch-DB limitation (not fixed here).
- **Touched floors re-verify** (a step, never an argument): the dialogue-seam floors
  (prose-prompt assembly) and reconstruction's (constraint inputs) — their walkers
  re-run; the write-path and read-path walkers' byte-identical passes are the
  zero-retrieval-change evidence.
- **The standing Phase C check**: after landing, a harness believability run on the
  existing scenario suite confirms no regression (reflection defaults OFF; the seam
  moves carry parity contracts, so the run is meaningful unchanged).
- **Docs at build**: test-suite.md gains the Set L section + the Set I amendment;
  `docs\README.md`'s row gains migration 007; CLAUDE.md + architecture §7 take the
  fourth-cause amendment; `mid-dialogue-gate.md:174`'s "only grows" note gets its
  expiry annotation; `.env.example` gains the role + price lines.

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

Exact SQL text and transaction boundaries (steps 7–8) · `reflection_runs` column types
(copy 006) · exact pydantic field names within the ruled response shape · the
`app\reflection.py` module split if it grows · the REPL `:reflect` flag surface · the
worker's agent-scan query shape · error-string taxonomy · Set L's exact scenario count
and the walker's criterion count.

## Done when

1. **Reflect happy path.** POST reflect (fake providers, agent ≥ floor) → ≥1
   `reflections` rows, each `source_memory_ids` non-empty and ⊆ the response's
   `sampled_memory_ids`; `valid_at` = the request timestamp; bi-temporal columns
   present; the response carries pressure before/after and honest instrumentation.
2. **Grounding is enforced mechanically.** A fake emitting one grounded + one ungrounded
   conclusion stores exactly the grounded one (`dropped_ungrounded` = 1); the
   all-ungrounded variant is a 502 with zero rows written.
3. **The floor is loud.** Below `reflection_min_episodes` → 409, zero rows.
4. **RRR guards.** A near-duplicate prior reflection fixture yields `rrr ≥ threshold`,
   `rrr_blocked_consolidation` true, no consolidation, and the new reflection stored.
5. **Consolidation absorbs bi-temporally.** At the trigger count (RRR clear) → one new
   identity-relevant reflection whose sources are the union of the absorbed rows'; the
   absorbed rows carry `invalid_at` and stay queryable; `identity_version` changes; the
   rendered document contains the consolidated belief and not the absorbed ones.
6. **Trim has teeth and stays inside its lane.** Under a frozen clock, a component whose
   entire span evidence is older than the window prunes (`invalid_at`, never DELETE); a
   zero-span (authored) component and a component referenced by the current sample both
   survive; `reflection_trim_stale_seconds` 0.0 prunes nothing; cache rows evict
   per-affected-memory only; `fetch_live_components` no longer returns the pruned
   component; `fetch_reconstruction_sources` drops its spans; with zero trims both are
   byte-identical to pre-build.
7. **Speech sees beliefs; parity holds without them.** With zero reflections the prose
   prompt is byte-identical to pre-build (walker-asserted); after an identity-relevant
   reflection + scene recompile, the `[identity]` block contains it.
8. **The worker is a real sibling.** `sweep()` is deterministic and timer-free; the
   per-agent kill-switch gates auto-pull only; a due agent reflects once per sweep with
   a `completed` run row; a failing reflect leaves a `failed` run row with the worker
   alive and retrying next sweep; constructed + started at both sites and stopped before
   the pool closes.
9. **Migration 007 is clean.** `migrate.py` applies it idempotently; the three pins are
   bumped; the census counts thirteen tables.
10. **The role is judge-shaped in code.** Real mode loads without
    `TWICETOLD_MODEL_REFLECTION`; the first real reflect without it raises `ConfigError`
    naming the var; fake mode runs on `FakeReflectionProvider` end to end.
11. **The record closes.** Set L green in the subset run; the ninth walker passes N/N;
    the dialogue-seam and reconstruction walkers re-run green; the independent
    floor-verifier returns pass before any floors row; the post-landing believability
    run shows no regression.
