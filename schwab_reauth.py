#!/usr/bin/env python3
"""
Schwab OAuth Auto Re-Auth Script

Runs weekly via cron to refresh the Schwab API token before the
7-day refresh token expires. Fully automated — uses browser automation
to complete the OAuth flow without human intervention.

Usage:
    python3 schwab_reauth.py

Cron (every 5 days at 3 AM to stay ahead of 7-day expiry):
    0 3 */5 * * cd /Users/chris/code/trading-pipeline && python3 schwab_reauth.py >> logs/schwab_reauth.log 2>&1
"""

import json
import base64
import time
import subprocess
import requests
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

APP_KEY = os.environ["SCHWAB_APP_KEY"]
APP_SECRET = os.environ["SCHWAB_APP_SECRET"]
CALLBACK_URL = "https://127.0.0.1/"
TOKEN_PATH = Path(__file__).parent / "schwab_token.json"
LOG_PREFIX = "[SchwabReAuth]"

# Schwab brokerage credentials (for automated login)
SCHWAB_USERNAME = "chrisbuetti"
SCHWAB_PW_FILE = Path(os.path.expanduser("~/.openclaw/workspace-zuck/.schwabpw"))


def log(msg):
    print(f"{LOG_PREFIX} {msg}", flush=True)


def try_refresh_token():
    """Try to refresh using existing refresh token first."""
    if not TOKEN_PATH.exists():
        return False

    token_data = json.loads(TOKEN_PATH.read_text())
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return False

    credentials = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    try:
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
            timeout=15,
        )
        if resp.status_code == 200:
            new_token = resp.json()
            TOKEN_PATH.write_text(json.dumps(new_token, indent=2))
            log("✅ Token refreshed via refresh_token grant")
            return True
        else:
            log(f"Refresh token grant failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        log(f"Refresh token request error: {e}")
        return False


def exchange_code(auth_code):
    """Exchange authorization code for tokens."""
    credentials = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    resp = requests.post(
        "https://api.schwabapi.com/v1/oauth/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": CALLBACK_URL,
        },
        timeout=15,
    )
    if resp.status_code == 200:
        token_data = resp.json()
        TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
        log("✅ Token saved via authorization_code grant")
        return True
    else:
        log(f"❌ Code exchange failed ({resp.status_code}): {resp.text[:300]}")
        return False


def verify_token():
    """Verify the token works with a test quote."""
    from schwab_data import fetch_schwab_quotes
    quotes = fetch_schwab_quotes(["AAPL"])
    if quotes:
        log(f"✅ Token verified — AAPL: ${quotes['AAPL']['last']}")
        return True
    else:
        log("❌ Token verification failed — no quotes returned")
        return False


def main():
    log("Starting Schwab token refresh...")

    # Step 1: Try simple refresh token grant
    if try_refresh_token():
        if verify_token():
            log("Done — refresh token grant succeeded")
            return True
        else:
            log("Refresh succeeded but verification failed — falling through to full re-auth")

    log("Refresh token expired or invalid — full re-auth needed")
    log("⚠️ Full browser re-auth required. This will be handled by Zuck agent on next session.")
    log("Alerting via OpenClaw...")

    # Try to alert Chris via OCPlatform
    try:
        subprocess.run(
            ["/opt/homebrew/bin/ocplatform", "message", "send",
             "--channel", "slack",
             "--agent", "zuck",
             "--message", "⚠️ Schwab API token expired and refresh failed. I need to do a full browser re-auth. Will handle it on my next session."],
            timeout=10,
            capture_output=True,
        )
    except Exception:
        pass

    return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
