"""
Open Claw — Watchlist Bench
Manages a persistent watchlist of Agent 2 candidates waiting for entry zones.
Candidates are promoted to READY when price pulls back to within 1% of the 20-day EMA.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
import numpy as np

WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "watchlist.json")


def _compute_ema_20(ticker: str) -> Optional[float]:
    """
    Fetch ~40 trading days of daily data and compute the 20-day EMA.
    Returns the EMA value or None on failure.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo")
        if hist.empty or len(hist) < 20:
            return None
        closes = hist["Close"].values
        # pandas EMA equivalent — use numpy for speed
        span = 20
        alpha = 2.0 / (span + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return round(float(ema), 4)
    except Exception:
        return None


def _is_bouncing(ticker: str) -> bool:
    """
    Momentum confirmation to avoid falling-knife entries.
    Fetches 5 days of daily history and checks whether the latest close
    is higher than the previous close (i.e., a green day / bounce).
    Returns False if the stock closed lower today than yesterday,
    meaning it may be crashing through the EMA rather than bouncing off it.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="5d")
        if hist.empty or len(hist) < 2:
            return False  # insufficient data → conservative, treat as falling
        closes = hist["Close"].values
        return bool(closes[-1] > closes[-2])
    except Exception:
        return False  # on error, be conservative


def _get_current_price(ticker: str) -> Optional[float]:
    """Fetch the current/last price for a ticker."""
    try:
        tk = yf.Ticker(ticker)
        # fast_info gives last price without heavy download
        price = tk.fast_info.get("lastPrice") or tk.fast_info.get("last_price")
        if price:
            return round(float(price), 4)
        # fallback: last close from history
        hist = tk.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 4)
        return None
    except Exception:
        return None


class Watchlist:
    """
    Persistent watchlist that stores Agent 2 candidates and monitors
    for pullback entries to the 20-day EMA zone.
    """

    def __init__(self, path: str = WATCHLIST_PATH):
        self.path = path
        self._entries: list[dict] = []
        self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._entries = []
        else:
            self._entries = []

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    # ── public API ───────────────────────────────────────────────

    def add(self, candidate: dict) -> dict:
        """
        Add a candidate from Agent 2 output to the watchlist.
        Computes the 20-day EMA as the target entry zone.
        Skips if ticker already on watchlist.
        """
        ticker = candidate.get("ticker", "").upper()
        if not ticker:
            return {"error": "No ticker in candidate"}

        # deduplicate
        if any(e["ticker"] == ticker for e in self._entries):
            return {"status": "already_on_watchlist", "ticker": ticker}

        ema_20 = _compute_ema_20(ticker)
        entry = {
            "ticker": ticker,
            "thesis": candidate.get("thesis", ""),
            "catalyst": candidate.get("catalyst", ""),
            "conviction_tier": candidate.get("conviction_tier", ""),
            "theme_match": candidate.get("theme_match", ""),
            "target_entry_zone": ema_20,
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "WATCHING",
            # Preserve full candidate data for downstream agents
            "_candidate": candidate,
        }
        self._entries.append(entry)
        self._save()
        return {"status": "added", "ticker": ticker, "ema_20": ema_20}

    def remove(self, ticker: str) -> bool:
        """Remove a ticker from the watchlist. Returns True if found."""
        ticker = ticker.upper()
        before = len(self._entries)
        self._entries = [e for e in self._entries if e["ticker"] != ticker]
        removed = len(self._entries) < before
        if removed:
            self._save()
        return removed

    def get_all(self) -> list[dict]:
        """Return all watchlist entries."""
        return list(self._entries)

    def prune(self, max_age_days: int = 5) -> list[str]:
        """
        Remove entries older than *max_age_days* trading days.
        (Approximation: calendar days × 5/7 ≈ trading days, but we use
        7 calendar days as a conservative proxy for 5 trading days.)
        Returns list of pruned tickers.
        """
        calendar_cutoff = 7  # ~5 trading days
        cutoff = (datetime.now() - timedelta(days=calendar_cutoff)).strftime("%Y-%m-%d")
        pruned = [e["ticker"] for e in self._entries if e.get("added_date", "9999") < cutoff]
        if pruned:
            self._entries = [e for e in self._entries if e["ticker"] not in pruned]
            self._save()
        return pruned

    def check_entries(self) -> list[dict]:
        """
        For each watchlist ticker, fetch current price.
        If price is within 1% above the 20-day EMA → promote to READY.
        Returns list of READY entries.
        """
        ready = []
        changed = False

        for entry in self._entries:
            ticker = entry["ticker"]
            ema_20 = entry.get("target_entry_zone")

            # Refresh EMA if missing
            if ema_20 is None:
                ema_20 = _compute_ema_20(ticker)
                entry["target_entry_zone"] = ema_20
                changed = True

            if ema_20 is None:
                continue

            current = _get_current_price(ticker)
            if current is None:
                continue

            # "Within 1% above the 20 EMA" means:
            #   price <= ema_20 * 1.01  (at or just above EMA)
            #   price >= ema_20 * 0.99  (not crashed far below — optional floor)
            # A pullback to EMA support means price is near/at EMA from above.
            pct_above_ema = ((current - ema_20) / ema_20) * 100

            if -1.0 <= pct_above_ema <= 1.0:
                # Momentum confirmation: avoid buying falling knives.
                # A stock crashing through the EMA from above will briefly
                # satisfy the ±1% zone but is NOT a healthy pullback entry.
                if _is_bouncing(ticker):
                    entry["status"] = "READY"
                    entry["current_price"] = current
                    entry["pct_above_ema"] = round(pct_above_ema, 2)
                    ready.append(entry)
                    changed = True
                else:
                    # Near EMA but still falling — don't promote yet
                    entry["status"] = "WATCHING_FALLING"
                    entry["current_price"] = current
                    entry["pct_above_ema"] = round(pct_above_ema, 2)
                    changed = True
            else:
                entry["current_price"] = current
                entry["pct_above_ema"] = round(pct_above_ema, 2)
                changed = True

        if changed:
            self._save()

        return ready


def promote_ready_candidates() -> list[dict]:
    """
    Check the watchlist and return READY candidates in Agent 2 output format
    so they can flow directly into Agent 3 → Agent 4.
    """
    wl = Watchlist()
    wl.prune()  # clean stale entries first
    ready_entries = wl.check_entries()

    # Convert back to Agent 2 candidate format
    candidates = []
    for entry in ready_entries:
        # Use stored original candidate if available, else reconstruct
        base = entry.get("_candidate", {})
        if not base:
            base = {
                "ticker": entry["ticker"],
                "thesis": entry.get("thesis", ""),
                "catalyst": entry.get("catalyst", ""),
                "conviction_tier": entry.get("conviction_tier", ""),
                "theme_match": entry.get("theme_match", ""),
                "type": "equity",
                "source": "Watchlist Bench",
            }
        # Tag it so downstream knows it came from watchlist
        base["source"] = "Watchlist Bench"
        base["watchlist_entry_zone"] = entry.get("target_entry_zone")
        base["watchlist_pct_above_ema"] = entry.get("pct_above_ema")
        candidates.append(base)

    # Remove promoted entries from watchlist to prevent re-buying
    if candidates:
        promoted_tickers = [c["ticker"] for c in candidates]
        wl._entries = [e for e in wl._entries if e["ticker"] not in promoted_tickers]
        wl._save()

    return candidates
