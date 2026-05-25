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

    print(f"[Agent 1] Macro data loaded from {macro_data.get('timestamp', 'unknown')}")

    # Send to Claude
    print("[Agent 1] Sending to Claude for regime classification...")

    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform instead.")
        client = anthropic.Anthropic(api_key=api_key)

        user_message = f"""Here is today's macro data. Classify the regime and produce your directive.

CRITICAL: If DIX, MOVE, or Credit data is marked as unavailable, you MUST output REGIME: DEFER.

{macro_text}{assembly_text}

Current date/time: {datetime.now().isoformat()}

Respond with ONLY the JSON directive, no other text."""

        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000,
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # With extended thinking, content has thinking + text blocks
        raw_text = next(b.text for b in response.content if b.type == "text").strip()
    except RuntimeError:
        # No API key — return the prompt for subagent execution
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
