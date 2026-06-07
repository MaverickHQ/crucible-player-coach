from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from player_coach.loop.circuit_breakers import (
    is_consistency_rule_breached,
    is_daily_loss_limit_breached,
    is_mll_breached,
    is_trading_cutoff_reached,
)

if TYPE_CHECKING:
    from player_coach.constraints.schema import ConstraintSchema
    from player_coach.portfolio.state import PortfolioState

# A breaker check returns True when the account/day must be halted.
BreakerCheck = Callable[["PortfolioState", "ConstraintSchema"], bool]


@dataclass(frozen=True)
class CircuitBreaker:
    """A named pre-exchange halt. ``name`` is the artifact termination reason;
    lower ``priority`` is checked first."""

    name: str
    priority: int
    check: BreakerCheck


def default_breakers() -> list[CircuitBreaker]:
    """The standing breakers, highest priority first:
    MLL (account terminated) → daily loss → consistency → trading cutoff."""
    return [
        CircuitBreaker("mll_breached", 1, lambda p, c: is_mll_breached(p, c)),
        CircuitBreaker(
            "daily_loss_limit", 2, lambda p, c: is_daily_loss_limit_breached(p, c)
        ),
        CircuitBreaker(
            "consistency_rule", 3, lambda p, c: is_consistency_rule_breached(p, c)
        ),
        CircuitBreaker("trading_cutoff", 4, lambda p, c: is_trading_cutoff_reached(c)),
    ]


class BreakerRegistry:
    """Ordered set of circuit breakers checked before each exchange.

    Replaces the hardcoded if-ladder in the coach loop so new breakers (F11
    trailing drawdown, F13 consistency) plug in by priority without editing the
    loop body.
    """

    def __init__(self, breakers: list[CircuitBreaker] | None = None) -> None:
        chosen = default_breakers() if breakers is None else list(breakers)
        self._breakers = sorted(chosen, key=lambda b: b.priority)

    def register(self, breaker: CircuitBreaker) -> None:
        self._breakers.append(breaker)
        self._breakers.sort(key=lambda b: b.priority)

    def names(self) -> list[str]:
        return [b.name for b in self._breakers]

    def first_breach(
        self, portfolio: "PortfolioState", constraints: "ConstraintSchema"
    ) -> str | None:
        """Return the name of the highest-priority breached breaker, or None."""
        for breaker in self._breakers:
            if breaker.check(portfolio, constraints):
                return breaker.name
        return None
