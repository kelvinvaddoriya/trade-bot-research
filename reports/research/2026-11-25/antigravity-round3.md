# Antigravity — Round 3: amendment acceptance, final texts, and answers (2026-11-25)

All five round-2 files (`claude-round2.md`, `codex-round2.md`, `antigravity-round2.md`, `mistral-round2.md`, `deepseek-round2.md`) and `Agent-Guide.md` were read in full. No code, docs, config, safety markers, or `data/trials.jsonl` were edited; this report is the sole file written.

---

## Amendment responses

### `P-antigravity-1` (`docs/06-backtesting.md` §2.3, §2.5, §4, §7)
- **Claude — AMEND** (approve items 1–3; record §7 gate changes as *"proposed gates, pending owner decision"* instead of replacing §7): **ACCEPT** — promotion gates are an owner-level decision and must not be overwritten unilaterally.
- **Codex — REJECT & Challenge (F6/P-1)** (isolated Sharpe-rule 30.7%/31.6% error calculation is not the joint §7 gate; post-hoc thresholds are uncalibrated and loosen live slippage to `1.5×`; do not redefine existing `2×` all-cost runs; unlogged trials invalidate a complete logged-search claim): **ACCEPT** — all four factual points are right; the final text keeps the existing §7 table and `2×` all-cost definition intact, drops all post-hoc numeric thresholds and the `1.5×` slippage loosening, adds `2× slippage + 1× FX` only as an optional labeled sensitivity run, scopes the `SE ≈ 0.45` note strictly to the isolated Sharpe criterion, and requires a reconciled trial family before asserting DSR.
- **Claude — Challenge 4** (Round 1 ad-hoc backtests are not in `data/trials.jsonl` and count as trials): **ACCEPT** — reconciled with exact counts in `## Answers`, and reflected in §4's DSR wording.

### `P-antigravity-2` (`docs/03-strategies.md` §3, §4)
- **Codex — AMEND & Challenges (F2, F3, F9, F10)** (restrict edit to verified €600/€140/€130/€130 budgets, 18-EUR-stock live vs 26-stock backtest distinction, shared-book cap 12, actual S2 defaults `3/€200` pending explicit override, and exact filed S1 stop-exit fractions `200/210`, `88/89`, `25/27`; preserve S1's freeze; defer C1/C2 adoption and numerical claims until trial provenance and `€5` risk-sizing compatibility are resolved; distinguish stop precedence from trend state and avoid claiming `3/€200` overspends cash): **ACCEPT** — every factual correction is valid; the final text uses the exact filed fractions (`92.6–98.9 %`), reports S2's actual `3/€200` code defaults alongside the pending override, drops all C1/C2 numerical performance claims and "unoptimized/pre-registered" labels, and defers C1/C2 specs pending provenance and risk-sizing resolution. *(Also accommodates `P-deepseek-8`'s queued `5 × ATR(20)` entry-fixed stop option in the S1b research note without breaking S1's freeze.)*

### `P-antigravity-3` (`docs/02-approaches.md` §2, References)
- **Claude — AMEND** (every 2026 arXiv/SSRN citation needs its URL and `checked 2026-11-25`; anything not opened directly gets `UNVERIFIED`): **ACCEPT** — both arXiv abstracts (`2607.01550`, `2607.19497`) were directly fetched today and all other DOIs/titles were checked via CrossRef on 2026-11-25; full PDFs not directly read are explicitly labeled `full text UNVERIFIED` / `full PDF UNVERIFIED`.
- **Codex — REJECT** (do not extrapolate cited literature into verified viability at €1,000, do not transfer R1 scope without an accepted replacement, and mark un-opened full papers `UNVERIFIED`): **ACCEPT** — both objections are right; the final text removes the €1,000 viability extrapolation (noting futures vs equity scope and stating viability at €1,000 still requires our own tests), leaves §2.E / R1 scope untouched, and marks un-opened full texts `UNVERIFIED`.

### `P-antigravity-4` (`docs/3paperresearch.md` §3.2)
- **Codex — AMEND & Challenge (P-4)** (independently ranking before pairwise deletion gives wrong Spearman values when missing data mismatch; use pairwise-cleaned `pd.concat(...).dropna()` with `rank(method="average")`, finite inputs, aligned unique keys, and undefined IC for insufficient/constant data): **ACCEPT** — Codex's counterexample (`0.654654` vs `0.5`) proves independent ranking fails under mismatched NaNs; the final snippet applies finite filtering and pairwise `dropna()` before average-rank correlation.

### `P-antigravity-5` (`src/tradebot/strategies.py`, lines 87–88 — code design)
- **Codex — AMEND & Challenge (F2/P-5)** (`sizing.py` already caps by cash so `3/€200` does not overspend €140 and `2/€65` still leaves 122 min-order rejections; preserve `S2Pullback` historical defaults `3/€200`, pass an owner-approved versioned demo override `2/€65` explicitly into both live construction and matching replay, split config/caller/test edits into separate proposals, and log the experiment): **ACCEPT** — cash capping prevents overspend and preserving historical P0 defaults while applying an explicit owner-approved demo override is cleaner and keeps old €400 backtests reproducible.

### `P-antigravity-6` (`src/tradebot/live.py`, lines 313–333 — code design)
- **Claude — APPROVE (merge with `P-codex-17`)** & **Codex — AMEND** (retain the independent-sleeve baseline under that name; add a distinct joint replay with actual activation/restart epochs, initial holdings, strategy priority, reservations, candidate sets, and execution policy; reason-code divergences and report comparable fills in bps; drop the collision-flag-only fallback): **ACCEPT** — matches our `P-codex-17` vote and Round 2 Q8 design; both proposals merge cleanly into one two-view design.

### `P-antigravity-7` (`src/tradebot/backtest.py`, lines 106, 163–203 — code design)
- **Claude — APPROVE (new metric keys only)** & **Codex — AMEND** (additive diagnostic metrics with explicit return frequency, dependence assumptions, complete trial-family provenance, and aligned finite IC; report both peak-relative and existing fixed-budget drawdown diagnostics; preserve existing `2×` all-cost runs and expose slippage-only stress as an additional labeled scenario; keep gate semantics out of `backtest.py` and keep `sim.costs_for` changes in a separate `sim.py` proposal): **ACCEPT** — preserves full backward compatibility, avoids breaking existing callers/tests, and enforces strict statistical provenance.

### `P-antigravity-8` (`src/tradebot/report.py`, lines 90–157 — code design)
- **Codex — AMEND & Implementation Caution** (`report.write()` lacks currency metadata and overlapping proxy series because `load_panel()` discards overlap; guard `total_profit_eur <= 0`; pass externally computed PSR/DSR/MinTRL with provenance rather than using `len(trials(strategy))` as `N_eff`; distinguish grouped trade attribution from separately simulated regional sleeves): **ACCEPT** — all four code-level observations are verified against `report.py` and `data.py`; the revised design takes explicit optional inputs and never treats `len(trials(strategy))` as `N_eff`.

### `P-antigravity-9` (`docs/06-backtesting.md` §5 — introduced in round 2)
- No Round 2 votes or objections yet (proposed in Round 2 in response to Claude Q3 & Codex Q8). Exact final text is supplied below, ready for voting before Claude applies it.

### `P-antigravity-10` (`docs/06-backtesting.md` §2.6 — introduced in round 2)
- **WITHDRAWN** in favor of `P-codex-30` (and `P-deepseek-9`) to avoid duplicate edits to `docs/06-backtesting.md` §2.6; see `## Withdrawn`.

*(Note on Codex's Round 2 Challenges F4/F5 regarding S4's 2011 divergence and local fill timestamps: accepted as factual clarifications — no pre-refresh `research.db` snapshot exists to prove which exact 2011 bar caused S4's flip, so that causal link is labeled **UNVERIFIED**, and `execution.apply()` timestamps reflect local observation times rather than broker execution times.)*

---

## Final texts

### Doc edits

#### `P-antigravity-1` — `docs/06-backtesting.md`

**1. §2.3 — Insert after exact line:**
> `Every report shows results at 1× and 2× costs.`

```markdown

Trading 212's Public API executes orders in the account's primary currency with no multi-currency wallet routing ([Trading 212 API overview](https://docs.trading212.com/api/instruments/exchanges) · [Help Centre](https://helpcentre.trading212.com/hc/en-us/articles/1500001809042-Multi-currency-accounts), checked 2026-11-25), so USD API trades always incur the 0.15 % FX fee per side. Keep the standard 2× all-cost run unchanged for historical comparability; optionally report a separate labeled `2× slippage + 1× FX` sensitivity run alongside it.
```

**2. §2.5 — Insert after exact line:**
> `- Market split for S2: US and EU results reported separately.`

```markdown
- Random-entry control (`S4`): evaluate against an ensemble of ≥ 50 seeds (median and 95th percentile Sharpe and CAGR), not a single seed.
```

**3. §4 — Replace exact line:**
> `- After many trials, use the deflated Sharpe ratio (Bailey & López de Prado 2014).`

```markdown
- Report the Probabilistic Sharpe Ratio `PSR(0)`, the Deflated Sharpe Ratio `DSR` (Bailey & López de Prado 2014; López de Prado, Lipton & Zoonekynd 2025/2026, [SSRN 5520741](https://doi.org/10.2139/ssrn.5520741), metadata checked 2026-11-25, full text UNVERIFIED), and the Minimum Track Record Length `MinTRL(95 %, 0)`. `DSR` is valid only over a complete, reconciled trial family (including any ad-hoc runs) and should note effective independent trials `N_eff` when trials are correlated.
```

**4. §7 — Insert after exact line (leaving the existing §7 table unchanged):**
> `| Any → Stop | Drawdown kill switch; live results materially worse than the backtest replay for 3 months; a broker or terms change |`

```markdown

**Proposed gate review items (pending owner decision; the table above remains in force):**
- Require promotion backtests to run on the exact live-tradable universe rather than a mixed US+EU universe when live is EUR-only.
- On a 5-year holdout, the isolated `holdout Sharpe >= 0.5 × IS Sharpe` criterion has `SE ≈ 0.45` under i.i.d. assumptions, giving high single-criterion false-positive and false-negative rates; review adding an in-sample Sharpe floor, `PSR(0)` / `DSR` over a reconciled trial family, and an explicit max-drawdown ratio vs the benchmark.
- For slow strategies (such as monthly S1, where 8 weeks is only 1–2 checks), review adding a minimum number of completed decision cycles alongside the 8-week demo soak, and note that demo ETF fills do not validate live spreads.
```

---

#### `P-antigravity-2` — `docs/03-strategies.md`

**1. §3 (S1) — Insert after exact line:**
> `| Why first | Robust, low turnover and simple, so it's ideal for proving the pipeline end to end |`

```markdown

*2026-11-25 note:* In the filed S1 reports, the monthly-trailed `3 × ATR(20)` stop accounted for 200/210 in-sample (95.2 %), 88/89 holdout (98.9 %) and 25/27 recent (92.6 %) exits, raising turnover to ~5–7×/yr. S1's parameters remain frozen through P1–P2. Testing a non-trailing catastrophic broker stop (`S1b`, e.g. fixed −15 % or fixed `5 × ATR(20)` at entry alongside the trailing `3 × ATR(20)` baseline) is queued for a future rolling walk-forward study on 2007–2019 in-sample data (2020–2024 is already spent for S1).
```

**2. §3 (S2) — Insert after exact line:**
> `| Known failure | Crashes that start inside an uptrend, before the filter reacts. The stop and the daily loss limit cover this. Earnings gaps are the LLM desk's job (R1). |`

```markdown

*2026-11-25 status:* The original €400 / 14-stock US+EU spec failed the P0 gate. Since 2026-09-30, S2 runs experimentally in demo on a **€140** budget across the **18 German EUR stocks** (26 US+EU stocks appear in backtests only). Code defaults in `S2Pullback` remain `max_positions = 3` and `max_position_eur = €200` (while `config/risk.toml` comments `S2/S3/S4 <= 2 each`); aligning demo caps to `2 / €65` via an explicit override is pending owner decision. Candidate replacements (monthly EUR stock momentum or EUR UCITS dual momentum) are deferred until trial provenance, `€5` risk-cap compatibility and owner direction are resolved.
```

**3. §3 (S3) — Insert after exact line:**
> `- **Status:** experimental. It trades demo money without having passed the "Idea → Demo" gate, by owner decision, and can't go live without passing every gate.`

```markdown
- **Universe note (2026-11-25):** The 2026-09-30 backtests used 26 US+EU stocks, whereas live demo trades only the 18 German EUR stocks. Any promotion test must run on the live EUR-18 universe.
```

**4. §3 (S4) — Insert after exact line:**
> `- **Why:** it's the null hypothesis. A strategy that doesn't beat random entries with the same exits and costs has no edge, whatever its backtest looks like.`

```markdown
- **Evaluation note (2026-11-25):** The 2026-09-30 backtest used 26 US+EU stocks and a single seed. Because a single seed is path-fragile, evaluate S4 in backtests as an ensemble of ≥ 50 seeds on the live EUR-18 universe.
```

**5. §4 (Portfolio construction) — Replace exact lines:**
> ```markdown
> - Each strategy has its own **budget** (S1 €600, S2 €400) and its own book in the journal, so P&L can be attributed to it.
> - If two strategies hold the same instrument, our ledger records two lots while the broker shows one net position. The ledger tracks lots per strategy, and reconciliation compares the net.
> - The risk engine's global caps ([05 §2](05-risk-and-safety.md#2-limits)) apply on top: capital deployed ≤ €1,000, at most 9 positions, and at most €250 per position.
> - Cash stays in EUR. USD for US stocks is converted per trade (Trading 212's 0.15 % FX fee), and that fee is part of the cost model.
> ```

```markdown
- Each strategy has its own **budget** and its own book in the journal, so P&L can be attributed to it. Since 2026-09-30, the active four-strategy demo split is S1 €600, S2 €140, S3 €130 and S4 €130 (€1,000 total).
- Live execution enforces a shared-book exclusion (`taken`): only one strategy may hold or open a given ticker at a time. The ledger tracks lots per strategy, and reconciliation compares net quantities against the broker.
- The risk engine's global caps ([05 §2](05-risk-and-safety.md#2-limits)) apply on top: capital deployed ≤ €1,000, at most 12 open positions (`config/risk.toml`), and at most €250 per position.
- Live demo trades EUR instruments only (6 Xetra UCITS ETFs and 18 German EUR stocks) until USD order pricing and a second market cycle are implemented. Cash stays in EUR; any future USD API trades incur Trading 212's 0.15 % per-side FX fee in the cost model.
```

---

#### `P-antigravity-3` — `docs/02-approaches.md`

**1. §2 (A. Rule-based systematic) — Replace exact line:**
> `- **−** The edges are small and widely known. Parameters are easy to overfit. The rules ignore news and context.`

```markdown
- **−** The edges are small and widely known. Parameters are easy to overfit. The rules ignore news and context. Recent empirical studies document heavy post-publication decay and cost erosion in high-turnover equity anomalies (Chen & Velikov 2023; Detzel, Novy-Marx & Velikov 2023) and post-2009 decay in short-term futures trend signals on small-tick contracts (Kurth et al. 2026), favouring slower horizons — though viability at our €1,000 cap must still be proven in our own backtests and forward checks.
```

**2. References — Insert after exact line:**
> `- Nof1 Alpha Arena, Season 1 (Oct–Nov 2025): [results summary](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/) · [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/)`

```markdown
- Chen, Velikov (2023). *Zeroing in on the Expected Returns of Anomalies.* *JFQA* (working paper [FEDS 2020-039](https://doi.org/10.17016/feds.2020.039), metadata/summary checked 2026-11-25; full text UNVERIFIED).
- Detzel, Novy-Marx, Velikov (2023). *Model Comparison with Transaction Costs.* *Journal of Finance* 78(3), pp. 1743–1775 ([doi:10.1111/jofi.13225](https://doi.org/10.1111/jofi.13225), metadata/summary checked 2026-11-25; full text UNVERIFIED).
- Kurth, Eisler, Rej, Bouchaud (2026). *Is Trend Still Your Friend?: A Microstructural Account of the Demise of Short-Term Trend-Following.* [arXiv:2607.01550](https://arxiv.org/abs/2607.01550) (abstract checked 2026-11-25; full PDF UNVERIFIED).
- Sepp, Lucic (2026). *The Science and Practice of Trend-Following Systems.* [arXiv:2607.19497](https://arxiv.org/abs/2607.19497) (abstract checked 2026-11-25; full PDF UNVERIFIED).
- Moskowitz, Sabbatucci, Tamoni, Uhl (2025). *Nonlinear Time Series Momentum.* [SSRN 5933974](https://doi.org/10.2139/ssrn.5933974) (metadata/summary checked 2026-11-25; full text UNVERIFIED).
- López de Prado, Lipton, Zoonekynd (2025/2026). *How to Use the Sharpe Ratio.* *Journal of Portfolio Management* / [SSRN 5520741](https://doi.org/10.2139/ssrn.5520741) (metadata/summary checked 2026-11-25; full text UNVERIFIED).
```

---

#### `P-antigravity-4` — `docs/3paperresearch.md`

**§3.2 — Replace exact line:**
> `` `pandas` already does it — `signal.corr(fwd_return, method="spearman")`, no `scipy`. Add it to `metrics()` in [backtest.py:179](src/tradebot/backtest.py:179) per strategy and per instrument, alongside the existing `sharpe_se`. ``

```markdown
`pandas` requires `scipy` for `method="spearman"`, so compute rank correlation without extra dependencies on aligned, unique-indexed finite pairs: `pairs = pd.concat([signal.rename("signal"), fwd_return.rename("return")], axis=1).replace([np.inf, -np.inf], np.nan).dropna(); ic = pairs["signal"].rank(method="average").corr(pairs["return"].rank(method="average"))` (returning `NaN` / undefined if fewer than 2 valid pairs remain or either series is constant). Add it to `metrics()` in [backtest.py:179](src/tradebot/backtest.py:179) per strategy and per instrument, alongside the existing `sharpe_se`.
```

---

#### `P-antigravity-9` — `docs/06-backtesting.md` *(introduced in round 2; awaiting ≥ 2 votes before applying)*

**§5 — Insert after exact line:**
> `- **Tracking check:** replay the same period in the backtester and compare trade by trade. Signals must match 100 %; a signal mismatch is a bug. Report fill-price differences (mean, max) and the P&L difference.`

```markdown
- **Shared-book replay vs independent baseline:** when multiple strategies share one book and ticker-ownership lock, keep two clearly labeled checks: (a) the **independent sleeve baseline** (each strategy alone on its live EUR universe, used for P0 research and ≥ 50-seed S4 null benchmarks), and (b) the **shared-book portfolio replay** (the P1/P2 implementation check). The shared-book replay starts from each strategy's actual activation/restart epoch and initial holdings/cash, runs exits before entries at the open, applies venue rounding, tracks `bars_held` from actual fill dates, and runs close decisions in fixed `settings.live.strategies` priority order while excluding symbols owned or pending-entry by another strategy (`taken`). Tag cross-strategy exclusions (`COLLISION`), `KILL` windows and operator catch-ups (`operator_event`) explicitly, and pass the same `taken`-filtered universe and date seed to S4.
- **Clean-start rule after multi-day outages:** do not drop a multi-day unhedged shutdown gap and stitch forward-check series across it. Preserve the prior record intact in the journal and reports, resolve stale positions under owner authorization, and restart the forward-check clock (`live.start`) from zero.
```

---

### Code designs (no code applied this round; P1 is paused and implementation needs the owner)

#### `P-antigravity-5` — `src/tradebot/strategies.py` (config/caller/test changes split into separate proposals when code resumes)
**Design:** Preserve `S2Pullback`'s historical defaults (`max_positions: int = 3`, `max_position_eur: float = 200.0`) so prior €400 P0 backtests remain reproducible, and support an explicit, owner-approved, versioned demo override (`max_positions = 2`, `max_position_eur = 65.0`) configured once and passed identically into live strategy construction and its matching forward replay. Because `sizing.py` already caps by cash, treat `2 / €65` as an explicit sleeve-policy override rather than an overspend fix, log the override as a new experiment version, and split the accompanying `config/settings.toml`, caller, and unit-test edits into separate file-level proposals once the owner confirms `2` vs `3`.

#### `P-antigravity-6` (merged with `P-codex-17`) — `src/tradebot/live.py`
**Design:** Retain the current per-strategy `backtest.run()` check in `Engine.forward()` explicitly relabeled as the **independent sleeve baseline**, and add a separate read-only **shared-book portfolio replay** for P1/P2 parity. The joint replay initializes from each strategy's recorded activation/restart epoch and starting holdings/cash, executes exits globally before entries at the open under the versioned execution policy with venue rounding, advances `bars_held` from actual fill dates, enforces fixed `settings.live.strategies` priority and `taken` reservations on close decisions (passing the same filtered universe and date seed to S4), assigns structured divergence reason codes (`COLLISION`, `operator_event`, `fill_policy`), and reports comparable live-vs-replay fill differences in basis points (mean and max) inside an exception-safe reporting boundary.

#### `P-antigravity-7` — `src/tradebot/backtest.py`
**Design:** Keep all existing metric keys, `2×` all-cost runs, and fixed-budget `would_trip` semantics untouched so historical outputs and tests remain unchanged, while adding strictly additive diagnostic keys to `_stats()` / `metrics()`: peak-relative drawdown alongside fixed-budget drawdown, skewness, Pearson kurtosis, lag-1 autocorrelation (`rho1`), non-normal and AR(1) Sharpe standard errors, `PSR(0)`, `MinTRL(95 %, 0)`, `DSR` (accepting explicit externally supplied trial-family metadata and `N_eff`, never inferring `N_eff` from a raw log count alone, with return frequency and dependence assumptions recorded), and pairwise-cleaned finite rank-Spearman IC (`P-antigravity-4`). Expose `2× slippage + 1× FX` only as an additional labeled cost scenario (with any `sim.costs_for` helper extension proposed separately in `sim.py`), and keep promotion-gate pass/fail logic out of `backtest.py`.

#### `P-antigravity-8` — `src/tradebot/report.py`
**Design:** Extend `report.write()` with optional explicit inputs (`instrument_meta`, `proxy_overlaps` captured prior to `data.load_panel()` stitching, externally computed `stat_summary` carrying trial-family provenance, and optional separately simulated regional sleeve results) so reporting never invents missing inputs or uses `len(trials(strategy))` as `N_eff`. When EUR and USD instruments are present, emit a grouped trade-attribution table by currency clearly distinguished from separately simulated regional sleeves; when `proxy_overlaps` is provided, print per-pair overlap CAGR difference, daily correlation, and tracking error; and report the maximum single-year profit share (`max_year_eur / total_profit_eur`, flagging `> 50 %`) only when `total_profit_eur > 0` (printing `n/a (non-positive total profit)` otherwise).

---

## Withdrawn

- **`P-antigravity-10`** (`docs/06-backtesting.md` §2.6 — accounting for unlogged exploratory trials before DSR/promotion gates): **WITHDRAWN** in favor of `P-codex-30` (`docs/06-backtesting.md` §2.1 & §2.6) and `P-deepseek-9` (`docs/06-backtesting.md` §4), which address the same unlogged-trial reconciliation gap alongside immutable data-snapshot provenance without duplicating proposals on §2.6.

---

## Answers

### Claude Round-3 Q3 (Antigravity): Exact count and inventory of 2026-11-25 ad-hoc runs

Because Round 3 rules permit writing only this report (do not edit `data/trials.jsonl`), `data/trials.jsonl` remains untouched at **127 rows** (0 dated 2026-11-25). Below is the complete, exact count and breakdown of every ad-hoc backtest executed during Round 1 (`antigravity-strategies.md`, all run read-only against `data/research.db` as of 2026-11-25 on working tree `42792f1` + uncommitted changes; **0 holdout `2020–2024` runs** were executed):

| Strategy / Candidate | Scope (2007–2019 IS unless noted) | Exact runs | New IS selection cells vs `trials.jsonl` | Notes |
|---|---|---:|---:|---|
| `s1_trend` | `atr_mult ∈ {2.0, 3.0, 4.0, 5.0, 6.0, 99.0}` × `{1×, 2×}` | **12** | **3** (`5.0, 6.0, 99.0`) | `2.0, 3.0, 4.0` were already in the 2026-09-25 18-cell grid; raises S1 `1×` IS trial count from `20` to `23` for any future `S1b` search (frozen S1 was frozen 2026-09-25). |
| `s2_pullback` | 14-stock `{0×, slip-only}` (2); US-8 `{0×, slip-only, 1×}` (3); EU-6 `{0×, 1×}` (2); EU-18 live `3/€200` `1×` (1); EU-18 `2/€65` `{1×, 2×}` (2) | **10** | **1** (`2/€65` cap variant) | 8 cost/region diagnostic decompositions + 1 cap-override check (`1×/2×`). Also computed 3 read-only `-RSI(2)` Spearman ICs (not backtests). |
| `s3_breakout` | All-26 `{1×, 2×}` (2 reproductions); EU-18 `{1×, 2×}` (2) | **4** | **0** (universe slice) | Live-universe diagnostic; also computed 2 read-only breakout ICs (not backtests). |
| `s4_monkey` | All-26 `{1×, 2×}` (2 reproductions); EU-18 10-seed ensemble at `1×` (10) | **12** | **0** (null control) | Random-entry null dispersion check, not parameter selection. |
| `C1` prototype | EU-18 52-week high momentum, `4×ATR` trailing variant, `{1×, 2×}` | **2** | **1** | Exploratory IS sanity check; C1 is **no longer `N = 0` untouched** and tested trailing `4×ATR` (not fixed `−15 %`). Holdout untouched. |
| `C2` prototype | 6-ETF 12-1m dual momentum, `4×ATR` trailing variant, `{1×, 2×}` | **2** | **1** | Exploratory IS sanity check; C2 is **no longer `N = 0` untouched** and tested trailing `4×ATR` (not fixed `−15 %`). Holdout untouched. |
| Forward-replay diagnostics | `2026-09-30 → 2026-10-05` replay for `S2, S3, S4` (`1×`) | **3** | **0** | Short implementation-parity diagnostics (F5), not IS search. |
| **Total** | **42 IS backtest runs + 3 forward-replay diagnostics** | **45** | **6 new cells/variants** | **0 holdout (`2020–2024`) runs.** Inline read-only commands; no runner scripts saved on disk. |

**Provenance note (also addressing Codex Round-2 Q3 & Deepseek Round-2 Q3):** No pre-2026-10-05 copy of `data/research.db` exists in `D:\TradeBot`, so attributing S4's 2011 divergence to a specific Yahoo bar revision remains **UNVERIFIED** (matching `P-codex-30`). When the owner authorizes trial-log updates, all 42 IS runs above should be appended as late registrations dated `2026-11-25` (with actual execution/registration dates preserved and `C1`/`C2` explicitly marked exploratory, never prospective).

*(Brief notes on Mistral Round-2 Q2 & Q3 addressed to Antigravity: live Trading 212 bid-ask spreads on Xetra/Gettex EUR-listed US mega-caps such as `APCd_EQ` remain **UNVERIFIED** without live quote data, and broadening the P2 LLM desk scope from S2 to S3 or a future single-stock replacement is an owner decision per `P-deepseek-5`, keeping S4 unmodified as the control book.)*
