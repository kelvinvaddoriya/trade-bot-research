"""Order submission with the submit-once protocol (docs/04 §4) and a JSON-lines journal.

The SQLite event journal replaces the JSONL file in P1; the protocol stays the same.
"""
import datetime as dt
import json
import time
import urllib.error

from .config import DATA_DIR
from .trading212 import T212Error

JOURNAL = DATA_DIR / "journal.jsonl"
FINAL = {"FILLED", "CANCELLED", "REJECTED"}


def journal(event: str, **data) -> None:
    JOURNAL.parent.mkdir(exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "event": event, **data},
                           default=str) + "\n")


def submit_once(broker, intent_id: str, place, match, log=print, pause: float = 10.0):
    """Send one order request, never retried blindly.

    place(): performs the single POST.  match(open_orders): finds our order if the outcome is unknown.
    Returns the order dict, or None if two lookups `pause` seconds apart both find nothing.
    """
    journal("SUBMITTING", intent_id=intent_id)
    try:
        order = place()
    except T212Error as e:
        if e.status < 500:                                   # the broker answered "no": nothing was placed
            journal("BROKER_REJECTED", intent_id=intent_id, status=e.status, body=e.body)
            raise
        order = None
    except (urllib.error.URLError, TimeoutError, OSError):
        order = None
    if order is None:
        journal("UNKNOWN", intent_id=intent_id)
        log("  outcome unknown: looking for the order instead of resending")
        for attempt in range(2):
            order = match(broker.orders())
            if order is not None:
                break
            if attempt == 0:
                time.sleep(pause)
        if order is None:
            journal("NOT_FOUND", intent_id=intent_id)
            return None
    journal("SUBMITTED", intent_id=intent_id, order_id=order.get("id"), status=order.get("status"))
    return order


def wait_for(broker, order_id: int, ticker: str, statuses=FINAL, timeout: float = 60.0) -> dict | None:
    """Poll one order until its status is in `statuses`. When it leaves the active list (HTTP 404),
    its final status comes from order history, so a fill is never mistaken for a cancel."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            o = broker.order(order_id)
        except T212Error as e:
            if e.status != 404:
                raise
            o = broker.order_history(ticker, order_id)       # history can lag a moment: keep polling
        if o is not None and o.get("status") in statuses:
            return o
        time.sleep(1.5)
    return None


def fill_price(o: dict) -> float | None:
    if o.get("filledQuantity") and o.get("filledValue"):
        return o["filledValue"] / o["filledQuantity"]
    return (o.get("fill") or {}).get("price")
