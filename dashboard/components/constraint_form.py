from __future__ import annotations

import re

import streamlit as st

_SYMBOLS = ["AMZN", "MSFT", "TSLA", "BTC-USD", "SPY", "QQQ"]
_VIOLATION_FIELDS = [
    "max_position_pct",
    "max_single_trade_pct",
    "max_leverage",
    "max_drawdown_pct",
    "min_risk_reward",
    "max_daily_loss_pct",
    "consistency_rule_pct",
    "max_open_positions",
]
_HH_MM = re.compile(r"^\d{2}:\d{2}$")


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def render_constraint_form(initial: dict, key_prefix: str = "cf") -> dict:
    left, right = st.columns(2)

    with left:
        st.markdown("**Position & Risk**")
        max_position_pct = st.slider(
            "Max Position %", 0.01, 0.50,
            _clamp(float(initial.get("max_position_pct", 0.15)), 0.01, 0.50),
            step=0.01, format="%.2f", key=f"{key_prefix}_max_position_pct",
        )
        max_single_trade_pct = st.slider(
            "Max Single Trade %", 0.01, 0.25,
            _clamp(float(initial.get("max_single_trade_pct", 0.05)), 0.01, 0.25),
            step=0.01, format="%.2f", key=f"{key_prefix}_max_single_trade_pct",
        )
        max_leverage = st.slider(
            "Max Leverage", 1.0, 5.0,
            _clamp(float(initial.get("max_leverage", 1.5)), 1.0, 5.0),
            step=0.1, format="%.1f", key=f"{key_prefix}_max_leverage",
        )
        max_drawdown_pct = st.slider(
            "Max Drawdown %", 0.01, 0.50,
            _clamp(float(initial.get("max_drawdown_pct", 0.10)), 0.01, 0.50),
            step=0.01, format="%.2f", key=f"{key_prefix}_max_drawdown_pct",
        )
        min_risk_reward = st.slider(
            "Min Risk/Reward", 0.5, 5.0,
            _clamp(float(initial.get("min_risk_reward", 1.5)), 0.5, 5.0),
            step=0.1, format="%.1f", key=f"{key_prefix}_min_risk_reward",
        )
        max_open_positions = st.number_input(
            "Max Open Positions", min_value=1, max_value=10,
            value=int(initial.get("max_open_positions", 3)),
            key=f"{key_prefix}_max_open_positions",
        )
        allowed_symbols = st.multiselect(
            "Allowed Symbols", _SYMBOLS,
            default=[s for s in initial.get("allowed_symbols", _SYMBOLS) if s in _SYMBOLS],
            key=f"{key_prefix}_allowed_symbols",
        )

    with right:
        st.markdown("**Daily, Consistency & Timing**")
        max_daily_loss_pct = st.slider(
            "Max Daily Loss %", 0.005, 0.10,
            _clamp(float(initial.get("max_daily_loss_pct", 0.02)), 0.005, 0.10),
            step=0.005, format="%.3f", key=f"{key_prefix}_max_daily_loss_pct",
        )
        consistency_rule_pct = st.slider(
            "Consistency Rule %", 0.10, 1.0,
            _clamp(float(initial.get("consistency_rule_pct", 0.30)), 0.10, 1.0),
            step=0.05, format="%.2f", key=f"{key_prefix}_consistency_rule_pct",
        )
        trading_cutoff_raw = st.text_input(
            "Trading Cutoff (HH:MM)",
            value=str(initial.get("trading_cutoff_time", "16:00")),
            key=f"{key_prefix}_trading_cutoff_time",
        )
        if trading_cutoff_raw and not _HH_MM.match(trading_cutoff_raw):
            st.warning("Enter time as HH:MM (e.g. 16:00)")
        max_rounds = st.number_input(
            "Max Rounds", min_value=1, max_value=5,
            value=int(initial.get("max_rounds", 3)),
            key=f"{key_prefix}_max_rounds",
        )
        abort_on_violations = st.multiselect(
            "Abort on Violations", _VIOLATION_FIELDS,
            default=[
                v for v in initial.get("abort_on_violations", [])
                if v in _VIOLATION_FIELDS
            ],
            key=f"{key_prefix}_abort_on_violations",
        )

    return {
        "max_position_pct": max_position_pct,
        "max_single_trade_pct": max_single_trade_pct,
        "max_leverage": max_leverage,
        "max_drawdown_pct": max_drawdown_pct,
        "min_risk_reward": min_risk_reward,
        "max_daily_loss_pct": max_daily_loss_pct,
        "consistency_rule_pct": consistency_rule_pct,
        "max_open_positions": int(max_open_positions),
        "max_rounds": int(max_rounds),
        "trading_cutoff_time": trading_cutoff_raw,
        "allowed_symbols": allowed_symbols,
        "abort_on_violations": abort_on_violations,
    }
