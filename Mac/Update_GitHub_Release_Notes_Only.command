#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PUBLIC_REPO_DIR="/Users/michaelsmac/Documents/Chronicle Public Repo"
DEFAULT_TAG="v1.0.0"
DEFAULT_TITLE="Chronicle 1.0.0"
DEFAULT_NOTES_FILE="$ROOT_DIR/docs/github_rollout/RELEASE_v1.0.0_DRAFT.md"

clear
echo "--- CHRONICLE GITHUB RELEASE NOTES ONLY ---"
echo "This updates the title and notes of an existing GitHub release."
echo "It does NOT upload or replace any release assets."
echo "It does NOT create a git commit and will NOT ask for a commit message."
echo "It reads the release body from a notes file."
echo ""

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: GitHub CLI (gh) is not installed."
  read -r -p "Press Enter to close..."
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated."
  echo "Run: gh auth login"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -d "$DEFAULT_PUBLIC_REPO_DIR/.git" ]]; then
  echo "ERROR: Public repo clone not found:"
  echo "  $DEFAULT_PUBLIC_REPO_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "Public repo clone path:"
echo "  $DEFAULT_PUBLIC_REPO_DIR"
echo ""
echo "Press Enter to use defaults where offered."
echo ""

read -r -p "Tag [$DEFAULT_TAG]: " TAG
TAG="${TAG:-$DEFAULT_TAG}"

read -r -p "Release title [$DEFAULT_TITLE]: " TITLE
TITLE="${TITLE:-$DEFAULT_TITLE}"

read -r -p "Release notes file [$DEFAULT_NOTES_FILE]: " NOTES_FILE
NOTES_FILE="${NOTES_FILE:-$DEFAULT_NOTES_FILE}"

if [[ ! -f "$NOTES_FILE" ]]; then
  echo "ERROR: Release notes file not found:"
  echo "  $NOTES_FILE"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "Release notes will be read from:"
echo "  $NOTES_FILE"
echo "If you want to edit that file now, type OPEN in ALL CAPITALS."
echo "Otherwise, just press Enter to keep going."
read -r -p "Type OPEN to edit the notes file now: " OPEN_NOTES

if [[ "$OPEN_NOTES" == "OPEN" ]]; then
  open -e "$NOTES_FILE"
  echo ""
  echo "The notes file has been opened in TextEdit."
  read -r -p "After you finish editing and saving it, press Enter to continue..."
fi

REPO_SLUG="$(git -C "$DEFAULT_PUBLIC_REPO_DIR" remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"

if ! gh release view "$TAG" --repo "$REPO_SLUG" >/dev/null 2>&1; then
  echo "ERROR: Release tag not found in repository:"
  echo "  $TAG"
  read -r -p "Press Enter to close..."
  exit 1
fi

echo ""
echo "Repository: $REPO_SLUG"
echo "Tag: $TAG"
echo "Title: $TITLE"
echo "Notes file: $NOTES_FILE"
echo ""
echo "This will update release notes only."
echo "No ZIP assets will be uploaded, replaced, or deleted."
echo "To continue, type NOTES in ALL CAPITALS."
read -r -p "Type NOTES to continue: " CONFIRM

if [[ "$CONFIRM" != "NOTES" ]]; then
  echo "Cancelled."
  read -r -p "Press Enter to close..."
  exit 0
fi

gh release edit "$TAG" \
  --repo "$REPO_SLUG" \
  --title "$TITLE" \
  --notes-file "$NOTES_FILE"

echo ""
echo "Release notes updated successfully."
gh release view "$TAG" --repo "$REPO_SLUG"
echo ""
read -r -p "Press Enter to close..."
