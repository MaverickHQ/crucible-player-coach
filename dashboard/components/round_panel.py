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
    import re, json as _j

    # Strip code fences first
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()

    # If it looks like JSON now, try to extract critique
    if cleaned.startswith("{"):
        try:
            parsed = _j.loads(cleaned)
            return parsed.get("critique", "") or cleaned
        except Exception:
            pass
        # Regex fallback — handles multiline critique values
        m = re.search(
            r'"critique"\s*:\s*"((?:[^"\\]|\\.)*)"',
            cleaned,
        )
        if m:
            return m.group(1).replace('\\"', '"')

    return cleaned


def _reasoning_badge(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 0.7:
        color = "#27AE60"
    elif score >= 0.4:
        color = "#F39C12"
    else:
        color = "#E74C3C"
    style = (
        f"background:{color};color:white;padding:2px 8px;"
        "border-radius:4px;font-size:0.75rem;font-weight:700"
    )
    label = f"reasoning {score:.2f}"
    return f'<span style="{style}">{label}</span>'


def render_round(round_dict: dict, expanded: bool = True) -> None:
    n = round_dict.get("round", "?")
    evaluation = round_dict.get("evaluation", {})
    verdict = evaluation.get("decision", "REJECT")
    violations = evaluation.get("violations", [])
    feedback = evaluation.get("feedback", "")
    proposal = round_dict.get("proposal", {})
    actions = proposal.get("actions", [])
    reasoning = proposal.get("reasoning", "")
    reasoning_score = round_dict.get("reasoning_score")
    reasoning_critique = round_dict.get("reasoning_critique")

    badge_style = _BADGE.get(verdict, _BADGE_DEFAULT)
    r_badge = _reasoning_badge(reasoning_score)

    with st.expander(f"Round {n} — {verdict}", expanded=expanded):
        st.markdown(
            f'**Round {n}** &nbsp; <span style="{badge_style}">{verdict}</span>'
            + (f" &nbsp; {r_badge}" if r_badge else ""),
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

        if reasoning_critique and reasoning_score is not None:
            st.markdown("**Reasoning Quality**")
            st.markdown(
                f"{r_badge} &nbsp; {reasoning_critique}",
                unsafe_allow_html=True,
            )

        with st.expander("Player reasoning", expanded=False):
            st.markdown(reasoning or "_No reasoning provided._")
