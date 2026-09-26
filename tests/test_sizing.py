import datetime as dt

import pytest

from tradebot.models import Signal
from tradebot.sizing import make_intent, size_entry

RISK = {"risk_per_trade_pct": 0.005, "max_position_eur": 250, "min_order_eur": 20}
DAY = dt.date(2020, 1, 31)


def s1(weight, close=50.0):
    return Signal("s1_trend", "A", "buy", "entry", DAY, "t", close, stop_distance=3, features={"weight": weight})


def s2(stop_distance, close=100.0):
    return Signal("s2_pullback", "B", "buy", "entry", DAY, "t", close, stop_distance=stop_distance)


def test_s1_budget_times_weight_at_worst_case_price():
    qty, notional, why = size_entry(s1(0.3), 600, 600, 1000, 250, RISK)
    assert notional == pytest.approx(180) and qty == pytest.approx(180 / 50.5) and why is None


def test_s1_capped_by_strategy_cap_and_cash():
    assert size_entry(s1(0.8), 600, 600, 1000, 250, RISK)[1] == pytest.approx(250)
    assert size_entry(s1(0.8), 600, 90, 1000, 250, RISK)[1] == pytest.approx(90)


def test_s2_risk_based():
    # €5 risk / €4 stop distance = 1.25 shares; notional at the €101 limit = €126.25
    qty, notional, _ = size_entry(s2(4.0), 400, 400, 1000, 200, RISK)
    assert qty == pytest.approx(1.25) and notional == pytest.approx(126.25)
    assert size_entry(s2(1.0), 400, 400, 1000, 200, RISK)[1] == pytest.approx(200)   # tight stop: capped
    assert size_entry(s2(4.0), 400, 400, 500, 200, RISK)[0] == pytest.approx(0.625)  # capital halved: risk halved


def test_below_minimum_order_is_skipped():
    assert size_entry(s2(40.0), 400, 400, 1000, 200, RISK) == (0.0, 0.0, "below minimum order")


def test_intents_entry_limit_and_exit_market():
    e = make_intent(s2(4.0), 1.25)
    assert e.order_type == "limit" and e.limit_price == pytest.approx(101.0)
    x = make_intent(Signal("s2_pullback", "B", "sell", "exit", DAY, "t", 100.0), 1.25)
    assert x.order_type == "market" and x.limit_price is None
    assert make_intent(s2(4.0), 1.25).id == e.id != x.id                               # deterministic ids
