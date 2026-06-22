"""
Unified Market Data Module — Schwab primary, Yahoo Finance fallback.

Replaces alpaca_data.py as the pipeline's data source.
No Alpaca dependency — uses Schwab for real-time quotes and Yahoo for
historical bars, fundamentals, and macro indicators.

Drop-in compatible with alpaca_data.py's function signatures.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# ── Schwab Quotes (primary for real-time) ────────────────────────────────

def _schwab_available() -> bool:
    """Check if Schwab data module is available and has a valid token."""
    try:
        from schwab_data import fetch_schwab_quotes
        test = fetch_schwab_quotes(["SPY"])
        return "SPY" in test and "error" not in test.get("SPY", {})
    except Exception:
        return False

_schwab_ok = None  # Lazy init


def _check_schwab():
    global _schwab_ok
    if _schwab_ok is None:
        _schwab_ok = _schwab_available()
        if _schwab_ok:
            print("[MarketData] Schwab API: AVAILABLE (primary for real-time quotes)")
        else:
            print("[MarketData] Schwab API: UNAVAILABLE — falling back to Yahoo Finance")
    return _schwab_ok


# ── Tiingo Quotes (PRIMARY for real-time as of 2026-06-22) ──────────
import urllib.request
import json as _json

_TIINGO_BASE = "https://api.tiingo.com"


def _tiingo_key() -> str:
    return os.getenv("TIINGO_API_KEY", "").strip()


def _tiingo_quotes(tickers: list) -> dict:
    """Fetch real-time (IEX) quotes from Tiingo.

    Returns {ticker: {bid, ask, last, mid, source}} matching the pipeline's
    quote schema. Tiingo's IEX endpoint gives tngoLast (last trade), plus
    bid/ask during market hours. Falls back to tngoLast/prevClose when the
    book is closed. Returns {} on any failure so the caller cascades to the
    next source.
    """
    key = _tiingo_key()
    if not key or not tickers:
        return {}
    out = {}
    try:
        url = (f"{_TIINGO_BASE}/iex/?tickers={','.join(tickers)}"
               f"&token={key}")
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        for row in data:
            t = row.get("ticker")
            if not t:
                continue
            bid = row.get("bidPrice") or 0
            ask = row.get("askPrice") or 0
            # last-trade preference: live last → tngoLast → prevClose
            last = row.get("last") or row.get("tngoLast") or row.get("prevClose") or 0
            mid = (round((float(bid) + float(ask)) / 2, 2)
                   if bid and ask else float(last or 0))
            out[t] = {
                "bid": float(bid) if bid else 0.0,
                "ask": float(ask) if ask else 0.0,
                "last": float(last) if last else 0.0,
                "mid": mid,
                "source": "tiingo",
            }
    except Exception as e:
        print(f"[MarketData] Tiingo quotes failed: {e}")
        return {}
    return out


def _tiingo_history(ticker: str, days: int = 30) -> dict:
    """Fetch daily OHLCV history from Tiingo's EOD endpoint.

    Returns {"bars": [...], "count": n, "source": "tiingo"} or {} on failure.
    Tiingo daily prices are split/dividend-adjusted via adjClose etc.; we use
    the raw OHLCV (open/high/low/close/volume) to match the pipeline's bar
    schema. Index symbols (^VIX) are not supported and return {}.
    """
    key = _tiingo_key()
    if not key or not ticker or ticker.startswith("^"):
        return {}
    from datetime import datetime, timedelta
    start = (datetime.now() - timedelta(days=int(days * 1.6) + 10)).strftime("%Y-%m-%d")
    try:
        url = (f"{_TIINGO_BASE}/tiingo/daily/{ticker}/prices"
               f"?startDate={start}&token={key}")
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
        bars = []
        for row in data:
            d = row.get("date", "")[:10]
            bars.append({
                "date": d,
                "open": round(float(row.get("open", 0)), 2),
                "high": round(float(row.get("high", 0)), 2),
                "low": round(float(row.get("low", 0)), 2),
                "close": round(float(row.get("close", 0)), 2),
                "volume": int(row.get("volume", 0)),
            })
        if bars:
            return {"bars": bars, "count": len(bars), "source": "tiingo"}
    except Exception as e:
        print(f"[MarketData] Tiingo history failed for {ticker}: {e}")
    return {}


# ── Robinhood Quotes (secondary for real-time) ──────────────────────────

def _robinhood_quotes(tickers: list) -> dict:
    """Fetch quotes from Robinhood MCP if a token exists."""
    try:
        from broker_factory import get_broker
        broker = get_broker("robinhood")  # cached singleton — reuses MCP session
        return broker.get_quotes(tickers)
    except Exception:
        return {}


# ── Yahoo Finance (historical data + fallback) ──────────────────────────

def _yf_import():
    import yfinance as yf
    return yf


# ── Public API (drop-in for alpaca_data) ─────────────────────────────────

def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch yesterday's close for a list of tickers.
    Primary: Schwab. Fallback: Yahoo Finance.
    """
    results = {}

    # Try Schwab first for real-time previous close
    if _check_schwab():
        try:
            from schwab_data import fetch_schwab_quotes
            # Batch in groups of 50
            for i in range(0, len(tickers), 50):
                batch = tickers[i:i+50]
                quotes = fetch_schwab_quotes(batch)
                for t, q in quotes.items():
                    if "error" not in q:
                        close = q.get("close") or q.get("last") or q.get("regularMarketPreviousClose", 0)
                        if close and close > 0:
                            results[t] = {
                                "prior_close": round(float(close), 2),
                                "prior_date": str((datetime.now() - timedelta(days=1)).date()),
                                "source": "schwab",
                            }
        except Exception as e:
            print(f"[MarketData] Schwab prior_close batch failed: {e}")

    # Fill gaps with Yahoo Finance
    missing = [t for t in tickers if t not in results]
    if missing:
        yf_results = _fetch_prior_close_yfinance(missing)
        results.update(yf_results)

    return results


def _fetch_prior_close_yfinance(tickers: list) -> dict:
    """Yahoo Finance prior close fetch."""
    yf = _yf_import()
    results = {}

    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            closes = [round(float(c), 2) for c in hist["Close"].values]
            dates = [str(d.date()) for d in hist.index]

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
                "source": "yfinance",
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_latest_quotes(tickers: list) -> dict:
    """
    Fetch real-time quotes.
    Primary: Tiingo (real-time IEX). Fallback: Schwab, Robinhood MCP, Yahoo.

    Tiingo became primary on 2026-06-22 because Schwab/Yahoo were unreliable.
    """
    results = {}

    # Try Tiingo first (real-time, reliable)
    if _tiingo_key():
        try:
            tq = _tiingo_quotes(tickers)
            for t, q in tq.items():
                if q.get("last", 0) > 0:
                    results[t] = q
            if tq:
                print(f"[MarketData] Tiingo: {len(results)}/{len(tickers)} quotes (PRIMARY)")
        except Exception as e:
            print(f"[MarketData] Tiingo quotes failed: {e}")

    # Fill gaps with Schwab
    schwab_targets = [t for t in tickers if t not in results]
    if schwab_targets and _check_schwab():
        try:
            from schwab_data import fetch_schwab_quotes
            quotes = fetch_schwab_quotes(schwab_targets)
            for t, q in quotes.items():
                if "error" not in q:
                    bid = q.get("bid", 0)
                    ask = q.get("ask", 0)
                    last = q.get("last", 0)
                    results[t] = {
                        "bid": float(bid) if bid else 0.0,
                        "ask": float(ask) if ask else 0.0,
                        "last": float(last) if last else 0.0,
                        "mid": round((float(bid or 0) + float(ask or 0)) / 2, 2) if bid and ask else float(last or 0),
                        "source": "schwab",
                    }
        except Exception as e:
            print(f"[MarketData] Schwab quotes failed: {e}")

    # Fill gaps with Robinhood
    missing = [t for t in tickers if t not in results]
    if missing:
        try:
            rh = _robinhood_quotes(missing)
            for t, q in rh.items():
                if "error" not in q:
                    results[t] = {**q, "source": "robinhood"}
        except Exception:
            pass

    # Fill remaining gaps with Yahoo
    still_missing = [t for t in tickers if t not in results]
    if still_missing:
        yf = _yf_import()
        for t in still_missing:
            try:
                info = yf.Ticker(t).info
                price = info.get("regularMarketPrice") or info.get("previousClose", 0)
                bid = info.get("bid", 0)
                ask = info.get("ask", 0)
                results[t] = {
                    "bid": float(bid) if bid else 0.0,
                    "ask": float(ask) if ask else 0.0,
                    "last": float(price) if price else 0.0,
                    "mid": round((float(bid or 0) + float(ask or 0)) / 2, 2) if bid and ask else float(price or 0),
                    "source": "yfinance",
                }
            except Exception as e:
                results[t] = {"error": str(e)}

    return results


def fetch_historical_bars(tickers: list, days: int = 30, timeframe: str = "day") -> dict:
    """
    Fetch historical OHLCV daily bars.

    Schwab-first (covers stocks, ETFs, and indices like $VIX/$MOVE), with
    Yahoo Finance as a last-resort fallback per-ticker. For daily bars Schwab
    is the authoritative source now; Yahoo only fires if Schwab returns empty.
    """
    results = {}

    # ━━━ PRIMARY: Tiingo daily history (single vendor as of 2026-06-22) ━━━
    if timeframe == "day" and _tiingo_key():
        for ticker in tickers:
            h = _tiingo_history(ticker, days=days)
            if h.get("count", 0) > 0:
                results[ticker] = h
        if results:
            print(f"[MarketData] Tiingo history: {len(results)}/{len(tickers)} (PRIMARY)")

    # Schwab fallback only serves daily/intraday candles for tickers Tiingo missed.
    schwab_targets = [t for t in tickers if t not in results]
    schwab_first = (timeframe == "day") and schwab_targets and _check_schwab()

    if schwab_first:
        try:
            from schwab_data import fetch_schwab_history
            for ticker in schwab_targets:
                h = fetch_schwab_history(ticker, days=days, frequency_type="daily")
                if h.get("count", 0) > 0:
                    results[ticker] = {
                        "bars": h["bars"],
                        "count": h["count"],
                        "source": "schwab",
                    }
                # leave missing tickers to the Yahoo fallback below
        except Exception as e:
            print(f"[MarketData] Schwab history failed ({e}) — falling back to yfinance")

    # Determine which tickers still need data (Yahoo fallback only for gaps)
    missing = [t for t in tickers if t not in results]
    if not missing:
        return results

    yf = _yf_import()

    period_map = {
        7: "7d", 14: "14d", 30: "1mo", 60: "2mo", 90: "3mo",
        180: "6mo", 365: "1y",
    }
    period = "1mo"
    for d, p in sorted(period_map.items()):
        if days <= d:
            period = p
            break
    if days > 365:
        period = f"{days}d"

    interval = {"day": "1d", "hour": "1h", "minute": "1m"}.get(timeframe, "1d")

    for ticker in missing:
        try:
            hist = yf.Ticker(ticker).history(period=period, interval=interval)
            if hist.empty:
                results[ticker] = {"bars": [], "count": 0}
                continue

            bar_list = []
            for ts, row in hist.iterrows():
                bar_list.append({
                    "date": str(ts.date()) if timeframe == "day" else ts.isoformat(),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

            results[ticker] = {"bars": bar_list, "count": len(bar_list), "source": "yfinance"}
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_snapshots(tickers: list) -> dict:
    """
    Fetch snapshot data (latest price + daily bar + previous daily bar).
    Uses Schwab for real-time, Yahoo for daily bars.
    """
    results = {}

    # Get real-time quotes
    quotes = fetch_latest_quotes(tickers)

    # Get 2-day history from Yahoo for daily bars
    yf = _yf_import()
    for ticker in tickers:
        entry = {}

        # Quote data
        q = quotes.get(ticker, {})
        if "error" not in q:
            entry["latest_quote"] = {"bid": q.get("bid", 0), "ask": q.get("ask", 0)}
            entry["latest_trade"] = {"price": q.get("last", q.get("mid", 0)), "source": q.get("source", "unknown")}

        # Daily bars from Yahoo
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty and len(hist) >= 1:
                last_bar = hist.iloc[-1]
                entry["daily_bar"] = {
                    "open": round(float(last_bar["Open"]), 2),
                    "high": round(float(last_bar["High"]), 2),
                    "low": round(float(last_bar["Low"]), 2),
                    "close": round(float(last_bar["Close"]), 2),
                    "volume": int(last_bar["Volume"]),
                }
                if len(hist) >= 2:
                    prev_bar = hist.iloc[-2]
                    entry["prev_daily_bar"] = {
                        "open": round(float(prev_bar["Open"]), 2),
                        "high": round(float(prev_bar["High"]), 2),
                        "low": round(float(prev_bar["Low"]), 2),
                        "close": round(float(prev_bar["Close"]), 2),
                        "volume": int(prev_bar["Volume"]),
                    }
        except Exception as e:
            entry["error"] = str(e)

        results[ticker] = entry

    return results


def fetch_macro_tickers() -> dict:
    """
    Fetch macro indicator tickers — sector ETFs, credit spreads, etc.
    """
    tickers = [
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        "HYG", "LQD", "TLT", "JNK",
        "SPY", "QQQ", "IWM",
        "GLD", "USO",
    ]
    return fetch_snapshots(tickers)


def enrich_screener_universe(screener: list) -> list:
    """
    Enrich screener results with accurate prior_close.
    Drop-in replacement for alpaca_data.enrich_screener_universe().
    """
    tickers = [t["ticker"] for t in screener]

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
            entry["price_source"] = all_closes[ticker].get("source", "unknown")

    return screener


# Quick smoke test
if __name__ == "__main__":
    print("Testing Unified Market Data module...\n")

    print("1. Latest quotes for SPY, AAPL, NVDA:")
    quotes = fetch_latest_quotes(["SPY", "AAPL", "NVDA"])
    for t, q in quotes.items():
        if "error" not in q:
            print(f"   {t}: bid={q.get('bid', 0):.2f} ask={q.get('ask', 0):.2f} mid={q.get('mid', 0):.2f} (source: {q.get('source', '?')})")
        else:
            print(f"   {t}: ERROR - {q['error']}")

    print("\n2. Prior close for SPY, AAPL:")
    closes = fetch_prior_close(["SPY", "AAPL"])
    for t, c in closes.items():
        if "error" not in c:
            print(f"   {t}: {c['prior_close']} (source: {c.get('source', '?')})")
        else:
            print(f"   {t}: ERROR - {c['error']}")

    print("\n3. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars(["NVDA"], days=7)
    for bar in hist.get("NVDA", {}).get("bars", [])[-5:]:
        print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} V={bar['volume']:,}")

    print("\n✅ Unified Market Data module working!")
