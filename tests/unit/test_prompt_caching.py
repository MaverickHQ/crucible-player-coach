"""T1 — prompt caching on PlayerAgent and CoachAgent.

System prompts are large and identical on every call; constraint schema in the
user message is also static across rounds within a day. Adding cache_control
markers means subsequent calls within the 5-min TTL pay ~10% of input price on
cached tokens and ~latency drops. We also capture cache_read_input_tokens so a
future panel can show cache hit %.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from player_coach.agents.coach import CoachAgent
from player_coach.agents.player import PlayerAgent
from player_coach.constraints.schema import ConstraintSchema


def _constraints() -> ConstraintSchema:
    return ConstraintSchema(
        max_position_pct=0.15, max_single_trade_pct=0.05, max_leverage=1.5,
        max_drawdown_pct=0.10, allowed_symbols=["AMZN"], max_open_positions=3,
        min_risk_reward=1.5, abort_on_violations=["max_leverage"],
    )


def _world_state() -> dict:
    return {"symbol": "AMZN", "price": 185.0, "sma5": 184.0, "sma10": 183.0, "volume": 1000}


def _make_response(text: str, *, cache_read: int = 0, cache_creation: int = 0):
    """Build a SimpleNamespace mimicking the anthropic Message response shape."""
    usage = SimpleNamespace(
        input_tokens=100, output_tokens=20,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
    )
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], usage=usage)


# ---------------------------------------------------------------- system cache

def test_player_system_prompt_carries_cache_control():
    agent = PlayerAgent.__new__(PlayerAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    agent._client.messages.create.return_value = _make_response(
        '{"actions": [], "reasoning": "ok"}'
    )
    agent.decide(world_state=_world_state(), constraints=_constraints())
    call = agent._client.messages.create.call_args
    system = call.kwargs["system"]
    # Must be a structured block list so we can attach cache_control — not a bare
    # string. Last block must carry ephemeral cache_control.
    assert isinstance(system, list), "system must be a list of blocks for caching"
    assert system[-1].get("cache_control") == {"type": "ephemeral"}


def test_coach_system_prompt_carries_cache_control():
    agent = CoachAgent.__new__(CoachAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    agent._client.messages.create.return_value = _make_response(
        '{"verdict": "APPROVE", "violations": [], "critique": "ok"}'
    )
    agent.evaluate(proposal={"actions": [], "reasoning": ""},
                   constraints=_constraints(), world_state=_world_state())
    call = agent._client.messages.create.call_args
    system = call.kwargs["system"]
    assert isinstance(system, list)
    assert system[-1].get("cache_control") == {"type": "ephemeral"}


# ----------------------------------------------------- cache-read token capture

def test_player_captures_cache_read_tokens():
    agent = PlayerAgent.__new__(PlayerAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    agent._client.messages.create.return_value = _make_response(
        '{"actions": [], "reasoning": "ok"}', cache_read=8000,
    )
    result = agent.decide(world_state=_world_state(), constraints=_constraints())
    assert result["tokens_used"].get("cache_read_player") == 8000


def test_coach_captures_cache_read_tokens():
    agent = CoachAgent.__new__(CoachAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    agent._client.messages.create.return_value = _make_response(
        '{"verdict": "APPROVE", "violations": [], "critique": "ok"}',
        cache_read=4200,
    )
    result = agent.evaluate(proposal={"actions": [], "reasoning": ""},
                            constraints=_constraints(),
                            world_state=_world_state())
    assert result["tokens_used"].get("cache_read_coach") == 4200


def test_player_handles_missing_cache_field_gracefully():
    # Older SDKs / responses without the field must not crash — defaults to 0.
    agent = PlayerAgent.__new__(PlayerAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    no_cache_usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    block = SimpleNamespace(type="text", text='{"actions": [], "reasoning": "ok"}')
    agent._client.messages.create.return_value = SimpleNamespace(
        content=[block], usage=no_cache_usage,
    )
    result = agent.decide(world_state=_world_state(), constraints=_constraints())
    assert result["tokens_used"].get("cache_read_player", 0) == 0


def test_coach_handles_missing_cache_field_gracefully():
    agent = CoachAgent.__new__(CoachAgent)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    no_cache_usage = SimpleNamespace(input_tokens=100, output_tokens=20)
    block = SimpleNamespace(
        type="text",
        text='{"verdict": "APPROVE", "violations": [], "critique": "ok"}',
    )
    agent._client.messages.create.return_value = SimpleNamespace(
        content=[block], usage=no_cache_usage,
    )
    result = agent.evaluate(proposal={"actions": [], "reasoning": ""},
                            constraints=_constraints(),
                            world_state=_world_state())
    assert result["tokens_used"].get("cache_read_coach", 0) == 0


# ---------------------------------------------------------------- N6: coverage
#
# T1 also needs to cover ReasoningEvaluator and the two dashboard streaming
# clones — those routes were silently uncached because they used the bare
# `system=_SYSTEM_PROMPT` string instead of the structured block. Without
# these, ½ of T1's projected savings vanish on Standard backtests (the
# evaluator runs once per round) and 100% on streaming exchanges.


def _evaluator_response(critique: str = "ok"):
    return _make_response(
        '{"market_grounded": 0.8, "internally_coherent": 0.9, '
        f'"proportionate": 0.7, "critique": "{critique}"}}'
    )


def test_reasoning_evaluator_uses_cached_system_block():
    from player_coach.evaluators.reasoning_evaluator import ReasoningEvaluator
    agent = ReasoningEvaluator.__new__(ReasoningEvaluator)
    agent._client = MagicMock()
    agent._model = "claude-haiku-4-5-20251001"
    agent._client.messages.create.return_value = _evaluator_response()
    agent.evaluate(reasoning="x", actions=[], world_state=_world_state())
    system = agent._client.messages.create.call_args.kwargs["system"]
    assert isinstance(system, list), (
        "ReasoningEvaluator must pass system as structured block list for caching"
    )
    assert system[-1].get("cache_control") == {"type": "ephemeral"}


def _stream_cm(text: str = '{"actions": [], "reasoning": "ok"}',
               *, input_tokens: int = 100, output_tokens: int = 20):
    """Mock for ``with client.messages.stream(...) as s`` context manager."""
    inner = MagicMock()
    inner.text_stream = iter([text])
    inner.get_final_usage = MagicMock(return_value=SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens,
    ))
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=inner)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def test_streaming_player_uses_cached_system_block():
    from unittest.mock import patch
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return _stream_cm()

    fake_client = MagicMock()
    fake_client.messages.stream = fake_stream
    with patch("dashboard.streaming.player_stream.anthropic.Anthropic",
               return_value=fake_client):
        from dashboard.streaming.player_stream import stream_player_decision
        list(stream_player_decision(
            world_state=_world_state(),
            constraints=_constraints(),
            history=None, api_key="k", patterns=None,
        ))
    assert isinstance(captured["system"], list), (
        "streaming player must pass system as structured block list for caching"
    )
    assert captured["system"][-1].get("cache_control") == {"type": "ephemeral"}


def test_streaming_coach_uses_cached_system_block():
    from unittest.mock import patch
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return _stream_cm(
            '{"verdict": "APPROVE", "violations": [], "critique": "ok"}'
        )

    fake_client = MagicMock()
    fake_client.messages.stream = fake_stream
    with patch("dashboard.streaming.coach_stream.anthropic.Anthropic",
               return_value=fake_client):
        from dashboard.streaming.coach_stream import stream_coach_evaluation
        list(stream_coach_evaluation(
            proposal={"actions": [], "reasoning": ""},
            constraints=_constraints(), world_state=_world_state(),
            api_key="k",
        ))
    assert isinstance(captured["system"], list), (
        "streaming coach must pass system as structured block list for caching"
    )
    assert captured["system"][-1].get("cache_control") == {"type": "ephemeral"}
