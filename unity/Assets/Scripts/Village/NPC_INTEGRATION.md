# Village NPC integration seam

`VillageScene` creates its five characters during `VillageSceneBootstrap.Awake`. Backend adapters
should discover them in `Start` (or later) through `VillageNpcAnchor`; the scene has no dependency on
the NPC package or on `SampleScene`.

The environment is now saved prefab scenery. The bootstrap's serialized market,
riverside-home and event-bench landmarks determine the same actor/event positions;
do not replace those references when swapping only artwork. NPC construction timing,
stable IDs, hand sockets and callbacks are unchanged by the environment migration.

## Stable characters

| Stable ID | Character | Demo focus | Dialogue enabled | Role |
| --- | --- | --- | --- | --- |
| `henry` | Henry | yes | yes | produce merchant |
| `joan` | Joan | yes | yes | riverside resident |
| `fisherman` | Fisherman | no | no | gold-event actor |
| `mara` | Mara | no | no | ambient baker |
| `rowan` | Rowan | no | no | ambient woodworker |

Use `VillageNpcAnchor.StableId`, not the generated GameObject name, as the durable lookup key.
`BackendAttachmentPoint` is an empty child reserved for adapter-owned components or presentation
objects that should follow the character.

## Dialogue

Walking close to Henry or Joan, looking toward them, and pressing `E` calls
`VillageNpcAnchor.RequestDialogue`. Subscribe to `DialogueRequested` to open the backend-owned
dialogue UI or session. The village itself deliberately supplies no dialogue text and creates no
backend agent.

## Observation event

`VillageGoldEventDirector` starts when the player approaches the market bench. After the fisherman
has placed the gold, checked his tackle, stood, and walked away, Henry and Joan turn toward the bag.
That same beat calls `ReportObservation` on both anchors and raises `ObservationReported` with:

- event ID: `forgotten-gold-at-market-bench`
- an observer-specific summary naming the fisherman and the bag of gold coins
- the bag's world position and current scene time

The event ID is stable across replays so an adapter can deduplicate recording attempts. Press `R`
after completion to reset and replay the scene choreography.

Presentation pacing: the trigger radius is 17 metres from the bench; the sequence takes about
13 seconds after it starts. The witnesses react once the fisherman is 4.5 metres away, while
he continues along his departure route. Their callbacks follow the start of the visible turn
by 0.35 seconds. Reset clears `LastObservation` on both focus anchors, but does not undo or
delete anything recorded by an external adapter.

Characters are approximately 1.7–1.8 metres tall, using real skinned Humanoid rigs and
imported animations. `VillageRigPresentation` is an art-only adapter beneath the
stable root; it neither records memories nor handles dialogue. Treat
the visual rig as replaceable: use the stable anchor, hand transforms, and attachment point,
not clothing mesh names or body dimensions. Presentation movement is local choreography;
it does not call a backend or write a memory database.

## Minimal adapter pattern

```csharp
private void Start()
{
    foreach (var anchor in FindObjectsByType<VillageNpcAnchor>(FindObjectsSortMode.None))
    {
        if (!anchor.IsDemoFocus) continue;
        anchor.DialogueRequested += BeginBackendDialogue;
        anchor.ObservationReported += RecordBackendObservation;
    }
}
```

Keep the backend adapter outside the village scripts. The scene's contract ends at these two events
and the stable attachment transform.
