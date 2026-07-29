"""
Pipeline Safeguards — Production hardening for Open Claw.

1. Market Calendar Check (Holiday Trap Prevention)
2. Penalty Box / Cooldown Tracker (Whipsaw Prevention)
3. Liquidity Cap (ADDV Filter + Volume-Aware Sizing)
4. Earnings Screen (Binary Event Prevention)
5. Heartbeat & Failure Telemetry (Telegram Alerts)
"""
import json
import os
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OUTPUT_DIR = "output"
COOLDOWN_FILE = os.path.join(OUTPUT_DIR, "cooldown.json")
COOLDOWN_TRADING_DAYS = 5  # Min trading days before re-entry after a loss


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. MARKET CALENDAR CHECK — Holiday Trap Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _nyse_holidays(year: int) -> set:
    """Compute NYSE full-day market holidays for a given year (observed dates).

    Pure-Python US-market calendar so we don't depend on a broker API or an
    external package. Covers the standard NYSE holiday schedule.
    """
    from datetime import date, timedelta

    def observed(d: date) -> date:
        # If holiday falls on Saturday -> observed Friday; Sunday -> Monday.
        if d.weekday() == 5:
            return d - timedelta(days=1)
        if d.weekday() == 6:
            return d + timedelta(days=1)
        return d

    def nth_weekday(year, month, weekday, n):
        # n-th given weekday of month (weekday: Mon=0..Sun=6).
        d = date(year, month, 1)
        offset = (weekday - d.weekday()) % 7
        return d + timedelta(days=offset + 7 * (n - 1))

    def last_weekday(year, month, weekday):
        # Last given weekday of the month.
        if month == 12:
            nxt = date(year + 1, 1, 1)
        else:
            nxt = date(year, month + 1, 1)
        d = nxt - timedelta(days=1)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d

    def easter(year):
        # Anonymous Gregorian algorithm (Meeus/Jones/Butcher).
        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return date(year, month, day)

    hol = set()
    hol.add(observed(date(year, 1, 1)))                 # New Year's Day
    hol.add(nth_weekday(year, 1, 0, 3))                 # MLK Day (3rd Mon Jan)
    hol.add(nth_weekday(year, 2, 0, 3))                 # Presidents' Day (3rd Mon Feb)
    hol.add(easter(year) - timedelta(days=2))           # Good Friday
    hol.add(last_weekday(year, 5, 0))                   # Memorial Day (last Mon May)
    hol.add(observed(date(year, 6, 19)))               # Juneteenth
    hol.add(observed(date(year, 7, 4)))                # Independence Day
    hol.add(nth_weekday(year, 9, 0, 1))                # Labor Day (1st Mon Sep)
    hol.add(nth_weekday(year, 11, 3, 4))               # Thanksgiving (4th Thu Nov)
    hol.add(observed(date(year, 12, 25)))              # Christmas
    return hol


def is_market_open_today() -> dict:
    """
    Check if the US stock market (NYSE) is open today using a self-contained
    NYSE calendar (no broker API / external package required).
    Returns dict with is_open, should_run, and reason.

    should_run = True if today is a regular NYSE trading day.
    Note: this is a date-level (calendar) check, not an intraday clock; the
    pipeline runs are scheduled within market hours, so a day-level gate is
    sufficient to block weekends/holidays.
    """
    try:
        from datetime import time as _time
        now = datetime.now()
        today = now.date()

        # Weekend?
        if today.weekday() >= 5:  # 5 = Sat, 6 = Sun
            return {
                "is_open": False,
                "should_run": False,
                "reason": "weekend",
                "timestamp": now.isoformat(),
            }

        # Holiday?
        if today in _nyse_holidays(today.year):
            return {
                "is_open": False,
                "should_run": False,
                "reason": "market_holiday",
                "timestamp": now.isoformat(),
            }

        # Regular trading day. Intraday open = 9:30–16:00 ET (best-effort; the
        # host is configured to America/New_York for the trading pipeline).
        market_open = _time(9, 30)
        market_close = _time(16, 0)
        is_open_now = market_open <= now.time() <= market_close

        return {
            "is_open": is_open_now,
            "should_run": True,
            "reason": "market_is_open" if is_open_now else "trading_day_outside_hours",
            "timestamp": now.isoformat(),
        }
    except Exception as e:
        # Fail OPEN on a regular weekday so a calendar bug never silently blocks
        # the whole pipeline; weekends/holidays are handled above explicitly.
        print(f"[Safeguard] ⚠️ Market calendar check errored: {e}. Proceeding (fail-open on weekday).")
        wd = datetime.now().weekday()
        return {
            "is_open": None,
            "should_run": wd < 5,
            "reason": f"calendar_check_failed_fail_open_weekday: {e}",
        }


class MarketClosedError(Exception):
    """Raised when the pipeline is invoked on a market holiday or closed day."""
    pass


def assert_market_open():
    """
    Hard gate: raises MarketClosedError if the market is closed today.
    Call this at any pipeline entry point to prevent holiday runs.
    """
    cal = is_market_open_today()
    if cal.get("should_run") is False:
        reason = cal.get("reason", "unknown")
        msg = f"Market is CLOSED today ({reason}). Pipeline aborted."
        print(f"[Safeguard] 🚫 {msg}")
        raise MarketClosedError(msg)
    return cal


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. PENALTY BOX — Whipsaw & Wash Sale Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _load_cooldown() -> dict:
    """Load cooldown tracker from disk."""
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE) as f:
            return json.load(f)
    return {"tickers": {}}


def _save_cooldown(data: dict):
    """Save cooldown tracker to disk."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _estimate_expiry_date(trading_days: int) -> str:
    """
    Estimate the expiry date by adding trading_days (skipping weekends).
    Conservative: doesn't account for market holidays, so cooldown may
    expire slightly early on holiday weeks. Good enough.
    """
    date = datetime.now().date()
    days_added = 0
    while days_added < trading_days:
        date += timedelta(days=1)
        if date.weekday() < 5:  # Mon-Fri
            days_added += 1
    return date.isoformat()


def add_to_penalty_box(ticker: str, loss_amount: float, reason: str = "stop_loss"):
    """
    Add a ticker to the penalty box after a losing trade.
    
    IRS Wash Sale Rule: If a loss is realized, the ticker is locked for 31
    calendar days (IRS requires 30, we add 1 for safety). Buying back within
    this window disallows the tax deduction on the loss.
    
    For non-loss exits (breakeven, whipsaw), use the standard 5-trading-day
    cooldown to prevent re-entry into a choppy name.
    """
    cooldown = _load_cooldown()

    is_realized_loss = loss_amount > 0 and "breakeven" not in reason.lower()

    if is_realized_loss:
        # IRS 30-day calendar rule (31 to be safe)
        expiry_str = (datetime.now() + timedelta(days=31)).date().isoformat()
        lock_type = "IRS Wash Sale"
    else:
        # Standard 5-day whipsaw cooldown
        expiry_str = _estimate_expiry_date(COOLDOWN_TRADING_DAYS)
        lock_type = "Whipsaw Timeout"

    cooldown["tickers"][ticker] = {
        "added": datetime.now().isoformat(),
        "added_date": datetime.now().date().isoformat(),
        "expiry_date": expiry_str,
        "loss_amount": loss_amount,
        "reason": reason,
        "lock_type": lock_type,
        "trading_days_remaining": COOLDOWN_TRADING_DAYS,  # backward compat
    }
    _save_cooldown(cooldown)
    print(f"[Penalty Box] 🚫 {ticker} added — {lock_type} until {expiry_str} (loss: ${loss_amount:.2f})")


def tick_penalty_box():
    """
    Check date-based expiry for all tickers in the penalty box.
    Safe to call multiple times per day or across retries — expiry is
    date-stamped, not tick-based.
    """
    cooldown = _load_cooldown()
    expired = []
    today = datetime.now().date().isoformat()
    
    for ticker, info in list(cooldown["tickers"].items()):
        expiry = info.get("expiry_date")
        if expiry and today >= expiry:
            expired.append(ticker)
            del cooldown["tickers"][ticker]
        elif not expiry:
            # Legacy entry without expiry_date — fall back to old tick behavior
            remaining = info.get("trading_days_remaining", 0) - 1
            if remaining <= 0:
                expired.append(ticker)
                del cooldown["tickers"][ticker]
            else:
                info["trading_days_remaining"] = remaining
    
    _save_cooldown(cooldown)
    
    if expired:
        print(f"[Penalty Box] ✅ Released from cooldown: {', '.join(expired)}")
    
    active = list(cooldown["tickers"].keys())
    if active:
        for t in active:
            exp = cooldown["tickers"][t].get("expiry_date", "?")
            print(f"[Penalty Box] 🚫 {t} in cooldown until {exp}")
    
    return expired


def is_in_penalty_box(ticker: str) -> bool:
    """Check if a ticker is currently in the penalty box (date-based)."""
    cooldown = _load_cooldown()
    if ticker not in cooldown["tickers"]:
        return False
    info = cooldown["tickers"][ticker]
    expiry = info.get("expiry_date")
    if expiry and datetime.now().date().isoformat() >= expiry:
        return False  # Expired but not yet cleaned up
    return True


def get_penalty_box_tickers() -> list:
    """Get all tickers currently in the penalty box."""
    cooldown = _load_cooldown()
    return list(cooldown["tickers"].keys())


def filter_cooldown_tickers(screener: list) -> list:
    """
    Filter out any tickers that are in the penalty box.
    Call this in preflight before screener results reach the agents.
    """
    cooldown_tickers = get_penalty_box_tickers()
    if not cooldown_tickers:
        return screener
    
    filtered = [t for t in screener if t.get("ticker") not in cooldown_tickers]
    removed = [t["ticker"] for t in screener if t.get("ticker") in cooldown_tickers]
    
    if removed:
        print(f"[Penalty Box] Filtered {len(removed)} tickers from screener: {', '.join(removed)}")
    
    return filtered


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. LIQUIDITY CAP — ADDV Filter + Volume-Aware Sizing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIN_ADDV = 15_000_000  # $15M minimum Average Daily Dollar Volume
MAX_VOLUME_PCT = 0.01  # Never exceed 1% of 10-day average daily volume


def calculate_addv(ticker: str, bars: list) -> float:
    """
    Calculate 20-day Average Daily Dollar Volume.
    ADDV = avg(close * volume) over last 20 trading days.
    """
    if not bars or len(bars) < 5:
        return 0.0
    
    # Use last 20 bars (or however many we have)
    recent = bars[-20:]
    dollar_volumes = [b["close"] * b["volume"] for b in recent if b.get("close") and b.get("volume")]
    
    if not dollar_volumes:
        return 0.0
    
    return sum(dollar_volumes) / len(dollar_volumes)


def check_addv_filter(ticker: str, addv: float) -> dict:
    """Check if ticker passes the ADDV liquidity filter."""
    passes = addv >= MIN_ADDV
    return {
        "ticker": ticker,
        "addv": round(addv, 2),
        "min_addv": MIN_ADDV,
        "passes": passes,
        "reason": "OK" if passes else f"ADDV ${addv:,.0f} < ${MIN_ADDV:,.0f} minimum",
    }


def cap_shares_by_volume(shares: int, price: float, avg_daily_volume: float) -> dict:
    """
    Cap position size to 1% of 10-day average daily volume.
    Prevents becoming a significant portion of the order book.
    
    Args:
        shares: Proposed number of shares from risk sizing
        price: Current price per share
        avg_daily_volume: 10-day average daily volume (shares)
    
    Returns:
        dict with capped shares and whether the cap was binding.
    """
    if avg_daily_volume <= 0:
        return {
            "shares": shares,
            "capped": False,
            "reason": "no_volume_data",
        }
    
    max_shares = int(avg_daily_volume * MAX_VOLUME_PCT)
    
    if shares <= max_shares:
        return {
            "shares": shares,
            "capped": False,
            "max_shares_by_volume": max_shares,
            "pct_of_adv": round(shares / avg_daily_volume * 100, 3),
        }
    else:
        return {
            "shares": max_shares,
            "original_shares": shares,
            "capped": True,
            "max_shares_by_volume": max_shares,
            "pct_of_adv": round(max_shares / avg_daily_volume * 100, 3),
            "reason": f"Capped from {shares} to {max_shares} shares (1% of {avg_daily_volume:,.0f} ADV)",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. EARNINGS SCREEN — Binary Event Prevention
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EARNINGS_BUFFER_DAYS = 5  # Don't enter if earnings within 5 calendar days


def fetch_earnings_dates(tickers: list) -> dict:
    """
    Fetch next earnings date for each ticker.
    Uses yfinance (reliable for earnings dates).
    Returns {ticker: {"earnings_date": str, "days_until": int, "safe": bool}}
    """
    import yfinance as yf
    import datetime as _dt
    
    results = {}
    today = datetime.now().date()
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # yfinance provides earnings_dates as a DataFrame
            cal = stock.calendar
            
            earnings_date = None
            if cal is not None:
                if isinstance(cal, dict):
                    # Some versions return a dict
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list):
                            earnings_date = ed[0]
                        else:
                            earnings_date = ed
                elif hasattr(cal, "iloc"):
                    # DataFrame format
                    try:
                        earnings_date = cal.iloc[0, 0] if len(cal) > 0 else None
                    except Exception:
                        pass
            
            if earnings_date is not None:
                # NOTE: order matters. datetime.datetime is a SUBCLASS of
                # datetime.date and has .date(); a plain datetime.date does NOT.
                # yfinance >=0.2.x returns plain datetime.date here, which used to
                # fall through to ed=None and fail-closed EVERY ticker (the
                # "70/70 circuit breaker" symptom) — silently disabling the
                # earnings screen entirely. Check date first, then datetime.
                if isinstance(earnings_date, _dt.datetime):
                    ed = earnings_date.date()
                elif isinstance(earnings_date, _dt.date):
                    ed = earnings_date
                elif hasattr(earnings_date, "date") and callable(getattr(earnings_date, "date")):
                    # pandas.Timestamp and friends
                    ed = earnings_date.date()
                elif isinstance(earnings_date, str):
                    ed = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
                else:
                    ed = None
                
                if ed:
                    days_until = (ed - today).days
                    safe = days_until > EARNINGS_BUFFER_DAYS or days_until < 0
                    results[ticker] = {
                        "earnings_date": str(ed),
                        "days_until": days_until,
                        "safe": safe,
                        "reason": "OK" if safe else f"Earnings in {days_until} days — too close",
                    }
                else:
                    # No date parsed — fail-closed unless ETF
                    _etfs = {"SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "TLT", "HYG", "LQD", "JNK",
                             "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"}
                    if ticker.upper() in _etfs:
                        results[ticker] = {"earnings_date": None, "days_until": None, "safe": True, "reason": "ETF Bypass"}
                    else:
                        results[ticker] = {"earnings_date": None, "days_until": None, "safe": False, "reason": "no_date_parsed_fail_closed"}
            else:
                _etfs = {"SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "TLT", "HYG", "LQD", "JNK",
                         "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"}
                if ticker.upper() in _etfs:
                    results[ticker] = {"earnings_date": None, "days_until": None, "safe": True, "reason": "ETF Bypass"}
                else:
                    results[ticker] = {"earnings_date": None, "days_until": None, "safe": False, "reason": "no_earnings_data_fail_closed"}
        except Exception as e:
            results[ticker] = {"earnings_date": None, "days_until": None, "safe": False, "reason": f"fetch_error_fail_closed: {e}"}
    
    return results


def filter_earnings_tickers(screener: list) -> tuple:
    """
    Filter out tickers with earnings within EARNINGS_BUFFER_DAYS.
    Returns (filtered_screener, removed_tickers).
    """
    tickers = [t.get("ticker") for t in screener if t.get("ticker")]
    
    if not tickers:
        return screener, []
    
    print(f"[Earnings Screen] Checking {len(tickers)} tickers for upcoming earnings...")
    earnings = fetch_earnings_dates(tickers)
    
    # Circuit breaker: if a huge fraction of the universe is being removed ONLY
    # because the earnings-date source failed to fetch (not because of real
    # earnings proximity), the data source is broken — don't nuke the whole day.
    # yfinance's calendar endpoint is flaky/rate-limited and intermittently
    # returns None for every ticker, which previously fail-closed the entire
    # universe to 0 and produced no trades (see 2026-06-04 incident).
    FAIL_CLOSED_REASONS = ("no_date_parsed_fail_closed",
                           "no_earnings_data_fail_closed",
                           "fetch_error_fail_closed")
    BREAKER_THRESHOLD = 0.70  # if >70% of universe is fetch-failure removals

    def _is_fetch_failure(info: dict) -> bool:
        r = (info.get("reason") or "")
        return any(r.startswith(fc) for fc in FAIL_CLOSED_REASONS)

    total = len(tickers)
    unsafe = [t for t in tickers if not earnings.get(t, {}).get("safe", True)]
    fetch_failures = [t for t in unsafe if _is_fetch_failure(earnings.get(t, {}))]
    real_earnings = [t for t in unsafe if not _is_fetch_failure(earnings.get(t, {}))]

    source_broken = (
        total > 0
        and len(fetch_failures) / total >= BREAKER_THRESHOLD
        and len(fetch_failures) >= len(unsafe)  # essentially all removals are fetch fails
    )

    if source_broken:
        print(f"[Earnings Screen] ⚠️ CIRCUIT BREAKER TRIPPED — {len(fetch_failures)}/{total} "
              f"tickers fail-closed on DATA FETCH (source broken, not real earnings). "
              f"Passing through with earnings_unverified flag instead of nuking the universe.")

    removed = []
    filtered = []

    for entry in screener:
        ticker = entry.get("ticker")
        if ticker and ticker in earnings:
            info = earnings[ticker]
            if not info.get("safe", True):
                # Real earnings proximity → always remove (binary-event protection).
                if not _is_fetch_failure(info):
                    removed.append({"ticker": ticker, **info})
                    print(f"[Earnings Screen] 🚫 {ticker} — {info['reason']}")
                    continue
                # Fetch failure: if breaker tripped, pass through (flagged);
                # otherwise keep the original conservative fail-closed behavior.
                if source_broken:
                    entry = {**entry, "earnings_unverified": True}
                else:
                    removed.append({"ticker": ticker, **info})
                    print(f"[Earnings Screen] 🚫 {ticker} — {info['reason']}")
                    continue
        filtered.append(entry)

    if removed:
        print(f"[Earnings Screen] Filtered {len(removed)} tickers "
              f"({len(real_earnings)} real earnings, "
              f"{len(removed) - len(real_earnings)} fetch-fail)")
    else:
        print(f"[Earnings Screen] ✅ All tickers clear of near-term earnings")

    return filtered, removed


def filter_corporate_actions(screener: list) -> tuple:
    """
    Hard-block tickers that had a stock split in the last 7 days.
    Prevents hallucinated gaps and broken VaR math from adjusted historical prices.
    Uses DataProvider (Massive/Polygon splits endpoint) instead of yfinance.
    """
    import time as _time
    from data_provider import get_provider
    dp = get_provider()

    print(f"[Corp Actions] Checking {len(screener)} tickers for recent splits...")
    filtered, removed = [], []

    # Circuit breaker: split-checking is a non-fatal safeguard. If the splits
    # data source (Massive) is down/slow, don't let it stall the whole pipeline.
    # Trip after too many consecutive failures OR after a total time budget,
    # then pass the remaining tickers through unchecked.
    MAX_CONSECUTIVE_FAILURES = 5
    TIME_BUDGET_SEC = 45
    start_t = _time.time()
    consecutive_failures = 0
    breaker_tripped = False

    for entry in screener:
        ticker = entry.get("ticker")

        if breaker_tripped:
            # Source is unhealthy — pass remaining tickers without checking.
            filtered.append(entry)
            continue

        if _time.time() - start_t > TIME_BUDGET_SEC:
            print(f"[Corp Actions] ⏱ Time budget exceeded — skipping split check for remaining tickers (data source slow).")
            breaker_tripped = True
            filtered.append(entry)
            continue

        try:
            splits = dp.get_corporate_actions(ticker, since_days=7)
            consecutive_failures = 0  # success (even if empty) resets the counter
            if splits:
                split_info = splits[0]
                print(f"  [Corp Actions] {ticker} -- Recent split detected ({split_info.get('execution_date', '?')})")
                removed.append({"ticker": ticker, "reason": "Recent corporate action/split", "detail": split_info})
                continue
        except Exception as e:
            consecutive_failures += 1
            print(f"  [Corp Actions] {ticker}: split check failed ({e}) -- passing")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[Corp Actions] ⚠ {consecutive_failures} consecutive failures — data source appears down. "
                      f"Skipping split check for remaining tickers.")
                breaker_tripped = True
        filtered.append(entry)

    if breaker_tripped:
        print(f"[Corp Actions] Split check ended early (source unhealthy). Checked partial set; rest passed through.")
    if removed:
        print(f"[Corp Actions] Filtered {len(removed)} tickers with recent splits")
    else:
        print(f"[Corp Actions] All tickers clear of recent splits")

    return filtered, removed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. HEARTBEAT & FAILURE TELEMETRY — Telegram Alerts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def send_telegram(message: str):
    """
    Send a message to the configured Telegram chat.
    Used for alerts, heartbeats, and crash notifications.
    """
    import requests
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        print(f"[Telegram] ⚠️ No bot token or chat ID — message not sent: {message}")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
        
        if resp.status_code == 200:
            return True
        else:
            print(f"[Telegram] ⚠️ Send failed ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"[Telegram] ⚠️ Send error: {e}")
        return False


def send_crash_alert(agent_name: str, error: Exception):
    """Send a crash alert via Telegram."""
    tb = traceback.format_exc()
    # Truncate traceback for Telegram
    tb_short = tb[-500:] if len(tb) > 500 else tb
    
    message = (
        f"🚨 <b>OPEN CLAW CRASH</b>\n\n"
        f"<b>Agent:</b> {agent_name}\n"
        f"<b>Error:</b> {str(error)[:200]}\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n\n"
        f"<pre>{tb_short}</pre>\n\n"
        f"⚠️ Manual intervention may be required."
    )
    send_telegram(message)


def send_market_closed_alert():
    """Send alert that pipeline was skipped due to market closure."""
    message = (
        f"📅 <b>Market Closed Today</b>\n"
        f"Pipeline halted gracefully.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_hb_signal(positions: list = None, portfolio_heat: float = None, errors: list = None):
    """
    Send EOD heartbeat summary via Telegram.
    Call this at 4:00 PM ET.
    """
    pos_count = len(positions) if positions else 0
    heat_str = f"{portfolio_heat:.1f}%" if portfolio_heat is not None else "N/A"
    error_str = "No system errors" if not errors else f"{len(errors)} error(s): {', '.join(errors[:3])}"
    
    status_emoji = "🟢" if not errors else "🟡"
    
    message = (
        f"{status_emoji} <b>EOD Heartbeat</b>\n\n"
        f"<b>Open Positions:</b> {pos_count}\n"
        f"<b>Portfolio Heat:</b> {heat_str}\n"
        f"<b>Status:</b> {error_str}\n"
        f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_pipeline_start_alert():
    """Send a notification that the morning pipeline has started."""
    message = (
        f"🌅 <b>Open Claw Starting</b>\n"
        f"Morning entry pipeline initiated.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    )
    send_telegram(message)


def send_pipeline_complete_alert(results: dict):
    """Send a notification that the morning pipeline completed."""
    # Count successes
    agents_run = [k for k, v in results.items() if isinstance(v, dict)]
    successes = [k for k in agents_run if results[k].get("success", False)]
    failures = [k for k in agents_run if not results[k].get("success", True)]
    
    trades = results.get("broker", {}).get("fills", [])
    submitted = [f for f in trades if f.get("status") == "submitted"]
    
    status_emoji = "✅" if not failures else "⚠️"
    
    message = (
        f"{status_emoji} <b>Morning Pipeline Complete</b>\n\n"
        f"<b>Agents:</b> {len(successes)}/{len(agents_run)} succeeded\n"
        f"<b>Trades Submitted:</b> {len(submitted)}\n"
    )
    
    if submitted:
        for f in submitted:
            message += f"  • BUY {f.get('shares', '?')} {f.get('ticker', '?')}\n"
    
    if failures:
        message += f"\n<b>Failures:</b> {', '.join(failures)}\n"
    
    message += f"\n<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}"
    send_telegram(message)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pipeline wrapper with crash protection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_with_crash_protection(pipeline_fn, pipeline_name: str = "pipeline", **kwargs):
    """
    Wrapper that catches any unhandled exception in the pipeline
    and sends a Telegram crash alert before re-raising.
    """
    try:
        return pipeline_fn(**kwargs)
    except Exception as e:
        send_crash_alert(pipeline_name, e)
        raise


if __name__ == "__main__":
    print("=== Safeguards Smoke Test ===\n")
    
    # Test 1: Market calendar
    print("1. Market Calendar Check:")
    cal = is_market_open_today()
    print(f"   is_open={cal.get('is_open')}, should_run={cal.get('should_run')}, reason={cal.get('reason')}")
    
    # Test 2: Penalty box
    print("\n2. Penalty Box:")
    print(f"   Current cooldowns: {get_penalty_box_tickers()}")
    
    # Test 3: Liquidity
    print("\n3. Liquidity Cap:")
    cap = cap_shares_by_volume(100, 150.0, 500_000)
    print(f"   100 shares of $150 stock with 500K ADV: {cap}")
    cap2 = cap_shares_by_volume(10000, 150.0, 500_000)
    print(f"   10000 shares of $150 stock with 500K ADV: {cap2}")
    
    print("\n✅ Safeguards module ready!")
