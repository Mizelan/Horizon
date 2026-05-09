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

# --- Step 2: Deploy to gh-pages via worktree ---
echo "==> Setting up gh-pages worktree..."
git fetch origin gh-pages 2>/dev/null || true
git branch -D gh-pages 2>/dev/null || true
WORKTREE=$(mktemp -d)
git worktree add --detach "$WORKTREE" origin/gh-pages

# Remove existing files (keep .git)
find "$WORKTREE" -maxdepth 1 -not -name '.git' -not -name "$WORKTREE" -exec rm -rf {} + 2>/dev/null

# Copy built site (dotfiles included via trailing "/.")
cp -a "$BUILD_DIR/." "$WORKTREE"

# Commit and push
cd "$WORKTREE"
git add -A
if git diff --cached --quiet; then
  echo "Nothing changed. Skipping deploy."
  DEPLOYED=false
else
  git commit -m "deploy: $(git -C "$REPO_ROOT" rev-parse --short HEAD)"
  echo "==> Pushing to gh-pages..."
  git push origin HEAD:gh-pages --force
  DEPLOYED=true
fi

# --- Step 3: Cleanup ---
cd "$REPO_ROOT"
git worktree remove --force "$WORKTREE" 2>/dev/null || rm -rf "$WORKTREE"

# --- Step 4: Verify deployment ---
OWNER=$(gh repo view --json owner --jq '.owner.login')
REPO=$(gh repo view --json name --jq '.name')
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
