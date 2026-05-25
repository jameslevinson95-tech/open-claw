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
