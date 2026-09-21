#!/usr/bin/env bash
set -euo pipefail

scan_mode="${1:-staged}"
scan_root=""
staged_files=()

if [[ "${scan_mode}" == "--tree" ]]; then
  if [[ -z "${2:-}" || ! -d "${2}" ]]; then
    echo "Usage: $0 [--all | --tree DIRECTORY]" >&2
    exit 2
  fi
  scan_root="$(cd "${2}" && pwd)"
  cd "${scan_root}"
  while IFS= read -r -d '' path; do
    staged_files+=("${path#./}")
  done < <(find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' -print0)
else
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -z "${repo_root}" ]]; then
    echo "[secret-scan] Not inside a git repository. Skipping."
    exit 0
  fi
  scan_root="${repo_root}"
  cd "${scan_root}"
fi

if [[ "${scan_mode}" == "--all" ]]; then
  while IFS= read -r path; do
    [[ -n "${path}" ]] && staged_files+=("${path}")
  done < <(git ls-files --cached --others --exclude-standard)
elif [[ "${scan_mode}" == "staged" ]]; then
  while IFS= read -r path; do
    [[ -n "${path}" ]] && staged_files+=("${path}")
  done < <(git diff --cached --name-only --diff-filter=ACMR)
elif [[ "${scan_mode}" != "--tree" ]]; then
  echo "Usage: $0 [--all | --tree DIRECTORY]" >&2
  exit 2
fi

if [[ "${#staged_files[@]}" -eq 0 ]]; then
  exit 0
fi

forbidden_paths=(
  "api_keys.json"
  "api_key.txt"
  "api_key_gemini.txt"
  "api_key_anthropic.txt"
  "api_key_openai.txt"
)

patterns=(
  "AIza[0-9A-Za-z_-]{20,}"                   # Google API keys
  "sk-[A-Za-z0-9]{20,}"                      # OpenAI-style keys
  "ghp_[A-Za-z0-9]{20,}"                     # GitHub personal access tokens
  "xox[baprs]-[A-Za-z0-9-]{10,}"             # Slack tokens
  "-----BEGIN (RSA|EC|OPENSSH|DSA)? ?PRIVATE KEY-----"
)

failed=0
tmp_report="$(mktemp)"
trap 'rm -f "${tmp_report}"' EXIT

for path in "${staged_files[@]}"; do
  for forbidden in "${forbidden_paths[@]}"; do
    if [[ "$(basename "${path}")" == "${forbidden}" ]]; then
      echo "[secret-scan] Blocked forbidden secret file: ${path}" | tee -a "${tmp_report}"
      failed=1
    fi
  done

  if [[ "${scan_mode}" == "--all" || "${scan_mode}" == "--tree" ]]; then
    [[ -f "${path}" ]] || continue
    for pattern in "${patterns[@]}"; do
      if rg -I -n --pcre2 -e "${pattern}" -- "${path}" >/dev/null 2>&1; then
        echo "[secret-scan] Potential secret match in ${path} (pattern: ${pattern})" | tee -a "${tmp_report}"
        failed=1
      fi
    done
  else
    if ! git cat-file -e ":${path}" 2>/dev/null; then
      continue
    fi
    staged_blob="$(git show ":${path}" || true)"
    for pattern in "${patterns[@]}"; do
      if rg -n --pcre2 -e "${pattern}" <<<"${staged_blob}" >/dev/null 2>&1; then
        echo "[secret-scan] Potential secret match in ${path} (pattern: ${pattern})" | tee -a "${tmp_report}"
        failed=1
      fi
    done
  fi
done

if [[ "${failed}" -ne 0 ]]; then
  cat <<'EOF'
[secret-scan] Commit blocked.
Fix:
1) Remove secrets from staged content.
2) Rotate any real credentials that were exposed.
3) Use Chronicle app-data key storage / keychain, not repository files.
EOF
  exit 1
fi

exit 0
