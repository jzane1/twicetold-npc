# parameter-compiler.md — reflection → parameter compiler (Phase C3)

**BUILT 2026-08-17, spec-to-floor in one session** — migration 008, `app\compiler.py`, the
consume splice at the dialogue seam, the judge-shaped `TWICETOLD_MODEL_COMPILER` role, suite
Set M (21 scenarios, all unmarked), the tenth walker (48 assertions), the C# mirror + four
interop beats (28 → 32). The seven C3 rulings are the dated 2026-08-17 entry in
`decisions.md`; the plan-mode fork batches settled them before a line was written. Ships
**default OFF** (`compiler_worker_enabled` 0.0 per agent); the flip is a Phase D question
beside C1's and C2's.

## What it is

C2 left formed beliefs (rows in `reflections`) with one consumer: identity-relevant rows
reach speech as prose through the rendered identity document; the rest sat runtime-inert by
ruling, waiting for C3. The compiler activates them: **live beliefs compile into
per-scene-type parameter bundles** — multipliers on the three prose-view weights
(relevance / recency / importance) — so the NPC's formed dispositions shape which memories
dominate its speech, per scene type, without the dialogue model ever seeing a raw parameter.
The founding §10 contract holds throughout: typed core + integrator-namespaced passthrough;
scene-type vocabulary integrator-owned; unknown types log-and-continue against the default
bundle; compiled params consumed **only upstream of the dialogue call**; cache key =
(reflection × scene-type); bi-temporal belief invalidation doubles as compiler-cache
eviction.

## The seven rulings (2026-08-17; the dated entry in `decisions.md`)

1. **Feedstock: ALL live beliefs compile** — identity-relevant included (the prose channel is
   orthogonal salience); a neutral bundle is a valid compile.
2. **Typed core = the three weight multipliers only.** No stance prompt block. §10's founding
   "action-set biases" clause died with the 2026-08-04 action-side scrap and is corrected in
   `architecture.md` with this build; stance-shaped content is integrator passthrough.
3. **Scheduling: a standalone third background worker** on the C1/C2 lifecycle contract.
   **No generic jobs table** (the unification refactor is its own later task — surfaced with
   its real cost and declined for this build). Work discovery is stateless SQL — the missing
   (live belief × scene-type) pairs join, the reflection-pressure precedent. **No new HTTP
   route**: C3 has no endpoint verb at all (the C1 worker precedent).
4. **The staleness guard is all-mechanical** (the confabulated-rule-library caution the C2
   spec obligated): the K-window + liveness-by-join + hard clamps. See below.
5. **`TWICETOLD_MODEL_COMPILER` takes the judge shape** — the THIRD such var: loaded both
   modes, required by neither, standalone lazy `build_compiler_provider`, loud `ConfigError`
   at the first real compile (always inside the worker); prices
   `TWICETOLD_PRICE_COMPILER_IN/OUT` join `PRICE_ENV_KEYS`.
6. **Multiplier clamp = [0.25, 4.0]**, frozen into migration 008's CHECK (applied migrations
   are immutable, so the bounds were ruled before the file was written): one belief moves one
   axis by at most ×4 either way and can never zero it — zeroing stays the caller's explicit
   weight-override privilege.
7. **`:compile` = sweep semantics** — the kill-switch is honored and the printed attempt
   count makes a no-op visible; the REPL exercises exactly what production runs (an
   always-live direct compile was declined: no endpoint exists for it to mirror).

## Data model (migration 008)

- **`compiled_bundles`** — one row per compile call, APPEND-ONLY: `bundle_id`, `agent_id` FK,
  `reflection_id` FK (safe — reflections are invalidated, never deleted; **C6 closed
  (2026-08-18)**: purge is per-memory and does NOT reach reflections, so bundle purge semantics
  never arise — the episode-scoped delete leaves reflections and their bundles standing; *still
  true under the per-agent purge verb of 2026-09-02, which erases every memory of an agent and
  leaves its reflections, bundles, and run logs standing*),
  `scene_type`, `w_relevance`/`w_recency`/`w_importance` (real, CHECK [0.25, 4.0]),
  `passthrough` jsonb, per-call `input_tokens`/`output_tokens`/`compile_ms`, `created_at`.
  Consume reads the newest row per (reflection_id, scene_type); a re-compile appends.
  **Liveness is DERIVED** — a bundle applies only while its source reflection is live, so
  supersession and consolidation evict compiled parameters with zero writes here.
- **`compiler_runs`** — the worker's per-agent-per-sweep accounting (the `reflection_runs`
  precedent; every row is worker-written since no endpoint exists): outcome
  completed/failed, error, `pairs_compiled`/`pairs_failed`/`passthrough_keys_dropped`,
  aggregate tokens, `total_ms`. A row lands only when the sweep ATTEMPTED the agent; skips
  (kill-switch, no missing pairs) write nothing.

## The compile pass

`CompilerWorker.sweep()` — the deterministic no-timer entry (tests, walker, `:compile`) —
scans agents in fixed order, skips `compiler_worker_enabled == 0.0`, and gives each enabled
agent the remaining call budget (`compiler_worker_batch`, a per-sweep cost bound across
agents, not a queue). Per agent, `CompilerService.compile_agent`: discover missing pairs
(the K most recent live beliefs × sorted vocabulary = config `scene_types` + the reserved
`default`, minus pairs already holding a bundle; deterministic order newest-belief-first then
scene_type, so the budget cuts a stable prefix), one model call per pair, mechanical
validation (clamp multipliers to the module constants; drop un-namespaced passthrough keys
with a count — the dropped-ungrounded precedent), insert each bundle as it lands. The
provider is built lazily only when work exists, so an idle real-mode deployment without the
var never errors.

Degradation ladder (every rung a Set M scenario or walker criterion): kill-switch → skipped,
no row · no missing pairs → nothing, no row (discovery IS the idempotency) · one pair
malformed/failing → recorded, others proceed, the pair stays missing and retries naturally
next sweep (NO attempts ledger — the C2 contrast-with-enrichment stance) · real mode without
the var → ConfigError at the first worked agent: a `failed` run row, logged loud ONCE, the
worker keeps running · budget exhausted → the remainder is the next sweep's stable prefix.

## The consume path

`DialogueTurnRequest.scene_type` (optional) resolves against the agent's vocabulary: a
configured (or the reserved) type → itself; unknown → the default **with the instrumentation
flag** (log-and-continue, ruled); absent → the default silently. One indexed fetch returns
the newest bundle per in-window live belief for exactly the resolved type — **a known type
whose pair is not yet compiled contributes nothing** (no cross-type fallback; the compile-lag
window degrades toward today's behavior, never leaks another type's parameters). The pure
composition (`compose_bundle_weights`) re-clamps each stored multiplier (defense), takes the
per-axis product, and clamps `base × product` back into the existing [WEIGHT_MIN,
WEIGHT_MAX] — over the base the existing resolver produced (request field → `agents.config`
→ 1.0), which stays walker-pinned and byte-untouched. `rank_dialogue_view` is unchanged;
membership never changes; `app\retrieval.py` is byte-untouched. **Zero bundles compose to
the identity — a bundle-free turn is byte-identical to the pre-C3 seam** (walker-asserted
parity). No byte-identity invariant amendment: C3 changes ordering upstream, never stored
text (`weight_overrides` already vary ordering per call).

Instrumentation (instrument at the seam): `scene_type_resolved`, `scene_type_unknown`, the
three composed `bundle_w_*` products, `bundle_reflection_ids` (window order), and
`bundle_fetch_ms` — the consume read costs one indexed query on every turn, bundle-free
agents included, recorded honestly. The REPL's debug view renders a `compiled:` line;
`:scene <type>` (which always carried a type on the boundary event) now also holds the type
as session state riding subsequent turns — a bare `:scene` clears it. The C# mirror is
field-for-field (`NpcSession.SceneType` set by `SceneBoundaryAsync`).

**Passthrough is stored, never consumed or wire-carried in C3.** Ruling 2 leaves it no
server-side consumer; it lands validated in `compiled_bundles.passthrough` for the future
integrator read (C5's agent-state neighborhood — the recorded dependency; **BUILT
2026-08-17**: `GET /v1/agents/{id}/state` serves it verbatim on every live bundle, still
never interpreted server-side). Nobody should hunt for a phantom consumer.

## The staleness guard (ruling 4 — all mechanical, no model judgment)

- **Liveness by join**: bundles have no independent life. A superseded or absorbed belief's
  parameters vanish from the next turn with zero bundle writes; its pairs leave discovery.
  The consolidation N→1 collapse is the sharp case: N contributions die at once and the
  survivor (a new `reflection_id`) surfaces as fresh work the next sweep compiles.
- **The K-window** (`compiler_window_k`): only the K most recent live beliefs compile AND
  apply — enforced by the same window CTE at discovery and at the consume fetch, so the
  never-consolidated non-identity population can never accumulate unbounded influence.
- **Hard clamps at both ends**: per-value at write (backstopped by the migration CHECK) and
  re-clamped at consume; the composed product clamps into the weight range. Module
  constants (`MULTIPLIER_MIN`/`MULTIPLIER_MAX`), not knobs — the WEIGHT_MIN/MAX precedent.

RRR upstream (C2) polices belief formation; this trio polices belief influence. Together
they are the two halves the C2 spec's ExpeL caution asked for.

## Knobs and config

| Knob (SERVICE_DEFAULTS, per-agent via `agents.config`) | Default | Note |
| --- | --- | --- |
| `compiler_worker_enabled` | 0.0 | Per-agent kill-switch; gates the component entirely (no endpoint exists). |
| `compiler_poll_seconds` | 60.0 | Process-level (agent override inert by design — the reflection precedent). |
| `compiler_worker_batch` | 8.0 | Max compile CALLS per sweep across agents; process-level cost bound. |
| `compiler_window_k` | 8.0 | The staleness-guard window, both ends. |

`scene_types` is a plain `agents.config` key (string list, default EMPTY — the
decay_classes precedent; the float-only `agent_knob` contract can't carry it). With no
configured vocabulary only the reserved `default` type compiles — a hardcoded vocabulary
would violate the never-hardcoded rule.

## Test surface

Set M (`tests\test_set_m_compiler.py`, 21 unmarked scenarios) covers the ladder, both window
ends, the collapse, parity, the per-scene re-rank flip (one agent, two types, opposite
extremes — deterministic regardless of embedding hashes), override composition, and the
role/load shape. The tenth walker (`tests\verify_compiler.py`, 48 assertions, sections A–F)
re-proves it against the scratch DB incl. the migration shape and both construction sites;
its module docstring carries the persistent-scratch rule (sections leaving enabled agents
with uncompiled pairs flip the kill-switch off). Interop beats [13] (four checks, 28 → 32)
assert the wire contract only — the harness cannot reach `sweep()`, deliberately. The four
mechanical migration pins bumped: the gate-walker ledger list, the eval-runner applied count,
the table census (+2), and the reflection walker's own A5 ledger pin (an undocumented fourth
found at plan time; future migrations: grep the PRIOR migration's filename).

## Done-when (what the independent floor-verifier re-checks)

1. Migration 008 applies fresh and idempotently; shape + CHECK teeth (walker A).
2. The compile ladder end to end, clamp-at-write + namespace filter included (walker B).
3. The guard: window at both ends, instant eviction, the collapse (walker C).
4. Parity byte-exact with zero bundles; the per-scene flip with membership constant; hand
   exponent math (walker D).
5. The worker lifecycle at both construction sites, stop-before-pool LIFO (walker E).
6. The judge-shaped role surface: loads without, loud at first real use, failed-row rung
   (walker F).
7. Suite green (`-m "not nlp"` 135 / full 149); the ten walkers green; the interop gate at
   32 checks; the nine prior walkers byte-untouched at their criteria (the
   zero-retrieval-change evidence).
