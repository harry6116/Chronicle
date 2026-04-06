#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif [[ -x "$ROOT_DIR/venv311/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/venv311/bin/python"
fi

echo "--------------------------------------------------"
echo "🚀 CHRONICLE ACCESSIBILITY BUILD"
echo "--------------------------------------------------"
echo "Project: $ROOT_DIR"
echo "Python:  $PYTHON_BIN"

# 1. Activate Environment
if [[ -d "$ROOT_DIR/.venv" ]]; then
    source "$ROOT_DIR/.venv/bin/activate"
elif [[ -d "$ROOT_DIR/venv311" ]]; then
    source "$ROOT_DIR/venv311/bin/activate"
fi

# 1b. Preflight checks
if [[ ! -f "$SCRIPT_DIR/build_mac.py" ]]; then
    echo "❌ Error: build_mac.py not found."
    exit 1
fi

if [[ ! -f "$ROOT_DIR/chronicle_gui.py" ]]; then
    echo "❌ Error: chronicle_gui.py not found."
    exit 1
fi

if [[ ! -f "$ROOT_DIR/chronicle_core.py" ]]; then
    echo "❌ Error: chronicle_core.py not found."
    exit 1
fi

if [[ ! -d "$ROOT_DIR/chronicle_app" ]]; then
    echo "❌ Error: chronicle_app package not found."
    exit 1
fi

if [[ ! -d "$ROOT_DIR/chronicle_app/services" ]]; then
    echo "❌ Error: chronicle_app/services not found."
    exit 1
fi

if [[ ! -d "$ROOT_DIR/chronicle_app/ui" ]]; then
    echo "❌ Error: chronicle_app/ui not found."
    exit 1
fi

if [[ ! -d "$ROOT_DIR/assets" ]]; then
    echo "❌ Error: assets directory not found."
    exit 1
fi

if [[ ! -d "$ROOT_DIR/docs" ]]; then
    echo "❌ Error: docs directory not found."
    exit 1
fi

# 2. Run the Sledgehammer Build
# This bundles the app so users NEVER see Python alerts
echo "📦 Bundling into standalone Mac App..."
"$PYTHON_BIN" "$SCRIPT_DIR/build_mac.py"

# 3. Verify and deploy the fresh app bundle
APP_BUNDLE="$ROOT_DIR/dist/Chronicle.app"
APP_STAMP="$APP_BUNDLE/Contents/Resources/build_stamp.txt"
if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "❌ Error: expected app bundle was not created at $APP_BUNDLE"
    exit 1
fi
if [[ -f "$APP_STAMP" ]]; then
    APP_STAMP_VALUE="$(cat "$APP_STAMP")"
    echo "Embedded app build stamp: $APP_STAMP_VALUE"
else
    APP_STAMP_VALUE="missing"
    echo "⚠️ Warning: embedded build stamp not found at $APP_STAMP"
fi
if [[ -d "$APP_BUNDLE" ]]; then
    echo "App bundle modified: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$APP_BUNDLE")"
fi

copy_app_bundle() {
    local target="$1"
    local label="$2"
    local target_parent
    target_parent="$(dirname "$target")"

    if [[ ! -d "$target_parent" ]]; then
        echo "ℹ️ Skipping $label (parent directory missing): $target_parent"
        return
    fi

    if [[ -e "$target" ]]; then
        echo "♻️ Replacing existing $label: $target"
        rm -rf "$target"
    else
        echo "➕ Creating fresh $label: $target"
    fi

    ditto "$APP_BUNDLE" "$target"
    local deployed_stamp="$target/Contents/Resources/build_stamp.txt"
    if [[ -f "$deployed_stamp" ]]; then
        echo "✅ Updated $label build stamp: $(cat "$deployed_stamp")"
    else
        echo "⚠️ Updated $label but build stamp was not found in the copied app."
    fi
}

copy_app_bundle "$ROOT_DIR/Chronicle.app" "workspace app copy"
copy_app_bundle "$HOME/Desktop/Chronicle.app" "Desktop app copy"
if [[ -w "/Applications" ]] || [[ -e "/Applications/Chronicle.app" && -w "/Applications/Chronicle.app" ]]; then
    copy_app_bundle "/Applications/Chronicle.app" "Applications app copy"
else
    echo "ℹ️ Skipping /Applications/Chronicle.app (no writable existing app copy or Applications permissions unavailable)."
fi

echo "--------------------------------------------------"
echo "✅ SUCCESS: Fresh build is ready at $APP_BUNDLE"
echo "--------------------------------------------------"
if [[ -t 0 ]]; then
    echo "Press any key to close..."
    read -k 1 -s
fi
