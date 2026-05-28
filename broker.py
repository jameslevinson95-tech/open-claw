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
    StopOrderRequest,
    ReplaceOrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus


def _cross_reference_price(ticker: str, prior_close: float, suspect_price: float):
    """
    Cross-reference a suspect broker quote against today's actual opening print or live tape.
    If the stock legitimately gapped up on news, today's tape will verify the live quote is real.
    Returns a trusted price, or None if no reliable price can be found.
    """
    import yfinance as yf

    trusted = None
    try:
        # Fetch today's 1-minute intraday tape
        today_data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not today_data.empty:
            # Handle pandas multi-index if necessary
            if hasattr(today_data.columns, 'levels') and len(today_data.columns.levels) > 1:
                today_open = float(today_data["Open"][ticker].iloc[0])
                current_tape = float(today_data["Close"][ticker].iloc[-1])
            else:
                today_open = float(today_data["Open"].iloc[0])
                current_tape = float(today_data["Close"].iloc[-1])

            # If the suspect broker price is within 1.5% of today's actual open or current tape,
            # it is a legitimate gap/breakout quote, not an anomaly.
            dev_from_open = abs(suspect_price - today_open) / today_open if today_open > 0 else 999
            dev_from_current = abs(suspect_price - current_tape) / current_tape if current_tape > 0 else 999

            if dev_from_open < 0.015 or dev_from_current < 0.015:
                print(f"  [CrossRef] \u2705 Real Breakout: Broker quote ${suspect_price:.2f} verified by today's tape (Open: ${today_open:.2f}, Live: ${current_tape:.2f}).")
                trusted = suspect_price
            else:
                print(f"  [CrossRef] \ud83d\udeab Anomaly Confirmed: Broker quote ${suspect_price:.2f} diverges wildly from today's tape (Open: ${today_open:.2f}, Live: ${current_tape:.2f}).")
                trusted = current_tape  # Fallback to the live yfinance tape
        else:
            print(f"  [CrossRef] No intraday tape available to verify {ticker}.")
    except Exception as e:
        print(f"  [CrossRef] yfinance tape verification failed: {e}")

    return trusted


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

    def execute_tear_sheet(self, trade_orders: list, max_gap_pct: float = 0.02) -> list:
        """
        Execute BUY orders from Agent 4B's tear sheet with live re-pricing.

        Uses live quotes at execution time to:
        1. Reject orders if the stock gapped up > max_gap_pct from planned entry
        2. Dynamically recalculate share count based on live price and risk budget
        3. Submit limit orders pegged to live ask + 0.15% (micro-slippage allowance)

        This prevents the gap-up sizing explosion where stale share counts from
        8:17 AM (based on yesterday's close) silently blow past MAX_RISK_PER_TRADE.

        Returns list of fill results.
        """
        fills = []

        # Collect BUY tickers for batch quote fetch
        buy_tickers = [o["ticker"] for o in trade_orders if o.get("action") == "BUY"]

        # Fetch live quotes right before execution
        live_quotes = {}
        if buy_tickers:
            try:
                from market_data import fetch_latest_quotes
                live_quotes = fetch_latest_quotes(buy_tickers)
                print(f"  [Broker] Live quotes fetched for {len(live_quotes)} tickers")
            except Exception as e:
                print(f"  [Broker] WARNING: Could not fetch live quotes ({e}), using planned prices")

        for order in trade_orders:
            if order.get("action") != "BUY":
                fills.append({
                    "ticker": order.get("ticker", "?"),
                    "status": "skipped",
                    "reason": order.get("reason", order.get("action", "not a BUY")),
                })
                continue

            ticker = order["ticker"]
            planned_entry = order["entry_price"]
            stop_price = order.get("stop_loss")
            risk_budget = order.get("risk_budgeted", order.get("risk_actual", 0))
            planned_shares = order["shares"]

            try:
                # Get live price — fall back to planned entry if quotes unavailable
                quote = live_quotes.get(ticker, {})
                live_ask = quote.get("ask") or quote.get("mid") or 0

                if live_ask > 0 and stop_price and stop_price > 0 and risk_budget > 0:
                    # === LIVE RE-PRICING MODE ===

                    # 0. Quote anomaly detection: if live price deviates beyond
                    #    the gap threshold, cross-reference before rejecting.
                    #    Pre-market Alpaca IEX quotes can be garbage on thin
                    #    liquidity (e.g. BAC showing $54.80 when real = $51.60).
                    deviation_pct = abs(live_ask - planned_entry) / planned_entry
                    if deviation_pct > max_gap_pct:
                        print(f"  [Broker] ⚠️ {ticker}: Alpaca quote ${live_ask:.2f} deviates {deviation_pct*100:.1f}% from prior close ${planned_entry:.2f} — cross-referencing...")
                        verified_price = _cross_reference_price(ticker, planned_entry, live_ask)
                        if verified_price is not None:
                            print(f"  [Broker] ✅ {ticker}: Cross-reference price ${verified_price:.2f} — using instead of Alpaca ${live_ask:.2f}")
                            live_ask = verified_price
                        else:
                            print(f"  [Broker] 🚫 {ticker}: Quote anomaly confirmed — no reliable price available, skipping")
                            fills.append({
                                "ticker": ticker,
                                "status": "rejected",
                                "reason": f"Quote anomaly: Alpaca ${live_ask:.2f} vs prior close ${planned_entry:.2f} ({deviation_pct*100:.1f}% deviation), cross-reference failed",
                            })
                            continue

                    # 1. Gap-up protection: reject if price moved too far
                    gap_pct = (live_ask - planned_entry) / planned_entry
                    if gap_pct > max_gap_pct:
                        msg = f"Gapped up {gap_pct*100:.1f}% (Planned: ${planned_entry}, Live: ${live_ask})"
                        print(f"  [Broker] 🚫 REJECTED {ticker}: {msg}")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Gap up exceeded {max_gap_pct*100:.0f}%",
                            "planned_entry": planned_entry,
                            "live_ask": live_ask,
                            "gap_pct": round(gap_pct * 100, 2),
                        })
                        continue

                    # 2. Dynamic share recalculation based on live risk per share
                    live_risk_per_share = live_ask - stop_price
                    if live_risk_per_share <= 0:
                        print(f"  [Broker] 🚫 REJECTED {ticker}: Live ask ${live_ask:.2f} at or below stop ${stop_price:.2f}")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Live price ${live_ask:.2f} at or below stop ${stop_price:.2f}",
                        })
                        continue

                    live_shares = int(risk_budget // live_risk_per_share)
                    if live_shares <= 0:
                        print(f"  [Broker] 🚫 REJECTED {ticker}: Zero shares after live re-sizing")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": "Zero shares after live re-sizing",
                        })
                        continue

                    # 3. Limit order pegged to ask + 0.15% (micro-slippage allowance)
                    limit_price = round(live_ask * 1.0015, 2)
                    shares = live_shares
                    pricing_mode = "live"

                    if shares != planned_shares:
                        print(f"  [Broker] 📐 {ticker}: Re-sized {planned_shares} → {shares} shares (live ask ${live_ask} vs planned ${planned_entry})")

                else:
                    # === FALLBACK: PLANNED PRICE MODE ===
                    # No live quotes available — use planned entry with 1.5% slippage cap
                    limit_price = round(planned_entry * 1.015, 2)
                    shares = planned_shares
                    pricing_mode = "planned"
                    print(f"  [Broker] ⚠️ {ticker}: No live quote — using planned price with 1.5% limit cap")

                # Submit order with OTO stop-loss
                if stop_price and stop_price > 0:
                    req = LimitOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price,
                        order_class="oto",
                        stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
                    )
                else:
                    req = LimitOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price,
                    )

                result = self.client.submit_order(req)
                fills.append({
                    "ticker": ticker,
                    "status": "submitted",
                    "order_id": str(result.id),
                    "shares": shares,
                    "planned_shares": planned_shares,
                    "order_type": "limit",
                    "limit_price": limit_price,
                    "pricing_mode": pricing_mode,
                    "live_ask": live_ask if live_ask > 0 else None,
                    "planned_entry": planned_entry,
                    "risk_budget": risk_budget,
                    "submitted_at": result.submitted_at.isoformat() if result.submitted_at else "",
                })
                print(f"  [Broker] ✅ BUY {shares} {ticker} @ limit ${limit_price} ({pricing_mode}) — submitted ({result.id})")

            except Exception as e:
                fills.append({
                    "ticker": ticker,
                    "status": "error",
                    "error": str(e),
                })
                print(f"  [Broker] ❌ ERROR on {ticker}: {e}")

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
                result = self.client.close_position(ticker, cancel_orders=True)
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

    def update_stop_order(self, ticker: str, new_stop_price: float) -> dict:
        """
        Update the existing stop order for a position to a tighter stop price.
        Used by Agent 5 when trailing stops tighten (new_stop > original_stop).

        Strategy:
        1. Find the open stop/stop_limit order for this ticker
        2. Replace it in-place via replace_order_by_id
        3. If replace fails, fall back to submit-new-then-cancel-old
        """
        new_stop_price = round(new_stop_price, 2)
        try:
            # Find existing stop order for this ticker
            req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                limit=100,
            )
            open_orders = self.client.get_orders(req)
            stop_order = None
            for o in open_orders:
                if o.symbol == ticker and o.stop_price is not None and o.side == OrderSide.SELL:
                    stop_order = o
                    break

            if stop_order is None:
                print(f"  [Broker] No existing stop order found for {ticker}")
                return {
                    "ticker": ticker,
                    "action": "update_stop",
                    "status": "no_stop_order",
                }

            old_stop_price = float(stop_order.stop_price)
            print(f"  [Broker] Updating stop for {ticker}: ${old_stop_price} → ${new_stop_price} (order {stop_order.id})")

            # Attempt 1: Replace in-place
            try:
                replace_req = ReplaceOrderRequest(stop_price=new_stop_price)
                replaced = self.client.replace_order_by_id(
                    order_id=str(stop_order.id),
                    order_data=replace_req,
                )
                print(f"  [Broker] Stop replaced successfully for {ticker} → ${new_stop_price} (new order {replaced.id})")
                return {
                    "ticker": ticker,
                    "action": "update_stop",
                    "status": "replaced",
                    "old_stop": old_stop_price,
                    "new_stop": new_stop_price,
                    "order_id": str(replaced.id),
                }
            except Exception as replace_err:
                print(f"  [Broker] Replace failed for {ticker} ({replace_err}), falling back to cancel+resubmit")

            # Attempt 2: Submit new stop first, then cancel old
            # Submit first so we're never unprotected
            new_req = StopOrderRequest(
                symbol=ticker,
                qty=int(stop_order.qty),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                type="stop",
                stop_price=new_stop_price,
            )
            new_order = self.client.submit_order(new_req)
            print(f"  [Broker] New stop submitted for {ticker} @ ${new_stop_price} (order {new_order.id})")

            # Now cancel the old one
            try:
                self.client.cancel_order_by_id(str(stop_order.id))
                print(f"  [Broker] Old stop cancelled for {ticker} (order {stop_order.id})")
            except Exception as cancel_err:
                # Old order might already be cancelled/filled — not fatal
                print(f"  [Broker] Warning: couldn't cancel old stop for {ticker} ({cancel_err})")

            return {
                "ticker": ticker,
                "action": "update_stop",
                "status": "resubmitted",
                "old_stop": old_stop_price,
                "new_stop": new_stop_price,
                "old_order_id": str(stop_order.id),
                "new_order_id": str(new_order.id),
            }

        except Exception as e:
            print(f"  [Broker] ERROR updating stop for {ticker}: {e}")
            return {
                "ticker": ticker,
                "action": "update_stop",
                "status": "error",
                "error": str(e),
            }

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
                new_stop = d.get("new_stop")
                original_stop = d.get("original_stop")
                if new_stop and original_stop and new_stop > original_stop:
                    # Trailing stop tightened — push to Alpaca
                    result = self.update_stop_order(ticker, new_stop)
                    result["action"] = "HOLD_STOP_TIGHTENED"
                    results.append(result)
                else:
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
