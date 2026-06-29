#!/bin/bash
set -euo pipefail

WINDOWS_APP_DIR="${CHRONICLE_WINDOWS_APP_DIR:-$HOME/Documents/dist/Chronicle}"
MAC_APP_DIR="${CHRONICLE_MAC_APP_DIR:-$HOME/Documents/Chronicle/dist/Chronicle.app}"
RELEASE_DIR="${CHRONICLE_RELEASE_ASSET_DIR:-$HOME/Documents/Chronicle Release Apps}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SNAPSHOT_DIR="$ROOT_DIR/artifacts/public_repo_stage/Chronicle"
RELEASE_STAGING_DIR="$RELEASE_DIR/.packaging-staging"

WINDOWS_ZIP="$RELEASE_DIR/Chronicle.windows.zip"
MAC_ZIP="$RELEASE_DIR/Chronicle.mac.zip"

cleanup_stale_zip_temps() {
  local output_path="$1"
  local temp_parent
  local temp_prefix

  temp_parent="$(dirname "$output_path")"
  temp_prefix="$(basename "$output_path").tmpdir."

  find "$temp_parent" -maxdepth 1 -type d -name "${temp_prefix}*" -print -exec rm -rf {} +
}

cleanup_release_staging() {
  rm -rf "$RELEASE_STAGING_DIR"
}

wait_for_close() {
  if [[ -t 0 ]]; then
    read -r -p "Press Enter to close..."
  fi
}

assert_no_embedded_offline_payload() {
  local source_path="$1"
  local label="$2"
  local found

  found="$(
    find "$source_path" \
      \( -path '*/_internal/offline' \
      -o -path '*/Contents/Resources/offline' \
      -o -path '*/Contents/Frameworks/offline' \
      -o -path '*/offline/models' \
      -o -path '*/offline/ollama' \) \
      -print -quit
  )"

  if [[ -n "$found" ]]; then
    echo "ERROR: $label still contains an embedded Private Offline Mode payload:"
    echo "  $found"
    echo "Chronicle release app ZIPs must stay slim. Private Offline Mode now uses the user's existing Ollama install."
    return 1
  fi
}

zip_folder_keep_parent() {
  local source_path="$1"
  local output_path="$2"
  local label="$3"
  local temp_dir
  local temp_path

  echo ""
  echo "Packaging $label..."
  echo "Source: $source_path"
  echo "Output: $output_path"

  cleanup_stale_zip_temps "$output_path"
  temp_dir="$(mktemp -d "${output_path}.tmpdir.XXXXXX")"
  temp_path="$temp_dir/$(basename "$output_path")"

  (
    cd "$(dirname "$source_path")"
    COPYFILE_DISABLE=1 /usr/bin/zip -qry --symlinks "$temp_path" "$(basename "$source_path")"
  )
  mv "$temp_path" "$output_path"
  rmdir "$temp_dir"
  echo "Done: $(du -h "$output_path" | awk '{print $1}')"
}

zip_slim_app_package() {
  local source_path="$1"
  local output_path="$2"
  local label="$3"
  local staged_path

  staged_path="$RELEASE_STAGING_DIR/$(basename "$source_path")"

  echo ""
  echo "Staging slim $label without embedded Private Offline Mode payloads..."
  rm -rf "$staged_path"
  mkdir -p "$RELEASE_STAGING_DIR"
  rsync -a --delete \
    --exclude '/_internal/offline/' \
    --exclude '/Contents/Resources/offline/' \
    --exclude '/Contents/Frameworks/offline/' \
    "$source_path/" "$staged_path/"

  assert_no_embedded_offline_payload "$staged_path" "$label"
  zip_folder_keep_parent "$staged_path" "$output_path" "$label"
}

clear 2>/dev/null || true
echo "--- CHRONICLE RELEASE APP PACKAGER ---"
echo "This creates the Windows and Mac ZIP files used by the GitHub release publisher."
echo "Private Offline Mode now uses the user's existing Ollama installation; no offline pack is packaged."
echo ""

if [[ ! -d "$WINDOWS_APP_DIR" ]]; then
  echo "ERROR: Windows build folder not found:"
  echo "  $WINDOWS_APP_DIR"
  wait_for_close
  exit 1
fi

if [[ ! -f "$WINDOWS_APP_DIR/Chronicle.exe" ]]; then
  echo "ERROR: Windows build does not contain Chronicle.exe:"
  echo "  $WINDOWS_APP_DIR"
  wait_for_close
  exit 1
fi

if [[ ! -d "$MAC_APP_DIR" ]]; then
  echo "ERROR: Mac app not found:"
  echo "  $MAC_APP_DIR"
  wait_for_close
  exit 1
fi

if [[ ! -f "$MAC_APP_DIR/Contents/MacOS/Chronicle" ]]; then
  echo "ERROR: Mac app does not contain the Chronicle executable:"
  echo "  $MAC_APP_DIR/Contents/MacOS/Chronicle"
  wait_for_close
  exit 1
fi

mkdir -p "$RELEASE_DIR"
cleanup_release_staging
trap cleanup_release_staging EXIT

zip_slim_app_package "$WINDOWS_APP_DIR" "$WINDOWS_ZIP" "Windows app"
zip_slim_app_package "$MAC_APP_DIR" "$MAC_ZIP" "Mac app"

echo ""
echo "Preparing public release snapshot..."
python3 "$ROOT_DIR/tools/prepare_public_repo_snapshot.py" \
  --repo-root "$ROOT_DIR" \
  --output "$SNAPSHOT_DIR" \
  --clean
if [[ ! -d "$SNAPSHOT_DIR" ]]; then
  echo "ERROR: Public release snapshot was not created:"
  echo "  $SNAPSHOT_DIR"
  wait_for_close
  exit 1
fi

echo ""
echo "Release ZIPs are ready:"
echo "  $WINDOWS_ZIP"
echo "  $MAC_ZIP"
echo "Public snapshot is ready:"
echo "  $SNAPSHOT_DIR"
echo ""
if [[ "${CHRONICLE_SKIP_OPEN:-0}" != "1" ]]; then
  open "$RELEASE_DIR"
fi
wait_for_close
