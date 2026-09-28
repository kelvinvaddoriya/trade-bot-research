"""The live engine (docs/04 §2–3). P1: demo money on the Trading 212 practice account.

Decisions are made after a session closes; the orders go out after the next open (exits first). Nothing but
protective stops rests at the broker overnight, and a crash between close and open leaves nothing half-sent.

The loop ticks every 20 s. A heartbeat thread writes data/heartbeat.json every 15 s while the loop keeps making
progress, so a dead or hung engine goes stale and the watchdog (watchdog.py) trips the kill switch. Each sync (every 2 min
while a traded market is open, else every 10 min): reconcile, and halt on a mismatch seen twice in a row (once
could be a fill in flight) → keep protective stops right → send pending orders after the open → decision cycle
once per session after the close → daily report after the US close → ping the dead-man's switch.
"""
import datetime as dt
import json
import threading
import time
import traceback
from types import SimpleNamespace

import pandas as pd

from . import backtest, data, execution, notify, risk
from .config import DATA_DIR, DB_PATH, REPORTS_DIR  # noqa: F401  (DB_PATH used by the CLI)
from .models import Position
from .sizing import make_intent, size_entry
from .strategies import STRATEGIES
from .trading212 import current, last_closed, next_after, price, qty, sessions
from .watchdog import beat

STOP_FILE = DATA_DIR / "STOP"              # `python -m tradebot stop` asks the engine to exit cleanly
TICK_S, BEAT_S, HANG_S = 20, 15, 600
SYNC_OPEN_S, SYNC_CLOSED_S = 120, 600
OPEN_DELAY = dt.timedelta(minutes=2)       # let the opening auction finish before sending orders
CLOSE_GUARD = dt.timedelta(minutes=10)     # no new orders in a session's last minutes
CYCLE_DELAY = dt.timedelta(minutes=20)     # decide this long after the close, once the daily bar is final
LATE_LIMIT = dt.timedelta(hours=1)         # a cycle still unrun an hour into the next session is skipped
REPORT_SCHEDULE = 56                       # NYSE in Trading 212's schedules: the daily report follows the US close
MAX_SKEW_S = 2.5                           # 2 s (docs/05 §10) plus the HTTP Date header's whole-second resolution
JUMP = 0.25                                # a bigger daily move is treated as a bad tick or unadjusted split


class RiskEngineError(Exception):
    pass


# ---------- decisions ----------

def suspect(panel: dict[str, pd.DataFrame], day: dt.date) -> list[str]:
    """Symbols whose latest bar isn't the session that just closed, or that jumped more than 25 % (docs/05 §10)."""
    out = []
    for s, df in panel.items():
        last = df.index[-1].date()
        jump = abs(df["close"].iloc[-1] / df["close"].iloc[-2] - 1) if len(df) > 1 else 0.0
        if last != day:
            out.append(f"{s}: last bar {last}")
        elif jump > JUMP:
            out.append(f"{s}: {jump:.0%} move")
    return out


def mark(db, cap: float, marks: dict[str, float]) -> dict:
    """Book equity = cap + realised P&L + open lots at `marks` (symbol -> price). Journals an EQUITY event with the
    peak and the change since the last mark of an earlier day."""
    lots = db.select("lots")
    equity = cap + sum(l["pnl"] or 0 for l in lots) + sum(
        l["qty"] * (marks.get(l["symbol"], l["entry_price"]) - l["entry_price"]) for l in lots if l["status"] == "OPEN")
    prev = db.events("type='EQUITY'")
    peak = max([cap, equity] + [e["payload"]["equity"] for e in prev])
    earlier = [e for e in prev if e["ts"][:10] < dt.datetime.now(dt.UTC).date().isoformat()]
    change = equity - earlier[-1]["payload"]["equity"] if earlier else 0.0
    m = {"equity": round(equity, 2), "peak": round(peak, 2), "day_change": round(change, 2)}
    db.event("EQUITY", **m)
    return m


def decide(db, strat, panel: dict[str, pd.DataFrame], day: dt.date, next_day: dt.date, risk_cfg: dict,
           budget: float, tickers: dict, daily_loss_hit: bool, tradable: set[str]) -> dict:
    """One decision cycle on fresh bars of the session that just closed: signals → sizing → risk check, exactly as
    in the backtest. Approved orders are planned for the next session; trails raise the lot's stop at once."""
    rows = {s: SimpleNamespace(**strat.features(df).iloc[-1].to_dict(), fresh=True) for s, df in panel.items()}
    closes = {s: float(r.close) for s, r in rows.items()}
    lots = {l["symbol"]: l for l in db.select("lots", "status='OPEN' AND strategy=?", strat.name)}
    positions = {s: Position(s, l["qty"], l["entry_price"], dt.date.fromisoformat(l["entry_date"]), l["stop_price"])
                 for s, l in lots.items()}
    deployed = sum(l["qty"] * closes.get(s, l["entry_price"]) for s, l in lots.items())
    equity = budget + sum(l["pnl"] or 0 for l in db.select("lots", "strategy=?", strat.name)) + sum(
        l["qty"] * (closes.get(s, l["entry_price"]) - l["entry_price"]) for s, l in lots.items())
    cap = risk_cfg["capital_cap_eur"]
    capital = min(cap, cap * equity / budget)                    # risk shrinks after losses, as in the backtest
    st = risk.RiskState(mode="demo", day=day, held_qty={s: l["qty"] for s, l in lots.items()}, deployed_eur=deployed,
                        cash_eur=equity - deployed, daily_loss_hit=daily_loss_hit,
                        seen_ids={r["intent_id"] for r in db.select("orders", "intent_id IS NOT NULL")},
                        orders_today=len(db.select("orders", "session=? AND role!='stop'", next_day.isoformat())),
                        last_bar={s: df.index[-1].date() for s, df in panel.items()}, last_close=closes, tradable=tradable)
    sigs = strat.decide(pd.Timestamp(day), rows, positions, True)
    out = {"signals": len(sigs), "planned": [], "rejected": [], "trails": []}
    for sig in sorted(sigs, key=lambda x: ({"exit": 0, "trail": 1, "entry": 2}[x.kind], x.rank)):
        lot = lots.get(sig.symbol)
        if sig.kind == "trail":
            if sig.stop_price > lot["stop_price"]:
                db.update("lots", lot["id"], stop_price=sig.stop_price)
                db.event("TRAIL", lot["id"], symbol=sig.symbol, stop=round(sig.stop_price, 2))
                out["trails"].append(sig.symbol)
            continue
        if sig.kind == "exit":
            intent = make_intent(sig, lot["qty"])
        else:
            q, notional, why = size_entry(sig, budget, st.cash_eur, capital, strat.max_position_eur, risk_cfg)
            if q <= 0:
                out["rejected"].append(f"{sig.symbol}: sizing: {why}")
                db.event("RISK_DECISION", sig.symbol, approved=False, reason=f"sizing: {why}", limits_hash=risk_cfg["hash"])
                continue
            intent = make_intent(sig, q)
        st.orders_this_minute = 0                                # the executor sends orders ≥ 2 s apart
        try:
            dec = risk.check(intent, st, risk_cfg)
        except Exception as e:
            raise RiskEngineError(f"{type(e).__name__}: {e}") from e
        db.event("RISK_DECISION", intent.id, symbol=sig.symbol, kind=sig.kind, approved=dec.approved, reason=dec.reason,
                 qty=intent.qty, limit=intent.limit_price, notional=round(intent.notional_eur, 2), limits_hash=dec.limits_hash)
        if not dec.approved:
            out["rejected"].append(f"{sig.symbol}: {dec.reason}")
            continue
        row = dict(key=intent.id, intent_id=intent.id, role=sig.kind, strategy=strat.name, symbol=sig.symbol,
                   ticker=tickers[sig.symbol]["ticker"], session=next_day.isoformat(), qty=qty(intent.qty),
                   type=intent.order_type, reason=sig.reason)
        if sig.kind == "entry":
            row.update(price=price(intent.limit_price), stop_distance=sig.stop_distance)
            st.cash_eur -= intent.notional_eur
            st.deployed_eur += intent.notional_eur
            st.held_qty[sig.symbol] = intent.qty
        else:
            row.update(lot=lot["id"])
        execution.plan_order(db, **row)
        out["planned"].append(f"{sig.kind} {sig.symbol}")
    return out


# ---------- the engine ----------

class Engine:
    def __init__(self, broker, db, env: dict, settings: dict, inst: dict, risk_cfg: dict, tickers: dict):
        self.broker, self.db, self.env = broker, db, env
        self.settings, self.inst, self.risk_cfg, self.tickers = settings, inst, risk_cfg, tickers
        self.live = settings["live"]["strategies"]
        self.live_syms = [s for s, i in inst.items() if i["strategy"] in self.live]
        self.symbol_of = {t["ticker"]: s for s, t in tickers.items()}
        self.cal, self.cal_at, self.last_problems = {}, 0.0, []
        self.progress, self.next_sync, self.stopping = time.time(), 0.0, False
        self.lock = threading.Lock()

    def alert(self, text: str) -> None:
        notify.alert(self.db, self.env, text)

    def calendar(self) -> None:
        if time.time() - self.cal_at > 6 * 3600:
            ex = self.broker.exchanges()
            ids = {t["schedule"] for t in self.tickers.values()} | {REPORT_SCHEDULE}
            self.cal, self.cal_at = {i: sessions(ex, i) for i in ids}, time.time()

    def session_of(self, symbol: str, now: dt.datetime):
        return current(self.cal.get(self.tickers[symbol]["schedule"], []), now)

    # ---- one sync ----
    def sync(self, now: dt.datetime) -> None:
        self.calendar()
        problems = execution.sync(self.broker, self.db, self.alert)
        if problems:
            if self.last_problems:
                execution.halt(self.broker, self.db, "reconciliation mismatch: " + "; ".join(problems), self.alert)
            self.last_problems = problems
            return
        self.last_problems = []
        tripped = risk.is_tripped()
        if tripped:
            execution.cancel_entries(self.broker, self.db)
        live_open = {self.tickers[s]["ticker"]: self.session_of(s, now) for s in self.live_syms}
        execution.ensure_stops(self.broker, self.db, self.alert, lambda tk: live_open.get(tk) is not None)
        if self.broker.skew is not None and abs(self.broker.skew) > MAX_SKEW_S:
            self.alert(f"clock off by {self.broker.skew:+.1f} s vs the broker: no new orders until time sync fixes it")
            return
        ready = {tk: s[0].date().isoformat() for tk, s in live_open.items()
                 if s and s[0] + OPEN_DELAY <= now < s[1] - CLOSE_GUARD}
        if ready:
            execution.execute_pending(self.broker, self.db, self.alert, ready)
        if not tripped:
            for name in self.live:
                self.cycle(name, now)
        self.report_if_due(now)

    def cycle(self, name: str, now: dt.datetime) -> None:
        """The strategy's decision cycle, once per session, after its close."""
        syms = {s: i for s, i in self.inst.items() if i["strategy"] == name}
        sess = self.cal[self.tickers[next(iter(syms))]["schedule"]]          # one market per strategy (S1: Xetra)
        last = last_closed(sess, now)
        if last is None or now < last[1] + CYCLE_DELAY:
            return
        day = last[0].date()
        if self.db.events("type='CYCLE' AND entity=? AND json_extract(payload, '$.session')=?", name, str(day)):
            return
        nxt = next_after(sess, last[1])
        if nxt is None:
            self.alert(f"{name}: the calendar has no session after {day}")
            return
        if now >= nxt[0] + LATE_LIMIT:
            self.db.event("CYCLE", name, session=str(day), result="missed (engine was down)")
            self.alert(f"{name}: decision cycle for {day} missed (engine was down)")
            return
        strat = STRATEGIES[name]()
        if not strat.is_check_day(pd.Timestamp(day), pd.Timestamp(nxt[0].date())):
            self.db.event("CYCLE", name, session=str(day), result="not a check day")
            return
        data.refresh(syms, day, self.settings["periods"]["data_start"], log=lambda m: None)
        panel = data.load_panel(self.inst, name)
        bad = suspect(panel, day)
        if bad:
            self.stale(name, day, nxt, bad, now)
            return
        closes = {s: float(df["close"].iloc[-1]) for s, df in panel.items()}
        m = mark(self.db, self.risk_cfg["capital_cap_eur"], closes)
        if self.drawdown_hit(m):
            return
        tradable = {s for s in syms if next_after(self.cal[self.tickers[s]["schedule"]], now)}
        try:
            out = decide(self.db, strat, panel, day, nxt[0].date(), self.risk_cfg, self.settings["budgets_eur"][name],
                         self.tickers, m["day_change"] <= -self.risk_cfg["max_daily_loss_pct"] * self.risk_cfg["capital_cap_eur"],
                         tradable)
        except RiskEngineError as e:
            execution.halt(self.broker, self.db, f"risk engine error: {e}", self.alert)
            return
        self.db.event("CYCLE", name, session=str(day), result="done", **out)
        if out["planned"] or out["rejected"]:
            self.alert(f"{name} {day}: planned {out['planned'] or 'nothing'}; rejected {out['rejected'] or 'nothing'}")

    def stale(self, name: str, day: dt.date, nxt, bad: list[str], now: dt.datetime) -> None:
        """Wait for the data until shortly before the next open, then skip the cycle (docs/05 §10)."""
        if now < nxt[0] - dt.timedelta(minutes=15):
            if not self.db.events("type='STALE_DATA' AND entity=? AND json_extract(payload, '$.session')=?", name, str(day)):
                self.db.event("STALE_DATA", name, session=str(day), symbols=bad)
            return
        prev = self.db.events("type='CYCLE' AND entity=?", name)
        self.db.event("CYCLE", name, session=str(day), result="skipped: stale data", symbols=bad)
        self.alert(f"{name}: cycle for {day} skipped, stale or suspect data: {'; '.join(bad)}")
        held = self.db.select("lots", "status='OPEN' AND strategy=?", name)
        if held and prev and prev[-1]["payload"]["result"].startswith("skipped: stale"):
            execution.halt(self.broker, self.db, f"{name}: stale data on two cycles in a row with positions held", self.alert)

    def drawdown_hit(self, m: dict) -> bool:
        cap = self.risk_cfg["capital_cap_eur"]
        if m["equity"] <= m["peak"] - self.risk_cfg["max_drawdown_pct"] * cap:
            execution.halt(self.broker, self.db, f"drawdown: equity €{m['equity']:.2f} vs peak €{m['peak']:.2f}", self.alert)
            return True
        return False

    # ---- daily report ----
    def report_if_due(self, now: dt.datetime) -> None:
        last = last_closed(self.cal.get(REPORT_SCHEDULE, []), now)
        if last is None or now < last[1] + dt.timedelta(minutes=30):
            return
        if not self.db.events("type='REPORT' AND json_extract(payload, '$.session')=?", str(last[0].date())):
            self.daily_report(last[0].date())

    def forward(self, day: dt.date) -> list[str]:
        """The P1 implementation check: the backtest over the live period must hold what the engine holds.
        Shadow strategies (S2) get their whole book from the same backtest: decisions only, no orders."""
        start = self.settings["live"]["start"]
        if str(day) < start:
            return []
        lines = ["| Strategy | Role | Backtest trades | Backtest P&L | Backtest holds | Engine holds | Check |", "|---|---|---|---|---|---|---|"]
        for name in self.live + self.settings["live"].get("shadow", []):
            syms = {s: i for s, i in self.inst.items() if i["strategy"] == name}
            data.refresh(syms, day, self.settings["periods"]["data_start"], log=lambda m: None)
            budget = self.settings["budgets_eur"][name]
            res = backtest.run(STRATEGIES[name](), data.load_panel(self.inst, name), self.inst, budget, start, str(day),
                               self.settings["costs"], self.risk_cfg)
            pnl = res.equity.iloc[-1] - budget if len(res.equity) else 0.0
            if name in self.live:
                held = sorted(l["symbol"] for l in self.db.select("lots", "status='OPEN' AND strategy=?", name))
                check = "match" if held == res.held else "**differs**"
                lines.append(f"| {name} | demo | {len(res.trades)} | €{pnl:+.2f} | {', '.join(res.held) or '-'} | {', '.join(held) or '-'} | {check} |")
            else:
                lines.append(f"| {name} | shadow | {len(res.trades)} | €{pnl:+.2f} | {', '.join(res.held) or '-'} | (no orders) | - |")
        return lines

    def daily_report(self, day: dt.date) -> str:
        marks = {self.symbol_of.get(execution.ticker_of(p), ""): p.get("currentPrice") for p in self.broker.positions()}
        m = mark(self.db, self.risk_cfg["capital_cap_eur"], {s: v for s, v in marks.items() if v})
        self.drawdown_hit(m)
        kill = risk.state()
        lots = self.db.select("lots", "status='OPEN'")
        orders = self.db.select("orders", "substr(updated, 1, 10)=? OR status='PENDING'", str(day))
        events = [e for e in self.db.events("substr(ts, 1, 10)=?", str(day))
                  if e["type"] in ("ALERT", "KILL", "CYCLE", "STALE_DATA", "ERROR", "LOT_CLOSED", "TRAIL")]
        recon = self.db.events("type='RECONCILE'")[-1:] or [{"payload": {"ok": None}}]
        try:
            fwd = self.forward(day)
        except Exception as e:                                   # the report must not fail on a data hiccup
            fwd = [f"Forward check failed: {type(e).__name__}: {e}"]
        dd = 1 - m["equity"] / m["peak"]
        L = [f"# Daily report {day} (demo)", "",
             f"- Kill switch: **{'TRIPPED' if kill['tripped'] else 'off'}**" + (f" ({kill['reason']}, by {kill['by']}, {kill['ts']})" if kill["tripped"] else ""),
             f"- Book: equity €{m['equity']:,.2f} of the €{self.risk_cfg['capital_cap_eur']:,} cap; day change €{m['day_change']:+.2f}; "
             f"peak €{m['peak']:,.2f}; drawdown {dd:.1%}",
             f"- Last reconciliation: {'OK' if recon[0]['payload']['ok'] else recon[0]['payload']}",
             f"- Limits hash `{self.risk_cfg['hash']}`, settings hash `{self.settings['hash']}`", "",
             "## Open lots", ""]
        L += ["| Lot | Symbol | Qty | Entry | Stop | Mark |", "|---|---|---|---|---|---|"] + [
            f"| {l['id'][:8]} | {l['symbol']} | {l['qty']:.4f} | {l['entry_price']:.2f} | {l['stop_price']:.2f} | {marks.get(l['symbol']) or '-'} |"
            for l in lots] if lots else ["None."]
        L += ["", "## Orders (updated today, or pending)", ""]
        L += ["| Order | Role | Symbol | Qty | Type | Price | Status | Filled | Fill price |", "|---|---|---|---|---|---|---|---|---|"] + [
            f"| {o['key'][:14]} | {o['role']} | {o['symbol']} | {o['qty']:.4f} | {o['type']} | {o['price'] or '-'} | {o['status']} "
            f"| {o['filled_qty'] or 0:.4f} | {o['fill_price'] or '-'} |" for o in orders] if orders else ["None."]
        L += ["", "## Events", ""] + ([f"- {e['ts'][11:16]} UTC **{e['type']}** {e['entity']} {json.dumps(e['payload'], default=str)[:300]}"
                                        for e in events] or ["None."])
        L += ["", f"## Forward check: backtest over the live period (from {self.settings['live']['start']})", ""] + (fwd or ["Not started yet."])
        out = REPORTS_DIR / "daily" / f"{day}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(L) + "\n", encoding="utf-8")
        self.db.event("REPORT", session=str(day), path=str(out), **m)
        notify.telegram(self.env, f"TradeBot daily {day}: equity €{m['equity']:,.2f} (day €{m['day_change']:+.2f}, DD {dd:.1%}), "
                                  f"{len(lots)} lots, kill switch {'TRIPPED' if kill['tripped'] else 'off'}. Report: {out.name}")
        return str(out)

    # ---- loop ----
    def _beat(self) -> None:
        while not self.stopping:
            with self.lock:
                if not self.stopping and time.time() - self.progress < HANG_S:
                    beat("running")
            time.sleep(BEAT_S)

    def step(self) -> None:
        now = dt.datetime.now(dt.UTC)
        try:
            self.sync(now)
            notify.ping(self.env)
        except Exception as e:
            self.db.event("ERROR", error=repr(e), trace=traceback.format_exc()[-3000:])
            self.alert(f"sync failed: {type(e).__name__}: {str(e)[:200]}")
            notify.ping(self.env, fail=True)
        open_now = any(self.session_of(s, now) for s in self.live_syms)
        self.next_sync = time.time() + (SYNC_OPEN_S if open_now else SYNC_CLOSED_S)

    def loop(self) -> None:
        STOP_FILE.unlink(missing_ok=True)
        beat("running")
        threading.Thread(target=self._beat, daemon=True).start()
        try:
            while not STOP_FILE.exists():
                self.progress = time.time()
                if time.time() >= self.next_sync:
                    self.step()
                time.sleep(TICK_S)
        finally:
            with self.lock:
                self.stopping = True
                beat("stopped")
            STOP_FILE.unlink(missing_ok=True)
            self.db.event("ENGINE_STOP")
