from __future__ import annotations

import json
from pathlib import Path

from player_coach.constraints.phase_profiles import (
    DEFAULT_PHASE_PROFILES,
    challenge_phase,
    load_phase_profiles,
)
from player_coach.constraints.regime_profiles import RegimeConstraintProfile


# ---------------------------------------------------------------- boundaries

def test_building_below_4pct():
    assert challenge_phase(0.0) == "building"
    assert challenge_phase(0.0399) == "building"


def test_conservation_band():
    assert challenge_phase(0.04) == "conservation"   # lower boundary
    assert challenge_phase(0.0549) == "conservation"


def test_lock_in_above_5_5pct():
    assert challenge_phase(0.055) == "lock_in"        # lower boundary
    assert challenge_phase(0.10) == "lock_in"


def test_negative_pnl_is_building():
    assert challenge_phase(-0.02) == "building"


# ------------------------------------------------------------ default profiles

def test_default_profiles_cover_all_phases():
    assert set(DEFAULT_PHASE_PROFILES) == {"building", "conservation", "lock_in"}


def test_building_profile_is_neutral():
    p = DEFAULT_PHASE_PROFILES["building"]
    assert p.max_single_trade_pct_mult == 1.0
    assert p.max_open_positions_override is None


def test_conservation_halves_size():
    assert DEFAULT_PHASE_PROFILES["conservation"].max_single_trade_pct_mult == 0.5


def test_lock_in_blocks_new_entries():
    assert DEFAULT_PHASE_PROFILES["lock_in"].max_open_positions_override == 0


# -------------------------------------------------------------------- loading

def test_load_phase_profiles_round_trip(tmp_path: Path):
    path = tmp_path / "phases.json"
    path.write_text(json.dumps({
        "lock_in": {
            "max_single_trade_pct_mult": 0.1, "max_position_pct_mult": 0.1,
            "min_risk_reward_mult": 1.0, "max_open_positions_override": 0,
        },
    }))
    profiles = load_phase_profiles(path)
    assert profiles["lock_in"] == RegimeConstraintProfile(0.1, 0.1, 1.0, 0)
