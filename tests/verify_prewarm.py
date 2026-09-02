"""verify_prewarm.py — structural done-when walker for the C7 Stage B
scene-boundary reconstruction pre-warm (probe-driven; `IngestService.scene_boundary`
+ `_prewarm_reconstruction`; 2026-08-18).

The pre-warm reuses `retrieve_dialogue_init` (embed -> fetch -> score -> serve)
with the boundary's probe as the query, at the FRESHLY recompiled identity
version + the boundary basis, so serve's write-backs land the reconstruction
cache under the exact composed keys the first on-camera read will look up. This
walker proves it end to end against the scratch DB with deterministic fakes:
a probe warms the cache (A), the next same-basis init is a CALL-FREE cache hit
(B, the success signal), a boundary WITHOUT a probe is the unchanged off state
(C), and a warm failure degrades without failing the boundary (D). The
drift-budget refusal (R8's guardrail) is inherited verbatim from serve and is
proven by `verify_reconstruction`; it is not re-walked here.

Offline, keyless, structural-only per tests\\CLAUDE.md; fake providers. The
agent names carry a per-run millisecond suffix, so re-runs against the
persistent scratch never collide and every assertion is agent-scoped.

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_prewarm.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from psycopg.types.json import Jsonb

from scratch_uri import scratch_uri

from app import db
from app.config import Settings
from app.db import build_pool
from app.ingest import IngestService
from app.providers import (
    FailingEmbeddingProvider,
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueInitRequest, SceneBoundaryEvent

NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=90)  # 90 days at episodic tau => strength ~ 0 < theta
SEED = "A verification NPC, keeper of the crossing ledger."
AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "gate_enabled": 0.0,  # loader turn — no mid-scene fetch
    # reconstruction_theta default 0.5: the 90-day memories are past it.
}
PROBE = "news of the ford gate and the crossing keeper"
MEMORIES = [
    "The ford gate lantern was shattered in the storm at the crossing.",
    "Merchants cheated the keeper twice at the ford crossing.",
]

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


def fake_providers(**overrides) -> Providers:
    return Providers(
        write=overrides.get("write", FakeWriteProvider()),
        escalation=overrides.get("escalation", FakeEscalationProvider()),
        embedding=overrides.get("embedding", FakeEmbeddingProvider()),
        dialogue=overrides.get("dialogue", FakeProseProvider()),
        reconstruction=overrides.get("reconstruction", FakeReconstructionProvider()),
    )


async def make_agent(pool, name: str) -> object:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (name, SEED, "what threatens the crossing", Jsonb(AGENT_CONFIG)),
        )
        return (await cur.fetchone())[0]


async def seed_memory(pool, agent_id, text: str, valid_at) -> object:
    """A completed original memory at the db layer (the verify_reflection seed
    shape): explicit fixture facts, the pure fake embedding, no NLP pass, no
    gist spans — reconstruction runs on the thinned whole-text detail."""
    vec = FakeEmbeddingProvider().embed([text]).vectors[0]
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=f"[walker seed] {text}",
        valid_at=valid_at,
        importance_raw=0.6,
        scoring_failed=False,
        typology="observed",
        typology_confidence=0.9,
        typology_source="declared",
        provenance="lived",
        pinned=False,
        decay_class="episodic",
        decay_class_unknown=False,
        embedding=vec,
        entities=None,
        spans=[],
    )
    return await db.insert_observation(pool, plan)


async def cache_row_count(pool, agent_id) -> int:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM reconstruction_cache rc "
            "JOIN memories m ON m.memory_id = rc.memory_id WHERE m.agent_id = %s",
            (agent_id,),
        )
        return (await cur.fetchone())[0]


async def scene_boundary(pool, settings, agent_id, probe, *, embedding=None):
    providers = fake_providers(embedding=embedding) if embedding else fake_providers()
    retrieval = RetrievalService(pool, providers, settings)
    ingest = IngestService(pool, providers, settings, retrieval)
    return await ingest.scene_boundary(
        SceneBoundaryEvent(
            agent_id=agent_id, client_timestamp=NOW, prewarm_context=probe
        )
    )


async def dialogue_init(pool, settings, agent_id, probe, version):
    providers = fake_providers()
    retrieval = RetrievalService(pool, providers, settings)
    return await retrieval.retrieve_dialogue_init(
        DialogueInitRequest(
            agent_id=agent_id,
            query_text=probe,
            identity_version=version,
            scene_started_at=NOW,
            as_of=NOW,
        )
    )


async def run(uri: str) -> None:
    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    try:
        suffix = int(time.time() * 1000)

        # -- A. a probe warms the reconstruction cache ---------------------
        print("\n-- A. a boundary probe warms the reconstruction cache")
        agent = await make_agent(pool, f"prewarm-A-{suffix}")
        for text in MEMORIES:
            await seed_memory(pool, agent, text, OLD)
        before = await cache_row_count(pool, agent)
        result = await scene_boundary(pool, settings, agent, PROBE)
        check(
            result.prewarm is not None,
            "A1 a boundary with a probe returns a prewarm record",
        )
        check(
            not result.prewarm.degraded,
            "A2 the warm ran clean (not degraded)",
            f"reason={result.prewarm.degraded_reason}",
        )
        check(
            result.prewarm.cache_misses > 0,
            "A3 the past-theta memories were reconstruct misses to warm",
            f"cache_misses={result.prewarm.cache_misses}",
        )
        after = await cache_row_count(pool, agent)
        check(
            before == 0 and after > 0,
            "A4 the reconstruction cache went from cold to warm",
            f"{before} -> {after}",
        )
        check(
            result.identity_version is not None,
            "A5 the identity document was recompiled alongside the warm",
        )

        # -- B. the first on-camera read at the same basis is call-free ----
        print("\n-- B. the next same-basis init is a call-free cache hit")
        init = await dialogue_init(
            pool, settings, agent, PROBE, result.identity_version
        )
        instr = init.instrumentation
        check(
            instr.cache_misses == 0,
            "B1 the on-camera read has zero reconstruct misses (all pre-warmed)",
            f"cache_misses={instr.cache_misses}",
        )
        check(
            instr.cache_hits > 0,
            "B2 the served items came from the warm cache",
            f"cache_hits={instr.cache_hits}",
        )
        check(
            instr.reconstruction_input_tokens == 0
            and instr.reconstruction_output_tokens == 0,
            "B3 no reconstruction model call ran on the on-camera read "
            "(zero tokens; only the cheap cache fetch, not the cold call)",
            f"in={instr.reconstruction_input_tokens} out={instr.reconstruction_output_tokens}",
        )

        # -- C. no probe = the unchanged off state -------------------------
        print("\n-- C. a boundary WITHOUT a probe is the off state (unchanged)")
        agent_c = await make_agent(pool, f"prewarm-C-{suffix}")
        await seed_memory(pool, agent_c, MEMORIES[0], OLD)
        result_c = await scene_boundary(pool, settings, agent_c, None)
        check(
            result_c.prewarm is None,
            "C1 a probe-less boundary carries no prewarm record (off state)",
        )
        check(
            result_c.identity_version is not None,
            "C2 identity is still recompiled without a probe (behavior unchanged)",
        )
        check(
            await cache_row_count(pool, agent_c) == 0,
            "C3 a probe-less boundary warms nothing (the cache stays cold)",
        )

        # -- D. fail-quiet: a warm failure never fails the boundary --------
        print("\n-- D. fail-quiet: a warm failure degrades, the boundary survives")
        agent_d = await make_agent(pool, f"prewarm-D-{suffix}")
        await seed_memory(pool, agent_d, MEMORIES[0], OLD)
        result_d = await scene_boundary(
            pool, settings, agent_d, PROBE, embedding=FailingEmbeddingProvider()
        )
        check(result_d.accepted, "D1 the boundary is accepted despite the warm failure")
        check(
            result_d.prewarm is not None and result_d.prewarm.degraded,
            "D2 the warm failure is recorded as a degraded prewarm, not raised",
            f"reason={result_d.prewarm.degraded_reason if result_d.prewarm else None}",
        )
        check(
            result_d.identity_version is not None,
            "D3 identity is recompiled even when the warm fails",
        )
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
