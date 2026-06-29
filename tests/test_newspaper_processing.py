import tempfile
import unittest
from pathlib import Path

from chronicle_app.services.newspaper_processing import apply_newspaper_html_safety_fallback
from chronicle_app.services.newspaper_processing import build_newspaper_safety_notice
from chronicle_app.services.newspaper_processing import recover_newspaper_header_citation
from chronicle_app.services.newspaper_processing import recover_source_attribution_footer


class NewspaperProcessingTest(unittest.TestCase):
    def test_safety_notice_is_format_specific(self):
        self.assertIn("Newspaper Safety Fallback", build_newspaper_safety_notice("html"))
        self.assertTrue(build_newspaper_safety_notice("txt").startswith("[Note:"))
        self.assertEqual(build_newspaper_safety_notice("json"), "")

    def test_safety_fallback_simplifies_div_layout(self):
        raw = '<div class="outer"><div id="inner"><p>Body</p></div></div>' * 40

        cleaned = apply_newspaper_html_safety_fallback(raw, "html", "newspaper", max_chars=200)

        self.assertIn("Newspaper safety fallback", cleaned)
        body_without_notice = cleaned.split("</div>", 1)[-1]
        self.assertNotIn("<div", body_without_notice.lower())
        self.assertIn("<section>", cleaned.lower())

    def test_header_citation_uses_pdf_title_metadata(self):
        class FakePage:
            def extract_text(self):
                return "National Library of Australia http://nla.gov.au/nla.news-article123"

        class FakeReader:
            metadata = {"/Title": "Example Herald, Monday 1 January 1900, page 3"}
            pages = [FakePage()]

            def __init__(self, _path):
                pass

        raw = '<main><article><h1>Example Story</h1></article></main>'

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "article.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_newspaper_header_citation(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=FakeReader,
            )

        self.assertIn("<header><cite>Example Herald, Monday 1 January 1900, page 3</cite></header>", cleaned)

    def test_source_footer_infers_internet_archive_from_filename(self):
        class FakePage:
            def extract_text(self):
                return "Scanned newspaper text."

        class FakeReader:
            metadata = {}
            pages = [FakePage()]

            def __init__(self, _path):
                pass

        raw = "<main><h1>Example</h1></main>"

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "cawsahs_000195_subset_2pages.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            cleaned = recover_source_attribution_footer(
                raw,
                "html",
                "newspaper",
                source_path=str(pdf_path),
                pdf_reader_cls=FakeReader,
            )

        self.assertIn("<footer><cite>Internet Archive</cite>", cleaned)
        self.assertIn("https://archive.org/details/cawsahs_000195", cleaned)


if __name__ == "__main__":
    unittest.main()
