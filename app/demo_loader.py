"""demo_loader.py — corpus -> demo-DB loader (E2, ruled 2026-08-19).

    PowerShell:  python -m app.demo_loader --fresh

Loads the demo corpus into a STABLE demo database (default `twicetold_demo`)
so the recording rig — `python -m app.serve` pointed at it, the Unity scene,
The Ledger — drives one persistent agent. This is deliberately not an eval
verb: the eval runner's databases are pid-scoped and dropped; the demo DB
survives the process and is only ever recreated by an explicit `--fresh`.

The provisioned agent carries the corpus block's five fields verbatim, and
the two worker-enable flags land AFTER the replay finishes (the E1 record's
shape: same seed, goal, rigidity, and decay config, diverging on exactly
those flags) — so the replay itself is deterministic, and the started
workers idle over an un-flagged agent. `--no-workers` skips the flip.

Each run rolls fresh write-time judgments (importance, gist spans), so the
printed report IS the rehearsal guard's input: inspect the roll, re-run with
`--fresh` until it is good, and the take then pins by the constancy
invariant (docs\\identity-authoring.md section 6).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from app import db
from app.config import load_settings
from app.db import build_pool
from app.eval_scenarios import (
    AsOfStep,
    ObserveStep,
    Scenario,
    assert_corpus_shape,
    load_scenarios,
)
from app.schemas import IngestResult
from app.scratch_db import provision_scratch
from app.session import SessionRunner

DEMO_DB_DEFAULT = "twicetold_demo"
DEMO_CORPUS = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "eval"
    / "corpora"
    / "demo-waystone.jsonl"
)
# The demo agent's divergence from its corpus block (D1 ruling 2026-08-19:
# workers stay OFF globally; the demo agent opts in per-agent).
WORKER_FLAGS = {"reflection_worker_enabled": 1.0, "compiler_worker_enabled": 1.0}


def _roll_row(ref: int, ingest: IngestResult) -> dict:
    flags = [
        name
        for name, hit in (
            ("scoring_failed", ingest.scoring_failed),
            ("escalation_failed", ingest.escalation_failed),
            ("embedding_failed", ingest.embedding_failed),
            ("enrichment_pending", ingest.enrichment_pending),
        )
        if hit
    ]
    return {
        "ref": ref,
        "memory_id": ingest.memory_id,
        "importance_raw": ingest.importance_raw,
        "gist_spans": len(ingest.gist_span_ids),
        "decay_class": ingest.decay_class,
        "flags": flags,
    }


async def load_demo(
    settings, scenario: Scenario, *, enable_workers: bool = True
) -> dict:
    """Provision the agent, replay the corpus, then (unless disabled) merge
    the worker flags — separable so the suite drives it in-process on an
    injected scratch Settings (the run_scenarios shape)."""
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    try:
        agent_id: UUID = await db.insert_agent(
            pool,
            name=scenario.agent.name,
            seed_identity=scenario.agent.seed_identity,
            rigidity=scenario.agent.rigidity,
            diagnosticity_goal=scenario.agent.diagnosticity_goal,
            config=scenario.agent.config,
        )
        runner = await SessionRunner.create(
            agent_id,
            settings=settings,
            pool=pool,
            phase_tag="demo-loader",
            warm_nlp=any(isinstance(e, ObserveStep) for e in scenario.events),
        )
        rows: list[dict] = []
        try:
            for event in scenario.events:
                if isinstance(event, AsOfStep):
                    runner.as_of = event.at
                elif isinstance(event, ObserveStep):
                    ingest = await runner.observe(event.text)
                    rows.append(_roll_row(len(rows), ingest))
        finally:
            await runner.close()
        config = dict(scenario.agent.config)
        if enable_workers:
            config = await db.merge_agent_config(pool, agent_id, WORKER_FLAGS)
        return {"agent_id": agent_id, "memories": rows, "config": config}
    finally:
        await pool.close()


def _print_report(report: dict, *, database_name: str, provider_mode: str) -> None:
    agent_id = report["agent_id"]
    print(f"\nprovisioned roll: {database_name} ({provider_mode} mode)")
    print(f"agent_id: {agent_id}")
    print(f"{'ref':>3}  {'memory_id':<36}  {'importance':>10}  {'spans':>5}  class")
    for row in report["memories"]:
        importance = (
            f"{row['importance_raw']:.3f}"
            if row["importance_raw"] is not None
            else "n/a"
        )
        line = (
            f"{row['ref']:>3}  {str(row['memory_id']):<36}  "
            f"{importance:>10}  {row['gist_spans']:>5}  {row['decay_class']}"
        )
        if row["flags"]:
            line += "  [" + ", ".join(row["flags"]) + "]"
        print(line)
    worker_keys = sorted(WORKER_FLAGS)
    stored = {key: report["config"].get(key) for key in worker_keys}
    print("worker flags as stored: " + ", ".join(f"{k}={v}" for k, v in stored.items()))
    print("\nhand-off:")
    print(f"  Unity inspector agentIdOverride: {agent_id}")
    print(f"  Ledger deep link: http://127.0.0.1:8000/ledger?agent={agent_id}")
    print(
        f"  next: point DATABASE_URI at '{database_name}' in .env, "
        "then: python -m app.serve"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo_loader",
        description=(
            "Load the demo corpus into a stable demo database. Destructive by "
            "design — the target database is dropped and recreated — so it "
            "refuses to act without --fresh."
        ),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help=(
            "required to act: drop + recreate the demo database and roll a "
            "fresh provisioning (a pinned take does not survive this)"
        ),
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEMO_CORPUS,
        help=f"corpus JSONL (default: {DEMO_CORPUS})",
    )
    parser.add_argument("--database-name", default=DEMO_DB_DEFAULT)
    parser.add_argument(
        "--database-uri",
        default=None,
        help="base URI (default: DATABASE_URI from .env); the demo database "
        "name replaces its dbname",
    )
    parser.add_argument(
        "--no-workers",
        action="store_true",
        help="leave the worker-enable flags off (pure corpus config)",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.corpus)
    if len(scenarios) != 1:
        print(
            f"{args.corpus} holds {len(scenarios)} scenarios; the demo loader "
            "provisions exactly one agent — split the file or pass a "
            "single-scenario corpus.",
            file=sys.stderr,
        )
        return 2
    scenario = scenarios[0]
    assert_corpus_shape(scenario)

    if not args.fresh:
        print(
            f"refusing without --fresh. This run would: drop database "
            f"'{args.database_name}' (if it exists), recreate + migrate it, "
            f"provision agent {scenario.agent.name!r}, replay "
            f"{sum(1 for e in scenario.events if isinstance(e, ObserveStep))} "
            "observes (a fresh importance/spans roll; any pinned take is "
            "lost), and "
            + (
                "leave the worker flags off."
                if args.no_workers
                else "enable the demo worker flags."
            ),
            file=sys.stderr,
        )
        return 2

    settings = load_settings()
    base_uri = args.database_uri or settings.database_uri
    uri = provision_scratch(base_uri, args.database_name)
    report = asyncio.run(
        load_demo(
            replace(settings, database_uri=uri),
            scenario,
            enable_workers=not args.no_workers,
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )
    _print_report(
        report,
        database_name=args.database_name,
        provider_mode=settings.provider_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
