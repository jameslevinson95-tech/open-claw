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
            # FAIL-CLOSED: reject if we can't verify VWAP
            order["vwap_note"] = "No intraday data — VWAP check FAILED (fail-closed)"
            order["reject_reason"] = "VWAP unavailable — fail-closed"
            rejected.append(order)
            continue

        if vwap_data.get("error"):
            order["vwap_note"] = f"VWAP error: {vwap_data['error']} (fail-closed)"
            order["reject_reason"] = f"VWAP error: {vwap_data['error']}"
            rejected.append(order)
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
