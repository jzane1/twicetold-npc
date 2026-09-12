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
