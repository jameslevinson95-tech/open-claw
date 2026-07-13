#!/usr/bin/env python3
"""
Alpha Tracker — cumulative portfolio performance vs the S&P 500 (SPY).

Jamie (2026-07-12): track how we're doing against the S&P over time and use it
to judge the model + inform the "when do I add capital" decision.

Each closed trade already logs spx_change_over_hold_pct (SPY's move over that
trade's exact holding window). This rolls those up into:
  - Cumulative strategy return (compounded R-weighted / $-weighted)
  - Cumulative SPY return over the same holding periods (benchmark)
  - ALPHA = strategy - benchmark
  - Monthly buckets so you can see "beat SPY by X% for C consecutive months"
  - Consistency stats (hit rate vs SPY, months of positive alpha)

NOTE on methodology: This is a TRADE-MATCHED benchmark — for each trade we
compare our return to SPY over the SAME days we held it. That isolates
selection/timing skill from simply being long during a bull market (pure beta).
It is NOT a buy-and-hold-SPY comparison of the whole account (that would also
reward/penalize sitting in cash). Both views have merit; this one answers
"is the strategy adding alpha when deployed."

USAGE
    python3 alpha_tracker.py            # full text report
    python3 alpha_tracker.py --json     # machine-readable
    python3 alpha_tracker.py --monthly  # month-by-month alpha table only
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")


def _load():
    if not JOURNAL_PATH.exists():
        return []
    import csv
    with JOURNAL_PATH.open() as f:
        return list(csv.DictReader(f))


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def compute(rows):
    """Return the full alpha analysis dict over the provided closed trades."""
    usable = [r for r in rows if r.get("pnl_pct") not in (None, "")]
    n = len(usable)
    if n == 0:
        return {"trades": 0, "note": "No closed trades yet."}

    # Trade-matched: our pnl_pct vs SPY's move over the same hold.
    strat_returns = [_f(r.get("pnl_pct")) for r in usable]
    spy_returns = [_f(r.get("spx_change_over_hold_pct")) for r in usable]
    per_trade_alpha = [s - b for s, b in zip(strat_returns, spy_returns)]

    # Average per-trade alpha and how often we beat SPY on a given trade.
    avg_alpha = sum(per_trade_alpha) / n
    beat_spy = sum(1 for a in per_trade_alpha if a > 0)

    # Cumulative compounded (treat each trade's pct as sequential — approximation
    # since positions overlap, but a reasonable strategy-vs-benchmark proxy).
    def _compound(pcts):
        eq = 1.0
        for p in pcts:
            eq *= (1 + p / 100.0)
        return (eq - 1) * 100

    cum_strat = _compound(strat_returns)
    cum_spy = _compound(spy_returns)
    cum_alpha = cum_strat - cum_spy

    # Monthly buckets keyed by exit month.
    monthly = defaultdict(lambda: {"strat": [], "spy": []})
    for r in usable:
        exit_dt = r.get("exit_dt", "")
        month = exit_dt[:7] if len(exit_dt) >= 7 else "unknown"
        monthly[month]["strat"].append(_f(r.get("pnl_pct")))
        monthly[month]["spy"].append(_f(r.get("spx_change_over_hold_pct")))

    monthly_rows = []
    for month in sorted(monthly.keys()):
        s = _compound(monthly[month]["strat"])
        b = _compound(monthly[month]["spy"])
        monthly_rows.append({
            "month": month,
            "trades": len(monthly[month]["strat"]),
            "strat_pct": round(s, 2),
            "spy_pct": round(b, 2),
            "alpha_pct": round(s - b, 2),
            "beat": s > b,
        })

    # Consecutive months of positive alpha, counting back from the latest.
    consec_beat = 0
    for mr in reversed(monthly_rows):
        if mr["month"] == "unknown":
            continue
        if mr["beat"]:
            consec_beat += 1
        else:
            break

    months_positive = sum(1 for mr in monthly_rows if mr["beat"] and mr["month"] != "unknown")
    total_months = sum(1 for mr in monthly_rows if mr["month"] != "unknown")

    return {
        "trades": n,
        "cum_strategy_pct": round(cum_strat, 2),
        "cum_spy_pct": round(cum_spy, 2),
        "cum_alpha_pct": round(cum_alpha, 2),
        "avg_per_trade_alpha_pct": round(avg_alpha, 2),
        "beat_spy_trades": beat_spy,
        "beat_spy_rate_pct": round(beat_spy / n * 100, 1),
        "consecutive_months_beating_spy": consec_beat,
        "months_positive_alpha": months_positive,
        "total_months": total_months,
        "monthly": monthly_rows,
    }


def render(rows):
    a = compute(rows)
    if a.get("trades", 0) == 0:
        return "📈 *ALPHA vs S&P 500* — no closed trades yet."

    lines = [
        "📈 *STRATEGY vs S&P 500 (trade-matched)*",
        "=" * 40,
        f"Closed trades: {a['trades']}",
        f"Cumulative strategy: {a['cum_strategy_pct']:+.2f}%",
        f"Cumulative SPY (same holds): {a['cum_spy_pct']:+.2f}%",
        f"*Cumulative ALPHA: {a['cum_alpha_pct']:+.2f}%*",
        f"Avg alpha per trade: {a['avg_per_trade_alpha_pct']:+.2f}%",
        f"Beat SPY on {a['beat_spy_trades']}/{a['trades']} trades ({a['beat_spy_rate_pct']}%)",
        f"Positive-alpha months: {a['months_positive_alpha']}/{a['total_months']} "
        f"(current streak: {a['consecutive_months_beating_spy']} mo)",
    ]

    if a["monthly"]:
        lines.append("")
        lines.append("*Monthly:*")
        for mr in a["monthly"]:
            mark = "✅" if mr["beat"] else "🔻"
            lines.append(
                f"  {mark} {mr['month']}: strat {mr['strat_pct']:+.1f}% vs "
                f"SPY {mr['spy_pct']:+.1f}% → α {mr['alpha_pct']:+.1f}% ({mr['trades']}t)"
            )

    # Honesty guard on small samples.
    if a["trades"] < 20:
        lines.append("")
        lines.append(f"_⚠️ Only {a['trades']} trades — alpha is not yet statistically meaningful. "
                     "Directional read only._")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = _load()
    if "--json" in sys.argv:
        print(json.dumps(compute(rows), indent=2))
    elif "--monthly" in sys.argv:
        a = compute(rows)
        for mr in a.get("monthly", []):
            print(f"{mr['month']}: strat {mr['strat_pct']:+.1f}% | SPY {mr['spy_pct']:+.1f}% "
                  f"| alpha {mr['alpha_pct']:+.1f}% | {mr['trades']}t")
    else:
        print(render(rows))
