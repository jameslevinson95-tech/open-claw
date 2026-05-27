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
