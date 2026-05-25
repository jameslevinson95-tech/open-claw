"""
Agent 3: Smart Money Verifier — v2.1
Model: Claude (Anthropic)
Role: Reads smart money Twitter/X sentiment for surviving tickers and
      outputs a VERIFICATION_SCORE (0-10).

X/Twitter research is MANDATORY — no bypass. If data is unavailable,
the pipeline halts with an error rather than skipping.
"""
import json
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# Curated smart money accounts to monitor
# These are the accounts whose sentiment we track
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

SYSTEM_PROMPT = """You are Agent 3: The Smart Money Verifier for a $100,000 speculative spot-only trading account.

YOUR JOB: Given curated smart money mentions from X/Twitter (7-day lookback, 31 institutional-grade accounts), determine whether smart money sentiment supports or vetoes each candidate trade.

OUTPUT EXACTLY ONE OF THE FOLLOWING VERDICTS per candidate:

- PASS_THROUGH: Default verdict. Smart money is silent, mildly mixed, or moderately positive. The trade proceeds as-is using Agent 2's conviction tier. No numeric score.

- VETO_DIVERGENT: 3 or more curated accounts are bearish on the ticker, OR at least 1 hedge fund principal (boazweinstein, CliffordAsness, DylanLeClair_, cngarabedian, RayDalio) is bearish. Effect: REJECT the trade. It does not proceed to Agent 4.

- VETO_CROWDED: 8 or more curated accounts are bullish on the same ticker within the last 48 hours. Effect: REJECT the trade (contrarian signal — too crowded).

- CONFIRM_ENHANCED: 2 or more sector specialists or hedge fund principals are publicly aligned with the thesis, AND zero curated accounts are bearish. Effect: Trade proceeds with a CONFIRM_BONUS applied in Agent 4B sizing.

RULES:
- Do NOT produce a numeric score. The verdict IS the output.
- Cite specific tweets or accounts that drove your verdict.
- If no mentions exist for a ticker, the verdict is PASS_THROUGH (silence is not a red flag).
- Be rigorous about VETO thresholds — do not veto on 1-2 mildly negative mentions.

OUTPUT FORMAT — respond with ONLY this JSON:
{
  "agent": "smart_money_verifier",
  "timestamp": "<ISO timestamp>",
  "verifications": [
    {
      "ticker": "<SYMBOL>",
      "verdict": "<PASS_THROUGH | VETO_DIVERGENT | VETO_CROWDED | CONFIRM_ENHANCED>",
      "sentiment_read": "<1-2 sentence summary of smart money stance>",
      "cited_accounts": ["<specific accounts that drove this verdict>"],
      "cited_tweets": ["<key tweet excerpts>"]
    }
  ],
  "overall_note": "<any cross-candidate observations>"
}"""


def fetch_x_mentions(tickers: list) -> dict:
    """
    Fetch Twitter/X mentions from curated smart money accounts
    for the given tickers over the last 14 days.
    
    Uses the x_search tool via the OpenClaw pipeline.
    Returns structured mention data per ticker.
    """
    # This function is called by the orchestrator, which has access to x_search.
    # When running standalone, it reads from the pre-fetched file.
    mentions_path = "output/smart_money_mentions.json"
    if os.path.exists(mentions_path):
        with open(mentions_path) as f:
            data = json.load(f)
        # x_fetch.py saves mentions nested under "mentions" key
        if "mentions" in data:
            return data["mentions"]
        return data

    # If no pre-fetched data exists, raise an error — X research is mandatory
    raise RuntimeError(
        "No smart money X/Twitter data found at output/smart_money_mentions.json. "
        "X research is MANDATORY — run x_fetch.py first. "
        "The pipeline cannot proceed without smart money sentiment data."
    )


def run_agent3(agent2_result: dict = None, x_mentions: dict = None) -> dict:
    """
    Run Agent 3: Analyze smart money X/Twitter sentiment.
    X research is MANDATORY — pipeline halts if data is unavailable.
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
            "verifications": [],
            "note": "No candidates to verify.",
        }

    tickers = [c.get("ticker") for c in candidates]

    # Fetch X mentions — MANDATORY, no bypass
    if x_mentions is None:
        try:
            x_mentions = fetch_x_mentions(tickers)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    # Filter mentions for our specific tickers
    ticker_mentions = {}
    for ticker in tickers:
        ticker_mentions[ticker] = x_mentions.get(ticker, x_mentions.get(ticker.lower(), []))

    print(f"[Agent 3] Analyzing X/Twitter sentiment for {len(tickers)} tickers: {tickers}")
    for t, mentions in ticker_mentions.items():
        count = len(mentions) if isinstance(mentions, list) else 0
        print(f"  [Agent 3] {t}: {count} mentions from curated accounts")

    # Send to Claude for interpretation
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OpenClaw.")

        client = anthropic.Anthropic(api_key=api_key)

        user_message = f"""Analyze smart money X/Twitter sentiment for these candidates.

CANDIDATES FROM AGENT 2:
{json.dumps([{"ticker": c.get("ticker"), "thesis": c.get("thesis"), "theme": c.get("theme_match")} for c in candidates], indent=2)}

CURATED SMART MONEY X/TWITTER MENTIONS (last 7 days):
{json.dumps(ticker_mentions, indent=2)}

CURATED ACCOUNTS MONITORED:
{json.dumps(CURATED_ACCOUNTS)}

Current date/time: {datetime.now().isoformat()}

Score each ticker's smart money alignment. Respond with ONLY the JSON output."""

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
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()

        result = json.loads(raw_text)

        # Validate verification_score is integer
        for v in result.get("verifications", []):
            score = v.get("verification_score")
            if not isinstance(score, int):
                raise ValueError(f"verification_score must be int, got: {score}")

        result["success"] = True
        result["candidates_passthrough"] = candidates
        return result

    except RuntimeError as e:
        # No API key — return data for subagent execution
        return {
            "success": False,
            "needs_subagent": True,
            "prompt": SYSTEM_PROMPT,
            "candidates": candidates,
            "x_mentions": ticker_mentions,
        }
    except Exception as e:
        return {"success": False, "error": f"Claude API error: {e}"}


def format_agent3_for_telegram(result: dict) -> str:
    """Format Agent 3 output for Telegram."""
    if not result.get("success"):
        return f"⚠️ Agent 3 FAILED: {result.get('error')}"

    lines = [
        f"{'='*30}",
        f"📡 AGENT 3: SMART MONEY VERIFIER (v2.1)",
        f"{'='*30}",
        f"",
    ]

    for v in result.get("verifications", []):
        score = v.get("verification_score", "?")
        flag = v.get("flag", "unknown")

        flag_emoji = {
            "aligned": "🟢",
            "contested": "🟡",
            "silent": "⚪",
            "crowded": "🔴",
            "divergent": "🔴",
        }.get(flag, "❓")

        lines.append(f"{'─'*25}")
        lines.append(f"{flag_emoji} {v.get('ticker')} — Score: {score}/10 [{flag.upper()}]")
        lines.append(f"  💬 {v.get('sentiment_read', 'N/A')}")
        mentions = v.get("key_mentions", [])
        if mentions:
            lines.append(f"  📣 Key: {', '.join(mentions)}")
        lines.append(f"")

    if result.get("overall_note"):
        lines.append(f"📝 {result.get('overall_note')}")

    return "\n".join(lines)


if __name__ == "__main__":
    result = run_agent3()
    print("\n" + format_agent3_for_telegram(result))

    if result.get("success"):
        os.makedirs("output", exist_ok=True)
        with open("output/agent3_verified.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[Agent 3] Results saved to output/agent3_verified.json")
