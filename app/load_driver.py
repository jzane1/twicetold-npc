"""load_driver.py — the synthetic load driver: scripted sessions at volume.

A first-class artifact co-built with the CLI harness (architecture §11: "no
distribution exists without it"). It drives observe events, utterances, and
scene boundaries through the SAME shared session-runner core the REPL uses
(app\\session.py) — no divergent second path, no timing of its own: every
number below is read off the seams' instrumentation payloads.

    PowerShell:  python -m app.load_driver [--sessions 5] [--turns 10]
                     [--script path.json] [--seed 0] [--agent <uuid>]
                     [--database-uri <uri>] [--json out.json]

Runs offline and keyless on the deterministic fake providers by default
(TWICETOLD_PROVIDER_MODE=fake); the real providers back a keyed smoke moment
ahead of demo choreography. Without --agent it creates a fresh driver agent
in the target database — point --database-uri at a scratch DB for clean
runs (verification uses twicetold_test); the product DB stays untouched unless
you aim at it deliberately.

Script format (--script): a JSON list of sessions; each session is a list of
events: {"kind": "observe", "text": ...} | {"kind": "utterance", "text": ...}
| {"kind": "scene"}. Omitted, a seeded built-in generator produces a
deterministic mix (same seed -> same script -> same fake outputs, byte for
byte).

Emits the §11 aggregates: the latency histogram (p50/p95 — gate check
(landed with the gate build 2026-07-19, over gate-evaluated turns only — a
series padded with loader-turn zeros would lie), retrieval SQL, query embed,
first word (prose TTFT at the seam — the headline, 2026-07-21), dialogue
total, turn total) and the itemized per-100-turn cost table (tokens per
model role, unconditionally; USD only for roles priced via TWICETOLD_PRICE_* —
build ruling 2026-07-15; the gate is non-LLM, no cost row), plus the
per-100-turn gate block (fires per signal, efficacy fractions, fruitless
fetches, damper activations — instrumentation-only by fork 4, the reserved
kill-switch decision's evidence).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from app import db
from app.config import Settings, load_settings
from app.db import build_pool
from app.gate import GATE_SIGNAL_ENTITY, GATE_SIGNAL_NOVELTY
from app.providers import build_providers
from app.schemas import DialogueTurnResult, IngestResult
from app.session import SessionRunner

_GENERATOR_TOPICS = [
    "the forge",
    "the north road",
    "the baron's tax",
    "the storm",
    "the market",
]

DRIVER_AGENT_CONFIG = {
    "decay_classes": {"episodic": 86400.0, "semantic": 604800.0},
    "decay_class_default": "episodic",
}


def generate_script(sessions: int, turns: int, seed: int) -> list[list[dict]]:
    """Deterministic synthetic sessions: same seed, same script."""
    rng = random.Random(seed)
    script: list[list[dict]] = []
    for s in range(sessions):
        events: list[dict] = []
        for t in range(turns):
            topic = rng.choice(_GENERATOR_TOPICS)
            if rng.random() < 0.4:
                events.append(
                    {
                        "kind": "observe",
                        "text": f"[s{s}t{t}] Something happened near {topic}.",
                    }
                )
            events.append(
                {
                    "kind": "utterance",
                    "text": f"[s{s}t{t}] Tell me about {topic}.",
                }
            )
            if t and t % 5 == 0:
                events.append({"kind": "scene"})
        script.append(events)
    return script


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile; 0.0 on an empty series."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return round(ordered[lo], 2)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 2)


async def _create_driver_agent(pool) -> UUID:
    """The driver's fixture agent, provisioned through the shared db verb —
    the same statement `POST /v1/agents` uses, so the driver measures the
    real provisioning path and no SQL lives outside app\\db.py."""
    return await db.insert_agent(
        pool,
        name="load-driver",
        seed_identity="A synthetic NPC standing in for load measurement.",
        rigidity=1.0,
        diagnosticity_goal="what matters to a load test",
        config=DRIVER_AGENT_CONFIG,
    )


async def run_driver(
    settings: Settings,
    *,
    sessions: int,
    turns: int,
    script: list[list[dict]] | None = None,
    seed: int = 0,
    agent_id: UUID | None = None,
    gate_budget: float | None = None,
) -> dict:
    """Drive the script through the seams; return the §11 aggregates.

    Separable from main() so the structural walker can run it in-process on
    an injected scratch Settings. `gate_budget` (encoding-context build,
    2026-07-20 — the TARG calibration recipe, arXiv 2511.09803 §3.4) adds a
    report-only gate_calibration block: the gate_novelty_threshold value
    that would fire on ~that fraction of evaluated turns, read off the run's
    empirical novelty-distance CDF. It never sets the knob.
    """
    script = script if script is not None else generate_script(sessions, turns, seed)
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    providers = build_providers(settings)
    turn_results: list[DialogueTurnResult] = []
    ingest_results: list[IngestResult] = []
    try:
        if agent_id is None:
            agent_id = await _create_driver_agent(pool)
        for events in script:
            runner = await SessionRunner.create(
                agent_id,
                settings=settings,
                providers=providers,
                pool=pool,
                phase_tag="load-driver",
                # Warm the NLP stack before the first measured event so model
                # load never lands inside a turn's numbers.
                warm_nlp=any(e["kind"] == "observe" for e in events),
            )
            for event in events:
                if event["kind"] == "observe":
                    ingest_results.append(await runner.observe(event["text"]))
                elif event["kind"] == "utterance":
                    turn_results.append(await runner.utterance(event["text"]))
                elif event["kind"] == "scene":
                    await runner.scene()
                else:
                    raise ValueError(f"unknown script event kind {event['kind']!r}")
            await runner.close()  # pool is driver-owned; close is a no-op
    finally:
        await pool.close()
    report = _aggregate(
        settings, agent_id, turn_results, ingest_results, gate_budget=gate_budget
    )
    report["sessions"] = len(script)
    return report


def gate_budget_calibration(
    gates: list, budget: float, default_threshold: float
) -> dict:
    """TARG-style budget calibration (arXiv 2511.09803 §3.4), adapted from
    their logit-uncertainty score to our non-LLM novelty distance: the
    threshold tau at the (1 - budget) quantile of the per-turn novelty
    min-distance CDF fires on ~budget of evaluated turns. Report-only.

    Turns whose min_distance is None (empty loaded set / all-NULL embeddings
    — trivially novel, they fire regardless of tau) are counted honestly but
    sit outside the CDF; the projected rate covers calibratable turns only.
    The default_threshold is the SERVICE default — a per-agent
    agents.config override is not consulted here (stated, not silent)."""
    distances = [
        g.novelty_min_distance
        for g in gates
        if g.evaluated and g.novelty_min_distance is not None
    ]
    trivially_novel = sum(
        1 for g in gates if g.evaluated and g.novelty_min_distance is None
    )
    if not distances:
        return {
            "target_fire_rate": budget,
            "samples": 0,
            "trivially_novel_turns": trivially_novel,
            "recommended_threshold": None,
            "projected_fire_rate": None,
            "rate_at_service_default": None,
        }
    recommended = percentile(distances, 1.0 - budget)
    projected = sum(1 for d in distances if d >= recommended) / len(distances)
    at_default = sum(1 for d in distances if d >= default_threshold) / len(distances)
    return {
        "target_fire_rate": budget,
        "samples": len(distances),
        "trivially_novel_turns": trivially_novel,
        "recommended_threshold": recommended,
        "projected_fire_rate": round(projected, 3),
        "rate_at_service_default": round(at_default, 3),
    }


def _aggregate(
    settings: Settings,
    agent_id: UUID,
    turns: list[DialogueTurnResult],
    observes: list[IngestResult],
    *,
    gate_budget: float | None = None,
) -> dict:
    prices = settings.prices
    gates = [t.instrumentation.retrieval.gate for t in turns]
    series = {
        "gate_check": [g.gate_ms for g in gates if g.evaluated],
        "retrieval_sql": [t.instrumentation.retrieval.sql_ms for t in turns],
        "query_embed": [t.instrumentation.retrieval.embed_ms for t in turns],
        "reconstruction": [
            t.instrumentation.retrieval.reconstruction_ms for t in turns
        ],
        # The honest headline pair (turn-route build, 2026-07-23):
        # `first_word` is prose TTFT at the seam (series continuity);
        # `perceived_first_word` clocks from turn start — retrieval-inclusive,
        # the field the <1s viability bar is measured against.
        "first_word": [t.instrumentation.first_word_ms for t in turns],
        "perceived_first_word": [
            t.instrumentation.perceived_first_word_ms for t in turns
        ],
        # Pre-prose attribution (F0, 2026-08-26): everything before the prose
        # call's first chunk, as a per-turn series — p50s don't subtract, so
        # `perceived p50 - first_word p50` is NOT the pre-prose p50.
        "pre_prose": [
            t.instrumentation.perceived_first_word_ms - t.instrumentation.first_word_ms
            for t in turns
        ],
        "dialogue_total": [t.instrumentation.prose_stream_ms for t in turns],
        "turn_total": [t.instrumentation.total_ms for t in turns],
        # Observe latency series (added with the deferred-write build,
        # 2026-08-12 — C1 changes observe latency and no series existed).
        # Deferred-token caveat: with `deferred_writes_enabled` on, the
        # write/escalation rows below sum SEAM tokens and will read ~0; the
        # deferred spend's source of truth is memory_enrichment_runs.
        "observe_total": [o.instrumentation.total_ms for o in observes],
    }
    latency = {
        name: {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}
        for name, values in series.items()
    }

    n_turns = max(len(turns), 1)

    def per_100(count: int) -> float:
        return round(count * 100.0 / n_turns, 1)

    def usd(tokens_in: int, tokens_out: int, key_in: str, key_out: str) -> float | None:
        if key_in in prices and key_out in prices:
            return round(
                (tokens_in * prices[key_in] + tokens_out * prices[key_out]) / 1e6, 6
            )
        return None

    dialogue_in = sum(t.instrumentation.sonnet_input_tokens for t in turns)
    dialogue_out = sum(t.instrumentation.sonnet_output_tokens for t in turns)
    write_in = sum(o.instrumentation.haiku_input_tokens for o in observes)
    write_out = sum(o.instrumentation.haiku_output_tokens for o in observes)
    esc_in = sum(o.instrumentation.escalation_input_tokens for o in observes)
    esc_out = sum(o.instrumentation.escalation_output_tokens for o in observes)
    recon_in = sum(
        t.instrumentation.retrieval.reconstruction_input_tokens for t in turns
    )
    recon_out = sum(
        t.instrumentation.retrieval.reconstruction_output_tokens for t in turns
    )
    embed_tokens = (
        sum(o.instrumentation.embedding_tokens for o in observes)
        + sum(t.instrumentation.retrieval.embedding_tokens for t in turns)
        # Drift-check embeddings ride the same embedding role/price.
        + sum(t.instrumentation.retrieval.reconstruction_embed_tokens for t in turns)
    )
    embed_usd = (
        round(embed_tokens * prices["embedding"] / 1e6, 6)
        if "embedding" in prices
        else None
    )
    cost = {
        "dialogue": {
            "input_tokens_per_100_turns": per_100(dialogue_in),
            "output_tokens_per_100_turns": per_100(dialogue_out),
            "usd_per_100_turns": usd(
                dialogue_in, dialogue_out, "dialogue_in", "dialogue_out"
            ),
        },
        "write": {
            "input_tokens_per_100_turns": per_100(write_in),
            "output_tokens_per_100_turns": per_100(write_out),
            "usd_per_100_turns": usd(write_in, write_out, "write_in", "write_out"),
        },
        "escalation": {
            "input_tokens_per_100_turns": per_100(esc_in),
            "output_tokens_per_100_turns": per_100(esc_out),
            "usd_per_100_turns": usd(
                esc_in, esc_out, "escalation_in", "escalation_out"
            ),
        },
        "reconstruction": {
            "input_tokens_per_100_turns": per_100(recon_in),
            "output_tokens_per_100_turns": per_100(recon_out),
            "usd_per_100_turns": usd(
                recon_in, recon_out, "reconstruction_in", "reconstruction_out"
            ),
        },
        "embedding": {
            "tokens_per_100_turns": per_100(embed_tokens),
            "usd_per_100_turns": embed_usd,
        },
    }
    # Scale the USD table to per-100-turns too, when priced at all.
    for row in ("dialogue", "write", "escalation", "reconstruction"):
        if cost[row]["usd_per_100_turns"] is not None:
            cost[row]["usd_per_100_turns"] = round(
                cost[row]["usd_per_100_turns"] * 100.0 / n_turns, 6
            )
    if cost["embedding"]["usd_per_100_turns"] is not None:
        cost["embedding"]["usd_per_100_turns"] = round(
            cost["embedding"]["usd_per_100_turns"] * 100.0 / n_turns, 6
        )
    # The gate block (mid-dialogue-gate.md §11 closure): per-signal fire
    # rates + the ruled efficacy fractions, computed over the fires whose
    # boolean was computable (non-None); None when no such fire happened.
    fired = [g for g in gates if g.fired]

    def _efficacy(values: list[bool | None]) -> float | None:
        known = [v for v in values if v is not None]
        if not known:
            return None
        return round(sum(1 for v in known if v) / len(known), 3)

    gate_block = {
        "evaluated_turns": sum(1 for g in gates if g.evaluated),
        "fires_per_100_turns": per_100(len(fired)),
        "novelty_fires_per_100_turns": per_100(
            sum(1 for g in fired if GATE_SIGNAL_NOVELTY in g.signals_fired)
        ),
        "entity_fires_per_100_turns": per_100(
            sum(1 for g in fired if GATE_SIGNAL_ENTITY in g.signals_fired)
        ),
        "novelty_efficacy": _efficacy([g.novelty_outscored for g in fired]),
        "entity_efficacy": _efficacy([g.entity_covered for g in fired]),
        "fruitless_fetches": sum(1 for g in gates if g.fruitless),
        "damper_activated_turns": sum(1 for g in gates if g.damper_active),
    }
    report_gate_calibration = (
        gate_budget_calibration(
            gates, gate_budget, settings.defaults["gate_novelty_threshold"]
        )
        if gate_budget is not None
        else None
    )
    return {
        "agent_id": str(agent_id),
        "turns": len(turns),
        "observes": len(observes),
        "latency_ms": latency,
        "per_100_turns": cost,
        "gate": gate_block,
        "gate_calibration": report_gate_calibration,
        "degraded_turns": sum(1 for t in turns if t.instrumentation.degraded),
        "write_backs": sum(t.instrumentation.retrieval.write_backs for t in turns),
        "drift_refusals": sum(
            t.instrumentation.retrieval.drift_refusals for t in turns
        ),
        "cache_hits": sum(t.instrumentation.retrieval.cache_hits for t in turns),
    }


def _print_report(report: dict) -> None:
    print(
        f"\nagent {report['agent_id']} — {report['turns']} turns, "
        f"{report['observes']} observes, {report['degraded_turns']} degraded"
    )
    print(
        f"reconstruction: {report['write_backs']} write-backs, "
        f"{report['cache_hits']} cache hits, "
        f"{report['drift_refusals']} drift refusals"
    )
    g = report["gate"]
    novelty_eff = g["novelty_efficacy"]
    entity_eff = g["entity_efficacy"]
    print(
        f"gate: {g['evaluated_turns']} evaluated turns, "
        f"{g['fires_per_100_turns']} fires/100 "
        f"(novelty {g['novelty_fires_per_100_turns']}, "
        f"entity {g['entity_fires_per_100_turns']}), "
        f"efficacy novelty="
        f"{novelty_eff if novelty_eff is not None else '(no fires)'} "
        f"entity={entity_eff if entity_eff is not None else '(no fires)'}, "
        f"{g['fruitless_fetches']} fruitless, "
        f"{g['damper_activated_turns']} damper-active"
    )
    cal = report.get("gate_calibration")
    if cal is not None:
        if cal["recommended_threshold"] is None:
            print(
                f"gate calibration: no calibratable samples "
                f"({cal['trivially_novel_turns']} trivially-novel turns)"
            )
        else:
            print(
                f"gate calibration (target {cal['target_fire_rate']}): "
                f"recommended gate_novelty_threshold="
                f"{cal['recommended_threshold']} "
                f"(projected rate {cal['projected_fire_rate']}, "
                f"service default fires at {cal['rate_at_service_default']}; "
                f"{cal['samples']} samples, "
                f"{cal['trivially_novel_turns']} trivially novel) — report-only"
            )
    print("\nlatency (ms)                p50        p95")
    for name, row in report["latency_ms"].items():
        print(f"  {name:<24} {row['p50']:>8}   {row['p95']:>8}")
    print("\nper-100-turn cost           tokens (in/out)        USD")
    for role, row in report["per_100_turns"].items():
        if role == "embedding":
            tokens = f"{row['tokens_per_100_turns']}"
        else:
            tokens = (
                f"{row['input_tokens_per_100_turns']}/"
                f"{row['output_tokens_per_100_turns']}"
            )
        usd_val = row["usd_per_100_turns"]
        usd_text = f"${usd_val}" if usd_val is not None else "(unpriced)"
        print(f"  {role:<24} {tokens:>20}   {usd_text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="twicetold-npc synthetic load driver")
    parser.add_argument("--sessions", type=int, default=5)
    parser.add_argument("--turns", type=int, default=10, help="turns per session")
    parser.add_argument("--script", type=Path, help="JSON script (see module doc)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--agent", type=UUID, help="existing agent (else create one)")
    parser.add_argument("--database-uri", help="override .env DATABASE_URI")
    parser.add_argument("--json", type=Path, help="also write the report as JSON")
    parser.add_argument(
        "--gate-budget",
        type=float,
        help="target novelty fire-rate in (0,1): report the "
        "gate_novelty_threshold the run's empirical CDF recommends "
        "(TARG-style calibration; report-only, never sets the knob)",
    )
    args = parser.parse_args()
    if args.gate_budget is not None and not (0.0 < args.gate_budget < 1.0):
        parser.error("--gate-budget must be strictly between 0 and 1")

    settings = load_settings()
    if args.database_uri:
        settings = replace(settings, database_uri=args.database_uri)
    script = None
    if args.script:
        script = json.loads(args.script.read_text(encoding="utf-8"))

    report = asyncio.run(
        run_driver(
            settings,
            sessions=args.sessions,
            turns=args.turns,
            script=script,
            seed=args.seed,
            agent_id=args.agent,
            gate_budget=args.gate_budget,
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )
    _print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nreport written to {args.json}")


if __name__ == "__main__":
    main()
