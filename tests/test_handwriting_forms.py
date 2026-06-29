import unittest

from chronicle_app.services.handwriting_forms import apply_handwriting_audit_flag
from chronicle_app.services.handwriting_forms import normalize_form_semantics_html
from chronicle_app.services.handwriting_forms import should_flag_handwriting_audit


class HandwritingFormsTests(unittest.TestCase):
    def test_handwriting_audit_requires_archival_clean_long_text(self):
        html = "<p>" + ("word " * 50) + "</p>"

        self.assertTrue(should_flag_handwriting_audit(html, "html", "archival"))
        self.assertFalse(should_flag_handwriting_audit(html, "html", "medical"))
        self.assertFalse(should_flag_handwriting_audit("<p>short note</p>", "html", "archival"))
        self.assertFalse(should_flag_handwriting_audit("<p>" + ("word " * 50) + "[Unclear Word: test]</p>", "html", "archival"))

    def test_handwriting_audit_injects_html_note_inside_main_once(self):
        doc = """<!DOCTYPE html>
<html lang="und" dir="auto">
<body>
<main id="content" role="main">
<p>""" + ("word " * 50) + """</p>
</main>
</body>
</html>"""

        flagged = apply_handwriting_audit_flag(doc, "html", "archival", whole_document=True)
        flagged_again = apply_handwriting_audit_flag(flagged, "html", "archival", whole_document=True)

        self.assertIn('aria-label="Transcription Audit Flag"', flagged)
        self.assertEqual(flagged_again.count('aria-label="Transcription Audit Flag"'), 1)
        self.assertLess(flagged.index('aria-label="Transcription Audit Flag"'), flagged.index("<p>word"))

    def test_form_semantics_normalizes_inputs_and_yes_no_controls(self):
        body = """
<p>[Checkbox: Empty] No</p>
<p>[Checkbox: Selected] Yes</p>
<p>Name <input type="text"/></p>
<p>Agree <input type="checkbox" checked/></p>
<p>Choice <input type="radio"/></p>
<textarea>prefilled</textarea>
"""

        cleaned = normalize_form_semantics_html(body)

        self.assertIn("[Radio Button: Empty] No", cleaned)
        self.assertIn("[Radio Button: Selected] Yes", cleaned)
        self.assertIn("[Text Field: Empty]", cleaned)
        self.assertIn("[Checkbox: Selected]", cleaned)
        self.assertIn("[Radio Button: Empty]", cleaned)
        self.assertNotIn("<textarea", cleaned.lower())


if __name__ == "__main__":
    unittest.main()
