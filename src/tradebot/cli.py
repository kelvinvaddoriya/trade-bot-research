"""Command line: `uv run python -m tradebot <command>` (docs/04 §9)."""
import argparse
import datetime as dt
import itertools
import json
import sys

from . import backtest, data, report
from .config import REPORTS_DIR, load_instruments, load_risk, load_settings
from .strategies import STRATEGIES

ALIASES = {"s1": "s1_trend", "s2": "s2_pullback"}
# Robustness ranges (docs/03 §3). The defaults sit in the middle of each range.
GRIDS = {
    "s1_trend": {"sma_n": [150, 200, 250], "check": ["M", "W"], "atr_mult": [2.0, 3.0, 4.0]},
    "s2_pullback": {"rsi_entry": [5.0, 10.0, 15.0], "exit_sma_n": [3, 5, 10], "time_stop": [5, 10, 15],
                    "atr_mult": [2.0, 2.5, 3.5]},
}


def _period(settings: dict, name: str) -> tuple[str, str]:
    p = settings["periods"]
    return {"insample": (p["in_sample_start"], p["in_sample_end"]),
            "holdout": (p["holdout_start"], p["holdout_end"]),
            "recent": (p["recent_start"], str(dt.date.today())),
            "all": (p["in_sample_start"], str(dt.date.today()))}[name]


def _parse_params(items: list[str]) -> dict:
    out = {}
    for it in items or []:
        k, v = it.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def cmd_data(args) -> None:
    settings, inst = load_settings(), load_instruments()
    res = data.update(inst, settings["periods"]["data_start"])
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"data_check_{dt.date.today()}.md"
    lines = [f"# Data check {dt.date.today()}", "", "Source quality per series (docs/10 step 4).", "",
             "| Series | Rows | First | Last | Non-positive | High<Low | OHLC inconsistent | Jumps >25% | Gaps >7d |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, v in res["validation"].items():
        lines.append(f"| {name} | {v['rows']} | {v['first']} | {v['last']} | {v['nonpositive']} | {v['high_below_low']} "
                     f"| {v['ohlc_inconsistent']} | {v['jumps_over_25pct']} | {v['gaps_over_7_days']} |")
    lines += ["", "## Yahoo vs Alpaca (US stocks, daily returns on overlapping days)", "",
              "| Symbol | Days | Correlation | Days with >0.5% difference | Share | Max difference % |", "|---|---|---|---|---|---|"]
    for sym, c in res["cross_check"].items():
        lines.append(f"| {sym} | {c['days']} | {c['corr']} | {c['days_diff_over_0.5pct']} | {c['share_diff_over_0.5pct']:.2%} | {c['max_diff_pct']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {path}")


def _setup(name: str):
    settings, inst, risk = load_settings(), load_instruments(), load_risk()
    return settings, inst, risk, data.load_panel(inst, name)


def cmd_backtest(args) -> None:
    name = ALIASES.get(args.strategy, args.strategy)
    params = _parse_params(args.param)
    if args.period == "holdout":
        done = [t for t in report.trials(name) if t["kind"] == "holdout"]
        if not args.frozen:
            sys.exit("holdout needs --frozen: parameters must be fixed from in-sample work first (docs/06 §2.4)")
        if done and not args.force:
            sys.exit(f"holdout for {name} already run on {done[0]['ts']}: it runs once (docs/06 §2.4). --force overrides.")
    settings, inst, risk, panel = _setup(name)
    start, end = _period(settings, args.period)
    strat = STRATEGIES[name](**params)
    budget = settings["budgets_eur"][name]
    r1 = backtest.run(strat, panel, inst, budget, start, end, settings["costs"], risk, 1.0)
    r2 = backtest.run(strat, panel, inst, budget, start, end, settings["costs"], risk, 2.0)
    tag = "_".join(f"{k}-{v}" for k, v in params.items())        # non-default runs get their own report file
    path, m1, m2 = report.write(r1, r2, args.period, panel, [f"Budget: €{budget} of the €1,000 cap."], tag)
    kind = "holdout" if args.period == "holdout" else "backtest"
    report.log_trial(r1, m1, args.period, kind)
    report.log_trial(r2, m2, args.period, kind + "_2x_costs")
    print(f"{name} {args.period}: CAGR {m1['cagr']:+.2%} (2x costs {m2['cagr']:+.2%}), Sharpe {m1['sharpe']:.2f}, "
          f"max DD {m1['max_dd']:.1%}, trades {m1['trades']} | benchmark CAGR {m1['bench_cagr']:+.2%}, "
          f"max DD {m1['bench_max_dd']:.1%}\nreport: {path}")


def cmd_grid(args) -> None:
    name = ALIASES.get(args.strategy, args.strategy)
    settings, inst, risk, panel = _setup(name)
    start, end = _period(settings, "insample")
    grid, budget = GRIDS[name], settings["budgets_eur"][name]
    base = _parse_params(args.param)
    rows = []
    for combo in itertools.product(*grid.values()):
        params = {**base, **dict(zip(grid, combo))}
        res = backtest.run(STRATEGIES[name](**params), panel, inst, budget, start, end, settings["costs"], risk, 1.0)
        m = backtest.metrics(res)
        report.log_trial(res, m, "insample", "grid")
        rows.append((combo, m))
        print(" ".join(f"{k}={v}" for k, v in zip(grid, combo)), f"CAGR {m['cagr']:+.2%} Sharpe {m['sharpe']:.2f} DD {m['max_dd']:.1%} trades {m['trades']}")
    default = tuple(getattr(STRATEGIES[name](**base), k) for k in grid)
    sharpes = sorted(m["sharpe"] for _, m in rows)
    d_sharpe = next(m["sharpe"] for c, m in rows if c == default)
    L = [f"# Robustness grid: {name}, in-sample {start} to {end}", "",
         f"{len(rows)} parameter combinations at 1× costs (docs/06 §2.5). Default: "
         f"{', '.join(f'{k}={v}' for k, v in zip(grid, default))}. Code `{report.code_hash()}`.", "",
         f"- Combinations with positive CAGR after costs: **{sum(m['cagr'] > 0 for _, m in rows)} / {len(rows)}**",
         f"- Sharpe: min {sharpes[0]:.2f}, median {sharpes[len(sharpes) // 2]:.2f}, max {sharpes[-1]:.2f}; "
         f"default {d_sharpe:.2f} (rank {sharpes.index(d_sharpe) + 1} of {len(rows)})",
         "- A plateau means neighbours of the default perform similarly; a lone spike means overfitting risk.", "",
         "| " + " | ".join(grid) + " | CAGR | Sharpe | Max DD | Trades |", "|" + "---|" * (len(grid) + 4)]
    for combo, m in sorted(rows, key=lambda x: -x[1]["sharpe"]):
        mark = " **(default)**" if combo == default else ""
        L.append("| " + " | ".join(map(str, combo)) + f" | {m['cagr']:+.2%} | {m['sharpe']:.2f}{mark} | {m['max_dd']:.1%} | {m['trades']} |")
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"grid_{name}_{dt.date.today()}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"report: {path}")


def _t212():
    from .trading212 import Trading212
    env = data.read_env()
    return Trading212(env["T212_DEMO_API_KEY"], env["T212_DEMO_API_SECRET"])


def cmd_t212_map(args) -> None:
    from .trading212 import TICKERS, map_tickers, write_tickers
    mapping = map_tickers(_t212().instruments(), load_instruments())
    write_tickers(mapping)
    missing = {s: m.get("candidates") for s, m in mapping.items() if not m["ticker"]}
    print(f"mapped {len(mapping) - len(missing)}/{len(mapping)} instruments -> {TICKERS}")
    for s, c in missing.items():
        print(f"  unresolved {s}: candidates {c}")


def cmd_demo_trade(args) -> None:
    """Demo order through the real pipeline: risk check -> submit-once -> broker -> journal -> reconcile."""
    import time

    from . import risk
    from .execution import fill_price, journal, submit_once, wait_for
    from .models import OrderIntent, Signal, intent_id
    from .sizing import ENTRY_LIMIT
    from .trading212 import TICKERS, is_open, load_tickers, qty

    inst, risk_cfg, sym = load_instruments(), load_risk(), args.symbol.upper()
    if sym not in inst or inst[sym]["currency"] != "EUR":
        sys.exit("demo supports the whitelisted EUR instruments (e.g. SXR8, SAP)")
    if not TICKERS.exists():
        cmd_t212_map(args)
    tk = load_tickers()[sym]
    ticker, t = tk["ticker"], _t212()

    summ = t.summary()
    avail = summ["cash"]["availableToTrade"]
    print(f"account: DEMO, {summ['currency']}, available {avail:,.2f} (bot sizes against the €{risk_cfg['capital_cap_eur']} cap)")
    open_now = is_open(t.exchanges(), tk["schedule"])
    bars = data.fetch_yahoo(inst[sym]["yahoo"], str(dt.date.today() - dt.timedelta(days=14)))
    close, bar_day = float(bars.iloc[-1]["close"]), bars.iloc[-1]["date"]
    print(f"instrument: {sym} = {ticker} ({tk['name']}); market open now: {open_now}; last close {close:.2f} on {bar_day}")

    positions, open_orders = t.positions(), t.orders()
    if any(o.get("ticker") == ticker for o in open_orders):
        sys.exit(f"there are already open orders for {ticker}: the bot's account must only hold its own orders")
    held = {p.get("ticker") or p.get("instrument", {}).get("ticker"): p.get("quantity", 0) for p in positions}

    if args.mode == "roundtrip" and not open_now:
        sys.exit("market closed: the round trip needs an open market (Xetra 09:00-17:30 CET)")
    limit = close * (1 - 0.015) if args.mode == "lifecycle" else close * (1 + ENTRY_LIMIT)
    q = qty(args.eur / limit)
    sig = Signal("demo", sym, "buy", "entry", dt.date.today(), f"manual demo ({args.mode})", close)
    intent = OrderIntent(intent_id("demo", sym, "buy", dt.datetime.now()), sig, q, "limit", limit, q * limit)
    st = risk.RiskState(mode="demo", day=dt.date.today(), cash_eur=min(avail, risk_cfg["capital_cap_eur"]),
                        held_qty={sym: held.get(ticker, 0.0)}, last_bar={sym: bar_day}, last_close={sym: close})
    dec = risk.check(intent, st, risk_cfg)
    journal("RISK_DECISION", intent_id=intent.id, approved=dec.approved, reason=dec.reason, limits_hash=dec.limits_hash)
    print(f"risk engine: {'APPROVED' if dec.approved else 'REJECTED: ' + dec.reason} "
          f"(buy {q} x {ticker} limit {limit:.2f} = €{q * limit:.2f}, limits {dec.limits_hash})")
    if not dec.approved:
        return

    def match(orders):
        return next((o for o in orders if o.get("ticker") == ticker and abs(o.get("quantity", 0) - q) < 1e-6), None)

    order = submit_once(t, intent.id, lambda: t.place_limit(ticker, q, limit, "DAY"), match)
    if order is None:
        sys.exit("order not found after two lookups: nothing resent (submit-once). Check the app.")
    oid = order["id"]
    time.sleep(2)
    now = t.order(oid)
    print(f"order {oid}: accepted by Trading 212, status {now.get('status')} "
          f"({now.get('type')} {now.get('quantity')} @ {now.get('limitPrice')}, {now.get('timeInForce') or now.get('timeValidity')})")
    journal("BROKER_STATUS", intent_id=intent.id, order_id=oid, status=now.get("status"))

    if args.mode == "lifecycle":
        t.cancel(oid)
        final = wait_for(t, oid, ticker, {"CANCELLED"})
        journal("CANCELLED", intent_id=intent.id, order_id=oid, status=final and final["status"],
                filled=final and final.get("filledQuantity"))
        print(f"order {oid}: cancel requested -> {final and final['status']} (filled {final and final.get('filledQuantity')})")
    else:
        final = wait_for(t, oid, ticker, timeout=120)
        if not final or final.get("status") != "FILLED":
            if final is None or final.get("status") not in ("CANCELLED", "REJECTED"):
                t.cancel(oid)
            sys.exit(f"entry not filled ({final and final.get('status')}): cancelled, nothing held")
        fq, fpx = final["filledQuantity"], fill_price(final)
        journal("FILLED", intent_id=intent.id, order_id=oid, qty=fq, price=fpx)
        print(f"FILLED {fq} @ {fpx:.2f}")
        stop = submit_once(t, intent.id + "-stop", lambda: t.place_stop(ticker, -fq, fpx * 0.97), match=lambda o: None)
        print(f"protective stop {stop['id']} placed at {fpx * 0.97:.2f} (GTC)")
        t.cancel(stop["id"])
        wait_for(t, stop["id"], ticker, {"CANCELLED"})
        sell = submit_once(t, intent.id + "-exit", lambda: t.place_market(ticker, -fq), match=lambda o: None)
        done = wait_for(t, sell["id"], ticker, timeout=120)
        journal("EXIT", intent_id=intent.id, order_id=sell["id"], status=done and done.get("status"))
        print(f"closed: market sell {sell['id']} -> {done and done.get('status')}")

    time.sleep(1)
    left = [o for o in t.orders() if o.get("ticker") == ticker]
    pos = {p.get("ticker") or p.get("instrument", {}).get("ticker"): p.get("quantity") for p in t.positions()}
    ok = not left and pos.get(ticker, 0) == held.get(ticker, 0)
    journal("RECONCILE", ticker=ticker, open_orders=len(left), position=pos.get(ticker, 0), ok=ok)
    print(f"reconcile: open orders for {ticker}: {len(left)}, position: {pos.get(ticker, 0)} -> {'OK' if ok else 'MISMATCH'}")
    print("journal: data/journal.jsonl")


def main() -> None:
    p = argparse.ArgumentParser(prog="tradebot")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("data", help="download/refresh market data and write a data-check report").set_defaults(fn=cmd_data)
    b = sub.add_parser("backtest", help="run a backtest (1x and 2x costs) and write a report")
    b.add_argument("--strategy", required=True, help="s1 | s2")
    b.add_argument("--period", default="insample", choices=["insample", "holdout", "recent", "all"])
    b.add_argument("--param", action="append", help="override a parameter, e.g. --param rsi_entry=5")
    b.add_argument("--frozen", action="store_true", help="confirm parameters are frozen (required for holdout)")
    b.add_argument("--force", action="store_true", help="allow a second holdout run (logged)")
    b.set_defaults(fn=cmd_backtest)
    g = sub.add_parser("grid", help="robustness grid over the parameter ranges (in-sample)")
    g.add_argument("--strategy", required=True)
    g.add_argument("--param", action="append", help="fixed parameter for all combinations")
    g.set_defaults(fn=cmd_grid)
    sub.add_parser("t212-map", help="map whitelisted instruments to Trading 212 tickers").set_defaults(fn=cmd_t212_map)
    d = sub.add_parser("demo-trade", help="place a demo order on the Trading 212 PRACTICE account")
    d.add_argument("--symbol", default="SXR8")
    d.add_argument("--eur", type=float, default=25.0, help="order size in EUR (default 25)")
    d.add_argument("--mode", default="lifecycle", choices=["lifecycle", "roundtrip"],
                   help="lifecycle: place a limit below the market and cancel it (any time); "
                        "roundtrip: buy, protective stop, sell (market must be open)")
    d.set_defaults(fn=cmd_demo_trade)
    args = p.parse_args()
    args.fn(args)
