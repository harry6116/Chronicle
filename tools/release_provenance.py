"""Verify the source and file inventories of Chronicle release candidates."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import tempfile


SOURCE_FILES = ('chronicle_gui.py', 'chronicle_core.py', 'chronicle_runtime.py', 'requirements.txt')
SOURCE_FOLDERS = ('chronicle_app', 'hooks', 'assets/icons')
BUILD_RECEIPT = 'chronicle-build.json'
RELEASE_RECEIPT = 'chronicle-release.json'


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity_hash(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def source_identity(root):
    entry = root / 'chronicle_gui.py'
    version = next(
        ast.literal_eval(node.value)
        for node in ast.parse(entry.read_text(encoding='utf-8')).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'APP_VERSION' for target in node.targets)
    )
    paths = [root / relative for relative in SOURCE_FILES]
    for directory in SOURCE_FOLDERS:
        paths.extend(path for path in (root / directory).rglob('*')
                     if path.is_file() and not path.name.startswith('.')
                     and '__pycache__' not in path.parts and path.suffix != '.pyc')
    files = {}
    for path in paths:
        data = path.read_bytes()
        if path.suffix in {'.py', '.txt', '.svg'}:
            data = data.replace(b'\r\n', b'\n')
        files[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()
    return {'version': version, 'source': identity_hash(files)}


def receipt_path(app, platform):
    return app / BUILD_RECEIPT if platform == 'windows' else app.with_suffix('.build.json')


def app_inventory(app, platform):
    files = {}
    for current, dirs, names in os.walk(app, followlinks=False):
        for name in dirs + names:
            path = Path(current) / name
            relative = path.relative_to(app).as_posix()
            if platform == 'windows' and relative == BUILD_RECEIPT:
                continue
            if path.is_symlink():
                files[relative] = ['link', os.readlink(path)]
            elif path.is_file():
                files[relative] = ['file', file_hash(path)]
    if not files:
        raise ValueError('The build output is empty.')
    return identity_hash(files)


def read_stamp(app, platform, version):
    if platform == 'windows':
        executable, stamp = app / 'Chronicle.exe', app / '_internal/build_stamp.txt'
    else:
        executable = app / 'Contents/MacOS/Chronicle'
        stamp = app / 'Contents/Resources/build_stamp.txt'
        metadata = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
        if any(metadata.get(key) != version for key in ('CFBundleVersion', 'CFBundleShortVersionString')):
            raise ValueError('The Mac bundle version differs from the source version.')
        subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    if not executable.is_file():
        raise ValueError(f'The {platform} executable is missing.')
    return stamp.read_text(encoding='utf-8-sig').strip()


def write_receipt(path, contents):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(contents, stream, sort_keys=True)
            stream.write('\n')
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def load_receipt(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def record_build(root, app, platform, identity, stamp):
    if source_identity(root) != identity:
        raise ValueError('The source has changed during the build. Rebuild from the current source.')
    if not stamp or read_stamp(app, platform, identity['version']) != stamp:
        raise ValueError(f'The {platform} build stamp differs from the current build.')
    receipt = dict(identity, platform=platform, stamp=stamp, files=app_inventory(app, platform))
    write_receipt(receipt_path(app, platform), receipt)


def verify_build(root, app, platform):
    receipt = load_receipt(receipt_path(app, platform))
    identity = source_identity(root)
    if receipt['platform'] != platform or any(receipt[key] != value for key, value in identity.items()):
        raise ValueError(f'The {platform} source has changed since this build. Rebuild the paired apps.')
    if read_stamp(app, platform, identity['version']) != receipt['stamp']:
        raise ValueError(f'The {platform} build stamp differs from the verified build.')
    if app_inventory(app, platform) != receipt['files']:
        raise ValueError(f'The {platform} app files have changed. Transfer or rebuild the complete app.')
    return receipt


def install_windows(root, source, target):
    verify_build(root, source, 'windows')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='chronicle-install-', dir=target.parent))
    preserve_recovery = False
    try:
        stage = temporary / 'new'
        previous = temporary / 'previous'
        shutil.copytree(source, stage, symlinks=True)
        verify_build(root, stage, 'windows')
        if target.is_symlink():
            raise ValueError('The Windows distribution destination is a symbolic link.')
        try:
            if target.exists():
                target.rename(previous)
            stage.rename(target)
            verify_build(root, target, 'windows')
        except BaseException:
            if previous.exists():
                try:
                    if target.exists():
                        target.rename(temporary / 'rejected')
                    previous.rename(target)
                except OSError as exc:
                    preserve_recovery = True
                    raise OSError(f'The previous Windows app is saved in {previous}.') from exc
            elif not stage.exists() and target.exists():
                target.rename(temporary / 'rejected')
            raise
    finally:
        if not preserve_recovery:
            shutil.rmtree(temporary)


def release_record(root, tag, mac_zip, windows_zip):
    identity = source_identity(root)
    if tag != 'v' + identity['version']:
        raise ValueError('The release tag differs from the current source version.')
    return dict(identity, tag=tag, mac=file_hash(mac_zip), windows=file_hash(windows_zip))


def verify_public_source(root, repo, revision):
    with tempfile.TemporaryDirectory(prefix='chronicle-public-source-') as directory:
        destination = Path(directory).resolve()
        archive = destination / 'source.tar'
        subprocess.run(['git', '-C', str(repo), 'archive', '-o', str(archive), revision,
                        *SOURCE_FILES, *SOURCE_FOLDERS], check=True)
        with tarfile.open(archive) as source:
            for member in source:
                path = destination / member.name
                if not member.isfile():
                    continue
                if not path.resolve().is_relative_to(destination):
                    raise ValueError('The public source archive contains an invalid path.')
                path.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as stream, path.open('xb') as output:
                    shutil.copyfileobj(stream, output)
        if source_identity(destination) != source_identity(root):
            raise ValueError('The selected public commit differs from the current app source.')


def mirror_release(source, destinations):
    names = ('Chronicle.mac.zip', 'Chronicle.windows.zip', 'checksums.sha256', RELEASE_RECEIPT)
    expected = {name: file_hash(source / name) for name in names}
    for target in destinations:
        if target == source.resolve():
            continue
        with tempfile.TemporaryDirectory(prefix='chronicle-packages-', dir=target) as temporary:
            stage = Path(temporary)
            for name in names:
                shutil.copyfile(source / name, stage / name)
                if file_hash(stage / name) != expected[name]:
                    raise ValueError('The mirrored ZIPs or verification files changed while copying.')
            for name in names:
                (stage / name).replace(target / name)
        if any(file_hash(target / name) != expected[name] for name in names):
            raise ValueError('The mirrored release folder failed verification.')
        print(f'Verified mirrored release folder: {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    source = commands.add_parser('source')
    source.add_argument('receipt', type=Path)
    for action in ('record-build', 'verify-build'):
        build = commands.add_parser(action)
        build.add_argument('platform', choices=('mac', 'windows'))
        build.add_argument('app', type=Path)
        if action == 'record-build':
            build.add_argument('identity', type=Path)
            build.add_argument('stamp')
    install = commands.add_parser('install-windows')
    install.add_argument('source', type=Path)
    install.add_argument('target', type=Path)
    public = commands.add_parser('verify-public-source')
    public.add_argument('repository', type=Path)
    public.add_argument('revision')
    mirror = commands.add_parser('mirror-release')
    mirror.add_argument('source', type=Path)
    for action in ('record-release', 'verify-release'):
        release = commands.add_parser(action)
        release.add_argument('receipt', type=Path)
        release.add_argument('tag')
        release.add_argument('mac', type=Path)
        release.add_argument('windows', type=Path)
        release.add_argument('mac_app', type=Path)
        release.add_argument('windows_app', type=Path)
        if action == 'record-release':
            release.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'source':
            write_receipt(args.receipt, source_identity(args.root))
        elif args.command == 'record-build':
            record_build(args.root, args.app, args.platform, load_receipt(args.identity), args.stamp)
        elif args.command == 'verify-build':
            verify_build(args.root, args.app, args.platform)
        elif args.command == 'install-windows':
            install_windows(args.root, args.source, args.target)
        elif args.command == 'verify-public-source':
            verify_public_source(args.root, args.repository, args.revision)
        elif args.command == 'mirror-release':
            from refresh_mac_dist import configured_dirs

            mirror_release(args.source, configured_dirs('release_asset_mirror_dirs'))
        else:
            record = release_record(args.root, args.tag, args.mac, args.windows)
            record['builds'] = {
                'mac': verify_build(args.root, args.mac_app, 'mac'),
                'windows': verify_build(args.root, args.windows_app, 'windows'),
            }
            if args.command == 'record-release':
                if any(record[key] != value for key, value in load_receipt(args.source).items()):
                    raise ValueError('The source has changed during packaging. Package the paired apps again.')
                write_receipt(args.receipt, record)
            elif load_receipt(args.receipt) != record:
                raise ValueError('The release ZIPs or source differ from the verified package pair. Package both apps again.')
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Chronicle verification failed: {exc}\n')


if __name__ == '__main__':
    main()
