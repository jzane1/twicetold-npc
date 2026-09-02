"""api.py — thin FastAPI routes over the ingest and retrieval services.

Pass-through by ruling (2026-07-13, mirrored for reads 2026-07-14): for one
call, the route's JSON response is exactly the serialization of the result
the service returned — the route adds and drops nothing, and records no
timing or tokens of its own (the seams are `app\\ingest.py` and
`app\\retrieval.py`).

    PowerShell:  python -m app.serve
(not bare `uvicorn app.api:app` — see app\\serve.py for the Windows
event-loop constraint)
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager
from uuid import UUID

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.compiler import CompilerWorker
from app.config import load_settings
from app.db import build_pool
from app.deferred import DeferredWriteWorker
from app.dialogue import DialogueService
from app.dissonance import DissonanceCallError, DissonanceService
from app.ingest import (
    CorrectionConflictError,
    CorrectionEmbedFailedError,
    CorrectionNlpFailedError,
    IngestService,
    UnknownAgentError,
    UnknownMemoryError,
)
from app.nlp import warm_pipelines
from app.providers import build_providers
from app.reconstruction import UnknownIdentityVersionError
from app.reflection import (
    ReflectionCallError,
    ReflectionFloorError,
    ReflectionService,
    ReflectionWorker,
)
from app.retrieval import RetrievalService
from app.schemas import (
    AgentMemoriesResult,
    AgentStateResult,
    CorrectionRequest,
    CorrectionResult,
    CreateAgentRequest,
    CreateAgentResult,
    DiegeticCorrectionEvent,
    DiegeticCorrectionResult,
    DialogueInitRequest,
    DialogueTurnRequest,
    DialogueTurnResult,
    IngestResult,
    LedgerTurnEntry,
    LedgerTurnsResult,
    MemoryChainResult,
    ObserveEvent,
    PinRequest,
    PinResult,
    PurgeResult,
    ReconstructionMetricsResult,
    ReflectRequest,
    ReflectResult,
    RetrievalResult,
    SceneBoundaryEvent,
    SceneResult,
)

# Running SSE pump tasks hold a reference here so a client disconnect can
# never garbage-collect a mid-turn task — the turn always completes
# server-side (coherent instrumentation and reconstruction write-backs, never
# a half-run seam).
_stream_tasks: set[asyncio.Task] = set()

# The Ledger's live turn feed (E2, ruled 2026-08-19): both dialogue routes
# tee their terminal DialogueTurnResult here, and GET /v1/ledger/turns serves
# it. An explicit, ruled carve-out to the pass-through contract above — the
# response stays byte-identical, but the route now records the result into
# PROCESS MEMORY (never the DB; a dialogue turn still persists nothing).
# Module-global like _stream_tasks, not app.state: the route-contract tests
# drive the app without lifespan. The cap is a demo inspector surface, not
# integrator config.
_TURN_FEED_CAP = 256
_turn_feed: deque[LedgerTurnEntry] = deque(maxlen=_TURN_FEED_CAP)
_turn_seq = 0


def _tee_turn(result: DialogueTurnResult) -> None:
    global _turn_seq
    _turn_seq += 1
    _turn_feed.append(LedgerTurnEntry(seq=_turn_seq, result=result))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings = load_settings()
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    await asyncio.to_thread(warm_pipelines)  # model load is startup cost
    providers = build_providers(settings)
    app.state.retrieval = RetrievalService(pool, providers, settings)
    app.state.service = IngestService(pool, providers, settings, app.state.retrieval)
    app.state.dialogue = DialogueService(pool, providers, settings, app.state.retrieval)
    # The dissonance seam (dissonance.md, the C4 rulings 2026-08-17): the
    # diegetic-correction event's service — synchronous, no worker, nothing
    # to start or stop.
    app.state.dissonance = DissonanceService(pool, providers, settings)
    # The deferred-write worker (deferred-writes.md, ruled 2026-08-12): one
    # per process, stopped BEFORE the pool closes. It drains pending rows
    # regardless of the deferral kill-switch, so flipping the knob off never
    # strands a row.
    app.state.deferred = DeferredWriteWorker(pool, providers, settings)
    app.state.deferred.start()
    # The reflection seam + its worker (reflection.md, ruled 2026-08-15):
    # the C1 lifecycle contract verbatim — one worker per process, stopped
    # BEFORE the pool closes. The per-agent reflection_worker_enabled knob
    # (default 0.0) gates its auto-pull only; the reflect route is always
    # live.
    app.state.reflection = ReflectionService(pool, providers, settings)
    app.state.reflection_worker = ReflectionWorker(pool, providers, settings)
    app.state.reflection_worker.start()
    # The parameter-compiler worker (parameter-compiler.md, ruled
    # 2026-08-17): the same lifecycle contract, and C3's ONLY scheduler —
    # no compile route exists. The per-agent compiler_worker_enabled knob
    # (default 0.0) gates the component entirely.
    app.state.compiler_worker = CompilerWorker(pool, providers, settings)
    app.state.compiler_worker.start()
    try:
        yield
    finally:
        await app.state.compiler_worker.stop()
        await app.state.reflection_worker.stop()
        await app.state.deferred.stop()
        providers.gate.shutdown()
        await pool.close()


app = FastAPI(title="twicetold-npc API", version="1", lifespan=_lifespan)


@app.post("/v1/dialogue/init", response_model=RetrievalResult)
async def dialogue_init(request: DialogueInitRequest) -> RetrievalResult:
    """Dialogue-init retrieval (read-path.md wire shape, ruled 2026-07-14) —
    since the reconstruction build (2026-07-17) this endpoint also serves the
    pre-warm: past-theta items reconstruct (write-back + cache) before the
    response returns. An unknown caller-passed identity_version is a broken
    contract, not a flaky model -> 422 (the unknown-agent 404 precedent)."""
    try:
        return await app.state.retrieval.retrieve_dialogue_init(request)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownIdentityVersionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/dialogue/turn", response_model=DialogueTurnResult)
async def dialogue_turn(request: DialogueTurnRequest) -> DialogueTurnResult:
    """One dialogue turn over HTTP (the audit's #1 gap, built 2026-07-23) —
    the Unity/C# front door to the dialogue seam. STATELESS: all scene
    state (identity version, scene basis, loaded set, context) rides on the
    request, and the runner bookkeeping (`session._apply_turn_result`) is the
    CLIENT'S job — the C# NpcSession ports it. Non-streaming: drains
    `run_dialogue_turn`'s async
    generator to the terminal result (first_word_ms/perceived_first_word_ms
    ride in the instrumentation, so no chunk consumption is needed); the SSE
    route below iterates the SAME generator — no rewrite, as designed.
    `on_reconstruct` stays None here (no during-wait signal without SSE; the
    result's post-hoc reconstruction fields carry it). Pass-through by ruling:
    the response is exactly the seam result's serialization."""
    try:
        result: DialogueTurnResult | None = None
        async for item in app.state.dialogue.run_dialogue_turn(request):
            if isinstance(item, DialogueTurnResult):
                result = item
        if result is None:  # the seam always yields a terminal result
            raise RuntimeError("dialogue turn produced no result")
        _tee_turn(result)
        return result
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownIdentityVersionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/dialogue/turn/stream")
async def dialogue_turn_stream(request: DialogueTurnRequest) -> StreamingResponse:
    """The SSE turn route (unity-client.md fork 1, ruled 2026-07-27) — the
    streaming twin of /v1/dialogue/turn, iterating the SAME async-generator
    seam (the 2026-07-23 no-rewrite payoff). Wire shape, text/event-stream:
    `event: chunk` per prose str (JSON-encoded so newlines survive SSE
    framing), optional `event: reconstructing` fired at the pre-serve
    callback DURING a blocking mid-scene retelling (the REPL's
    "(reconstructing…)" over HTTP), then `event: result` carrying the
    terminal DialogueTurnResult JSON — byte-identical serialization to the
    non-streaming route's body (pass-through by ruling). The seam runs in a
    pump task bridged through an asyncio.Queue because the callback fires
    inside the awaited chain; the FIRST queue item is awaited before the
    response starts, so UnknownAgentError → 404 / UnknownIdentityVersionError
    → 422 still map to real status codes. After streaming begins a failure
    becomes `event: error` (a 200 stream cannot change its status). A client
    disconnect never aborts the turn server-side."""
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    async def _pump() -> None:
        try:
            async for item in app.state.dialogue.run_dialogue_turn(
                request,
                on_reconstruct=lambda: queue.put_nowait(("reconstructing", None)),
            ):
                if isinstance(item, DialogueTurnResult):
                    _tee_turn(item)  # the pump completes even on disconnect
                    queue.put_nowait(("result", item))
                else:
                    queue.put_nowait(("chunk", item))
            queue.put_nowait(("done", None))
        except Exception as exc:  # forwarded: mapped pre-stream, event after
            queue.put_nowait(("error", exc))

    task = asyncio.create_task(_pump())
    _stream_tasks.add(task)
    task.add_done_callback(_stream_tasks.discard)

    first = await queue.get()
    if first[0] == "error":
        exc = first[1]
        if isinstance(exc, UnknownAgentError):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if isinstance(exc, UnknownIdentityVersionError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise exc  # type: ignore[misc]  # a genuine 500

    def _sse(name: str, data: str) -> str:
        return f"event: {name}\ndata: {data}\n\n"

    async def _events():
        item = first
        while True:
            kind, payload = item
            if kind == "chunk":
                yield _sse("chunk", json.dumps(payload))
            elif kind == "reconstructing":
                yield _sse("reconstructing", "{}")
            elif kind == "result":
                yield _sse("result", payload.model_dump_json())
            elif kind == "error":
                yield _sse("error", json.dumps(str(payload)))
                break
            else:  # "done" — the terminal result already streamed
                break
            item = await queue.get()

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/v1/events/observe", response_model=IngestResult)
async def observe(event: ObserveEvent) -> IngestResult:
    try:
        return await app.state.service.ingest_observation(event)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/events/scene-boundary", response_model=SceneResult)
async def scene_boundary(event: SceneBoundaryEvent) -> SceneResult:
    try:
        return await app.state.service.scene_boundary(event)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/events/diegetic-correction", response_model=DiegeticCorrectionResult)
async def diegetic_correction(
    event: DiegeticCorrectionEvent,
) -> DiegeticCorrectionResult:
    """The in-world confrontation (dissonance.md; the C4 rulings
    2026-08-17) — the third diegetic event: references a target memory_id
    (automatic discovery is CUT), decides defend-vs-update mechanically,
    and EXTENDS the telling chain through the dissonance path — the
    chain-preserving sibling of the authorial replace-model verb.
    Fail-loud: 404 unknown agent / unknown-or-foreign memory · 409 stale
    expected_detail_id · 422 malformed request (pydantic; naive timestamp;
    unknown typology literal) · 502 retell failure with nothing written
    (the all-or-nothing correction precedent). Pass-through by ruling."""
    try:
        return await app.state.dissonance.confront(event)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CorrectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DissonanceCallError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.put("/v1/memories/{memory_id}/pin", response_model=PinResult)
async def set_pin(memory_id: UUID, body: PinRequest) -> PinResult:
    try:
        return await app.state.service.set_pin(memory_id, body.pinned)
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/v1/memories/{memory_id}", response_model=PurgeResult)
async def purge_memory(memory_id: UUID) -> PurgeResult:
    """The purge verb (C6, ruled 2026-08-18): the sole sanctioned content
    DELETE — the GDPR release-blocker. Hard-removes one memory and everything
    beneath it (both chains, gist spans, corrections, caches, enrichment runs)
    in one transaction, returning the per-table counts; reflections derived
    from it survive by design (purge honesty). Per-memory and no-guard by
    ruling (the integrator owns retention safety). 404 on unknown; 422 on a
    malformed id (FastAPI); pass-through by the api.py contract."""
    try:
        return await app.state.service.purge_memory(memory_id)
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/memories/{memory_id}/correction", response_model=CorrectionResult)
async def correct_memory(memory_id: UUID, body: CorrectionRequest) -> CorrectionResult:
    """Authorial correction (authorial-correction.md; fact-following since
    the fact-level build): memory-scoped operator verb — /v1/events/* stays
    diegetic. Fail-loud: 404 unknown memory, 409 stale expected_detail_id,
    422 invalid content, 502 embed or NER failure with nothing written (the
    all-or-nothing correction rulings, 2026-07-18 / 2026-07-19); nothing
    partial. (The observe-path escalation call soft-degrades since 2026-07-22 —
    it no longer hard-stops; these correction paths stay fail-loud.)"""
    try:
        return await app.state.service.correct(memory_id, body)
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CorrectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CorrectionEmbedFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CorrectionNlpFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/agents", response_model=CreateAgentResult)
async def create_agent(request: CreateAgentRequest) -> CreateAgentResult:
    """Agent provisioning (unity-client.md fork 2, ruled 2026-07-27) — the
    integrator's minute-one verb; before this route the demo agent was
    hand-SQL. UUID minted server-side (stack constant); no model calls; the
    identity document compiles at the first scene boundary / session start
    as before. Pass-through by ruling."""
    return await app.state.service.create_agent(request)


@app.post("/v1/agents/{agent_id}/reflect", response_model=ReflectResult)
async def reflect(agent_id: UUID, body: ReflectRequest) -> ReflectResult:
    """The reflect verb (reflection.md; the C2 rulings 2026-08-15): an
    agent-scoped operator/integrator verb — /v1/events/* stays diegetic
    (the correction-route precedent). Stateless like every route. Fail-loud
    ladder: 404 unknown agent · 409 below the episode floor · 422 malformed
    request (pydantic; naive timestamp) · 502 reflect-call failure /
    malformed output / all-ungrounded — nothing written on any of these.
    ConfigError (real mode without TWICETOLD_MODEL_REFLECTION) propagates
    loud at first use, the judge shape. Pass-through by ruling: the
    response is exactly the seam result's serialization — sampled and
    cited ids ride as grounding evidence, unscored by nature (the sampling
    draw is not the retrieval seam)."""
    try:
        return await app.state.reflection.reflect(agent_id, body)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReflectionFloorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReflectionCallError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/memories/{memory_id}/chain", response_model=MemoryChainResult)
async def memory_chain(memory_id: UUID) -> MemoryChainResult:
    """The Ledger's ground-truth-vs-telling read (unity-client.md fork 3,
    ruled 2026-07-27): the immutable observation beside BOTH version chains
    (superseded rows present — greyed client-side, never dropped) + gist
    spans. Read-only and unscored: no retrieval ran, so no scores exist;
    IDs + structured fields on every row keep the read-payload discipline.
    404 on unknown memory (the pin-route precedent)."""
    try:
        return await app.state.retrieval.memory_chain(memory_id)
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/v1/memories/{memory_id}/reconstruction-metrics",
    response_model=ReconstructionMetricsResult,
)
async def reconstruction_metrics(memory_id: UUID) -> ReconstructionMetricsResult:
    """The judge-free metric read (eval-harness.md stage 1, ruled
    2026-07-29): gist-precision / detail-recall / fabrication / keyword
    retention against the live telling head, The Ledger's on-screen numbers.
    Runs no retrieval (no scores exist — the invariant does not bind) and
    performs ZERO writes; the two inspector reads' unscored-by-contract
    wording is untouched. 404 on unknown memory (the /chain shape);
    pass-through by ruling."""
    try:
        return await app.state.retrieval.reconstruction_metrics(memory_id)
    except UnknownMemoryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


_LEDGER_PATH = Path(__file__).resolve().parent.parent / "ledger" / "index.html"


@app.get("/ledger", include_in_schema=False)
async def ledger_page() -> FileResponse:
    """The Ledger (unity-client.md stage 3, ruled 2026-07-27) — the static
    designer-facing inspector page, served BY the API so it ships with the
    service and shares the origin of the two read routes it polls (no CORS
    surface, no second server). The page itself is `ledger\\index.html` —
    vanilla JS, no build step (fork 6)."""
    return FileResponse(_LEDGER_PATH, media_type="text/html")


@app.get("/v1/ledger/turns", include_in_schema=False)
async def ledger_turns(after: int = Query(default=0, ge=0)) -> LedgerTurnsResult:
    """The Ledger's live turn feed (E2, ruled 2026-08-19): the teed
    DialogueTurnResults newer than the caller's `after` cursor, oldest
    first, each the turn response's serialization verbatim (IDs + scores —
    the retrieval-read invariant holds). In-memory and process-local by the
    same ruling: a restart starts empty, and nothing here touches the DB.
    Schema-hidden like /ledger — a demo inspector surface, not integrator
    API. `last_seq` is the next poll's cursor (equal to `after` when no
    newer entries exist)."""
    entries = [entry for entry in _turn_feed if entry.seq > after]
    last_seq = entries[-1].seq if entries else max(_turn_seq, after)
    return LedgerTurnsResult(entries=entries, last_seq=last_seq)


@app.get("/v1/agents/{agent_id}/memories", response_model=AgentMemoriesResult)
async def agent_memories(
    agent_id: UUID, limit: int = Query(default=100, ge=1, le=1000)
) -> AgentMemoriesResult:
    """The Ledger's per-agent index (unity-client.md fork 3): each memory
    beside its live telling head, newest valid_at first; `limit` is a caller
    argument (the k precedent), never a config knob. 404 on unknown agent."""
    try:
        return await app.state.retrieval.agent_memories(agent_id, limit)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/agents/{agent_id}/state", response_model=AgentStateResult)
async def agent_state(
    agent_id: UUID, runs_limit: int = Query(default=100, ge=1, le=1000)
) -> AgentStateResult:
    """The agent-state read (C5, ruled 2026-08-17): the composed runtime
    snapshot — the stored row (config as stored, defaults never merged),
    the current identity version, the reflection-pressure gauge
    (computed-never-stored), live beliefs in the compiler-window order,
    derived-liveness bundles incl. the integrator passthrough, and the two
    workers' run logs (newest first; `runs_limit` is a caller argument, the
    k precedent). The FOURTH unscored-by-contract member (ruled 2026-08-17):
    no retrieval runs, so no scores exist — IDs + structured fields, ZERO
    writes. 404 on unknown agent; pass-through by ruling."""
    try:
        return await app.state.retrieval.agent_state(agent_id, runs_limit)
    except UnknownAgentError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
