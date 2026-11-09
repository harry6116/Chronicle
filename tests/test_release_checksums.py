import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(Path('/usr/libexec/PlistBuddy').exists(), 'Mac release packager')
class ReleaseChecksumsTest(unittest.TestCase):
    def test_packager_replaces_obsolete_checksums_with_both_current_zips(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            mac = temporary / 'Chronicle.app'
            (mac / 'Contents/MacOS').mkdir(parents=True)
            (mac / 'Contents/MacOS/Chronicle').write_bytes(b'disposable Mac fixture')
            notes = ROOT / 'docs/github_rollout/RELEASE_NOTES_CURRENT.md'
            version = notes.read_text().splitlines()[0].split()[-1]
            (mac / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString': version}))
            windows = temporary / 'Chronicle'
            embedded = windows / '_internal/docs/github_rollout/RELEASE_NOTES_CURRENT.md'
            embedded.parent.mkdir(parents=True)
            embedded.write_bytes(notes.read_bytes())
            (windows / 'Chronicle.exe').write_bytes(b'disposable Windows fixture')
            release = temporary / 'releases'
            release.mkdir()
            (release / 'checksums.sha256').write_text('obsolete checksum\n')
            environment = dict(os.environ, CHRONICLE_MAC_APP_DIR=str(mac),
                               CHRONICLE_WINDOWS_APP_DIR=str(windows),
                               CHRONICLE_RELEASE_ASSET_DIR=str(release), CHRONICLE_SKIP_OPEN='1',
                               CHRONICLE_PUBLIC_SNAPSHOT_DIR=str(temporary / 'public-snapshot'))
            result = subprocess.run(['bash', str(ROOT / 'Mac/Package_Release_Apps.command')],
                                    env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = {}
            for name in ('Chronicle.mac.zip', 'Chronicle.windows.zip'):
                archive = release / name
                with zipfile.ZipFile(archive) as package:
                    self.assertIsNone(package.testzip())
                expected[name] = hashlib.sha256(archive.read_bytes()).hexdigest()
            actual = {}
            for line in (release / 'checksums.sha256').read_text().splitlines():
                checksum, name = line.split()
                actual[name] = checksum
            self.assertEqual(actual, expected)
            self.assertFalse((release / '.packaging-staging').exists())
