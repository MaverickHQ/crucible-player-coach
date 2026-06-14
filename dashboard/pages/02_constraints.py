from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.components.constraint_form import (
    render_constraint_form,
    _SYMBOLS,
    _VIOLATION_FIELDS,
)
from player_coach.constraints.deriver import ConstraintDeriver
from dashboard.db import get_store

# ---------------------------------------------------------------------------
# Load presets from examples/constraints/
# ---------------------------------------------------------------------------

_PRESET_DIR = Path(__file__).parents[2] / "examples" / "constraints"
_PRESET_NAMES = ["conservative", "moderate", "aggressive", "strict", "futures_compatible"]

_PRESETS: dict[str, dict] = {}
for _name in _PRESET_NAMES:
    _path = _PRESET_DIR / f"{_name}.json"
    if _path.exists():
        _PRESETS[_name] = json.loads(_path.read_text())

if not _PRESETS:
    _PRESETS["moderate"] = {
        "max_position_pct": 0.15, "max_single_trade_pct": 0.05,
        "max_leverage": 1.5, "max_drawdown_pct": 0.10,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 3, "min_risk_reward": 1.5,
        "max_rounds": 3, "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
    }

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Derive from History
# ---------------------------------------------------------------------------

st.title("Constraints")

with st.expander("Derive from History", expanded=False):
    _store = get_store()
    _strategies = _store.get_strategies()

    if _strategies:
        _strategy_options = {"All history (no strategy filter)": None} | {
            s["name"] or s["strategy_id"]: s["strategy_id"] for s in _strategies
        }
    else:
        _strategy_options = {"All history (no strategy filter)": None}

    _selected_label = st.selectbox(
        "Strategy", list(_strategy_options.keys()), key="derive_strategy"
    )
    _selected_sid = _strategy_options[_selected_label]

    if st.button("Derive Constraints", key="derive_btn"):
        _schema = ConstraintDeriver.from_db(_store, strategy_id=_selected_sid).derive()
        _derived = _schema.to_dict()
        st.session_state["_derived_constraints"] = _derived
        st.session_state["cp_max_position_pct"] = float(_derived.get("max_position_pct", 0.15))
        st.session_state["cp_max_single_trade_pct"] = float(_derived.get("max_single_trade_pct", 0.05))
        st.session_state["cp_max_leverage"] = float(_derived.get("max_leverage", 1.5))
        st.session_state["cp_max_drawdown_pct"] = float(_derived.get("max_drawdown_pct", 0.10))
        st.session_state["cp_min_risk_reward"] = float(_derived.get("min_risk_reward", 1.5))
        st.session_state["cp_max_daily_loss_pct"] = float(_derived.get("max_daily_loss_pct", 0.02))
        st.session_state["cp_consistency_rule_pct"] = float(_derived.get("consistency_rule_pct", 0.30))
        st.session_state["cp_max_open_positions"] = int(_derived.get("max_open_positions", 3))
        st.session_state["cp_max_rounds"] = int(_derived.get("max_rounds", 3))
        st.session_state["cp_trading_cutoff_time"] = str(_derived.get("trading_cutoff_time", "16:00"))
        st.session_state["cp_allowed_symbols"] = [
            s for s in _derived.get("allowed_symbols", []) if s in _SYMBOLS
        ]
        st.session_state["cp_abort_on_violations"] = [
            v for v in _derived.get("abort_on_violations", []) if v in _VIOLATION_FIELDS
        ]
        st.success("Constraints derived from history — loaded below.")

    if "_derived_constraints" in st.session_state:
        st.info("Derived constraints are active. Switch presets to reset.")

# Preset selector — drives form initial values
selected_preset = st.selectbox("Load Preset", list(_PRESETS))

# Seed initial values from preset; switching preset reseeds intentionally
if "_derived_constraints" in st.session_state:
    initial = st.session_state["_derived_constraints"]
else:
    _seed_key = f"constraints_seed_{selected_preset}"
    if _seed_key not in st.session_state:
        st.session_state[_seed_key] = _PRESETS[selected_preset]
    initial = st.session_state[_seed_key]

st.divider()

# ---------------------------------------------------------------------------
# Two-column layout: form left, JSON preview right
# ---------------------------------------------------------------------------

form_col, preview_col = st.columns([3, 2])

with form_col:
    values = render_constraint_form(initial, key_prefix="cp")

with preview_col:
    st.markdown("**Live JSON Preview**")
    st.json(values)

st.divider()

# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------

btn_save, btn_export, btn_use = st.columns(3)

with btn_save:
    if st.button("Save as Profile", width='stretch'):
        st.session_state["_save_profile_open"] = True

    if st.session_state.get("_save_profile_open"):
        profile_name = st.text_input(
            "Profile name", key="new_profile_name", placeholder="e.g. my_setup"
        )
        if st.button("Confirm Save", key="confirm_save"):
            if profile_name:
                if "saved_profiles" not in st.session_state:
                    st.session_state.saved_profiles = {}
                st.session_state.saved_profiles[profile_name] = values
                st.session_state["_save_profile_open"] = False
                st.success(f'Profile "{profile_name}" saved.')

with btn_export:
    st.download_button(
        "Export JSON",
        data=json.dumps(values, indent=2),
        file_name="constraints.json",
        mime="application/json",
        width='stretch',
    )

with btn_use:
    if st.button("Use in Exchange", width='stretch'):
        st.session_state.constraint_profile = values
        st.success("Constraint profile updated")

# ---------------------------------------------------------------------------
# Saved Profiles
# ---------------------------------------------------------------------------

saved = st.session_state.get("saved_profiles", {})
if saved:
    with st.expander("Saved Profiles", expanded=False):
        for name, profile in saved.items():
            st.markdown(f"**{name}**")
            st.json(profile)
