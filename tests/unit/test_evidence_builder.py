from __future__ import annotations
import json

from player_coach.constraints.evidence_builder import build_evidence_policy


def _make_round(size_pct: float, entry: float, stop: float, target: float) -> dict:
    proposal = {
        "actions": [{
            "action_type": "enter_long",
            "symbol": "AMZN",
            "size_pct": size_pct,
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": target,
        }]
    }
    return {"proposal": json.dumps(proposal), "verdict": "APPROVE"}


def test_empty_inputs_returns_empty_policy():
    policy = build_evidence_policy([], [], {})
    assert policy == {"runs": [], "patterns": []}


def test_empty_db_produces_defaults_via_deriver():
    from player_coach.constraints.deriver import ConstraintDeriver
    deriver = ConstraintDeriver(build_evidence_policy([], [], {}))
    schema = deriver.derive()
    assert schema.max_single_trade_pct == 0.05
    assert schema.min_risk_reward == 1.5
    assert schema.allowed_symbols == ["AMZN", "MSFT"]


def test_approved_run_parsed_correctly():
    runs = [{"run_id": "r1"}]
    rounds_by_run = {"r1": [_make_round(0.03, 185.0, 183.0, 191.0)]}
    policy = build_evidence_policy(runs, [], rounds_by_run)
    assert len(policy["runs"]) == 1
    entry = policy["runs"][0]
    assert entry["outcome"] == "success"
    assert entry["trade_size_pct"] == 0.03
    # reward=6, risk=2 → RR=3.0
    assert entry["risk_reward"] == 3.0


def test_run_with_no_rounds_is_skipped():
    runs = [{"run_id": "r1"}]
    policy = build_evidence_policy(runs, [], {})
    assert policy["runs"] == []


def test_run_with_no_actions_is_skipped():
    runs = [{"run_id": "r1"}]
    rounds_by_run = {"r1": [{"proposal": json.dumps({"actions": []})}]}
    policy = build_evidence_policy(runs, [], rounds_by_run)
    assert policy["runs"] == []


def test_patterns_above_threshold_included():
    patterns = [
        {"symbol": "TSLA", "confidence": 0.8},
        {"symbol": "MSFT", "confidence": 0.6},
        {"symbol": "AMZN", "confidence": 0.4},  # below threshold — but builder doesn't filter
    ]
    policy = build_evidence_policy([], patterns, {})
    # builder passes all through; deriver filters at 0.6
    assert len(policy["patterns"]) == 3


def test_patterns_missing_symbol_excluded():
    patterns = [
        {"symbol": "TSLA", "confidence": 0.8},
        {"confidence": 0.9},           # no symbol
        {"symbol": None, "confidence": 0.7},  # None symbol
    ]
    policy = build_evidence_policy([], patterns, {})
    assert len(policy["patterns"]) == 1
    assert policy["patterns"][0]["symbol"] == "TSLA"


def test_last_round_proposal_used():
    # Two rounds: first rejected (size 0.10), second approved (size 0.03)
    rounds = [
        _make_round(0.10, 185.0, 183.0, 191.0),
        _make_round(0.03, 185.0, 183.0, 191.0),
    ]
    policy = build_evidence_policy([{"run_id": "r1"}], [], {"r1": rounds})
    assert policy["runs"][0]["trade_size_pct"] == 0.03
