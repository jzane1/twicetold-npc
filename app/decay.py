"""decay.py: the decay math (architecture §4.2), one formula, one implementation.

    tau_effective = tau_base(decay_class) * (1 + k_importance * importance_raw)
    recency       = exp(-age / tau_effective)        # age clamped at >= 0

Consumers: the read path's recency score component (app\\retrieval.py) and
the reconstruction theta/band evaluation (app\\reconstruction.py): the recency
term and detail decay share tau_effective exactly. Architecture's decayed detail
strength is this same exponential (decay = 1 - recency); reconstruction
evaluates it at the scene-frozen basis, scoring at the per-call as_of.

Invariant note (architecture.md §2): recency decay and bi-temporal invalidation are
distinct mechanisms. Everything in this module moves scores only — candidacy
is decided by invalid_at in SQL, never here.
"""

from __future__ import annotations

import math

from app.config import Settings, agent_knob


def resolve_tau_base(
    decay_class: str | None, agent_config: dict, settings: Settings
) -> float:
    """Label -> tau_base seconds, the same resolution rule as the write path's
    _resolve_decay_class: the stored label if mapped, else the agent's default
    class, else the tau_fallback_seconds knob — a read never fails on a
    resolvable row (rows flagged decay_class_unknown carry the default label
    or the sentinel, both of which resolve here)."""
    decay_map = agent_config.get("decay_classes") or {}
    if decay_class is not None and decay_class in decay_map:
        return float(decay_map[decay_class])
    default_label = agent_config.get("decay_class_default")
    if default_label is not None and default_label in decay_map:
        return float(decay_map[default_label])
    return agent_knob(agent_config, "tau_fallback_seconds", settings)


def tau_effective(tau_base: float, k_importance: float, importance_raw: float) -> float:
    """Importance slows decay: tau_base * (1 + k_importance * importance_raw)."""
    return tau_base * (1.0 + k_importance * importance_raw)


def recency(age_seconds: float, tau_eff: float) -> float:
    """exp(-age/tau) in (0, 1]; age clamps at 0 so a future-dated valid_at
    (relative to as_of) caps at 1.0 rather than scoring above fresh rows."""
    return math.exp(-max(age_seconds, 0.0) / tau_eff)
