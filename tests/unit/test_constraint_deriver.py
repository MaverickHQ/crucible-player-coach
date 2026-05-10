import json
from pathlib import Path

from player_coach.constraints.deriver import ConstraintDeriver
from player_coach.constraints.schema import ConstraintSchema


def test_derive_returns_constraint_schema_instance():
    deriver = ConstraintDeriver({})
    assert isinstance(deriver.derive(), ConstraintSchema)


def test_derive_with_empty_evidence_uses_defaults():
    schema = ConstraintDeriver({}).derive()
    assert schema.max_single_trade_pct == 0.05
    assert schema.max_position_pct == 0.10
    assert schema.min_risk_reward == 1.5
    assert schema.allowed_symbols == ["AMZN", "MSFT"]


def test_derive_with_evidence_sets_max_single_trade_pct():
    # 5 successful runs with trade sizes; 80th percentile of [0.02,0.03,0.04,0.05,0.06]
    # sorted: [0.02, 0.03, 0.04, 0.05, 0.06], idx = int(5*0.8) = 4 → 0.06
    policy = {
        "runs": [
            {"outcome": "success", "trade_size_pct": 0.03, "risk_reward": 2.0},
            {"outcome": "success", "trade_size_pct": 0.05, "risk_reward": 2.5},
            {"outcome": "success", "trade_size_pct": 0.02, "risk_reward": 1.8},
            {"outcome": "success", "trade_size_pct": 0.06, "risk_reward": 3.0},
            {"outcome": "success", "trade_size_pct": 0.04, "risk_reward": 2.2},
        ]
    }
    schema = ConstraintDeriver(policy).derive()
    assert schema.max_single_trade_pct == 0.06
    assert schema.max_position_pct == 0.12


def test_derive_ignores_failed_runs():
    policy = {
        "runs": [
            {"outcome": "failure", "trade_size_pct": 0.20, "risk_reward": 0.5},
            {"outcome": "success", "trade_size_pct": 0.03, "risk_reward": 2.0},
        ]
    }
    schema = ConstraintDeriver(policy).derive()
    assert schema.max_single_trade_pct == 0.03


def test_derive_symbols_from_high_confidence_patterns():
    policy = {
        "patterns": [
            {"symbol": "TSLA", "confidence": 0.9},
            {"symbol": "AMZN", "confidence": 0.7},
            {"symbol": "MSFT", "confidence": 0.5},
        ]
    }
    schema = ConstraintDeriver(policy).derive()
    assert schema.allowed_symbols[0] == "TSLA"
    assert "AMZN" in schema.allowed_symbols


def test_derive_hard_limits_are_fixed():
    policy = {
        "runs": [
            {"outcome": "success", "trade_size_pct": 0.50, "risk_reward": 0.1},
        ]
    }
    schema = ConstraintDeriver(policy).derive()
    assert schema.max_leverage == 1.5
    assert schema.max_drawdown_pct == 0.10
    assert schema.max_daily_loss_pct == 0.02
    assert schema.consistency_rule_pct == 0.50
    assert schema.trading_cutoff_time == "16:20"


def test_from_policy_file_loads_json(tmp_path: Path):
    policy = {
        "runs": [
            {"outcome": "success", "trade_size_pct": 0.04, "risk_reward": 2.0}
        ]
    }
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(json.dumps(policy))
    deriver = ConstraintDeriver.from_policy_file(policy_file)
    schema = deriver.derive()
    assert isinstance(schema, ConstraintSchema)
    assert schema.max_single_trade_pct == 0.04
