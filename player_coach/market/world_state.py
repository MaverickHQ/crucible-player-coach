from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Canonical market-state keys. Downstream features (F6 regime, F7 garch, F8 atr,
# F9 vwap, F10 kelly, F12 challenge_phase) each add ONE field to this model
# rather than editing the four ad-hoc dict sites this seam replaces.
_OPTIONAL_DEFAULTS: dict[str, Any] = {
    "session": "NY_open",
    "regime_label": "unknown",
    "regime_probability": 0.0,
    "garch_vol": None,
    "atr": None,
    "vwap": None,
    "price_vs_vwap": None,
    "position": None,
}

# Required positional/market fields, in declaration order.
_REQUIRED_FIELDS = ("symbol", "price", "sma5", "sma10", "volume")


@dataclass
class WorldState:
    """Formal market world state fed to the Player and Coach.

    Replaces the ad-hoc dicts previously built in the backtest runner, the demo
    script, and the dashboard. ``to_dict()`` is the canonical prompt dict:

    - the backtest runner builds no ``position`` → it is omitted when ``None``;
    - the demo/dashboard pass ``position="flat"`` → it appears in the output.

    The model is intentionally mutable: the market-feature enricher (Seam 4)
    writes computed fields (regime_label, garch_vol, ...) onto an instance.
    """

    symbol: str
    price: float
    sma5: float
    sma10: float
    volume: int
    session: str = "NY_open"
    # Feature 6: data-driven regime from the HMM. "unknown" until enriched.
    regime_label: str = "unknown"
    regime_probability: float = 0.0
    # Feature 7: next-day GARCH(1,1) conditional vol forecast. None until enriched.
    garch_vol: float | None = None
    # Feature 8: 14-day Wilder ATR. None until enriched.
    atr: float | None = None
    # Feature 9: rolling VWAP and signed (price - vwap)/vwap. None until enriched.
    vwap: float | None = None
    price_vs_vwap: float | None = None
    position: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the canonical prompt dict.

        ``position`` is omitted entirely when ``None`` so the runner's shape is
        preserved exactly. A fresh dict is returned on every call.
        """
        data: dict[str, Any] = {
            "symbol": self.symbol,
            "price": self.price,
            "sma5": self.sma5,
            "sma10": self.sma10,
            "volume": self.volume,
        }
        if self.position is not None:
            data["position"] = self.position
        data["regime_label"] = self.regime_label
        data["regime_probability"] = self.regime_probability
        data["garch_vol"] = self.garch_vol
        data["atr"] = self.atr
        data["vwap"] = self.vwap
        data["price_vs_vwap"] = self.price_vs_vwap
        data["session"] = self.session
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        """Build from a dict, ignoring unknown keys and applying defaults.

        Unknown keys (e.g. portfolio fields merged in by the coach loop) are
        tolerated rather than raising, so a merged prompt dict round-trips back
        to its market core.
        """
        return cls(
            symbol=data["symbol"],
            price=data["price"],
            sma5=data["sma5"],
            sma10=data["sma10"],
            volume=data["volume"],
            session=data.get("session", _OPTIONAL_DEFAULTS["session"]),
            regime_label=data.get(
                "regime_label", _OPTIONAL_DEFAULTS["regime_label"]
            ),
            regime_probability=data.get(
                "regime_probability", _OPTIONAL_DEFAULTS["regime_probability"]
            ),
            garch_vol=data.get("garch_vol", _OPTIONAL_DEFAULTS["garch_vol"]),
            atr=data.get("atr", _OPTIONAL_DEFAULTS["atr"]),
            vwap=data.get("vwap", _OPTIONAL_DEFAULTS["vwap"]),
            price_vs_vwap=data.get(
                "price_vs_vwap", _OPTIONAL_DEFAULTS["price_vs_vwap"]
            ),
            position=data.get("position", _OPTIONAL_DEFAULTS["position"]),
        )
