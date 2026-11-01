from pathlib import Path
import json
import unittest

from chronicle_app.services import update_service


class _Response:
    def __init__(self, payload):
        self.payload = payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def _release(tag, assets, body=""):
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/harry6116/Chronicle/releases/tag/{tag}",
        "body": body,
        "assets": [
            {"name": name, "browser_download_url": f"https://downloads.example/{name}"}
            for name in assets
        ],
    }


class UpdateServiceTest(unittest.TestCase):
    def test_reminder_is_only_due_for_a_newer_valid_version(self):
        for version, expected in (("1.2.0", "1.2.0"), ("1.1.1", ""), ("1.0.0", ""), ("invalid", ""), (None, "")):
            with self.subTest(version=version):
                self.assertEqual(update_service.pending_update_reminder({"update_reminder_version": version}, "1.1.1"), expected)
        self.assertEqual(update_service.pending_update_reminder({}, "1.1.1"), "")
    def test_update_check_ignores_drafts_and_prereleases(self):
        stable = _release("v1.2.0", ["Chronicle.mac.zip"], body="Stable improvements.")
        preview = dict(_release("v2.0.0-beta.1", ["Chronicle.mac.zip"], body="Preview changes."), prerelease=True)
        draft = dict(_release("v3.0.0", ["Chronicle.mac.zip"], body="Draft changes."), draft=True)
        result = update_service.check_for_updates(
            "1.1.1", system_name="Darwin",
            urlopen=lambda _request, timeout: _Response(json.dumps([draft, preview, stable])),
        )
        self.assertEqual(result.status, "available")
        self.assertEqual(result.latest_version, "1.2.0")
        self.assertNotIn("Preview changes", result.notes)
        self.assertNotIn("Draft changes", result.notes)

    def test_preview_only_feed_does_not_offer_an_update(self):
        preview = dict(_release("v2.0.0-beta.1", ["Chronicle.windows.zip"]), prerelease=True)
        result = update_service.check_for_updates(
            "1.1.1", system_name="Windows",
            urlopen=lambda _request, timeout: _Response(json.dumps([preview])),
        )
        self.assertEqual(result.status, "no_platform_release")
        self.assertIsNone(result.asset)

    def test_latest_platform_release_skips_releases_without_matching_asset(self):
        releases = update_service.parse_releases(
            json.dumps(
                [
                    _release("v1.3.0", ["Chronicle.mac.zip"]),
                    _release("v1.2.0", ["Chronicle.windows.zip"]),
                    _release("v1.1.0", ["Chronicle.windows.zip", "Chronicle.mac.zip"]),
                ]
            )
        )

        release, asset = update_service.latest_platform_release(releases, "Windows")

        self.assertEqual(release.tag_name, "v1.2.0")
        self.assertEqual(asset.name, "Chronicle.windows.zip")

    def test_check_for_updates_reports_available_platform_asset(self):
        payload = json.dumps(
            [
                _release("v1.2.0", ["Chronicle.windows.zip"], body="# Chronicle 1.2.0\n\n- Built-in updater."),
            ]
        )

        def fake_urlopen(_request, timeout):
            self.assertEqual(timeout, 20)
            return _Response(payload)

        result = update_service.check_for_updates("1.1.1", system_name="Windows", urlopen=fake_urlopen)

        self.assertEqual(result.status, "available")
        self.assertEqual(result.latest_version, "1.2.0")
        self.assertEqual(result.asset.name, "Chronicle.windows.zip")
        self.assertIn("Built-in updater.", result.notes)

    def test_check_for_updates_reports_mac_available_without_auto_install_claim(self):
        payload = json.dumps([_release("v1.2.0", ["Chronicle.mac.zip"])])

        result = update_service.check_for_updates(
            "1.1.1",
            system_name="Darwin",
            urlopen=lambda _request, timeout: _Response(payload),
        )

        self.assertEqual(result.status, "available")
        self.assertEqual(result.asset.name, "Chronicle.mac.zip")
        self.assertTrue(update_service.platform_supports_automatic_install("Darwin"))

    def test_release_notes_remove_duplicate_heading_and_markdown_bullets(self):
        notes = update_service.format_release_notes_for_dialog(
            update_service.remove_duplicate_release_heading("# Chronicle 1.2.0\n\n- Fixed updates.", "v1.2.0")
        )

        self.assertNotIn("#", notes)
        self.assertNotIn("Chronicle 1.2.0", notes)
        self.assertIn("Fixed updates.", notes)

    def test_windows_updater_script_preserves_user_state_and_uses_asset_url(self):
        script = update_service.build_windows_updater_script(
            asset_url="https://downloads.example/Chronicle.windows.zip",
            target_dir=r"C:\Chronicle",
            executable_path=r"C:\Chronicle\Chronicle.exe",
            wait_pid=123,
        )

        self.assertIn("Chronicle.windows.zip", script)
        self.assertIn("Settings", script)
        self.assertIn("Logs", script)
        self.assertIn("Backups", script)
        self.assertIn("Chronicle.exe", script)
        self.assertIn("Wait-Process", script)

    def test_windows_updater_refuses_a_running_app_before_replacement(self):
        script = update_service.build_windows_updater_script(
            asset_url="https://downloads.example/update.zip", target_dir=r"C:\Chronicle",
            executable_path=r"C:\Chronicle\Chronicle.exe", wait_pid=123,
        )
        self.assertIn("Chronicle is still running", script)
        self.assertLess(script.index("Chronicle is still running"), script.index("Move-Item -LiteralPath $Payload.target_dir"))
        self.assertIn("Assert-ChronicleStopped", script)

    def test_windows_updater_prepares_and_restores_a_backup(self):
        script = update_service.build_windows_updater_script(
            asset_url="https://downloads.example/update.zip", target_dir=r"C:\Chronicle",
            executable_path=r"C:\Chronicle\Chronicle.exe", wait_pid=123,
        )
        self.assertIn(".previous-update", script)
        self.assertIn("A previous update backup already exists", script)
        self.assertIn("Move-Item -LiteralPath $BackupPath -Destination $Payload.target_dir", script)
        self.assertLess(script.index("Copy-Item -LiteralPath"), script.index("Move-Item -LiteralPath $Payload.target_dir"))
        self.assertIn("finally", script)
        self.assertIn("unsafe paths", script)

    def test_mac_updater_script_replaces_app_and_clears_quarantine(self):
        script = update_service.build_mac_updater_script(
            asset_url="https://downloads.example/Chronicle.mac.zip",
            app_bundle_path="/Applications/Chronicle.app",
            wait_pid=456,
        )

        self.assertIn("Chronicle.mac.zip", script)
        self.assertIn("Chronicle.app", script)
        self.assertIn("xattr -rd com.apple.quarantine", script)
        self.assertIn("/usr/bin/open", script)
        self.assertIn('/usr/bin/open -g -n "$app_bundle_path"', script)
        self.assertIn("Chronicle.app.previous-update", script)

    def test_mac_updater_stops_if_running_process_does_not_exit(self):
        script = update_service.build_mac_updater_script(
            asset_url="https://downloads.example/Chronicle.mac.zip",
            app_bundle_path="/Applications/Chronicle.app", wait_pid=456,
        )
        self.assertIn("Chronicle is still running", script)
        self.assertLess(script.index("Chronicle is still running"), script.index('mv "$app_bundle_path"'))

    def test_mac_updater_does_not_require_system_python(self):
        script = update_service.build_mac_updater_script(
            asset_url="https://downloads.example/Chronicle.mac.zip",
            app_bundle_path="/Applications/Chronicle.app", wait_pid=456,
        )
        self.assertNotIn("/usr/bin/python3", script)

    def test_mac_updater_stages_replacement_before_moving_installed_app(self):
        script = update_service.build_mac_updater_script(
            asset_url="https://downloads.example/Chronicle.mac.zip",
            app_bundle_path="/Applications/Chronicle.app", wait_pid=456,
        )
        self.assertLess(script.index('ditto "$source_app" "$candidate_app"'), script.index('mv "$app_bundle_path"'))

    def test_mac_updater_shell_quotes_paths_and_urls(self):
        script = update_service.build_mac_updater_script(
            asset_url="https://downloads.example/it's.zip?x=$(false)",
            app_bundle_path="/Applications/Reader's Folder/Chronicle.app", wait_pid=0,
        )
        self.assertNotIn("PAYLOAD_JSON", script)
        self.assertIn("'\"'\"'", script)

    def test_resolve_mac_app_bundle_from_packaged_executable_path(self):
        path = update_service.resolve_mac_app_bundle("/Applications/Chronicle.app/Contents/MacOS/Chronicle")

        self.assertEqual(path, str(Path("/Applications/Chronicle.app").resolve()))


if __name__ == "__main__":
    unittest.main()
