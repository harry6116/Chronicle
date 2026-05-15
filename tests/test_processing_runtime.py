import os
from pathlib import Path
import tempfile
import time
import types
import unittest

from chronicle_app.services.processing_runtime import (
    CLAUDE_FILES_API_BETA,
    GEMINI_GENERATE_TIMEOUT_MS,
    HeartbeatMonitor,
    RequestRuntime,
    build_payload,
    build_request_cache_key,
    generate_retry,
    handle_stream,
    sha256_file,
    sha256_text,
    stream_with_cache,
)
from chronicle_app.services.runtime_policies import DEFAULT_CLAUDE_MODEL


class ProcessingRuntimeTest(unittest.TestCase):
    def test_sha_helpers_are_stable(self):
        self.assertEqual(sha256_text("abc"), sha256_text("abc"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "x.txt")
            with open(path, "wb") as fh:
                fh.write(b"hello")
            self.assertEqual(sha256_file(path), sha256_file(path))
        self.assertIn("model|kind|", build_request_cache_key("model", "prompt", "kind", "fp"))

    def test_handle_stream_sanitizes_and_writes_streamable_output(self):
        class Chunk:
            def __init__(self, text):
                self.text = text

        writes = []

        class FakeFile:
            def write(self, text):
                writes.append(text)

            def flush(self):
                writes.append("flushed")

        result = handle_stream(
            [Chunk(" alpha "), Chunk("beta")],
            "out.html",
            "html",
            FakeFile(),
            [],
            log_cb=lambda _msg: None,
            heartbeat=None,
            sanitize_model_output_fn=lambda text, _fmt: text.upper(),
            clean_text_fn=lambda text: text.strip(),
        )

        self.assertEqual(result, "ALPHA BETA")
        self.assertIn("ALPHA BETA", writes)

    def test_handle_stream_sanitizes_across_chunk_boundaries_before_writing(self):
        class Chunk:
            def __init__(self, text):
                self.text = text

        writes = []

        class FakeFile:
            def write(self, text):
                writes.append(text)

            def flush(self):
                writes.append("flushed")

        result = handle_stream(
            [Chunk("<style>.x{"), Chunk("color:red;}</style><p>Body</p>")],
            "out.html",
            "html",
            FakeFile(),
            [],
            log_cb=lambda _msg: None,
            heartbeat=None,
            sanitize_model_output_fn=lambda text, _fmt: text.replace("<style>.x{color:red;}</style>", ""),
            clean_text_fn=lambda text: text,
        )

        self.assertEqual(result, "<p>Body</p>")
        self.assertEqual(writes[0], "<p>Body</p>")

    def test_handle_stream_writes_preclean_stream_chunks_immediately(self):
        class PrecleanStream:
            _chronicle_preclean_stream = True

            def __iter__(self):
                return iter(["<section>\n", "<p>first line</p>\n"])

        writes = []

        class FakeFile:
            def write(self, text):
                writes.append(text)

            def flush(self):
                writes.append("flushed")

        memory = []
        result = handle_stream(
            PrecleanStream(),
            "out.html",
            "html",
            FakeFile(),
            memory,
            log_cb=lambda _msg: None,
            heartbeat=None,
            sanitize_model_output_fn=lambda text, _fmt: self.fail("preclean stream should not be re-sanitized per chunk"),
            clean_text_fn=lambda text: text,
        )

        self.assertEqual(result, "<section>\n<p>first line</p>\n")
        self.assertEqual(memory, ["<section>\n", "<p>first line</p>\n"])
        self.assertEqual(writes, ["<section>\n", "flushed", "<p>first line</p>\n", "flushed"])

    def test_handle_stream_accepts_plain_string_chunks(self):
        memory = []
        result = handle_stream(
            iter(["alpha ", "beta"]),
            "out.txt",
            "txt",
            None,
            memory,
            log_cb=lambda _msg: None,
            heartbeat=None,
            sanitize_model_output_fn=lambda text, _fmt: text.upper(),
            clean_text_fn=lambda text: text.strip(),
        )

        self.assertEqual(result, "ALPHA BETA")
        self.assertEqual(memory, ["ALPHA BETA"])

    def test_handle_stream_times_out_when_stream_stops_yielding_chunks(self):
        class BlockingStream:
            def __iter__(self):
                return self

            def __next__(self):
                time.sleep(1)
                return type("Chunk", (), {"text": "late"})()

        with self.assertRaises(TimeoutError) as ctx:
            handle_stream(
                BlockingStream(),
                "out.html",
                "html",
                None,
                [],
                log_cb=lambda _msg: None,
                heartbeat=None,
                sanitize_model_output_fn=lambda text, _fmt: text,
                clean_text_fn=lambda text: text,
                stream_chunk_timeout_sec=0.01,
            )

        self.assertIn("Timed out waiting for streamed model output", str(ctx.exception))

    def test_handle_stream_accepts_nonstream_text_response(self):
        response = type("Response", (), {"text": " complete page "})()
        memory = []

        result = handle_stream(
            response,
            "out.html",
            "html",
            None,
            memory,
            log_cb=lambda _msg: None,
            heartbeat=None,
            sanitize_model_output_fn=lambda text, _fmt: text.upper(),
            clean_text_fn=lambda text: text.strip(),
        )

        self.assertEqual(result, "COMPLETE PAGE")
        self.assertEqual(memory, ["COMPLETE PAGE"])

    def test_stream_with_cache_reuses_cached_value(self):
        runtime = RequestRuntime(
            api_min_request_interval_sec=0,
            api_max_pending_requests=1,
            api_request_queue_poll_sec=0,
            api_max_concurrent_requests=1,
            api_cache_max_entries=10,
        )
        runtime.cache_put("key", "cached")
        appended = []

        result = stream_with_cache(
            "key",
            lambda: self.fail("request_fn should not run"),
            "out.txt",
            "txt",
            None,
            [],
            log_cb=lambda _msg: None,
            runtime=runtime,
            append_generated_text_fn=lambda fmt, file_obj, memory, text: appended.append((fmt, text)),
            handle_stream_fn=lambda *args, **kwargs: self.fail("handle_stream should not run"),
        )

        self.assertEqual(result, "cached")
        self.assertEqual(appended, [("txt", "cached")])

    def test_request_runtime_skips_large_cache_entries_and_can_clear_cache(self):
        runtime = RequestRuntime(
            api_min_request_interval_sec=0,
            api_max_pending_requests=1,
            api_request_queue_poll_sec=0,
            api_max_concurrent_requests=1,
            api_cache_max_entries=10,
            max_cache_text_chars=5,
        )

        runtime.cache_put("small", "12345")
        runtime.cache_put("large", "123456")
        self.assertEqual(runtime.cache_get("small"), "12345")
        self.assertIsNone(runtime.cache_get("large"))
        runtime.clear_cache()
        self.assertIsNone(runtime.cache_get("small"))

    def test_generate_retry_handles_auth_and_rate_limits(self):
        runtime = RequestRuntime(
            api_min_request_interval_sec=0,
            api_max_pending_requests=1,
            api_request_queue_poll_sec=0,
            api_max_concurrent_requests=1,
            api_cache_max_entries=10,
        )

        class RateLimitedClient:
            def __init__(self):
                self.calls = 0
                self.models = self

            def generate_content_stream(self, model=None, contents=None, config=None):
                self.calls += 1
                self.config = config
                if self.calls == 1:
                    raise Exception("429 overloaded")
                return "ok"

        sleeps = []
        result = generate_retry(
            RateLimitedClient(),
            "gemini-2.5-pro",
            ["payload"],
            runtime=runtime,
            max_r=2,
            delay=1,
            backoff_max_sec=5,
            log_cb=lambda _msg: None,
            time_module=types.SimpleNamespace(time=lambda: 0, sleep=lambda secs: sleeps.append(secs)),
            random_module=types.SimpleNamespace(uniform=lambda _a, _b: 0.25),
        )
        self.assertEqual(result, "ok")
        self.assertEqual(sleeps, [1.25])

        class AuthClient:
            def __init__(self):
                self.models = self

            def generate_content_stream(self, model=None, contents=None, config=None):
                raise Exception("401 unauthorized")

        with self.assertRaises(Exception) as ctx:
            generate_retry(
                AuthClient(),
                "gemini-2.5-pro",
                ["payload"],
                runtime=runtime,
                max_r=1,
                delay=1,
                backoff_max_sec=5,
                log_cb=lambda _msg: None,
            )
        self.assertIn("Authentication failed", str(ctx.exception))

    def test_generate_retry_applies_gemini_http_timeout(self):
        runtime = RequestRuntime(
            api_min_request_interval_sec=0,
            api_max_pending_requests=1,
            api_request_queue_poll_sec=0,
            api_max_concurrent_requests=1,
            api_cache_max_entries=10,
        )
        calls = []

        class Client:
            def __init__(self):
                self.models = self

            def generate_content_stream(self, **kwargs):
                calls.append(kwargs)
                return "ok"

        result = generate_retry(
            Client(),
            "gemini-2.5-pro",
            ["payload"],
            runtime=runtime,
            max_r=1,
            delay=1,
            backoff_max_sec=5,
            log_cb=lambda _msg: None,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(calls[0]["config"]["http_options"]["timeout"], GEMINI_GENERATE_TIMEOUT_MS)

    def test_generate_retry_uses_beta_messages_for_claude_file_requests(self):
        runtime = RequestRuntime(
            api_min_request_interval_sec=0,
            api_max_pending_requests=1,
            api_request_queue_poll_sec=0,
            api_max_concurrent_requests=1,
            api_cache_max_entries=10,
        )
        calls = []

        class BetaMessages:
            def create(self, **kwargs):
                calls.append(kwargs)
                return "ok"

        class Client:
            def __init__(self):
                self.beta = types.SimpleNamespace(messages=BetaMessages())

        payload = {
            "_chronicle_claude_request": "message",
            "content": [{"type": "document", "source": {"type": "file", "file_id": "file_123"}}],
            "betas": [CLAUDE_FILES_API_BETA],
        }

        result = generate_retry(
            Client(),
            "claude-3-5-sonnet-20241022",
            payload,
            runtime=runtime,
            max_r=1,
            delay=1,
            backoff_max_sec=5,
            log_cb=lambda _msg: None,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(calls[0]["betas"], [CLAUDE_FILES_API_BETA])
        self.assertEqual(calls[0]["model"], DEFAULT_CLAUDE_MODEL)
        self.assertEqual(calls[0]["messages"][0]["content"], payload["content"])

    def test_build_payload_handles_claude_and_gpt_inputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "img.png")
            with open(path, "wb") as fh:
                fh.write(b"image-bytes")

            claude_payload = build_payload("claude-3-5-sonnet", "Prompt", path, "image/png")
            gpt_payload = build_payload("gpt-4o", "Prompt", path, "image/png")

            self.assertEqual(claude_payload[0]["type"], "image")
            self.assertEqual(gpt_payload[0]["type"], "text")
            with self.assertRaises(Exception):
                build_payload("gpt-4o", "Prompt", path, "application/pdf")

    def test_build_payload_accepts_in_memory_file_bytes(self):
        claude_payload = build_payload(
            "claude-3-5-sonnet",
            "Prompt",
            mime="application/pdf",
            file_bytes=b"%PDF-1.4\nhello",
        )

        self.assertEqual(claude_payload[0]["type"], "document")
        self.assertEqual(claude_payload[1]["text"], "Prompt")

    def test_heartbeat_monitor_uses_exit_hook(self):
        exits = []
        timer_events = []

        class FakeTimer:
            def __init__(self, timeout, fn):
                self.timeout = timeout
                self.fn = fn

            def start(self):
                timer_events.append(("start", self.timeout))

            def cancel(self):
                timer_events.append(("cancel", self.timeout))

        monitor = HeartbeatMonitor(timeout=5, exit_fn=lambda code: exits.append(code), print_fn=lambda _msg: None, timer_cls=FakeTimer)
        monitor.ping()
        monitor._stall_abort()
        monitor.stop()

        self.assertEqual(exits, [1])
        self.assertIn(("start", 5), timer_events)

    def test_heartbeat_monitor_without_exit_hook_keeps_process_alive(self):
        messages = []
        monitor = HeartbeatMonitor(
            timeout=5,
            exit_fn=None,
            print_fn=messages.append,
            timer_cls=lambda _timeout, _fn: type(
                "Timer",
                (),
                {"start": lambda self: None, "cancel": lambda self: None},
            )(),
        )

        monitor._stall_abort()

        self.assertEqual(
            messages,
            ["\n[NETWORK STALL ALERT] API connection has been quiet for over 5 minutes. Keeping Chronicle open for recovery."],
        )

    def test_gui_does_not_wire_heartbeat_to_hard_process_exit(self):
        gui_source = Path(__file__).resolve().parents[1] / "chronicle_gui.py"

        self.assertNotIn("HeartbeatMonitor(exit_fn=os._exit)", gui_source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
