"""Application integration: public HTTP contracts and byte-identical context only."""

import asyncio
import copy
import json
from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from conftest import NOW, run_structural

from examples import chat, memory_chat as example

AGENT, MEMORY, DETAIL = (str(uuid4()) for _ in range(3))
ITEM = {
    "memory_id": MEMORY,
    "detail_id": DETAIL,
    "content": "Fixture memory.",
    "read_mode": "verbatim",
    "score": 0.5,
}


def transport(requests, *, items=None, degraded=False):
    def handle(request):
        body = json.loads(request.content) if request.content else None
        requests.append((request.url.path, body))
        if request.url.path == "/v1/events/scene-boundary":
            return httpx.Response(
                200, json={"accepted": True, "identity_version": "v1"}
            )
        if request.url.path == "/v1/dialogue/init":
            return httpx.Response(
                200,
                json={
                    "items": [ITEM] if items is None else items,
                    "instrumentation": {"degraded": degraded},
                },
            )
        if request.url.path.endswith("/correction"):
            return httpx.Response(
                200, json={"memory_id": MEMORY, "detail_id": str(uuid4())}
            )
        raise AssertionError(request.url.path)

    return httpx.MockTransport(handle)


class Recorder:
    def __init__(self):
        self.messages = []
        self.failure = None

    async def __call__(self, messages):
        self.messages.append(copy.deepcopy(messages))
        if self.failure:
            raise self.failure
        return example.Completion("Fixture answer.", {"completion_tokens": 3})


def test_followup_uses_bounded_pairs_in_model_and_retrieval_without_observing_chat():
    async def scenario():
        requests, model = [], Recorder()
        async with httpx.AsyncClient(
            transport=transport(requests), base_url="http://localhost"
        ) as http:
            app = example.Conversation(
                example.MemoryAPI(http), AGENT, model, history_turns=1
            )
            first = await app.say("Where is it?", NOW)
            second = await app.say("Why?", NOW + timedelta(hours=1))
            third = await app.say("And then?", NOW + timedelta(hours=2))
            assert first["recent_messages_sent"] == 0
            assert second["recent_messages_sent"] == third["recent_messages_sent"] == 2
            assert [m["role"] for m in model.messages[1]] == [
                "system",
                "user",
                "assistant",
                "user",
            ]
            assert model.messages[1][1:3] == [
                {"role": "user", "content": "Where is it?"},
                {"role": "assistant", "content": first["content"]},
            ]
            assert model.messages[2][1]["content"] == "Why?"
            assert json.loads(model.messages[1][-1]["content"]) == {
                "question": "Why?",
                "memories": [ITEM],
            }
            reads = [body for path, body in requests if path == "/v1/dialogue/init"]
            assert (
                reads[1]["query_text"]
                == f"user: Where is it?\nassistant: {first['content']}\nuser: Why?"
            )
            assert all(
                body["identity_version"] == "v1"
                and body["scene_started_at"] == NOW.isoformat()
                and body["k"] == 3
                for body in reads
            )
            assert reads[1]["as_of"] == (NOW + timedelta(hours=1)).isoformat()
            assert all("loaded_memory_ids" not in body for body in reads)
            assert {path for path, _ in requests} == {
                "/v1/events/scene-boundary",
                "/v1/dialogue/init",
            }
            assert (
                third["used_memory_ids"] == [MEMORY] and not third["omitted_memory_ids"]
            )
            assert third["model_usage"] == {"completion_tokens": 3}

    asyncio.run(scenario())


@pytest.mark.parametrize("history_turns,history_chars", [(0, 100), (4, 0), (4, 5)])
def test_history_limits_discard_whole_oversized_pairs(history_turns, history_chars):
    async def scenario():
        async with httpx.AsyncClient(
            transport=transport([]), base_url="http://localhost"
        ) as http:
            app = example.Conversation(
                example.MemoryAPI(http),
                AGENT,
                Recorder(),
                history_turns=history_turns,
                history_chars=history_chars,
            )
            await app.say("Question", NOW)
            assert app.history == []

    asyncio.run(scenario())


def test_character_budget_evicts_oldest_pair_and_memory_budget_omits_whole_records():
    async def scenario():
        oversized = ITEM | {"memory_id": str(uuid4()), "content": "x" * 5000}
        model = Recorder()
        async with httpx.AsyncClient(
            transport=transport([], items=[oversized, ITEM]),
            base_url="http://localhost",
        ) as http:
            app = example.Conversation(
                example.MemoryAPI(http),
                AGENT,
                model,
                history_chars=30,
                memory_chars=300,
            )
            await app.say("one", NOW)
            result = await app.say("two", NOW)
            assert app.history == [("two", "Fixture answer.")]
            assert result["used_memory_ids"] == [MEMORY]
            assert result["omitted_memory_ids"] == [oversized["memory_id"]]
            assert json.loads(model.messages[-1][-1]["content"])["memories"] == [ITEM]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure", [example.IntegrationError("model failed"), asyncio.CancelledError()]
)
def test_failed_or_cancelled_model_turn_never_enters_history(failure):
    async def scenario():
        model = Recorder()
        async with httpx.AsyncClient(
            transport=transport([]), base_url="http://localhost"
        ) as http:
            app = example.Conversation(example.MemoryAPI(http), AGENT, model)
            await app.say("one", NOW)
            before = copy.deepcopy(app.history)
            model.failure = failure
            with pytest.raises(type(failure)):
                await app.say("two", NOW)
            assert app.history == before

    asyncio.run(scenario())


def test_degraded_retrieval_and_oversized_input_do_not_call_dialogue():
    async def scenario():
        model, requests = Recorder(), []
        async with httpx.AsyncClient(
            transport=transport(requests, degraded=True), base_url="http://localhost"
        ) as http:
            app = example.Conversation(
                example.MemoryAPI(http), AGENT, model, input_chars=5
            )
            with pytest.raises(ValueError):
                await app.say("too long", NOW)
            assert not requests
            with pytest.raises(example.IntegrationError):
                await app.say("ok", NOW)
            assert not model.messages and not app.history

    asyncio.run(scenario())


def test_scene_and_correction_reset_history_only_on_success():
    async def scenario():
        requests, fail = [], False
        normal = transport(requests)

        async def handler(request):
            if fail:
                return httpx.Response(409, text="private body")
            return await normal.handle_async_request(request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost"
        ) as http:
            app = example.Conversation(example.MemoryAPI(http), AGENT, Recorder())
            await app.say("one", NOW)
            before = copy.deepcopy(app.history)
            fail = True
            with pytest.raises(example.IntegrationError):
                await app.begin_scene(NOW + timedelta(days=1))
            with pytest.raises(example.IntegrationError):
                await app.correct(MEMORY, DETAIL, "Operator fix.", NOW)
            assert (
                app.history == before
                and app.scene["scene_started_at"] == NOW.isoformat()
            )
            fail = False
            await app.correct(MEMORY, DETAIL, "Operator fix.", NOW)
            assert not app.history
            assert requests[-1][1]["expected_detail_id"] == DETAIL
            await app.say("two", NOW)
            await app.begin_scene(NOW + timedelta(days=1))
            assert not app.history and app.scene["scene_started_at"] != NOW.isoformat()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure", ["timeout", 408, 429, 500, 502, 503, 504, 409, 422, 401]
)
def test_observe_retry_policy_preserves_exact_payload(failure):
    async def scenario():
        sent, delays = [], []
        payload = example.MemoryAPI.observation(AGENT, "Saved event.", NOW)
        snapshot = copy.deepcopy(payload)

        def handler(request):
            sent.append(request.content)
            payload["observation_text"] = "Caller mutation during delivery."
            if len(sent) == 1:
                if failure == "timeout":
                    raise httpx.ReadTimeout("private key", request=request)
                return httpx.Response(failure, text="private key")
            return httpx.Response(200, json={"memory_id": MEMORY, "detail_id": DETAIL})

        async def no_wait(seconds):
            delays.append(seconds)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://localhost"
        ) as http:
            memory = example.MemoryAPI(http)
            memory._sleep = no_wait
            if failure in {409, 422, 401}:
                with pytest.raises(example.IntegrationError) as error:
                    await memory.observe(payload)
                assert error.value.status == failure and "private" not in str(
                    error.value
                )
                assert len(sent) == 1 and not delays
            else:
                assert (await memory.observe(payload))["memory_id"] == MEMORY
                assert len(sent) == 2 and sent[0] == sent[1]
                assert delays == [0.5]
            assert json.loads(sent[0]) == snapshot

    asyncio.run(scenario())


def test_exhausted_delivery_survives_restart_and_replays_same_event(tmp_path):
    async def scenario():
        path = tmp_path / "state.json"
        state = chat.LocalState(path, "http://localhost")
        state.data["agent_id"] = AGENT
        payload = example.MemoryAPI.observation(AGENT, "Saved event.", NOW)
        sent, delays = [], []

        def fail(request):
            assert json.loads(path.read_text(encoding="utf-8"))["pending"] == payload
            sent.append(request.content)
            raise httpx.ReadTimeout("private key", request=request)

        async def no_wait(seconds):
            delays.append(seconds)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(fail), base_url="http://localhost"
        ) as http:
            memory = example.MemoryAPI(http)
            memory._sleep = no_wait
            with pytest.raises(example.IntegrationError):
                await state.deliver(memory, payload)
        assert len(sent) == 3 and delays == [0.5, 1.0]
        restored = chat.LocalState(path, "http://localhost")
        assert restored.data["pending"] == payload

        def succeed(request):
            assert request.content == sent[0]
            return httpx.Response(200, json={"memory_id": MEMORY, "detail_id": DETAIL})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(succeed), base_url="http://localhost"
        ) as http:
            await restored.deliver(example.MemoryAPI(http))
        assert chat.LocalState(path, "http://localhost").data["pending"] is None
        before = path.read_bytes()
        with pytest.raises(example.IntegrationError):
            chat.LocalState(path, "http://different-service")
        assert path.read_bytes() == before

    asyncio.run(scenario())


@pytest.mark.parametrize("token_field", ["max_tokens", "max_completion_tokens"])
def test_real_dialogue_adapter_wire_shape_and_usage(token_field):
    async def scenario():
        messages = [
            {"role": "system", "content": "instructions"},
            {"role": "user", "content": "fixture input"},
        ]

        def handler(request):
            assert str(request.url) == "http://model.invalid/v1/chat/completions"
            assert request.headers["authorization"] == "Bearer placeholder"
            assert json.loads(request.content) == {
                "model": "test-model",
                "messages": messages,
                "stream": False,
                token_field: 64,
            }
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": "fixture output"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 7},
                },
            )

        async with httpx.AsyncClient(
            base_url="http://model.invalid/v1/",
            headers={"Authorization": "Bearer placeholder"},
            transport=httpx.MockTransport(handler),
        ) as http:
            response = await example.ChatCompletionsDialogue(
                http, "test-model", max_output_tokens=64, token_limit_field=token_field
            )(messages)
            assert response == example.Completion(
                "fixture output", {"prompt_tokens": 7}
            )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": []},
        {"choices": None},
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]},
    ],
)
def test_model_rejects_missing_or_incomplete_answer(payload):
    async def scenario():
        async with httpx.AsyncClient(
            base_url="http://model.invalid/v1/",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
        ) as http:
            with pytest.raises(example.IntegrationError):
                await example.ChatCompletionsDialogue(http, "test-model")([])

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "args",
    [
        ["--dialogue", "real"],
        ["--timeout", "nan"],
        ["--history-turns", "-1"],
        ["--base-url", "http://user:secret@localhost"],
        ["--model-base-url", "https://model.invalid/v1?api_key=secret"],
        ["--memory-chars", "0"],
        ["--observe-attempts", "0"],
    ],
)
def test_cli_rejects_bad_configuration_before_network(args, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("network client constructed")

    monkeypatch.setattr(chat.httpx, "AsyncClient", forbidden)
    with pytest.raises(SystemExit) as error:
        chat.main(args)
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "secret" not in captured.out + captured.err


@pytest.mark.nlp
def test_cli_demo_over_public_routes_with_lost_ack_and_external_model(
    scene, tmp_path, monkeypatch
):
    async def scenario(ctx):
        from app import api

        ingest = ctx.ingest()
        retrieval = ctx.retrieval()
        ingest._retrieval = retrieval
        monkeypatch.setattr(api.app.state, "service", ingest, raising=False)
        monkeypatch.setattr(api.app.state, "retrieval", retrieval, raising=False)
        asgi = httpx.ASGITransport(app=api.app)
        requests, model_messages, observes = [], [], []

        async def api_handler(request):
            assert "authorization" not in request.headers
            requests.append(request.url.path)
            response = await asgi.handle_async_request(request)
            if request.url.path == "/v1/events/observe":
                observes.append(request.content)
                if len(observes) == 1:
                    await response.aread()
                    raise httpx.ReadTimeout("lost ACK after commit", request=request)
            return response

        def model_handler(request):
            assert request.headers["authorization"] == "Bearer placeholder"
            model_messages.append(json.loads(request.content)["messages"])
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": "Fixture model answer."},
                            "finish_reason": "stop",
                        }
                    ]
                },
            )

        client_class = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(
                model_handler if "model.invalid" in kwargs["base_url"] else api_handler
            )
            return client_class(*args, **kwargs)

        monkeypatch.setattr(chat.httpx, "AsyncClient", client_factory)
        monkeypatch.setenv("EXAMPLE_DIALOGUE_API_KEY", "placeholder")
        original_memory = chat.MemoryAPI

        async def no_wait(_):
            pass

        def memory_factory(*args, **kwargs):
            result = original_memory(*args, **kwargs)
            result._sleep = no_wait
            return result

        monkeypatch.setattr(chat, "MemoryAPI", memory_factory)
        args = chat.parser().parse_args(
            [
                "--base-url",
                "http://localhost",
                "--state",
                str(tmp_path / "session.json"),
                "--demo",
                "--dialogue",
                "real",
                "--model-base-url",
                "http://model.invalid/v1",
                "--model",
                "fixture-model",
            ]
        )
        await chat.run(args, clock=lambda: NOW)
        saved = chat.LocalState(args.state, args.base_url)
        assert saved.data["pending"] is None
        assert len(observes) == 3 and observes[0] == observes[1] == observes[2]
        assert (await ctx.fetchrow("SELECT count(*) FROM agents"))[0] == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM memories"))[0] == 1
        assert (await ctx.fetchrow("SELECT count(*) FROM observation_receipts"))[0] == 1
        assert "/v1/dialogue/turn" not in requests
        assert [len(messages) for messages in model_messages] == [2, 4, 2]
        assert model_messages[1][2]["content"] == "Fixture model answer."
        original = json.loads(model_messages[0][-1]["content"])["memories"][0]
        corrected = json.loads(model_messages[2][-1]["content"])["memories"][0]
        assert original["memory_id"] == corrected["memory_id"]
        assert original["detail_id"] != corrected["detail_id"]
        assert len(await ctx.chain(UUID(original["memory_id"]))) == 2
        # A new application process can attach to the same agent. Its chat history
        # is deliberately empty and no provisioning request occurs again.
        before = requests.count("/v1/agents")
        async with client_factory(base_url=args.base_url) as http:
            attached = example.Conversation(
                original_memory(http), saved.data["agent_id"], Recorder()
            )
            reply = await attached.say("What was left?", NOW)
            assert reply["recent_messages_sent"] == 0 and reply["items"]
        assert requests.count("/v1/agents") == before

    run_structural(scene, scenario)
