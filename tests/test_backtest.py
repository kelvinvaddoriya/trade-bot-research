import pandas as pd
import pytest

from tradebot import backtest
from tradebot.models import Signal

DAYS = pd.bdate_range("2020-01-01", periods=8)
RISK = {"hash": "h", "whitelist": ["A"], "max_orders_per_day": 10, "max_orders_per_minute": 1,
        "price_collar_pct": 0.02, "min_order_eur": 20, "max_position_eur": 250, "max_positions": 3,
        "capital_cap_eur": 1000, "risk_per_trade_pct": 0.005, "max_daily_loss_pct": 0.5, "max_drawdown_pct": 0.5}
COSTS = {"eu_slippage": 0.001, "us_slippage": 0.0, "us_fx_fee": 0.0}
INST = {"A": {"currency": "EUR"}}


def panel(opens, lows, closes):
    return {"A": pd.DataFrame({"open": opens, "high": [max(o, c) for o, c in zip(opens, closes)],
                               "low": lows, "close": closes, "volume": 1e6, "is_proxy": False}, index=DAYS)}


class Scripted:
    """Enters A on day `enter` (stop distance 5) and exits on day `leave`; sizing via weight = 1 -> €200 cap."""
    name = "scripted"
    max_position_eur = 200.0

    def __init__(self, enter, leave):
        self.enter, self.leave = DAYS[enter], DAYS[leave]

    def features(self, df):
        return pd.DataFrame({"close": df["close"]}, index=df.index)

    def is_check_day(self, day, nxt):
        return True

    def decide(self, day, rows, positions, check_day):
        r = rows["A"]
        if day == self.enter and "A" not in positions:
            return [Signal("scripted", "A", "buy", "entry", day.date(), "t", r.close, stop_distance=5.0, features={"weight": 1.0})]
        if day == self.leave and "A" in positions:
            return [Signal("scripted", "A", "sell", "exit", day.date(), "t", r.close)]
        return []


def run(p, strat):
    return backtest.run(strat, p, INST, 400, str(DAYS[0].date()), str(DAYS[-1].date()), COSTS, RISK)


def test_round_trip_fills_costs_and_accounting():
    closes = [100, 100, 101, 102, 103, 104, 105, 106]
    res = run(panel(closes, [c - 1 for c in closes], closes), Scripted(enter=1, leave=4))
    (t,) = res.trades
    assert t.entry_price == pytest.approx(101)                  # day-2 open 101 + slippage, capped by the limit (100 + 1 %)
    assert t.exit_price == pytest.approx(104 * 0.999)           # exit decided day 4, filled day-5 open
    assert t.qty * t.entry_price == pytest.approx(200, rel=1e-3)  # €200 strategy cap, sized on the signal close
    assert res.equity.iloc[-1] == pytest.approx(400 + t.pnl)    # accounting closes exactly
    assert t.pnl == pytest.approx(t.qty * (t.exit_price - t.entry_price))


def test_protective_stop_fills_at_stop():
    closes = [100, 100, 100, 100, 100, 100, 100, 100]
    lows = [99, 99, 99, 94, 99, 99, 99, 99]                     # entry at ~100 on day 2, stop ~95 hit day 3
    res = run(panel(closes, lows, closes), Scripted(enter=1, leave=7))
    (t,) = res.trades
    assert t.exit_reason == "protective stop"
    assert t.exit_price == pytest.approx((100 * 1.001 - 5) * 0.999)


class TwoSymbols(Scripted):
    """Enters A and B on the same day: both must pass even with a 1-order-per-minute limit."""

    def decide(self, day, rows, positions, check_day):
        if day != self.enter:
            return []
        return [Signal("scripted", s, "buy", "entry", day.date(), "t", rows[s].close, stop_distance=5.0,
                       features={"weight": 0.5}) for s in ("A", "B")]


def test_same_day_orders_are_not_cut_by_the_per_minute_limit():
    closes = [100.0] * 8
    p = panel(closes, [99.0] * 8, closes)
    p["B"] = p["A"].copy()
    res = backtest.run(TwoSymbols(1, 7), p, {**INST, "B": {"currency": "EUR"}}, 400, str(DAYS[0].date()),
                       str(DAYS[-1].date()), COSTS, {**RISK, "whitelist": ["A", "B"]})
    assert res.open_positions == 2 and not res.rejections


def test_gap_above_limit_leaves_entry_unfilled():
    opens = [100, 100, 105, 105, 105, 105, 105, 105]            # opens 5 % above the 100 close: limit 101 misses
    closes = [100, 100, 105, 105, 105, 105, 105, 105]
    res = run(panel(opens, [o - 1 for o in opens], closes), Scripted(enter=1, leave=7))
    assert res.trades == [] and res.unfilled == 1 and res.equity.iloc[-1] == pytest.approx(400)
