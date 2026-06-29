import unittest

from chronicle_app.services.output_cleanup import _collapse_inline_image_sources
from chronicle_app.services.output_cleanup import _convert_markdown_headings_inside_html
from chronicle_app.services.output_cleanup import _dedupe_adjacent_html_paragraph_blocks
from chronicle_app.services.output_cleanup import _strip_broken_placeholder_images_html
from chronicle_app.services.output_cleanup import _strip_html_page_wrapper_noise
from chronicle_app.services.output_cleanup import strip_internal_chronicle_output_labels


class OutputCleanupTests(unittest.TestCase):
    def test_html_wrapper_noise_and_markdown_headings_are_cleaned(self):
        raw = "<!-- Page wrapper -->\n## Page 3\n# Real Heading\n<p>Body</p>"

        cleaned = _convert_markdown_headings_inside_html(_strip_html_page_wrapper_noise(raw))

        self.assertNotIn("Page wrapper", cleaned)
        self.assertNotIn("## Page 3", cleaned)
        self.assertIn("<h1>Real Heading</h1>", cleaned)

    def test_image_placeholders_and_inline_payloads_are_collapsed(self):
        payload = "a" * 300
        raw = f'<figure><img src="IMAGE_PLACEHOLDER_1"></figure><img src="data:image/png;base64,{payload}">'

        cleaned = _strip_broken_placeholder_images_html(_collapse_inline_image_sources(raw))

        self.assertNotIn("IMAGE_PLACEHOLDER", cleaned)
        self.assertIn('src="about:blank"', cleaned)

    def test_internal_labels_are_stripped_and_page_fallbacks_normalized(self):
        raw = """[Gemini Image] internal status
<h2 data-strip="1">Source page 4, strip 2</h2>
<h2 data-source-page="4">Source page 4, text layer fallback</h2>
<p class="chronicle-note">Body</p>"""

        cleaned = strip_internal_chronicle_output_labels(raw, "html")

        self.assertNotIn("Gemini Image", cleaned)
        self.assertNotIn("data-strip", cleaned)
        self.assertNotIn("text layer fallback", cleaned)
        self.assertIn(">Page 4<", cleaned)

    def test_adjacent_duplicate_paragraph_blocks_are_deduped(self):
        raw = "<p>A</p>\n<p>B</p>\n<p>A</p>\n<p>B</p>\n<p>C</p>"

        cleaned = _dedupe_adjacent_html_paragraph_blocks(raw)

        self.assertEqual(cleaned.count("<p>A</p>"), 1)
        self.assertEqual(cleaned.count("<p>B</p>"), 1)
        self.assertEqual(cleaned.count("<p>C</p>"), 1)


if __name__ == "__main__":
    unittest.main()
