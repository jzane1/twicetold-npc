"""Offline setup contracts: validation, embedding identity, diagnostics and probes."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from unittest.mock import Mock

import httpx
import psycopg
import pytest
from provider_transport import openai_chat_json, openai_embeddings
from pydantic import ValidationError

from app import doctor, providers
from app.agent_config import validate_agent_config
from app.config import ConfigError, Settings, load_env, load_settings
from app.embedding_space import binding_status, embedding_configuration
from app.schemas import CreateAgentRequest


@pytest.mark.parametrize(
    "config",
    [
        {"retrieval_top_kk": 3},
        {"decay_classes": {"episodic": 0}},
        {"decay_classes": {"episodic": -1}},
        {"decay_classes": {"episodic": "86400"}},
        {"decay_classes": {"episodic": float("inf")}},
        {"decay_classes": []},
        {"decay_class_default": "missing"},
        {"tau_fallback_seconds": 0},
        {"retrieval_top_k": 0},
        {"retrieval_top_k": 1.5},
        {"retrieval_top_k": True},
        {"retrieval_top_k": "8"},
        {"reconstruction_band_quantum": 0},
        {"reconstruction_band_quantum": 2},
        {"context_time_scale_seconds": 0},
        {"reflection_pressure_norm": 0},
        {"importance_neutral": 2},
        {"decay_k_importance": -1},
        {"gate_enabled": 2},
        {"weight_relevance": float("nan")},
        {"weight_recency": 5},
        {"gate_novelty_threshold": 3},
        {"deferred_poll_seconds": 1},
        {"scene_types": "tavern"},
        {"scene_types": ["tavern", "tavern"]},
        {"text_search_config": ""},
        {"typology_default": "typo"},
    ],
)
def test_agent_config_rejected_at_request_boundary(config):
    with pytest.raises(ValidationError):
        CreateAgentRequest(name="test", config=config)


def test_valid_agent_config_stays_sparse_and_preserves_zero_switches():
    config = {
        "decay_classes": {"episodic": 86400},
        "decay_class_default": "episodic",
        "gate_enabled": 0.0,
        "reconstruction_theta": 0.0,
        "lexical_fetch_k": 0,
        "weight_recency": 0,
        "retrieval_top_k": None,
        "scene_types": ["tavern"],
        "typology_default": "observed",
        "dialogue_fallback_line": "...",
    }
    assert CreateAgentRequest(name="test", config=config).config == config
    assert validate_agent_config(None) is None
    assert validate_agent_config({}) == {}


def test_checked_in_corpora_use_valid_agent_configuration():
    from app.config import REPO_ROOT

    for path in (REPO_ROOT / "data" / "eval" / "corpora").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                agent = json.loads(line).get("agent", {})
                validate_agent_config(agent.get("config"))


def test_documented_ollama_settings_enable_real_mode_from_template():
    from app.config import REPO_ROOT

    def env_block(text):
        return dict(
            line.split("=", 1)
            for line in text.splitlines()
            if "=" in line and not line.startswith("#")
        )

    env = env_block((REPO_ROOT / ".env.example").read_text())
    assert load_settings(env).provider_mode == "fake"
    setup = (REPO_ROOT / "docs" / "SETUP.md").read_text(encoding="utf-8")
    blocks = re.findall(
        r"^```[^\n]*\n(.*?)^```[ \t]*$", setup, re.DOTALL | re.MULTILINE
    )
    recipe = next(
        block for block in blocks if "TWICETOLD_MODEL_BACKEND=openai" in block
    )
    env.update(env_block(recipe))
    settings = load_settings(env)
    assert settings.provider_mode == "real"
    assert settings.model_backend == "openai"
    assert settings.model_write == settings.model_dialogue
    for key in ("TWICETOLD_MODEL_BASE_URL", "TWICETOLD_EMBEDDING_BASE_URL"):
        env[key] = "http://host.docker.internal:11434/v1"
    assert load_settings(env).embedding_base_url == env["TWICETOLD_EMBEDDING_BASE_URL"]


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "http://",
        "http://host:bad",
        "https://user:secret@host/v1",
        "https://host/v1?key=secret",
        "https://host/v1#secret",
        "http://host:0/v1",
    ],
)
def test_invalid_provider_urls_do_not_echo_credentials(url):
    with pytest.raises(ConfigError) as error:
        load_settings({"DATABASE_URI": "unused", "TWICETOLD_EMBEDDING_BASE_URL": url})
    assert "secret" not in str(error.value)
    assert "TWICETOLD_EMBEDDING_BASE_URL" in str(error.value)


@pytest.mark.parametrize("value", ["NaN", "inf", "-1"])
def test_prices_must_be_finite_and_nonnegative(value):
    with pytest.raises(ConfigError):
        load_settings({"DATABASE_URI": "unused", "TWICETOLD_PRICE_EMBEDDING": value})


def test_env_overrides_include_credentials_missing_from_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("DATABASE_URI=unused\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-a")
    monkeypatch.setenv("OPENAI_API_KEY", "key-o")
    env = load_env(path)
    assert env["ANTHROPIC_API_KEY"] == "key-a"
    assert env["OPENAI_API_KEY"] == "key-o"


def test_embedding_identity_ignores_keys_and_chat_models_but_not_space():
    settings = Settings(database_uri="unused", provider_mode="real")
    identity = embedding_configuration(settings)
    assert identity == embedding_configuration(
        replace(settings, openai_api_key="secret", model_dialogue="different")
    )
    assert identity == embedding_configuration(
        replace(settings, embedding_base_url="https://API.OPENAI.COM:443/v1/")
    )
    for change in (
        {"provider_mode": "fake"},
        {"embedding_model": "different"},
        {"embedding_base_url": "http://localhost:11434/v1"},
    ):
        with pytest.raises(ConfigError):
            binding_status(
                identity, embedding_configuration(replace(settings, **change)), True
            )
    assert "secret" not in json.dumps(identity)
    assert binding_status(None, identity, False) == "unbound"
    assert binding_status(None, identity, True) == "legacy"


def test_fake_embedding_identity_ignores_inactive_remote_settings():
    settings = Settings(database_uri="unused")
    assert embedding_configuration(settings) == embedding_configuration(
        replace(
            settings,
            embedding_model="unused",
            embedding_base_url="https://unused.test/v1",
        )
    )


def test_doctor_default_has_no_provider_calls_or_adoption(monkeypatch):
    database = Mock(return_value=[doctor.Check("database", "pass", "ready")])
    probe = Mock(side_effect=AssertionError("must not call providers"))
    monkeypatch.setattr(doctor, "check_database", database)
    monkeypatch.setattr(doctor, "probe_providers", probe)
    results = doctor.diagnose(Settings(database_uri="unused"))
    database.assert_called_once()
    assert database.call_args.kwargs["adopt_existing"] is False
    assert not probe.called
    assert results[-1].status == "skip"


def test_doctor_does_not_spend_on_providers_when_database_fails(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "check_database",
        lambda *a, **k: [doctor.Check("database", "fail", "unavailable")],
    )
    probe = Mock(side_effect=AssertionError("must not call providers"))
    monkeypatch.setattr(doctor, "probe_providers", probe)
    doctor.diagnose(Settings(database_uri="unused"), probe=True)
    assert not probe.called


def test_doctor_database_failure_redacts_driver_details(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "inspect_setup_database",
        Mock(side_effect=psycopg.OperationalError("password=secret")),
    )
    checks = doctor.check_database(Settings(database_uri="password=secret"))
    assert checks[0].status == "fail"
    assert "secret" not in repr(checks)


def test_doctor_json_exit_status(monkeypatch, capsys):
    monkeypatch.setattr(
        doctor, "load_settings", lambda: Settings(database_uri="secret")
    )
    monkeypatch.setattr(
        doctor,
        "diagnose",
        lambda *a, **k: [doctor.Check("database", "fail", "unavailable")],
    )
    assert doctor.main(["--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["checks"][0]["name"] == "database"
    monkeypatch.setattr(
        doctor, "diagnose", lambda *a, **k: [doctor.Check("database", "pass", "ready")]
    )
    assert doctor.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_live_probe_uses_real_transports_with_bounded_no_retry_requests(monkeypatch):
    settings = Settings(
        database_uri="unused",
        provider_mode="real",
        model_backend="openai",
        model_base_url="https://models.test/v1",
        embedding_base_url="https://embeddings.test/v1",
        model_write="shared",
        model_dialogue="shared",
        model_reconstruction="other",
    )
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        assert request.extensions["timeout"]["read"] == 3
        if request.url.path.endswith("/embeddings"):
            return openai_embeddings([[1.0, 0.0]])
        return openai_chat_json('{"ok":true}')

    original_chat = providers.build_chat_backend
    original_embed = providers.RealEmbeddingProvider
    clients = []

    def client():
        value = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(value)
        return value

    def chat(s, **kwargs):
        assert kwargs["max_retries"] == 0
        return original_chat(s, http_client=client(), **kwargs)

    def embed(s, **kwargs):
        assert kwargs["max_retries"] == 0
        return original_embed(s, http_client=client(), **kwargs)

    monkeypatch.setattr(providers, "build_chat_backend", chat)
    monkeypatch.setattr(providers, "RealEmbeddingProvider", embed)
    checks = doctor.probe_providers(settings, timeout=3)
    assert all(check.status == "pass" for check in checks)
    assert len(calls) == 3  # two distinct chat models plus one embedding call
    assert all(c.is_closed for c in clients)


def test_provider_probe_failure_suppresses_body_and_does_not_retry(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500, json={"error": {"message": "password=secret"}})

    original_chat = providers.build_chat_backend
    original_embed = providers.RealEmbeddingProvider
    monkeypatch.setattr(
        providers,
        "build_chat_backend",
        lambda s, **kw: original_chat(
            s, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw
        ),
    )
    monkeypatch.setattr(
        providers,
        "RealEmbeddingProvider",
        lambda s, **kw: original_embed(
            s, http_client=httpx.Client(transport=httpx.MockTransport(handler)), **kw
        ),
    )
    settings = Settings(
        database_uri="unused",
        provider_mode="real",
        model_backend="openai",
        model_base_url="https://models.test/v1",
        embedding_base_url="https://models.test/v1",
        model_write="same",
        model_dialogue="same",
        model_reconstruction="same",
    )
    checks = doctor.probe_providers(settings)
    assert len(calls) == 2
    assert all(c.status == "fail" for c in checks)
    assert "secret" not in repr(checks)


@pytest.mark.parametrize(
    "vector", [[], [0.0, 0.0], [float("nan"), 1], [float("inf"), 1]]
)
def test_embedding_probe_rejects_unusable_vectors(vector):
    embedder = providers.RealEmbeddingProvider(
        Settings(database_uri="unused", openai_api_key="test"),
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _: openai_embeddings([vector]))
        ),
    )
    try:
        with pytest.raises(
            providers.ProviderCallError, match="nonempty, finite, nonzero"
        ):
            embedder.embed(["probe"])
    finally:
        embedder.close()
