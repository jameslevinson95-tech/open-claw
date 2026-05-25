#!/bin/bash
# Open Claw — Agent 5 Afternoon Position Monitor + Broker Execution
# Scheduled: 3:30 PM ET, weekdays only
cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Source environment variables
set -a
source .env
set +a

# Log output
LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/monitor_$(date +%Y-%m-%d).log"

echo "=== Afternoon Monitor — $(date) ===" >> "$LOG_FILE"
python3 orchestrator.py monitor >> "$LOG_FILE" 2>&1
echo "=== Done — $(date) ===" >> "$LOG_FILE"
