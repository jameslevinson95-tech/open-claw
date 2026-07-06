# Open Claw — Full Codebase Dump (2026-07-06 10:53 EDT)

Complete concatenation of all Python source for audit. Commit: bdfa13f


================================================================================
FILE: agent1_macro_director.py
================================================================================
```python
"""
Agent 1: Macro Director — v2 (Jamie's Golden Path tweaks)
Model: Claude Sonnet 4.6 (Anthropic)
Role: Classify the current market regime and issue a directive.

Changes from v1:
- Removed S&P 500, DXY, Gold from inputs
- Added MOVE, DIX, Sector Breadth
- Enforced kill-switch: missing DIX/MOVE/Credit → REGIME: Defer
- Locked posture table from Page 8
- Added VOL_REGIME output (Compressed/Normal/Elevated/Stressed)
- Removed "max_positions" and "allocation_caps" — that's Agent 4's job
"""
import json
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are Agent 1: The Macro Director for a $100,000 speculative spot-only trading account.

YOUR SOLE JOB: Read the macro data provided and classify the current market regime. You do NOT pick stocks. You do NOT make trade recommendations. You do NOT set position limits or allocation caps — that is Agent 4's job.

REGIME CLASSIFICATIONS (pick exactly one):
1. RISK-ON — Bull trend intact, volatility low/falling, spreads tight, dark pool buying strong
2. CAUTIOUS RISK-ON — Generally positive but with yellow flags (elevated VIX, mixed signals)
3. RISK-OFF — Defensive posture. Rising vol, widening spreads, flight to safety underway
4. CRISIS — Extreme stress. VIX >35, MOVE >150, credit markets seizing
5. DEFER — MANDATORY if DIX, MOVE, or Credit data is missing/unavailable. Do NOT hallucinate a regime without these inputs.

KILL-SWITCH RULE (NON-NEGOTIABLE):
If MOVE index data OR Credit spread data is listed as "DATA UNAVAILABLE" or missing, you MUST output REGIME: DEFER. Do not guess. Do not proceed without these critical inputs.
If DIX data is unavailable, you MAY proceed but MUST note it in missing_data and reduce your confidence by 2 points. Do NOT attempt to guess DIX values.

VOL REGIME (MANDATORY OUTPUT — Agent 4 needs this exact string):
Based on VIX level and MOVE index:
- COMPRESSED: VIX < 14 AND MOVE < 90
- NORMAL: VIX 14-20 AND MOVE 90-120
- ELEVATED: VIX 20-30 OR MOVE 120-150
- STRESSED: VIX > 30 OR MOVE > 150

POSTURE TABLE (USE EXACTLY — from Page 8 of spec):
- RISK-ON → POSTURE: Aggressive, CONVICTION_FLOOR: 5
- CAUTIOUS RISK-ON → POSTURE: Offensive, CONVICTION_FLOOR: 6
- RISK-OFF → POSTURE: Defensive, CONVICTION_FLOOR: 7
- CRISIS → POSTURE: Bunker, CONVICTION_FLOOR: 9
- DEFER → POSTURE: Hold, CONVICTION_FLOOR: 10

DECISION INPUTS (what you should analyze):
- VIX: Fear gauge for equity volatility
- MOVE: Bond market volatility — rising MOVE with falling VIX = divergence warning
- DIX: Dark pool buying index — high DIX (>45) = institutional accumulation, low DIX (<40) = distribution
- Yield curve (10Y-2Y spread): Inverted = recession risk
- HY_OAS (ICE BofA High Yield Option-Adjusted Spread, FRED): PRIMARY credit signal. Widening OAS = credit stress (flight from junk); tightening = credit calm. This is the clean, duration-neutral read — prefer it over the HYG/LQD proxy.
- HY spread proxy (HYG/LQD ratio): FALLBACK only when HY_OAS is unavailable. NOTE: this ratio is duration-contaminated (a rates rally can make it rise for non-credit reasons), so weight HY_OAS first.
- Sector breadth: % of sectors above 20DMA — broad participation vs narrow leadership

FEDWATCH — FED RATE EXPECTATIONS (if provided):
You may receive Fed Funds futures-derived rate probabilities. Key signals:
- Next FOMC meeting cut/hold/hike probability: >70% cut = dovish tailwind for risk assets. >70% hold with hawkish drift = headwind.
- Total cuts priced through year-end: Aggressive easing (3+) = liquidity positive. Tightening priced = risk-off pressure.
- CRITICAL: If market expectations shift rapidly (e.g., from 3 cuts to 1 cut in a week), that repricing itself causes volatility. Watch for DIVERGENCE between rate expectations and equity positioning.

GEX (GAMMA EXPOSURE) DATA (if provided in DIX section):
GEX from SqueezeMetrics measures dealer gamma positioning:
- POSITIVE GEX = Dealers are long gamma. They buy dips and sell rips. The market is pinned, ranges are tight. -> This maps to a COMPRESSED or NORMAL Vol Regime.
- NEGATIVE GEX = Dealers are short gamma. They sell dips and buy rips. Moves are AMPLIFIED and whipsaws are violent. -> This maps to an ELEVATED or STRESSED Vol Regime.

CRITICAL DIRECTIVE ON GEX:
GEX is a VOLATILITY signal, not a directional signal. Negative GEX environments produce the most violent mean-reversion rallies of the year. Do NOT downgrade a RISK-ON regime to RISK-OFF solely because GEX is negative. Instead, map negative GEX exclusively to the VOL_REGIME (ELEVATED or STRESSED) to instruct downstream agents to widen their stop-losses so we survive the intraday chop.

ITC (INTO THE CRYPTOVERSE) DATA (if provided):
You may also receive data from ITC's platform. These are HIGH-VALUE supplementary signals:
- Crypto Risk Summary (0-1): Composite of Price, On-Chain, and Social risk. <0.25 = accumulation zone, >0.75 = cycle peak danger
- BTC Risk Level (0-1): Ben Cowen's model. The lower this is, the more historically favorable BTC entry conditions are
- Macro Recession Risk (0-1): ITC's composite from Employment + National Income + Production. <0.10 = expansion, >0.50 = recession likely
- BTC Dominance: >60% with stables = flight to quality within crypto (risk-off signal). <45% = alt season (risk-on euphoria)
- Market Cap vs Log Regression: Deviation from fair value trendline. Major undervaluation (<-30%) suggests cycle has room to run
- S&P 500 / DXY / Gold Risk Levels: Cross-asset risk scores on same 0-1 scale
Use ITC data to CONFIRM or CHALLENGE your regime classification from the core inputs. If ITC recession risk diverges significantly from your yield curve / credit read, flag it.

ASSEMBLY PRIVATE DATA (if provided):
You may also receive Assembly sentiment and macro data. Use these for additional signal confirmation:
- Assembly Sentiment Composite (0-100): <25 = Extreme Fear, 25-45 = Fear, 45-55 = Neutral, 55-75 = Greed, >75 = Extreme Greed
- Sub-components: VIX sentiment, momentum, price strength, breadth, put/call, junk bond demand, safe haven demand
- Cross-asset rotation: equities vs bonds vs gold vs oil vs USD with 50d/200d trends
- Risk & Credit Gauges: VIX, VXN, MOVE, HYG, LQD, JNK with trend context
- Sector rotation with RS vs SPY: identifies sector leadership
- Full yield curve (1M through 30Y)
These are supplementary — your core regime classification still relies on VIX, MOVE, credit, and breadth.

PREFERRED THEMES: Based on regime, suggest 1-3 macro themes Agent 2 should focus on.

You MUST output valid JSON matching this EXACT schema — no extra fields:
{
  "agent": "macro_director",
  "timestamp": "<ISO timestamp>",
  "regime": "<RISK-ON | CAUTIOUS RISK-ON | RISK-OFF | CRISIS | DEFER>",
  "vol_regime": "<COMPRESSED | NORMAL | ELEVATED | STRESSED>",
  "posture": "<Aggressive | Offensive | Defensive | Bunker | Hold>",
  "conviction_floor": <integer 5-10>,
  "preferred_themes": ["<theme1>", "<theme2>"],
  "summary": "<2-3 sentence plain English summary>",
  "key_signals": {
    "vix_read": "<description>",
    "move_read": "<description>",
    "dix_read": "<description>",
    "yield_curve_read": "<description>",
    "credit_read": "<description>",
    "breadth_read": "<description>"
  },
  "missing_data": ["<list any unavailable data feeds>"]
}

Do NOT output "max_positions_today", "allocation_cap_pct", or any position sizing fields. That is Agent 4's domain.

Be decisive. Pick a regime and commit."""


def run_agent1(macro_data: dict = None) -> dict:
    """Run Agent 1: Read macro data, send to Claude, return structured directive."""

    # Load macro data from pre-flight if not passed
    if macro_data is None:
        macro_path = "output/preflight_macro.json"
        if not os.path.exists(macro_path):
            return {"success": False, "error": "No pre-flight macro data found. Run preflight.py first."}
        with open(macro_path, "r") as f:
            macro_data = json.load(f)

    # Format for prompt
    from preflight import format_macro_for_prompt, format_assembly_for_prompt
    macro_text = format_macro_for_prompt(macro_data)

    # Load Assembly data if available
    assembly_text = ""
    assembly_path = "output/assembly_data.json"
    if os.path.exists(assembly_path):
        try:
            with open(assembly_path) as f:
                assembly_data = json.load(f)
            assembly_text = "\n\n" + format_assembly_for_prompt(assembly_data)
            print("[Agent 1] Assembly Private data loaded")
        except Exception as e:
            print(f"[Agent 1] Assembly data load failed: {e}")

    # Load FedWatch (rate expectations) data if available
    fedwatch_text = ""
    fedwatch_path = "output/fedwatch.json"
    if os.path.exists(fedwatch_path):
        try:
            from fedwatch import load_fedwatch, format_fedwatch_for_prompt
            fw_loaded = load_fedwatch(fedwatch_path)
            if fw_loaded and "error" not in fw_loaded:
                fedwatch_text = "\n\n" + format_fedwatch_for_prompt(fw_loaded)
                summary = fw_loaded.get("summary", {})
                print(f"[Agent 1] FedWatch loaded (next: {summary.get('next_meeting', '?')} — {summary.get('next_meeting_action', '?')}, year-end cuts: {summary.get('total_cuts_priced_by_year_end', '?')})")
        except Exception as e:
            print(f"[Agent 1] FedWatch load failed: {e}")

    # Load ITC (Into The Cryptoverse) data if available
    itc_text = ""
    itc_path = "output/itc_data.json"
    if os.path.exists(itc_path):
        try:
            from itc_data import load_itc_data, format_itc_for_prompt
            itc_loaded = load_itc_data(itc_path)
            if itc_loaded:
                itc_text = "\n\n" + format_itc_for_prompt(itc_loaded)
                print(f"[Agent 1] ITC data loaded (crypto risk: {itc_loaded.get('crypto_risk', {}).get('summary', '?')}, recession risk: {itc_loaded.get('macro_risk', {}).get('recession_composite', '?')})")
        except Exception as e:
            print(f"[Agent 1] ITC data load failed: {e}")

    print(f"[Agent 1] Macro data loaded from {macro_data.get('timestamp', 'unknown')}")

    user_message = f"""Here is today's macro data. Classify the regime and produce your directive.

CRITICAL: If DIX, MOVE, or Credit data is marked as unavailable, you MUST output REGIME: DEFER.

{macro_text}{assembly_text}{itc_text}{fedwatch_text}

Current date/time: {datetime.now().isoformat()}

Respond with ONLY the JSON directive, no other text."""

    # Try Claude first, fall back to Gemini for automated runs
    raw_text = None
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    google_key = os.environ.get("GOOGLE_API_KEY", "")

    if anthropic_key:
        print("[Agent 1] Sending to Claude for regime classification...")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=16000,
                temperature=0.0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_text = response.content[0].text.strip()
        except Exception as e:
            print(f"[Agent 1] Claude failed: {e}")

    if raw_text is None and google_key:
        print("[Agent 1] Falling back to Gemini 3.1 Pro Preview...")
        try:
            import requests as _requests
            gemini_model = "gemini-3.1-pro-preview"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={google_key}"
            payload = {
                "contents": [{"parts": [{"text": user_message}]}],
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 2048},
                },
            }
            resp = _requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for p in parts:
                if p.get("text"):
                    raw_text = p["text"]
            print("[Agent 1] Gemini response received")
        except Exception as e:
            print(f"[Agent 1] Gemini failed: {e}")

    if raw_text is None:
        return {
            "success": False,
            "needs_subagent": True,
            "prompt": SYSTEM_PROMPT,
            "macro_text": macro_text,
        }

    # Parse response
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

    try:
        directive = json.loads(raw_text)

        # Validate required fields
        required = ["regime", "vol_regime", "posture", "conviction_floor"]
        for field in required:
            if field not in directive:
                return {"success": False, "error": f"Missing required field: {field}", "raw": raw_text}

        # Strip any hallucinated position-sizing fields
        for bad_field in ["max_positions_today", "allocation_cap_pct", "max_positions", "allocation_cap"]:
            directive.pop(bad_field, None)

        print(f"[Agent 1] Regime: {directive.get('regime')} | Vol: {directive.get('vol_regime')} | Posture: {directive.get('posture')}")
        return {"success": True, "directive": directive, "raw_macro_data": macro_data}
    except json.JSONDecodeError as e:
        print(f"[Agent 1] ERROR: Failed to parse response as JSON: {e}")
        return {"success": False, "error": str(e), "raw_response": raw_text}


def format_directive_for_telegram(result: dict) -> str:
    """Format Agent 1 output as a readable Telegram message."""
    if not result["success"]:
        return f"⚠️ Agent 1 FAILED: {result.get('error', 'Unknown error')}"

    d = result["directive"]
    regime_emoji = {
        "RISK-ON": "🟢",
        "CAUTIOUS RISK-ON": "🟡",
        "RISK-OFF": "🟠",
        "CRISIS": "🔴",
        "DEFER": "⚪",
    }
    emoji = regime_emoji.get(d.get("regime", ""), "⚪")

    lines = [
        f"{'='*30}",
        f"📊 AGENT 1: MACRO DIRECTOR (v2)",
        f"{'='*30}",
        f"",
        f"{emoji} Regime: {d.get('regime')}",
        f"📈 Vol Regime: {d.get('vol_regime')}",
        f"📋 Posture: {d.get('posture')}",
        f"🎯 Conviction Floor: {d.get('conviction_floor')}",
        f"",
        f"🎪 Themes: {', '.join(d.get('preferred_themes', []))}",
        f"",
        f"💬 {d.get('summary', '')}",
        f"",
        f"📡 Key Signals:",
    ]

    signals = d.get("key_signals", {})
    for key, val in signals.items():
        label = key.replace("_read", "").replace("_", " ").upper()
        lines.append(f"  • {label}: {val}")

    missing = d.get("missing_data", [])
    if missing:
        lines.append(f"")
        lines.append(f"⚠️ Missing data: {', '.join(missing)}")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent1()
    print("\n" + format_directive_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent1_directive.json", "w") as f:
            json.dump(result["directive"], f, indent=2)
        print(f"\n[Agent 1] Directive saved to output/agent1_directive.json")
```

================================================================================
FILE: agent2_fundamental_screener.py
================================================================================
```python
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

# Gemini model selection
# Switch to gemini-3.0-pro with responseSchema for deterministic JSON output.
# Deep Research is kept as fallback (set AGENT2_USE_DEEP_RESEARCH=true in .env).
USE_DEEP_RESEARCH = os.environ.get("AGENT2_USE_DEEP_RESEARCH", "false").lower() == "true"

MODEL = "deep-research-preview-04-2026" if USE_DEEP_RESEARCH else "gemini-3.1-pro-preview"
MODEL_DISPLAY = "Gemini Deep Research" if USE_DEEP_RESEARCH else "Gemini 3.1 Pro"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_RETRIES = 3
RETRY_DELAY = 5
POLL_INTERVAL = 15  # seconds between status polls
MAX_POLL_TIME = 300  # 5 min max wait for deep research to complete

# Strict JSON schema for Gemini responseSchema (non-deep-research path)
OUTPUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "candidates": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "ticker": {"type": "STRING"},
                    "thesis": {"type": "STRING"},
                    "conviction_tier": {"type": "STRING", "enum": ["PASS", "STRONG", "EXCEPTIONAL"]},
                    "theme_match": {"type": "STRING"},
                    "catalyst": {"type": "STRING"},
                    "source": {"type": "STRING", "enum": ["Newsletter", "Screener Stage 2"]},
                    "screening_notes": {"type": "STRING"},
                },
                "required": ["ticker", "thesis", "conviction_tier", "theme_match", "catalyst", "source"],
            },
        },
        "screening_notes": {"type": "STRING"},
        "regime_used": {"type": "STRING"},
        "posture_used": {"type": "STRING"},
    },
    "required": ["candidates", "screening_notes", "regime_used", "posture_used"],
}

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

ANALYSIS PROTOCOL:
Step 1: Inventory the exact numerical data and fundamentals injected by Python.
Step 2: Argue the downside. Why might this setup fail? (Play Devil's Advocate).
Step 3: Brutally interrogate the fundamentals to assign a CONVICTION_TIER (PASS, STRONG, or EXCEPTIONAL).
Step 4: Ensure the THEME_MATCH is a verbatim, character-for-character echo of Agent 1's theme.
(Note: Price and market cap constraints are already enforced by Python — do not re-check.)

OUTPUT FORMAT:
Respond with ONLY the JSON object. No preamble, no scratchpad, no explanation.
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

# Old OUTPUT_SCHEMA removed — consolidated into the one at the top of the file
# which uses Gemini API format (OBJECT/STRING/ARRAY uppercase) for responseSchema


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


def call_gemini_pro(directive: dict, screener_universe: list, fundamental_data: dict, held_tickers: list = None) -> dict:
    """
    Send directive + screener + fundamentals to Gemini 3.0 Pro.
    Uses synchronous generateContent with responseSchema for deterministic JSON.
    No deep research, no browsing — pure prompt-in, structured-JSON-out.
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("No GOOGLE_API_KEY — set in .env to use Gemini.")

    prompt = _build_research_prompt(directive, screener_universe, fundamental_data, held_tickers)

    url = f"{GEMINI_API_BASE}/models/{MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": OUTPUT_SCHEMA,
        },
    }

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 2] Calling {MODEL_DISPLAY} (attempt {attempt + 1}/{MAX_RETRIES})...")
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()

            # Extract text from response
            candidates_resp = data.get("candidates", [])
            if not candidates_resp:
                raise RuntimeError(f"Gemini returned no candidates: {data}")

            text = candidates_resp[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text:
                raise RuntimeError("Gemini returned empty text")

            parsed = json.loads(text)

            # Validate conviction_tier enums (should be enforced by schema, but belt-and-suspenders)
            for c in parsed.get("candidates", []):
                tier = c.get("conviction_tier")
                if tier not in ("PASS", "STRONG", "EXCEPTIONAL"):
                    c["conviction_tier"] = "PASS"
                source = c.get("source")
                if source not in ("Newsletter", "Screener Stage 2"):
                    c["source"] = "Screener Stage 2"

            print(f"  [Agent 2] Success with {MODEL_DISPLAY} — {len(parsed.get('candidates', []))} candidates")
            return parsed

        except Exception as e:
            last_error = e
            print(f"  [Agent 2] Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    raise RuntimeError(f"{MODEL_DISPLAY} failed after {MAX_RETRIES} attempts: {last_error}")


def call_deep_research(directive: dict, screener_universe: list, fundamental_data: dict, held_tickers: list = None) -> dict:
    """
    Send directive + screener + fundamentals to Gemini Deep Research Max.
    Uses the Interactions API (async). LEGACY — kept for fallback.
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
            # Safety net: if Gemini ignores the prompt and outputs conviction_score
            # instead of conviction_tier, convert it. This should not be needed
            # now that the schema/prompt contradiction is fixed.
            for c in parsed.get("candidates", []):
                tier = c.get("conviction_tier")
                if tier not in ("PASS", "STRONG", "EXCEPTIONAL"):
                    score = c.get("conviction_score")
                    if isinstance(score, (int, float)):
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

    # Fetch current broker positions to avoid portfolio blindness
    try:
        from broker_factory import get_broker
        broker = get_broker()
        current_positions = broker.get_positions()
        held_tickers = [p["ticker"] for p in current_positions]
    except Exception:
        held_tickers = []

    if held_tickers:
        print(f"[Agent 2] Current portfolio: {held_tickers}")
    else:
        print(f"[Agent 2] No current positions (or broker unavailable)")

    # Hard Python Pre-Screen: Sort by 20-day momentum and keep only the top 10.
    # This prevents LLM "lost in the middle" attention failure and reduces token costs.
    valid_universe = []
    for s in screener_universe:
        ticker = s["ticker"]
        if ticker in fundamental_data and "error" not in fundamental_data[ticker]:
            s["_momentum"] = fundamental_data[ticker].get("change_20d_pct", 0)
            valid_universe.append(s)

    valid_universe.sort(key=lambda x: x.get("_momentum", 0), reverse=True)
    screener_universe = valid_universe[:10]
    print(f"[Agent 2] Python pre-screen: top {len(screener_universe)} momentum candidates (from {len(valid_universe)} valid)")

    # Call model with trimmed universe
    print(f"[Agent 2] Calling {MODEL_DISPLAY} with {len(screener_universe)} tickers + fundamentals...")
    try:
        if USE_DEEP_RESEARCH:
            model_result = call_deep_research(directive, screener_universe, fundamental_data, held_tickers=held_tickers)
        else:
            model_result = call_gemini_pro(directive, screener_universe, fundamental_data, held_tickers=held_tickers)
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
```

================================================================================
FILE: agent3_synthesizer.py
================================================================================
```python
"""
Agent 3: Qualitative Synthesizer — v3.0
Model: Claude Opus 4.8 (Anthropic) with adaptive thinking
Role: Merges the former Agent 2.5 (deep research / red team) and Agent 3
      (smart money verifier) into a single qualitative synthesis pass.

Gathers ALL qualitative data in Python:
  - News headlines (yfinance)
  - Options flow / Put-Call ratio (yfinance)
  - Short interest (yfinance)
  - X/Twitter smart money mentions (from output/smart_money_mentions.json)

Then sends the complete "mosaic" to Claude for a unified verdict per ticker.

Verdicts:
  PASS_THROUGH      — Qualitative data is neutral/silent; trade proceeds as-is.
  CONFIRM_ENHANCED  — Multiple bullish qualitative signals reinforce the thesis.
  VETO_DIVERGENT    — Smart money diverges from the bullish thesis.
  VETO_CROWDED      — Too many accounts are bullish (contrarian crowding signal).
  VETO_QUALITATIVE  — Fatal qualitative flaw (e.g., 30% SI + bearish smart money).
"""
import json
import os
import re
from datetime import datetime, timedelta

import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Opus for synthesis — nuanced judgment on qualitative signals
MODEL = "claude-opus-4-8"
MAX_RETRIES = 3
RETRY_DELAY = 5

# Curated smart money accounts (carried from former Agent 3)
# FIX (2026-07-06): single source of truth. This list previously hardcoded 15
# accounts that DISAGREED with what x_fetch actually fetches (31 accounts) — it
# still listed retail accounts purged per Jamie's May directive (jimcramer,
# unusual_whales, OptionsHawk, WallStJesus) and OMITTED the hedge-fund principals
# (boazweinstein, RayDalio, ...) that Agent 3's own VETO_DIVERGENT rule cites.
# Opus was told it monitored accounts it never sees. Import the real fetched list.
try:
    from x_fetch import CURATED_ACCOUNTS
except Exception:
    # Fail-safe fallback if x_fetch import breaks; keep the veto principals present.
    CURATED_ACCOUNTS = [
        "DeItaone", "Fxhedgers", "zaborsky", "GurufocusData", "PeterSchiff",
        "TruthGundlach", "elerianm", "SqueezeMetrics", "sentimentrader",
        "DarkPoolChart", "VolSignals", "boazweinstein", "CliffordAsness",
        "DylanLeClair_", "cngarabedian", "RayDalio",
    ]

SYSTEM_PROMPT = """You are Agent 3: The Qualitative Synthesizer for a $100,000 speculative spot-only trading account.

YOUR JOB: Agent 2 has passed you 1-3 surviving candidates based on a rigid quantitative screen. You receive a complete QUALITATIVE MOSAIC assembled by Python — recent news headlines, options flow (put/call ratio), short interest, AND curated smart money X/Twitter mentions (7-day lookback, institutional-grade accounts). You must weigh this entire mosaic and produce a unified verdict per ticker.

CRITICAL RULES:
1. You may NOT look up or fetch external data. Rely ONLY on the QUALITATIVE_MOSAIC injected into this prompt.
2. For each candidate, assign exactly ONE verdict:

   - PASS_THROUGH: Default. Qualitative data is neutral, silent, or mildly mixed. Trade proceeds using Agent 2's conviction tier unchanged. No numeric score.

   - CONFIRM_ENHANCED: 2+ sector specialists or hedge fund principals are publicly aligned with the thesis on X/Twitter, AND zero curated accounts are bearish, AND options flow / news reinforce the bullish setup. Effect: conviction_adjustment = UNCHANGED, Agent 4B applies a CONFIRM_BONUS in sizing.

   - VETO_DIVERGENT: 3+ curated accounts are bearish on the ticker, OR at least 1 hedge fund principal (boazweinstein, CliffordAsness, DylanLeClair_, cngarabedian, RayDalio) is bearish, OR news headlines reveal a fatal narrative break (regulatory action, terrible earnings reaction). Effect: REJECT the trade.

   - VETO_CROWDED: 8+ curated accounts are bullish on the same ticker within the last 48 hours, OR options flow shows extreme call skew (P/C ratio < 0.3) suggesting the trade is too consensus. Effect: REJECT the trade (contrarian signal).

   - VETO_QUALITATIVE: The qualitative mosaic reveals a fatal combined flaw — for example, short interest > 25% of float WITH bearish smart money AND negative news sentiment. This is the "everything is wrong" veto. Effect: REJECT the trade.

3. conviction_adjustment: For non-veto verdicts, output either UNCHANGED or DOWNGRADE. You may NEVER upgrade a conviction tier. DOWNGRADE moves EXCEPTIONAL → STRONG or STRONG → PASS.

4. SHORT SQUEEZE RULE (CRITICAL): High short interest COMBINED with bullish smart money flow is a potential short squeeze setup — do NOT veto solely on high short interest if institutional flow confirms the bullish thesis. Only apply VETO_QUALITATIVE when high short interest is COMBINED with bearish smart money AND negative news.

5. Generate a "red_flag_warnings" array for every candidate — even clean setups have risks. Identify the biggest risk factor.

6. Cite specific X/Twitter accounts and/or news headlines that drove your verdict.

7. Synthesize a "qualitative_thesis" per ticker: 2-3 sentences merging Agent 2's quantitative thesis with the qualitative mosaic realities.

<synthesis_protocol>
MANDATORY — execute before generating JSON:
Step 1: Inventory the full mosaic (news, options flow, short interest, smart money tweets).
Step 2: Cross-reference: Does smart money sentiment align with the quantitative thesis?
Step 3: Check for crowding: Are too many accounts piling in? Is options flow too one-sided?
Step 4: Check for divergence: Are bearish voices credible? Is the news narrative breaking?
Step 5: Evaluate short squeeze potential: High SI + bullish flow = squeeze setup, not veto.
Step 6: Assign verdict and conviction_adjustment.
Step 7: Write the qualitative_thesis and red_flag_warnings.
</synthesis_protocol>

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "agent": "qualitative_synthesizer",
  "timestamp": "<ISO timestamp>",
  "evaluations": [
    {
      "ticker": "<SYMBOL>",
      "verdict": "<PASS_THROUGH | CONFIRM_ENHANCED | VETO_DIVERGENT | VETO_CROWDED | VETO_QUALITATIVE>",
      "conviction_adjustment": "<UNCHANGED | DOWNGRADE>",
      "updated_conviction_tier": "<PASS | STRONG | EXCEPTIONAL>",
      "red_flag_warnings": ["<specific risk 1>", "<specific risk 2>"],
      "qualitative_thesis": "<2-3 sentences merging quant thesis with qualitative mosaic>",
      "cited_accounts": ["<accounts that drove verdict>"],
      "short_interest_pct": "<X%>",
      "put_call_ratio": <float>,
      "x_bullish_count": <int: # of curated accounts bullish on this ticker in the mosaic>,
      "x_bearish_count": <int: # of curated accounts bearish on this ticker in the mosaic>,
      "hf_principal_signal": "<BULLISH | BEARISH | NONE: net stance of any named hedge-fund principal>"
    }
  ],
  "synthesis_notes": "<overall summary of qualitative synthesis>"
}"""


def prefetch_qualitative_context(candidates: list) -> dict:
    """
    Pre-fetch ALL qualitative data for candidates concurrently:
      - News headlines (yfinance)
      - Options flow / Put-Call ratio (yfinance)
      - Short interest (yfinance)
    Returns a dict keyed by ticker.
    """
    import concurrent.futures

    context = {}
    print(f"  [Agent 3] Pre-fetching qualitative context concurrently for {len(candidates)} candidates...")

    def fetch_single(ticker):
        try:
            # 1. News Headlines — via DataProvider (Massive → yfinance fallback)
            from data_provider import get_provider
            dp = get_provider()
            news_articles = dp.get_news(ticker, limit=5)
            if news_articles:
                headlines = [
                    f"- {n.get('published', '')}: {n.get('title', '')} [{n.get('publisher', '')}]"
                    for n in news_articles
                ]
            else:
                headlines = ["- No recent news available"]

            # Options OI and Short Interest stay on yfinance (Massive paywalled / unavailable)
            stock = yf.Ticker(ticker)

            # 2. Options Flow (Put/Call OI Ratio for nearest expiration)
            options_context = "No options data available"
            pc_ratio, puts_oi, calls_oi = None, 0, 0
            try:
                expirations = stock.options
                if expirations:
                    target_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                    valid_exps = [e for e in expirations if e >= target_date]
                    nearest_exp = valid_exps[0] if valid_exps else expirations[-1]
                    chain = stock.option_chain(nearest_exp)
                    puts_oi = int(chain.puts["openInterest"].fillna(0).sum()) if not chain.puts.empty else 0
                    calls_oi = int(chain.calls["openInterest"].fillna(0).sum()) if not chain.calls.empty else 0
                    pc_ratio = round(puts_oi / calls_oi, 2) if calls_oi > 0 else 0
                    options_context = f"Nearest Expiration ({nearest_exp}): Put OI = {puts_oi}, Call OI = {calls_oi}, P/C Ratio = {pc_ratio}"
            except Exception:
                pass

            # 3. Short Interest
            short_pct_raw = stock.info.get("shortPercentOfFloat")
            short_pct = f"{round(short_pct_raw * 100, 2)}%" if short_pct_raw else "N/A"

            return ticker, {
                "recent_headlines": headlines,
                "options_flow": options_context,
                "put_call_ratio": pc_ratio,
                "puts_oi": puts_oi,
                "calls_oi": calls_oi,
                "short_interest_pct_of_float": short_pct,
                "short_interest_raw": short_pct_raw,
            }
        except Exception as e:
            return ticker, {"error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {
            executor.submit(fetch_single, c["ticker"]): c["ticker"] for c in candidates
        }
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker, data = future.result()
            context[ticker] = data

    return context


def _load_x_mentions(tickers: list) -> dict:
    """
    Load X/Twitter smart money mentions from the pre-fetched file.
    Returns a dict keyed by ticker with mention lists.
    """
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            data = json.load(f)
        raw = data.get("mentions", data)  # x_fetch.py nests under "mentions"
        # Filter to our tickers
        result = {}
        for ticker in tickers:
            result[ticker] = raw.get(ticker, raw.get(ticker.lower(), []))
        return result

    # X data not available — return empty mentions, Agent 3 will work with news/options/SI
    print("  [Agent 3] No X/Twitter data found — proceeding with news/options/SI only.")
    return {t: [] for t in tickers}


def call_synthesis(candidates: list, qual_context: dict, x_mentions: dict) -> dict:
    """
    Send the complete qualitative mosaic to Claude Opus 4.8 for unified synthesis.
    Uses adaptive thinking (extended thinking with budget_tokens).
    """
    import time

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    google_key = os.environ.get("GOOGLE_API_KEY", "")

    if not anthropic_key and not google_key:
        raise RuntimeError("No ANTHROPIC_API_KEY or GOOGLE_API_KEY — cannot run Agent 3.")

    client = None
    if anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)

    # Build the mosaic payload for each candidate
    mosaic_lines = []
    for c in candidates:
        ticker = c["ticker"]
        qc = qual_context.get(ticker, {})
        mentions = x_mentions.get(ticker, [])

        # Token diet: plaintext instead of raw JSON, top 10 by engagement
        if mentions and isinstance(mentions, list):
            def _engagement(m):
                metrics = m.get("metrics", {})
                return metrics.get("like_count", 0) + metrics.get("retweet_count", 0)
            try:
                mentions.sort(key=_engagement, reverse=True)
            except Exception:
                pass
            top_mentions = mentions[:10]
            mention_text = "\n".join(
                f"    @{m.get('username', 'UNK')}: {m.get('text', '')}"
                for m in top_mentions
            )
            mention_count = len(mentions)  # Original count
        else:
            mention_count = 0
            mention_text = "    No mentions from curated accounts"

        # DOUBLE-BLIND: Do NOT show Agent 2's thesis, conviction tier, or theme
        # to Agent 3. This prevents sycophantic agreement with upstream analysis.
        # Agent 3 should form its own independent qualitative assessment.
        line = (
            f"TICKER: {ticker}\n"
            f"  --- QUALITATIVE MOSAIC ---\n"
            f"  Short Interest: {qc.get('short_interest_pct_of_float', 'N/A')}\n"
            f"  Options Flow: {qc.get('options_flow', 'N/A')}\n"
            f"  Recent Headlines:\n" + "\n".join([f"    {h}" for h in qc.get("recent_headlines", [])]) + "\n"
            f"  Smart Money X/Twitter ({mention_count} mentions from curated accounts):\n"
            f"    {mention_text}\n"
        )
        mosaic_lines.append(line)

    user_message = f"""Synthesize the qualitative mosaic for these candidates from Agent 2.

ALL data has been pre-fetched by Python. Do NOT look up external data.

CANDIDATES & QUALITATIVE MOSAIC:
{"=" * 60}
{"".join(mosaic_lines)}
{"=" * 60}

CURATED SMART MONEY ACCOUNTS MONITORED:
{json.dumps(CURATED_ACCOUNTS)}

Current date/time: {datetime.now().isoformat()}

Perform your synthesis and respond with ONLY the JSON output."""

    last_error = None
    raw_text = None

    # Try Claude first
    if client:
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  [Agent 3] Calling {MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=16000,
                    temperature=1,
                    thinking={"type": "adaptive"},
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )
                raw_text = next(b.text for b in response.content if b.type == "text").strip()
                break
            except Exception as e:
                last_error = e
                print(f"  [Agent 3] Claude error: {e}. Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

    # Fall back to Gemini if Claude unavailable or failed
    if raw_text is None and google_key:
        print("  [Agent 3] Falling back to Gemini 3.1 Pro Preview...")
        try:
            import requests as _requests
            gemini_model = "gemini-3.1-pro-preview"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={google_key}"
            payload = {
                "contents": [{"parts": [{"text": user_message}]}],
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 4096},
                },
            }
            resp = _requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for p in parts:
                if p.get("text"):
                    raw_text = p["text"]
            print("  [Agent 3] Gemini response received")
        except Exception as e:
            last_error = e
            print(f"  [Agent 3] Gemini failed: {e}")

    if raw_text is None:
        raise Exception(f"All models failed after retries. Last error: {last_error}")

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

    result = json.loads(json_str)
    return result




def run_agent3(agent2_result: dict = None, x_mentions: dict = None) -> dict:
    """
    Run Agent 3: Qualitative Synthesizer.
    Merges news, options flow, short interest, and smart money X/Twitter into
    a single qualitative pass with Claude.

    Args:
        agent2_result: Output from Agent 2 (or Agent 2 → 2.5 filtered).
        x_mentions: Pre-fetched X/Twitter mentions dict keyed by ticker.
                    If None, loads from output/smart_money_mentions.json.

    Returns:
        Dict with evaluations per ticker (verdicts, conviction adjustments, etc.).
    """
    # Load Agent 2 candidates
    if agent2_result is None:
        path = "output/agent2_candidates.json"
        if not os.path.exists(path):
            return {"success": False, "error": "No Agent 2 candidates found."}
        with open(path) as f:
            agent2_result = json.load(f)

    candidates = agent2_result.get("candidates", [])
    if not candidates:
        return {
            "success": True,
            "evaluations": [],
            "verifications": [],
            "note": "No candidates to synthesize.",
        }

    tickers = [c.get("ticker") for c in candidates]
    print(f"[Agent 3] Qualitative synthesis for {len(tickers)} tickers: {tickers}")

    # 1. Pre-fetch qualitative context (news, options, short interest)
    qual_context = prefetch_qualitative_context(candidates)

    # 2. Load X/Twitter mentions
    if x_mentions is None:
        try:
            x_mentions = _load_x_mentions(tickers)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}
    else:
        # Filter to our tickers if a raw dict was passed
        filtered = {}
        for ticker in tickers:
            filtered[ticker] = x_mentions.get(ticker, x_mentions.get(ticker.lower(), []))
        x_mentions = filtered

    for t in tickers:
        mentions = x_mentions.get(t, [])
        count = len(mentions) if isinstance(mentions, list) else 0
        qc = qual_context.get(t, {})
        si = qc.get("short_interest_pct_of_float", "N/A")
        pcr = qc.get("put_call_ratio", "N/A")
        print(f"  [Agent 3] {t}: {count} X mentions | SI: {si} | P/C: {pcr}")

    # 3. Call Claude for synthesis
    try:
        synthesis_result = call_synthesis(candidates, qual_context, x_mentions)
    except RuntimeError:
        # No API key — return data for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "prompt": SYSTEM_PROMPT,
            "candidates": candidates,
            "qual_context": qual_context,
            "x_mentions": x_mentions,
        }
    except Exception as e:
        return {"success": False, "error": f"Claude API error: {e}"}

    # 4. Process evaluations — filter vetoes, update conviction tiers
    evaluations = synthesis_result.get("evaluations", [])
    eval_lookup = {ev["ticker"]: ev for ev in evaluations}

    surviving_candidates = []
    verifications = []  # Backward-compatible with Agent 4's expected input

    for c in candidates:
        ticker = c["ticker"]
        ev = eval_lookup.get(ticker)

        if not ev:
            # No evaluation — pass through unchanged
            surviving_candidates.append(c)
            verifications.append({
                "ticker": ticker,
                "verdict": "PASS_THROUGH",
                "sentiment_read": "Not evaluated",
                "cited_accounts": [],
            })
            continue

        verdict = ev.get("verdict", "PASS_THROUGH")

        # Build backward-compatible verification record for Agent 4
        verification = {
            "ticker": ticker,
            "verdict": verdict,
            "sentiment_read": ev.get("qualitative_thesis", ""),
            "cited_accounts": ev.get("cited_accounts", []),
            # FIX (2026-07-06): emit the smart-money counts so trade_journal can
            # finally measure whether the X/Twitter veto carries alpha. These were
            # journal FIELDS that Agent 3 never populated -> empty strings forever.
            "x_bullish_count": ev.get("x_bullish_count", ""),
            "x_bearish_count": ev.get("x_bearish_count", ""),
            "hf_principal_signal": ev.get("hf_principal_signal", ""),
        }
        verifications.append(verification)

        # Handle vetoes
        if verdict in ("VETO_DIVERGENT", "VETO_CROWDED", "VETO_QUALITATIVE"):
            print(f"  [Agent 3] 🚫 {verdict}: {ticker}")
            continue

        # Apply conviction adjustment
        adjustment = ev.get("conviction_adjustment", "UNCHANGED")
        if adjustment == "DOWNGRADE":
            tier = c.get("conviction_tier", "PASS")
            downgrade_map = {"EXCEPTIONAL": "STRONG", "STRONG": "PASS", "PASS": "PASS"}
            c["conviction_tier"] = downgrade_map.get(tier, tier)
            print(f"  [Agent 3] ⬇️ DOWNGRADE: {ticker} {tier} → {c['conviction_tier']}")
        elif verdict == "CONFIRM_ENHANCED":
            c["confirm_enhanced"] = True
            print(f"  [Agent 3] ✅ CONFIRM_ENHANCED: {ticker}")

        # Merge qualitative data into candidate.
        # FIX (2026-07-06): preserve Agent 2's ORIGINAL quantitative thesis +
        # catalyst instead of clobbering them. The double-blind (Opus writes its
        # qualitative_thesis without seeing Agent 2's) is a good design; but
        # DESTROYING the original catalyst record is not — Agent 5's thesis-drift
        # monitor needs the original catalyst to detect when it dies. Keep both.
        c["agent2_thesis"] = c.get("thesis", "")
        c["catalyst"] = c.get("catalyst", "")
        c["qualitative_thesis"] = ev.get("qualitative_thesis", "")
        # Combined thesis Agent 5 will monitor: original catalyst + qualitative read.
        c["thesis"] = ev.get("qualitative_thesis", "") or c.get("thesis", "")
        c["red_flag_warnings"] = ev.get("red_flag_warnings", [])
        c["qualitative_verdict"] = verdict

        surviving_candidates.append(c)

    # Update agent2_result with filtered candidates
    updated_agent2_result = agent2_result.copy()
    updated_agent2_result["candidates"] = surviving_candidates

    return {
        "success": True,
        "evaluations": evaluations,
        "verifications": verifications,  # Agent 4 reads this
        "synthesis_notes": synthesis_result.get("synthesis_notes", ""),
        "candidates_passthrough": surviving_candidates,
        "updated_agent2_result": updated_agent2_result,
    }


def format_agent3_for_slack(result: dict) -> str:
    """Format Agent 3 output using Slack-friendly mrkdwn."""
    if not result.get("success"):
        return f"⚠️ *Agent 3 FAILED:* {result.get('error')}"

    evaluations = result.get("evaluations", [])
    surviving = result.get("candidates_passthrough", [])

    lines = [
        f"🧪 *AGENT 3: QUALITATIVE SYNTHESIZER*",
        f"> *Survived Synthesis:* {len(surviving)}/{len(evaluations)}",
        f"> *Model:* Claude Opus 4.8 (High Thinking)",
        f"",
    ]

    if not evaluations:
        lines.append("📋 No evaluations performed.")
        return "\n".join(lines)

    for i, ev in enumerate(evaluations, 1):
        verdict = ev.get("verdict", "PASS_THROUGH")
        emoji_map = {
            "PASS_THROUGH": "➡️",
            "CONFIRM_ENHANCED": "✅",
            "VETO_DIVERGENT": "🚫",
            "VETO_CROWDED": "🔴",
            "VETO_QUALITATIVE": "💀",
        }
        emoji = emoji_map.get(verdict, "❓")

        lines.append(f"*{i}. {ev.get('ticker')}* — {emoji} *{verdict}*")

        adj = ev.get("conviction_adjustment", "UNCHANGED")
        tier = ev.get("updated_conviction_tier", "N/A")
        lines.append(f"• *Tier:* {tier} ({adj})")

        si = ev.get("short_interest_pct", "N/A")
        pcr = ev.get("put_call_ratio", "N/A")
        lines.append(f"• *Short Interest:* {si} | *P/C Ratio:* {pcr}")

        flags = ev.get("red_flag_warnings", [])
        if flags:
            lines.append("• *Red Flags:*")
            for flag in flags:
                lines.append(f"  - {flag}")

        if verdict not in ("VETO_DIVERGENT", "VETO_CROWDED", "VETO_QUALITATIVE"):
            lines.append(f"• *Thesis:* {ev.get('qualitative_thesis', '')}")

        cited = ev.get("cited_accounts", [])
        if cited:
            lines.append(f"• *Cited:* {', '.join(cited)}")

        lines.append(f"")

    if result.get("synthesis_notes"):
        lines.append(f"📝 *Notes:* _{result.get('synthesis_notes')}_")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent3()
    print("\n" + format_agent3_for_slack(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent3_verified.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        # Also save the updated candidates with qualitative data merged in
        if result.get("updated_agent2_result"):
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(result["updated_agent2_result"], f, indent=2, default=str)
        print(f"\n[Agent 3] Results saved to output/agent3_verified.json")
```

================================================================================
FILE: agent4_risk_manager.py
================================================================================
```python
"""
Agent 4: Risk Manager — v3 (ATR-based stops, no LLM dependency)
All-Python pipeline: ATR stop calculation → position sizing → tear sheet.

Changes from v2:
- Killed Agent 4A (Claude LLM call for stop anchors)
- ATR-based stop calculation: 14-day ATR with conviction-scaled multipliers
- Correlation veto fix: min_periods=20, no double-dropna
- Formula: Target = Allocation_Cap * Conviction_Mod * Vol_Mod * Posture_Mod * Contrarian_Penalty
- Theme cap removed: capping at order-generation time is meaningless since an order
  being generated does not guarantee it fills. Concentration is handled by the
  correlation veto + heat/dry-powder budgets instead.
- Uses prior close price from 7:55 AM pre-flight (not live)
- Generates Markdown tear sheet for manual execution at 9:30 AM
"""
import json
import math
import os
from datetime import datetime

import pandas as pd
# yfinance removed — all data routed through DataProvider
from dotenv import load_dotenv

from config import (
    ACCOUNT_SIZE,
    PLANNING_FLOOR_EXPIRY,
    BASE_RISK,
    MAX_RISK_PER_TRADE,
    MIN_RISK_PER_TRADE,
    MAX_ALLOCATION_PCT,
    TIER_RISK_MULT,
    CONFIRM_RISK_MULT,
    VOL_RISK_MULT,
    POSTURE_RISK_MULT,
    DRY_POWDER_FLOOR,
    POSTURE_TABLE,
    SESSION_RISK_BUDGET,
    MAX_PORTFOLIO_HEAT_PCT,
    HEAT_WARNING_PCT,
    normalize_regime,
    normalize_vol_regime,
)
from broker_factory import get_broker

load_dotenv()


# ATR multipliers by conviction tier — higher conviction = wider stop (more room)
ATR_MULTIPLIERS = {
    "PASS": 1.2,
    "STRONG": 1.5,
    "EXCEPTIONAL": 2.0,
}

# Volatility Regime ATR Modifiers — widen stops in high-vol to survive whipsaws
# GEX-driven: negative GEX → Elevated/Stressed → wider stops, fewer shares, same dollar risk
VOL_ATR_MODIFIERS = {
    "Compressed": 0.85,   # Tighter stops in low vol (dealers long gamma, market pinned)
    "Normal": 1.0,
    "Elevated": 1.25,     # Give it room to breathe
    "Stressed": 1.5,      # Massive stops to survive negative GEX whipsaws
}


def get_moving_averages(ticker: str) -> dict:
    """Fetch prior close + moving averages for a ticker via DataProvider."""
    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        hist = dp.get_bars(ticker, lookback_days=180)  # ~6 months
        if hist.empty or len(hist) < 50:
            return {"error": f"Insufficient data for {ticker}"}

        closes = [float(c) for c in hist["Close"]]
        prior_close = closes[-1]
        ma_10 = sum(closes[-10:]) / 10
        ma_20 = sum(closes[-20:]) / 20
        ma_50 = sum(closes[-50:]) / 50

        return {
            "prior_close": round(prior_close, 2),
            "ma_10": round(ma_10, 2),
            "ma_20": round(ma_20, 2),
            "ma_50": round(ma_50, 2),
            "recent_low_20d": round(min(closes[-20:]), 2),
        }
    except DataUnavailable as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def calculate_atr_stop(ticker: str, entry_price: float, conviction_tier: str, vol_regime: str = "Normal") -> dict:
    """
    Calculate ATR-based stop loss for a ticker.
    Stop distance scales with Conviction Tier AND Volatility Regime.
    
    Wider stops in high-vol (negative GEX) environments avoid whipsaw stops
    while the dollar-VaR math upstream reduces share count to keep risk flat.
    """
    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        hist = dp.get_bars(ticker, lookback_days=30)  # ~20 trading days
        if hist.empty or len(hist) < 14:
            return {"error": f"Insufficient data for {ticker} ({len(hist)} bars)"}

        # Calculate True Range for each bar
        high = hist["High"]
        low = hist["Low"]
        prev_close = hist["Close"].shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 14-day ATR (simple moving average of true range)
        atr = true_range.tail(14).mean()

        # Dynamic stop expansion: Conviction * Volatility
        base_multiplier = ATR_MULTIPLIERS.get(conviction_tier, ATR_MULTIPLIERS["PASS"])
        vol_modifier = VOL_ATR_MODIFIERS.get(vol_regime, 1.0)
        final_multiplier = base_multiplier * vol_modifier

        stop_distance = final_multiplier * atr
        stop_price = entry_price - stop_distance
        stop_distance_pct = (stop_distance / entry_price) * 100

        return {
            "stop_price": round(stop_price, 2),
            "atr": round(atr, 4),
            "atr_multiplier": round(final_multiplier, 2),
            "stop_distance_pct": round(stop_distance_pct, 2),
            "stop_label": f"{round(final_multiplier, 2)}x ATR({round(atr, 2)})",
        }
    except Exception as e:
        return {"error": str(e)}


def correlation_veto(new_ticker: str, current_positions: list, threshold: float = 0.70) -> bool:
    """
    Check if new_ticker is >threshold correlated with any current position.
    Uses 60-day daily returns. Returns True if correlated (should veto).
    """
    if not current_positions:
        return False

    from data_provider import get_provider, DataUnavailable
    try:
        dp = get_provider()
        all_tickers = [new_ticker] + current_positions

        # Fetch bars for each ticker and build a returns DataFrame
        closes_dict = {}
        for t in all_tickers:
            try:
                bars = dp.get_bars(t, lookback_days=90)
                if bars is not None and not bars.empty:
                    closes_dict[t] = bars["Close"]
            except DataUnavailable:
                continue

        if new_ticker not in closes_dict:
            # Can't get data for the candidate — FAIL-CLOSED
            print(f"  [Agent 4B] No bar data for {new_ticker} — FAIL-CLOSED (vetoing)")
            return True

        if len(closes_dict) < 2:
            # Only one ticker (no positions to compare against) — pass
            return False

        closes = pd.DataFrame(closes_dict)
        returns = closes.pct_change().tail(60)

        for pos in current_positions:
            if pos in returns.columns:
                corr = returns[new_ticker].corr(returns[pos], min_periods=20)
                # NaN means insufficient overlap or unaligned dates — FAIL-CLOSED
                if pd.isna(corr):
                    print(f"  [Agent 4B] CORRELATION NaN for {new_ticker} vs {pos} — FAIL-CLOSED (vetoing)")
                    return True
                if corr > threshold:
                    print(f"  [Agent 4B] CORRELATION VETO: {new_ticker} vs {pos} = {corr:.2f} (>{threshold})")
                    return True
        return False  # All correlations computed and below threshold
    except DataUnavailable as e:
        print(f"  [Agent 4B] Correlation data unavailable \u2014 FAIL-CLOSED (vetoing {new_ticker}): {e}")
        return True
    except Exception as e:
        print(f"  [Agent 4B] Correlation check failed \u2014 FAIL-CLOSED (vetoing {new_ticker}): {e}")
        return True  # Fail-closed: if we can't verify, assume correlated and veto


def _get_live_stops(broker) -> dict:
    """
    Pull the live resting stop orders from the broker and return the
    tightest (highest) active stop_price per symbol.

    These are the REAL trailing stops protecting open positions. When a
    trailing stop has ratcheted above entry, this is the accurate measure
    of remaining capital at risk — far better than a wide ATR estimate.

    Returns: {symbol: stop_price_float}. Empty dict on any failure (caller
    falls back to agent4_orders / ATR estimate).
    """
    live = {}
    ACTIVE_STATES = {"confirmed", "queued", "open", "unconfirmed", "partially_filled"}
    try:
        if not hasattr(broker, "get_orders"):
            return live
        for o in (broker.get_orders() or []):
            try:
                if o.get("trigger") != "stop":
                    continue
                if o.get("side") != "sell":
                    continue
                if o.get("state") not in ACTIVE_STATES:
                    continue
                sp = o.get("stop_price")
                if sp is None:
                    continue
                sp = float(sp)
                sym = o.get("symbol")
                if not sym:
                    continue
                # Keep the tightest (highest) resting stop per symbol
                if sym not in live or sp > live[sym]:
                    live[sym] = sp
            except (TypeError, ValueError):
                continue
    except Exception as e:
        print(f"[Heat] WARN could not fetch live stops: {e}")
    return live


def calculate_portfolio_heat() -> dict:
    """
    Calculate total open risk ("heat") across all positions.

    For each position:
      - open_risk = shares * (current_price - stop_price)
      - If stop_price unknown, estimate as entry_price - (1.5 * ATR)

    Returns:
      {
        "total_heat_dollars": float,
        "heat_pct_of_equity": float,
        "positions_detail": [...]
      }
    """
    try:
        broker = get_broker()
        positions = broker.get_positions()
        account = broker.get_account_summary()
    except Exception as e:
        print(f"[Heat] ERROR connecting to broker: {e}")
        return {
            "total_heat_dollars": 0.0,
            "heat_pct_of_equity": 0.0,
            "positions_detail": [],
            "error": str(e),
        }

    equity = account.get("equity", ACCOUNT_SIZE)

    # PRIORITY 1: Live resting stop orders from the broker (real trailing stops).
    # When a trailing stop has locked in profit, this reflects true risk-to-stop
    # instead of a stale, wide ATR estimate.
    live_stops = _get_live_stops(broker)

    # PRIORITY 2: agent4 orders for known stop prices
    stop_lookup = {}
    orders_path = os.path.join("output", "agent4_orders.json")
    if os.path.exists(orders_path):
        try:
            with open(orders_path) as f:
                orders_data = json.load(f)
            for order in orders_data.get("trade_orders", []):
                if order.get("action") == "BUY" and order.get("stop_loss"):
                    stop_lookup[order["ticker"]] = order["stop_loss"]
        except (json.JSONDecodeError, Exception):
            pass

    total_heat = 0.0
    details = []

    for pos in positions:
        ticker = pos["ticker"]
        shares = pos["shares"]
        entry_price = pos["avg_entry_price"]
        current_price = pos["current_price"]

        # Priority chain: live broker stop > agent4_orders > ATR estimate > 3% fallback
        stop_price = live_stops.get(ticker)
        stop_source = "live_broker_stop"

        if stop_price is None:
            stop_price = stop_lookup.get(ticker)
            stop_source = "agent4_orders"

        if stop_price is None:
            # Estimate stop using ATR
            atr_result = calculate_atr_stop(ticker, entry_price, "PASS", "Normal")
            if "error" not in atr_result:
                stop_price = atr_result["stop_price"]
                stop_source = "estimated_atr"
            else:
                # Fallback: 3% below entry
                stop_price = entry_price * 0.97
                stop_source = "fallback_3pct"

        # Risk = current equity at stake down to the stop, with 1.5x gap slippage multiplier.
        # Using current_price (not entry_price) because that's the actual capital at risk NOW.
        # The "house money" fallacy: unrealized gains ARE real money, not free.
        open_risk = shares * max(0.0, current_price - stop_price) * 1.5

        total_heat += open_risk

        details.append({
            "ticker": ticker,
            "shares": shares,
            "entry_price": entry_price,
            "current_price": current_price,
            "stop_price": round(stop_price, 2),
            "stop_source": stop_source,
            "open_risk": round(open_risk, 2),
        })

    heat_pct = total_heat / equity if equity > 0 else 0.0

    return {
        "total_heat_dollars": round(total_heat, 2),
        "heat_pct_of_equity": round(heat_pct, 4),
        "equity": round(equity, 2),
        "positions_detail": details,
    }


def _reject_trade(ticker: str, reason: str) -> dict:
    """Build a rejection record."""
    return {"ticker": ticker, "action": "SKIP", "shares": 0, "reason": reason}


def size_position(
    entry: float,
    stop: float,
    tier: str,
    confirm_enhanced: bool,
    vol_regime: str,
    posture: str,
    account_value: float,
    session_risk_used: float,
) -> dict:
    """
    Risk-first position sizer.
    Starts from risk dollars, derives shares from stop distance,
    then floors with allocation cap. Logs the binding constraint.
    """
    if posture == "Bunker":
        return {"shares": 0, "reason": "BUNKER_POSTURE"}

    # 1. Conviction-scaled risk budget
    risk_mult = (
        TIER_RISK_MULT.get(tier, TIER_RISK_MULT["PASS"])
        * CONFIRM_RISK_MULT.get(confirm_enhanced, 1.0)
        * VOL_RISK_MULT.get(vol_regime, 1.0)
        * POSTURE_RISK_MULT.get(posture, 1.0)
    )
    risk_dollars = BASE_RISK * risk_mult
    risk_dollars = min(risk_dollars, MAX_RISK_PER_TRADE)

    if risk_dollars < MIN_RISK_PER_TRADE:
        return {"shares": 0, "reason": f"RISK_TOO_SMALL ({risk_dollars:.0f} < {MIN_RISK_PER_TRADE})"}

    # 2. Session budget check
    remaining_session_budget = SESSION_RISK_BUDGET - session_risk_used
    if risk_dollars > remaining_session_budget:
        risk_dollars = remaining_session_budget
        if risk_dollars < MIN_RISK_PER_TRADE:
            return {"shares": 0, "reason": "SESSION_BUDGET_EXHAUSTED"}

    # 3. Derive shares from risk and stop distance
    stop_distance = entry - stop
    if stop_distance <= 0:
        return {"shares": 0, "reason": "INVALID_STOP"}

    # Enforce minimum 1% stop distance floor to prevent infinite leverage on tight stops
    effective_stop_distance = max(stop_distance, entry * 0.01)
    shares_by_risk = risk_dollars / effective_stop_distance

    # 4. Allocation cap (max position value as % of account)
    max_position_value = account_value * MAX_ALLOCATION_PCT
    shares_by_alloc = max_position_value / entry

    shares_raw = min(shares_by_risk, shares_by_alloc)

    # Allow fractional shares (Robinhood supports them).
    # Round to 6 decimal places (Robinhood precision), enforce a minimum of 0.001 shares.
    shares = round(shares_raw, 6)
    if shares < 0.001:
        return {"shares": 0, "reason": "ZERO_SHARES_AFTER_CONSTRAINTS"}

    binding = "risk" if shares == shares_by_risk else "allocation"
    actual_risk = shares * effective_stop_distance

    return {
        "shares": shares,
        "position_value": round(shares * entry, 2),
        "risk_budgeted": round(risk_dollars, 2),
        "risk_actual": round(actual_risk, 2),
        "risk_multiplier": round(risk_mult, 3),
        "binding_constraint": binding,
        "stop_distance_pct": round(stop_distance / entry * 100, 2),
    }


def run_agent4b(
    stop_anchors: list,
    directive: dict,
    candidates: list,
    verifications: list = None,
    existing_exposure: float = 0.0,
    remaining_heat_budget: float = None,
    account_value: float = None,
    live_tickers: list = None,
) -> dict:
    """
    Agent 4B (Python): Risk-first position sizing + tear sheet generation.
    
    Starts from risk dollars (BASE_RISK * multiplier stack), derives shares
    from stop distance, then floors with allocation cap and dry powder check.
    Binding constraint is logged per trade.
    
    Args:
        existing_exposure: dollar value of already-open positions carried from prior sessions.
        remaining_heat_budget: max additional risk dollars allowed before portfolio heat cap is hit.
                               None means no heat constraint (backward compat).
        account_value: live account equity. If None, fetches from broker (fallback to ACCOUNT_SIZE).
    """
    regime_raw = directive.get("regime", "")
    vol_raw = directive.get("vol_regime", "")

    try:
        regime = normalize_regime(regime_raw)
        vol_regime = normalize_vol_regime(vol_raw)
    except ValueError as e:
        print(f"[Agent 4B] FATAL: {e}")
        return {
            "success": False,
            "agent": "risk_manager",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "trade_orders": [],
        }

    # DEFER short-circuit: no trades, no sizing, return clean halt
    if regime == "Defer":
        print("[Agent 4B] Regime=Defer — halting, no trades this session.")
        return {
            "success": True,
            "agent": "risk_manager",
            "timestamp": datetime.now().isoformat(),
            "trade_orders": [],
            "session_summary": {
                "total_trades": 0,
                "halted_reason": "DEFER",
                "session_risk_used": 0.0,
                "session_risk_budget": SESSION_RISK_BUDGET,
            },
            "modifiers_used": {"regime": regime, "vol_regime": vol_regime, "posture": "Hold"},
        }

    # Resolve account_value + buying_power: live broker → hardcoded fallback
    buying_power = None
    if account_value is None:
        try:
            broker_acct = get_broker().get_account_summary()
            live_equity = float(broker_acct["equity"])
            buying_power = float(broker_acct.get("buying_power", live_equity))
            # Planning floor: while the funding transfer is still settling, size
            # positions against at least ACCOUNT_SIZE ($10k target). Buying power
            # stays at the REAL available cash so execution never overdraws.
            #
            # FIX (2026-07-06): this floor is now DATE-GATED. It was permanent,
            # so after a drawdown to e.g. $7K we still sized against $10K — risk
            # rose as equity fell. On/after PLANNING_FLOOR_EXPIRY we size against
            # REAL live equity (correct fixed-fractional / anti-fragile behavior).
            from datetime import date as _date
            _floor_active = False
            try:
                _y, _m, _d = (int(x) for x in str(PLANNING_FLOOR_EXPIRY).split("-"))
                _floor_active = _date.today() < _date(_y, _m, _d)
            except Exception:
                _floor_active = False  # fail safe: no phantom floor
            if _floor_active:
                account_value = max(live_equity, float(ACCOUNT_SIZE))
                if account_value > live_equity:
                    print(f"[Agent 4B] Live equity ${live_equity:,.2f} below target — planning against ACCOUNT_SIZE=${float(ACCOUNT_SIZE):,.2f} (transfer settling, floor expires {PLANNING_FLOOR_EXPIRY})")
            else:
                account_value = live_equity
                if live_equity < float(ACCOUNT_SIZE):
                    print(f"[Agent 4B] Planning against REAL live equity ${live_equity:,.2f} (settling floor expired {PLANNING_FLOOR_EXPIRY}) — risk scales with actual account.")
            print(f"[Agent 4B] Planning equity: ${account_value:,.2f} | Real buying power: ${buying_power:,.2f}")
        except Exception as e:
            print(f"[Agent 4B] Could not fetch live equity ({e}) — falling back to ACCOUNT_SIZE=${ACCOUNT_SIZE}")
            account_value = float(ACCOUNT_SIZE)
            buying_power = float(ACCOUNT_SIZE)
    else:
        print(f"[Agent 4B] Using caller-passed equity: ${account_value:,.2f}")

    posture_info = POSTURE_TABLE[regime]  # Guaranteed to hit after normalize_regime
    posture = posture_info["posture"]

    print(f"[Agent 4B] Regime: {regime} | Vol: {vol_regime} | Posture: {posture}")
    print(f"[Agent 4B] Risk stack: BASE_RISK=${BASE_RISK} | MAX=${MAX_RISK_PER_TRADE} | MIN=${MIN_RISK_PER_TRADE}")

    trade_orders = []
    # Seed with live portfolio tickers for correlation checks against existing positions
    accepted_tickers = live_tickers.copy() if live_tickers else []
    session_risk_used = 0.0
    total_allocated = 0.0

    # Build lookups
    anchor_lookup = {a["ticker"]: a for a in stop_anchors}
    candidate_lookup = {c["ticker"]: c for c in candidates}

    # Sort: EXCEPTIONAL first, then STRONG, then PASS
    tier_priority = {"EXCEPTIONAL": 0, "STRONG": 1, "PASS": 2}
    sorted_tickers = sorted(
        anchor_lookup.keys(),
        key=lambda t: tier_priority.get(anchor_lookup[t].get("conviction_tier", "PASS"), 2),
    )

    for ticker in sorted_tickers:
        anchor = anchor_lookup[ticker]
        candidate = candidate_lookup.get(ticker, {})

        # Check if Agent 4A rejected (veto from Agent 3)
        if anchor.get("action") == "REJECTED":
            trade_orders.append({
                "ticker": ticker,
                "action": "REJECTED",
                "reason": f"Agent 3 veto: {anchor.get('veto_reason', 'unknown')}",
            })
            continue

        entry = anchor.get("prior_close", 0)
        stop = anchor.get("stop_anchor_price", 0)
        conviction_tier = anchor.get("conviction_tier", "PASS")
        confirm_enhanced = anchor.get("confirm_bonus", False)
        theme = candidate.get("theme_match", "Unknown")

        if entry <= 0 or stop <= 0:
            trade_orders.append(_reject_trade(ticker, "Invalid price data"))
            continue

        # Theme cap removed: capping by theme at order-generation time is meaningless
        # because an order being generated does not mean it fills. We let correlation
        # veto + heat/dry-powder budgets handle real concentration risk instead.

        # Correlation veto
        if correlation_veto(ticker, accepted_tickers, threshold=0.70):
            trade_orders.append(_reject_trade(ticker, "Correlation veto: >0.70 with existing position"))
            continue

        # RISK-FIRST SIZING
        sizing = size_position(
            entry=entry,
            stop=stop,
            tier=conviction_tier,
            confirm_enhanced=confirm_enhanced,
            vol_regime=vol_regime,
            posture=posture,
            account_value=account_value,
            session_risk_used=session_risk_used,
        )

        if sizing["shares"] == 0:
            trade_orders.append(_reject_trade(ticker, sizing.get("reason", "sizing returned 0")))
            continue

        shares = sizing["shares"]
        position_value = sizing["position_value"]
        risk_actual = sizing["risk_actual"]

        # Heat budget check: would this trade blow through the remaining heat cap?
        if remaining_heat_budget is not None:
            if risk_actual > remaining_heat_budget:
                trade_orders.append(_reject_trade(ticker, f"HEAT_BUDGET_EXCEEDED (trade risk ${risk_actual:.0f} > remaining ${remaining_heat_budget:.0f})"))
                continue

        # Dry powder floor: new + existing exposure cannot exceed 80%
        max_deployable = account_value * (1 - DRY_POWDER_FLOOR) - total_allocated - existing_exposure

        # Hard cap by actual broker buying power
        if buying_power is not None:
            actual_cash_available = buying_power - total_allocated
            max_deployable = min(max_deployable, actual_cash_available)

        if max_deployable <= 0:
            trade_orders.append(_reject_trade(ticker, "Insufficient cash/buying power available"))
            continue
        if position_value > max_deployable:
            shares = round(max_deployable / entry, 6)
            if shares < 0.001:
                trade_orders.append(_reject_trade(ticker, "Dry powder floor (existing + new > 80%)"))
                continue
            position_value = round(shares * entry, 2)
            risk_actual = round(shares * (entry - stop), 2)
            sizing["binding_constraint"] = "dry_powder"

        # Build order
        stop_distance = entry - stop
        order = {
            "ticker": ticker,
            "action": "BUY",
            "shares": shares,
            "entry_price": entry,
            "stop_loss": round(stop, 2),
            "stop_anchor_label": anchor.get("stop_anchor_label", ""),
            "position_value": position_value,
            "pct_of_account": round(position_value / account_value * 100, 2),
            "risk_budgeted": sizing["risk_budgeted"],
            "risk_actual": risk_actual,
            "risk_multiplier": sizing["risk_multiplier"],
            "stop_distance_pct": round(stop_distance / entry * 100, 2),
            "binding_constraint": sizing["binding_constraint"],
            "theme": theme,
            "conviction_tier": conviction_tier,
            "confirm_enhanced": confirm_enhanced,
            # FIX (2026-07-06): propagate the thesis into the order so Agent 5's
            # thesis-drift monitor has something real to evaluate. Previously the
            # order carried no thesis -> agent5 order.get("thesis","") was always
            # empty -> drift monitor ran against an empty string every day.
            "thesis": candidate.get("thesis", ""),
            "catalyst": candidate.get("catalyst", ""),
            "agent2_thesis": candidate.get("agent2_thesis", candidate.get("thesis", "")),
        }

        trade_orders.append(order)
        accepted_tickers.append(ticker)
        session_risk_used += risk_actual
        total_allocated += position_value
        if remaining_heat_budget is not None:
            remaining_heat_budget -= risk_actual

        print(f"  [Agent 4B] {ticker}: {shares} shares @ ${entry}, "
              f"risk ${risk_actual:.2f} (budgeted ${sizing['risk_budgeted']:.2f}), "
              f"alloc {round(position_value/account_value*100, 1)}%, "
              f"tier={conviction_tier}, bound={sizing['binding_constraint']}")

    result = {
        "success": True,
        "agent": "risk_manager",
        "timestamp": datetime.now().isoformat(),
        "trade_orders": trade_orders,
        "session_summary": {
            "total_trades": len([o for o in trade_orders if o.get("action") == "BUY"]),
            "session_risk_used": round(session_risk_used, 2),
            "session_risk_budget": SESSION_RISK_BUDGET,
            "total_allocated": round(total_allocated, 2),
            "existing_exposure": round(existing_exposure, 2),
            "pct_deployed": round((total_allocated + existing_exposure) / account_value * 100, 2),
            "dry_powder_pct": round((1 - (total_allocated + existing_exposure) / account_value) * 100, 2),
            "account_value": round(account_value, 2),
        },
        "modifiers_used": {
            "regime": regime,
            "vol_regime": vol_regime,
            "posture": posture,
        },
    }

    return result


def generate_tear_sheet(result: dict, directive: dict) -> str:
    """
    Generate Markdown tear sheet for manual execution at 9:30 AM.
    This is what gets sent to Telegram/Slack.

    v3 field mapping (post-sizing refactor):
      order keys: shares, entry_price, stop_loss, stop_anchor_label,
                  position_value, pct_of_account, risk_budgeted, risk_actual,
                  risk_multiplier, stop_distance_pct, binding_constraint,
                  theme, conviction_tier, confirm_enhanced
      modifiers_used keys: regime, vol_regime, posture
      session_summary keys: total_trades, session_risk_used, session_risk_budget,
                            total_allocated, existing_exposure, pct_deployed,
                            dry_powder_pct, account_value
    """
    orders = result.get("trade_orders", [])
    summary = result.get("session_summary", {})
    mods = result.get("modifiers_used", {})

    lines = [
        f"{'='*35}",
        f"📋 OPEN CLAW TEAR SHEET",
        f"📅 {datetime.now().strftime('%Y-%m-%d')} | Execute at 9:30 AM ET",
        f"{'='*35}",
        f"",
        f"🌍 Regime: {mods.get('regime', '?')} | Vol: {mods.get('vol_regime', '?')}",
        f"📋 Posture: {mods.get('posture', '?')}",
        f"💼 Account: ${summary.get('account_value', 0):,.2f}",
        f"",
    ]

    buy_orders = [o for o in orders if o.get("action") == "BUY"]
    skip_orders = [o for o in orders if o.get("action") in ("SKIP", "REJECTED")]

    if not buy_orders:
        lines.append("🚫 NO TRADES TODAY")
        if skip_orders:
            lines.append("")
            for s in skip_orders:
                lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        return "\n".join(lines)

    for i, order in enumerate(buy_orders, 1):
        lines.append(f"{'─'*30}")
        lines.append(f"TRADE #{i}: {order.get('ticker')}")
        lines.append(f"")
        lines.append(f"  Action:     BUY")
        lines.append(f"  Shares:     {order.get('shares')}")
        lines.append(f"  Entry:      ${order.get('entry_price', 0):.2f} (prior close)")
        lines.append(f"  Stop:       ${order.get('stop_loss', 0):.2f} ({order.get('stop_anchor_label', '')})")
        lines.append(f"  Stop Dist:  {order.get('stop_distance_pct', 0):.1f}%")
        lines.append(f"  Theme:      {order.get('theme', '?')}")
        lines.append(f"  Tier:       {order.get('conviction_tier', '?')} {'✨ ENHANCED' if order.get('confirm_enhanced') else ''}")
        lines.append(f"")
        lines.append(f"  💰 Position: ${order.get('position_value', 0):,.2f} ({order.get('pct_of_account', 0):.1f}% of account)")
        lines.append(f"  🎯 Risk:     ${order.get('risk_actual', 0):,.2f} (budgeted ${order.get('risk_budgeted', 0):,.2f})")
        lines.append(f"  📏 Bound:    {order.get('binding_constraint', '?')} | Risk mult: {order.get('risk_multiplier', 0):.3f}")
        lines.append(f"")

    if skip_orders:
        lines.append(f"{'─'*30}")
        lines.append(f"SKIPPED/REJECTED:")
        for s in skip_orders:
            lines.append(f"  ⏭️ {s.get('ticker')}: {s.get('reason')}")
        lines.append(f"")

    lines.append(f"{'─'*30}")
    lines.append(f"SESSION TOTALS:")
    lines.append(f"  Trades:       {summary.get('total_trades', 0)}")
    lines.append(f"  Risk Used:    ${summary.get('session_risk_used', 0):,.2f} / ${summary.get('session_risk_budget', 0):,.2f}")
    lines.append(f"  Allocated:    ${summary.get('total_allocated', 0):,.2f}")
    lines.append(f"  Deployed:     {summary.get('pct_deployed', 0):.1f}%")
    lines.append(f"  Dry Powder:   {summary.get('dry_powder_pct', 0):.1f}%")
    lines.append(f"{'='*35}")

    return "\n".join(lines)


def run_agent4(agent2_result: dict = None, agent3_result: dict = None, directive: dict = None) -> dict:
    """
    Run the full Agent 4 pipeline: ATR stops (Python) → 4B sizing (Python).
    No LLM calls — pure Python.
    """
    # Load data
    if directive is None:
        with open("output/agent1_directive.json") as f:
            directive = json.load(f)

    if agent2_result is None:
        with open("output/agent2_candidates.json") as f:
            agent2_result = json.load(f)

    if agent3_result is None:
        path = "output/agent3_verified.json"
        if os.path.exists(path):
            with open(path) as f:
                agent3_result = json.load(f)

    candidates = agent2_result.get("candidates", [])
    verifications = agent3_result.get("verifications", []) if agent3_result else []

    # Extract vol_regime for dynamic ATR stop widening
    vol_raw = directive.get("vol_regime", "Normal")
    try:
        vol_regime = normalize_vol_regime(vol_raw)
    except Exception:
        vol_regime = "Normal"
    print(f"[Agent 4] Vol regime: {vol_regime} (ATR modifier: {VOL_ATR_MODIFIERS.get(vol_regime, 1.0)}x)")

    if not candidates:
        return {
            "success": True,
            "trade_orders": [],
            "session_summary": {"total_trades": 0, "total_risk": 0},
        }

    # Build verification lookup
    verification_lookup = {v.get("ticker"): v for v in verifications}

    # Portfolio Heat Check — reject new trades if total open risk exceeds 6%
    heat = calculate_portfolio_heat()
    heat_pct = heat["heat_pct_of_equity"]
    remaining_heat_budget = None

    if heat_pct > MAX_PORTFOLIO_HEAT_PCT:
        print(f"[Agent 4] 🔥 PORTFOLIO HEAT EXCEEDED: {heat_pct*100:.1f}% > {MAX_PORTFOLIO_HEAT_PCT*100:.0f}% cap")
        print(f"[Agent 4] Total heat: ${heat['total_heat_dollars']:,.2f} on ${heat.get('equity', 0):,.2f} equity")
        return {
            "success": True,
            "trade_orders": [{"action": "SKIP", "ticker": c.get("ticker", "?"), "shares": 0,
                              "reason": f"PORTFOLIO_HEAT_EXCEEDED ({heat_pct*100:.1f}% > {MAX_PORTFOLIO_HEAT_PCT*100:.0f}%)"}
                             for c in candidates],
            "session_summary": {
                "total_trades": 0,
                "session_risk_used": 0,
                "session_risk_budget": SESSION_RISK_BUDGET,
                "portfolio_heat": heat,
            },
        }
    elif heat_pct > HEAT_WARNING_PCT:
        print(f"[Agent 4] ⚠️ Portfolio heat warning: {heat_pct*100:.1f}% (threshold: {HEAT_WARNING_PCT*100:.0f}%)")
        print(f"[Agent 4] Total heat: ${heat['total_heat_dollars']:,.2f} — trades allowed but budget constrained")

    # Compute remaining heat budget in dollars
    max_heat_dollars = heat.get("equity", ACCOUNT_SIZE) * MAX_PORTFOLIO_HEAT_PCT
    remaining_heat_budget = max_heat_dollars - heat["total_heat_dollars"]
    print(f"[Agent 4] Heat budget: ${remaining_heat_budget:,.2f} remaining of ${max_heat_dollars:,.2f}")

    # Build stop anchors from ATR calculations (replaces Agent 4A Claude call)
    stop_anchors = []
    print("[Agent 4] Calculating ATR-based stops (no LLM)...")

    for candidate in candidates:
        ticker = candidate.get("ticker")
        conviction_tier = candidate.get("conviction_tier", "PASS")

        # Apply Agent 3 verdict
        v = verification_lookup.get(ticker, {})
        verdict = v.get("verdict", "PASS_THROUGH")
        confirm_bonus = False

        if verdict in ("VETO_DIVERGENT", "VETO_CROWDED"):
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": verdict,
                "prior_close": 0,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": False,
            })
            print(f"  [Agent 4] {ticker}: REJECTED by Agent 3 ({verdict})")
            continue

        if verdict == "CONFIRM_ENHANCED":
            confirm_bonus = True

        # Get prior close from moving averages
        ma_data = get_moving_averages(ticker)
        if "error" in ma_data:
            print(f"  [Agent 4] {ticker}: Skipping — {ma_data['error']}")
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": f"Data error: {ma_data['error']}",
                "prior_close": 0,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": False,
            })
            continue

        entry_price = ma_data["prior_close"]

        # Calculate ATR-based stop with vol regime modifier
        atr_result = calculate_atr_stop(ticker, entry_price, conviction_tier, vol_regime)
        if "error" in atr_result:
            print(f"  [Agent 4] {ticker}: ATR failed — {atr_result['error']}")
            stop_anchors.append({
                "ticker": ticker,
                "action": "REJECTED",
                "veto_reason": f"ATR error: {atr_result['error']}",
                "prior_close": entry_price,
                "stop_anchor_price": None,
                "stop_anchor_label": None,
                "stop_distance_pct": 0,
                "conviction_tier": conviction_tier,
                "confirm_bonus": confirm_bonus,
            })
            continue

        stop_anchors.append({
            "ticker": ticker,
            "action": "PROCEED",
            "veto_reason": None,
            "prior_close": entry_price,
            "stop_anchor_price": atr_result["stop_price"],
            "stop_anchor_label": atr_result["stop_label"],
            "stop_distance_pct": atr_result["stop_distance_pct"],
            "conviction_tier": conviction_tier,
            "confirm_bonus": confirm_bonus,
        })
        print(f"  [Agent 4] {ticker}: Stop ${atr_result['stop_price']} "
              f"({atr_result['stop_label']}, -{atr_result['stop_distance_pct']:.1f}%)")

    # Fetch existing exposure + live tickers for correlation checks
    live_tickers = []
    try:
        broker = get_broker()
        open_positions = broker.get_positions()
        existing_exposure = sum(float(p.get("market_value", 0)) for p in open_positions)
        live_tickers = [p["ticker"] for p in open_positions]
        print(f"[Agent 4] Existing exposure: ${existing_exposure:,.2f} ({len(live_tickers)} positions: {live_tickers})")
    except Exception as e:
        print(f"[Agent 4] Could not fetch exposure: {e} — assuming $0")
        existing_exposure = 0.0

    # Step 4B: Python multiplicative sizing
    print("[Agent 4B] Running position sizing math...")
    result_4b = run_agent4b(stop_anchors, directive, candidates, verifications,
                            existing_exposure=existing_exposure,
                            remaining_heat_budget=remaining_heat_budget,
                            live_tickers=live_tickers)

    # Generate tear sheet
    tear_sheet = generate_tear_sheet(result_4b, directive)
    result_4b["tear_sheet"] = tear_sheet

    return result_4b


if __name__ == "__main__":
    result = run_agent4()

    if result.get("tear_sheet"):
        print("\n" + result["tear_sheet"])
    else:
        print(json.dumps(result, indent=2))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent4_orders.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 4] Orders saved to output/agent4_orders.json")
```

================================================================================
FILE: agent5_position_monitor.py
================================================================================
```python
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
                            # 2026-07-06: carry the original catalyst so the drift
                            # monitor can detect a DEAD catalyst, not just a soft read.
                            "catalyst": order.get("catalyst", ""),
                            "agent2_thesis": order.get("agent2_thesis", ""),
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
                    "catalyst": enrichment.get("catalyst", ""),
                    "agent2_thesis": enrichment.get("agent2_thesis", ""),
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
```

================================================================================
FILE: assembly_scraper.py
================================================================================
```python
"""
Assembly Private Scraper — Browser-based extraction.

Assembly is a Next.js SPA that renders data client-side.
This scraper uses the browser DOM snapshots (from OCPlatform BrowserControl)
or falls back to a pre-saved JSON file.

For automated pipeline runs, the orchestrator calls scrape via browser,
saves to output/assembly_data.json, and agents read from that file.

Usage:
  python assembly_scraper.py parse-snapshot <snapshot_file>
  python assembly_scraper.py load  (reads from output/assembly_data.json)
"""

import json
import re
import os
from datetime import datetime


def parse_sentiment_from_text(text: str) -> dict:
    """Parse sentiment data from page text content."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_sentiment"}

    # Composite score
    composite_match = re.search(r"(\d+)\s+(Greed|Fear|Neutral|Extreme\s*Greed|Extreme\s*Fear|Ex\.\s*Greed|Ex\.\s*Fear)", text)
    if composite_match:
        result["composite_score"] = int(composite_match.group(1))
        result["composite_label"] = composite_match.group(2)

    # Historical values
    for label, key in [
        ("Prev Close", "prev_close"),
        ("Previous Close", "prev_close"),
        ("1 Week Ago", "one_week_ago"),
        ("1W Ago", "one_week_ago"),
        ("1 Month Ago", "one_month_ago"),
        ("1M Ago", "one_month_ago"),
        ("1 Year Ago", "one_year_ago"),
        ("1Y Ago", "one_year_ago"),
        ("30-Day Avg", "thirty_day_avg"),
        ("52-Week High", "fifty_two_week_high"),
        ("52-Week Low", "fifty_two_week_low"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+(\d+)", text)
        if match and key not in result:
            result[key] = int(match.group(1))

    # Sub-components
    components = {}
    patterns = [
        (r"Market Volatility\s*\(VIX\)\s*(\d+)", "market_volatility_vix"),
        (r"S&P 125-day Momentum\s*(\d+)", "sp500_momentum_125d"),
        (r"S&P 500 Momentum\s*(\d+)", "sp500_momentum"),
        (r"Stock Price Strength\s*(\d+)", "stock_price_strength"),
        (r"Stock Price Breadth\s*(\d+)", "stock_price_breadth"),
        (r"Put\s*/\s*Call Options\s*(\d+)", "put_call_options"),
        (r"Junk Bond Demand\s*(\d+)", "junk_bond_demand"),
        (r"Safe Haven Demand\s*(\d+)", "safe_haven_demand"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, text)
        if match:
            components[key] = int(match.group(1))

    # VIX actual value
    vix_match = re.search(r"VIX\)\s*\d+\s+(\d+\.?\d*)", text)
    if vix_match:
        components["vix_value"] = float(vix_match.group(1))

    result["components"] = components

    # Sector breadth
    sectors = {}
    sector_pattern = re.findall(
        r"(Energy|Healthcare|Utilities|Real Estate|Consumer Defensive|Technology|"
        r"Communication Services|Consumer Cyclical|Industrials|Financial Services|"
        r"Basic Materials)\s+([+\-]?\d+\.?\d*%)",
        text
    )
    for sector, change in sector_pattern:
        sectors[sector] = change
    result["sector_breadth"] = sectors

    return result


def parse_macro_from_snapshot(snapshot_text: str) -> dict:
    """Parse macro data from a browser snapshot."""
    result = {"timestamp": datetime.utcnow().isoformat(), "source": "assembly_macro"}

    # Yield curve
    yield_curve = {}
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]:
        match = re.search(rf"\b{tenor}\s+(\d+\.?\d*)", snapshot_text)
        if match:
            yield_curve[tenor] = float(match.group(1))
    result["yield_curve"] = yield_curve

    # Key macro
    for label, key in [
        ("Fed Funds", "fed_funds"),
        ("Unemployment", "unemployment"),
    ]:
        match = re.search(rf"{re.escape(label)}\s+([\d.]+%?)", snapshot_text)
        if match:
            result[key] = match.group(1)

    # Cross-asset rotation — parse from structured snapshot
    cross_asset = []
    # Pattern: "SPY US Large Cap Equity $733.73 -0.67% +6.1% +8.4% 91%"
    asset_pattern = re.findall(
        r'([A-Z]{2,5})\s+([\w\s]+?)\s+(Equity|Bond|Commodity|FX|Crypto)\s+\$([\d,.]+)\s+'
        r'([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+([+\-]?\d+\.?\d*%)\s+(\d+%)',
        snapshot_text
    )
    for ticker, name, asset_class, price, today, vs50, vs200, range52 in asset_pattern:
        cross_asset.append({
            "ticker": ticker.strip(),
            "name": name.strip(),
            "asset_class": asset_class,
            "price": f"${price}",
            "today": today,
            "vs_50d": vs50,
            "vs_200d": vs200,
            "range_52w": range52,
        })
    result["cross_asset_rotation"] = cross_asset

    return result


def format_sentiment_for_prompt(sentiment: dict) -> str:
    """Format sentiment data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY SENTIMENT DATA",
        "=" * 40,
        f"Composite Score: {sentiment.get('composite_score', '?')} ({sentiment.get('composite_label', '?')})",
        f"Prev Close: {sentiment.get('prev_close', '?')} | 1W Ago: {sentiment.get('one_week_ago', '?')} | 1M Ago: {sentiment.get('one_month_ago', '?')}",
        f"30D Avg: {sentiment.get('thirty_day_avg', '?')} | 52W High: {sentiment.get('fifty_two_week_high', '?')} | 52W Low: {sentiment.get('fifty_two_week_low', '?')}",
        "",
        "Sub-Components:",
    ]
    components = sentiment.get("components", {})
    for key, label in [
        ("market_volatility_vix", "Market Volatility (VIX)"),
        ("vix_value", "VIX Actual"),
        ("sp500_momentum_125d", "S&P 125d Momentum"),
        ("sp500_momentum", "S&P 500 Momentum"),
        ("stock_price_strength", "Stock Price Strength"),
        ("stock_price_breadth", "Stock Price Breadth"),
        ("put_call_options", "Put/Call Options"),
        ("junk_bond_demand", "Junk Bond Demand"),
        ("safe_haven_demand", "Safe Haven Demand"),
    ]:
        val = components.get(key)
        if val is not None:
            lines.append(f"  {label}: {val}")

    sectors = sentiment.get("sector_breadth", {})
    if sectors:
        lines.append("")
        lines.append("Sector Breadth:")
        for sector, change in sectors.items():
            lines.append(f"  {sector}: {change}")

    return "\n".join(lines)


def format_macro_for_prompt(macro: dict) -> str:
    """Format macro data for Agent 1's system prompt."""
    lines = [
        "ASSEMBLY MACRO DATA",
        "=" * 40,
    ]

    yc = macro.get("yield_curve", {})
    if yc:
        curve_str = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"Yield Curve: {curve_str}")

    for key, label in [("fed_funds", "Fed Funds"), ("unemployment", "Unemployment")]:
        if key in macro:
            lines.append(f"{label}: {macro[key]}")

    cross_asset = macro.get("cross_asset_rotation", [])
    if cross_asset:
        lines.append("")
        lines.append("Cross-Asset Rotation:")
        for a in cross_asset:
            lines.append(f"  {a['ticker']} ({a['name']}): {a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    return "\n".join(lines)


def load_assembly_data() -> dict:
    """Load pre-scraped Assembly data from output file."""
    path = "output/assembly_data.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "load":
        data = load_assembly_data()
        if "sentiment" in data:
            print(format_sentiment_for_prompt(data["sentiment"]))
            print()
        if "macro" in data:
            print(format_macro_for_prompt(data["macro"]))
    else:
        print("Usage: python assembly_scraper.py load")
        print("  (Assembly data must be scraped via browser and saved to output/assembly_data.json)")
```

================================================================================
FILE: broker_factory.py
================================================================================
```python
"""
Broker Factory — Robinhood real-money execution.

Usage:
  from broker_factory import get_broker
  broker = get_broker()             # Robinhood (default)
  broker = get_broker("robinhood")  # Robinhood (explicit)

Both brokers expose the same interface:
  - get_account_summary()
  - get_positions()
  - get_existing_exposure()
  - get_position_tickers()
  - execute_tear_sheet(orders)
  - close_position(ticker, qty=None)
  - close_all_positions()
  - execute_agent5_decisions(decisions, crisis=False)
  - get_orders_today()
"""
import os
from pathlib import Path


# Default broker — set via BROKER env var or auto-detect
DEFAULT_BROKER = os.environ.get("BROKER", "auto")

# Process-level singleton cache. The Robinhood broker does a 3-round-trip MCP
# handshake (initialize + initialized notification + account discovery) in its
# __init__, so creating a fresh instance per get_broker() call was costing
# ~12+ network round-trips per pipeline run. Caching reuses one live MCP
# session for the lifetime of the process. Key is the RESOLVED broker name.
_BROKER_CACHE = {}


def reset_broker_cache():
    """Drop cached broker instances (e.g. after a token refresh or in tests)."""
    _BROKER_CACHE.clear()


def get_broker(broker_name: str = None, *, fresh: bool = False):
    """
    Get a broker instance (cached per-process by default).

    Args:
        broker_name: "robinhood" (default) or "auto" (alias for robinhood).
        fresh: If True, bypass the cache and build a new instance (and
               replace the cached one). Use for forced reconnects.
    """
    name = (broker_name or DEFAULT_BROKER).lower().strip()

    def _build():
        if name in ("robinhood", "auto"):
            # Robinhood is the only supported broker (real-money execution).
            # 'auto' is kept as an alias for backward compatibility and resolves
            # straight to Robinhood. We fail LOUD if it can't init rather than
            # silently routing anywhere else.
            token_path = Path(__file__).parent / "robinhood-mcp" / "token.json"
            if not token_path.exists():
                raise RuntimeError(
                    "Robinhood broker selected but robinhood-mcp/token.json is "
                    "missing. Re-auth Robinhood before running the pipeline."
                )
            return _get_robinhood()
        else:
            raise ValueError(
                f"Unknown broker: {name}. Only 'robinhood' (or 'auto') is supported."
            )

    if fresh:
        broker = _build()
        _BROKER_CACHE[name] = broker
        return broker

    cached = _BROKER_CACHE.get(name)
    if cached is not None:
        return cached

    broker = _build()
    _BROKER_CACHE[name] = broker
    return broker


def _get_robinhood():
    from robinhood_broker import RobinhoodBroker
    return RobinhoodBroker()
```

================================================================================
FILE: config.py
================================================================================
```python
"""
Trading Pipeline Configuration — "Golden Path" v2
Incorporates Jamie's finalized tweaks.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Account
# Robinhood agentic account: REAL RUN — $10,000 total ($9,500 deposited 2026-05-31
# + ~$500 existing cash). Prior runs were test runs sized to a $500 sandbox.
# All risk parameters below are calibrated to the full $10K account.
ACCOUNT_SIZE = 10_000  # $10K Robinhood agentic account (real run)
DRY_POWDER_FLOOR = 0.20  # Never deploy beyond 80% ($8,000 max deployed)

# Planning-equity floor EXPIRY (2026-07-06 fix).
# The transfer-settling floor `max(live_equity, ACCOUNT_SIZE)` was PERMANENT,
# so after any drawdown we kept sizing against phantom $10K equity — risk rose
# as the account shrank (anti-fragility inversion). This date-gates the floor:
# on/after this date, sizing uses REAL live equity. $9,500 deposited 2026-05-31;
# transfers settle well within 2 weeks, so the floor is long since unnecessary.
# Set to a future date only to re-enable the floor during a fresh settling deposit.
PLANNING_FLOOR_EXPIRY = os.environ.get("PLANNING_FLOOR_EXPIRY", "2026-06-14")  # YYYY-MM-DD

# LLM Keys
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")  # For Gemini (Agent 2)

# Telegram Output
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Schedule (ET) — Golden Path timing
PREFLIGHT_TIME = "07:55"       # Python pre-flight data fetch
AGENT1_TIME = "08:00"          # Agent 1 - Macro Director
AGENT2_TIME = "08:01"          # Agent 2 - Fundamental Screener
AGENT3_TIME = "08:15"          # Agent 3 - Signal Verifier (Smart Money)
AGENT4_TIME = "08:17"          # Agent 4a/4b - Risk Manager
TEARSHEET_TIME = "08:18"       # Deliver tear sheet
AGENT5_PREFLIGHT_TIME = "15:25"  # Agent 5 pre-flight price snapshot
AGENT5_TIME = "15:30"          # Agent 5 - Position Monitor

# Risk Parameters (scaled to $10K account)
# PER_TRADE_RISK_CAP removed (2026-07-06): it was defined but NEVER enforced
# anywhere — MAX_RISK_PER_TRADE ($200, below) is the actual per-trade ceiling.
# Two conflicting "caps" was a future "why didn't the limit fire" incident.
# The single per-trade risk policy is BASE_RISK -> MAX_RISK_PER_TRADE.
SESSION_RISK_BUDGET = 1000.00  # $1,000 max session risk (10% of $10K)

# ── Profit-taking (added) ──
# NOTE: BRACKET_TP_R_MULTIPLE drives the resting take-profit leg. Robinhood (the
# live broker) does NOT support OTO/bracket orders, so on RH this is placed as a
# separate GTC limit-sell AFTER the entry fills, for the FULL filled qty. It is
# the only profit-taking that fires intraday; Agent 5's +2R/+4R scale-outs run
# once daily at 3:30. On the partial-tranche scale-out, that TP leg is cancelled
# and re-armed on the remainder.
BRACKET_TP_R_MULTIPLE = 6.0    # take-profit at entry + 6R (runner target / intraday spike)
SCALE_LADDER = [(2.0, 0.34), (4.0, 0.67)]  # (R-multiple threshold, cumulative fraction of ORIGINAL position sold by then)
MIN_SHARES_TO_SCALE = 3        # don't scale positions smaller than this (leaves a real runner)

THEME_CAP = 1                  # DEPRECATED: no longer enforced. Capping at order-generation
                               # time is meaningless since an order doesn't guarantee a fill.
                               # Concentration handled by correlation veto + heat budgets.

# Screener Rules
SCREENER_MIN_MARKET_CAP = 100_000_000  # $100M minimum
SCREENER_MIN_PRICE = 5.00              # > $5

# Position Sizing — Risk-First Model (v3)
# Sizing starts from RISK DOLLARS, derives shares from stop distance,
# then floors with allocation cap. Binding constraint is logged.

# Posture table (regime -> posture + conviction floor)
POSTURE_TABLE = {
    "Risk-On":          {"posture": "Aggressive",  "conviction_floor": 5},
    "Cautious Risk-On": {"posture": "Offensive",   "conviction_floor": 6},
    "Risk-Off":         {"posture": "Defensive",   "conviction_floor": 7},
    "Crisis":           {"posture": "Bunker",      "conviction_floor": 9},
    "Defer":            {"posture": "Hold",        "conviction_floor": 10},
}

# Agent 1 emits regimes/vols in UPPERCASE; config keys are Title-Case.
# These maps are the single source of truth for normalization.
# Add a new alias here if you ever rename a regime.
_REGIME_CANONICAL = {
    "RISK-ON": "Risk-On",
    "CAUTIOUS RISK-ON": "Cautious Risk-On",
    "RISK-OFF": "Risk-Off",
    "CRISIS": "Crisis",
    "DEFER": "Defer",
}

_VOL_CANONICAL = {
    "COMPRESSED": "Compressed",
    "NORMAL": "Normal",
    "ELEVATED": "Elevated",
    "STRESSED": "Stressed",
}


def normalize_regime(s: str) -> str:
    """Coerce any-casing regime string to canonical POSTURE_TABLE key.
    Raises ValueError on unknown input — DO NOT swallow silently."""
    if not s:
        raise ValueError("normalize_regime: empty/None regime")
    key = s.strip().upper()
    if key in _REGIME_CANONICAL:
        return _REGIME_CANONICAL[key]
    if s in POSTURE_TABLE:  # already canonical
        return s
    raise ValueError(
        f"Unknown regime: {s!r} (expected one of {list(_REGIME_CANONICAL)})"
    )


def normalize_vol_regime(s: str) -> str:
    """Coerce any-casing vol_regime to canonical VOL_RISK_MULT key.
    Raises ValueError on unknown input."""
    if not s:
        raise ValueError("normalize_vol_regime: empty/None vol_regime")
    key = s.strip().upper()
    if key in _VOL_CANONICAL:
        return _VOL_CANONICAL[key]
    if s in VOL_RISK_MULT:
        return s
    raise ValueError(
        f"Unknown vol_regime: {s!r} (expected one of {list(_VOL_CANONICAL)})"
    )

# Risk-first sizing constants (scaled to $10K account)
BASE_RISK = 150.00             # Per-trade $ at neutral conviction (1.5% of $10K)
MAX_RISK_PER_TRADE = 200.00    # Hard ceiling regardless of multiplier stack (2.0%)
MIN_RISK_PER_TRADE = 50.00     # Below this, skip (regime says don't trade) (0.5%)
MAX_ALLOCATION_PCT = 0.25      # Share-count cap as % of account

# Tier risk multipliers (replaces numeric conviction_mod)
TIER_RISK_MULT = {
    "PASS": 0.70,
    "STRONG": 1.00,
    "EXCEPTIONAL": 1.20,
}

# Confirm bonus from Agent 3 CONFIRM_ENHANCED verdict
CONFIRM_RISK_MULT = {True: 1.10, False: 1.00}

# Vol regime risk multipliers
VOL_RISK_MULT = {
    "Compressed": 1.10,
    "Normal": 1.00,
    "Elevated": 0.70,
    "Stressed": 0.40,
}

# Posture risk multipliers
POSTURE_RISK_MULT = {
    "Aggressive": 1.00,
    "Offensive": 0.80,
    "Defensive": 0.40,
    "Bunker": 0.00,
}

# Legacy aliases (kept for backward compat, will deprecate)
BASE_ALLOCATION_CAP = 0.15
VOL_REGIME_MOD = VOL_RISK_MULT
CONVICTION_MOD = {}  # Deprecated — use TIER_RISK_MULT

# Curated smart money Twitter/X accounts for Agent 3
SMART_MONEY_ACCOUNTS = [
    # Add Twitter/X handles here when API is set up
    # e.g., "unusual_whales", "DeItaone", "zaborsky", etc.
]

# Portfolio Heat Cap
MAX_PORTFOLIO_HEAT_PCT = 0.06   # 6% of equity — reject all new trades above this
HEAT_WARNING_PCT = 0.04         # 4% — allow trades but print warning

# FRED API key (for MOVE index, credit data)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# Massive (Polygon-compatible) Market Data API
# Free tier: historical bars, technical indicators (SMA, EMA, RSI, MACD), 5 calls/min
MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "")
```

================================================================================
FILE: daemon_watchdog.py
================================================================================
```python
#!/usr/bin/env python3
"""
daemon_watchdog.py — Execution-daemon liveness check for Open Claw.

The execution daemon writes output/daemon_heartbeat.txt every ~10s. If that
file goes stale, the daemon is wedged/dead and the naked-stop safety net is
NOT running — protective stops won't auto-heal. This script reports that so a
scheduled job can alert #trading.

Exit codes:
  0 = healthy (hb_signal fresh AND process found)
  2 = STALE/DOWN (hb_signal older than threshold, or process missing)
  3 = UNKNOWN (hb_signal file missing entirely)

--json prints a machine-readable status line for the scheduler to act on.
"""
import os
import sys
import time
import json
import signal
import subprocess
from pathlib import Path

HB_SIGNAL_PATH = Path(__file__).parent / "output" / "daemon_hb_signal.txt"
# Daemon writes every 10s; flag stale only after a comfortable margin so we
# don't false-alarm on a slow loop or the atomic-rename window.
STALE_AFTER_SECONDS = 120

# Alert de-dupe: once we alert, stay quiet for this long before re-alerting on a
# still-down daemon (so a long outage doesn't spam #trading every poll).
ALERT_STATE_PATH = Path(__file__).parent / "output" / ".watchdog_last_alert"
ALERT_COOLDOWN_SECONDS = 1800  # 30 min


def should_alert() -> bool:
    """True if we haven't alerted within the cooldown window. Records the time."""
    now = time.time()
    try:
        if ALERT_STATE_PATH.exists():
            last = float(ALERT_STATE_PATH.read_text().strip() or 0)
            if now - last < ALERT_COOLDOWN_SECONDS:
                return False
    except Exception:
        pass
    try:
        ALERT_STATE_PATH.write_text(str(now))
    except Exception:
        pass
    return True


def clear_alert_state():
    """Called when healthy so the next outage alerts immediately."""
    try:
        if ALERT_STATE_PATH.exists():
            ALERT_STATE_PATH.unlink()
    except Exception:
        pass


def _daemon_pids() -> list:
    """PIDs of the wedged python CHILD (run_execution_daemon.py), NOT the bash
    supervisor. We only ever want to kill the python child so launchd's bash
    wrapper (KeepAlive) respawns a fresh one."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", "run_execution_daemon.py"],
            capture_output=True, text=True, timeout=8,
        )
        if out.returncode != 0:
            return []
        pids = []
        for line in out.stdout.split():
            line = line.strip()
            if not line.isdigit():
                continue
            pid = int(line)
            # Exclude the bash supervisor: only kill actual python processes.
            try:
                comm = subprocess.run(
                    ["ps", "-o", "command=", "-p", str(pid)],
                    capture_output=True, text=True, timeout=5,
                ).stdout.lower()
            except Exception:
                comm = ""
            if "python" in comm and "run_execution_daemon.py" in comm:
                pids.append(pid)
        return pids
    except Exception:
        return []


def _proc_alive() -> bool:
    """True if the python execution-daemon child is running."""
    return bool(_daemon_pids())


def heal_wedged_child() -> dict:
    """Kill the wedged-but-alive python child so launchd's KeepAlive bash
    supervisor respawns a fresh one. Returns a report dict.

    Why this exists: launchd only restarts the daemon when the process DIES.
    A hung child (blocked on a broker/API call or a lock) stays alive but stops
    writing the hb_signal, so the naked-stop safety net silently dies and never
    auto-heals. SIGTERM the child here -> wrapper loop / launchd respawns it.
    """
    pids = _daemon_pids()
    killed = []
    if not pids:
        return {"healed": False, "killed": [], "note": "no python child found (launchd will respawn on its own)"}
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            pass
        except Exception as e:
            return {"healed": False, "killed": killed, "note": f"failed to kill {pid}: {e}"}
    # Give it a moment; escalate to SIGKILL if still wedged.
    time.sleep(3)
    still = [p for p in killed if _pid_running(p)]
    for pid in still:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    return {"healed": True, "killed": killed, "note": "sent SIGTERM (SIGKILL escalation if needed); launchd/wrapper will respawn"}


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def check() -> dict:
    now = time.time()
    proc = _proc_alive()

    if not HB_SIGNAL_PATH.exists():
        return {
            "status": "unknown",
            "healthy": False,
            "code": 3,
            "reason": "hb_signal file missing",
            "hb_signal_age_s": None,
            "proc_alive": proc,
        }

    age = round(now - HB_SIGNAL_PATH.stat().st_mtime, 1)
    stale = age > STALE_AFTER_SECONDS

    if stale or not proc:
        reasons = []
        if stale:
            reasons.append(f"hb_signal stale ({age}s > {STALE_AFTER_SECONDS}s)")
        if not proc:
            reasons.append("daemon process not found")
        return {
            "status": "down",
            "healthy": False,
            "code": 2,
            "reason": "; ".join(reasons),
            "heartbeat_age_s": age,
            "proc_alive": proc,
        }

    return {
        "status": "healthy",
        "healthy": True,
        "code": 0,
        "reason": f"hb_signal fresh ({age}s) and process alive",
        "hb_signal_age_s": age,
        "proc_alive": proc,
    }


if __name__ == "__main__":
    result = check()

    # --heal: self-healing mode for the scheduled job. If the daemon is DOWN
    # because the python child is WEDGED (stale hb_signal but proc_alive=True),
    # kill the child so launchd respawns a fresh one. Then alert #trading once
    # (respecting cooldown). Prints exactly one of:
    #   OK                                  -> healthy (or already alerted recently)
    #   HEALED <one-line what-happened>     -> we killed a wedged child + respawn coming
    #   ALERT <one-line reason>             -> down for another reason (e.g. proc truly gone)
    if "--heal" in sys.argv:
        if result["healthy"]:
            clear_alert_state()
            print("OK")
            sys.exit(0)

        age = result.get("hb_signal_age_s")
        age_str = f"{age}s" if age is not None else "n/a"
        wedged = result.get("proc_alive")  # alive but stale == wedged child

        if wedged:
            heal = heal_wedged_child()
            if should_alert():
                print(
                    f"HEALED \U0001f527 Open Claw execution daemon was WEDGED "
                    f"({result['reason']}, hb_signal age {age_str}). "
                    f"Killed stuck python child {heal.get('killed')} so launchd "
                    f"respawns a fresh one. Naked-stop safety net auto-recovering."
                )
            else:
                print("OK")  # healed but within cooldown
        else:
            # Process genuinely gone (or hb_signal file missing) -> launchd should
            # already be respawning; just alert if outside cooldown.
            if should_alert():
                print(
                    f"ALERT \U0001f6a8 Open Claw EXECUTION DAEMON DOWN \u2014 {result['reason']} "
                    f"(hb_signal age {age_str}, process_alive={result['proc_alive']}). "
                    f"launchd should respawn the supervisor; if this persists, check "
                    f"`bash /Users/chris/code/trading-pipeline/run_execution_daemon.sh`."
                )
            else:
                print("OK")
        sys.exit(0)

    # --alert-gate: for the scheduled job. Prints exactly one of:
    #   OK                          -> daemon healthy (or already alerted recently)
    #   ALERT <one-line reason>     -> daemon down AND outside cooldown -> POST IT
    # This lets the agent turn stay silent unless there's a fresh, real problem.
    if "--alert-gate" in sys.argv:
        if result["healthy"]:
            clear_alert_state()
            print("OK")
        elif should_alert():
            age = result.get("hb_signal_age_s")
            age_str = f"{age}s" if age is not None else "n/a"
            print(
                f"ALERT \U0001f6a8 Open Claw EXECUTION DAEMON DOWN — {result['reason']} "
                f"(hb_signal age {age_str}, process_alive={result['proc_alive']}). "
                f"The naked-stop safety net is NOT running. Protective stops will "
                f"not auto-heal until the daemon is restarted: "
                f"`bash /Users/chris/code/trading-pipeline/run_execution_daemon.sh` "
                f"is the supervisor — check it / kill the wedged python child so it respawns."
            )
        else:
            print("OK")  # down but within cooldown — already alerted, stay quiet
        sys.exit(0)

    if "--json" in sys.argv:
        print(json.dumps(result))
    else:
        icon = "🟢" if result["healthy"] else ("🔴" if result["code"] == 2 else "⚪")
        print(f"{icon} execution daemon: {result['status'].upper()} — {result['reason']}")
    sys.exit(result["code"])
```

================================================================================
FILE: data_provider.py
================================================================================
```python
"""
data_provider.py — Unified Data Provider Abstraction

Single seam for all market data access. Routes through paid vendors
(Massive/Polygon, Tiingo) instead of yfinance scraping.

Fallback hierarchy per method:
  get_bars:    Massive → yfinance (deprecated fallback) → raise DataUnavailable
  get_quote:   Tiingo (via market_data) → raise DataUnavailable
  get_index:   Massive I:<SYM> → ETF proxy → raise DataUnavailable
  get_corporate_actions: Massive splits → [] with log warning

Rate limiting: Token-bucket for Massive free tier (5 calls/min).
"""
import os
import time
import logging
import threading
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

logger = logging.getLogger("DataProvider")


class DataUnavailable(Exception):
    """Raised when no data source can fulfill the request."""
    pass


# ── Rate Limiter ─────────────────────────────────────────────────────

class _TokenBucket:
    """Thread-safe token-bucket rate limiter for Massive free tier (5 calls/min).
    
    The read-modify-write on _timestamps is protected by a Lock to prevent
    concurrent ThreadPoolExecutor workers from all seeing "under limit" at
    the same millisecond and firing parallel requests that trigger 429s.
    """

    def __init__(self, max_calls: int = 5, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: list = []
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            self._timestamps = [t for t in self._timestamps if now - t < self.window]
            if len(self._timestamps) >= self.max_calls:
                sleep_time = self.window - (now - self._timestamps[0]) + 0.5
                if sleep_time > 0:
                    logger.info(f"Rate limit: waiting {sleep_time:.1f}s")
                    # Release lock during sleep so other threads can check
                    self._lock.release()
                    time.sleep(sleep_time)
                    self._lock.acquire()
            self._timestamps.append(time.time())


# ── Data Provider ────────────────────────────────────────────────────

class DataProvider:
    """
    Unified market data provider with cascading fallbacks.

    Usage:
        dp = DataProvider()
        bars = dp.get_bars("AAPL", lookback_days=60)
        index = dp.get_index("VIX")
        splits = dp.get_corporate_actions("NVDA", since_days=7)
    """

    def __init__(self):
        self._massive_key = os.environ.get("MASSIVE_API_KEY", "")
        self._massive_base = "https://api.massive.com"
        self._limiter = _TokenBucket(max_calls=5, window_seconds=60)

        # Schwab credentials loaded lazily
        self._schwab_quotes_fn = None

    # ── Public API ───────────────────────────────────────────────────

    def get_bars(
        self,
        ticker: str,
        lookback_days: int = 60,
        timespan: str = "day",
    ) -> pd.DataFrame:
        """
        OHLCV bars, newest last. Columns: Open, High, Low, Close, Volume.
        Fallback: Massive → yfinance (deprecated) → raise DataUnavailable.
        """
        # 1. Massive (Polygon)
        if self._massive_key:
            try:
                df = self._massive_bars(ticker, lookback_days, timespan)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"Massive bars failed for {ticker}: {e}")

        # 2. yfinance fallback (deprecated — will be removed)
        try:
            df = self._yfinance_bars(ticker, lookback_days, timespan)
            if df is not None and not df.empty:
                logger.info(f"[DataProvider] {ticker} served from yfinance fallback")
                return df
        except Exception as e:
            logger.warning(f"yfinance bars failed for {ticker}: {e}")

        raise DataUnavailable(f"No bar data available for {ticker}")

    def get_quote(self, ticker: str) -> dict:
        """
        Live bid/ask/last for execution.
        Source: Tiingo (via unified market_data) → raise DataUnavailable.
        """
        try:
            quotes = self._live_quotes([ticker])
            q = quotes.get(ticker)
            if q and "error" not in q:
                return q
        except Exception as e:
            logger.warning(f"Live quote failed for {ticker}: {e}")

        raise DataUnavailable(f"No live quote available for {ticker}")

    def get_index(self, symbol: str) -> dict:
        """
        Index level for VIX/SPX.
        Fallback: Massive I:<SYM> → ETF proxy → raise.
        Returns: {'symbol', 'value', 'source', 'is_proxy': bool}
        """
        symbol = symbol.upper().replace("^", "")
        massive_ticker = f"I:{symbol}"
        etf_proxy = {"VIX": "VIXY", "SPX": "SPY"}.get(symbol)

        # 1. Massive index snapshot
        if self._massive_key:
            try:
                val = self._massive_index(massive_ticker)
                if val is not None:
                    return {"symbol": symbol, "value": val, "source": "massive", "is_proxy": False}
            except Exception as e:
                logger.warning(f"Massive index {massive_ticker} failed: {e}")

        # 2. ETF proxy
        if etf_proxy:
            try:
                bars = self.get_bars(etf_proxy, lookback_days=5, timespan="day")
                if not bars.empty:
                    proxy_val = float(bars["Close"].iloc[-1])
                    logger.info(f"[DataProvider] {symbol} served via ETF proxy {etf_proxy} = {proxy_val}")
                    return {"symbol": symbol, "value": proxy_val, "source": f"etf_proxy_{etf_proxy}", "is_proxy": True}
            except Exception as e:
                logger.warning(f"ETF proxy {etf_proxy} for {symbol} failed: {e}")

        raise DataUnavailable(f"No index data available for {symbol}")

    # Class-level health flag: once the Massive splits endpoint looks down,
    # stop hammering it (and skip the rate-limiter wait) for the rest of the run.
    _corp_actions_failures = 0
    _corp_actions_disabled = False
    _CORP_ACTIONS_FAIL_LIMIT = 3

    def get_corporate_actions(self, ticker: str, since_days: int = 7) -> list:
        """
        Recent splits/dividends.
        Fallback: Massive → [] with log warning.

        Self-disables after a few consecutive failures so a down/slow Massive
        endpoint (free tier is 5 calls/min) can't stall the pipeline for minutes.
        """
        # Source already deemed unhealthy this run — skip immediately.
        if DataProvider._corp_actions_disabled:
            return []

        # 1. Massive splits endpoint
        if self._massive_key:
            try:
                result = self._massive_splits(ticker, since_days)
                DataProvider._corp_actions_failures = 0  # healthy response resets
                return result
            except Exception as e:
                DataProvider._corp_actions_failures += 1
                logger.warning(f"Massive splits failed for {ticker}: {e}")
                if DataProvider._corp_actions_failures >= DataProvider._CORP_ACTIONS_FAIL_LIMIT:
                    DataProvider._corp_actions_disabled = True
                    logger.warning(
                        f"[DataProvider] Corp-action source disabled after "
                        f"{DataProvider._corp_actions_failures} failures — "
                        f"skipping split checks for the rest of this run."
                    )
                return []

        logger.warning(f"[DataProvider] No corporate action data available for {ticker}")
        return []

    def get_news(self, ticker: str, limit: int = 5) -> list:
        """
        Recent news headlines for a ticker.
        Fallback: Massive -> yfinance -> [].
        Returns list of dicts with 'title', 'publisher', 'published'.
        """
        # 1. Massive news endpoint
        if self._massive_key:
            try:
                articles = self._massive_news(ticker, limit)
                if articles:
                    return articles
            except Exception as e:
                logger.warning(f"Massive news failed for {ticker}: {e}")

        # 2. yfinance fallback
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            news_items = stock.news or []
            return [
                {
                    "title": n.get("title", ""),
                    "publisher": n.get("publisher", ""),
                    "published": n.get("providerPublishTime", ""),
                }
                for n in news_items[:limit]
            ]
        except Exception as e:
            logger.warning(f"yfinance news failed for {ticker}: {e}")

        return []

    # ── Massive (Polygon) Internals ──────────────────────────────────

    def _massive_get(self, endpoint: str, params: dict = None) -> dict:
        """Authenticated GET to Massive with rate limiting."""
        self._limiter.wait()
        params = params or {}
        params["apiKey"] = self._massive_key
        url = f"{self._massive_base}{endpoint}"
        # 5s timeout: corp-action/split checks are non-fatal (caller passes on
        # failure), so don't let a slow/down Massive API stall the whole pipeline.
        resp = requests.get(url, params=params, timeout=5)

        if resp.status_code == 403:
            logger.warning(f"Massive 403 (not entitled): {endpoint}")
            return {}
        if resp.status_code == 429:
            logger.warning(f"Massive 429 (rate limited): {endpoint}")
            time.sleep(12)
            resp = requests.get(url, params=params, timeout=5)

        resp.raise_for_status()
        return resp.json()

    def _massive_bars(self, ticker: str, lookback_days: int, timespan: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV bars from Massive/Polygon aggregates endpoint."""
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        multiplier = 1

        data = self._massive_get(
            f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}",
            params={"limit": 5000, "sort": "asc"},
        )

        results = data.get("results", [])
        if not results:
            return None

        df = pd.DataFrame(results)
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume", "t": "timestamp"})
        df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("Date")
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        return df

    def _massive_index(self, ticker: str) -> Optional[float]:
        """Fetch index snapshot from Massive. Returns value or None."""
        # Try previous day endpoint first (works on broader tiers)
        data = self._massive_get(f"/v2/aggs/ticker/{ticker}/prev")
        results = data.get("results", [])
        if results:
            return float(results[0].get("c", 0))

        # Try snapshot endpoint
        data = self._massive_get("/v3/snapshot/indices", params={"ticker.any_of": ticker})
        results = data.get("results", [])
        if results:
            session = results[0].get("session", {}) or results[0].get("value", {})
            return float(session.get("close", session.get("value", 0)))

        return None

    def _massive_splits(self, ticker: str, since_days: int) -> list:
        """Fetch recent stock splits from Massive/Polygon reference endpoint."""
        data = self._massive_get("/v3/reference/splits", params={
            "ticker": ticker,
            "limit": 10,
            "sort": "execution_date",
            "order": "desc",
        })

        results = data.get("results", [])
        cutoff = (datetime.now() - timedelta(days=since_days)).strftime("%Y-%m-%d")
        recent = []
        for split in results:
            if split.get("execution_date", "1970-01-01") >= cutoff:
                recent.append({
                    "ticker": split.get("ticker"),
                    "execution_date": split.get("execution_date"),
                    "split_from": split.get("split_from"),
                    "split_to": split.get("split_to"),
                })
        return recent

    def _massive_news(self, ticker: str, limit: int = 5) -> list:
        """Fetch news articles from Massive/Polygon reference endpoint."""
        data = self._massive_get("/v2/reference/news", params={
            "ticker": ticker,
            "limit": limit,
            "sort": "published_utc",
            "order": "desc",
        })

        results = data.get("results", [])
        return [
            {
                "title": article.get("title", ""),
                "publisher": article.get("publisher", {}).get("name", "") if isinstance(article.get("publisher"), dict) else str(article.get("publisher", "")),
                "published": article.get("published_utc", ""),
            }
            for article in results
        ]

    # ── Schwab Internals ─────────────────────────────────────────────

    def _live_quotes(self, tickers: list) -> dict:
        """Lazy-load and call the unified market_data quote function (Tiingo-first)."""
        if self._schwab_quotes_fn is None:
            try:
                from market_data import fetch_latest_quotes
                self._schwab_quotes_fn = fetch_latest_quotes
            except ImportError:
                raise DataUnavailable("market_data module not available")
        return self._schwab_quotes_fn(tickers)

    # ── yfinance Fallback (deprecated) ───────────────────────────────

    @staticmethod
    def _yfinance_bars(ticker: str, lookback_days: int, timespan: str) -> Optional[pd.DataFrame]:
        """Deprecated yfinance fallback. Will be removed in a future PR."""
        import yfinance as yf
        period_map = {
            "day": f"{lookback_days}d" if lookback_days <= 30 else "3mo" if lookback_days <= 90 else "6mo",
        }
        interval_map = {"day": "1d", "minute": "1m", "hour": "1h"}

        period = period_map.get(timespan, "3mo")
        interval = interval_map.get(timespan, "1d")

        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty:
            return None

        # Normalize multi-index columns from yfinance
        if hasattr(data.columns, "levels") and len(data.columns.levels) > 1:
            data = data.droplevel(1, axis=1)

        return data[["Open", "High", "Low", "Close", "Volume"]]


# ── Mock Provider for Testing ────────────────────────────────────────

class MockDataProvider(DataProvider):
    """
    Mock provider for unit tests. Returns canned data, no network calls.

    Usage:
        bars = pd.DataFrame({'Open': [...], 'High': [...], ...})
        dp = MockDataProvider(bars={"AAPL": bars}, indices={"VIX": 18.5})
    """

    def __init__(self, bars: dict = None, quotes: dict = None, indices: dict = None, splits: dict = None, news: dict = None):
        self._canned_bars = bars or {}
        self._canned_quotes = quotes or {}
        self._canned_indices = indices or {}
        self._canned_splits = splits or {}
        self._canned_news = news or {}

    def get_bars(self, ticker: str, lookback_days: int = 60, timespan: str = "day") -> pd.DataFrame:
        if ticker in self._canned_bars:
            return self._canned_bars[ticker]
        raise DataUnavailable(f"MockDataProvider: no bars for {ticker}")

    def get_quote(self, ticker: str) -> dict:
        if ticker in self._canned_quotes:
            return self._canned_quotes[ticker]
        raise DataUnavailable(f"MockDataProvider: no quote for {ticker}")

    def get_index(self, symbol: str) -> dict:
        symbol = symbol.upper().replace("^", "")
        if symbol in self._canned_indices:
            return {"symbol": symbol, "value": self._canned_indices[symbol], "source": "mock", "is_proxy": False}
        raise DataUnavailable(f"MockDataProvider: no index for {symbol}")

    def get_corporate_actions(self, ticker: str, since_days: int = 7) -> list:
        return self._canned_splits.get(ticker, [])

    def get_news(self, ticker: str, limit: int = 5) -> list:
        return self._canned_news.get(ticker, [])


# ── Singleton ────────────────────────────────────────────────────────

_default_provider: Optional[DataProvider] = None


def get_provider() -> DataProvider:
    """Get the default DataProvider singleton."""
    global _default_provider
    if _default_provider is None:
        _default_provider = DataProvider()
    return _default_provider


def set_provider(provider: DataProvider):
    """Override the default DataProvider (for testing)."""
    global _default_provider
    _default_provider = provider
```

================================================================================
FILE: discord_fetch.py
================================================================================
```python
"""
Discord Smart Money Fetch — Pulls recent messages from curated Discord channels
for use in the Open Claw trading pipeline (Agent 3 signal verification).

Reads from The Assembly and ClearValue Investing Discord servers.
Filters for ticker mentions and saves structured JSON for Agent 3.

Uses the same Discord token and config as the daily email summarizer.

Usage:
  python3 discord_fetch.py                    # Fetch all high-signal channels (24h)
  python3 discord_fetch.py --tickers V EOG LLY  # Filter for specific tickers
  python3 discord_fetch.py --hours 48          # Custom lookback window
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Discord API
DISCORD_API = "https://discord.com/api/v10"

# Config from discord-summarizer
SUMMARIZER_CONFIG = Path("/Users/chris/code/discord-summarizer/config.json")

# High-signal channels for trading pipeline (skip lounge, scam_alert, youtube, etc.)
# Jamie's curated channel list (May 19, 2026)
HIGH_SIGNAL_CHANNELS = {
    "The Assembly": [
        # MARKETS
        "market-sentiment",    # Sentiment discussion
        "requested-analysis",  # Requested analysis
        "important-news",      # Curated important news
        "live-news",           # Breaking news
        "live-intel",          # Real-time market intelligence
        # INTELLIGENCE
        "insider-moves",       # Insider trading activity
        "flow-desk",           # Options flow, unusual activity
        "institutional-flow",  # Institutional buying/selling
        "macro-desk",          # Macro analysis
        "geo-intel",           # Geopolitical intelligence
        # CONVICTION
        "high-conviction-long-term-ideas",  # High-conviction plays
        "undervalued-stocks",  # Value plays
        "names-we-track",      # Tracked ticker discussion
    ],
    "ClearValue Investing": [
        # JD ORDERS ONLY channel — update channel name once confirmed
        "short-term-trades",   # Placeholder until Jamie confirms exact channel
    ],
}

# Ticker mention patterns
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
TICKER_WORD_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# Common words that look like tickers but aren't
TICKER_BLACKLIST = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
    "WAS", "ONE", "OUR", "OUT", "HAS", "HIS", "HOW", "MAN", "NEW", "NOW",
    "OLD", "SEE", "WAY", "WHO", "DID", "GET", "HIM", "LET", "SAY", "SHE",
    "TOO", "USE", "DAY", "HAD", "HOT", "OIL", "SIT", "TOP", "RED", "RUN",
    "YES", "YET", "BIG", "END", "FAR", "PUT", "SET", "TRY", "ASK", "OWN",
    "WHY", "MEN", "READ", "NEED", "LAND", "JUST", "ALSO", "BEEN", "CALL",
    "VERY", "WHEN", "COME", "MADE", "FIND", "BACK", "ONLY", "LONG", "MUCH",
    "TAKE", "THAN", "THEM", "TURN", "INTO", "YEAR", "SOME", "WANT", "SHOW",
    "GOOD", "GIVE", "MOST", "TOLD", "WITH", "THIS", "THAT", "WILL", "EACH",
    "MAKE", "LIKE", "HAVE", "FROM", "WORD", "WHAT", "WERE", "DOES", "KEEP",
    "HIGH", "LOW", "BUY", "SELL", "HOLD", "LONG", "SHORT", "BULL", "BEAR",
    "IPO", "SEC", "GDP", "CPI", "FED", "IMF", "CEO", "CFO", "COO", "ETF",
    "USD", "EUR", "GBP", "JPY", "CNY", "BPS", "YOY", "QOQ", "MOM", "ATH",
    "ATL", "EPS", "PE", "PB", "ROE", "ROA", "FCF", "DCF", "EBITDA", "FOMC",
    "NFP", "PMI", "ISM", "PPI", "PCE", "TIPS", "MOVE", "DIX", "GEX",
    "MAX", "MIN", "AVG", "SUM", "NET", "WIN", "LOSS", "GAIN", "DROP",
    "RISK", "SAFE", "PUMP", "DUMP", "MOON", "DIP", "FOMO", "YOLO",
    "HUGE", "MEGA", "NICE", "LMAO", "BTFD", "HODL", "WAGMI", "NGMI",
    "NEWS", "JUST", "LOOK", "DONT", "STOP", "WAIT", "OPEN", "CLOSE",
    "RIP", "LOL", "BTW", "IMO", "TBH", "NEXT", "LAST", "WEEK", "SURE",
    "PLAY", "MOVE", "TAKE", "BEEN", "DONE", "REAL", "FREE", "BEST",
}


def load_config() -> dict:
    """Load Discord config from the summarizer."""
    if not SUMMARIZER_CONFIG.exists():
        raise FileNotFoundError(f"Discord config not found at {SUMMARIZER_CONFIG}")
    with open(SUMMARIZER_CONFIG) as f:
        return json.load(f)


def snowflake_from_datetime(dt: datetime) -> str:
    """Convert datetime to Discord snowflake for pagination."""
    discord_epoch = 1420070400000
    timestamp_ms = int(dt.timestamp() * 1000)
    return str((timestamp_ms - discord_epoch) << 22)


def fetch_channel_messages(token: str, channel_id: str, after_dt: datetime, limit: int = 200) -> list:
    """Fetch messages from a Discord channel after a given datetime."""
    headers = {"Authorization": token}
    after_snowflake = snowflake_from_datetime(after_dt)
    all_messages = []
    last_id = after_snowflake

    while True:
        params = {"after": last_id, "limit": 100}
        resp = requests.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=headers,
            params=params,
        )
        if resp.status_code == 403:
            return []  # No access
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(retry_after + 0.5)
            continue
        if resp.status_code != 200:
            return []
        messages = resp.json()
        if not messages:
            break
        all_messages.extend(messages)
        if len(messages) < 100 or len(all_messages) >= limit:
            break
        last_id = max(m["id"] for m in messages)
        time.sleep(0.5)

    return all_messages


def extract_tickers(text: str) -> list:
    """Extract stock ticker mentions from message text."""
    tickers = set()

    # $TICKER pattern (high confidence)
    for match in TICKER_PATTERN.findall(text):
        if match not in TICKER_BLACKLIST:
            tickers.add(match)

    return list(tickers)


def fetch_discord_mentions(tickers: list = None, hours: int = 24) -> dict:
    """
    Fetch Discord messages from high-signal channels and extract ticker mentions.

    Args:
        tickers: If provided, only return mentions for these tickers
        hours: Lookback window in hours (default 24)

    Returns:
        {
            "timestamp": "ISO",
            "lookback_hours": 24,
            "channels_scraped": 27,
            "total_messages": 150,
            "mentions": {
                "TICKER": [
                    {
                        "text": "message content",
                        "author": "username",
                        "channel": "channel-name",
                        "server": "server-name",
                        "timestamp": "ISO",
                        "channel_type": "flow-desk"
                    }
                ]
            }
        }
    """
    config = load_config()
    token = config["discord_token"]
    servers = config["servers"]

    after_dt = datetime.now(timezone.utc) - timedelta(hours=hours)

    all_mentions = {}  # ticker -> [mentions]
    total_messages = 0
    channels_scraped = 0

    for server_name, channel_list in HIGH_SIGNAL_CHANNELS.items():
        if server_name not in servers:
            print(f"[Discord] Server '{server_name}' not in config, skipping")
            continue

        server_config = servers[server_name]
        server_channels = server_config["channels"]

        for channel_name in channel_list:
            if channel_name not in server_channels:
                continue

            channel_id = server_channels[channel_name]
            messages = fetch_channel_messages(token, channel_id, after_dt)
            channels_scraped += 1

            for msg in messages:
                total_messages += 1
                content = msg.get("content", "")
                if not content:
                    continue

                # Also check embeds
                for embed in msg.get("embeds", []):
                    if embed.get("title"):
                        content += " " + embed["title"]
                    if embed.get("description"):
                        content += " " + embed["description"]

                found_tickers = extract_tickers(content)
                author = msg.get("author", {}).get("username", "unknown")
                msg_time = msg.get("timestamp", "")

                for ticker in found_tickers:
                    if tickers and ticker not in tickers:
                        continue  # Skip if not in requested ticker list

                    if ticker not in all_mentions:
                        all_mentions[ticker] = []

                    all_mentions[ticker].append({
                        "text": content[:500],  # Truncate long messages
                        "author": author,
                        "channel": channel_name,
                        "server": server_name,
                        "timestamp": msg_time,
                    })

            if messages:
                print(f"  [Discord] {server_name}/{channel_name}: {len(messages)} messages")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lookback_hours": hours,
        "channels_scraped": channels_scraped,
        "total_messages": total_messages,
        "tickers_found": len(all_mentions),
        "mentions": all_mentions,
    }

    # Save output
    os.makedirs("output", exist_ok=True)
    with open("output/discord_mentions.json", "w") as f:
        json.dump(result, f, indent=2, default=str)

    # Summary
    print(f"\n[Discord] Complete. {channels_scraped} channels, {total_messages} messages, {len(all_mentions)} tickers mentioned")
    for ticker in sorted(all_mentions, key=lambda t: len(all_mentions[t]), reverse=True)[:10]:
        mentions = all_mentions[ticker]
        channels = set(m["channel"] for m in mentions)
        print(f"  {ticker}: {len(mentions)} mentions across {len(channels)} channels")

    return result


def format_discord_for_agent3(discord_data: dict, tickers: list) -> str:
    """Format Discord mentions for Agent 3's prompt."""
    mentions = discord_data.get("mentions", {})
    lines = [
        f"DISCORD SMART MONEY MENTIONS (last {discord_data.get('lookback_hours', 24)}h)",
        f"Sources: The Assembly + ClearValue Investing ({discord_data.get('channels_scraped', 0)} channels)",
        "=" * 50,
    ]

    for ticker in tickers:
        ticker_mentions = mentions.get(ticker, [])
        if not ticker_mentions:
            lines.append(f"\n{ticker} -- 0 Discord mentions (silent)")
        else:
            channels = set(m["channel"] for m in ticker_mentions)
            lines.append(f"\n{ticker} -- {len(ticker_mentions)} mentions across {', '.join(channels)}:")
            for m in ticker_mentions[:5]:  # Cap at 5 per ticker
                lines.append(f"  [{m['server']}/{m['channel']}] @{m['author']}: {m['text'][:200]}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discord Smart Money Fetch")
    parser.add_argument("--tickers", nargs="*", help="Filter for specific tickers")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours (default 24)")
    args = parser.parse_args()

    print(f"[Discord] Fetching messages from last {args.hours} hours...")
    result = fetch_discord_mentions(tickers=args.tickers, hours=args.hours)
```

================================================================================
FILE: eod_stop_digest.py
================================================================================
```python
#!/usr/bin/env python3
"""
End-of-Day Stop Reinforcement Digest.

Runs at 4:00 PM ET. Parses the day's reinforcement log (all 12 half-hourly
runs) plus the current portfolio_state.json (HWM stops) and produces ONE clean
summary of every stop movement during the day, then posts it to Slack #trading.

Pure read-only: places no orders, touches no broker. Safe to run anytime.
"""
import json
import os
import re
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE, "output", "portfolio_state.json")
LOG_PATH = os.path.join(BASE, "output", "logs", f"hourly_reinforce_{datetime.now():%Y-%m-%d}.log")


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def parse_log_movements(path: str) -> dict:
    """
    Scan the day's reinforce log for HWM stop updates.
    Lines look like: '... [HWM updated: $12.34 -> $13.00]'
    Returns {ticker: {"first": x, "last": y, "n_updates": k, "notes": [...]}}.
    """
    moves = {}
    if not os.path.exists(path):
        return moves
    # Capture e.g. "BAC: ... [HWM updated: $50.00 → $51.20]"
    pat = re.compile(r"([A-Z]{1,5}):.*?HWM updated:\s*\$([0-9.]+)\s*[→-]+>?\s*\$([0-9.]+)")
    with open(path, errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if not m:
                continue
            t, old, new = m.group(1), float(m.group(2)), float(m.group(3))
            d = moves.setdefault(t, {"first": old, "last": new, "n": 0})
            d["last"] = new
            d["n"] += 1
    return moves


def count_runs(path: str) -> int:
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, errors="ignore") as f:
        for line in f:
            if line.startswith("=== Hourly Reinforce —"):
                n += 1
    return n


def build_digest() -> str:
    state = load_state()
    moves = parse_log_movements(LOG_PATH)
    runs = count_runs(LOG_PATH)
    today = f"{datetime.now():%a %b %d, %Y}"

    lines = [f"*📋 EOD Stop Reinforcement Digest — {today}*"]
    lines.append(f"_{runs} reinforcement runs today (every 30 min, 10:00–15:30 ET)_")
    lines.append("")

    if moves:
        lines.append("*Stops that moved up today:*")
        for t in sorted(moves):
            mv = moves[t]
            lines.append(
                f"• *{t}*: ${mv['first']:.2f} → *${mv['last']:.2f}* "
                f"({mv['n']} ratchet{'s' if mv['n'] != 1 else ''})"
            )
    else:
        lines.append("No stop movements today (no position gained enough to trigger a tighten).")

    lines.append("")
    lines.append("*Current live stops (high-water-mark):*")
    if state:
        for t in sorted(state):
            s = state[t]
            stop = s.get("hwm_stop", 0)
            scaled = s.get("scaled_fraction", 0)
            tag = f"  _({int(scaled*100)}% scaled out)_" if scaled else ""
            lines.append(f"• {t}: ${stop:.2f}{tag}")
    else:
        lines.append("_(no portfolio state found)_")

    return "\n".join(lines)


if __name__ == "__main__":
    digest = build_digest()
    # Print to stdout (captured in log). Slack delivery is handled by the
    # runner wrapper via the OpenClaw message path / webhook if configured.
    print(digest)
```

================================================================================
FILE: execution_engine.py
================================================================================
```python
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_incidents (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    date            TEXT NOT NULL,
                    ticker          TEXT NOT NULL,
                    incident_type   TEXT NOT NULL,
                    limit_price     REAL,
                    bid             REAL,
                    ask             REAL,
                    mid             REAL,
                    spread_bps      REAL,
                    target_shares   INTEGER,
                    filled_shares   INTEGER DEFAULT 0,
                    time_open_sec   INTEGER,
                    close_reason    TEXT,
                    root_cause      TEXT,
                    fix_applied     TEXT,
                    notes           TEXT,
                    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        shares: float,
        limit_price: float,
        stop_price: float,
    ) -> dict:
        """
        Orchestrator calls this instead of calling the broker directly.
        Routes the entry order and records the intent in the ledger.
        The daemon will handle stop placement after fill.

        NOTE (2026-07-06): shares is FLOAT — Robinhood supports fractional
        shares and the account is configured for fractional sizing. Do NOT
        int()-truncate upstream (0.9 -> 0 is a dead order).
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

    # ── Partial Scale-Out (Agent 5 TRIM) ────────────────────────────

    def atomic_trim(self, ticker: str, trim_pct: float, new_stop: float = None,
                    reason: str = "Agent5_TRIM") -> dict:
        """
        Partial scale-out for the LIVE (Robinhood) account.

        Robinhood resting stop/TP legs encumber the shares they cover. A naive
        partial sell will either reject (encumbered) or oversell. So we mirror
        atomic_liquidate's discipline for a TRANCHE:

          1. Cancel ALL resting sell orders for this ticker (stop + any TP leg),
             which were sized to the OLD full qty.
          2. Wait for the clearinghouse to release the encumbered shares.
          3. Market-sell exactly the tranche (always leave >= 1 share runner).
          4. Re-arm a fresh protective stop on the REMAINDER, and update the
             ledger so the daemon stays in sync (doesn't double-place a stop).

        trim_pct is a fraction of CURRENT holdings (Agent 5 already accounts for
        tranches sold on prior days via persistent scaled_fraction state).
        """
        try:
            lock = FileLock(LOCK_PATH, timeout=15)
            with lock:
                logger.warning(f"✂️ ATOMIC TRIM: {ticker} ({reason}) trim_pct={trim_pct}")

                # 0. Size the tranche off CURRENT settled holdings.
                positions = self.broker.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)
                if not pos or float(pos.get("shares", 0)) <= 0:
                    logger.info(f"  No inventory for {ticker} — nothing to trim")
                    return {"ticker": ticker, "action": "TRIM", "status": "no_position"}

                cur_shares = int(float(pos["shares"]))
                if cur_shares < 2:
                    logger.info(f"  {ticker} only {cur_shares} share(s) — too small to trim")
                    return {"ticker": ticker, "action": "TRIM", "status": "too_small_to_trim"}

                frac = (trim_pct / 100.0) if trim_pct and trim_pct > 1 else (trim_pct or 0.33)
                trim_qty = max(1, int(cur_shares * frac))
                trim_qty = min(trim_qty, cur_shares - 1)  # always leave a runner
                remaining = cur_shares - trim_qty

                # 1. Cancel resting sell legs (sized to old full qty).
                all_orders = self.broker.get_orders_today()
                open_sells = [
                    o for o in all_orders
                    if o.get("ticker") == ticker
                    and str(o.get("side", "")).lower() == "sell"
                    and o.get("status", "").lower() in ("open", "partially_filled", "queued", "confirmed")
                ]
                for o in open_sells:
                    oid = str(o.get("id") or o.get("order_id"))
                    try:
                        self.broker.cancel_order(oid)
                        logger.info(f"  Cancelled resting sell leg {oid} for {ticker}")
                    except Exception as e:
                        logger.error(f"  Cancel failed for {oid}: {e}")

                # 2. Wait for clearinghouse to release encumbered shares (max 10s).
                if open_sells:
                    timeout = time.time() + 10
                    while time.time() < timeout:
                        remaining_open = [
                            o for o in self.broker.get_orders_today()
                            if o.get("ticker") == ticker
                            and str(o.get("side", "")).lower() == "sell"
                            and o.get("status", "").lower() in ("open", "partially_filled", "queued", "confirmed")
                        ]
                        if not remaining_open:
                            logger.info(f"  Clearinghouse released encumbered shares for {ticker}")
                            break
                        time.sleep(1.5)
                    else:
                        logger.error(f"  Timeout waiting for {ticker} sell-leg cancels to clear. "
                                     "Tranche sell may fail due to encumbered shares.")

                # 3. Market-sell the tranche.
                res = self.broker.place_order(
                    ticker=ticker, side="sell", order_type="market",
                    quantity=str(trim_qty),
                )
                sell_id = res.get("order_id") or res.get("id")
                logger.info(f"  Market SELL tranche {trim_qty} {ticker} routed: {sell_id}")
                result = {
                    "ticker": ticker, "action": "TRIM", "status": "submitted",
                    "trim_qty": trim_qty, "remaining": remaining, "sell_order_id": sell_id,
                }

                # 4. Re-arm a protective stop on the remainder + sync the ledger.
                if remaining > 0 and new_stop and new_stop > 0:
                    try:
                        # Prefer the broker's place_stop helper (fractional-safe,
                        # uses stop_market). Fall back to place_order if absent.
                        if hasattr(self.broker, "place_stop"):
                            sres = self.broker.place_stop(ticker, remaining, round(new_stop, 2))
                        else:
                            sres = self.broker.place_order(
                                ticker=ticker, side="sell", order_type="stop",
                                quantity=str(remaining),
                                stop_price=str(round(new_stop, 2)),
                                time_in_force="gtc",
                            )
                        new_stop_id = sres.get("order_id") or sres.get("id")
                        if new_stop_id:
                            result["restop_order_id"] = new_stop_id
                            result["restop_price"] = round(new_stop, 2)
                            logger.info(f"  Re-armed stop for {ticker}: {remaining} sh @ ${round(new_stop,2)} (id={new_stop_id})")
                        else:
                            result["restop_error"] = "no order_id"
                            new_stop_id = None
                    except Exception as e:
                        new_stop_id = None
                        result["restop_error"] = str(e)
                        logger.error(f"  ⚠️ Failed to re-arm stop for {ticker}: {e}")

                    # Keep the ledger consistent so the daemon doesn't fight us:
                    # update filled_shares to the remainder and point at the new stop
                    # (or NULL it so the daemon re-places if our re-arm failed).
                    with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                        conn.execute(
                            """UPDATE active_trades
                               SET filled_shares = ?, target_stop_price = ?,
                                   stop_order_id = ?, stop_status = ?, last_updated = ?
                               WHERE ticker = ? AND closed_at IS NULL""",
                            (remaining, round(new_stop, 2), new_stop_id,
                             "open" if new_stop_id else None,
                             datetime.now().isoformat(), ticker),
                        )
                        conn.commit()

                self._log_event("", ticker, "ATOMIC_TRIM",
                                f"{reason} sold={trim_qty} remaining={remaining} new_stop={new_stop}")
                return result

        except Timeout:
            logger.error(f"Lock timeout during atomic trim for {ticker}")
            return {"ticker": ticker, "action": "TRIM", "status": "lock_timeout"}

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
                    # Any open trade for this ticker — NOT just ones that already
                    # have a resting stop. A recon row (or a row whose stop was
                    # just canceled) has stop_order_id IS NULL but may still be a
                    # real held position that needs a stop placed. Bailing here
                    # is exactly what left KVUE naked on 2026-06-24.
                    trade = conn.execute(
                        "SELECT * FROM active_trades WHERE ticker = ? AND closed_at IS NULL",
                        (ticker,),
                    ).fetchone()

                    if not trade:
                        logger.warning(f"No active trade found for {ticker} to trail.")
                        return False

                    trade = dict(trade)
                    old_stop_id = trade["stop_order_id"]
                    filled_shares = trade["filled_shares"]

                # If the ledger doesn't know the share count (recon row with
                # filled_shares=0 / entry_status=unknown), pull it live from the
                # broker so we place a stop for the ACTUAL held quantity.
                if not filled_shares or filled_shares <= 0:
                    try:
                        held_qty = 0.0
                        for p in self.broker.get_positions():
                            if (p.get("ticker") or p.get("symbol")) == ticker:
                                # Fractional-safe: don't int()-truncate (would leave a sliver naked)
                                held_qty = float(p.get("shares") or p.get("quantity") or p.get("qty") or 0)
                                break
                        if held_qty > 0:
                            filled_shares = held_qty
                            logger.info(f"{ticker}: ledger share count missing; using live broker qty={held_qty}")
                        else:
                            logger.warning(f"{ticker}: not held at broker (qty=0); nothing to trail.")
                            return False
                    except Exception as e:
                        logger.error(f"{ticker}: failed to read live position qty: {e}")
                        return False

                # 1. Cancel old stop (only if one exists — recon/naked rows skip this)
                if old_stop_id:
                    try:
                        self.broker.cancel_order(old_stop_id)
                        logger.info(f"Canceled old stop {old_stop_id} for {ticker}")
                    except Exception as e:
                        logger.error(f"Failed to cancel old stop {old_stop_id} for {ticker}: {e}")
                else:
                    logger.info(f"{ticker}: no existing stop to cancel — placing fresh protective stop.")

            # 2. Blocking wait for shares to unencumber (OUTSIDE lock to avoid deadlock).
            # If there was no old stop (recon/naked row), shares are already free —
            # skip the wait and go straight to placing the protective stop.
            timeout_at = time.time() + 10
            unencumbered = not old_stop_id
            while not unencumbered and time.time() < timeout_at:
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
            # Use place_stop() (type="stop_market") — the Robinhood MCP REJECTS
            # order_type="stop", which silently left positions NAKED after the
            # cancel succeeded. place_stop is the known-good path and handles
            # fractional-share rounding correctly.
            stop_res = self.broker.place_stop(
                ticker, filled_shares, round(new_stop_price, 2),
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
        """Alive if hb_signal < 60s old. Path-stable + tolerant of the atomic
        rename window so it never spuriously reports the daemon dead."""
        try:
            mtime = HEARTBEAT_PATH.stat().st_mtime
        except (FileNotFoundError, OSError):
            return False
        return (time.time() - mtime) < 60

    def _write_heartbeat(self):
        """write hb_signal timestamp ATOMICALLY (temp + os.replace) so readers
        never observe a momentarily truncated/absent file."""
        tmp = HEARTBEAT_PATH.with_suffix(".tmp")
        tmp.write_text(datetime.now().isoformat())
        os.replace(tmp, HEARTBEAT_PATH)

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

                # ── Zombie-row sweep ──────────────────────────────────────
                # Auto-close any OPEN ledger row whose ticker is NOT held at the
                # broker AND has no live resting order. These are stale recon
                # artifacts (filled_shares=0 / entry_status='unknown') or rows
                # left behind when a position exited but the exact fill event was
                # missed. Leaving them open pollutes the ledger and makes the
                # trailing logic act on phantom positions (e.g. CSCO/SMCI).
                try:
                    held = {p["ticker"] for p in self.broker.get_positions()}
                    live_order_tickers = set()
                    live_stop_tickers = set()
                    for _o in self.broker.get_orders():
                        if _o.get("state") in ("confirmed", "queued", "unconfirmed"):
                            live_order_tickers.add(_o.get("symbol"))
                            if _o.get("trigger") == "stop" or _o.get("type") in ("stop", "stop_market"):
                                live_stop_tickers.add(_o.get("symbol"))
                    for _t in active_trades:
                        _tk = _t["ticker"]
                        if _tk not in held and _tk not in live_order_tickers:
                            with sqlite3.connect(DB_PATH, timeout=20.0) as _conn:
                                _conn.execute(
                                    "UPDATE active_trades SET closed_at = ?, "
                                    "close_reason = ? WHERE trade_id = ? AND closed_at IS NULL",
                                    (datetime.now().isoformat(),
                                     "AUTO_CLEANUP: not held at broker, no live order",
                                     _t["trade_id"]),
                                )
                                _conn.commit()
                            logger.warning(
                                f"  🧹 Auto-closed zombie ledger row for {_tk} "
                                f"(trade_id={_t['trade_id']}): not held at broker, no live order."
                            )
                    # Re-read after sweep so the rest of the pass ignores zombies.
                    with sqlite3.connect(DB_PATH, timeout=20.0) as _conn:
                        _conn.row_factory = sqlite3.Row
                        active_trades = _conn.execute(
                            "SELECT * FROM active_trades WHERE closed_at IS NULL"
                        ).fetchall()
                    if not active_trades:
                        return

                    # ── Naked held-position guard ─────────────────────────────
                    # SAFETY NET: any open trade that is genuinely HELD at the
                    # broker but has NO resting stop order (stop_order_id NULL
                    # AND no live stop at the broker) is NAKED. This covers
                    # recon rows (entry_status='unknown', entry order outside
                    # today's feed) and the cancel→replace gap from update_stop().
                    # The normal stop-placement path below only fires on a fresh
                    # fill of an entry order present in today's orders, so it can
                    # never re-arm these. Place the protective stop here, now.
                    # (This is exactly the gap that left KVUE naked 2026-06-24.)
                    for _t in active_trades:
                        _t = dict(_t)
                        _tk = _t["ticker"]
                        if _tk not in held:
                            continue  # not held → handled by zombie sweep, not naked
                        if _t.get("stop_order_id") or _tk in live_stop_tickers:
                            continue  # already protected
                        _stop_px = _t.get("target_stop_price")
                        if not _stop_px or _stop_px <= 0:
                            logger.error(f"  🚨 {_tk} held but NAKED and has no target_stop_price; cannot auto-arm.")
                            continue
                        # Resolve share count: prefer the LIVE broker qty (fractional-
                        # safe — don't int()-truncate or we leave a sliver unhedged),
                        # fall back to the ledger's filled_shares.
                        _qty = 0
                        for _p in self.broker.get_positions():
                            if (_p.get("ticker") or _p.get("symbol")) == _tk:
                                _qty = float(_p.get("shares") or _p.get("quantity") or _p.get("qty") or 0)
                                break
                        if _qty <= 0:
                            _qty = float(_t.get("filled_shares") or 0)
                        if _qty <= 0:
                            continue
                        # Whole-share count for the ledger's INTEGER filled_shares column.
                        _qty_int = int(_qty)
                        logger.critical(
                            f"  🚨 {_tk} is HELD but NAKED (no stop). Auto-arming "
                            f"protective stop: {_qty} sh @ ${_stop_px:.2f}"
                        )
                        try:
                            _sres = self.broker.place_stop(_tk, _qty, round(_stop_px, 2), time_in_force="gtc")
                            _sid = _sres.get("order_id") or _sres.get("id")
                            if _sid:
                                with sqlite3.connect(DB_PATH, timeout=20.0) as _conn:
                                    _conn.execute(
                                        "UPDATE active_trades SET stop_order_id = ?, stop_status = 'open', "
                                        "filled_shares = CASE WHEN filled_shares > 0 THEN filled_shares ELSE ? END, "
                                        "entry_status = CASE WHEN entry_status = 'unknown' THEN 'filled' ELSE entry_status END, "
                                        "last_updated = ? WHERE trade_id = ?",
                                        (_sid, _qty_int, datetime.now().isoformat(), _t["trade_id"]),
                                    )
                                    _conn.commit()
                                self._log_event(_t["trade_id"], _tk, "STOP_PLACED",
                                                f"naked-guard auto-arm id={_sid} price=${_stop_px:.2f} shares={_qty}")
                                logger.info(f"  🛡️ Naked-guard armed stop for {_tk}: {_sid}")
                                live_stop_tickers.add(_tk)
                            else:
                                logger.error(f"  Naked-guard stop for {_tk} returned no ID: {_sres}")
                                self._log_event(_t["trade_id"], _tk, "STOP_FAILED", json.dumps(_sres))
                        except Exception as _se:
                            logger.error(f"  Naked-guard stop placement failed for {_tk}: {_se}")
                            self._log_event(_t["trade_id"], _tk, "STOP_ERROR", str(_se))
                except Exception as _e:
                    logger.error(f"Zombie-row sweep / naked-guard failed (non-fatal): {_e}")

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
                        # (e.g. positions reconciled into the ledger after the fact).
                        # For an already-filled trade that carries a stop_order_id, we
                        # still MONITOR the stop fill even though the original entry
                        # order is outside the broker's recent-orders window.
                        if (str(trade.get("entry_status", "")).lower() == "filled"
                                and trade.get("stop_order_id")):
                            stop_order = broker_orders.get(trade["stop_order_id"])
                            if stop_order and stop_order.get("status", "").lower() in ("filled", "executed"):
                                exit_price = float(stop_order.get("filled_avg_price", stop_order.get("average_price", trade["target_stop_price"])))
                                logger.warning(f"  STOP filled for {ticker} (reconciled) at ${exit_price:.2f}. Closing ledger row.")
                                with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
                                    conn.execute(
                                        "UPDATE active_trades SET closed_at = ?, close_reason = ? WHERE trade_id = ?",
                                        (datetime.now().isoformat(), f"NATIVE_STOP_FILLED@{exit_price:.2f}", trade["trade_id"]),
                                    )
                                    conn.commit()
                                self._log_event(trade["trade_id"], ticker, "STOP_FILLED", f"exit=${exit_price:.2f} (reconciled)")
                        else:
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
                        # Log execution incident for system review
                        self.log_incident(
                            ticker=ticker,
                            incident_type="UNFILLED_ORDER",
                            limit_price=float(trade.get("limit_price", 0) or 0),
                            target_shares=int(trade.get("target_shares", 0) or 0),
                            filled_shares=0,
                            close_reason=status,
                            root_cause="passive_limit_below_ask" if status in ("canceled", "cancelled", "expired") else status,
                            notes=f"Trade {trade['trade_id']} died with 0 fills. Entry order {status}.",
                        )

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

    # ── Execution Incident Tracking ──────────────────────────────────────

    def log_incident(
        self,
        ticker: str,
        incident_type: str,
        limit_price: float = 0,
        bid: float = 0,
        ask: float = 0,
        target_shares: int = 0,
        filled_shares: int = 0,
        time_open_sec: int = 0,
        close_reason: str = "",
        root_cause: str = "",
        fix_applied: str = "",
        notes: str = "",
    ):
        """
        Log an execution incident (unfilled order, rejected order, partial fill,
        wide spread rejection, gap-up rejection, etc.) for system review.
        """
        mid = round((bid + ask) / 2, 2) if bid and ask else 0
        spread_bps = round((ask - bid) / mid * 10000, 1) if mid > 0 else 0
        today = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            conn.execute(
                """INSERT INTO execution_incidents
                (date, ticker, incident_type, limit_price, bid, ask, mid,
                 spread_bps, target_shares, filled_shares, time_open_sec,
                 close_reason, root_cause, fix_applied, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (today, ticker, incident_type, limit_price, bid, ask, mid,
                 spread_bps, target_shares, filled_shares, time_open_sec,
                 close_reason, root_cause, fix_applied, notes),
            )
            conn.commit()
        logger.info(f"[Incident] {incident_type}: {ticker} — {root_cause or notes}")

    def get_incidents(self, days: int = 30) -> list:
        """Return execution incidents from the last N days."""
        cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d")
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM execution_incidents WHERE date >= ? ORDER BY timestamp DESC",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_fill_rate_stats(self, days: int = 30) -> dict:
        """
        Calculate fill rate and execution quality stats for system review.
        Queries active_trades to compute: orders submitted, filled, dead, fill rate.
        """
        cutoff = (datetime.now() - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d")
        with sqlite3.connect(DB_PATH, timeout=20.0) as conn:
            # Total orders submitted in period
            total = conn.execute(
                "SELECT COUNT(*) FROM active_trades WHERE created_at >= ?", (cutoff,)
            ).fetchone()[0]

            # Filled (have filled_shares > 0)
            filled = conn.execute(
                "SELECT COUNT(*) FROM active_trades WHERE created_at >= ? AND filled_shares > 0",
                (cutoff,),
            ).fetchone()[0]

            # Dead (closed with 0 fills)
            dead = conn.execute(
                "SELECT COUNT(*) FROM active_trades WHERE created_at >= ? AND closed_at IS NOT NULL AND filled_shares = 0",
                (cutoff,),
            ).fetchone()[0]

            # Still open
            pending = conn.execute(
                "SELECT COUNT(*) FROM active_trades WHERE created_at >= ? AND closed_at IS NULL AND filled_shares = 0",
                (cutoff,),
            ).fetchone()[0]

            # Incidents
            incidents = conn.execute(
                "SELECT COUNT(*) FROM execution_incidents WHERE date >= ?", (cutoff,)
            ).fetchone()[0]

        fill_rate = (filled / total * 100) if total > 0 else 0

        return {
            "period_days": days,
            "orders_submitted": total,
            "orders_filled": filled,
            "orders_dead": dead,
            "orders_pending": pending,
            "fill_rate_pct": round(fill_rate, 1),
            "incidents": incidents,
        }


# Quick test
if __name__ == "__main__":
    print("Testing Execution Engine...\n")
    engine = ExecutionEngine()
    print(f"DB: {DB_PATH}")
    print(f"Active trades: {len(engine.get_active_trades())}")
    print(f"Execution log: {len(engine.get_execution_log())} entries")
    print("\n✅ Execution Engine initialized!")
```

================================================================================
FILE: fedwatch.py
================================================================================
```python
"""
FedWatch Calculator — Derives FOMC rate expectations from Fed Funds futures.

Uses 30-Day Fed Funds futures (ZQ) from CBOT via yfinance.
Replicates the CME FedWatch methodology:
- ZQ price = 100 - implied effective fed funds rate
- Compare implied rates across FOMC meeting months to derive cut/hike probabilities
- Auto-detects current effective rate from front-month contract

No API key needed — yfinance provides the futures data.

Usage:
    from fedwatch import fetch_fedwatch, format_fedwatch_for_prompt
    data = fetch_fedwatch()
    text = format_fedwatch_for_prompt(data)
"""
import json
import os
from datetime import datetime, date
from typing import Dict, Optional

import yfinance as yf


# FOMC meeting schedule for 2026 (full year)
# Month codes: F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov, Z=Dec
FOMC_MEETINGS_2026 = [
    {"label": "Jan 2026", "ticker": "ZQF26.CBT", "date": "2026-01-29", "month_code": "F"},
    {"label": "Mar 2026", "ticker": "ZQH26.CBT", "date": "2026-03-19", "month_code": "H"},
    {"label": "May 2026", "ticker": "ZQK26.CBT", "date": "2026-05-07", "month_code": "K"},
    {"label": "Jun 2026", "ticker": "ZQM26.CBT", "date": "2026-06-18", "month_code": "M"},
    {"label": "Jul 2026", "ticker": "ZQN26.CBT", "date": "2026-07-30", "month_code": "N"},
    {"label": "Sep 2026", "ticker": "ZQU26.CBT", "date": "2026-09-17", "month_code": "U"},
    {"label": "Oct 2026", "ticker": "ZQV26.CBT", "date": "2026-10-29", "month_code": "V"},
    {"label": "Dec 2026", "ticker": "ZQZ26.CBT", "date": "2026-12-10", "month_code": "Z"},
]

RATE_STEP = 0.25  # Fed moves in 25bp increments

# Month code map for ZQ (30-day fed funds) futures tickers.
_ZQ_MONTH_CODES = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
                   7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}


def _generate_fomc_schedule(year: int) -> list:
    """
    FIX (2026-07-06): FOMC_MEETINGS_2026 was hardcoded, so on 2027-01-01 FedWatch
    would silently return 'No remaining FOMC meetings' and disappear from Agent 1's
    context forever. This generates an APPROXIMATE schedule for any year (the Fed
    holds ~8 meetings/yr, one roughly every 6-7 weeks) so FedWatch degrades
    gracefully instead of vanishing. Update FOMC_MEETINGS_<year> with the real
    published dates when the Fed announces them for best accuracy.
    """
    import calendar
    # Approximate meeting months (Jan, Mar, May, Jun, Jul, Sep, Oct, Dec) mirror
    # the historical 8-meeting cadence. Day ~mid/late month; exact day not critical
    # for front-month ZQ contract selection (we key off the month contract).
    approx = [(1, 28), (3, 18), (5, 6), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9)]
    yy = str(year)[-2:]
    sched = []
    for month, day in approx:
        code = _ZQ_MONTH_CODES[month]
        sched.append({
            "label": f"{calendar.month_abbr[month]} {year}",
            "ticker": f"ZQ{code}{yy}.CBT",
            "date": f"{year}-{month:02d}-{day:02d}",
            "month_code": code,
            "approximate": True,
        })
    return sched


def get_fomc_meetings() -> list:
    """Return the FOMC schedule for the current + next year, auto-extending past
    the hardcoded 2026 list so FedWatch never silently disappears."""
    today = date.today()
    meetings = list(FOMC_MEETINGS_2026)
    # Extend forward for the current and next year if the hardcoded list is exhausted.
    for yr in (today.year, today.year + 1):
        if yr == 2026:
            continue  # already have the real 2026 dates
        if not any(str(yr) in m["label"] for m in meetings):
            meetings.extend(_generate_fomc_schedule(yr))
    return meetings


def _detect_current_rate() -> Dict:
    """
    Detect the current effective fed funds rate from the front-month ZQ contract.
    Returns {"rate": float, "target_range": str, "target_mid": float}
    """
    try:
        data = yf.download("ZQ=F", period="5d", progress=False)
        if data.empty:
            return {"error": "ZQ=F front month: no data"}
        
        price = float(data["Close"].iloc[-1].item())
        effr = round(100 - price, 4)
        
        # Round to nearest target range (25bp increments)
        # Target range is usually 25bp wide, e.g., 3.50-3.75%
        lower = round(effr * 4 - 0.5) / 4  # Round down to nearest 25bp
        upper = lower + 0.25
        mid = (lower + upper) / 2
        
        return {
            "effr": effr,
            "target_lower": lower,
            "target_upper": upper,
            "target_mid": mid,
            "target_range": f"{lower:.2f}%-{upper:.2f}%",
            "zq_front_price": price,
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_fedwatch() -> Dict:
    """
    Fetch FedWatch-style rate probabilities from Fed Funds futures.
    
    Returns structured data with:
    - Current rate detection
    - Per-meeting implied rates and cut/hike probabilities
    - Next meeting focus with detailed probability breakdown
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "source": "fed_funds_futures_ZQ_yfinance",
        "current_rate": {},
        "meetings": [],
        "summary": {},
    }
    
    # Step 1: Detect current rate
    current = _detect_current_rate()
    result["current_rate"] = current
    
    if "error" in current:
        result["error"] = f"Cannot detect current rate: {current['error']}"
        return result
    
    current_mid = current["target_mid"]
    
    # Step 2: Get future meeting month contracts
    today = date.today()
    # FIX (2026-07-06): use the auto-extending schedule so FedWatch survives past 2026.
    all_meetings = get_fomc_meetings()
    future_meetings = [m for m in all_meetings
                       if date.fromisoformat(m["date"]) > today]

    if not future_meetings:
        result["error"] = "No remaining FOMC meetings in schedule"
        return result
    if any(m.get("approximate") for m in future_meetings):
        result["schedule_note"] = ("Using APPROXIMATE FOMC dates (hardcoded schedule "
                                   "exhausted — update FOMC_MEETINGS_<year> with real dates).")
    
    # Fetch all tickers at once
    tickers = [m["ticker"] for m in future_meetings]
    try:
        if len(tickers) == 1:
            data = yf.download(tickers[0], period="5d", progress=False)
            # Wrap single ticker data to match multi-ticker format
            prices = {}
            if not data.empty:
                prices[tickers[0]] = float(data["Close"].iloc[-1].item())
        else:
            data = yf.download(tickers, period="5d", progress=False)
            prices = {}
            for t in tickers:
                try:
                    col = data["Close"][t].dropna()
                    if not col.empty:
                        prices[t] = float(col.iloc[-1].item())
                except Exception:
                    pass
    except Exception as e:
        result["error"] = f"Futures download failed: {e}"
        return result
    
    # Step 3: Calculate probabilities for each meeting
    prev_implied = current["effr"]  # Start from current effective rate
    
    for meeting in future_meetings:
        ticker = meeting["ticker"]
        meeting_data = {
            "label": meeting["label"],
            "date": meeting["date"],
            "ticker": ticker,
        }
        
        if ticker not in prices:
            meeting_data["error"] = "no data"
            result["meetings"].append(meeting_data)
            continue
        
        price = prices[ticker]
        implied_rate = round(100 - price, 4)
        
        # Cumulative change from current rate
        cum_change = current_mid - implied_rate
        cum_cuts = cum_change / RATE_STEP
        
        # Meeting-specific change (vs previous meeting's implied rate)
        meeting_change = prev_implied - implied_rate
        meeting_cuts = meeting_change / RATE_STEP
        
        # Probability breakdown for this specific meeting
        # If meeting_cuts = 0.7, that's 70% chance of a 25bp cut at THIS meeting
        if meeting_cuts >= 0:
            prob_cut = min(100, meeting_cuts * 100)
            prob_hold = max(0, 100 - prob_cut)
            prob_hike = 0
            action = "CUT" if prob_cut > 50 else "HOLD"
        else:
            prob_cut = 0
            prob_hike = min(100, abs(meeting_cuts) * 100)
            prob_hold = max(0, 100 - prob_hike)
            action = "HIKE" if prob_hike > 50 else "HOLD"
        
        meeting_data.update({
            "zq_price": round(price, 4),
            "implied_rate": implied_rate,
            "cum_cuts_from_current": round(cum_cuts, 2),
            "meeting_specific_cut_prob": round(prob_cut, 1),
            "meeting_specific_hold_prob": round(prob_hold, 1),
            "meeting_specific_hike_prob": round(prob_hike, 1),
            "expected_action": action,
        })
        
        result["meetings"].append(meeting_data)
        prev_implied = implied_rate
    
    # Step 4: Summary
    next_meeting = result["meetings"][0] if result["meetings"] else None
    if next_meeting and "error" not in next_meeting:
        last_meeting = result["meetings"][-1] if len(result["meetings"]) > 1 else next_meeting
        
        total_cuts_by_year_end = last_meeting.get("cum_cuts_from_current", 0)
        
        result["summary"] = {
            "next_meeting": next_meeting["label"],
            "next_meeting_date": next_meeting["date"],
            "next_meeting_action": next_meeting["expected_action"],
            "next_meeting_cut_prob": next_meeting.get("meeting_specific_cut_prob", 0),
            "total_cuts_priced_by_year_end": round(total_cuts_by_year_end, 1),
            "implied_year_end_rate": last_meeting.get("implied_rate", "?"),
        }
    
    return result


def format_fedwatch_for_prompt(data: Dict) -> str:
    """Format FedWatch data for Agent 1's prompt."""
    if not data or "error" in data:
        return f"FEDWATCH DATA: {data.get('error', 'NOT AVAILABLE')}"
    
    cr = data.get("current_rate", {})
    summary = data.get("summary", {})
    meetings = data.get("meetings", [])
    
    lines = [
        "=" * 55,
        "FED FUNDS FUTURES — RATE EXPECTATIONS (FedWatch-style)",
        f"Calculated: {data.get('timestamp', 'unknown')}",
        "=" * 55,
    ]
    
    # Current rate
    if cr and "error" not in cr:
        lines.append(f"\nCURRENT FED FUNDS RATE:")
        lines.append(f"  Target Range: {cr.get('target_range', '?')}")
        lines.append(f"  Effective Rate (from ZQ front): {cr.get('effr', '?')}%")
    
    # Next meeting focus
    if summary:
        lines.append(f"\nNEXT FOMC MEETING: {summary.get('next_meeting', '?')} ({summary.get('next_meeting_date', '?')})")
        cut_prob = summary.get("next_meeting_cut_prob", 0)
        action = summary.get("next_meeting_action", "?")
        
        if action == "CUT":
            lines.append(f"  Market Expects: CUT ({cut_prob}% probability)")
        elif action == "HIKE":
            lines.append(f"  Market Expects: HIKE")
        else:
            lines.append(f"  Market Expects: HOLD (cut prob only {cut_prob}%)")
        
        total_cuts = summary.get("total_cuts_priced_by_year_end", 0)
        ye_rate = summary.get("implied_year_end_rate", "?")
        lines.append(f"\n  Cuts priced through year-end: {total_cuts}")
        lines.append(f"  Implied year-end rate: {ye_rate}%")
        
        # Interpretation
        if total_cuts >= 3:
            lines.append(f"  → Market pricing AGGRESSIVE easing — dovish Fed outlook")
        elif total_cuts >= 1.5:
            lines.append(f"  → Market pricing MODERATE easing — gradual cut cycle")
        elif total_cuts >= 0.5:
            lines.append(f"  → Market pricing MILD easing — one more cut likely")
        elif total_cuts > -0.5:
            lines.append(f"  → Market pricing HOLD — no significant rate changes expected")
        else:
            lines.append(f"  → Market pricing TIGHTENING — hawkish surprise risk")
    
    # Meeting-by-meeting table
    if meetings:
        lines.append(f"\nMEETING-BY-MEETING EXPECTATIONS:")
        for m in meetings:
            if "error" in m:
                lines.append(f"  {m['label']}: DATA UNAVAILABLE")
                continue
            lines.append(
                f"  {m['label']:10s} | Implied: {m['implied_rate']:.3f}% | "
                f"Cut: {m.get('meeting_specific_cut_prob', 0):5.1f}% | "
                f"Hold: {m.get('meeting_specific_hold_prob', 0):5.1f}% | "
                f"Cum cuts: {m.get('cum_cuts_from_current', 0):+.1f}"
            )
    
    return "\n".join(lines)


def save_fedwatch(data: Dict, path: str = "output/fedwatch.json"):
    """Save FedWatch data to output file."""
    os.makedirs(os.path.dirname(path) or "output", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[FedWatch] Data saved to {path}")


def load_fedwatch(path: str = "output/fedwatch.json") -> Optional[Dict]:
    """Load FedWatch data from file."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    data = fetch_fedwatch()
    save_fedwatch(data)
    print(format_fedwatch_for_prompt(data))
```

================================================================================
FILE: flash_crash_daemon.py
================================================================================
```python
"""
Flash-Crash Daemon — Lightweight intraday safety net (NO LLM)
Runs every 5-10 minutes during market hours.

Checks (every ~7 min during market hours):
  1. SPY intraday drop > 2.5% AND VIX spike > 30% → market-wide defensive protocol
  2. Individual position down > 5% intraday → tighten that stop to breakeven
  3. Trailing-profit ladder (EVERY cycle) → same breakeven/+50%/+75% math as the
     3:30 PM Agent 5 monitor. Ratchets stops UP as winners run and locks in gains
     (atomic CLOSE) the moment price pulls back into the laddered stop — closing
     the "gave back gains between monitor windows" gap. Reuses
     agent5_position_monitor.calculate_trailing_stops for identical math + shared HWM state.

Defensive protocol:
  - Profitable positions → tighten stop to breakeven (entry price)
  - Losing positions → close immediately
  - Log all actions to output/daemon_log.json
  - Save alert to output/daemon_alert.json for Agent 5 visibility

Usage:
  python3 flash_crash_daemon.py
"""
import json
import os
import sys
from datetime import datetime, time

import pytz
# yfinance removed — all data routed through DataProvider

from broker_factory import get_broker

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Thresholds (tightened to avoid triggering on normal volatility)
# Market-wide defensive protocol requires BOTH SPY drop AND VIX spike (AND logic)
SPY_DROP_THRESHOLD = -0.025       # -2.5% from today's open
VIX_SPIKE_THRESHOLD = 0.30        # +30% from today's open
POSITION_DROP_THRESHOLD = -0.05   # -5% intraday for individual positions


def is_market_hours() -> bool:
    """Check if current time is within regular market hours (9:30-16:00 ET, Mon-Fri)."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(et)

    # Skip weekends (Monday=0, Sunday=6)
    if now.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)

    return market_open <= now.time() <= market_close


def get_intraday_change(ticker: str) -> dict:
    """
    Fetch intraday data for a ticker and compute change from today's open.
    Uses DataProvider for SPY (bars) and VIX (index). Falls back to yfinance.
    Returns {"open": float, "current": float, "change_pct": float} or {"error": str}.
    """
    from data_provider import get_provider, DataUnavailable

    # VIX/SPX — route through get_index for proper fallback chain
    clean = ticker.upper().replace("^", "")
    if clean in ("VIX", "SPX"):
        try:
            dp = get_provider()
            idx = dp.get_index(clean)
            current = idx["value"]
            # For intraday open we still need bars — try SPY as proxy for SPX
            proxy = "SPY" if clean == "SPX" else "VIXY"
            try:
                bars = dp.get_bars(proxy, lookback_days=1, timespan="minute")
                if bars is not None and not bars.empty:
                    open_price = float(bars["Open"].iloc[0])
                else:
                    open_price = current  # Can't get open, use current (0% change)
            except (DataUnavailable, Exception):
                open_price = current

            if open_price <= 0:
                return {"error": f"Invalid open price for {ticker}"}

            change_pct = (current - open_price) / open_price
            return {
                "open": round(open_price, 2),
                "current": round(current, 2),
                "change_pct": round(change_pct, 4),
                "source": idx.get("source", "unknown"),
                "is_proxy": idx.get("is_proxy", False),
            }
        except DataUnavailable as e:
            return {"error": f"DataProvider: {e}"}
        except Exception as e:
            return {"error": str(e)}

    # Regular tickers (SPY, individual positions) — use DataProvider bars
    try:
        dp = get_provider()
        bars = dp.get_bars(ticker, lookback_days=1, timespan="minute")
        if bars is None or bars.empty:
            return {"error": f"No intraday data for {ticker}"}

        open_price = float(bars["Open"].iloc[0])
        current_price = float(bars["Close"].iloc[-1])

        if open_price <= 0:
            return {"error": f"Invalid open price for {ticker}"}

        change_pct = (current_price - open_price) / open_price
        return {
            "open": round(open_price, 2),
            "current": round(current_price, 2),
            "change_pct": round(change_pct, 4),
        }
    except DataUnavailable as e:
        return {"error": f"DataProvider: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _save_json(filepath: str, data: dict):
    """Write JSON to file, creating output dir if needed."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _append_daemon_log(entry: dict):
    """Append an entry to the daemon log (keeps history)."""
    log_path = os.path.join(OUTPUT_DIR, "daemon_log.json")
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = [logs]
        except (json.JSONDecodeError, Exception):
            logs = []
    logs.append(entry)
    # Keep last 500 entries to avoid unbounded growth
    logs = logs[-500:]
    _save_json(log_path, logs)


def _get_current_stop_price(broker, ticker: str) -> float:
    """Get the current stop-loss price for a ticker from open orders (broker-agnostic)."""
    try:
        orders = broker.get_orders_today()
        for o in orders:
            if (o.get("ticker") == ticker
                and o.get("status", "").lower() in ("open", "queued", "confirmed")
                and (o.get("order_type", "").lower() == "stop" or o.get("stop_price"))):
                return float(o["stop_price"])
    except Exception:
        pass
    return None


def execute_defensive_protocol(broker, trigger_reason: str, positions: list) -> list:
    """
    Execute defensive protocol on all positions using the execution engine.
    - Profitable positions: tighten stop to breakeven via engine
    - Losing positions: atomic liquidation via engine
    Returns list of actions taken.
    """
    from execution_engine import ExecutionEngine
    engine = ExecutionEngine(broker=broker)
    actions = []

    for pos in positions:
        ticker = pos["ticker"]
        entry_price = pos["avg_entry_price"]
        unrealized_pl = pos["unrealized_pl"]

        if unrealized_pl < 0:
            # Losing — atomic liquidate (cancel resting orders → wait → market sell)
            result = engine.atomic_liquidate(ticker, reason=trigger_reason)
            actions.append({"ticker": ticker, "action": "LIQUIDATED", "result": result})
            print(f"  [Daemon] {ticker}: Losing (${unrealized_pl:.2f}) → ATOMICALLY CLOSED")
        else:
            # Profitable — tighten stop to breakeven, but NEVER widen
            current_stop = _get_current_stop_price(broker, ticker)
            if current_stop and current_stop > entry_price:
                actions.append({
                    "ticker": ticker,
                    "action": "SKIP",
                    "note": f"Stop already at ${current_stop:.2f} > entry ${entry_price:.2f} — not widening",
                })
                print(f"  [Daemon] {ticker}: Stop already tight at ${current_stop:.2f} — skipping")
                continue

            # Atomic trailing stop: cancel old → wait for clearinghouse → place new
            success = engine.update_trailing_stop(ticker, entry_price)
            if success:
                actions.append({
                    "ticker": ticker,
                    "action": "TIGHTEN_STOP_BREAKEVEN",
                    "new_stop": entry_price,
                })
                print(f"  [Daemon] {ticker}: Profitable (+${unrealized_pl:.2f}) \u2192 stop moved to ${entry_price:.2f}")
            else:
                actions.append({"ticker": ticker, "action": "TIGHTEN_STOP_FAILED"})
                print(f"  [Daemon] {ticker}: TIGHTEN FAILED \u2014 daemon will retry via update_stop fallback")
                engine.update_stop(ticker, entry_price, reason=f"flash_crash_{trigger_reason}_fallback")

    return actions


def tighten_individual_stop(broker, pos: dict) -> dict:
    """Tighten a single position's stop to breakeven when it's down >5% intraday."""
    from execution_engine import ExecutionEngine
    engine = ExecutionEngine(broker=broker)

    ticker = pos["ticker"]
    entry_price = pos["avg_entry_price"]
    current_price = pos["current_price"]

    # Check if stop is already tighter than entry price — don't widen it
    current_stop = _get_current_stop_price(broker, ticker)
    if current_stop and current_stop > entry_price:
        action = {
            "ticker": ticker,
            "action": "SKIP",
            "note": f"Stop already at ${current_stop:.2f} > entry ${entry_price:.2f} — not widening",
        }
        print(f"  [Daemon] {ticker}: Stop already at ${current_stop:.2f} > entry — skipping")
        return action

    # GUARD: If current price is already below entry, close via atomic liquidation
    if current_price < entry_price:
        result = engine.atomic_liquidate(ticker, reason="price_below_entry_during_tighten")
        action = {
            "ticker": ticker,
            "action": "CLOSE_BELOW_ENTRY",
            "entry_price": entry_price,
            "current_price": current_price,
            "result": result,
            "note": f"Price ${current_price:.2f} < entry ${entry_price:.2f} — atomically closed",
        }
        print(f"  [Daemon] {ticker}: Price ${current_price:.2f} < entry ${entry_price:.2f} → ATOMICALLY CLOSED")
        return action

    # Atomic trailing stop: cancel old → wait for clearinghouse → place new
    success = engine.update_trailing_stop(ticker, entry_price)
    if success:
        action = {
            "ticker": ticker,
            "action": "INDIVIDUAL_STOP_TIGHTEN",
            "entry_price": entry_price,
            "note": f"Position down >5% intraday — stop moved to breakeven (${entry_price:.2f})",
            "status": "executed",
        }
        print(f"  [Daemon] {ticker}: Down >5% intraday \u2192 stop tightened to ${entry_price:.2f}")
    else:
        # Fallback to async update_stop (daemon will place when it can)
        engine.update_stop(ticker, entry_price, reason="individual_stop_tighten_fallback")
        action = {
            "ticker": ticker,
            "action": "INDIVIDUAL_STOP_TIGHTEN",
            "entry_price": entry_price,
            "note": f"Atomic tighten failed \u2014 daemon will retry",
            "status": "deferred",
        }
        print(f"  [Daemon] {ticker}: Atomic tighten failed \u2014 deferred to daemon")
    return action


def _get_db_stop_price(ticker: str) -> float:
    """
    Read the authoritative target stop from the execution ledger DB
    (active_trades.target_stop_price). This is the source of truth the execution
    engine uses — NOT resting broker orders — so the ladder honors 'never widen'
    correctly and never fights the execution daemon's stop management.
    Returns the stop price, or 0 if no active trade / unavailable.
    """
    try:
        import sqlite3
        from execution_engine import DB_PATH
        with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
            row = conn.execute(
                "SELECT target_stop_price FROM active_trades WHERE ticker = ? AND closed_at IS NULL",
                (ticker,),
            ).fetchone()
            if row and row[0]:
                return float(row[0])
    except Exception:
        pass
    return 0.0


def run_trailing_ladder(broker, positions: list) -> list:
    """
    Intraday profit-locking. Runs the SAME trailing-stop ladder as the 3:30 PM
    Agent 5 monitor (breakeven / +50% / +75%) so a winner that spikes and bleeds
    back gets its stop ratcheted up between the fixed monitor windows.

    Reuses agent5_position_monitor.calculate_trailing_stops for identical math
    (incl. shared high-water-mark state on disk). NO LLM.

    For each position:
      - If price <= the ladder stop  -> atomic CLOSE (lock the gain / cut)
      - Else if ladder stop > current resting stop -> ratchet stop UP (never widen)
      - Else -> no-op
    Returns list of actions taken.
    """
    from agent5_position_monitor import (
        calculate_trailing_stops,
        _load_portfolio_state,
        _save_portfolio_state,
    )
    from execution_engine import ExecutionEngine

    if not positions:
        return []

    # Snapshot HWM state BEFORE the ladder so we can restore any open-position
    # keys it prunes. calculate_trailing_stops() deletes state for tickers not in
    # the list it's given; if the broker ever returns a partial/empty list, that
    # would wipe live floors. We merge those keys back after.
    hwm_before = dict(_load_portfolio_state())

    # Adapt broker positions -> the shape calculate_trailing_stops expects.
    adapted = []
    snapshot = {}
    for pos in positions:
        ticker = pos["ticker"]
        current_price = pos.get("current_price")
        # Fall back to a fresh intraday quote if the broker didn't include price
        if current_price is None:
            q = get_intraday_change(ticker)
            current_price = q.get("current") if "error" not in q else None
        if current_price is None:
            continue
        # Authoritative stop = execution-ledger DB target, not resting broker order.
        db_stop = _get_db_stop_price(ticker)
        adapted.append({
            "ticker": ticker,
            "entry_price": pos.get("avg_entry_price", 0),
            "stop_loss": db_stop,
            "shares": pos.get("shares", pos.get("qty", 0)),
        })
        snapshot[ticker] = {"current_price": current_price}

    if not adapted:
        return []

    laddered = calculate_trailing_stops(adapted, snapshot)

    # Restore HWM state for any currently-open ticker the ladder pruned
    # (defensive against partial broker reads).
    open_tickers = {p["ticker"] for p in positions}
    hwm_after = _load_portfolio_state()
    restored = False
    for t, v in hwm_before.items():
        if t in open_tickers and t not in hwm_after:
            hwm_after[t] = v
            restored = True
    if restored:
        _save_portfolio_state(hwm_after)

    engine = ExecutionEngine(broker=broker)
    actions = []
    for r in laddered:
        ticker = r["ticker"]
        mech = r.get("mechanical_action", "HOLD")
        new_stop = r.get("new_stop", 0)
        resting_stop = _get_db_stop_price(ticker)
        pnl_pct = r.get("pnl_pct", 0)

        if mech == "CLOSE":
            # Price fell into the laddered stop -> lock it in atomically.
            result = engine.atomic_liquidate(
                ticker, reason=f"intraday_ladder_CLOSE (pnl {pnl_pct:.1f}%, stop ${new_stop})"
            )
            actions.append({
                "ticker": ticker,
                "action": "LADDER_CLOSE",
                "pnl_pct": pnl_pct,
                "stop": new_stop,
                "result": result,
            })
            print(f"  [Daemon] {ticker}: ladder CLOSE — price hit ${new_stop} (pnl {pnl_pct:.1f}%) → liquidated")
        elif new_stop and new_stop > resting_stop:
            # Ratchet the stop UP only (never widen).
            success = engine.update_trailing_stop(ticker, new_stop)
            if not success:
                engine.update_stop(ticker, new_stop, reason="intraday_ladder_trail_fallback")
            actions.append({
                "ticker": ticker,
                "action": "LADDER_TRAIL",
                "pnl_pct": pnl_pct,
                "old_stop": resting_stop,
                "new_stop": new_stop,
                "note": r.get("trailing_stop_note", ""),
            })
            print(f"  [Daemon] {ticker}: ladder trail — stop ${resting_stop} → ${new_stop} (pnl {pnl_pct:.1f}%)")

    return actions


def run_daemon():
    """
    Main daemon entry point. Checks market conditions and positions.
    If no triggers, exits silently. If triggers fire, executes defensive protocol.
    Also runs the intraday trailing-profit ladder every cycle (profit-locking).
    """
    # Check market hours
    if not is_market_hours():
        return  # Silent exit outside market hours

    triggers = []
    actions = []

    # --- Check SPY ---
    spy_data = get_intraday_change("SPY")
    if "error" not in spy_data:
        if spy_data["change_pct"] <= SPY_DROP_THRESHOLD:
            trigger = {
                "type": "SPY_DROP",
                "detail": f"SPY down {spy_data['change_pct']*100:.2f}% (threshold: {SPY_DROP_THRESHOLD*100:.1f}%)",
                "open": spy_data["open"],
                "current": spy_data["current"],
                "change_pct": spy_data["change_pct"],
            }
            triggers.append(trigger)
            print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
    else:
        print(f"[Daemon] Warning: Could not fetch SPY data — {spy_data['error']}")

    # --- Check VIX ---
    vix_data = get_intraday_change("^VIX")
    if "error" not in vix_data:
        # Widen threshold if using ETF proxy (tracking error vs spot VIX)
        effective_threshold = VIX_SPIKE_THRESHOLD
        if vix_data.get("is_proxy"):
            effective_threshold *= 1.25
            print(f"[Daemon] VIX via proxy — widened threshold to +{effective_threshold*100:.0f}%")

        if vix_data["change_pct"] >= effective_threshold:
            trigger = {
                "type": "VIX_SPIKE",
                "detail": f"VIX up {vix_data['change_pct']*100:.2f}% (threshold: +{effective_threshold*100:.0f}%)",
                "open": vix_data["open"],
                "current": vix_data["current"],
                "change_pct": vix_data["change_pct"],
                "source": vix_data.get("source", "unknown"),
            }
            triggers.append(trigger)
            print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
    else:
        # VIX blind — alert but still run per-position checks
        from safeguards import send_telegram
        send_telegram(f"⚠️ Flash crash daemon blind on VIX: {vix_data['error']} — running degraded (per-position checks only)")
        print(f"[Daemon] Warning: VIX BLIND — {vix_data['error']} — skipping market-wide trigger, running per-position checks")

    # --- Load positions ---
    try:
        broker = get_broker()
        positions = broker.get_positions()
    except Exception as e:
        print(f"[Daemon] ERROR: Could not connect to broker — {e}")
        return

    if not positions:
        if triggers:
            # Triggers fired but no positions to defend — just log
            alert = {
                "timestamp": datetime.now().isoformat(),
                "triggers": triggers,
                "actions": [],
                "note": "Triggers fired but no open positions",
            }
            _save_json(os.path.join(OUTPUT_DIR, "daemon_alert.json"), alert)
            _append_daemon_log(alert)
            print("[Daemon] Triggers fired but no positions to defend. Alert saved.")
        return  # Silent exit if no positions and no triggers

    # --- Check individual positions for >5% intraday drop ---
    for pos in positions:
        ticker = pos["ticker"]
        pos_data = get_intraday_change(ticker)
        if "error" not in pos_data:
            if pos_data["change_pct"] <= POSITION_DROP_THRESHOLD:
                trigger = {
                    "type": "POSITION_DROP",
                    "ticker": ticker,
                    "detail": f"{ticker} down {pos_data['change_pct']*100:.2f}% intraday (threshold: {POSITION_DROP_THRESHOLD*100:.0f}%)",
                    "change_pct": pos_data["change_pct"],
                }
                triggers.append(trigger)
                print(f"[Daemon] ⚠️ TRIGGER: {trigger['detail']}")
                # Tighten this specific position's stop to breakeven
                action = tighten_individual_stop(broker, pos)
                actions.append(action)

    # --- Intraday trailing-profit ladder (runs EVERY cycle, profit-locking) ---
    # Same breakeven/+50%/+75% math as the 3:30 PM Agent 5 monitor, so winners
    # that give back gains between the fixed monitor windows still get locked in.
    try:
        ladder_actions = run_trailing_ladder(broker, positions)
        if ladder_actions:
            actions.extend(ladder_actions)
            # Treat ladder activity as a logged event even without crash triggers.
            triggers.append({
                "type": "TRAILING_LADDER",
                "detail": f"Intraday ladder acted on {len(ladder_actions)} position(s)",
            })
    except Exception as le:
        print(f"[Daemon] Warning: trailing ladder failed — {le}")

    # --- If market-wide triggers fired, run full defensive protocol ---
    # Require BOTH SPY drop AND VIX spike to avoid triggering on normal noise.
    # A -2.5% SPY day with calm VIX is an orderly pullback, not a crash.
    spy_triggered = any(t["type"] == "SPY_DROP" for t in triggers)
    vix_triggered = any(t["type"] == "VIX_SPIKE" for t in triggers)

    if spy_triggered and vix_triggered:
        market_wide_triggers = [t for t in triggers if t["type"] in ("SPY_DROP", "VIX_SPIKE")]
        trigger_reasons = "; ".join(t["detail"] for t in market_wide_triggers)
        print(f"\n[Daemon] 🛡️ DEFENSIVE PROTOCOL ACTIVATED: {trigger_reasons}")
        defensive_actions = execute_defensive_protocol(broker, trigger_reasons, positions)
        actions.extend(defensive_actions)
    elif spy_triggered or vix_triggered:
        single_triggers = [t for t in triggers if t["type"] in ("SPY_DROP", "VIX_SPIKE")]
        for t in single_triggers:
            print(f"[Daemon] ⚠️ WARNING (no action): {t['detail']} — waiting for dual confirmation")

    # --- If any triggers fired, save outputs ---
    if triggers:
        timestamp = datetime.now().isoformat()

        alert = {
            "timestamp": timestamp,
            "triggers": triggers,
            "actions": actions,
            "positions_at_trigger": positions,
        }
        _save_json(os.path.join(OUTPUT_DIR, "daemon_alert.json"), alert)
        _append_daemon_log(alert)

        # Print summary
        print(f"\n{'='*40}")
        print(f"[Daemon] SUMMARY")
        print(f"  Triggers: {len(triggers)}")
        for t in triggers:
            print(f"    - {t['detail']}")
        print(f"  Actions: {len(actions)}")
        for a in actions:
            print(f"    - {a['ticker']}: {a['action']} ({a.get('status', 'n/a')})")
        print(f"{'='*40}")


if __name__ == "__main__":
    run_daemon()
```

================================================================================
FILE: intraday_trail.py
================================================================================
```python
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
```

================================================================================
FILE: itc_data.py
================================================================================
```python
"""
ITC (Into The Cryptoverse) Data Fetcher
Scrapes key macro and crypto risk indicators from app.intothecryptoverse.com

Indicators fetched (from dashboard snapshot):
1. Crypto Risk Summary (composite: Price + On-Chain + Social)
2. BTC/ETH/asset-level Risk Levels (0-1 scale, Ben Cowen's model)
3. Macro Recession Risk (Employment + National Income + Production)
4. BTC Dominance (with/without stablecoins)
5. Market Cap vs Trendline (log regression deviation %)
6. Unemployment Rate, M2 Supply, Consumer Confidence
7. Full asset table (crypto + tradfi with risk scores)

Data is scraped from the dashboard DOM via browser snapshot.
Requires an active browser session (login handled by Zuck).

Usage:
    Called by preflight.py's fetch_itc_data() which delegates to Zuck's browser.
    Data is saved to output/itc_data.json.
    Agent 1 receives it as supplementary macro context via format_itc_for_prompt().
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, Optional


def parse_itc_dashboard_snapshot(snapshot_text: str) -> Dict:
    """
    Parse ITC dashboard data from a browser snapshot (aria tree text).
    
    The compact snapshot format contains:
    - Grid rows with asset data (name, price, changes, risk)
    - Crypto Risk Indicators widget with summary gauge
    - Macro Recession Risk widget
    - Dominance widget
    - Log Regression widget
    - Macro Calendar entries
    
    Returns a structured dict of all extractable indicators.
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "source": "intothecryptoverse.com/dashboard",
        "crypto_risk": {},
        "macro_risk": {},
        "dominance": {},
        "valuation": {},
        "macro_calendar": {},
        "assets": [],
    }

    # --- Extract favorite assets from grid rows ---
    # Compact format: row "Name (TICKER) $price change% change% mcap risk ..."
    asset_pattern = re.compile(
        r'row "(?:[\w\s.]+logo\s+)?([\w\s.&\'/]+?)\s*\((\w+)\)\s+'
        r'\$([\d,.]+)\s+'
        r'(-?[\d.]+%|-)\s+'
        r'(-?[\d.]+%|-)\s+'
        r'([\d.]+[TBMK]?|-)\s+'
        r'([\d.]+)'
    )
    
    for match in asset_pattern.finditer(snapshot_text):
        name, ticker, price, change_24h, change_7d, mcap, risk = match.groups()
        asset = {
            "name": name.strip(),
            "ticker": ticker,
            "price": price.replace(",", ""),
            "change_24h": change_24h,
            "change_7d": change_7d,
            "market_cap": mcap,
            "fiat_risk": float(risk),
        }
        result["assets"].append(asset)
        
        # Capture key asset risks
        if ticker == "BTC":
            result["crypto_risk"]["btc_risk"] = float(risk)
            result["crypto_risk"]["btc_price"] = price.replace(",", "")
        elif ticker == "ETH":
            result["crypto_risk"]["eth_risk"] = float(risk)
            result["crypto_risk"]["eth_price"] = price.replace(",", "")
        elif ticker == "SP500":
            result["macro_risk"]["sp500_risk"] = float(risk)
            result["macro_risk"]["sp500_price"] = price.replace(",", "")
        elif ticker == "DXY":
            result["macro_risk"]["dxy_risk"] = float(risk)
            result["macro_risk"]["dxy_value"] = price.replace(",", "")
        elif ticker == "GOLD":
            result["macro_risk"]["gold_risk"] = float(risk)
            result["macro_risk"]["gold_price"] = price.replace(",", "")

    # --- Extract Crypto Risk Summary from img alt text ---
    # Format: "0.239 0.239 0.239 ... Summary: 0.239 Price: 0.200 On-Chain: 0.303 Social: 0.213"
    crypto_risk_pattern = re.compile(
        r'Summary:\s*([\d.]+)\s+Price:\s*([\d.]+)\s+On-Chain:\s*([\d.]+)\s+Social:\s*([\d.]+)'
    )
    crypto_match = crypto_risk_pattern.search(snapshot_text)
    if crypto_match:
        result["crypto_risk"]["summary"] = float(crypto_match.group(1))
        result["crypto_risk"]["price_risk"] = float(crypto_match.group(2))
        result["crypto_risk"]["onchain_risk"] = float(crypto_match.group(3))
        result["crypto_risk"]["social_risk"] = float(crypto_match.group(4))

    # --- Extract Macro Recession Risk from img alt text ---
    # Format: "0.008 0.008 ... Employment: 0.008 National Income And Product: 0.049 Production And Business: 0.008"
    recession_pattern = re.compile(
        r'Employment:\s*([\d.]+)\s+National Income And Product:\s*([\d.]+)\s+Production And Business:\s*([\d.]+)'
    )
    recession_match = recession_pattern.search(snapshot_text)
    if recession_match:
        result["macro_risk"]["recession_employment"] = float(recession_match.group(1))
        result["macro_risk"]["recession_income"] = float(recession_match.group(2))
        result["macro_risk"]["recession_production"] = float(recession_match.group(3))
        # Composite is the max of the three (or the first number in the img text)
        components = [float(recession_match.group(i)) for i in (1, 2, 3)]
        result["macro_risk"]["recession_composite"] = max(components)

    # Also try to extract the headline recession number
    recession_headline = re.compile(r'Macro Recession Risk.*?(\d+\.\d+)', re.DOTALL)
    rh_match = recession_headline.search(snapshot_text)
    if rh_match:
        result["macro_risk"]["recession_risk"] = float(rh_match.group(1))

    # --- Extract BTC Dominance ---
    dom_pattern = re.compile(
        r'With Stables:\s*([\d.]+)%.*?Without Stables:\s*([\d.]+)%'
    )
    dom_match = dom_pattern.search(snapshot_text)
    if dom_match:
        result["dominance"]["btc_with_stables"] = float(dom_match.group(1))
        result["dominance"]["btc_without_stables"] = float(dom_match.group(2))

    # --- Extract Market Cap Log Regression ---
    val_pattern = re.compile(
        r'CMC:\s*([\d.]+[TBMK]?).*?Trend:\s*([\d.]+[TBMK]?).*?(?:Under|Over)valuation:\s*(-?[\d.]+)%'
    )
    val_match = val_pattern.search(snapshot_text)
    if val_match:
        result["valuation"]["cmc"] = val_match.group(1)
        result["valuation"]["trend"] = val_match.group(2)
        result["valuation"]["deviation_pct"] = float(val_match.group(3))

    # --- Extract Current BTC Risk from Color-Coded chart ---
    btc_risk_pattern = re.compile(r'Current risk:\s*([\d.]+)')
    btc_risk_match = btc_risk_pattern.search(snapshot_text)
    if btc_risk_match:
        result["crypto_risk"]["btc_risk_colorcoded"] = float(btc_risk_match.group(1))

    # --- Extract Unemployment Rate ---
    unemp_pattern = re.compile(r'Latest Value:\s*([\d.]+)%\s*\((\d+/\d+/\d+)\)')
    unemp_match = unemp_pattern.search(snapshot_text)
    if unemp_match:
        result["macro_risk"]["unemployment_rate"] = float(unemp_match.group(1))
        result["macro_risk"]["unemployment_date"] = unemp_match.group(2)

    # --- Extract Macro Calendar entries ---
    # M2 Money Supply
    m2_pattern = re.compile(r'M2 Money Supply.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    m2_match = m2_pattern.search(snapshot_text)
    if m2_match:
        result["macro_calendar"]["m2_supply"] = "$" + m2_match.group(1)

    # M1 Money Supply
    m1_pattern = re.compile(r'M1 Money Supply.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    m1_match = m1_pattern.search(snapshot_text)
    if m1_match:
        result["macro_calendar"]["m1_supply"] = "$" + m1_match.group(1)

    # Consumer Confidence
    cc_pattern = re.compile(r'Consumer Confidence.*?Result:\s*([\d.]+)', re.DOTALL)
    cc_match = cc_pattern.search(snapshot_text)
    if cc_match:
        result["macro_calendar"]["consumer_confidence"] = float(cc_match.group(1))

    # Retail Money Market Funds
    rmm_pattern = re.compile(r'Retail Money Market Funds.*?Result:\s*\$([\d.]+[TBMK]?)', re.DOTALL)
    rmm_match = rmm_pattern.search(snapshot_text)
    if rmm_match:
        result["macro_calendar"]["retail_money_market"] = "$" + rmm_match.group(1)

    return result


def format_itc_for_prompt(data: Dict) -> str:
    """
    Format ITC data into a clean text block for Agent 1's prompt.
    
    This goes alongside the Assembly data and FRED macro data
    as supplementary context for regime classification.
    """
    if not data or (not data.get("crypto_risk") and not data.get("macro_risk")):
        return "ITC DATA: NOT AVAILABLE"

    lines = [
        "=" * 55,
        f"ITC (INTO THE CRYPTOVERSE) DATA",
        f"Scraped: {data.get('timestamp', 'unknown')}",
        "=" * 55,
    ]

    # Crypto Risk Composite
    cr = data.get("crypto_risk", {})
    if cr:
        lines.append("")
        lines.append("CRYPTO RISK INDICATORS (0 = cycle floor, 1 = cycle peak):")
        if "summary" in cr:
            risk_val = cr["summary"]
            if risk_val < 0.25:
                zone = "ACCUMULATION ZONE — historically best risk/reward"
            elif risk_val < 0.45:
                zone = "LOW RISK — favorable entry conditions"
            elif risk_val < 0.65:
                zone = "MODERATE RISK — mid-cycle"
            elif risk_val < 0.80:
                zone = "ELEVATED RISK — late cycle, trim exposure"
            else:
                zone = "EXTREME RISK — historically near cycle tops"
            lines.append(f"  Summary Risk: {risk_val} → {zone}")
        if "price_risk" in cr:
            lines.append(f"  Price Component: {cr['price_risk']}")
        if "onchain_risk" in cr:
            lines.append(f"  On-Chain Component: {cr['onchain_risk']}")
        if "social_risk" in cr:
            lines.append(f"  Social Component: {cr['social_risk']}")
        if "btc_risk" in cr:
            lines.append(f"  BTC Risk: {cr['btc_risk']}  (price: ${cr.get('btc_price', '?')})")
        if "eth_risk" in cr:
            lines.append(f"  ETH Risk: {cr['eth_risk']}  (price: ${cr.get('eth_price', '?')})")

    # Macro Recession Risk
    mr = data.get("macro_risk", {})
    if mr:
        lines.append("")
        lines.append("MACRO RECESSION RISK (ITC composite model, 0-1 scale):")
        rc = mr.get("recession_composite") or mr.get("recession_risk")
        if rc is not None:
            if rc < 0.05:
                rlabel = "VERY LOW — expansion"
            elif rc < 0.15:
                rlabel = "LOW — no imminent recession signals"
            elif rc < 0.35:
                rlabel = "MODERATE — watch for deterioration"
            elif rc < 0.60:
                rlabel = "ELEVATED — recession becoming probable"
            else:
                rlabel = "HIGH — recession likely underway or imminent"
            lines.append(f"  Recession Risk: {rc} → {rlabel}")
        if "recession_employment" in mr:
            lines.append(f"  Employment sub: {mr['recession_employment']}")
        if "recession_income" in mr:
            lines.append(f"  National Income sub: {mr['recession_income']}")
        if "recession_production" in mr:
            lines.append(f"  Production sub: {mr['recession_production']}")
        if "unemployment_rate" in mr:
            lines.append(f"  Unemployment Rate: {mr['unemployment_rate']}% (as of {mr.get('unemployment_date', '?')})")
        if "sp500_risk" in mr:
            lines.append(f"  S&P 500 Risk: {mr['sp500_risk']}  (price: ${mr.get('sp500_price', '?')})")
        if "dxy_risk" in mr:
            lines.append(f"  DXY Risk: {mr['dxy_risk']}  (value: {mr.get('dxy_value', '?')})")
        if "gold_risk" in mr:
            lines.append(f"  Gold Risk: {mr['gold_risk']}  (price: ${mr.get('gold_price', '?')})")

    # Dominance
    dom = data.get("dominance", {})
    if dom:
        lines.append("")
        lines.append("BTC DOMINANCE (risk rotation signal):")
        if "btc_with_stables" in dom:
            lines.append(f"  With Stablecoins: {dom['btc_with_stables']}%")
        if "btc_without_stables" in dom:
            lines.append(f"  Without Stablecoins: {dom['btc_without_stables']}%")
        dom_val = dom.get("btc_with_stables") or dom.get("btc_without_stables")
        if dom_val:
            if dom_val > 60:
                lines.append("  Interpretation: HIGH dominance → flight to quality within crypto, risk-off signal")
            elif dom_val > 50:
                lines.append("  Interpretation: MODERATE dominance → BTC leading but alts participating")
            elif dom_val > 40:
                lines.append("  Interpretation: LOW dominance → alt season emerging, risk appetite high")
            else:
                lines.append("  Interpretation: VERY LOW dominance → deep alt season, euphoria risk")

    # Valuation
    val = data.get("valuation", {})
    if val:
        lines.append("")
        lines.append("CRYPTO MARKET CAP vs LOG REGRESSION TRENDLINE:")
        if "cmc" in val:
            lines.append(f"  Current Market Cap: ${val['cmc']}")
        if "trend" in val:
            lines.append(f"  Fair Value Trend: ${val['trend']}")
        if "deviation_pct" in val:
            dev = val["deviation_pct"]
            if dev < -40:
                dlabel = "DEEP VALUE — major undervaluation vs historical trend"
            elif dev < -20:
                dlabel = "UNDERVALUED — below fair value trend"
            elif dev < 0:
                dlabel = "SLIGHTLY BELOW trend"
            elif dev < 20:
                dlabel = "SLIGHTLY ABOVE trend"
            elif dev < 50:
                dlabel = "OVERVALUED — above fair value trend"
            else:
                dlabel = "EXTREME OVERVALUATION — historically unsustainable"
            lines.append(f"  Deviation: {dev}% → {dlabel}")

    # Macro Calendar highlights
    mc = data.get("macro_calendar", {})
    if mc:
        lines.append("")
        lines.append("RECENT MACRO CALENDAR (from ITC):")
        for key, val in mc.items():
            label = key.replace("_", " ").title()
            lines.append(f"  {label}: {val}")

    # Asset risk summary table
    assets = data.get("assets", [])
    if assets:
        lines.append("")
        lines.append(f"ASSET RISK TABLE ({len(assets)} assets tracked):")
        # Group by type
        crypto = [a for a in assets if a["ticker"] in 
                  {"BTC","ETH","BNB","XRP","SOL","TRX","DOGE","ADA","XMR","LINK"}]
        tradfi = [a for a in assets if a["ticker"] in 
                  {"SP500","DXY","GOLD","SILVER","AAPL","NFLX","MSTR","TSLA"}]
        
        if crypto:
            lines.append("  Crypto:")
            for a in crypto:
                lines.append(
                    f"    {a['ticker']:6s} ${a['price']:>10s} | 24h: {a['change_24h']:>7s} | "
                    f"7d: {a['change_7d']:>7s} | Risk: {a['fiat_risk']}"
                )
        if tradfi:
            lines.append("  TradFi:")
            for a in tradfi:
                lines.append(
                    f"    {a['ticker']:6s} ${a['price']:>10s} | 24h: {a['change_24h']:>7s} | "
                    f"7d: {a['change_7d']:>7s} | Risk: {a['fiat_risk']}"
                )

    return "\n".join(lines)


def load_itc_data(path: str = "output/itc_data.json") -> Optional[Dict]:
    """Load pre-scraped ITC data from output file."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[ITC] Failed to load data: {e}")
        return None


def save_itc_data(data: Dict, path: str = "output/itc_data.json"):
    """Save ITC data to output file."""
    os.makedirs(os.path.dirname(path) or "output", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[ITC] Data saved to {path}")


def is_itc_stale(path: str = "output/itc_data.json", max_hours: float = 18) -> bool:
    """Check if ITC data file is stale (older than max_hours)."""
    if not os.path.exists(path):
        return True
    try:
        with open(path) as f:
            data = json.load(f)
        ts = data.get("timestamp", "")
        if not ts:
            return True
        data_time = datetime.fromisoformat(ts.split("+")[0])
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        print(f"[ITC] Data age: {age_hours:.1f}h (stale threshold: {max_hours}h)")
        return age_hours > max_hours
    except Exception:
        return True


if __name__ == "__main__":
    # Test: load and display
    data = load_itc_data()
    if data:
        print(format_itc_for_prompt(data))
    else:
        print("No ITC data found. Run the browser scraper first.")
        print("To test parsing, pass a snapshot text file as argument.")
```

================================================================================
FILE: live_recap.py
================================================================================
```python
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
```

================================================================================
FILE: market_data.py
================================================================================
```python
"""
Unified Market Data Module — Tiingo primary, Robinhood + Yahoo Finance fallback.

Replaces alpaca_data.py as the pipeline's data source.
No Alpaca or Schwab dependency — uses Tiingo (IEX) for real-time quotes and
daily history, with Robinhood MCP and Yahoo as fallbacks.

Drop-in compatible with alpaca_data.py's function signatures.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# ── Tiingo Quotes (PRIMARY for real-time as of 2026-06-22) ──────────
import urllib.request
import json as _json

_TIINGO_BASE = "https://api.tiingo.com"


def _tiingo_key() -> str:
    return os.getenv("TIINGO_API_KEY", "").strip()


def _tiingo_quotes(tickers: list) -> dict:
    """Fetch real-time (IEX) quotes from Tiingo.

    Returns {ticker: {bid, ask, last, mid, source}} matching the pipeline's
    quote schema. Tiingo's IEX endpoint gives tngoLast (last trade), plus
    bid/ask during market hours. Falls back to tngoLast/prevClose when the
    book is closed. Returns {} on any failure so the caller cascades to the
    next source.
    """
    key = _tiingo_key()
    if not key or not tickers:
        return {}
    out = {}
    try:
        url = (f"{_TIINGO_BASE}/iex/?tickers={','.join(tickers)}"
               f"&token={key}")
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
        for row in data:
            t = row.get("ticker")
            if not t:
                continue
            bid = row.get("bidPrice") or 0
            ask = row.get("askPrice") or 0
            # last-trade preference: live last → tngoLast → prevClose
            last = row.get("last") or row.get("tngoLast") or row.get("prevClose") or 0
            mid = (round((float(bid) + float(ask)) / 2, 2)
                   if bid and ask else float(last or 0))
            out[t] = {
                "bid": float(bid) if bid else 0.0,
                "ask": float(ask) if ask else 0.0,
                "last": float(last) if last else 0.0,
                "mid": mid,
                "source": "tiingo",
            }
    except Exception as e:
        print(f"[MarketData] Tiingo quotes failed: {e}")
        return {}
    return out


def _tiingo_history(ticker: str, days: int = 30) -> dict:
    """Fetch daily OHLCV history from Tiingo's EOD endpoint.

    Returns {"bars": [...], "count": n, "source": "tiingo"} or {} on failure.
    Tiingo daily prices are split/dividend-adjusted via adjClose etc.; we use
    the raw OHLCV (open/high/low/close/volume) to match the pipeline's bar
    schema. Index symbols (^VIX) are not supported and return {}.
    """
    key = _tiingo_key()
    if not key or not ticker or ticker.startswith("^"):
        return {}
    from datetime import datetime, timedelta
    start = (datetime.now() - timedelta(days=int(days * 1.6) + 10)).strftime("%Y-%m-%d")
    try:
        url = (f"{_TIINGO_BASE}/tiingo/daily/{ticker}/prices"
               f"?startDate={start}&token={key}")
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
        bars = []
        for row in data:
            d = row.get("date", "")[:10]
            bars.append({
                "date": d,
                "open": round(float(row.get("open", 0)), 2),
                "high": round(float(row.get("high", 0)), 2),
                "low": round(float(row.get("low", 0)), 2),
                "close": round(float(row.get("close", 0)), 2),
                "volume": int(row.get("volume", 0)),
            })
        if bars:
            return {"bars": bars, "count": len(bars), "source": "tiingo"}
    except Exception as e:
        print(f"[MarketData] Tiingo history failed for {ticker}: {e}")
    return {}


# ── Robinhood Quotes (secondary for real-time) ──────────────────────────

def _robinhood_quotes(tickers: list) -> dict:
    """Fetch quotes from Robinhood MCP if a token exists."""
    try:
        from broker_factory import get_broker
        broker = get_broker("robinhood")  # cached singleton — reuses MCP session
        return broker.get_quotes(tickers)
    except Exception:
        return {}


# ── Yahoo Finance (historical data + fallback) ──────────────────────────

def _yf_import():
    import yfinance as yf
    return yf


# ── Public API (drop-in for alpaca_data) ─────────────────────────────────

def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch yesterday's close for a list of tickers.
    Primary: Tiingo daily history. Fallback: Yahoo Finance.
    """
    results = {}

    # Try Tiingo first for previous close (last daily bar)
    if _tiingo_key():
        for t in tickers:
            h = _tiingo_history(t, days=5)
            bars = h.get("bars", [])
            if bars:
                last = bars[-1]
                results[t] = {
                    "prior_close": round(float(last["close"]), 2),
                    "prior_date": last["date"],
                    "source": "tiingo",
                }

    # Fill gaps with Yahoo Finance
    missing = [t for t in tickers if t not in results]
    if missing:
        yf_results = _fetch_prior_close_yfinance(missing)
        results.update(yf_results)

    return results


def _fetch_prior_close_yfinance(tickers: list) -> dict:
    """Yahoo Finance prior close fetch."""
    yf = _yf_import()
    results = {}

    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            closes = [round(float(c), 2) for c in hist["Close"].values]
            dates = [str(d.date()) for d in hist.index]

            today_str = str(datetime.now().date())
            if dates[-1] == today_str and len(closes) >= 2:
                prior_close = closes[-2]
                prior_date = dates[-2]
            else:
                prior_close = closes[-1]
                prior_date = dates[-1]

            results[ticker] = {
                "prior_close": prior_close,
                "prior_date": prior_date,
                "closes_30d": closes,
                "source": "yfinance",
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_latest_quotes(tickers: list) -> dict:
    """
    Fetch real-time quotes.
    Primary: Tiingo (real-time IEX). Fallback: Robinhood MCP, Yahoo.

    Tiingo became primary on 2026-06-22 because Schwab/Yahoo were unreliable.
    """
    results = {}

    # Try Tiingo first (real-time, reliable)
    if _tiingo_key():
        try:
            tq = _tiingo_quotes(tickers)
            for t, q in tq.items():
                if q.get("last", 0) > 0:
                    results[t] = q
            if tq:
                print(f"[MarketData] Tiingo: {len(results)}/{len(tickers)} quotes (PRIMARY)")
        except Exception as e:
            print(f"[MarketData] Tiingo quotes failed: {e}")

    # Fill gaps with Robinhood
    missing = [t for t in tickers if t not in results]
    if missing:
        try:
            rh = _robinhood_quotes(missing)
            for t, q in rh.items():
                if "error" not in q:
                    results[t] = {**q, "source": "robinhood"}
        except Exception:
            pass

    # Fill remaining gaps with Yahoo
    still_missing = [t for t in tickers if t not in results]
    if still_missing:
        yf = _yf_import()
        for t in still_missing:
            try:
                info = yf.Ticker(t).info
                price = info.get("regularMarketPrice") or info.get("previousClose", 0)
                bid = info.get("bid", 0)
                ask = info.get("ask", 0)
                results[t] = {
                    "bid": float(bid) if bid else 0.0,
                    "ask": float(ask) if ask else 0.0,
                    "last": float(price) if price else 0.0,
                    "mid": round((float(bid or 0) + float(ask or 0)) / 2, 2) if bid and ask else float(price or 0),
                    "source": "yfinance",
                }
            except Exception as e:
                results[t] = {"error": str(e)}

    return results


def fetch_historical_bars(tickers: list, days: int = 30, timeframe: str = "day") -> dict:
    """
    Fetch historical OHLCV daily bars.

    Tiingo-first for daily bars (single vendor as of 2026-06-22), with Yahoo
    Finance as a last-resort fallback per-ticker. Yahoo only fires if Tiingo
    returns empty (e.g. index symbols like ^VIX that Tiingo can't serve).
    """
    results = {}

    # ━━━ PRIMARY: Tiingo daily history (single vendor as of 2026-06-22) ━━━
    if timeframe == "day" and _tiingo_key():
        for ticker in tickers:
            h = _tiingo_history(ticker, days=days)
            if h.get("count", 0) > 0:
                results[ticker] = h
        if results:
            print(f"[MarketData] Tiingo history: {len(results)}/{len(tickers)} (PRIMARY)")

    # Determine which tickers still need data (Yahoo fallback only for gaps)
    missing = [t for t in tickers if t not in results]
    if not missing:
        return results

    yf = _yf_import()

    period_map = {
        7: "7d", 14: "14d", 30: "1mo", 60: "2mo", 90: "3mo",
        180: "6mo", 365: "1y",
    }
    period = "1mo"
    for d, p in sorted(period_map.items()):
        if days <= d:
            period = p
            break
    if days > 365:
        period = f"{days}d"

    interval = {"day": "1d", "hour": "1h", "minute": "1m"}.get(timeframe, "1d")

    for ticker in missing:
        try:
            hist = yf.Ticker(ticker).history(period=period, interval=interval)
            if hist.empty:
                results[ticker] = {"bars": [], "count": 0}
                continue

            bar_list = []
            for ts, row in hist.iterrows():
                bar_list.append({
                    "date": str(ts.date()) if timeframe == "day" else ts.isoformat(),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

            results[ticker] = {"bars": bar_list, "count": len(bar_list), "source": "yfinance"}
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_snapshots(tickers: list) -> dict:
    """
    Fetch snapshot data (latest price + daily bar + previous daily bar).
    Uses Tiingo for real-time quotes, Yahoo for daily bars.
    """
    results = {}

    # Get real-time quotes
    quotes = fetch_latest_quotes(tickers)

    # Get 2-day history from Yahoo for daily bars
    yf = _yf_import()
    for ticker in tickers:
        entry = {}

        # Quote data
        q = quotes.get(ticker, {})
        if "error" not in q:
            entry["latest_quote"] = {"bid": q.get("bid", 0), "ask": q.get("ask", 0)}
            entry["latest_trade"] = {"price": q.get("last", q.get("mid", 0)), "source": q.get("source", "unknown")}

        # Daily bars from Yahoo
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty and len(hist) >= 1:
                last_bar = hist.iloc[-1]
                entry["daily_bar"] = {
                    "open": round(float(last_bar["Open"]), 2),
                    "high": round(float(last_bar["High"]), 2),
                    "low": round(float(last_bar["Low"]), 2),
                    "close": round(float(last_bar["Close"]), 2),
                    "volume": int(last_bar["Volume"]),
                }
                if len(hist) >= 2:
                    prev_bar = hist.iloc[-2]
                    entry["prev_daily_bar"] = {
                        "open": round(float(prev_bar["Open"]), 2),
                        "high": round(float(prev_bar["High"]), 2),
                        "low": round(float(prev_bar["Low"]), 2),
                        "close": round(float(prev_bar["Close"]), 2),
                        "volume": int(prev_bar["Volume"]),
                    }
        except Exception as e:
            entry["error"] = str(e)

        results[ticker] = entry

    return results


def fetch_macro_tickers() -> dict:
    """
    Fetch macro indicator tickers — sector ETFs, credit spreads, etc.
    """
    tickers = [
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        "HYG", "LQD", "TLT", "JNK",
        "SPY", "QQQ", "IWM",
        "GLD", "USO",
    ]
    return fetch_snapshots(tickers)


def enrich_screener_universe(screener: list) -> list:
    """
    Enrich screener results with accurate prior_close.
    Drop-in replacement for alpaca_data.enrich_screener_universe().
    """
    tickers = [t["ticker"] for t in screener]

    batch_size = 50
    all_closes = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_results = fetch_prior_close(batch)
        all_closes.update(batch_results)

    for entry in screener:
        ticker = entry["ticker"]
        if ticker in all_closes and "prior_close" in all_closes[ticker]:
            entry["prior_close"] = all_closes[ticker]["prior_close"]
            entry["price_source"] = all_closes[ticker].get("source", "unknown")

    return screener


# Quick smoke test
if __name__ == "__main__":
    print("Testing Unified Market Data module...\n")

    print("1. Latest quotes for SPY, AAPL, NVDA:")
    quotes = fetch_latest_quotes(["SPY", "AAPL", "NVDA"])
    for t, q in quotes.items():
        if "error" not in q:
            print(f"   {t}: bid={q.get('bid', 0):.2f} ask={q.get('ask', 0):.2f} mid={q.get('mid', 0):.2f} (source: {q.get('source', '?')})")
        else:
            print(f"   {t}: ERROR - {q['error']}")

    print("\n2. Prior close for SPY, AAPL:")
    closes = fetch_prior_close(["SPY", "AAPL"])
    for t, c in closes.items():
        if "error" not in c:
            print(f"   {t}: {c['prior_close']} (source: {c.get('source', '?')})")
        else:
            print(f"   {t}: ERROR - {c['error']}")

    print("\n3. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars(["NVDA"], days=7)
    for bar in hist.get("NVDA", {}).get("bars", [])[-5:]:
        print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} V={bar['volume']:,}")

    print("\n✅ Unified Market Data module working!")
```

================================================================================
FILE: massive_data.py
================================================================================
```python
"""
Massive Market Data Module — Polygon-compatible API for stocks, options, and technical indicators.

Free tier includes:
- Historical OHLCV bars (2 years, end-of-day)
- Previous day bar
- Built-in technical indicators (SMA, EMA, RSI, MACD)
- Minute aggregates
- 5 API calls/minute rate limit

Paid tiers add: real-time snapshots, options chains, greeks, WebSockets.

API base: https://api.massive.com
Auth: apiKey query parameter
"""
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://api.massive.com"
API_KEY = os.environ.get("MASSIVE_API_KEY", "")

# Thread-safe rate limiter: free tier = 5 calls/min
import threading
_call_times: list = []
_rate_lock = threading.Lock()
RATE_LIMIT = 5
RATE_WINDOW = 60  # seconds


def _rate_limit():
    """Thread-safe rate limiter for free tier (5 calls/min)."""
    global _call_times
    with _rate_lock:
        now = time.time()
        _call_times = [t for t in _call_times if now - t < RATE_WINDOW]
        if len(_call_times) >= RATE_LIMIT:
            wait = RATE_WINDOW - (now - _call_times[0]) + 0.5
            if wait > 0:
                print(f"[Massive] Rate limit reached \u2014 waiting {wait:.1f}s")
                _rate_lock.release()
                time.sleep(wait)
                _rate_lock.acquire()
        _call_times.append(time.time())


def _get(endpoint: str, params: dict = None) -> dict:
    """Make an authenticated GET request to Massive API."""
    import requests

    if not API_KEY:
        return {"error": "MASSIVE_API_KEY not set in .env"}

    _rate_limit()

    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    params["apiKey"] = API_KEY

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        if data.get("status") == "NOT_AUTHORIZED":
            return {"error": f"Not authorized: {data.get('message', 'upgrade plan')}"}
        return data
    except Exception as e:
        return {"error": str(e)}


# ─── Stock Aggregates ───────────────────────────────────────────────

def fetch_previous_day(ticker: str) -> dict:
    """Fetch previous trading day's OHLCV bar for a single ticker."""
    data = _get(f"/v2/aggs/ticker/{ticker}/prev")
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": f"No previous day data for {ticker}"}

    bar = results[0]
    return {
        "ticker": ticker,
        "open": bar.get("o"),
        "high": bar.get("h"),
        "low": bar.get("l"),
        "close": bar.get("c"),
        "volume": bar.get("v"),
        "vwap": bar.get("vw"),
        "transactions": bar.get("n"),
        "timestamp": bar.get("t"),
        "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d") if bar.get("t") else None,
    }


def fetch_prior_close_batch(tickers: list) -> dict:
    """
    Fetch previous day's close for multiple tickers.
    Note: free tier is 5 calls/min, so this is rate-limited.
    For large batches, prefer the unified market_data feed. Use Massive for enrichment.
    """
    results = {}
    for ticker in tickers:
        prev = fetch_previous_day(ticker)
        if "error" not in prev:
            results[ticker] = {
                "prior_close": round(prev["close"], 2),
                "prior_date": prev["date"],
                "prior_open": round(prev["open"], 2),
                "prior_high": round(prev["high"], 2),
                "prior_low": round(prev["low"], 2),
                "prior_volume": prev["volume"],
                "prior_vwap": round(prev["vwap"], 2) if prev["vwap"] else None,
                "source": "massive",
            }
        else:
            results[ticker] = {"error": prev["error"]}
    return results


def fetch_historical_bars(
    ticker: str,
    days: int = 30,
    timespan: str = "day",
    multiplier: int = 1,
) -> dict:
    """
    Fetch historical OHLCV bars for a ticker.

    Args:
        ticker: Stock symbol
        days: Number of calendar days of history
        timespan: "day", "hour", or "minute"
        multiplier: Bar size multiplier (e.g., 5 with minute = 5-min bars)
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data = _get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{start}/{end}",
        params={"sort": "asc", "limit": 5000},
    )

    if "error" in data:
        return data

    results = data.get("results", [])
    bars = []
    for bar in results:
        bars.append({
            "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d") if timespan == "day" else datetime.fromtimestamp(bar["t"] / 1000).isoformat(),
            "open": round(bar["o"], 2),
            "high": round(bar["h"], 2),
            "low": round(bar["l"], 2),
            "close": round(bar["c"], 2),
            "volume": bar.get("v", 0),
            "vwap": round(bar["vw"], 2) if bar.get("vw") else None,
            "transactions": bar.get("n"),
        })

    return {
        "ticker": ticker,
        "bars": bars,
        "count": len(bars),
        "source": "massive",
    }


# ─── Technical Indicators (FREE — this is the killer feature) ────────

def fetch_sma(ticker: str, window: int = 20, timespan: str = "day", limit: int = 30) -> dict:
    """
    Fetch Simple Moving Average values.
    Built-in — no local calculation needed.
    """
    data = _get(
        f"/v1/indicators/sma/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    return {
        "ticker": ticker,
        "indicator": f"SMA_{window}",
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 4),
            }
            for v in values
        ],
        "current": round(values[0]["value"], 4) if values else None,
        "source": "massive",
    }


def fetch_ema(ticker: str, window: int = 20, timespan: str = "day", limit: int = 30) -> dict:
    """Fetch Exponential Moving Average values."""
    data = _get(
        f"/v1/indicators/ema/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    return {
        "ticker": ticker,
        "indicator": f"EMA_{window}",
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 4),
            }
            for v in values
        ],
        "current": round(values[0]["value"], 4) if values else None,
        "source": "massive",
    }


def fetch_rsi(ticker: str, window: int = 14, timespan: str = "day", limit: int = 30) -> dict:
    """
    Fetch Relative Strength Index.
    RSI > 70 = overbought, RSI < 30 = oversold.
    """
    data = _get(
        f"/v1/indicators/rsi/{ticker}",
        params={"timespan": timespan, "window": window, "series_type": "close", "limit": limit, "order": "desc"},
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    current_rsi = round(values[0]["value"], 2) if values else None

    # Classify RSI
    signal = "neutral"
    if current_rsi:
        if current_rsi >= 70:
            signal = "overbought"
        elif current_rsi >= 60:
            signal = "bullish"
        elif current_rsi <= 30:
            signal = "oversold"
        elif current_rsi <= 40:
            signal = "bearish"

    return {
        "ticker": ticker,
        "indicator": f"RSI_{window}",
        "current": current_rsi,
        "signal": signal,
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "value": round(v["value"], 2),
            }
            for v in values
        ],
        "source": "massive",
    }


def fetch_macd(
    ticker: str,
    short_window: int = 12,
    long_window: int = 26,
    signal_window: int = 9,
    timespan: str = "day",
    limit: int = 30,
) -> dict:
    """
    Fetch MACD (Moving Average Convergence Divergence).
    Returns MACD line, signal line, and histogram.
    """
    data = _get(
        f"/v1/indicators/macd/{ticker}",
        params={
            "timespan": timespan,
            "short_window": short_window,
            "long_window": long_window,
            "signal_window": signal_window,
            "series_type": "close",
            "limit": limit,
            "order": "desc",
        },
    )
    if "error" in data:
        return data

    values = data.get("results", {}).get("values", [])
    if not values:
        return {"ticker": ticker, "indicator": "MACD", "error": "No data"}

    current = values[0]
    macd_val = round(current.get("value", 0), 4)
    signal_val = round(current.get("signal", 0), 4)
    histogram = round(current.get("histogram", 0), 4)

    # Classify signal
    signal = "neutral"
    if histogram > 0 and macd_val > signal_val:
        signal = "bullish"
    elif histogram < 0 and macd_val < signal_val:
        signal = "bearish"

    # Check for crossover (compare current vs previous)
    crossover = None
    if len(values) >= 2:
        prev = values[1]
        prev_hist = prev.get("histogram", 0)
        if prev_hist <= 0 < histogram:
            crossover = "bullish_crossover"
        elif prev_hist >= 0 > histogram:
            crossover = "bearish_crossover"

    return {
        "ticker": ticker,
        "indicator": "MACD",
        "macd": macd_val,
        "signal_line": signal_val,
        "histogram": histogram,
        "signal": signal,
        "crossover": crossover,
        "values": [
            {
                "date": datetime.fromtimestamp(v["timestamp"] / 1000).strftime("%Y-%m-%d"),
                "macd": round(v.get("value", 0), 4),
                "signal": round(v.get("signal", 0), 4),
                "histogram": round(v.get("histogram", 0), 4),
            }
            for v in values[:10]  # Last 10 days
        ],
        "source": "massive",
    }


def fetch_full_technicals(ticker: str) -> dict:
    """
    Fetch a complete technical analysis package for a single ticker.
    Returns previous day bar + RSI(14) + MACD.
    
    Optimized for free tier rate limits (5 calls/min):
    - 3 API calls per ticker (prev_day, RSI, MACD)
    - SMA is computed locally from historical bars when possible
    """
    result = {"ticker": ticker, "source": "massive", "timestamp": datetime.now().isoformat()}

    # 1. Previous day bar (1 call)
    prev = fetch_previous_day(ticker)
    if "error" not in prev:
        result["price"] = round(prev["close"], 2)
        result["prev_open"] = round(prev["open"], 2)
        result["prev_high"] = round(prev["high"], 2)
        result["prev_low"] = round(prev["low"], 2)
        result["prev_volume"] = prev["volume"]
        result["prev_vwap"] = round(prev["vwap"], 2) if prev.get("vwap") else None

    # 2. RSI (1 call)
    rsi = fetch_rsi(ticker, window=14, limit=5)
    result["rsi_14"] = rsi.get("current")
    result["rsi_signal"] = rsi.get("signal")

    # 3. MACD (1 call)
    macd = fetch_macd(ticker, limit=5)
    result["macd"] = macd.get("macd")
    result["macd_signal"] = macd.get("signal_line")
    result["macd_histogram"] = macd.get("histogram")
    result["macd_trend"] = macd.get("signal")
    result["macd_crossover"] = macd.get("crossover")

    return result


def fetch_technicals_with_sma(ticker: str) -> dict:
    """
    Full technicals including SMA(20) and SMA(50).
    Uses 5 API calls — consumes entire free tier minute quota for one ticker.
    Use sparingly (e.g., only for SPY or the top pick).
    """
    result = fetch_full_technicals(ticker)  # 3 calls

    # 4. SMA(20) (1 call)
    sma_20 = fetch_sma(ticker, window=20, limit=3)
    result["sma_20"] = sma_20.get("current")

    # 5. SMA(50) (1 call)
    sma_50 = fetch_sma(ticker, window=50, limit=3)
    result["sma_50"] = sma_50.get("current")

    # Price vs MAs
    price = result.get("price")
    if price:
        if result.get("sma_20"):
            result["price_vs_sma20"] = "above" if price > result["sma_20"] else "below"
        if result.get("sma_50"):
            result["price_vs_sma50"] = "above" if price > result["sma_50"] else "below"

    return result


# ─── Local Technical Calculations (no API calls) ────────────────────

def calculate_technicals_local(ticker: str, period: str = "6mo") -> dict:
    """
    Calculate technical indicators locally using yfinance + pandas.
    Zero API calls to Massive — no rate limit concerns.

    Downloads historical bars from yfinance and computes:
    - SMA 10, 20, 50
    - EMA 20
    - RSI 14
    - MACD (12, 26, 9)

    Args:
        ticker: Stock symbol (e.g. "SPY")
        period: yfinance period string ("1mo", "3mo", "6mo", "1y", "2y")

    Returns:
        dict with all indicators, or dict with "error" key on failure.
    """
    import pandas as pd

    # Map yfinance period string -> approximate calendar days for Schwab.
    _period_days = {
        "1mo": 30, "2mo": 60, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "ytd": 365,
    }
    days = _period_days.get(period, 180)

    df = None
    # Schwab-FIRST via the unified market_data layer (handles index symbols too).
    try:
        import market_data as _mdata
        res = _mdata.fetch_historical_bars([ticker], days=days, timeframe="day")
        entry = res.get(ticker, {}) if isinstance(res, dict) else {}
        bars = entry.get("bars") if entry.get("count", 0) > 0 else None
        if bars:
            idx = pd.to_datetime([b["date"] for b in bars])
            df = pd.DataFrame({
                "Open": [b["open"] for b in bars],
                "High": [b["high"] for b in bars],
                "Low": [b["low"] for b in bars],
                "Close": [b["close"] for b in bars],
                "Volume": [b["volume"] for b in bars],
            }, index=idx)
    except Exception:
        df = None

    # Last-resort fallback: raw yfinance.
    if df is None or df.empty:
        try:
            import yfinance as yf
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        except Exception as e:
            return {"ticker": ticker, "error": f"history download failed: {e}", "source": "local_calculation"}

    if df is None or df.empty or len(df) < 50:
        n = 0 if df is None else len(df)
        return {"ticker": ticker, "error": f"Insufficient data ({n} bars, need >=50)", "source": "local_calculation"}

    # Flatten MultiIndex columns if yfinance returns them (e.g. ("Close", "SPY"))
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    closes = df["Close"].astype(float)

    # ── SMA ──
    sma_10 = closes.rolling(window=10).mean()
    sma_20 = closes.rolling(window=20).mean()
    sma_50 = closes.rolling(window=50).mean()

    # ── EMA ──
    ema_20 = closes.ewm(span=20, adjust=False).mean()

    # ── RSI 14 ──
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    # ── MACD (12, 26, 9) ──
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    # ── Extract latest values ──
    last_close = round(float(closes.iloc[-1]), 2)
    cur_sma_10 = round(float(sma_10.iloc[-1]), 4) if pd.notna(sma_10.iloc[-1]) else None
    cur_sma_20 = round(float(sma_20.iloc[-1]), 4) if pd.notna(sma_20.iloc[-1]) else None
    cur_sma_50 = round(float(sma_50.iloc[-1]), 4) if pd.notna(sma_50.iloc[-1]) else None
    cur_ema_20 = round(float(ema_20.iloc[-1]), 4) if pd.notna(ema_20.iloc[-1]) else None
    cur_rsi = round(float(rsi.iloc[-1]), 2) if pd.notna(rsi.iloc[-1]) else None
    cur_macd = round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None
    cur_signal = round(float(signal_line.iloc[-1]), 4) if pd.notna(signal_line.iloc[-1]) else None
    cur_hist = round(float(histogram.iloc[-1]), 4) if pd.notna(histogram.iloc[-1]) else None

    # ── RSI classification ──
    rsi_signal = "neutral"
    if cur_rsi is not None:
        if cur_rsi >= 70:
            rsi_signal = "overbought"
        elif cur_rsi >= 60:
            rsi_signal = "bullish"
        elif cur_rsi <= 30:
            rsi_signal = "oversold"
        elif cur_rsi <= 40:
            rsi_signal = "bearish"

    # ── MACD classification ──
    macd_trend = "neutral"
    if cur_hist is not None and cur_macd is not None and cur_signal is not None:
        if cur_hist > 0 and cur_macd > cur_signal:
            macd_trend = "bullish"
        elif cur_hist < 0 and cur_macd < cur_signal:
            macd_trend = "bearish"

    # ── MACD crossover detection ──
    macd_crossover = None
    if len(histogram) >= 2 and pd.notna(histogram.iloc[-1]) and pd.notna(histogram.iloc[-2]):
        prev_hist = float(histogram.iloc[-2])
        curr_hist = float(histogram.iloc[-1])
        if prev_hist <= 0 < curr_hist:
            macd_crossover = "bullish_crossover"
        elif prev_hist >= 0 > curr_hist:
            macd_crossover = "bearish_crossover"

    # ── Price vs MAs ──
    price_vs_sma20 = None
    price_vs_sma50 = None
    if cur_sma_20 is not None:
        price_vs_sma20 = "above" if last_close > cur_sma_20 else "below"
    if cur_sma_50 is not None:
        price_vs_sma50 = "above" if last_close > cur_sma_50 else "below"

    return {
        "ticker": ticker,
        "sma_10": cur_sma_10,
        "sma_20": cur_sma_20,
        "sma_50": cur_sma_50,
        "ema_20": cur_ema_20,
        "rsi_14": cur_rsi,
        "rsi_signal": rsi_signal,
        "macd": {"macd_line": cur_macd, "signal_line": cur_signal, "histogram": cur_hist},
        "macd_trend": macd_trend,
        "macd_crossover": macd_crossover,
        "last_close": last_close,
        "price_vs_sma20": price_vs_sma20,
        "price_vs_sma50": price_vs_sma50,
        "source": "local_calculation",
    }


def calculate_technicals_batch(tickers: list, period: str = "6mo") -> dict:
    """
    Calculate technical indicators locally for multiple tickers.
    No API calls — runs entirely off yfinance historical data + pandas.

    Args:
        tickers: List of stock symbols
        period: yfinance period string

    Returns:
        Dict keyed by ticker symbol, each value is the output of calculate_technicals_local().
    """
    results = {}
    for ticker in tickers:
        results[ticker] = calculate_technicals_local(ticker, period=period)
    return results


def format_technicals_for_prompt(technicals: dict) -> str:
    """Format technical analysis data for agent prompts.
    Handles both API-based format and local calculation format."""
    t = technicals

    # Resolve price — API uses 'price', local uses 'last_close'
    price = t.get('price') or t.get('last_close', '?')

    # Resolve MACD fields — local wraps them in a dict, API puts them at top level
    macd_data = t.get('macd')
    if isinstance(macd_data, dict):
        macd_val = macd_data.get('macd_line', 'N/A')
        signal_val = macd_data.get('signal_line', 'N/A')
        hist_val = macd_data.get('histogram', 'N/A')
    else:
        macd_val = macd_data if macd_data is not None else 'N/A'
        signal_val = t.get('macd_signal', 'N/A')
        hist_val = t.get('macd_histogram', 'N/A')

    lines = [
        f"TECHNICAL ANALYSIS: {t['ticker']}",
        f"  Price: ${price}",
        f"  SMA(10): {t.get('sma_10', 'N/A')}",
        f"  SMA(20): {t.get('sma_20', 'N/A')} ({t.get('price_vs_sma20', '?')})",
        f"  SMA(50): {t.get('sma_50', 'N/A')} ({t.get('price_vs_sma50', '?')})",
        f"  EMA(20): {t.get('ema_20', 'N/A')}",
        f"  RSI(14): {t.get('rsi_14', 'N/A')} ({t.get('rsi_signal', '?')})",
        f"  MACD: {macd_val} | Signal: {signal_val} | Hist: {hist_val}",
        f"  MACD Trend: {t.get('macd_trend', '?')} | Crossover: {t.get('macd_crossover', 'none')}",
    ]
    return "\n".join(lines)


# ─── Macro / Economy (FREE — Schwab doesn't have these) ─────────────

def fetch_treasury_yields(limit: int = 5) -> dict:
    """
    Fetch U.S. Treasury yield curve data.
    Returns yields for 1mo, 3mo, 6mo, 1yr, 2yr, 3yr, 5yr, 7yr, 10yr, 20yr, 30yr.
    Data back to 1962. Included in ALL plans (including free).
    """
    data = _get("/fed/v1/treasury-yields", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No treasury yield data"}

    latest = results[0]
    return {
        "date": latest.get("date"),
        "yields": {
            "1mo": latest.get("yield_1_month"),
            "3mo": latest.get("yield_3_month"),
            "6mo": latest.get("yield_6_month"),
            "1yr": latest.get("yield_1_year"),
            "2yr": latest.get("yield_2_year"),
            "3yr": latest.get("yield_3_year"),
            "5yr": latest.get("yield_5_year"),
            "7yr": latest.get("yield_7_year"),
            "10yr": latest.get("yield_10_year"),
            "20yr": latest.get("yield_20_year"),
            "30yr": latest.get("yield_30_year"),
        },
        "spread_2s10s": round(latest.get("yield_10_year", 0) - latest.get("yield_2_year", 0), 2) if latest.get("yield_10_year") and latest.get("yield_2_year") else None,
        "spread_3mo10yr": round(latest.get("yield_10_year", 0) - latest.get("yield_3_month", 0), 2) if latest.get("yield_10_year") and latest.get("yield_3_month") else None,
        "history": [
            {
                "date": r.get("date"),
                "2yr": r.get("yield_2_year"),
                "10yr": r.get("yield_10_year"),
                "30yr": r.get("yield_30_year"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_inflation(limit: int = 5) -> dict:
    """
    Fetch U.S. inflation indicators: CPI, Core CPI, PCE, Core PCE, PCE Spending.
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/inflation", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No inflation data"}

    latest = results[0]

    # Calculate YoY CPI change if we have enough history
    yoy_cpi = None
    if len(results) >= 2:
        # Find a result ~12 months back
        for r in results:
            if r.get("cpi") and latest.get("cpi"):
                yoy_cpi = round((latest["cpi"] - r["cpi"]) / r["cpi"] * 100, 2)
                break  # Just use the oldest in our result set as approximation

    return {
        "date": latest.get("date"),
        "cpi": latest.get("cpi"),
        "cpi_core": latest.get("cpi_core"),
        "pce": latest.get("pce"),
        "pce_core": latest.get("pce_core"),
        "pce_spending": latest.get("pce_spending"),
        "history": [
            {
                "date": r.get("date"),
                "cpi": r.get("cpi"),
                "cpi_core": r.get("cpi_core"),
                "pce": r.get("pce"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_labor_market(limit: int = 5) -> dict:
    """
    Fetch U.S. labor market indicators: unemployment, participation, earnings, JOLTS.
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/labor-market", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No labor market data"}

    latest = results[0]
    return {
        "date": latest.get("date"),
        "unemployment_rate": latest.get("unemployment_rate"),
        "labor_force_participation": latest.get("labor_force_participation_rate"),
        "avg_hourly_earnings": latest.get("avg_hourly_earnings"),
        "job_openings": latest.get("job_openings"),
        "history": [
            {
                "date": r.get("date"),
                "unemployment": r.get("unemployment_rate"),
                "participation": r.get("labor_force_participation_rate"),
                "earnings": r.get("avg_hourly_earnings"),
            }
            for r in results
        ],
        "source": "massive",
    }


def fetch_inflation_expectations(limit: int = 5) -> dict:
    """
    Fetch U.S. inflation expectations (forward-looking).
    Included in ALL plans (including free).
    """
    data = _get("/fed/v1/inflation-expectations", params={"limit": limit, "sort": "date.desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"error": "No inflation expectations data"}

    return {
        "date": results[0].get("date"),
        "latest": results[0],
        "history": results,
        "source": "massive",
    }


def fetch_macro_snapshot() -> dict:
    """
    Fetch a complete macro snapshot in 4 API calls:
    treasury yields + inflation + labor market + inflation expectations.

    This is the macro enrichment layer for Agent 1 (Macro Director).
    Schwab doesn't offer ANY of this — it's Massive's unique value.

    Rate limit note: This uses 4 of your 5 free calls/minute.
    """
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "source": "massive_macro",
    }

    snapshot["treasury_yields"] = fetch_treasury_yields(limit=5)
    snapshot["inflation"] = fetch_inflation(limit=5)
    snapshot["labor_market"] = fetch_labor_market(limit=5)
    snapshot["inflation_expectations"] = fetch_inflation_expectations(limit=3)

    return snapshot


def format_macro_for_prompt(macro: dict) -> str:
    """
    Format macro snapshot data for agent prompts.
    Designed for Agent 1 (Macro Director) consumption.
    """
    lines = ["MACRO ENVIRONMENT SNAPSHOT"]
    lines.append(f"  Timestamp: {macro.get('timestamp', '?')}")

    # Treasury Yields
    ty = macro.get("treasury_yields", {})
    if "error" not in ty:
        y = ty.get("yields", {})
        lines.append(f"\nTREASURY YIELDS ({ty.get('date', '?')})")
        _y = lambda k: f"{y[k]}%" if y.get(k) is not None else "N/A"
        lines.append(f"  Short: 1mo={_y('1mo')} | 3mo={_y('3mo')} | 6mo={_y('6mo')}")
        lines.append(f"  Mid:   1yr={_y('1yr')} | 2yr={_y('2yr')} | 5yr={_y('5yr')}")
        lines.append(f"  Long:  10yr={_y('10yr')} | 20yr={_y('20yr')} | 30yr={_y('30yr')}")
        lines.append(f"  2s10s spread: {ty.get('spread_2s10s')}% | 3mo10yr spread: {ty.get('spread_3mo10yr')}%")
        if ty.get('spread_2s10s') is not None and ty['spread_2s10s'] < 0:
            lines.append("  ⚠️ INVERTED YIELD CURVE (2s10s) — recession signal")
    else:
        lines.append(f"\nTREASURY YIELDS: {ty.get('error', 'unavailable')}")

    # Inflation
    inf = macro.get("inflation", {})
    if "error" not in inf:
        lines.append(f"\nINFLATION ({inf.get('date', '?')})")
        lines.append(f"  CPI: {inf.get('cpi', 'N/A')} | Core CPI: {inf.get('cpi_core', 'N/A')}")
        if inf.get('pce') is not None:
            lines.append(f"  PCE: {inf['pce']} | Core PCE: {inf.get('pce_core', 'N/A')}")
        if inf.get('pce_spending') is not None:
            lines.append(f"  PCE Spending: ${inf['pce_spending']}B")
    else:
        lines.append(f"\nINFLATION: {inf.get('error', 'unavailable')}")

    # Labor Market
    lm = macro.get("labor_market", {})
    if "error" not in lm:
        lines.append(f"\nLABOR MARKET ({lm.get('date', '?')})")
        lines.append(f"  Unemployment: {lm.get('unemployment_rate')}%")
        lines.append(f"  Labor Force Participation: {lm.get('labor_force_participation')}%")
        lines.append(f"  Avg Hourly Earnings: ${lm.get('avg_hourly_earnings')}")
        if lm.get('job_openings'):
            lines.append(f"  Job Openings (JOLTS): {lm['job_openings']:,.0f}K")
    else:
        lines.append(f"\nLABOR MARKET: {lm.get('error', 'unavailable')}")

    return "\n".join(lines)


# ─── Ticker Reference & Fundamentals (FREE) ─────────────────────────

def fetch_ticker_details(ticker: str) -> dict:
    """
    Fetch comprehensive ticker details: name, market cap, sector, description, etc.
    Included in ALL plans (including free).
    """
    data = _get(f"/v3/reference/tickers/{ticker}")
    if "error" in data:
        return data

    r = data.get("results", {})
    return {
        "ticker": r.get("ticker"),
        "name": r.get("name"),
        "market_cap": r.get("market_cap"),
        "description": r.get("description"),
        "sector": r.get("sic_description"),
        "employees": r.get("total_employees"),
        "homepage": r.get("homepage_url"),
        "list_date": r.get("list_date"),
        "shares_outstanding": r.get("share_class_shares_outstanding"),
        "source": "massive",
    }


def fetch_dividends(ticker: str, limit: int = 4) -> dict:
    """
    Fetch recent dividend history for a ticker.
    Included in ALL plans (including free).
    """
    data = _get("/v3/reference/dividends", params={"ticker": ticker, "limit": limit, "sort": "ex_dividend_date", "order": "desc"})
    if "error" in data:
        return data

    results = data.get("results", [])
    return {
        "ticker": ticker,
        "dividends": [
            {
                "ex_date": d.get("ex_dividend_date"),
                "pay_date": d.get("pay_date"),
                "amount": d.get("cash_amount"),
                "frequency": d.get("frequency"),
            }
            for d in results
        ],
        "annual_dividend": sum(d.get("cash_amount", 0) for d in results[:4]) if len(results) >= 4 else None,
        "source": "massive",
    }


def fetch_financials(ticker: str, limit: int = 2) -> dict:
    """
    Fetch company financial statements (income statement, balance sheet).
    Included in ALL plans (including free).
    """
    data = _get("/vX/reference/financials", params={"ticker": ticker, "limit": limit})
    if "error" in data:
        return data

    results = data.get("results", [])
    if not results:
        return {"ticker": ticker, "error": "No financial data"}

    summaries = []
    for r in results:
        fi = r.get("financials", {})
        income = fi.get("income_statement", {})
        balance = fi.get("balance_sheet", {})

        summaries.append({
            "period": f"{r.get('fiscal_period', '?')} {r.get('fiscal_year', '?')}",
            "revenue": income.get("revenues", {}).get("value"),
            "net_income": income.get("net_income_loss", {}).get("value"),
            "gross_profit": income.get("gross_profit", {}).get("value"),
            "total_assets": balance.get("assets", {}).get("value"),
            "total_liabilities": balance.get("liabilities", {}).get("value"),
            "equity": balance.get("equity", {}).get("value"),
        })

    return {
        "ticker": ticker,
        "financials": summaries,
        "source": "massive",
    }


def fetch_market_status() -> dict:
    """
    Fetch current market status (open/closed) for all exchanges.
    Included in ALL plans (including free).
    """
    data = _get("/v1/marketstatus/now")
    if "error" in data:
        return data

    return {
        "market": data.get("market", "unknown"),
        "early_hours": data.get("earlyHours"),
        "after_hours": data.get("afterHours"),
        "exchanges": data.get("exchanges", {}),
        "currencies": data.get("currencies", {}),
        "source": "massive",
    }


# ─── Crypto (FREE) ──────────────────────────────────────────────────

def fetch_crypto_bars(pair: str = "X:BTCUSD", days: int = 30) -> dict:
    """
    Fetch historical OHLCV bars for a crypto pair.
    Free tier. Schwab doesn't have crypto at all.
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    data = _get(f"/v2/aggs/ticker/{pair}/range/1/day/{start}/{end}", params={"sort": "asc", "limit": 5000})
    if "error" in data:
        return data

    results = data.get("results", [])
    return {
        "pair": pair,
        "bars": [
            {
                "date": datetime.fromtimestamp(bar["t"] / 1000).strftime("%Y-%m-%d"),
                "open": round(bar["o"], 2),
                "high": round(bar["h"], 2),
                "low": round(bar["l"], 2),
                "close": round(bar["c"], 2),
                "volume": bar.get("v", 0),
                "vwap": round(bar["vw"], 2) if bar.get("vw") else None,
            }
            for bar in results
        ],
        "count": len(results),
        "source": "massive",
    }


# ─── Smoke Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Massive Market Data API...\n")

    # Test 1: Previous day bar
    print("1. Previous day bar for AAPL:")
    prev = fetch_previous_day("AAPL")
    if "error" not in prev:
        print(f"   {prev['date']}: O={prev['open']} H={prev['high']} L={prev['low']} C={prev['close']} V={prev['volume']:,.0f}")
    else:
        print(f"   ERROR: {prev['error']}")

    # Test 2: Historical bars
    print("\n2. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars("NVDA", days=7)
    if "error" not in hist:
        for bar in hist["bars"][-5:]:
            print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} VWAP={bar['vwap']}")
    else:
        print(f"   ERROR: {hist['error']}")

    # Test 3: Technical indicators
    print("\n3. RSI(14) for NVDA:")
    rsi = fetch_rsi("NVDA")
    if "error" not in rsi:
        print(f"   Current RSI: {rsi['current']} ({rsi['signal']})")
    else:
        print(f"   ERROR: {rsi}")

    print("\n4. MACD for NVDA:")
    macd = fetch_macd("NVDA")
    if "error" not in macd:
        print(f"   MACD: {macd['macd']} | Signal: {macd['signal_line']} | Hist: {macd['histogram']}")
        print(f"   Trend: {macd['signal']} | Crossover: {macd['crossover']}")
    else:
        print(f"   ERROR: {macd}")

    # Test 4: Full technicals package
    print("\n5. Full technicals for SPY:")
    tech = fetch_full_technicals("SPY")
    print(format_technicals_for_prompt(tech))

    # --- Wait for rate limit reset (free tier = 5 calls/min) ---
    print("\n--- Waiting 65s for rate limit reset to test macro endpoints ---")
    time.sleep(65)

    # Test 5: Macro snapshot
    print("\n6. Treasury Yields:")
    ty = fetch_treasury_yields(limit=3)
    if "error" not in ty:
        print(f"   Date: {ty['date']}")
        print(f"   2yr={ty['yields']['2yr']}% | 10yr={ty['yields']['10yr']}% | 30yr={ty['yields']['30yr']}%")
        print(f"   2s10s spread: {ty['spread_2s10s']}%")
    else:
        print(f"   ERROR: {ty}")

    print("\n7. Inflation:")
    inf = fetch_inflation(limit=3)
    if "error" not in inf:
        print(f"   Date: {inf['date']}")
        print(f"   CPI: {inf['cpi']} | Core CPI: {inf['cpi_core']}")
    else:
        print(f"   ERROR: {inf}")

    print("\n8. Labor Market:")
    lm = fetch_labor_market(limit=3)
    if "error" not in lm:
        print(f"   Date: {lm['date']}")
        print(f"   Unemployment: {lm['unemployment_rate']}% | Participation: {lm['labor_force_participation']}%")
        print(f"   Avg Hourly Earnings: ${lm['avg_hourly_earnings']}")
    else:
        print(f"   ERROR: {lm}")

    print("\n9. Ticker Details (AAPL):")
    td = fetch_ticker_details("AAPL")
    if "error" not in td:
        print(f"   {td['name']} | Market Cap: ${td['market_cap']/1e9:.1f}B | Employees: {td['employees']:,}")
    else:
        print(f"   ERROR: {td}")

    print("\n10. Crypto BTC-USD (7 days):")
    btc = fetch_crypto_bars("X:BTCUSD", days=7)
    if "error" not in btc:
        for bar in btc["bars"][-3:]:
            print(f"   {bar['date']}: C=${bar['close']:,.0f}")
    else:
        print(f"   ERROR: {btc}")

    print("\n✅ Massive Market Data module working (all endpoints)!")
```

================================================================================
FILE: orchestrator.py
================================================================================
```python
"""
Open Claw Orchestrator — "Golden Path" v2
Runs the full 5-agent pipeline in sequence.

Schedule (ET):
  7:55 AM  — Pre-flight: macro data, screener universe, prior closes
  8:00 AM  — Agent 1 (Claude): Regime classification
  8:01 AM  — Agent 2 (Gemini 3.1 Pro): Fundamental screening
  8:05 AM  — Agent 3 (Claude): Qualitative synthesis (news + options + SI + smart money X)
  8:17 AM  — Agent 4A (Claude): Stop anchors + 4B (Python): Position sizing
  8:18 AM  — Deliver tear sheet
  3:25 PM  — Agent 5 pre-flight: Price snapshot
  3:30 PM  — Agent 5 (Claude): Position monitoring

Usage:
  python3 orchestrator.py morning    # Run Agents 1-4 (morning entry pipeline, Agent 2.5 merged into 3)
  python3 orchestrator.py monitor    # Run Agent 5 (afternoon position monitor)
  python3 orchestrator.py full       # Run morning + schedule monitor for 3:30 PM
  python3 orchestrator.py test       # Dry run with verbose output
"""
import json
import os
import sys
from datetime import datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from preflight import run_preflight, format_macro_for_prompt
from agent1_macro_director import run_agent1, format_directive_for_telegram
from agent2_fundamental_screener import run_agent2, format_agent2_for_telegram
from agent3_synthesizer import run_agent3, format_agent3_for_slack
from agent4_risk_manager import run_agent4, generate_tear_sheet
from agent5_position_monitor import run_agent5, run_agent5_preflight, format_agent5_for_telegram
from broker_factory import get_broker
from trade_journal import log_close, build_trade_record
from watchlist import Watchlist, promote_ready_candidates
# VWAP gate removed — caused adverse selection (buying above morning VWAP = exit liquidity for institutions)
# Marketable limit routing: cross the book at ask + 15bps to guarantee fills on breakouts
# from vwap_gate import check_vwap, vwap_gate
from run_archiver import archive_run
from safeguards import (
    is_market_open_today,
    send_telegram,
    send_crash_alert,
    send_market_closed_alert,
    send_pipeline_start_alert,
    send_pipeline_complete_alert,
    send_hb_signal,
    add_to_penalty_box,
    tick_penalty_box,
    filter_cooldown_tickers,
    filter_earnings_tickers,
    cap_shares_by_volume,
)


def fetch_x_smart_money(tickers: list) -> dict:
    """
    Fetch smart money X/Twitter mentions for the given tickers.
    Uses the official X Developer API via x_fetch.py.
    7-day lookback, filtered by CURATED_ACCOUNTS (43 accounts).
    """
    from x_fetch import run_x_fetch
    
    print(f"[Orchestrator] Fetching X/Twitter smart money data for: {tickers}")
    result = run_x_fetch(tickers)
    return result.get("mentions", {})



# Discord is OUTPUT ONLY — used to deliver Tear Sheets and Agent 5 alerts.
# NO Discord scraping for sentiment input. All sentiment comes from X API.
# discord_fetch.py exists but is NOT called in the pipeline flow.


def run_morning_pipeline(verbose: bool = False) -> dict:
    """
    Run the full morning entry pipeline: Pre-flight → Agent 1 → 2 → 3 → 4.
    Returns the final tear sheet and all intermediate results.
    """
    results = {}
    pipeline_errors = []  # Track errors for hb_signal
    
    print("=" * 50)
    print("🌅 OPEN CLAW — MORNING ENTRY PIPELINE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)
    
    # ━━━ STEP 0: MARKET CALENDAR CHECK ━━━
    print("\n" + "━" * 40)
    print("📅 STEP 0: MARKET CALENDAR CHECK")
    print("━" * 40)
    
    calendar = is_market_open_today()
    print(f"  Market open: {calendar.get('is_open')}")
    print(f"  Should run: {calendar.get('should_run')}")
    print(f"  Reason: {calendar.get('reason')}")
    
    if not calendar.get("should_run", True):
        print("\n⚠️ Market is CLOSED today. Halting pipeline gracefully.")
        send_market_closed_alert()
        return {"halted": True, "reason": calendar.get("reason")}
    
    # Send pipeline start notification
    send_pipeline_start_alert()
    
    # ━━━ STEP 1: PRE-FLIGHT (7:55 AM) ━━━
    print("\n" + "━" * 40)
    print("📡 STEP 1: PRE-FLIGHT DATA FETCH")
    print("━" * 40)
    
    try:
        # Tick the penalty box (decrement cooldowns)
        tick_penalty_box()
        
        preflight_data = run_preflight()
        screener = preflight_data.get('screener_universe', [])
        
        # Filter out cooled-down tickers (whipsaw prevention)
        screener = filter_cooldown_tickers(screener)
        
        # Filter out tickers with upcoming earnings (binary event prevention)
        screener, earnings_removed = filter_earnings_tickers(screener)
        if earnings_removed:
            results["earnings_filtered"] = earnings_removed
        
        preflight_data['screener_universe'] = screener
        results["preflight"] = {"success": True, "data": preflight_data}
        print(f"✅ Pre-flight complete: {len(screener)} screener tickers (post-filters)")
    except Exception as e:
        print(f"❌ Pre-flight FAILED: {e}")
        send_crash_alert("Pre-Flight", e)
        pipeline_errors.append(f"preflight: {e}")
        results["preflight"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 2: AGENT 1 — MACRO DIRECTOR (8:00 AM) ━━━
    print("\n" + "━" * 40)
    print("🌍 STEP 2: AGENT 1 — MACRO DIRECTOR")
    print("━" * 40)
    
    try:
        agent1_result = run_agent1(preflight_data["macro"])
        results["agent1"] = agent1_result
        
        if agent1_result.get("success"):
            directive = agent1_result["directive"]
            print(format_directive_for_telegram(agent1_result))
            
            # Save directive
            with open("output/agent1_directive.json", "w") as f:
                json.dump(directive, f, indent=2)
            
            # Check for DEFER
            if directive.get("regime") == "DEFER":
                print("\n⚠️ REGIME: DEFER — Pipeline halted. Missing critical data.")
                return results
        elif agent1_result.get("needs_subagent"):
            print("⏳ Agent 1 needs subagent execution (no Anthropic API key)")
            print("   Run via OCPlatform: the agent will handle Claude calls")
            return results
        else:
            print(f"❌ Agent 1 FAILED: {agent1_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 1 FAILED: {e}")
        send_crash_alert("Agent 1 (Macro Director)", e)
        pipeline_errors.append(f"agent1: {e}")
        results["agent1"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 3: AGENT 2 — FUNDAMENTAL SCREENER (8:01 AM) ━━━
    print("\n" + "━" * 40)
    print("🔍 STEP 3: AGENT 2 — FUNDAMENTAL SCREENER")
    print("━" * 40)
    
    try:
        agent2_result = run_agent2(directive, preflight_data["screener_universe"])
        results["agent2"] = agent2_result
        
        if agent2_result.get("success"):
            candidates = agent2_result.get("candidates", [])
            print(format_agent2_for_telegram(agent2_result))
            
            # Save candidates
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(agent2_result, f, indent=2, default=str)
            
            if not candidates:
                print("\n📋 No candidates passed screening. Pipeline complete — no trades today.")
                return results
        else:
            print(f"❌ Agent 2 FAILED: {agent2_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 2 FAILED: {e}")
        send_crash_alert("Agent 2 (Fundamental Screener)", e)
        pipeline_errors.append(f"agent2: {e}")
        results["agent2"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 3.1: WATCHLIST BENCH ━━━
    print("\n" + "━" * 40)
    print("📋 STEP 3.1: WATCHLIST BENCH")
    print("━" * 40)
    
    try:
        wl = Watchlist()
        # Prune stale entries (>5 trading days)
        pruned = wl.prune()
        if pruned:
            print(f"  🗑️  Pruned stale watchlist entries: {', '.join(pruned)}")
        
        # Add all Agent 2 candidates to the watchlist
        for c in candidates:
            result = wl.add(c)
            status = result.get('status', 'unknown')
            ticker = result.get('ticker', c.get('ticker', '?'))
            if status == 'added':
                ema = result.get('ema_20', '?')
                print(f"  ➕ {ticker} added to watchlist (20 EMA: {ema})")
            elif status == 'already_on_watchlist':
                print(f"  ⏩ {ticker} already on watchlist")
        
        # Check which watchlist entries are at entry zones
        ready_entries = wl.check_entries()
        all_entries = wl.get_all()
        
        print(f"\n  📊 Watchlist: {len(all_entries)} total, {len(ready_entries)} READY at entry zone")
        
        for entry in all_entries:
            status_icon = "🟢" if entry.get('status') == 'READY' else "🔴"
            pct = entry.get('pct_above_ema', '?')
            print(f"  {status_icon} {entry['ticker']}: {pct}% above 20 EMA — {entry.get('status', 'WATCHING')}")
        
        if ready_entries:
            # Only pass READY candidates forward (in Agent 2 format)
            ready_candidates = promote_ready_candidates()
            # Replace candidates with only the READY ones (dedupe by ticker).
            # FIX (2026-07-06): was `candidates + ready_candidates`, which let
            # today's fresh, extended top-of-momentum names bypass the pullback
            # bench whenever ANY watchlist name was READY. Now only bench-gated
            # READY candidates trade. Dedupe guards against same-day duplicates.
            _seen = set()
            candidates = []
            for _c in ready_candidates:
                _t = _c.get("ticker")
                if _t and _t not in _seen:
                    _seen.add(_t)
                    candidates.append(_c)
            agent2_result = dict(agent2_result)
            agent2_result["candidates"] = candidates
            print(f"\n  ✅ Promoting {len(candidates)} READY candidates to Agent 3")
        else:
            print("\n  ⏸️  No watchlist candidates at entry zones today. Ideas saved for later.")
            return results
        
        results["watchlist"] = {"success": True, "total": len(all_entries), "ready": len(ready_entries)}
    except Exception as e:
        print(f"⚠️ Watchlist bench error (non-fatal): {e}")
        # On watchlist failure, fall through with original candidates
        results["watchlist"] = {"success": False, "error": str(e)}
    
    # ━━━ STEP 3.5: X/TWITTER SMART MONEY FETCH — RETIRED 2026-06-22 ━━━
    # Disabled per biweekly-review verdict: avg ~0.1 mentions/run (dead signal)
    # for $100/mo X API v2 Basic. Agent 3 handles empty mentions gracefully
    # (falls back to news + options flow + short interest). We write an empty
    # mentions file so Agent 3's loader is satisfied. To re-enable, restore the
    # fetch_x_smart_money(tickers) call below.
    print("\n" + "━" * 40)
    print("🐦 STEP 3.5: X/TWITTER SMART MONEY — DISABLED (retired)")
    print("━" * 40)

    tickers = [c.get("ticker") for c in candidates]
    x_mentions = {t: [] for t in tickers}
    with open("output/smart_money_mentions.json", "w") as smf:
        json.dump({"mentions": x_mentions, "total_mentions": 0,
                   "note": "X/Twitter fetch retired 2026-06-22"}, smf, indent=2)
    results["x_fetch"] = {"success": True, "note": "disabled"}
    # Discord is OUTPUT ONLY — no sentiment scraping from Discord channels
    
    # ━━━ STEP 4: AGENT 3 — QUALITATIVE SYNTHESIZER (8:05 AM) ━━━
    print("\n" + "━" * 40)
    print("🧪 STEP 4: AGENT 3 — QUALITATIVE SYNTHESIZER")
    print("━" * 40)
    
    try:
        agent3_result = run_agent3(agent2_result, x_mentions)
        results["agent3"] = agent3_result
        
        if agent3_result.get("success"):
            print(format_agent3_for_slack(agent3_result))
            
            # Replace agent2_result with the synthesis-filtered version
            if agent3_result.get("updated_agent2_result"):
                agent2_result = agent3_result["updated_agent2_result"]
                candidates = agent2_result.get("candidates", [])
            
            with open("output/agent3_verified.json", "w") as f:
                json.dump(agent3_result, f, indent=2, default=str)
            # Overwrite agent2 candidates with filtered set
            with open("output/agent2_candidates.json", "w") as f:
                json.dump(agent2_result, f, indent=2, default=str)
            
            if not candidates:
                print("\n🚫 All candidates vetoed by qualitative synthesis. No trades today.")
                return results
        elif agent3_result.get("needs_subagent"):
            print("⏳ Agent 3 needs subagent execution (no Anthropic API key)")
            return results
        else:
            print(f"❌ Agent 3 FAILED: {agent3_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 3 FAILED: {e}")
        send_crash_alert("Agent 3 (Synthesizer)", e)
        pipeline_errors.append(f"agent3: {e}")
        results["agent3"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 5: AGENT 4 — RISK MANAGER (8:17 AM) ━━━
    print("\n" + "━" * 40)
    print("🛡️ STEP 5: AGENT 4 — RISK MANAGER")
    print("━" * 40)
    
    try:
        agent4_result = run_agent4(agent2_result, agent3_result, directive)
        results["agent4"] = agent4_result
        
        if agent4_result.get("success"):
            tear_sheet = agent4_result.get("tear_sheet", "")
            print(tear_sheet)
            
            with open("output/agent4_orders.json", "w") as f:
                json.dump(agent4_result, f, indent=2, default=str)
            
            # Save tear sheet as text
            with open("output/tear_sheet.txt", "w") as f:
                f.write(tear_sheet)
            
            print(f"\n📋 Tear sheet saved to output/tear_sheet.txt")
        elif agent4_result.get("needs_subagent"):
            print("⏳ Agent 4A needs subagent execution (no Anthropic API key)")
            return results
        else:
            print(f"❌ Agent 4 FAILED: {agent4_result.get('error')}")
            return results
    except Exception as e:
        print(f"❌ Agent 4 FAILED: {e}")
        results["agent4"] = {"success": False, "error": str(e)}
        return results
    
    # ━━━ STEP 6: SAVE ORDERS FOR DEFERRED EXECUTION ━━━
    print("\n" + "━" * 40)
    print("💾 STEP 6: ORDERS SAVED — EXECUTION DEFERRED")
    print("━" * 40)
    
    trade_orders = agent4_result.get("trade_orders", [])
    buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
    
    if not buy_orders:
        print("📋 No BUY orders in tear sheet — nothing to execute.")
    else:
        # Save orders for deferred execution at 9:45-10:15 AM
        pending = {
            "timestamp": datetime.now().isoformat(),
            "orders": trade_orders,
            "directive": directive,
            "note": "Execute after 9:45 AM ET when VWAP has a mature volume profile",
        }
        os.makedirs("output", exist_ok=True)
        with open("output/pending_orders.json", "w") as f:
            json.dump(pending, f, indent=2)
        
        print(f"  📋 {len(buy_orders)} BUY order(s) saved to output/pending_orders.json")
        print(f"  ⏰ Execute at 9:45-10:15 AM via: python3 orchestrator.py execute")
        for o in buy_orders:
            print(f"     BUY {o.get('shares', '?')} {o.get('ticker', '?')} @ ~${o.get('entry_price', '?')}")
    
    # ━━━ ARCHIVE RUN ━━━
    try:
        archive_run("morning")
    except Exception as e:
        print(f"⚠️ Archiver failed: {e}")
    
    # ━━━ DONE ━━━
    print("\n" + "=" * 50)
    print("✅ MORNING PIPELINE COMPLETE")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("📈 Trades ready for execution.")
    print("🕒 Agent 5 will run at 3:30 PM to monitor positions.")
    print("=" * 50)
    
    # Send completion alert
    send_pipeline_complete_alert(results)
    
    return results


def run_afternoon_monitor(verbose: bool = False, mechanical_only: bool = False) -> dict:
    """Run Agent 5: position monitoring + broker execution.

    mechanical_only=True → hourly reinforcement mode: skip the Claude thesis
    review, just ratchet trailing stops and execute mechanical stop-hits.
    """
    label = "HOURLY STOP REINFORCEMENT" if mechanical_only else "AFTERNOON POSITION MONITOR"

    # Hourly reinforcement places LIVE stop orders, so it must only run while
    # the market is actually open (9:30–16:00 ET). Outside hours, broker
    # cancel/place round-trips hang. The daily 3:30 monitor is exempt (it runs
    # at the close and tolerates outside-hours behavior).
    if mechanical_only:
        try:
            from safeguards import is_market_open_today
            cal = is_market_open_today()
            if not cal.get("is_open"):
                print(f"[Hourly] 🕒 Market not open ({cal.get('reason')}). Skipping reinforcement.")
                return {"agent5": {"success": True, "note": f"market_not_open:{cal.get('reason')}"}}
        except Exception as e:
            print(f"[Hourly] ⚠️ market-hours check failed: {e}. Skipping for safety.")
            return {"agent5": {"success": False, "error": f"market_check_failed: {e}"}}

    print("=" * 50)
    print(f"🕒 OPEN CLAW — {label}")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)
    
    # Pre-flight snapshot (3:25 PM)
    print("\n" + "━" * 40)
    print("📸 AGENT 5 PRE-FLIGHT: PRICE SNAPSHOT")
    print("━" * 40)
    
    try:
        preflight = run_agent5_preflight()
        
        if not preflight["positions"]:
            print("📋 No open positions to monitor.")
            return {"agent5": {"success": True, "note": "No positions"}}
    except Exception as e:
        print(f"❌ Agent 5 pre-flight FAILED: {e}")
        return {"agent5": {"success": False, "error": str(e)}}
    
    # Agent 5 (3:30 PM)
    print("\n" + "━" * 40)
    print("🕒 AGENT 5: POSITION MONITOR")
    print("━" * 40)
    
    try:
        agent5_result = run_agent5(preflight["positions"], preflight["snapshot"],
                                   mechanical_only=mechanical_only)
        
        if agent5_result.get("success"):
            print(format_agent5_for_telegram(agent5_result))
            
            with open("output/agent5_decisions.json", "w") as f:
                json.dump(agent5_result, f, indent=2, default=str)
            
            # ━━━ EXECUTE AGENT 5 DECISIONS VIA EXECUTION ENGINE ━━━
            decisions = agent5_result.get("decisions", [])
            crisis = agent5_result.get("crisis_liquidation", False)
            # Run execution if there are ANY decisions — not just CLOSE/TRIM.
            # The old gate (only CLOSE/TRIM/crisis) silently skipped runs that
            # were pure HOLD stop-tightenings, which is exactly why trailing
            # stops never got pushed to the broker and went stale (BAC stuck
            # at \$52.31 below cost). HOLD trailing-stop updates MUST execute.
            actionable = bool(decisions) or crisis
            
            if actionable:
                print("\n" + "━" * 40)
                print("💰 EXECUTION ENGINE — AGENT 5 DECISIONS")
                print("━" * 40)
                
                try:
                    from execution_engine import ExecutionEngine
                    engine = ExecutionEngine()
                    exec_results = []
                    
                    if crisis:
                        # Crisis = liquidate everything atomically
                        positions = engine.broker.get_positions()
                        for p in positions:
                            result = engine.atomic_liquidate(p["ticker"], reason="CRISIS_LIQUIDATION")
                            exec_results.append(result)
                        print(f"  🚨 CRISIS: Atomically liquidated {len(positions)} positions")
                    else:
                        for d in decisions:
                            ticker = d.get("ticker")
                            action = d.get("action", "HOLD")
                            if action == "CLOSE":
                                result = engine.atomic_liquidate(ticker, reason=f"Agent5_CLOSE: {d.get('reasoning', '')}")
                                exec_results.append(result)
                            elif action == "TRIM":
                                # Trim = update stop to current price (let daemon handle it)
                                new_stop = d.get("new_stop", d.get("current_price", 0))
                                if new_stop > 0:
                                    engine.update_stop(ticker, new_stop, reason="Agent5_TRIM")
                                exec_results.append({"ticker": ticker, "action": "TRIM", "new_stop": new_stop})
                            elif action == "HOLD":
                                # Update trailing stop whenever the computed stop
                                # differs from what is actually LIVE (per ledger),
                                # not just when new_stop > original_stop. The old
                                # guard skipped stale stops (e.g. ledger stuck at
                                # \$52.31 while engine computed \$55.71).
                                new_stop = d.get("new_stop")
                                original_stop = d.get("original_stop")
                                live_stop = None
                                try:
                                    import sqlite3 as _sql
                                    from execution_engine import DB_PATH as _DBP
                                    with _sql.connect(_DBP, timeout=20.0) as _c:
                                        _r = _c.execute(
                                            "SELECT target_stop_price FROM active_trades "
                                            "WHERE ticker = ? AND closed_at IS NULL",
                                            (ticker,),
                                        ).fetchone()
                                        if _r:
                                            live_stop = _r[0]
                                except Exception:
                                    live_stop = None
                                baseline = live_stop if live_stop is not None else original_stop
                                needs_update = bool(new_stop) and (
                                    not baseline or baseline <= 0 or new_stop > baseline
                                )
                                if needs_update:
                                    # Atomic trailing: cancel → wait → place (synchronous)
                                    if not engine.update_trailing_stop(ticker, new_stop):
                                        # Fallback to async daemon-based update
                                        engine.update_stop(ticker, new_stop, reason="Agent5_TRAIL_fallback")
                                    print(f"  🔓 {ticker}: stop {baseline} → {new_stop} (pushed to broker)")
                                exec_results.append({"ticker": ticker, "action": "HOLD", "new_stop": new_stop, "prev_stop": baseline})
                    agent5_result["broker_results"] = exec_results
                    
                    # Load directive for trade journal
                    directive = {}
                    directive_path = "output/agent1_directive.json"
                    if os.path.exists(directive_path):
                        with open(directive_path) as f:
                            directive = json.load(f)
                    
                    snapshot = preflight.get("snapshot", {})
                    
                    for r in exec_results:
                        action = r.get("action", "unknown")
                        ticker = r.get("ticker", "ALL")
                        status = r.get("status", "unknown")
                        print(f"  [{action}] {ticker} — {status}")
                        
                        # Log closed trades to journal + penalty box for losses
                        if r.get("action") in ("LIQUIDATED", "CLOSE", "TRIM", "close", "trim", "close_all"):
                            pos_data = next((p for p in preflight.get("positions", []) if p.get("ticker") == r.get("ticker")), {})

                            # Wait for settlement and fetch actual fill price
                            import time as _time
                            _time.sleep(3.0)
                            try:
                                todays_orders = engine.broker.get_orders_today()
                                sell_order = next(
                                    (o for o in todays_orders
                                     if o.get("ticker") == r.get("ticker")
                                     and str(o.get("side", "")).lower() == "sell"
                                     and o.get("status", "").lower() in ("filled", "executed")),
                                    None,
                                )
                                real_exit_price = (
                                    float(sell_order["filled_avg_price"])
                                    if sell_order and sell_order.get("filled_avg_price")
                                    else snapshot.get(r.get("ticker", ""), {}).get("current_price", 0)
                                )
                            except Exception:
                                real_exit_price = snapshot.get(r.get("ticker", ""), {}).get("current_price", 0)

                            if pos_data and real_exit_price:
                                try:
                                    record = build_trade_record(
                                        trade_order=pos_data,
                                        directive=directive,
                                        agent3_verification={},
                                        exit_price=real_exit_price,
                                        exit_reason=f"Agent 5 {r.get('action', 'close')}",
                                    )
                                    log_close(record)
                                    print(f"  📝 Logged {r.get('ticker')} to trade journal (fill: ${real_exit_price:.2f})")

                                    # Add to penalty box if closed for a loss
                                    entry = pos_data.get("entry_price", pos_data.get("avg_entry_price", 0))
                                    if real_exit_price < entry:
                                        loss = (entry - real_exit_price) * pos_data.get("shares", 0)
                                        add_to_penalty_box(
                                            r.get("ticker", ""),
                                            loss,
                                            reason=f"Agent 5 {r.get('action', 'close')}",
                                        )
                                except Exception as je:
                                    print(f"  ⚠️ Journal log failed for {r.get('ticker')}: {je}")
                except Exception as e:
                    print(f"❌ Broker execution FAILED: {e}")
                    agent5_result["broker_error"] = str(e)
            else:
                print("\n📋 All positions HOLD — no broker action needed.")
        elif agent5_result.get("needs_subagent"):
            print("⏳ Agent 5 needs subagent execution (no Anthropic API key)")
        else:
            print(f"❌ Agent 5 FAILED: {agent5_result.get('error')}")
        
        # Send EOD hb_signal
        try:
            broker = get_broker()
            positions = broker.get_positions()
            account = broker.get_account_summary()
            
            # Calculate portfolio heat
            total_risk = sum(abs(p.get("unrealized_pl", 0)) for p in positions if p.get("unrealized_pl", 0) < 0)
            equity = account.get("equity", 100000)
            heat = (total_risk / equity * 100) if equity > 0 else 0
            
            send_hb_signal(positions=positions, portfolio_heat=heat)
        except Exception as he:
            print(f"\u26a0\ufe0f hb_signal send failed: {he}")
            send_hb_signal(errors=[str(he)])
        
        # ━━━ ARCHIVE RUN ━━━
        try:
            archive_run("monitor")
        except Exception as e:
            print(f"⚠️ Archiver failed: {e}")
        
        return {"agent5": agent5_result}
    except Exception as e:
        print(f"❌ Agent 5 FAILED: {e}")
        send_crash_alert("Agent 5 (Position Monitor)", e)
        return {"agent5": {"success": False, "error": str(e)}}


def resume_from_agent3(verbose: bool = False) -> dict:
    """
    Resume pipeline from Agent 3 (after X data has been fetched).
    Loads Agent 1 directive and Agent 2 candidates from saved files.
    """
    print("=" * 50)
    print("🔄 OPEN CLAW — RESUMING FROM AGENT 3")
    print("=" * 50)
    
    # Load saved state
    directive_path = "output/agent1_directive.json"
    candidates_path = "output/agent2_candidates.json"
    mentions_path = "output/smart_money_mentions.json"
    
    for path, name in [(directive_path, "Agent 1 directive"), 
                        (candidates_path, "Agent 2 candidates"),
                        (mentions_path, "Smart money X data")]:
        if not os.path.exists(path):
            print(f"❌ Missing {name}: {path}")
            return {"error": f"Missing {name}"}
    
    with open(directive_path) as f:
        directive = json.load(f)
    with open(candidates_path) as f:
        agent2_result = json.load(f)
    with open(mentions_path) as f:
        x_mentions = json.load(f)
    
    # Run Agent 3
    print("\n" + "━" * 40)
    print("🧪 AGENT 3 — QUALITATIVE SYNTHESIZER")
    print("━" * 40)
    
    agent3_result = run_agent3(agent2_result, x_mentions)
    if not agent3_result.get("success"):
        print(f"❌ Agent 3 FAILED: {agent3_result.get('error')}")
        return {"agent3": agent3_result}
    
    print(format_agent3_for_slack(agent3_result))
    
    # Update agent2_result with synthesis-filtered candidates
    if agent3_result.get("updated_agent2_result"):
        agent2_result = agent3_result["updated_agent2_result"]
    
    with open("output/agent3_verified.json", "w") as f:
        json.dump(agent3_result, f, indent=2, default=str)
    with open("output/agent2_candidates.json", "w") as f:
        json.dump(agent2_result, f, indent=2, default=str)
    
    # Run Agent 4
    print("\n" + "━" * 40)
    print("🛡️ AGENT 4 — RISK MANAGER")
    print("━" * 40)
    
    agent4_result = run_agent4(agent2_result, agent3_result, directive)
    if agent4_result.get("success"):
        print(agent4_result.get("tear_sheet", ""))
        with open("output/agent4_orders.json", "w") as f:
            json.dump(agent4_result, f, indent=2, default=str)
        with open("output/tear_sheet.txt", "w") as f:
            f.write(agent4_result.get("tear_sheet", ""))
        
        # Execute trades on the broker (Robinhood)
        trade_orders = agent4_result.get("trade_orders", [])
        buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]
        if buy_orders:
            print("\n" + "━" * 40)
            print("💰 EXECUTION ENGINE — LEDGER + BROKER")
            print("━" * 40)
            try:
                from execution_engine import ExecutionEngine
                engine = ExecutionEngine()

                # Verify daemon is alive before submitting trades
                if not ExecutionEngine.is_daemon_alive():
                    print("⚠️ WARNING: Execution daemon not running! Trades will be logged but stops won't auto-place.")
                    print("  Start with: python3 run_execution_daemon.py")

                fills = engine.submit_batch_intents(trade_orders)
                submitted = [f for f in fills if f.get("status") == "submitted"]
                print(f"  ✅ {len(submitted)} intents logged to execution ledger")
                print("  📡 Background daemon will route entries and attach stops")
            except Exception as e:
                print(f"❌ Execution engine FAILED: {e}")
    
    print("\n✅ Pipeline resumed and complete.")
    return {"agent3": agent3_result, "agent4": agent4_result}


def run_deferred_execution() -> dict:
    """
    Execute pending orders using PASSIVE MIDPOINT limits.
    VWAP gate removed — it caused adverse selection by buying above morning VWAP
    (i.e., crossing the spread to pay institutional algos who VWAP-slice their sells).
    Now routes limit orders at the NBBO midpoint via the ExecutionEngine.
    """
    import uuid
    import market_data
    from execution_engine import ExecutionEngine

    pending_path = "output/pending_orders.json"
    if not os.path.exists(pending_path):
        print("❌ No pending orders found. Run morning pipeline first.")
        return {"error": "no_pending_orders"}

    with open(pending_path) as f:
        pending = json.load(f)

    trade_orders = pending.get("orders", [])
    buy_orders = [o for o in trade_orders if o.get("action") == "BUY"]

    if not buy_orders:
        print("📋 No BUY orders to execute.")
        return {"success": True, "fills": []}

    print("=" * 50)
    print("💰 DEFERRED EXECUTION — PASSIVE MIDPOINT ROUTING")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
    print("=" * 50)

    engine = ExecutionEngine()

    # PRE-TRADE CHECK: Verify execution daemon is alive
    if not ExecutionEngine.is_daemon_alive():
        print("❌ ABORT: Execution daemon is not running or heartbeat is stale (>60s).")
        print("  Start it with: python3 run_execution_daemon.py")
        print("  Or: bash run_daemon.sh")
        return {"success": False, "error": "daemon_not_alive", "fills": []}
    print("✅ Execution daemon heartbeat confirmed")

    # Fetch live quotes to calculate NBBO midpoint
    tickers = [o["ticker"] for o in buy_orders]
    print(f"\n📡 Fetching live quotes for {len(tickers)} tickers...")
    live_quotes = market_data.fetch_latest_quotes(tickers)

    fills = []
    for order in buy_orders:
        ticker = order["ticker"]
        quote = live_quotes.get(ticker, {})

        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        last = quote.get("last", order.get("entry_price", 0))

        # Broken Book Guardrails
        if bid <= 0 or ask <= 0 or ask < bid:
            print(f"  🚫 REJECTED {ticker}: Order book broken (Bid: {bid}, Ask: {ask}).")
            fills.append({"ticker": ticker, "status": "rejected_broken_book"})
            engine.log_incident(
                ticker=ticker, incident_type="BROKEN_BOOK",
                bid=bid, ask=ask, target_shares=int(order.get("shares", 0)),
                root_cause="broken_order_book",
                notes=f"Bid={bid}, Ask={ask}. Order book invalid at execution time.",
            )
            continue

        midpoint = round((bid + ask) / 2.0, 2)
        spread_pct = (ask - bid) / midpoint if midpoint > 0 else 999

        # FIX (2026-07-06): tightened from 5% -> 0.75%. A 5% spread gate is
        # absurdly permissive for a large-cap momentum book (min mkt cap $100M,
        # price > $5) — 5% spreads are lottery tickets, not swing entries.
        MAX_SPREAD_PCT = 0.0075
        if spread_pct > MAX_SPREAD_PCT:
            print(f"  🚫 REJECTED {ticker}: Spread is toxic ({spread_pct*100:.2f}% wide). Bid: {bid}, Ask: {ask}")
            fills.append({"ticker": ticker, "status": "rejected_wide_spread"})
            engine.log_incident(
                ticker=ticker, incident_type="WIDE_SPREAD",
                bid=bid, ask=ask, target_shares=int(order.get("shares", 0)),
                root_cause="toxic_spread",
                notes=f"Spread {spread_pct*100:.2f}% exceeds {MAX_SPREAD_PCT*100:.2f}% threshold.",
            )
            continue

        print(f"  [NBBO] {ticker}: Bid ${bid:.2f} | Ask ${ask:.2f} | Spread {spread_pct*10000:.0f} bps")

        # ---------------------------------------------------------
        # Marketable Limit Routing
        # Cross the book by targeting the Ask + 15 bps slippage allowance.
        # This pays the spread to guarantee fill and defeat adverse selection.
        # ---------------------------------------------------------
        marketable_limit = round(ask * 1.0015, 2)

        # Safety: reject if stock gapped up > 3% from planned entry (avoid chasing)
        # Compare against the ASK (our actual fill target), not the midpoint
        entry_price = order.get("entry_price", ask)
        if entry_price > 0:
            gap_pct = (ask - entry_price) / entry_price
            if gap_pct > 0.03:
                print(f"  🚫 REJECTED {ticker}: Gapped up {gap_pct*100:.1f}% from planned entry. Avoid chasing.")
                fills.append({"ticker": ticker, "status": "rejected_gap_up", "gap_pct": round(gap_pct * 100, 1)})
                engine.log_incident(
                    ticker=ticker, incident_type="GAP_UP_REJECTION",
                    limit_price=entry_price, bid=bid, ask=ask,
                    target_shares=int(order.get("shares", 0)),
                    root_cause="gap_up_chase_prevention",
                    notes=f"Ask gapped {gap_pct*100:.1f}% above planned entry ${entry_price:.2f}.",
                )
                continue

        trade_id = str(uuid.uuid4())

        # -----------------------------------------------------------------
        # LIVE RE-SIZING (FIX 2026-07-06)
        # Previously we sent the PLANNED share count as-is. If the stock gapped
        # up (but stayed under the 3% reject), actual fill risk could ~2x the
        # budget: a +2.9% gap against a ~3% stop distance blows past the
        # MAX_RISK_PER_TRADE ceiling. Recompute shares against the LIVE fill
        # price (marketable_limit) and the planned stop so realized $-risk stays
        # at budget. Fractional-safe: Robinhood supports fractional shares, so we
        # round to 4dp instead of int()-truncating (0.9 -> 0 = dead order).
        # -----------------------------------------------------------------
        planned_shares = float(order.get("shares", 0) or 0)
        stop_price = order.get("stop_loss", 0) or 0
        # agent4 emits the per-trade $ risk as "risk_budgeted" (accept aliases too).
        risk_budget = (order.get("risk_budgeted")
                       or order.get("risk_budget")
                       or order.get("dollar_risk"))
        exec_shares = planned_shares
        per_share_risk = marketable_limit - stop_price
        if risk_budget and per_share_risk > 0:
            resized = float(risk_budget) / per_share_risk
            # Never size UP beyond the plan (plan already respects allocation caps);
            # only trim when the live fill price widened per-share risk.
            exec_shares = min(planned_shares, resized)
            if exec_shares < planned_shares:
                print(f"  ⚖️  RE-SIZED {ticker}: {planned_shares:.4f} -> {exec_shares:.4f} sh "
                      f"(live risk/sh ${per_share_risk:.2f}, budget ${float(risk_budget):.0f})")
        # Fractional-safe rounding: 4dp, floor-ish via round; guard tiny dust.
        exec_shares = round(exec_shares, 4)
        if exec_shares <= 0:
            print(f"  🚫 REJECTED {ticker}: re-sized share count rounded to 0.")
            fills.append({"ticker": ticker, "status": "rejected_zero_shares"})
            continue

        # Route intent to the Execution Ledger
        # Marketable limit: ask + 15bps to cross the spread and guarantee fills
        result = engine.submit_trade_intent(
            trade_id=trade_id,
            ticker=ticker,
            shares=exec_shares,
            limit_price=marketable_limit,
            stop_price=stop_price,
        )
        fills.append({
            "ticker": ticker,
            "status": result.get("status", "unknown"),
            "limit_price": marketable_limit,
            "order_id": result.get("order_id"),
        })
        print(f"  ✅ {ticker}: Marketable limit routed at ${marketable_limit:.2f} (Ask ${ask:.2f} + 15bps)")

    submitted = sum(1 for f in fills if f.get("status") == "submitted")
    print(f"\n📊 Results: {submitted}/{len(fills)} orders routed to execution ledger")
    print("📡 Background daemon will handle fills → stop placement")

    # Clean up pending file
    os.rename(pending_path, pending_path.replace(".json", f"_executed_{datetime.now().strftime('%Y%m%d_%H%M')}.json"))
    return {"success": True, "fills": fills}


if __name__ == "__main__":
    from safeguards import run_with_crash_protection
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    if mode == "morning":
        run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
    elif mode == "monitor":
        run_with_crash_protection(run_afternoon_monitor, "Afternoon Monitor", verbose=verbose)
    elif mode == "hourly":
        # Mechanical-only trailing-stop reinforcement (every market hour).
        run_with_crash_protection(
            lambda **kw: run_afternoon_monitor(mechanical_only=True, **kw),
            "Hourly Stop Reinforcement", verbose=verbose,
        )
    elif mode == "resume":
        run_with_crash_protection(resume_from_agent3, "Resume from Agent 3", verbose=verbose)
    elif mode == "execute":
        run_with_crash_protection(run_deferred_execution, "Deferred Execution")
    elif mode == "full":
        results = run_with_crash_protection(run_morning_pipeline, "Morning Pipeline", verbose=verbose)
        if results and all(r.get("success", False) for r in results.values() if isinstance(r, dict)):
            print("\n⏰ Morning pipeline done. Agent 5 runs at 3:30 PM.")
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python3 orchestrator.py [morning|monitor|hourly|resume|execute|full]")
```

================================================================================
FILE: performance_review.py
================================================================================
```python
"""
Open Claw - Performance Review Engine
Implements the 3-tier review system. Outputs reports to output/reviews/
and prints to console for Slack delivery.

Three tiers:
  1. Weekly Pulse — lightweight P&L summary, portfolio heat, stops hit. 30-second read.
  2. Bi-Weekly Deep Review — trade performance analysis + agent scorecards + data source audit.
  3. Monthly Parameter Review — config change recommendations based on accumulated data.

Usage:
  python3 performance_review.py              # Run all three reviews
  python3 performance_review.py weekly        # Weekly pulse only
  python3 performance_review.py biweekly      # Bi-weekly deep review only
  python3 performance_review.py monthly       # Monthly parameter review only
"""
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

JOURNAL_PATH = "journal/trades.csv"
ARCHIVE_DIR = "output/archive"
REVIEWS_DIR = "output/reviews"
OUTPUT_DIR = "output"


def load_journal(days=None):
    """Loads trade journal and filters by days back."""
    if not os.path.exists(JOURNAL_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(JOURNAL_PATH)
        if df.empty:
            return df
        # Convert date columns using UTC explicitly
        df['entry_dt'] = pd.to_datetime(df['entry_dt'], errors='coerce', utc=True)
        df['exit_dt'] = pd.to_datetime(df['exit_dt'], errors='coerce', utc=True)
        if days:
            now = datetime.now(df['exit_dt'].dt.tz) if df['exit_dt'].dt.tz else datetime.now()
            cutoff = now - timedelta(days=days)
            df = df[df['exit_dt'] >= cutoff]
        return df
    except Exception as e:
        print(f"Error loading journal: {e}")
        return pd.DataFrame()


def calculate_portfolio_heat():
    """Calculate current portfolio heat from open positions."""
    try:
        from agent4_risk_manager import calculate_portfolio_heat as calc_heat
        heat_data = calc_heat()
        return heat_data.get('heat_pct_of_equity', 0.0) * 100
    except Exception:
        return 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 1: WEEKLY PULSE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_weekly_pulse():
    """
    Lightweight weekly summary. Just the numbers, no recommendations.
    30-second read.
    """
    df = load_journal(days=7)
    report = [
        f"📊 *OPEN CLAW WEEKLY PULSE* — {datetime.now().strftime('%Y-%m-%d')}",
        "_" * 40,
        ""
    ]

    report.append(f"*Portfolio Heat:* {calculate_portfolio_heat():.1f}% of equity at risk\n")

    if df.empty:
        report.append("_Journal is currently empty. Pipeline is in early accumulation phase (Week 1)._")
    else:
        total = len(df)
        winners = df[df["pnl_dollars"] > 0]
        win_rate = (len(winners) / total) * 100
        avg_r = df["r_multiple"].mean()
        pnl = df["pnl_dollars"].sum()
        stops = len(df[df["exit_reason"].str.contains("STOP|MECHANICAL", case=False, na=False)])

        report.append("*Closed Trade Performance:*")
        report.append(f" • *Trades Closed:* {total}")
        report.append(f" • *Win Rate:* {win_rate:.0f}%")
        report.append(f" • *Avg R-Multiple:* {avg_r:.2f}R")
        report.append(f" • *Total P&L:* ${pnl:,.2f}")
        report.append(f" • *Hit Stops:* {stops} trades")

    # Execution quality — fill rate from the execution ledger
    try:
        from execution_engine import ExecutionEngine
        engine = ExecutionEngine()
        stats = engine.get_fill_rate_stats(days=7)
        incidents = engine.get_incidents(days=7)

        report.append("")
        report.append("*Execution Quality:*")
        report.append(f" • *Orders Submitted:* {stats['orders_submitted']}")
        report.append(f" • *Orders Filled:* {stats['orders_filled']}")
        report.append(f" • *Fill Rate:* {stats['fill_rate_pct']}%")
        if stats['orders_dead'] > 0:
            report.append(f" • ⚠️ *Unfilled/Dead:* {stats['orders_dead']}")
        if incidents:
            report.append(f" • *Incidents This Week:* {len(incidents)}")
            # Show last 3 incidents
            for inc in incidents[:3]:
                report.append(f"   — {inc['date']} {inc['ticker']}: {inc['incident_type']} ({inc.get('root_cause', '')})") 
    except Exception as e:
        report.append(f"\n_Execution stats unavailable: {e}_")

    return "\n".join(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA SOURCE QUALITY AUDIT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def audit_data_sources():
    """
    Comprehensive data source audit across ALL pipeline data providers.
    Grades each source: Strong 🟢, Neutral ⚪, or Weak 🔴.
    Tracks cost, reliability, and value-add.
    """
    report = ["\n*3. Data Source Quality Audit*"]
    report.append("  _Grading: 🟢 Strong | ⚪ Neutral | 🔴 Weak | 💰 Cost_")
    report.append("")

    # ── Source registry: what we use, what it costs, what it does ──
    sources = {
        "x_twitter": {"name": "X/Twitter Smart Money", "icon": "🐦", "cost": "~$100/mo (X API v2 Basic tier, X_BEARER_TOKEN)", "role": "Smart money sentiment, institutional mentions"},
        "gemini": {"name": "Gemini 3.1 Pro (Agent 2 Deep Research)", "icon": "💎", "cost": "~$0.05-0.15/run (token-based, Deep Research)", "role": "Fundamental screener — selects 1-3 candidates"},
        "market_data": {"name": "Unified Market Data (Tiingo + Yahoo)", "icon": "📈", "cost": "Tiingo free tier", "role": "Primary price quotes, prior close, historical bars"},
        "massive_technicals": {"name": "Massive API (Technicals)", "icon": "📈", "cost": "Free tier (5 calls/min)", "role": "Server-side RSI, MACD, SMA, EMA"},
        "massive_macro": {"name": "Massive API (Macro/Economy)", "icon": "🏛️", "cost": "Free tier", "role": "Treasury yields, inflation, labor market"},
        "massive_fundamentals": {"name": "Massive API (Fundamentals)", "icon": "📊", "cost": "Free tier", "role": "Financials, dividends, ticker details"},
        "assembly": {"name": "Market Sentiment (CNN F&G + yfinance)", "icon": "🏦", "cost": "Free", "role": "Sentiment composite, sub-component breadth"},
        "squeezemetrics": {"name": "SqueezMetrics DIX", "icon": "🌊", "cost": "Free (CSV)", "role": "Dark pool index — institutional accumulation/distribution"},
        "finviz": {"name": "Finviz Screener", "icon": "🔍", "cost": "Free (finvizfinance)", "role": "Dynamic stock screening (momentum, sectors, themes)"},
        "yfinance": {"name": "Yahoo Finance", "icon": "📰", "cost": "Free (yfinance)", "role": "Fallback price data, sector breadth, VIX"},
        "discord": {"name": "Discord", "icon": "💬", "cost": "Free", "role": "Output channel — signal-to-noise TBD"},
    }

    # ── Scan archived runs for reliability data ──
    runs = []
    if os.path.exists(ARCHIVE_DIR):
        runs = sorted(os.listdir(ARCHIVE_DIR))[-14:]  # Last 14 runs

    mentions_list = []
    missing_data_flags = []
    mdata_success = 0
    mdata_fail = 0
    massive_tech_success = 0
    massive_tech_fail = 0
    finviz_success = 0
    finviz_fallback = 0
    dix_success = 0
    dix_fail = 0
    assembly_stale = 0
    assembly_fresh = 0

    for run in runs:
        run_dir = os.path.join(ARCHIVE_DIR, run)
        if not os.path.isdir(run_dir):
            continue

        # Twitter/X mentions
        sm_file = os.path.join(run_dir, "smart_money_mentions.json")
        if os.path.exists(sm_file):
            try:
                with open(sm_file) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    mentions_list.append(data.get("total_mentions", 0))
                elif isinstance(data, list):
                    mentions_list.append(len(data))
            except Exception:
                pass

        # Macro audit (DIX, MOVE, assembly source)
        macro_file = os.path.join(run_dir, "preflight_macro.json")
        if os.path.exists(macro_file):
            try:
                with open(macro_file) as f:
                    macro = json.load(f)
                if isinstance(macro, dict):
                    if "DIX" not in macro or (isinstance(macro.get("DIX"), dict) and "error" in macro["DIX"]):
                        missing_data_flags.append(f"DIX missing in {run}")
                        dix_fail += 1
                    else:
                        dix_success += 1
                    if "MOVE" not in macro or (isinstance(macro.get("MOVE"), dict) and "error" in macro["MOVE"]):
                        missing_data_flags.append(f"MOVE missing in {run}")
            except Exception:
                pass

        # Technicals audit
        tech_file = os.path.join(run_dir, "technicals.json")
        if os.path.exists(tech_file):
            try:
                with open(tech_file) as f:
                    tech = json.load(f)
                errors = sum(1 for v in tech.values() if isinstance(v, dict) and "error" in v)
                if errors == 0:
                    massive_tech_success += 1
                else:
                    massive_tech_fail += 1
            except Exception:
                massive_tech_fail += 1

        # Screener source audit
        screener_file = os.path.join(run_dir, "screener_universe.json")
        if os.path.exists(screener_file):
            try:
                with open(screener_file) as f:
                    screen = json.load(f)
                if isinstance(screen, list) and screen:
                    sources_used = set(t.get("source", "") for t in screen)
                    if "finviz_dynamic" in sources_used:
                        finviz_success += 1
                    elif "hardcoded_fallback" in sources_used:
                        finviz_fallback += 1
            except Exception:
                pass

        # Market sentiment freshness
        # public_market_data = live CNN F&G + yfinance proxies (the current,
        # intended source). Legacy public_api_fallback also counts as fresh
        # since it's the same live public data under the old label. Anything
        # else (e.g. an empty/missing file) counts as stale.
        assembly_file = os.path.join(run_dir, "assembly_data.json")
        if os.path.exists(assembly_file):
            try:
                with open(assembly_file) as f:
                    asm = json.load(f)
                src = asm.get("source")
                has_sentiment = bool(asm.get("sentiment", {}).get("composite_score"))
                if src in ("public_market_data", "public_api_fallback") and has_sentiment:
                    assembly_fresh += 1
                elif has_sentiment:
                    assembly_fresh += 1
                else:
                    assembly_stale += 1
            except Exception:
                assembly_stale += 1

    total_runs = max(len(runs), 1)

    # ── Grade each source ──

    # X/Twitter — RETIRED 2026-06-22 (dead signal: avg ~0.1 mentions/run)
    report.append("  🐦 *X/Twitter Smart Money:* ⚫ — _RETIRED 2026-06-22 (dead signal, ~0.1 mentions/run)_ 💰 $0 (disabled)")

    # Unified Market Data (Tiingo + Yahoo)
    mdata_file = os.path.join(OUTPUT_DIR, "screener_universe.json")
    if os.path.exists(mdata_file):
        try:
            with open(mdata_file) as f:
                su = json.load(f)
            mdata_tickers = [t for t in su if isinstance(t, dict) and t.get("source") not in ("hardcoded_fallback",)]
            if mdata_tickers:
                report.append(f"  📈 *Market Data (Tiingo+Yahoo):* 🟢 — _Primary source for {len(mdata_tickers)} tickers_ 💰 Free")
            else:
                report.append("  📈 *Market Data (Tiingo+Yahoo):* ⚪ — _Not primary in latest run_ 💰 Free")
        except Exception:
            report.append("  📈 *Market Data (Tiingo+Yahoo):* ⚪ — _Unable to assess_ 💰 Free")
    else:
        report.append("  📈 *Market Data (Tiingo+Yahoo):* ⚪ — _No screener data to assess_ 💰 Free")

    # Massive Technicals
    if massive_tech_success + massive_tech_fail > 0:
        tech_rate = massive_tech_success / (massive_tech_success + massive_tech_fail) * 100
        if tech_rate >= 80:
            report.append(f"  📈 *Massive Technicals:* 🟢 — _{tech_rate:.0f}% clean runs ({massive_tech_success}/{massive_tech_success + massive_tech_fail})_ 💰 Free tier")
        elif tech_rate >= 50:
            report.append(f"  📈 *Massive Technicals:* ⚪ — _{tech_rate:.0f}% clean runs — some errors_ 💰 Free tier")
        else:
            report.append(f"  📈 *Massive Technicals:* 🔴 — _Only {tech_rate:.0f}% clean runs — check rate limits_ 💰 Free tier")
    elif os.path.exists(os.path.join(OUTPUT_DIR, "technicals.json")):
        report.append("  📈 *Massive Technicals:* 🟢 — _Data present, no archive history yet_ 💰 Free tier")
    else:
        report.append("  📈 *Massive Technicals:* 🔴 — _No technicals data found_ 💰 Free tier")

    # Massive Macro (NEW)
    report.append("  🏛️ *Massive Macro:* 🟢 — _Treasury yields, inflation, labor data — unique to Massive (Schwab doesn't have this)_ 💰 Free tier")

    # Massive Fundamentals (NEW)
    report.append("  📊 *Massive Fundamentals:* 🟢 — _Financials, dividends, ticker details — supplements Finviz_ 💰 Free tier")

    # Market Sentiment (live public market data: CNN F&G + yfinance proxies)
    if assembly_fresh + assembly_stale > 0:
        fresh_rate = assembly_fresh / (assembly_fresh + assembly_stale) * 100
        if fresh_rate >= 90:
            report.append(f"  🏦 *Market Sentiment:* 🟢 — _{fresh_rate:.0f}% live ({assembly_fresh}/{assembly_fresh + assembly_stale} runs) — CNN F&G + yfinance_ 💰 Free")
        elif fresh_rate >= 60:
            report.append(f"  🏦 *Market Sentiment:* ⚪ — _{fresh_rate:.0f}% live — some runs missing sentiment_ 💰 Free")
        else:
            report.append(f"  🏦 *Market Sentiment:* 🔴 — _Only {fresh_rate:.0f}% live — sentiment fetch failing, check CNN F&G / yfinance_ 💰 Free")
    else:
        asm_grade = "🟢" if not missing_data_flags else "🔴"
        report.append(f"  🏦 *Market Sentiment:* {asm_grade} — _{'Clean data' if not missing_data_flags else 'Missing DIX/MOVE data'}_ 💰 Free")

    # SqueezMetrics DIX
    if dix_success + dix_fail > 0:
        dix_rate = dix_success / (dix_success + dix_fail) * 100
        if dix_rate >= 80:
            report.append(f"  🌊 *SqueezMetrics DIX:* 🟢 — _{dix_rate:.0f}% available ({dix_success}/{dix_success + dix_fail} runs)_ 💰 Free")
        else:
            report.append(f"  🌊 *SqueezMetrics DIX:* 🔴 — _Only {dix_rate:.0f}% available — CSV feed unreliable_ 💰 Free")
    else:
        report.append("  🌊 *SqueezMetrics DIX:* ⚪ — _No archive data to assess_ 💰 Free")

    # Finviz
    if finviz_success + finviz_fallback > 0:
        fv_rate = finviz_success / (finviz_success + finviz_fallback) * 100
        if fv_rate >= 80:
            report.append(f"  🔍 *Finviz Screener:* 🟢 — _{fv_rate:.0f}% dynamic screens ({finviz_success}/{finviz_success + finviz_fallback})_ 💰 Free")
        elif fv_rate >= 50:
            report.append(f"  🔍 *Finviz Screener:* ⚪ — _{fv_rate:.0f}% dynamic, rest hardcoded fallback_ 💰 Free")
        else:
            report.append(f"  🔍 *Finviz Screener:* 🔴 — _Only {fv_rate:.0f}% dynamic — frequently falling back to hardcoded list_ 💰 Free")
    else:
        report.append("  🔍 *Finviz Screener:* ⚪ — _No archive data to assess_ 💰 Free")

    # yfinance
    report.append("  📰 *Yahoo Finance:* ⚪ — _Fallback source for prices, VIX, sector breadth_ 💰 Free")

    # Discord
    report.append("  💬 *Discord:* ⚪ — _Output only — signal-to-noise TBD_ 💰 Free")

    # ── Cost summary ──
    report.append("")
    report.append("  *💰 Total Monthly API Cost: ~$100-105/mo*")
    report.append("  _Breakdown: X API v2 Basic ~$100/mo (flat) + Gemini 3.1 Pro Agent 2 ~$1-4/mo (token-based, ~$0.05-0.15/run × ~21 trading days). All other sources free-tier._")
    report.append("  _Massive free tier (5 calls/min) sufficient for daily runs. Upgrade only if going intraday._")

    # ── Value assessment ──
    report.append("")
    report.append("  *📋 Value Assessment:*")
    report.append("  _HIGH VALUE:_ Massive Macro (unique data), DIX (institutional flow)")
    report.append("  _MEDIUM VALUE:_ Massive Technicals (saves compute), Finviz (dynamic screening), Market Sentiment (CNN F&G)")
    report.append("  _MONITOR:_ Discord (noise?), yfinance (reliability)")

    return "\n".join(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 2: BI-WEEKLY DEEP REVIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_biweekly_deep():
    """
    Deep review with two sections:
    1. Trade Performance Analysis (tier performance, R-multiples, MAE/MFE, beta check)
    2. Agent Performance Scorecards (per-agent accuracy)
    3. Data Source Quality Audit (X/Twitter, Discord, macro, technicals)
    """
    df = load_journal(days=14)
    report = [
        f"🔍 *OPEN CLAW BI-WEEKLY DEEP REVIEW* — {datetime.now().strftime('%Y-%m-%d')}",
        "_" * 40,
        ""
    ]

    # ── Section 1: Trade Performance ──
    report.append("*1. Trade Performance Analysis*")
    if df.empty:
        report.append("  _Insufficient closed trade data for quantitative attribution._")
    else:
        # Tier R-multiples
        if "tier" in df.columns and "r_multiple" in df.columns:
            tier_r = df.groupby("tier")["r_multiple"].agg(["count", "mean"])
            for tier, row in tier_r.iterrows():
                report.append(f"  • *{tier} Picks:* {row['mean']:.2f}R avg ({int(row['count'])} trades)")

        # CONFIRM_ENHANCED alpha
        if "confirm_enhanced" in df.columns and "r_multiple" in df.columns:
            conf = df.groupby("confirm_enhanced")["r_multiple"].mean().to_dict()
            ce = conf.get(True, conf.get("True", 0))
            reg = conf.get(False, conf.get("False", 0))
            report.append(f"  • *CONFIRM_ENHANCED:* {ce:.2f}R vs {reg:.2f}R (Standard)")

        # MAE analysis
        if "max_adverse_excursion_pct" in df.columns:
            mae = pd.to_numeric(df["max_adverse_excursion_pct"], errors='coerce').mean()
            if pd.notna(mae):
                report.append(f"  • *Avg MAE:* {mae:.2f}% (Stop-loss tightness check)")

        # SPX beta check
        if "spx_change_over_hold_pct" in df.columns:
            spx = pd.to_numeric(df["spx_change_over_hold_pct"], errors='coerce')
            r = pd.to_numeric(df["r_multiple"], errors='coerce')
            if not spx.isna().all() and not r.isna().all() and len(df) > 3:
                corr = r.corr(spx)
                report.append(f"  • *SPX Beta Check:* {corr:.2f} correlation")
                if abs(corr) > 0.7:
                    report.append("    ⚠️ High SPX correlation — may just be beta, not alpha")

        # Binding constraints
        if "binding_constraint" in df.columns:
            bc = df["binding_constraint"].value_counts().to_dict()
            bc_str = ", ".join(f"{k}: {v}" for k, v in bc.items())
            report.append(f"  • *Binding Constraints:* {bc_str}")

    # ── Section 2: Agent Scorecards ──
    report.append("\n*2. Agent Performance Scorecards*")

    report.append("  🎭 *Agent 1 (Macro Director):*")
    report.append("  _Regime tracking active. Awaiting SPX/VIX 1-2 day correlation to score accuracy._")

    report.append("  🔍 *Agent 2 (Fundamental Screener):*")
    if df.empty:
        report.append("  _Pick profitability pending closed trades._")
    else:
        win_rate = (len(df[df["pnl_dollars"] > 0]) / len(df)) * 100
        report.append(f"  _Pick Profitability:_ {win_rate:.0f}%")

    report.append("  🧪 *Agent 3 (Synthesizer):*")
    if df.empty:
        report.append("  _CONFIRM_ENHANCED alpha pending closed trades._")
    else:
        report.append("  _Tracking CONFIRM_ENHANCED outcomes vs regular verdicts._")

    report.append("  🛡️ *Agent 4 (Risk Manager):*")
    report.append("  _Stop tightness (MAE) being monitored. Allocation logic functioning._")

    report.append("  📉 *Agent 5 (Position Monitor):*")
    report.append("  _HOLD/SELL decisions being tracked against subsequent price drift._")

    # ── Section 3: Data Source Audit ──
    report.append(audit_data_sources())

    return "\n".join(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIER 3: MONTHLY PARAMETER REVIEW
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_monthly_params():
    """
    Monthly review that evaluates config.py parameters against trade data.
    The ONLY time actual config changes get recommended.
    """
    df = load_journal(days=30)
    report = [
        f"⚙️ *OPEN CLAW MONTHLY PARAMETER REVIEW* — {datetime.now().strftime('%Y-%m-%d')}",
        "_" * 40,
        ""
    ]

    if len(df) < 10:
        report.append("⚠️ *Not enough data yet to confidently recommend configuration changes.*")
        report.append(f"_Have {len(df)} closed trades. Need ~10-20 to statistically validate multiplier adjustments._")
        return "\n".join(report)

    report.append("*Configuration Change Recommendations:*\n")

    # Tier risk multiplier check
    if "tier" in df.columns and "r_multiple" in df.columns:
        tier_mean = df.groupby("tier")["r_multiple"].mean()
        exc = tier_mean.get("EXCEPTIONAL", 0)
        strong = tier_mean.get("STRONG", 0)
        pas = tier_mean.get("PASS", 0)

        if exc < pas:
            report.append("  • *TIER_RISK_MULT:* ⚠️ EXCEPTIONAL is underperforming PASS. Recommend lowering EXCEPTIONAL multiplier or investigating pick quality.")
        elif exc < strong:
            report.append("  • *TIER_RISK_MULT:* ⚠️ EXCEPTIONAL underperforming STRONG. Monitor — may need recalibration.")
        else:
            report.append("  • *TIER_RISK_MULT:* ✅ Aligned correctly (EXCEPTIONAL > STRONG > PASS).")

    # Allocation cap check
    if "binding_constraint" in df.columns:
        alloc_bound = len(df[df["binding_constraint"] == "allocation"]) / len(df)
        if alloc_bound > 0.7:
            report.append(f"  • *MAX_ALLOCATION_PCT:* ⚠️ {alloc_bound*100:.0f}% of trades are allocation-bound. Consider raising cap.")
        elif alloc_bound < 0.2:
            report.append(f"  • *MAX_ALLOCATION_PCT:* Consider tightening. Only {alloc_bound*100:.0f}% are allocation-bound (trades mostly risk-bound).")
        else:
            report.append("  • *MAX_ALLOCATION_PCT:* ✅ Risk vs Allocation balance is healthy.")

    # Stop-loss tightness
    if "max_adverse_excursion_pct" in df.columns:
        losers = df[df["r_multiple"] < 0]
        if not losers.empty:
            mae = pd.to_numeric(losers["max_adverse_excursion_pct"], errors='coerce').mean()
            if pd.notna(mae) and mae > -2.0:
                report.append("  • *Stop Distances:* ⚠️ Losers are getting stopped out with very little adverse excursion. Consider widening stops.")
            elif pd.notna(mae):
                report.append(f"  • *Stop Distances:* ✅ Avg loser MAE is {mae:.1f}% — stops appear appropriately placed.")

    # Win rate sanity check
    total = len(df)
    winners = len(df[df["pnl_dollars"] > 0])
    win_rate = winners / total * 100
    avg_r = df["r_multiple"].mean()
    report.append(f"\n  📊 *Overall:* {win_rate:.0f}% win rate, {avg_r:.2f}R avg across {total} trades")

    if avg_r < 0:
        report.append("  ⚠️ *Negative average R — system is losing money. Priority: review stop placement and entry criteria.*")

    return "\n".join(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all_reviews():
    """Run all three review tiers and save to output/reviews/."""
    os.makedirs(REVIEWS_DIR, exist_ok=True)

    pulse = generate_weekly_pulse()
    deep = generate_biweekly_deep()
    params = generate_monthly_params()

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    with open(os.path.join(REVIEWS_DIR, f"weekly_pulse_{ts}.txt"), "w") as f:
        f.write(pulse)
    with open(os.path.join(REVIEWS_DIR, f"biweekly_deep_review_{ts}.txt"), "w") as f:
        f.write(deep)
    with open(os.path.join(REVIEWS_DIR, f"monthly_params_{ts}.txt"), "w") as f:
        f.write(params)

    print(pulse)
    print("\n" + "=" * 50 + "\n")
    print(deep)
    print("\n" + "=" * 50 + "\n")
    print(params)

    return {
        "weekly_pulse": pulse,
        "biweekly_deep": deep,
        "monthly_params": params,
    }


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "weekly":
        print(generate_weekly_pulse())
    elif mode == "biweekly":
        print(generate_biweekly_deep())
    elif mode == "monthly":
        print(generate_monthly_params())
    else:
        run_all_reviews()
```

================================================================================
FILE: preflight.py
================================================================================
```python
"""
Pre-Flight Data Fetch — runs at 7:55 AM ET
Fetches:
1. Yesterday's close prices (NOT live/intraday) — Tweak #6
2. SCREENER_UNIVERSE from Finviz ($100M+ mkt cap, >$5 price)
3. FRED macro data (MOVE index, credit spreads)
4. Smart money Twitter mentions (placeholder until API is wired)

All data is saved to output/ for agents to consume.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import socket
# Global safety net: never let a hung Yahoo/HTTP socket freeze the whole pipeline.
# yfinance's yf.download() has no per-call timeout, so we set a default at the socket layer.
socket.setdefaulttimeout(30)

import yfinance as yf

from config import SCREENER_MIN_MARKET_CAP, SCREENER_MIN_PRICE

# Unified market data — Tiingo primary, Yahoo Finance fallback
try:
    import market_data as mdata
    MARKET_DATA_AVAILABLE = True
    print("[Pre-Flight] Unified Market Data: AVAILABLE (Tiingo + Yahoo Finance)")
except Exception as e:
    MARKET_DATA_AVAILABLE = False
    print(f"[Pre-Flight] Unified Market Data: UNAVAILABLE ({e}) — using yfinance directly")

# Massive (Polygon-compatible) — technical indicators (SMA, RSI, MACD)
try:
    import massive_data as massive
    from config import MASSIVE_API_KEY
    MASSIVE_AVAILABLE = bool(MASSIVE_API_KEY)
    if MASSIVE_AVAILABLE:
        print("[Pre-Flight] Massive Market Data: AVAILABLE (technical indicators)")
    else:
        print("[Pre-Flight] Massive Market Data: KEY NOT SET — skipping")
except Exception as e:
    MASSIVE_AVAILABLE = False
    print(f"[Pre-Flight] Massive Market Data: UNAVAILABLE ({e})")

# ITC (Into The Cryptoverse) — crypto risk, macro recession risk, dominance
try:
    import itc_data as itc
    ITC_AVAILABLE = True
    print("[Pre-Flight] ITC Data Module: AVAILABLE")
except Exception as e:
    ITC_AVAILABLE = False
    print(f"[Pre-Flight] ITC Data Module: UNAVAILABLE ({e})")

# FedWatch — rate expectations from Fed Funds futures
try:
    import fedwatch as fw
    FEDWATCH_AVAILABLE = True
    print("[Pre-Flight] FedWatch Module: AVAILABLE")
except Exception as e:
    FEDWATCH_AVAILABLE = False
    print(f"[Pre-Flight] FedWatch Module: UNAVAILABLE ({e})")


def _yf_download_shim(ticker, start=None, end=None, progress=False, **kwargs):
    """
    Drop-in replacement for yf.download(ticker, start=, end=) that is
    Tiingo-FIRST (via market_data.fetch_historical_bars) and only falls back
    to Yahoo for symbols Tiingo can't serve (e.g. 2YY=F).

    Returns a pandas DataFrame with columns Open/High/Low/Close/Volume and a
    DatetimeIndex, matching the shape downstream code expects from yfinance.
    Returns an EMPTY DataFrame on failure so existing `data.empty` checks work.
    """
    import pandas as pd

    # Estimate the lookback window in days from start/end if given.
    days = 30
    try:
        if start is not None and end is not None:
            days = max((end - start).days, 5)
        elif start is not None:
            days = max((datetime.now() - start).days, 5)
    except Exception:
        days = 30

    bars = None
    if MARKET_DATA_AVAILABLE:
        try:
            res = mdata.fetch_historical_bars([ticker], days=days, timeframe="day")
            entry = res.get(ticker, {}) if isinstance(res, dict) else {}
            if entry.get("count", 0) > 0:
                bars = entry["bars"]
        except Exception:
            bars = None

    # Last-resort: raw yfinance (only if Tiingo path produced nothing).
    if not bars:
        try:
            return yf.download(ticker, start=start, end=end, progress=progress, **kwargs)
        except Exception:
            return pd.DataFrame()

    # Build a DataFrame that mimics yfinance output.
    try:
        idx = pd.to_datetime([b["date"] for b in bars])
        df = pd.DataFrame({
            "Open": [b["open"] for b in bars],
            "High": [b["high"] for b in bars],
            "Low": [b["low"] for b in bars],
            "Close": [b["close"] for b in bars],
            "Volume": [b["volume"] for b in bars],
        }, index=idx)
        return df
    except Exception:
        return pd.DataFrame()

OUTPUT_DIR = "output"

ASSEMBLY_STALE_HOURS = 18  # Assembly data older than this triggers fresh fetch from public APIs
ITC_STALE_HOURS = 18  # ITC data older than this is considered stale


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch YESTERDAY's regular-session close for a list of tickers.
    This is critical — all pricing and stop calculations use prior close,
    NOT live/intraday pre-market data (Tweak #6).
    
    Primary: Tiingo + Yahoo Finance (unified market data)
    Fallback: Yahoo Finance direct
    """
    # Try unified market data first
    if MARKET_DATA_AVAILABLE:
        try:
            results = mdata.fetch_prior_close(tickers)
            ok_count = sum(1 for v in results.values() if "error" not in v)
            if ok_count >= len(tickers) * 0.5:
                print(f"[Pre-Flight] Prior close: {ok_count}/{len(tickers)} tickers from unified data")
                # Fill gaps with yfinance
                failed = [t for t, v in results.items() if "error" in v]
                if failed:
                    print(f"[Pre-Flight] Falling back to yfinance for {len(failed)} tickers: {failed[:5]}...")
                    yf_results = _fetch_prior_close_yfinance(failed)
                    results.update(yf_results)
                return results
            else:
                print(f"[Pre-Flight] Too many errors ({ok_count}/{len(tickers)}) — falling back to yfinance")
        except Exception as e:
            print(f"[Pre-Flight] Unified data prior_close failed: {e} — falling back to yfinance")

    return _fetch_prior_close_yfinance(tickers)


def _fetch_prior_close_yfinance(tickers: list) -> dict:
    """Original yfinance-based prior close fetch (fallback)."""
    results = {}
    end = datetime.now()
    start = end - timedelta(days=10)

    for ticker in tickers:
        try:
            data = _yf_download_shim(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            close_prices = data["Close"]
            if len(close_prices) >= 2:
                if str(close_prices.index[-1].date()) == str(datetime.now().date()):
                    prior_close = float(close_prices.iloc[-2].item())
                    prior_date = str(close_prices.index[-2].date())
                else:
                    prior_close = float(close_prices.iloc[-1].item())
                    prior_date = str(close_prices.index[-1].date())
            else:
                prior_close = float(close_prices.iloc[-1].item())
                prior_date = str(close_prices.index[-1].date())

            closes = [float(c) for c in data["Close"].values.flatten()]

            results[ticker] = {
                "prior_close": round(prior_close, 2),
                "prior_date": prior_date,
                "closes_30d": [round(c, 2) for c in closes],
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_macro_data() -> dict:
    """
    Fetch macro indicators for Agent 1.
    Replaced S&P 500, DXY, Gold with MOVE, DIX, Sector Breadth per Jamie's tweaks.
    
    - VIX: ^VIX
    - MOVE index: via FRED API (or proxy)
    - DIX: Dark Index (from squeezemetrics — needs separate fetch)
    - 10Y/2Y yields: ^TNX, 2YY=F
    - HY credit spread proxy: HYG vs LQD
    - Sector breadth: % of S&P sectors above 20-day MA
    """
    macro = {}

    # --- Tickers we can get from yfinance ---
    yf_tickers = {
        "VIX": "^VIX",
        "TNX_10Y": "^TNX",
        "TWO_YEAR": "2YY=F",
        "HYG": "HYG",
        "LQD": "LQD",
    }

    end = datetime.now()
    start = end - timedelta(days=30)

    for name, ticker in yf_tickers.items():
        try:
            data = _yf_download_shim(ticker, start=start, end=end, progress=False)
            if data.empty:
                macro[name] = {"error": f"No data for {ticker}"}
                continue

            # VIX pre-market noise filter: before 9:30 ET, use prior day's close
            # to avoid illiquid option book spreads causing fake spikes
            import pytz
            now_et = datetime.now(pytz.timezone('US/Eastern'))
            # FIX (2026-07-06): parenthesize the time check. Without these parens,
            # `and` bound tighter than `or`, so the guard applied to ALL tickers
            # between 9:00-9:29 ET, not just VIX.
            if name == "VIX" and (now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30)):
                if len(data) >= 2 and str(data.index[-1].date()) == str(now_et.date()):
                    current = float(data["Close"].iloc[-2].item())
                    print(f"[Pre-Flight] \U0001f6e1 VIX Guard: Using prior close {current} to avoid pre-market noise.")
                else:
                    current = float(data["Close"].iloc[-1].item())
            else:
                current = float(data["Close"].iloc[-1].item())

            prev_5d = float(data["Close"].iloc[-5].item()) if len(data) >= 5 else current
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current

            macro[name] = {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
            }
        except Exception as e:
            macro[name] = {"error": str(e)}

    # Yield curve spread
    if "TNX_10Y" in macro and "TWO_YEAR" in macro:
        if "current" in macro["TNX_10Y"] and "current" in macro["TWO_YEAR"]:
            macro["YIELD_CURVE_SPREAD"] = round(
                macro["TNX_10Y"]["current"] - macro["TWO_YEAR"]["current"], 2
            )

    # HY spread proxy (HYG/LQD ratio) — kept as FALLBACK only.
    if "HYG" in macro and "LQD" in macro:
        if "current" in macro["HYG"] and "current" in macro["LQD"]:
            macro["HY_SPREAD_PROXY"] = round(
                macro["HYG"]["current"] / macro["LQD"]["current"], 4
            )

    # --- HY Credit Spread (REAL — ICE BofA HY OAS via FRED) ---
    # FIX (2026-07-06): primary credit-stress signal. HYG/LQD conflates duration
    # with credit; BAMLH0A0HYM2 is the clean spread. Falls back to the proxy above.
    macro["HY_OAS"] = fetch_hy_oas()

    # --- MOVE Index (bond volatility) ---
    # MOVE is available via FRED as "MOVE" or as a proxy via ^MOVE
    # Trying FRED first, falling back to a note
    macro["MOVE"] = fetch_move_index()

    # --- DIX (Dark Index) ---
    # DIX comes from squeezemetrics.com — not available via yfinance/FRED
    # Requires a separate scrape or API
    macro["DIX"] = fetch_dix()

    # --- Sector Breadth ---
    macro["SECTOR_BREADTH"] = fetch_sector_breadth()

    macro["timestamp"] = datetime.now().isoformat()
    macro["price_source"] = "prior_close"  # Flag that we're using yesterday's close

    return macro


def fetch_move_index() -> dict:
    """
    Fetch MOVE index (Merrill Lynch Option Volatility Estimate).
    Measures Treasury/bond market volatility.
    Uses ^MOVE on yfinance (confirmed working), with FRED as fallback.
    """
    # Primary: yfinance ^MOVE
    try:
        end = datetime.now()
        start = end - timedelta(days=30)
        data = _yf_download_shim("^MOVE", start=start, end=end, progress=False)
        if not data.empty and len(data) >= 5:
            # MOVE pre-market noise filter (same as VIX)
            import pytz
            now_et = datetime.now(pytz.timezone('US/Eastern'))
            if now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30):
                if len(data) >= 2 and str(data.index[-1].date()) == str(now_et.date()):
                    current = float(data["Close"].iloc[-2].item())
                    print(f"[Pre-Flight] \U0001f6e1 MOVE Guard: Using prior close {current} to avoid pre-market noise.")
                else:
                    current = float(data["Close"].iloc[-1].item())
            else:
                current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item())
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current
            return {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
                "source": "yfinance ^MOVE",
            }
    except Exception:
        pass

    # Fallback: FRED API
    fred_key = os.environ.get("FRED_API_KEY", "")
    if fred_key:
        try:
            import requests
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": "BAMLMOVE",
                "api_key": fred_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 30,
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            obs = [o for o in data.get("observations", []) if o.get("value") != "."]
            if obs:
                current = float(obs[0]["value"])
                prev_5 = float(obs[min(4, len(obs)-1)]["value"])
                return {
                    "current": round(current, 2),
                    "5d_ago": round(prev_5, 2),
                    "5d_change_pct": round((current - prev_5) / prev_5 * 100, 2),
                    "date": obs[0]["date"],
                    "source": "FRED",
                }
        except Exception:
            pass

    return {"error": "MOVE index unavailable"}


def fetch_hy_oas() -> dict:
    """
    FIX (2026-07-06): fetch the REAL high-yield credit spread — ICE BofA US High
    Yield Option-Adjusted Spread (FRED series BAMLH0A0HYM2) — instead of relying on
    the HYG/LQD price ratio, which conflates DURATION with credit (LQD ~8.5y vs
    HYG ~3.5y, so a rates rally reads as false 'credit stress relief'). OAS is the
    clean credit-stress signal Agent 1's regime classifier should key off.

    Returns {current (bps as %), 5d_ago, 5d_change_pct, date, source} or {error}.
    """
    fred_key = os.environ.get("FRED_API_KEY", "")
    if not fred_key:
        return {"error": "FRED_API_KEY not set — HY OAS unavailable (using HYG/LQD proxy)"}
    try:
        import requests
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "BAMLH0A0HYM2",
            "api_key": fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 30,
        }
        resp = requests.get(url, params=params, timeout=10)
        obs = [o for o in resp.json().get("observations", []) if o.get("value") not in (".", None)]
        if obs:
            current = float(obs[0]["value"])
            prev_5 = float(obs[min(4, len(obs) - 1)]["value"])
            widening = current > prev_5
            return {
                "current": round(current, 2),           # percentage points (e.g. 3.15 = 315bps)
                "5d_ago": round(prev_5, 2),
                "5d_change_pct": round((current - prev_5) / prev_5 * 100, 2) if prev_5 else 0,
                "date": obs[0]["date"],
                "source": "FRED BAMLH0A0HYM2 (HY OAS)",
                "interpretation": "WIDENING (credit stress rising)" if widening else "tightening (credit calm)",
            }
    except Exception as e:
        return {"error": f"HY OAS fetch failed: {e}"}
    return {"error": "HY OAS unavailable"}


def fetch_dix() -> dict:
    """
    Fetch DIX (Dark Index) from squeezemetrics public CSV.
    Endpoint: https://squeezemetrics.com/monitor/static/DIX.csv
    Expected columns: date, price, dix, gex (ascending order by date).

    Returns {"current", "5d_ago", "20d_ago", "5d_change_pct", "date",
            "source", "interpretation"} on success,
            {"error": ...} on failure (Agent 1 will treat as soft-missing).
    """
    import csv
    import io
    import time
    import requests

    URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
    CACHE_PATH = f"{OUTPUT_DIR}/dix_cache.csv"
    MAX_RETRIES = 3

    # --- Fetch with retry + backoff; cache last-good CSV on success ---
    # squeezemetrics' free CSV intermittently times out / rate-limits (~1 in 3
    # morning fetches whiffed historically -> "67% available"). Retry first,
    # then fall back to the last-good cached CSV so we use yesterday's value
    # instead of returning empty.
    csv_text = None
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                URL,
                timeout=15,
                headers={"User-Agent": "open-claw/1.0 (research)"},
            )
            resp.raise_for_status()
            csv_text = resp.text
            # Cache the raw last-good CSV for future fallback
            try:
                with open(CACHE_PATH, "w") as cf:
                    cf.write(csv_text)
            except Exception:
                pass  # cache write is best-effort
            break
        except requests.HTTPError as e:
            last_err = f"DIX HTTP {e.response.status_code} from squeezemetrics"
        except requests.RequestException as e:
            last_err = f"DIX fetch failed: {e}"
        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)  # 2s, 4s backoff

    # All live attempts failed -> try last-good cache
    used_cache = False
    if csv_text is None:
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH) as cf:
                    csv_text = cf.read()
                used_cache = True
                print(f"[Pre-Flight] \u26a0\ufe0f DIX live fetch failed ({last_err}) \u2014 using last-good cached CSV")
            except Exception as e:
                return {"error": f"{last_err}; cache read also failed: {e}"}
        else:
            return {"error": f"{last_err}; no cache available"}

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        # Normalize column keys to lowercase
        rows = [{k.lower(): v for k, v in r.items()} for r in reader]
    except Exception as e:
        return {"error": f"DIX CSV parse failed: {e}"}

    if len(rows) < 20:
        return {"error": f"DIX CSV had only {len(rows)} rows (need >=20)"}

    def _f(row, key):
        try:
            v = row.get(key)
            return float(v) if v not in (None, "", ".") else None
        except (TypeError, ValueError):
            return None

    latest = _f(rows[-1], "dix")
    prev_5 = _f(rows[-6], "dix") if len(rows) >= 6 else None
    prev_20 = _f(rows[-21], "dix") if len(rows) >= 21 else None
    date_str = rows[-1].get("date", "unknown")

    if latest is None:
        return {"error": "DIX CSV: could not parse latest value"}

    # squeezemetrics returns DIX as decimal (e.g., 0.4465 = 44.65%)
    # Normalize to percentage if value is < 1.0
    if latest < 1.0:
        latest = latest * 100
        if prev_5 is not None:
            prev_5 = prev_5 * 100
        if prev_20 is not None:
            prev_20 = prev_20 * 100

    # Sanity: DIX historically lives 35-50. Outside [20, 60] = format change or bad day.
    if not (20.0 <= latest <= 60.0):
        return {
            "error": f"DIX value {latest} outside plausible range [20,60] — feed format may have changed",
            "raw_value": latest,
        }

    interpretation = (
        "HIGH (>45) — institutional accumulation"
        if latest > 45
        else "LOW (<40) — distribution"
        if latest < 40
        else "NEUTRAL (40-45)"
    )

    # --- GEX (Gamma Exposure) --- also in the CSV, free data we were ignoring
    gex_latest = _f(rows[-1], "gex")
    gex_prev_5 = _f(rows[-6], "gex") if len(rows) >= 6 else None
    gex_prev_20 = _f(rows[-21], "gex") if len(rows) >= 21 else None

    gex_data = {}
    if gex_latest is not None:
        # GEX is in billions. Positive = dealers long gamma (market stabilizing/pinning).
        # Negative = dealers short gamma (market volatile, moves amplified).
        if gex_latest > 0:
            gex_interp = "POSITIVE — dealers long gamma, expect dampened moves / pinning"
        elif gex_latest > -500_000_000:
            gex_interp = "SLIGHTLY NEGATIVE — mild volatility amplification"
        else:
            gex_interp = "DEEPLY NEGATIVE — dealers short gamma, expect amplified moves / whipsaws"

        # Normalize: squeezemetrics reports raw notional. Convert to billions for readability.
        gex_bn = gex_latest / 1_000_000_000 if abs(gex_latest) > 1000 else gex_latest
        gex_data = {
            "current": round(gex_bn, 3),
            "unit": "billions",
            "interpretation": gex_interp,
        }
        if gex_prev_5 is not None:
            gex_data["5d_ago"] = round((gex_prev_5 / 1_000_000_000 if abs(gex_prev_5) > 1000 else gex_prev_5), 3)
        if gex_prev_20 is not None:
            gex_data["20d_ago"] = round((gex_prev_20 / 1_000_000_000 if abs(gex_prev_20) > 1000 else gex_prev_20), 3)

    out = {
        "current": round(latest, 2),
        "date": date_str,
        "source": "squeezemetrics.com/monitor/static/DIX.csv"
                  + (" (cached last-good)" if used_cache else ""),
        "from_cache": used_cache,
        "interpretation": interpretation,
    }
    if gex_data:
        out["gex"] = gex_data
    if prev_5 is not None:
        out["5d_ago"] = round(prev_5, 2)
        out["5d_change_pct"] = round((latest - prev_5) / prev_5 * 100, 2)
    if prev_20 is not None:
        out["20d_ago"] = round(prev_20, 2)
        out["20d_change_pct"] = round((latest - prev_20) / prev_20 * 100, 2)
    return out


def fetch_sector_breadth() -> dict:
    """
    Calculate sector breadth: what % of S&P 500 sectors are above their 20-day MA.
    Uses sector ETFs as proxies.
    Primary: Yahoo Finance via unified market data. Fallback: yfinance direct.
    """
    sector_etfs = {
        "XLK": "Technology",
        "XLF": "Financials",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLI": "Industrials",
        "XLY": "Consumer Disc",
        "XLP": "Consumer Staples",
        "XLU": "Utilities",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLC": "Comm Services",
    }

    above_20ma = 0
    total = 0
    sector_detail = {}

    # Try unified market data first for all sector ETFs
    if MARKET_DATA_AVAILABLE:
        try:
            hist = mdata.fetch_historical_bars(list(sector_etfs.keys()), days=40)
            for etf, name in sector_etfs.items():
                etf_data = hist.get(etf, {})
                bars = etf_data.get("bars", [])
                if len(bars) < 20:
                    continue
                closes = [b["close"] for b in bars]
                current = closes[-1]
                ma_20 = sum(closes[-20:]) / 20
                is_above = current > ma_20
                if is_above:
                    above_20ma += 1
                total += 1
                sector_detail[name] = {
                    "etf": etf,
                    "price": round(current, 2),
                    "ma_20": round(ma_20, 2),
                    "above_20ma": is_above,
                    "source": etf_data.get("source", "market_data"),
                }
            if total > 0:
                breadth_pct = round(above_20ma / total * 100, 1)
                return {
                    "above_20ma_count": above_20ma,
                    "total_sectors": total,
                    "breadth_pct": breadth_pct,
                    "detail": sector_detail,
                }
        except Exception as e:
            print(f"[Pre-Flight] Market data sector breadth failed: {e} — falling back to yfinance")
            above_20ma = 0
            total = 0
            sector_detail = {}

    # Fallback: yfinance
    end = datetime.now()
    start = end - timedelta(days=40)

    for etf, name in sector_etfs.items():
        try:
            data = _yf_download_shim(etf, start=start, end=end, progress=False)
            if data.empty or len(data) < 20:
                continue

            closes = [float(c) for c in data["Close"].values.flatten()]
            current = closes[-1]
            ma_20 = sum(closes[-20:]) / 20

            is_above = current > ma_20
            if is_above:
                above_20ma += 1
            total += 1

            sector_detail[name] = {
                "etf": etf,
                "price": round(current, 2),
                "ma_20": round(ma_20, 2),
                "above_20ma": is_above,
            }
        except Exception:
            continue

    breadth_pct = round(above_20ma / total * 100, 1) if total > 0 else 0

    return {
        "above_20ma_count": above_20ma,
        "total_sectors": total,
        "breadth_pct": breadth_pct,
        "detail": sector_detail,
    }


# Theme-to-Finviz filter mapping for dynamic screening
_THEME_SECTOR_MAP = {
    "ai infrastructure": {"Sector": "Technology"},
    "ai": {"Sector": "Technology"},
    "technology": {"Sector": "Technology"},
    "semiconductors": {"Industry": "Semiconductors"},
    "software": {"Sector": "Technology"},
    "energy": {"Sector": "Energy"},
    "uranium": {"Industry": "Uranium"},
    "solar": {"Industry": "Solar"},
    "oil": {"Sector": "Energy"},
    "healthcare": {"Sector": "Healthcare"},
    "biotech": {"Industry": "Biotechnology"},
    "financials": {"Sector": "Financial"},
    "banks": {"Industry": "Banks - Diversified"},
    "industrials": {"Sector": "Industrials"},
    "defense": {"Industry": "Aerospace & Defense"},
    "aerospace": {"Industry": "Aerospace & Defense"},
    "gold": {"Industry": "Gold"},
    "silver": {"Industry": "Silver"},
    "mining": {"Industry": "Other Industrial Metals & Mining"},
    "copper": {"Industry": "Copper"},
    "real estate": {"Sector": "Real Estate"},
    "utilities": {"Sector": "Utilities"},
    "consumer": {"Sector": "Consumer Cyclical"},
    "retail": {"Industry": "Internet Retail"},
    "materials": {"Sector": "Basic Materials"},
}

# Fallback hardcoded list — used if Finviz screener fails
_FALLBACK_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "AVGO", "CRM",
    "ORCL", "ADBE", "NFLX", "INTC", "CSCO", "QCOM", "TXN", "MU", "AMAT", "LRCX",
    "JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW", "AXP", "V",
    "UNH", "JNJ", "PFE", "ABBV", "LLY", "MRK", "BMY", "AMGN", "GILD", "TMO",
    "XOM", "CVX", "COP", "SLB", "EOG",
    "CAT", "DE", "HON", "RTX", "LMT", "BA", "GE", "UNP",
    "HD", "LOW", "NKE", "SBUX", "MCD", "TGT", "COST",
    "SPY", "QQQ", "IWM", "XLF", "XLE", "XLK", "GLD", "TLT", "HYG",
]

MAX_SCREENER_TICKERS = 50


def _run_finviz_screen(theme_filters: Optional[Dict] = None) -> list:
    """
    Run a single Finviz screener query and return a list of dicts.
    Raises on any failure so the caller can fall back.
    """
    from finvizfinance.screener.overview import Overview

    filt = {
        # Finviz doesn't have an exact $500M threshold;
        # use >$300M and post-filter for >$500M
        "Market Cap.": "+Small (over $300mln)",
        "Price": "Over $5",
        "Average Volume": "Over 500K",
        "50-Day Simple Moving Average": "Price above SMA50",
        "200-Day Simple Moving Average": "Price above SMA200",
    }

    if theme_filters:
        filt.update(theme_filters)

    o = Overview()
    o.set_filter(filters_dict=filt)
    # Fetch up to 200 rows (sorted by volume desc), then trim to MAX
    df = o.screener_view(order="Volume", ascend=False, limit=500, verbose=0)

    if df is None or df.empty:
        return []

    # Post-filter: market cap > $500M (Finviz only lets us filter >$300M)
    df = df[df["Market Cap"] >= 500_000_000]

    results = []
    for _, row in df.iterrows():
        results.append({
            "ticker": row["Ticker"],
            "name": row["Company"],
            "sector": row["Sector"],
            "market_cap": int(row["Market Cap"]) if row["Market Cap"] else 0,
            "prior_close": round(float(row["Price"]), 2) if row["Price"] else 0.0,
            "source": "finviz_dynamic",
        })

    return results


def _fallback_screener_universe() -> list:
    """
    Fallback: use hardcoded ticker list + yfinance for basic data.
    Used when Finviz is unavailable (rate-limited, down, etc.).
    """
    import warnings
    warnings.warn(
        "[Pre-Flight] Finviz screener failed — falling back to hardcoded universe",
        RuntimeWarning,
        stacklevel=3,
    )
    print("[Pre-Flight] WARNING: Using hardcoded fallback universe")

    screener = []
    for ticker in _FALLBACK_UNIVERSE:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            mkt_cap = info.get("marketCap", 0)
            price = info.get("regularMarketPreviousClose") or info.get("previousClose", 0)

            if mkt_cap and mkt_cap >= SCREENER_MIN_MARKET_CAP and price and price >= SCREENER_MIN_PRICE:
                screener.append({
                    "ticker": ticker,
                    "name": info.get("shortName", ticker),
                    "sector": info.get("sector", "N/A"),
                    "market_cap": mkt_cap,
                    "prior_close": round(float(price), 2),
                    "source": "hardcoded_fallback",
                })
        except Exception:
            continue

    return screener[:MAX_SCREENER_TICKERS]


def _enrich_prior_close(tickers_data: list) -> list:
    """
    Enrich screener results with accurate prior_close from yfinance,
    since Finviz price data may be slightly delayed.
    """
    ticker_symbols = [t["ticker"] for t in tickers_data]
    end = datetime.now()
    start = end - timedelta(days=10)

    for entry in tickers_data:
        try:
            data = _yf_download_shim(entry["ticker"], start=start, end=end, progress=False)
            if not data.empty:
                entry["prior_close"] = round(float(data["Close"].iloc[-1].item()), 2)
        except Exception:
            pass  # Keep Finviz price as fallback

    return tickers_data


def generate_screener_universe(themes: Optional[List[str]] = None) -> list:
    """
    Generate SCREENER_UNIVERSE: up to 50 liquid tickers meeting:
    - Market cap > $500M
    - Price > $5
    - Average volume > 500K
    - Price above 50-day SMA (momentum filter)

    Uses Finviz dynamic screening via finvizfinance package.
    Accepts optional `themes` list to focus on specific sectors/industries.
    Falls back to hardcoded list if Finviz fails.
    """
    try:
        all_results = []
        seen_tickers = set()

        if themes:
            # Run separate screens per theme, then merge
            mapped_any = False
            for theme in themes:
                theme_key = theme.lower().strip()
                theme_filters = _THEME_SECTOR_MAP.get(theme_key)
                if theme_filters:
                    mapped_any = True
                    print(f"[Pre-Flight] Finviz screen: theme '{theme}' → {theme_filters}")
                    try:
                        results = _run_finviz_screen(theme_filters)
                        for r in results:
                            if r["ticker"] not in seen_tickers:
                                r["theme"] = theme
                                all_results.append(r)
                                seen_tickers.add(r["ticker"])
                    except Exception as e:
                        print(f"[Pre-Flight] Finviz theme '{theme}' screen failed: {e}")

            # If no themes mapped, or all theme screens failed, do broad scan
            if not mapped_any or not all_results:
                print("[Pre-Flight] No theme-specific results — running broad Finviz scan")
                results = _run_finviz_screen()
                for r in results:
                    if r["ticker"] not in seen_tickers:
                        all_results.append(r)
                        seen_tickers.add(r["ticker"])
        else:
            # No themes — broad scan
            print("[Pre-Flight] Running broad Finviz screener (no theme filter)")
            all_results = _run_finviz_screen()

        if not all_results:
            print("[Pre-Flight] Finviz returned 0 results — falling back")
            return _fallback_screener_universe()

        # Sort by volume proxy (market_cap as tiebreaker) and cap at MAX
        # Note: Finviz already sorted by volume desc, but after merging themes
        # we re-deduplicate; the order from the first theme takes precedence.
        all_results = all_results[:MAX_SCREENER_TICKERS]

        # Enrich with accurate prior_close (Schwab/Yahoo via unified market data)
        if MARKET_DATA_AVAILABLE:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with market data prior_close...")
            all_results = mdata.enrich_screener_universe(all_results)
        else:
            print(f"[Pre-Flight] Enriching {len(all_results)} tickers with yfinance prior_close...")
            all_results = _enrich_prior_close(all_results)

        print(f"[Pre-Flight] Screener universe: {len(all_results)} tickers from Finviz dynamic screen")
        return all_results

    except Exception as e:
        print(f"[Pre-Flight] Finviz screener failed: {e}")
        return _fallback_screener_universe()


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money Twitter/X mentions for given tickers.
    X research is MANDATORY — this must return real data.
    
    When called from the OCPlatform orchestrator, this uses x_search.
    When run standalone, it reads from a pre-existing file or raises an error.
    """
    from config import SMART_MONEY_ACCOUNTS

    mentions = {}
    # FIX (2026-07-06): single source of truth. SMART_MONEY_ACCOUNTS is empty in
    # config, and the old hardcoded fallback here was a THIRD divergent copy of the
    # curated list (still listing retail accounts purged per Jamie's May directive).
    # Fall back to x_fetch.CURATED_ACCOUNTS — the one list actually fetched.
    curated_handles = SMART_MONEY_ACCOUNTS
    if not curated_handles:
        try:
            from x_fetch import CURATED_ACCOUNTS as curated_handles
        except Exception:
            curated_handles = [
                "DeItaone", "Fxhedgers", "zaborsky", "GurufocusData", "PeterSchiff",
                "TruthGundlach", "elerianm", "SqueezeMetrics", "sentimentrader",
                "DarkPoolChart", "VolSignals", "boazweinstein", "RayDalio",
            ]

    # NOTE: The actual x_search calls happen in the orchestrator (orchestrator.py)
    # because x_search is an OCPlatform tool, not a Python library.
    # This function checks for the pre-fetched output file.
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            return json.load(f)

    raise RuntimeError(
        "Smart money X/Twitter data not found. The orchestrator must run x_search "
        "for each ticker against curated accounts and save to output/smart_money_mentions.json "
        "BEFORE Agent 3 can run. X research is MANDATORY."
    )


def format_macro_for_prompt(data: dict) -> str:
    """Format macro data into a clean text block for the LLM prompt."""
    lines = [
        f"MACRO DATA SNAPSHOT — {data.get('timestamp', 'unknown')}",
        f"Price Source: {data.get('price_source', 'unknown')}",
        "=" * 50,
    ]

    skip_keys = {"timestamp", "price_source"}

    for key, val in data.items():
        if key in skip_keys:
            continue
        if isinstance(val, dict) and "error" in val:
            lines.append(f"{key}: DATA UNAVAILABLE ({val['error']})")
        elif isinstance(val, dict) and "current" in val:
            change_str = ""
            if "5d_change_pct" in val:
                change_str = f" (5d: {val['5d_change_pct']:+.2f}%"
                if "20d_change_pct" in val:
                    change_str += f", 20d: {val['20d_change_pct']:+.2f}%"
                change_str += ")"
            lines.append(f"{key}: {val['current']}{change_str}")
        elif isinstance(val, dict) and "breadth_pct" in val:
            lines.append(
                f"{key}: {val['breadth_pct']}% of sectors above 20DMA "
                f"({val['above_20ma_count']}/{val['total_sectors']})"
            )
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {json.dumps(val)}" if not isinstance(val, str) else f"{key}: {val}")

    return "\n".join(lines)


def merge_assembly_screens(static_universe: list, assembly: dict) -> list:
    """
    Hybrid screener: merge Assembly's momentum/breakout screens into the static universe.
    Adds new tickers from Assembly that aren't already in the static list.
    Tags them with source='assembly_momentum' so Agent 2 knows they came from the live screen.
    """
    existing_tickers = set(t["ticker"] for t in static_universe)
    added = 0

    # Load Assembly screens if available
    screens_path = "output/assembly_screens.json"
    if os.path.exists(screens_path):
        try:
            with open(screens_path) as f:
                screens = json.load(f)
        except Exception:
            screens = {}
    else:
        screens = {}

    # Add overbought momentum names (these are running — potential trend plays)
    for entry in screens.get("overbought", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_overbought",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    # Add oversold names (these are beaten down — potential mean-reversion or value)
    for entry in screens.get("oversold", []):
        ticker = entry.get("ticker", "")
        if ticker and ticker not in existing_tickers:
            static_universe.append({
                "ticker": ticker,
                "name": entry.get("name", ""),
                "sector": entry.get("sector", ""),
                "market_cap": entry.get("mkt_cap", 0),
                "prior_close": entry.get("price", 0),
                "source": "assembly_momentum_oversold",
                "vs_50d": entry.get("vs_50d", ""),
            })
            existing_tickers.add(ticker)
            added += 1

    if added > 0:
        print(f"[Pre-Flight] Merged {added} new tickers from Assembly momentum screens (total: {len(static_universe)})")
    else:
        print("[Pre-Flight] No new Assembly tickers to merge (all already in universe)")

    return static_universe


def format_assembly_for_prompt(assembly: dict) -> str:
    """Format Assembly Private data for Agent 1's system prompt."""
    if not assembly:
        return "ASSEMBLY DATA: NOT AVAILABLE"

    lines = [
        f"ASSEMBLY SENTIMENT & MACRO — {assembly.get('timestamp', 'unknown')}",
        "Source: assemblyprivate.com (FMP data feed)",
        "=" * 50,
    ]

    # Sentiment
    sent = assembly.get("sentiment", {})
    if sent:
        lines.append(f"\nSENTIMENT COMPOSITE: {sent.get('composite_score', '?')} ({sent.get('composite_label', '?')})")
        lines.append(f"  Prev Close: {sent.get('prev_close', '?')} | 1W: {sent.get('one_week_ago', '?')} | 1M: {sent.get('one_month_ago', '?')} | 1Y: {sent.get('one_year_ago', '?')}")
        lines.append(f"  30D Avg: {sent.get('thirty_day_avg', '?')} | 52W High: {sent.get('fifty_two_week_high', '?')} | 52W Low: {sent.get('fifty_two_week_low', '?')}")

        comp = sent.get("components", {})
        if comp:
            lines.append("  Sub-Components:")
            for key, label in [
                ("market_volatility_vix", "Market Volatility (VIX)"),
                ("sp500_momentum_125d", "S&P 125d Momentum"),
                ("sp500_momentum", "S&P 500 Momentum"),
                ("stock_price_strength", "Stock Price Strength"),
                ("stock_price_breadth", "Stock Price Breadth"),
                ("put_call_options", "Put/Call Options"),
                ("junk_bond_demand", "Junk Bond Demand"),
                ("safe_haven_demand", "Safe Haven Demand"),
            ]:
                val = comp.get(key)
                if val is not None:
                    lines.append(f"    {label}: {val}")

    # Risk & Credit Gauges
    macro = assembly.get("macro", {})
    gauges = macro.get("risk_credit_gauges", [])
    if gauges:
        lines.append("\nRISK & CREDIT GAUGES (with 50d/200d trends):")
        for g in gauges:
            lines.append(f"  {g['ticker']} ({g['name']}): {g['price']} | Today: {g['today']} | vs50d: {g['vs_50d']} | vs200d: {g['vs_200d']} | 52wk: {g['range_52w']}")

    # Cross-asset rotation
    xasset = macro.get("cross_asset_rotation", [])
    if xasset:
        lines.append("\nCROSS-ASSET ROTATION:")
        for a in xasset:
            lines.append(f"  {a['ticker']} ({a['name']}): ${a['price']} | Today: {a['today']} | vs50d: {a['vs_50d']} | vs200d: {a['vs_200d']} | 52wk: {a['range_52w']}")

    # Sector rotation
    sectors = macro.get("sector_rotation", [])
    if sectors:
        lines.append("\nSECTOR ROTATION (RS vs SPY):")
        for s in sectors:
            lines.append(f"  {s['etf']} ({s['sector']}): Today: {s['today']} | vs50d: {s['vs_50d']} | vs200d: {s['vs_200d']} | RS: {s.get('rs_vs_spy', '?')}")

    # Yield curve
    yc = macro.get("yield_curve", {})
    if yc:
        curve = " | ".join(f"{t}: {v}" for t, v in yc.items())
        lines.append(f"\nYIELD CURVE: {curve}")
        if "2Y" in yc and "10Y" in yc:
            spread = round(yc["10Y"] - yc["2Y"], 2)
            lines.append(f"  2s10s Spread: {spread}")

    return "\n".join(lines)


def is_assembly_stale(assembly_path: str) -> bool:
    """Check if assembly data file is stale (older than ASSEMBLY_STALE_HOURS)."""
    if not os.path.exists(assembly_path):
        return True
    try:
        with open(assembly_path) as f:
            data = json.load(f)
        ts = data.get("timestamp", "")
        if not ts:
            return True
        # Parse ISO timestamp
        data_time = datetime.fromisoformat(ts.replace("Z", "+00:00").split("+")[0])
        age_hours = (datetime.now() - data_time).total_seconds() / 3600
        print(f"[Pre-Flight] Assembly data age: {age_hours:.1f}h (stale threshold: {ASSEMBLY_STALE_HOURS}h)")
        return age_hours > ASSEMBLY_STALE_HOURS
    except Exception as e:
        print(f"[Pre-Flight] Could not check assembly staleness: {e}")
        return True


def fetch_fresh_sentiment_fallback() -> dict:
    """
    Fetch fresh sentiment indicators from public APIs when Assembly data is stale.
    Uses CNN Fear & Greed API + yfinance for the same indicators Assembly provides.
    """
    import requests
    result = {"timestamp": datetime.now().isoformat(), "source": "public_market_data"}

    # 2. Sub-components from yfinance
    components = {}
    try:
        end = datetime.now()
        start = end - timedelta(days=5)

        # VIX for market volatility component
        vix = _yf_download_shim("^VIX", start=start, end=end, progress=False)
        if not vix.empty:
            vix_val = float(vix["Close"].iloc[-1].item())
            components["vix_value"] = round(vix_val, 2)
            if vix_val < 15: components["market_volatility_vix"] = 90
            elif vix_val < 20: components["market_volatility_vix"] = 65
            elif vix_val < 25: components["market_volatility_vix"] = 45
            elif vix_val < 35: components["market_volatility_vix"] = 25
            else: components["market_volatility_vix"] = 5

        # S&P 500 momentum (125-day)
        spy = _yf_download_shim("SPY", start=end - timedelta(days=180), end=end, progress=False)
        if not spy.empty and len(spy) > 125:
            current_spy = float(spy["Close"].iloc[-1].item())
            spy_125d = float(spy["Close"].iloc[-125].item())
            momentum_pct = (current_spy - spy_125d) / spy_125d * 100
            if momentum_pct > 10: components["sp500_momentum_125d"] = 90
            elif momentum_pct > 5: components["sp500_momentum_125d"] = 70
            elif momentum_pct > 0: components["sp500_momentum_125d"] = 50
            elif momentum_pct > -5: components["sp500_momentum_125d"] = 30
            else: components["sp500_momentum_125d"] = 10

        # Junk bond demand: HYG vs LQD spread
        hyg = _yf_download_shim("HYG", start=start, end=end, progress=False)
        lqd = _yf_download_shim("LQD", start=start, end=end, progress=False)
        if not hyg.empty and not lqd.empty:
            hyg_ret = float(hyg["Close"].pct_change().iloc[-1].item())
            lqd_ret = float(lqd["Close"].pct_change().iloc[-1].item())
            spread = (hyg_ret - lqd_ret) * 100
            if spread > 0.5: components["junk_bond_demand"] = 80
            elif spread > 0: components["junk_bond_demand"] = 60
            elif spread > -0.5: components["junk_bond_demand"] = 40
            else: components["junk_bond_demand"] = 20

        # Safe haven demand: TLT relative to SPY
        tlt = _yf_download_shim("TLT", start=start, end=end, progress=False)
        if not tlt.empty and not spy.empty:
            tlt_ret = float(tlt["Close"].pct_change().iloc[-1].item())
            spy_ret_1d = float(spy["Close"].pct_change().iloc[-1].item())
            haven_spread = (spy_ret_1d - tlt_ret) * 100
            if haven_spread > 1: components["safe_haven_demand"] = 80
            elif haven_spread > 0: components["safe_haven_demand"] = 60
            elif haven_spread > -1: components["safe_haven_demand"] = 40
            else: components["safe_haven_demand"] = 20

    except Exception as e:
        print(f"[Pre-Flight] Component fallback fetch error: {e}")

    # Compute synthetic composite from available components.
    # GUARD: require a minimum number of components so a single stale/empty
    # yfinance pull can't produce a confidently-wrong composite from 1 value.
    MIN_COMPONENTS = 3  # of the 4 score components (excl. vix_value)
    result["components"] = components
    if components:
        scores = [v for k, v in components.items() if k != "vix_value" and isinstance(v, (int, float))]
        if len(scores) >= MIN_COMPONENTS:
            composite = round(sum(scores) / len(scores))
            result["composite_score"] = composite
            result["component_count"] = len(scores)
            if composite >= 75: result["composite_label"] = "Extreme Greed"
            elif composite >= 55: result["composite_label"] = "Greed"
            elif composite >= 45: result["composite_label"] = "Neutral"
            elif composite >= 25: result["composite_label"] = "Fear"
            else: result["composite_label"] = "Extreme Fear"
            print(f"[Pre-Flight] Synthetic composite: {composite} ({result['composite_label']}) from {len(scores)} components")
        else:
            print(f"[Pre-Flight] \u26a0\ufe0f Only {len(scores)}/{MIN_COMPONENTS}+ sentiment components fetched — composite suppressed (insufficient data)")

    # --- Last-good cache + freshness fallback ---
    # If this fetch didn't produce a usable composite (yfinance stale/down),
    # fall back to the last-good cached sentiment rather than emitting a
    # partial/garbage result. Cache successful fetches for next time.
    SENT_CACHE = f"{OUTPUT_DIR}/sentiment_cache.json"
    if result.get("composite_score") is not None:
        try:
            with open(SENT_CACHE, "w") as cf:
                json.dump(result, cf, indent=2)
        except Exception:
            pass  # best-effort
    else:
        # Live fetch insufficient -> try cache
        if os.path.exists(SENT_CACHE):
            try:
                with open(SENT_CACHE) as cf:
                    cached = json.load(cf)
                if cached.get("composite_score") is not None:
                    cached_age = "unknown"
                    try:
                        ct = datetime.fromisoformat(cached.get("timestamp", "").split("+")[0])
                        cached_age = f"{(datetime.now() - ct).total_seconds()/3600:.1f}h"
                    except Exception:
                        pass
                    cached["source"] = "public_market_data (cached last-good)"
                    cached["from_cache"] = True
                    print(f"[Pre-Flight] \u26a0\ufe0f Live sentiment insufficient — using last-good cache (age {cached_age})")
                    return cached
            except Exception as e:
                print(f"[Pre-Flight] Sentiment cache read failed: {e}")

    return result


def run_preflight(themes: Optional[List[str]] = None) -> dict:
    """
    Run the full 7:55 AM pre-flight.
    Returns all data packaged for downstream agents.

    Args:
        themes: Optional list of theme strings from Agent 1's preferred_themes.
                Maps to Finviz sector/industry filters for focused screening.
                E.g. ["AI Infrastructure", "Energy", "Uranium"]
    """
    # ━━━ HOLIDAY GATE: Abort if market is closed (prevents holiday runs) ━━━
    from safeguards import assert_market_open
    assert_market_open()

    print("[Pre-Flight] Starting 7:55 AM data fetch...")
    print("[Pre-Flight] Using PRIOR CLOSE prices (not live/intraday)")
    if themes:
        print(f"[Pre-Flight] Theme filters: {themes}")

    # 1+2+6. Parallel fetch: macro, screener, fedwatch
    import concurrent.futures
    print("[Pre-Flight] Starting parallel data fetch (macro + screener + fedwatch)...")
    macro, screener, fedwatch_data = {}, [], {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_macro = executor.submit(fetch_macro_data)
        future_screener = executor.submit(generate_screener_universe, themes)
        future_fw = executor.submit(fw.fetch_fedwatch) if FEDWATCH_AVAILABLE else None

        macro = future_macro.result()
        screener = future_screener.result()

        if future_fw:
            try:
                fedwatch_data = future_fw.result()
                if "error" not in fedwatch_data:
                    fw.save_fedwatch(fedwatch_data)
                    summary = fedwatch_data.get("summary", {})
                    print(f"[Pre-Flight] FedWatch: next={summary.get('next_meeting', '?')} cuts={summary.get('total_cuts_priced_by_year_end', '?')}")
                else:
                    print(f"[Pre-Flight] FedWatch error: {fedwatch_data['error']}")
            except Exception as e:
                print(f"[Pre-Flight] FedWatch async failed: {e}")

    print(f"[Pre-Flight] Parallel fetch done: {len(macro)} macro keys, {len(screener)} screener tickers")

    # 3. Smart money X/Twitter mentions
    # NOTE: X search happens in the orchestrator via OCPlatform's x_search tool.
    # Pre-flight saves macro + screener. The orchestrator then:
    #   a) Runs Agent 1 + Agent 2 to get candidate tickers
    #   b) Runs x_search for those tickers against curated accounts
    #   c) Saves results to output/smart_money_mentions.json
    #   d) Then runs Agent 3 with that data
    # X research is MANDATORY — Agent 3 will not bypass.

    # 3. Market sentiment data (composite + sub-components)
    #    Sourced live from public market data (CNN Fear&Greed + yfinance proxies)
    #    every run. The legacy Assembly browser-scrape was retired — it required
    #    a manual login/snapshot that never ran in the automated pipeline, so it
    #    always went stale. The live public path is free, deterministic, and
    #    needs no browser. macro overlay is already covered by fetch_macro_data().
    assembly_path = f"{OUTPUT_DIR}/assembly_data.json"
    print("[Pre-Flight] Fetching live market sentiment from public market data...")
    fresh_sentiment = fetch_fresh_sentiment_fallback()
    fresh_sentiment["source"] = "public_market_data"
    assembly = {
        "timestamp": datetime.now().isoformat(),
        "source": "public_market_data",
        "sentiment": fresh_sentiment,
        "macro": {},  # macro already covered by fetch_macro_data() above
    }
    try:
        with open(assembly_path, "w") as f:
            json.dump(assembly, f, indent=2)
        print(f"[Pre-Flight] Market sentiment saved (composite: {fresh_sentiment.get('composite_score', '?')} / {fresh_sentiment.get('composite_label', '?')})")
    except Exception as e:
        print(f"[Pre-Flight] Could not save sentiment data: {e}")

    # 4a. Filter out tickers with recent stock splits
    from safeguards import filter_corporate_actions
    screener, splits_removed = filter_corporate_actions(screener)

    # 4b. Merge Assembly momentum screen into screener universe (hybrid approach)
    screener = merge_assembly_screens(screener, assembly)

    # 5. Technical indicators from Massive API (SMA, RSI, MACD)
    technicals = {}
    if MASSIVE_AVAILABLE:
        # Calculate technicals LOCALLY via Pandas (zero API calls)
        # Uses yfinance for historical data + pandas for RSI/MACD/SMA
        tech_tickers = ["SPY", "QQQ", "IWM"] + [t["ticker"] for t in screener[:10] if "ticker" in t]
        tech_tickers = list(dict.fromkeys(tech_tickers))  # Deduplicate preserving order

        print(f"[Pre-Flight] Calculating technicals locally for {len(tech_tickers)} tickers...")
        technicals = massive.calculate_technicals_batch(tech_tickers, period="6mo")
        for ticker, tech in technicals.items():
            if "error" not in tech:
                print(f"  {ticker}: RSI={tech.get('rsi_14', '?')} MACD_trend={tech.get('macd_trend', '?')}")
            else:
                print(f"  {ticker}: {tech['error']}")

        with open(f"{OUTPUT_DIR}/technicals.json", "w") as f:
            json.dump(technicals, f, indent=2)
        print(f"[Pre-Flight] Technicals saved for {len(technicals)} tickers (local calc, 0 API calls)")
    else:
        print("[Pre-Flight] Skipping Massive technicals (not available)")

    # 6. FedWatch — already fetched in parallel above
    if not fedwatch_data:
        print("[Pre-Flight] FedWatch: not available or failed during parallel fetch")

    # 7. ITC (Into The Cryptoverse) data — crypto risk, recession risk, dominance
    itc_data_loaded = {}
    if ITC_AVAILABLE:
        itc_path = f"{OUTPUT_DIR}/itc_data.json"
        if not itc.is_itc_stale(itc_path, ITC_STALE_HOURS):
            itc_data_loaded = itc.load_itc_data(itc_path) or {}
            if itc_data_loaded:
                print(f"[Pre-Flight] ITC data FRESH — loaded (crypto risk: {itc_data_loaded.get('crypto_risk', {}).get('summary', '?')})")
        else:
            print("[Pre-Flight] ITC data STALE or missing — will need browser scrape from Zuck")
            print("[Pre-Flight] ITC data must be fetched via browser (no public API). Skipping for now.")
    else:
        print("[Pre-Flight] ITC module not available — skipping")

    preflight_data = {
        "timestamp": datetime.now().isoformat(),
        "macro": macro,
        "screener_universe": screener,
        "assembly": assembly,
        "technicals": technicals,
        "fedwatch": fedwatch_data,
        "itc": itc_data_loaded,
    }

    # Save all outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(f"{OUTPUT_DIR}/preflight_macro.json", "w") as f:
        json.dump(macro, f, indent=2)

    with open(f"{OUTPUT_DIR}/screener_universe.json", "w") as f:
        json.dump(screener, f, indent=2)

    print(f"[Pre-Flight] Complete. Macro data + {len(screener)} screener tickers saved.")
    print(f"[Pre-Flight] NOTE: X/Twitter smart money fetch runs in orchestrator after Agent 2 picks tickers.")
    if itc_data_loaded:
        print(f"[Pre-Flight] ITC data included (crypto summary risk: {itc_data_loaded.get('crypto_risk', {}).get('summary', '?')}, recession: {itc_data_loaded.get('macro_risk', {}).get('recession_composite', '?')})")
    return preflight_data


if __name__ == "__main__":
    data = run_preflight()
    print("\n" + format_macro_for_prompt(data["macro"]))
    print(f"\nScreener: {len(data['screener_universe'])} tickers")
    print(f"Smart Money: {data['smart_money']['status']}")
```

================================================================================
FILE: preflight_proxy_guard.py
================================================================================
```python
#!/usr/bin/env python3
"""
Preflight Proxy Guard — Open Claw morning pipeline hardening.

WHY THIS EXISTS
---------------
On 2026-06-23 the 8 AM `open-claw-morning` cron failed all 3 model attempts
(opus-4-8 / 4-7 / 4-6) with `fetch failed (timeout)`. Root cause was NOT the
pipeline — it was the gateway->local-proxy path being unhealthy: the Claude
OAuth token-refresh loop had been logging `exit=1` failures overnight, so the
proxy couldn't complete upstream calls when the cron fired. It self-healed
later, but by then the 8 AM window was gone (no trades placed).

This guard runs as STEP 0 of the morning cron. It:
  1. Verifies the Claude OAuth credential is valid and not expiring soon.
     If it's stale/expiring, it force-triggers a refresh (claude ping) and
     re-checks.
  2. Health-checks the local model proxy (default 127.0.0.1:18801) with a real
     round-trip, retrying with exponential backoff.
  3. Exits 0 if the model path is healthy (cron proceeds), or exits non-zero
     after exhausting retries (cron should abort cleanly + alert).

Usage:
    python3 preflight_proxy_guard.py            # run the guard
    python3 preflight_proxy_guard.py --json     # machine-readable result

Exit codes:
    0  healthy — proceed with pipeline
    2  proxy unhealthy after retries
    3  credential could not be refreshed / still invalid
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
CREDS_FILE = Path.home() / ".claude" / ".credentials.json"
CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"
PROXY_URL = "http://127.0.0.1:18801/v1/messages"
# Token must have at least this long left, otherwise force a refresh first.
TOKEN_MIN_REMAINING_S = 600  # 10 minutes
# Proxy health-check retry schedule (seconds to wait BEFORE each attempt).
PROXY_BACKOFF = [0, 5, 15, 30, 60]
PROXY_TIMEOUT_S = 30
HEALTH_MODELS = ["claude-opus-4-8", "claude-opus-4-6"]  # primary + a fallback


def _log(msg: str):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} [proxy-guard] {msg}", flush=True)


# ── 1. Credential check + force refresh ─────────────────────────────────────
def _read_expiry_ms() -> int:
    try:
        d = json.loads(CREDS_FILE.read_text())
        return int(d.get("claudeAiOauth", {}).get("expiresAt", 0))
    except Exception:
        return 0


def _token_remaining_s() -> int:
    exp = _read_expiry_ms()
    if not exp:
        return -1
    return int((exp - time.time() * 1000) / 1000)


def _force_refresh() -> bool:
    """Trigger a token refresh via a tiny claude CLI ping. Returns True if the
    expiry advanced (refresh succeeded)."""
    before = _read_expiry_ms()
    if not CLAUDE_BIN.exists():
        _log(f"claude CLI not at {CLAUDE_BIN} — cannot force refresh")
        return False
    try:
        subprocess.run(
            [str(CLAUDE_BIN), "-p", "ping", "--max-turns", "1",
             "--no-session-persistence"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=90,
        )
    except Exception as e:
        _log(f"refresh ping errored: {e}")
    after = _read_expiry_ms()
    return after > before


def ensure_token_healthy() -> dict:
    remaining = _token_remaining_s()
    if remaining >= TOKEN_MIN_REMAINING_S:
        _log(f"token OK — {remaining}s remaining")
        return {"ok": True, "remaining_s": remaining, "refreshed": False}

    _log(f"token low/expired ({remaining}s) — forcing refresh...")
    for attempt in range(1, 4):
        if _force_refresh():
            remaining = _token_remaining_s()
            _log(f"refresh succeeded — {remaining}s remaining")
            return {"ok": True, "remaining_s": remaining, "refreshed": True}
        _log(f"refresh attempt {attempt}/3 did not advance expiry; retrying in 10s")
        time.sleep(10)

    remaining = _token_remaining_s()
    ok = remaining >= 60  # accept if it at least has a usable minute
    _log(f"refresh exhausted — {remaining}s remaining (ok={ok})")
    return {"ok": ok, "remaining_s": remaining, "refreshed": False}


# ── 2. Proxy health check w/ backoff ────────────────────────────────────────
def _ping_proxy(model: str) -> tuple:
    """Returns (ok, status_or_err, elapsed_s)."""
    body = json.dumps({
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "reply OK"}],
    }).encode()
    req = urllib.request.Request(
        PROXY_URL, data=body,
        headers={"content-type": "application/json"}, method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_S) as r:
            r.read()
            return (r.status == 200, r.status, time.time() - t0)
    except urllib.error.HTTPError as e:
        return (False, f"HTTP {e.code}", time.time() - t0)
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}", time.time() - t0)


def ensure_proxy_healthy() -> dict:
    last = None
    for i, wait in enumerate(PROXY_BACKOFF, 1):
        if wait:
            _log(f"backing off {wait}s before proxy attempt {i}/{len(PROXY_BACKOFF)}")
            time.sleep(wait)
        model = HEALTH_MODELS[(i - 1) % len(HEALTH_MODELS)]
        ok, info, elapsed = _ping_proxy(model)
        last = {"model": model, "info": info, "elapsed_s": round(elapsed, 2)}
        if ok:
            _log(f"proxy healthy via {model} — {info} in {elapsed:.2f}s")
            return {"ok": True, **last}
        _log(f"proxy attempt {i} failed ({model}): {info} after {elapsed:.2f}s")
    _log("proxy unhealthy after all retries")
    return {"ok": False, **(last or {})}


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON result")
    args = ap.parse_args()

    tok = ensure_token_healthy()
    if not tok["ok"]:
        result = {"healthy": False, "stage": "token", "token": tok}
        if args.json:
            print(json.dumps(result))
        _log("ABORT: token unhealthy")
        sys.exit(3)

    proxy = ensure_proxy_healthy()
    healthy = proxy["ok"]
    result = {"healthy": healthy, "stage": "proxy", "token": tok, "proxy": proxy}
    if args.json:
        print(json.dumps(result))

    if healthy:
        _log("PREFLIGHT PASS — model path healthy, pipeline may proceed")
        sys.exit(0)
    else:
        _log("ABORT: proxy unhealthy after retries")
        sys.exit(2)


if __name__ == "__main__":
    main()
```

================================================================================
FILE: reconcile_positions.py
================================================================================
```python
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
```

================================================================================
FILE: robinhood_broker.py
================================================================================
```python
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
                    live_shares = math.floor(risk_budget / live_risk_per_share)
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
```

================================================================================
FILE: run_archiver.py
================================================================================
```python
#!/usr/bin/env python3
"""
Run Archiver — Preserves each pipeline run's output files for historical analysis.

Problem: The pipeline overwrites output/*.json on every run. Without archiving,
the review system has no historical data to analyze.

Solution: After each pipeline run, archive all output files into a timestamped
directory under output/archive/YYYY-MM-DD_HHMM/.

Usage:
  python3 run_archiver.py                # Archive current output files
  python3 run_archiver.py --list         # List all archived runs
  python3 run_archiver.py --load 2026-05-22_0808  # Load a specific run's data
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
ARCHIVE_DIR = OUTPUT_DIR / "archive"

# Files to archive per run
ARCHIVE_FILES = [
    "agent1_directive.json",
    "agent2_candidates.json",
    "agent2_fundamentals.json",
    "agent3_verified.json",
    "agent4_orders.json",
    "agent4a_stops.json",
    "agent5_decisions.json",
    "agent5_snapshot.json",
    "broker_fills.json",
    "preflight_macro.json",
    "screener_universe.json",
    "smart_money_mentions.json",
    "x_mentions.json",
    "tear_sheet.txt",
    "assembly_data.json",
]


def archive_run(label: str = None) -> str:
    """
    Copy current output files into a timestamped archive folder.
    Returns the archive directory path.
    """
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    if label:
        run_dir = ARCHIVE_DIR / label
    else:
        run_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d_%H%M")

    if run_dir.exists():
        # Append seconds to avoid collision
        run_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")

    run_dir.mkdir(parents=True, exist_ok=True)

    archived = []
    for fname in ARCHIVE_FILES:
        src = OUTPUT_DIR / fname
        if src.exists():
            shutil.copy2(src, run_dir / fname)
            archived.append(fname)

    # Write manifest
    manifest = {
        "archived_at": datetime.now().isoformat(),
        "files": archived,
        "run_label": run_dir.name,
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[Archiver] Archived {len(archived)} files to {run_dir}")
    return str(run_dir)


def list_runs() -> list:
    """List all archived runs, sorted by date."""
    if not ARCHIVE_DIR.exists():
        return []

    runs = []
    for d in sorted(ARCHIVE_DIR.iterdir()):
        if d.is_dir():
            manifest_path = d / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                runs.append({
                    "label": d.name,
                    "path": str(d),
                    "archived_at": manifest.get("archived_at"),
                    "file_count": len(manifest.get("files", [])),
                })
            else:
                runs.append({
                    "label": d.name,
                    "path": str(d),
                    "archived_at": None,
                    "file_count": len(list(d.glob("*.json"))),
                })
    return runs


def load_run(label: str) -> dict:
    """Load all JSON files from an archived run."""
    run_dir = ARCHIVE_DIR / label
    if not run_dir.exists():
        raise FileNotFoundError(f"No archived run found: {label}")

    data = {}
    for f in run_dir.glob("*.json"):
        if f.name == "manifest.json":
            continue
        with open(f) as fh:
            try:
                data[f.stem] = json.load(fh)
            except json.JSONDecodeError:
                data[f.stem] = {"error": "invalid JSON"}

    # Load tear sheet text if present
    tear_sheet = run_dir / "tear_sheet.txt"
    if tear_sheet.exists():
        data["tear_sheet"] = tear_sheet.read_text()

    return data


def load_all_runs() -> list:
    """Load all archived runs with their data. Returns list of (label, data) tuples."""
    runs = list_runs()
    result = []
    for run in runs:
        try:
            data = load_run(run["label"])
            data["_label"] = run["label"]
            data["_archived_at"] = run.get("archived_at")
            result.append(data)
        except Exception as e:
            print(f"[Archiver] Warning: Could not load {run['label']}: {e}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Archive pipeline output files")
    parser.add_argument("--list", action="store_true", help="List all archived runs")
    parser.add_argument("--load", type=str, help="Load a specific archived run")
    parser.add_argument("--label", type=str, help="Custom label for this archive")
    args = parser.parse_args()

    if args.list:
        runs = list_runs()
        if not runs:
            print("No archived runs found.")
        else:
            print(f"\n{'Label':<25} {'Files':<8} {'Archived At'}")
            print("-" * 60)
            for r in runs:
                print(f"{r['label']:<25} {r['file_count']:<8} {r.get('archived_at', 'unknown')}")
    elif args.load:
        data = load_run(args.load)
        print(f"Loaded {len(data)} files from {args.load}")
        for k in sorted(data.keys()):
            print(f"  - {k}")
    else:
        archive_run(label=args.label)
```

================================================================================
FILE: run_execution_daemon.py
================================================================================
```python
#!/usr/bin/env python3
"""
run_execution_daemon.py — Background Execution Engine Daemon

Run this alongside the orchestrator during market hours.
It polls order status every ~15 seconds and:
- Places stop-loss orders immediately after entry fills
- Panic-liquidates positions if price crashes through stop during partial fills
- Handles order cancellation / expiry cleanup

Usage:
    python3 run_execution_daemon.py

Kill with Ctrl+C or SIGTERM.
"""
from execution_engine import ExecutionEngine

if __name__ == "__main__":
    print("=" * 60)
    print("  EXECUTION ENGINE DAEMON")
    print("  Reconciles orders every 15 seconds")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    engine = ExecutionEngine()
    engine.run_reconciliation_loop()
```

================================================================================
FILE: safeguards.py
================================================================================
```python
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
                if hasattr(earnings_date, "date"):
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
```

================================================================================
FILE: schwab_reauth.py
================================================================================
```python
#!/usr/bin/env python3
"""
RETIRED 2026-06-24 — Schwab was removed from the trading pipeline.
Tiingo is now the sole live market-data source (see market_data.py).

This file is a no-op stub kept ONLY so the lingering system crontab entry
    0 3 */2 * * cd .../trading-pipeline && python3 schwab_reauth.py >> logs/schwab_reauth.log 2>&1
exits cleanly (0) instead of erroring with "file not found".

TO FULLY REMOVE: delete the cron line from a real Terminal with:
    crontab -l | grep -v schwab_reauth | crontab -
(headless agent shells can't write crontab — macOS TCC gate blocks the
setuid `crontab` write and it hangs.)
"""
import sys
from datetime import datetime

print(f"[{datetime.now().isoformat(timespec='seconds')}] schwab_reauth.py is RETIRED "
      f"(Schwab removed; Tiingo is the data source). No-op exit.")
sys.exit(0)
```

================================================================================
FILE: trade_journal.py
================================================================================
```python
"""
Trade Journal — Feedback CSV for the Open Claw pipeline.
One row per closed trade. Appended on every Agent 5 close and manual exit.
All inputs to the sizer, all decision flags, and outcome stats.

The R-multiple is the key field: pnl_dollars / risk_budgeted.
Normalizes across position sizes — comparing EXCEPTIONAL to PASS by dollar
P&L is misleading because EXCEPTIONALs are sized bigger by design.
Comparing by R tells you whether the conviction signal actually predicts outcome.
"""
import csv
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")

FIELDS = [
    # Identity
    "trade_id", "ticker", "theme",
    "entry_dt", "exit_dt", "holding_days",

    # Decision flags (at entry)
    "regime", "vol_regime", "posture",
    "tier", "agent3_verdict", "confirm_enhanced",
    "x_bullish_count", "x_bearish_count", "hf_principal_signal",

    # Sizing
    "entry_price", "stop_price", "stop_distance_pct",
    "shares", "position_value",
    "risk_budgeted", "risk_actual",
    "risk_multiplier", "binding_constraint",

    # Outcome
    "exit_price", "exit_reason",
    "pnl_dollars", "pnl_pct", "r_multiple",

    # Path stats (the underrated fields)
    "max_adverse_excursion_pct",    # worst drawdown before exit
    "max_favorable_excursion_pct",  # best unrealized gain before exit
    "spx_change_over_hold_pct",     # beta context

    # Process notes
    "agent2_thesis_short",  # 1-line, for human review
    "notes",
]


def log_close(trade_record: dict):
    """Append a closed trade to the journal CSV."""
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    new_file = not JOURNAL_PATH.exists()
    with JOURNAL_PATH.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({k: trade_record.get(k, "") for k in FIELDS})


def build_trade_record(
    trade_order: dict,
    directive: dict,
    agent3_verification: dict,
    exit_price: float,
    exit_reason: str,
    exit_dt: datetime = None,
    mae_pct: float = None,
    mfe_pct: float = None,
    spx_change_pct: float = None,
    notes: str = "",
) -> dict:
    """
    Build a complete trade record from pipeline outputs.
    Call this when Agent 5 closes a position or on manual exit.
    """
    entry_price = trade_order.get("entry_price", 0)
    shares = trade_order.get("shares", 0)
    risk_budgeted = trade_order.get("risk_budgeted", 0)
    entry_dt_str = trade_order.get("entry_dt", directive.get("timestamp", ""))

    pnl_dollars = round((exit_price - entry_price) * shares, 2)
    pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price else 0
    r_multiple = round(pnl_dollars / risk_budgeted, 2) if risk_budgeted else 0

    # Parse dates for holding days
    exit_dt = exit_dt or datetime.now()
    holding_days = 0
    try:
        if isinstance(entry_dt_str, str) and entry_dt_str:
            entry_parsed = datetime.fromisoformat(entry_dt_str.replace("Z", "+00:00"))
            holding_days = (exit_dt - entry_parsed).days
    except Exception:
        pass

    # Calculate SPX beta context (Did we beat the market?)
    if spx_change_pct is None:
        try:
            import yfinance as yf
            from datetime import timedelta
            if isinstance(entry_dt_str, str) and entry_dt_str:
                entry_parsed_spx = datetime.fromisoformat(entry_dt_str.replace("Z", "+00:00"))
                spy = yf.download(
                    "SPY",
                    start=entry_parsed_spx.strftime("%Y-%m-%d"),
                    end=(exit_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                    progress=False,
                )
                if not spy.empty and len(spy) >= 1:
                    if hasattr(spy.columns, 'levels') and len(spy.columns.levels) > 1:
                        spy_entry = float(spy["Close"]["SPY"].iloc[0])
                        spy_exit = float(spy["Close"]["SPY"].iloc[-1])
                    else:
                        spy_entry = float(spy["Close"].iloc[0])
                        spy_exit = float(spy["Close"].iloc[-1])
                    spx_change_pct = round((spy_exit - spy_entry) / spy_entry * 100, 2)
        except Exception:
            spx_change_pct = None

    # Generate trade ID
    trade_id = f"{trade_order.get('ticker', 'UNK')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return {
        "trade_id": trade_id,
        "ticker": trade_order.get("ticker", ""),
        "theme": trade_order.get("theme", ""),
        "entry_dt": entry_dt_str,
        "exit_dt": exit_dt.isoformat(),
        "holding_days": holding_days,

        "regime": directive.get("regime", ""),
        "vol_regime": directive.get("vol_regime", ""),
        "posture": directive.get("posture", ""),
        "tier": trade_order.get("conviction_tier", ""),
        "agent3_verdict": agent3_verification.get("verdict", ""),
        "confirm_enhanced": trade_order.get("confirm_enhanced", False),
        "x_bullish_count": agent3_verification.get("x_bullish_count", ""),
        "x_bearish_count": agent3_verification.get("x_bearish_count", ""),
        "hf_principal_signal": agent3_verification.get("hf_principal_signal", ""),

        "entry_price": entry_price,
        "stop_price": trade_order.get("stop_loss", ""),
        "stop_distance_pct": trade_order.get("stop_distance_pct", ""),
        "shares": shares,
        "position_value": trade_order.get("position_value", ""),
        "risk_budgeted": risk_budgeted,
        "risk_actual": trade_order.get("risk_actual", ""),
        "risk_multiplier": trade_order.get("risk_multiplier", ""),
        "binding_constraint": trade_order.get("binding_constraint", ""),

        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "r_multiple": r_multiple,

        "max_adverse_excursion_pct": mae_pct or "",
        "max_favorable_excursion_pct": mfe_pct or "",
        "spx_change_over_hold_pct": spx_change_pct or "",

        "agent2_thesis_short": trade_order.get("thesis", "")[:100],
        "notes": notes,
    }
```

================================================================================
FILE: vwap_gate.py
================================================================================
```python
"""
Open Claw — VWAP Execution Gate
Filters BUY orders at 10:15 AM by checking if price is above the session VWAP.
Orders below VWAP are rejected — sellers are in control.
"""
import yfinance as yf
import numpy as np
from datetime import datetime
from typing import Optional


def check_vwap(ticker: str) -> Optional[dict]:
    """
    Download today's intraday 1-minute data and compute VWAP.

    VWAP = Σ(typical_price × volume) / Σ(volume)
    where typical_price = (high + low + close) / 3

    Returns dict with ticker, current_price, vwap, above_vwap, pct_vs_vwap
    or None if data is unavailable (e.g., pre-market, weekend).
    """
    try:
        tk = yf.Ticker(ticker)
        # "1d" period with "1m" interval gives today's intraday bars
        hist = tk.history(period="1d", interval="1m")

        if hist.empty:
            return None

        high = hist["High"].values
        low = hist["Low"].values
        close = hist["Close"].values
        volume = hist["Volume"].values

        # Typical price
        typical = (high + low + close) / 3.0

        cum_tp_vol = np.cumsum(typical * volume)
        cum_vol = np.cumsum(volume)

        # Avoid division by zero
        if cum_vol[-1] == 0:
            return None

        vwap = float(cum_tp_vol[-1] / cum_vol[-1])
        current_price = float(close[-1])
        pct_vs_vwap = ((current_price - vwap) / vwap) * 100.0

        return {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 4),
            "vwap": round(vwap, 4),
            "above_vwap": current_price >= vwap,
            "pct_vs_vwap": round(pct_vs_vwap, 2),
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


def vwap_gate(trade_orders: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter BUY orders through the VWAP gate.

    - BUY orders above VWAP → approved (pass through)
    - BUY orders below VWAP → rejected with reason
    - Non-BUY orders (SELL, HOLD, etc.) → always pass through

    Returns (approved_orders, rejected_orders).
    """
    approved = []
    rejected = []

    for order in trade_orders:
        action = order.get("action", "").upper()

        # Only gate BUY orders
        if action != "BUY":
            approved.append(order)
            continue

        ticker = order.get("ticker", "")
        vwap_data = check_vwap(ticker)

        if vwap_data is None:
            # No intraday data — can't check VWAP (pre-market, weekend, etc.)
            # FAIL-CLOSED: reject if we can't verify VWAP
            order["vwap_note"] = "No intraday data — VWAP check FAILED (fail-closed)"
            order["reject_reason"] = "VWAP unavailable — fail-closed"
            rejected.append(order)
            continue

        if vwap_data.get("error"):
            order["vwap_note"] = f"VWAP error: {vwap_data['error']} (fail-closed)"
            order["reject_reason"] = f"VWAP error: {vwap_data['error']}"
            rejected.append(order)
            continue

        if vwap_data["above_vwap"]:
            order["vwap"] = vwap_data["vwap"]
            order["vwap_pct"] = vwap_data["pct_vs_vwap"]
            approved.append(order)
        else:
            order["vwap"] = vwap_data["vwap"]
            order["vwap_pct"] = vwap_data["pct_vs_vwap"]
            order["reject_reason"] = "Below VWAP — sellers in control"
            rejected.append(order)

    return approved, rejected
```

================================================================================
FILE: watchlist.py
================================================================================
```python
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
```

================================================================================
FILE: weekly_review.py
================================================================================
```python
#!/usr/bin/env python3
"""
Weekly Review — Trade Journal Analysis
Run weekly after ~20+ trades to validate the conviction system.

Usage:
  python3 weekly_review.py
  python3 weekly_review.py --since 2026-05-01
"""
import sys
from pathlib import Path

import pandas as pd

JOURNAL_PATH = Path("journal/trades.csv")


def load_journal(since: str = None) -> pd.DataFrame:
    if not JOURNAL_PATH.exists():
        print("No journal found. Run some trades first.")
        sys.exit(0)

    df = pd.read_csv(JOURNAL_PATH, parse_dates=["entry_dt", "exit_dt"])
    if since:
        df = df[df["entry_dt"] >= since]
    print(f"Loaded {len(df)} trades")
    return df


def run_review(since: str = None):
    df = load_journal(since)

    if len(df) == 0:
        print("No trades in journal.")
        return

    print("\n" + "=" * 60)
    print("OPEN CLAW — WEEKLY REVIEW")
    print("=" * 60)

    # 1. Is EXCEPTIONAL actually outperforming STRONG?
    print("\n--- R-MULTIPLE BY TIER ---")
    tier_stats = df.groupby("tier")["r_multiple"].agg(["count", "mean", "std"])
    print(tier_stats.to_string())

    # 2. Does CONFIRM_ENHANCED add alpha?
    print("\n--- R-MULTIPLE BY CONFIRM_ENHANCED ---")
    confirm_stats = df.groupby("confirm_enhanced")["r_multiple"].agg(["count", "mean", "std"])
    print(confirm_stats.to_string())

    # 3. Which Agent 3 verdicts correlate with R?
    print("\n--- R-MULTIPLE BY AGENT 3 VERDICT ---")
    verdict_stats = df.groupby("agent3_verdict")["r_multiple"].agg(["count", "mean"])
    print(verdict_stats.to_string())

    # 4. Sharpe-equivalent by tier (mean R / stdev R)
    print("\n--- SHARPE-EQUIVALENT BY TIER ---")
    sharpe = df.groupby("tier")["r_multiple"].apply(
        lambda x: round(x.mean() / x.std(), 2) if x.std() > 0 else 0
    )
    print(sharpe.to_string())

    # 5. MAE/MFE analysis — are stops too tight?
    print("\n--- MAE/MFE ANALYSIS ---")
    if "max_adverse_excursion_pct" in df.columns:
        winners = df[df["r_multiple"] > 0]
        losers = df[df["r_multiple"] <= 0]

        if len(winners) > 0:
            print(f"\nWinners ({len(winners)}) — Max Adverse Excursion:")
            mae = pd.to_numeric(winners["max_adverse_excursion_pct"], errors="coerce")
            print(f"  Mean: {mae.mean():.2f}%  Median: {mae.median():.2f}%  Max: {mae.max():.2f}%")

        if len(losers) > 0:
            print(f"\nLosers ({len(losers)}) — Max Favorable Excursion:")
            mfe = pd.to_numeric(losers["max_favorable_excursion_pct"], errors="coerce")
            print(f"  Mean: {mfe.mean():.2f}%  Median: {mfe.median():.2f}%  Max: {mfe.max():.2f}%")
    else:
        print("  (No MAE/MFE data yet)")

    # 6. Beta check — are we just long SPX?
    print("\n--- BETA CHECK ---")
    spx_col = pd.to_numeric(df.get("spx_change_over_hold_pct", pd.Series()), errors="coerce")
    r_col = pd.to_numeric(df["r_multiple"], errors="coerce")
    if spx_col.notna().sum() >= 5:
        corr = r_col.corr(spx_col)
        print(f"  R-multiple vs SPX correlation: {corr:.3f}")
        if abs(corr) > 0.7:
            print("  WARNING: High correlation with SPX — may just be beta")
    else:
        print("  (Not enough SPX data yet)")

    # 7. Binding constraint distribution
    print("\n--- BINDING CONSTRAINT DISTRIBUTION ---")
    if "binding_constraint" in df.columns:
        bc = df["binding_constraint"].value_counts()
        print(bc.to_string())
        risk_pct = bc.get("risk", 0) / len(df) * 100
        alloc_pct = bc.get("allocation", 0) / len(df) * 100
        print(f"\n  Risk-bound: {risk_pct:.0f}%  Allocation-bound: {alloc_pct:.0f}%")
        if alloc_pct > 80:
            print("  NOTE: Allocation cap may be too tight — consider raising MAX_ALLOCATION_PCT")

    # 8. Summary stats
    print("\n--- OVERALL ---")
    total = len(df)
    winners_n = len(df[df["r_multiple"] > 0])
    print(f"  Trades: {total}")
    print(f"  Win rate: {winners_n/total*100:.0f}%")
    print(f"  Avg R: {df['r_multiple'].mean():.2f}")
    print(f"  Total P&L: ${df['pnl_dollars'].sum():.2f}")
    print(f"  Avg holding days: {df['holding_days'].mean():.1f}")

    # Calibration warning
    if total < 20:
        print(f"\n  ⚠️ Only {total} trades — too few for statistically valid conclusions.")
        print("  Need ~20+ per cohort before retuning multipliers.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", help="Only include trades after this date (YYYY-MM-DD)")
    args = parser.parse_args()
    run_review(args.since)
```

================================================================================
FILE: x_fetch.py
================================================================================
```python
"""
X/Twitter Smart Money Fetch — Official X Developer API
Uses the search/recent endpoint with X_BEARER_TOKEN (pay-per-use tier).

Queries surviving tickers against CURATED_ACCOUNTS list over a 7-day window.
Saves clean JSON to output/smart_money_mentions.json for Agent 3.

Usage:
  python3 x_fetch.py MSFT JPM           # Fetch mentions for specific tickers
  python3 x_fetch.py --from-agent2      # Read tickers from Agent 2 output
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# X API v2 search/recent endpoint
X_API_URL = "https://api.twitter.com/2/tweets/search/recent"

# Curated smart money accounts — INSTITUTIONAL MACRO/QUANT/FUNDAMENTAL ONLY
# Retail, options flow, and finfluencer handles PURGED per Jamie's directive (May 19)
# REMOVED: unusual_whales, WallStJesus, OptionsHawk, jimcramer, DumbMoneyTV
CURATED_ACCOUNTS = [
    # --- MACRO FLOW/SENTIMENT (institutional grade) ---
    "DeItaone",            # Institutional news wire
    "Fxhedgers",           # Macro/FX institutional feed
    "zaborsky",            # Macro strategist
    "GurufocusData",       # Fundamental data aggregator
    "PeterSchiff",         # Macro economist, hard assets
    "TruthGundlach",       # Jeffrey Gundlach, DoubleLine Capital
    "elerianm",            # Mohamed El-Erian, Allianz/PIMCO
    "SqueezeMetrics",      # DIX/GEX quant model
    "sentimentrader",      # Institutional sentiment data
    "DarkPoolChart",       # Dark pool flow analytics
    "VolSignals",          # Volatility structure analysis
    # --- MACRO_ANALYSTS (central bank, liquidity, regime) ---
    "MacroAlf",            # Alfonso Peccatiello, ex-ING $20B portfolio
    "FedGuy12",            # Joseph Wang, ex-NY Fed open market desk
    "biancoresearch",      # Jim Bianco, Bianco Research
    "TheMichaelEvery",     # Michael Every, Rabobank Global Strategist
    # --- SECTOR_SPECIALISTS ---
    "Josh_Young_1",        # Energy/oil specialist
    "brandon_munro",       # Uranium/nuclear sector
    "UraniumInsider",      # Uranium sector intelligence
    "PeterKolchinsky",     # Biotech/healthcare specialist
    "dylanpatel",          # Semiconductor/AI sector (SemiAnalysis)
    # --- QUANT_SYSTEMATIC (gamma, vol structure, quant models) ---
    "spotgamma",           # Options gamma exposure modeling
    "choffstein",          # Corey Hoffstein, Newfound Research
    "nope_its_lily",       # Lily Francus, options/vol quant
    # --- HEDGE_FUND_PRINCIPALS ---
    "boazweinstein",       # Boaz Weinstein, Saba Capital
    "CliffordAsness",      # Cliff Asness, AQR Capital
    "DylanLeClair_",       # Dylan LeClair, BTC/macro analyst
    "cngarabedian",        # Institutional fund manager
    "RayDalio",            # Ray Dalio, Bridgewater founder
    # --- CONTRARIAN_VOICES ---
    "WallStCynic",         # Contrarian macro voice
    "rampagingruss",       # Contrarian analyst
    "orrdavid",            # David Orr, contrarian macro
    # REMOVED per Jamie directive (May 19): benjamincowen, 0xReflection,
    # InTheAssembly, NoLimitGains, realDonaldTrump, TheGoldPrairie, great_martis
]

# Chunking config: X API Basic tier has 512-char query limit
# ~11 accounts per chunk keeps queries under limit for 31 accounts (3 chunks)
ACCOUNTS_PER_CHUNK = 11

# Rate limit: 450 requests per 15-min window on Basic tier
# We pace our requests to stay well under
REQUEST_DELAY = 2  # seconds between requests


def get_bearer_token() -> str:
    """Get X_BEARER_TOKEN from environment."""
    token = os.environ.get("X_BEARER_TOKEN", "")
    if not token:
        raise RuntimeError(
            "X_BEARER_TOKEN not set. Add it to .env or set as environment variable."
        )
    return token


def build_query(ticker: str, accounts: list) -> str:
    """
    Build a Twitter API v2 search query for a ticker filtered by a chunk of accounts.
    Query must stay under 512 chars for Basic tier.
    
    Example: ($MSFT OR MSFT) (from:DeItaone OR from:MacroAlf OR ...)
    """
    ticker_terms = f"(${ticker} OR {ticker})"
    account_filters = " OR ".join([f"from:{acct}" for acct in accounts])
    query = f"{ticker_terms} ({account_filters})"
    
    if len(query) > 512:
        print(f"  [X Fetch] WARNING: Query chunk for {ticker} is {len(query)} chars (over 512 limit)")
    
    return query


def chunk_accounts(accounts: list, chunk_size: int = None) -> list:
    """
    Split the curated accounts into chunks that produce queries under 512 chars.
    Returns list of account-list chunks.
    """
    size = chunk_size or ACCOUNTS_PER_CHUNK
    return [accounts[i:i + size] for i in range(0, len(accounts), size)]


def search_recent_tweets(
    query: str,
    bearer_token: str,
    max_results: int = 100,
    start_time: str = None,
) -> list:
    """
    Call X API v2 search/recent endpoint.
    Returns list of tweet objects.
    """
    headers = {
        "Authorization": f"Bearer {bearer_token}",
    }
    
    params = {
        "query": query,
        "max_results": min(max_results, 100),  # API max is 100 per page
        "tweet.fields": "created_at,author_id,public_metrics,text",
        "user.fields": "username,name",
        "expansions": "author_id",
    }
    
    if start_time:
        params["start_time"] = start_time
    
    all_tweets = []
    next_token = None
    pages = 0
    max_pages = 5  # Cap pagination to avoid runaway costs
    
    while pages < max_pages:
        if next_token:
            params["next_token"] = next_token
        
        response = requests.get(X_API_URL, headers=headers, params=params, timeout=30)
        
        if response.status_code == 429:
            # Rate limited — wait and retry
            retry_after = int(response.headers.get("x-rate-limit-reset", 60)) - int(time.time())
            retry_after = max(retry_after, 15)
            print(f"  [X Fetch] Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        if response.status_code != 200:
            print(f"  [X Fetch] API error {response.status_code}: {response.text[:200]}")
            break
        
        data = response.json()
        
        tweets = data.get("data", [])
        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
        
        # Enrich tweets with username
        for tweet in tweets:
            author_id = tweet.get("author_id")
            if author_id in users:
                tweet["username"] = users[author_id].get("username", "unknown")
                tweet["author_name"] = users[author_id].get("name", "unknown")
        
        all_tweets.extend(tweets)
        
        # Check for pagination
        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
        
        pages += 1
        time.sleep(REQUEST_DELAY)
    
    return all_tweets


def fetch_smart_money_mentions(tickers: list) -> dict:
    """
    Fetch smart money X mentions for a list of tickers.
    7-day lookback window using search/recent endpoint.
    
    Returns: {
        "MSFT": [{"text": "...", "username": "...", "created_at": "...", ...}, ...],
        "JPM": [...],
        ...
    }
    """
    bearer_token = get_bearer_token()
    
    # 7-day lookback window (search/recent max is ~7 days anyway)
    start_time = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    mentions = {}
    
    # Chunk accounts to keep queries under 512-char API limit
    account_chunks = chunk_accounts(CURATED_ACCOUNTS)
    print(f"[X Fetch] Split {len(CURATED_ACCOUNTS)} accounts into {len(account_chunks)} chunks of ~{ACCOUNTS_PER_CHUNK}")
    
    for ticker in tickers:
        print(f"[X Fetch] Searching for {ticker} mentions from curated accounts...")
        
        all_tweets_for_ticker = []
        
        for chunk_idx, chunk in enumerate(account_chunks):
            query = build_query(ticker, chunk)
            
            try:
                tweets = search_recent_tweets(
                    query=query,
                    bearer_token=bearer_token,
                    max_results=100,
                    start_time=start_time,
                )
                all_tweets_for_ticker.extend(tweets)
            except Exception as e:
                print(f"  [X Fetch] {ticker} chunk {chunk_idx + 1}: Error -- {e}")
            
            # Pace between chunks
            time.sleep(REQUEST_DELAY)
        
        # Deduplicate by tweet ID
        seen_ids = set()
        clean_tweets = []
        for t in all_tweets_for_ticker:
            tid = t.get("id", "")
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            clean_tweets.append({
                "text": t.get("text", ""),
                "username": t.get("username", "unknown"),
                "author_name": t.get("author_name", "unknown"),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
            })
        
        mentions[ticker] = clean_tweets
        print(f"  [X Fetch] {ticker}: {len(clean_tweets)} mentions found ({len(account_chunks)} chunks queried)")
    
    return mentions


def run_x_fetch(tickers: list = None) -> dict:
    """
    Main entry point. Fetches X mentions and saves to output file.
    """
    # Load tickers from Agent 2 if not provided
    if not tickers:
        agent2_path = "output/agent2_candidates.json"
        if os.path.exists(agent2_path):
            with open(agent2_path) as f:
                agent2 = json.load(f)
            tickers = [c.get("ticker") for c in agent2.get("candidates", [])]
        
        if not tickers:
            raise RuntimeError("No tickers provided and no Agent 2 candidates found.")
    
    print(f"[X Fetch] Fetching smart money mentions for: {tickers}")
    print(f"[X Fetch] Curated accounts: {len(CURATED_ACCOUNTS)}")
    print(f"[X Fetch] Lookback: 7 days")
    
    mentions = fetch_smart_money_mentions(tickers)
    
    # Save output
    output = {
        "timestamp": datetime.now().isoformat(),
        "lookback_days": 7,
        "curated_accounts": CURATED_ACCOUNTS,
        "tickers_queried": tickers,
        "mentions": mentions,
        "total_mentions": sum(len(m) for m in mentions.values()),
    }
    
    os.makedirs("output", exist_ok=True)
    output_path = "output/smart_money_mentions.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n[X Fetch] Complete. {output['total_mentions']} total mentions saved to {output_path}")
    
    # Summary
    for ticker, tweets in mentions.items():
        if tweets:
            accounts_seen = set(t["username"] for t in tweets)
            print(f"  {ticker}: {len(tweets)} mentions from {len(accounts_seen)} accounts ({', '.join(accounts_seen)})")
        else:
            print(f"  {ticker}: No mentions from curated accounts")
    
    return output


if __name__ == "__main__":
    if "--from-agent2" in sys.argv:
        run_x_fetch()
    elif len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:] if not t.startswith("-")]
        run_x_fetch(tickers)
    else:
        print("Usage:")
        print("  python3 x_fetch.py MSFT JPM        # Specific tickers")
        print("  python3 x_fetch.py --from-agent2    # Read from Agent 2 output")
```
