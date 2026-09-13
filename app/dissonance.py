"""dissonance.py — the dissonance path + diegetic-correction event (C4).

The in-world confrontation verb (design truth architecture.md §8): the game fires
POST /v1/events/diegetic-correction at a target memory_id, the mechanical
formula decides defend-vs-update (ruling 1 — no model call decides), the
RECONSTRUCTION role writes the character's new telling in the decided
stance (ruling 2 — the role's second consumer; no new env var), and one
transaction extends the telling chain, records the confrontation in
`corrections`, and evicts the reconstruction cache. Tellings-only by
ruling 3: the fact chain never moves — the store keeps recording what was
experienced; the confrontation changes the story.

Reaction machinery only: automatic conflict discovery is CUT (2026-08-04).
No worker, no runs table (the `corrections` row is the persistent record;
instrumentation rides the response), no kill-switch (the event is
client-invoked — not sending it is the off state, consciously unlike the
`*_worker_enabled` flags). Event-driven writes are drift-budget-exempt and
outrank pin — both exemptions are the ABSENCE of code here, asserted
structurally by Set N and the walker.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from psycopg_pool import AsyncConnectionPool

from app import db, identity
from app.config import Settings, agent_knob
from app.ingest import (
    TYPOLOGY_FALLBACK,
    CorrectionConflictError,
    UnknownAgentError,
    UnknownMemoryError,
)
from app.providers import (
    MalformedOutputError,
    ProviderCallError,
    Providers,
    ReconstructionItem,
)
from app.schemas import DiegeticCorrectionEvent, DiegeticCorrectionResult

logger = logging.getLogger(__name__)


class DissonanceCallError(RuntimeError):
    """The retell call failed or returned unusable output — the whole verb
    fails loud (502) and NOTHING is written (the authorial all-or-nothing
    precedent: network calls run before the transaction)."""


# The agents.rigidity CHECK band, mirrored as a defensive clamp on the
# resolved value (the WEIGHT_MIN/MAX precedent: a structural bound, not a
# knob — the band itself is schema-ruled, migration 001).
RIGIDITY_MIN = 0.5
RIGIDITY_MAX = 2.0

_BLOCK_IDENTITY = "[identity]\n{document}"  # the reconstruction block shape

# Both task blocks keep the reconstruction role's output contract verbatim
# ("ONLY a JSON object mapping each memory_id to its retelling string") so
# the real provider's parse-and-salvage side is reused unchanged.
_TASK_DEFEND = (
    "[task]\n"
    "You are the reconstructive memory of a game character. The character "
    "was just confronted: someone challenged how they remember an event, "
    "and the challenge FAILED — the character keeps their story. Per item: "
    "'current_telling' is how the character tells the event; 'challenge' is "
    "the account they reject, with its evidence class in "
    "'challenge_typology'. Retell the event as the character now tells it, "
    "in first person, defending it: dismiss, reinterpret, or explain away "
    "the challenge while keeping the substance of the current telling. "
    "Return ONLY a JSON object mapping each memory_id to its retelling "
    "string. No other text."
)
_TASK_ACCEPT = (
    "[task]\n"
    "You are the reconstructive memory of a game character. The character "
    "was just confronted: someone challenged how they remember an event, "
    "and the challenge STUCK — the character grudgingly accepts the "
    "challenger's account. Per item: 'current_telling' is how the character "
    "used to tell the event; 'challenge' is the account they now accept, "
    "with its evidence class in 'challenge_typology'. Retell the event as "
    "the character now holds it, in first person: the accepted account, "
    "colored with resentment at having been corrected. Return ONLY a JSON "
    "object mapping each memory_id to its retelling string. No other text."
)


# ---------------------------------------------------------------------------
# Pure functions (walker-assertable without a database or model call)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DissonanceDecision:
    """The mechanical fork's outcome plus every resolved input — all of it
    rides the response so a structural test recomputes both sides by hand
    from fixture values."""

    verb: str
    resistance: float
    challenge: float
    importance_norm: float
    rigidity_effective: float
    typology_mult_memory: float
    typology_mult_challenge: float
    challenge_weight_effective: float


def typology_mult(typology: str | None, config: dict, settings: Settings) -> float:
    """The per-side evidence multiplier: knob `dissonance_typology_<value>`,
    per-agent overridable. ONE table serves both sides of the clash ("'I saw
    it' resists harder than 'I heard it,' on both sides"). A NULL memory-side
    typology (the un-enriched deferred window) resolves through the
    resolve_typology tail first — config `typology_default`, else the ingest
    fallback. Floored at zero: 0.0 is the per-side kill-switch shape. An
    unknown resolved literal fails loud (KeyError) — never a silent pick."""
    resolved = (
        typology
        if typology is not None
        else str(config.get("typology_default", TYPOLOGY_FALLBACK))
    )
    return max(0.0, agent_knob(config, f"dissonance_typology_{resolved}", settings))


def decide_dissonance(
    *,
    importance_raw: float | None,
    memory_typology: str | None,
    rigidity: float | None,
    challenge_typology: str,
    challenge_weight: float | None,
    config: dict,
    settings: Settings,
) -> DissonanceDecision:
    """§8's formula verbatim (ruling 1; ruling 7 declined a
    typology_confidence term): resistance = importance_norm x
    mult(memory typology) x rigidity; challenge = challenge_weight x
    mult(challenge typology); strict > updates, anything else defends —
    ties go to the memory. NULLs resolve exactly like their existing
    precedents: importance -> `importance_neutral` (the scoring-failed
    shape) then the read-path clamp [importance_norm_floor, 1.0]; rigidity
    -> `dissonance_rigidity_default` then the CHECK-band clamp; an omitted
    challenge_weight -> `dissonance_challenge_weight_default`, clamped
    [0, 1]."""
    # DB numerics arrive as Decimal (the agents.rigidity / importance_raw
    # column types) — coerce at this boundary so the formula stays float.
    raw = (
        float(importance_raw)
        if importance_raw is not None
        else agent_knob(config, "importance_neutral", settings)
    )
    floor = agent_knob(config, "importance_norm_floor", settings)
    importance_norm = min(max(raw, floor), 1.0)
    resolved_rigidity = (
        float(rigidity)
        if rigidity is not None
        else agent_knob(config, "dissonance_rigidity_default", settings)
    )
    rigidity_effective = min(max(resolved_rigidity, RIGIDITY_MIN), RIGIDITY_MAX)
    resolved_weight = (
        challenge_weight
        if challenge_weight is not None
        else agent_knob(config, "dissonance_challenge_weight_default", settings)
    )
    weight_effective = min(max(resolved_weight, 0.0), 1.0)
    mult_memory = typology_mult(memory_typology, config, settings)
    mult_challenge = typology_mult(challenge_typology, config, settings)
    resistance = importance_norm * mult_memory * rigidity_effective
    challenge = weight_effective * mult_challenge
    verb = "update_with_resentment" if challenge > resistance else "rationalization"
    return DissonanceDecision(
        verb=verb,
        resistance=resistance,
        challenge=challenge,
        importance_norm=importance_norm,
        rigidity_effective=rigidity_effective,
        typology_mult_memory=mult_memory,
        typology_mult_challenge=mult_challenge,
        challenge_weight_effective=weight_effective,
    )


def assemble_dissonance_prompt(
    identity_document: str,
    verb: str,
    *,
    memory_id: str,
    current_telling: str,
    challenge_text: str,
    challenge_typology: str,
) -> tuple[str, str, ReconstructionItem]:
    """(system_prompt, user_content, item) — byte-stable for identical
    inputs (the assemble_reconstruction_prompt contract; identity block
    omitted for an empty document, the NULL-seed rule). The task block forks
    on the DECIDED verb — the model writes the stance, it never chooses it.
    The item mirrors the payload structurally so the deterministic fake
    derives a stable, verb-distinct retelling (the system prompt differs per
    verb; challenge and telling ride the hashed fields); the real provider
    reads only the prompts."""
    blocks: list[str] = []
    if identity_document:
        blocks.append(_BLOCK_IDENTITY.format(document=identity_document))
    blocks.append(_TASK_ACCEPT if verb == "update_with_resentment" else _TASK_DEFEND)
    payload = [
        {
            "memory_id": memory_id,
            "current_telling": current_telling,
            "challenge": challenge_text,
            "challenge_typology": challenge_typology,
        }
    ]
    item = ReconstructionItem(
        memory_id=memory_id,
        gist=challenge_text,
        thinned_detail=challenge_typology,
        current_telling=current_telling,
    )
    return "\n\n".join(blocks), json.dumps(payload), item


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------


class DissonanceService:
    """The diegetic-correction seam (no worker — the event is synchronous,
    like observe). Order mirrors `IngestService.correct`: reads, the
    decision, the retell call, THEN the one transaction — every network
    call before it, all-or-nothing."""

    def __init__(
        self, pool: AsyncConnectionPool, providers: Providers, settings: Settings
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings

    async def confront(
        self, event: DiegeticCorrectionEvent
    ) -> DiegeticCorrectionResult:
        t0 = time.perf_counter()
        agent = await db.fetch_agent(self._pool, event.agent_id)
        if agent is None:
            raise UnknownAgentError(f"unknown agent {event.agent_id}")
        inputs = await db.fetch_memory_dissonance_inputs(self._pool, event.memory_id)
        if inputs is None or inputs["agent_id"] != event.agent_id:
            # A foreign memory 404s exactly like a missing one: from this
            # agent's world it does not exist.
            raise UnknownMemoryError(f"unknown memory {event.memory_id}")
        config = agent["config"]
        decision = decide_dissonance(
            importance_raw=inputs["importance_raw"],
            memory_typology=inputs["typology"],
            rigidity=agent["rigidity"],
            challenge_typology=event.challenge_typology,
            challenge_weight=event.challenge_weight,
            config=config,
            settings=self._settings,
        )
        _version, document, _created = await identity.ensure_identity_document(
            self._pool, event.agent_id, agent["seed_identity"]
        )
        system_prompt, user_content, item = assemble_dissonance_prompt(
            document,
            decision.verb,
            memory_id=str(event.memory_id),
            current_telling=inputs["head_content"],
            challenge_text=event.challenge_text,
            challenge_typology=event.challenge_typology,
        )
        t_call = time.perf_counter()
        try:
            call = await self._providers.gate.run(
                self._providers.reconstruction.reconstruct,
                system_prompt=system_prompt,
                user_content=user_content,
                items=[item],
            )
        except (ProviderCallError, MalformedOutputError) as exc:
            raise DissonanceCallError(f"dissonance retell failed: {exc}") from exc
        retell_ms = (time.perf_counter() - t_call) * 1000.0
        content = call.retellings.get(str(event.memory_id), "").strip()
        if not content:
            # Per-item salvage dropped the only item: for a single-item call
            # that IS a malformed call — all-or-nothing, never a partial verb.
            raise DissonanceCallError("dissonance retell returned no usable retelling")
        applied = await db.apply_diegetic_correction(
            self._pool,
            memory_id=event.memory_id,
            content=content,
            verb=decision.verb,
            valid_at=event.client_timestamp,
            source_event=event.source_event,
            expected_detail_id=event.expected_detail_id,
        )
        if applied == "unknown_memory":
            raise UnknownMemoryError(f"unknown memory {event.memory_id}")
        if applied == "stale_head":
            raise CorrectionConflictError(
                f"expected_detail_id no longer names the live head of {event.memory_id}"
            )
        return DiegeticCorrectionResult(
            memory_id=event.memory_id,
            agent_id=event.agent_id,
            verb=decision.verb,
            correction_id=applied.correction_id,
            detail_id=applied.detail_id,
            superseded_detail_id=applied.superseded_detail_id,
            pinned=inputs["pinned"],
            content=content,
            resistance=decision.resistance,
            challenge=decision.challenge,
            importance_norm=decision.importance_norm,
            rigidity_effective=decision.rigidity_effective,
            typology_mult_memory=decision.typology_mult_memory,
            typology_mult_challenge=decision.typology_mult_challenge,
            challenge_weight_effective=decision.challenge_weight_effective,
            evicted_cache_rows=applied.evicted_cache_rows,
            retell_ms=retell_ms,
            retell_input_tokens=call.input_tokens,
            retell_output_tokens=call.output_tokens,
            total_ms=(time.perf_counter() - t0) * 1000.0,
        )
