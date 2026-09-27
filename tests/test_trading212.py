import datetime as dt
import urllib.error

import pytest

from tradebot import execution
from tradebot.trading212 import DEMO, T212Error, Trading212, is_open, map_tickers, qty

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
    assert qty(0.04129999) == 0.0412 and qty(1.0) == 1.0


def test_ticker_mapping_by_isin_currency_and_venue():
    inst = {"SXR8": {"isin": "IE00B5BMR087", "currency": "EUR", "market": "XETR"},
            "AAPL": {"isin": "US0378331005", "currency": "USD", "market": "XNYS"},
            "XXX": {"isin": "NOPE", "currency": "EUR", "market": "XETR"}}
    m = map_tickers(META, inst)
    assert m["SXR8"]["ticker"] == "SXR8d_EQ" and m["SXR8"]["schedule"] == 166
    assert m["AAPL"]["ticker"] == "AAPL_US_EQ"
    assert m["XXX"]["ticker"] == ""


def test_is_open_uses_the_latest_event():
    ex = [{"workingSchedules": [{"id": 166, "timeEvents": [
        {"date": "2026-09-25T07:00:03.000Z", "type": "OPEN"}, {"date": "2026-09-25T15:30:00.000Z", "type": "CLOSE"}]}]}]
    t = lambda h, m: dt.datetime(2026, 9, 25, h, m, tzinfo=dt.UTC)
    assert is_open(ex, 166, t(10, 0)) and not is_open(ex, 166, t(16, 0)) and not is_open(ex, 166, t(6, 0))
    assert not is_open(ex, 999, t(10, 0))


class FakeBroker:
    def __init__(self, open_orders):
        self.open_orders, self.lookups = open_orders, 0

    def orders(self):
        self.lookups += 1
        return self.open_orders


@pytest.fixture(autouse=True)
def tmp_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(execution, "JOURNAL", tmp_path / "journal.jsonl")


def test_submit_once_timeout_finds_the_order_without_resending():
    sent = []

    def place():
        sent.append(1)
        raise urllib.error.URLError("timed out")

    b = FakeBroker([{"id": 7, "ticker": "SXR8d_EQ", "quantity": 0.04, "status": "NEW"}])
    o = execution.submit_once(b, "i1", place, lambda os: next(iter(os), None), log=lambda *_: None, pause=0)
    assert o["id"] == 7 and len(sent) == 1
    assert [e for e in ("SUBMITTING", "UNKNOWN", "SUBMITTED") if e in execution.JOURNAL.read_text()] == ["SUBMITTING", "UNKNOWN", "SUBMITTED"]


def test_submit_once_gives_up_after_two_empty_lookups():
    def place():
        raise TimeoutError()

    b = FakeBroker([])
    assert execution.submit_once(b, "i2", place, lambda os: None, log=lambda *_: None, pause=0) is None
    assert b.lookups == 2 and "NOT_FOUND" in execution.JOURNAL.read_text()


class LeavingOrder:
    """An order that disappears from the active list after filling (HTTP 404) and shows up in history."""

    def order(self, oid):
        raise T212Error(404, "not found")

    def order_history(self, ticker, oid):
        return {"id": oid, "status": "FILLED", "filledQuantity": 0.04, "filledValue": 29.0}


def test_wait_for_reads_history_so_a_fill_is_not_mistaken_for_a_cancel():
    o = execution.wait_for(LeavingOrder(), 9, "SXR8d_EQ", timeout=1)
    assert o["status"] == "FILLED" and execution.fill_price(o) == pytest.approx(725.0)


def test_submit_once_broker_rejection_is_final():
    def place():
        raise T212Error(400, "bad quantity")

    with pytest.raises(T212Error):
        execution.submit_once(FakeBroker([]), "i3", place, lambda os: None, log=lambda *_: None, pause=0)
    assert "BROKER_REJECTED" in execution.JOURNAL.read_text()
