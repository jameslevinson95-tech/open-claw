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
            stock = yf.Ticker(ticker)

            # 1. News Headlines
            news_items = stock.news
            headlines = [
                f"- {n.get('providerPublishTime', '')}: {n.get('title', '')} [{n.get('publisher', '')}]"
                for n in (news_items[:5] if news_items else [])
            ] or ["- No recent news available"]

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

    # X research is mandatory — raise if missing
    raise RuntimeError(
        "No smart money X/Twitter data found at output/smart_money_mentions.json. "
        "X research is MANDATORY — run x_fetch.py first. "
        "The pipeline cannot proceed without smart money sentiment data."
    )


def call_synthesis(candidates: list, qual_context: dict, x_mentions: dict) -> dict:
    """
    Send the complete qualitative mosaic to Claude Opus 4.7 for unified synthesis.
    Uses adaptive thinking (extended thinking with budget_tokens).
    """
    import anthropic
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("No ANTHROPIC_API_KEY — run as subagent via OCPlatform.")

    client = anthropic.Anthropic(api_key=api_key)

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
    for attempt in range(MAX_RETRIES):
        try:
            print(f"  [Agent 3] Calling {MODEL} (attempt {attempt + 1}/{MAX_RETRIES})...")

            response = client.messages.create(
                model=MODEL,
                max_tokens=16000,
                temperature=1,  # Required for extended thinking
                thinking={
                    "type": "enabled",
                    "budget_tokens": 10000,
                },
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # With extended thinking, content has thinking + text blocks
            raw_text = next(b.text for b in response.content if b.type == "text").strip()

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

        except RuntimeError:
            raise  # Re-raise missing API key
        except Exception as e:
            last_error = e
            print(f"  [Agent 3] Claude error: {e}. Retrying in {RETRY_DELAY}s...")
            import time
            time.sleep(RETRY_DELAY)

    raise Exception(f"{MODEL} failed after {MAX_RETRIES} attempts. Last error: {last_error}")


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
