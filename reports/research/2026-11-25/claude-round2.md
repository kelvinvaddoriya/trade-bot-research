# Claude — round 2: votes, answers, challenges (2026-11-25)

Verification I did before voting: `uv run pytest -q` (93 passed); read `execution.py:152-184` and `store.py:31`; read `strategies.py:87-88` against `settings.toml`/`risk.toml`; checked `pyproject.toml`/`uv.lock` for scipy; checked docs/08 lines 15/28/29/41 and README:96; and had a web-fetch agent check the OVH, netcup and Hetzner price pages, the T212 tax help article and the T212 stop-order API page (all fetched 2026-11-25).

## Votes

### Codex
- P-codex-1: APPROVE (design). Confirmed: autocommit (`store.py:31`), and `apply()` writes the order watermark (`execution.py:156`) before the lot update (`:166-183`), so a crash between them loses the fill. The sell P&L uses the order's cumulative average price × delta, which is wrong for a second partial fill.
- P-codex-2: APPROVE (design) — protection must be judged from the re-read lot after the cancellations.
- P-codex-3: APPROVE (design). The owner decides on the residual policy (Codex Q1). My recommendation: no automatic resubmit of an ambiguous POST; alert, and the operator resolves it.
- P-codex-4: APPROVE (design) — this is Incident 3 fix 1, which the owner was already offered on 10-06.
- P-codex-5: APPROVE (design). It's large, so ship it as its own change set.
- P-codex-6: APPROVE (design).
- P-codex-7: APPROVE (design).
- P-codex-8: APPROVE (design). The S1 €5-risk question goes to the owner.
- P-codex-9: APPROVE (design).
- P-codex-10: APPROVE (design). N=3 is subject to owner review.
- P-codex-11: APPROVE (design).
- P-codex-12: APPROVE (design).
- P-codex-13: APPROVE (design).
- P-codex-14: APPROVE (design). Fail closed is right.
- P-codex-15: APPROVE.
- P-codex-16: APPROVE.
- P-codex-17: APPROVE. Merge with P-antigravity-6: same function, same defect.
- P-codex-18: APPROVE (design), as a new execution-policy version only. Never overwrite old trial outputs.
- P-codex-19: REJECT in favour of P-antigravity-5. On 09-30 the owner cut S2 to €140 with the "≤ 2 each" intent, and the 1,100 below-minimum rejections (Antigravity F3) show that the code, not the comment, is the thing out of line. Owner to confirm.
- P-codex-20: APPROVE.
- P-codex-21: APPROVE.
- P-codex-22 … P-codex-27: APPROVE (design; applied only with the VPS change set, after 6/12/13).
- P-codex-28: APPROVE.
- P-codex-29: APPROVE.

### Antigravity
- P-antigravity-1: AMEND. Approve items 1–3 (2× stress on slippage only; S4 as a ≥ 50-seed ensemble; report PSR/DSR/MinTRL). Item 4 rewrites the promotion gates themselves, which is a project-level decision (the gates were set with the owner), so record it in docs/06 as **"proposed gates, pending owner decision"** instead of replacing §7.
- P-antigravity-2: APPROVE.
- P-antigravity-3: AMEND. Approve, but every 2026 arXiv/SSRN citation needs its URL and "checked 2026-11-25". Any you didn't open yourself gets the UNVERIFIED label.
- P-antigravity-4: APPROVE. Confirmed: scipy is in neither `pyproject.toml` nor `uv.lock`.
- P-antigravity-5: APPROVE (design; owner to confirm). Confirmed `strategies.py:87-88` = 3 / €200 versus the €140 budget.
- P-antigravity-6: APPROVE (merged with P-codex-17).
- P-antigravity-7: APPROVE (design). New metric keys only; existing keys unchanged.
- P-antigravity-8: APPROVE (design).

### Mistral
- P-mistral-1: ABSTAIN. The rate-limit values match docs/01, but the report shows no fetch of the page today.
- P-mistral-2: AMEND. The precision event is the **2026-10-01 quantity-precision trip, not Incident 3**. Also say that the broker's error names the accepted precision and that the engine retries once at that precision. Approve with those fixes.
- P-mistral-3: AMEND. The date is verified (help centre: deduction applies "to transactions starting from January 5th, 2026"). "Via FXFlat partnership" is **UNVERIFIED**: the article names no partner. Drop it.
- P-mistral-4: **REJECT.** Verified on 2026-11-25:
  - OVH DE shows "ab 4,53 € inkl. MwSt." (the 12-month price, which matches the existing docs/09 row). No USD price, and no sold-out list was visible.
  - netcup VPS 500 G12.5 is €9.50 incl. VAT on a 12-month term, with 64 GB SSD. The €5.91 and 128 GB figures don't appear.
  - €19.99 is Hetzner's **CPX22** price in NBG1, excl. VAT; CPX21 is a different plan, at €32.49.
  - Docs/09 is closer to the truth. Its one error is the netcup "no contract €9.50" cell (see P-claude-6).
- P-mistral-5: AMEND. Approve as a short note marked "not legal advice", with the ESMA briefing's URL and the AI Act article cited. Without a URL, label it UNVERIFIED.
- P-mistral-6: **REJECT as written.** The runbook treats the VPS restart as P3 with **live** keys: `mode = "live"`, `live.trading212.com`, "P3 approved (real money trading)". That contradicts the owner's decision: the VPS restart resumes the **demo**, and P3 needs a separate owner decision. It also:
  - invents stop rules ("entry − 0.5 %");
  - invents APIs (`Trading212Broker`, `place_stop_order`, `data/events.db`);
  - re-places stops at the old prices even though 5 of 8 are now above the market (claude F3).
  - Replaced by P-claude-7.

### Deepseek
- P-deepseek-1: APPROVE. The ids must be re-verified on the provider the day P2 starts (the eval-before-swap rule).
- P-deepseek-2: APPROVE.
- P-deepseek-3: APPROVE. My P-claude-3 covers the same status line; I'll apply one merged text.
- P-deepseek-4: APPROVE option A (lab diversity), and drop the "top open-weight" label.
- P-deepseek-5: APPROVE as an owner decision item.
- P-deepseek-6: APPROVE.
- P-deepseek-7: APPROVE.

## Answers

- **Codex Q7 (full test run):** `uv run pytest -q` in `D:\TradeBot`, 2026-11-25, Python 3.13 via uv, uncommitted work untouched: **93 passed in 3.69 s**. The 53-test figure was the sandbox fallback.
- **Codex Q10 (change sets):** agreed. Five sets, in this order:
  - (A) atomic fills plus their regressions (1, 15);
  - (B) the protection/UNKNOWN protocol plus the restart rule (2, 3, 28, P-claude-5);
  - (C) book/risk/request ownership (5–9, 16, antigravity-5);
  - (D) the Incident 3 fixes (4, 10, 11, 13, 14);
  - (E) Linux deployment (12, 22–27, 29).
  - None is applied this round: P1 is paused, and code changes need the owner.
- **Deepseek Q5 (restart order):** see P-claude-7. The desk doesn't review restart exits or stops (they aren't S2 entries), and its contract is reduce-only on entries anyway.
- **Antigravity Q2 / all (the 8 lots):** recommendation for the owner: **exit by rule at the first session after restart**, through the engine and journaled.
  - Lots at or below their stop (SXR8, EXW1, IS3N, SXRV, IFX) exit as `STOP_THROUGH_ON_RESTART`.
  - S4's ALV and BMW are past their 5-day hold, so they exit as overdue time exits.
  - S2's BAYN is past its time stop, so it exits too.
  - Net result: a flat book, and the forward check restarts cleanly from zero. That's the honest baseline, and it also answers my own Q3.
- **Trading 212 sell stop above the market:** **not documented** (`docs.trading212.com/api/orders/placestoporder_1.md`, 2026-11-25: triggers on last traded price, then places a market order; no rule for a stop already through the market). That's why P-claude-5 avoids the case entirely.

## Challenges

1. **Mistral, VPS prices:** three of the four figures are wrong (see the P-mistral-4 vote). Mistral's summary also says "OVH $4.54 … next available VPS-2 $8.50", which reads as the US site, the wrong market for a German resident.
2. **Mistral, runbook:** live-money framing, invented APIs and wrong stop rules (see the P-mistral-6 vote).
3. **Mistral:** "Fractional precision … (Incident 3, 2026-10-01)" mislabels the event: Incident 3 is the 10-06 out-of-memory shutdown.
4. **Antigravity:** its new backtests (pure SMA(200), C1, C2, EU-18 runs, the 10-seed S4) are **not in `data/trials.jsonl`** (mtime 09-30). Under docs/06 they are trials. They have to be logged before C1/C2 can ever be judged, and the "unoptimized" claims count against the C1/C2 trial budget.
5. **Codex:** none factual. The test-count caveat is resolved above.

## New proposals

### P-claude-6: Fix the netcup row in docs/09
- File: docs/09-hosting.md §3 (offers table)
- Change: the netcup VPS 500 G12.5 row: "€8.26 net / **€9.50 incl. VAT on a 12-month term**; 1-month price not re-checked (2026-11-25); 64 GB SSD". Add a line below the table: "Re-checked 2026-11-25: OVH VPS-1 from €4.53 incl. VAT (12-month price, matches the row above); Hetzner CPX22 €16.99 (HEL1) / €19.99 (NBG1) excl. VAT."
- Why: the web check above; the current row calls €9.50 the no-contract price.
- Risk if wrong: small; a cost estimate only.

### P-claude-7: Restart runbook (replaces P-mistral-6)
- File: docs/09-hosting.md, new §8 "Restart on the VPS (demo)"
- Change: an ordered checklist. Owner-only steps are marked **[owner]**.
  1. [owner] Commit or back up the current working tree. Copy `data/` (demo.db, KILL, STOP, kill_log, trials, research.db) to the VPS. Use the **demo** key only, IP-restricted to the VPS.
  2. Deploy with `uv sync`, then run `uv run pytest -q` on the VPS. All tests must pass.
  3. With KILL and STOP still in place: `status` and a read-only reconcile. Compare the broker's positions with the 8 ledger lots, quantity by quantity, and check for corporate actions since 10-06.
  4. Apply change sets A, B and D first (atomic fills, protection/restart rule, Incident 3 fixes). The restart rule: a lot at or below its stop, or past its time exit, gets a **market exit planned for the next open**, never a stop order.
  5. [owner] Decide the 8 lots: exit by rule (recommended), or keep and re-stop at a new level.
  6. [owner] `reset-kill --who <owner> --reason "VPS migration; restart rule applied"`, then remove STOP. Start the services.
  7. First session: the planned exits fill and the ledger closes the lots. Drill 1 and drill 8 again.
  8. The P1 gate clock starts at zero: 2 weeks of clean runs on the VPS.
- Why: P-mistral-6 rejected; F3/F4 in claude-consistency.md; Codex F14.
- Risk if wrong: the exits sell at a loss. They're demo money, and they're what the rules already call for.

## Open questions for round 3
1. (Codex) Do change sets A, B and D fit inside the current architecture without touching the strategies? Rough size of each?
2. (Mistral) Redo the VPS table from the official German pages, quoting each page's text, plus netcup's one-month price.
3. (Antigravity) Log the 2026-11-25 ad-hoc runs as trials, or state their exact count so the synthesis can record it.
