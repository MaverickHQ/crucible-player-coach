from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Position:
    position_id: str
    symbol: str
    direction: str          # "long" | "short"
    entry_price: float
    quantity: float
    size_pct: float
    stop_loss: float
    take_profit: float
    opened_at: str          # ISO timestamp
    unrealized_pnl: float = 0.0

    def current_value(self, price: float) -> float:
        return self.quantity * price

    def is_stop_hit(self, price: float) -> bool:
        if self.direction == "long":
            return price <= self.stop_loss
        return price >= self.stop_loss

    def is_target_hit(self, price: float) -> bool:
        if self.direction == "long":
            return price >= self.take_profit
        return price <= self.take_profit

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "size_pct": self.size_pct,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "opened_at": self.opened_at,
            "unrealized_pnl": self.unrealized_pnl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Position:
        return cls(
            position_id=data["position_id"],
            symbol=data["symbol"],
            direction=data["direction"],
            entry_price=data["entry_price"],
            quantity=data["quantity"],
            size_pct=data["size_pct"],
            stop_loss=data["stop_loss"],
            take_profit=data["take_profit"],
            opened_at=data["opened_at"],
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
        )
