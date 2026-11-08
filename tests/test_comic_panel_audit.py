from pathlib import Path
import tempfile
import unittest

from tools.local_benchmark_pack_accessibility import audit_html_output, score_html_checks


class ComicPanelAuditTest(unittest.TestCase):
    def audit(self, body):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'comic.html'
            path.write_text(body, encoding='utf-8')
            return audit_html_output(path)

    def test_footer_cannot_fill_an_empty_final_panel(self):
        checks = self.audit('<main><h2>Panel 1</h2><p>Hello</p><h2>Panel 2</h2><footer>Copyright</footer></main>')
        self.assertFalse(checks['no_empty_panel_sections'])

    def test_each_panel_requires_its_own_description(self):
        checks = self.audit('<main><h2>Panel 1</h2><p>[Image Description: A child]</p><h2>Panel 2</h2><p>Hello</p></main>')
        self.assertFalse(checks['all_panels_described'])
        self.assertFalse(score_html_checks('comic', checks)['perfect_score'])
        good = self.audit('<main><h2>Panel 1</h2><p>[Image Description: A child]</p><h2>Panel 2</h2><p>[Image Description: A room]</p></main>')
        self.assertTrue(good['all_panels_described'])
