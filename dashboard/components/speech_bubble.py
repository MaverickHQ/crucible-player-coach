from __future__ import annotations

import time

import streamlit as st

_BUBBLE_CSS = """
<style>
.speech-bubble {
    background: #FFFFFF;
    color: #1A1A2E;
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
.speech-bubble-left::after {
    content: "";
    position: absolute;
    top: 50%;
    left: -14px;
    transform: translateY(-50%);
    border-width: 10px 14px 10px 0;
    border-style: solid;
    border-color: transparent #1A1A2E transparent transparent;
}
.speech-bubble-left::before {
    content: "";
    position: absolute;
    top: 50%;
    left: -10px;
    transform: translateY(-50%);
    border-width: 8px 11px 8px 0;
    border-style: solid;
    border-color: transparent #FFFFFF transparent transparent;
    z-index: 1;
}
.speech-bubble-right::after {
    content: "";
    position: absolute;
    top: 50%;
    right: -14px;
    transform: translateY(-50%);
    border-width: 10px 0 10px 14px;
    border-style: solid;
    border-color: transparent transparent transparent #1A1A2E;
}
.speech-bubble-right::before {
    content: "";
    position: absolute;
    top: 50%;
    right: -10px;
    transform: translateY(-50%);
    border-width: 8px 0 8px 11px;
    border-style: solid;
    border-color: transparent transparent transparent #FFFFFF;
    z-index: 1;
}
</style>
"""

def _inject_style() -> None:
    st.markdown(_BUBBLE_CSS, unsafe_allow_html=True)


def _render_html(text: str, side: str = "right") -> str:
    return (f'<div class="speech-bubble '
            f'speech-bubble-{side}">{text}&nbsp;</div>')


class SpeechBubble:
    def __init__(self,
        placeholder: st.delta_generator.DeltaGenerator,
        side: str = "right",
    ) -> None:
        _inject_style()
        self._ph = placeholder
        self._side = side

    def stream_text(self, text: str, delay: float = 0.04) -> None:
        words = text.split(" ")
        accumulated = ""
        for word in words:
            accumulated = accumulated + (" " if accumulated else "") + word
            self._ph.markdown(_render_html(accumulated, self._side), unsafe_allow_html=True)
            time.sleep(delay)

    def show_text(self, text: str) -> None:
        self._ph.markdown(_render_html(text, self._side), unsafe_allow_html=True)

    def clear(self) -> None:
        self._ph.empty()
