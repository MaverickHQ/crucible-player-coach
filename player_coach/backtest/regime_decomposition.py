from __future__ import annotations

from typing import Any


def decompose_by_regime(exchanges: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Group exchange artifacts by their world-state ``regime_label`` and report
    per-regime ``count`` and ``approve_rate`` (F19).

    Surfaces whether a configuration only performs in one regime — a config with
    a high approval rate in ``low_vol`` but poor in ``high_vol`` is regime-fragile.
    Exchanges without a regime label are grouped under ``"unknown"``.
    """
    groups: dict[str, dict[str, int]] = {}
    for ex in exchanges:
        regime = (ex.get("world_state") or {}).get("regime_label") or "unknown"
        g = groups.setdefault(regime, {"count": 0, "approved": 0})
        g["count"] += 1
        if ex.get("outcome") == "APPROVE":
            g["approved"] += 1

    return {
        regime: {
            "count": g["count"],
            "approve_rate": g["approved"] / g["count"] if g["count"] else 0.0,
        }
        for regime, g in groups.items()
    }
