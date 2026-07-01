# Open Claw — Trading Agent Handoff (Zuck → Elon)

> **Purpose:** Everything the trading agent (currently *Zuck* on OpenClaw) does, so *Elon* (Hermes) can take over. This is the operational runbook, not marketing. Read it top to bottom once, then use it as reference.
>
> **Last updated:** 2026-07-01 by Zuck
> **Repo:** `/Users/chris/code/trading-pipeline`
> **Remotes:** `origin` = `github.com/jameslevinson95-tech/open-claw.git` · `private` = `github.com/chrisbuetti/trading-pipeline.git`
> **Reports channel:** Slack `#trading` (`C0B45KX7T2B`). **ALL trading output goes here, never a DM.**

---

## 0. TL;DR — What "the trading agent" actually is

"Open Claw" is a multi-agent, real-money swing-trading system on a **Robinhood** account (acct `···5614`, ~$10k). The agent's job is to run the daily pipeline, monitor positions, keep every position protected by a stop, and report to `#trading`. Most of the heavy lifting is **cron-driven** (scheduled agent turns) plus **two always-on Python daemons** and a set of **launchd timers**. The LLM agent's real responsibilities are:

1. **Execute the agent-logic prompts** (Agents 1, 3, 5) directly as the model — the pipeline is designed so the agent *is* the Claude brain, no API shell-out. (Agents 2 uses Gemini; Agent 4 is pure Python ATR math.)
2. **Respond to alerts** the daemons/crons raise in `#trading`.
3. **Handle ad-hoc requests** from Chris/Jamie (e.g. "bump the AMD stop to breakeven").
4. **Keep the code healthy** and pushed to GitHub.

**Golden rule:** *Never leave a live position without a protective stop.* Everything below exists to enforce that.

---

## 1. The Pipeline — 5 Agents

Data flows through `output/*.json` files, one per stage. The orchestrator was built to call APIs, but **when the agent runs it, execute the agent logic directly as the model** (read the data + system prompt, produce the output JSON). No `ANTHROPIC_API_KEY` needed for Agents 1/3/5.

| Agent | File | Brain | Job | Output |
|---|---|---|---|---|
| **1 — Macro Director** | `agent1_macro_director.py` | LLM (you) | Reads macro + assembly data, sets **regime** (Risk-On/Off), vol regime, posture, preferred themes. Uses *regime hysteresis* — don't flip regime unless evidence is severe. | `output/agent1_directive.json` |
| **2 — Fundamental Screener** | `agent2_fundamental_screener.py` | **Gemini** `gemini-3.1-pro-preview` ONLY (no fallbacks) | Screens theme-aware universe → fundamental candidates. Portfolio-blindness fix: told which tickers are already held so it won't pick correlated names. | `output/agent2_candidates.json` |
| **3 — Qualitative Synthesizer** | `agent3_synthesizer.py` | LLM (you) | Combines news + options flow + short interest → verdict per candidate: `PASS_THROUGH`, `CONFIRM_ENHANCED`, `VETO_DIVERGENT`, `VETO_CROWDED`, `VETO_QUALITATIVE`. (X/Twitter signal **retired** 2026-06-22 — dead signal.) | `output/agent3_verified.json` |
| **4 — Risk Manager** | `agent4_risk_manager.py` | **Pure Python** (no LLM) | ATR-based position sizing + stop calc. `stop = entry − (mult × ATR)`. Enforces risk budget, allocation caps, dry-powder floor. (Old Agent 4A LLM-stops eliminated.) | `output/agent4_orders.json` |
| **5 — Position Monitor** | `agent5_position_monitor.py` | LLM (you) | Afternoon thesis review of open positions → HOLD/TRIM/CLOSE. Also owns breakeven/profit-lock trailing logic. | `output/agent5_decisions.json` |

**Execution layer:** `execution_engine.py` + `robinhood_broker.py` (via `broker_factory.get_broker()`). Robinhood MCP has **no native bracket/OTO orders**, so the execution engine is a *local clearinghouse*: it records intents in a SQLite ledger, polls fills every ~15s, and **places the stop the instant the entry fills**.

### Agent 4 stop philosophy (this is what Jamie asked about 2026-07-01)
Fresh entries get an **ATR-volatility stop BELOW the buy price** (e.g. 1.5×ATR ≈ 5–9% below). A stop *at* the buy price would trigger on the first tick of normal noise. The stop only rides **up to / above breakeven** once the trade is in profit — that's Agent 5's trailing logic:
- **Breakeven** at **+2.5%** (was +1%, loosened 2026-06-30 — was scratching new positions out on a single tick).
- **Profit-lock tiers** at +3% / +5% / +10% / +15%.

---

## 2. Scheduled Jobs — the heartbeat

### 2a. OpenClaw crons (agent turns → post to #trading)
Run `/opt/homebrew/bin/openclaw cron list` to see them. All owned by agent `zuck` (must be re-pointed to Elon after migration). Full prompt text lives in each cron's payload — **preserve these prompts verbatim when migrating**; they *are* the runbook.

| Cron | ID | Schedule (ET, weekdays) | What it does |
|---|---|---|---|
| **open-claw-morning** | `567121a0-…` | 8:00 AM | The full pipeline. **STEP 0 = proxy/token preflight guard** → aborts + alerts if model path unhealthy (no trades on a bad path). Then Agents 1→4 + broker execution. Timeout 2400s. |
| **open-claw-stop-guard** | `3646e8b9-…` | 9:45 AM | Runs `reconcile_positions.py` ~15min after open → ensures every live position has a stop. Heals naked positions. Timeout 600s. |
| **open-claw-monitor** | `4e6c7fd6-…` | 3:30 PM | Agent 5 afternoon monitor → HOLD/TRIM/CLOSE + execution. Timeout 300s. |
| **open-claw-eod-stop-digest** | `82ff2495-…` | 4:00 PM | `run_eod_digest.sh` — recap of the day's trailing-stop moves. Posts verbatim. Silent if 0 runs. |
| **open-claw-weekly-review** | `47a07968-…` | Fri 4:00 PM | Portfolio vs SPY weekly perf, alpha, P&L. (Note: still references `AlpacaBroker` in step 1 — **stale, needs fixing** to Robinhood.) |
| **open-claw-daemon-watchdog** | `6ee0c28e-…` | every 3 min, 9–16h | `daemon_watchdog.py --alert-gate`. Silent on OK; alerts #trading if the execution daemon is down. |

**Cron alert etiquette (important):** these crons are built to be **silent on healthy/clean runs** (reply `NO_REPLY`) and only post when something is healed or wrong. Don't announce clean runs.

### 2b. launchd timers (macOS, run pure Python — no gateway needed)
- **`com.cb.trading-prewarm`** — 7:55 AM weekdays. Runs `preflight_proxy_guard.py` as pure Python to force-warm the Claude token + local proxy 5 min before the 8 AM cron. Log: `~/Library/Logs/trading-prewarm.log`.
- **`com.openclaw.reinforce-HHMM`** (12 jobs, 10:00–15:30 every 30 min) — run `orchestrator.py hourly` = mechanical trailing-stop ratchet + stop-hit execution. **No thesis review** (that's the 3:30 monitor). Script: `run_hourly_reinforce.sh`. Real-time pricing via **Tiingo**.
- **`com.cb.execution-daemon-watchdog`** — keeps the watchdog alive.

### 2c. Always-on daemons (KeepAlive wrapper scripts, restart on crash)
- **Execution daemon** — `run_execution_daemon.sh` → `run_execution_daemon.py` → `execution_engine.py`. Internal 15s reconcile loop: polls order status, places stop on fill, panic-liquidates on stop breach. Writes heartbeat to `output/daemon_heartbeat.txt`. launchd: `com.openclaw.execution-daemon`.
- **Flash-crash daemon** — `run_flash_daemon.sh` → `flash_crash_daemon.py`. Polls every ~7 min during market hours; intraday crash safety net. launchd: `com.openclaw.flash-daemon`.

> ⚠️ **Python version gotcha:** the daemons + hourly reinforce are **pinned to `/usr/bin/python3` (3.9.6)** because that interpreter has all deps (`filelock`, `google.generativeai`). Homebrew's python3 is missing them and silently killed stop execution. Do **not** switch interpreters. Also: no `X | None` annotations at def-eval time on 3.9 — use `typing.Optional`.

---

## 3. Safety Nets (the "never naked" system)

Three independent layers, because a position without a stop is the one failure mode that actually loses money:

1. **Execution engine** places the stop the instant an entry fills (fill→stop→ledger, atomic).
2. **`reconcile_positions.py`** (`open-claw-stop-guard` cron @ 9:45 AM, plus run manually anytime) — self-healing guard. Checks EVERY live broker position, detects naked ones via **live broker ORDERS** (not the ledger — the ledger going out of sync IS the failure mode), resolves the stop from `ledger.target_stop → agent4_orders.json → portfolio_state.hwm_stop`, places a GTC stop + ledgers it. **Exit 2 = couldn't protect something → urgent.** Run: `python3 reconcile_positions.py [--dry-run]`.
3. **Daemon watchdog** (`daemon_watchdog.py`, cron every 3 min) — alerts if the execution daemon itself dies.

**Root incident this guards against (2026-06-30, ITUB):** a pre-market/manual entry placed *outside* the execution engine's fill→stop→ledger flow leaves the position naked (no `active_trades` row → monitor logs "No active trade found to trail" → no stop). Jamie caught it manually; the reconcile guard now heals it automatically.

---

## 4. State & Data Files

| File | What |
|---|---|
| `output/execution_ledger.db` | SQLite. Table **`active_trades`** = the truth for open trades: `ticker, avg_fill_price, target_stop_price, stop_order_id, stop_status, close_reason`. Also `execution_log`, `execution_incidents`. |
| `output/portfolio_state.json` | Per-ticker trailing state: `hwm_stop`, `hwm_price`, `scaled_fraction`. Agent 5 reads/writes this. |
| `output/agent{1,2,3}_*.json`, `output/agent4_orders.json`, `output/agent5_*.json` | Per-stage pipeline artifacts (regenerated each run; archived under `output/archive/<timestamp>/`). |
| `output/daemon_heartbeat.txt` | Execution daemon heartbeat (stale >60s = daemon wedged). |
| `output/logs/*.log` | Daemon + reinforce logs. |

**Manual stop edit recipe** (what I did for AMD 2026-07-01): (1) find the live stop order id via `broker.get_orders(symbol=…)`, (2) check the live quote so you don't place a stop above market (instant trigger), (3) `broker.cancel_order(id)`, (4) `broker.place_stop(ticker, qty, price, time_in_force='gtc')`, (5) **update BOTH** the ledger `active_trades` row (`target_stop_price`, `stop_order_id`) **and** `portfolio_state.json` `hwm_stop` so Agent 5 doesn't revert it.

---

## 5. Broker / Config

- **Broker:** Robinhood only, via MCP. `broker_factory.get_broker()` (process-cached singleton — the MCP handshake is expensive, don't build per-call). Interface: `get_positions`, `get_orders(state, symbol)`, `get_quote`, `place_order`, `place_stop(ticker, qty, stop_price, tif='gtc')`, `cancel_order`, `execute_tear_sheet`, `execute_agent5_decisions`, `close_position`, `close_all_positions`, `get_account_summary`.
- **Auth:** `robinhood-mcp/token.json` must exist or the factory fails loud. Re-auth Robinhood if it's missing.
- **Market data:** **Tiingo** (primary real-time, `TIINGO_API_KEY`), Schwab market-data API (`SCHWAB_APP_KEY/SECRET`) for cross-ref, yfinance for weekly SPY compare.
- **`.env`** holds: `GOOGLE_API_KEY` (Gemini/Agent 2), `TIINGO_API_KEY`, `SCHWAB_*`, `MASSIVE_API_KEY`, `BROKER`, `X_BEARER_TOKEN` (unused now). **Never commit `.env`** (gitignored).
- **Account snapshot (2026-07-01):** equity ~$9,945, cash ~$3,301, positions BAC/KVUE/ITUB/AMD. Inception baseline ~$10k on 2026-05-22.

---

## 6. Model-path resilience (why the 8 AM cron sometimes died)

The agent runs through a **local proxy on `127.0.0.1:18801`** that borrows a Claude OAuth token (Claude Max). If the token refresh loop hiccups overnight, the gateway→proxy call times out and the whole 8 AM run dies instantly (~1.5s = couldn't reach proxy). Guards:
- **`preflight_proxy_guard.py`** — force-refreshes token if <10min left, health-checks the proxy with backoff `[0,5,15,30,60]`, tests two models. Exit 0=healthy / 2=proxy dead / 3=token dead. Run: `python3 preflight_proxy_guard.py --json`.
- It's wired as **STEP 0** of the morning cron (abort + alert on failure) AND run third-partyly at **7:55 AM** by `com.cb.trading-prewarm` launchd (pure Python, no gateway) to pre-warm.

> **Migration note for Elon/Hermes:** Hermes calls `api.anthropic.com` directly (metered) rather than the OAuth proxy in some setups. If Elon runs off the direct paid API, the proxy-guard STEP 0 logic can be simplified/removed — but keep *some* preflight so a bad model path aborts before placing trades. Confirm Hermes' model routing before trusting the 8 AM run unattended.

---

## 7. Migration Checklist (OpenClaw/Zuck → Hermes/Elon)

- [ ] **Re-own the 6 crons** to Elon (or recreate them in Hermes' scheduler) — copy each cron's payload prompt *verbatim*; they encode the runbook.
- [ ] **Fix stale Alpaca ref** in `open-claw-weekly-review` step 1 → use `broker_factory.get_broker()` (Robinhood), not `AlpacaBroker`.
- [ ] **Keep the 3 launchd daemons/timers running** (they're user-level launchd, machine-bound — they run regardless of which agent is "the brain"): execution daemon, flash daemon, hourly reinforce, trading-prewarm, watchdog.
- [ ] **Confirm Elon's model routing** and adjust the proxy-guard STEP 0 accordingly (see §6).
- [ ] **Point all reports to `#trading`** (`C0B45KX7T2B`), never a DM.
- [ ] **Preserve the "silent on clean run" etiquette** for the guard/watchdog/digest crons.
- [ ] **Verify Robinhood auth** (`robinhood-mcp/token.json`) is valid on the machine Elon runs on.
- [ ] **Always push code to GitHub** after changes (`origin` = open-claw; Jamie's standing request).

---

## 8. Quick command reference

```bash
cd /Users/chris/code/trading-pipeline

# Health / safety
python3 reconcile_positions.py --dry-run     # check every position has a stop
python3 daemon_watchdog.py --alert-gate      # is the execution daemon alive?
python3 preflight_proxy_guard.py --json      # is the model path healthy?

# State
python3 -c "import sqlite3;c=sqlite3.connect('output/execution_ledger.db');[print(dict(zip([d[0] for d in c.execute('select * from active_trades limit 0').description], r))) for r in c.execute('select ticker,avg_fill_price,target_stop_price,stop_order_id,stop_status,close_reason from active_trades')]"
cat output/portfolio_state.json

# Broker
python3 -c "from broker_factory import get_broker;b=get_broker();print(b.get_account_summary());print(b.get_positions())"
python3 -c "from broker_factory import get_broker;b=get_broker();[print(o['symbol'],o['side'],o.get('stop_price'),o['state']) for o in b.get_orders() if o.get('stop_price') and o['state']=='confirmed']"

# Crons
/opt/homebrew/bin/openclaw cron list
/opt/homebrew/bin/openclaw cron get <id>

# Manual pipeline stages (see each cron payload for the exact one-liners)
python3 orchestrator.py hourly               # mechanical trailing-stop pass
```

---

*If in doubt: protect the position first (place/verify a stop), report to #trading, then figure out the rest. Losing money to a naked position is the only unforgivable failure here.*
