"""config.py — environment + integrator-knob loading for the write and read paths.

Secrets and connection strings live only in the gitignored repo-root .env
(same manual parse as db\\migrate.py — no dotenv dependency). Never print or
log values loaded from .env.

Model roles (architecture §3): every role has its own env var. The v1 write
call serves render + importance + typology in ONE Haiku call, so at startup
in real mode the three role vars must name the same model — divergence is a
loud config error, never a silent pick (ruled with the write-path plan,
2026-07-13). The dialogue role (TWICETOLD_MODEL_DIALOGUE, cli-harness build
2026-07-15) streams PURE PROSE — the dialogue turn's only model call since
the A1 re-shape (2026-08-04; the split-brain `behavior` role was removed by
ruling, real mode 7 -> 6 vars). The reconstruction role
(TWICETOLD_MODEL_RECONSTRUCTION) is the Haiku-class batched retelling call
(architecture.md §7).

The model BACKEND (the provider-path build, ruled 2026-09-01; shape ruled
2026-09-02) is one explicit selector for every LLM role: TWICETOLD_MODEL_BACKEND
= "anthropic" (the default — today's requests byte-for-byte) or "openai" (the
OpenAI-compatible chat-completions family behind TWICETOLD_MODEL_BASE_URL). The
embedding role carries its own independent knobs (model name, base URL, key).
Fake mode reads none of the URL/key requirements — it constructs no client.

Service-level defaults below are integrator-overridable per agent via
`agents.config` keys of the same name (nothing integrator-configurable is
hardcoded). `agents.config` additionally carries:
  - "decay_classes": {label: tau_base_seconds, ...}  (migration-01 ruling)
  - "decay_class_default": the label applied when an event omits or supplies
    an unknown decay_class label.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

# The embedding DIMENSION is a locked constant, not a knob (architecture.md
# §3: embedding dimension 1536, locked; migration 001's vector(1536) column). The
# embedding MODEL NAME became a knob with the provider-path build (ruled
# 2026-09-01/02): TWICETOLD_EMBEDDING_MODEL, defaulting to the model the locked
# slate was measured on. Narrower models are zero-padded to the locked width at
# the provider seam (ruled 2026-09-02); wider ones are refused there.
EMBEDDING_MODEL_DEFAULT = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Env var names — one per model role (architecture §3).
ENV_MODEL_IMPORTANCE = "TWICETOLD_MODEL_IMPORTANCE"
ENV_MODEL_RENDER = "TWICETOLD_MODEL_RENDER"
ENV_MODEL_TYPOLOGY = "TWICETOLD_MODEL_TYPOLOGY"
ENV_MODEL_ESCALATION = "TWICETOLD_MODEL_ESCALATION"
ENV_MODEL_DIALOGUE = "TWICETOLD_MODEL_DIALOGUE"
ENV_MODEL_RECONSTRUCTION = "TWICETOLD_MODEL_RECONSTRUCTION"
ENV_PROVIDER_MODE = "TWICETOLD_PROVIDER_MODE"
# Eval-runner-only judge role (eval-harness.md stage 3, ruled 2026-07-29):
# loaded in BOTH modes, required by NEITHER — the server/REPL never needs a
# judge; the eval runner validates it itself when a judged run starts.
ENV_MODEL_JUDGE = "TWICETOLD_MODEL_JUDGE"
# Reflection role (reflection.md; the C2 dossier ruling 2026-08-15): the
# judge shape exactly — loaded in BOTH modes, required by NEITHER, loud at
# the first real reflect call (build_reflection_provider raises ConfigError).
# The server starts fine without it; only a real-mode reflect needs it.
ENV_MODEL_REFLECTION = "TWICETOLD_MODEL_REFLECTION"
# Compiler role (parameter-compiler.md; the C3 rulings 2026-08-17): the
# THIRD judge-shaped var — loaded in BOTH modes, required by NEITHER, loud
# at the first real compile call (build_compiler_provider raises
# ConfigError). C3 has no endpoint verb, so that first call is always the
# worker's; the server starts fine without the var.
ENV_MODEL_COMPILER = "TWICETOLD_MODEL_COMPILER"
# Dialogue thinking knob (B2 ruling 2026-08-07): "" (unset) omits the thinking
# parameter from the real prose call entirely — today's request byte-for-byte;
# "disabled" sends thinking={"type": "disabled"} (the sonnet-5 thinking-off
# compare arm). Set per-arm via compare overlays, not globally.
ENV_DIALOGUE_THINKING = "TWICETOLD_DIALOGUE_THINKING"
# Bounded max_tokens for judge calls (adaptive thinking spends against it).
ENV_JUDGE_MAX_TOKENS = "TWICETOLD_JUDGE_MAX_TOKENS"
JUDGE_MAX_TOKENS_DEFAULT = 2048
# Concurrency cap (C7 / audit R8, 2026-08-18): the max provider (model) calls
# in flight at once across the whole process — the single ceiling the
# ModelCallGate enforces (app\concurrency.py). Process-level like the worker
# poll intervals (an agent cannot own a thread pool), so it is a Settings field
# with its own env var, not a per-agent SERVICE_DEFAULTS knob. Default aligns
# with the DB pool max_size (TWICETOLD_DB_POOL_MAX_SIZE below) so the cap never
# starves on a connection; raise both together. Integrator-tunable — nothing
# hardcoded.
ENV_MAX_CONCURRENT_MODEL_CALLS = "TWICETOLD_MAX_CONCURRENT_MODEL_CALLS"
MAX_CONCURRENT_MODEL_CALLS_DEFAULT = 8
# DB pool ceiling (F0, 2026-08-26): db.build_pool's max_size, the other half
# of the "raise both together" pair — the same process-level shape, closing
# the last hardcoded capacity number (the nothing-hardcoded invariant).
# min_size stays 1 in build_pool: not knobbed, surfaced at F0.
ENV_DB_POOL_MAX_SIZE = "TWICETOLD_DB_POOL_MAX_SIZE"
DB_POOL_MAX_SIZE_DEFAULT = 8

# The model backend (the provider-path build, ruled 2026-09-01; the explicit
# selector ruled 2026-09-02): ONE selector for every LLM role — the six product
# roles and the three judge-shaped ones. "anthropic" (the default) is today's
# path byte-for-byte; "openai" is the OpenAI-compatible chat-completions
# family (OpenAI, Ollama, vLLM, LM Studio, llama.cpp server, OpenRouter,
# LiteLLM, ...) reached through TWICETOLD_MODEL_BASE_URL. The same six role
# vars name the models on either backend. Misconfigurations are loud at
# load_settings: a base URL or key under the anthropic backend, a missing base
# URL under openai, the Anthropic-shaped dialogue-thinking knob under openai,
# max_completion_tokens under anthropic (whose wire field is always
# max_tokens). Fake mode constructs no client and needs no URL or key.
ENV_MODEL_BACKEND = "TWICETOLD_MODEL_BACKEND"
MODEL_BACKENDS = ("anthropic", "openai")
MODEL_BACKEND_DEFAULT = "anthropic"
ENV_MODEL_BASE_URL = "TWICETOLD_MODEL_BASE_URL"
# Optional on the openai backend: local servers ignore the key, hosted ones
# need it. The openai SDK refuses an EMPTY key at construction, so the
# placeholder below is what a keyless base-URL path actually sends.
ENV_MODEL_API_KEY = "TWICETOLD_MODEL_API_KEY"
PLACEHOLDER_API_KEY = "twicetold-no-key"
# The openai backend's token-limit FIELD NAME (ruled 2026-09-03): local
# servers document max_tokens; hosted OpenAI's reasoning-class models demand
# max_completion_tokens. The knob names the wire field only — the per-role
# VALUES are unchanged, and the anthropic backend always sends max_tokens.
ENV_MODEL_TOKEN_LIMIT_FIELD = "TWICETOLD_MODEL_TOKEN_LIMIT_FIELD"
MODEL_TOKEN_LIMIT_FIELDS = ("max_tokens", "max_completion_tokens")
MODEL_TOKEN_LIMIT_FIELD_DEFAULT = "max_tokens"
# The embedding role's own knobs, independent of the model backend (never
# inherited from it — explicit, loud): the model name (default = the locked
# slate's model), an optional base URL (set => the openai client targets it
# and OPENAI_API_KEY is no longer required), and an optional key for that URL.
ENV_EMBEDDING_MODEL = "TWICETOLD_EMBEDDING_MODEL"
ENV_EMBEDDING_BASE_URL = "TWICETOLD_EMBEDDING_BASE_URL"
ENV_EMBEDDING_API_KEY = "TWICETOLD_EMBEDDING_API_KEY"
# The hosted endpoints, passed EXPLICITLY to both SDK clients: with base_url
# omitted, each SDK silently honors an OPENAI_BASE_URL / ANTHROPIC_BASE_URL
# process variable, which could re-route a key to a stranger's host. Same
# bytes on the wire as the SDK defaults; no stray-env redirect.
ANTHROPIC_HOSTED_BASE_URL = "https://api.anthropic.com"
OPENAI_HOSTED_BASE_URL = "https://api.openai.com/v1"

# Optional per-Mtok USD prices (CLI-harness build ruling, 2026-07-15): cost
# fields carry token counts unconditionally; USD appears only when these are
# set. No model pricing is ever hardcoded. Maps env var -> Settings.prices key.
PRICE_ENV_KEYS: dict[str, str] = {
    "TWICETOLD_PRICE_DIALOGUE_IN": "dialogue_in",
    "TWICETOLD_PRICE_DIALOGUE_OUT": "dialogue_out",
    "TWICETOLD_PRICE_WRITE_IN": "write_in",
    "TWICETOLD_PRICE_WRITE_OUT": "write_out",
    "TWICETOLD_PRICE_ESCALATION_IN": "escalation_in",
    "TWICETOLD_PRICE_ESCALATION_OUT": "escalation_out",
    "TWICETOLD_PRICE_RECONSTRUCTION_IN": "reconstruction_in",
    "TWICETOLD_PRICE_RECONSTRUCTION_OUT": "reconstruction_out",
    "TWICETOLD_PRICE_EMBEDDING": "embedding",
    "TWICETOLD_PRICE_JUDGE_IN": "judge_in",
    "TWICETOLD_PRICE_JUDGE_OUT": "judge_out",
    "TWICETOLD_PRICE_REFLECTION_IN": "reflection_in",
    "TWICETOLD_PRICE_REFLECTION_OUT": "reflection_out",
    "TWICETOLD_PRICE_COMPILER_IN": "compiler_in",
    "TWICETOLD_PRICE_COMPILER_OUT": "compiler_out",
}

# Service-level defaults, each overridable per agent via the same key in
# agents.config (write-path plan rulings, 2026-07-13).
SERVICE_DEFAULTS: dict[str, float] = {
    # Neutral importance applied when the scoring model fails (scoring_failed).
    "importance_neutral": 0.5,
    # Escalation trigger (1): importance_raw >= this.
    "escalation_importance_threshold": 0.45,
    # Escalation trigger (2): identity/category hit co-occurring with
    # |valence| >= this.
    "escalation_affect_threshold": 0.5,
    # Escalation trigger (6), thin_gist (ruled 2026-07-23): fire when the base
    # NLP pass yields fewer gist spans than this floor — protects the gist
    # (reconstruction's fixed constraint) directly; 16/80 realistic observes
    # otherwise land with zero spans. 0.0 disables the trigger.
    "escalation_min_base_spans": 1.0,
    # Escalation trigger (5) threshold — RESERVED, not consulted in v1: neither
    # fastcoref's predict API nor en_core_web_lg's greedy NER exposes per-span
    # confidence, so every coref-derived span counts as low-confidence outright
    # (over-call only; see app\nlp.py). Becomes live when a confidence source exists.
    "nlp_confidence_threshold": 0.5,
    # Default per-typology confidence when the client declares a typology
    # without a confidence (architecture §5: a default table exists; single
    # scalar default until the table earns per-typology entries).
    "typology_confidence_default": 0.9,
    # --- read path (architecture.md §6) -------------------------------------
    # Default top-k for dialogue-init retrieval.
    "retrieval_top_k": 8,
    # Vector over-fetch: fetch ceil(factor * k) candidates by distance, then
    # re-rank by the full score.
    "retrieval_overfetch_factor": 4.0,
    # k in tau_effective = tau_base * (1 + k * importance_raw) — shared by the
    # recency score component and, at reconstruction, the theta check
    # (one formula, one implementation: app\decay.py).
    "decay_k_importance": 1.0,
    # importance_norm = clamp(importance_raw, floor, 1.0): the floor keeps the
    # multiplicative score from zeroing a memory out of existence.
    "importance_norm_floor": 0.05,
    # tau_base when neither the stored decay-class label nor the agent's
    # default class resolves in agents.config — a read never fails on a
    # resolvable row.
    "tau_fallback_seconds": 604800.0,
    # --- reconstruction (architecture.md §7) --------------------------------
    # Reconstruct when decayed detail strength (= decay.recency at the
    # scene-frozen basis) falls below theta. Pinned rows are exempt.
    "reconstruction_theta": 0.5,
    # Band quantum: band_index = floor((1 - strength) / quantum). The band
    # composes the cache key with identity_version AND sets the thinning
    # level (the band's midpoint strength), so same key => same input.
    "reconstruction_band_quantum": 0.25,
    # Drift budget: refuse a reconstruction write-back whose embedding's
    # cosine distance from the anchor exceeds this (ruled 2026-07-17). Scope
    # (R7 resolved 2026-08-12): a TOPIC guard — catches wholesale nonsense /
    # topic-swaps; measured blind to fact-level drift (stage-4 ablation).
    # Factual faithfulness is policed by the gist constraint + gist-precision
    # and the judged faithfulness category, never by this threshold.
    "drift_budget_threshold": 0.35,
    # Fixed-gist constraint switch (eval-harness stage 4, ruled 2026-08-12):
    # 0.0 => original-anchored retellings run WITHOUT the gist block (the
    # ablation's OFF arm — R7's deciding data). Correction-anchored chains
    # ignore the switch (fork 11: their gist IS the corrected head; blanking
    # it would delete the correction). The gate_enabled kill-switch shape;
    # production stays 1.0.
    "reconstruction_gist_constraint": 1.0,
    # --- mid-dialogue gate (mid-dialogue-gate.md; build rulings 2026-07-19) --
    # Non-LLM: no gate model role, no pricing entry. All floats (agent_knob
    # contract); integer-valued knobs are cast at the call site.
    # Novelty fires when the min cosine distance from the utterance embedding
    # to the loaded set's fact-head embeddings is >= this. Calibration split
    # honestly (measured at build): fake-provider echoes ~0.04, near-copies
    # ~0.08, ordinary distinct prose ~0.45-0.75 (fixture property — shared
    # English trigrams keep unrelated sentences under the naive ~1.0);
    # real-provider paraphrase ~0.05-0.25; 0.5 sits above the 0.35 drift
    # line's "left the neighborhood".
    "gate_novelty_threshold": 0.5,
    # New items appended per gate fetch (a full retrieval_top_k re-fetch
    # would swamp the loaded set).
    "gate_fetch_k": 3.0,
    # Damper (ruled 2026-07-19): after this many CONSECUTIVE fruitless
    # fetches (zero new IDs appended), the novelty signal is suppressed for
    # the scene remainder; the entity tripwire stays live; scene boundary
    # resets.
    "gate_damper_fruitless_max": 2.0,
    # Whole-gate switch: 0.0 => every request is a loader turn (v1 behavior).
    # The fixture-pin shape (the reconstruction_theta = 0 precedent) and the
    # integrator kill-switch scaffold — the reserved per-signal kill-switch
    # decision may later grow its own knobs.
    "gate_enabled": 1.0,
    # --- encoding-context read term (architecture.md §6) --------------------
    # The formerly-reserved DialogueInitRequest context fields become a soft
    # multiplicative nudge: score *= (1 + sum(w_i * match_i)) over the
    # components the REQUEST supplies (client-supplied fields, ruled — no LLM
    # query decomposition; the 2026-07-14 query-embedded-as-is ruling stands).
    # A request with no context fields skips the term entirely — scores stay
    # byte-identical to v1 (the loader-parity precedent). Never a hard filter:
    # a non-matching row loses no score (match floors at 0).
    "context_weight_entities": 0.25,
    "context_weight_event_time": 0.25,
    "context_weight_location": 0.25,
    # Time-proximity kernel scale: match = exp(-|event_time - query|/scale).
    "context_time_scale_seconds": 86400.0,
    # --- hybrid lexical channel (architecture.md §6) ------------------------
    # Lexical candidates unioned into the vector over-fetch before scoring
    # (dedup by memory_id; the scoring formula is untouched — lexical-only
    # hits carry their TRUE cosine relevance where the fact head has an
    # embedding). 0.0 disables the channel (the gate_enabled kill-switch
    # shape): pure-vector candidates, v1-byte-identical.
    "lexical_fetch_k": 8.0,
    # --- weights-on-speech (A1 re-shape, ruled 2026-08-04; formerly the
    # split-brain behavior view, built 2026-07-21) ---------------------------
    # Per-call WeightOverrides re-rank the SAME served top-k that retrieval
    # produced, feeding the PROSE prompt — the NPC's words shaped by weights
    # it is unaware of. Weights apply as exponents on the product score
    # component-wise (weighted_score = item.score * rel^(w_rel-1) *
    # rec^(w_rec-1) * imp^(w_imp-1)) — so 1.0 reproduces the served ranking
    # exactly (the parity contract) and any other value genuinely re-ranks.
    # Resolution is request field -> agents.config -> these defaults, then
    # clamped to [WEIGHT_MIN, WEIGHT_MAX].
    "weight_relevance": 1.0,
    "weight_recency": 1.0,
    "weight_importance": 1.0,
    # --- judge-free eval metrics (eval-harness.md stage 1; ruled 2026-07-29) --
    # Gist-precision presence rule: a gist fact counts as present when this
    # fraction of its content lemmas appears in the live telling's lemma set.
    # 1.0 = strict lexical (the fork-2 ruling); paraphrase slack belongs to
    # the judged faithfulness category, never to this knob.
    "metric_gist_match_threshold": 1.0,
    # --- deferred write processing (deferred-writes.md; ruled 2026-08-12) ----
    # Kill-switch: 0.0 (the landing default) = every observe enriches
    # synchronously — the pre-C1 path byte-for-byte. Non-zero defers the two
    # LLM calls (write call + escalation) to the worker; the NLP pass,
    # embedding, and insert stay synchronous. Gates DEFERRAL only — the
    # worker always drains pending rows, so flipping back to 0.0 never
    # strands a row. Default flips at Phase D if the numbers earn it.
    "deferred_writes_enabled": 0.0,
    # Worker poll interval between drain passes. Process-level: the worker
    # has no agent context, so this reads from the service defaults (an
    # agents.config override of it is inert by design).
    "deferred_poll_seconds": 1.0,
    # Rows claimed per drain batch (integer-valued, cast at the call site).
    "deferred_batch_size": 8.0,
    # Failed attempts before the terminal degraded completion — the row then
    # lands in today's sync scoring-failed end-state (integer-valued, cast at
    # the call site).
    "deferred_max_attempts": 3.0,
    # --- reflection (reflection.md; the C2 rulings 2026-08-15) ---------------
    # Per-agent worker kill-switch: 0.0 = the worker never auto-reflects this
    # agent. Gates the WORKER's auto-pull only — the reflect endpoint is
    # always live regardless.
    "reflection_worker_enabled": 0.0,
    # Worker sweep interval. Process-level (the deferred_poll_seconds
    # precedent: the worker has no agent context; an agents.config override
    # is inert by design).
    "reflection_poll_seconds": 60.0,
    # Max agents reflected per sweep — a cost bound, not a queue
    # (integer-valued, cast at the call site).
    "reflection_worker_batch": 4.0,
    # The worker pulls an enabled agent at/above this pressure.
    "reflection_pressure_threshold": 1.0,
    # The divisor defining what pressure 1.0 means (~ the unprocessed
    # importance mass that should trigger a reflection).
    "reflection_pressure_norm": 10.0,
    # Episodes sampled per reflect: deterministic top-k by
    # importance_norm x recency, ties on memory_id — never a lottery
    # (integer-valued, cast at the call site).
    "reflection_sample_k": 16.0,
    # Below this live-episode count the reflect verb 409s (integer-valued,
    # cast at the call site).
    "reflection_min_episodes": 4.0,
    # RRR (self-repetition) at/above this blocks the consolidation stage —
    # the reflection itself still stores (the paper default).
    "reflection_rrr_threshold": 0.85,
    # Recent live reflections compared for RRR (integer-valued, cast at the
    # call site).
    "reflection_rrr_window": 8.0,
    # Live identity-relevant count that triggers the consolidation stage;
    # the request's `consolidate` field overrides per call (integer-valued,
    # cast at the call site).
    "reflection_consolidate_at": 5.0,
    # The trim staleness window (30 days): a component prunes only when ALL
    # its span evidence sits on live memories older than this. 0.0 disables
    # the trim entirely (the gate_enabled kill-switch shape).
    "reflection_trim_stale_seconds": 2592000.0,
    # --- parameter compiler (parameter-compiler.md; the C3 rulings ---------
    # 2026-08-17) -----------------------------------------------------------
    # Per-agent worker kill-switch: 0.0 = the worker never compiles this
    # agent. C3 has no endpoint verb (the standalone-worker ruling), so this
    # gates compilation entirely; the consume side stays live either way
    # (zero bundles compose to the identity).
    "compiler_worker_enabled": 0.0,
    # Worker sweep interval. Process-level (the reflection_poll_seconds
    # precedent: the worker has no agent context; an agents.config override
    # is inert by design).
    "compiler_poll_seconds": 60.0,
    # Max compile CALLS per sweep across agents — a cost bound, not a queue
    # (integer-valued, cast at the call site). Missing pairs beyond the
    # budget persist; the next sweep continues them. Process-level, like the
    # poll interval.
    "compiler_worker_batch": 8.0,
    # The staleness-guard window (the C3 ruling): only the K most recent
    # live beliefs compile AND apply — enforced at work discovery and at the
    # consume fetch alike (integer-valued, cast at the call site).
    "compiler_window_k": 8.0,
    # --- dissonance path (architecture.md §8) -------------------------------
    # Evidence-typology multipliers for the mechanical defend-vs-update
    # decision (ruling 1): resistance = importance_norm * mult(memory.typology)
    # * rigidity vs challenge = challenge_weight * mult(challenge.typology);
    # strict > updates, ties defend. ONE table serves both sides ("'I saw it'
    # resists harder than 'I heard it,' on both sides of a clash"). 0.0 is the
    # per-side kill-switch shape: memory-side 0.0 => that class always folds;
    # challenge-side 0.0 => that class never wins. Defaults are Phase-D tuning
    # starting points, not measurements.
    "dissonance_typology_observed": 1.0,
    "dissonance_typology_told": 0.6,
    "dissonance_typology_inferred": 0.4,
    "dissonance_typology_reflected": 0.5,
    # Used ONLY when agents.rigidity IS NULL (the column carries no default by
    # design — the write path supplies it from integrator config); the resolved
    # value clamps to [0.5, 2.0] mirroring the schema CHECK as defense.
    "dissonance_rigidity_default": 1.0,
    # When the event omits challenge_weight: a full-strength confrontation.
    # Clamped [0.0, 1.0]. No dissonance_enabled kill-switch exists, consciously
    # (the event is client-invoked — not sending it is the off state; the
    # asymmetry vs the *_worker_enabled flags is deliberate).
    "dissonance_challenge_weight_default": 1.0,
}

# Prose-view weight clamp bounds (ruled at the split-brain build 2026-07-21;
# carried by the A1 re-shape): a soft de-/re-emphasis range, never a mask. 0.0
# zeroes a component's exponent contribution to +1 (pow(x, -1)); the ceiling
# bounds runaway emphasis. Module constants, not knobs — the range itself is
# not integrator policy (the EMBEDDING_DIM precedent for a fixed structural
# bound).
WEIGHT_MIN = 0.0
WEIGHT_MAX = 4.0

# Compiled-bundle multiplier clamp bounds (the C3 ruling 2026-08-17, frozen
# into migration 008's CHECK): one belief may move a prose-view weight axis
# by at most x4 in either direction and can never zero it — zeroing stays
# the caller's explicit weight-override privilege (WEIGHT_MIN above). Module
# constants, not knobs (the WEIGHT_MIN/MAX precedent); the compiler clamps
# at write and the consume path re-clamps as defense.
MULTIPLIER_MIN = 0.25
MULTIPLIER_MAX = 4.0

# The lexical channel's text-search config: a string knob, so it follows the
# decay_classes precedent (a plain agents.config key + a module default)
# rather than the float-only SERVICE_DEFAULTS/agent_knob contract. The
# migration-004 index expression bakes this default; an agent override still
# works but runs unindexed (correct, slower — stated in the migration).
TEXT_SEARCH_CONFIG_DEFAULT = "simple"


def text_search_config(agent_config: dict) -> str:
    """Per-agent text_search_config override, else the service default."""
    value = agent_config.get("text_search_config")
    return str(value) if value else TEXT_SEARCH_CONFIG_DEFAULT


# The compiler's scene-type vocabulary: an integrator-owned string list, so
# it follows the decay_classes / text_search_config precedent (a plain
# agents.config key + a module default) rather than the float-only
# SERVICE_DEFAULTS/agent_knob contract. The default is EMPTY — with no
# configured vocabulary only the reserved default scene type compiles; a
# hardcoded vocabulary would violate the never-hardcoded rule.
SCENE_TYPES_DEFAULT: tuple[str, ...] = ()


def scene_types(agent_config: dict) -> list[str]:
    """Per-agent scene-type vocabulary, else the (empty) service default."""
    value = agent_config.get("scene_types")
    if not isinstance(value, list):
        return list(SCENE_TYPES_DEFAULT)
    return [str(entry) for entry in value]


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    """Parse the repo-root .env into a dict. Values are never logged.

    A process environment variable of the same name overrides the .env value
    (lets verification point at the scratch DB without touching .env).
    """
    if not path.exists():
        sys.exit(f"ERROR: {path} not found; .env is required.")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    overridable = (
        set(values)
        | {
            "DATABASE_URI",
            ENV_PROVIDER_MODE,
            ENV_MODEL_IMPORTANCE,
            ENV_MODEL_RENDER,
            ENV_MODEL_TYPOLOGY,
            ENV_MODEL_ESCALATION,
            ENV_MODEL_DIALOGUE,
            ENV_MODEL_RECONSTRUCTION,
            ENV_MODEL_JUDGE,
            ENV_MODEL_REFLECTION,
            ENV_MODEL_COMPILER,
            ENV_DIALOGUE_THINKING,
            ENV_JUDGE_MAX_TOKENS,
            ENV_MAX_CONCURRENT_MODEL_CALLS,
            ENV_DB_POOL_MAX_SIZE,
            ENV_MODEL_BACKEND,
            ENV_MODEL_BASE_URL,
            ENV_MODEL_API_KEY,
            ENV_MODEL_TOKEN_LIMIT_FIELD,
            ENV_EMBEDDING_MODEL,
            ENV_EMBEDDING_BASE_URL,
            ENV_EMBEDDING_API_KEY,
        }
        | set(PRICE_ENV_KEYS)
    )
    for key in overridable:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration. Secrets stay off __repr__."""

    database_uri: str = field(repr=False)
    provider_mode: str = "fake"  # "real" | "fake"; fake is the offline default
    model_write: str = ""  # the single write-call model (render+importance+typology)
    model_escalation: str = ""
    model_dialogue: str = ""  # the streaming prose role (the turn's only call)
    model_reconstruction: str = ""  # the batched retelling role (architecture.md §7)
    # Eval-runner-only judge role: loaded both modes, required by neither
    # (eval-harness.md stage 3; the runner validates on judged runs).
    model_judge: str = ""
    # Reflection role, the same judge shape (reflection.md, ruled 2026-08-15):
    # loaded both modes, required by neither; build_reflection_provider raises
    # loudly at the first real reflect call without it.
    model_reflection: str = ""
    # Compiler role, the third judge-shaped var (parameter-compiler.md, the
    # C3 rulings 2026-08-17): loaded both modes, required by neither;
    # build_compiler_provider raises loudly at the first real compile call.
    model_compiler: str = ""
    dialogue_thinking: str = ""  # "" omit param | "disabled" thinking-off arm
    judge_max_tokens: int = JUDGE_MAX_TOKENS_DEFAULT
    # Process-level concurrency cap (C7): max provider calls in flight at once.
    max_concurrent_model_calls: int = MAX_CONCURRENT_MODEL_CALLS_DEFAULT
    # DB pool ceiling (F0): db.build_pool max_size — the cap's "raise both
    # together" sibling.
    db_pool_max_size: int = DB_POOL_MAX_SIZE_DEFAULT
    anthropic_api_key: str = field(default="", repr=False)
    openai_api_key: str = field(default="", repr=False)
    # The model backend (ruled 2026-09-02): "anthropic" | "openai"; the base
    # URL + optional key apply to the openai backend only (loud otherwise).
    model_backend: str = MODEL_BACKEND_DEFAULT
    model_base_url: str = ""
    model_api_key: str = field(default="", repr=False)
    # The openai backend's token-limit field name (ruled 2026-09-03):
    # "max_tokens" | "max_completion_tokens". Field name only; values stay.
    model_token_limit_field: str = MODEL_TOKEN_LIMIT_FIELD_DEFAULT
    # The embedding role's own knobs: the model NAME (the dimension stays the
    # locked EMBEDDING_DIM constant), an optional base URL, an optional key.
    embedding_model: str = EMBEDDING_MODEL_DEFAULT
    embedding_base_url: str = ""
    embedding_api_key: str = field(default="", repr=False)
    defaults: dict[str, float] = field(default_factory=lambda: dict(SERVICE_DEFAULTS))
    # Optional USD-per-Mtok prices (PRICE_ENV_KEYS); empty = cost in tokens only.
    prices: dict[str, float] = field(default_factory=dict)


class ConfigError(RuntimeError):
    """Loud startup configuration failure (never a silent fallback)."""


def _base_url_or_empty(env: dict[str, str], key: str) -> str:
    """A base-URL knob: "" when unset; otherwise it must be an http(s) URL
    (validated in both modes — a typo is loud regardless of mode), returned
    without a trailing slash (the SDKs append their own paths)."""
    raw = env.get(key, "").strip()
    if not raw:
        return ""
    if not (raw.startswith("http://") or raw.startswith("https://")):
        raise ConfigError(f"{key} must be an http(s) URL, got {raw!r}.")
    return raw.rstrip("/")


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Build Settings from .env; validate loudly per the v1 rulings."""
    if env is None:
        env = load_env()

    database_uri = env.get("DATABASE_URI", "")
    if not database_uri:
        raise ConfigError("DATABASE_URI not set in .env.")

    mode = env.get(ENV_PROVIDER_MODE, "fake").lower()
    if mode not in ("real", "fake"):
        raise ConfigError(
            f"{ENV_PROVIDER_MODE} must be 'real' or 'fake', got {mode!r}."
        )

    # The model backend selector (ruled 2026-09-02). The enum and the
    # cross-checks below run in BOTH modes (a typo is loud regardless of mode
    # — the dialogue-thinking precedent); the presence requirements (a base
    # URL under openai, the keys) apply in real mode only, so fake mode stays
    # keyless and offline.
    backend = env.get(ENV_MODEL_BACKEND, "").strip().lower() or MODEL_BACKEND_DEFAULT
    if backend not in MODEL_BACKENDS:
        raise ConfigError(
            f"{ENV_MODEL_BACKEND} must be 'anthropic' or 'openai', got {backend!r}."
        )
    model_base_url = _base_url_or_empty(env, ENV_MODEL_BASE_URL)
    model_api_key = env.get(ENV_MODEL_API_KEY, "")
    if backend == "anthropic":
        for name, value in (
            (ENV_MODEL_BASE_URL, model_base_url),
            (ENV_MODEL_API_KEY, model_api_key),
        ):
            if value:
                raise ConfigError(
                    f"{name} is set but {ENV_MODEL_BACKEND} is 'anthropic'; set the "
                    "backend to 'openai' or unset it."
                )
    token_limit_field = (
        env.get(ENV_MODEL_TOKEN_LIMIT_FIELD, "").strip().lower()
        or MODEL_TOKEN_LIMIT_FIELD_DEFAULT
    )
    if token_limit_field not in MODEL_TOKEN_LIMIT_FIELDS:
        raise ConfigError(
            f"{ENV_MODEL_TOKEN_LIMIT_FIELD} must be 'max_tokens' or "
            f"'max_completion_tokens', got {token_limit_field!r}."
        )
    # Only the un-honorable combo is refused (ruled 2026-09-11): the anthropic
    # wire field is always max_tokens, so an explicit max_tokens is harmless.
    if backend == "anthropic" and token_limit_field != MODEL_TOKEN_LIMIT_FIELD_DEFAULT:
        raise ConfigError(
            f"{ENV_MODEL_TOKEN_LIMIT_FIELD} is an openai wire knob and the "
            "anthropic backend always sends max_tokens; set the backend to "
            "'openai' or unset it."
        )
    # The embedding role's own knobs — independent of the model backend.
    embedding_model = (
        env.get(ENV_EMBEDDING_MODEL, "").strip() or EMBEDDING_MODEL_DEFAULT
    )
    embedding_base_url = _base_url_or_empty(env, ENV_EMBEDDING_BASE_URL)
    embedding_api_key = env.get(ENV_EMBEDDING_API_KEY, "")
    if embedding_api_key and not embedding_base_url:
        raise ConfigError(
            f"{ENV_EMBEDDING_API_KEY} is set without {ENV_EMBEDDING_BASE_URL}; the "
            "hosted OpenAI embedding path uses OPENAI_API_KEY."
        )

    model_write = ""
    model_escalation = ""
    model_dialogue = ""
    model_reconstruction = ""
    anthropic_key = ""
    openai_key = ""
    if mode == "real":
        importance = env.get(ENV_MODEL_IMPORTANCE, "")
        render = env.get(ENV_MODEL_RENDER, "")
        typology = env.get(ENV_MODEL_TYPOLOGY, "")
        escalation = env.get(ENV_MODEL_ESCALATION, "")
        dialogue = env.get(ENV_MODEL_DIALOGUE, "")
        reconstruction = env.get(ENV_MODEL_RECONSTRUCTION, "")
        missing = [
            name
            for name, value in (
                (ENV_MODEL_IMPORTANCE, importance),
                (ENV_MODEL_RENDER, render),
                (ENV_MODEL_TYPOLOGY, typology),
                (ENV_MODEL_ESCALATION, escalation),
                (ENV_MODEL_DIALOGUE, dialogue),
                (ENV_MODEL_RECONSTRUCTION, reconstruction),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                f"real mode requires model role env vars: {', '.join(missing)}."
            )
        # One call serves render+importance+typology in v1: the three role
        # vars must agree (documented limitation; error, never a silent pick).
        if not (importance == render == typology):
            raise ConfigError(
                "v1's single write call requires "
                f"{ENV_MODEL_IMPORTANCE} == {ENV_MODEL_RENDER} == {ENV_MODEL_TYPOLOGY}; "
                "they diverge in .env."
            )
        model_write = importance
        model_escalation = escalation
        model_dialogue = dialogue
        model_reconstruction = reconstruction
        anthropic_key = env.get("ANTHROPIC_API_KEY", "")
        openai_key = env.get("OPENAI_API_KEY", "")
        # Per-backend key/URL requirements (ruled 2026-09-02): the anthropic
        # backend needs its key; the openai backend needs its base URL (the
        # key is optional — the placeholder stands in for local servers) and
        # ignores an ANTHROPIC_API_KEY left in .env. The hosted embedding
        # path needs OPENAI_API_KEY unless an embedding base URL is set.
        if backend == "anthropic" and not anthropic_key:
            raise ConfigError(
                "real mode on the anthropic backend requires ANTHROPIC_API_KEY in .env."
            )
        if backend == "openai" and not model_base_url:
            raise ConfigError(
                f"the openai backend requires {ENV_MODEL_BASE_URL} in .env."
            )
        if not embedding_base_url and not openai_key:
            raise ConfigError(
                "real mode requires OPENAI_API_KEY in .env (or "
                f"{ENV_EMBEDDING_BASE_URL} for a self-hosted embedding server)."
            )

    # Eval-runner-only fields, loaded in BOTH modes (never in the real-mode
    # required list above — that absence is the stage-3 ruling as code).
    model_judge = env.get(ENV_MODEL_JUDGE, "")
    # The reflection role shares the judge shape (the C2 dossier ruling
    # 2026-08-15): loaded here in both modes, never in the required list —
    # the loud failure lives at the first real reflect call instead.
    model_reflection = env.get(ENV_MODEL_REFLECTION, "")
    # The compiler role is the third judge-shaped var (the C3 rulings
    # 2026-08-17): loaded in both modes, never in the required list — the
    # loud failure lives at the worker's first real compile call instead.
    model_compiler = env.get(ENV_MODEL_COMPILER, "")
    dialogue_thinking = env.get(ENV_DIALOGUE_THINKING, "")
    if dialogue_thinking not in ("", "disabled"):
        raise ConfigError(
            f"{ENV_DIALOGUE_THINKING} must be unset or 'disabled', "
            f"got {dialogue_thinking!r}."
        )
    if dialogue_thinking and backend == "openai":
        # The knob is an Anthropic request shape (thinking={"type": ...});
        # the OpenAI-compatible family has no equivalent — loud, never
        # silently dropped (ruled 2026-09-02).
        raise ConfigError(
            f"{ENV_DIALOGUE_THINKING} is an Anthropic request knob; unset it on the "
            "openai backend."
        )
    raw_judge_max = env.get(ENV_JUDGE_MAX_TOKENS, "")
    if raw_judge_max:
        try:
            judge_max_tokens = int(raw_judge_max)
        except ValueError as exc:
            raise ConfigError(
                f"{ENV_JUDGE_MAX_TOKENS} must be an integer, got {raw_judge_max!r}."
            ) from exc
        if judge_max_tokens < 1:
            raise ConfigError(
                f"{ENV_JUDGE_MAX_TOKENS} must be >= 1, got {judge_max_tokens}."
            )
    else:
        judge_max_tokens = JUDGE_MAX_TOKENS_DEFAULT

    raw_max_calls = env.get(ENV_MAX_CONCURRENT_MODEL_CALLS, "")
    if raw_max_calls:
        try:
            max_concurrent_model_calls = int(raw_max_calls)
        except ValueError as exc:
            raise ConfigError(
                f"{ENV_MAX_CONCURRENT_MODEL_CALLS} must be an integer, "
                f"got {raw_max_calls!r}."
            ) from exc
        if max_concurrent_model_calls < 1:
            raise ConfigError(
                f"{ENV_MAX_CONCURRENT_MODEL_CALLS} must be >= 1, "
                f"got {max_concurrent_model_calls}."
            )
    else:
        max_concurrent_model_calls = MAX_CONCURRENT_MODEL_CALLS_DEFAULT

    raw_pool_max = env.get(ENV_DB_POOL_MAX_SIZE, "")
    if raw_pool_max:
        try:
            db_pool_max_size = int(raw_pool_max)
        except ValueError as exc:
            raise ConfigError(
                f"{ENV_DB_POOL_MAX_SIZE} must be an integer, got {raw_pool_max!r}."
            ) from exc
        if db_pool_max_size < 1:
            raise ConfigError(
                f"{ENV_DB_POOL_MAX_SIZE} must be >= 1, got {db_pool_max_size}."
            )
    else:
        db_pool_max_size = DB_POOL_MAX_SIZE_DEFAULT

    prices: dict[str, float] = {}
    for env_key, price_key in PRICE_ENV_KEYS.items():
        raw = env.get(env_key, "")
        if not raw:
            continue
        try:
            prices[price_key] = float(raw)
        except ValueError as exc:
            raise ConfigError(f"{env_key} must be a number, got {raw!r}.") from exc

    return Settings(
        database_uri=database_uri,
        provider_mode=mode,
        model_write=model_write,
        model_escalation=model_escalation,
        model_dialogue=model_dialogue,
        model_reconstruction=model_reconstruction,
        model_judge=model_judge,
        model_reflection=model_reflection,
        model_compiler=model_compiler,
        dialogue_thinking=dialogue_thinking,
        judge_max_tokens=judge_max_tokens,
        max_concurrent_model_calls=max_concurrent_model_calls,
        db_pool_max_size=db_pool_max_size,
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        model_backend=backend,
        model_base_url=model_base_url,
        model_api_key=model_api_key,
        model_token_limit_field=token_limit_field,
        embedding_model=embedding_model,
        embedding_base_url=embedding_base_url,
        embedding_api_key=embedding_api_key,
        prices=prices,
    )


def agent_knob(agent_config: dict, key: str, settings: Settings) -> float:
    """Per-agent override from agents.config, else the service default."""
    value = agent_config.get(key)
    if value is None:
        return settings.defaults[key]
    return float(value)
