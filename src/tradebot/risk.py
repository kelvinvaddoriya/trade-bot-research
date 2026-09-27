"""Pre-trade checks and the kill switch (docs/05 §3–4). Only check() approves orders.

The kill switch is a file, re-read on every check, so it survives restarts and other processes (watchdog, CLI)
can trip it. Backtests (mode "backtest") don't consult it.
"""
import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import DATA_DIR
from .models import OrderIntent, RiskDecision

KILL_FILE = DATA_DIR / "KILL"
KILL_LOG = DATA_DIR / "kill_log.jsonl"
MODES = ("backtest", "shadow", "demo", "live")
MAX_BAR_AGE_DAYS = 5     # latest completed bar may be older only across weekends/holidays


@dataclass
class RiskState:
    mode: str = "backtest"
    day: dt.date | None = None                                   # decision day
    held_qty: dict[str, float] = field(default_factory=dict)
    deployed_eur: float = 0.0                                    # market value of open positions
    cash_eur: float = 0.0
    seen_ids: set[str] = field(default_factory=set)
    orders_today: int = 0
    orders_this_minute: int = 0
    daily_loss_hit: bool = False
    last_bar: dict[str, dt.date] = field(default_factory=dict)
    last_close: dict[str, float] = field(default_factory=dict)
    tradable: set[str] | None = None        # live: symbols whose market has a next session; None = not checked


def _failure(o: OrderIntent, st: RiskState, r: dict) -> str | None:
    sym, entry = o.signal.symbol, o.signal.kind == "entry"
    if st.mode != "backtest" and is_tripped():
        return "kill switch tripped"                                        # 1
    if st.mode not in MODES:
        return f"unknown mode {st.mode}"                                    # 2
    if st.tradable is not None and sym not in st.tradable:
        return "market has no next session"                                 # 3
    if sym not in r["whitelist"]:
        return "not on whitelist"                                           # 4
    if o.signal.side == "sell" and o.qty > st.held_qty.get(sym, 0.0) + 1e-9:
        return "sell exceeds holding (no shorting)"                         # 5
    if o.id in st.seen_ids:
        return "duplicate intent"                                           # 6
    if st.orders_today >= r["max_orders_per_day"] or st.orders_this_minute >= r["max_orders_per_minute"]:
        return "order rate limit"                                           # 7
    bar = st.last_bar.get(sym)
    if bar is None or st.day is None or (st.day - bar).days > MAX_BAR_AGE_DAYS:
        return "stale or missing data"                                      # 8
    if o.limit_price is not None and abs(o.limit_price / st.last_close[sym] - 1) > r["price_collar_pct"] + 1e-12:
        return "price collar"                                               # 9
    if not entry:
        return None                                                         # exits reduce risk: done
    if not r["min_order_eur"] <= o.notional_eur <= r["max_position_eur"] + 1e-9:
        return "notional outside [min, max]"                                # 10
    if sum(1 for q in st.held_qty.values() if q > 0) >= r["max_positions"]:
        return "max positions"                                              # 11
    if st.deployed_eur + o.notional_eur > r["capital_cap_eur"] + 1e-9:
        return "capital cap"                                                # 11
    if st.daily_loss_hit:
        return "daily loss limit"                                           # 12
    if o.notional_eur > st.cash_eur + 1e-9:
        return "insufficient cash"                                          # 13
    return None


def check(o: OrderIntent, st: RiskState, risk: dict) -> RiskDecision:
    reason = _failure(o, st, risk)
    if reason is None:
        st.seen_ids.add(o.id)
        st.orders_today += 1
        st.orders_this_minute += 1
    return RiskDecision(o.id, reason is None, reason, risk["hash"])


# ---------- kill switch: sticky, file-backed, reset only by a person ----------

def _log(record: dict, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def trip(reason: str, by: str = "engine", path: Path | None = None, log: Path | None = None) -> None:
    path, log = path or KILL_FILE, log or KILL_LOG
    record = {"tripped": True, "reason": reason, "by": by, "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")        # persist before anything else
    _log(record, log)


def is_tripped(path: Path | None = None) -> bool:
    path = path or KILL_FILE
    return path.exists() and json.loads(path.read_text(encoding="utf-8")).get("tripped", False)


def state(path: Path | None = None) -> dict:
    path = path or KILL_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"tripped": False}


def reset(who: str, why: str, path: Path | None = None, log: Path | None = None) -> None:
    path, log = path or KILL_FILE, log or KILL_LOG
    if path.exists():
        path.unlink()
    _log({"tripped": False, "reset_by": who, "why": why, "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}, log)
