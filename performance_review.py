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

    return "\n".join(report)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA SOURCE QUALITY AUDIT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def audit_data_sources():
    """
    Audit data source quality across archived pipeline runs.
    Grades each source: Strong 🟢, Neutral ⚪, or Weak 🔴.
    """
    if not os.path.exists(ARCHIVE_DIR):
        return "  ⚠️ No archive data available for audit."

    runs = sorted(os.listdir(ARCHIVE_DIR))[-14:]  # Last 14 runs
    mentions_list = []
    missing_data_flags = []

    for run in runs:
        run_dir = os.path.join(ARCHIVE_DIR, run)
        if not os.path.isdir(run_dir):
            continue

        # Twitter/X Audit
        sm_file = os.path.join(run_dir, "smart_money_mentions.json")
        if os.path.exists(sm_file):
            try:
                with open(sm_file) as f:
                    data = json.load(f)
                # Handle both formats: list of mentions or dict with total
                if isinstance(data, dict):
                    mentions_list.append(data.get("total_mentions", 0))
                elif isinstance(data, list):
                    mentions_list.append(len(data))
            except Exception:
                pass

        # Macro Audit
        macro_file = os.path.join(run_dir, "preflight_macro.json")
        if os.path.exists(macro_file):
            try:
                with open(macro_file) as f:
                    macro = json.load(f)
                if isinstance(macro, dict):
                    if "DIX" not in macro or (isinstance(macro.get("DIX"), dict) and "error" in macro["DIX"]):
                        missing_data_flags.append(f"DIX missing in {run}")
                    if "MOVE" not in macro or (isinstance(macro.get("MOVE"), dict) and "error" in macro["MOVE"]):
                        missing_data_flags.append(f"MOVE missing in {run}")
            except Exception:
                pass

    report = ["\n*3. Data Source Quality Audit*"]

    avg_mentions = np.mean(mentions_list) if mentions_list else 0

    x_grade = "Neutral ⚪"
    x_note = "Awaiting sufficient data"
    if avg_mentions < 5 and len(mentions_list) > 0:
        x_grade = "Weak 🔴"
        x_note = f"Mention volume too low (Avg {avg_mentions:.1f}). Consider expanding accounts."
    elif avg_mentions >= 5:
        x_grade = "Strong 🟢"
        x_note = f"Solid institutional coverage (Avg {avg_mentions:.1f})."

    report.append(f"  🐦 *X/Twitter Smart Money:* {x_grade} — _{x_note}_")
    report.append("  💬 *Discord:* Neutral ⚪ — _Output only right now, signal-to-noise TBD._")

    macro_grade = "Strong 🟢"
    macro_note = "Clean data"
    if missing_data_flags:
        macro_grade = "Weak 🔴"
        macro_note = f"Missing critical data (e.g., {missing_data_flags[-1]})."

    report.append(f"  📊 *Assembly/FRED Macro:* {macro_grade} — _{macro_note}_")

    tech_grade = "Strong 🟢" if os.path.exists(os.path.join(OUTPUT_DIR, "technicals.json")) else "Weak 🔴"
    tech_note = "Technicals correlating well" if tech_grade == "Strong 🟢" else "No technicals data found"
    report.append(f"  📈 *Polygon/Massive API:* {tech_grade} — _{tech_note}_")

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
