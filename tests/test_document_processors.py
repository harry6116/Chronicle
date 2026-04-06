import os
import tempfile
import types
import unittest

from chronicle_app.services.document_processors import (
    estimate_text_work_units,
    process_epub,
    process_img,
    process_pptx,
    process_text,
)


class DocumentProcessorsTest(unittest.TestCase):
    def test_process_text_streams_docx_batches(self):
        calls = []
        fake_docx = types.SimpleNamespace(
            Document=lambda path: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="Alpha"), types.SimpleNamespace(text="Beta")])
        )

        process_text(
            client="client",
            path="/tmp/sample.docx",
            out="out.html",
            ext=".docx",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=1000,
            csv_to_accessible_text_fn=lambda raw: raw,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda model, prompt, kind, fingerprint: f"{kind}:{fingerprint}",
            sha256_text_fn=lambda text: f"sha:{text}",
            stream_with_cache_fn=lambda key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None: calls.append((key, request_fn())),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            docx_module=fake_docx,
            openpyxl_module=None,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1][0], "Alpha\nBeta")
        self.assertIn("SOURCE-TEXT REPLICATION MODE", calls[0][1][1])

    def test_process_text_adds_source_text_mode_for_legal_docs(self):
        calls = []
        fake_docx = types.SimpleNamespace(
            Document=lambda path: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="Clause 1"), types.SimpleNamespace(text="Clause 2")])
        )

        process_text(
            client="client",
            path="/tmp/sample.docx",
            out="out.html",
            ext=".docx",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=1000,
            csv_to_accessible_text_fn=lambda raw: raw,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda model, prompt, kind, fingerprint: f"{kind}:{fingerprint}",
            sha256_text_fn=lambda text: f"sha:{text}",
            stream_with_cache_fn=lambda key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None: calls.append((key, request_fn())),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            docx_module=fake_docx,
            openpyxl_module=None,
            doc_profile="legal",
        )

        self.assertIn("legal/government hierarchy", calls[0][1][1])

    def test_estimate_text_work_units_counts_docx_batches(self):
        fake_docx = types.SimpleNamespace(
            Document=lambda path: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="Alpha"), types.SimpleNamespace(text="Beta")])
        )

        total = estimate_text_work_units(
            "/tmp/sample.docx",
            ".docx",
            text_chunk_chars=5,
            csv_to_accessible_text_fn=lambda raw: raw,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            docx_module=fake_docx,
            openpyxl_module=None,
        )

        self.assertEqual(total, 2)

    def test_process_text_uses_csv_adapter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sample.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("A,B\n1,2\n")
            seen = []

            process_text(
                client="client",
                path=path,
                out="out.html",
                ext=".csv",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=[],
                log_cb=lambda _msg: None,
                pause_cb=None,
                text_chunk_chars=1000,
                csv_to_accessible_text_fn=lambda raw: seen.append(raw) or "CSV_TEXT",
                clean_text_fn=lambda text: text,
                batch_text_chunks_fn=lambda chunks: chunks,
                build_request_cache_key_fn=lambda *args: "key",
                sha256_text_fn=lambda text: text,
                stream_with_cache_fn=lambda *args, **kwargs: None,
                generate_retry_fn=lambda *args, **kwargs: None,
                docx_module=None,
                openpyxl_module=None,
            )

            self.assertIn("A,B", seen[0])

    def test_process_text_renders_tabular_html_without_streaming(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sample.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("Date,Score\n2026-01-01,10\n")
            emitted = []
            progress = []

            process_text(
                client="client",
                path=path,
                out="out.html",
                ext=".csv",
                fmt="html",
                prompt="Prompt",
                model="gemini-2.5-pro",
                f_obj=None,
                mem=emitted,
                log_cb=lambda _msg: None,
                pause_cb=None,
                text_chunk_chars=1000,
                csv_to_accessible_text_fn=lambda raw: "UNUSED",
                clean_text_fn=lambda text: text,
                batch_text_chunks_fn=lambda chunks: chunks,
                build_request_cache_key_fn=lambda *args: "key",
                sha256_text_fn=lambda text: text,
                stream_with_cache_fn=lambda *args, **kwargs: self.fail("stream_with_cache should not run for tabular html"),
                generate_retry_fn=lambda *args, **kwargs: None,
                docx_module=None,
                openpyxl_module=None,
                page_progress_cb=lambda done, total: progress.append((done, total)),
                doc_profile="tabular",
            )

            self.assertIn("<h1>Sample</h1>", emitted[0])
            self.assertIn("<table>", emitted[0])
            self.assertEqual(progress, [(1, 1)])

    def test_process_pptx_reports_chunk_progress(self):
        class Shape:
            def __init__(self, text):
                self.text = text
                self.has_text_frame = True
                self.top = 0
                self.left = 0

        slides = [types.SimpleNamespace(shapes=[Shape("One")]), types.SimpleNamespace(shapes=[Shape("Two")])]
        fake_pptx = types.SimpleNamespace(Presentation=lambda path: types.SimpleNamespace(slides=slides))
        progress = []
        payloads = []

        process_pptx(
            client="client",
            path="/tmp/sample.pptx",
            out="out.html",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            page_progress_cb=lambda done, total: progress.append((done, total)),
            text_chunk_chars=1000,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda *args: "key",
            sha256_text_fn=lambda text: text,
            stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            pptx_module=fake_pptx,
        )

        self.assertEqual(progress, [(1, 1)])
        self.assertEqual(payloads[0][0], "\n[--- Slide: 1 ---]\nOne\n\n[--- Slide: 2 ---]\nTwo\n")
        self.assertIn("SOURCE-TEXT REPLICATION MODE", payloads[0][1])

    def test_process_text_reports_chunk_progress(self):
        progress = []
        fake_docx = types.SimpleNamespace(
            Document=lambda path: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="Alpha Beta")])
        )

        process_text(
            client="client",
            path="/tmp/sample.docx",
            out="out.html",
            ext=".docx",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=5,
            csv_to_accessible_text_fn=lambda raw: raw,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda model, prompt, kind, fingerprint: f"{kind}:{fingerprint}",
            sha256_text_fn=lambda text: f"sha:{text}",
            stream_with_cache_fn=lambda key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None: request_fn(),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            docx_module=fake_docx,
            openpyxl_module=None,
            page_progress_cb=lambda done, total: progress.append((done, total)),
        )

        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_process_text_skips_completed_batches_on_resume(self):
        progress = []
        payloads = []
        fake_docx = types.SimpleNamespace(
            Document=lambda path: types.SimpleNamespace(paragraphs=[types.SimpleNamespace(text="Alpha Beta")])
        )

        process_text(
            client="client",
            path="/tmp/sample.docx",
            out="out.html",
            ext=".docx",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=5,
            csv_to_accessible_text_fn=lambda raw: raw,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda model, prompt, kind, fingerprint: f"{kind}:{fingerprint}",
            sha256_text_fn=lambda text: f"sha:{text}",
            stream_with_cache_fn=lambda key, request_fn, out, fmt, f_obj, mem, log_cb, pause_cb=None: payloads.append(request_fn()),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            docx_module=fake_docx,
            openpyxl_module=None,
            page_progress_cb=lambda done, total: progress.append((done, total)),
            resume_from_batch=1,
        )

        self.assertEqual(progress, [(2, 2)])
        self.assertEqual(len(payloads), 1)

    def test_process_epub_reads_document_items_only(self):
        class Item:
            def __init__(self, type_id, body):
                self._type = type_id
                self._body = body

            def get_type(self):
                return self._type

            def get_body_content(self):
                return self._body

        fake_book = types.SimpleNamespace(get_items=lambda: [Item(9, b"<p>Hello</p>"), Item(1, b"skip")])
        fake_epub = types.SimpleNamespace(read_epub=lambda path: fake_book)
        payloads = []

        process_epub(
            client="client",
            path="/tmp/sample.epub",
            out="out.html",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=1000,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda *args: "key",
            sha256_text_fn=lambda text: text,
            stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            epub_module=fake_epub,
        )

        self.assertEqual(payloads[0][0], " Hello \n")
        self.assertIn("SOURCE-TEXT REPLICATION MODE", payloads[0][1])

    def test_process_epub_skips_completed_batches_on_resume(self):
        class Item:
            def __init__(self, type_id, body):
                self._type = type_id
                self._body = body

            def get_type(self):
                return self._type

            def get_body_content(self):
                return self._body

        fake_book = types.SimpleNamespace(get_items=lambda: [Item(9, b"<p>Hello there</p>"), Item(1, b"skip")])
        fake_epub = types.SimpleNamespace(read_epub=lambda path: fake_book)
        progress = []
        payloads = []

        process_epub(
            client="client",
            path="/tmp/sample.epub",
            out="out.html",
            fmt="html",
            prompt="Prompt",
            model="gemini-2.5-pro",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            text_chunk_chars=5,
            clean_text_fn=lambda text: text,
            batch_text_chunks_fn=lambda chunks: chunks,
            build_request_cache_key_fn=lambda *args: "key",
            sha256_text_fn=lambda text: text,
            stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
            epub_module=fake_epub,
            page_progress_cb=lambda done, total: progress.append((done, total)),
            resume_from_batch=1,
        )

        self.assertEqual(progress[-1], (3, 3))
        self.assertEqual(len(payloads), 2)

    def test_process_img_removes_enhanced_file_after_stream(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "img.png")
            enh = os.path.join(tmpdir, "img_enhanced.png")
            with open(src, "wb") as fh:
                fh.write(b"src")
            with open(enh, "wb") as fh:
                fh.write(b"enh")

            removed = []
            payloads = []

            process_img(
                client="client",
                path=src,
                out="out.html",
                fmt="html",
                prompt="Prompt",
                model="gpt-4o",
                f_obj=None,
                mem=[],
                log_cb=lambda _msg: None,
                pause_cb=None,
                enhance_image_fn=lambda path: enh,
                build_payload_fn=lambda model, prompt, file_path, mime: ("payload", file_path),
                build_request_cache_key_fn=lambda *args: "key",
                sha256_file_fn=lambda path: f"sha:{os.path.basename(path)}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                remove_fn=lambda path: removed.append(path),
            )

            self.assertEqual(payloads[0], ("payload", enh))
            self.assertEqual(removed, [enh])


if __name__ == "__main__":
    unittest.main()
