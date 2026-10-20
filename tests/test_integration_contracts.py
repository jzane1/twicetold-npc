"""Retry receipts and the scoring-clock contract, with disposable real SQL."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from conftest import NOW, V1_CONFIG, by_id, embed_text, run_structural

from app import db, nlp
from app.ingest import IngestService
from app.schemas import DialogueInitRequest, ObserveEvent


@pytest.fixture
def nlp_calls(monkeypatch):
    calls = []

    def write_pass(text, components):
        calls.append(text)
        return nlp.NlpResult([], [], [], None, None, None)

    monkeypatch.setattr(nlp, "run_write_pass", write_pass)
    return calls


def event(agent, **overrides):
    return ObserveEvent(
        **(
            dict(
                agent_id=agent,
                observation_text="The bridge closed.",
                client_timestamp=NOW,
                phase_tag="test",
                provenance="lived",
                event_id="bridge-1",
            )
            | overrides
        )
    )


@pytest.mark.parametrize("deferred", [False, True])
def test_retry_returns_original_receipt_even_after_head_changes(
    scene, nlp_calls, deferred
):
    async def scenario(ctx):
        agent = await ctx.make_agent(
            "retry", V1_CONFIG | {"deferred_writes_enabled": float(deferred)}
        )
        service = ctx.ingest()
        evt = event(agent)
        first = await service.ingest_observation(evt)
        # A later head change must not turn the retry into a second write or
        # make the acknowledgement pretend to describe the current head.
        await db.apply_authorial_correction(
            ctx.pool,
            memory_id=first.memory_id,
            content="Operator correction.",
            valid_at=NOW + timedelta(hours=1),
            embedding=embed_text("Operator correction."),
        )
        replay = await ctx.ingest().ingest_observation(
            ObserveEvent.model_validate(evt.model_dump())
        )
        assert replay == first
        assert len(nlp_calls) == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM memories"))[0] == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM observation_receipts"))[0] == 1
        assert len(await ctx.chain(first.memory_id)) == 2

    run_structural(scene, scenario)


@pytest.mark.parametrize("pool_size", [1, 2])
def test_concurrent_independent_services_share_one_receipt_without_pool_deadlock(
    scene, nlp_calls, pool_size
):
    async def scenario(ctx):
        agent = await ctx.make_agent("concurrent", V1_CONFIG)
        pool = db.build_pool(ctx.settings.database_uri, max_size=pool_size)
        await pool.open()
        try:
            services = [
                IngestService(pool, ctx.providers(), ctx.settings) for _ in range(8)
            ]
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[service.ingest_observation(event(agent)) for service in services]
                ),
                timeout=20,
            )
            assert all(result == results[0] for result in results)
            assert len(nlp_calls) == 1
            assert (await ctx.fetchrow("SELECT count(*) FROM memories"))[0] == 1
        finally:
            await pool.close()

    run_structural(scene, scenario)


@pytest.mark.parametrize("cancel", [False, True])
def test_receipt_and_memory_roll_back_together_and_key_is_reusable(
    scene, nlp_calls, monkeypatch, cancel
):
    async def scenario(ctx):
        agent = await ctx.make_agent("rollback", V1_CONFIG)
        saved = asyncio.Event()
        original = db.save_observation_receipt

        async def fail_after_save(*args):
            await original(*args)
            saved.set()
            if cancel:
                await asyncio.Event().wait()
            raise RuntimeError("injected transaction failure")

        monkeypatch.setattr(db, "save_observation_receipt", fail_after_save)
        task = asyncio.create_task(ctx.ingest().ingest_observation(event(agent)))
        await asyncio.wait_for(saved.wait(), timeout=20)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
            await task
        assert (await ctx.fetchrow("SELECT count(*) FROM memories"))[0] == 0
        assert (await ctx.fetchrow("SELECT count(*) FROM observation_receipts"))[0] == 0
        monkeypatch.setattr(db, "save_observation_receipt", original)
        assert (await ctx.ingest().ingest_observation(event(agent))).memory_id
        assert len(nlp_calls) == 2

    run_structural(scene, scenario)


def test_agent_scope_unkeyed_writes_and_purge_release(scene, nlp_calls):
    async def scenario(ctx):
        a = await ctx.make_agent("a", V1_CONFIG)
        b = await ctx.make_agent("b", V1_CONFIG)
        service = ctx.ingest()
        first = await service.ingest_observation(event(a))
        other = await service.ingest_observation(event(b))
        unkeyed = [
            await service.ingest_observation(event(a, event_id=None)) for _ in range(2)
        ]
        assert (
            len({first.memory_id, other.memory_id, *(r.memory_id for r in unkeyed)})
            == 4
        )
        await service.purge_memory(first.memory_id)
        assert (
            await ctx.fetchrow(
                "SELECT count(*) FROM observation_receipts WHERE agent_id = %s", a
            )
        )[0] == 0
        recreated = await service.ingest_observation(event(a))
        assert recreated.memory_id != first.memory_id
        await service.purge_agent_memories(b)
        assert (
            await ctx.fetchrow(
                "SELECT count(*) FROM observation_receipts WHERE agent_id = %s", b
            )
        )[0] == 0

    run_structural(scene, scenario)


def test_degraded_ack_is_replayed_without_provider_repair_or_duplicate(
    scene, nlp_calls
):
    async def scenario(ctx):
        from app.providers import FailingEmbeddingProvider, FailingWriteProvider

        agent = await ctx.make_agent("degraded-retry", V1_CONFIG)
        first = await ctx.ingest(
            embedding=FailingEmbeddingProvider(), write=FailingWriteProvider()
        ).ingest_observation(event(agent))
        assert first.embedding_failed and first.scoring_failed
        replay = await ctx.ingest().ingest_observation(event(agent))
        assert replay == first and len(nlp_calls) == 1
        separate = await ctx.ingest().ingest_observation(
            event(agent, event_id="bridge-2")
        )
        assert separate.memory_id != first.memory_id
        assert len(nlp_calls) == 2

    run_structural(scene, scenario)


def test_http_replay_conflict_validation_and_unknown_agent(
    scene, nlp_calls, monkeypatch
):
    async def scenario(ctx):
        from app import api

        agent = await ctx.make_agent("http-retry", V1_CONFIG)
        monkeypatch.setattr(api.app.state, "service", ctx.ingest(), raising=False)
        payload = event(agent).model_dump(mode="json", exclude_unset=True)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://localhost"
        ) as client:
            first = await client.post("/v1/events/observe", json=payload)
            assert first.status_code == 200
            # Explicit defaults and object key order do not cause conflicts.
            replay = await client.post(
                "/v1/events/observe", json=event(agent).model_dump(mode="json")
            )
            assert replay.status_code == 200 and replay.json() == first.json()
            for changed in [
                {"observation_text": "Different event."},
                {"pinned": True},
                {"client_timestamp": (NOW + timedelta(seconds=1)).isoformat()},
            ]:
                assert (
                    await client.post("/v1/events/observe", json=payload | changed)
                ).status_code == 409
            for key in ["", "  ", "x" * 201]:
                assert (
                    await client.post(
                        "/v1/events/observe", json=payload | {"event_id": key}
                    )
                ).status_code == 422
            assert (
                await client.post(
                    "/v1/events/observe", json=payload | {"agent_id": str(uuid4())}
                )
            ).status_code == 404
        assert len(nlp_calls) == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM memories"))[0] == 1

    run_structural(scene, scenario)


def test_backward_as_of_uses_current_heads_and_keeps_newer_memories_eligible(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("clock-contract", V1_CONFIG)
        newer = await ctx.seed(agent, "New observation.", NOW + timedelta(days=1))
        older = await ctx.seed(agent, "Old observation.", NOW - timedelta(days=1))
        changed = await db.apply_authorial_correction(
            ctx.pool,
            memory_id=older.memory_id,
            content="Corrected observation.",
            valid_at=NOW + timedelta(days=2),
            embedding=embed_text("Corrected observation."),
        )
        result = await ctx.retrieval().retrieve_dialogue_init(
            DialogueInitRequest(
                agent_id=agent,
                query_text="New observation.",
                as_of=NOW,
            )
        )
        items = by_id(result)
        assert set(items) == {newer.memory_id, older.memory_id}
        assert items[newer.memory_id].recency == 1.0
        assert items[older.memory_id].detail_id == changed.detail_id
        assert items[older.memory_id].content == "Corrected observation."

    run_structural(scene, scenario)
