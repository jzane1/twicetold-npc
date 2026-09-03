"""Set Q — the provider path (docs\\test-suite.md; the provider-path build
ruled 2026-09-01, its forks ruled 2026-09-02 — the explicit backend selector,
zero-padded embedding widths, Anthropic the default byte-for-byte).

Structural-only per tests\\CLAUDE.md, and OFFLINE + KEYLESS like the rest of
the suite: the REAL provider classes run here against canned in-process HTTP
handlers (`tests\\provider_transport.py` — httpx.MockTransport injected as the
SDK clients' `http_client`), so every request shape and every response
contract is asserted without a socket or a key. No scenario needs the
database; none carries the `nlp` marker.

What Set Q owns: the config matrix (every loud ConfigError row, the defaults,
fake mode reading nothing new, the process-env override allowlist), the
OpenAI-compatible backend's request shape per role and its response handling
(usage absent, empty content, malformed JSON, HTTP errors, the small-model
hardening), streaming (chunks byte-identical, the trailing usage chunk, the
pre-first-chunk vs mid-stream error contracts), the Anthropic backend's
request-shape PINS (today's bytes, so the seam move is provable), the
embedding width fit (pad / pass / refuse) + tokens + client selection, and the
offline wiring of `build_providers` on both backends.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from uuid import uuid4

import pytest
from provider_transport import (
    Recorder,
    anthropic_message,
    anthropic_message_sse,
    http_error,
    mock_client,
    openai_chat_json,
    openai_chat_sse,
    openai_embeddings,
)

import app.providers as providers_module
from app.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_DEFAULT,
    ENV_DIALOGUE_THINKING,
    ENV_EMBEDDING_API_KEY,
    ENV_EMBEDDING_BASE_URL,
    ENV_EMBEDDING_MODEL,
    ENV_MODEL_API_KEY,
    ENV_MODEL_BACKEND,
    ENV_MODEL_BASE_URL,
    PLACEHOLDER_API_KEY,
    ConfigError,
    load_env,
    load_settings,
)
from app.providers import (
    AnthropicChatBackend,
    CompilerItem,
    FakeWriteProvider,
    MalformedOutputError,
    OpenAIChatBackend,
    ProviderCallError,
    RealCompilerProvider,
    RealDialogueProvider,
    RealEmbeddingProvider,
    RealEscalationProvider,
    RealJudgeProvider,
    RealReconstructionProvider,
    RealReflectionProvider,
    RealWriteProvider,
    ReconstructionItem,
    build_chat_backend,
    build_compiler_provider,
    build_judge_provider,
    build_providers,
    build_reflection_provider,
)

UNREACHABLE_URI = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"
SIX_ROLES = {
    "TWICETOLD_MODEL_IMPORTANCE": "model-w",
    "TWICETOLD_MODEL_RENDER": "model-w",
    "TWICETOLD_MODEL_TYPOLOGY": "model-w",
    "TWICETOLD_MODEL_ESCALATION": "model-e",
    "TWICETOLD_MODEL_DIALOGUE": "model-d",
    "TWICETOLD_MODEL_RECONSTRUCTION": "model-r",
}
# Today's real-mode env (the Set I shape): anthropic by default, both keys.
REAL_ENV = {
    "DATABASE_URI": UNREACHABLE_URI,
    "TWICETOLD_PROVIDER_MODE": "real",
    "ANTHROPIC_API_KEY": "k1",
    "OPENAI_API_KEY": "k2",
    **SIX_ROLES,
}
# The openai backend against a local server: no Anthropic key, no OpenAI
# key (the embedding rides its own base URL), the six roles naming local
# models.
LOCAL_ENV = {
    "DATABASE_URI": UNREACHABLE_URI,
    "TWICETOLD_PROVIDER_MODE": "real",
    ENV_MODEL_BACKEND: "openai",
    ENV_MODEL_BASE_URL: "http://127.0.0.1:11434/v1",
    ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1",
    ENV_EMBEDDING_MODEL: "nomic-embed-text",
    **SIX_ROLES,
}


# ---------------------------------------------------------------------------
# Config: the ruled matrix as regression tests
# ---------------------------------------------------------------------------


def test_config_default_backend_is_anthropic():
    """No new var set => today's shape exactly: anthropic, no base URL, no
    model key, the locked slate's embedding model; Set I's REAL_ENV loads."""
    settings = load_settings(dict(REAL_ENV))
    assert settings.model_backend == "anthropic"
    assert settings.model_base_url == ""
    assert settings.model_api_key == ""
    assert settings.embedding_model == EMBEDDING_MODEL_DEFAULT
    assert settings.embedding_base_url == ""
    assert settings.embedding_api_key == ""
    # secrets stay off the repr
    assert "k1" not in repr(settings) and "k2" not in repr(settings)


def test_config_backend_enum():
    """The selector is validated in BOTH modes; values case-fold."""
    with pytest.raises(ConfigError, match="'anthropic' or 'openai'"):
        load_settings({**REAL_ENV, ENV_MODEL_BACKEND: "bedrock"})
    with pytest.raises(ConfigError, match="'anthropic' or 'openai'"):
        load_settings(
            {
                "DATABASE_URI": UNREACHABLE_URI,
                "TWICETOLD_PROVIDER_MODE": "fake",
                ENV_MODEL_BACKEND: "bedrock",
            }
        )
    assert load_settings({**LOCAL_ENV, ENV_MODEL_BACKEND: "OpenAI"}).model_backend == (
        "openai"
    )


def test_config_openai_backend_requirements():
    """openai needs a base URL (http/https, trailing slash stripped), never
    an Anthropic key; the model key is optional and stays off the repr."""
    missing = {k: v for k, v in LOCAL_ENV.items() if k != ENV_MODEL_BASE_URL}
    with pytest.raises(ConfigError, match=ENV_MODEL_BASE_URL):
        load_settings(missing)
    with pytest.raises(ConfigError, match="http"):
        load_settings({**LOCAL_ENV, ENV_MODEL_BASE_URL: "ftp://127.0.0.1/v1"})
    loaded = load_settings({**LOCAL_ENV, ENV_MODEL_BASE_URL: "http://host:8000/v1/"})
    assert loaded.model_backend == "openai"
    assert loaded.model_base_url == "http://host:8000/v1"
    assert loaded.anthropic_api_key == "" and loaded.model_api_key == ""
    keyed = load_settings({**LOCAL_ENV, ENV_MODEL_API_KEY: "sk-local"})
    assert keyed.model_api_key == "sk-local"
    assert "sk-local" not in repr(keyed)
    # an Anthropic key left in .env is ignored, not a misconfiguration
    assert load_settings({**LOCAL_ENV, "ANTHROPIC_API_KEY": "k1"}).model_backend == (
        "openai"
    )


def test_config_anthropic_backend_rejects_url_and_key():
    """A base URL or model key under the (default) anthropic backend is a
    loud misconfiguration, never silently ignored."""
    with pytest.raises(ConfigError, match="is 'anthropic'"):
        load_settings({**REAL_ENV, ENV_MODEL_BASE_URL: "http://127.0.0.1:11434/v1"})
    with pytest.raises(ConfigError, match="is 'anthropic'"):
        load_settings({**REAL_ENV, ENV_MODEL_API_KEY: "sk-local"})
    # ...and the anthropic backend still requires its key in real mode
    keyless = {k: v for k, v in REAL_ENV.items() if k != "ANTHROPIC_API_KEY"}
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_settings(keyless)


def test_config_openai_backend_rejects_dialogue_thinking():
    """The thinking knob is an Anthropic request shape: loud under openai,
    in both modes; still fine under anthropic."""
    with pytest.raises(ConfigError, match="Anthropic request knob"):
        load_settings({**LOCAL_ENV, ENV_DIALOGUE_THINKING: "disabled"})
    with pytest.raises(ConfigError, match="Anthropic request knob"):
        load_settings(
            {
                "DATABASE_URI": UNREACHABLE_URI,
                "TWICETOLD_PROVIDER_MODE": "fake",
                ENV_MODEL_BACKEND: "openai",
                ENV_DIALOGUE_THINKING: "disabled",
            }
        )
    assert (
        load_settings({**REAL_ENV, ENV_DIALOGUE_THINKING: "disabled"}).dialogue_thinking
        == "disabled"
    )


def test_config_embedding_knobs():
    """The embedding role's knobs are independent of the model backend: the
    model name overrides; a base URL lifts the OPENAI_API_KEY requirement; a
    key without a URL is loud; a non-http URL is loud."""
    named = load_settings({**REAL_ENV, ENV_EMBEDDING_MODEL: "text-embedding-3-large"})
    assert named.embedding_model == "text-embedding-3-large"
    no_openai_key = {k: v for k, v in REAL_ENV.items() if k != "OPENAI_API_KEY"}
    with pytest.raises(ConfigError, match=ENV_EMBEDDING_BASE_URL):
        load_settings(no_openai_key)
    routed = load_settings(
        {**no_openai_key, ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1/"}
    )
    assert routed.embedding_base_url == "http://127.0.0.1:11434/v1"
    assert routed.openai_api_key == ""
    keyed = load_settings(
        {
            **no_openai_key,
            ENV_EMBEDDING_BASE_URL: "https://proxy.example/v1",
            ENV_EMBEDDING_API_KEY: "sk-embed",
        }
    )
    assert keyed.embedding_api_key == "sk-embed" and "sk-embed" not in repr(keyed)
    with pytest.raises(ConfigError, match=ENV_EMBEDDING_API_KEY):
        load_settings({**REAL_ENV, ENV_EMBEDDING_API_KEY: "sk-embed"})
    with pytest.raises(ConfigError, match="http"):
        load_settings({**REAL_ENV, ENV_EMBEDDING_BASE_URL: "localhost:11434"})
    # the anthropic backend + a routed embedding is a legal mix
    mixed = load_settings(
        {**no_openai_key, ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1"}
    )
    assert mixed.model_backend == "anthropic"


def test_config_fake_mode_reads_nothing_new():
    """Fake mode stays keyless and offline: the openai backend without a base
    URL or any key loads (presence rules are real-mode only); the knobs are
    still carried on Settings."""
    fake = load_settings(
        {
            "DATABASE_URI": UNREACHABLE_URI,
            "TWICETOLD_PROVIDER_MODE": "fake",
            ENV_MODEL_BACKEND: "openai",
            ENV_EMBEDDING_MODEL: "nomic-embed-text",
        }
    )
    assert fake.provider_mode == "fake"
    assert fake.model_backend == "openai"
    assert fake.model_base_url == ""
    assert fake.embedding_model == "nomic-embed-text"
    assert fake.anthropic_api_key == "" and fake.openai_api_key == ""


def test_override_allowlist_carries_new_keys(tmp_path, monkeypatch):
    """All six new keys ride the process-env override allowlist (the C7 knob
    precedent), so a one-off run can point at a local server without
    touching .env."""
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URI={UNREACHABLE_URI}\n", encoding="utf-8")
    overrides = {
        ENV_MODEL_BACKEND: "openai",
        ENV_MODEL_BASE_URL: "http://127.0.0.1:11434/v1",
        ENV_MODEL_API_KEY: "sk-local",
        ENV_EMBEDDING_MODEL: "nomic-embed-text",
        ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1",
        ENV_EMBEDDING_API_KEY: "sk-embed",
    }
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    values = load_env(env_file)
    for key, value in overrides.items():
        assert values[key] == value


# ---------------------------------------------------------------------------
# The OpenAI-compatible backend over canned transport (request shape +
# response contracts; structure only, never prose)
# ---------------------------------------------------------------------------

WRITE_PAYLOAD = {
    "rendered_content": "[canned] I watched the lantern shatter at the toll.",
    "importance_raw": 0.7,
    "typology": "observed",
    "typology_confidence": 0.9,
}
OBSERVATION = "Mara crossed the ford at dawn with a shattered lantern"


def _reset_warn_once() -> None:
    """The warn-once register is process-global; a scenario that counts
    warnings clears it first so an earlier scenario cannot pre-empt it."""
    providers_module._WARNED_ONCE.clear()


def _openai_settings(**fields):
    return replace(load_settings(dict(LOCAL_ENV)), **fields)


def _openai_backend(routes, recorder=None):
    return build_chat_backend(
        _openai_settings(), http_client=mock_client(routes, recorder)
    )


def _drain(gen):
    """Drive a sync prose generator to (chunks, StopIteration.value)."""
    chunks = []
    while True:
        try:
            chunks.append(next(gen))
        except StopIteration as stop:
            return chunks, stop.value


def test_openai_write_call_request_shape():
    """Path, bearer placeholder, system + user messages, max_tokens 1024,
    json_object response_format, no stream/thinking/sampling; the
    round-trip lands every WriteCallResult field with the fixture usage."""
    rec = Recorder()
    backend = _openai_backend(
        {"/chat/completions": openai_chat_json(json.dumps(WRITE_PAYLOAD))}, rec
    )
    settings = _openai_settings()
    provider = RealWriteProvider(settings, backend)
    result = provider.render_and_score(
        observation_text=OBSERVATION,
        diagnosticity_goal="what threatens the ford",
        declared_typology=None,
    )
    assert result.rendered_content == WRITE_PAYLOAD["rendered_content"]
    assert result.importance_raw == 0.7
    assert result.typology == "observed" and result.typology_confidence == 0.9
    assert (result.input_tokens, result.output_tokens) == (7, 3)
    req = rec.last
    assert req.method == "POST" and req.path == "/v1/chat/completions"
    assert req.url.startswith("http://127.0.0.1:11434/v1/")
    assert req.headers["authorization"] == f"Bearer {PLACEHOLDER_API_KEY}"
    body = req.body
    assert body["model"] == "model-w"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert OBSERVATION in body["messages"][1]["content"]
    assert body["max_tokens"] == 1024
    assert body["response_format"] == {"type": "json_object"}
    for absent in ("stream", "stream_options", "thinking", "temperature", "top_p"):
        assert absent not in body
    # a declared typology drops the typology clause and the typology fields
    declared = provider.render_and_score(
        observation_text=OBSERVATION,
        diagnosticity_goal="g",
        declared_typology="told",
    )
    assert declared.typology is None and declared.typology_confidence is None


def test_openai_every_json_role_round_trips(caplog):
    """Escalation, reconstruction, judge, reflect, consolidate, compile each
    round-trip their dataclass through the openai backend with the per-role
    max_tokens; the judge's Anthropic-only adaptive thinking is dropped with
    exactly one warning and never reaches the wire."""
    _reset_warn_once()
    settings = _openai_settings(model_judge="model-j", model_reflection="model-f")
    settings = replace(settings, model_compiler="model-c")
    rec = Recorder()
    canned: dict[str, str] = {}
    backend = build_chat_backend(
        settings,
        http_client=mock_client(
            {"/chat/completions": lambda e: openai_chat_json(canned["text"])}, rec
        ),
    )
    component_id = str(uuid4())
    canned["text"] = json.dumps(
        {
            "spans": [
                {"text": "crossed the ford", "component": "Mara", "category": "place"},
                {"text": "not in the text", "component": None, "category": None},
            ],
            "new_components": [
                {"canonical": "the toll", "aliases": ["toll"], "category": "place"}
            ],
        }
    )
    esc = RealEscalationProvider(settings, backend).extract_gist(
        observation_text=OBSERVATION,
        known_components=[
            {
                "canonical": "Mara",
                "aliases": ["the blacksmith"],
                "category": "person",
                "component_id": component_id,
            }
        ],
        candidate_spans=[],
        candidate_components=[],
        triggers=["novelty"],
    )
    assert len(esc.spans) == 1  # the unlocatable substring dropped
    assert esc.spans[0].start_char == OBSERVATION.find("crossed the ford")
    assert esc.spans[0].matched_component_id == component_id
    assert esc.new_components[0].canonical == "the toll"
    assert rec.last.body["max_tokens"] == 1024 and rec.last.body["model"] == "model-e"

    memory_id = str(uuid4())
    canned["text"] = json.dumps({memory_id: "[canned] a retelling", "other": 3})
    items = [
        ReconstructionItem(
            memory_id=memory_id, gist="g", thinned_detail="d", current_telling="t"
        )
    ] * 3
    recon = RealReconstructionProvider(settings, backend).reconstruct(
        system_prompt="s", user_content="u", items=items
    )
    assert recon.retellings == {memory_id: "[canned] a retelling"}
    assert rec.last.body["max_tokens"] == 3072 and rec.last.body["model"] == "model-r"

    with caplog.at_level(logging.WARNING, logger="app.providers"):
        canned["text"] = json.dumps({"verdict": True, "score": 1})
        judge = RealJudgeProvider(settings, backend)
        first = judge.judge(system_prompt="s", user_content="u", category="abstention")
        second = judge.judge(system_prompt="s", user_content="u", category="abstention")
    assert first.payload == {"verdict": True, "score": 1} == second.payload
    assert rec.last.body["max_tokens"] == settings.judge_max_tokens
    assert "thinking" not in rec.last.body and "reasoning_effort" not in rec.last.body
    dropped = [r for r in caplog.records if "no thinking parameter" in r.getMessage()]
    assert len(dropped) == 1

    canned["text"] = json.dumps(
        {
            "reflections": [
                {
                    "content": "[canned] a belief",
                    "identity_relevant": True,
                    "source_memory_ids": [memory_id],
                }
            ]
        }
    )
    reflection = RealReflectionProvider(settings, backend)
    reflected = reflection.reflect(system_prompt="s", user_content="u", items=[])
    assert len(reflected.conclusions) == 1
    assert reflected.conclusions[0].source_memory_ids == [memory_id]
    assert reflected.conclusions[0].identity_relevant is True
    assert rec.last.body["max_tokens"] == 2048 and rec.last.body["model"] == "model-f"
    canned["text"] = json.dumps({"content": "[canned] one consolidated belief"})
    consolidated = reflection.consolidate(system_prompt="s", user_content="u")
    assert consolidated.content == "[canned] one consolidated belief"
    assert rec.last.body["max_tokens"] == 1024

    canned["text"] = json.dumps(
        {
            "multipliers": {"relevance": 1.25, "recency": 0.75, "importance": 1.0},
            "passthrough": {"mood": "wary"},
        }
    )
    compiled = RealCompilerProvider(settings, backend).compile(
        system_prompt="s",
        user_content="u",
        item=CompilerItem(
            reflection_id=str(uuid4()),
            content="c",
            identity_relevant=True,
            scene_type="default",
        ),
    )
    assert (compiled.w_relevance, compiled.w_recency, compiled.w_importance) == (
        1.25,
        0.75,
        1.0,
    )
    assert compiled.passthrough == {"mood": "wary"}
    assert rec.last.body["max_tokens"] == 512 and rec.last.body["model"] == "model-c"
    # every structured call asked for JSON mode; tokens rode every result
    assert all(
        r.body["response_format"] == {"type": "json_object"} for r in rec.requests
    )
    assert (compiled.input_tokens, compiled.output_tokens) == (7, 3)


def test_openai_usage_absent_is_zero_and_warns_once(caplog):
    """A server that reports no usage yields 0/0 tokens on every call and
    exactly one warning per process — honest about the gap, never
    fabricated, never per-call noise."""
    _reset_warn_once()
    backend = _openai_backend(
        {"/chat/completions": openai_chat_json(json.dumps(WRITE_PAYLOAD), usage=None)}
    )
    provider = RealWriteProvider(_openai_settings(), backend)
    with caplog.at_level(logging.WARNING, logger="app.providers"):
        first = provider.render_and_score(
            observation_text="a", diagnosticity_goal="g", declared_typology=None
        )
        second = provider.render_and_score(
            observation_text="b", diagnosticity_goal="g", declared_typology=None
        )
    assert (first.input_tokens, first.output_tokens) == (0, 0)
    assert (second.input_tokens, second.output_tokens) == (0, 0)
    warned = [r for r in caplog.records if "reported no usage" in r.getMessage()]
    assert len(warned) == 1


@pytest.mark.parametrize(
    "response",
    [
        openai_chat_json(None),
        openai_chat_json(""),
        openai_chat_json("not json at all"),
        openai_chat_json("{}", choices=False),
    ],
    ids=["null-content", "empty-content", "not-json", "no-choices"],
)
def test_openai_empty_or_malformed_content_is_malformed_output(response):
    """Null content, empty content, non-JSON, and an empty choices list all
    normalize to the role's MalformedOutputError, carrying the spend."""
    backend = _openai_backend({"/chat/completions": response})
    provider = RealWriteProvider(_openai_settings(), backend)
    with pytest.raises(MalformedOutputError) as caught:
        provider.render_and_score(
            observation_text="a", diagnosticity_goal="g", declared_typology=None
        )
    assert (caught.value.input_tokens, caught.value.output_tokens) == (7, 3)


@pytest.mark.parametrize("status", [400, 401, 404])
def test_openai_http_error_is_provider_call_error(status):
    """4xx from the server is the role's pinned ProviderCallError (no SDK
    retry sleeps on these statuses)."""
    backend = _openai_backend({"/chat/completions": http_error(status)})
    with pytest.raises(ProviderCallError, match="write call failed"):
        RealWriteProvider(_openai_settings(), backend).render_and_score(
            observation_text="a", diagnosticity_goal="g", declared_typology=None
        )


def test_openai_small_model_hardening_survives():
    """The ruled failure mode made structural: an echoed option syntax
    clamps to vocabulary, a non-numeric confidence drops to None, and a
    code-fenced object still parses — on the openai backend too."""
    payload = {
        **WRITE_PAYLOAD,
        "typology": "observed|told",
        "typology_confidence": "high",
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    backend = _openai_backend({"/chat/completions": openai_chat_json(fenced)})
    result = RealWriteProvider(_openai_settings(), backend).render_and_score(
        observation_text="a", diagnosticity_goal="g", declared_typology=None
    )
    assert result.typology == "observed"
    assert result.typology_confidence is None
    assert result.importance_raw == 0.7


def test_openai_streaming_chunks_and_final_usage():
    """The dialogue stream yields the fixture chunks byte-identically, takes
    its usage from the trailing chunk, measures first-token latency, and asks
    for stream_options.include_usage without a response_format."""
    rec = Recorder()
    fixture = ["The ford ", "is quiet ", "tonight."]
    backend = _openai_backend({"/chat/completions": openai_chat_sse(fixture)}, rec)
    provider = RealDialogueProvider(_openai_settings(), backend)
    chunks, result = _drain(
        provider.stream_prose(system_prompt="s", utterance="who crossed?")
    )
    assert "".join(chunks) == "".join(fixture)
    assert (result.input_tokens, result.output_tokens) == (7, 3)
    assert result.first_token_ms >= 0.0
    body = rec.last.body
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["max_tokens"] == 1024 and body["model"] == "model-d"
    assert "response_format" not in body and "thinking" not in body


def test_openai_stream_error_contracts():
    """An HTTP error raises BEFORE the first chunk (the fallback-line
    contract); a mid-stream error event raises AFTER the chunks already
    yielded (the keep-partial contract)."""
    settings = _openai_settings()
    pre = RealDialogueProvider(
        settings, _openai_backend({"/chat/completions": http_error(400)})
    )
    gen = pre.stream_prose(system_prompt="s", utterance="u")
    with pytest.raises(ProviderCallError, match="prose call failed"):
        next(gen)
    mid = RealDialogueProvider(
        settings,
        _openai_backend(
            {"/chat/completions": openai_chat_sse(["a ", "b ", "c"], error_after=2)}
        ),
    )
    gen = mid.stream_prose(system_prompt="s", utterance="u")
    received = [next(gen), next(gen)]
    with pytest.raises(ProviderCallError, match="prose call failed"):
        next(gen)
    assert received == ["a ", "b "]


# ---------------------------------------------------------------------------
# The Anthropic backend: today's request bytes, pinned
# ---------------------------------------------------------------------------


def test_anthropic_backend_request_shape_pinned():
    """The seam move must not change a request byte: the write call is
    exactly {model, max_tokens, system, messages:[user]} on /v1/messages with
    the x-api-key header and NO response_format; the judge adds
    thinking={"type": "adaptive"} and nothing else."""
    rec = Recorder()
    canned: dict[str, str] = {"text": json.dumps(WRITE_PAYLOAD)}
    settings = replace(load_settings(dict(REAL_ENV)), model_judge="model-j")
    backend = build_chat_backend(
        settings,
        http_client=mock_client(
            {"/v1/messages": lambda e: anthropic_message(canned["text"])}, rec
        ),
    )
    assert isinstance(backend, AnthropicChatBackend)
    result = RealWriteProvider(settings, backend).render_and_score(
        observation_text=OBSERVATION,
        diagnosticity_goal="g",
        declared_typology=None,
    )
    assert result.rendered_content == WRITE_PAYLOAD["rendered_content"]
    assert (result.input_tokens, result.output_tokens) == (7, 3)
    req = rec.last
    assert req.path == "/v1/messages"
    assert req.url.startswith("https://api.anthropic.com/")
    assert req.headers["x-api-key"] == "k1"
    assert set(req.body) == {"model", "max_tokens", "system", "messages"}
    assert req.body["model"] == "model-w" and req.body["max_tokens"] == 1024
    assert req.body["messages"] == [
        {"role": "user", "content": req.body["messages"][0]["content"]}
    ]
    assert OBSERVATION in req.body["messages"][0]["content"]

    canned["text"] = json.dumps({"verdict": False})
    RealJudgeProvider(settings, backend).judge(
        system_prompt="s", user_content="u", category="abstention"
    )
    assert set(rec.last.body) == {
        "model",
        "max_tokens",
        "system",
        "messages",
        "thinking",
    }
    assert rec.last.body["thinking"] == {"type": "adaptive"}
    assert rec.last.body["max_tokens"] == settings.judge_max_tokens


def test_anthropic_streaming_fixture():
    """The six-event Messages stream round-trips through the seam: chunks
    byte-identical, input tokens from message_start, output tokens from
    message_delta; the dialogue knob shapes the thinking key exactly."""
    rec = Recorder()
    fixture = ["The ford ", "is quiet."]
    base = load_settings(dict(REAL_ENV))
    for knob, expected in (("", None), ("disabled", {"type": "disabled"})):
        settings = replace(base, dialogue_thinking=knob)
        backend = build_chat_backend(
            settings,
            http_client=mock_client(
                {"/v1/messages": lambda e: anthropic_message_sse(fixture)}, rec
            ),
        )
        chunks, result = _drain(
            RealDialogueProvider(settings, backend).stream_prose(
                system_prompt="s", utterance="u"
            )
        )
        assert "".join(chunks) == "".join(fixture)
        assert (result.input_tokens, result.output_tokens) == (7, 3)
        body = rec.last.body
        assert body["stream"] is True and body["max_tokens"] == 1024
        assert body.get("thinking") == expected
        assert "response_format" not in body


# ---------------------------------------------------------------------------
# The embedding path: width fit (pad / pass / refuse), tokens, client selection
# ---------------------------------------------------------------------------


def _vector(width: int, seed: int = 1) -> list[float]:
    # multiples of 1/256 survive the float32 round-trip exactly
    return [((i * seed) % 17) / 256.0 for i in range(width)]


def test_embedding_width_fit_and_tokens(caplog):
    """Exactly 1536 passes; 768 is zero-padded to 1536 (the original prefix
    intact, exactly one warning); 2560 is refused loudly naming the model,
    the width, and the lock; absent usage counts 0 with one warning; the
    request carries the model knob, dimensions=1536, and base64."""
    _reset_warn_once()
    rec = Recorder()
    canned: dict[str, object] = {}
    settings = _openai_settings()
    provider = RealEmbeddingProvider(
        settings,
        http_client=mock_client({"/embeddings": lambda e: canned["response"]}, rec),
    )
    exact = _vector(EMBEDDING_DIM)
    canned["response"] = openai_embeddings([exact], usage=11)
    result = provider.embed(["one"])
    assert result.vectors[0] == exact and result.tokens == 11
    body = rec.last.body
    assert body["model"] == "nomic-embed-text"
    assert body["dimensions"] == EMBEDDING_DIM
    assert body["encoding_format"] == "base64"
    assert body["input"] == ["one"]

    narrow = _vector(768, seed=3)
    canned["response"] = openai_embeddings([narrow, narrow])
    with caplog.at_level(logging.WARNING, logger="app.providers"):
        padded = provider.embed(["a", "b"])
        provider.embed(["c", "d"])
    for vec in padded.vectors:
        assert len(vec) == EMBEDDING_DIM
        assert vec[:768] == narrow and vec[768:] == [0.0] * (EMBEDDING_DIM - 768)
    pads = [r for r in caplog.records if "zero-padded" in r.getMessage()]
    assert len(pads) == 1

    canned["response"] = openai_embeddings([_vector(2560)])
    with pytest.raises(ProviderCallError) as refused:
        provider.embed(["wide"])
    message = str(refused.value)
    assert "nomic-embed-text" in message and "2560" in message and "1536" in message

    caplog.clear()
    canned["response"] = openai_embeddings([exact], usage=None)
    with caplog.at_level(logging.WARNING, logger="app.providers"):
        assert provider.embed(["x"]).tokens == 0
        assert provider.embed(["y"]).tokens == 0
    absent = [r for r in caplog.records if "reported no usage" in r.getMessage()]
    assert len(absent) == 1

    # a server that ignores encoding_format and returns float lists still lands
    canned["response"] = openai_embeddings([exact], as_base64=False)
    assert provider.embed(["z"]).vectors[0] == exact


def test_embedding_client_selection():
    """Hosted: OPENAI_API_KEY as the bearer on api.openai.com; a base URL
    without a key: the placeholder; a base URL with its own key: that key.
    Fixture strings only — nothing here is a real secret."""
    exact = _vector(EMBEDDING_DIM)
    cases = [
        (
            load_settings(dict(REAL_ENV)),
            "https://api.openai.com/v1/embeddings",
            "Bearer k2",
            EMBEDDING_MODEL_DEFAULT,
        ),
        (
            _openai_settings(),
            "http://127.0.0.1:11434/v1/embeddings",
            f"Bearer {PLACEHOLDER_API_KEY}",
            "nomic-embed-text",
        ),
        (
            _openai_settings(embedding_api_key="sk-embed"),
            "http://127.0.0.1:11434/v1/embeddings",
            "Bearer sk-embed",
            "nomic-embed-text",
        ),
    ]
    for settings, url, bearer, model in cases:
        rec = Recorder()
        provider = RealEmbeddingProvider(
            settings,
            http_client=mock_client({"/embeddings": openai_embeddings([exact])}, rec),
        )
        provider.embed(["t"])
        assert rec.last.url == url
        assert rec.last.headers["authorization"] == bearer
        assert rec.last.body["model"] == model


# ---------------------------------------------------------------------------
# Offline wiring of the bundle + the lazy factories on both backends
# ---------------------------------------------------------------------------


def test_build_providers_wires_backends_offline():
    """Real-mode construction opens no socket on either backend: the five
    bundle roles share ONE backend object; the judge-shaped factories build
    Real* classes on the openai backend without an Anthropic key; fake mode
    ignores the selector entirely."""
    local = _openai_settings(
        model_judge="model-j", model_reflection="model-f", model_compiler="model-c"
    )
    bundle = build_providers(local)
    assert isinstance(bundle.write._backend, OpenAIChatBackend)
    assert (
        bundle.write._backend
        is bundle.escalation._backend
        is bundle.dialogue._backend
        is bundle.reconstruction._backend
    )
    assert isinstance(bundle.embedding, RealEmbeddingProvider)
    assert isinstance(build_judge_provider(local), RealJudgeProvider)
    assert isinstance(build_reflection_provider(local), RealReflectionProvider)
    assert isinstance(build_compiler_provider(local), RealCompilerProvider)
    assert local.anthropic_api_key == ""

    hosted = build_providers(load_settings(dict(REAL_ENV)))
    assert isinstance(hosted.write._backend, AnthropicChatBackend)
    assert hosted.write._backend is hosted.dialogue._backend

    fake = build_providers(replace(local, provider_mode="fake"))
    assert isinstance(fake.write, FakeWriteProvider)
