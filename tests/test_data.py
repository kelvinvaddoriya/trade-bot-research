import datetime as dt

import pandas as pd
import pytest

from tradebot import data


def _bars(dates, closes, adj_factor=1.0):
    return pd.DataFrame({"date": dates, "open": closes, "high": closes, "low": closes, "close": closes,
                         "adjclose": [c * adj_factor for c in closes], "volume": [1000] * len(closes)})


@pytest.fixture
def con():
    c = data.connect(":memory:")
    days = [dt.date(2020, 1, d) for d in (2, 3, 6, 7, 8)]
    c.executemany("INSERT INTO fx VALUES (?,?,?)", [(d.isoformat(), 2.0, "test") for d in days])  # 1 EUR = 2 USD
    data.save_bars(c, _bars(days, [10, 11, 12, 13, 14]), "yahoo", "PROXY", "USD")     # €5, 5.5, 6, 6.5, 7
    data.save_bars(c, _bars(days[2:], [60, 61, 62], adj_factor=0.5), "yahoo", "UCITS.DE", "EUR")  # adjusted €30, 30.5, 31
    return c


INST = {"U": {"name": "u", "isin": "x", "market": "XETR", "currency": "EUR", "strategy": "s1_trend",
              "yahoo": "UCITS.DE", "proxy": "PROXY"}}


def test_proxy_is_stitched_in_eur_and_scaled_to_join(con):
    df = data.load_panel(INST, "s1_trend", con)["U"]
    assert list(df["is_proxy"]) == [True, True, False, False, False]
    # own history: adjclose/close factor applied (60 * 0.5 = 30)
    assert df["close"].iloc[2] == pytest.approx(30.0)
    # proxy in EUR is 5, 5.5, then 6 on the join day; scaled by 30/6 = 5 -> 25, 27.5
    assert df["close"].iloc[:2].tolist() == pytest.approx([25.0, 27.5])


def test_native_from_moves_the_join(con):
    inst = {"U": {**INST["U"], "native_from": "2020-01-07"}}
    df = data.load_panel(inst, "s1_trend", con)["U"]
    assert list(df["is_proxy"]) == [True, True, True, False, False]


def test_validate_flags_bad_rows():
    df = _bars([dt.date(2020, 1, d) for d in (2, 3, 6)], [10, 20, 20]).set_index("date")
    df.index = pd.to_datetime(df.index)
    df.loc[df.index[2], "low"] = 25          # low above high
    v = data.validate(df)
    assert v["jumps_over_25pct"] == 1 and v["high_below_low"] == 1
    assert len(data.usable(df)) == 2
