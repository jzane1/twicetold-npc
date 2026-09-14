"""verify_provider_path.py — structural done-when walker for the provider path
(the provider-path build ruled 2026-09-01; its forks ruled 2026-09-02 — the
explicit backend selector, zero-padded embedding widths, Anthropic the
default byte-for-byte; NO migration by ruling; the token-limit-field knob
ruled 2026-09-03, built 2026-09-11 — criterion A9).

Runs the provider-path done-when criteria OFFLINE and KEYLESS: the REAL
provider classes are driven against canned in-process HTTP handlers
(tests\\provider_transport.py — httpx.MockTransport injected as the SDK
clients' `http_client`), so every request shape and response contract is
proven without a socket or a key. Only the served beat (G) and the failure
ladder (H) touch the SCRATCH database (default: the .env DATABASE_URI with
its database name swapped to `twicetold_test`); everything else is pure.

What this walker owns: the config matrix (A), the offline wiring of the
bundle + the lazy factories on both backends (B), the OpenAI-compatible
backend's request shape and round-trip per role (C), streaming + the usage
and error contracts + the small-model hardening (D), the Anthropic backend's
request-shape PINS — today's bytes, so the seam move is provable (E), the
embedding width fit pad / pass / refuse + tokens + client selection (F), a
served dialogue turn over httpx.ASGITransport with mock-backed real
providers (G), and the ruling's named failure mode made structural — a small
model's empty output landing as scoring_failed through the ingest ladder (H).

Persistent-scratch rule (the verify_purge precedent): the agent name carries
a per-run suffix and every DB assertion is scoped to this run's ids (never
a DB-global count). H runs one observe through the write pass, so it pays
the lazy spaCy+fastcoref load once (the verify_write_path precedent).

Prerequisite (PowerShell):
    python db\\migrate.py --database-uri <scratch-uri>
Run:
    python tests\\verify_provider_path.py [--database-uri <scratch-uri>]

The product `twicetold` DB is never touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests\ helpers

from provider_transport import (
    Recorder,
    anthropic_message,
    anthropic_message_sse,
    fake_embedding_route,
    http_error,
    mock_client,
    openai_chat_json,
    openai_chat_sse,
    openai_embeddings,
)
from psycopg.types.json import Jsonb
from scratch_uri import scratch_uri

import app.providers as providers_module
from app import db
from app.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_DEFAULT,
    ENV_DIALOGUE_THINKING,
    ENV_EMBEDDING_API_KEY,
    ENV_EMBEDDING_BASE_URL,
    ENV_MODEL_API_KEY,
    ENV_MODEL_BACKEND,
    ENV_MODEL_BASE_URL,
    ENV_MODEL_TOKEN_LIMIT_FIELD,
    PLACEHOLDER_API_KEY,
    ConfigError,
    load_env,
    load_settings,
)
from app.db import build_pool
from app.providers import (
    AnthropicChatBackend,
    CompilerItem,
    FakeEscalationProvider,
    FakeProseProvider,
    FakeReconstructionProvider,
    FakeWriteProvider,
    MalformedOutputError,
    OpenAIChatBackend,
    ProviderCallError,
    Providers,
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

NOW = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
SEED = "A verification NPC, keeper of the crossing ledger."
RUN = uuid4().hex[:8]  # per-run fixture scoping (persistent-scratch rule)
UNREACHABLE_URI = "postgresql://nobody:nothing@127.0.0.1:1/nowhere"
SIX_ROLES = {
    "TWICETOLD_MODEL_IMPORTANCE": "model-w",
    "TWICETOLD_MODEL_RENDER": "model-w",
    "TWICETOLD_MODEL_TYPOLOGY": "model-w",
    "TWICETOLD_MODEL_ESCALATION": "model-e",
    "TWICETOLD_MODEL_DIALOGUE": "model-d",
    "TWICETOLD_MODEL_RECONSTRUCTION": "model-r",
}
REAL_ENV = {
    "DATABASE_URI": UNREACHABLE_URI,
    "TWICETOLD_PROVIDER_MODE": "real",
    "ANTHROPIC_API_KEY": "k1",
    "OPENAI_API_KEY": "k2",
    **SIX_ROLES,
}
LOCAL_ENV = {
    "DATABASE_URI": UNREACHABLE_URI,
    "TWICETOLD_PROVIDER_MODE": "real",
    ENV_MODEL_BACKEND: "openai",
    ENV_MODEL_BASE_URL: "http://127.0.0.1:11434/v1",
    ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1",
    "TWICETOLD_EMBEDDING_MODEL": "nomic-embed-text",
    **SIX_ROLES,
}
WRITE_PAYLOAD = {
    "rendered_content": "[canned] I watched the lantern shatter at the toll.",
    "importance_raw": 0.7,
    "typology": "observed",
    "typology_confidence": 0.9,
}
OBSERVATION = "Mara crossed the ford at dawn with a shattered lantern"
AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400, "semantic": 604800},
    "decay_class_default": "episodic",
    "reconstruction_theta": 0.0,
    "gate_enabled": 0.0,
}

PASSED: list[str] = []


def ok(criterion: str, detail: str = "") -> None:
    PASSED.append(criterion)
    print(f"  PASS  {criterion}" + (f"  ({detail})" if detail else ""))


def fail(criterion: str, detail: str) -> None:
    print(f"  FAIL  {criterion}: {detail}")
    sys.exit(1)


def check(condition: bool, criterion: str, detail: str = "") -> None:
    if not condition:
        fail(criterion, detail or "condition false")
    ok(criterion, detail)


def raises(exc_type, fn, needle: str = "") -> bool:
    try:
        fn()
    except exc_type as exc:
        return needle in str(exc)
    return False


def scratch_uri_from_env() -> str:
    return scratch_uri(load_env()["DATABASE_URI"], "twicetold_test")


class WarningTap(logging.Handler):
    """Counts app.providers warnings containing a marker (the warn-once
    contract) — the walker's caplog."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    def count(self, marker: str) -> int:
        return sum(1 for m in self.messages if marker in m)


def reset_warn_once() -> None:
    providers_module._WARNED_ONCE.clear()


def drain(gen):
    chunks = []
    while True:
        try:
            chunks.append(next(gen))
        except StopIteration as stop:
            return chunks, stop.value


def vector(width: int, seed: int = 1) -> list[float]:
    return [((i * seed) % 17) / 256.0 for i in range(width)]


def local_settings(**fields):
    return replace(load_settings(dict(LOCAL_ENV)), **fields)


def openai_backend(routes, recorder=None, **fields):
    return build_chat_backend(
        local_settings(**fields), http_client=mock_client(routes, recorder)
    )


# ---------------------------------------------------------------------------
# DB helpers (RUN-scoped; the verify_purge seed shape)
# ---------------------------------------------------------------------------


async def make_agent(pool, tag: str):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO agents (name, seed_identity, rigidity, "
            "diagnosticity_goal, config) "
            "VALUES (%s, %s, 1.0, %s, %s) RETURNING agent_id",
            (
                f"provider-path-walker-{RUN}-{tag}",
                SEED,
                "what threatens the crossing",
                Jsonb(AGENT_CONFIG),
            ),
        )
        agent_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO identity_components (agent_id, canonical, aliases, "
            "category) VALUES (%s, %s, %s, 'person')",
            (agent_id, f"Mara-{RUN}", ["the blacksmith"]),
        )
        return agent_id


async def seed_memory(pool, agent_id, text: str):
    vec = providers_module.FakeEmbeddingProvider().embed([text]).vectors[0]
    plan = db.InsertPlan(
        agent_id=agent_id,
        observation_text=text,
        rendered_content=f"[walker seed] {text}",
        valid_at=NOW,
        importance_raw=0.5,
        scoring_failed=False,
        typology="observed",
        typology_confidence=0.9,
        typology_source="declared",
        provenance="lived",
        pinned=False,
        decay_class="episodic",
        decay_class_unknown=False,
        embedding=vec,
        entities=None,
        spans=[],
        event_time=None,
        location_name=None,
    )
    outcome = await db.insert_observation(pool, plan)
    return outcome.memory_id


async def fetchrow(pool, sql: str, *params):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def section_a_config() -> None:
    print("\n-- A. the config matrix (loud rows, defaults, fake mode, overrides)")
    base = load_settings(dict(REAL_ENV))
    check(
        base.model_backend == "anthropic"
        and base.model_base_url == ""
        and base.model_api_key == ""
        and base.embedding_model == EMBEDDING_MODEL_DEFAULT
        and base.embedding_base_url == ""
        and "k1" not in repr(base),
        "A1 no new var set => anthropic, no URL/key, the locked slate's embedding",
    )
    check(
        raises(
            ConfigError,
            lambda: load_settings({**REAL_ENV, ENV_MODEL_BACKEND: "bedrock"}),
            "'anthropic' or 'openai'",
        )
        and raises(
            ConfigError,
            lambda: load_settings(
                {
                    "DATABASE_URI": UNREACHABLE_URI,
                    "TWICETOLD_PROVIDER_MODE": "fake",
                    ENV_MODEL_BACKEND: "bedrock",
                }
            ),
        ),
        "A2 the selector enum is validated in both modes",
    )
    missing = {k: v for k, v in LOCAL_ENV.items() if k != ENV_MODEL_BASE_URL}
    local = load_settings({**LOCAL_ENV, ENV_MODEL_BASE_URL: "http://host:8000/v1/"})
    check(
        raises(ConfigError, lambda: load_settings(missing), ENV_MODEL_BASE_URL)
        and raises(
            ConfigError,
            lambda: load_settings({**LOCAL_ENV, ENV_MODEL_BASE_URL: "ftp://x/v1"}),
            "http",
        )
        and local.model_base_url == "http://host:8000/v1"
        and local.anthropic_api_key == ""
        and load_settings({**LOCAL_ENV, "ANTHROPIC_API_KEY": "k1"}).model_backend
        == "openai",
        "A3 openai needs an http(s) base URL (slash stripped), never an Anthropic key",
    )
    check(
        raises(
            ConfigError,
            lambda: load_settings({**REAL_ENV, ENV_MODEL_BASE_URL: "http://h/v1"}),
            "is 'anthropic'",
        )
        and raises(
            ConfigError,
            lambda: load_settings({**REAL_ENV, ENV_MODEL_API_KEY: "sk"}),
            "is 'anthropic'",
        ),
        "A4 a base URL or model key under anthropic is a loud misconfiguration",
    )
    check(
        raises(
            ConfigError,
            lambda: load_settings({**LOCAL_ENV, ENV_DIALOGUE_THINKING: "disabled"}),
            "Anthropic request knob",
        )
        and load_settings(
            {**REAL_ENV, ENV_DIALOGUE_THINKING: "disabled"}
        ).dialogue_thinking
        == "disabled",
        "A5 the dialogue-thinking knob is refused under openai, kept under anthropic",
    )
    no_openai_key = {k: v for k, v in REAL_ENV.items() if k != "OPENAI_API_KEY"}
    routed = load_settings({**no_openai_key, ENV_EMBEDDING_BASE_URL: "http://h/v1"})
    check(
        raises(
            ConfigError, lambda: load_settings(no_openai_key), ENV_EMBEDDING_BASE_URL
        )
        and routed.openai_api_key == ""
        and routed.model_backend == "anthropic"
        and raises(
            ConfigError,
            lambda: load_settings({**REAL_ENV, ENV_EMBEDDING_API_KEY: "sk"}),
            ENV_EMBEDDING_API_KEY,
        )
        and raises(
            ConfigError,
            lambda: load_settings({**REAL_ENV, ENV_EMBEDDING_BASE_URL: "h:1"}),
            "http",
        )
        and load_settings(
            {**REAL_ENV, "TWICETOLD_EMBEDDING_MODEL": "text-embedding-3-large"}
        ).embedding_model
        == "text-embedding-3-large",
        "A6 the embedding knobs are independent: base URL lifts OPENAI_API_KEY, "
        "key-without-URL and non-http URL are loud, the model name overrides",
    )
    fake = load_settings(
        {
            "DATABASE_URI": UNREACHABLE_URI,
            "TWICETOLD_PROVIDER_MODE": "fake",
            ENV_MODEL_BACKEND: "openai",
        }
    )
    check(
        fake.provider_mode == "fake" and fake.model_backend == "openai",
        "A7 fake mode loads the openai selector with no URL and no key",
    )
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / ".env"
        env_file.write_text(f"DATABASE_URI={UNREACHABLE_URI}\n", encoding="utf-8")
        overrides = {
            ENV_MODEL_BACKEND: "openai",
            ENV_MODEL_BASE_URL: "http://127.0.0.1:11434/v1",
            ENV_MODEL_API_KEY: "sk-local",
            ENV_MODEL_TOKEN_LIMIT_FIELD: "max_completion_tokens",
            "TWICETOLD_EMBEDDING_MODEL": "nomic-embed-text",
            ENV_EMBEDDING_BASE_URL: "http://127.0.0.1:11434/v1",
            ENV_EMBEDDING_API_KEY: "sk-embed",
        }
        saved = {k: os.environ.get(k) for k in overrides}
        try:
            os.environ.update(overrides)
            values = load_env(env_file)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    check(
        all(values[k] == v for k, v in overrides.items()),
        "A8 all seven new keys ride the process-env override allowlist",
    )
    rec = Recorder()
    flipped = openai_backend(
        {"/chat/completions": openai_chat_json(json.dumps(WRITE_PAYLOAD))},
        rec,
        model_token_limit_field="max_completion_tokens",
    )
    flipped.complete(
        model="model-w", system="s", user="u", max_tokens=64, json_mode=True
    )
    complete_body = rec.last.body
    stream_rec = Recorder()
    streamer = openai_backend(
        {"/chat/completions": openai_chat_sse(["a ", "b"])},
        stream_rec,
        model_token_limit_field="max_completion_tokens",
    )
    chunks, _ = drain(
        streamer.stream(model="model-d", system="s", user="u", max_tokens=64)
    )
    stream_body = stream_rec.last.body
    check(
        load_settings(dict(LOCAL_ENV)).model_token_limit_field == "max_tokens"
        and load_settings(
            {**LOCAL_ENV, ENV_MODEL_TOKEN_LIMIT_FIELD: " MAX_COMPLETION_TOKENS "}
        ).model_token_limit_field
        == "max_completion_tokens"
        and raises(
            ConfigError,
            lambda: load_settings(
                {**LOCAL_ENV, ENV_MODEL_TOKEN_LIMIT_FIELD: "max_output_tokens"}
            ),
            "'max_tokens' or",
        )
        and raises(
            ConfigError,
            lambda: load_settings(
                {**REAL_ENV, ENV_MODEL_TOKEN_LIMIT_FIELD: "max_completion_tokens"}
            ),
            "openai wire knob",
        )
        and load_settings(
            {**REAL_ENV, ENV_MODEL_TOKEN_LIMIT_FIELD: "max_tokens"}
        ).model_token_limit_field
        == "max_tokens"
        and complete_body["max_completion_tokens"] == 64
        and "max_tokens" not in complete_body
        and complete_body["response_format"] == {"type": "json_object"}
        and "".join(chunks) == "a b"
        and stream_body["max_completion_tokens"] == 64
        and "max_tokens" not in stream_body
        and stream_body["stream"] is True,
        "A9 the token-limit-field knob: defaulted/case-folded/enum-loud, "
        "max_completion_tokens refused under anthropic (max_tokens harmless), "
        "the flipped field on BOTH openai call paths with max_tokens absent",
    )


def section_b_wiring() -> None:
    print("\n-- B. offline wiring: the bundle + the lazy factories on both backends")
    local = local_settings(
        model_judge="model-j", model_reflection="model-f", model_compiler="model-c"
    )
    bundle = build_providers(local)
    check(
        isinstance(bundle.write._backend, OpenAIChatBackend)
        and bundle.write._backend
        is bundle.escalation._backend
        is bundle.dialogue._backend
        is bundle.reconstruction._backend
        and isinstance(bundle.embedding, RealEmbeddingProvider),
        "B1 the openai bundle shares ONE backend across its four LLM roles",
    )
    check(
        isinstance(build_judge_provider(local), RealJudgeProvider)
        and isinstance(build_reflection_provider(local), RealReflectionProvider)
        and isinstance(build_compiler_provider(local), RealCompilerProvider)
        and local.anthropic_api_key == "",
        "B2 the judge-shaped factories build Real* classes without an Anthropic key",
    )
    hosted = build_providers(load_settings(dict(REAL_ENV)))
    check(
        isinstance(hosted.write._backend, AnthropicChatBackend)
        and hosted.write._backend is hosted.dialogue._backend,
        "B3 the default bundle is the Anthropic backend, shared",
    )
    fake = build_providers(replace(local, provider_mode="fake"))
    check(
        isinstance(fake.write, FakeWriteProvider), "B4 fake mode ignores the selector"
    )


def section_c_openai_roles() -> None:
    print("\n-- C. the openai backend: request shape + round-trip per role")
    reset_warn_once()
    tap = WarningTap()
    logging.getLogger("app.providers").addHandler(tap)
    try:
        settings = local_settings(
            model_judge="model-j", model_reflection="model-f", model_compiler="model-c"
        )
        rec = Recorder()
        canned: dict[str, str] = {"text": json.dumps(WRITE_PAYLOAD)}
        backend = build_chat_backend(
            settings,
            http_client=mock_client(
                {"/chat/completions": lambda e: openai_chat_json(canned["text"])}, rec
            ),
        )
        write = RealWriteProvider(settings, backend).render_and_score(
            observation_text=OBSERVATION,
            diagnosticity_goal="what threatens the ford",
            declared_typology=None,
        )
        body = rec.last.body
        check(
            write.rendered_content == WRITE_PAYLOAD["rendered_content"]
            and write.importance_raw == 0.7
            and write.typology == "observed"
            and write.typology_confidence == 0.9
            and (write.input_tokens, write.output_tokens) == (7, 3)
            and rec.last.path == "/v1/chat/completions"
            and rec.last.url.startswith("http://127.0.0.1:11434/v1/")
            and rec.last.headers["authorization"] == f"Bearer {PLACEHOLDER_API_KEY}"
            and body["model"] == "model-w"
            and [m["role"] for m in body["messages"]] == ["system", "user"]
            and OBSERVATION in body["messages"][1]["content"]
            and body["max_tokens"] == 1024
            and body["response_format"] == {"type": "json_object"}
            and not any(
                k in body
                for k in ("stream", "stream_options", "thinking", "temperature")
            ),
            "C1 write: path, bearer placeholder, system+user, max_tokens 1024, "
            "json_object, no stream/thinking/sampling; every field round-trips",
        )
        component_id = str(uuid4())
        canned["text"] = json.dumps(
            {
                "spans": [
                    {"text": "crossed the ford", "component": "Mara", "category": "p"},
                    {
                        "text": "nowhere in the text",
                        "component": None,
                        "category": None,
                    },
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
                    "aliases": [],
                    "category": "person",
                    "component_id": component_id,
                }
            ],
            candidate_spans=[],
            candidate_components=[],
            triggers=["novelty"],
        )
        check(
            len(esc.spans) == 1
            and esc.spans[0].start_char == OBSERVATION.find("crossed the ford")
            and esc.spans[0].matched_component_id == component_id
            and esc.new_components[0].canonical == "the toll"
            and rec.last.body["max_tokens"] == 1024
            and rec.last.body["model"] == "model-e",
            "C2 escalation: span offsets + component id, unlocatable dropped, 1024",
        )
        memory_id = str(uuid4())
        canned["text"] = json.dumps({memory_id: "[canned] a retelling", "x": 1})
        items = [
            ReconstructionItem(
                memory_id=memory_id, gist="g", thinned_detail="d", current_telling="t"
            )
        ] * 3
        recon = RealReconstructionProvider(settings, backend).reconstruct(
            system_prompt="s", user_content="u", items=items
        )
        check(
            recon.retellings == {memory_id: "[canned] a retelling"}
            and rec.last.body["max_tokens"] == 3072
            and rec.last.body["model"] == "model-r",
            "C3 reconstruction: per-item salvage, max_tokens scales with the batch",
        )
        canned["text"] = json.dumps({"verdict": True})
        judge = RealJudgeProvider(settings, backend)
        judge.judge(system_prompt="s", user_content="u", category="abstention")
        judge.judge(system_prompt="s", user_content="u", category="abstention")
        check(
            rec.last.body["max_tokens"] == settings.judge_max_tokens
            and "thinking" not in rec.last.body
            and "reasoning_effort" not in rec.last.body
            and tap.count("no thinking parameter") == 1,
            "C4 judge: judge_max_tokens, adaptive thinking dropped off the wire, "
            "warned exactly once",
        )
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
        reflect_tokens = rec.last.body["max_tokens"]
        canned["text"] = json.dumps({"content": "[canned] consolidated"})
        consolidated = reflection.consolidate(system_prompt="s", user_content="u")
        check(
            len(reflected.conclusions) == 1
            and reflected.conclusions[0].source_memory_ids == [memory_id]
            and reflect_tokens == 2048
            and consolidated.content == "[canned] consolidated"
            and rec.last.body["max_tokens"] == 1024
            and rec.last.body["model"] == "model-f",
            "C5 reflect (2048) + consolidate (1024) round-trip",
        )
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
        check(
            (compiled.w_relevance, compiled.w_recency, compiled.w_importance)
            == (1.25, 0.75, 1.0)
            and compiled.passthrough == {"mood": "wary"}
            and rec.last.body["max_tokens"] == 512
            and rec.last.body["model"] == "model-c",
            "C6 compile (512) round-trip",
        )
        check(
            all(
                r.body["response_format"] == {"type": "json_object"}
                for r in rec.requests
            )
            and (compiled.input_tokens, compiled.output_tokens) == (7, 3),
            "C7 every structured request asked for JSON mode; tokens rode every result",
        )
    finally:
        logging.getLogger("app.providers").removeHandler(tap)


def section_d_streaming_and_contracts() -> None:
    print("\n-- D. streaming, usage-absent, error contracts, small-model hardening")
    reset_warn_once()
    tap = WarningTap()
    logging.getLogger("app.providers").addHandler(tap)
    try:
        settings = local_settings()
        rec = Recorder()
        fixture = ["The ford ", "is quiet ", "tonight."]
        backend = openai_backend({"/chat/completions": openai_chat_sse(fixture)}, rec)
        chunks, result = drain(
            RealDialogueProvider(settings, backend).stream_prose(
                system_prompt="s", utterance="who crossed?"
            )
        )
        body = rec.last.body
        check(
            "".join(chunks) == "".join(fixture)
            and (result.input_tokens, result.output_tokens) == (7, 3)
            and result.first_token_ms >= 0.0
            and body["stream"] is True
            and body["stream_options"] == {"include_usage": True}
            and body["max_tokens"] == 1024
            and body["model"] == "model-d"
            and "response_format" not in body
            and "thinking" not in body,
            "D1 stream: chunks byte-identical, usage from the trailing chunk, "
            "include_usage on the wire, no response_format",
        )
        absent = RealWriteProvider(
            settings,
            openai_backend(
                {
                    "/chat/completions": openai_chat_json(
                        json.dumps(WRITE_PAYLOAD), usage=None
                    )
                }
            ),
        )
        first = absent.render_and_score(
            observation_text="a", diagnosticity_goal="g", declared_typology=None
        )
        absent.render_and_score(
            observation_text="b", diagnosticity_goal="g", declared_typology=None
        )
        check(
            (first.input_tokens, first.output_tokens) == (0, 0)
            and tap.count("reported no usage") == 1,
            "D2 usage absent => 0/0 tokens, warned exactly once per process",
        )
        pre = RealDialogueProvider(
            settings, openai_backend({"/chat/completions": http_error(400)})
        ).stream_prose(system_prompt="s", utterance="u")
        check(
            raises(ProviderCallError, lambda: next(pre), "prose call failed"),
            "D3 an HTTP error raises BEFORE the first chunk (the fallback-line contract)",
        )
        mid = RealDialogueProvider(
            settings,
            openai_backend(
                {"/chat/completions": openai_chat_sse(["a ", "b ", "c"], error_after=2)}
            ),
        ).stream_prose(system_prompt="s", utterance="u")
        received = [next(mid), next(mid)]
        check(
            received == ["a ", "b "]
            and raises(ProviderCallError, lambda: next(mid), "prose call failed"),
            "D4 a mid-stream error raises AFTER the chunks already yielded "
            "(the keep-partial contract)",
        )
        outcomes = []
        for response in (
            openai_chat_json(None),
            openai_chat_json(""),
            openai_chat_json("not json"),
            openai_chat_json("{}", choices=False),
        ):
            provider = RealWriteProvider(
                settings, openai_backend({"/chat/completions": response})
            )
            try:
                provider.render_and_score(
                    observation_text="a", diagnosticity_goal="g", declared_typology=None
                )
                outcomes.append(None)
            except MalformedOutputError as exc:
                outcomes.append((exc.input_tokens, exc.output_tokens))
        check(
            outcomes == [(7, 3)] * 4,
            "D5 null / empty / non-JSON content and an empty choices list all raise "
            "MalformedOutputError carrying the spend",
        )
        check(
            all(
                raises(
                    ProviderCallError,
                    lambda s=status: RealWriteProvider(
                        settings, openai_backend({"/chat/completions": http_error(s)})
                    ).render_and_score(
                        observation_text="a",
                        diagnosticity_goal="g",
                        declared_typology=None,
                    ),
                    "write call failed",
                )
                for status in (400, 401, 404)
            ),
            "D6 4xx => the role's pinned ProviderCallError (no retry sleeps)",
        )
        fenced = (
            "```json\n"
            + json.dumps(
                {
                    **WRITE_PAYLOAD,
                    "typology": "observed|told",
                    "typology_confidence": "high",
                }
            )
            + "\n```"
        )
        hardened = RealWriteProvider(
            settings, openai_backend({"/chat/completions": openai_chat_json(fenced)})
        ).render_and_score(
            observation_text="a", diagnosticity_goal="g", declared_typology=None
        )
        check(
            hardened.typology == "observed"
            and hardened.typology_confidence is None
            and hardened.importance_raw == 0.7,
            "D7 the small-model hardening survives on the openai backend "
            "(clamp, salvage, fenced JSON)",
        )
    finally:
        logging.getLogger("app.providers").removeHandler(tap)


def section_e_anthropic_parity() -> None:
    print("\n-- E. the Anthropic backend: today's request bytes, pinned")
    rec = Recorder()
    canned: dict[str, str] = {"text": json.dumps(WRITE_PAYLOAD)}
    settings = replace(load_settings(dict(REAL_ENV)), model_judge="model-j")
    backend = build_chat_backend(
        settings,
        http_client=mock_client(
            {"/v1/messages": lambda e: anthropic_message(canned["text"])}, rec
        ),
    )
    write = RealWriteProvider(settings, backend).render_and_score(
        observation_text=OBSERVATION, diagnosticity_goal="g", declared_typology=None
    )
    body = rec.last.body
    check(
        isinstance(backend, AnthropicChatBackend)
        and write.rendered_content == WRITE_PAYLOAD["rendered_content"]
        and (write.input_tokens, write.output_tokens) == (7, 3)
        and rec.last.path == "/v1/messages"
        and rec.last.url.startswith("https://api.anthropic.com/")
        and rec.last.headers["x-api-key"] == "k1"
        and set(body) == {"model", "max_tokens", "system", "messages"}
        and body["model"] == "model-w"
        and body["max_tokens"] == 1024
        and body["messages"][0]["role"] == "user"
        and OBSERVATION in body["messages"][0]["content"],
        "E1 write: exactly {model, max_tokens, system, messages:[user]} on "
        "/v1/messages with x-api-key — no response_format, no thinking",
    )
    canned["text"] = json.dumps({"verdict": False})
    RealJudgeProvider(settings, backend).judge(
        system_prompt="s", user_content="u", category="abstention"
    )
    check(
        set(rec.last.body) == {"model", "max_tokens", "system", "messages", "thinking"}
        and rec.last.body["thinking"] == {"type": "adaptive"}
        and rec.last.body["max_tokens"] == settings.judge_max_tokens,
        "E2 judge: adds thinking={type: adaptive} and nothing else",
    )
    fixture = ["The ford ", "is quiet."]
    for knob, expected, label in (
        ("", None, "E3 stream with the knob unset: no thinking key, chunks + usage"),
        ("disabled", {"type": "disabled"}, "E4 stream with 'disabled': thinking-off"),
    ):
        streaming = replace(settings, dialogue_thinking=knob)
        stream_backend = build_chat_backend(
            streaming,
            http_client=mock_client(
                {"/v1/messages": lambda e: anthropic_message_sse(fixture)}, rec
            ),
        )
        chunks, result = drain(
            RealDialogueProvider(streaming, stream_backend).stream_prose(
                system_prompt="s", utterance="u"
            )
        )
        body = rec.last.body
        check(
            "".join(chunks) == "".join(fixture)
            and (result.input_tokens, result.output_tokens) == (7, 3)
            and body["stream"] is True
            and body["max_tokens"] == 1024
            and body.get("thinking") == expected
            and "response_format" not in body,
            label,
        )


def section_f_embedding() -> None:
    print(
        "\n-- F. embedding: width fit (pad / pass / refuse), tokens, client selection"
    )
    reset_warn_once()
    tap = WarningTap()
    logging.getLogger("app.providers").addHandler(tap)
    try:
        rec = Recorder()
        canned: dict[str, object] = {}
        provider = RealEmbeddingProvider(
            local_settings(),
            http_client=mock_client({"/embeddings": lambda e: canned["response"]}, rec),
        )
        exact = vector(EMBEDDING_DIM)
        canned["response"] = openai_embeddings([exact], usage=11)
        result = provider.embed(["one"])
        body = rec.last.body
        check(
            result.vectors[0] == exact
            and result.tokens == 11
            and body["model"] == "nomic-embed-text"
            and body["dimensions"] == EMBEDDING_DIM
            and body["encoding_format"] == "base64"
            and body["input"] == ["one"],
            "F1 exactly 1536 passes; the request carries the model knob, "
            "dimensions=1536, base64",
        )
        narrow = vector(768, seed=3)
        canned["response"] = openai_embeddings([narrow, narrow])
        padded = provider.embed(["a", "b"])
        provider.embed(["c", "d"])
        check(
            all(
                len(v) == EMBEDDING_DIM
                and v[:768] == narrow
                and v[768:] == [0.0] * (EMBEDDING_DIM - 768)
                for v in padded.vectors
            )
            and tap.count("zero-padded") == 1,
            "F2 768 is zero-padded to 1536 (prefix intact), warned exactly once",
        )
        canned["response"] = openai_embeddings([vector(2560)])
        check(
            raises(ProviderCallError, lambda: provider.embed(["wide"]), "2560")
            and raises(ProviderCallError, lambda: provider.embed(["wide"]), "1536")
            and raises(
                ProviderCallError, lambda: provider.embed(["wide"]), "nomic-embed-text"
            ),
            "F3 2560 is refused loudly, naming the model, the width, and the lock",
        )
        canned["response"] = openai_embeddings([exact], usage=None)
        tokens = (provider.embed(["x"]).tokens, provider.embed(["y"]).tokens)
        check(
            tokens == (0, 0) and tap.count("reported no usage") == 1,
            "F4 usage absent => tokens 0, warned exactly once",
        )
        canned["response"] = openai_embeddings([exact], as_base64=False)
        check(
            provider.embed(["z"]).vectors[0] == exact,
            "F5 a server that ignores encoding_format (float lists) still lands",
        )
        selections = []
        for settings, url, bearer, model in (
            (
                load_settings(dict(REAL_ENV)),
                "https://api.openai.com/v1/embeddings",
                "Bearer k2",
                EMBEDDING_MODEL_DEFAULT,
            ),
            (
                local_settings(),
                "http://127.0.0.1:11434/v1/embeddings",
                f"Bearer {PLACEHOLDER_API_KEY}",
                "nomic-embed-text",
            ),
            (
                local_settings(embedding_api_key="sk-embed"),
                "http://127.0.0.1:11434/v1/embeddings",
                "Bearer sk-embed",
                "nomic-embed-text",
            ),
        ):
            r = Recorder()
            RealEmbeddingProvider(
                settings,
                http_client=mock_client({"/embeddings": openai_embeddings([exact])}, r),
            ).embed(["t"])
            selections.append(
                r.last.url == url
                and r.last.headers["authorization"] == bearer
                and r.last.body["model"] == model
            )
        check(
            all(selections),
            "F6 client selection: hosted OPENAI_API_KEY @ api.openai.com; base URL "
            "without a key => the placeholder; base URL with a key => that key",
        )
    finally:
        logging.getLogger("app.providers").removeHandler(tap)


async def section_g_served_beat(pool, uri: str) -> None:
    print("\n-- G. a served dialogue turn over mock-backed real providers")
    import httpx

    import app.api as api_module
    from app.dialogue import DialogueService
    from app.retrieval import RetrievalService
    from app.schemas import DialogueTurnRequest

    settings = local_settings(database_uri=uri)
    fixture = ["The ford ", "is quiet ", "tonight."]
    embedding = RealEmbeddingProvider(
        settings, http_client=mock_client({"/embeddings": fake_embedding_route})
    )
    dialogue = RealDialogueProvider(
        settings, openai_backend({"/chat/completions": openai_chat_sse(fixture)})
    )
    providers = Providers(
        write=FakeWriteProvider(),
        escalation=FakeEscalationProvider(),
        embedding=embedding,
        dialogue=dialogue,
        reconstruction=FakeReconstructionProvider(),
    )
    agent = await make_agent(pool, "served")
    seeded = {
        await seed_memory(pool, agent, f"the lantern shattered at the toll {RUN}"),
        await seed_memory(pool, agent, f"a cart crossed at dawn {RUN}"),
    }
    retrieval = RetrievalService(pool, providers, settings)
    api_module.app.state.retrieval = retrieval
    api_module.app.state.dialogue = DialogueService(
        pool, providers, settings, retrieval
    )
    transport = httpx.ASGITransport(app=api_module.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost"
    ) as client:
        response = await client.post(
            "/v1/dialogue/turn",
            json=json.loads(
                DialogueTurnRequest(
                    agent_id=agent, utterance="who crossed at dawn?", as_of=NOW
                ).model_dump_json()
            ),
        )
    body = response.json()
    check(
        response.status_code == 200 and body["content"] == "".join(fixture),
        "G1 the turn streams the mock-backed real dialogue provider's chunks "
        "byte-identically into the result",
        detail=str(response.status_code),
    )
    inst = body["instrumentation"]
    check(
        (inst["sonnet_input_tokens"], inst["sonnet_output_tokens"]) == (7, 3),
        "G2 the turn's token accounting is the backend's reported usage",
    )
    ids = {item["memory_id"] for item in body["items"]}
    check(
        ids == {str(m) for m in seeded}
        and all("score" in item for item in body["items"]),
        "G3 retrieval through the mock-backed real embedding provider serves the "
        "seeded memories with IDs + scores",
        detail=str(len(ids)),
    )


async def section_h_failure_ladder(pool, uri: str) -> None:
    print("\n-- H. the ruling's named failure mode, made structural through ingest")
    from app.ingest import IngestService
    from app.schemas import ObserveEvent

    settings = local_settings(database_uri=uri)
    write = RealWriteProvider(
        settings,
        openai_backend({"/chat/completions": openai_chat_json("{}", choices=False)}),
    )
    providers = Providers(
        write=write,
        escalation=FakeEscalationProvider(),
        embedding=RealEmbeddingProvider(
            settings, http_client=mock_client({"/embeddings": fake_embedding_route})
        ),
        dialogue=FakeProseProvider(),
        reconstruction=FakeReconstructionProvider(),
    )
    agent = await make_agent(pool, "ladder")
    svc = IngestService(pool, providers, settings)
    result = await svc.ingest_observation(
        ObserveEvent(
            agent_id=agent,
            observation_text=f"Mara sharpened my blade at the forge {RUN}.",
            phase_tag="scene.action",
            client_timestamp=NOW,
            provenance="lived",
        )
    )
    row = await fetchrow(
        pool,
        "SELECT scoring_failed, importance_raw FROM memories WHERE memory_id = %s",
        result.memory_id,
    )
    check(
        result.scoring_failed is True and row is not None and row[0] is True,
        "H1 a small model's empty output lands the write with scoring_failed = true "
        "(MalformedOutputError -> the ladder), never a rejected request",
        detail=f"importance_raw={row[1]}",
    )


async def run(uri: str) -> None:
    from urllib.parse import urlsplit

    print(f"walker: scratch DB = {urlsplit(uri).path.lstrip('/')}")
    section_a_config()
    section_b_wiring()
    section_c_openai_roles()
    section_d_streaming_and_contracts()
    section_e_anthropic_parity()
    section_f_embedding()
    pool = build_pool(uri)
    await pool.open()
    try:
        await section_g_served_beat(pool, uri)
        await section_h_failure_ladder(pool, uri)
    finally:
        await pool.close()
    print(f"\nALL CHECKS PASSED ({len(PASSED)} assertions)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-uri",
        default=None,
        help="scratch Postgres URI (default: .env DATABASE_URI with the "
        "database swapped to twicetold_test)",
    )
    args = parser.parse_args()
    uri = args.database_uri or scratch_uri_from_env()
    asyncio.run(run(uri), loop_factory=asyncio.SelectorEventLoop)


if __name__ == "__main__":
    main()
