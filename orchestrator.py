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
from broker_factory import get_broker
from trade_journal import log_close, build_trade_record
from watchlist import Watchlist, promote_ready_candidates
from vwap_gate import check_vwap, vwap_gate
from run_archiver import archive_run
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
            candidates = candidates + ready_candidates
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
    
    # ━━━ STEP 6: SAVE ORDERS FOR DEFERRED EXECUTION ━━━
    print("\n" + "━" * 40)
    print("💾 STEP 6: ORDERS SAVED — EXECUTION DEFERRED")
    print("━" * 40)
    
    trade_orders = agent4_result.get("trade_orders", [])
    buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
    
    if not buy_orders:
        print("📋 No BUY orders in tear sheet — nothing to execute.")
    else:
        # Save orders for deferred execution at 9:45-10:15 AM
        pending = {
            "timestamp": datetime.now().isoformat(),
            "orders": trade_orders,
            "directive": directive,
            "note": "Execute after 9:45 AM ET when VWAP has a mature volume profile",
        }
        os.makedirs("output", exist_ok=True)
        with open("output/pending_orders.json", "w") as f:
            json.dump(pending, f, indent=2)
        
        print(f"  📋 {len(buy_orders)} BUY order(s) saved to output/pending_orders.json")
        print(f"  ⏰ Execute at 9:45-10:15 AM via: python3 orchestrator.py execute")
        for o in buy_orders:
            print(f"     BUY {o.get('shares', '?')} {o.get('ticker', '?')} @ ~${o.get('entry_price', '?')}")
    
    # ━━━ ARCHIVE RUN ━━━
    try:
        archive_run("morning")
    except Exception as e:
        print(f"⚠️ Archiver failed: {e}")
    
    # ━━━ DONE ━━━
    print("\n" + "=" * 50)
    print("✅ MORNING PIPELINE COMPLETE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("📈 Trades ready for execution.")
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
                    broker = get_broker()
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
            broker = get_broker()
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
        
        # ━━━ ARCHIVE RUN ━━━
        try:
            archive_run("monitor")
        except Exception as e:
            print(f"⚠️ Archiver failed: {e}")
        
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
            print("💰 EXECUTION ENGINE — LEDGER + BROKER")
            print("━" * 40)
            try:
                from execution_engine import ExecutionEngine
                engine = ExecutionEngine()
                fills = engine.submit_batch_intents(trade_orders)
                submitted = [f for f in fills if f.get("status") == "submitted"]
                print(f"  ✅ {len(submitted)} intents logged to execution ledger")
                print("  📡 Background daemon will route entries and attach stops")
            except Exception as e:
                print(f"❌ Execution engine FAILED: {e}")
    
    print("\n✅ Pipeline resumed and complete.")
    return {"agent3": agent3_result, "agent4": agent4_result}


def run_deferred_execution() -> dict:
    """
    Execute pending orders with VWAP gate.
    Run at 9:45-10:15 AM when intraday VWAP has matured.
    """
    pending_path = "output/pending_orders.json"
    if not os.path.exists(pending_path):
        print("❌ No pending orders found. Run morning pipeline first.")
        return {"error": "no_pending_orders"}
    
    with open(pending_path) as f:
        pending = json.load(f)
    
    trade_orders = pending.get("orders", [])
    buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
    
    if not buy_orders:
        print("📋 No BUY orders to execute.")
        return {"success": True, "fills": []}
    
    print("=" * 50)
    print("💰 DEFERRED EXECUTION — VWAP GATE + BROKER")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)
    
    # Run VWAP gate with mature intraday data
    print("\n🔒 VWAP Gate: Checking intraday VWAP...")
    approved_orders, rejected_orders = vwap_gate(trade_orders)
    
    if rejected_orders:
        print(f"  ❌ VWAP Rejected ({len(rejected_orders)}):")
        for r in rejected_orders:
            print(f"     {r['ticker']}: {r.get('reject_reason')}")
    
    approved_buys = [o for o in approved_orders if o.get('action') == 'BUY']
    
    if not approved_buys:
        print("📋 All orders rejected by VWAP gate.")
        return {"success": True, "fills": [], "all_rejected": True}
    
    print(f"  ✅ VWAP Approved: {len(approved_buys)} BUY order(s)")
    
    # Execute via execution engine (stateful ledger + daemon)
    try:
        from execution_engine import ExecutionEngine
        engine = ExecutionEngine()
        fills = engine.submit_batch_intents(approved_orders)
        
        submitted = [f for f in fills if f.get("status") == "submitted"]
        errors = [f for f in fills if f.get("status") in ("error", "rejected")]
        
        print(f"\n📊 Execution Engine Results:")
        print(f"  ✅ Submitted to ledger: {len(submitted)}")
        print(f"  ❌ Errors: {len(errors)}")
        print(f"  📡 Background daemon will handle fills → stop placement")
        
        # Clean up pending file
        os.rename(pending_path, pending_path.replace(".json", f"_executed_{datetime.now().strftime('%Y%m%d_%H%M')}.json"))
        
        return {"success": True, "fills": fills}
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return {"success": False, "error": str(e)}


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
    elif mode == "execute":
        run_with_crash_protection(run_deferred_execution, "Deferred Execution")
    elif mode == "full":
        results = run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
        if results and all(r.get("success", False) for r in results.values() if isinstance(r, dict)):
            print("\n⏰ Morning pipeline done. Agent 5 runs at 3:30 PM.")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 orchestrator.py [morning|monitor|resume|execute|full]")
