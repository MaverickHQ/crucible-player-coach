from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from player_coach.constraints.regime_profiles import RegimeConstraintProfile

# Profit bands (cumulative P&L / challenge starting balance).
BUILDING_MAX = 0.04
CONSERVATION_MAX = 0.055


def challenge_phase(
    pnl_pct: float,
    building_max: float = BUILDING_MAX,
    conservation_max: float = CONSERVATION_MAX,
) -> str:
    """Map challenge profit fraction to a phase.

    ``building`` while below ``building_max``; ``conservation`` from there up to
    ``conservation_max``; ``lock_in`` at or above ``conservation_max``. A
    negative P&L is ``building``.
    """
    if pnl_pct < building_max:
        return "building"
    if pnl_pct < conservation_max:
        return "conservation"
    return "lock_in"


# Reuses F6's profile dataclass. ``lock_in`` sets max_open_positions to 0 which —
# via the mechanical checker — blocks new entries while allowing holds/exits.
DEFAULT_PHASE_PROFILES: dict[str, RegimeConstraintProfile] = {
    "building": RegimeConstraintProfile(),
    "conservation": RegimeConstraintProfile(
        max_single_trade_pct_mult=0.5,
        max_position_pct_mult=0.5,
        min_risk_reward_mult=1.2,
    ),
    "lock_in": RegimeConstraintProfile(
        max_single_trade_pct_mult=0.25,
        max_position_pct_mult=0.25,
        min_risk_reward_mult=1.0,
        max_open_positions_override=0,
    ),
}


def load_phase_profiles(path: str | Path) -> dict[str, RegimeConstraintProfile]:
    """Load phase profiles from JSON, falling back to defaults per phase."""
    data = json.loads(Path(path).read_text())
    profiles = dict(DEFAULT_PHASE_PROFILES)
    for phase, raw in data.items():
        base = DEFAULT_PHASE_PROFILES.get(phase)
        # Backfill missing fields from the default profile so a partial override
        # (e.g. lock_in without max_open_positions_override) doesn't silently
        # drop the entry block.
        merged = {**asdict(base), **raw} if base is not None else raw
        profiles[phase] = RegimeConstraintProfile.from_dict(merged)
    return profiles
