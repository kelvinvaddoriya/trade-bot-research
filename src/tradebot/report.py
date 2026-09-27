"""Backtest reports (docs/06 §8), the trial log (docs/06 §2.6) and charts."""
import datetime as dt
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .backtest import Result, metrics  # noqa: E402
from .config import CONFIG_DIR, DATA_DIR, REPORTS_DIR, ROOT  # noqa: E402

TRIALS = DATA_DIR / "trials.jsonl"
# Reference palette (dataviz skill): categorical slots 1-2 on the light chart surface.
BLUE, ORANGE, SURFACE, INK, INK2, GRID = "#2a78d6", "#eb6834", "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"


def code_hash() -> str:
    """Hash of source + config: identifies the exact code a result came from (no git commits yet)."""
    h = hashlib.sha256()
    for p in sorted([*(ROOT / "src" / "tradebot").glob("*.py"), *CONFIG_DIR.glob("*.toml")]):
        h.update(p.name.encode() + p.read_bytes().replace(b"\r\n", b"\n"))      # line endings vary by checkout
    return h.hexdigest()[:12]


def log_trial(res: Result, m: dict, period: str, kind: str) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    rec = {"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "kind": kind, "strategy": res.strategy,
           "period": period, "start": str(res.start.date()), "end": str(res.end.date()), "costs_mult": res.costs_mult,
           "params": res.params, "code": code_hash(),
           "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in m.items()}}
    with TRIALS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def trials(strategy: str | None = None) -> list[dict]:
    if not TRIALS.exists():
        return []
    rows = [json.loads(l) for l in TRIALS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if strategy is None or r["strategy"] == strategy]


def chart(res: Result, path) -> None:
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]},
                                 facecolor=SURFACE)
    for ax in (a1, a2):
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, linewidth=0.8)
        ax.tick_params(colors=INK2, labelsize=9)
        for s in ax.spines.values():
            s.set_visible(False)
    a1.plot(res.equity.index, res.equity, color=BLUE, lw=1.6, label=f"{res.strategy} (after costs)")
    a1.plot(res.benchmark.index, res.benchmark, color=ORANGE, lw=1.6, label="Equal-weight universe (no costs)")
    a1.set_ylabel("Equity, EUR", color=INK2, fontsize=9)
    a1.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    a1.set_title(f"{res.strategy}: {res.start.date()} to {res.end.date()}", color=INK, fontsize=11, loc="left")
    for s, color in ((res.equity, BLUE), (res.benchmark, ORANGE)):
        a2.plot(s.index, (s / s.cummax() - 1) * 100, color=color, lw=1.2)
    a2.set_ylabel("Drawdown, %", color=INK2, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def monte_carlo(res: Result, n: int = 1000, seed: int = 0) -> dict:
    """Reshuffle the order of closed-trade P&L: distribution of max drawdown (EUR) and final P&L."""
    pnl = np.array([t.pnl for t in res.trades])
    if len(pnl) < 5:
        return {}
    rng, budget, dds = np.random.default_rng(seed), res.equity.iloc[0], []
    for _ in range(n):
        eq = budget + np.cumsum(rng.permutation(pnl))
        dds.append(float((np.maximum.accumulate(np.r_[budget, eq])[1:] - eq).max()))
    return {"dd_p50": np.percentile(dds, 50), "dd_p95": np.percentile(dds, 95), "dd_max": max(dds), "pnl": pnl.sum()}


def _yearly(s: pd.Series) -> pd.Series:
    ends = s.groupby(s.index.year).last()
    prev = ends.shift()
    prev.iloc[0] = s.iloc[0]
    return ends / prev - 1


def _pct(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.1%}"


def write(res1: Result, res2: Result, period: str, panel: dict, notes: list[str], tag: str = "") -> str:
    m1, m2 = metrics(res1), metrics(res2)
    REPORTS_DIR.mkdir(exist_ok=True)
    stem = f"backtest_{res1.strategy}_{period}{'_' + tag if tag else ''}_{dt.date.today()}"
    chart(res1, REPORTS_DIR / f"{stem}.png")
    proxies = []
    for sym, df in panel.items():
        pr = df[(df.index >= res1.start) & (df.index <= res1.end) & df["is_proxy"].astype(bool)]
        if len(pr):
            proxies.append(f"{sym} ({pr.index[0].date()} to {pr.index[-1].date()})")
    firsts = {s: df.index[0].date() for s, df in panel.items() if df.index[0] > res1.start}
    rows = [
        ("CAGR", _pct(m1["cagr"]), _pct(m2["cagr"]), _pct(m1["bench_cagr"])),
        ("Final equity, EUR", f"{m1['final']:,.0f}", f"{m2['final']:,.0f}", f"{m1['bench_final']:,.0f}"),
        ("Sharpe (± standard error)", f"{m1['sharpe']:.2f} ± {m1['sharpe_se']:.2f}", f"{m2['sharpe']:.2f}", f"{m1['bench_sharpe']:.2f}"),
        ("Sortino", f"{m1['sortino']:.2f}", f"{m2['sortino']:.2f}", ""),
        ("Volatility", f"{m1['vol']:.1%}", f"{m2['vol']:.1%}", ""),
        ("Max drawdown", _pct(m1["max_dd"]), _pct(m2["max_dd"]), _pct(m1["bench_max_dd"])),
        ("Longest drawdown, days", m1["max_dd_days"], m2["max_dd_days"], ""),
        ("Calmar", f"{m1['calmar']:.2f}", f"{m2['calmar']:.2f}", ""),
        ("Exposure (time invested)", f"{m1['exposure']:.0%}", f"{m2['exposure']:.0%}", "100%"),
        ("Trades (open at end)", f"{m1['trades']} ({m1['open_positions']})", f"{m2['trades']}", ""),
        ("Win rate", f"{m1['win_rate']:.0%}", f"{m2['win_rate']:.0%}", ""),
        ("Avg win / avg loss, EUR", f"{m1['avg_win']:.2f} / {m1['avg_loss']:.2f}", f"{m2['avg_win']:.2f} / {m2['avg_loss']:.2f}", ""),
        ("Profit factor", f"{m1['profit_factor']:.2f}", f"{m2['profit_factor']:.2f}", ""),
        ("Avg bars held", f"{m1['avg_bars_held']:.1f}", f"{m2['avg_bars_held']:.1f}", ""),
        ("Costs, EUR (% of gross P&L)", f"{m1['costs_eur']:.0f} ({_pct(m1['costs_pct_gross'])})", f"{m2['costs_eur']:.0f} ({_pct(m2['costs_pct_gross'])})", ""),
        ("Turnover, x per year", f"{m1['turnover_x_per_year']:.1f}", f"{m2['turnover_x_per_year']:.1f}", ""),
        ("Correlation / beta to benchmark", f"{m1['corr']:.2f} / {m1['beta']:.2f}", "", ""),
    ]
    ys, yb = _yearly(res1.equity), _yearly(res1.benchmark)
    trades = pd.DataFrame([t.__dict__ for t in res1.trades]) if res1.trades else pd.DataFrame()
    mc = monte_carlo(res1)
    L = [f"# Backtest: {res1.strategy}, {period} ({res1.start.date()} to {res1.end.date()})", "",
         f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} · code `{code_hash()}` · docs/06 method", "",
         "## Setup", "",
         f"- **Parameters:** `{json.dumps(res1.params)}`",
         f"- **Universe:** {', '.join(panel)}",
         f"- **Instruments starting later than the period:** {', '.join(f'{s} ({d})' for s, d in firsts.items()) or 'none'}",
         f"- **Proxy history used:** {', '.join(proxies) or 'none'}",
         "- **Data:** Yahoo daily bars, dividend-adjusted, converted to EUR at ECB rates (docs/10 step 4)",
         "- **Execution:** signal at close, entries as DAY limit (close + 1 %) at the next open, exits at the next open, "
         "resting stops (gap-through fills at the open). Costs per docs/06 §2.3, and again at 2×.",
         *[f"- {n}" for n in notes], "",
         f"![equity and drawdown]({stem}.png)", "",
         "## Metrics", "", "| Metric | Strategy (1× costs) | Strategy (2× costs) | Benchmark |", "|---|---|---|---|",
         *[f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows], "",
         f"Risk engine: {m1['unfilled']} entry orders unfilled (gap above the limit); rejections: "
         f"{', '.join(f'{k} ×{v}' for k, v in m1['rejections'].items()) or 'none'}.", "",
         f"Kill switch (drawdown ≥ 10 % of the strategy budget from peak) would have tripped on: "
         f"**{m1['kill_switch_would_trip'] or 'never'}**. The backtest keeps trading after that date, so the full "
         "history stays visible. Live, trading would halt there.", "",
         "## Returns per year", "", "| Year | Strategy | Benchmark |", "|---|---|---|",
         *[f"| {y} | {_pct(ys.get(y))} | {_pct(yb.get(y))} |" for y in ys.index], ""]
    if len(trades):
        by = trades.groupby("symbol").agg(trades=("pnl", "size"), pnl=("pnl", "sum"), win=("pnl", lambda x: (x > 0).mean()))
        L += ["## Trades", "", "| Symbol | Trades | P&L, EUR | Win rate |", "|---|---|---|---|",
              *[f"| {s} | {r.trades} | {r.pnl:+.2f} | {r.win:.0%} |" for s, r in by.sort_values("pnl").iterrows()], "",
              "Exit reasons: " + ", ".join(f"{k} ×{v}" for k, v in trades["exit_reason"].value_counts().items()), ""]
        for title, part in (("Top 5 winners", trades.nlargest(5, "pnl")), ("Top 5 losers", trades.nsmallest(5, "pnl"))):
            L += [f"**{title}:** " + "; ".join(f"{r.symbol} {r.entry_date}→{r.exit_date} {r.pnl:+.2f} €" for r in part.itertuples()), ""]
    if mc:
        L += ["## Monte Carlo (1,000 reshuffles of the trade order)", "",
              f"Max drawdown: median €{mc['dd_p50']:.0f}, 95th percentile €{mc['dd_p95']:.0f}, worst €{mc['dd_max']:.0f} "
              f"(closed-trade P&L, starting from €{res1.equity.iloc[0]:.0f}).", ""]
    path = REPORTS_DIR / f"{stem}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(path), m1, m2
