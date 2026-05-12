from __future__ import annotations

from pathlib import Path

import streamlit as st

_ASSETS = Path(__file__).parents[1] / "assets"

_PLAYER_IMAGES = {
    "confident": _ASSETS / "Player_Confident.png",
    "deflated":  _ASSETS / "Player_Deflated.png",
    "approving": _ASSETS / "Player_Approving.png",
}

_COACH_IMAGES = {
    "stern":     _ASSETS / "Coach_Stern.png",
    "approving": _ASSETS / "Coach_Approving.png",
}

PLAYER_SVGS: dict = {}
COACH_SVGS: dict = {}


def render_character(
    svgs: dict,
    state: str,
    label: str,
) -> None:
    images = _PLAYER_IMAGES if svgs is PLAYER_SVGS else _COACH_IMAGES
    path = images.get(state)
    if path and path.exists():
        st.image(str(path), use_container_width=True)
    else:
        st.markdown(
            f'<div style="height:200px;display:flex;'
            f'align-items:center;justify-content:center;'
            f'border:2px dashed #ccc;border-radius:8px;'
            f'color:#999">{label} ({state})</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="text-align:center;font-weight:700;'
        f'font-size:0.85rem;letter-spacing:0.05em;'
        f'margin-top:4px">{label}</div>',
        unsafe_allow_html=True,
    )
