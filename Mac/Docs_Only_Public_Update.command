#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SNAPSHOT_DIR="$ROOT_DIR/artifacts/public_repo_stage/Chronicle"
DEFAULT_PUBLIC_REPO_DIR="/Users/michaelsmac/Documents/Chronicle Public Repo"

clear
echo "--- CHRONICLE DOCS-ONLY PUBLIC UPDATE ---"
echo "This script is for public-facing document updates and other minor rollouts."
echo "It rebuilds the curated public snapshot, commits it, and pushes it."
echo "It does NOT publish or update GitHub release assets."
echo "It does NOT touch the Mac or Windows ZIP files."
echo ""

if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: Chronicle root is not a git repository."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Preparing fresh public snapshot from:"
echo "  $ROOT_DIR"
echo ""
python3 "$ROOT_DIR/tools/prepare_public_repo_snapshot.py" --clean

if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  echo "ERROR: Public snapshot was not created:"
  echo "  $SNAPSHOT_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
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
echo "Snapshot source: $SNAPSHOT_DIR"
echo ""
echo "This will replace the public repo working tree with the newly staged public snapshot."
echo "Use this only for docs, README, policy, and other minor public rollout changes."
echo "To continue, type DOCS in ALL CAPITALS."
read -r -p "Type DOCS to continue: " confirm

if [[ "$confirm" != "DOCS" ]]; then
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
  echo "No docs/minor public snapshot changes to commit."
  read -r -p "Press Enter to close..."
  exit 0
fi

echo ""
echo "Enter a public repo commit summary for this docs/minor rollout:"
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
  echo "Check:"
  echo "  git remote -v"
  echo "  git status"
  echo "  git branch -vv"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "SUCCESS: Docs/minor public update pushed."
read -r -p "Press Enter to close..."
