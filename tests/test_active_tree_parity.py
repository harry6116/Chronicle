import hashlib
from pathlib import Path
import unittest


PRIMARY_ROOT = Path("/Users/michaelsmac/Documents/Chronicle")
ACTIVE_TREE_ROOTS = [
    PRIMARY_ROOT,
    Path("/Users/michaelsmac/Documents/Chronicle Beta"),
    Path("/Users/michaelsmac/Documents/Chronicle windows Beta"),
]

CRITICAL_PARITY_FILES = [
    "chronicle_runtime.py",
    "chronicle_gui.py",
    "build_windows.bat",
    "build_windows.ps1",
    "Run_Safe_Batch.command",
    "Download_Latest_Windows_Artifact.command",
    "Mac/Run_Safe_Batch.command",
    "Mac/Download_Latest_Windows_Artifact.command",
    "chronicle_app/config.py",
    "chronicle_app/services/app_files.py",
    "chronicle_app/services/exporters.py",
    "chronicle_app/services/pdf_processor.py",
    "chronicle_app/services/prompting.py",
    "chronicle_app/services/runtime_policies.py",
    "chronicle_app/ui/bindings.py",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ActiveTreeParityTest(unittest.TestCase):
    def test_active_trees_exist(self):
        missing = [str(root) for root in ACTIVE_TREE_ROOTS if not root.is_dir()]
        self.assertEqual(missing, [], f"Missing active Chronicle tree(s): {missing}")

    def test_critical_files_match_across_active_trees(self):
        reference_hashes = {}
        for rel_path in CRITICAL_PARITY_FILES:
            reference_file = PRIMARY_ROOT / rel_path
            self.assertTrue(reference_file.exists(), f"Primary tree is missing {rel_path}")
            reference_hashes[rel_path] = _sha256(reference_file)

        mismatches = []
        for root in ACTIVE_TREE_ROOTS[1:]:
            for rel_path in CRITICAL_PARITY_FILES:
                candidate = root / rel_path
                if not candidate.exists():
                    mismatches.append(f"{root}: missing {rel_path}")
                    continue
                if _sha256(candidate) != reference_hashes[rel_path]:
                    mismatches.append(f"{root}: differs for {rel_path}")

        self.assertEqual(
            mismatches,
            [],
            "Active tree parity drift detected:\n" + "\n".join(mismatches),
        )


if __name__ == "__main__":
    unittest.main()
