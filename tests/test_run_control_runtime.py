import unittest

from chronicle_app.services.run_control_runtime import (
    build_running_state_update,
    count_active_queue_items,
    count_saved_queue_items,
    pause_current_processing_row,
    prepare_running_close,
    wait_while_paused,
)


class _StopRequestedError(Exception):
    pass


class RunControlRuntimeTest(unittest.TestCase):
    def test_wait_while_paused_raises_when_stop_requested(self):
        with self.assertRaises(_StopRequestedError):
            wait_while_paused(
                is_running=True,
                is_paused=True,
                stop_requested=True,
                heartbeat_ping=lambda: None,
                sleep_fn=lambda _: None,
                stop_requested_error_cls=_StopRequestedError,
            )

    def test_wait_while_paused_pings_while_paused(self):
        pings = []
        state = {"calls": 0}

        def sleep_fn(_seconds):
            state["calls"] += 1

        wait_while_paused(
            is_running=True,
            is_paused=False,
            stop_requested=False,
            heartbeat_ping=lambda: pings.append("ping"),
            sleep_fn=sleep_fn,
            stop_requested_error_cls=_StopRequestedError,
        )

        self.assertEqual(pings, [])
        self.assertEqual(state["calls"], 0)

    def test_build_running_state_update_resets_non_running_state(self):
        self.assertEqual(build_running_state_update(True), {"is_running": True})
        self.assertEqual(
            build_running_state_update(False),
            {
                "is_running": False,
                "is_paused": False,
                "stop_requested": False,
                "current_processing_index": -1,
                "current_file_page_total": 0,
                "current_file_page_done": 0,
                "current_file_ordinal": 0,
            },
        )

    def test_count_active_queue_items_and_pause_current_row(self):
        queue = [{"status": "Done"}, {"status": "Queued"}, {"status": "Paused"}]

        self.assertEqual(
            count_active_queue_items(queue, terminal_statuses={"Done", "Error", "Stopped"}),
            2,
        )
        self.assertTrue(pause_current_processing_row(queue, 1))
        self.assertEqual(queue[1]["status"], "Paused")
        self.assertFalse(pause_current_processing_row(queue, 9))
        self.assertEqual(
            count_saved_queue_items(queue, terminal_statuses={"Done", "Error", "Stopped"}),
            2,
        )

    def test_prepare_running_close_distinguishes_dialog_choices(self):
        self.assertEqual(
            prepare_running_close("keep", keep_open_value="keep", save_exit_value="save", discard_exit_value="discard"),
            {
                "should_veto": True,
                "pause_run": False,
                "pause_current_row_directly": False,
                "save_session": False,
                "discard_session": False,
            },
        )
        self.assertEqual(
            prepare_running_close("save", keep_open_value="keep", save_exit_value="save", discard_exit_value="discard"),
            {
                "should_veto": False,
                "pause_run": True,
                "pause_current_row_directly": True,
                "save_session": True,
                "discard_session": False,
            },
        )
        self.assertEqual(
            prepare_running_close(
                "save",
                keep_open_value="keep",
                save_exit_value="save",
                discard_exit_value="discard",
                is_running=False,
            ),
            {
                "should_veto": False,
                "pause_run": False,
                "pause_current_row_directly": False,
                "save_session": True,
                "discard_session": False,
            },
        )
        self.assertEqual(
            prepare_running_close("discard", keep_open_value="keep", save_exit_value="save", discard_exit_value="discard"),
            {
                "should_veto": False,
                "pause_run": False,
                "pause_current_row_directly": False,
                "save_session": False,
                "discard_session": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
