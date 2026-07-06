#!/usr/bin/env bash
# generate_codebase_dump.sh
# Regenerates OPEN_CLAW_FULL_CODEBASE_<DATE>.md from current HEAD.
# Concatenates all tracked root-level .py source into a single audit-ready markdown dump.
# Called automatically by the post-commit hook so the public audit dump NEVER goes stale.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DATE_TAG="$(date +%Y%m%d)"
DATE_HUMAN="$(date '+%Y-%m-%d %H:%M %Z')"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo 'uncommitted')"
OUT="OPEN_CLAW_FULL_CODEBASE_${DATE_TAG}.md"

# Root-level tracked .py only (matches the historical dump format: no deprecated/, robinhood-mcp/, output/).
FILES="$(git ls-files -- '*.py' | grep -vE '/' | grep -viE '(^|/)(test_|.*_deprecated)' | sort)"

{
  echo "# Open Claw — Full Codebase Dump (${DATE_HUMAN})"
  echo ""
  echo "Complete concatenation of all Python source for audit. Commit: ${COMMIT}"
  echo ""
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    echo ""
    printf '%.0s=' {1..80}; echo ""
    echo "FILE: ${f}"
    printf '%.0s=' {1..80}; echo ""
    echo '```python'
    cat "$f"
    echo '```'
  done <<< "$FILES"
} > "$OUT"

# Prune older dated dumps so we don't accumulate one per day — keep only the newest.
for old in OPEN_CLAW_FULL_CODEBASE_*.md; do
  [ "$old" = "$OUT" ] && continue
  git rm -q --cached "$old" 2>/dev/null || true
  rm -f "$old"
done

echo "[dump] wrote $OUT ($(wc -l < "$OUT") lines, $(echo "$FILES" | grep -c . ) files, commit $COMMIT)"
