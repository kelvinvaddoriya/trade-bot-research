# Claude — docs vs reality, open positions, restart hazards (round 1, 2026-11-25)

## Summary
1. **HIGH: the live system isn't in git.** About 700 changed lines across 20 tracked files, plus ~30 untracked files (S3/S4, the 18-stock universe, the qty-precision fix, Incident 3, `docs/3paperresearch.md`, `docs/guide/`, the daily reports from 09-29 to 10-05), have sat uncommitted in `D:\TradeBot` since early October. The last commit is 42792f1 (2026-09-29). One bad `git checkout` or disk failure loses two months of work. The worktree `Trade-Bot-Research/` is on that old commit and misled this round's first launch.
2. **HIGH: the 8 unprotected demo positions have lost money that the stops would have capped.** Five of eight are now **below their stop price** (Yahoo closes, 2026-11-25). Unrealised P&L is about **−€64**; with the stops kept, it would have been about **−€8**. The shutdown cost ≈ €55, 5.5 % of the €1,000 cap. Demo money only, but it's exactly the failure the design forbids ([05 §4](../../../docs/05-risk-and-safety.md) "keeps the protective stop orders").
3. **HIGH: a restart hazard.** On restart the engine "places new stops at each lot's stop price" (docs/10, Incident 3). For SXR8, EXW1, IS3N, SXRV and IFX that price is now *above* the market. A sell stop above the market either gets rejected, which can count toward the 3-rejection kill rule, or triggers immediately as a market sell. Either way it must be an explicit, decided exit, not an accident. Codex is tracing the code path.
4. **MED: strategy state is stale.** S4's 5-day holds (ALV, BMW) are 7 weeks overdue, and S2's BAYN time stop has passed. The monthly S1 checks on 10-30 were missed, and 11-27 will be too. A restart will fire a burst of exits and decisions at once. The forward check (live vs backtest) is broken from 10-06 on and has to be restarted, not continued.
5. **MED: the status lines are stale.** README (2026-09-27), docs/07 status (2026-09-27), README D5 (S1/S2 only) and docs/10 "What happens next" (still the 09-30/10-01 plan) all predate S3/S4 and the shutdown. `working_structure.md` (10-03) predates Incident 3.
6. **MED: a doc gap.** Nothing covers a *planned* shutdown. docs/05 covers HALT and FLATTEN, but on 10-06 a third, undocumented action was taken (cancel every stop, keep the positions). Proposal below: a planned shutdown keeps the broker-held GTC stops, or flattens; never both off.
7. **LOW:** the kill switch still holds the 10-06 watchdog reason. On restart the reset should name the new cause (migration), so the kill log stays readable.

## Findings

| # | Claim | Evidence | Sev | Conf |
|---|---|---|---|---|
| F1 | Current system uncommitted | `git status --short` in `D:\TradeBot`: 20 `M`, ~30 `??`; `git log -1` = 42792f1 (2026-09-29) | HIGH | certain |
| F2 | 8 open lots, all without stops | `data/demo.db` (read-only): `lots` with status OPEN: ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV, IFX; docs/10 Incident 3, step 2 | HIGH | certain |
| F3 | 5 lots now below their stop | Yahoo chart API, daily closes to 2026-11-25 (table below) | HIGH | high: one source, but the paths are gradual, with no split events; ^NDX −16 % from 10-05 confirms the move |
| F4 | Restart re-places stops at the old price | docs/10 Incident 3 ("place new stops at each lot's stop price") | HIGH | high (the code path is being traced by Codex) |
| F5 | Overdue time exits | S4 hold = 5 sessions (docs/03 S4), entries 10-01/10-02; S2 time stop (docs/03) | MED | high |
| F6 | Stale status lines | README:5, docs/07:15, docs/10 "What happens next" | MED | certain |
| F7 | No planned-shutdown policy | docs/05 §4 lists only HALT/FLATTEN; docs/04 CLI table has no "shutdown" | MED | certain |

**Positions on 2026-11-25** (prices: Yahoo `.DE` closes; quantities and stops: ledger):

| Lot | Strategy | Qty | Entry | Stop | Last | P&L € | vs stop |
|---|---|---|---|---|---|---|---|
| ALV | S4 | 0.1545 | 410.80 | 392.71 | 453.50 | +6.6 | ok |
| BAYN | S2 | 1.447 | 44.81 | 41.36 | 50.68 | +8.5 | ok |
| BMW | S4 | 1.104 | 54.78 | 50.25 | 55.24 | +0.5 | ok |
| SXR8 | S1 | 0.291 | 737.12 | 720.66 | 690.04 | −13.7 | **below** |
| EXW1 | S1 | 2.413 | 62.45 | 60.43 | 59.61 | −6.9 | **below** |
| IS3N | S1 | 2.067 | 48.85 | 46.83 | 40.72 | −16.8 | **below** |
| SXRV | S1 | 0.083 | 1564.60 | 1507.64 | 1314.60 | −20.8 | **below** |
| IFX | S3 | 0.906 | 64.39 | 58.87 | 40.90 | −21.3 | **below** |
| **Total** | | | | | | **≈ −63.9** | stops kept: ≈ −8 (before gap slippage) |

## Proposed edits

### P-claude-1: README status line
- File: README.md (the Status line)
- Change: "**Status (2026-11-25): paused since 2026-10-06** until the engine moves to an EU VPS. P1 ran 2026-09-28 → 10-06 with four demo strategies (S1 trend; S2 pullback, S3 breakout and S4 random control as demo-only experiments) on 6 ETFs and 18 German stocks. It stopped after the third out-of-memory incident on the laptop. 8 demo positions are open without stops (see build log, Incident 3 and the 2026-11-25 research round). Next: VPS, a restart runbook, and the P1 gate run again from zero."
- Why: F6. Risk if wrong: none.

### P-claude-2: README decision D5
- File: README.md (Key decisions, D5)
- Change: add "Since 2026-09-30, demo only: S2, S3 (Donchian 20/10) and S4 (random entries, the control group) trade 18 German large caps as experiments. None of them can go live without passing every gate."
- Why: F6.

### P-claude-3: roadmap status
- File: docs/07-roadmap.md (the Status line)
- Change: replace it with "**Status (2026-11-25): P1 paused, not passed.** The 2-week clean-run gate was never completed: there were three laptop incidents in 9 days. The gate restarts from zero on the VPS." Mark the 09-30/10-01 rows of docs/10's "What happens next" as history.
- Why: F6.

### P-claude-4: planned-shutdown policy
- File: docs/05-risk-and-safety.md §4 (kill switch)
- Change: add "**Planned shutdown (engine off for more than a day):** choose one: (a) **keep the broker-held GTC stops** (the default; they work without the engine, and the reconciler books any stop fill on restart), or (b) FLATTEN. Never leave positions open with no stops. Lesson from 2026-10-06: cancelling all stops cost ≈ €55 of demo money in 7 weeks (research round 2026-11-25)."
- Why: F2/F3/F7. Risk if wrong: a stop fills while the engine is off, and the ledger is behind until the next reconcile, which the reconciler is built to handle.

### P-claude-5: restart rule for stops through the market
- File: docs/04-architecture.md (order lifecycle / restart)
- Change: "On start, for each open lot without a live stop: if the last price is **at or below** the lot's stop price, plan a **market exit at the next open** (journaled `STOP_THROUGH_ON_RESTART`), not a stop order. Otherwise place the GTC stop. Overdue time exits (S2 time stop, S4 5-day hold) follow the same path."
- Why: F3/F4/F5. Needs Codex's trace to confirm what the code does today; a code change follows the vote.

## Open questions for round 2
1. (Codex) What does `execution.py` do today when a restart re-places a sell stop above the market? Does a T212 rejection count toward the kill rule?
2. (Mistral) Does Trading 212 accept a sell stop above the market (immediate trigger) or reject it? Docs, and the demo behaviour if known.
3. (Antigravity) Should the forward-check clock restart, or should the 10-06 → restart gap be excluded and the series stitched? Which is more honest?
4. (Owner) Commit the current working tree to a branch now? (It's the owner's decision under handbook rule 4; Claude recommends it.)
5. (All) Keep, flatten, or exit-by-rule the 8 lots at restart?

## Sources
- `D:\TradeBot\data\demo.db` (read-only, table `lots`), `data/KILL`, `data/STOP`; read 2026-11-25.
- Yahoo Finance chart API, `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>.DE`, daily and weekly bars, fetched 2026-11-25. One source; cross-check with T212 positions at restart.
- docs/03, 04, 05, 07, 10 and README in `D:\TradeBot` (working tree, 2026-11-25).
