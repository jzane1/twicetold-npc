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
