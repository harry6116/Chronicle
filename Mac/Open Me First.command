#!/bin/bash
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$DIR/Chronicle.app"

pause() {
  echo
  printf "Press Return to close this window. "
  read -r _ || true
}

echo "Chronicle first-launch helper"
echo "============================="
echo

if [ ! -d "$TARGET" ]; then
  echo "Chronicle.app was not found next to this helper at:"
  echo "  $TARGET"
  echo
  echo "Make sure Chronicle.app and Open Me First.command are in the same folder,"
  echo "then run this helper again."
  pause
  exit 1
fi

echo "Clearing macOS quarantine from:"
echo "  $TARGET"
echo
xattr_output="$(/usr/bin/xattr -dr com.apple.quarantine "$TARGET" 2>&1)" || true
if [ -n "$xattr_output" ]; then
  echo "xattr reported:"
  printf '%s\n' "$xattr_output" | sed 's/^/  /'
  echo
fi

remaining="$(/usr/bin/find "$TARGET" -exec sh -c '
  for path in "$@"; do
    if /usr/bin/xattr -p com.apple.quarantine "$path" >/dev/null 2>&1; then
      printf "%s\n" "$path"
    fi
  done
' _ {} +)"
if [ -n "$remaining" ]; then
  count="$(printf '%s\n' "$remaining" | wc -l | tr -d ' ')"
  echo "ERROR: $count file(s) inside Chronicle.app still carry com.apple.quarantine."
  echo "First few paths:"
  printf '%s\n' "$remaining" | head -5 | sed 's/^/  /'
  echo
  echo "Try moving the Chronicle folder to Downloads, or give Terminal access to"
  echo "the folder in System Settings -> Privacy & Security -> Files and Folders."
  echo
  echo "Manual command:"
  echo "  xattr -dr com.apple.quarantine \"$TARGET\""
  pause
  exit 1
fi

echo "Quarantine cleared from Chronicle.app and every file inside it."
echo

macos_version="$(/usr/bin/sw_vers -productVersion 2>/dev/null || echo "")"
macos_major="${macos_version%%.*}"
needs_settings_approval=0
if [ -z "$macos_major" ] || ! [[ "$macos_major" =~ ^[0-9]+$ ]] || [ "$macos_major" -ge 15 ]; then
  needs_settings_approval=1
fi

if [ "$needs_settings_approval" -eq 0 ]; then
  echo "Detected macOS $macos_version. You can close this window and open Chronicle.app."
  echo
  echo "If macOS still blocks Chronicle, open System Settings -> Privacy & Security"
  echo "and click Open Anyway near the security message for Chronicle."
  pause
  exit 0
fi

echo "Detected macOS ${macos_version:-unknown}. If macOS asks for approval,"
echo "use Privacy & Security to allow Chronicle after this launch attempt."
echo

/usr/bin/open "$TARGET" >/dev/null 2>&1 || true
sleep 2
/usr/bin/open "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension" >/dev/null 2>&1 || \
  /usr/bin/open "x-apple.systempreferences:com.apple.preference.security" >/dev/null 2>&1 || \
  /usr/bin/open -b com.apple.systempreferences >/dev/null 2>&1 || true

cat <<'NEXT_STEPS'
If macOS showed a security warning instead of launching Chronicle:

  1. Dismiss the warning.
  2. In System Settings, open Privacy & Security.
  3. Scroll to Security and click Open Anyway next to Chronicle.
  4. Confirm with your password or Touch ID if asked.

After that approval, normal double-click launches should work.
NEXT_STEPS

pause
