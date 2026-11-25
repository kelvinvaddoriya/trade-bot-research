# Antigravity - Strategies and evaluation (round 1, 2026-11-25)

## Summary

- **S1 (`s1_trend`) does not behave as a monthly SMA(200) trend filter:** its `3×ATR(20)` trailing stop triggers **95–99% of all exits** (200/210 in-sample, 88/89 holdout, 25/27 recent), inflating turnover to 5.3–6.9×/yr and halving in-sample CAGR (`+3.37%`, Sharpe `0.45`) versus pure SMA(200) (`+6.57%`, Sharpe `0.69`, turnover `1.1×/yr`, max DD `-15.7%`). Keep S1 frozen for P1–P2, then test stop width via walk-forward.
- **S2 (`s2_pullback`) failed for two distinct regional reasons obscured by a missing US/EU split:** in-sample (2007–2019), P0 US-8 had a strong gross edge (Sharpe `0.82`, heavy survivorship bias) crushed by Trading 212's 0.15%/side FX fee (Sharpe `0.67` without FX → `0.23` with FX), whereas EU-6/EU-18 had weak gross edge (EU-6 gross Sharpe `0.24`, EU-18 live-config net CAGR `-2.00%`, Sharpe `-0.06`, DD `-50.0%`). Trading 212's Public API still lacks multi-currency wallet routing (verified 2026-11-25), so the 0.15%/side FX fee is genuinely binding for automated US trades.
- **Code/config bug breaks S2's €140 demo budget:** `S2Pullback` still hardcodes `max_positions = 3, max_position_eur = 200.0` (`src/tradebot/strategies.py:87-88`) despite `config/settings.toml:13` cutting its budget to €140 and `config/risk.toml:5` commenting `S2/S3/S4 <= 2 each`, causing **1,100 `sizing: below minimum order` rejections** in `reports/backtest_s2_pullback_insample_2026-09-30.md:39`.
- **S3 (`s3_breakout`) and S4 (`s4_monkey`) reports do not match the live universe, and single-seed S4 is path-fragile:** `docs/10-build-log.md:167-174` reports 26 US+EU stocks (where NVDA alone generated €86.83 of S3's €116 net profit), whereas live demo trades only 18 German stocks—where S3 barely survives 2× costs (`+0.15%` CAGR, PF `0.98`, Sharpe `0.10`, MinTRL `39.1y`). A routine Yahoo refresh between 2026-09-30 and 2026-10-05 flipped single-seed `s4_monkey` 1× CAGR from `+1.35%` to `-7.57%`; 10-seed EU-18 dispersion spans `-5.79%` to `+2.07%` CAGR.
- **Daily forward checks (`reports/daily/`) show structural false mismatches, and demo fills cannot validate live spreads:** `live.py:313-333` backtests from global `live.start = 2026-09-28` (before S2/S3/S4 launched on 2026-09-30) and ignores the live shared-book `taken` exclusion (`live.py:94`). Demo fills on 2026-10-02 matched Yahoo Xetra opens to `0.000%` on all 4 S1 ETFs (practice-account artefact), while DHL's 21-minute delayed exit on 2026-10-05 suffered `+0.353%` adverse slippage (3.5× the 0.10% EU cost model).
- **Promotion gates in `docs/06-backtesting.md §7` are statistically underpowered and leak false positives:** over a 5-year holdout (`SE ≈ 0.45`), the `holdout Sharpe >= 0.5 × IS Sharpe` gate passes a zero-skill (`SR = 0`) strategy **30.7%** of the time (given `IS SR = 0.45`) and rejects a genuinely strong (`SR = 0.45`) strategy **31.6%** of the time. S1's Deflated Sharpe Ratio (DSR) across its 20 logged in-sample trials is **40.0%** (`63.5%` at `N_eff = 6`), yet DSR is never computed or enforced.
- **2024–2026 literature supports slow monthly trend/momentum over short-horizon mean reversion:** Kurth et al. (2026) document structural post-2008 decay in short-term signals on small-tick assets while slower trends persist; Sepp & Lucic (2026) formalize low-frequency trend spectral mass under friction; Chen & Velikov (2023) and Detzel, Novy-Marx & Velikov (2023) show high-turnover published anomalies net ~4–8 bps/mo after spreads and decay.
- **Two testable, EUR-only S2 replacements proposed (holdout untouched):** (1) **C1 — 52-Week High Cross-Sectional Momentum with SMA(200) filter and rank banding on EUR large caps** (monthly, keeps single-stock entries for the R1 LLM desk; unoptimized IS: `+4.21%` / `+3.88%` 2×, turnover `6.0×/yr`, costs `13.1%` of gross); (2) **C2 — Dual Momentum (Relative + Absolute) on EUR UCITS ETFs** (monthly, zero survivorship bias; unoptimized IS: `+2.29%` / `+1.73%` 2×, costs `21.1%` of gross).
- **Walk-forward plan for S1 designed without breaking the parameter freeze:** keep frozen S1 (`sma_n=200, check=M, atr_mult=3.0`) on demo for P1–P2; run a pre-registered 5y-train / 1y-test rolling walk-forward on 2007–2019 in-sample first (testing trailing vs catastrophic broker stop as `S1b`), logging every fold in `data/trials.jsonl` and treating 2020–2024 as already spent for S1 (evaluating `S1b` strictly forward + on post-2024 data).
- **Small documentation/code defects found:** `docs/3paperresearch.md:69` claims `pandas` Spearman correlation needs no `scipy` (actually raises `ModuleNotFoundError: No module named 'scipy'`); `report.py` omits US/EU split, proxy overlap tracking difference (`-0.53%` to `+0.57%/yr`, daily corr `0.56–0.76`), and max-single-year profit check required by `docs/06`; `backtest.py:106` uses fixed `% of budget` drawdown instead of `live.py:300`'s `% of cap`.

---

## Findings

### F1 — S2 cost model is operationally accurate for Trading 212 API, but `docs/10` misdiagnoses S2's failure by omitting the required US/EU split
- **Claim:** S2's P0 failure verdict is correct, and Trading 212's 0.15%/side FX fee is genuinely unavoidable via the Public API today. However, the failure mechanism differs sharply between US and EU stocks: US-8 had a substantial (survivorship-biased) gross edge destroyed by the FX fee, whereas EU stocks have almost no gross edge even before costs. `report.py` fails to implement the US/EU split mandated by `docs/06-backtesting.md:58,128`.
- **Evidence:**
  - Trading 212's Invest UI supports multi-currency wallets to avoid repeated 0.15% FX fees, **but the Public API executes orders in the primary account currency with no wallet/currency routing parameter**, triggering the 0.15% FX fee on every USD buy and sell ([Trading 212 Help Centre — Multi-currency](https://helpcentre.trading212.com/hc/en-us/articles/1500001809042) & [Trading 212 Community — API multi-currency limitation](https://community.trading212.com/t/trading-212-api-update/87988), checked 2026-11-25). Thus `config/settings.toml:20` (`us_fx_fee = 0.0015`) is accurate at `1×`.
  - One cost-model distortion: `src/tradebot/sim.py:12-13` multiplies both `us_slippage` **and** contractual `us_fx_fee` by `mult = 2.0` (`0.30%/side = 0.60%` round-trip FX). Slippage/spread is uncertain and should be stressed at `2×`; the fixed 0.15% FX tariff is known and doubling it exaggerates 2× US drag.
  - Read-only in-sample (2007–2019, holdout untouched) decomposition of `S2Pullback` against `data/research.db` (`config/instruments.toml`, `src/tradebot/backtest.py:39-152`):

| S2 Slice (2007–2019 IS) | Budget | Costs | CAGR | Sharpe | Max DD | Trades | PF | Costs (€) |
|---|---|---|---|---|---|---|---|---|
| P0 14-stock (reported) | €400 | 1× (FX+slip) | -0.11% | +0.02 | -18.8% | 935 | 0.99 | 275.1 |
| P0 14-stock | €400 | 0× (gross) | +4.13% | +0.69 | -12.5% | 940 | 1.33 | 0.0 |
| P0 14-stock | €400 | Slip only (no FX) | +2.29% | +0.37 | -14.1% | 943 | 1.15 | 145.6 |
| P0 US-8 only | €400 | 0× (gross) | +3.95% | +0.82 | -9.1% | 591 | 1.50 | 0.0 |
| P0 US-8 only | €400 | Slip only (no FX) | +3.31% | +0.67 | -9.4% | 593 | 1.39 | 58.1 |
| P0 US-8 only | €400 | 1× (FX+slip) | +1.17% | +0.23 | -14.3% | 594 | 1.11 | 231.2 |
| P0 EU-6 only | €400 | 0× (gross) | +1.19% | +0.24 | -9.9% | 557 | 1.13 | 0.0 |
| P0 EU-6 only | €400 | 1× (0.10% slip) | -1.20% | -0.18 | -18.6% | 557 | 0.89 | 110.8 |
| 09-30 EU-18 (live config) | €140 | 1× (0.10% slip) | -2.00% | -0.06 | -50.0% | 643 | 0.92 | 70.2 |
| 09-30 EU-18 (fixed 2×€65) | €140 | 1× / 2× | -1.80% / -7.34% | -0.06 / -0.48 | -48.2% / -69.2% | 697 / 585 | 0.93 / 0.73 | 72.6 / 98.5 |

  - Note survivorship bias: P0's US-8 universe (`AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, XOM`) has an equal-weight IS benchmark CAGR of **+18.8%/yr** (`reports/backtest_s2_pullback_insample_2026-09-25.md:21`). Even with extreme mega-cap survivorship bias, S2 fails net of Trading 212 API costs.
  - EU-18 at `0.10%/side` slippage is conservative for blue-chip Xetra DAX stocks during core hours (Deutsche Börse Xetra Liquidity Measure / XLM for DAX constituents and major ETFs is typically single-digit bps round-trip; [Deutsche Börse XLM](https://www.deutsche-boerse-cash-market.com/dbcm-en/instruments-statistics/statistics/xlm-xetra-liquidity-measure), checked 2026-11-25), **but** orders fire at `open + 2 min` (`src/tradebot/live.py:32`), when intraday XLM (iXLM) spreads and volatility are widest—and real demo fills showed timing slippage up to `+0.353%` (see F5).
  - Rank-based Spearman IC of `-RSI(2)` (conditioned on `close > SMA(200)`) vs 3-day / 5-day forward open-to-open returns (2007–2019 IS): `+0.0244` / `+0.0353` across 26 stocks (`+0.0199` / `+0.0389` US-8; `+0.0268` / `+0.0333` EU-18). A tiny gross short-horizon bounce exists, confirming `docs/10-build-log.md:522`, but turnover (36–66×/yr) wipes it out.
- **Severity:** HIGH
- **Confidence:** HIGH

### F2 — `S2Pullback` position caps contradict `settings.toml` and `risk.toml`, causing 1,100 sizing rejections
- **Claim:** When S2's budget was reduced from €400 to €140 on 2026-09-30 (`config/settings.toml:13`), `S2Pullback` kept `max_positions = 3, max_position_eur = 200.0` (`src/tradebot/strategies.py:87-88`) while `config/risk.toml:5` claims `# S1 <= 6, S2/S3/S4 <= 2 each`. In addition, `backtest.py:125` and `live.py:106` scale `capital = min(cap, cap * equity / budget)`, so €5 nominal trade risk equals **3.57–3.85% of sleeve equity** on €130–€140 sleeves, consuming nearly the entire €140 budget in 1–2 positions and causing 1,100+ rejections.
- **Evidence:**
  - `src/tradebot/strategies.py:87-88` (`max_positions: int = 3`, `max_position_eur: float = 200.0`) vs `S3Breakout`/`S4Monkey` (`max_positions = 2`, `max_position_eur = 65.0`, `strategies.py:139-140, 178-179`).
  - `reports/backtest_s2_pullback_insample_2026-09-30.md:7,13,39`: budget €140, `max_position_eur: 200.0`, `rejections: sizing: below minimum order ×1100`.
  - `reports/backtest_s2_pullback_recent_2026-09-30.md:39`: `sizing: below minimum order ×142` in just 21 months.
  - Fixing S2 to `max_positions = 2, max_position_eur = 65.0` cuts EU-18 IS `below minimum order` rejections from **857 → 122** (read-only verification above).
  - Live evidence: on 2026-10-01 (`reports/daily/2026-10-01.md:38-39`), S2 sized BAYN at `1.447 × 45.85 = €66.35` and DHL at `1.307 × 56.30 = €73.58` (total €139.93 of €140, leaving €0.07 cash—forcing slot 3 to always reject).
- **Severity:** HIGH
- **Confidence:** HIGH

### F3 — S1 is dominated by its `3×ATR(20)` trailing stop (95–99% of exits), not its SMA(200) trend filter
- **Claim:** `docs/03-strategies.md:43-46` and `src/tradebot/strategies.py:25` describe S1 as a monthly SMA(200) trend filter (`hold while close > SMA(200)`). In reality, raising the broker stop to `close - 3×ATR(20)` at month-end causes **95–99% of all exits** to occur via intramonth stop-outs while `close > SMA(200)`, creating 5× higher turnover, 49–57% exposure, and half the CAGR of a pure SMA(200) filter.
- **Evidence:**
  - Exit-reason counts in filed reports:
    - In-sample (`reports/backtest_s1_trend_insample_2026-09-25.md:72`): `protective stop ×200, trend lost: close <= SMA ×10` (**95.2%** stops).
    - Holdout (`reports/backtest_s1_trend_holdout_2026-09-25.md:64`): `protective stop ×88, trend lost: close <= SMA ×1` (**98.9%** stops).
    - Recent (`reports/backtest_s1_trend_recent_2026-09-25.md:61`): `protective stop ×25, trend lost: close <= SMA ×2` (**92.6%** stops).
  - Read-only in-sample sensitivity (2007–2019 ONLY; holdout NOT touched) varying `atr_mult` in `S1Trend`:

| `S1Trend` `atr_mult` (2007–2019 IS) | CAGR (1× / 2×) | Sharpe (1×) | Max DD | Trades (stop exits) | Exposure | Turnover/yr |
|---|---|---|---|---|---|---|
| `2.0` | +3.58% / +2.72% | 0.56 | -7.8% | 269 (263) | 39% | 6.4× |
| `3.0` (frozen default) | +3.37% / +2.95% | 0.45 | -12.4% | 210 (200) | 49% | 5.3× |
| `4.0` | +3.51% / +3.15% | 0.44 | -14.1% | 167 (151) | 55% | 4.1× |
| `5.0` | +3.40% / +3.07% | 0.41 | -20.0% | 132 (116) | 61% | 3.3× |
| `6.0` | +3.77% / +3.59% | 0.44 | -24.7% | 105 (86) | 63% | 2.5× |
| `99.0` (pure SMA200, no trail) | **+6.57% / +6.47%** | **0.69** | **-15.7%** | **53 (0)** | **62%** | **1.1×** |

  - Notice the non-monotonic drawdown curve: intermediate trailing stops (`4–6×ATR`) worsen drawdown (`-20%` to `-24.7%`) by stopping out near correction troughs and sitting in cash until month-end, whereas pure SMA(200) (which can still carry a wide, **non-trailing** catastrophic broker stop, e.g., `-15%` from entry, to preserve `docs/03 §1`'s resting-stop safety rule) cuts turnover 5× and doubles CAGR.
  - Per the parameter freeze (`docs/10-build-log.md:491-493`), S1 MUST NOT be altered mid-P1/P2; this becomes Hypothesis H1 in the walk-forward plan (F10).
- **Severity:** HIGH
- **Confidence:** HIGH

### F4 — S3 (Donchian) and S4 (Monkey) reports mismatch the live EU-18 universe; single-seed S4 is unstable
- **Claim:** The 2026-09-30 backtests for S2, S3, and S4 (`docs/10-build-log.md:167-178`, `reports/backtest_s3_*`, `reports/backtest_s4_*`) ran on **26 US+EU stocks**, whereas `live.py:180-183` restricts live demo trading to **18 German EUR stocks**. On the actual EU-18 universe, S3's edge almost vanishes at 2× costs; moreover, single-seed `S4Monkey` exhibits a 9 percentage-point CAGR flip after a routine Yahoo cache refresh.
- **Evidence:**
  - Universe mismatch: `reports/backtest_s3_breakout_insample_2026-09-30.md:8,89` includes 8 US stocks; **NVDA alone produced +€86.83** of S3's €116 net profit (`€246 − €130`), and ADS added +€56.09—2 of 25 stocks account for >120% of total profit.
  - Read-only 2007–2019 in-sample comparison (`data/research.db`, €130 budget):
    - **S3 all-26:** `1× +5.03% (SR 0.35, PF 1.32)` / `2× +3.35% (SR 0.26, PF 1.21)`.
    - **S3 live EU-18:** `1× +3.02% (SR 0.26, PF 1.19, DD -35.5%, MinTRL 39.1y)` / `2× +0.15% (SR 0.10, PF 0.98, DD -40.7%)` — **fails `PF > 1` at 2× costs**.
    - S3 continuous breakout signal `(close/hi20 - 1)` has **negative** 20-day Spearman IC (`-0.0282` all-26; `-0.0334` EU-18) across all days (unconditional mean reversion on stocks), meaning S3's slight positive return comes from convex stop/trailing-exit payoff asymmetry (`avg win €5.37 / avg loss -€2.42`, win rate `37%`), not positive linear rank IC.
  - **Path-dependence anomaly in S3 recent report:** `reports/backtest_s3_breakout_recent_2026-09-30.md:21-26` shows **2× costs (`+35.4%` CAGR, Sharpe `1.76`, DD `-8.2%`) outperforming 1× costs (`+31.5%` CAGR, Sharpe `1.58`, DD `-11.1%`)** across 34 trades—caused by 2-slot capacity forcing slightly different fills/rejections onto a lucky winner (`GOOGL +€23.19`, `NVDA +€14.05`).
  - **S4 reproducibility & single-seed fragility:** `reports/backtest_s4_monkey_insample_2026-09-30.md:21` reported `1× +1.3% (1,121 trades, 962 min-order rej)` and `2× -12.2% (866 trades)`. Re-running the exact same code (`src/tradebot/strategies.py:170-204`) on `data/research.db` today reproduces `2×` to 4 decimals (`-12.18%`, `866` trades) and reproduces `1×` identically through 2007–2010 (`-10.0%, -42.7%, +19.3%, -5.8%`), then diverges in 2011 (`-2.0%` vs `+0.3%`) and collapses to **`-7.57%` CAGR (`917` trades, `2,021` min-order rej)** after `live.py:188` refreshed 24 EUR Yahoo series on 2026-10-05. Across 10 random seeds on EU-18 (IS 2007–2019, 1×), `S4Monkey` spans **CAGR `-5.79%` to `+2.07%` (median `-3.50%`), Sharpe `-0.22` to `+0.20` (median `-0.09`)**. A single seed cannot serve as a statistical null hypothesis in backtests.
- **Severity:** HIGH
- **Confidence:** HIGH

### F5 — Live demo vs backtest forward check (`reports/daily/`) fails structurally; demo fills show timing risk and practice-account artefacts
- **Claim:** Comparing all 7 daily reports (`reports/daily/2026-09-25.md` through `2026-10-05.md`) and `data/demo.db` against `backtest.run()` reveals that the forward check (`src/tradebot/live.py:313-333`) is **structurally guaranteed to report `**differs**`** for S2 and S4 even with bug-free execution, and that practice-account fills cannot validate live spread assumptions.
- **Evidence:**
  - **Forward-check mismatches traced to 3 root causes:**
    1. **Global start date (`config/settings.toml:5`):** `live.start = "2026-09-28"` applies to all 4 strategies, even though S2/S3/S4 were deployed on `2026-09-30 13:18 CEST` (`docs/10-build-log.md:185`). Backtesting from `09-28` entered `BAS` (S2), `BAYN` stopped out `-€3.09` (S3), and `AIR, SAP` (S4) before those strategies existed live (`reports/daily/2026-09-30.md:52-54`, `2026-10-05.md:65-68`). Replaying from `2026-09-30` fixes S2's holdings (`BAYN`, 1 closed trade `DHL` matching live) and S3 (`IFX`, 0 closed trades matching live).
    2. **Oct 1 quantity-precision kill-switch cascade (`docs/10-build-log.md:189-213`):** 3 HTTP 400 rejections (`DTE`, `EXW1`, `IS3N`) tripped the kill switch at `07:04 UTC`, cancelling S1's `09-30` entries (causing `differs` on `2026-10-01.md:63`, later aligned by `cycle --force` on `10-01` close → `10-02` fill) and rejecting S4's `DTE` (leaving only `ALV`, so S4 picked `BMW` on `10-01` instead of holding `ALV, DTE` as in the `09-30` replay).
    3. **Missing shared-book exclusion in `forward()` (`live.py:94` vs `live.py:324`):** Live `decide()` excludes symbols held or planned by any other strategy (`taken`), whereas `forward()` runs `backtest.run()` independently per strategy. Whenever two stock strategies pick the same ticker, `forward()` will falsely flag `**differs**`.
  - **Live demo execution vs Yahoo opens (`data/demo.db` vs `data/research.db`, 10 strategy fills 2026-10-01..10-05):**

| Date | Strategy | Role | Symbol | Fill (€) | Yahoo Open (€) | Diff vs Open | Fill Time (UTC) | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-10-01 | `s4_monkey` | entry | ALV | 410.80 | 412.20 | -0.340% | 07:10:33 | Favorable drift |
| 2026-10-02 | `s1_trend` | entry | SXR8 | 737.12 | 737.12 | **0.000%** | 07:09:34 | Exact Yahoo open |
| 2026-10-02 | `s1_trend` | entry | EXW1 | 62.45 | 62.45 | **0.000%** | 07:09:35 | Exact Yahoo open |
| 2026-10-02 | `s1_trend` | entry | IS3N | 48.846 | 48.846 | **0.000%** | 07:09:35 | Exact Yahoo open |
| 2026-10-02 | `s1_trend` | entry | SXRV | 1564.60 | 1564.60 | **0.000%** | 07:11:43 | Exact Yahoo open |
| 2026-10-02 | `s2_pullback` | entry | BAYN | 44.81 | 45.00 | -0.422% | 07:07:29 | Favorable drift |
| 2026-10-02 | `s2_pullback` | entry | DHL | 55.92 | 56.28 | -0.640% | 07:07:29 | Favorable drift |
| 2026-10-02 | `s4_monkey` | entry | BMW | 54.78 | 54.90 | -0.219% | 07:07:29 | Favorable drift |
| 2026-10-05 | `s2_pullback` | exit | DHL | 56.44 | 56.64 | **+0.353%** | 07:21:09 | **3 cancel timeouts delayed exit 21 min** |
| 2026-10-05 | `s3_breakout` | entry | IFX | 64.39 | 64.69 | -0.464% | 07:21:10 | Favorable drift |

  - All 4 S1 ETF fills matched Yahoo's open to 4 decimal places despite submitting at `07:03 UTC` and filling at `07:09–07:11 UTC`—consistent with Trading 212's practice engine filling against Xetra's delayed first ETF print with zero simulated spread/impact. Conversely, `DHL`'s exit suffered 3 consecutive `RuntimeError('cancel of order 55850837740 (DHL) not confirmed')` failures (`reports/daily/2026-10-05.md:48-53`), delaying execution to `07:21 UTC` with `+0.353%` adverse slippage (**3.5×** the `0.10%` model).
  - Total demo result before Incident 3 shutdown (`reports/daily/2026-10-05.md:4-13`): book equity `€1,007.76` (`+0.78%`), 1 closed strategy trade (`DHL +€0.68`), 8 open lots (`ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV, IFX`) currently held **without stops** (`docs/10-build-log.md:235-239`).
- **Severity:** HIGH
- **Confidence:** HIGH

### F6 — Promotion gates in `docs/06-backtesting.md §7` are statistically unsound at this sample size
- **Claim:** The `Idea → Demo` and `Demo → Gated live` gates in `docs/06-backtesting.md:112-120` suffer from severe Type I/II error, omit multiple-testing control promised earlier in `docs/06`, lack an in-sample Sharpe floor, and specify an 8-week demo duration that covers only 1–2 S1 check days.
- **Evidence:**
  - **Analytical power of `holdout Sharpe >= 0.5 × IS Sharpe`** (`T_IS = 13y`, `T_OOS = 5y`, i.i.d. Lo 2002 `SE_OOS = sqrt((1 + SR²/2)/5) ≈ 0.45–0.47`):
    - **False-positive rate (Type I error):** A pure-noise strategy (`true SR = 0`) that achieved `IS SR = 0.45` by luck/selection clears `SR_OOS >= 0.225` with probability **30.7%** (`25.1%` if `IS SR = 0.60`). Almost 1 in 3 overfit strategies pass.
    - **False-negative rate (Type II error):** A genuinely strong strategy (`true SR = 0.45`) fails the 5-year holdout gate **31.6%** of the time (`37.5%` if `IS SR = 0.60`; still **28.1%** at `true SR = 0.50`).
    - **Missing floor:** Because the rule is purely multiplicative (`0.5 × IS`), a strategy with `IS SR = 0.04` and `OOS SR = 0.02` technically passes if `2× costs > 0`!
  - **S1 non-normality, autocorrelation, DSR, and MinTRL** (computed read-only from `S1Trend` IS daily returns, `n = 3,315` days, `12.99` years, following López de Prado, Lipton & Zoonekynd 2026 *JPM* / SSRN 5520741 & Bailey & López de Prado 2014):
    - `SR = 0.454`, skewness `-0.268`, Pearson kurtosis `9.785` (excess `+6.79`), lag-1 autocorrelation `rho1 = -0.115`.
    - Naive i.i.d. `SE = 0.291`; non-normal Mertens/PSR `SE = 0.277`; Lo (2002) AR(1) `SE = 0.260`.
    - `PSR(SR* = 0) = 94.9%` (one-sided borderline for a single pre-specified trial).
    - `MinTRL(95%, SR* = 0) = 13.25 years` — S1's 13.0-year IS barely reaches the 1-trial minimum track record length (and S3 EU-18 needs **39.1 years**).
    - **Deflated Sharpe Ratio (DSR):** `data/trials.jsonl` contains **127 total rows** (`22` S1 IS trials: `18` grid + `4` backtest `1×/2×`, `20` at `1×`; `89` S2 IS trials; `2` S3 IS; `2` S4 IS; `2` S1 holdout). Across `N = 20` independent trials, `E[max SR_0] = 0.524 > 0.454` → **`DSR = 40.0%`**. Even accounting for high correlation across the 18 grid cells (`N_eff = 5–6`), `E[max SR_0] = 0.329–0.359` → **`DSR = 63.5%–67.4%`**, far below a 95% discovery threshold. Crucially, `docs/06 §1, §2.6, §4` mandate DSR, yet `src/tradebot/backtest.py` and `report.py` **never compute it**.
    - Note nuance in S1's favor: S1 was frozen at its **pre-specified textbook default** (`sma_n=200, check=M, atr_mult=3.0`, rank 11 of 18 in the grid, NOT the grid maximum!), so selection bias on S1 is closer to `N_eff = 1–3` (`DSR = 78.5%–94.9%`) than `N = 20`. The gate should distinguish *pre-registered defaults* (`N_eff ≈ 1` + plateau check) from *grid-selected parameters* (full `N_eff` DSR penalty).
  - **Other §7 gaps:**
    - `Demo → Gated live` requires `≥ 8 weeks` + `100% signal match`. For monthly S1, 8 weeks is only **1–2 decision cycles** (sufficient to test pipeline/stops/reconciliation, NOT slippage distribution or trail behavior).
    - `Max drawdown acceptable vs benchmark` has no quantitative threshold (e.g., `MaxDD_strat <= 0.6 × MaxDD_bench` or `Calmar_strat >= Calmar_bench`).
    - `Any → Stop` (`live results materially worse than backtest replay for 3 months`) is undefined ("materially worse" has no numeric z-score/bps band).
- **Severity:** HIGH
- **Confidence:** HIGH

### F7 — 2024–2026 academic & practitioner evidence validates slow ETF trend/momentum and explains S2's collapse
- **Claim:** Current 2023–2026 empirical finance literature directly explains why S1-style monthly trend filters remain viable for a €1,000 EUR retail account while S2-style 2-to-5-day RSI(2) mean reversion fails after costs.
- **Evidence (all checked 2026-11-25):**
  1. **Demise of short-term signals vs persistence of slow trends:** Kurth, Eisler, Rej & Bouchaud (July 2026), *"Is Trend Still Your Friend?: A Microstructural Account of the Demise of Short-Term Trend-Following"* (`arXiv:2607.01550`), analyze ~100 liquid contracts (1995–2025) and show short-horizon trend signals collapsed post-2008 on small-tick electronic markets due to defensive HFT market-making, whereas longer-horizon (multi-week/monthly) trends remained resilient.
  2. **Mathematical bounds on trend-following under costs:** Sepp & Lucic (July 2026), *"The Science and Practice of Trend-Following Systems"* (`arXiv:2607.19497`), derive closed-form net Sharpe ratios and cost-optimal filter spans, proving trend-following profitability comes from low-frequency spectral mass and structural positive skewness—both destroyed by excessive turnover/tight stops. Moskowitz, Sabbatucci, Tamoni & Uhl (Dec 2025), *"Nonlinear Time Series Momentum"* (`SSRN:5933974` / `doi:10.2139/ssrn.5933974`), confirm persistent TSMOM predictability across global asset classes with nonlinear dampening at extreme moves.
  3. **Post-publication decay + transaction cost wipeout of short-term anomalies:** Chen & Velikov (2023), *"Zeroing in on the Expected Returns of Anomalies"* (*JFQA*, 120–204 anomalies), combine effective bid-ask spreads, McLean & Pontiff (2016) post-publication decay (~50–58%), and post-2005 electronic trading to show the average published anomaly nets only **~4–8 bps/month**. Detzel, Novy-Marx & Velikov (2023), *"Model Comparison with Transaction Costs"* (*Journal of Finance*), show high-turnover factors collapse once realistic spreads are applied, favoring low-turnover momentum/value/profitability with banding. Practitioner studies on Connors' RSI(2) corroborate that crowded 2–5 day pullbacks on mega-caps suffer severe friction drag unless holding periods lengthen or turnover drops.
  4. **Sharpe-ratio inference pitfalls:** López de Prado, Lipton & Zoonekynd (April 2026), *"How to Use the Sharpe Ratio"* (*Journal of Portfolio Management* 52(6), pp. 6–50; ADIA Lab / `SSRN:5520741`), and López de Prado & Porcu (2026), *"The Deflated Sharpe Ratio: A Unified Framework for Search-Adjusted Performance Inference"* (*JPM*), codify PSR, MinTRL, DSR, and Bayesian FDR to prevent low-power and multiple-testing errors in promotion gates.
  5. **Implications for a €1,000 Trading 212 account (Germany):** Because Trading 212 charges `€0` commission, fractional shares, automatic German Abgeltungsteuer withholding since Jan 2026 (`docs/01-platforms.md:57`), **0% German FTT**, and **0% FX fee on EUR instruments** (vs `0.30%` round-trip FX on USD API trades), **only low-turnover (<8×/yr), EUR-denominated strategies** (Xetra UCITS ETFs or Xetra EUR large caps) can keep transaction costs `<15–20%` of gross P&L.
- **Severity:** MED
- **Confidence:** HIGH

### F8 — Implementation & documentation discrepancies across `docs/02`, `docs/03`, `docs/06`, `docs/3paperresearch.md`, `backtest.py`, and `report.py`
- **Claim:** Several doc-vs-code discrepancies undermine reproducibility and honest reporting.
- **Evidence:**
  1. **`docs/3paperresearch.md:69` Spearman IC bug:** claims `signal.corr(fwd_return, method="spearman")` needs no `scipy`. In the project's `.venv` (`pandas 3.0.6`, no `scipy`), calling it raises `ModuleNotFoundError: No module named 'scipy'` (verified 2026-11-25). Zero-dependency replacement: `signal.rank().corr(fwd_return.rank())`.
  2. **Missing proxy tracking-difference report (`docs/06-backtesting.md:15`):** docs promise "tracking difference reported where both exist", but `report.py` never computes it. Read-only check on overlap periods (`data/research.db`, `native_from` to `2026-09-29`):
     - `SXR8` vs `SPY` (3,148d): CAGR `+15.16%` vs `+15.42%` (`-0.26%/yr`), daily corr `0.5647`, TE `16.50%`.
     - `SXRV` vs `QQQ` (3,149d): CAGR `+20.65%` vs `+20.93%` (`-0.28%/yr`), daily corr `0.5901`, TE `19.45%`.
     - `EXW1` vs `FEZ` (4,387d): CAGR `+7.86%` vs `+8.40%` (`-0.53%/yr`), daily corr `0.7437`, TE `16.12%`.
     - `IS3N` vs `EEM` (3,040d): CAGR `+7.98%` vs `+7.41%` (`+0.57%/yr`, lower TER), daily corr `0.7571`, TE `14.31%`.
     - `4GLD` vs `GLD` (4,168d): CAGR `+9.87%` vs `+9.42%` (`+0.45%/yr`), daily corr `0.7297`, TE `12.51%`.
     - Low daily correlations (`0.56–0.76`) stem from non-synchronous closes (Xetra 17:30 CET vs US 22:00 CET) and 14:15 CET ECB FX fixing; multi-year CAGRs track within `±0.57%/yr`.
  3. **Missing max-single-year profit check (`docs/06-backtesting.md:57`):** `report.py` never checks whether one year > 50% of total profit (S1 IS passes: 2009 = `+€111.26` / `+€322.28` = `34.5%`).
  4. **Drawdown kill-switch definition mismatch:** `backtest.py:106` trips at `equity <= peak - max_drawdown_pct * budget` (fixed €60 on S1, €13 on S3/S4—meaning a 10% drop from peak on a €130 sleeve even if equity grew to €246!), `live.py:300` trips at `equity <= peak - max_drawdown_pct * cap` (fixed €100), while `docs/05-risk-and-safety.md:35` says `10%` from equity peak (relative) and `live.py:349` displays `1 - equity / peak`.
  5. **Stale portfolio docs:** `docs/03-strategies.md:61-62,96-99` still describes S1 €600 + S2 €400 across 14 US+EU stocks and `max 9 positions`, contradicting `config/settings.toml:8-15`, `config/risk.toml:5`, and `live.py:181-183` (4 strategies, EUR-only live, €600/€140/€130/€130, 12 positions).
  6. **Mojibake in Bollinger report:** `reports/backtest_s2_pullback_insample_entry_rule-bollinger_2026-09-25.md:3,12-13` contains UTF-8-as-cp1252 mojibake (`Â·`, `â‚¬`, `Ã—`), confirming why UTF-8 output encoding must stay enforced everywhere.
- **Severity:** MED
- **Confidence:** HIGH

---

### F9 — Two candidate replacements for S2 (exact, testable specs; zero holdout fitting)
- **Claim:** Any replacement for S2 at €1,000 on Trading 212 must be **EUR-denominated** (0% FX fee), **low-turnover** (`<6–8×/yr` so 20 bps round-trip spread is `<15%` of gross edge), **long-only daily bars**, and **pre-registered with textbook round-number parameters** before touching the 2020–2024 holdout. Below are the two strongest candidates grounded in 2023–2026 literature; neither has been run on the 2020–2024 holdout.
- **Candidate C1 — 52-Week High Cross-Sectional Momentum + Trend Filter + Rank Banding (EUR Large Caps)** *(Recommended primary S2 replacement if keeping the R1 LLM desk active)*
  - **Literature basis:** George & Hwang (2004) 52-week high anchoring; Jegadeesh & Titman (1993); Detzel, Novy-Marx & Velikov (2023) on low-turnover banded momentum surviving transaction costs; Barroso & Santa-Clara (2015) / Moreira & Muir (2017) volatility-managed momentum.
  - **Exact spec (pre-registered defaults, no tuning):**
    - **Budget:** €400 (replaces S2/S3/S4 split once experiments end).
    - **Universe:** Existing 18 EUR Xetra large caps in `config/instruments.toml` (expandable to full DAX 40 EUR constituents pre-holdout to mitigate concentration/survivorship; state survivorship bias explicitly per `docs/06 §1`).
    - **Check schedule:** Last Xetra trading day of each **month** (`check = "M"`).
    - **Eligibility filter:** `close > SMA(200)` and `ready` (`≥ 252` bars).
    - **Ranking score:** `ratio52 = close / rolling_max(high, 252)` (descending; ties broken alphabetically).
    - **Portfolio & banding:** Hold top `K = 3` stocks (`max_positions = 3`). An already-held stock is **kept** if it remains above `SMA(200)` AND within the top `keep_k = 6` eligible stocks (2× banding halves turnover). Free slots fill with highest-ranked unheld eligible stocks.
    - **Sizing:** Equal-weight within budget (`weight = 1/3`, i.e. ~€133/slot, capped at `max_position_eur = 150.0` and cash). *(Robustness alternative: inverse-`σ(20)` weight.)*
    - **Protective stop (broker-resting GTC):** **Non-trailing catastrophic stop** at `entry × (1 − 0.15)` (or `entry − 4 × ATR(20)`, fixed at entry—NOT trailed monthly—to prevent S1-style premature stop-outs while capping single-stock blowups like Wirecard/Bayer).
    - **LLM desk compatibility:** Single-stock monthly entries (~1–3/month) carry real company news and earnings dates, preserving the R1 shadow A/B evaluation path (`docs/06 §6`, `docs/08`).
    - **Robustness ranges (IS only):** `K ∈ {2, 3, 4}`, `keep_k ∈ {K, 2K}`, `sma_n ∈ {150, 200, 250}`, `stop ∈ {fixed 15%, 4×ATR(20)}`.
    - **Unoptimized in-sample sanity check (2007–2019, EUR-18, `4×ATR` trailing variant, holdout untouched):** CAGR `1× +4.21%` / `2× +3.88%`, Sharpe `0.36 ± 0.29`, Max DD `-37.2%` (vs EU-18 benchmark `-61.1%`), `160` trades, turnover `6.0×/yr`, costs `13.1%` of gross P&L. (Testing the fixed catastrophic stop instead of trailing `4×ATR` is expected to further cut turnover; must be formally logged in `trials.jsonl` on IS only.)
- **Candidate C2 — Dual Momentum (Relative + Absolute) on EUR UCITS ETFs** *(Alternative if zero survivorship bias is prioritized over R1 single-stock news)*
  - **Literature basis:** Antonacci (2014) Global Equities Momentum; Moskowitz et al. (2012, 2025); Sepp & Lucic (2026) low-frequency trend spectral mass; Keller & Keuning protective asset allocation.
  - **Exact spec (pre-registered defaults, no tuning):**
    - **Budget:** €400.
    - **Universe (all Xetra EUR UCITS, 0% FX fee):** Risky sleeve = `SXR8, SXRV, EXW1, IS3N, 4GLD` (already in `config/instruments.toml`, with existing pre-inception proxies); Defensive sleeve = `EUNH` (or add a short-duration EUR cash-proxy UCITS ETF such as `XEON` / `ERNE` once verified on Trading 212).
    - **Check schedule:** Last Xetra trading day of each **month** (`check = "M"`).
    - **Signal:** 12-1 month return `mom = close[t-21] / close[t-252] - 1` (skipping the most recent month to avoid short-term reversal contamination).
    - **Allocation:** Select the top `K = 2` risky ETFs by `mom`. For each selected slot: if `mom > 0` AND `close > SMA(200)`, allocate `50%` of budget (€200); otherwise rotate that slot to `EUNH` (if `EUNH` `close > SMA(200)`) or cash.
    - **Protective stop (broker-resting GTC):** Non-trailing catastrophic stop at `entry × (1 − 0.15)` (protects against flash crashes/black swans without creating intramonth whipsaw churn).
    - **Robustness ranges (IS only):** `lookback ∈ {126, 189, 252}` days, `K ∈ {1, 2, 3}`, `stop ∈ {fixed 12%, fixed 15%, 4×ATR(20)}`.
    - **Trade-off vs C1:** Zero single-stock survivorship bias and tighter Xetra spreads, **but** trades ETFs (overlaps S1's universe, raising shared-book correlation unless S1+C2 share one unified ETF sleeve, and removes the R1 single-stock LLM desk test bed).
    - **Unoptimized in-sample sanity check (2007–2019, existing 6 ETFs, `4×ATR` trailing variant, holdout untouched):** CAGR `1× +2.29%` / `2× +1.73%`, Sharpe `0.26 ± 0.28`, Max DD `-25.5%` (vs `-40.3%` benchmark), `97` trades, costs `21.1%` of gross.
- **Severity:** MED
- **Confidence:** HIGH

### F10 — Walk-forward test plan for S1 (respecting parameter freeze and trial log)
- **Claim:** S1's parameter freeze (`docs/10-build-log.md:491-493`) and one-shot holdout rule (`docs/06-backtesting.md:49`) remain strictly binding because the 2020–2024 holdout has **already been run once** (`data/trials.jsonl`, `2026-09-25T16:35:58Z`, `code 75445e5c1b44`). Any modification (such as testing `atr_mult = 2.0` per `docs/10:493` or testing a non-trailing catastrophic stop per F3) must be run as a **new variant (`S1b`)** under a strict walk-forward protocol with zero peeking at 2020–2024 during model selection.
- **Walk-forward protocol (exact spec):**
  1. **Freeze boundary:** Production/demo `S1` stays untouched at `{sma_n: 200, check: "M", atr_n: 20, atr_mult: 3.0, vol_n: 20}` throughout P1–P2 so forward checks compare apples to apples.
  2. **Pre-registered search space (kept tiny to protect DSR):** Do **not** re-search `check` (`W` already failed in-sample via churn). Restrict the walk-forward hypothesis space to **6 cells** (3 `sma_n` × 2 stop modes, or 2 `sma_n` × 3 `atr_mult`):
     - Track A (owner's `docs/10:493` question): `sma_n ∈ {150, 200, 250}` × `atr_mult ∈ {2.0, 3.0, 4.0}` (`check="M"` fixed, 9 cells).
     - Track B (F3 hypothesis, pre-registered as `S1b`): `sma_n = 200, check = "M"` fixed, comparing **trailing `3×ATR(20)`** vs **fixed catastrophic stop `-15%` from entry** (only **2 cells**, keeping `N_eff ≤ 2`).
  3. **Rolling windows (per `docs/06 §2.4`, 5y train / 1y OOS step, strictly inside 2007–2019 IS first):**
     - **8 rolling folds inside IS:** Train `2007–2011` → Test `2012`; Train `2008–2012` → Test `2013`; …; Train `2014–2018` → Test `2019` (8 contiguous OOS years, 2012–2019, zero overlap with 2020–2024).
     - **Warm-up & embargo:** Each test year inherits the prior year's warm-up bars (`≥ 250` bars) for causal indicators (`features()`), with **0 parameter re-use across the fold boundary** and positions marked flat or seamlessly handed off with full transition costs logged.
     - **Selection rule inside each train fold:** Pick the parameter cell maximizing **cost-adjusted Calmar** (or `Sharpe` subject to `MaxDD <= 0.6 × BenchDD`) — never unconstrained max CAGR — and record parameter stability (how often the selected cell flips year-to-year; >50% flips = unstable, revert to fixed default).
  4. **Trial log discipline:** Add a `kind = "walkforward_train"` / `"walkforward_oos"` entry to `data/trials.jsonl` for **every fold and every candidate cell** (never bypass logging). Count total unique cells tested toward `N` in DSR.
  5. **Post-IS validation (because 2020–2024 is already spent for S1):**
     - **Do NOT claim 2020–2024 as an untouched holdout for S1.** Report 2020–2024 for `S1b` only as a *labeled secondary check* (`holdout_contaminated = true`), and evaluate `S1b` vs frozen `S1` **prospectively in shadow mode** alongside `S1` on `2025–2026+` live data before any promotion decision.
  6. **Promotion bar for `S1b` to replace `S1`:** Stitched WF-OOS (2012–2019) must beat frozen `S1` on both `2×`-slippage CAGR and Calmar, with `DSR >= 0.80` (at `N_eff`), parameter stability across ≥ 5 of 8 folds, and clean shadow tracking over ≥ 6 monthly check days (6 months, not 8 weeks).
- **Severity:** MED
- **Confidence:** HIGH

---

## Proposed edits

### P-antigravity-1: Harden promotion gates and add DSR/MinTRL/multi-seed null requirements
- File: `docs/06-backtesting.md` §2.3, §2.5, §4, §7
- Change:
  1. In §2.3 (after the cost table), add: *"At `2×` costs, double uncertain execution friction (`eu_slippage`, `us_slippage`), while keeping contractual broker tariffs (`us_fx_fee = 0.15%`) at `1×` (optionally report a separate FX-stress run). Note that Trading 212's Public API does not support multi-currency wallet routing (verified 2026-11-25), so USD API orders always incur 0.15% FX per side."*
  2. In §2.5, add: *"Random-entry control (`S4`): evaluate against an ensemble of ≥ 50 seeds (median and 95th percentile Sharpe/CAGR), not a single seed."*
  3. In §4, add: *"Compute and report Probabilistic Sharpe Ratio `PSR(0)`, Deflated Sharpe Ratio `DSR` (using logged trial count and effective independent trials `N_eff`, Bailey & López de Prado 2014; López de Prado, Lipton & Zoonekynd 2026), and Minimum Track Record Length `MinTRL(95%, 0)` in every backtest report."*
  4. Replace §7 `Idea → Demo` and `Demo → Gated live` rows with:
     - `Idea → Demo (P0 → P1)`: *"Backtest ≥ 10 years (with proxies) on the **exact live-tradable universe**; positive CAGR and `PF > 1.05` at `2×` slippage; in-sample `Sharpe >= 0.40` AND `PSR(0) >= 0.90` (or `DSR >= 0.80` if parameters were selected from a grid rather than pre-registered); holdout (5y) `Sharpe > 0` AND `Calmar >= 0.5 × IS Calmar` (noting a 5y holdout has `SE ≈ 0.45` and cannot reject small-sample noise alone); beats 50-seed random control median; max drawdown `<= 0.65 × benchmark max DD`; no single year > 50% of profit; plateau in robustness grid; code reviewed and unit-tested; report filed with US/EU split and proxy tracking difference."*
     - `Demo → Gated live (P2 → P3)`: *"≥ 8 weeks of demo trading **and** at least 3 completed strategy decision cycles (for monthly strategies like S1, ≥ 3 months); 100% signal match against a shared-book backtest replay from each strategy's actual start date; live fill slippage within `1.5×` the cost model (noting practice-account fills on ETFs do not validate live spreads—re-verify on micro live fills at P3); zero unexplained orders; all drills passed; VPS live; owner decision."*
- Why: Analytical power calculation (F6) shows the current 5-year `OOS >= 0.5 × IS` gate has a 30.7% false-positive rate (`SR=0`) and 31.6% false-negative rate (`SR=0.45`), lacks an IS floor, and omits DSR despite promising it in §1/§2.6/§4; S4 single-seed path flipped by 9% CAGR (F4); S1 gets only 1–2 check days in 8 weeks (F6). Supported by López de Prado, Lipton & Zoonekynd (April 2026, *JPM* 52(6), SSRN 5520741), checked 2026-11-25.
- Risk if wrong: Tighter statistical thresholds may reject marginal strategies on 13-year samples (e.g., S1's `DSR` is `40%` at `N=20` if treated as grid-selected, hence the explicit distinction for pre-registered textbook defaults).

### P-antigravity-2: Reconcile `docs/03` with live EUR-only sleeves, S1 stop behaviour, and register S2 replacement candidates + S1 walk-forward track
- File: `docs/03-strategies.md` §3, §4
- Change:
  1. In §3 (`S1`), add under *Expected behaviour*: *"Note (2026-11-25): at `atr_mult = 3.0` trailed monthly, 95–99% of exits occur via the protective stop rather than `close <= SMA(200)`, raising turnover to ~5–7×/yr. Parameters stay frozen through P1–P2; testing a fixed catastrophic broker stop (`S1b`) is queued for a rolling walk-forward study (5y/1y on 2007–2019 IS)."*
  2. In §3 (`S2`), update Budget/Universe to reflect current demo reality (`€140` experimental budget on 18 German EUR stocks; original €400 14-stock US+EU spec failed P0 gate) and add a note that `max_positions` and `max_position_eur` must match the €140 sleeve (`2` positions, `€65` cap).
  3. In §3 (`S3` and `S4`), explicitly note that 2026-09-30 backtests covered 26 US+EU stocks whereas live demo trades only 18 German EUR stocks (where S3 is flat at 2× costs and S4 must be evaluated as a ≥ 50-seed ensemble in backtest).
  4. Add §3.1 **"Candidate S2 replacements (research queue, holdout untouched)"** with the exact specs of **C1** (52-Week High Cross-Sectional Momentum + SMA200 + 2× banding on EUR large caps, monthly, fixed catastrophic stop) and **C2** (Dual Momentum 12-1m on EUR UCITS ETFs, monthly, fixed catastrophic stop) from F9.
  5. Update §4 (`Portfolio construction`) to reflect the active 4-strategy demo split (`S1 €600, S2 €140, S3 €130, S4 €130`, `max_positions = 12`, shared-book single-owner-per-ticker rule, EUR-only live until USD order pricing exists).
- Why: `docs/03 §3–§4` currently contradicts `config/settings.toml:8-15`, `config/risk.toml:5`, and `live.py:180-183`; S1's true exit mechanism and the two literature-backed S2 replacements need pre-registration before any backtest code is written.
- Risk if wrong: Low (documentation alignment and pre-registration only; does not alter frozen S1 or place orders).

### P-antigravity-3: Update `docs/02-approaches.md` with 2023–2026 literature and clarify R1 desk scope after S2 failure
- File: `docs/02-approaches.md` §2, References
- Change:
  1. In §2 (`A. Rule-based systematic` and `E. Hybrid`), add one sentence noting that 2023–2026 empirical evidence shows short-horizon equity signals (2–5d mean reversion, short-term trend on small-tick assets) suffer severe post-publication and cost erosion, whereas monthly trend/momentum on liquid EUR instruments remains viable at €1,000; note that R1's single-stock review scope moves from failed S2 to any approved single-stock replacement (e.g., C1).
  2. Add to `References`:
     - Chen & Velikov (2023). *Zeroing in on the Expected Returns of Anomalies.* *JFQA*.
     - Detzel, Novy-Marx & Velikov (2023). *Model Comparison with Transaction Costs.* *Journal of Finance*.
     - Kurth, Eisler, Rej & Bouchaud (2026). *Is Trend Still Your Friend?: A Microstructural Account of the Demise of Short-Term Trend-Following.* `arXiv:2607.01550`.
     - Sepp & Lucic (2026). *The Science and Practice of Trend-Following Systems.* `arXiv:2607.19497`.
     - Moskowitz, Sabbatucci, Tamoni & Uhl (2025). *Nonlinear Time Series Momentum.* `SSRN:5933974`.
     - López de Prado, Lipton & Zoonekynd (2026). *How to Use the Sharpe Ratio.* *Journal of Portfolio Management* 52(6), pp. 6–50 (`SSRN:5520741`).
- Why: Grounds TradeBot's deterministic-core strategy choices and statistical standards in verified 2023–2026 primary literature (checked 2026-11-25) and removes the stale assumption that S2 is the permanent R1 host.
- Risk if wrong: None (documentation & citations only).

### P-antigravity-4: Fix zero-dependency Spearman IC snippet in `docs/3paperresearch.md`
- File: `docs/3paperresearch.md` §3.2
- Change: Replace line 69:
  ```
  `pandas` already does it — `signal.corr(fwd_return, method="spearman")`, no `scipy`. Add it to `metrics()` in [backtest.py:179](src/tradebot/backtest.py:179) per strategy and per instrument, alongside the existing `sharpe_se`.
  ```
  with:
  ```
  `pandas` needs `scipy` for `method="spearman"`, so compute rank correlation with zero extra dependencies via `signal.rank().corr(fwd_return.rank())` (Pearson on ranks). Add it to `metrics()` in [backtest.py:179](src/tradebot/backtest.py:179) per strategy and per instrument, alongside the existing `sharpe_se`.
  ```
- Why: Directly reproduced `ModuleNotFoundError: No module named 'scipy'` in the project's `.venv` (`pandas 3.0.6`) on 2026-11-25 (F8).
- Risk if wrong: None; exact mathematical identity for Spearman correlation without ties (and standard mid-rank Pearson with ties).

### P-antigravity-5: Fix `S2Pullback` slot and notional caps to match its €140 demo budget
- File: `src/tradebot/strategies.py` (lines 87–88)
- Change: Change `S2Pullback` defaults (or read per-strategy caps from `config/settings.toml`) from:
  ```python
  max_positions: int = 3
  max_position_eur: float = 200.0
  ```
  to:
  ```python
  max_positions: int = 2
  max_position_eur: float = 65.0
  ```
  *(Note: keep `max_positions` and `max_position_eur` overridable via CLI `--param` so historical P0 €400 backtests remain reproducible, and update `tests/test_strategies.py` if any unit test asserts `max_positions == 3`.)*
- Why: Eliminates 857–1,100 spurious `sizing: below minimum order` rejections under the €140 budget and aligns code with `config/risk.toml:5` (`S2/S3/S4 <= 2 each`) and `S3Breakout`/`S4Monkey` (`65.0`).
- Risk if wrong: Changes S2's demo sizing/slots relative to prior €400 P0 reports (which already failed the gate and are superseded by the 2026-09-30 €140 demo experiment).

### P-antigravity-6: Fix `Engine.forward()` to respect per-strategy start dates and shared-book exclusion
- File: `src/tradebot/live.py` (lines 313–333)
- Change: Update `Engine.forward(self, day)` so that:
  1. Each strategy reads its own start date from `settings["live"].get("strategy_start", {}).get(name, start)` (defaulting to `settings["live"]["start"]`), preventing pre-deployment trades (2026-09-28/29 for S2/S3/S4) from polluting the check.
  2. When multiple strategies share a universe (`s2_pullback`, `s3_breakout`, `s4_monkey`), either run a joint multi-strategy replay honoring the `taken` symbol exclusion (`live.py:94`) or explicitly flag cross-strategy symbol collisions in the forward-check table instead of reporting an unexplained `**differs**`.
  3. Also report actual vs backtest fill-price differences (mean/max bps) as specified in `docs/06-backtesting.md:91`.
- Why: Currently `forward()` permanently reports `**differs**` on S2 and S4 (`reports/daily/2026-09-30..10-05.md`) for non-bug reasons, blinding the operator to real signal drift (F5).
- Risk if wrong: Multi-strategy replay adds slight complexity to `forward()`; must remain read-only and exception-wrapped so a report error never halts the engine.

### P-antigravity-7: Add PSR/DSR/MinTRL, rank-Spearman IC, relative drawdown check, and slippage-only 2× stress to `backtest.py`
- File: `src/tradebot/backtest.py` (lines 106, 163–203)
- Change:
  1. Align line 106 (`would_trip`) with `docs/05-risk-and-safety.md:35` relative drawdown (`equity <= peak * (1 - risk_cfg["max_drawdown_pct"])`) — or log both relative and fixed-budget drawdown clearly.
  2. In `_stats()` / `metrics()`, compute skewness, Pearson kurtosis, lag-1 autocorrelation `rho1`, non-normal `sharpe_se_nn`, `psr_zero`, `mintrl_years`, and (given trial count `n_trials`) `dsr`, plus zero-dependency rank-Spearman IC (`signal.rank().corr(fwd_return.rank())`).
  3. Allow `run(..., stress_fx: bool = False)` so `2×` cost runs double uncertain slippage (`eu_slippage`, `us_slippage`) without artificially doubling Trading 212's contractual `0.15%` FX fee unless explicitly requested (matching `P-antigravity-1`).
- Why: Implements the statistical safeguards already promised in `docs/06 §1, §2.6, §4` and fixes the `backtest.py` vs `docs/05` drawdown mismatch (F6, F8).
- Risk if wrong: Existing tests in `tests/test_backtest.py` must be verified; keeping existing metric keys unchanged and adding new keys avoids breaking callers.

### P-antigravity-8: Add US/EU split, proxy overlap tracking difference, and max-single-year profit check to `report.py`
- File: `src/tradebot/report.py` (lines 90–157)
- Change:
  1. When `panel` contains both `EUR` and `USD` instruments, emit a `## Market split (EUR vs USD)` table summarizing trades, net P&L, win rate, and costs per currency (`docs/06 §2.5, §8`).
  2. When `proxies` is non-empty, compute and print overlap-period CAGR difference, daily correlation, and tracking error for each proxy pair (`docs/06 §1`).
  3. Print the maximum single-year profit share (`max_year_eur / total_profit_eur`) and flag if `> 50%` (`docs/06 §2.5`).
  4. Display `PSR(0)`, `DSR` (using `len(trials(res1.strategy))`), and `MinTRL` in the Metrics table.
- Why: Closes three explicit `docs/06` requirements currently missing from every generated report (`reports/backtest_*.md`, F1, F6, F8).
- Risk if wrong: Minor report-formatting change; zero impact on live trading or strategy logic.

---

## Open questions for round 2

1. **For Owner & Claude (strategy direction):** Should the €400 non-S1 budget go to **C1** (52-Week High Momentum on EUR large caps — keeps single-stock news/earnings alive for the R1 LLM desk) or **C2** (Dual Momentum on EUR UCITS ETFs — eliminates single-stock survivorship bias, but leaves R1 with no single-stock sleeve)? Or keep S1 at €600 + C1 at €400 and drop S2/S3/S4 after the VPS soak?
2. **For Owner (8 open demo positions & restart baseline):** When the EU VPS launches, will the 8 unprotected demo positions (`ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV, IFX`, open since 2026-10-01..05) be flattened for a clean `live.start` reset, or reconciled as-is? (Flattening gives a clean forward-check baseline.)
3. **For Codex (code & risk mechanics):**
   - In `backtest.py:125` and `live.py:106`, `capital = min(cap, cap * equity / budget)` sizes a €130 sleeve at `€5` risk = **3.85% of sleeve equity per trade**. Should `risk_per_trade_pct` apply to `sleeve equity` or total `capital_cap_eur`?
   - In `execution.py:241-253`, why did `cancel` on `DHL`'s stop (`55850837740`) time out 3 times across 13 minutes on `2026-10-05` (`reports/daily/2026-10-05.md:48-53`), causing `+0.353%` exit slippage?
   - Can `data.refresh()` avoid mutating historical bars (or pin historical snapshots for backtests) so `research.db` refreshes don't alter prior years' backtest results (as seen in `s4_monkey` flipping from `+1.35%` to `-7.57%`)?
4. **For Deepseek (quant/maths verification):**
   - Please independently verify our DSR/MinTRL numbers for S1 (`kurt = 9.79`, `rho1 = -0.115`, `MinTRL = 13.25y`, `DSR = 40.0%` at `N=20` / `63.5%` at `N_eff=6`) and the optimal effective-trial estimator (`N_eff` via eigenvalue/clustering of the 18-cell S1 grid return correlation matrix per López de Prado & Porcu 2026).
   - For the S1 walk-forward (`F10`), is **non-trailing fixed `-15%` stop** vs **volatility-scaled catastrophic stop (e.g., fixed `5×ATR(20)` at entry, never trailed)** mathematically cleaner under fat-tailed ETF jumps?
5. **For Mistral (EU/German operations & tax):**
   - Under German Abgeltungsteuer (26.375%) and the `Aktienverlusttopf` (share losses only offset share gains, not ETF gains — `docs/05 §12`), does trading single stocks in **C1** (vs UCITS ETFs with 30% Teilfreistellung in **S1/C2**) materially change after-tax hurdle rates at €1,000 (assuming the €1,000 Sparer-Pauschbetrag is already used elsewhere)?
   - Are EUR-listed German tickers of US mega-caps on Xetra/Gettex (e.g., `APCd_EQ` noted in `docs/10-build-log.md:299`) viable on Trading 212 API without the 0.15% FX fee, or do their wider EUR-venue spreads negate the 0.30% FX saving? (Currently **UNVERIFIED** for live Xetra/Gettex retail spreads on Trading 212.)

---

## Sources

### Internal repository files (working tree `D:\TradeBot`, inspected 2026-11-25)
- `D:\TradeBot\Agent-Guide.md`, `D:\TradeBot\README.md`
- `D:\TradeBot\docs\01-platforms.md`, `02-approaches.md`, `03-strategies.md`, `04-architecture.md`, `05-risk-and-safety.md`, `06-backtesting.md`, `07-roadmap.md`, `10-build-log.md`, `3paperresearch.md`
- `D:\TradeBot\config\instruments.toml`, `risk.toml`, `settings.toml`, `t212_tickers.toml`
- `D:\TradeBot\src\tradebot\strategies.py`, `backtest.py`, `sim.py`, `sizing.py`, `indicators.py`, `report.py`, `live.py`, `execution.py`, `risk.py`, `config.py`, `models.py`, `data.py`, `cli.py`
- `D:\TradeBot\reports\backtest_s1_trend_{insample,holdout,recent}_2026-09-25.md`, `grid_s1_trend_2026-09-25.md`, `backtest_s2_pullback_insample_2026-09-25.md`, `backtest_s2_pullback_insample_entry_rule-bollinger_2026-09-25.md`, `grid_s2_pullback_2026-09-25.md`, `backtest_s2_pullback_{insample,recent}_2026-09-30.md`, `backtest_s3_breakout_{insample,recent}_2026-09-30.md`, `backtest_s4_monkey_{insample,recent}_2026-09-30.md`, `data_check_2026-09-30.md`
- `D:\TradeBot\reports\daily\2026-09-25.md`, `2026-09-28.md`, `2026-09-29.md`, `2026-09-30.md`, `2026-10-01.md`, `2026-10-02.md`, `2026-10-05.md`
- Read-only queries on `D:\TradeBot\data\trials.jsonl`, `data\demo.db`, `data\research.db`; test suite verified (`uv run pytest -q`: 93 passed).

### External sources (all checked 2026-11-25)
- **Trading 212 FX fee & multi-currency Invest accounts:** Trading 212 Help Centre (0.15% FX fee on interbank spot rate when converting; multi-currency wallets available in app): https://helpcentre.trading212.com/hc/en-us/articles/360007081177-Foreign-Exchange-FX-Fee · https://helpcentre.trading212.com/hc/en-us/articles/1500001809042-Multi-currency-accounts (checked 2026-11-25).
- **Trading 212 Public API multi-currency limitation:** Trading 212 Public API docs & Community forum thread confirming API orders execute in primary account currency with no wallet selection parameter: https://docs.trading212.com/api · https://community.trading212.com/t/trading-212-api-update/87988 (checked 2026-11-25).
- **Xetra Liquidity Measure (XLM / iXLM):** Deutsche Börse Cash Market — implicit round-trip spread/impact statistics for DAX stocks and ETFs: https://www.deutsche-boerse-cash-market.com/dbcm-en/instruments-statistics/statistics/xlm-xetra-liquidity-measure (checked 2026-11-25).
- **Kurth, J. G., Eisler, Z., Rej, A., & Bouchaud, J.-P. (July 2026):** *Is Trend Still Your Friend?: A Microstructural Account of the Demise of Short-Term Trend-Following.* https://arxiv.org/abs/2607.01550 (checked 2026-11-25).
- **Sepp, A., & Lucic, V. (July 2026):** *The Science and Practice of Trend-Following Systems.* https://arxiv.org/abs/2607.19497 (checked 2026-11-25).
- **Moskowitz, T. J., Sabbatucci, R., Tamoni, A., & Uhl, B. (Dec 2025):** *Nonlinear Time Series Momentum.* SSRN 5933974, https://dx.doi.org/10.2139/ssrn.5933974 (checked 2026-11-25).
- **López de Prado, M., Lipton, A., & Zoonekynd, V. (April 2026):** *How to Use the Sharpe Ratio* (*Sharpe Ratio Inference: A New Standard for Decision-Making and Reporting*). *Journal of Portfolio Management* 52(6), pp. 6–50; ADIA Lab / SSRN 5520741, https://dx.doi.org/10.2139/ssrn.5520741 (checked 2026-11-25).
- **López de Prado, M., & Porcu, E. (2026):** *The Deflated Sharpe Ratio: A Unified Framework for Search-Adjusted Performance Inference.* *Journal of Portfolio Management* (2026), https://www.quantresearch.org/ (checked 2026-11-25).
- **Chen, A. Y., & Velikov, M. (2023):** *Zeroing in on the Expected Returns of Anomalies.* *Journal of Financial and Quantitative Analysis* (JFQA), https://www.federalreserve.gov/econres/feds/ (checked 2026-11-25).
- **Detzel, A., Novy-Marx, R., & Velikov, M. (2023):** *Model Comparison with Transaction Costs.* *Journal of Finance*, https://onlinelibrary.wiley.com/journal/15406261 (checked 2026-11-25).
- **Foundational citations cross-referenced:** McLean & Pontiff (2016, *JF*); Bailey & López de Prado (2014, *JPM*); Lo (2002, *FAJ*); Moskowitz, Ooi & Pedersen (2012, *JFE*); Faber (2007, *JWM*); Jegadeesh & Titman (1993, *JF*); George & Hwang (2004, *JF*); Antonacci (2014); Moreira & Muir (2017, *JF*).
- **Unverified items explicitly flagged:** Live EUR-venue (Xetra/Gettex) bid-ask spreads on Trading 212 for EUR-denominated US stock tickers (`APCd_EQ`, etc.) — **UNVERIFIED**.
