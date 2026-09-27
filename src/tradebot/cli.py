"""Command line: `uv run python -m tradebot <command>` (docs/04 §9)."""
import argparse
import datetime as dt
import itertools
import json
import os
import sys

from . import backtest, data, report, risk
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


# ---------- live engine (P1) ----------

def _engine():
    from .live import DB_PATH, Engine
    from .store import Store
    from .trading212 import TICKERS, load_tickers
    risk_cfg = load_risk()                                        # a bad limit refuses to start (drill 6)
    settings, inst = load_settings(), load_instruments()
    if settings.get("mode") != "demo":
        sys.exit('the live engine runs mode = "demo" only until P3 (config/settings.toml)')
    if not TICKERS.exists():
        sys.exit("config/t212_tickers.toml missing: run `python -m tradebot t212-map` first")
    return Engine(_t212(), Store(DB_PATH), data.read_env(), settings, inst, risk_cfg, load_tickers())


def cmd_run(args) -> None:
    from .live import MAX_SKEW_S, engine_alive
    if engine_alive():
        sys.exit("another engine is running (its heartbeat is fresh): two engines would send duplicate orders")
    eng = _engine()
    eng.broker.summary()                                          # the first call also measures the clock skew
    if abs(eng.broker.skew) > MAX_SKEW_S:
        sys.exit(f"clock off by {eng.broker.skew:+.1f} s vs the broker: fix Windows time sync first (docs/05 §10)")
    eng.db.event("ENGINE_START", pid=os.getpid(), limits_hash=eng.risk_cfg["hash"], settings_hash=eng.settings["hash"],
                 code=report.code_hash(), skew=round(eng.broker.skew, 2), kill_switch=risk.is_tripped())
    print(f"engine started (demo): limits {eng.risk_cfg['hash']}, code {report.code_hash()}, clock skew "
          f"{eng.broker.skew:+.2f} s, kill switch {'TRIPPED' if risk.is_tripped() else 'off'}. Ctrl+C stops it.", flush=True)
    try:
        eng.loop()
    except KeyboardInterrupt:
        print("stopped")


def cmd_stop(args) -> None:
    from .live import STOP_FILE, TICK_S, engine_alive
    STOP_FILE.touch()
    print(f"stop requested: the engine exits within {TICK_S} s" if engine_alive() else "no running engine; stop file left for the next start to clear")


def cmd_watchdog(args) -> None:
    from . import notify
    from .live import DB_PATH, watchdog
    from .store import Store
    db, env = Store(DB_PATH), data.read_env()
    print(watchdog(_t212(), db, lambda t: notify.alert(db, env, t)))


def cmd_status(args) -> None:
    from .live import DB_PATH, heartbeat
    from .store import Store
    db, k, hb, settings = Store(DB_PATH), risk.state(), heartbeat(), load_settings()
    print(f"mode: {settings.get('mode')}   kill switch: "
          + (f"TRIPPED ({k['reason']}, by {k['by']}, {k['ts']})" if k["tripped"] else "off"))
    print("heartbeat: " + (f"{hb['state']}, {dt.datetime.now().timestamp() - hb['ts']:.0f} s old (pid {hb['pid']})" if hb else "none"))
    last = {e["type"]: e for e in db.events("type IN ('ENGINE_START', 'ENGINE_STOP', 'RECONCILE', 'EQUITY', 'REPORT')")}
    for t in ("ENGINE_START", "ENGINE_STOP", "RECONCILE", "EQUITY", "REPORT"):
        if t in last:
            print(f"last {t.lower()}: {last[t]['ts']} {json.dumps(last[t]['payload'], default=str)[:200]}")
    for name in settings.get("live", {}).get("strategies", []):
        c = db.events("type='CYCLE' AND entity=?", name)[-1:]
        print(f"last cycle {name}: " + (f"{c[0]['payload']['session']} {c[0]['payload']['result']}" if c else "none"))
    print("open lots:")
    for l in db.select("lots", "status='OPEN'"):
        print(f"  {l['symbol']} {l['qty']:.4f} @ {l['entry_price']:.2f}, stop {l['stop_price']:.2f} (since {l['entry_date']})")
    print("open or pending orders:")
    for o in db.select("orders", "done=0"):
        print(f"  {o['role']} {o['symbol']} {o['qty']:.4f} {o['type']} {o['price'] or ''} -> {o['status']} (session {o['session'] or '-'})")
    print("recent alerts:")
    for e in db.events("type='ALERT'")[-5:]:
        print(f"  {e['ts']} {e['payload']['text']}")


def cmd_kill(args) -> None:
    """HALT from the terminal (docs/05 §4). --flatten also plans a market exit for every lot at the next open."""
    from . import execution, notify
    from .live import DB_PATH
    from .store import Store
    from .trading212 import current, load_tickers, next_after, sessions
    db, env, t = Store(DB_PATH), data.read_env(), _t212()
    execution.halt(t, db, args.reason, lambda x: notify.alert(db, env, x), by="operator")
    print("kill switch tripped; entry orders cancelled; protective stops kept")
    if args.flatten:
        tickers, ex, now = load_tickers(), t.exchanges(), dt.datetime.now(dt.UTC)
        for lot in db.select("lots", "status='OPEN'"):
            sess = sessions(ex, tickers[lot["symbol"]]["schedule"])
            s = current(sess, now) or next_after(sess, now)
            execution.plan_order(db, key=f"{lot['id']}-flatten", role="exit", strategy=lot["strategy"], symbol=lot["symbol"],
                                 ticker=lot["ticker"], lot=lot["id"], session=s[0].date().isoformat(), qty=lot["qty"],
                                 type="market", reason=f"flatten (operator): {args.reason}")
            print(f"  flatten: market exit planned for {lot['symbol']} (session {s[0].date()})")


def cmd_reset_kill(args) -> None:
    """The only way out of HALT (docs/05 §4): shows why it tripped, requires typing RESET, logs who and why.
    The engine reconciles on its next sync before it trades again."""
    from .live import DB_PATH
    from .store import Store
    k = risk.state()
    if not k["tripped"]:
        sys.exit("the kill switch is not tripped")
    db = Store(DB_PATH)
    print(f"tripped {k['ts']} by {k['by']}: {k['reason']}")
    rec = db.events("type='RECONCILE'")[-1:]
    print("last reconciliation: " + (json.dumps(rec[0]["payload"], default=str)[:300] if rec else "none"))
    for l in db.select("lots", "status='OPEN'"):
        print(f"  open lot {l['symbol']} {l['qty']:.4f}, stop {l['stop_price']:.2f}")
    if input("type RESET to re-arm trading: ").strip() != "RESET":
        sys.exit("not reset")
    risk.reset(args.who, args.reason)
    db.event("KILL_RESET", who=args.who, why=args.reason)
    print("kill switch reset")


def cmd_reconcile(args) -> None:
    from . import notify
    from .execution import sync
    from .live import DB_PATH, engine_alive
    from .store import Store
    if engine_alive():
        sys.exit("the engine is running and reconciles on every sync: see `status`")
    db, env = Store(DB_PATH), data.read_env()
    problems = sync(_t212(), db, lambda t: notify.alert(db, env, t))
    print("reconciliation OK" if not problems else "MISMATCH:\n  " + "\n  ".join(problems))


def cmd_report(args) -> None:
    from .live import REPORT_SCHEDULE
    from .trading212 import last_closed
    eng = _engine()
    eng.calendar()
    last = last_closed(eng.cal[REPORT_SCHEDULE], dt.datetime.now(dt.UTC))
    print(f"report: {eng.daily_report(last[0].date())}")


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
    sub.add_parser("run", help="start the live engine (demo)").set_defaults(fn=cmd_run)
    sub.add_parser("stop", help="ask the running engine to exit cleanly (no watchdog trip)").set_defaults(fn=cmd_stop)
    sub.add_parser("watchdog", help="one watchdog check (Task Scheduler runs it every minute)").set_defaults(fn=cmd_watchdog)
    sub.add_parser("status", help="kill switch, heartbeat, lots, orders, last events").set_defaults(fn=cmd_status)
    k = sub.add_parser("kill", help="trip the kill switch (HALT): cancel entries, keep stops")
    k.add_argument("--reason", required=True)
    k.add_argument("--flatten", action="store_true", help="also sell every lot at market at the next open")
    k.set_defaults(fn=cmd_kill)
    r = sub.add_parser("reset-kill", help="re-arm trading after a HALT (typed confirmation, logged)")
    r.add_argument("--who", required=True)
    r.add_argument("--reason", required=True)
    r.set_defaults(fn=cmd_reset_kill)
    sub.add_parser("reconcile", help="reconcile the ledger with the broker (engine stopped)").set_defaults(fn=cmd_reconcile)
    sub.add_parser("report", help="write the daily report for the last US session now").set_defaults(fn=cmd_report)
    args = p.parse_args()
    args.fn(args)
