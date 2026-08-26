"""session.py — the shared session-runner core beneath both drive surfaces.

The interactive REPL (app\\cli.py) and the synthetic load driver
(app\\load_driver.py) both drive sessions through this class, calling the
three built seams in-process (ingest, retrieval via the dialogue service,
dialogue) — one runner core, two thin callers, so the paths cannot drift
apart (spec-time ruling 2026-07-14). No timing or token accounting happens
here; the seams record it.

Scene state lives here, per the seam contract (cli-harness.md; re-shaped by
A1 2026-08-04 — the reputation snapshot and the recent-actions block left
with the behavior/reputation removal). The frozen scene state carries
`identity_version` (returned by the scene-boundary handler's server-side
recompile — the hybrid plumbing ruling, reconstruction build 2026-07-17) and
`scene_started_at` (the boundary's world time — the basis for every
text-affecting decay evaluation, so read-mode and served text cannot flip
mid-scene). Both pass through every turn.

`as_of` is the session's time-travel surface: when set, it rides retrieval's
age computation AND becomes the client_timestamp of `observe()` events, so a
whole session can be driven at an injected world time (tests\\CLAUDE.md).

Callers on Windows must run this under a SelectorEventLoop (psycopg's async
pool cannot run on the default ProactorEventLoop) — see app\\serve.py; both
drive surfaces use asyncio.run(..., loop_factory=asyncio.SelectorEventLoop).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, identity
from app.compiler import CompilerWorker
from app.concurrency import ModelCallGate
from app.config import Settings, load_settings
from app.db import build_pool
from app.deferred import DeferredWriteWorker
from app.dialogue import DialogueService
from app.dissonance import DissonanceService
from app.ingest import IngestService, UnknownAgentError
from app.nlp import warm_pipelines
from app.providers import Providers, build_providers
from app.reflection import ReflectionService, ReflectionWorker
from app.retrieval import RetrievalService
from app.schemas import (
    CorrectionRequest,
    CorrectionResult,
    DialogueTurnRequest,
    DialogueTurnResult,
    DiegeticCorrectionEvent,
    DiegeticCorrectionResult,
    IngestResult,
    ObserveEvent,
    PinResult,
    ReflectRequest,
    ReflectResult,
    SceneBoundaryEvent,
    SceneResult,
    WeightOverrides,
)


class SessionRunner:
    """One NPC session: frozen scene state + the seams. Build with `create`."""

    def __init__(
        self,
        *,
        pool: AsyncConnectionPool,
        owns_pool: bool,
        settings: Settings,
        ingest: IngestService,
        dialogue: DialogueService,
        agent_id: UUID,
        phase_tag: str,
        deferred: DeferredWriteWorker | None = None,
        reflection: ReflectionService | None = None,
        reflection_worker: ReflectionWorker | None = None,
        compiler_worker: CompilerWorker | None = None,
        dissonance: DissonanceService | None = None,
    ):
        self._pool = pool
        self._owns_pool = owns_pool
        self._settings = settings
        self._ingest = ingest
        self._dialogue = dialogue
        # The deferred-write worker (deferred-writes.md, 2026-08-12): the
        # REPL/driver construction site starts one too, so a deferred-mode
        # `:observe` enriches without the API process. `deferred.drain()` is
        # also the walkers' deterministic entry.
        self.deferred = deferred
        # The reflect seam + its worker (reflection.md, 2026-08-15): the
        # second construction site of the C1 lifecycle contract.
        # `reflection_worker.sweep()` is the walkers' deterministic entry;
        # the per-agent kill-switch (default 0.0) gates its auto-pull only.
        self._reflection = reflection
        self.reflection_worker = reflection_worker
        # The parameter-compiler worker (parameter-compiler.md, 2026-08-17):
        # the second construction site of the C1/C2 lifecycle contract, and
        # C3's ONLY scheduler (no endpoint by ruling).
        # `compiler_worker.sweep()` is the walkers' and `:compile`'s
        # deterministic entry; the per-agent kill-switch (default 0.0) gates
        # the component entirely.
        self.compiler_worker = compiler_worker
        # The dissonance seam (dissonance.md, C4 2026-08-17): the diegetic-
        # correction event's service behind `:confront` — synchronous, no
        # worker, nothing to start or stop.
        self._dissonance = dissonance
        self.agent_id = agent_id
        self.phase_tag = phase_tag  # passthrough label on observe events
        self.identity_version: str | None = None  # frozen at scene boundaries
        # The session's scene type (C3): set by scene(<type>), cleared by a
        # bare scene(); rides every turn request so compiled bundles for the
        # current scene's type multiply the prose-view weights.
        self.scene_type: str | None = None
        self.scene_started_at: datetime | None = None  # the scene basis
        self.as_of: datetime | None = None  # session time-travel override
        self.debug: bool = False  # rendering hint; inert to the seams
        # Caller-held loaded set + damper streak (mid-dialogue-gate.md fork 1,
        # 2026-07-19 — the third application of the caller-freezes-scene-state
        # contract, and caller-side ONLY: no scene-boundary server consumer).
        # None => the next turn is a loader; the loader turn's served IDs seed
        # the set; gate fetches append; scene() and session start reset both.
        self.loaded_memory_ids: list[UUID] | None = None
        self.gate_fruitless_streak: int = 0
        # Caller-held scene context (encoding-context build 2026-07-20 — the
        # fourth application of the caller-holds-scene-state contract): the
        # REPL's :context meta-command sets these; every turn passes them
        # through unreinterpreted; scene() resets them (a new scene is a new
        # place/cast until the caller says otherwise). All None => the
        # context term is skipped, scoring byte-identical to pre-context.
        self.context_location: str | None = None
        self.context_entities: list[str] | None = None
        self.context_event_time: datetime | None = None
        # Fork 5: the pre-serve callback — set by the REPL to print
        # "(reconstructing…)" DURING a blocking mid-scene serve; the future
        # Unity hook attaches here. None => nothing fires (the load driver).
        self.on_reconstruct: Callable[[], None] | None = None
        # The concurrency gate (C7) + ownership flag (the _owns_pool precedent):
        # set post-construction by create(); close() shuts down the executor
        # only when this runner built the providers bundle it rides on.
        self._gate: ModelCallGate | None = None
        self._owns_gate = False

    @classmethod
    async def create(
        cls,
        agent_id: UUID,
        *,
        settings: Settings | None = None,
        providers: Providers | None = None,
        pool: AsyncConnectionPool | None = None,
        phase_tag: str = "cli",
        warm_nlp: bool = False,
    ) -> SessionRunner:
        """Bootstrap the seams and freeze the scene-start state. Injection
        points (settings/providers/pool) exist for the load driver and the
        structural walker; the REPL uses the defaults. `warm_nlp` front-loads
        the spaCy/fastcoref model cost (the load driver warms so warm-up never
        lands inside a measured turn; the REPL pays it lazily on the first
        `:observe` instead)."""
        settings = settings if settings is not None else load_settings()
        owns_pool = pool is None
        if pool is None:
            pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
            await pool.open()
        owns_providers = providers is None
        providers = providers if providers is not None else build_providers(settings)
        if warm_nlp:
            await asyncio.to_thread(warm_pipelines)
        retrieval = RetrievalService(pool, providers, settings)
        ingest = IngestService(pool, providers, settings, retrieval)
        dialogue = DialogueService(pool, providers, settings, retrieval)
        deferred = DeferredWriteWorker(pool, providers, settings)
        deferred.start()
        reflection = ReflectionService(pool, providers, settings)
        reflection_worker = ReflectionWorker(pool, providers, settings)
        reflection_worker.start()
        compiler_worker = CompilerWorker(pool, providers, settings)
        compiler_worker.start()
        dissonance = DissonanceService(pool, providers, settings)
        runner = cls(
            pool=pool,
            owns_pool=owns_pool,
            settings=settings,
            ingest=ingest,
            dialogue=dialogue,
            agent_id=agent_id,
            phase_tag=phase_tag,
            deferred=deferred,
            reflection=reflection,
            reflection_worker=reflection_worker,
            compiler_worker=compiler_worker,
            dissonance=dissonance,
        )
        runner._gate = providers.gate
        runner._owns_gate = owns_providers
        # Session start is an implicit scene start: verify the agent loudly,
        # freeze the identity version (ensured directly — no boundary event is
        # emitted), and the scene basis.
        state = await db.fetch_dialogue_agent_state(pool, agent_id)
        if state is None:
            raise UnknownAgentError(f"unknown agent_id {agent_id}")
        version, _rendered, _created = await identity.ensure_identity_document(
            pool, agent_id, state.seed_identity
        )
        runner.identity_version = version
        runner.scene_started_at = runner._now()
        return runner

    def _now(self) -> datetime:
        return self.as_of if self.as_of is not None else datetime.now(timezone.utc)

    async def stream_utterance(
        self,
        text: str,
        *,
        k: int | None = None,
        weight_overrides: WeightOverrides | None = None,
    ) -> AsyncIterator[str | DialogueTurnResult]:
        """One dialogue turn through the streaming seam: yields prose chunks
        (str) as they arrive, then the terminal DialogueTurnResult (the REPL
        prints the chunks live). All scene state — context, identity version,
        basis time, loaded set, damper streak — rides frozen from the caller;
        the turn's bookkeeping is applied when the result arrives."""
        request = DialogueTurnRequest(
            agent_id=self.agent_id,
            utterance=text,
            k=k,
            as_of=self.as_of,
            location_name=self.context_location,
            entities=self.context_entities,
            event_time=self.context_event_time,
            identity_version=self.identity_version,
            scene_started_at=self.scene_started_at,
            loaded_memory_ids=self.loaded_memory_ids,
            gate_fruitless_streak=self.gate_fruitless_streak,
            weight_overrides=weight_overrides,
            scene_type=self.scene_type,
            debug=self.debug,
        )
        async for item in self._dialogue.run_dialogue_turn(
            request, on_reconstruct=self.on_reconstruct
        ):
            if isinstance(item, DialogueTurnResult):
                self._apply_turn_result(item)
            yield item

    async def utterance(
        self,
        text: str,
        *,
        k: int | None = None,
        weight_overrides: WeightOverrides | None = None,
    ) -> DialogueTurnResult:
        """One dialogue turn, drained to its terminal result — the
        non-streaming convenience the load driver, suite, and walkers use
        (first_word_ms rides in the instrumentation, so no chunk consumption is
        needed). The REPL uses stream_utterance instead."""
        result: DialogueTurnResult | None = None
        async for item in self.stream_utterance(
            text,
            k=k,
            weight_overrides=weight_overrides,
        ):
            if isinstance(item, DialogueTurnResult):
                result = item
        if result is None:  # the seam always yields a terminal result
            raise RuntimeError("dialogue turn produced no result")
        return result

    def _apply_turn_result(self, result: DialogueTurnResult) -> None:
        """Post-turn scene-state bookkeeping, in ONE place so streaming and
        drained callers cannot drift.

        Loaded-set bookkeeping (gate build 2026-07-19) is keyed on what the
        SERVER reports (`gate.evaluated`), not on what was sent — a
        gate-disabled agent's runner state stays coherent instead of stale:
        loader turn -> the served IDs become the loaded set, streak resets;
        gated fire -> this turn's gate-fetched IDs append, streak resets on a
        productive fetch and increments on a fruitless one; gated closed ->
        untouched."""
        gate_inst = result.instrumentation.retrieval.gate
        if not gate_inst.evaluated:
            self.loaded_memory_ids = [item.memory_id for item in result.items]
            self.gate_fruitless_streak = 0
        elif gate_inst.fired:
            self.loaded_memory_ids = (self.loaded_memory_ids or []) + [
                item.memory_id for item in result.items if item.gate_fetched
            ]
            self.gate_fruitless_streak = (
                self.gate_fruitless_streak + 1
                if gate_inst.fetched_new_count == 0
                else 0
            )

    async def observe(self, text: str) -> IngestResult:
        """One observe event through the write seam, at the session's time."""
        return await self._ingest.ingest_observation(
            ObserveEvent(
                agent_id=self.agent_id,
                observation_text=text,
                phase_tag=self.phase_tag,
                client_timestamp=self._now(),
                provenance="lived",
            )
        )

    async def scene(self, scene_type: str | None = None) -> SceneResult:
        """Scene boundary: emit the event (whose handler recompiles the
        identity document server-side and returns its version), then refresh
        the frozen scene state — the next scene sees the current identity
        version and a new basis; within the ending scene neither moved.
        Since C3 the type ALSO becomes session state: it rides every
        subsequent turn so the new scene's compiled bundles apply (a bare
        boundary clears it back to the default)."""
        result = await self._ingest.scene_boundary(
            SceneBoundaryEvent(
                agent_id=self.agent_id,
                client_timestamp=self._now(),
                scene_type=scene_type,
            )
        )
        self.identity_version = result.identity_version
        self.scene_started_at = self._now()
        self.scene_type = scene_type
        # Gate scene reset (caller-side only): next turn is a loader; the
        # damper's suppression dies with the scene.
        self.loaded_memory_ids = None
        self.gate_fruitless_streak = 0
        # Scene context dies with the scene too (encoding-context build):
        # a new scene is a new place/cast until :context says otherwise.
        self.context_location = None
        self.context_entities = None
        self.context_event_time = None
        return result

    async def pin(self, memory_id: UUID, pinned: bool) -> PinResult:
        return await self._ingest.set_pin(memory_id, pinned)

    async def correct(self, memory_id: UUID, content: str) -> CorrectionResult:
        """Authorial correction at the session's effective time — the
        operator states t_c, and under time travel that is the session's
        as_of (authorial-correction.md; immediate effect, mid-scene
        included)."""
        return await self._ingest.correct(
            memory_id,
            CorrectionRequest(content=content, client_timestamp=self._now()),
        )

    async def confront(
        self,
        memory_id: UUID,
        challenge_text: str,
        *,
        challenge_typology: str = "observed",
        challenge_weight: float | None = None,
    ) -> DiegeticCorrectionResult:
        """The diegetic-correction event at the session's effective time
        (dissonance.md; the :correct precedent — under time travel the
        confrontation happens at as_of). The `observed` default is REPL
        ergonomics only — the wire field stays required; the caller prints
        the decided verb and both sides of the decision (debug surface)."""
        if self._dissonance is None:
            raise RuntimeError("this runner was constructed without dissonance")
        return await self._dissonance.confront(
            DiegeticCorrectionEvent(
                agent_id=self.agent_id,
                memory_id=memory_id,
                challenge_text=challenge_text,
                challenge_typology=challenge_typology,
                challenge_weight=challenge_weight,
                client_timestamp=self._now(),
            )
        )

    async def reflect(self, consolidate: bool | None = None) -> ReflectResult:
        """The reflect verb at the session's effective time (reflection.md;
        the correction-verb precedent — under time travel the reflect event
        happens at as_of). Deliberately does NOT touch the frozen scene
        state: identity_version stays caller-frozen until the next scene
        boundary picks up the recompiled document (the integrator guidance —
        reflect at scene edges and the trim-eviction exposure window
        vanishes)."""
        if self._reflection is None:
            raise RuntimeError("this runner was constructed without reflection")
        return await self._reflection.reflect(
            self.agent_id,
            ReflectRequest(client_timestamp=self._now(), consolidate=consolidate),
        )

    async def compile(self) -> int:
        """One deterministic compile sweep (the REPL's `:compile`; the
        walkers' entry beside it). Sweep semantics by ruling: the per-agent
        kill-switch is honored, so an unconfigured agent is a visible
        no-op — the returned attempt count says so."""
        if self.compiler_worker is None:
            raise RuntimeError("this runner was constructed without a compiler")
        return await self.compiler_worker.sweep()

    async def close(self) -> None:
        if self.compiler_worker is not None:
            await self.compiler_worker.stop()
        if self.reflection_worker is not None:
            await self.reflection_worker.stop()
        if self.deferred is not None:
            await self.deferred.stop()
        if self._owns_gate and self._gate is not None:
            self._gate.shutdown()
        if self._owns_pool:
            await self._pool.close()
