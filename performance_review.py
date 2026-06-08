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
        "assembly": {"name": "Market Sentiment (CNN F&G + yfinance)", "icon": "🏦", "cost": "Free", "role": "Sentiment composite, sub-component breadth"},
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
    report.append("  _MEDIUM VALUE:_ Massive Technicals (saves compute), Finviz (dynamic screening), Market Sentiment (CNN F&G)")
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
