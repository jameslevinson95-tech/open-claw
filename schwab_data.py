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


if __name__ == "__main__":
    import sys
    tickers = sys.argv[1:] or ["BAC", "QCOM", "AAPL"]
    quotes = fetch_schwab_quotes(tickers)
    print(json.dumps(quotes, indent=2, default=str))
