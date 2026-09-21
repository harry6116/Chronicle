import re
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOC_ROOTS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "docs",
]

PUBLIC_RELEASE_NOTES = REPO_ROOT / "docs/github_rollout/RELEASE_NOTES_CURRENT.md"

PRIVATE_PATH_PATTERNS = [
    re.compile(r"/Users/[^`\s)>\]]+"),
    re.compile(r"\\Users\\(?!<you>)[^`\s)>\]]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]:\\Users\\(?!<you>)[^`\s)>\]]+", re.IGNORECASE),
    re.compile(r"\bfile://", re.IGNORECASE),
    re.compile(r"/private/[^`\s)>\]]+"),
    re.compile(r"/var/folders/[^`\s)>\]]+"),
]

RELEASE_NOTES_PRIVATE_PATTERNS = [
    re.compile(r"/Users/", re.IGNORECASE),
    re.compile(r"\bmichaelsmac\b", re.IGNORECASE),
    re.compile(r"\bcurrent workspace\b", re.IGNORECASE),
    re.compile(r"\bworkspace (?:app )?copy\b", re.IGNORECASE),
    re.compile(r"\bDesktop (?:app )?copy\b", re.IGNORECASE),
    re.compile(r"/Applications/Chronicle\.app", re.IGNORECASE),
    re.compile(r"\bdist/Chronicle\.app\b", re.IGNORECASE),
    re.compile(r"\bMac/build\.command\b", re.IGNORECASE),
    re.compile(r"\bembedded build stamp\b", re.IGNORECASE),
    re.compile(r"\bbuild stamp:\s*`?\d{4}-\d{2}-\d{2}", re.IGNORECASE),
    re.compile(r"\blocal conversion workspace\b", re.IGNORECASE),
    re.compile(r"\blocal live benchmark pack\b", re.IGNORECASE),
    re.compile(r"\btemporary local scanner installs\b", re.IGNORECASE),
    re.compile(r"\.html\.bak\b", re.IGNORECASE),
    re.compile(r"\bChronicle_Source_\d{4}-\d{2}-\d{2}\.zip\b", re.IGNORECASE),
    re.compile(r"\bsource archive\b", re.IGNORECASE),
    re.compile(r"\bstate of directories\b", re.IGNORECASE),
    re.compile(r"\bstate of (?:the )?directories\b", re.IGNORECASE),
    re.compile(r"\bchronicle_app/", re.IGNORECASE),
    re.compile(r"\bchronicle_core\.py\b", re.IGNORECASE),
    re.compile(r"\bchronicle_runtime\.py\b", re.IGNORECASE),
    re.compile(r"\bprocess_pdf\(", re.IGNORECASE),
]

INTERNAL_RULE_PATTERNS = [
    re.compile(r"\binternal assistant instructions?\b", re.IGNORECASE),
    re.compile(r"\bimplementation constraints?\b", re.IGNORECASE),
    re.compile(r"\bplanning instructions?\b", re.IGNORECASE),
    re.compile(r"\bdocumentation rule:\b", re.IGNORECASE),
    re.compile(r"\bdo not use Markdown hash heading markers\b", re.IGNORECASE),
]

STALE_PRODUCT_PATTERNS = [
    re.compile(r"\bpackaged Private Offline Mode\b", re.IGNORECASE),
    re.compile(r"\bpackaged offline (?:model|runtime|components?)\b", re.IGNORECASE),
    re.compile(r"\bincluded `?qwen2\.5vl:7b`? (?:model|local model|model pack)\b", re.IGNORECASE),
    re.compile(r"\bclaude-sonnet-4-20250514\b", re.IGNORECASE),
]


def _public_doc_paths():
    seen = set()
    for root in PUBLIC_DOC_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = [
                path
                for path in root.rglob("*")
                if path.is_file()
                and "internal" not in path.relative_to(root).parts
                and path.suffix.lower() in {".md", ".html", ".txt"}
            ]
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            yield path


class PublicDocsSecurityTest(unittest.TestCase):
    def test_public_docs_do_not_expose_private_system_paths(self):
        leaks = []
        for path in _public_doc_paths():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in PRIVATE_PATH_PATTERNS:
                for match in pattern.finditer(text):
                    rel_path = path.relative_to(REPO_ROOT)
                    line = text.count("\n", 0, match.start()) + 1
                    leaks.append(f"{rel_path}:{line}: {match.group(0)}")

        self.assertEqual(
            leaks,
            [],
            "Public-facing docs must not expose private paths; move them to internal docs.",
        )

    def test_current_release_notes_are_public_copy_not_internal_handoff(self):
        text = PUBLIC_RELEASE_NOTES.read_text(encoding="utf-8", errors="ignore")
        leaks = []
        for pattern in RELEASE_NOTES_PRIVATE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                leaks.append(f"{PUBLIC_RELEASE_NOTES.relative_to(REPO_ROOT)}:{line}: {match.group(0)}")

        self.assertEqual(
            leaks,
            [],
            "Current release notes are public-facing copy; do not include local build/deployment state, private paths, source archives, or internal implementation handoff details.",
        )

    def test_public_docs_do_not_expose_internal_rules_or_stale_product_claims(self):
        leaks = []
        for path in _public_doc_paths():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in INTERNAL_RULE_PATTERNS + STALE_PRODUCT_PATTERNS:
                for match in pattern.finditer(text):
                    rel_path = path.relative_to(REPO_ROOT)
                    line = text.count("\n", 0, match.start()) + 1
                    leaks.append(f"{rel_path}:{line}: {match.group(0)}")

        self.assertEqual(
            leaks,
            [],
            "Public documentation contains internal rule text or a stale product claim.",
        )

    def test_current_release_identity_is_consistent(self):
        release_notes = PUBLIC_RELEASE_NOTES.read_text(encoding="utf-8")
        expected = re.search(r"^# Chronicle (\d+\.\d+\.\d+)$", release_notes, re.MULTILINE).group(1)
        checks = {
            "chronicle_gui.py": (REPO_ROOT / "chronicle_gui.py", r'^APP_VERSION = "([^"]+)"$'),
            "README.md": (REPO_ROOT / "README.md", r"Current public release line: \*\*Chronicle ([^*]+)\*\*"),
            "README_PUBLIC_FINAL.md": (
                REPO_ROOT / "docs/github_rollout/README_PUBLIC_FINAL.md",
                r"Current public release line: \*\*Chronicle ([^*]+)\*\*",
            ),
            "PROJECT_OVERVIEW_GITHUB.md": (
                REPO_ROOT / "docs/github_rollout/PROJECT_OVERVIEW_GITHUB.md",
                r"Current public release target: \*\*Chronicle ([^*]+)\*\*",
            ),
            "README_GITHUB_ROLLOUT_PACK.md": (
                REPO_ROOT / "docs/github_rollout/README_GITHUB_ROLLOUT_PACK.md",
                r"Current target release: `Chronicle ([^`]+)`",
            ),
            "LAUNCH_RUNBOOK.md": (
                REPO_ROOT / "docs/github_rollout/LAUNCH_RUNBOOK.md",
                r"Current target release: `Chronicle ([^`]+)`",
            ),
            "public/index.html": (
                REPO_ROOT / "docs/public/index.html",
                r"Current version:</strong> Chronicle ([0-9.]+)",
            ),
        }
        mismatches = []
        for label, (path, pattern) in checks.items():
            match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
            actual = match.group(1) if match else "missing"
            if actual != expected:
                mismatches.append(f"{label}: expected {expected}, found {actual}")
        self.assertEqual(mismatches, [])

    def test_public_html_has_basic_accessibility_structure(self):
        issues = []
        html_paths = sorted((REPO_ROOT / "docs/public").rglob("*.html"))
        html_paths.extend(sorted((REPO_ROOT / "docs/user").rglob("*.html")))
        for path in html_paths:
            soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
            rel_path = path.relative_to(REPO_ROOT)
            ids = [tag.get("id") for tag in soup.find_all(id=True)]
            duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
            if duplicate_ids:
                issues.append(f"{rel_path}: duplicate IDs {duplicate_ids}")
            if not soup.html or not soup.html.get("lang"):
                issues.append(f"{rel_path}: missing document language")
            if not soup.find("main"):
                issues.append(f"{rel_path}: missing main landmark")
            if len(soup.find_all("h1")) != 1:
                issues.append(f"{rel_path}: expected exactly one h1")
            for image in soup.find_all("img"):
                if not image.has_attr("alt"):
                    issues.append(f"{rel_path}: image missing alt text")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if href.startswith("#") and href[1:] not in ids:
                    issues.append(f"{rel_path}: missing fragment target {href}")

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
