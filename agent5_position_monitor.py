"""
Agent 5: Position Monitor — v3 (Python trailing stops + Claude thesis monitor)
Model: Claude Sonnet 4.6 (Anthropic) with adaptive thinking
Role: Runs at 3:30 PM ET to review open positions and decide hold/trim/close.

Architecture:
  1. Python calculates ALL mechanical trailing stops (no LLM needed for math)
  2. Claude reviews ONLY thesis drift: has the fundamental narrative broken?
  3. Merge: mechanical close if stop hit, thesis close if narrative broken, else HOLD

Timing:
  3:25 PM — Python snapshots current market prices + fetches breaking news
  3:30 PM — Python trailing stops → Claude thesis review → merge decisions
"""
import json
import os
import re
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Sonnet 4.6 with adaptive thinking for thesis drift classification
MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 3
RETRY_DELAY = 5

SYSTEM_PROMPT = """You are Agent 5: The Thesis Monitor for a $100,000 speculative spot-only trading account.

YOUR JOB: You are the qualitative half of the position monitoring system. Python has ALREADY calculated all trailing stops and mechanical close signals. Your ONLY job is to evaluate whether the FUNDAMENTAL THESIS for each position is still intact.

YOU DO NOT:
- Calculate trailing stops (Python already did this)
- Compute P&L percentages (Python already did this)
- Decide mechanical closes (Python already did this)
- Do any math whatsoever

YOU DO:
- Read the ORIGINAL THESIS from Agent 2 for each position
- Read today's BREAKING NEWS for each ticker (pre-fetched by Python from yfinance)
- Read Agent 1's MORNING REGIME classification
- Decide: Has the fundamental narrative broken? Did the macro regime shift?
- If the thesis is broken, you OVERRIDE the mechanical trailing stop with a CLOSE

PRE-CHECK (MANDATORY):
If Agent 1's morning regime was CRISIS, OR if VIX at 3:25 PM > 35:
-> ALL theses are considered BROKEN. Output thesis_status = "BROKEN" for every position
   with override_action = "CLOSE" and reasoning = "CRISIS_LIQUIDATION".
-> Skip per-position thesis evaluation entirely.

THESIS STATUS OPTIONS (per position):
- INTACT: The original thesis still holds. News is neutral or supportive. Macro regime has not shifted against the trade. No override.
- DEGRADED: The thesis is weakened but not fatally broken. News introduces uncertainty. No override, but flag for closer monitoring tomorrow.
- BROKEN: The thesis is fatally compromised. A material event has invalidated the trade rationale (e.g., regulatory action, earnings miss, key partnership dissolved, sector-wide selloff changing the narrative). Override: CLOSE the position regardless of what the trailing stop says.

RULES:
- Be conservative with BROKEN — only use it for genuine narrative breaks, not normal volatility.
- A stock being down is NOT thesis broken. The thesis is about WHY you entered, not the price.
- If no breaking news exists for a ticker, default to INTACT.
- Cite the specific news headline or regime shift that drove your decision.
- CLASSIFY the news_category for each review:
  * COMPANY_SPECIFIC: Earnings, FDA decision, lawsuit, management change, guidance revision
  * SECTOR_SPECIFIC: Industry-wide regulation, sector earnings trend, supply chain disruption
  * MACRO_NOISE: Fed commentary, CPI/jobs data, general market selloff, geopolitical tension
  * SECTOR_ROTATION: Money flowing between sectors (tech→value, growth→defensive)
  * GENERAL_MARKET: Broad index movement, VIX spike, options expiry
  Only COMPANY_SPECIFIC and SECTOR_SPECIFIC events can genuinely break a thesis.

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "agent": "thesis_monitor",
  "timestamp": "<ISO timestamp>",
  "crisis_liquidation": <true | false>,
  "thesis_reviews": [
    {
      "ticker": "<SYMBOL>",
      "thesis_status": "<INTACT | DEGRADED | BROKEN>",
      "news_category": "<COMPANY_SPECIFIC | SECTOR_SPECIFIC | MACRO_NOISE | SECTOR_ROTATION | GENERAL_MARKET>",
      "override_action": <null | "CLOSE">,
      "original_thesis_summary": "<1 sentence recap of the entry thesis>",
      "thesis_assessment": "<2-3 sentences explaining why the thesis is intact/degraded/broken>",
      "key_news_cited": ["<headline or event that influenced assessment>"]
    }
  ],
  "macro_assessment": "<1-2 sentences on whether the macro regime has shifted since morning>"
}"""


PORTFOLIO_STATE_PATH = "output/portfolio_state.json"


def _load_portfolio_state() -> dict:
    """Load persistent portfolio state (high-water-mark stops) from disk."""
    if os.path.exists(PORTFOLIO_STATE_PATH):
        try:
            with open(PORTFOLIO_STATE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [Agent 5] Warning: Could not load portfolio state: {e}")
    return {}


def _save_portfolio_state(state: dict) -> None:
    """Save persistent portfolio state (high-water-mark stops) to disk."""
    os.makedirs(os.path.dirname(PORTFOLIO_STATE_PATH) or ".", exist_ok=True)
    with open(PORTFOLIO_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def snapshot_prices(tickers: list) -> dict:
    """
    Snapshot current market prices for trailing-stop evaluation.

    PRIMARY: Tiingo (real-time IEX) — same source as the rest of the pipeline.
    FALLBACK: Yahoo Finance (yfinance) only for tickers Tiingo can't return
    (e.g. ^VIX, which isn't a Tiingo equity). This keeps the 30-min stop
    reinforcement pricing off the reliable Tiingo feed instead of flaky Yahoo.
    """
    snapshot = {}

    # ━━━ PRIMARY: Tiingo real-time quotes (batch, one call) ━━━
    tiingo_tickers = [t for t in tickers if not t.startswith("^")]
    if tiingo_tickers:
        try:
            from market_data import _tiingo_quotes
            tq = _tiingo_quotes(tiingo_tickers)
            for t, q in tq.items():
                last = q.get("last", 0)
                if last and last > 0:
                    snapshot[t] = {
                        "current_price": round(float(last), 2),
                        "source": "tiingo",
                    }
        except Exception as e:
            print(f"[Agent 5] Tiingo snapshot failed, will use Yahoo: {e}")

    # ━━━ FALLBACK: Yahoo for anything Tiingo didn't cover (incl. ^VIX) ━━━
    yahoo_targets = [t for t in tickers if t not in snapshot]
    for ticker in yahoo_targets:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1m")
            if not hist.empty:
                current = float(hist["Close"].iloc[-1])
                day_open = float(hist["Open"].iloc[0])
                day_high = float(hist["High"].max())
                day_low = float(hist["Low"].min())
                volume = int(hist["Volume"].sum())

                snapshot[ticker] = {
                    "current_price": round(current, 2),
                    "day_open": round(day_open, 2),
                    "day_high": round(day_high, 2),
                    "day_low": round(day_low, 2),
                    "day_volume": volume,
                    "intraday_change_pct": round((current - day_open) / day_open * 100, 2),
                }
            else:
                # Fallback to daily
                hist_d = stock.history(period="1d")
                if not hist_d.empty:
                    snapshot[ticker] = {
                        "current_price": round(float(hist_d["Close"].iloc[-1]), 2),
                        "note": "Using daily close (intraday unavailable)",
                    }
                else:
                    snapshot[ticker] = {"error": "No data available"}
        except Exception as e:
            snapshot[ticker] = {"error": str(e)}

    snapshot["snapshot_time"] = datetime.now().isoformat()
    return snapshot


def fetch_breaking_news(tickers: list) -> dict:
    """
    Fetch latest news headlines from yfinance for each ticker.
    Used to feed Claude's thesis drift assessment.
    """
    news_data = {}
    print(f"  [Agent 5] Fetching breaking news for {len(tickers)} tickers...")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news
            headlines = []
            if news_items:
                for n in news_items[:5]:
                    pub_time = n.get("providerPublishTime", "")
                    title = n.get("title", "")
                    publisher = n.get("publisher", "")
                    headlines.append(f"{pub_time}: {title} [{publisher}]")
            news_data[ticker] = headlines if headlines else ["No recent news"]
        except Exception as e:
            news_data[ticker] = [f"Error fetching news: {e}"]

    return news_data


def load_open_positions() -> list:
    """
    Load open positions from Robinhood (source of truth — the real-money book).
    Falls back to agent4_orders.json if Robinhood is unreachable.
    Enriches with stop_loss from agent4_orders.json when available.
    """
    # Primary: Read from Robinhood (the real-money execution account, which now
    # holds the full book). Previously this read from Alpaca paper as "source of
    # truth", but that paper account does not reflect actual holdings and caused
    # the recap to misreport positions.
    try:
        from broker_factory import get_broker
        broker = get_broker("robinhood")
        broker_positions = broker.get_positions()
        if broker_positions:
            # Enrich with stop/theme data from agent4 orders if available
            stop_map = {}
            orders_path = "output/agent4_orders.json"
            if os.path.exists(orders_path):
                with open(orders_path) as f:
                    orders_data = json.load(f)
                for order in orders_data.get("trade_orders", []):
                    if order.get("action") == "BUY":
                        stop_map[order["ticker"]] = {
                            "stop_loss": order.get("stop_loss", 0),
                            "stop_anchor_label": order.get("stop_anchor_label", ""),
                            "theme": order.get("theme", ""),
                            "thesis": order.get("thesis", ""),
                            "dollar_risk": order.get("dollar_risk", 0),
                        }

            positions = []
            for p in broker_positions:
                enrichment = stop_map.get(p["ticker"], {})
                positions.append({
                    "ticker": p["ticker"],
                    "shares": p["shares"],
                    "entry_price": p["avg_entry_price"],
                    "stop_loss": enrichment.get("stop_loss", 0),
                    "stop_anchor_label": enrichment.get("stop_anchor_label", ""),
                    "theme": enrichment.get("theme", ""),
                    "thesis": enrichment.get("thesis", ""),
                    "dollar_risk": enrichment.get("dollar_risk", 0),
                    "unrealized_pl": p.get("unrealized_pl", 0),
                    "unrealized_plpc": p.get("unrealized_plpc", 0),
                    "market_value": p.get("market_value", 0),
                })
            print(f"[Agent 5] Loaded {len(positions)} positions from Robinhood")
            return positions
    except Exception as e:
        print(f"[Agent 5] Robinhood read failed, falling back to orders file: {e}")

    # Fallback: Read from agent4_orders.json
    orders_path = "output/agent4_orders.json"
    if not os.path.exists(orders_path):
        return []

    with open(orders_path) as f:
        orders_data = json.load(f)

    positions = []
    for order in orders_data.get("trade_orders", []):
        if order.get("action") == "BUY":
            positions.append({
                "ticker": order["ticker"],
                "shares": order["shares"],
                "entry_price": order["entry_price"],
                "stop_loss": order["stop_loss"],
                "stop_anchor_label": order.get("stop_anchor_label", ""),
                "theme": order.get("theme", ""),
                "thesis": order.get("thesis", ""),
                "dollar_risk": order.get("dollar_risk", 0),
            })

    print(f"[Agent 5] Loaded {len(positions)} positions from orders file (fallback)")
    return positions


def calculate_trailing_stops(positions: list, snapshot: dict) -> list:
    """
    Pure Python trailing stop calculator. No LLM needed.

    Rules:
      - Up > 2.5% from entry → tighten stop to breakeven (entry price)
      - Up > 3% from entry  → trail stop to entry + 25% of gains
      - Up > 5% from entry  → trail stop to entry + 50% of gains
      - Up > 10% from entry → trail stop to entry + 75% of gains
      - Up > 15% from entry → trail stop to entry + 85% of gains (big runner)
      - Current price <= stop → MECHANICAL_CLOSE
      - Never widen a stop (new_stop >= original_stop always)

    Returns each position enriched with:
      new_stop, mechanical_action (HOLD/CLOSE), pnl_pct, pnl_dollars
    """
    # Load persistent high-water-mark state
    hwm_state = _load_portfolio_state()

    results = []
    active_tickers = set()

    for pos in positions:
        ticker = pos["ticker"]
        active_tickers.add(ticker)
        entry_price = pos["entry_price"]
        original_stop = pos.get("stop_loss", 0)
        shares = pos.get("shares", 0)

        # ━━━ STOP FLOOR: no position may ever sit unprotected ━━━
        # Some positions arrive with no stop (0/None) — e.g. SMCI was carried
        # with a $0 stop = ZERO downside protection. Seed a default protective
        # floor at 8% below entry (≈ the 2x-ATR distance Agent 4 produces) so
        # the trailing logic below always has a real stop to ratchet up from.
        STOP_FLOOR_PCT = 0.08
        if not original_stop or original_stop <= 0:
            if entry_price and entry_price > 0:
                original_stop = round(entry_price * (1 - STOP_FLOOR_PCT), 2)
                print(f"  🩹 {ticker}: had no stop ($0) — seeded protective floor "
                      f"${original_stop} (8% below entry ${entry_price})")

        price_data = snapshot.get(ticker, {})
        current_price = price_data.get("current_price")

        if current_price is None or entry_price <= 0:
            results.append({
                **pos,
                "current_price": current_price,
                "pnl_pct": 0,
                "pnl_dollars": 0,
                "new_stop": original_stop,
                "mechanical_action": "HOLD",
                "trailing_stop_note": "No price data available",
                "intraday": price_data,
            })
            continue

        # Calculate P&L
        pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
        pnl_dollars = round((current_price - entry_price) * shares, 2)

        # Corporate Action Guard (Reverse Split protection)
        # A 1-for-10 reverse split will show as a 900% gain. Lock the stop and flag for human review.
        if pnl_pct > 150.0:
            results.append({
                **pos,
                "current_price": current_price,
                "pnl_pct": pnl_pct,
                "pnl_dollars": 0,
                "new_stop": original_stop,
                "mechanical_action": "HOLD",
                "trailing_stop_note": f"⚠️ CORPORATE ACTION SUSPECTED ({pnl_pct:.0f}% gain). Trailing stop locked. Human review required.",
                "intraday": price_data,
            })
            print(f"  ⚠️ {ticker}: {pnl_pct:.0f}% gain — CORPORATE ACTION SUSPECTED, stop locked")
            continue

        # Calculate trailing stop
        gain_dollars = current_price - entry_price
        new_stop = original_stop  # Start with original

        trailing_note = "Below 1% gain — original stop unchanged"

        if pnl_pct > 15:
            # Big runner — lock in 85% of the gain (tighter than the +10% tier)
            candidate_stop = round(entry_price + 0.85 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 85% of gains"
        elif pnl_pct > 10:
            # Trail to entry + 75% of gains
            candidate_stop = round(entry_price + 0.75 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 75% of gains"
        elif pnl_pct > 5:
            # Trail to entry + 50% of gains
            candidate_stop = round(entry_price + 0.50 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 50% of gains"
        elif pnl_pct > 3:
            # Trail to entry + 25% of gains (lock in a quarter of the run)
            candidate_stop = round(entry_price + 0.25 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 25% of gains"
        elif pnl_pct > 2.5:
            # Tighten to breakeven once the position has real cushion (+2.5%).
            # Was +1%, which snapped new positions to a hair-tight break-even
            # stop (entry price) on a single tick of profit — normal intraday
            # noise then scratched them out for ~$0 (see 2026-06-30 ITUB, where
            # a +1.0% wiggle pulled the stop to entry $8.02 vs $8.11 price).
            # +2.5% gives new positions room to breathe before going risk-free.
            candidate_stop = entry_price
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop tightened to breakeven"

        # Never widen a stop
        new_stop = max(new_stop, original_stop)
        new_stop = round(new_stop, 2)

        # ━━━ HIGH-WATER-MARK: Never let the stop decrease ━━━
        stored = hwm_state.get(ticker, {})
        stored_hwm_stop = stored.get("hwm_stop", 0)
        stored_hwm_price = stored.get("hwm_price", 0)

        # Enforce: stop can only ratchet up, never down
        new_stop = max(new_stop, stored_hwm_stop)
        new_stop = round(new_stop, 2)

        if new_stop > stored_hwm_stop:
            trailing_note += f" [HWM updated: ${stored_hwm_stop} → ${new_stop}]"
        elif stored_hwm_stop > 0 and new_stop == stored_hwm_stop:
            trailing_note += f" [HWM held at ${stored_hwm_stop}]"

        # Update HWM state for this ticker. Preserve any existing scaled_fraction
        # so a prior day's scale-out isn't forgotten on the next snapshot.
        hwm_state[ticker] = {
            "hwm_stop": new_stop,
            "hwm_price": max(current_price, stored_hwm_price),
            "scaled_fraction": stored.get("scaled_fraction", 0.0),
            "last_updated": datetime.now().isoformat(),
        }

        # ━━━ R-MULTIPLE SCALE-OUT ━━━
        # R = initial per-share risk = entry - original_stop. We scale at
        # R-multiples rather than flat %, so 1R means the same thing on VOO and
        # URA. scaled_fraction (persisted) tracks cumulative fraction of the
        # ORIGINAL position already sold across prior days.
        from config import SCALE_LADDER, MIN_SHARES_TO_SCALE

        scale_action = None
        scale_trim_pct = None
        scale_note = ""
        r_multiple = None

        already_sold = stored.get("scaled_fraction", 0.0)
        per_share_R = entry_price - original_stop

        # Require a REAL stop anchor (0 < stop < entry) so R is meaningful.
        # A missing/zero stop (fallback path) yields per_share_R == entry, a
        # bogus huge R — skip scaling entirely there (no scale, no crash).
        if original_stop > 0 and per_share_R > 0 and shares >= MIN_SHARES_TO_SCALE:
            r_multiple = round((current_price - entry_price) / per_share_R, 2)

            # Highest cumulative fraction whose R threshold is satisfied now.
            target_sold = 0.0
            for r_threshold, cum_fraction in SCALE_LADDER:
                if r_multiple >= r_threshold:
                    target_sold = max(target_sold, cum_fraction)

            # Only act if we owe MORE selling than we've already done.
            if target_sold > already_sold + 1e-6:
                remaining_of_original = max(1.0 - already_sold, 1e-6)
                incremental = target_sold - already_sold
                # Express the increment as a pct of CURRENT holdings (what the
                # broker trims against).
                scale_trim_pct = int(round((incremental / remaining_of_original) * 100))
                scale_trim_pct = max(1, min(scale_trim_pct, 99))
                scale_action = "TRIM"
                scale_note = (f"+{r_multiple}R reached → scale to {int(target_sold*100)}% sold "
                              f"(trim {scale_trim_pct}% of current)")
                # Once we start scaling, never let the stop sit below breakeven.
                new_stop = max(new_stop, entry_price)
                new_stop = round(new_stop, 2)
                # Persist the new cumulative fraction sold for this ticker.
                hwm_state[ticker]["scaled_fraction"] = max(already_sold, target_sold)
                hwm_state[ticker]["hwm_stop"] = new_stop

        # Check if stop is hit (mechanical CLOSE supersedes any scale-out).
        mechanical_action = "HOLD"
        if current_price <= new_stop:
            mechanical_action = "CLOSE"
            trailing_note = f"STOP HIT — current ${current_price} <= stop ${new_stop}"

        results.append({
            **pos,
            "current_price": current_price,
            "pnl_pct": pnl_pct,
            "pnl_dollars": pnl_dollars,
            "original_stop": original_stop,
            "new_stop": new_stop,
            "mechanical_action": mechanical_action,
            "trailing_stop_note": trailing_note,
            "r_multiple": r_multiple,
            "scale_action": scale_action,
            "scale_trim_pct": scale_trim_pct,
            "scale_note": scale_note,
            "intraday": price_data,
        })

    # Clean up state entries for tickers no longer in positions
    stale_tickers = [t for t in hwm_state if t not in active_tickers]
    for t in stale_tickers:
        del hwm_state[t]
        print(f"  [Agent 5] Cleaned up HWM state for closed position: {t}")

    # Persist updated state
    _save_portfolio_state(hwm_state)

    return results


def call_thesis_monitor(positions_with_stops: list, breaking_news: dict, vix_data: dict) -> dict:
    """
    Call Claude to evaluate thesis drift ONLY.
    Claude does NOT calculate stops or P&L — those are pre-computed by Python.
    """
    import anthropic
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform.")

    client = anthropic.Anthropic(api_key=api_key)

    # Load Agent 1 morning regime if available
    morning_regime = "UNKNOWN"
    try:
        directive_path = "output/agent1_directive.json"
        if os.path.exists(directive_path):
            with open(directive_path) as f:
                directive = json.load(f)
            morning_regime = directive.get("regime", "UNKNOWN")
    except Exception:
        pass

    # Build position summaries for Claude (thesis focus, not math)
    position_summaries = []
    for pos in positions_with_stops:
        ticker = pos["ticker"]
        news = breaking_news.get(ticker, ["No news"])
        position_summaries.append({
            "ticker": ticker,
            "original_thesis": pos.get("thesis", "N/A"),
            "theme": pos.get("theme", "N/A"),
            "pnl_pct": pos.get("pnl_pct", 0),
            "mechanical_action": pos.get("mechanical_action", "HOLD"),
            "breaking_news": news,
        })

    user_message = f"""Review the fundamental thesis for each open position.

AGENT 1 MORNING REGIME: {morning_regime}

VIX STATUS:
{json.dumps(vix_data, indent=2)}

POSITIONS (with Python-computed trailing stops already applied):
{json.dumps(position_summaries, indent=2)}

Your job is ONLY to assess thesis drift. Python has already computed all trailing stops.
- Do NOT calculate P&L or stops.
- Focus on: Has the narrative broken? Has the macro regime shifted?
- If morning regime is CRISIS or VIX > 35, all theses are BROKEN.

Current date/time: {datetime.now().isoformat()}

Respond with ONLY the JSON output."""

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 5] Calling {MODEL} for thesis review (attempt {attempt + 1}/{MAX_RETRIES})...")

            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                temperature=1,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text.strip()
            # Strip scratchpad if present
            if "</research_scratchpad>" in raw_text:
                raw_text = raw_text.split("</research_scratchpad>", 1)[1].strip()

            # Try code-fenced JSON first
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Find the outermost JSON object by matching balanced braces
                brace_depth = 0
                start = None
                json_str = None
                for i, ch in enumerate(raw_text):
                    if ch == '{':
                        if brace_depth == 0:
                            start = i
                        brace_depth += 1
                    elif ch == '}':
                        brace_depth -= 1
                        if brace_depth == 0 and start is not None:
                            candidate = raw_text[start:i+1]
                            try:
                                json.loads(candidate)
                                json_str = candidate
                                break
                            except json.JSONDecodeError:
                                start = None
                                continue

                if json_str is None:
                    raise json.JSONDecodeError("No valid JSON object found in response", raw_text[:200], 0)

            return json.loads(json_str)

        except RuntimeError:
            raise  # Re-raise missing API key
        except Exception as e:
            last_error = e
            print(f"  [Agent 5] Claude error: {e}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    raise Exception(f"{MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent5_preflight() -> dict:
    """3:25 PM pre-flight: Snapshot current prices for open positions."""
    # ━━━ HOLIDAY GATE: Abort if market is closed (prevents holiday runs) ━━━
    from safeguards import assert_market_open
    assert_market_open()

    print("[Agent 5 Pre-Flight] Snapshotting prices at 3:25 PM...")

    positions = load_open_positions()
    if not positions:
        print("[Agent 5 Pre-Flight] No open positions to monitor.")
        return {"positions": [], "snapshot": {}}

    tickers = [p["ticker"] for p in positions]
    snapshot = snapshot_prices(tickers)

    # Also grab VIX for end-of-day risk assessment
    vix_snapshot = snapshot_prices(["^VIX"])
    snapshot["VIX"] = vix_snapshot.get("^VIX", {"error": "unavailable"})

    # Save snapshot
    os.makedirs("output", exist_ok=True)
    with open("output/agent5_snapshot.json", "w") as f:
        json.dump({"positions": positions, "snapshot": snapshot}, f, indent=2)

    print(f"[Agent 5 Pre-Flight] Snapshot saved for {len(positions)} positions")
    return {"positions": positions, "snapshot": snapshot}


def run_agent5(positions: list = None, snapshot: dict = None,
               mechanical_only: bool = False) -> dict:
    """
    Run Agent 5 at 3:30 PM: Python trailing stops FIRST, then Claude thesis review, then merge.

    Merge logic:
      - If Python says CLOSE (stop hit) → CLOSE
      - If Claude says CLOSE (thesis broken) → CLOSE
      - Otherwise → HOLD
    """
    # Load pre-flight data if not passed
    if positions is None or snapshot is None:
        preflight_path = "output/agent5_snapshot.json"
        if not os.path.exists(preflight_path):
            preflight = run_agent5_preflight()
            positions = preflight["positions"]
            snapshot = preflight["snapshot"]
        else:
            with open(preflight_path) as f:
                data = json.load(f)
            positions = data["positions"]
            snapshot = data["snapshot"]

    if not positions:
        return {
            "success": True,
            "decisions": [],
            "note": "No open positions to monitor.",
        }

    vix_data = snapshot.get("VIX", {})

    # ━━━ STEP 1: Python trailing stops (pure math, no LLM) ━━━
    print(f"[Agent 5] Step 1: Calculating trailing stops for {len(positions)} positions...")
    positions_with_stops = calculate_trailing_stops(positions, snapshot)

    for pos in positions_with_stops:
        action_emoji = "🔴" if pos["mechanical_action"] == "CLOSE" else "🟢"
        print(
            f"  {action_emoji} {pos['ticker']}: "
            f"P&L {pos['pnl_pct']:+.2f}% | "
            f"Stop ${pos.get('original_stop', 0)} → ${pos['new_stop']} | "
            f"{pos['mechanical_action']}"
        )

    # ━━━ STEP 2: Fetch breaking news for thesis review ━━━
    tickers = [p["ticker"] for p in positions]
    breaking_news = fetch_breaking_news(tickers)

    # ━━━ STEP 3: Claude thesis review (qualitative only) ━━━
    print(f"[Agent 5] Step 2: Claude thesis review...")

    thesis_result = None
    if mechanical_only:
        # Hourly reinforcement mode: skip the (expensive, slow-moving) Claude
        # thesis review entirely. Pure mechanical trailing-stop ratchet +
        # mechanical CLOSE on stop-hit. Thesis review stays on the daily run.
        print("  [Agent 5] MECHANICAL-ONLY mode — skipping thesis review.")
    else:
        try:
            thesis_result = call_thesis_monitor(positions_with_stops, breaking_news, vix_data)
        except RuntimeError:
            # No API key for the qualitative thesis review. DO NOT bail — the
            # mechanical trailing stops are pure Python and MUST still be applied
            # to the broker. Bailing here was the root cause of stale broker
            # stops: the engine computed higher stops but never pushed them.
            print("  [Agent 5] ⚠️ No API key for thesis review — proceeding with "
                  "MECHANICAL trailing stops only (still applied to broker).")
        except Exception as e:
            print(f"  [Agent 5] ⚠️ Claude thesis review failed: {e}")
            print(f"  [Agent 5] Proceeding with mechanical stops only.")

    # ━━━ STEP 4: Merge mechanical stops + thesis review ━━━
    print(f"[Agent 5] Step 3: Merging mechanical stops + thesis review...")

    # Build thesis lookup
    thesis_lookup = {}
    crisis_liquidation = False
    if thesis_result:
        crisis_liquidation = thesis_result.get("crisis_liquidation", False)
        for review in thesis_result.get("thesis_reviews", []):
            thesis_lookup[review["ticker"]] = review

    decisions = []
    for pos in positions_with_stops:
        ticker = pos["ticker"]
        mechanical = pos["mechanical_action"]
        thesis_review = thesis_lookup.get(ticker, {})
        thesis_status = thesis_review.get("thesis_status", "INTACT")
        thesis_override = thesis_review.get("override_action")
        news_category = thesis_review.get("news_category", "")

        # MATERIALITY GATE: Override LLM hallucinated thesis breaks on general noise.
        # If the LLM says BROKEN but the news is just macro noise (not a material
        # company-specific event), force thesis back to INTACT. Prevents panic sells
        # on "Fed said something" when the actual stock thesis hasn't changed.
        if thesis_status == "BROKEN" and news_category in ("MACRO_NOISE", "SECTOR_ROTATION", "GENERAL_MARKET", ""):
            print(f"  🛡️ {ticker}: MATERIALITY GATE — LLM said BROKEN but news_category='{news_category}' → overriding to INTACT")
            thesis_status = "INTACT"
            thesis_override = None

        # Merge logic. Priority: crisis > mechanical stop > thesis break > scale-out > hold.
        trim_pct = None
        if crisis_liquidation:
            action = "CLOSE"
            reasoning = "CRISIS_LIQUIDATION — all positions closed."
        elif mechanical == "CLOSE":
            action = "CLOSE"
            reasoning = f"MECHANICAL STOP HIT: {pos['trailing_stop_note']}"
            if thesis_status == "BROKEN":
                reasoning += f" + THESIS BROKEN: {thesis_review.get('thesis_assessment', '')}"
        elif thesis_override == "CLOSE":
            action = "CLOSE"
            reasoning = f"THESIS OVERRIDE: {thesis_review.get('thesis_assessment', 'Thesis broken per Claude review.')}"
        elif pos.get("scale_action") == "TRIM":
            action = "TRIM"
            trim_pct = pos.get("scale_trim_pct", 33)
            reasoning = f"SCALE-OUT: {pos.get('scale_note', '')}"
            if thesis_status == "DEGRADED":
                reasoning += f" | ⚠️ Thesis DEGRADED: {thesis_review.get('thesis_assessment', '')}"
        else:
            action = "HOLD"
            parts = [pos["trailing_stop_note"]]
            if thesis_status == "DEGRADED":
                parts.append(f"⚠️ Thesis DEGRADED: {thesis_review.get('thesis_assessment', '')}")
            elif thesis_status == "INTACT":
                parts.append("Thesis intact.")
            reasoning = " | ".join(parts)

        decisions.append({
            "ticker": ticker,
            "action": action,
            "current_price": pos.get("current_price"),
            "entry_price": pos.get("entry_price"),
            "original_stop": pos.get("original_stop", pos.get("stop_loss", 0)),
            "new_stop": pos.get("new_stop"),
            "pnl_pct": pos.get("pnl_pct", 0),
            "pnl_dollars": pos.get("pnl_dollars", 0),
            "mechanical_action": mechanical,
            "thesis_status": thesis_status,
            "thesis_override": thesis_override,
            "trim_pct": trim_pct,
            "reasoning": reasoning,
        })

        action_emoji = {"HOLD": "✅", "TRIM": "✂️", "CLOSE": "🚪"}.get(action, "❓")
        print(f"  {action_emoji} {ticker}: {action} — {reasoning[:80]}")

    portfolio_summary = ""
    if thesis_result:
        portfolio_summary = thesis_result.get("macro_assessment", "")

    return {
        "success": True,
        "agent": "position_monitor",
        "timestamp": datetime.now().isoformat(),
        "crisis_liquidation": crisis_liquidation,
        "decisions": decisions,
        "portfolio_summary": portfolio_summary,
    }


def format_agent5_for_telegram(result: dict) -> str:
    """Format Agent 5 output for Telegram."""
    if not result.get("success"):
        return f"⚠️ Agent 5 FAILED: {result.get('error', 'Unknown')}"

    decisions = result.get("decisions", [])
    if not decisions:
        return (
            f"{'='*30}\n"
            f"🕒 AGENT 5: POSITION MONITOR (3:30 PM)\n"
            f"{'='*30}\n\n"
            f"No open positions to review."
        )

    lines = [
        f"{'='*30}",
        f"🕒 AGENT 5: POSITION MONITOR (3:30 PM)",
        f"{'='*30}",
        f"",
    ]

    if result.get("crisis_liquidation"):
        lines.append("🚨 CRISIS LIQUIDATION — ALL POSITIONS CLOSED")
        lines.append("")

    for d in decisions:
        action = d.get("action", "UNKNOWN")
        emoji = {"HOLD": "✅", "TRIM": "✂️", "CLOSE": "🚪"}.get(action, "❓")

        pnl = d.get("pnl_pct", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"

        thesis = d.get("thesis_status", "N/A")
        thesis_emoji = {"INTACT": "🟢", "DEGRADED": "🟡", "BROKEN": "🔴"}.get(thesis, "⚪")

        lines.append(f"{'─'*25}")
        lines.append(f"{emoji} {d.get('ticker')} — {action}")
        lines.append(f"")
        lines.append(f"  {pnl_emoji} P&L: {pnl:+.2f}% (${d.get('pnl_dollars', 0):+.2f})")
        lines.append(f"  💲 Current: ${d.get('current_price')} | Entry: ${d.get('entry_price')}")
        lines.append(f"  🛑 Stop: ${d.get('original_stop')} → ${d.get('new_stop')}")
        lines.append(f"  {thesis_emoji} Thesis: {thesis}")

        if d.get("trim_pct"):
            lines.append(f"  ✂️ Trim: {d.get('trim_pct')}%")

        lines.append(f"  💬 {d.get('reasoning', '')}")
        lines.append(f"")

    if result.get("portfolio_summary"):
        lines.append(f"📋 {result.get('portfolio_summary')}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Run pre-flight first
    preflight = run_agent5_preflight()

    # Then run agent
    result = run_agent5(preflight["positions"], preflight["snapshot"])
    print("\n" + format_agent5_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent5_decisions.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 5] Decisions saved to output/agent5_decisions.json")

        # ━━━ APPLY DECISIONS TO THE BROKER ━━━
        # This is the step that was MISSING entirely: computed trailing stops
        # were saved to JSON but never pushed to Robinhood, so the live stop
        # orders went stale (placed once, never replaced). Now we actually
        # execute HOLD_STOP_TIGHTENED / CLOSE / TRIM against the broker.
        decisions = result.get("decisions", [])
        crisis = result.get("crisis_liquidation", False)
        if decisions or crisis:
            try:
                from broker_factory import get_broker
                broker = get_broker()
            except Exception:
                # Fall back to the Robinhood broker directly if factory absent.
                from robinhood_broker import RobinhoodBroker
                broker = RobinhoodBroker()
            try:
                print(f"\n[Agent 5] Applying {len(decisions)} decision(s) to broker...")
                exec_results = broker.execute_agent5_decisions(decisions, crisis=crisis)
                for r in exec_results:
                    print(f"  → {r.get('ticker')}: {r.get('action')} — {r.get('status')}"
                          + (f" (stop ${r.get('new_stop')})" if r.get('new_stop') else ""))
                with open("output/agent5_execution.json", "w") as f:
                    json.dump(exec_results, f, indent=2, default=str)
                print(f"[Agent 5] Execution results saved to output/agent5_execution.json")
            except Exception as e:
                print(f"[Agent 5] ⚠️ Broker execution FAILED: {e}")
