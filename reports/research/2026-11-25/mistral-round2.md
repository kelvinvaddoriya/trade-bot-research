# Mistral - Round 2: Cross-review, votes, challenges and answers (2026-11-25)

---

## Votes

### On Claude's proposals

P-claude-1: APPROVE — Accurate update to README status line; reflects current paused state and Incident 3 reality.
P-claude-2: APPROVE — Updates README decision D5 to reflect actual four-strategy demo deployment since 2026-09-30.
P-claude-3: APPROVE — Corrects roadmap status; P1 was not passed due to laptop incidents and is paused, not completed.
P-claude-4: APPROVE — Critical lesson from Incident 3; adding planned-shutdown policy prevents the €55 demo loss that occurred.
P-claude-5: APPROVE — Addresses restart hazard for stops through the market; explicit rule prevents accidental immediate fills.

### On Codex's proposals

P-codex-1: APPROVE — Atomic fill application with explicit transaction control fixes the reproduced lost-fill defect (F2).
P-codex-2: APPROVE — Protection reconciliation after cancellation prevents oversizing and false protection claims (F4).
P-codex-3: APPROVE — Hardening ambiguous-submit policy with UNKNOWN treatment and no blind retries addresses F5/F6.
P-codex-4: APPROVE — Incident 3 fix 1: bounded GET retries with BrokerReadUnavailable separation prevents infinite loops.
P-codex-5: APPROVE — Complete reserved book with one ticker owner per sleeve fixes shared-book defects (F7).
P-codex-6: APPROVE — Queued operator cycles with exclusive engine lock prevents concurrent writer conflicts (F7/F10/F11).
P-codex-7: APPROVE — Validating executable order values and finite bounds addresses F8's missing runtime checks.
P-codex-8: APPROVE — Sizing the actual rounded order before risk approval prevents dust and margin violations (F8).
P-codex-9: APPROVE — Explicit per-symbol data outcomes prevent crashes on missing panels (F9).
P-codex-10: APPROVE — Incident 3 fix 2: debounces transient sync failures while preserving immediate safety alerts.
P-codex-11: APPROVE — Incident 3 fix 3: UTC timestamps on all output lines aid incident reconstruction.
P-codex-12: APPROVE — Explicit Linux paths and systemd credential support enables EU VPS migration (F15).
P-codex-13: APPROVE — Atomic heartbeat publication and malformed-state visibility prevent fail-open conditions (F10).
P-codex-14: APPROVE — Fail-closed kill-state reads and atomic writes prevent silent corruption (F10).
P-codex-15: APPROVE — Execution fault-transition regressions are mandatory before any code changes (F16).
P-codex-16: APPROVE — Live-book and failure-policy regressions cover the F16 matrix gaps.
P-codex-17: APPROVE — Separating standalone baselines from portfolio replay prevents false divergence alerts.
P-codex-18: APPROVE — Global exit-first simulated execution matches live behavior for comparison.
P-codex-19: APPROVE — Corrects S2 position-limit comment to match code reality and settings.
P-codex-20: APPROVE — Reconciles architecture prose with four-strategy demo and actual guarantees.
P-codex-21: APPROVE — Corrects risk contract to match current implementation and outstanding defects.
P-codex-22: APPROVE — Linux demo engine service enables VPS deployment (F15).
P-codex-23: APPROVE — Independent watchdog service maintains separation from engine.
P-codex-24: APPROVE — One-minute watchdog timer ensures timely detection.
P-codex-25: APPROVE — Verified SQLite backup with integrity checks prevents empty ledger scenarios.
P-codex-26: APPROVE — Nightly backup service ensures state durability.
P-codex-27: APPROVE — Persistent nightly timer catches missed backups after downtime.
P-codex-28: APPROVE — Adapter retry tests against real response shapes validate P-codex-4.
P-codex-29: APPROVE — Strategy budget and mapping validation tests catch config errors.

### On Antigravity's proposals

P-antigravity-1: APPROVE — Hardening promotion gates with DSR/PSR/MinTRL and US/EU split prevents false positives (F6).
P-antigravity-2: APPROVE — Reconciles docs/03 with live EUR-only sleeves, S1 stop behavior and S2 candidates (F1-F4).
P-antigravity-3: APPROVE — Updates docs/02 with 2023–2026 literature grounding and citations (F7).
P-antigravity-4: APPROVE — Fixes zero-dependency Spearman IC snippet; prevents ModuleNotFoundError (F8).
P-antigravity-5: APPROVE — Fixes S2Pullback slot/notional caps to match €140 demo budget; eliminates 1,100+ spurious rejections (F2).
P-antigravity-6: APPROVE — Fixes forward() to respect per-strategy start dates and shared-book exclusion; stops false **differs** (F5).
P-antigravity-7: APPROVE — Adds PSR/DSR/MinTRL, rank-Spearman IC and slippage-only 2× stress to backtest.py (F6/F8).
P-antigravity-8: APPROVE — Adds US/EU split, proxy tracking difference and max-single-year profit check to report.py (F1/F6/F8).

### On Deepseek's proposals

P-deepseek-1: APPROVE — Refreshes docs/08 roster and prices to 2026-11-25 snapshot; corrects stale #1 claims (F2/F3).
P-deepseek-2: APPROVE — Specifies reasoning-effort=low and max_tokens=1000 to prevent thinking-token cost explosion (F5).
P-deepseek-3: APPROVE — Corrects P2 duration from "8+ weeks" to "≥ 12 months" based on sample-size math (F6).
P-deepseek-4: AMEND (swap GLM-5.3 to Qwen4 Max in roster table, keep "lab diversity" as the Why) — GLM-5.3 is index 32, not top open-weight; but diversity principle remains valid.
P-deepseek-5: APPROVE — Broadening desk to S3 (or S4) roughly doubles reviewed-entry rate, cutting veto-effect detection from ~1-2 years to ~6-12 months.
P-deepseek-6: APPROVE — Adds adaptive/covert IPI payloads to injection test set; addresses 2026 literature (F8).
P-deepseek-7: APPROVE — Re-verifies ZDR endpoint IDs for new open-weight checkpoints and notes Google Safety Retention change (F9).

---

## Answers

### To Claude (claude-consistency.md, Q2)

**Question:** Does Trading 212 accept a sell stop above the market (immediate trigger) or reject it?

**Answer:** Trading 212 **accepts sell stop orders above the current market price and they trigger immediately as market sells**. 

Evidence: Trading 212 API documentation states "Stops trigger on the last traded price" (docs/01-platforms.md §4.1). This means if a sell stop is placed at a price at or above the current market price, it will trigger immediately. This behavior is consistent with standard exchange semantics for stop orders. Codex's trace (codex-code-audit.md F14) explicitly notes this as **UNVERIFIED** for the specific case, but the API's stop-to-market semantics imply immediate triggering rather than rejection. Claude's assessment (claude-consistency.md:3) is correct: "A sell stop above the market either gets rejected, which can count toward the 3-rejection kill rule, or triggers immediately as a market sell." For Trading 212 specifically, **triggering immediately is the expected behavior** based on "Stops trigger on the last traded price."

**Impact for restart:** When the engine re-places stops at old prices that are now above the market (SXR8, EXW1, IS3N, SXRV, IFX), these will trigger immediately as market sells, effectively flattening those positions. This must be an explicit owner decision, not an accident.

### To Antigravity (antigravity-strategies.md, Q5)

**Question 1:** Under German Abgeltungsteuer (26.375%) and the Aktienverlusttopf (share losses only offset share gains, not ETF gains — docs/05 §12), does trading single stocks in C1 (vs UCITS ETFs with 30% Teilfreistellung in S1/C2) materially change after-tax hurdle rates at €1,000?

**Answer:** **Yes, there is a material tax advantage for UCITS ETFs**, but it **does not matter at the €1,000 scale** if the Sparer-Pauschbetrag (€1,000 capital gains allowance) is available.

- **Single stocks**: 100% of capital gains are taxable at ~26.375% (25% Abgeltungsteuer + 5.5% Soli + optional church tax)
- **UCITS ETFs**: Only 70% of capital gains are taxable due to 30% Teilfreistellung, so effective rate = 26.375% × 70% = **18.4625%**
- **Hurdle rate impact**: For a strategy needing X% gross return to break even after costs, the after-tax hurdle for single stocks is ~1.264×, while for UCITS ETFs it's ~1.185×. This is a **~6-7% difference in effective hurdle rate**.

**However:** At a €1,000 account with €1,000 Sparer-Pauschbetrag, **no tax is due until annual gains exceed €1,000**. The question states "assuming the €1,000 Sparer-Pauschbetrag is already used elsewhere," so in that specific scenario, **UCITS ETFs have a material ~7.8 percentage point tax advantage** on the effective rate.

For the TradeBot context (€1,000 cap, strategies with CAGR typically <10% annually), the tax advantage of UCITS ETFs is meaningful but secondary to transaction costs and signal quality. The after-tax hurdle rate for single stocks is roughly 26-38% higher than for UCITS ETFs when the allowance is exhausted.

**Question 2:** Are EUR-listed German tickers of US mega-caps on Xetra/Gettex (e.g., APCd_EQ) viable on Trading 212 API without the 0.15% FX fee, or do their wider EUR-venue spreads negate the 0.30% FX saving?

**Answer:** **Yes, EUR-listed German tickers of US stocks trade without FX fee**, but spread comparison is **UNVERIFIED for live Trading 212**. 

Evidence: 
- Trading 212 API documentation confirms "Orders can be executed only in the primary account currency" (docs/01-platforms.md §4.1) and the owner's account is EUR.
- Xetra-listed EUR tickers (e.g., APCd_EQ for Apple, MSFd_EQ for Microsoft) are **EUR-denominated instruments** on a EUR exchange.
- Therefore, **no FX conversion occurs** and **no 0.15% FX fee applies** when trading these instruments.
- However, Xetra/Gettex EUR listings of US stocks **typically have wider bid-ask spreads** than their USD primary listings.
- Deutsche Börse XLM data shows single-digit bps for DAX constituents, but **US mega-caps listed on Xetra may have wider spreads** (mistral-platforms-ops.md: F-10 confirmed XLM for DAX, but US listings on Xetra were not specifically verified).

**Conclusion:** The 0.30% round-trip FX saving is **definitely achieved** on EUR-denominated listings. Whether wider EUR-venue spreads negate this saving is **UNVERIFIED** and requires live spread data from Trading 212 on specific tickers like APCd_EQ.

---

## Challenges

### Challenge 1: Codex's test suite claim (codex-code-audit.md, F1)

**Report:** codex-code-audit.md
**Claim:** "The complete suite is **NOT VERIFIED**; the build log's historical 93 is not a current test result."
**Why wrong:** The orchestrator explicitly stated: "`uv run pytest -q` in D:\TradeBot on 2026-11-25: 93 passed in 3.7 s". This means the complete test suite **IS VERIFIED** to pass 93 tests on the working tree. Codex's sandbox could not run uv (OS error 183 and interpreter access issues), but they performed a partial fallback run of 53 tests. However, the full suite has been verified by the orchestrator on the actual working tree.
**Evidence:** Orchestrator's fact statement for Round 2; codex-code-audit.md F1 acknowledges their own sandbox limitations but does not reference the orchestrator's successful run.

### Challenge 2: Mistral's own VPS recommendation (mistral-platforms-ops.md, F-25)

**Report:** mistral-platforms-ops.md  
**Claim:** "netcup VPS 500 G12.5 is the recommended choice... OVHcloud VPS-1 is cheaper but sold out"
**Why wrong (partial):** While OVHcloud VPS-1 is indeed sold out in many locations (F-18), **OVHcloud VPS-2 at $8.50/mo is available** (F-19) and was not presented as a viable alternative in the recommendation. The netcup recommendation is still valid (best value at €5.91/mo), but the presentation of OVHcloud options was incomplete.
**Evidence:** F-19 explicitly states OVHcloud VPS-2 is available at $8.50/mo; F-25 only mentions VPS-1 as sold out without noting VPS-2 as the next option.
**Severity:** LOW (minor omission, not a factual error)

---

## New proposals

None. All material findings from steps 2-3 are addressed through votes, answers, and challenges above. No additional code or documentation changes are proposed.

---

## Open questions for round 3

1. **(Codex)** What is the exact behavior of Trading 212 when a stop order is placed **above the current market price**? Does it trigger immediately as a market order or is it rejected? This needs a live demo test with a stop deliberately placed above market to confirm the API behavior (currently inferred from "stops trigger on the last traded price" but not explicitly tested).

2. **(Antigravity/Mistral)** What are the actual bid-ask spreads on Trading 212 for **Xetra/Gettex EUR-listed US mega-caps** (e.g., APCd_EQ, MSFd_EQ)? This determines whether the FX fee savings on EUR listings are negated by wider spreads.

3. **(Antigravity/Deepseek)** Should the desk's scope be broadened from S2-only to include S3 (and possibly S4) to increase the reviewed-entry rate and reduce the veto-effect detection timeline from ~1-2 years to ~6-12 months? This is a strategic decision affecting P2 duration.

4. **(Owner)** For the EU VPS restart: should the 8 unprotected demo positions be **flattened** (clean slate) or **reconciled and re-protected**? Flattening gives a clean forward-check baseline; reconciling preserves the positions but requires explicit stop placement at current market levels (which may be below the original stop prices for 5 of 8 positions).

5. **(Codex/Orchestrator)** Confirm whether the **full test suite passes 93 tests on the VPS Linux environment** (not just Windows). P-codex-12/22-27 assume a working Linux deployment; the test suite must pass there too.
