from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from dashboard.state import init_session_state

st.set_page_config(
    page_title="Player-Coach",
    page_icon="⚡",
    layout="wide",
)

init_session_state()

exchange = st.Page("pages/01_exchange.py", title="Exchange", icon="🎯")
constraints = st.Page("pages/02_constraints.py", title="Constraints", icon="📋")
history = st.Page("pages/03_history.py", title="History", icon="📜")
settings = st.Page("pages/04_settings.py", title="Settings", icon="⚙️")
backtest = st.Page("pages/05_backtest.py", title="Backtest", icon="📊")

pg = st.navigation([exchange, constraints, history, settings, backtest])

st.sidebar.markdown("# Player-Coach")
st.sidebar.caption("Adversarial trading decisions, round by round")
st.sidebar.divider()

pg.run()
