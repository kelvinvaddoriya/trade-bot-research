import datetime as dt
import json

import pytest

from tradebot import risk
from tradebot.models import Signal
from tradebot.sizing import make_intent

R = {"hash": "h", "whitelist": ["SAP", "AAPL"], "max_orders_per_day": 10, "max_orders_per_minute": 2,
     "price_collar_pct": 0.02, "min_order_eur": 20, "max_position_eur": 250, "max_positions": 2,
     "capital_cap_eur": 1000}
DAY = dt.date(2020, 1, 31)


def entry(sym="SAP", close=100.0, qty=1.5):
    return make_intent(Signal("s2_pullback", sym, "buy", "entry", DAY, "t", close, stop_distance=4), qty)


def exit_(sym="SAP", qty=1.0):
    return make_intent(Signal("s2_pullback", sym, "sell", "exit", DAY, "t", 100.0), qty)


def state(**kw):
    st = risk.RiskState(day=DAY, cash_eur=400, last_bar={"SAP": DAY, "AAPL": DAY},
                        last_close={"SAP": 100.0, "AAPL": 100.0})
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def test_clean_entry_passes_and_is_recorded():
    st = state()
    d = risk.check(entry(), st, R)
    assert d.approved and d.limits_hash == "h" and st.orders_today == 1
    assert risk.check(entry(), st, R).reason == "duplicate intent"


@pytest.mark.parametrize("intent,st,reason", [
    (entry(sym="TSLA"), state(), "not on whitelist"),
    (exit_(qty=2.0), state(held_qty={"SAP": 1.0}), "sell exceeds holding (no shorting)"),
    (entry(), state(orders_today=10), "order rate limit"),
    (entry(), state(orders_this_minute=2), "order rate limit"),
    (entry(), state(last_bar={"SAP": DAY - dt.timedelta(days=9)}), "stale or missing data"),
    (entry(), state(last_close={"SAP": 90.0}), "price collar"),
    (entry(qty=0.1), state(), "notional outside [min, max]"),
    (entry(qty=3.0), state(), "notional outside [min, max]"),
    (entry(), state(held_qty={"AAPL": 1, "SAP": 0, "X": 2}), "max positions"),
    (entry(), state(deployed_eur=900), "capital cap"),
    (entry(), state(daily_loss_hit=True), "daily loss limit"),
    (entry(), state(cash_eur=100), "insufficient cash"),
    (entry(), state(mode="yolo"), "unknown mode yolo"),
    (entry(), state(tradable={"AAPL"}), "market has no next session"),
])
def test_each_check_rejects(intent, st, reason):
    d = risk.check(intent, st, R)
    assert not d.approved and d.reason == reason


def test_exits_skip_entry_only_limits():
    st = state(held_qty={"SAP": 1.0}, daily_loss_hit=True, cash_eur=0, deployed_eur=5000)
    assert risk.check(exit_(), st, R).approved


def test_kill_switch_is_sticky_and_blocks_everything():
    risk.trip("drawdown 10%")
    assert risk.is_tripped() and risk.state()["reason"] == "drawdown 10%"   # a "restart" just re-reads the file
    st = state(held_qty={"SAP": 1.0}, mode="demo")
    assert risk.check(exit_(), st, R).reason == "kill switch tripped"
    assert risk.check(exit_(), state(held_qty={"SAP": 1.0}), R).approved    # backtests don't read the file
    risk.reset("owner", "tested")
    assert not risk.is_tripped()
    assert [json.loads(l)["tripped"] for l in risk.KILL_LOG.read_text().splitlines()] == [True, False]
