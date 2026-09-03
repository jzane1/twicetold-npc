"""verify_purge.py — structural done-when walker for the purge endpoint
(Phase C6; the four rulings 2026-08-18 — per-memory scope, the DELETE verb,
no guard, NO migration by ruling — purge only deletes from the 001-008 tables).

Runs the C6 backend done-when criteria against the SCRATCH database (default:
the .env DATABASE_URI with its database name swapped to `twicetold_test`), with
deterministic fake providers — offline, keyless, structural-only per
tests\\CLAUDE.md. The seam is `db.purge_memory` / `IngestService.purge_memory`
(behind DELETE /v1/memories/{memory_id}, the SOLE sanctioned content DELETE in
an otherwise non-destructive store), exercised db-side for the ordered
seven-table delete + the honest per-table counts, and route-side over
httpx.ASGITransport for the wire contract (200 + counts / 404 / 422).

What this walker owns: the child-before-parent delete in one transaction, the
honest per-table counts, the survival boundary (a co-resident memory, the
agent, an identity_component whose only referencing gist span was purged, and a
reflection whose source_memory_ids still names the purged memory — dangling by
design, the purge-honesty stance), the unknown-id → None/404 path, and the
zero-collateral proof (nothing outside the target memory's rows moves).

Persistent-scratch rule (the verify_dissonance / verify_agent_state
precedent): the agent name carries a per-run suffix and every assertion is
scoped to this run's ids (never a DB-global count), so prior green runs on the
persistent scratch cannot perturb this one. In full sweeps this walker runs
after the elder correction/reconstruction walkers (fresh + serial).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_purge.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from scratch_uri import scratch_uri

from app import db
from app.config import Settings
from app.db import build_pool
from app.ingest import IngestService, UnknownMemoryError
from app.providers import (
    FakeEmbeddingProvider,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    Providers,
)

NOW = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
SEED = "A verification NPC, keeper of the crossing ledger."
RUN = uuid4().hex[:8]  # per-run fixture scoping (persistent-scratch rule)

# The six memory-child tables the purge clears before the memories row. Every
# survival/erasure assertion is scoped by memory_id over exactly these + memories.
CHILD_TABLES = (
    "memory_details",
    "memory_fact_versions",
    "memory_gist_spans",
    "corrections",
    "reconstruction_cache",
    "memory_enrichment_runs",
)

# The per-memory row counts add_children leaves (beyond the memories row): the
# two heads insert_observation writes gain a superseding partner each, and one
# row lands in every remaining child table.
EXPECTED = {
    "memory_details": 2,
    "memory_fact_versions": 2,
    "memory_gist_spans": 1,
    "corrections": 1,
    "reconstruction_cache": 1,
    "memory_enrichment_runs": 1,
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


def fake_providers() -> Providers:
    return Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=FakeEmbeddingProvider(),
        dialogue=FakeProseProvider(),
        reconstruction=FakeReconstructionProvider(),
    )


async def fetchall(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()


async def fetchrow(pool, sql: str, *params):
    rows = await fetchall(pool, sql, *params)
    return rows[0] if rows else None


async def make_agent(pool, tag: str) -> UUID:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity) VALUES (%s, %s) "
            "RETURNING agent_id",
            (f"purge-walker-{RUN}-{tag}", SEED),
        )
        return (await cur.fetchone())[0]


async def seed_memory(pool, agent_id: UUID, text: str) -> UUID:
    """A completed memory at the db layer (the verify_agent_state seed shape):
    insert_observation writes the memories row + the `original` detail head +
    the `original` fact head; no spans, no NLP pass, pure fake embedding."""
    vec = FakeEmbeddingProvider().embed([text]).vectors[0]
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=f"[walker seed] {text}",
        valid_at=NOW,
        importance_raw=0.5,
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
        event_time=None,
        location_name=None,
    )
    outcome = await db.insert_observation(pool, plan)
    return outcome.memory_id


async def seed_component(pool, agent_id: UUID) -> UUID:
    """One live identity_component for the agent — a purge-surviving parent
    whose only referencing gist span the purge deletes."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, %s, %s, %s) RETURNING component_id",
            (agent_id, f"crossing-{RUN}", ["ford"], "place"),
        )
        return (await cur.fetchone())[0]


async def seed_reflection(pool, agent_id: UUID, source_memory_ids) -> UUID:
    """A derived reflection carrying provenance in the intentionally un-FK'd
    source_memory_ids array (migration-01.md:132 — purge honesty)."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO reflections (agent_id, content, identity_relevant, "
            "source_memory_ids, valid_at) VALUES (%s, %s, %s, %s, %s) "
            "RETURNING reflection_id",
            (agent_id, "[walker] a derived belief", True, list(source_memory_ids), NOW),
        )
        return (await cur.fetchone())[0]


async def add_children(pool, memory_id: UUID, component_id: UUID) -> None:
    """Give a memory one extra row in every purge-scoped child table beyond the
    insert_observation heads, so the walker proves each table clears: a
    superseding detail + fact head (the correction shape), a gist span bound to
    a surviving identity_component, a corrections record, an enrichment run, and
    a cache row. Post-condition counts are EXPECTED."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO memory_gist_spans (memory_id, start_char, end_char, "
            "matched_component_id) VALUES (%s, 0, 5, %s)",
            (memory_id, component_id),
        )
        # Seeded superseded (invalid_at set) so insert_observation's original
        # stays the SOLE live head — the one-live-head partial unique index on
        # memory_details / memory_fact_versions forbids a second live head.
        await cur.execute(
            "INSERT INTO memory_details (memory_id, content, write_cause, "
            "valid_at, invalid_at) VALUES (%s, %s, 'authorial_correction', %s, %s) "
            "RETURNING detail_id",
            (memory_id, "[walker] corrected telling", NOW, NOW),
        )
        detail_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO memory_fact_versions (memory_id, basis_text, "
            "write_cause, valid_at, invalid_at) "
            "VALUES (%s, %s, 'authorial_correction', %s, %s)",
            (memory_id, "[walker] corrected basis", NOW, NOW),
        )
        await cur.execute(
            "INSERT INTO corrections (memory_id, detail_id, verb, valid_at) "
            "VALUES (%s, %s, 'rationalization', %s)",
            (memory_id, detail_id, NOW),
        )
        await cur.execute(
            "INSERT INTO memory_enrichment_runs (memory_id, attempt, outcome) "
            "VALUES (%s, 1, 'completed')",
            (memory_id,),
        )
        await cur.execute(
            "INSERT INTO reconstruction_cache (memory_id, identity_version, "
            "rendered_text) VALUES (%s, %s, %s)",
            (memory_id, "v-walker", "[walker] cached render"),
        )


async def scoped_counts(pool, memory_id: UUID) -> dict:
    out = {}
    for t in ("memories",) + CHILD_TABLES:
        row = await fetchrow(
            pool, f"SELECT count(*) FROM {t} WHERE memory_id = %s", memory_id
        )
        out[t] = row[0]
    return out


async def run(uri: str) -> None:
    from urllib.parse import urlsplit

    settings = Settings(database_uri=uri, provider_mode="fake")
    pool = build_pool(uri)
    await pool.open()
    print(f"walker: scratch DB = {urlsplit(uri).path.lstrip('/')}")
    try:
        svc = IngestService(pool, fake_providers(), settings)

        # ------------------------------------------------------------------ #
        print("\n-- A. seed the target + the survival boundary")
        agent = await make_agent(pool, "keeper")
        component = await seed_component(pool, agent)
        target = await seed_memory(pool, agent, "the lantern shattered at the toll")
        control = await seed_memory(pool, agent, "a cart crossed at dawn")
        await add_children(pool, target, component)
        await add_children(pool, control, component)
        reflection = await seed_reflection(pool, agent, [target, control])
        pre = await scoped_counts(pool, target)
        check(
            pre == {"memories": 1, **EXPECTED},
            "A1 target seeded with a row in every purge-scoped table",
            detail=str(pre),
        )

        # ------------------------------------------------------------------ #
        print("\n-- B. purge_memory returns the honest per-table counts")
        outcome = await db.purge_memory(pool, target)
        check(outcome is not None, "B1 purge of a live memory returns an outcome")
        check(outcome.memory_id == target, "B2 the outcome echoes the memory_id")
        check(outcome.details_deleted == 2, "B3 details_deleted == 2")
        check(outcome.fact_versions_deleted == 2, "B4 fact_versions_deleted == 2")
        check(outcome.gist_spans_deleted == 1, "B5 gist_spans_deleted == 1")
        check(outcome.corrections_deleted == 1, "B6 corrections_deleted == 1")
        check(outcome.cache_rows_evicted == 1, "B7 cache_rows_evicted == 1")
        check(outcome.enrichment_runs_deleted == 1, "B8 enrichment_runs_deleted == 1")

        # ------------------------------------------------------------------ #
        print("\n-- C. the target memory is erased from every table")
        post = await scoped_counts(pool, target)
        check(
            all(v == 0 for v in post.values()),
            "C1 zero rows remain for the purged memory_id in any table",
            detail=str(post),
        )

        # ------------------------------------------------------------------ #
        print("\n-- D. the co-resident memory survives intact")
        surv = await scoped_counts(pool, control)
        check(
            surv == {"memories": 1, **EXPECTED},
            "D1 the control memory keeps every row (no collateral delete)",
            detail=str(surv),
        )

        # ------------------------------------------------------------------ #
        print("\n-- E. survival boundary + purge honesty (dangling provenance)")
        arow = await fetchrow(
            pool, "SELECT count(*) FROM agents WHERE agent_id = %s", agent
        )
        check(arow[0] == 1, "E1 the agent row survives")
        crow = await fetchrow(
            pool,
            "SELECT count(*) FROM identity_components WHERE component_id = %s",
            component,
        )
        check(
            crow[0] == 1,
            "E2 the identity_component survives though its only span was purged",
        )
        rrow = await fetchrow(
            pool,
            "SELECT source_memory_ids FROM reflections WHERE reflection_id = %s",
            reflection,
        )
        check(rrow is not None, "E3 the derived reflection survives the purge")
        check(
            target in rrow[0] and control in rrow[0],
            "E4 source_memory_ids still names the purged memory "
            "(dangling by design — purge honesty)",
        )

        # ------------------------------------------------------------------ #
        print("\n-- F. an unknown id purges to None (the 404 source)")
        gone = await db.purge_memory(pool, uuid4())
        check(gone is None, "F1 purge of an unknown memory_id returns None")
        try:
            await svc.purge_memory(uuid4())
            fail("F2 the service raises UnknownMemoryError", "no exception")
        except UnknownMemoryError:
            ok("F2 the service raises UnknownMemoryError (the route's 404 source)")

        # ------------------------------------------------------------------ #
        print("\n-- G. the wire contract over httpx.ASGITransport")
        import httpx

        import app.api as api_module

        api_module.app.state.service = svc
        wired = await seed_memory(pool, agent, "a wire-contract memory")
        await add_children(pool, wired, component)
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://walker"
        ) as client:
            resp = await client.delete(f"/v1/memories/{wired}")
            body = resp.json()
            check(
                resp.status_code == 200
                and body["memory_id"] == str(wired)
                and body["details_deleted"] == 2
                and body["fact_versions_deleted"] == 2
                and body["gist_spans_deleted"] == 1
                and body["corrections_deleted"] == 1
                and body["cache_rows_evicted"] == 1
                and body["enrichment_runs_deleted"] == 1
                and "total_ms" in body,
                "G1 DELETE returns 200 with the honest per-table counts",
                detail=f"{resp.status_code} {body}",
            )
            after = await scoped_counts(pool, wired)
            check(
                all(v == 0 for v in after.values()),
                "G2 the wired memory is erased after the route call",
            )
            r404 = await client.delete(f"/v1/memories/{uuid4()}")
            check(r404.status_code == 404, "G3 unknown memory_id -> 404")
            r422 = await client.delete("/v1/memories/not-a-uuid")
            check(r422.status_code == 422, "G4 malformed memory_id -> 422")

        # ------------------------------------------------------------------ #
        print("\n-- H. the per-agent purge (ruled 2026-09-01/02): the thin extension")
        from app.ingest import UnknownAgentError

        bulk = await make_agent(pool, "bulk")
        bulk_component = await seed_component(pool, bulk)
        first = await seed_memory(pool, bulk, "the bulk agent's first memory")
        second = await seed_memory(pool, bulk, "the bulk agent's second memory")
        await add_children(pool, first, bulk_component)
        await add_children(pool, second, bulk_component)
        bulk_reflection = await seed_reflection(pool, bulk, [first, second])
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO compiled_bundles (agent_id, reflection_id, "
                "scene_type, w_relevance, w_recency, w_importance, passthrough) "
                "VALUES (%s, %s, 'default', 1.0, 1.0, 1.0, '{}') RETURNING bundle_id",
                (bulk, bulk_reflection),
            )
            bulk_bundle = (await cur.fetchone())[0]
        await db.insert_reflection_run(
            pool,
            db.ReflectionRunRecord(
                agent_id=bulk,
                outcome="completed",
                error=None,
                reflections_written=1,
                dropped_ungrounded=0,
                consolidation_ran=False,
                consolidation_failed=False,
                rrr=0.0,
                rrr_blocked=False,
                pruned_components=0,
                evicted_cache_rows=0,
                pressure_before=1.0,
                pressure_after=0.0,
                reflect_ms=1.0,
                consolidation_ms=0.0,
                insert_ms=1.0,
                total_ms=2.0,
                reflect_input_tokens=10,
                reflect_output_tokens=5,
                consolidation_input_tokens=0,
                consolidation_output_tokens=0,
            ),
        )
        await db.insert_compiler_run(
            pool,
            db.CompilerRunRecord(
                agent_id=bulk,
                outcome="completed",
                error=None,
                pairs_compiled=1,
                pairs_failed=0,
                passthrough_keys_dropped=0,
                input_tokens=10,
                output_tokens=5,
                total_ms=2.0,
            ),
        )
        bystander = await make_agent(pool, "bystander")
        bystander_component = await seed_component(pool, bystander)
        bystander_memory = await seed_memory(pool, bystander, "the bystander's one")
        await add_children(pool, bystander_memory, bystander_component)

        bulk_outcome = await db.purge_agent_memories(pool, bulk)
        check(
            bulk_outcome is not None and bulk_outcome.agent_id == bulk,
            "H1 purge of a known agent returns an outcome echoing the agent_id",
        )
        check(
            bulk_outcome.memories_deleted == 2
            and bulk_outcome.details_deleted == 4
            and bulk_outcome.fact_versions_deleted == 4
            and bulk_outcome.gist_spans_deleted == 2
            and bulk_outcome.corrections_deleted == 2
            and bulk_outcome.cache_rows_evicted == 2
            and bulk_outcome.enrichment_runs_deleted == 2,
            "H2 the honest SUMMED per-table counts over two full-chain memories",
        )
        gone = [await scoped_counts(pool, m) for m in (first, second)]
        check(
            all(v == 0 for counts in gone for v in counts.values()),
            "H3 zero rows remain for either memory_id in any of the seven tables",
            detail=str(gone),
        )
        check(
            await scoped_counts(pool, bystander_memory) == {"memories": 1, **EXPECTED},
            "H4 the co-resident agent's memory keeps every row (no collateral)",
        )
        arow = await fetchrow(
            pool, "SELECT count(*) FROM agents WHERE agent_id = %s", bulk
        )
        crow = await fetchrow(
            pool,
            "SELECT count(*) FROM identity_components WHERE component_id = %s",
            bulk_component,
        )
        check(
            arow[0] == 1 and crow[0] == 1,
            "H5 the agent row and its identity_component survive",
        )
        rrow = await fetchrow(
            pool,
            "SELECT source_memory_ids FROM reflections WHERE reflection_id = %s",
            bulk_reflection,
        )
        brow = await fetchrow(
            pool,
            "SELECT count(*) FROM compiled_bundles WHERE bundle_id = %s",
            bulk_bundle,
        )
        runs = await fetchrow(
            pool,
            "SELECT (SELECT count(*) FROM reflection_runs WHERE agent_id = %s), "
            "(SELECT count(*) FROM compiler_runs WHERE agent_id = %s)",
            bulk,
            bulk,
        )
        check(
            rrow is not None
            and first in rrow[0]
            and second in rrow[0]
            and brow[0] == 1
            and tuple(runs) == (1, 1),
            "H6 the reflection (EVERY source now dangling — purge honesty), its "
            "bundle, and both run logs survive: purge does not reach reflections "
            "under either verb",
        )
        zero = await db.purge_agent_memories(pool, bulk)
        check(
            zero is not None
            and zero.memories_deleted == 0
            and zero.details_deleted == 0
            and zero.corrections_deleted == 0
            and zero.cache_rows_evicted == 0
            and zero.fact_versions_deleted == 0
            and zero.enrichment_runs_deleted == 0
            and zero.gist_spans_deleted == 0,
            "H7 a known agent with nothing left purges to an all-zero outcome "
            "(the 200), never None",
        )
        check(
            await db.purge_agent_memories(pool, uuid4()) is None,
            "H8 an unknown agent_id purges to None (the 404 source)",
        )
        try:
            await svc.purge_agent_memories(uuid4())
            fail("H9 the service raises UnknownAgentError", "no exception")
        except UnknownAgentError:
            ok("H9 the service raises UnknownAgentError (the route's 404 source)")
        wired_agent = await make_agent(pool, "wired-bulk")
        wired_component = await seed_component(pool, wired_agent)
        wired_memory = await seed_memory(pool, wired_agent, "a wired bulk memory")
        await add_children(pool, wired_memory, wired_component)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://walker"
        ) as client:
            resp = await client.delete(f"/v1/agents/{wired_agent}/memories")
            body = resp.json()
            check(
                resp.status_code == 200
                and body["agent_id"] == str(wired_agent)
                and body["memories_deleted"] == 1
                and body["details_deleted"] == 2
                and body["fact_versions_deleted"] == 2
                and body["gist_spans_deleted"] == 1
                and body["corrections_deleted"] == 1
                and body["cache_rows_evicted"] == 1
                and body["enrichment_runs_deleted"] == 1
                and "total_ms" in body,
                "H10 DELETE /v1/agents/{id}/memories returns 200 with the counts",
                detail=f"{resp.status_code} {body}",
            )
            check(
                all(v == 0 for v in (await scoped_counts(pool, wired_memory)).values()),
                "H11 the wired agent's memory is erased after the route call",
            )
            again = await client.delete(f"/v1/agents/{wired_agent}/memories")
            check(
                again.status_code == 200 and again.json()["memories_deleted"] == 0,
                "H12 a re-DELETE is 200 with zeros",
            )
            r404 = await client.delete(f"/v1/agents/{uuid4()}/memories")
            check(r404.status_code == 404, "H13 unknown agent_id -> 404")
            r422 = await client.delete("/v1/agents/not-a-uuid/memories")
            check(r422.status_code == 422, "H14 malformed agent_id -> 422")
            purged = await client.delete(f"/v1/memories/{first}")
            check(
                purged.status_code == 404,
                "H15 the per-memory verb 404s on an id the bulk verb erased",
            )

        print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-uri",
        default=None,
        help="scratch Postgres URI (default: .env DATABASE_URI with the "
        "database swapped to twicetold_test)",
    )
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
