from __future__ import annotations

import streamlit as st

_BADGE: dict[str, str] = {
    "APPROVE": (
        "background:#27AE60;color:white;padding:2px 10px;"
        "border-radius:4px;font-size:0.8rem;font-weight:700"
    ),
    "REJECT": (
        "background:#E74C3C;color:white;padding:2px 10px;"
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

_ACTION_COLS = [
    "action_type",
    "symbol",
    "size_pct",
    "entry_price",
    "stop_loss",
    "take_profit",
]


def _clean_feedback(text: str) -> str:
    if not text:
        return ""
    if text.strip().startswith("{"):
        import re
        m = re.search(r'"critique"\s*:\s*"([^"]*)"', text)
        if m:
            return m.group(1)
        import json as _j
        try:
            parsed = _j.loads(text)
            return parsed.get("critique", text)
        except Exception:
            pass
    return text


def render_round(round_dict: dict, expanded: bool = True) -> None:
    n = round_dict.get("round", "?")
    evaluation = round_dict.get("evaluation", {})
    verdict = evaluation.get("decision", "REJECT")
    violations = evaluation.get("violations", [])
    feedback = evaluation.get("feedback", "")
    proposal = round_dict.get("proposal", {})
    actions = proposal.get("actions", [])
    reasoning = proposal.get("reasoning", "")

    badge_style = _BADGE.get(verdict, _BADGE_DEFAULT)

    with st.expander(f"Round {n} — {verdict}", expanded=expanded):
        st.markdown(
            f'**Round {n}** &nbsp; <span style="{badge_style}">{verdict}</span>',
            unsafe_allow_html=True,
        )

        if actions:
            st.markdown("**Proposed Actions**")
            rows = [{c: a.get(c, "—") for c in _ACTION_COLS} for a in actions]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption("No actions proposed.")

        if violations:
            st.markdown("**Violations**")
            for v in violations:
                st.markdown(
                    f'<span style="color:#E74C3C">• {v}</span>',
                    unsafe_allow_html=True,
                )

        if feedback:
            st.markdown("**Coach Feedback**")
            st.markdown(_clean_feedback(feedback))

        with st.expander("Player reasoning", expanded=False):
            st.markdown(reasoning or "_No reasoning provided._")
