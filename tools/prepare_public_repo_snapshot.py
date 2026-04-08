#!/usr/bin/env python3
"""Build a clean public-facing Chronicle repo snapshot from the current workspace."""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
from pathlib import Path


ROOT_DOC_REPLACEMENTS = {
    "docs/reference/CHANGELOG.md": "CHANGELOG.md",
    "docs/policies/CODE_OF_CONDUCT.md": "CODE_OF_CONDUCT.md",
    "docs/github_rollout/README_PUBLIC_FINAL.md": "README.md",
    "docs/github_rollout/CONTRIBUTING_GITHUB.md": "CONTRIBUTING.md",
    "docs/github_rollout/SECURITY_GITHUB.md": "SECURITY.md",
    "docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md": "DISCLAIMER.md",
}

ALLOWED_GITHUB_ROLLOUT_DOCS = {
    "docs/github_rollout/CONTRIBUTING_GITHUB.md",
    "docs/github_rollout/LAUNCH_RUNBOOK.md",
    "docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md",
    "docs/github_rollout/MIGRATION_NOTES_OLD_TO_NEW.md",
    "docs/github_rollout/PROJECT_OVERVIEW_GITHUB.md",
    "docs/github_rollout/PROVIDER_PRIVACY_AND_TIER_GUIDE.md",
    "docs/github_rollout/PUBLIC_REPO_BOOTSTRAP.md",
    "docs/github_rollout/README_GITHUB_ROLLOUT_PACK.md",
    "docs/github_rollout/README_PUBLIC_FINAL.md",
    "docs/github_rollout/RELEASE_MESSAGES.md",
    "docs/github_rollout/RELEASE_v1.0.0_DRAFT.md",
    "docs/github_rollout/REPOSITORY_OVERHAUL_CHECKLIST.md",
    "docs/github_rollout/SECURITY_GITHUB.md",
}

ALLOWED_DOC_PATHS = {
    "docs/README.md",
    "docs/policies/CODE_OF_CONDUCT.md",
    "docs/policies/CONTRIBUTING.md",
    "docs/policies/DISCLAIMER.md",
    "docs/policies/README.md",
    "docs/policies/SECURITY.md",
    "docs/public/CHRONICLE_BLURBS.md",
    "docs/public/CHRONICLE_ONE_PAGE.md",
    "docs/public/CLOUDFLARE_PAGES_SETUP.md",
    "docs/public/DEPLOY_STATIC_SITE.md",
    "docs/public/README.md",
    "docs/public/WEBSITE_LAUNCH_PLAN.md",
    "docs/public/WHY_CHRONICLE.md",
    "docs/public/.nojekyll",
    "docs/public/_headers",
    "docs/public/index.html",
    "docs/reference/CHANGELOG.md",
    "docs/reference/Chronicle_Accessibility_Compliance_Statement.md",
    "docs/reference/Chronicle_Technical_Architecture_Deep_Dive.md",
    "docs/reference/README.md",
    "docs/user/EXAMPLES.md",
    "docs/user/METHODOLOGY.md",
    "docs/user/README.md",
    "docs/user/SYSTEM_REQUIREMENTS.md",
    "docs/user/chronicle_help.html",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    ".pyinstaller-cache",
    ".venv",
    "Chronicle.app",
    "__pycache__",
    "build",
    "dist",
    "reaper_tools",
    "review_archives_2026-03-18",
    "venv311",
}

EXCLUDED_PATH_GLOBS = [
    ".worktrees/*",
    "artifacts/*",
    "Chronicle_Source_*.zip",
    "docs/github_rollout/*",
    "dist_windows_bundle/*",
    "input_files/*",
    "output_html/*",
    "windows_builds/*",
]

EXCLUDED_FILE_NAMES = {
    "Check_GitHub_Download_Counts.command",
    ".DS_Store",
    "CONTINUITY.md",
    "Download_Latest_Windows_Artifact.command",
    "api_key.txt",
    "api_keys.json",
    "chronicle.py",
    "chronicle_active_session.json",
    "legacy_extract_core.py",
    "Push_to_GitHub.command",
    "Resume_Chronicle.command",
    "Run_Safe_Batch.command",
    "Run_Windows_GitHub_Build.command",
    "Sync_from_GitHub.command",
    "Update_Samples.command",
    "WAKE_PHRASE.md",
    "user_config.json",
}

EXCLUDED_MAC_RELATIVE_PATHS = {
    "Mac/Check_GitHub_Download_Counts.command",
    "Mac/Download_Latest_Windows_Artifact.command",
    "Mac/Push_to_GitHub.command",
    "Mac/Run_Safe_Batch.command",
    "Mac/Run_Windows_GitHub_Build.command",
    "Mac/Sync_from_GitHub.command",
    "Mac/Update_Samples.command",
}

EXCLUDED_RELATIVE_PATHS = {
    "a11y_queue_harness.py",
    "Mac/mac_native_queue_harness.py",
    "Mac/run_a11y_harness.command",
    "Mac/run_native_queue_harness.command",
    "Mac/run_packaged_memory_stress.command",
    "run_a11y_harness.bat",
    "run_a11y_harness.command",
    "run_debug.py",
    "run_native_queue_harness.command",
    "upgrade_deps.py",
}

ALLOWED_TOOL_PATHS = {
    "tools/build_source_archive.py",
    "tools/check_platform_layout.sh",
    "tools/install_git_hooks.sh",
    "tools/precommit_secret_scan.sh",
    "tools/prepare_public_repo_snapshot.py",
    "tools/release_fileset_check.py",
    "tools/release_regression_offline.py",
    "tools/stage_windows_bundle.py",
}


def should_exclude(rel_path: str) -> bool:
    path_obj = Path(rel_path)
    if rel_path.startswith("docs/github_rollout/") and rel_path in ALLOWED_GITHUB_ROLLOUT_DOCS:
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in path_obj.parts):
        return True
    if path_obj.name in EXCLUDED_FILE_NAMES:
        return True
    if rel_path in EXCLUDED_MAC_RELATIVE_PATHS:
        return True
    if rel_path in EXCLUDED_RELATIVE_PATHS:
        return True
    for pattern in EXCLUDED_PATH_GLOBS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    if rel_path.startswith("docs/branding/"):
        return True
    if rel_path.startswith("docs/public/showcase_assets/"):
        return False
    if rel_path.startswith("docs/") and rel_path not in ALLOWED_DOC_PATHS and rel_path not in ALLOWED_GITHUB_ROLLOUT_DOCS:
        return True
    if rel_path.startswith("tools/") and rel_path not in ALLOWED_TOOL_PATHS:
        return True
    return False


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_file(src_root: Path, dst_root: Path, rel_path: str) -> None:
    src = src_root / rel_path
    dst = dst_root / rel_path
    ensure_parent(dst)
    shutil.copy2(src, dst)


def build_snapshot(repo_root: Path, output_root: Path) -> list[str]:
    copied: list[str] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        if rel_path.startswith("docs/github_rollout/") and rel_path not in ALLOWED_GITHUB_ROLLOUT_DOCS:
            continue
        if should_exclude(rel_path):
            continue
        copy_file(repo_root, output_root, rel_path)
        copied.append(rel_path)

    for src_rel, dst_rel in ROOT_DOC_REPLACEMENTS.items():
        src = repo_root / src_rel
        if not src.exists():
            continue
        dst = output_root / dst_rel
        ensure_parent(dst)
        shutil.copy2(src, dst)
        if dst_rel not in copied:
            copied.append(dst_rel)

    copied.sort()
    manifest = output_root / "PUBLIC_REPO_MANIFEST.txt"
    ensure_parent(manifest)
    manifest.write_text("\n".join(copied) + "\n", encoding="utf-8")
    return copied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a clean Chronicle public repo snapshot.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Source Chronicle repo root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/public_repo_stage/Chronicle",
        help="Destination directory for the staged public repo snapshot.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the output directory before rebuilding the snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_root = Path(args.output)
    if not output_root.is_absolute():
        output_root = (repo_root / output_root).resolve()

    if args.clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    copied = build_snapshot(repo_root, output_root)
    print(f"Prepared public repo snapshot: {output_root}")
    print(f"Included files: {len(copied)}")
    print(f"Manifest: {output_root / 'PUBLIC_REPO_MANIFEST.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
