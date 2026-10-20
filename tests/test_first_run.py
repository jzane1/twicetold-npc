"""First-run example stays executable over real HTTP routes with fake models."""

from __future__ import annotations

import argparse
import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from conftest import NOW, run_structural

from app import first_run


def test_scene_stability_allows_query_score_and_ranking_variation():
    items = [
        {
            "memory_id": "a",
            "detail_id": "a1",
            "content": "stored a",
            "read_mode": "reconstructed",
            "pinned": False,
            "score": 0.3,
        },
        {
            "memory_id": "b",
            "detail_id": "b1",
            "content": "stored b",
            "read_mode": "verbatim",
            "pinned": True,
            "score": 0.300001,
        },
    ]
    varied = [dict(item, score=item["score"] + 0.00001) for item in reversed(items)]
    assert first_run.telling_snapshot(items) == first_run.telling_snapshot(varied)


@pytest.mark.parametrize(
    "field,value",
    [
        ("memory_id", "other"),
        ("detail_id", "new-version"),
        ("content", "changed text"),
        ("read_mode", "verbatim"),
        ("pinned", True),
    ],
)
def test_scene_stability_still_detects_changed_stored_tellings(field, value):
    item = {
        "memory_id": "a",
        "detail_id": "a1",
        "content": "stored a",
        "read_mode": "reconstructed",
        "pinned": False,
    }
    assert first_run.telling_snapshot([item]) != first_run.telling_snapshot(
        [dict(item, **{field: value})]
    )


@pytest.mark.nlp
def test_complete_http_demo_and_repeat_run_keep_independent_history(scene, monkeypatch):
    async def scenario(ctx):
        from app import api
        from app.dialogue import DialogueService

        retrieval = ctx.retrieval()
        monkeypatch.setattr(api.app.state, "service", ctx.ingest(), raising=False)
        monkeypatch.setattr(api.app.state, "retrieval", retrieval, raising=False)
        monkeypatch.setattr(
            api.app.state,
            "dialogue",
            DialogueService(
                ctx.pool,
                ctx.providers(),
                ctx.settings,
                retrieval,
            ),
            raising=False,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app),
            base_url="http://localhost",
        ) as client:
            reports = [
                await first_run.run_demo(
                    client,
                    mode="fake",
                    public_url="http://localhost",
                    start=NOW,
                    emit=lambda _: None,
                )
                for _ in range(2)
            ]
            assert all(r["ok"] and len(r["checks"]) == 6 for r in reports)
            assert reports[0]["agent_id"] != reports[1]["agent_id"]
            assert set(reports[0]["memory_ids"]).isdisjoint(reports[1]["memory_ids"])
            for report in reports:
                link = urlsplit(report["inspector_url"])
                assert (await client.get(link.path)).status_code == 200
                assert parse_qs(link.query) == {
                    "agent": [report["agent_id"]],
                    "memory": [report["memory_ids"][0]],
                }
                chain = (
                    await client.get(f"/v1/memories/{report['memory_ids'][0]}/chain")
                ).json()
                assert chain == report["chain"] | {"total_ms": chain["total_ms"]}
                assert report["repeat"]["instrumentation"]["cache_misses"] == 0
                assert report["usage"]["reconstruction_input_tokens"] > 0
                assert len([d for d in chain["details"] if d["is_live"]]) == 1
                assert json.loads(json.dumps(report))["ok"]

    run_structural(scene, scenario)


@pytest.mark.parametrize("failure", ["timeout", "http", "json"])
def test_http_failure_is_safe_and_never_retries_a_write(failure):
    requests = []

    def handler(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("secret response", request=request)
        if failure == "http":
            return httpx.Response(500, text="secret response")
        return httpx.Response(200, text="secret response")

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://localhost",
        ) as client:
            with pytest.raises(first_run.DemoError) as error:
                await first_run.run_demo(
                    client,
                    mode="fake",
                    public_url="http://localhost",
                    emit=lambda _: None,
                )
            assert "secret" not in str(error.value)
            assert "POST" in str(error.value) or "JSON" in str(error.value)

    asyncio.run(scenario())
    assert len(requests) == 1 and requests[0].method == "POST"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://localhost",
        "http://",
        "http://user:secret@localhost",
        "http://localhost?key=secret",
        "http://localhost/path",
        "http://localhost:bad",
    ],
)
def test_demo_origin_validation_does_not_echo_credentials(url):
    with pytest.raises(argparse.ArgumentTypeError) as error:
        first_run.base_url(url)
    assert "secret" not in str(error.value)


def test_mode_mismatch_fails_before_making_requests(monkeypatch, capsys):
    from app import config

    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: config.Settings(database_uri="unused", provider_mode="fake"),
    )
    monkeypatch.setattr(
        first_run, "run_demo", lambda *a, **k: pytest.fail("must not call API")
    )
    assert first_run.main(["--mode", "real", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


@pytest.mark.parametrize("flag", ["scoring_failed", "embedding_failed"])
def test_successful_http_status_with_degraded_observation_fails_the_demo(flag):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/v1/agents":
            return httpx.Response(200, json={"agent_id": "created-agent"})
        result = {
            key: False
            for key in (
                "scoring_failed",
                "embedding_failed",
                "escalation_failed",
                "enrichment_pending",
                "decay_class_unknown",
            )
        }
        return httpx.Response(
            200, json={**result, flag: True, "memory_id": "created-memory"}
        )

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost"
        ) as client:
            with pytest.raises(first_run.DemoError, match="Observation degraded"):
                await first_run.run_demo(
                    client,
                    mode="fake",
                    public_url="http://localhost",
                    emit=lambda _: None,
                )

    asyncio.run(scenario())
    assert calls == ["/v1/agents", "/v1/events/observe"]


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(SystemExit) as error:
        first_run.main(["--mode", "fake", f"--timeout={timeout}"])
    assert error.value.code == 2
