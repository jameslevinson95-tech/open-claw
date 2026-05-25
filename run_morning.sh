#!/bin/bash
# Open Claw — Morning Entry Pipeline (Agents 1-4 + Broker Execution)
# Scheduled: 8:00 AM ET, weekdays only
cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Source environment variables
set -a
source .env
set +a

# Log output
LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/morning_$(date +%Y-%m-%d).log"

echo "=== Morning Pipeline — $(date) ===" >> "$LOG_FILE"
python3 orchestrator.py morning >> "$LOG_FILE" 2>&1
echo "=== Done — $(date) ===" >> "$LOG_FILE"
