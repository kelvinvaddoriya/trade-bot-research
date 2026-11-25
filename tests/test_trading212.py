import datetime as dt

import pytest

from tradebot import execution
from tradebot.trading212 import DEMO, T212Error, Trading212, current, last_closed, map_tickers, next_after, qty, sessions

META = [
    {"ticker": "SXR8d_EQ", "isin": "IE00B5BMR087", "currencyCode": "EUR", "name": "S&P", "type": "ETF", "workingScheduleId": 166},
    {"ticker": "CSPX_EQ", "isin": "IE00B5BMR087", "currencyCode": "USD", "name": "S&P", "type": "ETF", "workingScheduleId": 154},
    {"ticker": "AAPL_US_EQ", "isin": "US0378331005", "currencyCode": "USD", "name": "Apple", "type": "STOCK", "workingScheduleId": 71},
    {"ticker": "APCd_EQ", "isin": "US0378331005", "currencyCode": "EUR", "name": "Apple", "type": "STOCK", "workingScheduleId": 54},
]


def test_live_url_is_refused():
    with pytest.raises(ValueError):
        Trading212("k", "s", base="https://live.trading212.com/api/v0")
    assert Trading212("k", "s").base == DEMO


def test_quantity_rounds_down():
    assert qty(0.04129999) == 0.0412 and qty(1.0) == 1.0 and qty(2.4648, 3) == 2.464 and qty(2.4648, 2) == 2.46


def test_ticker_mapping_by_isin_currency_and_venue():
    inst = {"SXR8": {"isin": "IE00B5BMR087", "currency": "EUR", "market": "XETR"},
            "AAPL": {"isin": "US0378331005", "currency": "USD", "market": "XNYS"},
            "XXX": {"isin": "NOPE", "currency": "EUR", "market": "XETR"}}
    m = map_tickers(META, inst)
    assert m["SXR8"]["ticker"] == "SXR8d_EQ" and m["SXR8"]["schedule"] == 166
    assert m["AAPL"]["ticker"] == "AAPL_US_EQ"
    assert m["XXX"]["ticker"] == ""


def test_sessions_calendar_from_the_broker_schedule():
    ex = [{"workingSchedules": [
        {"id": 166, "timeEvents": [{"date": "2026-09-29T07:00:03.000Z", "type": "OPEN"}, {"date": "2026-09-29T15:30:00.000Z", "type": "CLOSE"},
                                   {"date": "2026-09-30T07:00:03.000Z", "type": "OPEN"}, {"date": "2026-09-30T15:30:00.000Z", "type": "CLOSE"},
                                   {"date": "2026-10-01T07:00:03.000Z", "type": "OPEN"}, {"date": "2026-10-01T15:30:00.000Z", "type": "CLOSE"}]},
        {"id": 56, "timeEvents": [{"date": "2026-09-30T08:00:00.000Z", "type": "PRE_MARKET_OPEN"}, {"date": "2026-09-30T13:30:00.000Z", "type": "OPEN"},
                                  {"date": "2026-09-30T20:00:00.000Z", "type": "AFTER_HOURS_OPEN"}]}]}]
    t = lambda d, h, m=0: dt.datetime(2026, 9, d, h, m, tzinfo=dt.UTC)
    xetra, nyse = sessions(ex, 166), sessions(ex, 56)
    assert len(xetra) == 3 and nyse == [(t(30, 13, 30), t(30, 20))]            # the US regular session ends at after-hours
    assert current(xetra, t(30, 10)) == xetra[1] and current(xetra, t(30, 16)) is None
    assert last_closed(xetra, t(30, 16)) == xetra[1] and last_closed(xetra, t(29, 6)) is None
    assert next_after(xetra, t(30, 16)) == xetra[2] and next_after(xetra, xetra[2][0]) is None
    assert sessions(ex, 999) == []


class LeavingOrder:
    """An order that disappears from the active list after filling (HTTP 404) and shows up in history."""

    def order(self, oid):
        raise T212Error(404, "not found")

    def order_history(self, ticker, oid):
        return {"id": oid, "status": "FILLED", "filledQuantity": 0.04, "filledValue": 29.0}


def test_wait_final_reads_history_so_a_fill_is_not_mistaken_for_a_cancel():
    o = execution.wait_final(LeavingOrder(), "SXR8d_EQ", 9, timeout=1)
    assert o["status"] == "FILLED" and execution.fill_price(o) == pytest.approx(725.0)


def test_rate_limit_rejections_are_retried(monkeypatch):
    """HTTP 429 means nothing was executed, so even an order POST is retried (up to 3 times); other errors are not."""
    import io
    import urllib.error
    import urllib.request

    replies = [429, 429, 200]

    class Reply:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"id": 1}'

    def urlopen(req, timeout):
        code = replies.pop(0)
        if code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "x", {"retry-after": "1"}, io.BytesIO(b"too many requests"))
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert Trading212("k", "s").place_limit("SXR8d_EQ", 0.1, 700) == {"id": 1} and not replies
    replies[:] = [400]
    with pytest.raises(T212Error):
        Trading212("k", "s").place_limit("SXR8d_EQ", 0.1, 700)


def test_clock_skew_is_measured_only_on_a_fast_round_trip(monkeypatch):
    """A slow request (a swapping laptop) once made a correct clock look 7 s off."""
    import email.utils
    import urllib.request

    class Reply:
        headers = {"Date": email.utils.formatdate(1000, usegmt=True)}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: Reply())
    for clock, expected in (([1000.0, 1000.0, 1014.0], None), ([1000.0, 1000.0, 1000.2], -0.4)):
        ticks = iter(clock)
        monkeypatch.setattr("time.time", lambda: next(ticks))
        t = Trading212("k", "s")
        t.summary()
        assert t.skew == (None if expected is None else pytest.approx(expected))
