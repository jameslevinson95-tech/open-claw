#!/usr/bin/env python3
"""
Milestone Review — trade-count-triggered performance checkpoints.

Jamie (2026-07-12): track how we're doing at 50, 100, 500, 1000 closed trades.
Each milestone gives tighter statistical confidence on what's actually binding
sizing (risk vs allocation vs dry_powder / heat cap) so we tune the right knob.

HOW IT WORKS
    - Reads journal/trades.csv (the closed-trade log).
    - Fires a review ONCE when the cumulative closed-trade count crosses a
      milestone in MILESTONES. State is persisted in journal/.milestones_fired.json
      so it never double-reports (idempotent — safe to run daily).
    - The review itself reuses performance_review.py's analysis (binding-constraint
      distribution, tier R-multiples, win rate, heat) plus a milestone-specific
      binding-constraint summary aimed at the heat-cap / sizing decision.

USAGE
    python3 milestone_review.py            # check + fire any newly-crossed milestone
    python3 milestone_review.py --status   # show counts + which milestones fired
    python3 milestone_review.py --force N   # force-render the report as if at N trades

Designed to be called by a daily cron AFTER the market close / EOD steps.
Prints the report to stdout; the cron delivers it to #trading.
"""

import json
import os
import sys
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")
STATE_PATH = Path("journal/.milestones_fired.json")
MILESTONES = [50, 100, 500, 1000]


def _load_trades():
    if not JOURNAL_PATH.exists():
        return []
    import csv
    with JOURNAL_PATH.open() as f:
        return list(csv.DictReader(f))


def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"fired": []}


def _save_state(state):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _binding_summary(rows):
    """Milestone-focused: what is actually capping our sizing?"""
    from collections import Counter
    n = len(rows)
    if n == 0:
        return "No closed trades yet."
    have = [r for r in rows if r.get("binding_constraint")]
    if not have:
        return "binding_constraint not recorded on any trade yet (older trades pre-fix)."
    c = Counter(r["binding_constraint"] for r in have)
    lines = [f"*Binding constraint* (n={len(have)} with data):"]
    for k, v in c.most_common():
        lines.append(f"  • {k}: {v} ({v/len(have)*100:.0f}%)")
    # Actionable read for the heat-cap decision
    risk_bound = c.get("risk", 0) / len(have)
    dry = c.get("dry_powder", 0) / len(have)
    if dry >= 0.25:
        lines.append(f"  → ⚠️ {dry*100:.0f}% dry_powder-bound: HEAT CAP is throttling deployment. "
                     "Consider raising MAX_PORTFOLIO_HEAT_PCT further.")
    elif risk_bound >= 0.7:
        lines.append(f"  → {risk_bound*100:.0f}% risk-bound: sizing is driven by stop distance (healthy). "
                     "Heat cap is NOT the bottleneck.")
    return "\n".join(lines)


def render_report(rows, milestone):
    n = len(rows)
    out = []
    out.append(f"📊 *MILESTONE REVIEW — {milestone} closed trades* (actual: {n})")
    out.append("=" * 44)

    # Alpha vs S&P FIRST — the headline "how are we doing" number.
    try:
        import alpha_tracker
        out.append(alpha_tracker.render(rows))
        out.append("")
    except Exception as e:
        out.append(f"_(alpha tracker unavailable: {e})_")

    # Cumulative binding-constraint read — the core of the milestone SIZING
    # decision (heat cap), computed over ALL trades to date.
    out.append(_binding_summary(rows))
    out.append("")

    # Scale-capital readiness — the "should we add money yet?" verdict.
    try:
        import scale_readiness
        out.append(scale_readiness.render(rows))
        out.append("")
    except Exception as e:
        out.append(f"_(scale readiness unavailable: {e})_")

    # Then the full parameter-tuning analysis (tier R-multiples, allocation cap,
    # stop distances, win rate). Reuse performance_review's monthly param review.
    try:
        import performance_review as pr
        out.append(pr.generate_monthly_params())
    except Exception as e:
        out.append(f"_(performance_review param analysis unavailable: {e})_")
    out.append("")
    out.append(f"_Next milestone: {_next_milestone(n) or 'none — all tiers reached'}_")
    return "\n".join(out)


def _next_milestone(n):
    for m in MILESTONES:
        if n < m:
            return m
    return None


def check_and_fire():
    rows = _load_trades()
    n = len(rows)
    state = _load_state()
    fired = set(state.get("fired", []))

    # Any milestone we've now reached but not yet reported?
    newly = [m for m in MILESTONES if n >= m and m not in fired]
    if not newly:
        print(f"[milestone] {n} closed trades — no new milestone "
              f"(fired: {sorted(fired) or 'none'}, next: {_next_milestone(n)})")
        return None

    # Report the HIGHEST newly-crossed milestone (covers skips if many closed at once).
    target = max(newly)
    report = render_report(rows, target)
    print(report)

    fired.update(newly)
    state["fired"] = sorted(fired)
    state["last_count"] = n
    _save_state(state)
    return report


if __name__ == "__main__":
    if "--status" in sys.argv:
        rows = _load_trades()
        st = _load_state()
        print(f"Closed trades: {len(rows)}")
        print(f"Milestones fired: {sorted(st.get('fired', [])) or 'none'}")
        print(f"Next milestone: {_next_milestone(len(rows))}")
    elif "--force" in sys.argv:
        i = sys.argv.index("--force")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else len(_load_trades())
        print(render_report(_load_trades(), n))
    else:
        check_and_fire()
