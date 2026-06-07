from __future__ import annotations

import json
from pathlib import Path

import pytest

from player_coach.constraints.schema import ConstraintSchema

_PRESET_DIR = Path("examples/constraints")
# Strategy presets only — regime_profiles.json is a different schema (F6).
_PRESETS = sorted(
    p for p in _PRESET_DIR.glob("*.json") if p.name != "regime_profiles.json"
)


@pytest.mark.parametrize("preset", _PRESETS, ids=lambda p: p.name)
def test_preset_declares_atr_and_vwap_constraints(preset: Path):
    # F8/F9 added these constraints; presets must declare them explicitly rather
    # than silently inheriting the schema defaults.
    data = json.loads(preset.read_text())
    assert "min_stop_atr_multiple" in data, f"{preset.name} missing min_stop_atr_multiple"
    assert "prefer_entry_below_vwap" in data, f"{preset.name} missing prefer_entry_below_vwap"


@pytest.mark.parametrize("preset", _PRESETS, ids=lambda p: p.name)
def test_preset_loads_into_schema(preset: Path):
    schema = ConstraintSchema.from_dict(json.loads(preset.read_text()))
    assert schema.min_stop_atr_multiple > 0
    assert isinstance(schema.prefer_entry_below_vwap, bool)
