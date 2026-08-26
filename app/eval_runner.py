"""eval_runner.py — the eval harness runner (eval-harness.md stages 2-3).

Seven verbs (PowerShell, from the repo root):

    python -m app.eval_runner run --scenarios data\\eval\\scenarios\\smoke.jsonl [--judged]
    python -m app.eval_runner drift-validate --corpus data\\eval\\corpora\\drift-fixture.jsonl
    python -m app.eval_runner compare --scenarios ... --arm-a data\\eval\\arms\\haiku.json --arm-b data\\eval\\arms\\sonnet5.json
    python -m app.eval_runner emit-gold --artifact data\\eval\\runs\\run_....json --out data\\eval\\gold\\candidates.jsonl
    python -m app.eval_runner agreement --gold data\\eval\\gold\\candidates.jsonl --artifact data\\eval\\runs\\run_....json
    python -m app.eval_runner judge-gold --gold-in data\\eval\\gold\\constructed.jsonl [--plumbing]
    python -m app.eval_runner ablation --corpus data\\eval\\corpora\\ablation-fixture.jsonl [--plumbing]

`run` replays authored scenarios literally through `SessionRunner` — REPL
parity: `as_of` sets the session attribute, a decay-basis re-freeze is an
authored `scene` event, never magic — on a disposable pid-scoped scratch
database, scores each utterance's membership assertions against the raw
served items (the IDs+scores retrieval echo), reads the judge-free
reconstruction metrics per observed memory through the one service-side
assembly, and writes a run-artifact JSON under `data\\eval\\runs\\`
(gitignored; fork 7 — milestone numbers get quoted into dated doc entries).
Exit 0 = every expected-IDs check passed; 1 = any failed.

`drift-validate` replays a drift corpus (the scenario schema's observe/as_of
subset, same loader — fork 10), jumps the session `--age-days` past the last
authored moment, re-freezes the scene basis at the aged instant, and probes
once with k covering the corpus so every unpinned past-theta item is retold
and drift-checked. Per-item cosine distances arrive through the
`reconstruction.drift_observer` capture seam; the report carries p50/p95/max,
the over-budget count against the agent's resolved `drift_budget_threshold`,
and a self-check against the turn's `drift_refusals` counter (they diverge
only on the blind embed-failure path, which carries no distance). Exit 0 =
every item under budget; 1 = any over. Real provider mode is required — the
construct is real-retelling drift under real embeddings — unless `--plumbing`
runs the mechanics offline in fake mode with the report labeled
`plumbing_only: true` (the stage-3 `--judged` labeling pattern). Exit 2 =
refused mode gate.

Stage 3 (`--judged`, the judge layer): a judged `run` additionally captures
each utterance's prose, judges the fixture-authored selective_forgetting /
abstention items and every reconstructed memory's faithfulness (rubrics +
verdict models: app\\eval_judge.py; providers: app\\providers.py), and
carries the judge's token/USD/latency accounting. A judge failure degrades
PER ITEM (judge_failed) — it never kills a run and never changes the exit
code, which stays structural-checks-only; judged numbers are quotable only
past the agreement bar. The same real-mode gate as drift-validate applies
(`--plumbing` for offline mechanics, report labeled plumbing_only).

`compare` runs the same scenarios through two arm overlays — JSON files whose
`env` block may vary the model roles, the dialogue thinking knob, and prices
(each arm carries its OWN dialogue prices: USD from each model's own counts
at its own rates — token columns are never comparable across models, ruled
2026-07-29) but never the mode, database, keys, or judge. Two pid-scoped
scratch DBs, sequential in-process runs; with `--judged`, paired turns are
prose-judged pairwise with a position-swapped second call (disagreement =>
tie) and the report closes with the Pareto table (accuracy vs
perceived_first_word p50/p95 vs USD/100 turns, non-dominated rows marked).

`emit-gold` projects a judged artifact into blind gold-candidate JSONL
(verdicts stripped; `label: null` for hand-filling); `agreement` joins a
labeled gold file back against an artifact's verdicts and reports raw %
+ Cohen's kappa per category against the quotability bar (default 0.6). Both
are offline file operations — no database, no providers, no mode gate.

`judge-gold` judges gold-shaped rows FRESH (the constructed-truth meta-eval
path, ruled 2026-08-12): rows authored with labels known by construction go
to the judge one at a time, and the artifact-shaped output joins back
through `agreement` — that kappa measures judge DISCRIMINATION on known
cases, the class-balance fix the natural gold set cannot provide when the
system under test rarely fails. A present `label` is never shown to the
judge. prose_pairwise rows are refused (pairwise needs the position-swap
protocol, which only `compare` runs); faithfulness rows must be single-fact
(`...:fact0` item_ids — the artifact item carries the base id so the
agreement fan-out re-derives the row's id). Same real-mode gate as
`run --judged` (`--plumbing` for offline mechanics); no database.

`ablation` (stage 4, ruled 2026-08-12) runs one observe/as_of corpus through
the drift-validate replay core TWICE — two pid-scoped scratch DBs, same
models, same instrument — with arm B's agent config carrying
`reconstruction_gist_constraint: 0.0` (original-anchored retellings run
without the gist block; correction-anchored chains are excluded from the
corpus outright, fork 11). Judge-free: per-item cosine drift rides the
observer seam and gist-precision/fabrication ride the stage-1 metric read.
The report pairs arms on (scenario_id, memory_ref) — memory UUIDs differ
across scratch DBs — and closes with mean paired |delta| beside per-arm
gist-precision and fabrication: R7's deciding data. Exit 0 = every ref
paired and drift-checked in both arms; 1 otherwise; 2 = the mode gate
(real required; `--plumbing` for offline mechanics).

Nothing eval-related persists in Postgres (ruled: no migration); scratch
databases are provisioned and dropped per invocation. Windows: both verbs run
under a SelectorEventLoop (psycopg's async pool cannot run on the default
ProactorEventLoop).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from psycopg_pool import AsyncConnectionPool

from app import db, eval_metrics, reconstruction
from app.config import (
    ENV_DIALOGUE_THINKING,
    ENV_MODEL_DIALOGUE,
    ENV_MODEL_ESCALATION,
    ENV_MODEL_IMPORTANCE,
    ENV_MODEL_RECONSTRUCTION,
    ENV_MODEL_RENDER,
    ENV_MODEL_TYPOLOGY,
    PRICE_ENV_KEYS,
    REPO_ROOT,
    ConfigError,
    Settings,
    agent_knob,
    load_env,
    load_settings,
)
from app.db import build_pool
from app.eval_judge import (
    RUBRICS,
    GoldItem,
    cohen_kappa,
    combine_pairwise,
    gold_line,
    load_gold,
    pareto_non_dominated,
    raw_agreement,
    validate_verdict,
)
from app.eval_scenarios import (
    AsOfStep,
    ContextStep,
    CorrectStep,
    ObserveStep,
    PinStep,
    Scenario,
    SceneStep,
    UtteranceStep,
    assert_corpus_shape,
    check_expected,
    load_scenario_files,
    load_scenarios,
)
from app.load_driver import percentile
from app.providers import (
    JudgeProvider,
    MalformedOutputError,
    Providers,
    ProviderCallError,
    build_judge_provider,
    build_providers,
)
from app.retrieval import RetrievalService
from app.schemas import DialogueTurnResult, IngestResult
from app.scratch_db import drop_scratch, pid_scoped_name, provision_scratch
from app.session import SessionRunner

DEFAULT_RUNS_DIR = REPO_ROOT / "data" / "eval" / "runs"
DEFAULT_PROBE = "Tell me about everything you remember."
METRIC_KEYS = (
    "gist_precision",
    "detail_recall",
    "fabrication_rate",
    "keyword_retention",
)


# ---------------------------------------------------------------------------
# Shared report blocks
# ---------------------------------------------------------------------------


def _latency_block(turns: list[DialogueTurnResult]) -> dict:
    series = {
        "perceived_first_word": [
            t.instrumentation.perceived_first_word_ms for t in turns
        ],
        "turn_total": [t.instrumentation.total_ms for t in turns],
    }
    return {
        name: {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95)}
        for name, values in series.items()
    }


def _cost_totals(
    settings: Settings,
    turns: list[DialogueTurnResult],
    observes: list[IngestResult],
    judge_tokens: tuple[int, int] | None = None,
) -> dict:
    """Run-total tokens per model role; USD only when both prices are set
    (the prices-optional -> None pattern, load_driver shape). `judge_tokens`
    is None on non-judged runs — the judge row is then absent entirely, so
    the no-judged cost block stays byte-identical to stage 2's."""
    prices = settings.prices

    def usd(t_in: int, t_out: int, key_in: str, key_out: str) -> float | None:
        if key_in in prices and key_out in prices:
            return round((t_in * prices[key_in] + t_out * prices[key_out]) / 1e6, 6)
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
        + sum(t.instrumentation.retrieval.reconstruction_embed_tokens for t in turns)
    )
    totals = {
        "dialogue": {
            "input_tokens": dialogue_in,
            "output_tokens": dialogue_out,
            "usd": usd(dialogue_in, dialogue_out, "dialogue_in", "dialogue_out"),
        },
        "write": {
            "input_tokens": write_in,
            "output_tokens": write_out,
            "usd": usd(write_in, write_out, "write_in", "write_out"),
        },
        "escalation": {
            "input_tokens": esc_in,
            "output_tokens": esc_out,
            "usd": usd(esc_in, esc_out, "escalation_in", "escalation_out"),
        },
        "reconstruction": {
            "input_tokens": recon_in,
            "output_tokens": recon_out,
            "usd": usd(recon_in, recon_out, "reconstruction_in", "reconstruction_out"),
        },
        "embedding": {
            "tokens": embed_tokens,
            "usd": (
                round(embed_tokens * prices["embedding"] / 1e6, 6)
                if "embedding" in prices
                else None
            ),
        },
    }
    if judge_tokens is not None:
        judge_in, judge_out = judge_tokens
        totals["judge"] = {
            "input_tokens": judge_in,
            "output_tokens": judge_out,
            "usd": usd(judge_in, judge_out, "judge_in", "judge_out"),
        }
    return totals


def _models_block(settings: Settings) -> dict:
    """Arm/run provenance (stage 3): the resolved role names + the dialogue
    thinking knob. Without this, two compare arms' artifacts are
    indistinguishable after the fact. Fake mode resolves roles to "" — the
    arm's overlay block carries the provenance there."""
    return {
        "provider_mode": settings.provider_mode,
        "write": settings.model_write,
        "escalation": settings.model_escalation,
        "dialogue": settings.model_dialogue,
        "reconstruction": settings.model_reconstruction,
        "judge": settings.model_judge,
        "dialogue_thinking": settings.dialogue_thinking,
    }


def _metrics_summary(memory_payloads: list[dict]) -> dict:
    """Honest denominators: means over measured values only, with the
    measured/null split stated — a null is never coerced to a number."""
    summary: dict = {}
    for key in METRIC_KEYS:
        values = [m[key] for m in memory_payloads if m.get(key) is not None]
        summary[key] = {
            "mean": round(sum(values) / len(values), 4) if values else None,
            "measured": len(values),
            "null": sum(1 for m in memory_payloads if m.get(key) is None),
        }
    summary["fabricated_entities_total"] = sum(
        len(m.get("fabricated_entities") or []) for m in memory_payloads
    )
    return summary


# ---------------------------------------------------------------------------
# The judged pass (stage 3)
# ---------------------------------------------------------------------------


def _judge_one(
    judge: JudgeProvider,
    category: str,
    template_kwargs: dict,
    *,
    n_facts: int = 0,
) -> dict:
    """One judge call + verdict validation, timed and token-accounted.

    Returns the fragment merged into the item record. Any failure —
    ProviderCallError, MalformedOutputError (tokens still accounted: the
    spend happened), or a verdict-shape ValidationError — degrades to
    judge_failed on this item alone; the run continues."""
    rubric = RUBRICS[category]
    user_content = rubric.user_template.format(**template_kwargs)
    t0 = time.perf_counter()
    fragment: dict = {"rubric_version": rubric.rubric_version}
    try:
        call = judge.judge(
            system_prompt=rubric.system_prompt,
            user_content=user_content,
            category=category,
            n_facts=n_facts,
        )
        verdict = validate_verdict(category, call.payload, n_facts=n_facts)
        fragment.update(
            judge_failed=False,
            verdict=verdict.model_dump(),
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
        )
    except (ProviderCallError, MalformedOutputError, ValueError) as exc:
        fragment.update(
            judge_failed=True,
            error=str(exc),
            input_tokens=getattr(exc, "input_tokens", 0),
            output_tokens=getattr(exc, "output_tokens", 0),
        )
    fragment["judge_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return fragment


async def _judge_utterance_items(
    scenario_id: str, prose_records: list[dict], judge: JudgeProvider
) -> list[dict]:
    """The fixture-authored categories (selective_forgetting / abstention):
    one judge call per utterance carrying a JudgedSpec. Display texts ride on
    the item so emit-gold is a pure artifact projection."""
    items: list[dict] = []
    for record in prose_records:
        spec = record.get("judged")
        if not spec:
            continue
        category = spec["category"]
        template_kwargs = {
            "question": record["utterance"],
            "reply": record["content"],
            "reference": spec["reference"],
        }
        if category == "selective_forgetting":
            template_kwargs["superseded"] = spec.get("superseded") or "(none)"
        else:
            template_kwargs["expected_behavior"] = spec["expected_behavior"]
        fragment = await asyncio.to_thread(_judge_one, judge, category, template_kwargs)
        items.append(
            {
                "item_id": f"{scenario_id}:{record['event_index']}",
                "scenario_id": scenario_id,
                "event_index": record["event_index"],
                "category": category,
                "question": record["utterance"],
                "reply": record["content"],
                "reference": spec["reference"],
                "superseded": spec.get("superseded"),
                "expected_behavior": spec.get("expected_behavior", "answer"),
                "degraded": record["degraded"],
                **fragment,
            }
        )
    return items


async def _judge_faithfulness_items(
    scenario_id: str,
    memory_ids: list[UUID],
    memory_payloads: list[dict],
    pool: AsyncConnectionPool,
    judge: JudgeProvider,
) -> tuple[list[dict], int]:
    """reconstruction_faithfulness: one judge call per RECONSTRUCTED memory
    (live_write_cause == "reconstruction" — the construct; anything else is
    counted skipped, never silently judged). Inputs are assembled from the
    same sources the stage-1 metric read uses (fetch_memory_chain +
    fetch_reconstruction_sources + gist_fact_texts) — but ALL merged-span
    facts go to the judge, with no lemma-measurability filter: that filter is
    a lexical-metric artifact; the judge does semantic support (settle-at-
    build, recorded in the B2 decisions entry)."""
    items: list[dict] = []
    skipped = 0
    for ref, memory_id in enumerate(memory_ids):
        if memory_payloads[ref].get("live_write_cause") != "reconstruction":
            skipped += 1
            continue
        chain = await db.fetch_memory_chain(pool, memory_id)
        source = (await db.fetch_reconstruction_sources(pool, [memory_id])).get(
            memory_id
        )
        spans = (
            source.spans
            if source
            else [(s["start_char"], s["end_char"]) for s in chain["gist_spans"]]
        )
        anchor_cause = source.anchor_cause if source else None
        anchor_content = source.anchor_content if source else ""
        facts = eval_metrics.gist_fact_texts(
            chain["observation_text"], spans, anchor_cause, anchor_content
        )
        live = next((d for d in chain["details"] if d["is_live"]), None)
        if not facts or live is None:
            skipped += 1
            continue
        telling = live["content"]
        facts_block = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
        fragment = await asyncio.to_thread(
            _judge_one,
            judge,
            "reconstruction_faithfulness",
            {"telling": telling, "facts": facts_block},
            n_facts=len(facts),
        )
        items.append(
            {
                "item_id": f"{scenario_id}:mem{ref}",
                "scenario_id": scenario_id,
                "memory_ref": ref,
                "category": "reconstruction_faithfulness",
                "facts": facts,
                "telling": telling,
                **fragment,
            }
        )
    return items, skipped


def _judged_summary(items: list[dict]) -> dict:
    """Per-category aggregates with honest-None rates (only categories that
    produced items appear — a zero-item category has no rate to state)."""
    summary: dict = {}
    for category in ("selective_forgetting", "abstention"):
        rows = [i for i in items if i["category"] == category]
        if not rows:
            continue
        ok = [i for i in rows if not i["judge_failed"]]
        passed = sum(1 for i in ok if i["verdict"]["verdict"] == "pass")
        summary[category] = {
            "items": len(rows),
            "judge_failed": len(rows) - len(ok),
            "passed": passed,
            "failed": len(ok) - passed,
            "pass_rate": round(passed / len(ok), 4) if ok else None,
        }
    rf = [i for i in items if i["category"] == "reconstruction_faithfulness"]
    if rf:
        ok = [i for i in rf if not i["judge_failed"]]
        facts_total = sum(len(i["facts"]) for i in ok)
        supported = sum(
            sum(1 for flag in i["verdict"]["gist_supported"] if flag) for i in ok
        )
        summary["reconstruction_faithfulness"] = {
            "items": len(rf),
            "judge_failed": len(rf) - len(ok),
            "facts_total": facts_total,
            "facts_supported": supported,
            "support_rate": round(supported / facts_total, 4) if facts_total else None,
            "fabricated_claims_total": sum(
                len(i["verdict"]["fabricated_claims"]) for i in ok
            ),
        }
    return summary


def _write_artifact(report: dict, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out


def _default_artifact_path(verb: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_RUNS_DIR / f"{verb}_{stamp}_{pid_scoped_name('pid')}.json"


# ---------------------------------------------------------------------------
# The `run` verb
# ---------------------------------------------------------------------------


async def _run_one_scenario(
    scenario: Scenario,
    *,
    pool: AsyncConnectionPool,
    providers: Providers,
    settings: Settings,
    retrieval: RetrievalService,
    k: int | None,
    all_turns: list[DialogueTurnResult],
    all_observes: list[IngestResult],
    judge: JudgeProvider | None = None,
    capture_prose: bool = False,
) -> dict:
    agent_id = await db.insert_agent(
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
        providers=providers,
        pool=pool,
        phase_tag="eval-runner",
        warm_nlp=any(isinstance(e, ObserveStep) for e in scenario.events),
    )
    memory_ids: list[UUID] = []
    checks: list[dict] = []
    prose_records: list[dict] = []
    turns = 0
    degraded = 0
    event_counts: dict[str, int] = {}
    for index, event in enumerate(scenario.events):
        event_counts[event.kind] = event_counts.get(event.kind, 0) + 1
        if isinstance(event, ObserveStep):
            ingest = await runner.observe(event.text)
            memory_ids.append(ingest.memory_id)
            all_observes.append(ingest)
        elif isinstance(event, UtteranceStep):
            result = await runner.utterance(
                event.text, k=event.k if event.k is not None else k
            )
            all_turns.append(result)
            turns += 1
            if result.instrumentation.degraded:
                degraded += 1
            if capture_prose:
                prose_records.append(
                    {
                        "event_index": index,
                        "utterance": event.text,
                        "content": result.content,
                        "degraded": result.instrumentation.degraded,
                        "judged": (event.judged.model_dump() if event.judged else None),
                    }
                )
            if event.expect is not None:
                outcome = check_expected(
                    event.expect,
                    [item.memory_id for item in result.items],
                    memory_ids,
                )
                checks.append({"event_index": index, **outcome})
        elif isinstance(event, SceneStep):
            await runner.scene(event.scene_type)
        elif isinstance(event, CorrectStep):
            await runner.correct(memory_ids[event.memory_ref], event.content)
        elif isinstance(event, PinStep):
            await runner.pin(memory_ids[event.memory_ref], event.pinned)
        elif isinstance(event, AsOfStep):
            runner.as_of = event.at
        elif isinstance(event, ContextStep):
            runner.context_location = event.location
            runner.context_entities = event.entities
            runner.context_event_time = event.event_time
    await runner.close()

    memories: list[dict] = []
    for ref, memory_id in enumerate(memory_ids):
        metrics = await retrieval.reconstruction_metrics(memory_id)
        memories.append({"memory_ref": ref, **metrics.model_dump(mode="json")})
    failed = sum(1 for c in checks if not c["passed"])
    report = {
        "scenario_id": scenario.scenario_id,
        "held_out": scenario.held_out,
        "agent_id": str(agent_id),
        "event_counts": event_counts,
        "checks": checks,
        "checks_passed": len(checks) - failed,
        "checks_failed": failed,
        "turns": turns,
        "degraded_turns": degraded,
        "memories": memories,
    }
    if capture_prose:
        report["prose"] = prose_records
    if judge is not None:
        utterance_items = await _judge_utterance_items(
            scenario.scenario_id, prose_records, judge
        )
        faith_items, skipped = await _judge_faithfulness_items(
            scenario.scenario_id, memory_ids, memories, pool, judge
        )
        report["judged_items"] = utterance_items + faith_items
        report["judged_skipped_not_reconstructed"] = skipped
    return report


async def run_scenarios(
    settings: Settings,
    scenarios: list[Scenario],
    *,
    include_held_out: bool,
    k: int | None,
    judged: bool = False,
    judge: JudgeProvider | None = None,
) -> dict:
    """The `run` core, separable so the suite can drive it in-process on an
    injected scratch Settings (the load_driver `run_driver` shape). With
    `judged`, prose is captured and the judge pass runs; the defaults keep
    every pre-stage-3 call site (and its artifact) byte-untouched."""
    included = [s for s in scenarios if include_held_out or not s.held_out]
    excluded = [s.scenario_id for s in scenarios if not include_held_out and s.held_out]
    if judged and judge is None:
        judge = build_judge_provider(settings)
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    providers = build_providers(settings)
    retrieval = RetrievalService(pool, providers, settings)
    all_turns: list[DialogueTurnResult] = []
    all_observes: list[IngestResult] = []
    scenario_reports: list[dict] = []
    started = datetime.now(timezone.utc)
    try:
        for scenario in included:
            scenario_reports.append(
                await _run_one_scenario(
                    scenario,
                    pool=pool,
                    providers=providers,
                    settings=settings,
                    retrieval=retrieval,
                    k=k,
                    all_turns=all_turns,
                    all_observes=all_observes,
                    judge=judge if judged else None,
                    capture_prose=judged,
                )
            )
    finally:
        await pool.close()
    memory_payloads = [m for report in scenario_reports for m in report["memories"]]
    judged_items = [
        item for r in scenario_reports for item in r.get("judged_items", [])
    ]
    judge_tokens: tuple[int, int] | None = None
    if judged:
        judge_tokens = (
            sum(i["input_tokens"] for i in judged_items),
            sum(i["output_tokens"] for i in judged_items),
        )
    report = {
        "verb": "run",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": settings.provider_mode,
        "models": _models_block(settings),
        "excluded_held_out": excluded,
        "scenarios": scenario_reports,
        "turns": len(all_turns),
        "observes": len(all_observes),
        "degraded_turns": sum(1 for t in all_turns if t.instrumentation.degraded),
        "write_backs": sum(t.instrumentation.retrieval.write_backs for t in all_turns),
        "drift_refusals": sum(
            t.instrumentation.retrieval.drift_refusals for t in all_turns
        ),
        "cache_hits": sum(t.instrumentation.retrieval.cache_hits for t in all_turns),
        "metrics_summary": _metrics_summary(memory_payloads),
        "latency_ms": _latency_block(all_turns),
        "cost": _cost_totals(settings, all_turns, all_observes, judge_tokens),
        "checks_passed_total": sum(r["checks_passed"] for r in scenario_reports),
        "checks_failed_total": sum(r["checks_failed"] for r in scenario_reports),
    }
    if judged:
        report["plumbing_only"] = settings.provider_mode != "real"
        report["judged"] = {
            "rubric_versions": {
                category: RUBRICS[category].rubric_version
                for category in (
                    "selective_forgetting",
                    "abstention",
                    "reconstruction_faithfulness",
                )
            },
            "summary": _judged_summary(judged_items),
            "items": judged_items,
            "skipped_not_reconstructed": sum(
                r.get("judged_skipped_not_reconstructed", 0) for r in scenario_reports
            ),
            "judge_ms_total": round(sum(i["judge_ms"] for i in judged_items), 2),
        }
    return report


def _print_run_report(report: dict) -> None:
    print(
        f"\neval run — {len(report['scenarios'])} scenario(s), "
        f"{report['turns']} turns, {report['observes']} observes, "
        f"{report['degraded_turns']} degraded "
        f"(provider mode: {report['provider_mode']})"
    )
    if report["excluded_held_out"]:
        print("held-out excluded by default: " + ", ".join(report["excluded_held_out"]))
    print(
        f"reconstruction: {report['write_backs']} write-backs, "
        f"{report['cache_hits']} cache hits, "
        f"{report['drift_refusals']} drift refusals"
    )

    def fmt(block: dict) -> str:
        mean = block["mean"]
        shown = f"{mean:.3f}" if mean is not None else "(null)"
        return f"{shown} ({block['measured']} measured/{block['null']} null)"

    print("\nscenario                     checks   gist_p   detail_r")
    for row in report["scenarios"]:
        summary = _metrics_summary(row["memories"])
        gist = summary["gist_precision"]["mean"]
        detail = summary["detail_recall"]["mean"]
        print(
            f"  {row['scenario_id']:<26} "
            f"{row['checks_passed']}/{row['checks_passed'] + row['checks_failed']:<6} "
            f"{gist if gist is not None else '(null)':>7}  "
            f"{detail if detail is not None else '(null)':>8}"
        )
    summary = report["metrics_summary"]
    print("\nrun metrics (honest denominators):")
    for key in METRIC_KEYS:
        print(f"  {key:<22} {fmt(summary[key])}")
    print(f"  fabricated entities    {summary['fabricated_entities_total']}")
    print("\nlatency (ms)                p50        p95")
    for name, row in report["latency_ms"].items():
        print(f"  {name:<24} {row['p50']:>8}   {row['p95']:>8}")
    print("\nrun-total cost              tokens (in/out)        USD")
    for role, row in report["cost"].items():
        if role == "embedding":
            tokens = f"{row['tokens']}"
        else:
            tokens = f"{row['input_tokens']}/{row['output_tokens']}"
        usd_val = row["usd"]
        usd_text = f"${usd_val}" if usd_val is not None else "(unpriced)"
        print(f"  {role:<24} {tokens:>20}   {usd_text}")
    print(
        f"\nchecks: {report['checks_passed_total']} passed, "
        f"{report['checks_failed_total']} failed"
    )
    if "judged" in report:
        _print_judged_block(report)


def _print_judged_block(report: dict) -> None:
    judged = report["judged"]
    label = " [PLUMBING ONLY — fake providers]" if report.get("plumbing_only") else ""
    print(f"\njudged ({judged['judge_ms_total']} ms total judge time){label}:")
    for category, block in judged["summary"].items():
        if category == "reconstruction_faithfulness":
            rate = block["support_rate"]
            print(
                f"  {category:<28} {block['facts_supported']}/"
                f"{block['facts_total']} facts supported "
                f"({rate if rate is not None else '(null)'}), "
                f"{block['fabricated_claims_total']} fabricated claim(s), "
                f"{block['judge_failed']} judge_failed"
            )
        else:
            rate = block["pass_rate"]
            print(
                f"  {category:<28} {block['passed']}/"
                f"{block['passed'] + block['failed']} pass "
                f"({rate if rate is not None else '(null)'}), "
                f"{block['judge_failed']} judge_failed"
            )
    if judged["skipped_not_reconstructed"]:
        print(
            f"  (faithfulness skipped {judged['skipped_not_reconstructed']} "
            "memory(ies) never reconstructed)"
        )


_JUDGED_GATE_MESSAGE = (
    "judged runs require real provider mode — judged signal is only "
    "meaningful on real prose. Pass --plumbing to exercise the mechanics "
    "offline in fake mode (report labeled plumbing_only)."
)


def _cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    judge = None
    if args.plumbing and not args.judged:
        print("--plumbing only applies to --judged runs.", file=sys.stderr)
        return 2
    if args.judged:
        if settings.provider_mode != "real" and not args.plumbing:
            print(_JUDGED_GATE_MESSAGE, file=sys.stderr)
            return 2
        try:
            judge = build_judge_provider(settings)
        except ConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    base_uri = args.database_uri or settings.database_uri
    scenarios = load_scenario_files(args.scenarios)
    name = args.database_name or pid_scoped_name("longmem_eval")
    uri = provision_scratch(base_uri, name)
    try:
        report = asyncio.run(
            run_scenarios(
                replace(settings, database_uri=uri),
                scenarios,
                include_held_out=args.include_held_out,
                k=args.k,
                judged=args.judged,
                judge=judge,
            ),
            loop_factory=asyncio.SelectorEventLoop,
        )
    finally:
        if args.keep_db:
            print(f"scratch database kept: {name}")
        else:
            drop_scratch(base_uri, name)
    report["scenario_files"] = [str(p) for p in args.scenarios]
    report["database_name"] = name
    _print_run_report(report)
    out = _write_artifact(report, args.out or _default_artifact_path("run"))
    print(f"\nrun artifact: {out}")
    return 0 if report["checks_failed_total"] == 0 else 1


# ---------------------------------------------------------------------------
# The `drift-validate` verb
# ---------------------------------------------------------------------------


async def replay_aged_probe(
    pool: AsyncConnectionPool,
    providers: Providers,
    settings: Settings,
    scenario: Scenario,
    *,
    age_days: float,
    probe: str,
    max_items: int | None,
    fallback_start: datetime,
) -> dict:
    """The drift-validate / ablation shared core (extracted for stage 4,
    2026-08-12 — behavior byte-identical to the pre-extraction loop): replay
    one corpus scenario's observes, age the session past the last authored
    moment, re-freeze the basis, and probe once with the capture seam
    attached. Returns agent_id, memory_ids, the ingests, the probe turn, and
    the observer samples; the caller shapes its own report."""
    agent_id = await db.insert_agent(
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
        providers=providers,
        pool=pool,
        phase_tag="eval-runner",
        warm_nlp=True,
    )
    memory_ids: list[UUID] = []
    observes: list[IngestResult] = []
    for event in scenario.events:
        if isinstance(event, ObserveStep):
            ingest = await runner.observe(event.text)
            memory_ids.append(ingest.memory_id)
            observes.append(ingest)
        else:  # AsOfStep — assert_corpus_shape admits nothing else
            runner.as_of = event.at
    last = runner.as_of if runner.as_of is not None else fallback_start
    runner.as_of = last + timedelta(days=age_days)
    await runner.scene()  # re-freeze the decay/theta basis, aged

    samples: list[tuple[UUID, float, bool]] = []

    def observer(
        memory_id: UUID,
        distance: float,
        refused: bool,
        _samples: list = samples,
    ) -> None:
        _samples.append((memory_id, distance, refused))

    k = len(memory_ids) if max_items is None else min(len(memory_ids), max_items)
    reconstruction.drift_observer = observer
    try:
        turn = await runner.utterance(probe, k=k)
    finally:
        reconstruction.drift_observer = None
    await runner.close()
    return {
        "agent_id": agent_id,
        "memory_ids": memory_ids,
        "observes": observes,
        "turn": turn,
        "samples": samples,
    }


async def drift_validate(
    settings: Settings,
    corpus: list[Scenario],
    *,
    age_days: float,
    probe: str,
    max_items: int | None,
) -> dict:
    """The `drift-validate` core: replay each corpus scenario's observes,
    age the session past the last authored moment, re-freeze the basis, and
    probe once with the capture seam attached."""
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    providers = build_providers(settings)
    all_turns: list[DialogueTurnResult] = []
    all_observes: list[IngestResult] = []
    scenario_reports: list[dict] = []
    started = datetime.now(timezone.utc)
    try:
        for scenario in corpus:
            replay = await replay_aged_probe(
                pool,
                providers,
                settings,
                scenario,
                age_days=age_days,
                probe=probe,
                max_items=max_items,
                fallback_start=started,
            )
            agent_id = replay["agent_id"]
            memory_ids = replay["memory_ids"]
            samples = replay["samples"]
            all_observes.extend(replay["observes"])
            all_turns.append(replay["turn"])
            turn = replay["turn"]

            threshold = agent_knob(
                scenario.agent.config, "drift_budget_threshold", settings
            )
            ref_by_id = {mid: ref for ref, mid in enumerate(memory_ids)}
            items = sorted(
                (
                    {
                        "memory_ref": ref_by_id.get(memory_id),
                        "memory_id": str(memory_id),
                        "distance": round(distance, 6),
                        "over_budget": refused,
                    }
                    for memory_id, distance, refused in samples
                ),
                key=lambda row: -row["distance"],
            )
            observer_over = sum(1 for _, _, refused in samples if refused)
            turn_refusals = turn.instrumentation.retrieval.drift_refusals
            scenario_reports.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "agent_id": str(agent_id),
                    "observes": len(memory_ids),
                    "items_checked": len(samples),
                    "over_budget_count": observer_over,
                    "threshold": threshold,
                    "items": items,
                    # Equal unless an embed call failed blind — that refusal
                    # path carries no distance and never reaches the observer.
                    "self_check": {
                        "turn_drift_refusals": turn_refusals,
                        "observer_over_budget": observer_over,
                        "match": turn_refusals == observer_over,
                    },
                }
            )
    finally:
        await pool.close()

    distances = [
        row["distance"] for report in scenario_reports for row in report["items"]
    ]
    return {
        "verb": "drift-validate",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": settings.provider_mode,
        "age_days": age_days,
        "probe": probe,
        "scenarios": scenario_reports,
        "items_checked_total": len(distances),
        "over_budget_count": sum(
            report["over_budget_count"] for report in scenario_reports
        ),
        "distance": {
            "p50": percentile(distances, 0.5),
            "p95": percentile(distances, 0.95),
            "max": max(distances) if distances else None,
        },
        "latency_ms": _latency_block(all_turns),
        "cost": _cost_totals(settings, all_turns, all_observes),
    }


def _print_drift_report(report: dict) -> None:
    plumbing = " [PLUMBING ONLY — fake providers]" if report["plumbing_only"] else ""
    print(
        f"\ndrift-validate — {report['items_checked_total']} item(s) checked, "
        f"{report['over_budget_count']} over budget{plumbing}"
    )
    dist = report["distance"]
    print(
        f"distance: p50 {dist['p50']}  p95 {dist['p95']}  "
        f"max {dist['max'] if dist['max'] is not None else '(none checked)'}"
    )
    for scenario in report["scenarios"]:
        check = scenario["self_check"]
        match_text = (
            "matches"
            if check["match"]
            else (
                f"DIVERGES (turn counted {check['turn_drift_refusals']} — "
                "a blind embed-failure refusal carries no distance)"
            )
        )
        print(
            f"\n  {scenario['scenario_id']} — {scenario['items_checked']}/"
            f"{scenario['observes']} items checked, threshold "
            f"{scenario['threshold']}, drift_refusals self-check: {match_text}"
        )
        for row in scenario["items"][:20]:
            flag = "OVER" if row["over_budget"] else "  ok"
            print(
                f"    {flag}  ref {row['memory_ref']}  "
                f"distance {row['distance']:.4f}  {row['memory_id']}"
            )
        if len(scenario["items"]) > 20:
            print(f"    … {len(scenario['items']) - 20} more (see artifact)")


def _cmd_drift_validate(args: argparse.Namespace) -> int:
    settings = load_settings()
    if settings.provider_mode != "real" and not args.plumbing:
        print(
            "drift-validate requires real provider mode — the construct is "
            "real-retelling drift under real embeddings. Pass --plumbing to "
            "run the mechanics offline in fake mode (report labeled "
            "plumbing_only).",
            file=sys.stderr,
        )
        return 2
    corpus = load_scenarios(args.corpus)
    for scenario in corpus:
        assert_corpus_shape(scenario)
    base_uri = args.database_uri or settings.database_uri
    name = args.database_name or pid_scoped_name("longmem_eval")
    uri = provision_scratch(base_uri, name)
    try:
        report = asyncio.run(
            drift_validate(
                replace(settings, database_uri=uri),
                corpus,
                age_days=args.age_days,
                probe=args.probe,
                max_items=args.max_items,
            ),
            loop_factory=asyncio.SelectorEventLoop,
        )
    finally:
        if args.keep_db:
            print(f"scratch database kept: {name}")
        else:
            drop_scratch(base_uri, name)
    report["corpus"] = str(args.corpus)
    report["database_name"] = name
    report["plumbing_only"] = settings.provider_mode != "real"
    _print_drift_report(report)
    if args.out is not None:
        print(f"\ndrift artifact: {_write_artifact(report, args.out)}")
    return 0 if report["over_budget_count"] == 0 else 1


# ---------------------------------------------------------------------------
# The `ablation` verb (stage 4, ruled 2026-08-12): fixed-gist ON vs OFF over
# the same corpus on two scratch DBs — R7's deciding data. Judge-free by
# design: per-item drift rides the observer seam, gist-precision/fabrication
# ride the stage-1 metric read. Correction-anchored chains are excluded from
# the corpus outright (fork 11 + assert_corpus_shape admits no `correct`
# events).
# ---------------------------------------------------------------------------


def _knob_off_scenario(scenario: Scenario) -> Scenario:
    """The OFF arm's copy: the agent config carries the 0 knob — persisted by
    insert_agent, read back inside reconstruction.serve(); no runner
    signature changes anywhere (the stage-4 contract's kill-switch shape)."""
    agent = scenario.agent.model_copy(
        update={
            "config": {
                **scenario.agent.config,
                "reconstruction_gist_constraint": 0.0,
            }
        }
    )
    return scenario.model_copy(update={"agent": agent})


async def _ablation_arm(
    settings: Settings,
    corpus: list[Scenario],
    *,
    arm_name: str,
    knob_off: bool,
    age_days: float,
    probe: str,
) -> dict:
    """One arm: the drift-validate replay core per scenario, then the
    judge-free metric read per observed memory."""
    pool = build_pool(settings.database_uri, max_size=settings.db_pool_max_size)
    await pool.open()
    providers = build_providers(settings)
    retrieval = RetrievalService(pool, providers, settings)
    all_turns: list[DialogueTurnResult] = []
    all_observes: list[IngestResult] = []
    scenario_blocks: list[dict] = []
    started = datetime.now(timezone.utc)
    try:
        for authored in corpus:
            scenario = _knob_off_scenario(authored) if knob_off else authored
            replay = await replay_aged_probe(
                pool,
                providers,
                settings,
                scenario,
                age_days=age_days,
                probe=probe,
                max_items=None,
                fallback_start=started,
            )
            all_turns.append(replay["turn"])
            all_observes.extend(replay["observes"])
            by_id: dict[UUID, tuple[float, bool]] = {
                memory_id: (distance, refused)
                for memory_id, distance, refused in replay["samples"]
            }
            items: list[dict] = []
            for ref, memory_id in enumerate(replay["memory_ids"]):
                metrics = await retrieval.reconstruction_metrics(memory_id)
                sample = by_id.get(memory_id)
                items.append(
                    {
                        "memory_ref": ref,
                        "memory_id": str(memory_id),
                        "distance": (
                            round(sample[0], 6) if sample is not None else None
                        ),
                        "over_budget": sample[1] if sample is not None else None,
                        "reconstructed": (metrics.live_write_cause == "reconstruction"),
                        "cache_bands": metrics.cache_bands,
                        "band": (
                            metrics.cache_bands[0]
                            if len(metrics.cache_bands) == 1
                            else None
                        ),
                        "gist_precision": metrics.gist_precision,
                        "fabrication_rate": metrics.fabrication_rate,
                        "fabricated_entities": metrics.fabricated_entities,
                        "live_write_cause": metrics.live_write_cause,
                    }
                )
            scenario_blocks.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "agent_id": str(replay["agent_id"]),
                    "observes": len(replay["memory_ids"]),
                    "items_checked": len(replay["samples"]),
                    "items": items,
                }
            )
    finally:
        await pool.close()
    distances = [
        item["distance"]
        for block in scenario_blocks
        for item in block["items"]
        if item["distance"] is not None
    ]
    return {
        "name": arm_name,
        "knob": {"reconstruction_gist_constraint": 0.0 if knob_off else 1.0},
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": scenario_blocks,
        "items_checked_total": len(distances),
        "over_budget_count": sum(
            1
            for block in scenario_blocks
            for item in block["items"]
            if item["over_budget"]
        ),
        "distance": {
            "p50": percentile(distances, 0.5),
            "p95": percentile(distances, 0.95),
            "max": max(distances) if distances else None,
        },
        "latency_ms": _latency_block(all_turns),
        "cost": _cost_totals(settings, all_turns, all_observes),
    }


def _ablation_pairs(arm_on: dict, arm_off: dict) -> tuple[list[dict], int]:
    """Pair the arms on (scenario_id, memory_ref) — memory UUIDs differ
    across scratch DBs, so both are carried as provenance, never as the
    join key (the stage-4 contract's `memory_id` read the only way it can
    work)."""
    index_off = {
        (block["scenario_id"], item["memory_ref"]): item
        for block in arm_off["scenarios"]
        for item in block["items"]
    }
    paired: list[dict] = []
    unpaired_refs = 0
    for block in arm_on["scenarios"]:
        for item_on in block["items"]:
            item_off = index_off.get((block["scenario_id"], item_on["memory_ref"]))
            if item_off is None:
                unpaired_refs += 1
                continue
            both = item_on["distance"] is not None and item_off["distance"] is not None
            paired.append(
                {
                    "scenario_id": block["scenario_id"],
                    "memory_ref": item_on["memory_ref"],
                    "memory_id_on": item_on["memory_id"],
                    "memory_id_off": item_off["memory_id"],
                    "band_on": item_on["band"],
                    "band_off": item_off["band"],
                    "distance_on": item_on["distance"],
                    "distance_off": item_off["distance"],
                    "delta_abs": (
                        round(abs(item_on["distance"] - item_off["distance"]), 6)
                        if both
                        else None
                    ),
                    "over_budget_on": item_on["over_budget"],
                    "over_budget_off": item_off["over_budget"],
                    "reconstructed_on": item_on["reconstructed"],
                    "reconstructed_off": item_off["reconstructed"],
                    "gist_precision_on": item_on["gist_precision"],
                    "gist_precision_off": item_off["gist_precision"],
                    "fabrication_rate_on": item_on["fabrication_rate"],
                    "fabrication_rate_off": item_off["fabrication_rate"],
                }
            )
    return paired, unpaired_refs


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _ablation_summary(paired: list[dict]) -> dict:
    """Honest-None aggregates over the paired rows (the harness principle)."""
    checked = [row for row in paired if row["delta_abs"] is not None]
    return {
        "n_paired": len(paired),
        "n_checked_both": len(checked),
        "mean_abs_delta": _mean([row["delta_abs"] for row in checked]),
        "band_mismatches": sum(
            1 for row in paired if row["band_on"] != row["band_off"]
        ),
        "over_budget_on": sum(1 for row in paired if row["over_budget_on"]),
        "over_budget_off": sum(1 for row in paired if row["over_budget_off"]),
        "gist_precision_mean_on": _mean(
            [
                row["gist_precision_on"]
                for row in paired
                if row["gist_precision_on"] is not None
            ]
        ),
        "gist_precision_mean_off": _mean(
            [
                row["gist_precision_off"]
                for row in paired
                if row["gist_precision_off"] is not None
            ]
        ),
        "fabrication_rate_mean_on": _mean(
            [
                row["fabrication_rate_on"]
                for row in paired
                if row["fabrication_rate_on"] is not None
            ]
        ),
        "fabrication_rate_mean_off": _mean(
            [
                row["fabrication_rate_off"]
                for row in paired
                if row["fabrication_rate_off"] is not None
            ]
        ),
    }


async def ablation_run(
    settings_on: Settings,
    settings_off: Settings,
    corpus: list[Scenario],
    *,
    age_days: float,
    probe: str,
) -> dict:
    """The two-arm rig, sequential in-process (the compare shape): same
    corpus, same models, same instrument — only the knob differs."""
    arm_on = await _ablation_arm(
        settings_on,
        corpus,
        arm_name="gist-on",
        knob_off=False,
        age_days=age_days,
        probe=probe,
    )
    arm_off = await _ablation_arm(
        settings_off,
        corpus,
        arm_name="gist-off",
        knob_off=True,
        age_days=age_days,
        probe=probe,
    )
    paired, unpaired_refs = _ablation_pairs(arm_on, arm_off)
    summary = _ablation_summary(paired)
    summary["unpaired_refs"] = unpaired_refs
    summary["pairs_missing_a_distance"] = (
        summary["n_paired"] - summary["n_checked_both"]
    )
    return {
        "verb": "ablation",
        "started_at": arm_on["started_at"],
        "finished_at": arm_off["finished_at"],
        "provider_mode": settings_on.provider_mode,
        "age_days": age_days,
        "probe": probe,
        "models": _models_block(settings_on),
        "arms": [arm_on, arm_off],
        "paired": paired,
        "paired_summary": summary,
        "plumbing_only": settings_on.provider_mode != "real",
    }


def _print_ablation_report(report: dict) -> None:
    plumbing = " [PLUMBING ONLY — fake providers]" if report["plumbing_only"] else ""
    summary = report["paired_summary"]
    print(
        f"\nablation — {summary['n_paired']} paired item(s), "
        f"{summary['n_checked_both']} drift-checked in both arms{plumbing}"
    )
    for arm in report["arms"]:
        dist = arm["distance"]
        print(
            f"  {arm['name']:<9} distance p50 {dist['p50']}  p95 {dist['p95']}  "
            f"max {dist['max']}  over-budget {arm['over_budget_count']}"
        )
    print(
        f"  mean paired |delta| {summary['mean_abs_delta']}  "
        f"band mismatches {summary['band_mismatches']}"
    )
    print(
        f"  gist-precision mean on {summary['gist_precision_mean_on']} / "
        f"off {summary['gist_precision_mean_off']}  "
        f"fabrication mean on {summary['fabrication_rate_mean_on']} / "
        f"off {summary['fabrication_rate_mean_off']}"
    )
    if summary["unpaired_refs"] or summary["pairs_missing_a_distance"]:
        print(
            f"  ({summary['unpaired_refs']} unpaired ref(s), "
            f"{summary['pairs_missing_a_distance']} pair(s) missing a "
            "distance — investigate before quoting)"
        )


def _cmd_ablation(args: argparse.Namespace) -> int:
    settings = load_settings()
    if settings.provider_mode != "real" and not args.plumbing:
        print(
            "ablation requires real provider mode — the construct is real "
            "retellings with and without the gist constraint. Pass "
            "--plumbing to run the mechanics offline in fake mode (report "
            "labeled plumbing_only).",
            file=sys.stderr,
        )
        return 2
    corpus = load_scenarios(args.corpus)
    for scenario in corpus:
        assert_corpus_shape(scenario)
    base_uri = args.database_uri or settings.database_uri
    name_on = pid_scoped_name("longmem_eval_abl_on")
    name_off = pid_scoped_name("longmem_eval_abl_off")
    uri_on = provision_scratch(base_uri, name_on)
    uri_off = provision_scratch(base_uri, name_off)
    try:
        report = asyncio.run(
            ablation_run(
                replace(settings, database_uri=uri_on),
                replace(settings, database_uri=uri_off),
                corpus,
                age_days=args.age_days,
                probe=args.probe,
            ),
            loop_factory=asyncio.SelectorEventLoop,
        )
    finally:
        if args.keep_db:
            print(f"scratch databases kept: {name_on}, {name_off}")
        else:
            drop_scratch(base_uri, name_on)
            drop_scratch(base_uri, name_off)
    report["corpus"] = str(args.corpus)
    report["database_names"] = [name_on, name_off]
    _print_ablation_report(report)
    out = _write_artifact(report, args.out or _default_artifact_path("ablation"))
    print(f"ablation artifact: {out}")
    summary = report["paired_summary"]
    complete = (
        summary["unpaired_refs"] == 0 and summary["pairs_missing_a_distance"] == 0
    )
    return 0 if complete else 1


# ---------------------------------------------------------------------------
# The `compare` verb (stage 3)
# ---------------------------------------------------------------------------

# An arm overlay may vary the SYSTEM UNDER TEST — model roles, the dialogue
# thinking knob, and prices (each arm carries its own dialogue prices; USD
# from each model's own counts at its own rates) — never the mode, database,
# API keys, or the judge (the instrument must not vary between arms).
_ARM_ALLOWED_KEYS = frozenset(
    {
        ENV_MODEL_IMPORTANCE,
        ENV_MODEL_RENDER,
        ENV_MODEL_TYPOLOGY,
        ENV_MODEL_ESCALATION,
        ENV_MODEL_DIALOGUE,
        ENV_MODEL_RECONSTRUCTION,
        ENV_DIALOGUE_THINKING,
    }
) | frozenset(PRICE_ENV_KEYS)


def _load_arm(path: Path, base_env: dict[str, str]) -> dict:
    """Parse one arm JSON file ({"name": ..., "env": {...}}) and resolve its
    Settings by merging the overlay over the base env — load_settings reuses
    every validation (role agreement, price parse, thinking values) for free."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{path}: arm file needs a non-empty string 'name'")
    overlay = payload.get("env", {})
    if not isinstance(overlay, dict):
        raise ValueError(f"{path}: arm 'env' must be an object of env overrides")
    unknown = set(overlay) - _ARM_ALLOWED_KEYS
    if unknown:
        raise ValueError(
            f"{path}: arm overlay key(s) not allowed: {sorted(unknown)} — an "
            "arm varies the system under test (model roles, dialogue "
            "thinking, prices), never the mode, database, keys, or judge"
        )
    overlay = {key: str(value) for key, value in overlay.items()}
    settings = load_settings({**base_env, **overlay})
    return {"name": name, "overlay": overlay, "settings": settings}


async def _judge_pairwise_items(
    report_a: dict, report_b: dict, judge: JudgeProvider
) -> list[dict]:
    """Prose judged pairwise across arms: per paired turn, one call in true
    order plus one position-swapped, combined with disagreement => tie."""

    def prose_index(report: dict) -> dict[tuple[str, int], dict]:
        return {
            (s["scenario_id"], p["event_index"]): p
            for s in report["scenarios"]
            for p in s.get("prose", [])
        }

    index_b = prose_index(report_b)
    rubric = RUBRICS["prose_pairwise"]
    items: list[dict] = []
    for scenario in report_a["scenarios"]:
        for record_a in scenario.get("prose", []):
            key = (scenario["scenario_id"], record_a["event_index"])
            record_b = index_b.get(key)
            if record_b is None:
                continue

            def call_pair(
                _q: str = record_a["utterance"],
                _a: str = record_a["content"],
                _b: str = record_b["content"],
            ) -> dict:
                fragment: dict = {"rubric_version": rubric.rubric_version}
                tokens_in = tokens_out = 0
                t0 = time.perf_counter()
                try:
                    verdicts = []
                    for reply_a, reply_b in ((_a, _b), (_b, _a)):
                        call = judge.judge(
                            system_prompt=rubric.system_prompt,
                            user_content=rubric.user_template.format(
                                question=_q, reply_a=reply_a, reply_b=reply_b
                            ),
                            category="prose_pairwise",
                        )
                        tokens_in += call.input_tokens
                        tokens_out += call.output_tokens
                        verdicts.append(
                            validate_verdict("prose_pairwise", call.payload)
                        )
                    fragment.update(
                        judge_failed=False,
                        combined=combine_pairwise(verdicts[0], verdicts[1]),
                    )
                except (ProviderCallError, MalformedOutputError, ValueError) as exc:
                    tokens_in += getattr(exc, "input_tokens", 0)
                    tokens_out += getattr(exc, "output_tokens", 0)
                    fragment.update(judge_failed=True, error=str(exc))
                fragment.update(
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                    judge_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                )
                return fragment

            fragment = await asyncio.to_thread(call_pair)
            items.append(
                {
                    "item_id": f"cmp:{key[0]}:{key[1]}",
                    "scenario_id": key[0],
                    "event_index": key[1],
                    "category": "prose_pairwise",
                    "question": record_a["utterance"],
                    "reply_a": record_a["content"],
                    "reply_b": record_b["content"],
                    "degraded_either": record_a["degraded"] or record_b["degraded"],
                    **fragment,
                }
            )
    return items


def _pairwise_summary(items: list[dict]) -> dict:
    ok = [i for i in items if not i["judge_failed"]]
    prefs = [i["combined"]["preference"] for i in ok]
    mean_scores = None
    if ok:
        mean_scores = {
            arm: {
                dim: round(sum(i["combined"][arm][dim] for i in ok) / len(ok), 3)
                for dim in ok[0]["combined"][arm]
            }
            for arm in ("a", "b")
        }
    return {
        "pairs": len(items),
        "judge_failed": len(items) - len(ok),
        "a_wins": prefs.count("a"),
        "b_wins": prefs.count("b"),
        "ties": prefs.count("tie"),
        "positions_agreed": sum(1 for i in ok if i["combined"]["positions_agreed"]),
        "mean_scores": mean_scores,
    }


def _arm_accuracy(report: dict) -> float | None:
    """The Pareto accuracy scalar: macro-mean over the non-None of structural
    check pass rate + the judged per-category rates. Honest-None when nothing
    was measurable."""
    rates: list[float] = []
    checks_total = report["checks_passed_total"] + report["checks_failed_total"]
    if checks_total:
        rates.append(report["checks_passed_total"] / checks_total)
    summary = report.get("judged", {}).get("summary", {})
    for category in ("selective_forgetting", "abstention"):
        block = summary.get(category)
        if block and block["pass_rate"] is not None:
            rates.append(block["pass_rate"])
    rf = summary.get("reconstruction_faithfulness")
    if rf and rf["support_rate"] is not None:
        rates.append(rf["support_rate"])
    if not rates:
        return None
    return round(sum(rates) / len(rates), 4)


def _total_usd(cost: dict) -> float | None:
    """Sum of role USD; None as soon as any role with nonzero spend is
    unpriced (an honest total, never a partial one presented as whole)."""
    total = 0.0
    for role, row in cost.items():
        tokens = (
            row["tokens"]
            if role == "embedding"
            else row["input_tokens"] + row["output_tokens"]
        )
        if row["usd"] is None:
            if tokens:
                return None
            continue
        total += row["usd"]
    return round(total, 6)


def _pareto_row(name: str, report: dict) -> dict:
    turns = report["turns"]
    total_usd = _total_usd(report["cost"])
    latency = report["latency_ms"]["perceived_first_word"]
    return {
        "arm": name,
        "accuracy": _arm_accuracy(report),
        "p50": latency["p50"],
        "p95": latency["p95"],
        "usd_per_100_turns": (
            round(total_usd * 100.0 / turns, 6)
            if total_usd is not None and turns
            else None
        ),
    }


async def compare_scenarios(
    arm_a: dict,
    arm_b: dict,
    scenarios: list[Scenario],
    *,
    include_held_out: bool,
    k: int | None,
    judged: bool,
    judge: JudgeProvider | None,
) -> dict:
    """The `compare` core: both arms sequentially in-process (each on its own
    scratch settings), then the pairwise prose pass and the Pareto table."""
    started = datetime.now(timezone.utc)
    report_a = await run_scenarios(
        arm_a["settings"],
        scenarios,
        include_held_out=include_held_out,
        k=k,
        judged=judged,
        judge=judge,
    )
    report_b = await run_scenarios(
        arm_b["settings"],
        scenarios,
        include_held_out=include_held_out,
        k=k,
        judged=judged,
        judge=judge,
    )
    pairwise = None
    if judged and judge is not None:
        items = await _judge_pairwise_items(report_a, report_b, judge)
        pairwise = {
            "rubric_version": RUBRICS["prose_pairwise"].rubric_version,
            "summary": _pairwise_summary(items),
            "items": items,
            "judge_tokens": {
                "input_tokens": sum(i["input_tokens"] for i in items),
                "output_tokens": sum(i["output_tokens"] for i in items),
            },
        }
    rows = [
        _pareto_row(arm_a["name"], report_a),
        _pareto_row(arm_b["name"], report_b),
    ]
    flags = pareto_non_dominated(rows)
    report = {
        "verb": "compare",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": arm_a["settings"].provider_mode,
        "arms": [
            {"name": arm_a["name"], "overlay": arm_a["overlay"], "report": report_a},
            {"name": arm_b["name"], "overlay": arm_b["overlay"], "report": report_b},
        ],
        "pairwise": pairwise,
        "pareto": [{**row, "non_dominated": flag} for row, flag in zip(rows, flags)],
    }
    if judged:
        report["plumbing_only"] = arm_a["settings"].provider_mode != "real"
    return report


def _print_compare_report(report: dict) -> None:
    plumbing = (
        " [PLUMBING ONLY — fake providers]" if report.get("plumbing_only") else ""
    )
    print(
        f"\ncompare — {report['arms'][0]['name']} vs {report['arms'][1]['name']} "
        f"(provider mode: {report['provider_mode']}){plumbing}"
    )
    for arm in report["arms"]:
        r = arm["report"]
        print(
            f"  {arm['name']:<26} checks {r['checks_passed_total']}/"
            f"{r['checks_passed_total'] + r['checks_failed_total']}, "
            f"{r['turns']} turns, {r['degraded_turns']} degraded"
        )
    pairwise = report.get("pairwise")
    if pairwise:
        s = pairwise["summary"]
        print(
            f"\nprose pairwise ({s['pairs']} pair(s), position-swapped, "
            f"disagreement => tie): A {s['a_wins']}  B {s['b_wins']}  "
            f"tie {s['ties']}  judge_failed {s['judge_failed']}  "
            f"(positions agreed {s['positions_agreed']}/{s['pairs'] - s['judge_failed']})"
        )
        if s["mean_scores"]:
            for arm_key, arm in zip(("a", "b"), report["arms"]):
                dims = s["mean_scores"][arm_key]
                shown = "  ".join(f"{dim} {val}" for dim, val in dims.items())
                print(f"  {arm['name']:<26} {shown}")
    print("\nPareto (accuracy vs perceived_first_word p50/p95 vs USD/100 turns):")
    print(f"  {'arm':<26} {'accuracy':>9} {'p50':>9} {'p95':>9} {'USD/100t':>11}")
    for row in report["pareto"]:

        def show(value, money: bool = False) -> str:
            if value is None:
                return "(null)"
            return f"${value}" if money else f"{value}"

        marker = "  <- frontier" if row["non_dominated"] else ""
        print(
            f"  {row['arm']:<26} {show(row['accuracy']):>9} "
            f"{show(row['p50']):>9} {show(row['p95']):>9} "
            f"{show(row['usd_per_100_turns'], money=True):>11}{marker}"
        )


def _cmd_compare(args: argparse.Namespace) -> int:
    settings = load_settings()
    judge = None
    if args.plumbing and not args.judged:
        print("--plumbing only applies to --judged runs.", file=sys.stderr)
        return 2
    if args.judged:
        if settings.provider_mode != "real" and not args.plumbing:
            print(_JUDGED_GATE_MESSAGE, file=sys.stderr)
            return 2
        try:
            judge = build_judge_provider(settings)
        except ConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    base_env = load_env()
    try:
        arm_a = _load_arm(args.arm_a, base_env)
        arm_b = _load_arm(args.arm_b, base_env)
    except (ValueError, ConfigError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    scenarios = load_scenario_files(args.scenarios)
    base_uri = args.database_uri or settings.database_uri
    name_a = pid_scoped_name("longmem_eval_a")
    name_b = pid_scoped_name("longmem_eval_b")
    uri_a = provision_scratch(base_uri, name_a)
    uri_b = provision_scratch(base_uri, name_b)
    arm_a["settings"] = replace(arm_a["settings"], database_uri=uri_a)
    arm_b["settings"] = replace(arm_b["settings"], database_uri=uri_b)
    try:
        report = asyncio.run(
            compare_scenarios(
                arm_a,
                arm_b,
                scenarios,
                include_held_out=args.include_held_out,
                k=args.k,
                judged=args.judged,
                judge=judge,
            ),
            loop_factory=asyncio.SelectorEventLoop,
        )
    finally:
        if args.keep_db:
            print(f"scratch databases kept: {name_a}, {name_b}")
        else:
            drop_scratch(base_uri, name_a)
            drop_scratch(base_uri, name_b)
    report["scenario_files"] = [str(p) for p in args.scenarios]
    report["arm_files"] = [str(args.arm_a), str(args.arm_b)]
    report["database_names"] = [name_a, name_b]
    _print_compare_report(report)
    out = _write_artifact(report, args.out or _default_artifact_path("compare"))
    print(f"\ncompare artifact: {out}")
    failed = sum(arm["report"]["checks_failed_total"] for arm in report["arms"])
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# The `emit-gold` and `agreement` verbs (stage 3; offline file operations)
# ---------------------------------------------------------------------------


def _iter_judged_artifact_items(artifact: dict):
    """Every judged item in a run OR compare artifact, artifact order."""
    judged = artifact.get("judged")
    if judged:
        yield from judged["items"]
    for arm in artifact.get("arms", []):
        arm_judged = arm["report"].get("judged")
        if arm_judged:
            yield from arm_judged["items"]
    pairwise = artifact.get("pairwise")
    if pairwise:
        yield from pairwise["items"]


def _gold_candidates(artifact: dict) -> tuple[list[GoldItem], int]:
    """Project a judged artifact into blind gold candidates. Verdicts are
    DELIBERATELY stripped (labels must be blind; item_id joins back to the
    artifact where verdicts live); judge_failed items are skipped — they
    carry no judge label to agree with."""
    rows: list[GoldItem] = []
    skipped_failed = 0
    for item in _iter_judged_artifact_items(artifact):
        if item.get("judge_failed"):
            skipped_failed += 1
            continue
        category = item["category"]
        version = item["rubric_version"]
        if category in ("selective_forgetting", "abstention"):
            rows.append(
                GoldItem(
                    item_id=item["item_id"],
                    category=category,
                    rubric_version=version,
                    question=item["question"],
                    reply=item["reply"],
                    reference=item["reference"],
                    superseded=item.get("superseded"),
                    expected_behavior=item.get("expected_behavior"),
                )
            )
        elif category == "reconstruction_faithfulness":
            for i, fact in enumerate(item["facts"]):
                rows.append(
                    GoldItem(
                        item_id=f"{item['item_id']}:fact{i}",
                        category=category,
                        rubric_version=version,
                        fact=fact,
                        telling=item["telling"],
                    )
                )
        elif category == "prose_pairwise":
            rows.append(
                GoldItem(
                    item_id=item["item_id"],
                    category=category,
                    rubric_version=version,
                    question=item["question"],
                    reply_a=item["reply_a"],
                    reply_b=item["reply_b"],
                )
            )
    return rows, skipped_failed


def _cmd_emit_gold(args: argparse.Namespace) -> int:
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    rows, skipped_failed = _gold_candidates(artifact)
    if not rows:
        print(
            f"{args.artifact}: no judged items — emit-gold needs a --judged "
            "run or compare artifact.",
            file=sys.stderr,
        )
        return 1
    capped: list[GoldItem] = []
    per_category: dict[str, int] = {}
    dropped = 0
    for row in rows:
        count = per_category.get(row.category, 0)
        if count >= args.limit_per_category:
            dropped += 1
            continue
        per_category[row.category] = count + 1
        capped.append(row)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(gold_line(row) + "\n" for row in capped), encoding="utf-8"
    )
    print(f"gold candidates: {args.out}")
    for category, count in sorted(per_category.items()):
        print(f"  {category:<28} {count}")
    if dropped:
        print(f"  (capped: {dropped} candidate(s) beyond --limit-per-category)")
    if skipped_failed:
        print(f"  (skipped {skipped_failed} judge_failed item(s) — no verdict)")
    print('fill each row\'s "label" (blind — the artifact holds the verdicts).')
    return 0


# ---------------------------------------------------------------------------
# The `judge-gold` verb (constructed-truth meta-eval, ruled 2026-08-12):
# providers yes, database no. Input rows are gold-shaped; their labels are
# constructed truth and are NEVER shown to the judge — _judge_one receives
# only display-field template kwargs.
# ---------------------------------------------------------------------------

_RF_GOLD_ID = re.compile(r"^(?P<base>.+):fact0$")

_PAIRWISE_REFUSAL = (
    "judge-gold refuses prose_pairwise rows — pairwise needs the "
    "position-swap protocol, which only a compare run (two live arms) "
    "provides."
)


def _prepare_judge_gold_rows(
    rows: list[GoldItem],
) -> list[tuple[str, str, dict, int, dict]]:
    """Validate gold-shaped input rows and map each to its judge call:
    (artifact item_id, category, template kwargs, n_facts, display fields).

    Any shape problem — a prose_pairwise row, a missing display field, a
    faithfulness id without the `:fact0` suffix, a rubric-version mismatch,
    or a duplicate id — raises ValueError naming the row; input-shape errors
    refuse the whole run loudly before any judge spend."""
    prepared: list[tuple[str, str, dict, int, dict]] = []
    seen: set[str] = set()
    for row in rows:
        if row.category == "prose_pairwise":
            raise ValueError(f"{row.item_id}: {_PAIRWISE_REFUSAL}")
        expected_version = RUBRICS[row.category].rubric_version
        if row.rubric_version != expected_version:
            raise ValueError(
                f"{row.item_id}: rubric_version {row.rubric_version!r} != "
                f"{expected_version!r} for category {row.category}"
            )
        if row.category in ("selective_forgetting", "abstention"):
            missing = [
                field
                for field in ("question", "reply", "reference")
                if getattr(row, field) is None
            ]
            if row.category == "abstention" and row.expected_behavior is None:
                missing.append("expected_behavior")
            if missing:
                raise ValueError(f"{row.item_id}: missing {', '.join(missing)}")
            template_kwargs = {
                "question": row.question,
                "reply": row.reply,
                "reference": row.reference,
            }
            if row.category == "selective_forgetting":
                template_kwargs["superseded"] = row.superseded or "(none)"
            else:
                template_kwargs["expected_behavior"] = row.expected_behavior
            item_id = row.item_id
            n_facts = 0
            display = {
                "question": row.question,
                "reply": row.reply,
                "reference": row.reference,
                "superseded": row.superseded,
                "expected_behavior": row.expected_behavior or "answer",
            }
        else:  # reconstruction_faithfulness — the only remaining category
            if row.fact is None or row.telling is None:
                raise ValueError(f"{row.item_id}: missing fact/telling")
            match = _RF_GOLD_ID.match(row.item_id)
            if match is None:
                raise ValueError(
                    f"{row.item_id}: faithfulness rows must be single-fact "
                    "with a ':fact0' item_id suffix (the artifact carries "
                    "the base id; agreement re-derives ':fact0')"
                )
            item_id = match.group("base")
            template_kwargs = {"telling": row.telling, "facts": f"1. {row.fact}"}
            n_facts = 1
            display = {"facts": [row.fact], "telling": row.telling}
        if item_id in seen:
            raise ValueError(
                f"{row.item_id}: duplicate item id — the agreement join "
                "index would silently overwrite"
            )
        seen.add(item_id)
        prepared.append((item_id, row.category, template_kwargs, n_facts, display))
    return prepared


def _cmd_judge_gold(args: argparse.Namespace) -> int:
    settings = load_settings()
    if settings.provider_mode != "real" and not args.plumbing:
        print(_JUDGED_GATE_MESSAGE, file=sys.stderr)
        return 2
    try:
        judge = build_judge_provider(settings)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        rows = load_gold(args.gold_in)
        prepared = _prepare_judge_gold_rows(rows)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    started = datetime.now(timezone.utc)
    items: list[dict] = []
    for item_id, category, template_kwargs, n_facts, display in prepared:
        fragment = _judge_one(judge, category, template_kwargs, n_facts=n_facts)
        items.append({"item_id": item_id, "category": category, **display, **fragment})
    finished = datetime.now(timezone.utc)
    judge_in = sum(i["input_tokens"] for i in items)
    judge_out = sum(i["output_tokens"] for i in items)
    prices = settings.prices
    judge_usd = (
        round(
            (judge_in * prices["judge_in"] + judge_out * prices["judge_out"]) / 1e6, 6
        )
        if "judge_in" in prices and "judge_out" in prices
        else None
    )
    categories = sorted({i["category"] for i in items})
    report = {
        "verb": "judge-gold",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "provider_mode": settings.provider_mode,
        "models": _models_block(settings),
        "gold_in": str(args.gold_in),
        "plumbing_only": settings.provider_mode != "real",
        "judged": {
            "rubric_versions": {c: RUBRICS[c].rubric_version for c in categories},
            "summary": _judged_summary(items),
            "items": items,
            "judge_ms_total": round(sum(i["judge_ms"] for i in items), 2),
            "judge_tokens": {
                "input_tokens": judge_in,
                "output_tokens": judge_out,
                "usd": judge_usd,
            },
        },
    }
    label = " [PLUMBING ONLY — fake providers]" if report["plumbing_only"] else ""
    print(f"\njudge-gold — {len(items)} row(s) judged{label}:")
    for category, block in report["judged"]["summary"].items():
        if "pass_rate" in block:
            print(
                f"  {category:<28} {block['passed']}/"
                f"{block['passed'] + block['failed']} pass, "
                f"{block['judge_failed']} judge_failed"
            )
        else:
            print(
                f"  {category:<28} {block['facts_supported']}/"
                f"{block['facts_total']} facts supported, "
                f"{block['judge_failed']} judge_failed"
            )
    failed_total = sum(1 for i in items if i["judge_failed"])
    if failed_total:
        print(
            f"  ({failed_total} judge_failed row(s) carry no verdict — "
            "agreement will count them unmatched)"
        )
    usd_text = f" (${judge_usd})" if judge_usd is not None else ""
    print(f"  judge tokens {judge_in}/{judge_out}{usd_text}")
    out = _write_artifact(report, args.out or _default_artifact_path("judge-gold"))
    print(f"judge-gold artifact: {out}")
    return 0


def _judge_label_index(artifact: dict) -> dict[str, tuple[str, str]]:
    """item_id -> (category, judge label) for agreement joining."""
    labels: dict[str, tuple[str, str]] = {}
    for item in _iter_judged_artifact_items(artifact):
        if item.get("judge_failed"):
            continue
        category = item["category"]
        if category in ("selective_forgetting", "abstention"):
            labels[item["item_id"]] = (category, item["verdict"]["verdict"])
        elif category == "reconstruction_faithfulness":
            for i, supported in enumerate(item["verdict"]["gist_supported"]):
                labels[f"{item['item_id']}:fact{i}"] = (
                    category,
                    "supported" if supported else "unsupported",
                )
        elif category == "prose_pairwise":
            labels[item["item_id"]] = (category, item["combined"]["preference"])
    return labels


def _cmd_agreement(args: argparse.Namespace) -> int:
    gold = load_gold(args.gold)
    artifact = json.loads(args.artifact.read_text(encoding="utf-8"))
    judge_labels = _judge_label_index(artifact)
    pairs: dict[str, list[tuple[str, str]]] = {}
    unlabeled = 0
    unmatched = 0
    for row in gold:
        if row.label is None:
            unlabeled += 1
            continue
        entry = judge_labels.get(row.item_id)
        if entry is None or entry[0] != row.category:
            unmatched += 1
            continue
        pairs.setdefault(row.category, []).append((row.label, entry[1]))
    report = {
        "verb": "agreement",
        "gold": str(args.gold),
        "artifact": str(args.artifact),
        "kappa_bar": args.kappa_bar,
        "unlabeled": unlabeled,
        "unmatched": unmatched,
        "categories": {},
    }
    print(
        f"\nagreement — {sum(len(p) for p in pairs.values())} labeled pair(s) "
        f"({unlabeled} unlabeled, {unmatched} unmatched) vs kappa bar "
        f"{args.kappa_bar}"
    )
    all_pass = bool(pairs)
    for category, category_pairs in sorted(pairs.items()):
        human = [h for h, _ in category_pairs]
        judge = [j for _, j in category_pairs]
        raw = raw_agreement(human, judge)
        kappa = cohen_kappa(human, judge)
        passed = kappa is not None and kappa >= args.kappa_bar
        all_pass = all_pass and passed
        report["categories"][category] = {
            "n": len(category_pairs),
            "raw_agreement": round(raw, 4) if raw is not None else None,
            "kappa": round(kappa, 4) if kappa is not None else None,
            "passes_bar": passed,
        }
        kappa_text = (
            f"{kappa:.4f}"
            if kappa is not None
            else "(undefined — degenerate marginals; rebalance the gold set)"
        )
        print(
            f"  {category:<28} n {len(category_pairs):>3}  raw "
            f"{raw:.4f}  kappa {kappa_text}  "
            f"{'PASS' if passed else 'FAIL'}"
        )
    if not pairs:
        print("  no labeled gold rows matched the artifact — nothing to score.")
    if args.out is not None:
        print(f"\nagreement report: {_write_artifact(report, args.out)}")
    print(
        "\njudged numbers are quotable"
        if all_pass
        else "\njudged numbers are NOT yet quotable (the agreement bar rules)"
    )
    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.eval_runner",
        description="longmem-npc eval runner (eval-harness.md stages 2-3)",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)

    run_parser = verbs.add_parser(
        "run", help="replay scenario files; score expected-IDs checks + metrics"
    )
    run_parser.add_argument(
        "--scenarios",
        type=Path,
        action="append",
        required=True,
        help="scenario JSONL file (repeatable)",
    )
    run_parser.add_argument(
        "--out",
        type=Path,
        help="run-artifact path (default: data\\eval\\runs\\run_<utc>_<pid>.json)",
    )
    run_parser.add_argument(
        "--database-name",
        help="scratch database name (default: longmem_eval_<pid>)",
    )
    run_parser.add_argument("--database-uri", help="override .env DATABASE_URI")
    run_parser.add_argument(
        "--include-held-out",
        action="store_true",
        help="also run scenarios marked held_out (excluded by default)",
    )
    run_parser.add_argument(
        "--k", type=int, help="run-wide top-k for utterances without their own k"
    )
    run_parser.add_argument(
        "--keep-db",
        action="store_true",
        help="skip the scratch drop for post-mortem inspection",
    )
    run_parser.add_argument(
        "--judged",
        action="store_true",
        help="run the stage-3 judge pass (real mode, or --plumbing)",
    )
    run_parser.add_argument(
        "--plumbing",
        action="store_true",
        help="allow --judged in fake mode; the report is labeled plumbing_only",
    )
    run_parser.set_defaults(func=_cmd_run)

    drift_parser = verbs.add_parser(
        "drift-validate",
        help="per-item reconstruction drift vs drift_budget_threshold",
    )
    drift_parser.add_argument(
        "--corpus", type=Path, required=True, help="corpus JSONL (observe/as_of only)"
    )
    drift_parser.add_argument(
        "--age-days",
        type=float,
        default=30.0,
        help="how far past the last authored moment the probe ages (default 30)",
    )
    drift_parser.add_argument(
        "--probe",
        default=DEFAULT_PROBE,
        help="probe utterance (coverage comes from k, not wording)",
    )
    drift_parser.add_argument(
        "--max-items", type=int, help="cap the probe's k (default: every observe)"
    )
    drift_parser.add_argument("--out", type=Path, help="also write the report JSON")
    drift_parser.add_argument(
        "--database-name",
        help="scratch database name (default: longmem_eval_<pid>)",
    )
    drift_parser.add_argument("--database-uri", help="override .env DATABASE_URI")
    drift_parser.add_argument(
        "--keep-db",
        action="store_true",
        help="skip the scratch drop for post-mortem inspection",
    )
    drift_parser.add_argument(
        "--plumbing",
        action="store_true",
        help="allow fake provider mode; the report is labeled plumbing_only",
    )
    drift_parser.set_defaults(func=_cmd_drift_validate)

    compare_parser = verbs.add_parser(
        "compare",
        help="A/B two arm overlays over the same scenarios (+ pairwise prose "
        "and the Pareto table with --judged)",
    )
    compare_parser.add_argument(
        "--scenarios",
        type=Path,
        action="append",
        required=True,
        help="scenario JSONL file (repeatable)",
    )
    compare_parser.add_argument(
        "--arm-a", type=Path, required=True, help="arm A overlay JSON"
    )
    compare_parser.add_argument(
        "--arm-b", type=Path, required=True, help="arm B overlay JSON"
    )
    compare_parser.add_argument(
        "--out",
        type=Path,
        help="artifact path (default: data\\eval\\runs\\compare_<utc>_<pid>.json)",
    )
    compare_parser.add_argument("--database-uri", help="override .env DATABASE_URI")
    compare_parser.add_argument(
        "--include-held-out",
        action="store_true",
        help="also run scenarios marked held_out (excluded by default — "
        "held-out stays out of tuning/compare runs)",
    )
    compare_parser.add_argument(
        "--k", type=int, help="run-wide top-k for utterances without their own k"
    )
    compare_parser.add_argument(
        "--keep-db",
        action="store_true",
        help="skip the scratch drops for post-mortem inspection",
    )
    compare_parser.add_argument(
        "--judged",
        action="store_true",
        help="judge both arms + pairwise prose (real mode, or --plumbing)",
    )
    compare_parser.add_argument(
        "--plumbing",
        action="store_true",
        help="allow --judged in fake mode; the report is labeled plumbing_only",
    )
    compare_parser.set_defaults(func=_cmd_compare)

    gold_parser = verbs.add_parser(
        "emit-gold",
        help="project a judged artifact into blind gold-candidate JSONL",
    )
    gold_parser.add_argument(
        "--artifact", type=Path, required=True, help="a --judged run/compare artifact"
    )
    gold_parser.add_argument(
        "--out", type=Path, required=True, help="gold JSONL output path"
    )
    gold_parser.add_argument(
        "--limit-per-category",
        type=int,
        default=30,
        help="gold-candidate cap per category (default 30, fork 12)",
    )
    gold_parser.set_defaults(func=_cmd_emit_gold)

    agreement_parser = verbs.add_parser(
        "agreement",
        help="reference labels vs judge verdicts: raw %% + Cohen's kappa per category",
    )
    agreement_parser.add_argument(
        "--gold", type=Path, required=True, help="labeled gold JSONL"
    )
    agreement_parser.add_argument(
        "--artifact", type=Path, required=True, help="the judged artifact to score"
    )
    agreement_parser.add_argument(
        "--kappa-bar",
        type=float,
        default=0.6,
        help="quotability bar: kappa >= this per category (default 0.6, fork 5)",
    )
    agreement_parser.add_argument(
        "--out", type=Path, help="also write the agreement report JSON"
    )
    agreement_parser.set_defaults(func=_cmd_agreement)

    judge_gold_parser = verbs.add_parser(
        "judge-gold",
        help="judge gold-shaped rows fresh (constructed-truth meta-eval); "
        "writes an artifact agreement can score",
    )
    judge_gold_parser.add_argument(
        "--gold-in",
        type=Path,
        required=True,
        help="gold-shaped JSONL; labels, if present, are never shown to the judge",
    )
    judge_gold_parser.add_argument(
        "--out",
        type=Path,
        help="artifact path (default: data\\eval\\runs\\judge-gold_<utc>_<pid>.json)",
    )
    judge_gold_parser.add_argument(
        "--plumbing",
        action="store_true",
        help="allow fake provider mode; the report is labeled plumbing_only",
    )
    judge_gold_parser.set_defaults(func=_cmd_judge_gold)

    ablation_parser = verbs.add_parser(
        "ablation",
        help="fixed-gist ON vs OFF over one corpus on two scratch DBs "
        "(stage 4 — R7's deciding data; judge-free)",
    )
    ablation_parser.add_argument(
        "--corpus", type=Path, required=True, help="corpus JSONL (observe/as_of only)"
    )
    ablation_parser.add_argument(
        "--age-days",
        type=float,
        default=30.0,
        help="how far past the last authored moment the probe ages (default 30)",
    )
    ablation_parser.add_argument(
        "--probe",
        default=DEFAULT_PROBE,
        help="probe utterance (coverage comes from k, not wording)",
    )
    ablation_parser.add_argument(
        "--out",
        type=Path,
        help="artifact path (default: data\\eval\\runs\\ablation_<utc>_<pid>.json)",
    )
    ablation_parser.add_argument("--database-uri", help="override .env DATABASE_URI")
    ablation_parser.add_argument(
        "--keep-db",
        action="store_true",
        help="skip the scratch drops for post-mortem inspection",
    )
    ablation_parser.add_argument(
        "--plumbing",
        action="store_true",
        help="allow fake provider mode; the report is labeled plumbing_only",
    )
    ablation_parser.set_defaults(func=_cmd_ablation)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
