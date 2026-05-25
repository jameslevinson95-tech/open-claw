# Open Claw Trading Pipeline — Full Codebase
# Generated: Sat May 23 22:51:04 EDT 2026

# Total: 19 Python files, ~7431 lines

==================================================================
FILE: config.py (     112 lines)
==================================================================
"""
Trading Pipeline Configuration — "Golden Path" v2
Incorporates Jamie's finalized tweaks.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Account
ACCOUNT_SIZE = 100_000  # $100K paper trading account
DRY_POWDER_FLOOR = 0.20  # Never deploy beyond 80%

# Alpaca
ALPACA_USERNAME = "jameslevinson95@gmail.com"
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # Paper trading first

# LLM Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # For Gemini (Agent 2)

# Telegram Output
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5238217629")

# Schedule (ET) — Golden Path timing
PREFLIGHT_TIME = "07:55"       # Python pre-flight data fetch
AGENT1_TIME = "08:00"          # Agent 1 - Macro Director
AGENT2_TIME = "08:01"          # Agent 2 - Fundamental Screener
AGENT3_TIME = "08:15"          # Agent 3 - Signal Verifier (Smart Money)
AGENT4_TIME = "08:17"          # Agent 4a/4b - Risk Manager
TEARSHEET_TIME = "08:18"       # Deliver tear sheet
AGENT5_PREFLIGHT_TIME = "15:25"  # Agent 5 pre-flight price snapshot
AGENT5_TIME = "15:30"          # Agent 5 - Position Monitor

# Risk Parameters
PER_TRADE_RISK_CAP = 1500.00   # $1,500 max risk per trade (1.5% of $100K)
SESSION_RISK_BUDGET = 10000.00  # $10,000 max session risk (10% of $100K)
THEME_CAP = 1                  # Max 1 position per theme per session (tweak #5)

# Screener Rules
SCREENER_MIN_MARKET_CAP = 100_000_000  # $100M minimum
SCREENER_MIN_PRICE = 5.00              # > $5

# Position Sizing — Risk-First Model (v3)
# Sizing starts from RISK DOLLARS, derives shares from stop distance,
# then floors with allocation cap. Binding constraint is logged.

# Posture table (regime -> posture + conviction floor)
POSTURE_TABLE = {
    "Risk-On":          {"posture": "Aggressive",  "conviction_floor": 5},
    "Cautious Risk-On": {"posture": "Offensive",   "conviction_floor": 6},
    "Risk-Off":         {"posture": "Defensive",   "conviction_floor": 7},
    "Crisis":           {"posture": "Bunker",      "conviction_floor": 9},
}

# Risk-first sizing constants
BASE_RISK = 1500               # Per-trade $ at neutral conviction
MAX_RISK_PER_TRADE = 2000      # Hard ceiling regardless of multiplier stack
MIN_RISK_PER_TRADE = 500       # Below this, skip (regime says don't trade)
MAX_ALLOCATION_PCT = 0.25      # Share-count cap as % of account

# Tier risk multipliers (replaces numeric conviction_mod)
TIER_RISK_MULT = {
    "PASS": 0.70,
    "STRONG": 1.00,
    "EXCEPTIONAL": 1.20,
}

# Confirm bonus from Agent 3 CONFIRM_ENHANCED verdict
CONFIRM_RISK_MULT = {True: 1.10, False: 1.00}

# Vol regime risk multipliers
VOL_RISK_MULT = {
    "Compressed": 1.10,
    "Normal": 1.00,
    "Elevated": 0.70,
    "Stressed": 0.40,
}

# Posture risk multipliers
POSTURE_RISK_MULT = {
    "Aggressive": 1.00,
    "Offensive": 0.80,
    "Defensive": 0.40,
    "Bunker": 0.00,
}

# Legacy aliases (kept for backward compat, will deprecate)
BASE_ALLOCATION_CAP = 0.15
VOL_REGIME_MOD = VOL_RISK_MULT
CONVICTION_MOD = {}  # Deprecated — use TIER_RISK_MULT

# Curated smart money Twitter/X accounts for Agent 3
SMART_MONEY_ACCOUNTS = [
    # Add Twitter/X handles here when API is set up
    # e.g., "unusual_whales", "DeItaone", "zaborsky", etc.
]

# Portfolio Heat Cap
MAX_PORTFOLIO_HEAT_PCT = 0.06   # 6% of equity — reject all new trades above this
HEAT_WARNING_PCT = 0.04         # 4% — allow trades but print warning

# FRED API key (for MOVE index, credit data)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# Massive (Polygon-compatible) Market Data API
# Free tier: historical bars, technical indicators (SMA, EMA, RSI, MACD), 5 calls/min
MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")


==================================================================
FILE: orchestrator.py (     638 lines)
==================================================================
"""
Open Claw Orchestrator — "Golden Path" v2
Runs the full 5-agent pipeline in sequence.

Schedule (ET):
  7:55 AM  — Pre-flight: macro data, screener universe, prior closes
  8:00 AM  — Agent 1 (Claude): Regime classification
  8:01 AM  — Agent 2 (Gemini 3.1 Pro): Fundamental screening
  8:05 AM  — Agent 3 (Claude): Qualitative synthesis (news + options + SI + smart money X)
  8:17 AM  — Agent 4A (Claude): Stop anchors + 4B (Python): Position sizing
  8:18 AM  — Deliver tear sheet
  3:25 PM  — Agent 5 pre-flight: Price snapshot
  3:30 PM  — Agent 5 (Claude): Position monitoring

Usage:
  python3 orchestrator.py morning    # Run Agents 1-4 (morning entry pipeline, Agent 2.5 merged into 3)
  python3 orchestrator.py monitor    # Run Agent 5 (afternoon position monitor)
  python3 orchestrator.py full       # Run morning + schedule monitor for 3:30 PM
  python3 orchestrator.py test       # Dry run with verbose output
"""
import json
import os
import sys
from datetime import datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from preflight import run_preflight, format_macro_for_prompt
from agent1_macro_director import run_agent1, format_directive_for_telegram
from agent2_fundamental_screener import run_agent2, format_agent2_for_telegram
from agent3_synthesizer import run_agent3, format_agent3_for_slack
from agent4_risk_manager import run_agent4, generate_tear_sheet
from agent5_position_monitor import run_agent5, run_agent5_preflight, format_agent5_for_telegram
from broker import AlpacaBroker
from trade_journal import log_close, build_trade_record
from watchlist import Watchlist, promote_ready_candidates
from vwap_gate import check_vwap, vwap_gate
from safeguards import (
    is_market_open_today,
    send_telegram,
    send_crash_alert,
    send_market_closed_alert,
    send_pipeline_start_alert,
    send_pipeline_complete_alert,
    send_hb_signal,
    add_to_penalty_box,
    tick_penalty_box,
    filter_cooldown_tickers,
    filter_earnings_tickers,
    cap_shares_by_volume,
)


def fetch_x_smart_money(tickers: list) -> dict:
    """
    Fetch smart money X/Twitter mentions for the given tickers.
    Uses the official X Developer API via x_fetch.py.
    7-day lookback, filtered by CURATED_ACCOUNTS (43 accounts).
    """
    from x_fetch import run_x_fetch
    
    print(f"[Orchestrator] Fetching X/Twitter smart money data for: {tickers}")
    result = run_x_fetch(tickers)
    return result.get("mentions", {})


# Discord is OUTPUT ONLY — used to deliver Tear Sheets and Agent 5 alerts.
# NO Discord scraping for sentiment input. All sentiment comes from X API.
# discord_fetch.py exists but is NOT called in the pipeline flow.


def run_morning_pipeline(verbose: bool = False) -> dict:
    """
    Run the full morning entry pipeline: Pre-flight → Agent 1 → 2 → 3 → 4.
    Returns the final tear sheet and all intermediate results.
    """
    results = {}
    pipeline_errors = []  # Track errors for hb_signal
    
    print("=" * 50)
    print("🌅 OPEN CLAW — MORNING ENTRY PIPELINE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)
    
    # ━━━ STEP 0: MARKET CALENDAR CHECK ━━━
    print("\n" + "━" * 40)
    print("📅 STEP 0: MARKET CALENDAR CHECK")
    print("━" * 40)
    
    calendar = is_market_open_today()
    print(f"  Market open: {calendar.get('is_open')}")
    print(f"  Should run: {calendar.get('should_run')}")
    print(f"  Reason: {calendar.get('reason')}")
    
    if not calendar.get("should_run", True):
        print("\n⚠️ Market is CLOSED today. Halting pipeline gracefully.")
        send_market_closed_alert()
        return {"halted": True, "reason": calendar.get("reason")}
    
    # Send pipeline start notification
    send_pipeline_start_alert()
    
    # ━━━ STEP 1: PRE-FLIGHT (7:55 AM) ━━━
    print("\n" + "━" * 40)
    print("📡 STEP 1: PRE-FLIGHT DATA FETCH")
    print("━" * 40)
    
    try:
        # Tick the penalty box (decrement cooldowns)
        tick_penalty_box()
        
        preflight_data = run_preflight()
        screener = preflight_data.get('screener_universe', [])
        
        # Filter out cooled-down tickers (whipsaw prevention)
        screener = filter_cooldown_tickers(screener)
        
        # Filter out tickers with upcoming earnings (binary event prevention)
        screener, earnings_removed = filter_earnings_tickers(screener)
        if earnings_removed:
            results["earnings_filtered"] = earnings_removed
        
        preflight_data['screener_universe'] = screener
        results["preflight"] = {"success": True, "data": preflight_data}
        print(f"✅ Pre-flight complete: {len(screener)} screener tickers (post-filters)")
    except Exception as e:
        print(f"❌ Pre-flight FAILED: {e}")
        send_crash_alert("Pre-Flight", e)
        pipeline_errors.append(f"preflight: {e}")
        results["preflight"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 2: AGENT 1 — MACRO DIRECTOR (8:00 AM) ━━━
    print("\n" + "━" * 40)
    print("🌍 STEP 2: AGENT 1 — MACRO DIRECTOR")
    print("━" * 40)
    
    try:
        agent1_result = run_agent1(preflight_data["macro"])
        results["agent1"] = agent1_result
        
        if agent1_result.get("success"):
            directive = agent1_result["directive"]
            print(format_directive_for_telegram(agent1_result))
            
            # Save directive
            with open("output/agent1_directive.json", "w") as f:
                json.dump(directive, f, indent=2)
            
            # Check for DEFER
            if directive.get("regime") == "DEFER":
                print("\n⚠️ REGIME: DEFER — Pipeline halted. Missing critical data.")
                return results
        elif agent1_result.get("needs_subagent"):
            print("⏳ Agent 1 needs subagent execution (no Anthropic API key)")
            print("   Run via OCPlatform: the agent will handle Claude calls")
            return results
        else:
            print(f"❌ Agent 1 FAILED: {agent1_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 1 FAILED: {e}")
        send_crash_alert("Agent 1 (Macro Director)", e)
        pipeline_errors.append(f"agent1: {e}")
        results["agent1"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 3: AGENT 2 — FUNDAMENTAL SCREENER (8:01 AM) ━━━
    print("\n" + "━" * 40)
    print("🔍 STEP 3: AGENT 2 — FUNDAMENTAL SCREENER")
    print("━" * 40)
    
    try:
        agent2_result = run_agent2(directive, preflight_data["screener_universe"])
        results["agent2"] = agent2_result
        
        if agent2_result.get("success"):
            candidates = agent2_result.get("candidates", [])
            print(format_agent2_for_telegram(agent2_result))
            
            # Save candidates
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(agent2_result, f, indent=2, default=str)
            
            if not candidates:
                print("\n📋 No candidates passed screening. Pipeline complete — no trades today.")
                return results
        else:
            print(f"❌ Agent 2 FAILED: {agent2_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 2 FAILED: {e}")
        send_crash_alert("Agent 2 (Fundamental Screener)", e)
        pipeline_errors.append(f"agent2: {e}")
        results["agent2"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 3.1: WATCHLIST BENCH ━━━
    print("\n" + "━" * 40)
    print("📋 STEP 3.1: WATCHLIST BENCH")
    print("━" * 40)
    
    try:
        wl = Watchlist()
        # Prune stale entries (>5 trading days)
        pruned = wl.prune()
        if pruned:
            print(f"  🗑️  Pruned stale watchlist entries: {', '.join(pruned)}")
        
        # Add all Agent 2 candidates to the watchlist
        for c in candidates:
            result = wl.add(c)
            status = result.get('status', 'unknown')
            ticker = result.get('ticker', c.get('ticker', '?'))
            if status == 'added':
                ema = result.get('ema_20', '?')
                print(f"  ➕ {ticker} added to watchlist (20 EMA: {ema})")
            elif status == 'already_on_watchlist':
                print(f"  ⏩ {ticker} already on watchlist")
        
        # Check which watchlist entries are at entry zones
        ready_entries = wl.check_entries()
        all_entries = wl.get_all()
        
        print(f"\n  📊 Watchlist: {len(all_entries)} total, {len(ready_entries)} READY at entry zone")
        
        for entry in all_entries:
            status_icon = "🟢" if entry.get('status') == 'READY' else "🔴"
            pct = entry.get('pct_above_ema', '?')
            print(f"  {status_icon} {entry['ticker']}: {pct}% above 20 EMA — {entry.get('status', 'WATCHING')}")
        
        if ready_entries:
            # Only pass READY candidates forward (in Agent 2 format)
            ready_candidates = promote_ready_candidates()
            # Replace candidates with only the READY ones
            candidates = ready_candidates
            agent2_result = dict(agent2_result)
            agent2_result["candidates"] = candidates
            print(f"\n  ✅ Promoting {len(candidates)} READY candidates to Agent 3")
        else:
            print("\n  ⏸️  No watchlist candidates at entry zones today. Ideas saved for later.")
            return results
        
        results["watchlist"] = {"success": True, "total": len(all_entries), "ready": len(ready_entries)}
    except Exception as e:
        print(f"⚠️ Watchlist bench error (non-fatal): {e}")
        # On watchlist failure, fall through with original candidates
        results["watchlist"] = {"success": False, "error": str(e)}
    
    # ━━━ STEP 3.5: X/TWITTER SMART MONEY FETCH ━━━
    print("\n" + "━" * 40)
    print("🐦 STEP 3.5: X/TWITTER SMART MONEY FETCH")
    print("━" * 40)
    
    tickers = [c.get("ticker") for c in candidates]
    
    try:
        x_mentions = fetch_x_smart_money(tickers)
        results["x_fetch"] = {"success": True}
    except RuntimeError as e:
        print(f"⚠️ {e}")
        print("\n🔧 Agent 3 requires X data. Pipeline paused here.")
        print("   Once X data is available, re-run from Agent 3.")
        results["x_fetch"] = {"success": False, "error": str(e)}
        with open("output/pipeline_state.json", "w") as f:
            json.dump({
                "stopped_at": "agent3_x_fetch",
                "tickers_needed": tickers,
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2)
        return results
    # Discord is OUTPUT ONLY — no sentiment scraping from Discord channels
    
    # ━━━ STEP 4: AGENT 3 — QUALITATIVE SYNTHESIZER (8:05 AM) ━━━
    print("\n" + "━" * 40)
    print("🧪 STEP 4: AGENT 3 — QUALITATIVE SYNTHESIZER")
    print("━" * 40)
    
    try:
        agent3_result = run_agent3(agent2_result, x_mentions)
        results["agent3"] = agent3_result
        
        if agent3_result.get("success"):
            print(format_agent3_for_slack(agent3_result))
            
            # Replace agent2_result with the synthesis-filtered version
            if agent3_result.get("updated_agent2_result"):
                agent2_result = agent3_result["updated_agent2_result"]
                candidates = agent2_result.get("candidates", [])
            
            with open("output/agent3_verified.json", "w") as f:
                json.dump(agent3_result, f, indent=2, default=str)
            # Overwrite agent2 candidates with filtered set
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(agent2_result, f, indent=2, default=str)
            
            if not candidates:
                print("\n🚫 All candidates vetoed by qualitative synthesis. No trades today.")
                return results
        elif agent3_result.get("needs_subagent"):
            print("⏳ Agent 3 needs subagent execution (no Anthropic API key)")
            return results
        else:
            print(f"❌ Agent 3 FAILED: {agent3_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 3 FAILED: {e}")
        send_crash_alert("Agent 3 (Synthesizer)", e)
        pipeline_errors.append(f"agent3: {e}")
        results["agent3"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 5: AGENT 4 — RISK MANAGER (8:17 AM) ━━━
    print("\n" + "━" * 40)
    print("🛡️ STEP 5: AGENT 4 — RISK MANAGER")
    print("━" * 40)
    
    try:
        agent4_result = run_agent4(agent2_result, agent3_result, directive)
        results["agent4"] = agent4_result
        
        if agent4_result.get("success"):
            tear_sheet = agent4_result.get("tear_sheet", "")
            print(tear_sheet)
            
            with open("output/agent4_orders.json", "w") as f:
                json.dump(agent4_result, f, indent=2, default=str)
            
            # Save tear sheet as text
            with open("output/tear_sheet.txt", "w") as f:
                f.write(tear_sheet)
            
            print(f"\n📋 Tear sheet saved to output/tear_sheet.txt")
        elif agent4_result.get("needs_subagent"):
            print("⏳ Agent 4A needs subagent execution (no Anthropic API key)")
            return results
        else:
            print(f"❌ Agent 4 FAILED: {agent4_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 4 FAILED: {e}")
        results["agent4"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 6: EXECUTE TRADES ON ALPACA (9:30 AM) ━━━
    print("\n" + "━" * 40)
    print("💰 STEP 6: BROKER EXECUTION — ALPACA")
    print("━" * 40)
    
    trade_orders = agent4_result.get("trade_orders", [])
    buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
    
    if not buy_orders:
        print("📋 No BUY orders in tear sheet — nothing to execute.")
    else:
        # ━━━ VWAP GATE ━━━
        print("\n  🔒 VWAP Gate: Checking intraday VWAP for BUY orders...")
        approved_orders, rejected_orders = vwap_gate(trade_orders)
        
        if rejected_orders:
            print(f"  ❌ VWAP Rejected ({len(rejected_orders)}):")
            for r in rejected_orders:
                print(f"     {r['ticker']}: {r.get('reject_reason')} "
                      f"(price vs VWAP: {r.get('vwap_pct', '?')}%)")
        
        approved_buys = [o for o in approved_orders if o.get('action') == 'BUY']
        if not approved_buys:
            print("  📋 All BUY orders rejected by VWAP gate — nothing to execute.")
        else:
            print(f"  ✅ VWAP Approved: {len(approved_buys)} BUY order(s)")
        
        trade_orders = approved_orders  # only execute approved
        buy_orders = approved_buys
        
        if not buy_orders:
            print("📋 No BUY orders passed VWAP gate — nothing to execute.")
        else:
            try:
                broker = AlpacaBroker()
                fills = broker.execute_tear_sheet(trade_orders)
                results["broker"] = {"success": True, "fills": fills}
            
                submitted = [f for f in fills if f.get("status") == "submitted"]
                skipped = [f for f in fills if f.get("status") == "skipped"]
                errors = [f for f in fills if f.get("status") == "error"]
                
                print(f"\n📊 Broker Results:")
                print(f"  ✅ Submitted: {len(submitted)}")
                print(f"  ⏭️  Skipped:   {len(skipped)}")
                print(f"  ❌ Errors:    {len(errors)}")
                
                for f in errors:
                    print(f"     {f['ticker']}: {f.get('error', 'unknown')}")
            except Exception as e:
                print(f"❌ Broker execution FAILED: {e}")
                results["broker"] = {"success": False, "error": str(e)}
    
    # ━━━ DONE ━━━
    print("\n" + "=" * 50)
    print("✅ MORNING PIPELINE COMPLETE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("📈 Trades submitted to Alpaca paper trading.")
    print("🕒 Agent 5 will run at 3:30 PM to monitor positions.")
    print("=" * 50)
    
    # Send completion alert
    send_pipeline_complete_alert(results)
    
    return results


def run_afternoon_monitor(verbose: bool = False) -> dict:
    """Run Agent 5: Afternoon position monitoring."""
    print("=" * 50)
    print("🕒 OPEN CLAW — AFTERNOON POSITION MONITOR")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)
    
    # Pre-flight snapshot (3:25 PM)
    print("\n" + "━" * 40)
    print("📸 AGENT 5 PRE-FLIGHT: PRICE SNAPSHOT")
    print("━" * 40)
    
    try:
        preflight = run_agent5_preflight()
        
        if not preflight["positions"]:
            print("📋 No open positions to monitor.")
            return {"agent5": {"success": True, "note": "No positions"}}
    except Exception as e:
        print(f"❌ Agent 5 pre-flight FAILED: {e}")
        return {"agent5": {"success": False, "error": str(e)}}
    
    # Agent 5 (3:30 PM)
    print("\n" + "━" * 40)
    print("🕒 AGENT 5: POSITION MONITOR")
    print("━" * 40)
    
    try:
        agent5_result = run_agent5(preflight["positions"], preflight["snapshot"])
        
        if agent5_result.get("success"):
            print(format_agent5_for_telegram(agent5_result))
            
            with open("output/agent5_decisions.json", "w") as f:
                json.dump(agent5_result, f, indent=2, default=str)
            
            # ━━━ EXECUTE AGENT 5 DECISIONS ON ALPACA ━━━
            decisions = agent5_result.get("decisions", [])
            crisis = agent5_result.get("crisis_liquidation", False)
            actionable = [d for d in decisions if d.get("action") in ("CLOSE", "TRIM")] or crisis
            
            if actionable:
                print("\n" + "━" * 40)
                print("💰 BROKER EXECUTION — AGENT 5 DECISIONS")
                print("━" * 40)
                
                try:
                    broker = AlpacaBroker()
                    exec_results = broker.execute_agent5_decisions(decisions, crisis=crisis)
                    agent5_result["broker_results"] = exec_results
                    
                    # Load directive for trade journal
                    directive = {}
                    directive_path = "output/agent1_directive.json"
                    if os.path.exists(directive_path):
                        with open(directive_path) as f:
                            directive = json.load(f)
                    
                    snapshot = preflight.get("snapshot", {})
                    
                    for r in exec_results:
                        action = r.get("action", "unknown")
                        ticker = r.get("ticker", "ALL")
                        status = r.get("status", "unknown")
                        print(f"  [{action}] {ticker} — {status}")
                        
                        # Log closed trades to journal + penalty box for losses
                        if r.get("status") == "submitted" and r.get("action") in ("close", "trim", "close_all"):
                            pos_data = next((p for p in preflight["positions"] if p["ticker"] == r["ticker"]), {})
                            ticker_snap = snapshot.get(r["ticker"], {})
                            exit_price = ticker_snap.get("current_price", 0)
                            if pos_data and exit_price:
                                try:
                                    record = build_trade_record(
                                        trade_order=pos_data,
                                        directive=directive,
                                        agent3_verification={},
                                        exit_price=exit_price,
                                        exit_reason=f"Agent 5 {r['action']}",
                                    )
                                    log_close(record)
                                    print(f"  📝 Logged {r['ticker']} to trade journal")
                                    
                                    # Add to penalty box if closed for a loss
                                    unrealized_pl = pos_data.get("unrealized_pl", 0)
                                    if unrealized_pl < 0:
                                        add_to_penalty_box(
                                            r["ticker"],
                                            abs(unrealized_pl),
                                            reason=f"Agent 5 {r['action']}",
                                        )
                                except Exception as je:
                                    print(f"  ⚠️ Journal log failed for {r['ticker']}: {je}")
                except Exception as e:
                    print(f"❌ Broker execution FAILED: {e}")
                    agent5_result["broker_error"] = str(e)
            else:
                print("\n📋 All positions HOLD — no broker action needed.")
        elif agent5_result.get("needs_subagent"):
            print("⏳ Agent 5 needs subagent execution (no Anthropic API key)")
        else:
            print(f"❌ Agent 5 FAILED: {agent5_result.get('error')}")
        
        # Send EOD hb_signal
        try:
            broker = AlpacaBroker()
            positions = broker.get_positions()
            account = broker.get_account_summary()
            
            # Calculate portfolio heat
            total_risk = sum(abs(p.get("unrealized_pl", 0)) for p in positions if p.get("unrealized_pl", 0) < 0)
            equity = account.get("equity", 100000)
            heat = (total_risk / equity * 100) if equity > 0 else 0
            
            send_hb_signal(positions=positions, portfolio_heat=heat)
        except Exception as he:
            print(f"\u26a0\ufe0f hb_signal send failed: {he}")
            send_hb_signal(errors=[str(he)])
        
        return {"agent5": agent5_result}
    except Exception as e:
        print(f"❌ Agent 5 FAILED: {e}")
        send_crash_alert("Agent 5 (Position Monitor)", e)
        return {"agent5": {"success": False, "error": str(e)}}


def resume_from_agent3(verbose: bool = False) -> dict:
    """
    Resume pipeline from Agent 3 (after X data has been fetched).
    Loads Agent 1 directive and Agent 2 candidates from saved files.
    """
    print("=" * 50)
    print("🔄 OPEN CLAW — RESUMING FROM AGENT 3")
    print("=" * 50)
    
    # Load saved state
    directive_path = "output/agent1_directive.json"
    candidates_path = "output/agent2_candidates.json"
    mentions_path = "output/smart_money_mentions.json"
    
    for path, name in [(directive_path, "Agent 1 directive"), 
                        (candidates_path, "Agent 2 candidates"),
                        (mentions_path, "Smart money X data")]:
        if not os.path.exists(path):
            print(f"❌ Missing {name}: {path}")
            return {"error": f"Missing {name}"}
    
    with open(directive_path) as f:
        directive = json.load(f)
    with open(candidates_path) as f:
        agent2_result = json.load(f)
    with open(mentions_path) as f:
        x_mentions = json.load(f)
    
    # Run Agent 3
    print("\n" + "━" * 40)
    print("🧪 AGENT 3 — QUALITATIVE SYNTHESIZER")
    print("━" * 40)
    
    agent3_result = run_agent3(agent2_result, x_mentions)
    if not agent3_result.get("success"):
        print(f"❌ Agent 3 FAILED: {agent3_result.get('error')}")
        return {"agent3": agent3_result}
    
    print(format_agent3_for_slack(agent3_result))
    
    # Update agent2_result with synthesis-filtered candidates
    if agent3_result.get("updated_agent2_result"):
        agent2_result = agent3_result["updated_agent2_result"]
    
    with open("output/agent3_verified.json", "w") as f:
        json.dump(agent3_result, f, indent=2, default=str)
    with open("output/agent2_candidates.json", "w") as f:
        json.dump(agent2_result, f, indent=2, default=str)
    
    # Run Agent 4
    print("\n" + "━" * 40)
    print("🛡️ AGENT 4 — RISK MANAGER")
    print("━" * 40)
    
    agent4_result = run_agent4(agent2_result, agent3_result, directive)
    if agent4_result.get("success"):
        print(agent4_result.get("tear_sheet", ""))
        with open("output/agent4_orders.json", "w") as f:
            json.dump(agent4_result, f, indent=2, default=str)
        with open("output/tear_sheet.txt", "w") as f:
            f.write(agent4_result.get("tear_sheet", ""))
        
        # Execute trades on Alpaca
        trade_orders = agent4_result.get("trade_orders", [])
        buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
        if buy_orders:
            print("\n" + "━" * 40)
            print("💰 BROKER EXECUTION — ALPACA")
            print("━" * 40)
            try:
                broker = AlpacaBroker()
                fills = broker.execute_tear_sheet(trade_orders)
                submitted = [f for f in fills if f.get("status") == "submitted"]
                print(f"  ✅ {len(submitted)} orders submitted to Alpaca")
            except Exception as e:
                print(f"❌ Broker execution FAILED: {e}")
    
    print("\n✅ Pipeline resumed and complete.")
    return {"agent3": agent3_result, "agent4": agent4_result}


if __name__ == "__main__":
    from safeguards import run_with_crash_protection
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    if mode == "morning":
        run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
    elif mode == "monitor":
        run_with_crash_protection(run_afternoon_monitor, "Afternoon Monitor", verbose=verbose)
    elif mode == "resume":
        run_with_crash_protection(resume_from_agent3, "Resume from Agent 3", verbose=verbose)
    elif mode == "full":
        results = run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
        if results and all(r.get("success", False) for r in results.values() if isinstance(r, dict)):
            print("\n⏰ Morning pipeline done. Agent 5 runs at 3:30 PM.")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 orchestrator.py [morning|monitor|resume|full]")


==================================================================
FILE: preflight.py (    1007 lines)
==================================================================
"""
Pre-Flight Data Fetch — runs at 7:55 AM ET
Fetches:
1. Yesterday's close prices (NOT live/intraday) — Tweak #6
2. SCREENER_UNIVERSE from Finviz ($100M+ mkt cap, >$5 price)
3. FRED macro data (MOVE index, credit spreads)
4. Smart money Twitter mentions (placeholder until API is wired)

All data is saved to output/ for agents to consume.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf

from config import SCREENER_MIN_MARKET_CAP, SCREENER_MIN_PRICE

# Alpaca market data — primary source (falls back to yfinance on error)
try:
    import alpaca_data as alpaca
    ALPACA_AVAILABLE = True
    print("[Pre-Flight] Alpaca Market Data: AVAILABLE (primary source)")
except Exception as e:
    ALPACA_AVAILABLE = False
    print(f"[Pre-Flight] Alpaca Market Data: UNAVAILABLE ({e}) — using yfinance")

# Massive (Polygon-compatible) — technical indicators (SMA, RSI, MACD)
try:
    import massive_data as massive
    from config import MASSIVE_API_KEY
    MASSIVE_AVAILABLE = bool(MASSIVE_API_KEY)
    if MASSIVE_AVAILABLE:
        print("[Pre-Flight] Massive Market Data: AVAILABLE (technical indicators)")
    else:
        print("[Pre-Flight] Massive Market Data: KEY NOT SET — skipping")
except Exception as e:
    MASSIVE_AVAILABLE = False
    print(f"[Pre-Flight] Massive Market Data: UNAVAILABLE ({e})")

OUTPUT_DIR = "output"

ASSEMBLY_STALE_HOURS = 18  # Assembly data older than this triggers fresh fetch from public APIs


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch YESTERDAY's regular-session close for a list of tickers.
    This is critical — all pricing and stop calculations use prior close,
    NOT live/intraday pre-market data (Tweak #6).
    
    Primary: Alpaca Market Data API (IEX feed, real-time)
    Fallback: Yahoo Finance
    """
    # Try Alpaca first
    if ALPACA_AVAILABLE:
        try:
            results = alpaca.fetch_prior_close(tickers)
            # Check if most results came back OK
            ok_count = sum(1 for v in results.values() if "error" not in v)
            if ok_count >= len(tickers) * 0.5:  # At least half succeeded
                print(f"[Pre-Flight] Prior close: {ok_count}/{len(tickers)} tickers from Alpaca")
                # Fill any Alpaca failures with yfinance
                failed = [t for t, v in results.items() if "error" in v]
                if failed:
                    print(f"[Pre-Flight] Falling back to yfinance for {len(failed)} tickers: {failed[:5]}...")
                    yf_results = _fetch_prior_close_yfinance(failed)
                    results.update(yf_results)
                return results
            else:
                print(f"[Pre-Flight] Alpaca returned too many errors ({ok_count}/{len(tickers)}) — falling back to yfinance")
        except Exception as e:
            print(f"[Pre-Flight] Alpaca prior_close failed: {e} — falling back to yfinance")

    return _fetch_prior_close_yfinance(tickers)


def _fetch_prior_close_yfinance(tickers: list) -> dict:
    """Original yfinance-based prior close fetch (fallback)."""
    results = {}
    end = datetime.now()
    start = end - timedelta(days=10)

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            close_prices = data["Close"]
            if len(close_prices) >= 2:
                if str(close_prices.index[-1].date()) == str(datetime.now().date()):
                    prior_close = float(close_prices.iloc[-2].item())
                    prior_date = str(close_prices.index[-2].date())
                else:
                    prior_close = float(close_prices.iloc[-1].item())
                    prior_date = str(close_prices.index[-1].date())
            else:
                prior_close = float(close_prices.iloc[-1].item())
                prior_date = str(close_prices.index[-1].date())

            closes = [float(c) for c in data["Close"].values.flatten()]

            results[ticker] = {
                "prior_close": round(prior_close, 2),
                "prior_date": prior_date,
                "closes_30d": [round(c, 2) for c in closes],
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_macro_data() -> dict:
    """
    Fetch macro indicators for Agent 1.
    Replaced S&P 500, DXY, Gold with MOVE, DIX, Sector Breadth per Jamie's tweaks.
    
    - VIX: ^VIX
    - MOVE index: via FRED API (or proxy)
    - DIX: Dark Index (from squeezemetrics — needs separate fetch)
    - 10Y/2Y yields: ^TNX, 2YY=F
    - HY credit spread proxy: HYG vs LQD
    - Sector breadth: % of S&P sectors above 20-day MA
    """
    macro = {}

    # --- Tickers we can get from yfinance ---
    yf_tickers = {
        "VIX": "^VIX",
        "TNX_10Y": "^TNX",
        "TWO_YEAR": "2YY=F",
        "HYG": "HYG",
        "LQD": "LQD",
    }

    end = datetime.now()
    start = end - timedelta(days=30)

    for name, ticker in yf_tickers.items():
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                macro[name] = {"error": f"No data for {ticker}"}
                continue

            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item()) if len(data) >= 5 else current
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current

            macro[name] = {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
            }
        except Exception as e:
            macro[name] = {"error": str(e)}

    # Yield curve spread
    if "TNX_10Y" in macro and "TWO_YEAR" in macro:
        if "current" in macro["TNX_10Y"] and "current" in macro["TWO_YEAR"]:
            macro["YIELD_CURVE_SPREAD"] = round(
                macro["TNX_10Y"]["current"] - macro["TWO_YEAR"]["current"], 2
            )

    # HY spread proxy
    if "HYG" in macro and "LQD" in macro:
        if "current" in macro["HYG"] and "current" in macro["LQD"]:
            macro["HY_SPREAD_PROXY"] = round(
                macro["HYG"]["current"] / macro["LQD"]["current"], 4
            )

    # --- MOVE Index (bond volatility) ---
    # MOVE is available via FRED as "MOVE" or as a proxy via ^MOVE
    # Trying FRED first, falling back to a note
    macro["MOVE"] = fetch_move_index()

    # --- DIX (Dark Index) ---
    # DIX comes from squeezemetrics.com — not available via yfinance/FRED
    # Requires a separate scrape or API
    macro["DIX"] = fetch_dix()

    # --- Sector Breadth ---
    macro["SECTOR_BREADTH"] = fetch_sector_breadth()

    macro["timestamp"] = datetime.now().isoformat()
    macro["price_source"] = "prior_close"  # Flag that we're using yesterday's close

    return macro


def fetch_move_index() -> dict:
    """
    Fetch MOVE index (Merrill Lynch Option Volatility Estimate).
    Measures Treasury/bond market volatility.
    Uses ^MOVE on yfinance (confirmed working), with FRED as fallback.
    """
    # Primary: yfinance ^MOVE
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        data = yf.download("^MOVE", start=start, end=end, progress=False)
        if not data.empty and len(data) >= 5:
            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item())
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current
            return {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
                "source": "yfinance ^MOVE",
            }
    except Exception:
        pass

    # Fallback: FRED API
    fred_key = os.environ.get("FRED_API_KEY", "")
    if fred_key:
        try:
            import requests
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": "BAMLMOVE",
                "api_key": fred_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 30,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            obs = [o for o in data.get("observations", []) if o.get("value") != "."]
            if obs:
                current = float(obs[0]["value"])
                prev_5 = float(obs[min(4, len(obs)-1)]["value"])
                return {
                    "current": round(current, 2),
                    "5d_ago": round(prev_5, 2),
                    "5d_change_pct": round((current - prev_5) / prev_5 * 100, 2),
                    "date": obs[0]["date"],
                    "source": "FRED",
                }
        except Exception:
            pass

    return {"error": "MOVE index unavailable"}


def fetch_dix() -> dict:
    """
    Fetch DIX (Dark Index) from squeezemetrics.
    DIX measures dark pool buying — high DIX = institutional accumulation.
    NOTE: Requires scraping squeezemetrics.com/monitor/dix — not a free API.
    """
    # Placeholder — needs web scrape or paid data source
    return {"error": "DIX unavailable — needs squeezemetrics.com scraper setup"}


def fetch_sector_breadth() -> dict:
    """
    Calculate sector breadth: what % of S&P 500 sectors are above their 20-day MA.
    Uses sector ETFs as proxies.
    Primary: Alpaca historical bars. Fallback: yfinance.
    """
    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Disc",
        "XLP": "Consumer Staples",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLC": "Comm Services",
    }

    above_20ma = 0
    total = 0
    sector_detail = {}

    # Try Alpaca first for all sector ETFs
    if ALPACA_AVAILABLE:
        try:
            hist = alpaca.fetch_historical_bars(list(sector_etfs.keys()), days=40)
            for etf, name in sector_etfs.items():
                etf_data = hist.get(etf, {})
                bars = etf_data.get("bars", [])
                if len(bars) < 20:
                    continue
                closes = [b["close"] for b in bars]
                current = closes[-1]
                ma_20 = sum(closes[-20:]) / 20
                is_above = current > ma_20
                if is_above:
                    above_20ma += 1
                total += 1
                sector_detail[name] = {
                    "etf": etf,
                    "price": round(current, 2),
                    "ma_20": round(ma_20, 2),
                    "above_20ma": is_above,
                    "source": "alpaca",
                }
            if total > 0:
                breadth_pct = round(above_20ma / total * 100, 1)
                return {
                    "above_20ma_count": above_20ma,
                    "total_sectors": total,
                    "breadth_pct": breadth_pct,
                    "detail": sector_detail,
                }
        except Exception as e:
            print(f"[Pre-Flight] Alpaca sector breadth failed: {e} — falling back to yfinance")
            above_20ma = 0
            total = 0
            sector_detail = {}

    # Fallback: yfinance
    end = datetime.now()
    start = end - timedelta(days=40)

    for etf, name in sector_etfs.items():
        try:
            data = yf.download(etf, start=start, end=end, progress=False)
            if data.empty or len(data) < 20:
                continue

            closes = [float(c) for c in data["Close"].values.flatten()]
            current = closes[-1]
            ma_20 = sum(closes[-20:]) / 20

            is_above = current > ma_20
            if is_above:
                above_20ma += 1
            total += 1

            sector_detail[name] = {
                "etf": etf,
                "price": round(current, 2),
                "ma_20": round(ma_20, 2),
                "above_20ma": is_above,
            }
        except Exception:
            continue

    breadth_pct = round(above_20ma / total * 100, 1) if total > 0 else 0

    return {
        "above_20ma_count": above_20ma,
        "total_sectors": total,
        "breadth_pct": breadth_pct,
        "detail": sector_detail,
    }


# Theme-to-Finviz filter mapping for dynamic screening
_THEME_SECTOR_MAP = {
    "ai infrastructure": {"Sector": "Technology"},
    "ai": {"Sector": "Technology"},
    "technology": {"Sector": "Technology"},
    "semiconductors": {"Industry": "Semiconductors"},
    "software": {"Sector": "Technology"},
    "energy": {"Sector": "Energy"},
    "uranium": {"Industry": "Uranium"},
    "solar": {"Industry": "Solar"},
    "oil": {"Sector": "Energy"},
    "healthcare": {"Sector": "Healthcare"},
    "biotech": {"Industry": "Biotechnology"},
    "financials": {"Sector": "Financial"},
    "banks": {"Industry": "Banks - Diversified"},
    "industrials": {"Sector": "Industrials"},
    "defense": {"Industry": "Aerospace & Defense"},
    "aerospace": {"Industry": "Aerospace & Defense"},
    "gold": {"Industry": "Gold"},
    "silver": {"Industry": "Silver"},
    "mining": {"Industry": "Other Industrial Metals & Mining"},
    "copper": {"Industry": "Copper"},
    "real estate": {"Sector": "Real Estate"},
    "utilities": {"Sector": "Utilities"},
    "consumer": {"Sector": "Consumer Cyclical"},
    "retail": {"Industry": "Internet Retail"},
    "materials": {"Sector": "Basic Materials"},
}

# Fallback hardcoded list — used if Finviz screener fails
_FALLBACK_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "AVGO", "CRM",
    "ORCL", "ADBE", "NFLX", "INTC", "CSCO", "QCOM", "TXN", "MU", "AMAT", "LRCX",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW", "AXP", "V",
    "UNH", "JNJ", "PFE", "ABBV", "LLY", "MRK", "BMY", "AMGN", "GILD", "TMO",
    "XOM", "CVX", "COP", "SLB", "EOG",
    "CAT", "DE", "HON", "RTX", "LMT", "BA", "GE", "UNP",
    "HD", "LOW", "NKE", "SBUX", "MCD", "TGT", "COST",
    "SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "GLD", "TLT", "HYG",
]

MAX_SCREENER_TICKERS = 50


def _run_finviz_screen(theme_filters: Optional[Dict] = None) -> list:
    """
    Run a single Finviz screener query and return a list of dicts.
    Raises on any failure so the caller can fall back.
    """
    from finvizfinance.screener.overview import Overview

    filt = {
        # Finviz doesn't have an exact $500M threshold;
        # use >$300M and post-filter for >$500M
        "Market Cap.": "+Small (over $300mln)",
        "Price": "Over $5",
        "Average Volume": "Over 500K",
        "50-Day Simple Moving Average": "Price above SMA50",
        "200-Day Simple Moving Average": "Price above SMA200",
    }

    if theme_filters:
        filt.update(theme_filters)

    o = Overview()
    o.set_filter(filters_dict=filt)
    # Fetch up to 200 rows (sorted by volume desc), then trim to MAX
    df = o.screener_view(order="Volume", ascend=False, limit=200, verbose=0)

    if df is None or df.empty:
        return []

    # Post-filter: market cap > $500M (Finviz only lets us filter >$300M)
    df = df[df["Market Cap"] >= 500_000_000]

    results = []
    for _, row in df.iterrows():
        results.append({
            "ticker": row["Ticker"],
            "name": row["Company"],
            "sector": row["Sector"],
            "market_cap": int(row["Market Cap"]) if row["Market Cap"] else 0,
            "prior_close": round(float(row["Price"]), 2) if row["Price"] else 0.0,
            "source": "finviz_dynamic",
        })

    return results


def _fallback_screener_universe() -> list:
    """
    Fallback: use hardcoded ticker list + yfinance for basic data.
    Used when Finviz is unavailable (rate-limited, down, etc.).
    """
    import warnings
    warnings.warn(
        "[Pre-Flight] Finviz screener failed — falling back to hardcoded universe",
        RuntimeWarning,
        stacklevel=3,
    )
    print("[Pre-Flight] WARNING: Using hardcoded fallback universe")

    screener = []
    for ticker in _FALLBACK_UNIVERSE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mkt_cap = info.get("marketCap", 0)
            price = info.get("regularMarketPreviousClose") or info.get("previousClose", 0)

            if mkt_cap and mkt_cap >= SCREENER_MIN_MARKET_CAP and price and price >= SCREENER_MIN_PRICE:
                screener.append({
                    "ticker": ticker,
                    "name": info.get("shortName", ticker),
                    "sector": info.get("sector", "N/A"),
                    "market_cap": mkt_cap,
                    "prior_close": round(float(price), 2),
                    "source": "hardcoded_fallback",
                })
        except Exception:
            continue

    return screener[:MAX_SCREENER_TICKERS]


def _enrich_prior_close(tickers_data: list) -> list:
    """
    Enrich screener results with accurate prior_close from yfinance,
    since Finviz price data may be slightly delayed.
    """
    ticker_symbols = [t["ticker"] for t in tickers_data]
    end = datetime.now()
    start = end - timedelta(days=10)

    for entry in tickers_data:
        try:
            data = yf.download(entry["ticker"], start=start, end=end, progress=False)
            if not data.empty:
                entry["prior_close"] = round(float(data["Close"].iloc[-1].item()), 2)
        except Exception:
            pass  # Keep Finviz price as fallback

    return tickers_data


def generate_screener_universe(themes: Optional[List[str]] = None) -> list:
    """
    Generate SCREENER_UNIVERSE: up to 50 liquid tickers meeting:
    - Market cap > $500M
    - Price > $5
    - Average volume > 500K
    - Price above 50-day SMA (momentum filter)

    Uses Finviz dynamic screening via finvizfinance package.
    Accepts optional `themes` list to focus on specific sectors/industries.
    Falls back to hardcoded list if Finviz fails.
    """
    try:
        all_results = []
        seen_tickers = set()

        if themes:
            # Run separate screens per theme, then merge
            mapped_any = False
            for theme in themes:
                theme_key = theme.lower().strip()
                theme_filters = _THEME_SECTOR_MAP.get(theme_key)
                if theme_filters:
                    mapped_any = True
                    print(f"[Pre-Flight] Finviz screen: theme '{theme}' → {theme_filters}")
                    try:
                        results = _run_finviz_screen(theme_filters)
                        for r in results:
                            if r["ticker"] not in seen_tickers:
                                r["theme"] = theme
                                all_results.append(r)
                                seen_tickers.add(r["ticker"])
                    except Exception as e:
                        print(f"[Pre-Flight] Finviz theme '{theme}' screen failed: {e}")

            # If no themes mapped, or all theme screens failed, do broad scan
            if not mapped_any or not all_results:
                print("[Pre-Flight] No theme-specific results — running broad Finviz scan")
                results = _run_finviz_screen()
                for r in results:
                    if r["ticker"] not in seen_tickers:
                        all_results.append(r)
                        seen_tickers.add(r["ticker"])
        else:
            # No themes — broad scan
            print("[Pre-Flight] Running broad Finviz screener (no theme filter)")
            all_results = _run_finviz_screen()

        if not all_results:
            print("[Pre-Flight] Finviz returned 0 results — falling back")
            return _fallback_screener_universe()

        # Sort by volume proxy (market_cap as tiebreaker) and cap at MAX
        # Note: Finviz already sorted by volume desc, but after merging themes
        # we re-deduplicate; the order from the first theme takes precedence.
        all_results = all_results[:MAX_SCREENER_TICKERS]

        # Enrich with accurate prior_close (Alpaca primary, yfinance fallback)
        if ALPACA_AVAILABLE:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with Alpaca prior_close...")
            all_results = alpaca.enrich_screener_universe(all_results)
        else:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with yfinance prior_close...")
            all_results = _enrich_prior_close(all_results)

        print(f"[Pre-Flight] Screener universe: {len(all_results)} tickers from Finviz dynamic screen")
        return all_results

    except Exception as e:
        print(f"[Pre-Flight] Finviz screener failed: {e}")
        return _fallback_screener_universe()


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money Twitter/X mentions for given tickers.
    X research is MANDATORY — this must return real data.
    
    When called from the OCPlatform orchestrator, this uses x_search.
    When run standalone, it reads from a pre-existing file or raises an error.
    """
    from config import SMART_MONEY_ACCOUNTS

    mentions = {}
    curated_handles = SMART_MONEY_ACCOUNTS
    if not curated_handles:
        curated_handles = [
            "unusual_whales", "DeItaone", "Fxhedgers", "zaborsky",
            "jimcramer", "GurufocusData", "OptionsHawk", "PeterSchiff",
            "TruthGundlach", "elerianm", "SqueezeMetrics", "sentimentrader",
            "DarkPoolChart", "WallStJesus", "VolSignals",
        ]

    # NOTE: The actual x_search calls happen in the orchestrator (orchestrator.py)
    # because x_search is an OCPlatform tool, not a Python library.
    # This function checks for the pre-fetched output file.
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            return json.load(f)

    raise RuntimeError(
        "Smart money X/Twitter data not found. The orchestrator must run x_search "
        "for each ticker against curated accounts and save to output/smart_money_mentions.json "
        "BEFORE Agent 3 can run. X research is MANDATORY."
    )


def format_macro_for_prompt(data: dict) -> str:
    """Format macro data into a clean text block for the LLM prompt."""
    lines = [
        f"MACRO DATA SNAPSHOT — {data.get('timestamp', 'unknown')}",
        f"Price Source: {data.get('price_source', 'unknown')}",
        "=" * 50,
    ]

    skip_keys = {"timestamp", "price_source"}

    for key, val in data.items():
        if key in skip_keys:
            continue
        if isinstance(val, dict) and "error" in val:
            lines.append(f"{key}: DATA UNAVAILABLE ({val['error']})")
        elif isinstance(val, dict) and "current" in val:
            change_str = ""
            if "5d_change_pct" in val:
                change_str = f" (5d: {val['5d_change_pct']:+.2f}%"
                if "20d_change_pct" in val:
                    change_str += f", 20d: {val['20d_change_pct']:+.2f}%"
                change_str += ")"
            lines.append(f"{key}: {val['current']}{change_str}")
        elif isinstance(val, dict) and "breadth_pct" in val:
            lines.append(
                f"{key}: {val['breadth_pct']}% of sectors above 20DMA "
                f"({val['above_20ma_count']}/{val['total_sectors']})"
            )
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {json.dumps(val)}" if not isinstance(val, str) else f"{key}: {val}")

    return "\n".join(lines)


def merge_assembly_screens(static_universe: list, assembly: dict) -> list:
    """
    Hybrid screener: merge Assembly's momentum/breakout screens into the static universe.
    Adds new tickers from Assembly that aren't already in the static list.
    Tags them with source='assembly_momentum' so Agent 2 knows they came from the live screen.
    """
    existing_tickers = set(t["ticker"] for t in static_universe)
    added = 0

    # Load Assembly screens if available
    screens_path = "output/assembly_screens.json"
    if os.path.exists(screens_path):
        try:
            with open(screens_path) as f:
                screens = json.load(f)
        except Exception:
            screens = {}
    else:
        screens = {}

    # Add overbought momentum names (these are running — potential trend plays)
    for entry in screens.get("overbought", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_overbought",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    # Add oversold names (these are beaten down — potential mean-reversion or value)
    for entry in screens.get("oversold", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_oversold",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    if added > 0:
        print(f"[Pre-Flight] Merged {added} new tickers from Assembly momentum screens (total: {len(static_universe)})")
    else:
        print("[Pre-Flight] No new Assembly tickers to merge (all already in universe)")

    return static_universe


def format_assembly_for_prompt(assembly: dict) -> str:
    """Format Assembly Private data for Agent 1's system prompt."""
    if not assembly:
        return "ASSEMBLY DATA: NOT AVAILABLE"

    lines = [
        f"ASSEMBLY SENTIMENT & MACRO — {assembly.get('timestamp', 'unknown')}",
        "Source: assemblyprivate.com (FMP data feed)",
        "=" * 50,
    ]

    # Sentiment
    sent = assembly.get("sentiment", {})
    if sent:
        lines.append(f"\nSENTIMENT COMPOSITE: {sent.get('composite_score', '?')} ({sent.get('composite_label', '?')})")
        lines.append(f"  Prev Close: {sent.get('prev_close', '?')} | 1W: {sent.get('one_week_ago', '?')} | 1M: {sent.get('one_month_ago', '?')} | 1Y: {sent.get('one_year_ago', '?')}")
        lines.append(f"  30D Avg: {sent.get('thirty_day_avg', '?')} | 52W High: {sent.get('fifty_two_week_high', '?')} | 52W Low: {sent.get('fifty_two_week_low', '?')}")

        comp = sent.get("components", {})
        if comp:
            lines.append("  Sub-Components:")
            for key, label in [
                ("market_volatility_vix", "Market Volatility (VIX)"),
                ("sp500_momentum_125d", "S&P 125d Momentum"),
                ("sp500_momentum", "S&P 500 Momentum"),
                ("stock_price_strength", "Stock Price Strength"),
                ("stock_price_breadth", "Stock Price Breadth"),
                ("put_call_options", "Put/Call Options"),
                ("junk_bond_demand", "Junk Bond Demand"),
                ("safe_haven_demand", "Safe Haven Demand"),
            ]:
                val = comp.get(key)
                if val is not None:
                    lines.append(f"    {label}: {val}")

    # Risk & Credit Gauges
    macro = assembly.get("macro", {})
    gauges = macro.get("risk_credit_gauges", [])
    if gauges:
        lines.append("\nRISK & CREDIT GAUGES (with 50d/200d trends):")
        for g in gauges:
            lines.append(f"  {g['ticker']} ({g['name']}): {g['price']} | Today: {g['today']} | vs50d: {g['vs_50d']} | vs200d: {g['vs_200d']} | 52wk: {g['range_52w']}")

    # Cross-asset rotation
    xasset = macro.get("cross_asset_rotation", [])
    if xasset:
        lines.append("\nCROSS-ASSET ROTATION:")
        for a in xasset:
            lines.append(f"  {a['ticker']} ({a['name']}): ${a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    # Sector rotation
    sectors = macro.get("sector_rotation", [])
    if sectors:
        lines.append("\nSECTOR ROTATION (RS vs SPY):")
        for s in sectors:
            lines.append(f"  {s['etf']} ({s['sector']}): Today: {s['today']} | vs50d: {s['vs_50d']} | vs200d: {s['vs_200d']} | RS: {s.get('rs_vs_spy', '?')}")

    # Yield curve
    yc = macro.get("yield_curve", {})
    if yc:
        curve = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"\nYIELD CURVE: {curve}")
        if "2Y" in yc and "10Y" in yc:
            spread = round(yc["10Y"] - yc["2Y"], 2)
            lines.append(f"  2s10s Spread: {spread}")

    return "\n".join(lines)


def is_assembly_stale(assembly_path: str) -> bool:
    """Check if assembly data file is stale (older than ASSEMBLY_STALE_HOURS)."""
    if not os.path.exists(assembly_path):
        return True
    try:
        with open(assembly_path) as f:
            data = json.load(f)
        ts = data.get("timestamp", "")
        if not ts:
            return True
        # Parse ISO timestamp
        data_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        print(f"[Pre-Flight] Assembly data age: {age_hours:.1f}h (stale threshold: {ASSEMBLY_STALE_HOURS}h)")
        return age_hours > ASSEMBLY_STALE_HOURS
    except Exception as e:
        print(f"[Pre-Flight] Could not check assembly staleness: {e}")
        return True


def fetch_fresh_sentiment_fallback() -> dict:
    """
    Fetch fresh sentiment indicators from public APIs when Assembly data is stale.
    Uses CNN Fear & Greed API + yfinance for the same indicators Assembly provides.
    """
    import requests
    result = {"timestamp": datetime.now().isoformat(), "source": "public_api_fallback"}

    # 2. Sub-components from yfinance
    components = {}
    try:
        end = datetime.now()
        start = end - timedelta(days=5)

        # VIX for market volatility component
        vix = yf.download("^VIX", start=start, end=end, progress=False)
        if not vix.empty:
            vix_val = float(vix["Close"].iloc[-1].item())
            components["vix_value"] = round(vix_val, 2)
            if vix_val < 15: components["market_volatility_vix"] = 90
            elif vix_val < 20: components["market_volatility_vix"] = 65
            elif vix_val < 25: components["market_volatility_vix"] = 45
            elif vix_val < 35: components["market_volatility_vix"] = 25
            else: components["market_volatility_vix"] = 5

        # S&P 500 momentum (125-day)
        spy = yf.download("SPY", start=end - timedelta(days=180), end=end, progress=False)
        if not spy.empty and len(spy) > 125:
            current_spy = float(spy["Close"].iloc[-1].item())
            spy_125d = float(spy["Close"].iloc[-125].item())
            momentum_pct = (current_spy - spy_125d) / spy_125d * 100
            if momentum_pct > 10: components["sp500_momentum_125d"] = 90
            elif momentum_pct > 5: components["sp500_momentum_125d"] = 70
            elif momentum_pct > 0: components["sp500_momentum_125d"] = 50
            elif momentum_pct > -5: components["sp500_momentum_125d"] = 30
            else: components["sp500_momentum_125d"] = 10

        # Junk bond demand: HYG vs LQD spread
        hyg = yf.download("HYG", start=start, end=end, progress=False)
        lqd = yf.download("LQD", start=start, end=end, progress=False)
        if not hyg.empty and not lqd.empty:
            hyg_ret = float(hyg["Close"].pct_change().iloc[-1].item())
            lqd_ret = float(lqd["Close"].pct_change().iloc[-1].item())
            spread = (hyg_ret - lqd_ret) * 100
            if spread > 0.5: components["junk_bond_demand"] = 80
            elif spread > 0: components["junk_bond_demand"] = 60
            elif spread > -0.5: components["junk_bond_demand"] = 40
            else: components["junk_bond_demand"] = 20

        # Safe haven demand: TLT relative to SPY
        tlt = yf.download("TLT", start=start, end=end, progress=False)
        if not tlt.empty and not spy.empty:
            tlt_ret = float(tlt["Close"].pct_change().iloc[-1].item())
            spy_ret_1d = float(spy["Close"].pct_change().iloc[-1].item())
            haven_spread = (spy_ret_1d - tlt_ret) * 100
            if haven_spread > 1: components["safe_haven_demand"] = 80
            elif haven_spread > 0: components["safe_haven_demand"] = 60
            elif haven_spread > -1: components["safe_haven_demand"] = 40
            else: components["safe_haven_demand"] = 20

    except Exception as e:
        print(f"[Pre-Flight] Component fallback fetch error: {e}")

    result["components"] = components

    # Compute synthetic composite from available components
    if components:
        scores = [v for k, v in components.items() if k != "vix_value" and isinstance(v, (int, float))]
        if scores:
            composite = round(sum(scores) / len(scores))
            result["composite_score"] = composite
            if composite >= 75: result["composite_label"] = "Extreme Greed"
            elif composite >= 55: result["composite_label"] = "Greed"
            elif composite >= 45: result["composite_label"] = "Neutral"
            elif composite >= 25: result["composite_label"] = "Fear"
            else: result["composite_label"] = "Extreme Fear"
            print(f"[Pre-Flight] Synthetic composite: {composite} ({result['composite_label']}) from {len(scores)} components")

    return result


def run_preflight(themes: Optional[List[str]] = None) -> dict:
    """
    Run the full 7:55 AM pre-flight.
    Returns all data packaged for downstream agents.

    Args:
        themes: Optional list of theme strings from Agent 1's preferred_themes.
                Maps to Finviz sector/industry filters for focused screening.
                E.g. ["AI Infrastructure", "Energy", "Uranium"]
    """
    print("[Pre-Flight] Starting 7:55 AM data fetch...")
    print("[Pre-Flight] Using PRIOR CLOSE prices (not live/intraday)")
    if themes:
        print(f"[Pre-Flight] Theme filters: {themes}")

    # 1. Macro data
    print("[Pre-Flight] Fetching macro data...")
    macro = fetch_macro_data()

    # 2. Screener universe (dynamic via Finviz)
    print("[Pre-Flight] Generating screener universe...")
    screener = generate_screener_universe(themes=themes)

    # 3. Smart money X/Twitter mentions
    # NOTE: X search happens in the orchestrator via OCPlatform's x_search tool.
    # Pre-flight saves macro + screener. The orchestrator then:
    #   a) Runs Agent 1 + Agent 2 to get candidate tickers
    #   b) Runs x_search for those tickers against curated accounts
    #   c) Saves results to output/smart_money_mentions.json
    #   d) Then runs Agent 3 with that data
    # X research is MANDATORY — Agent 3 will not bypass.

    # 3. Assembly Private data (sentiment + macro overlay)
    #    If stale or missing, auto-fetch fresh indicators from public APIs
    assembly = {}
    assembly_path = f"{OUTPUT_DIR}/assembly_data.json"
    stale = is_assembly_stale(assembly_path)

    if not stale:
        try:
            with open(assembly_path) as f:
                assembly = json.load(f)
            print(f"[Pre-Flight] Assembly data FRESH — loaded (sentiment: {assembly.get('sentiment', {}).get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Assembly data load failed: {e}")
            stale = True

    if stale:
        print("[Pre-Flight] Assembly data STALE or missing — fetching fresh indicators from public APIs...")
        fresh_sentiment = fetch_fresh_sentiment_fallback()
        assembly = {
            "timestamp": datetime.now().isoformat(),
            "source": "public_api_fallback",
            "sentiment": fresh_sentiment,
            "macro": {},  # macro already covered by fetch_macro_data() above
        }
        # Save the fresh fallback so agents can reference it
        try:
            with open(assembly_path, "w") as f:
                json.dump(assembly, f, indent=2)
            print(f"[Pre-Flight] Fresh fallback data saved (sentiment: {fresh_sentiment.get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Could not save fallback data: {e}")

    # 4. Merge Assembly momentum screen into screener universe (hybrid approach)
    screener = merge_assembly_screens(screener, assembly)

    # 5. Technical indicators from Massive API (SMA, RSI, MACD)
    technicals = {}
    if MASSIVE_AVAILABLE:
        # Get technicals for key macro tickers (SPY, QQQ, IWM)
        # and top screener picks (first 5 to stay within rate limits)
        tech_tickers = ["SPY", "QQQ", "IWM"]
        top_screener = [t["ticker"] for t in screener[:3] if "ticker" in t]
        tech_tickers.extend([t for t in top_screener if t not in tech_tickers])

        print(f"[Pre-Flight] Fetching Massive technicals for {tech_tickers}...")
        for i, ticker in enumerate(tech_tickers):
            try:
                # SPY gets the full treatment (SMA + RSI + MACD = 5 calls)
                # Others get lightweight (prev + RSI + MACD = 3 calls)
                if i == 0:  # SPY
                    tech = massive.fetch_technicals_with_sma(ticker)
                else:
                    tech = massive.fetch_full_technicals(ticker)
                technicals[ticker] = tech
                print(f"  {ticker}: RSI={tech.get('rsi_14', '?')} MACD_trend={tech.get('macd_trend', '?')}")
            except Exception as e:
                print(f"  {ticker}: FAILED — {e}")
                technicals[ticker] = {"error": str(e)}

        # Save technicals
        with open(f"{OUTPUT_DIR}/technicals.json", "w") as f:
            json.dump(technicals, f, indent=2)
        print(f"[Pre-Flight] Technicals saved for {len(technicals)} tickers")
    else:
        print("[Pre-Flight] Skipping Massive technicals (not available)")

    preflight_data = {
        "timestamp": datetime.now().isoformat(),
        "macro": macro,
        "screener_universe": screener,
        "assembly": assembly,
        "technicals": technicals,
    }

    # Save all outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(f"{OUTPUT_DIR}/preflight_macro.json", "w") as f:
        json.dump(macro, f, indent=2)

    with open(f"{OUTPUT_DIR}/screener_universe.json", "w") as f:
        json.dump(screener, f, indent=2)

    print(f"[Pre-Flight] Complete. Macro data + {len(screener)} screener tickers saved.")
    print(f"[Pre-Flight] NOTE: X/Twitter smart money fetch runs in orchestrator after Agent 2 picks tickers.")
    return preflight_data


if __name__ == "__main__":
    data = run_preflight()
    print("\n" + format_macro_for_prompt(data["macro"]))
    print(f"\nScreener: {len(data['screener_universe'])} tickers")
    print(f"Smart Money: {data['smart_money']['status']}")


==================================================================
FILE: safeguards.py (     508 lines)
==================================================================
"""
Pipeline Safeguards — Production hardening for Open Claw.

1. Market Calendar Check (Holiday Trap Prevention)
2. Penalty Box / Cooldown Tracker (Whipsaw Prevention)
3. Liquidity Cap (ADDV Filter + Volume-Aware Sizing)
4. Earnings Screen (Binary Event Prevention)
5. Heartbeat & Failure Telemetry (Telegram Alerts)
"""
import json
import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OUTPUT_DIR = "output"
COOLDOWN_FILE = os.path.join(OUTPUT_DIR, "cooldown.json")
COOLDOWN_TRADING_DAYS = 5  # Min trading days before re-entry after a loss


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. MARKET CALENDAR CHECK — Holiday Trap Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_market_open_today() -> dict:
    """
    Check if the US stock market is open today via Alpaca's Clock API.
    Returns dict with is_open, next_open, next_close, and should_run.
    
    should_run = True if market is open OR will open today.
    """
    try:
        from alpaca.trading.client import TradingClient
        
        api_key = os.environ.get("ALPACA_API_KEY", "")
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        
        if not api_key or not secret_key:
            print("[Safeguard] ⚠️ No Alpaca keys — cannot check market calendar. Proceeding anyway.")
            return {"is_open": None, "should_run": True, "reason": "no_alpaca_keys"}
        
        client = TradingClient(api_key, secret_key, paper=True)
        clock = client.get_clock()
        
        today = datetime.now().date()
        next_open_date = clock.next_open.date() if clock.next_open else None
        
        result = {
            "is_open": clock.is_open,
            "next_open": clock.next_open.isoformat() if clock.next_open else None,
            "next_close": clock.next_close.isoformat() if clock.next_close else None,
            "timestamp": datetime.now().isoformat(),
        }
        
        if clock.is_open:
            result["should_run"] = True
            result["reason"] = "market_is_open"
        elif next_open_date == today:
            result["should_run"] = True
            result["reason"] = "market_opens_today"
        else:
            result["should_run"] = False
            result["reason"] = f"market_closed_today_next_open_{next_open_date}"
        
        return result
    except Exception as e:
        print(f"[Safeguard] ⚠️ Clock API check failed: {e}. Proceeding anyway.")
        return {"is_open": None, "should_run": True, "reason": f"clock_check_failed: {e}"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PENALTY BOX — Whipsaw & Wash Sale Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _load_cooldown() -> dict:
    """Load cooldown tracker from disk."""
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE) as f:
            return json.load(f)
    return {"tickers": {}}


def _save_cooldown(data: dict):
    """Save cooldown tracker to disk."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_to_penalty_box(ticker: str, loss_amount: float, reason: str = "stop_loss"):
    """
    Add a ticker to the penalty box after a losing trade.
    Called by Agent 5 / broker when a position is closed for a loss.
    """
    cooldown = _load_cooldown()
    cooldown["tickers"][ticker] = {
        "added": datetime.now().isoformat(),
        "loss_amount": loss_amount,
        "reason": reason,
        "trading_days_remaining": COOLDOWN_TRADING_DAYS,
    }
    _save_cooldown(cooldown)
    print(f"[Penalty Box] 🚫 {ticker} added — cooldown {COOLDOWN_TRADING_DAYS} trading days (loss: ${loss_amount:.2f})")


def tick_penalty_box():
    """
    Decrement trading days for all tickers in the penalty box.
    Call this once per trading day (in preflight).
    Removes tickers whose cooldown has expired.
    """
    cooldown = _load_cooldown()
    expired = []
    
    for ticker, info in list(cooldown["tickers"].items()):
        remaining = info.get("trading_days_remaining", 0) - 1
        if remaining <= 0:
            expired.append(ticker)
            del cooldown["tickers"][ticker]
        else:
            info["trading_days_remaining"] = remaining
    
    _save_cooldown(cooldown)
    
    if expired:
        print(f"[Penalty Box] ✅ Released from cooldown: {', '.join(expired)}")
    
    active = list(cooldown["tickers"].keys())
    if active:
        print(f"[Penalty Box] 🚫 Still in cooldown: {', '.join(active)}")
    
    return expired


def is_in_penalty_box(ticker: str) -> bool:
    """Check if a ticker is currently in the penalty box."""
    cooldown = _load_cooldown()
    return ticker in cooldown["tickers"]


def get_penalty_box_tickers() -> list:
    """Get all tickers currently in the penalty box."""
    cooldown = _load_cooldown()
    return list(cooldown["tickers"].keys())


def filter_cooldown_tickers(screener: list) -> list:
    """
    Filter out any tickers that are in the penalty box.
    Call this in preflight before screener results reach the agents.
    """
    cooldown_tickers = get_penalty_box_tickers()
    if not cooldown_tickers:
        return screener
    
    filtered = [t for t in screener if t.get("ticker") not in cooldown_tickers]
    removed = [t["ticker"] for t in screener if t.get("ticker") in cooldown_tickers]
    
    if removed:
        print(f"[Penalty Box] Filtered {len(removed)} tickers from screener: {', '.join(removed)}")
    
    return filtered


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. LIQUIDITY CAP — ADDV Filter + Volume-Aware Sizing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIN_ADDV = 15_000_000  # $15M minimum Average Daily Dollar Volume
MAX_VOLUME_PCT = 0.01  # Never exceed 1% of 10-day average daily volume


def calculate_addv(ticker: str, bars: list) -> float:
    """
    Calculate 20-day Average Daily Dollar Volume.
    ADDV = avg(close * volume) over last 20 trading days.
    """
    if not bars or len(bars) < 5:
        return 0.0
    
    # Use last 20 bars (or however many we have)
    recent = bars[-20:]
    dollar_volumes = [b["close"] * b["volume"] for b in recent if b.get("close") and b.get("volume")]
    
    if not dollar_volumes:
        return 0.0
    
    return sum(dollar_volumes) / len(dollar_volumes)


def check_addv_filter(ticker: str, addv: float) -> dict:
    """Check if ticker passes the ADDV liquidity filter."""
    passes = addv >= MIN_ADDV
    return {
        "ticker": ticker,
        "addv": round(addv, 2),
        "min_addv": MIN_ADDV,
        "passes": passes,
        "reason": "OK" if passes else f"ADDV ${addv:,.0f} < ${MIN_ADDV:,.0f} minimum",
    }


def cap_shares_by_volume(shares: int, price: float, avg_daily_volume: float) -> dict:
    """
    Cap position size to 1% of 10-day average daily volume.
    Prevents becoming a significant portion of the order book.
    
    Args:
        shares: Proposed number of shares from risk sizing
        price: Current price per share
        avg_daily_volume: 10-day average daily volume (shares)
    
    Returns:
        dict with capped shares and whether the cap was binding.
    """
    if avg_daily_volume <= 0:
        return {
            "shares": shares,
            "capped": False,
            "reason": "no_volume_data",
        }
    
    max_shares = int(avg_daily_volume * MAX_VOLUME_PCT)
    
    if shares <= max_shares:
        return {
            "shares": shares,
            "capped": False,
            "max_shares_by_volume": max_shares,
            "pct_of_adv": round(shares / avg_daily_volume * 100, 3),
        }
    else:
        return {
            "shares": max_shares,
            "original_shares": shares,
            "capped": True,
            "max_shares_by_volume": max_shares,
            "pct_of_adv": round(max_shares / avg_daily_volume * 100, 3),
            "reason": f"Capped from {shares} to {max_shares} shares (1% of {avg_daily_volume:,.0f} ADV)",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. EARNINGS SCREEN — Binary Event Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EARNINGS_BUFFER_DAYS = 5  # Don't enter if earnings within 5 calendar days


def fetch_earnings_dates(tickers: list) -> dict:
    """
    Fetch next earnings date for each ticker.
    Uses yfinance (reliable for earnings dates).
    Returns {ticker: {"earnings_date": str, "days_until": int, "safe": bool}}
    """
    import yfinance as yf
    
    results = {}
    today = datetime.now().date()
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # yfinance provides earnings_dates as a DataFrame
            cal = stock.calendar
            
            earnings_date = None
            if cal is not None:
                if isinstance(cal, dict):
                    # Some versions return a dict
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list):
                            earnings_date = ed[0]
                        else:
                            earnings_date = ed
                elif hasattr(cal, "iloc"):
                    # DataFrame format
                    try:
                        earnings_date = cal.iloc[0, 0] if len(cal) > 0 else None
                    except Exception:
                        pass
            
            if earnings_date is not None:
                if hasattr(earnings_date, "date"):
                    ed = earnings_date.date()
                elif isinstance(earnings_date, str):
                    ed = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
                else:
                    ed = None
                
                if ed:
                    days_until = (ed - today).days
                    safe = days_until > EARNINGS_BUFFER_DAYS or days_until < 0
                    results[ticker] = {
                        "earnings_date": str(ed),
                        "days_until": days_until,
                        "safe": safe,
                        "reason": "OK" if safe else f"Earnings in {days_until} days — too close",
                    }
                else:
                    results[ticker] = {"earnings_date": None, "days_until": None, "safe": True, "reason": "no_date_parsed"}
            else:
                results[ticker] = {"earnings_date": None, "days_until": None, "safe": True, "reason": "no_earnings_data"}
        except Exception as e:
            results[ticker] = {"earnings_date": None, "days_until": None, "safe": True, "reason": f"fetch_error: {e}"}
    
    return results


def filter_earnings_tickers(screener: list) -> tuple:
    """
    Filter out tickers with earnings within EARNINGS_BUFFER_DAYS.
    Returns (filtered_screener, removed_tickers).
    """
    tickers = [t.get("ticker") for t in screener if t.get("ticker")]
    
    if not tickers:
        return screener, []
    
    print(f"[Earnings Screen] Checking {len(tickers)} tickers for upcoming earnings...")
    earnings = fetch_earnings_dates(tickers)
    
    removed = []
    filtered = []
    
    for entry in screener:
        ticker = entry.get("ticker")
        if ticker and ticker in earnings:
            info = earnings[ticker]
            if not info.get("safe", True):
                removed.append({"ticker": ticker, **info})
                print(f"[Earnings Screen] 🚫 {ticker} — {info['reason']}")
                continue
        filtered.append(entry)
    
    if removed:
        print(f"[Earnings Screen] Filtered {len(removed)} tickers with upcoming earnings")
    else:
        print(f"[Earnings Screen] ✅ All tickers clear of near-term earnings")
    
    return filtered, removed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. HEARTBEAT & FAILURE TELEMETRY — Telegram Alerts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_telegram(message: str):
    """
    Send a message to the configured Telegram chat.
    Used for alerts, heartbeats, and crash notifications.
    """
    import requests
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        print(f"[Telegram] ⚠️ No bot token or chat ID — message not sent: {message}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        
        if resp.status_code == 200:
            return True
        else:
            print(f"[Telegram] ⚠️ Send failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"[Telegram] ⚠️ Send error: {e}")
        return False


def send_crash_alert(agent_name: str, error: Exception):
    """Send a crash alert via Telegram."""
    tb = traceback.format_exc()
    # Truncate traceback for Telegram
    tb_short = tb[-500:] if len(tb) > 500 else tb
    
    message = (
        f"🚨 <b>OPEN CLAW CRASH</b>\n\n"
        f"<b>Agent:</b> {agent_name}\n"
        f"<b>Error:</b> {str(error)[:200]}\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n\n"
        f"<pre>{tb_short}</pre>\n\n"
        f"⚠️ Manual intervention may be required."
    )
    send_telegram(message)


def send_market_closed_alert():
    """Send alert that pipeline was skipped due to market closure."""
    message = (
        f"📅 <b>Market Closed Today</b>\n"
        f"Pipeline halted gracefully.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_hb_signal(positions: list = None, portfolio_heat: float = None, errors: list = None):
    """
    Send EOD heartbeat summary via Telegram.
    Call this at 4:00 PM ET.
    """
    pos_count = len(positions) if positions else 0
    heat_str = f"{portfolio_heat:.1f}%" if portfolio_heat is not None else "N/A"
    error_str = "No system errors" if not errors else f"{len(errors)} error(s): {', '.join(errors[:3])}"
    
    status_emoji = "🟢" if not errors else "🟡"
    
    message = (
        f"{status_emoji} <b>EOD Heartbeat</b>\n\n"
        f"<b>Open Positions:</b> {pos_count}\n"
        f"<b>Portfolio Heat:</b> {heat_str}\n"
        f"<b>Status:</b> {error_str}\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_pipeline_start_alert():
    """Send a notification that the morning pipeline has started."""
    message = (
        f"🌅 <b>Open Claw Starting</b>\n"
        f"Morning entry pipeline initiated.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_pipeline_complete_alert(results: dict):
    """Send a notification that the morning pipeline completed."""
    # Count successes
    agents_run = [k for k, v in results.items() if isinstance(v, dict)]
    successes = [k for k in agents_run if results[k].get("success", False)]
    failures = [k for k in agents_run if not results[k].get("success", True)]
    
    trades = results.get("broker", {}).get("fills", [])
    submitted = [f for f in trades if f.get("status") == "submitted"]
    
    status_emoji = "✅" if not failures else "⚠️"
    
    message = (
        f"{status_emoji} <b>Morning Pipeline Complete</b>\n\n"
        f"<b>Agents:</b> {len(successes)}/{len(agents_run)} succeeded\n"
        f"<b>Trades Submitted:</b> {len(submitted)}\n"
    )
    
    if submitted:
        for f in submitted:
            message += f"  • BUY {f.get('shares', '?')} {f.get('ticker', '?')}\n"
    
    if failures:
        message += f"\n<b>Failures:</b> {', '.join(failures)}\n"
    
    message += f"\n<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    send_telegram(message)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pipeline wrapper with crash protection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_with_crash_protection(pipeline_fn, pipeline_name: str = "pipeline", **kwargs):
    """
    Wrapper that catches any unhandled exception in the pipeline
    and sends a Telegram crash alert before re-raising.
    """
    try:
        return pipeline_fn(**kwargs)
    except Exception as e:
        send_crash_alert(pipeline_name, e)
        raise


if __name__ == "__main__":
    print("=== Safeguards Smoke Test ===\n")
    
    # Test 1: Market calendar
    print("1. Market Calendar Check:")
    cal = is_market_open_today()
    print(f"   is_open={cal.get('is_open')}, should_run={cal.get('should_run')}, reason={cal.get('reason')}")
    
    # Test 2: Penalty box
    print("\n2. Penalty Box:")
    print(f"   Current cooldowns: {get_penalty_box_tickers()}")
    
    # Test 3: Liquidity
    print("\n3. Liquidity Cap:")
    cap = cap_shares_by_volume(100, 150.0, 500_000)
    print(f"   100 shares of $150 stock with 500K ADV: {cap}")
    cap2 = cap_shares_by_volume(10000, 150.0, 500_000)
    print(f"   10000 shares of $150 stock with 500K ADV: {cap2}")
    
    print("\n✅ Safeguards module ready!")


==================================================================
FILE: alpaca_data.py (     352 lines)
==================================================================
"""
Alpaca Market Data Module — Replaces Yahoo Finance for price data.

Uses Alpaca's Market Data API via the paper trading credentials.
Free tier provides IEX real-time quotes, 5+ years of historical bars,
and options chain data.

Drop-in replacement for yfinance calls in preflight.py.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    StockSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame
import pandas as pd

# Initialize client — uses paper trading keys for market data
_client = None


def _get_client() -> StockHistoricalDataClient:
    global _client
    if _client is None:
        api_key = os.environ.get("ALPACA_API_KEY", "")
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        _client = StockHistoricalDataClient(api_key, secret_key)
    return _client


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch yesterday's close for a list of tickers via Alpaca.
    Drop-in replacement for preflight.fetch_prior_close().
    """
    client = _get_client()
    results = {}
    end = datetime.now()
    start = end - timedelta(days=10)

    for ticker in tickers:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                results[ticker] = {"error": f"No bar data for {ticker}"}
                continue

            # If multi-index (symbol, timestamp), slice to this ticker
            if isinstance(df.index, pd.MultiIndex):
                if ticker in df.index.get_level_values(0):
                    df = df.loc[ticker]
                else:
                    results[ticker] = {"error": f"No bar data for {ticker}"}
                    continue

            closes = [round(float(c), 2) for c in df["close"].values]
            dates = [str(d.date()) for d in df.index]

            # Prior close = last complete bar
            today_str = str(datetime.now().date())
            if dates[-1] == today_str and len(closes) >= 2:
                prior_close = closes[-2]
                prior_date = dates[-2]
            else:
                prior_close = closes[-1]
                prior_date = dates[-1]

            results[ticker] = {
                "prior_close": prior_close,
                "prior_date": prior_date,
                "closes_30d": closes,
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_latest_quotes(tickers: list) -> dict:
    """
    Fetch real-time (IEX) quotes for a list of tickers.
    Returns bid, ask, and mid price for each.
    """
    client = _get_client()
    results = {}

    try:
        request = StockLatestQuoteRequest(symbol_or_symbols=tickers)
        quotes = client.get_stock_latest_quote(request)

        for ticker, quote in quotes.items():
            results[ticker] = {
                "bid": float(quote.bid_price) if quote.bid_price else 0.0,
                "ask": float(quote.ask_price) if quote.ask_price else 0.0,
                "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                "mid": round((float(quote.bid_price or 0) + float(quote.ask_price or 0)) / 2, 2),
                "timestamp": quote.timestamp.isoformat() if quote.timestamp else "",
            }
    except Exception as e:
        for ticker in tickers:
            results[ticker] = {"error": str(e)}

    return results


def fetch_snapshots(tickers: list) -> dict:
    """
    Fetch full snapshots (latest trade, quote, minute bar, daily bar, prev daily bar).
    Richer than just quotes — includes today's OHLCV and previous day's bar.
    """
    client = _get_client()
    results = {}

    try:
        request = StockSnapshotRequest(symbol_or_symbols=tickers)
        snapshots = client.get_stock_snapshot(request)

        for ticker, snap in snapshots.items():
            entry = {}

            if snap.latest_trade:
                entry["latest_trade"] = {
                    "price": float(snap.latest_trade.price),
                    "size": int(snap.latest_trade.size),
                    "timestamp": snap.latest_trade.timestamp.isoformat() if snap.latest_trade.timestamp else "",
                }

            if snap.latest_quote:
                entry["latest_quote"] = {
                    "bid": float(snap.latest_quote.bid_price) if snap.latest_quote.bid_price else 0,
                    "ask": float(snap.latest_quote.ask_price) if snap.latest_quote.ask_price else 0,
                }

            if snap.daily_bar:
                entry["daily_bar"] = {
                    "open": float(snap.daily_bar.open),
                    "high": float(snap.daily_bar.high),
                    "low": float(snap.daily_bar.low),
                    "close": float(snap.daily_bar.close),
                    "volume": int(snap.daily_bar.volume),
                }

            if snap.previous_daily_bar:
                entry["prev_daily_bar"] = {
                    "open": float(snap.previous_daily_bar.open),
                    "high": float(snap.previous_daily_bar.high),
                    "low": float(snap.previous_daily_bar.low),
                    "close": float(snap.previous_daily_bar.close),
                    "volume": int(snap.previous_daily_bar.volume),
                }

            if snap.minute_bar:
                entry["minute_bar"] = {
                    "open": float(snap.minute_bar.open),
                    "high": float(snap.minute_bar.high),
                    "low": float(snap.minute_bar.low),
                    "close": float(snap.minute_bar.close),
                    "volume": int(snap.minute_bar.volume),
                    "timestamp": snap.minute_bar.timestamp.isoformat() if snap.minute_bar.timestamp else "",
                }

            results[ticker] = entry
    except Exception as e:
        for ticker in tickers:
            results[ticker] = {"error": str(e)}

    return results


def fetch_historical_bars(
    tickers: list,
    days: int = 30,
    timeframe: str = "day",
) -> dict:
    """
    Fetch historical OHLCV bars for a list of tickers.
    
    Args:
        tickers: List of ticker symbols
        days: Number of days of history (default 30)
        timeframe: "day", "hour", or "minute"
    """
    client = _get_client()

    tf_map = {
        "day": TimeFrame.Day,
        "hour": TimeFrame.Hour,
        "minute": TimeFrame.Minute,
    }
    tf = tf_map.get(timeframe, TimeFrame.Day)

    end = datetime.now()
    start = end - timedelta(days=days)
    results = {}

    for ticker in tickers:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=tf,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                results[ticker] = {"bars": [], "count": 0}
                continue

            # Handle multi-index
            if isinstance(df.index, pd.MultiIndex):
                if ticker in df.index.get_level_values(0):
                    df = df.loc[ticker]
                else:
                    results[ticker] = {"bars": [], "count": 0}
                    continue

            bar_list = []
            for ts, row in df.iterrows():
                bar_list.append({
                    "date": str(ts.date()) if tf == TimeFrame.Day else ts.isoformat(),
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": int(row["volume"]),
                    "vwap": round(float(row["vwap"]), 2) if pd.notna(row.get("vwap")) else None,
                })

            results[ticker] = {
                "bars": bar_list,
                "count": len(bar_list),
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_macro_tickers() -> dict:
    """
    Fetch macro indicator tickers that Alpaca supports.
    Replaces yfinance for VIX, sector ETFs, etc.
    
    Note: Alpaca doesn't support index tickers like ^VIX directly.
    We use VIXY/UVXY as VIX proxies, and sector ETFs work fine.
    For ^VIX, ^TNX, etc. we still fall back to yfinance.
    """
    # Alpaca supports ETFs and stocks, not raw indices
    # These are the tickers we CAN get from Alpaca
    alpaca_tickers = [
        # Sector ETFs (for breadth)
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        # Credit/bond ETFs
        "HYG", "LQD", "TLT", "JNK",
        # Broad market
        "SPY", "QQQ", "IWM",
        # Commodity proxies
        "GLD", "USO",
    ]

    return fetch_snapshots(alpaca_tickers)


def enrich_screener_universe(screener: list) -> list:
    """
    Enrich screener results with accurate prior_close from Alpaca.
    Drop-in replacement for preflight._enrich_prior_close().
    """
    tickers = [t["ticker"] for t in screener]

    # Batch into groups of 50 to avoid request size limits
    batch_size = 50
    all_closes = {}

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_results = fetch_prior_close(batch)
        all_closes.update(batch_results)

    for entry in screener:
        ticker = entry["ticker"]
        if ticker in all_closes and "prior_close" in all_closes[ticker]:
            entry["prior_close"] = all_closes[ticker]["prior_close"]
            entry["price_source"] = "alpaca"

    return screener


# Quick smoke test
if __name__ == "__main__":
    print("Testing Alpaca Market Data connection...\n")

    # Test 1: Latest quotes
    print("1. Latest quotes for SPY, AAPL, NVDA:")
    quotes = fetch_latest_quotes(["SPY", "AAPL", "NVDA"])
    for t, q in quotes.items():
        if "error" not in q:
            print(f"   {t}: bid={q['bid']:.2f} ask={q['ask']:.2f} mid={q['mid']:.2f}")
        else:
            print(f"   {t}: ERROR - {q['error']}")

    # Test 2: Prior close
    print("\n2. Prior close for SPY, AAPL:")
    closes = fetch_prior_close(["SPY", "AAPL"])
    for t, c in closes.items():
        if "error" not in c:
            print(f"   {t}: {c['prior_close']} (date: {c['prior_date']})")
        else:
            print(f"   {t}: ERROR - {c['error']}")

    # Test 3: Historical bars
    print("\n3. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars(["NVDA"], days=7)
    for bar in hist.get("NVDA", {}).get("bars", [])[-5:]:
        print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} V={bar['volume']:,}")

    # Test 4: Snapshot
    print("\n4. Snapshot for SPY:")
    snaps = fetch_snapshots(["SPY"])
    spy = snaps.get("SPY", {})
    if "latest_trade" in spy:
        print(f"   Latest trade: ${spy['latest_trade']['price']:.2f}")
    if "daily_bar" in spy:
        db = spy["daily_bar"]
        print(f"   Today's bar: O={db['open']} H={db['high']} L={db['low']} C={db['close']} V={db['volume']:,}")

    print("\n✅ Alpaca Market Data module working!")


==================================================================
FILE: massive_data.py (     467 lines)
==================================================================
"""
Massive Market Data Module — Polygon-compatible API for stocks, options, and technical indicators.

Free tier includes:
- Historical OHLCV bars (2 years, end-of-day)
- Previous day bar
- Built-in technical indicators (SMA, EMA, RSI, MACD)
- Minute aggregates
- 5 API calls/minute rate limit

Paid tiers add: real-time snapshots, options chains, greeks, WebSockets.

API base: https://api.massive.com
Auth: apiKey query parameter
"""
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.massive.com"
API_KEY = os.environ.get("MASSIVE_API_KEY", "")

# Rate limiter: free tier = 5 calls/min
_call_times: list = []
RATE_LIMIT = 5
RATE_WINDOW = 60  # seconds


def _rate_limit():
    """Simple rate limiter for free tier (5 calls/min)."""
    global _call_times
    now = time.time()
    _call_times = [t for t in _call_times if now - t < RATE_WINDOW]
    if len(_call_times) >= RATE_LIMIT:
        wait = RATE_WINDOW - (now - _call_times[0]) + 0.5
        if wait > 0:
            print(f"[Massive] Rate limit reached — waiting {wait:.1f}s")
            time.sleep(wait)
    _call_times.append(time.time())


def _get(endpoint: str, params: dict = None) -> dict:
    """Make an authenticated GET request to Massive API."""
    import requests

    if not API_KEY:
        return {"error": "MASSIVE_API_KEY not set in .env"}

    _rate_limit()

    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    params["apiKey"] = API_KEY

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("status") == "NOT_AUTHORIZED":
            return {"error": f"Not authorized: {data.get('message', 'upgrade plan')}"}
        return data
    except Exception as e:
        return {"error": str(e)}


# ─── Stock Aggregates ───────────────────────────────────────────────

def fetch_previous_day(ticker: str) -> dict:
    """Fetch previous trading day's OHLCV bar for a single ticker."""
    data = _get(f"/v2/aggs/ticker/{ticker}/prev")
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": f"No previous day data for {ticker}"}

    bar = results[0]
    return {
        "ticker": ticker,
        "open": bar.get("o"),
        "high": bar.get("h"),
        "low": bar.get("l"),
        "close": bar.get("c"),
        "volume": bar.get("v"),
        "vwap": bar.get("vw"),
        "transactions": bar.get("n"),
        "timestamp": bar.get("t"),
        "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d") if bar.get("t") else None,
    }


def fetch_prior_close_batch(tickers: list) -> dict:
    """
    Fetch previous day's close for multiple tickers.
    Note: free tier is 5 calls/min, so this is rate-limited.
    For large batches, prefer Alpaca. Use Massive for enrichment.
    """
    results = {}
    for ticker in tickers:
        prev = fetch_previous_day(ticker)
        if "error" not in prev:
            results[ticker] = {
                "prior_close": round(prev["close"], 2),
                "prior_date": prev["date"],
                "prior_open": round(prev["open"], 2),
                "prior_high": round(prev["high"], 2),
                "prior_low": round(prev["low"], 2),
                "prior_volume": prev["volume"],
                "prior_vwap": round(prev["vwap"], 2) if prev["vwap"] else None,
                "source": "massive",
            }
        else:
            results[ticker] = {"error": prev["error"]}
    return results


def fetch_historical_bars(
    ticker: str,
    days: int = 30,
    timespan: str = "day",
    multiplier: int = 1,
) -> dict:
    """
    Fetch historical OHLCV bars for a ticker.

    Args:
        ticker: Stock symbol
        days: Number of calendar days of history
        timespan: "day", "hour", or "minute"
        multiplier: Bar size multiplier (e.g., 5 with minute = 5-min bars)
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data = _get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}",
        params={"sort": "asc", "limit": 5000},
    )

    if "error" in data:
        return data

    results = data.get("results", [])
    bars = []
    for bar in results:
        bars.append({
            "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d") if timespan == "day" else datetime.fromtimestamp(bar["t"] / 1000).isoformat(),
            "open": round(bar["o"], 2),
            "high": round(bar["h"], 2),
            "low": round(bar["l"], 2),
            "close": round(bar["c"], 2),
            "volume": bar.get("v", 0),
            "vwap": round(bar["vw"], 2) if bar.get("vw") else None,
            "transactions": bar.get("n"),
        })

    return {
        "ticker": ticker,
        "bars": bars,
        "count": len(bars),
        "source": "massive",
    }


# ─── Technical Indicators (FREE — this is the killer feature) ────────

def fetch_sma(ticker: str, window: int = 20, timespan: str = "day", limit: int = 30) -> dict:
    """
    Fetch Simple Moving Average values.
    Built-in — no local calculation needed.
    """
    data = _get(
        f"/v1/indicators/sma/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    return {
        "ticker": ticker,
        "indicator": f"SMA_{window}",
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 4),
            }
            for v in values
        ],
        "current": round(values[0]["value"], 4) if values else None,
        "source": "massive",
    }


def fetch_ema(ticker: str, window: int = 20, timespan: str = "day", limit: int = 30) -> dict:
    """Fetch Exponential Moving Average values."""
    data = _get(
        f"/v1/indicators/ema/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    return {
        "ticker": ticker,
        "indicator": f"EMA_{window}",
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 4),
            }
            for v in values
        ],
        "current": round(values[0]["value"], 4) if values else None,
        "source": "massive",
    }


def fetch_rsi(ticker: str, window: int = 14, timespan: str = "day", limit: int = 30) -> dict:
    """
    Fetch Relative Strength Index.
    RSI > 70 = overbought, RSI < 30 = oversold.
    """
    data = _get(
        f"/v1/indicators/rsi/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    current_rsi = round(values[0]["value"], 2) if values else None

    # Classify RSI
    signal = "neutral"
    if current_rsi:
        if current_rsi >= 70:
            signal = "overbought"
        elif current_rsi >= 60:
            signal = "bullish"
        elif current_rsi <= 30:
            signal = "oversold"
        elif current_rsi <= 40:
            signal = "bearish"

    return {
        "ticker": ticker,
        "indicator": f"RSI_{window}",
        "current": current_rsi,
        "signal": signal,
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 2),
            }
            for v in values
        ],
        "source": "massive",
    }


def fetch_macd(
    ticker: str,
    short_window: int = 12,
    long_window: int = 26,
    signal_window: int = 9,
    timespan: str = "day",
    limit: int = 30,
) -> dict:
    """
    Fetch MACD (Moving Average Convergence Divergence).
    Returns MACD line, signal line, and histogram.
    """
    data = _get(
        f"/v1/indicators/macd/{ticker}",
        params={
            "timespan": timespan,
            "short_window": short_window,
            "long_window": long_window,
            "signal_window": signal_window,
            "series_type": "close",
            "limit": limit,
            "order": "desc",
        },
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    if not values:
        return {"ticker": ticker, "indicator": "MACD", "error": "No data"}

    current = values[0]
    macd_val = round(current.get("value", 0), 4)
    signal_val = round(current.get("signal", 0), 4)
    histogram = round(current.get("histogram", 0), 4)

    # Classify signal
    signal = "neutral"
    if histogram > 0 and macd_val > signal_val:
        signal = "bullish"
    elif histogram < 0 and macd_val < signal_val:
        signal = "bearish"

    # Check for crossover (compare current vs previous)
    crossover = None
    if len(values) >= 2:
        prev = values[1]
        prev_hist = prev.get("histogram", 0)
        if prev_hist <= 0 < histogram:
            crossover = "bullish_crossover"
        elif prev_hist >= 0 > histogram:
            crossover = "bearish_crossover"

    return {
        "ticker": ticker,
        "indicator": "MACD",
        "macd": macd_val,
        "signal_line": signal_val,
        "histogram": histogram,
        "signal": signal,
        "crossover": crossover,
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "macd": round(v.get("value", 0), 4),
                "signal": round(v.get("signal", 0), 4),
                "histogram": round(v.get("histogram", 0), 4),
            }
            for v in values[:10]  # Last 10 days
        ],
        "source": "massive",
    }


def fetch_full_technicals(ticker: str) -> dict:
    """
    Fetch a complete technical analysis package for a single ticker.
    Returns previous day bar + RSI(14) + MACD.
    
    Optimized for free tier rate limits (5 calls/min):
    - 3 API calls per ticker (prev_day, RSI, MACD)
    - SMA is computed locally from historical bars when possible
    """
    result = {"ticker": ticker, "source": "massive", "timestamp": datetime.now().isoformat()}

    # 1. Previous day bar (1 call)
    prev = fetch_previous_day(ticker)
    if "error" not in prev:
        result["price"] = round(prev["close"], 2)
        result["prev_open"] = round(prev["open"], 2)
        result["prev_high"] = round(prev["high"], 2)
        result["prev_low"] = round(prev["low"], 2)
        result["prev_volume"] = prev["volume"]
        result["prev_vwap"] = round(prev["vwap"], 2) if prev.get("vwap") else None

    # 2. RSI (1 call)
    rsi = fetch_rsi(ticker, window=14, limit=5)
    result["rsi_14"] = rsi.get("current")
    result["rsi_signal"] = rsi.get("signal")

    # 3. MACD (1 call)
    macd = fetch_macd(ticker, limit=5)
    result["macd"] = macd.get("macd")
    result["macd_signal"] = macd.get("signal_line")
    result["macd_histogram"] = macd.get("histogram")
    result["macd_trend"] = macd.get("signal")
    result["macd_crossover"] = macd.get("crossover")

    return result


def fetch_technicals_with_sma(ticker: str) -> dict:
    """
    Full technicals including SMA(20) and SMA(50).
    Uses 5 API calls — consumes entire free tier minute quota for one ticker.
    Use sparingly (e.g., only for SPY or the top pick).
    """
    result = fetch_full_technicals(ticker)  # 3 calls

    # 4. SMA(20) (1 call)
    sma_20 = fetch_sma(ticker, window=20, limit=3)
    result["sma_20"] = sma_20.get("current")

    # 5. SMA(50) (1 call)
    sma_50 = fetch_sma(ticker, window=50, limit=3)
    result["sma_50"] = sma_50.get("current")

    # Price vs MAs
    price = result.get("price")
    if price:
        if result.get("sma_20"):
            result["price_vs_sma20"] = "above" if price > result["sma_20"] else "below"
        if result.get("sma_50"):
            result["price_vs_sma50"] = "above" if price > result["sma_50"] else "below"

    return result


def format_technicals_for_prompt(technicals: dict) -> str:
    """Format technical analysis data for agent prompts."""
    t = technicals
    lines = [
        f"TECHNICAL ANALYSIS: {t['ticker']}",
        f"  Price: ${t.get('price', '?')}",
        f"  SMA(20): {t.get('sma_20', 'N/A')} ({t.get('price_vs_sma20', '?')})",
        f"  SMA(50): {t.get('sma_50', 'N/A')} ({t.get('price_vs_sma50', '?')})",
        f"  RSI(14): {t.get('rsi_14', 'N/A')} ({t.get('rsi_signal', '?')})",
        f"  MACD: {t.get('macd', 'N/A')} | Signal: {t.get('macd_signal', 'N/A')} | Hist: {t.get('macd_histogram', 'N/A')}",
        f"  MACD Trend: {t.get('macd_trend', '?')} | Crossover: {t.get('macd_crossover', 'none')}",
    ]
    return "\n".join(lines)


# ─── Smoke Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Massive Market Data API...\n")

    # Test 1: Previous day bar
    print("1. Previous day bar for AAPL:")
    prev = fetch_previous_day("AAPL")
    if "error" not in prev:
        print(f"   {prev['date']}: O={prev['open']} H={prev['high']} L={prev['low']} C={prev['close']} V={prev['volume']:,.0f}")
    else:
        print(f"   ERROR: {prev['error']}")

    # Test 2: Historical bars
    print("\n2. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars("NVDA", days=7)
    if "error" not in hist:
        for bar in hist["bars"][-5:]:
            print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} VWAP={bar['vwap']}")
    else:
        print(f"   ERROR: {hist['error']}")

    # Test 3: Technical indicators
    print("\n3. RSI(14) for NVDA:")
    rsi = fetch_rsi("NVDA")
    if "error" not in rsi:
        print(f"   Current RSI: {rsi['current']} ({rsi['signal']})")
    else:
        print(f"   ERROR: {rsi}")

    print("\n4. MACD for NVDA:")
    macd = fetch_macd("NVDA")
    if "error" not in macd:
        print(f"   MACD: {macd['macd']} | Signal: {macd['signal_line']} | Hist: {macd['histogram']}")
        print(f"   Trend: {macd['signal']} | Crossover: {macd['crossover']}")
    else:
        print(f"   ERROR: {macd}")

    # Test 4: Full technicals package
    print("\n5. Full technicals for SPY:")
    tech = fetch_full_technicals("SPY")
    print(format_technicals_for_prompt(tech))

    print("\n✅ Massive Market Data module working!")


==================================================================
FILE: broker.py (     249 lines)
==================================================================
"""
Broker Module — Alpaca Paper Trading Integration
Executes tear sheet orders, manages positions, and tracks fills.

All orders go through Alpaca's paper trading API.
Real account size from Alpaca overrides config.py ACCOUNT_SIZE.

Usage:
  from broker import AlpacaBroker
  broker = AlpacaBroker()
  broker.execute_tear_sheet(trade_orders)
  broker.get_positions()
  broker.close_position("AAPL")
"""
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    GetOrdersRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus


class AlpacaBroker:
    def __init__(self):
        self.client = TradingClient(
            api_key=os.environ.get("ALPACA_API_KEY", ""),
            secret_key=os.environ.get("ALPACA_SECRET_KEY", ""),
            paper=True,
        )
        self._verify_connection()

    def _verify_connection(self):
        account = self.client.get_account()
        if account.status != "ACTIVE":
            raise RuntimeError(f"Alpaca account not active: {account.status}")
        print(f"[Broker] Connected to Alpaca paper account")
        print(f"[Broker] Cash: ${float(account.cash):,.2f} | Equity: ${float(account.equity):,.2f}")

    def get_account_summary(self) -> dict:
        """Get current account state."""
        account = self.client.get_account()
        return {
            "cash": float(account.cash),
            "equity": float(account.equity),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "status": account.status,
        }

    def get_positions(self) -> list:
        """Get all open positions."""
        positions = self.client.get_all_positions()
        result = []
        for p in positions:
            result.append({
                "ticker": p.symbol,
                "shares": int(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            })
        return result

    def get_existing_exposure(self) -> float:
        """Get total dollar value of existing positions (for dry powder calc)."""
        positions = self.get_positions()
        return sum(p["market_value"] for p in positions)

    def get_position_tickers(self) -> list:
        """Get list of tickers with open positions (for correlation veto)."""
        positions = self.get_positions()
        return [p["ticker"] for p in positions]

    def execute_tear_sheet(self, trade_orders: list) -> list:
        """
        Execute BUY orders from Agent 4B's tear sheet.
        Uses market orders at 9:30 AM (market open).
        Returns list of fill results.
        """
        fills = []
        for order in trade_orders:
            if order.get("action") != "BUY":
                fills.append({
                    "ticker": order.get("ticker", "?"),
                    "status": "skipped",
                    "reason": order.get("reason", order.get("action", "not a BUY")),
                })
                continue

            ticker = order["ticker"]
            shares = order["shares"]

            try:
                # Use OTC (One-Triggers-Cancel) with attached stop-loss if stop price available
                stop_price = order.get("stop_loss")
                if stop_price and stop_price > 0:
                    req = MarketOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        order_class="oto",
                        stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
                    )
                else:
                    req = MarketOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                    )
                result = self.client.submit_order(req)
                fills.append({
                    "ticker": ticker,
                    "status": "submitted",
                    "order_id": str(result.id),
                    "shares": shares,
                    "order_type": "market",
                    "submitted_at": result.submitted_at.isoformat() if result.submitted_at else "",
                })
                print(f"  [Broker] BUY {shares} {ticker} — order submitted ({result.id})")

            except Exception as e:
                fills.append({
                    "ticker": ticker,
                    "status": "error",
                    "error": str(e),
                })
                print(f"  [Broker] ERROR on {ticker}: {e}")

        # Save fills
        os.makedirs("output", exist_ok=True)
        with open("output/broker_fills.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "fills": fills,
            }, f, indent=2)

        return fills

    def close_position(self, ticker: str, qty: int = None) -> dict:
        """
        Close a position (full or partial).
        Used by Agent 5 for CLOSE and TRIM decisions.
        """
        try:
            if qty:
                # Partial close (TRIM)
                req = MarketOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                result = self.client.submit_order(req)
                print(f"  [Broker] TRIM {qty} shares of {ticker} — submitted ({result.id})")
            else:
                # Full close
                result = self.client.close_position(ticker)
                print(f"  [Broker] CLOSE {ticker} — submitted")

            return {
                "ticker": ticker,
                "status": "submitted",
                "action": "trim" if qty else "close",
                "qty": qty,
            }
        except Exception as e:
            print(f"  [Broker] ERROR closing {ticker}: {e}")
            return {"ticker": ticker, "status": "error", "error": str(e)}

    def close_all_positions(self) -> dict:
        """
        CRISIS_LIQUIDATION — close everything at market.
        Used by Agent 5 when CRISIS pre-check triggers.
        """
        try:
            result = self.client.close_all_positions(cancel_orders=True)
            print(f"  [Broker] CRISIS_LIQUIDATION — closing all positions")
            return {"status": "submitted", "action": "close_all"}
        except Exception as e:
            print(f"  [Broker] ERROR on close_all: {e}")
            return {"status": "error", "error": str(e)}

    def execute_agent5_decisions(self, decisions: list, crisis: bool = False) -> list:
        """
        Execute Agent 5's HOLD/TRIM/CLOSE decisions.
        """
        if crisis:
            self.close_all_positions()
            return [{"action": "CRISIS_LIQUIDATION", "status": "submitted"}]

        results = []
        for d in decisions:
            ticker = d.get("ticker")
            action = d.get("action", "HOLD")

            if action == "HOLD":
                results.append({"ticker": ticker, "action": "HOLD", "status": "no_action"})

            elif action == "CLOSE":
                result = self.close_position(ticker)
                results.append(result)

            elif action == "TRIM":
                trim_pct = d.get("trim_pct", 50) / 100
                positions = self.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)
                if pos:
                    trim_qty = max(1, int(pos["shares"] * trim_pct))
                    result = self.close_position(ticker, qty=trim_qty)
                    results.append(result)
                else:
                    results.append({"ticker": ticker, "action": "TRIM", "status": "no_position"})

        return results

    def get_orders_today(self) -> list:
        """Get all orders from today."""
        try:
            req = GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                limit=50,
            )
            orders = self.client.get_orders(req)
            return [{
                "ticker": o.symbol,
                "side": str(o.side),
                "qty": str(o.qty),
                "filled_qty": str(o.filled_qty),
                "status": str(o.status),
                "filled_avg_price": str(o.filled_avg_price) if o.filled_avg_price else None,
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else "",
            } for o in orders]
        except Exception as e:
            return [{"error": str(e)}]


==================================================================
FILE: agent1_macro_director.py (     247 lines)
==================================================================
"""
Agent 1: Macro Director — v2 (Jamie's Golden Path tweaks)
Model: Claude (Anthropic)
Role: Classify the current market regime and issue a directive.

Changes from v1:
- Removed S&P 500, DXY, Gold from inputs
- Added MOVE, DIX, Sector Breadth
- Enforced kill-switch: missing DIX/MOVE/Credit → REGIME: Defer
- Locked posture table from Page 8
- Added VOL_REGIME output (Compressed/Normal/Elevated/Stressed)
- Removed "max_positions" and "allocation_caps" — that's Agent 4's job
"""
import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are Agent 1: The Macro Director for a $100,000 speculative spot-only trading account.

YOUR SOLE JOB: Read the macro data provided and classify the current market regime. You do NOT pick stocks. You do NOT make trade recommendations. You do NOT set position limits or allocation caps — that is Agent 4's job.

REGIME CLASSIFICATIONS (pick exactly one):
1. RISK-ON — Bull trend intact, volatility low/falling, spreads tight, dark pool buying strong
2. CAUTIOUS RISK-ON — Generally positive but with yellow flags (elevated VIX, mixed signals)
3. RISK-OFF — Defensive posture. Rising vol, widening spreads, flight to safety underway
4. CRISIS — Extreme stress. VIX >35, MOVE >150, credit markets seizing
5. DEFER — MANDATORY if DIX, MOVE, or Credit data is missing/unavailable. Do NOT hallucinate a regime without these inputs.

KILL-SWITCH RULE (NON-NEGOTIABLE):
If MOVE index data OR Credit spread data is listed as "DATA UNAVAILABLE" or missing, you MUST output REGIME: DEFER. Do not guess. Do not proceed without these critical inputs.
If DIX data is unavailable, you MAY proceed but MUST note it in missing_data and reduce your confidence by 2 points. Do NOT attempt to guess DIX values.

VOL REGIME (MANDATORY OUTPUT — Agent 4 needs this exact string):
Based on VIX level and MOVE index:
- COMPRESSED: VIX < 14 AND MOVE < 90
- NORMAL: VIX 14-20 AND MOVE 90-120
- ELEVATED: VIX 20-30 OR MOVE 120-150
- STRESSED: VIX > 30 OR MOVE > 150

POSTURE TABLE (USE EXACTLY — from Page 8 of spec):
- RISK-ON → POSTURE: Aggressive, CONVICTION_FLOOR: 5
- CAUTIOUS RISK-ON → POSTURE: Offensive, CONVICTION_FLOOR: 6
- RISK-OFF → POSTURE: Defensive, CONVICTION_FLOOR: 7
- CRISIS → POSTURE: Bunker, CONVICTION_FLOOR: 9
- DEFER → POSTURE: Hold, CONVICTION_FLOOR: 10

DECISION INPUTS (what you should analyze):
- VIX: Fear gauge for equity volatility
- MOVE: Bond market volatility — rising MOVE with falling VIX = divergence warning
- DIX: Dark pool buying index — high DIX (>45) = institutional accumulation, low DIX (<40) = distribution
- Yield curve (10Y-2Y spread): Inverted = recession risk
- HY spread proxy (HYG/LQD ratio): Falling = credit stress
- Sector breadth: % of sectors above 20DMA — broad participation vs narrow leadership

ASSEMBLY PRIVATE DATA (if provided):
You may also receive Assembly sentiment and macro data. Use these for additional signal confirmation:
- Assembly Sentiment Composite (0-100): <25 = Extreme Fear, 25-45 = Fear, 45-55 = Neutral, 55-75 = Greed, >75 = Extreme Greed
- Sub-components: VIX sentiment, momentum, price strength, breadth, put/call, junk bond demand, safe haven demand
- Cross-asset rotation: equities vs bonds vs gold vs oil vs USD with 50d/200d trends
- Risk & Credit Gauges: VIX, VXN, MOVE, HYG, LQD, JNK with trend context
- Sector rotation with RS vs SPY: identifies sector leadership
- Full yield curve (1M through 30Y)
These are supplementary — your core regime classification still relies on VIX, MOVE, credit, and breadth.

PREFERRED THEMES: Based on regime, suggest 1-3 macro themes Agent 2 should focus on.

You MUST output valid JSON matching this EXACT schema — no extra fields:
{
  "agent": "macro_director",
  "timestamp": "<ISO timestamp>",
  "regime": "<RISK-ON | CAUTIOUS RISK-ON | RISK-OFF | CRISIS | DEFER>",
  "vol_regime": "<COMPRESSED | NORMAL | ELEVATED | STRESSED>",
  "posture": "<Aggressive | Offensive | Defensive | Bunker | Hold>",
  "conviction_floor": <integer 5-10>,
  "preferred_themes": ["<theme1>", "<theme2>"],
  "summary": "<2-3 sentence plain English summary>",
  "key_signals": {
    "vix_read": "<description>",
    "move_read": "<description>",
    "dix_read": "<description>",
    "yield_curve_read": "<description>",
    "credit_read": "<description>",
    "breadth_read": "<description>"
  },
  "missing_data": ["<list any unavailable data feeds>"]
}

Do NOT output "max_positions_today", "allocation_cap_pct", or any position sizing fields. That is Agent 4's domain.

Be decisive. Pick a regime and commit."""


def run_agent1(macro_data: dict = None) -> dict:
    """Run Agent 1: Read macro data, send to Claude, return structured directive."""

    # Load macro data from pre-flight if not passed
    if macro_data is None:
        macro_path = "output/preflight_macro.json"
        if not os.path.exists(macro_path):
            return {"success": False, "error": "No pre-flight macro data found. Run preflight.py first."}
        with open(macro_path, "r") as f:
            macro_data = json.load(f)

    # Format for prompt
    from preflight import format_macro_for_prompt, format_assembly_for_prompt
    macro_text = format_macro_for_prompt(macro_data)

    # Load Assembly data if available
    assembly_text = ""
    assembly_path = "output/assembly_data.json"
    if os.path.exists(assembly_path):
        try:
            with open(assembly_path) as f:
                assembly_data = json.load(f)
            assembly_text = "\n\n" + format_assembly_for_prompt(assembly_data)
            print("[Agent 1] Assembly Private data loaded")
        except Exception as e:
            print(f"[Agent 1] Assembly data load failed: {e}")

    print(f"[Agent 1] Macro data loaded from {macro_data.get('timestamp', 'unknown')}")

    # Send to Claude
    print("[Agent 1] Sending to Claude for regime classification...")

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform instead.")
        client = anthropic.Anthropic(api_key=api_key)

        user_message = f"""Here is today's macro data. Classify the regime and produce your directive.

CRITICAL: If DIX, MOVE, or Credit data is marked as unavailable, you MUST output REGIME: DEFER.

{macro_text}{assembly_text}

Current date/time: {datetime.now().isoformat()}

Respond with ONLY the JSON directive, no other text."""

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000,
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # With extended thinking, content has thinking + text blocks
        raw_text = next(b.text for b in response.content if b.type == "text").strip()
    except RuntimeError:
        # No API key — return the prompt for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "prompt": SYSTEM_PROMPT,
            "macro_text": macro_text,
        }

    # Parse response
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

    try:
        directive = json.loads(raw_text)

        # Validate required fields
        required = ["regime", "vol_regime", "posture", "conviction_floor"]
        for field in required:
            if field not in directive:
                return {"success": False, "error": f"Missing required field: {field}", "raw": raw_text}

        # Strip any hallucinated position-sizing fields
        for bad_field in ["max_positions_today", "allocation_cap_pct", "max_positions", "allocation_cap"]:
            directive.pop(bad_field, None)

        print(f"[Agent 1] Regime: {directive.get('regime')} | Vol: {directive.get('vol_regime')} | Posture: {directive.get('posture')}")
        return {"success": True, "directive": directive, "raw_macro_data": macro_data}
    except json.JSONDecodeError as e:
        print(f"[Agent 1] ERROR: Failed to parse response as JSON: {e}")
        return {"success": False, "error": str(e), "raw_response": raw_text}


def format_directive_for_telegram(result: dict) -> str:
    """Format Agent 1 output as a readable Telegram message."""
    if not result["success"]:
        return f"⚠️ Agent 1 FAILED: {result.get('error', 'Unknown error')}"

    d = result["directive"]
    regime_emoji = {
        "RISK-ON": "🟢",
        "CAUTIOUS RISK-ON": "🟡",
        "RISK-OFF": "🟠",
        "CRISIS": "🔴",
        "DEFER": "⚪",
    }
    emoji = regime_emoji.get(d.get("regime", ""), "⚪")

    lines = [
        f"{'='*30}",
        f"📊 AGENT 1: MACRO DIRECTOR (v2)",
        f"{'='*30}",
        f"",
        f"{emoji} Regime: {d.get('regime')}",
        f"📈 Vol Regime: {d.get('vol_regime')}",
        f"📋 Posture: {d.get('posture')}",
        f"🎯 Conviction Floor: {d.get('conviction_floor')}",
        f"",
        f"🎪 Themes: {', '.join(d.get('preferred_themes', []))}",
        f"",
        f"💬 {d.get('summary', '')}",
        f"",
        f"📡 Key Signals:",
    ]

    signals = d.get("key_signals", {})
    for key, val in signals.items():
        label = key.replace("_read", "").replace("_", " ").upper()
        lines.append(f"  • {label}: {val}")

    missing = d.get("missing_data", [])
    if missing:
        lines.append(f"")
        lines.append(f"⚠️ Missing data: {', '.join(missing)}")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent1()
    print("\n" + format_directive_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent1_directive.json", "w") as f:
            json.dump(result["directive"], f, indent=2)
        print(f"\n[Agent 1] Directive saved to output/agent1_directive.json")


==================================================================
FILE: agent2_fundamental_screener.py (     485 lines)
==================================================================
"""
Agent 2: Fundamental Screener — v3.0 (Opus 4.7 Adaptive Thinking)
Model: Claude Opus 4.7 (Anthropic) with adaptive thinking
Role: Given Agent 1's directive + SCREENER_UNIVERSE + FUNDAMENTAL_DATA
      (all pre-fetched by Python), select 1-3 tickers with rigorous analysis.

Changes from v2.1:
- Switched from Gemini 3.1 Pro to Claude Opus 4.7 with adaptive thinking
- Deep research protocol: forced chain-of-thought via <research_scratchpad>
- Strict JSON schema enforcement for data types
- Python pre-fetches ALL fundamental data — model does NOT fetch or browse
- Verbatim THEME_MATCH, SOURCE enum
"""
import json
import os
import time
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv
import anthropic

load_dotenv()

# Claude Opus 4.7 with adaptive thinking
MODEL = "claude-opus-4-7"
MAX_RETRIES = 3
RETRY_DELAY = 5
TEMPERATURE = 0.1

SYSTEM_PROMPT = """You are Agent 2: The Fundamental Screener for a $100,000 speculative spot-only trading account.

YOUR JOB: Given Agent 1's regime directive, a pre-filtered SCREENER_UNIVERSE, and pre-fetched FUNDAMENTAL_DATA (all provided by Python — you do NOT fetch any data yourself), select 1-3 candidates through rigorous quantitative analysis.

CRITICAL RULES:
1. You may ONLY select tickers from the provided SCREENER_UNIVERSE list. Do NOT suggest any ticker not on the list. Do NOT fetch, browse, or look up any data — use ONLY what Python injected into this prompt.
2. CONVICTION_TIER must be exactly one of: PASS, STRONG, or EXCEPTIONAL (string enum). Numeric scores are FORBIDDEN and will crash the pipeline.
   - PASS: Meets all screens, thesis is coherent, no red flags. Default state for any candidate that survives Step 3.
   - STRONG: PASS + at least two of: (a) clear near-term catalyst, (b) valuation in bottom tercile, (c) momentum confirmed by price > MA50 > MA200.
   - EXCEPTIONAL: STRONG + thesis is asymmetric AND theme is the single strongest in Agent 1's preferred themes.
   - Do NOT output STRONG or EXCEPTIONAL for more than one candidate per run unless explicitly justified in screening_notes.
3. You must COPY the PREFERRED_THEME string from Agent 1 EXACTLY character-for-character into your THEME_MATCH field. Do not summarize, paraphrase, or reword it even slightly.
4. SOURCE must be exactly one of: "Newsletter" or "Screener Stage 2" (enum). For screener-sourced picks, use "Screener Stage 2".
5. Each candidate needs a rigorous quantitative thesis grounded in the FUNDAMENTAL_DATA provided, plus a specific near-term catalyst.
6. If the regime is DEFER, CRISIS with Bunker posture, output an empty candidates array.
7. All surviving candidates must be at least PASS tier.

<deep_research_protocol>
CRITICAL: You must conduct your analysis inside a <research_scratchpad> block before generating your final structured output.
Step 1: Inventory the exact numerical data and fundamentals injected by Python.
Step 2: Verify the asset passes the >$5 price and >$100M market cap constraints.
Step 3: Argue the downside. Why might this setup fail? (Play Devil's Advocate).
Step 4: Brutally interrogate the fundamentals to assign a CONVICTION_TIER (PASS, STRONG, or EXCEPTIONAL).
Step 5: Ensure the THEME_MATCH is a verbatim, character-for-character echo of Agent 1's theme.
Only after completing this <research_scratchpad> block may you output the final JSON.
</deep_research_protocol>

OUTPUT FORMAT:
First, output your <research_scratchpad>...</research_scratchpad> analysis.
Then, output ONLY this JSON structure (no markdown, no code blocks):
{
  "agent": "fundamental_screener",
  "timestamp": "<ISO timestamp>",
  "regime_received": "<regime from Agent 1>",
  "candidates": [
    {
      "ticker": "<SYMBOL from SCREENER_UNIVERSE>",
      "name": "<company name>",
      "type": "<equity | sector ETF | commodity ETF | crypto>",
      "theme_match": "<EXACT string from Agent 1 preferred_themes>",
      "conviction_tier": "<PASS | STRONG | EXCEPTIONAL>",
      "thesis": "<2-3 sentences grounded in the numerical fundamentals>",
      "catalyst": "<specific near-term catalyst>",
      "source": "Screener Stage 2"
    }
  ],
  "screening_notes": "<brief note on selection process and rejected names>"
}"""

# Strict JSON schema for structured outputs (Jamie fix #3)
# This prevents Gemini from outputting "HIGH" instead of an integer
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string"},
        "timestamp": {"type": "string"},
        "regime_received": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["equity", "sector ETF", "commodity ETF", "crypto"]},
                    "theme_match": {"type": "string"},
                    "conviction_tier": {"type": "string", "enum": ["PASS", "STRONG", "EXCEPTIONAL"]},
                    "thesis": {"type": "string"},
                    "catalyst": {"type": "string"},
                    "source": {"type": "string", "enum": ["Newsletter", "Screener Stage 2"]},
                },
                "required": ["ticker", "name", "type", "theme_match", "conviction_score", "thesis", "catalyst", "source"],
            },
        },
        "screening_notes": {"type": "string"},
    },
    "required": ["agent", "timestamp", "regime_received", "candidates", "screening_notes"],
}


def prefetch_fundamental_data(screener_universe: list) -> dict:
    """
    Pre-fetch ALL fundamental data for the screener universe.
    Uses bulk yf.download() for price history (much faster than per-ticker),
    then per-ticker yf.Ticker().info for fundamentals.
    """
    fundamentals = {}
    tickers_list = [t["ticker"] for t in screener_universe]
    print(f"  [Agent 2] Pre-fetching fundamentals for {len(tickers_list)} tickers (bulk download)...")

    # Bulk download price history — much faster than individual calls
    try:
        bulk_hist = yf.download(tickers_list, period="1mo", group_by="ticker", threads=True, progress=False)
    except Exception as e:
        print(f"  [Agent 2] Bulk download failed: {e}, falling back to per-ticker")
        bulk_hist = None

    for entry in screener_universe:
        ticker = entry["ticker"]
        try:
            # Get price data from bulk download
            if bulk_hist is not None and len(tickers_list) > 1:
                try:
                    hist = bulk_hist[ticker]
                    closes = [float(c) for c in hist["Close"].dropna().values.flatten()]
                    volumes = [int(v) for v in hist["Volume"].dropna().values.flatten()]
                except (KeyError, TypeError):
                    closes = []
                    volumes = []
            else:
                hist = yf.Ticker(ticker).history(period="1mo")
                closes = [float(c) for c in hist["Close"].values.flatten()] if not hist.empty else []
                volumes = [int(v) for v in hist["Volume"].values.flatten()] if not hist.empty else []

            if not closes:
                fundamentals[ticker] = {"error": "No price history"}
                continue

            # Get fundamentals from .info (still per-ticker, but these are fast)
            stock = yf.Ticker(ticker)
            info = stock.info

            prior_close = closes[-1]
            price_5d = closes[-5] if len(closes) >= 5 else prior_close
            price_20d = closes[0]
            avg_vol = int(sum(volumes) / len(volumes)) if volumes else 0

            fundamentals[ticker] = {
                "prior_close": round(prior_close, 2),
                "change_5d_pct": round((prior_close - price_5d) / price_5d * 100, 2),
                "change_20d_pct": round((prior_close - price_20d) / price_20d * 100, 2),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "profit_margin": info.get("profitMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"),
                "beta": info.get("beta"),
                "sector": info.get("sector", "N/A"),
                "avg_volume_20d": avg_vol,
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
            }
        except Exception as e:
            fundamentals[ticker] = {"error": str(e)}

    fetched = len([v for v in fundamentals.values() if "error" not in v])
    print(f"  [Agent 2] Fetched fundamentals for {fetched}/{len(screener_universe)} tickers")
    return fundamentals


def call_opus(directive: dict, screener_universe: list, fundamental_data: dict, held_tickers: list = None) -> dict:
    """
    Send directive + screener + fundamentals to Claude Opus 4.7.
    Uses adaptive thinking (extended thinking with budget_tokens).
    Falls back to needs_subagent if no ANTHROPIC_API_KEY.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform instead.")

    client = anthropic.Anthropic(api_key=api_key)

    # Build enriched screener summary with full fundamentals
    screener_lines = []
    for s in screener_universe:
        ticker = s["ticker"]
        fund = fundamental_data.get(ticker, {})

        if "error" in fund:
            continue

        mkt_cap = fund.get("market_cap", 0)
        cap_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap and mkt_cap > 1e9 else f"${mkt_cap/1e6:.0f}M" if mkt_cap else "N/A"

        line = (
            f"  {ticker} | {s.get('name', '')} | {s.get('sector', 'N/A')}\n"
            f"    Prior Close: ${fund.get('prior_close', '?')} | Mkt Cap: {cap_str}\n"
            f"    5d Change: {fund.get('change_5d_pct', '?')}% | 20d Change: {fund.get('change_20d_pct', '?')}%\n"
            f"    P/E: {fund.get('pe_ratio', 'N/A')} | Fwd P/E: {fund.get('forward_pe', 'N/A')} | PEG: {fund.get('peg_ratio', 'N/A')}\n"
            f"    P/B: {fund.get('price_to_book', 'N/A')} | Beta: {fund.get('beta', 'N/A')}\n"
            f"    Rev Growth: {fund.get('revenue_growth', 'N/A')} | Earnings Growth: {fund.get('earnings_growth', 'N/A')}\n"
            f"    Profit Margin: {fund.get('profit_margin', 'N/A')} | D/E: {fund.get('debt_to_equity', 'N/A')}\n"
            f"    FCF: {fund.get('free_cash_flow', 'N/A')} | 52w: ${fund.get('52w_low', '?')} — ${fund.get('52w_high', '?')}"
        )
        screener_lines.append(line)

    screener_text = "\n".join(screener_lines)

    user_message = f"""Here is Agent 1's directive and the pre-filtered SCREENER_UNIVERSE with FUNDAMENTAL_DATA.
ALL data has been pre-fetched by Python. Do NOT look up, browse, or fetch any additional data.
You may ONLY select from the tickers listed below.

AGENT 1 DIRECTIVE:
{json.dumps(directive, indent=2)}

SCREENER_UNIVERSE WITH FUNDAMENTALS ({len(screener_lines)} tickers with data):
{screener_text}

RULES REMINDER:
- CONVICTION_TIER must be exactly one of: PASS, STRONG, or EXCEPTIONAL
- THEME_MATCH must be copied EXACTLY character-for-character from preferred_themes
- SOURCE must be "Screener Stage 2"
- Use the <research_scratchpad> to show your work before outputting JSON

CURRENT PORTFOLIO:
You currently hold: {held_tickers if held_tickers else '(empty — full freedom)'}
Do NOT select candidates highly correlated with existing holdings. Diversify across sectors and themes.
If portfolio is empty, you have full freedom.

Current date/time: {datetime.now().isoformat()}

First show your <research_scratchpad> analysis, then output the final JSON."""

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 2] Calling {MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")
            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                temperature=1,  # Required when using extended thinking
                thinking={
                    "type": "enabled",
                    "budget_tokens": 10000,  # Adaptive thinking budget
                },
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract text content (skip thinking blocks)
            raw_text = ""
            for block in response.content:
                if block.type == "text":
                    raw_text += block.text
            raw_text = raw_text.strip()

            # Extract JSON after the scratchpad
            if "</research_scratchpad>" in raw_text:
                after_scratchpad = raw_text.split("</research_scratchpad>", 1)[1].strip()
            else:
                after_scratchpad = raw_text

            # Strip markdown code blocks
            if after_scratchpad.startswith("```"):
                after_scratchpad = after_scratchpad.split("\n", 1)[1]
                after_scratchpad = after_scratchpad.rsplit("```", 1)[0]
                after_scratchpad = after_scratchpad.strip()

            # Find the JSON object
            brace_start = after_scratchpad.find("{")
            if brace_start >= 0:
                json_str = after_scratchpad[brace_start:]
            else:
                raise json.JSONDecodeError("No JSON object found", after_scratchpad, 0)

            result = json.loads(json_str)

            # Validate: conviction_tier must be valid enum
            for c in result.get("candidates", []):
                tier = c.get("conviction_tier")
                if tier not in ("PASS", "STRONG", "EXCEPTIONAL"):
                    score = c.get("conviction_score")
                    if isinstance(score, int):
                        if score >= 9:
                            c["conviction_tier"] = "EXCEPTIONAL"
                        elif score >= 7:
                            c["conviction_tier"] = "STRONG"
                        else:
                            c["conviction_tier"] = "PASS"
                    else:
                        raise ValueError(f"conviction_tier must be PASS/STRONG/EXCEPTIONAL, got: {tier}")
                source = c.get("source")
                if source not in ("Newsletter", "Screener Stage 2"):
                    raise ValueError(f"source must be enum, got: {source}")

            print(f"  [Agent 2] Success with {MODEL}")
            return result

        except json.JSONDecodeError as je:
            last_error = je
            print(f"  [Agent 2] {MODEL} returned invalid JSON (attempt {attempt + 1}), retrying...")
            time.sleep(RETRY_DELAY)
        except ValueError as ve:
            last_error = ve
            print(f"  [Agent 2] {MODEL} validation error: {ve}, retrying...")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "529" in error_str or "overloaded" in error_str.lower():
                print(f"  [Agent 2] {MODEL} overloaded, retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                raise

    raise Exception(f"{MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent2(directive: dict = None, screener_universe: list = None) -> dict:
    """Run Agent 2: Pre-fetch fundamentals, call Opus 4.7 with full context."""

    # Load directive
    if directive is None:
        path = "output/agent1_directive.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No Agent 1 directive found."}
        with open(path) as f:
            directive = json.load(f)

    # Load screener universe
    if screener_universe is None:
        path = "output/screener_universe.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No screener universe found. Run preflight.py first."}
        with open(path) as f:
            screener_universe = json.load(f)

    regime = directive.get("regime", "UNKNOWN")
    conviction_floor = directive.get("conviction_floor", 5)
    print(f"[Agent 2] Regime: {regime} | Conviction floor: {conviction_floor}")

    # DEFER or CRISIS = no trades
    if regime in ("DEFER", "CRISIS"):
        return {
            "success": True,
            "candidates": [],
            "screening_notes": f"Regime is {regime}. No candidates.",
            "directive_used": directive,
        }

    # Pre-fetch ALL fundamental data BEFORE calling the model
    print("[Agent 2] Pre-fetching fundamental data for entire screener universe...")
    fundamental_data = prefetch_fundamental_data(screener_universe)

    # Fetch current Alpaca positions to avoid portfolio blindness
    try:
        from broker import AlpacaBroker
        broker = AlpacaBroker()
        current_positions = broker.get_positions()
        held_tickers = [p["ticker"] for p in current_positions]
    except Exception:
        held_tickers = []

    if held_tickers:
        print(f"[Agent 2] Current portfolio: {held_tickers}")
    else:
        print(f"[Agent 2] No current positions (or broker unavailable)")

    # Call Opus 4.7 with full context
    print(f"[Agent 2] Calling {MODEL} with {len(screener_universe)} tickers + fundamentals...")
    try:
        model_result = call_opus(directive, screener_universe, fundamental_data, held_tickers=held_tickers)
    except RuntimeError as re:
        # No API key — signal that OCPlatform should run this as subagent
        return {"success": False, "needs_subagent": True, "error": str(re)}
    except Exception as e:
        return {"success": False, "error": f"Opus error: {e}"}

    candidates = model_result.get("candidates", [])

    # Filter by conviction tier
    pre_filter = len(candidates)
    tier_order = {"PASS": 1, "STRONG": 2, "EXCEPTIONAL": 3}
    candidates = [c for c in candidates if c.get("conviction_tier") in tier_order]
    if len(candidates) < pre_filter:
        print(f"  [Agent 2] Filtered {pre_filter - len(candidates)} candidates below conviction floor {conviction_floor}")

    # Validate tickers are in screener universe
    valid_tickers = {s["ticker"] for s in screener_universe}
    invalid = [c for c in candidates if c.get("ticker") not in valid_tickers]
    if invalid:
        print(f"  [Agent 2] WARNING: Removing {len(invalid)} tickers not in screener: {[c['ticker'] for c in invalid]}")
        candidates = [c for c in candidates if c.get("ticker") in valid_tickers]

    print(f"[Agent 2] {len(candidates)} candidates: {[c.get('ticker') for c in candidates]}")

    # Attach the pre-fetched fundamentals to each candidate
    for c in candidates:
        ticker = c.get("ticker")
        c["fundamentals"] = fundamental_data.get(ticker, {"error": "not found"})

    return {
        "success": True,
        "agent": "fundamental_screener",
        "timestamp": datetime.now().isoformat(),
        "regime_received": regime,
        "candidates": candidates,
        "screening_notes": model_result.get("screening_notes", ""),
        "directive_used": directive,
    }


def format_agent2_for_telegram(result: dict) -> str:
    """Format Agent 2 output for Telegram."""
    if not result.get("success"):
        return f"⚠️ Agent 2 FAILED: {result.get('error')}"

    candidates = result.get("candidates", [])
    if not candidates:
        return (
            f"{'='*30}\n"
            f"🔍 AGENT 2: FUNDAMENTAL SCREENER (v3.0 — Opus 4.7)\n"
            f"{'='*30}\n\n"
            f"📋 Regime: {result.get('regime_received')}\n"
            f"💵 No candidates met criteria.\n"
            f"📝 {result.get('screening_notes', '')}"
        )

    lines = [
        f"{'='*30}",
        f"🔍 AGENT 2: FUNDAMENTAL SCREENER (v3.0 — Opus 4.7 Adaptive)",
        f"{'='*30}",
        f"",
        f"📋 Regime: {result.get('regime_received')}",
        f"🎯 Candidates: {len(candidates)}",
        f"🔬 Model: {MODEL} | Adaptive Thinking",
        f"",
    ]

    for i, c in enumerate(candidates, 1):
        fund = c.get("fundamentals", {})
        lines.append(f"{'─'*25}")
        lines.append(f"#{i}  {c.get('ticker')} — {c.get('name')}")
        lines.append(f"    Theme: {c.get('theme_match')}")
        lines.append(f"    Conviction: {c.get('conviction_tier', 'N/A')} | Source: {c.get('source', 'N/A')}")
        lines.append(f"    💡 Thesis: {c.get('thesis')}")
        lines.append(f"    ⚡ Catalyst: {c.get('catalyst')}")

        if fund and "error" not in fund:
            mkt_cap = fund.get("market_cap")
            mkt_cap_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap and mkt_cap > 1e9 else "N/A"
            lines.append(f"    📊 Close: ${fund.get('prior_close')} | P/E: {fund.get('pe_ratio', 'N/A')} | Fwd P/E: {fund.get('forward_pe', 'N/A')}")
            lines.append(f"    📊 Cap: {mkt_cap_str} | Beta: {fund.get('beta', 'N/A')} | PEG: {fund.get('peg_ratio', 'N/A')}")
            lines.append(f"    📊 5d: {fund.get('change_5d_pct')}% | 20d: {fund.get('change_20d_pct')}%")

        lines.append(f"")

    lines.append(f"📝 {result.get('screening_notes', '')}")
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent2()
    print("\n" + format_agent2_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent2_candidates.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 2] Candidates saved to output/agent2_candidates.json")


==================================================================
FILE: agent3_synthesizer.py (     522 lines)
==================================================================
"""
Agent 3: Qualitative Synthesizer — v3.0
Model: Claude Opus 4.7 (Anthropic) with adaptive thinking
Role: Merges the former Agent 2.5 (deep research / red team) and Agent 3
      (smart money verifier) into a single qualitative synthesis pass.

Gathers ALL qualitative data in Python:
  - News headlines (yfinance)
  - Options flow / Put-Call ratio (yfinance)
  - Short interest (yfinance)
  - X/Twitter smart money mentions (from output/smart_money_mentions.json)

Then sends the complete "mosaic" to Claude for a unified verdict per ticker.

Verdicts:
  PASS_THROUGH      — Qualitative data is neutral/silent; trade proceeds as-is.
  CONFIRM_ENHANCED  — Multiple bullish qualitative signals reinforce the thesis.
  VETO_DIVERGENT    — Smart money diverges from the bullish thesis.
  VETO_CROWDED      — Too many accounts are bullish (contrarian crowding signal).
  VETO_QUALITATIVE  — Fatal qualitative flaw (e.g., 30% SI + bearish smart money).
"""
import json
import os
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Claude Opus 4.7 with adaptive thinking
MODEL = "claude-opus-4-7"
MAX_RETRIES = 3
RETRY_DELAY = 5

# Curated smart money accounts (carried from former Agent 3)
CURATED_ACCOUNTS = [
    "unusual_whales",
    "DeItaone",
    "Fxhedgers",
    "zaborsky",
    "jimcramer",
    "GurufocusData",
    "OptionsHawk",
    "PeterSchiff",
    "TruthGundlach",
    "elerianm",
    "SqueezeMetrics",
    "sentimentrader",
    "DarkPoolChart",
    "WallStJesus",
    "VolSignals",
]

SYSTEM_PROMPT = """You are Agent 3: The Qualitative Synthesizer for a $100,000 speculative spot-only trading account.

YOUR JOB: Agent 2 has passed you 1-3 surviving candidates based on a rigid quantitative screen. You receive a complete QUALITATIVE MOSAIC assembled by Python — recent news headlines, options flow (put/call ratio), short interest, AND curated smart money X/Twitter mentions (7-day lookback, institutional-grade accounts). You must weigh this entire mosaic and produce a unified verdict per ticker.

CRITICAL RULES:
1. You may NOT look up or fetch external data. Rely ONLY on the QUALITATIVE_MOSAIC injected into this prompt.
2. For each candidate, assign exactly ONE verdict:

   - PASS_THROUGH: Default. Qualitative data is neutral, silent, or mildly mixed. Trade proceeds using Agent 2's conviction tier unchanged. No numeric score.

   - CONFIRM_ENHANCED: 2+ sector specialists or hedge fund principals are publicly aligned with the thesis on X/Twitter, AND zero curated accounts are bearish, AND options flow / news reinforce the bullish setup. Effect: conviction_adjustment = UNCHANGED, Agent 4B applies a CONFIRM_BONUS in sizing.

   - VETO_DIVERGENT: 3+ curated accounts are bearish on the ticker, OR at least 1 hedge fund principal (boazweinstein, CliffordAsness, DylanLeClair_, cngarabedian, RayDalio) is bearish, OR news headlines reveal a fatal narrative break (regulatory action, terrible earnings reaction). Effect: REJECT the trade.

   - VETO_CROWDED: 8+ curated accounts are bullish on the same ticker within the last 48 hours, OR options flow shows extreme call skew (P/C ratio < 0.3) suggesting the trade is too consensus. Effect: REJECT the trade (contrarian signal).

   - VETO_QUALITATIVE: The qualitative mosaic reveals a fatal combined flaw — for example, short interest > 25% of float WITH bearish smart money AND negative news sentiment. This is the "everything is wrong" veto. Effect: REJECT the trade.

3. conviction_adjustment: For non-veto verdicts, output either UNCHANGED or DOWNGRADE. You may NEVER upgrade a conviction tier. DOWNGRADE moves EXCEPTIONAL → STRONG or STRONG → PASS.

4. SHORT SQUEEZE RULE (CRITICAL): High short interest COMBINED with bullish smart money flow is a potential short squeeze setup — do NOT veto solely on high short interest if institutional flow confirms the bullish thesis. Only apply VETO_QUALITATIVE when high short interest is COMBINED with bearish smart money AND negative news.

5. Generate a "red_flag_warnings" array for every candidate — even clean setups have risks. Identify the biggest risk factor.

6. Cite specific X/Twitter accounts and/or news headlines that drove your verdict.

7. Synthesize a "qualitative_thesis" per ticker: 2-3 sentences merging Agent 2's quantitative thesis with the qualitative mosaic realities.

<synthesis_protocol>
MANDATORY — execute before generating JSON:
Step 1: Inventory the full mosaic (news, options flow, short interest, smart money tweets).
Step 2: Cross-reference: Does smart money sentiment align with the quantitative thesis?
Step 3: Check for crowding: Are too many accounts piling in? Is options flow too one-sided?
Step 4: Check for divergence: Are bearish voices credible? Is the news narrative breaking?
Step 5: Evaluate short squeeze potential: High SI + bullish flow = squeeze setup, not veto.
Step 6: Assign verdict and conviction_adjustment.
Step 7: Write the qualitative_thesis and red_flag_warnings.
</synthesis_protocol>

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "agent": "qualitative_synthesizer",
  "timestamp": "<ISO timestamp>",
  "evaluations": [
    {
      "ticker": "<SYMBOL>",
      "verdict": "<PASS_THROUGH | CONFIRM_ENHANCED | VETO_DIVERGENT | VETO_CROWDED | VETO_QUALITATIVE>",
      "conviction_adjustment": "<UNCHANGED | DOWNGRADE>",
      "updated_conviction_tier": "<PASS | STRONG | EXCEPTIONAL>",
      "red_flag_warnings": ["<specific risk 1>", "<specific risk 2>"],
      "qualitative_thesis": "<2-3 sentences merging quant thesis with qualitative mosaic>",
      "cited_accounts": ["<accounts that drove verdict>"],
      "short_interest_pct": "<X%>",
      "put_call_ratio": <float>
    }
  ],
  "synthesis_notes": "<overall summary of qualitative synthesis>"
}"""


def prefetch_qualitative_context(candidates: list) -> dict:
    """
    Pre-fetch ALL qualitative data for candidates in Python:
      - News headlines (yfinance)
      - Options flow / Put-Call ratio (yfinance)
      - Short interest (yfinance)
    Returns a dict keyed by ticker.
    """
    context = {}
    print(f"  [Agent 3] Pre-fetching qualitative context for {len(candidates)} candidates...")

    for c in candidates:
        ticker = c["ticker"]
        try:
            stock = yf.Ticker(ticker)

            # 1. News Headlines
            news_items = stock.news
            headlines = []
            if news_items:
                for n in news_items[:5]:
                    pub_time = n.get("providerPublishTime", "")
                    title = n.get("title", "")
                    publisher = n.get("publisher", "")
                    headlines.append(f"- {pub_time}: {title} [{publisher}]")
            if not headlines:
                headlines = ["- No recent news available"]

            # 2. Options Flow (Put/Call OI Ratio for nearest expiration)
            options_context = "No options data available"
            pc_ratio = None
            puts_oi = 0
            calls_oi = 0
            try:
                expirations = stock.options
                if expirations:
                    nearest_exp = expirations[0]
                    chain = stock.option_chain(nearest_exp)
                    puts_oi = int(chain.puts["openInterest"].fillna(0).sum()) if not chain.puts.empty else 0
                    calls_oi = int(chain.calls["openInterest"].fillna(0).sum()) if not chain.calls.empty else 0
                    pc_ratio = round(puts_oi / calls_oi, 2) if calls_oi > 0 else 0
                    options_context = (
                        f"Nearest Expiration ({nearest_exp}): "
                        f"Put OI = {puts_oi}, Call OI = {calls_oi}, P/C Ratio = {pc_ratio}"
                    )
            except Exception:
                pass

            # 3. Short Interest
            info = stock.info
            short_pct_raw = info.get("shortPercentOfFloat")
            short_pct = f"{round(short_pct_raw * 100, 2)}%" if short_pct_raw else "N/A"

            context[ticker] = {
                "recent_headlines": headlines,
                "options_flow": options_context,
                "put_call_ratio": pc_ratio,
                "puts_oi": puts_oi,
                "calls_oi": calls_oi,
                "short_interest_pct_of_float": short_pct,
                "short_interest_raw": short_pct_raw,
            }
        except Exception as e:
            context[ticker] = {"error": str(e)}

    return context


def _load_x_mentions(tickers: list) -> dict:
    """
    Load X/Twitter smart money mentions from the pre-fetched file.
    Returns a dict keyed by ticker with mention lists.
    """
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            data = json.load(f)
        raw = data.get("mentions", data)  # x_fetch.py nests under "mentions"
        # Filter to our tickers
        result = {}
        for ticker in tickers:
            result[ticker] = raw.get(ticker, raw.get(ticker.lower(), []))
        return result

    # X research is mandatory — raise if missing
    raise RuntimeError(
        "No smart money X/Twitter data found at output/smart_money_mentions.json. "
        "X research is MANDATORY — run x_fetch.py first. "
        "The pipeline cannot proceed without smart money sentiment data."
    )


def call_synthesis(candidates: list, qual_context: dict, x_mentions: dict) -> dict:
    """
    Send the complete qualitative mosaic to Claude Opus 4.7 for unified synthesis.
    Uses adaptive thinking (extended thinking with budget_tokens).
    """
    import anthropic
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform.")

    client = anthropic.Anthropic(api_key=api_key)

    # Build the mosaic payload for each candidate
    mosaic_lines = []
    for c in candidates:
        ticker = c["ticker"]
        qc = qual_context.get(ticker, {})
        mentions = x_mentions.get(ticker, [])

        mention_count = len(mentions) if isinstance(mentions, list) else 0
        mention_text = json.dumps(mentions, indent=2) if mentions else "No mentions from curated accounts"

        line = (
            f"TICKER: {ticker}\n"
            f"  Quantitative Thesis: {c.get('thesis', 'N/A')}\n"
            f"  Current Conviction Tier: {c.get('conviction_tier', 'PASS')}\n"
            f"  Theme: {c.get('theme_match', 'N/A')}\n"
            f"  --- QUALITATIVE MOSAIC ---\n"
            f"  Short Interest: {qc.get('short_interest_pct_of_float', 'N/A')}\n"
            f"  Options Flow: {qc.get('options_flow', 'N/A')}\n"
            f"  Recent Headlines:\n" + "\n".join([f"    {h}" for h in qc.get("recent_headlines", [])]) + "\n"
            f"  Smart Money X/Twitter ({mention_count} mentions from curated accounts):\n"
            f"    {mention_text}\n"
        )
        mosaic_lines.append(line)

    user_message = f"""Synthesize the qualitative mosaic for these candidates from Agent 2.

ALL data has been pre-fetched by Python. Do NOT look up external data.

CANDIDATES & QUALITATIVE MOSAIC:
{"=" * 60}
{"".join(mosaic_lines)}
{"=" * 60}

CURATED SMART MONEY ACCOUNTS MONITORED:
{json.dumps(CURATED_ACCOUNTS)}

Current date/time: {datetime.now().isoformat()}

Perform your synthesis and respond with ONLY the JSON output."""

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 3] Calling {MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")

            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                temperature=1,  # Required when using extended thinking
                thinking={
                    "type": "enabled",
                    "budget_tokens": 10000,
                },
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # With extended thinking, content has thinking + text blocks
            raw_text = next(b.text for b in response.content if b.type == "text").strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                raw_text = raw_text.rsplit("```", 1)[0]
                raw_text = raw_text.strip()

            brace_start = raw_text.find("{")
            if brace_start >= 0:
                result = json.loads(raw_text[brace_start:])
                return result
            else:
                raise json.JSONDecodeError("No JSON object found", raw_text, 0)

        except RuntimeError:
            raise  # Re-raise missing API key
        except Exception as e:
            last_error = e
            print(f"  [Agent 3] Claude error: {e}. Retrying in {RETRY_DELAY}s...")
            import time
            time.sleep(RETRY_DELAY)

    raise Exception(f"{MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent3(agent2_result: dict = None, x_mentions: dict = None) -> dict:
    """
    Run Agent 3: Qualitative Synthesizer.
    Merges news, options flow, short interest, and smart money X/Twitter into
    a single qualitative pass with Claude.

    Args:
        agent2_result: Output from Agent 2 (or Agent 2 → 2.5 filtered).
        x_mentions: Pre-fetched X/Twitter mentions dict keyed by ticker.
                    If None, loads from output/smart_money_mentions.json.

    Returns:
        Dict with evaluations per ticker (verdicts, conviction adjustments, etc.).
    """
    # Load Agent 2 candidates
    if agent2_result is None:
        path = "output/agent2_candidates.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No Agent 2 candidates found."}
        with open(path) as f:
            agent2_result = json.load(f)

    candidates = agent2_result.get("candidates", [])
    if not candidates:
        return {
            "success": True,
            "evaluations": [],
            "verifications": [],
            "note": "No candidates to synthesize.",
        }

    tickers = [c.get("ticker") for c in candidates]
    print(f"[Agent 3] Qualitative synthesis for {len(tickers)} tickers: {tickers}")

    # 1. Pre-fetch qualitative context (news, options, short interest)
    qual_context = prefetch_qualitative_context(candidates)

    # 2. Load X/Twitter mentions
    if x_mentions is None:
        try:
            x_mentions = _load_x_mentions(tickers)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
    else:
        # Filter to our tickers if a raw dict was passed
        filtered = {}
        for ticker in tickers:
            filtered[ticker] = x_mentions.get(ticker, x_mentions.get(ticker.lower(), []))
        x_mentions = filtered

    for t in tickers:
        mentions = x_mentions.get(t, [])
        count = len(mentions) if isinstance(mentions, list) else 0
        qc = qual_context.get(t, {})
        si = qc.get("short_interest_pct_of_float", "N/A")
        pcr = qc.get("put_call_ratio", "N/A")
        print(f"  [Agent 3] {t}: {count} X mentions | SI: {si} | P/C: {pcr}")

    # 3. Call Claude for synthesis
    try:
        synthesis_result = call_synthesis(candidates, qual_context, x_mentions)
    except RuntimeError:
        # No API key — return data for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "prompt": SYSTEM_PROMPT,
            "candidates": candidates,
            "qual_context": qual_context,
            "x_mentions": x_mentions,
        }
    except Exception as e:
        return {"success": False, "error": f"Claude API error: {e}"}

    # 4. Process evaluations — filter vetoes, update conviction tiers
    evaluations = synthesis_result.get("evaluations", [])
    eval_lookup = {ev["ticker"]: ev for ev in evaluations}

    surviving_candidates = []
    verifications = []  # Backward-compatible with Agent 4's expected input

    for c in candidates:
        ticker = c["ticker"]
        ev = eval_lookup.get(ticker)

        if not ev:
            # No evaluation — pass through unchanged
            surviving_candidates.append(c)
            verifications.append({
                "ticker": ticker,
                "verdict": "PASS_THROUGH",
                "sentiment_read": "Not evaluated",
                "cited_accounts": [],
            })
            continue

        verdict = ev.get("verdict", "PASS_THROUGH")

        # Build backward-compatible verification record for Agent 4
        verification = {
            "ticker": ticker,
            "verdict": verdict,
            "sentiment_read": ev.get("qualitative_thesis", ""),
            "cited_accounts": ev.get("cited_accounts", []),
        }
        verifications.append(verification)

        # Handle vetoes
        if verdict in ("VETO_DIVERGENT", "VETO_CROWDED", "VETO_QUALITATIVE"):
            print(f"  [Agent 3] 🚫 {verdict}: {ticker}")
            continue

        # Apply conviction adjustment
        adjustment = ev.get("conviction_adjustment", "UNCHANGED")
        if adjustment == "DOWNGRADE":
            tier = c.get("conviction_tier", "PASS")
            downgrade_map = {"EXCEPTIONAL": "STRONG", "STRONG": "PASS", "PASS": "PASS"}
            c["conviction_tier"] = downgrade_map.get(tier, tier)
            print(f"  [Agent 3] ⬇️ DOWNGRADE: {ticker} {tier} → {c['conviction_tier']}")
        elif verdict == "CONFIRM_ENHANCED":
            c["confirm_enhanced"] = True
            print(f"  [Agent 3] ✅ CONFIRM_ENHANCED: {ticker}")

        # Merge qualitative data into candidate
        c["thesis"] = ev.get("qualitative_thesis", c.get("thesis", ""))
        c["red_flag_warnings"] = ev.get("red_flag_warnings", [])
        c["qualitative_verdict"] = verdict

        surviving_candidates.append(c)

    # Update agent2_result with filtered candidates
    updated_agent2_result = agent2_result.copy()
    updated_agent2_result["candidates"] = surviving_candidates

    return {
        "success": True,
        "evaluations": evaluations,
        "verifications": verifications,  # Agent 4 reads this
        "synthesis_notes": synthesis_result.get("synthesis_notes", ""),
        "candidates_passthrough": surviving_candidates,
        "updated_agent2_result": updated_agent2_result,
    }


def format_agent3_for_slack(result: dict) -> str:
    """Format Agent 3 output using Slack-friendly mrkdwn."""
    if not result.get("success"):
        return f"⚠️ *Agent 3 FAILED:* {result.get('error')}"

    evaluations = result.get("evaluations", [])
    surviving = result.get("candidates_passthrough", [])

    lines = [
        f"🧪 *AGENT 3: QUALITATIVE SYNTHESIZER*",
        f"> *Survived Synthesis:* {len(surviving)}/{len(evaluations)}",
        f"> *Model:* Claude Opus 4.7 (Adaptive Thinking)",
        f"",
    ]

    if not evaluations:
        lines.append("📋 No evaluations performed.")
        return "\n".join(lines)

    for i, ev in enumerate(evaluations, 1):
        verdict = ev.get("verdict", "PASS_THROUGH")
        emoji_map = {
            "PASS_THROUGH": "➡️",
            "CONFIRM_ENHANCED": "✅",
            "VETO_DIVERGENT": "🚫",
            "VETO_CROWDED": "🔴",
            "VETO_QUALITATIVE": "💀",
        }
        emoji = emoji_map.get(verdict, "❓")

        lines.append(f"*{i}. {ev.get('ticker')}* — {emoji} *{verdict}*")

        adj = ev.get("conviction_adjustment", "UNCHANGED")
        tier = ev.get("updated_conviction_tier", "N/A")
        lines.append(f"• *Tier:* {tier} ({adj})")

        si = ev.get("short_interest_pct", "N/A")
        pcr = ev.get("put_call_ratio", "N/A")
        lines.append(f"• *Short Interest:* {si} | *P/C Ratio:* {pcr}")

        flags = ev.get("red_flag_warnings", [])
        if flags:
            lines.append("• *Red Flags:*")
            for flag in flags:
                lines.append(f"  - {flag}")

        if verdict not in ("VETO_DIVERGENT", "VETO_CROWDED", "VETO_QUALITATIVE"):
            lines.append(f"• *Thesis:* {ev.get('qualitative_thesis', '')}")

        cited = ev.get("cited_accounts", [])
        if cited:
            lines.append(f"• *Cited:* {', '.join(cited)}")

        lines.append(f"")

    if result.get("synthesis_notes"):
        lines.append(f"📝 *Notes:* _{result.get('synthesis_notes')}_")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent3()
    print("\n" + format_agent3_for_slack(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent3_verified.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        # Also save the updated candidates with qualitative data merged in
        if result.get("updated_agent2_result"):
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(result["updated_agent2_result"], f, indent=2, default=str)
        print(f"\n[Agent 3] Results saved to output/agent3_verified.json")


==================================================================
FILE: agent4_risk_manager.py (     738 lines)
==================================================================
"""
Agent 4: Risk Manager — v3 (ATR-based stops, no LLM dependency)
All-Python pipeline: ATR stop calculation → position sizing → tear sheet.

Changes from v2:
- Killed Agent 4A (Claude LLM call for stop anchors)
- ATR-based stop calculation: 14-day ATR with conviction-scaled multipliers
- Correlation veto fix: min_periods=20, no double-dropna
- Formula: Target = Allocation_Cap * Conviction_Mod * Vol_Mod * Posture_Mod * Contrarian_Penalty
- Theme cap enforced: 1 position per theme, keep higher conviction if duplicates
- Uses prior close price from 7:55 AM pre-flight (not live)
- Generates Markdown tear sheet for manual execution at 9:30 AM
"""
import json
import math
import os
from datetime import datetime

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from config import (
    ACCOUNT_SIZE,
    BASE_RISK,
    MAX_RISK_PER_TRADE,
    MIN_RISK_PER_TRADE,
    MAX_ALLOCATION_PCT,
    TIER_RISK_MULT,
    CONFIRM_RISK_MULT,
    VOL_RISK_MULT,
    POSTURE_RISK_MULT,
    DRY_POWDER_FLOOR,
    POSTURE_TABLE,
    SESSION_RISK_BUDGET,
    THEME_CAP,
    MAX_PORTFOLIO_HEAT_PCT,
    HEAT_WARNING_PCT,
)
from broker import AlpacaBroker

load_dotenv()


# ATR multipliers by conviction tier — higher conviction = wider stop (more room)
ATR_MULTIPLIERS = {
    "PASS": 1.2,
    "STRONG": 1.5,
    "EXCEPTIONAL": 2.0,
}


def get_moving_averages(ticker: str) -> dict:
    """Fetch prior close + moving averages for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        if hist.empty or len(hist) < 50:
            return {"error": f"Insufficient data for {ticker}"}

        closes = [float(c) for c in hist["Close"]]
        prior_close = closes[-1]
        ma_10 = sum(closes[-10:]) / 10
        ma_20 = sum(closes[-20:]) / 20
        ma_50 = sum(closes[-50:]) / 50

        return {
            "prior_close": round(prior_close, 2),
            "ma_10": round(ma_10, 2),
            "ma_20": round(ma_20, 2),
            "ma_50": round(ma_50, 2),
            "recent_low_20d": round(min(closes[-20:]), 2),
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_atr_stop(ticker: str, entry_price: float, conviction_tier: str) -> dict:
    """
    Calculate ATR-based stop loss for a ticker.
    Downloads 20 trading days of daily OHLC, computes 14-day ATR,
    and sets stop at entry_price - (multiplier * ATR).
    Multiplier scales with conviction tier (wider stop = more room for winners).
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1mo")  # ~20 trading days
        if hist.empty or len(hist) < 14:
            return {"error": f"Insufficient data for {ticker} ({len(hist) if not hist.empty else 0} bars)"}

        # Calculate True Range for each bar
        high = hist["High"]
        low = hist["Low"]
        prev_close = hist["Close"].shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 14-day ATR (simple moving average of true range)
        atr = true_range.tail(14).mean()

        multiplier = ATR_MULTIPLIERS.get(conviction_tier, ATR_MULTIPLIERS["PASS"])
        stop_distance = multiplier * atr
        stop_price = entry_price - stop_distance
        stop_distance_pct = (stop_distance / entry_price) * 100

        return {
            "stop_price": round(stop_price, 2),
            "atr": round(atr, 4),
            "atr_multiplier": multiplier,
            "stop_distance_pct": round(stop_distance_pct, 2),
            "stop_label": f"{multiplier}x ATR({round(atr, 2)})",
        }
    except Exception as e:
        return {"error": str(e)}


def correlation_veto(new_ticker: str, current_positions: list, threshold: float = 0.70) -> bool:
    """
    Check if new_ticker is >threshold correlated with any current position.
    Uses 60-day daily returns. Returns True if correlated (should veto).
    """
    if not current_positions:
        return False

    try:
        all_tickers = [new_ticker] + current_positions
        data = yf.download(all_tickers, period="3mo", progress=False)
        if data.empty:
            return False

        closes = data["Close"] if "Close" in data.columns else data
        returns = closes.pct_change().tail(60)

        if new_ticker not in returns.columns:
            return False

        for pos in current_positions:
            if pos in returns.columns:
                corr = returns[new_ticker].corr(returns[pos], min_periods=20)
                if corr is not None and corr > threshold:
                    print(f"  [Agent 4B] CORRELATION VETO: {new_ticker} vs {pos} = {corr:.2f} (>{threshold})")
                    return True
    except Exception as e:
        print(f"  [Agent 4B] Correlation check failed (non-fatal): {e}")

    return False


def calculate_portfolio_heat() -> dict:
    """
    Calculate total open risk ("heat") across all positions.

    For each position:
      - open_risk = shares * (current_price - stop_price)
      - If stop_price unknown, estimate as entry_price - (1.5 * ATR)

    Returns:
      {
        "total_heat_dollars": float,
        "heat_pct_of_equity": float,
        "positions_detail": [...]
      }
    """
    try:
        broker = AlpacaBroker()
        positions = broker.get_positions()
        account = broker.get_account_summary()
    except Exception as e:
        print(f"[Heat] ERROR connecting to Alpaca: {e}")
        return {
            "total_heat_dollars": 0.0,
            "heat_pct_of_equity": 0.0,
            "positions_detail": [],
            "error": str(e),
        }

    equity = account.get("equity", ACCOUNT_SIZE)

    # Try to load agent4 orders for known stop prices
    stop_lookup = {}
    orders_path = os.path.join("output", "agent4_orders.json")
    if os.path.exists(orders_path):
        try:
            with open(orders_path) as f:
                orders_data = json.load(f)
            for order in orders_data.get("trade_orders", []):
                if order.get("action") == "BUY" and order.get("stop_loss"):
                    stop_lookup[order["ticker"]] = order["stop_loss"]
        except (json.JSONDecodeError, Exception):
            pass

    total_heat = 0.0
    details = []

    for pos in positions:
        ticker = pos["ticker"]
        shares = pos["shares"]
        entry_price = pos["avg_entry_price"]
        current_price = pos["current_price"]

        stop_price = stop_lookup.get(ticker)
        stop_source = "agent4_orders"

        if stop_price is None:
            # Estimate stop using ATR
            atr_result = calculate_atr_stop(ticker, entry_price, "PASS")
            if "error" not in atr_result:
                stop_price = atr_result["stop_price"]
                stop_source = "estimated_atr"
            else:
                # Fallback: 3% below entry
                stop_price = entry_price * 0.97
                stop_source = "fallback_3pct"

        # Open risk = what we'd lose if price hits stop from current level
        open_risk = shares * (current_price - stop_price)
        # If stop is above current price, risk is effectively the unrealized loss already
        if open_risk < 0:
            open_risk = abs(shares * (current_price - entry_price))

        total_heat += open_risk

        details.append({
            "ticker": ticker,
            "shares": shares,
            "entry_price": entry_price,
            "current_price": current_price,
            "stop_price": round(stop_price, 2),
            "stop_source": stop_source,
            "open_risk": round(open_risk, 2),
        })

    heat_pct = total_heat / equity if equity > 0 else 0.0

    return {
        "total_heat_dollars": round(total_heat, 2),
        "heat_pct_of_equity": round(heat_pct, 4),
        "equity": round(equity, 2),
        "positions_detail": details,
    }


def _reject_trade(ticker: str, reason: str) -> dict:
    """Build a rejection record."""
    return {"ticker": ticker, "action": "SKIP", "shares": 0, "reason": reason}


def size_position(
    entry: float,
    stop: float,
    tier: str,
    confirm_enhanced: bool,
    vol_regime: str,
    posture: str,
    account_value: float,
    session_risk_used: float,
) -> dict:
    """
    Risk-first position sizer.
    Starts from risk dollars, derives shares from stop distance,
    then floors with allocation cap. Logs the binding constraint.
    """
    if posture == "Bunker":
        return {"shares": 0, "reason": "BUNKER_POSTURE"}

    # 1. Conviction-scaled risk budget
    risk_mult = (
        TIER_RISK_MULT.get(tier, TIER_RISK_MULT["PASS"])
        * CONFIRM_RISK_MULT.get(confirm_enhanced, 1.0)
        * VOL_RISK_MULT.get(vol_regime, 1.0)
        * POSTURE_RISK_MULT.get(posture, 1.0)
    )
    risk_dollars = BASE_RISK * risk_mult
    risk_dollars = min(risk_dollars, MAX_RISK_PER_TRADE)

    if risk_dollars < MIN_RISK_PER_TRADE:
        return {"shares": 0, "reason": f"RISK_TOO_SMALL ({risk_dollars:.0f} < {MIN_RISK_PER_TRADE})"}

    # 2. Session budget check
    remaining_session_budget = SESSION_RISK_BUDGET - session_risk_used
    if risk_dollars > remaining_session_budget:
        risk_dollars = remaining_session_budget
        if risk_dollars < MIN_RISK_PER_TRADE:
            return {"shares": 0, "reason": "SESSION_BUDGET_EXHAUSTED"}

    # 3. Derive shares from risk and stop distance
    stop_distance = entry - stop
    if stop_distance <= 0:
        return {"shares": 0, "reason": "INVALID_STOP"}

    shares_by_risk = int(risk_dollars // stop_distance)

    # 4. Allocation cap (max position value as % of account)
    max_position_value = account_value * MAX_ALLOCATION_PCT
    shares_by_alloc = int(max_position_value // entry)

    shares = min(shares_by_risk, shares_by_alloc)
    if shares == 0:
        return {"shares": 0, "reason": "ZERO_SHARES_AFTER_CONSTRAINTS"}

    binding = "risk" if shares == shares_by_risk else "allocation"
    actual_risk = shares * stop_distance

    return {
        "shares": shares,
        "position_value": round(shares * entry, 2),
        "risk_budgeted": round(risk_dollars, 2),
        "risk_actual": round(actual_risk, 2),
        "risk_multiplier": round(risk_mult, 3),
        "binding_constraint": binding,
        "stop_distance_pct": round(stop_distance / entry * 100, 2),
    }


def run_agent4b(
    stop_anchors: list,
    directive: dict,
    candidates: list,
    verifications: list = None,
    existing_exposure: float = 0.0,
    remaining_heat_budget: float = None,
) -> dict:
    """
    Agent 4B (Python): Risk-first position sizing + tear sheet generation.
    
    Starts from risk dollars (BASE_RISK * multiplier stack), derives shares
    from stop distance, then floors with allocation cap and dry powder check.
    Binding constraint is logged per trade.
    
    Args:
        existing_exposure: dollar value of already-open positions carried from prior sessions.
        remaining_heat_budget: max additional risk dollars allowed before portfolio heat cap is hit.
                               None means no heat constraint (backward compat).
    """
    regime = directive.get("regime", "UNKNOWN")
    vol_regime = directive.get("vol_regime", "Normal")
    posture_info = POSTURE_TABLE.get(regime, POSTURE_TABLE.get("Cautious Risk-On"))
    posture = posture_info["posture"]

    print(f"[Agent 4B] Regime: {regime} | Vol: {vol_regime} | Posture: {posture}")
    print(f"[Agent 4B] Risk stack: BASE_RISK=${BASE_RISK} | MAX=${MAX_RISK_PER_TRADE} | MIN=${MIN_RISK_PER_TRADE}")

    trade_orders = []
    theme_tracker = {}
    accepted_tickers = []
    session_risk_used = 0.0
    total_allocated = 0.0

    # Build lookups
    anchor_lookup = {a["ticker"]: a for a in stop_anchors}
    candidate_lookup = {c["ticker"]: c for c in candidates}

    # Sort: EXCEPTIONAL first, then STRONG, then PASS
    tier_priority = {"EXCEPTIONAL": 0, "STRONG": 1, "PASS": 2}
    sorted_tickers = sorted(
        anchor_lookup.keys(),
        key=lambda t: tier_priority.get(anchor_lookup[t].get("conviction_tier", "PASS"), 2),
    )

    for ticker in sorted_tickers:
        anchor = anchor_lookup[ticker]
        candidate = candidate_lookup.get(ticker, {})

        # Check if Agent 4A rejected (veto from Agent 3)
        if anchor.get("action") == "REJECTED":
            trade_orders.append({
                "ticker": ticker,
                "action": "REJECTED",
                "reason": f"Agent 3 veto: {anchor.get('veto_reason', 'unknown')}",
            })
            continue

        entry = anchor.get("prior_close", 0)
        stop = anchor.get("stop_anchor_price", 0)
        conviction_tier = anchor.get("conviction_tier", "PASS")
        confirm_enhanced = anchor.get("confirm_bonus", False)
        theme = candidate.get("theme_match", "Unknown")

        if entry <= 0 or stop <= 0:
            trade_orders.append(_reject_trade(ticker, "Invalid price data"))
            continue

        # Theme cap check
        if theme in theme_tracker:
            existing = theme_tracker[theme]
            print(f"  [Agent 4B] {ticker}: Theme '{theme}' already taken by {existing}. Dropping.")
            trade_orders.append(_reject_trade(ticker, f"Theme cap: '{theme}' used by {existing}"))
            continue

        # Correlation veto
        if correlation_veto(ticker, accepted_tickers, threshold=0.70):
            trade_orders.append(_reject_trade(ticker, "Correlation veto: >0.70 with existing position"))
            continue

        # RISK-FIRST SIZING
        sizing = size_position(
            entry=entry,
            stop=stop,
            tier=conviction_tier,
            confirm_enhanced=confirm_enhanced,
            vol_regime=vol_regime,
            posture=posture,
            account_value=ACCOUNT_SIZE,
            session_risk_used=session_risk_used,
        )

        if sizing["shares"] == 0:
            trade_orders.append(_reject_trade(ticker, sizing.get("reason", "sizing returned 0")))
            continue

        shares = sizing["shares"]
        position_value = sizing["position_value"]
        risk_actual = sizing["risk_actual"]

        # Heat budget check: would this trade blow through the remaining heat cap?
        if remaining_heat_budget is not None:
            if risk_actual > remaining_heat_budget:
                trade_orders.append(_reject_trade(ticker, f"HEAT_BUDGET_EXCEEDED (trade risk ${risk_actual:.0f} > remaining ${remaining_heat_budget:.0f})"))
                continue

        # Dry powder floor: new + existing exposure cannot exceed 80%
        max_deployable = ACCOUNT_SIZE * (1 - DRY_POWDER_FLOOR) - total_allocated - existing_exposure
        if max_deployable <= 0:
            trade_orders.append(_reject_trade(ticker, "Dry powder floor: existing exposure at 80%"))
            continue
        if position_value > max_deployable:
            shares = int(max_deployable // entry)
            if shares <= 0:
                trade_orders.append(_reject_trade(ticker, "Dry powder floor (existing + new > 80%)"))
                continue
            position_value = round(shares * entry, 2)
            risk_actual = round(shares * (entry - stop), 2)
            sizing["binding_constraint"] = "dry_powder"

        # Build order
        stop_distance = entry - stop
        order = {
            "ticker": ticker,
            "action": "BUY",
            "shares": shares,
            "entry_price": entry,
            "stop_loss": round(stop, 2),
            "stop_anchor_label": anchor.get("stop_anchor_label", ""),
            "position_value": position_value,
            "pct_of_account": round(position_value / ACCOUNT_SIZE * 100, 2),
            "risk_budgeted": sizing["risk_budgeted"],
            "risk_actual": risk_actual,
            "risk_multiplier": sizing["risk_multiplier"],
            "stop_distance_pct": round(stop_distance / entry * 100, 2),
            "binding_constraint": sizing["binding_constraint"],
            "theme": theme,
            "conviction_tier": conviction_tier,
            "confirm_enhanced": confirm_enhanced,
        }

        trade_orders.append(order)
        theme_tracker[theme] = ticker
        accepted_tickers.append(ticker)
        session_risk_used += risk_actual
        total_allocated += position_value
        if remaining_heat_budget is not None:
            remaining_heat_budget -= risk_actual

        print(f"  [Agent 4B] {ticker}: {shares} shares @ ${entry}, "
              f"risk ${risk_actual:.2f} (budgeted ${sizing['risk_budgeted']:.2f}), "
              f"alloc {round(position_value/ACCOUNT_SIZE*100, 1)}%, "
              f"tier={conviction_tier}, bound={sizing['binding_constraint']}")

    result = {
        "success": True,
        "agent": "risk_manager",
        "timestamp": datetime.now().isoformat(),
        "trade_orders": trade_orders,
        "session_summary": {
            "total_trades": len([o for o in trade_orders if o.get("action") == "BUY"]),
            "session_risk_used": round(session_risk_used, 2),
            "session_risk_budget": SESSION_RISK_BUDGET,
            "total_allocated": round(total_allocated, 2),
            "existing_exposure": round(existing_exposure, 2),
            "pct_deployed": round((total_allocated + existing_exposure) / ACCOUNT_SIZE * 100, 2),
            "dry_powder_pct": round((1 - (total_allocated + existing_exposure) / ACCOUNT_SIZE) * 100, 2),
        },
        "modifiers_used": {
            "regime": regime,
            "vol_regime": vol_regime,
            "posture": posture,
        },
    }

    return result


def generate_tear_sheet(result: dict, directive: dict) -> str:
    """
    Generate Markdown tear sheet for manual execution at 9:30 AM.
    This is what gets sent to Telegram/Slack.
    """
    orders = result.get("trade_orders", [])
    summary = result.get("session_summary", {})
    mods = result.get("modifiers_used", {})

    lines = [
        f"{'='*35}",
        f"📋 OPEN CLAW TEAR SHEET",
        f"📅 {datetime.now().strftime('%Y-%m-%d')} | Execute at 9:30 AM ET",
        f"{'='*35}",
        f"",
        f"🌍 Regime: {mods.get('regime')} | Vol: {mods.get('vol_regime')}",
        f"📋 Posture Mod: {mods.get('posture_mod')} | Vol Mod: {mods.get('vol_mod')}",
        f"",
    ]

    buy_orders = [o for o in orders if o.get("action") == "BUY"]
    skip_orders = [o for o in orders if o.get("action") == "SKIP"]

    if not buy_orders:
        lines.append("🚫 NO TRADES TODAY")
        if skip_orders:
            lines.append("")
            for s in skip_orders:
                lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        return "\n".join(lines)

    for i, order in enumerate(buy_orders, 1):
        math_info = order.get("sizing_math", {})
        lines.append(f"{'─'*30}")
        lines.append(f"TRADE #{i}: {order.get('ticker')}")
        lines.append(f"")
        lines.append(f"  Action:     BUY")
        lines.append(f"  Shares:     {order.get('shares')}")
        lines.append(f"  Entry:      ${order.get('entry_price'):.2f} (prior close)")
        lines.append(f"  Stop:       ${order.get('stop_loss'):.2f} ({order.get('stop_anchor_label')})")
        lines.append(f"  Stop Dist:  {order.get('stop_distance_pct'):.1f}%")
        lines.append(f"  Theme:      {order.get('theme')}")
        lines.append(f"  Conviction: {order.get('final_conviction')}/10")
        lines.append(f"")
        lines.append(f"  💰 Cost:    ${order.get('total_cost'):,.2f} ({order.get('pct_of_account'):.1f}% of account)")
        lines.append(f"  🎯 Risk:    ${order.get('dollar_risk'):.2f}")
        lines.append(f"  📏 Sizing:  {order.get('sizing_note')}")
        lines.append(f"")
        lines.append(f"  Math: {math_info.get('base_alloc',0)*100:.0f}% base × "
                      f"{math_info.get('conviction_mod',0)} conv × "
                      f"{math_info.get('vol_mod',0)} vol × "
                      f"{math_info.get('posture_mod',0)} posture × "
                      f"{math_info.get('contrarian_penalty',0)} contrarian "
                      f"= {math_info.get('target_alloc_pct',0):.2f}% → "
                      f"${math_info.get('target_alloc_dollars',0):.2f}")
        lines.append(f"")

    if skip_orders:
        lines.append(f"{'─'*30}")
        lines.append(f"SKIPPED:")
        for s in skip_orders:
            lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        lines.append(f"")

    lines.append(f"{'─'*30}")
    lines.append(f"SESSION TOTALS:")
    lines.append(f"  Trades:      {summary.get('total_trades')}")
    lines.append(f"  Total Risk:  ${summary.get('total_risk', 0):.2f} / ${summary.get('session_risk_budget', 0):.2f}")
    lines.append(f"  Deployed:    {summary.get('pct_deployed', 0):.1f}%")
    lines.append(f"  Dry Powder:  {summary.get('dry_powder_pct', 0):.1f}%")
    lines.append(f"{'='*35}")

    return "\n".join(lines)


def run_agent4(agent2_result: dict = None, agent3_result: dict = None, directive: dict = None) -> dict:
    """
    Run the full Agent 4 pipeline: ATR stops (Python) → 4B sizing (Python).
    No LLM calls — pure Python.
    """
    # Load data
    if directive is None:
        with open("output/agent1_directive.json") as f:
            directive = json.load(f)

    if agent2_result is None:
        with open("output/agent2_candidates.json") as f:
            agent2_result = json.load(f)

    if agent3_result is None:
        path = "output/agent3_verified.json"
        if os.path.exists(path):
            with open(path) as f:
                agent3_result = json.load(f)

    candidates = agent2_result.get("candidates", [])
    verifications = agent3_result.get("verifications", []) if agent3_result else []

    if not candidates:
        return {
            "success": True,
            "trade_orders": [],
            "session_summary": {"total_trades": 0, "total_risk": 0},
        }

    # Build verification lookup
    verification_lookup = {v.get("ticker"): v for v in verifications}

    # Portfolio Heat Check — reject new trades if total open risk exceeds 6%
    heat = calculate_portfolio_heat()
    heat_pct = heat["heat_pct_of_equity"]
    remaining_heat_budget = None

    if heat_pct > MAX_PORTFOLIO_HEAT_PCT:
        print(f"[Agent 4] 🔥 PORTFOLIO HEAT EXCEEDED: {heat_pct*100:.1f}% > {MAX_PORTFOLIO_HEAT_PCT*100:.0f}% cap")
        print(f"[Agent 4] Total heat: ${heat['total_heat_dollars']:,.2f} on ${heat.get('equity', 0):,.2f} equity")
        return {
            "success": True,
            "trade_orders": [{"action": "SKIP", "ticker": c.get("ticker", "?"), "shares": 0,
                              "reason": f"PORTFOLIO_HEAT_EXCEEDED ({heat_pct*100:.1f}% > {MAX_PORTFOLIO_HEAT_PCT*100:.0f}%)"}
                             for c in candidates],
            "session_summary": {
                "total_trades": 0,
                "session_risk_used": 0,
                "session_risk_budget": SESSION_RISK_BUDGET,
                "portfolio_heat": heat,
            },
        }
    elif heat_pct > HEAT_WARNING_PCT:
        print(f"[Agent 4] ⚠️ Portfolio heat warning: {heat_pct*100:.1f}% (threshold: {HEAT_WARNING_PCT*100:.0f}%)")
        print(f"[Agent 4] Total heat: ${heat['total_heat_dollars']:,.2f} — trades allowed but budget constrained")

    # Compute remaining heat budget in dollars
    max_heat_dollars = heat.get("equity", ACCOUNT_SIZE) * MAX_PORTFOLIO_HEAT_PCT
    remaining_heat_budget = max_heat_dollars - heat["total_heat_dollars"]
    print(f"[Agent 4] Heat budget: ${remaining_heat_budget:,.2f} remaining of ${max_heat_dollars:,.2f}")

    # Build stop anchors from ATR calculations (replaces Agent 4A Claude call)
    stop_anchors = []
    print("[Agent 4] Calculating ATR-based stops (no LLM)...")

    for candidate in candidates:
        ticker = candidate.get("ticker")
        conviction_tier = candidate.get("conviction_tier", "PASS")

        # Apply Agent 3 verdict
        v = verification_lookup.get(ticker, {})
        verdict = v.get("verdict", "PASS_THROUGH")
        confirm_bonus = False

        if verdict in ("VETO_DIVERGENT", "VETO_CROWDED"):
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": verdict,
                "prior_close": 0,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": False,
            })
            print(f"  [Agent 4] {ticker}: REJECTED by Agent 3 ({verdict})")
            continue

        if verdict == "CONFIRM_ENHANCED":
            confirm_bonus = True

        # Get prior close from moving averages
        ma_data = get_moving_averages(ticker)
        if "error" in ma_data:
            print(f"  [Agent 4] {ticker}: Skipping — {ma_data['error']}")
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": f"Data error: {ma_data['error']}",
                "prior_close": 0,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": False,
            })
            continue

        entry_price = ma_data["prior_close"]

        # Calculate ATR-based stop
        atr_result = calculate_atr_stop(ticker, entry_price, conviction_tier)
        if "error" in atr_result:
            print(f"  [Agent 4] {ticker}: ATR failed — {atr_result['error']}")
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": f"ATR error: {atr_result['error']}",
                "prior_close": entry_price,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": confirm_bonus,
            })
            continue

        stop_anchors.append({
            "ticker": ticker,
            "action": "PROCEED",
            "veto_reason": None,
            "prior_close": entry_price,
            "stop_anchor_price": atr_result["stop_price"],
            "stop_anchor_label": atr_result["stop_label"],
            "stop_distance_pct": atr_result["stop_distance_pct"],
            "conviction_tier": conviction_tier,
            "confirm_bonus": confirm_bonus,
        })
        print(f"  [Agent 4] {ticker}: Stop ${atr_result['stop_price']} "
              f"({atr_result['stop_label']}, -{atr_result['stop_distance_pct']:.1f}%)")

    # Step 4B: Python multiplicative sizing
    print("[Agent 4B] Running position sizing math...")
    result_4b = run_agent4b(stop_anchors, directive, candidates, verifications,
                            remaining_heat_budget=remaining_heat_budget)

    # Generate tear sheet
    tear_sheet = generate_tear_sheet(result_4b, directive)
    result_4b["tear_sheet"] = tear_sheet

    return result_4b


if __name__ == "__main__":
    result = run_agent4()

    if result.get("tear_sheet"):
        print("\n" + result["tear_sheet"])
    else:
        print(json.dumps(result, indent=2))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent4_orders.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 4] Orders saved to output/agent4_orders.json")


==================================================================
FILE: agent5_position_monitor.py (     644 lines)
==================================================================
"""
Agent 5: Position Monitor — v3 (Python trailing stops + Claude thesis monitor)
Model: Claude Opus 4.7 (Anthropic) with adaptive thinking
Role: Runs at 3:30 PM ET to review open positions and decide hold/trim/close.

Architecture:
  1. Python calculates ALL mechanical trailing stops (no LLM needed for math)
  2. Claude reviews ONLY thesis drift: has the fundamental narrative broken?
  3. Merge: mechanical close if stop hit, thesis close if narrative broken, else HOLD

Timing:
  3:25 PM — Python snapshots current market prices + fetches breaking news
  3:30 PM — Python trailing stops → Claude thesis review → merge decisions
"""
import json
import os
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Claude Opus 4.7 with adaptive thinking — thesis drift ONLY
MODEL = "claude-opus-4-7"
MAX_RETRIES = 3
RETRY_DELAY = 5

SYSTEM_PROMPT = """You are Agent 5: The Thesis Monitor for a $100,000 speculative spot-only trading account.

YOUR JOB: You are the qualitative half of the position monitoring system. Python has ALREADY calculated all trailing stops and mechanical close signals. Your ONLY job is to evaluate whether the FUNDAMENTAL THESIS for each position is still intact.

YOU DO NOT:
- Calculate trailing stops (Python already did this)
- Compute P&L percentages (Python already did this)
- Decide mechanical closes (Python already did this)
- Do any math whatsoever

YOU DO:
- Read the ORIGINAL THESIS from Agent 2 for each position
- Read today's BREAKING NEWS for each ticker (pre-fetched by Python from yfinance)
- Read Agent 1's MORNING REGIME classification
- Decide: Has the fundamental narrative broken? Did the macro regime shift?
- If the thesis is broken, you OVERRIDE the mechanical trailing stop with a CLOSE

PRE-CHECK (MANDATORY):
If Agent 1's morning regime was CRISIS, OR if VIX at 3:25 PM > 35:
-> ALL theses are considered BROKEN. Output thesis_status = "BROKEN" for every position
   with override_action = "CLOSE" and reasoning = "CRISIS_LIQUIDATION".
-> Skip per-position thesis evaluation entirely.

THESIS STATUS OPTIONS (per position):
- INTACT: The original thesis still holds. News is neutral or supportive. Macro regime has not shifted against the trade. No override.
- DEGRADED: The thesis is weakened but not fatally broken. News introduces uncertainty. No override, but flag for closer monitoring tomorrow.
- BROKEN: The thesis is fatally compromised. A material event has invalidated the trade rationale (e.g., regulatory action, earnings miss, key partnership dissolved, sector-wide selloff changing the narrative). Override: CLOSE the position regardless of what the trailing stop says.

RULES:
- Be conservative with BROKEN — only use it for genuine narrative breaks, not normal volatility.
- A stock being down is NOT thesis broken. The thesis is about WHY you entered, not the price.
- If no breaking news exists for a ticker, default to INTACT.
- Cite the specific news headline or regime shift that drove your decision.

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "agent": "thesis_monitor",
  "timestamp": "<ISO timestamp>",
  "crisis_liquidation": <true | false>,
  "thesis_reviews": [
    {
      "ticker": "<SYMBOL>",
      "thesis_status": "<INTACT | DEGRADED | BROKEN>",
      "override_action": <null | "CLOSE">,
      "original_thesis_summary": "<1 sentence recap of the entry thesis>",
      "thesis_assessment": "<2-3 sentences explaining why the thesis is intact/degraded/broken>",
      "key_news_cited": ["<headline or event that influenced assessment>"]
    }
  ],
  "macro_assessment": "<1-2 sentences on whether the macro regime has shifted since morning>"
}"""


def snapshot_prices(tickers: list) -> dict:
    """
    Snapshot current market prices at 3:25 PM ET.
    Captures the intraday tape for trailing stop evaluation.
    """
    snapshot = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1m")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                day_open = float(hist["Open"].iloc[0])
                day_high = float(hist["High"].max())
                day_low = float(hist["Low"].min())
                volume = int(hist["Volume"].sum())

                snapshot[ticker] = {
                    "current_price": round(current, 2),
                    "day_open": round(day_open, 2),
                    "day_high": round(day_high, 2),
                    "day_low": round(day_low, 2),
                    "day_volume": volume,
                    "intraday_change_pct": round((current - day_open) / day_open * 100, 2),
                }
            else:
                # Fallback to daily
                hist_d = stock.history(period="1d")
                if not hist_d.empty:
                    snapshot[ticker] = {
                        "current_price": round(float(hist_d["Close"].iloc[-1]), 2),
                        "note": "Using daily close (intraday unavailable)",
                    }
                else:
                    snapshot[ticker] = {"error": "No data available"}
        except Exception as e:
            snapshot[ticker] = {"error": str(e)}

    snapshot["snapshot_time"] = datetime.now().isoformat()
    return snapshot


def fetch_breaking_news(tickers: list) -> dict:
    """
    Fetch latest news headlines from yfinance for each ticker.
    Used to feed Claude's thesis drift assessment.
    """
    news_data = {}
    print(f"  [Agent 5] Fetching breaking news for {len(tickers)} tickers...")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news
            headlines = []
            if news_items:
                for n in news_items[:5]:
                    pub_time = n.get("providerPublishTime", "")
                    title = n.get("title", "")
                    publisher = n.get("publisher", "")
                    headlines.append(f"{pub_time}: {title} [{publisher}]")
            news_data[ticker] = headlines if headlines else ["No recent news"]
        except Exception as e:
            news_data[ticker] = [f"Error fetching news: {e}"]

    return news_data


def load_open_positions() -> list:
    """
    Load open positions from Alpaca (source of truth).
    Falls back to agent4_orders.json if Alpaca is unreachable.
    Enriches with stop_loss from agent4_orders.json when available.
    """
    # Primary: Read from Alpaca
    try:
        from broker import AlpacaBroker
        broker = AlpacaBroker()
        alpaca_positions = broker.get_positions()
        if alpaca_positions:
            # Enrich with stop/theme data from agent4 orders if available
            stop_map = {}
            orders_path = "output/agent4_orders.json"
            if os.path.exists(orders_path):
                with open(orders_path) as f:
                    orders_data = json.load(f)
                for order in orders_data.get("trade_orders", []):
                    if order.get("action") == "BUY":
                        stop_map[order["ticker"]] = {
                            "stop_loss": order.get("stop_loss", 0),
                            "stop_anchor_label": order.get("stop_anchor_label", ""),
                            "theme": order.get("theme", ""),
                            "thesis": order.get("thesis", ""),
                            "dollar_risk": order.get("dollar_risk", 0),
                        }

            positions = []
            for p in alpaca_positions:
                enrichment = stop_map.get(p["ticker"], {})
                positions.append({
                    "ticker": p["ticker"],
                    "shares": p["shares"],
                    "entry_price": p["avg_entry_price"],
                    "stop_loss": enrichment.get("stop_loss", 0),
                    "stop_anchor_label": enrichment.get("stop_anchor_label", ""),
                    "theme": enrichment.get("theme", ""),
                    "thesis": enrichment.get("thesis", ""),
                    "dollar_risk": enrichment.get("dollar_risk", 0),
                    "unrealized_pl": p.get("unrealized_pl", 0),
                    "unrealized_plpc": p.get("unrealized_plpc", 0),
                    "market_value": p.get("market_value", 0),
                })
            print(f"[Agent 5] Loaded {len(positions)} positions from Alpaca")
            return positions
    except Exception as e:
        print(f"[Agent 5] Alpaca read failed, falling back to orders file: {e}")

    # Fallback: Read from agent4_orders.json
    orders_path = "output/agent4_orders.json"
    if not os.path.exists(orders_path):
        return []

    with open(orders_path) as f:
        orders_data = json.load(f)

    positions = []
    for order in orders_data.get("trade_orders", []):
        if order.get("action") == "BUY":
            positions.append({
                "ticker": order["ticker"],
                "shares": order["shares"],
                "entry_price": order["entry_price"],
                "stop_loss": order["stop_loss"],
                "stop_anchor_label": order.get("stop_anchor_label", ""),
                "theme": order.get("theme", ""),
                "thesis": order.get("thesis", ""),
                "dollar_risk": order.get("dollar_risk", 0),
            })

    print(f"[Agent 5] Loaded {len(positions)} positions from orders file (fallback)")
    return positions


def calculate_trailing_stops(positions: list, snapshot: dict) -> list:
    """
    Pure Python trailing stop calculator. No LLM needed.

    Rules:
      - Up > 2% from entry  → tighten stop to breakeven (entry price)
      - Up > 5% from entry  → trail stop to entry + 50% of gains
      - Up > 10% from entry → trail stop to entry + 75% of gains
      - Current price <= stop → MECHANICAL_CLOSE
      - Never widen a stop (new_stop >= original_stop always)

    Returns each position enriched with:
      new_stop, mechanical_action (HOLD/CLOSE), pnl_pct, pnl_dollars
    """
    results = []

    for pos in positions:
        ticker = pos["ticker"]
        entry_price = pos["entry_price"]
        original_stop = pos.get("stop_loss", 0)
        shares = pos.get("shares", 0)

        price_data = snapshot.get(ticker, {})
        current_price = price_data.get("current_price")

        if current_price is None or entry_price <= 0:
            results.append({
                **pos,
                "current_price": current_price,
                "pnl_pct": 0,
                "pnl_dollars": 0,
                "new_stop": original_stop,
                "mechanical_action": "HOLD",
                "trailing_stop_note": "No price data available",
                "intraday": price_data,
            })
            continue

        # Calculate P&L
        pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
        pnl_dollars = round((current_price - entry_price) * shares, 2)

        # Calculate trailing stop
        gain_dollars = current_price - entry_price
        new_stop = original_stop  # Start with original

        trailing_note = "Below 2% gain — original stop unchanged"

        if pnl_pct > 10:
            # Trail to entry + 75% of gains
            candidate_stop = round(entry_price + 0.75 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 75% of gains"
        elif pnl_pct > 5:
            # Trail to entry + 50% of gains
            candidate_stop = round(entry_price + 0.50 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 50% of gains"
        elif pnl_pct > 2:
            # Tighten to breakeven
            candidate_stop = entry_price
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop tightened to breakeven"

        # Never widen a stop
        new_stop = max(new_stop, original_stop)
        new_stop = round(new_stop, 2)

        # Check if stop is hit
        mechanical_action = "HOLD"
        if current_price <= new_stop:
            mechanical_action = "CLOSE"
            trailing_note = f"STOP HIT — current ${current_price} <= stop ${new_stop}"

        results.append({
            **pos,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "pnl_dollars": pnl_dollars,
            "original_stop": original_stop,
            "new_stop": new_stop,
            "mechanical_action": mechanical_action,
            "trailing_stop_note": trailing_note,
            "intraday": price_data,
        })

    return results


def call_thesis_monitor(positions_with_stops: list, breaking_news: dict, vix_data: dict) -> dict:
    """
    Call Claude to evaluate thesis drift ONLY.
    Claude does NOT calculate stops or P&L — those are pre-computed by Python.
    """
    import anthropic
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform.")

    client = anthropic.Anthropic(api_key=api_key)

    # Load Agent 1 morning regime if available
    morning_regime = "UNKNOWN"
    try:
        directive_path = "output/agent1_directive.json"
        if os.path.exists(directive_path):
            with open(directive_path) as f:
                directive = json.load(f)
            morning_regime = directive.get("regime", "UNKNOWN")
    except Exception:
        pass

    # Build position summaries for Claude (thesis focus, not math)
    position_summaries = []
    for pos in positions_with_stops:
        ticker = pos["ticker"]
        news = breaking_news.get(ticker, ["No news"])
        position_summaries.append({
            "ticker": ticker,
            "original_thesis": pos.get("thesis", "N/A"),
            "theme": pos.get("theme", "N/A"),
            "pnl_pct": pos.get("pnl_pct", 0),
            "mechanical_action": pos.get("mechanical_action", "HOLD"),
            "breaking_news": news,
        })

    user_message = f"""Review the fundamental thesis for each open position.

AGENT 1 MORNING REGIME: {morning_regime}

VIX STATUS:
{json.dumps(vix_data, indent=2)}

POSITIONS (with Python-computed trailing stops already applied):
{json.dumps(position_summaries, indent=2)}

Your job is ONLY to assess thesis drift. Python has already computed all trailing stops.
- Do NOT calculate P&L or stops.
- Focus on: Has the narrative broken? Has the macro regime shifted?
- If morning regime is CRISIS or VIX > 35, all theses are BROKEN.

Current date/time: {datetime.now().isoformat()}

Respond with ONLY the JSON output."""

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 5] Calling {MODEL} for thesis review (attempt {attempt + 1}/{MAX_RETRIES})...")

            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                temperature=1,  # Required when using extended thinking
                thinking={
                    "type": "enabled",
                    "budget_tokens": 10000,
                },
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # With extended thinking, content has thinking + text blocks
            raw_text = next(b.text for b in response.content if b.type == "text").strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                raw_text = raw_text.rsplit("```", 1)[0]
                raw_text = raw_text.strip()

            brace_start = raw_text.find("{")
            if brace_start >= 0:
                return json.loads(raw_text[brace_start:])
            else:
                raise json.JSONDecodeError("No JSON object found", raw_text, 0)

        except RuntimeError:
            raise  # Re-raise missing API key
        except Exception as e:
            last_error = e
            print(f"  [Agent 5] Claude error: {e}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    raise Exception(f"{MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent5_preflight() -> dict:
    """3:25 PM pre-flight: Snapshot current prices for open positions."""
    print("[Agent 5 Pre-Flight] Snapshotting prices at 3:25 PM...")

    positions = load_open_positions()
    if not positions:
        print("[Agent 5 Pre-Flight] No open positions to monitor.")
        return {"positions": [], "snapshot": {}}

    tickers = [p["ticker"] for p in positions]
    snapshot = snapshot_prices(tickers)

    # Also grab VIX for end-of-day risk assessment
    vix_snapshot = snapshot_prices(["^VIX"])
    snapshot["VIX"] = vix_snapshot.get("^VIX", {"error": "unavailable"})

    # Save snapshot
    os.makedirs("output", exist_ok=True)
    with open("output/agent5_snapshot.json", "w") as f:
        json.dump({"positions": positions, "snapshot": snapshot}, f, indent=2)

    print(f"[Agent 5 Pre-Flight] Snapshot saved for {len(positions)} positions")
    return {"positions": positions, "snapshot": snapshot}


def run_agent5(positions: list = None, snapshot: dict = None) -> dict:
    """
    Run Agent 5 at 3:30 PM: Python trailing stops FIRST, then Claude thesis review, then merge.

    Merge logic:
      - If Python says CLOSE (stop hit) → CLOSE
      - If Claude says CLOSE (thesis broken) → CLOSE
      - Otherwise → HOLD
    """
    # Load pre-flight data if not passed
    if positions is None or snapshot is None:
        preflight_path = "output/agent5_snapshot.json"
        if not os.path.exists(preflight_path):
            preflight = run_agent5_preflight()
            positions = preflight["positions"]
            snapshot = preflight["snapshot"]
        else:
            with open(preflight_path) as f:
                data = json.load(f)
            positions = data["positions"]
            snapshot = data["snapshot"]

    if not positions:
        return {
            "success": True,
            "decisions": [],
            "note": "No open positions to monitor.",
        }

    vix_data = snapshot.get("VIX", {})

    # ━━━ STEP 1: Python trailing stops (pure math, no LLM) ━━━
    print(f"[Agent 5] Step 1: Calculating trailing stops for {len(positions)} positions...")
    positions_with_stops = calculate_trailing_stops(positions, snapshot)

    for pos in positions_with_stops:
        action_emoji = "🔴" if pos["mechanical_action"] == "CLOSE" else "🟢"
        print(
            f"  {action_emoji} {pos['ticker']}: "
            f"P&L {pos['pnl_pct']:+.2f}% | "
            f"Stop ${pos.get('original_stop', 0)} → ${pos['new_stop']} | "
            f"{pos['mechanical_action']}"
        )

    # ━━━ STEP 2: Fetch breaking news for thesis review ━━━
    tickers = [p["ticker"] for p in positions]
    breaking_news = fetch_breaking_news(tickers)

    # ━━━ STEP 3: Claude thesis review (qualitative only) ━━━
    print(f"[Agent 5] Step 2: Claude thesis review...")

    thesis_result = None
    try:
        thesis_result = call_thesis_monitor(positions_with_stops, breaking_news, vix_data)
    except RuntimeError:
        # No API key — return data for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "positions": positions_with_stops,
            "vix": vix_data,
            "breaking_news": breaking_news,
        }
    except Exception as e:
        print(f"  [Agent 5] ⚠️ Claude thesis review failed: {e}")
        print(f"  [Agent 5] Proceeding with mechanical stops only.")

    # ━━━ STEP 4: Merge mechanical stops + thesis review ━━━
    print(f"[Agent 5] Step 3: Merging mechanical stops + thesis review...")

    # Build thesis lookup
    thesis_lookup = {}
    crisis_liquidation = False
    if thesis_result:
        crisis_liquidation = thesis_result.get("crisis_liquidation", False)
        for review in thesis_result.get("thesis_reviews", []):
            thesis_lookup[review["ticker"]] = review

    decisions = []
    for pos in positions_with_stops:
        ticker = pos["ticker"]
        mechanical = pos["mechanical_action"]
        thesis_review = thesis_lookup.get(ticker, {})
        thesis_status = thesis_review.get("thesis_status", "INTACT")
        thesis_override = thesis_review.get("override_action")

        # Merge logic
        if crisis_liquidation:
            action = "CLOSE"
            reasoning = "CRISIS_LIQUIDATION — all positions closed."
        elif mechanical == "CLOSE":
            action = "CLOSE"
            reasoning = f"MECHANICAL STOP HIT: {pos['trailing_stop_note']}"
            if thesis_status == "BROKEN":
                reasoning += f" + THESIS BROKEN: {thesis_review.get('thesis_assessment', '')}"
        elif thesis_override == "CLOSE":
            action = "CLOSE"
            reasoning = f"THESIS OVERRIDE: {thesis_review.get('thesis_assessment', 'Thesis broken per Claude review.')}"
        else:
            action = "HOLD"
            parts = [pos["trailing_stop_note"]]
            if thesis_status == "DEGRADED":
                parts.append(f"⚠️ Thesis DEGRADED: {thesis_review.get('thesis_assessment', '')}")
            elif thesis_status == "INTACT":
                parts.append("Thesis intact.")
            reasoning = " | ".join(parts)

        decisions.append({
            "ticker": ticker,
            "action": action,
            "current_price": pos.get("current_price"),
            "entry_price": pos.get("entry_price"),
            "original_stop": pos.get("original_stop", pos.get("stop_loss", 0)),
            "new_stop": pos.get("new_stop"),
            "pnl_pct": pos.get("pnl_pct", 0),
            "pnl_dollars": pos.get("pnl_dollars", 0),
            "mechanical_action": mechanical,
            "thesis_status": thesis_status,
            "thesis_override": thesis_override,
            "trim_pct": None,
            "reasoning": reasoning,
        })

        action_emoji = {"HOLD": "✅", "CLOSE": "🚪"}.get(action, "❓")
        print(f"  {action_emoji} {ticker}: {action} — {reasoning[:80]}")

    portfolio_summary = ""
    if thesis_result:
        portfolio_summary = thesis_result.get("macro_assessment", "")

    return {
        "success": True,
        "agent": "position_monitor",
        "timestamp": datetime.now().isoformat(),
        "crisis_liquidation": crisis_liquidation,
        "decisions": decisions,
        "portfolio_summary": portfolio_summary,
    }


def format_agent5_for_telegram(result: dict) -> str:
    """Format Agent 5 output for Telegram."""
    if not result.get("success"):
        return f"⚠️ Agent 5 FAILED: {result.get('error', 'Unknown')}"

    decisions = result.get("decisions", [])
    if not decisions:
        return (
            f"{'='*30}\n"
            f"🕒 AGENT 5: POSITION MONITOR (3:30 PM)\n"
            f"{'='*30}\n\n"
            f"No open positions to review."
        )

    lines = [
        f"{'='*30}",
        f"🕒 AGENT 5: POSITION MONITOR (3:30 PM)",
        f"{'='*30}",
        f"",
    ]

    if result.get("crisis_liquidation"):
        lines.append("🚨 CRISIS LIQUIDATION — ALL POSITIONS CLOSED")
        lines.append("")

    for d in decisions:
        action = d.get("action", "UNKNOWN")
        emoji = {"HOLD": "✅", "TRIM": "✂️", "CLOSE": "🚪"}.get(action, "❓")

        pnl = d.get("pnl_pct", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        thesis = d.get("thesis_status", "N/A")
        thesis_emoji = {"INTACT": "🟢", "DEGRADED": "🟡", "BROKEN": "🔴"}.get(thesis, "⚪")

        lines.append(f"{'─'*25}")
        lines.append(f"{emoji} {d.get('ticker')} — {action}")
        lines.append(f"")
        lines.append(f"  {pnl_emoji} P&L: {pnl:+.2f}% (${d.get('pnl_dollars', 0):+.2f})")
        lines.append(f"  💲 Current: ${d.get('current_price')} | Entry: ${d.get('entry_price')}")
        lines.append(f"  🛑 Stop: ${d.get('original_stop')} → ${d.get('new_stop')}")
        lines.append(f"  {thesis_emoji} Thesis: {thesis}")

        if d.get("trim_pct"):
            lines.append(f"  ✂️ Trim: {d.get('trim_pct')}%")

        lines.append(f"  💬 {d.get('reasoning', '')}")
        lines.append(f"")

    if result.get("portfolio_summary"):
        lines.append(f"📋 {result.get('portfolio_summary')}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Run pre-flight first
    preflight = run_agent5_preflight()

    # Then run agent
    result = run_agent5(preflight["positions"], preflight["snapshot"])
    print("\n" + format_agent5_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent5_decisions.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 5] Decisions saved to output/agent5_decisions.json")


==================================================================
FILE: trade_journal.py (     137 lines)
==================================================================
"""
Trade Journal — Feedback CSV for the Open Claw pipeline.
One row per closed trade. Appended on every Agent 5 close and manual exit.
All inputs to the sizer, all decision flags, and outcome stats.

The R-multiple is the key field: pnl_dollars / risk_budgeted.
Normalizes across position sizes — comparing EXCEPTIONAL to PASS by dollar
P&L is misleading because EXCEPTIONALs are sized bigger by design.
Comparing by R tells you whether the conviction signal actually predicts outcome.
"""
import csv
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")

FIELDS = [
    # Identity
    "trade_id", "ticker", "theme",
    "entry_dt", "exit_dt", "holding_days",

    # Decision flags (at entry)
    "regime", "vol_regime", "posture",
    "tier", "agent3_verdict", "confirm_enhanced",
    "x_bullish_count", "x_bearish_count", "hf_principal_signal",

    # Sizing
    "entry_price", "stop_price", "stop_distance_pct",
    "shares", "position_value",
    "risk_budgeted", "risk_actual",
    "risk_multiplier", "binding_constraint",

    # Outcome
    "exit_price", "exit_reason",
    "pnl_dollars", "pnl_pct", "r_multiple",

    # Path stats (the underrated fields)
    "max_adverse_excursion_pct",    # worst drawdown before exit
    "max_favorable_excursion_pct",  # best unrealized gain before exit
    "spx_change_over_hold_pct",     # beta context

    # Process notes
    "agent2_thesis_short",  # 1-line, for human review
    "notes",
]


def log_close(trade_record: dict):
    """Append a closed trade to the journal CSV."""
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    new_file = not JOURNAL_PATH.exists()
    with JOURNAL_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: trade_record.get(k, "") for k in FIELDS})


def build_trade_record(
    trade_order: dict,
    directive: dict,
    agent3_verification: dict,
    exit_price: float,
    exit_reason: str,
    exit_dt: datetime = None,
    mae_pct: float = None,
    mfe_pct: float = None,
    spx_change_pct: float = None,
    notes: str = "",
) -> dict:
    """
    Build a complete trade record from pipeline outputs.
    Call this when Agent 5 closes a position or on manual exit.
    """
    entry_price = trade_order.get("entry_price", 0)
    shares = trade_order.get("shares", 0)
    risk_budgeted = trade_order.get("risk_budgeted", 0)
    entry_dt_str = trade_order.get("entry_dt", directive.get("timestamp", ""))

    pnl_dollars = round((exit_price - entry_price) * shares, 2)
    pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price else 0
    r_multiple = round(pnl_dollars / risk_budgeted, 2) if risk_budgeted else 0

    # Parse dates for holding days
    exit_dt = exit_dt or datetime.now()
    holding_days = 0
    try:
        if isinstance(entry_dt_str, str) and entry_dt_str:
            entry_parsed = datetime.fromisoformat(entry_dt_str.replace("Z", "+00:00"))
            holding_days = (exit_dt - entry_parsed).days
    except Exception:
        pass

    # Generate trade ID
    trade_id = f"{trade_order.get('ticker', 'UNK')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return {
        "trade_id": trade_id,
        "ticker": trade_order.get("ticker", ""),
        "theme": trade_order.get("theme", ""),
        "entry_dt": entry_dt_str,
        "exit_dt": exit_dt.isoformat(),
        "holding_days": holding_days,

        "regime": directive.get("regime", ""),
        "vol_regime": directive.get("vol_regime", ""),
        "posture": directive.get("posture", ""),
        "tier": trade_order.get("conviction_tier", ""),
        "agent3_verdict": agent3_verification.get("verdict", ""),
        "confirm_enhanced": trade_order.get("confirm_enhanced", False),
        "x_bullish_count": agent3_verification.get("x_bullish_count", ""),
        "x_bearish_count": agent3_verification.get("x_bearish_count", ""),
        "hf_principal_signal": agent3_verification.get("hf_principal_signal", ""),

        "entry_price": entry_price,
        "stop_price": trade_order.get("stop_loss", ""),
        "stop_distance_pct": trade_order.get("stop_distance_pct", ""),
        "shares": shares,
        "position_value": trade_order.get("position_value", ""),
        "risk_budgeted": risk_budgeted,
        "risk_actual": trade_order.get("risk_actual", ""),
        "risk_multiplier": trade_order.get("risk_multiplier", ""),
        "binding_constraint": trade_order.get("binding_constraint", ""),

        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,

        "max_adverse_excursion_pct": mae_pct or "",
        "max_favorable_excursion_pct": mfe_pct or "",
        "spx_change_over_hold_pct": spx_change_pct or "",

        "agent2_thesis_short": trade_order.get("thesis", "")[:100],
        "notes": notes,
    }


==================================================================
FILE: watchlist.py (     225 lines)
==================================================================
"""
Open Claw — Watchlist Bench
Manages a persistent watchlist of Agent 2 candidates waiting for entry zones.
Candidates are promoted to READY when price pulls back to within 1% of the 20-day EMA.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
import numpy as np

WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "watchlist.json")


def _compute_ema_20(ticker: str) -> Optional[float]:
    """
    Fetch ~40 trading days of daily data and compute the 20-day EMA.
    Returns the EMA value or None on failure.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return None
        closes = hist["Close"].values
        # pandas EMA equivalent — use numpy for speed
        span = 20
        alpha = 2.0 / (span + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return round(float(ema), 4)
    except Exception:
        return None


def _get_current_price(ticker: str) -> Optional[float]:
    """Fetch the current/last price for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        # fast_info gives last price without heavy download
        price = tk.fast_info.get("lastPrice") or tk.fast_info.get("last_price")
        if price:
            return round(float(price), 4)
        # fallback: last close from history
        hist = tk.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 4)
        return None
    except Exception:
        return None


class Watchlist:
    """
    Persistent watchlist that stores Agent 2 candidates and monitors
    for pullback entries to the 20-day EMA zone.
    """

    def __init__(self, path: str = WATCHLIST_PATH):
        self.path = path
        self._entries: list[dict] = []
        self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._entries = []
        else:
            self._entries = []

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    # ── public API ───────────────────────────────────────────────

    def add(self, candidate: dict) -> dict:
        """
        Add a candidate from Agent 2 output to the watchlist.
        Computes the 20-day EMA as the target entry zone.
        Skips if ticker already on watchlist.
        """
        ticker = candidate.get("ticker", "").upper()
        if not ticker:
            return {"error": "No ticker in candidate"}

        # deduplicate
        if any(e["ticker"] == ticker for e in self._entries):
            return {"status": "already_on_watchlist", "ticker": ticker}

        ema_20 = _compute_ema_20(ticker)
        entry = {
            "ticker": ticker,
            "thesis": candidate.get("thesis", ""),
            "catalyst": candidate.get("catalyst", ""),
            "conviction_tier": candidate.get("conviction_tier", ""),
            "theme_match": candidate.get("theme_match", ""),
            "target_entry_zone": ema_20,
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "WATCHING",
            # Preserve full candidate data for downstream agents
            "_candidate": candidate,
        }
        self._entries.append(entry)
        self._save()
        return {"status": "added", "ticker": ticker, "ema_20": ema_20}

    def remove(self, ticker: str) -> bool:
        """Remove a ticker from the watchlist. Returns True if found."""
        ticker = ticker.upper()
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["ticker"] != ticker]
        removed = len(self._entries) < before
        if removed:
            self._save()
        return removed

    def get_all(self) -> list[dict]:
        """Return all watchlist entries."""
        return list(self._entries)

    def prune(self, max_age_days: int = 5) -> list[str]:
        """
        Remove entries older than *max_age_days* trading days.
        (Approximation: calendar days × 5/7 ≈ trading days, but we use
        7 calendar days as a conservative proxy for 5 trading days.)
        Returns list of pruned tickers.
        """
        calendar_cutoff = 7  # ~5 trading days
        cutoff = (datetime.now() - timedelta(days=calendar_cutoff)).strftime("%Y-%m-%d")
        pruned = [e["ticker"] for e in self._entries if e.get("added_date", "9999") < cutoff]
        if pruned:
            self._entries = [e for e in self._entries if e["ticker"] not in pruned]
            self._save()
        return pruned

    def check_entries(self) -> list[dict]:
        """
        For each watchlist ticker, fetch current price.
        If price is within 1% above the 20-day EMA → promote to READY.
        Returns list of READY entries.
        """
        ready = []
        changed = False

        for entry in self._entries:
            ticker = entry["ticker"]
            ema_20 = entry.get("target_entry_zone")

            # Refresh EMA if missing
            if ema_20 is None:
                ema_20 = _compute_ema_20(ticker)
                entry["target_entry_zone"] = ema_20
                changed = True

            if ema_20 is None:
                continue

            current = _get_current_price(ticker)
            if current is None:
                continue

            # "Within 1% above the 20 EMA" means:
            #   price <= ema_20 * 1.01  (at or just above EMA)
            #   price >= ema_20 * 0.99  (not crashed far below — optional floor)
            # A pullback to EMA support means price is near/at EMA from above.
            pct_above_ema = ((current - ema_20) / ema_20) * 100

            if pct_above_ema <= 1.0:
                entry["status"] = "READY"
                entry["current_price"] = current
                entry["pct_above_ema"] = round(pct_above_ema, 2)
                ready.append(entry)
                changed = True
            else:
                entry["current_price"] = current
                entry["pct_above_ema"] = round(pct_above_ema, 2)
                changed = True

        if changed:
            self._save()

        return ready


def promote_ready_candidates() -> list[dict]:
    """
    Check the watchlist and return READY candidates in Agent 2 output format
    so they can flow directly into Agent 3 → Agent 4.
    """
    wl = Watchlist()
    wl.prune()  # clean stale entries first
    ready_entries = wl.check_entries()

    # Convert back to Agent 2 candidate format
    candidates = []
    for entry in ready_entries:
        # Use stored original candidate if available, else reconstruct
        base = entry.get("_candidate", {})
        if not base:
            base = {
                "ticker": entry["ticker"],
                "thesis": entry.get("thesis", ""),
                "catalyst": entry.get("catalyst", ""),
                "conviction_tier": entry.get("conviction_tier", ""),
                "theme_match": entry.get("theme_match", ""),
                "type": "equity",
                "source": "Watchlist Bench",
            }
        # Tag it so downstream knows it came from watchlist
        base["source"] = "Watchlist Bench"
        base["watchlist_entry_zone"] = entry.get("target_entry_zone")
        base["watchlist_pct_above_ema"] = entry.get("pct_above_ema")
        candidates.append(base)

    return candidates


==================================================================
FILE: vwap_gate.py (     106 lines)
==================================================================
"""
Open Claw — VWAP Execution Gate
Filters BUY orders at 10:15 AM by checking if price is above the session VWAP.
Orders below VWAP are rejected — sellers are in control.
"""
import yfinance as yf
import numpy as np
from datetime import datetime
from typing import Optional


def check_vwap(ticker: str) -> Optional[dict]:
    """
    Download today's intraday 1-minute data and compute VWAP.

    VWAP = Σ(typical_price × volume) / Σ(volume)
    where typical_price = (high + low + close) / 3

    Returns dict with ticker, current_price, vwap, above_vwap, pct_vs_vwap
    or None if data is unavailable (e.g., pre-market, weekend).
    """
    try:
        tk = yf.Ticker(ticker)
        # "1d" period with "1m" interval gives today's intraday bars
        hist = tk.history(period="1d", interval="1m")

        if hist.empty:
            return None

        high = hist["High"].values
        low = hist["Low"].values
        close = hist["Close"].values
        volume = hist["Volume"].values

        # Typical price
        typical = (high + low + close) / 3.0

        cum_tp_vol = np.cumsum(typical * volume)
        cum_vol = np.cumsum(volume)

        # Avoid division by zero
        if cum_vol[-1] == 0:
            return None

        vwap = float(cum_tp_vol[-1] / cum_vol[-1])
        current_price = float(close[-1])
        pct_vs_vwap = ((current_price - vwap) / vwap) * 100.0

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 4),
            "vwap": round(vwap, 4),
            "above_vwap": current_price >= vwap,
            "pct_vs_vwap": round(pct_vs_vwap, 2),
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


def vwap_gate(trade_orders: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter BUY orders through the VWAP gate.

    - BUY orders above VWAP → approved (pass through)
    - BUY orders below VWAP → rejected with reason
    - Non-BUY orders (SELL, HOLD, etc.) → always pass through

    Returns (approved_orders, rejected_orders).
    """
    approved = []
    rejected = []

    for order in trade_orders:
        action = order.get("action", "").upper()

        # Only gate BUY orders
        if action != "BUY":
            approved.append(order)
            continue

        ticker = order.get("ticker", "")
        vwap_data = check_vwap(ticker)

        if vwap_data is None:
            # No intraday data — can't check VWAP (pre-market, weekend, etc.)
            # Let it through with a warning
            order["vwap_note"] = "No intraday data — VWAP check skipped"
            approved.append(order)
            continue

        if vwap_data.get("error"):
            order["vwap_note"] = f"VWAP error: {vwap_data['error']}"
            approved.append(order)
            continue

        if vwap_data["above_vwap"]:
            order["vwap"] = vwap_data["vwap"]
            order["vwap_pct"] = vwap_data["pct_vs_vwap"]
            approved.append(order)
        else:
            order["vwap"] = vwap_data["vwap"]
            order["vwap_pct"] = vwap_data["pct_vs_vwap"]
            order["reject_reason"] = "Below VWAP — sellers in control"
            rejected.append(order)

    return approved, rejected


==================================================================
FILE: x_fetch.py (     313 lines)
==================================================================
"""
X/Twitter Smart Money Fetch — Official X Developer API
Uses the search/recent endpoint with X_BEARER_TOKEN (pay-per-use tier).

Queries surviving tickers against CURATED_ACCOUNTS list over a 7-day window.
Saves clean JSON to output/smart_money_mentions.json for Agent 3.

Usage:
  python3 x_fetch.py MSFT JPM           # Fetch mentions for specific tickers
  python3 x_fetch.py --from-agent2      # Read tickers from Agent 2 output
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# X API v2 search/recent endpoint
X_API_URL = "https://api.twitter.com/2/tweets/search/recent"

# Curated smart money accounts — INSTITUTIONAL MACRO/QUANT/FUNDAMENTAL ONLY
# Retail, options flow, and finfluencer handles PURGED per Jamie's directive (May 19)
# REMOVED: unusual_whales, WallStJesus, OptionsHawk, jimcramer, DumbMoneyTV
CURATED_ACCOUNTS = [
    # --- MACRO FLOW/SENTIMENT (institutional grade) ---
    "DeItaone",            # Institutional news wire
    "Fxhedgers",           # Macro/FX institutional feed
    "zaborsky",            # Macro strategist
    "GurufocusData",       # Fundamental data aggregator
    "PeterSchiff",         # Macro economist, hard assets
    "TruthGundlach",       # Jeffrey Gundlach, DoubleLine Capital
    "elerianm",            # Mohamed El-Erian, Allianz/PIMCO
    "SqueezeMetrics",      # DIX/GEX quant model
    "sentimentrader",      # Institutional sentiment data
    "DarkPoolChart",       # Dark pool flow analytics
    "VolSignals",          # Volatility structure analysis
    # --- MACRO_ANALYSTS (central bank, liquidity, regime) ---
    "MacroAlf",            # Alfonso Peccatiello, ex-ING $20B portfolio
    "FedGuy12",            # Joseph Wang, ex-NY Fed open market desk
    "biancoresearch",      # Jim Bianco, Bianco Research
    "TheMichaelEvery",     # Michael Every, Rabobank Global Strategist
    # --- SECTOR_SPECIALISTS ---
    "Josh_Young_1",        # Energy/oil specialist
    "brandon_munro",       # Uranium/nuclear sector
    "UraniumInsider",      # Uranium sector intelligence
    "PeterKolchinsky",     # Biotech/healthcare specialist
    "dylanpatel",          # Semiconductor/AI sector (SemiAnalysis)
    # --- QUANT_SYSTEMATIC (gamma, vol structure, quant models) ---
    "spotgamma",           # Options gamma exposure modeling
    "choffstein",          # Corey Hoffstein, Newfound Research
    "nope_its_lily",       # Lily Francus, options/vol quant
    # --- HEDGE_FUND_PRINCIPALS ---
    "boazweinstein",       # Boaz Weinstein, Saba Capital
    "CliffordAsness",      # Cliff Asness, AQR Capital
    "DylanLeClair_",       # Dylan LeClair, BTC/macro analyst
    "cngarabedian",        # Institutional fund manager
    "RayDalio",            # Ray Dalio, Bridgewater founder
    # --- CONTRARIAN_VOICES ---
    "WallStCynic",         # Contrarian macro voice
    "rampagingruss",       # Contrarian analyst
    "orrdavid",            # David Orr, contrarian macro
    # REMOVED per Jamie directive (May 19): benjamincowen, 0xReflection,
    # InTheAssembly, NoLimitGains, realDonaldTrump, TheGoldPrairie, great_martis
]

# Chunking config: X API Basic tier has 512-char query limit
# ~11 accounts per chunk keeps queries under limit for 31 accounts (3 chunks)
ACCOUNTS_PER_CHUNK = 11

# Rate limit: 450 requests per 15-min window on Basic tier
# We pace our requests to stay well under
REQUEST_DELAY = 2  # seconds between requests


def get_bearer_token() -> str:
    """Get X_BEARER_TOKEN from environment."""
    token = os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        raise RuntimeError(
            "X_BEARER_TOKEN not set. Add it to .env or set as environment variable."
        )
    return token


def build_query(ticker: str, accounts: list) -> str:
    """
    Build a Twitter API v2 search query for a ticker filtered by a chunk of accounts.
    Query must stay under 512 chars for Basic tier.
    
    Example: ($MSFT OR MSFT) (from:DeItaone OR from:MacroAlf OR ...)
    """
    ticker_terms = f"(${ticker} OR {ticker})"
    account_filters = " OR ".join([f"from:{acct}" for acct in accounts])
    query = f"{ticker_terms} ({account_filters})"
    
    if len(query) > 512:
        print(f"  [X Fetch] WARNING: Query chunk for {ticker} is {len(query)} chars (over 512 limit)")
    
    return query


def chunk_accounts(accounts: list, chunk_size: int = None) -> list:
    """
    Split the curated accounts into chunks that produce queries under 512 chars.
    Returns list of account-list chunks.
    """
    size = chunk_size or ACCOUNTS_PER_CHUNK
    return [accounts[i:i + size] for i in range(0, len(accounts), size)]


def search_recent_tweets(
    query: str,
    bearer_token: str,
    max_results: int = 100,
    start_time: str = None,
) -> list:
    """
    Call X API v2 search/recent endpoint.
    Returns list of tweet objects.
    """
    headers = {
        "Authorization": f"Bearer {bearer_token}",
    }
    
    params = {
        "query": query,
        "max_results": min(max_results, 100),  # API max is 100 per page
        "tweet.fields": "created_at,author_id,public_metrics,text",
        "user.fields": "username,name",
        "expansions": "author_id",
    }
    
    if start_time:
        params["start_time"] = start_time
    
    all_tweets = []
    next_token = None
    pages = 0
    max_pages = 5  # Cap pagination to avoid runaway costs
    
    while pages < max_pages:
        if next_token:
            params["next_token"] = next_token
        
        response = requests.get(X_API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            # Rate limited — wait and retry
            retry_after = int(response.headers.get("x-rate-limit-reset", 60)) - int(time.time())
            retry_after = max(retry_after, 15)
            print(f"  [X Fetch] Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        if response.status_code != 200:
            print(f"  [X Fetch] API error {response.status_code}: {response.text[:200]}")
            break
        
        data = response.json()
        
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        
        # Enrich tweets with username
        for tweet in tweets:
            author_id = tweet.get("author_id")
            if author_id in users:
                tweet["username"] = users[author_id].get("username", "unknown")
                tweet["author_name"] = users[author_id].get("name", "unknown")
        
        all_tweets.extend(tweets)
        
        # Check for pagination
        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
        
        pages += 1
        time.sleep(REQUEST_DELAY)
    
    return all_tweets


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money X mentions for a list of tickers.
    7-day lookback window using search/recent endpoint.
    
    Returns: {
        "MSFT": [{"text": "...", "username": "...", "created_at": "...", ...}, ...],
        "JPM": [...],
        ...
    }
    """
    bearer_token = get_bearer_token()
    
    # 7-day lookback window (search/recent max is ~7 days anyway)
    start_time = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    mentions = {}
    
    # Chunk accounts to keep queries under 512-char API limit
    account_chunks = chunk_accounts(CURATED_ACCOUNTS)
    print(f"[X Fetch] Split {len(CURATED_ACCOUNTS)} accounts into {len(account_chunks)} chunks of ~{ACCOUNTS_PER_CHUNK}")
    
    for ticker in tickers:
        print(f"[X Fetch] Searching for {ticker} mentions from curated accounts...")
        
        all_tweets_for_ticker = []
        
        for chunk_idx, chunk in enumerate(account_chunks):
            query = build_query(ticker, chunk)
            
            try:
                tweets = search_recent_tweets(
                    query=query,
                    bearer_token=bearer_token,
                    max_results=100,
                    start_time=start_time,
                )
                all_tweets_for_ticker.extend(tweets)
            except Exception as e:
                print(f"  [X Fetch] {ticker} chunk {chunk_idx + 1}: Error -- {e}")
            
            # Pace between chunks
            time.sleep(REQUEST_DELAY)
        
        # Deduplicate by tweet ID
        seen_ids = set()
        clean_tweets = []
        for t in all_tweets_for_ticker:
            tid = t.get("id", "")
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            clean_tweets.append({
                "text": t.get("text", ""),
                "username": t.get("username", "unknown"),
                "author_name": t.get("author_name", "unknown"),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
            })
        
        mentions[ticker] = clean_tweets
        print(f"  [X Fetch] {ticker}: {len(clean_tweets)} mentions found ({len(account_chunks)} chunks queried)")
    
    return mentions


def run_x_fetch(tickers: list = None) -> dict:
    """
    Main entry point. Fetches X mentions and saves to output file.
    """
    # Load tickers from Agent 2 if not provided
    if not tickers:
        agent2_path = "output/agent2_candidates.json"
        if os.path.exists(agent2_path):
            with open(agent2_path) as f:
                agent2 = json.load(f)
            tickers = [c.get("ticker") for c in agent2.get("candidates", [])]
        
        if not tickers:
            raise RuntimeError("No tickers provided and no Agent 2 candidates found.")
    
    print(f"[X Fetch] Fetching smart money mentions for: {tickers}")
    print(f"[X Fetch] Curated accounts: {len(CURATED_ACCOUNTS)}")
    print(f"[X Fetch] Lookback: 7 days")
    
    mentions = fetch_smart_money_mentions(tickers)
    
    # Save output
    output = {
        "timestamp": datetime.now().isoformat(),
        "lookback_days": 7,
        "curated_accounts": CURATED_ACCOUNTS,
        "tickers_queried": tickers,
        "mentions": mentions,
        "total_mentions": sum(len(m) for m in mentions.values()),
    }
    
    os.makedirs("output", exist_ok=True)
    output_path = "output/smart_money_mentions.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n[X Fetch] Complete. {output['total_mentions']} total mentions saved to {output_path}")
    
    # Summary
    for ticker, tweets in mentions.items():
        if tweets:
            accounts_seen = set(t["username"] for t in tweets)
            print(f"  {ticker}: {len(tweets)} mentions from {len(accounts_seen)} accounts ({', '.join(accounts_seen)})")
        else:
            print(f"  {ticker}: No mentions from curated accounts")
    
    return output


if __name__ == "__main__":
    if "--from-agent2" in sys.argv:
        run_x_fetch()
    elif len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:] if not t.startswith("-")]
        run_x_fetch(tickers)
    else:
        print("Usage:")
        print("  python3 x_fetch.py MSFT JPM        # Specific tickers")
        print("  python3 x_fetch.py --from-agent2    # Read from Agent 2 output")


==================================================================
FILE: assembly_scraper.py (     217 lines)
==================================================================
"""
Assembly Private Scraper — Browser-based extraction.

Assembly is a Next.js SPA that renders data client-side.
This scraper uses the browser DOM snapshots (from OCPlatform BrowserControl)
or falls back to a pre-saved JSON file.

For automated pipeline runs, the orchestrator calls scrape via browser,
saves to output/assembly_data.json, and agents read from that file.

Usage:
  python assembly_scraper.py parse-snapshot <snapshot_file>
  python assembly_scraper.py load  (reads from output/assembly_data.json)
"""

import json
import re
import os
from datetime import datetime


def parse_sentiment_from_text(text: str) -> dict:
    """Parse sentiment data from page text content."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_sentiment"}

    # Composite score
    composite_match = re.search(r"(\d+)\s+(Greed|Fear|Neutral|Extreme\s*Greed|Extreme\s*Fear|Ex\.\s*Greed|Ex\.\s*Fear)", text)
    if composite_match:
        result["composite_score"] = int(composite_match.group(1))
        result["composite_label"] = composite_match.group(2)

    # Historical values
    for label, key in [
        ("Prev Close", "prev_close"),
        ("Previous Close", "prev_close"),
        ("1 Week Ago", "one_week_ago"),
        ("1W Ago", "one_week_ago"),
        ("1 Month Ago", "one_month_ago"),
        ("1M Ago", "one_month_ago"),
        ("1 Year Ago", "one_year_ago"),
        ("1Y Ago", "one_year_ago"),
        ("30-Day Avg", "thirty_day_avg"),
        ("52-Week High", "fifty_two_week_high"),
        ("52-Week Low", "fifty_two_week_low"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+(\d+)", text)
        if match and key not in result:
            result[key] = int(match.group(1))

    # Sub-components
    components = {}
    patterns = [
        (r"Market Volatility\s*\(VIX\)\s*(\d+)", "market_volatility_vix"),
        (r"S&P 125-day Momentum\s*(\d+)", "sp500_momentum_125d"),
        (r"S&P 500 Momentum\s*(\d+)", "sp500_momentum"),
        (r"Stock Price Strength\s*(\d+)", "stock_price_strength"),
        (r"Stock Price Breadth\s*(\d+)", "stock_price_breadth"),
        (r"Put\s*/\s*Call Options\s*(\d+)", "put_call_options"),
        (r"Junk Bond Demand\s*(\d+)", "junk_bond_demand"),
        (r"Safe Haven Demand\s*(\d+)", "safe_haven_demand"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, text)
        if match:
            components[key] = int(match.group(1))

    # VIX actual value
    vix_match = re.search(r"VIX\)\s*\d+\s+(\d+\.?\d*)", text)
    if vix_match:
        components["vix_value"] = float(vix_match.group(1))

    result["components"] = components

    # Sector breadth
    sectors = {}
    sector_pattern = re.findall(
        r"(Energy|Healthcare|Utilities|Real Estate|Consumer Defensive|Technology|"
        r"Communication Services|Consumer Cyclical|Industrials|Financial Services|"
        r"Basic Materials)\s+([+\-]?\d+\.?\d*%)",
        text
    )
    for sector, change in sector_pattern:
        sectors[sector] = change
    result["sector_breadth"] = sectors

    return result


def parse_macro_from_snapshot(snapshot_text: str) -> dict:
    """Parse macro data from a browser snapshot."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_macro"}

    # Yield curve
    yield_curve = {}
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]:
        match = re.search(rf"\b{tenor}\s+(\d+\.?\d*)", snapshot_text)
        if match:
            yield_curve[tenor] = float(match.group(1))
    result["yield_curve"] = yield_curve

    # Key macro
    for label, key in [
        ("Fed Funds", "fed_funds"),
        ("Unemployment", "unemployment"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+([\d.]+%?)", snapshot_text)
        if match:
            result[key] = match.group(1)

    # Cross-asset rotation — parse from structured snapshot
    cross_asset = []
    # Pattern: "SPY US Large Cap Equity $733.73 -0.67% +6.1% +8.4% 91%"
    asset_pattern = re.findall(
        r'([A-Z]{2,5})\s+([\w\s]+?)\s+(Equity|Bond|Commodity|FX|Crypto)\s+\$([\d,.]+)\s+'
        r'([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+(\d+%)',
        snapshot_text
    )
    for ticker, name, asset_class, price, today, vs50, vs200, range52 in asset_pattern:
        cross_asset.append({
            "ticker": ticker.strip(),
            "name": name.strip(),
            "asset_class": asset_class,
            "price": f"${price}",
            "today": today,
            "vs_50d": vs50,
            "vs_200d": vs200,
            "range_52w": range52,
        })
    result["cross_asset_rotation"] = cross_asset

    return result


def format_sentiment_for_prompt(sentiment: dict) -> str:
    """Format sentiment data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY SENTIMENT DATA",
        "=" * 40,
        f"Composite Score: {sentiment.get('composite_score', '?')} ({sentiment.get('composite_label', '?')})",
        f"Prev Close: {sentiment.get('prev_close', '?')} | 1W Ago: {sentiment.get('one_week_ago', '?')} | 1M Ago: {sentiment.get('one_month_ago', '?')}",
        f"30D Avg: {sentiment.get('thirty_day_avg', '?')} | 52W High: {sentiment.get('fifty_two_week_high', '?')} | 52W Low: {sentiment.get('fifty_two_week_low', '?')}",
        "",
        "Sub-Components:",
    ]
    components = sentiment.get("components", {})
    for key, label in [
        ("market_volatility_vix", "Market Volatility (VIX)"),
        ("vix_value", "VIX Actual"),
        ("sp500_momentum_125d", "S&P 125d Momentum"),
        ("sp500_momentum", "S&P 500 Momentum"),
        ("stock_price_strength", "Stock Price Strength"),
        ("stock_price_breadth", "Stock Price Breadth"),
        ("put_call_options", "Put/Call Options"),
        ("junk_bond_demand", "Junk Bond Demand"),
        ("safe_haven_demand", "Safe Haven Demand"),
    ]:
        val = components.get(key)
        if val is not None:
            lines.append(f"  {label}: {val}")

    sectors = sentiment.get("sector_breadth", {})
    if sectors:
        lines.append("")
        lines.append("Sector Breadth:")
        for sector, change in sectors.items():
            lines.append(f"  {sector}: {change}")

    return "\n".join(lines)


def format_macro_for_prompt(macro: dict) -> str:
    """Format macro data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY MACRO DATA",
        "=" * 40,
    ]

    yc = macro.get("yield_curve", {})
    if yc:
        curve_str = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"Yield Curve: {curve_str}")

    for key, label in [("fed_funds", "Fed Funds"), ("unemployment", "Unemployment")]:
        if key in macro:
            lines.append(f"{label}: {macro[key]}")

    cross_asset = macro.get("cross_asset_rotation", [])
    if cross_asset:
        lines.append("")
        lines.append("Cross-Asset Rotation:")
        for a in cross_asset:
            lines.append(f"  {a['ticker']} ({a['name']}): {a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    return "\n".join(lines)


def load_assembly_data() -> dict:
    """Load pre-scraped Assembly data from output file."""
    path = "output/assembly_data.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        data = load_assembly_data()
        if "sentiment" in data:
            print(format_sentiment_for_prompt(data["sentiment"]))
            print()
        if "macro" in data:
            print(format_macro_for_prompt(data["macro"]))
    else:
        print("Usage: python assembly_scraper.py load")
        print("  (Assembly data must be scraped via browser and saved to output/assembly_data.json)")


==================================================================
FILE: flash_crash_daemon.py (     339 lines)
==================================================================
"""
Flash-Crash Daemon — Lightweight intraday safety net (NO LLM)
Runs every 5-10 minutes during market hours.

Checks:
  1. SPY intraday drop > 1.5% from today's open → defensive protocol
  2. VIX intraday spike > 20% from today's open → defensive protocol
  3. Individual position down > 5% intraday → tighten that stop to breakeven

Defensive protocol:
  - Profitable positions → tighten stop to breakeven (entry price)
  - Losing positions → close immediately
  - Log all actions to output/daemon_log.json
  - Save alert to output/daemon_alert.json for Agent 5 visibility

Usage:
  python3 flash_crash_daemon.py
"""
import json
import os
import sys
from datetime import datetime, time

import pytz
import yfinance as yf

from broker import AlpacaBroker

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Thresholds
SPY_DROP_THRESHOLD = -0.015       # -1.5% from today's open
VIX_SPIKE_THRESHOLD = 0.20        # +20% from today's open
POSITION_DROP_THRESHOLD = -0.05   # -5% intraday for individual positions


def is_market_hours() -> bool:
    """Check if current time is within regular market hours (9:30-16:00 ET, Mon-Fri)."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)

    # Skip weekends (Monday=0, Sunday=6)
    if now.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)

    return market_open <= now.time() <= market_close


def get_intraday_change(ticker: str) -> dict:
    """
    Fetch intraday data for a ticker and compute change from today's open.
    Returns {"open": float, "current": float, "change_pct": float} or {"error": str}.
    """
    try:
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if data.empty:
            return {"error": f"No intraday data for {ticker}"}

        # Handle multi-level columns from yfinance
        if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
            open_price = float(data["Open"][ticker].iloc[0])
            current_price = float(data["Close"][ticker].iloc[-1])
        else:
            open_price = float(data["Open"].iloc[0])
            current_price = float(data["Close"].iloc[-1])

        if open_price <= 0:
            return {"error": f"Invalid open price for {ticker}"}

        change_pct = (current_price - open_price) / open_price

        return {
            "open": round(open_price, 2),
            "current": round(current_price, 2),
            "change_pct": round(change_pct, 4),
        }
    except Exception as e:
        return {"error": str(e)}


def _save_json(filepath: str, data: dict):
    """Write JSON to file, creating output dir if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _append_daemon_log(entry: dict):
    """Append an entry to the daemon log (keeps history)."""
    log_path = os.path.join(OUTPUT_DIR, "daemon_log.json")
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = [logs]
        except (json.JSONDecodeError, Exception):
            logs = []
    logs.append(entry)
    # Keep last 500 entries to avoid unbounded growth
    logs = logs[-500:]
    _save_json(log_path, logs)


def execute_defensive_protocol(broker: AlpacaBroker, trigger_reason: str, positions: list) -> list:
    """
    Execute defensive protocol on all positions:
    - Profitable positions: tighten stop to breakeven (entry price)
    - Losing positions: close immediately
    Returns list of actions taken.
    """
    actions = []

    for pos in positions:
        ticker = pos["ticker"]
        entry_price = pos["avg_entry_price"]
        unrealized_pl = pos["unrealized_pl"]

        if unrealized_pl >= 0:
            # Profitable — tighten stop to breakeven
            # We can't directly modify an existing stop order via the broker module,
            # so we cancel existing orders and resubmit with breakeven stop.
            # For now, log the intent — the broker module doesn't expose stop modification.
            action = {
                "ticker": ticker,
                "action": "TIGHTEN_STOP_BREAKEVEN",
                "entry_price": entry_price,
                "unrealized_pl": unrealized_pl,
                "note": f"Stop tightened to breakeven (${entry_price:.2f})",
            }
            # Attempt to cancel existing orders and place a new stop at breakeven
            try:
                from alpaca.trading.requests import StopOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                # Cancel existing orders for this ticker
                orders = broker.client.get_orders()
                for o in orders:
                    if o.symbol == ticker:
                        try:
                            broker.client.cancel_order_by_id(o.id)
                        except Exception:
                            pass
                # Place new stop at breakeven
                from alpaca.trading.requests import StopOrderRequest
                stop_req = StopOrderRequest(
                    symbol=ticker,
                    qty=pos["shares"],
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    stop_price=round(entry_price, 2),
                )
                broker.client.submit_order(stop_req)
                action["status"] = "executed"
            except Exception as e:
                action["status"] = "logged_only"
                action["error"] = str(e)

            actions.append(action)
            print(f"  [Daemon] {ticker}: Profitable (+${unrealized_pl:.2f}) → stop tightened to ${entry_price:.2f}")
        else:
            # Losing — close immediately
            result = broker.close_position(ticker)
            action = {
                "ticker": ticker,
                "action": "CLOSE_LOSING",
                "entry_price": entry_price,
                "unrealized_pl": unrealized_pl,
                "close_result": result,
            }
            actions.append(action)
            print(f"  [Daemon] {ticker}: Losing (${unrealized_pl:.2f}) → CLOSED")

    return actions


def tighten_individual_stop(broker: AlpacaBroker, pos: dict) -> dict:
    """Tighten a single position's stop to breakeven when it's down >5% intraday."""
    ticker = pos["ticker"]
    entry_price = pos["avg_entry_price"]

    action = {
        "ticker": ticker,
        "action": "INDIVIDUAL_STOP_TIGHTEN",
        "entry_price": entry_price,
        "note": f"Position down >5% intraday — stop moved to breakeven (${entry_price:.2f})",
    }

    try:
        # Cancel existing orders for this ticker
        orders = broker.client.get_orders()
        for o in orders:
            if o.symbol == ticker:
                try:
                    broker.client.cancel_order_by_id(o.id)
                except Exception:
                    pass

        from alpaca.trading.requests import StopOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        stop_req = StopOrderRequest(
            symbol=ticker,
            qty=pos["shares"],
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            stop_price=round(entry_price, 2),
        )
        broker.client.submit_order(stop_req)
        action["status"] = "executed"
    except Exception as e:
        action["status"] = "logged_only"
        action["error"] = str(e)

    print(f"  [Daemon] {ticker}: Down >5% intraday → stop tightened to ${entry_price:.2f}")
    return action


def run_daemon():
    """
    Main daemon entry point. Checks market conditions and positions.
    If no triggers, exits silently. If triggers fire, executes defensive protocol.
    """
    # Check market hours
    if not is_market_hours():
        return  # Silent exit outside market hours

    triggers = []
    actions = []

    # --- Check SPY ---
    spy_data = get_intraday_change("SPY")
    if "error" not in spy_data:
        if spy_data["change_pct"] <= SPY_DROP_THRESHOLD:
            trigger = {
                "type": "SPY_DROP",
                "detail": f"SPY down {spy_data['change_pct']*100:.2f}% (threshold: {SPY_DROP_THRESHOLD*100:.1f}%)",
                "open": spy_data["open"],
                "current": spy_data["current"],
                "change_pct": spy_data["change_pct"],
            }
            triggers.append(trigger)
            print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
    else:
        print(f"[Daemon] Warning: Could not fetch SPY data — {spy_data['error']}")

    # --- Check VIX ---
    vix_data = get_intraday_change("^VIX")
    if "error" not in vix_data:
        if vix_data["change_pct"] >= VIX_SPIKE_THRESHOLD:
            trigger = {
                "type": "VIX_SPIKE",
                "detail": f"VIX up {vix_data['change_pct']*100:.2f}% (threshold: +{VIX_SPIKE_THRESHOLD*100:.0f}%)",
                "open": vix_data["open"],
                "current": vix_data["current"],
                "change_pct": vix_data["change_pct"],
            }
            triggers.append(trigger)
            print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
    else:
        print(f"[Daemon] Warning: Could not fetch VIX data — {vix_data['error']}")

    # --- Load positions ---
    try:
        broker = AlpacaBroker()
        positions = broker.get_positions()
    except Exception as e:
        print(f"[Daemon] ERROR: Could not connect to Alpaca — {e}")
        return

    if not positions:
        if triggers:
            # Triggers fired but no positions to defend — just log
            alert = {
                "timestamp": datetime.now().isoformat(),
                "triggers": triggers,
                "actions": [],
                "note": "Triggers fired but no open positions",
            }
            _save_json(os.path.join(OUTPUT_DIR, "daemon_alert.json"), alert)
            _append_daemon_log(alert)
            print("[Daemon] Triggers fired but no positions to defend. Alert saved.")
        return  # Silent exit if no positions and no triggers

    # --- Check individual positions for >5% intraday drop ---
    for pos in positions:
        ticker = pos["ticker"]
        pos_data = get_intraday_change(ticker)
        if "error" not in pos_data:
            if pos_data["change_pct"] <= POSITION_DROP_THRESHOLD:
                trigger = {
                    "type": "POSITION_DROP",
                    "ticker": ticker,
                    "detail": f"{ticker} down {pos_data['change_pct']*100:.2f}% intraday (threshold: {POSITION_DROP_THRESHOLD*100:.0f}%)",
                    "change_pct": pos_data["change_pct"],
                }
                triggers.append(trigger)
                print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
                # Tighten this specific position's stop to breakeven
                action = tighten_individual_stop(broker, pos)
                actions.append(action)

    # --- If market-wide triggers fired, run full defensive protocol ---
    market_wide_triggers = [t for t in triggers if t["type"] in ("SPY_DROP", "VIX_SPIKE")]
    if market_wide_triggers:
        trigger_reasons = "; ".join(t["detail"] for t in market_wide_triggers)
        print(f"\n[Daemon] 🛡️ DEFENSIVE PROTOCOL ACTIVATED: {trigger_reasons}")
        defensive_actions = execute_defensive_protocol(broker, trigger_reasons, positions)
        actions.extend(defensive_actions)

    # --- If any triggers fired, save outputs ---
    if triggers:
        timestamp = datetime.now().isoformat()

        alert = {
            "timestamp": timestamp,
            "triggers": triggers,
            "actions": actions,
            "positions_at_trigger": positions,
        }
        _save_json(os.path.join(OUTPUT_DIR, "daemon_alert.json"), alert)
        _append_daemon_log(alert)

        # Print summary
        print(f"\n{'='*40}")
        print(f"[Daemon] SUMMARY")
        print(f"  Triggers: {len(triggers)}")
        for t in triggers:
            print(f"    - {t['detail']}")
        print(f"  Actions: {len(actions)}")
        for a in actions:
            print(f"    - {a['ticker']}: {a['action']} ({a.get('status', 'n/a')})")
        print(f"{'='*40}")


if __name__ == "__main__":
    run_daemon()


==================================================================
FILE: weekly_review.py (     125 lines)
==================================================================
#!/usr/bin/env python3
"""
Weekly Review — Trade Journal Analysis
Run weekly after ~20+ trades to validate the conviction system.

Usage:
  python3 weekly_review.py
  python3 weekly_review.py --since 2026-05-01
"""
import sys
from pathlib import Path

import pandas as pd

JOURNAL_PATH = Path("journal/trades.csv")


def load_journal(since: str = None) -> pd.DataFrame:
    if not JOURNAL_PATH.exists():
        print("No journal found. Run some trades first.")
        sys.exit(0)

    df = pd.read_csv(JOURNAL_PATH, parse_dates=["entry_dt", "exit_dt"])
    if since:
        df = df[df["entry_dt"] >= since]
    print(f"Loaded {len(df)} trades")
    return df


def run_review(since: str = None):
    df = load_journal(since)

    if len(df) == 0:
        print("No trades in journal.")
        return

    print("\n" + "=" * 60)
    print("OPEN CLAW — WEEKLY REVIEW")
    print("=" * 60)

    # 1. Is EXCEPTIONAL actually outperforming STRONG?
    print("\n--- R-MULTIPLE BY TIER ---")
    tier_stats = df.groupby("tier")["r_multiple"].agg(["count", "mean", "std"])
    print(tier_stats.to_string())

    # 2. Does CONFIRM_ENHANCED add alpha?
    print("\n--- R-MULTIPLE BY CONFIRM_ENHANCED ---")
    confirm_stats = df.groupby("confirm_enhanced")["r_multiple"].agg(["count", "mean", "std"])
    print(confirm_stats.to_string())

    # 3. Which Agent 3 verdicts correlate with R?
    print("\n--- R-MULTIPLE BY AGENT 3 VERDICT ---")
    verdict_stats = df.groupby("agent3_verdict")["r_multiple"].agg(["count", "mean"])
    print(verdict_stats.to_string())

    # 4. Sharpe-equivalent by tier (mean R / stdev R)
    print("\n--- SHARPE-EQUIVALENT BY TIER ---")
    sharpe = df.groupby("tier")["r_multiple"].apply(
        lambda x: round(x.mean() / x.std(), 2) if x.std() > 0 else 0
    )
    print(sharpe.to_string())

    # 5. MAE/MFE analysis — are stops too tight?
    print("\n--- MAE/MFE ANALYSIS ---")
    if "max_adverse_excursion_pct" in df.columns:
        winners = df[df["r_multiple"] > 0]
        losers = df[df["r_multiple"] <= 0]

        if len(winners) > 0:
            print(f"\nWinners ({len(winners)}) — Max Adverse Excursion:")
            mae = pd.to_numeric(winners["max_adverse_excursion_pct"], errors="coerce")
            print(f"  Mean: {mae.mean():.2f}%  Median: {mae.median():.2f}%  Max: {mae.max():.2f}%")

        if len(losers) > 0:
            print(f"\nLosers ({len(losers)}) — Max Favorable Excursion:")
            mfe = pd.to_numeric(losers["max_favorable_excursion_pct"], errors="coerce")
            print(f"  Mean: {mfe.mean():.2f}%  Median: {mfe.median():.2f}%  Max: {mfe.max():.2f}%")
    else:
        print("  (No MAE/MFE data yet)")

    # 6. Beta check — are we just long SPX?
    print("\n--- BETA CHECK ---")
    spx_col = pd.to_numeric(df.get("spx_change_over_hold_pct", pd.Series()), errors="coerce")
    r_col = pd.to_numeric(df["r_multiple"], errors="coerce")
    if spx_col.notna().sum() >= 5:
        corr = r_col.corr(spx_col)
        print(f"  R-multiple vs SPX correlation: {corr:.3f}")
        if abs(corr) > 0.7:
            print("  WARNING: High correlation with SPX — may just be beta")
    else:
        print("  (Not enough SPX data yet)")

    # 7. Binding constraint distribution
    print("\n--- BINDING CONSTRAINT DISTRIBUTION ---")
    if "binding_constraint" in df.columns:
        bc = df["binding_constraint"].value_counts()
        print(bc.to_string())
        risk_pct = bc.get("risk", 0) / len(df) * 100
        alloc_pct = bc.get("allocation", 0) / len(df) * 100
        print(f"\n  Risk-bound: {risk_pct:.0f}%  Allocation-bound: {alloc_pct:.0f}%")
        if alloc_pct > 80:
            print("  NOTE: Allocation cap may be too tight — consider raising MAX_ALLOCATION_PCT")

    # 8. Summary stats
    print("\n--- OVERALL ---")
    total = len(df)
    winners_n = len(df[df["r_multiple"] > 0])
    print(f"  Trades: {total}")
    print(f"  Win rate: {winners_n/total*100:.0f}%")
    print(f"  Avg R: {df['r_multiple'].mean():.2f}")
    print(f"  Total P&L: ${df['pnl_dollars'].sum():.2f}")
    print(f"  Avg holding days: {df['holding_days'].mean():.1f}")

    # Calibration warning
    if total < 20:
        print(f"\n  ⚠️ Only {total} trades — too few for statistically valid conclusions.")
        print("  Need ~20+ per cohort before retuning multipliers.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="Only include trades after this date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_review(args.since)


