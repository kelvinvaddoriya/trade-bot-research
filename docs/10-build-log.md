# 10 — Build log

One entry per backlog step ([07](07-roadmap.md)): what was built, decisions made, how to run it, and the results. Newest phase first; steps in order within a phase.

## P1: Shadow & demo engine (built 2026-09-27)

The owner asked to start P1. The whole P1 deliverable list is built and tested. Five of the eight P1 drills passed against the Trading 212 practice account on a closed-market Sunday. What's left is waiting: the 2-week unattended run, and the first real fills (S1's first orders go out on Thursday 2026-10-01).

### Owner decisions (defaults I set on 2026-09-27; the owner can override any of them)

The three P0 questions ([step 11](#step-11-backtest-results-and-the-p0-gate)) blocked P1, so I took the defaults that follow from earlier owner decisions:

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | S2's role | **Shadow only.** Its decisions come from the backtest engine run over the live period; it places no orders. | S2 failed its gate, so it doesn't trade. The desk reviews S2 entries only (resolved item 4), so P2 needs S2's decisions to exist. |
| 2 | S2's €400 budget | **Stays unused.** S1 keeps its €600. | S1 then runs exactly as backtested, so the forward check compares like with like. |
| 3 | EU runtime data | **Yahoo**, with a freshness check against Trading 212's calendar | P1's budget is €0 (resolved item 3). A paid EU source comes before real money. |

### Built

| Module | What it does |
|---|---|
| `store.py` | SQLite `data/demo.db` in WAL mode, autocommit: append-only `events`, the `orders` ledger (PENDING → SUBMITTING/UNKNOWN → broker status) and `lots` |
| `execution.py` (rewritten) | The order manager. **`submit()`** is the submit-once protocol on the ledger: journal first, one POST, a timeout or 5xx means UNKNOWN, then two lookups 10 s apart in open orders *and* history (a filled market order has already left the open list). A lost order is resubmitted once, after one more lookup; lost twice trips the kill switch. **`sync()`** mirrors every order into the ledger (entry fills open lots, stop and exit fills close them, with P&L) and reconciles open orders and positions. **`ensure_stops()`** keeps exactly one GTC stop per lot at its price and size. **`execute_pending()`** sends at the open. **`halt()`** writes the kill file first, then cancels entries and keeps stops. |
| `live.py` | The engine loop (20 s ticks; syncs every 2 min in session, 10 min outside), the decision cycle once per session after the close, the heartbeat thread, the watchdog check, equity marks (drawdown → HALT, daily loss → no entries), the daily report |
| `notify.py` | Alerts to the console, the journal and Telegram (at most once an hour per text); healthchecks.io pings (`/fail` when a sync fails) |
| `trading212.py` | Calendar from the exchange schedules (`sessions`, `current`, `last_closed`, `next_after`); `history()`; clock skew from the `Date` header; rate-limit retries (see the drill 1 bug) |
| `risk.py` | Check 3 (the market has a next session); the kill file is read at call time, so tests and other processes can point at it; backtests skip it by mode |
| `data.py` | `refresh()`: full history up to the session that just closed. `fetch_yahoo` used to drop today's bar, which would have hidden the session the cycle is deciding on. |
| `cli.py` | `run`, `stop`, `watchdog`, `status`, `kill [--flatten]`, `reset-kill`, `reconcile`, `report` |
| `ops/install-tasks.ps1` | Laptop setup for 24/7 (docs/09 §6): power plan, hourly time sync, Task Scheduler (engine at boot with restart, watchdog every minute, nightly backup). **For the owner to run**, since it changes system settings. |
| `config/settings.toml` | `mode = "demo"`; `[live]`: start date 2026-09-28, S1 trades, S2 in shadow |

**Removed:** the `demo-trade` command and its JSONL journal. The engine does its round trip through the ledger now, and a second path to the broker would break "one door to the broker".

### Design decisions

| Decision | Why |
|---|---|
| **Orders go out at the open + 2 min, not queued overnight** ([04 §3](04-architecture.md#3-runtime-cycle)) | Nothing but stops rests at the broker overnight; a crash between close and open leaves nothing half-sent; a night-time kill has no queued entries to chase. It also sidesteps two untested broker behaviours: whether a DAY order placed after the close survives into the next session, and whether stops can be placed while the market is closed. |
| **The calendar comes from Trading 212's schedules**, not `exchange_calendars` | The venue's own sessions, about three weeks back and ahead, with holidays and half days. One dependency fewer. The US regular session ends at `AFTER_HOURS_OPEN`. |
| **A mismatch must show on two syncs in a row** before HALT | Order history and positions update a moment apart after a fill, so a single mismatch can be a fill in flight. Orders that left the open list but aren't in history yet are "limbo": their ticker is skipped for 10 minutes, then counted as a mismatch. |
| **Stops are placed or replaced only in session** | Nothing can trigger overnight. A trail decided at the close (cancel, then place) takes effect at the next open. |
| **The heartbeat thread beats only while the loop makes progress** | A dead engine goes stale in 60 s (the watchdog catches it within 2 minutes); a hung loop stops the beat after 10 minutes. |
| **`stop` command** | Stopping the engine any other way looks like a crash and trips the kill switch (by design). `stop` exits cleanly within 20 s. |
| **Forward check in the daily report** | P1 tests the implementation, not the edge ([06 §4](06-backtesting.md#4-statistical-sanity)). The backtest over the live period must hold the same symbols the engine holds; a difference is flagged. S2's shadow book comes from the same run. |
| **Two engines can't run at once** | `run` refuses while another heartbeat is fresh. Two engines would send duplicate orders. |

### Drills ([05 §11](05-risk-and-safety.md#11-drills-all-must-pass-before-each-promotion))

| # | Drill | Unit test | Against the demo API (2026-09-27, market closed) |
|---|---|---|---|
| 1 | Manual kill with orders open | ✅ entries cancelled, stop kept, no new entries | ✅ The entry order was cancelled at the broker and the ledger shows CANCELLED. After a restart the engine stayed halted. **Found a bug, fixed below.** *Stops kept*: ✅ 2026-09-28 with a real position (below). |
| 2 | Kill the engine process | ✅ | ✅ Killed at 16:19:08 UTC; the watchdog tripped at 16:20:10 (62 s, so within 2 minutes when run every minute) |
| 3 | Network cut during a submit | ✅ | ✅ Simulated at the socket. *Sent, answer lost:* found by lookup and adopted, 1 order at the broker. *Lost before sending:* two empty lookups, then exactly one resubmit. The lookup also ignored the identical-looking order already claimed by the first case. |
| 4 | Stale data | ✅ waits until 15 min before the next open, then skips with an alert | ⏳ Unit test only; Yahoo's late closes (see the P1 preview) will likely trigger it for real |
| 5 | Manual order in the account | ✅ | ✅ The mismatch was seen once, then HALT on the next sync; the unknown buy order was cancelled |
| 6 | Out-of-bounds limit | ✅ (P0) | ✅ `run` refused: `capital_cap_eur=5000 outside [100, 1000]`; `risk.toml` restored |
| 7 | LLM failure paths | — | P2 (no desk yet) |
| 8 | Delete a protective stop | ✅ replaced, with an alert | ✅ 2026-09-28: the owner deleted it in the app; replaced within one sync, with a Telegram alert (below) |

Plus a full-loop engine test: month-end close → planned entry → sent at the open → fill → stop at fill − 3×ATR → stop-out closes the lot → reconciliation OK.

**Bug found by drill 1: rate limits across processes.** `kill` runs as its own process. Its `GET /equity/orders` hit HTTP 429 because the drill had just made the same call, and the adapter's single retry at `x-ratelimit-reset` got a second 429. The process crashed after tripping the switch but before cancelling the entry. The kill switch had been written first, so trading was halted anyway, and the engine's next sync cancelled the entry (it cancels entries on every sync while tripped). **Fix:** up to 3 retries on 429, each waiting for `retry-after` or the reset plus 1 s. This is safe even for order POSTs, because a 429 means nothing was executed. A regression test covers it.

**Findings:**

| Finding | Consequence |
|---|---|
| Rejected requests seem to count against the rate window (1 per 5 s for the order list), and responses carry `retry-after` | The engine, watchdog and CLI share one key, so every client must wait with a margin (fixed above) |
| Open orders carry `createdAt` (e.g. `2026-09-27T19:21:20.788+03:00`), `side`, `type`, `quantity`, `limitPrice`, `timeInForce: DAY` | Enough to match an order whose response was lost (drill 3) |
| Clock skew vs the broker: −0.4 to −0.8 s | Within the 2 s limit. Windows syncs only weekly by default, so the setup script makes it hourly. |
| Xetra opens at 07:00:03 UTC in Trading 212's schedule | Orders go out at open + 2 min, after the opening auction |

**Smoke run (2026-09-27 16:18 UTC):** the engine started (limits `eff24a142253`, code `9bc8a4ffec1a`), reconciled OK and recorded Friday's cycle as "not a check day". It also wrote `reports/daily/2026-09-25.md`, which is empty because the demo run starts on 2026-09-28. The journal has every drill's events.

**Tests:** 81, up from 61:
- `test_execution.py` (14): submit-once, fills, stops, exits, reconciliation and HALT against a stateful fake Trading 212.
- `test_live.py` (7): the full loop, check days, drills 2, 4 and 5, drawdown.
- Adapter tests: the calendar, `wait_final` reading history, 429 retries.
- `conftest.py` keeps every test away from the real `data/KILL`.

### Demo round trip, drills 1 and 8, and the first incident (2026-09-28)

The owner asked for a demo trade while the market was open. A helper script sent a €25 SXR8 buy through the risk
engine and wrote it into the ledger as a PENDING order, and left the rest to the running engine, the only process
that sends orders. Nothing was sent from outside the engine.

| Time (CEST) | What happened |
|---|---|
| 14:18 | Risk engine APPROVED: buy 0.0338 SXR8 at limit €738.11 (live price €730.80 + 1 %) = €24.95. The engine sent it at its next sync. |
| 14:20 | **Filled at €731.80.** The same sync opened the lot and placed a **GTC stop at €709.88** (fill − 3 %), which Trading 212 accepted. |
| 14:21 | **Drill 1, second half:** `kill` with the position open. After the engine's next sync the stop was still at the broker, the position was intact, and nothing new was sent. The kill switch was reset. |
| 14:25 | **Drill 8:** the owner deleted the stop in the Trading 212 app. |
| 14:26 | The engine saw it as CANCELLED in history, alerted on Telegram ("protective stop for SXR8 disappeared at the broker: replacing it") and had a new stop at €709.88 resting one second later. Reconciliation stayed OK. |
| 14:28 | Exit planned: the engine cancelled the stop, then sent a market sell. |
| 14:30 | **Sold at €731.74.** Lot closed, P&L −€0.002. Broker flat, reconciliation OK. |

**Findings:**

| Finding | Consequence |
|---|---|
| Trading 212 accepts `GOOD_TILL_CANCEL` stops from the API during the session | The protective-stop design works as specified |
| The API reports sell orders with a **negative** quantity (−0.0338) plus `side: SELL` | The code already compares absolute quantities |
| A demo market order was still NEW right after submission and FILLED by the next sync (within 2 minutes) | Exits confirm at the following sync, as designed |

**Incident: the engine didn't come back after a restart (14:31–14:41).** I restarted the engine to load a small fix
(UTF-8 console output, below). It refused to start: `clock off by -7.2 s vs the broker`. The clock was fine
(−0.003 s against time.windows.com, −0.14 s against Trading 212 a minute later).

- **Root cause:** the laptop was out of memory. Only 0.4 GB of 7.9 GB RAM was free and 21.5 GB was committed (Chrome, the Claude app, Acrobat), so Windows was paging hard. A fresh Python process loading pandas crawled. One watchdog run hung until Task Scheduler killed it after 5 minutes, and the next runs were refused while it hung (`0x800710E0`).
- **How that became a false clock alarm:** the engine's first request to the broker took about 14 s. The clock skew is estimated from the middle of the round trip, so a slow round trip puts the estimate seconds off.
- **Three weaknesses it exposed, all fixed:**
  1. **Clock sample from a slow request.** The skew is now measured only from round trips under 1 s. The start-up check takes up to 3 samples, and an unmeasured skew doesn't block a start (every sync keeps checking). Test added.
  2. **No restart and no alert.** Task Scheduler's "restart on failure" only covers a task that fails to launch, not a process that exits with an error, so the engine stayed down. The only signal was healthchecks.io's missed pings. Now a refused start sends a Telegram alert, and `ops/install-tasks.ps1` starts the engine every 5 minutes as well as at boot (a start is ignored while it runs).
  3. **A heavy watchdog.** It went through the CLI, which imports pandas. It is now `watchdog.py`, standard library only, reached straight from `python -m tradebot watchdog`: 1.0 s instead of 8 s even with plenty of memory. Its time limit is now 2 minutes. A test checks that it doesn't import pandas.
- **Also fixed:** the CLI now writes UTF-8 to `data/engine.log`. On Windows, redirected output used cp1252, and an alert containing a character outside it (for example from a broker error body) would have crashed that sync.
- **Downtime:** 10 minutes during a session, with nothing pending. The engine was back at 14:41 on the old code and restarted at 14:44 on the fixed code.
- **Lesson for the hosting decision ([09](09-hosting.md)):** the laptop's real risk is memory pressure from personal use, not CPU. Keep the browser and other heavy apps light while the engine runs, or move to the VPS sooner.

### Incident 2: the laptop froze overnight and rebooted (2026-09-29)

| Time (CEST) | What happened |
|---|---|
| 02:03 | Last successful sync. Flat, nothing pending. |
| 02:07 onwards | The laptop was starved: Windows services timed out after 3 minutes, system components failed to register in time, and the per-user background-download queue (BITS) was full with 60 stuck Firefox updater jobs. Windows flagged a memory leak in Acrobat (02:11), then "suspected deadlock" (03:16, 09:55, 11:47). |
| 02:03–12:12 | The engine journaled nothing, not even errors. The watchdog couldn't trip either: a machine that can't start processes can't run it. Only the external dead-man's switch (healthchecks.io) could notice, which is why it exists. |
| 05:24–11:31 | Defender's network inspection service (NisSrv) and explorer.exe crashed repeatedly |
| 12:12–14:55 | The engine was running again, but every sync failed with WinError 10053 / SSL EOF ("connection aborted by the software in your host machine"), consistent with the crashing network inspection service. Each failure alerted on Telegram (at most once an hour per text). |
| 12:56 | Windows flagged a memory leak in Dropbox |
| 14:26 | explorer.exe hung |
| 14:58 | Hard reboot ("rebooted without cleanly shutting down first") |
| 15:01 | The watchdog found the heartbeat from before the crash and tripped the kill switch, as designed |
| 15:02 | Task Scheduler started the engine at boot. Reconciliation OK, flat. It holds in halted mode until a person resets the kill switch. |

**Impact:** none on money. No positions or orders were open, and the demo book is at €1,000.00.
**What worked:** the heartbeat, the watchdog trip after the reboot, the boot start, startup reconciliation, and the sticky kill switch (no automatic reset).
**What this shows:** the laptop, not the engine, is the weak part. Memory leaks in desktop apps (Acrobat, Dropbox), crashing Defender components and a stuck Firefox updater took the whole machine down for 13 hours. The P1 gate needs 2 weeks of clean unattended runs; this laptop hasn't managed 2 days.

### Demo experiments: four strategies, 18 stocks (2026-09-30)

The owner asked for more trading: "take multiple trades, fail-pass and learn … take different approaches, different stocks". Demo money is the right place for that, so the rules changed for demo only. The guardrails didn't: the €1,000 cap, the risk engine, protective stops and the kill switch all apply as before, and no strategy can go live without passing the gates in [06 §7](06-backtesting.md#7-promotion-gates).

| Strategy | Approach | Universe (live) | Budget | Gate status |
|---|---|---|---|---|
| S1 trend | Trend-following, monthly | 6 UCITS ETFs | €600 (unchanged) | Passed |
| S2 pullback | Mean reversion (RSI(2) < 10 in an uptrend) | 18 German stocks | €140 | Failed in P0; now trades as an experiment |
| S3 breakout | Donchian 20/10 breakout (new, [03](03-strategies.md#s3-donchian-breakout-on-stocks-experiment-2026-09-30)) | same 18 | €130 | Never gated: experiment |
| S4 monkey | Random entries, 5-day hold (new): the control group | same 18 | €130 | Control |

**Changes:**
- **12 more German large caps**, all Xetra in EUR, mapped by ISIN (all 32 instruments map):
  - Adidas, Infineon, Deutsche Bank, Mercedes-Benz (`DAId_EQ`), BASF and Rheinmetall;
  - Airbus, DHL (`DPWd_EQ`), Bayer, E.ON, Deutsche Börse and Siemens Energy.

  US names stay in backtests only: their orders would need USD prices and a second market's cycle.
- **An instrument can serve several strategies** (`strategy` is a list in `instruments.toml`).
- **One book:**
  - The risk engine now sees every strategy's open lots and planned entries for the capital cap and the position count; cash still comes from each strategy's budget.
  - **A stock held or planned by one strategy is off-limits to the others**, so each ticker has one owner and one protective stop.
- **Live positions count days held**, which S2's time stop and S4's 5-day hold need.
- **Stale data per stock:** S1 still skips its whole cycle when any ETF's bar is missing, because its weights span all six. The stock strategies wait for late data until 15 minutes before the next open, then decide without the late or suspect symbols, with an alert.
- **Limits** (hash `1e6f13262ebd`): at most 12 positions (was 9) and 20 orders a day (was 10).
- **The daily report** now has one results row per strategy: open lots, closed trades, winners and realised P&L.
- **`stop --until HH:MM`** for planned pauses (used for the owner's interview on 2026-09-29).

**Backtests before any demo money (2007–2019, all stocks including US names in EUR; single runs, in-sample):**

| Strategy | CAGR | at 2× costs | Sharpe | Max DD (of its budget) | Trades | 2025 → now |
|---|---|---|---|---|---|---|
| S2 pullback | +1.5 % | −6.0 % | 0.17 | −41 % | 812 | +12.0 % |
| S3 breakout | +5.0 % | +3.4 % | 0.35 | −47 % | 236 | +31.5 % (34 trades) |
| S4 monkey | +1.4 % | −12.2 % | 0.16 | −54 % | 1,121 | +9.3 % |

- **First lesson, before a single trade:** S2's pullback rule does about as well as random entries with the same size and stops. Its "edge" looks like chance.
- S3 beats the monkey and survives doubled costs, but with a Sharpe of 0.35 (± ~0.3) it isn't significant.
- The drawdowns look large because each sleeve is small: a €65 position is half of a €130 budget. In euros, S4's worst drawdown was about €70 over 13 years.
- The live run will show whether any of this holds up.

**Dry run** (the real code on real data for 2026-09-29, against a copy of the ledger, nothing sent):
- S2 would have bought BASF (€91, stop distance 5.5 %).
- S4 would have picked Munich Re and Siemens (€65 each).
- S3 had no breakout.

**Deployed** at 13:18 CEST with a clean stop and the scheduled restart: limits `1e6f13262ebd`, code `9b74d98887a5`. Each new strategy logged one "missed" cycle for 2026-09-29, since it wasn't live then, and sent one alert each: first-start noise.

**Tests:** 90, including S3 signals and causality, the monkey's replayable picks and time exit, the shared book with one owner per stock and days held, and deciding without a late stock at the deadline.

### First experiment orders, and the quantity-precision trip (2026-10-01)

The laptop's lid was closed overnight. The engine kept running (lid set to "do nothing" on AC): 307 clean reconciliations, no gaps.

| Time (CEST) | What happened |
|---|---|
| 09-30 17:51 | The first real cycles. **S1** (month-end) planned SXR8 €210, EXW1 €160, SXRV €129 and IS3N €101; EUNH and 4GLD weren't in trend. **S4** picked Deutsche Telekom and Allianz (€65 each). S2 and S3 had no signal. |
| 10-01 09:04 | Orders sent. Accepted: SXR8 0.2834, SXRV 0.0828, Allianz 0.1545. **Rejected:** DTE 2.4648, EXW1 2.5077 and IS3N 2.0681, each with HTTP 400 `quantity-precision-mismatch: invalid quantity precision 3`. |
| 09:04:18 | **Three rejections in a row tripped the kill switch**, as designed. HALT cancelled the open entries (SXR8, SXRV), but Allianz had already filled at €410.80. |
| 09:10 | Allianz's lot opened (S4) and its protective stop went in at €392.71. Reconciliation OK. |

**Root cause:** the bot sized every quantity to 4 decimals. Trading 212 accepts fewer for some instruments: all three rejections were orders over one share of instruments under €100. The instrument metadata has no precision field; the error message names the precision it accepts.

**Fix (deployed 12:23, code `b1999a9d447a`, 92 tests):**
- New entries are sized to 3 decimals. Stops and exits keep the broker's own fill quantity.
- If Trading 212 still rejects a quantity's precision, the order is rounded down to the precision named in the error and sent again once. That's safe because a 400 means nothing was placed, and it's journaled as `QTY_PRECISION`. It no longer counts toward the "3 rejections" kill rule, because the corrected order goes through.

**The kill switch did its job:** a systematic order error stopped all new trading within 14 seconds, and the one filled position kept its stop.
**What it cost:** S1's month-end entries. Under S1's rule, the next check day is 30 October. The new operator command `cycle --strategy s1 --force` runs a strategy's decision for the last closed session off its schedule, through the same risk checks and journaled as a catch-up. Run after today's close, S1 enters tomorrow at the open, one day later than its backtest. The forward check will show that gap honestly.

**Follow-up (13:17–13:24):** the owner reset the kill switch, then ran the catch-up before the close. At that point the last closed session was 09-30, whose decision window had shut at 10:00. Nothing was planned, but the engine logged a misleading "missed (engine was down)". Two changes, deployed at 13:23 (code `59f65a4524ba`, 93 tests):
- A `cycle --force` that's too early is now **queued**: the engine runs the strategy as a catch-up at its next cycle.
- The "missed" message now says what happened ("not run by an hour after the next open").

S1's catch-up is queued for today's close; its orders go out on 10-02 at about 09:02.

### Incident 3: out of memory again, kill switch trip, and shutdown until the server (2026-10-06)

The owner saw the bot "stopping and restarting". It wasn't: the engine had run as one process (PID 14828) since 10-01 13:23.

| Time (CEST) | What happened |
|---|---|
| 14:56–19:47 | 12 syncs failed with dropped connections (`WinError 10053`, `SSL: UNEXPECTED_EOF`). Each failure sent a Telegram alert and a healthchecks.io `/fail` ping, so the check flipped DOWN, then UP at the next good sync. That flapping is what looked like restarts. Every sync after a failure recovered on its own. |
| 16:53 | The heartbeat was 72 s old, so the **watchdog tripped the kill switch**. The engine came back by itself 2 minutes later, but the kill switch stays tripped until a human resets it, so the 10-06 decision cycles didn't run. All 8 lots kept their stops. |
| ~19:45 | While I was diagnosing: 0.36 GB of 7.9 GB RAM free, ~6,000 page reads a second, the engine paged out to 4 MB, and a ~7-minute heartbeat stall. The watchdog's previous run had been stopped by its 2-minute limit. |

**Root cause: memory, as on 09-28.** The laptop was also running an Android emulator (Pixel_8, ~5.8 GB, started at 15:12 and again at 19:02), Android Studio/Gradle (~1.9 GB), Claude, ChatGPT, Codex and Dropbox. Under that much paging, HTTPS requests to the broker time out and break, and the engine's heartbeat stalls.

**Weaknesses this exposed (not fixed yet):**
- One dropped connection on a read-only request fails the whole sync.
- Every failed sync pings healthchecks `/fail`.
- Telegram's one-per-hour limit only matches identical text, so variants of the same network error all get through.
- `engine.log` has no timestamps.

**Owner decision (19:50): shut everything down; restart it on a rented EU server** ([09 §3](09-hosting.md#3-a-small-eu-vps)), which this third laptop incident in 9 days brings forward from P3. What I did:
1. **Engine stopped cleanly** at 19:57 (heartbeat `stopped`, so no watchdog trip). `data/STOP` holds a pause until 2030-01-01, so a scheduled start exits with "paused … not starting" (seen at 19:58). Afterwards the owner disabled all three scheduled tasks (engine, watchdog, backup) in an elevated PowerShell and paused the healthchecks.io check. No TradeBot process is running.
2. **All 8 protective stops cancelled** (ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV, IFX), each confirmed CANCELLED by the broker and recorded in the ledger (`CANCEL_ALL` event). The broker shows no open orders, and the ledger has none left to do.
3. **Left as they are:**
   - The 8 positions stay open at the broker **without stops**.
   - The kill switch stays tripped.
   - On a restart the engine would reconcile and place new stops at each lot's stop price once their market opens.

### Research round with five agents (2026-11-25)

The owner asked for a multi-agent research round under the agents' handbook (`D:\TradeBot\Agent-Guide.md`, rewritten today: votes, file locks, project rules no vote can override). Claude orchestrated Codex, Antigravity, Mistral and Deepseek in four rounds: research → cross-review and vote → amendment acceptance → verification. All reports and the synthesis are in [`reports/research/2026-11-25/`](../reports/research/2026-11-25/00-synthesis.md).

**Key findings:**
- The current system (S3/S4, 18 stocks, Incident 3) is **uncommitted**; the last commit is 42792f1.
- 5 of the 8 open demo lots are below their old stop prices (Yahoo, 2026-11-25).
- Restarting as-is would re-place those stops above the market.
- Applying a fill isn't one atomic transaction, and partial fills break P&L and stop sizing (Codex audit, reproduced).
- S2's code caps (3/€200) don't match its €140 budget.
- S1's stop makes 95–99 % of its exits.
- The S3/S4 backtests used 26 US+EU stocks, while live trades 18 German stocks.
- The LLM desk's P2 needs months to years, not 8 weeks.

**Applied:** 42 doc edits from 20 proposals that passed the handbook vote (≥ 2 approvals from other agents, amendments accepted by their authors, no open factual objection), across README, docs/01–09 and `3paperresearch.md`. They include a planned-shutdown rule ([05 §4](05-risk-and-safety.md)), a restart recovery design ([04](04-architecture.md), not implemented) and the VPS restart runbook ([09 §8](09-hosting.md)). Rejected or withdrawn: Mistral's VPS prices and runbook (wrong figures, live-money framing, invented APIs) and Claude's netcup correction (Claude misread the billing term). **No code, config, order or safety-state change.** `uv run pytest -q`: 93 passed.

**Open for the owner:** commit the tree; decide the 8 lots; S2's caps; the order of code change sets A/B/D/C/E; the ambiguous-submit policy; the promotion-gate review; the desk scope ([synthesis §3](../reports/research/2026-11-25/00-synthesis.md)).

### What happens next

| When | What |
|---|---|
| Once the tasks are installed | The engine runs 24/7: syncs, heartbeat, pings, a daily report after each US close |
| Wed 2026-09-30, ~17:50 CEST | S1's first check day (last Xetra session of September): signals, sizing and risk checks; entries planned |
| Thu 2026-10-01, ~09:02 CEST | The entries go out, fills arrive, stops follow. Then: repeat drill 8 (delete a stop in the app) and drill 1's "stops kept" half. |
| Fri 2026-10-30 | Next check day (exits, trails, new entries) |
| ~2 weeks after installing | P1 gate review. "Clean" means no kill-switch trip or mismatch from an engine fault, a daily report for every US session, and the forward check matching. |

**Needs the owner:**
1. ~~Run `ops/install-tasks.ps1` once in an elevated PowerShell.~~ ✅ Done 2026-09-27 23:02 CEST. The engine task is running (S4U logon); the watchdog runs every minute with exit code 0; the lid does nothing on AC; Windows time synced.

   **Fix made while checking it:** the journal's limits hash had changed from `eff24a142253` to `38b52067eea6` with identical limits. When I restored `risk.toml` after drill 6, git (`core.autocrlf=true`) rewrote it with CRLF line endings, and the hash was taken over raw bytes. The config hash and the code hash now ignore line endings, so the limits hash is `eff24a142253` again and matches the P0 reports. A test covers it (82 tests). The engine was restarted with `stop` + the scheduled task: the watchdog saw a clean stop and did not trip.
2. ~~Create a Telegram bot and a healthchecks.io check, and put the three values in `.env`.~~ ✅ Done 2026-09-27: the bot token checks out and a test alert was sent; a test ping to healthchecks.io returned 200 OK.
3. Set Windows Update active hours to 06:00–00:00.
4. Review the three default decisions above.

## P1 preview: first demo order on Trading 212 (2026-09-26)

The owner asked for a demo trade. It was built as the first slice of P1's broker adapter, running through the real pipeline: **risk check → submit-once → Trading 212 practice account → journal → reconcile**.

**Built:**
- `src/tradebot/trading212.py`: the REST adapter.
  - **Refuses any base URL other than the demo.** Live needs the P3 arming.
  - Basic auth; honours rate limits from the `x-ratelimit-remaining/-reset` headers per endpoint; safe single retry on HTTP 429, since nothing was executed.
  - `Decimal` rounding at the boundary: quantity rounded down to 4 decimals, prices to cents.
  - Read calls: summary, positions, orders, order, order history, instruments, exchanges.
  - Order calls: limit, market, stop, cancel.
  - Also `map_tickers()` and `is_open()`. `is_open()` reads the exchange schedule, where the latest event at or before now must be OPEN.
- `src/tradebot/execution.py`:
  - `journal()`: JSON lines in `data/journal.jsonl`. The SQLite journal replaces it in P1.
  - `submit_once()`: the [04 §4](04-architecture.md#4-core-data-contracts-sketch) protocol. It sends once; a broker "no" (4xx) is final; a timeout or 5xx makes the order UNKNOWN, and it's looked for in open orders twice, 10 s apart, never resent.
  - `wait_for()`, which falls back to order history when an order leaves the active list.
- CLI:
  - `t212-map` writes `config/t212_tickers.toml` (20 of 20 mapped).
  - `demo-trade --symbol SXR8 --eur 25 --mode lifecycle|roundtrip`.

**Run (2026-09-26, Saturday, market closed), `--mode lifecycle`:**

| Step | Result |
|---|---|
| Account | Practice account, EUR, €5,000 available. The bot sizes against its €1,000 cap. |
| Instrument | SXR8 → `SXR8d_EQ`; market open: no; last close €727.76 |
| Risk engine | APPROVED: buy 0.0348 at limit €716.84 (1.5 % below the close, so it can't fill) = €24.95; limits hash `eff24a142253` |
| Submit | Order `55600608984` accepted with status **NEW**, `DAY` validity |
| Cancel | Final status **CANCELLED**, 0 filled (read from order history) |
| Reconcile | No open orders, no position → **OK** |
| Journal | RISK_DECISION → SUBMITTING → SUBMITTED → BROKER_STATUS → CANCELLED → RECONCILE |

**Findings:**

| Finding | Consequence |
|---|---|
| Ticker formats: Xetra `XXXXd_EQ`, US `XXXX_US_EQ`; META is still `FB_US_EQ` | Mapping file generated from the ISINs |
| **Exxon's ISIN in Trading 212 is US30233Q1085**, not the older US30231G1022 in our config | Config corrected. This is exactly why ISINs are confirmed against broker metadata. |
| **Limit orders placed while the market is closed are accepted and queued** (status NEW) | The P1 adapter-test question is answered ✅ |
| A cancelled (or filled) order **disappears from the active list** (HTTP 404) instead of showing a final status | First run logged "NOT_ACTIVE". **Fixed:** `wait_for()` reads the final status from history. Without this, the round trip would have mistaken a *fill* for a failure and left a position open. A test covers it. |
| US stocks also trade in EUR on a German venue (e.g. Apple as `APCd_EQ`) | Possible way around the 0.15 % FX fee for S2-type strategies (spreads to check) |
| **Yahoo's Friday bar for SXR8.DE still had no close on Saturday** (open and volume present) | Invalid rows are dropped, so decisions would quietly use Thursday's close, and the "bar ≤ 5 days old" freshness check wouldn't notice. **P1 change:** freshness must require the bar for the exchange's last completed session (from Trading 212's schedule). This also strengthens the case for a paid EU data source. |
| Rate-limit headers: account summary allows 1 per 5 s; `x-ratelimit-reset` is a Unix timestamp | The adapter waits accordingly |

**Tests (`tests/test_trading212.py`, 8):** the live URL is refused; quantities round down; ticker mapping by ISIN, currency and venue; `is_open` across a session; submit-once finds a timed-out order without resending, gives up after two empty lookups, and treats a broker rejection as final; `wait_for` reads history so a fill isn't mistaken for a cancel. 61 tests in total.

**Superseded (2026-09-27):** the planned `demo-trade --mode roundtrip` run was dropped with the command. The P1 engine does the same round trip (limit entry, GTC stop, cancel, market exit, reconcile) through the ledger, starting with S1's first orders on 2026-10-01.

## P0: Foundations & backtest (started 2026-09-25)

### Step 1: Repository setup

**Built:**
- `git init -b main` (no commits yet; committing is the owner's call).
- `pyproject.toml`: package `tradebot` under `src/`. Runtime deps: `pandas`, `numpy`, `matplotlib`. Dev dep: `pytest`.
- `uv sync --python 3.13` created `.venv/` and `uv.lock`. The lockfile pins every package with sha256 hashes (468 hashes), per the supply-chain rule in [04 §11](04-architecture.md#11-tech-stack).
- `.gitignore`: `.env`, `data/`, `*.db`, `.venv/`, `__pycache__/`, `.pytest_cache/`.

**Versions:** Python 3.13.12, pandas 3.0.6, numpy 2.5.3, matplotlib 3.11.2, pytest 9.1.1.

**Decisions:**
- Python 3.13 instead of the 3.12 in the docs. It's what's installed, and nothing needs 3.12.
- No `alpaca-py`: Alpaca's REST endpoints are called with the standard library (`urllib`), as `check_keys.py` already does. One dependency fewer.

**Run:** `uv sync` (install) · `uv run pytest` (tests) · `uv run python -m tradebot …` (CLI, from step 9).

### Step 2: Data contracts (`src/tradebot/models.py`)

**Built:** frozen dataclasses `Signal`, `OrderIntent`, `RiskDecision`, `Trade`, a mutable `Position` (one strategy lot), and `intent_id()`, a deterministic hash of strategy, symbol, side and bar date ([04 §4](04-architecture.md#4-core-data-contracts-sketch)).

**Decisions:**
- `Signal.kind` has a third value, `trail`: S1 raises its protective stop at each monthly check, and that's a strategy decision like entries and exits.
- **Floats in research code, `Decimal` at the broker boundary.** The docs said `Decimal` everywhere. Doing that across pandas backtests is slow and awkward, and the rounding problem only exists where quantities and prices go to Trading 212. That boundary is built in P1.

### Step 3: Config loading with bounds (`src/tradebot/config.py`, `config/*.toml`)

**Built:**
- `config/risk.toml`: the limits from [05 §2](05-risk-and-safety.md#2-limits).
- `config/instruments.toml`: all 20 instruments with ISIN, market, currency, data symbols and proxy.
- `config/settings.toml`: strategy budgets (€600 / €400), the cost model, and test periods.
- `load_risk()` rejects a missing key or any value outside `BOUNDS`, `allow_short = true`, an empty whitelist, or inconsistent order sizes. It returns a short sha256 hash of the file for the journal.

**Decisions:**
- **The €1,000 cap is enforced in code:** `capital_cap_eur` has an upper bound of 1000, so raising it needs a code change, not just a config edit.
- The ISINs were filled in from public listings. They're confirmed against Trading 212's instrument metadata in P1 ([07](07-roadmap.md#trading-212-api-facts-and-p1-adapter-tests)).

**Tests (`tests/test_config.py`, 8):** the shipped config loads and the whitelist equals the instrument list. Six kinds of bad config make it refuse to start: cap above €1,000, drawdown typed as `10` instead of `0.10`, shorting enabled, empty whitelist, minimum order above the maximum position, and a missing key. The hash changes when the content changes.

### Step 4: Market data (`src/tradebot/data.py`, `python -m tradebot data`)

**Built:**
- Downloaders for Yahoo's chart API (daily OHLC, dividend-adjusted close), Alpaca (`feed=sip`, `adjustment=all`, paginated) and Frankfurter (ECB EUR/USD reference rates, one request per year).
- A SQLite cache at `data/research.db` with tables `bars(source, symbol, date, …)` and `fx`. Raw downloads are stored with source and fetch time.
- `validate()` counts problem rows: non-positive prices, high < low, OHLC inconsistencies, >25 % daily jumps, and gaps over 7 days. `usable()` drops rows that can't be traded on.
- `cross_check()` compares daily returns from Yahoo and Alpaca on overlapping days.
- `load_panel()` builds per-strategy panels: adjusted OHLC (scaled by adjclose/close), USD converted to EUR at the ECB rate of the day, and proxy history stitched in before `native_from`.
- `python -m tradebot data` refreshes everything and writes `reports/data_check_<date>.md`.

**Findings:**

| Finding | Consequence |
|---|---|
| **Stooq now blocks scripted downloads** with a JavaScript bot check. Getting around bot checks is off-limits. | Stooq dropped. **Yahoo is the research source for all history**, and [01 §6](01-platforms.md#6-market-data-us--eu-daily-bars) is updated. |
| Alpaca's free historical data starts 2016-01-04 (the `iex` feed returns nothing that early; `sip` works). | Alpaca can't supply 2006–2015. It serves as the **independent cross-check** for the US names. |
| Yahoo vs Alpaca, 8 US stocks, ~2,700 days each: return correlation 0.997–1.000. Only 4 of 21,568 stock-days differ by >0.5 %: MSFT on 2020-03-18/19 and XOM on 2020-03-12/13, crash days where one close differs for a day and then reverts. | Yahoo's US data is trustworthy. That's indirect evidence for its EU data, which has no free second source. |
| `www.ecb.europa.eu` and `data-api.ecb.europa.eu` fail TLS verification from this machine ("unable to get local issuer certificate"), while other HTTPS sites work. | EUR/USD from **Frankfurter**, which republishes the ECB reference rates: 5,308 rates from 2005-12-30. |
| Yahoo's Xetra history for the iShares ETFs is stale or wrong in the early years. SXR8/SXRV had 81–86 % zero-volume days in 2010. SXRV's 2010 prices sit ~30 % off its QQQ ratio (the −27.8 % "drop" on 2010-11-01 is a data error). EUNH had 76–99 % zero-volume days in 2009–2011. | A new instrument field `native_from`: own data is trusted from SXR8/SXRV 2014-01-01, EXW1 2009-01-01 and EUNH 2013-01-01. Before that the US twin (in EUR) is used. EUNH has no twin, so it **joins the universe in 2013**; stale prices would have faked near-zero volatility and oversized it. |
| Proxy joins are smooth (−0.3 % to +2.1 % on the join day, normal daily moves). The largest daily moves are real (2008, 2020, NVDA earnings). | Panels accepted for backtesting. |

**Coverage (EUR, adjusted):**
- S1: SXR8/SXRV/EXW1/IS3N/4GLD from 2006 (with proxies), EUNH from 2013.
- S2: 13 stocks from 2006, and META from its 2012 listing.

**Known limitations:**
- EU prices depend on one unofficial source. The paid upgrade (EODHD) needs owner approval ([08 §6](08-multi-agent-llm.md#6-cost)). The decision about a P1 runtime source is recorded in step 11.
- FX uses the ECB 14:15 CET rate for US closes at 22:00 CET, an approximation that's fine for daily research.
- Adjusted prices mean dividends are treated as reinvested, and taxes on them are ignored.

**Tests (`tests/test_data.py`, 3):** proxy stitching in EUR is scaled to join exactly; `native_from` moves the join; validation flags a jump and a high < low row, and `usable()` drops the bad row.

**Run:** `uv run python -m tradebot data` (≈1 min). Report: `reports/data_check_2026-09-25.md`.

### Step 5: Indicators (`src/tradebot/indicators.py`)

**Built:**
- `sma`.
- `rsi` and `atr`, both with Wilder smoothing: seeded with the mean of the first *n* values, then `avg = (avg·(n−1) + x) / n`.
- `bollinger_lower` (population standard deviation, the Bollinger convention).
- `volatility`: standard deviation of daily returns.

**Decision:** Wilder smoothing is written as a short explicit loop instead of pandas `ewm(adjust=False)`. `ewm` seeds with the first value instead of an average, which makes RSI(2) differ from the textbook definition early in a series.

**Tests (`tests/test_indicators.py`, 6):**
- Hand-computed values: RSI(2) on 1,2,1,2,1 gives 50 / 75 / 37.5, and ATR gives 2.5 / 1.75.
- Extremes: RSI is 100, 0 and 50 for rising, falling and flat series.
- **A causality test:** for each indicator, the value at *t* on the full history equals the value at *t* on history cut off at *t*. That proves no indicator peeks into the future.

### Step 6: Strategies (`src/tradebot/strategies.py`)

**Built:**
- **`S1Trend`**:
  - Features: SMA(200), ATR(20), 20-day volatility, `in_trend`.
  - `decide()` does nothing except on check days (last trading day of the month; weekly for the robustness test). On a check day it exits instruments that lost the trend, raises stops to close − 3×ATR (never lowers them), and enters new in-trend instruments with inverse-volatility weights.
- **`S2Pullback`**:
  - Features: SMA(200), RSI(2), SMA(5) exit, ATR(14), and `setup` = uptrend and (RSI(2) < 10 *or*, as a switch, close < lower Bollinger band).
  - `decide()` exits on close > SMA(5) or after 10 bars. It enters the lowest-RSI setups into free slots (at most 3), counting slots that exits free up at the same open.

**Decisions:**
- **One code path for backtest and live** ([04 §1](04-architecture.md#1-principles)). `features()` is computed once over history, which is safe because indicators are causal (step 5). `decide()` is a pure function of the latest row per symbol, and live will call exactly the same two methods.
- Each row carries `fresh`, meaning the symbol traded on that day. S2 only acts on fresh rows. S1 uses the latest row even on its exchange's holiday, so a month-end holiday doesn't skip a whole month.
- Whether a day is a check day is a calendar question. The backtest answers it from the data's own dates; live answers it from the exchange calendar (P1).

**Tests (`tests/test_strategies.py`, 8):** period-end detection; the S1 trend flag, inverse-volatility weights, no action on non-check days, exits, and stops only moving up; S2's setup firing on a sharp pullback in an uptrend, lowest-RSI ranking with a slot limit, a stale symbol ignored, exits on the bounce and the time stop, and slots freed by exits.

### Step 7: Sizing (`src/tradebot/sizing.py`)

**Built:**
- `size_entry()`:
  - S1 target = €600 budget × weight. S2 target = (0.5 % × capital) ÷ stop distance × price, i.e. €5 of risk at the €1,000 cap.
  - Both are capped by the strategy's position cap (S1 €250, S2 €200), the global €250, and cash.
  - Anything under €20 is skipped.
- `make_intent()`: entries become DAY limit orders at close + 1 %, exits become market orders, and ids are deterministic.

**Decision:** in a per-strategy backtest, "capital" is `€1,000 × strategy equity ÷ strategy budget`, capped at €1,000. Risk per trade therefore shrinks after losses, as `min(equity, cap)` does live.

**Tests (`tests/test_sizing.py`, 5):** budget × weight; the caps; €5 risk ÷ €4 stop = 1.25 shares; halved capital halves risk; orders under the minimum are skipped; order types and deterministic ids.

### Step 8: Simulated fills (`src/tradebot/sim.py`)

**Built:**
- Limit buy at the open: no fill if the open is above the limit, and slippage never pushes the price above the limit.
- Market orders at the open, with slippage on both sides.
- Stops: fill at the open if it gapped through the stop, otherwise at the stop, minus slippage.
- FX fee on USD instruments.
- `costs_for()` reads the cost model from settings, with a multiplier for 2× cost runs.

**Decision:** the "≤ 1 % of daily volume" cap from [06 §2.2](06-backtesting.md#22-execution-model) is **not built**. At €1,000 it can never bind, and Yahoo's zero-volume days on early Xetra data would turn it into fake no-fills. Add it when position sizes grow.

**Tests (`tests/test_sim.py`, 4):** limit fill, limit cap, gap-up no-fill; market slippage; intraday stop vs a gap through the stop; FX fee only on USD.

### Step 10: Risk engine and kill switch (`src/tradebot/risk.py`), built before step 9

**Built:**
- `check(intent, state, limits)` runs the pre-trade checks of [05 §3](05-risk-and-safety.md#3-pre-trade-checks-in-order-the-first-failure-wins) in order, and the first failure wins: kill switch, known mode, whitelist, no shorting, duplicate intent, order rate, data freshness (bar ≤ 5 days old, covering weekends and holidays), price collar, then, for entries only, notional in [€20, €250], max positions, the €1,000 capital cap, the daily loss limit, and cash.
- Exits skip the entry-only limits, because they reduce risk.
- Every decision carries the limits hash.
- Kill switch:
  - `trip()` writes `data/KILL` before anything else and appends to `data/kill_log.jsonl`.
  - `is_tripped()` re-reads the file, so the state survives restarts.
  - `reset(who, why)` is the only way out and is logged.

**Not yet:** check 3 (market open) needs the exchange calendar, and arrives with the live engine in P1.

**Tests (`tests/test_risk.py`, 16):** a clean entry passes and is recorded; a repeat is rejected as a duplicate; **each** of the 13 rejection reasons has its own failing case; exits pass even with the daily loss hit, no cash and the cap exceeded; the kill switch blocks everything, survives a re-read, and resets with a log entry.

### Step 9: Backtest engine, metrics, reports (`backtest.py`, `report.py`, `cli.py`)

**Built:**
- **`backtest.run()`**, an event-driven daily loop. For each symbol that traded that day:
  1. Fill yesterday's orders at the open: exits first, then entries.
  2. Check the protective stop.
  3. Count bars held.

  At the close, the day is marked to market and the strategy decides. Each entry is sized, becomes an intent, and passes through the **same** `risk.check()`. Approved orders queue for that symbol's next bar.
- It records unfilled limits, rejections by reason, and the first date the kill switch *would* have tripped (drawdown ≥ 10 % of the strategy budget). The backtest keeps going after that date, so the full history stays visible.
- The benchmark is the equal-weight universe, rebalanced daily, with no costs.
- **`metrics()`**: CAGR, volatility, Sharpe ± its standard error (Lo 2002), Sortino, max drawdown and its longest duration, Calmar, exposure, trade statistics, costs as % of gross P&L, turnover, and correlation/beta to the benchmark.
- **`report.write()`**: a markdown report following [06 §8](06-backtesting.md#8-backtest-report-template). It includes a chart (equity vs benchmark plus drawdown; the dataviz skill's reference palette, with a legend), 1× vs 2× costs, returns per year, trades by symbol and exit reason, top winners and losers, and a 1,000-reshuffle Monte Carlo of the drawdown.
- **Trial log `data/trials.jsonl`**: every run, with parameters, period, metrics and a **code hash** (sha256 of source and config, since there are no git commits yet).
- **CLI:**
  - `backtest --strategy s1|s2 --period insample|holdout|recent|all [--param k=v]`
  - `grid --strategy s1|s2`
  - The **holdout guard** refuses without `--frozen` and refuses a second holdout run for the same strategy (both verified).

**Bugs found and fixed while building:**

| Bug | How it showed | Fix |
|---|---|---|
| Entries sized on the signal close could fill 1 % higher and exceed a cap (€202 vs €200) | Engine unit test | Size and risk-check entries at the worst-case price (the limit) |
| The 2-orders-per-minute limit rejected the 3rd+ order of a day (129 rejections in S2, including exits) | Rejection counts in the first S2 report | In a backtest every order is sent in the same instant; live, the executor spaces orders ≥ 2 s apart. The backtest resets the per-minute counter per order; the per-day limit still applies. A regression test covers it. |
| A run with `--param` overwrote the default report | Bollinger run replaced the S2 report | Report names include parameter overrides |

The pre-fix runs stay in the trial log (the honest trial count) and are identifiable by their code hash.

**Tests (`tests/test_backtest.py`, 4):**
- A round trip: fill prices, the limit cap, exit at the next open, and **final equity = budget + Σ trade P&L**.
- A stop filled at the stop minus slippage.
- A gap above the limit leaves the entry unfilled.
- Two same-day orders both pass under a 1-per-minute limit.

**Performance:** one backtest (2007–2019, 6–14 symbols) takes 2–5 s, and the 81-cell S2 grid about 4 min.

### Parameter freeze (recorded 2026-09-25, before any holdout run)

**S1 is frozen at its pre-specified defaults:** `sma_n=200, check=M, atr_mult=3.0, atr_n=20, vol_n=20`. The in-sample grid showed a plateau for monthly checks (Sharpe 0.42–0.61), and the default sits inside it. Tighter stops (`atr_mult=2.0`) scored higher in-sample, but switching to the best cell after looking would be exactly the overfitting the method forbids. They stay a candidate for a future walk-forward test, not a change now.
**S2 is not frozen: it failed in-sample** (details in step 11), so it gets no holdout run.

### Step 11: Backtest results and the P0 gate

All runs use code `0be3a594cfcb`, EUR, with the costs from `config/settings.toml`. Reports are in `reports/`.

**S1 (trend filter, €600 budget):**

| Period | CAGR (1× / 2× costs) | Sharpe ± SE | Max DD | Trades | Benchmark CAGR / max DD |
|---|---|---|---|---|---|
| In-sample 2007–2019 | +3.4 % / +2.9 % | 0.45 ± 0.29 | −12.4 % | 210 | +8.6 % / −40.3 % |
| **Holdout 2020–2024 (run once)** | **+4.5 % / +3.8 %** | **0.71** | **−13.4 %** | 89 | +10.6 % / −24.0 % |
| Recent 2025–2026-09 | +3.5 % / +2.7 % | 0.65 | −5.4 % | 27 | +16.2 % / −14.6 % |

- **Grid (18 cells):** 17 of 18 cells are profitable after costs, and every monthly-check cell lands in Sharpe 0.42–0.61 (a plateau). Weekly checks with tight stops churn (Sharpe 0.03–0.47).
- **Behaviour:** the protective stop makes 200 of 210 exits. After a stop, S1 waits for the next month-end check, so it's invested ~50 % of the time.
- **Character:** it cut the worst drawdown by two thirds (2008: −2.8 % vs −29 %). In return it gave up over half of buy-and-hold's return in rising markets.
- **Kill switch:** it would have tripped on 2009-06-23 and 2022-05-16, when drawdown reached 10 % of the budget. Live, that pauses trading for a human review each time: roughly once every 7 years.

**S2 (pullback, €400 budget): FAILS.**

| Run | CAGR (1× / 2× costs) | Sharpe | Max DD | Trades |
|---|---|---|---|---|
| Default (RSI(2) < 10), in-sample | −0.1 % / −6.0 % | 0.02 | −18.8 % | 935 |
| Bollinger variant (the PRD's rule), in-sample | +0.1 % / −2.2 % | 0.04 | −12.5 % | 395 |
| Grid, 81 cells | 35 of 81 profitable; median Sharpe −0.02, best 0.28 (≈ 1 standard error) | | | |

**Why S2 fails:**
- A small positive gross edge (~0.2 % per trade, a 61 % win rate) is fully eaten by costs: 110 % of gross P&L at 1×.
- Trades last ~3.4 days on average, so the spread plus Trading 212's 0.3 % round-trip FX fee on US names outweighs the edge.
- Holding longer (exit SMA 10) is the only area that's consistently better, and it's still weak. This matches the literature's warning that this edge has decayed since publication.

**P0 gate ("Idea → Demo", [06 §7](06-backtesting.md#7-promotion-gates)) for S1:**

| Criterion | Result |
|---|---|
| Backtest ≥ 10 years where data exists | ✅ 13 years in-sample (with proxies) + 5 years holdout |
| Still positive at 2× costs | ✅ +2.9 % in-sample, +3.8 % holdout |
| Holdout Sharpe ≥ ½ in-sample | ✅ 0.71 vs 0.45 |
| Plateau in the robustness checks | ✅ monthly cells 0.42–0.61 |
| Max drawdown acceptable vs benchmark | ✅ −12 % vs −40 %; −13 % vs −24 % |
| Code unit-tested | ✅ 53 tests pass |
| Code reviewed | ⏳ owner review |
| Report filed | ✅ `reports/` |

**Verdict:**
- **S1 passes, so P0's exit gate ("at least one strategy") is met.**
- **S2 fails and doesn't go to demo.**

**Honest reading:**
- S1's Sharpe of 0.45 ± 0.29 isn't statistically significant (t ≈ 1.6), and ~20 S1 trials were run, which weakens it further.
- The robust, literature-backed property is **drawdown control**, not excess return. At €600, +3–4 % a year is €20–25 a year.
- As planned, P1 checks the *implementation*, not the edge ([06 §4](06-backtesting.md#4-statistical-sanity)).

**Decisions for the owner** (they affect P1–P2; my recommendations are in the summary to the owner):
1. **S2's role.** Its signals still exist, and it was always going to be the LLM desk's test bed. Options: (a) keep S2 in **shadow only** (no demo orders), so the desk is tested on whether its news and earnings vetoes can turn a zero-edge strategy positive; (b) drop it and research a different single-stock family.
2. **S2's €400 budget:** leave it unused, or give S1 the full €1,000 cap.
3. **EU runtime data for P1:** Yahoo, the only working free EU source, for the demo phase with daily validation; or EODHD (~€20/month) now. Either way, a paid source before real money.

### P0 summary

| Step | Status |
|---|---|
| 1 Repository setup | ✅ |
| 2 Data contracts | ✅ |
| 3 Config with bounds | ✅ |
| 4 Market data | ✅ (source changed: Stooq blocked → Yahoo, cross-checked against Alpaca) |
| 5 Indicators | ✅ |
| 6 Strategies | ✅ |
| 7 Sizing | ✅ |
| 8 Simulated fills | ✅ |
| 9 Backtest, reports, trial log | ✅ |
| 10 Risk engine, kill switch | ✅ (market-hours check in P1) |
| 11 Backtests, grids, holdout | ✅ S1 passes the gate, S2 fails |

53 tests, 11 modules, ~1,030 lines of code. Everything reproduces with: `uv sync`, `uv run python -m tradebot data`, `… backtest --strategy s1 --period insample`, `… grid --strategy s1`.