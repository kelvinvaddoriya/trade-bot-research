import numpy as np
import pandas as pd
import pytest

from tradebot.models import Position
from tradebot.strategies import S1Trend, S2Pullback, S3Breakout, S4Monkey, is_period_end

D = pd.Timestamp("2020-01-31")


def row(**kw):
    base = {"fresh": True, "ready": True}
    return pd.Series({**base, **kw})


def pos(sym, stop=0.0, bars=1):
    return Position(sym, 1.0, 100.0, D.date(), stop, bars_held=bars)


def bars(closes):
    c = pd.Series(closes, index=pd.bdate_range("2019-01-01", periods=len(closes)), dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_period_end():
    assert is_period_end(D, pd.Timestamp("2020-02-03"), "M")
    assert not is_period_end(pd.Timestamp("2020-01-30"), D, "M")
    assert not is_period_end(D, None, "M")


# ---- S1 ----

def test_s1_features_trend_flag():
    f = S1Trend(sma_n=20).features(bars(np.linspace(100, 150, 60)))
    assert not f["in_trend"].iloc[:20].any() and f["in_trend"].iloc[-1]


def test_s1_entries_weights_inverse_vol_and_only_on_check_days():
    s = S1Trend()
    rows = {"A": row(close=10, in_trend=True, atr=0.5, vol=0.01),
            "B": row(close=20, in_trend=True, atr=1.0, vol=0.02),
            "C": row(close=30, in_trend=False, atr=1.0, vol=0.01)}
    assert s.decide(D, rows, {}, check_day=False) == []
    sig = {x.symbol: x for x in s.decide(D, rows, {}, check_day=True)}
    assert set(sig) == {"A", "B"}
    assert sig["A"].features["weight"] == pytest.approx(2 / 3)       # half the vol, twice the weight
    assert sig["A"].stop_distance == pytest.approx(1.5)              # 3 x ATR


def test_s1_exit_when_trend_lost_and_trail_only_up():
    s = S1Trend()
    rows = {"A": row(close=10, in_trend=False, atr=0.5, vol=0.01),
            "B": row(close=20, in_trend=True, atr=1.0, vol=0.02)}
    sig = s.decide(D, rows, {"A": pos("A"), "B": pos("B", stop=16.0)}, check_day=True)
    assert [(x.symbol, x.kind) for x in sig] == [("A", "exit"), ("B", "trail")]
    assert sig[1].stop_price == pytest.approx(17.0)
    assert s.decide(D, rows, {"B": pos("B", stop=18.0)}, check_day=True) == []   # never lowers a stop


# ---- S2 ----

def test_s2_features_setup_on_sharp_pullback_in_uptrend():
    closes = list(np.linspace(100, 200, 230)) + [190, 180]
    f = S2Pullback().features(bars(closes))
    assert f["setup"].iloc[-1] and not f["setup"].iloc[-3]


def test_s2_entries_ranked_by_rsi_and_limited_by_slots():
    s = S2Pullback(max_positions=2)
    rows = {"A": row(close=10, setup=True, rsi=8, atr=0.4),
            "B": row(close=10, setup=True, rsi=3, atr=0.4),
            "C": row(close=10, setup=True, rsi=5, atr=0.4, fresh=False),   # didn't trade today
            "H": row(close=10, setup=False, rsi=50, exit_sma=11, atr=0.4)}
    sig = s.decide(D, rows, {"H": pos("H")})
    assert [(x.symbol, x.kind) for x in sig] == [("B", "entry")]          # one free slot, lowest RSI wins
    assert sig[0].stop_distance == pytest.approx(1.0)                      # 2.5 x ATR


def test_s2_exits_on_bounce_and_time_stop_and_frees_slots():
    s = S2Pullback(max_positions=2, time_stop=10)
    rows = {"H1": row(close=12, exit_sma=11, rsi=60, setup=False, atr=1),   # bounce
            "H2": row(close=9, exit_sma=11, rsi=20, setup=False, atr=1),    # time stop
            "N": row(close=10, setup=True, rsi=4, atr=1)}
    sig = s.decide(D, rows, {"H1": pos("H1", bars=2), "H2": pos("H2", bars=10)})
    assert [(x.symbol, x.kind) for x in sig] == [("H1", "exit"), ("H2", "exit"), ("N", "entry")]
    assert "time stop" in sig[1].reason


# ---- S3 ----

def test_s3_breakout_enters_above_the_prior_high_and_exits_below_the_prior_low():
    f = S3Breakout().features(bars([100.0] * 25 + [110.0]))
    assert f["breakout"].iloc[-1] and not f["breakout"].iloc[-2]
    rows = {"A": row(close=110, hi=101, lo=99, atr=2.0, breakout=True), "B": row(close=105, hi=100, lo=98, atr=1.0, breakout=True),
            "C": row(close=90, hi=100, lo=95, atr=1.0, breakout=False)}
    sig = S3Breakout().decide(D, rows, {"C": pos("C")})
    assert [(x.symbol, x.kind) for x in sig] == [("C", "exit"), ("A", "entry"), ("B", "entry")]   # strongest first
    assert sig[1].stop_distance == 4.0


def test_s3_features_are_causal():
    df = bars(list(np.random.default_rng(1).normal(0, 1, 80).cumsum() + 100))
    pd.testing.assert_frame_equal(S3Breakout().features(df).iloc[:60], S3Breakout().features(df.iloc[:60]))


# ---- S4 ----

def test_s4_monkey_replays_the_same_picks_and_exits_on_time():
    s, rows = S4Monkey(), {k: row(close=10.0, atr=0.5) for k in "ABCDEF"}
    first = [x.symbol for x in s.decide(D, rows, {})]
    assert len(first) == 2 and first == [x.symbol for x in s.decide(D, rows, {})]      # seeded by the date
    sig = s.decide(D, rows, {"A": pos("A", bars=5), "B": pos("B", bars=2)})
    assert [x.symbol for x in sig if x.kind == "exit"] == ["A"] and sum(x.kind == "entry" for x in sig) == 1
    assert all(x.symbol not in ("A", "B") for x in sig if x.kind == "entry")
