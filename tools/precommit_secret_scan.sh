#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "[secret-scan] Not inside a git repository. Skipping."
  exit 0
fi
cd "${repo_root}"

staged_files=()
while IFS= read -r path; do
  [[ -n "${path}" ]] && staged_files+=("${path}")
done < <(git diff --cached --name-only --diff-filter=ACMR)

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
    if [[ "${path}" == "${forbidden}" ]]; then
      echo "[secret-scan] Blocked forbidden secret file: ${path}" | tee -a "${tmp_report}"
      failed=1
    fi
  done

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
