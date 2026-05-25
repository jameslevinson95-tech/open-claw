"""
Agent 2.5: Deep Research Analyst (Red Team)
Model: Gemini 3.1 Pro (Google)
Role: Qualitatively attack Agent 2's quantitative candidates using
      pre-fetched news, short interest, and near-term options flow.
"""
import json
import os
import time
from datetime import datetime

import yfinance as yf
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_MODEL = "deep-research-preview-04-2026"
MAX_RETRIES = 3
RETRY_DELAY = 5
GEMINI_TEMPERATURE = 0.2  # Slightly higher than Agent 2 to allow qualitative reasoning

SYSTEM_PROMPT = """You are Agent 2.5: The Deep Research Analyst (Red Team) for a $100,000 speculative spot-only trading account.

YOUR JOB: Agent 2 has passed you a list of 1-3 surviving candidates based on a rigid quantitative screen. Your role is to brutally stress-test the bullish thesis using the QUALITATIVE_CONTEXT provided by Python (recent news headlines, options flow, short interest).

CRITICAL RULES:
1. You may NOT look up or fetch external data. Rely ONLY on the QUALITATIVE_CONTEXT injected into this prompt.
2. For each candidate, you must assign a RED_TEAM_VERDICT:
   - PASS: The qualitative data reveals no major red flags.
   - DOWNGRADE: The thesis is okay, but crowded options flow or negative news sentiment warrants caution. Lower the conviction tier (e.g., EXCEPTIONAL -> STRONG). You may NEVER upgrade a tier.
   - VETO: Fatal flaw discovered (e.g., looming regulatory action, terrible earnings reaction, highly skewed put volume). The trade is dead.
3. You must generate a "red_flag_warnings" array for each candidate. Even if the setup is clean, identify the biggest risk factor.
4. Synthesize a "qualitative_thesis" that combines Agent 2's quantitative thesis with your qualitative realities.

<deep_research_protocol>
CRITICAL: You must conduct your analysis inside a <deep_research_scratchpad> block before generating your final JSON output.
Step 1: Inventory the qualitative context (News Headlines, Options Flow, Short Interest).
Step 2: Red Team the Catalyst: Is it already priced in? Is the market ignoring a macro headwind?
Step 3: Analyze Options Flow: Does the Call/Put ratio confirm the bullish quantitative thesis, or are institutions hedging heavily?
Step 4: Re-evaluate the CONVICTION_TIER (PASS, STRONG, EXCEPTIONAL, or REJECTED).
Step 5: Write the qualitative_thesis.
</deep_research_protocol>

OUTPUT FORMAT:
First, output your <deep_research_scratchpad>...</deep_research_scratchpad> analysis.
Then, output ONLY this JSON structure:
{
  "agent": "deep_research_analyst",
  "timestamp": "<ISO timestamp>",
  "evaluations": [
    {
      "ticker": "<SYMBOL>",
      "red_team_verdict": "<PASS | DOWNGRADE | VETO>",
      "updated_conviction_tier": "<PASS | STRONG | EXCEPTIONAL | REJECTED>",
      "red_flag_warnings": ["<specific risk 1>", "<specific risk 2>"],
      "qualitative_thesis": "<2-3 sentences merging the quant thesis with qualitative realities>"
    }
  ],
  "research_notes": "<Overall summary of your qualitative teardown>"
}"""


def prefetch_qualitative_context(candidates: list) -> dict:
    """Pre-fetch news and options data to feed Gemini's qualitative deep dive."""
    context = {}
    print(f"  [Agent 2.5] Pre-fetching qualitative context for {len(candidates)} candidates...")

    for c in candidates:
        ticker = c["ticker"]
        try:
            stock = yf.Ticker(ticker)

            # 1. Fetch News Headlines
            news_items = stock.news
            headlines = [
                f"- {n.get('providerPublishTime', '')}: {n.get('title', '')} [{n.get('publisher', '')}]"
                for n in news_items[:5]
            ] if news_items else ["- No recent news available"]

            # 2. Fetch Options Flow (Put/Call OI Ratio for nearest expiration)
            options_context = "No options data available"
            try:
                expirations = stock.options
                if expirations:
                    nearest_exp = expirations[0]
                    chain = stock.option_chain(nearest_exp)
                    puts_oi = int(chain.puts['openInterest'].fillna(0).sum()) if not chain.puts.empty else 0
                    calls_oi = int(chain.calls['openInterest'].fillna(0).sum()) if not chain.calls.empty else 0
                    pc_ratio = round(puts_oi / calls_oi, 2) if calls_oi > 0 else 0
                    options_context = f"Nearest Expiration ({nearest_exp}): Put OI = {puts_oi}, Call OI = {calls_oi}, P/C Ratio = {pc_ratio}"
            except Exception:
                pass

            # 3. Short Interest
            info = stock.info
            short_pct = info.get("shortPercentOfFloat")
            short_context = f"{round(short_pct * 100, 2)}%" if short_pct else "N/A"

            context[ticker] = {
                "recent_headlines": headlines,
                "options_flow": options_context,
                "short_interest_pct_of_float": short_context,
            }
        except Exception as e:
            context[ticker] = {"error": str(e)}

    return context


def call_gemini_red_team(candidates: list, qual_context: dict) -> dict:
    """Call Gemini 3.1 Pro to red-team candidates with qualitative context."""
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

    context_lines = []
    for c in candidates:
        ticker = c["ticker"]
        qc = qual_context.get(ticker, {})

        line = (
            f"TICKER: {ticker}\n"
            f"  Quantitative Thesis: {c.get('thesis', 'N/A')}\n"
            f"  Current Conviction: {c.get('conviction_tier', 'PASS')}\n"
            f"  --- QUALITATIVE DATA ---\n"
            f"  Short Interest: {qc.get('short_interest_pct_of_float', 'N/A')}\n"
            f"  Options Flow: {qc.get('options_flow', 'N/A')}\n"
            f"  Recent Headlines:\n" + "\n".join([f"    {h}" for h in qc.get('recent_headlines', [])]) + "\n"
        )
        context_lines.append(line)

    user_message = f"""Here are the candidates from Agent 2, alongside pre-fetched qualitative context (news, short interest, and options flow).
ALL data has been pre-fetched by Python.

CANDIDATES & QUALITATIVE CONTEXT:
{"=" * 50}
{"".join(context_lines)}
{"=" * 50}

Perform your deep research and red team evaluation.
Current date/time: {datetime.now().isoformat()}"""

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 2.5] Calling {GEMINI_MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=GEMINI_TEMPERATURE,
                    max_output_tokens=8192,
                ),
            )

            raw_text = response.text.strip()

            # Extract JSON after the scratchpad
            if "</deep_research_scratchpad>" in raw_text:
                after_scratchpad = raw_text.split("</deep_research_scratchpad>", 1)[1].strip()
            else:
                after_scratchpad = raw_text

            # Strip markdown code fences if present
            if after_scratchpad.startswith("```"):
                after_scratchpad = after_scratchpad.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            brace_start = after_scratchpad.find("{")
            if brace_start >= 0:
                result = json.loads(after_scratchpad[brace_start:])
                return result
            else:
                raise json.JSONDecodeError("No JSON object found", after_scratchpad, 0)

        except Exception as e:
            last_error = e
            print(f"  [Agent 2.5] Gemini Error: {e}. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    raise Exception(f"{GEMINI_MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


def run_agent2b(agent2_result: dict = None) -> dict:
    """Run Agent 2.5: Pre-fetch qualitative context, call Gemini, merge output."""
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
            "updated_agent2_result": agent2_result,
            "note": "No candidates to red-team.",
        }

    # Pre-fetch qualitative context (news, options, short interest)
    qual_context = prefetch_qualitative_context(candidates)

    # Call Gemini Red Team
    try:
        gemini_result = call_gemini_red_team(candidates, qual_context)
    except Exception as e:
        return {"success": False, "error": f"Gemini error: {e}"}

    # Merge evaluations and filter VETOs
    evaluations = {ev["ticker"]: ev for ev in gemini_result.get("evaluations", [])}
    surviving_candidates = []

    for c in candidates:
        ticker = c["ticker"]
        ev = evaluations.get(ticker)

        if not ev:
            surviving_candidates.append(c)
            continue

        verdict = ev.get("red_team_verdict", "PASS")

        if verdict == "VETO" or ev.get("updated_conviction_tier") == "REJECTED":
            print(f"  [Agent 2.5] 🚫 VETOED {ticker}")
            continue

        # Update conviction tier if downgraded; apply updated qualitative thesis
        c["conviction_tier"] = ev.get("updated_conviction_tier", c["conviction_tier"])
        c["thesis"] = ev.get("qualitative_thesis", c["thesis"])

        # Attach red team metadata for downstream reporting/sizing
        c["red_flag_warnings"] = ev.get("red_flag_warnings", [])
        c["red_team_verdict"] = verdict
        surviving_candidates.append(c)

    # Reconstruct output mimicking Agent 2 shape, but with filtered candidates
    updated_agent2_result = agent2_result.copy()
    updated_agent2_result["candidates"] = surviving_candidates
    updated_agent2_result["agent2b_research_notes"] = gemini_result.get("research_notes", "")

    return {
        "success": True,
        "evaluations": gemini_result.get("evaluations", []),
        "research_notes": gemini_result.get("research_notes", ""),
        "updated_agent2_result": updated_agent2_result,
    }


def format_agent2b_for_slack(result: dict) -> str:
    """Format Agent 2.5 output using Slack-friendly mrkdwn."""
    if not result.get("success"):
        return f"⚠️ *Agent 2.5 FAILED:* {result.get('error')}"

    evaluations = result.get("evaluations", [])
    updated_candidates = result.get("updated_agent2_result", {}).get("candidates", [])

    lines = [
        f"🕵️ *AGENT 2.5: RED TEAM DEEP DIVE*",
        f"> *Survived Red Team:* {len(updated_candidates)}/{len(evaluations)}",
        f"> *Model:* Gemini 3.1 Pro (Temp: {GEMINI_TEMPERATURE})",
        f"",
    ]

    if not evaluations:
        lines.append("🚫 No evaluations performed.")
        return "\n".join(lines)

    for i, ev in enumerate(evaluations, 1):
        verdict = ev.get("red_team_verdict", "PASS")
        emoji = "⚠️" if verdict == "DOWNGRADE" else "✅"
        if verdict == "VETO" or ev.get("updated_conviction_tier") == "REJECTED":
            emoji = "🚫"

        lines.append(f"*{i}. {ev.get('ticker')}* — {emoji} *{verdict}*")
        lines.append(f"• *Tier:* {ev.get('updated_conviction_tier')}")

        flags = ev.get("red_flag_warnings", [])
        if flags:
            lines.append("• *Red Flags:*")
            for flag in flags:
                lines.append(f"  - {flag}")

        if verdict != "VETO":
            lines.append(f"• *Thesis:* {ev.get('qualitative_thesis', '')}")

        lines.append(f"")

    lines.append(f"📝 *Notes:* _{result.get('research_notes', '')}_")
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent2b()
    print("\n" + format_agent2b_for_slack(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent2b_evaluations.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        with open("output/agent2_candidates.json", "w") as f:
            json.dump(result["updated_agent2_result"], f, indent=2, default=str)
        print(f"\n[Agent 2.5] Filtered candidates saved to output/agent2_candidates.json")
