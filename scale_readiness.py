#!/usr/bin/env python3
"""
Scale Readiness — should we add capital to the Open Claw pipeline yet?

Jamie (2026-07-12): "if we're beating the S&P by X% for C months, when do I
start increasing capital?"

The honest answer isn't "when returns are good" — a few good months can be
luck, or un-scalable alpha. The gate is: is the edge REAL, REPEATABLE, and
does it survive more size. This evaluates four gates against the live journal.
ALL must pass before scaling is advisable.

  GATE 1 — SAMPLE SIZE      ≥100 closed trades (statistical confidence).
                            Soft-pass at ≥50 (directional only).
  GATE 2 — CONSISTENCY      ≥4 consecutive months of positive alpha vs SPY.
                            (Steady beats magnitude — one huge month ≠ edge.)
  GATE 3 — RISK-ADJUSTED    Max drawdown within tolerance AND positive
                            expectancy (avg R > 0). Beating SPY on 3x vol
                            isn't alpha, it's leverage.
  GATE 4 — REAL ALPHA       SPY correlation < 0.7 (not just leveraged beta)
                            AND cumulative alpha is actually positive.

If all pass → recommend scaling IN STEPS (never double in one move), then
re-confirm the edge held at the larger size before the next step.

USAGE
    python3 scale_readiness.py            # verdict + gate breakdown
    python3 scale_readiness.py --json
"""

import json
import sys
from pathlib import Path

JOURNAL_PATH = Path("journal/trades.csv")

# ── Tunable thresholds ──────────────────────────────────────────────
MIN_TRADES_HARD = 100          # full statistical confidence
MIN_TRADES_SOFT = 50           # directional-only floor
MIN_CONSEC_ALPHA_MONTHS = 4    # consistency requirement
MAX_DRAWDOWN_R = 8.0           # max peak-to-trough drawdown in R (tolerance)
MAX_SPY_CORRELATION = 0.70     # above this = it's beta, not alpha


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _load():
    if not JOURNAL_PATH.exists():
        return []
    import csv
    with JOURNAL_PATH.open() as f:
        return [r for r in csv.DictReader(f) if r.get("pnl_pct") not in (None, "")]


def _max_drawdown_R(r_multiples):
    """Peak-to-trough drawdown of the cumulative-R equity curve, in R units."""
    peak = 0.0
    cum = 0.0
    max_dd = 0.0
    for r in r_multiples:
        cum += r
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    return round(max_dd, 2)


def _correlation(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    if vx == 0 or vy == 0:
        return None
    return round(cov / (vx * vy), 2)


def evaluate(rows):
    n = len(rows)
    if n == 0:
        return {"trades": 0, "ready": False, "note": "No closed trades yet."}

    # Pull alpha analysis (reuse the tracker for monthly consistency).
    import alpha_tracker
    alpha = alpha_tracker.compute(rows)

    r_mults = [_f(r.get("r_multiple")) for r in rows]
    strat = [_f(r.get("pnl_pct")) for r in rows]
    spy = [_f(r.get("spx_change_over_hold_pct")) for r in rows]

    avg_r = sum(r_mults) / n if n else 0
    max_dd = _max_drawdown_R(r_mults)
    corr = _correlation(strat, spy)
    consec = alpha.get("consecutive_months_beating_spy", 0)
    cum_alpha = alpha.get("cum_alpha_pct", 0)

    # ── Gate evaluations ──
    g1_pass = n >= MIN_TRADES_HARD
    g1_soft = n >= MIN_TRADES_SOFT
    g2_pass = consec >= MIN_CONSEC_ALPHA_MONTHS
    g3_pass = (max_dd <= MAX_DRAWDOWN_R) and (avg_r > 0)
    g4_pass = (corr is None or corr < MAX_SPY_CORRELATION) and cum_alpha > 0

    gates = [
        {
            "gate": "1. Sample size",
            "pass": g1_pass,
            "detail": f"{n} trades (need {MIN_TRADES_HARD}; soft floor {MIN_TRADES_SOFT})"
                      + ("" if g1_pass else (" — SOFT ok" if g1_soft else "")),
        },
        {
            "gate": "2. Consistency",
            "pass": g2_pass,
            "detail": f"{consec} consecutive months of + alpha (need {MIN_CONSEC_ALPHA_MONTHS})",
        },
        {
            "gate": "3. Risk-adjusted",
            "pass": g3_pass,
            "detail": f"max DD {max_dd}R (limit {MAX_DRAWDOWN_R}R), avg {avg_r:+.2f}R "
                      f"({'positive' if avg_r > 0 else 'NEGATIVE'} expectancy)",
        },
        {
            "gate": "4. Real alpha (not beta)",
            "pass": g4_pass,
            "detail": f"SPY corr {corr if corr is not None else 'n/a'} "
                      f"(limit <{MAX_SPY_CORRELATION}), cum alpha {cum_alpha:+.1f}%",
        },
    ]

    ready = all(g["pass"] for g in gates)

    # Next-blocker guidance.
    blockers = [g["gate"] for g in gates if not g["pass"]]
    if ready:
        verdict = "✅ READY to consider scaling capital — all gates passed."
        guidance = ("Scale IN STEPS (e.g. +50%, not 2x). After each step run ~20-30 "
                    "more trades and confirm the edge HELD at the larger size (watch "
                    "fill quality / slippage) before the next step.")
    else:
        verdict = f"❌ NOT YET — {len(blockers)} gate(s) unmet: {', '.join(blockers)}"
        # Most actionable single next step.
        if not g1_pass and g1_soft:
            guidance = f"Closest blocker: sample size. Have {n}, want {MIN_TRADES_HARD}. Keep trading."
        elif not g1_pass:
            guidance = f"Need {MIN_TRADES_SOFT - n} more trades just to reach the soft floor."
        elif not g2_pass:
            guidance = f"Need {MIN_CONSEC_ALPHA_MONTHS - consec} more consecutive +alpha month(s)."
        elif not g3_pass:
            guidance = ("Risk profile too hot — drawdown or expectancy failed. Do NOT add "
                        "capital to a book that isn't risk-clean.")
        else:
            guidance = "Alpha looks like beta (high SPY correlation) — adding size just leverages the index."

    return {
        "trades": n,
        "ready": ready,
        "verdict": verdict,
        "guidance": guidance,
        "gates": gates,
        "metrics": {
            "avg_r": round(avg_r, 3),
            "max_drawdown_R": max_dd,
            "spy_correlation": corr,
            "consecutive_alpha_months": consec,
            "cum_alpha_pct": cum_alpha,
        },
    }


def render(rows):
    e = evaluate(rows)
    if e.get("trades", 0) == 0:
        return "🎯 *SCALE READINESS* — no closed trades yet."
    lines = [
        "🎯 *SCALE-CAPITAL READINESS*",
        "=" * 40,
        e["verdict"],
        "",
    ]
    for g in e["gates"]:
        mark = "✅" if g["pass"] else "❌"
        lines.append(f"  {mark} {g['gate']}: {g['detail']}")
    lines.append("")
    lines.append(f"_{e['guidance']}_")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = _load()
    if "--json" in sys.argv:
        print(json.dumps(evaluate(rows), indent=2))
    else:
        print(render(rows))
