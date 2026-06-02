from __future__ import annotations
import json
from pathlib import Path

import streamlit as st

from player_coach.market import WorldState

_moderate_path = (
    Path(__file__).parent.parent / "examples" / "constraints" / "moderate.json"
)
_moderate_default = {
    "max_position_pct": 0.15,
    "max_single_trade_pct": 0.05,
    "max_leverage": 1.5,
    "max_drawdown_pct": 0.10,
    "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
    "max_open_positions": 3,
    "min_risk_reward": 1.5,
    "max_rounds": 3,
    "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
}


def init_session_state() -> None:
    defaults: dict = {
        "api_key": None,
        "api_key_valid": False,
        "constraint_profile": (
            json.loads(_moderate_path.read_text())
            if _moderate_path.exists()
            else _moderate_default
        ),
        "world_state": WorldState(
            symbol="AMZN",
            price=185.0,
            sma5=183.0,
            sma10=180.0,
            volume=45_000_000,
            position="flat",
        ).to_dict(),
        "last_artifact": None,
        "player_state": "confident",
        "coach_state": "stern",
        "replay_artifact": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
