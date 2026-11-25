# Codex - Code and test audit (round 1, 2026-11-25)

## Summary

- **HIGH: fill processing is not crash-atomic.** An order's fill watermark commits before its lot update; a crash can permanently omit the holding from the ledger. Reproduced with an in-memory database.
- **HIGH: partial fills break accounting and protection.** Reproductions produced P&L 30 instead of 40, a CLOSED lot with quantity 2 after a new buy fill, and a replacement stop for 1 share against a remaining 0.6-share position.
- **HIGH: the shared book omits submitted/unfilled entries and does not reserve an existing pending order's cash within its own sleeve.** The one-owner invariant and capital controls are therefore incomplete. Concurrent CLI cycles add a second writer.
- **HIGH: whole-book valuation is inconsistent across strategy cycles.** Other sleeves fall back to entry prices; a reproduced book worth 960 was marked 980 by either individual sleeve. Loss checks also run after pending execution, rather than gating it with current account state.
- **Stop restoration is conditional, not a restart guarantee.** KILL does not prevent protective stops, but the pause prevents startup; reconciliation, valid mappings, an open market and successful submissions must all precede protection. No broker state was queried or changed in this audit.
- **Submit-once has unresolved cases:** HTTP 408 is marked definitively rejected; ambiguous matches are adopted arbitrarily; only the first history page is searched; an unrecognised stop status can count as protection. No absence-based retry can prove non-execution when history visibility is delayed.
- **Requested `uv run pytest -q`: failed before collection**, first on uv cache access and then on the inaccessible managed Python 3.13 interpreter. A clearly labelled fallback on Python 3.14.6 passed **53 tests in 1.17 s**. The complete suite is **NOT VERIFIED**; the build log's historical 93 is not a current test result.
- Concrete, unapplied proposals below address Incident 3: bounded retries for GETs, a three-consecutive-failure notification policy with immediate safety alerts, and UTC timestamps on console/log output.
- A Linux deployment needs service/timer units, credential and path handling, durable single-writer ownership, deliberate shutdown semantics, backup verification and an operator-controlled migration. Changing hosts alone does not fix these code defects.
- Baseline: **20 tracked files changed, 704 insertions and 73 deletions**, plus untracked work. Only this report was authored; no production files, safety files, broker orders, tasks or git history were changed.

## Findings

All local evidence below was checked on **2026-11-25** in `D:/TradeBot`, excluding `Trade-Bot-Research/`. Line references describe the uncommitted working tree, not HEAD. Reproductions used the existing code, fake brokers and SQLite `:memory:`; they did not load credentials, instantiate the real broker, or run the engine. External references carry their check date in Sources. Proposed behavior is a recommendation, not an assertion that the current implementation has it.

### F1 — Validation result and limits of this audit

- **Claim:** the requested full-suite run did not execute tests in this environment. Severity **HIGH** for release readiness; confidence **HIGH**.
- **Evidence:** `uv run pytest -q` exited 1: default cache `C:/Users/SAT/AppData/Local/uv/cache` could not be initialized (OS error 183). Retrying with `UV_CACHE_DIR` in the permitted temporary directory exited 1: `.venv/Scripts/python.exe` references the inaccessible `C:/Users/SAT/AppData/Roaming/uv/python/cpython-3.13-windows-x86_64-none/python.exe`; managed-interpreter discovery returned access denied. Direct invocation of that venv Python also failed. I did not replace the venv or install packages.
- Available `python3` is Python **3.14.6**. Its own environment has no pytest/pandas/numpy/matplotlib. Adding the existing venv's pure-Python packages to `PYTHONPATH` permitted a standard-library subset. Its first run had **53 fixture-setup errors**, caused by the default pytest temporary-directory permissions, not application assertions. Retrying with a fresh explicit temporary base passed:

```powershell
$env:PYTHONPATH='D:\TradeBot\src;D:\TradeBot\.venv\Lib\site-packages'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python3 -m pytest -q -x -p no:cacheprovider --basetemp C:/Users/SAT/AppData/Local/Temp/tradebot-codex-audit-pytest-20261125 tests/test_execution.py tests/test_trading212.py tests/test_risk.py tests/test_sizing.py tests/test_config.py
# 53 passed in 1.17s
```

- The temporary base above must be a fresh audit-specific directory on another run; pytest can clear an existing `--basetemp`. No test files were edited. `tests/conftest.py:7-12` redirects KILL and its log into temporary test paths. All **31 Python source/test files** parsed successfully with `ast.parse`, without importing scientific dependencies or writing bytecode.
- **Not established:** current full-suite success, Linux behavior, real partial-fill payloads, or broker compatibility of any proposed patch. The full suite and regression matrix below remain release gates. `docs/10-build-log.md:202-211` records 92/93 tests historically; that evidence is dated October, not this audit.

### F2 — Order fill watermark and lot update are separate durable writes

- **Claim:** a process failure can make a real fill permanently unaccounted for. Severity **HIGH**; confidence **HIGH**, reproduced.
- **Evidence:** `store.py:29-34` uses autocommit. `execution.py:154-174` writes status, `filled_qty` and `done` before creating/updating the lot. `execution.py:196` then ignores `done=1` orders on later syncs. A failure after the order update but before lot insertion left `done=1`, `filled_qty=0.35`, and zero lots. Replaying the same payload also left zero lots because delta was already zero. Sells have the corresponding lost reduction/P&L window at `execution.py:176-184`.
- **Failure:** startup sees a position mismatch and returns before stop creation (`live.py:203-214`). KILL prevents further entries but does not reconstruct or protect the missing lot.
- **Fix:** validate the payload before changing its watermark; atomically commit order state, lot mutation and associated journal events using an explicit transaction. Alerts/network requests must occur after commit. Add crash injection between every write. A connection context manager alone is insufficient with the current autocommit configuration; use explicit transaction/savepoint control [S7]. See P-codex-1 and P-codex-15.

### F3 — Partial-fill quantities, proceeds and dates are wrong in several paths

- **Claim:** the current cumulative-order model is insufficiently normalized. Severity **HIGH**; confidence **HIGH** for the reproduced calculations; **MED** for the exact prevalence of broker payload shapes.
- **Evidence:** `execution.py:37-40,156-183` treats `fill.price` as an order average if `filledValue` is absent; `trading212.py:102-109` returns only the first matching history item. The current API documents separate fill IDs, quantities and times, and says `filledValue` applies to value orders, while this API places quantity orders [S2]. This does not prove exactly how every partial-fill response is emitted; that needs sanitized broker fixtures.
- Reproduction: sell 1 share at 110 from a 2-share lot with cost 100, then receive cumulative quantity 2 / value 240. Correct total proceeds 240, cost 200, P&L **40**. Code adds `1*(110-100) + 1*(120-100)` and records **30**. Derive incremental proceeds from cumulative proceeds, or book unique fills.
- Reproduction: entry fills 1 of 2; a stop sells that 1; the entry later reaches cumulative fill 2. `execution.py:168-173` writes quantity **2** to the existing **CLOSED** lot without reopening it. Correct remaining position is **1**. Even if a lot remains open, replacing its remaining quantity with cumulative bought quantity resurrects shares already sold.
- Reproduction: `{status: PARTIALLY_FILLED, filledQuantity: 0.1}` without usable price raises `TypeError` only **after** storing the fill watermark. Quantity fills without `filledValue` are compatible with the documented field description; whether live open-order responses include another usable cost field is **UNVERIFIED** [S2,S3]. Fetch fill history before committing; never guess cost.
- `execution.py:166,171,183` dates fills by reconciliation time. A restart after a week dates old fills today, shifting S2/S4 holding periods (`live.py:99-100`). Use actual fill timestamps; define a lot's first-fill date explicitly.
- **Fix:** normalize unique fill events or cumulative quantity plus cumulative consideration with a monotonic watermark, preserve remaining inventory and cost basis separately, and maintain stop monotonicity. A later entry fill must not lower a trailed stop (`execution.py:168`). Cancel/resolve the outstanding entry remainder when a protective exit begins. See P-codex-1, P-codex-4, P-codex-15.

### F4 — Stop replacement can oversize, falsely claim protection, or duplicate an unresolved sell

- **Claim:** exactly-one-stop is not verified at the broker. Severity **HIGH**; confidence **HIGH**.
- **Evidence:** `execution.py:270` computes replacement quantity before cancellations; `execution.py:282-290` rereads the lot but reuses the old quantity. A fake cancellation that filled 0.4 of a 1-share stop left a **0.6** lot and submitted a **1.0** replacement. Recalculate quantity and price after all confirmed cancellation fills.
- `execution.py:271-276` calls a stop good based on local quantity/price and `done=0`, irrespective of whether it is confirmed, cancelling, absent during the 600-second history limbo, or unrecognised. `execution.py:162-163` merely alerts on unknown statuses; it does not add a reconciliation failure. The documented status `REPLACED` is in neither `FINAL` nor `ACTIVE` [S3]. Do not simply label REPLACED terminal and create another stop; first identify the successor order.
- `execution.py:274-275` ignores a failed submit result when retrying an existing PENDING stop, unlike the new-stop branch at 291-292. An immediately FILLED stop response is adopted without applying its fill until the next sync (`_adopt`, 86-90).
- `execute_pending()` cancels only stop rows with a broker ID (`execution.py:312`); a PENDING stop whose first POST remains unresolved can coexist with a market exit. An absence-based retry/exit needs explicit unresolved-sell reservations.
- Partially filled stops are compared using original order quantity instead of remaining executable quantity. Replacement introduces a cancellation gap unnecessarily and can race more fills.
- **Fix:** separate desired protection from broker-confirmed protection; reconcile open remaining sell quantities and statuses; never overlap unresolved sells; recalculate after cancel confirmation; apply fills from successful POST responses through the atomic fill handler. An unprotected lot is an explicit safety condition, even when KILL is already set. See P-codex-2.

### F5 — Submit-once protects common timeouts but not all ambiguous outcomes

- **Claim:** several paths undermine the intended protocol. Severity **HIGH**; confidence **HIGH** for code behavior, **MED** for broker timing assumptions.
- **Evidence:** `execution.py:132` makes every HTTP status below 500 final. Injecting HTTP **408** returned `BROKER_REJECTED`, `done=1`. Placement docs describe 408 as timed out, not a certified non-execution result [S3,S4]. Treat 408 as UNKNOWN; actual 408 execution behavior is **UNVERIFIED**.
- `find_order()` (`execution.py:61-74`) accepts a missing creation timestamp, has no upper time bound and returns the first matching order. A reproduction with two matching broker orders adopted ID 101 instead of reporting ambiguity. Claimed-ID exclusion is useful but is not proof of identity.
- `trading212.py:102-109` ignores `nextPagePath`; two successful first-page reads are not exhaustive history searches. Pagination and a 50-item maximum are documented [S2,S5]. Multiple history rows for one order must be normalized before matching.
- `execution.py:95-102` converts two empty lookups into permission to resubmit; that is a documented project policy (`docs/04-architecture.md:135-141`), not an exactly-once guarantee. A delayed accepted order can appear after the final pre-submit lookup and coexist with the retry. The upstream POST endpoints explicitly are not idempotent [S3,S4]. Stronger default recommendation: retain UNKNOWN and require resolution/operator adjudication rather than auto-retry ambiguous submissions.
- `submit()` itself contains no KILL check. `execute_pending()` checks before entering it, but a lookup, rate wait or recursive precision correction can separate that check from the actual POST (`execution.py:117-131`, `trading212.py:54-80`). A watchdog can trip in that interval. Recheck immediately before each entry POST attempt, including 429 retries; protection/authorized flatten have distinct rules.
- Unclassified response/read/JSON failures can leave SUBMITTING for the next sync, which is recoverable in principle. They must not be treated as a definitive rejection or silently retried at the HTTP layer.
- **Fix:** P-codex-3/4; preserve all attempts and their timestamps, reject ambiguous matches, bound/exhaust relevant history, and reserve unresolved quantity throughout recovery.

### F6 — Quantity correction is sensible for rejected buys but unsafe as a universal retry

- **Claim:** the added correction is broader than its stated one-retry entry fix. Severity **HIGH** for stops/exits; confidence **HIGH**.
- **Evidence:** `execution.py:106-131` applies to every role, recursively decrements `attempts`, and does not persist a separate correction count. A sequence of progressively coarser precision errors permits multiple corrections. Correcting a sell from 0.1545 to 0.154 leaves a residual; correcting a stop leaves part of the holding unprotected. `ensure_stops()` then keeps wanting the original quantity and may repeatedly cancel/recreate a rounded-down stop. The existing regression only covers three independent entry errors (`tests/test_execution.py:257-268`).
- `qty()` truncates to four decimals for all outgoing stops/exits; retaining the broker's exact quantity is therefore not literally guaranteed (`trading212.py:33-36,122-128`). Supported precision beyond the incident's observed examples is **UNVERIFIED**; the error phrase is local incident evidence, not a current public API contract (`docs/10-build-log.md:196-204`).
- `TOL=1e-4` can close a lot with a residual at or below one full quantity step and tolerate a corresponding position discrepancy (`execution.py:179,216`). Dust must remain explicitly represented, even if it cannot be traded.
- **Fix:** allow one persisted correction for a definitive rejected **entry**, validate the corrected executable notional, and learn precision without modifying unknown outcomes. Stops/exits require explicit residual handling and an alert rather than silently pretending full protection. See P-codex-3.

### F7 — Shared-book reservations and ownership are incomplete

- **Claim:** one owner per stock is implemented for open lots and PENDING entries only. Severity **HIGH**; confidence **HIGH**.
- **Evidence:** `live.py:92-117` reads only `role='entry' AND status='PENDING'`. A NEW/UNKNOWN/SUBMITTING/unfilled entry is absent until it creates a lot. A second strategy, or a catch-up while a DAY order rests, can plan the same stock and disregard the reserved capital. Partial fills reserve the lot but not the remaining buy quantity.
- Same-sleeve pending orders are counted globally but not subtracted from `cash_eur=equity-own`. Their symbols are not excluded from the strategy candidate pool and their slots are not represented in `positions`. A second decision with a different date can spend the sleeve again. Deterministic intent IDs protect identical date/strategy/symbol/side, not a later date or another strategy.
- Other sleeves' marks are unavailable after `taken` filters their symbols (`live.py:94-97,112`); deployed capital falls back to historical entry cost.
- `cli.py:301-321` calls `eng.cycle()` directly without ownership locking or reconciliation, even while the engine runs. SQLite serializes individual writes, not the read-risk-plan sequence; different strategies can both pass against the same snapshot. `cmd_report()` also writes while the engine may run (`cli.py:324-330`).
- **Fix:** reserve remaining buy quantity/notional for every unresolved or active order; subtract own reservations from sleeve cash, include them in slot counts, and maintain ticker ownership transactionally. Make CLI cycles queued requests handled by one engine writer. See P-codex-5/6/12.

### F8 — Risk valuation, freshness and order-rate enforcement differ from the safety specification

- **Claim:** the current runtime does not implement several advertised safety bounds. Severity **HIGH**; confidence **HIGH**.
- **Evidence:** `live.py:263-270` sends only the current strategy's closes to `mark()`, which substitutes entry prices for other open lots (`live.py:73-74`). In-memory reproduction: two 1-share lots bought at 100 and now worth 80 each give book equity **960** with both marks, but **980** with either sleeve alone. Artificial marks also contaminate the recorded peak/day baseline.
- `live.py:201-225` executes pending orders before obtaining current equity/loss state. Broker account summary is called at startup for clock skew, not reconciled for cash/equity (`cli.py:176-184`, `execution.py:209-217`). The virtual EUR 1,000 sleeve is intentional, but broker available cash and complete book valuation still need independent checks. `docs/05-risk-and-safety.md:19,87-94` currently promises more.
- Daily loss is anchored to the last mark of an earlier **wall-clock UTC date**, not a persisted exchange session baseline (`live.py:77-78`). A late prior-day cycle can reset the effective daily-loss result before a later open.
- `live.py:137` resets the per-minute counter for every intent. The executor has no strategy order limiter; a broker limit of one request per two seconds [S4] permits far more than `config/risk.toml:12`'s two per minute. Stops and different endpoint types have separate API pacing, so broker pacing cannot substitute for the configured policy.
- `risk.py:53` admits future bars; it only rejects excessive positive age. No general finite/positive quantity, allowed side/kind consistency or finite-price validation precedes the sell checks. Typed dataclasses do not enforce these values at runtime.
- `sizing.py:16-25` applies the risk-distance cap only to non-weighted signals; S1's weighted entries can exceed the universally worded EUR 5 entry-to-stop risk in `docs/05-risk-and-safety.md:28`. This may be an intentional strategy exception; do not silently change the frozen S1 model. Owner must resolve the contract.
- Rounding occurs after risk approval (`live.py:139-152`). A minimum EUR 20 intent can become executable dust, or cent rounding of the limit can marginally exceed a cap. Check the actual rounded quantity/price that will be posted.
- **Fix:** P-codex-5/7/8; measure one complete timestamped book, gate execution with current risk, reserve cash explicitly, enforce time-based order rates centrally, and validate executable values. Define the S1 exception before changing sizing.

### F9 — Stock stale-data degradation can run indefinitely; missing panels can crash the cycle

- **Claim:** the new stock-specific fallback bypasses the documented two-cycle held-symbol halt. Severity **HIGH** for held-symbol monitoring; confidence **HIGH**.
- **Evidence:** after the deadline `live.py:260-262` drops bad stock symbols and logs a completed cycle. Only `stale()` counts consecutive skipped cycles and halts with positions (`live.py:285-296`); the stock fallback never calls that branch. S1 is only checked on its monthly strategy schedule (`live.py:251-253`), rather than validating held data every session.
- `suspect()` indexes `df.index[-1]` without checking emptiness (`live.py:59-61`); `load_panel()` indexes empty native history for proxies (`data.py:226`). `refresh()` aborts the whole refresh on one download exception (`data.py:191-195`), so the promised per-stock fallback may never be reached. `usable()` does not reject all OHLC inconsistencies/non-finite data recorded by `validate()` (`data.py:120-139`).
- **Fix:** persist a per-held-symbol, per-session health streak independently of strategy check days; distinguish stale input from a failed download; treat missing/empty panels as data defects, not index errors; preserve valid stops and halt entries when the threshold is reached. See P-codex-5/9.

### F10 — Watchdog and notifications confuse progress, successful sync and trading readiness

- **Claim:** continuous failed syncs can retain a healthy local heartbeat, and logical reconciliation failure can send a success ping. Severity **HIGH**; confidence **HIGH**.
- **Evidence:** `live.py:389-399` catches exceptions and returns; `loop()` updates `progress` every 20 seconds (`live.py:407`). The heartbeat measures loop liveness, not a last successful reconciliation. `sync()` returns normally on mismatches or skew (`live.py:204-217`), and `step()` then calls successful `notify.ping()` anyway. Both are separate states and should be reported separately.
- Incident 3's three unfinished fixes remain unfinished at `trading212.py:52-83`, `live.py:394-397`, `notify.py:27-38`, `ops/install-tasks.ps1:43-44`; see `docs/10-build-log.md:227-231`.
- `watchdog.py:22` overwrites heartbeat JSON non-atomically; parse failure becomes None, treated as stopped/never started (`watchdog.py:25-42`). A killed writer can leave this fail-open condition indefinitely. `engine_alive()` is a heartbeat check, not a process lock; two startup contenders can both pass (`cli.py:170-171`). A restarting engine can overwrite a stale running heartbeat before a watchdog sees the crash.
- `risk.py:93,99` also writes/reads KILL non-atomically. Malformed existing JSON raises, rather than providing a structured fail-closed state; this can stop maintenance as well as entries. Timed STOP parse failure is treated as no pause (`live.py:45-51`), so a corrupt shutdown marker could permit startup. These are code findings only; actual safety files were neither read nor changed.
- **Fix:** P-codex-10/11/12/13/14. Keep heartbeat, reconciliation health and protection health distinct. N-failure debounce applies to transient network noise, never to a safety trip or known missing protection.

### F11 — Catch-up queueing works in the covered case, but can be deferred or consumed incorrectly

- **Claim:** tests cover the before-close happy path, not concurrent/failed catch-ups. Severity **MED**; confidence **HIGH**.
- **Evidence:** queue presence is checked at `live.py:249`, after the already-ran-session early return at 238 and deadline return at 244. A newly queued request for a session already recorded cannot override that return; it waits for a later session. A forced cycle that reaches `decide()` under KILL can reject every intent but still log `done (operator catch-up)`, consuming the request (`live.py:275,279-283`). Direct CLI execution bypasses `sync()`'s no-cycle-under-KILL guard.
- `tests/test_live.py:184-201` verifies an explicit forced cycle and one queued request before a fresh cycle. It does not verify two callers, request acknowledgements, duplicate planned entries, failed/stale cycles, pause/KILL, unknown strategy names or restarts. Re-running the same date cannot recover a previously SKIPPED intent, because `seen_ids` includes all historical order intents (`live.py:115`); this is deliberate duplicate protection, but the CLI needs to explain it.
- **Fix:** durable request IDs with pending/consumed/rejected outcomes; one engine consumer; consume only after a successful, reviewed decision transaction; validate live strategy selection. See P-codex-5/6/16.

### F12 — S3/S4 signal implementation is reasonable, but the forward check is not a shared-book replay

- **Claim:** causal signal tests do not establish runtime/backtest equivalence. Severity **MED**; confidence **HIGH**.
- **Evidence:** S3 uses shifted prior rolling highs/lows (`strategies.py:144-145`) and has a prefix-causality test (`tests/test_strategies.py:104-106`). S4 uses a local date-seeded RNG and sorted candidates (`strategies.py:197-201`), not global randomness. These are good properties. Runtime bars-held includes the entry session (`live.py:99-100`), matching the backtest's first-session increment (`backtest.py:90-97`) for ordinary fills; reconciliation-time entry dates break that parity (F3).
- `live.py:320-325` backtests each sleeve independently; live filters other owners and allocates in `settings.toml:8` order. S4's input candidate set therefore differs even with the same seed. Same algorithm + same seed is insufficient when the book differs. The daily report dated **2026-10-05** explicitly reports S2 and S4 holdings differing; it is evidence of divergence, not proof of alpha or a specific single bug.
- Backtest fills iterate **symbols first**, processing exits and entries only within each symbol (`backtest.py:70-90`), whereas live sends all exits first. Under a cash-constrained same-open replacement, insertion order can affect which entry fills. Backtest rounds neither quantities nor limit prices to broker precision. DAY orders are simulated only at the open (`sim.py:17-21`), while live lets them rest; that discrepancy is already admitted in `docs/04-architecture.md:106`.
- `config/risk.toml:5` says S2 <=2, but `strategies.py:87` allows **3**. Budget 140 does not prove at most two holdings. `tests/test_config.py:11` checks only S1+S2 budgets, omitting S3/S4; `load_settings()` has no validation (`config.py:86-89`). Removing a brittle fixed hash assertion was reasonable; it did not replace this missing all-sleeve validation.
- **Fix:** keep the standalone research baseline, but label it accurately; add a separate portfolio replay with actual activation dates, allocations, ownership, requests and fill policy. Correct the S2 comment or obtain approval for an explicit demo override; do not mutate strategy parameters to make a report match. See P-codex-17/18/19.

### F13 — Documentation overstates implemented safety, beyond the stale strategy roster

- **Claim:** a reader cannot safely use docs 04/05 as an exact runtime contract. Severity **MED**; confidence **HIGH**.
- **Evidence:** docs 04:104 still says S2 shadow-only; settings enables all four. Docs 04:133 says money/quantities use Decimal, but models/store use float/REAL (`models.py:3,39-42`, `store.py:15-20`) with Decimal rounding only at the boundary. Docs 05:26,30 retain 9 positions / 10 daily orders, versus current 12/20. Docs 05:79 promises reconciliation before reset, but `cli.py:277-284` only displays the most recent recorded reconciliation. Docs 05:91-92 promise stop and cash/equity reconciliation beyond the implemented position/order comparison. Docs 05:141 says cancel partial entry remainder at session end; no such scheduler action exists. Broker DAY expiry is at exchange-local midnight, not necessarily the exchange close [S4].
- **Fix:** document actual P1 behavior and unresolved controls without claiming the proposals are implemented; migrate the runbook only after the fixes are accepted and tested. See P-codex-20/21.

### F14 — Safe restart of the eight unprotected demo positions: exact conditional trace

- **Claim:** code can restore the eight stops with KILL still tripped, but cannot do so while the current pause is honored or if reconciliation fails. Severity **HIGH**; confidence **HIGH** for the trace, **UNVERIFIED** for current broker quantities/prices/orders.
- **Historical evidence:** `docs/10-build-log.md:233-239` records the October 6 shutdown, pause to 2030, cancelled stops and retained holdings. `reports/daily/2026-10-05.md` lists ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV and IFX. That report predates cancellation; it is not a current account snapshot. No new account query was performed.
- **Trace:** `python -m tradebot run` -> `__main__.py:6` -> `cli.cmd_run` -> `paused_until()` (`cli.py:161-163`, return without engine construction if paused) -> risk/settings/demo checks and startup summary/clock probes (`cli.py:173-184`) -> `Engine.loop()` -> first `step()` -> `Engine.sync()` -> calendar -> `execution.sync()`.
- On any first reconciliation problem, `sync()` returns before `ensure_stops`; on a second it calls HALT then returns. If clean, it reads KILL, cancels entries if tripped, then calls `ensure_stops` **regardless of KILL** (`live.py:203-214`). Thus KILL should remain tripped throughout protection recovery.
- `live_open` only includes symbols in enabled EUR strategy universes. Removing a strategy or mapping can strand its still-open lots, because their ticker never appears in that set. Current mappings cover the eight symbols; ETFs use schedule 166 and stocks 54 (`config/t212_tickers.toml:1-42,115-140,178-183`). Actual future schedules must be refreshed.
- `ensure_stops` ignores closed markets and active exits (`execution.py:267-269`), then uses the ledger stop price and quantity. Cancelled rows with `done=1` are not reused; it plans a fresh stop key and posts it. An old stop price is not validated against a current market quote here. Whether a stale stop above the current market is rejected or immediately executes in a particular case is **UNVERIFIED**; the API only establishes stop-to-market semantics [S3].
- A rejected new stop calls HALT; since KILL is already set, that does not establish protection. A network failure midway through eight stops can leave a partially protected book. `RECONCILE ok=true` is not proof of eight active stops.

**Proposed owner/operator procedure for a later authorized EU-VPS restart — not performed in this round:**

1. Complete the release fixes/tests, establish one active host, and keep all laptop scheduled tasks disabled. Confirm the EU host, account identity and **demo** settings; do not reset KILL. Preserve the current working tree and ledger with consistent backups and hashes; do not deploy stale HEAD.
2. With execution still stopped, obtain a fresh read-only account inventory: positions, quantities, pending orders, relevant order/fill history, current prices, current schedules and available cash. Compare all eight lots and cancelled stops to the ledger. Resolve corporate actions, dividends/accounting changes, residuals and missing history explicitly. Never create an empty ledger to make reconciliation pass.
3. Review each intended protective stop against current quantity, accepted precision and price. Decide any required adjustment or controlled close explicitly; do not treat October stop levels as automatically safe today. Keep outstanding/unknown sells reserved until resolved.
4. Only the owner-authorized operator retires the long pause when the service, watchdog and backup installation is ready. This is an explicit future transition; the round-1 agent must never touch STOP/KILL or launch the service. Keeping KILL set allows protection maintenance while blocking entries.
5. Observe recovery during the relevant broker-open sessions. Confirm eight positions against the ledger, and for **each remaining open lot** confirm one accepted GTC sell stop with the correct **remaining** quantity and price from a fresh broker read. If a stop executes, reconcile that fill and reduce the expected open-lot count; do not recreate protection for a closed lot.
6. Require no UNKNOWN/SUBMITTING/limbo orders, no unresolved discrepancies, protection-complete status, and a subsequent clean sync. A rejection/outage leaves restart incomplete; retain KILL and escalate the specific unprotected holding.
7. Resume the external dead-man monitor only when its cadence/grace and the successful/protection-health signals are verified. Independently test the watchdog without removing protection. Reset KILL only in a separate owner-approved step after fresh reconciliation and protection checks; inspect old pending exits/catch-up requests before normal decisions resume.

### F15 — Linux EU VPS: code paths and systemd design

- **Claim:** the core code is largely portable, but the existing operational wrapper is Windows-specific and safety ownership is not portable by assumption. Severity **HIGH** for migration readiness; confidence **HIGH** for source findings, **MED** for the unexecuted deployment proposal.
- `ops/install-tasks.ps1:7,9,12-24,36-65` depends on `.venv/Scripts/python.exe`, C:/ backup, powercfg/registry/Windows Time, cmd redirection and Task Scheduler. Replace these with an independently supervised engine service, a one-minute oneshot watchdog timer, and a persistent nightly backup timer (P-codex-22 to 27). No cloud purchase or deployment is proposed as already authorized.
- `config.py:6-10` resolves data/config relative to the source tree. An editable checkout at `/opt/tradebot` works; a conventional wheel can resolve ROOT inside site-packages and find neither configuration nor state. Add explicit absolute data/report/config overrides; keep source read-only to the service account (P-codex-12).
- `config.read_env()` ignores process environment and systemd credentials (`config.py:31-41`). `LoadCredential=` alone will not work until the reader supports `CREDENTIALS_DIRECTORY` [S6c]. Proposed credential `tradebot.env` holds demo-only values supplied by the owner; it is never printed or embedded in a unit.
- `Engine.loop()` only has Python `finally` cleanup; the normal systemd termination signal has no custom handler. Proposed `KillSignal=SIGINT` uses the existing KeyboardInterrupt/finally path (`cli.py:188-191`, `live.py:411-417`), pending a proper bounded graceful shutdown handler. A timeout/SIGKILL remains a crash, with submit-once recovery and a sticky kill, not a clean stop.
- The service uses `Restart=always`, `RestartSec=300` to preserve the current retry/paused-start behavior. A deliberate systemd stop is not automatically restarted [S6a]. Avoid `WatchdogSec=` until the application implements sd_notify; the existing JSON heartbeat is not that protocol.
- Linux UTC is suitable for internal sessions, which are timezone-aware. `stop --until` uses local host time (`cli.py:202`); either make the CLI explicitly Europe/Berlin-aware or document/display UTC for the server. NTP readiness requires a working selected time-sync service, not just an ordering target. Missing HTTP skew samples currently fail open (`cli.py:181`); bound sample age and require verified startup time before entries.
- Preserve demo DB through SQLite backup rather than casually copying an active main DB while ignoring WAL; preserve research cache, configurations, journal/trial records and safety state through an operator-controlled migration. Test restore and `PRAGMA integrity_check`. The old Windows venv is not the Linux runtime; install the pinned dependencies for that platform and run the full suite.
- Service isolation does not fence another host using the same broker account. Disable the old host's automation and verify it remains disabled. A local process lock is still necessary for manual CLI/start races. API limits are per account even across different keys/IPs [S5].

### F16 — Priority regression matrix

- **Claim:** current tests exercise important happy paths but omit the failure transitions most likely to invalidate safety claims. Severity **HIGH**; confidence **HIGH** from `tests/test_execution.py:14-78,111-268`, `tests/test_live.py:28-201`, `tests/test_trading212.py:67-124`.
- The fake broker fills whole orders in one action; it does not produce repeated/missing-price partial snapshots, cancellation races, fill-level pages or unknown successor orders. Extend it before relying on a green count.

| Area | Required scenario and assertion |
|---|---|
| Fill durability | Crash after every ledger/event mutation; restart/replay produces one correct lot transition and no lost/doubled P&L. |
| Partial fills | Entry 1/2 -> stop 1 -> entry 2/2 leaves OPEN 1; multiple sell prices produce exact total proceeds; duplicate/out-of-order fill IDs do not reapply. |
| Stop recovery | Eight lots, KILL set, cancelled stops, closed then open sessions; restore each once; simulate one rejection/network failure; protection cannot be green. |
| Cancel/replace | Stop partially fills during cancellation; replacement equals residual; unknown/cancelling/REPLACED stop cannot be called confirmed protection. |
| Submit ambiguity | Accepted-but-timeout, HTTP 408, truncated JSON, 5xx, multiple matches, missing timestamps, second history page, late visibility; no blind duplicate POST. |
| Precision | One entry correction only; zero/dust result; stop/exit correction leaves tracked residual; correction followed by timeout; no attempt-count erasure. |
| Shared book | NEW/UNKNOWN and partial pending entries reserve owner/cash/slots; two strategy cycles and CLI request contention preserve one ticker owner. |
| Risk | Whole-book loss across sleeves, overnight loss before pending send, session baseline, rounded EUR 20/250 boundaries, future bars, NaN/negative qty, real elapsed-time order limits. |
| Data | Empty/missing panel, individual download failure, two stale sessions on a held stock, S1 monitoring off monthly check day. |
| Incident 3 | GET timeout/503 then success; GET 401 no retry; POST ambiguity no retry; exact N-streak alert, reset and recovery; no green ping for mismatch. |
| Operations | Partial heartbeat/KILL/STOP writes, stale heartbeat before restart, simultaneous engine starts, service stop during POST, failed backup/restore. |
| Experiments | Shared-book replay vs independent sleeve baseline; stable S4 candidates/seeds; global exit-first execution across two symbols. |

## Proposed edits

These are **unapplied proposals**, one file per item. IDs are for cross-review under handbook section 3.2. The exact Incident 3 snippets are candidate patches to review and test, not production-validated replacements. Related proposals must be integrated coherently; do not deploy only a schema or only its caller.

### P-codex-1: Make fill application atomic and inventory-based
- File: src/tradebot/execution.py §apply
- Change: Validate/normalize the incoming fill before any mutation. Wrap the order watermark, lot quantity/cost/P&L and ORDER/FILL/LOT_CLOSED events in one explicit savepoint; rollback and re-raise on error, release on success, alert afterward. Re-read the current order inside the transaction. Update remaining lot quantity by newly bought/sold delta, not total cumulative buys. For cumulative average input, incremental consideration is `new_filled * new_average - old_filled * old_average`; only use this formula after the adapter certifies both are cumulative averages. Prefer deduplicated fill IDs. Use broker fill dates; preserve raised stops and residual quantities; reject missing/non-finite prices without advancing the watermark. Do not perform network I/O while holding the transaction.
- Why: F2/F3 reproductions; execution.py:154-184; store.py:31; [S2,S7], checked 2026-11-25.
- Risk if wrong: duplicate/missing fills, incorrect cost basis, a long SQLite lock or incorrect resurrection of a closed lot. Requires P-codex-4 normalization and P-codex-15 regressions.

### P-codex-2: Reconcile protection after cancellation and before new exposure
- File: src/tradebot/execution.py §ensure_stops / execute_pending / sync
- Change: Recompute `want_q, want_p` from the reread lot **after** confirmed cancellations, immediately before planning a replacement. Track remaining executable sell quantity, not original stop quantity. Only broker-confirmed resting statuses count as protection; return a structured protection result with unprotected/uncertain lot IDs. Treat unrecognised/REPLACED status as unresolved, reconcile its successor, and block conflicting sells/new entries. Apply successful POST fill payloads immediately through the atomic handler. Check return values from both new and existing-PENDING stop submits. Resolve/cancel unfilled entry remainders before disposing of their lot. Never overlap an UNKNOWN stop and a discretionary sell. Reserve flatten intent as an explicit field rather than relying on a reason-string prefix.
- Why: F4; execution.py:263-320; [S3], checked 2026-11-25.
- Risk if wrong: overselling, duplicate protection or leaving a holding uncovered. Partial-fill/cancel fault tests are mandatory.

### P-codex-3: Harden ambiguous-submit and precision-correction policy
- File: src/tradebot/execution.py §submit / find_order / _lost
- Change: Treat HTTP 408, network/response-decoding errors and server errors as UNKNOWN. Keep one immutable record per attempt; do not overwrite its time or erase attempts when precision changes. Match a unique candidate only, with validated creation time and bounded/exhaustive relevant history; multiple matches remain unresolved. Default to no automatic resubmit of an ambiguous POST, recording an operator-resolution requirement; changing docs 04's existing two-lookups retry policy requires approval. If the desk retains automatic retry, clearly label its duplicate risk and require complete history plus reservations. Permit at most one persisted precision correction for a definitive rejected entry, not an unknown response or a protective sell; enforce nonzero and rounded-notional bounds. Recheck KILL at the entry transport boundary after waits, including each allowed 429 retry, while continuing protective maintenance under KILL.
- Why: F5/F6; execution.py:61-149; [S2-S5], checked 2026-11-25.
- Risk if wrong: duplicate orders or missed entries; stricter UNKNOWN policy may require operator intervention more often. Do not fix this by retrying every HTTP failure.

### P-codex-4: Normalize complete broker history and bound read retries (Incident 3 fix 1)
- File: src/tradebot/trading212.py §_call / history / order_history
- Change: Separate a single HTTP request from policy. Keep write retries restricted to definitive 429 rejection under the existing policy; ambiguous POST/DELETE outcomes propagate to execution. Add `BrokerReadUnavailable` and wrap **GET only** retries. The following is an exact minimal insertion/rename design, preserving the existing `_call` body as `_request`:

```python
import http.client

class BrokerReadUnavailable(Exception):
    """A transient broker read failed after bounded attempts."""

class Trading212:
    # Existing __init__ and other methods remain.

    def _call(self, method: str, path: str, body: dict | None = None):
        if method != "GET":
            return self._request(method, path, body)
        last = None
        for attempt in range(3):
            if attempt:
                time.sleep(float(attempt))  # 1 s, then 2 s
            try:
                return self._request(method, path, body)
            except T212Error as exc:
                if exc.status not in {408, 500, 502, 503, 504}:
                    raise
                last = exc
            except (urllib.error.URLError, TimeoutError, OSError,
                    http.client.HTTPException) as exc:
                last = exc
        raise BrokerReadUnavailable(
            f"GET {path.split('?')[0]} failed after 3 attempts"
        ) from last

    def _request(self, method: str, path: str, body: dict | None = None):
        # Exact former _call body (current lines 53-83).
        ...
```

  Integration requirements: `_request` remains the existing implementation, not a literal ellipsis; its existing 429 policy still waits for reset and has four attempts. Thus the three GET attempts are a **count bound, not a wall-clock guarantee**; add a monotonic total read deadline (proposal: 90 s), cap each socket timeout to the remaining budget, and abort a read rather than sleep past that deadline. Do not retry 400/401/403/404 or arbitrary application/JSON schema errors. A final 429 remains `T212Error(429)` and is transient for the sync-level policy. A write transport hook from P-codex-3 must run after each rate wait and before each write request.

  Also follow relevant `nextPagePath` pages, validating that they stay on the configured API origin/path; deduplicate order/fill IDs; normalize cumulative quantities, fill prices/consideration and broker timestamps. A search stopped by page/time bounds returns incomplete/unknown, never certified absence. Do not use a single fill's price as a cumulative average.
- Why: Incident 3, docs/10-build-log.md:227-230; F3/F5; [S2,S5,S8], checked 2026-11-25.
- Risk if wrong: accidentally retrying writes duplicates orders; excessive retry delay stalls protection; incorrectly normalized history corrupts accounting. Tests must count actual transport calls and cover partial response reads, not just raised TimeoutError before sending.

### P-codex-5: Build one complete reserved book and make cycles consume requests
- File: src/tradebot/live.py §decide / Engine.sync / Engine.cycle
- Change: Load full-book marks, broker cash and order reservations once per sync before any pending entry execution. Include all non-final entry states and only their unfilled remainder; subtract own reservations from sleeve cash, reserve strategy/global slots, and prevent any other owner for a ticker. Recheck state when planning under a serialized transaction. Use an exchange-session equity baseline; reject entries if marks are missing or stale, and retain explicit last-known marks instead of entry-price substitution. Evaluate drawdown/daily loss before pending entries; re-read KILL after protection maintenance. Track per-held-symbol data health every session. Make cycle requests durable and consume them inside the engine after reconciliation; acknowledgement must distinguish successful decision, rejection, data wait and expiry. Include held lots from disabled strategies in protection scheduling. Return explicit sync/protection health, not None on both success and failure.
- Why: F7-F11/F14; live.py:69-160,201-283; checked 2026-11-25.
- Risk if wrong: double-reserving partial fills can undertrade; missing reservations can breach the cap; request replay can duplicate decisions. This is a safety refactor, not a strategy parameter change.

### P-codex-6: Queue operator cycles instead of running a competing writer
- File: src/tradebot/cli.py §cmd_cycle / cmd_reset_kill / cmd_run
- Change: `cmd_cycle` validates a configured live strategy and appends a request with an ID, requested session policy and force flag; it never constructs an engine to make a concurrent decision. Display queued/consumed/rejected status accurately. Put a process-lifetime exclusive engine lock before startup checks and maintain it through shutdown; all mutating offline CLI operations must honor it. Before reset, require a fresh successful reconciliation/protection check, not merely display an old event. Require verified time readiness before entry arming. Keep pause handling and demo-only gates intact.
- Why: F7/F10/F11/F13; cli.py:155-184,267-321; checked 2026-11-25.
- Risk if wrong: stale requests can fire unexpectedly or commands can deadlock behind the engine. Preserve explicit operator identity and journal acknowledgements.

### P-codex-7: Validate executable order values and enforce real order rates
- File: src/tradebot/risk.py §_failure / RiskState
- Change: Reject invalid side/kind/type combinations, non-finite or non-positive quantity/price/notional, future/missing session bars, and entry notional inconsistent with rounded quantity times executable limit. Check aggregate symbol exposure including reservations. Replace the per-loop minute counter contract with persisted recent submission timestamps supplied by the executor, with a separately reviewed policy for urgent protection and exits. Return explicit failures for malformed state rather than allowing NaN comparisons to pass. Keep exit exposure exemptions.
- Why: F8; risk.py:36-68; docs/05-risk-and-safety.md:41-57; checked 2026-11-25.
- Risk if wrong: overly strict freshness/rate logic can obstruct risk-reducing exits. Test those exceptions explicitly.

### P-codex-8: Size and approve the actual rounded order
- File: src/tradebot/sizing.py §size_entry / make_intent
- Change: Introduce a shared executable-price/quantity policy supplied by the venue boundary, round before final risk approval, recompute notional, and reject zero/dust results. Enforce finite positive stop distance and a valid resulting stop. Resolve the S1 risk-cap specification first: either apply `min(weight_target, risk_cap_target)` with a new separately evaluated strategy version, or document the approved weighted-S1 exception. Do not alter frozen S1 sizing silently.
- Why: F8; sizing.py:15-32; live.py:139-152; checked 2026-11-25.
- Risk if wrong: changes historical quantities and strategy behavior; requires a new version/trial record if sizing policy changes.

### P-codex-9: Make missing-symbol data an explicit per-symbol outcome
- File: src/tradebot/data.py §refresh / load_panel / usable
- Change: Return a per-symbol refresh result, close database connections in finally blocks, and let callers distinguish failed download, empty history and invalid rows. Do not index an empty native/proxy frame. Exclude non-finite/non-positive prices and invalid OHLC geometry from usable input; preserve reason codes for the runtime monitor. Bound requests and record data timestamps. A partial refresh may allow unheld valid symbols to proceed only under P-codex-5's held-symbol safety policy.
- Why: F9; data.py:137-139,187-235; checked 2026-11-25.
- Risk if wrong: silently filtering a genuine split can mask needed corporate-action reconciliation; ambiguous changes remain operator-visible.

### P-codex-10: Debounce transient sync failures while preserving immediate safety alerts (Incident 3 fix 2)
- File: src/tradebot/live.py §Engine.__init__ / Engine.step
- Change: Add `self.read_failures = 0` and `self.read_failure_announced = False`; import `BrokerReadUnavailable, T212Error`. Use **N=3** as the proposed policy, subject to owner review. Persist every ERROR immediately, notify once at the threshold with stable text, and send one recovery notification. Never send a green ping for a failed/degraded sync. With P-codex-5, `sync()` returns True only after successful reconciliation/protection checks; False is a logical safety failure, not a transient network success. Candidate replacement for the body of `step()`:

```python
now = dt.datetime.now(dt.UTC)
try:
    healthy = self.sync(now)
except Exception as exc:
    self.db.event("ERROR", error=repr(exc),
                  trace=traceback.format_exc()[-3000:])
    transient = isinstance(exc, BrokerReadUnavailable) or (
        isinstance(exc, T212Error) and exc.status == 429
    )
    if transient:
        self.read_failures += 1
        if self.read_failures >= 3:
            if not self.read_failure_announced:
                self.alert("broker reads failed for 3 consecutive syncs; entries blocked")
                self.read_failure_announced = True
            notify.ping(self.env, fail=True)
    else:
        self.read_failures = 0
        self.alert(f"sync safety failure: {type(exc).__name__}: {str(exc)[:200]}")
        notify.ping(self.env, fail=True)
else:
    if healthy:
        if self.read_failure_announced:
            self.alert("broker reads recovered; reconciliation and protection verified")
        self.read_failures = 0
        self.read_failure_announced = False
        notify.ping(self.env)
    else:
        self.read_failures = 0
        notify.ping(self.env, fail=True)
open_now = any(self.session_of(s, now) for s in self.live_syms)
self.next_sync = time.time() + (SYNC_OPEN_S if open_now else SYNC_CLOSED_S)
```

  Safety trips/missing-stop alerts remain immediate in their own paths; this code must not suppress them. Persist the streak/announcement state in the journal and reconstruct it on start so repeated process restarts cannot reset N. First and second transient failures send neither success nor `/fail`; an external missed-ping alarm remains independent. Review its grace against the worst closed-session schedule: three failed syncs are roughly 20 minutes apart from first to third, plus request duration. If that is unacceptable, use a shorter retry-sync cadence rather than sending false green pings. Readiness must block new entries while a sync is incomplete.
- Why: Incident 3, docs/10-build-log.md:221,227-230; F10; notify.py:27-38; checked 2026-11-25.
- Risk if wrong: debounce can hide a persistent outage or emit false recovery. Tests must include safety failures interleaved with transient failures and restart persistence. Exact text prevents changing network exception wording from defeating the existing Telegram deduplication.

### P-codex-11: Timestamp every engine/watchdog output line in UTC (Incident 3 fix 3)
- File: src/tradebot/__main__.py
- Change: Replace this file with the following entry-point wrapper, preserving the lightweight watchdog dispatch. It timestamps prints and uncaught traceback lines before Windows redirection; journald additionally supplies host timestamps on Linux.

```python
import datetime as dt
import sys
import threading

class TimestampedStream:
    def __init__(self, stream):
        self.stream = stream
        self.at_line_start = True
        self.lock = threading.RLock()

    def write(self, text):
        with self.lock:
            for part in text.splitlines(keepends=True):
                if self.at_line_start:
                    stamp = dt.datetime.now(dt.UTC).isoformat(timespec="milliseconds")
                    self.stream.write(stamp + " ")
                self.stream.write(part)
                self.at_line_start = part.endswith(("\n", "\r"))
        return len(text)

    def flush(self):
        with self.lock:
            self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)

for name in ("stdout", "stderr"):
    stream = getattr(sys, name)
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    setattr(sys, name, TimestampedStream(stream))

if sys.argv[1:2] == ["watchdog"]:
    from .watchdog import main
else:
    from .cli import main

main()
```

- Why: Incident 3 and F10; current __main__.py:1-8 and ops/install-tasks.ps1:43-44, checked 2026-11-25.
- Risk if wrong: stream wrapping can change buffering or third-party stream expectations; test split writes, Unicode, empty writes, multiline traceback, reconfigure delegation and the no-pandas watchdog assertion. This does not add log rotation; use journald retention on the VPS and a separately reviewed rotation policy if keeping Windows files.

### P-codex-12: Support explicit Linux paths and systemd credentials
- File: src/tradebot/config.py
- Change: Add `import os`; keep `ROOT` for source identity, and replace the directory constants with:

```python
CONFIG_DIR = Path(os.environ.get("TRADEBOT_CONFIG_DIR", ROOT / "config"))
DATA_DIR = Path(os.environ.get("TRADEBOT_DATA_DIR", ROOT / "data"))
REPORTS_DIR = Path(os.environ.get("TRADEBOT_REPORTS_DIR", ROOT / "reports"))
DB_PATH = DATA_DIR / "demo.db"
```

  In `read_env`, replace only `path = ROOT / ".env"` with:

```python
credential_dir = os.environ.get("CREDENTIALS_DIRECTORY")
path = Path(credential_dir) / "tradebot.env" if credential_dir else ROOT / ".env"
if credential_dir and not path.is_file():
    raise ConfigError("systemd credential tradebot.env missing")
```

  Require absolute override paths and validate permissions at deployment. Add settings validation: allowed mode, unique known strategies, finite positive budgets, all enabled/shadow references present, and total enabled budgets <= capital cap; validate instrument strategy lists and ticker currency/schedule mappings together at startup. Provide a cross-platform process-lock helper through a separately reviewed implementation rather than treating heartbeat freshness as a lock.
- Why: F10/F12/F15; config.py:6-10,31-41,75-89; [S6c], checked 2026-11-25.
- Risk if wrong: selecting a different state path can create an empty ledger and duplicate orders. Migration must verify the exact existing ledger before starting; credential-file precedence must fail closed.

### P-codex-13: Make heartbeat publication atomic and malformed state visible
- File: src/tradebot/watchdog.py
- Change: Write heartbeat JSON to a unique temporary sibling, flush it, then atomically replace the target. Distinguish missing, malformed, stopped, starting, running and stale states; malformed existing state is a fault, not a clean stop. Track last successful sync/protection status separately from the liveness timestamp. Check pre-existing stale-running state before a restarted engine publishes a new heartbeat. Keep the standard-library-only import path and independent broker session; retain stops when tripping.
- Why: F10; watchdog.py:20-46; checked 2026-11-25.
- Risk if wrong: startup races can cause nuisance kills; false-clean handling can hide a dead engine. Coordinate ownership with P-codex-6; do not add pandas.

### P-codex-14: Make kill-state reads fail closed and writes atomic
- File: src/tradebot/risk.py §trip / is_tripped / state
- Change: Publish KILL via a flushed temporary sibling plus atomic replace; record structured audit state after successful persistence. If an existing file is unreadable/malformed, `is_tripped()` returns true and `state()` returns a structured corruption fault requiring operator review. Do not auto-reset or rewrite damaged state merely by reading it. Coordinate write/reset ownership so one process cannot overwrite another operator transition. Keep all tests redirected to temporary safety paths.
- Why: F10; risk.py:89-110; checked 2026-11-25.
- Risk if wrong: corruption handling could accidentally clear a trip or lose the original reason. Preserve original evidence and require an explicit audited reset.

### P-codex-15: Add execution fault-transition regressions
- File: tests/test_execution.py
- Change: Extend FakeT212 with staged partial fills, delayed/multiple history pages, ambiguous accepted POSTs, cancellation fills and transient failures. Implement the fill durability, stop recovery, cancellation, submit and precision rows of F16. Assert quantities/proceeds and broker POST counts, not just status labels. Include the exact reproduced cases: P&L 40, residual OPEN 1, replacement 0.6, no watermark advance without a valid fill, and ambiguous matches remaining unresolved.
- Why: F1-F6/F16; existing FakeT212.fill at tests/test_execution.py:74-78; checked 2026-11-25.
- Risk if wrong: a fake that invents broker guarantees can produce false confidence. Ground response fixtures in reviewed redacted API examples.

### P-codex-16: Add live-book and failure-policy regressions
- File: tests/test_live.py
- Change: Implement F16 shared-book/risk/data/Incident 3 cases with synthetic bars and mocked clocks/transports; test two actors reading the same state, queued request acknowledgement, all eight lots restored under KILL, and missing protection causing unhealthy sync. Assert whole-book 960 rather than per-sleeve 980. Preserve the lightweight-watchdog test and add startup ownership/corrupt-heartbeat cases.
- Why: F7-F11/F14/F16; tests/test_live.py:152-201 covers only simple ownership and queueing; checked 2026-11-25.
- Risk if wrong: mock-only tests can miss actual lock/service semantics; require a separate Linux smoke test after unit tests.

### P-codex-17: Separate standalone baselines from portfolio replay
- File: src/tradebot/live.py §forward
- Change: Rename the existing report check to “independent sleeve baseline — holdings may differ by allocation, activation, fills and catch-up policy.” Do not call differing S4 holdings evidence that seeded replay failed. Design a separately identified shared-book replay using journaled universe/config versions, activation dates, candidate sets and request/fill policy; expose reason-coded divergences.
- Why: F12; live.py:313-333; reports/daily/2026-10-05.md forward table; checked 2026-11-25.
- Risk if wrong: relabelling can excuse real bugs. Retain and investigate unexplained differences; do not retroactively change baseline results.

### P-codex-18: Make simulated same-session execution globally exit-first
- File: src/tradebot/backtest.py §run
- Change: Split each day's execution into global exit processing, then entry processing, then intraday stop processing, preserving each symbol's own fresh-session condition. Add an explicit execution-policy/version record for broker rounding and open-only versus resting DAY fills; do not overwrite existing trial outputs. Preserve the original standalone baseline as a distinct version when comparing results.
- Why: F12; backtest.py:70-97 versus execution.py:298; checked 2026-11-25.
- Risk if wrong: changes cash availability and historical results. Require a two-symbol insertion-order-invariance test and normal trial logging, not a parameter search.

### P-codex-19: Correct the S2 position-limit comment without silently changing the strategy
- File: config/risk.toml §max_positions
- Change: Replace line 5 with `max_positions = 12             # shared-book cap; strategy defaults: S1 <= 6, S2 <= 3, S3 <= 2, S4 <= 2`.
- Why: F12; strategies.py:33,87,140,181; checked 2026-11-25. The aggregate cap can bind even if individual strategy maxima sum to 13.
- Risk if wrong: if the owner intended S2 <=2, a comment-only correction is insufficient; obtain a separate explicit demo override proposal and evaluation rather than silently rewriting the frozen/default strategy.

### P-codex-20: Reconcile architecture prose with the four-strategy demo and actual guarantees
- File: docs/04-architecture.md §3/4/7/9
- Change: Replace the S2-shadow-only paragraph at line 104 with: “The current demo enables S1, S2, S3 and S4 on mapped EUR instruments. The stock strategies share ticker ownership with S2 before S3 before S4 in the configured decision order. US symbols remain research-only. The implementation has outstanding shared-book reservation and recovery defects documented in the 2026-11-25 Codex audit; independent per-strategy backtests are baselines, not exact portfolio replays.” Replace the Decimal assertion with the current float/SQLite REAL plus boundary-rounding description. Explicitly distinguish write-ahead submit intent from atomic fill accounting, and describe unresolved POST policy only after the corresponding proposal is approved/applied.
- Why: F7/F12/F13; settings.toml:8, models.py:3, store.py:15-20; checked 2026-11-25.
- Risk if wrong: prematurely documenting a proposed guarantee encourages unsafe operation; mark pending fixes plainly.

### P-codex-21: Correct the risk contract and conditional restart requirements
- File: docs/05-risk-and-safety.md §2/4/6/10
- Change: Update demo limits to 12 positions and 20 orders/day while keeping real-money gates explicitly unimplemented. State that current reset displays historical reconciliation; it does not run a fresh one. State that current sync compares positions/orders, and stop maintenance is separate; cash/equity/protection-complete checks remain release work. Record F14's restart preconditions, stale-data gaps, the disabled effective minute limiter, and the unresolved S1 EUR 5 risk interpretation. Describe session-end remainder cancellation as pending until implemented.
- Why: F8/F9/F13/F14; docs/05:19-39,79-94,141 and cited code; checked 2026-11-25.
- Risk if wrong: weakening prose must not silently weaken an intended control. Preserve each missing control as a tracked requirement.

### P-codex-22: Add the Linux demo engine service
- File: ops/systemd/tradebot-engine.service
- Change: Add this **proposed** unit after P-codex-6/12/13 and the recovery tests are implemented:

```ini
[Unit]
Description=TradeBot demo engine
Wants=network-online.target time-sync.target
After=network-online.target time-sync.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=tradebot
Group=tradebot
WorkingDirectory=/opt/tradebot
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=MPLCONFIGDIR=/var/lib/tradebot/matplotlib
Environment=TRADEBOT_CONFIG_DIR=/opt/tradebot/config
Environment=TRADEBOT_DATA_DIR=/var/lib/tradebot
Environment=TRADEBOT_REPORTS_DIR=/var/lib/tradebot/reports
LoadCredential=tradebot.env:/etc/tradebot/demo.env
ExecStartPre=/opt/tradebot/.venv/bin/python -m tradebot watchdog
ExecStart=/opt/tradebot/.venv/bin/python -m tradebot run
Restart=always
RestartSec=300
KillSignal=SIGINT
TimeoutStopSec=120
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/tradebot
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

  Provision the service account, state/cache/report directories and owner-supplied credential before installation. Install dependencies in an editable `/opt/tradebot` checkout from the current reviewed tree. Time synchronization must actually be configured/verified. The pre-start watchdog preserves detection of an old stale-running heartbeat; a network failure there may deliberately prevent startup. Units are not enabled or started by this proposal.
- Why: F15; replacement for ops/install-tasks.ps1:40-48; [S6a,S6c], checked 2026-11-25.
- Risk if wrong: wrong data path starts with an empty ledger, restart loops hide refusal, or a shutdown mid-write requires recovery. Verify unit semantics on the chosen distro; latest upstream documentation is not proof of its installed systemd version.

### P-codex-23: Add the independent Linux watchdog service
- File: ops/systemd/tradebot-watchdog.service
- Change: Add `[Unit] Description=TradeBot demo watchdog`, `Wants=network-online.target`, `After=network-online.target`; `[Service] Type=oneshot`, `User=tradebot`, `Group=tradebot`, `WorkingDirectory=/opt/tradebot`, `Environment=TRADEBOT_DATA_DIR=/var/lib/tradebot`, `Environment=PYTHONDONTWRITEBYTECODE=1`, `LoadCredential=tradebot.env:/etc/tradebot/demo.env`, `ExecStart=/opt/tradebot/.venv/bin/python -m tradebot watchdog`, `TimeoutStartSec=120`, `UMask=0077`, `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `ReadWritePaths=/var/lib/tradebot`, `StandardOutput=journal`, `StandardError=journal`, each directive on its own line. Do not bind its lifetime to the engine's service; it must remain available when the engine dies. No `Restart=always` on a oneshot.
- Why: F15; watchdog.py:50-54; [S6a,S6c], checked 2026-11-25.
- Risk if wrong: coupling watchdog lifetime to engine failure removes its independence; insufficient permissions prevent persisting KILL.

### P-codex-24: Add the one-minute watchdog timer
- File: ops/systemd/tradebot-watchdog.timer
- Change: Add:

```ini
[Unit]
Description=Check TradeBot demo heartbeat every minute
[Timer]
OnBootSec=60s
OnUnitActiveSec=60s
AccuracySec=1s
Unit=tradebot-watchdog.service
[Install]
WantedBy=timers.target
```

- Why: F15; replaces ops/install-tasks.ps1:50-56. Timers do not spawn another instance while the service is still active; default timer accuracy is one minute, so specify it [S6b], checked 2026-11-25.
- Risk if wrong: a watchdog exceeding its cadence delays detection. A 120-second deadline is an outer bound, not evidence of one-minute completion.

### P-codex-25: Add a verified SQLite backup program
- File: ops/backup.py
- Change: Implement a standard-library command that opens the configured demo DB in read-only mode, uses `sqlite3.Connection.backup()` into a unique temporary destination under `/var/backups/tradebot`, checks `PRAGMA integrity_check`, closes both connections, then atomically publishes a UTC-dated backup. Fail nonzero on any error; never silently create a missing source DB. Retain dated copies by an explicit reviewed retention policy and test restore into a separate temporary DB. No broker credentials or network calls are needed. Preserve the research cache/config/trial journal through a separate migration archive policy.
- Why: F15; ops/install-tasks.ps1:58-63 currently overwrites a single local backup; [S7], checked 2026-11-25.
- Risk if wrong: a zero-byte/missing-source backup can appear successful, or retention can erase the only recoverable state. Never prune before successful verification.

### P-codex-26: Add the nightly backup service
- File: ops/systemd/tradebot-backup.service
- Change: Add `[Unit] Description=Back up TradeBot demo ledger`; `[Service] Type=oneshot`, `User=tradebot`, `Group=tradebot`, `WorkingDirectory=/opt/tradebot`, `Environment=TRADEBOT_DATA_DIR=/var/lib/tradebot`, `Environment=PYTHONDONTWRITEBYTECODE=1`, `ExecStart=/opt/tradebot/.venv/bin/python /opt/tradebot/ops/backup.py`, `TimeoutStartSec=300`, `UMask=0077`, `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `ReadWritePaths=/var/backups/tradebot /var/lib/tradebot`, `StandardOutput=journal`, `StandardError=journal`, each on its own line. The state directory remains writable for SQLite WAL coordination; application source opens read-only. Grant no credentials. Monitor nonzero backup status independently.
- Why: F15; P-codex-25; [S6a,S6c,S7], checked 2026-11-25.
- Risk if wrong: a timer can appear active while backups fail. Confirm ownership, restoreability and space limits before relying on it.

### P-codex-27: Add a persistent nightly backup timer
- File: ops/systemd/tradebot-backup.timer
- Change: Add:

```ini
[Unit]
Description=Nightly TradeBot demo ledger backup
[Timer]
OnCalendar=*-*-* 03:00:00 UTC
Persistent=true
AccuracySec=1min
Unit=tradebot-backup.service
[Install]
WantedBy=timers.target
```

- Why: F15; [S6b], checked 2026-11-25. A persistent calendar timer catches a missed scheduled activation after downtime; it does not replace backup success/restore monitoring.
- Risk if wrong: unexpected timezone/catch-up behavior or storage exhaustion. Verify the calendar expression and unit files with the target host's systemd tools before enabling them.

### P-codex-28: Test adapter retries against real response shapes
- File: tests/test_trading212.py
- Change: Add mocked transport cases for GET recovery/exhaustion, 401/403/404 non-retry, bounded rate waits, POST 408/5xx/timeout/truncated responses never automatically repeated, and GET history pagination with duplicate fill IDs. Assert transport call counts and normalized cumulative cost; include documented quantity-order responses with no filledValue. Keep the demo-only URL rejection test.
- Why: F3/F5 and P-codex-4; tests/test_trading212.py currently tests 429 and clock skew but not these cases; [S2-S5], checked 2026-11-25.
- Risk if wrong: schema fixtures can conceal broker changes; retain their source/check date and validate sanitized real examples in a later authorized read-only round.

### P-codex-29: Test all strategy budgets and mapping validation
- File: tests/test_config.py
- Change: Replace the S1+S2-only budget assertion with the sum over enabled strategies and add malformed/unknown/duplicate strategy, absent budget, negative/NaN budget, mismatched currency/schedule and override-path tests. Test systemd credential precedence and missing-credential refusal with synthetic temporary files containing dummy values only.
- Why: F12/F15; tests/test_config.py:11; P-codex-12; checked 2026-11-25.
- Risk if wrong: tests that only mirror the implementation will miss semantic conflicts; assert the owner cap and same-ledger invariants independently.

## Open questions for round 2

1. **Claude/owner:** approve a stricter UNKNOWN policy with no automatic ambiguous-POST resubmit, or explicitly accept the residual duplicate risk of the existing two-empty-lookups rule? Current external API docs offer no idempotency guarantee.
2. **Owner:** what fresh read-only inventory exists for the eight holdings, pending orders and corporate actions since October 6? What are the intended stop levels now? This audit deliberately did not access credentials/account state.
3. **Other code reviewer:** obtain sanitized partial-entry/partial-stop/history-page examples, including fill IDs, fill timestamps, quantity-order `filledValue` absence and REPLACED successor relationships. Do not expose secrets. Which precision rules apply to each current residual holding?
4. **Claude/owner:** is EUR 5 entry-to-stop risk universal, including S1, or is weighted S1 an approved exception? Is S2's intended demo maximum two or its implemented default three? Resolve policy before modifying frozen parameters.
5. **Owner/operations agent:** which Linux distribution/systemd version and EU host will be used? Confirm NTP, resource budget, API/data reachability, backup destination, credential provisioning, fixed-address policy and single-host handover. Provider prices/availability were outside this audit and are **UNVERIFIED** here.
6. **Owner:** approve N=3 and the desired maximum outage detection time. Is roughly 20 minutes from first to third closed-session failure acceptable, or should retries become more frequent? What is the paused external monitor's current interval/grace? **UNVERIFIED** in this round.
7. **Claude:** arrange a full `uv run pytest -q` on the intended Python/runtime with existing uncommitted work preserved. Then run the fault-transition matrix and Linux service/restore smoke tests. The 53-test fallback must not be presented as a 93-test full pass.
8. **Quant agents:** define a shared-book replay contract and activation/ownership policy. How should foregone S4 choices and S2/S3 collisions be counted? Independent sleeve results cannot validate exact combined-book behavior.
9. **Owner:** specify the controlled disposition if a current stop cannot be placed at the old level or full residual quantity. HALT alone does not protect an already unprotected holding; any close/adjustment requires explicit later authorization.
10. **Claude:** split approved changes into reviewable implementation sets: atomic fill/accounting + regressions; protection/UNKNOWN protocol; book/risk/request ownership; Incident 3; deployment. Apply only after handbook votes; no restart is implied by accepting this report.

## Sources

**Local primary evidence, read/checked 2026-11-25:** `Agent-Guide.md` Parts 2-5; `README.md`; `git status --short`, `git diff --stat`, and working-tree diff for src/tests/config; `src/tradebot/*.py`, `tests/*.py`, `ops/install-tasks.ps1`, `config/*.toml`; `docs/04-architecture.md`, `docs/05-risk-and-safety.md`, `docs/10-build-log.md` (especially 189-239), and VPS-related passages of `docs/09-hosting.md`; `reports/daily/2026-10-05.md`. Findings cite the relevant lines. No new performance backtest/grid was run and no return claim is made.

**Audit observations, 2026-11-25:** requested uv failures; available interpreter discovery; 53 passing fallback tests; 31-file AST parse; in-memory reproductions of lost fill mutation, cumulative-sell P&L error, late entry fill after stop closure, missing fill price, stale replacement-stop quantity, ambiguous matching, HTTP 408 classification, and incomplete multi-sleeve valuation. These are local engineering experiments, not broker experiments.

External primary sources checked **2026-11-25**:

- **[S1]** Trading 212, [Public API overview](https://docs.trading212.com/api): demo URL, main-account-currency limitation and optional IP restriction. No broker orders were sent.
- **[S2]** Trading 212, [Get historical orders data](https://docs.trading212.com/api/historical-events/orders_1.md): pagination, order/fill fields, fill quantities/IDs/timestamps, quantity/value distinction and status enum.
- **[S3]** Trading 212, [Place a Stop order](https://docs.trading212.com/api/orders/placestoporder_1.md): stop-to-market behavior, negative sell quantity, GTC, non-idempotency, status enum and 408 response. Acceptance behavior for a stale stop level or a particular precision remains **UNVERIFIED**.
- **[S4]** Trading 212, [Place a Limit order](https://docs.trading212.com/api/orders/placelimitorder.md): non-idempotency, request pacing, DAY validity and 408 response.
- **[S5]** Trading 212, [Rate limiting and pagination](https://docs.trading212.com/api/section/rate-limiting): per-account limits, reset headers, maximum page size and `nextPagePath`.
- **[S6a]** systemd, [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html): process supervision, restart semantics and oneshot restrictions.
- **[S6b]** systemd, [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html): calendar/monotonic activation, accuracy, persistence and active-service behavior.
- **[S6c]** systemd, [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html): execution environment, output routing, filesystem controls and credentials directory. The proposed units still require validation against the selected distribution's installed version.
- **[S7]** Python, [sqlite3 transaction control and backup](https://docs.python.org/3/library/sqlite3.html): explicit transaction behavior and connection backup API. Existing behavior was additionally verified with local in-memory reproductions.
- **[S8]** Python, [http.client exceptions](https://docs.python.org/3/library/http.client.html): HTTP response-read failures to account for in GET retry classification.

Tool limitation: the required local browser-harness skill was read and its command attempted, but its executable failed with “uv trampoline failed to canonicalize script path.” Public primary documents were then retrieved using the available web lookup tool. No authenticated browser session or account was accessed.
