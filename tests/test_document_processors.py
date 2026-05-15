import os
import tempfile
import types
import unittest

from chronicle_app.services.document_processors import (
    FITZ_TEXT_EXTENSIONS,
    convert_heic_to_png_for_scan,
    estimate_text_work_units,
    prepare_image_for_scan,
    process_epub,
    process_img,
    process_pptx,
    process_rendered_document,
    process_text,
    supported_files_wildcard,
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

    def test_process_text_reads_html_json_tsv_and_eml_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            samples = {
                "page.html": "<html><script>bad()</script><body><h1>Title</h1><p>Body</p></body></html>",
                "data.jsonl": '{"a":1}\n{"b":2}\n',
                "table.tsv": "A\tB\n1\t2\n",
                "mail.eml": "Subject: Hi\nFrom: a@example.com\nTo: b@example.com\n\nHello body",
            }
            payloads = []
            for name, content in samples.items():
                path = os.path.join(tmpdir, name)
                mode = "wb" if name.endswith(".eml") else "w"
                open_kwargs = {} if mode == "wb" else {"encoding": "utf-8"}
                with open(path, mode, **open_kwargs) as fh:
                    fh.write(content.encode("utf-8") if mode == "wb" else content)
                process_text(
                    client="client",
                    path=path,
                    ext=os.path.splitext(name)[1].lower(),
                    out="out.html",
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
                    build_request_cache_key_fn=lambda *args: "key",
                    sha256_text_fn=lambda text: text,
                    stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
                    generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                    docx_module=None,
                    openpyxl_module=None,
                )

            combined = "\n".join(payload[0] for payload in payloads)
            self.assertIn("Title", combined)
            self.assertNotIn("bad()", combined)
            self.assertIn('{"a":1}', combined)
            self.assertIn("A,B", combined)
            self.assertIn("Subject: Hi", combined)

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

    def test_process_img_converts_heic_before_enhancement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "img.heic")
            staged = os.path.join(tmpdir, "img_staged.png")
            enh = os.path.join(tmpdir, "img_enhanced.png")
            for path in (src, staged, enh):
                with open(path, "wb") as fh:
                    fh.write(os.path.basename(path).encode("utf-8"))

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
                enhance_image_fn=lambda path: enh if path == staged else path,
                build_payload_fn=lambda model, prompt, file_path, mime: ("payload", file_path, mime),
                build_request_cache_key_fn=lambda *args: "key",
                sha256_file_fn=lambda path: f"sha:{os.path.basename(path)}",
                stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
                generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
                remove_fn=lambda path: removed.append(path),
                image_prepare_fn=lambda path, **kwargs: staged,
            )

            self.assertEqual(payloads[0], ("payload", enh, "image/png"))
            self.assertEqual(removed, [enh, staged])

    def test_prepare_image_for_scan_converts_pil_staged_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "img.gif")
            staged = os.path.join(tmpdir, "img_staged.png")
            with open(src, "wb") as fh:
                fh.write(b"gif")

            class FakeImage:
                n_frames = 1
                mode = "P"

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def convert(self, mode):
                    self.mode = mode
                    return self

                def save(self, path, _fmt):
                    with open(path, "wb") as fh:
                        fh.write(b"png")

            fake_image_module = types.SimpleNamespace(open=lambda _path: FakeImage())
            result = prepare_image_for_scan(
                src,
                image_module=fake_image_module,
                mkstemp_fn=lambda prefix, suffix: tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=tmpdir),
            )
            self.assertTrue(result.endswith(".png"))
            self.assertTrue(os.path.exists(result))

    def test_process_rendered_document_renders_pages_to_image_path(self):
        class FakePixmap:
            def tobytes(self, _fmt):
                return b"png-bytes"

        class FakePage:
            def get_pixmap(self, **_kwargs):
                return FakePixmap()

        class FakeDoc:
            def __init__(self):
                self.closed = False

            def __len__(self):
                return 2

            def __getitem__(self, index):
                return FakePage()

            def close(self):
                self.closed = True

        fake_doc = FakeDoc()
        fake_fitz = types.SimpleNamespace(open=lambda path: fake_doc, Matrix=lambda x, y: ("matrix", x, y))
        payloads = []
        progress = []

        process_rendered_document(
            client="client",
            path="/tmp/sample.svg",
            out="out.html",
            fmt="html",
            prompt="Prompt",
            model="gpt-4o",
            f_obj=None,
            mem=[],
            log_cb=lambda _msg: None,
            pause_cb=None,
            page_progress_cb=lambda done, total, source=None: progress.append((done, total, source)),
            fitz_module=fake_fitz,
            enhance_image_fn=lambda path: path,
            build_payload_fn=lambda model, prompt, file_path, mime: ("payload", os.path.exists(file_path), mime),
            build_request_cache_key_fn=lambda *args: "key",
            sha256_file_fn=lambda path: "sha",
            stream_with_cache_fn=lambda key, request_fn, *args, **kwargs: payloads.append(request_fn()),
            generate_retry_fn=lambda client, model, payload, log_cb=None: payload,
        )

        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0], ("payload", True, "image/png"))
        self.assertEqual(progress, [(1, 2, 1), (2, 2, 2)])
        self.assertTrue(fake_doc.closed)

    def test_supported_wildcard_includes_new_formats(self):
        wildcard = supported_files_wildcard()
        for ext in [".html", ".json", ".xml", ".gif", ".avif", ".jp2", ".svg", ".xps", ".cbz", ".mobi", ".fb2", ".eml"]:
            self.assertIn(f"*{ext}", wildcard)

    def test_convert_heic_to_png_for_scan_uses_sips(self):
        calls = []

        class FakeSubprocess:
            @staticmethod
            def run(cmd, capture_output, text, check):
                calls.append(cmd)
                with open(cmd[-1], "wb") as fh:
                    fh.write(b"png")
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "img.heif")
            with open(src, "wb") as fh:
                fh.write(b"heif")

            converted = convert_heic_to_png_for_scan(
                src,
                subprocess_module=FakeSubprocess,
                mkstemp_fn=lambda prefix, suffix: tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=tmpdir),
            )

            self.assertTrue(converted.endswith(".png"))
            self.assertTrue(os.path.exists(converted))
            self.assertEqual(calls[0][:4], ["sips", "-s", "format", "png"])


if __name__ == "__main__":
    unittest.main()
