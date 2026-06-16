#!/usr/bin/env python3
"""
reconcile_positions.py — One-time reconciliation of live open positions into the
execution ledger (active_trades) + place protective GTC stops.

Stops come from Agent 4's morning portfolio_heat.positions_detail (estimated_atr).
Idempotent: skips a ticker if it already has an OPEN active_trades row with a
live stop_order_id. Use --dry-run to preview.
"""
import sys, json, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from broker_factory import get_broker

DB_PATH = "output/execution_ledger.db"
DRY = "--dry-run" in sys.argv

# Authoritative stops from output/agent4_orders.json (08:14 run, estimated_atr)
STOPS = {
    "SMCI": 32.26,
    "CSCO": 117.47,
    "BAC":  52.31,
    "KVUE": 17.18,
    "GOOGL": 353.17,
    "HPE":  39.89,
}

def main():
    b = get_broker()
    positions = {p["ticker"]: p for p in b.get_positions()}
    print(f"Broker reports {len(positions)} positions: {sorted(positions)}")

    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row

    for tkr, stop in STOPS.items():
        pos = positions.get(tkr)
        if not pos:
            print(f"[SKIP] {tkr}: no live broker position")
            continue
        shares = float(pos["shares"])
        avg = float(pos["avg_entry_price"])
        cur = float(pos.get("current_price", 0))

        # idempotency: already tracked + has a live stop?
        existing = conn.execute(
            "SELECT trade_id, stop_order_id, stop_status FROM active_trades WHERE ticker=? AND closed_at IS NULL",
            (tkr,)).fetchone()
        if existing and existing["stop_order_id"]:
            print(f"[SKIP] {tkr}: already in ledger with stop {existing['stop_order_id']}")
            continue

        if stop >= cur and cur > 0:
            print(f"[WARN] {tkr}: stop ${stop} >= current ${cur} — would trigger immediately. SKIPPING stop placement, will still ledger it.")
            place = False
        else:
            place = True

        trade_id = existing["trade_id"] if existing else f"recon-{tkr}-{uuid.uuid4().hex[:8]}"
        risk = round((avg - stop) * shares, 2)
        print(f"\n{tkr}: {shares} sh @ ${avg} (cur ${cur}) -> stop ${stop}  open_risk≈${risk}")

        if DRY:
            print(f"   [DRY] would INSERT/UPDATE active_trades ({trade_id})")
            print(f"   [DRY] would place GTC stop_market sell {shares} @ ${stop}" if place else "   [DRY] would NOT place stop (see WARN)")
            continue

        # 1. upsert ledger row
        now = datetime.now().isoformat()
        if existing:
            conn.execute("UPDATE active_trades SET target_shares=?, avg_fill_price=?, filled_shares=?, target_stop_price=?, entry_status='filled', last_updated=? WHERE trade_id=?",
                         (int(round(shares)) if shares==int(shares) else shares, avg, shares, stop, now, trade_id))
        else:
            conn.execute("""INSERT INTO active_trades
                (trade_id,ticker,target_shares,limit_price,target_stop_price,entry_order_id,entry_status,filled_shares,avg_fill_price,created_at,last_updated)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (trade_id, tkr, int(round(shares)) if shares==int(shares) else shares, None, stop,
                 "reconciled", "filled", shares, avg, now, now))
        conn.commit()
        print(f"   ✓ ledgered {trade_id}")

        # 2. place stop
        if place:
            res = b.place_stop(tkr, shares, round(stop, 2), time_in_force="gtc")
            if res.get("ok"):
                sid = res["order_id"]
                conn.execute("UPDATE active_trades SET stop_order_id=?, stop_status='placed', last_updated=? WHERE trade_id=?",
                             (sid, datetime.now().isoformat(), trade_id))
                conn.commit()
                print(f"   ✓ STOP PLACED {tkr} @ ${stop} -> {sid}")
            else:
                print(f"   ✗ STOP FAILED {tkr}: {res.get('error')}")
    conn.close()
    print("\nDone.", "(dry-run, nothing changed)" if DRY else "(LIVE — ledger + stops updated)")

if __name__ == "__main__":
    main()
