#!/bin/bash
# run_daemon.sh — Auto-restarting execution daemon wrapper
#
# Runs the execution reconciliation daemon with automatic restart on crash.
# Writes heartbeat to output/daemon_hb_signal.txt every cycle.
# The orchestrator checks this heartbeat before routing trades.
#
# Usage:
#   bash run_daemon.sh          # Foreground
#   nohup bash run_daemon.sh &  # Background
#   tmux new -d -s daemon 'bash run_daemon.sh'  # tmux session

cd "$(dirname "$0")"

echo "═══════════════════════════════════════════"
echo "  EXECUTION DAEMON — AUTO-RESTART WRAPPER"
echo "  Press Ctrl+C to stop"
echo "═══════════════════════════════════════════"

while true; do
    echo "[$(date)] Starting execution daemon..."
    python3 run_execution_daemon.py
    EXIT_CODE=$?
    echo "[$(date)] Daemon exited with code $EXIT_CODE. Restarting in 5s..."
    sleep 5
done
