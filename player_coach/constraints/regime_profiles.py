from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RegimeConstraintProfile:
    """Multipliers applied to base constraints for a detected market regime.

    A multiplier of 1.0 leaves the base value unchanged. ``max_open_positions``
    is an absolute override (or ``None`` to keep the base) because halving a
    small integer position cap is meaningless.
    """

    max_single_trade_pct_mult: float = 1.0
    max_position_pct_mult: float = 1.0
    min_risk_reward_mult: float = 1.0
    max_open_positions_override: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegimeConstraintProfile:
        return cls(
            max_single_trade_pct_mult=data.get("max_single_trade_pct_mult", 1.0),
            max_position_pct_mult=data.get("max_position_pct_mult", 1.0),
            min_risk_reward_mult=data.get("min_risk_reward_mult", 1.0),
            max_open_positions_override=data.get("max_open_positions_override"),
        )


# Conservative-by-default: high vol AND unknown both tighten. low/medium are the
# baseline (1.0x). These are the shipped defaults; override via JSON.
DEFAULT_REGIME_PROFILES: dict[str, RegimeConstraintProfile] = {
    "low_vol": RegimeConstraintProfile(),
    "medium_vol": RegimeConstraintProfile(),
    "high_vol": RegimeConstraintProfile(
        max_single_trade_pct_mult=0.6,
        max_position_pct_mult=0.6,
        min_risk_reward_mult=1.3,
        max_open_positions_override=2,
    ),
    "unknown": RegimeConstraintProfile(
        max_single_trade_pct_mult=0.6,
        max_position_pct_mult=0.6,
        min_risk_reward_mult=1.3,
        max_open_positions_override=2,
    ),
}


def load_regime_profiles(path: str | Path) -> dict[str, RegimeConstraintProfile]:
    """Load regime profiles from JSON, falling back to defaults per label."""
    data = json.loads(Path(path).read_text())
    profiles = dict(DEFAULT_REGIME_PROFILES)
    for label, raw in data.items():
        profiles[label] = RegimeConstraintProfile.from_dict(raw)
    return profiles
