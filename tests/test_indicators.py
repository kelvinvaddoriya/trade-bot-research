import numpy as np
import pandas as pd
import pytest

from tradebot import indicators as ind


def s(values):
    return pd.Series(values, dtype=float)


def test_sma():
    assert ind.sma(s([1, 2, 3, 4, 5]), 3).tolist()[2:] == [2, 3, 4]
    assert ind.sma(s([1, 2, 3]), 3).isna().tolist() == [True, True, False]


def test_rsi_wilder_by_hand():
    # closes 1,2,1,2,1 with n=2: gains 1,0,1,0 / losses 0,1,0,1
    # seed (t=2): 0.5/0.5 -> 50; t=3: 0.75/0.25 -> 75; t=4: 0.375/0.625 -> 37.5
    assert ind.rsi(s([1, 2, 1, 2, 1]), 2).tolist()[2:] == pytest.approx([50, 75, 37.5])


def test_rsi_extremes():
    assert ind.rsi(s([1, 2, 3, 4]), 2).iloc[-1] == 100
    assert ind.rsi(s([4, 3, 2, 1]), 2).iloc[-1] == 0
    assert ind.rsi(s([5, 5, 5, 5]), 2).iloc[-1] == 50


def test_atr_by_hand():
    # true ranges: 2, max(3,3,0)=3, max(1,0,1)=1 -> seed (2+3)/2 = 2.5, then (2.5+1)/2 = 1.75
    h, l, c = s([10, 12, 11]), s([8, 9, 10]), s([9, 11, 10])
    assert ind.atr(h, l, c, 2).tolist()[1:] == pytest.approx([2.5, 1.75])


def test_bollinger_and_volatility():
    assert ind.bollinger_lower(s([5] * 5), 3, 2).iloc[-1] == 5
    assert ind.bollinger_lower(s([1, 2, 3]), 3, 1).iloc[-1] == pytest.approx(2 - np.std([1, 2, 3]))
    assert ind.volatility(s([100, 110, 99]), 2).iloc[-1] == pytest.approx(np.std([0.1, -0.1], ddof=1))


def test_indicators_are_causal():
    """Value at t on the full history == value at t on history truncated at t (no look-ahead)."""
    rng = np.random.default_rng(0)
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400))))
    h, l = c * 1.01, c * 0.99
    funcs = {
        "sma": lambda c, h, l: ind.sma(c, 50),
        "rsi": lambda c, h, l: ind.rsi(c, 2),
        "atr": lambda c, h, l: ind.atr(h, l, c, 14),
        "boll": lambda c, h, l: ind.bollinger_lower(c, 20, 2),
        "vol": lambda c, h, l: ind.volatility(c, 20),
    }
    for name, f in funcs.items():
        full = f(c, h, l)
        for t in (60, 150, 399):
            assert f(c[:t + 1], h[:t + 1], l[:t + 1]).iloc[-1] == pytest.approx(full.iloc[t]), name
