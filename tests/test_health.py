"""Readiness fails closed on infrastructure loss; probes never call providers."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from conftest import run_structural

from app import api, db, health
from app.compiler import CompilerWorker
from app.config import ConfigError, Settings
from app.deferred import DeferredWriteWorker
from app.reflection import ReflectionWorker
from app.runtime import open_runtime_pool


def run(coro):
    return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)


def test_live_and_uninitialized_readiness(monkeypatch):
    monkeypatch.setattr(api.app.state, "readiness", None, raising=False)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://localhost"
        ) as client:
            assert (await client.get("/health/live")).json() == {"status": "alive"}
            result = await client.get("/health/ready")
            assert result.status_code == 503
            assert result.json()["checks"] == {"startup": "fail"}
            assert result.headers["cache-control"] == "no-store"

    run(scenario())


@pytest.mark.parametrize("failure", [None, RuntimeError("secret DSN"), TimeoutError()])
def test_ready_http_status_and_safe_failure(monkeypatch, failure):
    check = AsyncMock(side_effect=failure)
    monkeypatch.setattr(health, "check_runtime_database", check)
    monitor = health.Readiness(
        object(), Settings("unused"), (SimpleNamespace(is_running=True),)
    )
    monkeypatch.setattr(api.app.state, "readiness", monitor, raising=False)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://localhost"
        ) as client:
            result = await client.get("/health/ready")
        assert result.status_code == (200 if failure is None else 503)
        assert result.json() == {
            "status": "ready" if failure is None else "not_ready",
            "checks": {
                "database": "pass" if failure is None else "fail",
                "workers": "pass",
            },
        }
        check.assert_awaited_once()

    run(scenario())


def test_readiness_bounds_wait_and_propagates_cancellation(monkeypatch):
    async def blocked(*args):
        await asyncio.Future()

    monkeypatch.setattr(health, "check_runtime_database", blocked)
    monitor = health.Readiness(object(), Settings("unused"), (), timeout_seconds=0)

    async def scenario():
        assert (await monitor.check())["status"] == "not_ready"
        monkeypatch.setattr(
            health,
            "check_runtime_database",
            AsyncMock(side_effect=asyncio.CancelledError),
        )
        with pytest.raises(asyncio.CancelledError):
            await monitor.check()

    run(scenario())


@pytest.mark.parametrize(
    "worker_type", [DeferredWriteWorker, ReflectionWorker, CompilerWorker]
)
def test_worker_liveness(worker_type):
    async def scenario():
        worker = worker_type(None, None, Settings("unused"))
        assert not worker.is_running
        task = asyncio.create_task(asyncio.Event().wait())
        worker._task = task
        assert worker.is_running
        await worker.stop()
        assert not worker.is_running
        worker._task = asyncio.create_task(asyncio.Event().wait())
        worker._task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker._task
        assert not worker.is_running

    run(scenario())


@pytest.mark.parametrize("failure_stage", ["warm", "providers", "worker", None])
def test_lifespan_cleanup_and_readiness_publication(monkeypatch, failure_stage):
    pool = SimpleNamespace(close=AsyncMock())
    providers = SimpleNamespace(gate=SimpleNamespace(shutdown=Mock()))
    workers = [
        SimpleNamespace(start=Mock(), stop=AsyncMock(), is_running=True)
        for _ in range(3)
    ]
    monkeypatch.setattr(api, "load_settings", lambda: Settings("unused"))
    monkeypatch.setattr(api, "open_runtime_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(
        api,
        "warm_pipelines",
        Mock(side_effect=RuntimeError("warm") if failure_stage == "warm" else None),
    )
    monkeypatch.setattr(
        api,
        "build_providers",
        Mock(
            return_value=providers,
            side_effect=RuntimeError("providers")
            if failure_stage == "providers"
            else None,
        ),
    )
    for name in (
        "RetrievalService",
        "IngestService",
        "DialogueService",
        "DissonanceService",
        "ReflectionService",
    ):
        monkeypatch.setattr(api, name, Mock())
    for name, worker in zip(
        ("DeferredWriteWorker", "ReflectionWorker", "CompilerWorker"), workers
    ):
        monkeypatch.setattr(api, name, Mock(return_value=worker))
    if failure_stage == "worker":
        workers[2].start.side_effect = RuntimeError("worker")

    async def scenario():
        async def lifecycle():
            async with api._lifespan(api.app):
                assert api.app.state.readiness.pool is pool

        if failure_stage:
            with pytest.raises(RuntimeError, match=failure_stage):
                await lifecycle()
        else:
            await lifecycle()
        assert api.app.state.readiness is None
        pool.close.assert_awaited_once()
        if failure_stage in {None, "worker"}:
            for worker in workers:
                worker.stop.assert_awaited_once()
            providers.gate.shutdown.assert_called_once()

    run(scenario())


def test_database_readiness_is_read_only_and_detects_binding_loss(scene):
    async def scenario(ctx):
        # Readiness must not bind an empty database as a side effect.
        with pytest.raises(ConfigError, match="binding is missing"):
            await db.check_runtime_database(ctx.pool, ctx.settings)
        assert (await ctx.fetchrow("SELECT count(*) FROM embedding_space"))[0] == 0
        await db.ensure_embedding_space(ctx.pool, ctx.settings)
        before = await ctx.fetchrow("SELECT configuration FROM embedding_space")
        await db.check_runtime_database(ctx.pool, ctx.settings)
        with pytest.raises(ConfigError, match="does not match"):
            await db.check_runtime_database(
                ctx.pool, replace(ctx.settings, provider_mode="real")
            )
        assert await ctx.fetchrow("SELECT configuration FROM embedding_space") == before
        monitor = health.Readiness(
            ctx.pool, ctx.settings, (SimpleNamespace(is_running=False),)
        )
        assert (await monitor.check())["checks"] == {
            "database": "pass",
            "workers": "fail",
        }

    run_structural(scene, scenario)


@pytest.mark.parametrize("change", ["pending", "newer"])
def test_startup_refuses_incompatible_migration_ledger(scene, change):
    async def scenario(ctx):
        async with ctx.pool.connection() as conn:
            if change == "pending":
                row = await (
                    await conn.execute(
                        "DELETE FROM schema_migrations WHERE version = (SELECT max(version) FROM schema_migrations) RETURNING version, applied_at"
                    )
                ).fetchone()
            else:
                await conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES ('999_future.sql')"
                )
        try:
            with pytest.raises(ConfigError, match="Migration ledger differs"):
                await open_runtime_pool(ctx.settings)
        finally:
            async with ctx.pool.connection() as conn:
                if change == "pending":
                    await conn.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (%s, %s)",
                        row,
                    )
                else:
                    await conn.execute(
                        "DELETE FROM schema_migrations WHERE version = '999_future.sql'"
                    )

    run_structural(scene, scenario)
