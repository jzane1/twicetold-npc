"""Executable HTTP integration example: python -m app.first_run --help.

The scenario is bundled in this module so the Compose image is self-contained.
It creates a new agent on every run. No SQL, internal service calls, or POST
retries: after an ambiguous timeout the partial run remains inspectable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode, urlsplit

import httpx

OBSERVATION = (
    "Mara returned my lost ledger at the Waystone Inn. She found it beside the "
    "well and kept every page dry. I thanked her and promised to help repair "
    "her market stall. Rain tapped the green shutters while a fiddler played "
    "near the fireplace. My tea had gone cold and three copper coins lay on "
    "the table. I left feeling grateful that a neighbor had looked out for me."
)
PINNED_OBSERVATION = (
    "Mara runs the market stall beside the Waystone Inn. "
    "We agreed to meet there on market mornings."
)
CORRECTION = (
    "Mara returned my lost ledger at the Waystone Inn. She found it in the "
    "market, not beside the well. I thanked her and promised to help repair "
    "her market stall."
)
QUERY = "What do I remember about Mara, my lost ledger, and the Waystone Inn?"


class DemoError(RuntimeError):
    """A safe, actionable failure; never contains a remote response body."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DemoError(message)


def telling_snapshot(items: list[dict]) -> dict:
    """Stable scene state, independent of new query embeddings and rankings.

    Real embedding services can return slightly different vectors for the
    same query. The cache guarantees stored text/versions, not float scores.
    """
    return {
        item["memory_id"]: tuple(
            item[key] for key in ("detail_id", "content", "read_mode", "pinned")
        )
        for item in items
    }


def base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in {"", "/"}
        )
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError(
            "Use an HTTP(S) origin without credentials or a path."
        )
    return value.rstrip("/")


async def run_demo(
    client: httpx.AsyncClient,
    *,
    mode: str,
    public_url: str,
    emit: Callable[[str], None] = print,
    start: datetime | None = None,
) -> dict:
    """Run against any API client, including ASGITransport in focused tests."""
    start = start or datetime.now(timezone.utc).replace(microsecond=0)
    require(start.tzinfo is not None, "The demo clock must include a timezone.")
    require(mode in {"fake", "real"}, "Choose fake or real mode explicitly.")
    report: dict = {"mode": mode, "checks": [], "usage": {}}

    def passed(name: str) -> None:
        report["checks"].append(name)
        emit(f"PASS {name}")

    def account(data: dict) -> None:
        # Instrumentation is flat except for dialogue's nested retrieval.
        for key, value in data.items():
            if isinstance(value, dict):
                account(value)
            elif key.endswith("_tokens") and isinstance(value, int):
                report["usage"][key] = report["usage"].get(key, 0) + value

    async def request(method: str, path: str, body: dict | None = None) -> dict:
        try:
            response = await client.request(method, path, json=body)
        except httpx.RequestError:
            raise DemoError(
                f"{method} {path}: connection failed or timed out. Check Compose logs. "
                "The request was not retried; a write may already have completed."
            ) from None
        require(
            response.is_success,
            f"{method} {path}: HTTP {response.status_code}. Check Compose logs and "
            "app.doctor --probe-providers; response details are suppressed.",
        )
        try:
            data = response.json()
            require(isinstance(data, dict), f"{path}: expected a JSON object.")
        except ValueError:
            raise DemoError(f"{path}: expected JSON.") from None
        account(data.get("instrumentation", {}))
        if "embedding_tokens" in data:  # correction's flat accounting
            account({"embedding_tokens": data["embedding_tokens"]})
        return data

    async def scene(at: datetime) -> dict:
        boundary = await request(
            "POST",
            "/v1/events/scene-boundary",
            {
                "agent_id": agent,
                "client_timestamp": at.isoformat(),
            },
        )
        require(
            bool(boundary["identity_version"]),
            "Scene boundary returned no identity version.",
        )
        return {
            "agent_id": agent,
            "as_of": at.isoformat(),
            "scene_started_at": at.isoformat(),
            "identity_version": boundary["identity_version"],
            "k": 2,
        }

    async def recall(context: dict, label: str) -> dict:
        result = await request(
            "POST",
            "/v1/dialogue/init",
            {
                **context,
                "query_text": QUERY,
            },
        )
        require(
            not result["instrumentation"]["degraded"],
            f"{label}: retrieval degraded. Check provider connectivity and server logs.",
        )
        items = {item["memory_id"]: item for item in result["items"]}
        require(
            set(items) == set(memory_ids), f"{label}: expected both recorded memories."
        )
        require(
            all(math.isfinite(item["score"]) for item in items.values()),
            f"{label}: non-finite retrieval score.",
        )
        report[label] = result
        emit(f"\n{label} ({context['as_of']}):")
        for item in items.values():
            emit(
                f"  {item['memory_id']} | {item['read_mode']} | score={item['score']:.6f} | pinned={item['pinned']}\n  {item['content']}"
            )
        return result

    emit(
        f"First-run demo: {mode} providers. "
        + (
            "Deterministic plumbing check; no remote model calls."
            if mode == "fake"
            else "Live provider calls; wording and token usage will vary."
        )
    )
    created = await request(
        "POST",
        "/v1/agents",
        {
            "name": "First-run keeper",
            "seed_identity": "I keep the Waystone Inn. I value neighbors who help one another and remember kindness with gratitude.",
            "rigidity": 1.0,
            "config": {
                "decay_classes": {"episodic": 86400},
                "decay_class_default": "episodic",
            },
        },
    )
    agent = created["agent_id"]
    report["agent_id"] = agent
    emit(
        f"Agent: {agent}\nInspector: {public_url}/ledger?{urlencode({'agent': agent})}"
    )
    memory_ids = []
    writes = []
    for text, pinned in ((OBSERVATION, False), (PINNED_OBSERVATION, True)):
        result = await request(
            "POST",
            "/v1/events/observe",
            {
                "agent_id": agent,
                "observation_text": text,
                "client_timestamp": start.isoformat(),
                "phase_tag": "first-run",
                "provenance": "lived",
                "typology": "observed",
                "decay_class": "episodic",
                "pinned": pinned,
            },
        )
        memory_ids.append(result["memory_id"])
        writes.append(result)
        emit(f"Recorded memory: {result['memory_id']}")
        require(
            not any(
                result[key]
                for key in (
                    "scoring_failed",
                    "embedding_failed",
                    "escalation_failed",
                    "enrichment_pending",
                    "decay_class_unknown",
                )
            ),
            "Observation degraded. Check provider settings before judging the demo.",
        )
    target, pinned_id = memory_ids
    report["memory_ids"] = memory_ids
    report["observations"] = writes
    report["inspector_url"] = (
        public_url + "/ledger?" + urlencode({"agent": agent, "memory": target})
    )
    passed("agent and two observations created without degradation")

    fresh = await recall(await scene(start), "fresh")
    require(
        all(i["read_mode"] == "verbatim" for i in fresh["items"]),
        "Fresh recall should be verbatim.",
    )
    passed("fresh recall serves stored tellings with IDs and scores")

    # Only the simulated clock advances; no wall-clock wait or historical query.
    aged_context = await scene(start + timedelta(days=7))
    aged = await recall(aged_context, "aged")
    by_id = {i["memory_id"]: i for i in aged["items"]}
    require(
        by_id[target]["read_mode"] == "reconstructed"
        and aged["instrumentation"]["write_backs"] == 1,
        "Aged recall did not persist a reconstruction. A drift refusal is a valid guard outcome, but does not complete this demonstration. Check the model output in the inspector; the demo keeps the default drift budget.",
    )
    require(
        by_id[pinned_id]["read_mode"] == "verbatim",
        "Pinned memory should remain verbatim.",
    )
    fresh_pin = next(i for i in fresh["items"] if i["memory_id"] == pinned_id)
    require(
        by_id[pinned_id]["detail_id"] == fresh_pin["detail_id"]
        and by_id[pinned_id]["content"] == fresh_pin["content"],
        "Pinned memory's stored telling changed as time advanced.",
    )
    passed("seven days later: reconstruction persisted; pinned memory stays verbatim")

    repeat = await recall(aged_context, "repeat")
    require(
        telling_snapshot(repeat["items"]) == telling_snapshot(aged["items"]),
        "Same-scene recall changed stored text, IDs or read modes.",
    )
    require(
        repeat["instrumentation"]["cache_hits"] == 1
        and repeat["instrumentation"]["write_backs"] == 0,
        "Repeated recall should use the reconstruction cache without writing.",
    )
    passed("same scene returns identical stored tellings from cache")

    dialogue = await request(
        "POST",
        "/v1/dialogue/turn",
        {
            **aged_context,
            "utterance": QUERY,
        },
    )
    require(
        not dialogue["instrumentation"]["degraded"]
        and not dialogue["instrumentation"]["retrieval"]["degraded"],
        "Dialogue degraded. Check the dialogue model and provider logs.",
    )
    require(
        telling_snapshot(dialogue["items"]) == telling_snapshot(aged["items"]),
        "Dialogue did not use the same scene's memories.",
    )
    report["dialogue"] = dialogue
    emit(f"\nDialogue: {dialogue['content']}")
    passed("dialogue uses the recalled memories")

    before = await request("GET", f"/v1/memories/{target}/chain")
    correction = await request(
        "POST",
        f"/v1/memories/{target}/correction",
        {
            "content": CORRECTION,
            "client_timestamp": (start + timedelta(days=7, seconds=1)).isoformat(),
            "expected_detail_id": by_id[target]["detail_id"],
        },
    )
    require(
        correction["evicted_cache_rows"] >= 1,
        "Correction did not evict the old reconstruction cache.",
    )
    # New scene ensures the reconstruction's timestamp follows the correction.
    corrected = await recall(
        await scene(start + timedelta(days=7, seconds=2)), "corrected"
    )
    after = await request("GET", f"/v1/memories/{target}/chain")
    live_facts = [f for f in after["facts"] if f["is_live"]]
    require(
        len(live_facts) == 1
        and live_facts[0]["basis_text"] == CORRECTION
        and live_facts[0]["has_embedding"],
        "Corrected fact head is missing, unembedded, or does not match the supplied correction.",
    )
    require(
        live_facts[0]["fact_version_id"] == correction["fact_version_id"],
        "Correction fact ID mismatch.",
    )
    old_detail_ids = {d["detail_id"] for d in before["details"]}
    require(
        old_detail_ids <= {d["detail_id"] for d in after["details"]}
        and all(
            not d["is_live"]
            for d in after["details"]
            if d["detail_id"] in old_detail_ids
        ),
        "Correction failed to preserve and supersede prior tellings.",
    )
    require(
        after["observation_text"] == OBSERVATION and len(after["facts"]) == 2,
        "Correction changed the original observation or failed to preserve fact history.",
    )
    served = next(i for i in corrected["items"] if i["memory_id"] == target)
    live_details = [d for d in after["details"] if d["is_live"]]
    require(
        len(live_details) == 1
        and served["detail_id"] == live_details[0]["detail_id"]
        and served["content"] == live_details[0]["content"]
        and served["detail_id"] not in old_detail_ids,
        "Post-correction retrieval served stale or unpersisted text.",
    )
    report["chain"] = after
    report["correction"] = correction
    passed(
        "correction replaces the fact head; subsequent recall serves the new chain; history survives"
    )
    report["ok"] = True
    emit(
        f"\nPASS first-run demo ({mode})\nInspector: {report['inspector_url']}\nToken usage (fake counts are synthetic): {json.dumps(report['usage'], sort_keys=True)}"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    from app.config import ConfigError, load_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("fake", "real"))
    parser.add_argument("--base-url", type=base_url, default="http://127.0.0.1:8000")
    parser.add_argument(
        "--public-url",
        type=base_url,
        default=None,
        help="Browser origin for inspector links (defaults to --base-url).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Per-request timeout in seconds; no automatic HTTP retries.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON report instead of the narrated walkthrough.",
    )
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite positive number")

    async def run() -> dict:
        async with httpx.AsyncClient(
            base_url=args.base_url, timeout=args.timeout, trust_env=False
        ) as client:
            return await run_demo(
                client,
                mode=args.mode,
                public_url=args.public_url or args.base_url,
                emit=(lambda _: None) if args.json else print,
            )

    try:
        settings = load_settings()
        require(
            settings.provider_mode == args.mode,
            "Requested mode differs from the local API configuration. Use the matching Compose demo file(s).",
        )
        result = asyncio.run(run())
    except (ConfigError, DemoError, SystemExit) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"FAIL {exc}")
        return 1
    except (KeyError, TypeError, ValueError):
        # Unexpected wire shape is a failed integration, not a traceback with
        # a potentially sensitive provider error payload.
        print(
            json.dumps({"ok": False, "error": "Unexpected API response shape."})
            if args.json
            else "FAIL Unexpected API response shape."
        )
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
