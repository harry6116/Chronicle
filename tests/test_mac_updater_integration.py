import functools
import http.server
import os
import plistlib
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from chronicle_app.services.update_service import build_mac_updater_script


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/interrupted.zip":
            self.send_response(200)
            self.send_header("Content-Length", "10000")
            self.end_headers()
            self.wfile.write(b"incomplete download")
            self.close_connection = True
            return
        super().do_GET()


@unittest.skipUnless(sys.platform == "darwin", "Uses macOS archive and app utilities")
class MacUpdaterIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="chronicle-mac-updater-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "Reader's Apps" / "Chronicle.app"
        self.target.mkdir(parents=True)
        (self.target / "version.txt").write_text("old", encoding="utf-8")
        self.state = self.root / "state.json"
        self.state.write_text('{"preset":"academic","queue":["sample.pdf"]}', encoding="utf-8")
        self.original_state = self.state.read_bytes()
        self.launcher = self.root / "launch.sh"
        self.launcher.write_text('#!/bin/bash\ncat "$1/version.txt" > "$1/../launched.txt"\n', encoding="utf-8")
        self.launcher.chmod(0o700)
        handler = functools.partial(_QuietHandler, directory=str(self.root))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def make_zip(self, *, app=True, executable=True, unsafe=False):
        destination = self.root / "Chronicle.mac.zip"
        with zipfile.ZipFile(destination, "w") as archive:
            if unsafe:
                archive.writestr("../outside.txt", "must not be extracted")
            elif not app:
                archive.writestr("readme.txt", "No app in this download.")
            else:
                archive.writestr("Chronicle.app/Contents/Info.plist", plistlib.dumps({"CFBundleExecutable": "Chronicle"}))
                archive.writestr("Chronicle.app/version.txt", "new")
                if executable:
                    entry = zipfile.ZipInfo("Chronicle.app/Contents/MacOS/Chronicle")
                    entry.create_system = 3
                    entry.external_attr = 0o100755 << 16
                    archive.writestr(entry, "#!/bin/bash\nexit 0\n")
        return destination

    def run_update(self, *, asset="Chronicle.mac.zip", wait_pid=0, fault=None):
        script = build_mac_updater_script(
            asset_url=f"{self.url}/{asset}", app_bundle_path=str(self.target),
            wait_pid=wait_pid, wait_timeout_seconds=1,
            log_dir=str(self.root / "logs"), show_alerts=False,
        )
        # Isolate OS launching; all download, extraction and replacement commands run natively.
        script = script.replace('/usr/bin/open -g -n', shlex.quote(str(self.launcher)))
        if fault == "copy":
            script = script.replace('/usr/bin/ditto "$source_app" "$candidate_app"', '/usr/bin/false')
        if fault == "launch":
            script = script.replace(shlex.quote(str(self.launcher)) + ' "$app_bundle_path"', '/usr/bin/false')
        if fault == "swap":
            script = script.replace('mv "$candidate_app" "$app_bundle_path"', '/usr/bin/false')
        path = self.root / "apply-update.sh"
        path.write_text(script, encoding="utf-8")
        syntax = subprocess.run(["/bin/bash", "-n", str(path)], capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        result = subprocess.run(["/bin/bash", str(path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(self.state.read_bytes(), self.original_state)
        self.assertFalse(list(self.target.parent.glob(".ChronicleUpdate.*")))
        return result

    def assert_old_app_preserved(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / "version.txt").read_text(), "old")
        self.assertFalse((self.target.parent / "launched.txt").exists())

    def test_native_download_extract_replace_and_launch_request(self):
        self.make_zip()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / "version.txt").read_text(), "new")
        self.assertEqual((self.target.parent / "launched.txt").read_text(), "new")
        self.assertFalse(self.target.with_name("Chronicle.app.previous-update").exists())

    def test_running_app_aborts_before_replacement(self):
        self.make_zip()
        self.assert_old_app_preserved(self.run_update(wait_pid=os.getpid()))
        self.assertIn("Chronicle is still running", (self.root / "logs/Updater.log").read_text())

    def test_failed_download_preserves_installed_app(self):
        self.assert_old_app_preserved(self.run_update(asset="missing.zip"))

    def test_interrupted_download_preserves_installed_app(self):
        self.assert_old_app_preserved(self.run_update(asset="interrupted.zip"))

    def test_corrupt_zip_preserves_installed_app(self):
        (self.root / "Chronicle.mac.zip").write_bytes(b"not a zip")
        self.assert_old_app_preserved(self.run_update())

    def test_archive_without_app_preserves_installed_app(self):
        self.make_zip(app=False)
        self.assert_old_app_preserved(self.run_update())

    def test_archive_without_executable_preserves_installed_app(self):
        self.make_zip(executable=False)
        self.assert_old_app_preserved(self.run_update())

    def test_unsafe_archive_paths_are_rejected_before_extraction(self):
        self.make_zip(unsafe=True)
        self.assert_old_app_preserved(self.run_update())
        self.assertFalse((self.root / "outside.txt").exists())

    def test_failed_copy_preserves_installed_app(self):
        self.make_zip()
        self.assert_old_app_preserved(self.run_update(fault="copy"))

    def test_failed_launch_restores_installed_app(self):
        self.make_zip()
        self.assert_old_app_preserved(self.run_update(fault="launch"))
        self.assertIn("Previous app restored", (self.root / "logs/Updater.log").read_text())

    def test_failed_swap_restores_installed_app(self):
        self.make_zip()
        self.assert_old_app_preserved(self.run_update(fault="swap"))

    def test_unwritable_destination_preserves_installed_app(self):
        self.make_zip()
        self.target.parent.chmod(0o500)
        try:
            self.assert_old_app_preserved(self.run_update())
        finally:
            self.target.parent.chmod(0o700)

    def test_existing_recovery_backup_is_preserved(self):
        backup = self.target.with_name("Chronicle.app.previous-update")
        backup.mkdir()
        (backup / "version.txt").write_text("recovery", encoding="utf-8")
        self.make_zip()
        self.assert_old_app_preserved(self.run_update())
        self.assertEqual((backup / "version.txt").read_text(), "recovery")


if __name__ == "__main__":
    unittest.main()
