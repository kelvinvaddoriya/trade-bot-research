# 03 — Strategies

> This is research, not advice. Published edges shrink after publication: McLean & Pontiff (2016) estimate returns about 58 % lower post-publication. Every rule below must earn its place in our own backtest with costs included ([06](06-backtesting.md)), and then in forward demo trading.

## 1. Ground rules for the prototype

- **€1,000 capital cap** in both demo and live. Sizing uses `min(broker equity, €1,000)`.
- Long-only cash account: no leverage, no short selling, no options, no derivatives, no crypto.
- Instruments: liquid US and EU (Xetra) large caps, plus **UCITS ETFs**. US-listed ETFs are unavailable to EU retail clients ([01 §1](01-platforms.md#1-what-being-in-germany-changes)).
- Fractional shares (Trading 212), so small positions can still be sized precisely.
- Daily bars. Signals are computed on the completed daily bar of each instrument's home exchange, and orders execute at the next session's open. With no intraday data there is no speed race, operations stay simple, and backtests stay honest.
- Every position has a protective stop resting at the broker.
- Few parameters, round numbers, and a written reason for each one.

At this size a good year earns tens of euros. The prototype is judged on process quality: correct signals, controlled risk, and live results that match the backtest. It is not judged on euros made.

## 2. Strategy families surveyed

| Family | Core idea | Horizon | Evidence | Main risks | Prototype fit |
|---|---|---|---|---|---|
| Time-series trend / momentum | Hold assets whose own past return (or price vs moving average) is positive | Weeks–months | Strong, across asset classes, over a century of data (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017; Faber 2007) | Whipsaws in sideways markets; lags at turning points | ✅ **S1** |
| Cross-sectional momentum | Buy recent winners and avoid losers within a universe | 3–12 months | Strong (Jegadeesh & Titman 1993) | Momentum crashes; needs a broad universe | ⚠️ later (needs more capital and a bigger universe) |
| Short-term mean reversion | Buy sharp short pullbacks in an uptrend, sell the bounce | 2–10 days | Widely published for equity indices and large caps (e.g. Connors & Alvarez 2008); weaker since | Catching falling knives; gap risk; costs matter at high turnover | ✅ **S2** (the PRD's idea, refined) |
| Breakout (Donchian channel) | Buy N-day highs, exit on M-day lows | Weeks | Classic CTA / "turtle" rule; works mainly on trending assets | Many small losses, few large wins | ⚠️ later, on stocks (crypto is out of scope) |
| Pairs / statistical arbitrage | Trade the spread between two cointegrated assets | Days–weeks | Documented (Gatev, Goetzmann & Rouwenhorst 2006), weaker since | Needs shorting; relationships break | ❌ needs shorting |
| Factor investing (value, quality, low-vol) | Tilt toward stocks with those traits | Months–years | Strong but slow, with long stretches of underperformance | Too slow to evaluate in a prototype | ❌ |
| Event / news-driven | React to earnings, news, filings | Hours–days | Mixed; the edge fades quickly | Speed, data costs, **prompt injection** | 🔬 **R1**: the LLM desk as a reduce-only overlay, measured going forward only |
| ML return prediction | A model predicts next returns | Any | Mostly overfit in retail setups | Overfitting, leakage | 🔬 later research track |
| Options premium selling | Sell volatility | Days–weeks | A volatility risk premium exists | Rare large losses dwarf the gains | ❌ |
| Market making / HFT / arbitrage | Capture the spread or speed advantages | Milliseconds–seconds | Real, for institutions | Infrastructure and speed race that a retail bot loses | ❌ |
| Grid / martingale / averaging-down bots | Add to losing positions, harvest ranges | Any | Marketing, not evidence | Unlimited losses in a trend | ❌ banned by the risk rules |

## 3. Selected strategy specifications

The defaults below are starting points for the backtest, not tuned values. The parameter ranges are for robustness checks ([06 §2.5](06-backtesting.md#25-robustness)), not for picking the best-looking number. The tickers are examples: confirm the ISIN and Trading 212 availability of each before it goes on the whitelist.

### S1: Trend filter on UCITS ETFs (time-series momentum)

| Item | Spec |
|---|---|
| Budget | 60 % of the cap (€600) |
| Universe (Xetra, UCITS) | `SXR8` iShares Core S&P 500 · `SXRV` iShares Nasdaq 100 · `EXW1` iShares Core EURO STOXX 50 · `IS3N` iShares Core MSCI EM IMI · `EUNH` iShares Core Euro Government Bond · `4GLD` Xetra-Gold (an ETC) |
| Signal | `in_trend = close > SMA(close, 200)`, checked on the last trading day of each **month** (weekly in the robustness test) |
| Entry | Instrument becomes `in_trend` → buy at next open |
| Exit | Instrument no longer `in_trend` at the monthly check → sell at next open; or the protective stop is hit |
| Protective stop | `entry − 3 × ATR(20)`, resting at the broker. Moved up at each check, never down. |
| Sizing | Inverse volatility within the budget: weight ∝ 1/σ20 (σ20 = 20-day standard deviation of daily returns), capped at 25 % of the cap per position (€250). Cash when nothing qualifies. |
| Max positions | 6 |
| Backtest history | Before each UCITS ETF existed, use a proxy: SPY/QQQ/EEM/IEF/GLD or the index, converted to EUR |
| Robustness ranges | SMA 150–250; monthly vs weekly check; ATR multiple 2–4 |
| Benchmarks | Equal-weight buy-and-hold of the same six; 60/40 SXR8/EUNH |
| Expected behaviour | Very few trades (a handful per quarter); smaller drawdowns than buy-and-hold; lags in V-shaped recoveries |
| Why first | Robust, low turnover and simple, so it's ideal for proving the pipeline end to end |

### S2: Pullback in an uptrend (mean reversion), US + EU large caps

This refines the PRD's Bollinger idea: it keeps the trend filter, makes exits volatility-aware, and adds a time stop.

| Item | Spec |
|---|---|
| Budget | 40 % of the cap (€400) |
| Universe | US: `AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, XOM` · Xetra: `SAP, SIE, ALV, DTE, MUV2, BMW` (whitelist in config) |
| Filter | `close > SMA(200)` (long-term uptrend) |
| Entry signal | `RSI(2) < 10` **or** `close < BollingerLower(20, 2σ)`. A config switch picks the variant, and both are backtested. |
| Entry | Next open on the instrument's home exchange |
| Exit (whichever comes first) | `close > SMA(5)` → sell at next open · time stop after 10 trading days · protective stop |
| Protective stop | `entry − 2.5 × ATR(14)`, resting at the broker |
| Sizing | Risk-based: risk 0.5 % of the cap (€5) between entry and stop, so `qty = 5 / (entry − stop)` (fractional), capped at €200 per position |
| Max positions | 3. If there are more signals than slots, take the lowest RSI(2) first. |
| Robustness ranges | RSI threshold 5–15; exit SMA 3–10; time stop 5–15 days; ATR multiple 2–3.5 |
| Benchmarks | Buy-and-hold of an equal-weight basket of the universe; S2 with random entry days and the same holding time |
| Expected behaviour | Many small wins and occasional larger losses. Roughly 8–12 entries a month across both markets, so it's the fastest to validate going forward. |
| Known failure | Crashes that start inside an uptrend, before the filter reacts. The stop and the daily loss limit cover this. Earnings gaps are the LLM desk's job (R1). |

### R1: LLM desk overlay (research, measured going forward only)

This is not a strategy. It is the multi-model LLM desk ([08](08-multi-agent-llm.md)) reviewing **S2** entries against recent news and scheduled earnings. S1 entries skip it, because UCITS ETFs have no company news or earnings. It can only shrink or veto an entry. It can only be evaluated with the shadow A/B test ([06 §6](06-backtesting.md#6-evaluating-the-llm-desk-forward-only)), because it cannot be honestly backtested.

## 4. Portfolio construction

- Each strategy has its own **budget** (S1 €600, S2 €400) and its own book in the journal, so P&L can be attributed to it.
- If two strategies hold the same instrument, our ledger records two lots while the broker shows one net position. The ledger tracks lots per strategy, and reconciliation compares the net.
- The risk engine's global caps ([05 §2](05-risk-and-safety.md#2-limits)) apply on top: capital deployed ≤ €1,000, at most 9 positions, and at most €250 per position.
- Cash stays in EUR. USD for US stocks is converted per trade (Trading 212's 0.15 % FX fee), and that fee is part of the cost model.

## 5. Costs and minimum order size

Round-trip costs must be small compared with the average trade's expected gain (S2 aims for about 1–3 % per trade).

For a fixed per-order fee `F` and a cost budget `c` per side:

`min_order = F / c`

| Venue / instrument | Fee per side | Effective at €200 order |
|---|---|---|
| Trading 212, EU stock / UCITS ETF | €0 + spread | ~0.05–0.10 % |
| Trading 212, US stock | 0.15 % FX + spread | ~0.20 % |
| IBKR, Xetra (fallback) | max(€1.25, 0.05 %) | ~0.63 % |
| Trade Republic | €1 | 0.50 % |

With a fixed fee and a 0.25 % budget per side, the minimum sensible order is €400–500. That's why a fixed-fee venue doesn't fit a €1,000 cap. The risk engine also rejects orders under **€20** (dust), and the PRD's €10 orders fall below that floor.

## References

- Moskowitz, Ooi, Pedersen (2012). Time series momentum. *Journal of Financial Economics* 104(2).
- Hurst, Ooi, Pedersen (2017). A century of evidence on trend-following investing. *Journal of Portfolio Management* 44(1).
- Faber (2007). A quantitative approach to tactical asset allocation. *Journal of Wealth Management* 9(4).
- Jegadeesh, Titman (1993). Returns to buying winners and selling losers. *Journal of Finance* 48(1).
- Connors, Alvarez (2008). *Short Term Trading Strategies That Work.* TradingMarkets.
- Gatev, Goetzmann, Rouwenhorst (2006). Pairs trading. *Review of Financial Studies* 19(3).
- McLean, Pontiff (2016). Does academic research destroy stock return predictability? *Journal of Finance* 71(1).
- Barber, Odean (2000). Trading is hazardous to your wealth. *Journal of Finance* 55(2).
