#!/bin/bash
# Open Claw — Trailing-Stop Reinforcement (mechanical-only)
# Scheduled: every 30 min during market hours (10:00–15:30 ET), weekdays only.
# (12 launchd jobs: com.ocplatform.reinforce-HHMM)
# Ratchets trailing stops up + executes mechanical stop-hits. NO thesis review
# (that stays on the 3:30 PM daily monitor). Real-time pricing via Tiingo.
cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/hourly_reinforce_$(date +%Y-%m-%d).log"

echo "=== Hourly Reinforce — $(date) ===" >> "$LOG_FILE"
# Pin to Homebrew python3 (3.14) — same interpreter the morning pipeline uses.
# It has all live-path deps (yfinance, filelock, pandas, finvizfinance, dotenv).
# System /usr/bin/python3 (3.9.6) lost its deps and was crashing on `import yfinance`
# every 30-min run (ModuleNotFoundError), silently killing stop reinforcement.
# The live path calls Gemini via REST (requests.post), so google.generativeai
# SDK is NOT required. (interpreter re-pinned 2026-07-29)
/opt/homebrew/bin/python3 orchestrator.py hourly >> "$LOG_FILE" 2>&1
echo "=== Done — $(date) ===" >> "$LOG_FILE"
