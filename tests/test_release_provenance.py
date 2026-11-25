import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import release_provenance as provenance


class ReleaseProvenanceTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for relative in provenance.SOURCE_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'APP_VERSION = "1.2.3"\n')
        self.windows = self.root / 'dist' / 'Chronicle'
        (self.windows / '_internal').mkdir(parents=True)
        (self.windows / 'Chronicle.exe').write_bytes(b'executable')
        (self.windows / '_internal/build_stamp.txt').write_text('a build stamp\n')
        self.runtime = self.windows / '_internal/runtime.dll'
        self.runtime.write_bytes(b'fresh runtime')

    def test_rejects_older_source_with_the_same_version(self):
        identity = provenance.source_identity(self.source)
        provenance.record_build(self.source, self.windows, 'windows', identity, 'a build stamp')
        (self.source / 'chronicle_core.py').write_text('different source, same version\n')
        with self.assertRaisesRegex(ValueError, 'source has changed'):
            provenance.verify_build(self.source, self.windows, 'windows')

    def test_rejects_mixed_runtime_behind_matching_executable_and_stamp(self):
        identity = provenance.source_identity(self.source)
        provenance.record_build(self.source, self.windows, 'windows', identity, 'a build stamp')
        provenance.verify_build(self.source, self.windows, 'windows')
        self.runtime.write_bytes(b'older runtime')
        with self.assertRaisesRegex(ValueError, 'app files have changed'):
            provenance.verify_build(self.source, self.windows, 'windows')
        self.runtime.unlink()
        with self.assertRaisesRegex(ValueError, 'app files have changed'):
            provenance.verify_build(self.source, self.windows, 'windows')

    def test_receipt_cannot_be_created_after_a_source_edit_mid_build(self):
        identity = provenance.source_identity(self.source)
        (self.source / 'chronicle_core.py').write_text('updated during build\n')
        with self.assertRaisesRegex(ValueError, 'source has changed'):
            provenance.record_build(self.source, self.windows, 'windows', identity, 'a build stamp')
        self.assertFalse(provenance.receipt_path(self.windows, 'windows').exists())

    def test_source_identity_is_stable_across_checkout_line_endings(self):
        identity = provenance.source_identity(self.source)
        path = self.source / 'chronicle_core.py'
        path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
        self.assertEqual(provenance.source_identity(self.source), identity)

    def test_install_restores_previous_windows_app_if_final_verification_fails(self):
        identity = provenance.source_identity(self.source)
        provenance.record_build(self.source, self.windows, 'windows', identity, 'a build stamp')
        target = self.root / 'installed'
        target.mkdir()
        (target / 'Chronicle.exe').write_bytes(b'previous executable')
        verify = provenance.verify_build

        def break_target(root, app, platform):
            if app == target:
                raise ValueError('copy changed')
            return verify(root, app, platform)

        with patch.object(provenance, 'verify_build', side_effect=break_target):
            with self.assertRaisesRegex(ValueError, 'copy changed'):
                provenance.install_windows(self.source, self.windows, target)
        self.assertEqual((target / 'Chronicle.exe').read_bytes(), b'previous executable')
        self.assertEqual(list(self.root.glob('chronicle-install-*')), [])

    def test_release_record_binds_the_tag_and_both_packaged_files(self):
        mac, windows = self.root / 'mac.zip', self.root / 'windows.zip'
        mac.write_bytes(b'first mac zip')
        windows.write_bytes(b'first windows zip')
        original = provenance.release_record(self.source, 'v1.2.3', mac, windows)
        windows.write_bytes(b'older windows zip with the same filename')
        changed = provenance.release_record(self.source, 'v1.2.3', mac, windows)
        self.assertEqual(original['mac'], changed['mac'])
        self.assertNotEqual(original['windows'], changed['windows'])
        with self.assertRaisesRegex(ValueError, 'tag differs'):
            provenance.release_record(self.source, 'v1.2.2', mac, windows)
