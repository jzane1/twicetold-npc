using System;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace NpcMemory.Unity
{
    /// <summary>
    /// The thin MonoBehaviour adapter over the engine-agnostic core
    /// (unity-client.md stage 2, ruled 2026-07-27; re-shaped by A1
    /// 2026-08-04 — the directive/reputation surface left with the
    /// behavior/reputation removal): one component holding the flat client
    /// + the NpcSession, exposing thin async passthroughs. All scene state
    /// lives in the session (the server is stateless by ruling); this class
    /// adds ONLY Unity lifecycle + inspector config.
    ///
    /// Main-thread rule: never .Result / .Wait(). Awaits started from the
    /// main thread resume on Unity's SynchronizationContext, so callbacks
    /// (chunks) land on the main thread without explicit marshaling — the
    /// demo driver asserts this in Play mode.
    /// </summary>
    public sealed class NpcMemoryNpc : MonoBehaviour
    {
        [Header("Backend")]
        [Tooltip("The served twicetold-npc API (python -m app.serve).")]
        public string baseUrl = "http://127.0.0.1:8000";

        [Tooltip("Provision a fresh agent on Start; otherwise attach to agentIdOverride.")]
        public bool autoProvision = true;

        [Tooltip("Existing agent UUID when autoProvision is off.")]
        public string agentIdOverride = "";

        [Header("Agent (auto-provision)")]
        public string agentName = "graybox-keeper";

        [TextArea]
        public string seedIdentity =
            "I keep the ford and remember who pays their toll.";

        public string diagnosticityGoal = "what threatens the ford";

        [Tooltip("Decay taus (seconds) written to the provisioned agent's config.")]
        public double episodicTauSeconds = 604800.0;

        public double semanticTauSeconds = 2592000.0;
        public string phaseTag = "unity";

        public NpcMemoryClient Client { get; private set; }
        public NpcSession Session { get; private set; }
        public Guid AgentId { get; private set; }
        public bool Ready { get; private set; }

        private Task _initialization;
        private readonly CancellationTokenSource _lifetime = new CancellationTokenSource();
        private bool _destroyed;
        private DateTimeOffset? _asOf;

        /// <summary>Starts initialization if needed and shares its success/failure
        /// with all callers, including Start. Await before enabling gameplay.</summary>
        public Task ReadyTask => InitializeAsync();

        private async void Start()
        {
            try { await ReadyTask; }
            catch (Exception exc) { if (!_destroyed) Debug.LogException(exc, this); }
        }

        /// <summary>Provision/attach + initialize the first scene exactly once.
        /// A failure remains observable; no hidden reprovisioning or retry.</summary>
        public Task InitializeAsync()
        {
            ThrowIfDestroyed();
            return _initialization ??= InitializeCoreAsync();
        }

        private async Task InitializeCoreAsync()
        {
            Client = new NpcMemoryClient(baseUrl);
            try
            {
                if (autoProvision)
                {
                    var created = await Client.CreateAgentAsync(new CreateAgentRequest
                    {
                        Name = agentName,
                        SeedIdentity = seedIdentity,
                        DiagnosticityGoal = diagnosticityGoal,
                        Config = new JObject
                        {
                            ["decay_classes"] = new JObject
                            {
                                ["episodic"] = episodicTauSeconds,
                                ["semantic"] = semanticTauSeconds,
                            },
                            ["decay_class_default"] = "episodic",
                        },
                    }, _lifetime.Token);
                    AgentId = created.AgentId;
                }
                else
                {
                    AgentId = Guid.Parse(agentIdOverride);
                }
                Session = new NpcSession(Client, AgentId, phaseTag) { AsOf = _asOf };
                await Session.InitializeAsync(_lifetime.Token);
                _lifetime.Token.ThrowIfCancellationRequested();
                Ready = true;
            }
            catch
            {
                Client.Dispose();
                throw;
            }
        }

        private void ThrowIfDestroyed()
        {
            if (_destroyed) throw new ObjectDisposedException(nameof(NpcMemoryNpc));
        }

        // Cancelling one caller stops only its wait, not shared initialization.
        private async Task WaitForReadyAsync(CancellationToken ct)
        {
            ct.ThrowIfCancellationRequested();
            var ready = ReadyTask;
            if (!ct.CanBeCanceled) { await ready; return; }
            var cancelled = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            using (ct.Register(() => cancelled.TrySetCanceled(ct)))
                await await Task.WhenAny(ready, cancelled.Task);
            ct.ThrowIfCancellationRequested();
        }

        public async Task<DialogueTurnResult> SayAsync(string text, CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, _lifetime.Token);
            return await Session.SayAsync(text, ct: linked.Token);
        }

        public async Task<DialogueTurnResult> SayStreamAsync(
            string text, Action<string> onChunk, Action onReconstructing = null,
            CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, _lifetime.Token);
            return await Session.SayStreamAsync(text, onChunk, onReconstructing, ct: linked.Token);
        }

        public async Task<IngestResult> ObserveAsync(string text, CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, _lifetime.Token);
            return await Session.ObserveAsync(text, linked.Token);
        }

        /// <summary>Await ReadyTask first: a synchronous fire-and-forget event
        /// must retain its call-time timestamp, never wait and stamp it later.</summary>
        public void ObserveAndForget(string text)
        {
            ThrowIfDestroyed();
            if (!Ready) throw new InvalidOperationException("Await ReadyTask before ObserveAndForget.");
            Session.ObserveAndForget(text);
        }

        public async Task DrainObservesAsync(CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            await Session.DrainObservesAsync(ct);
        }

        public int PendingObserves => Session != null ? Session.PendingObserves : 0;

        public async Task<SceneResult> SceneBoundaryAsync(
            string sceneType = null, string prewarmContext = null, CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, _lifetime.Token);
            return await Session.SceneBoundaryAsync(sceneType, prewarmContext, linked.Token);
        }

        public async Task<CorrectionResult> CorrectAsync(Guid memoryId, string content, CancellationToken ct = default)
        {
            await WaitForReadyAsync(ct);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(ct, _lifetime.Token);
            return await Session.CorrectAsync(memoryId, content, ct: linked.Token);
        }

        /// <summary>Set before ReadyTask for the first scene's game clock.
        /// This changes aging/scoring, not historical visibility.</summary>
        public void SetAsOf(DateTimeOffset? asOf)
        {
            ThrowIfDestroyed();
            _asOf = asOf;
            if (Session != null) Session.AsOf = asOf;
        }

        private void OnDestroy()
        {
            _destroyed = true;
            Ready = false;
            _lifetime.Cancel();
            Client?.Dispose();
            // Keep the cancelled source valid for in-flight continuations.
        }
    }
}
