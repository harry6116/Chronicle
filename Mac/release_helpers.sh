#!/bin/bash

release_notes_file() {
  local root_dir="$1"
  printf '%s/docs/github_rollout/RELEASE_NOTES_CURRENT.md' "$root_dir"
}

release_version_from_notes() {
  local notes_file="$1"
  python3 - "$notes_file" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="ignore")
patterns = (
    r"(?im)^\s*#\s*Chronicle\s+([0-9]+(?:\.[0-9]+){1,3})\b",
    r"(?im)\bChronicle\s+([0-9]+(?:\.[0-9]+){1,3})\b",
)
for pattern in patterns:
    match = re.search(pattern, text)
    if match:
        print(match.group(1))
        raise SystemExit(0)
print(f"Could not derive Chronicle release version from {path}", file=sys.stderr)
raise SystemExit(1)
PY
}

release_tag_from_notes() {
  local notes_file="$1"
  printf 'v%s' "$(release_version_from_notes "$notes_file")"
}

release_title_from_tag() {
  local tag="${1#v}"
  printf 'Chronicle %s' "$tag"
}
