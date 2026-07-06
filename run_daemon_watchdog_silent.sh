#!/bin/bash
# run_daemon_watchdog_silent.sh — Command-payload wrapper for the every-3-min
# execution-daemon watchdog. Runs directly on the Gateway host (no model
# session), which eliminates the EmbeddedAttemptSessionTakeoverError collisions
# this job was causing every 3 min against other Open Claw isolated crons
# (open-claw-monitor at 15:30, open-claw-morning, intraday-trail) — see the
# 2026-07-06 session-file race. Silent on OK (empty stdout = no post); on ALERT
# it prints the alert text, which cron's `announce` delivery posts to #trading.
cd /Users/chris/code/trading-pipeline || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

OUT="$(/usr/bin/python3 daemon_watchdog.py --alert-gate 2>/dev/null)"

# OK / empty -> stay silent. "ALERT <text>" -> emit <text> for cron to post.
case "$OUT" in
  ALERT\ *)
    printf '%s\n' "${OUT#ALERT }"
    ;;
  *)
    # healthy or within-cooldown or empty — post nothing
    :
    ;;
esac
