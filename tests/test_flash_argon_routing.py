import io
import types
import unittest
from unittest.mock import patch

from chronicle_app.services.runtime_policies import GEMINI_FAST_MODEL, GEMINI_REASONING_MODEL


class FlashArgonRoutingTests(unittest.TestCase):
    def test_separate_mode_selects_flash_and_argon_without_changing_existing_automatic(self):
        from chronicle_app.services.runtime_policies import FLASH_ARGON_MODE
        from chronicle_app.services.adaptive_engine_routing import select_execution_model_for_job
        for ext in ('.pdf', '.png', '.heic'):
            result = select_execution_model_for_job('source' + ext, ext, {'model_override': FLASH_ARGON_MODE}, 'gemini-3.1-pro-preview')
            self.assertEqual(result['model_name'], GEMINI_FAST_MODEL)
            self.assertEqual(result['auto_escalation_model'], GEMINI_REASONING_MODEL)
            self.assertEqual(result['routing_mode'], 'adaptive')
        manual = select_execution_model_for_job('a.pdf', '.pdf', {'model_override': GEMINI_FAST_MODEL}, GEMINI_FAST_MODEL)
        self.assertIsNone(manual['auto_escalation_model'])
        offline = select_execution_model_for_job('a.pdf', '.pdf', {'model_override': FLASH_ARGON_MODE}, 'chronicle-offline-private')
        self.assertEqual(offline['model_name'], 'chronicle-offline-private')
        self.assertIsNone(offline['auto_escalation_model'])

    def test_clean_uncertain_clean_sequence_resets_to_flash(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        calls = []
        for page in (1, 2, 3):
            def read(model):
                calls.append((page, model))
                return '[Unclear Word: x]' if page == 2 and model == GEMINI_FAST_MODEL else f'Complete page {page}'
            result = read_adaptive_page(read, fmt='txt', log_cb=lambda _: None)
            self.assertEqual(result.model, GEMINI_REASONING_MODEL if page == 2 else GEMINI_FAST_MODEL)
        self.assertEqual(calls, [(1, GEMINI_FAST_MODEL), (2, GEMINI_FAST_MODEL), (2, GEMINI_REASONING_MODEL), (3, GEMINI_FAST_MODEL)])

    def test_token_limit_retries_but_auth_network_and_cancellation_do_not(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        from chronicle_app.services.generation_completion import IncompleteGenerationError
        calls = []
        def limited(model):
            calls.append(model)
            if model == GEMINI_FAST_MODEL:
                raise IncompleteGenerationError('MAX_TOKENS')
            return 'Complete reading'
        self.assertEqual(read_adaptive_page(limited, fmt='txt', log_cb=lambda _: None).text, 'Complete reading')
        self.assertEqual(calls, [GEMINI_FAST_MODEL, GEMINI_REASONING_MODEL])
        for error in (PermissionError('authentication'), OSError('network'), InterruptedError('cancel'), IncompleteGenerationError('SAFETY')):
            calls = []
            def fail(model):
                calls.append(model)
                raise error
            with self.assertRaises(type(error)):
                read_adaptive_page(fail, fmt='txt', log_cb=lambda _: None)
            self.assertEqual(calls, [GEMINI_FAST_MODEL])

    def test_failed_argon_keeps_complete_flash_with_warning(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        logs = []
        def read(model):
            if model == GEMINI_REASONING_MODEL:
                raise OSError('network')
            return 'Readable text [Illegible Signature]'
        result = read_adaptive_page(read, fmt='txt', log_cb=logs.append)
        self.assertEqual(result.model, GEMINI_FAST_MODEL)
        self.assertEqual(result.text, 'Readable text [Illegible Signature]')
        self.assertTrue(result.needs_review)
        self.assertTrue(any('retained' in line.lower() for line in logs))

    def test_failed_or_empty_both_never_accept_incomplete_page(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        with self.assertRaises(RuntimeError):
            read_adaptive_page(lambda _: '', fmt='html', log_cb=lambda _: None)

    def test_uncertainty_in_argon_does_not_loop_or_disappear(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        calls = []
        def read(model):
            calls.append(model)
            return '[Unclear Letters: x]'
        result = read_adaptive_page(read, fmt='txt', log_cb=lambda _: None)
        self.assertTrue(result.needs_review)
        self.assertIn('[Unclear Letters:', result.text)
        self.assertEqual(calls, [GEMINI_FAST_MODEL, GEMINI_REASONING_MODEL])

    def test_html_title_and_explicit_blank_page_are_not_treated_as_unreadable(self):
        from chronicle_app.services.page_engine_routing import page_review_reason
        self.assertIsNone(page_review_reason('<h1>A title page</h1>', fmt='html'))
        self.assertIsNone(page_review_reason('[Blank page]', fmt='txt'))
        self.assertIsNotNone(page_review_reason('<section><h2>Page 4</h2></section>', fmt='html'))

    def test_pause_cancel_before_retry_does_not_commit_a_draft(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        calls = []
        def pause():
            if calls:
                raise InterruptedError('cancel')
        def read(model):
            calls.append(model)
            return '[Unclear Word]'
        with self.assertRaises(InterruptedError):
            read_adaptive_page(read, fmt='txt', pause_cb=pause, log_cb=lambda _: None)
        self.assertEqual(calls, [GEMINI_FAST_MODEL])

    def test_pdf_selected_pages_commit_once_and_report_progress_once(self):
        import chronicle_app.services.pdf_processor as module
        calls, progress, confidence, memory = [], [], [], []
        file_obj = io.StringIO()
        reader = types.SimpleNamespace(pages=[object() for _ in range(4)])
        def engine(**kwargs):
            self.assertIsNone(kwargs['f_obj'])
            page = kwargs['parse_pdf_page_scope_spec_fn']('', 4)[0] + 1
            model = kwargs['model']; calls.append((page, model))
            text = f'<h2>Page {page}</h2><p>' + ('FLASH DRAFT [Unclear Word]' if page == 2 and model == GEMINI_FAST_MODEL else f'Accepted {page}') + '</p>'
            kwargs['mem'].append(text)
            if kwargs['confidence_cb']:
                kwargs['confidence_cb'](page, .9, model)
            return {'used_dense_newspaper_local_ocr': False}
        arguments = dict(client=None, path='scan.pdf', out='out.html', fmt='html', prompt='transcribe', model=GEMINI_FAST_MODEL,
            f_obj=file_obj, mem=memory, log_cb=lambda _: None, auto_escalation_model=GEMINI_REASONING_MODEL,
            page_scope='2,4', script_dir='.', pdf_reader_cls=lambda _: reader, pdf_writer_cls=object,
            parse_pdf_page_scope_spec_fn=lambda *_: [1, 3], normalize_pdf_page_scope_text_fn=lambda x: x,
            get_pdf_chunk_pages_fn=None, sha256_file_fn=None, sha256_text_fn=None, build_payload_fn=None,
            build_request_cache_key_fn=None, stream_with_cache_fn=None, generate_retry_fn=None,
            split_text_for_fail_safe_fn=None, page_progress_cb=lambda *a: progress.append(a), confidence_cb=lambda *a: confidence.append(a))
        with patch.object(module, '_process_pdf_pages', side_effect=engine):
            module.process_pdf(**arguments)
        self.assertEqual(calls, [(2, GEMINI_FAST_MODEL), (2, GEMINI_REASONING_MODEL), (4, GEMINI_FAST_MODEL)])
        self.assertNotIn('FLASH DRAFT', file_obj.getvalue())
        self.assertEqual(file_obj.getvalue(), ''.join(memory))
        self.assertEqual(progress, [(1, 2, 2), (2, 2, 4)])
        self.assertEqual([row[0] for row in confidence], [2, 4])

    def test_two_page_boundaries_without_content_are_not_accepted(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        with self.assertRaises(RuntimeError):
            read_adaptive_page(lambda _: '<section><h2>Page 4</h2></section>', fmt='html', log_cb=lambda _: None)

    def test_gui_stop_state_during_argon_is_not_swallowed(self):
        from chronicle_app.services.page_engine_routing import read_adaptive_page
        class StopRequested(Exception):
            pass
        stopped = False
        def pause():
            if stopped:
                raise StopRequested()
        def read(model):
            nonlocal stopped
            if model == GEMINI_REASONING_MODEL:
                stopped = True
                raise StopRequested()
            return 'Text [Unclear Word]'
        with self.assertRaises(StopRequested):
            read_adaptive_page(read, fmt='txt', log_cb=lambda _: None, pause_cb=pause)

    def test_mode_requires_gemini_even_when_other_provider_key_exists(self):
        from chronicle_app.services.runtime_policies import FLASH_ARGON_MODE
        from chronicle_app.services.run_start_runtime import find_missing_api_key_requirement
        result = find_missing_api_key_requirement([{'engine': 'Claude'}],
            normalize_row_settings_fn=lambda _: {'model_name':'claude-sonnet-4-6','model_override':FLASH_ARGON_MODE},
            model_from_label_fn=lambda _: 'claude-sonnet-4-6', label_from_model_fn=lambda x: x,
            has_vendor_key_fn=lambda vendor: vendor == 'claude')
        self.assertEqual(result['vendor'], 'gemini')
        self.assertEqual(result['label'], FLASH_ARGON_MODE)

    def test_real_pdf_slices_reset_models_and_clean_every_upload(self):
        import tempfile
        from pathlib import Path
        import fitz
        from chronicle_gui import PdfReader, PdfWriter
        from chronicle_app.services.pdf_processor import process_pdf
        from chronicle_app.services.runtime_policies import get_pdf_chunk_pages
        uploaded, deleted, calls, memory, progress = [], [], [], [], []
        generation_failure = None
        class Files:
            def upload(self, *, file, config):
                data = file.read()
                with fitz.open(stream=data, filetype='pdf') as uploaded_pdf:
                    text = uploaded_pdf[0].get_text()
                item = types.SimpleNamespace(name=f'files/{len(uploaded)}', state=types.SimpleNamespace(name='ACTIVE'), source=text)
                uploaded.append(item.name)
                return item
            def delete(self, *, name, **kwargs):
                deleted.append(name)
        def generate(client, model, content, **kwargs):
            page = int(content[0].source.strip().split()[-1])
            calls.append((page, model))
            if page == 2 and generation_failure is not None:
                raise generation_failure
            return '<p>Rejected draft [Unclear Word: x]</p>' if page == 2 and model == GEMINI_FAST_MODEL else f'<p>Accepted page {page}</p>'
        def stream(key, request_fn, out, fmt, f_obj, mem, log_cb, **kwargs):
            text, cleanup = request_fn()
            try:
                self.assertIsNone(f_obj)
                mem.append(text)
                return text
            finally:
                cleanup()
        with tempfile.TemporaryDirectory(prefix='ChronicleAdaptiveTest-') as directory:
            path = Path(directory) / 'source.pdf'
            with fitz.open() as pdf:
                for n in (1, 2, 3):
                    page = pdf.new_page()
                    page.insert_text((60, 60), f'Source page {n}')
                pdf.save(path)
            def run(**extra):
                return process_pdf(types.SimpleNamespace(files=Files()), str(path), 'output.html', 'html', 'Transcribe', GEMINI_FAST_MODEL, None, memory, lambda _: None,
                    auto_escalation_model=GEMINI_REASONING_MODEL, script_dir=directory, pdf_reader_cls=PdfReader, pdf_writer_cls=PdfWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)), normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=get_pdf_chunk_pages, sha256_file_fn=lambda _: 'hash', sha256_text_fn=lambda _: 'hash', build_payload_fn=lambda *a, **k: None,
                    build_request_cache_key_fn=lambda *a: repr(a), stream_with_cache_fn=stream, generate_retry_fn=generate,
                    split_text_for_fail_safe_fn=lambda text, **k: [text], page_progress_cb=lambda *a: progress.append(a), **extra)
            run()
            self.assertEqual(calls, [(1, GEMINI_FAST_MODEL), (2, GEMINI_FAST_MODEL), (2, GEMINI_REASONING_MODEL), (3, GEMINI_FAST_MODEL)])
            self.assertEqual(uploaded, deleted)
            self.assertNotIn('Rejected draft', ''.join(memory))
            self.assertEqual(progress, [(1, 3, 1), (2, 3, 2), (3, 3, 3)])
            for items in (uploaded, deleted, calls, memory, progress):
                items.clear()
            generation_failure = PermissionError('test authentication failure')
            with self.assertRaises(PermissionError):
                run()
            self.assertEqual(calls, [(1, GEMINI_FAST_MODEL), (2, GEMINI_FAST_MODEL)])
            self.assertEqual(uploaded, deleted)
            self.assertEqual(progress, [(1, 3, 1)])
            for items in (uploaded, deleted, calls, memory, progress):
                items.clear()
            generation_failure = None
            def wait_failure(*args, **kwargs):
                raise OSError('test upload polling failure')
            with self.assertRaises(OSError):
                run(wait_for_gemini_upload_ready_fn=wait_failure)
            self.assertEqual(len(uploaded), 1)
            self.assertEqual(uploaded, deleted)
            self.assertEqual(calls, [])
            self.assertEqual(memory, [])

    def test_images_commit_only_chosen_reading(self):
        from chronicle_app.services.worker_execute_runtime import dispatch_processing_for_job
        calls, memory = [], []
        output = io.StringIO()
        def image(client,path,out,fmt,prompt,model,file_obj,mem,log,**kwargs):
            self.assertIsNone(file_obj);calls.append(model)
            mem.append('[Unclear Word: draft]' if model == GEMINI_FAST_MODEL else 'Final image reading')
        unused=lambda *a,**k: self.fail('Unrelated processor was called')
        dispatch_processing_for_job('.png',job_cfg={},client=None,path='source.png',temp_path='output.html',fmt='html',prompt='Read',model=GEMINI_FAST_MODEL,
            file_obj=output,memory=memory,processing_log=lambda _: None,pause_cb=None,confidence_cb=None,page_progress_cb=None,page_scope='',auto_escalation_model=GEMINI_REASONING_MODEL,
            process_pdf_fn=unused,process_pptx_fn=unused,process_epub_fn=unused,process_img_fn=image,process_rendered_document_fn=unused,process_text_fn=unused)
        self.assertEqual(calls,[GEMINI_FAST_MODEL,GEMINI_REASONING_MODEL])
        self.assertEqual(output.getvalue(),'Final image reading')
        self.assertEqual(memory,['Final image reading'])

    def test_existing_automatic_and_manual_model_preferences_remain_distinct(self):
        from chronicle_app.config import MODEL_OVERRIDE_CHOICES, PROFILE_PRESETS
        from chronicle_app.services.runtime_policies import FLASH_ARGON_MODE, get_preferred_profile_model, get_model_tradeoff_text
        choices = dict(MODEL_OVERRIDE_CHOICES)
        self.assertIn('', choices)
        self.assertIn(FLASH_ARGON_MODE, choices)
        self.assertNotEqual(choices[''], choices[FLASH_ARGON_MODE])
        self.assertEqual(get_preferred_profile_model('medical',cfg={'model_override':''},profile_presets=PROFILE_PRESETS),'gemini-3.1-pro-preview')
        self.assertEqual(get_preferred_profile_model('medical',cfg={'model_override':FLASH_ARGON_MODE},profile_presets=PROFILE_PRESETS),GEMINI_FAST_MODEL)
        self.assertIn('cannot catch every error',get_model_tradeoff_text(FLASH_ARGON_MODE))

    def test_redactions_blank_cells_and_plain_word_unclear_do_not_trigger_retry(self):
        from chronicle_app.services.page_engine_routing import page_review_reason
        for text in ('[Redacted by Censor]', '[Blank]', 'The unclear case was discussed.'):
            self.assertIsNone(page_review_reason(text,fmt='txt'))

    def test_non_scanned_formats_do_not_claim_page_escalation(self):
        from chronicle_app.services.adaptive_engine_routing import select_execution_model_for_job
        from chronicle_app.services.runtime_policies import FLASH_ARGON_MODE
        result = select_execution_model_for_job('a.docx','.docx',{'model_override':FLASH_ARGON_MODE},GEMINI_FAST_MODEL)
        self.assertIsNone(result['auto_escalation_model'])
        self.assertIn('without page escalation', result['routing_reason'])

    def test_original_is_retained_when_adaptive_reading_needs_review(self):
        import tempfile
        from pathlib import Path
        from chronicle_app.services.worker_finalize_runtime import maybe_delete_source_file
        with tempfile.TemporaryDirectory(prefix='ChronicleAdaptiveSource-') as directory:
            source = Path(directory) / 'original.txt'
            source.write_text('Original source', encoding='utf-8')
            self.assertFalse(maybe_delete_source_file(str(source), delete_source_on_success=True,
                needs_review=True, is_protected_path_fn=lambda _: False, log_cb=lambda _: None))
            self.assertTrue(source.exists())
            self.assertTrue(maybe_delete_source_file(str(source), delete_source_on_success=True,
                needs_review=False, is_protected_path_fn=lambda _: False, log_cb=lambda _: None))
            self.assertFalse(source.exists())

    def test_gui_worker_passes_the_prepared_job_settings_without_mutating_global_preferences(self):
        import ast
        from pathlib import Path
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'chronicle_gui.py').read_text(encoding='utf-8'))
        call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'shared_process_job_content')
        cfg_argument = next(keyword.value for keyword in call.keywords if keyword.arg == 'cfg')
        global_cfg = {'model_override': ''}
        job_cfg = {'model_override': 'automatic-flash-argon', 'auto_escalation_model': GEMINI_REASONING_MODEL}
        actual = eval(compile(ast.Expression(cfg_argument), '<worker settings>', 'eval'), {'self':types.SimpleNamespace(cfg=global_cfg),'job_cfg':job_cfg})
        self.assertIs(actual, job_cfg)
        actual['automatic_review_pages'] = [2]
        self.assertNotIn('automatic_review_pages', global_cfg)

    def test_automatic_page_logging_does_not_assign_false_accuracy_scores(self):
        from chronicle_app.services.worker_execute_runtime import build_confidence_callback
        logs = []
        callback = build_confidence_callback(enabled=True, file_name='source.pdf', describe_quality_score_fn=lambda *a,**k: self.fail('No accuracy grade is available'), log_cb=logs.append)
        callback(1, 1.0, 'automatic-flash')
        callback(2, 1.0, 'automatic-review-required')
        callback(3, 1.0, 'automatic-argon')
        self.assertEqual(len(logs), 2)
        self.assertTrue(all('10' not in line and 'grade is assigned' in line for line in logs))


if __name__ == '__main__':
    unittest.main()
