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

# Thread-safe rate limiter: free tier = 5 calls/min
import threading
_call_times: list = []
_rate_lock = threading.Lock()
RATE_LIMIT = 5
RATE_WINDOW = 60  # seconds


def _rate_limit():
    """Thread-safe rate limiter for free tier (5 calls/min)."""
    global _call_times
    with _rate_lock:
        now = time.time()
        _call_times = [t for t in _call_times if now - t < RATE_WINDOW]
        if len(_call_times) >= RATE_LIMIT:
            wait = RATE_WINDOW - (now - _call_times[0]) + 0.5
            if wait > 0:
                print(f"[Massive] Rate limit reached \u2014 waiting {wait:.1f}s")
                _rate_lock.release()
                time.sleep(wait)
                _rate_lock.acquire()
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


# ─── Local Technical Calculations (no API calls) ────────────────────

def calculate_technicals_local(ticker: str, period: str = "6mo") -> dict:
    """
    Calculate technical indicators locally using yfinance + pandas.
    Zero API calls to Massive — no rate limit concerns.

    Downloads historical bars from yfinance and computes:
    - SMA 10, 20, 50
    - EMA 20
    - RSI 14
    - MACD (12, 26, 9)

    Args:
        ticker: Stock symbol (e.g. "SPY")
        period: yfinance period string ("1mo", "3mo", "6mo", "1y", "2y")

    Returns:
        dict with all indicators, or dict with "error" key on failure.
    """
    import yfinance as yf
    import pandas as pd

    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    except Exception as e:
        return {"ticker": ticker, "error": f"yfinance download failed: {e}", "source": "local_calculation"}

    if df.empty or len(df) < 50:
        return {"ticker": ticker, "error": f"Insufficient data ({len(df)} bars, need >=50)", "source": "local_calculation"}

    # Flatten MultiIndex columns if yfinance returns them (e.g. ("Close", "SPY"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    closes = df["Close"].astype(float)

    # ── SMA ──
    sma_10 = closes.rolling(window=10).mean()
    sma_20 = closes.rolling(window=20).mean()
    sma_50 = closes.rolling(window=50).mean()

    # ── EMA ──
    ema_20 = closes.ewm(span=20, adjust=False).mean()

    # ── RSI 14 ──
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # ── MACD (12, 26, 9) ──
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    # ── Extract latest values ──
    last_close = round(float(closes.iloc[-1]), 2)
    cur_sma_10 = round(float(sma_10.iloc[-1]), 4) if pd.notna(sma_10.iloc[-1]) else None
    cur_sma_20 = round(float(sma_20.iloc[-1]), 4) if pd.notna(sma_20.iloc[-1]) else None
    cur_sma_50 = round(float(sma_50.iloc[-1]), 4) if pd.notna(sma_50.iloc[-1]) else None
    cur_ema_20 = round(float(ema_20.iloc[-1]), 4) if pd.notna(ema_20.iloc[-1]) else None
    cur_rsi = round(float(rsi.iloc[-1]), 2) if pd.notna(rsi.iloc[-1]) else None
    cur_macd = round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None
    cur_signal = round(float(signal_line.iloc[-1]), 4) if pd.notna(signal_line.iloc[-1]) else None
    cur_hist = round(float(histogram.iloc[-1]), 4) if pd.notna(histogram.iloc[-1]) else None

    # ── RSI classification ──
    rsi_signal = "neutral"
    if cur_rsi is not None:
        if cur_rsi >= 70:
            rsi_signal = "overbought"
        elif cur_rsi >= 60:
            rsi_signal = "bullish"
        elif cur_rsi <= 30:
            rsi_signal = "oversold"
        elif cur_rsi <= 40:
            rsi_signal = "bearish"

    # ── MACD classification ──
    macd_trend = "neutral"
    if cur_hist is not None and cur_macd is not None and cur_signal is not None:
        if cur_hist > 0 and cur_macd > cur_signal:
            macd_trend = "bullish"
        elif cur_hist < 0 and cur_macd < cur_signal:
            macd_trend = "bearish"

    # ── MACD crossover detection ──
    macd_crossover = None
    if len(histogram) >= 2 and pd.notna(histogram.iloc[-1]) and pd.notna(histogram.iloc[-2]):
        prev_hist = float(histogram.iloc[-2])
        curr_hist = float(histogram.iloc[-1])
        if prev_hist <= 0 < curr_hist:
            macd_crossover = "bullish_crossover"
        elif prev_hist >= 0 > curr_hist:
            macd_crossover = "bearish_crossover"

    # ── Price vs MAs ──
    price_vs_sma20 = None
    price_vs_sma50 = None
    if cur_sma_20 is not None:
        price_vs_sma20 = "above" if last_close > cur_sma_20 else "below"
    if cur_sma_50 is not None:
        price_vs_sma50 = "above" if last_close > cur_sma_50 else "below"

    return {
        "ticker": ticker,
        "sma_10": cur_sma_10,
        "sma_20": cur_sma_20,
        "sma_50": cur_sma_50,
        "ema_20": cur_ema_20,
        "rsi_14": cur_rsi,
        "rsi_signal": rsi_signal,
        "macd": {"macd_line": cur_macd, "signal_line": cur_signal, "histogram": cur_hist},
        "macd_trend": macd_trend,
        "macd_crossover": macd_crossover,
        "last_close": last_close,
        "price_vs_sma20": price_vs_sma20,
        "price_vs_sma50": price_vs_sma50,
        "source": "local_calculation",
    }


def calculate_technicals_batch(tickers: list, period: str = "6mo") -> dict:
    """
    Calculate technical indicators locally for multiple tickers.
    No API calls — runs entirely off yfinance historical data + pandas.

    Args:
        tickers: List of stock symbols
        period: yfinance period string

    Returns:
        Dict keyed by ticker symbol, each value is the output of calculate_technicals_local().
    """
    results = {}
    for ticker in tickers:
        results[ticker] = calculate_technicals_local(ticker, period=period)
    return results


def format_technicals_for_prompt(technicals: dict) -> str:
    """Format technical analysis data for agent prompts.
    Handles both API-based format and local calculation format."""
    t = technicals

    # Resolve price — API uses 'price', local uses 'last_close'
    price = t.get('price') or t.get('last_close', '?')

    # Resolve MACD fields — local wraps them in a dict, API puts them at top level
    macd_data = t.get('macd')
    if isinstance(macd_data, dict):
        macd_val = macd_data.get('macd_line', 'N/A')
        signal_val = macd_data.get('signal_line', 'N/A')
        hist_val = macd_data.get('histogram', 'N/A')
    else:
        macd_val = macd_data if macd_data is not None else 'N/A'
        signal_val = t.get('macd_signal', 'N/A')
        hist_val = t.get('macd_histogram', 'N/A')

    lines = [
        f"TECHNICAL ANALYSIS: {t['ticker']}",
        f"  Price: ${price}",
        f"  SMA(10): {t.get('sma_10', 'N/A')}",
        f"  SMA(20): {t.get('sma_20', 'N/A')} ({t.get('price_vs_sma20', '?')})",
        f"  SMA(50): {t.get('sma_50', 'N/A')} ({t.get('price_vs_sma50', '?')})",
        f"  EMA(20): {t.get('ema_20', 'N/A')}",
        f"  RSI(14): {t.get('rsi_14', 'N/A')} ({t.get('rsi_signal', '?')})",
        f"  MACD: {macd_val} | Signal: {signal_val} | Hist: {hist_val}",
        f"  MACD Trend: {t.get('macd_trend', '?')} | Crossover: {t.get('macd_crossover', 'none')}",
    ]
    return "\n".join(lines)


# ─── Macro / Economy (FREE — Schwab doesn't have these) ─────────────

def fetch_treasury_yields(limit: int = 5) -> dict:
    """
    Fetch U.S. Treasury yield curve data.
    Returns yields for 1mo, 3mo, 6mo, 1yr, 2yr, 3yr, 5yr, 7yr, 10yr, 20yr, 30yr.
    Data back to 1962. Included in ALL plans (including free).
    """
    data = _get("/fed/v1/treasury-yields", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No treasury yield data"}

    latest = results[0]
    return {
        "date": latest.get("date"),
        "yields": {
            "1mo": latest.get("yield_1_month"),
            "3mo": latest.get("yield_3_month"),
            "6mo": latest.get("yield_6_month"),
            "1yr": latest.get("yield_1_year"),
            "2yr": latest.get("yield_2_year"),
            "3yr": latest.get("yield_3_year"),
            "5yr": latest.get("yield_5_year"),
            "7yr": latest.get("yield_7_year"),
            "10yr": latest.get("yield_10_year"),
            "20yr": latest.get("yield_20_year"),
            "30yr": latest.get("yield_30_year"),
        },
        "spread_2s10s": round(latest.get("yield_10_year", 0) - latest.get("yield_2_year", 0), 2) if latest.get("yield_10_year") and latest.get("yield_2_year") else None,
        "spread_3mo10yr": round(latest.get("yield_10_year", 0) - latest.get("yield_3_month", 0), 2) if latest.get("yield_10_year") and latest.get("yield_3_month") else None,
        "history": [
            {
                "date": r.get("date"),
                "2yr": r.get("yield_2_year"),
                "10yr": r.get("yield_10_year"),
                "30yr": r.get("yield_30_year"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_inflation(limit: int = 5) -> dict:
    """
    Fetch U.S. inflation indicators: CPI, Core CPI, PCE, Core PCE, PCE Spending.
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/inflation", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No inflation data"}

    latest = results[0]

    # Calculate YoY CPI change if we have enough history
    yoy_cpi = None
    if len(results) >= 2:
        # Find a result ~12 months back
        for r in results:
            if r.get("cpi") and latest.get("cpi"):
                yoy_cpi = round((latest["cpi"] - r["cpi"]) / r["cpi"] * 100, 2)
                break  # Just use the oldest in our result set as approximation

    return {
        "date": latest.get("date"),
        "cpi": latest.get("cpi"),
        "cpi_core": latest.get("cpi_core"),
        "pce": latest.get("pce"),
        "pce_core": latest.get("pce_core"),
        "pce_spending": latest.get("pce_spending"),
        "history": [
            {
                "date": r.get("date"),
                "cpi": r.get("cpi"),
                "cpi_core": r.get("cpi_core"),
                "pce": r.get("pce"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_labor_market(limit: int = 5) -> dict:
    """
    Fetch U.S. labor market indicators: unemployment, participation, earnings, JOLTS.
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/labor-market", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No labor market data"}

    latest = results[0]
    return {
        "date": latest.get("date"),
        "unemployment_rate": latest.get("unemployment_rate"),
        "labor_force_participation": latest.get("labor_force_participation_rate"),
        "avg_hourly_earnings": latest.get("avg_hourly_earnings"),
        "job_openings": latest.get("job_openings"),
        "history": [
            {
                "date": r.get("date"),
                "unemployment": r.get("unemployment_rate"),
                "participation": r.get("labor_force_participation_rate"),
                "earnings": r.get("avg_hourly_earnings"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_inflation_expectations(limit: int = 5) -> dict:
    """
    Fetch U.S. inflation expectations (forward-looking).
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/inflation-expectations", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No inflation expectations data"}

    return {
        "date": results[0].get("date"),
        "latest": results[0],
        "history": results,
        "source": "massive",
    }


def fetch_macro_snapshot() -> dict:
    """
    Fetch a complete macro snapshot in 4 API calls:
    treasury yields + inflation + labor market + inflation expectations.

    This is the macro enrichment layer for Agent 1 (Macro Director).
    Schwab doesn't offer ANY of this — it's Massive's unique value.

    Rate limit note: This uses 4 of your 5 free calls/minute.
    """
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "source": "massive_macro",
    }

    snapshot["treasury_yields"] = fetch_treasury_yields(limit=5)
    snapshot["inflation"] = fetch_inflation(limit=5)
    snapshot["labor_market"] = fetch_labor_market(limit=5)
    snapshot["inflation_expectations"] = fetch_inflation_expectations(limit=3)

    return snapshot


def format_macro_for_prompt(macro: dict) -> str:
    """
    Format macro snapshot data for agent prompts.
    Designed for Agent 1 (Macro Director) consumption.
    """
    lines = ["MACRO ENVIRONMENT SNAPSHOT"]
    lines.append(f"  Timestamp: {macro.get('timestamp', '?')}")

    # Treasury Yields
    ty = macro.get("treasury_yields", {})
    if "error" not in ty:
        y = ty.get("yields", {})
        lines.append(f"\nTREASURY YIELDS ({ty.get('date', '?')})")
        _y = lambda k: f"{y[k]}%" if y.get(k) is not None else "N/A"
        lines.append(f"  Short: 1mo={_y('1mo')} | 3mo={_y('3mo')} | 6mo={_y('6mo')}")
        lines.append(f"  Mid:   1yr={_y('1yr')} | 2yr={_y('2yr')} | 5yr={_y('5yr')}")
        lines.append(f"  Long:  10yr={_y('10yr')} | 20yr={_y('20yr')} | 30yr={_y('30yr')}")
        lines.append(f"  2s10s spread: {ty.get('spread_2s10s')}% | 3mo10yr spread: {ty.get('spread_3mo10yr')}%")
        if ty.get('spread_2s10s') is not None and ty['spread_2s10s'] < 0:
            lines.append("  ⚠️ INVERTED YIELD CURVE (2s10s) — recession signal")
    else:
        lines.append(f"\nTREASURY YIELDS: {ty.get('error', 'unavailable')}")

    # Inflation
    inf = macro.get("inflation", {})
    if "error" not in inf:
        lines.append(f"\nINFLATION ({inf.get('date', '?')})")
        lines.append(f"  CPI: {inf.get('cpi', 'N/A')} | Core CPI: {inf.get('cpi_core', 'N/A')}")
        if inf.get('pce') is not None:
            lines.append(f"  PCE: {inf['pce']} | Core PCE: {inf.get('pce_core', 'N/A')}")
        if inf.get('pce_spending') is not None:
            lines.append(f"  PCE Spending: ${inf['pce_spending']}B")
    else:
        lines.append(f"\nINFLATION: {inf.get('error', 'unavailable')}")

    # Labor Market
    lm = macro.get("labor_market", {})
    if "error" not in lm:
        lines.append(f"\nLABOR MARKET ({lm.get('date', '?')})")
        lines.append(f"  Unemployment: {lm.get('unemployment_rate')}%")
        lines.append(f"  Labor Force Participation: {lm.get('labor_force_participation')}%")
        lines.append(f"  Avg Hourly Earnings: ${lm.get('avg_hourly_earnings')}")
        if lm.get('job_openings'):
            lines.append(f"  Job Openings (JOLTS): {lm['job_openings']:,.0f}K")
    else:
        lines.append(f"\nLABOR MARKET: {lm.get('error', 'unavailable')}")

    return "\n".join(lines)


# ─── Ticker Reference & Fundamentals (FREE) ─────────────────────────

def fetch_ticker_details(ticker: str) -> dict:
    """
    Fetch comprehensive ticker details: name, market cap, sector, description, etc.
    Included in ALL plans (including free).
    """
    data = _get(f"/v3/reference/tickers/{ticker}")
    if "error" in data:
        return data

    r = data.get("results", {})
    return {
        "ticker": r.get("ticker"),
        "name": r.get("name"),
        "market_cap": r.get("market_cap"),
        "description": r.get("description"),
        "sector": r.get("sic_description"),
        "employees": r.get("total_employees"),
        "homepage": r.get("homepage_url"),
        "list_date": r.get("list_date"),
        "shares_outstanding": r.get("share_class_shares_outstanding"),
        "source": "massive",
    }


def fetch_dividends(ticker: str, limit: int = 4) -> dict:
    """
    Fetch recent dividend history for a ticker.
    Included in ALL plans (including free).
    """
    data = _get("/v3/reference/dividends", params={"ticker": ticker, "limit": limit, "sort": "ex_dividend_date", "order": "desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    return {
        "ticker": ticker,
        "dividends": [
            {
                "ex_date": d.get("ex_dividend_date"),
                "pay_date": d.get("pay_date"),
                "amount": d.get("cash_amount"),
                "frequency": d.get("frequency"),
            }
            for d in results
        ],
        "annual_dividend": sum(d.get("cash_amount", 0) for d in results[:4]) if len(results) >= 4 else None,
        "source": "massive",
    }


def fetch_financials(ticker: str, limit: int = 2) -> dict:
    """
    Fetch company financial statements (income statement, balance sheet).
    Included in ALL plans (including free).
    """
    data = _get("/vX/reference/financials", params={"ticker": ticker, "limit": limit})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"ticker": ticker, "error": "No financial data"}

    summaries = []
    for r in results:
        fi = r.get("financials", {})
        income = fi.get("income_statement", {})
        balance = fi.get("balance_sheet", {})

        summaries.append({
            "period": f"{r.get('fiscal_period', '?')} {r.get('fiscal_year', '?')}",
            "revenue": income.get("revenues", {}).get("value"),
            "net_income": income.get("net_income_loss", {}).get("value"),
            "gross_profit": income.get("gross_profit", {}).get("value"),
            "total_assets": balance.get("assets", {}).get("value"),
            "total_liabilities": balance.get("liabilities", {}).get("value"),
            "equity": balance.get("equity", {}).get("value"),
        })

    return {
        "ticker": ticker,
        "financials": summaries,
        "source": "massive",
    }


def fetch_market_status() -> dict:
    """
    Fetch current market status (open/closed) for all exchanges.
    Included in ALL plans (including free).
    """
    data = _get("/v1/marketstatus/now")
    if "error" in data:
        return data

    return {
        "market": data.get("market", "unknown"),
        "early_hours": data.get("earlyHours"),
        "after_hours": data.get("afterHours"),
        "exchanges": data.get("exchanges", {}),
        "currencies": data.get("currencies", {}),
        "source": "massive",
    }


# ─── Crypto (FREE) ──────────────────────────────────────────────────

def fetch_crypto_bars(pair: str = "X:BTCUSD", days: int = 30) -> dict:
    """
    Fetch historical OHLCV bars for a crypto pair.
    Free tier. Schwab doesn't have crypto at all.
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data = _get(f"/v2/aggs/ticker/{pair}/range/1/day/{start}/{end}", params={"sort": "asc", "limit": 5000})
    if "error" in data:
        return data

    results = data.get("results", [])
    return {
        "pair": pair,
        "bars": [
            {
                "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d"),
                "open": round(bar["o"], 2),
                "high": round(bar["h"], 2),
                "low": round(bar["l"], 2),
                "close": round(bar["c"], 2),
                "volume": bar.get("v", 0),
                "vwap": round(bar["vw"], 2) if bar.get("vw") else None,
            }
            for bar in results
        ],
        "count": len(results),
        "source": "massive",
    }


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

    # --- Wait for rate limit reset (free tier = 5 calls/min) ---
    print("\n--- Waiting 65s for rate limit reset to test macro endpoints ---")
    time.sleep(65)

    # Test 5: Macro snapshot
    print("\n6. Treasury Yields:")
    ty = fetch_treasury_yields(limit=3)
    if "error" not in ty:
        print(f"   Date: {ty['date']}")
        print(f"   2yr={ty['yields']['2yr']}% | 10yr={ty['yields']['10yr']}% | 30yr={ty['yields']['30yr']}%")
        print(f"   2s10s spread: {ty['spread_2s10s']}%")
    else:
        print(f"   ERROR: {ty}")

    print("\n7. Inflation:")
    inf = fetch_inflation(limit=3)
    if "error" not in inf:
        print(f"   Date: {inf['date']}")
        print(f"   CPI: {inf['cpi']} | Core CPI: {inf['cpi_core']}")
    else:
        print(f"   ERROR: {inf}")

    print("\n8. Labor Market:")
    lm = fetch_labor_market(limit=3)
    if "error" not in lm:
        print(f"   Date: {lm['date']}")
        print(f"   Unemployment: {lm['unemployment_rate']}% | Participation: {lm['labor_force_participation']}%")
        print(f"   Avg Hourly Earnings: ${lm['avg_hourly_earnings']}")
    else:
        print(f"   ERROR: {lm}")

    print("\n9. Ticker Details (AAPL):")
    td = fetch_ticker_details("AAPL")
    if "error" not in td:
        print(f"   {td['name']} | Market Cap: ${td['market_cap']/1e9:.1f}B | Employees: {td['employees']:,}")
    else:
        print(f"   ERROR: {td}")

    print("\n10. Crypto BTC-USD (7 days):")
    btc = fetch_crypto_bars("X:BTCUSD", days=7)
    if "error" not in btc:
        for bar in btc["bars"][-3:]:
            print(f"   {bar['date']}: C=${bar['close']:,.0f}")
    else:
        print(f"   ERROR: {btc}")

    print("\n✅ Massive Market Data module working (all endpoints)!")
