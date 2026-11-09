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


class OriginalReadingAidTests(unittest.TestCase):
    def test_currency_aid_retains_source_and_is_idempotent(self):
        source = '<p>Paid £1/2/- and 2d.</p><code>3d</code>'
        once = apply_modern_currency(source, preserve_original=True)
        self.assertIn('£1/2/- [1 pounds, 2 shillings]', once)
        self.assertIn('2d. [2 pence]', once)
        self.assertIn('<code>3d</code>', once)
        self.assertEqual(apply_modern_currency(once, preserve_original=True), once)

    def test_abbreviation_aid_does_not_expand_existing_aids_or_protected_tokens(self):
        source = '<p>Capt. [Captain] and Pte Smith at HQ. A.D.S.S. J.B.C.</p>'
        once = apply_expanded_abbreviations(source, 'military', preserve_original=True)
        self.assertIn('Capt. [Captain]', once)
        self.assertIn('Pte [Private] Smith', once)
        self.assertIn('HQ. A.D.S.S. J.B.C.', once)
        self.assertEqual(apply_expanded_abbreviations(once, 'military', preserve_original=True), once)

    def test_clinical_shorthand_is_protected_even_with_reading_aids(self):
        source = '<p>BP 120/80, OD, q.d. and PRN.</p>'
        self.assertEqual(apply_expanded_abbreviations(source, 'medical', preserve_original=True), source)

    def test_frontends_choose_original_preserving_aids(self):
        import chronicle_runtime
        self.assertEqual(chronicle_runtime.apply_expanded_abbreviations('Pte Smith', 'military'), 'Pte [Private] Smith')
        self.assertEqual(chronicle_runtime.apply_modern_currency('2d.'), '2d. [2 pence]')

    def test_reading_aids_do_not_reinterpret_decimal_or_partial_currency(self):
        source = '£5.50, £5,000 and £5/10/6; ID2d and A.D.S.S./Forms/C.'
        self.assertEqual(apply_modern_currency(source, preserve_original=True), source)

    def test_frontend_punctuation_cleanup_preserves_source_word_hyphens(self):
        import chronicle_runtime
        self.assertEqual(chronicle_runtime.apply_modern_punctuation('King-road. Mrs. X.- Next'), 'King-road. Mrs. X. Next')

    def test_compound_rank_aids_do_not_overlap_or_expand_twice(self):
        source = 'Lt. Col. Smith and Maj. Gen. Jones.'
        expected = 'Lt. Col. [Lieutenant Colonel] Smith and Maj. Gen. [Major General] Jones.'
        once = apply_expanded_abbreviations(source, 'military', preserve_original=True)
        self.assertEqual(once, expected)
        self.assertEqual(apply_expanded_abbreviations(once, 'military', preserve_original=True), expected)
