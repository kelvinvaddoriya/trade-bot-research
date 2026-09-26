"""Simulated fills (docs/06 §2.2) and the cost model (docs/06 §2.3). Prices are EUR per unit."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Costs:
    slippage: float          # per side, fraction of price (half-spread + slippage)
    fx_fee: float = 0.0      # per side, fraction of notional (Trading 212 FX fee on USD instruments)


def costs_for(inst: dict, cfg: dict, mult: float = 1.0) -> Costs:
    if inst["currency"] == "USD":
        return Costs(cfg["us_slippage"] * mult, cfg["us_fx_fee"] * mult)
    return Costs(cfg["eu_slippage"] * mult)


def fill_limit_buy(open_: float, limit: float, c: Costs) -> float | None:
    """DAY limit buy at the open: no fill if the market opens above the limit."""
    if open_ > limit:
        return None
    return min(open_ * (1 + c.slippage), limit)


def fill_market(open_: float, side: str, c: Costs) -> float:
    return open_ * (1 + c.slippage) if side == "buy" else open_ * (1 - c.slippage)


def fill_stop_sell(open_: float, low: float, stop: float, c: Costs) -> float | None:
    """Resting stop: a gap through the stop fills at the (worse) open, otherwise at the stop."""
    if open_ <= stop:
        return open_ * (1 - c.slippage)
    if low <= stop:
        return stop * (1 - c.slippage)
    return None


def fee(notional: float, c: Costs) -> float:
    return notional * c.fx_fee
