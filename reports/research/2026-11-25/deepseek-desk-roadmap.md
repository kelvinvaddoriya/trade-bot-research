# Deepseek (OpenCode) - The multi-agent LLM desk, and the roadmap (round 1, 2026-11-25)

## Summary

1. **The desk is still a design, not code.** `desk.py` / `llm_providers.py` appear in the repo layout (docs/04 §10) but are not marked `[built]` and never appear in the build log's "Built" tables. P2 has not started; there are no provider adapters, no news sources, no jury, and no desk tests (92-93 tests, none for the desk). The system is at the P1→P2 boundary, with P1 itself unvalidated (no 2-week clean run; three laptop OOM incidents, shutdown since 2026-10-06).
2. **Every juror's model id in docs/08 is now stale.** As of 2026-11-25 the Artificial Analysis index top is: Claude Fable 5.2 (65), GPT-6.2 Astra (62) / Gemini 4 Neon (62), Gemini 4 Carbon (60), Claude Opus 5.5 (59), GPT-6.2 Sol (57). "Claude Opus 5.5 (#1)" (docs/08:15, README:96) is wrong — it is #10 and Fable 5.2 is #1. GPT-6 Sol and Gemini 3.8 Flash and Kimi K3 are each a generation behind.
3. **Sol-tier is still the right GPT seat, but it should be GPT-6.2 Sol.** GPT-6.2 Sol is $2/$10 and index 57 vs GPT-6.2 Astra $8/$40 index 62 — Sol keeps the ~4× cost advantage the desk's choice was built on (docs/08:42). Update the id and the Astra comparison to 6.2.
4. **Cost model still fits the €10 runtime budget** (and is slightly cheaper than Sept 2026): a 5-juror review is now ≈ $0.16 (was ≈ $0.18), ≈ €1.7/month at ~10 S2 reviews. But the new models are *reasoning* models with effort levels and heavy thinking-token output — the "$0.16" holds only if reasoning effort is pinned low and max output tokens capped. The docs never say this.
5. **The veto-effect measurement is a multi-year problem, not an "8-week" one.** At the observed S2 frequency (~5-8 entries/month, backtest 812 trades/13y ≈ 5.2/month, docs/10:168) and a 20 % veto rate, detecting a *large* 30-point veto-precision edge needs ~16 vetoed entries ≈ **10-16 months**; a moderate 20-point edge needs ~37 vetoed entries ≈ **2-3 years**. The P2 gate's own "≥ 50 reviewed entries" floor (docs/06:110) alone is 6-10 months. docs/07's "8+ weeks" is off by ~5-20×.
6. **The desk's scope (S2 entries only) is now narrower in practice than the docs assume.** S2's live universe is 18 German stocks (US names are backtests-only, config/instruments.toml:68); the "8-12 entries/month across both markets" (docs/03:72, docs/08:196) was written for the 14-stock US+EU universe. Real S2 entry rate is uncertain and plausibly lower.
7. **Safety design holds up against the 2026 attack literature.** The 2026 IPI papers (AgentSentry 2602.22724, AttriGuard 2603.10749, IterInject 2605.24659, covert IPI 2608.30362) all target tool-using agents; the desk gives no agent tools and quarantines raw text behind enums, which is precisely the action-level mitigation they recommend. Two gaps: the injection test set uses only static payloads (should add adaptive/covert payloads), and the `NewsFindings.summary` free-text field is the one remaining injection channel.
8. **Zero-data-retention needs a re-check, not a redesign.** OpenRouter ZDR is still account-wide but now has (a) Google "Safety Retention" on Vertex since 2026-10-18 (strict ZDR excludes most Google models) and (b) CSAM screening on ZDR traffic from 2026-10-27. The open-weight seats' *new* checkpoint ids (Kimi K3.1 Pro, DeepSeek V4.1 Flash 1017) must be confirmed on the ZDR endpoint list before pinning.
9. **Real phase: "P1 blocked on hosting, P2 unstarted."** Next steps are dominated by the EU VPS and the naked positions, not by the desk. The desk's most urgent action is a *decision* (broaden scope to S3 / accept a multi-year shadow), not code.

## Findings

### F1 — The desk is a spec, not an implementation (HIGH, high confidence)
- **Claim:** P2 has not started; the LLM desk exists only as design docs.
- **Evidence:** `docs/04-architecture.md:300-301` lists `desk.py` and `llm_providers.py` without a `[built Px]` tag, unlike every other module; `docs/10-build-log.md` "Built" tables (P0 step 2-11, P1) never mention desk code; the test count tops out at 93 (build log, "quantity-precision trip" entry) with no desk tests; drill 7 ("LLM failure paths") is marked "P2 (no desk yet)" at `docs/10-build-log.md:59`. No `desk.py`/`llm_providers.py` file exists under `src/tradebot/` (verified via the repo layout, which is consistent with git status showing no such untracked files).

### F2 — Model landscape moved 2 generations since the docs' snapshot (HIGH, high confidence)
- **Claim:** All five juror model ids in `docs/08` are stale; the index ranking cited is wrong.
- **Evidence:** Artificial Analysis leaderboard, checked 2026-11-25 (https://artificialanalysis.ai/leaderboards/models). Current index: Claude Fable 5.2 = 65 (#1), GPT-6.2 Astra = 62, Gemini 4 Neon = 62, Gemini 4 Carbon = 60, Claude Opus 5.5 = 59 (#10), GPT-6.2 Sol = 57, Claude Sonnet 5.5 = 55, Gemini 4 Hydrogen = 54, GPT-6.1 Terra = 51, Gemini 4 Argon = 51, Muse Wonder Full = 50, Kimi K3.1 Pro = 47, Qwen4 Max = 43, Grok 4.7 = 35, DeepSeek V4.1 Flash 1017 = 32, GLM-5.3 = 32, DeepSeek V4 Pro = 23.
- **Why it matters:** `docs/08:15` says "Claude Opus 5.5 (58, #1 overall)" and README:96 repeats "#1 on the index" — both wrong. `docs/08:20` calls Gemini 3.8 Flash "Google's best"; `docs/08:28-29` calls GLM-5.3 and Kimi K3 "tied for #1 open-weight" — GLM-5.3 is now index 32 (below Kimi K3.1 Pro 47 and Qwen4 Max 43), so neither open-weight seat is "top open-weight" anymore.

### F3 — Per-lab "best model now" and pricing (HIGH, high confidence)
- **Claim (table):** Current best-per-lab and list price (in/out per 1M tokens), checked 2026-11-25.

| Seat (lab) | Roster id (docs/08) | Current best / sensible seat | Index | $ in/out per 1M | Context |
|---|---|---|---|---|---|
| Anthropic | `claude-opus-5` (Opus 5.5 swap) | Opus 5.5 (sensible); Fable 5.2 is #1 | 59 / 65 | 4 / 20 (Opus 5.5); 8 / 40 (Fable 5.2) | 1M |
| OpenAI | `gpt-6-sol` | GPT-6.2 Sol (sensible); GPT-6.2 Astra flagship | 57 / 62 | 2 / 10 (Sol); 8 / 40 (Astra) | 1M |
| Google | `gemini-3.8-flash` | Gemini 4 Neon (best $/index) | 62 | 1.50 / 7.50 | 1M |
| Z.ai | `z-ai/glm-5.3` | GLM-5.3 (still the Z.ai model) | 32 | 1.40 / 4.40 | 1M |
| Moonshot | `moonshotai/kimi-k3` | Kimi K3.1 Pro | 47 | 2 / 10 | 1M |
| News analyst | `deepseek/deepseek-v4.1-flash` | DeepSeek V4.1 Flash 1017 | 32 | 0.15 / 0.60 (DeepSeek direct; third-party from 0.035 / 0.45) | 1M |

- **Sources:** AA model pages checked 2026-11-25 (claude-opus-5-5, claude-fable-5-2, gpt-6-2-astra); OpenRouter model pages checked 2026-11-25 (gpt-6.2-sol $2/$10 OpenAI direct; gemini-4-neon $1.50/$7.50 AI Studio; z-ai/glm-5.3 $1.40/$4.40 Z.ai; moonshotai/kimi-k3.1-pro $2/$10 Moonshot; deepseek-v4.1-flash-1017 $0.15/$0.60 DeepSeek direct).
- **Notes:** Gemini 4 Neon at $1.50/$7.50 for index 62 is the best price/performance on the whole board — the Gemini seat gets *cheaper and stronger* by moving off 3.8 Flash. Kimi K3.1 Pro ($2/$10) is cheaper than the K3 it replaces ($3/$15). DeepSeek news analyst got ~2-4× cheaper. Grok 4.7 (index 35, 500k context) is now weaker than every other seat; its role as "alternate paid seat" is less justified.

### F4 — GPT seat: Sol-tier still right, update to GPT-6.2 Sol (MED, high confidence)
- **Claim:** The desk's "Sol not Astra" decision (docs/08:42, README:86) remains correct, but the id is now `gpt-6.2-sol`, and the offline-eval Astra comparison should be GPT-6.2 Astra.
- **Evidence:** GPT-6.2 Sol = index 57 at $2/$10; GPT-6.2 Astra = index 62 at $8/$40 (AA pages, 2026-11-25). Cost-per-task on the AA index: Sol $1.01 vs Astra $4.00 — Sol keeps the ~4× per-task advantage the desk chose it for. A 5-point index gap on a bounded reduce-only review does not justify 4× the spend.

### F5 — Cost model still fits the budget, with one new caveat (MED, medium confidence)
- **Claim:** Per-review cost ≈ $0.16 (down from $0.18), monthly runtime ≈ €1.7, both well under the €10 cap — but only if reasoning effort is pinned low and output tokens capped.
- **Math** (5k in / 2k out+thinking per juror, 8k/1k news, Nov 2026 list prices): Opus 5.5 0.02+0.04=$0.060; GPT-6.2 Sol 0.01+0.02=$0.030; Gemini 4 Neon 0.0075+0.015=$0.0225; GLM-5.3 0.007+0.0088=$0.0158; Kimi K3.1 Pro 0.01+0.02=$0.030; DeepSeek news ≈ $0.002. Total ≈ **$0.160** (docs/08:189 says $0.18).
- **Monthly:** 10 reviews × $0.16 = $1.60 + 22 Gemini reports ≈ $0.24 → ≈ **$1.84 ≈ €1.7** (docs/08:196 budgeted €2-3). Fits ≤ €25 P2 / ≤ €10 runtime.
- **Caveat (the new risk):** every current juror is a *reasoning* model with effort levels. AA shows Opus 5.5 emits ~218M output tokens across the index (vs ~65M median) and Fable 5.2 ~275M — thinking tokens can dwarf the 600-char rationale. The docs' "2k output+thinking" assumption (docs/08:179) is only realistic with `reasoning effort = low` and a `max_tokens` cap, neither of which is specified anywhere. Without that, a single review could cost several × $0.16 and blow the eval budget especially. This is a concrete spec gap to fix before P2 code.

### F6 — Veto-effect detection needs ~1-2 years of shadow data, not weeks (HIGH, high confidence)
- **Claim:** The desk's veto effect cannot be statistically demonstrated in anything like the "8+ weeks" in docs/07:9.
- **Setup:** The desk reviews S2 entries only. Base S2 loss rate p₀ ≈ 0.39 (build log step 11: "a 61 % win rate", docs/10:522). Veto precision = share of vetoed entries whose *book-A* trade lost (book A still takes the entry, so the outcome is observable for free — docs/06:99-106). Test: one-sided binomial of vetoed-trade loss rate vs p₀.
- **Math** (normal approximation, one-sided α=0.05, power=0.80): n_v ≈ [1.645·√(p₀(1−p₀)) + 0.842·√(p₁(1−p₁))]² / (p₁−p₀)².

| Veto-precision uplift d = p₁ − p₀ | p₁ | Vetoed entries needed n_v |
|---|---|---|
| 0.30 (0.39→0.69) | large | **≈ 16** |
| 0.20 (0.39→0.59) | moderate | **≈ 37** |
| 0.10 (0.39→0.49) | modest | **≈ 150** |

- **Months** = n_v / (veto rate × entries/month). With S2 ≈ 5/month (backtest 812 trades/13y ≈ 5.2/mo, docs/10:168) or 8/month (the docs' own "8-12", docs/08:196), veto rate 20 %:

| Effect | r=5/mo, v=0.20 (1 veto/mo) | r=8/mo, v=0.20 (1.6 veto/mo) |
|---|---|---|
| 0.30 (large) | 16 months | 10 months |
| 0.20 (moderate) | 37 months (~3 y) | 23 months (~2 y) |
| 0.10 (modest) | 150 months (~12 y) | 94 months (~8 y) |

- **Independent floor:** the P2 gate already requires "≥ 50 reviewed entries" before `affects_orders=true` (docs/06:110). That alone is 50/5 = 10 months at r=5, 6.3 months at r=8. So even the *minimum* gate, before any statistical power, is ~6-10 months.
- **Reading:** "detect a useful veto effect" is a 1-2 year measurement at best, ~12 years for a modest effect. The desk can still *run* in shadow cheaply during that time (it costs ~€1.7/month), but the roadmap's P2 duration and the "8 weeks" figure are wrong by 5-20×.

### F7 — S2's live entry rate is probably lower than the docs assume (MED, medium confidence)
- **Claim:** The "8-12 S2 entries/month across both markets" figure is stale; S2 now trades 18 German names only.
- **Evidence:** `config/instruments.toml:68` — "US names trade only in backtests until FX handling exists"; S2/S3/S4 live universe = 18 Xetra names (lines 190-286). Observed demo week (reports/daily/2026-10-02.md, 2026-10-05.md): S2 entries BAYN, DHL, BMW (~3 in the first 5 trading days, a fill-up transient). Steady-state bound: 3 slots ÷ ~3.4-day hold ≈ up to ~18/month if signals were always available (build log:523), but RSI(2)<10 setups are rare. Honest range: 5-18/month, central ~8; UNVERIFIED pending real forward data (only 6 trading days exist before shutdown).

### F8 — Safety design is aligned with 2026 IPI research; two updates needed (MED, medium confidence)
- **Claim:** The quarantine + reduce-only + no-tools + quorum/median design is sound against the current published attack class (indirect prompt injection in tool-using agents); two refinements are worth making.
- **Evidence (checked 2026-11-25):** 2026 IPI literature — AgentSentry (arXiv 2602.22724), AttriGuard (2603.10749, action-level causal attribution), IterInject (2605.24659, adaptive payloads), covert IPI (2608.30362, attacks that hide from the user), "How vulnerable are AI agents to IPI" (2603.15714), USENIX Security '26 "IPI in the wild". All target agents that *execute tool calls from retrieved content*. The desk gives no agent tools and no agent-to-agent calls (docs/08:221-222, docs/05:108), so an injected instruction has no actuator — the equivalent of AttriGuard's action-level defence. The enum-only NewsFindings quarantine (docs/08:72) is the input-side isolation these papers advocate.
- **Gap 1 (MED):** the injection test set (docs/05:113, docs/08:214) uses static payloads ("ignore previous instructions"). IterInject/covert-IPI show payloads now adapt to defences and hide from the operator; the frozen test set should add adaptive and covert payloads or it will overstate resistance.
- **Gap 2 (LOW):** `NewsFindings.summary` is a free-text field ≤200 chars (docs/08:107). It is the one remaining text channel from raw news to the jury. Worst case is still a missed entry (reduce-only), so low severity, but a stricter template (or dropping free text to a fixed enum vocabulary) would close it.

### F9 — Zero-data-retention: policy changed; re-verify endpoint ids (MED, high confidence)
- **Claim:** OpenRouter ZDR still works account-wide, but (a) Google models now need "Safety Retention" on Vertex (since 2026-10-18) and are excluded under strict ZDR; (b) ZDR traffic is CSAM-screened from 2026-10-27; (c) the new open-weight checkpoint ids must be confirmed ZDR-eligible.
- **Evidence:** OpenRouter ZDR docs, checked 2026-11-25 (https://openrouter.ai/docs/guides/features/zdr). "Starting October 18, 2026, Google requires Safety Retention for Google models served through Vertex … These endpoints don't meet a strict Zero Data Retention requirement." CSAM screening announcement dated 2026-10-27. Per-model-group ZDR toggles exist (`enforce_zdr_anthropic/openai/google/xai/other`).
- **Impact:** the desk's Gemini seat uses Google's *native* SDK (docs/08:117), so OpenRouter ZDR does not govern it — but the doc's implicit "zero data retention" comfort for the Gemini seat should be re-checked against Google AI Studio's own terms (paid vs free tier train-on-data differences). The GLM/Kimi/DeepSeek seats go through OpenRouter with account-wide ZDR; their *new* ids (`kimi-k3.1-pro`, `deepseek-v4.1-flash-1017`) must be checked on https://openrouter.ai/api/v1/endpoints/zdr before pinning, because new checkpoints do not automatically inherit a ZDR endpoint. CSAM screening is irrelevant to market-data prompts but is a policy change to log.

### F10 — Real phase and the roadmap (HIGH, high confidence)
- **Claim:** The project is not "in P2"; it is "P1 built-but-unvalidated, blocked on hosting; P2 unstarted." The shutdown and naked positions dominate the next steps.
- **Evidence:** docs/10-build-log.md:215-239 (Incident 3: 8 positions open without stops, kill switch tripped, `data/STOP` paused to 2030-01-01, three scheduled tasks disabled, healthchecks paused). docs/07:15 (status line) still says "P1 built; the 2-week demo run starts once the scheduled tasks are installed" — no longer true. The P2 gate ("≥ 8 weeks of demo trading", docs/07:9 and docs/06:117) has not been approached.

## Proposed edits

### P-deepseek-1: Refresh the docs/08 roster and prices to 2026-11-25
- File: docs/08-multi-agent-llm.md §1 and §2 (one file per proposal)
- Change: replace the §1 model tables and §2 roster with the 2026-11-25 snapshot (F2/F3 above). Exact new roster rows:

```
| Seat | Default model | Type | Why |
|---|---|---|---|
| Juror 1 | Claude Opus 5.5 (`claude-opus-5-5`, effort low) | Paid | Anthropic's top practical model; Fable 5.2 (index 65) is stronger but $8/$40 and unnecessary for a bounded review |
| Juror 2 | GPT-6.2 Sol (`gpt-6.2-sol`) | Paid | Second lab; $2/$10 and index 57 vs GPT-6.2 Astra $8/$40 index 62. Astra runs once in the offline eval (§7) for comparison |
| Juror 3 | Gemini 4 Neon (`gemini-4-neon`) | Paid | Third lab; index 62 at $1.50/$7.50 — best price/performance on the board |
| Juror 4 | GLM-5.3 (`z-ai/glm-5.3`) | Open-weight | Z.ai's model; distinct lab. NOTE: no longer top open-weight (index 32) — see P-deepseek-4 |
| Juror 5 | Kimi K3.1 Pro (`moonshotai/kimi-k3.1-pro`) | Open-weight | Moonshot's model; index 47, $2/$10 |
| News analyst | DeepSeek V4.1 Flash 1017 (`deepseek/deepseek-v4.1-flash-1017`) | Open-weight (MIT) | Cheapest capable model; $0.15/$0.60 direct |
| Reporter | Gemini 4 Neon | Paid, cheap | Writes explanations; decides nothing |
```

  And delete/correct "Claude Opus 5.5 … #1 overall" (docs/08:15) and "tied for #1 open-weight" for GLM/Kimi (docs/08:28-29).
- Why: every id is stale; the ranking citation is factually wrong (AA leaderboard, 2026-11-25).
- Risk if wrong: pinning an id that doesn't exist on the provider breaks the desk at first run; the eval-set-before-swap rule (docs/08:126) applies.

### P-deepseek-2: Specify reasoning-effort and token caps in the cost model
- File: docs/08-multi-agent-llm.md §6
- Change: after the per-review cost table, add: "All five jurors are reasoning models. Run every juror with reasoning effort `low` and a hard `max_tokens` (e.g. 1,000) on the structured output; without this the thinking tokens can be 10-50× the answer and a review can cost several × the $0.16 figure. The per-call token/cost is logged (`llm_calls`) and the budget guard alerts at 80 %." Recompute the table to ≈ $0.16 (F5).
- Why: AA data shows reasoning models emit hundreds of millions of output tokens on an eval suite; the current "2k output+thinking" assumption is unstated and optimistic (F5).
- Risk if wrong: a mid-effort run quietly burns the €10 runtime or €15 eval cap; desk switches off mid-month.

### P-deepseek-3: Correct the P2 duration and add the sample-size reality
- File: docs/07-roadmap.md (P2 row and status line)
- Change: P2 duration "8+ weeks (mostly waiting)" → "≥ 12 months (mostly waiting; see docs/08 §7 sample-size note)"; and replace the stale status line (docs/07:15) with a 2026-11-25 status: P0 done, P1 built but no clean 2-week run, engine shut down since 2026-10-06, P2 unstarted, next step is the EU VPS (docs/09 §3) before the desk.
- Why: the "≥ 50 reviewed entries" gate (docs/06:110) needs 6-10 months at real S2 frequency, and veto-effect detection needs ~1-2 years (F6).
- Risk if wrong: the owner funds a P2 eval expecting an 8-week answer and gets nothing statistically meaningful.

### P-deepseek-4: Decide whether the open-weight seats stay "top open-weight" or "one per lab"
- File: docs/08-multi-agent-llm.md §2
- Change: open a decision item (for the owner / round 2) instead of asserting "top open-weight": GLM-5.3 is now index 32, behind Kimi K3.1 Pro (47) and Qwen4 Max (43, Alibaba). Option A: keep GLM-5.3 for lab diversity (the desk's own principle, docs/08:37). Option B: swap GLM → Qwen4 Max for the strongest open-weight seat. Recommend A in round 1 (diversity is the stated goal; the "top open-weight" label was the error, not the seat).
- Why: the §2 "Why" text for both open-weight jurors is now factually false (F2).
- Risk if wrong: none immediate (shadow only), but the doc currently makes a claim that no longer holds.

### P-deepseek-5: Broaden the desk's evaluation scope (decision, not code)
- File: docs/08-multi-agent-llm.md §2 / docs/06-backtesting.md §6
- Change: add an option to review S3 breakout entries (and/or S4 for calibration) alongside S2, to raise the reviewed-entry rate, because S2-only at ~5-8/month makes the veto effect a multi-year measurement (F6). Present as an owner decision: (a) S2-only and accept ~1-2 years of shadow, or (b) also review S3 to roughly double the entry rate.
- Why: the sample-size math is the single biggest constraint on the desk's research value (F6).
- Risk if wrong: reviewing S3 adds cost (~€2-4/month) and a small scope change to the desk contract (docs/04:182); S3 has no company-news gap vs S2, so no safety change.

### P-deepseek-6: Update the injection test set for adaptive/covert payloads
- File: docs/05-risk-and-safety.md §8 (injection test set bullet) and docs/08-multi-agent-llm.md §7
- Change: extend the injection test set from static payloads to include (i) adaptive/iterative payloads (IterInject, arXiv 2605.24659) and (ii) covert payloads that hide the instruction from the operator (arXiv 2608.30362), plus a test that the `NewsFindings.summary` field cannot carry an instruction that changes a juror's size upward (reduce-only already bounds the damage; the test should assert the bound).
- Why: the 2026 IPI literature shows payloads now adapt to static defences (F8).
- Risk if wrong: a false sense of injection resistance; the tests are the only forward check before `affects_orders=true`.

### P-deepseek-7: Re-verify ZDR endpoint ids and note the Google policy change
- File: docs/08-multi-agent-llm.md §5
- Change: add to the ZDR bullet: "Google models via Vertex now require Safety Retention (since 2026-10-18) and are excluded under strict ZDR — the Gemini seat uses Google's native SDK, so re-check its AI Studio retention terms separately. New open-weight checkpoint ids must be confirmed on https://openrouter.ai/api/v1/endpoints/zdr before pinning. ZDR traffic is CSAM-screened from 2026-10-27 (policy change, logged, no impact on market-data prompts)."
- Why: F9.
- Risk if wrong: a pinned open-weight id with no ZDR endpoint silently breaks the "no retention" guarantee the owner decided on (README:84).

## Open questions for round 2

1. **Owner:** does S2 stay live-trading (as a demo experiment) given it failed its gate, and should the desk's scope stay S2-only or also cover S3? (Decides whether the veto-effect measurement is 1 year or 3 years.)
2. **Antigravity/Mistral (research):** what are Google AI Studio's *current* paid-tier retention terms for Gemini 4 Neon (train-on-data yes/no), and does Anthropic offer ZDR for the native `claude-opus-5-5` API? (The doc claims "zero data retention" comfort for seats that do not go through OpenRouter.)
3. **Codex:** is there any desk code in the uncommitted tree I missed (I found none under `src/tradebot/`), and what is the exact plan to add `reasoning effort`/`max_tokens` to the provider adapters?
4. **Any agent:** confirm on https://openrouter.ai/api/v1/endpoints/zdr whether `moonshotai/kimi-k3.1-pro`, `deepseek/deepseek-v4.1-flash-1017` and `z-ai/glm-5.3` each have a ZDR-eligible endpoint today.
5. **Orchestrator:** on the VPS restart, what is the exact order of operations to re-place stops on the 8 naked positions before resetting the kill switch (build log says the engine auto-replaces on restart, docs/10:239) — does the desk review those re-entry decisions or not (they are not S2 entries, so by contract no)?
6. **Owner:** is the €10 runtime / €15 eval split still right, given the desk may now sit in shadow for 1-2 years (cost ≈ €1.7/month runtime, negligible)?

## Sources

- Artificial Analysis LLM leaderboard — https://artificialanalysis.ai/leaderboards/models (checked 2026-11-25). Model pages: https://artificialanalysis.ai/models/claude-opus-5-5 · /claude-fable-5-2 · /gpt-6-2-astra (checked 2026-11-25; per-1M prices, index, context).
- OpenRouter model pages (pricing + EU routing + ZDR status), checked 2026-11-25: https://openrouter.ai/openai/gpt-6.2-sol · /google/gemini-4-neon · /moonshotai/kimi-k3.1-pro · /z-ai/glm-5.3 · /deepseek/deepseek-v4.1-flash-1017.
- OpenRouter Zero Data Retention docs — https://openrouter.ai/docs/guides/features/zdr (checked 2026-11-25; Google Safety Retention 2026-10-18; CSAM screening 2026-10-27; per-model-group ZDR fields).
- 2026 indirect-prompt-injection literature (checked 2026-11-25): AgentSentry arXiv 2602.22724 · AttriGuard 2603.10749 · IterInject 2605.24659 · covert IPI 2608.30362 · "How vulnerable are AI agents to IPI" 2603.15714 · USENIX Security '26 "IPI in the wild" · ChatInject 2509.22830.
- Repo: README.md (D3/D4/D8, resolved items 2-4); docs/08 §1/§2/§5/§6/§7; docs/07 §(P2 row, status); docs/04 §6/§10; docs/06 §6; docs/05 §8; docs/10 (Incident 3, S2 61 % win rate, 812-trade backtest); config/instruments.toml; reports/daily/2026-10-02.md and 2026-10-05.md.
- UNVERIFIED (not independently checked this round): S2's exact steady-state live entry rate (only 6 trading days of demo data exist); Google AI Studio paid-tier retention terms; Anthropic native-API ZDR; OpenRouter ZDR eligibility of the three new open-weight ids.
