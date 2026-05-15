import unittest

from chronicle_app.services.nla_newspaper import (
    contains_nla_ocr_marker,
    is_nla_newspaper_source_path,
    should_skip_cleanup_for_nla_ocr_output,
    should_skip_pdf_textlayer_audit_for_nla_output,
    should_skip_pdf_textlayer_audit_for_nla_source,
)


class NlaNewspaperTests(unittest.TestCase):
    def test_detects_nla_ocr_markers_in_text_and_html(self):
        self.assertTrue(contains_nla_ocr_marker("National Library of Australia"))
        self.assertTrue(contains_nla_ocr_marker("<p>nla.gov.au/nla.news-page</p>", strip_html=True))
        self.assertFalse(contains_nla_ocr_marker("ordinary newspaper text"))

    def test_detects_nla_newspaper_source_path(self):
        self.assertTrue(is_nla_newspaper_source_path("/tmp/nla.news-issue108507.pdf"))
        self.assertTrue(is_nla_newspaper_source_path("/tmp/nla.news_issue108507.pdf"))
        self.assertFalse(is_nla_newspaper_source_path("/tmp/other.pdf"))

    def test_audit_source_skip_requires_pdf_newspaper_and_nla_name(self):
        cfg = {"doc_profile": "newspaper"}
        self.assertTrue(
            should_skip_pdf_textlayer_audit_for_nla_source(
                ext=".pdf",
                cfg=cfg,
                path="/tmp/nla.news-issue108507.pdf",
            )
        )
        self.assertFalse(
            should_skip_pdf_textlayer_audit_for_nla_source(
                ext=".pdf",
                cfg={"doc_profile": "legal"},
                path="/tmp/nla.news-issue108507.pdf",
            )
        )
        self.assertFalse(
            should_skip_pdf_textlayer_audit_for_nla_source(
                ext=".txt",
                cfg=cfg,
                path="/tmp/nla.news-issue108507.txt",
            )
        )

    def test_large_output_skips_require_newspaper_profile_and_marker(self):
        nla_text = "National Library of Australia " + ("x" * 100_000)
        self.assertTrue(
            should_skip_pdf_textlayer_audit_for_nla_output(
                ext=".pdf",
                cfg={"doc_profile": "newspaper"},
                extracted_text=nla_text,
            )
        )
        self.assertFalse(
            should_skip_pdf_textlayer_audit_for_nla_output(
                ext=".pdf",
                cfg={"doc_profile": "standard"},
                extracted_text=nla_text,
            )
        )
        self.assertTrue(
            should_skip_cleanup_for_nla_ocr_output(
                nla_text,
                fmt="html",
                job_cfg={"doc_profile": "newspaper"},
            )
        )
        self.assertFalse(
            should_skip_cleanup_for_nla_ocr_output(
                "National Library of Australia short",
                fmt="html",
                job_cfg={"doc_profile": "newspaper"},
            )
        )


if __name__ == "__main__":
    unittest.main()
