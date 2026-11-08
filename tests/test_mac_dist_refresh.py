import os
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from tools.refresh_mac_dist import refresh_mac_dist, resolve_dist_dir


class MacDistRefreshTest(unittest.TestCase):
    def make_app(self, parent, version='1.1.6', stamp='test-build', payload=b'new executable'):
        app = parent / 'Chronicle.app'
        (app / 'Contents/MacOS').mkdir(parents=True)
        (app / 'Contents/Resources').mkdir()
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleVersion':version, 'CFBundleShortVersionString':version}))
        (app / 'Contents/MacOS/Chronicle').write_bytes(payload)
        (app / 'Contents/Resources/build_stamp.txt').write_text(stamp+'\n')
        if os.name != 'nt':
            (app / 'Contents/Resources/alias').symlink_to('build_stamp.txt')
        return app

    def test_replaces_stale_app_and_removes_temporary_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            source=self.make_app(root/'build')
            target=self.make_app(root/'dist',version='1.1.3',payload=b'old')
            with patch('tools.refresh_mac_dist._verify_signature'), patch('tools.refresh_mac_dist._running_app_pids',return_value=[]):
                result=refresh_mac_dist(source,root/'dist','1.1.6','test-build')
            self.assertEqual(result,target)
            self.assertEqual((target/'Contents/MacOS/Chronicle').read_bytes(),b'new executable')
            if os.name != 'nt':
                self.assertEqual(os.readlink(target/'Contents/Resources/alias'),'build_stamp.txt')
            self.assertEqual(sorted(p.name for p in root.iterdir()),['build','dist'])
            self.assertEqual(sorted(p.name for p in (root/'dist').iterdir()),['Chronicle.app'])

    def test_failed_replacement_verification_restores_previous_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            source=self.make_app(root/'build')
            target=self.make_app(root/'dist',version='1.1.3',payload=b'old')
            def signature(path):
                if Path(path)==target:
                    raise RuntimeError('simulated replacement verification failure')
            with patch('tools.refresh_mac_dist._verify_signature',side_effect=signature), patch('tools.refresh_mac_dist._running_app_pids',return_value=[]):
                with self.assertRaisesRegex(RuntimeError,'simulated'):
                    refresh_mac_dist(source,root/'dist','1.1.6','test-build')
            self.assertEqual((target/'Contents/MacOS/Chronicle').read_bytes(),b'old')

    def test_rejects_wrong_version_or_build_stamp_without_replacing(self):
        for version,stamp in [('1.1.3','test-build'),('1.1.6','stale-build')]:
            with self.subTest(version=version,stamp=stamp), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve()
                source=self.make_app(root/'build',version=version,stamp=stamp)
                target=self.make_app(root/'dist',payload=b'keep')
                with patch('tools.refresh_mac_dist._verify_signature'), patch('tools.refresh_mac_dist._running_app_pids',return_value=[]):
                    with self.assertRaises(ValueError):
                        refresh_mac_dist(source,root/'dist','1.1.6','test-build')
                self.assertEqual((target/'Contents/MacOS/Chronicle').read_bytes(),b'keep')

    def test_does_not_replace_a_running_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            source=self.make_app(root/'build')
            target=self.make_app(root/'dist',payload=b'keep')
            with patch('tools.refresh_mac_dist._verify_signature'), patch('tools.refresh_mac_dist._running_app_pids',return_value=[123]):
                with self.assertRaisesRegex(RuntimeError,'running'):
                    refresh_mac_dist(source,root/'dist','1.1.6','test-build')
            self.assertEqual((target/'Contents/MacOS/Chronicle').read_bytes(),b'keep')

    def test_building_in_final_dist_still_verifies_the_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=self.make_app(Path(tmp).resolve()/'dist')
            with patch('tools.refresh_mac_dist._verify_signature') as verify:
                self.assertEqual(refresh_mac_dist(source,source.parent,'1.1.6','test-build'),source)
                verify.assert_called_once_with(source.resolve())

    def test_destination_uses_override_then_private_config_then_build_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            config=root/'build_paths.json'
            config.write_text(json.dumps({'mac_dist_dir':str(root/'configured')}))
            with patch.dict(os.environ,{'CHRONICLE_MAC_DIST_DIR':str(root/'override')}):
                self.assertEqual(resolve_dist_dir(root,config),root/'override')
            with patch.dict(os.environ,{},clear=True):
                self.assertEqual(resolve_dist_dir(root,config),root/'configured')
                self.assertEqual(resolve_dist_dir(root,root/'missing.json'),root/'dist')


if __name__=='__main__':
    unittest.main()
