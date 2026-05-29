"""
execution_engine.py — Stateful Execution Ledger & Daemon

Replaces naive fire-and-forget execution with atomic operations
and SQLite state tracking. Acts as the local clearinghouse since
Robinhood MCP lacks native OTO (bracket) order support.

Architecture (credit: Gemini code review):
1. Orchestrator submits trade *intents* (entry + stop price)
2. Engine routes entry order to broker, records in SQLite ledger
3. Background daemon polls order status every ~15 seconds
4. On fill detection → immediately places stop-loss order
5. On partial fill + price crash through stop → panic liquidation
6. Atomic liquidation: cancel resting orders → wait → market sell

Requires: pip install filelock
"""
import json
import os
import sqlite3
import time
import uuid
import logging
from datetime import datetime
from pathlib import Path

from filelock import FileLock, Timeout

from broker_factory import get_broker

DB_PATH = Path("output/execution_ledger.db")
LOCK_PATH = Path("output/broker_state.lock")
HEARTBEAT_PATH = Path("output/daemon_hb_signal.txt")
RECONCILE_INTERVAL = 15  # seconds between daemon loops (Robinhood rate-limit safe)
HEARTBEAT_INTERVAL = 10  # seconds between heartbeat writes
HEARTBEAT_MAX_AGE = 60   # seconds before heartbeat is considered stale

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("output/execution_engine.log"),
    ],
)
logger = logging.getLogger("ExecutionEngine")


class ExecutionEngine:
    """
    Stateful execution layer that bridges the orchestrator's trade intents
    with the broker's async order lifecycle.
    """

    def __init__(self, broker=None):
        self.broker = broker or get_broker()
        self._init_db()

    def _init_db(self):
        """Initialize the local state reconciliation ledger."""
        DB_PATH.parent.mkdir(exist_ok=True)
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            # WAL mode for concurrent daemon + orchestrator access
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_trades (
                    trade_id        TEXT PRIMARY KEY,
                    ticker          TEXT NOT NULL,
                    target_shares   INTEGER NOT NULL,
                    limit_price     REAL,
                    target_stop_price REAL NOT NULL,
                    entry_order_id  TEXT,
                    entry_status    TEXT DEFAULT 'pending',
                    filled_shares   INTEGER DEFAULT 0,
                    avg_fill_price  REAL,
                    stop_order_id   TEXT,
                    stop_status     TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated    TIMESTAMP,
                    closed_at       TIMESTAMP,
                    close_reason    TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id    TEXT,
                    ticker      TEXT,
                    event       TEXT NOT NULL,
                    detail      TEXT,
                    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _log_event(self, trade_id: str, ticker: str, event: str, detail: str = ""):
        """Append to the execution audit trail."""
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            conn.execute(
                "INSERT INTO execution_log (trade_id, ticker, event, detail) VALUES (?, ?, ?, ?)",
                (trade_id, ticker, event, detail),
            )
            conn.commit()

    # ── Orchestrator Interface ───────────────────────────────────────────

    def submit_trade_intent(
        self,
        trade_id: str,
        ticker: str,
        shares: int,
        limit_price: float,
        stop_price: float,
    ) -> dict:
        """
        Orchestrator calls this instead of calling the broker directly.
        Routes the entry order and records the intent in the ledger.
        The daemon will handle stop placement after fill.
        """
        try:
            lock = FileLock(LOCK_PATH, timeout=10)
            with lock:
                logger.info(
                    f"Routing intent: BUY {shares} {ticker} @ ${limit_price:.2f} "
                    f"(stop: ${stop_price:.2f})"
                )

                # Submit entry order to broker
                res = self.broker.place_order(
                    ticker=ticker,
                    side="buy",
                    order_type="limit",
                    quantity=str(shares),
                    limit_price=str(round(limit_price, 2)),
                )

                order_id = res.get("order_id") or res.get("id")
                if not order_id:
                    logger.error(f"Broker rejected entry for {ticker}: {res}")
                    self._log_event(trade_id, ticker, "ENTRY_REJECTED", json.dumps(res))
                    return {"ticker": ticker, "status": "rejected", "reason": str(res)}

                # Record in ledger
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.execute(
                        """INSERT INTO active_trades
                        (trade_id, ticker, target_shares, limit_price,
                         target_stop_price, entry_order_id, entry_status, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
                        (
                            trade_id, ticker, shares, limit_price,
                            stop_price, order_id, datetime.now().isoformat(),
                        ),
                    )
                    conn.commit()

                self._log_event(trade_id, ticker, "ENTRY_SUBMITTED", f"order_id={order_id}")
                logger.info(f"✅ {ticker} entry submitted: {order_id}")
                return {"ticker": ticker, "status": "submitted", "order_id": order_id}

        except Timeout:
            logger.error(f"Lock timeout submitting intent for {ticker}")
            return {"ticker": ticker, "status": "error", "reason": "lock_timeout"}

    def submit_batch_intents(self, trade_orders: list) -> list:
        """
        Submit multiple trade intents from a tear sheet.
        Drop-in replacement for broker.execute_tear_sheet().
        """
        results = []
        for order in trade_orders:
            if order.get("action") != "BUY":
                results.append({
                    "ticker": order.get("ticker", "?"),
                    "status": "skipped",
                    "reason": order.get("reason", order.get("action", "not a BUY")),
                })
                continue

            trade_id = str(uuid.uuid4())
            # Use the limit price as-is — slippage allowance is already applied
            # upstream in orchestrator.py (marketable limit = ask * 1.0015)
            entry_price = order.get("entry_price", order.get("limit_price", 0))
            limit_price = round(entry_price, 2)
            stop_price = order.get("stop_loss", 0)
            shares = order.get("shares", 0)

            if not all([entry_price, stop_price, shares]):
                results.append({
                    "ticker": order.get("ticker", "?"),
                    "status": "skipped",
                    "reason": "missing entry_price, stop_loss, or shares",
                })
                continue

            result = self.submit_trade_intent(
                trade_id=trade_id,
                ticker=order["ticker"],
                shares=shares,  # Allow fractional shares (Robinhood supports them)
                limit_price=limit_price,
                stop_price=stop_price,
            )
            results.append(result)

        submitted = sum(1 for r in results if r.get("status") == "submitted")
        logger.info(
            f"📋 Batch complete: {submitted}/{len(results)} intents submitted to ledger"
        )
        return results

    # ── Atomic Liquidation ───────────────────────────────────────────────

    def atomic_liquidate(self, ticker: str, reason: str) -> dict:
        """
        The Nuclear Option — Flash Crash / Agent 5 CLOSE.
        Safely clears encumbered shares before dumping inventory.

        Sequence:
        1. Cancel ALL resting orders for this ticker (pending entries, stops)
        2. Wait for clearinghouse to release encumbered shares
        3. Fetch actual settled position
        4. Market sell everything
        5. Remove from ledger
        """
        try:
            lock = FileLock(LOCK_PATH, timeout=15)
            with lock:
                logger.warning(f"🚨 ATOMIC LIQUIDATION: {ticker} ({reason})")

                # 1. Find all open orders for this ticker
                all_orders = self.broker.get_orders_today()
                open_orders = [
                    o for o in all_orders
                    if o.get("ticker") == ticker
                    and o.get("status", "").lower() in ("open", "partially_filled", "queued", "confirmed")
                ]

                # 2. Cancel them all
                for o in open_orders:
                    oid = str(o.get("id") or o.get("order_id"))
                    logger.info(f"  Canceling resting order {oid} for {ticker}...")
                    try:
                        self.broker.cancel_order(oid)
                    except Exception as e:
                        logger.error(f"  Cancel failed for {oid}: {e}")

                # 3. Wait for clearinghouse to release shares (max 10s)
                if open_orders:
                    timeout = time.time() + 10
                    while time.time() < timeout:
                        remaining = [
                            o for o in self.broker.get_orders_today()
                            if o.get("ticker") == ticker
                            and o.get("status", "").lower() in ("open", "partially_filled", "queued", "confirmed")
                        ]
                        if not remaining:
                            logger.info(f"  Clearinghouse confirms shares unencumbered for {ticker}")
                            break
                        time.sleep(1.5)
                    else:
                        logger.error(
                            f"  Timeout waiting for {ticker} cancels to clear. "
                            "Market sell may fail due to encumbered shares."
                        )

                # 4. Check actual position
                positions = self.broker.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)

                if not pos or float(pos.get("shares", 0)) <= 0:
                    logger.info(f"  No inventory found for {ticker} — nothing to sell")
                    result = {"ticker": ticker, "action": "LIQUIDATED", "shares_sold": 0}
                else:
                    # 5. Market sell everything
                    shares_to_sell = int(float(pos["shares"]))
                    res = self.broker.place_order(
                        ticker=ticker,
                        side="sell",
                        order_type="market",
                        quantity=str(shares_to_sell),
                    )
                    sell_id = res.get("order_id") or res.get("id")
                    logger.info(
                        f"  Market SELL {shares_to_sell} {ticker} routed: {sell_id}"
                    )
                    result = {
                        "ticker": ticker,
                        "action": "LIQUIDATED",
                        "shares_sold": shares_to_sell,
                        "sell_order_id": sell_id,
                    }

                # 6. Clean up ledger
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.execute(
                        "UPDATE active_trades SET closed_at = ?, close_reason = ? WHERE ticker = ? AND closed_at IS NULL",
                        (datetime.now().isoformat(), reason, ticker),
                    )
                    conn.commit()

                self._log_event("", ticker, "ATOMIC_LIQUIDATION", reason)
                return result

        except Timeout:
            logger.error(f"Lock timeout during atomic liquidation for {ticker}")
            return {"ticker": ticker, "action": "LIQUIDATION_FAILED", "reason": "lock_timeout"}

    # ── Update Stop Price (for trailing / tightening) ────────────────────

    def update_stop(self, ticker: str, new_stop_price: float, reason: str = "manual"):
        """
        Update the target stop price for a ticker.
        Cancels the existing stop order — the daemon will place the new one.
        """
        try:
            lock = FileLock(LOCK_PATH, timeout=10)
            with lock:
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    # Get current trade
                    row = conn.execute(
                        "SELECT trade_id, stop_order_id FROM active_trades WHERE ticker = ? AND closed_at IS NULL",
                        (ticker,),
                    ).fetchone()

                    if not row:
                        logger.warning(f"No active trade for {ticker} to update stop")
                        return

                    trade_id, old_stop_id = row

                    # Cancel existing stop if placed
                    if old_stop_id:
                        try:
                            self.broker.cancel_order(old_stop_id)
                            logger.info(f"Canceled old stop {old_stop_id} for {ticker}")
                        except Exception as e:
                            logger.error(f"Failed to cancel old stop for {ticker}: {e}")

                    # Update ledger — daemon will detect NULL stop_order_id and place new one
                    conn.execute(
                        "UPDATE active_trades SET target_stop_price = ?, stop_order_id = NULL, stop_status = NULL, last_updated = ? WHERE trade_id = ?",
                        (new_stop_price, datetime.now().isoformat(), trade_id),
                    )
                    conn.commit()

                self._log_event(trade_id, ticker, "STOP_UPDATED", f"new_stop=${new_stop_price:.2f} reason={reason}")
                logger.info(f"📝 {ticker} stop updated to ${new_stop_price:.2f} ({reason})")

        except Timeout:
            logger.error(f"Lock timeout updating stop for {ticker}")

    def update_trailing_stop(self, ticker: str, new_stop_price: float) -> bool:
        """
        Safely tightens a stop loss. Atomic: cancel old → WAIT for clearinghouse → place new.
        Unlike update_stop() which delegates to the daemon, this method blocks until
        the new stop is confirmed placed. Use for time-critical trailing (flash crash, etc.).
        """
        try:
            lock = FileLock(LOCK_PATH, timeout=15)
            with lock:
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.row_factory = sqlite3.Row
                    trade = conn.execute(
                        "SELECT * FROM active_trades WHERE ticker = ? AND stop_order_id IS NOT NULL AND closed_at IS NULL",
                        (ticker,),
                    ).fetchone()

                    if not trade:
                        logger.warning(f"No active stop found for {ticker} to trail.")
                        return False

                    trade = dict(trade)
                    old_stop_id = trade["stop_order_id"]
                    filled_shares = trade["filled_shares"]

                # 1. Cancel old stop
                try:
                    self.broker.cancel_order(old_stop_id)
                    logger.info(f"Canceled old stop {old_stop_id} for {ticker}")
                except Exception as e:
                    logger.error(f"Failed to cancel old stop {old_stop_id} for {ticker}: {e}")

            # 2. Blocking wait for shares to unencumber (OUTSIDE lock to avoid deadlock)
            timeout_at = time.time() + 10
            unencumbered = False
            while time.time() < timeout_at:
                try:
                    open_orders = self.broker.get_orders_today()
                    if not any(
                        str(o.get("id") or o.get("order_id")) == old_stop_id
                        and o.get("status", "").lower() in ("open", "pending_cancel", "queued", "new")
                        for o in open_orders
                    ):
                        unencumbered = True
                        break
                except Exception:
                    pass
                time.sleep(1.0)

            if not unencumbered:
                logger.error(f"Timeout waiting for old stop {old_stop_id} to clear for {ticker}. Position temporarily naked.")
                # Re-register with daemon so it can recover
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.execute(
                        "UPDATE active_trades SET target_stop_price = ?, stop_order_id = NULL, stop_status = NULL, last_updated = ? WHERE trade_id = ?",
                        (new_stop_price, datetime.now().isoformat(), trade["trade_id"]),
                    )
                    conn.commit()
                return False

            # 3. Place new stop
            stop_res = self.broker.place_order(
                ticker=ticker,
                side="sell",
                order_type="stop",
                quantity=str(filled_shares),
                stop_price=str(round(new_stop_price, 2)),
                time_in_force="gtc",
            )
            new_stop_id = stop_res.get("order_id") or stop_res.get("id")

            if new_stop_id:
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.execute(
                        "UPDATE active_trades SET target_stop_price = ?, stop_order_id = ?, stop_status = 'open', last_updated = ? WHERE trade_id = ?",
                        (new_stop_price, new_stop_id, datetime.now().isoformat(), trade["trade_id"]),
                    )
                    conn.commit()
                self._log_event(trade["trade_id"], ticker, "TRAILING_STOP_PLACED", f"new_stop=${new_stop_price:.2f} id={new_stop_id}")
                logger.info(f"✅ Successfully trailed stop for {ticker} to ${new_stop_price:.2f}")
                return True
            else:
                logger.critical(f"Failed to place new stop for {ticker} after canceling old stop! Position is naked.")
                # Fallback: let daemon recover
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.execute(
                        "UPDATE active_trades SET target_stop_price = ?, stop_order_id = NULL, stop_status = NULL, last_updated = ? WHERE trade_id = ?",
                        (new_stop_price, datetime.now().isoformat(), trade["trade_id"]),
                    )
                    conn.commit()
                return False

        except Timeout:
            logger.error(f"Lock timeout during trailing stop update for {ticker}")
            return False

    # ── Background Reconciliation Daemon ─────────────────────────────────

    @staticmethod
    def is_daemon_alive() -> bool:
        """Check if the execution daemon is alive (hb_signal file < 60s old)."""
        hb = Path("output/daemon_heartbeat.txt"); 
        if not hb.exists():
            return False
        age = time.time() - hb.stat().st_mtime
        return age < 60

    def _write_heartbeat(self):
        """Write daemon hb_signal timestamp."""
        HB_SIGNAL_PATH.write_text(datetime.now().isoformat())

    def run_reconciliation_loop(self):
        """
        Background daemon. Run alongside the orchestrator during market hours.
        Polls every RECONCILE_INTERVAL seconds, detects fills, places stops.
        Writes hb_signal every cycle so orchestrator can verify daemon is alive.
        """
        logger.info(f"Starting Execution Reconciliation Daemon (interval: {RECONCILE_INTERVAL}s)...")
        while True:
            try:
                self._write_heartbeat()
                self._reconcile_state()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}", exc_info=True)
            time.sleep(RECONCILE_INTERVAL)

    def _reconcile_state(self):
        """
        Single reconciliation pass:
        1. Fetch all active trades without stops placed
        2. Batch-fetch broker order status
        3. On fill → place stop-loss
        4. On partial fill + price through stop → panic liquidate
        """
        panic_liquidations = []

        try:
            lock = FileLock(LOCK_PATH, timeout=5)
            with lock:
                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                    conn.row_factory = sqlite3.Row
                    # All unclosed trades: need stop placement OR stop fill monitoring
                    active_trades = conn.execute(
                        "SELECT * FROM active_trades WHERE closed_at IS NULL"
                    ).fetchall()

                if not active_trades:
                    return

                logger.info(f"Reconciling {len(active_trades)} active trades...")

                # Batch-fetch broker state ONCE per loop (rate-limit friendly)
                all_orders = self.broker.get_orders_today()
                broker_orders = {}
                for o in all_orders:
                    oid = str(o.get("id") or o.get("order_id", ""))
                    if oid:
                        broker_orders[oid] = o

                # Fetch live quotes for partial fill protection
                tickers_to_quote = list(set(t["ticker"] for t in active_trades))
                try:
                    quotes = self.broker.get_quotes(tickers_to_quote)
                except Exception as e:
                    logger.warning(f"Quote fetch failed: {e}")
                    quotes = {}

                for trade in active_trades:
                    trade = dict(trade)  # Convert Row to dict
                    ticker = trade["ticker"]
                    entry_id = trade["entry_order_id"]
                    b_order = broker_orders.get(entry_id)

                    if not b_order:
                        # Order not found — might be too old for today's orders
                        logger.debug(f"  {ticker}: entry order {entry_id} not found in today's orders")
                        continue

                    status = b_order.get("status", "unknown").lower()
                    filled_qty = int(float(b_order.get("filled_qty", b_order.get("filled_shares", 0))))
                    avg_price = float(b_order.get("avg_fill_price", b_order.get("average_price", 0)))

                    # Update DB state
                    with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                        conn.execute(
                            """UPDATE active_trades
                            SET entry_status = ?, filled_shares = ?, avg_fill_price = ?, last_updated = ?
                            WHERE trade_id = ?""",
                            (status, filled_qty, avg_price, datetime.now().isoformat(), trade["trade_id"]),
                        )
                        conn.commit()

                    # --- Sweep Stale Dangling Limits ---
                    # If entry order has been open > 45 minutes, cancel unfilled remainder
                    # Prevents accidental fills on a 2 PM flash crash
                    if status in ("open", "partially_filled"):
                        try:
                            last_up_str = trade["last_updated"].replace("Z", "+00:00")
                            last_up = datetime.fromisoformat(last_up_str)
                            age_seconds = (datetime.now() - last_up.replace(tzinfo=None)).total_seconds()
                            if age_seconds > 2700:  # 45 minutes
                                logger.warning(
                                    f"  \U0001f9f9 Sweeping stale limit order for {ticker} "
                                    f"(Order {trade['entry_order_id']} open for > 45 mins)."
                                )
                                self.broker.cancel_order(trade["entry_order_id"])
                                self._log_event(
                                    trade["trade_id"], ticker, "STALE_LIMIT_SWEPT",
                                    f"age={age_seconds:.0f}s filled={filled_qty}",
                                )
                                # Don't mark canceled in DB yet — next loop iteration will
                                # see broker status='canceled' and route stop for what DID fill
                        except Exception as e:
                            logger.error(f"Error checking order age for {ticker}: {e}")

                    # --- Partial Fill Protection ---
                    if status in ("open", "partially_filled") and filled_qty > 0:
                        live_bid = quotes.get(ticker, {}).get("bid", 0)
                        if live_bid > 0 and live_bid <= trade["target_stop_price"]:
                            logger.critical(
                                f"🚨 {ticker} price crashed through stop "
                                f"(bid=${live_bid:.2f} <= stop=${trade['target_stop_price']:.2f}) "
                                f"while partially filled ({filled_qty}/{trade['target_shares']} shares)! "
                                "Aborting entry + panic liquidation."
                            )
                            panic_liquidations.append(ticker)
                            self._log_event(
                                trade["trade_id"], ticker, "PARTIAL_FILL_PANIC",
                                f"bid={live_bid} stop={trade['target_stop_price']} filled={filled_qty}",
                            )
                            continue

                    # --- Terminal State: Route Native Stop (only if no stop placed yet) ---
                    terminal_states = ("filled", "canceled", "cancelled", "rejected", "expired")
                    if (status in terminal_states and filled_qty > 0
                            and ticker not in panic_liquidations
                            and not trade.get("stop_order_id")):
                        logger.info(
                            f"✅ {ticker} entry terminal ('{status}'). "
                            f"Placing stop for {filled_qty} shares at ${trade['target_stop_price']:.2f}"
                        )

                        try:
                            stop_res = self.broker.place_order(
                                ticker=ticker,
                                side="sell",
                                order_type="stop",
                                quantity=str(filled_qty),
                                stop_price=str(round(trade["target_stop_price"], 2)),
                                time_in_force="gtc",
                            )

                            stop_id = stop_res.get("order_id") or stop_res.get("id")
                            if stop_id:
                                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                                    conn.execute(
                                        "UPDATE active_trades SET stop_order_id = ?, stop_status = 'open', last_updated = ? WHERE trade_id = ?",
                                        (stop_id, datetime.now().isoformat(), trade["trade_id"]),
                                    )
                                    conn.commit()
                                self._log_event(
                                    trade["trade_id"], ticker, "STOP_PLACED",
                                    f"stop_id={stop_id} price=${trade['target_stop_price']:.2f} shares={filled_qty}",
                                )
                                logger.info(f"  🛡️ Stop placed for {ticker}: {stop_id}")
                            else:
                                logger.error(f"  Stop order for {ticker} returned no ID: {stop_res}")
                                self._log_event(
                                    trade["trade_id"], ticker, "STOP_FAILED",
                                    json.dumps(stop_res),
                                )
                        except Exception as e:
                            logger.error(f"  Stop placement failed for {ticker}: {e}")
                            self._log_event(trade["trade_id"], ticker, "STOP_ERROR", str(e))

                    # --- Monitor Native Stop Fills ---
                    if trade.get("stop_order_id"):
                        stop_order = broker_orders.get(trade["stop_order_id"])
                        if stop_order and stop_order.get("status", "").lower() in ("filled", "executed"):
                            exit_price = float(stop_order.get("filled_avg_price", stop_order.get("average_price", trade["target_stop_price"])))
                            logger.warning(f"  🛑 Native stop filled for {ticker} at ${exit_price:.2f}. Logging to journal.")

                            # Log to trade journal + penalty box
                            try:
                                from trade_journal import build_trade_record, log_close
                                from safeguards import add_to_penalty_box

                                directive = {}
                                orig_order = {}
                                if os.path.exists("output/agent1_directive.json"):
                                    with open("output/agent1_directive.json") as f:
                                        directive = json.load(f)
                                if os.path.exists("output/agent4_orders.json"):
                                    with open("output/agent4_orders.json") as f:
                                        a4_data = json.load(f)
                                    orig_order = next((o for o in a4_data.get("trade_orders", []) if o.get("ticker") == ticker), {})

                                if orig_order:
                                    record = build_trade_record(
                                        trade_order=orig_order,
                                        directive=directive,
                                        agent3_verification={},
                                        exit_price=exit_price,
                                        exit_reason="NATIVE_STOP_HIT",
                                    )
                                    log_close(record)

                                # Penalty box: loss = (entry - exit) * shares
                                entry_p = float(trade.get("limit_price", 0) or orig_order.get("entry_price", 0))
                                loss_amount = max(0, (entry_p - exit_price) * filled_qty)
                                if loss_amount > 0:
                                    add_to_penalty_box(ticker, loss_amount, reason="NATIVE_STOP_HIT")
                            except Exception as e:
                                logger.error(f"Failed to log native stop for {ticker}: {e}")

                            # Clear from ledger
                            with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                                conn.execute(
                                    "UPDATE active_trades SET closed_at = ?, close_reason = ? WHERE trade_id = ?",
                                    (datetime.now().isoformat(), f"NATIVE_STOP_FILLED@{exit_price:.2f}", trade["trade_id"]),
                                )
                                conn.commit()
                            self._log_event(trade["trade_id"], ticker, "STOP_FILLED", f"exit=${exit_price:.2f}")
                            continue  # Move to next trade

                    # --- Entry rejected/expired with 0 fills = dead trade ---
                    if status in ("canceled", "cancelled", "rejected", "expired") and filled_qty == 0:
                        logger.info(f"  ❌ {ticker} entry {status} with 0 fills — removing from ledger")
                        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                            conn.execute(
                                "UPDATE active_trades SET closed_at = ?, close_reason = ? WHERE trade_id = ?",
                                (datetime.now().isoformat(), f"entry_{status}", trade["trade_id"]),
                            )
                            conn.commit()
                        self._log_event(trade["trade_id"], ticker, "TRADE_DEAD", status)

        except Timeout:
            logger.warning("Lock timeout during reconciliation — skipping this cycle")

        # Execute panic liquidations OUTSIDE the lock (avoids recursive deadlock)
        for ticker in panic_liquidations:
            self.atomic_liquidate(ticker, "Stop hit during partial fill window")

    # ── Status / Debugging ───────────────────────────────────────────────

    def get_active_trades(self) -> list:
        """Return all active (unclosed) trades from the ledger."""
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM active_trades WHERE closed_at IS NULL ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_execution_log(self, limit: int = 50) -> list:
        """Return recent execution events."""
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]


# Quick test
if __name__ == "__main__":
    print("Testing Execution Engine...\n")
    engine = ExecutionEngine()
    print(f"DB: {DB_PATH}")
    print(f"Active trades: {len(engine.get_active_trades())}")
    print(f"Execution log: {len(engine.get_execution_log())} entries")
    print("\n✅ Execution Engine initialized!")
