# 3paperresearch — what the three LLM-quant papers offer this project

Read in full 2026-10-01, from the three arXiv links in the "3 AI Quant Finance Projects" post.

**Verdict up front:** none of the three papers is evidence of a live edge, and all three use a weaker evaluation method than this repo already uses. Their reported returns come from short, favourable, mostly pre-training-cutoff windows, with transaction costs either excluded or unstated. What *is* worth taking is three cheap mechanisms — not the architectures and not the numbers. All three fit existing seams in the code; none needs a new dependency.

## 1. The three papers

| # | Paper | Date | What it actually is | Headline claim |
|---|---|---|---|---|
| P1 | [TradingAgents: Multi-Agents LLM Financial Trading Framework](https://arxiv.org/abs/2412.20138) | Dec 2024, v7 Jun 2025; oral, Multi-Agent AI in the Real World | 7–8 LLM agents (fundamentals, sentiment, news, technicals, bull/bear researchers, trader, risk manager) with debate rounds and a facilitator | +26.62 % CR, Sharpe 8.21 on AAPL |
| P2 | [HARLF: Hierarchical RL and lightweight LLM sentiment](https://arxiv.org/abs/2507.18560) | Jul 2025, Coriat & Benhamou | 4 RL algos (PPO/SAC/DDPG/TD3) → 2 meta-agents → 1 super-agent, allocating 14 index/commodity weights monthly | 26 % annualised, Sharpe 1.2, 2018–2024 |
| P3 | [Automate Strategy Finding with LLM in Quant Investment](https://arxiv.org/abs/2409.06289) | EMNLP 2025 | GPT-4o writes 100 formulaic alpha factors in 9 categories; two agents score them on IC and risk; a 3-layer MLP learns the weights | 53.17 % cumulative return, SSE50 2023 |

## 2. Why the numbers don't transfer

### 2.1 Apply this repo's own Sharpe standard error

`backtest.py:173` already computes `sharpe_se = sqrt((1 + SR**2 / 2) / years)`. Applied to the papers' own figures:

| Paper | Reported Sharpe | Window | SE by our formula | Reading |
|---|---|---|---|---|
| P1 (AAPL) | 8.21 | 3 months (0.25 y) | **± 11.8** | Indistinguishable from zero. A 3-month Sharpe of 8 is a window artefact, and the authors say so: "few pullbacks during that period". |
| P2 (super-agent) | 1.2 | 7 years | ± 0.50 | Suggestive. Beats the S&P 500's 0.63 ± 0.41, but not by a significant margin. The most believable claim of the three. |
| P3 | 0.287 / 1.94 / 13.33 | varies | — | The same system is given three incompatible Sharpe values in one paper (results table, ablation table, hyperparameter table). Sharpe is not being computed consistently, so no figure in P3 can be relied on. |

P3 also reports 192.27 % for H1 2023 on CSI300 against a 9.13 % benchmark. Long-only and unlevered, that is not plausible.

### 2.2 Training-cutoff contamination

P1 backtests **January–March 2024** using models trained on data through at least late 2023, and later still in the v7 revision. The LLM knows what happened to NVDA that quarter. P3 has GPT-4o generate factors from 11 research documents and then tests on 2021–2024 price data that is also in its training set.

This repo's eval design already names the defence: "~50 frozen historical S2 contexts *dated after every model's training cutoff*" ([08 §7](08-multi-agent-llm.md#7-evaluation)). P1 is the proof that the precaution is load-bearing, not paranoia.

### 2.3 Costs and the publication-decay problem

P2 states plainly that it "excludes transaction costs, inflating practical returns". P1 never specifies position sizing. P3 caps turnover at ~38 % monthly but its cost model isn't reconcilable with its return figures.

P3 has a deeper problem that [03](03-strategies.md) already cites the answer to: an LLM mining alpha factors out of the published literature is, mechanically, recalling post-publication factors — exactly the ~58 % return decay McLean & Pontiff (2016) measure. P3's own limitations section concedes its factors "occasionally lack the financial intuition characteristic of human analysts".

### 2.4 Nobody ran a monkey

P1's baselines are buy-and-hold and four indicator rules. P2's are equal-weight and the S&P 500. P3's are XGBoost, LightGBM, MLP and PPO. **None of the three compares against random entries with the same exits, holding period and costs** — which is what **S4** ([03 §3](03-strategies.md#s4-the-monkey-random-entries-the-control-group-2026-09-30)) exists to do. Our own S2 failed its gate; a comparable strategy in any of these papers would never have been tested that way.

## 3. Worth building (three items, all cheap)

### 3.1 From P2 — sentiment as a numeric feature, not just an enum

P2's one clean, repeated result: the NLP-fed meta-agent beat the metrics-only meta-agent at every level (20.5 % ROI / Sharpe 1.2 vs 14.7 % / 0.8), and every NLP base agent beat its metrics-only twin. Sentiment carried signal as a *continuous monthly number*, computed by code.

Their sentiment model is **FinBERT** — a 110 M-parameter BERT classifier from 2019, not an LLM in the current sense; the paper's framing oversells this. The score is just `sum(P_positive - P_negative) / N` over the month's headlines.

**The lazy version, which needs no new dependency:** the news analyst already emits `direction` and `materiality` per item ([08 §4](08-multi-agent-llm.md#4-schemas)). Collapse those into one signed scalar in the context builder —

```
sentiment_score = sum(±1 × materiality) / sum(materiality)   # positive +1, negative −1, neutral/unclear 0
```

— and hand the jurors (and the shadow books) a number rather than only a list of enums. Three lines, zero cost, and it gives the per-juror scorecard in [08 §7](08-multi-agent-llm.md#7-evaluation) something continuous to calibrate against.

Running FinBERT locally as a *second, independent* sentiment opinion is the upgrade path, not the starting point: it costs a `torch` + `transformers` install (~2.5 GB) on an i5-7200U with 8 GB RAM. Do it only if the cheap scalar shows signal, and then mainly for its best property — a FinBERT-vs-news-analyst disagreement is a free `data_suspect` trigger that doesn't depend on any provider.

### 3.2 From P3 — Information Coefficient in the backtest report

P3's single best methodological idea is scoring each signal by **IC**, the rank correlation between the signal value and the forward return, rather than by backtested P&L. Their ablation shows IC moving sensibly (mean IC per category roughly doubling after filtering) where equity-curve metrics are noisy.

Why this matters here specifically: IC converges far faster than CAGR or Sharpe. S2 failed its gate on equity-curve metrics; IC would say *whether there is any signal at all* on the same data, with a usable answer from far fewer observations. Same for judging S3 breakout, which is trading demo money without having passed a gate.

`pandas` requires `scipy` for `method="spearman"`, so compute rank correlation without extra dependencies on aligned, unique-indexed finite pairs: `pairs = pd.concat([signal.rename("signal"), fwd_return.rename("return")], axis=1).replace([np.inf, -np.inf], np.nan).dropna(); ic = pairs["signal"].rank(method="average").corr(pairs["return"].rank(method="average"))` (returning `NaN` / undefined if fewer than 2 valid pairs remain or either series is constant). Add it to `metrics()` in [backtest.py:179](../src/tradebot/backtest.py) per strategy and per instrument, alongside the existing `sharpe_se`.

### 3.3 From P1 — give the jurors different risk stances

P1's risk team deliberates from three explicit angles — risk-seeking, neutral, risk-conservative — before a fund manager decides. That is a cheaper version of the bull/bear debate rounds [08 §3](08-multi-agent-llm.md#3-pipeline-per-entry-intent) deliberately deferred.

Right now all five jurors get "the same versioned prompt and the same context", which maximises *correlated* answers; provider diversity decorrelates the failures but not the framing. Assigning three of the five a risk stance in the prompt costs **nothing** — same five calls, same $0.18, same median-over-quorum aggregator, no extra round trips, no LLM chair. It just stops the quorum from being five models asked to think the same way.

Treat it as a prompt variant to run through the offline eval set before it affects anything, and keep it out of the P2 gate comparison unless it is measured.

Also worth keeping from P1: it confirms the **structured-document** choice. The paper adopts structured reports between agents specifically to stop the "telephone effect" of natural-language relay — the same reason [08 §8](08-multi-agent-llm.md#8-safety-specifics-for-multi-agent) quarantines raw text behind enums. Independent arrival at the same design.

And one budget data point: P1 burns **11 LLM calls and 20+ tool calls per prediction**, which is exactly why the authors could only afford a 3-month backtest. Our 6 calls per entry at ≈ $0.18 is already an order of magnitude leaner, and the €10 / €15 budget guards are the reason we won't end up with a 3-month evaluation window either.

## 4. Not worth building

| Idea | From | Why not |
|---|---|---|
| Hierarchical RL stack (4 base → 2 meta → 1 super) | P2 | Three layers of agents to choose 6 ETF weights, against a €1,000 cap, on a CPU laptop. RL also needs far more data than 14 monthly series × 15 years; P2 reports medians over 5 seeds, which hides the variance that matters. Inverse-vol weighting ([03 S1](03-strategies.md#s1-trend-filter-on-ucits-etfs-time-series-momentum)) is one line and has a century of evidence behind it. |
| LLM-generated alpha factors | P3 | Post-publication decay (§2.3), plus it needs a factor-expression engine, an IC pipeline and a factor zoo we have no capital to exploit. The IC metric alone (§3.2) is the part with value. |
| 60 technical indicators fed to an LLM | P1 | Indicators and regime are computed by code here, on purpose. No LLM does arithmetic ([08 §3](08-multi-agent-llm.md#3-pipeline-per-entry-intent)). |
| Reddit / X sentiment | P1 | Noise at this horizon, and a wide prompt-injection surface, for a desk whose whole design is to minimise raw-text exposure. The allow-list in [08 §3.1](08-multi-agent-llm.md#31-news-and-event-sources-decided-2026-09-25) stays as it is. |
| MLP learning signal weights | P3 | Few parameters, round numbers, a written reason for each ([03 §1](03-strategies.md#1-ground-rules-for-the-prototype)). An opaque weight vector fitted on a few hundred observations is the overfitting this project is set up to avoid. |
| Multi-agent debate rounds | P1 | Deferred already, and §3.3 gets most of the decorrelation benefit for no extra calls. Revisit only if the jury shows value at the P2 gate. |
| HFTENGINE (from the same post) | — | Intraday market making. Ruled out explicitly in [03 §2](03-strategies.md#2-strategy-families-surveyed); we trade daily bars and don't enter a speed race. Worth opening to look at, not to build on. |

## 5. What the papers say about this project's method

Read together, the three papers calibrate in the opposite direction from the one the post intends. Every methodological control this repo already has — a holdout run once, costs in the model, a random-entry control group, forward-only evaluation of anything an LLM touches, contexts dated after the model cutoff, Sharpe reported with its standard error — is **absent from at least two of the three papers**, and those absences are what produces their headline numbers.

So: take the three mechanisms in §3, keep the gates, and let none of these return figures set an expectation. The P2 gate's framing stands unchanged — "the LLMs don't help" remains a valid research result.

## Sources

- TradingAgents — [arXiv 2412.20138](https://arxiv.org/abs/2412.20138) · [code](https://github.com/TauricResearch/TradingAgents)
- HARLF — [arXiv 2507.18560](https://arxiv.org/abs/2507.18560) · [code](https://github.com/franjgs/llm-rl-finance-trader) · [FinBERT](https://github.com/ProsusAI/finBERT)
- Automate Strategy Finding with LLM — [arXiv 2409.06289](https://arxiv.org/abs/2409.06289) · [code](https://github.com/kouzhizhuo/Automate-Strategy-Finding-with-LLM-in-Quant-investment)
- HFTENGINE — [repo](https://github.com/mirkovicdev/HFTENGINE)
- McLean & Pontiff (2016), as cited in [03](03-strategies.md#references)
