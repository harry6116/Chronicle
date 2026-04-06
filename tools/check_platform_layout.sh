#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

check_file() {
  local p="$1"
  [ -e "$p" ] || fail "Missing: $p"
}

check_exec() {
  local p="$1"
  [ -x "$p" ] || fail "Not executable: $p"
}

echo "Checking platform wrappers and targets..."
check_file "$ROOT_DIR/build.command"
check_file "$ROOT_DIR/run_a11y_harness.command"
check_file "$ROOT_DIR/run_native_queue_harness.command"
check_file "$ROOT_DIR/Push_to_GitHub.command"
check_file "$ROOT_DIR/Sync_from_GitHub.command"
check_file "$ROOT_DIR/Update_Samples.command"
check_file "$ROOT_DIR/build_windows.bat"
check_file "$ROOT_DIR/run_a11y_harness.bat"
check_file "$ROOT_DIR/stage_windows_bundle.command"

check_file "$ROOT_DIR/Mac/build.command"
check_file "$ROOT_DIR/Mac/run_a11y_harness.command"
check_file "$ROOT_DIR/Mac/run_native_queue_harness.command"
check_file "$ROOT_DIR/Mac/Push_to_GitHub.command"
check_file "$ROOT_DIR/Mac/Sync_from_GitHub.command"
check_file "$ROOT_DIR/Mac/Update_Samples.command"
if [ -d "$ROOT_DIR/Windows" ]; then
  check_file "$ROOT_DIR/Windows/build_windows.bat"
  check_file "$ROOT_DIR/Windows/run_a11y_harness.bat"
fi

check_exec "$ROOT_DIR/build.command"
check_exec "$ROOT_DIR/run_a11y_harness.command"
check_exec "$ROOT_DIR/run_native_queue_harness.command"
check_exec "$ROOT_DIR/Push_to_GitHub.command"
check_exec "$ROOT_DIR/Sync_from_GitHub.command"
check_exec "$ROOT_DIR/Update_Samples.command"
check_exec "$ROOT_DIR/stage_windows_bundle.command"
check_exec "$ROOT_DIR/Mac/build.command"
check_exec "$ROOT_DIR/Mac/run_a11y_harness.command"
check_exec "$ROOT_DIR/Mac/run_native_queue_harness.command"
check_exec "$ROOT_DIR/Mac/Push_to_GitHub.command"
check_exec "$ROOT_DIR/Mac/Sync_from_GitHub.command"
check_exec "$ROOT_DIR/Mac/Update_Samples.command"

echo "Checking wrapper forwarding strings..."
grep -q 'Mac/build.command' "$ROOT_DIR/build.command" || fail "build.command does not forward to Mac/build.command"
grep -q 'Mac/run_a11y_harness.command' "$ROOT_DIR/run_a11y_harness.command" || fail "run_a11y_harness.command does not forward to Mac script"
grep -q 'Mac/run_native_queue_harness.command' "$ROOT_DIR/run_native_queue_harness.command" || fail "run_native_queue_harness.command does not forward to Mac script"
grep -q 'build_windows.ps1' "$ROOT_DIR/build_windows.bat" || fail "build_windows.bat does not forward to build_windows.ps1"
grep -Eq 'Windows[\\/]+run_a11y_harness\.bat|a11y_queue_harness\.py' "$ROOT_DIR/run_a11y_harness.bat" || fail "run_a11y_harness.bat does not forward to the Windows harness"

echo "Running Mac build preflight dry-check..."
check_file "$ROOT_DIR/Mac/build_mac.py"
check_file "$ROOT_DIR/chronicle_gui.py"
check_file "$ROOT_DIR/chronicle_core.py"
check_file "$ROOT_DIR/assets"
check_file "$ROOT_DIR/docs"

echo "All platform layout checks passed."
