"""Set J — eval-harness stage 4: the fixed-gist ablation's structural surface
(docs\\eval-harness.md stage 4; the 2026-08-12 workaround + fork-11 rulings).

Covers the knob's presence and plumbing, the pure no-gist assembly shapes
(default paths byte-identical to the pre-stage-4 floor), the committed
ablation corpus census, the OFF-arm scenario copy, the real-mode gate, and
one plumbing two-arm end-to-end on scratch settings (nlp mark — it drives
the real write pass, the Set H/I precedent). Never asserts on prose;
system-prompt and item-key assertions are byte-identity of assembled INPUT,
never model output.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import pytest

from app.config import SERVICE_DEFAULTS, Settings, agent_knob
from app.db import ReconstructionSource
from app.eval_runner import _cmd_ablation, _knob_off_scenario, ablation_run
from app.eval_scenarios import Scenario, assert_corpus_shape, load_scenarios
from app.reconstruction import (
    _SYSTEM_TASK,
    _SYSTEM_TASK_NO_GIST,
    assemble_reconstruction_prompt,
    build_reconstruction_item,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ABLATION_FIXTURE = REPO_ROOT / "data" / "eval" / "corpora" / "ablation-fixture.jsonl"

# TEST-NET-1 (RFC 5737), the Set H convention.
UNREACHABLE_URI = "postgresql://u:p@192.0.2.1:5432/postgres"

_ORIGINAL = ReconstructionSource(
    observation_text="The rope frayed at the post. It was spliced by noon.",
    spans=[(0, 28)],
    anchor_content="The rope frayed at the post. It was spliced by noon.",
    anchor_cause="original",
)
_CORRECTED = ReconstructionSource(
    observation_text="The rope frayed at the post. It was spliced by noon.",
    spans=[(0, 28)],
    anchor_content="The rope never frayed; the post itself split.",
    anchor_cause="authorial_correction",
)


def test_knob_default_and_agent_knob():
    """The stage-4 knob exists with the kill-switch default; agent_knob
    resolves the default and a per-agent 0.0 override."""
    assert SERVICE_DEFAULTS["reconstruction_gist_constraint"] == 1.0
    settings = Settings(database_uri=UNREACHABLE_URI, provider_mode="fake")
    assert agent_knob({}, "reconstruction_gist_constraint", settings) == 1.0
    assert (
        agent_knob(
            {"reconstruction_gist_constraint": 0.0},
            "reconstruction_gist_constraint",
            settings,
        )
        == 0.0
    )


def test_build_item_gist_constraint_semantics():
    """Default == explicit True (byte parity); False blanks the gist on an
    original-anchored source only; a correction-anchored chain keeps the
    corrected head regardless of the flag (fork 11)."""
    default_item = build_reconstruction_item("m1", _ORIGINAL, 0.5, "telling")
    on_item = build_reconstruction_item(
        "m1", _ORIGINAL, 0.5, "telling", gist_constraint=True
    )
    assert default_item == on_item
    assert default_item.gist == "The rope frayed at the post."

    off_item = build_reconstruction_item(
        "m1", _ORIGINAL, 0.5, "telling", gist_constraint=False
    )
    assert off_item.gist == ""
    assert off_item.thinned_detail == default_item.thinned_detail
    assert off_item.current_telling == default_item.current_telling

    for flag in (True, False):
        corrected = build_reconstruction_item(
            "m2", _CORRECTED, 0.5, "telling", gist_constraint=flag
        )
        assert corrected.gist == _CORRECTED.anchor_content
        assert corrected.thinned_detail == ""


def test_assemble_no_gist_prompt_shapes():
    """Default assembly is byte-identical to explicit True; False swaps the
    task constant and omits the 'gist' key from every item while preserving
    the remaining key order."""
    items = [
        build_reconstruction_item("m1", _ORIGINAL, 0.5, "telling one"),
        build_reconstruction_item("m2", _ORIGINAL, 0.5, "telling two"),
    ]
    default_system, default_user = assemble_reconstruction_prompt("doc", items)
    on_system, on_user = assemble_reconstruction_prompt(
        "doc", items, include_gist_constraint=True
    )
    assert (default_system, default_user) == (on_system, on_user)
    assert default_system.endswith(_SYSTEM_TASK)
    for entry in json.loads(default_user):
        assert list(entry) == [
            "memory_id",
            "gist",
            "detail",
            "current_telling",
            "detail_retention",
        ]
        assert entry["detail_retention"] == 0.5

    off_system, off_user = assemble_reconstruction_prompt(
        "doc", items, include_gist_constraint=False
    )
    assert off_system.endswith(_SYSTEM_TASK_NO_GIST)
    assert "[identity]" in off_system  # the identity block survives the swap
    for entry in json.loads(off_user):
        assert list(entry) == [
            "memory_id",
            "detail",
            "current_telling",
            "detail_retention",
        ]
        assert entry["detail_retention"] == 0.5


def test_ablation_fixture_census_and_knob_copy():
    """The committed corpus parses under the corpus shape (observe/as_of
    only — fork 11 by construction), pins the decay knobs for cross-arm band
    determinism, and _knob_off_scenario injects the 0 knob without touching
    the authored scenario."""
    corpus = load_scenarios(ABLATION_FIXTURE)
    assert len(corpus) == 3
    for scenario in corpus:
        assert_corpus_shape(scenario)
        kinds = [event.kind for event in scenario.events]
        assert kinds.count("observe") == 8
        assert kinds.count("as_of") == 2
        assert set(kinds) == {"observe", "as_of"}
        config = scenario.agent.config
        classes = config["decay_classes"]
        assert classes["episodic"] == classes["semantic"] == 2160000.0
        assert config["decay_k_importance"] == 0.0

        off = _knob_off_scenario(scenario)
        assert off.agent.config["reconstruction_gist_constraint"] == 0.0
        assert "reconstruction_gist_constraint" not in scenario.agent.config
        assert off.agent.config["decay_k_importance"] == 0.0
        assert off.scenario_id == scenario.scenario_id


def test_ablation_gate_exit2(monkeypatch):
    """Fake mode without --plumbing refuses with exit 2 BEFORE any corpus
    read or provisioning."""
    import app.eval_runner as runner_module

    fake_settings = Settings(database_uri=UNREACHABLE_URI, provider_mode="fake")
    monkeypatch.setattr(runner_module, "load_settings", lambda: fake_settings)

    def _explode(*_args, **_kwargs):
        raise AssertionError("the gate must fire before corpus/provisioning")

    monkeypatch.setattr(runner_module, "load_scenarios", _explode)
    monkeypatch.setattr(runner_module, "provision_scratch", _explode)
    args = argparse.Namespace(
        corpus=Path("never-read.jsonl"),
        age_days=30.0,
        probe="Tell me about everything you remember.",
        out=None,
        database_uri=None,
        keep_db=False,
        plumbing=False,
    )
    assert _cmd_ablation(args) == 2


_E2E_CORPUS = [
    {
        "scenario_id": "set-j-abl-one",
        "agent": {
            "name": "set-j-abl-one",
            "seed_identity": "A keeper of small facts by the weir.",
            "diagnosticity_goal": "what changed and who changed it",
            "config": {
                "decay_classes": {"episodic": 2160000.0, "semantic": 2160000.0},
                "decay_class_default": "semantic",
                "importance_norm_floor": 1.0,
                "decay_k_importance": 0.0,
            },
        },
        "events": [
            {"kind": "as_of", "at": "2026-06-01T09:00:00+00:00"},
            {
                "kind": "observe",
                "text": "The weir gate jammed with drift wood at dawn.",
            },
            {
                "kind": "observe",
                "text": "A heron took station on the third post all morning.",
            },
            {
                "kind": "observe",
                "text": "The eel count came to forty in the night traps.",
            },
        ],
    },
    {
        "scenario_id": "set-j-abl-two",
        "agent": {
            "name": "set-j-abl-two",
            "seed_identity": "A keeper of small facts by the kiln.",
            "diagnosticity_goal": "what changed and who changed it",
            "config": {
                "decay_classes": {"episodic": 2160000.0, "semantic": 2160000.0},
                "decay_class_default": "semantic",
                "importance_norm_floor": 1.0,
                "decay_k_importance": 0.0,
            },
        },
        "events": [
            {"kind": "as_of", "at": "2026-06-01T09:00:00+00:00"},
            {
                "kind": "observe",
                "text": "The kiln cracked along the north seam in the frost.",
            },
            {
                "kind": "observe",
                "text": "Two cartloads of clay came up from the pit at Reed Lane.",
            },
        ],
    },
]


@pytest.mark.nlp
def test_ablation_plumbing_end_to_end(scene):
    """The two-arm rig on scratch settings with fake providers: knob
    provenance per arm, every observe paired on (scenario_id, memory_ref)
    with distinct per-arm memory UUIDs, drift checked in both arms, honest
    summary keys, JSON-serializable report. Never asserts on prose."""
    corpus = [Scenario.model_validate(payload) for payload in _E2E_CORPUS]
    report = asyncio.run(
        ablation_run(
            scene.settings,
            scene.settings,
            corpus,
            age_days=30.0,
            probe="Tell me about everything you remember.",
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert report["verb"] == "ablation"
    assert report["plumbing_only"] is True
    assert [arm["name"] for arm in report["arms"]] == ["gist-on", "gist-off"]
    assert report["arms"][0]["knob"] == {"reconstruction_gist_constraint": 1.0}
    assert report["arms"][1]["knob"] == {"reconstruction_gist_constraint": 0.0}

    paired = report["paired"]
    assert len(paired) == 5  # 3 + 2 observes, every ref paired
    for row in paired:
        assert row["memory_id_on"] != row["memory_id_off"]  # distinct per-arm rows
        assert row["band_on"] == row["band_off"]  # pinned decay => same band
        assert isinstance(row["band_on"], int)
        assert row["distance_on"] is not None
        assert row["distance_off"] is not None
        assert row["delta_abs"] is not None
        assert row["reconstructed_on"] is True or row["over_budget_on"] is True
        assert row["reconstructed_off"] is True or row["over_budget_off"] is True

    summary = report["paired_summary"]
    assert summary["n_paired"] == 5
    assert summary["n_checked_both"] == 5
    assert summary["unpaired_refs"] == 0
    assert summary["pairs_missing_a_distance"] == 0
    assert summary["band_mismatches"] == 0
    assert summary["mean_abs_delta"] is not None
    json.dumps(report)
