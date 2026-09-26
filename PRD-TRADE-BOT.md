# PRD: Codex-Driven Trade Republic Trading System (TR‑Sentinel)

**Version:** 1.0  
**Status:** Draft  
**Author:** [Your Name]  
**Date:** 2026-09-10  

---

## 1. Executive Summary

**Goal:** Build an AI-assisted trading system that uses OpenAI Codex to generate and execute trading strategies on a user’s Trade Republic account, with the objective of generating positive returns.

**Core Constraint:** The system must operate under a **defense‑in‑depth guardrail architecture** that makes it impossible for the AI to execute unauthorized trades, exceed predefined risk limits, or continue operating after a kill‑switch is triggered. Profit is pursued only within strict, pre‑approved boundaries.

**Key Reality Check:** Trade Republic has **no official public API**. All automation relies on reverse‑engineered private APIs, which violates Trade Republic’s terms of service and carries a high risk of account suspension or permanent ban. This PRD is therefore framed as a **research and simulation project first**, with live trading as an optional, heavily gated phase.

---

## 2. Non‑Negotiable Guardrails (The “Do Not Go Rogue” Layer)

These controls are **mandatory** and must be implemented **before any live order can be placed**.

### 2.1 Hard‑Coded Capital Limits

| Limit | Value | Enforcement |
|---|---|---|
| **Maximum total capital deployed** | €100 (initial cap) | Hard‑coded in config; cannot be overridden by AI |
| **Maximum single order value** | €10 | Pre‑trade check; order rejected if exceeded |
| **Maximum daily loss** | €5 | Daily loss counter; trading halts for 24h when hit |
| **Maximum drawdown (from peak)** | 10% of deployed capital | Kill‑switch activates automatically |
| **Maximum open positions** | 3 | New orders blocked if limit reached |
| **Allowed instruments** | Whitelist: `{SAP, SIE, ALV, BMW, VOW3}` (German blue chips) | Orders for non‑whitelisted ISINs rejected |

### 2.2 Kill‑Switch Mechanisms

A **multi‑level kill‑switch** is required, inspired by ASIC’s proposed algorithmic trading rules and Bank of England guidance on autonomous AI.

- **Level 1 — Automatic (System‑Triggered):** Triggered by any breach of the hard limits above. The system immediately cancels all pending orders and stops trading.
- **Level 2 — Manual (Operator‑Triggered):** A physical button (or CLI command) that the user can press to instantly halt all trading activity.
- **Level 3 — Watchdog (Heartbeat):** A separate process that monitors the trading engine. If the engine does not send a heartbeat every 60 seconds, the watchdog cancels all orders and locks the system.
- **Sticky State:** Once triggered, the kill‑switch remains **sticky** until the user explicitly resets it with a manual confirmation step. It must survive system restarts (persisted to disk).

### 2.3 Order Validation Layer (Pre‑Trade Controls)

Every order must pass through a **SafeBroker‑style validation layer** before submission. This layer is **separate from the strategy code** and cannot be bypassed by the AI.

Checks include:
- **Notional value** ≤ €10
- **Asset** is in the whitelist
- **Order rate** ≤ 2 orders per minute (duplicate‑order suppression)
- **Price deviation** ≤ 5% from the latest cached price
- **Data staleness** ≤ 60 seconds (reject stale market data)
- **Position count** ≤ 3 open positions

### 2.4 Human‑in‑the‑Loop Gate

- **All order proposals** must be logged with a human‑readable rationale.
- **First 30 days** of live trading: Every single order requires **explicit human approval** before execution (e.g., via a Telegram/Slack confirmation prompt with a 5‑minute timeout).
- After 30 days of clean operation, the approval requirement can be relaxed to **only orders above €5** or **orders in new instruments**.

### 2.5 Codex‑Specific Restrictions

- **No direct network access** from Codex‑generated code. All API calls must go through a **mediated broker service** that enforces the guardrails.
- **No credential access:** Codex must never see the Trade Republic phone number, PIN, or session cookies. The authentication token is injected at runtime from a secure vault (e.g., environment variables or a local keyring).
- **No filesystem access** outside the project directory.
- **No shell execution** of arbitrary commands.
- **Prompt injection protection:** Any web‑sourced data (news, prices) must be sanitized and treated as untrusted. Codex must not follow instructions embedded in external content.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Human Operator                         │
│  (Approves orders, triggers manual kill-switch, monitors)   │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator (Python)                     │
│  - Reads market data (via mediated broker)                  │
│  - Calls Codex to generate strategy signals                 │
│  - Passes proposals to SafeBroker                           │
│  - Logs all decisions                                       │
└───────┬─────────────────────────────────────┬───────────────┘
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌─────────────────────────┐
│  SafeBroker       │               │  Codex (OpenAI API)     │
│  (Pre-trade       │               │  - Generates trade      │
│  validation)      │               │    signals              │
│  - Limits         │               │  - No direct broker     │
│  - Kill-switch    │               │    access               │
│  - Audit log      │               │  - Receives sanitized   │
└─────────┬─────────┘               │    market context only  │
          │                         └─────────────────────────┘
          ▼
┌───────────────────┐
│  Trade Republic   │
│  Private API      │
│  (Unofficial)     │
│  - pytr / SDK     │
└───────────────────┘
```

**Key Components:**
- **Mediated Broker:** A wrapper around `pytr` or `trade-republic-sdk` that only exposes methods allowed by SafeBroker. It handles authentication and session management.
- **SafeBroker:** The enforcement layer. All orders must pass through it. It persists risk state to a file (e.g., `.tr_sentinel_state.json`) and logs every decision to an append‑only journal.
- **Codex Integration:** Codex is called via the OpenAI API with a strict system prompt that defines its role, the available market data, and the constraints. It outputs a structured JSON signal (e.g., `{"action": "BUY", "isin": "DE0007164600", "reason": "..."}`). It never generates executable code that directly places orders.

---

## 4. Trading Strategy (Profit Objective)

**Core Principle:** The strategy must be **simple, transparent, and testable**. Complex AI‑generated strategies are harder to audit and more likely to exhibit unintended behavior.

**Proposed Baseline Strategy:**
- **Mean Reversion on Blue Chips:** Use a simple moving average (SMA) crossover with a Bollinger Band filter.
  - Buy signal: Price crosses below lower Bollinger Band (20‑period, 2σ) **and** SMA(50) > SMA(200) (trend filter).
  - Sell signal: Price crosses above SMA(20) or hits +5% profit target.
  - Stop‑loss: -3% per position.
- **Position Sizing:** Fixed €10 per trade (max 3 concurrent positions).
- **Frequency:** Maximum 2 trades per day.

**Role of Codex:**
- Codex generates the **signal logic** as Python functions, which are then reviewed and unit‑tested by the human operator before deployment.
- Codex also generates **daily market summaries** to inform the human operator, but does not directly decide trade parameters.

**Backtesting Requirement:**
- The strategy must be backtested on at least **2 years of historical data** before any live deployment.
- Backtest results must include Sharpe ratio, max drawdown, and win rate.

---

## 5. Development Phases

| Phase | Duration | Deliverable | Live Trading? |
|---|---|---|---|
| **P0 — Research & Setup** | 1 week | Trade Republic API library working in read‑only mode; Codex integration tested with dummy data | No |
| **P1 — Simulation** | 2 weeks | SafeBroker implemented; strategy backtested; paper‑trading mode (shadow execution) | No (shadow only) |
| **P2 — Gated Live (Approval Mode)** | 4 weeks | Live trading with human approval for every order; capital capped at €50 | Yes (approval required) |
| **P3 — Limited Autonomous** | 4 weeks | Human approval only for orders > €5; capital capped at €100 | Yes (limited) |
| **P4 — Review & Expand** | Ongoing | Weekly review of P&L, drawdown, and guardrail breaches; only then consider expanding limits | Yes (if profitable and clean) |

**Go/No‑Go Criteria for P2 → P3:**
- Zero guardrail breaches during P2.
- Positive P&L over 4 weeks.
- No unexplained orders or system anomalies.

---

## 6. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Trade Republic bans account** | High | Catastrophic | Use a separate, dedicated account with minimal funds; never automate the main account. |
| **API changes break automation** | High | High | Monitor pytr/SDK repositories for updates; have a manual fallback. |
| **Codex generates unintended orders** | Medium | High | SafeBroker validation; human approval gate in early phases. |
| **Prompt injection from market data** | Medium | High | Sanitize all external text; treat as untrusted. |
| **Runaway losses** | Low | High | Hard capital limits; daily loss limit; kill‑switch. |
| **Regulatory scrutiny (MiFID II / AI Act)** | Low (retail) | Medium | Retail algorithmic trading is generally outside MiFID II’s strictest requirements if not high‑frequency. Document compliance rationale. |

**Legal Disclaimer:** This project is for **personal, educational, and research purposes**. The user is solely responsible for compliance with Trade Republic’s terms of service and applicable financial regulations. The authors of this PRD do not endorse or encourage violations of any platform’s terms.

---

## 7. Success Metrics

- **Primary:** Positive risk‑adjusted return (Sharpe > 0.5) over a 3‑month period.
- **Secondary:** Zero guardrail breaches; zero unauthorized trades; kill‑switch never triggered by a breach.
- **Tertiary:** System uptime > 95% during market hours.

---

## 8. Appendices

### A. Trade Republic API Libraries (Unofficial)

| Library | Language | Key Features | Source |
|---|---|---|---|
| `pytr` | Python | Login, portfolio, price alarms, order placement (with caution) | GitHub / PyPI |
| `trade-republic-sdk` | TypeScript | Two‑step auth, REST, WebSocket, account info | npm |
| `trade-republic-api` | TypeScript | Login, WebSocket, session persistence | GitHub |

### B. Sample SafeBroker Config

```python
# config.py
MAX_TOTAL_CAPITAL = 100.0          # EUR
MAX_ORDER_VALUE = 10.0             # EUR
MAX_DAILY_LOSS = 5.0               # EUR
MAX_DRAWDOWN_PCT = 0.10            # 10%
MAX_POSITIONS = 3
ALLOWED_ISINS = {"DE0007164600", "DE0007236101", "DE0008404005"}
MAX_ORDERS_PER_MINUTE = 2
MAX_DATA_STALENESS_SECONDS = 60
KILL_SWITCH_ENABLED = True
EXECUTION_MODE = "shadow"          # "shadow", "paper", "live"
```

### C. Codex System Prompt (Excerpt)

```
You are a trading signal generator for a strictly limited retail account.
You MUST NOT generate code that places orders directly.
You MUST output only JSON signals in the format:
{"action": "BUY"|"SELL"|"HOLD", "isin": "...", "reason": "..."}
You MUST respect the following constraints:
- Never suggest an order > €10.
- Never suggest an instrument outside the whitelist.
- Never suggest more than 3 concurrent positions.
If you are unsure, output HOLD.
```

---

**End of PRD**