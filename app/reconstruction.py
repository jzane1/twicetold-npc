"""reconstruction.py: the read path's reconstruction serving stage (architecture.md §7).

Identity-conditioned reconstruction is the mandatory read path for unpinned
memories past theta (architecture §7). This module is the serving-stage
engine the retrieval seam delegates to: theta partition -> cache batch-fetch
-> batched retelling call for the misses -> per-item drift check -> persist
-> serve. Retrieval and scoring are untouched by this stage.

Design lines (architecture.md §7):
  - Every text-affecting decay evaluation (theta, band, thinning) binds to
    the SCENE-FROZEN basis (caller-passed scene_started_at, else
    as_of_effective), so read-mode and served text cannot flip mid-scene.
  - The band both keys the cache (composed with identity_version) and sets
    the thinning level, so same key => same input => byte-identical text.
  - SERVE ONLY PERSISTED TEXT: a model response that failed to persist is
    never served — the write-back transaction (chain supersession + new
    `reconstruction` head + cache row) commits before the text goes out.
  - read_mode is honest to what was actually served: a failed or refused
    reconstruction serves the live head under the head's own mode.
  - Degradation is named per model call (the ladder in architecture.md §7):
    call failure -> fail-quiet, serve heads, write nothing; drift-embed
    failure -> fail-closed on the write (refuse, serve head; NOT cached, so
    a transient embed outage never permanently pins a key); persistence
    failure -> serve the head, the next read retries the miss.
  - CONSTRAINT FOLLOWS THE ANCHOR (architecture.md §7 and §8): a
    correction-anchored chain
    (`FIXED_CONSTRAINT_ANCHORS`) retells from that head as the fixed
    constraint — no observation-derived gist or detail is re-injected (it
    may contain exactly the data the operator corrected away, or details
    the character conceded at a confrontation); the band still keys the
    cache. Original-anchored chains are unchanged; `rationalization` heads
    never anchor at all (the crystallization rule).

Cache-hit corner (documented shape): after backwards time travel a cached
telling can predate the current live head. The cache row is still served
(same key => byte-identical text, Set C); `detail_id` in the payload always
identifies the LIVE chain head, `content` the key's telling.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, decay, identity
from app.config import Settings, agent_knob
from app.providers import (
    MalformedOutputError,
    ProviderCallError,
    Providers,
    ReconstructionItem,
)
from app.schemas import DialogueInitRequest, RetrievedMemory

logger = logging.getLogger(__name__)

# Eval capture seam (eval-harness.md stage 2, the `on_reconstruct` shape):
# invoked once per checked item at the drift computation as
# (memory_id, cosine_distance, refused), where refused == distance > threshold
# — the budget refused this write-back. None (the default) leaves serving
# byte-identical to the pre-seam floor. Set only by the eval runner; the blind
# embed-failure refusal path carries no distance and never calls it.
drift_observer: Callable[[UUID, float, bool], None] | None = None


class UnknownIdentityVersionError(RuntimeError):
    """A caller-passed identity_version the server does not know — a broken
    caller contract (loud), never a flaky model (which degrades soft)."""


# Sentence boundary for thinning: deterministic, dependency-free (no spaCy on
# the read path), stable across environments.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_SYSTEM_TASK = (
    "[task]\n"
    "You are the reconstructive memory of a game character. Retell each "
    "remembered event as the character currently holds it, in first person. "
    "Per item: 'gist' lists FIXED facts — every retelling must remain "
    "consistent with all of them; 'detail' is the fragmentary detail still "
    "available (it may be thin — fill gaps plausibly, in character); "
    "'current_telling' is how the character currently tells it, the starting "
    "point. Return ONLY a JSON object mapping each memory_id to its "
    "retelling string. No other text."
)
# The stage-4 ablation's OFF-arm task (ruled 2026-08-12): the same contract
# with the gist sentence removed — items carry no 'gist' key, so the
# retelling is unconstrained by fixed facts. Eval-only in practice; the
# production default keeps the constraint (reconstruction_gist_constraint
# 1.0).
_SYSTEM_TASK_NO_GIST = (
    "[task]\n"
    "You are the reconstructive memory of a game character. Retell each "
    "remembered event as the character currently holds it, in first person. "
    "Per item: 'detail' is the fragmentary detail still available (it may "
    "be thin — fill gaps plausibly, in character); 'current_telling' is how "
    "the character currently tells it, the starting point. Return ONLY a "
    "JSON object mapping each memory_id to its retelling string. No other "
    "text."
)
_BLOCK_IDENTITY = "[identity]\n{document}"

# The anchor causes whose head IS the fixed constraint (constraint follows
# the anchor): `authorial_correction` and `update_with_resentment`. An
# accepted in-world correction retells from the accepted account, and
# original observation gist cannot resurrect details the character conceded.
FIXED_CONSTRAINT_ANCHORS = frozenset({"authorial_correction", "update_with_resentment"})


# ---------------------------------------------------------------------------
# Pure functions (walker-assertable without a database or model call)
# ---------------------------------------------------------------------------


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping/adjacent half-open span offsets."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def split_gist_detail(
    observation_text: str, spans: list[tuple[int, int]]
) -> tuple[str, list[str]]:
    """(gist_text, detail_segments): gist = the merged span texts verbatim,
    newline-joined; detail = the stripped non-empty between-span remainders."""
    merged = merge_spans(spans)
    gist_parts = [observation_text[start:end] for start, end in merged]
    segments: list[str] = []
    cursor = 0
    for start, end in merged:
        segment = observation_text[cursor:start].strip()
        if segment:
            segments.append(segment)
        cursor = end
    tail = observation_text[cursor:].strip()
    if tail:
        segments.append(tail)
    return "\n".join(gist_parts), segments


def band_index(strength: float, quantum: float) -> int:
    """Quantized thinning band: 0 = freshest. Capped at the last band so the
    level below never goes meaningfully negative."""
    cap = math.ceil(1.0 / quantum) - 1
    return min(max(int((1.0 - strength) / quantum), 0), cap)


def band_level(index: int, quantum: float) -> float:
    """The band's midpoint strength — the thinning proportion. A property of
    the BAND (not the raw strength) so same cache key => same input."""
    return max(0.0, 1.0 - (index + 0.5) * quantum)


def compose_cache_key(identity_version: str, band: int) -> str:
    """The composed reconstruction key stored in the cache's version column
    (spec ruling 2026-07-17): identity_version + the decay band."""
    return f"{identity_version}|b{band}"


def thin_detail(segments: list[str], level: float) -> str:
    """Deterministic, monotone thinning: per contiguous detail segment,
    retain the first ceil(level x n) sentences (always >= 1 — gist carries
    the floor of durability; detail thins toward minimal, never to nothing
    while the segment survives at all)."""
    kept: list[str] = []
    for segment in segments:
        sentences = _SENTENCE_SPLIT.split(segment)
        retain = max(1, math.ceil(level * len(sentences)))
        kept.append(" ".join(sentences[:retain]))
    return "\n".join(kept)


def build_reconstruction_item(
    memory_id: str,
    source: db.ReconstructionSource,
    level: float,
    current_telling: str,
    *,
    gist_constraint: bool = True,
) -> ReconstructionItem:
    """The per-memory call inputs, anchor-cause-aware (constraint follows
    the anchor, architecture.md §7 and §8): on a
    correction-anchored chain (`FIXED_CONSTRAINT_ANCHORS`) that head IS the
    fixed facts (the gist slot), with no observation-derived detail
    re-injected; original-anchored chains build byte-identically to the
    pre-correction stage. Pure — walker-assertable without a database or
    model call.

    `gist_constraint=False` (stage-4 ablation OFF arm, ruled 2026-08-12)
    blanks the gist on ORIGINAL-anchored items only; a correction-anchored
    chain keeps the correction head regardless (fork 11 — blanking it would
    delete the correction; the C4 extension inherits the rule). The default
    keeps every existing call byte-identical."""
    if source.anchor_cause in FIXED_CONSTRAINT_ANCHORS:
        return ReconstructionItem(
            memory_id=memory_id,
            gist=source.anchor_content,
            thinned_detail="",
            current_telling=current_telling,
        )
    gist, segments = split_gist_detail(source.observation_text, source.spans)
    return ReconstructionItem(
        memory_id=memory_id,
        gist=gist if gist_constraint else "",
        thinned_detail=thin_detail(segments, level),
        current_telling=current_telling,
    )


def assemble_reconstruction_prompt(
    identity_document: str,
    items: list[ReconstructionItem],
    *,
    include_gist_constraint: bool = True,
) -> tuple[str, str]:
    """(system_prompt, user_content), byte-stable for identical inputs. The
    identity block is omitted for an empty document (NULL-seed rule); items
    arrive sorted by memory_id (the seam sorts) so the JSON is deterministic.

    `include_gist_constraint=False` (stage-4 ablation OFF arm, ruled
    2026-08-12) swaps the task block for `_SYSTEM_TASK_NO_GIST` and omits
    the `"gist"` key from every item — the retelling runs unconstrained.
    The default reproduces the pre-stage-4 prompt byte-for-byte."""
    blocks: list[str] = []
    if identity_document:
        blocks.append(_BLOCK_IDENTITY.format(document=identity_document))
    blocks.append(_SYSTEM_TASK if include_gist_constraint else _SYSTEM_TASK_NO_GIST)
    payload: list[dict] = []
    for item in items:
        entry: dict = {"memory_id": item.memory_id}
        if include_gist_constraint:
            entry["gist"] = item.gist
        entry["detail"] = item.thinned_detail
        entry["current_telling"] = item.current_telling
        payload.append(entry)
    user_content = json.dumps(payload)
    return "\n\n".join(blocks), user_content


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity; degenerate zero-norm vectors read as maximally
    distant (fail-closed for the budget)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# The serving stage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ServeOutcome:
    """Items in rank order + the stage's instrumentation deltas."""

    items: list[RetrievedMemory]
    reconstruction_ms: float
    input_tokens: int
    output_tokens: int
    embed_tokens: int
    cache_hits: int
    cache_misses: int
    write_backs: int
    drift_refusals: int
    identity_version: str
    identity_bootstrapped: bool
    degraded_reason: str | None


@dataclass
class _Slot:
    """One top-k row moving through the stage."""

    score: float
    relevance: float | None
    recency: float
    importance_norm: float
    importance_raw: float
    row: db.CandidateRow
    read_mode: str = "verbatim"
    content: str | None = None  # None until served
    detail_id: UUID | None = None
    composed_key: str | None = None  # set only on the reconstructed path
    band: int = 0


def _head_mode(row: db.CandidateRow) -> str:
    """read_mode honesty for a served live head."""
    return "reconstructed" if row.write_cause == "reconstruction" else "verbatim"


class ReconstructionService:
    """Constructed by RetrievalService; one instance per process."""

    def __init__(
        self, pool: AsyncConnectionPool, providers: Providers, settings: Settings
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings

    async def serve(
        self,
        *,
        request: DialogueInitRequest,
        config: dict,
        seed_identity: str | None,
        scored_top: list[
            tuple[float, float | None, float, float, float, db.CandidateRow]
        ],
        as_of: datetime,
        on_reconstruct: Callable[[], None] | None = None,
    ) -> ServeOutcome:
        t0 = time.perf_counter()
        theta = agent_knob(config, "reconstruction_theta", self._settings)
        quantum = agent_knob(config, "reconstruction_band_quantum", self._settings)
        threshold = agent_knob(config, "drift_budget_threshold", self._settings)
        k_importance = agent_knob(config, "decay_k_importance", self._settings)
        neutral = agent_knob(config, "importance_neutral", self._settings)
        # Stage-4 ablation switch (ruled 2026-08-12), the gate_enabled
        # truthiness convention. Deliberately NOT in compose_cache_key: arms
        # live on separate scratch DBs; a live mid-process flip could serve
        # stale-keyed text (the kill-switch caveat, documented in
        # eval-harness.md).
        gist_constraint = (
            agent_knob(config, "reconstruction_gist_constraint", self._settings) != 0.0
        )

        # Scene-frozen basis: every text-affecting decay evaluation below
        # uses this, never the per-call as_of (which scores may follow).
        basis = (
            request.scene_started_at if request.scene_started_at is not None else as_of
        )

        # --- identity resolution (hybrid plumbing, ruled 2026-07-17) -------
        bootstrapped = False
        if request.identity_version is not None:
            document = await db.fetch_identity_document(
                self._pool, request.agent_id, request.identity_version
            )
            if document is None:
                raise UnknownIdentityVersionError(
                    f"unknown identity_version {request.identity_version!r} "
                    f"for agent {request.agent_id}"
                )
            version = request.identity_version
        else:
            version, document, _created = await identity.ensure_identity_document(
                self._pool, request.agent_id, seed_identity
            )
            bootstrapped = True

        # --- theta partition (three-state read-mode boundary) --------------
        slots = [_Slot(*entry) for entry in scored_top]
        recon_slots: list[_Slot] = []
        for slot in slots:
            row = slot.row
            if row.pinned:  # pin = reconstruction exclusion (architecture §8)
                continue
            raw = row.importance_raw if row.importance_raw is not None else neutral
            tau_base = decay.resolve_tau_base(row.decay_class, config, self._settings)
            tau_eff = decay.tau_effective(tau_base, k_importance, raw)
            strength = decay.recency((basis - row.valid_at).total_seconds(), tau_eff)
            if strength >= theta:
                continue  # fresher than the threshold: verbatim for now
            slot.band = band_index(strength, quantum)
            slot.composed_key = compose_cache_key(version, slot.band)
            recon_slots.append(slot)

        # --- cache batch-fetch ---------------------------------------------
        cache = await db.fetch_cache_rows(
            self._pool,
            [(slot.row.memory_id, slot.composed_key) for slot in recon_slots],
        )
        misses: list[_Slot] = []
        cache_hits = 0
        for slot in recon_slots:
            cached = cache.get((slot.row.memory_id, slot.composed_key))
            if cached is None:
                misses.append(slot)
                continue
            cache_hits += 1
            slot.content = cached
            slot.detail_id = slot.row.detail_id
            # Honesty: an evicted-on-write cache means a row equal to the live
            # head came from that head; anything else is a stored retelling.
            slot.read_mode = (
                _head_mode(slot.row) if cached == slot.row.content else "reconstructed"
            )

        # --- the batched retelling call for the misses ---------------------
        input_tokens = output_tokens = embed_tokens = 0
        write_backs = drift_refusals = 0
        degraded_reasons: list[str] = []

        if misses:
            sources = await db.fetch_reconstruction_sources(
                self._pool, [slot.row.memory_id for slot in misses]
            )
            call_slots = [s for s in misses if s.row.memory_id in sources]
            for slot in misses:
                if slot.row.memory_id not in sources:  # defensive: no anchor row
                    degraded_reasons.append(
                        f"no reconstruction source for {slot.row.memory_id}"
                    )
            # Fixed-gist ablation partition (stage 4, ruled 2026-08-12): with
            # the knob OFF, original-anchored misses retell WITHOUT the gist
            # block while correction-anchored misses still retell normally
            # (fork 11 — their gist IS the corrected head). Default ON is a
            # single group, byte-identical to the pre-stage-4 call.
            if gist_constraint:
                groups: list[tuple[bool, list[_Slot]]] = [(True, call_slots)]
            else:
                groups = [
                    (
                        False,
                        [
                            s
                            for s in call_slots
                            if sources[s.row.memory_id].anchor_cause
                            not in FIXED_CONSTRAINT_ANCHORS
                        ],
                    ),
                    (
                        True,
                        [
                            s
                            for s in call_slots
                            if sources[s.row.memory_id].anchor_cause
                            in FIXED_CONSTRAINT_ANCHORS
                        ],
                    ),
                ]
            retellings: dict[str, str] = {}
            call_ok = False
            if call_slots and on_reconstruct is not None:
                # The pre-serve callback (mid-dialogue-gate.md fork 5,
                # 2026-07-19): fired ONCE, the moment a real blocking
                # retelling call is about to run — the caller can show
                # "(reconstructing…)" DURING the pause (latency becomes
                # characterization, architecture §7). Absent parameter =>
                # behavior byte-identical to the pre-gate floor.
                on_reconstruct()
            for include_gist, group in groups:
                if not group:
                    continue
                items: list[ReconstructionItem] = []
                for slot in sorted(group, key=lambda s: str(s.row.memory_id)):
                    items.append(
                        build_reconstruction_item(
                            str(slot.row.memory_id),
                            sources[slot.row.memory_id],
                            band_level(slot.band, quantum),
                            slot.row.content,
                            gist_constraint=include_gist,
                        )
                    )
                system_prompt, user_content = assemble_reconstruction_prompt(
                    document, items, include_gist_constraint=include_gist
                )
                try:  # single attempt per group (ruled): read latency, not a lost write
                    result = await self._providers.gate.run(
                        self._providers.reconstruction.reconstruct,
                        system_prompt=system_prompt,
                        user_content=user_content,
                        items=items,
                    )
                    retellings.update(result.retellings)
                    input_tokens += result.input_tokens
                    output_tokens += result.output_tokens
                    call_ok = True
                except ProviderCallError as exc:
                    degraded_reasons.append(f"reconstruction call failed: {exc}")
                except MalformedOutputError as exc:
                    degraded_reasons.append(f"reconstruction output malformed: {exc}")
                    input_tokens += exc.input_tokens  # the spend happened
                    output_tokens += exc.output_tokens

            # --- drift check + persistence, per miss -----------------------
            if call_ok:
                checked: list[tuple[_Slot, str, str]] = []  # slot, candidate, anchor
                for slot in call_slots:
                    candidate = retellings.get(str(slot.row.memory_id))
                    if candidate is None:  # per-item salvage: this item degrades
                        degraded_reasons.append(
                            f"no retelling returned for {slot.row.memory_id}"
                        )
                        continue
                    checked.append(
                        (slot, candidate, sources[slot.row.memory_id].anchor_content)
                    )
                vectors: list[list[float]] | None = None
                if checked:
                    texts: list[str] = []
                    for _, candidate, anchor in checked:
                        texts.extend((candidate, anchor))
                    try:
                        embed_result = await self._providers.gate.run(
                            self._providers.embedding.embed, texts
                        )
                        vectors = embed_result.vectors
                        embed_tokens = embed_result.tokens
                    except ProviderCallError as exc:
                        # Fail-closed on the write: refuse every write-back on
                        # a blind check; NOT cached, so a transient outage
                        # never permanently pins a key.
                        degraded_reasons.append(f"drift-check embedding failed: {exc}")
                        drift_refusals += len(checked)
                        vectors = None
                if vectors is not None:
                    for index, (slot, candidate, _anchor) in enumerate(checked):
                        distance = cosine_distance(
                            vectors[2 * index], vectors[2 * index + 1]
                        )
                        refused = distance > threshold
                        if drift_observer is not None:
                            drift_observer(slot.row.memory_id, distance, refused)
                        if refused:
                            drift_refusals += 1
                            logger.info(
                                "drift budget refused write-back for %s "
                                "(distance %.4f > %.4f)",
                                slot.row.memory_id,
                                distance,
                                threshold,
                            )
                            # Refusal caching (ruled): the served prior text
                            # is cached under the key — stable and call-free
                            # on the next same-key read.
                            await db.insert_cache_row(
                                self._pool,
                                slot.row.memory_id,
                                slot.composed_key,
                                slot.row.content,
                            )
                            continue
                        try:
                            new_detail_id = await db.write_back_reconstruction(
                                self._pool,
                                memory_id=slot.row.memory_id,
                                prior_detail_id=slot.row.detail_id,
                                content=candidate,
                                basis=basis,
                                composed_key=slot.composed_key,
                            )
                        except Exception as exc:  # serve-only-persisted-text
                            degraded_reasons.append(
                                f"write-back failed for {slot.row.memory_id}: {exc}"
                            )
                            continue
                        if new_detail_id is None:  # concurrent writer won
                            degraded_reasons.append(
                                f"stale head for {slot.row.memory_id}; served head"
                            )
                            continue
                        write_backs += 1
                        slot.content = candidate
                        slot.detail_id = new_detail_id
                        slot.read_mode = "reconstructed"

        # --- assemble: any slot not served above serves its live head ------
        served: list[RetrievedMemory] = []
        for slot in slots:
            if slot.content is None:
                slot.content = slot.row.content
                slot.detail_id = slot.row.detail_id
                # A refused/degraded past-theta slot still reads honestly.
                slot.read_mode = (
                    _head_mode(slot.row) if slot.composed_key else "verbatim"
                )
            served.append(
                RetrievedMemory(
                    memory_id=slot.row.memory_id,
                    detail_id=slot.detail_id,
                    content=slot.content,
                    read_mode=slot.read_mode,
                    pinned=slot.row.pinned,
                    score=slot.score,
                    relevance=slot.relevance,
                    recency=slot.recency,
                    importance_norm=slot.importance_norm,
                    importance_raw=slot.importance_raw,
                )
            )
        return ServeOutcome(
            items=served,
            reconstruction_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            embed_tokens=embed_tokens,
            cache_hits=cache_hits,
            cache_misses=len(misses),
            write_backs=write_backs,
            drift_refusals=drift_refusals,
            identity_version=version,
            identity_bootstrapped=bootstrapped,
            degraded_reason="; ".join(degraded_reasons) if degraded_reasons else None,
        )
