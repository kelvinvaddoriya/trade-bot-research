# 01 — Platforms, brokers & market data

**Question:** where do orders go, and where does the data come from?
**Owner context (decided 2026-09-24):** tax resident in Germany. Trades US and EU stocks and ETFs. Demo money first, with a hard cap of **€1,000** in both the demo and any later real-money phase. The facts below were checked in **September 2026**. Re-check anything marked *(verify)* before P3.

## 1. What being in Germany changes

1. **No US-listed ETFs.** EU retail clients can't buy US-domiciled ETFs (SPY, QQQ, …). Those funds publish no PRIIPs Key Information Document, so every EU broker blocks them (IBKR, Trading 212, Trade Republic, Scalable). ETF exposure therefore uses **UCITS ETFs** listed in Europe, mostly on Xetra. US *single stocks* are fine.
2. **Fees dominate at €1,000.** Positions will be €50–250. A €1–1.25 minimum fee costs 0.4–2 % per side at that size, so zero commission and fractional shares matter more than anything else.
3. **Tax handling depends on the broker.** German banks (Scalable, Trade Republic) withhold Abgeltungsteuer automatically, and so has **Trading 212 since January 2026**. IBKR doesn't, so gains there go on Anlage KAP in the tax return. See [05 §12](05-risk-and-safety.md#12-legal-regulatory-tax-not-legal-advice).

## 2. Selection criteria

Hard requirements for any venue the bot talks to:

1. **An official, documented API** that the broker allows for automated trading. Reverse-engineered private APIs are out.
2. **A demo / paper environment** with the same API as live.
3. **Order lifecycle visibility:** status, fills and cancels.
4. **Stop orders held at the broker**, so positions stay protected if the bot dies.
5. **US stocks, EU stocks and UCITS ETFs** in one account.

Strongly preferred at €1,000: zero or near-zero commission, fractional shares, and a demo that anyone can open.

## 3. Comparison for a German resident

| Venue | Official API | Demo | US stocks / EU stocks / UCITS ETFs | Fractional | Cost at €1,000 scale | Tax | Verdict |
|---|---|---|---|---|---|---|---|
| **Trading 212** | Yes: REST (beta). Live supports market, limit, stop, stop-limit | Free practice account, same API | ✅ / ✅ / ✅ | ✅ incl. on limit and stop orders | €0 commission; 0.15 % FX fee each way on USD stocks | **Withheld** automatically since Jan 2026 | **Primary venue, demo → live** |
| **Interactive Brokers** | Yes: TWS API / Client Portal Web API; all order types | Paper account, needs an approved, funded live account ($0 minimum for cash accounts) | ✅ / ✅ / ✅ | Limited *(verify for API)* | Xetra ≈ €1.25 minimum per order → ~0.5 % per side on a €250 order; US about $0.35–1 minimum | Not withheld → self-report | **Fallback** if Trading 212's beta API falls short |
| **Scalable Capital** Agentic Investing | Yes: official MCP server + CLI (launched 2026-08-25) | Not documented *(verify)* | ✅ / ✅ / ✅ (US stocks traded in EUR on German venues) | *(verify for orders)* | Plan-dependent: per-trade fee or flat monthly plan | **Withheld** (German bank) | Watch. Every order needs confirmation in the app, which only suits the approve-every-order phase |
| **Trade Republic** | No (`pytr` reverse-engineers it) | No | ✅ / ✅ / ✅ | ✅ | €1 per order | Withheld | **Rejected for automation**; fine for the owner's manual investing |
| **Alpaca** | Yes | Free paper account for anyone | US only; US ETFs blocked for EU retail | ✅ | — | — | **Not a venue.** Kept as a free source of US market data (§6) |
| Saxo | Yes: OpenAPI | SIM | ✅ / ✅ / ✅ | ❌ | High minimum fees | Not withheld | Excluded on cost |
| CFD brokers, MT5, OANDA, crypto exchanges, lemon.markets | — | — | — | — | — | — | Out of scope: leverage products, crypto excluded by owner, no access for individuals |

## 4. Venue notes

### 4.1 Trading 212: primary venue

- Official REST API (beta). Demo base URL: `https://demo.trading212.com/api/v0`; live: `https://live.trading212.com/api/v0`. Invest accounts only (plus UK ISA).
- **Access:** the key and secret are created in the app (Settings → API). The key's **permissions are chosen at creation** (account data, portfolio, orders, …) and can optionally be **restricted to given IP addresses**. Requests use HTTP Basic auth with `key:secret`. The API has no endpoints for deposits or withdrawals.
- **Orders:** `POST /equity/orders/{market|limit|stop|stop_limit}`, `DELETE /equity/orders/{id}`, `GET /equity/orders` and `/equity/orders/{id}`. Quantity is positive to buy, negative to sell; fractional quantities are accepted, and value-based orders aren't. `timeValidity` is `DAY` or `GOOD_TILL_CANCEL`. Stops trigger on the last traded price. Market orders take an `extendedHours` flag.
- **Order status values:** `LOCAL, UNCONFIRMED, CONFIRMED, NEW, CANCELLING, CANCELLED, PARTIALLY_FILLED, FILLED, REJECTED, REPLACING, REPLACED`.
- **Rate limits** (per endpoint; bursts allowed; `x-ratelimit-reset` header; HTTP 429 when exceeded):

  | Endpoint | Limit |
  |---|---|
  | Place limit / stop / stop-limit | 1 request / 2 s |
  | Place market; cancel | 50 / min |
  | List open orders | 1 / 5 s |
  | Get one order | 1 / s |
  | Account summary | 1 / 5 s |

- ⚠️ **No duplicate protection.** The docs warn that sending the same request twice may create two orders, and there's no client-supplied order reference. The execution service therefore never retries an order request blindly ([04 §4](04-architecture.md#4-core-data-contracts-sketch)).
- Since early 2026, live accepts **limit, stop and stop-limit** orders, not just market orders. So protective stops can rest at the broker as `GOOD_TILL_CANCEL`, and €1,000 can be split into precise fractional positions.
- One commission-free account covers US stocks, EU stocks and UCITS ETFs. USD stocks carry a 0.15 % FX fee each way.
- **Tax:** since 5 January 2026, Trading 212 withholds German capital-gains tax, solidarity surcharge and church tax automatically. Its German accounts run through a partnership with FXFlat, a German broker. Before P3, confirm the live account is on this setup and file a Freistellungsauftrag if the app offers one.
- **Constraints:**
  - The API is in beta: endpoints and rate limits change. The adapter honours the rate-limit headers, and adapter tests run against demo.
  - There's no historical price data in the API, so data comes from separate sources (§6).
  - Community reports say positions not opened through the API can't be closed through it. **The bot's account must hold only bot positions.** Keep manual investing elsewhere, e.g. the existing Trade Republic account.
  - The demo balance is far above €1,000. The engine sizes positions against `min(broker equity, €1,000 cap)` ([05 §2](05-risk-and-safety.md#2-limits)).
  - A few behaviours aren't documented and become P1 adapter tests ([07](07-roadmap.md#trading-212-api-facts-and-p1-adapter-tests)): whether limit/stop orders placed while the market is closed are queued, the minimum fractional step per instrument, and the ticker format of each whitelisted instrument.

### 4.2 Interactive Brokers: fallback

- The most complete official API: real paper account, historical data through the API, every order type.
- The problem is cost at this size. With a Xetra minimum of about €1.25 per order, a €250 position pays ~0.5 % per side (~1 % round trip), which eats a large part of S2's expected gain per trade.
- Operations: the IB Gateway (Java) must run constantly. IBKR forces a full re-login with 2FA once a week (Sunday around 01:00 ET), and the gateway restarts daily. IBC, or its 2026 Python replacement, can automate the daily restart. It needs a machine with ≥ 2 GB of free RAM.
- Switch to IBKR if Trading 212's beta API blocks something essential, or if capital grows until fees matter less.

### 4.3 Scalable Capital: watch

- A German bank, so tax is withheld automatically (the simplest tax situation). Official MCP server and a local CLI for AI assistants. According to Scalable's launch material, each order needs explicit confirmation in the app.
- It could fit P3, where a human approves every order anyway. Open questions: can our execution adapter script the CLI while confirmation stays in the app? Is there a sandbox?

### 4.4 Trade Republic: why the bot does not use it

- No public API. Every tool reverse-engineers the private WebSocket API behind TR's app. Automating it may breach TR's terms, the account can be restricted, and the protocol can change without notice.
- It charges €1 per order and has no sandbox, so every test would use real money.
- The owner can keep using it for manual investing, which also keeps manual holdings out of the bot's Trading 212 account.

## 5. Broker MCP servers: development only

Scalable and Alpaca ship official MCP servers, and community MCP servers exist for Trading 212. Any of them lets an LLM place orders directly. This design **forbids that at runtime**, because those orders would skip the risk engine, the journal and the kill switch. The only allowed use is read-only exploration during development. At runtime the only path to a broker is `Strategy → LLM desk → Risk engine → (Human gate) → Broker adapter`.

## 6. Market data (US + EU daily bars)

Trading 212's API provides no price history, so data comes from separate sources:

| Source | Coverage | Cost | Use |
|---|---|---|---|
| Alpaca Market Data | US stocks; official API; free tier (IEX real-time; SIP history from 2016) | Free (account without funding) | **US daily bars at runtime**; cross-check of Yahoo for US names |
| Yahoo chart API | Daily OHLC + adjusted close incl. `.DE` tickers, decades of history | Free, unofficial, personal-use terms, can break | **Research history for everything** (P0). EU runtime source to be decided before P1 ([10](10-build-log.md)) |
| ~~Stooq~~ | — | — | **Dropped 2026-09-25:** scripted downloads are now blocked by a JavaScript bot check |
| EODHD (or Twelve Data) | Global end-of-day incl. Xetra, adjusted | ~€20/month *(verify)* | Upgrade path if free EU data proves unreliable |
| Massive (formerly Polygon.io) | US | Free tier: 5 req/min, 2 years of end-of-day data | Cross-check |

Data rules:

- Compute signals on split- and dividend-adjusted prices. Size orders and set limit prices on raw prices.
- Store the raw download and the provider with every bar. Before trusting a source, cross-check a sample against a second one.
- **UCITS ETF histories are short** (most start 2009–2010). Research backtests use a long-history proxy (the US-listed twin or the index, converted to EUR) before the UCITS ETF existed. Demo and live trade the UCITS ETF. Each report states where the proxy was used.

## 7. Recommendation

| Phase | Venue | Data |
|---|---|---|
| P0 backtest | Internal simulator | Yahoo (all history), cross-checked against Alpaca (US); Frankfurter/ECB FX |
| P1–P2 demo | **Trading 212 practice account**, sized to the €1,000 cap | same |
| P3 live (owner decision) | **Trading 212 live**, €1,000 cap. Fallback: IBKR. Watch: Scalable | same, or a paid end-of-day source |

One adapter (`Trading212Broker`) serves demo and live; only the base URL and key change. `SimBroker` serves backtest and shadow mode.

## Sources

- EU access to US ETFs (PRIIPs/KID): [Banker on Wheels](https://www.bankeronwheels.com/kid-etf-registration-priips-ucits/) · [UCITS Income](https://ucitsincome.com/learn/why-cant-i-buy-us-etfs)
- Trading 212: [Public API docs](https://docs.trading212.com/api) · [orders & rate limits](https://docs.trading212.com/api/orders) · [quickstart (auth)](https://docs.trading212.com/api/section/general-information/quickstart) · [rate limiting](https://docs.trading212.com/api/section/rate-limiting/how-it-works) · [API environments](https://docs.trading212.com/api/section/general-information/api-environments) · [API update thread](https://community.trading212.com/t/trading-212-api-update/87988) · [fractions on limit/stop orders](https://community.trading212.com/t/introducing-fractions-on-limit-stop-and-stop-limit-orders/60877) · [API key help](https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key)
- Trading 212 German tax: [boerse.de announcement](https://www.boerse.de/nachrichten/GNW-News-Trading-212-bietet-ab-sofort-automatische-Steuerabfuehrung-in-Deutschland-an/38078968) · [broker-test.at](https://www.broker-test.at/news/trading-212-wird-in-deutschland-steuereinfach-und-verschaerft-den-wettbewerb/) · [rankia.de](https://rankia.de/trading-212-steuern/)
- IBKR: [API solutions](https://www.interactivebrokers.com/en/trading/ib-api.php) · [required minimums](https://www.interactivebrokers.com/en/accounts/required-minimums.php) · [EU stock commissions](https://www.interactivebrokers.ie/en/pricing/commissions-stocks-europe.php) · [IBC user guide (weekly re-auth)](https://github.com/IbcAlpha/IBC/blob/master/userguide.md) · [ibg-controller](https://github.com/code-hustler-ft3d/ibg-controller)
- Scalable Capital: [Agentic Investing](https://de.scalable.capital/en/agentic-investing) · [press release](https://de.scalable.capital/en/newsroom/scalable-agentic-investing) · [FAQ](https://help.scalable.capital/en/agentic-investing-aac939f8)
- Trade Republic: [pytr](https://github.com/nborrmann/pytr) · [API Tracker](https://apitracker.io/a/traderepublic)
- Alpaca: [countries](https://alpaca.markets/support/countries-alpaca-is-available) · [Trading API](https://docs.alpaca.markets/us/docs/trading-api) · [MCP server](https://github.com/alpacahq/alpaca-mcp-server)
- Saxo: [OpenAPI environments](https://www.developer.saxo/openapi/learn/environments)
- Massive (Polygon): [rename announcement](https://massive.com/blog/polygon-is-now-massive)
