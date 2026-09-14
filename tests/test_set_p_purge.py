"""Set P — purge, the sole sanctioned content DELETE
(docs\\test-suite.md; the C6 rulings 2026-08-18 — per-memory scope, the DELETE
verb, no guard, NO migration). Structural-only per tests\\CLAUDE.md: row
presence/absence and the honest per-table counts, never prose.

The seam is `db.purge_memory` / `IngestService.purge_memory` (behind
DELETE /v1/memories/{memory_id}). Every scenario seeds a full-chain memory at
the db layer (no write pass — unmarked, no NLP loaders), then proves the purge
erases exactly that memory's seven tables and nothing else: a co-resident
memory, the agent, its identity components, and a reflection whose
source_memory_ids still names the purged memory (dangling by design — purge
honesty, migration-01.md:132) all survive. The `scene` fixture truncates
between tests, so counts here are exact, not id-scoped like the walker's.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from conftest import NOW, V1_CONFIG, run_structural

from app import db
from app.ingest import UnknownMemoryError

# The six memory-child tables the purge clears before the memories row.
CHILD_TABLES = (
    "memory_details",
    "memory_fact_versions",
    "memory_gist_spans",
    "corrections",
    "reconstruction_cache",
    "memory_enrichment_runs",
)

# Per-memory row counts after a seed + _add_children: the two insert_observation
# heads each gain a superseding partner, and one row lands in every other table.
EXPECTED = {
    "memory_details": 2,
    "memory_fact_versions": 2,
    "memory_gist_spans": 1,
    "corrections": 1,
    "reconstruction_cache": 1,
    "memory_enrichment_runs": 1,
}


async def _add_children(ctx, memory_id, component_id) -> None:
    """One extra row in every purge-scoped child table beyond the
    insert_observation heads: a superseding detail + fact head, a gist span
    bound to a surviving identity_component, a corrections record, an enrichment
    run, and a cache row. Post-condition counts are EXPECTED."""
    async with ctx.pool.connection() as conn, conn.cursor() as cur:
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
            (memory_id, "[set-p] corrected telling", NOW, NOW),
        )
        detail_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO memory_fact_versions (memory_id, basis_text, "
            "write_cause, valid_at, invalid_at) "
            "VALUES (%s, %s, 'authorial_correction', %s, %s)",
            (memory_id, "[set-p] corrected basis", NOW, NOW),
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
            (memory_id, "v-set-p", "[set-p] cached render"),
        )


async def _scoped_counts(ctx, memory_id) -> dict:
    out = {}
    for t in ("memories",) + CHILD_TABLES:
        row = await ctx.fetchrow(
            f"SELECT count(*) FROM {t} WHERE memory_id = %s", memory_id
        )
        out[t] = row[0]
    return out


async def _seed_full_memory(ctx, agent_id, text: str):
    component = await ctx.add_component(agent_id, f"crossing-{text[:6]}")
    out = await ctx.seed(agent_id, text, NOW)
    await _add_children(ctx, out.memory_id, component)
    return out.memory_id, component


def test_purge_seeds_then_erases_every_table(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-erase", V1_CONFIG)
        memory_id, _ = await _seed_full_memory(ctx, agent, "the lantern shattered")
        assert await _scoped_counts(ctx, memory_id) == {"memories": 1, **EXPECTED}
        outcome = await db.purge_memory(ctx.pool, memory_id)
        assert outcome is not None
        post = await _scoped_counts(ctx, memory_id)
        assert all(v == 0 for v in post.values()), post

    run_structural(scene, scenario)


def test_purge_returns_honest_per_table_counts(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-counts", V1_CONFIG)
        memory_id, _ = await _seed_full_memory(ctx, agent, "a cart crossed at dawn")
        outcome = await db.purge_memory(ctx.pool, memory_id)
        assert outcome.memory_id == memory_id
        assert outcome.details_deleted == EXPECTED["memory_details"]
        assert outcome.fact_versions_deleted == EXPECTED["memory_fact_versions"]
        assert outcome.gist_spans_deleted == EXPECTED["memory_gist_spans"]
        assert outcome.corrections_deleted == EXPECTED["corrections"]
        assert outcome.cache_rows_evicted == EXPECTED["reconstruction_cache"]
        assert outcome.enrichment_runs_deleted == EXPECTED["memory_enrichment_runs"]

    run_structural(scene, scenario)


def test_purge_leaves_a_co_resident_memory_untouched(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-coresident", V1_CONFIG)
        target, _ = await _seed_full_memory(ctx, agent, "the target memory")
        control, _ = await _seed_full_memory(ctx, agent, "the control memory")
        await db.purge_memory(ctx.pool, target)
        assert all(v == 0 for v in (await _scoped_counts(ctx, target)).values())
        assert await _scoped_counts(ctx, control) == {"memories": 1, **EXPECTED}

    run_structural(scene, scenario)


def test_purge_leaves_agent_and_identity_intact(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-agent", V1_CONFIG)
        memory_id, _ = await _seed_full_memory(ctx, agent, "a lantern at the ford")
        before = (
            await ctx.fetchrow(
                "SELECT count(*) FROM identity_components WHERE agent_id = %s", agent
            )
        )[0]
        await db.purge_memory(ctx.pool, memory_id)
        agent_row = await ctx.fetchrow(
            "SELECT count(*) FROM agents WHERE agent_id = %s", agent
        )
        after = (
            await ctx.fetchrow(
                "SELECT count(*) FROM identity_components WHERE agent_id = %s", agent
            )
        )[0]
        assert agent_row[0] == 1
        # the component whose only referencing gist span was purged still stands
        assert after == before and before >= 1

    run_structural(scene, scenario)


def test_reflection_survives_purge_with_dangling_provenance(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-reflection", V1_CONFIG)
        target, _ = await _seed_full_memory(ctx, agent, "the purged episode")
        control, _ = await _seed_full_memory(ctx, agent, "a surviving episode")
        reflection = await ctx.seed_reflection(
            agent, "a derived belief", NOW, source_memory_ids=(target, control)
        )
        await db.purge_memory(ctx.pool, target)
        row = await ctx.fetchrow(
            "SELECT source_memory_ids FROM reflections WHERE reflection_id = %s",
            reflection,
        )
        assert row is not None, "the derived reflection must survive the purge"
        # provenance is intentionally un-FK'd: the purged id still dangles here
        assert target in row[0] and control in row[0]

    run_structural(scene, scenario)


def test_purge_unknown_memory_returns_none_and_deletes_nothing(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-unknown", V1_CONFIG)
        bystander, _ = await _seed_full_memory(ctx, agent, "an untouched memory")
        result = await db.purge_memory(ctx.pool, uuid4())
        assert result is None
        # the unknown-id purge is a pure no-op: the bystander keeps every row
        assert await _scoped_counts(ctx, bystander) == {"memories": 1, **EXPECTED}

    run_structural(scene, scenario)


def test_service_purge_returns_result_and_raises_on_unknown(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("purge-service", V1_CONFIG)
        memory_id, _ = await _seed_full_memory(ctx, agent, "a service-layer purge")
        svc = ctx.ingest()
        result = await svc.purge_memory(memory_id)
        assert result.memory_id == memory_id
        assert result.details_deleted == EXPECTED["memory_details"]
        assert result.fact_versions_deleted == EXPECTED["memory_fact_versions"]
        assert result.gist_spans_deleted == EXPECTED["memory_gist_spans"]
        assert result.corrections_deleted == EXPECTED["corrections"]
        assert result.cache_rows_evicted == EXPECTED["reconstruction_cache"]
        assert result.enrichment_runs_deleted == EXPECTED["memory_enrichment_runs"]
        assert result.total_ms >= 0.0
        assert all(v == 0 for v in (await _scoped_counts(ctx, memory_id)).values())
        with pytest.raises(UnknownMemoryError):
            await svc.purge_memory(uuid4())

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The per-agent purge (ruled 2026-09-01; contract ruled 2026-09-02): the thin
# extension — the same seven tables, set-scoped, one transaction, no guard,
# no migration, no client verb. The seam is `db.purge_agent_memories` /
# `IngestService.purge_agent_memories` (behind DELETE /v1/agents/{id}/memories).
# ---------------------------------------------------------------------------

# Two full-chain memories under one agent: every child count doubles.
AGENT_EXPECTED = {table: 2 * n for table, n in EXPECTED.items()}


async def _seed_two(ctx, agent):
    first, _ = await _seed_full_memory(ctx, agent, "the first of two memories")
    second, _ = await _seed_full_memory(ctx, agent, "the second of two memories")
    return first, second


def _assert_summed_counts(outcome) -> None:
    assert outcome.memories_deleted == 2
    assert outcome.details_deleted == AGENT_EXPECTED["memory_details"]
    assert outcome.fact_versions_deleted == AGENT_EXPECTED["memory_fact_versions"]
    assert outcome.gist_spans_deleted == AGENT_EXPECTED["memory_gist_spans"]
    assert outcome.corrections_deleted == AGENT_EXPECTED["corrections"]
    assert outcome.cache_rows_evicted == AGENT_EXPECTED["reconstruction_cache"]
    assert outcome.enrichment_runs_deleted == AGENT_EXPECTED["memory_enrichment_runs"]


def test_agent_purge_erases_every_memory_and_child_row(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("agent-purge-erase", V1_CONFIG)
        first, second = await _seed_two(ctx, agent)
        outcome = await db.purge_agent_memories(ctx.pool, agent)
        assert outcome is not None and outcome.agent_id == agent
        _assert_summed_counts(outcome)
        for memory_id in (first, second):
            post = await _scoped_counts(ctx, memory_id)
            assert all(v == 0 for v in post.values()), post

    run_structural(scene, scenario)


def test_agent_purge_leaves_a_co_resident_agent_untouched(scene):
    async def scenario(ctx):
        target = await ctx.make_agent("agent-purge-target", V1_CONFIG)
        control = await ctx.make_agent("agent-purge-control", V1_CONFIG)
        await _seed_two(ctx, target)
        kept, _ = await _seed_full_memory(ctx, control, "the control agent's memory")
        await db.purge_agent_memories(ctx.pool, target)
        assert await _scoped_counts(ctx, kept) == {"memories": 1, **EXPECTED}
        remaining = await ctx.fetchrow(
            "SELECT count(*) FROM memories WHERE agent_id = %s", target
        )
        assert remaining[0] == 0

    run_structural(scene, scenario)


def test_agent_purge_survival_boundary(scene):
    """The agent row, its identity components, a reflection citing BOTH
    purged memories (every source now dangling — purge honesty), and the
    reflection's compiled bundle all survive: purge does not reach
    reflections under either verb."""

    async def scenario(ctx):
        agent = await ctx.make_agent("agent-purge-survival", V1_CONFIG)
        first, second = await _seed_two(ctx, agent)
        reflection = await ctx.seed_reflection(
            agent, "a belief from both", NOW, source_memory_ids=(first, second)
        )
        bundle = await ctx.seed_bundle(agent, reflection)
        components_before = (
            await ctx.fetchrow(
                "SELECT count(*) FROM identity_components WHERE agent_id = %s", agent
            )
        )[0]
        await db.purge_agent_memories(ctx.pool, agent)
        assert (
            await ctx.fetchrow("SELECT count(*) FROM agents WHERE agent_id = %s", agent)
        )[0] == 1
        components_after = (
            await ctx.fetchrow(
                "SELECT count(*) FROM identity_components WHERE agent_id = %s", agent
            )
        )[0]
        assert components_after == components_before and components_before >= 1
        row = await ctx.fetchrow(
            "SELECT source_memory_ids FROM reflections WHERE reflection_id = %s",
            reflection,
        )
        assert row is not None, "the derived reflection must survive"
        assert first in row[0] and second in row[0]  # both dangle, by design
        kept_bundle = await ctx.fetchrow(
            "SELECT count(*) FROM compiled_bundles WHERE bundle_id = %s", bundle
        )
        assert kept_bundle[0] == 1

    run_structural(scene, scenario)


def test_agent_purge_zero_memories_returns_zero_outcome(scene):
    """A known agent with nothing to purge is a 200 with zeros (never a
    404), and a repeat purge is the same zero outcome."""

    async def scenario(ctx):
        agent = await ctx.make_agent("agent-purge-empty", V1_CONFIG)
        for _ in range(2):
            outcome = await db.purge_agent_memories(ctx.pool, agent)
            assert outcome is not None and outcome.agent_id == agent
            assert outcome.memories_deleted == 0
            assert outcome.details_deleted == 0 and outcome.corrections_deleted == 0
            assert outcome.cache_rows_evicted == 0 and outcome.gist_spans_deleted == 0
            assert outcome.fact_versions_deleted == 0
            assert outcome.enrichment_runs_deleted == 0

    run_structural(scene, scenario)


def test_agent_purge_unknown_agent_returns_none_and_deletes_nothing(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("agent-purge-unknown", V1_CONFIG)
        bystander, _ = await _seed_full_memory(ctx, agent, "an untouched memory")
        assert await db.purge_agent_memories(ctx.pool, uuid4()) is None
        assert await _scoped_counts(ctx, bystander) == {"memories": 1, **EXPECTED}

    run_structural(scene, scenario)


def test_service_agent_purge_result_and_route_contract(scene):
    """The service maps the outcome to AgentPurgeResult (+ total_ms) and
    raises UnknownAgentError on an unknown agent; the route is a
    pass-through: 200 + the summed counts, a re-DELETE 200 with zeros, 404
    unknown, 422 malformed."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module
        from app.ingest import UnknownAgentError

        svc = ctx.ingest()
        agent = await ctx.make_agent("agent-purge-service", V1_CONFIG)
        await _seed_two(ctx, agent)
        result = await svc.purge_agent_memories(agent)
        assert result.agent_id == agent
        _assert_summed_counts(result)
        assert result.total_ms >= 0.0
        with pytest.raises(UnknownAgentError):
            await svc.purge_agent_memories(uuid4())

        wired = await ctx.make_agent("agent-purge-wired", V1_CONFIG)
        first, second = await _seed_two(ctx, wired)
        api_module.app.state.service = svc
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
            ok = await c.delete(f"/v1/agents/{wired}/memories")
            assert ok.status_code == 200
            body = ok.json()
            assert body["agent_id"] == str(wired)
            assert body["memories_deleted"] == 2
            assert body["details_deleted"] == AGENT_EXPECTED["memory_details"]
            assert body["corrections_deleted"] == AGENT_EXPECTED["corrections"]
            assert "total_ms" in body
            for memory_id in (first, second):
                assert all(
                    v == 0 for v in (await _scoped_counts(ctx, memory_id)).values()
                )
            again = await c.delete(f"/v1/agents/{wired}/memories")
            assert again.status_code == 200 and again.json()["memories_deleted"] == 0
            unknown = await c.delete(f"/v1/agents/{uuid4()}/memories")
            assert unknown.status_code == 404
            malformed = await c.delete("/v1/agents/not-a-uuid/memories")
            assert malformed.status_code == 422

    run_structural(scene, scenario)


def test_per_memory_purge_of_a_purged_id_is_404(scene):
    """After the bulk verb, the per-memory verb finds nothing: None at the
    db layer, UnknownMemoryError (the 404) at the service."""

    async def scenario(ctx):
        agent = await ctx.make_agent("agent-purge-then-memory", V1_CONFIG)
        first, _ = await _seed_two(ctx, agent)
        await db.purge_agent_memories(ctx.pool, agent)
        assert await db.purge_memory(ctx.pool, first) is None
        with pytest.raises(UnknownMemoryError):
            await ctx.ingest().purge_memory(first)

    run_structural(scene, scenario)
