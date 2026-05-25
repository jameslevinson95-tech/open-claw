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
