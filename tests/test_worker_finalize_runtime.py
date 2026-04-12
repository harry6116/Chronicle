import tempfile
import unittest
from pathlib import Path

from chronicle_app.services.worker_finalize_runtime import (
    append_pdf_audit_appendix_if_needed,
    cleanup_output_text,
    finalize_job_success,
    finalize_merged_output,
    finalize_single_output,
    finalize_worker_completion,
    finalize_worker_session,
    handle_job_error,
    maybe_delete_source_file,
    should_reject_cleaned_output,
)


class _FakeFile:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeWinSound:
    SND_ALIAS = 1
    SND_ASYNC = 2

    def __init__(self):
        self.calls = []

    def PlaySound(self, *args):
        self.calls.append(args)


class WorkerFinalizeRuntimeTest(unittest.TestCase):
    def test_append_pdf_audit_appendix_logs_and_appends_when_needed(self):
        logs = []
        appended = []

        changed = append_pdf_audit_appendix_if_needed(
            pdf_path='/tmp/a.pdf',
            extracted_text='text',
            page_scope='1-10',
            fmt='html',
            file_obj=None,
            memory=[],
            run_pdf_textlayer_audit_fn=lambda *_: {
                'coverage': 0.5,
                'missing_lines': ['a', 'b'],
                'source_text': 'full',
            },
            render_audit_appendix_fn=lambda fmt, heading, body: f'{heading}:{body}',
            append_generated_text_fn=lambda fmt, file_obj, memory, text: appended.append(text),
            coverage_warn_threshold=0.9,
            coverage_append_full_threshold=0.6,
            log_cb=logs.append,
        )

        self.assertTrue(changed)
        self.assertTrue(any('Low coverage detected' in entry for entry in logs))
        self.assertEqual(appended, ['Text-Layer Safety Appendix:full'])

    def test_append_pdf_audit_appendix_passes_page_scope_to_audit(self):
        calls = []

        append_pdf_audit_appendix_if_needed(
            pdf_path='/tmp/a.pdf',
            extracted_text='text',
            page_scope='1-100',
            fmt='html',
            file_obj=None,
            memory=[],
            run_pdf_textlayer_audit_fn=lambda path, text, page_scope='': calls.append((path, text, page_scope)) or None,
            render_audit_appendix_fn=lambda fmt, heading, body: body,
            append_generated_text_fn=lambda fmt, file_obj, memory, text: None,
            coverage_warn_threshold=0.9,
            coverage_append_full_threshold=0.6,
            log_cb=lambda _msg: None,
        )

        self.assertEqual(calls, [('/tmp/a.pdf', 'text', '1-100')])

    def test_cleanup_output_text_applies_text_transforms(self):
        cleaned = cleanup_output_text(
            'x',
            fmt='txt',
            job_cfg={'modernize_punctuation': True, 'unit_conversion': True, 'abbrev_expansion': True},
            normalize_html_fn=lambda value: value,
            modernize_punctuation_fn=lambda value: value + 'p',
            modernize_currency_fn=lambda value: value + 'c',
            expand_abbreviations_fn=lambda value: value + 'a',
            enforce_heading_structure_fn=lambda content, fmt, profile: content,
        )

        self.assertEqual(cleaned, 'xpca')

    def test_cleanup_output_text_skips_duplicate_integrity_pass_for_legal_html(self):
        integrity_calls = []

        cleaned = cleanup_output_text(
            '<html></html>',
            fmt='html',
            job_cfg={'doc_profile': 'legal'},
            normalize_html_fn=lambda value: value + '-normalized',
            modernize_punctuation_fn=lambda value: value + '-punct',
            modernize_currency_fn=lambda value: value + '-currency',
            expand_abbreviations_fn=lambda value: value + '-abbr',
            enforce_heading_structure_fn=lambda content, fmt, profile: content + f'-headings-{profile}',
            apply_integrity_contract_fn=lambda content, fmt, profile: integrity_calls.append((content, fmt, profile)) or content + '-integrity',
        )

        self.assertEqual(cleaned, '<html></html>-normalized-headings-legal')
        self.assertEqual(integrity_calls, [])

    def test_finalize_single_output_cleans_and_replaces(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            progress_path = Path(tmpdir) / '.chronicle_progress_out.html.txt.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text('raw')
            progress_path.write_text('progress')
            file_obj = _FakeFile()

            finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=[],
                base='out',
                file_obj=file_obj,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda file_obj, fmt: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content + '-clean',
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
            )

            self.assertTrue(file_obj.closed)
            self.assertEqual(output_path.read_text(), 'raw-clean')
            self.assertFalse(progress_path.exists())

    def test_finalize_single_output_preserves_raw_when_cleanup_shrinks_too_far(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            raw = "<html><body><main>" + ("<p>alpha beta gamma delta</p>" * 1200) + "</main></body></html>"
            temp_path.write_text(raw, encoding="utf-8")

            finalize_single_output(
                job_cfg={'doc_profile': 'legal'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: "<html><body><main><p>tiny</p></main></body></html>",
                log_cb=logs.append,
            )

            self.assertEqual(output_path.read_text(encoding="utf-8"), raw)
            self.assertTrue(any('Finalize Guard' in entry for entry in logs))

    def test_maybe_delete_source_file_respects_protected_paths(self):
        logs = []
        self.assertFalse(
            maybe_delete_source_file(
                '/tmp/a.pdf',
                delete_source_on_success=True,
                is_protected_path_fn=lambda path: True,
                log_cb=logs.append,
            )
        )
        self.assertIn('Protected folder rule', logs[0])


    def test_finalize_job_success_updates_status_and_logs(self):
        logs = []
        statuses = []
        result = finalize_job_success(
            merge_mode=False,
            job_cfg={'doc_profile': 'standard'},
            temp_path='/tmp/out.html.tmp',
            memory=[],
            base='out',
            file_obj=None,
            fmt='html',
            output_path='/tmp/out.html',
            source_path='/tmp/source.pdf',
            file_name='source.pdf',
            ext='.txt',
            current_file_page_total=3,
            memory_telemetry=True,
            delete_source_on_success=False,
            dispatch_save_fn=lambda *args: None,
            write_footer_fn=lambda *args: None,
            cleanup_output_text_fn=lambda *args, **kwargs: '',
            is_protected_path_fn=lambda path: False,
            set_queue_status_fn=statuses.append,
            log_cb=logs.append,
            get_peak_rss_mb_fn=lambda: 12.5,
            progress_temp_path='/tmp/.chronicle_progress_out.html.txt.tmp',
        )

        self.assertEqual(statuses, ['Done'])
        self.assertTrue(result['set_page_done_to_total'])
        self.assertEqual(result['page_total_increment'], 3)
        self.assertIn('Saved: /tmp/out.html', logs)
        self.assertIn('[Memory] Peak RSS after task: 12.5 MB', logs)

    def test_handle_job_error_cleans_temp_file(self):
        actions = []
        file_obj = _FakeFile()
        handle_job_error(
            merge_mode=False,
            file_obj=file_obj,
            temp_path='/tmp/out.html.tmp',
            file_name='broken.pdf',
            error='boom',
            set_queue_status_fn=actions.append,
            log_cb=actions.append,
            progress_temp_path='/tmp/.chronicle_progress_out.html.txt.tmp',
            path_exists=lambda path: True,
            remove_fn=lambda path: actions.append(('remove', path)),
        )

        self.assertTrue(file_obj.closed)
        self.assertEqual(actions[0], 'Error')
        self.assertIn('Error on broken.pdf: boom', actions[1])
        self.assertEqual(actions[2], ('remove', '/tmp/out.html.tmp'))
        self.assertEqual(actions[3], 'Preserved in-progress temp file: /tmp/.chronicle_progress_out.html.txt.tmp')

    def test_finalize_merged_output_streamable_path_cleans_and_replaces(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'merged.html.tmp'
            out_path = Path(tmpdir) / 'merged.html'
            progress_path = Path(tmpdir) / '.chronicle_progress_merged.html.txt.tmp'
            temp_path.write_text('merged')
            progress_path.write_text('header+progress')
            file_obj = _FakeFile()

            finalize_merged_output(
                cfg={'doc_profile': 'standard'},
                merge_fmt='html',
                streamable_fmt=True,
                master_file_obj=file_obj,
                master_temp_path=str(temp_path),
                master_output_path=str(out_path),
                master_memory=None,
                write_footer_fn=lambda file_obj, fmt: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content + '-clean',
                strip_synthetic_headings_fn=lambda content, fmt: content + '-stripped',
                dispatch_save_fn=lambda *args: None,
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
                resume_state_path=str(progress_path),
            )

            self.assertTrue(file_obj.closed)
            self.assertEqual(out_path.read_text(), 'merged-clean-stripped')
            self.assertFalse(progress_path.exists())
            self.assertTrue(any('Saved merged output' in entry for entry in logs))

    def test_should_reject_cleaned_output_flags_large_visible_text_drop(self):
        raw = "<html><body><main>" + ("<p>alpha beta gamma delta</p>" * 1200) + "</main></body></html>"
        cleaned = "<html><body><main><p>tiny</p></main></body></html>"

        reject, stats = should_reject_cleaned_output(raw, cleaned, fmt='html')

        self.assertTrue(reject)
        self.assertGreater(stats['raw_visible_chars'], stats['cleaned_visible_chars'])

    def test_finalize_worker_completion_and_session(self):
        logs = []
        popens = []
        winsound = _FakeWinSound()
        file_obj = _FakeFile()
        actions = []

        finalize_worker_completion(
            auto_save_processing_log_fn=lambda: '/tmp/log.txt',
            log_cb=logs.append,
            platform_system='Windows',
            subprocess_popen=popens.append,
            winsound_module=winsound,
        )
        finalize_worker_session(
            master_file_obj=file_obj,
            has_incomplete_items=False,
            save_active_session_fn=lambda: actions.append('save'),
            delete_active_session_fn=lambda: actions.append('delete'),
            set_running_state_fn=lambda value: actions.append(('running', value)),
        )

        self.assertIn('Auto-saved processing log: /tmp/log.txt', logs)
        self.assertIn(('SystemAsterisk', 3), winsound.calls)
        self.assertTrue(file_obj.closed)
        self.assertEqual(actions, ['delete', ('running', False)])


if __name__ == '__main__':
    unittest.main()
