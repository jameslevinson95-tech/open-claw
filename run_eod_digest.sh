#!/bin/bash
# Open Claw — EOD Stop Reinforcement Digest
# Scheduled: 16:00 ET weekdays (after the 3:30 monitor + final reinforce run).
# Generates the digest and writes it to a file the agent turn will post to #trading.
cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

LOG_DIR="output/logs"
mkdir -p "$LOG_DIR"
OUT="output/eod_digest_$(date +%Y-%m-%d).txt"

python3 eod_stop_digest.py > "$OUT" 2>> "$LOG_DIR/eod_digest.err.log"
echo "$(date) wrote $OUT" >> "$LOG_DIR/eod_digest.log"
cat "$OUT"
