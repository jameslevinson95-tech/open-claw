#!/bin/bash
# run_flash_daemon.sh — Intraday flash-crash safety net loop
# Polls every ~7 min during market hours. KeepAlive-friendly (this script stays up).
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
set -a
source .env 2>/dev/null
set +a

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/flash_daemon_$(date +%Y-%m-%d).log"

echo "=== Flash daemon wrapper started $(date) ===" >> "$LOG_FILE"
while true; do
  python3 flash_crash_daemon.py >> "$LOG_FILE" 2>&1
  sleep 420   # ~7 min between polls
done
