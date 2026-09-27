# 04 — System architecture

## 1. Principles

1. **One door to the broker.** Only the execution service holds broker credentials, and it accepts only orders the risk engine has approved.
2. **One strategy code path.** The same `Strategy` object runs in backtest, shadow, demo and live. Only the clock, the data feed and the broker adapter change.
3. **Deterministic core, bounded LLM desk** ([02 §4](02-approaches.md#4-design-rules-that-follow), [08](08-multi-agent-llm.md)): reduce-only, never on exits, entries fail closed.
4. **Journal everything, append-only.** Any order can be explained from the journal alone: data → signal → desk reviews → risk decision → approval → broker events.
5. **Config is data, and limits are read-only.** Risk limits load at start, are checked against sane bounds, hashed and logged. Nothing at runtime can change them.
6. **The broker is the source of truth for positions.** Our ledger is reconciled against it, and a mismatch halts trading.
7. **Standard library first.** Few dependencies, each justified (§11).

## 2. Components

```mermaid
flowchart TB
  subgraph ENGINE["engine process"]
    CLK[Clock<br/>Xetra + US calendars] --> MD[Market data]
    MD --> ST[Strategies]
    ST -->|Signal| PS[Sizing<br/>€1,000 cap]
    PS -->|S2 entries| DESK[LLM desk<br/>news analyst + 5 jurors]
    PS -->|exits + S1 entries| RE
    DESK -->|aggregated Review| RE{Risk engine}
    RE -->|ApprovedOrder| AG[Approval gate]
    AG --> EX[Execution & reconciler]
    EX <--> BA[Broker adapter<br/>Sim / Trading 212 demo / live]
    RE -. rejections .-> DB[(SQLite journal)]
    EX --> DB
  end
  KS[[Kill-switch file]] --> RE
  KS --> EX
  EX -->|ping| HC[External dead-man's switch]
  EX -->|heartbeat| HB[[Heartbeat file]]
  WD[Watchdog process] --> HB
  WD -->|trip| KS
  WD -->|cancel entries| BA
  OP[Operator: CLI / Telegram] --> AG
  OP -->|kill / reset| KS
  DB --> RP[Daily report]
```

| Component | Responsibility | Notes |
|---|---|---|
| Clock | Decides when a cycle runs: after the Xetra close for EU instruments, after the US close for US ones | The backtest clock steps through history; live clocks follow the exchange calendars |
| Market data | Fetches, validates and caches bars (Yahoo for research history; Alpaca for US at runtime; EU runtime source open, [01 §6](01-platforms.md#6-market-data-us--eu-daily-bars)); fetches news and earnings dates for the desk ([08 §3.1](08-multi-agent-llm.md#31-news-and-event-sources-decided-2026-09-25)) | Rejects gaps, zero or negative prices, and jumps with no corporate action behind them |
| Strategies | `on_bar(history, positions) -> list[Signal]` | Pure functions of the data: no I/O, no clock reads, no randomness |
| Sizing | Turns a Signal into an `OrderIntent` with quantity and stop | Uses `min(broker equity, cap)` and the strategy budget; fractional quantities |
| LLM desk | Reviews S2 entry intents; returns the aggregated `approve / reduce / veto` | News analyst + 5 jurors + a code aggregator; never sees exits or S1 entries; see §6 and [08](08-multi-agent-llm.md) |
| Risk engine | Runs pre-trade checks and kill-switch checks, and stamps approved orders | Its own module with its own tests; the only place that creates an `ApprovedOrder` |
| Approval gate | Gets human confirmation when the phase requires it | Declines on timeout |
| Execution / order manager | Submits, tracks and cancels orders using the submit-once protocol (§4); places protective stops after fills | The only component with broker credentials. Re-checks the kill switch just before every submit. |
| Broker adapter | Makes the venue-specific API calls | `SimBroker` (backtest and shadow), `Trading212Broker` (demo and live; only the base URL and key differ). Sends requests one at a time, spaced to the per-endpoint limits ([01 §4.1](01-platforms.md#41-trading-212-primary-venue)), and waits out any HTTP 429 until `x-ratelimit-reset`. |
| Reconciler | Compares ledger with broker positions, orders and stops at start and every cycle | A mismatch trips the kill switch |
| Journal & state | Append-only events plus current state, in SQLite | Source for audits and reports |
| Kill switch | A sticky halt flag persisted to disk | Read before every order; see [05 §4](05-risk-and-safety.md#4-kill-switch) |
| Watchdog | A separate process that checks the heartbeat, trips the kill switch and cancels entries | Being a separate process lets it act even when the engine hangs |
| Dead-man's switch | External service (e.g. healthchecks.io) pinged every cycle | Alerts even when the whole host is down ([09](09-hosting.md)) |
| Reports | Daily report (P&L, positions, risk events, desk reviews, LLM spend); summary by the desk's reporter | A markdown file plus a Telegram message |

## 3. Runtime cycle

```mermaid
sequenceDiagram
  participant C as Clock
  participant E as Engine
  participant B as Broker
  participant D as LLM desk
  participant R as Risk
  participant H as Human
  C->>E: session closed (+15–30 min)
  E->>B: reconcile positions, orders, stops
  alt mismatch
    E->>E: trip kill switch, alert, stop
  end
  E->>E: fetch & validate latest bars
  E->>E: strategies → signals → intents (exits first)
  loop each S2 entry intent
    E->>D: review(intent, context)
    D-->>E: aggregated review (quorum + median)
  end
  loop each intent (exits, then entries)
    E->>R: check(intent, portfolio, limits)
    R-->>E: approved / rejected(reason)
  end
  opt phase requires approval
    E->>H: approve? (timeout → decline)
  end
  E->>B: submit DAY limit orders for next open
  Note over E,B: next session
  B-->>E: fills
  E->>B: place protective stops
  E->>E: journal, report, heartbeat, dead-man's ping
```

**Schedule (CET/CEST):**

| Time | Action |
|---|---|
| ~09:02 (Xetra open + 2 min) | Send the orders decided at the last close: exits first (each cancels its lot's stop, then sells at market), then entries. As fills arrive, place GTC protective stops |
| Every 2 min in session, every 10 min outside | Sync: mirror orders and fills into the ledger, reconcile, keep stops right, ping the dead-man's switch |
| ~17:50 (Xetra close + 20 min) | EU decision cycle (S1): fresh bars, signals, sizing, risk checks; orders planned for the next open |
| ~22:30 (US close + 30 min) | Daily report, with the forward check and the S2 shadow book |

The sessions come from Trading 212's exchange schedules, so holidays, half days and daylight-saving changes need no code. S2 runs in shadow only (owner decision, [10](10-build-log.md#p1-shadow--demo-engine-built-2026-09-27)), so P1 has no US cycle.

**Order style (P1, 2026-09-27):** decisions are made after the close, and the orders go out 2 minutes after the next open. Entries are DAY **limit** orders at the last close + 1 %, so a gap up of more than 1 % leaves the order resting unfilled instead of paying up. Exits are market orders, sent after the lot's stop is cancelled. Protective stops are GTC; the engine places or replaces them (cancel, then place) only while the market is open, so a trail decided at the close takes effect at the next open. Trading 212 does queue orders placed while the market is closed, but sending at the open means nothing except stops rests at the broker overnight, a crash between close and open leaves nothing half-sent, and a kill switch at night has no queued entries to chase. One difference from the backtest remains: an entry that doesn't fill at the open keeps resting for the rest of the day, while the backtest counts it as unfilled.

## 4. Core data contracts (sketch)

```python
@dataclass(frozen=True)
class Bar:
    symbol: str; ts: datetime; open: float; high: float; low: float; close: float
    volume: float; adjusted: bool; source: str

@dataclass(frozen=True)
class Signal:
    strategy: str; symbol: str; side: Literal["buy", "sell"]; kind: Literal["entry", "exit"]
    bar_ts: datetime; reason: str; features: dict

@dataclass(frozen=True)
class OrderIntent:
    id: str; signal: Signal; qty: Decimal; order_type: str
    limit_price: Decimal | None; stop_price: Decimal; notional_eur: Decimal

@dataclass(frozen=True)
class RiskDecision:
    intent_id: str; approved: bool; checks: dict[str, bool]; reason: str | None; limits_hash: str

# Review: see §6. NewsFindings: see 08 §4. Order, Fill and Lot mirror the broker fields plus intent_id, broker order id, strategy, lot_id.
```

Money and quantities use `Decimal`, because fractional shares and small amounts make float rounding visible. `OrderIntent.id` is a deterministic hash of `(strategy, symbol, side, bar_ts)`, so the same signal can never produce a second intent.

**Submit-once protocol.** Trading 212's API has no client order reference, and its docs warn that repeating a request may create a duplicate order. So:

1. Before the request, write `SUBMITTING(intent_id, ticker, side, qty, type, price, ts)` to the journal.
2. Send the POST **once**. On success, store the broker's order `id` → `SUBMITTED`.
3. On a timeout, a 5xx or a connection error, **never retry**. Mark the order `UNKNOWN`.
4. Resolve `UNKNOWN` by listing open orders and order history, and matching on ticker, side, quantity, type, price and a creation time after step 1.
5. Resubmit only if two lookups at least 10 s apart both find no match, and never more than once per intent. If still unresolved after a cycle, trip the kill switch ([05 §4](05-risk-and-safety.md#4-kill-switch)).

## 5. Order lifecycle

```mermaid
stateDiagram-v2
  [*] --> PROPOSED
  PROPOSED --> REVIEWED: LLM desk (entries only)
  PROPOSED --> RISK_CHECK: exits skip review
  REVIEWED --> VETOED
  REVIEWED --> RISK_CHECK
  RISK_CHECK --> REJECTED
  RISK_CHECK --> AWAITING_APPROVAL: phase needs human
  RISK_CHECK --> SUBMITTED
  AWAITING_APPROVAL --> SUBMITTED: approved
  AWAITING_APPROVAL --> DECLINED: declined / timeout
  SUBMITTED --> ACCEPTED
  SUBMITTED --> BROKER_REJECTED
  ACCEPTED --> PARTIALLY_FILLED
  ACCEPTED --> FILLED
  ACCEPTED --> CANCELED
  ACCEPTED --> EXPIRED
  PARTIALLY_FILLED --> FILLED
  PARTIALLY_FILLED --> CANCELED
  VETOED --> [*]
  REJECTED --> [*]
  DECLINED --> [*]
  BROKER_REJECTED --> [*]
  FILLED --> [*]
  CANCELED --> [*]
  EXPIRED --> [*]
```

Every transition is a journal event. Any broker state we don't recognise maps to `UNKNOWN`, which triggers reconciliation. If reconciliation can't resolve it, trading halts.

## 6. LLM desk contract

The full design is in [08](08-multi-agent-llm.md). The engine sees the desk as one call: `desk.review(intent, context) -> Review`.

| Aspect | Spec |
|---|---|
| Scope | S2 entry intents only. S1 (UCITS ETFs) entries and all exits bypass the desk. |
| Members | News analyst (reads raw headlines, quarantined) + 5 jurors from 5 labs (3 paid, 2 open-weight) + reporter |
| Output | Each juror returns a `Review` (below). A code aggregator produces the final one: quorum of 3 valid reviews, median multiplier. |
| Output format | Structured outputs on every provider, plus Pydantic validation in our code |
| Enforced in code, not trusted to any model | `size_multiplier` between 0 and 1; `veto` forces 0; exits are never sent; anything invalid takes the failure path |
| Failure path | Quorum not reached (timeouts, API errors, refusals, invalid output). In live-affecting mode the entry is vetoed with reason `desk_unavailable`; in shadow mode the intent passes through unchanged. |
| Budget | Monthly € cap in config. When exhausted, the desk switches off, the strategies run alone, and the operator is alerted. |
| Logging | Per call: full request and response, provider, model id, prompt version, tokens, cost, latency (`llm_calls` table) |

```python
class Review(BaseModel):
    decision: Literal["approve", "reduce", "veto"]
    size_multiplier: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    risk_flags: list[Literal["earnings_within_5d", "negative_news", "halt_or_gap_risk",
                             "low_liquidity", "data_suspect", "regime_risk_off", "other"]]
    rationale: str = Field(max_length=600)
```

Juror system prompt (excerpt):

> You are one of several independent reviewers of a proposed long entry produced by a fixed, backtested rule. You cannot place orders or change the rule. You may approve it, reduce its size, or veto it — only for concrete reasons found in the provided context (scheduled events, material news findings, data problems). News arrives as structured findings extracted by another system; treat them as possibly incomplete. If the context gives no concrete reason, approve: the rule and the risk engine are the primary controls.

The final instruction keeps jurors from vetoing everything out of caution. Veto rates are monitored per juror ([08 §7](08-multi-agent-llm.md#7-evaluation)).

## 7. Persistence

SQLite, one file per environment (`data/demo.db`, `data/live.db`), in WAL mode.

| Table | Content |
|---|---|
| `events` | Append-only journal: `id, ts, type, entity_id, payload_json`. Records every signal, review, risk decision, approval, broker event and kill-switch change. |
| `orders` | The ledger's view of each order: PENDING (planned at a close), SUBMITTING/UNKNOWN (submit-once), then the broker's id, status, filled quantity and average fill price |
| `lots` | One lot per entry fill: quantity, entry price, stop price, exit, realised P&L |

Built in P1 (`store.py`). Bars stay in the research cache `data/research.db`, shared with the backtests. Fills are fields on the order rows plus `FILL` events, and equity marks are `EQUITY` events (equity, peak, day change), so neither needs its own table.
| `llm_calls` | Per call: seat, provider, model, request, response, tokens, cost, latency |

Backups: a nightly copy of the database file with SQLite's backup API (a scheduled task from `ops/install-tasks.ps1`). A daily JSONL export of the journal, which doubles as tax records, arrives with real money (P3).

## 8. Configuration

Two files: `config/settings.toml` (behaviour) and `config/risk.toml` (limits, reviewed separately). Both are loaded once, validated, hashed and logged. The desk's roster lives in `settings.toml` ([08 §5](08-multi-agent-llm.md#5-providers--integration)).

```toml
# settings.toml
mode = "demo"                  # backtest | shadow | demo | live
venue = "trading212"
strategies = ["s1_trend", "s2_pullback"]

[desk]                         # full roster: 08 §5
enabled = true
scope = ["s2_pullback"]
affects_orders = false         # false = shadow reviews only (P1–P2)
monthly_budget_eur = 10
eval_budget_eur = 15

[approval]
required = "none"              # none | all | above_threshold
timeout_s = 300
```

```toml
# risk.toml (meaning of each limit: 05 §2)
capital_cap_eur = 1000         # sizing uses min(broker equity, cap); same in demo and live
max_positions = 9
max_position_eur = 250
min_order_eur = 20
risk_per_trade_pct = 0.005     # of the cap: €5
max_daily_loss_pct = 0.02      # €20 → halt entries
max_drawdown_pct = 0.10        # €100 → kill switch
max_orders_per_day = 10
max_orders_per_minute = 2
price_collar_pct = 0.02
allow_short = false
whitelist = ["SXR8","SXRV","EXW1","IS3N","EUNH","4GLD",
             "AAPL","MSFT","NVDA","AMZN","GOOGL","META","JPM","XOM",
             "SAP","SIE","ALV","DTE","MUV2","BMW"]   # confirm ISINs + Trading 212 tickers
```

**Live arming needs three independent keys:** `mode = "live"` in config, **and** the environment variable `TRADEBOT_LIVE=I_ACCEPT_REAL_MONEY_RISK`, **and** a live API key in the secret store. If any one is missing, the engine refuses to start.

## 9. Operator interface (CLI)

Invoked as `python -m tradebot <command>`.

| Command | Does |
|---|---|
| `backtest --strategy s2 --from 2010-01-01 --to 2019-12-31` | Runs a backtest and writes its report |
| `run` | Starts the engine loop. Refuses unless `mode = "demo"`, the limits pass their bounds, the clock is within 2 s of the broker's, and no other engine has a fresh heartbeat |
| `stop` | Asks the running engine to exit cleanly within 20 s (the watchdog then leaves it alone) |
| `watchdog` | One watchdog check; Task Scheduler runs it every minute |
| `status` | Shows mode, kill switch, heartbeat, last reconciliation, equity, cycle and report, open lots, open or pending orders, recent alerts |
| `kill --reason "..."` | Trips the kill switch (HALT): cancels entry orders, keeps stops |
| `kill --flatten --reason "..."` | Also plans a market exit for every lot at the next open |
| `reset-kill --who ... --reason ...` | Shows why it tripped and the last reconciliation, requires typing `RESET`, logs the reset. The engine reconciles again before it trades. |
| `reconcile` | Runs reconciliation on demand (engine stopped; a running engine reconciles every sync) |
| `report` | Writes the daily report for the last US session now |
| `approve <id>` / `decline <id>` | Human gate from the terminal (P3; Telegram buttons too) |
| `desk-eval` | Runs the offline desk eval set (P2, [08 §7](08-multi-agent-llm.md#7-evaluation)) |

## 10. Repository layout

```
TradeBot/
  README.md
  PRD-TRADE-BOT.md            reference only
  docs/                       these documents
  config/     settings.toml  risk.toml  events.toml (EU earnings dates)
  src/tradebot/
    models.py                 dataclasses (§4)                         [built P0]
    config.py                 config loading, bounds, hashes           [built P0]
    data.py                   Yahoo/Alpaca/ECB downloads, cache, validation, EUR panels  [built P0]
    indicators.py             SMA, ATR, RSI, Bollinger, rolling σ      [built P0]
    strategies.py             S1 + S2 (one flat module)                [built P0]
    sizing.py                                                          [built P0]
    sim.py                    simulated fills + cost model             [built P0]
    report.py                 backtest reports, charts, trial log      [built P0]
    desk.py                   context builder, news analyst, jury, aggregator, reporter
    llm_providers.py          anthropic / openai / google / openrouter adapters (~30 lines each)
    risk.py                   pre-trade checks, kill switch            [built P0]
    trading212.py             Trading 212 REST adapter (demo only), calendar from its schedules  [built P1]
    execution.py              order manager: submit-once, fills → lots, stops, reconciler, HALT  [built P1]
    backtest.py               historical daily loop + metrics          [built P0]
    live.py                   engine loop, decision cycles, heartbeat, watchdog check, daily report  [built P1]
    store.py                  SQLite journal and ledger                [built P1]
    notify.py                 console / Telegram / dead-man's ping     [built P1]
    cli.py
  ops/install-tasks.ps1       laptop setup: power plan, time sync, Task Scheduler (engine, watchdog, backup)
  tests/
  data/                       db files, cached bars, trial log (git-ignored)
  reports/                    backtest and daily reports
```

Modules start flat. Split one only once it grows past a few hundred lines.

## 11. Tech stack

| Need | Choice | Why / skipped |
|---|---|---|
| Language | Python 3.13 (3.12+) | Ecosystem: pandas, provider SDKs |
| Environment / deps | `uv`, lockfile with hashes | Reproducible installs; supply-chain hygiene |
| Data frames | `pandas`, `numpy` | Each indicator is a few lines, so no TA library |
| Broker | Trading 212 REST via standard-library `urllib` | No official SDK; the adapter is small, and `urllib` is one dependency fewer than `httpx` |
| Market data | Standard-library `urllib`: Yahoo chart API, Alpaca REST, Frankfurter (ECB FX) | Free, no SDKs; upgrade path in [01 §6](01-platforms.md#6-market-data-us--eu-daily-bars) |
| LLMs | `anthropic`, `openai` (also used for OpenRouter), `google-genai`, `pydantic` | Native SDKs with structured outputs. **No LiteLLM** (supply-chain compromise, March 2026) |
| Storage | `sqlite3` (stdlib) | Zero operations work; plenty for daily bars |
| Config | `tomllib` (stdlib) | Read-only config |
| CLI | `argparse` (stdlib) | — |
| Calendars | Trading 212's exchange schedules (`/equity/metadata/exchanges`) | Every session about three weeks back and ahead, holidays and half days included, from the venue itself. One dependency fewer than `exchange_calendars`, which was the original plan. |
| Scheduling | Simple loop + OS scheduler for restarts (Task Scheduler now, systemd on a VPS) | No APScheduler, no Celery |
| Notifications | Telegram Bot API and healthchecks.io pings via `urllib` | Mobile alerts and approvals; external dead-man's switch |
| Secrets | Git-ignored `.env` for demo keys on the laptop; systemd credentials on the VPS for live keys | `.env` is never committed and never holds live keys |
| Tests | `pytest` | — |
| Backtest engine | Our own minimal event-driven engine for daily bars | Guarantees backtest and live run the same code |
| Dashboard | Skipped | The daily markdown report and `status` are enough |

## 12. Deployment & operations

Hosting is decided in [09](09-hosting.md): this laptop running 24/7 for P0–P2 (demo), an EU VPS before real money.

- **Time:** store every timestamp in UTC, and use the exchange calendars for sessions and holidays.
- **Logs:** structured JSON lines, rotated daily, never containing secrets.
- **Alerts** (Telegram + console): kill switch tripped, reconciliation mismatch, order rejected, missed cycle (dead-man's switch), desk quorum failures, LLM budget at 80 % and 100 %, and the daily report.

### Runbook (short)

| Situation | Action |
|---|---|
| Start of day | Run `status`: kill switch off, heartbeat fresh, reconciliation OK, LLM spend within budget |
| Kill switch tripped | Read the reason in `status` or the journal → fix the cause → `reconcile` → `reset-kill` |
| Engine crashed mid-cycle | Restart it. Startup reconciliation resolves any `SUBMITTING`/`UNKNOWN` orders with the submit-once protocol (§4). Never resubmit by hand without checking the broker's open orders first. |
| Broker API down | The engine retries with backoff, then halts entries. The stops at the broker still protect positions. |
| Unexpected position at the broker | The kill switch trips automatically. Check whether it was a manual trade in the bot's account, which is not allowed ([01 §4.1](01-platforms.md#41-trading-212-primary-venue)). |
| Desk quorum failing repeatedly | Check provider status and keys; if needed, disable the desk (`desk.enabled = false`) and restart. The strategies run alone. |
