"""
Robinhood Broker Module — Agentic Trading via MCP

Executes tear sheet orders, manages positions, and tracks fills
through Robinhood's MCP (Model Context Protocol) API.

Drop-in replacement for AlpacaBroker — same interface, different execution layer.

Usage:
  from robinhood_broker import RobinhoodBroker
  broker = RobinhoodBroker()
  broker.execute_tear_sheet(trade_orders)
  broker.get_positions()
  broker.close_position("AAPL")
"""
import json
import math
import os
import uuid
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MCP_URL = "https://agent.robinhood.com/mcp/trading"
TOKEN_PATH = Path(__file__).parent / "robinhood-mcp" / "token.json"


class RobinhoodBroker:
    def __init__(self):
        self._session_id = None
        self._access_token = None
        self._req_id = 0
        self._agentic_account = None
        self._all_accounts = []
        self._load_token()
        self._init_mcp()
        self._discover_accounts()

    # ── Auth ─────────────────────────────────────────────────────────────
    def _load_token(self):
        if not TOKEN_PATH.exists():
            raise RuntimeError(
                f"No Robinhood token at {TOKEN_PATH}. "
                "Run robinhood-mcp/auth_and_discover.py first."
            )
        data = json.loads(TOKEN_PATH.read_text())
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._client_id = data.get("client_id")

    def _refresh_access_token(self):
        """Refresh the access token using the refresh token."""
        if not self._refresh_token or not self._client_id:
            raise RuntimeError("No refresh token available. Re-run auth_and_discover.py.")

        import urllib.parse
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
        }).encode()

        req = Request(
            "https://api.robinhood.com/oauth2/token/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req)
        token_data = json.loads(resp.read())

        self._access_token = token_data["access_token"]
        self._refresh_token = token_data.get("refresh_token", self._refresh_token)

        # Persist
        TOKEN_PATH.write_text(json.dumps({
            "client_id": self._client_id,
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type"),
        }, indent=2))
        print("[RH-Broker] Access token refreshed")

    # ── MCP Transport ────────────────────────────────────────────────────
    def _mcp_request(self, method, params=None):
        """Send a JSON-RPC request to the MCP endpoint."""
        self._req_id += 1
        payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method}
        if params:
            payload["params"] = params

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self._access_token}",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        data = json.dumps(payload).encode()
        req = Request(MCP_URL, data=data, headers=headers)

        try:
            resp = urlopen(req)
        except HTTPError as e:
            if e.code == 401:
                # Token expired — try refresh
                print("[RH-Broker] Token expired, refreshing...")
                self._refresh_access_token()
                self._init_mcp()
                return self._mcp_request(method, params)
            body = e.read().decode()
            raise RuntimeError(f"MCP error {e.code}: {body}")

        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid

        body = resp.read().decode()
        content_type = resp.headers.get("Content-Type", "")

        if "text/event-stream" in content_type:
            result = None
            for line in body.split("\n"):
                if line.startswith("data: "):
                    try:
                        result = json.loads(line[6:])
                    except json.JSONDecodeError:
                        pass
            return result
        else:
            return json.loads(body) if body.strip() else None

    def _call_tool(self, tool_name, arguments=None):
        """Call an MCP tool and return the parsed result.

        Surfaces MCP-level errors instead of silently returning None/empty so that
        order placement can never be falsely recorded as 'submitted'. On error the
        return is {"__mcp_error__": True, "message": <text>}.
        """
        resp = self._mcp_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        if not resp:
            return {"__mcp_error__": True, "message": "empty MCP response"}

        # JSON-RPC level error
        if isinstance(resp, dict) and resp.get("error"):
            return {"__mcp_error__": True, "message": json.dumps(resp["error"])}

        result = resp.get("result", {}) if isinstance(resp, dict) else {}
        is_error = bool(result.get("isError"))
        content = result.get("content", [])
        for item in content:
            if item.get("type") == "text":
                txt = item["text"]
                try:
                    parsed = json.loads(txt)
                except json.JSONDecodeError:
                    if is_error:
                        return {"__mcp_error__": True, "message": txt}
                    return txt
                if is_error:
                    return {"__mcp_error__": True, "message": txt,
                            "data": parsed.get("data", parsed)}
                return parsed.get("data", parsed)
        if is_error:
            return {"__mcp_error__": True, "message": json.dumps(content)}
        return content

    def _init_mcp(self):
        """Initialize the MCP session."""
        resp = self._mcp_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "trading-pipeline", "version": "1.0.0"},
        })
        if resp and resp.get("result", {}).get("serverInfo"):
            print(f"[RH-Broker] MCP connected: {resp['result']['serverInfo']}")

        # Send initialized notification
        try:
            notify = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode()
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {self._access_token}",
            }
            if self._session_id:
                headers["Mcp-Session-Id"] = self._session_id
            req = Request(MCP_URL, data=notify, headers=headers)
            urlopen(req)
        except Exception:
            pass

    def _discover_accounts(self):
        """Find all accounts and identify the agentic one."""
        result = self._call_tool("get_accounts")
        accounts = result.get("accounts", []) if isinstance(result, dict) else []
        self._all_accounts = accounts

        for acct in accounts:
            if acct.get("agentic_allowed"):
                self._agentic_account = acct["account_number"]
                break

        if not self._agentic_account:
            raise RuntimeError("No agentic-enabled account found on this Robinhood login")

        print(f"[RH-Broker] Connected to Robinhood agentic account ···{self._agentic_account[-4:]}")

    # ── Public Interface (matches AlpacaBroker) ──────────────────────────

    def get_account_summary(self) -> dict:
        """Get current account state for the agentic account."""
        result = self._call_tool("get_portfolio", {
            "account_number": self._agentic_account,
        })
        if not result:
            return {"error": "Failed to get portfolio"}

        # Parse buying power (can be a nested dict or a string)
        bp = result.get("buying_power", 0)
        if isinstance(bp, dict):
            bp = float(bp.get("buying_power", 0))
        else:
            bp = float(bp)

        cash = float(result.get("cash", 0))
        total = float(result.get("total_value", 0))
        equity_val = float(result.get("equity_value", 0))

        return {
            "account_number": self._agentic_account,
            "cash": cash,
            "equity": total,
            "market_value": equity_val,
            "buying_power": bp,
            "portfolio_value": total,
            "status": "active",
        }

    def get_positions(self) -> list:
        """Get all open positions in the agentic account."""
        result = self._call_tool("get_equity_positions", {
            "account_number": self._agentic_account,
        })

        positions = result.get("positions", []) if isinstance(result, dict) else []
        parsed = []
        for p in positions:
            parsed.append({
                "ticker": p.get("symbol", ""),
                "shares": float(p.get("quantity", 0)),
                "avg_entry_price": float(p.get("average_buy_price", 0)),
                "current_price": float(p.get("current_price", 0)),
                "market_value": float(p.get("equity", 0)),
                "unrealized_pl": float(p.get("unrealized_pl", 0)),
                "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
            })

        # The RH MCP `get_equity_positions` endpoint frequently returns rows
        # with quantity/avg_buy_price populated but current_price == 0 and
        # equity == 0 (no live pricing on the positions feed). That made real
        # open positions look like $0 market value, which the afternoon monitor
        # interpreted as "flat / no open positions". Backfill missing prices
        # from the live quotes feed (which is reliable) so downstream logic
        # sees true market values.
        stale = [p["ticker"] for p in parsed
                 if p["ticker"] and p["shares"] != 0 and p["current_price"] <= 0]
        if stale:
            try:
                quotes = self.get_quotes(stale)
            except Exception as e:
                print(f"[RH-Broker] price hydration failed for {stale}: {e}")
                quotes = {}
            for p in parsed:
                if p["ticker"] in quotes and p["current_price"] <= 0:
                    q = quotes[p["ticker"]]
                    px = q.get("mid") or q.get("last") or q.get("bid") or 0
                    px = float(px or 0)
                    if px > 0:
                        p["current_price"] = px
                        p["market_value"] = px * p["shares"]
                        cost = p["avg_entry_price"] * p["shares"]
                        if cost > 0:
                            p["unrealized_pl"] = p["market_value"] - cost
                            p["unrealized_plpc"] = (p["market_value"] - cost) / cost
        return parsed

    def get_existing_exposure(self) -> float:
        """Get total dollar value of existing positions."""
        positions = self.get_positions()
        return sum(p["market_value"] for p in positions)

    def get_position_tickers(self) -> list:
        """Get list of tickers with open positions."""
        positions = self.get_positions()
        return [p["ticker"] for p in positions]

    def get_quote(self, ticker: str) -> dict:
        """Get real-time quote for a single ticker."""
        quotes = self.get_quotes([ticker])
        return quotes.get(ticker, {"error": f"No quote for {ticker}"})

    def get_quotes(self, tickers: list) -> dict:
        """Get real-time quotes for multiple tickers."""
        result = self._call_tool("get_equity_quotes", {"symbols": tickers})
        parsed = {}
        # Handle the actual MCP response structure: {results: [{quote: {...}, close: {...}}, ...]}
        items = []
        if isinstance(result, dict):
            items = result.get("results", result.get("quotes", []))
        elif isinstance(result, list):
            items = result

        for item in items:
            # Each item has a "quote" sub-object and optionally a "close" sub-object
            q = item.get("quote", item) if isinstance(item, dict) else item
            sym = q.get("symbol", "")
            bid = float(q.get("bid_price", 0))
            ask = float(q.get("ask_price", 0))
            last = float(q.get("last_trade_price", 0))
            prev_close = float(q.get("previous_close", 0))
            # Also check the close sub-object for official previous close
            close_obj = item.get("close", {}) if isinstance(item, dict) else {}
            if close_obj and close_obj.get("price"):
                prev_close = float(close_obj["price"])
            parsed[sym] = {
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid": round((bid + ask) / 2, 2) if bid and ask else last,
                "previous_close": prev_close,
            }
        return parsed

    def review_order(self, ticker: str, side: str, order_type: str = "market",
                     quantity: str = None, dollar_amount: str = None,
                     limit_price: str = None, stop_price: str = None) -> dict:
        """
        Dry-run an order — returns pre-trade alerts without placing.
        """
        args = {
            "account_number": self._agentic_account,
            "symbol": ticker,
            "side": side,
            "type": order_type,
        }
        if quantity:
            args["quantity"] = str(quantity)
        if dollar_amount:
            args["dollar_amount"] = str(dollar_amount)
        if limit_price:
            args["limit_price"] = str(limit_price)
        if stop_price:
            args["stop_price"] = str(stop_price)

        return self._call_tool("review_equity_order", args)

    def place_order(self, ticker: str, side: str, order_type: str = "market",
                    quantity: str = None, dollar_amount: str = None,
                    limit_price: str = None, stop_price: str = None,
                    time_in_force: str = "gfd") -> dict:
        """
        Place a real equity order.
        """
        args = {
            "account_number": self._agentic_account,
            "symbol": ticker,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "ref_id": str(uuid.uuid4()),
        }
        if quantity:
            args["quantity"] = str(quantity)
        if dollar_amount:
            args["dollar_amount"] = str(dollar_amount)
        if limit_price:
            args["limit_price"] = str(limit_price)
        if stop_price:
            args["stop_price"] = str(stop_price)

        result = self._call_tool("place_equity_order", args)
        return self._normalize_order_result(result)

    def get_order(self, order_id: str) -> dict:
        """Fetch a single equity order's current state via get_equity_orders."""
        r = self._call_tool("get_equity_orders", {"account_number": self._agentic_account})
        if not isinstance(r, dict) or r.get("__mcp_error__"):
            return {"ok": False, "error": (r or {}).get("message", "fetch failed")}
        orders = r.get("orders") if isinstance(r.get("orders"), list) else (r if isinstance(r, list) else [])
        for o in orders:
            if isinstance(o, dict) and o.get("id") == order_id:
                return {"ok": True, "state": o.get("state"),
                        "filled": o.get("cumulative_quantity"),
                        "avg_price": o.get("average_price"), "order": o}
        return {"ok": False, "error": "order not found"}

    def wait_for_fill(self, order_id: str, timeout: int = 90, interval: int = 5) -> dict:
        """Poll an order until it fills (or terminal/timeout). Returns last status."""
        terminal = {"filled", "cancelled", "rejected", "failed", "voided"}
        last = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            last = self.get_order(order_id)
            state = last.get("state")
            if state in terminal:
                return last
            time.sleep(interval)
        return last

    def place_stop(self, ticker: str, qty, stop_price: float,
                   time_in_force: str = "gtc") -> dict:
        """Place a protective stop-market SELL order.

        Robinhood supports fractional shares, so we must NOT int()-truncate the
        quantity (that would leave a fractional sliver of the position unhedged,
        e.g. int(10.47) -> 10 leaves 0.47 sh uncovered). Round to 6 dp (RH's
        fractional precision) and strip trailing zeros.
        """
        qty_str = ("%.6f" % float(qty)).rstrip("0").rstrip(".")
        if not qty_str or float(qty_str) <= 0:
            return {"ok": False, "order_id": None,
                    "error": f"invalid stop qty {qty!r}"}
        args = {
            "account_number": self._agentic_account,
            "symbol": ticker, "side": "sell", "type": "stop_market",
            "quantity": qty_str, "stop_price": str(round(float(stop_price), 2)),
            "time_in_force": time_in_force, "ref_id": str(uuid.uuid4()),
        }
        return self._normalize_order_result(self._call_tool("place_equity_order", args))

    @staticmethod
    def _normalize_order_result(result) -> dict:
        """Normalize a place_equity_order response into a flat dict with a
        reliable order_id and an explicit `ok` flag.

        The Robinhood MCP returns the order under data.order (which _call_tool
        unwraps to result['order']). The order UUID lives at result['order']['id'].
        Previous code looked for result['order_id']/result['id'] which are absent,
        so every fill recorded order_id=null. This fixes that and refuses to
        report success when no order object/id came back.
        """
        if not isinstance(result, dict):
            return {"ok": False, "order_id": None,
                    "error": f"unexpected order result: {result!r}"}
        if result.get("__mcp_error__"):
            return {"ok": False, "order_id": None,
                    "error": result.get("message", "MCP error")}
        order = result.get("order") if isinstance(result.get("order"), dict) else None
        order_id = None
        state = None
        if order:
            order_id = order.get("id")
            state = order.get("state")
        # fall back to legacy/top-level shapes just in case
        order_id = order_id or result.get("order_id") or result.get("id")
        ok = bool(order_id) and state not in ("rejected", "failed", "voided", "cancelled")
        return {
            "ok": ok,
            "order_id": order_id,
            "state": state,
            "order": order,
            "raw": result,
            "error": None if ok else f"no order_id returned (state={state})",
        }

    def execute_tear_sheet(self, trade_orders: list, max_gap_pct: float = 0.02) -> list:
        """
        Execute BUY orders from Agent 4B's tear sheet with live re-pricing.

        Same logic as AlpacaBroker but uses Robinhood MCP for quotes and execution.
        Robinhood doesn't support OTO (bracket) orders via MCP, so stop-losses
        need to be placed as separate orders after fills.
        """
        fills = []

        # Collect BUY tickers for batch quote fetch
        buy_tickers = [o["ticker"] for o in trade_orders if o.get("action") == "BUY"]

        # Fetch live quotes via Robinhood
        live_quotes = {}
        if buy_tickers:
            try:
                live_quotes = self.get_quotes(buy_tickers)
                print(f"  [RH-Broker] Live quotes fetched for {len(live_quotes)} tickers")
            except Exception as e:
                print(f"  [RH-Broker] WARNING: Could not fetch live quotes ({e}), using planned prices")

        for order in trade_orders:
            if order.get("action") != "BUY":
                fills.append({
                    "ticker": order.get("ticker", "?"),
                    "status": "skipped",
                    "reason": order.get("reason", order.get("action", "not a BUY")),
                })
                continue

            ticker = order["ticker"]
            planned_entry = order["entry_price"]
            stop_price = order.get("stop_loss")
            risk_budget = order.get("risk_budgeted", order.get("risk_actual", 0))
            planned_shares = order["shares"]

            try:
                # Get live price
                quote = live_quotes.get(ticker, {})
                live_ask = quote.get("ask") or quote.get("mid") or quote.get("last") or 0

                if live_ask > 0 and stop_price and stop_price > 0 and risk_budget > 0:
                    # === LIVE RE-PRICING MODE ===
                    deviation_pct = abs(live_ask - planned_entry) / planned_entry

                    if deviation_pct > max_gap_pct:
                        # Cross-reference to verify the anomaly. The legacy
                        # `broker._cross_reference_price` helper no longer exists,
                        # so degrade gracefully: prefer a more reliable price
                        # reference (mid, then last) over a wide pre-market ask
                        # before deciding to reject.
                        verified_price = None
                        try:
                            from broker import _cross_reference_price  # legacy, optional
                            verified_price = _cross_reference_price(ticker, planned_entry, live_ask)
                        except (ImportError, ModuleNotFoundError):
                            ref_price = quote.get("mid") or quote.get("last")
                            if ref_price and ref_price > 0:
                                ref_dev = abs(ref_price - planned_entry) / planned_entry
                                if ref_dev <= max_gap_pct:
                                    print(f"  [RH-Broker] ℹ️ {ticker}: wide ask ${live_ask:.2f} ignored; using mid/last ${ref_price:.2f} (dev {ref_dev*100:.1f}%)")
                                    verified_price = ref_price

                        if verified_price is not None:
                            print(f"  [RH-Broker] ✅ {ticker}: Cross-ref price ${verified_price:.2f}")
                            live_ask = verified_price
                        else:
                            fills.append({
                                "ticker": ticker,
                                "status": "rejected",
                                "reason": f"Quote anomaly: ${live_ask:.2f} vs planned ${planned_entry:.2f} ({deviation_pct*100:.1f}%)",
                            })
                            continue

                    # Gap-up protection
                    gap_pct = (live_ask - planned_entry) / planned_entry
                    if gap_pct > max_gap_pct:
                        print(f"  [RH-Broker] 🚫 REJECTED {ticker}: Gapped up {gap_pct*100:.1f}%")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Gap up {gap_pct*100:.1f}% > {max_gap_pct*100:.0f}%",
                            "planned_entry": planned_entry,
                            "live_ask": live_ask,
                        })
                        continue

                    # Dynamic share recalculation
                    live_risk_per_share = live_ask - stop_price
                    if live_risk_per_share <= 0:
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Live ${live_ask:.2f} at/below stop ${stop_price:.2f}",
                        })
                        continue

                    # Robinhood rejects fractional-share LIMIT orders
                    # ("Limit order quantity cannot include fractional shares").
                    # Floor to whole shares — this trims position size slightly,
                    # which is the conservative/safe direction (lowers risk).
                    #
                    # CLAMP (2026-07-30): never size UP beyond the planned share
                    # count. Agent 4's plan already respects allocation/notional
                    # caps; the live re-size exists only to TRIM when the live
                    # fill price widened per-share risk. Without the min(), a
                    # tight stop makes risk_per_share tiny and the division
                    # inflates notional past buying power. Real case: NVO planned
                    # 18.11 sh, risk/sh $1.21, budget $58.80 -> 48 sh ($2,396)
                    # -> rejected "Not enough buying power", which then starved
                    # the next order (UL) of cash. Mirrors the correct guard
                    # already present in orchestrator.py (exec_shares = min(...)).
                    live_shares = math.floor(
                        min(planned_shares, risk_budget / live_risk_per_share)
                    )
                    if live_shares < 1:
                        fills.append({"ticker": ticker, "status": "rejected", "reason": "Zero whole shares after re-sizing (risk budget too small for 1 share)"})
                        continue

                    limit_price = round(live_ask * 1.0015, 2)
                    shares = live_shares
                    pricing_mode = "live"

                    if shares != planned_shares:
                        print(f"  [RH-Broker] 📐 {ticker}: Re-sized {planned_shares} → {shares} shares")
                else:
                    limit_price = round(planned_entry * 1.015, 2)
                    # Whole shares only for limit orders (RH constraint).
                    shares = math.floor(planned_shares)
                    if shares < 1:
                        fills.append({"ticker": ticker, "status": "rejected", "reason": "Zero whole shares (planned < 1 share)"})
                        continue
                    pricing_mode = "planned"

                # First: review the order (dry run)
                review = self.review_order(ticker, "buy", "limit",
                                           quantity=str(shares), limit_price=str(limit_price))
                if review and isinstance(review, dict):
                    alerts = review.get("alerts", [])
                    if alerts:
                        print(f"  [RH-Broker] ⚠️ {ticker} pre-trade alerts: {alerts}")

                # Place the order, with one retry if the broker didn't accept it.
                # RULE: an approved trade must end with a real Robinhood order_id.
                # We never record "submitted" without one.
                result = self.place_order(
                    ticker, "buy", "limit",
                    quantity=str(shares),
                    limit_price=str(limit_price),
                    time_in_force="gfd",
                )
                order_id = result.get("order_id") if isinstance(result, dict) else None

                if not order_id:
                    err = result.get("error") if isinstance(result, dict) else str(result)
                    print(f"  [RH-Broker] ⚠️ {ticker}: first submit returned no order_id ({err}) — retrying once")
                    # Re-quote and retry as a marketable limit so it actually fills.
                    try:
                        rq = self.get_quotes([ticker]).get(ticker, {})
                        retry_ask = rq.get("ask") or rq.get("mid") or rq.get("last") or live_ask
                        if retry_ask and retry_ask > 0:
                            limit_price = round(retry_ask * 1.003, 2)
                            if stop_price and stop_price > 0 and risk_budget > 0:
                                rps = retry_ask - stop_price
                                if rps > 0:
                                    shares = max(1, math.floor(risk_budget / rps))
                    except Exception as rqe:
                        print(f"  [RH-Broker] retry re-quote failed: {rqe}")
                    result = self.place_order(
                        ticker, "buy", "limit",
                        quantity=str(shares),
                        limit_price=str(limit_price),
                        time_in_force="gfd",
                    )
                    order_id = result.get("order_id") if isinstance(result, dict) else None

                if not order_id:
                    err = result.get("error") if isinstance(result, dict) else str(result)
                    print(f"  [RH-Broker] ❌ {ticker}: NOT FILLED — broker rejected order ({err})")
                    fills.append({
                        "ticker": ticker,
                        "status": "failed",
                        "order_id": None,
                        "shares": shares,
                        "planned_shares": planned_shares,
                        "order_type": "limit",
                        "limit_price": limit_price,
                        "pricing_mode": pricing_mode,
                        "live_ask": live_ask if live_ask > 0 else None,
                        "planned_entry": planned_entry,
                        "risk_budget": risk_budget,
                        "stop_price": stop_price,
                        "broker": "robinhood",
                        "error": err,
                    })
                    continue

                print(f"  [RH-Broker] ✅ {ticker}: order placed — id={order_id} state={result.get('state')}")
                fills.append({
                    "ticker": ticker,
                    "status": "submitted",
                    "order_id": order_id,
                    "order_state": result.get("state"),
                    "shares": shares,
                    "planned_shares": planned_shares,
                    "order_type": "limit",
                    "limit_price": limit_price,
                    "pricing_mode": pricing_mode,
                    "live_ask": live_ask if live_ask > 0 else None,
                    "planned_entry": planned_entry,
                    "risk_budget": risk_budget,
                    "stop_price": stop_price,
                    "broker": "robinhood",
                })
                print(f"  [RH-Broker] ✅ BUY {shares} {ticker} @ limit ${limit_price} ({pricing_mode})")

                # Robinhood MCP doesn't support bracket/OTO orders, so place the
                # protective stop separately AFTER the entry fills. Poll, then arm.
                if stop_price and stop_price > 0:
                    print(f"  [RH-Broker] ⏳ Waiting for {ticker} fill to arm stop ${stop_price:.2f}...")
                    status = self.wait_for_fill(order_id, timeout=90, interval=5)
                    filled_qty = 0.0
                    try:
                        # Keep the FULL fractional fill qty so the stop covers the
                        # entire position (no int() truncation leaving a sliver).
                        filled_qty = float(status.get("filled") or 0)
                    except (TypeError, ValueError):
                        filled_qty = 0.0
                    if status.get("state") == "filled" and filled_qty > 0:
                        stop_res = self.place_stop(ticker, filled_qty, stop_price)
                        if stop_res.get("ok"):
                            fills[-1]["stop_order_id"] = stop_res.get("order_id")
                            fills[-1]["stop_armed"] = True
                            print(f"  [RH-Broker] 🛡️ Stop armed: SELL {filled_qty:g} {ticker} @ ${stop_price:.2f} stop (id={stop_res.get('order_id')})")
                        else:
                            fills[-1]["stop_armed"] = False
                            fills[-1]["stop_error"] = stop_res.get("error")
                            print(f"  [RH-Broker] ⚠️ Stop FAILED for {ticker}: {stop_res.get('error')} — PLACE MANUALLY")
                        # ── +6R take-profit leg (intraday spike capture) ──
                        # RH has no OTO/bracket, so we place a SEPARATE GTC limit
                        # sell at entry + BRACKET_TP_R_MULTIPLE * per-share-risk,
                        # for the FULL filled qty. This is the only profit-taking
                        # that fires intraday; Agent 5's +2R/+4R scale-outs run at
                        # 3:30. On a partial scale-out, atomic_trim cancels this
                        # leg and re-arms a fresh stop on the remainder.
                        #
                        # NOTE: both the stop and this TP encumber the same
                        # shares. RH allows the resting stop + a resting limit on
                        # the same lot; if your account rejects the double-hold,
                        # the TP submit just logs an error and the position rides
                        # on the stop alone (no crash).
                        try:
                            from config import BRACKET_TP_R_MULTIPLE
                            entry_fill = float(status.get("avg_price") or limit_price)
                            per_share_risk = max(entry_fill - stop_price, 0.01)
                            tp_price = round(entry_fill + BRACKET_TP_R_MULTIPLE * per_share_risk, 2)
                            tp_res = self.place_order(
                                ticker, "sell", "limit",
                                quantity=str(filled_qty),
                                limit_price=str(tp_price),
                                time_in_force="gtc",
                            )
                            tp_id = tp_res.get("order_id") if isinstance(tp_res, dict) else None
                            if tp_id:
                                fills[-1]["take_profit_price"] = tp_price
                                fills[-1]["take_profit_order_id"] = tp_id
                                print(f"  [RH-Broker] 🎯 TP armed: SELL {filled_qty:g} {ticker} @ ${tp_price:.2f} limit (+{BRACKET_TP_R_MULTIPLE:g}R, id={tp_id})")
                            else:
                                err = tp_res.get("error") if isinstance(tp_res, dict) else str(tp_res)
                                fills[-1]["take_profit_error"] = err
                                print(f"  [RH-Broker] ⚠️ TP leg not placed for {ticker} ({err}) — riding on stop only")
                        except Exception as tpe:
                            fills[-1]["take_profit_error"] = str(tpe)
                            print(f"  [RH-Broker] ⚠️ TP leg error for {ticker}: {tpe} — riding on stop only")
                    else:
                        fills[-1]["stop_armed"] = False
                        fills[-1]["stop_error"] = f"entry not filled (state={status.get('state')})"
                        print(f"  [RH-Broker] ⚠️ {ticker} not filled (state={status.get('state')}) — stop NOT armed")

            except Exception as e:
                fills.append({"ticker": ticker, "status": "error", "error": str(e)})
                print(f"  [RH-Broker] ❌ ERROR on {ticker}: {e}")

        # Save fills
        os.makedirs("output", exist_ok=True)
        with open("output/broker_fills.json", "w") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "broker": "robinhood", "fills": fills}, f, indent=2)

        return fills

    def close_position(self, ticker: str, qty: int = None) -> dict:
        """Close a position (full or partial). Market order."""
        try:
            if qty:
                result = self.place_order(ticker, "sell", "market", quantity=str(qty))
                print(f"  [RH-Broker] TRIM {qty} shares of {ticker}")
            else:
                # Full close — get current position size first
                positions = self.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)
                if not pos:
                    return {"ticker": ticker, "status": "no_position"}
                result = self.place_order(ticker, "sell", "market", quantity=str(int(pos["shares"])))
                print(f"  [RH-Broker] CLOSE {ticker} ({int(pos['shares'])} shares)")

            return {"ticker": ticker, "status": "submitted", "action": "trim" if qty else "close", "qty": qty, "result": result}
        except Exception as e:
            print(f"  [RH-Broker] ERROR closing {ticker}: {e}")
            return {"ticker": ticker, "status": "error", "error": str(e)}

    def close_all_positions(self) -> dict:
        """CRISIS_LIQUIDATION — close everything at market."""
        positions = self.get_positions()
        results = []
        for p in positions:
            r = self.close_position(p["ticker"])
            results.append(r)
        print(f"  [RH-Broker] CRISIS_LIQUIDATION — closing {len(positions)} positions")
        return {"status": "submitted", "action": "close_all", "count": len(positions), "results": results}

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an open order."""
        return self._call_tool("cancel_equity_order", {
            "account_number": self._agentic_account,
            "order_id": order_id,
        })

    def get_orders(self, state: str = None, symbol: str = None) -> list:
        """Get orders for the agentic account."""
        args = {"account_number": self._agentic_account}
        if state:
            args["state"] = state
        if symbol:
            args["symbol"] = symbol
        result = self._call_tool("get_equity_orders", args)
        return result.get("orders", []) if isinstance(result, dict) else []

    def get_orders_today(self) -> list:
        """Get all orders — matches AlpacaBroker interface."""
        return self.get_orders()

    def check_tradability(self, tickers: list) -> dict:
        """Check if tickers can be traded on the agentic account."""
        return self._call_tool("get_equity_tradability", {
            "account_number": self._agentic_account,
            "symbols": tickers[:10],  # Max 10 per call
        })

    def search(self, query: str) -> list:
        """Search for instruments by name or ticker."""
        result = self._call_tool("search", {"query": query})
        return result.get("results", []) if isinstance(result, dict) else []

    def execute_agent5_decisions(self, decisions: list, crisis: bool = False) -> list:
        """
        Execute Agent 5's HOLD/TRIM/CLOSE decisions.
        CLOSE/TRIM route through ExecutionEngine to handle encumbered shares
        (resting stop-loss orders lock shares, raw close_position will fail).
        """
        from execution_engine import ExecutionEngine
        engine = ExecutionEngine(broker=self)

        if crisis:
            positions = self.get_positions()
            results = []
            for p in positions:
                engine.atomic_liquidate(p["ticker"], reason="CRISIS_LIQUIDATION")
                results.append({"ticker": p["ticker"], "action": "CRISIS_LIQUIDATION", "status": "submitted"})
            return results

        results = []
        for d in decisions:
            ticker = d.get("ticker")
            action = d.get("action", "HOLD")

            if action == "HOLD":
                new_stop = d.get("new_stop")
                original_stop = d.get("original_stop")
                # Re-apply the stop whenever the COMPUTED stop differs from what
                # is ACTUALLY RESTING AT THE BROKER. The prior guard compared
                # against the ledger's target_stop_price — but the ledger target
                # and the live resting order routinely DESYNC (e.g. BAC ledger
                # said $55.83 while the real Robinhood stop was frozen at $55.71
                # with a NULL order_id). Comparing against the DB made the guard
                # think "already done" and skip the push, leaving the live stop
                # stale. We now read the LIVE broker stop and force a replace on
                # any mismatch, while still never widening (ratchet-up only).
                live_stop = None
                live_stop_id = None
                try:
                    for _o in self.get_orders(symbol=ticker):
                        if (_o.get("trigger") == "stop"
                                and _o.get("state") in ("confirmed", "queued", "unconfirmed")):
                            live_stop = float(_o.get("stop_price") or 0)
                            live_stop_id = _o.get("id")
                            break
                except Exception:
                    live_stop = None

                # Fall back to the ledger target only if the broker query failed.
                if live_stop is None:
                    try:
                        import sqlite3
                        from execution_engine import DB_PATH
                        with sqlite3.connect(DB_PATH, timeout=20.0) as _c:
                            _r = _c.execute(
                                "SELECT target_stop_price FROM active_trades "
                                "WHERE ticker = ? AND closed_at IS NULL", (ticker,),
                            ).fetchone()
                            if _r:
                                live_stop = _r[0]
                    except Exception:
                        live_stop = None

                baseline = live_stop if live_stop is not None else original_stop
                # Never widen: only push if new_stop is a real number and is
                # higher than what's actually resting (ratchet up), OR there is
                # no live stop at all (naked position -> must protect).
                needs_update = bool(new_stop) and (
                    not baseline or baseline <= 0 or round(new_stop, 2) > round(baseline, 2)
                )
                if needs_update:
                    # update_trailing_stop is ATOMIC (cancel old -> wait for the
                    # clearinghouse to release the shares -> place new -> confirm)
                    # and writes the new order_id back to the ledger. update_stop()
                    # only cancels + NULLs the row and relies on a daemon that no
                    # longer runs, so it would leave the position naked.
                    ok = engine.update_trailing_stop(ticker, round(new_stop, 2))
                    if not ok:
                        # Atomic path needs a linked order_id; if it bailed (no
                        # live order on file) fall back to the cancel+replace via
                        # the ledger so the position still gets re-armed.
                        engine.update_stop(ticker, new_stop, reason="Agent5_TRAIL")
                    results.append({"ticker": ticker, "action": "HOLD_STOP_TIGHTENED",
                                    "new_stop": round(new_stop, 2), "prev_stop": baseline,
                                    "status": "executed" if ok else "requeued"})
                else:
                    results.append({"ticker": ticker, "action": "HOLD", "status": "no_action"})

            elif action == "CLOSE":
                result = engine.atomic_liquidate(ticker, reason="Agent5_CLOSE")
                results.append(result)

            elif action == "TRIM":
                # Real partial scale-out: cancel encumbering sell legs → wait for
                # release → market-sell the tranche → re-arm a stop on the
                # remainder. trim_pct is a fraction of CURRENT holdings (Agent 5
                # already nets out tranches sold on prior days).
                trim_pct = d.get("trim_pct")
                if trim_pct is None:
                    trim_pct = 33  # safety default; Agent 5 normally supplies this
                new_stop = d.get("new_stop") or d.get("current_price") or 0
                result = engine.atomic_trim(
                    ticker, trim_pct=trim_pct, new_stop=new_stop, reason="Agent5_TRIM"
                )
                results.append(result)

        return results


# Quick smoke test
if __name__ == "__main__":
    print("Testing Robinhood MCP Broker connection...\n")

    broker = RobinhoodBroker()

    # Test 1: Account summary
    print("\n1. Account Summary:")
    summary = broker.get_account_summary()
    for k, v in summary.items():
        if k != "raw":
            print(f"   {k}: {v}")

    # Test 2: Positions
    print("\n2. Open Positions:")
    positions = broker.get_positions()
    if positions:
        for p in positions:
            print(f"   {p['ticker']}: {p['shares']} shares @ ${p['avg_entry_price']:.2f}")
    else:
        print("   No open positions")

    # Test 3: Quote
    print("\n3. Quote for AAPL:")
    quote = broker.get_quote("AAPL")
    print(f"   {quote}")

    # Test 4: Review order (dry run)
    print("\n4. Review order — BUY 1 AAPL @ market:")
    review = broker.review_order("AAPL", "buy", "market", quantity="1")
    print(f"   {json.dumps(review, indent=2)[:500]}")

    print("\n✅ Robinhood Broker module working!")
