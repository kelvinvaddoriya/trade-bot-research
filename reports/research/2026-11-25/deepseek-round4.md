# Deepseek (OpenCode) — Round 4: verification + carried votes (2026-11-25)

Read Agent-Guide.md Parts 2–5 and applied the binding rules (no orders, no data/STOP or data/KILL, no git writes). Verified the applied doc edits against the round-3 final texts (claude/deepseek/antigravity/mistral) and, for P-codex-20/21, against Codex's round-1 change description plus the actual source (`cli.py`, `strategies.py`, `models.py`, `store.py`, `config/risk.toml`, `config/settings.toml`). Ignored the older uncommitted docs/09 and docs/10 diffs per the brief.

## Verification

| Edit | Proposal | Verdict |
|---|---|---|
| README.md status line | P-claude-1 | OK |
| README.md D5 row append | P-claude-2 | OK |
| docs/01 §4.1 precision bullet | P-mistral-2 | OK |
| docs/02 §2 rule-based − bullet | P-antigravity-3 | OK |
| docs/02 References additions (6 citations) | P-antigravity-3 | OK |
| docs/03 S1 stop-fraction note | P-antigravity-2 | OK |
| docs/03 S2 €140/18-stock status | P-antigravity-2 | OK |
| docs/03 S3 universe note | P-antigravity-2 | OK |
| docs/03 S4 ensemble note | P-antigravity-2 | OK |
| docs/03 §4 portfolio construction | P-antigravity-2 | OK |
| docs/04 §3 sessions paragraph | P-codex-20 | OK (matches settings.toml:8 order S1→S2→S3→S4; audit link correct) |
| docs/04 Decimal→float/REAL | P-codex-20 | OK (matches models.py:3, store.py:15–20) |
| docs/04 CLI `stop [--until]` row | P-codex-20 (§9) | OK (cli.py:194–212,353 has `--until`; accurate though not spelled out in P-codex-20's terse text) |
| docs/04 restart recovery design | P-claude-5 | OK |
| docs/05 §2 max positions 12 | P-codex-21 | OK (strategies.py:33/87/139/178 → S1≤6, S2≤3, S3≤2, S4≤2) |
| docs/05 §2 max orders 20 | P-codex-21 | OK (risk.toml max_orders_per_day=20) |
| docs/05 §2 implementation-gaps note | P-codex-21 | OK (minute-limiter/S1-€5/session-end/P3 gates all in F8/F13; F9 stale-data gap not explicitly restated — minor) |
| docs/05 §4 planned shutdown | P-claude-4 | OK |
| docs/05 §4 reset-kill note | P-codex-21 | OK (cli.py:267–285 displays last RECONCILE, does not run one) |
| docs/05 §6 sync status note | P-codex-21 | OK |
| docs/05 §8 injection test set | P-deepseek-6 | OK |
| docs/06 §2.3 FX note | P-antigravity-1 | OK |
| docs/06 §2.5 S4 ≥50-seed | P-antigravity-1 | OK |
| docs/06 §4 PSR/DSR/MinTRL | P-antigravity-1 | OK |
| docs/06 §7 proposed gate items | P-antigravity-1 | OK |
| docs/07 P2 duration cell | P-deepseek-3 | OK |
| docs/07 P2-duration note | P-deepseek-3 | OK (trailing "status line updated under P-claude-3" meta-sentence correctly dropped) |
| docs/07 status line | P-claude-3 | OK |
| docs/08 Opus/GLM/Kimi ranking rows | P-deepseek-1 | OK |
| docs/08 §2 juror 4/5 rows | P-deepseek-4 | OK |
| docs/08 §2 owner decision | P-deepseek-5 | OK |
| docs/08 §5 ZDR fail-closed + re-check | P-deepseek-7 | OK |
| docs/08 §6 reasoning-cost note | P-deepseek-2 | OK |
| docs/3paperresearch.md §3.2 | P-antigravity-4 | OK |

Notes on links / markdown:
- The link `reports/research/2026-11-25/00-synthesis.md` in README.md and docs/07-roadmap.md (from P-claude-1/P-claude-3) is currently **dangling** — `00-synthesis.md` does not exist yet. It is faithful to the passed final text; the orchestrator must write the synthesis to complete the link.
- docs/3paperresearch.md's `[backtest.py:179](src/tradebot/backtest.py:179)` is a code reference rendered as a link that resolves relative to `docs/` (should be `../src/…`). Faithful to P-antigravity-4's exact final text, so not flagged as a MISMATCH, but the link target is technically wrong.
- No broken tables/lists introduced; S3/S4 subsections and the replaced §4 bullet list render correctly.

## Votes

- P-claude-6: AMEND (fix the netcup term attribution) — Mistral's round-3 answer, quoting the netcup.de page, gives €9.50/mo incl. VAT as the **no-contract** price and €8.26/mo as the 12-month price, which inverts P-claude-6's "€9.50 on a 12-month term"; the "€8.26 net / €9.50 … 12-month" phrasing is internally garbled and needs a dated primary-source re-check before applying.
- P-claude-7: APPROVE — the runbook is demo-only, owner-gated, keeps KILL tripped through recovery, plans market (not stop) exits for breached/overdue lots, and its commands (`uv sync`, `uv run pytest -q`, `reset-kill --who --reason`) match the actual CLI (cli.py:267–285, 363–364) and F14 restart preconditions.
- P-antigravity-9: APPROVE — the shared-book-replay vs independent-sleeve-baseline split correctly encodes the F12/P-codex-17/P-antigravity-6 merged design (activation epochs, exit-before-entry, `taken` reservations, COLLISION/operator_event tags, clean-start-after-outage), so the forward check stops overstating backtest parity.
- P-codex-30: APPROVE — an immutable snapshot + manifest-ID provenance contract and late (never "prospective") registration of the 42 unlogged 2026-11-25 ad-hoc runs directly closes the trial-provenance gap Antigravity Q3(c)/Challenges exposed, and it is correctly scoped as a docs-only edit with implementation deferred to separate source proposals.

## Omission response

ACCEPT — the omitted sentence was a proposal-to-proposal cross-reference, not documentation, and docs/07 needs no mention of which proposal updated its status line.
