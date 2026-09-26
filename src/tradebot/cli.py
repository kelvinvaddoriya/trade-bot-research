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
    args = p.parse_args()
    args.fn(args)
