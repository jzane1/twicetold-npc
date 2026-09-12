using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;

namespace NpcMemory
{
    /// <summary>
    /// One NPC session: the caller-held scene state + turn bookkeeping —
    /// the field-for-field port of the Python session runner
    /// (app\session.py; the server is STATELESS by ruling, so this
    /// bookkeeping is the client's job). Re-shaped by A1 (2026-08-04): the
    /// reputation snapshot, the directive/reputation callbacks, and the
    /// recent-actions block left with the behavior/reputation removal.
    ///
    /// Scene state frozen within a scene: the identity version and the
    /// scene basis move only at scene boundaries (or session start). The
    /// loaded set + damper streak and the scene context fields are
    /// caller-held and reset at boundaries. AsOf is the session's
    /// time-travel surface: it rides retrieval's age computation AND
    /// becomes the client timestamp of observes and corrections.
    /// </summary>
    public sealed class NpcSession
    {
        private readonly NpcMemoryClient _client;
        private readonly string _phaseTag;

        public Guid AgentId { get; }
        public string? IdentityVersion { get; private set; }
        public DateTimeOffset? SceneStartedAt { get; private set; }

        /// <summary>The session's scene type (C3, 2026-08-17): set by
        /// SceneBoundaryAsync's argument, cleared by a bare boundary; rides
        /// every turn request so the current scene's compiled bundles
        /// multiply the prose-view weights.</summary>
        public string? SceneType { get; private set; }
        public DateTimeOffset? AsOf { get; set; }
        public List<Guid>? LoadedMemoryIds { get; private set; }
        public int GateFruitlessStreak { get; private set; }
        public string? ContextLocation { get; set; }
        public List<string>? ContextEntities { get; set; }
        public DateTimeOffset? ContextEventTime { get; set; }

        /// <summary>Mirrors the Python runner's `debug` flag on every turn
        /// request (app\session.py) — the server widens its debug payload.</summary>
        public bool Debug { get; set; }

        // -- fire-and-forget observes (C5, ruled 2026-08-17) -------------
        // No queue, no pump: each ObserveAndForget launches its HTTP call
        // immediately and a tracker records the outcome. The lock exists for
        // the console harness (no SynchronizationContext => continuations on
        // pool threads); under Unity's context it is uncontended.
        private readonly object _observeGate = new object();
        private readonly List<Task> _pendingObserves = new List<Task>();
        private readonly List<Exception> _observeFailures = new List<Exception>();

        /// <summary>In-flight fire-and-forget observes right now (completed
        /// trackers are pruned on read).</summary>
        public int PendingObserves
        {
            get
            {
                lock (_observeGate)
                {
                    _pendingObserves.RemoveAll(t => t.IsCompleted);
                    return _pendingObserves.Count;
                }
            }
        }

        /// <summary>Per-failure surfacing at failure time: (observation
        /// text, the typed error). Fires on the caller's
        /// SynchronizationContext like every other callback here — safe to
        /// touch Unity objects. Failures ALSO accumulate for the next
        /// DrainObservesAsync, which re-throws them — never swallowed,
        /// with or without a subscriber.</summary>
        public event Action<string, Exception>? OnObserveFailed;

        public NpcSession(
            NpcMemoryClient client,
            Guid agentId,
            string phaseTag = "unity")
        {
            _client = client;
            AgentId = agentId;
            _phaseTag = phaseTag;
        }

        private DateTimeOffset Now() => AsOf ?? DateTimeOffset.UtcNow;

        private DialogueTurnRequest BuildTurnRequest(
            string text,
            int? k,
            WeightOverrides? weightOverrides) =>
            new DialogueTurnRequest
            {
                AgentId = AgentId,
                Utterance = text,
                K = k,
                AsOf = AsOf,
                LocationName = ContextLocation,
                Entities = ContextEntities,
                EventTime = ContextEventTime,
                IdentityVersion = IdentityVersion,
                SceneStartedAt = SceneStartedAt,
                LoadedMemoryIds = LoadedMemoryIds,
                GateFruitlessStreak = GateFruitlessStreak,
                WeightOverrides = weightOverrides,
                SceneType = SceneType,
                Debug = Debug,
            };

        /// <summary>One dialogue turn, drained (POST /v1/dialogue/turn).
        /// `weightOverrides` is the weights-on-speech slot (A1 re-shape):
        /// per-call multipliers re-rank the served view feeding the prose
        /// prompt; the result's DialogueView reports that ranking.</summary>
        public async Task<DialogueTurnResult> SayAsync(
            string text,
            int? k = null,
            WeightOverrides? weightOverrides = null,
            CancellationToken ct = default)
        {
            var result = await _client
                .DialogueTurnAsync(BuildTurnRequest(text, k, weightOverrides), ct);
            ApplyTurnResult(result);
            return result;
        }

        /// <summary>One streaming dialogue turn (the SSE route): onChunk per
        /// prose chunk; onReconstructing during a blocking mid-scene
        /// retelling — the "(reconstructing…)" hook.</summary>
        public async Task<DialogueTurnResult> SayStreamAsync(
            string text,
            Action<string> onChunk,
            Action? onReconstructing = null,
            int? k = null,
            WeightOverrides? weightOverrides = null,
            CancellationToken ct = default)
        {
            var result = await _client
                .DialogueTurnStreamAsync(
                    BuildTurnRequest(text, k, weightOverrides),
                    onChunk,
                    onReconstructing,
                    ct);
            ApplyTurnResult(result);
            return result;
        }

        /// <summary>Post-turn scene-state bookkeeping, in ONE place so the
        /// streaming and drained paths cannot drift (the Python
        /// _apply_turn_result, ported). Keyed on what the SERVER reports
        /// (gate.evaluated / fired), not on what was sent.</summary>
        private void ApplyTurnResult(DialogueTurnResult result)
        {
            var gate = result.Instrumentation.Retrieval.Gate;
            if (!gate.Evaluated)
            {
                // Loader turn: the served IDs become the scene's loaded set.
                LoadedMemoryIds = result.Items.Select(i => i.MemoryId).ToList();
                GateFruitlessStreak = 0;
            }
            else if (gate.Fired)
            {
                // Gated fire: this turn's gate-fetched IDs append; the streak
                // resets on a productive fetch, increments on a fruitless one.
                LoadedMemoryIds = (LoadedMemoryIds ?? new List<Guid>())
                    .Concat(
                        result.Items.Where(i => i.GateFetched).Select(i => i.MemoryId))
                    .ToList();
                GateFruitlessStreak =
                    gate.FetchedNewCount == 0 ? GateFruitlessStreak + 1 : 0;
            }
            // Gated-closed: untouched.
        }

        /// <summary>One observe event at the session's effective time.</summary>
        public Task<IngestResult> ObserveAsync(
            string text, CancellationToken ct = default) =>
            _client.ObserveAsync(
                new ObserveEvent
                {
                    AgentId = AgentId,
                    ObservationText = text,
                    PhaseTag = _phaseTag,
                    ClientTimestamp = Now(),
                    Provenance = "lived",
                },
                ct);

        /// <summary>Fire-and-forget observe (C5, ruled 2026-08-17): the
        /// event is stamped at the session's effective time NOW —
        /// byte-identical shape to ObserveAsync's, and the synchronous stamp
        /// is what preserves world-time ordering (valid_at and every product
        /// ordering ride the timestamp, not arrival) — then the call runs
        /// without blocking the caller. Observe latency was ruled a client
        /// concern; this is the lever: dialogue never waits on the ~3 s
        /// write pass. No retry, no auto-drain anywhere (ruled — drain at
        /// scene edges is integrator guidance, the reflect-at-scene-edges
        /// shape); an un-drained observe is bi-temporally safe, merely not
        /// yet retrievable. Orthogonal to server-side deferred writes (C1):
        /// deferral shortens the round trip, this hides it — they compose.
        /// </summary>
        public void ObserveAndForget(string text)
        {
            var evt = new ObserveEvent
            {
                AgentId = AgentId,
                ObservationText = text,
                PhaseTag = _phaseTag,
                ClientTimestamp = Now(),
                Provenance = "lived",
            };
            Task tracker = TrackObserveAsync(evt);
            lock (_observeGate)
            {
                _pendingObserves.Add(tracker);
            }
        }

        /// <summary>The tracker owns its observe's outcome, so no Task ever
        /// faults unobserved (nothing leaks to
        /// TaskScheduler.UnobservedTaskException): a failure is recorded for
        /// the next drain and raised through OnObserveFailed at failure
        /// time.</summary>
        private async Task TrackObserveAsync(ObserveEvent evt)
        {
            try
            {
                await _client.ObserveAsync(evt);
            }
            catch (Exception ex)
            {
                lock (_observeGate)
                {
                    _observeFailures.Add(ex);
                }
                OnObserveFailed?.Invoke(evt.ObservationText, ex);
            }
        }

        /// <summary>Await every in-flight fire-and-forget observe; then, if
        /// any failed since the last drain, throw ONE AggregateException
        /// carrying the typed failures (a stable type even for a single
        /// failure) and clear them. Drains are always explicit by ruling —
        /// no verb hides one. `ct` abandons the WAIT only (an abandoned
        /// drain is not a drain: failures stay for the next one); the
        /// observes themselves keep running under the client's per-route
        /// timeout, which also bounds this await.</summary>
        public async Task DrainObservesAsync(CancellationToken ct = default)
        {
            Task[] pending;
            lock (_observeGate)
            {
                pending = _pendingObserves.ToArray();
            }
            if (pending.Length > 0)
            {
                // Trackers never fault, so WhenAll completes; the token
                // needs its own lane (netstandard2.1 has no WaitAsync).
                var all = Task.WhenAll(pending);
                if (ct.CanBeCanceled)
                {
                    var abandon = new TaskCompletionSource<object?>(
                        TaskCreationOptions.RunContinuationsAsynchronously);
                    using (ct.Register(() => abandon.TrySetCanceled(ct)))
                    {
                        await await Task.WhenAny(all, abandon.Task);
                    }
                }
                else
                {
                    await all;
                }
            }
            Exception[] failures;
            lock (_observeGate)
            {
                _pendingObserves.RemoveAll(t => t.IsCompleted);
                failures = _observeFailures.ToArray();
                _observeFailures.Clear();
            }
            if (failures.Length > 0)
            {
                throw new AggregateException(
                    $"{failures.Length} fire-and-forget observe(s) failed "
                        + "since the last drain",
                    failures);
            }
        }

        /// <summary>Scene boundary: emit the event (the handler recompiles
        /// the identity document server-side), then refresh the frozen scene
        /// state — within the ending scene none of it moved. Since C3 the
        /// type also becomes session state riding the following turns
        /// (a bare boundary clears it back to the default). A non-empty
        /// prewarmContext rides as the C7-B reconstruction pre-warm probe;
        /// the result's Prewarm record is null without one (the off
        /// state).</summary>
        public async Task<SceneResult> SceneBoundaryAsync(
            string? sceneType = null,
            string? prewarmContext = null,
            CancellationToken ct = default)
        {
            var result = await _client
                .SceneBoundaryAsync(
                    new SceneBoundaryEvent
                    {
                        AgentId = AgentId,
                        ClientTimestamp = Now(),
                        SceneType = sceneType,
                        PrewarmContext = prewarmContext,
                    },
                    ct);
            IdentityVersion = result.IdentityVersion;
            SceneStartedAt = Now();
            SceneType = sceneType;
            LoadedMemoryIds = null; // next turn is a loader
            GateFruitlessStreak = 0; // the damper dies with the scene
            ContextLocation = null; // a new scene is a new place/cast
            ContextEntities = null;
            ContextEventTime = null;
            return result;
        }

        /// <summary>Authorial correction at the session's effective time.</summary>
        public Task<CorrectionResult> CorrectAsync(
            Guid memoryId,
            string content,
            Guid? expectedDetailId = null,
            List<string>? entities = null,
            CancellationToken ct = default) =>
            _client.CorrectAsync(
                memoryId,
                new CorrectionRequest
                {
                    Content = content,
                    ClientTimestamp = Now(),
                    ExpectedDetailId = expectedDetailId,
                    Entities = entities,
                },
                ct);

        /// <summary>The diegetic-correction event at the session's effective
        /// time (dissonance.md, C4; the CorrectAsync time precedent): an
        /// in-world confrontation of a memory — the server decides defend vs
        /// fold mechanically and the reconstruction role writes the new
        /// telling. The "observed" default is caller ergonomics; the wire
        /// field itself is required.</summary>
        public Task<DiegeticCorrectionResult> ConfrontAsync(
            Guid memoryId,
            string challengeText,
            string challengeTypology = "observed",
            double? challengeWeight = null,
            JObject? sourceEvent = null,
            CancellationToken ct = default) =>
            _client.DiegeticCorrectAsync(
                new DiegeticCorrectionEvent
                {
                    AgentId = AgentId,
                    MemoryId = memoryId,
                    ChallengeText = challengeText,
                    ChallengeTypology = challengeTypology,
                    ChallengeWeight = challengeWeight,
                    ClientTimestamp = Now(),
                    SourceEvent = sourceEvent,
                },
                ct);

        /// <summary>The reflect verb at the session's effective time
        /// (reflection.md, 2026-08-15; the CorrectAsync time precedent).
        /// Deliberately does NOT touch the frozen scene state:
        /// IdentityVersion stays caller-frozen until the next scene boundary
        /// picks up the recompiled document — reflect at scene edges and the
        /// trim-eviction exposure window vanishes.</summary>
        public Task<ReflectResult> ReflectAsync(
            bool? consolidate = null, CancellationToken ct = default) =>
            _client.ReflectAsync(
                AgentId,
                new ReflectRequest
                {
                    ClientTimestamp = Now(),
                    Consolidate = consolidate,
                },
                ct);

        public Task<PinResult> PinAsync(
            Guid memoryId, bool pinned, CancellationToken ct = default) =>
            _client.SetPinAsync(memoryId, pinned, ct);
    }
}
