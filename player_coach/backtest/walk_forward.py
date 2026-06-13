from __future__ import annotations

from player_coach.backtest.metrics import EquityCurve


def walk_forward_windows(
    n: int, fit_days: int, eval_days: int
) -> list[tuple[slice, slice]]:
    """Anchored walk-forward folds over ``n`` ordered observations.

    Each fold is ``(fit, eval)``: the fit window is anchored at index 0 and grows;
    the eval (out-of-sample) window is the next ``eval_days`` strictly *after* the
    fit window — so no fold ever evaluates on data its fit window saw, which is
    what prevents data snooping. Slides forward by ``eval_days`` until exhausted.
    """
    if fit_days <= 0 or eval_days <= 0:
        return []
    windows: list[tuple[slice, slice]] = []
    fit_end = fit_days
    while fit_end + eval_days <= n:
        windows.append((slice(0, fit_end), slice(fit_end, fit_end + eval_days)))
        fit_end += eval_days
    return windows


def oos_returns(eval_curves: list[EquityCurve]) -> list[float]:
    """Concatenate the per-fold out-of-sample daily returns into one series.

    Returns are taken *within* each fold only — no spurious jump is introduced at
    fold boundaries — giving the combined out-of-sample return series for an
    aggregate metric (e.g. an OOS Sharpe).
    """
    out: list[float] = []
    for curve in eval_curves:
        caps = [c for _, c in curve]
        for prev, cur in zip(caps, caps[1:]):
            if prev:
                out.append(cur / prev - 1.0)
    return out
