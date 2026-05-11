from __future__ import annotations
import json
from pathlib import Path

import streamlit as st


def init_session_state() -> None:
    defaults: dict = {
        "api_key": None,
        "api_key_valid": False,
        "constraint_profile": json.loads(
            Path("examples/constraints/moderate.json").read_text()
        ),
        "world_state": {
            "symbol": "AMZN",
            "price": 185.0,
            "sma5": 183.0,
            "sma10": 180.0,
            "volume": 45_000_000,
            "position": "flat",
            "volatility_regime": "medium",
            "session": "NY_open",
        },
        "last_artifact": None,
        "player_state": "confident",
        "coach_state": "stern",
        "replay_artifact": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
