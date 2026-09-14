"""Set K — deferred write processing (deferred-writes.md; migration 006,
ruled 2026-08-12).

The worker path is exercised through `drain()` — the deterministic entry, no
timers — against pending rows seeded at the db layer (`Ctx.seed_pending`:
NULL write-call scalars, raw text as the `original` head, persisted trigger
names), so every scenario but the end-to-end observe stays unmarked (the
worker reads spans/triggers from the DB and never touches the spaCy
loaders). Structural-only, per the standing rule: write_cause chains, row
state, run-log outcomes, byte-identity — never prose judgment (the fake
render's byte shape is a fixture property).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import NOW, V1_CONFIG, item_ids, run_structural

T_OBS = "Bram shattered the lantern at the ford gate."


def _read_request(agent_id, text=T_OBS, **overrides):
    from app.schemas import DialogueInitRequest

    base = dict(agent_id=agent_id, query_text=text, as_of=NOW)
    base.update(overrides)
    return DialogueInitRequest(**base)


async def _memories_row(ctx, memory_id):
    return await ctx.fetchrow(
        "SELECT importance_raw, typology, typology_confidence, typology_source, "
        "scoring_failed, escalation_failed, enrichment_pending, "
        "enrichment_attempts, enrichment_pending_triggers "
        "FROM memories WHERE memory_id = %s",
        memory_id,
    )


async def _runs(ctx, memory_id):
    return await ctx.fetchall(
        "SELECT attempt, outcome, error, escalation_failed, embedding_repaired "
        "FROM memory_enrichment_runs WHERE memory_id = %s "
        "ORDER BY created_at, attempt",
        memory_id,
    )


def test_completion_happy_path_and_redrain_noop(scene):
    """The one-shot completion: scalars filled NULL->value, the raw head
    superseded by the 'enrichment' head, the cache evicted, a `completed`
    run row — and a re-drain is a 0-row no-op with the chain byte-stable
    (idempotency by the row-state guard)."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("k-happy", V1_CONFIG)
        seeded = await ctx.seed_pending(
            agent, T_OBS, NOW - timedelta(hours=1), triggers=("thin_gist",)
        )
        m = seeded.memory_id
        await db.insert_cache_row(ctx.pool, m, "vhash|b0", "stale cached telling")

        before = await _memories_row(ctx, m)
        assert before[:4] == (None, None, None, None)  # NULL scalars = pending
        assert before[6] is True and before[7] == 0
        assert before[8] == ["thin_gist"]

        worker = ctx.worker()
        assert await worker.drain() == 1

        after = await _memories_row(ctx, m)
        assert after[0] is not None and 0.0 <= after[0] <= 1.0  # importance filled
        assert after[1] is not None and after[3] == "inferred"  # typology filled
        assert after[4] is False  # scoring_failed: the call succeeded
        assert after[6] is False and after[7] == 1  # pending cleared, 1 attempt
        assert after[8] == ["thin_gist"]  # persisted triggers never cleared

        chain = await ctx.chain(m)
        assert [(r[0], r[3] is None) for r in chain] == [
            ("original", False),  # the raw head, superseded
            ("enrichment", True),  # the worker's render, live
        ]
        assert chain[0][1] == T_OBS  # the raw head IS the observation text
        assert chain[1][1] == f"[fake render] {T_OBS}"  # deterministic fake
        assert chain[0][3] == chain[1][2]  # supersede instant == new valid_at

        assert await ctx.cache_rows(m) == {}  # chain writer evicts, always
        runs = await _runs(ctx, m)
        assert [(r[0], r[1]) for r in runs] == [(1, "completed")]

        # Re-drain: nothing pending — no rows handled, chain byte-stable.
        assert await worker.drain() == 0
        assert await ctx.chain(m) == chain
        assert await _runs(ctx, m) == runs

    run_structural(scene, scenario)


def test_declared_typology_survives_completion(scene):
    """The COALESCE proof: a declared typology (stored at insert) is never
    overwritten by the worker — completion fills importance only."""

    async def scenario(ctx):
        agent = await ctx.make_agent("k-declared", V1_CONFIG)
        seeded = await ctx.seed_pending(
            agent,
            T_OBS,
            NOW - timedelta(hours=1),
            declared_typology="told",
            declared_confidence=0.7,
        )
        m = seeded.memory_id
        assert await ctx.worker().drain() == 1
        row = await _memories_row(ctx, m)
        assert row[0] is not None  # importance filled
        assert (row[1], row[2], row[3]) == ("told", 0.7, "declared")  # untouched

    run_structural(scene, scenario)


def test_escalation_novel_component_appends_add_only(scene):
    """A worker escalation that surfaces a novel entity grows
    identity_components and appends its mention span (add-only; stored span
    rows byte-untouched) — and the fact chain does NOT supersede: sync
    parity, escalation novels become components, never memory entities."""

    async def scenario(ctx):
        text = "Bram hid the ledger stone beneath the ford gate."
        agent = await ctx.make_agent("k-novel", V1_CONFIG)
        seeded = await ctx.seed_pending(
            agent,
            text,
            NOW - timedelta(hours=1),
            triggers=("thin_gist",),
            spans=((0, 4),),  # a stored base span (Bram)
            entities=["Bram"],
        )
        m = seeded.memory_id
        spans_before = await ctx.fetchall(
            "SELECT span_id, start_char, end_char FROM memory_gist_spans "
            "WHERE memory_id = %s ORDER BY start_char",
            m,
        )

        from app.providers import NoveltyEscalationProvider

        assert await ctx.worker(escalation=NoveltyEscalationProvider()).drain() == 1

        comp = await ctx.fetchrow(
            "SELECT component_id, category FROM identity_components "
            "WHERE agent_id = %s AND canonical = %s",
            agent,
            "ledger stone",
        )
        assert comp is not None and comp[1] == "object"

        spans_after = await ctx.fetchall(
            "SELECT span_id, start_char, end_char, matched_component_id "
            "FROM memory_gist_spans WHERE memory_id = %s ORDER BY start_char",
            m,
        )
        # Add-only: the stored span row survives byte-identically...
        assert [s[0] for s in spans_before] == [
            s[0] for s in spans_after if s[3] != comp[0]
        ]
        # ...and exactly one new span points at the novel component's mention.
        novel_spans = [s for s in spans_after if s[3] == comp[0]]
        start = text.index("ledger stone")
        assert [(s[1], s[2]) for s in novel_spans] == [
            (start, start + len("ledger stone"))
        ]

        # Sync parity: no fact supersede — one live 'original' fact row,
        # entities unchanged.
        facts = await ctx.fact_chain(m)
        assert [(f[0], f[3] is None) for f in facts] == [("original", True)]
        assert facts[0][5] == ["Bram"]

    run_structural(scene, scenario)


def test_failed_attempt_stays_pending_then_completes(scene):
    """Retry-later failure policy: a failed write call records a `failed`
    run row and leaves the row pending (scalars still NULL); the next drain
    completes it."""

    async def scenario(ctx):
        from app.providers import FlakyWriteProvider

        agent = await ctx.make_agent("k-flaky", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id

        worker = ctx.worker(write=FlakyWriteProvider(1))
        assert await worker.drain() == 1  # the failure was handled (recorded)
        row = await _memories_row(ctx, m)
        assert row[0] is None and row[6] is True and row[7] == 1  # still pending
        assert [(r[0], r[1]) for r in await _runs(ctx, m)] == [(1, "failed")]
        assert [(c[0], c[3] is None) for c in await ctx.chain(m)] == [
            ("original", True)  # no chain write on a failed attempt
        ]

        assert await worker.drain() == 1  # second attempt completes
        row = await _memories_row(ctx, m)
        assert row[0] is not None and row[6] is False and row[7] == 2
        assert [(r[0], r[1]) for r in await _runs(ctx, m)] == [
            (1, "failed"),
            (2, "completed"),
        ]

    run_structural(scene, scenario)


def test_terminal_degrade_matches_sync_end_state(scene):
    """The attempt that spends the budget terminal-fills the row
    byte-equivalent to today's sync scoring-failed end-state: neutral
    importance, scoring_failed, the config-default typology, raw head still
    live — nothing chain-written."""

    async def scenario(ctx):
        from app.providers import FailingWriteProvider

        agent = await ctx.make_agent("k-terminal", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id

        worker = ctx.worker(
            write=FailingWriteProvider(), defaults={"deferred_max_attempts": 1.0}
        )
        assert await worker.drain() == 1

        row = await _memories_row(ctx, m)
        neutral = ctx.settings.defaults["importance_neutral"]
        conf_default = ctx.settings.defaults["typology_confidence_default"]
        assert row[0] == neutral  # the sync fallback value, not NULL
        assert row[4] is True  # scoring_failed — the sync flag
        assert (row[1], row[2], row[3]) == ("observed", conf_default, "inferred")
        assert row[5] is False  # escalation never ran: flag stays honest-false
        assert row[6] is False  # pending cleared — terminal, not retryable
        assert [(c[0], c[3] is None) for c in await ctx.chain(m)] == [
            ("original", True)  # the raw head stays the live telling
        ]
        assert [(r[0], r[1]) for r in await _runs(ctx, m)] == [(1, "terminal_degraded")]

    run_structural(scene, scenario)


def test_superseded_head_completes_facts_only(scene):
    """A retelling beat enrichment to the memory: completion fills the
    scalars, SKIPS the prose supersede (the reconstruction head stays the
    live telling), still evicts the cache, and records
    `completed_facts_only`."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("k-raced", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=2))
        m = seeded.memory_id
        # A reconstruction superseded the raw head before the worker arrived
        # (db-layer fixture manipulation, the write_back shape).
        new_id = await db.write_back_reconstruction(
            ctx.pool,
            memory_id=m,
            prior_detail_id=seeded.detail_id,
            content="A drifted retelling of the lantern.",
            basis=NOW - timedelta(hours=1),
            composed_key="vhash|b1",
        )
        assert new_id is not None
        assert await ctx.cache_rows(m) != {}

        assert await ctx.worker().drain() == 1

        row = await _memories_row(ctx, m)
        assert row[0] is not None and row[6] is False  # scalars filled
        assert [(c[0], c[3] is None) for c in await ctx.chain(m)] == [
            ("original", False),
            ("reconstruction", True),  # the retelling won; no enrichment head
        ]
        assert await ctx.cache_rows(m) == {}  # eviction on the skip path too
        assert [(r[0], r[1]) for r in await _runs(ctx, m)] == [
            (1, "completed_facts_only")
        ]

    run_structural(scene, scenario)


def test_embedding_repair_supersedes_fact_head(scene):
    """A pending row that landed embed-degraded (NULL embedding) gets an
    opportunistic repair: a new 'enrichment' fact version carries the
    vector; the superseded original stays honestly NULL."""

    async def scenario(ctx):
        agent = await ctx.make_agent("k-repair", V1_CONFIG)
        seeded = await ctx.seed_pending(
            agent, T_OBS, NOW - timedelta(hours=1), embedding=None
        )
        m = seeded.memory_id
        assert await ctx.worker().drain() == 1

        facts = await ctx.fetchall(
            "SELECT write_cause, invalid_at IS NULL, embedding IS NOT NULL, "
            "basis_text FROM memory_fact_versions WHERE memory_id = %s "
            "ORDER BY created_at",
            m,
        )
        assert [(f[0], f[1], f[2]) for f in facts] == [
            ("original", False, False),  # superseded, still honestly NULL
            ("enrichment", True, True),  # the repaired live head
        ]
        assert facts[0][3] == facts[1][3] == T_OBS  # basis_text byte-verbatim
        runs = await _runs(ctx, m)
        assert [(r[1], r[4]) for r in runs] == [("completed", True)]

    run_structural(scene, scenario)


def test_enrichment_head_anchors_drift(scene):
    """Post-completion, the drift anchor is the 'enrichment' head (the
    canonical render re-anchors; migration 006 joined the anchor set)."""

    async def scenario(ctx):
        from app import db

        agent = await ctx.make_agent("k-anchor", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id
        assert await ctx.worker().drain() == 1

        sources = await db.fetch_reconstruction_sources(ctx.pool, [m])
        assert sources[m].anchor_cause == "enrichment"
        assert sources[m].anchor_content == f"[fake render] {T_OBS}"
        assert sources[m].observation_text == T_OBS  # immutable raw untouched

    run_structural(scene, scenario)


def test_orphan_sweep_terminal_fills_exhausted_row(scene):
    """A row still pending with its attempt budget spent (a process died
    mid-final-attempt) is swept to the terminal fill WITHOUT further model
    calls — the queue can never strand a row."""

    async def scenario(ctx):
        agent = await ctx.make_agent("k-orphan", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id
        max_attempts = int(ctx.settings.defaults["deferred_max_attempts"])
        await ctx.execute(
            "UPDATE memories SET enrichment_attempts = %s WHERE memory_id = %s",
            max_attempts,
            m,
        )

        from app.providers import FailingWriteProvider

        # A provider that would fail proves no model call happens: the sweep
        # terminal-fills directly.
        assert await ctx.worker(write=FailingWriteProvider()).drain() == 1
        row = await _memories_row(ctx, m)
        assert row[4] is True and row[6] is False  # scoring_failed, not pending
        assert [(r[1]) for r in await _runs(ctx, m)] == ["terminal_degraded"]

    run_structural(scene, scenario)


def test_chain_route_surfaces_pending_state_and_runs(scene):
    """/chain (unscored by contract — wording untouched) carries the
    deferred window's inspector surface: the pending flag, the attempt
    counter, and the per-attempt run log."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("k-chain", V1_CONFIG)
        seeded = await ctx.seed_pending(
            agent, T_OBS, NOW - timedelta(hours=1), triggers=("thin_gist",)
        )
        m = seeded.memory_id

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            body = (await client.get(f"/v1/memories/{m}/chain")).json()
            assert body["enrichment_pending"] is True
            assert body["enrichment_attempts"] == 0
            assert body["enrichment_runs"] == []
            assert body["typology"] is None  # NULL scalars surface honestly

            assert await ctx.worker().drain() == 1

            body = (await client.get(f"/v1/memories/{m}/chain")).json()
            assert body["enrichment_pending"] is False
            assert body["enrichment_attempts"] == 1
            assert [r["outcome"] for r in body["enrichment_runs"]] == ["completed"]
            assert body["enrichment_runs"][0]["write_input_tokens"] > 0
            assert [d["write_cause"] for d in body["details"]] == [
                "original",
                "enrichment",
            ]

    run_structural(scene, scenario)


def test_pending_row_fully_reachable_neutral_scored(scene):
    """The un-enriched window's retrieval contract: a pending row (embedding
    inline by ruling 1) is vector-reachable with true relevance, scores
    under the importance-NULL neutral fallback, and serves the raw text
    verbatim — all existing ruled shapes; retrieval itself is untouched."""

    async def scenario(ctx):
        agent = await ctx.make_agent("k-window", V1_CONFIG)
        seeded = await ctx.seed_pending(agent, T_OBS, NOW - timedelta(hours=1))
        m = seeded.memory_id

        r = await ctx.retrieval().retrieve_dialogue_init(_read_request(agent))
        assert m in item_ids(r)
        item = next(i for i in r.items if i.memory_id == m)
        assert item.relevance is not None  # the vector probe found it
        assert item.read_mode == "verbatim"
        assert item.content == T_OBS  # the raw head serves during the window
        neutral = ctx.settings.defaults["importance_neutral"]
        assert item.importance_raw == neutral  # the effective value, as fed
        assert item.score > 0.0

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_deferred_observe_end_to_end(scene):
    """The full deferred pipeline at the service level: an enabled agent's
    observe lands pending with NULL scalars and honest zero LLM
    instrumentation; a drain enriches it."""

    async def scenario(ctx):
        from app.schemas import ObserveEvent

        agent = await ctx.make_agent(
            "k-e2e", {**V1_CONFIG, "deferred_writes_enabled": 1.0}
        )
        result = await ctx.ingest().ingest_observation(
            ObserveEvent(
                agent_id=agent,
                observation_text=T_OBS,
                phase_tag="suite",
                client_timestamp=NOW - timedelta(hours=1),
                provenance="lived",
            )
        )
        assert result.enrichment_pending is True
        assert result.importance_raw is None and result.typology is None
        assert result.scoring_failed is False  # pending, not degraded
        assert result.instrumentation.haiku_ms == 0.0
        assert result.instrumentation.haiku_input_tokens == 0
        assert result.instrumentation.escalated is False
        m = result.memory_id

        row = await _memories_row(ctx, m)
        assert row[6] is True and row[0] is None
        # The five non-importance triggers were evaluated and persisted
        # (importance_threshold can never appear — no importance existed).
        assert row[8] is None or "importance_threshold" not in row[8]
        # Embedding stayed inline (ruling 1): the live fact head carries it.
        has_vec = await ctx.fetchrow(
            "SELECT embedding IS NOT NULL FROM memory_fact_versions "
            "WHERE memory_id = %s AND invalid_at IS NULL",
            m,
        )
        assert has_vec[0] is True

        assert await ctx.worker().drain() == 1
        row = await _memories_row(ctx, m)
        assert row[0] is not None and row[6] is False
        assert [(c[0], c[3] is None) for c in await ctx.chain(m)] == [
            ("original", False),
            ("enrichment", True),
        ]

    run_structural(scene, scenario)


def test_salvage_confidence_semantics():
    """The typology_confidence parse seat (ruled 2026-08-12, the clamp's
    sibling): non-numeric -> None (everything else survives); numeric
    out-of-range -> clamped into [0, 1]; NaN -> None; in-range passes
    through byte-untouched. Client declarations keep their loud 422 at the
    wire model (ObserveEvent bounds them; this helper is model-output-only)."""
    from app.providers import salvage_confidence

    assert salvage_confidence(0.7) == 0.7
    assert salvage_confidence("0.4") == 0.4  # numeric string salvages
    assert salvage_confidence(1) == 1.0
    assert salvage_confidence("high") is None  # the flagged crash value
    assert salvage_confidence(None) is None
    assert salvage_confidence([0.5]) is None
    assert salvage_confidence(float("nan")) is None
    assert salvage_confidence(1.5) == 1.0
    assert salvage_confidence(-0.2) == 0.0
