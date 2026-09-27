"""Event-driven daily backtest (docs/06 §2) using the same strategy, sizing and risk code as live.

Per day, per symbol that traded: fill yesterday's orders at the open (exits, then entries), check the
protective stop, count bars held. At the close: mark to market, ask the strategy, size, risk-check, and
queue orders for that symbol's next bar.
"""
import math
from collections import Counter
from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import risk as riskmod
from . import sim
from .models import Position, Trade
from .sizing import make_intent, size_entry


@dataclass
class Result:
    strategy: str
    params: dict
    start: pd.Timestamp
    end: pd.Timestamp
    costs_mult: float
    equity: pd.Series
    benchmark: pd.Series
    exposure: pd.Series
    trades: list[Trade]
    open_positions: int
    rejections: Counter = field(default_factory=Counter)
    unfilled: int = 0
    kill_switch_would_trip: pd.Timestamp | None = None
    held: list[str] = field(default_factory=list)          # symbols still open at the end


def run(strategy, panel: dict[str, pd.DataFrame], instruments: dict, budget: float, start: str, end: str,
        cost_cfg: dict, risk_cfg: dict, costs_mult: float = 1.0) -> Result:
    feats = {s: strategy.features(df) for s, df in panel.items()}
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    dates = sorted(set().union(*(df.index for df in panel.values())))
    dates = [d for d in dates if start <= d <= end]
    costs = {s: sim.costs_for(instruments[s], cost_cfg, costs_mult) for s in panel}
    ohlc = {s: df[["open", "low", "close"]].to_dict("index") for s, df in panel.items()}
    recs = {s: dict(zip(f.index, f.to_dict("records"))) for s, f in feats.items()}

    cash, positions, pending, trades = budget, {}, {}, []
    last_rec, last_date, last_close = {}, {}, {}
    st = riskmod.RiskState(mode="backtest")
    rejections, unfilled = Counter(), 0
    eq, expo, prev_eq, peak, would_trip = [], [], budget, budget, None
    cap = risk_cfg["capital_cap_eur"]

    def close_pos(sym, px, day, reason, c):
        nonlocal cash
        p = positions.pop(sym)
        notional = p.qty * px
        f = sim.fee(notional, c)
        cash += notional - f
        slip = p.qty * px * c.slippage / (1 - c.slippage) if px else 0.0
        entry_slip = p.qty * p.entry_price * c.slippage / (1 + c.slippage)
        trades.append(Trade(strategy.name, sym, p.entry_date, day.date(), p.qty, p.entry_price, px,
                            p.entry_costs + f + slip + entry_slip,
                            p.qty * (px - p.entry_price) - p.entry_costs - f, reason, p.bars_held))

    for i, d in enumerate(dates):
        # ---- open & intraday: fills and stops ----
        for sym in panel:
            bar = ohlc[sym].get(d)
            if bar is None:
                continue
            c = costs[sym]
            for o in pending.pop(sym, []):
                if o.signal.side == "sell":
                    if sym in positions:
                        close_pos(sym, sim.fill_market(bar["open"], "sell", c), d, o.signal.reason, c)
                    continue
                px = sim.fill_limit_buy(bar["open"], o.limit_price, c)
                if px is None:
                    unfilled += 1
                    continue
                qty = min(o.qty, cash / (px * (1 + c.fx_fee)))
                if qty * px < risk_cfg["min_order_eur"]:
                    rejections["cash at fill"] += 1
                    continue
                f = sim.fee(qty * px, c)
                cash -= qty * px + f
                positions[sym] = Position(sym, qty, px, d.date(), px - o.signal.stop_distance, entry_costs=f)
            p = positions.get(sym)
            if p is not None:
                px = sim.fill_stop_sell(bar["open"], bar["low"], p.stop, c)
                if px is not None:
                    close_pos(sym, px, d, "protective stop", c)
                else:
                    p.bars_held += 1
            last_rec[sym], last_date[sym], last_close[sym] = recs[sym][d], d, bar["close"]

        # ---- close: mark to market ----
        deployed = sum(p.qty * last_close[s] for s, p in positions.items())
        equity = cash + deployed
        eq.append(equity)
        expo.append(deployed / equity if equity > 0 else 0.0)
        peak = max(peak, equity)
        if would_trip is None and equity <= peak - risk_cfg["max_drawdown_pct"] * budget:
            would_trip = d
        daily_loss_hit = equity - prev_eq <= -risk_cfg["max_daily_loss_pct"] * budget
        prev_eq = equity

        # ---- decisions ----
        nxt = dates[i + 1] if i + 1 < len(dates) else None
        check_day = strategy.is_check_day(d, nxt)
        if not check_day or not last_rec:
            continue
        rows = {s: SimpleNamespace(**r, fresh=last_date[s] == d) for s, r in last_rec.items()}
        sigs = strategy.decide(d, rows, positions, check_day)
        st.day, st.orders_today, st.orders_this_minute = d.date(), 0, 0
        st.daily_loss_hit = daily_loss_hit
        st.held_qty = {s: p.qty for s, p in positions.items()}
        st.deployed_eur = deployed
        st.cash_eur = cash
        st.last_bar = {s: x.date() for s, x in last_date.items()}
        st.last_close = dict(last_close)
        capital = min(cap, cap * equity / budget)
        for sig in sorted(sigs, key=lambda x: ({"exit": 0, "trail": 1, "entry": 2}[x.kind], x.rank)):
            if sig.kind == "trail":
                positions[sig.symbol].stop = max(positions[sig.symbol].stop, sig.stop_price)
                continue
            if sig.kind == "exit":
                intent = make_intent(sig, positions[sig.symbol].qty)
            else:
                qty, notional, why = size_entry(sig, budget, st.cash_eur, capital, strategy.max_position_eur, risk_cfg)
                if qty <= 0:
                    rejections[f"sizing: {why}"] += 1
                    continue
                intent = make_intent(sig, qty)
            st.orders_this_minute = 0     # live, the executor spaces orders out (≥ 2 s apart); the day limit still applies
            dec = riskmod.check(intent, st, risk_cfg)
            if not dec.approved:
                rejections[f"risk: {dec.reason}"] += 1
                continue
            pending.setdefault(sig.symbol, []).append(intent)
            if sig.kind == "entry":
                st.cash_eur -= intent.notional_eur
                st.deployed_eur += intent.notional_eur
                st.held_qty[sig.symbol] = intent.qty

    idx = pd.DatetimeIndex(dates)
    return Result(strategy.name, dict(vars(strategy)), start, end, costs_mult,
                  pd.Series(eq, idx), benchmark(panel, idx, budget), pd.Series(expo, idx), trades,
                  len(positions), rejections, unfilled, would_trip, sorted(positions))


def benchmark(panel: dict[str, pd.DataFrame], idx: pd.DatetimeIndex, budget: float) -> pd.Series:
    """Equal weight across the universe, rebalanced daily (mean of available daily returns), no costs."""
    rets = pd.concat({s: df["close"].pct_change() for s, df in panel.items()}, axis=1).reindex(idx)
    return budget * (1 + rets.mean(axis=1).fillna(0)).cumprod()


# ---------- metrics ----------

def _stats(equity: pd.Series) -> dict:
    r = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    dd = equity / equity.cummax() - 1
    under = (dd < 0).astype(int)
    longest = (under.groupby((under == 0).cumsum()).cumsum()).max()
    sharpe = r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else 0.0
    downside = math.sqrt((np.minimum(r, 0) ** 2).mean()) * math.sqrt(252)
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    return {"years": years, "cagr": cagr, "vol": r.std() * math.sqrt(252), "sharpe": sharpe,
            "sharpe_se": math.sqrt((1 + sharpe ** 2 / 2) / years) if years > 0 else float("nan"),
            "sortino": r.mean() * 252 / downside if downside > 0 else 0.0,
            "max_dd": dd.min(), "max_dd_days": int(longest), "calmar": cagr / abs(dd.min()) if dd.min() < 0 else 0.0,
            "final": equity.iloc[-1]}


def metrics(res: Result) -> dict:
    m = _stats(res.equity)
    b = _stats(res.benchmark)
    t = res.trades
    pnl = np.array([x.pnl for x in t]) if t else np.array([0.0])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    gross = sum(x.pnl + x.costs for x in t)
    turnover = sum(x.qty * (x.entry_price + x.exit_price) for x in t)
    r, rb = res.equity.pct_change().dropna(), res.benchmark.pct_change().dropna()
    beta = r.cov(rb) / rb.var() if rb.var() > 0 else 0.0
    m.update({
        "trades": len(t), "open_positions": res.open_positions,
        "win_rate": len(wins) / len(t) if t else 0.0,
        "avg_win": wins.mean() if len(wins) else 0.0, "avg_loss": losses.mean() if len(losses) else 0.0,
        "profit_factor": wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf"),
        "avg_bars_held": float(np.mean([x.bars_held for x in t])) if t else 0.0,
        "costs_eur": sum(x.costs for x in t), "costs_pct_gross": (sum(x.costs for x in t) / gross) if gross > 0 else float("nan"),
        "turnover_x_per_year": turnover / res.equity.mean() / m["years"] if m["years"] > 0 else 0.0,
        "exposure": res.exposure.mean(),
        "bench_cagr": b["cagr"], "bench_sharpe": b["sharpe"], "bench_max_dd": b["max_dd"], "bench_final": b["final"],
        "excess_cagr": m["cagr"] - b["cagr"], "corr": r.corr(rb), "beta": beta,
        "unfilled": res.unfilled, "rejections": dict(res.rejections),
        "kill_switch_would_trip": str(res.kill_switch_would_trip.date()) if res.kill_switch_would_trip is not None else None,
    })
    return m
