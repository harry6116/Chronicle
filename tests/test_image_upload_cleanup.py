import types
import unittest
from unittest.mock import Mock, patch

import chronicle_runtime
from chronicle_app.services.document_processors import process_img


class ImageUploadCleanupTest(unittest.TestCase):
    def run_image(self, mode, client, wait, generate):
        def stream(_key, request, *_args, **_kwargs):
            response, cleanup = request()
            try:
                return response
            finally:
                cleanup()

        if mode == 'cli':
            with patch.object(chronicle_runtime, 'prepare_image_for_scan', return_value='source.png'), \
                    patch.object(chronicle_runtime, 'enhance_image_for_microtext', return_value='source.png'), \
                    patch.object(chronicle_runtime, 'sha256_file', return_value='hash'), \
                    patch.object(chronicle_runtime, 'wait_for_gemini_upload_ready', wait), \
                    patch.object(chronicle_runtime, 'generate_with_retry', generate), \
                    patch.object(chronicle_runtime, 'stream_with_cache', stream):
                chronicle_runtime.process_image(client, 'source.png', 'out.html', 'html', 'Prompt', 'gemini-2.5-pro', None, [])
        else:
            with patch('chronicle_app.services.document_processors.wait_for_gemini_upload_ready', wait):
                process_img(client, 'source.png', 'out.html', 'html', 'Prompt', 'gemini-2.5-pro', None, [], lambda _: None,
                            enhance_image_fn=lambda p: p, build_payload_fn=Mock(),
                            build_request_cache_key_fn=lambda *_: 'key', sha256_file_fn=lambda _: 'hash',
                            stream_with_cache_fn=stream, generate_retry_fn=generate,
                            image_prepare_fn=lambda p, **_: p)

    def test_uploaded_image_is_deleted_after_generation_rejection(self):
        for mode in ('cli', 'gui'):
            with self.subTest(mode=mode):
                uploaded = types.SimpleNamespace(name='files/disposable')
                client = types.SimpleNamespace(files=Mock())
                client.files.upload.return_value = uploaded
                with self.assertRaisesRegex(RuntimeError, 'credits depleted'):
                    self.run_image(mode, client, Mock(return_value=uploaded), Mock(side_effect=RuntimeError('credits depleted')))
                client.files.delete.assert_called_once()
                self.assertEqual(client.files.delete.call_args.kwargs['name'], uploaded.name)

    def test_uploaded_image_is_deleted_after_readiness_failure(self):
        for mode in ('cli', 'gui'):
            with self.subTest(mode=mode):
                client = types.SimpleNamespace(files=Mock())
                client.files.upload.return_value = types.SimpleNamespace(name='files/disposable')
                with self.assertRaisesRegex(RuntimeError, 'not ready'):
                    self.run_image(mode, client, Mock(side_effect=RuntimeError('not ready')), Mock())
                client.files.delete.assert_called_once()

    def test_success_keeps_upload_until_stream_consumption_then_deletes_once(self):
        for mode in ('cli', 'gui'):
            with self.subTest(mode=mode):
                client = types.SimpleNamespace(files=Mock())
                uploaded = types.SimpleNamespace(name='files/disposable')
                client.files.upload.return_value = uploaded
                def generate(*_args, **_kwargs):
                    client.files.delete.assert_not_called()
                    return 'Transcript'
                self.run_image(mode, client, Mock(return_value=uploaded), generate)
                client.files.delete.assert_called_once()
