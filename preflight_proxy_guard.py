#!/usr/bin/env python3
"""
Preflight Proxy Guard — Open Claw morning pipeline hardening.

WHY THIS EXISTS
---------------
On 2026-06-23 the 8 AM `open-claw-morning` cron failed all 3 model attempts
(opus-4-8 / 4-7 / 4-6) with `fetch failed (timeout)`. Root cause was NOT the
pipeline — it was the gateway->local-proxy path being unhealthy: the Claude
OAuth token-refresh loop had been logging `exit=1` failures overnight, so the
proxy couldn't complete upstream calls when the cron fired. It self-healed
later, but by then the 8 AM window was gone (no trades placed).

This guard runs as STEP 0 of the morning cron. It:
  1. Verifies the Claude OAuth credential is valid and not expiring soon.
     If it's stale/expiring, it force-triggers a refresh (claude ping) and
     re-checks.
  2. Health-checks the local model proxy (default 127.0.0.1:18801) with a real
     round-trip, retrying with exponential backoff.
  3. Exits 0 if the model path is healthy (cron proceeds), or exits non-zero
     after exhausting retries (cron should abort cleanly + alert).

Usage:
    python3 preflight_proxy_guard.py            # run the guard
    python3 preflight_proxy_guard.py --json     # machine-readable result

Exit codes:
    0  healthy — proceed with pipeline
    2  proxy unhealthy after retries
    3  credential could not be refreshed / still invalid
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
CREDS_FILE = Path.home() / ".claude" / ".credentials.json"
CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"
PROXY_URL = "http://127.0.0.1:18801/v1/messages"
# Token must have at least this long left, otherwise force a refresh first.
TOKEN_MIN_REMAINING_S = 600  # 10 minutes
# Proxy health-check retry schedule (seconds to wait BEFORE each attempt).
PROXY_BACKOFF = [0, 5, 15, 30, 60]
PROXY_TIMEOUT_S = 30
HEALTH_MODELS = ["claude-opus-4-8", "claude-opus-4-6"]  # primary + a fallback


def _log(msg: str):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} [proxy-guard] {msg}", flush=True)


# ── 1. Credential check + force refresh ─────────────────────────────────────
def _read_expiry_ms() -> int:
    try:
        d = json.loads(CREDS_FILE.read_text())
        return int(d.get("claudeAiOauth", {}).get("expiresAt", 0))
    except Exception:
        return 0


def _token_remaining_s() -> int:
    exp = _read_expiry_ms()
    if not exp:
        return -1
    return int((exp - time.time() * 1000) / 1000)


def _force_refresh() -> bool:
    """Trigger a token refresh via a tiny claude CLI ping. Returns True if the
    expiry advanced (refresh succeeded)."""
    before = _read_expiry_ms()
    if not CLAUDE_BIN.exists():
        _log(f"claude CLI not at {CLAUDE_BIN} — cannot force refresh")
        return False
    try:
        subprocess.run(
            [str(CLAUDE_BIN), "-p", "ping", "--max-turns", "1",
             "--no-session-persistence"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=90,
        )
    except Exception as e:
        _log(f"refresh ping errored: {e}")
    after = _read_expiry_ms()
    return after > before


def ensure_token_healthy() -> dict:
    remaining = _token_remaining_s()
    if remaining >= TOKEN_MIN_REMAINING_S:
        _log(f"token OK — {remaining}s remaining")
        return {"ok": True, "remaining_s": remaining, "refreshed": False}

    _log(f"token low/expired ({remaining}s) — forcing refresh...")
    for attempt in range(1, 4):
        if _force_refresh():
            remaining = _token_remaining_s()
            _log(f"refresh succeeded — {remaining}s remaining")
            return {"ok": True, "remaining_s": remaining, "refreshed": True}
        _log(f"refresh attempt {attempt}/3 did not advance expiry; retrying in 10s")
        time.sleep(10)

    remaining = _token_remaining_s()
    ok = remaining >= 60  # accept if it at least has a usable minute
    _log(f"refresh exhausted — {remaining}s remaining (ok={ok})")
    return {"ok": ok, "remaining_s": remaining, "refreshed": False}


# ── 2. Proxy health check w/ backoff ────────────────────────────────────────
def _ping_proxy(model: str) -> tuple:
    """Returns (ok, status_or_err, elapsed_s)."""
    body = json.dumps({
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "reply OK"}],
    }).encode()
    req = urllib.request.Request(
        PROXY_URL, data=body,
        headers={"content-type": "application/json"}, method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_S) as r:
            r.read()
            return (r.status == 200, r.status, time.time() - t0)
    except urllib.error.HTTPError as e:
        return (False, f"HTTP {e.code}", time.time() - t0)
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}", time.time() - t0)


def ensure_proxy_healthy() -> dict:
    last = None
    for i, wait in enumerate(PROXY_BACKOFF, 1):
        if wait:
            _log(f"backing off {wait}s before proxy attempt {i}/{len(PROXY_BACKOFF)}")
            time.sleep(wait)
        model = HEALTH_MODELS[(i - 1) % len(HEALTH_MODELS)]
        ok, info, elapsed = _ping_proxy(model)
        last = {"model": model, "info": info, "elapsed_s": round(elapsed, 2)}
        if ok:
            _log(f"proxy healthy via {model} — {info} in {elapsed:.2f}s")
            return {"ok": True, **last}
        _log(f"proxy attempt {i} failed ({model}): {info} after {elapsed:.2f}s")
    _log("proxy unhealthy after all retries")
    return {"ok": False, **(last or {})}


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON result")
    args = ap.parse_args()

    tok = ensure_token_healthy()
    if not tok["ok"]:
        result = {"healthy": False, "stage": "token", "token": tok}
        if args.json:
            print(json.dumps(result))
        _log("ABORT: token unhealthy")
        sys.exit(3)

    proxy = ensure_proxy_healthy()
    healthy = proxy["ok"]
    result = {"healthy": healthy, "stage": "proxy", "token": tok, "proxy": proxy}
    if args.json:
        print(json.dumps(result))

    if healthy:
        _log("PREFLIGHT PASS — model path healthy, pipeline may proceed")
        sys.exit(0)
    else:
        _log("ABORT: proxy unhealthy after retries")
        sys.exit(2)


if __name__ == "__main__":
    main()
