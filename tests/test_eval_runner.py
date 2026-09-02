"""Set H — eval-harness stage 2: the runner's structural surface
(docs\\eval-harness.md stage 2; docs\\test-suite.md discipline).

Covers the four stage-2 pieces at the structural level: the scenario
schema/loader (strictness — a typo'd fixture fails at load, never a silently
dropped assertion), the promoted scratch provisioning (the product-DB hard
refusal fires before any connection), the `drift_observer` capture seam
(sample-per-checked-item; attaching it perturbs nothing the pre-seam floor
asserted), and the in-process `run_scenarios` core (report structure only —
never prose). The committed fixture files under `data\\eval\\` are parsed as
a canary so fixture drift fails here, not at demo time.

Unmarked scenarios seed at the db layer (no NLP loaders); the one
`run_scenarios` end-to-end drives the real write pass and carries the `nlp`
mark. Judged evals stay out of this folder (test-suite.md) — the runner's
judged surface arrives at stage 3 and lives in run artifacts.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from conftest import NOW, RECON_CONFIG, by_id, run_structural
from pydantic import ValidationError

from app import reconstruction
from app.eval_scenarios import (
    ExpectedIds,
    Scenario,
    assert_corpus_shape,
    check_expected,
    load_scenario_files,
    load_scenarios,
)
from app.schemas import DialogueInitRequest
from app.scratch_db import (
    PRODUCT_DB,
    ScratchUriError,
    drop_scratch,
    provision_scratch,
    scratch_uri,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURE = REPO_ROOT / "data" / "eval" / "scenarios" / "smoke.jsonl"
CORPUS_FIXTURE = REPO_ROOT / "data" / "eval" / "corpora" / "drift-fixture.jsonl"

# A host from TEST-NET-1 (RFC 5737): if a refusal ever tried to connect, the
# dial-out would hang to timeout instead of raising instantly.
UNREACHABLE_URI = "postgresql://u:p@192.0.2.1:5432/postgres"

MINIMAL = {
    "scenario_id": "inline-minimal",
    "agent": {
        "name": "set-h-inline",
        "seed_identity": "A keeper of small facts.",
        "diagnosticity_goal": "what changed and who changed it",
        "config": {
            "decay_classes": {"episodic": 86400.0, "semantic": 604800.0},
            "decay_class_default": "semantic",
        },
    },
    "events": [
        {"kind": "as_of", "at": "2026-06-01T09:00:00+00:00"},
        {"kind": "observe", "text": "The well rope frayed and was replaced."},
        {"kind": "observe", "text": "A grey cat took up residence in the loft."},
        {
            "kind": "correct",
            "memory_ref": 0,
            "content": "The well rope frayed; the replacement is still on order.",
        },
        {"kind": "pin", "memory_ref": 1, "pinned": True},
        {
            "kind": "utterance",
            "text": "What happened to the well rope, and who lives in the loft?",
            "k": 2,
            "expect": {"present": [0, 1]},
        },
    ],
}


# ---------------------------------------------------------------------------
# Pure: fixture canary, loader strictness, check arithmetic, refusals
# ---------------------------------------------------------------------------


def test_fixture_files_parse_census_and_corpus_shape():
    """The committed fixtures stay loadable and shaped as authored: five
    smoke scenarios covering every event kind with exactly one held-out;
    the drift corpus is the observe/as_of subset — and a smoke scenario is
    NOT corpus-shaped (the restriction is stated, not silent)."""
    smoke = load_scenarios(SMOKE_FIXTURE)
    assert [s.scenario_id for s in smoke] == [
        "ford-retrieval-basics",
        "millers-correction",
        "frost-pin-and-decay",
        "market-context",
        "held-out-probe",
    ]
    assert [s.held_out for s in smoke] == [False, False, False, False, True]
    kinds = {event.kind for s in smoke for event in s.events}
    assert kinds == {
        "observe",
        "utterance",
        "scene",
        "correct",
        "pin",
        "as_of",
        "context",
    }

    corpus = load_scenarios(CORPUS_FIXTURE)
    assert len(corpus) == 1
    assert_corpus_shape(corpus[0])
    assert corpus[0].observe_count == 7
    with pytest.raises(ValueError, match="non-corpus event"):
        assert_corpus_shape(smoke[0])

    both = load_scenario_files([SMOKE_FIXTURE, CORPUS_FIXTURE])
    assert len(both) == 6


def test_loader_strictness(tmp_path):
    """extra=forbid + ref/timezone validation: every authoring mistake dies
    at load with file:line context."""
    with pytest.raises(ValidationError):
        Scenario.model_validate({**MINIMAL, "typo_field": 1})
    with pytest.raises(ValidationError):
        Scenario.model_validate({**MINIMAL, "events": [{"kind": "dance", "text": "x"}]})
    with pytest.raises(ValidationError, match="before that observe occurs"):
        Scenario.model_validate(
            {
                **MINIMAL,
                "events": [
                    {"kind": "utterance", "text": "x", "expect": {"present": [0]}},
                    {"kind": "observe", "text": "y"},
                ],
            }
        )
    with pytest.raises(ValidationError, match="only 1 observe"):
        Scenario.model_validate(
            {
                **MINIMAL,
                "events": [
                    {"kind": "observe", "text": "y"},
                    {"kind": "pin", "memory_ref": 1},
                ],
            }
        )
    with pytest.raises(ValidationError, match="timezone-aware"):
        Scenario.model_validate(
            {**MINIMAL, "events": [{"kind": "as_of", "at": "2026-06-01T09:00:00"}]}
        )
    with pytest.raises(ValidationError, match="both expect.present"):
        Scenario.model_validate(
            {
                **MINIMAL,
                "events": [
                    {"kind": "observe", "text": "y"},
                    {
                        "kind": "utterance",
                        "text": "x",
                        "expect": {"present": [0], "absent": [0]},
                    },
                ],
            }
        )

    bad_json = tmp_path / "bad.jsonl"
    bad_json.write_text('{"scenario_id": broken\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"bad\.jsonl:1"):
        load_scenarios(bad_json)

    dup_a = tmp_path / "a.jsonl"
    dup_b = tmp_path / "b.jsonl"
    line = json.dumps(MINIMAL)
    dup_a.write_text(line + "\n", encoding="utf-8")
    dup_b.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate scenario_id"):
        load_scenario_files([dup_a, dup_b])


def test_check_expected_arithmetic():
    from uuid import uuid4

    a, b, c = uuid4(), uuid4(), uuid4()
    observed = [a, b, c]
    hit = check_expected(ExpectedIds(present=[0], absent=[2]), [a, b], observed)
    assert hit == {"passed": True, "missing": [], "unexpected": []}
    miss = check_expected(ExpectedIds(present=[2]), [a], observed)
    assert miss == {"passed": False, "missing": [str(c)], "unexpected": []}
    violation = check_expected(ExpectedIds(absent=[0]), [a], observed)
    assert violation == {"passed": False, "missing": [], "unexpected": [str(a)]}
    empty = check_expected(ExpectedIds(), [], observed)
    assert empty["passed"] is True


def test_product_db_refusal_and_shim_identity():
    """The hard refusal fires by NAME, before any connection is attempted
    (an unreachable TEST-NET host would otherwise hang to timeout), and the
    promotion is a re-export, not a fork."""
    with pytest.raises(ScratchUriError, match="product database"):
        provision_scratch(UNREACHABLE_URI, PRODUCT_DB)
    with pytest.raises(ScratchUriError, match="product database"):
        drop_scratch(UNREACHABLE_URI, PRODUCT_DB)
    with pytest.raises(ScratchUriError, match="unsafe scratch database name"):
        provision_scratch(UNREACHABLE_URI, "bad-name; drop")

    import scratch_uri as shim

    assert shim.scratch_uri is scratch_uri
    assert shim.ScratchUriError is ScratchUriError


# ---------------------------------------------------------------------------
# DB-backed: provisioning round-trip + the capture seam
# ---------------------------------------------------------------------------


def test_provision_drop_roundtrip(suite_env):
    """provision creates + fully migrates; drop removes. pid-scoped name so
    an overlapping run can never collide (the conftest convention)."""
    name = f"twicetold_evaltest_{os.getpid()}"
    base = suite_env.database_uri
    try:
        uri = provision_scratch(base, name)
        with psycopg.connect(uri, connect_timeout=3) as conn:
            applied = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()
        assert applied[0] == 8  # 001-008 (008: parameter compiler, 2026-08-17)
        drop_scratch(base, name)
        admin = scratch_uri(base, "postgres")
        with psycopg.connect(admin, connect_timeout=3, autocommit=True) as conn:
            row = conn.execute(
                "SELECT count(*) FROM pg_database WHERE datname = %s", (name,)
            ).fetchone()
        assert row[0] == 0
    finally:
        drop_scratch(base, name)


def _recon_request(agent_id, version, basis) -> DialogueInitRequest:
    return DialogueInitRequest(
        agent_id=agent_id,
        query_text="What broke at the ford?",
        as_of=basis,
        scene_started_at=basis,
        identity_version=version,
    )


async def _boundary(ctx, agent) -> str:
    from app.schemas import SceneBoundaryEvent

    result = await ctx.ingest().scene_boundary(
        SceneBoundaryEvent(agent_id=agent, client_timestamp=NOW)
    )
    return result.identity_version


def test_drift_observer_default_none():
    assert reconstruction.drift_observer is None


def test_drift_observer_happy_path(scene):
    """One sample per checked item at the drift computation; attaching the
    observer perturbs nothing the Set C floor asserts; try/finally restores
    the None default."""

    async def scenario(ctx):
        agent = await ctx.make_agent("h-observer", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent,
            "The cart broke at the ford and blocked the road for hours.",
            NOW - timedelta(days=10),
            decay_class="semantic",
        )
        fresh = await ctx.seed(
            agent, "Mara sharpened a blade at the forge.", NOW - timedelta(hours=1)
        )
        samples: list[tuple] = []
        reconstruction.drift_observer = lambda mid, dist, refused: samples.append(
            (mid, dist, refused)
        )
        try:
            result = await ctx.retrieval().retrieve_dialogue_init(
                _recon_request(agent, version, NOW)
            )
        finally:
            reconstruction.drift_observer = None
        assert reconstruction.drift_observer is None

        # Exactly the one past-theta unpinned row was checked.
        assert [(mid, refused) for mid, _, refused in samples] == [
            (old.memory_id, False)
        ]
        distance = samples[0][1]
        assert 0.0 <= distance <= 2.0 and distance <= 0.35
        # The serve outcome is the Set C shape — observer presence changed
        # nothing structural.
        items = by_id(result)
        assert items[old.memory_id].read_mode == "reconstructed"
        assert items[fresh.memory_id].read_mode == "verbatim"
        inst = result.instrumentation
        assert inst.write_backs == 1 and inst.drift_refusals == 0

    run_structural(scene, scenario)


def test_drift_observer_refusal_path(scene):
    """A drifting retelling: the observer's refused flag IS the serving
    decision (same computation, same threshold), and the refusal count
    matches the turn's instrumentation."""

    async def scenario(ctx):
        from app.providers import DriftingReconstructionProvider

        agent = await ctx.make_agent("h-refusal", RECON_CONFIG)
        version = await _boundary(ctx, agent)
        old = await ctx.seed(
            agent,
            "The cart broke at the ford and blocked the road for hours.",
            NOW - timedelta(days=10),
            decay_class="semantic",
        )
        samples: list[tuple] = []
        reconstruction.drift_observer = lambda mid, dist, refused: samples.append(
            (mid, dist, refused)
        )
        try:
            result = await ctx.retrieval(
                reconstruction=DriftingReconstructionProvider()
            ).retrieve_dialogue_init(_recon_request(agent, version, NOW))
        finally:
            reconstruction.drift_observer = None

        assert [(mid, refused) for mid, _, refused in samples] == [
            (old.memory_id, True)
        ]
        assert samples[0][1] > 0.35
        inst = result.instrumentation
        assert inst.drift_refusals == 1
        assert inst.drift_refusals == sum(1 for _, _, r in samples if r)
        # Refusal caching: the served prior text is pinned under the key.
        assert len(await ctx.cache_rows(old.memory_id)) == 1

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# End-to-end: the run core in-process (real write pass -> nlp mark)
# ---------------------------------------------------------------------------


@pytest.mark.nlp
def test_run_scenarios_end_to_end(scene):
    """The `run` core on the suite's scratch settings: report structure,
    honest-None ratios, keyless USD None, JSON-serializable artifact.
    Never asserts on prose."""
    from app.eval_runner import run_scenarios

    scenario = Scenario.model_validate(MINIMAL)
    report = asyncio.run(
        run_scenarios(scene.settings, [scenario], include_held_out=False, k=None),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert report["checks_passed_total"] == 1
    assert report["checks_failed_total"] == 0
    assert report["excluded_held_out"] == []
    (row,) = report["scenarios"]
    assert row["event_counts"] == {
        "as_of": 1,
        "observe": 2,
        "correct": 1,
        "pin": 1,
        "utterance": 1,
    }
    assert [c["passed"] for c in row["checks"]] == [True]
    assert len(row["memories"]) == 2
    for memory in row["memories"]:
        for key in ("gist_precision", "detail_recall", "fabrication_rate"):
            assert key in memory
            assert memory[key] is None or isinstance(memory[key], (int, float))
        assert memory["memory_id"] and memory["live_detail_id"]
    # Keyless suite settings: token counts always, USD honestly None.
    assert report["cost"]["dialogue"]["usd"] is None
    assert report["cost"]["embedding"]["usd"] is None
    json.dumps(report)  # the artifact must serialize as-is

    run_structural(scene, lambda ctx: _assert_no_eval_rows(ctx))


async def _assert_no_eval_rows(ctx):
    """Nothing eval-related persists beyond the ordinary product rows the
    replayed events themselves wrote (ruled: no eval state in Postgres)."""
    tables = await ctx.fetchall(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    assert [t[0] for t in tables] == [
        "agents",
        # 008 (parameter compiler, 2026-08-17) added the bundle + run-log
        # tables — the same mechanical census bump ('compiled' sorts before
        # 'compiler' at char 8, both before 'corrections'; confirmed on the
        # migrated scratch). The no-eval-rows claim this helper asserts is
        # untouched by 008.
        "compiled_bundles",
        "compiler_runs",
        "corrections",
        "identity_components",
        "identity_documents",
        "memories",
        "memory_details",
        # 006 (deferred writes, 2026-08-12) added the run-log table — the
        # mechanical census bump every migration makes here; the no-eval-rows
        # claim this helper asserts is untouched by 006.
        "memory_enrichment_runs",
        "memory_fact_versions",
        "memory_gist_spans",
        "reconstruction_cache",
        # 007 (reflection, 2026-08-15) added the worker run-log table — the
        # same mechanical census bump (sorts BEFORE 'reflections' under the
        # DB collation; confirmed on the migrated scratch). The no-eval-rows
        # claim this helper asserts is untouched by 007.
        "reflection_runs",
        "reflections",
        "schema_migrations",
    ]
