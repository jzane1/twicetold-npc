using System;
using System.Globalization;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace NpcMemory.Unity
{
    /// <summary>
    /// The gray-box demo surface (unity-client.md fork 7, settled at build:
    /// an IMGUI dev-tool overlay — the intended systems aesthetic — over the
    /// primitive set; dialogue streams into the panel, the gate line reads
    /// out live). Re-shaped by A1 (2026-08-04): the directive flash and the
    /// reputation readout left with the behavior/reputation removal.
    ///
    /// autoRun plays a scripted Play-mode verification: provision → observes
    /// at injected times → boundary → loader turn → streamed turn — logging
    /// [npc-demo] receipts the MCP console read can assert on. It proves the
    /// ADAPTER contract (the full beat coverage is the console harness's
    /// floor): async work never blocks the main thread (frames keep pumping,
    /// asserted), and every callback lands ON the main thread (thread-id
    /// asserted).
    /// </summary>
    public sealed class NpcDemoDriver : MonoBehaviour
    {
        public NpcMemoryNpc npc;

        [Tooltip("Run the scripted Play-mode verification beats on Start.")]
        public bool autoRun;

        [Header("Demo beat controls (E2, 2026-08-19)")]
        [Tooltip("Target memory UUID for the Correct button (paste from the "
            + "demo loader's printed roll).")]
        public string correctionMemoryId = "";

        [TextArea]
        [Tooltip("Override text the Correct button applies (falls back to "
            + "the input field when empty).")]
        public string correctionText = "";

        [TextArea]
        [Tooltip("C7-B pre-warm probe the Scene boundary button sends "
            + "(empty = no probe).")]
        public string prewarmContext =
            "Do you remember the two drovers you turned away at the door in June?";

        [Tooltip("Per-turn k for the Say button (0 = the server default). "
            + "The beat condition is the utterance's, not the agent's.")]
        public int sayK;

        [Tooltip("Day count for the as-of jump button.")]
        public int jumpDays = 60;

        [Tooltip("Starting as-of applied once the adapter attaches (the E3 "
            + "recording rig, attach mode only; empty = real time). The demo "
            + "timeline needs the June-25 basis so every take and retake "
            + "lands on the pinned reconstruction caches.")]
        public string startAsOf = "2026-06-25T19:00:00Z";

        private string _input = "What has happened at the ford lately?";
        private string _dialogue = "";
        private string _status = "(connecting…)";
        private string _gateLine = "-";
        private bool _busy;
        private int _frames;
        private int _mainThreadId;

        private void Awake()
        {
            // Keep the player loop pumping when the window is unfocused —
            // the demo records and verifies unattended (without this, an
            // unfocused Editor pauses Update while the sync context still
            // pumps, and the frame-pump proof reads zero).
            Application.runInBackground = true;
            _mainThreadId = Thread.CurrentThread.ManagedThreadId;
        }

        private void Update()
        {
            _frames++;
        }

        private async void Start()
        {
            if (!autoRun)
            {
                try
                {
                    await ApplyStartAsOfAsync();
                }
                catch (Exception exc)
                {
                    Debug.LogException(exc, this);
                }
                return;
            }
            try
            {
                await RunBeatsAsync();
            }
            catch (Exception exc)
            {
                Debug.LogException(exc, this);
                Debug.LogError("[npc-demo] PLAY-MODE BEATS FAILED");
            }
        }

        /// <summary>Attach-mode start basis (the scripted gate owns its own
        /// timeline, so autoRun skips this). Waits for the adapter, then
        /// pins the session clock so the boundary bases match rehearsal.</summary>
        private async Task ApplyStartAsOfAsync()
        {
            var deadline = Time.realtimeSinceStartup + 30f;
            while (npc == null || !npc.Ready)
            {
                if (Time.realtimeSinceStartup > deadline)
                {
                    _status = "adapter never became Ready";
                    return;
                }
                await Task.Yield();
            }
            if (string.IsNullOrWhiteSpace(startAsOf))
            {
                _status = "attached (real time)";
                return;
            }
            var t = DateTimeOffset.Parse(
                startAsOf,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal);
            npc.SetAsOf(t);
            _status = $"as of {t:yyyy-MM-dd HH:mm}Z";
            Debug.Log($"[npc-demo] startAsOf applied: {t:o}");
        }

        private int _checks;

        private void Check(bool condition, string criterion, string detail = "")
        {
            if (!condition)
            {
                throw new InvalidOperationException(
                    $"[npc-demo] FAIL {criterion} {detail}");
            }
            _checks++;
            Debug.Log($"[npc-demo] PASS {criterion}"
                + (detail == "" ? "" : $" ({detail})"));
        }

        private async Task RunBeatsAsync()
        {
            // Wait for the adapter's own Start() to finish provisioning.
            var deadline = Time.realtimeSinceStartup + 30f;
            while (npc == null || !npc.Ready)
            {
                if (Time.realtimeSinceStartup > deadline)
                {
                    throw new TimeoutException("[npc-demo] adapter never became Ready");
                }
                await Task.Yield();
            }
            _status = $"agent {npc.AgentId}";
            Check(true, "adapter provisioned over the API", npc.AgentId.ToString());

            var t0 = new DateTimeOffset(2026, 7, 27, 12, 0, 0, TimeSpan.Zero);
            npc.SetAsOf(t0.AddDays(-2));
            await npc.ObserveAsync(
                "The miller raised his toll at the bridge and the carters grumbled all week.");
            npc.SetAsOf(t0.AddHours(-6));
            var coin = await npc.ObserveAsync(
                "A stranger paid the ford toll in foreign coin and would not give a name.");
            Check(coin.MemoryId != Guid.Empty, "observes landed at injected world times");

            npc.SetAsOf(t0);
            var scene = await npc.SceneBoundaryAsync("graybox");
            Check(
                scene.Accepted && npc.Session.IdentityVersion != null,
                "scene boundary froze identity + basis");

            var framesBefore = _frames;
            var loader = await npc.SayAsync(_input);
            _dialogue = loader.Content;
            _gateLine = GateLine(loader);
            Check(
                !loader.Instrumentation.Retrieval.Gate.Evaluated
                    && loader.Items.Count > 0,
                "loader turn served IDs + scores",
                $"{loader.Items.Count} items");

            var chunkThread = -1;
            var chunks = new StringBuilder();
            _dialogue = "";
            var streamed = await npc.SayStreamAsync(
                "Tell me about the stranger.",
                chunk =>
                {
                    chunkThread = Thread.CurrentThread.ManagedThreadId;
                    chunks.Append(chunk);
                    _dialogue += chunk; // live on-screen streaming
                });
            _gateLine = GateLine(streamed);
            Check(
                chunks.ToString() == streamed.Content,
                "streamed chunks == content, rendered live");
            Check(
                chunkThread == _mainThreadId,
                "chunk callbacks land ON the main thread",
                $"thread {chunkThread}");
            Check(
                streamed.Instrumentation.Retrieval.Gate.Evaluated,
                "second turn gated (session bookkeeping live in-engine)");
            Check(
                _frames > framesBefore,
                "the main thread kept pumping frames through both turns",
                $"+{_frames - framesBefore} frames");

            Debug.Log(
                $"[npc-demo] ALL PLAY-MODE BEATS PASSED ({_checks} checks) — "
                + "the Unity adapter contract holds");
        }

        private static string GateLine(DialogueTurnResult result)
        {
            var gate = result.Instrumentation.Retrieval.Gate;
            return gate.Evaluated
                ? $"gate: evaluated fired={gate.Fired} new={gate.FetchedNewCount}"
                : "gate: loader turn";
        }

        private void OnGUI()
        {
            // The dev-tool overlay IS the intended aesthetic (ruled 2026-07-22).
            GUILayout.BeginArea(new Rect(12, 12, 560, 340), GUI.skin.box);
            GUILayout.Label($"twicetold-npc · {_status}");
            var pending = npc != null ? npc.PendingObserves : 0;
            GUILayout.Label($"{_gateLine}   pending observes: {pending}");
            GUILayout.Space(6);
            GUILayout.Label(_dialogue, GUILayout.Height(140));
            GUILayout.Space(6);
            _input = GUILayout.TextField(_input);
            GUI.enabled = !_busy && npc != null && npc.Ready;
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Say"))
            {
                RunUi(async () =>
                {
                    _dialogue = "";
                    var result = await npc.Session.SayStreamAsync(
                        _input,
                        chunk => _dialogue += chunk,
                        k: sayK > 0 ? (int?)sayK : null);
                    _gateLine = GateLine(result);
                });
            }
            if (GUILayout.Button("Observe"))
            {
                RunUi(async () => await npc.ObserveAsync(_input));
            }
            if (GUILayout.Button("Observe (async)"))
            {
                // Fire-and-forget: returns immediately, drains at the edge.
                npc.ObserveAndForget(_input);
            }
            if (GUILayout.Button("Drain"))
            {
                RunUi(async () => await npc.DrainObservesAsync());
            }
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Correct"))
            {
                RunUi(async () =>
                {
                    var memoryId = Guid.Parse(correctionMemoryId.Trim());
                    var content = string.IsNullOrEmpty(correctionText)
                        ? _input
                        : correctionText;
                    await npc.CorrectAsync(memoryId, content);
                });
            }
            if (GUILayout.Button("Scene boundary"))
            {
                RunUi(async () => await npc.SceneBoundaryAsync(
                    "graybox",
                    string.IsNullOrEmpty(prewarmContext) ? null : prewarmContext));
            }
            if (GUILayout.Button($"+{jumpDays} days"))
            {
                var now = npc.Session.AsOf ?? DateTimeOffset.UtcNow;
                var next = now.AddDays(jumpDays);
                npc.SetAsOf(next);
                _status = $"as of {next:yyyy-MM-dd HH:mm}Z";
            }
            GUILayout.EndHorizontal();
            GUI.enabled = true;
            GUILayout.EndArea();
        }

        private async void RunUi(Func<Task> action)
        {
            _busy = true;
            try
            {
                await action();
            }
            catch (Exception exc)
            {
                Debug.LogException(exc, this);
            }
            finally
            {
                _busy = false;
            }
        }
    }
}
