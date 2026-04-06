#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
clear

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: This folder is not a git repository."
  read -r -p "Press Enter to close..."
  exit 1
fi

echo "--- CHRONICLE PUBLIC REPO PREP ---"
echo "This rebuilds the curated public snapshot only."
echo "It does not push anything."
echo ""

python3 tools/prepare_public_repo_snapshot.py --clean

SNAPSHOT_DIR="/Users/michaelsmac/Documents/Chronicle/artifacts/public_repo_stage/Chronicle"
MANIFEST_PATH="$SNAPSHOT_DIR/PUBLIC_REPO_MANIFEST.txt"

echo ""
echo "Snapshot ready:"
echo "  $SNAPSHOT_DIR"
echo ""
echo "Top-level files:"
ls -1 "$SNAPSHOT_DIR" | sed -n '1,40p'
echo ""
echo "Manifest:"
echo "  $MANIFEST_PATH"
echo ""
read -r -p "Press Enter to close..."
