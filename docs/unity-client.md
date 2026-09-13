# twicetold-npc: Unity client

The client side of twicetold-npc ships in four parts:

1. **`NpcMemory.Core`**, an engine-agnostic .NET class library: HTTP + JSON plus `NpcSession`, the
   scene-state bookkeeping. It has **zero `UnityEngine` types** and one flat client class, no
   abstraction ceremony.
2. **A `dotnet run` console harness** that drives the core through every integration beat headless
   against a live backend. It is the wire-contract go/no-go, provable without opening Unity.
3. **A Unity adapter plus a gray-box reference scene**: a thin MonoBehaviour wrapper over the core,
   plus one room, an NPC with a nameplate, and dialogue text on screen. No navmesh, no animation, no
   art on the critical path.
4. **The Ledger**, a browser page (not Unity UI) that shows ground truth beside the character's
   telling.

The client ships as an embedded Unity package at `unity\Packages\com.jacksonzane.twicetold-npc\`
(`Runtime\Core` the engine-agnostic core, `Runtime\` the adapter). `first-npc.md` is the thirty-line
integration; `shipping.md` is the hosting and platform guide.

## Principles

- **The server is stateless; the client owns scene state.** Four scene-state groups ride the request
  (`identity_version` + `scene_started_at`, `loaded_memory_ids` + `gate_fruitless_streak`, the
  context fields, `as_of`). `NpcSession` is the one place that bookkeeping lives, mirroring
  `app\session.py` exactly.
- **Nothing integrator-configurable is hardcoded:** base URL, per-route timeouts, k, weight
  overrides are all constructor or config surface. No hardcoded model names or pricing anywhere in C#.
- **IDs and scores are always surfaced.** The client exposes the full structured results (items with
  memory IDs, scores, `read_mode`; the weighted view; instrumentation), never prose-only.
- **Structural tests only.** C# tests assert structure (IDs, flags, state transitions), never model
  prose: the suite discipline carried across the language boundary.
- **Instrument at the seam.** The client records one client-side term per call
  (`NpcMemoryClient.ClientTotalMs`, wall time around the HTTP call, plus an `OnCallMeasured(path, ms)`
  event) beside the server's instrumentation, so transport overhead is visible from day one. It is
  client-side only and never rides the wire.

## NpcMemory.Core (the flat client)

`NpcMemoryClient` exposes stateless verbs mirroring the routes 1:1, pass-through both ways: request
models serialize exactly what the service accepts, and response models deserialize every field it
returns.

| Verb | Route | Errors surfaced |
|---|---|---|
| `DialogueTurnAsync` | `POST /v1/dialogue/turn` | 404 unknown agent, 422 unknown identity version |
| `DialogueTurnStreamAsync` | `POST /v1/dialogue/turn/stream` (SSE) | 404 / 422 pre-stream; after the stream opens, an `error` **event** |
| `DialogueInitAsync` | `POST /v1/dialogue/init` | 404, 422 |
| `ObserveAsync` | `POST /v1/events/observe` | 404 |
| `SceneBoundaryAsync` | `POST /v1/events/scene-boundary` (carries the optional `prewarm_context` probe; `SceneResult.prewarm`, the `ScenePrewarmInstrumentation`, rides back, null without a probe) | 404 |
| `SetPinAsync` | `PUT /v1/memories/{id}/pin` | 404 |
| `CorrectAsync` | `POST /v1/memories/{id}/correction` | 404 / 409 CAS conflict / 422 / 502 fail-loud |
| `DiegeticCorrectAsync` | `POST /v1/events/diegetic-correction` | 404 unknown or foreign memory / 409 CAS / 422 / 502 retell fail-loud |
| `CreateAgentAsync` | `POST /v1/agents` | 422 on an empty name |
| `ReflectAsync` | `POST /v1/agents/{id}/reflect` | 404 / 409 below the episode floor / 422 / 502 fail-loud |
| `MemoryChainAsync` | `GET /v1/memories/{id}/chain` (unscored) | 404 |
| `AgentMemoriesAsync` | `GET /v1/agents/{id}/memories` (unscored) | 404 |
| `ReconstructionMetricsAsync` | `GET /v1/memories/{id}/reconstruction-metrics` (unscored) | 404 |
| `AgentStateAsync` | `GET /v1/agents/{id}/state` (unscored; the composed runtime snapshot) | 404 |

HTTP errors map to typed exceptions (`NpcMemoryApiException` carrying the status code), never
swallowed and never retried silently. Timeouts are per-route config: `init` must tolerate the cold
reconstruction pre-warm (single-digit seconds; a probed scene boundary absorbs this cost at the cut,
but an unprobed cold init can still pay it), `turn` the full turn (about a 30 s ceiling), `observe`
about 10 s. Fire-and-forget observe is the session's job, not hidden retry logic in the client.

**The null-vs-absent contract is load-bearing.** On `DialogueTurnRequest`, `loaded_memory_ids = null`
means a **loader turn** and `[]` means **a loaded set that is empty**. A serializer that emits `null`
for an empty list, or omits nulls wholesale, silently changes gate behavior. The C# DTOs preserve the
tri-state exactly (present-null / present-empty / value) for every optional field; this is proven
against the live route, not asserted in a comment.

## NpcSession (the ported runner)

A stateful per-NPC session over the client, porting `app\session.py` field-for-field: the frozen
snapshot refresh at boundaries, `_apply_turn_result` keyed on the server's `gate.evaluated` / `fired`
(loader, the served IDs seed the loaded set; gated fire, gate-fetched IDs append and the streak
resets on a productive fetch; closed, untouched), scene-boundary reset of the loaded set, streak, and
context, and `as_of` time travel riding both retrieval and observe timestamps.

Surface: `SayAsync(text, weightOverrides)` and its streaming twin `SayStreamAsync`, `ObserveAsync`,
`SceneBoundaryAsync`, `CorrectAsync`, `ConfrontAsync` (the diegetic-correction event at the session's
effective time), `ReflectAsync`, and `PinAsync`. `weightOverrides` carries the weights-on-speech
parameters (architecture.md §9). The `(reconstructing...)` during-wait hook is available under the SSE
verb; the non-streaming path surfaces the result's post-hoc reconstruction fields instead, never a
faked signal.

## Async observes

Observe latency is a client concern (server-side deferral, `deferred-writes.md`, answers throughput;
this answers latency), and the session is its home. Four members, no queue, no pump:

- **`ObserveAndForget(text)`** stamps the event at the session's effective time **synchronously**
  (byte-identical event shape to `ObserveAsync`), then runs the HTTP call without blocking the caller.
  The synchronous stamp preserves world-time ordering: `valid_at` and every product ordering ride the
  timestamp, so arrival order cannot reorder the record. (One caveat: an observe fired before a
  `reflect` but arriving after it counts toward the new pressure epoch, since the gauge thresholds on
  arrival-side `created_at`.)
- **`PendingObserves`** is the in-flight count (completed trackers pruned on read).
- **`OnObserveFailed(text, error)`** surfaces each failure at failure time, on the caller's
  SynchronizationContext (the Unity main thread, safe to touch UI).
- **`DrainObservesAsync()`** awaits every in-flight observe; failures accumulated since the last drain
  re-throw as ONE `AggregateException` (a stable type even for a single failure; the inners are typed
  `NpcMemoryApiException`s) and then clear. Draining is how the integrator acknowledges. There is no
  retry anywhere, and failures are never swallowed, with or without a subscriber.

**No verb auto-drains:** there is no hidden multi-second await inside an on-camera verb. Guidance:
**drain at scene edges**. An un-drained observe is bi-temporally safe, landing with the correct world
time; it is merely not retrievable until it arrives. This is orthogonal to server-side deferred
writes: deferral shortens the round trip, fire-and-forget hides it, and they compose.

## The console harness

A `dotnet run` console app driving `NpcSession` against `python -m app.serve` through every
integration beat headless: observe, then a loader turn (IDs, scores, and `read_mode` printed), a
correction head-swap and the corrected memory's retrieval move visible in scores, an `as_of` jump
plus scene boundary, a reconstructed serve and a call-free cache-hit reread, a mid-scene gate fire, a
warm init at a jumped basis hitting cache, a weights-on-speech pair (parity at default weights, then
an override re-ranking the prose-prompt view over the same served set), the reflect verb and its 409
episode floor, the compiled-parameter scene-type echo, the diegetic-correction event (both decision
sides recomputed client-side from the echoed inputs, the chain read's correction record, the 409 CAS),
the agent-state read, fire-and-forget observes (fires return with calls in flight, a dialogue turn
completes without draining, the drain joins, both rows land in call-time world order, and a
bogus-agent failure re-throws typed at drain), and the scene-boundary pre-warm (a probed boundary
returns a clean prewarm record, the same-basis init is a call-free cache hit, a probe-less boundary
carries no record). Debug output mirrors the REPL's debug view (IDs, scores, gate line, both TTFT
fields, cost row). Passing this end to end is the interop go/no-go.

## The Unity adapter + gray-box scene

`NpcMemoryNpc` (namespace `NpcMemory.Unity`) is a thin `MonoBehaviour` wrapper over the core: async
calls marshal back to the main thread (Unity's SynchronizationContext, so awaits resume on the main
thread and there is no blocking `.Result` or `.Wait()` anywhere), dialogue text goes to a world-space
or overlay field, and scene-boundary emission is wired to the camera-cut and scene-change points. The
gray-box scene is the dev-tool aesthetic: primitives, a nameplate, static camera positions.
`NpcDemoDriver` (an IMGUI dev-tool overlay plus scripted verification beats) stays under
`Assets\Scripts\` as the project dev rig and is not part of the shipped package.

## The Ledger

The designer-facing ground-truth-versus-telling inspector, served beside the game by the API at
`GET /ledger` and composited in a capture tool: original versus current telling side by side,
superseded rows greyed but present, `read_mode`, scores, and memory IDs per served item, and a real
gist/detail number on screen. It binds the same `DialogueTurnResult` / `RetrievalResult` fields the
eval harness scores, so the on-screen number and the evaluation number are one object. It reads two
deep-link params: `?agent=<uuid>` preloads the per-agent index, and `&memory=<uuid>` opens that
memory's chain view directly.
