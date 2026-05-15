import unittest

from chronicle_app.services.mac_activity_runtime import (
    start_mac_activity_guard,
    stop_mac_activity_guard,
)


class MacActivityRuntimeTest(unittest.TestCase):
    def test_start_mac_activity_guard_uses_caffeinate_on_darwin(self):
        calls = []
        logs = []

        class Process:
            def poll(self):
                return None

        process = start_mac_activity_guard(
            current_process=None,
            is_running=False,
            platform_system="Darwin",
            subprocess_popen=lambda *args, **kwargs: calls.append((args, kwargs)) or Process(),
            log_cb=logs.append,
        )

        self.assertIsNotNone(process)
        self.assertEqual(calls[0][0][0][:2], ["caffeinate", "-dimsu"])
        self.assertIn("-w", calls[0][0][0])
        self.assertTrue(any("Keeping Chronicle active" in line for line in logs))

    def test_start_mac_activity_guard_skips_non_mac(self):
        process = start_mac_activity_guard(
            current_process=None,
            is_running=False,
            platform_system="Windows",
            subprocess_popen=lambda *args, **kwargs: self.fail("should not start caffeinate"),
        )

        self.assertIsNone(process)

    def test_stop_mac_activity_guard_terminates_running_process(self):
        events = []

        class Process:
            def poll(self):
                return None

            def terminate(self):
                events.append("terminate")

            def wait(self, timeout=None):
                events.append(("wait", timeout))

            def kill(self):
                events.append("kill")

        self.assertIsNone(stop_mac_activity_guard(Process()))
        self.assertEqual(events, ["terminate", ("wait", 2)])


if __name__ == "__main__":
    unittest.main()
