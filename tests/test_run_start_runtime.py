import unittest

from chronicle_app.services.run_start_runtime import (
    apply_start_configuration,
    begin_run_start,
    build_run_reset_state,
    build_start_messages,
    collect_pending_rows,
    expand_multi_range_pdf_rows,
    find_missing_api_key_requirement,
    prepare_queue_for_start,
    validate_output_destination,
    validate_pending_pdf_page_scopes,
)


class RunStartRuntimeTest(unittest.TestCase):
    def test_begin_run_start_clears_resume_flag_and_schedule(self):
        result = begin_run_start(resume_incomplete_only=True, scheduled_start_ts=123.0)

        self.assertTrue(result["resume_mode"])
        self.assertFalse(result["next_resume_incomplete_only"])
        self.assertTrue(result["should_clear_schedule"])

    def test_apply_start_configuration_populates_runtime_fields(self):
        result = apply_start_configuration(
            {"format_type": "html", "merge_files": False},
            control_settings={"format_type": "docx", "model_name": "gpt-5"},
            force_merge_from_scan=True,
            recursive_scan=True,
            dest_mode=1,
            custom_dest=" /tmp/out ",
            preserve_source_structure=False,
            delete_source_on_success=True,
            script_dir="/app",
        )

        self.assertEqual(result["format_type"], "docx")
        self.assertTrue(result["merge_files"])
        self.assertTrue(result["recursive_scan"])
        self.assertEqual(result["dest_mode"], 1)
        self.assertEqual(result["custom_dest"], "/tmp/out")
        self.assertFalse(result["preserve_source_structure"])
        self.assertTrue(result["delete_source_on_success"])
        self.assertEqual(result["output_dir"], "/app/output_docx")

    def test_validate_output_destination_checks_custom_folder(self):
        self.assertIsNone(validate_output_destination({"dest_mode": 0}))
        self.assertIn(
            "Please choose",
            validate_output_destination({"dest_mode": 1, "custom_dest": " "}, isdir=lambda _: True),
        )
        self.assertEqual(
            validate_output_destination({"dest_mode": 1, "custom_dest": "/tmp/out"}, isdir=lambda _: False),
            "Custom output folder does not exist.",
        )

    def test_prepare_queue_for_start_handles_resume_and_fresh_runs(self):
        resumed_queue = [{"status": "Processing"}, {"status": "Paused"}, {"status": "Done"}]
        resume_state = prepare_queue_for_start(
            resumed_queue,
            resume_mode=True,
            normalize_row_settings_fn=lambda row: row,
        )

        self.assertEqual([row["status"] for row in resumed_queue], ["Queued", "Queued", "Done"])
        self.assertEqual(resume_state, {"is_paused": False})

        fresh_queue = [{"status": "Paused"}, {"status": "Done"}, {"status": "Queued"}]
        touched = []

        def normalize(row):
            touched.append(row["status"])
            row["normalized"] = True
            return row

        prepare_queue_for_start(fresh_queue, resume_mode=False, normalize_row_settings_fn=normalize)

        self.assertEqual(touched, ["Done", "Queued"])
        self.assertEqual(fresh_queue[0]["status"], "Paused")
        self.assertEqual(fresh_queue[1]["status"], "Queued")
        self.assertEqual(fresh_queue[2]["status"], "Queued")
        self.assertTrue(fresh_queue[1]["normalized"])
        self.assertTrue(fresh_queue[2]["normalized"])

    def test_collect_pending_rows_filters_to_queued(self):
        queue = [{"status": "Queued"}, {"status": "Paused"}, {"status": "Queued"}]

        pending = collect_pending_rows(queue)

        self.assertEqual(pending, [queue[0], queue[2]])

    def test_expand_multi_range_pdf_rows_splits_disjoint_scopes_when_merge_is_off(self):
        queue = [
            {
                "path": "/tmp/a.pdf",
                "engine": "Gemini",
                "status": "Queued",
                "settings": {"pdf_page_scope": "1-30,185-220,530-574", "merge_files": False},
            }
        ]

        result = expand_multi_range_pdf_rows(
            queue,
            normalize_row_settings_fn=lambda row: row["settings"],
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
        )

        self.assertTrue(result["changed"])
        self.assertEqual([row["settings"]["pdf_page_scope"] for row in queue], ["1-30", "185-220", "530-574"])

    def test_expand_multi_range_pdf_rows_keeps_single_job_when_merge_is_on(self):
        queue = [
            {
                "path": "/tmp/a.pdf",
                "engine": "Gemini",
                "status": "Queued",
                "settings": {"pdf_page_scope": "1-30,185-220", "merge_files": True},
            }
        ]

        result = expand_multi_range_pdf_rows(
            queue,
            normalize_row_settings_fn=lambda row: row["settings"],
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
        )

        self.assertFalse(result["changed"])
        self.assertEqual(len(queue), 1)

    def test_validate_pending_pdf_page_scopes_reports_first_invalid_scope(self):
        rows = [
            {"path": "/tmp/a.pdf", "settings": {"pdf_page_scope": "1-2"}},
            {"path": "/tmp/b.pdf", "settings": {"pdf_page_scope": "bad"}},
        ]

        class Reader:
            def __init__(self, path):
                self.pages = [object(), object(), object()]

        error = validate_pending_pdf_page_scopes(
            rows,
            normalize_row_settings_fn=lambda row: row["settings"],
            pdf_reader_factory=Reader,
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
            parse_pdf_page_scope_spec_fn=lambda scope, total: (_ for _ in ()).throw(ValueError("bad scope")) if scope == "bad" else [1],
        )

        self.assertEqual(error, {"filename": "b.pdf", "details": "bad scope"})

    def test_find_missing_api_key_requirement_reports_label(self):
        rows = [
            {"engine": "Gemini", "settings": {"model_name": "gemini-2.5-flash"}},
            {"engine": "GPT", "settings": {"model_name": "gpt-5"}},
        ]

        missing = find_missing_api_key_requirement(
            rows,
            normalize_row_settings_fn=lambda row: row["settings"],
            model_from_label_fn=lambda label: "fallback-model",
            label_from_model_fn=lambda model: f"Label:{model}",
            has_vendor_key_fn=lambda vendor: vendor == "gemini",
        )

        self.assertEqual(missing, {"vendor": "openai", "label": "Label:gpt-5"})

    def test_find_missing_api_key_requirement_accepts_claude_vendor_key(self):
        rows = [
            {"engine": "Claude", "settings": {"model_name": "claude-sonnet-4-20250514"}},
        ]

        missing = find_missing_api_key_requirement(
            rows,
            normalize_row_settings_fn=lambda row: row["settings"],
            model_from_label_fn=lambda label: "fallback-model",
            label_from_model_fn=lambda model: f"Label:{model}",
            has_vendor_key_fn=lambda vendor: vendor == "claude",
        )

        self.assertIsNone(missing)

    def test_build_start_messages_and_run_reset_state(self):
        messages = build_start_messages(resume_mode=False, pending_count=4)
        reset_state = build_run_reset_state()

        self.assertEqual(messages["log_message"], "Starting extraction for queued files (4 queued).")
        self.assertEqual(messages["status_text"], "Extraction started: 4 queued file(s).")
        self.assertEqual(reset_state["processing_log_lines"], [])
        self.assertEqual(reset_state["current_file_ordinal"], 0)
        self.assertFalse(reset_state["current_run_resume_mode"])
        self.assertFalse(reset_state["stop_requested"])


if __name__ == "__main__":
    unittest.main()
