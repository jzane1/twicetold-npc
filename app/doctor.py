"""Setup diagnostics: python -m app.doctor [--probe-providers].

Default checks are read-only and make no model calls. Explicit legacy adoption
only records a missing embedding binding; it never changes vectors or a binding.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

import psycopg

from app.config import EMBEDDING_DIM, REPO_ROOT, ConfigError, Settings, load_settings
from app.db import inspect_setup_database
from app.embedding_space import EmbeddingSpaceError


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def check_database(
    settings: Settings, *, timeout: int = 10, adopt_existing: bool = False
) -> list[Check]:
    """Check schema and embedding identity without invoking NLP or providers."""
    try:
        expected = {p.name for p in (REPO_ROOT / "db" / "migrations").glob("*.sql")}
        status = inspect_setup_database(
            settings, expected, timeout=timeout, adopt_existing=adopt_existing
        )
        detail = {
            "matched": "Stored embedding configuration matches.",
            "unbound": "No stored vectors or binding; first runtime startup will bind this configuration.",
            "adopted": "Recorded the attested embedding configuration; no vectors changed.",
        }[status]
        return [
            Check("database", "pass", "Connected; pgvector and migrations are ready."),
            Check("embedding_space", "pass", detail),
        ]
    except EmbeddingSpaceError as exc:
        return [Check("embedding_space", "fail", str(exc))]
    except ConfigError as exc:
        return [Check("database", "fail", str(exc))]
    except psycopg.Error:
        # Driver exceptions can contain DSNs and server-controlled text.
        return [
            Check(
                "database",
                "fail",
                "Database check failed. Check DATABASE_URI, server availability, permissions and migrations; connection details are suppressed.",
            )
        ]


def _provider_failure(name: str, exc: Exception) -> Check:
    # Never print response bodies, exception strings, request URLs or headers.
    code = getattr(exc, "status_code", None)
    suffix = f" HTTP {code}." if isinstance(code, int) else ""
    return Check(
        name,
        "fail",
        "Provider probe failed."
        + suffix
        + " Check the model name, endpoint, credentials and server logs; response details are suppressed.",
    )


def probe_providers(settings: Settings, *, timeout: int = 10) -> list[Check]:
    from app.providers import (
        FakeEmbeddingProvider,
        RealEmbeddingProvider,
        build_chat_backend,
    )

    if settings.provider_mode == "fake":
        vector = FakeEmbeddingProvider().embed(["twicetold setup probe"]).vectors[0]
        return [
            Check(
                "providers",
                "pass",
                f"Fake providers only: deterministic {len(vector)}-dimension embedding; no remote connectivity tested.",
            )
        ]
    checks = []
    # Each distinct required model is probed once. Optional worker/judge models
    # are intentionally outside the basic setup check.
    roles: dict[str, list[str]] = {}
    for role, model in (
        ("write", settings.model_write),
        ("dialogue", settings.model_dialogue),
        ("reconstruction", settings.model_reconstruction),
    ):
        roles.setdefault(model, []).append(role)
    for model, names in roles.items():
        name = "model:" + ",".join(names)
        backend = None
        try:
            backend = build_chat_backend(settings, timeout=timeout, max_retries=0)
            result = backend.complete(
                model=model,
                system="Return only a JSON object.",
                user='Return {"ok":true}.',
                max_tokens=64,
                json_mode=True,
            )
            if not isinstance(json.loads(result.text), dict):
                raise ValueError("not a JSON object")
            checks.append(
                Check(
                    name,
                    "pass",
                    "Model answered a small JSON request; this checks connectivity, not memory quality.",
                )
            )
        except Exception as exc:
            checks.append(_provider_failure(name, exc))
        finally:
            if backend is not None:
                backend.close()
    embedder = None
    try:
        embedder = RealEmbeddingProvider(settings, timeout=timeout, max_retries=0)
        vectors = embedder.embed(["twicetold setup probe"]).vectors
        if len(vectors) != 1 or len(vectors[0]) != EMBEDDING_DIM:
            raise ValueError("unexpected embedding shape")
        checks.append(
            Check(
                "embedding",
                "pass",
                f"Embedding accepted at {EMBEDDING_DIM} dimensions, including the documented zero-padding fit.",
            )
        )
    except Exception as exc:
        checks.append(_provider_failure("embedding", exc))
    finally:
        if embedder is not None:
            embedder.close()
    return checks


def diagnose(
    settings: Settings,
    *,
    probe: bool = False,
    timeout: int = 10,
    adopt_existing: bool = False,
) -> list[Check]:
    mode = settings.provider_mode
    checks = [
        Check(
            "configuration",
            "pass",
            f"provider_mode={mode}; "
            + (
                "remote model settings are inactive."
                if mode == "fake"
                else f"backend={settings.model_backend}; write={settings.model_write}; dialogue={settings.model_dialogue}; reconstruction={settings.model_reconstruction}; embedding={settings.embedding_model}."
            ),
        )
    ]
    checks.extend(
        check_database(settings, timeout=timeout, adopt_existing=adopt_existing)
    )
    if probe and not any(c.status == "fail" for c in checks):
        checks.extend(probe_providers(settings, timeout=timeout))
    else:
        checks.append(
            Check(
                "providers",
                "skip",
                "No provider calls made. Use --probe-providers after database checks pass; real-mode probes may incur charges.",
            )
        )
    if mode == "real":
        checks.append(
            Check(
                "optional_models",
                "skip",
                "Judge, reflection and compiler models are not probed; configure them before using those features.",
            )
        )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-providers",
        action="store_true",
        help="Make small model requests (real mode may cost money).",
    )
    parser.add_argument(
        "--adopt-existing-embeddings",
        action="store_true",
        help="Attest that existing vectors were produced by the configured embedding setup. Stop all writers first. Never overrides a binding.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Database statement/connect and provider request timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured checks and an overall ok flag.",
    )
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be >= 1")
    try:
        settings = load_settings()
        checks = diagnose(
            settings,
            probe=args.probe_providers,
            timeout=args.timeout,
            adopt_existing=args.adopt_existing_embeddings,
        )
    except (ConfigError, SystemExit) as exc:
        checks = [Check("configuration", "fail", str(exc))]
    ok = not any(c.status == "fail" for c in checks)
    if args.json:
        print(json.dumps({"ok": ok, "checks": [asdict(c) for c in checks]}))
    else:
        for check in checks:
            print(f"{check.status.upper()} {check.name}: {check.detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
