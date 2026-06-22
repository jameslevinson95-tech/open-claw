#!/bin/bash
# Open Claw — Trailing-Stop Reinforcement (mechanical-only)
# Scheduled: every 30 min during market hours (10:00–15:30 ET), weekdays only.
# (12 launchd jobs: com.ocplatform.reinforce-HHMM)
# Ratchets trailing stops up + executes mechanical stop-hits. NO thesis review
# (that stays on the 3:30 PM daily monitor). Real-time pricing via Tiingo.
cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/hourly_reinforce_$(date +%Y-%m-%d).log"

echo "=== Hourly Reinforce — $(date) ===" >> "$LOG_FILE"
python3 orchestrator.py hourly >> "$LOG_FILE" 2>&1
echo "=== Done — $(date) ===" >> "$LOG_FILE"
