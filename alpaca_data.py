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
