from __future__ import annotations

import socket as _socket

import streamlit as st

from dashboard.components.characters import COACH_SVGS, PLAYER_SVGS, render_character
from dashboard.components.round_panel import render_round
from dashboard.components.speech_bubble import SpeechBubble
from dashboard.db import get_store
from dashboard.streaming.loop_runner import DashboardRunner
from player_coach.constraints.schema import ConstraintSchema
from player_coach.market import WorldState

# ---------------------------------------------------------------------------
# Constraint presets (inline — no file I/O at import time)
# ---------------------------------------------------------------------------

_PRESETS: dict[str, dict] = {
    "conservative": {
        "max_position_pct": 0.10,
        "max_single_trade_pct": 0.03,
        "max_leverage": 1.0,
        "max_drawdown_pct": 0.05,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 2,
        "min_risk_reward": 2.0,
        "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
    },
    "moderate": {
        "max_position_pct": 0.15,
        "max_single_trade_pct": 0.05,
        "max_leverage": 1.5,
        "max_drawdown_pct": 0.10,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 3,
        "min_risk_reward": 1.5,
        "abort_on_violations": ["max_leverage", "max_drawdown_pct"],
    },
    "aggressive": {
        "max_position_pct": 0.25,
        "max_single_trade_pct": 0.10,
        "max_leverage": 2.0,
        "max_drawdown_pct": 0.20,
        "allowed_symbols": ["AMZN", "MSFT", "TSLA", "BTC-USD"],
        "max_open_positions": 5,
        "min_risk_reward": 1.0,
        "abort_on_violations": ["max_leverage"],
    },
}

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _yfinance_available() -> bool:
    try:
        _socket.setdefaulttimeout(1)
        _socket.socket(_socket.AF_INET,
                       _socket.SOCK_STREAM).connect(
            ("fc.yahoo.com", 443))
        return True
    except Exception:
        return False

_USE_YFINANCE = _yfinance_available()


@st.cache_data(ttl=300)
def _fetch_market_data(sym: str) -> dict:
    if _USE_YFINANCE:
        try:
            import yfinance as yf
            import pandas as pd
            raw = yf.download(
                sym, period="20d",
                auto_adjust=True, progress=False,
            )
            if not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = [c[0].lower()
                                   for c in raw.columns]
                else:
                    raw.columns = [c.lower()
                                   for c in raw.columns]
                closes = raw["close"].tolist()
                return {
                    "price": round(float(closes[-1]), 2),
                    "sma5": round(float(
                        sum(closes[-5:]) /
                        min(5, len(closes))), 2),
                    "sma10": round(float(
                        sum(closes[-10:]) /
                        min(10, len(closes))), 2),
                    "volume": int(raw["volume"].iloc[-1]),
                }
        except Exception:
            pass
        return {}

    # Local fallback: direct Yahoo Finance v8 API
    try:
        import requests
        r = requests.get(
            "https://query1.finance.yahoo.com"
            f"/v8/finance/chart/{sym}",
            params={"range": "20d", "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 200:
            result = r.json()["chart"]["result"][0]
            quotes = result["indicators"]["quote"][0]
            closes = [c for c in quotes["close"]
                      if c is not None]
            volumes = [v for v in quotes["volume"]
                       if v is not None]
            if closes:
                return {
                    "price": round(float(closes[-1]), 2),
                    "sma5": round(float(
                        sum(closes[-5:]) /
                        min(5, len(closes))), 2),
                    "sma10": round(float(
                        sum(closes[-10:]) /
                        min(10, len(closes))), 2),
                    "volume": int(volumes[-1])
                              if volumes else 0,
                }
    except Exception:
        pass
    return {}


with st.sidebar:
    st.header("Market Parameters")
    symbol = st.selectbox("Symbol", ["AMZN", "MSFT", "TSLA", "BTC-USD"])
    mkt = _fetch_market_data(symbol)
    price = st.number_input("Current Price ($)", value=mkt.get("price", 185.0), min_value=0.01, step=1.0, key=f"price_{symbol}")
    sma5 = st.number_input("SMA 5-day", value=mkt.get("sma5", 183.0), step=1.0, key=f"sma5_{symbol}")
    sma10 = st.number_input("SMA 10-day", value=mkt.get("sma10", 180.0), step=1.0, key=f"sma10_{symbol}")
    volume = st.number_input("Volume", value=mkt.get("volume", 45000000), step=100000, key=f"volume_{symbol}")
    session = st.selectbox("Session", ["NY_open", "NY_mid", "NY_close", "overnight"])
    regime = st.selectbox(
        "Regime", ["unknown", "low_vol", "medium_vol", "high_vol"]
    )

    st.divider()
    st.header("Constraints")
    preset = st.selectbox("Preset", list(_PRESETS))
    max_rounds = st.slider("Max Rounds", min_value=1, max_value=5, value=3)

    st.divider()
    run_clicked = st.button("Run Exchange", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Page title + character area
# ---------------------------------------------------------------------------

st.title("Trade Review")

# Row 1 — Player left, bubble right
p_img_col, p_bub_col = st.columns([1, 3])
with p_img_col:
    player_char_ph = st.empty()
with p_bub_col:
    player_bubble_ph = st.empty()

# Row 2 — bubble left, Coach right
c_bub_col, c_img_col = st.columns([3, 1])
with c_bub_col:
    coach_bubble_ph = st.empty()
with c_img_col:
    coach_char_ph = st.empty()


def _set_player(state: str) -> None:
    with player_char_ph.container():
        render_character(PLAYER_SVGS, state, "PLAYER", width=120)


def _set_coach(state: str) -> None:
    with coach_char_ph.container():
        render_character(COACH_SVGS, state, "COACH", width=120)


_set_player("confident")
_set_coach("stern")

# ---------------------------------------------------------------------------
# Rounds + artifact placeholders
# ---------------------------------------------------------------------------

rounds_ph = st.empty()
artifact_ph = st.empty()

# ---------------------------------------------------------------------------
# Clear stale rounds when symbol changes
# ---------------------------------------------------------------------------

if st.session_state.get("_last_symbol") != symbol:
    st.session_state["_last_symbol"] = symbol
    st.session_state["last_artifact"] = None
    rounds_ph.empty()
    artifact_ph.empty()

# ---------------------------------------------------------------------------
# Replay mode — pop before run logic so it clears on first render
# ---------------------------------------------------------------------------

_replay = st.session_state.pop("replay_artifact", None)

if _replay:
    replay_rounds = _replay.get("rounds", [])
    if replay_rounds:
        last_rd = replay_rounds[-1]
        last_verdict = last_rd.get("evaluation", {}).get("decision", "REJECT")
        if last_verdict == "APPROVE":
            _set_player("approving")
            _set_coach("approving")
        else:
            _set_player("deflated")
            _set_coach("stern")
        SpeechBubble(player_bubble_ph).show_text(
            last_rd.get("proposal", {}).get("reasoning", "") or "—"
        )
        SpeechBubble(coach_bubble_ph).show_text(
            last_rd.get("evaluation", {}).get("feedback", "") or "—"
        )
    with rounds_ph.container():
        for rd in replay_rounds:
            render_round(rd, expanded=False)
    with artifact_ph.container():
        st.subheader("Artifact")
        st.json(_replay)

# ---------------------------------------------------------------------------
# Run Exchange
# ---------------------------------------------------------------------------

elif run_clicked:
    if not st.session_state.get("api_key_valid"):
        st.warning("Set your API key in Settings")
    else:
        constraints_dict = st.session_state.get("constraint_profile")
        if not constraints_dict:
            constraints_dict = _PRESETS[preset]
        else:
            st.session_state["constraint_profile"] = None
        constraints = ConstraintSchema.from_dict(
            {**constraints_dict, "max_rounds": max_rounds}
        )
        world_state = WorldState(
            symbol=symbol,
            price=price,
            sma5=sma5,
            sma10=sma10,
            volume=int(volume),
            position="flat",
            regime_label=regime,
            session=session,
        ).to_dict()
        runner = DashboardRunner(
            constraints=constraints,
            world_state=world_state,
            portfolio_state=None,
            api_key=st.session_state.api_key,
            db_store=get_store(),
        )

        player_bubble = SpeechBubble(player_bubble_ph, side="left")
        coach_bubble  = SpeechBubble(coach_bubble_ph,  side="right")
        completed_rounds: list[dict] = []

        for event in runner.run():
            etype = event.get("type")

            if etype == "round_start":
                player_bubble.clear()
                coach_bubble.clear()
                _set_player("confident")
                _set_coach("stern")

            elif etype == "player_token":
                player_bubble.show_text("⏳ thinking...")

            elif etype == "player_done":
                reasoning = event.get("result", {}).get("reasoning", "")
                if reasoning:
                    player_bubble.stream_text(reasoning, delay=0.03)

            elif etype == "coach_token":
                coach_bubble.show_text("⏳ evaluating...")

            elif etype == "coach_done":
                result = event.get("result", {})
                verdict = result.get("verdict", "REJECT")
                critique = result.get("critique", "")
                if critique:
                    coach_bubble.stream_text(critique, delay=0.03)
                if verdict == "APPROVE":
                    _set_player("approving")
                    _set_coach("approving")
                else:
                    _set_player("deflated")
                    _set_coach("stern")

            elif etype == "round_end":
                completed_rounds.append(event.get("round", {}))
                with rounds_ph.container():
                    for i, rd in enumerate(completed_rounds):
                        render_round(rd, expanded=(i == len(completed_rounds) - 1))

            elif etype == "loop_done":
                artifact = event.get("artifact", {})
                st.session_state.last_artifact = artifact
                with artifact_ph.container():
                    st.subheader("Artifact")
                    st.json(artifact)

            elif etype == "circuit_breaker":
                st.error(f"Circuit breaker triggered: {event.get('reason', 'unknown')}")
                _set_player("deflated")
                _set_coach("stern")

            elif etype == "error":
                st.error(f"Exchange failed: {event.get('message', 'unknown error')}")
                _set_player("deflated")
                _set_coach("stern")

# ---------------------------------------------------------------------------
# Persist last artifact across reruns (sidebar changes, etc.)
# ---------------------------------------------------------------------------

elif st.session_state.get("last_artifact"):
    artifact = st.session_state.last_artifact
    rounds = artifact.get("rounds", [])
    if rounds:
        with rounds_ph.container():
            for rd in rounds:
                render_round(rd, expanded=False)
    with artifact_ph.container():
        st.subheader("Artifact")
        st.json(artifact)
