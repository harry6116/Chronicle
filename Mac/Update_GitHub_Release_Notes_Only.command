#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PUBLIC_REPO_DIR="/Users/michaelsmac/Documents/Chronicle Public Repo"
DEFAULT_TAG="v1.0.0"
DEFAULT_NOTES_BASENAME="RELEASE_NOTES_CURRENT.md"

derive_release_title() {
  local tag="${1#v}"
  printf 'Chronicle %s' "$tag"
}

derive_release_version() {
  printf '%s' "${1#v}"
}

derive_release_notes_file() {
  printf '%s/docs/github_rollout/%s' "$ROOT_DIR" "$DEFAULT_NOTES_BASENAME"
}

find_latest_release_notes_file() {
  local latest
  latest="$(find "$ROOT_DIR/docs/github_rollout" -maxdepth 1 -type f -name 'RELEASE_v*_DRAFT.md' | sort -V | tail -n 1)"
  printf '%s' "$latest"
}

seed_release_notes_file_if_missing() {
  local target="$1"
  local tag="$2"
  local version source source_tag source_version
  if [[ -f "$target" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$target")"
  source="$(find_latest_release_notes_file)"
  if [[ -z "$source" || ! -f "$source" ]]; then
    cat >"$target" <<EOF
# $(derive_release_title "$tag")

Write release notes here.
EOF
    return 0
  fi
  cp "$source" "$target"
  source_tag="$(basename "$source" | sed -E 's/^RELEASE_(v[^_]+)_DRAFT\.md$/\1/')"
  source_version="$(derive_release_version "$source_tag")"
  version="$(derive_release_version "$tag")"
  perl -0pi -e "s/\Q$source_tag\E/$tag/g; s/\Q$source_version\E/$version/g" "$target"
}

DEFAULT_TITLE="$(derive_release_title "$DEFAULT_TAG")"
DEFAULT_NOTES_FILE="$(derive_release_notes_file "$DEFAULT_TAG")"

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

SUGGESTED_TITLE="$(derive_release_title "$TAG")"
SUGGESTED_NOTES_FILE="$(derive_release_notes_file "$TAG")"

read -r -p "Release title [$SUGGESTED_TITLE]: " TITLE
TITLE="${TITLE:-$SUGGESTED_TITLE}"

read -r -p "Release notes file [$SUGGESTED_NOTES_FILE]: " NOTES_FILE
NOTES_FILE="${NOTES_FILE:-$SUGGESTED_NOTES_FILE}"

if [[ ! -f "$NOTES_FILE" ]]; then
  seed_release_notes_file_if_missing "$NOTES_FILE" "$TAG"
  echo "Created release notes draft:"
  echo "  $NOTES_FILE"
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
while true; do
  read -r -p "Type NOTES to continue (or CANCEL to stop): " CONFIRM
  if [[ "$CONFIRM" == "NOTES" ]]; then
    break
  fi
  if [[ "$CONFIRM" == "CANCEL" ]]; then
    echo "Cancelled."
    read -r -p "Press Enter to close..."
    exit 0
  fi
  echo "Please type NOTES to continue or CANCEL to stop."
done

gh release edit "$TAG" \
  --repo "$REPO_SLUG" \
  --title "$TITLE" \
  --notes-file "$NOTES_FILE"

echo ""
echo "Release notes updated successfully."
gh release view "$TAG" --repo "$REPO_SLUG"
echo ""
read -r -p "Press Enter to close..."
