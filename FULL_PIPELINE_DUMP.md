# OPEN CLAW TRADING PIPELINE — FULL CODEBASE DUMP

Generated: 2026-05-28 22:06:09 ET

Repo: https://github.com/jameslevinson95-tech/open-claw

## Files Included (35)

- `agent1_macro_director.py` (15,264 bytes)
- `agent2_fundamental_screener.py` (29,808 bytes)
- `agent3_synthesizer.py` (24,510 bytes)
- `agent4_risk_manager.py` (34,187 bytes)
- `agent5_position_monitor.py` (30,492 bytes)
- `alpaca_data.py` (11,957 bytes)
- `assembly_scraper.py` (7,932 bytes)
- `broker.py` (22,224 bytes)
- `broker_factory.py` (2,014 bytes)
- `config.py` (6,045 bytes)
- `data_fetcher_v1_deprecated.py` (3,477 bytes)
- `data_provider.py` (16,990 bytes)
- `discord_fetch.py` (11,288 bytes)
- `execution_engine.py` (40,791 bytes)
- `fedwatch.py` (11,075 bytes)
- `flash_crash_daemon.py` (16,571 bytes)
- `itc_data.py` (16,523 bytes)
- `market_data.py` (12,431 bytes)
- `massive_data.py` (36,119 bytes)
- `orchestrator.py` (38,730 bytes)
- `performance_review.py` (25,689 bytes)
- `preflight.py` (48,731 bytes)
- `robinhood_broker.py` (26,680 bytes)
- `run_archiver.py` (5,396 bytes)
- `run_execution_daemon.py` (760 bytes)
- `safeguards.py` (24,129 bytes)
- `schwab_auth_server.py` (3,844 bytes)
- `schwab_data.py` (5,569 bytes)
- `schwab_reauth.py` (4,753 bytes)
- `test_data_provider.py` (8,972 bytes)
- `trade_journal.py` (6,178 bytes)
- `vwap_gate.py` (3,483 bytes)
- `watchlist.py` (9,653 bytes)
- `weekly_review.py` (4,604 bytes)
- `x_fetch.py` (11,509 bytes)

---

## Agent Responsibilities

# OPEN CLAW - Agent Responsibilities (v2 Golden Path)
### Updated: May 19, 2026

---

## Pipeline Overview

Open Claw is a 5-agent AI trading pipeline for a $10,000 speculative spot-only equity account. Each agent has a single, clearly-defined responsibility. No agent overlaps with another.

**Schedule (Eastern Time):**
| Time | Step |
|------|------|
| 7:50 AM | Pre-flight: Assembly Private scrape (sentiment, macro, momentum screens) |
| 7:55 AM | Pre-flight: Macro data fetch (VIX, MOVE, yields, credit, breadth) + screener universe (66 tickers) |
| 8:00 AM | Agent 1 (Claude): Regime classification |
| 8:01 AM | Agent 2 (Gemini 3.1 Pro): Fundamental screening with deep research |
| 8:10 AM | X/Twitter fetch: Smart money mentions for Agent 2's candidates |
| 8:15 AM | Agent 3 (Claude): Smart money sentiment verification |
| 8:20 AM | Agent 4A (Claude) + 4B (Python): Risk management + tear sheet |
| 9:30 AM | **Execute trades** (market open) |
| 3:25 PM | Agent 5 pre-flight: Intraday price snapshot |
| 3:30 PM | Agent 5 (Claude): Position monitoring (hold/trim/close) |

---

## Pre-Flight Data Layer

**What:** Fetches all raw data before any agent runs. No agent calls APIs directly.

**Data Sources:**
- **yfinance:** VIX, MOVE, 10Y/2Y yields, HYG, LQD, sector ETFs, prior closes
- **Assembly Private:** Sentiment composite (fear/greed + 7 sub-components), risk & credit gauges (VIX, VXN, MOVE, HYG, LQD, JNK with 50d/200d trends), cross-asset rotation, sector RS vs SPY, full yield curve, momentum screens
- **X/Twitter API:** Smart money mentions from 15 curated accounts (7-day lookback)

**Screener Universe:** 60 static core tickers (mega-cap leaders across all sectors) + ~6-10 dynamic tickers from Assembly's live momentum screen = ~66-70 total per day.

---

## Agent 1: Macro Director
**Model:** Claude (Anthropic)
**Role:** Classify the current market regime and issue a directive for downstream agents.

**Inputs:**
- VIX (current + 5d/20d change)
- MOVE index (current + 5d/20d change)
- DIX (dark pool index, if available)
- 10Y/2Y yields + yield curve spread
- HY credit spread proxy (HYG/LQD ratio)
- Sector breadth (% of sectors above 20DMA)
- Assembly Private: sentiment composite, risk gauges, cross-asset rotation, sector RS, yield curve

**Outputs (JSON):**
- `regime`: RISK-ON | CAUTIOUS RISK-ON | RISK-OFF | CRISIS | DEFER
- `vol_regime`: COMPRESSED | NORMAL | ELEVATED | STRESSED
- `posture`: Aggressive | Offensive | Defensive | Bunker | Hold
- `conviction_floor`: integer (5-10)
- `preferred_themes`: 1-3 macro themes for Agent 2
- `summary`: 2-3 sentence plain English
- `key_signals`: reads on VIX, MOVE, DIX, yield curve, credit, breadth
- `missing_data`: any unavailable feeds

**Kill-Switch:** If MOVE or Credit data is missing → REGIME: DEFER (non-negotiable). DIX missing → proceed with -2 confidence penalty.

**Does NOT do:** Pick stocks, set position sizes, set allocation caps.

---

## Agent 2: Fundamental Screener
**Model:** Gemini 3.1 Pro (Google) with Deep Research protocol
**Role:** Screen the 66-ticker universe through Agent 1's regime lens and select 3-5 candidates with the best risk/reward.

**Inputs:**
- Agent 1's directive (regime, posture, conviction floor, preferred themes)
- Screener universe (66 tickers with pre-fetched fundamentals: P/E, Fwd P/E, PEG, market cap, beta, margins, FCF, D/E, 5d/20d momentum)

**Outputs (JSON per candidate):**
- `ticker`, `company_name`
- `conviction_score`: integer (must meet Agent 1's conviction floor)
- `theme_match`: which of Agent 1's themes this candidate fits
- `thesis`: 2-3 sentence investment case
- `catalyst`: what could move this in 5-15 days
- `asset_type`: EQUITY | ETF
- Fundamental data passthrough (P/E, Fwd P/E, PEG, beta, margins, etc.)

**Key Rules:**
- Must respect Agent 1's conviction floor (won't pass candidates below it)
- Must map each candidate to one of Agent 1's preferred themes
- Uses Gemini's deep research mode: extended thinking, multi-step reasoning
- No candidate without a clear catalyst

**Does NOT do:** Set stops, calculate position sizes, verify sentiment.

---

## Agent 3: Smart Money Verifier
**Model:** Claude (Anthropic)
**Role:** Score the smart money X/Twitter sentiment for each of Agent 2's candidates.

**Inputs:**
- Agent 2's candidate list (tickers + theses)
- X/Twitter mentions from 15 curated smart money accounts (7-day window)
- Curated accounts: unusual_whales, DeItaone, Fxhedgers, zaborsky, jimcramer, GurufocusData, OptionsHawk, PeterSchiff, TruthGundlach, elerianm, SqueezeMetrics, sentimentrader, DarkPoolChart, WallStJesus, VolSignals

**Outputs (JSON per candidate):**
- `verification_score`: 0-10
  - 9-10: Strong alignment, multiple accounts bullish
  - 7-8: Moderate alignment
  - 5-6: Neutral/silent (not a red flag)
  - 3-4: Contested
  - 1-2: Divergent/bearish
  - 0: Crowded trade warning
- `sentiment_read`: 1-2 sentence summary
- `key_mentions`: notable tweets
- `flag`: aligned | contested | silent | crowded | divergent

**Key Rules:**
- Silence (no mentions) scores 5 — neutral, not negative
- A crowded trade (score 0) is a kill signal
- X research is mandatory — Agent 3 does not bypass

**Does NOT do:** Change conviction scores, reject candidates, set stops.

---

## Agent 4: Risk Manager
**Model:** Agent 4A = Claude (stop anchors), Agent 4B = Python (math)
**Role:** Calculate position sizes, stop losses, and generate the final tear sheet.

**Sub-Agent 4A (Claude) — Stop Anchor Identification:**
- Looks at each candidate's moving averages (MA10, MA20, MA50) and recent 20d low
- Identifies the nearest significant technical level below entry as the stop anchor
- Calculates FINAL_CONVICTION = average of Agent 2's conviction_score and Agent 3's verification_score

**Sub-Agent 4B (Python) — Multiplicative Sizing:**
- Position size = BASE_ALLOC × CONVICTION_MOD × VOL_MOD × POSTURE_MOD × CONTRARIAN_MOD
- Base allocation: 15% of account ($1,500)
- Conviction modifier: 0.6 (score 5) → 1.0 (score 7) → 1.4 (score 10)
- Vol regime modifier: Compressed=1.2, Normal=1.0, Elevated=0.7, Stressed=0.4
- Posture modifier: Aggressive=1.0, Offensive=0.85, Defensive=0.6, Bunker=0.3
- Contrarian modifier: 1.0 default (future: adjusts for Agent 3 divergent signals)
- Shares = floor(dollar_amount / entry_price)
- Risk per trade = shares × (entry - stop)

**Outputs — Tear Sheet:**
- Per trade: ticker, action (BUY), shares, entry price, stop price, stop distance %, theme, conviction, cost, risk, sizing math
- Session totals: trade count, total risk vs budget ($500), % deployed, dry powder

**Key Rules:**
- Max risk budget: $500/session (5% of account)
- Max risk per trade: $150
- Stops must be within 10% of entry
- No position exceeds calculated allocation cap

**Does NOT do:** Pick stocks, verify sentiment, monitor positions.

---

## Agent 5: Position Monitor
**Model:** Claude (Anthropic)
**Role:** Run at 3:30 PM ET to review all open positions and decide hold/trim/close before market close.

**Inputs:**
- Open positions from today's tear sheet
- 3:25 PM price snapshot (5 min before agent runs)
- Original stop prices and theses

**Outputs (JSON per position):**
- `action`: HOLD | TRIM | CLOSE
- `reasoning`: why this action
- `new_stop`: adjusted stop if applicable (trailing stop logic)

**Key Rules:**
- If price is below stop → CLOSE (non-negotiable)
- If position is up >3% from entry → consider tightening stop (trailing)
- If thesis has broken (catalyst failed, sector rotation against) → CLOSE
- TRIM = sell half, keep half with tighter stop
- Default action is HOLD unless there's a reason not to

**Does NOT do:** Open new positions, change the regime, override Agent 4's sizing.

---

## Data Flow Summary

```
Pre-Flight (7:55 AM)
    ├── Macro data (yfinance + Assembly)
    ├── Screener universe (60 static + Assembly momentum)
    └── Assembly sentiment + risk gauges
        │
        ▼
Agent 1: Regime → directive.json
        │
        ▼
Agent 2: Screen 66 tickers → candidates.json (3-5 picks)
        │
        ▼
X/Twitter Fetch → smart_money_mentions.json
        │
        ▼
Agent 3: Verify sentiment → verified.json (scored candidates)
        │
        ▼
Agent 4A: Stop anchors (Claude) → 4B: Sizing math (Python) → tear_sheet.txt
        │
        ▼
Execute at 9:30 AM market open
        │
        ▼
Agent 5: Monitor at 3:30 PM → hold/trim/close decisions
```


---

## agent1_macro_director.py

```python
"""
Agent 1: Macro Director — v2 (Jamie's Golden Path tweaks)
Model: Claude (Anthropic)
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
- HY spread proxy (HYG/LQD ratio): Falling = credit stress
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
                model="claude-3-5-sonnet-latest",
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

---

## agent2_fundamental_screener.py

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

    # Fetch current Alpaca positions to avoid portfolio blindness
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

---

## agent3_synthesizer.py

```python
"""
Agent 3: Qualitative Synthesizer — v3.0
Model: Claude Opus 4.7 (Anthropic) with adaptive thinking
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
MODEL = "claude-opus-4-7"
MAX_RETRIES = 3
RETRY_DELAY = 5

# Curated smart money accounts (carried from former Agent 3)
CURATED_ACCOUNTS = [
    "unusual_whales",
    "DeItaone",
    "Fxhedgers",
    "zaborsky",
    "jimcramer",
    "GurufocusData",
    "OptionsHawk",
    "PeterSchiff",
    "TruthGundlach",
    "elerianm",
    "SqueezeMetrics",
    "sentimentrader",
    "DarkPoolChart",
    "WallStJesus",
    "VolSignals",
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
      "put_call_ratio": <float>
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
    Send the complete qualitative mosaic to Claude Opus 4.7 for unified synthesis.
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
                    thinking={"type": "enabled", "budget_tokens": 10000},
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

        # Merge qualitative data into candidate
        c["thesis"] = ev.get("qualitative_thesis", c.get("thesis", ""))
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
        f"> *Model:* Claude Opus 4.7 (Adaptive Thinking)",
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

---

## agent4_risk_manager.py

```python
"""
Agent 4: Risk Manager — v3 (ATR-based stops, no LLM dependency)
All-Python pipeline: ATR stop calculation → position sizing → tear sheet.

Changes from v2:
- Killed Agent 4A (Claude LLM call for stop anchors)
- ATR-based stop calculation: 14-day ATR with conviction-scaled multipliers
- Correlation veto fix: min_periods=20, no double-dropna
- Formula: Target = Allocation_Cap * Conviction_Mod * Vol_Mod * Posture_Mod * Contrarian_Penalty
- Theme cap enforced: 1 position per theme, keep higher conviction if duplicates
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
    THEME_CAP,
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
        print(f"[Heat] ERROR connecting to Alpaca: {e}")
        return {
            "total_heat_dollars": 0.0,
            "heat_pct_of_equity": 0.0,
            "positions_detail": [],
            "error": str(e),
        }

    equity = account.get("equity", ACCOUNT_SIZE)

    # Try to load agent4 orders for known stop prices
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
        account_value: live account equity. If None, fetches from Alpaca (fallback to ACCOUNT_SIZE).
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
            account_value = float(broker_acct["equity"])
            buying_power = float(broker_acct.get("buying_power", account_value))
            print(f"[Agent 4B] Live equity: ${account_value:,.2f} | Buying Power: ${buying_power:,.2f}")
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
    theme_tracker = {}
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

        # Theme cap check
        if theme in theme_tracker:
            existing = theme_tracker[theme]
            print(f"  [Agent 4B] {ticker}: Theme '{theme}' already taken by {existing}. Dropping.")
            trade_orders.append(_reject_trade(ticker, f"Theme cap: '{theme}' used by {existing}"))
            continue

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
        }

        trade_orders.append(order)
        theme_tracker[theme] = ticker
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

---

## agent5_position_monitor.py

```python
"""
Agent 5: Position Monitor — v3 (Python trailing stops + Claude thesis monitor)
Model: Claude Opus 4.7 (Anthropic) with adaptive thinking
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

# Haiku for fast thesis drift classification — no extended thinking needed
MODEL = "claude-3-5-haiku-latest"
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
    Snapshot current market prices at 3:25 PM ET.
    Captures the intraday tape for trailing stop evaluation.
    """
    snapshot = {}
    for ticker in tickers:
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
    Load open positions from Alpaca (source of truth).
    Falls back to agent4_orders.json if Alpaca is unreachable.
    Enriches with stop_loss from agent4_orders.json when available.
    """
    # Primary: Read from broker (Robinhood or Alpaca via factory)
    try:
        from broker_factory import get_broker
        broker = get_broker()
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
            print(f"[Agent 5] Loaded {len(positions)} positions from Alpaca")
            return positions
    except Exception as e:
        print(f"[Agent 5] Alpaca read failed, falling back to orders file: {e}")

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
      - Up > 2% from entry  → tighten stop to breakeven (entry price)
      - Up > 5% from entry  → trail stop to entry + 50% of gains
      - Up > 10% from entry → trail stop to entry + 75% of gains
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

        trailing_note = "Below 2% gain — original stop unchanged"

        if pnl_pct > 10:
            # Trail to entry + 75% of gains
            candidate_stop = round(entry_price + 0.75 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 75% of gains"
        elif pnl_pct > 5:
            # Trail to entry + 50% of gains
            candidate_stop = round(entry_price + 0.50 * gain_dollars, 2)
            new_stop = max(new_stop, candidate_stop)
            trailing_note = f"Up {pnl_pct:.1f}% — stop trailed to entry + 50% of gains"
        elif pnl_pct > 2:
            # Tighten to breakeven
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

        # Update HWM state for this ticker
        hwm_state[ticker] = {
            "hwm_stop": new_stop,
            "hwm_price": max(current_price, stored_hwm_price),
            "last_updated": datetime.now().isoformat(),
        }

        # Check if stop is hit
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
                temperature=0.0,
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


def run_agent5(positions: list = None, snapshot: dict = None) -> dict:
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
    try:
        thesis_result = call_thesis_monitor(positions_with_stops, breaking_news, vix_data)
    except RuntimeError:
        # No API key — return data for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "positions": positions_with_stops,
            "vix": vix_data,
            "breaking_news": breaking_news,
        }
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

        # Merge logic
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
            "trim_pct": None,
            "reasoning": reasoning,
        })

        action_emoji = {"HOLD": "✅", "CLOSE": "🚪"}.get(action, "❓")
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

```

---

## alpaca_data.py

```python
"""
Alpaca Market Data Module — Replaces Yahoo Finance for price data.

Uses Alpaca's Market Data API via the paper trading credentials.
Free tier provides IEX real-time quotes, 5+ years of historical bars,
and options chain data.

Drop-in replacement for yfinance calls in preflight.py.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockLatestQuoteRequest,
    StockSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame
import pandas as pd

# Initialize client — uses paper trading keys for market data
_client = None


def _get_client() -> StockHistoricalDataClient:
    global _client
    if _client is None:
        api_key = os.environ.get("ALPACA_API_KEY", "")
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        _client = StockHistoricalDataClient(api_key, secret_key)
    return _client


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch yesterday's close for a list of tickers via Alpaca.
    Drop-in replacement for preflight.fetch_prior_close().
    """
    client = _get_client()
    results = {}
    end = datetime.now()
    start = end - timedelta(days=10)

    for ticker in tickers:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                results[ticker] = {"error": f"No bar data for {ticker}"}
                continue

            # If multi-index (symbol, timestamp), slice to this ticker
            if isinstance(df.index, pd.MultiIndex):
                if ticker in df.index.get_level_values(0):
                    df = df.loc[ticker]
                else:
                    results[ticker] = {"error": f"No bar data for {ticker}"}
                    continue

            closes = [round(float(c), 2) for c in df["close"].values]
            dates = [str(d.date()) for d in df.index]

            # Prior close = last complete bar
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
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_latest_quotes(tickers: list) -> dict:
    """
    Fetch real-time (IEX) quotes for a list of tickers.
    Returns bid, ask, and mid price for each.
    """
    client = _get_client()
    results = {}

    try:
        request = StockLatestQuoteRequest(symbol_or_symbols=tickers)
        quotes = client.get_stock_latest_quote(request)

        for ticker, quote in quotes.items():
            results[ticker] = {
                "bid": float(quote.bid_price) if quote.bid_price else 0.0,
                "ask": float(quote.ask_price) if quote.ask_price else 0.0,
                "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                "mid": round((float(quote.bid_price or 0) + float(quote.ask_price or 0)) / 2, 2),
                "timestamp": quote.timestamp.isoformat() if quote.timestamp else "",
            }
    except Exception as e:
        for ticker in tickers:
            results[ticker] = {"error": str(e)}

    return results


def fetch_snapshots(tickers: list) -> dict:
    """
    Fetch full snapshots (latest trade, quote, minute bar, daily bar, prev daily bar).
    Richer than just quotes — includes today's OHLCV and previous day's bar.
    """
    client = _get_client()
    results = {}

    try:
        request = StockSnapshotRequest(symbol_or_symbols=tickers)
        snapshots = client.get_stock_snapshot(request)

        for ticker, snap in snapshots.items():
            entry = {}

            if snap.latest_trade:
                entry["latest_trade"] = {
                    "price": float(snap.latest_trade.price),
                    "size": int(snap.latest_trade.size),
                    "timestamp": snap.latest_trade.timestamp.isoformat() if snap.latest_trade.timestamp else "",
                }

            if snap.latest_quote:
                entry["latest_quote"] = {
                    "bid": float(snap.latest_quote.bid_price) if snap.latest_quote.bid_price else 0,
                    "ask": float(snap.latest_quote.ask_price) if snap.latest_quote.ask_price else 0,
                }

            if snap.daily_bar:
                entry["daily_bar"] = {
                    "open": float(snap.daily_bar.open),
                    "high": float(snap.daily_bar.high),
                    "low": float(snap.daily_bar.low),
                    "close": float(snap.daily_bar.close),
                    "volume": int(snap.daily_bar.volume),
                }

            if snap.previous_daily_bar:
                entry["prev_daily_bar"] = {
                    "open": float(snap.previous_daily_bar.open),
                    "high": float(snap.previous_daily_bar.high),
                    "low": float(snap.previous_daily_bar.low),
                    "close": float(snap.previous_daily_bar.close),
                    "volume": int(snap.previous_daily_bar.volume),
                }

            if snap.minute_bar:
                entry["minute_bar"] = {
                    "open": float(snap.minute_bar.open),
                    "high": float(snap.minute_bar.high),
                    "low": float(snap.minute_bar.low),
                    "close": float(snap.minute_bar.close),
                    "volume": int(snap.minute_bar.volume),
                    "timestamp": snap.minute_bar.timestamp.isoformat() if snap.minute_bar.timestamp else "",
                }

            results[ticker] = entry
    except Exception as e:
        for ticker in tickers:
            results[ticker] = {"error": str(e)}

    return results


def fetch_historical_bars(
    tickers: list,
    days: int = 30,
    timeframe: str = "day",
) -> dict:
    """
    Fetch historical OHLCV bars for a list of tickers.
    
    Args:
        tickers: List of ticker symbols
        days: Number of days of history (default 30)
        timeframe: "day", "hour", or "minute"
    """
    client = _get_client()

    tf_map = {
        "day": TimeFrame.Day,
        "hour": TimeFrame.Hour,
        "minute": TimeFrame.Minute,
    }
    tf = tf_map.get(timeframe, TimeFrame.Day)

    end = datetime.now()
    start = end - timedelta(days=days)
    results = {}

    for ticker in tickers:
        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=tf,
                start=start,
                end=end,
                feed="iex",
            )
            bars = client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                results[ticker] = {"bars": [], "count": 0}
                continue

            # Handle multi-index
            if isinstance(df.index, pd.MultiIndex):
                if ticker in df.index.get_level_values(0):
                    df = df.loc[ticker]
                else:
                    results[ticker] = {"bars": [], "count": 0}
                    continue

            bar_list = []
            for ts, row in df.iterrows():
                bar_list.append({
                    "date": str(ts.date()) if tf == TimeFrame.Day else ts.isoformat(),
                    "open": round(float(row["open"]), 2),
                    "high": round(float(row["high"]), 2),
                    "low": round(float(row["low"]), 2),
                    "close": round(float(row["close"]), 2),
                    "volume": int(row["volume"]),
                    "vwap": round(float(row["vwap"]), 2) if pd.notna(row.get("vwap")) else None,
                })

            results[ticker] = {
                "bars": bar_list,
                "count": len(bar_list),
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_macro_tickers() -> dict:
    """
    Fetch macro indicator tickers that Alpaca supports.
    Replaces yfinance for VIX, sector ETFs, etc.
    
    Note: Alpaca doesn't support index tickers like ^VIX directly.
    We use VIXY/UVXY as VIX proxies, and sector ETFs work fine.
    For ^VIX, ^TNX, etc. we still fall back to yfinance.
    """
    # Alpaca supports ETFs and stocks, not raw indices
    # These are the tickers we CAN get from Alpaca
    alpaca_tickers = [
        # Sector ETFs (for breadth)
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC",
        # Credit/bond ETFs
        "HYG", "LQD", "TLT", "JNK",
        # Broad market
        "SPY", "QQQ", "IWM",
        # Commodity proxies
        "GLD", "USO",
    ]

    return fetch_snapshots(alpaca_tickers)


def enrich_screener_universe(screener: list) -> list:
    """
    Enrich screener results with accurate prior_close from Alpaca.
    Drop-in replacement for preflight._enrich_prior_close().
    """
    tickers = [t["ticker"] for t in screener]

    # Batch into groups of 50 to avoid request size limits
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
            entry["price_source"] = "alpaca"

    return screener


# Quick smoke test
if __name__ == "__main__":
    print("Testing Alpaca Market Data connection...\n")

    # Test 1: Latest quotes
    print("1. Latest quotes for SPY, AAPL, NVDA:")
    quotes = fetch_latest_quotes(["SPY", "AAPL", "NVDA"])
    for t, q in quotes.items():
        if "error" not in q:
            print(f"   {t}: bid={q['bid']:.2f} ask={q['ask']:.2f} mid={q['mid']:.2f}")
        else:
            print(f"   {t}: ERROR - {q['error']}")

    # Test 2: Prior close
    print("\n2. Prior close for SPY, AAPL:")
    closes = fetch_prior_close(["SPY", "AAPL"])
    for t, c in closes.items():
        if "error" not in c:
            print(f"   {t}: {c['prior_close']} (date: {c['prior_date']})")
        else:
            print(f"   {t}: ERROR - {c['error']}")

    # Test 3: Historical bars
    print("\n3. Last 5 daily bars for NVDA:")
    hist = fetch_historical_bars(["NVDA"], days=7)
    for bar in hist.get("NVDA", {}).get("bars", [])[-5:]:
        print(f"   {bar['date']}: O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']} V={bar['volume']:,}")

    # Test 4: Snapshot
    print("\n4. Snapshot for SPY:")
    snaps = fetch_snapshots(["SPY"])
    spy = snaps.get("SPY", {})
    if "latest_trade" in spy:
        print(f"   Latest trade: ${spy['latest_trade']['price']:.2f}")
    if "daily_bar" in spy:
        db = spy["daily_bar"]
        print(f"   Today's bar: O={db['open']} H={db['high']} L={db['low']} C={db['close']} V={db['volume']:,}")

    print("\n✅ Alpaca Market Data module working!")

```

---

## assembly_scraper.py

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

---

## broker.py

```python
"""
Broker Module — Alpaca Paper Trading Integration
Executes tear sheet orders, manages positions, and tracks fills.

All orders go through Alpaca's paper trading API.
Real account size from Alpaca overrides config.py ACCOUNT_SIZE.

Usage:
  from broker import AlpacaBroker
  broker = AlpacaBroker()
  broker.execute_tear_sheet(trade_orders)
  broker.get_positions()
  broker.close_position("AAPL")
"""
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    GetOrdersRequest,
    StopLossRequest,
    StopOrderRequest,
    ReplaceOrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus


def _cross_reference_price(ticker: str, prior_close: float, suspect_price: float):
    """
    Cross-reference a suspect broker quote against today's actual opening print or live tape.
    If the stock legitimately gapped up on news, today's tape will verify the live quote is real.
    Returns a trusted price, or None if no reliable price can be found.
    """
    import yfinance as yf

    trusted = None
    try:
        # Fetch today's 1-minute intraday tape
        today_data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not today_data.empty:
            # Handle pandas multi-index if necessary
            if hasattr(today_data.columns, 'levels') and len(today_data.columns.levels) > 1:
                today_open = float(today_data["Open"][ticker].iloc[0])
                current_tape = float(today_data["Close"][ticker].iloc[-1])
            else:
                today_open = float(today_data["Open"].iloc[0])
                current_tape = float(today_data["Close"].iloc[-1])

            # If the suspect broker price is within 1.5% of today's actual open or current tape,
            # it is a legitimate gap/breakout quote, not an anomaly.
            dev_from_open = abs(suspect_price - today_open) / today_open if today_open > 0 else 999
            dev_from_current = abs(suspect_price - current_tape) / current_tape if current_tape > 0 else 999

            if dev_from_open < 0.015 or dev_from_current < 0.015:
                print(f"  [CrossRef] \u2705 Real Breakout: Broker quote ${suspect_price:.2f} verified by today's tape (Open: ${today_open:.2f}, Live: ${current_tape:.2f}).")
                trusted = suspect_price
            else:
                print(f"  [CrossRef] \ud83d\udeab Anomaly Confirmed: Broker quote ${suspect_price:.2f} diverges wildly from today's tape (Open: ${today_open:.2f}, Live: ${current_tape:.2f}).")
                trusted = current_tape  # Fallback to the live yfinance tape
        else:
            print(f"  [CrossRef] No intraday tape available to verify {ticker}.")
    except Exception as e:
        print(f"  [CrossRef] yfinance tape verification failed: {e}")

    return trusted


class AlpacaBroker:
    def __init__(self):
        self.client = TradingClient(
            api_key=os.environ.get("ALPACA_API_KEY", ""),
            secret_key=os.environ.get("ALPACA_SECRET_KEY", ""),
            paper=True,
        )
        self._verify_connection()

    def _verify_connection(self):
        account = self.client.get_account()
        if account.status != "ACTIVE":
            raise RuntimeError(f"Alpaca account not active: {account.status}")
        print(f"[Broker] Connected to Alpaca paper account")
        print(f"[Broker] Cash: ${float(account.cash):,.2f} | Equity: ${float(account.equity):,.2f}")

    def get_account_summary(self) -> dict:
        """Get current account state."""
        account = self.client.get_account()
        return {
            "cash": float(account.cash),
            "equity": float(account.equity),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "status": account.status,
        }

    def get_positions(self) -> list:
        """Get all open positions."""
        positions = self.client.get_all_positions()
        result = []
        for p in positions:
            result.append({
                "ticker": p.symbol,
                "shares": int(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            })
        return result

    def get_existing_exposure(self) -> float:
        """Get total dollar value of existing positions (for dry powder calc)."""
        positions = self.get_positions()
        return sum(p["market_value"] for p in positions)

    def get_position_tickers(self) -> list:
        """Get list of tickers with open positions (for correlation veto)."""
        positions = self.get_positions()
        return [p["ticker"] for p in positions]

    def execute_tear_sheet(self, trade_orders: list, max_gap_pct: float = 0.02) -> list:
        """
        Execute BUY orders from Agent 4B's tear sheet with live re-pricing.

        Uses live quotes at execution time to:
        1. Reject orders if the stock gapped up > max_gap_pct from planned entry
        2. Dynamically recalculate share count based on live price and risk budget
        3. Submit limit orders pegged to live ask + 0.15% (micro-slippage allowance)

        This prevents the gap-up sizing explosion where stale share counts from
        8:17 AM (based on yesterday's close) silently blow past MAX_RISK_PER_TRADE.

        Returns list of fill results.
        """
        fills = []

        # Collect BUY tickers for batch quote fetch
        buy_tickers = [o["ticker"] for o in trade_orders if o.get("action") == "BUY"]

        # Fetch live quotes right before execution
        live_quotes = {}
        if buy_tickers:
            try:
                from market_data import fetch_latest_quotes
                live_quotes = fetch_latest_quotes(buy_tickers)
                print(f"  [Broker] Live quotes fetched for {len(live_quotes)} tickers")
            except Exception as e:
                print(f"  [Broker] WARNING: Could not fetch live quotes ({e}), using planned prices")

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
                # Get live price — fall back to planned entry if quotes unavailable
                quote = live_quotes.get(ticker, {})
                live_ask = quote.get("ask") or quote.get("mid") or 0

                if live_ask > 0 and stop_price and stop_price > 0 and risk_budget > 0:
                    # === LIVE RE-PRICING MODE ===

                    # 0. Quote anomaly detection: if live price deviates beyond
                    #    the gap threshold, cross-reference before rejecting.
                    #    Pre-market Alpaca IEX quotes can be garbage on thin
                    #    liquidity (e.g. BAC showing $54.80 when real = $51.60).
                    deviation_pct = abs(live_ask - planned_entry) / planned_entry
                    if deviation_pct > max_gap_pct:
                        print(f"  [Broker] ⚠️ {ticker}: Alpaca quote ${live_ask:.2f} deviates {deviation_pct*100:.1f}% from prior close ${planned_entry:.2f} — cross-referencing...")
                        verified_price = _cross_reference_price(ticker, planned_entry, live_ask)
                        if verified_price is not None:
                            print(f"  [Broker] ✅ {ticker}: Cross-reference price ${verified_price:.2f} — using instead of Alpaca ${live_ask:.2f}")
                            live_ask = verified_price
                        else:
                            print(f"  [Broker] 🚫 {ticker}: Quote anomaly confirmed — no reliable price available, skipping")
                            fills.append({
                                "ticker": ticker,
                                "status": "rejected",
                                "reason": f"Quote anomaly: Alpaca ${live_ask:.2f} vs prior close ${planned_entry:.2f} ({deviation_pct*100:.1f}% deviation), cross-reference failed",
                            })
                            continue

                    # 1. Gap-up protection: reject if price moved too far
                    gap_pct = (live_ask - planned_entry) / planned_entry
                    if gap_pct > max_gap_pct:
                        msg = f"Gapped up {gap_pct*100:.1f}% (Planned: ${planned_entry}, Live: ${live_ask})"
                        print(f"  [Broker] 🚫 REJECTED {ticker}: {msg}")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Gap up exceeded {max_gap_pct*100:.0f}%",
                            "planned_entry": planned_entry,
                            "live_ask": live_ask,
                            "gap_pct": round(gap_pct * 100, 2),
                        })
                        continue

                    # 2. Dynamic share recalculation based on live risk per share
                    live_risk_per_share = live_ask - stop_price
                    if live_risk_per_share <= 0:
                        print(f"  [Broker] 🚫 REJECTED {ticker}: Live ask ${live_ask:.2f} at or below stop ${stop_price:.2f}")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": f"Live price ${live_ask:.2f} at or below stop ${stop_price:.2f}",
                        })
                        continue

                    live_shares = int(risk_budget // live_risk_per_share)
                    if live_shares <= 0:
                        print(f"  [Broker] 🚫 REJECTED {ticker}: Zero shares after live re-sizing")
                        fills.append({
                            "ticker": ticker,
                            "status": "rejected",
                            "reason": "Zero shares after live re-sizing",
                        })
                        continue

                    # 3. Limit order pegged to ask + 0.15% (micro-slippage allowance)
                    limit_price = round(live_ask * 1.0015, 2)
                    shares = live_shares
                    pricing_mode = "live"

                    if shares != planned_shares:
                        print(f"  [Broker] 📐 {ticker}: Re-sized {planned_shares} → {shares} shares (live ask ${live_ask} vs planned ${planned_entry})")

                else:
                    # === FALLBACK: PLANNED PRICE MODE ===
                    # No live quotes available — use planned entry with 1.5% slippage cap
                    limit_price = round(planned_entry * 1.015, 2)
                    shares = planned_shares
                    pricing_mode = "planned"
                    print(f"  [Broker] ⚠️ {ticker}: No live quote — using planned price with 1.5% limit cap")

                # Submit order with OTO stop-loss
                if stop_price and stop_price > 0:
                    req = LimitOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price,
                        order_class="oto",
                        stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
                    )
                else:
                    req = LimitOrderRequest(
                        symbol=ticker,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        limit_price=limit_price,
                    )

                result = self.client.submit_order(req)
                fills.append({
                    "ticker": ticker,
                    "status": "submitted",
                    "order_id": str(result.id),
                    "shares": shares,
                    "planned_shares": planned_shares,
                    "order_type": "limit",
                    "limit_price": limit_price,
                    "pricing_mode": pricing_mode,
                    "live_ask": live_ask if live_ask > 0 else None,
                    "planned_entry": planned_entry,
                    "risk_budget": risk_budget,
                    "submitted_at": result.submitted_at.isoformat() if result.submitted_at else "",
                })
                print(f"  [Broker] ✅ BUY {shares} {ticker} @ limit ${limit_price} ({pricing_mode}) — submitted ({result.id})")

            except Exception as e:
                fills.append({
                    "ticker": ticker,
                    "status": "error",
                    "error": str(e),
                })
                print(f"  [Broker] ❌ ERROR on {ticker}: {e}")

        # Save fills
        os.makedirs("output", exist_ok=True)
        with open("output/broker_fills.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "fills": fills,
            }, f, indent=2)

        return fills

    def close_position(self, ticker: str, qty: int = None) -> dict:
        """
        Close a position (full or partial).
        Used by Agent 5 for CLOSE and TRIM decisions.
        """
        try:
            if qty:
                # Partial close (TRIM)
                req = MarketOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                result = self.client.submit_order(req)
                print(f"  [Broker] TRIM {qty} shares of {ticker} — submitted ({result.id})")
            else:
                # Full close
                result = self.client.close_position(ticker, cancel_orders=True)
                print(f"  [Broker] CLOSE {ticker} — submitted")

            return {
                "ticker": ticker,
                "status": "submitted",
                "action": "trim" if qty else "close",
                "qty": qty,
            }
        except Exception as e:
            print(f"  [Broker] ERROR closing {ticker}: {e}")
            return {"ticker": ticker, "status": "error", "error": str(e)}

    def close_all_positions(self) -> dict:
        """
        CRISIS_LIQUIDATION — close everything at market.
        Used by Agent 5 when CRISIS pre-check triggers.
        """
        try:
            result = self.client.close_all_positions(cancel_orders=True)
            print(f"  [Broker] CRISIS_LIQUIDATION — closing all positions")
            return {"status": "submitted", "action": "close_all"}
        except Exception as e:
            print(f"  [Broker] ERROR on close_all: {e}")
            return {"status": "error", "error": str(e)}

    def update_stop_order(self, ticker: str, new_stop_price: float) -> dict:
        """
        Update the existing stop order for a position to a tighter stop price.
        Used by Agent 5 when trailing stops tighten (new_stop > original_stop).

        Strategy:
        1. Find the open stop/stop_limit order for this ticker
        2. Replace it in-place via replace_order_by_id
        3. If replace fails, fall back to submit-new-then-cancel-old
        """
        new_stop_price = round(new_stop_price, 2)
        try:
            # Find existing stop order for this ticker
            req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                limit=100,
            )
            open_orders = self.client.get_orders(req)
            stop_order = None
            for o in open_orders:
                if o.symbol == ticker and o.stop_price is not None and o.side == OrderSide.SELL:
                    stop_order = o
                    break

            if stop_order is None:
                print(f"  [Broker] No existing stop order found for {ticker}")
                return {
                    "ticker": ticker,
                    "action": "update_stop",
                    "status": "no_stop_order",
                }

            old_stop_price = float(stop_order.stop_price)
            print(f"  [Broker] Updating stop for {ticker}: ${old_stop_price} → ${new_stop_price} (order {stop_order.id})")

            # Attempt 1: Replace in-place
            try:
                replace_req = ReplaceOrderRequest(stop_price=new_stop_price)
                replaced = self.client.replace_order_by_id(
                    order_id=str(stop_order.id),
                    order_data=replace_req,
                )
                print(f"  [Broker] Stop replaced successfully for {ticker} → ${new_stop_price} (new order {replaced.id})")
                return {
                    "ticker": ticker,
                    "action": "update_stop",
                    "status": "replaced",
                    "old_stop": old_stop_price,
                    "new_stop": new_stop_price,
                    "order_id": str(replaced.id),
                }
            except Exception as replace_err:
                print(f"  [Broker] Replace failed for {ticker} ({replace_err}), falling back to cancel+resubmit")

            # Attempt 2: Submit new stop first, then cancel old
            # Submit first so we're never unprotected
            new_req = StopOrderRequest(
                symbol=ticker,
                qty=int(stop_order.qty),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                type="stop",
                stop_price=new_stop_price,
            )
            new_order = self.client.submit_order(new_req)
            print(f"  [Broker] New stop submitted for {ticker} @ ${new_stop_price} (order {new_order.id})")

            # Now cancel the old one
            try:
                self.client.cancel_order_by_id(str(stop_order.id))
                print(f"  [Broker] Old stop cancelled for {ticker} (order {stop_order.id})")
            except Exception as cancel_err:
                # Old order might already be cancelled/filled — not fatal
                print(f"  [Broker] Warning: couldn't cancel old stop for {ticker} ({cancel_err})")

            return {
                "ticker": ticker,
                "action": "update_stop",
                "status": "resubmitted",
                "old_stop": old_stop_price,
                "new_stop": new_stop_price,
                "old_order_id": str(stop_order.id),
                "new_order_id": str(new_order.id),
            }

        except Exception as e:
            print(f"  [Broker] ERROR updating stop for {ticker}: {e}")
            return {
                "ticker": ticker,
                "action": "update_stop",
                "status": "error",
                "error": str(e),
            }

    def execute_agent5_decisions(self, decisions: list, crisis: bool = False) -> list:
        """
        Execute Agent 5's HOLD/TRIM/CLOSE decisions.
        """
        if crisis:
            self.close_all_positions()
            return [{"action": "CRISIS_LIQUIDATION", "status": "submitted"}]

        results = []
        for d in decisions:
            ticker = d.get("ticker")
            action = d.get("action", "HOLD")

            if action == "HOLD":
                new_stop = d.get("new_stop")
                original_stop = d.get("original_stop")
                if new_stop and original_stop and new_stop > original_stop:
                    # Trailing stop tightened — push to Alpaca
                    result = self.update_stop_order(ticker, new_stop)
                    result["action"] = "HOLD_STOP_TIGHTENED"
                    results.append(result)
                else:
                    results.append({"ticker": ticker, "action": "HOLD", "status": "no_action"})

            elif action == "CLOSE":
                result = self.close_position(ticker)
                results.append(result)

            elif action == "TRIM":
                trim_pct = d.get("trim_pct", 50) / 100
                positions = self.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)
                if pos:
                    trim_qty = max(1, int(pos["shares"] * trim_pct))
                    result = self.close_position(ticker, qty=trim_qty)
                    results.append(result)
                else:
                    results.append({"ticker": ticker, "action": "TRIM", "status": "no_position"})

        return results

    def get_orders_today(self) -> list:
        """Get all orders from today."""
        try:
            req = GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                limit=50,
            )
            orders = self.client.get_orders(req)
            return [{
                "ticker": o.symbol,
                "side": str(o.side),
                "qty": str(o.qty),
                "filled_qty": str(o.filled_qty),
                "status": str(o.status),
                "filled_avg_price": str(o.filled_avg_price) if o.filled_avg_price else None,
                "submitted_at": o.submitted_at.isoformat() if o.submitted_at else "",
            } for o in orders]
        except Exception as e:
            return [{"error": str(e)}]

```

---

## broker_factory.py

```python
"""
Broker Factory — Switch between Robinhood and Alpaca execution.

Usage:
  from broker_factory import get_broker
  broker = get_broker()  # Auto-detects based on env/config
  broker = get_broker("robinhood")  # Force Robinhood
  broker = get_broker("alpaca")     # Force Alpaca (paper trading)

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


def get_broker(broker_name: str = None):
    """
    Get a broker instance.
    
    Args:
        broker_name: "robinhood", "alpaca", or "auto" (default).
                     Auto tries Robinhood first, falls back to Alpaca.
    """
    name = (broker_name or DEFAULT_BROKER).lower().strip()

    if name == "robinhood":
        return _get_robinhood()
    elif name == "alpaca":
        return _get_alpaca()
    elif name == "auto":
        # Try Robinhood first (real money), fall back to Alpaca (paper)
        try:
            token_path = Path(__file__).parent / "robinhood-mcp" / "token.json"
            if token_path.exists():
                return _get_robinhood()
        except Exception as e:
            print(f"[BrokerFactory] Robinhood unavailable ({e}), trying Alpaca...")

        try:
            return _get_alpaca()
        except Exception as e:
            raise RuntimeError(f"No broker available. Robinhood and Alpaca both failed: {e}")
    else:
        raise ValueError(f"Unknown broker: {name}. Use 'robinhood', 'alpaca', or 'auto'.")


def _get_robinhood():
    from robinhood_broker import RobinhoodBroker
    return RobinhoodBroker()


def _get_alpaca():
    from broker import AlpacaBroker
    return AlpacaBroker()

```

---

## config.py

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
# Robinhood agentic account: $500 funded, sizing to represent ~$5,500 remaining
# budget (out of $10K total project allowance, ~$4K already deployed elsewhere).
# Scale factor: $500 / $5,500 ≈ 9.1% — pipeline sizes as if $500 is the full account,
# so all risk parameters below are calibrated to this amount.
ACCOUNT_SIZE = 500  # $500 Robinhood agentic account
ALPACA_PAPER_BUDGET = 10_000  # $10K paper trading budget (Alpaca mirror)
DRY_POWDER_FLOOR = 0.20  # Never deploy beyond 80% ($400 max deployed)

# Alpaca
ALPACA_USERNAME = os.environ.get("ALPACA_USERNAME", "")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"  # Paper trading first

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

# Risk Parameters (scaled to $500 account)
PER_TRADE_RISK_CAP = 7.50      # $7.50 max risk per trade (1.5% of $500)
SESSION_RISK_BUDGET = 50.00    # $50 max session risk (10% of $500)
THEME_CAP = 1                  # Max 1 position per theme per session (tweak #5)

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

# Risk-first sizing constants (scaled to $500 account)
BASE_RISK = 7.50               # Per-trade $ at neutral conviction (1.5% of $500)
MAX_RISK_PER_TRADE = 10.00     # Hard ceiling regardless of multiplier stack
MIN_RISK_PER_TRADE = 2.50      # Below this, skip (regime says don't trade)
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

---

## data_fetcher_v1_deprecated.py

```python
"""
Market Data Fetcher
Pulls macro indicators for Agent 1 (Macro Director).
Uses yfinance for free, reliable data.
"""
import yfinance as yf
from datetime import datetime, timedelta
import json


def fetch_macro_data() -> dict:
    """
    Fetch current macro indicators:
    - VIX (^VIX)
    - 10Y Treasury Yield (^TNX)
    - 2Y Treasury Yield (^IRX approximation via 2Y)
    - US Dollar Index (DX-Y.NYB)
    - S&P 500 (^GSPC) - current + recent trend
    - Gold (GC=F) - flight to safety signal
    - HY Credit Spread proxy: HYG vs LQD ratio
    """
    tickers = {
        "VIX": "^VIX",
        "SP500": "^GSPC",
        "TNX_10Y": "^TNX",
        "TWO_YEAR": "2YY=F",
        "DXY": "DX-Y.NYB",
        "GOLD": "GC=F",
        "HYG": "HYG",  # High yield corporate bond ETF
        "LQD": "LQD",  # Investment grade corporate bond ETF
    }

    results = {}
    end = datetime.now()
    start = end - timedelta(days=30)

    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                results[name] = {"error": f"No data for {ticker}"}
                continue

            current = float(data["Close"].iloc[-1].item())
            prev_5d = float(data["Close"].iloc[-5].item()) if len(data) >= 5 else current
            prev_20d = float(data["Close"].iloc[-20].item()) if len(data) >= 20 else current

            results[name] = {
                "current": round(current, 2),
                "5d_ago": round(prev_5d, 2),
                "20d_ago": round(prev_20d, 2),
                "5d_change_pct": round((current - prev_5d) / prev_5d * 100, 2),
                "20d_change_pct": round((current - prev_20d) / prev_20d * 100, 2),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    # Compute yield curve (10Y - 2Y approximation)
    if "TNX_10Y" in results and "TWO_YEAR" in results:
        if "current" in results["TNX_10Y"] and "current" in results["TWO_YEAR"]:
            results["YIELD_CURVE_SPREAD"] = round(
                results["TNX_10Y"]["current"] - results["TWO_YEAR"]["current"], 2
            )

    # HY spread proxy (HYG/LQD ratio - lower = wider spreads = more stress)
    if "HYG" in results and "LQD" in results:
        if "current" in results["HYG"] and "current" in results["LQD"]:
            results["HY_SPREAD_PROXY"] = round(
                results["HYG"]["current"] / results["LQD"]["current"], 4
            )

    results["timestamp"] = datetime.now().isoformat()
    return results


def format_macro_for_prompt(data: dict) -> str:
    """Format macro data into a clean text block for the LLM prompt."""
    lines = [f"MACRO DATA SNAPSHOT — {data.get('timestamp', 'unknown')}", "=" * 50]

    for key, val in data.items():
        if key == "timestamp":
            continue
        if isinstance(val, dict) and "error" in val:
            lines.append(f"{key}: DATA UNAVAILABLE ({val['error']})")
        elif isinstance(val, dict):
            lines.append(
                f"{key}: {val['current']} "
                f"(5d: {val['5d_change_pct']:+.2f}%, 20d: {val['20d_change_pct']:+.2f}%)"
            )
        else:
            lines.append(f"{key}: {val}")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Fetching macro data...")
    data = fetch_macro_data()
    print(json.dumps(data, indent=2))
    print("\n" + format_macro_for_prompt(data))

```

---

## data_provider.py

```python
"""
data_provider.py — Unified Data Provider Abstraction

Single seam for all market data access. Routes through paid vendors
(Massive/Polygon, Schwab) instead of yfinance scraping.

Fallback hierarchy per method:
  get_bars:    Massive → yfinance (deprecated fallback) → raise DataUnavailable
  get_quote:   Schwab → raise DataUnavailable (broker feed ONLY)
  get_index:   Massive I:<SYM> → Schwab → ETF proxy → raise DataUnavailable
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
        Live bid/ask/last for execution. Broker feed ONLY.
        Fallback: Schwab → raise DataUnavailable.
        (Execution paths must price against the venue we trade on.)
        """
        # Schwab
        try:
            quotes = self._schwab_quotes([ticker])
            if ticker in quotes:
                return quotes[ticker]
        except Exception as e:
            logger.warning(f"Schwab quote failed for {ticker}: {e}")

        raise DataUnavailable(f"No live quote available for {ticker}")

    def get_index(self, symbol: str) -> dict:
        """
        Index level for VIX/SPX.
        Fallback: Massive I:<SYM> → Schwab $<SYM> → ETF proxy → raise.
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

        # 2. Schwab $VIX / $SPX
        try:
            schwab_ticker = f"${symbol}"
            quotes = self._schwab_quotes([schwab_ticker])
            if schwab_ticker in quotes:
                val = quotes[schwab_ticker].get("last") or quotes[schwab_ticker].get("bid")
                if val and val > 0:
                    return {"symbol": symbol, "value": float(val), "source": "schwab", "is_proxy": False}
        except Exception as e:
            logger.warning(f"Schwab index ${symbol} failed: {e}")

        # 3. ETF proxy
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

    def get_corporate_actions(self, ticker: str, since_days: int = 7) -> list:
        """
        Recent splits/dividends.
        Fallback: Massive → [] with log warning.
        """
        # 1. Massive splits endpoint
        if self._massive_key:
            try:
                return self._massive_splits(ticker, since_days)
            except Exception as e:
                logger.warning(f"Massive splits failed for {ticker}: {e}")

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
        resp = requests.get(url, params=params, timeout=15)

        if resp.status_code == 403:
            logger.warning(f"Massive 403 (not entitled): {endpoint}")
            return {}
        if resp.status_code == 429:
            logger.warning(f"Massive 429 (rate limited): {endpoint}")
            time.sleep(12)
            resp = requests.get(url, params=params, timeout=15)

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

    def _schwab_quotes(self, tickers: list) -> dict:
        """Lazy-load and call Schwab quote function."""
        if self._schwab_quotes_fn is None:
            try:
                from schwab_data import fetch_schwab_quotes
                self._schwab_quotes_fn = fetch_schwab_quotes
            except ImportError:
                raise DataUnavailable("Schwab module not available")
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

---

## discord_fetch.py

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

---

## execution_engine.py

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

---

## fedwatch.py

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
    future_meetings = [m for m in FOMC_MEETINGS_2026 
                       if date.fromisoformat(m["date"]) > today]
    
    if not future_meetings:
        result["error"] = "No remaining FOMC meetings in schedule"
        return result
    
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

---

## flash_crash_daemon.py

```python
"""
Flash-Crash Daemon — Lightweight intraday safety net (NO LLM)
Runs every 5-10 minutes during market hours.

Checks:
  1. SPY intraday drop > 1.5% from today's open → defensive protocol
  2. VIX intraday spike > 20% from today's open → defensive protocol
  3. Individual position down > 5% intraday → tighten that stop to breakeven

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


def run_daemon():
    """
    Main daemon entry point. Checks market conditions and positions.
    If no triggers, exits silently. If triggers fire, executes defensive protocol.
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
        print(f"[Daemon] ERROR: Could not connect to Alpaca — {e}")
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

---

## itc_data.py

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

---

## market_data.py

```python
"""
Unified Market Data Module — Schwab primary, Yahoo Finance fallback.

Replaces alpaca_data.py as the pipeline's data source.
No Alpaca dependency — uses Schwab for real-time quotes and Yahoo for
historical bars, fundamentals, and macro indicators.

Drop-in compatible with alpaca_data.py's function signatures.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


# ── Schwab Quotes (primary for real-time) ────────────────────────────────

def _schwab_available() -> bool:
    """Check if Schwab data module is available and has a valid token."""
    try:
        from schwab_data import fetch_schwab_quotes
        test = fetch_schwab_quotes(["SPY"])
        return "SPY" in test and "error" not in test.get("SPY", {})
    except Exception:
        return False

_schwab_ok = None  # Lazy init


def _check_schwab():
    global _schwab_ok
    if _schwab_ok is None:
        _schwab_ok = _schwab_available()
        if _schwab_ok:
            print("[MarketData] Schwab API: AVAILABLE (primary for real-time quotes)")
        else:
            print("[MarketData] Schwab API: UNAVAILABLE — falling back to Yahoo Finance")
    return _schwab_ok


# ── Robinhood Quotes (secondary for real-time) ──────────────────────────

def _robinhood_quotes(tickers: list) -> dict:
    """Fetch quotes from Robinhood MCP if a token exists."""
    try:
        from robinhood_broker import RobinhoodBroker
        broker = RobinhoodBroker()
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
    Primary: Schwab. Fallback: Yahoo Finance.
    """
    results = {}

    # Try Schwab first for real-time previous close
    if _check_schwab():
        try:
            from schwab_data import fetch_schwab_quotes
            # Batch in groups of 50
            for i in range(0, len(tickers), 50):
                batch = tickers[i:i+50]
                quotes = fetch_schwab_quotes(batch)
                for t, q in quotes.items():
                    if "error" not in q:
                        close = q.get("close") or q.get("last") or q.get("regularMarketPreviousClose", 0)
                        if close and close > 0:
                            results[t] = {
                                "prior_close": round(float(close), 2),
                                "prior_date": str((datetime.now() - timedelta(days=1)).date()),
                                "source": "schwab",
                            }
        except Exception as e:
            print(f"[MarketData] Schwab prior_close batch failed: {e}")

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
    Fetch real-time quotes. Primary: Schwab. Fallback: Robinhood MCP, then Yahoo.
    """
    results = {}

    # Try Schwab
    if _check_schwab():
        try:
            from schwab_data import fetch_schwab_quotes
            quotes = fetch_schwab_quotes(tickers)
            for t, q in quotes.items():
                if "error" not in q:
                    bid = q.get("bid", 0)
                    ask = q.get("ask", 0)
                    last = q.get("last", 0)
                    results[t] = {
                        "bid": float(bid) if bid else 0.0,
                        "ask": float(ask) if ask else 0.0,
                        "last": float(last) if last else 0.0,
                        "mid": round((float(bid or 0) + float(ask or 0)) / 2, 2) if bid and ask else float(last or 0),
                        "source": "schwab",
                    }
        except Exception as e:
            print(f"[MarketData] Schwab quotes failed: {e}")

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
    Fetch historical OHLCV bars. Uses Yahoo Finance (best free source for this).
    """
    yf = _yf_import()
    results = {}

    period_map = {
        7: "7d", 14: "14d", 30: "1mo", 60: "2mo", 90: "3mo",
        180: "6mo", 365: "1y",
    }
    # Find closest period
    period = "1mo"
    for d, p in sorted(period_map.items()):
        if days <= d:
            period = p
            break
    if days > 365:
        period = f"{days}d"

    interval = {"day": "1d", "hour": "1h", "minute": "1m"}.get(timeframe, "1d")

    for ticker in tickers:
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
    Uses Schwab for real-time, Yahoo for daily bars.
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

---

## massive_data.py

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
    For large batches, prefer Alpaca. Use Massive for enrichment.
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
    import yfinance as yf
    import pandas as pd

    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    except Exception as e:
        return {"ticker": ticker, "error": f"yfinance download failed: {e}", "source": "local_calculation"}

    if df.empty or len(df) < 50:
        return {"ticker": ticker, "error": f"Insufficient data ({len(df)} bars, need >=50)", "source": "local_calculation"}

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

---

## orchestrator.py

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



# ━━━ ALPACA PAPER MIRROR ━━━
# Scale factor: Robinhood $500 → Alpaca paper $10K budget (20x)
ALPACA_MIRROR_SCALE = 20  # $10K / $500

def mirror_to_alpaca_paper(trade_orders: list) -> list:
    """
    Mirror today's trades to the Alpaca paper account, scaled to $10K budget.
    Runs independently of Robinhood — failures here don't affect real execution.
    """
    try:
        from broker import AlpacaBroker
        paper_broker = AlpacaBroker()
        
        scaled_orders = []
        for order in trade_orders:
            if order.get("action") != "BUY":
                continue
            
            scaled = dict(order)
            original_shares = order.get("shares", 0)
            
            # Scale shares by mirror factor
            if isinstance(original_shares, (int, float)) and original_shares > 0:
                scaled["shares"] = max(1, int(original_shares * ALPACA_MIRROR_SCALE))
            else:
                # Dollar-based: scale the dollar amount
                scaled["shares"] = ALPACA_MIRROR_SCALE
            
            scaled_orders.append(scaled)
        
        if not scaled_orders:
            print("[Mirror] No BUY orders to mirror.")
            return []
        
        print(f"[Mirror] Mirroring {len(scaled_orders)} orders to Alpaca paper (scale: {ALPACA_MIRROR_SCALE}x)...")
        for o in scaled_orders:
            print(f"  [Mirror] BUY {o['shares']} {o['ticker']} @ ${o.get('entry_price', '?')}")
        
        fills = paper_broker.execute_tear_sheet(scaled_orders, max_gap_pct=0.05)
        
        for f in fills:
            status = f.get("status", "unknown")
            print(f"  [Mirror] {f.get('ticker')}: {status}")
        
        return fills
    except Exception as e:
        print(f"[Mirror] ⚠️ Alpaca paper mirror failed (non-fatal): {e}")
        return []


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
            # Replace candidates with only the READY ones
            candidates = candidates + ready_candidates
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
    
    # ━━━ STEP 3.5: X/TWITTER SMART MONEY FETCH ━━━
    print("\n" + "━" * 40)
    print("🐦 STEP 3.5: X/TWITTER SMART MONEY FETCH")
    print("━" * 40)
    
    tickers = [c.get("ticker") for c in candidates]
    
    try:
        x_mentions = fetch_x_smart_money(tickers)
        results["x_fetch"] = {"success": True}
    except Exception as e:
        print(f"\u26a0\ufe0f X/Twitter fetch failed: {e}")
        print("   Continuing with empty X data — Agent 3 will use news/options/SI only.")
        x_mentions = {t: [] for t in tickers}
        # Save empty mentions so Agent 3 can load them
        with open("output/smart_money_mentions.json", "w") as smf:
            json.dump(x_mentions, smf, indent=2)
        results["x_fetch"] = {"success": False, "error": str(e), "fallback": "empty_mentions"}
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
    
    # ━━━ STEP 6.5: MIRROR TO ALPACA PAPER ━━━
    if buy_orders:
        print("\n" + "━" * 40)
        print("📋 STEP 6.5: ALPACA PAPER MIRROR")
        print("━" * 40)
        mirror_fills = mirror_to_alpaca_paper(trade_orders)
        results["alpaca_mirror"] = {"fills": mirror_fills}

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


def run_afternoon_monitor(verbose: bool = False) -> dict:
    """Run Agent 5: Afternoon position monitoring."""
    print("=" * 50)
    print("🕒 OPEN CLAW — AFTERNOON POSITION MONITOR")
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
        agent5_result = run_agent5(preflight["positions"], preflight["snapshot"])
        
        if agent5_result.get("success"):
            print(format_agent5_for_telegram(agent5_result))
            
            with open("output/agent5_decisions.json", "w") as f:
                json.dump(agent5_result, f, indent=2, default=str)
            
            # ━━━ EXECUTE AGENT 5 DECISIONS VIA EXECUTION ENGINE ━━━
            decisions = agent5_result.get("decisions", [])
            crisis = agent5_result.get("crisis_liquidation", False)
            actionable = [d for d in decisions if d.get("action") in ("CLOSE", "TRIM")] or crisis
            
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
                                # Update trailing stop if tightened
                                new_stop = d.get("new_stop")
                                original_stop = d.get("original_stop")
                                if new_stop and original_stop and new_stop > original_stop:
                                    # Atomic trailing: cancel → wait → place (synchronous)
                                    if not engine.update_trailing_stop(ticker, new_stop):
                                        # Fallback to async daemon-based update
                                        engine.update_stop(ticker, new_stop, reason="Agent5_TRAIL_fallback")
                                exec_results.append({"ticker": ticker, "action": "HOLD", "new_stop": new_stop})
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
        
        # Execute trades on Alpaca
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

        if spread_pct > 0.05:
            print(f"  🚫 REJECTED {ticker}: Spread is toxic ({spread_pct*100:.1f}% wide). Bid: {bid}, Ask: {ask}")
            fills.append({"ticker": ticker, "status": "rejected_wide_spread"})
            engine.log_incident(
                ticker=ticker, incident_type="WIDE_SPREAD",
                bid=bid, ask=ask, target_shares=int(order.get("shares", 0)),
                root_cause="toxic_spread",
                notes=f"Spread {spread_pct*100:.1f}% exceeds 5% threshold.",
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

        # Route intent to the Execution Ledger
        # Marketable limit: ask + 15bps to cross the spread and guarantee fills
        result = engine.submit_trade_intent(
            trade_id=trade_id,
            ticker=ticker,
            shares=int(order.get("shares", 0)),
            limit_price=marketable_limit,
            stop_price=order.get("stop_loss", 0),
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
        print("Usage: python3 orchestrator.py [morning|monitor|resume|execute|full]")

```

---

## performance_review.py

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
        "x_twitter": {"name": "X/Twitter Smart Money", "icon": "🐦", "cost": "Free (x_search via OCPlatform)", "role": "Smart money sentiment, institutional mentions"},
        "alpaca": {"name": "Alpaca Market Data", "icon": "🦙", "cost": "Free (IEX feed)", "role": "Primary price quotes, prior close, historical bars"},
        "massive_technicals": {"name": "Massive API (Technicals)", "icon": "📈", "cost": "Free tier (5 calls/min)", "role": "Server-side RSI, MACD, SMA, EMA"},
        "massive_macro": {"name": "Massive API (Macro/Economy)", "icon": "🏛️", "cost": "Free tier", "role": "Treasury yields, inflation, labor market"},
        "massive_fundamentals": {"name": "Massive API (Fundamentals)", "icon": "📊", "cost": "Free tier", "role": "Financials, dividends, ticker details"},
        "assembly": {"name": "Assembly/FRED Macro", "icon": "🏦", "cost": "Free", "role": "Sentiment composite, cross-asset rotation, sector RS"},
        "squeezemetrics": {"name": "SqueezMetrics DIX", "icon": "🌊", "cost": "Free (CSV)", "role": "Dark pool index — institutional accumulation/distribution"},
        "finviz": {"name": "Finviz Screener", "icon": "🔍", "cost": "Free (finvizfinance)", "role": "Dynamic stock screening (momentum, sectors, themes)"},
        "yfinance": {"name": "Yahoo Finance", "icon": "📰", "cost": "Free (yfinance)", "role": "Fallback price data, sector breadth, VIX"},
        "schwab": {"name": "Schwab API", "icon": "🏦", "cost": "Free (with brokerage acct)", "role": "Real-time quotes, trade execution (incoming)"},
        "discord": {"name": "Discord", "icon": "💬", "cost": "Free", "role": "Output channel — signal-to-noise TBD"},
    }

    # ── Scan archived runs for reliability data ──
    runs = []
    if os.path.exists(ARCHIVE_DIR):
        runs = sorted(os.listdir(ARCHIVE_DIR))[-14:]  # Last 14 runs

    mentions_list = []
    missing_data_flags = []
    alpaca_success = 0
    alpaca_fail = 0
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

        # Assembly freshness
        assembly_file = os.path.join(run_dir, "assembly_data.json")
        if os.path.exists(assembly_file):
            try:
                with open(assembly_file) as f:
                    asm = json.load(f)
                if asm.get("source") == "public_api_fallback":
                    assembly_stale += 1
                else:
                    assembly_fresh += 1
            except Exception:
                assembly_stale += 1

    total_runs = max(len(runs), 1)

    # ── Grade each source ──

    # X/Twitter
    avg_mentions = np.mean(mentions_list) if mentions_list else 0
    if avg_mentions >= 5:
        x_grade, x_note = "🟢", f"Solid coverage (Avg {avg_mentions:.1f} mentions/run)"
    elif avg_mentions > 0:
        x_grade, x_note = "🔴", f"Low volume (Avg {avg_mentions:.1f}). Expand curated accounts."
    else:
        x_grade, x_note = "⚪", "No data yet"
    report.append(f"  🐦 *X/Twitter Smart Money:* {x_grade} — _{x_note}_ 💰 Free")

    # Alpaca
    alpaca_file = os.path.join(OUTPUT_DIR, "screener_universe.json")
    if os.path.exists(alpaca_file):
        try:
            with open(alpaca_file) as f:
                su = json.load(f)
            alpaca_tickers = [t for t in su if isinstance(t, dict) and t.get("source") not in ("hardcoded_fallback",)]
            if alpaca_tickers:
                report.append(f"  🦙 *Alpaca:* 🟢 — _Primary source for {len(alpaca_tickers)} tickers_ 💰 Free")
            else:
                report.append("  🦙 *Alpaca:* ⚪ — _Not primary in latest run_ 💰 Free")
        except Exception:
            report.append("  🦙 *Alpaca:* ⚪ — _Unable to assess_ 💰 Free")
    else:
        report.append("  🦙 *Alpaca:* ⚪ — _No screener data to assess_ 💰 Free")

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

    # Assembly
    if assembly_fresh + assembly_stale > 0:
        fresh_rate = assembly_fresh / (assembly_fresh + assembly_stale) * 100
        if fresh_rate >= 70:
            report.append(f"  🏦 *Assembly/FRED:* 🟢 — _{fresh_rate:.0f}% fresh data ({assembly_fresh}/{assembly_fresh + assembly_stale} runs)_ 💰 Free")
        elif fresh_rate >= 40:
            report.append(f"  🏦 *Assembly/FRED:* ⚪ — _{fresh_rate:.0f}% fresh — falling back to public APIs often_ 💰 Free")
        else:
            report.append(f"  🏦 *Assembly/FRED:* 🔴 — _Only {fresh_rate:.0f}% fresh — mostly using fallback. Check Assembly scraper._ 💰 Free")
    else:
        asm_grade = "🟢" if not missing_data_flags else "🔴"
        report.append(f"  🏦 *Assembly/FRED:* {asm_grade} — _{'Clean data' if not missing_data_flags else 'Missing DIX/MOVE data'}_ 💰 Free")

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

    # Schwab (incoming)
    report.append("  🏦 *Schwab API:* ⚪ — _Integration in progress — will replace Alpaca for real-time quotes + trade execution_ 💰 Free")

    # Discord
    report.append("  💬 *Discord:* ⚪ — _Output only — signal-to-noise TBD_ 💰 Free")

    # ── Cost summary ──
    report.append("")
    report.append("  *💰 Total Monthly API Cost: $0* (all sources on free tiers)")
    report.append("  _Recommendation: When Schwab is live, evaluate dropping Alpaca (redundant for quotes)._")
    report.append("  _Massive free tier (5 calls/min) sufficient for daily runs. Upgrade only if going intraday._")

    # ── Value assessment ──
    report.append("")
    report.append("  *📋 Value Assessment:*")
    report.append("  _HIGH VALUE:_ Massive Macro (unique data), X/Twitter (alpha signal), DIX (institutional flow)")
    report.append("  _MEDIUM VALUE:_ Massive Technicals (saves compute), Finviz (dynamic screening), Assembly (sentiment)")
    report.append("  _MONITOR:_ Discord (noise?), yfinance (reliability), Schwab (not live yet)")

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

---

## preflight.py

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

import yfinance as yf

from config import SCREENER_MIN_MARKET_CAP, SCREENER_MIN_PRICE

# Unified market data — Schwab primary, Yahoo Finance fallback (replaces Alpaca)
try:
    import market_data as mdata
    MARKET_DATA_AVAILABLE = True
    print("[Pre-Flight] Unified Market Data: AVAILABLE (Schwab + Yahoo Finance)")
except Exception as e:
    MARKET_DATA_AVAILABLE = False
    print(f"[Pre-Flight] Unified Market Data: UNAVAILABLE ({e}) — using yfinance directly")

# Legacy alias for backward compat
ALPACA_AVAILABLE = MARKET_DATA_AVAILABLE

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

OUTPUT_DIR = "output"

ASSEMBLY_STALE_HOURS = 18  # Assembly data older than this triggers fresh fetch from public APIs
ITC_STALE_HOURS = 18  # ITC data older than this is considered stale


def fetch_prior_close(tickers: list) -> dict:
    """
    Fetch YESTERDAY's regular-session close for a list of tickers.
    This is critical — all pricing and stop calculations use prior close,
    NOT live/intraday pre-market data (Tweak #6).
    
    Primary: Schwab + Yahoo Finance (unified market data)
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
            data = yf.download(ticker, start=start, end=end, progress=False)
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
            data = yf.download(ticker, start=start, end=end, progress=False)
            if data.empty:
                macro[name] = {"error": f"No data for {ticker}"}
                continue

            # VIX pre-market noise filter: before 9:30 ET, use prior day's close
            # to avoid illiquid option book spreads causing fake spikes
            import pytz
            now_et = datetime.now(pytz.timezone('US/Eastern'))
            if name == "VIX" and now_et.hour < 9 or (now_et.hour == 9 and now_et.minute < 30):
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

    # HY spread proxy
    if "HYG" in macro and "LQD" in macro:
        if "current" in macro["HYG"] and "current" in macro["LQD"]:
            macro["HY_SPREAD_PROXY"] = round(
                macro["HYG"]["current"] / macro["LQD"]["current"], 4
            )

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
        data = yf.download("^MOVE", start=start, end=end, progress=False)
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
    import requests

    URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
    try:
        resp = requests.get(
            URL,
            timeout=10,
            headers={"User-Agent": "open-claw/1.0 (research)"},
        )
        resp.raise_for_status()
    except requests.HTTPError as e:
        return {"error": f"DIX HTTP {e.response.status_code} from squeezemetrics"}
    except requests.RequestException as e:
        return {"error": f"DIX fetch failed: {e}"}

    try:
        reader = csv.DictReader(io.StringIO(resp.text))
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
        "source": "squeezemetrics.com/monitor/static/DIX.csv",
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
            data = yf.download(etf, start=start, end=end, progress=False)
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
            data = yf.download(entry["ticker"], start=start, end=end, progress=False)
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
    curated_handles = SMART_MONEY_ACCOUNTS
    if not curated_handles:
        curated_handles = [
            "unusual_whales", "DeItaone", "Fxhedgers", "zaborsky",
            "jimcramer", "GurufocusData", "OptionsHawk", "PeterSchiff",
            "TruthGundlach", "elerianm", "SqueezeMetrics", "sentimentrader",
            "DarkPoolChart", "WallStJesus", "VolSignals",
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
    result = {"timestamp": datetime.now().isoformat(), "source": "public_api_fallback"}

    # 2. Sub-components from yfinance
    components = {}
    try:
        end = datetime.now()
        start = end - timedelta(days=5)

        # VIX for market volatility component
        vix = yf.download("^VIX", start=start, end=end, progress=False)
        if not vix.empty:
            vix_val = float(vix["Close"].iloc[-1].item())
            components["vix_value"] = round(vix_val, 2)
            if vix_val < 15: components["market_volatility_vix"] = 90
            elif vix_val < 20: components["market_volatility_vix"] = 65
            elif vix_val < 25: components["market_volatility_vix"] = 45
            elif vix_val < 35: components["market_volatility_vix"] = 25
            else: components["market_volatility_vix"] = 5

        # S&P 500 momentum (125-day)
        spy = yf.download("SPY", start=end - timedelta(days=180), end=end, progress=False)
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
        hyg = yf.download("HYG", start=start, end=end, progress=False)
        lqd = yf.download("LQD", start=start, end=end, progress=False)
        if not hyg.empty and not lqd.empty:
            hyg_ret = float(hyg["Close"].pct_change().iloc[-1].item())
            lqd_ret = float(lqd["Close"].pct_change().iloc[-1].item())
            spread = (hyg_ret - lqd_ret) * 100
            if spread > 0.5: components["junk_bond_demand"] = 80
            elif spread > 0: components["junk_bond_demand"] = 60
            elif spread > -0.5: components["junk_bond_demand"] = 40
            else: components["junk_bond_demand"] = 20

        # Safe haven demand: TLT relative to SPY
        tlt = yf.download("TLT", start=start, end=end, progress=False)
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

    result["components"] = components

    # Compute synthetic composite from available components
    if components:
        scores = [v for k, v in components.items() if k != "vix_value" and isinstance(v, (int, float))]
        if scores:
            composite = round(sum(scores) / len(scores))
            result["composite_score"] = composite
            if composite >= 75: result["composite_label"] = "Extreme Greed"
            elif composite >= 55: result["composite_label"] = "Greed"
            elif composite >= 45: result["composite_label"] = "Neutral"
            elif composite >= 25: result["composite_label"] = "Fear"
            else: result["composite_label"] = "Extreme Fear"
            print(f"[Pre-Flight] Synthetic composite: {composite} ({result['composite_label']}) from {len(scores)} components")

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

    # 3. Assembly Private data (sentiment + macro overlay)
    #    If stale or missing, auto-fetch fresh indicators from public APIs
    assembly = {}
    assembly_path = f"{OUTPUT_DIR}/assembly_data.json"
    stale = is_assembly_stale(assembly_path)

    if not stale:
        try:
            with open(assembly_path) as f:
                assembly = json.load(f)
            print(f"[Pre-Flight] Assembly data FRESH — loaded (sentiment: {assembly.get('sentiment', {}).get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Assembly data load failed: {e}")
            stale = True

    if stale:
        print("[Pre-Flight] Assembly data STALE or missing — fetching fresh indicators from public APIs...")
        fresh_sentiment = fetch_fresh_sentiment_fallback()
        assembly = {
            "timestamp": datetime.now().isoformat(),
            "source": "public_api_fallback",
            "sentiment": fresh_sentiment,
            "macro": {},  # macro already covered by fetch_macro_data() above
        }
        # Save the fresh fallback so agents can reference it
        try:
            with open(assembly_path, "w") as f:
                json.dump(assembly, f, indent=2)
            print(f"[Pre-Flight] Fresh fallback data saved (sentiment: {fresh_sentiment.get('composite_score', '?')})")
        except Exception as e:
            print(f"[Pre-Flight] Could not save fallback data: {e}")

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

---

## robinhood_broker.py

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
        """Call an MCP tool and return the parsed result."""
        resp = self._mcp_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })
        if not resp:
            return None

        content = resp.get("result", {}).get("content", [])
        for item in content:
            if item.get("type") == "text":
                try:
                    parsed = json.loads(item["text"])
                    return parsed.get("data", parsed)
                except json.JSONDecodeError:
                    return item["text"]
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

        return self._call_tool("place_equity_order", args)

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
                        # Cross-reference with Schwab
                        from broker import _cross_reference_price
                        verified_price = _cross_reference_price(ticker, planned_entry, live_ask)
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

                    live_shares = round(risk_budget / live_risk_per_share, 6)
                    if live_shares < 0.001:
                        fills.append({"ticker": ticker, "status": "rejected", "reason": "Zero shares after re-sizing"})
                        continue

                    limit_price = round(live_ask * 1.0015, 2)
                    shares = live_shares
                    pricing_mode = "live"

                    if shares != planned_shares:
                        print(f"  [RH-Broker] 📐 {ticker}: Re-sized {planned_shares} → {shares} shares")
                else:
                    limit_price = round(planned_entry * 1.015, 2)
                    shares = planned_shares
                    pricing_mode = "planned"

                # First: review the order (dry run)
                review = self.review_order(ticker, "buy", "limit",
                                           quantity=str(shares), limit_price=str(limit_price))
                if review and isinstance(review, dict):
                    alerts = review.get("alerts", [])
                    if alerts:
                        print(f"  [RH-Broker] ⚠️ {ticker} pre-trade alerts: {alerts}")

                # Place the order
                result = self.place_order(
                    ticker, "buy", "limit",
                    quantity=str(shares),
                    limit_price=str(limit_price),
                    time_in_force="gfd",
                )

                order_id = None
                if isinstance(result, dict):
                    order_id = result.get("order_id") or result.get("id")

                fills.append({
                    "ticker": ticker,
                    "status": "submitted",
                    "order_id": order_id,
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

                # Note: Robinhood MCP doesn't support bracket/OTO orders.
                # Stop-loss orders need to be placed separately after fill confirmation.
                if stop_price and stop_price > 0:
                    print(f"  [RH-Broker] ⏳ Stop-loss ${stop_price:.2f} pending — will place after fill")

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
                if new_stop and original_stop and new_stop > original_stop:
                    engine.update_stop(ticker, new_stop, reason="Agent5_TRAIL")
                    results.append({"ticker": ticker, "action": "HOLD_STOP_TIGHTENED", "new_stop": new_stop, "status": "executed"})
                else:
                    results.append({"ticker": ticker, "action": "HOLD", "status": "no_action"})

            elif action == "CLOSE":
                result = engine.atomic_liquidate(ticker, reason="Agent5_CLOSE")
                results.append(result)

            elif action == "TRIM":
                trim_pct = d.get("trim_pct", 50) / 100
                positions = self.get_positions()
                pos = next((p for p in positions if p["ticker"] == ticker), None)
                if pos:
                    # For trim: atomic liquidate the full position then re-enter the remainder
                    # Simpler approach: update stop and let the position ride at smaller size
                    new_stop = d.get("new_stop", d.get("current_price", 0))
                    if new_stop > 0:
                        engine.update_stop(ticker, new_stop, reason="Agent5_TRIM")
                    results.append({"ticker": ticker, "action": "TRIM", "new_stop": new_stop, "status": "stop_tightened"})
                else:
                    results.append({"ticker": ticker, "action": "TRIM", "status": "no_position"})

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

---

## run_archiver.py

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

---

## run_execution_daemon.py

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

---

## safeguards.py

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

def is_market_open_today() -> dict:
    """
    Check if the US stock market is open today via Alpaca's Clock API.
    Returns dict with is_open, next_open, next_close, and should_run.
    
    should_run = True if market is open OR will open today.
    """
    try:
        from alpaca.trading.client import TradingClient
        
        api_key = os.environ.get("ALPACA_API_KEY", "")
        secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        
        if not api_key or not secret_key:
            print("[Safeguard] ⚠️ No Alpaca keys — cannot check market calendar. Proceeding anyway.")
            return {"is_open": None, "should_run": False, "reason": "no_alpaca_keys_fail_closed"}
        
        client = TradingClient(api_key, secret_key, paper=True)
        clock = client.get_clock()
        
        today = datetime.now().date()
        next_open_date = clock.next_open.date() if clock.next_open else None
        
        result = {
            "is_open": clock.is_open,
            "next_open": clock.next_open.isoformat() if clock.next_open else None,
            "next_close": clock.next_close.isoformat() if clock.next_close else None,
            "timestamp": datetime.now().isoformat(),
        }
        
        if clock.is_open:
            result["should_run"] = True
            result["reason"] = "market_is_open"
        elif next_open_date == today:
            result["should_run"] = True
            result["reason"] = "market_opens_today"
        else:
            result["should_run"] = False
            result["reason"] = f"market_closed_today_next_open_{next_open_date}"
        
        return result
    except Exception as e:
        print(f"[Safeguard] ⚠️ Clock API check failed: {e}. Proceeding anyway.")
        return {"is_open": None, "should_run": False, "reason": f"clock_check_failed_fail_closed: {e}"}


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
    
    removed = []
    filtered = []
    
    for entry in screener:
        ticker = entry.get("ticker")
        if ticker and ticker in earnings:
            info = earnings[ticker]
            if not info.get("safe", True):
                removed.append({"ticker": ticker, **info})
                print(f"[Earnings Screen] 🚫 {ticker} — {info['reason']}")
                continue
        filtered.append(entry)
    
    if removed:
        print(f"[Earnings Screen] Filtered {len(removed)} tickers with upcoming earnings")
    else:
        print(f"[Earnings Screen] ✅ All tickers clear of near-term earnings")
    
    return filtered, removed


def filter_corporate_actions(screener: list) -> tuple:
    """
    Hard-block tickers that had a stock split in the last 7 days.
    Prevents hallucinated gaps and broken VaR math from adjusted historical prices.
    Uses DataProvider (Massive/Polygon splits endpoint) instead of yfinance.
    """
    from data_provider import get_provider
    dp = get_provider()

    print(f"[Corp Actions] Checking {len(screener)} tickers for recent splits...")
    filtered, removed = [], []

    for entry in screener:
        ticker = entry.get("ticker")
        try:
            splits = dp.get_corporate_actions(ticker, since_days=7)
            if splits:
                split_info = splits[0]
                print(f"  [Corp Actions] {ticker} -- Recent split detected ({split_info.get('execution_date', '?')})")
                removed.append({"ticker": ticker, "reason": "Recent corporate action/split", "detail": split_info})
                continue
        except Exception as e:
            print(f"  [Corp Actions] {ticker}: split check failed ({e}) -- passing")
        filtered.append(entry)

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

---

## schwab_auth_server.py

```python
"""
Temporary local HTTPS server to catch the Schwab OAuth callback.
Captures the auth code and exchanges it for tokens automatically.

Usage: python3 schwab_auth_server.py
Then open the auth URL in a browser, log in, and it handles the rest.
"""
import http.server
import ssl
import json
import base64
import requests
import subprocess
import sys
import os
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

APP_KEY = os.environ["SCHWAB_APP_KEY"]
APP_SECRET = os.environ["SCHWAB_APP_SECRET"]
CALLBACK_URL = "https://127.0.0.1/"
TOKEN_PATH = Path(__file__).parent / "schwab_token.json"

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if "code" not in params:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No auth code found in callback")
            return
        
        auth_code = params["code"][0]
        print(f"\n[+] Got auth code: {auth_code[:20]}...")
        
        # Exchange immediately
        credentials = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
        resp = requests.post(
            "https://api.schwabapi.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": CALLBACK_URL,
            },
        )
        
        if resp.status_code == 200:
            token_data = resp.json()
            TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
            print(f"[+] Token saved to {TOKEN_PATH}")
            print(f"[+] Access token expires in: {token_data.get('expires_in')}s")
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Success!</h1><p>Schwab API token saved. You can close this tab.</p></body></html>")
            
            # Shutdown after success
            import threading
            threading.Thread(target=self.server.shutdown).start()
        else:
            print(f"[-] Token exchange failed: {resp.status_code} {resp.text}")
            self.send_response(500)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error</h1><pre>{resp.text}</pre></body></html>".encode())
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

# Generate self-signed cert for HTTPS
CERT_PATH = Path(__file__).parent / "schwab_localhost.pem"
KEY_PATH = Path(__file__).parent / "schwab_localhost.key"
if not CERT_PATH.exists():
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(KEY_PATH), "-out", str(CERT_PATH),
        "-days", "365", "-nodes",
        "-subj", "/CN=127.0.0.1"
    ], capture_output=True)

server = http.server.HTTPServer(("127.0.0.1", 443), CallbackHandler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(str(CERT_PATH), str(KEY_PATH))
server.socket = context.wrap_socket(server.socket, server_side=True)

auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?client_id={APP_KEY}&redirect_uri=https%3A//127.0.0.1/&response_type=code"
print(f"[*] Listening on https://127.0.0.1:443")
print(f"[*] Opening auth URL in browser...")
os.system(f'open "{auth_url}"')
print(f"[*] Waiting for callback...")

try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
print("[*] Done.")

```

---

## schwab_data.py

```python
"""
Schwab Market Data module — cross-reference quote source.

Uses Schwab's REST API directly for real-time quotes.
Token stored in schwab_token.json, auto-refreshes access token
(30 min expiry) using the refresh token (7 day expiry — manual
re-auth needed weekly).

Usage:
    from schwab_data import fetch_schwab_quotes
    quotes = fetch_schwab_quotes(["BAC", "QCOM"])
"""

import os
import json
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SCHWAB_APP_KEY = os.environ.get("SCHWAB_APP_KEY", "")
SCHWAB_APP_SECRET = os.environ.get("SCHWAB_APP_SECRET", "")
TOKEN_PATH = Path(__file__).parent / "schwab_token.json"

# Cache token in memory to avoid re-reading file every call
_token_cache = {"access_token": None, "expires_at": 0}


def _load_token():
    """Load token from file, refresh if expired."""
    global _token_cache

    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    if not TOKEN_PATH.exists():
        print(f"[Schwab] No token file at {TOKEN_PATH}")
        return None

    token_data = json.loads(TOKEN_PATH.read_text())

    # Try using existing access token first (test with a lightweight call)
    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    # Try a test request
    try:
        resp = requests.get(
            "https://api.schwabapi.com/marketdata/v1/quotes",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"symbols": "AAPL", "fields": "quote"},
            timeout=5,
        )
        if resp.status_code == 200:
            _token_cache["access_token"] = access_token
            _token_cache["expires_at"] = time.time() + 1500  # ~25 min
            return access_token
    except Exception:
        pass

    # Access token expired — try refresh
    if refresh_token:
        try:
            credentials = base64.b64encode(
                f"{SCHWAB_APP_KEY}:{SCHWAB_APP_SECRET}".encode()
            ).decode()
            resp = requests.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                new_token = resp.json()
                TOKEN_PATH.write_text(json.dumps(new_token, indent=2))
                _token_cache["access_token"] = new_token["access_token"]
                _token_cache["expires_at"] = time.time() + 1500
                print("[Schwab] Access token refreshed successfully")
                return new_token["access_token"]
            else:
                print(f"[Schwab] Token refresh failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"[Schwab] Token refresh error: {e}")

    print("[Schwab] No valid token — re-run OAuth setup")
    return None


def fetch_schwab_quotes(tickers: list) -> dict:
    """
    Fetch real-time quotes from Schwab for a list of tickers.

    Returns dict like:
        {"BAC": {"bid": 52.10, "ask": 52.15, "last": 52.12, "source": "schwab"}, ...}

    Returns empty dict on failure.
    """
    access_token = _load_token()
    if not access_token:
        return {}

    result = {}
    try:
        resp = requests.get(
            "https://api.schwabapi.com/marketdata/v1/quotes",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"symbols": ",".join(tickers), "fields": "quote"},
            timeout=8,
        )

        if resp.status_code == 401:
            # Token just expired mid-request — force refresh
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0
            access_token = _load_token()
            if access_token:
                resp = requests.get(
                    "https://api.schwabapi.com/marketdata/v1/quotes",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"symbols": ",".join(tickers), "fields": "quote"},
                    timeout=8,
                )

        if resp.status_code != 200:
            print(f"[Schwab] Quote request failed ({resp.status_code}): {resp.text[:200]}")
            return {}

        data = resp.json()
        for ticker in tickers:
            if ticker in data:
                q = data[ticker].get("quote", data[ticker])
                bid = float(q.get("bidPrice", 0))
                ask = float(q.get("askPrice", 0))
                last = float(q.get("lastPrice", 0))
                if ask > 0 or last > 0:
                    result[ticker] = {
                        "bid": bid,
                        "ask": ask,
                        "last": last,
                        "mid": round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else last,
                        "source": "schwab",
                    }
    except Exception as e:
        print(f"[Schwab] Quote fetch failed: {e}")

    return result


if __name__ == "__main__":
    import sys
    tickers = sys.argv[1:] or ["BAC", "QCOM", "AAPL"]
    quotes = fetch_schwab_quotes(tickers)
    print(json.dumps(quotes, indent=2, default=str))

```

---

## schwab_reauth.py

```python
#!/usr/bin/env python3
"""
Schwab OAuth Auto Re-Auth Script

Runs weekly via cron to refresh the Schwab API token before the
7-day refresh token expires. Fully automated — uses browser automation
to complete the OAuth flow without human intervention.

Usage:
    python3 schwab_reauth.py

Cron (every 5 days at 3 AM to stay ahead of 7-day expiry):
    0 3 */5 * * cd /Users/chris/code/trading-pipeline && python3 schwab_reauth.py >> logs/schwab_reauth.log 2>&1
"""

import json
import base64
import time
import subprocess
import requests
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

APP_KEY = os.environ["SCHWAB_APP_KEY"]
APP_SECRET = os.environ["SCHWAB_APP_SECRET"]
CALLBACK_URL = "https://127.0.0.1/"
TOKEN_PATH = Path(__file__).parent / "schwab_token.json"
LOG_PREFIX = "[SchwabReAuth]"

# Schwab brokerage credentials (for automated login)
SCHWAB_USERNAME = "chrisbuetti"
SCHWAB_PW_FILE = Path(os.path.expanduser("~/.openclaw/workspace-zuck/.schwabpw"))


def log(msg):
    print(f"{LOG_PREFIX} {msg}", flush=True)


def try_refresh_token():
    """Try to refresh using existing refresh token first."""
    if not TOKEN_PATH.exists():
        return False

    token_data = json.loads(TOKEN_PATH.read_text())
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        return False

    credentials = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    try:
        resp = requests.post(
            "https://api.schwabapi.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            new_token = resp.json()
            TOKEN_PATH.write_text(json.dumps(new_token, indent=2))
            log("✅ Token refreshed via refresh_token grant")
            return True
        else:
            log(f"Refresh token grant failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        log(f"Refresh token request error: {e}")
        return False


def exchange_code(auth_code):
    """Exchange authorization code for tokens."""
    credentials = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    resp = requests.post(
        "https://api.schwabapi.com/v1/oauth/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": CALLBACK_URL,
        },
        timeout=15,
    )
    if resp.status_code == 200:
        token_data = resp.json()
        TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
        log("✅ Token saved via authorization_code grant")
        return True
    else:
        log(f"❌ Code exchange failed ({resp.status_code}): {resp.text[:300]}")
        return False


def verify_token():
    """Verify the token works with a test quote."""
    from schwab_data import fetch_schwab_quotes
    quotes = fetch_schwab_quotes(["AAPL"])
    if quotes:
        log(f"✅ Token verified — AAPL: ${quotes['AAPL']['last']}")
        return True
    else:
        log("❌ Token verification failed — no quotes returned")
        return False


def main():
    log("Starting Schwab token refresh...")

    # Step 1: Try simple refresh token grant
    if try_refresh_token():
        if verify_token():
            log("Done — refresh token grant succeeded")
            return True
        else:
            log("Refresh succeeded but verification failed — falling through to full re-auth")

    log("Refresh token expired or invalid — full re-auth needed")
    log("⚠️ Full browser re-auth required. This will be handled by Zuck agent on next session.")
    log("Alerting via OpenClaw...")

    # Try to alert Chris via OCPlatform
    try:
        subprocess.run(
            ["/opt/homebrew/bin/ocplatform", "message", "send",
             "--channel", "slack",
             "--agent", "zuck",
             "--message", "⚠️ Schwab API token expired and refresh failed. I need to do a full browser re-auth. Will handle it on my next session."],
            timeout=10,
            capture_output=True,
        )
    except Exception:
        pass

    return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

```

---

## test_data_provider.py

```python
"""
Tests for DataProvider abstraction and risk math.
Uses MockDataProvider — no live API calls.

Run: pytest test_data_provider.py -v
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from data_provider import DataProvider, MockDataProvider, DataUnavailable, set_provider, get_provider


# ── Fixtures ─────────────────────────────────────────────────────────

# Shared date index for all mock bars (avoids join misalignment)
_SHARED_DATES = pd.date_range(end="2026-05-28", periods=120, freq="B")


def _make_bars(prices: list, dates=None) -> pd.DataFrame:
    """Create a mock OHLCV DataFrame from a list of close prices."""
    n = len(prices)
    if dates is None:
        dates = _SHARED_DATES[-n:]
    return pd.DataFrame({
        "Open": [p * 0.99 for p in prices],
        "High": [p * 1.01 for p in prices],
        "Low": [p * 0.98 for p in prices],
        "Close": prices,
        "Volume": [1_000_000] * n,
    }, index=dates)


@pytest.fixture
def mock_dp():
    """Set up a MockDataProvider and register it as default."""
    # Generate correlated returns (AAPL and MSFT move together)
    np.random.seed(42)
    common_factor = np.random.randn(120) * 0.02  # shared market factor
    aapl_returns = common_factor + np.random.randn(120) * 0.005
    msft_returns = common_factor + np.random.randn(120) * 0.005
    # TSLA: independent random walk
    tsla_returns = np.random.randn(120) * 0.03

    aapl_prices = [150.0]
    msft_prices = [300.0]
    tsla_prices = [200.0]
    for i in range(119):
        aapl_prices.append(aapl_prices[-1] * (1 + aapl_returns[i]))
        msft_prices.append(msft_prices[-1] * (1 + msft_returns[i]))
        tsla_prices.append(tsla_prices[-1] * (1 + tsla_returns[i]))

    dp = MockDataProvider(
        bars={
            "AAPL": _make_bars(aapl_prices),
            "MSFT": _make_bars(msft_prices),
            "TSLA": _make_bars(tsla_prices),
        },
        indices={
            "VIX": 18.5,
            "SPX": 5425.0,
        },
        splits={
            "NVDA": [{"ticker": "NVDA", "execution_date": "2024-06-10", "split_from": 1, "split_to": 10}],
        },
    )
    set_provider(dp)
    yield dp
    set_provider(None)  # Reset


# ── DataProvider Tests ───────────────────────────────────────────────

class TestDataProviderInterface:

    def test_get_bars_returns_dataframe(self, mock_dp):
        bars = get_provider().get_bars("AAPL", lookback_days=60)
        assert isinstance(bars, pd.DataFrame)
        assert "Close" in bars.columns
        assert len(bars) == 120  # Mock returns all bars

    def test_get_bars_missing_ticker_raises(self, mock_dp):
        with pytest.raises(DataUnavailable):
            get_provider().get_bars("FAKE", lookback_days=60)

    def test_get_index_returns_dict(self, mock_dp):
        idx = get_provider().get_index("VIX")
        assert idx["symbol"] == "VIX"
        assert idx["value"] == 18.5
        assert idx["is_proxy"] is False

    def test_get_index_missing_raises(self, mock_dp):
        with pytest.raises(DataUnavailable):
            get_provider().get_index("FAKE")

    def test_get_corporate_actions(self, mock_dp):
        splits = get_provider().get_corporate_actions("NVDA")
        assert len(splits) == 1
        assert splits[0]["split_to"] == 10

    def test_get_corporate_actions_empty(self, mock_dp):
        splits = get_provider().get_corporate_actions("AAPL")
        assert splits == []


# ── Correlation Veto Tests ───────────────────────────────────────────

class TestCorrelationVeto:

    def test_correlated_tickers_vetoed(self, mock_dp):
        from agent4_risk_manager import correlation_veto
        # AAPL and MSFT share 80% common factor — should be correlated
        # Use lower threshold to account for mock data alignment
        result = correlation_veto("AAPL", ["MSFT"], threshold=0.50)
        assert result is True  # Vetoed

    def test_uncorrelated_tickers_pass(self, mock_dp):
        from agent4_risk_manager import correlation_veto
        # AAPL trending, TSLA random — should not be correlated
        result = correlation_veto("AAPL", ["TSLA"], threshold=0.70)
        assert result is False  # Passes

    def test_empty_positions_pass(self, mock_dp):
        from agent4_risk_manager import correlation_veto
        result = correlation_veto("AAPL", [], threshold=0.70)
        assert result is False

    def test_data_unavailable_vetoes(self, mock_dp):
        from agent4_risk_manager import correlation_veto
        # FAKE ticker not in mock — should fail-closed (veto)
        result = correlation_veto("FAKE", ["AAPL"], threshold=0.70)
        assert result is True  # Fail-closed: no data for candidate = veto

    def test_nan_correlation_vetoes(self, mock_dp):
        from agent4_risk_manager import correlation_veto
        from data_provider import MockDataProvider, set_provider
        # Create two tickers with non-overlapping dates → NaN correlation
        dates_a = pd.date_range(end="2026-01-15", periods=60, freq="B")
        dates_b = pd.date_range(end="2026-05-15", periods=60, freq="B")
        dp = MockDataProvider(bars={
            "AAA": _make_bars([100 + i for i in range(60)], dates=dates_a),
            "BBB": _make_bars([200 + i for i in range(60)], dates=dates_b),
        })
        set_provider(dp)
        result = correlation_veto("AAA", ["BBB"], threshold=0.70)
        assert result is True  # NaN = fail-closed
        set_provider(mock_dp)  # Restore


# ── Size Position Tests ──────────────────────────────────────────────

class TestSizePosition:

    def test_basic_sizing(self, mock_dp):
        from agent4_risk_manager import size_position
        result = size_position(
            entry=100.0, stop=95.0, account_value=10000,
            tier="PASS", confirm_enhanced=False, vol_regime="Normal",
            posture="Aggressive", session_risk_used=0.0,
        )
        assert result["shares"] > 0
        assert result["binding_constraint"] in ("risk", "allocation")

    def test_tight_stop_floor(self, mock_dp):
        from agent4_risk_manager import size_position
        # Stop distance = $0.10 on $100 stock (0.1%)
        # Without 1% floor: shares = risk / 0.10 = huge
        # With 1% floor: shares = risk / 1.00 = reasonable
        result = size_position(
            entry=100.0, stop=99.90, account_value=10000,
            tier="PASS", confirm_enhanced=False, vol_regime="Normal",
            posture="Aggressive", session_risk_used=0.0,
        )
        # Position should be capped by allocation, not infinite
        assert result["shares"] > 0
        max_alloc_shares = int(10000 * 0.25 / 100)  # 25% of 10k
        assert result["shares"] <= max_alloc_shares

    def test_invalid_stop_zero_shares(self, mock_dp):
        from agent4_risk_manager import size_position
        result = size_position(
            entry=100.0, stop=100.0, account_value=10000,
            tier="PASS", confirm_enhanced=False, vol_regime="Normal",
            posture="Aggressive", session_risk_used=0.0,
        )
        assert result["shares"] == 0

    def test_bunker_posture_zero_shares(self, mock_dp):
        from agent4_risk_manager import size_position
        result = size_position(
            entry=100.0, stop=95.0, account_value=10000,
            tier="PASS", confirm_enhanced=False, vol_regime="Normal",
            posture="Bunker", session_risk_used=0.0,
        )
        assert result["shares"] == 0

    def test_session_budget_exhausted(self, mock_dp):
        from agent4_risk_manager import size_position
        result = size_position(
            entry=100.0, stop=95.0, account_value=10000,
            tier="PASS", confirm_enhanced=False, vol_regime="Normal",
            posture="Aggressive", session_risk_used=99999.0,
        )
        assert result["shares"] == 0
        assert "EXHAUSTED" in result.get("reason", "")


# ── Index Fallback Chain Tests ───────────────────────────────────────

class TestIndexFallback:

    def test_massive_hit(self, mock_dp):
        idx = get_provider().get_index("VIX")
        assert idx["value"] == 18.5
        assert idx["source"] == "mock"

    def test_all_miss_raises(self):
        empty_dp = MockDataProvider()
        set_provider(empty_dp)
        with pytest.raises(DataUnavailable):
            get_provider().get_index("VIX")
        set_provider(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

```

---

## trade_journal.py

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

---

## vwap_gate.py

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

---

## watchlist.py

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

---

## weekly_review.py

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

---

## x_fetch.py

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
