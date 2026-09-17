# Village NPC integration seam

`VillageScene` creates its five characters during `VillageSceneBootstrap.Awake`. Backend adapters
should discover them in `Start` (or later) through `VillageNpcAnchor`; the scene has no dependency on
the NPC package or on `SampleScene`.

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
