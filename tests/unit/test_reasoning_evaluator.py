from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

from player_coach.evaluators.reasoning_evaluator import ReasoningEvaluator

_WORLD_STATE = {"symbol": "AMZN", "price": 185.0, "rsi": 42.0}
_ACTIONS = [{"action_type": "enter_long", "symbol": "AMZN", "size_pct": 0.05}]
_REASONING = "RSI at 42 signals oversold; entering long at 185 with 5% position."


def _make_evaluator() -> ReasoningEvaluator:
    with patch("player_coach.evaluators.reasoning_evaluator.ReasoningEvaluator.__init__", return_value=None):
        ev = ReasoningEvaluator.__new__(ReasoningEvaluator)
    ev._model = "claude-haiku-4-5-20251001"
    return ev


def _mock_response(text: str) -> MagicMock:
    content = MagicMock()
    content.text = text
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    resp = MagicMock()
    resp.content = [content]
    resp.usage = usage
    return resp


def _patch_client(ev: ReasoningEvaluator, response_text: str) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = _mock_response(response_text)
    ev._client = client
    return client


# ------------------------------------------------------------------ happy path

def test_evaluate_returns_score_and_critique():
    ev = _make_evaluator()
    _patch_client(ev, '{"market_grounded": 0.9, "internally_coherent": 0.8, "proportionate": 0.7, "critique": "cites RSI, logic holds, size matches conviction"}')

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] == pytest.approx(0.8, abs=0.01)
    assert "cites RSI" in result["reasoning_critique"]


def test_score_clamped_to_unit_interval():
    ev = _make_evaluator()
    _patch_client(ev, '{"market_grounded": 1.5, "internally_coherent": -0.2, "proportionate": 1.0, "critique": "out of range values"}')

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert 0.0 <= result["reasoning_score"] <= 1.0


def test_score_is_mean_of_three_dimensions():
    ev = _make_evaluator()
    _patch_client(ev, '{"market_grounded": 0.6, "internally_coherent": 0.9, "proportionate": 0.3, "critique": "mixed"}')

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] == pytest.approx(0.6, abs=0.001)


# ------------------------------------------------------------------ fallbacks

def test_truncated_json_returns_fallback():
    ev = _make_evaluator()
    _patch_client(ev, '{"market_grounded": 0.8, "internally_coherent":')  # truncated

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] is None
    assert result["reasoning_critique"] == "evaluation unavailable"


def test_missing_key_returns_fallback():
    ev = _make_evaluator()
    _patch_client(ev, '{"market_grounded": 0.8, "critique": "missing two keys"}')

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] is None
    assert result["reasoning_critique"] == "evaluation unavailable"


def test_api_exception_returns_fallback():
    ev = _make_evaluator()
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("network error")
    ev._client = client

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] is None
    assert result["reasoning_critique"] == "evaluation unavailable"


def test_empty_response_content_returns_fallback():
    ev = _make_evaluator()
    client = MagicMock()
    resp = MagicMock()
    resp.content = []
    client.messages.create.return_value = resp
    ev._client = client

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] is None
    assert result["reasoning_critique"] == "evaluation unavailable"


def test_json_embedded_in_prose_is_extracted():
    ev = _make_evaluator()
    prose = 'Here is my evaluation: {"market_grounded": 0.5, "internally_coherent": 0.5, "proportionate": 0.5, "critique": "average across all dimensions"} — done.'
    _patch_client(ev, prose)

    result = ev.evaluate(_REASONING, _ACTIONS, _WORLD_STATE)

    assert result["reasoning_score"] == pytest.approx(0.5, abs=0.001)
