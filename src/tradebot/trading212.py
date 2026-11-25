"""Trading 212 REST adapter (docs/01 §4.1). Demo only: live needs the P3 arming (docs/04 §8).

Decimal rounding happens here, at the broker boundary. Rate limits are read from the response headers
(x-ratelimit-remaining/-reset) and honoured per endpoint. The exchange schedules double as the trading
calendar: they list each session (holidays and half days included) about three weeks back and ahead.
"""
import base64
import datetime as dt
import email.utils
import json
import re
import time
import tomllib
import urllib.error
import urllib.request
from decimal import ROUND_DOWN, Decimal

from .config import CONFIG_DIR

DEMO = "https://demo.trading212.com/api/v0"
TICKERS = CONFIG_DIR / "t212_tickers.toml"


class T212Error(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Trading 212 HTTP {status}: {body}")
        self.status, self.body = status, body


ENTRY_DECIMALS = 3      # Trading 212 rejected 4-decimal buys of cheaper instruments ("invalid quantity precision 3")


def qty(q: float, places: int = 4) -> float:
    """Round a quantity down (never buy or sell more than intended). Stops and exits use the broker's own fill
    quantity at 4 decimals; new entries are sized at ENTRY_DECIMALS."""
    return float(Decimal(repr(q)).quantize(Decimal(1).scaleb(-places), ROUND_DOWN))


def price(p: float) -> float:
    return float(Decimal(repr(p)).quantize(Decimal("0.01")))


class Trading212:
    def __init__(self, key: str, secret: str, base: str = DEMO):
        if base != DEMO:
            raise ValueError("only the Trading 212 demo is allowed until live arming exists (docs/04 §8)")
        self.base = base
        self.auth = "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()
        self.wait_until: dict[str, float] = {}
        self.skew: float | None = None                      # local clock minus broker clock, seconds (None: unmeasured)

    def _call(self, method: str, path: str, body: dict | None = None):
        ep = f"{method} {re.sub(r'/\d+', '/{id}', path.split('?')[0])}"
        delay = self.wait_until.get(ep, 0) - time.time()
        if delay > 0:
            time.sleep(delay)
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json"})
        for attempt in range(4):
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    self._note(ep, r.headers)
                    t1 = time.time()
                    # The Date header has whole seconds: compare its middle with the middle of the round trip. Only a
                    # fast round trip says where that second was; a slow one (a swapping laptop) faked -7 s once.
                    if r.headers.get("Date") and t1 - t0 < 1.0:
                        server = email.utils.parsedate_to_datetime(r.headers["Date"]).timestamp() + 0.5
                        self.skew = (t0 + t1) / 2 - server
                    raw = r.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                self._note(ep, e.headers)
                text = e.read().decode(errors="replace")[:300]
                if e.code == 429 and attempt < 3:
                    # Rejected for rate, so nothing was executed: safe to retry, even a POST. The engine, watchdog
                    # and CLI share one key, and a rejected request seems to count too, so wait with a margin.
                    wait = max(float(e.headers.get("retry-after") or 0), self.wait_until.get(ep, 0) - time.time())
                    time.sleep(max(1.0, wait) + 1.0)
                    continue
                raise T212Error(e.code, text) from None
        # timeouts / connection errors propagate: for POSTs the caller treats the outcome as UNKNOWN

    def _note(self, ep: str, headers) -> None:
        if headers and headers.get("x-ratelimit-remaining") == "0" and headers.get("x-ratelimit-reset"):
            self.wait_until[ep] = float(headers["x-ratelimit-reset"]) + 0.2

    # ---- read ----
    def summary(self):
        return self._call("GET", "/equity/account/summary")

    def positions(self):
        return self._call("GET", "/equity/positions")

    def orders(self):
        return self._call("GET", "/equity/orders")

    def order(self, order_id: int):
        return self._call("GET", f"/equity/orders/{order_id}")

    def history(self, ticker: str) -> list[dict]:
        """The latest 50 finished orders for a ticker, each with its fill (if any)."""
        body = self._call("GET", f"/equity/history/orders?ticker={ticker}&limit=50")
        return [{**it.get("order", it), "fill": it.get("fill")} for it in body.get("items", [])]

    def order_history(self, ticker: str, order_id: int) -> dict | None:
        """Final state of an order that has left the active list (filled, cancelled, rejected)."""
        return next((o for o in self.history(ticker) if o.get("id") == order_id), None)

    def instruments(self):
        return self._call("GET", "/equity/metadata/instruments")

    def exchanges(self):
        return self._call("GET", "/equity/metadata/exchanges")

    # ---- write (quantity > 0 buys, < 0 sells) ----
    def place_limit(self, ticker: str, quantity: float, limit: float, validity: str = "DAY"):
        return self._call("POST", "/equity/orders/limit", {"ticker": ticker, "quantity": qty(quantity),
                                                            "limitPrice": price(limit), "timeValidity": validity})

    def place_market(self, ticker: str, quantity: float):
        return self._call("POST", "/equity/orders/market", {"ticker": ticker, "quantity": qty(quantity),
                                                             "extendedHours": False})

    def place_stop(self, ticker: str, quantity: float, stop: float, validity: str = "GOOD_TILL_CANCEL"):
        return self._call("POST", "/equity/orders/stop", {"ticker": ticker, "quantity": qty(quantity),
                                                           "stopPrice": price(stop), "timeValidity": validity})

    def cancel(self, order_id: int):
        return self._call("DELETE", f"/equity/orders/{order_id}")


# ---------- metadata helpers ----------

def map_tickers(meta: list[dict], instruments: dict) -> dict:
    """Pick the Trading 212 ticker for each of our instruments: same ISIN, same currency; Xetra listings end 'd_EQ'."""
    out = {}
    for sym, inst in instruments.items():
        cands = [m for m in meta if m.get("isin") == inst["isin"] and m.get("currencyCode") == inst["currency"]]
        if inst["market"] == "XETR":
            cands = [m for m in cands if m["ticker"].endswith("d_EQ")] or cands
        else:
            cands = [m for m in cands if m["ticker"].endswith("_US_EQ")] or cands
        if len(cands) == 1:
            c = cands[0]
            out[sym] = {"ticker": c["ticker"], "name": c.get("name", ""), "type": c.get("type", ""),
                        "currency": c["currencyCode"], "schedule": c.get("workingScheduleId")}
        else:
            out[sym] = {"ticker": "", "candidates": [c["ticker"] for c in cands]}
    return out


def write_tickers(mapping: dict) -> None:
    lines = ["# Generated by `python -m tradebot t212-map` from Trading 212 instrument metadata. Review once by hand.", ""]
    for sym, m in mapping.items():
        lines.append(f"[{sym}]")
        for k, v in m.items():
            lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
        lines.append("")
    TICKERS.write_text("\n".join(lines), encoding="utf-8")


def load_tickers() -> dict:
    return tomllib.loads(TICKERS.read_text(encoding="utf-8"))


Session = tuple[dt.datetime, dt.datetime]


def sessions(exchanges: list[dict], schedule_id: int) -> list[Session]:
    """Regular sessions (open, close) in UTC: each OPEN event until the next event (CLOSE on Xetra,
    AFTER_HOURS_OPEN in the US)."""
    for ex in exchanges:
        for ws in ex.get("workingSchedules", []):
            if ws["id"] == schedule_id:
                ev = sorted((dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00")), e["type"]) for e in ws["timeEvents"])
                return [(t, ev[i + 1][0]) for i, (t, kind) in enumerate(ev[:-1]) if kind == "OPEN"]
    return []


def current(sess: list[Session], now: dt.datetime) -> Session | None:
    return next((s for s in sess if s[0] <= now < s[1]), None)


def last_closed(sess: list[Session], now: dt.datetime) -> Session | None:
    return max((s for s in sess if s[1] <= now), default=None)


def next_after(sess: list[Session], t: dt.datetime) -> Session | None:
    return min((s for s in sess if s[0] > t), default=None)
