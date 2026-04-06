import unittest

from chronicle_app.services.worker_execute_runtime import (
    build_confidence_callback,
    build_page_progress_callback,
    dispatch_processing_for_job,
    log_image_quality_if_needed,
    process_job_content,
)


class WorkerExecuteRuntimeTest(unittest.TestCase):
    def test_build_confidence_callback_logs_scaled_score(self):
        logs = []
        cb = build_confidence_callback(
            enabled=True,
            file_name='alpha.pdf',
            describe_quality_score_fn=lambda score, method: f'{method}:{score:.1f}',
            log_cb=logs.append,
        )
        cb(2, 0.83, 'vision')
        self.assertIn('[Confidence] alpha.pdf page 2: 8.3/10 - vision:8.3', logs[0])

    def test_log_image_quality_if_needed_respects_ext_and_quality(self):
        logs = []
        self.assertTrue(log_image_quality_if_needed(
            enabled=True,
            ext='.png',
            path='/tmp/a.png',
            file_name='a.png',
            assess_image_file_quality_fn=lambda path: (7.5, 'clear'),
            log_cb=logs.append,
        ))
        self.assertIn('[Quality] a.png: 7.5/10 - clear', logs[0])

    def test_build_page_progress_callback_updates_and_logs(self):
        logs = []
        state = {'done': 0, 'total': 0, 'processed': 0, 'refreshed': 0}
        def update(done, total):
            state['done'] = done
            state['total'] = total
            state['processed'] += 1
            return state['processed']
        cb = build_page_progress_callback(
            file_name='alpha.pdf',
            update_progress_state_fn=update,
            should_log_page_progress_fn=lambda done, total: True,
            log_cb=logs.append,
            refresh_progress_fn=lambda: state.__setitem__('refreshed', state['refreshed'] + 1),
            memory=None,
        )
        cb(1, 5, 3)
        self.assertEqual(state['done'], 1)
        self.assertEqual(state['refreshed'], 1)
        self.assertIn('[Page] 1/5 pages processed (source page 3, run total: 1).', logs[0])

    def test_build_page_progress_callback_uses_resume_wording_when_recovering_remaining_pages(self):
        logs = []
        cb = build_page_progress_callback(
            file_name='alpha.pdf',
            update_progress_state_fn=lambda done, total: done + 312,
            should_log_page_progress_fn=lambda done, total: True,
            log_cb=logs.append,
            refresh_progress_fn=lambda: None,
            memory=None,
            resume_recovered_units=312,
            original_total_units=386,
        )

        cb(56, 74, 368)
        self.assertIn(
            '[Page] Resume pass: 56/74 remaining pages complete (currently on source page 368; total progress: 368/386).',
            logs[0],
        )

    def test_build_page_progress_callback_flushes_and_clears_memory_guard(self):
        logs = []

        class MemoryGuard(list):
            def __init__(self):
                super().__init__()
                self.flushed = 0
                self.mark_calls = 0

            def force_flush(self):
                self.flushed += 1

            def mark_page_processed(self):
                self.mark_calls += 1
                return self.mark_calls == 5

        memory = MemoryGuard()
        cb = build_page_progress_callback(
            file_name='alpha.pdf',
            update_progress_state_fn=lambda done, total: done,
            should_log_page_progress_fn=lambda done, total: False,
            log_cb=logs.append,
            refresh_progress_fn=lambda: None,
            memory=memory,
        )
        for idx in range(1, 6):
            cb(idx, 20, idx)

        self.assertEqual(memory.flushed, 5)
        self.assertEqual(memory.mark_calls, 5)
        self.assertTrue(any('Cleared buffered page text at run page 5.' in log for log in logs))

    def test_build_page_progress_callback_supports_chunk_wording(self):
        logs = []
        cb = build_page_progress_callback(
            file_name='alpha.docx',
            update_progress_state_fn=lambda done, total: done,
            should_log_page_progress_fn=lambda done, total: True,
            log_cb=logs.append,
            refresh_progress_fn=lambda: None,
            memory=None,
            log_prefix='Chunk',
            unit_label='chunk',
        )

        cb(2, 7)
        self.assertIn('[Chunk] 2/7 chunks processed (run total: 2).', logs[0])

    def test_process_job_content_reads_streamed_temp_file_for_pdf_audit(self):
        logs = []

        class MemoryGuard(list):
            def force_flush(self):
                return None

            def mark_page_processed(self):
                return False

        memory = MemoryGuard()

        def process_pdf(*args, **kwargs):
            kwargs["page_progress_cb"](1, 2, 1)
            args[6].write("first page\n")
            args[7].append("first page\n")
            kwargs["page_progress_cb"](2, 2, 2)
            args[6].write("second page\n")
            args[7].clear()

        captured = {}

        def append_audit(**kwargs):
            captured["text"] = kwargs["extracted_text"]

        import tempfile

        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=True) as temp_file:
            process_job_content(
                '.pdf',
                cfg={'page_confidence_scoring': False},
                path='/tmp/alpha.pdf',
                file_name='alpha.pdf',
                temp_path=temp_file.name,
                fmt='html',
                prompt='prompt',
                model='model',
                client=object(),
                file_obj=temp_file,
                memory=memory,
                processing_log=logs.append,
                pause_cb=lambda: None,
                page_scope='',
                describe_quality_score_fn=lambda score, method: f'{method}:{score:.1f}',
                assess_image_file_quality_fn=lambda path: None,
                update_progress_state_fn=lambda done, total: done,
                should_log_page_progress_fn=lambda done, total: False,
                refresh_progress_fn=lambda: None,
                needs_pdf_audit=True,
                append_pdf_audit_appendix_if_needed_fn=append_audit,
                run_pdf_textlayer_audit_fn=lambda path, text: None,
                render_audit_appendix_fn=lambda fmt, title, body: body,
                append_generated_text_fn=lambda fmt, file_obj, memory, text: memory.append(text),
                coverage_warn_threshold=0.9,
                coverage_append_full_threshold=0.7,
                process_pdf_fn=process_pdf,
                process_pptx_fn=lambda *args, **kwargs: None,
                process_epub_fn=lambda *args, **kwargs: None,
                process_img_fn=lambda *args, **kwargs: None,
                process_text_fn=lambda *args, **kwargs: None,
            )

        self.assertEqual(captured["text"], "first page\nsecond page\n")


    def test_process_job_content_runs_pdf_callbacks_and_audit(self):
        calls = []
        logs = []
        memory = ['existing']

        def process_pdf(*args, **kwargs):
            calls.append(('pdf', kwargs['page_scope'], kwargs['confidence_cb'] is not None, kwargs['page_progress_cb'] is not None))
            args[7].append('new text')
            kwargs['page_progress_cb'](1, 2, 4)
            kwargs['confidence_cb'](4, 0.8, 'vision')

        def append_audit(**kwargs):
            calls.append(('audit', kwargs['pdf_path'], kwargs['extracted_text'], kwargs['page_scope']))

        result = process_job_content(
            '.pdf',
            cfg={'page_confidence_scoring': True},
            path='/tmp/alpha.pdf',
            file_name='alpha.pdf',
            temp_path='/tmp/alpha.tmp',
            fmt='html',
            prompt='prompt',
            model='model',
            client=object(),
            file_obj=None,
            memory=memory,
            processing_log=logs.append,
            pause_cb=lambda: None,
            page_scope='1-2',
            describe_quality_score_fn=lambda score, method: f'{method}:{score:.1f}',
            assess_image_file_quality_fn=lambda path: None,
            update_progress_state_fn=lambda done, total: 9,
            should_log_page_progress_fn=lambda done, total: True,
            refresh_progress_fn=lambda: calls.append(('refresh',)),
            needs_pdf_audit=True,
            append_pdf_audit_appendix_if_needed_fn=append_audit,
            run_pdf_textlayer_audit_fn=lambda path, text: None,
            render_audit_appendix_fn=lambda fmt, title, body: body,
            append_generated_text_fn=lambda fmt, file_obj, memory, text: memory.append(text),
            coverage_warn_threshold=0.9,
            coverage_append_full_threshold=0.7,
            process_pdf_fn=process_pdf,
            process_pptx_fn=lambda *args, **kwargs: None,
            process_epub_fn=lambda *args, **kwargs: None,
            process_img_fn=lambda *args, **kwargs: None,
            process_text_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result, 'new text')
        self.assertIn(('pdf', '1-2', True, True), calls)
        self.assertIn(('audit', '/tmp/alpha.pdf', 'new text', '1-2'), calls)
        self.assertTrue(any('[Page] 1/2 pages processed (source page 4, run total: 9).' in log for log in logs))
        self.assertTrue(any('[Confidence] alpha.pdf page 4: 8.0/10 - vision:8.0' in log for log in logs))

    def test_dispatch_processing_for_job_routes_by_extension(self):
        calls = []
        def mark(name):
            def inner(*args, **kwargs):
                calls.append((name, kwargs))
            return inner
        dispatch_processing_for_job(
            '.pdf',
            job_cfg={'doc_profile': 'legal'},
            client=None, path='a', temp_path='b', fmt='html', prompt='p', model='m', file_obj=None, memory=[],
            processing_log=lambda msg: None, pause_cb=lambda: None, confidence_cb='conf', page_progress_cb='page', page_scope='1-2',
            auto_escalation_model='gemini-2.5-pro',
            process_pdf_fn=mark('pdf'), process_pptx_fn=mark('pptx'), process_epub_fn=mark('epub'), process_img_fn=mark('img'), process_text_fn=mark('text'),
        )
        dispatch_processing_for_job(
            '.epub',
            job_cfg={'doc_profile': 'standard'},
            client=None, path='a', temp_path='b', fmt='html', prompt='p', model='m', file_obj=None, memory=[],
            processing_log=lambda msg: None, pause_cb=lambda: None, confidence_cb='conf', page_progress_cb='page', page_scope='1-2',
            auto_escalation_model=None,
            process_pdf_fn=mark('pdf'), process_pptx_fn=mark('pptx'), process_epub_fn=mark('epub'), process_img_fn=mark('img'), process_text_fn=mark('text'),
        )
        self.assertEqual(calls[0][0], 'pdf')
        self.assertEqual(calls[0][1]['page_scope'], '1-2')
        self.assertEqual(calls[0][1]['doc_profile'], 'legal')
        self.assertEqual(calls[0][1]['auto_escalation_model'], 'gemini-2.5-pro')
        self.assertEqual(calls[1][0], 'epub')


if __name__ == '__main__':
    unittest.main()
