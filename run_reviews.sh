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

REVIEWS_DIR="output/reviews"
mkdir -p "$REVIEWS_DIR"

MODE="${1:-all}"
TS=$(date +%Y%m%d_%H%M)
LOG="$REVIEWS_DIR/review_${MODE}_${TS}.log"

echo "=== Open Claw ${MODE} Review — $(date) ===" | tee "$LOG"
python3 performance_review.py "$MODE" 2>&1 | tee -a "$LOG"
echo "=== Done — $(date) ===" | tee -a "$LOG"
