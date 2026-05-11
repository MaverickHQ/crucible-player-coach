from __future__ import annotations
from pathlib import Path

import streamlit as st

from player_coach.database.store import DatabaseStore


@st.cache_resource
def get_store() -> DatabaseStore:
    Path("data").mkdir(exist_ok=True)
    return DatabaseStore("data/player_coach.db")
