import unittest
from pathlib import Path

from chronicle_app.services.worker_runtime import (
    BufferedOutputMemory,
    MirroredProgressMemory,
    build_progress_state_header,
    build_output_base_name,
    build_worker_run_plan,
    compute_target_dir,
    determine_needs_pdf_audit,
    estimate_current_file_total_units,
    load_merge_resume_state,
    prepare_job_execution_context,
    read_progress_state,
    read_progress_text,
    recover_completed_output_artifacts,
    resolve_output_path,
)


class WorkerRuntimeTest(unittest.TestCase):
    def test_read_progress_helpers_strip_embedded_header(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = str(Path(tmpdir) / "alpha.html.progress.txt.tmp")
            Path(progress_path).write_text(
                build_progress_state_header({"completed_units": 2, "total_units": 5}) + "<p>body</p>",
                encoding="utf-8",
            )

            self.assertEqual(read_progress_state(progress_path)["completed_units"], 2)
            self.assertEqual(read_progress_text(progress_path), "<p>body</p>")

    def test_read_progress_state_falls_back_to_legacy_sidecar_once(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = str(Path(tmpdir) / "alpha.html.progress.txt.tmp")
            legacy_state = progress_path + ".state.json"
            Path(progress_path).write_text("partial body", encoding="utf-8")
            Path(legacy_state).write_text('{"completed_units": 3, "total_units": 7}', encoding="utf-8")

            self.assertEqual(read_progress_state(progress_path)["completed_units"], 3)

    def test_recover_completed_output_artifacts_promotes_temp_and_cleans_sidecar(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "alpha.html"
            temp_path = Path(tmpdir) / "alpha.html.tmp"
            progress_path = Path(tmpdir) / "alpha.html.progress.txt.tmp"
            temp_path.write_text("<html>done</html>", encoding="utf-8")
            progress_path.write_text(
                build_progress_state_header({"completed_units": 4, "total_units": 4}) + "<html>done</html>",
                encoding="utf-8",
            )
            logs = []

            recovered = recover_completed_output_artifacts(
                output_path=str(output_path),
                temp_path=str(temp_path),
                progress_temp_path=str(progress_path),
                log_cb=logs.append,
            )

            self.assertTrue(recovered)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "<html>done</html>")
            self.assertFalse(temp_path.exists())
            self.assertFalse(progress_path.exists())
            self.assertTrue(any("Materialized completed output" in entry for entry in logs))

    def test_build_worker_run_plan_disables_merge_for_mixed_formats(self):
        jobs = [
            {"status": "Queued", "settings": {"format_type": "html"}},
            {"status": "Queued", "settings": {"format_type": "pdf"}},
        ]

        plan = build_worker_run_plan(
            {"merge_files": True, "format_type": "html"},
            jobs,
            normalize_row_settings_fn=lambda row: row["settings"],
            streamable_formats={"html", "txt", "md"},
        )

        self.assertFalse(plan["merge_mode"])
        self.assertIn("[Merge] Disabled", plan["messages"][0])

    def test_determine_needs_pdf_audit_respects_low_memory_threshold(self):
        enabled, size_mb = determine_needs_pdf_audit(
            ".pdf",
            {"pdf_textlayer_audit": True},
            low_memory_mode=True,
            path="/tmp/a.pdf",
            low_memory_pdf_audit_skip_mb=40,
            getsize=lambda _: 50 * 1024 * 1024,
        )

        self.assertFalse(enabled)
        self.assertGreaterEqual(size_mb, 50)

    def test_compute_target_dir_preserves_relative_structure_when_available(self):
        job = {"path": "/source/sub/file.pdf", "source_root": "/source"}

        target = compute_target_dir(
            job,
            custom_dest="/dest",
            dest_mode=1,
            preserve_source_structure=True,
            isdir=lambda path: path == "/source",
        )

        self.assertEqual(target, "/dest/sub")

    def test_build_output_base_name_appends_pdf_scope_suffix(self):
        result = build_output_base_name(
            "24104b01",
            ".pdf",
            {"pdf_page_scope": "185-220"},
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
        )

        self.assertEqual(result, "24104b01_pages_185-220")


    def test_prepare_job_execution_context_marks_missing_files(self):
        statuses = []
        logs = []
        result = prepare_job_execution_context(
            {'_queue_index': 3, 'path': '/missing/a.pdf', 'engine': 'Model'},
            cfg={},
            resume_mode=False,
            low_memory_mode=False,
            low_memory_pdf_audit_skip_mb=40,
            custom_dest='/out',
            dest_mode=0,
            merge_mode=False,
            master_output_path=None,
            master_temp_path=None,
            master_file_obj=None,
            master_memory=None,
            streamable_formats={'html', 'txt', 'md'},
            supported_extensions={'.pdf'},
            normalize_row_settings_fn=lambda job: {},
            build_prompt_fn=lambda cfg: 'prompt',
            model_from_label_fn=lambda label: 'model',
            get_client_fn=lambda model: object(),
            determine_needs_pdf_audit_fn=determine_needs_pdf_audit,
            compute_target_dir_fn=compute_target_dir,
            resolve_output_path_fn=resolve_output_path,
            write_header_fn=lambda *args: None,
            get_output_lang_code_fn=lambda cfg: 'en',
            get_output_text_direction_fn=lambda cfg: 'ltr',
            pdf_reader_factory=None,
            normalize_pdf_page_scope_text_fn=None,
            parse_pdf_page_scope_spec_fn=None,
            set_queue_status_fn=lambda idx, status: statuses.append((idx, status)),
            log_cb=logs.append,
            path_exists_fn=lambda path: False,
        )
        self.assertTrue(result['skip'])
        self.assertEqual(statuses, [(3, 'Missing')])
        self.assertIn('Missing file: /missing/a.pdf', logs[0])

    def test_prepare_job_execution_context_builds_non_merge_streamable_output(self):
        headers = []
        makedirs_calls = []
        removed = []

        class DummyFile:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True

        result = prepare_job_execution_context(
            {'_queue_index': 1, 'path': '/source/a.pdf', 'engine': 'Fast', 'settings': {'format_type': 'html'}},
            cfg={'collision_mode': None, 'preserve_source_structure': True},
            resume_mode=False,
            low_memory_mode=False,
            low_memory_pdf_audit_skip_mb=40,
            custom_dest='/out',
            dest_mode=1,
            merge_mode=False,
            master_output_path=None,
            master_temp_path=None,
            master_file_obj=None,
            master_memory=None,
            streamable_formats={'html', 'txt', 'md'},
            supported_extensions={'.pdf'},
            normalize_row_settings_fn=lambda job: job.get('settings', {}),
            build_prompt_fn=lambda cfg: 'prompt',
            model_from_label_fn=lambda label: f'model:{label}',
            get_client_fn=lambda model: f'client:{model}',
            determine_needs_pdf_audit_fn=lambda *args, **kwargs: (True, 0.0),
            compute_target_dir_fn=lambda *args, **kwargs: '/out/sub',
            resolve_output_path_fn=lambda base, *args, **kwargs: {'output_path': f'/out/sub/{base}.html', 'should_skip': False},
            write_header_fn=lambda *args: headers.append(args[1:]),
            get_output_lang_code_fn=lambda cfg: 'en',
            get_output_text_direction_fn=lambda cfg: 'ltr',
            pdf_reader_factory=None,
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
            parse_pdf_page_scope_spec_fn=None,
            set_queue_status_fn=lambda idx, status: None,
            log_cb=lambda msg: None,
            makedirs_fn=lambda path, exist_ok=False: makedirs_calls.append((path, exist_ok)),
            path_exists_fn=lambda path: path in {'/source/a.pdf', '/out/sub/a.html.tmp'},
            remove_fn=lambda path: removed.append(path),
            open_fn=lambda *args, **kwargs: DummyFile(),
        )
        self.assertFalse(result['skip'])
        self.assertEqual(result['fmt'], 'html')
        self.assertEqual(result['model'], 'model:Fast')
        self.assertEqual(result['client'], 'client:model:Fast')
        self.assertEqual(result['output_path'], '/out/sub/a.html')
        self.assertEqual(result['temp_path'], '/out/sub/a.html.tmp')
        self.assertEqual(result['progress_temp_path'], '/out/sub/a.html.progress.txt.tmp')
        self.assertIsInstance(result['memory'], BufferedOutputMemory)
        self.assertEqual(result['memory'].clear_every_pages, 2)
        self.assertEqual(result['memory'].progress_temp_path, '/out/sub/a.html.progress.txt.tmp')
        self.assertEqual(makedirs_calls, [('/out/sub', True)])
        self.assertEqual(removed, ['/out/sub/a.html.tmp'])
        self.assertEqual(headers[0], ('a', 'html', 'en', 'ltr'))

    def test_prepare_job_execution_context_uses_pdf_scope_suffix_in_output_name(self):
        result = prepare_job_execution_context(
            {'_queue_index': 1, 'path': '/source/a.pdf', 'engine': 'Fast', 'settings': {'format_type': 'html', 'pdf_page_scope': '185-220'}},
            cfg={'collision_mode': None, 'preserve_source_structure': True},
            resume_mode=False,
            low_memory_mode=False,
            low_memory_pdf_audit_skip_mb=40,
            custom_dest='/out',
            dest_mode=1,
            merge_mode=False,
            master_output_path=None,
            master_temp_path=None,
            master_file_obj=None,
            master_memory=None,
            streamable_formats={'html', 'txt', 'md'},
            supported_extensions={'.pdf'},
            normalize_row_settings_fn=lambda job: job.get('settings', {}),
            build_prompt_fn=lambda cfg: 'prompt',
            model_from_label_fn=lambda label: f'model:{label}',
            get_client_fn=lambda model: f'client:{model}',
            determine_needs_pdf_audit_fn=lambda *args, **kwargs: (True, 0.0),
            compute_target_dir_fn=lambda *args, **kwargs: '/out/sub',
            resolve_output_path_fn=lambda base, *args, **kwargs: {'output_path': f'/out/sub/{base}.html', 'should_skip': False},
            write_header_fn=lambda *args: None,
            get_output_lang_code_fn=lambda cfg: 'en',
            get_output_text_direction_fn=lambda cfg: 'ltr',
            pdf_reader_factory=None,
            normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
            parse_pdf_page_scope_spec_fn=None,
            set_queue_status_fn=lambda idx, status: None,
            log_cb=lambda msg: None,
            makedirs_fn=lambda path, exist_ok=False: None,
            path_exists_fn=lambda path: path == '/source/a.pdf',
            remove_fn=lambda path: None,
            open_fn=lambda *args, **kwargs: None,
        )

        self.assertEqual(result['output_path'], '/out/sub/a_pages_185-220.html')

    def test_prepare_job_execution_context_uses_plain_memory_for_non_streamable_formats(self):
        result = prepare_job_execution_context(
            {'_queue_index': 1, 'path': '/source/a.pdf', 'engine': 'Fast', 'settings': {'format_type': 'docx'}},
            cfg={'collision_mode': None, 'preserve_source_structure': True},
            resume_mode=False,
            low_memory_mode=False,
            low_memory_pdf_audit_skip_mb=40,
            custom_dest='/out',
            dest_mode=1,
            merge_mode=False,
            master_output_path=None,
            master_temp_path=None,
            master_file_obj=None,
            master_memory=None,
            streamable_formats={'html', 'txt', 'md'},
            supported_extensions={'.pdf'},
            normalize_row_settings_fn=lambda job: job.get('settings', {}),
            build_prompt_fn=lambda cfg: 'prompt',
            model_from_label_fn=lambda label: f'model:{label}',
            get_client_fn=lambda model: f'client:{model}',
            determine_needs_pdf_audit_fn=lambda *args, **kwargs: (True, 0.0),
            compute_target_dir_fn=lambda *args, **kwargs: '/out/sub',
            resolve_output_path_fn=lambda *args, **kwargs: {'output_path': '/out/sub/a.docx', 'should_skip': False},
            write_header_fn=lambda *args: None,
            get_output_lang_code_fn=lambda cfg: 'en',
            get_output_text_direction_fn=lambda cfg: 'ltr',
            pdf_reader_factory=None,
            normalize_pdf_page_scope_text_fn=None,
            parse_pdf_page_scope_spec_fn=None,
            set_queue_status_fn=lambda idx, status: None,
            log_cb=lambda msg: None,
            makedirs_fn=lambda path, exist_ok=False: None,
            path_exists_fn=lambda path: path == '/source/a.pdf',
            remove_fn=lambda path: None,
            open_fn=lambda *args, **kwargs: None,
        )

        self.assertIsInstance(result['memory'], MirroredProgressMemory)
        self.assertEqual(result['progress_temp_path'], '/out/sub/a.docx.progress.txt.tmp')

    def test_mirrored_progress_memory_reads_written_text_since_checkpoint(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/progress.txt"
            progress_file = open(path, "w", encoding="utf-8")
            memory = MirroredProgressMemory(
                progress_file_obj=progress_file,
                progress_temp_path=path,
                retain_chunks=False,
            )
            checkpoint = memory.checkpoint()
            memory.append("alpha")
            memory.append("beta")
            progress_file.close()

            self.assertEqual(memory.read_text_since(checkpoint), "alphabeta")

    def test_buffered_output_memory_reads_full_text_from_progress_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/progress.txt"
            progress_file = open(path, "w", encoding="utf-8")
            memory = BufferedOutputMemory(
                file_obj=progress_file,
                clear_every_pages=2,
                progress_temp_path=path,
            )
            progress_file.write("alpha")
            memory.append("alpha")
            memory.mark_page_processed()
            progress_file.write("beta")
            memory.append("beta")
            memory.mark_page_processed()
            progress_file.write("gamma")
            memory.append("gamma")
            progress_file.flush()
            progress_file.close()

            self.assertEqual(memory.read_all_text(), "alphabetagamma")

    def test_prepare_job_execution_context_logs_explicit_collision_skip_reason(self):
        statuses = []
        logs = []

        result = prepare_job_execution_context(
            {'_queue_index': 2, 'path': '/source/alpha.pdf', 'engine': 'Fast', 'settings': {'format_type': 'html'}},
            cfg={'collision_mode': 'skip', 'preserve_source_structure': True},
            resume_mode=False,
            low_memory_mode=False,
            low_memory_pdf_audit_skip_mb=40,
            custom_dest='/out',
            dest_mode=1,
            merge_mode=False,
            master_output_path=None,
            master_temp_path=None,
            master_file_obj=None,
            master_memory=None,
            streamable_formats={'html', 'txt', 'md'},
            supported_extensions={'.pdf'},
            normalize_row_settings_fn=lambda job: job.get('settings', {}),
            build_prompt_fn=lambda cfg: 'prompt',
            model_from_label_fn=lambda label: f'model:{label}',
            get_client_fn=lambda model: f'client:{model}',
            determine_needs_pdf_audit_fn=lambda *args, **kwargs: (False, 0.0),
            compute_target_dir_fn=lambda *args, **kwargs: '/out/sub',
            resolve_output_path_fn=lambda *args, **kwargs: {'output_path': '/out/sub/alpha.html', 'should_skip': True},
            write_header_fn=lambda *args: None,
            get_output_lang_code_fn=lambda cfg: 'en',
            get_output_text_direction_fn=lambda cfg: 'ltr',
            pdf_reader_factory=None,
            normalize_pdf_page_scope_text_fn=None,
            parse_pdf_page_scope_spec_fn=None,
            set_queue_status_fn=lambda idx, status: statuses.append((idx, status)),
            log_cb=logs.append,
            makedirs_fn=lambda path, exist_ok=False: None,
            path_exists_fn=lambda path: True,
            remove_fn=lambda path: None,
            open_fn=lambda *args, **kwargs: None,
        )

        self.assertTrue(result['skip'])
        self.assertEqual(statuses, [(2, 'Skipped')])
        self.assertEqual(
            logs[0],
            'Skipped alpha.pdf: output already exists at /out/sub/alpha.html and File Collisions is set to Skip.',
        )

    def test_prepare_job_execution_context_preserves_progress_files_and_narrows_pdf_scope_on_resume(self):
        with self.subTest("resume"):
            statuses = []
            logs = []

            class Reader:
                def __init__(self, _path):
                    self.pages = [object()] * 6

            def fake_open(path, mode="r", encoding=None, errors=None):
                return open(path, mode, encoding=encoding, errors=errors)

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                progress_path = str(Path(tmpdir) / "a.docx.progress.txt.tmp")
                Path(progress_path).write_text(
                    build_progress_state_header({"completed_pages": 2, "total_pages": 6, "current_source_page": 2}) + "partial",
                    encoding="utf-8",
                )
                removed = []

                result = prepare_job_execution_context(
                    {'_queue_index': 1, 'path': '/source/a.pdf', 'engine': 'Fast', 'settings': {'format_type': 'docx'}},
                    cfg={'collision_mode': None, 'preserve_source_structure': True},
                    resume_mode=True,
                    low_memory_mode=False,
                    low_memory_pdf_audit_skip_mb=40,
                    custom_dest='/out',
                    dest_mode=1,
                    merge_mode=False,
                    master_output_path=None,
                    master_temp_path=None,
                    master_file_obj=None,
                    master_memory=None,
                    streamable_formats={'html', 'txt', 'md'},
                    supported_extensions={'.pdf'},
                    normalize_row_settings_fn=lambda job: job.get('settings', {}),
                    build_prompt_fn=lambda cfg: cfg.get('pdf_page_scope', ''),
                    model_from_label_fn=lambda label: f'model:{label}',
                    get_client_fn=lambda model: f'client:{model}',
                    determine_needs_pdf_audit_fn=lambda *args, **kwargs: (True, 0.0),
                    compute_target_dir_fn=lambda *args, **kwargs: tmpdir,
                    resolve_output_path_fn=lambda *args, **kwargs: {'output_path': str(Path(tmpdir) / 'a.docx'), 'should_skip': False},
                    write_header_fn=lambda *args: None,
                    get_output_lang_code_fn=lambda cfg: 'en',
                    get_output_text_direction_fn=lambda cfg: 'ltr',
                    pdf_reader_factory=Reader,
                    normalize_pdf_page_scope_text_fn=lambda value: value,
                    parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)) if not scope else [int(x) - 1 for x in scope.split(',')],
                    set_queue_status_fn=lambda idx, status: statuses.append((idx, status)),
                    log_cb=logs.append,
                    makedirs_fn=lambda path, exist_ok=False: None,
                    path_exists_fn=lambda path: path in {"/source/a.pdf", str(Path(tmpdir) / 'a.docx.progress.txt.tmp')},
                    remove_fn=lambda path: removed.append(path),
                    open_fn=fake_open,
                )

                self.assertFalse(result['skip'])
                self.assertEqual(result['job_cfg']['pdf_page_scope'], '3-6')
                self.assertEqual(result['recovered_units'], 2)
                self.assertEqual(result['original_total_units'], 6)
                self.assertEqual(removed, [])
                self.assertTrue(any('Recovered 2 of 6 pages' in entry for entry in logs))
                result['progress_file_obj'].close()

    def test_prepare_job_execution_context_resumes_text_units_without_deleting_progress(self):
        statuses = []
        logs = []

        def fake_open(path, mode="r", encoding=None, errors=None):
            return open(path, mode, encoding=encoding, errors=errors)

        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = str(Path(tmpdir) / "a.html.progress.txt.tmp")
            temp_path = str(Path(tmpdir) / "a.html.tmp")
            Path(progress_path).write_text(
                build_progress_state_header({"completed_units": 3, "total_units": 7}) + "partial progress",
                encoding="utf-8",
            )
            Path(temp_path).write_text("partial temp", encoding="utf-8")
            removed = []

            result = prepare_job_execution_context(
                {'_queue_index': 1, 'path': '/source/a.docx', 'engine': 'Fast', 'settings': {'format_type': 'html'}},
                cfg={'collision_mode': None, 'preserve_source_structure': True},
                resume_mode=True,
                low_memory_mode=False,
                low_memory_pdf_audit_skip_mb=40,
                custom_dest='/out',
                dest_mode=1,
                merge_mode=False,
                master_output_path=None,
                master_temp_path=None,
                master_file_obj=None,
                master_memory=None,
                streamable_formats={'html', 'txt', 'md'},
                supported_extensions={'.docx'},
                normalize_row_settings_fn=lambda job: job.get('settings', {}),
                build_prompt_fn=lambda cfg: 'prompt',
                model_from_label_fn=lambda label: f'model:{label}',
                get_client_fn=lambda model: f'client:{model}',
                determine_needs_pdf_audit_fn=lambda *args, **kwargs: (False, 0.0),
                compute_target_dir_fn=lambda *args, **kwargs: tmpdir,
                resolve_output_path_fn=lambda *args, **kwargs: {'output_path': str(Path(tmpdir) / 'a.html'), 'should_skip': False},
                write_header_fn=lambda *args: None,
                get_output_lang_code_fn=lambda cfg: 'en',
                get_output_text_direction_fn=lambda cfg: 'ltr',
                pdf_reader_factory=None,
                normalize_pdf_page_scope_text_fn=None,
                parse_pdf_page_scope_spec_fn=None,
                set_queue_status_fn=lambda idx, status: statuses.append((idx, status)),
                log_cb=logs.append,
                makedirs_fn=lambda path, exist_ok=False: None,
                path_exists_fn=lambda path: path in {"/source/a.docx", progress_path, temp_path},
                remove_fn=lambda path: removed.append(path),
                open_fn=fake_open,
            )

            self.assertFalse(result['skip'])
            self.assertEqual(result['resume_from_unit'], 3)
            self.assertEqual(result['recovered_units'], 3)
            self.assertEqual(result['original_total_units'], 7)
            self.assertEqual(removed, [])
            self.assertTrue(any('Recovered 3 of 7 units' in entry for entry in logs))
            result['file_obj'].close()

    def test_load_merge_resume_state_returns_completed_jobs_when_sidecar_exists(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = str(Path(tmpdir) / "merged.docx.progress.txt.tmp")
            Path(progress_path).write_text(
                build_progress_state_header(
                    {"completed_job_paths": ["/tmp/a.pdf", "/tmp/b.pdf", "/tmp/a.pdf"], "total_units": 4}
                ) + "partial merged output",
                encoding="utf-8",
            )

            result = load_merge_resume_state(
                progress_temp_path=progress_path,
                expected_total_units=4,
                path_exists_fn=lambda path: path in {progress_path},
                open_fn=open,
            )

            self.assertEqual(result["recovered_units"], 2)
            self.assertEqual(result["original_total_units"], 4)
            self.assertEqual(result["completed_job_paths"], ["/tmp/a.pdf", "/tmp/b.pdf"])

    def test_prepare_job_execution_context_recovers_completed_pdf_output_from_temp(self):
        import tempfile

        statuses = []
        logs = []

        class Reader:
            def __init__(self, _path):
                self.pages = [object(), object(), object()]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "a.html"
            temp_path = Path(tmpdir) / "a.html.tmp"
            progress_path = Path(tmpdir) / "a.html.progress.txt.tmp"
            temp_path.write_text("<html>rescued</html>", encoding="utf-8")
            progress_path.write_text(
                build_progress_state_header(
                    {
                        "completed_units": 3,
                        "total_units": 3,
                        "completed_pages": 3,
                        "total_pages": 3,
                    }
                ) + "<html>rescued</html>",
                encoding="utf-8",
            )

            result = prepare_job_execution_context(
                {'_queue_index': 1, 'path': '/source/a.pdf', 'engine': 'Fast', 'settings': {'format_type': 'html'}},
                cfg={'collision_mode': None, 'preserve_source_structure': True},
                resume_mode=True,
                low_memory_mode=False,
                low_memory_pdf_audit_skip_mb=40,
                custom_dest=tmpdir,
                dest_mode=1,
                merge_mode=False,
                master_output_path=None,
                master_temp_path=None,
                master_file_obj=None,
                master_memory=None,
                streamable_formats={'html', 'txt', 'md'},
                supported_extensions={'.pdf'},
                normalize_row_settings_fn=lambda job: job.get('settings', {}),
                build_prompt_fn=lambda cfg: 'prompt',
                model_from_label_fn=lambda label: f'model:{label}',
                get_client_fn=lambda model: f'client:{model}',
                determine_needs_pdf_audit_fn=lambda *args, **kwargs: (True, 0.0),
                compute_target_dir_fn=lambda *args, **kwargs: tmpdir,
                resolve_output_path_fn=lambda *args, **kwargs: {'output_path': str(output_path), 'should_skip': False},
                write_header_fn=lambda *args: None,
                get_output_lang_code_fn=lambda cfg: 'en',
                get_output_text_direction_fn=lambda cfg: 'ltr',
                pdf_reader_factory=Reader,
                normalize_pdf_page_scope_text_fn=lambda scope: str(scope).strip(),
                parse_pdf_page_scope_spec_fn=lambda scope, total: [0, 1, 2],
                set_queue_status_fn=lambda idx, status: statuses.append((idx, status)),
                log_cb=logs.append,
                makedirs_fn=lambda path, exist_ok=False: None,
                path_exists_fn=lambda path: path in {"/source/a.pdf", str(temp_path), str(progress_path)},
                remove_fn=lambda path: Path(path).unlink(),
                replace_fn=lambda src, dst: Path(src).replace(dst),
                open_fn=open,
            )

            self.assertTrue(result['skip'])
            self.assertEqual(statuses, [(1, 'Done')])
            self.assertEqual(output_path.read_text(encoding="utf-8"), "<html>rescued</html>")
            self.assertFalse(temp_path.exists())
            self.assertFalse(progress_path.exists())
            self.assertTrue(any("Recovered completed PDF task" in entry for entry in logs))

    def test_resolve_output_path_handles_skip_and_auto_collision_modes(self):
        skipped = resolve_output_path(
            "alpha",
            "html",
            "/out",
            collision_mode="skip",
            path_exists=lambda _: True,
        )
        auto = resolve_output_path(
            "alpha",
            "html",
            "/out",
            collision_mode="auto",
            path_exists=lambda _: True,
            now=123,
        )

        self.assertTrue(skipped["should_skip"])
        self.assertEqual(auto["output_path"], "/out/alpha_123.html")

    def test_estimate_current_file_total_units_reports_pdf_scope_and_pptx_slides(self):
        class Reader:
            def __init__(self, _path):
                self.pages = [object(), object(), object()]

        pdf = estimate_current_file_total_units(
            ".pdf",
            "/tmp/a.pdf",
            {"pdf_page_scope": "1,3"},
            pdf_reader_factory=Reader,
            normalize_pdf_page_scope_text_fn=lambda value: value,
            parse_pdf_page_scope_spec_fn=lambda scope, total: [0, 2],
            pptx_slide_count_fn=lambda _: 7,
            estimate_text_work_units_fn=lambda *args: 4,
        )
        pptx = estimate_current_file_total_units(
            ".pptx",
            "/tmp/a.pptx",
            {},
            pdf_reader_factory=Reader,
            normalize_pdf_page_scope_text_fn=lambda value: value,
            parse_pdf_page_scope_spec_fn=lambda scope, total: [0, 2],
            pptx_slide_count_fn=lambda _: 7,
            estimate_text_work_units_fn=lambda *args: 4,
        )
        docx = estimate_current_file_total_units(
            ".docx",
            "/tmp/a.docx",
            {},
            pdf_reader_factory=Reader,
            normalize_pdf_page_scope_text_fn=lambda value: value,
            parse_pdf_page_scope_spec_fn=lambda scope, total: [0, 2],
            pptx_slide_count_fn=lambda _: 7,
            estimate_text_work_units_fn=lambda *args: 6,
        )

        self.assertEqual(pdf["total_units"], 2)
        self.assertEqual(pdf["selected_scope"], "1,3")
        self.assertEqual(pdf["source_total"], 3)
        self.assertEqual(pdf["unit_label"], "page(s)")
        self.assertEqual(pptx["total_units"], 4)
        self.assertEqual(pptx["unit_label"], "chunk(s)")
        self.assertEqual(docx["total_units"], 6)
        self.assertEqual(docx["unit_label"], "chunk(s)")


if __name__ == "__main__":
    unittest.main()
