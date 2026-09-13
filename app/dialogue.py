"""dialogue.py — THE dialogue-turn service: the streaming prose seam.

All callers (the interactive REPL and the synthetic load driver via the
shared session-runner, and the stateless HTTP route `POST /v1/dialogue/turn`
in app\\api.py) sit on this module; none duplicates the timing or token
accounting recorded here (architecture.md §2: instrument at the seam). The
streaming SSE route (`POST /v1/dialogue/turn/stream`) iterates this SAME
generator, the no-rewrite payoff of the generator shape (architecture.md §9).

Pipeline per turn (weights-on-speech):
  resolve agent -> retrieval ONCE (retrieve_dialogue_init, byte-untouched)
  -> re-rank the served set with the resolved per-call weights
     (exponent-form on the product score, so all-1.0 reproduces the served
     ranking — the parity contract carried over from the split-brain build)
  -> assemble the prose prompt (identity + the weight-ranked memories + the
     pure-prose instruction) — the NPC's words are shaped by weights it is
     unaware of; on gated turns the [memories] block still renders the loaded
     set in the caller's append-only order (the byte-stable-prefix ruling,
     2026-07-19), so the weighted order is fully visible on loader turns and
     among gate-fetched items on gated turns
  -> the prose call (dialogue role) STREAMS pure prose — its first chunk is
     the product metric (first_word_ms); chunks yield through this seam
  -> yield the terminal DialogueTurnResult (`items` = the raw retrieval echo,
     `dialogue_view` = the weight-ranked view the prompt was built from).

A dialogue turn persists NOTHING: the sole in-place reputation write left
with the A1 re-shape, and directives were never stored. The NPC's own actions
are the game developer's domain and arrive as ordinary observes (the
game-authored action-observe contract, ruled 2026-07-21, standing).

`run_dialogue_turn` is an ASYNC GENERATOR (ruled seam shape): it yields prose
chunks (str) as they arrive, then yields the terminal DialogueTurnResult. The
sync streaming SDK is bridged into the async side through a worker thread + an
asyncio.Queue (the asyncio.to_thread + SelectorEventLoop precedent).

Scene state lives in the caller (identity version, scene basis, loaded set,
context) and rides on every request unreinterpreted.

Degradation ladder (never-blank-a-dialogue):
  - prose call fails BEFORE the first chunk -> fallback line, degraded flag.
  - prose stream DROPS mid-stream            -> KEEP the partial prose (it is
    non-blank) + degraded flag (ruled 2026-07-21).
  - retrieval degraded                       -> inherited in nested instrumentation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Callable
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, identity
from app.compiler import compose_bundle_weights, resolve_scene_type
from app.config import (
    WEIGHT_MAX,
    WEIGHT_MIN,
    Settings,
    agent_knob,
)
from app.ingest import UnknownAgentError
from app.providers import (
    ProseResult,
    Providers,
)
from app.reconstruction import UnknownIdentityVersionError
from app.retrieval import RetrievalService
from app.schemas import (
    DialogueInitRequest,
    DialogueTurnInstrumentation,
    DialogueTurnRequest,
    DialogueTurnResult,
    RetrievedMemory,
    ScoredRef,
    WeightOverrides,
)

logger = logging.getLogger(__name__)

# Never-blank fallback (build ruling 2026-07-15): a neutral beat, not a canned
# apology — overridable per agent via agents.config "dialogue_fallback_line".
DIALOGUE_FALLBACK_LINE = "..."

# Prompt blocks. Labeled, in spec order. Identical inputs assemble
# byte-identical prompts (memories arrive in a deterministic rank order).
_BLOCK_IDENTITY = "[identity]\n{seed}"
_BLOCK_MEMORIES_HEADER = "[memories]\nWhat you remember, most salient first:"
# The memory line carried its UUID ("- ({memory_id}) {content}") from the
# ruled 2026-07-15 prompt shape, when [output] was a JSON contract and the
# model cited memories back. A1 (2026-08-04) removed that contract; the F0
# audit (2026-08-26) established nothing consumes the in-prompt id — served
# IDs ride the payload from retrieval — so the id was stripped: fewer
# character-facing tokens, no UUID fragments to leak into spoken prose.
_MEMORY_LINE = "- {content}"
# Gated turns (mid-dialogue-gate.md, 2026-07-19): the [memories] block renders
# the scene's loaded set in the caller's append-only order (a byte-stable
# prefix — the structure prompt caching later attaches to), with this turn's
# gate fetches under a marked sub-header.
_MEMORY_RECOLLECTION_SUBHEADER = "Recalled just now, mid-conversation:"
# The prose call's output contract: PURE PROSE, no JSON envelope.
_BLOCK_PROSE_INSTRUCTION = (
    "[output]\nReply with ONLY your spoken line, in character. Prose only — no "
    "JSON, no labels, no surrounding quotation marks."
)


def _ms(seconds: float) -> float:
    return round(seconds * 1000.0, 2)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _render_memories(
    items: list[RetrievedMemory], loaded_order: list[UUID] | None
) -> str:
    """The [memories] block. `loaded_order` (gate build): loaded items in the
    caller's append-only order, then gate-fetched items under the recollection
    sub-header. None => plain payload rank order (since A1, the weight-ranked
    order the seam hands in)."""
    if loaded_order is None:
        ordered = list(items)
        fetched: list[RetrievedMemory] = []
    else:
        order_index = {memory_id: i for i, memory_id in enumerate(loaded_order)}
        loaded_items = [item for item in items if not item.gate_fetched]
        ordered = sorted(
            loaded_items,
            key=lambda item: order_index.get(item.memory_id, len(order_index)),
        )
        fetched = [item for item in items if item.gate_fetched]
    lines = [_MEMORY_LINE.format(content=item.content) for item in ordered]
    if fetched:
        lines.append(_MEMORY_RECOLLECTION_SUBHEADER)
        lines.extend(_MEMORY_LINE.format(content=item.content) for item in fetched)
    return _BLOCK_MEMORIES_HEADER + "\n" + "\n".join(lines)


def assemble_prose_prompt(
    identity_document: str | None,
    items: list[RetrievedMemory],
    *,
    loaded_order: list[UUID] | None = None,
) -> str:
    """The streaming prose call's system prompt: identity + the weight-ranked
    memories + the pure-prose instruction. Exposed so the walker can assert
    block order + byte-stability without a model call. The prose call sees no
    JSON contract — it speaks.

    Since the C2 build (reflection.md, ruled 2026-08-15) the identity block
    is the RENDERED IDENTITY DOCUMENT for the request's caller-frozen
    version, not the raw seed — speech sees formed beliefs. With zero
    reflections the document IS the seed verbatim, so the prompt is
    byte-identical to the pre-C2 shape (the parity contract the walkers
    assert); an empty document omits the block, exactly as an empty seed
    did."""
    blocks: list[str] = []
    if identity_document:
        blocks.append(_BLOCK_IDENTITY.format(seed=identity_document))
    if items:
        blocks.append(_render_memories(items, loaded_order))
    blocks.append(_BLOCK_PROSE_INSTRUCTION)
    return "\n\n".join(blocks)


def resolve_dialogue_weights(
    config: dict, overrides: WeightOverrides | None, settings: Settings
) -> tuple[float, float, float]:
    """The prose view's per-call weights: request field -> agents.config ->
    1.0 defaults, each clamped to [WEIGHT_MIN, WEIGHT_MAX]. Pure,
    module-level: the walker asserts it without a service."""

    def pick(key: str, override_value: float | None) -> float:
        if override_value is not None:
            value = float(override_value)
        else:
            value = agent_knob(config, key, settings)
        return _clamp(value, WEIGHT_MIN, WEIGHT_MAX)

    return (
        pick("weight_relevance", overrides.relevance if overrides else None),
        pick("weight_recency", overrides.recency if overrides else None),
        pick("weight_importance", overrides.importance if overrides else None),
    )


def weighted_score(
    item: RetrievedMemory, w_rel: float, w_rec: float, w_imp: float
) -> float:
    """Exponent-form re-weighting of an already-scored served item: start from
    its served score (which folds in the encoding-context factor) and adjust
    each component by its weight minus one. At all-1.0 the exponents are zero,
    so weighted_score == item.score — the parity contract. A zero base
    component is skipped (pow(0, negative) is undefined), never a divide."""
    score = item.score
    if item.relevance is not None and item.relevance > 0.0:
        score *= item.relevance ** (w_rel - 1.0)
    if item.recency > 0.0:
        score *= item.recency ** (w_rec - 1.0)
    if item.importance_norm > 0.0:
        score *= item.importance_norm ** (w_imp - 1.0)
    return score


def rank_dialogue_view(
    items: list[RetrievedMemory], weights: tuple[float, float, float]
) -> list[tuple[float, RetrievedMemory]]:
    """The prose view: the SAME served items re-scored with the resolved
    weights, in deterministic order (ties break on memory_id — the retrieval
    _sort_scored convention, so identical inputs reproduce byte-identically).
    Membership never changes — weights re-rank the served set, they cannot
    pull in a memory the top-k excluded (ruled at spec, 2026-08-04)."""
    w_rel, w_rec, w_imp = weights
    scored = [(weighted_score(item, w_rel, w_rec, w_imp), item) for item in items]
    scored.sort(key=lambda entry: (-entry[0], entry[1].memory_id))
    return scored


def _turn_cost_usd(
    prices: dict[str, float],
    prose_in: int,
    prose_out: int,
    embed_tokens: int,
) -> float | None:
    """USD per turn, only from the prices actually configured; None when
    nothing is priced (tokens are the unconditional unit — ruled 2026-07-15)."""
    total = 0.0
    priced = False
    if "dialogue_in" in prices and "dialogue_out" in prices:
        total += (
            prose_in * prices["dialogue_in"] + prose_out * prices["dialogue_out"]
        ) / 1e6
        priced = True
    if "embedding" in prices:
        total += embed_tokens * prices["embedding"] / 1e6
        priced = True
    return round(total, 6) if priced else None


class DialogueService:
    """One instance per process; both callers share it via the session-runner."""

    def __init__(
        self,
        pool: AsyncConnectionPool,
        providers: Providers,
        settings: Settings,
        retrieval: RetrievalService,
    ):
        self._pool = pool
        self._providers = providers
        self._settings = settings
        self._retrieval = retrieval

    async def run_dialogue_turn(
        self,
        request: DialogueTurnRequest,
        *,
        on_reconstruct: Callable[[], None] | None = None,
    ) -> AsyncIterator[str | DialogueTurnResult]:
        """The streaming dialogue seam (async generator): yields prose chunks
        (str) as they arrive, then the terminal DialogueTurnResult.
        Non-streaming callers drain to the terminal item (session.utterance);
        the REPL yields the chunks live (session.stream_utterance)."""
        t_total = time.perf_counter()

        # --- retrieval: the built read seam, run ONCE, passed through
        # unreinterpreted (scene state + gate loaded set + on_reconstruct).
        # Started FIRST as a task (F0 overlap, 2026-08-26): the agent-state,
        # bundle, and identity fetches below run under the retrieval leg
        # (dominated by the query embed), since none of them consumes
        # retrieval output. Concurrent by design — anything that DOES consume
        # retrieval output moves below the `await retrieval_task`.
        retrieval_task = asyncio.create_task(
            self._retrieval.retrieve_dialogue_init(
                DialogueInitRequest(
                    agent_id=request.agent_id,
                    query_text=request.utterance,
                    k=request.k,
                    as_of=request.as_of,
                    location_name=request.location_name,
                    entities=request.entities,
                    event_time=request.event_time,
                    identity_version=request.identity_version,
                    scene_started_at=request.scene_started_at,
                    loaded_memory_ids=request.loaded_memory_ids,
                    gate_fruitless_streak=request.gate_fruitless_streak,
                ),
                on_reconstruct=on_reconstruct,
            )
        )
        tasks: list[asyncio.Task] = [retrieval_task]
        try:
            state = await db.fetch_dialogue_agent_state(self._pool, request.agent_id)
            if state is None:
                raise UnknownAgentError(f"unknown agent_id {request.agent_id}")
            config = state.config

            # --- compiled parameters (parameter-compiler.md, C3 2026-08-17):
            # resolve the scene type (unknown -> the default bundle + a flag,
            # log-and-continue by ruling), fetch the newest bundle per in-window
            # live belief for exactly that type, and compose multiplier products
            # over the resolved base — clamped back into [WEIGHT_MIN, WEIGHT_MAX].
            # Zero bundles compose to the identity, so a bundle-free turn is
            # byte-identical to the pre-C3 seam (the parity contract).
            scene_type_resolved, scene_type_unknown = resolve_scene_type(
                config, request.scene_type
            )
            if scene_type_unknown:
                logger.warning(
                    "unknown scene_type %r for agent %s; serving the default bundle",
                    request.scene_type,
                    request.agent_id,
                )

            async def _timed_bundles() -> tuple[list, float]:
                # bundle_fetch_ms keeps its meaning: this await's own duration.
                t_bundles = time.perf_counter()
                rows = await db.fetch_dialogue_bundles(
                    self._pool,
                    request.agent_id,
                    scene_type=scene_type_resolved,
                    window_k=int(
                        agent_knob(config, "compiler_window_k", self._settings)
                    ),
                )
                return rows, _ms(time.perf_counter() - t_bundles)

            # --- the identity block rides the RENDERED DOCUMENT (reflection.md,
            # ruled 2026-08-15 — the raw-seed asymmetry closed at the C2 build):
            # resolved exactly like reconstruction's (present -> fetch, unknown ->
            # UnknownIdentityVersionError = 422 at both turn routes; absent ->
            # lazy ensure). Runs concurrently with retrieval's own resolution of
            # the same version (F0 overlap); retrieval is awaited first, so a
            # caller-passed unknown version still surfaces as retrieval's error,
            # and this fetch can only miss on a store mutated mid-request — the
            # same loud contract error, with the two resolutions now near-
            # simultaneous instead of a retrieval leg apart.
            async def _resolve_identity() -> str | None:
                if request.identity_version is not None:
                    document = await db.fetch_identity_document(
                        self._pool, request.agent_id, request.identity_version
                    )
                    if document is None:
                        raise UnknownIdentityVersionError(
                            f"unknown identity_version "
                            f"{request.identity_version!r} "
                            f"for agent {request.agent_id}"
                        )
                    return document
                (
                    _version,
                    document,
                    _created,
                ) = await identity.ensure_identity_document(
                    self._pool, request.agent_id, state.seed_identity
                )
                return document

            bundles_task = asyncio.create_task(_timed_bundles())
            tasks.append(bundles_task)
            identity_task = asyncio.create_task(_resolve_identity())
            tasks.append(identity_task)

            retrieval = await retrieval_task

            # --- weights-on-speech (A1 re-shape, 2026-08-04): re-rank the served
            # set with the resolved per-call weights; the re-ranked list feeds the
            # prose prompt and is reported as dialogue_view. `items` stays the raw
            # retrieval echo, so at all-1.0 weights dialogue_view == its (id,
            # score) projection — the parity contract.
            weights = resolve_dialogue_weights(
                config, request.weight_overrides, self._settings
            )

            bundles, bundle_fetch_ms = await bundles_task
            effective_weights, bundle_products = compose_bundle_weights(
                weights, bundles
            )
            ranked = rank_dialogue_view(retrieval.items, effective_weights)
            ranked_items = [item for _score, item in ranked]
            dialogue_view = [
                ScoredRef(memory_id=item.memory_id, score=score)
                for score, item in ranked
            ]

            # The append-only prompt order applies only when the gate actually
            # evaluated (a gate-disabled agent with loaded IDs took the loader path
            # — its prose prompt renders the weight-ranked order directly).
            loaded_order = (
                request.loaded_memory_ids
                if retrieval.instrumentation.gate.evaluated
                else None
            )

            identity_document = await identity_task
        except BaseException:
            # A failed leg must not leak its siblings: cancel, then drain so
            # every task's exception is retrieved and every pool connection
            # returns before the original error propagates to the route.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        prose_prompt = assemble_prose_prompt(
            identity_document,
            ranked_items,
            loaded_order=loaded_order,
        )

        loop = asyncio.get_running_loop()
        gate = self._providers.gate

        # Prose leg: run the sync stream generator in a worker thread, bridge
        # its chunks onto an asyncio.Queue, yield them from this async
        # generator. StopIteration.value carries the ProseResult (tokens +
        # provider-side first-token latency); an exception mid-iteration is a
        # mid-stream drop (partial chunks already yielded), before any chunk a
        # pre-first-chunk failure.
        queue: asyncio.Queue = asyncio.Queue()

        def _produce() -> None:
            gen = self._providers.dialogue.stream_prose(
                system_prompt=prose_prompt, utterance=request.utterance
            )
            try:
                while True:
                    try:
                        chunk = next(gen)
                    except StopIteration as stop:
                        loop.call_soon_threadsafe(
                            queue.put_nowait, ("done", stop.value)
                        )
                        return
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
            except Exception as exc:  # noqa: BLE001 — signalled to the seam
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))

        # Hold one concurrency slot for the whole stream (the C7 cap): a
        # streaming NPC occupies a slot until its last chunk. gate_wait_ms is
        # the queue time before the slot opened — perceived_first_word_ms folds
        # it into the honest end-to-end TTFT. Released on EVERY exit, including a
        # consumer that abandons the generator (GeneratorExit at the yield).
        gate_wait_ms = await gate.acquire()
        content_parts: list[str] = []
        prose_result: ProseResult | None = None
        prose_error: Exception | None = None
        first_word_ms = 0.0
        perceived_first_word_ms = 0.0
        t_prose = time.perf_counter()
        try:
            producer = loop.run_in_executor(gate.executor, _produce)
            while True:
                kind, payload = await queue.get()
                if kind == "chunk":
                    if not content_parts:
                        now = time.perf_counter()
                        first_word_ms = _ms(now - t_prose)
                        # Perceived TTFT: same instant, clocked from turn start —
                        # retrieval- AND gate-wait-inclusive (the honest metric).
                        perceived_first_word_ms = _ms(now - t_total)
                    content_parts.append(payload)
                    yield payload
                elif kind == "done":
                    prose_result = payload
                    break
                else:  # "error"
                    prose_error = payload
                    break
            await producer  # let the worker thread finish cleanly
        finally:
            gate.release()
        prose_stream_ms = _ms(time.perf_counter() - t_prose)

        # --- content: never-blank-a-dialogue (keep-partial on mid-drop) --
        prose_text = "".join(content_parts)
        degraded_reason: str | None = None
        if prose_error is not None:
            degraded_reason = (
                f"prose stream dropped mid-stream: {prose_error}"
                if content_parts
                else f"prose call failed: {prose_error}"
            )
        if prose_text:
            content = prose_text  # full, or partial kept (ruled 2026-07-21)
        else:
            content = str(config.get("dialogue_fallback_line", DIALOGUE_FALLBACK_LINE))
            if degraded_reason is None:
                degraded_reason = "prose produced no text"
            logger.warning(
                "never-blank fallback served for agent %s: %s",
                request.agent_id,
                degraded_reason,
            )

        prose_in = prose_result.input_tokens if prose_result else 0
        prose_out = prose_result.output_tokens if prose_result else 0

        yield DialogueTurnResult(
            agent_id=request.agent_id,
            content=content,
            items=retrieval.items,
            dialogue_view=dialogue_view,
            instrumentation=DialogueTurnInstrumentation(
                retrieval=retrieval.instrumentation,
                sonnet_ms=prose_stream_ms,
                sonnet_first_token_ms=first_word_ms,
                total_ms=_ms(time.perf_counter() - t_total),
                sonnet_input_tokens=prose_in,
                sonnet_output_tokens=prose_out,
                first_word_ms=first_word_ms,
                perceived_first_word_ms=perceived_first_word_ms,
                gate_wait_ms=gate_wait_ms,
                prose_stream_ms=prose_stream_ms,
                scene_type_resolved=scene_type_resolved,
                scene_type_unknown=scene_type_unknown,
                bundle_w_relevance=bundle_products[0],
                bundle_w_recency=bundle_products[1],
                bundle_w_importance=bundle_products[2],
                bundle_reflection_ids=[b.reflection_id for b in bundles],
                bundle_fetch_ms=bundle_fetch_ms,
                cost_usd=_turn_cost_usd(
                    self._settings.prices,
                    prose_in,
                    prose_out,
                    retrieval.instrumentation.embedding_tokens,
                ),
                degraded=degraded_reason is not None,
                degraded_reason=degraded_reason,
            ),
        )
