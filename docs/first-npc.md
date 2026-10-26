# Your first NPC

[All guides](README.md) | [Python integration](python-integration.md)

To try the whole lifecycle before writing client code, run [the first-run Compose demo](first-run.md).
It includes a small executable Python HTTP example, fake and real providers, and a populated Ledger.

For an existing application that owns its dialogue model and recent conversation, use the
[standalone Python integration](python-integration.md). This page covers the Unity client path.

This is the page for the person wiring twicetold-npc into a game. The starter C# sample includes
readiness and failure handling. The order of the calls matters more than the calls themselves,
so I'll give you the order and the why. [Setup](SETUP.md) gets the service running;
[identity authoring](identity-authoring.md) is how to write a character worth remembering things for.

## What you're wiring

The service holds the record. Your game owns three things: the agent's UUID (the character),
the scene edges (when a scene starts and ends), and the clock (whether the character lives on
wall time or game time). Everything else, the retrieval, the retelling, the decay, is the
service's job, and every reply tells you what it did.

## 1. Create the agent, and keep the UUID

```http
POST /v1/agents
Content-Type: application/json

{
  "name": "branwen-waystone",
  "seed_identity": "I am Branwen, and I keep the Waystone Inn where the north road crosses the drove way...",
  "diagnosticity_goal": "what threatens the house, who owes it, and what news the road brings",
  "rigidity": 1.0,
  "config": {
    "decay_classes": { "episodic": 604800, "semantic": 2592000 },
    "decay_class_default": "episodic"
  }
}
```

Only `name` is required; every other field has a default. The response carries `agent_id`,
minted server-side. **Store it in your save file.** The UUID is the character: re-attach to it
next session and the record is there, and lose it and the record is orphaned (there is no
lookup by name on purpose). The two taus above are seconds: a week for episodic memories, a
month for semantic ones. That's the decay clock, and it's per agent, so a gossip and a monk
can forget at different speeds.

## 2. The MonoBehaviour

The client ships as an embedded Unity package at
`unity\Packages\com.jacksonzane.twicetold-npc`. Install it through the Package Manager (Install
package from git URL, with `?path=unity/Packages/com.jacksonzane.twicetold-npc`, forward
slashes) or copy the folder into your project's `Packages`; the First NPC sample mirrors this
page and ships the `link.xml` that IL2CPP builds need. The package's `NpcMemoryNpc`
(`Runtime\NpcMemoryNpc.cs`) is a thin adapter over the engine-agnostic `NpcMemory.Core` client.
Drop it on the NPC's GameObject, set `baseUrl`,
and either let it provision (`autoProvision` on, with a name and seed identity in the
inspector) or attach it to a saved character (`autoProvision` off, `agentIdOverride` set).
Then this is the whole integration:

```csharp
using System;
using System.Threading;
using System.Threading.Tasks;
using NpcMemory.Unity;
using UnityEngine;

public sealed class TavernScene : MonoBehaviour
{
    [SerializeField] private NpcMemoryNpc innkeeper;
    [SerializeField] private DialogueBox box;
    private readonly CancellationTokenSource _lifetime = new CancellationTokenSource();
    private readonly SemaphoreSlim _actions = new SemaphoreSlim(1, 1);
    private int _pendingActions;

    // Bind gameplay/dialogue controls to this flag; initialization can fail.
    public bool CanInteract => innkeeper.Ready && _pendingActions == 0;

    private async void Start()
    {
        try
        {
            // SetAsOf(gameTime) before this await if the game owns the clock.
            await innkeeper.ReadyTask;
            if (!_lifetime.IsCancellationRequested)
                innkeeper.Session.OnObserveFailed += ObserveFailed;
        }
        catch (Exception exc) { if (!_lifetime.IsCancellationRequested) Debug.LogException(exc, this); }
    }

    private void ObserveFailed(string text, Exception exc) => Debug.LogException(exc, this);

    public void OnPlayerPaidTheTab(int shillings)
    {
        // Never delay and re-stamp a gameplay event while loading.
        if (!CanInteract) throw new InvalidOperationException("Enable gameplay after ReadyTask completes.");
        innkeeper.ObserveAndForget($"The traveler paid {shillings} shillings for the room.");
    }

    public async void OnPlayerSaid(string line) => await Run(async () =>
    {
        var result = await innkeeper.SayStreamAsync(
            line, onChunk: box.Append, onReconstructing: box.ShowThinking,
            ct: _lifetime.Token);
        Debug.Log($"read_mode per item: {result.Items.Count} served");
    });

    public async void OnSceneEnd() => await Run(async () =>
    {
        await innkeeper.DrainObservesAsync(_lifetime.Token);
        await innkeeper.SceneBoundaryAsync("tavern", prewarmContext: "the road north", ct: _lifetime.Token);
    });

    private async Task Run(Func<Task> action)
    {
        // Queue scene edges behind a pending turn; never silently lose a boundary.
        _pendingActions++;
        var entered = false;
        try
        {
            await _actions.WaitAsync(_lifetime.Token);
            entered = true;
            await innkeeper.ReadyTask;
            _lifetime.Token.ThrowIfCancellationRequested();
            await action();
        }
        catch (OperationCanceledException) when (_lifetime.IsCancellationRequested) { }
        catch (Exception exc) { Debug.LogException(exc, this); }
        finally
        {
            if (entered) _actions.Release();
            _pendingActions--;
        }
    }

    private void OnDestroy()
    {
        _lifetime.Cancel();
        if (innkeeper != null && innkeeper.Session != null)
            innkeeper.Session.OnObserveFailed -= ObserveFailed;
    }
}
```

That's it. Every async call marshals back to the Unity main thread; there is no `.Result` or
`.Wait()` anywhere in the client, and there shouldn't be in yours.

## 3. The order, and why

- **Await readiness before enabling gameplay.** `ReadyTask` provisions or attaches the agent and
  freezes the first scene identity and time. All callers share its success or failure; no Unity
  script execution order is required. Async adapter methods also await readiness;
  `ObserveAndForget` requires it first so an event is never silently delayed and re-stamped.
  Bind controls to `CanInteract` in the sample, and serialize turns and scene boundaries per NPC.
- **Observe from gameplay, not from dialogue.** The character learns what happened to her
  from your game's events (the tab paid, the door barred, the rumor overheard), stamped with
  the time it happened. `ObserveAndForget` returns immediately so dialogue never blocks on a
  write; `PendingObserves` tells you how many are in flight, and `Session.OnObserveFailed`
  hands you a failure on the main thread if one lands badly.
- **Talk with the streaming call.** `SayStreamAsync` streams the prose chunk by chunk and
  fires `onReconstructing` when a mid-scene retelling is about to block the line, which is
  the moment to show the character thinking. The non-streaming `SayAsync` returns the same
  result after the fact. A dialogue turn persists nothing: the character does not remember
  the conversation unless your game observes it.
- **Drain, then boundary, at the scene edge.** No call auto-drains, by ruling: a hidden join
  inside a dialogue turn would be a hidden stall. Drain where you can afford to wait, then
  fire the boundary. The boundary freezes the identity version the next scene reads, clears
  the loaded set so the next line is a full retrieval, and, given a `prewarmContext`, retells
  the memories that context will pull so the next scene's first line is a cache hit.

## 4. Time

By default the character lives on wall time: a memory observed on Tuesday is three days old
on Friday, and decay follows real calendar time between play sessions. If your game has its
own clock, set `AsOf` before `InitializeAsync` on the session (`SetAsOf` before awaiting
`ReadyTask` on the adapter)
and every observe is stamped with that time and every retrieval decays against it. Set it
every session; it is per session, not stored. Moving it forward ages detail.

**`AsOf` is a scoring/aging clock, not a historical-knowledge query.** Retrieval uses current
live memory and fact heads. Moving the clock backward still allows newer memories (their age
is clamped to zero), still serves later corrections, and does not undo reconstruction,
reflection or identity changes. Use the Ledger and `/v1/memories/{id}/chain` to inspect stored
history; the dialogue API does not reconstruct what the character knew at a past instant.

## 5. Two contracts worth knowing

- **The session owns the request state.** `loaded_memory_ids` is `null` on a loader turn and
  `[]` on a loaded-but-empty scene, and the service treats those differently. Go through
  `NpcSession` (the adapter does) rather than hand-rolling `DialogueTurnRequest`, and that
  distinction is kept for you.
- **Model calls are capped per process.** `TWICETOLD_MAX_CONCURRENT_MODEL_CALLS` (default 8)
  bounds the model calls in flight, and a streaming turn holds one slot for its whole life.
  Nine characters talking at once means one waits; the wait shows up as `gate_wait_ms` in
  the turn's instrumentation, so you can see it rather than guess.

## 6. What you get back

Every `DialogueTurnResult` carries the served memory IDs, each item's score decomposed as
relevance × recency × importance, its `read_mode` (`verbatim` or `reconstructed`), and the
timings and token counts for the turn. Log them. The Ledger (`/ledger?agent=<uuid>`) shows the
same record for any memory ID you paste in, which is how you'll debug a line you didn't
expect.

When the character says something you know is wrong, that's an authorial correction
(`CorrectAsync(memoryId, text)`): retrieval follows the fix from the next turn, and the old
telling stays on the record. `shipping.md` covers what to do before players ever meet her.

## 7. Retrying an observation safely

For delivery you may retry, build and persist one `ObserveEvent` before sending it. Include an
`EventId` unique within that agent (a game-event UUID is suitable), keep its timestamp and all
other fields unchanged, and use `NpcMemoryClient.ObserveAsync(evt, ct)`. If the response is lost,
retry that same payload with bounded backoff. A successful duplicate returns the original
acknowledgement with the same memory ID and no second write or model call. Reusing the key for
a changed payload returns HTTP 409; an empty, blank or over-200-character key returns 422.

```csharp
var evt = new NpcMemory.ObserveEvent
{
    AgentId = savedAgentId,
    EventId = savedGameEventId,
    ObservationText = "The traveler paid for the room.",
    PhaseTag = "tavern",
    ClientTimestamp = savedEventTime,
    Provenance = "lived",
};
// Persist evt in your delivery queue before sending. Retry this same object/payload.
var receipt = await client.ObserveAsync(evt, cancellationToken);
```

The text-only session/adapter convenience methods create new, unkeyed events and never retry
automatically. Do not use them for resending an uncertain write. Unkeyed requests retain their
original behavior: each successful call creates a memory. Only observations have this retry
contract; scene boundaries, provisioning and corrections do not gain it.

Receipts persist until their memory is purged. Stop queued retries before purging, because purge
also deletes the receipt and a later delivery can recreate the memory. Replayed flags and detail
IDs describe the original acknowledgement, even after correction or deferred enrichment; inspect
the memory for current state. Migration 011 enables receipts for new keyed writes; old events
cannot be deduplicated retroactively.
