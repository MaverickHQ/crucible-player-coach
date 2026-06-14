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
