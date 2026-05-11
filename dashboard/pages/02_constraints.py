from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.components.constraint_form import render_constraint_form

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

st.title("Constraints")

# Preset selector — drives form initial values
selected_preset = st.selectbox("Load Preset", list(_PRESETS))

# Seed initial values from preset; switching preset reseeds intentionally
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
    if st.button("Save as Profile", use_container_width=True):
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
        use_container_width=True,
    )

with btn_use:
    if st.button("Use in Exchange", use_container_width=True):
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
