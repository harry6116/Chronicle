import unittest

from chronicle_app.services.queue_state_runtime import (
    apply_settings_to_rows,
    build_progress_summary,
    estimate_path_work_units,
    get_run_unit_totals,
    get_target_queue_indices_for_setting_change,
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

    def test_get_run_unit_totals_counts_terminal_and_processing_progress(self):
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

    def test_should_log_page_progress_and_status_echo_follow_noise_rules(self):
        self.assertTrue(should_log_page_progress(1, 10))
        self.assertTrue(should_log_page_progress(2, 10))
        self.assertTrue(should_log_page_progress(19, 100))
        self.assertFalse(should_log_page_progress(21, 100))
        self.assertTrue(should_log_page_progress(22, 100))
        self.assertTrue(should_status_echo_log("ordinary message", engine_event=False))
        self.assertFalse(should_status_echo_log("[Page] noisy", engine_event=True))

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
