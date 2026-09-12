using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace NpcMemory
{
    // ------------------------------------------------------------------
    // Wire models — a field-for-field mirror of app\schemas.py (the route
    // contract is pass-through, so these are both the request and response
    // shapes). Property names map to snake_case via NpcJson's naming
    // strategy. Optional service fields are nullable here; nullable LISTS
    // are deliberate — see NpcJson on the null-vs-absent contract.
    // ------------------------------------------------------------------

    // -- events + operator verbs ---------------------------------------

    public sealed class AffectOverride
    {
        public double? Valence { get; set; }
        public double? Arousal { get; set; }
        public JObject? Detail { get; set; }
    }

    public sealed class ObserveEvent
    {
        public Guid AgentId { get; set; }
        public string ObservationText { get; set; } = "";
        public string PhaseTag { get; set; } = "";
        public DateTimeOffset ClientTimestamp { get; set; }
        public string Provenance { get; set; } = "lived";
        public string? Typology { get; set; }
        public double? TypologyConfidence { get; set; }
        public string? DecayClass { get; set; }
        public string? LocationName { get; set; }
        public string? LocationDescription { get; set; }
        public List<string>? Entities { get; set; }
        public DateTimeOffset? EventTime { get; set; }
        public AffectOverride? Affect { get; set; }
        public bool Pinned { get; set; }
        public string? EventId { get; set; }
    }

    public sealed class SceneBoundaryEvent
    {
        public Guid AgentId { get; set; }
        public DateTimeOffset ClientTimestamp { get; set; }
        public string? SceneType { get; set; }
        public string? EventId { get; set; }

        /// <summary>The C7-B reconstruction pre-warm probe (2026-08-18):
        /// non-empty runs the dialogue-init retrieval/reconstruction path at
        /// the boundary's fresh basis, warming the cache before the first
        /// on-camera turn. Null or empty is the off state (identity
        /// recompile only).</summary>
        public string? PrewarmContext { get; set; }
    }

    /// <summary>The in-world confrontation event (dissonance.md, C4
    /// 2026-08-17) — the third diegetic event. References a target memory;
    /// ChallengeTypology is REQUIRED by the wire contract
    /// (observed|told|inferred|reflected); a null ChallengeWeight resolves
    /// through the server-side default knob.</summary>
    public sealed class DiegeticCorrectionEvent
    {
        public Guid AgentId { get; set; }
        public Guid MemoryId { get; set; }
        public string ChallengeText { get; set; } = "";
        public string ChallengeTypology { get; set; } = "observed";
        public double? ChallengeWeight { get; set; }
        public DateTimeOffset ClientTimestamp { get; set; }
        public JObject? SourceEvent { get; set; }
        public Guid? ExpectedDetailId { get; set; }
        public string? EventId { get; set; }
    }

    public sealed class PinRequest
    {
        public bool Pinned { get; set; }
    }

    public sealed class CorrectionRequest
    {
        public string Content { get; set; } = "";
        public DateTimeOffset ClientTimestamp { get; set; }
        public Guid? ExpectedDetailId { get; set; }
        public List<string>? Entities { get; set; }
    }

    public sealed class CreateAgentRequest
    {
        public string Name { get; set; } = "";
        public string? SeedIdentity { get; set; }
        public double? Rigidity { get; set; }
        public string? DiagnosticityGoal { get; set; }
        public JObject? Config { get; set; }
    }

    // -- event results --------------------------------------------------

    public sealed class AffectOut
    {
        public double? Valence { get; set; }
        public double? Arousal { get; set; }
        public JObject? Detail { get; set; }
    }

    public sealed class Instrumentation
    {
        public double NlpMs { get; set; }
        public double EmbedMs { get; set; }
        public double HaikuMs { get; set; }
        public double InsertMs { get; set; }
        public double TotalMs { get; set; }
        public int HaikuInputTokens { get; set; }
        public int HaikuOutputTokens { get; set; }
        public int EmbeddingTokens { get; set; }
        public bool Escalated { get; set; }
        public List<string> EscalatedBy { get; set; } = new List<string>();
        public double EscalationMs { get; set; }
        public int EscalationInputTokens { get; set; }
        public int EscalationOutputTokens { get; set; }
    }

    public sealed class IngestResult
    {
        public Guid MemoryId { get; set; }
        public Guid DetailId { get; set; }
        public Guid FactVersionId { get; set; }
        public List<Guid> GistSpanIds { get; set; } = new List<Guid>();
        public List<Guid> NewComponentIds { get; set; } = new List<Guid>();
        // Nullable since the deferred-write build (2026-08-12): a
        // deferred-mode observe returns the write-call scalars as null with
        // EnrichmentPending true — the worker fills them server-side later.
        public double? ImportanceRaw { get; set; }
        public string? Typology { get; set; }
        public double? TypologyConfidence { get; set; }
        public string? TypologySource { get; set; }
        public string Provenance { get; set; } = "";
        public AffectOut Affect { get; set; } = new AffectOut();
        public List<string> Entities { get; set; } = new List<string>();
        public string DecayClass { get; set; } = "";
        public bool DecayClassUnknown { get; set; }
        public bool ScoringFailed { get; set; }
        public bool EscalationFailed { get; set; }
        public bool EmbeddingFailed { get; set; }
        public bool Pinned { get; set; }
        public bool EnrichmentPending { get; set; }
        public Instrumentation Instrumentation { get; set; } = new Instrumentation();
    }

    /// <summary>The scene-boundary pre-warm's per-pass record (C7-B,
    /// 2026-08-18). CacheMisses == 0 with ReconstructionMs near zero on the
    /// first same-basis read is the pre-warm's success signal; a hard warm
    /// failure arrives as a degraded all-zero record, never an error (the
    /// boundary must survive).</summary>
    public sealed class ScenePrewarmInstrumentation
    {
        public double EmbedMs { get; set; }
        public double ReconstructionMs { get; set; }
        public int CandidateCount { get; set; }
        public int CacheHits { get; set; }
        public int CacheMisses { get; set; }
        public int WriteBacks { get; set; }
        public int DriftRefusals { get; set; }
        public int EmbeddingTokens { get; set; }
        public int ReconstructionInputTokens { get; set; }
        public int ReconstructionOutputTokens { get; set; }
        public int ReconstructionEmbedTokens { get; set; }
        public bool Degraded { get; set; }
        public string? DegradedReason { get; set; }
    }

    public sealed class SceneResult
    {
        public Guid AgentId { get; set; }
        public bool Accepted { get; set; }
        public double TotalMs { get; set; }
        public string? IdentityVersion { get; set; }
        public bool IdentityDocumentNew { get; set; }

        /// <summary>Null unless the boundary carried a PrewarmContext probe
        /// (the off state).</summary>
        public ScenePrewarmInstrumentation? Prewarm { get; set; }
    }

    public sealed class PinResult
    {
        public Guid MemoryId { get; set; }
        public bool Pinned { get; set; }
        public double TotalMs { get; set; }
    }

    public sealed class CorrectionResult
    {
        public Guid MemoryId { get; set; }
        public Guid DetailId { get; set; }
        public Guid SupersededDetailId { get; set; }
        public Guid FactVersionId { get; set; }
        public Guid SupersededFactVersionId { get; set; }
        public int EvictedCacheRows { get; set; }
        public List<string> Entities { get; set; } = new List<string>();
        public double EmbedMs { get; set; }
        public int EmbeddingTokens { get; set; }
        public double NlpMs { get; set; }
        public double TotalMs { get; set; }
    }

    /// <summary>Result of the diegetic-correction event (dissonance.md, C4):
    /// the decided verb, the head swap + correction record IDs, and every
    /// resolved decision input (both sides recomputable client-side). The
    /// retell prose rides in Content; its spend is counted under the
    /// reconstruction role.</summary>
    public sealed class DiegeticCorrectionResult
    {
        public Guid MemoryId { get; set; }
        public Guid AgentId { get; set; }
        public string Verb { get; set; } = "";
        public Guid CorrectionId { get; set; }
        public Guid DetailId { get; set; }
        public Guid SupersededDetailId { get; set; }
        public bool Pinned { get; set; }
        public string Content { get; set; } = "";
        public double Resistance { get; set; }
        public double Challenge { get; set; }
        public double ImportanceNorm { get; set; }
        public double RigidityEffective { get; set; }
        public double TypologyMultMemory { get; set; }
        public double TypologyMultChallenge { get; set; }
        public double ChallengeWeightEffective { get; set; }
        public int EvictedCacheRows { get; set; }
        public double RetellMs { get; set; }
        public int RetellInputTokens { get; set; }
        public int RetellOutputTokens { get; set; }
        public double TotalMs { get; set; }
    }

    public sealed class CreateAgentResult
    {
        public Guid AgentId { get; set; }
        public string Name { get; set; } = "";
        public string? SeedIdentity { get; set; }
        public double? Rigidity { get; set; }
        public string? DiagnosticityGoal { get; set; }
        public JObject Config { get; set; } = new JObject();
        public double TotalMs { get; set; }
    }

    // -- reflection (reflection.md; the C2 rulings 2026-08-15) -----------

    public sealed class ReflectRequest
    {
        /// <summary>The reflect event's world time — the written rows'
        /// valid_at AND the pipeline's time basis (tz-aware, required).</summary>
        public DateTimeOffset ClientTimestamp { get; set; }

        /// <summary>Tri-state consolidation override: true forces the stage
        /// (RRR still guards), false suppresses it, null lets the
        /// reflection_consolidate_at knob decide.</summary>
        public bool? Consolidate { get; set; }
    }

    public sealed class ReflectionOut
    {
        public Guid ReflectionId { get; set; }
        public string Content { get; set; } = "";
        public bool IdentityRelevant { get; set; }
        public List<Guid> SourceMemoryIds { get; set; } = new List<Guid>();
    }

    public sealed class ConsolidationOut
    {
        public Guid? ReflectionId { get; set; }
        public List<Guid> AbsorbedReflectionIds { get; set; } = new List<Guid>();
        public bool Failed { get; set; }
    }

    public sealed class ReflectInstrumentation
    {
        public double ReflectMs { get; set; }
        public double ConsolidationMs { get; set; }
        public double InsertMs { get; set; }
        public double TotalMs { get; set; }
        public int ReflectInputTokens { get; set; }
        public int ReflectOutputTokens { get; set; }
        public int ConsolidationInputTokens { get; set; }
        public int ConsolidationOutputTokens { get; set; }
    }

    public sealed class ReflectResult
    {
        public Guid AgentId { get; set; }
        public List<ReflectionOut> Reflections { get; set; } = new List<ReflectionOut>();
        public List<Guid> SampledMemoryIds { get; set; } = new List<Guid>();
        public int DroppedUngrounded { get; set; }
        public double? Rrr { get; set; }
        public bool RrrBlockedConsolidation { get; set; }
        public ConsolidationOut? Consolidation { get; set; }
        public List<Guid> PrunedComponentIds { get; set; } = new List<Guid>();
        public int EvictedCacheRows { get; set; }
        public double PressureBefore { get; set; }
        public double PressureAfter { get; set; }
        public string IdentityVersion { get; set; } = "";
        public bool IdentityDocumentNew { get; set; }
        public ReflectInstrumentation Instrumentation { get; set; } =
            new ReflectInstrumentation();
    }

    // -- read path ------------------------------------------------------

    public sealed class WeightOverrides
    {
        public double? Relevance { get; set; }
        public double? Recency { get; set; }
        public double? Importance { get; set; }
    }

    public sealed class DialogueInitRequest
    {
        public Guid AgentId { get; set; }
        public string QueryText { get; set; } = "";
        public int? K { get; set; }
        public string? LocationName { get; set; }
        public List<string>? Entities { get; set; }
        public DateTimeOffset? EventTime { get; set; }
        public DateTimeOffset? AsOf { get; set; }
        public string? IdentityVersion { get; set; }
        public DateTimeOffset? SceneStartedAt { get; set; }
        public List<Guid>? LoadedMemoryIds { get; set; }
        public int GateFruitlessStreak { get; set; }
    }

    public sealed class RetrievedMemory
    {
        public Guid MemoryId { get; set; }
        public Guid DetailId { get; set; }
        public string Content { get; set; } = "";
        public string ReadMode { get; set; } = "";
        public bool Pinned { get; set; }
        public double Score { get; set; }
        public double? Relevance { get; set; }
        public double Recency { get; set; }
        public double ImportanceNorm { get; set; }
        public double ImportanceRaw { get; set; }
        public bool GateFetched { get; set; }
    }

    public sealed class GateInstrumentation
    {
        public bool Evaluated { get; set; }
        public bool Fired { get; set; }
        public List<string> SignalsFired { get; set; } = new List<string>();
        public string? DegradedRung { get; set; }
        public double? NoveltyMinDistance { get; set; }
        public int NullEmbeddingLoadedCount { get; set; }
        public int LoadedMissingCount { get; set; }
        public List<string> UncoveredEntities { get; set; } = new List<string>();
        public List<Guid> FetchedMemoryIds { get; set; } = new List<Guid>();
        public int FetchedNewCount { get; set; }
        public bool Fruitless { get; set; }
        public bool DamperActive { get; set; }
        public bool? NoveltyOutscored { get; set; }
        public bool? EntityCovered { get; set; }
        public double GateMs { get; set; }
        public bool ReconstructingBlocked { get; set; }
    }

    public sealed class RetrievalInstrumentation
    {
        public double EmbedMs { get; set; }
        public double SqlMs { get; set; }
        public double ScoreMs { get; set; }
        public double TotalMs { get; set; }
        public int EmbeddingTokens { get; set; }
        public int CandidateCount { get; set; }
        public int KEffective { get; set; }
        public double LexicalSqlMs { get; set; }
        public int LexicalCandidateCount { get; set; }
        public bool Degraded { get; set; }
        public string? DegradedReason { get; set; }
        public DateTimeOffset AsOfEffective { get; set; }
        public bool ContextActive { get; set; }
        public List<string> ContextComponents { get; set; } = new List<string>();
        public double ReconstructionMs { get; set; }
        public int ReconstructionInputTokens { get; set; }
        public int ReconstructionOutputTokens { get; set; }
        public int ReconstructionEmbedTokens { get; set; }
        public int CacheHits { get; set; }
        public int CacheMisses { get; set; }
        public int WriteBacks { get; set; }
        public int DriftRefusals { get; set; }
        public string? IdentityVersionEffective { get; set; }
        public bool IdentityBootstrapped { get; set; }
        public GateInstrumentation Gate { get; set; } = new GateInstrumentation();
    }

    public sealed class RetrievalResult
    {
        public List<RetrievedMemory> Items { get; set; } = new List<RetrievedMemory>();
        public RetrievalInstrumentation Instrumentation { get; set; } =
            new RetrievalInstrumentation();
    }

    // -- dialogue turn --------------------------------------------------

    /// <summary>One (memory_id, score) tuple in the weight-ranked view that
    /// fed the prose prompt (weights-on-speech, A1 re-shape 2026-08-04).
    /// On a loader turn at default weights DialogueView equals the
    /// (id, score) projection of Items — the parity contract; on gated
    /// turns Items keeps the loaded+fetched serve shape while DialogueView
    /// is the global weight ranking.</summary>
    public sealed class ScoredRef
    {
        public Guid MemoryId { get; set; }
        public double Score { get; set; }
    }

    public sealed class DialogueTurnRequest
    {
        public Guid AgentId { get; set; }
        public string Utterance { get; set; } = "";
        public int? K { get; set; }
        public DateTimeOffset? AsOf { get; set; }
        public string? LocationName { get; set; }
        public List<string>? Entities { get; set; }
        public DateTimeOffset? EventTime { get; set; }
        public string? IdentityVersion { get; set; }
        public DateTimeOffset? SceneStartedAt { get; set; }

        /// <summary>null = LOADER TURN; an empty list = an empty loaded set
        /// the gate still evaluates. Never collapse one into the other.</summary>
        public List<Guid>? LoadedMemoryIds { get; set; }

        public int GateFruitlessStreak { get; set; }
        public WeightOverrides? WeightOverrides { get; set; }

        /// <summary>The compiled-parameter scene type (C3, 2026-08-17):
        /// selects which compiled bundles multiply the prose-view weights.
        /// null = the reserved default type; an unconfigured value
        /// log-and-continues against the default server-side (flagged in
        /// the instrumentation echo).</summary>
        public string? SceneType { get; set; }

        public bool Debug { get; set; }
    }

    public sealed class DialogueTurnInstrumentation
    {
        public RetrievalInstrumentation Retrieval { get; set; } =
            new RetrievalInstrumentation();
        public double SonnetMs { get; set; }
        public double SonnetFirstTokenMs { get; set; }
        public double TotalMs { get; set; }
        public int SonnetInputTokens { get; set; }
        public int SonnetOutputTokens { get; set; }
        public double? CostUsd { get; set; }
        public bool Degraded { get; set; }
        public string? DegradedReason { get; set; }
        public double FirstWordMs { get; set; }
        public double ProseStreamMs { get; set; }
        public double PerceivedFirstWordMs { get; set; }

        // Parameter-compiler consume terms (C3, 2026-08-17): the composed
        // multiplier products applied over the resolved weights — all 1.0
        // with zero bundles (the parity contract) — plus the resolved scene
        // type, its unknown flag, the contributing beliefs in window order,
        // and the consume read's per-turn cost.
        public string SceneTypeResolved { get; set; } = "default";
        public bool SceneTypeUnknown { get; set; }
        public double BundleWRelevance { get; set; } = 1.0;
        public double BundleWRecency { get; set; } = 1.0;
        public double BundleWImportance { get; set; } = 1.0;
        public List<Guid> BundleReflectionIds { get; set; } = new List<Guid>();
        public double BundleFetchMs { get; set; }
    }

    public sealed class DialogueTurnResult
    {
        public Guid AgentId { get; set; }
        public string Content { get; set; } = "";
        public List<RetrievedMemory> Items { get; set; } = new List<RetrievedMemory>();
        public List<ScoredRef> DialogueView { get; set; } = new List<ScoredRef>();
        public DialogueTurnInstrumentation Instrumentation { get; set; } =
            new DialogueTurnInstrumentation();
    }

    // -- inspector reads (The Ledger's data source) ---------------------

    public sealed class DetailVersionOut
    {
        public Guid DetailId { get; set; }
        public string Content { get; set; } = "";
        public string? WriteCause { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset ValidAt { get; set; }
        public DateTimeOffset? InvalidAt { get; set; }
        public bool IsLive { get; set; }
    }

    public sealed class FactVersionOut
    {
        public Guid FactVersionId { get; set; }
        public string BasisText { get; set; } = "";
        public string? WriteCause { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset ValidAt { get; set; }
        public DateTimeOffset? InvalidAt { get; set; }
        public bool IsLive { get; set; }
        public bool HasEmbedding { get; set; }
        public List<string> Entities { get; set; } = new List<string>();
    }

    public sealed class GistSpanOut
    {
        public Guid SpanId { get; set; }
        public int StartChar { get; set; }
        public int EndChar { get; set; }
        public string? MatchedCategory { get; set; }
    }

    public sealed class EnrichmentRunOut
    {
        public int Attempt { get; set; }
        public string Outcome { get; set; } = "";
        public string? Error { get; set; }
        public List<string> Triggers { get; set; } = new List<string>();
        public bool EscalationFailed { get; set; }
        public bool EmbeddingRepaired { get; set; }
        public double? WriteMs { get; set; }
        public double? EscalationMs { get; set; }
        public double? EmbedMs { get; set; }
        public double? InsertMs { get; set; }
        public double? TotalMs { get; set; }
        public int WriteInputTokens { get; set; }
        public int WriteOutputTokens { get; set; }
        public int EscalationInputTokens { get; set; }
        public int EscalationOutputTokens { get; set; }
        public int EmbeddingTokens { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }

    /// <summary>One diegetic confrontation record (C4, dissonance.md) —
    /// the verb, the head it produced, and the client's in-world reference
    /// verbatim; the unscored chain read is its inspector surface.</summary>
    public sealed class CorrectionOut
    {
        public Guid CorrectionId { get; set; }
        public Guid DetailId { get; set; }
        public string Verb { get; set; } = "";
        public JObject? SourceEvent { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset ValidAt { get; set; }
    }

    public sealed class MemoryChainResult
    {
        public Guid MemoryId { get; set; }
        public Guid AgentId { get; set; }
        public string ObservationText { get; set; } = "";
        public string Provenance { get; set; } = "";
        public string? Typology { get; set; }
        public string? DecayClass { get; set; }
        public bool Pinned { get; set; }
        public bool ScoringFailed { get; set; }
        public bool EscalationFailed { get; set; }
        public bool DecayClassUnknown { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset ValidAt { get; set; }
        public DateTimeOffset? InvalidAt { get; set; }
        public string? LocationName { get; set; }
        public DateTimeOffset? EventTime { get; set; }
        public bool EnrichmentPending { get; set; }
        public int EnrichmentAttempts { get; set; }
        public List<EnrichmentRunOut> EnrichmentRuns { get; set; } = new List<EnrichmentRunOut>();
        public List<DetailVersionOut> Details { get; set; } = new List<DetailVersionOut>();
        public List<FactVersionOut> Facts { get; set; } = new List<FactVersionOut>();
        public List<GistSpanOut> GistSpans { get; set; } = new List<GistSpanOut>();
        public List<CorrectionOut> Corrections { get; set; } = new List<CorrectionOut>();
        public double TotalMs { get; set; }
    }

    public sealed class MemorySummaryOut
    {
        public Guid MemoryId { get; set; }
        public string ObservationText { get; set; } = "";
        public string? LiveContent { get; set; }
        public string? LiveWriteCause { get; set; }
        public int DetailCount { get; set; }
        public bool Pinned { get; set; }
        public DateTimeOffset ValidAt { get; set; }
        public DateTimeOffset? InvalidAt { get; set; }
    }

    public sealed class AgentMemoriesResult
    {
        public Guid AgentId { get; set; }
        public List<MemorySummaryOut> Memories { get; set; } = new List<MemorySummaryOut>();
        public int TotalCount { get; set; }
        public int Limit { get; set; }
        public double TotalMs { get; set; }
    }

    public sealed class ReconstructionMetricsResult
    {
        public Guid MemoryId { get; set; }
        public Guid AgentId { get; set; }
        public Guid? LiveDetailId { get; set; }
        public string? LiveWriteCause { get; set; }
        public string? AnchorCause { get; set; }
        public int GistFactsTotal { get; set; }
        public int GistFactsPresent { get; set; }
        public double? GistPrecision { get; set; }
        public int DetailLemmasTotal { get; set; }
        public int DetailLemmasPresent { get; set; }
        public double? DetailRecall { get; set; }
        public List<string> TellingEntities { get; set; } = new List<string>();
        public List<string> FabricatedEntities { get; set; } = new List<string>();
        public double? FabricationRate { get; set; }
        public double? KeywordRetention { get; set; }
        public List<int> CacheBands { get; set; } = new List<int>();
        public double MetricsMs { get; set; }
        public double TotalMs { get; set; }
    }

    // -- the agent-state read (C5, ruled 2026-08-17) --------------------

    /// <summary>One live belief as the state read serves it, in the ruled
    /// compiler-window order — the first compiler_window_k rows ARE the
    /// compile window.</summary>
    public sealed class ReflectionSummaryOut
    {
        public Guid ReflectionId { get; set; }
        public string Content { get; set; } = "";
        public bool IdentityRelevant { get; set; }
        public List<Guid> SourceMemoryIds { get; set; } = new List<Guid>();
        public DateTimeOffset ValidAt { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }

    /// <summary>The newest live bundle per (belief, scene_type) —
    /// Passthrough is the integrator's namespaced data verbatim,
    /// stored-never-interpreted server-side (this read is its recorded
    /// surface).</summary>
    public sealed class CompiledBundleOut
    {
        public Guid BundleId { get; set; }
        public Guid ReflectionId { get; set; }
        public string SceneType { get; set; } = "";
        public double WRelevance { get; set; }
        public double WRecency { get; set; }
        public double WImportance { get; set; }
        public JObject Passthrough { get; set; } = new JObject();
        public int InputTokens { get; set; }
        public int OutputTokens { get; set; }
        public double? CompileMs { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }

    /// <summary>One reflection-worker run row (migration 007, full mirror).
    /// Endpoint reflects write NO row — the endpoint/worker split.</summary>
    public sealed class ReflectionRunOut
    {
        public Guid RunId { get; set; }
        public string Outcome { get; set; } = "";
        public string? Error { get; set; }
        public int ReflectionsWritten { get; set; }
        public int DroppedUngrounded { get; set; }
        public bool ConsolidationRan { get; set; }
        public bool ConsolidationFailed { get; set; }
        public double? Rrr { get; set; }
        public bool RrrBlocked { get; set; }
        public int PrunedComponents { get; set; }
        public int EvictedCacheRows { get; set; }
        public double? PressureBefore { get; set; }
        public double? PressureAfter { get; set; }
        public double? ReflectMs { get; set; }
        public double? ConsolidationMs { get; set; }
        public double? InsertMs { get; set; }
        public double? TotalMs { get; set; }
        public int ReflectInputTokens { get; set; }
        public int ReflectOutputTokens { get; set; }
        public int ConsolidationInputTokens { get; set; }
        public int ConsolidationOutputTokens { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }

    /// <summary>One compiler-worker run row (migration 008, full mirror) —
    /// every row is worker-written; C3 has no endpoint verb.</summary>
    public sealed class CompilerRunOut
    {
        public Guid RunId { get; set; }
        public string Outcome { get; set; } = "";
        public string? Error { get; set; }
        public int PairsCompiled { get; set; }
        public int PairsFailed { get; set; }
        public int PassthroughKeysDropped { get; set; }
        public int InputTokens { get; set; }
        public int OutputTokens { get; set; }
        public double? TotalMs { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }

    /// <summary>GET /v1/agents/{id}/state — the composed runtime snapshot
    /// (C5): the stored row (Config AS STORED, defaults never merged), the
    /// current identity version (null = never compiled), the pressure gauge
    /// (computed server-side, never stored), live beliefs, derived-liveness
    /// bundles, and both workers' run logs newest-first. The fourth
    /// unscored-by-contract read: structured fields, no scores.</summary>
    public sealed class AgentStateResult
    {
        public Guid AgentId { get; set; }
        public string? Name { get; set; }
        public string? SeedIdentity { get; set; }
        public double? Rigidity { get; set; }
        public string? DiagnosticityGoal { get; set; }
        public JObject Config { get; set; } = new JObject();
        public string? IdentityVersion { get; set; }
        public DateTimeOffset? IdentityCompiledAt { get; set; }
        public double ReflectionPressure { get; set; }
        public List<ReflectionSummaryOut> Reflections { get; set; } =
            new List<ReflectionSummaryOut>();
        public List<CompiledBundleOut> CompiledBundles { get; set; } =
            new List<CompiledBundleOut>();
        public List<ReflectionRunOut> ReflectionRuns { get; set; } =
            new List<ReflectionRunOut>();
        public List<CompilerRunOut> CompilerRuns { get; set; } =
            new List<CompilerRunOut>();
        public int RunsLimit { get; set; }
        public double TotalMs { get; set; }
    }
}
