#!/usr/bin/env python3
"""
intraday_trail.py — Intraday Trailing-Stop Ratchet (every ~15 min)

WHY THIS EXISTS
---------------
The trailing-stop TIER recompute (+2.5% -> breakeven, +3% -> +25% of gains,
... +15% -> +85%) historically only ran ONCE a day inside agent5 at 3:30 PM.
Between runs the stop sat static — so an intraday spike to +8% that faded back
to +1% by close never got its gains locked in.

This module runs the SAME tier math against the SAME paid Tiingo feed on a tight
intraday cadence and ratchets the broker stop UP whenever the live price earns
a tighter tier. It NEVER loosens a stop (HWM-enforced by the reused calculator).

DESIGN — deliberately conservative:
  * REUSES agent5's exact functions (no re-implemented math => no drift):
        load_open_positions(), snapshot_prices(), calculate_trailing_stops()
  * Pushes ONLY stop tightenings ("HOLD_STOP_TIGHTENED"), via the ATOMIC
    ExecutionEngine.update_trailing_stop() path (cancel-old -> confirm-new).
  * Does NOT execute TRIM or CLOSE intraday. Scale-outs and mechanical/thesis
    closes stay on the 3:30 PM agent5 pass + Claude thesis review. A single
    intraday tick should tighten protection, never liquidate the book.
  * HWM state (output/portfolio_state.json) is shared with agent5, so the 3:30
    run picks up right where intraday left off (ratchet is monotonic).

USAGE
-----
    python3 intraday_trail.py            # do it for real
    python3 intraday_trail.py --dry-run  # compute + print, push nothing
    python3 intraday_trail.py --json     # machine-readable summary line

Intended to be called by a cron every 15 min during market hours (9:45–15:30),
BEFORE the 3:30 agent5 pass takes over for the full tier+thesis+scale run.

Exit codes:
    0  ran clean (whether or not anything was tightened)
    1  hard error (couldn't load positions / broker unreachable)
"""
import sys
import json
import argparse
from datetime import datetime

import os

from agent5_position_monitor import (
    load_open_positions,
    snapshot_prices,
    calculate_trailing_stops,
)

# The EOD stop digest (4:00 PM) parses the day's reinforce log for lines like
# "TICKER: ... HWM updated: $X -> $Y". The 30-min launchd reinforce writes there;
# this 15-min intraday trail historically did NOT, so intraday-only ratchets were
# invisible in the daily summary. We now append applied intraday ratchets to the
# SAME log in the SAME format so the digest picks them up with zero changes.
_BASE = os.path.dirname(os.path.abspath(__file__))
_REINFORCE_LOG = os.path.join(
    _BASE, "output", "logs", f"hourly_reinforce_{datetime.now():%Y-%m-%d}.log"
)


def _log_ratchet_for_digest(ticker: str, prev_stop, new_stop) -> None:
    """Append an applied intraday ratchet in the digest's parse format."""
    if not prev_stop or not new_stop:
        return
    try:
        os.makedirs(os.path.dirname(_REINFORCE_LOG), exist_ok=True)
        with open(_REINFORCE_LOG, "a") as f:
            f.write(
                f"[IntradayTrail {datetime.now():%H:%M}] {ticker}: intraday ratchet "
                f"[HWM updated: ${prev_stop:.2f} -> ${new_stop:.2f}]\n"
            )
    except Exception:
        # Never let a logging hiccup break the actual stop push.
        pass


def run_intraday_trail(dry_run: bool = False) -> dict:
    """Compute tier stops off the live feed and ratchet UP-only tightenings."""
    positions = load_open_positions()
    if not positions:
        return {"status": "ok", "positions": 0, "tightened": [], "note": "no open positions"}

    tickers = [p["ticker"] for p in positions]
    snapshot = snapshot_prices(tickers)

    # This is the SAME pure function agent5 uses. It also persists the HWM
    # (high-water-mark) state to output/portfolio_state.json, so the 3:30 PM
    # agent5 run inherits every intraday ratchet automatically.
    enriched = calculate_trailing_stops(positions, snapshot)

    tightened = []
    skipped_scale_close = []

    for pos in enriched:
        ticker = pos["ticker"]
        new_stop = pos.get("new_stop")
        original_stop = pos.get("original_stop", pos.get("stop_loss", 0))
        mech = pos.get("mechanical_action", "HOLD")

        # HARD RULE: intraday pass only TIGHTENS stops. If the reused calculator
        # says the price is already <= stop (mechanical CLOSE) or a scale-out is
        # due, we DO NOT act on it here — the native broker stop is already
        # sitting there to catch a real breach, and TRIM/CLOSE decisions belong
        # to the 3:30 agent5 pass (+ thesis review). Just record + move on.
        if mech == "CLOSE" or pos.get("scale_action"):
            skipped_scale_close.append({
                "ticker": ticker,
                "reason": "mechanical_close" if mech == "CLOSE" else "scale_due",
                "pnl_pct": pos.get("pnl_pct"),
                "note": "left for 3:30 agent5 pass",
            })
            continue

        # Only push a REAL upward move (calculator already enforces monotonic
        # via HWM, but we double-gate here so we never spam the broker with
        # no-op cancel/replace churn on flat ticks).
        if not new_stop or new_stop <= 0:
            continue
        if original_stop and round(new_stop, 2) <= round(original_stop, 2):
            continue

        rec = {
            "ticker": ticker,
            "prev_stop": round(original_stop, 2) if original_stop else None,
            "new_stop": round(new_stop, 2),
            "current_price": pos.get("current_price"),
            "pnl_pct": pos.get("pnl_pct"),
            "note": pos.get("trailing_stop_note", ""),
        }

        if dry_run:
            rec["applied"] = False
            tightened.append(rec)
            continue

        # Push via the SAME atomic trailing path agent5's broker layer uses.
        try:
            from execution_engine import ExecutionEngine
            engine = ExecutionEngine()
            ok = engine.update_trailing_stop(ticker, round(new_stop, 2))
            if not ok and hasattr(engine, "update_stop"):
                # Non-atomic fallback (matches robinhood_broker behavior).
                ok = engine.update_stop(ticker, round(new_stop, 2), reason="IntradayTrail")
            rec["applied"] = bool(ok)
            if ok:
                # Record it so the 4 PM EOD digest sees intraday ratchets too.
                _log_ratchet_for_digest(ticker, original_stop, round(new_stop, 2))
            else:
                rec["error"] = "broker update returned falsy"
        except Exception as e:
            rec["applied"] = False
            rec["error"] = str(e)

        tightened.append(rec)

    return {
        "status": "ok",
        "positions": len(positions),
        "tightened": tightened,
        "skipped": skipped_scale_close,
        "ts": datetime.now().isoformat(),
    }


def main():
    ap = argparse.ArgumentParser(description="Intraday trailing-stop ratchet (15-min).")
    ap.add_argument("--dry-run", action="store_true", help="compute + print, push nothing")
    ap.add_argument("--json", action="store_true", help="emit one machine-readable JSON line")
    args = ap.parse_args()

    # Only run during regular trading hours; outside that there's nothing to do.
    try:
        from safeguards import is_market_open_today
        cal = is_market_open_today()
        if not cal.get("is_open", cal.get("open", False)):
            out = {"status": "ok", "positions": 0, "tightened": [], "note": "market closed"}
            print(json.dumps(out) if args.json else "Market closed — nothing to do.")
            sys.exit(0)
    except Exception:
        # If the calendar check itself fails, don't block a real ratchet — the
        # cron only fires on weekdays during hours anyway.
        pass

    try:
        result = run_intraday_trail(dry_run=args.dry_run)
    except Exception as e:
        msg = {"status": "error", "error": str(e)}
        print(json.dumps(msg) if args.json else f"ERROR: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result))
    else:
        n = len(result.get("tightened", []))
        applied = sum(1 for t in result["tightened"] if t.get("applied"))
        mode = "DRY-RUN" if args.dry_run else "LIVE"
        print(f"[{mode}] {result['positions']} positions checked, "
              f"{n} tier-tightenings ({applied} pushed to broker).")
        for t in result.get("tightened", []):
            flag = "✅" if t.get("applied") else ("🔎" if args.dry_run else "⚠️")
            print(f"  {flag} {t['ticker']}: ${t.get('prev_stop')} → ${t['new_stop']} "
                  f"(price ${t.get('current_price')}, {t.get('pnl_pct')}%) — {t.get('note','')}"
                  + (f"  [{t['error']}]" if t.get("error") else ""))
        for s in result.get("skipped", []):
            print(f"  ⏭️  {s['ticker']}: {s['reason']} ({s.get('pnl_pct')}%) — {s['note']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
