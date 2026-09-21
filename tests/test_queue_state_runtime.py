import unittest

from chronicle_app.services.queue_state_runtime import (
    apply_settings_to_rows,
    build_progress_summary,
    estimate_path_work_units,
    get_run_unit_totals,
    get_target_queue_indices_for_setting_change,
    format_scan_log_message,
    pause_selected_tasks,
    refresh_queue_work_unit_estimates,
    resume_selected_tasks,
    should_log_page_progress,
    should_status_echo_log,
    stop_selected_tasks,
)


class QueueStateRuntimeTest(unittest.TestCase):
    def test_get_target_queue_indices_for_setting_change_prefers_selected_assignable_rows(self):
        queue = [{"status": "Queued"}, {"status": "Done"}, {"status": "Paused"}]

        target = get_target_queue_indices_for_setting_change(queue, [0, 1, 2])

        self.assertEqual(target, [0, 2])

    def test_get_target_queue_indices_for_setting_change_falls_back_to_selected_when_none_assignable(self):
        queue = [{"status": "Done"}, {"status": "Stopped"}]

        target = get_target_queue_indices_for_setting_change(queue, [0, 1])

        self.assertEqual(target, [0, 1])

    def test_apply_settings_to_rows_updates_settings_and_engine(self):
        queue = [{"settings": {}, "engine": "Old"}]

        apply_settings_to_rows(
            queue,
            [0],
            {"format_type": "pdf", "model_name": "gpt-5"},
            row_setting_keys=("format_type", "model_name"),
            label_from_model_fn=lambda model: f"Label:{model}",
        )

        self.assertEqual(queue[0]["settings"], {"format_type": "pdf", "model_name": "gpt-5"})
        self.assertEqual(queue[0]["engine"], "Label:gpt-5")

    def test_estimate_path_work_units_uses_pdf_scope_when_available(self):
        class Reader:
            def __init__(self, path):
                self.pages = [object(), object(), object(), object()]

        units = estimate_path_work_units(
            "/tmp/sample.pdf",
            settings={"pdf_page_scope": "1,3"},
            pdf_reader_factory=Reader,
            normalize_pdf_page_scope_text_fn=lambda scope: scope,
            parse_pdf_page_scope_spec_fn=lambda scope, total: [0, 2],
        )

        self.assertEqual(units, 2)

    def test_refresh_queue_work_unit_estimates_populates_rows(self):
        queue = [{"path": "/tmp/a.pdf", "status": "Queued"}, {"path": "", "status": "Queued"}]

        refresh_queue_work_unit_estimates(
            queue,
            normalize_row_settings_fn=lambda row: {"pdf_page_scope": ""},
            estimate_path_work_units_fn=lambda path, settings=None: 4 if path.endswith(".pdf") else 1,
        )

        self.assertEqual(queue[0]["_work_units"], 4)
        self.assertEqual(queue[1]["_work_units"], 1)

    def test_get_run_unit_totals_counts_done_and_processing_progress(self):
        queue = [
            {"status": "Done", "_work_units": 3},
            {"status": "Processing", "_work_units": 5},
            {"status": "Queued", "_work_units": 2},
        ]

        totals = get_run_unit_totals(
            queue,
            current_processing_index=1,
            current_file_page_done=2,
            terminal_statuses={"Done", "Error"},
        )

        self.assertEqual(totals, (10, 5))

    def test_get_run_unit_totals_keeps_errored_pdf_at_actual_page_progress(self):
        queue = [{"status": "Error", "_work_units": 12}]

        totals = get_run_unit_totals(
            queue,
            current_processing_index=0,
            current_file_page_done=2,
            terminal_statuses={"Done", "Error", "Stopped"},
        )

        self.assertEqual(totals, (12, 2))

    def test_progress_summary_does_not_report_errored_pdf_as_completed_work(self):
        queue = [{"status": "Error", "_work_units": 12}]

        summary = build_progress_summary(
            queue,
            current_processing_index=0,
            current_file_ordinal=1,
            current_file_page_total=12,
            current_file_page_done=2,
            terminal_statuses={"Done", "Error", "Stopped"},
        )

        self.assertIn("Progress 2 of 12 work units (16%).", summary)
        self.assertIn("Files done: 0 of 1.", summary)
        self.assertIn("Resolved: 1 of 1.", summary)
        self.assertIn("Errors: 1.", summary)

    def test_should_log_page_progress_and_status_echo_follow_noise_rules(self):
        self.assertTrue(should_log_page_progress(1, 10))
        self.assertTrue(should_log_page_progress(2, 10))
        self.assertTrue(should_log_page_progress(19, 100))
        self.assertFalse(should_log_page_progress(21, 100))
        self.assertTrue(should_log_page_progress(22, 100))
        self.assertTrue(should_status_echo_log("ordinary message", engine_event=False))
        self.assertFalse(should_status_echo_log("[Page] noisy", engine_event=True))

    def test_format_scan_log_message_makes_dense_newspaper_progress_readable(self):
        message = (
            "[Gemini Image] Requesting dense newspaper strip 2/3 for source page 4 "
            "via streaming inline REST on gemini-2.5-pro."
        )

        formatted = format_scan_log_message(message)

        self.assertEqual(formatted, "Scanning page 4, part 2 of 3 with gemini-2.5-pro.")
        self.assertNotIn("strip", formatted.lower())
        self.assertNotIn("[Gemini Image]", formatted)

    def test_format_scan_log_message_makes_scanned_image_progress_readable(self):
        message = (
            "[Gemini Image] Requesting full-page scanned image output for source page 7 "
            "via streaming inline REST on gemini-2.5-pro."
        )

        formatted = format_scan_log_message(message)

        self.assertEqual(formatted, "Scanning image-only page 7 with gemini-2.5-pro.")

    def test_format_scan_log_message_relabels_internal_status_prefixes(self):
        self.assertEqual(
            format_scan_log_message("[Auto Engine] Routing dense newspaper page 1 to gemini-2.5-pro."),
            "Routing: dense newspaper page 1 to gemini-2.5-pro.",
        )
        self.assertEqual(
            format_scan_log_message("[FAIL-SAFE] Page 1 vision failed. Extracting raw text layer."),
            "Recovery: Page 1 vision failed. Extracting raw text layer.",
        )

    def test_format_scan_log_message_makes_gemini_pdf_progress_readable(self):
        self.assertEqual(
            format_scan_log_message("[Gemini PDF] Uploading slice chronicle_pdf_1_1.pdf (372144 bytes)."),
            "Preparing PDF page 1 for Gemini (363 KB).",
        )
        self.assertEqual(
            format_scan_log_message("[Gemini PDF] Waiting for slice chronicle_pdf_1_1.pdf to become ready."),
            "Waiting for Gemini to accept PDF page 1.",
        )
        self.assertEqual(
            format_scan_log_message("[Gemini PDF] Slice chronicle_pdf_1_1.pdf is ready."),
            "PDF page 1 is ready for reading.",
        )
        self.assertEqual(
            format_scan_log_message("[Gemini PDF] Requesting model output for page 1 of 9 pages via gemini-2.5-pro."),
            "Reading page 1 of 9 with Gemini 2.5 Pro.",
        )

    def test_format_scan_log_message_makes_page_and_memory_progress_readable(self):
        self.assertEqual(
            format_scan_log_message("[Page] 1/9 pages processed (source page 1, run total: 1)."),
            "Finished page 1 of 9.",
        )
        self.assertEqual(
            format_scan_log_message("[Memory] Cleared buffered page text at run page 2 (buffer cadence: every 2 pages)."),
            "Memory: released temporary page text after page 2.",
        )

    def test_format_scan_log_message_makes_recovery_and_mac_lines_readable(self):
        self.assertEqual(
            format_scan_log_message(
                "[Mac] Keeping Chronicle active during extraction so backgrounding the window does not pause provider/network work."
            ),
            "Mac: preventing sleep or background pauses during extraction.",
        )
        self.assertEqual(
            format_scan_log_message("[Progress] In-progress recovery file: /tmp/example.html.progress.txt.tmp"),
            "Progress backup: saving recoverable work to /tmp/example.html.progress.txt.tmp",
        )

    def test_build_progress_summary_includes_review_and_page_detail(self):
        queue = [
            {"status": "Done", "review_recommended": True, "_work_units": 2},
            {"status": "Processing", "path": "/tmp/deck.pptx", "_work_units": 5},
            {"status": "Queued", "_work_units": 1},
        ]

        summary = build_progress_summary(
            queue,
            current_processing_index=1,
            current_file_ordinal=2,
            current_file_page_total=5,
            current_file_page_done=2,
            terminal_statuses={"Done", "Error", "Skipped", "Unsupported", "Missing", "Stopped"},
        )

        self.assertIn("Done: 1.", summary)
        self.assertIn("Review: 1.", summary)
        self.assertIn("Current file 2: 2 of 5 slides.", summary)

    def test_task_transition_helpers_mutate_expected_rows(self):
        queue = [
            {"status": "Queued"},
            {"status": "Processing"},
            {"status": "Paused"},
            {"status": "Done"},
        ]

        stop_result = stop_selected_tasks(queue, [0, 1, 3])
        paused = pause_selected_tasks(queue, [1, 2, 3])
        resumed = resume_selected_tasks(queue, [1, 2])

        self.assertEqual(stop_result, {"stopped": 1, "includes_processing": True})
        self.assertEqual(paused, 1)
        self.assertEqual(resumed, 2)
        self.assertEqual([row["status"] for row in queue], ["Stopped", "Queued", "Queued", "Done"])


if __name__ == "__main__":
    unittest.main()
