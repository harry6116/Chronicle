import unittest

from tools.comic_accuracy_audit import audit_reference, extract_panels


class ComicAccuracyAuditTest(unittest.TestCase):
    def test_panel_reference_rejects_invented_dialogue_and_shifted_numbering(self):
        reference = {"panels": [{"number": 1, "excerpts": ["Register here"]},
                                {"number": 2, "excerpts": ["Go to sleep"]}]}
        old = '<main><h2>Panel 1</h2><p>Buy a theatre ticket</p><h2>Panel 2</h2><p>Register here</p></main>'
        result = audit_reference(old, reference)
        self.assertFalse(result["reference_checks_passed"])
        self.assertEqual(len(result["missing_excerpts"]), 2)
        corrected = '<main><h2>Panel 1</h2><p>Speech: REGISTER HERE!</p><h2>Panel 2</h2><p>Go to sleep.</p></main>'
        self.assertTrue(audit_reference(corrected, reference)["reference_checks_passed"])

    def test_navigation_footer_and_descriptions_cannot_supply_dialogue(self):
        html = '''<nav><h2>Panel 99</h2><p>Register here</p></nav>
        <main><h2>Panel 1</h2><p>[Image Description: Register here]</p>
        <footer>Register here</footer></main>'''
        panels = extract_panels(html)
        self.assertEqual([p["number"] for p in panels], [1])
        self.assertEqual(panels[0]["transcription"], "")
        self.assertFalse(audit_reference(html, {"panels": [{"number": 1, "excerpts": ["Register here"]}]})["reference_checks_passed"])

    def test_duplicate_extra_or_reordered_panels_fail_even_with_all_excerpts(self):
        reference = {"panels": [{"number": 1, "excerpts": ["Hello"]}, {"number": 2, "excerpts": ["Goodbye"]}]}
        for numbers in ([2, 1], [1, 2, 2], [1, 2, 3]):
            html = ''.join(f'<h2>Panel {n}</h2><p>Hello Goodbye</p>' for n in numbers)
            self.assertFalse(audit_reference(html, reference)["reference_checks_passed"])

    def test_reference_validation_and_word_boundaries(self):
        with self.assertRaises(ValueError):
            audit_reference('', {"panels": []})
        with self.assertRaises(ValueError):
            audit_reference('', {"panels": [{"number": 1, "excerpts": []}]})
        result = audit_reference('<h2>Panel 1</h2><p>sleeping</p>', {"panels": [{"number": 1, "excerpts": ["sleep"]}]})
        self.assertFalse(result["reference_checks_passed"])
