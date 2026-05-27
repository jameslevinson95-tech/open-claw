"""
Pre-Flight Data Fetch — runs at 7:55 AM ET
Fetches:
1. Yesterday's close prices (NOT live/intraday) — Tweak #6
2. SCREENER_UNIVERSE from Finviz ($100M+ mkt cap, >$5 price)
3. FRED macro data (MOVE index, credit spreads)
4. Smart money Twitter mentions (placeholder until API is wired)

All data is saved to output/ for agents to consume.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yfinance as yf

from config import SCREENER_MIN_MARKET_CAP, SCREENER_MIN_PRICE

# Unified market data — Schwab primary, Yahoo Finance fallback (replaces Alpaca)
try:
    import market_data as mdata
    MARKET_DATA_AVAILABLE = True
    print("[Pre-Flight] Unified Market Data: AVAILABLE (Schwab + Yahoo Finance)")
except Exception as e:
    MARKET_DATA_AVAILABLE = False
    print(f"[Pre-Flight] Unified Market Data: UNAVAILABLE ({e}) — using yfinance directly")

# Legacy alias for backward compat
ALPACA_AVAILABLE = MARKET_DATA_AVAILABLE

# Massive (Polygon-compatible) — technical indicators (SMA, RSI, MACD)
try:
    import massive_data as massive
    from config import MASSIVE_API_KEY
    MASSIVE_AVAILABLE = bool(MASSIVE_API_KEY)
    if MASSIVE_AVAILABLE:
        print("[Pre-Flight] Massive Market Data: AVAILABLE (technical indicators)")
    else:
        print("[Pre-Flight] Massive Market Data: KEY NOT SET — skipping")
except Exception as e:
    MASSIVE_AVAILABLE = False
    print(f"[Pre-Flight] Massive Market Data: UNAVAILABLE ({e})")

# ITC (Into The Cryptoverse) — crypto risk, macro recession risk, dominance
try:
    import itc_data as itc
    ITC_AVAILABLE = True
    print("[Pre-Flight] ITC Data Module: AVAILABLE")
except Exception as e:
    ITC_AVAILABLE = False
    print(f"[Pre-Flight] ITC Data Module: UNAVAILABLE ({e})")

# FedWatch — rate expectations from Fed Funds futures
try:
    import fedwatch as fw
    FEDWATCH_AVAILABLE = True
    print("[Pre-Flight] FedWatch Module: AVAILABLE")
except Exception as e:
    FEDWATCH_AVAILABLE = False
    print(f"[Pre-Flight] FedWatch Module: UNAVAILABLE ({e})")

OUTPUT_DIR = "output"

ASSEMBLY_STALE_HOURS = 18  # Assembly data older than this triggers fresh fetch from public APIs
ITC_STALE_HOURS = 18  # ITC data older than this is considered stale


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch YESTERDAY's regular-session close for a list of tickers.
    This is critical — all pricing and stop calculations use prior close,
    NOT live/intraday pre-market data (Tweak #6).
    
    Primary: Schwab + Yahoo Finance (unified market data)
    Fallback: Yahoo Finance direct
    """
    # Try unified market data first
    if MARKET_DATA_AVAILABLE:
        try:
            results = mdata.fetch_prior_close(tickers)
            ok_count = sum(1 for v in results.values() if "error" not in v)
            if ok_count >= len(tickers) * 0.5:
                print(f"[Pre-Flight] Prior close: {ok_count}/{len(tickers)} tickers from unified data")
                # Fill gaps with yfinance
                failed = [t for t, v in results.items() if "error" in v]
                if failed:
                    print(f"[Pre-Flight] Falling back to yfinance for {len(failed)} tickers: {failed[:5]}...")
                    yf_results = _fetch_prior_close_yfinance(failed)
                    results.update(yf_results)
                return results
            else:
                print(f"[Pre-Flight] Too many errors ({ok_count}/{len(tickers)}) — falling back to yfinance")
        except Exception as e:
            print(f"[Pre-Flight] Unified data prior_close failed: {e} — falling back to yfinance")

    return _fetch_prior_close_yfinance(tickers)


def _fetch_prior_close_yfinance(tickers: list) -> dict:
    """Original yfinance-based prior close fetch (fallback)."""
    results = {}
    end = datetime.now()
    start = end - timedelta(days=10)

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            close_prices = data["Close"]
            if len(close_prices) >= 2:
                if str(close_prices.index[-1].date()) == str(datetime.now().date()):
                    prior_close = float(close_prices.iloc[-2].item())
                    prior_date = str(close_prices.index[-2].date())
                else:
                    prior_close = float(close_prices.iloc[-1].item())
                    prior_date = str(close_prices.index[-1].date())
            else:
                prior_close = float(close_prices.iloc[-1].item())
                prior_date = str(close_prices.index[-1].date())

            closes = [float(c) for c in data["Close"].values.flatten()]

            results[ticker] = {
                "prior_close": round(prior_close, 2),
                "prior_date": prior_date,
                "closes_30d": [round(c, 2) for c in closes],
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_macro_data() -> dict:
    """
    Fetch macro indicators for Agent 1.
    Replaced S&P 500, DXY, Gold with MOVE, DIX, Sector Breadth per Jamie's tweaks.
    
    - VIX: ^VIX
    - MOVE index: via FRED API (or proxy)
    - DIX: Dark Index (from squeezemetrics — needs separate fetch)
    - 10Y/2Y yields: ^TNX, 2YY=F
    - HY credit spread proxy: HYG vs LQD
    - Sector breadth: % of S&P sectors above 20-day MA
    """
    macro = {}

    # --- Tickers we can get from yfinance ---
    yf_tickers = {
        "VIX": "^VIX",
        "TNX_10Y": "^TNX",
        "TWO_YEAR": "2YY=F",
        "HYG": "HYG",
        "LQD": "LQD",
    }

    end = datetime.now()
    start = end - timedelta(days=30)

    for name, ticker in yf_tickers.items():
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                macro[name] = {"error": f"No data for {ticker}"}
                continue

            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item()) if len(data) >= 5 else current
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current

            macro[name] = {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
            }
        except Exception as e:
            macro[name] = {"error": str(e)}

    # Yield curve spread
    if "TNX_10Y" in macro and "TWO_YEAR" in macro:
        if "current" in macro["TNX_10Y"] and "current" in macro["TWO_YEAR"]:
            macro["YIELD_CURVE_SPREAD"] = round(
                macro["TNX_10Y"]["current"] - macro["TWO_YEAR"]["current"], 2
            )

    # HY spread proxy
    if "HYG" in macro and "LQD" in macro:
        if "current" in macro["HYG"] and "current" in macro["LQD"]:
            macro["HY_SPREAD_PROXY"] = round(
                macro["HYG"]["current"] / macro["LQD"]["current"], 4
            )

    # --- MOVE Index (bond volatility) ---
    # MOVE is available via FRED as "MOVE" or as a proxy via ^MOVE
    # Trying FRED first, falling back to a note
    macro["MOVE"] = fetch_move_index()

    # --- DIX (Dark Index) ---
    # DIX comes from squeezemetrics.com — not available via yfinance/FRED
    # Requires a separate scrape or API
    macro["DIX"] = fetch_dix()

    # --- Sector Breadth ---
    macro["SECTOR_BREADTH"] = fetch_sector_breadth()

    macro["timestamp"] = datetime.now().isoformat()
    macro["price_source"] = "prior_close"  # Flag that we're using yesterday's close

    return macro


def fetch_move_index() -> dict:
    """
    Fetch MOVE index (Merrill Lynch Option Volatility Estimate).
    Measures Treasury/bond market volatility.
    Uses ^MOVE on yfinance (confirmed working), with FRED as fallback.
    """
    # Primary: yfinance ^MOVE
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        data = yf.download("^MOVE", start=start, end=end, progress=False)
        if not data.empty and len(data) >= 5:
            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item())
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current
            return {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
                "source": "yfinance ^MOVE",
            }
    except Exception:
        pass

    # Fallback: FRED API
    fred_key = os.environ.get("FRED_API_KEY", "")
    if fred_key:
        try:
            import requests
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": "BAMLMOVE",
                "api_key": fred_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 30,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            obs = [o for o in data.get("observations", []) if o.get("value") != "."]
            if obs:
                current = float(obs[0]["value"])
                prev_5 = float(obs[min(4, len(obs)-1)]["value"])
                return {
                    "current": round(current, 2),
                    "5d_ago": round(prev_5, 2),
                    "5d_change_pct": round((current - prev_5) / prev_5 * 100, 2),
                    "date": obs[0]["date"],
                    "source": "FRED",
                }
        except Exception:
            pass

    return {"error": "MOVE index unavailable"}


def fetch_dix() -> dict:
    """
    Fetch DIX (Dark Index) from squeezemetrics public CSV.
    Endpoint: https://squeezemetrics.com/monitor/static/DIX.csv
    Expected columns: date, price, dix, gex (ascending order by date).

    Returns {"current", "5d_ago", "20d_ago", "5d_change_pct", "date",
            "source", "interpretation"} on success,
            {"error": ...} on failure (Agent 1 will treat as soft-missing).
    """
    import csv
    import io
    import requests

    URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
    try:
        resp = requests.get(
            URL,
            timeout=10,
            headers={"User-Agent": "open-claw/1.0 (research)"},
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        return {"error": f"DIX HTTP {e.response.status_code} from squeezemetrics"}
    except requests.RequestException as e:
        return {"error": f"DIX fetch failed: {e}"}

    try:
        reader = csv.DictReader(io.StringIO(resp.text))
        # Normalize column keys to lowercase
        rows = [{k.lower(): v for k, v in r.items()} for r in reader]
    except Exception as e:
        return {"error": f"DIX CSV parse failed: {e}"}

    if len(rows) < 20:
        return {"error": f"DIX CSV had only {len(rows)} rows (need >=20)"}

    def _f(row, key):
        try:
            v = row.get(key)
            return float(v) if v not in (None, "", ".") else None
        except (TypeError, ValueError):
            return None

    latest = _f(rows[-1], "dix")
    prev_5 = _f(rows[-6], "dix") if len(rows) >= 6 else None
    prev_20 = _f(rows[-21], "dix") if len(rows) >= 21 else None
    date_str = rows[-1].get("date", "unknown")

    if latest is None:
        return {"error": "DIX CSV: could not parse latest value"}

    # squeezemetrics returns DIX as decimal (e.g., 0.4465 = 44.65%)
    # Normalize to percentage if value is < 1.0
    if latest < 1.0:
        latest = latest * 100
        if prev_5 is not None:
            prev_5 = prev_5 * 100
        if prev_20 is not None:
            prev_20 = prev_20 * 100

    # Sanity: DIX historically lives 35-50. Outside [20, 60] = format change or bad day.
    if not (20.0 <= latest <= 60.0):
        return {
            "error": f"DIX value {latest} outside plausible range [20,60] — feed format may have changed",
            "raw_value": latest,
        }

    interpretation = (
        "HIGH (>45) — institutional accumulation"
        if latest > 45
        else "LOW (<40) — distribution"
        if latest < 40
        else "NEUTRAL (40-45)"
    )

    # --- GEX (Gamma Exposure) --- also in the CSV, free data we were ignoring
    gex_latest = _f(rows[-1], "gex")
    gex_prev_5 = _f(rows[-6], "gex") if len(rows) >= 6 else None
    gex_prev_20 = _f(rows[-21], "gex") if len(rows) >= 21 else None

    gex_data = {}
    if gex_latest is not None:
        # GEX is in billions. Positive = dealers long gamma (market stabilizing/pinning).
        # Negative = dealers short gamma (market volatile, moves amplified).
        if gex_latest > 0:
            gex_interp = "POSITIVE — dealers long gamma, expect dampened moves / pinning"
        elif gex_latest > -500_000_000:
            gex_interp = "SLIGHTLY NEGATIVE — mild volatility amplification"
        else:
            gex_interp = "DEEPLY NEGATIVE — dealers short gamma, expect amplified moves / whipsaws"

        # Normalize: squeezemetrics reports raw notional. Convert to billions for readability.
        gex_bn = gex_latest / 1_000_000_000 if abs(gex_latest) > 1000 else gex_latest
        gex_data = {
            "current": round(gex_bn, 3),
            "unit": "billions",
            "interpretation": gex_interp,
        }
        if gex_prev_5 is not None:
            gex_data["5d_ago"] = round((gex_prev_5 / 1_000_000_000 if abs(gex_prev_5) > 1000 else gex_prev_5), 3)
        if gex_prev_20 is not None:
            gex_data["20d_ago"] = round((gex_prev_20 / 1_000_000_000 if abs(gex_prev_20) > 1000 else gex_prev_20), 3)

    out = {
        "current": round(latest, 2),
        "date": date_str,
        "source": "squeezemetrics.com/monitor/static/DIX.csv",
        "interpretation": interpretation,
    }
    if gex_data:
        out["gex"] = gex_data
    if prev_5 is not None:
        out["5d_ago"] = round(prev_5, 2)
        out["5d_change_pct"] = round((latest - prev_5) / prev_5 * 100, 2)
    if prev_20 is not None:
        out["20d_ago"] = round(prev_20, 2)
        out["20d_change_pct"] = round((latest - prev_20) / prev_20 * 100, 2)
    return out


def fetch_sector_breadth() -> dict:
    """
    Calculate sector breadth: what % of S&P 500 sectors are above their 20-day MA.
    Uses sector ETFs as proxies.
    Primary: Yahoo Finance via unified market data. Fallback: yfinance direct.
    """
    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Disc",
        "XLP": "Consumer Staples",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLC": "Comm Services",
    }

    above_20ma = 0
    total = 0
    sector_detail = {}

    # Try unified market data first for all sector ETFs
    if MARKET_DATA_AVAILABLE:
        try:
            hist = mdata.fetch_historical_bars(list(sector_etfs.keys()), days=40)
            for etf, name in sector_etfs.items():
                etf_data = hist.get(etf, {})
                bars = etf_data.get("bars", [])
                if len(bars) < 20:
                    continue
                closes = [b["close"] for b in bars]
                current = closes[-1]
                ma_20 = sum(closes[-20:]) / 20
                is_above = current > ma_20
                if is_above:
                    above_20ma += 1
                total += 1
                sector_detail[name] = {
                    "etf": etf,
                    "price": round(current, 2),
                    "ma_20": round(ma_20, 2),
                    "above_20ma": is_above,
                    "source": etf_data.get("source", "market_data"),
                }
            if total > 0:
                breadth_pct = round(above_20ma / total * 100, 1)
                return {
                    "above_20ma_count": above_20ma,
                    "total_sectors": total,
                    "breadth_pct": breadth_pct,
                    "detail": sector_detail,
                }
        except Exception as e:
            print(f"[Pre-Flight] Market data sector breadth failed: {e} — falling back to yfinance")
            above_20ma = 0
            total = 0
            sector_detail = {}

    # Fallback: yfinance
    end = datetime.now()
    start = end - timedelta(days=40)

    for etf, name in sector_etfs.items():
        try:
            data = yf.download(etf, start=start, end=end, progress=False)
            if data.empty or len(data) < 20:
                continue

            closes = [float(c) for c in data["Close"].values.flatten()]
            current = closes[-1]
            ma_20 = sum(closes[-20:]) / 20

            is_above = current > ma_20
            if is_above:
                above_20ma += 1
            total += 1

            sector_detail[name] = {
                "etf": etf,
                "price": round(current, 2),
                "ma_20": round(ma_20, 2),
                "above_20ma": is_above,
            }
        except Exception:
            continue

    breadth_pct = round(above_20ma / total * 100, 1) if total > 0 else 0

    return {
        "above_20ma_count": above_20ma,
        "total_sectors": total,
        "breadth_pct": breadth_pct,
        "detail": sector_detail,
    }


# Theme-to-Finviz filter mapping for dynamic screening
_THEME_SECTOR_MAP = {
    "ai infrastructure": {"Sector": "Technology"},
    "ai": {"Sector": "Technology"},
    "technology": {"Sector": "Technology"},
    "semiconductors": {"Industry": "Semiconductors"},
    "software": {"Sector": "Technology"},
    "energy": {"Sector": "Energy"},
    "uranium": {"Industry": "Uranium"},
    "solar": {"Industry": "Solar"},
    "oil": {"Sector": "Energy"},
    "healthcare": {"Sector": "Healthcare"},
    "biotech": {"Industry": "Biotechnology"},
    "financials": {"Sector": "Financial"},
    "banks": {"Industry": "Banks - Diversified"},
    "industrials": {"Sector": "Industrials"},
    "defense": {"Industry": "Aerospace & Defense"},
    "aerospace": {"Industry": "Aerospace & Defense"},
    "gold": {"Industry": "Gold"},
    "silver": {"Industry": "Silver"},
    "mining": {"Industry": "Other Industrial Metals & Mining"},
    "copper": {"Industry": "Copper"},
    "real estate": {"Sector": "Real Estate"},
    "utilities": {"Sector": "Utilities"},
    "consumer": {"Sector": "Consumer Cyclical"},
    "retail": {"Industry": "Internet Retail"},
    "materials": {"Sector": "Basic Materials"},
}

# Fallback hardcoded list — used if Finviz screener fails
_FALLBACK_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "AVGO", "CRM",
    "ORCL", "ADBE", "NFLX", "INTC", "CSCO", "QCOM", "TXN", "MU", "AMAT", "LRCX",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW", "AXP", "V",
    "UNH", "JNJ", "PFE", "ABBV", "LLY", "MRK", "BMY", "AMGN", "GILD", "TMO",
    "XOM", "CVX", "COP", "SLB", "EOG",
    "CAT", "DE", "HON", "RTX", "LMT", "BA", "GE", "UNP",
    "HD", "LOW", "NKE", "SBUX", "MCD", "TGT", "COST",
    "SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "GLD", "TLT", "HYG",
]

MAX_SCREENER_TICKERS = 50


def _run_finviz_screen(theme_filters: Optional[Dict] = None) -> list:
    """
    Run a single Finviz screener query and return a list of dicts.
    Raises on any failure so the caller can fall back.
    """
    from finvizfinance.screener.overview import Overview

    filt = {
        # Finviz doesn't have an exact $500M threshold;
        # use >$300M and post-filter for >$500M
        "Market Cap.": "+Small (over $300mln)",
        "Price": "Over $5",
        "Average Volume": "Over 500K",
        "50-Day Simple Moving Average": "Price above SMA50",
        "200-Day Simple Moving Average": "Price above SMA200",
    }

    if theme_filters:
        filt.update(theme_filters)

    o = Overview()
    o.set_filter(filters_dict=filt)
    # Fetch up to 200 rows (sorted by volume desc), then trim to MAX
    df = o.screener_view(order="Volume", ascend=False, limit=500, verbose=0)

    if df is None or df.empty:
        return []

    # Post-filter: market cap > $500M (Finviz only lets us filter >$300M)
    df = df[df["Market Cap"] >= 500_000_000]

    results = []
    for _, row in df.iterrows():
        results.append({
            "ticker": row["Ticker"],
            "name": row["Company"],
            "sector": row["Sector"],
            "market_cap": int(row["Market Cap"]) if row["Market Cap"] else 0,
            "prior_close": round(float(row["Price"]), 2) if row["Price"] else 0.0,
            "source": "finviz_dynamic",
        })

    return results


def _fallback_screener_universe() -> list:
    """
    Fallback: use hardcoded ticker list + yfinance for basic data.
    Used when Finviz is unavailable (rate-limited, down, etc.).
    """
    import warnings
    warnings.warn(
        "[Pre-Flight] Finviz screener failed — falling back to hardcoded universe",
        RuntimeWarning,
        stacklevel=3,
    )
    print("[Pre-Flight] WARNING: Using hardcoded fallback universe")

    screener = []
    for ticker in _FALLBACK_UNIVERSE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mkt_cap = info.get("marketCap", 0)
            price = info.get("regularMarketPreviousClose") or info.get("previousClose", 0)

            if mkt_cap and mkt_cap >= SCREENER_MIN_MARKET_CAP and price and price >= SCREENER_MIN_PRICE:
                screener.append({
                    "ticker": ticker,
                    "name": info.get("shortName", ticker),
                    "sector": info.get("sector", "N/A"),
                    "market_cap": mkt_cap,
                    "prior_close": round(float(price), 2),
                    "source": "hardcoded_fallback",
                })
        except Exception:
            continue

    return screener[:MAX_SCREENER_TICKERS]


def _enrich_prior_close(tickers_data: list) -> list:
    """
    Enrich screener results with accurate prior_close from yfinance,
    since Finviz price data may be slightly delayed.
    """
    ticker_symbols = [t["ticker"] for t in tickers_data]
    end = datetime.now()
    start = end - timedelta(days=10)

    for entry in tickers_data:
        try:
            data = yf.download(entry["ticker"], start=start, end=end, progress=False)
            if not data.empty:
                entry["prior_close"] = round(float(data["Close"].iloc[-1].item()), 2)
        except Exception:
            pass  # Keep Finviz price as fallback

    return tickers_data


def generate_screener_universe(themes: Optional[List[str]] = None) -> list:
    """
    Generate SCREENER_UNIVERSE: up to 50 liquid tickers meeting:
    - Market cap > $500M
    - Price > $5
    - Average volume > 500K
    - Price above 50-day SMA (momentum filter)

    Uses Finviz dynamic screening via finvizfinance package.
    Accepts optional `themes` list to focus on specific sectors/industries.
    Falls back to hardcoded list if Finviz fails.
    """
    try:
        all_results = []
        seen_tickers = set()

        if themes:
            # Run separate screens per theme, then merge
            mapped_any = False
            for theme in themes:
                theme_key = theme.lower().strip()
                theme_filters = _THEME_SECTOR_MAP.get(theme_key)
                if theme_filters:
                    mapped_any = True
                    print(f"[Pre-Flight] Finviz screen: theme '{theme}' → {theme_filters}")
                    try:
                        results = _run_finviz_screen(theme_filters)
                        for r in results:
                            if r["ticker"] not in seen_tickers:
                                r["theme"] = theme
                                all_results.append(r)
                                seen_tickers.add(r["ticker"])
                    except Exception as e:
                        print(f"[Pre-Flight] Finviz theme '{theme}' screen failed: {e}")

            # If no themes mapped, or all theme screens failed, do broad scan
            if not mapped_any or not all_results:
                print("[Pre-Flight] No theme-specific results — running broad Finviz scan")
                results = _run_finviz_screen()
                for r in results:
                    if r["ticker"] not in seen_tickers:
                        all_results.append(r)
                        seen_tickers.add(r["ticker"])
        else:
            # No themes — broad scan
            print("[Pre-Flight] Running broad Finviz screener (no theme filter)")
            all_results = _run_finviz_screen()

        if not all_results:
            print("[Pre-Flight] Finviz returned 0 results — falling back")
            return _fallback_screener_universe()

        # Sort by volume proxy (market_cap as tiebreaker) and cap at MAX
        # Note: Finviz already sorted by volume desc, but after merging themes
        # we re-deduplicate; the order from the first theme takes precedence.
        all_results = all_results[:MAX_SCREENER_TICKERS]

        # Enrich with accurate prior_close (Schwab/Yahoo via unified market data)
        if MARKET_DATA_AVAILABLE:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with market data prior_close...")
            all_results = mdata.enrich_screener_universe(all_results)
        else:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with yfinance prior_close...")
            all_results = _enrich_prior_close(all_results)

        print(f"[Pre-Flight] Screener universe: {len(all_results)} tickers from Finviz dynamic screen")
        return all_results

    except Exception as e:
        print(f"[Pre-Flight] Finviz screener failed: {e}")
        return _fallback_screener_universe()


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money Twitter/X mentions for given tickers.
    X research is MANDATORY — this must return real data.
    
    When called from the OCPlatform orchestrator, this uses x_search.
    When run standalone, it reads from a pre-existing file or raises an error.
    """
    from config import SMART_MONEY_ACCOUNTS

    mentions = {}
    curated_handles = SMART_MONEY_ACCOUNTS
    if not curated_handles:
        curated_handles = [
            "unusual_whales", "DeItaone", "Fxhedgers", "zaborsky",
            "jimcramer", "GurufocusData", "OptionsHawk", "PeterSchiff",
            "TruthGundlach", "elerianm", "SqueezeMetrics", "sentimentrader",
            "DarkPoolChart", "WallStJesus", "VolSignals",
        ]

    # NOTE: The actual x_search calls happen in the orchestrator (orchestrator.py)
    # because x_search is an OCPlatform tool, not a Python library.
    # This function checks for the pre-fetched output file.
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            return json.load(f)

    raise RuntimeError(
        "Smart money X/Twitter data not found. The orchestrator must run x_search "
        "for each ticker against curated accounts and save to output/smart_money_mentions.json "
        "BEFORE Agent 3 can run. X research is MANDATORY."
    )


def format_macro_for_prompt(data: dict) -> str:
    """Format macro data into a clean text block for the LLM prompt."""
    lines = [
        f"MACRO DATA SNAPSHOT — {data.get('timestamp', 'unknown')}",
        f"Price Source: {data.get('price_source', 'unknown')}",
        "=" * 50,
    ]

    skip_keys = {"timestamp", "price_source"}

    for key, val in data.items():
        if key in skip_keys:
            continue
        if isinstance(val, dict) and "error" in val:
            lines.append(f"{key}: DATA UNAVAILABLE ({val['error']})")
        elif isinstance(val, dict) and "current" in val:
            change_str = ""
            if "5d_change_pct" in val:
                change_str = f" (5d: {val['5d_change_pct']:+.2f}%"
                if "20d_change_pct" in val:
                    change_str += f", 20d: {val['20d_change_pct']:+.2f}%"
                change_str += ")"
            lines.append(f"{key}: {val['current']}{change_str}")
        elif isinstance(val, dict) and "breadth_pct" in val:
            lines.append(
                f"{key}: {val['breadth_pct']}% of sectors above 20DMA "
                f"({val['above_20ma_count']}/{val['total_sectors']})"
            )
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {json.dumps(val)}" if not isinstance(val, str) else f"{key}: {val}")

    return "\n".join(lines)


def merge_assembly_screens(static_universe: list, assembly: dict) -> list:
    """
    Hybrid screener: merge Assembly's momentum/breakout screens into the static universe.
    Adds new tickers from Assembly that aren't already in the static list.
    Tags them with source='assembly_momentum' so Agent 2 knows they came from the live screen.
    """
    existing_tickers = set(t["ticker"] for t in static_universe)
    added = 0

    # Load Assembly screens if available
    screens_path = "output/assembly_screens.json"
    if os.path.exists(screens_path):
        try:
            with open(screens_path) as f:
                screens = json.load(f)
        except Exception:
            screens = {}
    else:
        screens = {}

    # Add overbought momentum names (these are running — potential trend plays)
    for entry in screens.get("overbought", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_overbought",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    # Add oversold names (these are beaten down — potential mean-reversion or value)
    for entry in screens.get("oversold", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_oversold",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    if added > 0:
        print(f"[Pre-Flight] Merged {added} new tickers from Assembly momentum screens (total: {len(static_universe)})")
    else:
        print("[Pre-Flight] No new Assembly tickers to merge (all already in universe)")

    return static_universe


def format_assembly_for_prompt(assembly: dict) -> str:
    """Format Assembly Private data for Agent 1's system prompt."""
    if not assembly:
        return "ASSEMBLY DATA: NOT AVAILABLE"

    lines = [
        f"ASSEMBLY SENTIMENT & MACRO — {assembly.get('timestamp', 'unknown')}",
        "Source: assemblyprivate.com (FMP data feed)",
        "=" * 50,
    ]

    # Sentiment
    sent = assembly.get("sentiment", {})
    if sent:
        lines.append(f"\nSENTIMENT COMPOSITE: {sent.get('composite_score', '?')} ({sent.get('composite_label', '?')})")
        lines.append(f"  Prev Close: {sent.get('prev_close', '?')} | 1W: {sent.get('one_week_ago', '?')} | 1M: {sent.get('one_month_ago', '?')} | 1Y: {sent.get('one_year_ago', '?')}")
        lines.append(f"  30D Avg: {sent.get('thirty_day_avg', '?')} | 52W High: {sent.get('fifty_two_week_high', '?')} | 52W Low: {sent.get('fifty_two_week_low', '?')}")

        comp = sent.get("components", {})
        if comp:
            lines.append("  Sub-Components:")
            for key, label in [
                ("market_volatility_vix", "Market Volatility (VIX)"),
                ("sp500_momentum_125d", "S&P 125d Momentum"),
                ("sp500_momentum", "S&P 500 Momentum"),
                ("stock_price_strength", "Stock Price Strength"),
                ("stock_price_breadth", "Stock Price Breadth"),
                ("put_call_options", "Put/Call Options"),
                ("junk_bond_demand", "Junk Bond Demand"),
                ("safe_haven_demand", "Safe Haven Demand"),
            ]:
                val = comp.get(key)
                if val is not None:
                    lines.append(f"    {label}: {val}")

    # Risk & Credit Gauges
    macro = assembly.get("macro", {})
    gauges = macro.get("risk_credit_gauges", [])
    if gauges:
        lines.append("\nRISK & CREDIT GAUGES (with 50d/200d trends):")
        for g in gauges:
            lines.append(f"  {g['ticker']} ({g['name']}): {g['price']} | Today: {g['today']} | vs50d: {g['vs_50d']} | vs200d: {g['vs_200d']} | 52wk: {g['range_52w']}")

    # Cross-asset rotation
    xasset = macro.get("cross_asset_rotation", [])
    if xasset:
        lines.append("\nCROSS-ASSET ROTATION:")
        for a in xasset:
            lines.append(f"  {a['ticker']} ({a['name']}): ${a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    # Sector rotation
    sectors = macro.get("sector_rotation", [])
    if sectors:
        lines.append("\nSECTOR ROTATION (RS vs SPY):")
        for s in sectors:
            lines.append(f"  {s['etf']} ({s['sector']}): Today: {s['today']} | vs50d: {s['vs_50d']} | vs200d: {s['vs_200d']} | RS: {s.get('rs_vs_spy', '?')}")

    # Yield curve
    yc = macro.get("yield_curve", {})
    if yc:
        curve = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"\nYIELD CURVE: {curve}")
        if "2Y" in yc and "10Y" in yc:
            spread = round(yc["10Y"] - yc["2Y"], 2)
            lines.append(f"  2s10s Spread: {spread}")

    return "\n".join(lines)


def is_assembly_stale(assembly_path: str) -> bool:
    """Check if assembly data file is stale (older than ASSEMBLY_STALE_HOURS)."""
    if not os.path.exists(assembly_path):
        return True
    try:
        with open(assembly_path) as f:
            data = json.load(f)
        ts = data.get("timestamp", "")
        if not ts:
            return True
        # Parse ISO timestamp
        data_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        print(f"[Pre-Flight] Assembly data age: {age_hours:.1f}h (stale threshold: {ASSEMBLY_STALE_HOURS}h)")
        return age_hours > ASSEMBLY_STALE_HOURS
    except Exception as e:
        print(f"[Pre-Flight] Could not check assembly staleness: {e}")
        return True


def fetch_fresh_sentiment_fallback() -> dict:
    """
    Fetch fresh sentiment indicators from public APIs when Assembly data is stale.
    Uses CNN Fear & Greed API + yfinance for the same indicators Assembly provides.
    """
    import requests
    result = {"timestamp": datetime.now().isoformat(), "source": "public_api_fallback"}

    # 2. Sub-components from yfinance
    components = {}
    try:
        end = datetime.now()
        start = end - timedelta(days=5)

        # VIX for market volatility component
        vix = yf.download("^VIX", start=start, end=end, progress=False)
        if not vix.empty:
            vix_val = float(vix["Close"].iloc[-1].item())
            components["vix_value"] = round(vix_val, 2)
            if vix_val < 15: components["market_volatility_vix"] = 90
            elif vix_val < 20: components["market_volatility_vix"] = 65
            elif vix_val < 25: components["market_volatility_vix"] = 45
            elif vix_val < 35: components["market_volatility_vix"] = 25
            else: components["market_volatility_vix"] = 5

        # S&P 500 momentum (125-day)
        spy = yf.download("SPY", start=end - timedelta(days=180), end=end, progress=False)
        if not spy.empty and len(spy) > 125:
            current_spy = float(spy["Close"].iloc[-1].item())
            spy_125d = float(spy["Close"].iloc[-125].item())
            momentum_pct = (current_spy - spy_125d) / spy_125d * 100
            if momentum_pct > 10: components["sp500_momentum_125d"] = 90
            elif momentum_pct > 5: components["sp500_momentum_125d"] = 70
            elif momentum_pct > 0: components["sp500_momentum_125d"] = 50
            elif momentum_pct > -5: components["sp500_momentum_125d"] = 30
            else: components["sp500_momentum_125d"] = 10

        # Junk bond demand: HYG vs LQD spread
        hyg = yf.download("HYG", start=start, end=end, progress=False)
        lqd = yf.download("LQD", start=start, end=end, progress=False)
        if not hyg.empty and not lqd.empty:
            hyg_ret = float(hyg["Close"].pct_change().iloc[-1].item())
            lqd_ret = float(lqd["Close"].pct_change().iloc[-1].item())
            spread = (hyg_ret - lqd_ret) * 100
            if spread > 0.5: components["junk_bond_demand"] = 80
            elif spread > 0: components["junk_bond_demand"] = 60
            elif spread > -0.5: components["junk_bond_demand"] = 40
            else: components["junk_bond_demand"] = 20

        # Safe haven demand: TLT relative to SPY
        tlt = yf.download("TLT", start=start, end=end, progress=False)
        if not tlt.empty and not spy.empty:
            tlt_ret = float(tlt["Close"].pct_change().iloc[-1].item())
            spy_ret_1d = float(spy["Close"].pct_change().iloc[-1].item())
            haven_spread = (spy_ret_1d - tlt_ret) * 100
            if haven_spread > 1: components["safe_haven_demand"] = 80
            elif haven_spread > 0: components["safe_haven_demand"] = 60
            elif haven_spread > -1: components["safe_haven_demand"] = 40
            else: components["safe_haven_demand"] = 20

    except Exception as e:
        print(f"[Pre-Flight] Component fallback fetch error: {e}")

    result["components"] = components

    # Compute synthetic composite from available components
    if components:
        scores = [v for k, v in components.items() if k != "vix_value" and isinstance(v, (int, float))]
        if scores:
            composite = round(sum(scores) / len(scores))
            result["composite_score"] = composite
            if composite >= 75: result["composite_label"] = "Extreme Greed"
            elif composite >= 55: result["composite_label"] = "Greed"
            elif composite >= 45: result["composite_label"] = "Neutral"
            elif composite >= 25: result["composite_label"] = "Fear"
            else: result["composite_label"] = "Extreme Fear"
            print(f"[Pre-Flight] Synthetic composite: {composite} ({result['composite_label']}) from {len(scores)} components")

    return result


def run_preflight(themes: Optional[List[str]] = None) -> dict:
    """
    Run the full 7:55 AM pre-flight.
    Returns all data packaged for downstream agents.

    Args:
        themes: Optional list of theme strings from Agent 1's preferred_themes.
                Maps to Finviz sector/industry filters for focused screening.
                E.g. ["AI Infrastructure", "Energy", "Uranium"]
    """
    # ━━━ HOLIDAY GATE: Abort if market is closed (prevents holiday runs) ━━━
    from safeguards import assert_market_open
    assert_market_open()

    print("[Pre-Flight] Starting 7:55 AM data fetch...")
    print("[Pre-Flight] Using PRIOR CLOSE prices (not live/intraday)")
    if themes:
        print(f"[Pre-Flight] Theme filters: {themes}")

    # 1. Macro data
    print("[Pre-Flight] Fetching macro data...")
    macro = fetch_macro_data()

    # 2. Screener universe (dynamic via Finviz)
    print("[Pre-Flight] Generating screener universe...")
    screener = generate_screener_universe(themes=themes)

    # 3. Smart money X/Twitter mentions
    # NOTE: X search happens in the orchestrator via OCPlatform's x_search tool.
    # Pre-flight saves macro + screener. The orchestrator then:
    #   a) Runs Agent 1 + Agent 2 to get candidate tickers
    #   b) Runs x_search for those tickers against curated accounts
    #   c) Saves results to output/smart_money_mentions.json
    #   d) Then runs Agent 3 with that data
    # X research is MANDATORY — Agent 3 will not bypass.

    # 3. Assembly Private data (sentiment + macro overlay)
    #    If stale or missing, auto-fetch fresh indicators from public APIs
    assembly = {}
    assembly_path = f"{OUTPUT_DIR}/assembly_data.json"
    stale = is_assembly_stale(assembly_path)

    if not stale:
        try:
            with open(assembly_path) as f:
                assembly = json.load(f)
            print(f"[Pre-Flight] Assembly data FRESH — loaded (sentiment: {assembly.get('sentiment', {}).get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Assembly data load failed: {e}")
            stale = True

    if stale:
        print("[Pre-Flight] Assembly data STALE or missing — fetching fresh indicators from public APIs...")
        fresh_sentiment = fetch_fresh_sentiment_fallback()
        assembly = {
            "timestamp": datetime.now().isoformat(),
            "source": "public_api_fallback",
            "sentiment": fresh_sentiment,
            "macro": {},  # macro already covered by fetch_macro_data() above
        }
        # Save the fresh fallback so agents can reference it
        try:
            with open(assembly_path, "w") as f:
                json.dump(assembly, f, indent=2)
            print(f"[Pre-Flight] Fresh fallback data saved (sentiment: {fresh_sentiment.get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Could not save fallback data: {e}")

    # 4. Merge Assembly momentum screen into screener universe (hybrid approach)
    screener = merge_assembly_screens(screener, assembly)

    # 5. Technical indicators from Massive API (SMA, RSI, MACD)
    technicals = {}
    if MASSIVE_AVAILABLE:
        # Get technicals for key macro tickers (SPY, QQQ, IWM)
        # and top screener picks (first 5 to stay within rate limits)
        tech_tickers = ["SPY", "QQQ", "IWM"]
        top_screener = [t["ticker"] for t in screener[:3] if "ticker" in t]
        tech_tickers.extend([t for t in top_screener if t not in tech_tickers])

        print(f"[Pre-Flight] Fetching Massive technicals for {tech_tickers}...")
        for i, ticker in enumerate(tech_tickers):
            try:
                # SPY gets the full treatment (SMA + RSI + MACD = 5 calls)
                # Others get lightweight (prev + RSI + MACD = 3 calls)
                if i == 0:  # SPY
                    tech = massive.fetch_technicals_with_sma(ticker)
                else:
                    tech = massive.fetch_full_technicals(ticker)
                technicals[ticker] = tech
                print(f"  {ticker}: RSI={tech.get('rsi_14', '?')} MACD_trend={tech.get('macd_trend', '?')}")
            except Exception as e:
                print(f"  {ticker}: FAILED — {e}")
                technicals[ticker] = {"error": str(e)}

        # Save technicals
        with open(f"{OUTPUT_DIR}/technicals.json", "w") as f:
            json.dump(technicals, f, indent=2)
        print(f"[Pre-Flight] Technicals saved for {len(technicals)} tickers")
    else:
        print("[Pre-Flight] Skipping Massive technicals (not available)")

    # 6. FedWatch — rate expectations from Fed Funds futures
    fedwatch_data = {}
    if FEDWATCH_AVAILABLE:
        try:
            print("[Pre-Flight] Fetching FedWatch rate expectations...")
            fedwatch_data = fw.fetch_fedwatch()
            if "error" not in fedwatch_data:
                fw.save_fedwatch(fedwatch_data)
                summary = fedwatch_data.get("summary", {})
                print(f"[Pre-Flight] FedWatch: next={summary.get('next_meeting', '?')} action={summary.get('next_meeting_action', '?')} year-end cuts={summary.get('total_cuts_priced_by_year_end', '?')}")
            else:
                print(f"[Pre-Flight] FedWatch error: {fedwatch_data['error']}")
        except Exception as e:
            print(f"[Pre-Flight] FedWatch fetch failed: {e}")
    else:
        print("[Pre-Flight] FedWatch module not available — skipping")

    # 7. ITC (Into The Cryptoverse) data — crypto risk, recession risk, dominance
    itc_data_loaded = {}
    if ITC_AVAILABLE:
        itc_path = f"{OUTPUT_DIR}/itc_data.json"
        if not itc.is_itc_stale(itc_path, ITC_STALE_HOURS):
            itc_data_loaded = itc.load_itc_data(itc_path) or {}
            if itc_data_loaded:
                print(f"[Pre-Flight] ITC data FRESH — loaded (crypto risk: {itc_data_loaded.get('crypto_risk', {}).get('summary', '?')})")
        else:
            print("[Pre-Flight] ITC data STALE or missing — will need browser scrape from Zuck")
            print("[Pre-Flight] ITC data must be fetched via browser (no public API). Skipping for now.")
    else:
        print("[Pre-Flight] ITC module not available — skipping")

    preflight_data = {
        "timestamp": datetime.now().isoformat(),
        "macro": macro,
        "screener_universe": screener,
        "assembly": assembly,
        "technicals": technicals,
        "fedwatch": fedwatch_data,
        "itc": itc_data_loaded,
    }

    # Save all outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(f"{OUTPUT_DIR}/preflight_macro.json", "w") as f:
        json.dump(macro, f, indent=2)

    with open(f"{OUTPUT_DIR}/screener_universe.json", "w") as f:
        json.dump(screener, f, indent=2)

    print(f"[Pre-Flight] Complete. Macro data + {len(screener)} screener tickers saved.")
    print(f"[Pre-Flight] NOTE: X/Twitter smart money fetch runs in orchestrator after Agent 2 picks tickers.")
    if itc_data_loaded:
        print(f"[Pre-Flight] ITC data included (crypto summary risk: {itc_data_loaded.get('crypto_risk', {}).get('summary', '?')}, recession: {itc_data_loaded.get('macro_risk', {}).get('recession_composite', '?')})")
    return preflight_data


if __name__ == "__main__":
    data = run_preflight()
    print("\n" + format_macro_for_prompt(data["macro"]))
    print(f"\nScreener: {len(data['screener_universe'])} tickers")
    print(f"Smart Money: {data['smart_money']['status']}")
