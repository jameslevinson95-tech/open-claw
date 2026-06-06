#!/usr/bin/env python3
"""
live_recap.py — Ground-truth account recap straight from the live broker.

No LLM, no templates, no stored state. Reads the actual Robinhood agentic
account and prints exactly what's there. Use this to sanity-check any
agent-generated recap (which can hallucinate holdings if it lacks live data).

Usage:  python3 live_recap.py
"""
import sys
import json
from datetime import datetime

sys.path.insert(0, ".")
from broker_factory import get_broker


def main():
    broker = get_broker("robinhood")
    summary = broker.get_account_summary()
    positions = broker.get_positions()

    rows = []
    positions_mv = 0.0
    net_pl = 0.0
    for p in positions:
        ticker = p["ticker"]
        shares = p["shares"]
        avg = p["avg_entry_price"]
        try:
            last = broker.get_quote(ticker)["last"]
        except Exception:
            last = p.get("current_price") or 0.0
        mv = shares * last
        cost = shares * avg
        pl = mv - cost
        plpc = (pl / cost * 100) if cost else 0.0
        positions_mv += mv
        net_pl += pl
        rows.append((ticker, shares, avg, last, mv, pl, plpc))

    acct = summary.get("account_number", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()

    print(f"🦞 Open Claw — Live Snapshot ({ts})")
    print(f"Account ···{str(acct)[-4:]}")
    print(f"Portfolio value: ${summary['portfolio_value']:,.2f}")
    print(f"Cash: ${summary['cash']:,.2f} | Buying power: ${summary.get('buying_power', 0):,.2f}")
    print(f"Positions market value: ${positions_mv:,.2f}")
    if not rows:
        print("Status: 100% CASH — no open positions")
    else:
        print(f"Status: {len(rows)} open position(s)")
        print(f"{'Ticker':<6} | {'Shares':>8} | {'Avg':>9} | {'Last':>9} | {'Mkt Val':>10} | {'Unreal P&L':>14}")
        for t, sh, avg, last, mv, pl, plpc in rows:
            print(f"{t:<6} | {sh:>8.4f} | ${avg:>8.2f} | ${last:>8.2f} | ${mv:>9.2f} | {pl:>+8.2f} ({plpc:>+5.1f}%)")
        print(f"Net open unrealized P&L: ${net_pl:+,.2f}")


if __name__ == "__main__":
    main()
