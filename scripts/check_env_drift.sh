#!/usr/bin/env bash
# check_env_drift.sh
# Loud health check for the three failure modes that let the codebase rot:
#   1. Unpushed commits (per remote)
#   2. Dirty working tree (uncommitted changes)
#   3. .env drift — keys in .env.example (or referenced in code) missing from .env
#
# Exit 0 = all clean.  Exit 1 = drift detected (prints a report suitable for a cron alert).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PROBLEMS=()
INFO=()

# --- 1. Unpushed commits, per remote ---
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git fetch --quiet --all 2>/dev/null || true
for remote in $(git remote); do
  if git rev-parse --verify --quiet "$remote/$BRANCH" >/dev/null; then
    AHEAD="$(git rev-list --count "$remote/$BRANCH..$BRANCH" 2>/dev/null || echo 0)"
    [ "$AHEAD" -gt 0 ] && PROBLEMS+=("🔴 $AHEAD unpushed commit(s) to $remote/$BRANCH  (fix: git push $remote $BRANCH)")
  else
    PROBLEMS+=("🔴 branch $BRANCH does not exist on $remote yet  (fix: git push -u $remote $BRANCH)")
  fi
done

# --- 2. Dirty working tree ---
if [ -n "$(git status --porcelain)" ]; then
  DIRTY="$(git status --porcelain | wc -l | tr -d ' ')"
  PROBLEMS+=("🟡 $DIRTY uncommitted change(s) in working tree  (fix: git add -A && git commit)")
fi

# --- 3. .env drift ---
if [ -f .env ] && [ -f .env.example ]; then
  # keys the code actually references
  CODE_KEYS="$(grep -rhoE "os\.(getenv|environ(\.get)?)\(?\[?['\"][A-Z_]+['\"]" *.py 2>/dev/null | grep -oE "[A-Z_]{4,}" | sort -u)"
  # keys declared in the contract
  EXAMPLE_KEYS="$(grep -oE '^[A-Z_]+=' .env.example | sed 's/=//' | sort -u)"
  # keys present in the real env
  ENV_KEYS="$(grep -oE '^[A-Z_]+=' .env | sed 's/=//' | sort -u)"

  # code references a key that's NOT declared in .env.example -> contract is stale
  while IFS= read -r k; do
    [ -z "$k" ] && continue
    if ! grep -qx "$k" <<< "$EXAMPLE_KEYS"; then
      PROBLEMS+=("🟠 $k used in code but missing from .env.example  (fix: add $k= to .env.example)")
    fi
  done <<< "$CODE_KEYS"

  # Keys that are optional (have code defaults) or supplied out-of-band (proxy/launchd).
  # Missing these is informational, not a failure.
  OPTIONAL_KEYS="ANTHROPIC_API_KEY PLANNING_FLOOR_EXPIRY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID SCHWAB_APP_KEY SCHWAB_APP_SECRET SCHWAB_CALLBACK_URL"

  # contract declares a key with no value in the real .env -> config incomplete
  while IFS= read -r k; do
    [ -z "$k" ] && continue
    if ! grep -qx "$k" <<< "$ENV_KEYS"; then
      if grep -qw "$k" <<< "$OPTIONAL_KEYS"; then
        INFO+=("ℹ️  $k not set in .env (optional / has default / proxy-supplied)")
      else
        PROBLEMS+=("🟠 REQUIRED key $k in .env.example but absent from .env  (fix: add $k=<value> to .env)")
      fi
    fi
  done <<< "$EXAMPLE_KEYS"
fi

# --- report ---
if [ ${#PROBLEMS[@]} -eq 0 ]; then
  echo "✅ Open Claw repo hygiene: clean (pushed, committed, required env in sync)"
  for i in "${INFO[@]:-}"; do [ -n "$i" ] && echo "  $i"; done
  exit 0
fi

echo "⚠️  Open Claw repo drift detected ($(date '+%Y-%m-%d %H:%M %Z')):"
for p in "${PROBLEMS[@]}"; do echo "  - $p"; done
for i in "${INFO[@]:-}"; do [ -n "$i" ] && echo "  - $i"; done
exit 1
