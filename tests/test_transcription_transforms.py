import unittest

from chronicle_core import apply_expanded_abbreviations, apply_modern_currency, apply_modern_punctuation


class TranscriptionTransformsTest(unittest.TestCase):
    def test_currency_changes_text_without_damaging_css_attributes_or_code(self):
        source = '<style>a {color:#1d4ed8}</style><p id="2d" title="3d">Paid 2d. and £1/2/-.</p><code>3d</code><!-- 4d -->'
        result = apply_modern_currency(source)
        self.assertIn('<style>a {color:#1d4ed8}</style>', result)
        self.assertIn('id="2d" title="3d"', result)
        self.assertIn('Paid 2 pence and 1 pounds, 2 shillings.', result)
        self.assertIn('<code>3d</code><!-- 4d -->', result)

    def test_production_identifiers_are_not_money_or_military_units(self):
        source = '<p>1875 Wt. W593/826 1,000,000 4/15 J.B.C. &amp; A. A.D.S.S./Forms/C. 2118.</p>'
        for transform in (apply_modern_currency, apply_expanded_abbreviations):
            self.assertEqual(transform(source), source)
        self.assertEqual(apply_expanded_abbreviations('A.D.S.S. number 2118'), 'A.D.S.S. number 2118')
        self.assertEqual(apply_expanded_abbreviations('ADS received Pte Smith.'), 'Advanced Dressing Station received Private Smith.')

    def test_abbreviations_preserve_code_and_styles_but_expand_prose(self):
        source = '<script>const Bde = "HQ";</script><style>.Bde {}</style><p>Capt. at HQ.</p><pre>HQ</pre>'
        result = apply_expanded_abbreviations(source)
        self.assertIn('<script>const Bde = "HQ";</script><style>.Bde {}</style>', result)
        self.assertIn('<p>Captain at Headquarters</p>', result)
        self.assertIn('<pre>HQ</pre>', result)

    def test_punctuation_preserves_markup_and_handles_plain_text(self):
        source = '<a href="https://example.test/king-road">King-road</a><code>alpha.-beta</code>'
        self.assertEqual(apply_modern_punctuation(source), '<a href="https://example.test/king-road">King Road</a><code>alpha.-beta</code>')
        self.assertEqual(apply_modern_currency('Paid 2d. < 3d.'), 'Paid 2 pence < 3 pence')

    def test_reading_rules_preserve_identifiers_and_distinguish_page_continuations(self):
        from chronicle_app.services.prompting import build_prompt
        def prompt(profile):
            return build_prompt({'doc_profile':profile,'abbrev_expansion':True}, translation_targets=[], rtl_language_codes=set(), format_type='html')
        self.assertIn('Preserve printer imprints', prompt('military'))
        self.assertIn('cancelled title choices', prompt('military'))
        self.assertIn('[Struck through: Unclear Word]', prompt('military'))
        self.assertIn('do not invent its continuation', prompt('handwritten'))
