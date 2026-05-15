import json
import os
import tempfile
import types
import unittest
import zipfile

from chronicle_app.services.diagnostics import (
    build_provider_capability_matrix,
    build_resume_center_summary,
    compare_output_files,
    create_support_bundle,
    redact_sensitive,
)
from chronicle_app.services.security import sanitize_log_text


class DiagnosticsTest(unittest.TestCase):
    def _fake_gemini_key(self, suffix="1"):
        return "AI" + "za" + (suffix * 35)

    def test_redact_sensitive_removes_keys_recursively(self):
        payload = {"gemini_api_key": "secret", "nested": {"token": "abc", "safe": "ok"}}

        redacted = redact_sensitive(payload)

        self.assertEqual(redacted["gemini_api_key"], "[redacted]")
        self.assertEqual(redacted["nested"]["token"], "[redacted]")
        self.assertEqual(redacted["nested"]["safe"], "ok")

    def test_sanitize_log_text_removes_api_key_patterns(self):
        key_one = self._fake_gemini_key("1")
        key_two = self._fake_gemini_key("a")
        text = sanitize_log_text(
            f"failed with x-goog-api-key: {key_one} and key={key_two}"
        )

        self.assertNotIn("AIza", text)
        self.assertIn("x-goog-api-key: [redacted]", text)

    def test_provider_capability_matrix_reports_configured_providers(self):
        text = build_provider_capability_matrix(
            {"gemini": "x"},
            has_provider_key_fn=lambda vendor: vendor == "gemini",
        )

        self.assertIn("Google Gemini: configured", text)
        self.assertIn("Anthropic Claude: not configured", text)
        self.assertIn("OpenAI: not configured", text)

    def test_resume_center_summary_lists_recoverable_rows(self):
        text = build_resume_center_summary(
            {
                "queue": [
                    {"path": "/tmp/a.pdf", "status": "Queued"},
                    {"path": "/tmp/b.pdf", "status": "Done"},
                ]
            },
            terminal_statuses={"Done"},
        )

        self.assertIn("Recoverable rows: 1", text)
        self.assertIn("a.pdf (Queued)", text)

    def test_create_support_bundle_redacts_config_and_session(self):
        fake_time = types.SimpleNamespace(strftime=lambda fmt: "20260416_120000")
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = os.path.join(tmpdir, "session.json")
            with open(session_path, "w", encoding="utf-8") as fh:
                json.dump({"api_key": "hidden"}, fh)

            bundle = create_support_bundle(
                destination_dir=tmpdir,
                build_stamp="build",
                cfg={"api_key": "secret", "format_type": "html"},
                queue=[{"path": "/tmp/a.pdf", "settings": {"token": "abc"}}],
                processing_log_lines=["line one", f"provider said api_key={self._fake_gemini_key('2')}"],
                session_file=session_path,
                provider_matrix_text="matrix",
                time_module=fake_time,
            )

            with zipfile.ZipFile(bundle) as zf:
                self.assertIn("diagnostic_summary.txt", zf.namelist())
                cfg = json.loads(zf.read("config_redacted.json").decode("utf-8"))
                session = json.loads(zf.read("active_session_redacted.json").decode("utf-8"))
                processing_log = zf.read("processing_log.txt").decode("utf-8")

            self.assertEqual(cfg["api_key"], "[redacted]")
            self.assertEqual(session["api_key"], "[redacted]")
            self.assertNotIn("AIza", processing_log)

    def test_compare_output_files_returns_unified_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            left = os.path.join(tmpdir, "left.txt")
            right = os.path.join(tmpdir, "right.txt")
            with open(left, "w", encoding="utf-8") as fh:
                fh.write("alpha\nbeta\n")
            with open(right, "w", encoding="utf-8") as fh:
                fh.write("alpha\ngamma\n")

            report = compare_output_files(left, right)

        self.assertIn("Diff lines:", report)
        self.assertIn("-beta", report)
        self.assertIn("+gamma", report)


if __name__ == "__main__":
    unittest.main()
