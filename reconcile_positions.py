#!/usr/bin/env python3
"""
reconcile_positions.py — Self-healing stop-loss guard + ledger reconciliation.

For EVERY live broker position, ensure there is a protective resting stop order
at the broker AND a matching OPEN active_trades row. If a position is "naked"
(held with no live sell/stop at the broker), place the stop and ledger it.

This is the safety net for the 2026-06-30 ITUB incident: a pre-market entry was
placed outside the normal engine flow, so neither the active_trades row nor the
protective stop ever got created, leaving the position unprotected until caught
by eye. This guard makes that self-healing — run it after the open.

Stop-price resolution priority (per ticker):
  1. OPEN active_trades.target_stop_price (the engine's tracked stop)
  2. output/agent4_orders.json trade_orders[].stop_loss (today's intended stop)
  3. output/portfolio_state.json hwm_stop (trailing high-water-mark stop)
  -> if none found, the position is reported as UNRESOLVED (no stop placed) so a
     human can decide; we never guess a stop out of thin air.

Authoritative "naked" detection: queries live broker orders for a resting
sell/stop on the symbol — does NOT trust the ledger alone (the ledger being out
of sync is exactly what caused the incident).

Idempotent. Use --dry-run to preview. Exit codes:
  0 = all positions protected (or healed)
  2 = one or more positions could not be protected (unresolved stop / API fail)
"""
import sys, json, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from broker_factory import get_broker

DB_PATH = "output/execution_ledger.db"
AGENT4_PATH = "output/agent4_orders.json"
PORTFOLIO_PATH = "output/portfolio_state.json"
DRY = "--dry-run" in sys.argv

# A protective stop sitting more than this fraction below the current price is
# "wide" — usually a reconciled position that fell back to a loose swing-low
# default (no thesis anchor). It IS protected, so we never auto-move it, but we
# surface it loudly so a human can tighten it to a real technical level. This is
# the 2026-07-06 TSM case: naked-guard armed a $419 stop while TSM was at $455.
WIDE_STOP_PCT = 0.05

# Broker order states that count as a LIVE resting order (still working).
LIVE_STATES = {"confirmed", "queued", "unconfirmed", "partially_filled", "new", "accepted"}


def load_agent4_stops() -> dict:
    """ticker -> stop_loss from today's Agent 4 orders."""
    out = {}
    try:
        with open(AGENT4_PATH) as f:
            data = json.load(f)
        for o in data.get("trade_orders", []):
            t = o.get("ticker")
            s = o.get("stop_loss")
            if t and s:
                out[t] = float(s)
    except Exception as e:
        print(f"[warn] could not read {AGENT4_PATH}: {e}")
    return out


def load_portfolio_stops() -> dict:
    """ticker -> hwm_stop from the trailing-stop state file."""
    out = {}
    try:
        with open(PORTFOLIO_PATH) as f:
            data = json.load(f)
        for t, v in data.items():
            s = v.get("hwm_stop")
            if s:
                out[t] = float(s)
    except Exception as e:
        print(f"[warn] could not read {PORTFOLIO_PATH}: {e}")
    return out


def has_live_stop(orders: list, ticker: str) -> Optional[dict]:
    """Return the live resting sell/stop order for ticker, if any."""
    for o in orders:
        if o.get("symbol") != ticker:
            continue
        if o.get("side") != "sell":
            continue
        if o.get("state") not in LIVE_STATES:
            continue
        # A protective order is either an explicit stop (has stop_price/trigger)
        # or any live sell that would close the position. We treat any live sell
        # as "protected" to avoid double-selling, but prefer stop orders.
        return o
    return None


def main():
    b = get_broker()
    positions = {p["ticker"]: p for p in b.get_positions() if float(p.get("shares", 0)) > 0}
    print(f"Broker reports {len(positions)} live positions: {sorted(positions)}")

    try:
        orders = b.get_orders_today()
    except Exception as e:
        print(f"[FATAL] could not fetch broker orders: {e}")
        sys.exit(2)

    a4_stops = load_agent4_stops()
    pf_stops = load_portfolio_stops()

    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row

    problems = 0
    wide_stops = []  # protected but too-loose stops flagged for human tightening

    for tkr, pos in sorted(positions.items()):
        shares = float(pos["shares"])
        avg = float(pos["avg_entry_price"])
        cur = float(pos.get("current_price", 0))

        existing = conn.execute(
            "SELECT trade_id, target_stop_price, stop_order_id, stop_status "
            "FROM active_trades WHERE ticker=? AND closed_at IS NULL",
            (tkr,)).fetchone()

        live = has_live_stop(orders, tkr)
        if live:
            sp = live.get("stop_price") or "(no stop_price)"
            print(f"[OK]   {tkr}: {shares} sh — live {live.get('type')} sell @ stop {sp} "
                  f"({live.get('state')}) order {live.get('id')}")
            # WIDE-STOP GUARD: protected, but is the stop absurdly loose vs the
            # current price? (Reconciled positions can fall back to a stale
            # swing-low default.) We never auto-move a live stop here, just flag.
            try:
                sp_val = float(live.get("stop_price")) if live.get("stop_price") else 0.0
            except (TypeError, ValueError):
                sp_val = 0.0
            if sp_val > 0 and cur > 0 and (cur - sp_val) / cur > WIDE_STOP_PCT:
                gap_pct = round((cur - sp_val) / cur * 100, 1)
                print(f"[WIDE] {tkr}: stop ${sp_val:.2f} is {gap_pct}% below current "
                      f"${cur:.2f} (> {int(WIDE_STOP_PCT*100)}%). Consider tightening.")
                wide_stops.append({"ticker": tkr, "stop": round(sp_val, 2),
                                   "current": round(cur, 2), "gap_pct": gap_pct})
            # Heal the ledger if it's missing the stop_order_id (cosmetic sync).
            if existing and not existing["stop_order_id"] and not DRY:
                conn.execute(
                    "UPDATE active_trades SET stop_order_id=?, stop_status='open', last_updated=? "
                    "WHERE trade_id=?",
                    (live.get("id"), datetime.now().isoformat(), existing["trade_id"]))
                conn.commit()
                print(f"        ↳ synced stop_order_id into ledger row {existing['trade_id']}")
            continue

        # ---- NAKED position: held with no live protective sell ----
        # Resolve a stop price.
        src = None
        stop = None
        if existing and existing["target_stop_price"]:
            stop, src = float(existing["target_stop_price"]), "ledger.target_stop"
        elif tkr in a4_stops:
            stop, src = a4_stops[tkr], "agent4_orders"
        elif tkr in pf_stops:
            stop, src = pf_stops[tkr], "portfolio_state.hwm_stop"

        if stop is None:
            problems += 1
            print(f"[NAKED] {tkr}: {shares} sh @ ${avg} (cur ${cur}) — NO STOP and NO "
                  f"resolvable stop price. MANUAL ACTION NEEDED.")
            continue

        if cur > 0 and stop >= cur:
            problems += 1
            print(f"[NAKED] {tkr}: {shares} sh — resolved stop ${stop} ({src}) >= current "
                  f"${cur}; would trigger immediately. NOT placing. MANUAL REVIEW.")
            continue

        risk = round((avg - stop) * shares, 2)
        print(f"[HEAL] {tkr}: {shares} sh @ ${avg} (cur ${cur}) NAKED -> placing stop "
              f"${stop} (src={src}) open_risk≈${risk}")

        if DRY:
            print(f"        [DRY] would ledger + place GTC stop_market sell {shares} @ ${stop}")
            continue

        # 1. upsert ledger row
        now = datetime.now().isoformat()
        trade_id = existing["trade_id"] if existing else f"recon-{tkr}-{uuid.uuid4().hex[:8]}"
        sh_val = int(round(shares)) if shares == int(shares) else shares
        if existing:
            conn.execute(
                "UPDATE active_trades SET target_shares=?, avg_fill_price=?, filled_shares=?, "
                "target_stop_price=?, entry_status='filled', last_updated=? WHERE trade_id=?",
                (sh_val, avg, shares, stop, now, trade_id))
        else:
            conn.execute(
                "INSERT INTO active_trades "
                "(trade_id,ticker,target_shares,limit_price,target_stop_price,entry_order_id,"
                "entry_status,filled_shares,avg_fill_price,created_at,last_updated) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (trade_id, tkr, sh_val, None, stop, "reconciled", "filled", shares, avg, now, now))
        conn.commit()

        # 2. place stop
        res = b.place_stop(tkr, shares, round(stop, 2), time_in_force="gtc")
        if res.get("ok"):
            sid = res["order_id"]
            conn.execute(
                "UPDATE active_trades SET stop_order_id=?, stop_status='open', last_updated=? "
                "WHERE trade_id=?",
                (sid, datetime.now().isoformat(), trade_id))
            conn.commit()
            print(f"        ✓ STOP PLACED {tkr} @ ${stop} -> {sid} (ledger {trade_id})")
        else:
            problems += 1
            print(f"        ✗ STOP FAILED {tkr}: {res.get('error')}")

    conn.close()

    if wide_stops:
        flags = ", ".join(f"{w['ticker']} (stop ${w['stop']}, {w['gap_pct']}% wide)"
                          for w in wide_stops)
        print(f"\n⚠️  WIDE-STOP WATCH — {len(wide_stops)} protected position(s) with a "
              f"loose stop >{int(WIDE_STOP_PCT*100)}% below price: {flags}. "
              f"Protected, but consider tightening to a technical level.")

    if problems:
        print(f"\nDONE with {problems} UNPROTECTED position(s) — see [NAKED]/FAILED above.",
              "(dry-run)" if DRY else "")
        sys.exit(2)
    print("\nDone. All live positions protected.", "(dry-run, nothing changed)" if DRY else "")
    sys.exit(0)


if __name__ == "__main__":
    main()
