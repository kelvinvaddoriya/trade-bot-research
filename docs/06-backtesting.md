# 06 — Backtesting & evaluation

**Purpose:** to avoid fooling ourselves. A strategy is promoted on evidence that survives costs, out-of-sample data and forward trading, not on a good-looking equity curve.

## 1. How backtests lie, and our countermeasures

| Bias | What happens | Countermeasure |
|---|---|---|
| Look-ahead | Trading at today's close using today's close; using revised data | Signals use the close of bar *t* and fill at the open of bar *t+1*. The engine passes only history up to *t*. |
| Survivorship | The universe is today's survivors | A fixed ETF universe (with proxies before a UCITS ETF existed). For single stocks, state the bias explicitly: today's mega-caps are yesterday's winners. |
| Overfitting / data snooping | Trying many parameters and keeping the best | Few parameters, robustness ranges, a holdout, a trial log, the deflated Sharpe ratio |
| Ignoring costs | No fees, FX, spread or slippage | A conservative cost model (§2.3), plus a rerun at 2× costs |
| Unrealistic fills | Filling at the exact stop price; unlimited liquidity | Stops fill at the stop or worse (including gaps through the stop at the open); a volume cap |
| Cherry-picked regime | Testing only in a bull market | ≥ 10 years including 2008, 2020 and 2022, where data allows |
| Proxy mismatch | The UCITS ETF differs from its proxy (fees, currency, index version) | Proxy only before inception; EUR conversion; tracking difference reported where both exist |
| LLM leakage | The LLM "knows" what happened next | The LLM desk is never backtested; it's evaluated going forward only (§6) |
| Code drift | Backtest code differs from live code | The same `Strategy` class and sizing code run in both ([04 §1](04-architecture.md#1-principles)) |

## 2. Method

### 2.1 Data

- Daily OHLCV: split- and dividend-adjusted for signals, raw prices for sizing. All history from Yahoo, cross-checked against Alpaca's official data for US names (Stooq was dropped, see [10, step 4](10-build-log.md#step-4-market-data-srctradebotdatapy-python--m-tradebot-data)) ([01 §6](01-platforms.md#6-market-data-us--eu-daily-bars)).
- History: single stocks from 2010 at the latest. UCITS ETFs from inception, with a proxy before that (the US twin or the index in EUR).
- US instruments are converted to EUR at the daily ECB reference rate, so results are reported in the account currency.
- Validation: no gaps on trading days, no zero or negative prices, big jumps flagged.

### 2.2 Execution model

- Entry limit orders at the last close + 1 % fill at the next open if the open ≤ the limit; otherwise no fill.
- Market exits fill at the next open, adjusted for slippage.
- Stop orders: if the open gaps through the stop, fill at the open; otherwise fill at the stop minus slippage.
- Position quantity ≤ 1 % of the bar's volume (never binding at €1,000, but kept for scale).
- Fractional quantities. Cash earns nothing (conservative).

### 2.3 Cost model (defaults)

| Item | EU stocks & UCITS ETFs (Trading 212) | US stocks (Trading 212, EUR account) | Xetra via IBKR (fallback) |
|---|---|---|---|
| Commission | 0 | 0 | max(€1.25, 0.05 %) |
| FX fee | 0 | 0.15 % per side | IBKR conversion fee *(verify)* |
| Half-spread + slippage | 0.10 % | 0.05 % | 0.10 % |

Every report shows results at 1× and 2× costs.

Trading 212's Public API executes orders in the account's primary currency with no multi-currency wallet routing ([Trading 212 API overview](https://docs.trading212.com/api/instruments/exchanges) · [Help Centre](https://helpcentre.trading212.com/hc/en-us/articles/1500001809042-Multi-currency-accounts), checked 2026-11-25), so USD API trades always incur the 0.15 % FX fee per side. Keep the standard 2× all-cost run unchanged for historical comparability; optionally report a separate labeled `2× slippage + 1× FX` sensitivity run alongside it.

### 2.4 Splits

- **In-sample** (development): start of data → 2019-12-31.
- **Out-of-sample holdout**: 2020-01-01 → 2024-12-31. Run it **once**, only after parameters are frozen, and log that run.
- **Walk-forward**: rolling windows of 5 years to fit and 1 year to test, for any parameter that gets tuned.
- 2025-01-01 → today: a "recent" reference, reported separately.

### 2.5 Robustness

- Parameter heatmaps over the ranges in [03 §3](03-strategies.md#3-selected-strategy-specifications). Accept only a plateau of good performance, not a lone spike.
- Monte Carlo: reshuffle the trade sequence 1,000 times to get a distribution of maximum drawdown and final equity.
- Subperiods: returns per year. No single year may contribute more than 50 % of total profit.
- Market split for S2: US and EU results reported separately.
- Random-entry control (`S4`): evaluate against an ensemble of ≥ 50 seeds (median and 95th percentile Sharpe and CAGR), not a single seed.

### 2.6 Trial log

Every backtest run (strategy, parameters, period, git commit, metrics) is appended to `data/trials.jsonl`. The trial count feeds the deflated Sharpe ratio.

**Data provenance and the trial inventory (added 2026-11-25).** Each research run must identify an immutable, consistent snapshot of bars and FX plus its native/proxy definitions, universe, parameters, source/config hashes, dependency versions, execution/cost policy and runner hash. The trial record and report reference the same manifest ID. Runtime refreshes may update the live cache but must not overwrite the inputs of an already reported experiment. Repeating an experiment on revised data is a separately identified run, with differences disclosed. A snapshot supports reproducibility; it does not establish historical point-in-time availability. Every exploratory variant, seed, fold and cost scenario is recorded, including ad-hoc runs that bypass the normal report writer. Reconstruct the 2026-11-25 unlogged trials as late registrations, preserving their actual known execution/registration dates and marking unavailable inputs/results UNVERIFIED; never describe them as prospectively registered. Do not assert a complete trial count, effective independent search count or definitive DSR until the search inventory is reconciled. Reproductions and sensitivity runs remain distinguishable from genuinely new selection opportunities. *(Implementing snapshots and manifest fields needs separate code proposals and tests.)*

## 3. Metrics

CAGR · annualised volatility · Sharpe (risk-free rate 0 unless stated) · Sortino · max drawdown and its duration · Calmar · exposure (% of time invested) · turnover · number of trades · win rate · average win / average loss · profit factor · average holding days · costs (incl. FX) as % of gross P&L · relative to the benchmark: excess return, beta, correlation.

Everything is reported in % **and** in € at the €1,000 cap, so it's obvious how small the absolute numbers are.

## 4. Statistical sanity

Standard error of the Sharpe ratio, using the i.i.d. approximation (Lo 2002): `SE ≈ sqrt((1 + SR²/2) / T)`, with T in years.

| Track record | SE of Sharpe (at SR = 0.5) | 95 % interval |
|---|---|---|
| 3 months | ≈ 2.1 | −3.7 … 4.7 |
| 1 year | ≈ 1.06 | −1.6 … 2.6 |
| 10 years | ≈ 0.34 | −0.2 … 1.2 |

What this means:

- Weeks or months of forward demo results **cannot** prove profitability. They verify the *implementation* (fills, costs and behaviour match the backtest), not the edge.
- The edge is judged on long backtests plus the holdout. Forward trading checks that live results ≈ the backtest.
- Trade-level statistics need at least 100 trades (S2, in backtest). Always report the trade count next to a win rate.
- Report the Probabilistic Sharpe Ratio `PSR(0)`, the Deflated Sharpe Ratio `DSR` (Bailey & López de Prado 2014; López de Prado, Lipton & Zoonekynd 2025/2026, [SSRN 5520741](https://doi.org/10.2139/ssrn.5520741), metadata checked 2026-11-25, full text UNVERIFIED), and the Minimum Track Record Length `MinTRL(95 %, 0)`. `DSR` is valid only over a complete, reconciled trial family (including any ad-hoc runs) and should note effective independent trials `N_eff` when trials are correlated.

## 5. Forward testing (shadow & demo)

- **Shadow:** live data, with orders simulated by `SimBroker` using the backtest's execution model. This tests the pipeline without any broker.
- **Demo:** the Trading 212 practice account, sized to the €1,000 cap.
- **Tracking check:** replay the same period in the backtester and compare trade by trade. Signals must match 100 %; a signal mismatch is a bug. Report fill-price differences (mean, max) and the P&L difference.
- **Shared-book replay vs independent baseline:** when multiple strategies share one book and ticker-ownership lock, keep two clearly labeled checks: (a) the **independent sleeve baseline** (each strategy alone on its live EUR universe, used for P0 research and ≥ 50-seed S4 null benchmarks), and (b) the **shared-book portfolio replay** (the P1/P2 implementation check). The shared-book replay starts from each strategy's actual activation/restart epoch and initial holdings/cash, runs exits before entries at the open, applies venue rounding, tracks `bars_held` from actual fill dates, and runs close decisions in fixed `settings.live.strategies` priority order while excluding symbols owned or pending-entry by another strategy (`taken`). Tag cross-strategy exclusions (`COLLISION`), `KILL` windows and operator catch-ups (`operator_event`) explicitly, and pass the same `taken`-filtered universe and date seed to S4.
- **Clean-start rule after multi-day outages:** do not drop a multi-day unhedged shutdown gap and stitch forward-check series across it. Preserve the prior record intact in the journal and reports, resolve stale positions under owner authorization, and restart the forward-check clock (`live.start`) from zero.

## 6. Evaluating the LLM desk (forward only)

The desk can't be backtested, because every model's training data contains the "future" of any historical test. So it's measured forward, in shadow, on the S2 entry signals (the desk's scope, [08 §2](08-multi-agent-llm.md#2-roster-the-top-5-as-jurors-plus-a-cheap-utility-model)):

| Book | Rules |
|---|---|
| A — control | Strategies + risk engine (these orders go to the demo account in P1–P2) |
| B — desk | Strategies + desk (quorum + median) + risk engine, in shadow |
| J1…J5 — single jurors | Strategies + one juror's review alone, in shadow |

Once the signals exist, the counterfactual books cost nothing to compute. Measure:

- Veto and reduce rates, and **veto precision**: the share of vetoed entries whose book-A trade lost money, compared with the base loss rate.
- P&L, drawdown and trade count: B vs A, and each J vs A.
- Per juror: agreement with the majority, calibration (Brier score), failure rate, latency and cost ([08 §7](08-multi-agent-llm.md#7-evaluation)).
- Stability: re-run the same input 3 times and measure how often the decisions agree.

The desk moves to `affects_orders = true` only with ≥ 50 reviewed entries, veto precision above the base loss rate, a book B drawdown no worse than book A's, and a cost that pays for itself. Otherwise the desk shrinks to its useful jurors or stays advisory (reports only). Both are valid research outcomes.

## 7. Promotion gates

| Gate | Criteria |
|---|---|
| Idea → Demo (P0 → P1) | Backtest ≥ 10 years (with proxies) where data exists; still positive at 2× costs; holdout Sharpe at least half the in-sample Sharpe; a plateau in the robustness checks; max drawdown acceptable vs the benchmark; code reviewed and unit-tested; report filed |
| Demo → Gated live (P2 → P3) | ≥ 8 weeks of demo trading; 100 % signal match with the backtest replay; slippage within the cost model; zero unexplained orders; all drills ([05 §11](05-risk-and-safety.md#11-drills-all-must-pass-before-each-promotion)) passed; engine moved to the VPS ([09](09-hosting.md)); owner decision to use real money |
| Gated → Bounded autonomy (P3 → P4) | ≥ 4 weeks live with approvals; zero guardrail breaches; zero unexplained orders; live ≈ backtest replay; owner decision |
| Any → Stop | Drawdown kill switch; live results materially worse than the backtest replay for 3 months; a broker or terms change |

**Proposed gate review items (pending owner decision; the table above remains in force):**
- Require promotion backtests to run on the exact live-tradable universe rather than a mixed US+EU universe when live is EUR-only.
- On a 5-year holdout, the isolated `holdout Sharpe >= 0.5 × IS Sharpe` criterion has `SE ≈ 0.45` under i.i.d. assumptions, giving high single-criterion false-positive and false-negative rates; review adding an in-sample Sharpe floor, `PSR(0)` / `DSR` over a reconciled trial family, and an explicit max-drawdown ratio vs the benchmark.
- For slow strategies (such as monthly S1, where 8 weeks is only 1–2 checks), review adding a minimum number of completed decision cycles alongside the 8-week demo soak, and note that demo ETF fills do not validate live spreads.

## 8. Backtest report template

Each run writes `reports/backtest_<strategy>_<date>.md`:

1. Strategy, parameters, universe, period, git commit, data sources, proxies used, cost model.
2. Equity curve vs benchmark (EUR), and a drawdown chart.
3. Metrics table (1× and 2× costs, in % and €), including the benchmark.
4. Returns per year; US vs EU split for S2.
5. Trade list summary, with the top 5 winners and losers.
6. Robustness heatmap and the Monte Carlo drawdown distribution.
7. Holdout result (if run) and the trial count.
8. Verdict against the gate criteria.

## References

- Lo (2002). The statistics of Sharpe ratios. *Financial Analysts Journal* 58(4).
- Bailey, López de Prado (2014). The deflated Sharpe ratio. *Journal of Portfolio Management* 40(5).
- Harvey, Liu, Zhu (2016). …and the cross-section of expected returns. *Review of Financial Studies* 29(1).
- López de Prado (2018). *Advances in Financial Machine Learning.* Wiley.
- *Beyond Agent Architecture: Execution Assumptions and Reproducibility in LLM-Based Trading Systems* (2026). [arXiv:2606.08285](https://arxiv.org/abs/2606.08285)
