import re
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
