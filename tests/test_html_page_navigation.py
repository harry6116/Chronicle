import unittest

from chronicle_core import normalize_streamed_html_document
from chronicle_app.services.html_page_navigation import inject_page_navigation
from chronicle_app.services.html_page_navigation import inject_single_page_boundary_from_metadata


class HtmlPageNavigationTest(unittest.TestCase):
    def test_injects_page_navigation_and_heading_ids(self):
        raw = (
            '<main><h1 id="document-title">Issue</h1>'
            "<h2>Page 1</h2><p>One.</p>"
            "<h2>Source Page 2</h2><p>Two.</p></main>"
        )

        cleaned = inject_page_navigation(raw)

        self.assertIn('aria-label="Page navigation"', cleaned)
        self.assertIn('id="page-1"', cleaned)
        self.assertIn('id="page-2"', cleaned)
        self.assertIn('href="#page-1"', cleaned)
        self.assertIn('href="#page-2"', cleaned)

    def test_single_page_boundary_from_nla_url_uses_page_one_label(self):
        raw = '<main><h1 id="document-title">Article</h1><footer>https://nla.gov.au/nla.news-page12345</footer></main>'

        cleaned = inject_single_page_boundary_from_metadata(raw)

        self.assertIn("<h2>Page 1</h2>", cleaned)
        self.assertLess(cleaned.index("<h2>Page 1</h2>"), cleaned.index("<footer>"))

    def test_existing_page_navigation_is_left_alone(self):
        raw = '<main><nav aria-label="Page navigation"></nav><h2>Page 1</h2><h2>Page 2</h2></main>'

        self.assertEqual(inject_page_navigation(raw), raw)

    def test_single_page_heading_does_not_create_page_navigation(self):
        raw = '<main><h1 id="document-title">Manual</h1><h2>Page 1</h2><p>Only page.</p></main>'

        cleaned = inject_page_navigation(raw)

        self.assertNotIn('aria-label="Page navigation"', cleaned)
        self.assertNotIn('id="page-1"', cleaned)

    def test_normalizer_removes_page_headings_when_page_references_are_disabled(self):
        raw = """<!DOCTYPE html>
<html><body><main id="content">
<h1 id="document-title">Report</h1>
<h2>Page 1</h2><p>One.</p>
<h2>Source Page 2</h2><p>Two.</p>
<h2>Findings</h2><p>Body.</p>
</main></body></html>"""

        cleaned = normalize_streamed_html_document(
            raw,
            insert_page_navigation=True,
            preserve_page_headings=False,
        )

        self.assertNotIn(">Page 1</h2>", cleaned)
        self.assertNotIn(">Source Page 2</h2>", cleaned)
        self.assertNotIn('aria-label="Page navigation"', cleaned)
        self.assertIn('aria-label="Table of Contents"', cleaned)
        self.assertIn(">Findings</h2>", cleaned)

    def test_normalizer_keeps_top_toc_when_page_links_are_enabled(self):
        raw = """<!DOCTYPE html>
<html><body><main id="content">
<h1 id="document-title">Single Heading Report</h1>
<p>Body.</p>
</main></body></html>"""

        cleaned = normalize_streamed_html_document(
            raw,
            insert_page_navigation=True,
            preserve_page_headings=False,
        )

        self.assertIn('aria-label="Table of Contents"', cleaned)
        self.assertIn('href="#document-title"', cleaned)


if __name__ == "__main__":
    unittest.main()
