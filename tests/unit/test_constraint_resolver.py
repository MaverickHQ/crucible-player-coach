from __future__ import annotations

import json
from pathlib import Path

from player_coach.constraints.regime_profiles import (
    DEFAULT_REGIME_PROFILES,
    RegimeConstraintProfile,
    load_regime_profiles,
)
from player_coach.constraints.resolver import (
    ConstraintResolver,
    garch_scale,
    regime_overlay,
)
from player_coach.constraints.schema import ConstraintSchema


def _base_schema() -> ConstraintSchema:
    return ConstraintSchema(
        max_position_pct=0.10,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage", "max_drawdown_pct"],
    )


def _resolve(regime_label: str | None) -> ConstraintSchema:
    ctx = {} if regime_label is None else {"regime_label": regime_label}
    resolver = ConstraintResolver([regime_overlay()])
    return resolver.resolve(_base_schema(), ctx)


# ----------------------------------------------------------- regime tightening

def test_high_vol_tightens_trade_size():
    assert _resolve("high_vol").max_single_trade_pct == 0.03  # 0.05 * 0.6


def test_high_vol_tightens_position_size():
    assert _resolve("high_vol").max_position_pct == 0.06  # 0.10 * 0.6


def test_high_vol_raises_risk_reward_requirement():
    assert _resolve("high_vol").min_risk_reward == 1.95  # 1.5 * 1.3


def test_high_vol_caps_open_positions():
    assert _resolve("high_vol").max_open_positions == 2


def test_low_vol_leaves_constraints_unchanged():
    s = _resolve("low_vol")
    assert s.max_single_trade_pct == 0.05
    assert s.min_risk_reward == 1.5
    assert s.max_open_positions == 3


def test_unknown_uses_conservative_profile():
    unknown = _resolve("unknown")
    high = _resolve("high_vol")
    assert unknown.max_single_trade_pct == high.max_single_trade_pct
    assert unknown.max_open_positions == high.max_open_positions


def test_missing_regime_label_defaults_conservative():
    # No regime_label in ctx → fall back to the conservative profile.
    assert _resolve(None).max_single_trade_pct == 0.03


# ------------------------------------------------------------- pipeline purity

def test_resolve_does_not_mutate_base_schema():
    base = _base_schema()
    ConstraintResolver([regime_overlay()]).resolve(base, {"regime_label": "high_vol"})
    assert base.max_single_trade_pct == 0.05  # original untouched
    assert base.max_open_positions == 3


def test_empty_resolver_returns_equivalent_schema():
    base = _base_schema()
    out = ConstraintResolver([]).resolve(base, {"regime_label": "high_vol"})
    assert out.to_dict() == base.to_dict()


# --------------------------------------------------------------- profile config

def test_default_profiles_cover_all_labels():
    assert set(DEFAULT_REGIME_PROFILES) == {
        "low_vol", "medium_vol", "high_vol", "unknown"
    }


def test_load_regime_profiles_round_trip(tmp_path: Path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({
        "high_vol": {
            "max_single_trade_pct_mult": 0.5,
            "max_position_pct_mult": 0.5,
            "min_risk_reward_mult": 1.4,
            "max_open_positions_override": 1,
        },
    }))
    profiles = load_regime_profiles(path)
    assert profiles["high_vol"] == RegimeConstraintProfile(0.5, 0.5, 1.4, 1)


# ----------------------------------------------------- F7 garch_scale stage

def _resolve_garch(garch_vol: float | None, regime_label: str = "low_vol"):
    ctx: dict = {"regime_label": regime_label}
    if garch_vol is not None:
        ctx["garch_vol"] = garch_vol
    return ConstraintResolver([garch_scale()]).resolve(_base_schema(), ctx)


def test_high_forecast_vol_cuts_trade_size():
    # target 0.01 / forecast 0.04 = 0.25, floored at 0.5 → 0.05 * 0.5 = 0.025.
    assert _resolve_garch(0.04).max_single_trade_pct == 0.025


def test_calm_low_vol_regime_allows_modest_increase():
    # forecast 0.005 → 2.0, capped at calm_cap 1.25 → 0.05 * 1.25 = 0.0625.
    assert _resolve_garch(0.005, "low_vol").max_single_trade_pct == 0.0625


def test_stressed_regime_caps_scale_at_one():
    # Same low forecast, but a stressed regime forbids *increasing* size.
    assert _resolve_garch(0.005, "high_vol").max_single_trade_pct == 0.05


def test_regime_conditioning_changes_outcome():
    calm = _resolve_garch(0.005, "low_vol").max_single_trade_pct
    stressed = _resolve_garch(0.005, "high_vol").max_single_trade_pct
    assert calm > stressed  # identical forecast, different regime → different size


def test_missing_garch_vol_means_no_scaling():
    assert _resolve_garch(None).max_single_trade_pct == 0.05


def test_zero_garch_vol_means_no_scaling():
    assert _resolve_garch(0.0).max_single_trade_pct == 0.05


def test_size_is_monotonic_non_increasing_in_forecast():
    low = _resolve_garch(0.005).max_single_trade_pct
    mid = _resolve_garch(0.02).max_single_trade_pct
    high = _resolve_garch(0.04).max_single_trade_pct
    assert low >= mid >= high


def test_garch_scale_does_not_mutate_base():
    base = _base_schema()
    ConstraintResolver([garch_scale()]).resolve(
        base, {"garch_vol": 0.04, "regime_label": "low_vol"}
    )
    assert base.max_single_trade_pct == 0.05


def test_regime_then_garch_compose_in_pipeline():
    # high_vol overlay (0.6x) then garch cut (0.5x) → 0.05 * 0.6 * 0.5 = 0.015.
    resolver = ConstraintResolver([regime_overlay(), garch_scale()])
    out = resolver.resolve(
        _base_schema(), {"regime_label": "high_vol", "garch_vol": 0.04}
    )
    assert out.max_single_trade_pct == 0.015
