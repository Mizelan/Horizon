#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

usage() {
  echo "Usage: $(basename "$0") [OPTIONS]"
  echo ""
  echo "Run Horizon daily summary and deploy to GitHub Pages."
  echo ""
  echo "Options:"
  echo "  --hours N       Fetch from last N hours (default: 24)"
  echo "  --date YYYY-MM-DD  Single date to process"
  echo "  --from YYYY-MM-DD  Start date (inclusive)"
  echo "  --to YYYY-MM-DD    End date (inclusive, default: today)"
  echo "  --deploy-only    Only deploy (skip horizon run)"
  echo "  -h, --help       Show this help"
  echo ""
  echo "Examples:"
  echo "  $(basename "$0")                          # Today + deploy"
  echo "  $(basename "$0") --hours 48               # Last 48h + deploy"
  echo "  $(basename "$0") --date 2026-05-08        # Single backdate + deploy"
  echo "  $(basename "$0") --from 2026-05-01 --to 2026-05-05  # Range + deploy"
  echo "  $(basename "$0") --deploy-only            # Deploy existing posts"
  exit 0
}

# --- Parse args ---
HOURS=""
DATE=""
FROM=""
TO=""
DEPLOY_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hours) HOURS="$2"; shift 2 ;;
    --date) DATE="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --deploy-only) DEPLOY_ONLY=true; shift ;;
    -h|--help) usage ;;
    *) echo "Error: unknown option $1"; usage ;;
  esac
done

# --- Prerequisites ---
if ! command -v gh &>/dev/null; then echo "Error: gh CLI not found." >&2; exit 1; fi
if ! gh auth status 2>&1 | grep -qi "active account.*true"; then
  echo "Error: gh not authenticated." >&2; exit 1
fi
if [ -n "$(git status --porcelain)" ] && [ "$DEPLOY_ONLY" = false ]; then
  echo "Error: working tree has uncommitted changes. Commit or stash first." >&2
  exit 1
fi
export OLLAMA_API_KEY="${OLLAMA_API_KEY:-ollama}"

# --- Resolve date range ---
today() { date -u +%Y-%m-%d; }
date_to_epoch() { date -j -u -f "%Y-%m-%d %H:%M:%S" "$1 00:00:00" +%s 2>/dev/null; }

TODAY=$(today)

# Read current post schema version from orchestrator source
POST_SCHEMA_VERSION=$(grep '^POST_SCHEMA_VERSION' src/orchestrator.py | grep -o '[0-9]\+' | head -1)
POST_SCHEMA_VERSION="${POST_SCHEMA_VERSION:-1}"

run_single() {
  local target_date="$1"
  local hours="$2"
  local post_file="docs/_posts/${target_date}-summary-ko.md"

  if [ -f "$post_file" ]; then
    # Check if existing post has matching schema version
    local existing_ver
    existing_ver=$(grep 'post_schema_version:' "$post_file" | grep -o '[0-9]\+' | head -1)
    if [ "$existing_ver" = "$POST_SCHEMA_VERSION" ]; then
      echo "  ⏭️  $post_file already exists (schema v$existing_ver), skipping"
      return 0
    fi
    echo "  🔄  $post_file schema v${existing_ver:-0} → v$POST_SCHEMA_VERSION, regenerating"
  fi

  echo "  🗓️  $target_date (--hours $hours)..."
  if ! uv run horizon --hours "$hours" --date "$target_date" 2>&1; then
    echo "  ⚠️  Failed for $target_date, continuing..." >&2
    return 1
  fi
  return 0
}

deploy() {
  echo ""
  # Commit any pending changes before deploying
  if [ -n "$(git status --porcelain)" ]; then
    echo "  📝 Committing changes..."
    git add -A
    git commit -m "chore: auto-commit before deploy" 2>/dev/null || true
    git push origin main 2>/dev/null || true
  fi
  echo "=========================================="
  echo "🚀  Deploying to GitHub Pages..."
  echo "=========================================="
  bash scripts/deploy-gh-pages.sh
}

# --- Main ---
if [ "$DEPLOY_ONLY" = true ]; then
  deploy
  exit 0
fi

if [ -n "$FROM" ]; then
  # --- Date range mode ---
  TO="${TO:-$TODAY}"
  echo "📅 Processing range: $FROM → $TO"
  echo ""

  from_epoch=$(date_to_epoch "$FROM")
  to_epoch=$(date_to_epoch "$TO")
  now_epoch=$(date -u +%s)

  if [ -z "$from_epoch" ] || [ -z "$to_epoch" ]; then
    echo "Error: invalid date format. Use YYYY-MM-DD." >&2; exit 1
  fi
  if [ "$to_epoch" -lt "$from_epoch" ]; then
    echo "Error: --to must be >= --from" >&2; exit 1
  fi

  current="$from_epoch"
  failures=0

  while [ "$current" -le "$to_epoch" ]; do
    day=$(date -j -u -f "%s" "$current" +%Y-%m-%d 2>/dev/null)
    day_start=$(date -j -u -f "%Y-%m-%d %H:%M:%S" "$day 00:00:00" +%s 2>/dev/null)
    delta_hours=$(( (now_epoch - day_start) / 3600 + 1 ))
    [ "$delta_hours" -lt 24 ] && delta_hours=24

    run_single "$day" "$delta_hours" || failures=$((failures + 1))
    current=$((current + 86400))
  done

  echo ""
  echo "✅ Range complete ($failures failures)"
  deploy

elif [ -n "$DATE" ]; then
  # --- Single date mode ---
  echo "📅 Processing date: $DATE"
  date_epoch=$(date_to_epoch "$DATE")
  if [ -z "$date_epoch" ]; then
    echo "Error: invalid date format." >&2; exit 1
  fi
  delta_hours=$(( ($(date -u +%s) - date_epoch) / 3600 + 1 ))
  [ "$delta_hours" -lt 24 ] && delta_hours=24

  run_single "$DATE" "$delta_hours" || true
  deploy

else
  # --- Default mode (today) ---
  echo "📅 Processing today ($TODAY)"
  HOURS="${HOURS:-24}"
  run_single "$TODAY" "$HOURS" || true
  deploy
fi
