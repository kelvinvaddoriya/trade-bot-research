# Antigravity — Round 2 Cross-Review and Vote (2026-11-25)

All 5 Round 1 reports were present and read in full (`claude-consistency.md`, `codex-code-audit.md`, `antigravity-strategies.md`, `mistral-platforms-ops.md`, `deepseek-desk-roadmap.md`). All claims below were verified on **2026-11-25** against the `D:\TradeBot` working tree (ignoring `Trade-Bot-Research/`), read-only SQLite queries on `data/demo.db`, live public APIs (`https://openrouter.ai/api/v1/endpoints/zdr`, `https://openrouter.ai/api/v1/models`, Yahoo `.DE` chart API), and primary vendor documentation. Per orchestrator rules, all votes on `src/`, `tests/`, `config/`, and `ops/` proposals are **DESIGN approvals only** (no code edits applied while P1 is paused).

---

## Votes

### Claude (`claude-consistency.md`)

- `P-claude-1`: **APPROVE** — Accurately replaces the stale 2026-09-27 status (`README.md:5`) with verified 2026-10-06 shutdown facts, the 4-strategy demo scope, and the 8 unprotected lots (`docs/10-build-log.md:140-239`).
- `P-claude-2`: **APPROVE** — Verified against `config/settings.toml:8`, `config/instruments.toml:141-286`, and `docs/10-build-log.md:140-166`; keeps the live-gate requirement intact.
- `P-claude-3`: **AMEND (restrict this proposal to `docs/07-roadmap.md` only per handbook §3.2 one-file-per-proposal rule, merging status wording with `P-deepseek-3`, and archive `docs/10`'s "What happens next" in a separate build-log edit)** — Status facts are verified (`docs/07-roadmap.md:15`), but Change edits two files.
- `P-claude-4`: **APPROVE** — Closes the undocumented planned-shutdown gap in `docs/05-risk-and-safety.md §4`; independent Yahoo `.DE` daily-low path verification confirms actual unrealised P&L `−€63.78` vs `−€7.96` if stops had been kept (`≈ €55.82` avoided; none of ALV/BAYN/BMW touched stops, all 5 losers crossed stops between 10-08 and 11-20).
- `P-claude-5`: **AMEND (add that restart stop-through/overdue exits require explicit operator confirmation or a dedicated kill-exempt exit flag, because `execution.py:307-309` skips non-flatten exits while `KILL` is tripped)** — Core rule is vital (5/8 lots are below stops and `ensure_stops()` does not check market price), but the interaction with `KILL` must be specified.

### Codex (`codex-code-audit.md`) — all `src/`, `tests/`, `ops/` votes are DESIGN approvals only

- `P-codex-1`: **APPROVE** — Verified as design (`store.py:31` autocommit, `execution.py:156-184`); watermark-before-lot mutation, cumulative P&L distortion, and closed-lot resurrection are real defects.
- `P-codex-2`: **APPROVE** — Verified as design (`execution.py:270-292,312`); computing replacement stop size before cancel confirmation and ignoring `submit()` results on PENDING stops can oversize or drop protection.
- `P-codex-3`: **APPROVE** — Verified as design (`execution.py:61-74,106-149`); HTTP 408 rejection, unbounded precision retries on sells/stops, and first-match adoption are confirmed; rightly flags changing the two-lookup retry rule as an owner/doc decision.
- `P-codex-4`: **APPROVE** — Verified as design (`trading212.py:52-83,102-109`); GET-only bounded retries with a monotonic deadline plus `nextPagePath` pagination fix Incident 3 weakness 1 without risking duplicate POSTs.
- `P-codex-5`: **APPROVE** — Verified as design (`live.py:69-117,201-225,260-262`); whole-book marking, full unresolved-order reservations, per-held-symbol stale tracking, and pre-execution loss gating close confirmed safety gaps.
- `P-codex-6`: **APPROVE** — Verified as design (`cli.py:170-171,277-285,301-321`); eliminating concurrent CLI writers, adding an exclusive process lock, and requiring fresh reconciliation before `reset-kill` align code with `docs/05 §4`.
- `P-codex-7`: **APPROVE** — Verified as design (`risk.py:36-69`, `live.py:137`); finite/positive bounds, non-future bar checks, and timestamped rate limiting fix real pre-trade check gaps.
- `P-codex-8`: **APPROVE** — Verified as design (`sizing.py:15-32`, `live.py:139-152`); rounding before risk approval prevents dust/cap breaches while properly leaving frozen S1 untouched until the S1 €5-risk exception is resolved.
- `P-codex-9`: **APPROVE** — Verified as design (`data.py:137-139,191-195,226`); per-symbol refresh outcomes, `finally` connection closing, and empty-frame guards prevent full-cycle crashes.
- `P-codex-10`: **APPROVE** — Verified as design (`live.py:389-399`, `docs/10-build-log.md:227-230`); debouncing transient GET failures (`N=3`) while keeping safety/logical mismatches immediate fixes Incident 3 alert flapping.
- `P-codex-11`: **APPROVE** — Verified as design (`__main__.py:1-8`, `docs/10-build-log.md:231`); clean UTC line-timestamp wrapper preserving the stdlib-only no-pandas watchdog path.
- `P-codex-12`: **APPROVE** — Verified as design (`config.py:6-10,31-41,86-89`); required prerequisite for Linux VPS paths, `CREDENTIALS_DIRECTORY` loading, and all-sleeve settings validation.
- `P-codex-13`: **APPROVE** — Verified as design (`watchdog.py:20-46`); non-atomic heartbeat writes currently fail open (`JSONDecodeError -> None -> stopped`).
- `P-codex-14`: **APPROVE** — Verified as design (`risk.py:89-105`); atomic temp-replace writes and structured fail-closed corruption handling prevent lost kill state or unhandled crashes.
- `P-codex-15`: **APPROVE** — Verified as design (`tests/test_execution.py`); directly tests the reproduced partial-fill, cancel-race, 408/ambiguity, pagination, and precision failure transitions in `F16`.
- `P-codex-16`: **APPROVE** — Verified as design (`tests/test_live.py:152-201`); covers shared-book valuation (960 vs 980), 8-lot KILL recovery, Incident 3 debounce, and corrupt-heartbeat regressions.
- `P-codex-17`: **APPROVE** — Verified as design (`live.py:313-333`, complements `P-antigravity-6`); cleanly separates independent sleeve baselines from a shared-book portfolio replay.
- `P-codex-18`: **APPROVE** — Verified as design (`backtest.py:70-98` vs `execution.py:298`); global exit-first processing removes symbol-insertion-order cash bias while preserving historical baseline versioning.
- `P-codex-19`: **APPROVE** — Accurately documents current `strategies.py` defaults (`6/3/2/2`) while `src/` is frozen (minor: actual lines are `33,87,139,178`); will be superseded if the owner later approves `P-antigravity-5` (`S2 <= 2, €65`).
- `P-codex-20`: **APPROVE** — Verified (`docs/04-architecture.md:104,133` vs `settings.toml:8`, `store.py:15-20`); removes overstated Decimal/S2-shadow-only prose and marks pending recovery fixes honestly.
- `P-codex-21`: **APPROVE** — Verified (`docs/05-risk-and-safety.md:26,30,79,91-92,141` vs `risk.toml`, `cli.py:277-284`); brings documented P1 controls in line with implemented behavior while tracking gaps as release requirements.
- `P-codex-22`: **APPROVE** — Verified as design (depends on `P-codex-6/12/13`); sound Linux systemd engine unit (`ProtectSystem=strict`, `ReadWritePaths=/var/lib/tradebot`, `LoadCredential=`, `KillSignal=SIGINT`, `Restart=always`).
- `P-codex-23`: **APPROVE** — Verified as design (depends on `P-codex-12/13`); correctly uses `Type=oneshot` without `Restart=always`, keeping watchdog independent of engine lifetime.
- `P-codex-24`: **APPROVE** — Verified as design; accurately replaces the Windows 1-minute watchdog task (`ops/install-tasks.ps1:50-56`) with `AccuracySec=1s`.
- `P-codex-25`: **APPROVE** — Verified as design; `sqlite3.Connection.backup()` + `PRAGMA integrity_check` + atomic publish fixes `ops/install-tasks.ps1:58-63`'s single unverified overwrite.
- `P-codex-26`: **APPROVE** — Verified as design (depends on `P-codex-25`); least-privilege oneshot backup unit with no broker credentials and WAL-compatible path access.
- `P-codex-27`: **APPROVE** — Verified as design; persistent 03:00 UTC calendar timer catches missed nightly backups after host downtime.
- `P-codex-28`: **APPROVE** — Verified as design (pairs with `P-codex-4`); tests transport call counts, GET recovery, non-retry on ambiguous POSTs, and paginated history without `filledValue`.
- `P-codex-29`: **APPROVE** — Verified as design (pairs with `P-codex-12`); extends config validation tests from S1+S2 to all enabled sleeves, mappings, and fail-closed systemd credentials.

### Mistral (`mistral-platforms-ops.md`)

- `P-mistral-1`: **APPROVE** — Trading 212 rate limits in `docs/01-platforms.md:44-52` are confirmed unchanged as of 2026-11-25 (corroborated by Codex `[S5]`).
- `P-mistral-2`: **AMEND (replace "Incident 3, 2026-10-01" with "2026-10-01 quantity-precision trip, docs/10-build-log.md:189-205", state that precision varies empirically rather than asserting an unverified "< €100" broker rule, and note the dynamic precision fallback)** — Mislabels 2026-10-01 as Incident 3 (which was 2026-10-06 OOM) and overstates an empirical 3-ticker observation as a broker rule.
- `P-mistral-3`: **REJECT** — Target text does not exist in `docs/01-platforms.md §3` (a table), and every proposed detail (05-Jan-2026, FXFlat, 25%/5.5%/church tax, Freistellungsauftrag) is already written in `docs/01-platforms.md:57` (§4.1) and `docs/05-risk-and-safety.md:175-176`.
- `P-mistral-4`: **REJECT** — Factually wrong on all three providers (verified 2026-11-25): netcup VPS 500 G12.5 has 64 GB SSD at €9.50/mo incl. VAT no-contract (not 128 GB at €5.91); Hetzner's current plan is CPX22 at €19.49 excl. VAT (not deprecated CPX21 at €19.99); OVHcloud mixes USD ($4.54) into an EUR-incl.-VAT table.
- `P-mistral-5`: **REJECT** — Redundantly duplicates `docs/05-risk-and-safety.md:172-173,182`, which already state the MiFID II retail scope, EU AI Act Art. 2(10), and the Feb 2026 ESMA Supervisory Briefing with appropriate non-legal-advice nuance.
- `P-mistral-6`: **REJECT** — Dangerous and broken: conflates P1 demo VPS restart with P3 live (`live.trading212.com` for demo lots), uses nonexistent APIs/events (`Trading212Broker`, `STOP_ADOPTED`), breaks `git clone`/tar/systemd units, falsely claims `reconcile` adopts unknown stops, and ignores 5/8 lots being below stop price (see Challenges).

### Deepseek (`deepseek-desk-roadmap.md`)

- `P-deepseek-1`: **AMEND (correct Gemini 4 Neon's synchronous price from `$1.50/$7.50` to `$3.00/$15.00` per 1M tokens [`$1.50/$7.50` is Batch API only, verified 2026-11-25 on Google AI Studio and OpenRouter], and remove "cheap" from the Reporter row or pick a cheaper non-flagship tier)** — AA rankings and other model IDs are verified, but Gemini 4 Neon's sync price is off by 2×.
- `P-deepseek-2`: **AMEND (recompute the §6 table with Gemini 4 Neon at `$3.00/$15.00` sync → `$0.045`/review and `≈ $0.18` total/review instead of `$0.16`, and specify whether `max_tokens` caps visible output or output+thinking per SDK)** — Pinning `reasoning effort = low` and token caps is essential, but the `$0.16` figure uses the 50%-off batch price.
- `P-deepseek-3`: **APPROVE** — Verified binomial power math (`n_v ≈ 16/37/150`) and `≥ 50`-entry gate floor (`docs/06:110`); on EU-18 live S2 (~4.1–4.5 trades/mo), `≥ 12 months` is conservative; coordinate status wording with `P-claude-3`.
- `P-deepseek-4`: **AMEND (remove Qwen4 Max from Option B because Qwen4 Max is proprietary API-only with 0 OpenRouter ZDR endpoints [verified 2026-11-25]; keep `z-ai/glm-5.3` [42 ZDR endpoints] for lab diversity or compare against open-weight ZDR alternatives such as `z-ai/glm-5.3-flash` [32 ZDR endpoints])** — Correcting the stale "top open-weight" label is right, but Option B nominates a closed-weight, non-ZDR model.
- `P-deepseek-5`: **AMEND (restrict edit to `docs/08-multi-agent-llm.md §2` per handbook §3.2, frame the owner decision around S2/S3 or an approved single-stock S2 replacement such as C1, and clarify S4 stays an unmodified control book unless scored offline/shadow-only)** — Valid decision item given the sample-size bottleneck, but spans two files and omits S2's P0 failure.
- `P-deepseek-6`: **AMEND (apply only to `docs/05-risk-and-safety.md §8` per handbook §3.2 one-file-per-proposal rule, with `docs/08 §7` referencing §8)** — Adding adaptive/covert IPI payloads and testing the `NewsFindings.summary` channel (`docs/08:106`) is well-founded.
- `P-deepseek-7`: **AMEND (incorporate 2026-11-25 live ZDR verification: `z-ai/glm-5.3` [42], `moonshotai/kimi-k3.1-pro` [27], and `deepseek/deepseek-v4.1-flash-1017` [47] all have OpenRouter ZDR endpoints; clarify that native Google AI Studio paid tier and standard Anthropic API prohibit training but retain abuse/safety logs [Anthropic 30d default; ZDR requires enterprise sales approval])** — OpenRouter policy updates verified; folding in today's live checks resolves the open verification immediately.

---

## Answers

### 1. Claude Q3 (to Antigravity): Restart the forward-check clock, or exclude the 10-06 → restart gap and stitch?

**Restart the forward-check clock from zero at the VPS launch (`live.start = <restart_date>`), and preserve the 2026-09-28 → 2026-10-06 laptop record intact as archived history. Do NOT stitch across the gap.**

- **Why stitching is statistically and operationally dishonest:**
  1. **Severe path dependence:** S1–S4 are stateful (sleeve cash, slot limits, shared-book `taken` ownership, S2/S4 holding-day counts, S1's missed monthly checks on 2026-10-30 and 2026-11-27). Between 2026-10-06 and 2026-11-25, **5 of 8 lots breached their protective stops** (Yahoo `.DE` daily lows, verified 2026-11-25: `IFX` 10-08, `IS3N` & `SXRV` 10-15, `SXR8` 11-05, `EXW1` 11-20), and the remaining 3 (`ALV`, `BMW`, `BAYN`) are 6–7 weeks past mandatory time exits. Stitching across a 7-week unhedged gap compares a damaged live book against a backtest that either stopped out or rotated into different names, guaranteeing permanent noise in `live.forward()`.
  2. **P1 gate definition (`docs/06 §5`, `docs/07:8`):** P1 tests *implementation parity* (`2 weeks of clean unattended runs`, `100% signal match`), not return accumulation. The 09-28 → 10-06 window already failed that gate (3 laptop OOMs, 10-01 precision trip, 10-06 stop cancellation, missing per-strategy start dates). Restarting cleanly on the VPS from zero ensures any future `**differs**` flag is a genuine engineering defect.
  3. **Audit integrity (`docs/04 §1`):** Never erase `reports/daily/2026-09-25..10-05.md` or `demo.db` events; log the unhedged shutdown episode (`≈ −€55.82` extra demo drawdown) transparently in `docs/10-build-log.md`.

### 2. Claude Q5 (to All): Keep, flatten, or exit-by-rule the 8 lots at restart?

**Flatten all 8 demo lots at restart (under explicit owner authorization while `KILL` remains tripped), verify flat reconciliation, and begin the VPS P1 soak cleanly from cash.**

- **Quantitative proof that "exit-by-rule" equals 100% exit anyway (Yahoo `.DE` closes & lows through 2026-11-25, `data/demo.db` read-only):**
  - **5/8 lots are below their protective stop (`stop-through`):** `SXR8` (`690.04 < 720.66`), `EXW1` (`59.61 < 60.43`), `IS3N` (`40.72 < 46.83`), `SXRV` (`1314.60 < 1507.64`), `IFX` (`40.90 < 58.87`).
  - **3/8 lots are ~38–39 Xetra sessions past mandatory time exits:** `ALV` (S4, entered 10-01, 5-day hold), `BMW` (S4, entered 10-02, 5-day hold), `BAYN` (S2, entered 10-02, 10-day time stop).
- Not a single lot is still valid under its strategy rule. "Keep" violates all four strategies and triggers the sell-stop-above-market hazard on 5/8 positions; "exit-by-rule" closes all 8 anyway. Flattening explicitly after a fresh read-only broker inventory check (confirming quantities, splits/dividends, and precision per Codex F14), while keeping `KILL` tripped until broker flat + clean reconcile + updated `live.start`, gives the cleanest, safest reset. *(We still support `P-claude-5` for future shorter outages where only a subset of lots gap through stops.)*

### 3. Codex Q8 (to Quant agents): Shared-book replay contract, activation/ownership policy, and S2/S3/S4 collision accounting

To resolve the structural `**differs**` failures (`live.py:313-333`, Antigravity Round 1 F5, Codex F12), define two distinct, explicitly labeled evaluations:

1. **View A — Independent Sleeve Baseline (`backtest.py`, unchanged role):** Each strategy runs alone on its full live-tradable EUR universe with its own budget. Used for P0 research gates and multi-seed statistical benchmarking (`docs/06 §7`). Relabel in `live.forward()` as `independent baseline` (`P-codex-17`).
2. **View B — Shared-Book Portfolio Replay (the P1/P2 implementation-parity contract):** A deterministic multi-strategy daily simulator replicating live `Engine` rules:
   - **Activation & initial state:** Each strategy has an explicit `strategy_start[name]` date (from `settings.toml` / journal) and `budget_eur[name]`. Strategies only participate on `d >= strategy_start[name]`. Starts flat from `live.start` (recommended after flattening) or from a journaled starting-lots snapshot.
   - **Global daily execution order:**
     1. *Open — global exits first (`P-codex-18`):* execute all pending exits across all strategies before any pending entry; credit proceeds to each exiting strategy's sleeve cash and release ticker ownership immediately on fill.
     2. *Open — pending entries:* execute pending entries in fixed `settings.live.strategies` priority order (`s1_trend → s2_pullback → s3_breakout → s4_monkey`), applying venue rounding (`ENTRY_DECIMALS`, cents) and reserving sleeve cash and global slots. Record open-only vs resting DAY limit as a labeled `fill_policy` residual (`docs/04:106`).
     3. *Intraday — stops & `bars_held`:* check stops on all open lots; increment `bars_held` on surviving lots using actual broker/simulated fill dates (`live.py:99-100`, Codex F3).
     4. *Close — sequential decisions with `taken` ownership lock:* iterate `settings.live.strategies` in priority order. Compute `taken = {sym with OPEN lot or non-final entry owned by another strategy}` (`P-codex-5`) and exclude `taken` from the strategy's candidate universe *before* calling `strat.decide()`. Add newly planned entries to `taken` immediately; release a ticker only after its exit fills (matching `live.py:92-94`).
   - **Counting S2/S3 collisions:** Log every suppressed signal as a structured `COLLISION(date, blocked_strategy, owner_strategy, symbol, rank)` record. Because priority order is deterministic (`S2 → S3 → S4`), View B reproduces S3's exact filtered candidate pool so `100% signal match` is restored, while `View B − View A` directly measures the economic **collision drag** of sharing one book.
   - **Counting foregone S4 (`s4_monkey`) choices:** In live execution, `S4` calls `rng.sample(sorted(eligible \ taken), free)` (`strategies.py:198-200`). Passing the exact same `taken`-filtered candidate list and date seed in View B reproduces live S4 picks **100% identically** (eliminating false `**differs**` such as `AIR, SAP` vs `ALV, BMW`). Because dropping one symbol shifts all subsequent `rng.sample` draws, single-seed divergence between View A and View B is expected combinatorics, not a bug: use **View B** for implementation parity, and use a **≥ 50-seed View A ensemble** for statistical null benchmarking (`P-antigravity-1`).
   - **Operator events:** Replay consumes journaled `KILL` windows and `CATCHUP_REQUESTED` dates (or tags affected dates `divergent: operator_event`) so manual pauses/catch-ups are never confused with code drift. *(Formalized in `P-antigravity-9` below.)*

### 4. Deepseek Q2 (to Antigravity/Mistral): Google AI Studio paid-tier retention for Gemini 4 Neon & Anthropic native API ZDR for `claude-opus-5-5`

Verified **2026-11-25** against primary provider terms (Google Gemini API Additional Terms / `blog.google` / `ai.google.dev`; Anthropic Commercial Terms & ZDR documentation at `claude.com` / `anthropic.com`):

| Provider & Seat | Model ID (native) | Train on data? | Default retention | Strict ZDR available? | Practical note for `docs/08 §5` |
|---|---|---|---|---|---|
| **Google AI Studio** (Paid Services) | `gemini-4-neon` (`$3/$15` sync; paid-tier only) | **No** (contractual under Cloud Billing + Cloud DPA; EEA/UK/CH also covered) | Temporary **abuse/safety logging** for Prohibited Use Policy & legal compliance | **No** on standard AI Studio (and Vertex requires Safety Retention since 2026-10-18) | Must tie API key to a Cloud Billing project; do not call it "ZDR" |
| **Anthropic API** (Commercial API) | `claude-opus-5-5` (`$4/$20`) | **No** (excluded by default on commercial API) | **30 days** auto-delete (up to 2 years if flagged for Usage Policy violation) | **Enterprise/sales-approved only** (per-org approval; EFS/BYOS exceptions for covered frontier models) | Individual developer keys get 30d retention + no training, NOT out-of-the-box ZDR |
| **Anthropic Interim** (`claude -p`, `docs/08 §5.1`) | Subscription `opus` | **Opt-out toggle** on consumer Free/Pro/Max plans | Consumer retention rules | **No** (explicitly ineligible for ZDR) | Owner must ensure the consumer training toggle is OFF while using interim `claude -p` |

**Conclusion:** `docs/08 §5` must NOT claim "zero data retention" for native Google or Anthropic developer keys. The accurate, defensible posture is: **no model training** across all paid native APIs, **temporary abuse-monitoring retention** (acceptable because prompts contain zero personal data — only public prices/news and trade intents), and **account-wide ZDR on OpenRouter** for open-weight seats (noting OpenRouter's in-flight CSAM exception).

### 5. Deepseek Q4 (to Any agent): Live OpenRouter ZDR endpoint verification (`https://openrouter.ai/api/v1/endpoints/zdr`)

Directly queried `https://openrouter.ai/api/v1/endpoints/zdr` on **2026-11-25** (946 total ZDR endpoints returned):

- **`moonshotai/kimi-k3.1-pro`:** **YES — 27 ZDR endpoints** (incl. Amazon Bedrock, Fireworks, DeepInfra, Nebius, Together, DigitalOcean, Parasail, Modal).
- **`deepseek/deepseek-v4.1-flash-1017`:** **YES — 47 ZDR endpoints** (incl. Together, DeepInfra, Fireworks, Nebius, Cloudflare, CoreWeave, Google, Mistral, Cohere, Venice).
- **`z-ai/glm-5.3`:** **YES — 42 ZDR endpoints** (incl. Together, DeepInfra, Amazon Bedrock, Fireworks, Nebius, Cloudflare, CoreWeave, Mistral, Venice).
- **Additional checks relevant to Round 2:** `z-ai/glm-5.3-flash` has **32 ZDR endpoints** (`$0.12/$0.38` on OpenRouter); `openai/gpt-6.2-sol` has **1 ZDR endpoint** (`Azure`); `anthropic/claude-opus-5.5` has **2 ZDR endpoints** (`Amazon Bedrock`, `Google`); **`qwen/qwen4-max` has 0 ZDR endpoints** (and is proprietary API-only); `anthropic/claude-fable-5.2` has **0 ZDR endpoints**.

### 6. Orchestrator note on Antigravity's Round 1 unlogged ad-hoc backtests

Acknowledged and accepted. Because Round 1 rules forbade modifying any file outside our report, our exploratory in-sample runs (`S1` `atr_mult` sensitivity, `S2` US/EU decomposition, `C1`/`C2` IS sanity checks, 10-seed `S4` dispersion) were **not** appended to `data/trials.jsonl`. They represent real unlogged IS trials and **must** be counted toward `N` / `N_eff` in any future DSR calculation for `S1b`, `C1`, or `C2` (we must not treat `C1`/`C2` as `N = 1` "unoptimized" once exploratory runs exist). Holdout `2020–2024` remained strictly untouched for `C1` and `C2`. *(Formalized in `P-antigravity-10` below.)*

---

## Challenges

1. **`mistral-platforms-ops.md` (F-20, F-25, P-mistral-4)**
   - **Claim:** `netcup VPS 500 G12.5` provides **128 GB NVMe/SSD** at **€5.91/mo (incl. 19% VAT)** with **no contract**.
   - **Why wrong:** Conflates a legacy/promotional G12 figure and VPS 1000's 128 GB storage with VPS 500 G12.5's actual month-to-month terms.
   - **Evidence:** Web verification on 2026-11-25 (`vpsbenchmarks.com`, `netcup.discount`) and `docs/09-hosting.md:45`: `VPS 500 G12.5` includes **64 GB SSD** (128 GB starts at `VPS 1000 G12.5`) and costs **€7.98/mo excl. VAT (€9.50/mo incl. 19% VAT)** on a 1-month contract, or €6.94/mo excl. VAT (€8.26 incl. VAT) on 12 months.

2. **`mistral-platforms-ops.md` (F-22, P-mistral-4)**
   - **Claim:** Hetzner Cloud's entry point is **CPX21 at €19.99/mo**.
   - **Why wrong:** Misnames the deprecated `CPX21` plan (Mistral's own quoted source says `CPX22`) and misstates the current rate.
   - **Evidence:** Web verification on 2026-11-25 (`betterstack.com`, `cloudtally.eu`) and `docs/09-hosting.md:48`: the active 2 vCPU / 4 GB plan is **CPX22** (80 GB NVMe) at **€19.49/mo excl. VAT**. (Similarly, OVHcloud VPS-1 in `P-mistral-4` mixes US-store `$4.54/mo` into an EUR-incl.-VAT table; German OVHcloud store lists from €4.53/mo incl. VAT on 12 months / €5.34 no-contract, checked 2026-11-25.)

3. **`mistral-platforms-ops.md` (F-5, P-mistral-2)**
   - **Claim:** Attributes the 2026-10-01 quantity-precision rejections to **"Incident 3 (2026-10-01)"** and asserts **3-decimal precision is required for instruments under €100**.
   - **Why wrong:** Wrong incident label (Incident 3 was the 2026-10-06 OOM shutdown), and `< €100` was merely an observation across 3 rejected orders (`DTE, EXW1, IS3N`), not a documented broker rule.
   - **Evidence:** `docs/10-build-log.md:189-205` (2026-10-01 precision trip) vs `docs/10-build-log.md:215-239` (Incident 3, 2026-10-06); `src/tradebot/trading212.py:30` (`ENTRY_DECIMALS = 3` globally) and `execution.py:106-131` (dynamic fallback).

4. **`mistral-platforms-ops.md` (Section 4 Restart Runbook, P-mistral-6)**
   - **Claim:** Provides an executable restart runbook migrating the 8 open demo lots onto a VPS in `mode = "live"` via `Trading212Broker`, `git clone`, `tar -C data/`, `systemd-creds`, and `tradebot reconcile` auto-adopting stops.
   - **Why wrong:** Contains five severe operational/code errors that would fail or risk live-account errors:
     1. Conflates the **P1 demo** VPS restart with **P3 live** (`mode = "live"`, `https://live.trading212.com/api/v0`, `T212_LIVE_KEY` for 8 demo lots — blocked by `cli.py:148`, `trading212.py:45`, and Part 4 rule 1).
     2. Invents nonexistent classes/methods/events/files (`Trading212Broker`, `place_stop_order()`, `get_orders()`, `STOP_ADOPTED`, `SYNC_COMPLETE`, `data/events.db`, `data/journal.jsonl`; actual code has `Trading212`, `place_stop()`, `orders()`, `data/demo.db` at `trading212.py:43,96,126` and `store.py:11-21`).
     3. Falsely claims `tradebot reconcile` adopts unknown broker stops (line 590) and `reset-kill` runs reconciliation (line 606); in fact `execution.py:206-208` flags unknown broker orders as mismatches (→ HALT) and `cli.py:277-285` only prints the last historical reconcile event.
     4. Fabricates S2/S3/S4 stop formulas (`"entry - 0.5% or entry - 3×ATR"`, line 527; actual code is `2.5×ATR(14)` for S2/S4 and `2.0×ATR(20)` for S3 at `strategies.py:85-86,137-138,176-177`) and ignores that 5/8 lots are below their October stops.
     5. Broken deployment steps: `git clone` omits the ~700 uncommitted lines (`HEAD` is `42792f1`); `tar xzvf ... -C data/` nests `data/data/demo.db`; invalid `systemd-creds`/`LoadCredential=` syntax (`config.read_env()` ignores `CREDENTIALS_DIRECTORY`); `ProtectHome=yes` + `WorkingDirectory=/home/tradebot/TradeBot` + `ProtectSystem=strict` without `ReadWritePaths` breaks startup; `tradebot-watchdog.service` mixes `Type=simple`/`Restart=always` with a timer.
   - **Evidence:** `src/tradebot/cli.py:148,277-285`, `trading212.py:43-46,96,126`, `execution.py:206-208`, `strategies.py:85-86,137-138,176-177`, `store.py:11-21`, `config.py:31-41`, `Agent-Guide.md:96`.

5. **`deepseek-desk-roadmap.md` (F3, F5, P-deepseek-1, P-deepseek-2)**
   - **Claim:** **Gemini 4 Neon** costs **`$1.50 / $7.50`** per 1M tokens ("gets *cheaper* and stronger by moving off 3.8 Flash"), yielding a per-review total of **`≈ $0.16`**.
   - **Why wrong:** `$1.50 / $7.50` is the 50%-off **Batch API** price (`google/gemini-4-neon:batch`), not real-time synchronous inference.
   - **Evidence:** Verified 2026-11-25 on Google AI Studio (`ai.google.dev` / `blog.google`) and live OpenRouter `/api/v1/models`: synchronous `gemini-4-neon` is **`$3.00 / $15.00`** per 1M tokens (2–4× more expensive than Gemini 3.8 Flash's `$0.75/$3.75` intro / `$1.50/$7.50` 2027 rate). Correct per-review cost at 5k/2k tokens is **`≈ $0.18`** (`$0.1826`), still comfortably inside the €10/mo runtime budget (`≈ €2.15/mo` at 10 reviews + 22 reports).

6. **`deepseek-desk-roadmap.md` (F2, P-deepseek-4)**
   - **Claim:** Treats **Qwen4 Max** as an **open-weight** model and proposes swapping GLM-5.3 → Qwen4 Max *"for the strongest open-weight seat."*
   - **Why wrong:** Qwen4 Max is strictly **proprietary API-only** (no downloadable weights) and has **zero** OpenRouter ZDR endpoints.
   - **Evidence:** Web verification on 2026-11-25 (Alibaba Qwen4 Max release 2026-11-16: proprietary cloud API only, no Hugging Face weights, mirroring `Qwen3.8 Max` in `docs/08:30`) and live query to `https://openrouter.ai/api/v1/endpoints/zdr` on 2026-11-25 (`qwen/qwen4-max`: `0` ZDR endpoints).

7. **`deepseek-desk-roadmap.md` (F7, line 75)**
   - **Claim:** *"Observed demo week (`reports/daily/2026-10-02.md`, `2026-10-05.md`): S2 entries BAYN, DHL, BMW (~3 in the first 5 trading days)"*.
   - **Why wrong:** `BMW` is an **S4 (`s4_monkey`)** lot, not S2. S2 had only **2** demo entries (`BAYN`, `DHL`).
   - **Evidence:** `data/demo.db` (`lots` table, read-only 2026-11-25: `id='52bf027c580b7868'`, `strategy='s4_monkey'`, `symbol='BMW'`, `entry_date='2026-10-02'`) and `reports/daily/2026-10-02.md:11,13` (`s2_pullback` open lots = 2; `s4_monkey` open lots = 2).

8. **`deepseek-desk-roadmap.md` (F6, lines 53 & 62)**
   - **Claim:** Uses `812 trades / 13y = 5.2/mo` (`docs/10:168`) and `61%` win rate (`docs/10:522`) to calculate live S2 shadow timelines.
   - **Why wrong:** Both numbers come from US+EU stock backtests (`812` trades = 26 US+EU stocks in `reports/backtest_s2_pullback_insample_2026-09-30.md:8,30`; `61%` = 14 US+EU stocks in P0), whereas live S2 trades only 18 German EUR stocks (~643 trades / 13y = **4.1/mo**, or 697 = **4.5/mo** with fixed 2×€65 caps — Antigravity Round 1 F1). This strengthens rather than weakens Deepseek's conclusion: reaching 50 reviewed entries on EU-18 takes ~11–12 months.

---

## New proposals

### P-antigravity-9: Specify the shared-book replay contract and clean-start forward-check rule
- File: `docs/06-backtesting.md` §5
- Change: Add two paragraphs after the "Tracking check" bullet:
  1. *"Shared-book replay vs independent baseline: when multiple strategies share one book and ticker-ownership lock, keep two clearly labeled checks: (a) the **independent sleeve baseline** (each strategy alone on its live EUR universe, used for P0 gates and ≥ 50-seed S4 null benchmarks), and (b) the **shared-book portfolio replay** (the P1/P2 implementation check). The shared-book replay uses each strategy's actual `strategy_start` date, executes global exits before entries at the open, applies venue rounding, increments `bars_held` from actual fill dates, and runs close decisions in fixed `settings.live.strategies` priority order while excluding symbols owned or pending-entry by another strategy (`taken`). Suppressing a candidate by `taken` is logged as a `COLLISION` event rather than an unexplained mismatch; S4 receives the same `taken`-filtered candidate list and date seed so its live picks replay identically; journaled `KILL` windows and operator catch-ups are tagged `divergent: operator_event`."*
  2. *"Clean-start rule after multi-day outages: do not exclude a multi-day unhedged shutdown gap and stitch forward-check series across it. Archive the prior period in the journal/reports, reconcile or flatten stale positions under owner authorization, and restart the forward-check clock (`live.start`) from zero."*
- Why: Directly resolves Claude Q3 and Codex Q8; eliminates structural false `**differs**` flags (`live.py:313-333`, `reports/daily/2026-10-05.md:63-68`) and prevents dishonest gap stitching after the 2026-10-06 → VPS outage.
- Risk if wrong: Low (documentation contract only; guides future `P-codex-17`/`P-antigravity-6` implementation without changing frozen strategies).

### P-antigravity-10: Require accounting for unlogged exploratory trials before DSR/promotion gates
- File: `docs/06-backtesting.md` §2.6
- Change: Append to §2.6: *"Any exploratory or ad-hoc in-sample backtest run outside `cli.py` (for example during read-only research rounds where `data/trials.jsonl` cannot be written) still counts toward the true trial count `N` and effective independent trials `N_eff`. Before a strategy or variant enters a promotion gate or DSR calculation, declare and log all prior exploratory runs (or conservatively increment `N` to include them); never treat a strategy as an untouched `N = 1` default after exploratory IS checks have been inspected."*
- Why: Addresses the orchestrator's Round 2 finding that Antigravity's read-only Round 1 IS checks (S1 `atr_mult` sensitivity, S2 splits, C1/C2 sanity runs) were not written to `data/trials.jsonl`; prevents accidental data-snooping understatement in DSR.
- Risk if wrong: None (stricter statistical honesty; cannot weaken any gate).

---

## Open questions

1. **Owner (VPS restart & post-soak strategy direction):** Confirm (a) flattening all 8 demo lots at VPS restart and resetting `live.start` from cash (per Claude Q5 & our Q3/Q5 answers), and (b) whether the €400 non-S1 budget post-soak should go to **C1** (52-Week High Momentum on EUR large caps — keeps single-stock news alive for R1) or **C2** (EUR UCITS Dual Momentum — zero survivorship bias), or remain split across S2/S3/S4 demo experiments.
2. **Owner / Deepseek (LLM desk Reporter & Juror 4 seat):** Given Gemini 4 Neon's verified synchronous price (`$3.00/$15.00`, not `$1.50/$7.50`) and Qwen4 Max being proprietary with 0 ZDR endpoints, should (a) the Reporter seat use a cheaper Gemini tier (e.g., Argon/Hydrogen) instead of Neon, and (b) Juror 4 remain on `z-ai/glm-5.3` (42 ZDR endpoints) or evaluate `z-ai/glm-5.3-flash` (32 ZDR endpoints, `$0.12/$0.38`)?
3. **Mistral / Owner (EU VPS final provider & distro):** With netcup VPS 500 G12.5 verified at **€9.50/mo incl. VAT** (64 GB SSD, 1-month) vs OVHcloud VPS-1 at **€5.34/mo** no-contract (€4.53/mo 12-month), confirm the chosen provider, datacenter, and Linux distro/systemd version so `P-codex-22..27` units can be validated against the target host.
4. **Deepseek (quant verification carry-over from Round 1):** Still awaiting independent verification of Round 1 S1 DSR/MinTRL (`N_eff` via eigenvalue clustering on the 18-cell S1 grid) and fixed `-15%` vs entry-fixed `5×ATR(20)` catastrophic broker stop for the `S1b` walk-forward design.
