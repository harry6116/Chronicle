#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "Not inside a git repository."
  exit 1
fi

chmod +x "${repo_root}/.githooks/pre-commit" "${repo_root}/tools/precommit_secret_scan.sh"
git config core.hooksPath .githooks
echo "Installed git hooks path: .githooks"
echo "Pre-commit secret scanning is now active."
