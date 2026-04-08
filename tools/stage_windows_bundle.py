#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


BUNDLE_NAME = "Chronicle_Windows_Bundle"
REQUIRED_PATHS = [
    "chronicle_gui.py",
    "chronicle_runtime.py",
    "chronicle_core.py",
    "chronicle_app",
    "capture_windows_build_diagnostics.bat",
    "build_windows.ps1",
    "requirements.txt",
    "build_windows.bat",
    "run_a11y_harness.bat",
    "LICENSE",
    "assets",
    "docs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage a portable Windows build bundle from the current Chronicle workspace."
    )
    parser.add_argument(
        "--dest",
        default="dist_windows_bundle",
        help="Destination folder where the staged bundle will be created.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing staged bundle if present.",
    )
    return parser.parse_args()


def copy_path(src: Path, dest: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def write_manifest(root: Path, bundle_root: Path) -> None:
    manifest = bundle_root / "WINDOWS_BUNDLE_MANIFEST.txt"
    lines = [
        "Chronicle Windows Build Bundle",
        "",
        "Purpose:",
        "This folder is the minimum staged project layout required to run Chronicle's Windows build script.",
        "",
        "How to use on Windows:",
        "1. Copy this entire folder to the Windows machine.",
        "2. Keep the folder structure intact.",
        "3. Place it in a normal user-writable folder such as Documents, Downloads, or Desktop.",
        "4. Do NOT place it under Program Files, the Windows root, or another admin-protected path.",
        "5. Open the bundle folder.",
        "6. Run build_windows.bat from the bundle root.",
        "   Chronicle will route that launcher through capture_windows_build_diagnostics.bat when available.",
        "7. Check the generated windows_build_diagnostic_YYYYMMDD_HHMMSS.log beside the build scripts.",
        "8. If the launcher fell back to the PowerShell builder, also check %APPDATA%\\Chronicle\\logs\\windows_build_YYYYMMDD_HHMMSS.log",
        "",
        "Important:",
        "Copying only the Windows subfolder is not enough. The build needs the files and folders listed below beside it.",
        "The diagnostic batch file is included on purpose because it is the primary Windows build path.",
        "Avoid building from read-only, cloud-locked, or admin-protected folders to reduce Access Denied failures.",
        "",
        "Included paths:",
    ]
    lines.extend(f"- {path}" for path in REQUIRED_PATHS)
    lines.extend(
        [
            "",
            f"Staged from: {root}",
            f"Bundle root: {bundle_root}",
            "",
            "Recommended destination on Windows:",
            "A normal local folder such as C:\\Users\\<you>\\Documents\\Chronicle_Windows_Bundle",
            "An internal drive is recommended for simplicity, but any readable/writeable local folder with the full bundle is fine.",
            "Best practice: copy the bundle to a fresh folder that you own completely, then build from there.",
        ]
    )
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    missing = [path for path in REQUIRED_PATHS if not (root / path).exists()]
    if missing:
        print("Cannot stage Windows bundle. Missing required paths:")
        for path in missing:
            print(f"- {path}")
        return 1

    dest_root = (root / args.dest).resolve()
    bundle_root = dest_root / BUNDLE_NAME

    if bundle_root.exists():
        if not args.force:
            print(f"Bundle already exists: {bundle_root}")
            print("Re-run with --force to replace it.")
            return 1
        shutil.rmtree(bundle_root)

    bundle_root.mkdir(parents=True, exist_ok=True)
    for rel_path in REQUIRED_PATHS:
        copy_path(root / rel_path, bundle_root / rel_path)

    write_manifest(root, bundle_root)

    print("Windows bundle staged successfully.")
    print(f"Bundle root: {bundle_root}")
    print(f"Manifest: {bundle_root / 'WINDOWS_BUNDLE_MANIFEST.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
