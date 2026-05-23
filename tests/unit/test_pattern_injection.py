from __future__ import annotations

from player_coach.agents.player import _build_user_prompt
from player_coach.constraints.schema import ConstraintSchema


def _constraints() -> ConstraintSchema:
    return ConstraintSchema(
        max_position_pct=0.15,
        max_single_trade_pct=0.05,
        max_leverage=1.5,
        max_drawdown_pct=0.10,
        allowed_symbols=["AMZN"],
        max_open_positions=3,
        min_risk_reward=1.5,
        abort_on_violations=["max_leverage"],
        max_rounds=3,
    )


def _world_state() -> dict:
    return {"symbol": "AMZN", "price": 185.0}


def test_patterns_rendered_in_prompt():
    patterns = [
        {
            "pattern_type": "min_risk_reward",
            "observation": "target too close to entry",
            "weighted_confidence": 0.8,
        }
    ]
    prompt = _build_user_prompt(_world_state(), _constraints(), None, patterns)
    assert "## Relevant patterns (from coach memory)" in prompt
    assert "min_risk_reward" in prompt
    assert "confidence 0.80" in prompt
    assert "target too close to entry" in prompt


def test_no_patterns_no_section():
    prompt = _build_user_prompt(_world_state(), _constraints(), None, None)
    assert "## Relevant patterns" not in prompt


def test_empty_patterns_list_no_section():
    prompt = _build_user_prompt(_world_state(), _constraints(), None, [])
    assert "## Relevant patterns" not in prompt


def test_patterns_appear_before_propose_line():
    patterns = [
        {
            "pattern_type": "max_leverage",
            "observation": "leverage too high",
            "weighted_confidence": 0.9,
        }
    ]
    prompt = _build_user_prompt(_world_state(), _constraints(), None, patterns)
    pattern_pos = prompt.index("## Relevant patterns")
    propose_pos = prompt.index("Propose your trading actions now.")
    assert pattern_pos < propose_pos
