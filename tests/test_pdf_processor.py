import os
import tempfile
import unittest
import io

from chronicle_app.services.pdf_processor import process_pdf
from chronicle_app.services.runtime_policies import DEFAULT_CLAUDE_MODEL


class PdfProcessorTest(unittest.TestCase):
    def test_process_pdf_uses_text_fast_path_for_text_backed_legal_pages(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "Aged Care Bill 2024",
                                "Chapter 1 Introduction",
                                "Part 1 Preliminary",
                                "1 Short title",
                                "This Act may be cited as the Aged Care Act 2024.",
                                "2 Commencement",
                                "This Act commences on a day fixed by Proclamation.",
                                "3 Objects",
                                "The objects of this Act are to improve aged care outcomes.",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        cache_calls = []
        progress = []
        emitted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=emitted,
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                page_scope="",
                doc_profile="legal",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 2,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Text fast path should avoid PDF payload building"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: cache_calls.append((key, request_fn())),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("[PDF Fast Path]" in line for line in logs))
        self.assertEqual(cache_calls, [])
        self.assertNotIn("Aged Care Bill 2024", emitted[0])
        self.assertIn("<h3>1 Short title</h3>", emitted[0])
        self.assertIn("<p>This Act may be cited as the Aged Care Act 2024.</p>", emitted[0])
        self.assertEqual(progress[-1], (1, 1, 1))

    def test_process_pdf_keeps_text_backed_legal_contents_page_on_fast_path(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "Contents",
                                "Chapter 1 Introduction",
                                "1",
                                "Part 1 Preliminary ..................................................... 1",
                                "2",
                                "Part 2 Definitions and key concepts ........................... 5",
                                "5",
                                "Division 1 Meaning of aged care ................................ 6",
                                "6",
                                "Division 2 Access decisions ...................................... 8",
                                "Additional contents wording to keep the page strongly text-backed for Chronicle.",
                                "Further legal contents text ensures the alpha-character threshold is safely exceeded.",
                                "This line exists purely to make the fixture representative of a born-digital legal contents page.",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        emitted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=emitted,
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="legal",
                auto_escalation_model="gemini-2.5-pro",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Legal contents page should stay on direct text fast path"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=lambda *args, **kwargs: self.fail("Legal contents page should not trigger model streaming"),
                generate_retry_fn=lambda *args, **kwargs: self.fail("Legal contents page should not call the model"),
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("Keeping source page 1 on direct rendering" in line for line in logs))
        self.assertIn("<h1>Contents</h1>", emitted[0])
        self.assertIn("<h2>Part 1 Preliminary ..................................................... 1</h2>", emitted[0])
        self.assertIn("<h3>Division 1 Meaning of aged care ................................ 6</h3>", emitted[0])
        self.assertNotIn("[Original Page Number:", emitted[0])

    def test_process_pdf_escalates_fragmented_legal_text_page_to_auto_engine(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "A Bill for an Act about aged care, and for related",
                                "purposes",
                                "The Parliament of Australia enacts:",
                                "Chapter 1 Introduction",
                                "Part 1 Preliminary",
                                "1",
                                "Division 1 Entry into this Act",
                                "2",
                                "Division 2 Application and objects",
                                "3",
                                "Division 3 Simplified outline",
                                "4",
                                "Subdivision A Preliminary operation",
                                "5",
                                "Subdivision B Transitional application",
                                "6",
                                "Schedule 1 Review framework",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        uploads = []
        cache_calls = []
        logs = []
        emitted = []

        class Uploaded:
            def __init__(self):
                self.name = "files/line-numbered"
                self.state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                uploads.append((file, config))
                return Uploaded()

            def delete(self, *, name):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            cache_calls.append(key)
            response, cleanup = request_fn()
            try:
                mem.append(response)
            finally:
                cleanup()

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client=Client(),
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=emitted,
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="legal",
                auto_escalation_model="gemini-2.5-pro",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Fragmented legal pages should escalate via PDF upload"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: f"<h1>{model}</h1>",
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertTrue(any("Routing source page 1 straight to gemini-2.5-pro" in line for line in logs))
        self.assertEqual(len(cache_calls), 1)
        self.assertTrue(cache_calls[0].startswith("pdf-auto-escalate-upload:gemini-2.5-pro:0:"))
        self.assertEqual(len(uploads), 1)
        self.assertIn("gemini-2.5-pro", emitted[0])

    def test_process_pdf_keeps_line_numbered_legal_clause_page_on_fast_path(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "Chapter 1 Introduction",
                                "Part 1 Preliminary",
                                "1",
                                "1  Short title",
                                "2",
                                "This Act is the Aged Care Act 2024.",
                                "3",
                                "2  Commencement",
                                "4",
                                "This Act commences on a day fixed by Proclamation.",
                                "5",
                                "(a) on 1 July 2025;",
                                "6",
                                "(b) or on an earlier proclaimed day.",
                                "This additional legal body text keeps the fixture representative of a born-digital clause page.",
                                "Further substantive wording ensures the text-layer fast path thresholds are comfortably exceeded.",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        emitted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=emitted,
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="legal",
                auto_escalation_model="gemini-2.5-pro",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Clause-heavy legal pages should stay on direct text fast path"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=lambda *args, **kwargs: self.fail("Clause-heavy legal pages should not trigger model streaming"),
                generate_retry_fn=lambda *args, **kwargs: self.fail("Clause-heavy legal pages should not call the model"),
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("Keeping source page 1 on direct rendering because the legal clause layout" in line for line in logs))
        self.assertIn("<h3>1 Short title</h3>", emitted[0])
        self.assertIn("<h3>2 Commencement</h3>", emitted[0])

    def test_process_pdf_fast_path_treats_edge_digit_line_as_page_marker_only_once(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "7",
                                "1 Short title",
                                "This Act may be cited as the Aged Care Act 2024.",
                                "2 Commencement",
                                "This Act commences on a day fixed by Proclamation.",
                                "3 Objects",
                                "The objects of this Act are to improve aged care outcomes and access.",
                                "4 Act binds the Crown",
                                "This Act binds the Crown in each of its capacities.",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        emitted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=emitted,
                log_cb=lambda _msg: None,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="legal",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Text fast path should avoid PDF payload building"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: request_fn(),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertNotIn("[Original Page Number: 7]", emitted[0])
        self.assertIn("<h3>1 Short title</h3>", emitted[0])
        self.assertIn("<h3>2 Commencement</h3>", emitted[0])

    def test_process_pdf_legal_fast_path_ignores_top_table_digits_for_page_marker(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [
                    FakePage(
                        "\n".join(
                            [
                                "25",
                                "A decision under subsection 131(3) not to revoke the registration of an entity.",
                                "The entity",
                                "26",
                                "A decision under subsection 136(1) to vary the approval of an approved residential care home.",
                                "The registered provider",
                                "27",
                                "A decision under subsection 138(1) to revoke the approval of an approved residential care home.",
                                "The registered provider",
                                "11",
                            ]
                        )
                    )
                ]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        emitted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=emitted,
                log_cb=lambda _msg: None,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="legal",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Text fast path should avoid PDF payload building"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: request_fn(),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertNotIn("[Original Page Number:", emitted[0])

    def test_process_pdf_reports_scope_and_uses_vision_path(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage("one"), FakePage("two")]

        class FakeWriter:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        cache_calls = []
        progress = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gpt-4o",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                page_scope="1",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda model, prompt, file_path=None, mime=None, file_bytes=None: ("payload", file_path, mime, file_bytes),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: cache_calls.append((key, request_fn())),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("[Scope] Reading PDF pages 1" in line for line in logs))
        self.assertTrue(cache_calls[0][0].startswith("pdf-vision:0:1:"))
        self.assertEqual(progress[-1], (1, 1, 1))

    def test_process_pdf_logs_openai_pdf_fallback_reason_before_text_recovery(self):
        class FakePage:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage("Recovered text layer")]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        cache_calls = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gpt-4o",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda model, prompt, file_path=None, mime=None, file_bytes=None: (_ for _ in ()).throw(
                    Exception("GPT-4o cannot read Base64 PDF. Forcing text fallback.")
                ),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: cache_calls.append((key, request_fn())),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("[OpenAI PDF]" in line for line in logs))
        self.assertTrue(any("Falling back to the PDF text layer" in line for line in logs))
        self.assertTrue(any("[FAIL-SAFE] Page 1 vision failed. Extracting raw text layer." in line for line in logs))
        self.assertEqual(cache_calls[0][0], "pdf-text-failsafe-unit:sha:Recovered text layer")

    def test_process_pdf_uses_claude_files_api_when_available(self):
        class FakePage:
            def extract_text(self):
                return "one"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        uploads = []
        deleted = []
        request_payloads = []

        class FilesApi:
            def upload(self, **kwargs):
                uploads.append(kwargs)
                return {"id": "file_123"}

            def delete(self, file_id, **kwargs):
                deleted.append((file_id, kwargs))

        class BetaMessages:
            def create(self, **kwargs):
                request_payloads.append(kwargs)
                return []

        class Client:
            def __init__(self):
                self.beta = type("Beta", (), {"files": FilesApi(), "messages": BetaMessages()})()

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client=Client(),
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model=DEFAULT_CLAUDE_MODEL,
                f_obj=None,
                mem=[],
                log_cb=lambda _msg: None,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Claude Files API path should avoid inline base64 payloads"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: (
                    (lambda result: result[1]() if isinstance(result, tuple) and len(result) == 2 and callable(result[1]) else None)(request_fn())
                ),
                generate_retry_fn=lambda client, model, payload, log_cb=None: client.beta.messages.create(
                    model=model,
                    max_tokens=8192,
                    messages=[{"role": "user", "content": payload["content"]}],
                    stream=True,
                    betas=payload["betas"],
                ),
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertEqual(uploads[0]["betas"], ["files-api-2025-04-14"])
        self.assertEqual(request_payloads[0]["betas"], ["files-api-2025-04-14"])
        self.assertEqual(
            request_payloads[0]["messages"][0]["content"][0],
            {"type": "document", "source": {"type": "file", "file_id": "file_123"}},
        )
        self.assertEqual(deleted[0][0], "file_123")

    def test_process_pdf_logs_dense_newspaper_heuristic_for_heavy_short_pdf(self):
        class FakePage:
            def extract_text(self):
                return "one"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage() for _ in range(8)]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "dense.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(8.9 * 1024 * 1024))
            process_pdf(
                client="client",
                path=pdf_path,
                out="out.html",
                fmt="html",
                prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: list(range(total_pages)),
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda model, prompt, file_path=None, mime=None, file_bytes=None: ("payload", file_path, mime, file_bytes),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: request_fn(),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
            )

        self.assertTrue(any("[PDF Heuristic] Dense scanned newspaper detected" in line for line in logs))

    def test_process_pdf_prefers_in_memory_gemini_upload_and_waits_for_ready(self):
        class FakePage:
            def extract_text(self):
                return "one"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        uploads = []
        upload_configs = []
        waits = []
        removed = []
        logs = []

        class Uploaded:
            def __init__(self, name, state_name):
                self.name = name
                self.state = type("State", (), {"name": state_name})()

        class FilesApi:
            def upload(self, *, file, config=None):
                uploads.append(file)
                upload_configs.append(config)
                return Uploaded("files/123", "PROCESSING")

            def delete(self, *, name):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        with tempfile.TemporaryDirectory() as script_dir:
            process_pdf(
                client=Client(),
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                script_dir=script_dir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Gemini PDF flow should not build inline payloads here"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: (
                    (lambda result: result[1]() if isinstance(result, tuple) and len(result) == 2 and callable(result[1]) else None)(request_fn())
                ),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: removed.append(path) or os.remove(path),
                exists_fn=os.path.exists,
                tempdir_fn=lambda: self.fail("in-memory Gemini upload should not ask for a temp directory"),
                mkstemp_fn=lambda *args, **kwargs: self.fail("in-memory Gemini upload should not create temp files"),
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: waits.append((uploaded.name, kwargs["poll_sec"], kwargs["max_wait_sec"])) or Uploaded(uploaded.name, "ACTIVE"),
            )

        self.assertEqual(len(uploads), 1)
        self.assertIsInstance(uploads[0], io.BytesIO)
        self.assertEqual(getattr(uploads[0], "name", ""), "chronicle_pdf_1_1.pdf")
        self.assertEqual(uploads[0].getvalue(), b"%PDF-1.4\n")
        self.assertEqual(upload_configs[0], {"mime_type": "application/pdf", "display_name": "chronicle_pdf_1_1.pdf"})
        self.assertEqual(waits, [("files/123", 0.5, 30.0)])
        self.assertFalse(removed)
        self.assertIn("[Gemini PDF] Uploading slice chronicle_pdf_1_1.pdf (9 bytes).", logs)
        self.assertIn("[Gemini PDF] Waiting for slice chronicle_pdf_1_1.pdf to become ready.", logs)
        self.assertIn("[Gemini PDF] Slice chronicle_pdf_1_1.pdf is ready.", logs)

    def test_process_pdf_falls_back_to_system_temp_when_gemini_in_memory_upload_fails(self):
        class FakePage:
            def extract_text(self):
                return "one"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        uploads = []
        upload_configs = []
        removed = []
        logs = []

        class Uploaded:
            def __init__(self, name, state_name):
                self.name = name
                self.state = type("State", (), {"name": state_name})()

        class FilesApi:
            def __init__(self):
                self.calls = 0

            def upload(self, *, file, config=None):
                self.calls += 1
                uploads.append(file)
                upload_configs.append(config)
                if self.calls == 1:
                    raise RuntimeError("stream upload unavailable")
                return Uploaded("files/123", "ACTIVE")

            def delete(self, *, name):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        with tempfile.TemporaryDirectory() as script_dir, tempfile.TemporaryDirectory() as temp_dir:
            created_paths = []

            def fake_mkstemp(prefix, suffix, dir):
                self.assertEqual(dir, temp_dir)
                fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
                created_paths.append(path)
                return fd, path

            process_pdf(
                client=Client(),
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-flash",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                script_dir=script_dir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Gemini PDF flow should not build inline payloads here"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: (
                    (lambda result: result[1]() if isinstance(result, tuple) and len(result) == 2 and callable(result[1]) else None)(request_fn())
                ),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: removed.append(path) or os.remove(path),
                exists_fn=os.path.exists,
                tempdir_fn=lambda: temp_dir,
                mkstemp_fn=fake_mkstemp,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertEqual(len(created_paths), 1)
        self.assertEqual(uploads[1], created_paths[0])
        self.assertEqual(upload_configs[0], {"mime_type": "application/pdf", "display_name": "chronicle_pdf_1_1.pdf"})
        self.assertEqual(upload_configs[1], {"mime_type": "application/pdf", "display_name": "chronicle_pdf_1_1.pdf"})
        self.assertEqual(removed, created_paths)
        self.assertTrue(any("Falling back to temp-file upload" in line for line in logs))

    def test_process_pdf_does_not_need_temp_pdf_cleanup_for_in_memory_openai_path(self):
        class FakePage:
            def extract_text(self):
                return "one"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        logs = []
        progress = []

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client="client",
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gpt-4o",
                f_obj=None,
                mem=[],
                log_cb=logs.append,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                page_scope="",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text}",
                build_payload_fn=lambda model, prompt, file_path=None, mime=None, file_bytes=None: ("payload", file_path, mime, file_bytes),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: request_fn(),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: (_ for _ in ()).throw(PermissionError("still in use")),
                exists_fn=lambda path: True,
                tempdir_fn=lambda: tmpdir,
            )

        self.assertEqual(progress[-1], (1, 1, 1))
        self.assertFalse(any("Warning: could not delete temporary PDF slice" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
