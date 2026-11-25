# Claude — round 3: amendment responses and final texts (2026-11-25)

## Amendment responses

| Proposal | From | Amendment | Response |
|---|---|---|---|
| P-claude-1 | Codex | "third laptop incident" instead of "third out-of-memory incident"; the ledger lots aren't a broker observation, and a fresh broker inventory is needed | **ACCEPT.** Incident 2 (09-29) was a freeze and reboot, not a proven OOM. Correct. |
| P-claude-3 | Codex, Antigravity | docs/07 only (one file per proposal); merge the status wording with P-deepseek-3; docs/10 "What happens next" goes in a separate edit | **ACCEPT.** docs/10 is handled by the orchestrator's build-log entry, which is its own file and the lock holder's job (Part 3.4). |
| P-claude-4 | Codex | Policy wording: keep confirmed GTC stops, or an authorized flatten with verified fills; reconcile before resuming. Drop the €55 figure and the unconditional "the reconciler books it" | **ACCEPT.** The €55 comes from Yahoo prices, not the broker, and Codex F2/F3 show recovery isn't guaranteed. The figure stays in the research report, not in the risk doc. |
| P-claude-5 | Codex | Label it a proposed design; fresh inventory, quote/session checks, remaining quantity, an owner-approved per-lot disposition; overdue time exits separate; don't reset KILL just to allow exits | **ACCEPT** |
| P-claude-5 | Antigravity | Say how this interacts with KILL: `execution.py:307-309` skips non-flatten exits while tripped, so the exits need operator confirmation or a kill-exempt flag | **ACCEPT.** Merged with Codex's wording: the exits go through the existing operator FLATTEN path (`kill --flatten`), which `execution.py:307` already lets through, so no new bypass is needed. |

P-claude-6 and P-claude-7 were filed in round 2 and have no votes yet. They're **carried to the next round** and not applied.

## Final texts

### P-claude-1: README.md
Replace the line that starts with `> **Status (2026-09-27):** **P1 built**` with:

> **Status (2026-11-25): paused since 2026-10-06** until the engine moves to a rented EU server. P1 ran on the Trading 212 demo from 2026-09-28 to 10-06 with four strategies: S1 trend (6 UCITS ETFs), plus S2 pullback, S3 breakout and S4 random control as demo-only experiments on 18 German stocks. It stopped after the third laptop incident in 9 days. The local ledger still holds 8 open demo lots, and Incident 3 records that all their stops were cancelled on 2026-10-06. A fresh broker inventory is needed before any restart. 93 tests pass. The P1 gate (2 weeks of clean runs) was never completed and restarts from zero on the server. Details: [build log](docs/10-build-log.md), [research round 2026-11-25](reports/research/2026-11-25/00-synthesis.md).

### P-claude-2: README.md
In the Key decisions table, row D5, append to the Decision cell:

> Since 2026-09-30, on demo only: S2, S3 (Donchian 20/10) and S4 (random entries, the control group) trade 18 German large caps as experiments. None can go live without passing every gate.

### P-claude-3: docs/07-roadmap.md
Replace the line that starts with `**Status (2026-09-27): P1 built; the 2-week demo run starts` with (merged with P-deepseek-3's status part):

> **Status (2026-11-25): P0 done; P1 built but paused, not passed; P2 not started.** The demo engine ran 2026-09-28 → 10-06. The 2-week clean-run gate was never completed: there were three laptop incidents in 9 days ([10](10-build-log.md#incident-3-out-of-memory-again-kill-switch-trip-and-shutdown-until-the-server-2026-10-06)). The engine has been shut down since 2026-10-06. Next: the EU server ([09 §3](09-hosting.md#3-a-small-eu-vps)), the recovery fixes from the [2026-11-25 research round](../reports/research/2026-11-25/00-synthesis.md), then the P1 gate again from zero. No LLM desk code exists yet.

### P-claude-4: docs/05-risk-and-safety.md
After the line `**FLATTEN** (manual option \`--flatten\`) also closes every position at market.`, insert:

> **Planned shutdown** (engine off for more than a day). Either keep a confirmed broker-held GTC protective stop on every open position, or run an authorized FLATTEN and verify its fills before shutting down. Never cancel all protection while keeping the positions: broker-held stops work without the engine. Before resuming, reconcile broker fills and remaining quantities against the ledger. The recovery gaps found in the [2026-11-25 code audit](../reports/research/2026-11-25/codex-code-audit.md) must be fixed first. *(Added 2026-11-25 after Incident 3, when all stops were cancelled for the shutdown and the positions stayed open.)*

### P-claude-5: docs/04-architecture.md
After the CLI table row that starts with `| \`kill --flatten --reason "..."\``, insert this paragraph after the table:

> **Restart after a long pause: proposed recovery design, not implemented (2026-11-25).** Today, `ensure_stops()` re-places each lot's stop at its stored price and doesn't compare it with the market. The proposed design:
> 1. With KILL still tripped, take a fresh broker inventory (positions, open orders, corporate actions) and reconcile the remaining quantity of every lot.
> 2. The owner decides each lot. For a lot whose stop is already breached, the engine journals `STOP_THROUGH_ON_RESTART` and the exit runs through the existing `kill --flatten` path, which is allowed while KILL is tripped. An overdue time exit (S2's time stop, S4's 5-day hold) is a separate, explicit decision.
> 3. A lot that is kept gets a confirmed protective stop before anything else happens.
> 4. KILL is reset only after that, and never just to let the recovery exits through.

## Withdrawn
None.

## Answers
- Round-3 questions to me: none.
