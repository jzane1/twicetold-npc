"""Provision two village witnesses and preserve real rehearsal evidence.

    python -m app.village_demo provision
    python -m app.village_demo rehearse --takes 3

Each invocation uses a new database; it never resets an existing take. The
manifest contains IDs and public configuration, never database credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app import db
from app.config import REPO_ROOT, Settings, load_settings
from app.demo_loader import load_demo
from app.eval_scenarios import ObserveStep, load_scenarios
from app.providers import build_providers
from app.runtime import open_runtime_pool
from app.retrieval import RetrievalService
from app.schemas import DialogueInitRequest
from app.scratch_db import provision_scratch, scratch_uri
from app.session import SessionRunner

DEMO_ROOT = REPO_ROOT / "data" / "demo"
WITNESSES = ("henry", "joan")
QUESTION = "What do you remember about the fisherman leaving his pouch of gold by the market bench?"


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


async def provision(settings, *, base_url: str) -> tuple[dict, Path, Settings]:
    take_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8]
    )
    database_name = f"twicetold_video_{take_id}"
    uri = await asyncio.to_thread(
        provision_scratch, settings.database_uri, database_name
    )
    settings = replace(settings, database_uri=uri)
    path = DEMO_ROOT / "runs" / take_id / "manifest.json"
    event = json.loads((DEMO_ROOT / "village-event.json").read_text(encoding="utf-8"))
    manifest = {
        "take_id": take_id,
        "database_name": database_name,
        "base_url": base_url,
        "event": event,
        "world_time": event["world_time"],
        "provider_mode": settings.provider_mode,
        "models": {
            role: getattr(settings, f"model_{role}")
            for role in ("write", "reconstruction", "dialogue")
        },
        "witnesses": [],
        "status": "provisioning",
    }
    save_json(path, manifest)
    for stable_id in WITNESSES:
        corpus = REPO_ROOT / "data" / "eval" / "corpora" / f"village-{stable_id}.jsonl"
        scenario = load_scenarios(corpus)[0]
        if (
            not isinstance(scenario.events[-1], ObserveStep)
            or scenario.events[-1].text != event["observation_text"]
        ):
            raise ValueError(
                "village corpus final observation differs from canonical event"
            )
        backstory = scenario.model_copy(update={"events": scenario.events[:-1]})
        backstory.agent.config.update(
            {
                "reflection_worker_enabled": 0.0,
                "compiler_worker_enabled": 0.0,
                "deferred_writes_enabled": 0.0,
            }
        )
        report = await load_demo(settings, backstory, enable_workers=False)
        manifest["witnesses"].append(
            {
                "stable_id": stable_id,
                "name": stable_id.title(),
                "agent_id": str(report["agent_id"]),
                "identity": scenario.agent.seed_identity,
                "backstory": report["memories"],
                "event_status": "not_observed",
                "event_memory_id": None,
            }
        )
        save_json(path, manifest)
        print(f"{take_id}: {stable_id} provisioned with five backstories", flush=True)
    manifest["status"] = "ready"
    save_json(path, manifest)
    return manifest, path, settings


async def rehearse(settings, *, base_url: str) -> Path:
    manifest, path, settings = await provision(settings, base_url=base_url)
    evidence_path = path.with_name("rehearsal.json")
    evidence = {
        "take_id": manifest["take_id"],
        "question": QUESTION,
        "witnesses": [],
        "status": "running",
    }
    save_json(evidence_path, evidence)
    pool = await open_runtime_pool(settings)
    providers = build_providers(settings)
    retrieval = RetrievalService(pool, providers, settings)
    try:
        for witness in manifest["witnesses"]:
            runner = await SessionRunner.create(
                UUID(witness["agent_id"]),
                settings=settings,
                pool=pool,
                providers=providers,
                phase_tag="village-rehearsal",
            )
            record = {"stable_id": witness["stable_id"], "ages": []}
            evidence["witnesses"].append(record)
            try:
                origin = datetime.fromisoformat(manifest["event"]["world_time"])
                runner.as_of = origin
                witness["event_status"] = "in_flight"
                save_json(path, manifest)
                ingest = await runner.observe(manifest["event"]["observation_text"])
                witness["event_memory_id"] = str(ingest.memory_id)
                witness["event_status"] = "observed"
                save_json(path, manifest)
                record["ingest"] = ingest.model_dump(mode="json")
                record["initial_chain"] = await db.fetch_memory_chain(
                    pool, ingest.memory_id
                )
                save_json(evidence_path, evidence)
                for day in (0, 60, 90, 180):
                    runner.as_of = origin + timedelta(days=day)
                    await runner.scene()
                    request = DialogueInitRequest(
                        agent_id=runner.agent_id,
                        query_text=QUESTION,
                        k=3,
                        as_of=runner.as_of,
                        scene_started_at=runner.scene_started_at,
                        identity_version=runner.identity_version,
                    )
                    result = await retrieval.retrieve_dialogue_init(request)
                    repeated = await retrieval.retrieve_dialogue_init(request)
                    chain = await db.fetch_memory_chain(pool, ingest.memory_id)
                    record["ages"].append(
                        {
                            "day": day,
                            "result": result.model_dump(mode="json"),
                            "repeat": repeated.model_dump(mode="json"),
                            "hero_retrieved": any(
                                item.memory_id == ingest.memory_id
                                for item in result.items
                            ),
                            "repeat_text_identical": [
                                (x.memory_id, x.content) for x in result.items
                            ]
                            == [(x.memory_id, x.content) for x in repeated.items],
                            "chain": chain,
                        }
                    )
                    save_json(evidence_path, evidence)
                    print(
                        f"{manifest['take_id']}: {witness['stable_id']} day {day} saved",
                        flush=True,
                    )
            finally:
                await runner.close()
        evidence["status"] = "complete_pending_review"
        manifest["status"] = "rehearsed"
    except Exception as exc:
        # SDK exception messages can contain URLs; retain only the safe class.
        evidence["status"] = "failed"
        evidence["error_type"] = type(exc).__name__
        manifest["status"] = "aborted"
        raise
    finally:
        save_json(path, manifest)
        save_json(evidence_path, evidence)
        providers.gate.shutdown()
        await pool.close()
    return evidence_path


async def run(args) -> None:
    settings = load_settings()
    if settings.provider_mode != "real":
        raise ValueError("Demo rehearsals require TWICETOLD_PROVIDER_MODE=real")
    if args.command == "serve":
        import uvicorn
        from urllib.parse import urlsplit

        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        name = manifest["database_name"]
        if not name.startswith("twicetold_video_"):
            raise ValueError("Only a village demo database may be served here")
        os.environ["DATABASE_URI"] = scratch_uri(settings.database_uri, name)
        url = urlsplit(manifest["base_url"])
        if url.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("Demo server must bind to loopback")
        await uvicorn.Server(
            uvicorn.Config("app.api:app", host=url.hostname, port=url.port or 8000)
        ).serve()
    elif args.command == "provision":
        manifest, path, _ = await provision(settings, base_url=args.base_url)
        save_json(DEMO_ROOT / "session.json", manifest)
        print(path)
    else:
        for _ in range(args.takes):
            print(await rehearse(settings, base_url=args.base_url), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("provision", "rehearse", "serve"))
    parser.add_argument("--manifest", type=Path, default=DEMO_ROOT / "session.json")
    parser.add_argument("--takes", type=int, default=3)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    if args.takes < 1:
        parser.error("--takes must be positive")
    asyncio.run(run(args), loop_factory=asyncio.SelectorEventLoop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
