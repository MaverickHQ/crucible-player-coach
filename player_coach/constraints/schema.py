from __future__ import annotations
from dataclasses import dataclass
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
    max_daily_loss_pct: float = 0.02
    consistency_rule_pct: float = 0.50
    trading_cutoff_time: str = "16:20"
    # Feature 8: entry stop must be >= this multiple of ATR from entry.
    min_stop_atr_multiple: float = 1.5
    # Feature 9: SOFT preference — prefer entries below VWAP. Advisory, not a
    # hard constraint; the Coach notes it but never rejects for it alone.
    prefer_entry_below_vwap: bool = True

    def is_daily_loss_breached(
        self, daily_pnl: float, daily_starting_balance: float
    ) -> bool:
        if daily_starting_balance == 0.0:
            return False
        return (-daily_pnl / daily_starting_balance) > self.max_daily_loss_pct

    def is_consistency_breached(
        self, day_pnl: float, cumulative_pnl: float
    ) -> bool:
        if cumulative_pnl <= 0.0:
            return False
        return day_pnl > self.consistency_rule_pct * cumulative_pnl

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
            max_daily_loss_pct=data.get("max_daily_loss_pct", 0.02),
            consistency_rule_pct=data.get("consistency_rule_pct", 0.50),
            trading_cutoff_time=data.get("trading_cutoff_time", "16:20"),
            min_stop_atr_multiple=data.get("min_stop_atr_multiple", 1.5),
            prefer_entry_below_vwap=data.get("prefer_entry_below_vwap", True),
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
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "consistency_rule_pct": self.consistency_rule_pct,
            "trading_cutoff_time": self.trading_cutoff_time,
            "min_stop_atr_multiple": self.min_stop_atr_multiple,
            "prefer_entry_below_vwap": self.prefer_entry_below_vwap,
        }
