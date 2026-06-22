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
# VWAP gate removed — caused adverse selection (buying above morning VWAP = exit liquidity for institutions)
# Marketable limit routing: cross the book at ask + 15bps to guarantee fills on breakouts
# from vwap_gate import check_vwap, vwap_gate
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
    except Exception as e:
        print(f"\u26a0\ufe0f X/Twitter fetch failed: {e}")
        print("   Continuing with empty X data — Agent 3 will use news/options/SI only.")
        x_mentions = {t: [] for t in tickers}
        # Save empty mentions so Agent 3 can load them
        with open("output/smart_money_mentions.json", "w") as smf:
            json.dump(x_mentions, smf, indent=2)
        results["x_fetch"] = {"success": False, "error": str(e), "fallback": "empty_mentions"}
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


def run_afternoon_monitor(verbose: bool = False, mechanical_only: bool = False) -> dict:
    """Run Agent 5: position monitoring + broker execution.

    mechanical_only=True → hourly reinforcement mode: skip the Claude thesis
    review, just ratchet trailing stops and execute mechanical stop-hits.
    """
    label = "HOURLY STOP REINFORCEMENT" if mechanical_only else "AFTERNOON POSITION MONITOR"

    # Hourly reinforcement places LIVE stop orders, so it must only run while
    # the market is actually open (9:30–16:00 ET). Outside hours, broker
    # cancel/place round-trips hang. The daily 3:30 monitor is exempt (it runs
    # at the close and tolerates outside-hours behavior).
    if mechanical_only:
        try:
            from safeguards import is_market_open_today
            cal = is_market_open_today()
            if not cal.get("is_open"):
                print(f"[Hourly] 🕒 Market not open ({cal.get('reason')}). Skipping reinforcement.")
                return {"agent5": {"success": True, "note": f"market_not_open:{cal.get('reason')}"}}
        except Exception as e:
            print(f"[Hourly] ⚠️ market-hours check failed: {e}. Skipping for safety.")
            return {"agent5": {"success": False, "error": f"market_check_failed: {e}"}}

    print("=" * 50)
    print(f"🕒 OPEN CLAW — {label}")
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
        agent5_result = run_agent5(preflight["positions"], preflight["snapshot"],
                                   mechanical_only=mechanical_only)
        
        if agent5_result.get("success"):
            print(format_agent5_for_telegram(agent5_result))
            
            with open("output/agent5_decisions.json", "w") as f:
                json.dump(agent5_result, f, indent=2, default=str)
            
            # ━━━ EXECUTE AGENT 5 DECISIONS VIA EXECUTION ENGINE ━━━
            decisions = agent5_result.get("decisions", [])
            crisis = agent5_result.get("crisis_liquidation", False)
            # Run execution if there are ANY decisions — not just CLOSE/TRIM.
            # The old gate (only CLOSE/TRIM/crisis) silently skipped runs that
            # were pure HOLD stop-tightenings, which is exactly why trailing
            # stops never got pushed to the broker and went stale (BAC stuck
            # at \$52.31 below cost). HOLD trailing-stop updates MUST execute.
            actionable = bool(decisions) or crisis
            
            if actionable:
                print("\n" + "━" * 40)
                print("💰 EXECUTION ENGINE — AGENT 5 DECISIONS")
                print("━" * 40)
                
                try:
                    from execution_engine import ExecutionEngine
                    engine = ExecutionEngine()
                    exec_results = []
                    
                    if crisis:
                        # Crisis = liquidate everything atomically
                        positions = engine.broker.get_positions()
                        for p in positions:
                            result = engine.atomic_liquidate(p["ticker"], reason="CRISIS_LIQUIDATION")
                            exec_results.append(result)
                        print(f"  🚨 CRISIS: Atomically liquidated {len(positions)} positions")
                    else:
                        for d in decisions:
                            ticker = d.get("ticker")
                            action = d.get("action", "HOLD")
                            if action == "CLOSE":
                                result = engine.atomic_liquidate(ticker, reason=f"Agent5_CLOSE: {d.get('reasoning', '')}")
                                exec_results.append(result)
                            elif action == "TRIM":
                                # Trim = update stop to current price (let daemon handle it)
                                new_stop = d.get("new_stop", d.get("current_price", 0))
                                if new_stop > 0:
                                    engine.update_stop(ticker, new_stop, reason="Agent5_TRIM")
                                exec_results.append({"ticker": ticker, "action": "TRIM", "new_stop": new_stop})
                            elif action == "HOLD":
                                # Update trailing stop whenever the computed stop
                                # differs from what is actually LIVE (per ledger),
                                # not just when new_stop > original_stop. The old
                                # guard skipped stale stops (e.g. ledger stuck at
                                # \$52.31 while engine computed \$55.71).
                                new_stop = d.get("new_stop")
                                original_stop = d.get("original_stop")
                                live_stop = None
                                try:
                                    import sqlite3 as _sql
                                    from execution_engine import DB_PATH as _DBP
                                    with _sql.connect(_DBP, timeout=20.0) as _c:
                                        _r = _c.execute(
                                            "SELECT target_stop_price FROM active_trades "
                                            "WHERE ticker = ? AND closed_at IS NULL",
                                            (ticker,),
                                        ).fetchone()
                                        if _r:
                                            live_stop = _r[0]
                                except Exception:
                                    live_stop = None
                                baseline = live_stop if live_stop is not None else original_stop
                                needs_update = bool(new_stop) and (
                                    not baseline or baseline <= 0 or new_stop > baseline
                                )
                                if needs_update:
                                    # Atomic trailing: cancel → wait → place (synchronous)
                                    if not engine.update_trailing_stop(ticker, new_stop):
                                        # Fallback to async daemon-based update
                                        engine.update_stop(ticker, new_stop, reason="Agent5_TRAIL_fallback")
                                    print(f"  🔓 {ticker}: stop {baseline} → {new_stop} (pushed to broker)")
                                exec_results.append({"ticker": ticker, "action": "HOLD", "new_stop": new_stop, "prev_stop": baseline})
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
                        if r.get("action") in ("LIQUIDATED", "CLOSE", "TRIM", "close", "trim", "close_all"):
                            pos_data = next((p for p in preflight.get("positions", []) if p.get("ticker") == r.get("ticker")), {})

                            # Wait for settlement and fetch actual fill price
                            import time as _time
                            _time.sleep(3.0)
                            try:
                                todays_orders = engine.broker.get_orders_today()
                                sell_order = next(
                                    (o for o in todays_orders
                                     if o.get("ticker") == r.get("ticker")
                                     and str(o.get("side", "")).lower() == "sell"
                                     and o.get("status", "").lower() in ("filled", "executed")),
                                    None,
                                )
                                real_exit_price = (
                                    float(sell_order["filled_avg_price"])
                                    if sell_order and sell_order.get("filled_avg_price")
                                    else snapshot.get(r.get("ticker", ""), {}).get("current_price", 0)
                                )
                            except Exception:
                                real_exit_price = snapshot.get(r.get("ticker", ""), {}).get("current_price", 0)

                            if pos_data and real_exit_price:
                                try:
                                    record = build_trade_record(
                                        trade_order=pos_data,
                                        directive=directive,
                                        agent3_verification={},
                                        exit_price=real_exit_price,
                                        exit_reason=f"Agent 5 {r.get('action', 'close')}",
                                    )
                                    log_close(record)
                                    print(f"  📝 Logged {r.get('ticker')} to trade journal (fill: ${real_exit_price:.2f})")

                                    # Add to penalty box if closed for a loss
                                    entry = pos_data.get("entry_price", pos_data.get("avg_entry_price", 0))
                                    if real_exit_price < entry:
                                        loss = (entry - real_exit_price) * pos_data.get("shares", 0)
                                        add_to_penalty_box(
                                            r.get("ticker", ""),
                                            loss,
                                            reason=f"Agent 5 {r.get('action', 'close')}",
                                        )
                                except Exception as je:
                                    print(f"  ⚠️ Journal log failed for {r.get('ticker')}: {je}")
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
        
        # Execute trades on the broker (Robinhood)
        trade_orders = agent4_result.get("trade_orders", [])
        buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
        if buy_orders:
            print("\n" + "━" * 40)
            print("💰 EXECUTION ENGINE — LEDGER + BROKER")
            print("━" * 40)
            try:
                from execution_engine import ExecutionEngine
                engine = ExecutionEngine()

                # Verify daemon is alive before submitting trades
                if not ExecutionEngine.is_daemon_alive():
                    print("⚠️ WARNING: Execution daemon not running! Trades will be logged but stops won't auto-place.")
                    print("  Start with: python3 run_execution_daemon.py")

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
    Execute pending orders using PASSIVE MIDPOINT limits.
    VWAP gate removed — it caused adverse selection by buying above morning VWAP
    (i.e., crossing the spread to pay institutional algos who VWAP-slice their sells).
    Now routes limit orders at the NBBO midpoint via the ExecutionEngine.
    """
    import uuid
    import market_data
    from execution_engine import ExecutionEngine

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
    print("💰 DEFERRED EXECUTION — PASSIVE MIDPOINT ROUTING")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)

    engine = ExecutionEngine()

    # PRE-TRADE CHECK: Verify execution daemon is alive
    if not ExecutionEngine.is_daemon_alive():
        print("❌ ABORT: Execution daemon is not running or heartbeat is stale (>60s).")
        print("  Start it with: python3 run_execution_daemon.py")
        print("  Or: bash run_daemon.sh")
        return {"success": False, "error": "daemon_not_alive", "fills": []}
    print("✅ Execution daemon heartbeat confirmed")

    # Fetch live quotes to calculate NBBO midpoint
    tickers = [o["ticker"] for o in buy_orders]
    print(f"\n📡 Fetching live quotes for {len(tickers)} tickers...")
    live_quotes = market_data.fetch_latest_quotes(tickers)

    fills = []
    for order in buy_orders:
        ticker = order["ticker"]
        quote = live_quotes.get(ticker, {})

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        last = quote.get("last", order.get("entry_price", 0))

        # Broken Book Guardrails
        if bid <= 0 or ask <= 0 or ask < bid:
            print(f"  🚫 REJECTED {ticker}: Order book broken (Bid: {bid}, Ask: {ask}).")
            fills.append({"ticker": ticker, "status": "rejected_broken_book"})
            engine.log_incident(
                ticker=ticker, incident_type="BROKEN_BOOK",
                bid=bid, ask=ask, target_shares=int(order.get("shares", 0)),
                root_cause="broken_order_book",
                notes=f"Bid={bid}, Ask={ask}. Order book invalid at execution time.",
            )
            continue

        midpoint = round((bid + ask) / 2.0, 2)
        spread_pct = (ask - bid) / midpoint if midpoint > 0 else 999

        if spread_pct > 0.05:
            print(f"  🚫 REJECTED {ticker}: Spread is toxic ({spread_pct*100:.1f}% wide). Bid: {bid}, Ask: {ask}")
            fills.append({"ticker": ticker, "status": "rejected_wide_spread"})
            engine.log_incident(
                ticker=ticker, incident_type="WIDE_SPREAD",
                bid=bid, ask=ask, target_shares=int(order.get("shares", 0)),
                root_cause="toxic_spread",
                notes=f"Spread {spread_pct*100:.1f}% exceeds 5% threshold.",
            )
            continue

        print(f"  [NBBO] {ticker}: Bid ${bid:.2f} | Ask ${ask:.2f} | Spread {spread_pct*10000:.0f} bps")

        # ---------------------------------------------------------
        # Marketable Limit Routing
        # Cross the book by targeting the Ask + 15 bps slippage allowance.
        # This pays the spread to guarantee fill and defeat adverse selection.
        # ---------------------------------------------------------
        marketable_limit = round(ask * 1.0015, 2)

        # Safety: reject if stock gapped up > 3% from planned entry (avoid chasing)
        # Compare against the ASK (our actual fill target), not the midpoint
        entry_price = order.get("entry_price", ask)
        if entry_price > 0:
            gap_pct = (ask - entry_price) / entry_price
            if gap_pct > 0.03:
                print(f"  🚫 REJECTED {ticker}: Gapped up {gap_pct*100:.1f}% from planned entry. Avoid chasing.")
                fills.append({"ticker": ticker, "status": "rejected_gap_up", "gap_pct": round(gap_pct * 100, 1)})
                engine.log_incident(
                    ticker=ticker, incident_type="GAP_UP_REJECTION",
                    limit_price=entry_price, bid=bid, ask=ask,
                    target_shares=int(order.get("shares", 0)),
                    root_cause="gap_up_chase_prevention",
                    notes=f"Ask gapped {gap_pct*100:.1f}% above planned entry ${entry_price:.2f}.",
                )
                continue

        trade_id = str(uuid.uuid4())

        # Route intent to the Execution Ledger
        # Marketable limit: ask + 15bps to cross the spread and guarantee fills
        result = engine.submit_trade_intent(
            trade_id=trade_id,
            ticker=ticker,
            shares=int(order.get("shares", 0)),
            limit_price=marketable_limit,
            stop_price=order.get("stop_loss", 0),
        )
        fills.append({
            "ticker": ticker,
            "status": result.get("status", "unknown"),
            "limit_price": marketable_limit,
            "order_id": result.get("order_id"),
        })
        print(f"  ✅ {ticker}: Marketable limit routed at ${marketable_limit:.2f} (Ask ${ask:.2f} + 15bps)")

    submitted = sum(1 for f in fills if f.get("status") == "submitted")
    print(f"\n📊 Results: {submitted}/{len(fills)} orders routed to execution ledger")
    print("📡 Background daemon will handle fills → stop placement")

    # Clean up pending file
    os.rename(pending_path, pending_path.replace(".json", f"_executed_{datetime.now().strftime('%Y%m%d_%H%M')}.json"))
    return {"success": True, "fills": fills}


if __name__ == "__main__":
    from safeguards import run_with_crash_protection
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    if mode == "morning":
        run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
    elif mode == "monitor":
        run_with_crash_protection(run_afternoon_monitor, "Afternoon Monitor", verbose=verbose)
    elif mode == "hourly":
        # Mechanical-only trailing-stop reinforcement (every market hour).
        run_with_crash_protection(
            lambda **kw: run_afternoon_monitor(mechanical_only=True, **kw),
            "Hourly Stop Reinforcement", verbose=verbose,
        )
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
        print("Usage: python3 orchestrator.py [morning|monitor|hourly|resume|execute|full]")
