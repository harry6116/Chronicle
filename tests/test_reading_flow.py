from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock
from zipfile import ZipFile
from xml.etree import ElementTree as XML

from chronicle_app.services.document_preflight import inspect_pdf
from chronicle_app.services.output_quality import analyze_output_quality
from chronicle_app.services.run_start_runtime import find_missing_api_key_requirement
from chronicle_app.services.session_runtime import build_project_payload, read_project_payload, save_active_session_file
from chronicle_app.services.webpage_article import build_article
from chronicle_app.services.worker_finalize_runtime import finalize_single_output


class ReadingFlowTests(unittest.TestCase):
    def test_streamed_html_obeys_print_page_preference_without_optional_cleanup(self):
        for preserve in (False, True):
            with self.subTest(preserve=preserve), TemporaryDirectory() as directory:
                pending = Path(directory) / "pending.html"
                final = Path(directory) / "final.html"
                with pending.open("w", encoding="utf-8") as stream:
                    stream.write('<html><body><main><section><h2>Page 1</h2>'
                                 '<h1>Article title</h1><h2>Page 2 of the report</h2>'
                                 '<p>Discussed on page 1.</p></section></main>')
                    finalize_single_output(
                        job_cfg={"preserve_original_page_numbers": preserve, "post_save_cleanup": False},
                        temp_path=str(pending), memory=None, base="", file_obj=stream, fmt="html",
                        output_path=str(final), dispatch_save_fn=None,
                        write_footer_fn=lambda stream, _: stream.write("</body></html>"),
                        cleanup_output_text_fn=None, log_cb=lambda _: None,
                    )
                rendered = final.read_text()
                self.assertEqual("<h2>Page 1</h2>" in rendered, preserve)
                self.assertIn("Page 2 of the report", rendered)
                self.assertIn("Discussed on page 1.", rendered)

    def test_single_document_wrapper_is_valid(self):
        self.assertTrue(analyze_output_quality(
            "<!doctype html><html><head><title>Sample</title></head><body><p>Text</p></body></html>",
            fmt="html",
        )["ok"])

    def test_article_excludes_web_furniture_and_preserves_second_page(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is required for the local article workflow")
        with fitz.open() as source:
            first = source.new_page(width=600, height=2000)
            first.insert_text((80, 100), "Example article heading", fontsize=25, fontname="hebo")
            first.insert_text((80, 135), "By Example Author", fontsize=10)
            first.insert_text((460, 175), "Listen Live", fontsize=12)
            first.insert_text((80, 185), "The first source paragraph contains enough words to be readable.", fontsize=12)
            first.insert_text((80, 215), "Next section", fontsize=17, fontname="hebo")
            first.insert_text((80, 240), "The next section describes the evidence from the first source.", fontsize=12)
            first.insert_text((80, 280), "The main column continues with details below the navigation.", fontsize=12)
            second = source.new_page(width=600, height=450)
            second.insert_text((80, 55), "The article continues onto the next page before the list of links.", fontsize=12)
            second.insert_text((80, 100), "More in Science", fontsize=17, fontname="hebo")
            second.insert_text((80, 145), "A different story is linked here for other interested readers.", fontsize=12)
            evidence = inspect_pdf(source, [0, 1])
            self.assertEqual(evidence.tall_pages, (1,))
            self.assertTrue(evidence.webpage)
            result = build_article(source, [0, 1])
        self.assertEqual(result["source_pages"], [1, 2])
        self.assertEqual(result["end_label"], "More in Science")
        self.assertIn("<h2>Next section</h2>", result["html"])
        self.assertIn("The article continues onto the next page", result["html"])
        self.assertNotIn("A different story", result["html"])
        self.assertNotIn("Listen Live", result["html"])
        self.assertNotIn(">Source page 1<", result["html"])

    def test_article_only_job_does_not_need_a_provider_key(self):
        has_key = Mock(return_value=False)
        self.assertIsNone(find_missing_api_key_requirement(
            [{"path": "source.pdf", "settings": {"webpage_reading_mode": "article"}}],
            normalize_row_settings_fn=lambda row: row["settings"], model_from_label_fn=None,
            label_from_model_fn=None, has_vendor_key_fn=has_key,
        ))
        has_key.assert_not_called()

    def test_project_round_trip_keeps_review_state_and_excludes_credentials(self):
        from threading import Lock
        payload = build_project_payload(
            {"api_key": "disposable", "dest_mode": 0},
            [{"path": "source.pdf", "status": "Done", "review_workbench_path": "review.html",
              "settings": {"webpage_reading_mode": "article", "token": "disposable"}}],
            row_setting_keys=("webpage_reading_mode",),
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "Example.chronicle-project"
            save_active_session_file(str(path), payload, session_lock=Lock())
            rows, settings = read_project_payload(path)
            self.assertNotIn("disposable", path.read_text())
        self.assertEqual(rows[0]["review_workbench_path"], "review.html")
        self.assertEqual(rows[0]["settings"]["webpage_reading_mode"], "article")
        self.assertEqual(settings, {"dest_mode": 0})

    def test_epub_navigation_has_links_to_readable_chapters(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reading.epub"
            # Some suites import a stub EbookLib for GUI contract tests. Verify
            # the actual archive with a fresh interpreter and real dependency.
            result = subprocess.run(
                [sys.executable, "-c",
                 "import sys; from ebooklib import epub; "
                 "from chronicle_app.services.exporters import save_epub; "
                 "save_epub(sys.argv[1], 'Article', sys.argv[2], epub_module=epub)",
                 str(path), "<article><h1>Headline</h1><p>Intro</p>"
                 "<h2>First section</h2><p>First body</p><h2>Second section</h2>"
                 "<p>Second body</p></article>"],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20,
            )
            if "No module named 'ebooklib'" in result.stderr:
                self.skipTest("EbookLib is required for EPUB export")
            self.assertEqual(result.returncode, 0, result.stderr)
            with ZipFile(path) as package:
                nav = XML.fromstring(package.read("EPUB/nav.xhtml"))
                ns = {"x": "http://www.w3.org/1999/xhtml"}
                anchors = nav.findall(".//x:a", ns)
                self.assertEqual([link.text for link in anchors], ["Headline", "First section", "Second section"])
                for link in anchors:
                    chapter = XML.fromstring(package.read("EPUB/" + link.attrib["href"]))
                    self.assertEqual(len(chapter.findall(".//x:h1", ns)), 1)
