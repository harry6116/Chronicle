import unittest

from chronicle_app.services.dense_newspaper_rendering import (
    dense_newspaper_visible_chars,
    render_newspaper_ocr_line_as_html,
    render_plain_newspaper_ocr_as_html,
    stream_plain_newspaper_ocr_as_html,
)


class DenseNewspaperRenderingTest(unittest.TestCase):
    def test_render_line_promotes_short_uppercase_heading(self):
        self.assertEqual(render_newspaper_ocr_line_as_html("LOCAL NEWS:"), "<h3>LOCAL NEWS</h3>\n")

    def test_render_plain_ocr_wraps_page_and_paragraphs(self):
        rendered = render_plain_newspaper_ocr_as_html("THE AGE\nStory text", 3, None)

        self.assertIn("<h2>Page 3</h2>", rendered)
        self.assertIn("<h3>THE AGE</h3>", rendered)
        self.assertIn("<p>Story text</p>", rendered)

    def test_stream_plain_ocr_handles_split_lines(self):
        streamed = "".join(stream_plain_newspaper_ocr_as_html(["HEAD", "LINE\nBody"], 4, 1))

        self.assertIn("<h2>Page 4</h2>", streamed)
        self.assertIn("<h3>HEADLINE</h3>", streamed)
        self.assertIn("</section>", streamed)

    def test_visible_chars_ignores_page_heading_markup(self):
        self.assertEqual(dense_newspaper_visible_chars("<h2>Page 8</h2><p>Readable text</p>", 8), 13)


if __name__ == "__main__":
    unittest.main()
