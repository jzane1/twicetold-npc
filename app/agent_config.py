"""Validation at agent-config write boundaries; stored dictionaries stay sparse."""

from __future__ import annotations

import math

from app.config import SERVICE_DEFAULTS, WEIGHT_MAX

# These defaults belong to a process, never an individual agent.
PROCESS_ONLY = {
    "deferred_poll_seconds",
    "deferred_batch_size",
    "deferred_max_attempts",
    "reflection_poll_seconds",
    "reflection_worker_batch",
    "compiler_poll_seconds",
    "compiler_worker_batch",
}
INTEGER_MIN = {
    "gist_max_spans": 1,
    "retrieval_top_k": 1,
    "gate_fetch_k": 1,
    "gate_damper_fruitless_max": 1,
    "lexical_fetch_k": 0,
    "reflection_sample_k": 1,
    "reflection_min_episodes": 1,
    "reflection_rrr_window": 1,
    "reflection_consolidate_at": 1,
    "compiler_window_k": 1,
    "escalation_min_base_spans": 0,
}
UNIT_INTERVAL = {
    "importance_neutral",
    "escalation_importance_threshold",
    "escalation_affect_threshold",
    "nlp_confidence_threshold",
    "typology_confidence_default",
    "importance_norm_floor",
    "reconstruction_theta",
    "metric_gist_match_threshold",
    "reflection_rrr_threshold",
    "dissonance_challenge_weight_default",
}
SWITCHES = {
    "reconstruction_gist_constraint",
    "gate_enabled",
    "deferred_writes_enabled",
    "reflection_worker_enabled",
    "compiler_worker_enabled",
}
POSITIVE = {
    "tau_fallback_seconds",
    "reconstruction_band_quantum",
    "context_time_scale_seconds",
    "reflection_pressure_norm",
}
SPECIAL = {
    "decay_classes",
    "decay_class_default",
    "text_search_config",
    "scene_types",
    "typology_default",
    "dialogue_fallback_line",
}


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def _label(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a nonempty string without edge whitespace")


def validate_agent_config(config: dict | None) -> dict | None:
    """Reject typos and unsafe values without filling in service defaults.

    Retired escalation keys remain accepted for existing corpus compatibility.
    Explicit null numeric overrides retain the existing 'use default' meaning.
    """
    if config is None:
        return None
    for key, value in config.items():
        if key in PROCESS_ONLY:
            raise ValueError(f"{key} is process-level and cannot be set per agent")
        if key not in SERVICE_DEFAULTS and key not in SPECIAL:
            raise ValueError(f"unknown agent configuration key: {key}")
        if key not in SERVICE_DEFAULTS or value is None:
            continue
        number = _number(value, key)
        if number < 0 or (key in POSITIVE and number == 0):
            bound = "> 0" if key in POSITIVE else ">= 0"
            raise ValueError(f"{key} must be {bound}")
        if key in UNIT_INTERVAL and number > 1:
            raise ValueError(f"{key} must be between 0 and 1")
        if key in SWITCHES and number not in (0, 1):
            raise ValueError(f"{key} must be 0 or 1")
        if key in INTEGER_MIN and (
            not number.is_integer() or number < INTEGER_MIN[key]
        ):
            raise ValueError(f"{key} must be an integer >= {INTEGER_MIN[key]}")
        if key == "retrieval_overfetch_factor" and number < 1:
            raise ValueError(f"{key} must be >= 1")
        if key == "reconstruction_band_quantum" and number > 1:
            raise ValueError(f"{key} must be <= 1")
        if key in {"drift_budget_threshold", "gate_novelty_threshold"} and number > 2:
            raise ValueError(f"{key} must be <= 2 (cosine distance)")
        if key.startswith("weight_") and number > WEIGHT_MAX:
            raise ValueError(f"{key} must be <= {WEIGHT_MAX}")
        if key == "dissonance_rigidity_default" and not 0.5 <= number <= 2:
            raise ValueError(f"{key} must be between 0.5 and 2")

    classes = config.get("decay_classes")
    if classes is not None:
        if not isinstance(classes, dict):
            raise ValueError("decay_classes must be an object of label: seconds")
        for label, seconds in classes.items():
            _label(label, "decay class label")
            if _number(seconds, "decay class seconds") <= 0:
                raise ValueError("decay class seconds must be > 0")
    default = config.get("decay_class_default")
    if default is not None:
        _label(default, "decay_class_default")
        if default not in (classes or {}):
            raise ValueError("decay_class_default must name a configured decay class")
    for key in ("text_search_config", "dialogue_fallback_line"):
        if key in config:
            _label(config[key], key)
    if "typology_default" in config and config["typology_default"] not in (
        "observed",
        "told",
        "inferred",
        "reflected",
    ):
        raise ValueError(
            "typology_default must be observed, told, inferred, or reflected"
        )
    if "scene_types" in config:
        values = config["scene_types"]
        if not isinstance(values, list):
            raise ValueError("scene_types must be a list of strings")
        for value in values:
            _label(value, "scene_types entry")
        if len(values) != len(set(values)):
            raise ValueError("scene_types must not contain duplicates")
    return config
