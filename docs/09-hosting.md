# 09 — Hosting: this PC 24/7, or a server?

## 1. What has to run

| Workload | Timing | Resources |
|---|---|---|
| Engine: EU cycle | After the Xetra close (17:30 CET), ~17:45 | Seconds of CPU, < 500 MB RAM |
| Engine: US cycle | After the US close (22:00 CET), ~22:30 | same |
| Fill checks + stop placement | After the opens, ~09:15 and ~15:45 CET | same |
| Watchdog | Every minute | negligible |
| LLM desk | During the cycles; calls go to hosted APIs | Network only, **no GPU** |
| Broker gateway | Only if IBKR is chosen: IB Gateway (Java) runs constantly | 1–2 GB RAM |

Reliability needs are modest. Protective stops rest at the broker, so a missed cycle means a missed signal, not an unprotected position.

## 2. This PC as a 24/7 host

Measured on 2026-09-24: Intel Core i5-7200U (2 cores / 4 threads, a 2016 laptop CPU), 7.9 GB RAM, Intel HD 620 graphics (no CUDA GPU), 90 GB free on C: and 22 GB free on D:.

- **Enough for the engine.** Trading 212 is plain REST, and SQLite with daily bars stays well under 1 GB.
- **Not enough for local LLMs.** Small quantised 7–8B models would run on the CPU at a few tokens per second, and they aren't the models the desk needs. The leading open-weight models need hundreds of GB of GPU memory. Open models therefore run on hosted inference ([08 §5](08-multi-agent-llm.md#5-providers--integration)), wherever the engine runs.
- **Electricity:** a laptop idling at ~10–15 W uses ~90–130 kWh a year, about **€35–50/year** at ~€0.38/kWh. A desktop drawing 60–100 W would cost €200–330.

| Risk on a home laptop | Mitigation |
|---|---|
| Windows Update reboots | Set active hours around the cycle times; start the engine at boot via Task Scheduler; startup reconciliation resumes cleanly |
| Sleep, hibernate, lid closed | Power plan: never sleep on AC; lid action "do nothing"; hibernate off |
| Battery ageing from being always plugged in | Turn on the vendor's charge limit (60–80 %) if available |
| Home power or internet outage | Stops at the broker; the external dead-man's switch alerts (§5) |
| **Memory pressure from personal use** (seen 2026-09-28: 0.4 GB of 7.9 GB free, 21.5 GB committed) | New processes crawl, requests time out, a watchdog run hung for 5 minutes. Mitigated in code (a light watchdog, clock samples only from fast requests, restarts every 5 min, refusal alerts). Keep browser tabs and heavy apps down while the engine runs; a recurring problem is a reason to move to the VPS early. |
| Shared personal machine (browsing, downloads) holding broker keys | Acceptable for **demo keys only**; live keys never go on this machine |
| Laptop moved, closed or switched off by accident | The dead-man's switch alerts within one cycle |

## 3. A small EU VPS

- 1–2 vCPU, 2–4 GB RAM, Linux, at a German or EU provider (Hetzner, netcup, IONOS, OVH, …): roughly **€5–10/month**. Hetzner raised prices twice in 2026 and paused its cheapest plans in September, so check current offers.
- **Pros:** always on; datacentre power and network; snapshots and backups; kept apart from personal use, which keeps keys safer; data stays in the EU.
- **Cons:** €60–120 a year, which is 6–12 % of the €1,000 cap and counts as research cost. It also needs basic Linux administration.

**Offers checked on 2026-10-06** (2 vCPU / 4 GB is plenty: the engine needs < 500 MB). Prices include 19 % VAT:

| Provider and plan | Specs | No contract | With a contract | Locations orderable on 10-06 | Notes |
|---|---|---|---|---|---|
| **OVHcloud VPS-1** | 2 vCore, 4 GB, 40 GB NVMe | **€5.34/mo** | €4.53/mo on 12 months (paid upfront, renews automatically) | Strasbourg, Gravelines (FR); Limburg (DE) out of stock | Daily backup of the last 24 h included; no setup fee |
| **netcup VPS 500 G12.5** | 2 vCore x86, 4 GB, 64 GB SSD | €9.50/mo | €8.26 (12 months), €7.03 (24 months) | Random EU site (AT/DE/NL), or Nuremberg for +€1.04 | German company; snapshots; no setup fee |
| IONOS VPS M+ | 2 vCore, 4 GB, 120 GB NVMe | €4 for 3 months, then **€12/mo**, + €10 setup | Minimum terms not shown | EU, US, UK | Expensive after the intro price |
| Contabo Cloud VPS 4 | 4 vCPU, 8 GB, 100 GB SSD | Not checked | €5.50/mo effective on 12 months | Not checked | The most RAM per euro; 12-month price |
| Hetzner Cloud | CPX22: 2 vCPU, 4 GB | €19.99/mo excl. VAT (CPX22, as reported in September) | — | EU plans showed "currently unavailable" on 10-06 | The cheap CX/CAX line has been unavailable since early September 2026; Hetzner has limited capacity for new customers since 06-26 |

**Choice: OVHcloud VPS-1 without a contract, in Strasbourg.** It's the cheapest option without a contract, includes a daily backup, and can be cancelled monthly. If the T212 or Yahoo data feeds misbehave from that IP range, netcup is the fallback.

**Considered and rejected: the owner's idle tablet** (Redmi Pad Pro, 8 GB, Android/HyperOS).
- It would avoid the laptop's memory problem, but the bot would run under Termux, and Android stops background apps; Xiaomi is among the most aggressive vendors.
- It shares the laptop's home Wi-Fi and power, and would sit on the charger 24/7.
- It can't hold live keys (no fixed IP), so it would mean a second migration before P3.

## 4. Comparison

| | Laptop 24/7 | VPS | Hybrid (VPS runs the bot, laptop is for development) |
|---|---|---|---|
| Cost / year | ~€40 electricity | ~€60–120 | ~€60–120 |
| Uptime | Home-grade | Datacentre-grade | Datacentre-grade |
| Key security | Weak (shared personal machine) | Good (single-purpose, SSH only) | Good |
| Local LLMs | No (no GPU) | No (no GPU) | No; all use hosted APIs |
| Setup effort | Low (Windows, Task Scheduler) | Medium (Linux, systemd) | Medium |
| Good for | P0–P2, demo money | P3+, real money | P3+ |

## 5. Recommendation

- **P0–P2 (demo money): this laptop, running 24/7** with the checklist in §6. It costs nothing extra, and failures only cost demo trades, which is itself useful research into how a home setup fails.
- **Before P3 (real money):** move the engine and watchdog to an EU VPS. Live keys exist only there, and the laptop stays the development machine.
- **In both setups, add an external dead-man's switch.** healthchecks.io (free tier) or similar gets a ping from the engine every cycle. If a ping is missed, it alerts via Telegram or email. This works even when the whole host is dead, which an on-host watchdog can't handle.
- **If IBKR replaces Trading 212:** use a VPS with ≥ 4 GB RAM, and plan for the weekly 2FA re-login on your phone every Sunday ([01 §4.2](01-platforms.md#42-interactive-brokers-fallback)).

## 6. Laptop checklist (P0–P2)

`ops/install-tasks.ps1` automates the power plan, hourly time sync, the Task Scheduler entries (engine at boot and started again every 5 minutes if it isn't running, watchdog every minute, nightly backup to `C:\TradeBotBackup`) and starts the engine. Run it once in an elevated PowerShell, and again after it changes: it stops a running engine cleanly before re-registering. The other items are manual.

- [ ] Plugged in; never sleep on AC; lid closed → do nothing; hibernate off; battery charge limit on if available.
- [ ] Windows Update: set active hours; patch manually at the weekend if needed.
- [ ] Task Scheduler: engine starts at boot (whether or not a user is logged on) and restarts on failure; watchdog every minute.
- [ ] Time sync on (Windows Time service). The engine refuses to run if the clock is off by more than 2 s.
- [ ] Project and `data/` on D: (22 GB free is plenty); nightly copy of `data/` to C: or cloud storage.
- [ ] Ethernet rather than Wi-Fi if possible.
- [ ] A separate Windows user for the bot; **demo keys only**; disk encryption if the edition supports it.
- [ ] Dead-man's switch check created (healthchecks.io, period 10 min, grace 10 min, URL in `.env` as `HC_PING_URL`); test alert received.
- [ ] Telegram bot created (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `.env`); test alert received.

## 7. VPS checklist (P3)

- [ ] Ubuntu LTS; SSH key login only; firewall denies all inbound traffic except SSH (ideally only from your IP).
- [ ] `unattended-upgrades` on; clock in UTC with NTP.
- [ ] systemd services for engine and watchdog with `Restart=always`.
- [ ] Secrets via systemd credentials (`LoadCredential=`) or a root-owned file readable only by the service user, since the desktop keyring doesn't exist on a headless server.
- [ ] Daily snapshot; journal exported off the machine.
- [ ] Dead-man's switch moved to the VPS engine; drill 2 ([05 §11](05-risk-and-safety.md#11-drills-all-must-pass-before-each-promotion)) repeated on the VPS.

## 8. Restart on the VPS (demo) — runbook (added 2026-11-25)

This resumes the **demo**. Live keys and P3 need a separate owner decision. Steps marked **[owner]** are the owner's to do.

1. **[owner]** Commit or back up the current working tree. Copy `data/` to the VPS: `demo.db`, `KILL`, `STOP`, `kill_log.jsonl`, `trials.jsonl`, `research.db`. Use the **demo** API key only, IP-restricted to the VPS, kept out of git.
2. Deploy with `uv sync`, then `uv run pytest -q` on the VPS. Every test must pass.
3. With `KILL` and `STOP` still in place, take a **read-only** broker inventory (positions, open orders, corporate actions since 2026-10-06) and compare it lot by lot with the ledger. Don't use `tradebot reconcile` for this step: it runs a sync that writes to the ledger and can trip the kill switch.
4. Apply change sets A (atomic fills), B (protection and the restart rule, [04](04-architecture.md)), D (the Incident 3 fixes) and E (Linux paths, systemd units, credentials, backup) before starting any service.
5. **[owner]** Decide each of the 8 lots: exit by rule (recommended; breached stops and overdue time exits), or keep the lot and re-stop it at a new level.
6. With KILL **still tripped**, the recovery exits go through `kill --flatten` and fill at the next open. Every kept lot gets a confirmed protective stop. Check both against the broker.
7. **[owner]** Only then: `reset-kill --who <owner> --reason "VPS migration; recovery done"`, remove `STOP`, and start the services.
8. Run drills 1 and 8 again. The P1 gate clock starts at zero: 2 weeks of clean runs on the VPS.

## Sources

- Hetzner pricing: [price adjustment June 2026](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) · [2026 overview](https://www.bitdoze.com/hetzner-cloud-cost-optimized-plans/)
- IB Gateway operations: [IBC user guide](https://github.com/IbcAlpha/IBC/blob/master/userguide.md) · [running IB Gateway 24/7](https://newyorkcityservers.com/blog/interactive-brokers-vps-tws-ib-gateway)
