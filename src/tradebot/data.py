"""Market data: download, cache (SQLite), validate, cross-check, and build EUR panels (docs/01 §6, docs/10 step 4).

Sources: Yahoo chart API (research history, unofficial), Alpaca (official US data, cross-check),
Frankfurter (ECB EUR/USD reference rates).
"""
import datetime as dt
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from .config import DATA_DIR, read_env  # noqa: F401  (read_env re-exported for callers)

DB = DATA_DIR / "research.db"
UA = {"User-Agent": "Mozilla/5.0 (TradeBot research; personal use)"}
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
ALPACA = "https://data.alpaca.markets/v2/stocks/bars"
FX = "https://api.frankfurter.dev/v1/{start}..{end}?base=EUR&symbols=USD"
JUMP = 0.25            # |daily return| above this is flagged for review


# ---------- HTTP & env ----------

def http_json(url: str, headers: dict | None = None, tries: int = 3) -> dict:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1 or (isinstance(e, urllib.error.HTTPError) and e.code < 500 and e.code != 429):
                raise
            time.sleep(2 * (attempt + 1))


# ---------- downloads ----------

def fetch_yahoo(sym: str, start: str, through: dt.date | None = None) -> pd.DataFrame:
    """Daily bars from `start`. `through` is the last completed session (live); by default today's bar is
    dropped because it may still be forming."""
    p1 = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.UTC).timestamp())
    res = http_json(YAHOO.format(sym=urllib.parse.quote(sym), p1=p1, p2=int(time.time())))["chart"]["result"][0]
    offset = res["meta"].get("gmtoffset", 0)
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({
        "date": [dt.datetime.fromtimestamp(t + offset, dt.UTC).date() for t in res["timestamp"]],
        "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"],
        "adjclose": res["indicators"]["adjclose"][0]["adjclose"], "volume": q["volume"],
    })
    df = df[df["date"] <= through] if through else df[df["date"] < dt.datetime.now(dt.UTC).date()]
    return df.drop_duplicates("date", keep="last").dropna(subset=["open", "high", "low", "close", "adjclose"])


def fetch_alpaca(sym: str, start: str, env: dict) -> pd.DataFrame:
    headers = {"APCA-API-KEY-ID": env["APCA_API_KEY_ID"], "APCA-API-SECRET-KEY": env["APCA_API_SECRET_KEY"]}
    rows, token = [], None
    while True:
        params = {"symbols": sym, "timeframe": "1Day", "start": start, "adjustment": "all", "feed": "sip", "limit": 10000}
        if token:
            params["page_token"] = token
        body = http_json(f"{ALPACA}?{urllib.parse.urlencode(params)}", headers)
        rows += body.get("bars", {}).get(sym, [])
        token = body.get("next_page_token")
        if not token:
            break
    df = pd.DataFrame(rows)
    return pd.DataFrame({"date": pd.to_datetime(df["t"]).dt.date, "open": df["o"], "high": df["h"], "low": df["l"],
                         "close": df["c"], "adjclose": df["c"], "volume": df["v"]})


def fetch_fx(start: str) -> pd.DataFrame:
    """ECB EUR/USD reference rates via Frankfurter, one request per year."""
    out = {}
    for year in range(int(start[:4]), dt.date.today().year + 1):
        body = http_json(FX.format(start=f"{year}-01-01", end=f"{year}-12-31"))
        out.update({d: r["USD"] for d, r in body["rates"].items()})
    return pd.DataFrame({"date": [dt.date.fromisoformat(d) for d in out], "eurusd": list(out.values())})


# ---------- cache ----------

def connect(path=None) -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(path or DB)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS bars (source TEXT, symbol TEXT, date TEXT, open REAL, high REAL, low REAL,
            close REAL, adjclose REAL, volume REAL, currency TEXT, fetched_at TEXT, PRIMARY KEY (source, symbol, date));
        CREATE TABLE IF NOT EXISTS fx (date TEXT PRIMARY KEY, eurusd REAL, source TEXT);
    """)
    return con


def save_bars(con, df: pd.DataFrame, source: str, symbol: str, currency: str) -> None:
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    con.executemany(
        "INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(source, symbol, r.date.isoformat(), r.open, r.high, r.low, r.close, r.adjclose, r.volume, currency, now)
         for r in df.itertuples()])
    con.commit()


def load_bars(con, source: str, symbol: str) -> pd.DataFrame:
    df = pd.read_sql("SELECT date, open, high, low, close, adjclose, volume FROM bars WHERE source=? AND symbol=? ORDER BY date",
                     con, params=(source, symbol), parse_dates=["date"])
    return df.set_index("date")


def load_fx(con) -> pd.Series:
    df = pd.read_sql("SELECT date, eurusd FROM fx ORDER BY date", con, parse_dates=["date"])
    return df.set_index("date")["eurusd"]


# ---------- quality ----------

def validate(df: pd.DataFrame) -> dict:
    """Counts of suspicious rows. Rows with non-positive prices or high < low are unusable."""
    ret = df["adjclose"].pct_change()
    gaps = pd.Series(df.index).diff().dt.days
    return {
        "rows": len(df),
        "first": df.index[0].date() if len(df) else None,
        "last": df.index[-1].date() if len(df) else None,
        "nonpositive": int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()),
        "high_below_low": int((df["high"] < df["low"]).sum()),
        "ohlc_inconsistent": int(((df["high"] < df[["open", "close"]].max(axis=1) * 0.999) |
                                  (df["low"] > df[["open", "close"]].min(axis=1) * 1.001)).sum()),
        "jumps_over_25pct": int((ret.abs() > JUMP).sum()),
        "gaps_over_7_days": int((gaps > 7).sum()),
    }


def usable(df: pd.DataFrame) -> pd.DataFrame:
    bad = (df[["open", "high", "low", "close", "adjclose"]] <= 0).any(axis=1) | (df["high"] < df["low"])
    return df[~bad]


def cross_check(yahoo: pd.DataFrame, alpaca: pd.DataFrame) -> dict:
    """Compare daily returns (robust to different dividend-adjustment methods) on overlapping dates."""
    both = pd.concat({"y": yahoo["adjclose"], "a": alpaca["adjclose"]}, axis=1).dropna()
    r = both.pct_change().dropna()
    diff = (r["y"] - r["a"]).abs()
    return {"days": len(r), "corr": round(float(r["y"].corr(r["a"])), 5),
            "days_diff_over_0.5pct": int((diff > 0.005).sum()),
            "share_diff_over_0.5pct": round(float((diff > 0.005).mean()), 4),
            "max_diff_pct": round(float(diff.max() * 100), 2)}


# ---------- update ----------

def update(instruments: dict, start: str, log=print) -> dict:
    """Download everything into the cache. Returns validation and cross-check results for the report."""
    env, con = read_env(), connect()
    fx = fetch_fx(start)
    con.executemany("INSERT OR REPLACE INTO fx VALUES (?,?,?)", [(d.isoformat(), v, "frankfurter/ECB") for d, v in fx.itertuples(index=False)])
    con.commit()
    log(f"fx: {len(fx)} EUR/USD rates {fx['date'].min()} .. {fx['date'].max()}")

    yahoo_syms = {}                                    # yahoo symbol -> currency
    for inst in instruments.values():
        yahoo_syms[inst["yahoo"]] = inst["currency"]
        if inst.get("proxy"):
            yahoo_syms[inst["proxy"]] = "USD"
    results = {"validation": {}, "cross_check": {}}
    for ysym, cur in yahoo_syms.items():
        df = fetch_yahoo(ysym, start)
        save_bars(con, df, "yahoo", ysym, cur)
        results["validation"][f"yahoo:{ysym}"] = validate(load_bars(con, "yahoo", ysym))
        log(f"yahoo {ysym}: {len(df)} bars")
        time.sleep(0.5)                                # be polite to an unofficial endpoint
    for sym, inst in instruments.items():
        if inst.get("alpaca"):
            df = fetch_alpaca(inst["alpaca"], start, env)
            save_bars(con, df, "alpaca", inst["alpaca"], "USD")
            a = load_bars(con, "alpaca", inst["alpaca"])
            results["validation"][f"alpaca:{inst['alpaca']}"] = validate(a)
            results["cross_check"][sym] = cross_check(load_bars(con, "yahoo", inst["yahoo"]), a)
            log(f"alpaca {sym}: {len(df)} bars; cross-check {results['cross_check'][sym]}")
    con.close()
    return results


def refresh(instruments: dict, through: dt.date, start: str, log=print) -> None:
    """Runtime update for the live engine: each instrument's full Yahoo history up to the session that just closed.
    Full history, not just recent days, because a dividend changes the adjusted close of every earlier bar.
    Proxies aren't refreshed: they only fill years long past, and the stitch rescales them anyway."""
    con = connect()
    for inst in instruments.values():
        save_bars(con, fetch_yahoo(inst["yahoo"], start, through), "yahoo", inst["yahoo"], inst["currency"])
        time.sleep(0.5)
    con.close()
    log(f"refreshed {len(instruments)} instruments through {through}")


# ---------- panels ----------

def _eur_adjusted(df: pd.DataFrame, currency: str, fx: pd.Series) -> pd.DataFrame:
    """Split/dividend-adjusted OHLC (scaled by adjclose/close), converted to EUR at the ECB rate of the day."""
    f = df["adjclose"] / df["close"]
    out = pd.DataFrame({c: df[c] * f for c in ("open", "high", "low", "close")})
    if currency == "USD":
        rate = fx.reindex(out.index.union(fx.index)).ffill().reindex(out.index)
        out = out.div(rate, axis=0)
    out["volume"] = df["volume"]
    return out.dropna(subset=["close"])


def load_panel(instruments: dict, strategy: str, con=None) -> dict[str, pd.DataFrame]:
    """EUR, adjusted OHLCV per symbol of a strategy. Proxy history is stitched in before the instrument existed."""
    con = con or connect()
    fx = load_fx(con)
    panel = {}
    for sym, inst in instruments.items():
        if inst["strategy"] != strategy:
            continue
        own = _eur_adjusted(usable(load_bars(con, "yahoo", inst["yahoo"])), inst["currency"], fx)
        if inst.get("native_from"):
            own = own[own.index >= pd.Timestamp(inst["native_from"])]
        own["is_proxy"] = False
        if inst.get("proxy"):
            px = _eur_adjusted(usable(load_bars(con, "yahoo", inst["proxy"])), "USD", fx)
            d0 = own.index[0]
            anchor = px["close"][px.index <= d0]
            if len(anchor):
                k = own["close"].iloc[0] / anchor.iloc[-1]
                pre = px[px.index < d0].copy()
                pre[["open", "high", "low", "close"]] *= k
                pre["is_proxy"] = True
                own = pd.concat([pre, own])
        panel[sym] = own
    return panel
