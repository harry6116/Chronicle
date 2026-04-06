#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SNAPSHOT_DIR="/Users/michaelsmac/Documents/Chronicle/artifacts/public_repo_stage/Chronicle"
DEFAULT_PUBLIC_REPO_DIR="/Users/michaelsmac/Documents/Chronicle Public Repo"

clear
echo "--- CHRONICLE PUBLIC REPO PUSH ---"
echo "This script syncs ONLY the curated public snapshot into a local clone of the public repo."
echo "It does NOT push the whole private/canonical Chronicle tree."
echo ""

if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  echo "Public snapshot not found."
  echo "Run Prepare_Public_Repo.command first."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Enter the full path to your LOCAL clone of the public GitHub repository:"
echo "Press Enter to use the default:"
echo "  $DEFAULT_PUBLIC_REPO_DIR"
read -r PUBLIC_REPO_DIR

if [[ -z "${PUBLIC_REPO_DIR// }" ]]; then
  PUBLIC_REPO_DIR="$DEFAULT_PUBLIC_REPO_DIR"
fi

if [[ ! -d "$PUBLIC_REPO_DIR/.git" ]]; then
  echo "ERROR: That path is not a git clone:"
  echo "  $PUBLIC_REPO_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

cd "$PUBLIC_REPO_DIR"

CURRENT_BRANCH="$(git branch --show-current)"
REMOTE_NAME="origin"

if [[ -z "${CURRENT_BRANCH// }" ]]; then
  echo "ERROR: Detached HEAD state detected in the public repo clone."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "Public repo clone: $PUBLIC_REPO_DIR"
echo "Branch: $CURRENT_BRANCH"
echo "Remote: $(git remote get-url "$REMOTE_NAME" 2>/dev/null || echo "$REMOTE_NAME not configured")"
echo ""
echo "This will replace the full working tree contents with the staged public snapshot."
echo "Your .git folder will be preserved."
echo ""
read -r -p "Type PUBLIC to continue: " confirm

if [[ "$confirm" != "PUBLIC" ]]; then
  echo "Cancelled."
  read -r -p "Press Enter to close..."
  exit 0
fi

find "$PUBLIC_REPO_DIR" -mindepth 1 -maxdepth 1 \
  ! -name '.git' \
  -exec rm -rf {} +

rsync -a --delete --exclude '.git/' "$SNAPSHOT_DIR"/ "$PUBLIC_REPO_DIR"/

git add -A

if git diff --cached --quiet; then
  echo "No public snapshot changes to commit."
  read -r -p "Press Enter to close..."
  exit 0
fi

echo ""
echo "Enter a public repo commit summary (e.g., Public repo refresh for 1.0.0):"
read -r commit_message

if [[ -z "${commit_message// }" ]]; then
  echo "ERROR: Commit summary cannot be empty."
  read -r -p "Press Enter to close..."
  exit 1
fi

git commit -m "$commit_message"

if ! git push -u "$REMOTE_NAME" "$CURRENT_BRANCH"; then
  echo ""
  echo "ERROR: Push failed."
  echo "Possible causes:"
  echo "- GitHub auth is not configured for this machine"
  echo "- the branch is protected"
  echo "- repo rules or Actions restrictions are blocking direct pushes"
  echo "- the local clone points at the wrong remote"
  echo ""
  echo "Check:"
  echo "  git remote -v"
  echo "  git status"
  echo "  git branch -vv"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "SUCCESS: Only the staged public snapshot was pushed."
read -r -p "Press Enter to close..."
