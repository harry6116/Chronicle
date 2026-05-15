#!/bin/bash
set -euo pipefail

WINDOWS_APP_DIR="${CHRONICLE_WINDOWS_APP_DIR:-$HOME/Documents/dist/Chronicle}"
MAC_APP_DIR="${CHRONICLE_MAC_APP_DIR:-$HOME/Documents/Chronicle/dist/Chronicle.app}"
RELEASE_DIR="${CHRONICLE_RELEASE_ASSET_DIR:-$HOME/Documents/Chronicle Release Apps}"

WINDOWS_ZIP="$RELEASE_DIR/Chronicle.windows.zip"
MAC_ZIP="$RELEASE_DIR/Chronicle.mac.zip"

zip_folder_keep_parent() {
  local source_path="$1"
  local output_path="$2"
  local label="$3"
  local temp_dir
  local temp_path

  temp_dir="$(mktemp -d "${output_path}.tmpdir.XXXXXX")"
  temp_path="$temp_dir/$(basename "$output_path")"

  echo ""
  echo "Packaging $label..."
  echo "Source: $source_path"
  echo "Output: $output_path"

  (
    cd "$(dirname "$source_path")"
    COPYFILE_DISABLE=1 /usr/bin/zip -qry --symlinks "$temp_path" "$(basename "$source_path")"
  )
  mv "$temp_path" "$output_path"
  rmdir "$temp_dir"
  echo "Done: $(du -h "$output_path" | awk '{print $1}')"
}

clear 2>/dev/null || true
echo "--- CHRONICLE RELEASE APP PACKAGER ---"
echo "This creates the Windows and Mac ZIP files used by the GitHub release publisher."
echo ""

if [[ ! -d "$WINDOWS_APP_DIR" ]]; then
  echo "ERROR: Windows build folder not found:"
  echo "  $WINDOWS_APP_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -f "$WINDOWS_APP_DIR/Chronicle.exe" ]]; then
  echo "ERROR: Windows build does not contain Chronicle.exe:"
  echo "  $WINDOWS_APP_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -d "$MAC_APP_DIR" ]]; then
  echo "ERROR: Mac app not found:"
  echo "  $MAC_APP_DIR"
  read -r -p "Press Enter to close..."
  exit 1
fi

if [[ ! -f "$MAC_APP_DIR/Contents/MacOS/Chronicle" ]]; then
  echo "ERROR: Mac app does not contain the Chronicle executable:"
  echo "  $MAC_APP_DIR/Contents/MacOS/Chronicle"
  read -r -p "Press Enter to close..."
  exit 1
fi

mkdir -p "$RELEASE_DIR"

zip_folder_keep_parent "$WINDOWS_APP_DIR" "$WINDOWS_ZIP" "Windows app"
zip_folder_keep_parent "$MAC_APP_DIR" "$MAC_ZIP" "Mac app"

echo ""
echo "Release ZIPs are ready:"
echo "  $WINDOWS_ZIP"
echo "  $MAC_ZIP"
echo ""
if [[ "${CHRONICLE_SKIP_OPEN:-0}" != "1" ]]; then
  open "$RELEASE_DIR"
fi
read -r -p "Press Enter to close..."
