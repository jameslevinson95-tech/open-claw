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
# yfinance removed — all data routed through DataProvider
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
    normalize_regime,
    normalize_vol_regime,
)
from broker_factory import get_broker

load_dotenv()


# ATR multipliers by conviction tier — higher conviction = wider stop (more room)
ATR_MULTIPLIERS = {
    "PASS": 1.2,
    "STRONG": 1.5,
    "EXCEPTIONAL": 2.0,
}

# Volatility Regime ATR Modifiers — widen stops in high-vol to survive whipsaws
# GEX-driven: negative GEX → Elevated/Stressed → wider stops, fewer shares, same dollar risk
VOL_ATR_MODIFIERS = {
    "Compressed": 0.85,   # Tighter stops in low vol (dealers long gamma, market pinned)
    "Normal": 1.0,
    "Elevated": 1.25,     # Give it room to breathe
    "Stressed": 1.5,      # Massive stops to survive negative GEX whipsaws
}


def get_moving_averages(ticker: str) -> dict:
    """Fetch prior close + moving averages for a ticker via DataProvider."""
    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        hist = dp.get_bars(ticker, lookback_days=180)  # ~6 months
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
    except DataUnavailable as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def calculate_atr_stop(ticker: str, entry_price: float, conviction_tier: str, vol_regime: str = "Normal") -> dict:
    """
    Calculate ATR-based stop loss for a ticker.
    Stop distance scales with Conviction Tier AND Volatility Regime.
    
    Wider stops in high-vol (negative GEX) environments avoid whipsaw stops
    while the dollar-VaR math upstream reduces share count to keep risk flat.
    """
    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        hist = dp.get_bars(ticker, lookback_days=30)  # ~20 trading days
        if hist.empty or len(hist) < 14:
            return {"error": f"Insufficient data for {ticker} ({len(hist)} bars)"}

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

        # Dynamic stop expansion: Conviction * Volatility
        base_multiplier = ATR_MULTIPLIERS.get(conviction_tier, ATR_MULTIPLIERS["PASS"])
        vol_modifier = VOL_ATR_MODIFIERS.get(vol_regime, 1.0)
        final_multiplier = base_multiplier * vol_modifier

        stop_distance = final_multiplier * atr
        stop_price = entry_price - stop_distance
        stop_distance_pct = (stop_distance / entry_price) * 100

        return {
            "stop_price": round(stop_price, 2),
            "atr": round(atr, 4),
            "atr_multiplier": round(final_multiplier, 2),
            "stop_distance_pct": round(stop_distance_pct, 2),
            "stop_label": f"{round(final_multiplier, 2)}x ATR({round(atr, 2)})",
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

    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        all_tickers = [new_ticker] + current_positions

        # Fetch bars for each ticker and build a returns DataFrame
        closes_dict = {}
        for t in all_tickers:
            try:
                bars = dp.get_bars(t, lookback_days=90)
                if bars is not None and not bars.empty:
                    closes_dict[t] = bars["Close"]
            except DataUnavailable:
                continue

        if new_ticker not in closes_dict:
            # Can't get data for the candidate — FAIL-CLOSED
            print(f"  [Agent 4B] No bar data for {new_ticker} — FAIL-CLOSED (vetoing)")
            return True

        if len(closes_dict) < 2:
            # Only one ticker (no positions to compare against) — pass
            return False

        closes = pd.DataFrame(closes_dict)
        returns = closes.pct_change().tail(60)

        for pos in current_positions:
            if pos in returns.columns:
                corr = returns[new_ticker].corr(returns[pos], min_periods=20)
                # NaN means insufficient overlap or unaligned dates — FAIL-CLOSED
                if pd.isna(corr):
                    print(f"  [Agent 4B] CORRELATION NaN for {new_ticker} vs {pos} — FAIL-CLOSED (vetoing)")
                    return True
                if corr > threshold:
                    print(f"  [Agent 4B] CORRELATION VETO: {new_ticker} vs {pos} = {corr:.2f} (>{threshold})")
                    return True
        return False  # All correlations computed and below threshold
    except DataUnavailable as e:
        print(f"  [Agent 4B] Correlation data unavailable \u2014 FAIL-CLOSED (vetoing {new_ticker}): {e}")
        return True
    except Exception as e:
        print(f"  [Agent 4B] Correlation check failed \u2014 FAIL-CLOSED (vetoing {new_ticker}): {e}")
        return True  # Fail-closed: if we can't verify, assume correlated and veto


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
        broker = get_broker()
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
            atr_result = calculate_atr_stop(ticker, entry_price, "PASS", "Normal")
            if "error" not in atr_result:
                stop_price = atr_result["stop_price"]
                stop_source = "estimated_atr"
            else:
                # Fallback: 3% below entry
                stop_price = entry_price * 0.97
                stop_source = "fallback_3pct"

        # Risk = current equity at stake down to the stop, with 1.5x gap slippage multiplier.
        # Using current_price (not entry_price) because that's the actual capital at risk NOW.
        # The "house money" fallacy: unrealized gains ARE real money, not free.
        open_risk = shares * max(0.0, current_price - stop_price) * 1.5

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

    # Enforce minimum 1% stop distance floor to prevent infinite leverage on tight stops
    effective_stop_distance = max(stop_distance, entry * 0.01)
    shares_by_risk = int(risk_dollars // effective_stop_distance)

    # 4. Allocation cap (max position value as % of account)
    max_position_value = account_value * MAX_ALLOCATION_PCT
    shares_by_alloc = int(max_position_value // entry)

    shares = min(shares_by_risk, shares_by_alloc)
    if shares == 0:
        return {"shares": 0, "reason": "ZERO_SHARES_AFTER_CONSTRAINTS"}

    binding = "risk" if shares == shares_by_risk else "allocation"
    actual_risk = shares * effective_stop_distance

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
    account_value: float = None,
    live_tickers: list = None,
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
        account_value: live account equity. If None, fetches from Alpaca (fallback to ACCOUNT_SIZE).
    """
    regime_raw = directive.get("regime", "")
    vol_raw = directive.get("vol_regime", "")

    try:
        regime = normalize_regime(regime_raw)
        vol_regime = normalize_vol_regime(vol_raw)
    except ValueError as e:
        print(f"[Agent 4B] FATAL: {e}")
        return {
            "success": False,
            "agent": "risk_manager",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "trade_orders": [],
        }

    # DEFER short-circuit: no trades, no sizing, return clean halt
    if regime == "Defer":
        print("[Agent 4B] Regime=Defer — halting, no trades this session.")
        return {
            "success": True,
            "agent": "risk_manager",
            "timestamp": datetime.now().isoformat(),
            "trade_orders": [],
            "session_summary": {
                "total_trades": 0,
                "halted_reason": "DEFER",
                "session_risk_used": 0.0,
                "session_risk_budget": SESSION_RISK_BUDGET,
            },
            "modifiers_used": {"regime": regime, "vol_regime": vol_regime, "posture": "Hold"},
        }

    # Resolve account_value + buying_power: live broker → hardcoded fallback
    buying_power = None
    if account_value is None:
        try:
            broker_acct = get_broker().get_account_summary()
            account_value = float(broker_acct["equity"])
            buying_power = float(broker_acct.get("buying_power", account_value))
            print(f"[Agent 4B] Live equity: ${account_value:,.2f} | Buying Power: ${buying_power:,.2f}")
        except Exception as e:
            print(f"[Agent 4B] Could not fetch live equity ({e}) — falling back to ACCOUNT_SIZE=${ACCOUNT_SIZE}")
            account_value = float(ACCOUNT_SIZE)
            buying_power = float(ACCOUNT_SIZE)
    else:
        print(f"[Agent 4B] Using caller-passed equity: ${account_value:,.2f}")

    posture_info = POSTURE_TABLE[regime]  # Guaranteed to hit after normalize_regime
    posture = posture_info["posture"]

    print(f"[Agent 4B] Regime: {regime} | Vol: {vol_regime} | Posture: {posture}")
    print(f"[Agent 4B] Risk stack: BASE_RISK=${BASE_RISK} | MAX=${MAX_RISK_PER_TRADE} | MIN=${MIN_RISK_PER_TRADE}")

    trade_orders = []
    theme_tracker = {}
    # Seed with live portfolio tickers for correlation checks against existing positions
    accepted_tickers = live_tickers.copy() if live_tickers else []
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
            account_value=account_value,
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
        max_deployable = account_value * (1 - DRY_POWDER_FLOOR) - total_allocated - existing_exposure

        # Hard cap by actual broker buying power
        if buying_power is not None:
            actual_cash_available = buying_power - total_allocated
            max_deployable = min(max_deployable, actual_cash_available)

        if max_deployable <= 0:
            trade_orders.append(_reject_trade(ticker, "Insufficient cash/buying power available"))
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
            "pct_of_account": round(position_value / account_value * 100, 2),
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
              f"alloc {round(position_value/account_value*100, 1)}%, "
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
            "pct_deployed": round((total_allocated + existing_exposure) / account_value * 100, 2),
            "dry_powder_pct": round((1 - (total_allocated + existing_exposure) / account_value) * 100, 2),
            "account_value": round(account_value, 2),
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

    v3 field mapping (post-sizing refactor):
      order keys: shares, entry_price, stop_loss, stop_anchor_label,
                  position_value, pct_of_account, risk_budgeted, risk_actual,
                  risk_multiplier, stop_distance_pct, binding_constraint,
                  theme, conviction_tier, confirm_enhanced
      modifiers_used keys: regime, vol_regime, posture
      session_summary keys: total_trades, session_risk_used, session_risk_budget,
                            total_allocated, existing_exposure, pct_deployed,
                            dry_powder_pct, account_value
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
        f"🌍 Regime: {mods.get('regime', '?')} | Vol: {mods.get('vol_regime', '?')}",
        f"📋 Posture: {mods.get('posture', '?')}",
        f"💼 Account: ${summary.get('account_value', 0):,.2f}",
        f"",
    ]

    buy_orders = [o for o in orders if o.get("action") == "BUY"]
    skip_orders = [o for o in orders if o.get("action") in ("SKIP", "REJECTED")]

    if not buy_orders:
        lines.append("🚫 NO TRADES TODAY")
        if skip_orders:
            lines.append("")
            for s in skip_orders:
                lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        return "\n".join(lines)

    for i, order in enumerate(buy_orders, 1):
        lines.append(f"{'─'*30}")
        lines.append(f"TRADE #{i}: {order.get('ticker')}")
        lines.append(f"")
        lines.append(f"  Action:     BUY")
        lines.append(f"  Shares:     {order.get('shares')}")
        lines.append(f"  Entry:      ${order.get('entry_price', 0):.2f} (prior close)")
        lines.append(f"  Stop:       ${order.get('stop_loss', 0):.2f} ({order.get('stop_anchor_label', '')})")
        lines.append(f"  Stop Dist:  {order.get('stop_distance_pct', 0):.1f}%")
        lines.append(f"  Theme:      {order.get('theme', '?')}")
        lines.append(f"  Tier:       {order.get('conviction_tier', '?')} {'✨ ENHANCED' if order.get('confirm_enhanced') else ''}")
        lines.append(f"")
        lines.append(f"  💰 Position: ${order.get('position_value', 0):,.2f} ({order.get('pct_of_account', 0):.1f}% of account)")
        lines.append(f"  🎯 Risk:     ${order.get('risk_actual', 0):,.2f} (budgeted ${order.get('risk_budgeted', 0):,.2f})")
        lines.append(f"  📏 Bound:    {order.get('binding_constraint', '?')} | Risk mult: {order.get('risk_multiplier', 0):.3f}")
        lines.append(f"")

    if skip_orders:
        lines.append(f"{'─'*30}")
        lines.append(f"SKIPPED/REJECTED:")
        for s in skip_orders:
            lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        lines.append(f"")

    lines.append(f"{'─'*30}")
    lines.append(f"SESSION TOTALS:")
    lines.append(f"  Trades:       {summary.get('total_trades', 0)}")
    lines.append(f"  Risk Used:    ${summary.get('session_risk_used', 0):,.2f} / ${summary.get('session_risk_budget', 0):,.2f}")
    lines.append(f"  Allocated:    ${summary.get('total_allocated', 0):,.2f}")
    lines.append(f"  Deployed:     {summary.get('pct_deployed', 0):.1f}%")
    lines.append(f"  Dry Powder:   {summary.get('dry_powder_pct', 0):.1f}%")
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

    # Extract vol_regime for dynamic ATR stop widening
    vol_raw = directive.get("vol_regime", "Normal")
    try:
        vol_regime = normalize_vol_regime(vol_raw)
    except Exception:
        vol_regime = "Normal"
    print(f"[Agent 4] Vol regime: {vol_regime} (ATR modifier: {VOL_ATR_MODIFIERS.get(vol_regime, 1.0)}x)")

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

        # Calculate ATR-based stop with vol regime modifier
        atr_result = calculate_atr_stop(ticker, entry_price, conviction_tier, vol_regime)
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

    # Fetch existing exposure + live tickers for correlation checks
    live_tickers = []
    try:
        broker = get_broker()
        open_positions = broker.get_positions()
        existing_exposure = sum(float(p.get("market_value", 0)) for p in open_positions)
        live_tickers = [p["ticker"] for p in open_positions]
        print(f"[Agent 4] Existing exposure: ${existing_exposure:,.2f} ({len(live_tickers)} positions: {live_tickers})")
    except Exception as e:
        print(f"[Agent 4] Could not fetch exposure: {e} — assuming $0")
        existing_exposure = 0.0

    # Step 4B: Python multiplicative sizing
    print("[Agent 4B] Running position sizing math...")
    result_4b = run_agent4b(stop_anchors, directive, candidates, verifications,
                            existing_exposure=existing_exposure,
                            remaining_heat_budget=remaining_heat_budget,
                            live_tickers=live_tickers)

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
