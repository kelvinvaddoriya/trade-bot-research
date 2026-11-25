# Research round 2026-11-25 — synthesis

Orchestrator: Claude. Agents: Codex (gpt-6-astra), Antigravity (gemini-4-neon), Mistral (Vibe), Deepseek (deepseek-v4-pro via OpenCode). Rules: [`Agent-Guide.md`](../../../Agent-Guide.md) (revised today). Rounds: 1 research → 2 cross-review and vote → 3 authors accept or decline the amendments → apply → 4 verify the applied text and vote on the carried proposals.

> Not investment advice. All trading here is demo money on the Trading 212 practice account.

## 1. What matters most (read this first)

| # | Finding | Severity | Who found it | Status |
|---|---|---|---|---|
| 1 | **The current system isn't in git.** About 700 changed lines in 20 tracked files, plus ~30 untracked files (S3/S4, the 18-stock universe, the qty-precision fix, Incident 3, the daily reports, `docs/3paperresearch.md`, `docs/guide/`), have been uncommitted since early October. The last commit is 42792f1 (2026-09-29). | HIGH | Claude | **Owner decision:** commit to a branch |
| 2 | **5 of the 8 open demo lots are below their old stop prices** (SXR8, EXW1, IS3N, SXRV, IFX; Yahoo closes 2026-11-25). Unrealised ≈ −€64; with the stops kept, ≈ −€8. All stops were cancelled for the 10-06 shutdown. | HIGH | Claude, re-derived by Antigravity | docs/05 now has a planned-shutdown rule |
| 3 | **Restart hazard:** on start, `ensure_stops()` re-places each stop at its stored price without comparing it with the market. Trading 212's docs don't say what a sell stop above the market does (checked 2026-11-25). KILL also blocks non-flatten exits (`execution.py:307`). | HIGH | Claude, Codex, Antigravity | Recovery design in docs/04, marked "not implemented" |
| 4 | **Fills aren't crash-atomic.** The ledger is in autocommit mode, and `apply()` writes the order's fill watermark before the lot, so a crash in between loses the fill. Partial fills break P&L and stop sizing (reproduced). | HIGH | Codex, verified by Claude | Change set A (code; needs the owner) |
| 5 | The shared book misses submitted/unfilled entries and other sleeves' reservations; whole-book valuation is inconsistent across sleeves. | HIGH | Codex | Change set C |
| 6 | **S2's code caps (3 / €200) don't match its €140 demo budget** (`strategies.py:87-88`), causing ~1,100 below-minimum rejections in backtests. | MED | Antigravity, verified | **Owner decision:** 2 / €65 override |
| 7 | **S1's stop does almost all the exiting**: 200/210 in-sample, 88/89 holdout. S1 behaves like a trailing-stop system more than a trend filter. It stays frozen; a walk-forward study is queued. | MED | Antigravity | docs/03 note |
| 8 | **The S3/S4 backtests used 26 US+EU stocks, but live trades 18 German stocks.** On EUR-18, S3 is flat at 2× costs. A single-seed S4 is path-fragile. | MED | Antigravity | docs/03 notes; ≥ 50-seed S4 in docs/06 |
| 9 | **Promotion gates:** the "holdout Sharpe ≥ ½ in-sample" rule is weak on a 5-year holdout. DSR, PSR and MinTRL are promised in docs/06 but never computed. | MED | Antigravity (statistics re-derived by Deepseek) | docs/06: reporting added; gate changes marked "pending owner decision" |
| 10 | **The LLM desk's P2 would take months to years, not "8+ weeks"**, to show a veto effect at 5–8 S2 entries a month. No desk code exists yet. | MED | Deepseek | docs/07 corrected; desk scope is an owner decision (docs/08) |
| 11 | docs/08's model rankings are stale ("Opus 5.5 #1" no longer holds; GLM/Kimi are not "top open-weight"). The ZDR endpoints for the open-weight seats were re-checked. | LOW | Deepseek, corrected by Antigravity and Codex | docs/08 corrected |
| 12 | The three Incident 3 fixes (retrying read-only GETs, alerting only after N failures, timestamped logs) are designed in detail. | MED | Codex | Change set D |

## 2. What was applied to the docs (37 edits, 17 proposals)

Each passed with ≥ 2 approvals from other agents, with every amendment accepted by its author and no unresolved factual objection (handbook §3.3). Applied by script with exact anchors. The originals are backed up.

| File | Proposals |
|---|---|
| README.md | P-claude-1 (status: paused since 10-06), P-claude-2 (D5: the four demo strategies) |
| docs/01-platforms.md | P-mistral-2 (quantity precision is empirical, not a documented rule) |
| docs/02-approaches.md | P-antigravity-3 (2023–26 literature; full texts marked UNVERIFIED) |
| docs/03-strategies.md | P-antigravity-2 (S1 stop share; S2 €140 and the 3/€200 mismatch; EUR-18 vs 26-stock backtests; ≥ 50-seed S4; the €600/€140/€130/€130 split; cap 12) |
| docs/04-architecture.md | P-codex-20 (four-strategy demo, float/REAL not Decimal, non-atomic fills), P-claude-5 (restart recovery design, not implemented) |
| docs/05-risk-and-safety.md | P-claude-4 (planned-shutdown rule), P-codex-21 (demo limits 12/20, reset doesn't reconcile, implementation gaps), P-deepseek-6 (injection tests: iterative and covert payloads) |
| docs/06-backtesting.md | P-antigravity-1 (FX note, ≥ 50-seed S4, PSR/DSR/MinTRL; gate changes listed as *pending owner decision*) |
| docs/07-roadmap.md | P-claude-3 + P-deepseek-3 (status: P1 paused, not passed; P2 duration corrected) |
| docs/08-multi-agent-llm.md | P-deepseek-1 (three ranking corrections), 2 (reasoning-effort and token caps), 4 (lab-diversity wording), 5 (desk scope as an owner decision), 7 (ZDR re-check) |
| docs/3paperresearch.md | P-antigravity-4 (Spearman IC without scipy, pairwise-clean) |

**Not applied:** P-codex-19 (2–2 tie; superseded by the S2 owner decision). Mistral 1, 3, 4, 5 and 6 were withdrawn after factual objections: wrong VPS prices (three of four figures), an unverified "FXFlat partnership", and a restart runbook that framed the demo restart as live money with invented APIs. **No code was changed.** The 29 Codex code proposals and the Antigravity code designs are approved *as designs* only.

## 3. Decisions for the owner

1. **Commit the working tree** to a branch (finding 1). Nothing else is safe until two months of work have a backup.
2. **The 8 open demo lots at restart:** exit by rule (recommended: breached stops and overdue time exits exit through `kill --flatten` at the first session, so the forward check restarts clean), or keep them and re-stop at new levels.
3. **S2's demo caps:** keep the code defaults 3 / €200, or apply a versioned override of 2 / €65 to match the €140 budget.
4. **Code change sets, in order:**
   - A: atomic fills plus regressions;
   - B: the protection/UNKNOWN protocol plus the restart rule;
   - D: the Incident 3 fixes;
   - C: book, risk and request ownership;
   - E: the Linux VPS deployment (systemd units, backup).
   - A, B and D come before any restart.
5. **Ambiguous order submits:** no automatic resubmit (recommended), or accept the residual duplicate risk (Codex Q1).
6. **Promotion gates:** adopt any of the "proposed gate review items" now listed in docs/06 §7.
7. **LLM desk scope:** S2 only, with a multi-year shadow study, or S2 + S3 (docs/08 §2).
8. **The VPS:** docs/09's choice (OVHcloud VPS-1) still stands; its table was confirmed in round 4. The restart runbook is now docs/09 §8.

## 4. Carried to the next round

Resolved in round 4 (§6). Still open: none from the vote. The code change sets (§3, item 4) wait for the owner. Codex re-joins after 2026-11-26 02:39 and can review the round-4 texts written from its proposals (P-codex-21's completion, P-codex-30).

## 5. Process notes (honest)

- **Orchestrator error:** round 1 was first launched against the stale worktree `Trade-Bot-Research/` (commit 42792f1). It was caught within minutes, all agents were stopped and re-briefed on `D:\TradeBot`, and nothing had been written.
- **Orchestrator error 2:** in round 2 the orchestrator relied on a garbled web summary and called netcup's €9.50 a 12-month price. It was month-to-month. Antigravity caught it in round 4, and P-claude-6 was withdrawn. Mistral's VPS figures were still wrong on other points.
- **Orchestrator disclosure:** one sentence of P-deepseek-3 was dropped when it was applied. It was disclosed, and the author accepted it.
- **Unlogged trials:** Antigravity's ad-hoc backtests (pure SMA(200), C1, C2, EU-18 runs, the 10-seed S4) are not in `data/trials.jsonl`. They count as trials (docs/06), and P-codex-30 covers reconstructing them.
- **Vote quality varied.** Mistral approved every round-2 proposal, including two that conflict, and its round-1 prices were mostly wrong. Antigravity and Codex verified claims against code and primary sources. The 3.3 rule ("no unresolved factual objection") stopped the wrong figures from reaching the docs.
- **Codex** hit its usage limit in round 3 (resets 2026-11-26 02:39), so its two doc proposals were applied from the round-1 descriptions and checked in round 4.
- **Machine:** free RAM fell to ~0.6 GB while four agents ran. The engine is off, so there was no trading impact, but it's the same failure mode as Incidents 1–3.
- **Tests:** `uv run pytest -q` → 93 passed (2026-11-25).

## 6. Round 4 (verification of the applied text, carried votes)

Run as Orca chats: Antigravity, Deepseek (OpenCode) and Mistral (Vibe, in an Orca terminal; OpenCode's Mistral key was invalid). Codex was absent (usage limit).

**Verification of the 37 edits:** Deepseek and Mistral found every edit faithful. Antigravity found 34 exact or accurate and flagged 3:

| Flag | Resolution |
|---|---|
| P-deepseek-3: the orchestrator dropped the trailing sentence "The status line is updated under P-claude-3." | Disclosed to the author; **Deepseek accepted** the omission (deepseek-round4.md) |
| P-codex-21: the stale-data gap from Codex's description was missing | **Added** after checking the code: `MAX_BAR_AGE_DAYS = 5` (`risk.py:17`). The two-stale-cycles halt (`live.py:295`) fires only for a strategy that skips its cycle (S1); per-stock strategies drop a stale stock at the deadline (`live.py:259-262`), so a held stale stock never trips it. |
| docs/3paperresearch.md: the `backtest.py` link was broken from `docs/` (it predates this round; also flagged by Deepseek) | **Fixed** to `../src/tradebot/backtest.py` |

**Carried proposals:**

| Proposal | Antigravity | Mistral | Deepseek | Result |
|---|---|---|---|---|
| P-claude-6 (netcup row) | REJECT (factual) | APPROVE | AMEND | **Withdrawn.** The orchestrator's netcup reading was wrong: €7.98 net / **€9.50 gross is month-to-month** and €6.94 / €8.26 is the 12-month term (the arithmetic checks: × 1.19). **docs/09's existing row was right**, and the orchestrator's round-2 note on netcup is retracted. Mistral's €5.91 / 128 GB figures remain wrong. |
| P-claude-7 (VPS restart runbook) | AMEND | APPROVE | APPROVE | **Passed with Antigravity's amendments accepted.** Step 3 is a read-only inventory (`reconcile` writes to the ledger); change set E is added; KILL stays tripped through the recovery exits and stops, matching P-claude-5. Applied as docs/09 §8. |
| P-antigravity-9 (shared-book replay, clean-start rule) | author | APPROVE | APPROVE | **Passed**; applied in docs/06 §5 |
| P-codex-30 (data provenance, late-registered trials) | APPROVE | APPROVE | APPROVE | **Passed**; applied in docs/06 §2.6 |

**Round 4 totals:** 5 more edits in 4 files (docs/05, docs/06, docs/09, docs/3paperresearch). Over the whole round: **42 edits, 20 passed proposals, 0 code changes.**

## Reports in this folder

Round 1: `claude-consistency.md`, `codex-code-audit.md`, `antigravity-strategies.md`, `mistral-platforms-ops.md`, `deepseek-desk-roadmap.md` · Round 2: `*-round2.md` · Round 3: `*-round3.md` · Round 4: `*-round4.md`
