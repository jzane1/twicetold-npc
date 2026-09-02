"""Set I — eval-harness stage 3: the judge layer's structural surface
(docs\\eval-harness.md stage 3; docs\\test-suite.md discipline).

Covers the stage-3 MECHANICS with the deterministic fake judge — never real
judged signal and never assertions on prose (the judged surface's semantics
live in real run artifacts, past the agreement bar): the config regression
(real mode never requires the judge var — the 2026-07-29 ruling as code;
the reflection var joined the same judge shape 2026-08-15, asserted here),
the thinking knob's request shapes, fake-judge determinism, verdict
validation and per-item judge_failed degradation, the position-swap tie
rule, hand-computed kappa arithmetic with honest-None denominators, the
gold emit -> label -> agreement round trip, arm-overlay loading, Pareto
non-domination, and one plumbing compare end-to-end (nlp mark — it drives
the real write pass on scratch settings, the Set H precedent).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    ENV_DIALOGUE_THINKING,
    ENV_JUDGE_MAX_TOKENS,
    ENV_MODEL_JUDGE,
    ENV_MODEL_REFLECTION,
    ConfigError,
    Settings,
    load_env,
    load_settings,
)
from app.eval_judge import (
    GOLD_LABELS,
    RUBRICS,
    GoldItem,
    PairwiseVerdict,
    cohen_kappa,
    combine_pairwise,
    gold_line,
    load_gold,
    pareto_non_dominated,
    raw_agreement,
    validate_verdict,
)
from app.eval_runner import (
    _cmd_agreement,
    _cmd_judge_gold,
    _cmd_run,
    _gold_candidates,
    _judge_label_index,
    _judge_one,
    _judge_utterance_items,
    _load_arm,
    compare_scenarios,
)
from app.eval_scenarios import JudgedSpec, Scenario, load_scenarios
from app.providers import (
    FailingJudgeProvider,
    FakeJudgeProvider,
    MalformedJudgeProvider,
    _dialogue_thinking_kwargs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
JUDGED_FIXTURE = REPO_ROOT / "data" / "eval" / "scenarios" / "judged.jsonl"
ARMS_DIR = REPO_ROOT / "data" / "eval" / "arms"

# TEST-NET-1 (RFC 5737), the Set H convention: a refusal that tried to
# connect would hang to timeout instead of returning instantly.
UNREACHABLE_URI = "postgresql://u:p@192.0.2.1:5432/postgres"

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


# ---------------------------------------------------------------------------
# Config: the ruling as a regression test + the thinking knob
# ---------------------------------------------------------------------------


def test_config_judge_regression():
    """Real mode loads WITHOUT the judge var (never in the required list);
    both modes load it when present; prices and the max-tokens knob parse.
    The reflection role shares the judge shape (the C2 dossier ruling
    2026-08-15) — the same load-rule assertions cover it here."""
    settings = load_settings(dict(REAL_ENV))
    assert settings.provider_mode == "real"
    assert settings.model_judge == ""
    assert settings.model_reflection == ""  # loaded-never-required, like judge

    settings = load_settings({**REAL_ENV, ENV_MODEL_JUDGE: "model-j"})
    assert settings.model_judge == "model-j"
    assert (
        load_settings({**REAL_ENV, ENV_MODEL_REFLECTION: "model-f"}).model_reflection
        == "model-f"
    )
    fake = load_settings(
        {
            "DATABASE_URI": UNREACHABLE_URI,
            "TWICETOLD_PROVIDER_MODE": "fake",
            ENV_MODEL_JUDGE: "model-j",
            ENV_MODEL_REFLECTION: "model-f",
        }
    )
    assert fake.model_judge == "model-j"  # loaded in fake mode too
    assert fake.model_reflection == "model-f"

    priced = load_settings(
        {
            **REAL_ENV,
            "TWICETOLD_PRICE_JUDGE_IN": "5.00",
            "TWICETOLD_PRICE_JUDGE_OUT": "25.00",
            "TWICETOLD_PRICE_REFLECTION_IN": "1.00",
            "TWICETOLD_PRICE_REFLECTION_OUT": "5.00",
        }
    )
    assert priced.prices["judge_in"] == 5.0
    assert priced.prices["judge_out"] == 25.0
    assert priced.prices["reflection_in"] == 1.0
    assert priced.prices["reflection_out"] == 5.0

    assert load_settings(dict(REAL_ENV)).judge_max_tokens == 2048
    assert (
        load_settings({**REAL_ENV, ENV_JUDGE_MAX_TOKENS: "4096"}).judge_max_tokens
        == 4096
    )
    with pytest.raises(ConfigError, match="must be an integer"):
        load_settings({**REAL_ENV, ENV_JUDGE_MAX_TOKENS: "many"})
    with pytest.raises(ConfigError, match=">= 1"):
        load_settings({**REAL_ENV, ENV_JUDGE_MAX_TOKENS: "0"})


def test_dialogue_thinking_knob(tmp_path, monkeypatch):
    """Values validate at load; the request-shape helper is exact; the
    judge/thinking/max-tokens keys (B2) and the reflection key (C2) all
    ride the process-env override allowlist."""
    assert load_settings(dict(REAL_ENV)).dialogue_thinking == ""
    assert (
        load_settings({**REAL_ENV, ENV_DIALOGUE_THINKING: "disabled"}).dialogue_thinking
        == "disabled"
    )
    with pytest.raises(ConfigError, match="unset or 'disabled'"):
        load_settings({**REAL_ENV, ENV_DIALOGUE_THINKING: "adaptive"})

    assert _dialogue_thinking_kwargs("") == {}
    assert _dialogue_thinking_kwargs("disabled") == {"thinking": {"type": "disabled"}}

    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URI={UNREACHABLE_URI}\n", encoding="utf-8")
    monkeypatch.setenv(ENV_MODEL_JUDGE, "override-j")
    monkeypatch.setenv(ENV_DIALOGUE_THINKING, "disabled")
    monkeypatch.setenv(ENV_JUDGE_MAX_TOKENS, "1024")
    monkeypatch.setenv(ENV_MODEL_REFLECTION, "override-f")
    values = load_env(env_file)
    assert values[ENV_MODEL_JUDGE] == "override-j"
    assert values[ENV_DIALOGUE_THINKING] == "disabled"
    assert values[ENV_JUDGE_MAX_TOKENS] == "1024"
    assert values[ENV_MODEL_REFLECTION] == "override-f"


# ---------------------------------------------------------------------------
# The fake judge + verdict validation + degradation
# ---------------------------------------------------------------------------


def test_fake_judge_determinism():
    """Byte-identical payloads on identical inputs across all four
    categories; every payload validates under its verdict model; distinct
    inputs vary the binary verdict somewhere."""
    judge = FakeJudgeProvider()
    cases = [
        ("selective_forgetting", 0),
        ("abstention", 0),
        ("reconstruction_faithfulness", 3),
        ("prose_pairwise", 0),
    ]
    for category, n_facts in cases:
        first = judge.judge(
            system_prompt="s", user_content="u", category=category, n_facts=n_facts
        )
        second = judge.judge(
            system_prompt="s", user_content="u", category=category, n_facts=n_facts
        )
        assert first.payload == second.payload
        validate_verdict(category, first.payload, n_facts=n_facts)
    with pytest.raises(ValueError, match="unknown judge category"):
        judge.judge(system_prompt="s", user_content="u", category="vibes")

    verdicts = {
        judge.judge(
            system_prompt="s", user_content=f"input {i}", category="abstention"
        ).payload["verdict"]
        for i in range(16)
    }
    assert verdicts == {"pass", "fail"}


def test_verdict_validation_and_judge_failed():
    """Shape violations raise; _judge_one degrades per item with token
    accounting (Malformed carries 7/3 — the spend happened; Failing carries
    zero) and the fragment stays JSON-shaped either way."""
    with pytest.raises(ValidationError):
        validate_verdict("selective_forgetting", {"verdict": "maybe"})
    with pytest.raises(ValidationError):
        validate_verdict("selective_forgetting", {"verdict": "pass", "extra_key": 1})
    with pytest.raises(ValidationError):
        validate_verdict(
            "prose_pairwise",
            {
                "a": {
                    "naturalness": 6,
                    "character_consistency": 3,
                    "memory_grounding": 3,
                    "brevity": 3,
                },
                "b": {
                    "naturalness": 3,
                    "character_consistency": 3,
                    "memory_grounding": 3,
                    "brevity": 3,
                },
                "preference": "a",
            },
        )
    with pytest.raises(ValueError, match="expected 3"):
        validate_verdict(
            "reconstruction_faithfulness",
            {"gist_supported": [True, False]},
            n_facts=3,
        )

    template = {"question": "q", "reply": "r", "reference": "ref"}
    malformed = _judge_one(
        MalformedJudgeProvider(),
        "abstention",
        {**template, "expected_behavior": "answer"},
    )
    assert malformed["judge_failed"] is True
    assert (malformed["input_tokens"], malformed["output_tokens"]) == (7, 3)
    assert "verdict" not in malformed
    failed = _judge_one(
        FailingJudgeProvider(),
        "abstention",
        {**template, "expected_behavior": "answer"},
    )
    assert failed["judge_failed"] is True
    assert (failed["input_tokens"], failed["output_tokens"]) == (0, 0)
    ok = _judge_one(
        FakeJudgeProvider(), "abstention", {**template, "expected_behavior": "answer"}
    )
    assert ok["judge_failed"] is False
    assert ok["verdict"]["verdict"] in ("pass", "fail")
    for fragment in (malformed, failed, ok):
        assert fragment["rubric_version"] == RUBRICS["abstention"].rubric_version
        assert fragment["judge_ms"] >= 0
        json.dumps(fragment)


def test_rubric_constants():
    """All four categories, non-empty version tags, and the JSON-only output
    contract every real-provider prompt in this repo ends with."""
    assert set(RUBRICS) == {
        "selective_forgetting",
        "abstention",
        "reconstruction_faithfulness",
        "prose_pairwise",
    }
    assert set(RUBRICS) == set(GOLD_LABELS)
    versions = [rubric.rubric_version for rubric in RUBRICS.values()]
    assert all(versions) and len(set(versions)) == len(versions)
    for category, rubric in RUBRICS.items():
        assert rubric.category == category
        assert rubric.system_prompt.endswith("No other text.")
        assert rubric.user_template


def test_judged_utterance_pass_offline():
    """The sf/abstention judging step over captured prose records: items
    carry stable ids, display texts, verdicts, and accounting; records
    without a JudgedSpec are skipped."""
    records = [
        {
            "event_index": 4,
            "utterance": "Where are the apples?",
            "content": "[fake dialogue] Where are the apples?",
            "degraded": False,
            "judged": {
                "category": "selective_forgetting",
                "reference": "In the loft.",
                "superseded": "In the cellar.",
                "expected_behavior": "answer",
            },
        },
        {
            "event_index": 5,
            "utterance": "Unjudged probe.",
            "content": "[fake dialogue] Unjudged probe.",
            "degraded": False,
            "judged": None,
        },
        {
            "event_index": 6,
            "utterance": "What did the miller pay?",
            "content": "[fake dialogue] What did the miller pay?",
            "degraded": True,
            "judged": {
                "category": "abstention",
                "reference": "No miller bought anything.",
                "superseded": None,
                "expected_behavior": "abstain",
            },
        },
    ]
    items = asyncio.run(
        _judge_utterance_items("fix", records, FakeJudgeProvider()),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert [i["item_id"] for i in items] == ["fix:4", "fix:6"]
    sf, abst = items
    assert sf["category"] == "selective_forgetting"
    assert sf["superseded"] == "In the cellar."
    assert abst["expected_behavior"] == "abstain"
    assert abst["degraded"] is True
    for item in items:
        assert item["judge_failed"] is False
        assert item["verdict"]["verdict"] in ("pass", "fail")
        assert item["input_tokens"] > 0
    json.dumps(items)


# ---------------------------------------------------------------------------
# Position swap, kappa, Pareto — pure arithmetic
# ---------------------------------------------------------------------------


def _pairwise(pref: str, a: int = 3, b: int = 3) -> PairwiseVerdict:
    scores_a = {
        "naturalness": a,
        "character_consistency": a,
        "memory_grounding": a,
        "brevity": a,
    }
    scores_b = {
        "naturalness": b,
        "character_consistency": b,
        "memory_grounding": b,
        "brevity": b,
    }
    return PairwiseVerdict.model_validate(
        {"a": scores_a, "b": scores_b, "preference": pref}
    )


def test_position_swap_tie_arithmetic():
    """Un-swap + agreement rule: both positions must name the same true arm
    or the pair is a tie; per-arm scores average the two calls."""
    # First call (A,B) prefers a; swapped call (B,A) prefers b => true A both.
    agree_a = combine_pairwise(_pairwise("a", a=4, b=2), _pairwise("b", a=1, b=5))
    assert agree_a["preference"] == "a"
    assert agree_a["positions_agreed"] is True
    # True A scored 4 in first.a and 5 in second.b -> mean 4.5.
    assert agree_a["a"]["naturalness"] == 4.5
    assert agree_a["b"]["naturalness"] == 1.5

    agree_b = combine_pairwise(_pairwise("b"), _pairwise("a"))
    assert agree_b["preference"] == "b"

    flip = combine_pairwise(_pairwise("a"), _pairwise("a"))
    assert flip["preference"] == "tie"
    assert flip["positions_agreed"] is False

    tie_first = combine_pairwise(_pairwise("tie"), _pairwise("b"))
    assert tie_first["preference"] == "tie"
    both_tie = combine_pairwise(_pairwise("tie"), _pairwise("tie"))
    assert both_tie["preference"] == "tie"
    assert both_tie["positions_agreed"] is True


def test_cohen_kappa_exact():
    """Hand-computed: po 0.7 with balanced 6/4 marginals -> pe 0.5 -> kappa
    exactly 0.4; perfect two-class agreement -> 1.0; degenerate single-class
    marginals and empty inputs -> honest None."""
    human = ["p"] * 5 + ["f"] * 5
    judge = ["p", "p", "p", "p", "f", "p", "p", "f", "f", "f"]
    assert raw_agreement(human, judge) == pytest.approx(0.7)
    assert cohen_kappa(human, judge) == pytest.approx(0.4)

    assert cohen_kappa(["p", "f", "p"], ["p", "f", "p"]) == pytest.approx(1.0)
    assert cohen_kappa(["p", "p"], ["p", "p"]) is None  # pe == 1
    assert cohen_kappa([], []) is None
    assert raw_agreement([], []) is None
    with pytest.raises(ValueError, match="differ in length"):
        raw_agreement(["p"], ["p", "f"])


def test_pareto_dominance():
    """Strict dominance on the four keys; any None makes a pair incomparable
    (an unpriced arm is never 'beaten' on cost)."""
    dominated = {"accuracy": 0.5, "p50": 900.0, "p95": 1800.0, "usd_per_100_turns": 0.5}
    dominator = {"accuracy": 0.9, "p50": 800.0, "p95": 1500.0, "usd_per_100_turns": 0.2}
    assert pareto_non_dominated([dominator, dominated]) == [True, False]

    tradeoff_a = {
        "accuracy": 0.9,
        "p50": 1200.0,
        "p95": 2000.0,
        "usd_per_100_turns": 0.4,
    }
    tradeoff_b = {
        "accuracy": 0.7,
        "p50": 900.0,
        "p95": 1700.0,
        "usd_per_100_turns": 0.1,
    }
    assert pareto_non_dominated([tradeoff_a, tradeoff_b]) == [True, True]

    unpriced = {
        "accuracy": 0.1,
        "p50": 9999.0,
        "p95": 9999.0,
        "usd_per_100_turns": None,
    }
    assert pareto_non_dominated([dominator, unpriced]) == [True, True]

    identical = dict(dominator)
    assert pareto_non_dominated([dominator, identical]) == [True, True]


# ---------------------------------------------------------------------------
# Schema strictness + fixture census canary
# ---------------------------------------------------------------------------


def test_judged_schema_strictness_and_fixture_census():
    spec = JudgedSpec.model_validate(
        {"category": "abstention", "reference": "x", "expected_behavior": "abstain"}
    )
    assert spec.superseded is None
    with pytest.raises(ValidationError):
        JudgedSpec.model_validate(
            {"category": "abstention", "reference": "x", "typo": 1}
        )
    with pytest.raises(ValidationError, match="only valid with category abstention"):
        JudgedSpec.model_validate(
            {
                "category": "selective_forgetting",
                "reference": "x",
                "expected_behavior": "abstain",
            }
        )
    with pytest.raises(
        ValidationError, match="only valid with category selective_forgetting"
    ):
        JudgedSpec.model_validate(
            {"category": "abstention", "reference": "x", "superseded": "y"}
        )

    scenarios = load_scenarios(JUDGED_FIXTURE)
    assert len(scenarios) == 8
    assert not any(s.held_out for s in scenarios)
    sf = abst = probes = 0
    for scenario in scenarios:
        for event in scenario.events:
            judged = getattr(event, "judged", None)
            if judged is None:
                if event.kind == "utterance":
                    probes += 1
                continue
            if judged.category == "selective_forgetting":
                assert judged.superseded is not None
                sf += 1
            else:
                abst += 1
    assert (sf, abst, probes) == (24, 24, 8)
    # Every abstention trio carries a true-premise control (kappa balance).
    for scenario in scenarios:
        behaviors = [
            e.judged.expected_behavior
            for e in scenario.events
            if getattr(e, "judged", None) and e.judged.category == "abstention"
        ]
        assert behaviors.count("abstain") == 2 and behaviors.count("answer") == 1


# ---------------------------------------------------------------------------
# Gates, overlays, gold round trip
# ---------------------------------------------------------------------------


def _run_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        scenarios=[Path("never-touched.jsonl")],
        out=None,
        database_name=None,
        database_uri=None,
        include_held_out=False,
        k=None,
        keep_db=False,
        judged=True,
        plumbing=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_judged_refusal_exit2(monkeypatch):
    """Fake mode + --judged without --plumbing refuses with exit 2 BEFORE
    any provisioning or file access; --plumbing without --judged is refused
    the same way."""
    import app.eval_runner as runner_module

    fake_settings = Settings(database_uri=UNREACHABLE_URI, provider_mode="fake")
    monkeypatch.setattr(runner_module, "load_settings", lambda: fake_settings)

    def _explode(*_args, **_kwargs):
        raise AssertionError("provisioning must not be reached")

    monkeypatch.setattr(runner_module, "provision_scratch", _explode)
    monkeypatch.setattr(runner_module, "load_scenario_files", _explode)

    assert _cmd_run(_run_args()) == 2
    assert _cmd_run(_run_args(judged=False, plumbing=True)) == 2


def test_overlay_loading(tmp_path):
    """The env-dict merge resolves model/prices/thinking through
    load_settings; mode/database/key/judge overrides are refused loudly; the
    committed arm files parse (canary)."""
    base_env = {"DATABASE_URI": UNREACHABLE_URI, "TWICETOLD_PROVIDER_MODE": "fake"}
    arm_file = tmp_path / "arm.json"
    arm_file.write_text(
        json.dumps(
            {
                "name": "test-arm",
                "env": {
                    "TWICETOLD_MODEL_DIALOGUE": "model-x",
                    "TWICETOLD_DIALOGUE_THINKING": "disabled",
                    "TWICETOLD_PRICE_DIALOGUE_IN": "2.00",
                    "TWICETOLD_PRICE_DIALOGUE_OUT": "10.00",
                },
            }
        ),
        encoding="utf-8",
    )
    arm = _load_arm(arm_file, base_env)
    assert arm["name"] == "test-arm"
    assert arm["settings"].dialogue_thinking == "disabled"
    assert arm["settings"].prices["dialogue_in"] == 2.0
    # Fake mode ignores role values by design — the overlay block itself is
    # the arm's provenance there.
    assert arm["overlay"]["TWICETOLD_MODEL_DIALOGUE"] == "model-x"

    for bad_key in ("DATABASE_URI", "TWICETOLD_PROVIDER_MODE", "TWICETOLD_MODEL_JUDGE"):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps({"name": "bad", "env": {bad_key: "x"}}), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="not allowed"):
            _load_arm(bad_file, base_env)
    unnamed = tmp_path / "unnamed.json"
    unnamed.write_text(json.dumps({"env": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty string 'name'"):
        _load_arm(unnamed, base_env)

    committed = sorted(p.name for p in ARMS_DIR.glob("*.json"))
    assert committed == ["haiku.json", "sonnet5-thinking-off.json", "sonnet5.json"]
    for path in ARMS_DIR.glob("*.json"):
        _load_arm(path, base_env)


def _judged_artifact() -> dict:
    """A constructed judged run artifact: four sf items with mixed verdicts
    plus one faithfulness item with a mixed per-fact vector."""
    sf_items = [
        {
            "item_id": f"fix:{i}",
            "scenario_id": "fix",
            "event_index": i,
            "category": "selective_forgetting",
            "question": f"q{i}",
            "reply": f"r{i}",
            "reference": "ref",
            "superseded": "old",
            "expected_behavior": "answer",
            "degraded": False,
            "rubric_version": "sf-v1",
            "judge_failed": False,
            "verdict": {"verdict": verdict, "rationale": ""},
            "input_tokens": 10,
            "output_tokens": 5,
            "judge_ms": 1.0,
        }
        for i, verdict in enumerate(["pass", "pass", "fail", "fail"])
    ]
    rf_item = {
        "item_id": "fix:mem0",
        "scenario_id": "fix",
        "memory_ref": 0,
        "category": "reconstruction_faithfulness",
        "facts": ["fact one", "fact two"],
        "telling": "the telling",
        "rubric_version": "rf-v1",
        "judge_failed": False,
        "verdict": {
            "gist_supported": [True, False],
            "fabricated_claims": [],
            "rationale": "",
        },
        "input_tokens": 10,
        "output_tokens": 5,
        "judge_ms": 1.0,
    }
    failed_item = {
        "item_id": "fix:9",
        "scenario_id": "fix",
        "event_index": 9,
        "category": "abstention",
        "question": "q9",
        "reply": "r9",
        "reference": "ref",
        "superseded": None,
        "expected_behavior": "abstain",
        "degraded": False,
        "rubric_version": "abst-v1",
        "judge_failed": True,
        "error": "injected",
        "input_tokens": 7,
        "output_tokens": 3,
        "judge_ms": 1.0,
    }
    return {"verb": "run", "judged": {"items": [*sf_items, rf_item, failed_item]}}


def test_gold_emit_label_agreement_roundtrip(tmp_path, capsys):
    """emit -> blind rows (verdicts stripped, judge_failed skipped) -> hand
    labels -> agreement reproduces the hand-computed kappa and the bar's
    exit codes; unlabeled rows are skipped with honest counts."""
    artifact = _judged_artifact()
    rows, skipped_failed = _gold_candidates(artifact)
    assert skipped_failed == 1
    assert [r.item_id for r in rows] == [
        "fix:0",
        "fix:1",
        "fix:2",
        "fix:3",
        "fix:mem0:fact0",
        "fix:mem0:fact1",
    ]
    for row in rows:
        assert row.label is None
        line = json.loads(gold_line(row))
        assert "verdict" not in line and line["label"] is None

    labels = _judge_label_index(artifact)
    assert labels["fix:0"] == ("selective_forgetting", "pass")
    assert labels["fix:mem0:fact1"] == ("reconstruction_faithfulness", "unsupported")
    assert "fix:9" not in labels  # judge_failed carries no label

    # Perfect agreement (both classes used) -> kappa 1.0 -> exit 0.
    agree = {
        "fix:0": "pass",
        "fix:1": "pass",
        "fix:2": "fail",
        "fix:3": "fail",
        "fix:mem0:fact0": "supported",
        "fix:mem0:fact1": "unsupported",
    }
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text(
        "".join(
            gold_line(row.model_copy(update={"label": agree[row.item_id]})) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    loaded = load_gold(gold_path)
    assert [g.label for g in loaded] == list(agree.values())
    args = argparse.Namespace(
        gold=gold_path, artifact=artifact_path, kappa_bar=0.6, out=None
    )
    assert _cmd_agreement(args) == 0
    assert "quotable" in capsys.readouterr().out

    # One sf label flipped + one row left null: kappa drops below the bar
    # for sf -> exit 1; the null row is counted, not scored.
    disagree = dict(agree)
    disagree["fix:2"] = "pass"
    lines = []
    for row in rows:
        label = None if row.item_id == "fix:mem0:fact0" else disagree[row.item_id]
        lines.append(gold_line(row.model_copy(update={"label": label})) + "\n")
    gold_path.write_text("".join(lines), encoding="utf-8")
    assert _cmd_agreement(args) == 1
    out = capsys.readouterr().out
    assert "1 unlabeled" in out
    with pytest.raises(ValueError, match="not in"):
        GoldItem.model_validate(
            {
                "item_id": "x",
                "category": "abstention",
                "rubric_version": "abst-v1",
                "label": "supported",
            }
        )


# ---------------------------------------------------------------------------
# End-to-end: compare plumbing in-process (real write pass -> nlp mark)
# ---------------------------------------------------------------------------

COMPARE_SCENARIO = {
    "scenario_id": "set-i-compare",
    "agent": {
        "name": "set-i-inline",
        "seed_identity": "A keeper of small facts by the mill.",
        "diagnosticity_goal": "what changed and who changed it",
        "config": {
            "decay_classes": {"episodic": 86400.0, "semantic": 604800.0},
            "decay_class_default": "semantic",
            "importance_norm_floor": 1.0,
            "decay_k_importance": 0.0,
        },
    },
    "events": [
        {"kind": "as_of", "at": "2026-06-01T09:00:00+00:00"},
        {
            "kind": "observe",
            "text": "The well rope frayed and was replaced with new hemp.",
        },
        {"kind": "observe", "text": "A grey cat took up residence in the mill loft."},
        {
            "kind": "correct",
            "memory_ref": 0,
            "content": "The well rope frayed; the hemp replacement is still on order.",
        },
        {
            "kind": "utterance",
            "text": "Is the well rope mended yet?",
            "k": 2,
            "judged": {
                "category": "selective_forgetting",
                "reference": "Not yet — the hemp replacement is still on order.",
                "superseded": "The rope was replaced with new hemp.",
            },
        },
        {
            "kind": "utterance",
            "text": "What did the dog knock into the well?",
            "k": 2,
            "judged": {
                "category": "abstention",
                "reference": "No dog is known at the well; a grey cat lives in the loft.",
                "expected_behavior": "abstain",
            },
        },
        {"kind": "as_of", "at": "2026-07-06T09:00:00+00:00"},
        {"kind": "scene"},
        {"kind": "utterance", "text": "Tell me everything you remember here.", "k": 2},
    ],
}


@pytest.mark.nlp
def test_compare_plumbing_end_to_end(scene):
    """The compare core on scratch settings with fake providers + the fake
    judge: stamped arm blocks, judged summaries, deterministic pairwise
    verdicts, the Pareto table with honest-None USD, plumbing_only label,
    JSON-serializable report. Never asserts on prose."""
    scenario = Scenario.model_validate(COMPARE_SCENARIO)
    arm_a = {"name": "arm-a", "overlay": {}, "settings": scene.settings}
    arm_b = {
        "name": "arm-b",
        "overlay": {"TWICETOLD_DIALOGUE_THINKING": "disabled"},
        "settings": replace(scene.settings, dialogue_thinking="disabled"),
    }
    report = asyncio.run(
        compare_scenarios(
            arm_a,
            arm_b,
            [scenario],
            include_held_out=False,
            k=None,
            judged=True,
            judge=FakeJudgeProvider(),
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert report["verb"] == "compare"
    assert report["plumbing_only"] is True
    assert [arm["name"] for arm in report["arms"]] == ["arm-a", "arm-b"]
    assert report["arms"][1]["report"]["models"]["dialogue_thinking"] == "disabled"

    for arm in report["arms"]:
        arm_report = arm["report"]
        assert arm_report["plumbing_only"] is True
        summary = arm_report["judged"]["summary"]
        assert summary["selective_forgetting"]["items"] == 1
        assert summary["abstention"]["items"] == 1
        rf = summary.get("reconstruction_faithfulness")
        assert rf is not None and rf["items"] >= 1  # the aged probe retold
        assert arm_report["cost"]["judge"]["usd"] is None  # keyless: unpriced
        prose = [p for s in arm_report["scenarios"] for p in s["prose"]]
        assert [p["event_index"] for p in prose] == [4, 5, 8]

    pairwise = report["pairwise"]
    assert pairwise["summary"]["pairs"] == 3
    assert pairwise["summary"]["judge_failed"] == 0
    for item in pairwise["items"]:
        assert item["combined"]["preference"] in ("a", "b", "tie")
        assert item["item_id"].startswith("cmp:set-i-compare:")

    rows = report["pareto"]
    assert [row["arm"] for row in rows] == ["arm-a", "arm-b"]
    for row in rows:
        assert row["accuracy"] is not None
        assert row["usd_per_100_turns"] is None  # keyless -> honest None
        assert row["non_dominated"] is True  # None cost -> incomparable
    json.dumps(report)


# ---------------------------------------------------------------------------
# judge-gold (the constructed-truth meta-eval verb, ruled 2026-08-12)
# ---------------------------------------------------------------------------


def _judge_gold_args(**overrides) -> argparse.Namespace:
    defaults = dict(gold_in=Path("never-read.jsonl"), out=None, plumbing=True)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _gold_row(**fields) -> str:
    return gold_line(GoldItem.model_validate(fields)) + "\n"


def test_judge_gold_gate_and_input_refusals(monkeypatch, tmp_path):
    """Fake mode without --plumbing refuses exit 2 BEFORE any file access;
    prose_pairwise rows, malformed faithfulness ids, duplicate ids,
    rubric-version mismatches, and missing display fields all refuse exit 2
    before any judge call."""
    import app.eval_runner as runner_module

    fake_settings = Settings(database_uri=UNREACHABLE_URI, provider_mode="fake")
    monkeypatch.setattr(runner_module, "load_settings", lambda: fake_settings)

    def _explode(*_args, **_kwargs):
        raise AssertionError("the gate must fire before the input is read")

    monkeypatch.setattr(runner_module, "load_gold", _explode)
    assert _cmd_judge_gold(_judge_gold_args(plumbing=False)) == 2
    monkeypatch.undo()
    monkeypatch.setattr(runner_module, "load_settings", lambda: fake_settings)

    def refuses(*lines: str) -> bool:
        path = tmp_path / "in.jsonl"
        path.write_text("".join(lines), encoding="utf-8")
        return _cmd_judge_gold(_judge_gold_args(gold_in=path)) == 2

    assert refuses(
        _gold_row(
            item_id="cmp:x:1",
            category="prose_pairwise",
            rubric_version="pp-v1",
            question="q",
            reply_a="a",
            reply_b="b",
        )
    )
    assert refuses(
        _gold_row(
            item_id="ct:rf:001:fact2",  # single-fact rows must end :fact0
            category="reconstruction_faithfulness",
            rubric_version="rf-v1",
            fact="f",
            telling="t",
        )
    )
    assert refuses(
        _gold_row(
            item_id="ct:rf:002:fact0",
            category="reconstruction_faithfulness",
            rubric_version="rf-v1",
            fact="f",
            telling="t",
        )
        * 2  # same id twice -> duplicate join key
    )
    assert refuses(
        _gold_row(
            item_id="ct:sf:001",
            category="selective_forgetting",
            rubric_version="sf-v0",  # stale version tag
            question="q",
            reply="r",
            reference="ref",
        )
    )
    assert refuses(
        _gold_row(
            item_id="ct:abst:001",  # abstention without expected_behavior
            category="abstention",
            rubric_version="abst-v1",
            question="q",
            reply="r",
            reference="ref",
        )
    )


def test_judge_gold_plumbing_roundtrip(monkeypatch, tmp_path):
    """--plumbing happy path on the fake judge: artifact shape, rf base-id
    fan-in, label-index keys == input item_ids, and agreement joins with
    0 unmatched / 0 unlabeled. Never asserts which verdict the fake
    produced."""
    import app.eval_runner as runner_module

    fake_settings = Settings(database_uri=UNREACHABLE_URI, provider_mode="fake")
    monkeypatch.setattr(runner_module, "load_settings", lambda: fake_settings)

    rows = [
        GoldItem(
            item_id="ct:sf:001",
            category="selective_forgetting",
            rubric_version="sf-v1",
            question="q1",
            reply="r1",
            reference="ref1",
            superseded="old1",
            label="pass",
        ),
        GoldItem(
            item_id="ct:sf:002",  # superseded=None exercises the "(none)" fill
            category="selective_forgetting",
            rubric_version="sf-v1",
            question="q2",
            reply="r2",
            reference="ref2",
            label="fail",
        ),
        GoldItem(
            item_id="ct:abst:001",
            category="abstention",
            rubric_version="abst-v1",
            question="q3",
            reply="r3",
            reference="ref3",
            expected_behavior="abstain",
            label="fail",
        ),
        GoldItem(
            item_id="ct:abst:002",
            category="abstention",
            rubric_version="abst-v1",
            question="q4",
            reply="r4",
            reference="ref4",
            expected_behavior="answer",
            label="pass",
        ),
        GoldItem(
            item_id="ct:rf:001:fact0",
            category="reconstruction_faithfulness",
            rubric_version="rf-v1",
            fact="fact A",
            telling="telling A",
            label="supported",
        ),
        GoldItem(
            item_id="ct:rf:002:fact0",
            category="reconstruction_faithfulness",
            rubric_version="rf-v1",
            fact="fact B",
            telling="telling B",
            label="unsupported",
        ),
    ]
    gold_in = tmp_path / "constructed.jsonl"
    gold_in.write_text("".join(gold_line(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "artifact.json"
    assert _cmd_judge_gold(_judge_gold_args(gold_in=gold_in, out=out)) == 0

    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["verb"] == "judge-gold"
    assert artifact["plumbing_only"] is True
    assert artifact["provider_mode"] == "fake"
    assert "models" in artifact and "gold_in" in artifact
    judged = artifact["judged"]
    assert judged["judge_tokens"]["usd"] is None  # keyless: unpriced
    items = judged["items"]
    assert len(items) == 6
    rf_items = [i for i in items if i["category"] == "reconstruction_faithfulness"]
    assert {i["item_id"] for i in rf_items} == {"ct:rf:001", "ct:rf:002"}
    for item in rf_items:
        assert len(item["facts"]) == 1  # single-fact by the verb's contract
    for item in items:
        assert item["judge_failed"] is False
        validate_verdict(
            item["category"],
            item["verdict"],
            n_facts=len(item.get("facts", [])),
        )
    # The join contract: every input row id resolves in the label index.
    assert set(_judge_label_index(artifact)) == {r.item_id for r in rows}

    agreement_out = tmp_path / "agreement.json"
    _cmd_agreement(
        argparse.Namespace(gold=gold_in, artifact=out, kappa_bar=0.6, out=agreement_out)
    )  # exit code depends on the fake's verdicts — structural checks only
    report = json.loads(agreement_out.read_text(encoding="utf-8"))
    assert report["unmatched"] == 0
    assert report["unlabeled"] == 0
    assert {c: v["n"] for c, v in report["categories"].items()} == {
        "selective_forgetting": 2,
        "abstention": 2,
        "reconstruction_faithfulness": 2,
    }
