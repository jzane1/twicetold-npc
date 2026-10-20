"""Real Postgres contracts on the suite-owned disposable database only."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import replace
from unittest.mock import Mock

import httpx
import psycopg
import pytest
from conftest import BASE_CONFIG, NOW, run_structural

from app import db, doctor
from app.config import REPO_ROOT, ConfigError
from app.embedding_space import embedding_configuration
from app.runtime import open_runtime_pool


def test_api_rejects_mismatch_before_warming_or_building_providers(scene, monkeypatch):
    from app import api

    warm = Mock(side_effect=AssertionError("must not warm NLP"))
    build = Mock(side_effect=AssertionError("must not build providers"))
    monkeypatch.setattr(api, "warm_pipelines", warm)
    monkeypatch.setattr(api, "build_providers", build)
    monkeypatch.setattr(
        api, "load_settings", lambda: replace(scene.settings, provider_mode="real")
    )

    async def scenario(ctx):
        await db.ensure_embedding_space(ctx.pool, ctx.settings)
        with pytest.raises(ConfigError, match="does not match"):
            async with api._lifespan(api.app):
                raise AssertionError("must not start")
        assert not warm.called and not build.called

    run_structural(scene, scenario)


def test_runtime_binds_once_and_rejects_mode_change_even_when_empty(scene):
    async def scenario(ctx):
        pool = await open_runtime_pool(ctx.settings)
        await pool.close()
        await db.ensure_embedding_space(ctx.pool, ctx.settings)
        row = await ctx.fetchrow("SELECT configuration FROM embedding_space")
        assert row[0] == embedding_configuration(ctx.settings)
        with pytest.raises(ConfigError, match="does not match"):
            await open_runtime_pool(replace(ctx.settings, provider_mode="real"))
        assert (await ctx.fetchrow("SELECT count(*) FROM embedding_space"))[0] == 1

    run_structural(scene, scenario)


def test_competing_startups_cannot_bind_different_spaces(scene):
    async def scenario(ctx):
        results = await asyncio.gather(
            db.ensure_embedding_space(ctx.pool, ctx.settings),
            db.ensure_embedding_space(
                ctx.pool, replace(ctx.settings, provider_mode="real")
            ),
            return_exceptions=True,
        )
        assert sum(result is None for result in results) == 1
        assert sum(isinstance(result, ConfigError) for result in results) == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM embedding_space"))[0] == 1

    run_structural(scene, scenario)


def test_legacy_vectors_require_attestation_and_remain_unchanged(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("legacy", BASE_CONFIG)
        await ctx.seed(agent, "Mara crossed the ford.", NOW)
        before = await ctx.fetchrow("SELECT embedding::text FROM memory_fact_versions")
        with pytest.raises(ConfigError, match="no recorded embedding"):
            await db.ensure_embedding_space(ctx.pool, ctx.settings)
        assert (await ctx.fetchrow("SELECT count(*) FROM embedding_space"))[0] == 0
        with psycopg.connect(ctx.settings.database_uri) as conn:
            assert (
                db.inspect_embedding_space(conn, ctx.settings, adopt_existing=True)
                == "adopted"
            )
        await db.ensure_embedding_space(ctx.pool, ctx.settings)
        assert (
            await ctx.fetchrow("SELECT embedding::text FROM memory_fact_versions")
            == before
        )
        with psycopg.connect(ctx.settings.database_uri) as conn:
            with pytest.raises(ConfigError, match="does not match"):
                db.inspect_embedding_space(
                    conn,
                    replace(ctx.settings, provider_mode="real"),
                    adopt_existing=True,
                )

    run_structural(scene, scenario)


def test_legacy_location_vectors_also_block_binding(scene):
    async def scenario(ctx):
        agent = await ctx.make_agent("location", BASE_CONFIG)
        await ctx.seed(agent, "At the ford.", NOW)
        # Model a degraded fact embedding with a surviving location vector.
        await ctx.execute(
            "UPDATE memories SET location_embedding = f.embedding FROM memory_fact_versions f WHERE memories.memory_id = f.memory_id"
        )
        await ctx.execute("UPDATE memory_fact_versions SET embedding = NULL")
        with pytest.raises(ConfigError, match="no recorded embedding"):
            await db.ensure_embedding_space(ctx.pool, ctx.settings)

    run_structural(scene, scenario)


def test_doctor_reads_without_binding_and_reports_pending_migration(scene):
    checks = doctor.check_database(scene.settings)
    assert all(c.status == "pass" for c in checks)
    with psycopg.connect(scene.database_uri) as conn:
        assert conn.execute("SELECT count(*) FROM embedding_space").fetchone()[0] == 0
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '010_embedding_space.sql'"
        )
        try:
            # On the same connection the missing version must be detected.
            conn.commit()
            checks = doctor.check_database(scene.settings)
            assert any(
                c.status == "fail" and "010_embedding_space.sql" in c.detail
                for c in checks
            )
        finally:
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ('010_embedding_space.sql')"
            )
    assert all(c.status == "pass" for c in doctor.check_database(scene.settings))


def test_agent_config_validation_is_atomic_at_database_boundary(scene):
    async def scenario(ctx):
        with pytest.raises(ValueError, match="unknown agent"):
            await db.insert_agent(
                ctx.pool,
                name="bad",
                seed_identity=None,
                rigidity=None,
                diagnosticity_goal=None,
                config={"retrieval_top_kk": 3},
            )
        assert (await ctx.fetchrow("SELECT count(*) FROM agents"))[0] == 0
        agent = await ctx.make_agent("valid", BASE_CONFIG)
        with pytest.raises(ValueError, match="must be > 0"):
            await db.merge_agent_config(
                ctx.pool, agent, {"decay_classes": {"episodic": 0}}
            )
        assert (await db.fetch_agent(ctx.pool, agent))["config"] == BASE_CONFIG
        merged = await db.merge_agent_config(ctx.pool, agent, {"retrieval_top_k": 3})
        assert merged == {**BASE_CONFIG, "retrieval_top_k": 3}

    run_structural(scene, scenario)


def test_invalid_agent_config_returns_http_422_before_service(scene, monkeypatch):
    from app import api

    monkeypatch.setattr(api.app.state, "service", None, raising=False)

    async def scenario(ctx):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://localhost"
        ) as client:
            response = await client.post(
                "/v1/agents",
                json={"name": "bad", "config": {"decay_classes": {"episodic": 0}}},
            )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "config"]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://localhost"
        ) as client:
            response = await client.post(
                "/v1/agents",
                content='{"name":"bad","config":{"tau_fallback_seconds":1e400}}',
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "config"]

    run_structural(scene, scenario)


def test_migration_runner_is_idempotent_with_embedding_binding(scene):
    async def scenario(ctx):
        await db.ensure_embedding_space(ctx.pool, ctx.settings)

    run_structural(scene, scenario)
    with psycopg.connect(scene.database_uri) as conn:
        before = conn.execute(
            "SELECT configuration, recorded_at FROM embedding_space"
        ).fetchone()
    for _ in range(2):
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "db" / "migrate.py"),
                "--database-uri",
                scene.database_uri,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert "0 pending" in result.stdout
    with psycopg.connect(scene.database_uri) as conn:
        assert (
            conn.execute(
                "SELECT configuration, recorded_at FROM embedding_space"
            ).fetchone()
            == before
        )
