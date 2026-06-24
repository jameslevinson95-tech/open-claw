"""
Flash-Crash Daemon — Lightweight intraday safety net (NO LLM)
Runs every 5-10 minutes during market hours.

Checks (every ~7 min during market hours):
  1. SPY intraday drop > 2.5% AND VIX spike > 30% → market-wide defensive protocol
  2. Individual position down > 5% intraday → tighten that stop to breakeven
  3. Trailing-profit ladder (EVERY cycle) → same breakeven/+50%/+75% math as the
     3:30 PM Agent 5 monitor. Ratchets stops UP as winners run and locks in gains
     (atomic CLOSE) the moment price pulls back into the laddered stop — closing
     the "gave back gains between monitor windows" gap. Reuses
     agent5_position_monitor.calculate_trailing_stops for identical math + shared HWM state.

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
# yfinance removed — all data routed through DataProvider

from broker_factory import get_broker

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Thresholds (tightened to avoid triggering on normal volatility)
# Market-wide defensive protocol requires BOTH SPY drop AND VIX spike (AND logic)
SPY_DROP_THRESHOLD = -0.025       # -2.5% from today's open
VIX_SPIKE_THRESHOLD = 0.30        # +30% from today's open
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
    Uses DataProvider for SPY (bars) and VIX (index). Falls back to yfinance.
    Returns {"open": float, "current": float, "change_pct": float} or {"error": str}.
    """
    from data_provider import get_provider, DataUnavailable

    # VIX/SPX — route through get_index for proper fallback chain
    clean = ticker.upper().replace("^", "")
    if clean in ("VIX", "SPX"):
        try:
            dp = get_provider()
            idx = dp.get_index(clean)
            current = idx["value"]
            # For intraday open we still need bars — try SPY as proxy for SPX
            proxy = "SPY" if clean == "SPX" else "VIXY"
            try:
                bars = dp.get_bars(proxy, lookback_days=1, timespan="minute")
                if bars is not None and not bars.empty:
                    open_price = float(bars["Open"].iloc[0])
                else:
                    open_price = current  # Can't get open, use current (0% change)
            except (DataUnavailable, Exception):
                open_price = current

            if open_price <= 0:
                return {"error": f"Invalid open price for {ticker}"}

            change_pct = (current - open_price) / open_price
            return {
                "open": round(open_price, 2),
                "current": round(current, 2),
                "change_pct": round(change_pct, 4),
                "source": idx.get("source", "unknown"),
                "is_proxy": idx.get("is_proxy", False),
            }
        except DataUnavailable as e:
            return {"error": f"DataProvider: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # Regular tickers (SPY, individual positions) — use DataProvider bars
    try:
        dp = get_provider()
        bars = dp.get_bars(ticker, lookback_days=1, timespan="minute")
        if bars is None or bars.empty:
            return {"error": f"No intraday data for {ticker}"}

        open_price = float(bars["Open"].iloc[0])
        current_price = float(bars["Close"].iloc[-1])

        if open_price <= 0:
            return {"error": f"Invalid open price for {ticker}"}

        change_pct = (current_price - open_price) / open_price
        return {
            "open": round(open_price, 2),
            "current": round(current_price, 2),
            "change_pct": round(change_pct, 4),
        }
    except DataUnavailable as e:
        return {"error": f"DataProvider: {e}"}
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


def _get_current_stop_price(broker, ticker: str) -> float:
    """Get the current stop-loss price for a ticker from open orders (broker-agnostic)."""
    try:
        orders = broker.get_orders_today()
        for o in orders:
            if (o.get("ticker") == ticker
                and o.get("status", "").lower() in ("open", "queued", "confirmed")
                and (o.get("order_type", "").lower() == "stop" or o.get("stop_price"))):
                return float(o["stop_price"])
    except Exception:
        pass
    return None


def execute_defensive_protocol(broker, trigger_reason: str, positions: list) -> list:
    """
    Execute defensive protocol on all positions using the execution engine.
    - Profitable positions: tighten stop to breakeven via engine
    - Losing positions: atomic liquidation via engine
    Returns list of actions taken.
    """
    from execution_engine import ExecutionEngine
    engine = ExecutionEngine(broker=broker)
    actions = []

    for pos in positions:
        ticker = pos["ticker"]
        entry_price = pos["avg_entry_price"]
        unrealized_pl = pos["unrealized_pl"]

        if unrealized_pl < 0:
            # Losing — atomic liquidate (cancel resting orders → wait → market sell)
            result = engine.atomic_liquidate(ticker, reason=trigger_reason)
            actions.append({"ticker": ticker, "action": "LIQUIDATED", "result": result})
            print(f"  [Daemon] {ticker}: Losing (${unrealized_pl:.2f}) → ATOMICALLY CLOSED")
        else:
            # Profitable — tighten stop to breakeven, but NEVER widen
            current_stop = _get_current_stop_price(broker, ticker)
            if current_stop and current_stop > entry_price:
                actions.append({
                    "ticker": ticker,
                    "action": "SKIP",
                    "note": f"Stop already at ${current_stop:.2f} > entry ${entry_price:.2f} — not widening",
                })
                print(f"  [Daemon] {ticker}: Stop already tight at ${current_stop:.2f} — skipping")
                continue

            # Atomic trailing stop: cancel old → wait for clearinghouse → place new
            success = engine.update_trailing_stop(ticker, entry_price)
            if success:
                actions.append({
                    "ticker": ticker,
                    "action": "TIGHTEN_STOP_BREAKEVEN",
                    "new_stop": entry_price,
                })
                print(f"  [Daemon] {ticker}: Profitable (+${unrealized_pl:.2f}) \u2192 stop moved to ${entry_price:.2f}")
            else:
                actions.append({"ticker": ticker, "action": "TIGHTEN_STOP_FAILED"})
                print(f"  [Daemon] {ticker}: TIGHTEN FAILED \u2014 daemon will retry via update_stop fallback")
                engine.update_stop(ticker, entry_price, reason=f"flash_crash_{trigger_reason}_fallback")

    return actions


def tighten_individual_stop(broker, pos: dict) -> dict:
    """Tighten a single position's stop to breakeven when it's down >5% intraday."""
    from execution_engine import ExecutionEngine
    engine = ExecutionEngine(broker=broker)

    ticker = pos["ticker"]
    entry_price = pos["avg_entry_price"]
    current_price = pos["current_price"]

    # Check if stop is already tighter than entry price — don't widen it
    current_stop = _get_current_stop_price(broker, ticker)
    if current_stop and current_stop > entry_price:
        action = {
            "ticker": ticker,
            "action": "SKIP",
            "note": f"Stop already at ${current_stop:.2f} > entry ${entry_price:.2f} — not widening",
        }
        print(f"  [Daemon] {ticker}: Stop already at ${current_stop:.2f} > entry — skipping")
        return action

    # GUARD: If current price is already below entry, close via atomic liquidation
    if current_price < entry_price:
        result = engine.atomic_liquidate(ticker, reason="price_below_entry_during_tighten")
        action = {
            "ticker": ticker,
            "action": "CLOSE_BELOW_ENTRY",
            "entry_price": entry_price,
            "current_price": current_price,
            "result": result,
            "note": f"Price ${current_price:.2f} < entry ${entry_price:.2f} — atomically closed",
        }
        print(f"  [Daemon] {ticker}: Price ${current_price:.2f} < entry ${entry_price:.2f} → ATOMICALLY CLOSED")
        return action

    # Atomic trailing stop: cancel old → wait for clearinghouse → place new
    success = engine.update_trailing_stop(ticker, entry_price)
    if success:
        action = {
            "ticker": ticker,
            "action": "INDIVIDUAL_STOP_TIGHTEN",
            "entry_price": entry_price,
            "note": f"Position down >5% intraday — stop moved to breakeven (${entry_price:.2f})",
            "status": "executed",
        }
        print(f"  [Daemon] {ticker}: Down >5% intraday \u2192 stop tightened to ${entry_price:.2f}")
    else:
        # Fallback to async update_stop (daemon will place when it can)
        engine.update_stop(ticker, entry_price, reason="individual_stop_tighten_fallback")
        action = {
            "ticker": ticker,
            "action": "INDIVIDUAL_STOP_TIGHTEN",
            "entry_price": entry_price,
            "note": f"Atomic tighten failed \u2014 daemon will retry",
            "status": "deferred",
        }
        print(f"  [Daemon] {ticker}: Atomic tighten failed \u2014 deferred to daemon")
    return action


def _get_db_stop_price(ticker: str) -> float:
    """
    Read the authoritative target stop from the execution ledger DB
    (active_trades.target_stop_price). This is the source of truth the execution
    engine uses — NOT resting broker orders — so the ladder honors 'never widen'
    correctly and never fights the execution daemon's stop management.
    Returns the stop price, or 0 if no active trade / unavailable.
    """
    try:
        import sqlite3
        from execution_engine import DB_PATH
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            row = conn.execute(
                "SELECT target_stop_price FROM active_trades WHERE ticker = ? AND closed_at IS NULL",
                (ticker,),
            ).fetchone()
            if row and row[0]:
                return float(row[0])
    except Exception:
        pass
    return 0.0


def run_trailing_ladder(broker, positions: list) -> list:
    """
    Intraday profit-locking. Runs the SAME trailing-stop ladder as the 3:30 PM
    Agent 5 monitor (breakeven / +50% / +75%) so a winner that spikes and bleeds
    back gets its stop ratcheted up between the fixed monitor windows.

    Reuses agent5_position_monitor.calculate_trailing_stops for identical math
    (incl. shared high-water-mark state on disk). NO LLM.

    For each position:
      - If price <= the ladder stop  -> atomic CLOSE (lock the gain / cut)
      - Else if ladder stop > current resting stop -> ratchet stop UP (never widen)
      - Else -> no-op
    Returns list of actions taken.
    """
    from agent5_position_monitor import (
        calculate_trailing_stops,
        _load_portfolio_state,
        _save_portfolio_state,
    )
    from execution_engine import ExecutionEngine

    if not positions:
        return []

    # Snapshot HWM state BEFORE the ladder so we can restore any open-position
    # keys it prunes. calculate_trailing_stops() deletes state for tickers not in
    # the list it's given; if the broker ever returns a partial/empty list, that
    # would wipe live floors. We merge those keys back after.
    hwm_before = dict(_load_portfolio_state())

    # Adapt broker positions -> the shape calculate_trailing_stops expects.
    adapted = []
    snapshot = {}
    for pos in positions:
        ticker = pos["ticker"]
        current_price = pos.get("current_price")
        # Fall back to a fresh intraday quote if the broker didn't include price
        if current_price is None:
            q = get_intraday_change(ticker)
            current_price = q.get("current") if "error" not in q else None
        if current_price is None:
            continue
        # Authoritative stop = execution-ledger DB target, not resting broker order.
        db_stop = _get_db_stop_price(ticker)
        adapted.append({
            "ticker": ticker,
            "entry_price": pos.get("avg_entry_price", 0),
            "stop_loss": db_stop,
            "shares": pos.get("shares", pos.get("qty", 0)),
        })
        snapshot[ticker] = {"current_price": current_price}

    if not adapted:
        return []

    laddered = calculate_trailing_stops(adapted, snapshot)

    # Restore HWM state for any currently-open ticker the ladder pruned
    # (defensive against partial broker reads).
    open_tickers = {p["ticker"] for p in positions}
    hwm_after = _load_portfolio_state()
    restored = False
    for t, v in hwm_before.items():
        if t in open_tickers and t not in hwm_after:
            hwm_after[t] = v
            restored = True
    if restored:
        _save_portfolio_state(hwm_after)

    engine = ExecutionEngine(broker=broker)
    actions = []
    for r in laddered:
        ticker = r["ticker"]
        mech = r.get("mechanical_action", "HOLD")
        new_stop = r.get("new_stop", 0)
        resting_stop = _get_db_stop_price(ticker)
        pnl_pct = r.get("pnl_pct", 0)

        if mech == "CLOSE":
            # Price fell into the laddered stop -> lock it in atomically.
            result = engine.atomic_liquidate(
                ticker, reason=f"intraday_ladder_CLOSE (pnl {pnl_pct:.1f}%, stop ${new_stop})"
            )
            actions.append({
                "ticker": ticker,
                "action": "LADDER_CLOSE",
                "pnl_pct": pnl_pct,
                "stop": new_stop,
                "result": result,
            })
            print(f"  [Daemon] {ticker}: ladder CLOSE — price hit ${new_stop} (pnl {pnl_pct:.1f}%) → liquidated")
        elif new_stop and new_stop > resting_stop:
            # Ratchet the stop UP only (never widen).
            success = engine.update_trailing_stop(ticker, new_stop)
            if not success:
                engine.update_stop(ticker, new_stop, reason="intraday_ladder_trail_fallback")
            actions.append({
                "ticker": ticker,
                "action": "LADDER_TRAIL",
                "pnl_pct": pnl_pct,
                "old_stop": resting_stop,
                "new_stop": new_stop,
                "note": r.get("trailing_stop_note", ""),
            })
            print(f"  [Daemon] {ticker}: ladder trail — stop ${resting_stop} → ${new_stop} (pnl {pnl_pct:.1f}%)")

    return actions


def run_daemon():
    """
    Main daemon entry point. Checks market conditions and positions.
    If no triggers, exits silently. If triggers fire, executes defensive protocol.
    Also runs the intraday trailing-profit ladder every cycle (profit-locking).
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
        # Widen threshold if using ETF proxy (tracking error vs spot VIX)
        effective_threshold = VIX_SPIKE_THRESHOLD
        if vix_data.get("is_proxy"):
            effective_threshold *= 1.25
            print(f"[Daemon] VIX via proxy — widened threshold to +{effective_threshold*100:.0f}%")

        if vix_data["change_pct"] >= effective_threshold:
            trigger = {
                "type": "VIX_SPIKE",
                "detail": f"VIX up {vix_data['change_pct']*100:.2f}% (threshold: +{effective_threshold*100:.0f}%)",
                "open": vix_data["open"],
                "current": vix_data["current"],
                "change_pct": vix_data["change_pct"],
                "source": vix_data.get("source", "unknown"),
            }
            triggers.append(trigger)
            print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
    else:
        # VIX blind — alert but still run per-position checks
        from safeguards import send_telegram
        send_telegram(f"⚠️ Flash crash daemon blind on VIX: {vix_data['error']} — running degraded (per-position checks only)")
        print(f"[Daemon] Warning: VIX BLIND — {vix_data['error']} — skipping market-wide trigger, running per-position checks")

    # --- Load positions ---
    try:
        broker = get_broker()
        positions = broker.get_positions()
    except Exception as e:
        print(f"[Daemon] ERROR: Could not connect to broker — {e}")
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

    # --- Intraday trailing-profit ladder (runs EVERY cycle, profit-locking) ---
    # Same breakeven/+50%/+75% math as the 3:30 PM Agent 5 monitor, so winners
    # that give back gains between the fixed monitor windows still get locked in.
    try:
        ladder_actions = run_trailing_ladder(broker, positions)
        if ladder_actions:
            actions.extend(ladder_actions)
            # Treat ladder activity as a logged event even without crash triggers.
            triggers.append({
                "type": "TRAILING_LADDER",
                "detail": f"Intraday ladder acted on {len(ladder_actions)} position(s)",
            })
    except Exception as le:
        print(f"[Daemon] Warning: trailing ladder failed — {le}")

    # --- If market-wide triggers fired, run full defensive protocol ---
    # Require BOTH SPY drop AND VIX spike to avoid triggering on normal noise.
    # A -2.5% SPY day with calm VIX is an orderly pullback, not a crash.
    spy_triggered = any(t["type"] == "SPY_DROP" for t in triggers)
    vix_triggered = any(t["type"] == "VIX_SPIKE" for t in triggers)

    if spy_triggered and vix_triggered:
        market_wide_triggers = [t for t in triggers if t["type"] in ("SPY_DROP", "VIX_SPIKE")]
        trigger_reasons = "; ".join(t["detail"] for t in market_wide_triggers)
        print(f"\n[Daemon] 🛡️ DEFENSIVE PROTOCOL ACTIVATED: {trigger_reasons}")
        defensive_actions = execute_defensive_protocol(broker, trigger_reasons, positions)
        actions.extend(defensive_actions)
    elif spy_triggered or vix_triggered:
        single_triggers = [t for t in triggers if t["type"] in ("SPY_DROP", "VIX_SPIKE")]
        for t in single_triggers:
            print(f"[Daemon] ⚠️ WARNING (no action): {t['detail']} — waiting for dual confirmation")

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
