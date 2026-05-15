import os
import tempfile
import unittest
import io

import chronicle_app.services.pdf_processor as pdf_processor_module
from chronicle_app.services.pdf_processor import process_pdf
from chronicle_app.services.pdf_processor import GEMINI_FILE_UPLOAD_TIMEOUT_MS
from chronicle_app.services.runtime_policies import DEFAULT_CLAUDE_MODEL


class PdfProcessorTest(unittest.TestCase):
    def test_process_pdf_sends_text_backed_legal_pages_to_deep_engine(self):
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

        class Uploaded:
            name = "files/legal"
            state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        logs = []
        cache_calls = []
        progress = []
        emitted = []

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            generated, cleanup = request_fn()
            cache_calls.append((key, generated))
            try:
                mem.append(generated)
                return generated
            finally:
                cleanup()

        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_pdf(
                client=Client(),
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
                build_payload_fn=lambda *args, **kwargs: self.fail("Deep legal PDF path should use Gemini PDF upload"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: f"deep legal output from {model}",
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertFalse(any("[PDF Fast Path]" in line for line in logs))
        self.assertTrue(cache_calls[0][0].startswith("pdf-upload:0:1:"))
        self.assertIn("deep legal output from gemini-2.5-pro", emitted[0])
        self.assertEqual(progress[-1], (1, 1, 1))

    def test_process_pdf_uses_text_fast_path_for_text_backed_script_pages(self):
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
                                "THE SAMPLE SCRIPT",
                                "-Lines for Reader-",
                                "THIS cue should stay exactly as printed. I Promise...",
                                "*Reader leans in with a smile sort of whispering* : and just pay attention.",
                                "READER Very Excited : WOW - WOW I CAN'T BELIEVE THIS WORKS!",
                                "Reader begs : GIve him a sample! I need this...",
                                "Reader Swooning : this keeps my VOIICE?!",
                                "Well, it's really not a fortune. More like Reality. That hurts...",
                                "*Performer please do some adlibbing here like we discussed in the call!*",
                                "DO SOMETHING, WIZARD! HELP HIM!",
                                "JUST PICK ONE!!!",
                                "Or",
                                "\"PICK ONE\"!!!",
                                "RIGHT!",
                                "*Reader Running *",
                                "Thanks for interrupting my reading!",
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
            os.environ["CHRONICLE_PDF_TEXT_FAST_PATH"] = "1"
            try:
                process_pdf(
                    client="client",
                    path="dummy.pdf",
                    out="out.html",
                    fmt="html",
                    prompt="SCRIPT / DIALOGUE / TRANSCRIPT RULES",
                    model=DEFAULT_CLAUDE_MODEL,
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=None,
                    page_scope="",
                    doc_profile="transcript",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=FakeWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 2,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text[:20]}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Text-backed script page should avoid PDF payload building"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                    stream_with_cache_fn=lambda *args, **kwargs: self.fail("Text-backed script page should not call the model"),
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Text-backed script page should not call generate"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                )
            finally:
                os.environ.pop("CHRONICLE_PDF_TEXT_FAST_PATH", None)

        self.assertTrue(any("[PDF Fast Path]" in line for line in logs))
        self.assertIn("<h1>THE SAMPLE SCRIPT</h1>", emitted[0])
        self.assertIn("<strong>READER Very Excited</strong>: WOW - WOW I CAN&#x27;T BELIEVE THIS WORKS!", emitted[0])
        self.assertIn("GIve him a sample", emitted[0])
        self.assertIn("<p><strong><em>*Performer please do some adlibbing here like we discussed in the call!*</em></strong></p>", emitted[0])

    def test_process_pdf_sends_text_backed_legal_contents_page_to_deep_engine(self):
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

        class Uploaded:
            name = "files/legal"
            state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        logs = []
        emitted = []
        calls = []

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            generated, cleanup = request_fn()
            calls.append((key, generated))
            try:
                mem.append(generated)
                return generated
            finally:
                cleanup()

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client=Client(),
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
                build_payload_fn=lambda *args, **kwargs: self.fail("Legal contents page should use Gemini PDF upload"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: f"deep legal output from {model}",
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertTrue(calls)
        self.assertIn("pdf-upload:gemini-2.5-pro", calls[0][0])
        self.assertTrue(any("[Gemini PDF] Requesting model output" in line for line in logs))
        self.assertFalse(any("Keeping source page 1 on direct rendering" in line for line in logs))
        self.assertIn("deep legal output from gemini-2.5-pro", emitted[0])

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
                model="gemini-2.5-pro",
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

        self.assertTrue(any("[Gemini PDF] Requesting model output" in line for line in logs))
        self.assertEqual(len(cache_calls), 1)
        self.assertTrue(cache_calls[0].startswith("pdf-upload:gemini-2.5-pro:0:"))
        self.assertEqual(len(uploads), 1)
        self.assertIn("gemini-2.5-pro", emitted[0])

    def test_process_pdf_modern_newspaper_uses_gemini_pdf_upload_not_text_fast_path(self):
        class FakePage:
            def extract_text(self):
                return "\n".join(
                    [
                        "Volume 144 Number 18",
                        "MIT's Oldest and Largest Newspaper",
                        "News",
                        "The 2024 Election: The Institute Reacts",
                        "By Alex Tang",
                        "Student voices echo the sentiments of the nation.",
                        "Opinion",
                        "What now?",
                        "Sports",
                        "Upcoming tournament coverage and standings.",
                    ]
                    * 25
                )

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def __init__(self):
                self.added = []

            def add_page(self, page):
                self.added.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\nmodern newspaper page")

        uploads = []
        emitted = []

        class Uploaded:
            def __init__(self):
                self.name = "files/modern-newspaper"
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
            response, cleanup = request_fn()
            try:
                mem.append(response)
                return response
            finally:
                cleanup()

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client=Client(),
                path="dummy.pdf",
                out="out.html",
                fmt="html",
                prompt="Prompt\nMODERN NEWSPAPER / E-PAPER RULES",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=emitted,
                log_cb=lambda line: None,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="modern_newspaper",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda *args, **kwargs: self.fail("Modern newspaper Gemini path should upload PDF slices"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: "<article><h1>Modern newspaper output</h1></article>",
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0][1]["mime_type"], "application/pdf")
        self.assertIn("Modern newspaper output", emitted[0])

    def test_process_pdf_sends_line_numbered_legal_clause_page_to_deep_engine(self):
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

        class Uploaded:
            name = "files/legal"
            state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        logs = []
        emitted = []
        calls = []

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            generated, cleanup = request_fn()
            calls.append((key, generated))
            try:
                mem.append(generated)
                return generated
            finally:
                cleanup()

        with tempfile.TemporaryDirectory() as tmpdir:
            process_pdf(
                client=Client(),
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
                build_payload_fn=lambda *args, **kwargs: self.fail("Clause-heavy legal pages should use Gemini PDF upload"),
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: f"deep legal output from {model}",
                split_text_for_fail_safe_fn=lambda text, max_chars=1600: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
            )

        self.assertTrue(calls)
        self.assertIn("pdf-upload:gemini-2.5-pro", calls[0][0])
        self.assertTrue(any("[Gemini PDF] Requesting model output" in line for line in logs))
        self.assertFalse(any("Keeping source page 1 on direct rendering" in line for line in logs))
        self.assertIn("deep legal output from gemini-2.5-pro", emitted[0])

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
            os.environ["CHRONICLE_PDF_TEXT_FAST_PATH"] = "1"
            try:
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
                doc_profile="standard",
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
            finally:
                os.environ.pop("CHRONICLE_PDF_TEXT_FAST_PATH", None)

        self.assertIn("[Original Page Number: 7]", emitted[0])
        self.assertIn("<h3>1 Short title</h3>", emitted[0])
        self.assertIn("<h3>2 Commencement</h3>", emitted[0])

    def test_process_pdf_internal_text_fast_path_keeps_top_table_digit_marker_visible(self):
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
            os.environ["CHRONICLE_PDF_TEXT_FAST_PATH"] = "1"
            try:
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
                doc_profile="standard",
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
            finally:
                os.environ.pop("CHRONICLE_PDF_TEXT_FAST_PATH", None)

        self.assertIn("[Original Page Number: 25]", emitted[0])

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
                allow_text_layer_fallback=True,
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
                allow_text_layer_fallback=True,
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
            try:
                result = process_pdf(
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
	                allow_text_layer_fallback=True,
	                )
            finally:
                os.environ.pop("CHRONICLE_NLA_LOCAL_OCR_FAST_PATH", None)

        self.assertTrue(any("[PDF Heuristic] Dense scanned newspaper detected" in line for line in logs))

    def test_process_pdf_uses_pro_image_strips_for_dense_newspaper_without_engine_switch(self):
        nla_text = "\n".join(
            [
                "National Library of Australia",
                "http://nla.gov.au/nla.news-page971274",
                "BATES' SALVE",
            ]
            + [f"Column OCR line {idx} with newspaper text and advertisements." for idx in range(900)]
        )

        class FakePage:
            def extract_text(self):
                return nla_text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        class Uploaded:
            def __init__(self, name="files/123"):
                self.name = name
                self.state = type("State", (), {"name": "ACTIVE"})()

        uploads = []

        class FilesApi:
            def upload(self, *, file, config=None):
                uploads.append((file, config))
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        calls = []

        class ModelsApi:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                return type("Response", (), {"text": "<article><h1>Pro newspaper result</h1></article>"})()

        class Client:
            def __init__(self):
                self.files = FilesApi()
                self.models = ModelsApi()

        logs = []
        emitted = []
        trove_requests = []

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            response, cleanup = request_fn()
            try:
                mem.append(response if isinstance(response, str) else response.text)
            finally:
                cleanup()

        def fake_urlopen(*args, **kwargs):
            trove_requests.append(args)
            raise RuntimeError("offline")

        test_case = self

        class FakePixmap:
            def tobytes(self, fmt):
                test_case.assertEqual(fmt, "png")
                return b"rendered-png"

        class FakePageImage:
            rect = type("Rect", (), {"x0": 0, "y0": 0, "x1": 400, "y1": 800, "width": 400})()

            def get_pixmap(self, **kwargs):
                test_case.assertIn("clip", kwargs)
                return FakePixmap()

        class FakeFitzDoc:
            def load_page(self, index):
                test_case.assertEqual(index, 0)
                return FakePageImage()

            def close(self):
                return None

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(x, y):
                return (x, y)

            @staticmethod
            def Rect(x0, y0, x1, y1):
                return (x0, y0, x1, y1)

            @staticmethod
            def open(path):
                return FakeFitzDoc()

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "dense.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(1.2 * 1024 * 1024))
            original_fitz = pdf_processor_module.fitz
            pdf_processor_module.fitz = FakeFitz
            try:
                process_pdf(
                    client=Client(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=None,
                    page_scope="",
                    doc_profile="newspaper",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=FakeWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Gemini PDF flow should not build inline payloads here"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=fake_stream,
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Dense newspaper Pro path should not use streaming"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                    remove_fn=lambda path: None,
	                    exists_fn=lambda path: True,
	                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
	                    allow_text_layer_fallback=True,
	                    urlopen_fn=fake_urlopen,
	                )
            finally:
                pdf_processor_module.fitz = original_fitz

        self.assertEqual(trove_requests, [])
        self.assertEqual([call["model"] for call in calls], ["gemini-2.5-pro"] * 2)
        self.assertEqual(calls[0]["config"]["http_options"]["timeout"], 300_000)
        self.assertEqual(calls[0]["contents"][0]["parts"][0]["inlineData"]["mimeType"], "image/png")
        self.assertEqual(len(uploads), 0)
        self.assertEqual(len(emitted), 2)
        self.assertIn("Pro newspaper result", emitted[0])
        self.assertNotIn("strip 1", "".join(emitted).lower())
        self.assertNotIn("Source page", "".join(emitted))
        self.assertTrue(any("[Gemini Image] Requesting dense newspaper strip 2/2" in line for line in logs))
        self.assertFalse(any("Dense NLA newspaper OCR detected" in line for line in logs))

    def test_process_pdf_does_not_use_trove_article_ocr_by_default(self):
        class FakePage:
            def extract_text(self):
                return "National Library of Australia\nhttp://nla.gov.au/nla.news-page14852172\nOCR marker"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        trove_requests = []
        emitted = []

        def fake_urlopen(*args, **kwargs):
            trove_requests.append(args)
            raise RuntimeError("Trove should not be consulted by default")

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            mem.append(request_fn())

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "nla.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * 1024)

            process_pdf(
                client=object(),
                path=pdf_path,
                out="out.html",
                fmt="html",
                prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                model="gpt-4.1",
                f_obj=None,
                mem=emitted,
                log_cb=lambda _line: None,
                confidence_cb=None,
                pause_cb=None,
                page_progress_cb=None,
                page_scope="",
                doc_profile="newspaper",
                script_dir=tmpdir,
                pdf_reader_cls=FakeReader,
                pdf_writer_cls=FakeWriter,
                parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                normalize_pdf_page_scope_text_fn=lambda scope: scope,
                get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                sha256_file_fn=lambda path: "fingerprint",
                sha256_text_fn=lambda text: f"sha:{text[:20]}",
                build_payload_fn=lambda model, prompt, mime=None, file_bytes=None, **kwargs: "gpt visual output",
                build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                stream_with_cache_fn=fake_stream,
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                remove_fn=lambda path: None,
                exists_fn=lambda path: True,
                urlopen_fn=fake_urlopen,
            )

        self.assertEqual(trove_requests, [])
        self.assertEqual(emitted, ["gpt visual output"])

    def test_process_pdf_uses_trove_article_ocr_only_when_explicitly_enabled(self):
        class FakePage:
            def extract_text(self):
                return "National Library of Australia\nhttp://nla.gov.au/nla.news-page14852172\nOCR marker"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class FakeWriter:
            def add_page(self, page):
                return None

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        class FakeResponse:
            def __init__(self, text):
                self._text = text

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self._text.encode("utf-8")

        def fake_urlopen(request, timeout=25):
            url = getattr(request, "full_url", str(request))
            if url.endswith("/newspaper/page/14852172"):
                return FakeResponse('<li class="articleFromDB" id="article129610963"><h4><a href="#">Honor roll</a></h4></li>')
            if "nla.news-article129610963.txt" in url:
                return FakeResponse(
                    "<html><head><title>04 May 1918 - KYNETON DISTRICT HONOR ROLL.</title></head>"
                    "<body><p>citation</p><hr/>"
                    "<div class='zone'><p>KYNETON DISTRICT HONOR ROLL.</p></div>"
                    "<div class='zone'><p>THOSE WHO HAVE FOUGHT FOR FREEDOM'S CAUSE.</p>"
                    "<p>Pte. A. Aitken</p></div></body></html>"
                )
            raise AssertionError(url)

        logs = []
        emitted = []
        progress = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "nla.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * 1024)

            os.environ["CHRONICLE_NLA_TROVE_ARTICLE_OCR"] = "1"
            try:
                process_pdf(
                    client=object(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                    page_scope="",
                    doc_profile="newspaper",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=FakeWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text[:20]}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Explicit Trove article OCR should bypass Gemini payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{fp}",
                    stream_with_cache_fn=lambda *args, **kwargs: self.fail("Explicit Trove article OCR should bypass streaming"),
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Explicit Trove article OCR should bypass Gemini retries"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
                    urlopen_fn=fake_urlopen,
                )
            finally:
                os.environ.pop("CHRONICLE_NLA_TROVE_ARTICLE_OCR", None)

        joined = "".join(emitted)
        self.assertIn("<h2>Page 1</h2>", joined)
        self.assertIn("<h3>KYNETON DISTRICT HONOR ROLL</h3>", joined)
        self.assertIn("Pte. A. Aitken", joined)
        self.assertEqual(progress[-1], (1, 1, 1))
        self.assertTrue(any("Trove OCR: used article-level OCR" in line for line in logs))

    def test_process_pdf_dense_newspaper_pro_skips_pdf_slice_build_before_rendered_strips(self):
        class FakePage:
            def extract_text(self):
                return ""

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage(), FakePage()]

        class BrokenSliceWriter:
            def add_page(self, page):
                raise RuntimeError("damaged xref slice path should not be touched")

            def write(self, fh):
                raise RuntimeError("damaged xref slice path should not be touched")

        class Uploaded:
            def __init__(self, name="files/123"):
                self.name = name
                self.state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        class ModelsApi:
            def generate_content(self, **kwargs):
                return type("Response", (), {"text": "HEADLINE\nBody text"})()

        class Client:
            def __init__(self):
                self.files = FilesApi()
                self.models = ModelsApi()

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            response, cleanup = request_fn()
            try:
                text = response if isinstance(response, str) else response.text
                mem.append(text)
                return text
            finally:
                cleanup()

        class FakePixmap:
            def tobytes(self, fmt):
                return b"rendered-png"

        class FakePageImage:
            rect = type("Rect", (), {"x0": 0, "y0": 0, "x1": 400, "y1": 800, "width": 400})()

            def get_pixmap(self, **kwargs):
                return FakePixmap()

        class FakeFitzDoc:
            def load_page(self, index):
                return FakePageImage()

            def close(self):
                return None

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(x, y):
                return (x, y)

            @staticmethod
            def Rect(x0, y0, x1, y1):
                return (x0, y0, x1, y1)

            @staticmethod
            def open(path):
                return FakeFitzDoc()

        logs = []
        emitted = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "dense.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(2.4 * 1024 * 1024))
            original_fitz = pdf_processor_module.fitz
            pdf_processor_module.fitz = FakeFitz
            try:
                process_pdf(
                    client=Client(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=None,
                    page_scope="",
                    doc_profile="newspaper",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=BrokenSliceWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0, 1],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 2,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Dense strip path should not build inline payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=fake_stream,
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Dense newspaper Pro path should not use streaming"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
                    allow_text_layer_fallback=True,
                )
            finally:
                pdf_processor_module.fitz = original_fitz

        self.assertEqual(len(emitted), 4)
        self.assertTrue(any("Rendering source page 1 as 2 newspaper strips" in line for line in logs))
        self.assertTrue(any("Rendering source page 2 as 2 newspaper strips" in line for line in logs))

    def test_process_pdf_image_only_military_page_uses_rendered_image_before_pdf_upload(self):
        class FakePage:
            def extract_text(self):
                return ""

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class BrokenSliceWriter:
            def add_page(self, page):
                raise RuntimeError("image-only scanned page should not be rebuilt as a PDF slice")

            def write(self, fh):
                raise RuntimeError("image-only scanned page should not be rebuilt as a PDF slice")

        class FilesApi:
            def upload(self, *, file, config=None):
                self_test.fail("Rendered scanned-page path should use inline image REST, not Gemini file upload")

            def delete(self, *, name, config=None):
                return None

        calls = []

        class ModelsApi:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                return type("Response", (), {"text": "<article><h1>War diary</h1><table><tr><td>1 June</td><td>Body text</td></tr></table></article>"})()

        class Client:
            def __init__(self):
                self.files = FilesApi()
                self.models = ModelsApi()

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            response, cleanup = request_fn()
            try:
                mem.append(response if isinstance(response, str) else response.text)
                return mem[-1]
            finally:
                cleanup()

        class FakePixmap:
            def tobytes(self, fmt):
                self_test.assertEqual(fmt, "png")
                return b"rendered-war-diary-page"

        class FakePageImage:
            def get_pixmap(self, **kwargs):
                self_test.assertNotIn("clip", kwargs)
                return FakePixmap()

        class FakeFitzDoc:
            def load_page(self, index):
                self_test.assertEqual(index, 0)
                return FakePageImage()

            def close(self):
                return None

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(x, y):
                return (x, y)

            @staticmethod
            def open(path):
                return FakeFitzDoc()

        self_test = self
        logs = []
        emitted = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "Australian Imperial Force Unit War Diary.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(2.0 * 1024 * 1024))
            original_fitz = pdf_processor_module.fitz
            pdf_processor_module.fitz = FakeFitz
            try:
                process_pdf(
                    client=Client(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nMILITARY RECORDS",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=None,
                    page_scope="",
                    doc_profile="military",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=BrokenSliceWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Image-only scanned page should not build PDF payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=fake_stream,
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Image-only scanned page should not use Gemini PDF streaming"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                    remove_fn=os.remove,
                    exists_fn=os.path.exists,
                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
                    allow_text_layer_fallback=True,
                )
            finally:
                pdf_processor_module.fitz = original_fitz

            leftovers = [name for name in os.listdir(tmpdir) if name.startswith("chronicle_temp_")]

        self.assertEqual(len(calls), 1)
        self.assertIn("'mimeType': 'image/png'", str(calls[0]["contents"]))
        self.assertIn("SCANNED IMAGE-ONLY PDF PAGE MODE", str(calls[0]["contents"]))
        self.assertIn("War diary", emitted[0])
        self.assertEqual(leftovers, [])
        self.assertTrue(any("Image-only scanned page detected" in line for line in logs))
        self.assertTrue(any("Visible rendered page:" in line for line in logs))

    def test_process_pdf_dense_newspaper_flash_uses_pro_strip_escalation_before_pdf_slice(self):
        class FakePage:
            def extract_text(self):
                return ""

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class BrokenSliceWriter:
            def add_page(self, page):
                raise RuntimeError("malformed PDF slice path should not run before Pro strips")

            def write(self, fh):
                raise RuntimeError("malformed PDF slice path should not run before Pro strips")

        class Uploaded:
            def __init__(self, name="files/123"):
                self.name = name
                self.state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        calls = []

        class ModelsApi:
            def generate_content(self, **kwargs):
                calls.append(kwargs)
                return type("Response", (), {"text": "HEADLINE\nBody text"})()

        class Client:
            def __init__(self):
                self.files = FilesApi()
                self.models = ModelsApi()

        def fake_stream(key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None):
            response, cleanup = request_fn()
            try:
                text = response if isinstance(response, str) else response.text
                mem.append(text)
                return text
            finally:
                cleanup()

        class FakePixmap:
            def tobytes(self, fmt):
                return b"rendered-png"

        class FakePageImage:
            rect = type("Rect", (), {"x0": 0, "y0": 0, "x1": 400, "y1": 800, "width": 400})()

            def get_pixmap(self, **kwargs):
                return FakePixmap()

        class FakeFitzDoc:
            def load_page(self, index):
                return FakePageImage()

            def close(self):
                return None

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(x, y):
                return (x, y)

            @staticmethod
            def Rect(x0, y0, x1, y1):
                return (x0, y0, x1, y1)

            @staticmethod
            def open(path):
                return FakeFitzDoc()

        logs = []
        emitted = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "dense.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(1.2 * 1024 * 1024))
            original_fitz = pdf_processor_module.fitz
            pdf_processor_module.fitz = FakeFitz
            try:
                process_pdf(
                    client=Client(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-flash",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=None,
                    page_scope="",
                    doc_profile="newspaper",
                    auto_escalation_model="gemini-2.5-pro",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=BrokenSliceWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Dense strip path should not build inline payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=fake_stream,
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Dense newspaper Pro strip path should not use streaming"),
                    split_text_for_fail_safe_fn=lambda text, max_chars=900: [text],
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
                    allow_text_layer_fallback=True,
                )
            finally:
                pdf_processor_module.fitz = original_fitz

        self.assertEqual([call["model"] for call in calls], ["gemini-2.5-pro"] * 2)
        self.assertEqual(len(emitted), 2)
        self.assertTrue(any("directly to gemini-2.5-pro image strips" in line for line in logs))

    def test_process_pdf_dense_newspaper_strip_failure_uses_local_text_layer_without_recovery_storm(self):
        class FakePage:
            def extract_text(self):
                return "National Library of Australia\nHEADLINE\nBody text from local OCR"

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class BrokenSliceWriter:
            def add_page(self, page):
                raise RuntimeError("PDF retry should not be used after dense strip failure")

            def write(self, fh):
                raise RuntimeError("PDF retry should not be used after dense strip failure")

        class Uploaded:
            def __init__(self, name="files/123"):
                self.name = name
                self.state = type("State", (), {"name": "ACTIVE"})()

        class FilesApi:
            def upload(self, *, file, config=None):
                return Uploaded()

            def delete(self, *, name, config=None):
                return None

        class Client:
            def __init__(self):
                self.files = FilesApi()

        class FakePixmap:
            def tobytes(self, fmt):
                return b"rendered-png"

        class FakePageImage:
            rect = type("Rect", (), {"x0": 0, "y0": 0, "x1": 400, "y1": 800, "width": 400})()

            def get_pixmap(self, **kwargs):
                return FakePixmap()

        class FakeFitzDoc:
            def load_page(self, index):
                return FakePageImage()

            def close(self):
                return None

        class FakeFitz:
            csRGB = object()

            @staticmethod
            def Matrix(x, y):
                return (x, y)

            @staticmethod
            def Rect(x0, y0, x1, y1):
                return (x0, y0, x1, y1)

            @staticmethod
            def open(path):
                return FakeFitzDoc()

        logs = []
        emitted = []
        progress = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "dense.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(1.2 * 1024 * 1024))
            original_fitz = pdf_processor_module.fitz
            pdf_processor_module.fitz = FakeFitz
            try:
                process_pdf(
                    client=Client(),
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                    page_scope="",
                    doc_profile="newspaper",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=BrokenSliceWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Dense fallback should not build inline payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("image upload failed")),
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Dense fallback should not call model recovery"),
                    split_text_for_fail_safe_fn=lambda *args, **kwargs: self.fail("Dense fallback should not split local OCR into many model calls"),
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                    wait_for_gemini_upload_ready_fn=lambda client, uploaded, **kwargs: uploaded,
                    allow_text_layer_fallback=True,
                )
            finally:
                pdf_processor_module.fitz = original_fitz

        self.assertEqual(progress[-1], (1, 1, 1))
        self.assertEqual(len(emitted), 1)
        self.assertIn("Body text from local OCR", emitted[0])
        self.assertTrue(any("using local OCR text layer" in line for line in logs))

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
        self.assertEqual(upload_configs[0]["http_options"]["timeout"], GEMINI_FILE_UPLOAD_TIMEOUT_MS)
        self.assertEqual(upload_configs[0]["mime_type"], "application/pdf")
        self.assertEqual(upload_configs[0]["display_name"], "chronicle_pdf_1_1.pdf")
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
        self.assertEqual(upload_configs[0]["mime_type"], "application/pdf")
        self.assertEqual(upload_configs[0]["display_name"], "chronicle_pdf_1_1.pdf")
        self.assertEqual(upload_configs[0]["http_options"]["timeout"], GEMINI_FILE_UPLOAD_TIMEOUT_MS)
        self.assertEqual(upload_configs[1]["mime_type"], "application/pdf")
        self.assertEqual(upload_configs[1]["display_name"], "chronicle_pdf_1_1.pdf")
        self.assertEqual(upload_configs[1]["http_options"]["timeout"], GEMINI_FILE_UPLOAD_TIMEOUT_MS)
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

    def test_process_pdf_dense_nla_newspaper_uses_local_ocr_only_when_fast_path_enabled(self):
        nla_text = "\n".join(
            [
                "National Library of Australia",
                "http://nla.gov.au/nla.news-page971274",
                "BATES' SALVE",
                "Shipping.",
                "FREMANTLE INDIA CHINA AND EUROPE",
            ]
            + [f"Column OCR line {idx} with newspaper text and advertisements." for idx in range(900)]
        )

        class FakePage:
            def extract_text(self):
                return nla_text

        class FakeReader:
            def __init__(self, _path):
                self.pages = [FakePage()]

        class BrokenSliceWriter:
            def add_page(self, page):
                raise RuntimeError("dense NLA OCR path should not build PDF slices")

            def write(self, fh):
                raise RuntimeError("dense NLA OCR path should not build PDF slices")

        logs = []
        emitted = []
        progress = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "nla.news-issue108507.pdf")
            with open(pdf_path, "wb") as fh:
                fh.write(b"x" * int(1.2 * 1024 * 1024))
            os.environ["CHRONICLE_NLA_LOCAL_OCR_FAST_PATH"] = "1"

            try:
                result = process_pdf(
                    client="client",
                    path=pdf_path,
                    out="out.html",
                    fmt="html",
                    prompt="Prompt\nHISTORICAL NEWSPAPER RULES",
                    model="gemini-2.5-pro",
                    f_obj=None,
                    mem=emitted,
                    log_cb=logs.append,
                    confidence_cb=None,
                    pause_cb=None,
                    page_progress_cb=lambda done, total, page=None: progress.append((done, total, page)),
                    page_scope="",
                    doc_profile="newspaper",
                    script_dir=tmpdir,
                    pdf_reader_cls=FakeReader,
                    pdf_writer_cls=BrokenSliceWriter,
                    parse_pdf_page_scope_spec_fn=lambda scope, total_pages: [0],
                    normalize_pdf_page_scope_text_fn=lambda scope: scope,
                    get_pdf_chunk_pages_fn=lambda model, profile, total, **kwargs: 1,
                    sha256_file_fn=lambda path: "fingerprint",
                    sha256_text_fn=lambda text: f"sha:{text}",
                    build_payload_fn=lambda *args, **kwargs: self.fail("Dense NLA OCR path should not build inline payloads"),
                    build_request_cache_key_fn=lambda model, prompt, kind, fp: f"{kind}:{model}:{fp}",
                    stream_with_cache_fn=lambda *args, **kwargs: self.fail("Dense NLA OCR path should not call model streaming"),
                    generate_retry_fn=lambda *args, **kwargs: self.fail("Dense NLA OCR path should not call the model"),
                    split_text_for_fail_safe_fn=lambda *args, **kwargs: self.fail("Dense NLA OCR path should not split OCR into model calls"),
                    remove_fn=lambda path: None,
                    exists_fn=lambda path: True,
                )
            finally:
                os.environ.pop("CHRONICLE_NLA_LOCAL_OCR_FAST_PATH", None)

        self.assertEqual(progress[-1], (1, 1, 1))
        self.assertEqual(result, {"used_dense_newspaper_local_ocr": True})
        self.assertEqual(len(emitted), 1)
        self.assertIn("BATES&#x27; SALVE", emitted[0])
        self.assertTrue(any("Dense NLA newspaper OCR detected" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
