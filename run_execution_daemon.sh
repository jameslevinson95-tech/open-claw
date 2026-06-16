#!/bin/bash
# run_execution_daemon.sh — Execution engine reconciliation loop wrapper.
# The Python daemon runs its own internal 15s reconcile loop; this wrapper just
# keeps it alive (restarts on crash). KeepAlive-friendly.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
set -a
source .env 2>/dev/null
set +a

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/execution_daemon_$(date +%Y-%m-%d).log"

# Pin to the system Python that actually has the deps (filelock, etc.). The
# Homebrew python3 on PATH is missing filelock, which was crash-looping the daemon.
PY=/usr/bin/python3

echo "=== Execution daemon wrapper started $(date) (py=$PY) ===" >> "$LOG_FILE"
while true; do
  "$PY" run_execution_daemon.py >> "$LOG_FILE" 2>&1
  echo "=== daemon exited rc=$? at $(date); restarting in 10s ===" >> "$LOG_FILE"
  sleep 10
done
