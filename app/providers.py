"""providers.py — model provider interfaces: real implementations + deterministic fakes.

Two write-path roles (write-path.md §Model provider interfaces) plus the
escalation call ruled into v1 (2026-07-13), plus the dialogue role (the
CLI-harness build 2026-07-15; the concurrent behavior role it was once split
with was removed by the A1 re-shape, 2026-08-04), plus the reconstruction
role (the reconstruction build, 2026-07-17):
  - the single Haiku write call (render + importance + typology-when-absent),
  - the LLM-escalation gist call (hard cases, biased loose),
  - the embedding call (text-embedding-3-small @ 1536, locked),
  - the streaming dialogue call — PURE PROSE, the dialogue turn's only
    model call,
  - the batched Haiku-class reconstruction call (all cache misses of one
    retrieval in one structured call; reconstruction.md).

Every fake is deterministic: same input -> byte-identical output, offline and
keyless, so the structural suite never asserts on prose and CI needs no keys.
The fake embedding is LOCALITY-SENSITIVE (ruled 2026-07-17): similar texts
get similar vectors, so fake-mode retrieval relevance and reconstruction
drift distances are meaningful, not hash noise.
Failure-injection fakes live here too — the degradation ladder is tested per
model call (architecture §2).

Error contract (the seam owns degradation policy, providers only signal):
  - ProviderCallError    — the call itself failed (network, API error).
  - MalformedOutputError — the call succeeded but structured output did not
    parse; carries token counts because the spend happened.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from app.concurrency import ModelCallGate
from app.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    ENV_MODEL_COMPILER,
    ENV_MODEL_JUDGE,
    ENV_MODEL_REFLECTION,
    MAX_CONCURRENT_MODEL_CALLS_DEFAULT,
    ConfigError,
    Settings,
)


logger = logging.getLogger(__name__)

# The typology vocabulary — one tuple, mirrored three ways: the wire Literal
# (schemas.Typology), the fake provider's hash-pick, and migration 001's
# memories_typology_check. The degradation suite asserts the Python copies
# stay identical; the SQL copy is fixed by the applied-migration immutability
# rule.
TYPOLOGY_VOCABULARY = ("observed", "told", "inferred", "reflected")


def clamp_typology(raw: str) -> str | None:
    """Clamp a model-emitted typology to the vocabulary (ruled 2026-08-12).

    The write prompt lists the options as `observed|told|inferred|reflected`,
    and a real call echoed the option syntax back (`"observed|told"`) —
    un-clamped, that value reaches `memories_typology_check` and the
    CheckViolation kills the whole request (it cost a compare run on
    2026-08-12). In-vocabulary values pass through untouched; otherwise the
    FIRST vocabulary member found in the string wins (the model's leading
    choice); a string containing none returns None, which flows into
    ingest's existing undeclared-typology default path (config
    `typology_default` -> TYPOLOGY_FALLBACK). Never silent: every clamp
    logs the raw value.
    """
    if raw in TYPOLOGY_VOCABULARY:
        return raw
    for token in re.findall(r"[a-z]+", raw.lower()):
        if token in TYPOLOGY_VOCABULARY:
            logger.warning("write-call typology %r clamped to %r", raw, token)
            return token
    logger.warning(
        "write-call typology %r contains no vocabulary member; deferring to "
        "the undeclared-typology default path",
        raw,
    )
    return None


def salvage_confidence(raw: object) -> float | None:
    """Salvage a model-emitted typology confidence (ruled 2026-08-12).

    The sibling seat to `clamp_typology`, one field over: this value used to
    be `float()`-converted OUTSIDE the parse's try/except, so a model
    emitting `"high"` crashed the whole request (an uncaught ValueError ->
    500, nothing written) and a numeric out-of-range value (1.5) aborted the
    insert at `memories_typology_confidence_check`. Salvage semantics:
    everything parseable survives — a non-numeric (or NaN) confidence
    becomes None while the render, importance, and typology all stand
    (ingest knob-defaults the confidence); a numeric out-of-range one
    clamps into [0, 1]. Never silent: every intervention logs the raw
    value. The client-DECLARED path is untouched — an out-of-range
    declaration stays a loud 422 at the wire model.
    """
    try:
        value = float(raw)  # type: ignore[arg-type] — the point is the failure
    except (TypeError, ValueError):
        logger.warning(
            "write-call typology_confidence %r is non-numeric; dropping to "
            "None (the confidence-default knob path)",
            raw,
        )
        return None
    if math.isnan(value):
        logger.warning("write-call typology_confidence is NaN; dropping to None")
        return None
    if value < 0.0 or value > 1.0:
        clamped = min(max(value, 0.0), 1.0)
        logger.warning(
            "write-call typology_confidence %r out of [0, 1]; clamped to %s",
            raw,
            clamped,
        )
        return clamped
    return value


class ProviderCallError(RuntimeError):
    """The model call failed outright."""


class MalformedOutputError(RuntimeError):
    """The call returned, but its structured output did not parse."""

    def __init__(self, message: str, input_tokens: int = 0, output_tokens: int = 0):
        super().__init__(message)
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriteCallResult:
    """Structured output of the single Haiku write call."""

    rendered_content: str
    importance_raw: float
    typology: str | None  # None when the client declared (call not asked)
    typology_confidence: float | None
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class GistSpanCandidate:
    """A half-open [start_char, end_char) span into observation_text."""

    start_char: int
    end_char: int
    matched_component_id: str | None = None  # UUID str of an existing component
    matched_category: str | None = None


@dataclass(frozen=True)
class NewComponent:
    """A novel entity to grow identity_components with."""

    canonical: str
    aliases: list[str] = field(default_factory=list)
    category: str | None = None


@dataclass(frozen=True)
class EscalationResult:
    """Structured output of the escalation gist call."""

    spans: list[GistSpanCandidate]
    new_components: list[NewComponent]
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class EmbedResult:
    vectors: list[list[float]]
    tokens: int


@dataclass(frozen=True)
class ProseResult:
    """The streaming prose call's terminal accounting (split-brain-streaming.md,
    2026-07-21; since the A1 re-shape 2026-08-04 the prose call is the turn's
    ONLY model call). The prose call streams PURE PROSE — the chunks ARE the
    player-facing text, yielded as they arrive; this is returned from the
    stream generator (via StopIteration.value) once the stream closes, so the
    seam has token counts and the measured first-token latency."""

    input_tokens: int
    output_tokens: int
    first_token_ms: float  # 0.0 on the fake; measured on the streaming real call


@dataclass(frozen=True)
class ReconstructionItem:
    """One cache-missed memory prepared for the batched retelling call
    (reconstruction.md call contract): the fixed gist, the band-thinned
    original detail, and the current live telling. memory_id is the UUID
    string — the JSON key of the batched output contract."""

    memory_id: str
    gist: str
    thinned_detail: str
    current_telling: str


@dataclass(frozen=True)
class ReconstructionCallResult:
    """Parsed batched output: memory_id -> retelling. Per-item salvage
    (reconstruction.md ladder): an entry that is missing, empty, or not a
    string simply has no key here, and that item alone degrades at the seam;
    the call still counts as succeeded and its spend is accounted."""

    retellings: dict[str, str]
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class JudgeCallResult:
    """One judge verdict call's parsed output (eval-harness.md stage 3).
    `payload` is the raw JSON object — semantic validation (the pydantic
    verdict models) is the eval runner's job, so a shape mismatch degrades
    per-item (judge_failed) rather than failing the call layer."""

    payload: dict
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ReflectionItem:
    """One sampled episode prepared for the reflect call (reflection.md):
    the live telling head plus the sampling metadata the prompt carries.
    memory_id is the UUID string — the citation unit of the output
    contract (the ReconstructionItem precedent: structured inputs ride
    beside the assembled prompt so the deterministic fake can derive
    stable, correctly-cited output)."""

    memory_id: str
    telling: str
    importance: float | None
    valid_at: str  # ISO 8601 text — prompt payload, never parsed here


@dataclass(frozen=True)
class ReflectionConclusion:
    """One parsed conclusion of the reflect call. `source_memory_ids` are
    raw strings — grounding (non-empty AND a subset of the sampled ids) is
    the seam's mechanical validation, not the call layer's."""

    content: str
    identity_relevant: bool
    source_memory_ids: list[str]


@dataclass(frozen=True)
class ReflectionCallResult:
    """Parsed output of the reflect call (reflection.md output contract:
    a JSON object {"reflections": [...]}). An empty conclusion list is a
    VALID outcome — thin evidence concludes nothing."""

    conclusions: list[ReflectionConclusion]
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ConsolidationCallResult:
    """Parsed output of the consolidation call: ONE belief's content. The
    source union and the bi-temporal absorption are computed at the seam —
    the model never proposes provenance."""

    content: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class CompilerItem:
    """One (belief, scene-type) pair prepared for the compile call
    (parameter-compiler.md): the compilable surface plus the target scene
    type. reflection_id is the UUID string — structural input so the
    deterministic fake derives stable per-pair output (the ReflectionItem
    precedent); the real provider ignores it."""

    reflection_id: str
    content: str
    identity_relevant: bool
    scene_type: str


@dataclass(frozen=True)
class CompilerCallResult:
    """Parsed output of the compile call (the C3 output contract: a JSON
    object {"multipliers": {"relevance", "recency", "importance"},
    "passthrough": {...}}). Values arrive RAW — the clamp to the module
    constants and the passthrough namespace filter are the seam's
    mechanical validation, not the call layer's (the grounding-validation
    split)."""

    w_relevance: float
    w_recency: float
    w_importance: float
    passthrough: dict
    input_tokens: int
    output_tokens: int


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class WriteProvider(Protocol):
    def render_and_score(
        self,
        *,
        observation_text: str,
        diagnosticity_goal: str,
        declared_typology: str | None,
    ) -> WriteCallResult: ...


class EscalationProvider(Protocol):
    def extract_gist(
        self,
        *,
        observation_text: str,
        known_components: list[dict],
        candidate_spans: list[GistSpanCandidate],
        candidate_components: list[NewComponent],
        triggers: list[str],
    ) -> EscalationResult: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> EmbedResult: ...


class DialogueProvider(Protocol):
    """The streaming prose call — the dialogue turn's only model call since
    the A1 re-shape (2026-08-04). `system_prompt` is fully assembled at the
    seam (app\\dialogue.py owns the block shape). Returns a SYNC generator
    that yields prose chunks as they arrive and returns a ProseResult (token
    counts + first-token latency) via StopIteration.value once the stream
    closes; the seam runs it in a worker thread and bridges the chunks onto
    its async output."""

    def stream_prose(self, *, system_prompt: str, utterance: str) -> Iterator[str]: ...


class ReconstructionProvider(Protocol):
    """`system_prompt` and `user_content` are fully assembled at the seam
    (app\\reconstruction.py's pure assembly owns the block shape, the dialogue
    precedent); `items` rides separately so the deterministic fake can derive
    stable retellings from the structured inputs."""

    def reconstruct(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReconstructionItem],
    ) -> ReconstructionCallResult: ...


class JudgeProvider(Protocol):
    """The eval-runner-only judge call (eval-harness.md stage 3). Prompts are
    fully assembled by the runner from app\\eval_judge.py's rubric constants;
    `category` and `n_facts` ride structurally so the deterministic fake can
    emit shape-conformant verdicts (the ReconstructionProvider `items`
    precedent) — the real provider ignores both."""

    def judge(
        self,
        *,
        system_prompt: str,
        user_content: str,
        category: str,
        n_facts: int = 0,
    ) -> JudgeCallResult: ...


class ReflectionProvider(Protocol):
    """The reflect + consolidation calls (reflection.md; C2 build 2026-08-15).
    Judge-shaped by ruling: never a field on the Providers bundle — the
    reflect seam builds one lazily via build_reflection_provider at first
    use. Prompts are fully assembled at the seam (app\\reflection.py owns
    the block shape); `items` rides structurally so the deterministic fake
    can cite real sampled ids (the ReconstructionProvider precedent) — the
    real provider ignores it."""

    def reflect(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReflectionItem],
    ) -> ReflectionCallResult: ...

    def consolidate(
        self,
        *,
        system_prompt: str,
        user_content: str,
    ) -> ConsolidationCallResult: ...


class CompilerProvider(Protocol):
    """The parameter-compile call (parameter-compiler.md; the C3 rulings
    2026-08-17). Judge-shaped by ruling: never a field on the Providers
    bundle — the compiler seam builds one lazily via build_compiler_provider
    at first use. Prompts are fully assembled at the seam (app\\compiler.py
    owns the block shape); `item` rides structurally so the deterministic
    fake can derive stable per-(belief, scene-type) output — the real
    provider ignores it."""

    def compile(
        self,
        *,
        system_prompt: str,
        user_content: str,
        item: CompilerItem,
    ) -> CompilerCallResult: ...


# ---------------------------------------------------------------------------
# Deterministic fakes
# ---------------------------------------------------------------------------


def _stable_unit_float(text: str, salt: str) -> float:
    """Deterministic float in [0, 1) from text — stable across runs/platforms."""
    digest = hashlib.sha256(f"{salt}:{text}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class FakeWriteProvider:
    """Echo render + hash-derived scores. Deterministic, keyless."""

    TYPOLOGIES = TYPOLOGY_VOCABULARY

    def render_and_score(
        self,
        *,
        observation_text: str,
        diagnosticity_goal: str,
        declared_typology: str | None,
    ) -> WriteCallResult:
        importance = round(_stable_unit_float(observation_text, "importance"), 4)
        typology: str | None = None
        confidence: float | None = None
        if declared_typology is None:
            index = int(_stable_unit_float(observation_text, "typology") * 4)
            typology = self.TYPOLOGIES[index]
            confidence = round(
                0.5 + _stable_unit_float(observation_text, "conf") / 2, 4
            )
        words = len(observation_text.split())
        return WriteCallResult(
            rendered_content=f"[fake render] {observation_text}",
            importance_raw=importance,
            typology=typology,
            typology_confidence=confidence,
            input_tokens=words,
            output_tokens=words,
        )


class FakeEscalationProvider:
    """Echoes the NLP pass's candidates unchanged — deterministic by construction."""

    def extract_gist(
        self,
        *,
        observation_text: str,
        known_components: list[dict],
        candidate_spans: list[GistSpanCandidate],
        candidate_components: list[NewComponent],
        triggers: list[str],
    ) -> EscalationResult:
        words = len(observation_text.split())
        return EscalationResult(
            spans=list(candidate_spans),
            new_components=list(candidate_components),
            input_tokens=words,
            output_tokens=len(candidate_spans) + len(candidate_components),
        )


class FakeEmbeddingProvider:
    """Locality-sensitive deterministic pseudo-embedding (ruled 2026-07-17,
    superseding the original shake_256 hash vectors): lowercased character
    trigrams hashed into the 1536 buckets, counted, L2-normalized. Similar
    texts get similar vectors, so fake-mode retrieval relevance and the
    reconstruction drift check are meaningful — the hash fake made any two
    texts nearly orthogonal, which would have refused every fake-mode
    write-back at any sane drift threshold."""

    def embed(self, texts: list[str]) -> EmbedResult:
        vectors: list[list[float]] = []
        tokens = 0
        for text in texts:
            counts = [0.0] * EMBEDDING_DIM
            lowered = text.lower()
            grams = (
                [lowered[i : i + 3] for i in range(len(lowered) - 2)]
                if len(lowered) >= 3
                else [lowered]
            )
            for gram in grams:
                digest = hashlib.sha256(gram.encode()).digest()
                counts[int.from_bytes(digest[:4], "big") % EMBEDDING_DIM] += 1.0
            norm = math.sqrt(sum(c * c for c in counts)) or 1.0
            vectors.append([c / norm for c in counts])
            tokens += len(text.split())
        return EmbedResult(vectors=vectors, tokens=tokens)


class FakeProseProvider:
    """Deterministic streaming prose: the stable echo split into word chunks,
    yielded one at a time (so the seam's chunk bridge and first_word_ms are
    exercised offline), returning a ProseResult with byte-stable token counts —
    identical turns reproduce it exactly (split-brain done-when)."""

    def stream_prose(self, *, system_prompt: str, utterance: str) -> Iterator[str]:
        prose = f"[fake dialogue] {utterance}"
        words = prose.split()
        for i, word in enumerate(words):
            # Re-emit with the original spacing so "".join(chunks) == prose.
            yield word if i == 0 else " " + word
        return ProseResult(
            input_tokens=len(system_prompt.split()) + len(utterance.split()),
            output_tokens=len(words),
            first_token_ms=0.0,
        )


class FakeReconstructionProvider:
    """Deterministic retelling: the current telling plus a short marker hashed
    from every input (identity document via the system prompt, gist, thinned
    detail, telling) — so an identity bump or a band crossing changes the
    output, byte-identical inputs reproduce it, and the echo shape keeps the
    candidate NEAR the anchor under the trigram fake embedding (the happy
    path passes the default drift budget; compounding markers slowly spend
    it, which is the drift dynamic in miniature)."""

    def reconstruct(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReconstructionItem],
    ) -> ReconstructionCallResult:
        retellings: dict[str, str] = {}
        input_tokens = len(system_prompt.split()) + len(user_content.split())
        output_tokens = 0
        for item in items:
            marker = hashlib.sha256(
                f"{system_prompt}|{item.gist}|{item.thinned_detail}"
                f"|{item.current_telling}".encode()
            ).hexdigest()[:8]
            text = f"{item.current_telling} [retold {marker}]"
            retellings[item.memory_id] = text
            output_tokens += len(text.split())
        return ReconstructionCallResult(
            retellings=retellings,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class FakeJudgeProvider:
    """Deterministic hash verdicts per category (eval-harness.md stage 3,
    plumbing only): same inputs -> byte-identical payloads that validate under
    app\\eval_judge.py's verdict models, so the runner's judged mechanics are
    testable offline and keyless. Judged SIGNAL exists only in real mode —
    plumbing runs are labeled plumbing_only by the runner."""

    def judge(
        self,
        *,
        system_prompt: str,
        user_content: str,
        category: str,
        n_facts: int = 0,
    ) -> JudgeCallResult:
        marker = hashlib.sha256(
            f"judge:{category}:{user_content}".encode()
        ).hexdigest()[:8]
        rationale = f"[fake judge] {marker}"
        if category in ("selective_forgetting", "abstention"):
            verdict = (
                "pass"
                if _stable_unit_float(user_content, f"judge:{category}") < 0.5
                else "fail"
            )
            payload: dict = {"verdict": verdict, "rationale": rationale}
        elif category == "reconstruction_faithfulness":
            payload = {
                # Biased ~0.8 supported: fake retellings hug their anchors, so
                # a mostly-supported verdict is the realistic plumbing shape.
                "gist_supported": [
                    _stable_unit_float(user_content, f"judge:rf:{i}") < 0.8
                    for i in range(n_facts)
                ],
                "fabricated_claims": [],
                "rationale": rationale,
            }
        elif category == "prose_pairwise":

            def scores(arm: str) -> dict:
                return {
                    dim: int(
                        _stable_unit_float(user_content, f"judge:pp:{arm}:{dim}") * 5
                    )
                    + 1
                    for dim in (
                        "naturalness",
                        "character_consistency",
                        "memory_grounding",
                        "brevity",
                    )
                }

            pref_roll = _stable_unit_float(user_content, "judge:pp:pref")
            preference = "a" if pref_roll < 0.4 else "b" if pref_roll < 0.8 else "tie"
            payload = {
                "a": scores("a"),
                "b": scores("b"),
                "preference": preference,
                "rationale": rationale,
            }
        else:
            raise ValueError(f"unknown judge category: {category!r}")
        return JudgeCallResult(
            payload=payload,
            input_tokens=len(system_prompt.split()) + len(user_content.split()),
            output_tokens=len(rationale.split()) + max(n_facts, 1),
        )


class FakeReflectionProvider:
    """Deterministic conclusions grounded in the ACTUAL sampled ids: one
    identity-relevant conclusion citing the first ids (up to three) and one
    non-identity-relevant conclusion citing the last id, both with content
    derived from the cited tellings (so distinct samples yield distinct
    contents — the RRR guard sees honest variation). Byte-identical on
    identical inputs, offline, keyless."""

    def reflect(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReflectionItem],
    ) -> ReflectionCallResult:
        input_tokens = len(system_prompt.split()) + len(user_content.split())
        conclusions: list[ReflectionConclusion] = []
        if items:
            marker = hashlib.sha256(f"reflect:{user_content}".encode()).hexdigest()[:8]
            head = items[0]
            conclusions.append(
                ReflectionConclusion(
                    content=f"{head.telling} [reflected {marker}]",
                    identity_relevant=True,
                    source_memory_ids=[item.memory_id for item in items[:3]],
                )
            )
            tail = items[-1]
            conclusions.append(
                ReflectionConclusion(
                    content=f"{tail.telling} [noted {marker}]",
                    identity_relevant=False,
                    source_memory_ids=[tail.memory_id],
                )
            )
        output_tokens = sum(len(c.content.split()) for c in conclusions)
        return ReflectionCallResult(
            conclusions=conclusions,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def consolidate(
        self,
        *,
        system_prompt: str,
        user_content: str,
    ) -> ConsolidationCallResult:
        marker = hashlib.sha256(f"consolidate:{user_content}".encode()).hexdigest()[:8]
        content = f"Taken together these amount to one belief. [consolidated {marker}]"
        return ConsolidationCallResult(
            content=content,
            input_tokens=len(system_prompt.split()) + len(user_content.split()),
            output_tokens=len(content.split()),
        )


class FakeCompilerProvider:
    """Deterministic multipliers derived from the pair itself: per axis,
    0.5 + 3.0 * hash-unit of the belief content salted by axis + scene type
    — inside the [0.25, 4.0] write clamp, almost never exactly 1.0, and
    DISTINCT per scene type (so per-type selection is assertable). One
    namespaced passthrough key exercises the store path. Byte-identical on
    identical inputs, offline, keyless. Scenarios that need exact
    multipliers (re-rank flips) pin a local provider instead — hash-derived
    values cannot guarantee a flip on an arbitrary fixture."""

    def compile(
        self,
        *,
        system_prompt: str,
        user_content: str,
        item: CompilerItem,
    ) -> CompilerCallResult:
        def axis(name: str) -> float:
            unit = _stable_unit_float(
                item.content, f"compiler:{name}:{item.scene_type}"
            )
            return round(0.5 + 3.0 * unit, 4)

        marker = hashlib.sha256(
            f"compile:{item.content}:{item.scene_type}".encode()
        ).hexdigest()[:8]
        return CompilerCallResult(
            w_relevance=axis("relevance"),
            w_recency=axis("recency"),
            w_importance=axis("importance"),
            passthrough={"fake.note": marker},
            input_tokens=len(system_prompt.split()) + len(user_content.split()),
            output_tokens=9,
        )


# --- failure-injection fakes (degradation ladder tests) --------------------


class FailingWriteProvider:
    """Importance-scoring failure: the write must still land (scoring_failed)."""

    def render_and_score(self, **_kwargs) -> WriteCallResult:
        raise ProviderCallError("injected write-call failure")


class MalformedWriteProvider:
    """Call 'succeeds' but structured output is unparseable: neutral/default."""

    def render_and_score(self, **_kwargs) -> WriteCallResult:
        raise MalformedOutputError(
            "injected malformed output", input_tokens=7, output_tokens=3
        )


class FlakyWriteProvider:
    """Fails the first `fail_times` write calls, then delegates to
    FakeWriteProvider — the deferred worker's retry ladder (deferred-writes.md):
    a failed attempt leaves the row pending with the attempt recorded; a later
    drain completes it."""

    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self._fail_times = fail_times
        self._delegate = FakeWriteProvider()

    def render_and_score(self, **kwargs) -> WriteCallResult:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ProviderCallError(f"injected flaky write failure (call {self.calls})")
        return self._delegate.render_and_score(**kwargs)


class FailingEmbeddingProvider:
    """Embedding failure: write lands with NULL embedding (ruled 2026-07-13)."""

    def embed(self, texts: list[str]) -> EmbedResult:
        raise ProviderCallError("injected embedding failure")


class FailingEscalationProvider:
    """Escalation failure: retry once, then the write soft-degrades to the base
    NLP-pass gist with escalation_failed = true (ruled 2026-07-22)."""

    def __init__(self) -> None:
        self.calls = 0

    def extract_gist(self, **_kwargs) -> EscalationResult:
        self.calls += 1
        raise ProviderCallError(f"injected escalation failure (call {self.calls})")


class NoveltyEscalationProvider:
    """Echoes the candidates plus one fixed novel component whose mention (when
    present in the observation text) gains a span via the plan_spans term
    match — the deferred worker's entity-merge / add-only-append path needs a
    fake whose merge is NOT a no-op (the plain echo fake changes nothing).
    Deterministic: same fixture text -> byte-identical merge."""

    NOVEL = NewComponent(canonical="ledger stone", category="object")

    def extract_gist(
        self,
        *,
        observation_text: str,
        known_components: list[dict],
        candidate_spans: list[GistSpanCandidate],
        candidate_components: list[NewComponent],
        triggers: list[str],
    ) -> EscalationResult:
        words = len(observation_text.split())
        components = [*candidate_components, self.NOVEL]
        return EscalationResult(
            spans=list(candidate_spans),
            new_components=components,
            input_tokens=words,
            output_tokens=len(candidate_spans) + len(components),
        )


class FailingProseProvider:
    """Prose failure BEFORE the first chunk: never-blank — the turn serves the
    fallback line (degradation ladder)."""

    def stream_prose(self, *, system_prompt: str, utterance: str) -> Iterator[str]:
        raise ProviderCallError("injected prose-call failure")
        yield  # pragma: no cover — makes this a generator function


class MidStreamDropProseProvider:
    """Prose drops AFTER some chunks (degradation ladder, ruled 2026-07-21:
    keep the partial + degraded flag). Yields two deterministic chunks,
    then raises — the seam keeps the partial prose and flags the turn."""

    def stream_prose(self, *, system_prompt: str, utterance: str) -> Iterator[str]:
        yield "partial"
        yield " prose"
        raise ProviderCallError("injected mid-stream prose drop")


class FailingReconstructionProvider:
    """Reconstruction-call failure: fail-quiet — the affected items serve
    their live heads with honest read_mode; nothing is written."""

    def reconstruct(self, **_kwargs) -> ReconstructionCallResult:
        raise ProviderCallError("injected reconstruction-call failure")


class MalformedReconstructionProvider:
    """Call 'succeeds' but the batched output is unparseable: every item
    degrades, token spend accounted."""

    def reconstruct(self, **_kwargs) -> ReconstructionCallResult:
        raise MalformedOutputError(
            "injected malformed reconstruction output", input_tokens=7, output_tokens=3
        )


class DriftingReconstructionProvider:
    """Emits a retelling with no trigram overlap with any English fixture —
    cosine distance from the anchor ~1.0 under the fake embedding, so the
    drift budget must refuse the write-back at the default threshold."""

    def reconstruct(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReconstructionItem],
    ) -> ReconstructionCallResult:
        text = "xyzzq plughz " * 12
        return ReconstructionCallResult(
            retellings={item.memory_id: text.strip() for item in items},
            input_tokens=len(system_prompt.split()) + len(user_content.split()),
            output_tokens=len(text.split()) * len(items),
        )


class FailingJudgeProvider:
    """Judge-call failure: the affected item records judge_failed and the
    judged run continues (per-item degradation, eval-harness.md stage 3)."""

    def judge(self, **_kwargs) -> JudgeCallResult:
        raise ProviderCallError("injected judge-call failure")


class MalformedJudgeProvider:
    """Call 'succeeds' but the verdict JSON is unparseable: the item degrades,
    token spend accounted (the MalformedWriteProvider convention)."""

    def judge(self, **_kwargs) -> JudgeCallResult:
        raise MalformedOutputError(
            "injected malformed judge output", input_tokens=7, output_tokens=3
        )


class FailingReflectionProvider:
    """Both reflection-call legs fail outright: the reflect verb is
    fail-loud (502, nothing written); a worker attempt lands a `failed`
    run row and retries naturally next sweep."""

    def reflect(self, **_kwargs) -> ReflectionCallResult:
        raise ProviderCallError("injected reflect-call failure")

    def consolidate(self, **_kwargs) -> ConsolidationCallResult:
        raise ProviderCallError("injected consolidation-call failure")


class MalformedReflectionProvider:
    """Calls 'succeed' but the JSON is unparseable: the malformed-class
    failure of the reflect ladder, token spend accounted (the
    MalformedWriteProvider convention)."""

    def reflect(self, **_kwargs) -> ReflectionCallResult:
        raise MalformedOutputError(
            "injected malformed reflect output", input_tokens=7, output_tokens=3
        )

    def consolidate(self, **_kwargs) -> ConsolidationCallResult:
        raise MalformedOutputError(
            "injected malformed consolidation output",
            input_tokens=7,
            output_tokens=3,
        )


class FailingCompilerProvider:
    """The compile call fails outright: the pair records as failed, the
    sweep continues its other pairs, and the missing pair persists — the
    next sweep retries naturally (no attempts ledger by design)."""

    def compile(self, **_kwargs) -> CompilerCallResult:
        raise ProviderCallError("injected compile-call failure")


class MalformedCompilerProvider:
    """Calls 'succeed' but the JSON is unparseable: the malformed-class
    failure of the compile ladder, token spend accounted (the
    MalformedWriteProvider convention)."""

    def compile(self, **_kwargs) -> CompilerCallResult:
        raise MalformedOutputError(
            "injected malformed compile output", input_tokens=7, output_tokens=3
        )


# ---------------------------------------------------------------------------
# Real implementations (constructed only in real mode; SDKs imported lazily)
# ---------------------------------------------------------------------------


def _first_text_block(response) -> str:
    """The first text block's text, or "" (=> JSONDecodeError at the parse
    site). Thinking-capable models (sonnet-5+) put a thinking block at
    content[0], so indexing content[0].text crashes on them (found in the
    2026-07-21 real-mode smoke; parse-side hardening ruled by Jack)."""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _lenient_json_text(text: str) -> str:
    """The JSON-in-text contract read tolerantly: models sometimes wrap the
    object in markdown code fences despite "No other text" (haiku-4.5 did so
    3/3 on the escalation prompt in the 2026-07-21 diagnostic)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        stripped = stripped.rstrip()
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


# The rendered_content voice clause (F0, 2026-08-26) encodes the three
# measured register rules from identity-authoring.md §5: the render model's
# witness-voice default ("I watched Branwen turn away..." for the NPC's OWN
# action), invented casual names (the fabrication metric counts them), and
# report-register drift. Key list and JSON contract unchanged.
_WRITE_SYSTEM = (
    "You are the write-time memory scorer for a game NPC. Given an observation, "
    "return ONLY a JSON object with keys: rendered_content (a first-person prose "
    "telling of the observation in the NPC's own plain spoken register: actions "
    "the NPC performed are owned in first person, never narrated as if watched; "
    "events the NPC witnessed stay witnessed; use only people and things the "
    "observation itself establishes, never inventing names), importance_raw "
    "(float 0..1, anchored to the NPC's diagnosticity goal){typology_clause}. "
    "No other text."
)
_TYPOLOGY_CLAUSE = (
    ", typology (one of observed|told|inferred|reflected), "
    "typology_confidence (float 0..1)"
)

_ESCALATION_SYSTEM = (
    "You are the gist-extraction escalation pass for a game NPC's memory. Gist "
    "spans are EXACT substrings of the observation tied to the NPC's identity "
    "components. Return ONLY a JSON object with keys: spans (list of objects "
    "{text: exact substring, component: canonical name of a known component or "
    "null, category: category label or null}) and new_components (list of "
    "objects {canonical, aliases, category} for entities central to the "
    "observation but absent from the known components). No other text."
)


class RealWriteProvider:
    """Anthropic Haiku-class call: render + importance (+ typology when absent)."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_write

    def render_and_score(
        self,
        *,
        observation_text: str,
        diagnosticity_goal: str,
        declared_typology: str | None,
    ) -> WriteCallResult:
        clause = _TYPOLOGY_CLAUSE if declared_typology is None else ""
        system = _WRITE_SYSTEM.format(typology_clause=clause)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Diagnosticity goal: {diagnosticity_goal}\n\n"
                            f"Observation: {observation_text}"
                        ),
                    }
                ],
            )
        except Exception as exc:
            raise ProviderCallError(f"write call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            rendered = str(payload["rendered_content"])
            importance = float(payload["importance_raw"])
            typology = payload.get("typology") if declared_typology is None else None
            confidence = (
                payload.get("typology_confidence")
                if declared_typology is None
                else None
            )
        except (
            KeyError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            IndexError,
        ) as exc:
            raise MalformedOutputError(
                f"write call output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        # Clamp the model-emitted label to vocabulary (ruled 2026-08-12); a
        # clamp-to-None also drops the confidence — a label the vocabulary
        # rejected has no meaningful confidence, and ingest's default branch
        # knob-defaults both together.
        clamped = clamp_typology(str(typology)) if typology is not None else None
        return WriteCallResult(
            rendered_content=rendered,
            importance_raw=importance,
            typology=clamped,
            typology_confidence=(
                salvage_confidence(confidence)
                if confidence is not None and clamped is not None
                else None
            ),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class RealEscalationProvider:
    """Anthropic Haiku-class gist escalation. Spans returned as exact substrings,
    mapped to half-open char offsets here; unlocatable substrings are dropped."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_escalation

    def extract_gist(
        self,
        *,
        observation_text: str,
        known_components: list[dict],
        candidate_spans: list[GistSpanCandidate],
        candidate_components: list[NewComponent],
        triggers: list[str],
    ) -> EscalationResult:
        known = [
            {
                "canonical": c["canonical"],
                "aliases": c.get("aliases") or [],
                "category": c.get("category"),
            }
            for c in known_components
        ]
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_ESCALATION_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Known identity components: {json.dumps(known)}\n"
                            f"Escalation triggers: {triggers}\n\n"
                            f"Observation: {observation_text}"
                        ),
                    }
                ],
            )
        except Exception as exc:
            raise ProviderCallError(f"escalation call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            by_canonical = {c["canonical"]: c for c in known_components}
            spans: list[GistSpanCandidate] = []
            for item in payload["spans"]:
                text = str(item["text"])
                start = observation_text.find(text)
                if start < 0:
                    continue  # unlocatable substring: drop, offsets stay truthful
                component = by_canonical.get(item.get("component"))
                spans.append(
                    GistSpanCandidate(
                        start_char=start,
                        end_char=start + len(text),
                        matched_component_id=(
                            str(component["component_id"]) if component else None
                        ),
                        matched_category=item.get("category"),
                    )
                )
            new_components = [
                NewComponent(
                    canonical=str(item["canonical"]),
                    aliases=[str(a) for a in item.get("aliases") or []],
                    category=item.get("category"),
                )
                for item in payload["new_components"]
            ]
        except (
            KeyError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
            IndexError,
        ) as exc:
            raise MalformedOutputError(
                f"escalation output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        return EscalationResult(
            spans=spans,
            new_components=new_components,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def _dialogue_thinking_kwargs(value: str) -> dict:
    """The LONGMEM_DIALOGUE_THINKING knob's request shape (B2 ruling
    2026-08-07): "" -> {} — the pre-B2 request byte-for-byte; "disabled" ->
    the thinking-off arm (sonnet-5 accepts {"type": "disabled"}). Values are
    validated at load_settings; nothing else can reach here."""
    if value == "disabled":
        return {"thinking": {"type": "disabled"}}
    return {}


class RealDialogueProvider:
    """Anthropic streaming PROSE call (built 2026-07-21; the dialogue turn's
    only model call since the A1 re-shape, 2026-08-04). Streams PURE PROSE —
    no JSON envelope. first-token latency is measured; usage comes from the
    final message.

    `stream_prose` is a sync generator: it yields prose chunks as they arrive
    and returns a ProseResult (token counts + first-token latency) via
    StopIteration.value once the stream closes. The seam runs it in a worker
    thread and bridges the chunks onto its async output. A raise before the
    first yield is a pre-first-chunk failure (fallback line); a raise after some
    chunks is a mid-stream drop (keep-partial + flag) — the seam decides by
    what it received.
    """

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_dialogue
        self._thinking_kwargs = _dialogue_thinking_kwargs(settings.dialogue_thinking)

    def stream_prose(self, *, system_prompt: str, utterance: str) -> Iterator[str]:
        t0 = time.perf_counter()
        first_token_ms = 0.0
        seen_first = False
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": utterance}],
                **self._thinking_kwargs,
            ) as stream:
                for text in stream.text_stream:
                    if not seen_first:
                        first_token_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                        seen_first = True
                    yield text
                final = stream.get_final_message()
        except Exception as exc:
            raise ProviderCallError(f"prose call failed: {exc}") from exc
        return ProseResult(
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            first_token_ms=first_token_ms,
        )


class RealReconstructionProvider:
    """Anthropic Haiku-class batched retelling call (reconstruction.md).

    Output contract (build ruling 2026-07-17, JSON-in-text per the
    write/escalation/dialogue precedent): ONLY a JSON object mapping each
    memory_id to its retelling string. The instructions live in the
    seam-assembled system prompt; this class enforces the parse side with
    per-item salvage (a non-string entry drops; the object-level shape must
    parse). max_tokens scales with the batch (1024 per item, capped at 8192 —
    a fixed 1024 would truncate large batches)."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_reconstruction

    def reconstruct(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReconstructionItem],
    ) -> ReconstructionCallResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=min(1024 * max(len(items), 1), 8192),
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            raise ProviderCallError(f"reconstruction call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            if not isinstance(payload, dict):
                raise ValueError("batched output is not a JSON object")
        except (ValueError, TypeError, json.JSONDecodeError, IndexError) as exc:
            raise MalformedOutputError(
                f"reconstruction output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        retellings = {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, str) and value
        }
        return ReconstructionCallResult(
            retellings=retellings,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class RealJudgeProvider:
    """Anthropic judge call (eval-harness.md stage 3; B2 build 2026-08-07).
    Eval-runner-only — never constructed by the service; build_judge_provider
    is the sole entry. Opus-4.8-class by ruling (dialogue ships haiku, and the
    first real compare's arms are haiku vs sonnet-5 — no same-model
    self-grading). Adaptive thinking ON and NO sampling params: the 4.7+ API
    rejects temperature/top_p/top_k outright, so the spec's original
    "temperature 0" is unimplementable (dated correction in eval-harness.md);
    the rubric's JSON-only contract carries determinism instead. max_tokens is
    the LONGMEM_JUDGE_MAX_TOKENS knob — adaptive thinking spends against it."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_judge
        self._max_tokens = settings.judge_max_tokens

    def judge(
        self,
        *,
        system_prompt: str,
        user_content: str,
        category: str,
        n_facts: int = 0,
    ) -> JudgeCallResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                thinking={"type": "adaptive"},
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            raise ProviderCallError(f"judge call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            if not isinstance(payload, dict):
                raise ValueError("judge output is not a JSON object")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MalformedOutputError(
                f"judge output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        return JudgeCallResult(
            payload=payload,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class RealReflectionProvider:
    """Anthropic reflect + consolidation calls (reflection.md; C2 build
    2026-08-15). Constructed only by build_reflection_provider — the judge
    precedent: the server's Providers bundle never carries this role and
    the seam builds it lazily at first use. Prompts arrive fully assembled
    (app\\reflection.py owns the block shape); `items` is the fake's
    structural input and is ignored here. Fixed max_tokens bounds follow
    the write-call precedent (a structural bound, not integrator policy)."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_reflection

    def reflect(
        self,
        *,
        system_prompt: str,
        user_content: str,
        items: list[ReflectionItem],
    ) -> ReflectionCallResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            raise ProviderCallError(f"reflect call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            raw_conclusions = payload["reflections"]
            if not isinstance(raw_conclusions, list):
                raise ValueError("'reflections' is not a list")
            conclusions = []
            for entry in raw_conclusions:
                sources = entry["source_memory_ids"]
                if not isinstance(sources, list):
                    raise ValueError("'source_memory_ids' is not a list")
                conclusions.append(
                    ReflectionConclusion(
                        content=str(entry["content"]),
                        identity_relevant=bool(entry["identity_relevant"]),
                        source_memory_ids=[str(value) for value in sources],
                    )
                )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MalformedOutputError(
                f"reflect output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        return ReflectionCallResult(
            conclusions=conclusions,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def consolidate(
        self,
        *,
        system_prompt: str,
        user_content: str,
    ) -> ConsolidationCallResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            raise ProviderCallError(f"consolidation call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            content = payload["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("'content' is not a non-empty string")
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MalformedOutputError(
                f"consolidation output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        return ConsolidationCallResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class RealCompilerProvider:
    """The Anthropic compile call (parameter-compiler.md; C3 2026-08-17).
    Constructed only by build_compiler_provider — the judge precedent: the
    server's Providers bundle never carries this role and the seam builds it
    lazily at first use. Prompts arrive fully assembled (app\\compiler.py
    owns the block shape); `item` is the fake's structural input and is
    ignored here. Fixed max_tokens bounds follow the write-call precedent
    (a structural bound, not integrator policy)."""

    def __init__(self, settings: Settings):
        import anthropic

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_compiler

    def compile(
        self,
        *,
        system_prompt: str,
        user_content: str,
        item: CompilerItem,
    ) -> CompilerCallResult:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as exc:
            raise ProviderCallError(f"compile call failed: {exc}") from exc
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        try:
            payload = json.loads(_lenient_json_text(_first_text_block(response)))
            multipliers = payload["multipliers"]
            if not isinstance(multipliers, dict):
                raise ValueError("'multipliers' is not an object")
            passthrough = payload.get("passthrough", {})
            if not isinstance(passthrough, dict):
                raise ValueError("'passthrough' is not an object")
            result = CompilerCallResult(
                w_relevance=float(multipliers["relevance"]),
                w_recency=float(multipliers["recency"]),
                w_importance=float(multipliers["importance"]),
                passthrough=passthrough,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MalformedOutputError(
                f"compile output unparseable: {exc}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc
        return result


class RealEmbeddingProvider:
    """OpenAI text-embedding-3-small @ 1536 (locked)."""

    def __init__(self, settings: Settings):
        import openai

        self._client = openai.OpenAI(api_key=settings.openai_api_key)

    def embed(self, texts: list[str]) -> EmbedResult:
        try:
            response = self._client.embeddings.create(
                model=EMBEDDING_MODEL, input=texts, dimensions=EMBEDDING_DIM
            )
        except Exception as exc:
            raise ProviderCallError(f"embedding call failed: {exc}") from exc
        vectors = [item.embedding for item in response.data]
        return EmbedResult(vectors=vectors, tokens=response.usage.total_tokens)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Providers:
    # `dialogue` and `reconstruction` default to their fakes so pre-existing
    # constructions (the earlier structural walkers) stand unchanged;
    # build_providers always sets them explicitly. `dialogue` is the streaming
    # PROSE provider — the dialogue turn's only model call since the A1
    # re-shape (2026-08-04).
    write: WriteProvider
    escalation: EscalationProvider
    embedding: EmbeddingProvider
    dialogue: DialogueProvider = field(default_factory=FakeProseProvider)
    reconstruction: ReconstructionProvider = field(
        default_factory=FakeReconstructionProvider
    )
    # The concurrency cap (C7): one gate per process, carried here so every seam
    # and worker reaches it as `providers.gate`. The default-factory keeps
    # pre-existing direct Providers(...) constructions (the structural walkers)
    # unchanged; build_providers always sizes it from settings.
    gate: ModelCallGate = field(
        default_factory=lambda: ModelCallGate(MAX_CONCURRENT_MODEL_CALLS_DEFAULT)
    )


def build_providers(settings: Settings) -> Providers:
    """Provider selection by config; the services are identical under either.
    The concurrency gate is sized from settings and shared by both modes (fake
    calls route through it too, so the gated path is exercised offline)."""
    gate = ModelCallGate(settings.max_concurrent_model_calls)
    if settings.provider_mode == "real":
        return Providers(
            write=RealWriteProvider(settings),
            escalation=RealEscalationProvider(settings),
            embedding=RealEmbeddingProvider(settings),
            dialogue=RealDialogueProvider(settings),
            reconstruction=RealReconstructionProvider(settings),
            gate=gate,
        )
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=FakeEmbeddingProvider(),
        dialogue=FakeProseProvider(),
        reconstruction=FakeReconstructionProvider(),
        gate=gate,
    )


def build_judge_provider(settings: Settings) -> JudgeProvider:
    """Standalone judge selection (stage-3 ruling: the judge is NOT a field on
    the frozen Providers bundle — the server never carries one). A real judged
    run without the judge var is the runner-side loud error the spec assigns;
    the var is otherwise loaded-never-required (load_settings)."""
    if settings.provider_mode == "real":
        if not settings.model_judge:
            raise ConfigError(
                f"a judged run in real mode requires {ENV_MODEL_JUDGE} in .env."
            )
        return RealJudgeProvider(settings)
    return FakeJudgeProvider()


def build_reflection_provider(settings: Settings) -> ReflectionProvider:
    """Standalone reflection selection (the judge shape, ruled 2026-08-15:
    NOT a field on the frozen Providers bundle — the server never carries
    one; the reflect seam builds it lazily at first use). A real reflect
    without the var is the loud first-use error the spec assigns; the var
    is otherwise loaded-never-required (load_settings)."""
    if settings.provider_mode == "real":
        if not settings.model_reflection:
            raise ConfigError(
                f"a reflect call in real mode requires {ENV_MODEL_REFLECTION} in .env."
            )
        return RealReflectionProvider(settings)
    return FakeReflectionProvider()


def build_compiler_provider(settings: Settings) -> CompilerProvider:
    """Standalone compiler selection (the judge shape, the C3 ruling
    2026-08-17: NOT a field on the frozen Providers bundle — the compiler
    seam builds it lazily at first use). A real compile without the var is
    the loud first-use error the spec assigns — always inside the worker,
    since C3 has no endpoint verb; the var is otherwise loaded-never-required
    (load_settings)."""
    if settings.provider_mode == "real":
        if not settings.model_compiler:
            raise ConfigError(
                f"a compile call in real mode requires {ENV_MODEL_COMPILER} in .env."
            )
        return RealCompilerProvider(settings)
    return FakeCompilerProvider()
