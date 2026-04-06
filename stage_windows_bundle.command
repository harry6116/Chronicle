#!/bin/zsh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if [[ -x "$SCRIPT_DIR/venv311/bin/python" ]]; then
    PYTHON_BIN="$SCRIPT_DIR/venv311/bin/python"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/tools/stage_windows_bundle.py" --force "$@"
