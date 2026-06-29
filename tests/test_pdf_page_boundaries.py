import unittest

from chronicle_app.services.pdf_page_boundaries import ensure_source_page_boundary
from chronicle_app.services.pdf_page_boundaries import output_format_keeps_page_boundaries


class PdfPageBoundaryTest(unittest.TestCase):
    def test_html_output_gets_page_heading_wrapper(self):
        rendered = ensure_source_page_boundary("<article><p>Body.</p></article>", 3, fmt="html")

        self.assertIn("<section>", rendered)
        self.assertIn("<h2>Page 3</h2>", rendered)
        self.assertIn("<article><p>Body.</p></article>", rendered)

    def test_html_existing_section_receives_heading_inside_section(self):
        rendered = ensure_source_page_boundary("<section><article><p>Body.</p></article></section>", 4, fmt="html")

        self.assertTrue(rendered.startswith("<section><h2>Page 4</h2>"))

    def test_existing_html_page_heading_is_not_duplicated(self):
        raw = "<section><h2>Page 5</h2><p>Body.</p></section>"

        self.assertEqual(ensure_source_page_boundary(raw, 5, fmt="html"), raw)

    def test_text_like_output_gets_plain_page_boundary(self):
        rendered = ensure_source_page_boundary("Body text.", 2, fmt="md")

        self.assertEqual(rendered, "Page 2\n\nBody text.")

    def test_json_does_not_get_page_boundary(self):
        raw = '{"body": "text"}'

        self.assertFalse(output_format_keeps_page_boundaries("json"))
        self.assertEqual(ensure_source_page_boundary(raw, 1, fmt="json"), raw)


if __name__ == "__main__":
    unittest.main()
