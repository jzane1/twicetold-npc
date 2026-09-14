"""Set G — judge-free eval metrics (docs\\test-suite.md; eval-harness.md
stage 1, built 2026-07-29).

Two layers, matching the build: pure metric ARITHMETIC over fixed inputs
(unmarked, no database, no NLP loaders — the repo-hygiene precedent), and
the reconstruction-metrics ROUTE contract (nlp-marked: any 200 runs the
spaCy lemma/NER block). Structural throughout — every telling asserted on
here is a fixture string or a db-layer write, never model prose; the exact
metric values are therefore byte-known, not judged.

The one payload-identity caveat: the non-perturbation pair compares /chain
with `total_ms` excluded — it is a per-call timing field, not record state.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import NOW, V1_CONFIG, run_structural

from app.eval_metrics import (
    band_from_composed_key,
    detail_recall,
    detail_segment_texts,
    fabricated_entities,
    fabrication_rate,
    gist_fact_texts,
    gist_precision,
    keyword_retention,
)

T_CHAPEL = (
    "Mara left the chapel before the harvest bells and the sexton counted "
    "the silver twice by candlelight."
)
T_QUARRY = (
    "Flood water filled the eastern quarry pits and the winch ropes "
    "rotted where they hung."
)


# ---------------------------------------------------------------------------
# Pure arithmetic — unmarked, no database
# ---------------------------------------------------------------------------


def test_gist_facts_and_detail_segments_anchor_aware():
    text = "Mara left the chapel. The sexton counted the silver twice."
    # Overlapping spans merge before slicing (one fact per MERGED span).
    facts = gist_fact_texts(text, [(0, 4), (10, 20), (14, 23)], "original", "")
    assert facts == [text[0:4], text[10:23]]
    segments = detail_segment_texts(text, [(0, 4), (10, 23)], "original")
    assert segments == [text[4:10].strip(), text[23:].strip()]
    # Correction-anchored: the corrected head IS the facts (sentence-split,
    # stripped) and no observation detail is owed.
    corr = gist_fact_texts(
        text, [(0, 4)], "authorial_correction", "One fact. Two facts!  "
    )
    assert corr == ["One fact.", "Two facts!"]
    assert detail_segment_texts(text, [(0, 4)], "authorial_correction") == []


def test_gist_precision_threshold_and_unmeasurable_facts():
    telling = {"mara", "chapel", "silver"}
    # Present / absent / unmeasurable (empty lemma set — excluded, not 1.0).
    precision, flags = gist_precision(
        [{"mara", "chapel"}, {"sexton"}, set()], telling, 1.0
    )
    assert flags == [True, False, None]
    assert precision == 0.5
    # The threshold knob is honored: half-present fact flips at 0.5.
    assert gist_precision([{"mara", "well"}], telling, 1.0) == (0.0, [False])
    assert gist_precision([{"mara", "well"}], telling, 0.5) == (1.0, [True])
    # Honest denominators: all-unmeasurable and no-facts are None, never 1.0.
    assert gist_precision([set(), set()], telling, 1.0) == (None, [None, None])
    assert gist_precision([], telling, 1.0) == (None, [])


def test_detail_recall_honest_denominator():
    assert detail_recall(set(), {"anything"}) is None
    assert detail_recall({"a", "b", "c", "d"}, {"a", "b", "x"}) == 0.5


def test_fabrication_and_keyword_retention():
    fabricated = fabricated_entities(
        ["Mara", "Baldric", "mara", ""],
        ["Mara left the chapel.", "", "I keep the ford."],
    )
    assert fabricated == ["Baldric"]  # deduped case-insensitively, grounded Mara out
    assert fabrication_rate(["Mara", "Baldric", "mara"], fabricated) == 0.5
    assert fabrication_rate([], []) is None
    # Whole-word grounding: "Mar" inside "Mara" is NOT a ground hit.
    assert fabricated_entities(["Mar"], ["Mara left."]) == ["Mar"]
    assert keyword_retention(["Mara", "Baldric"], "Mara came back.") == 0.5
    assert keyword_retention([], "anything") is None


def test_band_key_roundtrip():
    from app.reconstruction import compose_cache_key

    assert band_from_composed_key(compose_cache_key("deadbeef", 3)) == 3
    assert band_from_composed_key("iv|b12") == 12
    assert band_from_composed_key("deadbeef") is None


# ---------------------------------------------------------------------------
# The route contract — nlp-marked (any 200 runs the spaCy lemma/NER block)
# ---------------------------------------------------------------------------


@pytest.mark.nlp
def test_metrics_route_contract(scene):
    """200 = IDs + counts + exact ratios against the fixture live head (the
    seeded telling contains the observation verbatim, so presence is total);
    a zero-span memory reports gist_precision None (never a flattering 1.0);
    404 unknown memory (the /chain shape)."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("g-metrics", V1_CONFIG)
        seeded = await ctx.seed(
            agent,
            T_CHAPEL,
            NOW - timedelta(days=2),
            entities=["Mara"],
            spans=((0, 4),),
        )
        bare = await ctx.seed(agent, T_QUARRY, NOW - timedelta(days=1))

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.get(
                f"/v1/memories/{seeded.memory_id}/reconstruction-metrics"
            )
            assert ok.status_code == 200
            body = ok.json()
            assert body["memory_id"] == str(seeded.memory_id)
            assert body["agent_id"] == str(agent)
            assert body["live_detail_id"] == str(seeded.detail_id)
            assert body["live_write_cause"] == "original"
            assert body["anchor_cause"] == "original"
            assert body["gist_facts_total"] == 1  # the one span, measurable
            assert body["gist_facts_present"] == 1
            assert body["gist_precision"] == 1.0
            assert body["detail_lemmas_total"] > 0
            assert body["detail_lemmas_present"] == body["detail_lemmas_total"]
            assert body["detail_recall"] == 1.0
            assert body["fabricated_entities"] == []
            assert body["keyword_retention"] == 1.0
            assert body["cache_bands"] == []  # nothing reconstructed yet
            assert body["total_ms"] >= body["metrics_ms"] >= 0.0

            none_resp = await client.get(
                f"/v1/memories/{bare.memory_id}/reconstruction-metrics"
            )
            assert none_resp.status_code == 200
            nb = none_resp.json()
            assert nb["gist_facts_total"] == 0
            assert nb["gist_facts_present"] == 0
            assert nb["gist_precision"] is None  # the honest denominator
            assert nb["detail_recall"] is not None  # detail still measurable

            r404 = await client.get(f"/v1/memories/{uuid4()}/reconstruction-metrics")
            assert r404.status_code == 404

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_metrics_follow_correction_then_reconstruction(scene):
    """The anchor-cause contract end to end: after a correction the gist IS
    the corrected head (no detail owed); after a reconstruction head lands
    on top, the anchor stays the correction, the cache band parses out of
    the composed key, a never-observed entity is flagged fabricated, and a
    gist violation reads as precision 0.0 — all against db-layer fixture
    writes, never model prose."""

    async def scenario(ctx):
        import httpx
        from conftest import embed_text

        import app.api as api_module
        from app import db
        from app.reconstruction import compose_cache_key

        agent = await ctx.make_agent("g-anchor", V1_CONFIG)
        seeded = await ctx.seed(
            agent,
            T_CHAPEL,
            NOW - timedelta(days=3),
            entities=["Mara"],
            spans=((0, 4),),
        )
        m = seeded.memory_id
        corrected = "Mara counted the silver once in the chapel."
        applied = await db.apply_authorial_correction(
            ctx.pool,
            memory_id=m,
            content=corrected,
            valid_at=NOW - timedelta(days=2),
            embedding=embed_text(corrected),
            entities=["Mara"],
        )
        assert not isinstance(applied, str)

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.get(f"/v1/memories/{m}/reconstruction-metrics")
            assert ok.status_code == 200
            body = ok.json()
            assert body["anchor_cause"] == "authorial_correction"
            assert body["live_write_cause"] == "authorial_correction"
            assert body["gist_facts_total"] == 1  # one corrected sentence
            assert body["gist_precision"] == 1.0  # the live head IS the anchor
            assert body["detail_lemmas_total"] == 0  # no detail re-injected
            assert body["detail_recall"] is None

            retold = "Weymouth took the silver and Mara wept."
            new_head = await db.write_back_reconstruction(
                ctx.pool,
                memory_id=m,
                prior_detail_id=applied.detail_id,
                content=retold,
                basis=NOW - timedelta(days=1),
                composed_key=compose_cache_key("fixtureiv", 2),
            )
            assert new_head is not None

            again = await client.get(f"/v1/memories/{m}/reconstruction-metrics")
            assert again.status_code == 200
            b2 = again.json()
            assert b2["live_write_cause"] == "reconstruction"
            assert b2["anchor_cause"] == "authorial_correction"  # never re-anchors
            assert b2["live_detail_id"] == str(new_head)
            assert b2["cache_bands"] == [2]  # parsed off the composed key
            assert "Weymouth" in b2["fabricated_entities"]
            assert "Mara" not in b2["fabricated_entities"]  # grounded in anchor
            assert b2["gist_precision"] == 0.0  # the retelling dropped the facts

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_metrics_read_is_zero_write(scene):
    """The non-perturbation pair: a metrics read leaves the record
    byte-identical (/chain compared with the per-call total_ms timing field
    excluded) and writes NOTHING — telling chain, reconstruction cache, and
    identity documents all count-stable (the identity render is pure, never
    the ensure_ upsert)."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("g-zerowrite", V1_CONFIG)
        seeded = await ctx.seed(
            agent,
            T_CHAPEL,
            NOW - timedelta(days=2),
            entities=["Mara"],
            spans=((0, 4),),
        )
        m = seeded.memory_id

        counts_sql = (
            "SELECT (SELECT count(*) FROM memory_details), "
            "(SELECT count(*) FROM reconstruction_cache), "
            "(SELECT count(*) FROM identity_documents)"
        )

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            before = (await client.get(f"/v1/memories/{m}/chain")).json()
            counts_before = await ctx.fetchrow(counts_sql)

            resp = await client.get(f"/v1/memories/{m}/reconstruction-metrics")
            assert resp.status_code == 200

            after = (await client.get(f"/v1/memories/{m}/chain")).json()
            counts_after = await ctx.fetchrow(counts_sql)

            before.pop("total_ms")
            after.pop("total_ms")
            assert before == after
            assert counts_before == counts_after

    run_structural(scene, scenario)
