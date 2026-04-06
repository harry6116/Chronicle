#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PUBLIC_REPO_DIR="/Users/michaelsmac/Documents/Chronicle Public Repo"
DEFAULT_ASSET_DIR="/Users/michaelsmac/Documents/Convert"
DEFAULT_TAG="v1.0.0"
DEFAULT_TITLE="Chronicle 1.0.0"
DEFAULT_MAC_ASSET="$DEFAULT_ASSET_DIR/Chronicle 1.0 mac.zip"
DEFAULT_WINDOWS_ASSET="$DEFAULT_ASSET_DIR/Chronicle 1.0 windows.zip"
DEFAULT_NOTES_FILE="$ROOT_DIR/docs/github_rollout/RELEASE_v1.0.0_DRAFT.md"

clear
echo "--- CHRONICLE GITHUB RELEASE PUBLISHER ---"
echo "This creates or updates a GitHub release using the GitHub CLI."
echo "It is intended for large ZIP assets that the web uploader may reject."
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

echo "Public repo clone path:"
echo "  $DEFAULT_PUBLIC_REPO_DIR"
echo ""
echo "Press Enter to use defaults where offered."
echo ""

read -r -p "Tag [$DEFAULT_TAG]: " TAG
TAG="${TAG:-$DEFAULT_TAG}"

read -r -p "Release title [$DEFAULT_TITLE]: " TITLE
TITLE="${TITLE:-$DEFAULT_TITLE}"

read -r -p "Mac asset path [$DEFAULT_MAC_ASSET]: " MAC_ASSET
MAC_ASSET="${MAC_ASSET:-$DEFAULT_MAC_ASSET}"

read -r -p "Windows asset path [$DEFAULT_WINDOWS_ASSET]: " WINDOWS_ASSET
WINDOWS_ASSET="${WINDOWS_ASSET:-$DEFAULT_WINDOWS_ASSET}"

read -r -p "Release notes file [$DEFAULT_NOTES_FILE]: " NOTES_FILE
NOTES_FILE="${NOTES_FILE:-$DEFAULT_NOTES_FILE}"

if [[ ! -d "$DEFAULT_PUBLIC_REPO_DIR/.git" ]]; then
  echo "ERROR: Public repo clone not found:"
  echo "  $DEFAULT_PUBLIC_REPO_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -f "$MAC_ASSET" ]]; then
  echo "ERROR: Mac asset not found:"
  echo "  $MAC_ASSET"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -f "$WINDOWS_ASSET" ]]; then
  echo "ERROR: Windows asset not found:"
  echo "  $WINDOWS_ASSET"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -f "$NOTES_FILE" ]]; then
  echo "ERROR: Release notes file not found:"
  echo "  $NOTES_FILE"
  read -r -p "Press Enter to close..."
  exit 1
fi

REPO_SLUG="$(git -C "$DEFAULT_PUBLIC_REPO_DIR" remote get-url origin | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"

echo ""
echo "Repository: $REPO_SLUG"
echo "Tag: $TAG"
echo "Title: $TITLE"
echo "Mac asset: $MAC_ASSET"
echo "Windows asset: $WINDOWS_ASSET"
echo "Notes file: $NOTES_FILE"
echo ""
read -r -p "Type RELEASE to continue: " CONFIRM

if [[ "$CONFIRM" != "RELEASE" ]]; then
  echo "Cancelled."
  read -r -p "Press Enter to close..."
  exit 0
fi

if gh release view "$TAG" --repo "$REPO_SLUG" >/dev/null 2>&1; then
  echo ""
  echo "Release already exists. Uploading assets with clobber enabled..."
  gh release upload "$TAG" "$MAC_ASSET" "$WINDOWS_ASSET" --repo "$REPO_SLUG" --clobber
  gh release edit "$TAG" --repo "$REPO_SLUG" --title "$TITLE" --notes-file "$NOTES_FILE"
else
  echo ""
  echo "Creating new release and uploading large assets..."
  gh release create "$TAG" "$MAC_ASSET" "$WINDOWS_ASSET" \
    --repo "$REPO_SLUG" \
    --title "$TITLE" \
    --notes-file "$NOTES_FILE" \
    --target main
fi

echo ""
echo "Release published successfully."
gh release view "$TAG" --repo "$REPO_SLUG"
echo ""
read -r -p "Press Enter to close..."
