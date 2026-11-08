import types
import unittest
from unittest.mock import Mock, patch

import chronicle_runtime
from chronicle_app.services.document_processors import process_img


class ImageUploadCleanupTest(unittest.TestCase):
    def run_image(self, mode, client, wait, generate, prompt='Prompt', enhance=None):
        enhance = enhance or Mock(return_value='source.png')
        def stream(_key, request, *_args, **_kwargs):
            response, cleanup = request()
            try:
                return response
            finally:
                cleanup()

        if mode == 'cli':
            with patch.object(chronicle_runtime, 'prepare_image_for_scan', return_value='source.png'), \
                    patch.object(chronicle_runtime, 'enhance_image_for_microtext', enhance), \
                    patch.object(chronicle_runtime, 'sha256_file', return_value='hash'), \
                    patch.object(chronicle_runtime, 'wait_for_gemini_upload_ready', wait), \
                    patch.object(chronicle_runtime, 'generate_with_retry', generate), \
                    patch.object(chronicle_runtime, 'append_comic_detail_views', side_effect=lambda contents, *_: contents), \
                    patch.object(chronicle_runtime, 'stream_with_cache', stream):
                chronicle_runtime.process_image(client, 'source.png', 'out.html', 'html', prompt, 'gemini-2.5-pro', None, [])
        else:
            with patch('chronicle_app.services.document_processors.wait_for_gemini_upload_ready', wait), \
                    patch('chronicle_app.services.document_processors.append_comic_detail_views', side_effect=lambda contents, *_: contents):
                process_img(client, 'source.png', 'out.html', 'html', prompt, 'gemini-2.5-pro', None, [], lambda _: None,
                            enhance_image_fn=enhance, build_payload_fn=Mock(),
                            build_request_cache_key_fn=lambda *_: 'key', sha256_file_fn=lambda _: 'hash',
                            stream_with_cache_fn=stream, generate_retry_fn=generate,
                            image_prepare_fn=lambda p, **_: p)

    def test_comics_preserve_colour_while_other_profiles_keep_microtext_enhancement(self):
        for mode in ('cli', 'gui'):
            for comic in (False, True):
                with self.subTest(mode=mode, comic=comic):
                    client = types.SimpleNamespace(files=Mock())
                    uploaded = types.SimpleNamespace(name='files/disposable')
                    client.files.upload.return_value = uploaded
                    enhance = Mock(return_value='source.png')
                    prompt = 'COMICS / MANGA / GRAPHIC NOVELS RULES:' if comic else 'Prompt'
                    self.run_image(mode, client, Mock(return_value=uploaded), Mock(return_value='Transcript'), prompt, enhance)
                    self.assertEqual(enhance.call_count, 0 if comic else 1)
                    self.assertEqual(client.files.upload.call_args.kwargs['file'], 'source.png')

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
