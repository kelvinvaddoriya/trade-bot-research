# 02 — Approaches to an automated trading agent

## 1. What "agent" means in this project

The trading agent is the whole loop, not just the LLM:

**perceive** (market data, positions) → **decide** (signal) → **check** (risk) → **act** (order) → **record & review** (journal, reports)

An LLM could sit at several points in that loop. This doc answers two questions: **which component makes the trade decision, and what is the LLM allowed to do?**

## 2. Candidate approaches

### A. Rule-based systematic

Hand-written, deterministic rules on prices and indicators, e.g. "hold while the close is above the 200-day average".

- **+** Fully backtestable, deterministic, auditable, cheap and fast. Decades of research back a few robust families (trend, momentum, mean reversion).
- **−** The edges are small and widely known. Parameters are easy to overfit. The rules ignore news and context. Recent empirical studies document heavy post-publication decay and cost erosion in high-turnover equity anomalies (Chen & Velikov 2023; Detzel, Novy-Marx & Velikov 2023) and post-2009 decay in short-term futures trend signals on small-tick contracts (Kurth et al. 2026), favouring slower horizons — though viability at our €1,000 cap must still be proven in our own backtests and forward checks.

### B. Supervised ML prediction

Features (returns, volatility, volume, fundamentals) feed a model (gradient boosting, linear, neural net) that predicts the next period's return or direction. The bot trades on the predictions.

- **+** Can combine many weak signals.
- **−** Financial data is short, noisy and keeps changing character, so overfitting is the default outcome. It needs purged and embargoed cross-validation, large samples and disciplined feature engineering. Individual trades are harder to explain.

### C. Reinforcement learning

An agent learns a trading policy by trading inside a simulator.

- **+** Optimises the whole decision, including sizing and timing.
- **−** Needs huge numbers of samples, games its reward, and suffers a big gap between simulation and reality: the simulator's fills are the only world the policy knows. Research-grade; not for a first system.

### D. LLM-as-trader

An LLM decides BUY/SELL/HOLD directly from prices, news and filings. It can work alone or as a team of role-playing agents, e.g. TradingAgents with analysts, researchers, a trader and a risk manager.

- **+** Uses unstructured information and explains itself in natural language.
- **−** **It cannot be honestly backtested.** The model's training data already contains the "future" of any historical test period (look-ahead leakage), so any backtest before the model's training cutoff is inflated.
- **−** It is non-deterministic and changes behaviour between model versions. Each decision costs money and takes seconds.
- **−** It opens a prompt-injection path: news text can steer orders.
- **−** Published results cover short windows and are hard to reproduce. A 2026 reproducibility study of LLM trading papers found hidden execution assumptions (perfect fills, zero latency) and training-cutoff leakage.
- **−** Live evidence is mixed. In Nof1's Alpha Arena (Oct–Nov 2025), six LLMs traded $10,000 each of real money autonomously. Two finished ahead, and four lost money, some more than 60 %. Results depended heavily on which model was trading.

### E. Hybrid: deterministic core, bounded LLM (**chosen**)

Deterministic strategies (A) make every trade decision. The LLM layer is a **multi-agent desk** ([08](08-multi-agent-llm.md)): a news analyst plus five juror models from five labs (three paid, two open-weight), combined by a code aggregator. It has three jobs:

1. **Review** each proposed *entry* using context the rules can't see (news, earnings dates, unusual moves), and return `approve | reduce | veto` by majority. It can only shrink risk.
2. **Explain and report:** a daily summary, the reasoning behind each decision, and plain-language notes on anomalies for the operator.
3. **Research offline** (approach F), never at runtime.

- **+** The core stays backtestable, and the desk's value, and each model's, can be measured going forward (shadow books, see [06 §6](06-backtesting.md#6-evaluating-the-llm-desk-forward-only)).
- **+** A wrong, hallucinated or injected LLM output can at worst cause a missed or smaller trade.
- **−** In theory the LLM adds less upside here than in D. We accept that trade-off.

### F. LLM as offline strategy researcher

Coding agents (Codex, Claude Code) write new strategy code or variants. Each goes through human review, unit tests, the backtest gate ([06](06-backtesting.md)) and then demo trading. This is where the PRD's "Codex generates signal logic" belongs: at development time, through a PR. The bot never generates and runs code at runtime.

## 3. Comparison

| Criterion | A Rules | B ML | C RL | D LLM-trader | **E Hybrid** |
|---|---|---|---|---|---|
| Honest backtest possible | ✅ | ⚠️ with care | ⚠️ simulator only | ❌ leakage | ✅ core; LLM measured going forward only |
| Deterministic / reproducible | ✅ | ✅ (fixed model) | ⚠️ | ❌ | ✅ core |
| Explainability | ✅ | ⚠️ | ❌ | ✅ (narrative, unverified) | ✅ |
| Uses news / unstructured data | ❌ | ⚠️ | ❌ | ✅ | ✅ (veto/reduce only) |
| Data needed | Low | High | Very high | Low | Low |
| Runtime cost | ~0 | ~0 | ~0 | High per decision | Low (a few calls/day) |
| Damage one component bug can do | One strategy | The model | The policy | **Every order** | Capped by reduce-only |
| Engineering effort | Low | Medium–high | High | Medium | Medium |

## 4. Design rules that follow

1. **The LLM never talks to the broker** and holds no credentials. It has no tools that can act. It only returns a schema-validated JSON review.
2. **Reduce-only:** final size = strategy size × multiplier, where the multiplier is between 0 and 1. Nothing the LLM says can enlarge an order, add a symbol, or open a position the strategy didn't propose.
3. **Exits are never blocked.** Stop-losses and strategy exits skip the LLM entirely.
4. **Entries fail closed:** if the LLM times out, errors, refuses or returns invalid output, no new entry is made (configurable per phase).
5. **Everything is logged:** model id, prompt version, full input, full output, latency and cost.
6. **The LLM must prove its value going forward.** Shadow books ([06 §6](06-backtesting.md#6-evaluating-the-llm-desk-forward-only)) run before the desk ever affects a real order.
7. **No single model decides.** The desk's verdict is a quorum and median over five independent jurors, computed by code ([08 §3](08-multi-agent-llm.md#3-pipeline-per-entry-intent)).

## 5. Autonomy ladder

| Level | Who decides | Who executes | Used in |
|---|---|---|---|
| L0 Advisory | Bot proposes | Human, manually | — (optional) |
| L1 Shadow | Bot decides | Nobody: orders are simulated and journaled | P1 |
| L2 Demo | Bot decides | Broker demo account (Trading 212 practice, €1,000 cap) | P1–P2 |
| L3 Gated live | Bot proposes, **human approves each order** | Broker live, micro capital | P3 |
| L4 Bounded autonomy | Bot decides; human approves only orders above thresholds or in new instruments | Broker live | P4 |

Moving up a level requires passing the gates in [06 §7](06-backtesting.md#7-promotion-gates).

## References

- Xiao et al. (2024). *TradingAgents: Multi-Agents LLM Financial Trading Framework.* [arXiv:2412.20138](https://arxiv.org/abs/2412.20138) · [repo](https://github.com/tauricresearch/tradingagents)
- *Beyond Agent Architecture: Execution Assumptions and Reproducibility in LLM-Based Trading Systems* (2026). [arXiv:2606.08285](https://arxiv.org/abs/2606.08285)
- *Agentic Quantitative Trading: A Survey of Workflows, Systems, and Evaluation* (2026). [arXiv:2608.31041](https://arxiv.org/abs/2608.31041)
- *Agentic Trading: When LLM Agents Meet Financial Markets* (2026). [arXiv:2605.19337](https://arxiv.org/abs/2605.19337)
- López de Prado (2018). *Advances in Financial Machine Learning.* Wiley. Covers purged cross-validation and backtest overfitting.
- Nof1 Alpha Arena, Season 1 (Oct–Nov 2025): [results summary](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/) · [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/)
- Chen, Velikov (2023). *Zeroing in on the Expected Returns of Anomalies.* *JFQA* (working paper [FEDS 2020-039](https://doi.org/10.17016/feds.2020.039), metadata/summary checked 2026-11-25; full text UNVERIFIED).
- Detzel, Novy-Marx, Velikov (2023). *Model Comparison with Transaction Costs.* *Journal of Finance* 78(3), pp. 1743–1775 ([doi:10.1111/jofi.13225](https://doi.org/10.1111/jofi.13225), metadata/summary checked 2026-11-25; full text UNVERIFIED).
- Kurth, Eisler, Rej, Bouchaud (2026). *Is Trend Still Your Friend?: A Microstructural Account of the Demise of Short-Term Trend-Following.* [arXiv:2607.01550](https://arxiv.org/abs/2607.01550) (abstract checked 2026-11-25; full PDF UNVERIFIED).
- Sepp, Lucic (2026). *The Science and Practice of Trend-Following Systems.* [arXiv:2607.19497](https://arxiv.org/abs/2607.19497) (abstract checked 2026-11-25; full PDF UNVERIFIED).
- Moskowitz, Sabbatucci, Tamoni, Uhl (2025). *Nonlinear Time Series Momentum.* [SSRN 5933974](https://doi.org/10.2139/ssrn.5933974) (metadata/summary checked 2026-11-25; full text UNVERIFIED).
- López de Prado, Lipton, Zoonekynd (2025/2026). *How to Use the Sharpe Ratio.* *Journal of Portfolio Management* / [SSRN 5520741](https://doi.org/10.2139/ssrn.5520741) (metadata/summary checked 2026-11-25; full text UNVERIFIED).
