from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from player_coach.portfolio.position import Position


@dataclass
class PortfolioState:
    capital: float
    daily_starting_balance: float
    peak_capital: float
    cash_available: float
    open_positions: list[Position] = field(default_factory=list)
    daily_pnl: float = 0.0
    cumulative_pnl: float = 0.0
    consistency_pct: float = 0.0
    trading_days_active: int = 0

    @property
    def current_drawdown_pct(self) -> float:
        if self.daily_starting_balance == 0.0:
            return 0.0
        return (self.daily_starting_balance - self.capital) / self.daily_starting_balance

    def to_dict(self) -> dict[str, Any]:
        return {
            "capital": self.capital,
            "daily_starting_balance": self.daily_starting_balance,
            "peak_capital": self.peak_capital,
            "cash_available": self.cash_available,
            "open_positions": [p.to_dict() for p in self.open_positions],
            "daily_pnl": self.daily_pnl,
            "cumulative_pnl": self.cumulative_pnl,
            "consistency_pct": self.consistency_pct,
            "trading_days_active": self.trading_days_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PortfolioState:
        return cls(
            capital=data["capital"],
            daily_starting_balance=data["daily_starting_balance"],
            peak_capital=data["peak_capital"],
            cash_available=data["cash_available"],
            open_positions=[
                Position.from_dict(p) for p in data.get("open_positions", [])
            ],
            daily_pnl=data.get("daily_pnl", 0.0),
            cumulative_pnl=data.get("cumulative_pnl", 0.0),
            consistency_pct=data.get("consistency_pct", 0.0),
            trading_days_active=data.get("trading_days_active", 0),
        )
