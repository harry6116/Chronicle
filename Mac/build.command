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

echo "Build and configured installation checks passed."
if [[ -t 0 ]]; then
    echo "Press any key to close..."
    read -k 1 -s
fi
