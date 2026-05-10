from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConstraintSchema:
    max_position_pct: float
    max_single_trade_pct: float
    max_leverage: float
    max_drawdown_pct: float
    allowed_symbols: list[str]
    max_open_positions: int
    min_risk_reward: float
    abort_on_violations: list[str]
    max_rounds: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConstraintSchema:
        return cls(
            max_position_pct=data["max_position_pct"],
            max_single_trade_pct=data["max_single_trade_pct"],
            max_leverage=data["max_leverage"],
            max_drawdown_pct=data["max_drawdown_pct"],
            allowed_symbols=data["allowed_symbols"],
            max_open_positions=data["max_open_positions"],
            min_risk_reward=data["min_risk_reward"],
            abort_on_violations=data["abort_on_violations"],
            max_rounds=data.get("max_rounds", 3),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_position_pct": self.max_position_pct,
            "max_single_trade_pct": self.max_single_trade_pct,
            "max_leverage": self.max_leverage,
            "max_drawdown_pct": self.max_drawdown_pct,
            "allowed_symbols": self.allowed_symbols,
            "max_open_positions": self.max_open_positions,
            "min_risk_reward": self.min_risk_reward,
            "max_rounds": self.max_rounds,
            "abort_on_violations": self.abort_on_violations,
        }
