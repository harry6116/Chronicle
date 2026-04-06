#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from datetime import date
from pathlib import Path


EXCLUDED_DIRS = {
    '.git',
    '.venv',
    'venv311',
    'build',
    'dist',
    'dist_windows_bundle',
    '__pycache__',
    '.pytest_cache',
    '.pyinstaller-cache',
    '.worktrees',
}
EXCLUDED_NAMES = {
    '.DS_Store',
    'api_key.txt',
    'api_keys.json',
    'api_key_gemini.txt',
    'api_key_anthropic.txt',
    'api_key_openai.txt',
    'user_config.json',
    'chronicle_active_session.json',
}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo'}
INCLUDED_TOP_LEVEL = {
    '.github',
    '.githooks',
    'Mac',
    'assets',
    'chronicle_app',
    'docs',
    'hooks',
    'tests',
    'tools',
    'CONTINUITY.md',
    'Chronicle.spec',
    'LICENSE',
    'PLATFORM_LAYOUT.md',
    'build.command',
    'build_windows.bat',
    'build_windows.ps1',
    'build_stamp.txt',
    'chronicle.py',
    'chronicle_core.py',
    'chronicle_gui.py',
    'legacy_extract_core.py',
    'requirements.txt',
    'run_a11y_harness.bat',
    'run_a11y_harness.command',
    'run_native_queue_harness.command',
    'stage_windows_bundle.command',
    'Resume_Chronicle.command',
    'Run_Safe_Batch.command',
    'Run_Windows_GitHub_Build.command',
    'Sync_from_GitHub.command',
    'Update_Samples.command',
    'Download_Latest_Windows_Artifact.command',
    'Push_to_GitHub.command',
}


def should_include(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if not parts or parts[0] not in INCLUDED_TOP_LEVEL:
        return False
    if any(part in EXCLUDED_DIRS for part in parts[:-1]):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.suffix == '.zip':
        return False
    return path.is_file()


def iter_files(root: Path):
    for path in sorted(root.rglob('*')):
        if should_include(path, root):
            yield path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build a Chronicle source archive from the current workspace.')
    parser.add_argument('--date', default=str(date.today()), help='Archive date label in YYYY-MM-DD form.')
    parser.add_argument('--output', default=None, help='Explicit output zip path. Defaults to Chronicle_Source_<date>.zip at repo root.')
    parser.add_argument('--replace-old', action='store_true', help='Remove older Chronicle*Source*.zip files after writing the new archive.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    output = Path(args.output) if args.output else root / f'Chronicle_Source_{args.date}.zip'
    output = output.resolve()
    files = list(iter_files(root))
    if not files:
        raise SystemExit('No files selected for source archive.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.relative_to(root).as_posix())
    if args.replace_old:
        for existing in root.glob('Chronicle*Source*.zip'):
            if existing.resolve() != output:
                existing.unlink()
    print(f'Wrote source archive: {output}')
    print(f'Included files: {len(files)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
