# Reflection

Formed beliefs over lived episodes. The reflect verb samples an agent's live memories by importance
and recency, writes conclusions grounded in cited `memory_id`s to the `reflections` table, guards the
identity revision with a non-LLM repetition detector (RRR), folds identity-relevant beliefs into the
rendered identity document (which the dialogue prompt moves onto), and prunes the identity-components
table with constraint-follows-liveness teeth. Design truth is [architecture.md](architecture.md) §10,
with §2, §4.2 to §4.3, and §7. This document describes the mechanism.

The feature ships default OFF at the worker (`reflection_worker_enabled` 0.0 per agent); the reflect
endpoint is always live.

## Principles

- **Non-destructive.** Reflections are bi-temporal rows; consolidation absorbs by `invalid_at`, never
  by rewrite; trim invalidates components, never deletes; `agents.seed_identity` is never updated;
  `identity_documents` only gains rows.
- **Nothing integrator-configurable is hardcoded.** The full knob slate lives in `SERVICE_DEFAULTS`
  under the `agent_knob` contract.
- **Deterministic where tests stand.** Top-k sampling (never a lottery), pure prompt assembly,
  content-hash versions, a no-timer worker entry.
- **Instrument at the seam.** The endpoint rides its response payload; the worker persists
  `reflection_runs`, because a background seam has no payload.
- **Degradation named per call.** The reflect call is fail-loud (nothing is lost by refusing to store
  a failed derivation); consolidation failure is soft; the worker is catch-log-continue.
- **Zero retrieval changes.** `app\retrieval.py` is untouched, with byte-parity.

## Boundaries

Reflection deliberately does not do graph or associative memory, recall-reinforced decay, automatic
cross-memory conflict or staleness detection, habituation, or dormant-agent orchestration (the worker
never grows wake triggers or cross-agent orchestration). Belief influence on speech is a separate
layer, the parameter compiler ([parameter-compiler.md](parameter-compiler.md)); reflection leaves only
that layer's contract standing.

## The reflect verb

`POST /v1/agents/{agent_id}/reflect` is an agent-scoped operator or integrator verb (`/v1/events/*`
stays diegetic). It is stateless, like every route. The REPL carries a `:reflect` meta-command.

The request (`ReflectRequest`) carries `client_timestamp: datetime` (tz-aware, validated like
`SceneBoundaryEvent`, and becoming the written rows' `valid_at`) and `consolidate: bool | None`.
Nothing else: sampling, thresholds, and cadence are knobs.

The pipeline is one service seam, `ReflectionService.reflect`, used identically by the route, the REPL,
and the worker:

1. Verify the agent loudly (404) and resolve the current rendered identity document.
2. Sample (below). Below `reflection_min_episodes`, return 409 with nothing written.
3. Compute the mechanical trim set (the rule below), with no model input.
4. Make one reflect model call (the prompt below). A provider or parse failure returns 502 with
   nothing written (the worker instead records a `failed` run row).
5. Validate mechanically: per conclusion, `source_memory_ids` must be non-empty and a subset of the
   sampled ids, else the conclusion is dropped and counted (`dropped_ungrounded`). A non-empty model
   output whose conclusions all drop is a malformed-class failure, returning 502 with nothing written.
   A genuinely empty conclusion list is a valid outcome (thin evidence concludes nothing).
6. Run RRR (below) over the surviving conclusions.
7. Run the write transaction: insert `reflections` rows (`valid_at` = request timestamp); invalidate
   pruned components; evict caches per the eviction scope below. Then re-render and upsert the identity
   document (`ensure_identity_document`, extended render).
8. Run the consolidation stage when due (below) and not RRR-blocked: a second model call conditioned on
   the prior document, the live identity-relevant reflections, and the immutable seed; the output is one
   identity-relevant reflection whose `source_memory_ids` is the union of the absorbed rows'. Its
   transaction inserts it and invalidates the absorbed rows, and the document re-renders again. Failure
   here is soft: `consolidation_failed` flags, and everything from step 7 stands.
9. The response carries the final `identity_version`.

Errors: 404 unknown agent; 409 below the episode floor; 422 malformed request (pydantic, naive
timestamp); 502 reflect-call failure, malformed output, or all-ungrounded (nothing written);
`ConfigError` (real mode, var missing) surfaces loud at first use.

Reflect is a write endpoint; the weighted sampling draw is not the retrieval seam and produces no
relevance scores. The sampled and cited ids ride the response as grounding evidence, unscored by nature.

## Sampling

- **Pool**: the agent's live memories (`memories.invalid_at IS NULL`) joined to the live telling head.
  Pinned rows are included, because a pin means exactly two things (decay exemption and reconstruction
  exclusion) and reflection is neither.
- **Score** = `importance_norm x recency`, reusing the decay module (`app\decay.py`): `importance_norm`
  = `clamp(COALESCE(importance_raw, importance_neutral), importance_norm_floor, 1.0)` (the read path's
  normalization; NULL-importance pending rows take the neutral fallback); `recency` =
  `exp(-age/tau_effective)` with `tau_effective` from `resolve_tau_base` plus `decay_k_importance`, and
  age measured as `now - valid_at`.
- **Draw**: deterministic top-`reflection_sample_k` by score, ties broken on `memory_id`. Weighted by
  importance and recency, never a lottery; the walkers assert it.
- **Sampled text**: the live telling head, so the character concludes from how it currently tells the
  memory. The evaluation harness can still diff belief against ground truth through the record.

## The reflect prompt and provider

`assemble_reflection_prompt(identity_document, items)` returns `(system_prompt, user_content)` and is a
pure function, byte-stable for identical inputs (walker-assertable without a database or model): items
are sorted by `memory_id`, each `{memory_id, telling, importance, valid_at}`, and the identity block is
omitted for an empty document. The prompt carries no trim content; pruning is mechanical, so the model
never sees or proposes prunes.

The output contract is strict JSON-in-text: `{"reflections": [{"content": str, "identity_relevant":
bool, "source_memory_ids": [uuid...]}]}`.

The provider is the `ReflectionProvider` protocol plus `FakeReflectionProvider` (deterministic, citing
the first sampled ids), failing and malformed fake variants, and `RealReflectionProvider` reading
`settings.model_reflection`. The standalone factory `build_reflection_provider` takes the judge shape:
it is not a field on the frozen `Providers` bundle, the service builds it lazily at first use, and it
raises `ConfigError` in real mode without the var. Pricing keys `TWICETOLD_PRICE_REFLECTION_IN` and
`TWICETOLD_PRICE_REFLECTION_OUT` join `PRICE_ENV_KEYS`.

## The RRR guard

Per surviving conclusion, `rrr_i` is the maximum `SequenceMatcher.ratio(new.content, prior.content)`
over the agent's most recent `reflection_rrr_window` live reflections; the call-level `rrr` is the
maximum over conclusions, or `None` when no priors exist. It is non-LLM by construction. When `rrr >=
reflection_rrr_threshold`, the consolidation stage is suppressed this call and
`rrr_blocked_consolidation` flags, but the reflections still store (honest evidence of the agent's
state). It is always reported (on the response and the run rows). RRR is self-repetition among the
agent's own reflections, not cross-memory conflict detection.

## Identity render, consolidation, and the dialogue seam

- **Render** (`render_identity_document`, in `app\identity.py`): `seed prose` plus `"\n\n"` plus each
  live identity-relevant reflection's content, ordered by `valid_at, created_at, reflection_id` for a
  stable chronology, joined with `"\n\n"`. There is no template (a template would be a hidden authorial
  artifact). The function stays pure, and `identity_version` is the sha256 of the rendered text.
  `ensure_identity_document` fetches the live identity-relevant contents itself, so both existing call
  sites (the scene-boundary handler and `SessionRunner.create`) keep their shape. `identity_relevant IS
  NULL` counts as not identity-relevant (the write always sets it explicitly).
- **Zero reflections** means the render is seed-verbatim, so every existing hash, cache key, prompt, and
  floor holds. This parity contract is what the re-verifications assert.
- **Consolidation** is pipeline step 8. The absorbed rows stay queryable (superseded, never deleted),
  and provenance flows through by source-union. A version bump invalidates reconstruction caches by key
  construction (the composed key), with no deletion; trim is the one case that must evict (same key,
  changed constraint).
- **The dialogue seam** moves so the prose prompt's identity block becomes the rendered document for the
  request's caller-frozen `identity_version`, resolved exactly like reconstruction's (present means
  fetch, unknown means 422, absent means lazy ensure). The raw `state.seed_identity` argument leaves the
  prompt path.

## Component trim and eviction

- **The mechanical rule** (SQL plus the sample list, zero model input). A live component is pruned by
  this reflect call if and only if all of:
  1. **It has span evidence at all**: at least one `memory_gist_spans` row matches it. Zero-span
     components are authored (provisioning-seeded; escalation always creates the component with its
     mention span), and authored identity is operator intent, so mechanically pruning it would be
     auto-deleting seed content. Exempt.
  2. **All its evidence is stale**: no live memory carrying a span matched to it has `valid_at` within
     `reflection_trim_stale_seconds` of now.
  3. **It is not active evidence**: no memory in this call's sample references it (a formative old
     memory can be low-recency yet high-importance enough to sample; its components are in active use
     and never pruned by the call that sampled them).

  `reflection_trim_stale_seconds` = 0.0 disables the trim entirely (the kill-switch shape). There is
  deliberately no pinned-memory clause: a pin means exactly two things, and a trim guard would be an
  unwanted third meaning.
- **Prune** sets `invalid_at` on the component row (it invalidates, never deletes). Pruned ids and
  eviction counts ride the response (`pruned_component_ids`, `evicted_cache_rows`), fully
  walker-assertable with a frozen clock.
- **Constraint-follows-liveness**: `fetch_reconstruction_sources` carries the liveness join, so spans
  whose `matched_component_id` is invalidated drop out of the gist constraint, while spans with a NULL
  `matched_component_id` are untouched. With no trimmed components the sources are byte-identical.
- **Eviction** happens per-affected-memory, inside the write transaction: only `reconstruction_cache`
  rows for `memory_id`s having at least one gist span whose `matched_component_id` was pruned this call.
  Agent-wide eviction is rejected, because it would evict unrelated memories and force re-reconstruction
  for rows the trim never touched. The gate needs no change, since `fetch_live_components` already
  follows liveness, and the tripwire set shrinks.
- Reflection-driven eviction is a sanctioned mid-scene text-change cause (alongside correction,
  diegetic events, enrichment, and purge). Integrator guidance: reflect at scene edges and the exposure
  window vanishes.

## The worker

`ReflectionWorker(pool, providers, settings)` in `app\reflection.py` delegates to the same service seam
the route calls, so there is one implementation. It follows the shared worker lifecycle contract:
constructed and started at both sites (the `app\api.py` lifespan beside the deferred worker, and
`SessionRunner.create`), stopped (cancel then await) before the pool closes, with a catch-log-continue
poll loop and `sweep(limit=None)` as the deterministic no-timer entry that tests and walkers call
directly.

Per sweep it scans agents, resolves `reflection_worker_enabled` per agent (the per-agent kill-switch
gates the worker's auto-pull only; the endpoint always works), computes pressure for enabled agents, and
reflects those at or above `reflection_pressure_threshold`, at most one reflect per agent per sweep and
at most `reflection_worker_batch` agents per sweep. There is no attempts ledger: a failed reflect writes
a `failed` run row and the pressure that triggered it persists, so the next sweep retries naturally.

## The pressure gauge

`pressure = sum of COALESCE(importance_raw, importance_neutral)` over the agent's live memories with
`created_at` later than the agent's most recent reflection's `created_at` (any reflection row, live or
absorbed, i.e. the last reflect event; all live memories when none exists), divided by
`reflection_pressure_norm`. It is one SQL aggregate, computed on demand and never stored (the
runtime-state rule), served as `pressure_before` and `pressure_after` on the reflect response and used
identically by the worker's threshold check. It uses `created_at`, not `valid_at`, because pressure is
service bookkeeping (unprocessed accumulation), not world time. `GET /v1/agents/{id}/state` serves it as
`reflection_pressure` through the same implementation and the same loud norm guard.

## Degradation ladder

| Event | Endpoint | Worker |
|---|---|---|
| below episode floor | 409, nothing written | not reached (pressure implies volume); skip, no run row |
| reflect call fails, malformed, or all-ungrounded | 502, nothing written | `failed` run row; retried naturally next sweep |
| some conclusions ungrounded | stored valid subset; `dropped_ungrounded` counts | same; count on the run row |
| model concludes nothing (empty list) | 200, zero rows, honest | `completed` run row, zero written |
| consolidation call fails | soft: `consolidation_failed`, step-7 writes stand | same, flagged on the run row |
| `TWICETOLD_MODEL_REFLECTION` missing (real) | `ConfigError`, loud, nothing written | log loud once; worker keeps running, run row `failed` |

Every rung is a Set L scenario or walker criterion.

## Knobs

All in `SERVICE_DEFAULTS`, floats, under the `agent_knob` contract.

| Knob | Default | Meaning |
|---|---|---|
| `reflection_worker_enabled` | **0.0** | Per-agent worker kill-switch; 0.0 means the worker never auto-reflects this agent. The endpoint is always live regardless. |
| `reflection_poll_seconds` | 60.0 | Worker sweep interval. Process-level (an `agents.config` override is inert by design). |
| `reflection_worker_batch` | 4.0 | Max agents reflected per sweep (int at the call site); a cost bound, not a queue. |
| `reflection_pressure_threshold` | 1.0 | The worker pulls at or above this pressure. |
| `reflection_pressure_norm` | 10.0 | The divisor defining what pressure 1.0 means (roughly the importance mass that should trigger reflection). |
| `reflection_sample_k` | 16.0 | Episodes sampled per reflect (int at the call site). |
| `reflection_min_episodes` | 4.0 | Below this live-episode count the verb returns 409 (int at the call site). |
| `reflection_rrr_threshold` | 0.85 | RRR at or above this blocks consolidation. |
| `reflection_rrr_window` | 8.0 | Recent live reflections compared for RRR (int at the call site). |
| `reflection_consolidate_at` | 5.0 | Live identity-relevant count that triggers consolidation (int at the call site). |
| `reflection_trim_stale_seconds` | 2592000.0 | The trim staleness window (30 days): a component prunes only when all its span evidence sits on live memories older than this. 0.0 disables the trim entirely. |

## Migration 007: `reflection_runs`

The worker's persisted per-run accounting (endpoint runs ride the response payload): `run_id` PK;
`agent_id` NOT NULL FK to agents; `outcome` CHECK (`completed` or `failed`); `error`;
`reflections_written`; `dropped_ungrounded`; `consolidation_ran`; `consolidation_failed`; `rrr`;
`rrr_blocked`; `pruned_components`; `evicted_cache_rows`; `pressure_before` and `pressure_after`;
per-stage timings (`reflect_ms`, `consolidation_ms`, `insert_ms`, `total_ms`); token columns
(`reflect_input/output_tokens`, `consolidation_input/output_tokens`); and `created_at`. Plus
`reflection_runs_agent_id_idx`. No other schema change: the `reflections` table (migration 001) carries
the mechanism as built.

## Instrumentation and wire

`ReflectResult` (the seam's route-passthrough payload) carries: `agent_id`; `reflections:
list[ReflectionOut]` (`reflection_id`, `content`, `identity_relevant`, `source_memory_ids`);
`sampled_memory_ids`; `dropped_ungrounded`; `rrr: float | None`; `rrr_blocked_consolidation`;
`consolidation: ConsolidationOut | None` (`reflection_id`, `absorbed_reflection_ids`, `failed`);
`pruned_component_ids`; `evicted_cache_rows`; `pressure_before` and `pressure_after`;
`identity_version`; `identity_document_new`; and `instrumentation: ReflectInstrumentation` (`reflect_ms`,
`consolidation_ms`, `insert_ms`, `total_ms`, and the four token counts).

The C# core (`NpcMemory.Core`) mirrors the reflect call and models field-for-field, both projects build
0-warning, and the console-harness gate extends. The Ledger's reflection surface stays out of scope for
this layer; the agent-state read carries the live-beliefs list.

## The compiler contract

Reflection leaves the parameter compiler ([parameter-compiler.md](parameter-compiler.md)) a stable,
addressable `reflection_id` (the compiler's cache-key component); bi-temporal reflection invalidation
that doubles as compiler-cache eviction (consolidation and any future supersession set `invalid_at`,
never delete); and `content`, `identity_relevant`, and `source_memory_ids` as the compilable surface. A
compiled parameter layer amplifies like a confabulated rule library, so the compiler budgets its own
staleness guard; RRR here is the upstream half.

## Verification

- **Suite Set L** (`tests\test_reflection.py`, mostly unmarked; fixtures seed memories and reflections
  at the database layer, and the service is exercised through the seam and `sweep()`, no timers): the
  endpoint happy path (citations subset of sampled, bi-temporal rows); grounding enforcement (partial
  drop; all-ungrounded returns 502 with nothing written); the empty-conclusion valid outcome; the 409
  floor; the RRR guard (a near-identical fixture blocks consolidation while the reflection still stores);
  consolidation (absorbs by `invalid_at`, source union, version bump, document gains the belief); trim
  (the mechanical rule under a frozen clock: the stale-window prune fires, the active-evidence and
  authored-component exemptions hold, 0.0 disables, per-affected eviction, the gate set shrinks,
  reconstruction sources drop trimmed spans, no-trim parity); the dialogue seam (zero-reflection
  byte-parity, and a reflection visible in the `[identity]` block after recompile); worker lifecycle,
  sweep determinism, the per-agent kill-switch, and the no-attempts retry semantics; pressure math; the
  role load shape (real mode loads without the var, and the first real reflect without it raises
  `ConfigError` naming it); and route contracts (success plus 404, 409, 502).
- **The walker** `tests\verify_reflection.py` (lettered fail-fast sections): A. migration 007 shape;
  B. the reflect verb ladder; C. render, consolidation, and dialogue-seam parity; D. trim, liveness, and
  eviction; E. worker lifecycle at both construction sites; F. role and config shape. It inherits the
  walkers' shared-scratch-database convention (see [test-suite.md](test-suite.md)).
- **Touched floors re-verify**: the dialogue-seam floors (prose-prompt assembly) and reconstruction's
  (constraint inputs) re-run, and the write-path and read-path walkers' byte-identical passes are the
  zero-retrieval-change evidence.
- **A believability check**: after landing, a harness run on the existing scenario suite confirms no
  regression (reflection defaults off, and the seam moves carry parity contracts, so the run is
  meaningful unchanged).
