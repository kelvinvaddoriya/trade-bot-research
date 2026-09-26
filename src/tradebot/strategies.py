"""Strategies S1 and S2 (docs/03 §3).

Each strategy has two parts, used identically by the backtest and (from P1) the live engine:
- features(df): causal indicator columns for one symbol (value at t uses bars <= t only);
- decide(day, rows, positions, check_day): pure rule on the latest feature row per symbol.
  rows[sym].fresh is True when that symbol traded on `day` (False on its exchange's holidays).
"""
from dataclasses import dataclass
from typing import ClassVar

import pandas as pd

from . import indicators as ind
from .models import Position, Signal


def is_period_end(day: pd.Timestamp, next_day: pd.Timestamp | None, period: str) -> bool:
    """True on the last trading day of a month ('M') or week ('W'). next_day comes from the calendar."""
    return next_day is not None and day.to_period(period) != next_day.to_period(period)


@dataclass
class S1Trend:
    """Trend filter on UCITS ETFs: hold while close > SMA(200), checked monthly; inverse-volatility weights."""
    name: ClassVar[str] = "s1_trend"
    sma_n: int = 200
    atr_n: int = 20
    atr_mult: float = 3.0
    vol_n: int = 20
    check: str = "M"                 # "M" monthly, "W" weekly
    max_positions: int = 6
    max_position_eur: float = 250.0

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        f = pd.DataFrame({"close": df["close"]}, index=df.index)
        f["sma"] = ind.sma(df["close"], self.sma_n)
        f["atr"] = ind.atr(df["high"], df["low"], df["close"], self.atr_n)
        f["vol"] = ind.volatility(df["close"], self.vol_n)
        f["ready"] = f[["sma", "atr", "vol"]].notna().all(axis=1) & (f["vol"] > 0)
        f["in_trend"] = f["ready"] & (f["close"] > f["sma"])
        return f

    def is_check_day(self, day, next_day) -> bool:
        return is_period_end(day, next_day, self.check)

    def decide(self, day, rows: dict[str, pd.Series], positions: dict[str, Position], check_day: bool) -> list[Signal]:
        if not check_day:
            return []
        sig = []
        trend = {s: r for s, r in rows.items() if r.in_trend}
        for s, pos in positions.items():
            r = rows.get(s)
            if r is None or not r.ready:
                continue
            if s not in trend:
                sig.append(Signal(self.name, s, "sell", "exit", day, "trend lost: close <= SMA", r.close))
            else:
                new_stop = r.close - self.atr_mult * r.atr
                if new_stop > pos.stop:
                    sig.append(Signal(self.name, s, "sell", "trail", day, "raise stop", r.close, stop_price=new_stop))
        inv = {s: 1 / r.vol for s, r in trend.items()}
        total = sum(inv.values())
        for s, r in trend.items():
            if s not in positions:
                w = inv[s] / total
                sig.append(Signal(self.name, s, "buy", "entry", day, "trend: close > SMA", r.close,
                                  stop_distance=self.atr_mult * r.atr, rank=-w, features={"weight": w, "vol": r.vol}))
        return sig


@dataclass
class S2Pullback:
    """Buy short pullbacks in an uptrend; exit on the bounce, a time stop, or the protective stop."""
    name: ClassVar[str] = "s2_pullback"
    sma_n: int = 200
    rsi_n: int = 2
    rsi_entry: float = 10.0
    entry_rule: str = "rsi"          # "rsi" or "bollinger"
    boll_n: int = 20
    boll_k: float = 2.0
    exit_sma_n: int = 5
    time_stop: int = 10
    atr_n: int = 14
    atr_mult: float = 2.5
    max_positions: int = 3
    max_position_eur: float = 200.0

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        c = df["close"]
        f = pd.DataFrame({"close": c}, index=df.index)
        f["sma"] = ind.sma(c, self.sma_n)
        f["rsi"] = ind.rsi(c, self.rsi_n)
        f["exit_sma"] = ind.sma(c, self.exit_sma_n)
        f["atr"] = ind.atr(df["high"], df["low"], c, self.atr_n)
        f["ready"] = f[["sma", "rsi", "exit_sma", "atr"]].notna().all(axis=1)
        if self.entry_rule == "bollinger":
            f["setup"] = c < ind.bollinger_lower(c, self.boll_n, self.boll_k)
        else:
            f["setup"] = f["rsi"] < self.rsi_entry
        f["setup"] = f["ready"] & (c > f["sma"]) & f["setup"]
        return f

    def is_check_day(self, day, next_day) -> bool:
        return True

    def decide(self, day, rows: dict[str, pd.Series], positions: dict[str, Position], check_day: bool = True) -> list[Signal]:
        sig, exiting = [], 0
        for s, pos in positions.items():
            r = rows.get(s)
            if r is None or not r.fresh or not r.ready:
                continue
            if r.close > r.exit_sma:
                sig.append(Signal(self.name, s, "sell", "exit", day, f"close above SMA{self.exit_sma_n}", r.close))
                exiting += 1
            elif pos.bars_held >= self.time_stop:
                sig.append(Signal(self.name, s, "sell", "exit", day, f"time stop {self.time_stop} bars", r.close))
                exiting += 1
        free = self.max_positions - (len(positions) - exiting)
        cands = sorted((r.rsi, s) for s, r in rows.items() if s not in positions and r.fresh and r.setup)
        for rsi_val, s in cands[:max(free, 0)]:
            r = rows[s]
            sig.append(Signal(self.name, s, "buy", "entry", day, f"pullback: RSI{self.rsi_n}={rsi_val:.1f} in uptrend",
                              r.close, stop_distance=self.atr_mult * r.atr, rank=rsi_val))
        return sig


STRATEGIES = {"s1_trend": S1Trend, "s2_pullback": S2Pullback}
