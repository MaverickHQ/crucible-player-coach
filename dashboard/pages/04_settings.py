from __future__ import annotations

import streamlit as st

from dashboard.db import get_store

# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

st.header("API Key")
st.info(
    "Your key is stored in session memory only. "
    "It is never written to disk or logs."
)

key_input = st.text_input(
    "Anthropic API Key",
    type="password",
    placeholder="sk-ant-...",
    value=st.session_state.get("api_key") or "",
)

col_validate, col_clear = st.columns(2)

with col_validate:
    if st.button("Validate Key", use_container_width=True):
        try:
            import anthropic
            anthropic.Anthropic(api_key=key_input).models.list()
            st.session_state.api_key = key_input
            st.session_state.api_key_valid = True
            st.success("Key valid — Exchange enabled")
        except Exception as e:
            st.session_state.api_key_valid = False
            st.error(f"Invalid key: {e}")

with col_clear:
    if st.button("Clear Key", use_container_width=True):
        st.session_state.api_key = None
        st.session_state.api_key_valid = False
        st.info("Key cleared")

if st.session_state.get("api_key_valid"):
    st.markdown(
        '<span style="color:#27AE60;font-weight:700">✓ Key valid</span>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<span style="color:#E74C3C;font-weight:700">✗ No valid key</span>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

st.header("Database")

store = get_store()
db_path = getattr(store, "_db_path", "unknown")
exchange_count = len(store.get_exchanges(limit=10_000))

st.markdown(f"**Path:** `{db_path}`")
st.markdown(f"**Exchanges stored:** {exchange_count}")

st.divider()

confirm = st.checkbox("I understand this is irreversible")
if st.button("Clear all exchanges", disabled=not confirm, type="secondary"):
    store.clear_exchanges()
    st.success("All exchanges and rounds deleted.")
    st.rerun()

# ---------------------------------------------------------------------------
# About
# ---------------------------------------------------------------------------

st.header("About")

try:
    from player_coach import version
    st.markdown(f"**Version:** {version}")
except Exception:
    st.markdown("**Version:** unknown")

st.markdown(
    "**GitHub:** [MaverickHQ/crucible-player-coach]"
    "(https://github.com/MaverickHQ/crucible-player-coach)"
)
st.markdown(
    "**Essay:** "
    "[8b — How player-coach works]"
    "(https://github.com/MaverickHQ/crucible-player-coach#essays)"
)
