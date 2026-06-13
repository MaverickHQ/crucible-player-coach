from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


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
    # Feature 10: half-Kelly sizing reference (capped by max_single_trade_pct).
    kelly_fraction: float | None = None
    # Feature 12: challenge phase + profit fraction. None outside a challenge.
    challenge_phase: str | None = None
    challenge_pnl_pct: float | None = None
    # Feature 13: daily consistency signal — ok / approaching / breached.
    consistency_status: str = "ok"
    # Feature 14: Monte Carlo P(pass) checked at session start. None until run.
    mc_success_prob: float | None = None
    position: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the canonical prompt dict (driven by the dataclass
        fields, so a new field is included automatically). ``position`` is
        omitted when ``None`` to preserve the runner's shape. Fresh dict each call.
        """
        data: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "position" and value is None:
                continue
            data[f.name] = value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        """Build from a dict, ignoring unknown keys (e.g. portfolio fields merged
        in by the coach loop) and applying the dataclass defaults for absent
        optional fields."""
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})
