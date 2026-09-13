"""nlp.py: the no-LLM write pass (architecture.md §5, the NLP stage).

spaCy (en_core_web_lg) + fastcoref intra-observation coreference + VADER
valence + Warriner 2013 VAD lexicon (arousal/dominance). NRC-VAD was rejected
at the license gate (research-only); Warriner
is CC-BY 4.0 and bundled under data\\lexicons\\ with attribution.

Outputs:
  - gist spans as half-open char offsets into the immutable observation_text
    (never rewritten text), matched against the agent's identity_components
    (canonical + aliases + category; a category hit counts without a named
    entity and carries matched_category with a NULL component id);
  - novel-entity candidates (NER hits absent from the component index) that
    grow identity_components;
  - affect: VADER compound -> valence; Warriner lemma lookup -> arousal
    (normalized 1-9 -> 0-1); dominance + raw breakdown -> affect_detail jsonb
    (the frozen schema has no dominance column — ruled 2026-07-13);
  - escalation trigger evaluation (five triggers ruled 2026-07-13 + the
    thin_gist span-floor trigger ruled 2026-07-23),
    biased loose: confidence only ever ADDS calls.

Confidence sources: fastcoref cluster spans carry no per-span probability in
its public predict API, and en_core_web_lg's greedy NER exposes none either —
so v1 treats every coref-derived identity span as low-confidence (over-call,
biased loose, per the plan's fallback). Direct string matches of known
canonical/alias/category terms are deterministic and count as confident.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.providers import GistSpanCandidate, NewComponent

REPO_ROOT = Path(__file__).resolve().parent.parent
WARRINER_CSV = REPO_ROOT / "data" / "lexicons" / "warriner_2013_vad.csv"

SPACY_MODEL = "en_core_web_lg"

# spaCy NER label -> component category vocabulary used for novel growth.
NER_CATEGORY = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "place",
    "LOC": "place",
    "FAC": "place",
    "NORP": "group",
    "PRODUCT": "thing",
    "EVENT": "event",
    "WORK_OF_ART": "work",
}

PRONOUN_TAGS = {"PRP", "PRP$"}

# Escalation trigger names surfaced in escalated_by (instrumentation).
TRIGGER_IMPORTANCE = "importance_threshold"
TRIGGER_IDENTITY_AFFECT = "identity_affect"
TRIGGER_NOVEL_ENTITY = "novel_entity"
TRIGGER_UNRESOLVED_REFERENCE = "unresolved_reference"
TRIGGER_LOW_CONFIDENCE = "low_confidence"
TRIGGER_THIN_GIST = "thin_gist"  # base gist below the span floor (ruled 2026-07-23)


@dataclass
class NlpResult:
    """Everything the seam needs from the no-LLM pass."""

    spans: list[GistSpanCandidate]
    novel_components: list[NewComponent]
    entities: list[str]
    affect_valence: float | None
    affect_arousal: float | None
    affect_detail: dict | None
    # trigger raw material
    has_identity_hit: bool = False
    has_unresolved_reference: bool = False
    has_low_confidence_span: bool = False
    coref_span_count: int = 0


@lru_cache(maxsize=1)
def _spacy():
    import spacy

    return spacy.load(SPACY_MODEL)


def _tame_datasets_fingerprint() -> None:
    """Kill the biggest write-path cost: fastcoref's per-observation dataset
    fingerprinting.

    `FCoref.predict` builds a fresh `datasets.Dataset` and `.map()`s a
    tokenizer over it on EVERY call. `datasets` derives a content fingerprint
    for that map by dill-pickling the transform's closure — which reaches
    fastcoref's internal spaCy pipeline, and `datasets`' spaCy dill-reducer
    then serializes the whole model. Measured (cProfile + wall clock): ~90 ms
    of a ~136 ms write pass, every observation, entirely to name a cache file
    we never read.

    Fix: turn caching off (the mapped dataset is consumed in-process and never
    re-read) and replace the fingerprint Hasher with a constant. Safe together
    because caching is disabled — constant fingerprints can't collide on any
    cache file — and the fingerprint otherwise only sets an ephemeral dataset's
    `_fingerprint` attribute; it never affects the tokenizer's OUTPUT, so
    coref results (the walkers' assertion surface) are byte-identical. Measured
    ~136 ms -> ~48 ms per write (the residue is the real coref inference).

    Guarded end to end: this is an OPTIMIZATION, never a correctness lever. Any
    drift in the `datasets` internals (attr renamed or gone) is swallowed and
    leaves the slow-but-correct path exactly as it was — the worst case is we
    stop saving the 90 ms, never a wrong or failed write.
    """
    try:
        import datasets
        from datasets.fingerprint import Hasher

        datasets.disable_caching()
        if not getattr(Hasher, "_twicetold_tamed", False):
            Hasher.hash = staticmethod(lambda _obj: "twicetold-nofingerprint")
            Hasher._twicetold_tamed = True
    except Exception:  # noqa: BLE001 — optimization only; never break the pass
        pass


@lru_cache(maxsize=1)
def _coref():
    from fastcoref import FCoref

    _tame_datasets_fingerprint()
    return FCoref(device="cpu")


@lru_cache(maxsize=1)
def _vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


@lru_cache(maxsize=1)
def _warriner() -> dict[str, tuple[float, float, float]]:
    """word -> (valence, arousal, dominance) means on the 1-9 scale."""
    if not WARRINER_CSV.exists():
        raise FileNotFoundError(
            f"Warriner VAD lexicon missing: {WARRINER_CSV} (see data\\lexicons\\ATTRIBUTION.md)"
        )
    table: dict[str, tuple[float, float, float]] = {}
    # utf-8-sig: tolerate a BOM (the bundled CSV was written by PowerShell)
    with WARRINER_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            table[row["Word"].lower()] = (
                float(row["V.Mean.Sum"]),
                float(row["A.Mean.Sum"]),
                float(row["D.Mean.Sum"]),
            )
    return table


def warm_pipelines() -> None:
    """Load every model up front (startup cost, not first-request cost)."""
    _spacy()
    _coref()
    _vader()
    _warriner()


def _find_term_spans(text: str, term: str) -> list[tuple[int, int]]:
    """Case-insensitive whole-word occurrences of term -> half-open offsets."""
    if not term.strip():
        return []
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
    return [(m.start(), m.end()) for m in pattern.finditer(text)]


def find_term_spans(text: str, term: str) -> list[tuple[int, int]]:
    """The gate's tripwire atom, promoted public 2026-07-19
    (mid-dialogue-gate.md): mention detection is this same case-insensitive
    whole-word match — mechanical string work stays mechanical, no spaCy on
    the read path."""
    return _find_term_spans(text, term)


def extract_entities(text: str) -> list[str]:
    """NER-only pass — the run_write_pass step-4 mirror without coref/affect:
    surface entity strings whose labels sit in NER_CATEGORY, document order,
    no dedup (the caller merges with operator-supplied entities using the
    observe-path dedup). Used by the correction verb's entities re-derivation
    (fork 3, 2026-07-19); the lru-cached spaCy model means no extra load."""
    doc = _spacy()(text)
    return [
        ent.text.strip()
        for ent in doc.ents
        if ent.text.strip() and ent.label_ in NER_CATEGORY
    ]


def lemma_content_set(text: str) -> set[str]:
    """Lowercased content lemmas — byte-for-byte the write pass's Warriner
    token filter (not stop/punct/space), promoted public for the judge-free
    eval metrics (eval-harness.md stage 1; the extract_entities promotion
    precedent). The lru-cached spaCy model means no extra load."""
    doc = _spacy()(text)
    return {
        token.lemma_.lower()
        for token in doc
        if not (token.is_stop or token.is_punct or token.is_space)
    }


def _dedupe_overlapping(spans: list[GistSpanCandidate]) -> list[GistSpanCandidate]:
    """Drop spans fully contained in an already-kept span (longest first)."""
    kept: list[GistSpanCandidate] = []
    for span in sorted(spans, key=lambda s: s.end_char - s.start_char, reverse=True):
        contained = any(
            span.start_char >= k.start_char and span.end_char <= k.end_char
            for k in kept
        )
        if not contained:
            kept.append(span)
    return sorted(kept, key=lambda s: s.start_char)


def run_write_pass(observation_text: str, components: list[dict]) -> NlpResult:
    """The full no-LLM pass over one observation.

    `components` rows need: component_id, canonical, aliases, category.
    """
    doc = _spacy()(observation_text)

    # --- 1. direct identity matches: canonical + aliases ------------------
    spans: list[GistSpanCandidate] = []
    matched_component_char_ranges: list[tuple[int, int, str]] = []
    for comp in components:
        terms = [comp["canonical"], *(comp.get("aliases") or [])]
        for term in terms:
            for start, end in _find_term_spans(observation_text, term):
                spans.append(
                    GistSpanCandidate(
                        start_char=start,
                        end_char=end,
                        matched_component_id=str(comp["component_id"]),
                        matched_category=comp.get("category"),
                    )
                )
                matched_component_char_ranges.append(
                    (start, end, str(comp["component_id"]))
                )

    # --- 2. category hits without a named entity --------------------------
    # A component category term appearing in the text counts as gist even when
    # no canonical/alias matched (schema: matched_category, NULL component id).
    seen_categories: set[str] = set()
    for comp in components:
        category = comp.get("category")
        if not category or category in seen_categories:
            continue
        seen_categories.add(category)
        for start, end in _find_term_spans(observation_text, category):
            spans.append(
                GistSpanCandidate(
                    start_char=start,
                    end_char=end,
                    matched_component_id=None,
                    matched_category=category,
                )
            )

    # --- 3. intra-observation coreference ----------------------------------
    # A pronoun/mention coreferent with a matched component mention becomes a
    # gist span for that component. fastcoref exposes no per-span probability
    # via predict(), so coref-derived spans count as low-confidence (they only
    # ever ADD an escalation call, never suppress one).
    coref_span_count = 0
    resolved_pronoun_ranges: list[tuple[int, int]] = []
    prediction = _coref().predict(texts=[observation_text])[0]
    for cluster in prediction.get_clusters(as_strings=False):
        cluster_components = {
            comp_id
            for m_start, m_end in cluster
            for c_start, c_end, comp_id in matched_component_char_ranges
            if m_start <= c_start and c_end <= m_end
        }
        if not cluster_components:
            continue
        comp_id = sorted(cluster_components)[0]
        for m_start, m_end in cluster:
            resolved_pronoun_ranges.append((m_start, m_end))
            already = any(
                s.start_char == m_start
                and s.end_char == m_end
                and s.matched_component_id
                for s in spans
            )
            if not already:
                spans.append(
                    GistSpanCandidate(
                        start_char=m_start,
                        end_char=m_end,
                        matched_component_id=comp_id,
                        matched_category=None,
                    )
                )
                coref_span_count += 1

    spans = _dedupe_overlapping(spans)

    # --- 4. NER entities + novel-entity candidates ------------------------
    known_terms = {
        term.lower()
        for comp in components
        for term in [comp["canonical"], *(comp.get("aliases") or [])]
    }
    entities: list[str] = []
    novel: list[NewComponent] = []
    seen_novel: set[str] = set()
    for ent in doc.ents:
        text = ent.text.strip()
        if not text or ent.label_ not in NER_CATEGORY:
            continue
        entities.append(text)
        if text.lower() not in known_terms and text.lower() not in seen_novel:
            seen_novel.add(text.lower())
            novel.append(
                NewComponent(
                    canonical=text, aliases=[], category=NER_CATEGORY[ent.label_]
                )
            )

    # --- 5. unresolved references ------------------------------------------
    has_unresolved = False
    for token in doc:
        if token.tag_ not in PRONOUN_TAGS:
            continue
        covered = any(
            start <= token.idx and (token.idx + len(token.text)) <= end
            for start, end in resolved_pronoun_ranges
        )
        if not covered:
            has_unresolved = True
            break

    # --- 6. affect -----------------------------------------------------------
    vader_scores = _vader().polarity_scores(observation_text)
    valence = float(vader_scores["compound"])

    table = _warriner()
    matched: list[tuple[float, float, float]] = []
    for token in doc:
        if token.is_stop or token.is_punct or token.is_space:
            continue
        row = table.get(token.lemma_.lower()) or table.get(token.text.lower())
        if row:
            matched.append(row)
    arousal: float | None = None
    dominance_norm: float | None = None
    warriner_detail: dict | None = None
    if matched:
        v_mean = sum(r[0] for r in matched) / len(matched)
        a_mean = sum(r[1] for r in matched) / len(matched)
        d_mean = sum(r[2] for r in matched) / len(matched)
        arousal = round((a_mean - 1.0) / 8.0, 4)
        dominance_norm = round((d_mean - 1.0) / 8.0, 4)
        warriner_detail = {
            "valence_mean_1_9": round(v_mean, 4),
            "arousal_mean_1_9": round(a_mean, 4),
            "dominance_mean_1_9": round(d_mean, 4),
            "matched_lemmas": len(matched),
        }
    detail = {
        "vader": {k: float(v) for k, v in vader_scores.items()},
        "warriner": warriner_detail,
        "dominance": dominance_norm,
        "source": "lexicon",
    }

    return NlpResult(
        spans=spans,
        novel_components=novel,
        entities=entities,
        affect_valence=valence,
        affect_arousal=arousal,
        affect_detail=detail,
        has_identity_hit=bool(spans),
        has_unresolved_reference=has_unresolved,
        has_low_confidence_span=coref_span_count > 0,
        coref_span_count=coref_span_count,
    )


def evaluate_triggers(
    nlp_result: NlpResult, importance_raw: float, knobs: dict[str, float]
) -> list[str]:
    """The six escalation triggers (five ruled 2026-07-13; thin_gist added by
    the 2026-07-23 trigger-tuning ruling). ANY one fires the call.

    Biased loose: (5) only ever adds a call for spans something else already
    flagged; nothing here suppresses. `importance_raw` is the effective value
    (a scoring-failed neutral importance can legitimately trip (1) — uncertain
    importance escalating is loose in the right direction). (6) thin_gist
    protects the gist floor directly: a base NLP pass with fewer spans than
    `escalation_min_base_spans` escalates regardless of importance — measured
    2026-07-23, 16/80 realistic observes otherwise land with ZERO gist spans,
    leaving reconstruction's fixed constraint empty. Knob 0.0 disables (span
    counts are never negative).
    """
    triggers: list[str] = []
    if importance_raw >= knobs["escalation_importance_threshold"]:
        triggers.append(TRIGGER_IMPORTANCE)
    if nlp_result.has_identity_hit and nlp_result.affect_valence is not None:
        if abs(nlp_result.affect_valence) >= knobs["escalation_affect_threshold"]:
            triggers.append(TRIGGER_IDENTITY_AFFECT)
    if nlp_result.novel_components:
        triggers.append(TRIGGER_NOVEL_ENTITY)
    if nlp_result.has_unresolved_reference and nlp_result.has_identity_hit:
        triggers.append(TRIGGER_UNRESOLVED_REFERENCE)
    if nlp_result.has_low_confidence_span:
        triggers.append(TRIGGER_LOW_CONFIDENCE)
    if len(nlp_result.spans) < knobs["escalation_min_base_spans"]:
        triggers.append(TRIGGER_THIN_GIST)
    return triggers
