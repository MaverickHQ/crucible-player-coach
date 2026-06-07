from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Callable

from player_coach.constraints.regime_profiles import (
    DEFAULT_REGIME_PROFILES,
    RegimeConstraintProfile,
)
from player_coach.constraints.schema import ConstraintSchema

# A resolver stage is a pure transform: (schema, context) -> new schema.
# Context is the world-state dict (after market enrichment), so a stage can read
# regime_label (F6), garch_vol (F7), challenge_phase (F12), etc.
Stage = Callable[[ConstraintSchema, dict[str, Any]], ConstraintSchema]


class ConstraintResolver:
    """Composes pure stages into the effective constraints for one exchange.

    The base schema (from the evidence-driven ``ConstraintDeriver``) is static;
    the resolver layers per-exchange adjustments on top — regime overlay (F6),
    GARCH scaling (F7), challenge phase (F12) — each as an independent stage.
    Stages never mutate their input; they return a new schema.
    """

    def __init__(self, stages: list[Stage] | None = None) -> None:
        self._stages: list[Stage] = list(stages or [])

    def resolve(
        self, base: ConstraintSchema, context: dict[str, Any]
    ) -> ConstraintSchema:
        schema = base
        for stage in self._stages:
            schema = stage(schema, context)
        return schema


def apply_regime_profile(
    schema: ConstraintSchema, profile: RegimeConstraintProfile
) -> ConstraintSchema:
    """Return a new schema with the regime profile's multipliers applied."""
    return replace(
        schema,
        max_single_trade_pct=round(
            schema.max_single_trade_pct * profile.max_single_trade_pct_mult, 6
        ),
        max_position_pct=round(
            schema.max_position_pct * profile.max_position_pct_mult, 6
        ),
        min_risk_reward=round(
            schema.min_risk_reward * profile.min_risk_reward_mult, 6
        ),
        # The override is a ceiling, never a floor: a conservative profile must
        # only tighten, so cap at the base rather than risk loosening a stricter
        # preset (e.g. base max_open_positions=1 must not be raised to 2).
        max_open_positions=(
            min(schema.max_open_positions, profile.max_open_positions_override)
            if profile.max_open_positions_override is not None
            else schema.max_open_positions
        ),
    )


def regime_overlay(
    profiles: dict[str, RegimeConstraintProfile] | None = None,
) -> Stage:
    """Resolver stage (F6) that tightens/relaxes constraints by regime label.

    Reads ``context["regime_label"]``; a missing or unrecognised label falls
    back to the conservative ``unknown`` profile.
    """
    profiles = profiles or DEFAULT_REGIME_PROFILES

    def stage(schema: ConstraintSchema, context: dict[str, Any]) -> ConstraintSchema:
        label = context.get("regime_label") or "unknown"
        profile = profiles.get(label, profiles["unknown"])
        return apply_regime_profile(schema, profile)

    return stage


def garch_scale(
    target_vol: float = 0.01,
    floor: float = 0.5,
    calm_cap: float = 1.25,
    stressed_cap: float = 1.0,
) -> Stage:
    """Resolver stage (F7) that scales trade size by the GARCH vol forecast.

    Volatility targeting: ``scale = clamp(target_vol / garch_vol, floor, cap)``,
    applied to ``max_single_trade_pct`` — a higher forecast shrinks size.

    Conditions on F6's regime: in ``high_vol`` / ``unknown`` the cap is
    ``stressed_cap`` (1.0 → never *increase* size on top of a stressed regime);
    in calm regimes a modest increase up to ``calm_cap`` is allowed. A missing
    or non-positive ``garch_vol`` leaves the schema untouched.
    """

    def stage(schema: ConstraintSchema, context: dict[str, Any]) -> ConstraintSchema:
        garch_vol = context.get("garch_vol")
        if garch_vol is None or not math.isfinite(garch_vol) or garch_vol <= 0:
            return schema
        regime = context.get("regime_label") or "unknown"
        cap = stressed_cap if regime in ("high_vol", "unknown") else calm_cap
        scale = min(max(target_vol / garch_vol, floor), cap)
        return replace(
            schema,
            max_single_trade_pct=round(schema.max_single_trade_pct * scale, 6),
        )

    return stage


def clamp_invariants() -> Stage:
    """Final resolver stage enforcing constraint coherence.

    Per-field scaling (e.g. ``garch_scale`` touches only single-trade size) can
    push ``max_single_trade_pct`` above ``max_position_pct`` — an incoherent pair
    (one trade larger than the whole book). Clamp single down to position. Append
    this last in the resolver pipeline.
    """

    def stage(schema: ConstraintSchema, context: dict[str, Any]) -> ConstraintSchema:
        if schema.max_single_trade_pct <= schema.max_position_pct:
            return schema
        return replace(schema, max_single_trade_pct=schema.max_position_pct)

    return stage
