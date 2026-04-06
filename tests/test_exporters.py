import os
import tempfile
import types
import unittest

from chronicle_app.services.exporters import (
    dispatch_save,
    save_docx,
    save_epub,
    save_pdf,
    should_reject_transformed_content,
)


class ExportersTest(unittest.TestCase):
    def test_save_pdf_falls_back_to_plain_text_when_html_write_fails(self):
        events = []

        class FakePdf:
            def add_page(self):
                events.append("add_page")

            def set_auto_page_break(self, auto=True, margin=15):
                events.append(("page_break", auto, margin))

            def set_font(self, family, size=11):
                events.append(("font", family, size))

            def write_html(self, _content):
                raise RuntimeError("html unsupported")

            def multi_cell(self, width, height, text=""):
                events.append(("multi_cell", width, height, text))

            def output(self, path):
                events.append(("output", path))

        save_pdf("/tmp/out.pdf", "Body", large_print=True, fpdf_cls=FakePdf, sanitize_latin1_fn=lambda text: f"safe:{text}")

        self.assertIn(("font", "Helvetica", 18), events)
        self.assertIn(("multi_cell", 0, 16, "safe:Body"), events)

    def test_save_docx_maps_headings_and_bullets(self):
        class FakeDoc:
            def __init__(self):
                self.calls = []

            def add_heading(self, text, level=1):
                self.calls.append(("heading", level, text))

            def add_paragraph(self, text, style=None):
                self.calls.append(("paragraph", style, text))

            def save(self, path):
                self.calls.append(("save", path))

        fake_doc = FakeDoc()
        fake_docx = types.SimpleNamespace(Document=lambda *args, **kwargs: fake_doc)

        save_docx("/tmp/out.docx", "# Title\n- Bullet\nPlain", docx_module=fake_docx)

        self.assertIn(("heading", 1, "Title"), fake_doc.calls)
        self.assertIn(("paragraph", "List Bullet", "Bullet"), fake_doc.calls)
        self.assertIn(("paragraph", None, "Plain"), fake_doc.calls)

    def test_save_docx_maps_numbered_lists_and_pipe_tables(self):
        class FakeCell:
            def __init__(self):
                self.text = ""

        class FakeTable:
            def __init__(self, rows, cols, calls):
                self._cells = [[FakeCell() for _ in range(cols)] for _ in range(rows)]
                calls.append(("table", rows, cols))

            def cell(self, row, col):
                return self._cells[row][col]

        class FakeDoc:
            def __init__(self):
                self.calls = []

            def add_paragraph(self, text, style=None):
                self.calls.append(("paragraph", style, text))

            def add_table(self, rows, cols):
                return FakeTable(rows, cols, self.calls)

            def save(self, path):
                self.calls.append(("save", path))

        fake_doc = FakeDoc()
        fake_docx = types.SimpleNamespace(Document=lambda *args, **kwargs: fake_doc)

        save_docx(
            "/tmp/out.docx",
            "1. First\n| Name | Value |\n| --- | --- |\n| Alpha | Beta |",
            docx_module=fake_docx,
        )

        self.assertIn(("paragraph", "List Number", "First"), fake_doc.calls)
        self.assertIn(("table", 2, 2), fake_doc.calls)

    def test_save_docx_honors_page_break_marker(self):
        class FakeDoc:
            def __init__(self):
                self.calls = []

            def add_heading(self, text, level=1):
                self.calls.append(("heading", level, text))

            def add_page_break(self):
                self.calls.append(("page_break",))

            def add_paragraph(self, text, style=None):
                self.calls.append(("paragraph", style, text))

            def save(self, path):
                self.calls.append(("save", path))

        fake_doc = FakeDoc()
        fake_docx = types.SimpleNamespace(Document=lambda *args, **kwargs: fake_doc)

        save_docx("/tmp/out.docx", "# Title\n[[PAGE BREAK]]\nPlain", docx_module=fake_docx)

        self.assertIn(("page_break",), fake_doc.calls)
        self.assertIn(("paragraph", None, "Plain"), fake_doc.calls)

    def test_save_epub_creates_chapters_from_h2_breaks(self):
        written = {}

        class FakeBook:
            def __init__(self):
                self.items = []
                self.spine = []

            def set_identifier(self, value):
                self.identifier = value

            def set_title(self, value):
                self.title = value

            def set_language(self, value):
                self.language = value

            def add_item(self, item):
                self.items.append(item)

        class FakeHtml:
            def __init__(self, title, file_name, lang):
                self.title = title
                self.file_name = file_name
                self.lang = lang
                self.content = ""

        fake_epub = types.SimpleNamespace(
            EpubBook=FakeBook,
            EpubHtml=FakeHtml,
            EpubNcx=lambda: "ncx",
            EpubNav=lambda: "nav",
            write_epub=lambda path, book, opts: written.update({"path": path, "book": book, "opts": opts}),
        )

        save_epub(
            "/tmp/out.epub",
            "Book",
            "<h2>One</h2><p>A</p><h2>Two</h2><p>B</p>",
            lang_code="en",
            text_dir="ltr",
            epub_module=fake_epub,
            time_module=types.SimpleNamespace(time=lambda: 1000),
        )

        self.assertEqual(written["path"], "/tmp/out.epub")
        html_items = [item for item in written["book"].items if isinstance(item, FakeHtml)]
        self.assertEqual(len(html_items), 2)
        self.assertEqual(html_items[0].title, "One")
        self.assertEqual(html_items[1].title, "Two")

    def test_dispatch_save_writes_json_and_csv_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "out.json")
            csv_path = os.path.join(tmpdir, "out.csv")
            base_cfg = {
                "modernize_punctuation": False,
                "unit_conversion": False,
                "abbrev_expansion": False,
                "merge_files": False,
            }

            dispatch_save(
                {**base_cfg, "format_type": "json"},
                json_path,
                ['```json\n{"a":1}\n```'],
                "Title",
                sanitize_model_output_fn=lambda content, fmt, *_args: content,
                apply_modern_punctuation_fn=lambda content: content,
                apply_modern_currency_fn=lambda content: content,
                apply_expanded_abbreviations_fn=lambda content: content,
                strip_synthetic_page_filename_headings_fn=lambda content, fmt: content,
                get_output_lang_code_fn=lambda cfg: "en",
                get_output_text_direction_fn=lambda cfg: "ltr",
                save_docx_fn=lambda *args, **kwargs: None,
                save_pdf_fn=lambda *args, **kwargs: None,
                save_epub_fn=lambda *args, **kwargs: None,
            )

            dispatch_save(
                {**base_cfg, "format_type": "csv"},
                csv_path,
                ["```csv\nA,B\n1,2\n```"],
                "Title",
                sanitize_model_output_fn=lambda content, fmt, *_args: content,
                apply_modern_punctuation_fn=lambda content: content,
                apply_modern_currency_fn=lambda content: content,
                apply_expanded_abbreviations_fn=lambda content: content,
                strip_synthetic_page_filename_headings_fn=lambda content, fmt: content,
                get_output_lang_code_fn=lambda cfg: "en",
                get_output_text_direction_fn=lambda cfg: "ltr",
                save_docx_fn=lambda *args, **kwargs: None,
                save_pdf_fn=lambda *args, **kwargs: None,
                save_epub_fn=lambda *args, **kwargs: None,
            )

            with open(json_path, "r", encoding="utf-8") as fh:
                json_content = fh.read()
            with open(csv_path, "r", encoding="utf-8") as fh:
                csv_content = fh.read()
            self.assertIn('"a": 1', json_content)
            self.assertEqual(csv_content, "A,B\n1,2")

    def test_dispatch_save_preserves_raw_content_when_transform_shrinks_too_far(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = os.path.join(tmpdir, "out.txt")
            raw = ("alpha beta gamma delta\n" * 4000).strip()

            dispatch_save(
                {"format_type": "csv", "modernize_punctuation": False, "unit_conversion": False, "abbrev_expansion": False, "merge_files": False},
                txt_path,
                [raw],
                "Title",
                sanitize_model_output_fn=lambda content, fmt, *_args: "tiny",
                apply_modern_punctuation_fn=lambda content: content,
                apply_modern_currency_fn=lambda content: content,
                apply_expanded_abbreviations_fn=lambda content: content,
                strip_synthetic_page_filename_headings_fn=lambda content, fmt: content,
                get_output_lang_code_fn=lambda cfg: "en",
                get_output_text_direction_fn=lambda cfg: "ltr",
                save_docx_fn=lambda *args, **kwargs: None,
                save_pdf_fn=lambda *args, **kwargs: None,
                save_epub_fn=lambda *args, **kwargs: None,
            )

            with open(txt_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.assertEqual(content, raw)

    def test_should_reject_transformed_content_flags_large_visible_text_drop(self):
        raw = ("alpha beta gamma delta\n" * 4000).strip()
        self.assertTrue(should_reject_transformed_content(raw, "tiny", fmt="csv"))


if __name__ == "__main__":
    unittest.main()
