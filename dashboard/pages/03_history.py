from __future__ import annotations

import json

import streamlit as st

from dashboard.components.round_panel import render_round
from dashboard.db import get_store

# ---------------------------------------------------------------------------
# Load exchanges
# ---------------------------------------------------------------------------

store = get_store()
exchanges = store.get_exchanges(limit=200)

# ---------------------------------------------------------------------------
# Page title + outcome filter
# ---------------------------------------------------------------------------

st.title("History")

outcome_filter = st.radio(
    "Filter", ["All", "APPROVE", "REJECT-MAX", "ABORT"], horizontal=True
)

if outcome_filter != "All":
    exchanges = [e for e in exchanges if e.get("outcome") == outcome_filter]

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if not exchanges:
    st.info("No exchanges yet. Run an exchange first.")
    st.stop()

# ---------------------------------------------------------------------------
# Build display rows (truncated fields for table)
# ---------------------------------------------------------------------------

display_rows = [
    {
        "run_id": str(e.get("run_id", ""))[:8],
        "timestamp": str(e.get("timestamp", ""))[:19],
        "symbol": e.get("symbol", ""),
        "outcome": e.get("outcome", ""),
        "rounds_taken": int(e.get("rounds_taken", 0)),
        "total_tokens": int(e.get("total_tokens", 0)),
    }
    for e in exchanges
]

# ---------------------------------------------------------------------------
# Dataframe with single-row selection
# ---------------------------------------------------------------------------

event = st.dataframe(
    display_rows,
    column_config={
        "outcome": st.column_config.TextColumn(
            "Outcome",
            help=(
                "APPROVE = approved  |  "
                "REJECT-MAX = max rounds reached  |  "
                "ABORT = hard constraint violation"
            ),
        ),
    },
    on_select="rerun",
    selection_mode="single-row",
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# DB round → artifact round format
# ---------------------------------------------------------------------------

def _db_round_to_artifact_round(r: dict) -> dict:
    import json as _j
    proposal = r.get("proposal", "{}")
    if isinstance(proposal, str):
        try: proposal = _j.loads(proposal)
        except Exception: proposal = {}
    violations = r.get("violations", "[]")
    if isinstance(violations, str):
        try: violations = _j.loads(violations)
        except Exception: violations = []
    return {
        "round": r.get("round_number", 0),
        "proposal": proposal,
        "evaluation": {
            "decision": r.get("verdict", "REJECT"),
            "violations": violations,
            "feedback": r.get("critique", ""),
        },
        "tokens_used": {
            "player": r.get("player_tokens", 0),
            "coach": r.get("coach_tokens", 0),
        },
    }

# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

_BADGE = {
    "APPROVE": (
        "background:#27AE60;color:white;padding:2px 10px;"
        "border-radius:4px;font-size:0.8rem;font-weight:700"
    ),
    "REJECT-MAX": (
        "background:#E67E22;color:white;padding:2px 10px;"
        "border-radius:4px;font-size:0.8rem;font-weight:700"
    ),
    "ABORT": (
        "background:#E74C3C;color:white;padding:2px 10px;"
        "border-radius:4px;font-size:0.8rem;font-weight:700"
    ),
}
_BADGE_DEFAULT = (
    "background:#7F8C8D;color:white;padding:2px 10px;"
    "border-radius:4px;font-size:0.8rem;font-weight:700"
)

selected_rows = event.selection.rows if event and hasattr(event, "selection") else []

if selected_rows:
    idx = selected_rows[0]
    exchange = exchanges[idx]
    full_run_id = str(exchange.get("run_id", ""))
    outcome = exchange.get("outcome", "")

    st.divider()
    st.subheader(f"Run: {full_run_id}")

    badge_style = _BADGE.get(outcome, _BADGE_DEFAULT)
    st.markdown(
        f'<span style="{badge_style}">{outcome}</span>'
        f" &nbsp; **{str(exchange.get('timestamp', ''))[:19]}**"
        f" &nbsp; Symbol: **{exchange.get('symbol', '')}**"
        f" &nbsp; Rounds: **{exchange.get('rounds_taken', '')}**"
        f" &nbsp; Tokens: **{exchange.get('total_tokens', '')}**",
        unsafe_allow_html=True,
    )

    # Rounds
    rounds = store.get_rounds(full_run_id)
    if rounds:
        st.markdown("**Rounds**")
        for rd in rounds:
            render_round(_db_round_to_artifact_round(rd), expanded=False)

    # Constraint snapshot
    constraint_snapshot = exchange.get("constraint_snapshot")
    if constraint_snapshot:
        if isinstance(constraint_snapshot, str):
            try:
                constraint_snapshot = json.loads(constraint_snapshot)
            except (json.JSONDecodeError, ValueError):
                pass
        with st.expander("Constraint Snapshot", expanded=False):
            st.json(constraint_snapshot)

    # Replay
    if st.button("Replay with animation", type="primary"):
        artifact = {
            "run_id": full_run_id,
            "outcome": outcome,
            "symbol": exchange.get("symbol"),
            "rounds": [_db_round_to_artifact_round(r) for r in rounds] if rounds else [],
            "constraint_snapshot": constraint_snapshot,
        }
        st.session_state.replay_artifact = artifact
        st.switch_page("pages/01_exchange.py")
