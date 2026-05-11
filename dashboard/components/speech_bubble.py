from __future__ import annotations

import time

import streamlit as st

_BUBBLE_CSS = """
<style>
.speech-bubble {
    background: #FFFFFF;
    border: 2.5px solid #1A1A2E;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 0.88rem;
    line-height: 1.5;
    box-shadow: 3px 3px 0px #1A1A2E;
    position: relative;
    max-width: 100%;
    word-wrap: break-word;
    min-height: 48px;
}
.speech-bubble::after {
    content: "";
    position: absolute;
    bottom: -14px;
    left: 50%;
    transform: translateX(-50%);
    border-width: 14px 10px 0 10px;
    border-style: solid;
    border-color: #1A1A2E transparent transparent transparent;
}
.speech-bubble::before {
    content: "";
    position: absolute;
    bottom: -10px;
    left: 50%;
    transform: translateX(-50%);
    border-width: 11px 8px 0 8px;
    border-style: solid;
    border-color: #FFFFFF transparent transparent transparent;
    z-index: 1;
}
</style>
"""

_STYLE_INJECTED = False


def _inject_style() -> None:
    global _STYLE_INJECTED
    if not _STYLE_INJECTED:
        st.markdown(_BUBBLE_CSS, unsafe_allow_html=True)
        _STYLE_INJECTED = True


def _render_html(text: str) -> str:
    return f'<div class="speech-bubble">{text}&nbsp;</div>'


class SpeechBubble:
    def __init__(self, placeholder: st.delta_generator.DeltaGenerator) -> None:
        _inject_style()
        self._ph = placeholder

    def stream_text(self, text: str, delay: float = 0.04) -> None:
        words = text.split(" ")
        accumulated = ""
        for word in words:
            accumulated = accumulated + (" " if accumulated else "") + word
            self._ph.markdown(_render_html(accumulated), unsafe_allow_html=True)
            time.sleep(delay)

    def show_text(self, text: str) -> None:
        self._ph.markdown(_render_html(text), unsafe_allow_html=True)

    def clear(self) -> None:
        self._ph.empty()
