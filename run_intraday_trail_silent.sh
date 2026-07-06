#!/bin/bash
# run_intraday_trail_silent.sh — Command-payload wrapper for the 15-min intraday
# trailing-stop ratchet. Runs the ratchet directly on the Gateway host (no model
# session), so it can't hit EmbeddedAttemptSessionTakeoverError like the old
# agentTurn cron did (2026-07-06). Stays SILENT: prints nothing unless a stop
# actually ratcheted, in which case it prints a one-line-per-ticker summary that
# cron's `announce` delivery posts to #trading. The 4 PM EOD digest remains the
# single scheduled daily summary; this only speaks on a real applied move.
cd /Users/chris/code/trading-pipeline || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

# Pin to system python3 (3.9.6) — has all deps (filelock, generativeai, etc).
OUT="$(/usr/bin/python3 intraday_trail.py --json 2>/dev/null)"

# Parse the JSON and decide whether to emit anything. Silence = no post.
/usr/bin/python3 - "$OUT" <<'PY'
import json, sys
raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    d = json.loads(raw)
except Exception:
    # Bad/empty output — stay silent (don't spam the channel on a hiccup).
    sys.exit(0)

if d.get("status") != "ok":
    sys.exit(0)

applied = [t for t in d.get("tightened", []) if t.get("applied")]
if not applied:
    sys.exit(0)  # nothing really moved — silent

lines = ["🔒 Intraday stop ratchet:"]
for t in applied:
    lines.append(
        f"{t['ticker']} stop ${t.get('prev_stop')} → ${t['new_stop']} "
        f"(px ${t.get('current_price')}, {t.get('pnl_pct')}%)"
    )
print("\n".join(lines))
PY
