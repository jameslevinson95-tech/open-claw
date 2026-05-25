"""
Agent 2: Fundamental Screener — v4.0 (Gemini Deep Research Max)
Model: Gemini Deep Research Max (Google) via Interactions API
Role: Given Agent 1's directive + SCREENER_UNIVERSE + FUNDAMENTAL_DATA
      (all pre-fetched by Python), select 1-3 tickers with rigorous analysis.

Changes from v3.0:
- Switched from Claude Opus 4.7 to Gemini Deep Research Max
- Uses Interactions API (async) for comprehensive research synthesis
- Deep Research Max: maximum comprehensiveness, accuracy-critical investigations
- Python pre-fetches ALL fundamental data — model does NOT fetch or browse
- Verbatim THEME_MATCH, SOURCE enum
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Gemini Deep Research (speed/efficiency)
MODEL = "deep-research-preview-04-2026"
MODEL_DISPLAY = "Gemini Deep Research"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_RETRIES = 3
RETRY_DELAY = 5
POLL_INTERVAL = 15  # seconds between status polls
MAX_POLL_TIME = 300  # 5 min max wait for deep research to complete

SYSTEM_PROMPT = """You are Agent 2: The Fundamental Screener for a $100,000 speculative spot-only trading account.

YOUR JOB: Given Agent 1's regime directive, a pre-filtered SCREENER_UNIVERSE, and pre-fetched FUNDAMENTAL_DATA (all provided by Python — you do NOT fetch any data yourself), select 1-3 candidates through rigorous quantitative analysis.

CRITICAL RULES:
1. You may ONLY select tickers from the provided SCREENER_UNIVERSE list. Do NOT suggest any ticker not on the list. Do NOT fetch, browse, or look up any data — use ONLY what Python injected into this prompt.
2. CONVICTION_TIER must be exactly one of: PASS, STRONG, or EXCEPTIONAL (string enum). Numeric scores are FORBIDDEN and will crash the pipeline.
   - PASS: Meets all screens, thesis is coherent, no red flags. Default state for any candidate that survives Step 3.
   - STRONG: PASS + at least two of: (a) clear near-term catalyst, (b) valuation in bottom tercile, (c) momentum confirmed by price > MA50 > MA200.
   - EXCEPTIONAL: STRONG + thesis is asymmetric AND theme is the single strongest in Agent 1's preferred themes.
   - Do NOT output STRONG or EXCEPTIONAL for more than one candidate per run unless explicitly justified in screening_notes.
3. You must COPY the PREFERRED_THEME string from Agent 1 EXACTLY character-for-character into your THEME_MATCH field. Do not summarize, paraphrase, or reword it even slightly.
4. SOURCE must be exactly one of: "Newsletter" or "Screener Stage 2" (enum). For screener-sourced picks, use "Screener Stage 2".
5. Each candidate needs a rigorous quantitative thesis grounded in the FUNDAMENTAL_DATA provided, plus a specific near-term catalyst.
6. If the regime is DEFER, CRISIS with Bunker posture, output an empty candidates array.
7. All surviving candidates must be at least PASS tier.

<deep_research_protocol>
CRITICAL: You must conduct your analysis inside a <research_scratchpad> block before generating your final structured output.
Step 1: Inventory the exact numerical data and fundamentals injected by Python.
Step 2: Verify the asset passes the >$5 price and >$100M market cap constraints.
Step 3: Argue the downside. Why might this setup fail? (Play Devil's Advocate).
Step 4: Brutally interrogate the fundamentals to assign a CONVICTION_TIER (PASS, STRONG, or EXCEPTIONAL).
Step 5: Ensure the THEME_MATCH is a verbatim, character-for-character echo of Agent 1's theme.
Only after completing this <research_scratchpad> block may you output the final JSON.
</deep_research_protocol>

OUTPUT FORMAT:
First, output your <research_scratchpad>...</research_scratchpad> analysis.
Then, output ONLY this JSON structure (no markdown, no code blocks):
{
  "agent": "fundamental_screener",
  "timestamp": "<ISO timestamp>",
  "regime_received": "<regime from Agent 1>",
  "candidates": [
    {
      "ticker": "<SYMBOL from SCREENER_UNIVERSE>",
      "name": "<company name>",
      "type": "<equity | sector ETF | commodity ETF | crypto>",
      "theme_match": "<EXACT string from Agent 1 preferred_themes>",
      "conviction_tier": "<PASS | STRONG | EXCEPTIONAL>",
      "thesis": "<2-3 sentences grounded in the numerical fundamentals>",
      "catalyst": "<specific near-term catalyst>",
      "source": "Screener Stage 2"
    }
  ],
  "screening_notes": "<brief note on selection process and rejected names>"
}"""

# Strict JSON schema for structured outputs (Jamie fix #3)
# This prevents Gemini from outputting "HIGH" instead of an integer
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "agent": {"type": "string"},
        "timestamp": {"type": "string"},
        "regime_received": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["equity", "sector ETF", "commodity ETF", "crypto"]},
                    "theme_match": {"type": "string"},
                    "conviction_tier": {"type": "string", "enum": ["PASS", "STRONG", "EXCEPTIONAL"]},
                    "thesis": {"type": "string"},
                    "catalyst": {"type": "string"},
                    "source": {"type": "string", "enum": ["Newsletter", "Screener Stage 2"]},
                },
                "required": ["ticker", "name", "type", "theme_match", "conviction_score", "thesis", "catalyst", "source"],
            },
        },
        "screening_notes": {"type": "string"},
    },
    "required": ["agent", "timestamp", "regime_received", "candidates", "screening_notes"],
}


def prefetch_fundamental_data(screener_universe: list) -> dict:
    """
    Pre-fetch ALL fundamental data for the screener universe.
    Uses bulk yf.download() for price history (much faster than per-ticker),
    then per-ticker yf.Ticker().info for fundamentals.
    """
    fundamentals = {}
    tickers_list = [t["ticker"] for t in screener_universe]
    print(f"  [Agent 2] Pre-fetching fundamentals for {len(tickers_list)} tickers (bulk download)...")

    # Bulk download price history — much faster than individual calls
    try:
        bulk_hist = yf.download(tickers_list, period="1mo", group_by="ticker", threads=True, progress=False)
    except Exception as e:
        print(f"  [Agent 2] Bulk download failed: {e}, falling back to per-ticker")
        bulk_hist = None

    def _fetch_single_ticker_data(entry):
        """Fetch fundamental data for a single ticker. Designed for parallel execution."""
        ticker = entry["ticker"]
        try:
            # Get price data from bulk download
            if bulk_hist is not None and len(tickers_list) > 1:
                try:
                    hist = bulk_hist[ticker]
                    closes = [float(c) for c in hist["Close"].dropna().values.flatten()]
                    volumes = [int(v) for v in hist["Volume"].dropna().values.flatten()]
                except (KeyError, TypeError):
                    closes = []
                    volumes = []
            else:
                hist = yf.Ticker(ticker).history(period="1mo")
                closes = [float(c) for c in hist["Close"].values.flatten()] if not hist.empty else []
                volumes = [int(v) for v in hist["Volume"].values.flatten()] if not hist.empty else []

            if not closes:
                return ticker, {"error": "No price history"}

            # Get fundamentals from .info
            stock = yf.Ticker(ticker)
            info = stock.info

            prior_close = closes[-1]
            price_5d = closes[-5] if len(closes) >= 5 else prior_close
            price_20d = closes[0]
            avg_vol = int(sum(volumes) / len(volumes)) if volumes else 0

            return ticker, {
                "prior_close": round(prior_close, 2),
                "change_5d_pct": round((prior_close - price_5d) / price_5d * 100, 2),
                "change_20d_pct": round((prior_close - price_20d) / price_20d * 100, 2),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "profit_margin": info.get("profitMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "free_cash_flow": info.get("freeCashflow"),
                "beta": info.get("beta"),
                "sector": info.get("sector", "N/A"),
                "avg_volume_20d": avg_vol,
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
            }
        except Exception as e:
            return ticker, {"error": str(e)}

    # Fetch fundamentals in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_single_ticker_data, entry): entry for entry in screener_universe}
        for future in as_completed(futures):
            ticker, data = future.result()
            fundamentals[ticker] = data

    fetched = len([v for v in fundamentals.values() if "error" not in v])
    print(f"  [Agent 2] Fetched fundamentals for {fetched}/{len(screener_universe)} tickers")
    return fundamentals


def _build_research_prompt(directive: dict, screener_universe: list, fundamental_data: dict, held_tickers: list = None) -> str:
    """
    Build the full research prompt with all pre-fetched data.
    Used by both Deep Research Max and fallback paths.
    """
    screener_lines = []
    for s in screener_universe:
        ticker = s["ticker"]
        fund = fundamental_data.get(ticker, {})

        if "error" in fund:
            continue

        mkt_cap = fund.get("market_cap", 0)
        cap_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap and mkt_cap > 1e9 else f"${mkt_cap/1e6:.0f}M" if mkt_cap else "N/A"

        line = (
            f"  {ticker} | {s.get('name', '')} | {s.get('sector', 'N/A')}\n"
            f"    Prior Close: ${fund.get('prior_close', '?')} | Mkt Cap: {cap_str}\n"
            f"    5d Change: {fund.get('change_5d_pct', '?')}% | 20d Change: {fund.get('change_20d_pct', '?')}%\n"
            f"    P/E: {fund.get('pe_ratio', 'N/A')} | Fwd P/E: {fund.get('forward_pe', 'N/A')} | PEG: {fund.get('peg_ratio', 'N/A')}\n"
            f"    P/B: {fund.get('price_to_book', 'N/A')} | Beta: {fund.get('beta', 'N/A')}\n"
            f"    Rev Growth: {fund.get('revenue_growth', 'N/A')} | Earnings Growth: {fund.get('earnings_growth', 'N/A')}\n"
            f"    Profit Margin: {fund.get('profit_margin', 'N/A')} | D/E: {fund.get('debt_to_equity', 'N/A')}\n"
            f"    FCF: {fund.get('free_cash_flow', 'N/A')} | 52w: ${fund.get('52w_low', '?')} — ${fund.get('52w_high', '?')}"
        )
        screener_lines.append(line)

    screener_text = "\n".join(screener_lines)

    prompt = f"""{SYSTEM_PROMPT}

---

Here is Agent 1's directive and the pre-filtered SCREENER_UNIVERSE with FUNDAMENTAL_DATA.
ALL data has been pre-fetched by Python. Do NOT look up, browse, or fetch any additional data.
You may ONLY select from the tickers listed below.

AGENT 1 DIRECTIVE:
{json.dumps(directive, indent=2)}

SCREENER_UNIVERSE WITH FUNDAMENTALS ({len(screener_lines)} tickers with data):
{screener_text}

RULES REMINDER:
- CONVICTION_TIER must be exactly one of: PASS, STRONG, or EXCEPTIONAL
- THEME_MATCH must be copied EXACTLY character-for-character from preferred_themes
- SOURCE must be "Screener Stage 2"

CURRENT PORTFOLIO:
You currently hold: {held_tickers if held_tickers else '(empty — full freedom)'}
Do NOT select candidates highly correlated with existing holdings. Diversify across sectors and themes.
If portfolio is empty, you have full freedom.

Current date/time: {datetime.now().isoformat()}

After your analysis, output the final result as a JSON object with this schema:
{{
  "candidates": [
    {{
      "ticker": "SYMBOL",
      "name": "Company Name",
      "thesis": "Why this stock fits the regime and theme",
      "catalyst": "Near-term catalyst",
      "theme_match": "Exact theme from Agent 1",
      "conviction_tier": "PASS|STRONG|EXCEPTIONAL",
      "conviction_score": 7,
      "source": "Screener Stage 2"
    }}
  ],
  "screening_notes": "Brief summary of screening logic"
}}"""
    return prompt


def _submit_deep_research(prompt: str, api_key: str) -> str:
    """
    Submit a Deep Research Max interaction and return the interaction ID.
    """
    url = f"{GEMINI_API_BASE}/interactions"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "agent": MODEL,
        "input": {"type": "text", "text": prompt},
        "background": True,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    interaction_id = data.get("id")
    if not interaction_id:
        raise RuntimeError(f"No interaction ID returned: {data}")

    print(f"  [Agent 2] Deep Research task submitted: {interaction_id}")
    return interaction_id


def _poll_deep_research(interaction_id: str, api_key: str) -> dict:
    """
    Poll for Deep Research completion. Returns the full interaction result.
    """
    url = f"{GEMINI_API_BASE}/interactions/{interaction_id}"
    headers = {"x-goog-api-key": api_key}

    start_time = time.time()
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > MAX_POLL_TIME:
            raise TimeoutError(f"Deep Research timed out after {MAX_POLL_TIME}s")

        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status != last_status:
            print(f"  [Agent 2] Research status: {status} ({elapsed:.0f}s elapsed)")
            last_status = status

        if status == "completed":
            return data
        elif status == "failed":
            error = data.get("error", "unknown error")
            raise RuntimeError(f"Deep Research failed: {error}")

        time.sleep(POLL_INTERVAL)


def _extract_json_from_report(report_text: str) -> dict:
    """
    Extract the JSON candidates object from a Deep Research report.
    The report may contain markdown, citations, and prose around the JSON.
    """
    # Try to find JSON block in markdown code fences
    if "```json" in report_text:
        json_block = report_text.split("```json", 1)[1]
        json_block = json_block.split("```", 1)[0].strip()
        return json.loads(json_block)

    if "```" in report_text:
        parts = report_text.split("```")
        for i in range(1, len(parts), 2):  # odd indices are inside fences
            block = parts[i].strip()
            if block.startswith("{"):
                return json.loads(block)

    # Try to find a raw JSON object
    brace_depth = 0
    start = None
    for i, ch in enumerate(report_text):
        if ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start is not None:
                candidate = report_text[start:i+1]
                try:
                    parsed = json.loads(candidate)
                    if "candidates" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    start = None
                    continue

    raise json.JSONDecodeError("No valid JSON with 'candidates' found in report", report_text[:200], 0)


def call_deep_research(directive: dict, screener_universe: list, fundamental_data: dict, held_tickers: list = None) -> dict:
    """
    Send directive + screener + fundamentals to Gemini Deep Research Max.
    Uses the Interactions API (async).
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("No GOOGLE_API_KEY — set in .env to use Gemini Deep Research Max.")

    prompt = _build_research_prompt(directive, screener_universe, fundamental_data, held_tickers)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 2] Calling {MODEL_DISPLAY} (attempt {attempt + 1}/{MAX_RETRIES})...")

            # Submit async research task
            interaction_id = _submit_deep_research(prompt, api_key)

            # Poll for completion
            result = _poll_deep_research(interaction_id, api_key)

            # Extract the report text from outputs
            outputs = result.get("outputs", [])
            if not outputs:
                raise RuntimeError("Deep Research completed but returned no outputs")

            # The last output typically contains the synthesized report
            report_text = ""
            for output in outputs:
                text = output.get("text", "")
                if text:
                    report_text = text  # use the last text output

            if not report_text:
                raise RuntimeError("Deep Research outputs contained no text")

            print(f"  [Agent 2] Report received ({len(report_text)} chars)")

            # Extract JSON from the report
            parsed = _extract_json_from_report(report_text)

            # Validate conviction_tier enums
            for c in parsed.get("candidates", []):
                tier = c.get("conviction_tier")
                if tier not in ("PASS", "STRONG", "EXCEPTIONAL"):
                    score = c.get("conviction_score")
                    if isinstance(score, int):
                        if score >= 9:
                            c["conviction_tier"] = "EXCEPTIONAL"
                        elif score >= 7:
                            c["conviction_tier"] = "STRONG"
                        else:
                            c["conviction_tier"] = "PASS"
                    else:
                        raise ValueError(f"conviction_tier must be PASS/STRONG/EXCEPTIONAL, got: {tier}")
                source = c.get("source")
                if source not in ("Newsletter", "Screener Stage 2"):
                    c["source"] = "Screener Stage 2"  # Auto-fix common Deep Research output

            print(f"  [Agent 2] Success with {MODEL_DISPLAY}")
            return parsed

        except json.JSONDecodeError as je:
            last_error = je
            print(f"  [Agent 2] {MODEL_DISPLAY} returned unparseable report (attempt {attempt + 1}), retrying...")
            time.sleep(RETRY_DELAY)
        except TimeoutError as te:
            last_error = te
            print(f"  [Agent 2] {MODEL_DISPLAY} timed out (attempt {attempt + 1}), retrying...")
            time.sleep(RETRY_DELAY)
        except ValueError as ve:
            last_error = ve
            print(f"  [Agent 2] {MODEL_DISPLAY} validation error: {ve}, retrying...")
            time.sleep(RETRY_DELAY)
        except Exception as e:
            last_error = e
            print(f"  [Agent 2] {MODEL_DISPLAY} error: {e}")
            time.sleep(RETRY_DELAY)

    raise Exception(f"{MODEL_DISPLAY} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent2(directive: dict = None, screener_universe: list = None) -> dict:
    """Run Agent 2: Pre-fetch fundamentals, call Deep Research Max with full context."""

    # Load directive
    if directive is None:
        path = "output/agent1_directive.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No Agent 1 directive found."}
        with open(path) as f:
            directive = json.load(f)

    # Load screener universe
    if screener_universe is None:
        path = "output/screener_universe.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No screener universe found. Run preflight.py first."}
        with open(path) as f:
            screener_universe = json.load(f)

    regime = directive.get("regime", "UNKNOWN")
    conviction_floor = directive.get("conviction_floor", 5)
    print(f"[Agent 2] Regime: {regime} | Conviction floor: {conviction_floor}")

    # DEFER or CRISIS = no trades
    if regime in ("DEFER", "CRISIS"):
        return {
            "success": True,
            "candidates": [],
            "screening_notes": f"Regime is {regime}. No candidates.",
            "directive_used": directive,
        }

    # Pre-fetch ALL fundamental data BEFORE calling the model
    print("[Agent 2] Pre-fetching fundamental data for entire screener universe...")
    fundamental_data = prefetch_fundamental_data(screener_universe)

    # Fetch current Alpaca positions to avoid portfolio blindness
    try:
        from broker import AlpacaBroker
        broker = AlpacaBroker()
        current_positions = broker.get_positions()
        held_tickers = [p["ticker"] for p in current_positions]
    except Exception:
        held_tickers = []

    if held_tickers:
        print(f"[Agent 2] Current portfolio: {held_tickers}")
    else:
        print(f"[Agent 2] No current positions (or broker unavailable)")

    # Call Deep Research Max with full context
    print(f"[Agent 2] Calling {MODEL_DISPLAY} with {len(screener_universe)} tickers + fundamentals...")
    try:
        model_result = call_deep_research(directive, screener_universe, fundamental_data, held_tickers=held_tickers)
    except RuntimeError as re:
        # No API key
        return {"success": False, "needs_subagent": True, "error": str(re)}
    except Exception as e:
        return {"success": False, "error": f"Deep Research Max error: {e}"}

    candidates = model_result.get("candidates", [])

    # Filter by conviction tier
    pre_filter = len(candidates)
    tier_order = {"PASS": 1, "STRONG": 2, "EXCEPTIONAL": 3}
    candidates = [c for c in candidates if c.get("conviction_tier") in tier_order]
    if len(candidates) < pre_filter:
        print(f"  [Agent 2] Filtered {pre_filter - len(candidates)} candidates below conviction floor {conviction_floor}")

    # Validate tickers are in screener universe
    valid_tickers = {s["ticker"] for s in screener_universe}
    invalid = [c for c in candidates if c.get("ticker") not in valid_tickers]
    if invalid:
        print(f"  [Agent 2] WARNING: Removing {len(invalid)} tickers not in screener: {[c['ticker'] for c in invalid]}")
        candidates = [c for c in candidates if c.get("ticker") in valid_tickers]

    print(f"[Agent 2] {len(candidates)} candidates: {[c.get('ticker') for c in candidates]}")

    # Attach the pre-fetched fundamentals to each candidate
    for c in candidates:
        ticker = c.get("ticker")
        c["fundamentals"] = fundamental_data.get(ticker, {"error": "not found"})

    return {
        "success": True,
        "agent": "fundamental_screener",
        "timestamp": datetime.now().isoformat(),
        "regime_received": regime,
        "candidates": candidates,
        "screening_notes": model_result.get("screening_notes", ""),
        "directive_used": directive,
    }


def format_agent2_for_telegram(result: dict) -> str:
    """Format Agent 2 output for Telegram."""
    if not result.get("success"):
        return f"⚠️ Agent 2 FAILED: {result.get('error')}"

    candidates = result.get("candidates", [])
    if not candidates:
        return (
            f"{'='*30}\n"
            f"🔍 AGENT 2: FUNDAMENTAL SCREENER (v4.0 — Deep Research Max)\n"
            f"{'='*30}\n\n"
            f"📋 Regime: {result.get('regime_received')}\n"
            f"💵 No candidates met criteria.\n"
            f"📝 {result.get('screening_notes', '')}"
        )

    lines = [
        f"{'='*30}",
        f"🔍 AGENT 2: FUNDAMENTAL SCREENER (v4.0 — Gemini Deep Research Max)",
        f"{'='*30}",
        f"",
        f"📋 Regime: {result.get('regime_received')}",
        f"🎯 Candidates: {len(candidates)}",
        f"🔬 Model: {MODEL} | Adaptive Thinking",
        f"",
    ]

    for i, c in enumerate(candidates, 1):
        fund = c.get("fundamentals", {})
        lines.append(f"{'─'*25}")
        lines.append(f"#{i}  {c.get('ticker')} — {c.get('name')}")
        lines.append(f"    Theme: {c.get('theme_match')}")
        lines.append(f"    Conviction: {c.get('conviction_tier', 'N/A')} | Source: {c.get('source', 'N/A')}")
        lines.append(f"    💡 Thesis: {c.get('thesis')}")
        lines.append(f"    ⚡ Catalyst: {c.get('catalyst')}")

        if fund and "error" not in fund:
            mkt_cap = fund.get("market_cap")
            mkt_cap_str = f"${mkt_cap/1e9:.1f}B" if mkt_cap and mkt_cap > 1e9 else "N/A"
            lines.append(f"    📊 Close: ${fund.get('prior_close')} | P/E: {fund.get('pe_ratio', 'N/A')} | Fwd P/E: {fund.get('forward_pe', 'N/A')}")
            lines.append(f"    📊 Cap: {mkt_cap_str} | Beta: {fund.get('beta', 'N/A')} | PEG: {fund.get('peg_ratio', 'N/A')}")
            lines.append(f"    📊 5d: {fund.get('change_5d_pct')}% | 20d: {fund.get('change_20d_pct')}%")

        lines.append(f"")

    lines.append(f"📝 {result.get('screening_notes', '')}")
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent2()
    print("\n" + format_agent2_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent2_candidates.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 2] Candidates saved to output/agent2_candidates.json")
