"""provider_transport.py — canned in-process HTTP for the REAL provider
classes (the provider-path build, 2026-09-02).

Both SDK clients accept an injected `http_client`; an `httpx.Client` over
`httpx.MockTransport` answers every request in-process, so Set Q and the
`verify_provider_path` walker drive the real `Real*` classes with no socket
and no key (tests\\CLAUDE.md: offline, keyless, deterministic). The helpers
here are response BUILDERS in the exact wire shapes the SDKs parse — the
OpenAI chat completion (JSON and SSE with a trailing usage chunk), the OpenAI
embeddings list (base64 float32, the SDK's default encoding), and the
Anthropic message (JSON and the six-event SSE sequence) — plus a request
`Recorder` so scenarios assert on what actually went over the wire.

Error fixtures use 4xx only: both SDKs retry 408/409/429/5xx with backoff
sleeps, and a test must never sit through one.

Imported by tests, never by app\\ (the scratch_uri.py helper precedent).
"""

from __future__ import annotations

import array
import base64
import json
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.providers import FakeEmbeddingProvider


@dataclass
class RecordedRequest:
    method: str
    url: str
    path: str
    headers: dict[str, str]  # lower-cased names
    body: object  # parsed JSON when the body was JSON, else the raw bytes


class Recorder:
    """Every request the mock transport saw, in order."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []

    @property
    def last(self) -> RecordedRequest:
        return self.requests[-1]

    def record(self, request: httpx.Request) -> RecordedRequest:
        raw = request.read()
        body: object = None
        if raw:
            try:
                body = json.loads(raw)
            except ValueError:
                body = raw
        entry = RecordedRequest(
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            headers={k.lower(): v for k, v in request.headers.items()},
            body=body,
        )
        self.requests.append(entry)
        return entry


Route = httpx.Response | Callable[[RecordedRequest], httpx.Response]


def mock_client(
    routes: dict[str, Route], recorder: Recorder | None = None
) -> httpx.Client:
    """An httpx.Client whose transport answers in-process. `routes` maps a
    path SUFFIX ("/chat/completions", "/embeddings", "/v1/messages") to a
    canned Response or a callable of the recorded request; a canned Response
    is re-materialized per request so it can answer repeatedly. Unrouted
    paths answer 404 (loud in the SDK, never a silent success)."""
    rec = recorder or Recorder()

    def handler(request: httpx.Request) -> httpx.Response:
        entry = rec.record(request)
        for suffix, route in routes.items():
            if entry.path.endswith(suffix):
                if callable(route):
                    return route(entry)
                return httpx.Response(
                    route.status_code, headers=route.headers, content=route.read()
                )
        return httpx.Response(
            404, json={"error": {"message": f"unrouted path {entry.path}"}}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# OpenAI-compatible shapes
# ---------------------------------------------------------------------------


def _usage_block(usage: tuple[int, int]) -> dict:
    return {
        "prompt_tokens": usage[0],
        "completion_tokens": usage[1],
        "total_tokens": usage[0] + usage[1],
    }


def openai_chat_json(
    text: str | None,
    *,
    usage: tuple[int, int] | None = (7, 3),
    choices: bool = True,
    model: str = "canned",
) -> httpx.Response:
    """A non-streaming chat completion. `text=None` mirrors a server that
    returns a null content; `choices=False` an empty choices list; `usage=None`
    a server that reports no usage at all."""
    payload: dict = {
        "id": "chatcmpl-canned",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": (
            [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ]
            if choices
            else []
        ),
    }
    if usage is not None:
        payload["usage"] = _usage_block(usage)
    return httpx.Response(200, json=payload)


def _sse(events: list[str]) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="".join(events).encode("utf-8"),
    )


def _chunk(model: str, **fields) -> str:
    payload = {
        "id": "chatcmpl-canned",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": model,
        **fields,
    }
    return "data: " + json.dumps(payload) + "\n\n"


def openai_chat_sse(
    chunks: list[str],
    *,
    usage: tuple[int, int] | None = (7, 3),
    error_after: int | None = None,
    model: str = "canned",
) -> httpx.Response:
    """A streamed chat completion: one content delta per chunk, a stop
    chunk, the trailing usage chunk (`stream_options.include_usage`), then
    `[DONE]`. `error_after=n` emits n deltas and then an error event — the
    SDK raises from the iterator mid-stream, the keep-partial contract."""
    events: list[str] = []
    for i, text in enumerate(chunks):
        if error_after is not None and i == error_after:
            events.append(
                "data: "
                + json.dumps(
                    {
                        "error": {
                            "message": "canned mid-stream failure",
                            "type": "server_error",
                        }
                    }
                )
                + "\n\n"
            )
            return _sse(events)
        events.append(
            _chunk(
                model,
                choices=[
                    {"index": 0, "delta": {"content": text}, "finish_reason": None}
                ],
            )
        )
    events.append(
        _chunk(model, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
    )
    if usage is not None:
        events.append(_chunk(model, choices=[], usage=_usage_block(usage)))
    events.append("data: [DONE]\n\n")
    return _sse(events)


def openai_embeddings(
    vectors: list[list[float]],
    *,
    usage: int | None = 5,
    as_base64: bool = True,
    model: str = "canned-embed",
) -> httpx.Response:
    """An embeddings list. base64 float32 by default — the SDK's default
    `encoding_format`, which the provider deliberately leaves alone so
    hosted bytes stay unchanged; float lists model a server that ignores
    the parameter. Fixture values should be float32-exact (multiples of
    1/256) so round-trips compare with ==."""
    data = []
    for i, vec in enumerate(vectors):
        if as_base64:
            encoded: object = base64.b64encode(array.array("f", vec).tobytes()).decode(
                "ascii"
            )
        else:
            encoded = list(vec)
        data.append({"object": "embedding", "index": i, "embedding": encoded})
    payload: dict = {"object": "list", "data": data, "model": model}
    if usage is not None:
        payload["usage"] = {"prompt_tokens": usage, "total_tokens": usage}
    return httpx.Response(200, json=payload)


def fake_embedding_route(entry: RecordedRequest) -> httpx.Response:
    """The mock server IS the locality-sensitive fake: it answers with
    FakeEmbeddingProvider().embed(input), so a served beat over a mock-backed
    RealEmbeddingProvider retrieves meaningfully against fake-seeded rows."""
    inputs = entry.body["input"]  # type: ignore[index]
    if isinstance(inputs, str):
        inputs = [inputs]
    result = FakeEmbeddingProvider().embed(list(inputs))
    return openai_embeddings(result.vectors, usage=result.tokens)


def http_error(status: int, message: str = "canned error") -> httpx.Response:
    """A 4xx error body both SDKs map to their *Error classes without a
    retry (never 5xx here — see the module docstring)."""
    return httpx.Response(
        status,
        json={"error": {"message": message, "type": "invalid_request_error"}},
    )


# ---------------------------------------------------------------------------
# Anthropic shapes
# ---------------------------------------------------------------------------


def anthropic_message(
    text: str, *, usage: tuple[int, int] = (7, 3), model: str = "canned"
) -> httpx.Response:
    """A non-streaming Messages response with one text block."""
    return httpx.Response(
        200,
        json={
            "id": "msg_canned",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]},
        },
    )


def anthropic_message_sse(
    chunks: list[str], *, usage: tuple[int, int] = (7, 3), model: str = "canned"
) -> httpx.Response:
    """The six-event streamed Messages sequence the SDK accumulates:
    message_start (input tokens) -> content_block_start -> text deltas ->
    content_block_stop -> message_delta (output tokens) -> message_stop."""

    def event(name: str, data: dict) -> str:
        return f"event: {name}\ndata: {json.dumps(data)}\n\n"

    events = [
        event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_canned",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": usage[0], "output_tokens": 1},
                },
            },
        ),
        event(
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
    ]
    for text in chunks:
        events.append(
            event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": text},
                },
            )
        )
    events += [
        event("content_block_stop", {"type": "content_block_stop", "index": 0}),
        event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": usage[1]},
            },
        ),
        event("message_stop", {"type": "message_stop"}),
    ]
    return _sse(events)
