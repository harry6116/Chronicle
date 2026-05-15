import tempfile
import time
import unittest
from pathlib import Path

from chronicle_app.services.worker_finalize_runtime import (
    _promote_temp_output,
    append_pdf_audit_appendix_if_needed,
    cleanup_output_text,
    finalize_job_success,
    finalize_merged_output,
    finalize_single_output,
    finalize_worker_completion,
    finalize_worker_session,
    handle_job_error,
    maybe_delete_source_file,
    should_skip_cleanup_for_ocr_backed_nla_newspaper,
    should_skip_redundant_large_profile_cleanup,
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

    def test_cleanup_output_text_passes_profile_to_abbreviation_expander(self):
        calls = []

        cleaned = cleanup_output_text(
            'AP',
            fmt='txt',
            job_cfg={'doc_profile': 'newspaper', 'abbrev_expansion': True},
            normalize_html_fn=lambda value: value,
            modernize_punctuation_fn=lambda value: value,
            modernize_currency_fn=lambda value: value,
            expand_abbreviations_fn=lambda value, profile=None: calls.append(profile) or f'{value}:{profile}',
            enforce_heading_structure_fn=lambda content, fmt, profile: content,
        )

        self.assertEqual(cleaned, 'AP:newspaper')
        self.assertEqual(calls, ['newspaper'])

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
            progress_path = Path(tmpdir) / 'out.html.progress.txt.tmp'
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
            self.assertEqual(output_path.read_text(), 'raw')
            self.assertFalse(progress_path.exists())
            self.assertTrue(any('[Finalize] out.html: begin finalization.' == entry for entry in logs))
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))
            self.assertTrue(any('[Finalize] out.html: finalization complete.' == entry for entry in logs))

    def test_finalize_single_output_bypasses_output_quality_until_after_save(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text("<html><body><h2></h2><p>Text</p></body></html>")

            finalize_single_output(
                job_cfg={'doc_profile': 'magazine'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
            )

            self.assertEqual(output_path.read_text(encoding="utf-8"), "<html><body><h2></h2><p>Text</p></body></html>")
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))

    def test_finalize_single_output_logs_finalize_stages(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            progress_path = Path(tmpdir) / 'out.html.progress.txt.tmp'
            temp_path.write_text("<html><body><p>Text</p></body></html>")
            progress_path.write_text('progress')

            finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
            )

            self.assertTrue(any('promoting temp output into place' in entry for entry in logs))
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))
            self.assertTrue(any('removing progress file' in entry for entry in logs))
            self.assertTrue(any('finalization complete' in entry for entry in logs))

    def test_finalize_single_output_skips_redundant_cleanup_for_nla_ocr_newspaper(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'nla.news-issue108507.html.tmp'
            output_path = Path(tmpdir) / 'nla.news-issue108507.html'
            raw = (
                "<html><body><main>"
                "<p>National Library of Australia</p>"
                "<p>http://nla.gov.au/nla.news-page971274</p>"
                + ("<p>OCR backed newspaper line.</p>" * 6000)
                + "</main></body></html>"
            )
            temp_path.write_text(raw, encoding="utf-8")

            finalize_single_output(
                job_cfg={'doc_profile': 'newspaper'},
                temp_path=str(temp_path),
                memory=None,
                base='nla.news-issue108507',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda *args, **kwargs: self.fail("NLA OCR output should not run final cleanup"),
                log_cb=logs.append,
            )

            self.assertEqual(output_path.read_text(encoding="utf-8"), raw)
            self.assertTrue(any("final cleanup is bypassed for save reliability" in entry for entry in logs))

    def test_finalize_single_output_skips_large_military_html_cleanup(self):
        logs = []
        cleanup_calls = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'war-diary.html.tmp'
            output_path = Path(tmpdir) / 'war-diary.html'
            raw = (
                "<!DOCTYPE html><html><body><main>"
                + ("<p>Unit war diary movement table and nominal roll.</p>" * 9000)
                + "</main></body></html>"
            )
            self.assertTrue(should_skip_redundant_large_profile_cleanup(
                raw,
                fmt="html",
                job_cfg={"doc_profile": "military"},
            ))
            self.assertTrue(should_skip_redundant_large_profile_cleanup(
                raw.removesuffix("</main></body></html>"),
                fmt="html",
                job_cfg={"doc_profile": "military"},
            ))
            temp_path.write_text(raw, encoding="utf-8")

            finalize_single_output(
                job_cfg={'doc_profile': 'military'},
                temp_path=str(temp_path),
                memory=None,
                base='war-diary',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: cleanup_calls.append(content) or content + '-clean',
                log_cb=logs.append,
            )

            self.assertEqual(cleanup_calls, [])
            self.assertEqual(output_path.read_text(encoding="utf-8"), raw)
            self.assertTrue(any("final cleanup is bypassed for save reliability" in entry for entry in logs))

    def test_nla_ocr_cleanup_skip_requires_newspaper_profile(self):
        raw = (
            "<p>National Library of Australia</p>"
            "<p>http://nla.gov.au/nla.news-page971274</p>"
            + ("<p>OCR line.</p>" * 9000)
        )

        self.assertTrue(should_skip_cleanup_for_ocr_backed_nla_newspaper(
            raw,
            fmt="html",
            job_cfg={"doc_profile": "newspaper"},
        ))
        self.assertFalse(should_skip_cleanup_for_ocr_backed_nla_newspaper(
            raw,
            fmt="html",
            job_cfg={"doc_profile": "legal"},
        ))

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
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))

    def test_finalize_single_output_saves_fallback_when_replace_fails(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text('<html>done</html>', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                replace_fn=lambda src, dst: (_ for _ in ()).throw(PermissionError('locked')),
            )

            fallback_path = Path(saved_path)
            self.assertNotEqual(fallback_path, output_path)
            self.assertTrue(fallback_path.name.startswith('out_finalized_'))
            self.assertEqual(fallback_path.read_text(encoding='utf-8'), '<html>done</html>')
            self.assertFalse(temp_path.exists())
            self.assertTrue(any('saved completed output as' in entry for entry in logs))
            self.assertTrue(any('finalization complete' in entry for entry in logs))

    def test_finalize_single_output_writes_emergency_text_when_format_dispatch_fails(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.docx.tmp'
            output_path = Path(tmpdir) / 'out.docx'
            progress_path = Path(tmpdir) / 'out.docx.progress.txt.tmp'
            progress_path.write_text('progress', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=['completed extraction text'],
                base='out',
                file_obj=None,
                fmt='docx',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: (_ for _ in ()).throw(RuntimeError('docx writer failed')),
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
            )

            fallback_path = Path(saved_path)
            self.assertEqual(fallback_path.name, 'out.recovered.txt')
            self.assertEqual(fallback_path.read_text(encoding='utf-8'), 'completed extraction text')
            self.assertFalse(progress_path.exists())
            self.assertTrue(any('emergency text fallback saved' in entry for entry in logs))
            self.assertTrue(any('finalization complete' in entry for entry in logs))

    def test_promote_temp_output_saves_fallback_when_replace_hangs(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text('<html>done</html>', encoding='utf-8')

            saved_path = _promote_temp_output(
                str(temp_path),
                str(output_path),
                label='out.html',
                log_cb=logs.append,
                path_exists=lambda path: Path(path).exists(),
                replace_fn=lambda src, dst: time.sleep(0.2),
                remove_fn=lambda path: Path(path).unlink(),
                sleep_fn=lambda _seconds: None,
                operation_timeout_s=0.01,
            )

            fallback_path = Path(saved_path)
            self.assertNotEqual(fallback_path, output_path)
            self.assertTrue(fallback_path.name.startswith('out_finalized_'))
            self.assertEqual(fallback_path.read_text(encoding='utf-8'), '<html>done</html>')
            self.assertFalse(temp_path.exists())
            self.assertTrue(any('did not finish within' in entry for entry in logs))
            self.assertTrue(any('saved completed output as' in entry for entry in logs))

    def test_finalize_single_output_keeps_completion_when_sidecar_remove_fails(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            progress_path = Path(tmpdir) / 'out.html.progress.txt.tmp'
            temp_path.write_text('<html>done</html>', encoding='utf-8')
            progress_path.write_text('progress', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
                remove_fn=lambda path: (_ for _ in ()).throw(PermissionError('busy')),
            )

            self.assertEqual(saved_path, str(output_path))
            self.assertEqual(output_path.read_text(encoding='utf-8'), '<html>done</html>')
            self.assertTrue(progress_path.exists())
            self.assertTrue(any('warning: could not remove progress file' in entry for entry in logs))

    def test_finalize_single_output_keeps_completion_when_sidecar_remove_hangs(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            progress_path = Path(tmpdir) / 'out.html.progress.txt.tmp'
            temp_path.write_text('<html>done</html>', encoding='utf-8')
            progress_path.write_text('progress', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                progress_temp_path=str(progress_path),
                remove_fn=lambda path: time.sleep(0.2),
                operation_timeout_s=0.01,
            )

            self.assertEqual(saved_path, str(output_path))
            self.assertEqual(output_path.read_text(encoding='utf-8'), '<html>done</html>')
            self.assertTrue(progress_path.exists())
            self.assertTrue(any('warning: could not remove progress file' in entry for entry in logs))
            self.assertTrue(any('did not finish within' in entry for entry in logs))

    def test_finalize_single_output_promotes_raw_when_cleanup_hangs(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text('<html>raw complete body</html>', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=None,
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: time.sleep(0.2) or content + '-clean',
                log_cb=logs.append,
                operation_timeout_s=0.01,
                cleanup_timeout_s=0.01,
            )

            self.assertEqual(saved_path, str(output_path))
            self.assertEqual(output_path.read_text(encoding='utf-8'), '<html>raw complete body</html>')
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))
            self.assertTrue(any('promoting temp output into place' in entry for entry in logs))

    def test_finalize_single_output_promotes_when_stream_close_hangs(self):
        logs = []

        class SlowCloseFile:
            closed = False

            def close(self):
                time.sleep(0.2)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'out.html.tmp'
            output_path = Path(tmpdir) / 'out.html'
            temp_path.write_text('<html>flushed body</html>', encoding='utf-8')

            saved_path = finalize_single_output(
                job_cfg={'doc_profile': 'standard'},
                temp_path=str(temp_path),
                memory=None,
                base='out',
                file_obj=SlowCloseFile(),
                fmt='html',
                output_path=str(output_path),
                dispatch_save_fn=lambda *args: None,
                write_footer_fn=lambda *args: None,
                cleanup_output_text_fn=lambda content, fmt, job_cfg: content,
                log_cb=logs.append,
                operation_timeout_s=0.01,
            )

            self.assertEqual(saved_path, str(output_path))
            self.assertEqual(output_path.read_text(encoding='utf-8'), '<html>flushed body</html>')
            self.assertTrue(any('could not close output stream' in entry for entry in logs))
            self.assertTrue(any('finalization complete' in entry for entry in logs))

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
            progress_temp_path='/tmp/out.html.progress.txt.tmp',
        )

        self.assertEqual(statuses, ['Done'])
        self.assertTrue(result['set_page_done_to_total'])
        self.assertEqual(result['page_total_increment'], 3)
        self.assertIn('Saved: /tmp/out.html', logs)
        self.assertTrue(any(entry.startswith('[Health]') for entry in logs))
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
            progress_temp_path='/tmp/out.html.progress.txt.tmp',
            path_exists=lambda path: True,
            remove_fn=lambda path: actions.append(('remove', path)),
        )

        self.assertTrue(file_obj.closed)
        self.assertEqual(actions[0], 'Error')
        self.assertIn('Error on broken.pdf: boom', actions[1])
        self.assertEqual(actions[2], ('remove', '/tmp/out.html.tmp'))
        self.assertEqual(actions[3], 'Preserved in-progress temp file: /tmp/out.html.progress.txt.tmp')

    def test_finalize_merged_output_streamable_path_cleans_and_replaces(self):
        logs = []
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / 'merged.html.tmp'
            out_path = Path(tmpdir) / 'merged.html'
            progress_path = Path(tmpdir) / 'merged.html.progress.txt.tmp'
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
            self.assertEqual(out_path.read_text(), 'merged')
            self.assertFalse(progress_path.exists())
            self.assertTrue(any('final cleanup is bypassed for save reliability' in entry for entry in logs))
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
        self.assertTrue(any('auto-save processing log step' in entry for entry in logs))
        self.assertTrue(any('triggering Windows completion sound' in entry for entry in logs))
        self.assertIn(('SystemAsterisk', 3), winsound.calls)
        self.assertTrue(file_obj.closed)
        self.assertEqual(actions, ['delete', ('running', False)])

    def test_finalize_worker_completion_skips_sound_for_incomplete_run(self):
        logs = []
        popens = []
        winsound = _FakeWinSound()

        finalize_worker_completion(
            auto_save_processing_log_fn=lambda: '/tmp/log.txt',
            log_cb=logs.append,
            platform_system='Darwin',
            subprocess_popen=popens.append,
            winsound_module=winsound,
            all_items_completed=False,
        )

        self.assertIn('Auto-saved processing log: /tmp/log.txt', logs)
        self.assertIn('--- RUN ENDED WITH ATTENTION NEEDED ---', logs)
        self.assertTrue(any('completion sound skipped' in entry for entry in logs))
        self.assertNotIn('--- COMPLETE ---', logs)
        self.assertEqual(popens, [])
        self.assertEqual(winsound.calls, [])


if __name__ == '__main__':
    unittest.main()
