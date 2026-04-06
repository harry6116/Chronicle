import os
import tempfile
import types
import unittest
from unittest import mock

from chronicle_app.services.app_files import (
    build_log_header,
    emit_launch_continuity,
    get_runtime_build_stamp,
    load_json_file,
    read_continuity_file,
    resolve_runtime_crash_log_path,
    resolve_continuity_file_path,
    resolve_default_log_directory,
    save_json_file,
    update_continuity_runtime_status,
    write_processing_log,
)


class AppFilesTest(unittest.TestCase):
    def test_load_and_save_json_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.json")
            payload = {"alpha": 1, "beta": True}

            save_json_file(path, payload)

            self.assertEqual(load_json_file(path, {}), payload)
            self.assertEqual(load_json_file(os.path.join(tmpdir, "missing.json"), {"fallback": 1}), {"fallback": 1})

    def test_get_runtime_build_stamp_prefers_build_stamp_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stamp_path = os.path.join(tmpdir, "build_stamp.txt")
            with open(stamp_path, "w", encoding="utf-8") as fh:
                fh.write("2026-03-18 build")

            value = get_runtime_build_stamp(
                script_dir=tmpdir,
                module_file=__file__,
                sys_executable="/tmp/fake-python",
                is_frozen=False,
            )

            self.assertEqual(value, "2026-03-18 build")

    def test_continuity_helpers_resolve_read_and_emit_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_path = resolve_continuity_file_path(script_dir=tmpdir)
            self.assertEqual(continuity_path, os.path.join(tmpdir, "CONTINUITY.md"))

            with open(continuity_path, "w", encoding="utf-8") as fh:
                fh.write("# Chronicle Continuity\n\nWake phrase")

            read_path, continuity_text = read_continuity_file(script_dir=tmpdir)
            self.assertEqual(read_path, continuity_path)
            self.assertEqual(continuity_text, "# Chronicle Continuity\n\nWake phrase")

            lines = []
            emitted_path, emitted_text = emit_launch_continuity(
                script_dir=tmpdir,
                print_fn=lines.append,
            )

            self.assertEqual(emitted_path, continuity_path)
            self.assertEqual(emitted_text, continuity_text)
            self.assertIn(f"Chronicle repo root: {tmpdir}", lines)
            self.assertIn("Loading CONTINUITY.md before launch.", lines)
            self.assertIn("# Chronicle Continuity\n\nWake phrase", lines)

    def test_emit_launch_continuity_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lines = []

            emitted_path, emitted_text = emit_launch_continuity(
                script_dir=tmpdir,
                print_fn=lines.append,
            )

            self.assertEqual(emitted_path, os.path.join(tmpdir, "CONTINUITY.md"))
            self.assertIsNone(emitted_text)
            self.assertIn(f"CONTINUITY.md not found at {emitted_path}.", lines)

    def test_resolve_continuity_file_path_supports_env_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "custom-continuity.md")
            with mock.patch.dict(os.environ, {"CHRONICLE_CONTINUITY_FILE": target}, clear=False):
                self.assertEqual(resolve_continuity_file_path(script_dir="/ignored"), target)

    def test_resolve_continuity_file_path_falls_back_to_cwd_parents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = os.path.join(tmpdir, "workspace")
            nested = os.path.join(root, "dist", "Chronicle.app", "Contents", "Frameworks")
            os.makedirs(nested)
            continuity_path = os.path.join(root, "CONTINUITY.md")
            with open(continuity_path, "w", encoding="utf-8") as fh:
                fh.write("# Chronicle Continuity\n")

            with mock.patch.dict(os.environ, {}, clear=False):
                with mock.patch("os.getcwd", return_value=nested):
                    resolved = resolve_continuity_file_path(script_dir=os.path.join(nested, "chronicle_gui.py"))

            self.assertEqual(resolved, continuity_path)

    def test_update_continuity_runtime_status_appends_and_refreshes_block(self):
        fake_time = types.SimpleNamespace(
            strftime=lambda fmt, *_args: "2026-03-29 17:00:00",
            localtime=lambda *_args: object(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_path = os.path.join(tmpdir, "CONTINUITY.md")
            with open(continuity_path, "w", encoding="utf-8") as fh:
                fh.write("# Chronicle Continuity\n\nManual notes stay here.\n")

            path, status = update_continuity_runtime_status(
                script_dir=tmpdir,
                event="run_start",
                detail="Queued 1 legal file.",
                time_module=fake_time,
            )

            self.assertEqual(path, continuity_path)
            self.assertEqual(status["Last extraction start"], "2026-03-29 17:00:00")
            self.assertEqual(status["Last extraction summary"], "Queued 1 legal file.")

            with open(continuity_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            self.assertIn("## Runtime Status (Auto-updated)", content)
            self.assertIn("- Last extraction start: 2026-03-29 17:00:00", content)
            self.assertIn("- Last extraction summary: Queued 1 legal file.", content)
            self.assertIn("Manual notes stay here.", content)

    def test_emit_launch_continuity_refreshes_runtime_launch_status(self):
        fake_time = types.SimpleNamespace(
            strftime=lambda fmt, *_args: "2026-03-29 17:05:00",
            localtime=lambda *_args: object(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            continuity_path = os.path.join(tmpdir, "CONTINUITY.md")
            with open(continuity_path, "w", encoding="utf-8") as fh:
                fh.write("# Chronicle Continuity\n")

            lines = []
            emit_launch_continuity(script_dir=tmpdir, print_fn=lines.append)
            update_continuity_runtime_status(
                script_dir=tmpdir,
                event="launch",
                time_module=fake_time,
            )

            with open(continuity_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            self.assertIn("- Last app launch: 2026-03-29 17:05:00", content)

    def test_resolve_default_log_directory_prefers_source_root_then_custom_dest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = os.path.join(tmpdir, "source")
            custom_dest = os.path.join(tmpdir, "dest")
            os.makedirs(source_root)
            os.makedirs(custom_dest)

            queue = [{"source_root": source_root, "path": os.path.join(source_root, "doc.pdf")}]
            cfg = {"dest_mode": 1, "custom_dest": custom_dest}

            self.assertEqual(resolve_default_log_directory(queue, cfg, "/fallback"), source_root)
            self.assertEqual(resolve_default_log_directory([], cfg, "/fallback"), custom_dest)
            self.assertEqual(resolve_default_log_directory([], {"dest_mode": 0}, "/fallback"), "/fallback")

    def test_build_and_write_processing_log_use_expected_header(self):
        fake_time = types.SimpleNamespace(
            strftime=lambda fmt, *_args: "2026-03-18 09:30:00" if " " in fmt else "20260318_093000",
            localtime=lambda *_args: object(),
        )
        header = build_log_header("build-123", time_module=fake_time)
        self.assertEqual(header[:3], [
            "Chronicle Processing Log",
            "Build: build-123",
            "Generated: 2026-03-18 09:30:00",
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_processing_log(tmpdir, "build-123", ["line one", "line two"], time_module=fake_time)
            self.assertTrue(path.endswith("chronicle_processing_log_20260318_093000.txt"))
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("Build: build-123", content)
            self.assertIn("line one", content)
            self.assertIn("line two", content)

    def test_resolve_runtime_crash_log_path_uses_os_specific_locations(self):
        windows_path = resolve_runtime_crash_log_path(
            platform_system="Windows",
            env={"LOCALAPPDATA": r"C:\Users\tester\AppData\Local"},
            tempdir=lambda: r"C:\Temp",
        )
        self.assertEqual(windows_path, r"C:\Users\tester\AppData\Local/Chronicle/logs/chronicle_crash.log")

        with tempfile.TemporaryDirectory() as tmpdir:
            mac_home = os.path.join(tmpdir, "tester-home")
            mac_path = resolve_runtime_crash_log_path(
                platform_system="Darwin",
                env={},
                expanduser=lambda path: path.replace("~", mac_home),
                tempdir=lambda: "/tmp",
            )
            self.assertEqual(mac_path, os.path.join(mac_home, "Library/Logs/Chronicle/chronicle_crash.log"))


if __name__ == "__main__":
    unittest.main()
