# The parameter compiler

The reflection layer ([reflection.md](reflection.md)) forms beliefs (rows in `reflections`), and
identity-relevant beliefs reach speech as prose through the rendered identity document. The parameter
compiler activates the rest: live beliefs compile into per-scene-type parameter bundles, which are
multipliers on the three prose-view weights (relevance, recency, importance). The NPC's formed
dispositions then shape which memories dominate its speech, per scene type, without the dialogue model
ever seeing a raw parameter.

The founding contract from [architecture.md](architecture.md) §10 holds throughout: a typed core plus
integrator-namespaced passthrough; an integrator-owned scene-type vocabulary; unknown types
log-and-continue against the default bundle; compiled parameters consumed only upstream of the
dialogue call; a cache key of (reflection x scene-type); and bi-temporal belief invalidation doubling
as compiler-cache eviction. The feature ships default OFF (`compiler_worker_enabled` 0.0 per agent).

## Design

- **Feedstock: all live beliefs compile**, identity-relevant ones included (the prose channel is
  orthogonal salience). A neutral bundle is a valid compile.
- **The typed core is the three weight multipliers only**, with no stance prompt block. Stance-shaped
  content is integrator passthrough.
- **Scheduling is a standalone background worker** on the same lifecycle contract as the deferred-write
  and reflection workers, with no generic jobs table. Work discovery is stateless SQL: the missing
  (live belief x scene-type) pairs join, the same pattern as reflection-pressure discovery. There is no
  HTTP route; the compiler has no endpoint verb.
- **The staleness guard is all-mechanical** (no model judgment): a K-window, liveness-by-join, and hard
  clamps, described below.
- **`TWICETOLD_MODEL_COMPILER` takes the judge shape**: loaded in both provider modes, required by
  neither, built through a standalone lazy `build_compiler_provider` that raises a loud `ConfigError` at
  the first real compile (always inside the worker). Its prices `TWICETOLD_PRICE_COMPILER_IN` and
  `TWICETOLD_PRICE_COMPILER_OUT` join `PRICE_ENV_KEYS`.
- **The multiplier clamp is [0.25, 4.0]**, frozen into migration 008's CHECK. One belief moves one axis
  by at most 4x either way and can never zero it; zeroing stays the caller's explicit
  weight-override privilege.
- **`:compile` has sweep semantics**: the kill-switch is honored and the printed attempt count makes a
  no-op visible, so the REPL exercises exactly what production runs.

## Data model (migration 008)

- **`compiled_bundles`**, one append-only row per compile call: `bundle_id`, `agent_id` FK,
  `reflection_id` FK (safe, because reflections are invalidated and never deleted; the per-memory and
  per-agent purge verbs both leave reflections, bundles, and run logs standing), `scene_type`,
  `w_relevance` / `w_recency` / `w_importance` (real, CHECK [0.25, 4.0]), `passthrough` jsonb, per-call
  `input_tokens` / `output_tokens` / `compile_ms`, and `created_at`. Consume reads the newest row per
  (reflection_id, scene_type); a re-compile appends. Liveness is derived: a bundle applies only while its
  source reflection is live, so supersession and consolidation evict compiled parameters with zero writes
  here.
- **`compiler_runs`**, the worker's per-agent-per-sweep accounting (every row is worker-written, since no
  endpoint exists): outcome completed or failed, error, `pairs_compiled` / `pairs_failed` /
  `passthrough_keys_dropped`, aggregate tokens, and `total_ms`. A row lands only when the sweep attempted
  the agent; skips (kill-switch, no missing pairs) write nothing.

## The compile pass

`CompilerWorker.sweep()` is the deterministic no-timer entry (tests, walker, `:compile`). It scans
agents in fixed order, skips any with `compiler_worker_enabled == 0.0`, and gives each enabled agent the
remaining call budget (`compiler_worker_batch`, a per-sweep cost bound across agents, not a queue). Per
agent, `CompilerService.compile_agent` discovers missing pairs (the K most recent live beliefs by the
sorted vocabulary, which is config `scene_types` plus the reserved `default`, minus pairs already
holding a bundle; deterministic order, newest belief first then scene_type, so the budget cuts a stable
prefix), makes one model call per pair, validates mechanically (clamp multipliers to the module
constants; drop un-namespaced passthrough keys with a count), and inserts each bundle as it lands. The
provider is built lazily only when work exists, so an idle real-mode deployment without the var never
errors.

The degradation ladder, each rung a test scenario or walker criterion: kill-switch is skipped with no
row; no missing pairs writes nothing (discovery is the idempotency); one malformed or failing pair is
recorded while the others proceed, and the pair stays missing and retries naturally next sweep (there is
no attempts ledger); real mode without the var raises `ConfigError` at the first worked agent, which
lands a `failed` run row, logs loud once, and leaves the worker running; and an exhausted budget leaves
the remainder as the next sweep's stable prefix.

## The consume path

`DialogueTurnRequest.scene_type` (optional) resolves against the agent's vocabulary: a configured or
reserved type resolves to itself; an unknown type resolves to the default with an instrumentation flag
(log-and-continue); an absent type resolves to the default silently. One indexed fetch returns the
newest bundle per in-window live belief for exactly the resolved type. A known type whose pair is not
yet compiled contributes nothing: there is no cross-type fallback, so the compile-lag window degrades
toward the un-compiled behavior and never leaks another type's parameters. The pure composition
(`compose_bundle_weights`) re-clamps each stored multiplier (defense), takes the per-axis product, and
clamps `base x product` back into the existing [WEIGHT_MIN, WEIGHT_MAX], over the base the existing
resolver produced (request field, then `agents.config`, then 1.0), which stays byte-untouched.
`rank_dialogue_view` is unchanged, membership never changes, and `app\retrieval.py` is byte-untouched.
Zero bundles compose to the identity, so a bundle-free turn is byte-identical to the un-compiled seam.
There is no byte-identity invariant amendment: the compiler changes ordering upstream, never stored
text, and `weight_overrides` already vary ordering per call.

Instrumentation at the seam records `scene_type_resolved`, `scene_type_unknown`, the three composed
`bundle_w_*` products, `bundle_reflection_ids` (window order), and `bundle_fetch_ms`, since the consume
read costs one indexed query on every turn, bundle-free agents included. The REPL's debug view renders
a `compiled:` line; `:scene <type>` holds the type as session state riding subsequent turns, and a bare
`:scene` clears it. The C# mirror is field-for-field (`NpcSession.SceneType`, set by `SceneBoundaryAsync`).

Passthrough is stored, never consumed or wire-carried by the compiler: the typed-core decision leaves it
no server-side consumer, so it lands validated in `compiled_bundles.passthrough` for the integrator read.
`GET /v1/agents/{id}/state` serves it verbatim on every live bundle, still never interpreted
server-side.

## The staleness guard

All mechanical, no model judgment:

- **Liveness by join.** Bundles have no independent life. A superseded or absorbed belief's parameters
  vanish from the next turn with zero bundle writes, and its pairs leave discovery. The consolidation
  N-to-1 collapse is the sharp case: N contributions die at once, and the survivor (a new
  `reflection_id`) surfaces as fresh work the next sweep compiles.
- **The K-window** (`compiler_window_k`): only the K most recent live beliefs compile and apply,
  enforced by the same window CTE at discovery and at the consume fetch, so the never-consolidated
  non-identity population can never accumulate unbounded influence.
- **Hard clamps at both ends**: per-value at write (backstopped by the migration CHECK) and re-clamped
  at consume, with the composed product clamped into the weight range. These are module constants
  (`MULTIPLIER_MIN`, `MULTIPLIER_MAX`), not knobs.

The reflection layer polices belief formation; this trio polices belief influence. Together they answer
the confabulated-rule-library caution: bounded formation upstream, bounded influence downstream.

## Knobs and config

| Knob (SERVICE_DEFAULTS, per-agent via `agents.config`) | Default | Note |
| --- | --- | --- |
| `compiler_worker_enabled` | 0.0 | Per-agent kill-switch; gates the component entirely (no endpoint exists). |
| `compiler_poll_seconds` | 60.0 | Process-level (agent override inert by design). |
| `compiler_worker_batch` | 8.0 | Max compile calls per sweep across agents; process-level cost bound. |
| `compiler_window_k` | 8.0 | The staleness-guard window, both ends. |

`scene_types` is a plain `agents.config` key (a string list, default empty), because the float-only
`agent_knob` contract cannot carry it. With no configured vocabulary only the reserved `default` type
compiles; a hardcoded vocabulary would violate the never-hardcoded rule.

## Verification

Set M (`tests\test_set_m_compiler.py`, 21 unmarked scenarios) covers the ladder, both window ends, the
collapse, parity, the per-scene re-rank flip (one agent, two types, opposite extremes, deterministic
regardless of embedding hashes), override composition, and the role and load shape. The walker
(`tests\verify_compiler.py`, 48 assertions, sections A to F) re-proves it against the scratch database
including the migration shape and both construction sites; its module docstring carries the
persistent-scratch rule (sections that leave enabled agents with uncompiled pairs flip the kill-switch
off). The interop beat asserts the wire contract only, since the harness cannot reach `sweep()`.

An independent verification re-checks:

1. Migration 008 applies fresh and idempotently; shape and CHECK teeth (walker A).
2. The compile ladder end to end, clamp-at-write and namespace filter included (walker B).
3. The guard: window at both ends, instant eviction, the collapse (walker C).
4. Parity byte-exact with zero bundles; the per-scene flip with membership constant; hand exponent math
   (walker D).
5. The worker lifecycle at both construction sites, stop-before-pool LIFO (walker E).
6. The judge-shaped role surface: loads without the var, loud at first real use, the failed-row rung
   (walker F).
7. Suite green; the walkers green; the interop gate green; the prior walkers byte-untouched at their
   criteria (the zero-retrieval-change evidence).
