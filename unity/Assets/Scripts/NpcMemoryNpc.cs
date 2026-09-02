using System;
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

        private async void Start()
        {
            try
            {
                await InitializeAsync();
            }
            catch (Exception exc)
            {
                Debug.LogException(exc, this);
            }
        }

        /// <summary>Provision (or attach) + open the session. Loud on failure.</summary>
        public async Task InitializeAsync()
        {
            Client = new NpcMemoryClient(baseUrl);
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
                });
                AgentId = created.AgentId;
            }
            else
            {
                AgentId = Guid.Parse(agentIdOverride);
            }
            Session = new NpcSession(Client, AgentId, phaseTag);
            Ready = true;
        }

        // Thin passthroughs — the session owns all bookkeeping.

        public Task<DialogueTurnResult> SayAsync(string text) =>
            Session.SayAsync(text);

        public Task<DialogueTurnResult> SayStreamAsync(
            string text, Action<string> onChunk, Action onReconstructing = null) =>
            Session.SayStreamAsync(text, onChunk, onReconstructing);

        public Task<IngestResult> ObserveAsync(string text) =>
            Session.ObserveAsync(text);

        /// <summary>Fire-and-forget observe (C5): returns immediately, the
        /// timestamp already stamped. Failures surface on the session's
        /// OnObserveFailed event and re-throw at the next drain — subscribe
        /// via Session.OnObserveFailed if the game wants the signal.</summary>
        public void ObserveAndForget(string text) =>
            Session.ObserveAndForget(text);

        /// <summary>The explicit join for in-flight observes (no verb
        /// auto-drains, by ruling — place drains at scene edges).</summary>
        public Task DrainObservesAsync() =>
            Session.DrainObservesAsync();

        /// <summary>In-flight fire-and-forget observes (0 when idle).</summary>
        public int PendingObserves =>
            Session != null ? Session.PendingObserves : 0;

        public Task<SceneResult> SceneBoundaryAsync(
            string sceneType = null, string prewarmContext = null) =>
            Session.SceneBoundaryAsync(sceneType, prewarmContext);

        public Task<CorrectionResult> CorrectAsync(Guid memoryId, string content) =>
            Session.CorrectAsync(memoryId, content);

        /// <summary>The session's time-travel surface (null = wall clock).</summary>
        public void SetAsOf(DateTimeOffset? asOf)
        {
            Session.AsOf = asOf;
        }

        private void OnDestroy()
        {
            Client?.Dispose();
        }
    }
}
