"""Order manager against a stateful fake Trading 212: submit-once, fills → lots, stops, reconciliation, HALT.
Drills 1, 3, 5 and 8 (docs/05 §11) are covered here."""
import datetime as dt

import pytest

from tradebot import execution, risk
from tradebot.store import Store
from tradebot.trading212 import T212Error, price, qty

TK = "SXR8d_EQ"


class FakeT212:
    """Open orders, finished orders (history) and positions, like the practice account. `fail` injects one fault
    into the next order request: 'lost' (timeout, nothing placed), 'timeout' (placed, then the connection drops)
    or an HTTP status (rejected)."""

    def __init__(self):
        self.open, self.hist, self.pos, self.next_id, self.fail, self.sent = {}, [], {}, 100, None, 0
        self.skew = 0.0

    def _new(self, ticker, q, type_, **px):
        self.sent += 1
        fail, self.fail = self.fail, None
        if fail == "lost":
            raise TimeoutError()
        if isinstance(fail, int):
            raise T212Error(fail, "rejected")
        if isinstance(fail, tuple):                       # (status, body): a specific broker answer
            raise T212Error(*fail)
        self.next_id += 1
        o = {"id": self.next_id, "ticker": ticker, "quantity": abs(q), "side": "BUY" if q > 0 else "SELL", "type": type_,
             "status": "NEW", "filledQuantity": 0, "createdAt": dt.datetime.now(dt.UTC).isoformat(), **px}
        self.open[o["id"]] = o
        if fail == "timeout":
            raise TimeoutError()
        return dict(o)

    def place_limit(self, t, q, limit, validity="DAY"):
        return self._new(t, qty(q), "LIMIT", limitPrice=price(limit))

    def place_market(self, t, q):
        return self._new(t, qty(q), "MARKET")

    def place_stop(self, t, q, stop, validity="GOOD_TILL_CANCEL"):
        return self._new(t, qty(q), "STOP", stopPrice=price(stop))

    def orders(self):
        return [dict(o) for o in self.open.values()]

    def order(self, oid):
        if oid in self.open:
            return dict(self.open[oid])
        raise T212Error(404, "not found")

    def history(self, ticker):
        return [dict(o) for o in reversed(self.hist) if o["ticker"] == ticker]

    def order_history(self, ticker, oid):
        return next((o for o in self.history(ticker) if o["id"] == oid), None)

    def cancel(self, oid):
        if oid not in self.open:
            raise T212Error(404, "not found")
        o = self.open.pop(oid)
        o["status"] = "CANCELLED"
        self.hist.append(o)

    def positions(self):
        return [{"ticker": t, "quantity": q, "currentPrice": 700.0} for t, q in self.pos.items() if abs(q) > 1e-9]

    # test helpers
    def fill(self, oid, px):
        o = self.open.pop(oid)
        o.update(status="FILLED", filledQuantity=o["quantity"], fill={"price": px})
        self.hist.append(o)
        self.pos[o["ticker"]] = self.pos.get(o["ticker"], 0) + (o["quantity"] if o["side"] == "BUY" else -o["quantity"])

    def only(self, type_):
        [o] = [o for o in self.open.values() if o["type"] == type_]
        return o


@pytest.fixture
def db(tmp_path):
    return Store(tmp_path / "demo.db")


@pytest.fixture
def alerts():
    return []


def entry(db, key="e1", q=0.35, limit=710.0, session="2026-10-01"):
    return execution.plan_order(db, key=key, intent_id=key, role="entry", strategy="s1_trend", symbol="SXR8", ticker=TK,
                                session=session, qty=q, type="limit", price=limit, stop_distance=30.0, reason="trend")


def filled_lot(b, db, alerts, px=700.0):
    """An entry sent, filled at `px` and synced: an open lot with its protective stop resting at the broker."""
    execution.submit(b, db, entry(db), alerts.append, pause=0)
    b.fill(b.only("LIMIT")["id"], px)
    assert execution.sync(b, db, alerts.append, pause=0) == []
    execution.ensure_stops(b, db, alerts.append, lambda tk: True)
    return db.lot("e1")


# ---------- submit-once (drill 3: network cut during a submit) ----------

def test_timeout_after_placing_finds_the_order_and_never_resends(db, alerts):
    b = FakeT212()
    b.fail = "timeout"
    assert execution.submit(b, db, entry(db), alerts.append, pause=0) == "NEW"
    assert b.sent == 1 and len(b.open) == 1 and db.order("e1")["broker_id"] == 101
    assert [e["type"] for e in db.events()][-3:] == ["SUBMITTING", "UNKNOWN", "SUBMITTED"]


def test_lost_order_is_resubmitted_once_then_the_kill_switch_trips(db, alerts):
    b = FakeT212()
    b.fail = "lost"
    assert execution.submit(b, db, entry(db), alerts.append, pause=0) == "PENDING"
    assert db.order("e1")["attempts"] == 1 and not risk.is_tripped()
    b.fail = "lost"
    assert execution.submit(b, db, db.order("e1"), alerts.append, pause=0) == "NOT_FOUND"
    assert b.sent == 2 and risk.is_tripped()


def test_crash_mid_submit_is_resolved_by_the_next_sync(db, alerts):
    b = FakeT212()
    r = entry(db)
    db.update("orders", "e1", status="SUBMITTING", attempts=1, created=r["created"])
    b.place_limit(TK, 0.35, 710.0)                          # the POST did reach the broker before the crash
    assert execution.sync(b, db, alerts.append, pause=0) == []
    assert db.order("e1")["broker_id"] == 101 and b.sent == 1


def test_broker_rejection_is_final_and_three_in_a_row_trip(db, alerts):
    b = FakeT212()
    for i in range(3):
        b.fail = 400
        assert execution.submit(b, db, entry(db, key=f"e{i}"), alerts.append, pause=0) == "BROKER_REJECTED"
        assert risk.is_tripped() == (i == 2)
    assert db.order("e0")["done"] == 1


# ---------- fills, stops, exits ----------

def test_entry_fill_opens_a_lot_and_a_protective_stop_follows(db, alerts):
    b = FakeT212()
    lot = filled_lot(b, db, alerts)
    assert lot["status"] == "OPEN" and lot["qty"] == 0.35 and lot["entry_price"] == 700.0 and lot["stop_price"] == 670.0
    stop = b.only("STOP")
    assert stop["side"] == "SELL" and stop["quantity"] == 0.35 and stop["stopPrice"] == 670.0
    execution.ensure_stops(b, db, alerts.append, lambda tk: True)          # already right: nothing changes
    assert len(b.open) == 1 and b.sent == 2


def test_stops_wait_for_the_market_to_open(db, alerts):
    b = FakeT212()
    execution.submit(b, db, entry(db), alerts.append, pause=0)
    b.fill(b.only("LIMIT")["id"], 700.0)
    execution.sync(b, db, alerts.append, pause=0)
    execution.ensure_stops(b, db, alerts.append, lambda tk: False)
    assert not b.open


def test_stop_fill_at_the_broker_closes_the_lot(db, alerts):
    b = FakeT212()
    filled_lot(b, db, alerts)
    b.fill(b.only("STOP")["id"], 669.0)
    assert execution.sync(b, db, alerts.append, pause=0) == []
    lot = db.lot("e1")
    assert lot["status"] == "CLOSED" and lot["exit_reason"] == "protective stop" and lot["pnl"] == pytest.approx(-0.35 * 31)
    execution.ensure_stops(b, db, alerts.append, lambda tk: True)
    assert not b.open                                                       # no stop for a closed lot


def test_deleted_stop_is_replaced_with_an_alert(db, alerts):                  # drill 8
    b = FakeT212()
    filled_lot(b, db, alerts)
    b.cancel(b.only("STOP")["id"])                                          # someone deletes it in the app
    assert execution.sync(b, db, alerts.append, pause=0) == []
    execution.ensure_stops(b, db, alerts.append, lambda tk: True)
    assert b.only("STOP")["stopPrice"] == 670.0 and any("disappeared" in a for a in alerts)


def test_trail_replaces_the_stop_at_the_higher_price(db, alerts):
    b = FakeT212()
    filled_lot(b, db, alerts)
    db.update("lots", "e1", stop_price=685.0)
    execution.ensure_stops(b, db, alerts.append, lambda tk: True)
    assert b.only("STOP")["stopPrice"] == 685.0 and not any("disappeared" in a for a in alerts)


def test_exit_cancels_the_stop_then_sells(db, alerts):
    b = FakeT212()
    filled_lot(b, db, alerts)
    execution.plan_order(db, key="x1", intent_id="x1", role="exit", strategy="s1_trend", symbol="SXR8", ticker=TK, lot="e1",
                         session="2026-11-02", qty=0.35, type="market", reason="trend lost")
    execution.execute_pending(b, db, alerts.append, {TK: "2026-11-02"})
    sell = b.only("MARKET")
    assert sell["side"] == "SELL" and sell["quantity"] == 0.35 and len(b.open) == 1     # the stop is gone
    b.fill(sell["id"], 720.0)
    assert execution.sync(b, db, alerts.append, pause=0) == []
    lot = db.lot("e1")
    assert lot["status"] == "CLOSED" and lot["exit_reason"] == "trend lost" and lot["pnl"] == pytest.approx(0.35 * 20)


def test_pending_orders_only_go_out_in_their_session(db, alerts):
    b = FakeT212()
    entry(db, session="2026-10-01")
    execution.execute_pending(b, db, alerts.append, {TK: "2026-09-30"})     # too early: stays pending
    assert not b.open and db.order("e1")["status"] == "PENDING"
    execution.execute_pending(b, db, alerts.append, {TK: "2026-10-02"})     # engine was down on the 1st: skipped
    assert not b.open and db.order("e1")["status"] == "SKIPPED"


# ---------- reconciliation (drill 5) ----------

def test_manual_order_or_position_is_a_mismatch(db, alerts):
    b = FakeT212()
    b.place_limit("SAPd_EQ", 1, 150.0)                                       # a manual order in the bot's account
    b.pos["SIEd_EQ"] = 2.0                                                  # and a manual position
    problems = execution.sync(b, db, alerts.append, pause=0)
    assert len(problems) == 2 and "unknown order" in problems[0] and "position mismatch SIEd_EQ" in problems[1]


def test_history_lag_after_a_fill_is_not_a_mismatch(db, alerts):
    b = FakeT212()
    execution.submit(b, db, entry(db), alerts.append, pause=0)
    o = b.open.pop(101)                                                     # filled, left the active list, history lags
    b.pos[TK] = 0.35
    assert execution.sync(b, db, alerts.append, pause=0) == []
    assert db.order("e1")["missing_since"]
    o.update(status="FILLED", filledQuantity=0.35, fill={"price": 700.0})
    b.hist.append(o)
    assert execution.sync(b, db, alerts.append, pause=0) == [] and db.lot("e1")["qty"] == 0.35


# ---------- HALT (drill 1) ----------

def test_halt_cancels_entries_keeps_stops_and_blocks_new_entries(db, alerts):
    b = FakeT212()
    filled_lot(b, db, alerts)
    execution.submit(b, db, entry(db, key="e2", limit=705.0), alerts.append, pause=0)   # an open entry order
    entry(db, key="e3", session="2026-10-02")                                          # and a planned one
    execution.halt(b, db, "drill 1", alerts.append, by="operator")
    assert risk.is_tripped() and [o["type"] for o in b.open.values()] == ["STOP"]
    assert db.order("e3")["status"] == "SKIPPED"
    entry(db, key="e4", session="2026-10-02")
    execution.execute_pending(b, db, alerts.append, {TK: "2026-10-02"})
    assert db.order("e4")["status"] == "PENDING" and [o["type"] for o in b.open.values()] == ["STOP"]
    assert execution.sync(b, db, alerts.append, pause=0) == [] and db.order("e2")["status"] == "CANCELLED"


def test_quantity_precision_rejection_is_fixed_and_resent_without_counting_as_a_reject(db, alerts):
    """2026-10-01: Trading 212 refused 2.4648 DTE with "invalid quantity precision 3"; three of those tripped the kill switch."""
    b = FakeT212()
    body = '{"type":"/api-errors/quantity-precision-mismatch","status":400,"detail":"invalid quantity precision 3"}'
    for i in range(3):
        b.fail = (400, body)
        assert execution.submit(b, db, entry(db, key=f"e{i}", q=2.4648, limit=26.37), alerts.append, pause=0) == "NEW"
    assert [o["quantity"] for o in b.open.values()] == [2.464] * 3 and not risk.is_tripped() and not alerts
    assert db.order("e0")["qty"] == 2.464 and db.order("e0")["attempts"] == 1
    assert [e["type"] for e in db.events("entity='e0'")][-3:] == ["QTY_PRECISION", "SUBMITTING", "SUBMITTED"]
