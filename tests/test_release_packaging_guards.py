import unittest
from pathlib import Path

from tools import prepare_public_repo_snapshot
from tools import stage_windows_bundle


ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingGuardsTest(unittest.TestCase):
    def test_windows_staging_does_not_require_offline_pack(self):
        self.assertNotIn("offline_pack", stage_windows_bundle.REQUIRED_PATHS)
        self.assertTrue(prepare_public_repo_snapshot.should_exclude("offline_pack/models/blobs/model"))

    def test_release_packager_creates_app_zips_only(self):
        script = (ROOT / "Mac" / "Package_Release_Apps.command").read_text(encoding="utf-8")

        self.assertIn("release_version_from_notes", script)
        self.assertIn("CFBundleShortVersionString", script)
        self.assertIn("App versions do not match", script)
        self.assertLess(script.index("App versions do not match"), script.index('mkdir -p "$RELEASE_DIR"'))
        self.assertIn("Chronicle.windows.zip", script)
        self.assertIn("Chronicle.mac.zip", script)
        self.assertIn('--repo-root "$ROOT_DIR"', script)
        self.assertIn('--output "$SNAPSHOT_DIR"', script)
        self.assertIn("zip_slim_app_package", script)
        self.assertIn("zip_slim_mac_release_package", script)
        self.assertIn("Open Me First.command", script)
        self.assertIn("assert_no_embedded_offline_payload", script)
        self.assertIn("Private Offline Mode now uses the user's existing Ollama installation", script)
        self.assertNotIn("CHRONICLE_OFFLINE_RELEASE_DIR", script)
        self.assertNotIn("Chronicle.offline-pack.zip", script)
        self.assertNotIn("split_offline_pack_for_upload", script)
        self.assertNotIn("require_offline_pack_source", script)

    def test_release_publisher_uploads_app_zips_only(self):
        script = (ROOT / "Mac" / "Publish_GitHub_Release.command").read_text(encoding="utf-8")

        self.assertIn("GITHUB_RELEASE_ASSET_SIZE_LIMIT_BYTES=2147483648", script)
        self.assertIn('check_release_asset_size "$MAC_ASSET" "Mac asset"', script)
        self.assertIn('check_release_asset_size "$WINDOWS_ASSET" "Windows asset"', script)
        self.assertIn("uploads only the Mac and Windows app ZIPs", script)
        self.assertIn('gh release upload "$TAG" "$MAC_ASSET" "$WINDOWS_ASSET"', script)
        self.assertNotIn("Offline pack upload folder", script)
        self.assertNotIn("OFFLINE_ASSETS", script)
        self.assertNotIn("Chronicle.offline-pack", script)

    def test_windows_vm_sync_does_not_check_offline_pack(self):
        script = (ROOT / "sync_and_build_only.bat").read_text(encoding="utf-8")

        self.assertIn("user-managed Ollama", script)
        self.assertIn("ollama pull qwen2.5vl:7b", script)
        self.assertNotIn(r"offline_pack\models", script)
        self.assertNotIn(r"offline_pack\ollama", script)
        self.assertNotIn("CHRONICLE_BUNDLE_OFFLINE_PACK", script)

    def test_windows_powershell_build_never_embeds_offline_payload(self):
        script = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")

        self.assertIn("Assert-NoEmbeddedOfflinePayload", script)
        self.assertIn(r"_internal\offline\models", script)
        self.assertIn(r"_internal\offline\ollama", script)
        self.assertIn("existing Ollama installation", script)
        self.assertNotIn("separate offline_pack upload", script)

    def test_mac_build_never_embeds_offline_payload(self):
        script = (ROOT / "Mac" / "build_mac.py").read_text(encoding="utf-8")

        self.assertIn("assert_no_embedded_offline_payload", script)
        self.assertIn('Contents", "Resources", "offline", "models"', script)
        self.assertIn('Contents", "Resources", "offline", "ollama"', script)
        self.assertIn("existing Ollama installation", script)
        self.assertNotIn("separate offline_pack upload", script)

    def test_mac_bundle_metadata_uses_the_app_version(self):
        import plistlib
        import tempfile
        from unittest import mock
        from Mac import build_mac
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Chronicle.app"
            (app / "Contents").mkdir(parents=True)
            metadata = app / "Contents/Info.plist"
            metadata.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "0.0.0", "CFBundleIdentifier": "Chronicle"}))
            with mock.patch.object(build_mac.subprocess, "run") as signing:
                build_mac.finalize_app_metadata(app, ROOT / "chronicle_gui.py")
            info = plistlib.loads(metadata.read_bytes())
            self.assertEqual(info["CFBundleShortVersionString"], "1.1.5")
            self.assertEqual(info["CFBundleVersion"], "1.1.5")
            self.assertEqual(info["CFBundleIdentifier"], "Chronicle")
            self.assertIn("--sign", signing.call_args.args[0])

    def test_public_snapshot_excludes_assistant_and_machine_state(self):
        from tools import build_source_archive
        for rel in ("AGENTS.md", ".agents/skills/example/SKILL.md", "skills-lock.json", "CONTINUITY.md", "Chronicle.spec", "docs/internal/HANDOFF.md"):
            with self.subTest(path=rel):
                self.assertTrue(prepare_public_repo_snapshot.should_exclude(rel))
                self.assertFalse(build_source_archive.should_include(ROOT / rel, ROOT))

    def test_app_builds_stage_public_docs_only(self):
        mac = (ROOT / "Mac/build_mac.py").read_text(encoding="utf-8")
        windows = (ROOT / "build_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("stage_public_app_docs", mac)
        self.assertNotIn('("docs", "docs")', mac)
        self.assertIn("--docs-only", windows)
        diagnostic = (ROOT / "capture_windows_build_diagnostics.bat").read_text(encoding="utf-8")
        self.assertIn("--docs-only", diagnostic)
        self.assertNotIn('--add-data "%SCRIPT_DIR%docs;docs"', diagnostic)
        self.assertIn("tools/prepare_public_repo_snapshot.py", stage_windows_bundle.REQUIRED_PATHS)
        self.assertNotIn('$pyArgs.Add("$rootDir\\docs;docs")', windows)

    def test_app_doc_staging_excludes_internal_and_release_planning(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "docs"
            prepare_public_repo_snapshot.stage_public_app_docs(ROOT, output)
            self.assertTrue((output / "user/chronicle_help.html").is_file())
            self.assertTrue((output / "reference/CHANGELOG.md").is_file())
            self.assertFalse((output / "internal").exists())
            self.assertFalse((output / "github_rollout/LAUNCH_RUNBOOK.md").exists())
            self.assertFalse((output / "branding").exists())

    def test_release_scripts_derive_tag_from_current_release_notes(self):
        for rel_path in (
            "Mac/Publish_GitHub_Release.command",
            "Mac/Update_GitHub_Release_Notes_Only.command",
            "Mac/Push_Public_Repo.command",
            "Mac/Docs_Only_Public_Update.command",
        ):
            script = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertIn("release_helpers.sh", script)
            self.assertNotIn('DEFAULT_TAG="v1.0.5"', script)
        publish_script = (ROOT / "Mac/Publish_GitHub_Release.command").read_text(encoding="utf-8")
        notes_script = (ROOT / "Mac/Update_GitHub_Release_Notes_Only.command").read_text(encoding="utf-8")
        self.assertIn("release_tag_from_notes", publish_script)
        self.assertIn("release_tag_from_notes", notes_script)

    def test_snapshot_callers_pass_explicit_repo_root(self):
        for rel_path in (
            "Mac/Package_Release_Apps.command",
            "Mac/Docs_Only_Public_Update.command",
            "Mac/Prepare_Public_Repo.command",
        ):
            script = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertIn("prepare_public_repo_snapshot.py", script)
            self.assertIn('--repo-root "$ROOT_DIR"', script)
            self.assertIn('--output "$SNAPSHOT_DIR"', script)

    def test_private_offline_menu_uses_local_ollama_setup(self):
        source = (ROOT / "chronicle_app" / "ui" / "menus.py").read_text(encoding="utf-8")

        self.assertIn("Set Up Local &Ollama", source)
        self.assertIn("OnUseExistingOllama", source)
        self.assertNotIn("Install Private Offline &Pack", source)
        self.assertNotIn("OnInstallOfflinePack", source)

    def test_help_menu_exposes_builtin_update_checks(self):
        source = (ROOT / "chronicle_app" / "ui" / "menus.py").read_text(encoding="utf-8")
        gui = (ROOT / "chronicle_gui.py").read_text(encoding="utf-8")
        updater = (ROOT / "chronicle_app" / "services" / "update_service.py").read_text(encoding="utf-8")

        self.assertIn("Check for &Updates", source)
        self.assertIn(r"Context &Help\tF1", source)
        self.assertIn("&Open User Guide", source)
        self.assertIn("OnContextHelp", source)
        self.assertIn("&Version History", source)
        self.assertIn("OnCheckForUpdates", source)
        self.assertIn("OnVersionHistory", source)
        self.assertIn("ShowContextHelpForWindow", gui)
        self.assertIn("Automatic installation is available only from a packaged Chronicle app", gui)
        self.assertIn("xattr -rd com.apple.quarantine", gui)
        self.assertIn("build_mac_updater_script", updater)
        self.assertIn("xattr -rd com.apple.quarantine", updater)

    def test_mac_first_launch_helper_clears_quarantine(self):
        helper = (ROOT / "Mac" / "Open Me First.command").read_text(encoding="utf-8")

        self.assertIn("Chronicle.app", helper)
        self.assertIn("xattr -dr com.apple.quarantine", helper)
        self.assertIn("Privacy & Security", helper)
        self.assertIn("Open Anyway", helper)

    def test_first_launch_offers_ollama_setup_after_welcome(self):
        source = (ROOT / "chronicle_gui.py").read_text(encoding="utf-8")

        self.assertIn("MaybeOfferOllamaSetupOnFirstLaunch", source)
        self.assertIn("ollama pull", source)
        self.assertIn("self.MaybeOfferOllamaSetupOnFirstLaunch()", source)
        self.assertNotIn("MaybeOfferOfflinePackOnFirstLaunch", source)


if __name__ == "__main__":
    unittest.main()
