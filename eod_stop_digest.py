#!/usr/bin/env python3
"""
End-of-Day Stop Reinforcement Digest.

Runs at 4:00 PM ET. Parses the day's reinforcement log (all 12 half-hourly
runs) plus the current portfolio_state.json (HWM stops) and produces ONE clean
summary of every stop movement during the day, then posts it to Slack #trading.

Pure read-only: places no orders, touches no broker. Safe to run anytime.
"""
import json
import os
import re
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(BASE, "output", "portfolio_state.json")
LOG_PATH = os.path.join(BASE, "output", "logs", f"hourly_reinforce_{datetime.now():%Y-%m-%d}.log")


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def parse_log_movements(path: str) -> dict:
    """
    Scan the day's reinforce log for HWM stop updates.
    Lines look like: '... [HWM updated: $12.34 -> $13.00]'
    Returns {ticker: {"first": x, "last": y, "n_updates": k, "notes": [...]}}.
    """
    moves = {}
    if not os.path.exists(path):
        return moves
    # Capture e.g. "BAC: ... [HWM updated: $50.00 → $51.20]"
    pat = re.compile(r"([A-Z]{1,5}):.*?HWM updated:\s*\$([0-9.]+)\s*[→-]+>?\s*\$([0-9.]+)")
    with open(path, errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if not m:
                continue
            t, old, new = m.group(1), float(m.group(2)), float(m.group(3))
            d = moves.setdefault(t, {"first": old, "last": new, "n": 0})
            d["last"] = new
            d["n"] += 1
    return moves


def count_runs(path: str) -> int:
    if not os.path.exists(path):
        return 0
    n = 0
    with open(path, errors="ignore") as f:
        for line in f:
            if line.startswith("=== Hourly Reinforce —"):
                n += 1
    return n


def build_digest() -> str:
    state = load_state()
    moves = parse_log_movements(LOG_PATH)
    runs = count_runs(LOG_PATH)
    today = f"{datetime.now():%a %b %d, %Y}"

    lines = [f"*📋 EOD Stop Reinforcement Digest — {today}*"]
    lines.append(f"_{runs} reinforcement runs today (every 30 min, 10:00–15:30 ET)_")
    lines.append("")

    if moves:
        lines.append("*Stops that moved up today:*")
        for t in sorted(moves):
            mv = moves[t]
            lines.append(
                f"• *{t}*: ${mv['first']:.2f} → *${mv['last']:.2f}* "
                f"({mv['n']} ratchet{'s' if mv['n'] != 1 else ''})"
            )
    else:
        lines.append("No stop movements today (no position gained enough to trigger a tighten).")

    lines.append("")
    lines.append("*Current live stops (high-water-mark):*")
    if state:
        for t in sorted(state):
            s = state[t]
            stop = s.get("hwm_stop", 0)
            scaled = s.get("scaled_fraction", 0)
            tag = f"  _({int(scaled*100)}% scaled out)_" if scaled else ""
            lines.append(f"• {t}: ${stop:.2f}{tag}")
    else:
        lines.append("_(no portfolio state found)_")

    return "\n".join(lines)


if __name__ == "__main__":
    digest = build_digest()
    # Print to stdout (captured in log). Slack delivery is handled by the
    # runner wrapper via the OpenClaw message path / webhook if configured.
    print(digest)
