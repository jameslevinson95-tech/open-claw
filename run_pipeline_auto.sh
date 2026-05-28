#!/bin/bash
# Open Claw — Automated Morning Pipeline
# Runs the full morning pipeline (Agents 1-4) and executes trades on Robinhood.
# Cron: 55 7 * * 1-5 (7:55 AM ET, weekdays only)
#
# Agent 1 & 3: Gemini fallback (no Anthropic API key needed)
# Agent 2: Gemini 3.1 Pro Preview
# Agent 4: Pure Python (no LLM)
# Execution: Robinhood MCP broker

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/output/logs"
mkdir -p "$LOG_DIR"

DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/pipeline_${DATE}.log"

echo "=============================================" >> "$LOG_FILE"
echo "🌅 Open Claw Automated Pipeline — $DATE" >> "$LOG_FILE"
echo "Started: $(date)" >> "$LOG_FILE"
echo "=============================================" >> "$LOG_FILE"

# Source env vars
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Ensure PATH includes Python and system binaries
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Run the morning pipeline
python3 "$SCRIPT_DIR/orchestrator.py" morning >> "$LOG_FILE" 2>&1
PIPELINE_EXIT=$?

echo "" >> "$LOG_FILE"
echo "Pipeline exit code: $PIPELINE_EXIT" >> "$LOG_FILE"
echo "Finished: $(date)" >> "$LOG_FILE"

# If pipeline succeeded and there are pending orders, execute them
if [ $PIPELINE_EXIT -eq 0 ] && [ -f "$SCRIPT_DIR/output/pending_orders.json" ]; then
    echo "" >> "$LOG_FILE"
    echo "⏰ Executing pending orders..." >> "$LOG_FILE"
    python3 "$SCRIPT_DIR/orchestrator.py" execute >> "$LOG_FILE" 2>&1
    echo "Execution exit code: $?" >> "$LOG_FILE"
fi

exit $PIPELINE_EXIT
