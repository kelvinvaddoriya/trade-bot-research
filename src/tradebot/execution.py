"""Order manager (docs/04 §4–5, docs/05 §4 and §6). The broker is the source of truth; the ledger mirrors it.

- submit():   the submit-once protocol. SUBMITTING is journaled before the single POST. A timeout or 5xx makes the
              order UNKNOWN: it is looked for in open orders and history, never resent blindly. After two empty
              lookups 10 s apart it may be resubmitted once; losing it twice trips the kill switch.
- sync():     mirror broker orders into the ledger (entry fills open lots, stop/exit fills close them), then
              reconcile positions and open orders. Returns the mismatches.
- ensure_stops(): every open lot has exactly one resting GTC stop at its stop price, sized to the lot.
- execute_pending(): orders decided at a close are sent after the next open, exits first.
- halt():     the kill switch's HALT: trip (persisted first), cancel entry orders, keep protective stops.
"""
import datetime as dt
import re
import time
import urllib.error

from . import risk
from .store import now
from .trading212 import T212Error, price, qty

FINAL = {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"}
ACTIVE = {"NEW", "CONFIRMED", "UNCONFIRMED", "LOCAL", "PARTIALLY_FILLED", "CANCELLING", "REPLACING"}
SIDE = {"entry": "BUY", "exit": "SELL", "stop": "SELL"}
TYPE = {"entry": "LIMIT", "exit": "MARKET", "stop": "STOP"}
LIMBO_S = 600        # an order that left the active list but isn't in history yet; longer than this is a mismatch
TOL = 1e-4           # quantities have 4 decimals


def ticker_of(x: dict) -> str:
    return x.get("ticker") or (x.get("instrument") or {}).get("ticker", "")


def side_of(o: dict) -> str:
    return (o.get("side") or ("BUY" if (o.get("quantity") or 0) > 0 else "SELL")).upper()


def fill_price(o: dict) -> float | None:
    if o.get("filledQuantity") and o.get("filledValue"):
        return abs(o["filledValue"] / o["filledQuantity"])
    return (o.get("fill") or {}).get("price")


def _ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ---------- submit-once ----------

def _place(broker, r: dict):
    if r["role"] == "entry":
        return broker.place_limit(r["ticker"], r["qty"], r["price"], "DAY")
    if r["role"] == "exit":
        return broker.place_market(r["ticker"], -r["qty"])
    return broker.place_stop(r["ticker"], -r["qty"], r["price"])


def find_order(broker, db, r: dict) -> dict | None:
    """Our order at the broker, open or finished: same ticker, side, type, quantity and price, created after
    SUBMITTING (30 s allowance for clock skew), and not already claimed by another ledger row."""
    claimed = {x["broker_id"] for x in db.select("orders", "broker_id IS NOT NULL")}
    since = _ts(r["created"]) - dt.timedelta(seconds=30)
    for o in broker.orders() + broker.history(r["ticker"]):
        created = o.get("createdAt") or o.get("creationTime")
        px = o.get("limitPrice") or o.get("stopPrice")
        if (ticker_of(o) == r["ticker"] and side_of(o) == SIDE[r["role"]] and o.get("type") == TYPE[r["role"]]
                and abs(abs(o.get("quantity") or 0) - r["qty"]) < TOL
                and (r["price"] is None or (px is not None and abs(px - r["price"]) < 0.005))
                and (created is None or _ts(created) >= since) and o["id"] not in claimed):
            return o
    return None


def _lookup(broker, db, r: dict, pause: float) -> dict | None:
    """Two lookups at least `pause` seconds apart (docs/04 §4)."""
    o = find_order(broker, db, r)
    if o is None:
        time.sleep(pause)
        o = find_order(broker, db, r)
    return o


def _adopt(db, r: dict, o: dict) -> str:
    status = o.get("status") or "NEW"
    db.update("orders", r["key"], status=status, broker_id=o["id"])
    db.event("SUBMITTED", r["key"], broker_id=o["id"], status=status)
    return status


def _lost(broker, db, r: dict, alert) -> str:
    """Nothing found: resubmit once (at the next sync), never twice."""
    if r["attempts"] < 2:
        db.update("orders", r["key"], status="PENDING")
        db.event("NOT_FOUND", r["key"], resubmit=True)
        alert(f"order {r['role']} {r['symbol']}: outcome unknown and not found at the broker; one resubmit allowed")
        return "PENDING"
    db.update("orders", r["key"], status="NOT_FOUND", done=1)
    db.event("NOT_FOUND", r["key"], resubmit=False)
    halt(broker, db, f"order {r['key']} ({r['role']} {r['symbol']}) lost twice", alert)
    return "NOT_FOUND"


def _precision_fix(r: dict, e: T212Error) -> float | None:
    """Trading 212's 400 "quantity-precision-mismatch" names the number of decimals it accepts for that instrument
    (2026-10-01: "invalid quantity precision 3"). Returns the quantity rounded down to it, or None."""
    m = re.search(r"quantity precision (\d+)", e.body) if e.status == 400 and "quantity-precision" in e.body else None
    fixed = qty(r["qty"], int(m.group(1))) if m else None
    return fixed if fixed and fixed < r["qty"] else None


def submit(broker, db, r: dict, alert, pause: float = 10.0) -> str:
    """Send one ledger order with the submit-once protocol. Returns its new status."""
    key = r["key"]
    if r["attempts"]:                                     # an earlier attempt was lost: look once more first
        o = find_order(broker, db, r)
        if o is not None:
            return _adopt(db, r, o)
    db.update("orders", key, status="SUBMITTING", attempts=r["attempts"] + 1, created=now())
    r = db.order(key)
    db.event("SUBMITTING", key, ticker=r["ticker"], role=r["role"], qty=r["qty"], type=r["type"], price=r["price"])
    try:
        o = _place(broker, r)
    except T212Error as e:
        fixed = _precision_fix(r, e)
        if fixed is not None:                              # nothing was placed; T212 named the precision it accepts
            db.update("orders", key, qty=fixed, status="PENDING", attempts=r["attempts"] - 1)
            db.event("QTY_PRECISION", key, sent=r["qty"], resent=fixed, detail=e.body[:200])
            return submit(broker, db, db.order(key), alert, pause)
        if e.status < 500:                                 # the broker said no: nothing was placed
            db.update("orders", key, status="BROKER_REJECTED", done=1)
            db.event("BROKER_REJECTED", key, status=e.status, body=e.body)
            alert(f"order rejected: {r['role']} {r['symbol']} (HTTP {e.status}: {e.body[:150]})")
            last = db.con.execute("SELECT status FROM orders WHERE attempts > 0 ORDER BY created DESC LIMIT 3").fetchall()
            if len(last) == 3 and all(x[0] == "BROKER_REJECTED" for x in last):
                halt(broker, db, "3 broker rejections in a row", alert)
            return "BROKER_REJECTED"
        o = None
    except (urllib.error.URLError, TimeoutError, OSError):
        o = None
    if o is None:                                          # never resend blindly: look for it instead
        db.update("orders", key, status="UNKNOWN")
        db.event("UNKNOWN", key)
        o = _lookup(broker, db, r, pause)
        if o is None:
            return _lost(broker, db, r, alert)
    return _adopt(db, r, o)


# ---------- ledger <- broker ----------

def apply(db, r: dict, o: dict, alert) -> None:
    """Mirror one broker order into the ledger. New fills open or grow a lot (entries) or shrink/close it (sells)."""
    status, filled, px = o.get("status") or "UNKNOWN", abs(o.get("filledQuantity") or 0), fill_price(o)
    delta = filled - (r["filled_qty"] or 0)
    db.update("orders", r["key"], status=status, filled_qty=filled, fill_price=px, done=int(status in FINAL),
              missing_since=None)
    if status != r["status"] or delta > 1e-9:
        db.event("ORDER", r["key"], broker_id=r["broker_id"], status=status, filled=filled, price=px)
    if status not in FINAL | ACTIVE:
        alert(f"unrecognised broker order status {status} for {r['symbol']} (order {r['broker_id']})")
    if delta <= 1e-9:
        return
    day = _utcnow().date().isoformat()
    if r["role"] == "entry":
        fields = dict(qty=filled, entry_price=px, stop_price=px - r["stop_distance"])
        if db.lot(r["key"]) is None:
            db.insert("lots", id=r["key"], strategy=r["strategy"], symbol=r["symbol"], ticker=r["ticker"],
                      entry_date=day, status="OPEN", pnl=0.0, **fields)
        else:
            db.update("lots", r["key"], **fields)
        db.event("FILL", r["key"], symbol=r["symbol"], side="buy", qty=filled, price=px)
        return
    lot = db.lot(r["lot"])
    left, pnl = lot["qty"] - delta, (lot["pnl"] or 0) + delta * (px - lot["entry_price"])
    db.event("FILL", r["key"], symbol=r["symbol"], side="sell", qty=delta, price=px, lot=lot["id"])
    if left > TOL:
        db.update("lots", lot["id"], qty=left, pnl=pnl)
        return
    reason = "protective stop" if r["role"] == "stop" else r["reason"]
    db.update("lots", lot["id"], qty=0.0, pnl=pnl, status="CLOSED", exit_price=px, exit_date=day, exit_reason=reason)
    db.event("LOT_CLOSED", lot["id"], symbol=lot["symbol"], reason=reason, pnl=round(pnl, 2))
    alert(f"{lot['symbol']} closed ({reason}) at {px:.2f}: P&L €{pnl:+.2f}")


def sync(broker, db, alert, pause: float = 10.0) -> list[str]:
    """Bring the ledger up to date with the broker, then reconcile (docs/05 §6). Returns mismatches; empty = OK."""
    for r in db.select("orders", "status IN ('SUBMITTING', 'UNKNOWN')"):      # left behind by a crash mid-submit
        o = _lookup(broker, db, r, pause)
        _adopt(db, r, o) if o is not None else _lost(broker, db, r, alert)
    open_orders = broker.orders()
    by_id = {o["id"]: o for o in open_orders}
    problems, limbo = [], set()
    for r in db.select("orders", "broker_id IS NOT NULL AND done=0"):
        o = by_id.get(r["broker_id"]) or broker.order_history(r["ticker"], r["broker_id"])
        if o is None:                                       # left the active list; history can lag a moment
            since = r["missing_since"] or now()
            db.update("orders", r["key"], missing_since=since)
            if (_utcnow() - _ts(since)).total_seconds() > LIMBO_S:
                problems.append(f"order {r['broker_id']} ({r['symbol']}) is neither open nor in history")
            limbo.add(r["ticker"])
            continue
        apply(db, db.order(r["key"]), o, alert)
    known = {r["broker_id"] for r in db.select("orders", "broker_id IS NOT NULL")}
    problems += [f"unknown order at the broker: {o['id']} {ticker_of(o)} {side_of(o)} {o.get('quantity')}"
                 for o in open_orders if o["id"] not in known]
    held, booked = {}, {}
    for p in broker.positions():
        held[ticker_of(p)] = held.get(ticker_of(p), 0) + (p.get("quantity") or 0)
    for lot in db.select("lots", "status='OPEN'"):
        booked[lot["ticker"]] = booked.get(lot["ticker"], 0) + lot["qty"]
    problems += [f"position mismatch {tk}: broker {held.get(tk, 0)}, ledger {booked.get(tk, 0):.4f}"
                 for tk in sorted(set(held) | set(booked))
                 if tk not in limbo and abs(held.get(tk, 0) - booked.get(tk, 0)) > TOL]
    db.event("RECONCILE", ok=not problems, problems=problems, positions=held)
    return problems


# ---------- actions ----------

def wait_final(broker, ticker: str, order_id: int, timeout: float = 60.0, poll: float = 1.5) -> dict | None:
    """Poll one order until it is final. When it leaves the active list (HTTP 404) its final status comes from
    order history, so a fill is never mistaken for a cancel."""
    end = time.time() + timeout
    while True:
        try:
            o = broker.order(order_id)
        except T212Error as e:
            if e.status != 404:
                raise
            o = broker.order_history(ticker, order_id)
        if o is not None and o.get("status") in FINAL:
            return o
        if time.time() >= end:
            return None
        time.sleep(poll)


def cancel(broker, db, r: dict, alert, timeout: float = 60.0) -> str:
    """Cancel one of our orders and record its final state (it may have filled first)."""
    db.update("orders", r["key"], reason=f"{r['reason']} [cancelled by engine]")
    try:
        broker.cancel(r["broker_id"])
    except T212Error as e:
        if e.status not in (400, 404):                     # already gone: the final state tells what happened
            raise
    o = wait_final(broker, r["ticker"], r["broker_id"], timeout)
    if o is None:
        raise RuntimeError(f"cancel of order {r['broker_id']} ({r['symbol']}) not confirmed")
    apply(db, db.order(r["key"]), o, alert)
    return o["status"]


def plan_order(db, **row) -> dict:
    """A new ledger order, PENDING until it is submitted."""
    db.insert("orders", status="PENDING", created=now(), updated=now(), **row)
    db.event("ORDER_PLANNED", row["key"], **{k: v for k, v in row.items() if k != "key"})
    return db.order(row["key"])


def ensure_stops(broker, db, alert, market_open) -> None:
    """Every open lot has exactly one resting stop at the lot's stop price, sized to the lot (docs/05 §6).
    Acts only while the lot's market is open: nothing can trigger overnight, and a trail decided at the close
    is applied at the next open."""
    for lot in db.select("lots", "status='OPEN'"):
        if not market_open(lot["ticker"]) or db.select("orders", "lot=? AND role='exit' AND done=0 AND status!='PENDING'", lot["id"]):
            continue                                        # closed market, or an exit is under way
        want_q, want_p = qty(lot["qty"]), price(lot["stop_price"])
        stops = db.select("orders", "lot=? AND role='stop' AND done=0", lot["id"])
        ok = [s for s in stops if abs(s["qty"] - want_q) < TOL and abs(s["price"] - want_p) < 0.005]
        if len(stops) == 1 and ok:
            if ok[0]["status"] == "PENDING":                # lost once: resubmit
                submit(broker, db, ok[0], alert)
            continue
        for s in stops:
            if s["broker_id"]:
                cancel(broker, db, s, alert)
            else:
                db.update("orders", s["key"], status="SKIPPED", done=1)
        lot = db.lot(lot["id"])
        if lot["status"] != "OPEN":                          # the old stop filled while being replaced
            continue
        before = db.select("orders", "lot=? AND role='stop'", lot["id"])
        if any(s["status"] == "CANCELLED" and "[cancelled by engine]" not in s["reason"] for s in before):
            alert(f"protective stop for {lot['symbol']} disappeared at the broker: replacing it")
        r = plan_order(db, key=f"{lot['id']}-stop{len(before) + 1}", role="stop", strategy=lot["strategy"],
                       symbol=lot["symbol"], ticker=lot["ticker"], lot=lot["id"], qty=want_q, type="stop",
                       price=want_p, reason="protective stop")
        if submit(broker, db, r, alert) in ("BROKER_REJECTED", "NOT_FOUND"):
            halt(broker, db, f"could not place the protective stop for {lot['symbol']}", alert)


def execute_pending(broker, db, alert, open_sessions: dict[str, str]) -> None:
    """Send the orders decided at the last close, now that their market is open (docs/04 §3). Exits go first;
    each exit cancels the lot's stop before selling. open_sessions: ticker -> date of its current session."""
    for r in db.select("orders", "status='PENDING' AND role IN ('exit', 'entry') ORDER BY role='entry', key"):
        sess = open_sessions.get(r["ticker"])
        if sess is None or r["session"] > sess:
            continue
        if r["session"] < sess:
            db.update("orders", r["key"], status="SKIPPED", done=1)
            db.event("SKIPPED", r["key"], why=f"missed its session {r['session']}")
            alert(f"{r['role']} {r['symbol']} missed its session {r['session']}: skipped")
            continue
        flatten = r["role"] == "exit" and r["reason"].startswith("flatten")
        if risk.is_tripped() and not flatten:              # checked again just before every submit
            continue
        if r["role"] == "exit":
            lot = db.lot(r["lot"])
            for s in db.select("orders", "lot=? AND role='stop' AND done=0 AND broker_id IS NOT NULL", r["lot"]):
                cancel(broker, db, s, alert)
            lot = db.lot(r["lot"])
            if lot["status"] != "OPEN":
                db.update("orders", r["key"], status="SKIPPED", done=1)
                db.event("SKIPPED", r["key"], why="lot already closed")
                continue
            db.update("orders", r["key"], qty=qty(lot["qty"]))
        submit(broker, db, db.order(r["key"]), alert)


def cancel_entries(broker, db) -> None:
    """Skip planned entries and cancel entry orders at the broker. Long-only, so every buy order is an entry."""
    for r in db.select("orders", "role='entry' AND status='PENDING'"):
        db.update("orders", r["key"], status="SKIPPED", done=1)
        db.event("SKIPPED", r["key"], why="kill switch")
    for o in broker.orders():
        if side_of(o) == "BUY":
            try:
                broker.cancel(o["id"])
            except T212Error:
                pass                                        # already filled or gone; sync records what happened
            db.event("CANCEL_ENTRY", str(o["id"]), ticker=ticker_of(o))


def halt(broker, db, reason: str, alert, by: str = "engine") -> None:
    """HALT (docs/05 §4): persist the kill switch before anything else, cancel entries, keep protective stops."""
    if not risk.is_tripped():
        risk.trip(reason, by)
        db.event("KILL", by=by, reason=reason)
        alert(f"KILL SWITCH tripped by {by}: {reason}")
    cancel_entries(broker, db)
