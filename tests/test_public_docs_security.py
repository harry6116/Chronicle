import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOC_ROOTS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "docs",
]

PRIVATE_PATH_PATTERNS = [
    re.compile(r"/Users/[^`\s)>\]]+"),
    re.compile(r"\\Users\\(?!<you>)[^`\s)>\]]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]:\\Users\\(?!<you>)[^`\s)>\]]+", re.IGNORECASE),
    re.compile(r"\bfile://", re.IGNORECASE),
    re.compile(r"/private/[^`\s)>\]]+"),
    re.compile(r"/var/folders/[^`\s)>\]]+"),
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


if __name__ == "__main__":
    unittest.main()
