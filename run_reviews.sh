#!/bin/bash
# Open Claw — Performance Review Runner
# Schedule: Weekly pulse (Fridays), Biweekly deep (1st + 15th), Monthly params (1st)
#
# Usage:
#   ./run_reviews.sh weekly      # Friday weekly pulse
#   ./run_reviews.sh biweekly    # Biweekly deep review + data source audit
#   ./run_reviews.sh monthly     # Monthly parameter review
#   ./run_reviews.sh all         # All three

cd /Users/chris/code/trading-pipeline
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

set -a
source .env 2>/dev/null
set +a

# Select a python3 that has the review dependencies (pandas/numpy).
# The homebrew python3 on this machine lacks pandas; /usr/bin/python3 has it.
PYTHON=""
for candidate in /usr/bin/python3 python3 /opt/homebrew/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import pandas, numpy" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: no python3 with pandas/numpy found" >&2
    exit 1
fi

REVIEWS_DIR="output/reviews"
mkdir -p "$REVIEWS_DIR"

MODE="${1:-all}"
TS=$(date +%Y%m%d_%H%M)
LOG="$REVIEWS_DIR/review_${MODE}_${TS}.log"

echo "=== Open Claw ${MODE} Review — $(date) ===" | tee "$LOG"
echo "Using python: $PYTHON" | tee -a "$LOG"
"$PYTHON" performance_review.py "$MODE" 2>&1 | tee -a "$LOG"
echo "=== Done — $(date) ===" | tee -a "$LOG"
