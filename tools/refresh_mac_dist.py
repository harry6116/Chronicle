"""Verify a Mac build and refresh its configured distribution folder."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import tempfile


def resolve_dist_dir(build_root, config_file=None):
    override = os.environ.get('CHRONICLE_MAC_DIST_DIR')
    if override:
        return Path(override).expanduser().resolve()
    config_file = Path(config_file) if config_file else Path.home() / 'Library/Application Support/ChronicleMaintainer/build_paths.json'
    if config_file.is_file():
        config = json.loads(config_file.read_text(encoding='utf-8'))
        configured = config.get('mac_dist_dir')
        if configured:
            path = Path(configured).expanduser()
            if not path.is_absolute():
                raise ValueError('The configured Mac distribution folder must be an absolute path.')
            return path.resolve()
    return Path(build_root).resolve() / 'dist'


def _verify_signature(app):
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)


def _running_app_pids(app):
    executable = str(app / 'Contents/MacOS/Chronicle')
    output = subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True)
    matches = []
    for line in output.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and (fields[1] == executable or fields[1].startswith(executable + ' ')):
            matches.append(int(fields[0]))
    return matches


def _inventory(app):
    items = {}
    for current, directories, files in os.walk(app, followlinks=False):
        for name in directories + files:
            path = Path(current) / name
            relative = path.relative_to(app).as_posix()
            if path.is_symlink():
                items[relative] = ('link', os.readlink(path))
            elif path.is_file():
                items[relative] = ('file', hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(path.stat().st_mode))
    return items


def _verify_app(app, version, build_stamp):
    metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if metadata.get('CFBundleVersion') != version or metadata.get('CFBundleShortVersionString') != version:
        raise ValueError('The Mac app version does not match this build.')
    stamp = (app / 'Contents/Resources/build_stamp.txt').read_text(encoding='utf-8').strip()
    if not build_stamp.strip() or stamp != build_stamp.strip():
        raise ValueError('The Mac app build stamp does not match this build.')
    if not (app / 'Contents/MacOS/Chronicle').is_file():
        raise ValueError('The Mac app executable is missing.')
    _verify_signature(app)


def refresh_mac_dist(source_app, dist_dir, version, build_stamp):
    source_app = Path(source_app).resolve()
    dist_dir = Path(dist_dir).resolve()
    target = dist_dir / 'Chronicle.app'
    _verify_app(source_app, version, build_stamp)
    if source_app == target:
        return target
    if target.is_symlink():
        raise ValueError('The distribution app must not be a symbolic link.')
    if _running_app_pids(target):
        raise RuntimeError('The distribution app is running. Close it before refreshing this build.')
    expected = _inventory(source_app)
    dist_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.chronicle-dist-', dir=dist_dir.parent))
    cleanup = True
    try:
        staged = temporary / 'Chronicle.app'
        previous = temporary / 'previous.app'
        shutil.copytree(source_app, staged, symlinks=True)
        if _inventory(staged) != expected:
            raise RuntimeError('The staged Mac app differs from the completed build.')
        _verify_app(staged, version, build_stamp)
        if _running_app_pids(target):
            raise RuntimeError('The distribution app started during staging. Close it before refreshing this build.')
        had_previous = target.exists()
        if had_previous:
            target.rename(previous)
        try:
            staged.rename(target)
            if _inventory(target) != expected:
                raise RuntimeError('The refreshed distribution app differs from the completed build.')
            _verify_app(target, version, build_stamp)
        except BaseException:
            try:
                if target.exists():
                    target.rename(temporary / 'rejected.app')
                if had_previous:
                    previous.rename(target)
            except BaseException as restore_error:
                cleanup = False
                raise RuntimeError(f'Could not restore the previous app; recovery files remain in {temporary}') from restore_error
            raise
    finally:
        if cleanup:
            shutil.rmtree(temporary)
    return target
