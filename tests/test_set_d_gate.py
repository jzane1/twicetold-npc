"""Set D — mid-dialogue gate (docs\\test-suite.md; mid-dialogue-gate.md,
built 2026-07-19). GATE_CONFIG agents: gate at PRODUCTION defaults;
reconstruction FIXTURE-pinned inert (see conftest).

Unmarked except the entities-follow-correction pair (the correction verb's
NER merge is service-level). Seeding is db-layer with explicit entities —
the fact-head coverage basis is a fixture fact here, exactly as observe
would have written it.

Fixture texts are the gate walker's measured corpus (fake-mode distances:
echo ~0; these trigram-distinct texts ~>= 0.73 apart — over the 0.5 novelty
threshold; a FIXTURE property of the pure fake embedding).
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import (
    GATE_CONFIG,
    NOW,
    V1_CONFIG,
    by_id,
    drain_turn,
    item_ids,
    run_structural,
)

from app.gate import GATE_SIGNAL_ENTITY, GATE_SIGNAL_NOVELTY
from app.schemas import DialogueInitRequest, GateInstrumentation

T_CHAPEL = (
    "Mara left the chapel before the harvest bells and the sexton counted "
    "the silver twice by candlelight."
)
T_BRIDGE = (
    "The miller raised his toll at the bridge and the carters grumbled "
    "about the price of crossing all week."
)
T_STORM = (
    "A late storm flattened the barley on the south slope and the gleaners "
    "worked until dusk to save what remained."
)
T_QUARRY = (
    "Flood water filled the eastern quarry pits and the winch ropes "
    "rotted where they hung."
)
T_FERRY = T_BRIDGE + " Aldous waited by the far bank."
T_OLD_DEBT = "Nine grey herons circled the weir at dawn, quarrelling over eels."

COMPONENTS = (("Mara", ["the blacksmith"]), ("Aldous", ["the ferryman"]))


def request(agent_id, query_text, *, loaded=None, streak=0, k=None):
    return DialogueInitRequest(
        agent_id=agent_id,
        query_text=query_text,
        k=k,
        as_of=NOW,
        scene_started_at=NOW,
        loaded_memory_ids=loaded,
        gate_fruitless_streak=streak,
    )


async def _base_store(ctx, agent):
    """Three loaded-set memories, entities on the fact heads."""
    m1 = await ctx.seed(agent, T_CHAPEL, NOW - timedelta(hours=3), entities=["Mara"])
    m2 = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=2))
    m3 = await ctx.seed(agent, T_STORM, NOW - timedelta(hours=1))
    return [m1.memory_id, m2.memory_id, m3.memory_id]


def test_loader_parity(scene):
    """A request without loaded fields is the loader turn: the gate is not
    evaluated (all-default instrumentation), nothing is gate_fetched, the
    store is served. gate_enabled = 0 keeps the loader path even with
    loaded IDs (the kill-switch pin shape)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-loader", GATE_CONFIG, COMPONENTS)
        off_agent = await ctx.make_agent(
            "d-loader-off", {**GATE_CONFIG, "gate_enabled": 0.0}, COMPONENTS
        )
        ids = await _base_store(ctx, agent)
        retrieval = ctx.retrieval()
        loader = await retrieval.retrieve_dialogue_init(request(agent, T_BRIDGE))
        assert loader.instrumentation.gate == GateInstrumentation()
        assert not any(item.gate_fetched for item in loader.items)
        assert set(item_ids(loader)) == set(ids)

        off_ids = await _base_store(ctx, off_agent)
        off = await ctx.retrieval().retrieve_dialogue_init(
            request(off_agent, T_QUARRY, loaded=off_ids)
        )
        assert not off.instrumentation.gate.evaluated

    run_structural(scene, scenario)


def test_closed_gate_serves_loaded_set(scene):
    """A covered, near-loaded utterance: gate closed, zero probe SQL,
    exactly the loaded IDs served deterministically; a NULL-fact-embedding
    loaded row is counted out of the novelty basis and served with
    relevance null."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-closed", GATE_CONFIG, COMPONENTS)
        ids = await _base_store(ctx, agent)
        retrieval = ctx.retrieval()
        closed = await retrieval.retrieve_dialogue_init(
            request(agent, T_CHAPEL, loaded=ids)
        )
        g = closed.instrumentation.gate
        assert g.evaluated and not g.fired and g.signals_fired == []
        assert set(item_ids(closed)) == set(ids)
        assert closed.instrumentation.sql_ms == 0.0  # zero probe SQL
        assert all(item.relevance is not None for item in closed.items)

        again = await retrieval.retrieve_dialogue_init(
            request(agent, T_CHAPEL, loaded=ids)
        )
        assert item_ids(again) == item_ids(closed)
        assert [i.content for i in again.items] == [i.content for i in closed.items]

        null_row = await ctx.seed(
            agent,
            "Someone left a lantern burning overnight.",
            NOW - timedelta(minutes=30),
            embedding=None,
        )
        with_null = await retrieval.retrieve_dialogue_init(
            request(agent, T_CHAPEL, loaded=ids + [null_row.memory_id])
        )
        g = with_null.instrumentation.gate
        assert g.null_embedding_loaded_count == 1
        null_items = [i for i in with_null.items if i.memory_id == null_row.memory_id]
        assert null_items and null_items[0].relevance is None

    run_structural(scene, scenario)


def test_novelty_fire_appends_only_new(scene):
    """A far utterance fires novelty alone; the fetch is SQL-excluded (only
    NEW ids), exactly this turn's appends are marked gate_fetched, and a
    gate-fetched item's text is byte-stable on the next serve."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-novelty", GATE_CONFIG, COMPONENTS)
        ids = await _base_store(ctx, agent)
        cold = await ctx.seed(agent, T_QUARRY, NOW - timedelta(minutes=20))
        retrieval = ctx.retrieval()
        novel = await retrieval.retrieve_dialogue_init(
            request(agent, T_QUARRY, loaded=ids)
        )
        g = novel.instrumentation.gate
        assert g.fired and g.signals_fired == [GATE_SIGNAL_NOVELTY]
        assert cold.memory_id in g.fetched_memory_ids
        assert not set(g.fetched_memory_ids) & set(ids)
        assert all(
            item.gate_fetched == (item.memory_id in set(g.fetched_memory_ids))
            for item in novel.items
        )
        assert set(item_ids(novel)) == set(ids) | set(g.fetched_memory_ids)

        fetched_text = by_id(novel)[cold.memory_id].content
        served_again = await retrieval.retrieve_dialogue_init(
            request(agent, T_QUARRY, loaded=ids + list(g.fetched_memory_ids))
        )
        assert by_id(served_again)[cold.memory_id].content == fetched_text

    run_structural(scene, scenario)


def test_entity_tripwire_and_covered_suppression(scene):
    """An uncovered live-component mention fires the tripwire alone; the
    fetch contains the entity (efficacy true); the same mention covered by
    a loaded item's fact-head entities does not fire."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-tripwire", GATE_CONFIG, COMPONENTS)
        ids = await _base_store(ctx, agent)
        ferry = await ctx.seed(
            agent, T_FERRY, NOW - timedelta(minutes=10), entities=["Aldous"]
        )
        retrieval = ctx.retrieval()
        trip = await retrieval.retrieve_dialogue_init(
            request(agent, T_FERRY, loaded=ids)
        )
        g = trip.instrumentation.gate
        assert g.fired and g.signals_fired == [GATE_SIGNAL_ENTITY]
        assert g.uncovered_entities == ["Aldous"]
        assert ferry.memory_id in g.fetched_memory_ids
        assert g.entity_covered is True

        covered = await retrieval.retrieve_dialogue_init(
            request(agent, T_FERRY, loaded=ids + [ferry.memory_id])
        )
        assert not covered.instrumentation.gate.fired
        assert covered.instrumentation.gate.signals_fired == []

    run_structural(scene, scenario)


def test_both_signals_logged(scene):
    """Far + uncovered logs both named constants; every fire event carries
    non-empty signals_fired."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-both", GATE_CONFIG, COMPONENTS)
        ids = await _base_store(ctx, agent)
        await ctx.seed(agent, T_FERRY, NOW - timedelta(minutes=10), entities=["Aldous"])
        both = await ctx.retrieval().retrieve_dialogue_init(
            request(agent, T_QUARRY + " Aldous waited.", loaded=ids)
        )
        g = both.instrumentation.gate
        assert g.signals_fired == [GATE_SIGNAL_NOVELTY, GATE_SIGNAL_ENTITY]
        assert g.fired and len(g.signals_fired) > 0

    run_structural(scene, scenario)


def test_damper_suppresses_novelty_not_tripwire(scene):
    """A fire that appends nothing is fruitless; at the ruled streak the
    damper suppresses novelty for the scene remainder while the tripwire
    stays live."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-damper", GATE_CONFIG, COMPONENTS)
        ids = await _base_store(ctx, agent)
        ferry = await ctx.seed(
            agent, T_FERRY, NOW - timedelta(minutes=10), entities=["Aldous"]
        )
        all_ids = ids + [ferry.memory_id]
        retrieval = ctx.retrieval()
        fruitless = await retrieval.retrieve_dialogue_init(
            request(agent, T_OLD_DEBT, loaded=all_ids)
        )
        g = fruitless.instrumentation.gate
        assert g.fired and g.fetched_new_count == 0 and g.fruitless

        damped = await retrieval.retrieve_dialogue_init(
            request(agent, T_OLD_DEBT, loaded=all_ids, streak=2)
        )
        g = damped.instrumentation.gate
        assert g.damper_active and not g.fired and g.signals_fired == []

        damped_trip = await retrieval.retrieve_dialogue_init(
            request(agent, T_FERRY, loaded=ids, streak=2)
        )
        g = damped_trip.instrumentation.gate
        assert g.damper_active and g.signals_fired == [GATE_SIGNAL_ENTITY]

    run_structural(scene, scenario)


def test_novelty_outscored_efficacy(scene):
    """The novelty-efficacy boolean populates on fire events per the ruled
    comparator: a fetched distance-0 echo out-scores a far loaded row."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-efficacy", GATE_CONFIG, COMPONENTS)
        bridge = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=2))
        await ctx.seed(agent, T_QUARRY, NOW - timedelta(minutes=20))
        outscored = await ctx.retrieval().retrieve_dialogue_init(
            request(agent, T_QUARRY, loaded=[bridge.memory_id])
        )
        assert outscored.instrumentation.gate.novelty_outscored is True

    run_structural(scene, scenario)


def test_runner_append_only_and_scene_reset(scene):
    """The caller-held contract end-to-end: the loader turn's served IDs
    become the scene's loaded set; gate fetches append in order; a scene
    boundary resets the loaded set and the damper streak (caller-side)."""

    async def scenario(ctx):
        from app.session import SessionRunner

        agent = await ctx.make_agent("d-runner", GATE_CONFIG, COMPONENTS)
        await _base_store(ctx, agent)
        await ctx.seed(agent, T_OLD_DEBT, NOW - timedelta(minutes=5))
        runner = await SessionRunner.create(
            agent, settings=ctx.settings, providers=ctx.providers(), pool=ctx.pool
        )
        try:
            runner.as_of = NOW
            turn1 = await runner.utterance(T_BRIDGE)
            assert runner.loaded_memory_ids == item_ids(turn1)
            assert not turn1.instrumentation.retrieval.gate.evaluated

            turn2 = await runner.utterance(T_OLD_DEBT + " Nobody forgave it.")
            g2 = turn2.instrumentation.retrieval.gate
            assert g2.evaluated
            assert runner.loaded_memory_ids == item_ids(turn1) + list(
                g2.fetched_memory_ids
            )

            runner.gate_fruitless_streak = 2
            await runner.scene()
            assert runner.loaded_memory_ids is None
            assert runner.gate_fruitless_streak == 0
        finally:
            await runner.close()

    run_structural(scene, scenario)


def test_weights_shape_the_prose_view(scene):
    """Weights-on-speech (A1 re-shape, ruled 2026-08-04): one retrieval, one
    weight-ranked view. At default weights `dialogue_view` is byte-identical
    to the (id, score) projection of `items` (the parity contract carried
    over from the split-brain build); a weight override re-scores the SAME
    served set, the re-ranked order matches a recomputation through the pure
    weight functions, and the prose prompt's [memories] block renders in that
    order (the weights-shape-the-words proof — loader turn, so no append-only
    prefix applies). The seam streams prose == content."""

    async def scenario(ctx):
        import re

        from app.dialogue import (
            DialogueService,
            rank_dialogue_view,
            resolve_dialogue_weights,
        )
        from app.providers import FakeProseProvider
        from app.schemas import DialogueTurnRequest, WeightOverrides

        class RecordingProseProvider:
            """FakeProseProvider that keeps the last system prompt so the
            [memories] render order is assertable (fixture-authored line
            text only, never model output — the in-prompt id left at F0,
            2026-08-26)."""

            def __init__(self):
                self._inner = FakeProseProvider()
                self.last_system_prompt = None

            def stream_prose(self, *, system_prompt, utterance):
                self.last_system_prompt = system_prompt
                return self._inner.stream_prose(
                    system_prompt=system_prompt, utterance=utterance
                )

        agent = await ctx.make_agent("d-weights", V1_CONFIG)
        await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=1), importance=0.9)
        await ctx.seed(agent, T_STORM, NOW - timedelta(hours=20), importance=0.3)
        await ctx.seed(agent, T_QUARRY, NOW - timedelta(hours=2), importance=0.6)
        recording = RecordingProseProvider()
        service = DialogueService(
            ctx.pool,
            ctx.providers(dialogue=recording),
            ctx.settings,
            ctx.retrieval(),
        )

        def turn(**over):
            base = dict(
                agent_id=agent,
                utterance="Tell me the news.",
                as_of=NOW,
            )
            base.update(over)
            return DialogueTurnRequest(**base)

        def prompt_memory_lines(prompt: str) -> list[str]:
            return re.findall(r"^- (.+)$", prompt, flags=re.MULTILINE)

        prose, r = await drain_turn(service.run_dialogue_turn(turn()))
        assert prose and r.content == prose  # the seam streamed
        served = {i.memory_id for i in r.items}
        assert served == {v.memory_id for v in r.dialogue_view}
        content_by_id = {i.memory_id: i.content for i in r.items}
        # parity at default weights: dialogue_view == the (id, score)
        # projection of the served ranking, order AND scores.
        assert [v.memory_id for v in r.dialogue_view] == [i.memory_id for i in r.items]
        assert [v.score for v in r.dialogue_view] == [i.score for i in r.items]
        # ...and the prompt rendered the served (== weight-ranked) order.
        assert prompt_memory_lines(recording.last_system_prompt) == [
            content_by_id[v.memory_id] for v in r.dialogue_view
        ]

        # a weight override re-scores the SAME served set; the re-rank is
        # exactly what the pure functions compute, and the prose prompt
        # renders in the re-ranked order.
        _p, rw = await drain_turn(
            service.run_dialogue_turn(
                turn(weight_overrides=WeightOverrides(relevance=0.0))
            )
        )
        assert {v.memory_id for v in rw.dialogue_view} == served
        assert [v.score for v in rw.dialogue_view] != [i.score for i in rw.items]
        weights = resolve_dialogue_weights(
            dict(V1_CONFIG), WeightOverrides(relevance=0.0), ctx.settings
        )
        expected = rank_dialogue_view(list(rw.items), weights)
        assert [v.memory_id for v in rw.dialogue_view] == [
            item.memory_id for _s, item in expected
        ]
        assert [v.score for v in rw.dialogue_view] == [s for s, _i in expected]
        assert prompt_memory_lines(recording.last_system_prompt) == [
            content_by_id[v.memory_id] for v in rw.dialogue_view
        ]
        # `items` stays the raw retrieval echo under an override: same served
        # ranking both turns (the read path is untouched by weights).
        assert [i.memory_id for i in rw.items] == [i.memory_id for i in r.items]
        assert [i.score for i in rw.items] == [i.score for i in r.items]

    run_structural(scene, scenario)


def test_dialogue_turn_route_contract(scene):
    """The HTTP turn route (turn-route build, 2026-07-23): POST
    /v1/dialogue/turn drains the split-brain seam to its terminal result —
    response JSON == the seam result's serialization (the pass-through
    ruling), scene state entirely caller-held on the request (stateless).
    Both TTFT fields ride the wire, the perceived (retrieval-inclusive)
    field strictly above the seam-clocked first_word. 404 unknown agent;
    422 unknown identity_version (the init-route precedent)."""

    async def scenario(ctx):
        import json

        import httpx

        import app.api as api_module
        from app.dialogue import DialogueService
        from app.schemas import DialogueTurnRequest

        agent = await ctx.make_agent("d-route", V1_CONFIG)
        await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=1))
        await ctx.seed(agent, T_STORM, NOW - timedelta(hours=2))
        service = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )

        class CapturingDialogue:
            def __init__(self, inner):
                self._inner = inner
                self.last = None

            async def run_dialogue_turn(self, req, *, on_reconstruct=None):
                async for item in self._inner.run_dialogue_turn(
                    req, on_reconstruct=on_reconstruct
                ):
                    if not isinstance(item, str):
                        self.last = item
                    yield item

        capturing = CapturingDialogue(service)
        api_module.app.state.dialogue = capturing
        transport = httpx.ASGITransport(app=api_module.app)

        def payload(**over):
            base = dict(
                agent_id=agent,
                utterance="Tell me the news.",
                as_of=NOW,
            )
            base.update(over)
            return json.loads(DialogueTurnRequest(**base).model_dump_json())

        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.post("/v1/dialogue/turn", json=payload())
            assert ok.status_code == 200
            assert ok.json() == json.loads(capturing.last.model_dump_json())
            body = ok.json()
            assert [i["memory_id"] for i in body["items"]]
            assert all(i["score"] is not None for i in body["items"])
            ins = body["instrumentation"]
            assert ins["perceived_first_word_ms"] > ins["first_word_ms"] > 0.0

            r404 = await client.post(
                "/v1/dialogue/turn", json=payload(agent_id=uuid4())
            )
            assert r404.status_code == 404

            r422 = await client.post(
                "/v1/dialogue/turn",
                json=payload(identity_version="no-such-version"),
            )
            assert r422.status_code == 422

    run_structural(scene, scenario)


@pytest.mark.nlp
def test_entities_follow_correction(scene):
    """Migration 003's behavior pair through the real verb: the corrected
    fact head carries the merged NER + operator-field entities; the
    superseded fact row keeps its own; windowed SQL re-derives entity
    liveness at any instant."""

    async def scenario(ctx):
        from app.schemas import CorrectionRequest, ObserveEvent

        agent = await ctx.make_agent("d-entities", GATE_CONFIG, COMPONENTS)
        ingest = ctx.ingest()
        seeded = await ingest.ingest_observation(
            ObserveEvent(
                agent_id=agent,
                observation_text=T_CHAPEL,
                phase_tag="suite",
                client_timestamp=NOW - timedelta(hours=3),
                provenance="lived",
                entities=["Mara"],
            )
        )
        m = seeded.memory_id
        correction = await ingest.correct(
            m,
            CorrectionRequest(
                content="The silver was counted once, in the vestry, by Mara herself.",
                client_timestamp=NOW + timedelta(hours=1),
                entities=["the vestry"],
            ),
        )
        facts = await ctx.fact_chain(m)
        assert facts[1][0] == "authorial_correction"
        assert facts[1][5] == correction.entities
        assert "the vestry" in correction.entities
        assert facts[0][5] == seeded.entities  # superseded keeps ITS entities
        assert facts[0][3] == facts[1][2]  # coherent chain timeline

        t_before = NOW - timedelta(hours=2)
        live_before = await ctx.fetchall(
            "SELECT write_cause FROM memory_fact_versions WHERE memory_id = %s "
            "AND valid_at <= %s AND (invalid_at IS NULL OR invalid_at > %s)",
            m,
            t_before,
            t_before,
        )
        assert [row[0] for row in live_before] == ["original"]

    run_structural(scene, scenario)


# ---------------------------------------------------------------------------
# unity-client stage-0 route contracts (ruled 2026-07-27): the SSE turn
# stream, agent provisioning, and The Ledger's two inspector reads. All
# unmarked — db-layer seeding + route-level asserts, no NLP pass.
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[tuple[str, str]]:
    """(event, data) pairs from a text/event-stream body — framing only."""
    events = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        fields = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        events.append((fields["event"], fields["data"]))
    return events


def test_turn_stream_route_contract(scene):
    """The SSE turn route (unity-client.md fork 1, ruled 2026-07-27): POST
    /v1/dialogue/turn/stream iterates the SAME split-brain seam — the chunk
    events concatenate byte-identically to the terminal result's content,
    the result event is exactly the seam result's serialization (the
    pass-through ruling carried to the stream), and a pre-stream failure
    still maps to a real status code (404 unknown agent — the
    queue-priming design)."""

    async def scenario(ctx):
        import json

        import httpx

        import app.api as api_module
        from app.dialogue import DialogueService
        from app.schemas import DialogueTurnRequest

        agent = await ctx.make_agent("d-stream", V1_CONFIG)
        await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=1))
        service = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )

        class CapturingDialogue:
            def __init__(self, inner):
                self._inner = inner
                self.last = None

            async def run_dialogue_turn(self, request, **kwargs):
                async for item in self._inner.run_dialogue_turn(request, **kwargs):
                    if not isinstance(item, str):
                        self.last = item
                    yield item

        capturing = CapturingDialogue(service)
        api_module.app.state.dialogue = capturing
        transport = httpx.ASGITransport(app=api_module.app)

        def payload(**over):
            base = dict(
                agent_id=agent,
                utterance="What happened at the bridge?",
                as_of=NOW,
            )
            base.update(over)
            return json.loads(DialogueTurnRequest(**base).model_dump_json())

        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.post("/v1/dialogue/turn/stream", json=payload())
            assert ok.status_code == 200
            assert ok.headers["content-type"].startswith("text/event-stream")
            events = _parse_sse(ok.text)
            assert events[-1][0] == "result"
            chunks = [json.loads(d) for k, d in events if k == "chunk"]
            assert chunks  # the fake prose provider streams
            result = json.loads(events[-1][1])
            assert "".join(chunks) == result["content"]  # byte-identity
            assert result == json.loads(capturing.last.model_dump_json())
            assert [i["memory_id"] for i in result["items"]]
            ins = result["instrumentation"]
            assert ins["perceived_first_word_ms"] > ins["first_word_ms"] > 0.0

            r404 = await client.post(
                "/v1/dialogue/turn/stream", json=payload(agent_id=uuid4())
            )
            assert r404.status_code == 404

    run_structural(scene, scenario)


def test_create_agent_route(scene):
    """Agent provisioning (unity-client.md fork 2, ruled 2026-07-27): POST
    /v1/agents mints the UUID server-side, stores exactly the supplied
    fields (unsupplied knobs land NULL and resolve config →
    SERVICE_DEFAULTS at read time), and the provisioned agent is
    immediately a working agent — a dialogue turn completes through the
    route. 422 on an empty name (the schema floor)."""

    async def scenario(ctx):
        import json
        from uuid import UUID as UUIDType

        import httpx

        import app.api as api_module
        from app.dialogue import DialogueService
        from app.schemas import DialogueTurnRequest

        api_module.app.state.service = ctx.ingest()
        api_module.app.state.dialogue = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )
        transport = httpx.ASGITransport(app=api_module.app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            minimal = await client.post("/v1/agents", json={"name": "prov-min"})
            assert minimal.status_code == 200
            body = minimal.json()
            UUIDType(body["agent_id"])  # server-minted, parseable
            assert body["config"] == {}
            assert body["seed_identity"] is None

            full = await client.post(
                "/v1/agents",
                json={
                    "name": "prov-full",
                    "seed_identity": "I keep the ford and remember who pays.",
                    "rigidity": 1.5,
                    "diagnosticity_goal": "what threatens the ford",
                    "config": dict(V1_CONFIG),
                },
            )
            assert full.status_code == 200
            fb = full.json()
            # The reputation surface left provisioning with the A1 re-shape
            # (2026-08-04): not echoed on the wire, and the schema column —
            # which stays, applied migrations being immutable — is never
            # written.
            assert "reputation" not in fb
            assert "reputation_sensitivity" not in fb
            row = await ctx.fetchrow(
                "SELECT name, seed_identity, reputation, rigidity, config "
                "FROM agents WHERE agent_id = %s",
                fb["agent_id"],
            )
            assert row[0] == "prov-full"
            assert row[1] == "I keep the ford and remember who pays."
            assert row[2] is None  # reputation column stays NULL, unwritten
            assert float(row[3]) == 1.5
            assert row[4] == dict(V1_CONFIG)  # config jsonb round-trip

            turn = await client.post(
                "/v1/dialogue/turn",
                json=json.loads(
                    DialogueTurnRequest(
                        agent_id=fb["agent_id"],
                        utterance="Do you know me?",
                        as_of=NOW,
                    ).model_dump_json()
                ),
            )
            assert turn.status_code == 200  # provisioned agent works end-to-end

            invalid = await client.post("/v1/agents", json={"name": ""})
            assert invalid.status_code == 422

    run_structural(scene, scenario)


def test_memory_chain_route_follows_correction(scene):
    """The Ledger's chain read (unity-client.md fork 3, ruled 2026-07-27):
    GET /v1/memories/{id}/chain returns the immutable observation beside
    BOTH version chains with superseded rows PRESENT — after a correction
    the original telling/fact rows ride invalidated (never dropped), the
    corrected heads are live, the chain timeline is coherent, and gist
    spans + fact entities are structural payload. 404 unknown memory."""

    async def scenario(ctx):
        import httpx
        from conftest import embed_text

        import app.api as api_module
        from app import db

        agent = await ctx.make_agent("d-chain", V1_CONFIG)
        seeded = await ctx.seed(
            agent,
            T_CHAPEL,
            NOW - timedelta(days=2),
            entities=["Mara"],
            spans=((0, 9),),
        )
        m = seeded.memory_id
        corrected_text = "The sexton counted the silver once, not twice."
        applied = await db.apply_authorial_correction(
            ctx.pool,
            memory_id=m,
            content=corrected_text,
            valid_at=NOW - timedelta(days=1),
            embedding=embed_text(corrected_text),
            entities=["the sexton"],
        )
        assert not isinstance(applied, str)

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.get(f"/v1/memories/{m}/chain")
            assert ok.status_code == 200
            body = ok.json()
            assert body["memory_id"] == str(m)
            assert body["observation_text"] == T_CHAPEL  # immutable
            details = body["details"]
            assert [d["write_cause"] for d in details] == [
                "original",
                "authorial_correction",
            ]
            assert [d["is_live"] for d in details] == [False, True]
            assert details[1]["content"] == corrected_text
            assert details[0]["invalid_at"] == details[1]["valid_at"]
            facts = body["facts"]
            assert [f["write_cause"] for f in facts] == [
                "original",
                "authorial_correction",
            ]
            assert [f["is_live"] for f in facts] == [False, True]
            assert facts[1]["basis_text"] == corrected_text
            assert all(f["has_embedding"] for f in facts)
            assert facts[1]["entities"] == ["the sexton"]
            spans = body["gist_spans"]
            assert [(s["start_char"], s["end_char"]) for s in spans] == [(0, 9)]

            r404 = await client.get(f"/v1/memories/{uuid4()}/chain")
            assert r404.status_code == 404

    run_structural(scene, scenario)


def test_agent_memories_route(scene):
    """The Ledger's index read (unity-client.md fork 3): newest valid_at
    first with the memory_id tiebreak, each row beside its live telling
    head; `limit` caps the page while total_count reports the full store.
    404 unknown agent."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("d-index", V1_CONFIG)
        older = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(days=3))
        newer = await ctx.seed(agent, T_STORM, NOW - timedelta(days=1))
        middle = await ctx.seed(agent, T_QUARRY, NOW - timedelta(days=2))

        api_module.app.state.retrieval = ctx.retrieval()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            ok = await client.get(f"/v1/agents/{agent}/memories")
            assert ok.status_code == 200
            body = ok.json()
            assert body["total_count"] == 3
            ids = [m["memory_id"] for m in body["memories"]]
            assert ids == [
                str(newer.memory_id),
                str(middle.memory_id),
                str(older.memory_id),
            ]
            head = body["memories"][0]
            assert head["live_content"] == f"[suite seed] {T_STORM}"
            assert head["live_write_cause"] == "original"
            assert head["detail_count"] == 1

            page = await client.get(f"/v1/agents/{agent}/memories?limit=1")
            assert page.status_code == 200
            pb = page.json()
            assert pb["total_count"] == 3
            assert len(pb["memories"]) == 1
            assert pb["limit"] == 1

            r404 = await client.get(f"/v1/agents/{uuid4()}/memories")
            assert r404.status_code == 404

    run_structural(scene, scenario)


def test_ledger_page_served(scene):
    """The Ledger ships WITH the service (unity-client.md stage 3, ruled
    2026-07-27): GET /ledger serves the static inspector page from
    ledger\\index.html — same origin as the two read routes it polls, so no
    CORS surface exists. Structural: status, content type, and the page's
    own route bindings present as text."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            page = await client.get("/ledger")
            assert page.status_code == 200
            assert page.headers["content-type"].startswith("text/html")
            assert "THE LEDGER" in page.text
            assert "/v1/agents/" in page.text  # polls the index route
            assert "/v1/memories/" in page.text  # polls the chain route
            assert "/state" in page.text  # the identity pane (E2, 2026-08-19)
            assert "/v1/ledger/turns" in page.text  # the live turn feed (E2)

    run_structural(scene, scenario)


def test_context_term_applies_on_gated_turns(scene):
    """The encoding-context term (built 2026-07-20) rides the gated path
    too: on a closed gate the loaded set's scores carry the same exact
    factor, and the gate decision itself is untouched by context fields
    (context nudges scores; it never opens or closes the gate)."""

    async def scenario(ctx):
        agent = await ctx.make_agent("d-context", GATE_CONFIG, COMPONENTS)
        stamped = await ctx.seed(
            agent,
            T_CHAPEL,
            NOW - timedelta(hours=3),
            entities=["Mara"],
            event_time=NOW,
            location_name="The Chapel",
        )
        other = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=2))
        ids = [stamped.memory_id, other.memory_id]
        retrieval = ctx.retrieval()
        no_ctx = await retrieval.retrieve_dialogue_init(
            request(agent, T_CHAPEL, loaded=ids)
        )
        with_ctx = await retrieval.retrieve_dialogue_init(
            DialogueInitRequest(
                agent_id=agent,
                query_text=T_CHAPEL,
                as_of=NOW,
                scene_started_at=NOW,
                loaded_memory_ids=ids,
                entities=["mara"],
                event_time=NOW,
                location_name="the chapel",
            )
        )
        for result in (no_ctx, with_ctx):
            g = result.instrumentation.gate
            assert g.evaluated and not g.fired and g.signals_fired == []
        assert with_ctx.instrumentation.context_active is True
        p, c = by_id(no_ctx), by_id(with_ctx)
        assert c[stamped.memory_id].score == p[stamped.memory_id].score * 1.75
        assert c[other.memory_id].score == p[other.memory_id].score

    run_structural(scene, scenario)


# --------------------------------------------------------------------------
# Route contracts closed by the 2026-07-28 audit: two routes had NO HTTP-level
# exercise anywhere in the repo, and two of the SSE stream's event kinds were
# emitted by the server and consumed by the C# client but asserted by nothing.
# --------------------------------------------------------------------------


def test_pin_route_contract(scene):
    """PUT /v1/memories/{memory_id}/pin — the operator pin toggle over HTTP.

    The service method `set_pin` was exercised by two walkers, but the ROUTE
    had no test, so its 404 mapping was unproven. `memories.pinned` is one of
    the two sanctioned in-place runtime scalars, so this asserts the DB row
    actually moved (both directions) and the payload mirrors it."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module

        agent = await ctx.make_agent("d-pin-route", V1_CONFIG)
        seeded = await ctx.seed(agent, T_BRIDGE, NOW - timedelta(hours=1))

        api_module.app.state.service = ctx.ingest()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            for wanted in (True, False, True):
                resp = await client.put(
                    f"/v1/memories/{seeded.memory_id}/pin", json={"pinned": wanted}
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["pinned"] is wanted
                assert body["memory_id"] == str(seeded.memory_id)
                row = await ctx.fetchrow(
                    "SELECT pinned FROM memories WHERE memory_id = %s",
                    seeded.memory_id,
                )
                assert row[0] is wanted

            missing = await client.put(
                f"/v1/memories/{uuid4()}/pin", json={"pinned": True}
            )
            assert missing.status_code == 404

    run_structural(scene, scenario)


def test_scene_boundary_route_contract(scene):
    """POST /v1/events/scene-boundary — the boundary verb over HTTP.

    Tested at the service level only, never through the route. The boundary
    is the identity-recompile seam the C# NpcSession calls at every scene
    change, so the route payload it freezes (accepted + identity_version) and
    the unknown-agent 404 are both load-bearing for the client."""

    async def scenario(ctx):
        import httpx

        import app.api as api_module
        from app.schemas import SceneBoundaryEvent

        agent = await ctx.make_agent("d-boundary-route", V1_CONFIG)
        api_module.app.state.service = ctx.ingest()
        transport = httpx.ASGITransport(app=api_module.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            body = {
                "agent_id": str(agent),
                "client_timestamp": NOW.isoformat(),
                "scene_type": "tavern",
            }
            ok = await client.post("/v1/events/scene-boundary", json=body)
            assert ok.status_code == 200
            payload = ok.json()
            assert payload["accepted"] is True
            assert payload["identity_version"]  # the caller freezes this
            assert payload["total_ms"] >= 0

            # Pass-through by ruling: the route adds and drops nothing. A
            # stable identity recompiles to the SAME version.
            direct = await ctx.ingest().scene_boundary(
                SceneBoundaryEvent(agent_id=agent, client_timestamp=NOW)
            )
            assert direct.identity_version == payload["identity_version"]

            missing = await client.post(
                "/v1/events/scene-boundary", json={**body, "agent_id": str(uuid4())}
            )
            assert missing.status_code == 404

    run_structural(scene, scenario)


def test_turn_stream_reconstructing_and_error_events(scene):
    """The SSE stream's two previously-unasserted event kinds.

    `reconstructing` is the HTTP form of the REPL's "(reconstructing…)":
    fired from the pre-serve callback while a blocking mid-scene retelling
    runs, so a client can show the pause instead of appearing hung. It is
    the demo's latency-as-characterization beat, and the C# client consumes
    it. Note the deliberate scoping (mid-dialogue-gate.md fork 5, ruled
    2026-07-19): the callback rides GATED turns only — `app\\retrieval.py`
    passes it to `serve` on the gated branch and not on the loader branch,
    because the signal that earns a spinner is a pause appearing MID-scene,
    not the expected cost of a scene's first read. So this scenario needs an
    agent with the gate live AND reconstruction live (neither knob pinned)
    and a request carrying a loaded set.

    `error` is the ROUTE's contract, not the seam's. The seam absorbs every
    provider failure into its degradation ladder, but once the first queue
    item has been awaited the response is already a 200 — and a 200 stream
    cannot change its status, so anything raised afterwards must arrive as
    an `error` EVENT rather than a silently truncated stream. Injected at
    the route boundary, which is exactly where that contract lives."""

    async def scenario(ctx):
        import json

        import httpx

        import app.api as api_module
        from conftest import BASE_CONFIG

        from app.dialogue import DialogueService
        from app.schemas import DialogueTurnRequest, SceneBoundaryEvent

        # BASE_CONFIG pins NEITHER knob: reconstruction at production theta
        # 0.5 and the gate live — both are required for the callback to
        # reach the route. A past-theta `semantic` row (10 days against a
        # 7-day tau) forces a real blocking retelling (the Set C fixture
        # math), and passing it as the loaded set makes the turn gated.
        agent = await ctx.make_agent("d-stream-recon", BASE_CONFIG)
        seeded = await ctx.seed(
            agent, T_QUARRY, NOW - timedelta(days=10), decay_class="semantic"
        )
        boundary = await ctx.ingest().scene_boundary(
            SceneBoundaryEvent(agent_id=agent, client_timestamp=NOW)
        )

        api_module.app.state.dialogue = DialogueService(
            ctx.pool, ctx.providers(), ctx.settings, ctx.retrieval()
        )
        transport = httpx.ASGITransport(app=api_module.app)
        body = json.loads(
            DialogueTurnRequest(
                agent_id=agent,
                utterance="What happened at the quarry?",
                as_of=NOW,
                scene_started_at=NOW,
                identity_version=boundary.identity_version,
                loaded_memory_ids=[seeded.memory_id],  # gated => callback rides
            ).model_dump_json()
        )

        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.post("/v1/dialogue/turn/stream", json=body)
            assert resp.status_code == 200
            kinds = [k for k, _ in _parse_sse(resp.text)]
            assert "reconstructing" in kinds
            # Fired ONCE, and before any prose chunk: the pause it announces
            # happens during retrieval, ahead of the first token.
            assert kinds.count("reconstructing") == 1
            assert kinds.index("reconstructing") < kinds.index("chunk")
            assert kinds[-1] == "result"
            result = json.loads(_parse_sse(resp.text)[-1][1])
            retrieval_inst = result["instrumentation"]["retrieval"]
            # A real retelling really ran — the event is not cosmetic.
            assert retrieval_inst["write_backs"] >= 1
            assert retrieval_inst["gate"]["evaluated"] is True

        # -- the error event: a failure AFTER the stream has begun --------
        class ExplodesMidStream:
            async def run_dialogue_turn(self, request, **kwargs):
                yield "first "
                raise RuntimeError("injected post-first-chunk failure")

        api_module.app.state.dialogue = ExplodesMidStream()
        async with httpx.AsyncClient(
            transport=transport, base_url="http://localhost"
        ) as client:
            resp = await client.post("/v1/dialogue/turn/stream", json=body)
            # Already committed to 200 before it failed — that IS the
            # contract; the failure surfaces as an event, not a status.
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            assert [k for k, _ in events] == ["chunk", "error"]
            assert "injected post-first-chunk failure" in json.loads(events[-1][1])

    run_structural(scene, scenario)
