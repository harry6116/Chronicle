#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path


REQUIRED_PATHS = [
    "chronicle_gui.py",
    "chronicle_runtime.py",
    "chronicle_core.py",
    "chronicle_app/__init__.py",
    "chronicle_app/config.py",
    "chronicle_app/services/__init__.py",
    "chronicle_app/services/worker_runtime.py",
    "chronicle_app/services/worker_execute_runtime.py",
    "chronicle_app/services/worker_finalize_runtime.py",
    "chronicle_app/services/file_cleanup.py",
    "chronicle_app/services/legacy_pdf_runtime.py",
    "chronicle_app/ui/__init__.py",
    "chronicle_app/ui/bindings.py",
    "chronicle_app/ui/dialogs.py",
    "chronicle_app/ui/main_frame_sections.py",
    "requirements.txt",
    "build.command",
    "build_windows.bat",
    "build_windows.ps1",
    "capture_windows_build_diagnostics.bat",
    "stage_windows_bundle.command",
    "Mac/build.command",
    "Mac/build_mac.py",
    "Chronicle.spec",
    "LICENSE",
    ".gitignore",
    ".github/workflows/build-mac-windows.yml",
    "docs/README.md",
    "docs/reference/CHANGELOG.md",
    "docs/policies/CONTRIBUTING.md",
    "docs/policies/CODE_OF_CONDUCT.md",
    "docs/user/METHODOLOGY.md",
    "docs/reference/Chronicle_Technical_Architecture_Deep_Dive.md",
    "docs/user/chronicle_help.html",
    "docs/user/SYSTEM_REQUIREMENTS.md",
    "tools/precommit_secret_scan.sh",
    "tools/install_git_hooks.sh",
    "tools/stage_windows_bundle.py",
    "tools/release_regression_offline.py",
    "tools/release_fileset_check.py",
    ".githooks/pre-commit",
]

SOURCE_ARCHIVE_REQUIRED = [
    "chronicle_gui.py",
    "chronicle_runtime.py",
    "chronicle_core.py",
    "chronicle_app/services/worker_runtime.py",
    "chronicle_app/services/worker_execute_runtime.py",
    "chronicle_app/services/worker_finalize_runtime.py",
    "chronicle_app/services/file_cleanup.py",
    "chronicle_app/services/legacy_pdf_runtime.py",
    "chronicle_app/services/pdf_processor.py",
    "chronicle_app/services/document_processors.py",
    "chronicle_app/services/scan_runtime.py",
    "chronicle_app/ui/bindings.py",
    "chronicle_app/ui/main_frame_sections.py",
    "chronicle_app/ui/dialogs.py",
    "tests/test_pdf_processor.py",
    "tests/test_document_processors.py",
    "tests/test_scan_runtime.py",
    "tests/test_ui_bindings.py",
    "tests/test_worker_runtime.py",
    "tests/test_worker_execute_runtime.py",
    "tests/test_worker_finalize_runtime.py",
]

FORBIDDEN_TRACKED = [
    "api_keys.json",
    "api_key.txt",
    "api_key_gemini.txt",
    "api_key_anthropic.txt",
    "api_key_openai.txt",
    "user_config.json",
    "chronicle_active_session.json",
]


def git_tracked_files() -> set[str]:
    out = subprocess.check_output(["git", "ls-files"], text=True)
    return {line.strip() for line in out.splitlines() if line.strip()}


def find_source_archives(root: Path) -> list[Path]:
    return sorted(root.glob("Chronicle*Source*.zip"))


def validate_source_archive(zip_path: Path) -> list[str]:
    missing: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    for rel_path in SOURCE_ARCHIVE_REQUIRED:
        if rel_path not in names:
            missing.append(rel_path)
    return missing


def main() -> int:
    tracked = git_tracked_files()
    root = Path.cwd()
    missing_paths = [p for p in REQUIRED_PATHS if not (root / p).exists()]
    forbidden = [p for p in FORBIDDEN_TRACKED if p in tracked]
    archives = find_source_archives(root)
    archive_failures: list[tuple[Path, list[str]]] = []
    for archive in archives:
        missing = validate_source_archive(archive)
        if missing:
            archive_failures.append((archive, missing))

    print("=== Release Fileset Check ===")
    print(f"Required path count: {len(REQUIRED_PATHS)}")
    print(f"Forbidden tracked paths checked: {len(FORBIDDEN_TRACKED)}")
    print(f"Source archives checked: {len(archives)}")

    if missing_paths:
        print("\nMissing required paths:")
        for p in missing_paths:
            print(f"- {p}")

    if forbidden:
        print("\nForbidden files are still tracked:")
        for p in forbidden:
            print(f"- {p}")

    if archive_failures:
        print("\nSource archive drift detected:")
        for archive, missing in archive_failures:
            print(f"- {archive.name}")
            for item in missing:
                print(f"  - missing: {item}")

    if missing_paths or forbidden or archive_failures:
        print("\nResult: FAIL")
        return 1

    print("\nResult: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
