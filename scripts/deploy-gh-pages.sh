#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

# --- Prerequisites ---
if ! command -v gh &>/dev/null; then
  echo "Error: gh CLI not found." >&2; exit 1
fi
if ! gh auth status 2>&1 | grep -qi "active account.*true"; then
  echo "Error: gh not authenticated." >&2; exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: working tree has uncommitted changes. Commit or stash first." >&2
  exit 1
fi

# --- Step 1: Build Jekyll site ---
echo "==> Installing Jekyll dependencies..."
(cd docs && bundle install --path vendor/bundle --quiet 2>/dev/null)

echo "==> Building Jekyll site..."
(cd docs && bundle exec jekyll build --quiet)

BUILD_DIR="docs/_site"
if [ ! -f "$BUILD_DIR/index.html" ]; then
  echo "Error: build failed (no index.html)" >&2; exit 1
fi

# --- Step 2: Clone gh-pages branch to temp dir and update ---
echo "==> Cloning gh-pages branch..."
WORKTREE=$(mktemp -d)
git clone --branch gh-pages --single-branch "$(git remote get-url origin)" "$WORKTREE" 2>/dev/null

# Remove existing files (keep .git)
cd "$WORKTREE"
find . -maxdepth 1 -not -name '.git' -not -name '.' -exec rm -rf {} + 2>/dev/null

# Copy built site
cp -a "$REPO_ROOT/$BUILD_DIR/." "$WORKTREE"

# Commit and push
git add -A
if git diff --cached --quiet; then
  echo "Nothing changed. Skipping deploy."
  DEPLOYED=false
else
  git commit -m "deploy: $(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  echo "==> Pushing to gh-pages..."
  git push origin gh-pages
  DEPLOYED=true
fi

# --- Step 3: Cleanup ---
cd "$REPO_ROOT"
rm -rf "$WORKTREE"

# --- Step 4: Verify deployment ---
OWNER=$(gh repo view "$(git remote get-url origin)" --json owner --jq '.owner.login')
REPO=$(gh repo view "$(git remote get-url origin)" --json name --jq '.name')
SITE_URL="https://${OWNER}.github.io/${REPO}"

if [ "$DEPLOYED" = "true" ]; then
  echo "==> Waiting for GitHub Pages to build..."
  for i in $(seq 1 12); do
    STATUS=$(gh api "repos/${OWNER}/${REPO}/pages" --jq '.status' 2>/dev/null || echo "building")
    if [ "$STATUS" = "built" ] || [ "$STATUS" = "deployed" ]; then
      break
    fi
    sleep 10
  done
fi

echo "==> Verifying site..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL")
echo "HTTP $HTTP  $SITE_URL"
echo "Deployment complete."
