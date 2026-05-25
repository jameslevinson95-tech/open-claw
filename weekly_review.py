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
