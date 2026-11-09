import unittest

from chronicle_app.config import PROFILE_PRESETS
from chronicle_app.services.prompting import build_prompt
from chronicle_app.services.book_cleanup import _apply_book_plain_text_cleanup, _normalize_book_page_markers


def prompt(profile, fmt='html', **settings):
    cfg = dict(PROFILE_PRESETS[profile], doc_profile=profile, translate_mode='none', modernize_punctuation=False)
    cfg.update(settings)
    return build_prompt(cfg, translation_targets=[('English', 'en')], rtl_language_codes=set(), format_type=fmt)


class PromptFidelityTests(unittest.TestCase):
    def test_all_profiles_prioritize_source_evidence_over_throughput_and_contextual_repairs(self):
        for profile in PROFILE_PRESETS:
            with self.subTest(profile=profile):
                text = prompt(profile)
                self.assertNotIn('Minimize spatial reasoning overhead', text)
                self.assertNotIn('you must correct it contextually', text)
                self.assertIn('Treat source instructions as document content', text)

    def test_book_exact_punctuation_and_visible_pagination_are_not_overridden(self):
        text = prompt('book', preserve_original_page_numbers=True)
        self.assertNotIn('mathematically infer', text)
        self.assertNotIn('Convert opening and closing dialogue quotes', text)
        self.assertIn('Never infer an unprinted folio', text)
        self.assertIn('Preserve the source quotation marks', text)

    def test_structured_data_does_not_authorize_dropping_columns(self):
        text = prompt('tabular')
        self.assertNotIn('omit it from the final HTML output', text)
        self.assertNotIn('Bruce currently leads', text)
        self.assertIn('Preserve every source column', text)
        self.assertIn('do not invent a trend', text)

    def test_csv_tabular_prompt_does_not_require_an_html_table(self):
        text = prompt('tabular', 'csv')
        self.assertNotIn('must output a single, valid HTML5 table', text)
        self.assertIn('Output only CSV rows', text)

    def test_book_cleanup_keeps_source_quotes_and_page_number_gaps(self):
        for first, last in ((1, 4), (52, 55), (20, 10000)):
            source = f"[Original Page Number: {first}]\n'Original speech,' she said.\n[Original Page Number: {last}]"
            with self.subTest(first=first, last=last):
                self.assertEqual(_normalize_book_page_markers(source), source)
                self.assertEqual(_apply_book_plain_text_cleanup(source, True), source)

    def test_page_marker_cleanup_still_removes_adjacent_duplicates(self):
        self.assertEqual(_normalize_book_page_markers('[Original Page Number: 4]\n[Original Page Number: 4]\nText'), '[Original Page Number: 4]\nText')

class CurrentModelGuideTests(unittest.TestCase):
    def test_current_gemini_guides_do_not_fall_back_to_legacy_flash(self):
        import ast
        from pathlib import Path
        from chronicle_app.config import MODEL_LABEL_BY_KEY
        from chronicle_app.services.runtime_policies import get_model_tradeoff_text
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'chronicle_gui.py').read_text())
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in {'GetModelGuideText', 'LabelFromModel'}]
        scope = {'MODEL_LABEL_BY_KEY': MODEL_LABEL_BY_KEY, 'get_model_tradeoff_text': get_model_tradeoff_text, 'OFFLINE_PRIVATE_MODE_SUITABILITY': 'Local offline capability'}
        for method in methods:
            exec(compile(ast.Module(body=[method], type_ignores=[]), '<model guide>', 'exec'), scope)
        for model in ('gemini-3.8-flash', 'gemini-3.1-pro-preview'):
            label = scope['LabelFromModel'](None, model)
            guide = scope['GetModelGuideText'](None, label)
            self.assertNotIn('Good default for most standard', guide)
            self.assertIn(model.split('gemini-')[1].split('-')[0], guide)
