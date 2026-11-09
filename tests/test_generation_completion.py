import ast
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from chronicle_app.services.gemini_rest_payloads import extract_gemini_text_from_data
from chronicle_app.services.processing_runtime import handle_stream, RequestRuntime, stream_with_cache


class GenerationCompletionTests(unittest.TestCase):
    def stream(self, chunks, file=None):
        return handle_stream(chunks, 'out.html', 'html', file, [], lambda message: None,
                             sanitize_model_output_fn=lambda text, fmt: text, clean_text_fn=lambda text: text)

    def test_sdk_token_limits_never_write_successful_output(self):
        for chunk in (NS(candidates=[NS(finish_reason='MAX_TOKENS')], text='partial'),
                      NS(choices=[NS(finish_reason='length', delta=NS(content='partial'))]),
                      NS(type='message_delta', delta=NS(stop_reason='max_tokens'))):
            with self.subTest(chunk=chunk):
                output = io.StringIO()
                with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                    self.stream([NS(text='beginning'), chunk], output)
                self.assertEqual(output.getvalue(), '')

    def test_normal_stop_keeps_complete_content(self):
        result = self.stream([NS(text='complete', candidates=[NS(finish_reason='STOP')])])
        self.assertEqual(result, 'complete')

    def test_rest_token_limit_rejects_partial_content(self):
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            extract_gemini_text_from_data({'candidates': [{'finishReason': 'MAX_TOKENS', 'content': {'parts': [{'text': 'partial'}]}}]}, error_prefix='Gemini')

    def test_incomplete_stream_is_not_cached(self):
        runtime = RequestRuntime(api_min_request_interval_sec=0, api_max_pending_requests=1, api_request_queue_poll_sec=0.01, api_max_concurrent_requests=1, api_cache_max_entries=10)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            stream_with_cache('test', lambda: [NS(text='partial', candidates=[NS(finish_reason='MAX_TOKENS')])],
                              'out.html', 'html', io.StringIO(), [], lambda message: None, runtime=runtime,
                              append_generated_text_fn=Mock(), handle_stream_fn=lambda *args, **kwargs: self.stream(args[0]))
        self.assertIsNone(runtime.cache_get('test'))

    def test_cli_newspaper_keeps_text_after_twelve_thousand_characters(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'chronicle_runtime.py').read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'handle_stream')
        writes = []
        scope = {'heartbeat': Mock(), 'sanitize_model_output': lambda text, fmt: text,
                 'clean_text_artifacts': lambda text: text, '_filter_streaming_inline_image_payload': lambda text, state: text,
                 'append_generated_text': lambda fmt, **kw: writes.append(kw['text']),
                 'core_build_newspaper_safety_notice': lambda fmt: 'old cutoff notice'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<cli stream>', 'exec'), scope)
        chunks = [NS(text='a' * 13000), NS(text='Final article and source footer.')]
        result = scope['handle_stream'](chunks, 'out.html', 'html', profile_key='newspaper')
        self.assertTrue(result.endswith('Final article and source footer.'))
        self.assertNotIn('old cutoff notice', result)
