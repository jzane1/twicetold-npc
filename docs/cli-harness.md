# CLI harness & synthetic load driver — v1 build target

Fourth build target, on top of migration 01, write path v1, and read path v1. This specs the
**remaining piece of the vertical slice** (*retrieved memories → dialogue out*), completing
*event in → memory stored → dialogue out* as an interactive console. Design truth is
[architecture.md](architecture.md) §9 (behavior output & turn topology) + §11 (instrumentation &
load driver); the rulings behind it are in [decisions.md](decisions.md); the schema it reads and
the one scalar it writes are frozen in [migration-01.md](migration-01.md). This doc points, it does
not re-derive.

> **Status: BUILT & floor-verified 2026-07-15.** Every `[SETTLE-AT-BUILD]` item below was ruled at
> build time (dated "CLI-harness build rulings" entry in `decisions.md`; the two genuine forks —
> action-vocabulary source and cost units — were ruled via explicit questions at plan approval,
> the rest approved with the plan); the rulings are annotated inline. **The build added no new DB
> migration — the migration-01 schema stayed frozen;** reputation rides the existing
> `agents.reputation` / `reputation_sensitivity` scalar columns. Two scope forks had been ruled at
> spec time (dated "CLI-harness spec scope rulings" entry in `decisions.md`): the reputation delta
> is **persisted in-place** to the agent-row scalar, and the drive surface is an **interactive REPL
> over a shared session-runner core** (`app\session.py`) that the synthetic load driver reuses.
> **Single-call reconciliation:** §9's "August ship: a single Sonnet-class call" governs the slice —
> one call emits prose + action directive + reputation delta together; §9's "the Haiku call emits a
> delta" describes the *post-August split-brain* behavior call, not this slice. Do not wire a second
> Haiku behavior call into the vertical slice. *(Pulled forward pre-demo 2026-07-21 —
> `split-brain-streaming.md` now governs the second call; this slice stands as built.)*
>
> **A1 re-shape note (2026-08-04):** the reputation mechanic, the action directive, the
> `reputation_snapshot` / `reputation_delta_override` / `action_vocabulary` request fields, and
> the split-brain degradation rows below are **removed by ruling** — a dialogue turn now makes
> one streaming prose call, re-ranks the served view with per-call `weight_overrides`
> (weights-on-speech), and **persists nothing**. `architecture.md` §9 is the living seam
> statement; the sections below stand as the v1 historical spec.

## Principles this build honors

- **Vertical-slice completion, one dialogue seam.** The harness composes the two built seams (ingest,
  retrieval) and adds the single Sonnet call. It introduces no new storage mechanism beyond the
  reputation scalar update — no new tables, no version chains, no caches.
- **IDs + scores carried through to the turn.** The retrieval payload's `memory_id`s + score
  components surface in the dialogue turn's result and debug view, extending the read-path invariant
  (IDs + scores in every payload) through to behavior output. The suite and CLI assert on structure,
  never on generated prose ([test-suite.md](test-suite.md)).
- **Single instrumentation seam, two thin callers.** One dialogue-turn service carries the timing and
  token accounting for the Sonnet call; the REPL and the synthetic load driver both sit on it,
  neither duplicates the seam. (CLAUDE.md: *instrument at the seam*.)
- **Structured behavior output, not just prose.** The call returns prose **and** a parsed action
  directive **and** a reputation delta as structured data; prose is the only unassertable field.
- **Never-blank-a-dialogue.** A failing dialogue call or malformed structured output degrades soft —
  the turn still returns (§9: "unknown or unparseable directives → log, ignore, the turn still
  succeeds"). The behavior analog of the read path's never-blank and the write path's never-lose.
- **The action-directive contract survives the split-brain migration unchanged** (architecture §9).
  It is written as observed world fact carrying `{type, params}` — no "you decided to," so the
  behavior call — post-August then, pulled forward 2026-07-21 (`split-brain-streaming.md`) —
  can emit it without a contract change.
- **Nothing integrator-configurable is hardcoded** — the dialogue model role env var, the
  action-directive vocabulary, the reputation scale / sensitivity / clamp bounds: service defaults in
  `app\config.py`, per-agent overrides via `agents.config` (the existing `agent_knob` pattern).
- **Reputation is agent runtime state.** The per-turn delta mutates the `agents.reputation` scalar
  **in place** — deliberate, and explicitly outside the memory-content non-destructive invariant
  (which governs `memories` / `memory_details`). Recorded in `decisions.md`.
- **Instrument at the seam** — per-turn latency (first token, total) and per-100-turn cost feed
  architecture §11's histogram and cost table; surfaced verbatim in the CLI debug view.
- **Provider real + deterministic fake.** The dialogue call ships both, so the structural suite and
  the load driver run offline, without keys, and never assert on prose.

## Scope boundary — do NOT build

The mid-dialogue gate and its degradation ladder (immediate-queue item 1 since the 2026-07-18
fact-level build; specced & built 2026-07-19, `mid-dialogue-gate.md`); prompt caching /
prompt-head rebuild (post-August); **reconstruction serving — theta check, cache reads/writes,
pre-warm, `reconstructed` read_mode** (landed on the retrieval seam 2026-07-17,
`reconstruction.md`) — in this slice every
retrieved memory was served **verbatim**, as the read path then shipped; the split-brain behavior
call and per-call weight overrides (then post-August; pulled forward 2026-07-21 —
`split-brain-streaming.md`); reflection; correction endpoints; purge;
identity-document recompile (rides with reconstruction) — the slice's identity document is
**seed-prose-only**; a dialogue-turn **HTTP route** (rides with the Unity client surface — the
harness calls the seam in-process); and **any new DB schema or migration**. If adjacent work looks
necessary, **stop and report** rather than expand scope.

## The dialogue-turn service (the seam)

One entry point, both callers sit on it:

```
run_dialogue_turn(request: DialogueTurnRequest) -> DialogueTurnResult
```

It composes, in order: **retrieval** (`retrieve_dialogue_init`, built) → **prompt assembly**
(seed identity document + reputation snapshot + retrieved memories + utterance) → **single Sonnet
call** → **parse** structured output (prose + action directive + reputation delta) → **apply the
reputation delta in-place** → return.

- The **REPL** and the **synthetic load driver** both call it **in-process** (mirroring the
  write/read seams; the seams were built for a second caller — `app\ingest.py`, `app\retrieval.py`).
  On Windows the process drives its async work under a `SelectorEventLoop`, exactly as
  `app\serve.py` does, because the psycopg `AsyncConnectionPool` cannot run on the default Proactor
  loop.
- Timing + token accounting is recorded **once**, at this seam. There is **no FastAPI route** in
  this build — the CLI is the product surface; the dialogue-turn HTTP route belongs to the Unity
  client surface (out of scope).
- **Scene state lives in the caller** (the session-runner), not the service: the caller passes the
  frozen `reputation_snapshot` into each request and refreshes it only at a scene boundary. This
  makes "snapshot frozen within a scene" a property of the seam contract, not an implementation
  accident.

### `DialogueTurnResult` — the structured payload

Returned by `run_dialogue_turn`, surfaced verbatim in the CLI debug view and asserted by the suite:

- **Prose** — `content`: the generated dialogue line. **Never asserted on** — the only unassertable
  field in the payload.
- **Action directive** — `directive` `{type, params}` from the integrator vocabulary, plus
  `directive_dropped` (+ reason) when the emitted directive was unknown or unparseable (so soft
  failure is assertable without reading logs).
- **Reputation** — the emitted `reputation_delta`, the applied `reputation_sensitivity`, the clamped
  `reputation_after` (the value persisted to the row), and the injected scene-start
  `reputation_snapshot` (what the prompt actually saw).
- **Retrieval echo** — the retrieved `memory_id`s with their `score` + components, carried through
  from the `RetrievalResult` so the debug view shows exactly what the turn was conditioned on
  (IDs + scores invariant).
- **Instrumentation** — retrieval per-stage timings (from the read seam) + dialogue-call timing
  (`sonnet_ms`, first-token latency, total) + token accounting (`sonnet_input_tokens`,
  `sonnet_output_tokens`) + the per-turn cost — **cost units ruled 2026-07-15 (explicit question):
  tokens unconditionally; USD (`cost_usd`) only when the optional `LONGMEM_PRICE_*` env vars are
  set, else null — model pricing is never hardcoded.** Feeds architecture §11's latency histogram
  (first token, total; **no gate term** in the slice — it landed with the gate build,
  2026-07-19) and the per-100-turn cost table; `degraded`
  flag (+ reason) on the never-blank path.

## Request contract — `DialogueTurnRequest`

| Field | Meaning |
|---|---|
| `agent_id` | target NPC (FK → agents). |
| `utterance` | **required** — the player line; drives retrieval (passed to `retrieve_dialogue_init` as `query_text`, embedded as-is) **and** is the dialogue prompt's turn input. |
| `reputation_snapshot` | the scene-start reputation value the caller froze at the last scene boundary; injected into the prompt prefix. Caller-owned scene state (see the seam note). `[SETTLE-AT-BUILD]` exact plumbing — **ruled 2026-07-15: a required request field** (not a session-state handle), so "frozen within a scene" is a seam-contract property the walker asserts directly. |
| `reputation_delta_override` | optional client-supplied delta; **a client override wins** over the model's emitted delta (§9). |
| `action_vocabulary` | the integrator's action-directive vocabulary for this turn. `[SETTLE-AT-BUILD]` source — **ruled 2026-07-15 (explicit question): per-call field wins → `agents.config["action_vocabulary"]` fallback; neither configured → every emitted directive drops (`"no vocabulary configured"`), the turn succeeds.** No hardcoded default vocabulary. Shape: JSON array of `type` strings; `params` free. |
| `k` / `as_of` | pass-through to `retrieve_dialogue_init` (retrieval knob + time-travel surface); the harness does not reinterpret them. |
| `debug` | optional; when set, the caller renders the full `DialogueTurnResult` debug view (IDs, scores, parsed output, token + latency counts). |

## Reputation mechanic (the one persisted state change)

> **Removed by the A1 re-shape (2026-08-04).** The delta emission, the in-place apply, the
> snapshot plumbing, and the wire fields are gone; `agents.reputation` stays in the schema,
> unwritten and unread. Historical spec below.

The single Sonnet call emits `reputation_delta` in its structured output. Applied:

```
reputation_after = clamp(reputation_prev + reputation_sensitivity × delta, scale_min, scale_max)
```

then `UPDATE agents.reputation` **in place**. A client `reputation_delta_override`, if supplied,
**replaces the model's delta** before sensitivity/clamp (§9: "a client override wins"). The scale's
neutral point, `scale_min`/`scale_max`, and the `reputation_sensitivity` default are **integrator
config** (`agents.config` / `SERVICE_DEFAULTS`), never hardcoded — consistent with the migration-01
ruling that `reputation` / `reputation_sensitivity` carry no column default.

**Snapshot semantics.** The reputation value is read at **scene start** (the scene-boundary event's
reputation-snapshot consumer — deferred in write-v1, landing here per the 2026-07-14 re-slating) and
frozen into the prompt prefix for every turn in that scene. Mid-scene deltas accumulate on the
`agents.reputation` row, but the injected snapshot does **not** change until the next scene boundary,
where the caller re-reads the row. The next scene's prompt therefore reflects the accumulated change;
within a scene the prefix is stable.

**Invariant note.** This is an in-place **UPDATE** of an agent-row runtime scalar — the same class of
operation as the existing pin-flag toggle (`set_pinned` flips `memories.pinned` in place, shipped
write-path v1), and likewise **outside** the memory-content non-destructive invariant (which governs
`memories` / `memory_details` content, never DELETE except purge). Reputation is runtime state, not stored
memory content (architecture §9: "a scalar on the NPC row"); the schema was designed for it as a
single mutable column, not a version chain. Recorded in `decisions.md`.

## Prompt assembly (seed-prose-only)

The prompt prefix assembles, in order: the **seed identity document** (seed prose only in the slice —
identity-document recompile rides with reconstruction, which needs `identity_version`; reflection
stays deferred) + the **reputation snapshot** + the **retrieved memories** (verbatim head content,
carrying their IDs) ; the body is the **player utterance**. The exact block shape and ordering are
`[SETTLE-AT-BUILD]` — **ruled 2026-07-15:** labeled blocks in spec order — `[identity]` (omitted
when seed is NULL) → `[reputation]` (snapshot + scale bounds) → `[memories]` (rank order, one
`- (memory_id) content` line each) → `[output]` (the JSON contract + the turn's vocabulary; a
no-vocabulary turn instructs `directive: null`); user message = the raw utterance. Identical inputs
assemble byte-identical prompts (`assemble_system_prompt`, assertable without a model call).
*(As built today: `[reputation]` and the JSON `[output]` contract left with the A1 re-shape,
2026-08-04 — the prose call speaks plain prose; and the memory line's in-prompt `(memory_id)`
was stripped at F0, 2026-08-26, once the audit established nothing consumes it there — served
IDs ride the payload. The line is now `- content`; byte-stability unchanged.)*

## Action directive

> **Removed by the A1 re-shape (2026-08-04).** Deciding actions belongs to the game developer;
> the NPC's own actions arrive as ordinary observes (the game-authored action-observe contract,
> standing). Historical spec below.

Per-turn, from an **integrator-supplied vocabulary** (free `type` + `params`). The emitted directive
is validated against the vocabulary; an unknown or unparseable directive is **logged, ignored, and
the turn still succeeds** with `directive_dropped` set. The contract is written to **survive the
split-brain migration unchanged** (architecture §9) — the behavior call (pulled forward
2026-07-21) emits the same `{type, params}` shape as observed world fact. Vocabulary source is `[SETTLE-AT-BUILD]` —
**ruled 2026-07-15: per-call → `agents.config` fallback (see the request contract row).**

## Degradation ladder (dialogue turn)

| Condition | Behavior |
|---|---|
| dialogue (Sonnet) call fails | **never-blank-a-dialogue**: `[SETTLE-AT-BUILD]` fallback — **ruled 2026-07-15:** `DIALOGUE_FALLBACK_LINE = "..."` (a neutral beat), overridable per agent via `agents.config["dialogue_fallback_line"]` (the `TYPOLOGY_FALLBACK` precedent) — empty directive, zero reputation delta, `degraded = true` + reason; the turn still returns (fail-quiet, the behavior analog of never-lose-a-write). *Build note: a client `reputation_delta_override`, being client-authoritative, still applies on this path; the zero delta describes the no-override default.* |
| malformed structured output | log; use the prose if present, drop the directive (`directive_dropped`), zero the delta; the turn succeeds. |
| unknown / unparseable action directive | log, ignore, the turn succeeds; `directive_dropped` set (§9). |
| retrieval degraded (query-embedding down) | inherited from the read path's fail-quiet ladder — the turn proceeds on the degraded candidate set; the retrieval `degraded` flag rides through into the turn instrumentation. |
| reputation delta would exceed the scale | clamped to `scale_min`/`scale_max`; never throws. |

## Synthetic load driver (co-built)

A **first-class artifact co-built with the harness** (architecture §11: "no distribution exists
without it"). Python; drives **scripted sessions at volume** — observe events, utterances, and scene
boundaries — through the same `run_dialogue_turn` and `ingest_observation` seams, reusing the
session-runner core (not a divergent second path). It emits the §11 aggregates: the **latency
histogram** (p50/p95, decomposed into retrieval SQL, first token, total — **no gate term** in the
slice; the gate term landed at its build, 2026-07-19) and the **itemized per-100-turn
cost table**. It runs on the **deterministic fake providers**
by default (offline, keyless, at volume); the real providers back a keyed smoke moment ahead of demo
choreography. Script format, scale knobs, and the exact aggregate output are `[SETTLE-AT-BUILD]` —
**ruled 2026-07-15:** `python -m app.load_driver --sessions N --turns M [--script p.json] [--seed S]
[--agent <uuid>] [--database-uri <uri>] [--json out.json]`; script = JSON list of sessions, each a
list of `{"kind": "observe" | "utterance" | "scene", ...}` events, with a seeded deterministic
built-in generator when omitted; aggregates = latency p50/p95 (retrieval SQL, query embed, first
token, dialogue total, turn total) + the itemized per-100-turn token table, USD per the pricing
ruling. Without `--agent` it creates a driver agent in the target DB.

## Model provider interfaces

The dialogue call is a **new model role**, following the write path's provider triad exactly
(`app\providers.py`): a `DialogueProvider` **Protocol**, a `RealDialogueProvider(settings)`
(Sonnet-class via the `anthropic` SDK, model read from a new `LONGMEM_MODEL_DIALOGUE` env var), and a
deterministic `FakeDialogueProvider` (stable prose echo, a fixed directive drawn from the vocabulary,
a deterministic reputation delta) so the structural suite and the load driver run **offline, keyless,
and never assert on prose**. The result dataclass carries `input_tokens` / `output_tokens` (spend is
always accounted). Registered on the `Providers` bundle and selected by `LONGMEM_PROVIDER_MODE`; the
new role env var sits alongside the four existing roles in `app\config.py` with a `Settings` field
and the existing real-mode key requirement. The dialogue service is identical under either provider.

## `[SETTLE-AT-BUILD]` — physical shapes, ruled at build (stop and report, never silently choose)

**All ruled 2026-07-15 with the build plan** (dated "CLI-harness build rulings" entry in
`decisions.md`; the two genuine forks were ruled via explicit questions; annotated inline above):

- **`LONGMEM_MODEL_DIALOGUE` env-var name** — **ruled as suggested:** exactly that string, alongside
  the four existing roles in `app\config.py`; required in real mode; `Settings.model_dialogue`.
- **Dialogue structured-output schema** — **ruled:** JSON-in-text per the write/escalation
  precedent — ONLY `{"prose": str, "directive": {"type", "params"} | null, "reputation_delta":
  float}`. Malformed = no parseable prose (→ fallback line, `degraded`, spend accounted); below
  prose the parse salvages field-wise (directive drops with reason; delta zeroes,
  `reputation_delta_source = "zeroed"`). Vocabulary validation happens at the seam.
- **Reputation apply shape** — **ruled:** one atomic SQL statement (clamp in SQL, `FOR UPDATE`
  old-value capture, `RETURNING (prev, after)`); `SERVICE_DEFAULTS` keys `reputation_scale_min`
  (−1.0) / `reputation_scale_max` (1.0) / `reputation_neutral` (0.0) /
  `reputation_sensitivity_default` (1.0), per-agent overridable; the `agents.reputation_sensitivity`
  column wins over the knob when non-NULL.
- **Action-directive vocabulary source** — **ruled (explicit question): per-call request field →
  `agents.config` fallback; neither → drop with reason** (see the request-contract row).
- **Prompt-assembly block shape** — **ruled:** labeled blocks in spec order (see §Prompt assembly).
- **Never-blank fallback line** — **ruled:** `DIALOGUE_FALLBACK_LINE = "..."`, per-agent
  `agents.config["dialogue_fallback_line"]` override (see the degradation ladder).
- **CLI surface** — **ruled:** entry `python -m app.cli --agent <uuid> [--debug]` (`app\cli.py`);
  meta-commands `:observe` / `:scene [type]` / `:pin` / `:unpin` / `:as-of <iso8601|clear>` /
  `:debug [on|off]` / `:help` / `:quit`, anything else an utterance; session state (frozen
  snapshot, `as_of`, debug flag) lives in the session-runner; `--debug` renders via the pure
  `render_debug` function the walker asserts on.
- **Load-driver shape** — **ruled:** `app\load_driver.py` (see §Synthetic load driver).
- **Wire models** — **ruled: Pydantic in `app\schemas.py`**, mirroring the write/read payloads
  (the eventual Unity route reuses them); `DialogueTurnInstrumentation` nests
  `RetrievalInstrumentation`.

## Done when

- **Turn happy path (fake provider).** Given a seeded agent and an utterance, `run_dialogue_turn`
  returns `content` + a parsed `directive` + a `reputation_delta`, and the `DialogueTurnResult`
  carries the retrieved `memory_id`s with their score components and non-null instrumentation
  (retrieval + `sonnet_ms` timings, token counts).
- **One seam, thin callers.** The REPL and the synthetic load driver both call `run_dialogue_turn`;
  the timing + token accounting is recorded once, at the service seam — neither caller duplicates it.
- **Reputation persists in-place.** A turn's delta updates `agents.reputation` (clamp + sensitivity
  applied), a client `reputation_delta_override` wins over the model delta, and `reputation_after`
  in the result equals the persisted scalar.
- **Snapshot frozen within a scene.** The injected `reputation_snapshot` is the scene-start value;
  mid-scene deltas accumulate on the row but the injected value is unchanged until the next
  scene-boundary, and the next scene's snapshot reflects the accumulation.
- **Action directive soft-fails.** Given an emitted directive outside the vocabulary, it is logged
  and dropped, `directive_dropped` is set, and the turn still returns prose.
- **Never-blank-a-dialogue.** Given a dialogue provider that fails, the turn still returns (a
  fallback line, `degraded = true` + reason) — not an exception.
- **IDs + scores carried through.** The retrieved `memory_id`s and score components from retrieval
  appear in the turn result and the `--debug` view.
- **Debug view.** `--debug` surfaces retrieved memory IDs + scores, the parsed structured output
  (prose / directive / delta), and token + latency counts (status.md's debug-mode requirement).
- **Load driver runs.** A scripted N-session run through the seams on the fake providers completes
  offline and keyless, emitting the §11 per-100-turn cost table and latency p50/p95 (retrieval SQL,
  first token, total).
- **Deterministic fake.** Two identical scripted turns on the fake dialogue provider yield
  byte-identical structured output (prose / directive / delta) and identical reputation math.
- **Schema frozen.** No new migration; `db\migrate.py` no-arg is still a clean no-op on `longmem`;
  reputation uses the existing `agents.reputation` column.
- Every touched `[SETTLE-AT-BUILD]` was reported and confirmed before being built, and recorded in
  `decisions.md`.
