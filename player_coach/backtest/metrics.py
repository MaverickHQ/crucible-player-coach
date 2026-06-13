from __future__ import annotations

import numpy as np

# An equity curve is a list of (date_str, capital) points.
EquityCurve = list[tuple[str, float]]


def _capitals(curve: EquityCurve) -> np.ndarray:
    return np.array([c for _, c in curve], dtype=float)


def daily_returns(curve: EquityCurve) -> np.ndarray:
    caps = _capitals(curve)
    if caps.size < 2:
        return np.empty(0, dtype=float)
    return caps[1:] / caps[:-1] - 1.0


def sharpe_ratio(curve: EquityCurve, periods_per_year: int = 252) -> float:
    """Annualised Sharpe (risk-free 0). 0.0 for flat/insufficient data."""
    r = daily_returns(curve)
    if r.size == 0:
        return 0.0
    sd = float(r.std())
    if sd == 0.0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(periods_per_year))


def sortino_ratio(curve: EquityCurve, periods_per_year: int = 252) -> float:
    """Annualised Sortino — like Sharpe but penalising only downside deviation."""
    r = daily_returns(curve)
    if r.size == 0:
        return 0.0
    downside = r[r < 0.0]
    dd = float(downside.std()) if downside.size > 0 else 0.0
    if dd == 0.0:
        return 0.0
    return float(r.mean() / dd * np.sqrt(periods_per_year))


def max_drawdown(curve: EquityCurve) -> float:
    """Largest peak-to-trough decline as a positive fraction of the peak."""
    caps = _capitals(curve)
    if caps.size == 0:
        return 0.0
    peak = np.maximum.accumulate(caps)
    return float(((peak - caps) / peak).max())


def calmar_ratio(curve: EquityCurve, periods_per_year: int = 252) -> float:
    """CAGR / max drawdown. 0.0 when drawdown is zero or data is insufficient."""
    caps = _capitals(curve)
    if caps.size < 2 or caps[0] <= 0:
        return 0.0
    mdd = max_drawdown(curve)
    if mdd == 0.0:
        return 0.0
    years = (caps.size - 1) / periods_per_year
    if years <= 0:
        return 0.0
    cagr = (caps[-1] / caps[0]) ** (1.0 / years) - 1.0
    return float(cagr / mdd)


def drawdown_duration(curve: EquityCurve) -> int:
    """Longest consecutive run (in periods) the equity spends below a prior peak."""
    caps = _capitals(curve)
    if caps.size == 0:
        return 0
    peak = np.maximum.accumulate(caps)
    underwater = caps < peak
    longest = run = 0
    for u in underwater:
        run = run + 1 if u else 0
        longest = max(longest, run)
    return int(longest)


def avg_recovery_time(curve: EquityCurve) -> float:
    """Average periods from first dropping below a peak to recovering it.

    Drawdowns that never recover by the end of the curve are not counted.
    """
    caps = _capitals(curve)
    if caps.size == 0:
        return 0.0
    peak = caps[0]
    started: int | None = None
    recoveries: list[int] = []
    for i, c in enumerate(caps):
        if c >= peak:
            if started is not None:
                recoveries.append(i - started)
                started = None
            peak = c
        elif started is None:
            started = i
    return float(np.mean(recoveries)) if recoveries else 0.0
