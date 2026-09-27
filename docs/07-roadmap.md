# 07 — Roadmap

Durations are estimates for one part-time developer.

| Phase | Goal | Deliverables | Exit gate | Estimate |
|---|---|---|---|---|
| **P0: Foundations & backtest** | Prove S1/S2 honestly, offline | Repo skeleton; config and validation; data module (Yahoo history cross-checked against Alpaca, ECB FX, UCITS proxies) and cache; models; indicators; strategies S1/S2; sizing (€1,000 cap, fractional); SimBroker; backtest engine with metrics and report; risk engine (unit-tested); trial log | "Idea → Demo" ([06 §7](06-backtesting.md#7-promotion-gates)) for at least one strategy | 2–3 weeks |
| **P1: Shadow & demo engine** | Run the full loop live with demo money | Laptop hardened for 24/7 ([09 §6](09-hosting.md#6-laptop-checklist-p0p2)); exchange calendars (XETR, XNYS); Trading 212 demo adapter (rate-limit aware); order manager with the submit-once protocol ([04 §4](04-architecture.md#4-core-data-contracts-sketch)); protective stops; reconciler; kill switch; watchdog; dead-man's switch; journal; CLI; daily report; Telegram alerts | 2 weeks of clean unattended runs; drills 1–8 pass ([05 §11](05-risk-and-safety.md#11-drills-all-must-pass-before-each-promotion)) | 3–4 weeks |
| **P2: LLM desk (shadow) + demo soak** | Measure what each of the 5 models adds; build up demo evidence | Provider adapters (Anthropic, OpenAI, Google, OpenRouter); news and events sources (Alpaca News, Marketaux, Finnhub, `events.toml`, [08 §3.1](08-multi-agent-llm.md#31-news-and-event-sources-decided-2026-09-25)); news analyst; jury; aggregator; reporter; runtime and eval budget guards; offline eval set + injection tests; counterfactual books A/B/J1–J5; ≥ 8 weeks of demo trading | "Demo → Gated live"; decide which jurors to keep | 8+ weeks (mostly waiting) |
| **P3: Gated live (optional)** | Real orders within the €1,000 cap, each approved by a human | VPS migration ([09 §7](09-hosting.md#7-vps-checklist-p3)); Trading 212 live keys on the VPS only; Telegram approvals; live arming | "Gated → Bounded autonomy" | 4+ weeks |
| **P4: Bounded autonomy (optional)** | Human approval only above thresholds | Threshold rules; a weekly review routine | Ongoing; stop criteria in [06 §7](06-backtesting.md#7-promotion-gates) | ongoing |

P3 and P4 happen only if the owner explicitly decides so. At the end of P2 the project is already complete and useful as a research system.

**Status (2026-09-25): P0 complete.** S1 passed the "Idea → Demo" gate, while S2 failed in-sample and doesn't go to demo. All steps, findings and results are in the [build log](10-build-log.md). Three owner decisions are open before P1 ([10, step 11](10-build-log.md#step-11-backtest-results-and-the-p0-gate)).

## P0 backlog (first sprint)

1. Repo setup: `git init`, a `uv` project with a hashed lockfile, `.gitignore` (`data/`, `*.db`, `.env`), `pytest`.
2. `models.py` dataclasses ([04 §4](04-architecture.md#4-core-data-contracts-sketch)), with `Decimal` for money and quantities.
3. Config loading with bounds validation and a hash, plus a test that the engine refuses to start on bad config.
4. `data.py`: Yahoo bars for all instruments into the SQLite cache, cross-checked against Alpaca for US names; validation checks; EUR conversion; UCITS proxy stitching. (Stooq, the original EU source, now blocks scripts: [10, step 4](10-build-log.md#step-4-market-data-srctradebotdatapy-python--m-tradebot-data).)
5. `indicators.py`: SMA, ATR, RSI, Bollinger bands and rolling σ, each with a known-value test.
6. `strategies/s1_trend.py` and `s2_pullback.py`, with tests on synthetic price series whose entry and exit bars are known.
7. `sizing.py` (inverse volatility, risk-based, €1,000 cap, per-strategy budgets, fractional, min/max order) with tests.
8. `brokers/sim.py` implementing the execution model ([06 §2.2](06-backtesting.md#22-execution-model)), with tests for an unfilled limit on a gap up and a gap through the stop.
9. `backtest.py`: the loop, metrics, markdown report and trial log.
10. `risk.py`: pre-trade checks and kill-switch persistence, with a failing-case test for every check.
11. Run S1 and S2 in-sample, run the robustness grids, freeze parameters, run the holdout once, and write the reports.

## Trading 212 API facts and P1 adapter tests

Most questions are answered by Trading 212's API docs ([01 §4.1](01-platforms.md#41-trading-212-primary-venue)). What the docs leave open becomes an automated adapter test against the demo account.

| Question | Answer | Status |
|---|---|---|
| Can stop orders use `GOOD_TILL_CANCEL`? | `timeValidity` is `DAY` or `GOOD_TILL_CANCEL` | ✅ documented; adapter test places a GTC stop |
| Rate limits and HTTP 429 | Per endpoint (e.g. limit/stop orders 1 per 2 s); `x-ratelimit-reset` header; 429 when exceeded | ✅ documented |
| Client order reference for idempotency | **None.** Docs warn that repeated requests may create duplicates | ✅ documented → submit-once protocol ([04 §4](04-architecture.md#4-core-data-contracts-sketch)) |
| API key permissions | Chosen at key creation; optional IP allow-list; no money-movement endpoints | ✅ documented → key split in [05 §9](05-risk-and-safety.md#9-secrets--access) |
| Can API positions be closed by the API? | Yes. Positions opened manually reportedly can't be. | ✅ design: bot-only account |
| Are limit/stop orders placed while the market is closed queued for the open? | **Yes**: a DAY limit placed on a Saturday was accepted with status NEW | ✅ tested 2026-09-26 ([10](10-build-log.md#p1-preview-first-demo-order-on-trading-212-2026-09-26)) |
| Minimum fractional step per instrument | Not in the metadata (`minTradeQuantity` absent); 4-decimal quantities are accepted (0.0348 SXR8) | ✅ partly: sizing rounds down to 4 decimals |
| Ticker / ISIN mapping for the whitelist | `t212-map` → `config/t212_tickers.toml`, 20/20 (XOM's ISIN corrected) | ✅ done 2026-09-26 |
| Final status of filled/cancelled orders | They leave the active list (404); the final status is in order history | ✅ handled in `wait_for()` |
| Does demo behave like live? | Same API and order types | 🧪 re-run the adapter tests with live keys at the P3 gate (read-only calls plus one €20 order) |

**Needs the owner** (account setup, which I can't do): create the Trading 212 practice account and a demo API key, and a free Alpaca account for US data and news (start of P0). The LLM provider keys come later, at the start of P2.

## Definition of done (every item)

- Non-trivial logic has tests, and they pass.
- Every state change produces a journal event.
- The docs are updated wherever behaviour differs from them.

## Schedule risks

| Risk | Mitigation |
|---|---|
| Strategies fail the gate | That's a valid research outcome. Keep the pipeline and try the next family from [03 §2](03-strategies.md#2-strategy-families-surveyed). |
| The demo phase is slow (S1 trades rarely) | S2 trades across two markets; the desk is evaluated on S2 entries mostly |
| Trading 212 beta API changes or lacks a needed feature | The adapter is isolated; IBKR is the documented fallback ([01 §4.2](01-platforms.md#42-interactive-brokers-fallback)) |
| Free EU data source breaks | Cross-checks catch it; EODHD is the paid upgrade path |
| LLM model churn (new versions monthly) | The roster lives in config; the eval set runs before any swap |
| Scope creep (dashboards, more strategies, intraday data) | Nothing extra before the P2 gate |
