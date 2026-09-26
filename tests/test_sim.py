import pytest

from tradebot.sim import Costs, costs_for, fee, fill_limit_buy, fill_market, fill_stop_sell

C = Costs(slippage=0.001, fx_fee=0.0015)


def test_limit_buy_fills_at_open_but_never_above_limit():
    assert fill_limit_buy(100.0, 101.0, C) == pytest.approx(100.1)
    assert fill_limit_buy(100.95, 101.0, C) == pytest.approx(101.0)     # slippage capped by the limit
    assert fill_limit_buy(102.0, 101.0, C) is None                      # gap up: unfilled


def test_market_fills_with_slippage_both_sides():
    assert fill_market(100.0, "buy", C) == pytest.approx(100.1)
    assert fill_market(100.0, "sell", C) == pytest.approx(99.9)


def test_stop_fills_at_stop_or_worse_open_on_a_gap():
    assert fill_stop_sell(100.0, 94.0, 95.0, C) == pytest.approx(94.905)  # traded through intraday
    assert fill_stop_sell(90.0, 88.0, 95.0, C) == pytest.approx(89.91)    # gapped below: fill at open
    assert fill_stop_sell(100.0, 96.0, 95.0, C) is None


def test_fx_fee_only_on_usd():
    assert fee(200.0, C) == pytest.approx(0.30)
    cfg = {"us_slippage": 0.0005, "us_fx_fee": 0.0015, "eu_slippage": 0.001}
    assert costs_for({"currency": "EUR"}, cfg) == Costs(0.001, 0.0)
    assert costs_for({"currency": "USD"}, cfg, mult=2) == Costs(0.001, 0.003)
