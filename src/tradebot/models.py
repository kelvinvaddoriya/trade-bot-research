"""Core data contracts (docs/04 §4).

Research and backtest code uses floats; Decimal rounding happens at the broker boundary (P1),
where quantities and prices are sent to Trading 212.
"""
import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Side = Literal["buy", "sell"]
Kind = Literal["entry", "exit", "trail"]


@dataclass(frozen=True)
class Signal:
    strategy: str
    symbol: str
    side: Side
    kind: Kind                  # entry, exit, or trail (raise the protective stop)
    bar_date: date
    reason: str
    close: float                # close of the signal bar, EUR
    stop_distance: float = 0.0  # entries: protective stop = fill price - stop_distance
    stop_price: float = 0.0     # trail: new stop level
    rank: float = 0.0           # lower is better when slots are scarce
    features: dict = field(default_factory=dict, compare=False)


def intent_id(strategy: str, symbol: str, side: str, bar_date: date) -> str:
    """Deterministic: the same signal can never produce a second intent (docs/04 §4)."""
    return hashlib.sha256(f"{strategy}|{symbol}|{side}|{bar_date}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class OrderIntent:
    id: str
    signal: Signal
    qty: float
    order_type: Literal["market", "limit"]
    limit_price: float | None
    notional_eur: float


@dataclass(frozen=True)
class RiskDecision:
    intent_id: str
    approved: bool
    reason: str | None
    limits_hash: str


@dataclass
class Position:
    """One strategy lot."""
    symbol: str
    qty: float
    entry_price: float
    entry_date: date
    stop: float
    entry_costs: float = 0.0
    bars_held: int = 0


@dataclass(frozen=True)
class Trade:
    """A closed round trip."""
    strategy: str
    symbol: str
    entry_date: date
    exit_date: date
    qty: float
    entry_price: float
    exit_price: float
    costs: float
    pnl: float                  # net of costs, EUR
    exit_reason: str
    bars_held: int
