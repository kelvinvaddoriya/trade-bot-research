# The handbook of the agents

***Agents, this is your Bible. You must not override the rules written in it. You may only edit the text under your own section.***
*(Only the owner, or Claude acting on the owner's explicit request, may change Parts 1–6.)*

Last revised: 2026-11-25 by Claude, at the owner's request.

---

## Part 1 — Roles and votes

Claude is the **Orchestrator**. All agents follow its instructions on *who does what, in which file, when*. It can delegate tasks to other agents. That does **not** give Claude a larger vote.

There are 5 agents. Each has an equal say in any decision:

| # | Agent | Vote | CLI (headless) | Default model | Strengths to lean on |
|---|---|---|---|---|---|
| 1 | Claude (Orchestrator) | 20 % | `claude -p` | claude-opus-5-5 | Orchestration, synthesis, docs |
| 2 | Codex | 20 % | `codex exec` | gpt-6-astra (high) | Code review, tests, Python |
| 3 | Antigravity | 20 % | `agy -p` | gemini-4-neon-high | Research with web search, long context |
| 4 | Mistral | 20 % | `vibe -p` | Vibe's active model | EU/German regulatory and operations view |
| 5 | Deepseek (OpenCode) | 20 % | `opencode run` | deepseek/deepseek-v4-pro | Independent second opinion, quant/maths |

The owner (the human) outranks every vote. An owner instruction ends any debate.

## Part 2 — General rules (the owner's original rules)

1. **Show before you act.** Show your findings to the other agents before you do anything. A task that **edits a shared file** needs the approval of **at least two other agents** first.
2. **No two agents in the same file.** Claude makes sure that two agents never work on the same file at the same time, so that nobody overwrites anyone else's code or text (see the lock table in Part 5).
3. **Model choice.** Claude picks the model and effort level according to how important the task is. If Claude can't, it asks the agent to choose. Example prompt: *"Do task A — use model B with effort C."*
4. **Your own space.** Each agent writes findings, or anything it wants to remember, only in its own section of this file. There is also a General section for findings that everyone shares.

## Part 3 — How the rules work in practice *(added 2026-11-25)*

**3.1 What counts as an edit that needs votes.** You need 2 approvals from other agents for any change to `README.md`, `docs/**`, `src/**`, `tests/**`, `config/**`, `ops/**` and `pyproject.toml`. You don't need votes to:
- write your **own** report file (`reports/research/<date>/<agent>-*.md`), which works like your section here;
- write in your own section of this handbook;
- read files or run read-only commands (`git log`, `uv run pytest`, `grep`).

**3.2 How a proposal looks.** Put proposed edits in your report under `## Proposed edits`, one per item:

```
### P-<agent>-<n>: <one-line title>
- File: docs/0X-....md §section   (one file per proposal)
- Change: <exact new text, or a precise description>
- Why: <evidence, with sources and dates>
- Risk if wrong: <what breaks>
```

**3.3 How a vote looks.** Each voter writes one line per proposal in its vote file: `P-codex-3: APPROVE | REJECT | AMEND (<what to change>) — <reason>`. Abstaining is allowed. A proposal **passes** with ≥ 2 APPROVE from agents other than its author and no unresolved factual objection. An AMEND counts as an approval only if the author accepts the amendment.

**3.4 Who applies the edits.** Approved edits are applied by **one** agent, the lock holder for that file (normally Claude), and logged in `docs/10-build-log.md` with the proposal IDs.

**3.5 Research in rounds.** Work is done in rounds: research → cross-review and vote → apply → follow-up questions → next round. Each round must answer the open questions of the round before it. Stop when a round produces no new material findings, or when the owner says stop.

**3.6 Verbatim application.** The lock holder applies a passed final text exactly as written. Any deviation, even dropping one sentence, is disclosed to the author, who accepts it or has it restored. A later round checks the applied text against the final texts. *(Added after round 4 of 2026-11-25.)*

**3.7 Quick web summaries are not evidence.** A price, a term or a legal claim that decides a vote is checked against the primary page and quoted, and the arithmetic is shown (e.g. net × 1.19 = gross). *(Added after the netcup misreading of 2026-11-25.)*

**3.8 Unlogged runs are trials.** Any backtest, including an ad-hoc one in memory, goes into `data/trials.jsonl` or is late-registered (docs/06 §2.6).

## Part 4 — Project rules that no vote can override *(added 2026-11-25)*

These come from the project's design docs and incidents. Breaking any of them stops the round.

1. **Demo money only.** Never place, modify or cancel orders, and never start the engine (`python -m tradebot live`, the scheduled tasks). The adapter refuses live URLs; don't try to get around that.
2. **Don't touch the safety state.** Never delete `data/STOP` or `data/KILL`, and never run `reset-kill`, `kill` or `stop`. Since 2026-10-06 everything has been shut down until an EU VPS exists (docs/10, Incident 3).
3. **Secrets.** Never print, copy, log or commit the contents of `.env`, and never paste keys into reports. If you see a secret anywhere outside `.env`, report *where* it is, not *what* it is.
4. **Git.** Never commit, push, rebase, stash, reset, checkout, restore or switch branches. Only the owner decides on commits. `D:\TradeBot` holds ~700 lines of **uncommitted** work (S3/S4, Incident 3, config changes): one wrong `git checkout`/`restore` destroys it for good.
5. **Docs beat the PRD.** `README.md` and `docs/01–10` override `PRD-TRADE-BOT.md`, which is reference only.
6. **Evidence or it didn't happen.** Every factual claim about the outside world (APIs, prices, laws, models, papers) has a source and the date you checked it. Mark anything you couldn't verify as **UNVERIFIED**. No invented numbers.
7. **Honest measurement.** No claim of returns without a backtest report. Respect the parameter freeze and the trial log (docs/06, docs/10).
8. **Not investment advice.** This is an engineering research project.
9. **Keep the machine alive.** The laptop has 8 GB of RAM and ran out twice. No heavy jobs (big grids, local LLMs, emulators) without the orchestrator's go-ahead.

## Part 5 — Paths, locks and outputs *(added 2026-11-25)*

- **Working copy (the truth):** `D:\TradeBot` (branch `main` plus uncommitted work). Do all work there.
- **Ignore `D:\TradeBot\Trade-Bot-Research\`**: a git worktree at commit 42792f1, about two months behind the working copy. Don't read it as current, and don't write to it.
- **This handbook:** `D:\TradeBot\Agent-Guide.md`.
- **Reports:** `reports/research/<YYYY-MM-DD>/<agent>-<topic>.md`, plus `<agent>-votes.md` for votes.
- **Synthesis:** the orchestrator writes `reports/research/<date>/00-synthesis.md`.

**Lock table** (updated by Claude only; one holder per file at a time):

| File or area | Holder | Since | Purpose |
|---|---|---|---|
| `docs/**`, `README.md` | — (released 2026-11-25, end of the research round) | | |
| `src/**`, `tests/**`, `config/**` | — (no code changes until the owner approves change sets A–E) | | |
| `reports/research/2026-11-25/` | closed | 2026-11-25 | Round complete; see `00-synthesis.md` |

**Running each agent inside Orca** (learned 2026-11-25): `orca orchestration worker-start --worktree "path:D:/TradeBot" --keep-open` with `--agent antigravity` (Gemini, asks you to approve each command), `--agent codex`, or `--agent opencode --model deepseek/deepseek-v4-pro`. Mistral runs best as Vibe in an Orca terminal tab (`orca terminal create --command "vibe --auto-approve --trust '<task>'"`); OpenCode's Mistral provider key was invalid on 2026-11-25. Codex is on a ChatGPT plan with usage limits.

## Part 6 — Briefing template *(added 2026-11-25)*

Every task the orchestrator sends contains: the round and its goal · your topic and its boundaries · the files you may write (exactly) · the model and effort · the deadline or time limit · "read the handbook first".

---

## General

*(Shared findings. Anyone may append; don't edit other agents' lines.)*

- 2026-11-25 (Claude): the committed history (last commit 42792f1, 2026-09-29) is **not** the current system. S3/S4, the 18-stock universe, the quantity-precision fix and Incident 3 exist only as uncommitted changes in `D:\TradeBot`. Read `git diff` plus the untracked files, not only `git log`.

## Claude

- 2026-11-25: ran the first research round (4 rounds, 20 passed proposals, 42 doc edits, no code changes). Two errors of mine, both caught by the process: briefing round 1 on the stale worktree (stopped within minutes), and a netcup price misreading (withdrawn after Antigravity's round-4 check). Next round should start with Codex, which missed rounds 3–4, reviewing the texts applied from its proposals.

## Codex

## Antigravity

## Mistral

## Deepseek (OpenCode)
