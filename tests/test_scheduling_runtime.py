import types
import unittest

from chronicle_app.services.scheduling_runtime import (
    build_schedule_summary_label,
    format_timestamp_local,
    normalize_future_timestamp,
    should_trigger_scheduled_start,
)


class SchedulingRuntimeTest(unittest.TestCase):
    def test_normalize_future_timestamp_filters_past_and_invalid_values(self):
        self.assertEqual(normalize_future_timestamp(200.0, now=100.0), 200.0)
        self.assertIsNone(normalize_future_timestamp(50.0, now=100.0))
        self.assertIsNone(normalize_future_timestamp("bad", now=100.0))

    def test_format_and_summary_helpers_render_expected_text(self):
        fake_time = types.SimpleNamespace(
            strftime=lambda fmt, *_args: "2026-03-18 10:15:00",
            localtime=lambda ts: object(),
        )
        self.assertEqual(format_timestamp_local(123.0, time_module=fake_time), "2026-03-18 10:15:00")
        self.assertEqual(build_schedule_summary_label(None, time_module=fake_time), "No extraction scheduled.")
        self.assertEqual(
            build_schedule_summary_label(123.0, time_module=fake_time),
            "Scheduled extraction: 2026-03-18 10:15:00",
        )

    def test_should_trigger_scheduled_start_checks_flags_and_time(self):
        self.assertTrue(should_trigger_scheduled_start(100.0, is_running=False, scheduled_start_triggered=False, now=120.0))
        self.assertFalse(should_trigger_scheduled_start(100.0, is_running=True, scheduled_start_triggered=False, now=120.0))
        self.assertFalse(should_trigger_scheduled_start(100.0, is_running=False, scheduled_start_triggered=True, now=120.0))
        self.assertFalse(should_trigger_scheduled_start(None, is_running=False, scheduled_start_triggered=False, now=120.0))


if __name__ == "__main__":
    unittest.main()
