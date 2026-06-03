"""
Schwab Market Data module — cross-reference quote source.

Uses Schwab's REST API directly for real-time quotes.
Token stored in schwab_token.json, auto-refreshes access token
(30 min expiry) using the refresh token (7 day expiry — manual
re-auth needed weekly).

Usage:
    from schwab_data import fetch_schwab_quotes
    quotes = fetch_schwab_quotes(["BAC", "QCOM"])
"""

import os
import json
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SCHWAB_APP_KEY = os.environ.get("SCHWAB_APP_KEY", "")
SCHWAB_APP_SECRET = os.environ.get("SCHWAB_APP_SECRET", "")
TOKEN_PATH = Path(__file__).parent / "schwab_token.json"

# Cache token in memory to avoid re-reading file every call
_token_cache = {"access_token": None, "expires_at": 0}


def _load_token():
    """Load token from file, refresh if expired."""
    global _token_cache

    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    if not TOKEN_PATH.exists():
        print(f"[Schwab] No token file at {TOKEN_PATH}")
        return None

    token_data = json.loads(TOKEN_PATH.read_text())

    # Try using existing access token first (test with a lightweight call)
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    # Try a test request
    try:
        resp = requests.get(
            "https://api.schwabapi.com/marketdata/v1/quotes",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"symbols": "AAPL", "fields": "quote"},
            timeout=5,
        )
        if resp.status_code == 200:
            _token_cache["access_token"] = access_token
            _token_cache["expires_at"] = time.time() + 1500  # ~25 min
            return access_token
    except Exception:
        pass

    # Access token expired — try refresh
    if refresh_token:
        try:
            credentials = base64.b64encode(
                f"{SCHWAB_APP_KEY}:{SCHWAB_APP_SECRET}".encode()
            ).decode()
            resp = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                new_token = resp.json()
                TOKEN_PATH.write_text(json.dumps(new_token, indent=2))
                _token_cache["access_token"] = new_token["access_token"]
                _token_cache["expires_at"] = time.time() + 1500
                print("[Schwab] Access token refreshed successfully")
                return new_token["access_token"]
            else:
                print(f"[Schwab] Token refresh failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"[Schwab] Token refresh error: {e}")

    print("[Schwab] No valid token — re-run OAuth setup")
    return None


def fetch_schwab_quotes(tickers: list) -> dict:
    """
    Fetch real-time quotes from Schwab for a list of tickers.

    Returns dict like:
        {"BAC": {"bid": 52.10, "ask": 52.15, "last": 52.12, "source": "schwab"}, ...}

    Returns empty dict on failure.
    """
    access_token = _load_token()
    if not access_token:
        return {}

    result = {}
    try:
        resp = requests.get(
            "https://api.schwabapi.com/marketdata/v1/quotes",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"symbols": ",".join(tickers), "fields": "quote"},
            timeout=8,
        )

        if resp.status_code == 401:
            # Token just expired mid-request — force refresh
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0
            access_token = _load_token()
            if access_token:
                resp = requests.get(
                    "https://api.schwabapi.com/marketdata/v1/quotes",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"symbols": ",".join(tickers), "fields": "quote"},
                    timeout=8,
                )

        if resp.status_code != 200:
            print(f"[Schwab] Quote request failed ({resp.status_code}): {resp.text[:200]}")
            return {}

        data = resp.json()
        for ticker in tickers:
            if ticker in data:
                q = data[ticker].get("quote", data[ticker])
                bid = float(q.get("bidPrice", 0))
                ask = float(q.get("askPrice", 0))
                last = float(q.get("lastPrice", 0))
                if ask > 0 or last > 0:
                    result[ticker] = {
                        "bid": bid,
                        "ask": ask,
                        "last": last,
                        "mid": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last,
                        "source": "schwab",
                    }
    except Exception as e:
        print(f"[Schwab] Quote fetch failed: {e}")

    return result


# Symbol remapping: Yahoo-style index tickers -> Schwab index tickers.
# Schwab uses a leading "$" for cash indices (e.g. $VIX, $MOVE) and does NOT
# recognize Yahoo's "^" prefix or bare names. Map the ones we actually use.
_SCHWAB_SYMBOL_MAP = {
    "^VIX": "$VIX", "VIX": "$VIX",
    "^MOVE": "$MOVE", "MOVE": "$MOVE",
    "^VXN": "$VXN", "VXN": "$VXN",
    "^TNX": "$TNX", "TNX": "$TNX",
}


# Schwab quotes Treasury yield indices as (yield % * 10), e.g. $TNX = 44.55
# means a 4.455% 10-year yield. Yahoo's ^TNX returns 4.455 directly. Divide
# these by 10 so downstream math (yield-curve spread) stays on one scale.
_SCHWAB_SCALE = {
    "$TNX": 0.1, "$TYX": 0.1, "$FVX": 0.1, "$IRX": 0.1,
}


def _map_symbol(sym: str) -> str:
    """Translate a Yahoo-style symbol to its Schwab equivalent."""
    return _SCHWAB_SYMBOL_MAP.get(sym, sym)


def fetch_schwab_history(symbol: str, days: int = 30, frequency_type: str = "daily") -> dict:
    """
    Fetch historical daily OHLCV candles from Schwab's price-history endpoint.

    Handles index symbol remapping (^VIX -> $VIX, ^MOVE -> $MOVE, etc.).

    Returns dict:
        {"symbol": <schwab_symbol>, "bars": [{date, open, high, low, close, volume}, ...],
         "count": N, "source": "schwab"}
    Returns {"bars": [], "count": 0, "error": ...} on failure.
    """
    access_token = _load_token()
    if not access_token:
        return {"bars": [], "count": 0, "error": "no_token"}

    schwab_sym = _map_symbol(symbol)

    # Pick the smallest periodType window that covers `days`.
    # Schwab periodType=month supports period in {1,2,3,6}; year for longer.
    if days <= 5:
        period_type, period = "day", 5
    elif days <= 30:
        period_type, period = "month", 1
    elif days <= 60:
        period_type, period = "month", 2
    elif days <= 90:
        period_type, period = "month", 3
    elif days <= 180:
        period_type, period = "month", 6
    else:
        period_type, period = "year", 1

    params = {
        "symbol": schwab_sym,
        "periodType": period_type,
        "period": period,
        "frequencyType": frequency_type,
        "frequency": 1,
    }

    def _do_request(tok):
        return requests.get(
            "https://api.schwabapi.com/marketdata/v1/pricehistory",
            headers={"Authorization": f"Bearer {tok}"},
            params=params,
            timeout=10,
        )

    try:
        resp = _do_request(access_token)
        if resp.status_code == 401:
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0
            access_token = _load_token()
            if access_token:
                resp = _do_request(access_token)

        if resp.status_code != 200:
            return {"symbol": schwab_sym, "bars": [], "count": 0,
                    "error": f"http_{resp.status_code}: {resp.text[:120]}"}

        data = resp.json()
        candles = data.get("candles", [])
        scale = _SCHWAB_SCALE.get(schwab_sym, 1.0)
        bars = []
        for c in candles:
            ts = c.get("datetime", 0) / 1000.0  # ms epoch -> s
            from datetime import datetime as _dt
            bars.append({
                "date": _dt.utcfromtimestamp(ts).strftime("%Y-%m-%d"),
                "open": round(float(c.get("open", 0)) * scale, 4),
                "high": round(float(c.get("high", 0)) * scale, 4),
                "low": round(float(c.get("low", 0)) * scale, 4),
                "close": round(float(c.get("close", 0)) * scale, 4),
                "volume": int(c.get("volume", 0)),
            })
        return {"symbol": schwab_sym, "bars": bars, "count": len(bars), "source": "schwab"}
    except Exception as e:
        return {"symbol": schwab_sym, "bars": [], "count": 0, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "history":
        sym = sys.argv[2] if len(sys.argv) > 2 else "SPY"
        h = fetch_schwab_history(sym, days=30)
        print(json.dumps({"symbol": h["symbol"], "count": h["count"],
                          "last": h["bars"][-1] if h["bars"] else None}, indent=2, default=str))
    else:
        tickers = sys.argv[1:] or ["BAC", "QCOM", "AAPL"]
        quotes = fetch_schwab_quotes(tickers)
        print(json.dumps(quotes, indent=2, default=str))
