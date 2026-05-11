from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from player_coach.constraints.schema import ConstraintSchema

_DEFAULT_SYMBOLS = ["AMZN", "MSFT"]


class ConstraintDeriver:
    def __init__(self, evidence_policy: dict[str, Any]) -> None:
        self._policy = evidence_policy

    def derive(self) -> ConstraintSchema:
        runs = self._policy.get("runs", [])
        patterns = self._policy.get("patterns", [])

        max_single_trade_pct = self._derive_trade_pct(runs)
        min_risk_reward = self._derive_min_rr(runs)
        allowed_symbols = self._derive_symbols(patterns)

        return ConstraintSchema(
            max_single_trade_pct=max_single_trade_pct,
            max_position_pct=round(max_single_trade_pct * 2, 4),
            max_leverage=1.5,
            max_drawdown_pct=0.10,
            allowed_symbols=allowed_symbols,
            max_open_positions=3,
            min_risk_reward=min_risk_reward,
            abort_on_violations=["max_leverage", "max_drawdown_pct"],
            max_rounds=3,
            max_daily_loss_pct=0.02,
            consistency_rule_pct=0.50,
            trading_cutoff_time="16:20",
        )

    @classmethod
    def from_policy_file(cls, path: str | Path) -> ConstraintDeriver:
        data = json.loads(Path(path).read_text())
        return cls(data)

    # ---------------------------------------------------------------- helpers

    def _derive_trade_pct(self, runs: list[dict[str, Any]]) -> float:
        sizes = [
            r["trade_size_pct"]
            for r in runs
            if r.get("outcome") == "success" and "trade_size_pct" in r
        ]
        if not sizes:
            return 0.05
        sizes.sort()
        idx = int(len(sizes) * 0.8)
        return sizes[min(idx, len(sizes) - 1)]

    def _derive_min_rr(self, runs: list[dict[str, Any]]) -> float:
        rr_values = [
            r["risk_reward"]
            for r in runs
            if r.get("outcome") == "success" and "risk_reward" in r
        ]
        if not rr_values:
            return 1.5
        rr_values.sort()
        idx = max(0, int(len(rr_values) * 0.25) - 1)
        return rr_values[idx]

    def _derive_symbols(self, patterns: list[dict[str, Any]]) -> list[str]:
        qualified_symbols = [
            p["symbol"]
            for p in patterns
            if "symbol" in p and p.get("confidence", 0.0) >= 0.6
        ]
        if not qualified_symbols:
            return list(_DEFAULT_SYMBOLS)
        seen: dict[str, float] = {}
        for p in patterns:
            sym = p.get("symbol")
            conf = p.get("confidence", 0.0)
            if sym and conf >= 0.6:
                seen[sym] = max(seen.get(sym, 0.0), conf)
        return sorted(seen, key=lambda s: seen[s], reverse=True)
