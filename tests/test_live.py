"""The engine end to end on a fake Trading 212 and synthetic bars. Drills 2 (watchdog) and 4 (stale data)."""
import datetime as dt
import time

import numpy as np
import pandas as pd
import pytest

from tradebot import data, live, risk, watchdog
from tradebot.config import load_risk
from tradebot.store import Store
from test_execution import FakeT212

T = lambda d, h, m=0: dt.datetime(2026, d[0], d[1], h, m, tzinfo=dt.UTC)
DAYS = [(9, 29), (9, 30), (10, 1), (10, 2)]
TICKERS = {"SXR8": {"ticker": "SXR8d_EQ", "schedule": 166}, "EXW1": {"ticker": "EXW1d_EQ", "schedule": 166}}
INST = {"SXR8": {"strategy": "s1_trend", "currency": "EUR"}, "EXW1": {"strategy": "s1_trend", "currency": "EUR"}}
SETTINGS = {"hash": "s", "live": {"start": "2026-09-28", "strategies": ["s1_trend"], "shadow": []},
            "budgets_eur": {"s1_trend": 600}, "periods": {"data_start": "2006-01-01"}, "costs": {}}


def bars(last: str, drift: float) -> pd.DataFrame:
    idx = pd.bdate_range(end=last, periods=260)
    close = 100 * np.exp(drift * np.arange(260) + 0.004 * np.sin(np.arange(260)))
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e5}, index=idx)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "HEARTBEAT", tmp_path / "heartbeat.json")
    b = FakeT212()
    b.exchanges = lambda: [{"workingSchedules": [{"id": 166, "timeEvents": [
        e for d in DAYS for e in ({"date": T(d, 7).isoformat(), "type": "OPEN"}, {"date": T(d, 15, 30).isoformat(), "type": "CLOSE"})]}]}]
    panel = {"SXR8": bars("2026-09-30", 0.002), "EXW1": bars("2026-09-30", -0.002)}      # one in trend, one not
    monkeypatch.setattr(data, "refresh", lambda *a, **k: None)
    monkeypatch.setattr(data, "load_panel", lambda inst, name: panel)
    eng = live.Engine(b, Store(tmp_path / "demo.db"), {}, SETTINGS, INST, load_risk(), TICKERS)
    eng.alerts = []
    monkeypatch.setattr(eng, "alert", eng.alerts.append)
    return eng, b, panel


def test_full_loop_close_to_stop_out(engine):
    eng, b, panel = engine
    eng.sync(T((9, 30), 15, 55))                              # month-end close: S1's check day
    [cyc] = eng.db.events("type='CYCLE'")
    assert cyc["payload"]["session"] == "2026-09-30" and cyc["payload"]["planned"] == ["entry SXR8"]
    [o] = eng.db.select("orders")
    close = panel["SXR8"]["close"].iloc[-1]
    assert o["session"] == "2026-10-01" and o["price"] == pytest.approx(close * 1.01, abs=0.006)
    assert o["qty"] * o["price"] == pytest.approx(250, abs=0.1)          # €600 × weight 1, capped at €250
    assert not b.open                                                     # nothing goes out overnight

    eng.sync(T((9, 30), 16, 5))                                           # the cycle runs once per session
    assert len(eng.db.events("type='CYCLE'")) == 1
    eng.sync(T((10, 1), 7, 1))                                            # opening auction still running
    assert not b.open
    eng.sync(T((10, 1), 7, 3))
    buy = b.only("LIMIT")
    assert buy["side"] == "BUY" and buy["limitPrice"] == o["price"]

    b.fill(buy["id"], close * 1.002)
    eng.sync(T((10, 1), 7, 5))                                            # fill → lot → protective stop
    lot = eng.db.select("lots")[0]
    stop = b.only("STOP")
    assert stop["quantity"] == lot["qty"] == buy["quantity"] and stop["stopPrice"] == pytest.approx(lot["stop_price"], abs=0.006)
    assert lot["stop_price"] == pytest.approx(close * 1.002 - o["stop_distance"])

    b.fill(stop["id"], stop["stopPrice"])
    eng.sync(T((10, 1), 12))
    assert eng.db.lot(lot["id"])["status"] == "CLOSED" and not b.open and not risk.is_tripped()
    assert eng.db.events("type='RECONCILE'")[-1]["payload"]["ok"]


def test_not_a_check_day_means_no_data_and_no_orders(engine):
    eng, b, _ = engine
    eng.sync(T((9, 29), 15, 55))
    [cyc] = eng.db.events("type='CYCLE'")
    assert cyc["payload"] == {"session": "2026-09-29", "result": "not a check day"} and not eng.db.select("orders")


def test_stale_data_waits_then_skips_the_cycle_with_an_alert(engine):          # drill 4
    eng, b, panel = engine
    panel["SXR8"] = panel["SXR8"].iloc[:-1]                               # Yahoo hasn't published the close yet
    eng.sync(T((9, 30), 15, 55))
    assert eng.db.events("type='STALE_DATA'") and not eng.db.events("type='CYCLE'") and not eng.alerts
    eng.sync(T((10, 1), 6, 50))                                           # 10 minutes before the next open
    [cyc] = eng.db.events("type='CYCLE'")
    assert cyc["payload"]["result"] == "skipped: stale data" and "SXR8: last bar 2026-09-29" in eng.alerts[0]
    assert not eng.db.select("orders")


def test_reconciliation_mismatch_twice_trips_the_kill_switch(engine):         # drill 5
    eng, b, _ = engine
    b.place_limit("SAPd_EQ", 1, 150.0)                                     # manual order in the bot's account
    eng.sync(T((9, 30), 10))
    assert not risk.is_tripped()                                          # once could be a fill in flight
    eng.sync(T((9, 30), 10, 2))
    assert risk.is_tripped() and "reconciliation mismatch" in risk.state()["reason"]
    assert not b.open                                                     # the (buy) order was cancelled


def test_drawdown_trips_the_kill_switch(engine):
    eng, b, _ = engine
    eng.db.insert("lots", id="L", strategy="s1_trend", symbol="SXR8", ticker="SXR8d_EQ", qty=1.0, entry_price=500.0,
                  entry_date="2026-09-01", stop_price=300.0, status="OPEN", pnl=0.0)
    m = live.mark(eng.db, 1000, {"SXR8": 395.0})
    assert m["equity"] == 895.0 and eng.drawdown_hit(m) and risk.is_tripped()


def test_watchdog_trips_on_a_dead_engine_only(engine):                         # drill 2
    eng, b, _ = engine
    b.place_limit("SXR8d_EQ", 0.3, 700.0)
    b.place_stop("SXR8d_EQ", -0.3, 650.0)
    assert watchdog.check(b, eng.db, eng.alerts.append).startswith("engine not running")
    watchdog.beat("running")
    assert watchdog.check(b, eng.db, eng.alerts.append).startswith("ok")
    watchdog.beat("stopped")
    assert watchdog.check(b, eng.db, eng.alerts.append).startswith("engine not running")
    watchdog.HEARTBEAT.write_text(f'{{"ts": {time.time() - 90}, "pid": 1, "state": "running"}}')   # killed 90 s ago
    assert watchdog.check(b, eng.db, eng.alerts.append).startswith("stale")
    assert risk.state()["by"] == "watchdog" and [o["type"] for o in b.open.values()] == ["STOP"]


def test_engine_refuses_new_entries_while_tripped(engine):
    eng, b, _ = engine
    risk.trip("drill", by="operator")
    eng.sync(T((9, 30), 15, 55))
    assert not eng.db.events("type='CYCLE'") and not eng.db.select("orders")


def test_the_watchdog_starts_without_pandas():
    """It runs every minute; on a laptop short of memory, loading pandas made one run take over 5 minutes."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", "import sys, tradebot.watchdog; print('pandas' in sys.modules)"],
                         capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"
