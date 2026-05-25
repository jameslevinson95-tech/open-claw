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


def _get_current_stop_price(broker: AlpacaBroker, ticker: str) -> float:
    """Get the current stop-loss price for a ticker from Alpaca open orders."""
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[ticker], limit=20)
        orders = broker.client.get_orders(req)
        for order in orders:
            if order.order_type == "stop" or (hasattr(order, 'stop_price') and order.stop_price):
                return float(order.stop_price)
    except Exception:
        pass
    return None


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
        current_price = pos["current_price"]
        unrealized_pl = pos["unrealized_pl"]

        if unrealized_pl >= 0:
            # Profitable — tighten stop to breakeven, but NEVER widen an existing stop
            # Check if there's already a stop tighter than (i.e. above) entry price
            current_stop = _get_current_stop_price(broker, ticker)
            if current_stop and current_stop > entry_price:
                # Stop already trailed above entry — do NOT widen it
                actions.append({
                    "ticker": ticker,
                    "action": "SKIP",
                    "note": f"Stop already at ${current_stop:.2f} > entry ${entry_price:.2f} — not widening",
                })
                continue

            # GUARD: If current price is already below entry, a stop at entry_price
            # would trigger immediately as a market sell with uncontrolled slippage.
            # Close the position directly instead.
            if current_price < entry_price:
                result = broker.close_position(ticker)
                action = {
                    "ticker": ticker,
                    "action": "CLOSE_BELOW_ENTRY",
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "unrealized_pl": unrealized_pl,
                    "close_result": result,
                    "note": f"Price ${current_price:.2f} < entry ${entry_price:.2f} — closed to avoid immediate stop trigger",
                }
                actions.append(action)
                print(f"  [Daemon] {ticker}: Price ${current_price:.2f} < entry ${entry_price:.2f} → CLOSED (would trigger immediately)")
                continue

            # Place new stop FIRST, then cancel old orders (position never naked)
            action = {
                "ticker": ticker,
                "action": "TIGHTEN_STOP_BREAKEVEN",
                "entry_price": entry_price,
                "unrealized_pl": unrealized_pl,
                "note": f"Stop tightened to breakeven (${entry_price:.2f})",
            }
            try:
                from alpaca.trading.requests import StopOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce

                # Collect existing order IDs for this ticker BEFORE submitting new one
                existing_order_ids = []
                orders = broker.client.get_orders()
                for o in orders:
                    if o.symbol == ticker:
                        existing_order_ids.append(o.id)

                # Submit new breakeven stop FIRST — position stays protected
                stop_req = StopOrderRequest(
                    symbol=ticker,
                    qty=pos["shares"],
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    stop_price=round(entry_price, 2),
                )
                broker.client.submit_order(stop_req)

                # NOW cancel old orders (position was never unprotected)
                for oid in existing_order_ids:
                    try:
                        broker.client.cancel_order_by_id(oid)
                    except Exception:
                        pass

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

    # GUARD: If current price is already below entry, a stop at entry_price
    # would trigger immediately as a market sell with uncontrolled slippage.
    # Close the position directly instead.
    if current_price < entry_price:
        action = {
            "ticker": ticker,
            "action": "CLOSE_BELOW_ENTRY",
            "entry_price": entry_price,
            "current_price": current_price,
            "note": f"Price ${current_price:.2f} < entry ${entry_price:.2f} — closed to avoid immediate stop trigger",
        }
        try:
            result = broker.close_position(ticker)
            action["close_result"] = result
            action["status"] = "executed"
        except Exception as e:
            action["status"] = "logged_only"
            action["error"] = str(e)
        print(f"  [Daemon] {ticker}: Price ${current_price:.2f} < entry ${entry_price:.2f} → CLOSED (would trigger immediately)")
        return action

    # Place new stop FIRST, then cancel old orders (position never naked)
    action = {
        "ticker": ticker,
        "action": "INDIVIDUAL_STOP_TIGHTEN",
        "entry_price": entry_price,
        "note": f"Position down >5% intraday — stop moved to breakeven (${entry_price:.2f})",
    }

    try:
        from alpaca.trading.requests import StopOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        # Collect existing order IDs for this ticker BEFORE submitting new one
        existing_order_ids = []
        orders = broker.client.get_orders()
        for o in orders:
            if o.symbol == ticker:
                existing_order_ids.append(o.id)

        # Submit new breakeven stop FIRST — position stays protected
        stop_req = StopOrderRequest(
            symbol=ticker,
            qty=pos["shares"],
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            stop_price=round(entry_price, 2),
        )
        broker.client.submit_order(stop_req)

        # NOW cancel old orders (position was never unprotected)
        for oid in existing_order_ids:
            try:
                broker.client.cancel_order_by_id(oid)
            except Exception:
                pass

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
