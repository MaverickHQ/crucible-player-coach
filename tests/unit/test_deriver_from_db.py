from __future__ import annotations
import json
from pathlib import Path

from player_coach.constraints.deriver import ConstraintDeriver
from player_coach.database.store import DatabaseStore


def _make_store(tmp_path: Path) -> DatabaseStore:
    return DatabaseStore(tmp_path / "test.db")


def _approved_artifact(run_id: str, strategy_id: str, size_pct: float,
                        entry: float, stop: float, target: float) -> dict:
    proposal = {
        "actions": [{
            "action_type": "enter_long",
            "symbol": "AMZN",
            "size_pct": size_pct,
            "entry_price": entry,
            "stop_loss": stop,
            "take_profit": target,
            "position_id": None,
        }]
    }
    return {
        "run_id": run_id,
        "timestamp": "2026-01-01T10:00:00+00:00",
        "strategy_id": strategy_id,
        "symbol": "AMZN",
        "outcome": "APPROVE",
        "rounds_taken": 1,
        "total_tokens": 80,
        "constraint_snapshot": None,
        "portfolio_snapshot": None,
        "daily_pnl_at_time": 0.0,
        "rounds": [
            {
                "round": 1,
                "proposal": proposal,
                "evaluation": {
                    "decision": "APPROVE",
                    "violations": [],
                    "feedback": "Looks good.",
                },
                "tokens_used": {"player": 50, "coach": 30},
            }
        ],
    }


def test_from_db_empty_store_returns_safe_defaults(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    schema = ConstraintDeriver.from_db(store).derive()
    assert schema.max_single_trade_pct == 0.05
    assert schema.min_risk_reward == 1.5
    assert schema.allowed_symbols == ["AMZN", "MSFT"]


def test_from_db_end_to_end(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.save_exchange(_approved_artifact("r1", "strat-a", 0.03, 185.0, 183.0, 191.0))
    store.save_coach_memory({
        "strategy_id": "strat-a",
        "pattern_type": "breakout",
        "symbol": "TSLA",
        "observation": "strong breakout",
        "confidence": 0.85,
    })

    schema = ConstraintDeriver.from_db(store).derive()

    # 80th-pct of [0.03] → 0.03, not the default 0.05
    assert schema.max_single_trade_pct == 0.03
    # TSLA confidence 0.85 ≥ 0.6 → appears in allowed_symbols
    assert "TSLA" in schema.allowed_symbols


def test_from_db_strategy_filter(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.save_exchange(_approved_artifact("r1", "strat-a", 0.03, 185.0, 183.0, 191.0))
    store.save_exchange(_approved_artifact("r2", "strat-b", 0.08, 185.0, 183.0, 191.0))

    schema_a = ConstraintDeriver.from_db(store, strategy_id="strat-a").derive()
    schema_b = ConstraintDeriver.from_db(store, strategy_id="strat-b").derive()

    # strat-a derives from size 0.03; strat-b from size 0.08
    assert schema_a.max_single_trade_pct == 0.03
    assert schema_b.max_single_trade_pct == 0.08


def test_from_db_none_strategy_id_reads_all_history(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.save_exchange(_approved_artifact("r1", "strat-a", 0.03, 185.0, 183.0, 191.0))
    store.save_exchange(_approved_artifact("r2", "strat-b", 0.07, 185.0, 183.0, 191.0))

    schema = ConstraintDeriver.from_db(store, strategy_id=None).derive()

    # Both runs in pool → 80th-pct of [0.03, 0.07]
    assert schema.max_single_trade_pct in (0.03, 0.07)
