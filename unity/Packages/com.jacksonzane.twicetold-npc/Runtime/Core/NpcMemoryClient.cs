using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace NpcMemory
{
    /// <summary>An HTTP error from the twicetold-npc service, surfaced loudly —
    /// never swallowed, never silently retried (the service's fail-loud
    /// precedent). StatusCode 0 means a transport/contract failure.</summary>
    public sealed class NpcMemoryApiException : Exception
    {
        public int StatusCode { get; }

        public NpcMemoryApiException(int statusCode, string detail)
            : base($"twicetold-npc API error {statusCode}: {detail}")
        {
            StatusCode = statusCode;
        }
    }

    /// <summary>
    /// The ONE flat client over the twicetold-npc HTTP API (unity-client.md,
    /// ruled 2026-07-27: engine-agnostic, zero UnityEngine types, no
    /// abstraction ceremony). Stateless — scene state lives in NpcSession.
    /// Verbs mirror the routes 1:1 and are pass-through both ways: requests
    /// serialize exactly what the service accepts; responses deserialize
    /// every field the service returns.
    ///
    /// Timeouts are per-route and integrator-configurable (nothing
    /// hardcoded beyond overridable defaults): Init must tolerate the cold
    /// reconstruction pre-warm (16.3 s measured real-mode), Turn the full
    /// turn, Observe the synchronous write pass.
    ///
    /// Deliberately NO ConfigureAwait(false) anywhere: continuations honor
    /// the caller's SynchronizationContext, so in Unity every await — and
    /// every callback (chunks) — resumes on the
    /// main thread with no explicit marshaling. The classic library-deadlock
    /// hazard needs a caller that BLOCKS on these tasks, and blocking
    /// (.Result/.Wait) is banned by the adapter contract. Play-mode-proven:
    /// the demo driver asserts chunk callbacks land on the main thread.
    /// </summary>
    public sealed class NpcMemoryClient : IDisposable
    {
        private readonly HttpClient _http;
        private readonly bool _ownsHttp;
        private readonly string _baseUrl;

        /// <summary>Wall time in ms around the LAST completed HTTP call, the
        /// client's half of "instrument at the seam" (architecture.md §2). The
        /// server reports its own decomposition inside the payload; the gap
        /// between that and this is transport, visible from day one. Not on the
        /// wire: purely client-side.</summary>
        public double ClientTotalMs { get; private set; }

        /// <summary>Per-call (route path, wall ms) as each call completes.
        /// Fires on the caller's SynchronizationContext, like every other
        /// callback here — safe to touch Unity objects from.</summary>
        public event Action<string, double>? OnCallMeasured;

        public TimeSpan InitTimeout { get; set; } = TimeSpan.FromSeconds(60);
        public TimeSpan TurnTimeout { get; set; } = TimeSpan.FromSeconds(60);
        public TimeSpan ObserveTimeout { get; set; } = TimeSpan.FromSeconds(30);
        public TimeSpan DefaultTimeout { get; set; } = TimeSpan.FromSeconds(15);

        public NpcMemoryClient(string baseUrl, HttpClient? http = null)
        {
            _baseUrl = baseUrl.TrimEnd('/');
            _ownsHttp = http == null;
            _http = http ?? new HttpClient();
            // Per-route timeouts ride CancellationTokens; the HttpClient-level
            // timeout must not undercut them.
            if (_ownsHttp)
            {
                _http.Timeout = Timeout.InfiniteTimeSpan;
            }
        }

        public void Dispose()
        {
            if (_ownsHttp)
            {
                _http.Dispose();
            }
        }

        // -- verbs (route table, unity-client.md) -----------------------

        public Task<CreateAgentResult> CreateAgentAsync(
            CreateAgentRequest request, CancellationToken ct = default) =>
            PostAsync<CreateAgentResult>("/v1/agents", request, DefaultTimeout, ct);

        public Task<IngestResult> ObserveAsync(
            ObserveEvent evt, CancellationToken ct = default) =>
            PostAsync<IngestResult>("/v1/events/observe", evt, ObserveTimeout, ct);

        public Task<SceneResult> SceneBoundaryAsync(
            SceneBoundaryEvent evt, CancellationToken ct = default) =>
            PostAsync<SceneResult>("/v1/events/scene-boundary", evt, DefaultTimeout, ct);

        /// <summary>The diegetic-correction event (architecture.md §8): one
        /// retell model call rides it server-side, so it takes the
        /// observe-class timeout (the ReflectAsync precedent).</summary>
        public Task<DiegeticCorrectionResult> DiegeticCorrectAsync(
            DiegeticCorrectionEvent evt, CancellationToken ct = default) =>
            PostAsync<DiegeticCorrectionResult>(
                "/v1/events/diegetic-correction", evt, ObserveTimeout, ct);

        public Task<PinResult> SetPinAsync(
            Guid memoryId, bool pinned, CancellationToken ct = default) =>
            SendAsync<PinResult>(
                HttpMethod.Put,
                $"/v1/memories/{memoryId}/pin",
                new PinRequest { Pinned = pinned },
                DefaultTimeout,
                ct);

        public Task<CorrectionResult> CorrectAsync(
            Guid memoryId, CorrectionRequest request, CancellationToken ct = default) =>
            PostAsync<CorrectionResult>(
                $"/v1/memories/{memoryId}/correction", request, DefaultTimeout, ct);

        /// <summary>The reflect verb (reflection.md, 2026-08-15): up to two
        /// model calls ride it server-side, so it takes the observe-class
        /// timeout rather than the default.</summary>
        public Task<ReflectResult> ReflectAsync(
            Guid agentId, ReflectRequest request, CancellationToken ct = default) =>
            PostAsync<ReflectResult>(
                $"/v1/agents/{agentId}/reflect", request, ObserveTimeout, ct);

        public Task<RetrievalResult> DialogueInitAsync(
            DialogueInitRequest request, CancellationToken ct = default) =>
            PostAsync<RetrievalResult>("/v1/dialogue/init", request, InitTimeout, ct);

        public Task<DialogueTurnResult> DialogueTurnAsync(
            DialogueTurnRequest request, CancellationToken ct = default) =>
            PostAsync<DialogueTurnResult>("/v1/dialogue/turn", request, TurnTimeout, ct);

        public Task<MemoryChainResult> MemoryChainAsync(
            Guid memoryId, CancellationToken ct = default) =>
            GetAsync<MemoryChainResult>($"/v1/memories/{memoryId}/chain", ct);

        public Task<AgentMemoriesResult> AgentMemoriesAsync(
            Guid agentId, int? limit = null, CancellationToken ct = default) =>
            GetAsync<AgentMemoriesResult>(
                $"/v1/agents/{agentId}/memories" + (limit is int l ? $"?limit={l}" : ""),
                ct);

        public Task<ReconstructionMetricsResult> ReconstructionMetricsAsync(
            Guid memoryId, CancellationToken ct = default) =>
            GetAsync<ReconstructionMetricsResult>(
                $"/v1/memories/{memoryId}/reconstruction-metrics", ct);

        /// <summary>The agent-state read (C5, ruled 2026-08-17): the fourth
        /// unscored inspector read — the stored row, identity currency, the
        /// pressure gauge, live beliefs, bundles incl. passthrough, and both
        /// workers' run logs (newest first, capped by runsLimit). No model
        /// call rides it, so the default GET timeout applies; runsLimit is
        /// the size lever.</summary>
        public Task<AgentStateResult> AgentStateAsync(
            Guid agentId, int? runsLimit = null, CancellationToken ct = default) =>
            GetAsync<AgentStateResult>(
                $"/v1/agents/{agentId}/state"
                    + (runsLimit is int r ? $"?runs_limit={r}" : ""),
                ct);

        /// <summary>
        /// The SSE turn (POST /v1/dialogue/turn/stream): onChunk fires per
        /// prose chunk as it arrives; onReconstructing fires if the server
        /// signals a blocking mid-scene retelling; returns the terminal
        /// DialogueTurnResult. Pre-stream service errors (404/422) throw
        /// NpcMemoryApiException exactly like the non-streaming route; an
        /// in-stream `error` event throws with StatusCode 0.
        /// </summary>
        public async Task<DialogueTurnResult> DialogueTurnStreamAsync(
            DialogueTurnRequest request,
            Action<string> onChunk,
            Action? onReconstructing = null,
            CancellationToken ct = default)
        {
            var started = Stopwatch.GetTimestamp();
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(TurnTimeout);
            using var message = new HttpRequestMessage(
                HttpMethod.Post, _baseUrl + "/v1/dialogue/turn/stream")
            {
                Content = new StringContent(
                    NpcJson.Serialize(request), Encoding.UTF8, "application/json"),
            };
            using var response = await _http
                .SendAsync(message, HttpCompletionOption.ResponseHeadersRead, cts.Token);
            if (!response.IsSuccessStatusCode)
            {
                var detail = await response.Content.ReadAsStringAsync();
                throw new NpcMemoryApiException((int)response.StatusCode, detail);
            }

            using var stream = await response.Content.ReadAsStreamAsync();
            using var reader = new StreamReader(stream, Encoding.UTF8);

            DialogueTurnResult? result = null;
            string? eventName = null;
            string? data = null;
            // Driven purely off the async read's null sentinel. `EndOfStream`
            // would be a SYNCHRONOUS read whenever the buffer is empty — on a
            // live SSE stream that blocks the caller until the server sends
            // the next byte, i.e. it stalls Unity's main thread between
            // chunks (this type deliberately has no ConfigureAwait(false), so
            // every continuation resumes there). Never reintroduce it.
            while (true)
            {
                var line = await reader.ReadLineAsync();
                if (line == null)
                {
                    break;
                }
                if (line.StartsWith("event: ", StringComparison.Ordinal))
                {
                    eventName = line.Substring(7);
                }
                else if (line.StartsWith("data: ", StringComparison.Ordinal))
                {
                    data = line.Substring(6);
                }
                else if (line.Length == 0 && eventName != null)
                {
                    switch (eventName)
                    {
                        case "chunk":
                            onChunk(NpcJson.Deserialize<string>(data ?? "\"\""));
                            break;
                        case "reconstructing":
                            onReconstructing?.Invoke();
                            break;
                        case "result":
                            result = NpcJson.Deserialize<DialogueTurnResult>(data ?? "");
                            break;
                        case "error":
                            throw new NpcMemoryApiException(
                                0, NpcJson.Deserialize<string>(data ?? "\"stream error\""));
                    }
                    eventName = null;
                    data = null;
                }
            }
            if (result == null)
            {
                throw new NpcMemoryApiException(0, "stream ended without a result event");
            }
            // Whole-stream wall time: first byte to terminal result. The
            // server's first_word_ms / perceived_first_word_ms ride inside
            // the payload; this is the transport envelope around them.
            Measure("/v1/dialogue/turn/stream", started);
            return result;
        }

        // -- transport ---------------------------------------------------

        private Task<T> PostAsync<T>(
            string path, object body, TimeSpan timeout, CancellationToken ct) =>
            SendAsync<T>(HttpMethod.Post, path, body, timeout, ct);

        private async Task<T> GetAsync<T>(string path, CancellationToken ct)
        {
            var started = Stopwatch.GetTimestamp();
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(DefaultTimeout);
            using var response = await _http
                .GetAsync(_baseUrl + path, cts.Token);
            var result = await ReadAsync<T>(response);
            Measure(path, started);
            return result;
        }

        private async Task<T> SendAsync<T>(
            HttpMethod method, string path, object body, TimeSpan timeout,
            CancellationToken ct)
        {
            var started = Stopwatch.GetTimestamp();
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            cts.CancelAfter(timeout);
            using var message = new HttpRequestMessage(method, _baseUrl + path)
            {
                Content = new StringContent(
                    NpcJson.Serialize(body), Encoding.UTF8, "application/json"),
            };
            using var response = await _http.SendAsync(message, cts.Token);
            var result = await ReadAsync<T>(response);
            Measure(path, started);
            return result;
        }

        private void Measure(string path, long started)
        {
            // ALWAYS record, then notify. Gating the measurement on a
            // subscriber (the first shape of this, 2026-07-28) left
            // ClientTotalMs sitting at 0 for any caller that reads the
            // property without also subscribing — a plausible-looking zero
            // instead of a real number, which is the exact failure
            // "instrument at the seam" exists to prevent.
            var ms = (Stopwatch.GetTimestamp() - started) * 1000.0 / Stopwatch.Frequency;
            ClientTotalMs = ms;
            OnCallMeasured?.Invoke(path, ms);
        }

        private static async Task<T> ReadAsync<T>(HttpResponseMessage response)
        {
            var text = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                throw new NpcMemoryApiException((int)response.StatusCode, text);
            }
            return NpcJson.Deserialize<T>(text);
        }
    }
}
