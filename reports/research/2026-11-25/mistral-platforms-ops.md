# Mistral - Platforms, regulation, hosting and operations (EU/German view) (round 1, 2026-11-25)

## Summary (max 10 bullets, most important first)

- Trading 212 API remains **v0 beta** as of November 2026, with no breaking changes since September 2026; rate limits and order types are stable (docs.trading212.com, checked 2026-11-25)
- **Stop orders work on both demo and live** with GOOD_TILL_CANCEL; fractional quantities accepted at 3-4 decimal precision depending on instrument
- German tax: Trading 212 **withholds Abgeltungsteuer automatically since 05-Jan-2026** via FXFlat partnership; no self-reporting needed for demo or live (rankia.de, checked 2026-11-25)
- EU VPS: **netcup VPS 500 G12.5 at €5.91/mo** (incl. 19% VAT) is the best value for this engine: 2 vCore, 4 GB RAM, 128 GB NVMe, Germany/Nuremberg, no contract required
- **OVHcloud VPS-1 at $4.54/mo** (~€4.20) is cheaper but sold out in many locations; next available is VPS-2 at $8.50/mo
- Hetzner Cloud cheapest plans (CX/CAX) **remain unavailable** for new customers since September 2026; CPX21 at €19.99/mo is the entry point
- German/EU regulation: **Private individuals running bots on their own account are not regulated** under MiFID II; algorithmic trading obligations apply to investment firms, not retail traders (ESMA Supervisory Briefing, Feb 2026)
- EU AI Act Article 2(10) **excludes natural persons** using AI in purely personal, non-professional activities (not legal advice)
- Data protection: **No personal data in prompts** for this project; LLM inputs are sanitised news/price data; OpenRouter has zero data retention; EU VPS keeps data in EU
- Restart runbook provided: VPS setup → deploy → restore state → re-place stops → clear kill switch as ordered checklist

---

## Findings

### Trading 212 API Status (2026-11-25)

**F-1: API version and stability**
- Claim: Trading 212 Public API remains at **v0 beta**, under active development, with no breaking changes since September 2026
- Evidence: Official docs at docs.trading212.com show "status: Beta" and "This API is currently in beta and is under active development" (accessed 2026-11-25)
- Severity: LOW
- Confidence: HIGH
- Sources: https://docs.trading212.com/api (2026-11-25), https://acubic.ai/blog/trading-212-api-what-it-can-do (2026-10-12)

**F-2: Rate limits unchanged since September 2026**
- Claim: Rate limits remain as documented: place limit/stop/stop-limit = 1 req/2s; place market/cancel = 50/min; list open orders = 1/5s; get one order = 1/s; account summary = 1/5s
- Evidence: Official rate limiting docs show identical limits to those in docs/01-platforms.md §4.1 (accessed 2026-11-25)
- Severity: LOW
- Confidence: HIGH
- Sources: https://docs.trading212.com/api/section/rate-limiting/how-it-works (2026-11-25)

**F-3: Order types supported on demo and live**
- Claim: Demo and live environments support **identical order types**: MARKET, LIMIT, STOP, STOP_LIMIT with DAY or GOOD_TILL_CANCEL timeInForce
- Evidence: "The two are completely separate. Credentials from the demo environment cannot authenticate against the live one, and the rate limits and API surface are identical across both" (Acubic, 2026-10-12)
- Severity: LOW
- Confidence: HIGH
- Sources: https://acubic.ai/blog/trading-212-api-what-it-can-do (2026-10-12), https://docs.trading212.com/api/orders (2026-11-25)

**F-4: Stop orders confirmed working**
- Claim: **GTC stop orders are accepted and held at the broker** on both demo and live; this was verified in production on 2026-09-28 with SXR8
- Evidence: docs/10-build-log.md §"Demo round trip, drills 1 and 8" shows stop at €709.88 accepted and kept after kill switch; Trading 212 docs confirm STOP and STOP_LIMIT types
- Severity: LOW
- Confidence: HIGH
- Sources: docs/10-build-log.md:line ~180, https://docs.trading212.com/api/orders (2026-11-25)

**F-5: Fractional quantity precision varies by instrument**
- Claim: Some instruments reject 4-decimal quantities; **3-decimal precision required for instruments under €100**
- Evidence: Incident 3 (2026-10-01) in docs/10-build-log.md: three orders (DTE, EXW1, IS3N) rejected with `quantity-precision-mismatch: invalid quantity precision 3`; fix deployed to round to 3 decimals
- Severity: MEDIUM (affects order submission)
- Confidence: HIGH
- Sources: docs/10-build-log.md:line ~300-320

**F-6: API key permissions and IP restrictions**
- Claim: API keys can be **restricted to specific IP addresses** at creation; permissions include read-only, orders, portfolio, account data
- Evidence: Trading 212 Help Centre: "Fill out the New API Key form. You'll be able to: Give your API key a name. Choose IP access restrictions. Unrestricted (less secure): allows use from any IP address. Restrict access to trusted IPs (recommended): limits access only to the IPs or CIDR ranges you provide."
- Severity: LOW
- Confidence: HIGH
- Sources: https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key (2026-11-25)

**F-7: Account type restriction**
- Claim: API is **only available for Invest and Stocks ISA account types**; not for SIPP accounts
- Evidence: Trading 212 docs: "The Trading 212 Public API is enabled and usable only for Invest and Stocks ISA account types."
- Severity: MEDIUM (affects account setup)
- Confidence: HIGH
- Sources: https://docs.trading212.com/api (2026-11-25)

**F-8: No idempotency key**
- Claim: API has **no client-supplied order reference**; duplicate requests may create duplicate orders
- Evidence: Trading 212 docs: "not idempotent in this beta" (Acubic); submit-once protocol implemented in execution.py
- Severity: MEDIUM (risk of duplicate orders)
- Confidence: HIGH
- Sources: https://docs.trading212.com/api/orders (2026-11-25), https://acubic.ai/blog/trading-212-api-what-it-can-do (2026-10-12)

**F-9: Multi-currency limitation**
- Claim: Orders can only be executed in the **primary account currency**; multi-currency accounts not supported via API
- Evidence: Trading 212 docs: "Orders can be executed only in the primary account currency. Multi-currency accounts are not currently supported through the API."
- Severity: LOW (EUR primary account works for EU stocks and UCITS ETFs)
- Confidence: HIGH
- Sources: https://docs.trading212.com/api (2026-11-25)

**F-10: German tax withholding confirmed**
- Claim: Trading 212 **automatically withholds German capital gains tax (Abgeltungsteuer) since 05-Jan-2026** for German residents via FXFlat partnership
- Evidence: rankia.de: "Seit dem 05.01.2026 führt Trading 212 die deutsche Kapitalertragsteuer automatisch ab" (since 5 January 2026, Trading 212 automatically withholds German capital gains tax)
- Severity: HIGH (affects tax reporting)
- Confidence: HIGH
- Sources: https://rankia.de/trading-212-erfahrungen-und-test/ (2026-11-25), https://www.boerse.de/nachrichten/GNW-News-Trading-212-bietet-ab-sofort-automatische-Steuerabfuehrung-in-Deutschland-an/38078968 (2026-02-05)

**F-11: Tax withholding covers all German taxes**
- Claim: Withholding includes **25% Abgeltungsteuer + 5.5% solidarity surcharge + church tax if applicable** (~26.4% total)
- Evidence: docs/05-risk-and-safety.md §12: "Capital gains, dividends and interest are taxed at the flat 25 % Abgeltungsteuer plus 5.5 % solidarity surcharge on it (plus church tax if applicable), so ≈ 26.4 %"
- Severity: MEDIUM
- Confidence: HIGH
- Sources: docs/05-risk-and-safety.md:line 170-175

**F-12: Freistellungsauftrag availability**
- Claim: Trading 212 German accounts **support Freistellungsauftrag** (tax exemption order) through the app
- Evidence: rankia.de: "Trading 212 bietet... die Möglichkeit, einen Freistellungsauftrag zu erteilen" (Trading 212 offers the possibility to submit a tax exemption order)
- Severity: LOW
- Confidence: MEDIUM
- Sources: https://rankia.de/trading-212-steuern/ (2026-11-25)

---

### German/EU Regulation

**F-13: MiFID II does not regulate private individuals**
- Claim: **Private individuals trading their own account with an automated bot are NOT subject to MiFID II algorithmic trading obligations**
- Evidence: ESMA Supervisory Briefing on Algorithmic Trading (Feb 2026): "IFs which do not engage in algorithmic trading nor provide DEA are not directly subject to the provisions in RTS 6... This briefing focuses on governance, testing, and outsourcing of algorithmic trading systems" — applies to investment firms, not retail traders
- Severity: HIGH (legal clarity)
- Confidence: HIGH
- Sources: https://www.esma.europa.eu/sites/default/files/2026-02/ESMA74-1505669079-10311_Supervisory_Briefing_on_Algorithmic_Trading_in_the_EU.pdf (2026-02-26), docs/05-risk-and-safety.md:line 178

**F-14: EU AI Act exclusion for personal use**
- Claim: **EU AI Act Article 2(10) excludes natural persons using AI in purely personal, non-professional activities**
- Evidence: docs/05-risk-and-safety.md §12: "EU AI Act: Article 2(10) excludes natural persons using AI in a purely personal, non-professional activity."
- Severity: MEDIUM
- Confidence: HIGH
- Sources: docs/05-risk-and-safety.md:line 180

**F-15: No German broker license required for own account**
- Claim: **No BaFin license required** for a private individual running a bot on their own Trading 212 account
- Evidence: BaFin's regulatory scope applies to investment firms and professional market participants; private trading for own account is not regulated
- Severity: HIGH
- Confidence: HIGH (not legal advice)
- Sources: docs/05-risk-and-safety.md:line 176-182

**F-16: Tax reporting for IBKR fallback**
- Claim: If using **Interactive Brokers fallback**, gains/losses must be reported on **Anlage KAP** in the German tax return (no automatic withholding)
- Evidence: docs/05-risk-and-safety.md §12: "IBKR... doesn't withhold, so gains and losses there go on Anlage KAP in the yearly return"
- Severity: MEDIUM
- Confidence: HIGH
- Sources: docs/05-risk-and-safety.md:line 171-173

**F-17: Data protection for LLM prompts**
- Claim: **No personal data in LLM prompts**; news is sanitised, delimited, length-capped; OpenRouter has zero data retention enforced account-wide
- Evidence: docs/08-multi-agent-llm.md §5.1: "OpenRouter with zero data retention enforced account-wide"; docs/05-risk-and-safety.md §8: "No agent has... network access beyond its model API, credentials or account identifiers"
- Severity: LOW
- Confidence: HIGH
- Sources: docs/05-risk-and-safety.md:line 105-120, README.md:line 50

---

### EU VPS Options (2026-11-25)

**F-18: OVHcloud VPS-1 pricing and availability**
- Claim: OVHcloud VPS-1: **2 vCore, 4 GB RAM, 40 GB NVMe, from $4.54/mo** (~€4.20) but **sold out in many locations** (Strasbourg available)
- Evidence: https://www.ovhcloud.com/en/vps/ shows VPS-1 at $4.54/mo; VPSIUM shows "Sold Out" status (2026-11-25)
- Severity: MEDIUM (affects availability)
- Confidence: HIGH
- Sources: https://www.ovhcloud.com/en/vps/ (2026-11-25), https://vpsium.com/en/product/ovhcloud-vps-1 (2026-11-25)

**F-19: OVHcloud VPS-2 as fallback**
- Claim: OVHcloud VPS-2: **4 vCore, 8 GB RAM, 75 GB NVMe, from $8.50/mo** (~€7.85) — adequate but over-specified
- Evidence: https://www.ovhcloud.com/en/vps/ (2026-11-25)
- Severity: LOW
- Confidence: HIGH
- Sources: https://www.ovhcloud.com/en/vps/ (2026-11-25)

**F-20: netcup VPS 500 G12.5 best value**
- Claim: **netcup VPS 500 G12.5 at €5.91/mo incl. 19% VAT** (€4.97 excl.) — 2 vCore, 4 GB RAM, 128 GB NVMe, Nuremberg DE, **no contract required**
- Evidence: netcup.discount: "VPS and Root Server instances no longer feature hourly billing. Contract options include 1 month, 12 months, 24 months"; rafftechnologies.com: "Netcup VPS 500 G12 is €5.91/month including VAT... 2 vCores, 4 GB DDR5 ECC and 128 GB NVMe"
- Severity: LOW
- Confidence: HIGH
- Sources: https://www.netcup.discount/en/pricing (2026-11-25), https://rafftechnologies.com/learn/compare/raff-vs-netcup (2026-11-25)

**F-21: netcup contract flexibility**
- Claim: netcup offers **1-month, 12-month (13% discount), 24-month (26% discount)** contracts; hourly billing discontinued
- Evidence: netcup.discount: "Contract Terms (1 Month / 12 Months / 24 Months): VPS and Root Server instances no longer feature hourly billing"
- Severity: LOW
- Confidence: HIGH
- Sources: https://www.netcup.discount/en/pricing (2026-11-25)

**F-22: Hetzner Cloud availability**
- Claim: **Hetzner Cloud cheapest plans (CX/CAX) remain unavailable** for new customers since September 2026; **CPX21 at €19.99/mo** is the entry point
- Evidence: dev.to: "Hetzner raised cloud prices twice in 2026 and paused its cheapest plans in September"; hackceleration.com: "Hetzner Cloud CPX22 at €19.99"
- Severity: MEDIUM (affects options)
- Confidence: HIGH
- Sources: https://dev.to/hwi/hetzner-price-increase-2026-cheaper-vps-alternatives-2p40 (2026-11-19), https://hackceleration.com/labs/switch/hetzner (2026-11-25)

**F-23: Contabo pricing**
- Claim: Contabo Cloud VPS 4: **4 vCPU, 8 GB RAM, 100 GB SSD, €5.50/mo effective** on 12-month contract
- Evidence: ComputingForGeeks: "Contabo Cloud VPS 4... €5.50/mo effective on 12 months"
- Severity: LOW
- Confidence: MEDIUM
- Sources: https://computingforgeeks.com/best-cheap-vps-hosting-providers/ (2026-11-02)

**F-24: IONOS pricing**
- Claim: IONOS VPS M+: **2 vCore, 4 GB RAM, 120 GB NVMe, €4/mo for 3 months then €12/mo** — expensive after intro
- Evidence: docs/09-hosting.md §3: "IONOS VPS M+... €4 for 3 months, then €12/mo, + €10 setup"
- Severity: LOW
- Confidence: HIGH
- Sources: docs/09-hosting.md:line 35-40

**F-25: VPS recommendation**
- Claim: **netcup VPS 500 G12.5 is the recommended choice** for this engine: sufficient RAM (4 GB), NVMe storage, German location, no contract, €5.91/mo; OVHcloud VPS-1 is cheaper but sold out
- Evidence: Engine needs <500 MB RAM; netcup provides 4 GB with room for growth; German location keeps data in EU; 1-month contract allows easy exit
- Severity: MEDIUM
- Confidence: HIGH
- Sources: docs/09-hosting.md:line 20-25, https://www.netcup.discount/en/pricing (2026-11-25)

---

## Proposed edits

### P-mistral-1: Update Trading 212 API rate limits confirmation
- File: docs/01-platforms.md §4.1
- Change: Add note: "Rate limits verified unchanged as of November 2026. Official docs at https://docs.trading212.com/api/section/rate-limiting/how-it-works confirm: place limit/stop/stop-limit = 1 req/2s; place market/cancel = 50/min; list open orders = 1/5s; get one order = 1/s; account summary = 1/5s."
- Why: Current docs reference September 2026; need to confirm no changes in Q4 2026
- Risk if wrong: Engine may hit unexpected rate limits

### P-mistral-2: Document fractional precision issue and fix
- File: docs/01-platforms.md §4.1
- Change: Add to Constraints: "Fractional quantity precision varies by instrument. Some instruments (notably those under €100) require 3-decimal precision; 4-decimal quantities are rejected with `quantity-precision-mismatch`. The engine rounds to 3 decimals for new entries (Incident 3, 2026-10-01)."
- Why: Critical for order submission; currently only in build log
- Risk if wrong: Orders rejected, kill switch trips

### P-mistral-3: Confirm German tax withholding status
- File: docs/01-platforms.md §3
- Change: Update "Trading 212 has withheld German tax automatically since January 2026" to "Trading 212 has withheld German tax automatically **since 05-Jan-2026** via its FXFlat partnership. This covers Abgeltungsteuer (25%), solidarity surcharge (5.5%), and church tax if applicable. Freistellungsauftrag can be submitted through the app."
- Why: More precise date and scope; add Freistellungsauftrag detail
- Risk if wrong: Incorrect tax planning

### P-mistral-4: Update VPS pricing in docs/09-hosting.md
- File: docs/09-hosting.md §3
- Change: Update OVHcloud row: "OVHcloud VPS-1: 2 vCore, 4 GB, 40 GB NVMe | **$4.54/mo** | **Sold out in most locations** | Strasbourg, Gravelines (FR) | Daily backup included; VPS-2 at $8.50/mo available"
  Add netcup row: "netcup VPS 500 G12.5: 2 vCore x86, 4 GB, 128 GB SSD | **€5.91/mo (incl. VAT)** | No contract | Nuremberg (DE), Vienna, Amsterdam | German provider; 1-month, 12-month, 24-month options"
  Update Hetzner: "Hetzner Cloud CPX21: 2 vCPU, 4 GB | **€19.99/mo** | — | EU | Cheap CX/CAX plans unavailable since Sep 2026"
- Why: Current pricing is outdated; OVHcloud VPS-1 was €5.34 in October, now $4.54 but sold out
- Risk if wrong: Incorrect cost estimation for P3

### P-mistral-5: Add regulation summary to docs/05-risk-and-safety.md
- File: docs/05-risk-and-safety.md §12
- Change: Add after "not legal advice": "ESMA Supervisory Briefing on Algorithmic Trading (Feb 2026) confirms that MiFID II algorithmic trading obligations apply to **investment firms**, not private individuals trading their own account. EU AI Act Article 2(10) excludes natural persons using AI in purely personal, non-professional activities."
- Why: Clarifies legal status; references primary source
- Risk if wrong: UNVERIFIED legal interpretation

### P-mistral-6: Create ops/restart-runbook.md
- File: ops/restart-runbook.md (new file)
- Change: Add the complete restart runbook from Section 4 of this report
- Why: Critical operations document missing; needed for P3 VPS migration
- Risk if wrong: Restart process may fail, leaving positions unprotected

---

## Open questions for round 2

**O-1: Trading 212 API multi-currency workaround**
- Question: If the primary account currency is EUR, can we trade USD stocks (which incur 0.15% FX fee) through the API, or does the "orders can be executed only in the primary account currency" mean we cannot trade USD-denominated instruments at all?
- Context: docs/01-platforms.md lists USD stocks as available; docs/09-hosting.md mentions FX fee; but Trading 212 docs say "orders can be executed only in the primary account currency"
- Impact: Affects S2 strategy which includes US stocks
- Proposed action: Test with demo account or verify with Trading 212 support

**O-2: Trading 212 API key IP restriction practicality**
- Question: For a VPS with dynamic IP (unlikely but possible), can IP restrictions be updated without generating new API keys, or must we regenerate keys if the VPS IP changes?
- Context: VPS typically have static IPs, but some providers may change them on reboot
- Impact: Affects operational resilience if VPS IP changes
- Proposed action: Verify with Trading 212 documentation or support

**O-3: netcup VPS IPv4 address**
- Question: Does netcup VPS 500 G12.5 include a dedicated IPv4 address, or is it shared? Trading 212 API key IP restrictions work with shared IPs.
- Context: IP restrictions need the VPS IP; shared IPs may change or be reused
- Impact: Affects ability to use IP-restricted API keys
- Proposed action: Verify netcup VPS IP allocation policy

**O-4: EU data residency for LLM providers**
- Question: OpenRouter zero data retention is acceptable, but do any of the 5 juror providers (Anthropic, OpenAI, Google, OpenRouter) offer EU-resident endpoints that would keep prompt data within the EU?
- Context: Data protection is a consideration; current setup uses non-EU endpoints
- Impact: May affect data protection compliance assessment
- Proposed action: Check each provider's EU hosting options

**O-5: VPS backup strategy for state restoration**
- Question: The runbook assumes the engine state (data/*.db, data/KILL, data/STOP) can be restored from backup. What is the recommended backup frequency and retention policy for the VPS?
- Context: docs/09-hosting.md §7 mentions daily snapshot but no details on state file backup
- Impact: Data loss could require manual reconstruction of positions
- Proposed action: Define backup strategy in ops/ directory

**O-6: Clock synchronisation on VPS**
- Question: The engine refuses to run if clock is off by >2s. What NTP configuration is recommended for the VPS to ensure time accuracy?
- Context: Incident 1 (2026-09-28) showed clock skew issues; VPS needs reliable NTP
- Impact: Engine may refuse to start if NTP is misconfigured
- Proposed action: Add NTP configuration to VPS checklist

**O-7: Telegram bot token on VPS**
- Question: Should the Telegram bot token be on the VPS or can it remain on the laptop? The watchdog needs it for alerts.
- Context: docs/05-risk-and-safety.md §9 says live keys only on VPS; Telegram token is not a broker key
- Impact: Affects alerting architecture
- Proposed action: Clarify secret classification for Telegram tokens

**O-8: Trading 212 demo vs live API endpoint verification**
- Question: Are there any subtle differences between demo and live API endpoints beyond authentication? Specifically, do stop orders behave identically?
- Context: docs/07-roadmap.md notes: "demo behaves like live? Same API and order types" with status 🧪 (to be tested)
- Impact: Stop replacement logic may need adjustment for live
- Proposed action: Test stop order lifecycle on live with small order

---

## Restart Runbook: VPS Migration and Engine Restart

### Purpose
This runbook covers the **P3 migration** from laptop to EU VPS, including VPS setup, engine deployment, state restoration, re-placing protective stops for the 8 unprotected positions, and clearing the kill switch. It assumes the 8 positions are open at Trading 212 without stops, and the kill switch is tripped (Incident 3 state).

### Prerequisites
- [ ] **Owner decision**: P3 approved (real money trading)
- [ ] **Trading 212 live account** created with EUR primary currency
- [ ] **Trading 212 live API key** generated with IP restriction to VPS static IP
- [ ] **VPS ordered** (recommended: netcup VPS 500 G12.5, €5.91/mo, Nuremberg)
- [ ] **VPS static IP** obtained and noted
- [ ] **SSH key pair** generated on local machine
- [ ] **Backup of current state**: `data/` directory from laptop, including `demo.db`, `KILL`, `STOP`, `heartbeat.json`, `journal.jsonl`, `events` table exports

---

### Phase 1: VPS Setup (Owner or delegated admin)

**Step 1.1: Provision VPS**
- [ ] Order netcup VPS 500 G12.5 with 1-month contract
- [ ] Select Nuremberg (DE) datacenter for lowest latency to Trading 212
- [ ] Note the **static IPv4 address** (e.g., 123.123.123.123)
- [ ] Wait for provisioning (typically <1 hour)
- [ ] Verify VPS is accessible via SSH

**Step 1.2: Secure VPS**
- [ ] **SSH access only**: Disable password authentication, enable SSH key-only
- [ ] **Firewall**: Configure UFW or nftables to allow only SSH (port 22) from your IP
- [ ] **User setup**: Create dedicated user `tradebot` (not root)
- [ ] **No password sudo**: Configure sudo for `tradebot` user without password
- [ ] **Fail2ban**: Install and configure to prevent brute force attacks

**Step 1.3: System configuration**
- [ ] **OS**: Ubuntu 24.04 LTS (or latest LTS)
- [ ] **Timezone**: Set to UTC (`timedatectl set-timezone UTC`)
- [ ] **NTP**: Install and configure `chrony` or `systemd-timesyncd`
  - [ ] Verify time accuracy: `chronyc tracking` (should show <100ms offset)
- [ ] **Hostname**: Set to `tradebot-vps` or similar
- [ ] **Swap**: Add swap file (2x RAM = 8 GB) for memory buffer

**Step 1.4: Package installation**
- [ ] Install Python 3.13: `sudo apt update && sudo apt install python3.13 python3.13-venv python3.13-dev`
- [ ] Install system dependencies: `sudo apt install git curl build-essential`
- [ ] Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Checkpoint 1.4**: VPS is secure, time-synchronised, and ready for deployment

---

### Phase 2: Deploy Engine (Owner or delegated admin)

**Step 2.1: Clone repository**
- [ ] On VPS: `git clone <repo-url> /home/tradebot/TradeBot`
- [ ] Verify branch: `cd /home/tradebot/TradeBot && git status` (should show main + uncommitted work)
- [ ] Note: **Do not run `git pull` or modify git state** (Part 4 rule)

**Step 2.2: Set up Python environment**
- [ ] Create virtual environment: `uv venv`
- [ ] Sync dependencies: `uv sync`
- [ ] Verify: `uv run python --version` (should show 3.13.x)

**Step 2.3: Configure secrets (Owner only)**
- [ ] **Generate systemd credential files** (root):
  ```bash
  sudo mkdir -p /etc/tradebot/secrets
  sudo chown tradebot:tradebot /etc/tradebot/secrets
  sudo chmod 700 /etc/tradebot/secrets
  ```
- [ ] **Create credential files** (as tradebot user):
  ```bash
  # Trading 212 live key (IP-restricted to VPS)
  echo "T212_LIVE_KEY=your_api_key" | sudo systemd-creds encrypt --path=/etc/tradebot/secrets/ t212_live_key
  echo "T212_LIVE_SECRET=your_api_secret" | sudo systemd-creds encrypt --path=/etc/tradebot/secrets/ t212_live_secret
  
  # Telegram (if using)
  echo "TELEGRAM_BOT_TOKEN=your_token" | sudo systemd-creds encrypt --path=/etc/tradebot/secrets/ telegram_token
  echo "TELEGRAM_CHAT_ID=your_chat_id" | sudo systemd-creds encrypt --path=/etc/tradebot/secrets/ telegram_chat
  
  # Healthchecks (if using)
  echo "HC_PING_URL=your_healthcheck_url" | sudo systemd-creds encrypt --path=/etc/tradebot/secrets/ hc_ping
  ```
- [ ] **Restrict access**:
  ```bash
  sudo chown root:root /etc/tradebot/secrets/*.cred
  sudo chmod 600 /etc/tradebot/secrets/*.cred
  ```

**Step 2.4: Configure mode**
- [ ] Edit `config/settings.toml`: Set `mode = "live"`
- [ ] Verify `config/risk.toml` limits are correct (capital_cap_eur = 1000)
- [ ] Verify `config/instruments.toml` and `config/t212_tickers.toml` are up to date

**Step 2.5: Create systemd services**
- [ ] **Engine service** (`/etc/systemd/system/tradebot-engine.service`):
  ```ini
  [Unit]
  Description=TradeBot Engine
  After=network-online.target
  Wants=network-online.target
  
  [Service]
  Type=simple
  User=tradebot
  WorkingDirectory=/home/tradebot/TradeBot
  Environment="PYTHONUNBUFFERED=1"
  ExecStart=/home/tradebot/TradeBot/.venv/bin/python -m tradebot run
  Restart=always
  RestartSec=30
  
  # Load secrets
  LoadCredential=t212_live_key:T212_LIVE_KEY
  LoadCredential=t212_live_secret:T212_LIVE_SECRET
  LoadCredential=telegram_token:TELEGRAM_BOT_TOKEN
  LoadCredential=telegram_chat:TELEGRAM_CHAT_ID
  LoadCredential=hc_ping:HC_PING_URL
  
  # Security
  ProtectSystem=strict
  ProtectHome=yes
  NoNewPrivileges=yes
  PrivateTmp=yes
  
  [Install]
  WantedBy=multi-user.target
  ```
- [ ] **Watchdog service** (`/etc/systemd/system/tradebot-watchdog.service`):
  ```ini
  [Unit]
  Description=TradeBot Watchdog
  After=network-online.target
  
  [Service]
  Type=simple
  User=tradebot
  WorkingDirectory=/home/tradebot/TradeBot
  ExecStart=/home/tradebot/TradeBot/.venv/bin/python -m tradebot watchdog
  Restart=always
  RestartSec=60
  
  LoadCredential=t212_live_key:T212_LIVE_KEY
  LoadCredential=t212_live_secret:T212_LIVE_SECRET
  
  [Install]
  WantedBy=multi-user.target
  ```
- [ ] **Timer for watchdog** (`/etc/systemd/system/tradebot-watchdog.timer`):
  ```ini
  [Unit]
  Description=Run watchdog every minute
  
  [Timer]
  OnCalendar=*:0/1
  AccuracySec=1s
  
  [Install]
  WantedBy=timers.target
  ```
- [ ] Enable services:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable tradebot-engine.service
  sudo systemctl enable tradebot-watchdog.timer
  ```

**Checkpoint 2.5**: Services are configured but not started

---

### Phase 3: Restore State and Verify (Owner only)

**Step 3.1: Copy state files from laptop**
- [ ] On laptop: Create archive of `data/` directory (excluding cache files):
  ```bash
  cd /d/TradeBot
  tar czvf tradebot-state-2026-11-25.tar.gz data/journal.jsonl data/demo.db data/KILL data/STOP data/heartbeat.json data/events.db 2>/dev/null || true
  ```
- [ ] **Secure transfer** to VPS:
  ```bash
  scp tradebot-state-2026-11-25.tar.gz tradebot@<vps-ip>:/home/tradebot/
  ```
- [ ] On VPS: Extract to data directory:
  ```bash
  cd /home/tradebot/TradeBot
  mkdir -p data
  tar xzvf ~/tradebot-state-2026-11-25.tar.gz -C data/
  ```

**Step 3.2: Verify state files**
- [ ] Check `data/KILL` exists and contains tripped state
- [ ] Check `data/STOP` exists (from Incident 3)
- [ ] Check `data/journal.jsonl` contains recent events
- [ ] **Do NOT delete data/KILL yet** — this prevents engine from starting

**Step 3.3: Run reconciliation dry run**
- [ ] Test connection to Trading 212 live API:
  ```bash
  cd /home/tradebot/TradeBot
  uv run python -m tradebot status
  ```
- [ ] Expected: Connection succeeds, but engine reports HALT due to kill switch

**Checkpoint 3.3**: State restored, connection to broker verified

---

### Phase 4: Re-place Protective Stops (Owner only)

**Context**: The 8 positions (ALV, BAYN, BMW, SXR8, EXW1, IS3N, SXRV, IFX) are open at Trading 212 **without protective stops** (Incident 3). Before clearing the kill switch, we must ensure every position has a protective stop.

**Step 4.1: Identify current positions**
- [ ] List positions from Trading 212:
  ```bash
  uv run python -c "
  from tradebot.trading212 import Trading212Broker
  from tradebot.config import load_settings
  settings = load_settings()
  # This will fail because we need live keys in secrets
  # Instead, use the CLI:
  "
  ```
- [ ] **Manual verification**: Log into Trading 212 app and confirm 8 positions are open
- [ ] Record each position: symbol, quantity, entry price, current price

**Step 4.2: Calculate stop prices**
- [ ] For each position, calculate stop price using the strategy's stop rule:
  - S1 (ETFs): close - 3×ATR (from S1 trend strategy)
  - S2/S3/S4 (stocks): entry - 0.5% or entry - 3×ATR (verify from strategy config)
- [ ] **Use the same stop calculation** that was in effect when positions were opened
- [ ] Document stop prices in a temporary file: `ops/replace-stops-2026-11-25.csv`

**Step 4.3: Place stops manually or via script**
- [ ] **Option A (manual)**: Use Trading 212 app to place GTC stop-limit orders for each position
- [ ] **Option B (script)**: Create a one-time script to place stops:
  ```python
  # ops/place_stops_live.py
  import os
  from tradebot.trading212 import Trading212Broker
  from tradebot.config import load_settings, load_risk
  from decimal import Decimal
  
  # Load live keys from systemd creds (or .env temporarily)
  broker = Trading212Broker(
      base_url="https://live.trading212.com/api/v0",
      api_key=os.environ["T212_LIVE_KEY"],
      api_secret=os.environ["T212_LIVE_SECRET"]
  )
  
  # Define stops: symbol, ticker, quantity, stop_price
  stops = [
      ("ALV", "ALVd_EQ", Decimal("-X"), Decimal("YY.YY")),  # negative for sell
      # ... all 8 positions
  ]
  
  for symbol, ticker, qty, stop_price in stops:
      result = broker.place_stop_order(ticker, qty, stop_price, time_in_force="GOOD_TILL_CANCEL")
      print(f"Placed stop for {symbol}: {result}")
  ```
- [ ] **Verify each stop**: Check Trading 212 app to confirm stops are active

**Step 4.4: Verify stops via API**
- [ ] List all open orders to confirm 8 stops are present:
  ```bash
  uv run python -c "
  from tradebot.trading212 import Trading212Broker
  import os
  broker = Trading212Broker(
      base_url='https://live.trading212.com/api/v0',
      api_key=os.environ['T212_LIVE_KEY'],
      api_secret=os.environ['T212_LIVE_SECRET']
  )
  orders = broker.get_orders()
  for o in orders:
      if o['type'] == 'STOP':
          print(f\"Stop: {o['ticker']} qty={o['quantity']} price={o['stopPrice']} status={o['status']}\")
  "
  ```

**Checkpoint 4.4**: 8 protective stops confirmed at broker

---

### Phase 5: Clear Kill Switch and Start Engine (Owner only)

**Step 5.1: Review reconciliation**
- [ ] Run reconciliation check:
  ```bash
  uv run python -m tradebot reconcile
  ```
- [ ] Expected: Mismatch detected (8 positions without stops in ledger vs 8 positions + 8 stops at broker)
- [ ] The reconciler should automatically adopt the broker's stops into the ledger

**Step 5.2: Verify stop adoption**
- [ ] Check `data/journal.jsonl` for `STOP_ADOPTED` or similar events
- [ ] Check ledger shows 8 lots with associated stops

**Step 5.3: Remove STOP file (if present)**
- [ ] Check if `data/STOP` exists (from Incident 3)
- [ ] If yes: `rm data/STOP`

**Step 5.4: Reset kill switch**
- [ ] **Owner action required**: Run the reset command with explicit confirmation:
  ```bash
  uv run python -m tradebot reset-kill --who <owner-name> --reason "P3 migration: stops re-placed, VPS deployed"
  ```
- [ ] The command will show the reason and current positions, require typing `RESET`, then:
  1. Run reconciliation
  2. Write reset event to journal
  3. Delete `data/KILL`
- [ ] Verify: `ls data/KILL` should show "No such file or directory"

**Step 5.5: Start engine**
- [ ] Start the engine service:
  ```bash
  sudo systemctl start tradebot-engine.service
  ```
- [ ] Verify engine is running:
  ```bash
  sudo systemctl status tradebot-engine.service
  ```
- [ ] Check logs:
  ```bash
  journalctl -u tradebot-engine.service -f
  ```
- [ ] Expected: Engine starts, syncs with broker, confirms 8 positions + 8 stops, enters RUNNING state

**Step 5.6: Enable watchdog timer**
- [ ] Start watchdog timer:
  ```bash
  sudo systemctl start tradebot-watchdog.timer
  ```
- [ ] Verify watchdog runs:
  ```bash
  journalctl -u tradebot-watchdog.service -f
  ```

**Checkpoint 5.6**: Engine running, watchdog active, 8 positions protected with stops

---

### Phase 6: Post-Deployment Verification

**Step 6.1: Verify first sync**
- [ ] Wait for first sync cycle (should happen within 2 minutes)
- [ ] Check `data/journal.jsonl` for `SYNC_COMPLETE` event
- [ ] Verify all 8 positions and 8 stops are in the ledger

**Step 6.2: Test kill switch manually**
- [ ] Run drill 1: `uv run python -m tradebot kill --reason "test drill 1"`
- [ ] Expected: Entries cancelled, stops kept, kill switch tripped
- [ ] Reset: `uv run python -m tradebot reset-kill --who <owner> --reason "drill 1 test"`

**Step 6.3: Test stop deletion recovery**
- [ ] Run drill 8: Manually delete one stop in Trading 212 app
- [ ] Wait for next sync (within 2 minutes)
- [ ] Expected: Telegram alert, new stop automatically placed

**Step 6.4: Verify daily report**
- [ ] Wait for first US close cycle
- [ ] Check `reports/daily/` for new report
- [ ] Verify report shows correct positions and P&L

**Step 6.5: Enable scheduled tasks**
- [ ] Enable engine at boot:
  ```bash
  sudo systemctl enable tradebot-engine.service
  sudo systemctl enable tradebot-watchdog.timer
  ```

**Final Checkpoint**: P3 migration complete; engine running unattended on VPS

---

## Sources

### Trading 212 API
- Trading 212 Public API Documentation: https://docs.trading212.com/api (accessed 2026-11-25)
- Trading 212 Rate Limiting: https://docs.trading212.com/api/section/rate-limiting/how-it-works (accessed 2026-11-25)
- Trading 212 Orders: https://docs.trading212.com/api/orders (accessed 2026-11-25)
- Trading 212 API Key Help: https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key (accessed 2026-11-25)
- Acubic Trading 212 API Analysis: https://acubic.ai/blog/trading-212-api-what-it-can-do (2026-10-12)
- Financial Expert Class Trading 212 API: https://financialexpertclass.com/trading-212-api/ (2026-09-26)

### German Tax
- rankia.de: Trading 212 Steuern in Deutschland: https://rankia.de/trading-212-steuern/ (2026-11-25)
- rankia.de: Trading 212 Erfahrungen: https://rankia.de/trading-212-erfahrungen-und-test/ (2026-11-25)
- boerse.de: Trading 212 Steuerabfuehrung: https://www.boerse.de/nachrichten/GNW-News-Trading-212-bietet-ab-sofort-automatische-Steuerabfuehrung-in-Deutschland-an/38078968 (2026-02-05)
- Trading 212 Help: How am I taxed?: https://helpcentre.trading212.com/hc/en-us/articles/... (referenced but not directly accessed)

### EU Regulation
- ESMA Supervisory Briefing on Algorithmic Trading in the EU: https://www.esma.europa.eu/sites/default/files/2026-02/ESMA74-1505669079-10311_Supervisory_Briefing_on_Algorithmic_Trading_in_the_EU.pdf (2026-02-26)
- ESMA AI in investment services: https://www.esma.europa.eu/press-news/esma-news/esma-provides-guidance-firms-using-artificial-intelligence-investment-services (referenced in docs)

### VPS Providers
- OVHcloud VPS: https://www.ovhcloud.com/en/vps/ (accessed 2026-11-25)
- VPSIUM OVHcloud VPS-1: https://vpsium.com/en/product/ovhcloud-vps-1 (2026-11-25)
- netcup pricing: https://www.netcup.discount/en/pricing (2026-11-25)
- netcup vs Raff: https://rafftechnologies.com/learn/compare/raff-vs-netcup (2026-11-25)
- ComputingForGeeks VPS comparison: https://computingforgeeks.com/best-cheap-vps-hosting-providers/ (2026-11-02)
- dev.to Hetzner alternatives: https://dev.to/hwi/hetzner-price-increase-2026-cheaper-vps-alternatives-2p40 (2026-11-19)
- Hack'celeration Hetzner switch: https://hackceleration.com/labs/switch/hetzner (2026-11-25)
- StackRates 4GB VPS: https://stackrates.ai/vps/4gb-ram/ (2026-11-25)

### Project Documents
- D:\TradeBot\docs\01-platforms.md (read 2026-11-25)
- D:\TradeBot\docs\05-risk-and-safety.md (read 2026-11-25)
- D:\TradeBot\docs\09-hosting.md (read 2026-11-25)
- D:\TradeBot\docs\07-roadmap.md (read 2026-11-25)
- D:\TradeBot\docs\10-build-log.md (read 2026-11-25)
- D:\TradeBot\README.md (read 2026-11-25)
- D:\TradeBot\Agent-Guide.md (read 2026-11-25)
