import unittest

from chronicle_app.services.html_heading_cleanup import _extract_running_header_title
from chronicle_app.services.html_heading_cleanup import _looks_like_heading_text
from chronicle_app.services.html_heading_cleanup import _promote_definition_list_headings
from chronicle_app.services.html_heading_cleanup import _promote_leading_paragraph_headings
from chronicle_app.services.html_heading_cleanup import _promote_list_section_headings
from chronicle_app.services.html_heading_cleanup import _promote_numbered_instruction_headings
from chronicle_app.services.html_heading_cleanup import _promote_sparse_heading_blocks
from chronicle_app.services.html_heading_cleanup import _promote_strong_paragraph_headings


class HtmlHeadingCleanupTests(unittest.TestCase):
    def test_sparse_heading_blocks_promote_two_plain_leaders(self):
        body = """<main id="content" role="main">
<p>WAR DIARY<br>15TH INFANTRY BRIGADE<br>Body line one.</p>
<p>Body line two.</p>
</main>"""

        cleaned = _promote_sparse_heading_blocks(body)

        self.assertIn("<h1>WAR DIARY</h1>", cleaned)
        self.assertIn("<h2>15TH INFANTRY BRIGADE</h2>", cleaned)
        self.assertIn("<p>Body line one.</p>", cleaned)

    def test_leading_paragraph_headings_promote_uppercase_title_and_subhead(self):
        body = """<main id="content" role="main">
<p>APPLICATION FORM</p>
<p>PART A</p>
<p>Body line.</p>
</main>"""

        cleaned = _promote_leading_paragraph_headings(body)

        self.assertIn("<h1>APPLICATION FORM</h1>", cleaned)
        self.assertIn("<h2>PART A</h2>", cleaned)

    def test_running_header_title_is_extracted_for_heading_promotion(self):
        title, remainder = _extract_running_header_title("March 1944 WAR DIARY Daily notes 23")

        self.assertEqual(title, "WAR DIARY")
        self.assertEqual(remainder, "Daily notes")
        self.assertTrue(_looks_like_heading_text("Chapter 3"))
        self.assertFalse(_looks_like_heading_text("This is a normal sentence."))

    def test_list_section_headings_promote_intro_and_first_strong_label(self):
        body = """<main id="content" role="main">
<p>Checklist</p>
<ul><li><strong>Prepare</strong> the file.</li><li><strong>Review</strong> the result.</li></ul>
</main>"""

        cleaned = _promote_list_section_headings(body)

        self.assertIn("<h1>Checklist</h1>", cleaned)
        self.assertIn("<h2>Prepare</h2>", cleaned)

    def test_numbered_instruction_headings_promote_first_step(self):
        body = """<main id="content" role="main">
<p>Instructions</p>
<p>1. Prepare. Gather documents.</p>
<p>2. Review. Check output.</p>
</main>"""

        cleaned = _promote_numbered_instruction_headings(body)

        self.assertIn("<h1>Instructions</h1>", cleaned)
        self.assertIn("<h2>1. Prepare</h2>", cleaned)

    def test_definition_and_strong_paragraph_headings_are_promoted(self):
        definition_body = """<main id="content" role="main">
<p>Glossary</p>
<dl><dt>Term</dt><dd>Definition.</dd></dl>
</main>"""
        strong_body = """<main id="content" role="main">
<p><strong>Title</strong><br>Body.</p>
<p><strong>Section</strong><br>More body.</p>
</main>"""

        definition_cleaned = _promote_definition_list_headings(definition_body)
        strong_cleaned = _promote_strong_paragraph_headings(strong_body)

        self.assertIn("<h1>Glossary</h1>", definition_cleaned)
        self.assertIn("<h2>Term</h2>", definition_cleaned)
        self.assertIn("<h1>Title</h1>", strong_cleaned)
        self.assertIn("<h2>Section</h2>", strong_cleaned)


if __name__ == "__main__":
    unittest.main()
