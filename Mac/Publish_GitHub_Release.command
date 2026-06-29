#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PUBLIC_REPO_DIR="${CHRONICLE_PUBLIC_REPO_DIR:-$HOME/Documents/Chronicle Public Repo}"
DEFAULT_ASSET_DIR="${CHRONICLE_RELEASE_ASSET_DIR:-$HOME/Documents/Chronicle Release Apps}"
. "$SCRIPT_DIR/release_helpers.sh"

derive_release_title() {
  release_title_from_tag "$1"
}

derive_release_notes_file() {
  release_notes_file "$ROOT_DIR"
}

derive_mac_asset_path() {
  printf '%s/Chronicle.mac.zip' "$DEFAULT_ASSET_DIR"
}

derive_windows_asset_path() {
  printf '%s/Chronicle.windows.zip' "$DEFAULT_ASSET_DIR"
}

normalize_answer() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

seed_release_notes_file_if_missing() {
  local target="$1"
  local tag="$2"
  if [[ -f "$target" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$target")"
  cat >"$target" <<EOF
# $(derive_release_title "$tag")

Write release notes here.
EOF
}

DEFAULT_NOTES_FILE="$(derive_release_notes_file)"
DEFAULT_TAG="$(release_tag_from_notes "$DEFAULT_NOTES_FILE")"
DEFAULT_TITLE="$(derive_release_title "$DEFAULT_TAG")"
DEFAULT_MAC_ASSET="$(derive_mac_asset_path "$DEFAULT_TAG")"
DEFAULT_WINDOWS_ASSET="$(derive_windows_asset_path "$DEFAULT_TAG")"
GITHUB_RELEASE_ASSET_SIZE_LIMIT_BYTES=2147483648

asset_size_bytes() {
  stat -f %z "$1"
}

format_asset_size() {
  python3 - "$1" <<'PY'
import sys

size = int(sys.argv[1])
gib = size / (1024 ** 3)
print(f"{size} bytes ({gib:.2f} GiB)")
PY
}

check_release_asset_size() {
  local asset_path="$1"
  local label="$2"
  local size_bytes

  size_bytes="$(asset_size_bytes "$asset_path")"
  if (( size_bytes >= GITHUB_RELEASE_ASSET_SIZE_LIMIT_BYTES )); then
    echo "ERROR: $label is too large for a GitHub release asset:"
    echo "  $asset_path"
    echo "  Size: $(format_asset_size "$size_bytes")"
    echo "GitHub release assets must be smaller than 2147483648 bytes (2 GiB)."
    echo "Publish the release notes without this ZIP, or move the installer payload to another hosting path."
    read -r -p "Press Enter to close..."
    exit 1
  fi
}

clear 2>/dev/null || true
echo "--- CHRONICLE GITHUB RELEASE PUBLISHER ---"
echo "This creates or updates a GitHub release using the GitHub CLI."
echo "It uploads only the Mac and Windows app ZIPs."
echo "Private Offline Mode now uses the user's existing Ollama installation; no offline pack is uploaded."
echo "It is NOT the right script for docs-only public repo updates."
echo "This script does NOT create a git commit and will NOT ask for a commit message."
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

echo "Public repo clone path:"
echo "  $DEFAULT_PUBLIC_REPO_DIR"
echo ""
echo "Press Enter to use defaults where offered."
echo ""

read -r -p "Tag [$DEFAULT_TAG]: " TAG
TAG="${TAG:-$DEFAULT_TAG}"

SUGGESTED_TITLE="$(derive_release_title "$TAG")"
SUGGESTED_MAC_ASSET="$(derive_mac_asset_path "$TAG")"
SUGGESTED_WINDOWS_ASSET="$(derive_windows_asset_path "$TAG")"
SUGGESTED_NOTES_FILE="$(derive_release_notes_file)"

read -r -p "Release title [$SUGGESTED_TITLE]: " TITLE
TITLE="${TITLE:-$SUGGESTED_TITLE}"

read -r -p "Mac asset path [$SUGGESTED_MAC_ASSET]: " MAC_ASSET
MAC_ASSET="${MAC_ASSET:-$SUGGESTED_MAC_ASSET}"

read -r -p "Windows asset path [$SUGGESTED_WINDOWS_ASSET]: " WINDOWS_ASSET
WINDOWS_ASSET="${WINDOWS_ASSET:-$SUGGESTED_WINDOWS_ASSET}"

read -r -p "Release notes file [$SUGGESTED_NOTES_FILE]: " NOTES_FILE
NOTES_FILE="${NOTES_FILE:-$SUGGESTED_NOTES_FILE}"

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

check_release_asset_size "$MAC_ASSET" "Mac asset"
check_release_asset_size "$WINDOWS_ASSET" "Windows asset"

if [[ ! -f "$NOTES_FILE" ]]; then
  seed_release_notes_file_if_missing "$NOTES_FILE" "$TAG"
  echo "Created release notes draft:"
  echo "  $NOTES_FILE"
fi

echo ""
echo "Release notes will be read from:"
echo "  $NOTES_FILE"
echo "If you want to edit that file now, type OPEN."
echo "Otherwise, just press Enter to keep going."
read -r -p "Type OPEN to edit the notes file now: " OPEN_NOTES

if [[ "$(normalize_answer "$OPEN_NOTES")" == "open" ]]; then
  open -e "$NOTES_FILE"
  echo ""
  echo "The notes file has been opened in TextEdit."
  read -r -p "After you finish editing and saving it, press Enter to continue..."
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
echo "To continue, type RELEASE."
while true; do
  read -r -p "Type RELEASE to continue (or CANCEL to stop): " CONFIRM
  CONFIRM_NORMALIZED="$(normalize_answer "$CONFIRM")"
  if [[ "$CONFIRM_NORMALIZED" == "release" ]]; then
    break
  fi
  if [[ "$CONFIRM_NORMALIZED" == "cancel" ]]; then
    echo "Cancelled."
    read -r -p "Press Enter to close..."
    exit 0
  fi
  echo "Please type RELEASE to publish or CANCEL to stop. Capitals are optional."
done

if gh release view "$TAG" --repo "$REPO_SLUG" >/dev/null 2>&1; then
  echo ""
  echo "Release already exists. Uploading app assets with clobber enabled..."
  gh release upload "$TAG" "$MAC_ASSET" "$WINDOWS_ASSET" --repo "$REPO_SLUG" --clobber
  gh release edit "$TAG" --repo "$REPO_SLUG" --title "$TITLE" --notes-file "$NOTES_FILE"
else
  echo ""
  echo "Creating new release and uploading app assets..."
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
