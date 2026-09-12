# Unity client + reference scene + The Ledger — build target (specced 2026-07-27)

> **BUILT 2026-07-27 — all four stages, same day.** Stage 0 (the three ruled-in routes) and
> stage 1 (`NpcMemory.Core` + console harness, the interop gate 21/21) are floor-verified;
> stages 2 (Unity adapter + gray-box set, Play-mode gate 8/8) and 3 (The Ledger, live browser
> beat + suite 49) carry live receipts. *(2026-07-28: stage 3's re-runnable half — the `/ledger`
> route contract — plus stage 1's build and interop gate were independently re-verified during the
> full-repo audit. The **stage-2 Play-mode gate remains the one outstanding verification**; see
> `status.md`, which is the authority on what is still owed.)* *(2026-08-07 audit note: both
> figures above are as-built history — the interop gate has since grown 21 → 23 → 24 checks
> (client-timing 2026-07-28, metrics read 2026-07-29, re-composed by A1 2026-08-04) and runs
> 24/24; the stage-2 Play-mode gate closed 2026-07-29, was re-opened by the A1 re-shape, and
> re-closed 2026-08-05 fake-only by ruling — the dated notes on `floors.md` rows 19/21 are the
> evidence.)* Fork rulings + build record:
> the two dated 2026-07-27 entries in `decisions.md` and the five 2026-07-27 session-log
> entries in `session-log.md` (they lived in `status.md` until the 2026-07-28 split).

Immediate-queue item 2's spec session. Consolidates the artifact-queue "Unity client C# API
surface" entry, architecture's environment section (Unity 6, flatscreen 3D, `NpcMemory` root
namespace, `Assets\Scripts\` until packaging), the July 2026 external audit's choreography +
engineering spec (its solutions doc, in the local record), and the **2026-07-27 demo-vehicle ruling**
(dated "Demo-vehicle ruling" entry in `decisions.md`) into one build target over the frozen
schema (ledger 001–005 — **no migration is expected**; if a fork below rules in server work that
needs one, it follows the numbered-migration rule as normal).

## The ruled shape (2026-07-27)

Jack ruled the demo vehicle after a five-agent panel — the four audit personas + a
modding-landscape research scout — (the fork:
custom Unity scene vs modding into an established game — Skyrim declined; full rationale in the
register entry):

1. **`NpcMemory.Core` first — engine-agnostic.** Plain .NET class library: HTTP + JSON + the
   `NpcSession` port of the Python runner's `_apply_turn_result` bookkeeping. **Zero
   `UnityEngine` types. One flat client class** — no abstraction ceremony, no interface layers
   with a single implementation.
2. **A `dotnet run` console harness drives the core through every demo beat headless** against
   the live served API — this is the Unity↔backend interop go/no-go, **moved from Wk-2 to Wk-1**:
   the wire contract is proven before Unity ever opens.
3. **Unity is a thin adapter + a set, not a game.** A MonoBehaviour wrapper over the proven core,
   plus the gray-box scene as the *intended* systems/dev-tool aesthetic (adopted with the
   2026-07-22 audit plan): one
   room, an NPC with a nameplate, dialogue text on screen, static camera positions. No navmesh,
   no animation work, no art on the critical path.
4. **The Ledger is a browser page, not Unity UI** — composited beside the game view in OBS.
5. **Established-game integration is post-demo** (sequenced-later ledger: a C#-moddable game
   reusing `NpcMemory.Core` — not Skyrim).

## Principles this build honors

- **The server is stateless; the client owns scene state.** Four scene-state groups ride the
  request (`identity_version` + `scene_started_at`, `loaded_memory_ids` +
  `gate_fruitless_streak`, context fields, `as_of`); `NpcSession` is the one
  place the bookkeeping lives, mirroring `app\session.py` exactly. *(As written this listed six
  groups incl. `reputation_snapshot` and `recent_actions` — both removed by the A1 re-shape,
  2026-08-04, like the `:142` annotation below; corrected at the F0 audit, 2026-08-26.)*
- **Nothing integrator-configurable is hardcoded**: base URL, per-route timeouts, k, weight
  overrides — all constructor/config surface (the action vocabulary left with A1). No hardcoded
  model names or pricing anywhere in C#.
- **IDs + scores always surfaced.** The client exposes the full structured results (items with
  memory IDs, scores, `read_mode`; both scored views; instrumentation) — never prose-only.
- **Structural tests only.** C# tests assert structure (IDs, flags, state transitions), never
  model prose — the suite discipline carried across the language boundary.
- **Instrument at the seam.** The client records one client-side term per call
  (`client_total_ms`, wall time around the HTTP call) beside the server's instrumentation, so
  transport overhead is visible from day one. *(Built 2026-07-28 — the audit found this bullet
  asserting a term no C# file carried. Now `NpcMemoryClient.ClientTotalMs` plus an
  `OnCallMeasured(path, ms)` event, covering the nine request/response verbs and the SSE stream's
  whole envelope. Client-side only — it never rides the wire.)*

## Scope boundary — do NOT build

- **Unity Package Manager packaging** (`com.jacksonzane.npc-memory`) — deferred post-demo
  (architecture environment section). Scripts live under `Assets\Scripts\`.
- **The established-game clip** — post-demo (2026-07-27 ruling; sequenced-later ledger).
- **The judged eval harness** — immediate-queue item 3, its own target (the Ledger binds the
  fields it will score, but builds no judge).
- **The thread-pool cap** (ruled deferred post-demo 2026-07-23) and the **C1 pre-warm build**
  (ruled post-demo 2026-07-22 — warm-init is choreography, below). *(Superseded 2026-08-18:
  C7-B landed the real pre-warm as `SceneBoundaryEvent.prewarm_context` — a probed boundary
  warms the reconstruction cache at the fresh basis, and the warm-init choreography trick is
  retired. The C# mirror landed with E2, 2026-08-19.)*
- **No TTS/STT, no voice** — text is the demo surface.

## Mechanism

### NpcMemory.Core (the flat client)

`NpcMemoryClient` — stateless verbs mirroring the routes 1:1, pass-through both ways
(request models serialize exactly what Pydantic accepts; response models deserialize every field
the service returns — the route pass-through ruling carried to the client).

**Fourteen verbs as built** *(table corrected 2026-07-28: it was written before the forks were ruled
and still said "six routes" — forks 1–3 added four more, all of which shipped in stage 0; row
eleven added 2026-08-07 audit — `ReconstructionMetricsAsync` had joined 2026-07-29 with
eval-harness stage 1 and the table was never updated; corrected again 2026-08-17 with C5's row —
`ReflectAsync` had joined 2026-08-15 with C2 and this table was never updated, the same miss)*:

| Verb | Route | Errors surfaced |
|---|---|---|
| `DialogueTurnAsync` | `POST /v1/dialogue/turn` | 404 unknown agent, 422 unknown identity version |
| `DialogueTurnStreamAsync` | `POST /v1/dialogue/turn/stream` (SSE, fork 1) | 404 / 422 pre-stream; after the stream opens, an `error` **event** |
| `DialogueInitAsync` | `POST /v1/dialogue/init` (the warm-init verb) | 404, 422 |
| `ObserveAsync` | `POST /v1/events/observe` | 404 |
| `SceneBoundaryAsync` | `POST /v1/events/scene-boundary` *(since E2 2026-08-19 the event carries the optional C7-B `prewarm_context` probe; `SceneResult.prewarm` — the 13-field `ScenePrewarmInstrumentation` — rides back, null without a probe)* | 404 |
| `SetPinAsync` | `PUT /v1/memories/{id}/pin` | 404 |
| `CorrectAsync` | `POST /v1/memories/{id}/correction` | 404 / 409 CAS conflict / 422 / 502 fail-loud |
| `DiegeticCorrectAsync` | `POST /v1/events/diegetic-correction` (C4, 2026-08-17 — `dissonance.md`) | 404 unknown/foreign memory / 409 CAS / 422 / 502 retell fail-loud |
| `CreateAgentAsync` | `POST /v1/agents` (provisioning, fork 2) | 422 on an empty name |
| `ReflectAsync` | `POST /v1/agents/{id}/reflect` (C2, 2026-08-15 — `reflection.md`) | 404 / 409 below the episode floor / 422 / 502 fail-loud |
| `MemoryChainAsync` | `GET /v1/memories/{id}/chain` (fork 3, unscored) | 404 |
| `AgentMemoriesAsync` | `GET /v1/agents/{id}/memories` (fork 3, unscored) | 404 |
| `ReconstructionMetricsAsync` | `GET /v1/memories/{id}/reconstruction-metrics` (eval-harness stage 1, 2026-07-29; the third unscored-by-contract read) | 404 |
| `AgentStateAsync` | `GET /v1/agents/{id}/state` (C5, 2026-08-17; the FOURTH unscored-by-contract read — the composed runtime snapshot: the stored row as stored, identity currency, the pressure gauge, live beliefs, bundles incl. passthrough, both workers' run logs newest-first capped by `runsLimit`) | 404 |

HTTP errors map to typed exceptions (the Python service-error precedent — never swallowed,
never retried silently). Timeouts are per-route config: `init` must tolerate the cold
reconstruction pre-warm (8.1 s headline, 3.3–8.6 s across the cold snaps — measured 2026-07-29
on the ruled Haiku class, replacing the retired sonnet-5 stopgap's 16.3 s; with C7-B a probed
scene boundary absorbs this cost at the cut, but an unprobed cold init can still pay it — the
timeout stands), `turn` the full turn (~30 s ceiling),
`observe` ~10 s; fire-and-forget observe is the session's job, not hidden retry logic here
(built with C5, 2026-08-17 — the "Async observes" subsection below).

**The null-vs-absent contract is load-bearing** (the panel's sharpest finding): on
`DialogueTurnRequest`, `loaded_memory_ids = null` means **loader turn** and `[]` means **a
loaded set that is empty** — a serializer that emits `null` for an empty list (or omits nulls
wholesale) silently changes gate behavior. The C# DTOs must preserve the tri-state exactly
(present-null / present-empty / value) for every `Optional[...]` field; this is a named
done-when criterion, proven against the live route, not a code comment.

### NpcSession (the ported runner)

Stateful per-NPC session over the client, porting `app\session.py` field-for-field: the frozen
snapshot refresh at boundaries, `_apply_turn_result` keyed on the SERVER's `gate.evaluated` /
`fired` (loader → served IDs seed the loaded set; gated fire → gate-fetched IDs append, streak
resets on productive fetch; closed → untouched), recent-actions append-on-resolved-directive
with the per-agent cap, scene-boundary reset of loaded set + streak + context + recent actions,
`as_of` time travel riding both retrieval and observe timestamps. Surface: `SayAsync(text)`,
`ObserveAsync(text)`, `SceneBoundaryAsync()`, `CorrectAsync(...)`, `ConfrontAsync(...)` (C4 —
the diegetic-correction event at the session's effective time), plus `OnDirective` and
`OnReputationChanged(prev, after)` callbacks. The `(reconstructing…)` during-wait hook exists
only under SSE (fork 1); until then the session surfaces the result's post-hoc reconstruction
fields — no faked signal. *(**A1 re-shape, 2026-08-04:** the snapshot refresh, both callbacks,
and the recent-actions block are removed with the behavior/reputation cut; `SayAsync` gained
the `weightOverrides` weights-on-speech parameter. Gate/loaded-set bookkeeping unchanged.)*
*(**C5, 2026-08-17:** the fire-and-forget observe surface joined — the subsection below.)*

### Async observes (C5, ruled 2026-08-17)

Observe latency was ruled a client concern (`deferred-writes.md` — server-side deferral is
throughput, this is the latency answer), and the session is its ruled home. Four members, no
queue, no pump, ~40 lines:

- **`ObserveAndForget(text)`** — stamps the event at the session's effective time
  **synchronously** (byte-identical event shape to `ObserveAsync`), then the HTTP call runs
  without blocking the caller. The synchronous stamp is what preserves world-time ordering:
  `valid_at` and every product ordering ride the timestamp, so arrival order cannot reorder
  the record. (One honest caveat: an observe fired before a `reflect` but *arriving* after it
  counts toward the new pressure epoch — the gauge thresholds on arrival-side `created_at`.)
- **`PendingObserves`** — the in-flight count (completed trackers pruned on read).
- **`OnObserveFailed(text, error)`** — per-failure surfacing at failure time, on the caller's
  SynchronizationContext (Unity main thread — safe to touch UI).
- **`DrainObservesAsync()`** — awaits every in-flight observe; failures accumulated since the
  last drain re-throw as ONE `AggregateException` (a stable type even for a single failure;
  inners are the typed `NpcMemoryApiException`s) and then clear — draining is how the
  integrator acknowledges. No retry anywhere; failures are never swallowed, with or without a
  subscriber.

**No verb auto-drains, by ruling** — no hidden multi-second await inside an on-camera verb.
Integrator guidance: **drain at scene edges** (the reflect-at-scene-edges shape); the E2 beat
script places the actual drains (beat 3: an explicit Drain before the
scene boundary). An un-drained observe is bi-temporally safe — it lands
with the correct world time, it is merely not yet retrievable until it arrives. Orthogonal to
C1's server-side deferred writes: deferral shortens the round trip, fire-and-forget hides it —
they compose, and nothing backend changed for this half of C5.

### Console harness (the Wk-1 gate)

A `dotnet run` console app driving `NpcSession` against `python -m app.serve` through every
demo beat headless: observe → loader turn (IDs + scores + `read_mode` printed) → `:correct`
head-swap → the corrected memory's retrieval move visible in scores → `as_of` jump + scene
boundary → reconstructed serve + call-free cache-hit reread → gate fire mid-scene →
warm-init (`DialogueInitAsync` at a jumped basis, then the on-camera-equivalent read hitting
cache) → a `weight_overrides` divergence turn *(since the A1 re-shape 2026-08-04: the
weights-on-speech pair — parity at default weights, then an override re-ranking the view that
feeds the prose prompt over the same served set)* → the reflect verb + its 409 floor (C2) →
the compiled-parameter scene-type echo contract (C3) → the diegetic-correction event (C4:
verb + IDs over the wire, both decision sides recomputed client-side from the echoed inputs,
the chain read's correction record, the 409 CAS) → the agent-state read (C5: the stored row
as stored, identity currency agreeing with the session's frozen version, the endpoint/worker
split visible as empty run logs, the 404) → fire-and-forget observes (C5: fires return with
calls in flight, a dialogue turn completes without draining, the drain joins, both rows land
in CALL-time world order, and the bogus-agent failure path re-throws typed at drain) → the
scene-boundary pre-warm (E2, 2026-08-19 — `verify_prewarm.py` A/B/C mirrored over the C#
wire: a probed boundary returns a clean prewarm record, the same-basis init is a call-free
cache hit, a probe-less boundary carries no record). Debug
output mirrors the REPL's debug view (IDs, scores, gate line, both TTFT fields, cost row).
Passing this end-to-end IS the interop go/no-go.

### Unity adapter + gray-box scene

Thin `MonoBehaviour` wrapper under `Assets\Scripts\` (`NpcMemory` namespace): async calls
marshaled back to the main thread (Unity's SynchronizationContext — awaits resume on the main
thread; no blocking `.Result`/`.Wait()` anywhere), dialogue text to a world-space or overlay
TMP field, directive callback driving a visible acknowledgment (nameplate flash / simple move),
reputation callback to a debug readout *(both callbacks and their driver wiring removed by the
A1 re-shape, 2026-08-04)*, scene-boundary emission wired to the camera-cut /
scene-change points. MCP for Unity connects at this step (the setup runbook lives in the
local record) with an **early
one-hour verification** (the bridge has never been connected; note that scene-manipulation
operations fail during Play mode, so the Play-mode debug loop is partly
stop/start).

### The Ledger (browser page)

The designer-facing ground-truth-vs-telling inspector, served beside the game and composited
in OBS: original vs current telling side by side, superseded rows greyed-but-present,
`read_mode` / scores / memory IDs per served item, and a real gist/detail number on screen.
It binds the SAME `DialogueTurnResult` / `RetrievalResult` fields the eval harness (item 3)
will score — the on-screen number and the paper number are one object. Data source is fork 3.
*Addendum (2026-08-13, with the interim public README):* the page reads two deep-link params —
`?agent=<uuid>` preloads the index (build-settled with stage 3) and `&memory=<uuid>` opens that
memory's chain view directly (added for the README's capture; also a demo-choreography hook —
a scene cut can land on a specific chain).

### Demo choreography hooks (ride here, no new backend)

~~Off-camera warm-init during camera cuts (one throwaway `DialogueInitAsync` per scene-basis
jump — kills the cold stall with zero pre-warm code)~~ *(retired: C7-B's probed scene
boundary IS the pre-warm — the beat-2 boundary carries `prewarm_context` and the cold stall
never reaches camera; harness beat [9] still exercises the old trick as a working pattern)*;
the game-authored action-observe beat +
async observes (the old pre-ship (d): the client fires observes without blocking dialogue —
**built with C5, 2026-08-17**: `ObserveAndForget` + drain-at-scene-edges, the subsection
above; the beat's driver staging stays E2's);
the demo corpus authored in **shipped-game dialogue register**, not driver prose (the
construct-validity mitigation — escalation fired 79% on realistic prose vs 0% on synthetic in
the 2026-07-21 pre-thin_gist measurement, ~95% on the corpus at current defaults; the
held-out corpus arm rides item 3's eval build).

## Open forks — RESOLVED (ruled by Jack at plan approval 2026-07-27, forks 1–6; fork 7 + the
## sub-shapes settled at build as authorized)

> 1 SSE **in** (built, stage 0) · 2 `POST /v1/agents` **in** (built, stage 0) · 3 Ledger data =
> **the chain read route** (built, stage 0) · 4 **Newtonsoft everywhere** · 5 **targets/layout
> as proposed** (`unity\` settled by Jack's project creation) · 6 **static HTML + vanilla JS**
> — build-settled sub-shapes: the page is served BY the API at `GET /ledger` (same origin, no
> CORS, ships with the service) and the turn feed v1 is paste/drop of a `DialogueTurnResult`
> JSON (a live feed rides the demo choreography) · 7 **IMGUI dev-tool overlay** + primitive
> set with nameplate (settled at build). The original fork text below stands as specced.

1. **SSE `/v1/dialogue/turn/stream` — in scope now, or deferred?** Without it there is NO
   on-screen streaming: the non-streaming route returns whole turns (~4 s real-mode), so the
   **<1 s perceived-first-word beat is unrecordable** and the during-wait `(reconstructing…)`
   hook has no carrier. The route is small by design — it iterates the SAME async generator
   (`event: chunk` per str, `event: result` terminal; the 2026-07-23 build stated "no
   rewrite"), plus the C# consumption side. The alternative — record latency numbers from the
   CLI instead of the game view — weakens the headline beat. **Recommended: in scope.**
2. **Agent provisioning — `POST /v1/agents`, or hand-SQL for the demo?** No route exists
   today; the demo agent is provisioned by hand-SQL, which an integrator hits in minute one.
   The architecturally correct option is a small create-agent route (name, seed identity,
   config knobs — server-minted UUID per the stack constants); its real cost is one route +
   wire models + walker/suite growth, no migration (`agents` exists). Deferring keeps the
   demo unblocked but ships the gap into the public flip. **Recommended: in scope (small).**
3. **The Ledger's data source.** The turn/init payloads carry served items + scores, but the
   side-by-side needs each memory's telling CHAIN (original + superseded heads), which no
   route serves. Options: **(a)** the Ledger's tiny server reads Postgres read-only directly —
   fastest, demo-grade, adds no API surface, but the inspector then isn't part of the product
   an integrator gets; **(b)** a read-only `GET /v1/memories/{id}/chain` (+ optionally a
   per-agent memory list) — the architecturally correct product surface (the inspector data
   becomes part of the API; IDs + scores discipline already governs read endpoints), costing
   one route + wire models + walker growth, no migration. **Recommended: (b).**
4. **C# JSON serializer.** Unity's `JsonUtility` cannot express the contract (no `Guid`, no
   nullable value types, no dicts, no ISO-8601 offsets). Options: Newtonsoft everywhere (the
   Unity-shipped `com.unity.nuget.newtonsoft-json` package; one serializer, one behavior in
   both hosts) vs `System.Text.Json` (faster, but IL2CPP/AOT hazards in Unity). Tri-state
   null-vs-absent handling must be explicit either way. **Suggested: Newtonsoft everywhere.**
   `[SETTLE-AT-BUILD]`
5. **Targets + repo layout.** Suggested: `client\NpcMemory.Core\` as **netstandard2.1** (the
   Unity 6 compatibility profile), `client\NpcMemory.Harness\` as a net8.0 console app, the
   Unity project under `unity\` with the adapter in `Assets\Scripts\`. `[SETTLE-AT-BUILD]`
6. **Ledger page stack.** Suggested: a single static HTML page + vanilla JS polling the API
   (or the fork-3 chain route), no framework, no build step — readable-as-documentation, the
   CLI precedent. `[SETTLE-AT-BUILD]`
7. **Unity dialogue-render shape** (world-space vs overlay text, how the directive is made
   visible on camera). Demo-choreography detail. `[SETTLE-AT-BUILD]`

## Done-when (the build's floor)

1. `NpcMemory.Core` compiles with **zero `UnityEngine` references**; the public surface is the
   flat client + `NpcSession` + DTOs, nothing else.
2. **Wire-contract parity proven, tri-state included**: round-trip tests for every request DTO
   against the live service — including `loaded_memory_ids` present-null (loader turn) vs
   present-empty vs populated, each visibly changing gate behavior in the returned
   instrumentation — and every response field of `DialogueTurnResult` / `IngestResult` /
   `CorrectionResult` / `SceneResult` / `PinResult` / `RetrievalResult` deserialized without
   loss *(+ `ReconstructionMetricsResult` since 2026-07-29 — eval-harness stage 1; noted
   2026-08-07 audit)*.
3. **`NpcSession` bookkeeping parity with `app\session.py`**: driven by the same fixture
   sequence of turn results (loader / gated-fire productive / gated-fire fruitless / closed /
   directive present / dropped), the C# scene state matches the Python runner's field-for-field,
   including scene-boundary resets and the recent-actions cap.
4. **The console harness completes every demo beat headless** against the served API (fake and
   real mode), printing IDs + scores + `read_mode` + both TTFT fields + the cost row — the
   Wk-1 interop go/no-go, recorded in the session log with receipts.
5. **Unity Play mode**: a full turn from the gray-box scene with dialogue text on screen,
   directive + reputation callbacks firing *(callbacks removed by the A1 re-shape 2026-08-04 —
   this criterion's callback clause is historical)*, and the main thread never blocked (no
   `.Result`/`.Wait()`; interaction stays responsive during a turn).
6. **Scene-boundary + warm-init choreography proven in-engine**: boundary emission at the
   scene edge refreshes frozen state; an off-camera `DialogueInitAsync` at a jumped basis makes
   the next on-camera read a call-free cache hit with byte-identical within-scene rereads.
7. **The Ledger renders live**: side-by-side original vs current telling, superseded rows
   greyed-but-present, `read_mode`/scores/IDs, and the gist/detail number — bound to the same
   fields item 3 scores.
8. **Degradation honesty**: dropped directives, degraded turns, and correction-verb failures
   (409/502) surface in the harness output and Unity debug readout — never swallowed.
9. **The Python floor is untouched or grown only as ruled**: walkers + suite green; no-arg
   migrate still a no-op (unless a fork ruled a route in, in which case its walker/suite
   growth and re-verification are named in the build plan); `longmem` pristine after
   verification; no invariant violated (the client sends only the sanctioned verbs).
10. Docs propagated (status.md, architecture markers, this spec's ruling annotations) and the
    floor-verifier passes on the touched floors.
