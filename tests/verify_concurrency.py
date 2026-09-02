"""verify_concurrency.py — structural done-when walker for the C7 concurrency
cap (audit R8; app\\concurrency.py::ModelCallGate; 2026-08-18).

The cap is process-level asyncio + a bounded executor, so the mechanism checks
(cap enforcement, release-on-exception, the gate_wait_ms wait timing) need no
database — they drive ModelCallGate directly with a thread-safe barrier, fully
deterministic. The seam check then confirms the wiring: an uncontended dialogue
turn surfaces gate_wait_ms == 0.0 and stays byte-identical across runs (the gate
changed the executor a provider call runs on, never the prose). All thirteen
gated provider call sites route through gate.run / gate.acquire — the same
primitives proven here — so the gate-level cap governs every seam call.

Offline, keyless, structural-only per tests\\CLAUDE.md; fake providers. The
agent name carries a per-run millisecond suffix, so re-runs against the
persistent scratch never collide and leave nothing that perturbs a later run
(every assertion is scoped to this run's own agent_id).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_concurrency.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app.concurrency import ModelCallGate
from app.config import Settings
from app.db import build_pool
from app.dialogue import DialogueService
from app.providers import (
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueTurnRequest, DialogueTurnResult

NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
SEED = "A verification NPC, keeper of the crossing ledger."
AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "gate_enabled": 0.0,  # every turn is a loader turn — no mid-scene fetch
}

PASSED: list[str] = []


def ok(criterion: str, detail: str = "") -> None:
    PASSED.append(criterion)
    print(f"  PASS  {criterion}" + (f"  ({detail})" if detail else ""))


def fail(criterion: str, detail: str) -> None:
    print(f"  FAIL  {criterion}: {detail}")
    sys.exit(1)


def check(condition: bool, criterion: str, detail: str = "") -> None:
    if not condition:
        fail(criterion, detail or "condition false")
    ok(criterion, detail)


def scratch_uri_from_env() -> str:
    from app.config import load_env

    return scratch_uri(load_env()["DATABASE_URI"], "twicetold_test")


def fake_providers(gate: ModelCallGate) -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=FakeEmbeddingProvider(),
        dialogue=FakeProseProvider(),
        reconstruction=FakeReconstructionProvider(),
        gate=gate,
    )


async def make_agent(pool, name: str, config: dict) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED, "what threatens the crossing", Jsonb(config)),
        )
        return (await cur.fetchone())[0]


# --------------------------------------------------------------------------- #
# A. cap enforcement — N+2 concurrent calls, the (N+1)th blocks (no database)
# --------------------------------------------------------------------------- #


async def section_cap_enforcement() -> None:
    print("\n-- A. cap enforcement (N+2 concurrent, the (N+1)th blocks)")
    cap = 2
    gate = ModelCallGate(cap)
    lock = threading.Lock()
    state = {"in_flight": 0, "peak": 0}
    release = threading.Event()

    def blocking_call() -> str:
        with lock:
            state["in_flight"] += 1
            state["peak"] = max(state["peak"], state["in_flight"])
        release.wait(timeout=5.0)  # hold the slot until the test frees all
        with lock:
            state["in_flight"] -= 1
        return "done"

    tasks = [asyncio.create_task(gate.run(blocking_call)) for _ in range(cap + 2)]
    for _ in range(50):  # let the admitted calls reach the barrier
        await asyncio.sleep(0.02)
        with lock:
            if state["in_flight"] >= cap:
                break
    with lock:
        in_flight = state["in_flight"]
        peak = state["peak"]
    check(
        in_flight == cap and peak == cap,
        "A1 exactly cap=2 calls run at once; the extra 2 block at the gate",
        f"in_flight={in_flight} peak={peak}",
    )
    pending = sum(not t.done() for t in tasks)
    check(
        pending == cap + 2,
        "A2 nothing completes while the barrier holds: cap admitted, 2 blocked at the gate",
        f"pending={pending}",
    )
    release.set()
    results = await asyncio.gather(*tasks)
    check(
        results == ["done"] * (cap + 2) and state["peak"] == cap,
        "A3 all complete once slots free; peak concurrency never exceeded cap",
        f"peak={state['peak']}",
    )
    gate.shutdown()


# --------------------------------------------------------------------------- #
# B. a failed call releases its slot (no database)
# --------------------------------------------------------------------------- #


async def section_release_on_exception() -> None:
    print("\n-- B. a failed call releases its slot")
    gate = ModelCallGate(1)

    def boom() -> str:
        raise ValueError("provider blew up")

    raised = False
    try:
        await gate.run(boom)
    except ValueError:
        raised = True
    check(raised, "B1 gate.run propagates the provider exception")
    try:  # the single slot must be free again — acquire must not block
        wait_ms = await asyncio.wait_for(gate.acquire(), timeout=1.0)
    except TimeoutError:
        fail("B2 the slot is released after the exception", "acquire blocked -> leak")
    gate.release()
    check(
        wait_ms == 0.0, "B2 the slot is released after the exception", f"wait={wait_ms}"
    )
    gate.shutdown()


# --------------------------------------------------------------------------- #
# C. gate_wait_ms source: acquire() times the queue wait (no database)
# --------------------------------------------------------------------------- #


async def section_wait_timing() -> None:
    print("\n-- C. gate_wait_ms source: acquire() times the queue wait")
    gate = ModelCallGate(1)
    w0 = await gate.acquire()  # uncontended: the one slot is free
    check(
        w0 == 0.0,
        "C1 an uncontended acquire waits 0.0 ms (the gate_wait_ms floor)",
        f"wait={w0}",
    )

    waited: dict[str, float] = {}

    async def contender() -> None:
        waited["ms"] = await gate.acquire()
        gate.release()

    task = asyncio.create_task(contender())
    await asyncio.sleep(0.2)  # the contender is now blocked on the held slot
    check(not task.done(), "C2 a second acquire blocks while the slot is held")
    gate.release()  # free the slot the contender is waiting on
    await task
    check(
        waited["ms"] > 0.0,
        "C3 the contended acquire reports a non-zero wait (gate_wait_ms > 0 under contention)",
        f"wait={waited['ms']}",
    )
    gate.shutdown()


# --------------------------------------------------------------------------- #
# D. seam wiring — an uncontended turn surfaces gate_wait_ms == 0 (database)
# --------------------------------------------------------------------------- #


async def run_turn(pool, settings, agent_id) -> DialogueTurnResult:
    gate = ModelCallGate(settings.max_concurrent_model_calls)
    providers = fake_providers(gate)
    service = DialogueService(
        pool, providers, settings, RetrievalService(pool, providers, settings)
    )
    result = None
    async for item in service.run_dialogue_turn(
        DialogueTurnRequest(
            agent_id=agent_id, utterance="what news at the crossing?", as_of=NOW
        )
    ):
        if isinstance(item, DialogueTurnResult):
            result = item
    gate.shutdown()
    if result is None:
        fail("D dialogue turn", "no terminal result")
    return result


async def section_seam_wiring(pool, settings) -> None:
    print("\n-- D. seam wiring: an uncontended turn surfaces gate_wait_ms == 0")
    name = f"concurrency-walker-{int(time.time() * 1000)}"
    agent_id = await make_agent(pool, name, AGENT_CONFIG)
    r1 = await run_turn(pool, settings, agent_id)
    check(
        r1.instrumentation.gate_wait_ms == 0.0,
        "D1 an uncontended dialogue turn surfaces gate_wait_ms == 0.0",
        f"gate_wait_ms={r1.instrumentation.gate_wait_ms}",
    )
    check(bool(r1.content), "D2 the gated turn still produces prose")
    r2 = await run_turn(pool, settings, agent_id)
    check(
        r1.content == r2.content,
        "D3 the gated turn is byte-identical across runs (the executor swap changed no text)",
    )


async def run(uri: str) -> None:
    settings = Settings(database_uri=uri, provider_mode="fake")
    await section_cap_enforcement()
    await section_release_on_exception()
    await section_wait_timing()
    pool = build_pool(uri)
    await pool.open()
    try:
        await section_seam_wiring(pool, settings)
    finally:
        await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-uri", default=None)
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
