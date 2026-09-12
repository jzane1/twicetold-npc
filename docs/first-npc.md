# Your first NPC

This is the page for the person wiring twicetold-npc into a game. It's about thirty lines of
C# once the service is running, and the order of the calls matters more than the calls
themselves, so I'll give you the order and the why. `SETUP.md` gets the service running;
`identity-authoring.md` is how to write a character worth remembering things for.

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
using NpcMemory.Unity;
using UnityEngine;

public sealed class TavernScene : MonoBehaviour
{
    [SerializeField] private NpcMemoryNpc innkeeper;
    [SerializeField] private DialogueBox box;

    // Gameplay tells the character what happened to her. Returns at once:
    // the write lands in the background, timestamped now.
    public void OnPlayerPaidTheTab(int shillings) =>
        innkeeper.ObserveAndForget($"The traveler paid {shillings} shillings for the room.");

    // The player speaks. Prose streams into the box; the result carries the
    // memory IDs and scores the line was built from.
    public async void OnPlayerSaid(string line)
    {
        var result = await innkeeper.SayStreamAsync(
            line,
            onChunk: box.Append,
            onReconstructing: () => box.ShowThinking());
        Debug.Log($"read_mode per item: {result.Items.Count} served");
    }

    // Scene edge. Drain first so this scene's observes have landed, then the
    // boundary: it freezes identity for the next scene and can pre-warm the
    // retellings the next scene will need.
    public async void OnSceneEnd()
    {
        await innkeeper.DrainObservesAsync();
        await innkeeper.SceneBoundaryAsync("tavern", prewarmContext: "the road north");
    }
}
```

That's it. Every async call marshals back to the Unity main thread; there is no `.Result` or
`.Wait()` anywhere in the client, and there shouldn't be in yours.

## 3. The order, and why

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
own clock, set `AsOf` on the session before you observe or speak (`SetAsOf` on the adapter)
and every observe is stamped with that time and every retrieval decays against it. Set it
every session; it is per session, not stored. Move it forward and the character genuinely
forgets detail; move it back and you are asking what she knew then.

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
relevance × recency × importance, its `read_mode` (`stored` or `reconstructed`), and the
timings and token counts for the turn. Log them. The Ledger (`/ledger?agent=<uuid>`) shows the
same record for any memory ID you paste in, which is how you'll debug a line you didn't
expect.

When the character says something you know is wrong, that's an authorial correction
(`CorrectAsync(memoryId, text)`): retrieval follows the fix from the next turn, and the old
telling stays on the record. `shipping.md` covers what to do before players ever meet her.
