"""Set O — the agent-state read (C5, the rulings dated 2026-08-17;
GET /v1/agents/{agent_id}/state — the FOURTH unscored-by-contract member).

The seam is `RetrievalService.agent_state`, exercised service-side for the
composed values (pressure hand math, liveness joins, newest-per-pair picks,
run-log mirrors) and route-side over httpx.ASGITransport for the wire
contract (404/422 ladder, present-null tri-state, pass-through-by-ruling
JSON identity). Every fixture is db-layer (`Ctx.seed*` + the run-record
inserts), so every scenario stays unmarked — no write-pass call, no spaCy
loaders. Structural-only per the standing rule: IDs, row membership, order,
NULL-vs-value shapes, and the zero-writes count proof — never prose.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from conftest import NOW, V1_CONFIG, run_structural

from app import db

# A wall-clock anchor: memories/runs insert with DB now() (real time), while
# the suite's NOW fixture (2026-07-20) sits in the past. Reflections seeded
# with created_at around WALL land before/after those rows deterministically.
WALL_FUTURE = datetime.now(timezone.utc) + timedelta(hours=6)

STATE_CONFIG = dict(V1_CONFIG)


async def _bare_agent(ctx, name: str):
    """An agent row with ONLY a name — every nullable column NULL, config
    NULL: the normalization fixture make_agent (which pins rigidity, seed,
    and goal) cannot produce."""
    row = await ctx.fetchrow(
        "INSERT INTO agents (name) VALUES (%s) RETURNING agent_id", name
    )
    return row[0]


def _reflection_run(agent_id, *, outcome="completed", error=None, **overrides):
    """A migration-007 run record with explicit fixture values (the
    hand-inserted worker-accounting row; endpoint reflects write none)."""
    fields = {
        "agent_id": agent_id,
        "outcome": outcome,
        "error": error,
        "reflections_written": 2,
        "dropped_ungrounded": 1,
        "consolidation_ran": True,
        "consolidation_failed": False,
        "rrr": 0.25,
        "rrr_blocked": False,
        "pruned_components": 0,
        "evicted_cache_rows": 3,
        "pressure_before": 1.2,
        "pressure_after": 0.0,
        "reflect_ms": 10.0,
        "consolidation_ms": 5.0,
        "insert_ms": 1.0,
        "total_ms": 16.0,
        "reflect_input_tokens": 100,
        "reflect_output_tokens": 40,
        "consolidation_input_tokens": 20,
        "consolidation_output_tokens": 10,
    }
    fields.update(overrides)
    return db.ReflectionRunRecord(**fields)


def _compiler_run(agent_id, *, outcome="completed", error=None, **overrides):
    fields = {
        "agent_id": agent_id,
        "outcome": outcome,
        "error": error,
        "pairs_compiled": 2,
        "pairs_failed": 0,
        "passthrough_keys_dropped": 1,
        "input_tokens": 50,
        "output_tokens": 20,
        "total_ms": 8.0,
    }
    fields.update(overrides)
    return db.CompilerRunRecord(**fields)


# ---------------------------------------------------------------------------
# The route ladder + the wire baseline
# ---------------------------------------------------------------------------


def test_route_404_unknown_agent_and_422_bounds(scene):
    """404 on an unknown agent (the agent-memories shape); 422 when
    runs_limit leaves Query(ge=1, le=1000) — both ends."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            r404 = await client.get(f"/v1/agents/{uuid4()}/state")
            assert r404.status_code == 404

            agent = await ctx.make_agent("o-ladder", STATE_CONFIG)
            low = await client.get(f"/v1/agents/{agent}/state?runs_limit=0")
            assert low.status_code == 422
            high = await client.get(f"/v1/agents/{agent}/state?runs_limit=1001")
            assert high.status_code == 422

    run_structural(scene, scenario)


def test_empty_agent_wire_baseline(scene):
    """A name-only agent over the wire: every nullable scalar PRESENT and
    null (the tri-state contract — key present, value null, never absent),
    config normalized {} for NULL, identity never compiled => present-null
    version, pressure 0.0, all four lists empty, runs_limit echoed."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await _bare_agent(ctx, "o-bare")
        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.get(f"/v1/agents/{agent}/state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == str(agent)
        assert body["name"] == "o-bare"
        for key in (
            "seed_identity",
            "rigidity",
            "diagnosticity_goal",
            "identity_version",
            "identity_compiled_at",
        ):
            assert key in body and body[key] is None
        assert body["config"] == {}
        assert body["reflection_pressure"] == 0.0
        assert body["reflections"] == []
        assert body["compiled_bundles"] == []
        assert body["reflection_runs"] == []
        assert body["compiler_runs"] == []
        assert body["runs_limit"] == 100  # the Query default, echoed
        assert body["total_ms"] > 0.0

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The pressure gauge (service-side hand math)
# ---------------------------------------------------------------------------


def test_pressure_hand_math_and_norm_override(scene):
    """pressure = sum(COALESCE(importance_raw, neutral)) / norm over live
    memories created after the last reflection EVENT: hand-chosen
    importances at the 10.0 default; a NULL-importance row contributes
    importance_neutral (0.5); a per-agent norm override rescales; a
    reflection row created AFTER the memories zeroes the gauge (any
    reflection row — the epoch threshold is created_at, service time)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-pressure", STATE_CONFIG)
        await ctx.seed(agent, "toll dispute at the ford", NOW, importance=0.6)
        await ctx.seed(
            agent, "a cart lost a wheel", NOW + timedelta(hours=1), importance=0.4
        )
        await ctx.seed(
            agent,
            "unscored shape",
            NOW + timedelta(hours=2),
            importance=None,
        )

        service = ctx.retrieval()
        state = await service.agent_state(agent, 100)
        assert state.reflection_pressure == pytest.approx((0.6 + 0.4 + 0.5) / 10.0)

        # Per-agent norm override: same mass, different divisor.
        overridden = await ctx.make_agent(
            "o-pressure-norm",
            {**STATE_CONFIG, "reflection_pressure_norm": 5.0},
        )
        await ctx.seed(overridden, "the same mass", NOW, importance=0.6)
        state2 = await service.agent_state(overridden, 100)
        assert state2.reflection_pressure == pytest.approx(0.6 / 5.0)

        # A reflection EVENT after every memory row resets the epoch — even
        # an already-invalidated one (live or absorbed: the last reflect
        # event counts).
        await ctx.seed_reflection(
            agent,
            "the keeper distrusts carts",
            NOW,
            created_at=WALL_FUTURE,
            invalid_at=WALL_FUTURE,
        )
        state3 = await service.agent_state(agent, 100)
        assert state3.reflection_pressure == 0.0

    run_structural(scene, scenario)


def test_pressure_norm_misuse_raises(scene):
    """reflection_pressure_norm <= 0 raises the reflect verb's ValueError —
    one rule at both gauges, never a silent clamp."""

    async def scenario(ctx):
        agent = await ctx.make_agent(
            "o-norm-zero", {**STATE_CONFIG, "reflection_pressure_norm": 0.0}
        )
        with pytest.raises(ValueError, match="reflection_pressure_norm"):
            await ctx.retrieval().agent_state(agent, 100)

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Beliefs + bundles (liveness, order, verbatim passthrough)
# ---------------------------------------------------------------------------


def test_reflections_live_only_ruled_order_and_provenance(scene):
    """Live beliefs only (an invalidated row absent), BOTH identity_relevant
    values carried, the ruled compiler-window order (valid_at DESC,
    created_at DESC, reflection_id), and source_memory_ids round-tripped."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-beliefs", STATE_CONFIG)
        seeded = await ctx.seed(agent, "a lantern shattered", NOW)
        older = await ctx.seed_reflection(
            agent,
            "strangers test the keeper",
            NOW - timedelta(days=2),
            identity_relevant=True,
            source_memory_ids=(seeded.memory_id,),
            created_at=NOW - timedelta(days=2),
        )
        newer = await ctx.seed_reflection(
            agent,
            "carts break at the ford",
            NOW - timedelta(days=1),
            identity_relevant=False,
            created_at=NOW - timedelta(days=1),
        )
        await ctx.seed_reflection(
            agent,
            "an absorbed belief",
            NOW,
            created_at=NOW,
            invalid_at=NOW + timedelta(hours=1),
        )

        state = await ctx.retrieval().agent_state(agent, 100)
        assert [r.reflection_id for r in state.reflections] == [newer, older]
        by_id = {r.reflection_id: r for r in state.reflections}
        assert by_id[older].identity_relevant is True
        assert by_id[newer].identity_relevant is False
        assert by_id[older].source_memory_ids == [seeded.memory_id]
        assert by_id[newer].source_memory_ids == []

    run_structural(scene, scenario)


def test_bundles_newest_per_pair_derived_liveness_passthrough(scene):
    """The newest bundle wins per (reflection, scene_type); a bundle on an
    invalidated reflection is EXCLUDED (liveness derived, no stored flag);
    nested passthrough round-trips verbatim; outer order = belief window
    order then scene_type."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-bundles", STATE_CONFIG)
        newer_belief = await ctx.seed_reflection(
            agent, "belief newer", NOW, created_at=NOW
        )
        older_belief = await ctx.seed_reflection(
            agent,
            "belief older",
            NOW - timedelta(days=1),
            created_at=NOW - timedelta(days=1),
        )
        dead_belief = await ctx.seed_reflection(
            agent,
            "belief dead",
            NOW - timedelta(days=2),
            created_at=NOW - timedelta(days=2),
            invalid_at=NOW,
        )

        stale = await ctx.seed_bundle(
            agent,
            newer_belief,
            scene_type="tavern",
            w_relevance=2.0,
            created_at=NOW - timedelta(hours=2),
        )
        fresh = await ctx.seed_bundle(
            agent,
            newer_belief,
            scene_type="tavern",
            w_relevance=3.0,
            passthrough={"studio": {"tone": "wary", "depth": 2}},
            created_at=NOW - timedelta(hours=1),
        )
        market = await ctx.seed_bundle(
            agent, newer_belief, scene_type="market", created_at=NOW
        )
        old_pair = await ctx.seed_bundle(
            agent, older_belief, scene_type="tavern", created_at=NOW
        )
        await ctx.seed_bundle(agent, dead_belief, scene_type="tavern", created_at=NOW)

        state = await ctx.retrieval().agent_state(agent, 100)
        # Belief window order (newer belief first), then scene_type asc.
        assert [b.bundle_id for b in state.compiled_bundles] == [
            market,
            fresh,
            old_pair,
        ]
        assert stale not in {b.bundle_id for b in state.compiled_bundles}
        winner = next(b for b in state.compiled_bundles if b.bundle_id == fresh)
        assert winner.w_relevance == 3.0
        assert winner.passthrough == {"studio": {"tone": "wary", "depth": 2}}

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# The run logs (full column mirrors, newest first, per-list limit)
# ---------------------------------------------------------------------------


def test_run_logs_mirror_order_and_limit(scene):
    """Both logs come back newest first with EVERY migration column carried
    (present-null rrr/error/timings on a failed row — the tri-state), and
    runs_limit caps each list independently."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-runs", STATE_CONFIG)
        await db.insert_reflection_run(ctx.pool, _reflection_run(agent))
        await db.insert_reflection_run(
            ctx.pool,
            _reflection_run(
                agent,
                outcome="failed",
                error="provider unreachable",
                rrr=None,
                reflect_ms=None,
                consolidation_ms=None,
                insert_ms=None,
                total_ms=None,
                pressure_after=None,
            ),
        )
        await db.insert_compiler_run(ctx.pool, _compiler_run(agent))
        await db.insert_compiler_run(
            ctx.pool,
            _compiler_run(agent, outcome="failed", error="role missing", total_ms=None),
        )

        state = await ctx.retrieval().agent_state(agent, 100)
        assert len(state.reflection_runs) == 2
        assert len(state.compiler_runs) == 2
        # Newest first: created_at non-increasing, and the head is the
        # failed (second-inserted) row in both logs.
        r_times = [r.created_at for r in state.reflection_runs]
        assert r_times == sorted(r_times, reverse=True)
        head = state.reflection_runs[0]
        assert head.outcome == "failed"
        assert head.error == "provider unreachable"
        assert head.rrr is None
        assert head.reflect_ms is None
        assert head.total_ms is None
        assert head.pressure_after is None
        # The completed row carries its full instrumentation verbatim.
        done = state.reflection_runs[1]
        assert done.outcome == "completed"
        assert done.reflections_written == 2
        assert done.rrr == pytest.approx(0.25)
        assert done.evicted_cache_rows == 3
        assert done.reflect_input_tokens == 100
        c_head = state.compiler_runs[0]
        assert c_head.outcome == "failed"
        assert c_head.error == "role missing"
        assert c_head.total_ms is None
        assert state.compiler_runs[1].pairs_compiled == 2

        capped = await ctx.retrieval().agent_state(agent, 1)
        assert len(capped.reflection_runs) == 1
        assert len(capped.compiler_runs) == 1
        assert capped.reflection_runs[0].outcome == "failed"
        assert capped.runs_limit == 1

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Identity currency
# ---------------------------------------------------------------------------


def test_identity_version_is_the_newest_row(scene):
    """identity_version/identity_compiled_at = the newest identity_documents
    row; an older second version never wins; the read never compiles a
    document itself (the never-compiled case is the wire baseline test)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-identity", STATE_CONFIG)
        await ctx.execute(
            "INSERT INTO identity_documents (agent_id, rendered_text, "
            "identity_version, created_at) VALUES (%s, 'old render', 'aaa', %s)",
            agent,
            NOW - timedelta(days=1),
        )
        await ctx.execute(
            "INSERT INTO identity_documents (agent_id, rendered_text, "
            "identity_version, created_at) VALUES (%s, 'new render', 'bbb', %s)",
            agent,
            NOW,
        )
        state = await ctx.retrieval().agent_state(agent, 100)
        assert state.identity_version == "bbb"
        assert state.identity_compiled_at == NOW

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# Pass-through by ruling + zero writes
# ---------------------------------------------------------------------------


def test_route_json_equals_service_json(scene):
    """The pass-through proof (the verify_read_path CapturingRetrieval
    pattern): the route's JSON is exactly the serialization of the result
    the service returned — the route adds and drops nothing."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("o-passthru", STATE_CONFIG)
        await ctx.seed(agent, "a toll argument", NOW, importance=0.7)
        belief = await ctx.seed_reflection(
            agent, "merchants push their luck", NOW, created_at=NOW
        )
        await ctx.seed_bundle(
            agent, belief, scene_type="tavern", passthrough={"k": [1, 2]}
        )
        await db.insert_reflection_run(ctx.pool, _reflection_run(agent))
        await db.insert_compiler_run(ctx.pool, _compiler_run(agent))

        class CapturingRetrieval:
            def __init__(self, inner):
                self._inner = inner
                self.last = None

            async def agent_state(self, agent_id, runs_limit):
                self.last = await self._inner.agent_state(agent_id, runs_limit)
                return self.last

        capture = CapturingRetrieval(ctx.retrieval())
        api_module.app.state.retrieval = capture
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.get(f"/v1/agents/{agent}/state?runs_limit=7")
        assert resp.status_code == 200
        assert capture.last is not None
        assert resp.json() == json.loads(capture.last.model_dump_json())
        assert resp.json()["runs_limit"] == 7

    run_structural(scene, scenario)


def test_zero_writes(scene):
    """The read writes NOTHING: row counts across every table it touches
    (and the caches a read could plausibly warm) are byte-identical
    before/after — identity via pure SELECT (never ensure_), pressure
    computed-never-stored."""

    async def scenario(ctx):
        agent = await ctx.make_agent("o-zero-writes", STATE_CONFIG)
        await ctx.seed(agent, "quiet evening at the ford", NOW)
        belief = await ctx.seed_reflection(
            agent, "evenings stay quiet", NOW, created_at=NOW
        )
        await ctx.seed_bundle(agent, belief)
        await db.insert_reflection_run(ctx.pool, _reflection_run(agent))
        await db.insert_compiler_run(ctx.pool, _compiler_run(agent))

        tables = (
            "agents",
            "memories",
            "memory_details",
            "identity_documents",
            "reconstruction_cache",
            "reflections",
            "compiled_bundles",
            "reflection_runs",
            "compiler_runs",
        )

        async def counts():
            return [
                (await ctx.fetchrow(f"SELECT count(*) FROM {t}"))[0] for t in tables
            ]

        before = await counts()
        state = await ctx.retrieval().agent_state(agent, 100)
        assert state.identity_version is None  # never compiled — and STAYS so
        after = await counts()
        assert before == after

    run_structural(scene, scenario)
