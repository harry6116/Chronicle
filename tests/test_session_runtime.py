import os
import tempfile
import threading
import unittest

from chronicle_app.services.session_runtime import (
    build_session_payload,
    delete_active_session_file,
    has_incomplete_items,
    restore_session_queue,
    save_active_session_file,
)


class SessionRuntimeTest(unittest.TestCase):
    def test_build_session_payload_contains_expected_fields(self):
        payload = build_session_payload(1, {"format_type": "html"}, [{"path": "a.pdf"}], True, False)

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["cfg"]["format_type"], "html")
        self.assertEqual(payload["queue"][0]["path"], "a.pdf")
        self.assertTrue(payload["is_running"])
        self.assertFalse(payload["is_paused"])
        self.assertIn("updated_at", payload)

    def test_save_and_delete_active_session_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "session.json")
            payload = {"queue": [{"path": "a.pdf"}]}

            save_active_session_file(path, payload, session_lock=threading.Lock())
            self.assertTrue(os.path.exists(path))

            delete_active_session_file(path)
            self.assertFalse(os.path.exists(path))

    def test_has_incomplete_items_respects_terminal_statuses(self):
        terminal = {"Done", "Error"}
        self.assertFalse(has_incomplete_items([{"status": "Done"}], terminal))
        self.assertTrue(has_incomplete_items([{"status": "Queued"}], terminal))

    def test_restore_session_queue_normalizes_processing_rows(self):
        restored = restore_session_queue(
            [
                {
                    "path": "a.pdf",
                    "settings": {"format_type": "html", "doc_profile": "standard"},
                    "status": "Processing",
                    "source_root": "/tmp/src",
                }
            ],
            {"model_name": "gemini-2.5-flash"},
            row_setting_keys=("format_type", "doc_profile"),
            label_from_model_fn=lambda model: f"label:{model}",
        )

        self.assertEqual(restored[0]["engine"], "label:gemini-2.5-flash")
        self.assertEqual(restored[0]["status"], "Queued")
        self.assertEqual(restored[0]["settings"], {"format_type": "html", "doc_profile": "standard"})


if __name__ == "__main__":
    unittest.main()
