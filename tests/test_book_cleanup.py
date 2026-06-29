import unittest

from chronicle_app.services.book_cleanup import _apply_book_plain_text_cleanup
from chronicle_app.services.book_cleanup import _normalize_book_dialogue_quotes
from chronicle_app.services.book_cleanup import _normalize_book_page_markers


class BookCleanupTests(unittest.TestCase):
    def test_dialogue_quotes_preserve_apostrophes_and_normalize_speech(self):
        cleaned = _normalize_book_dialogue_quotes("'Hello,' said Artemis. 'Don't move.'")

        self.assertIn('"Hello,"', cleaned)
        self.assertIn('"Don\'t move."', cleaned)

    def test_plain_text_cleanup_splits_headings_and_front_matter(self):
        raw = "Intro line# ARTEMIS FOWL\nARTEMIS FOWL\nNEVER BEFORE HAS A CRIMINAL MASTERMIND\nPENGUIN BOOKS"

        cleaned = _apply_book_plain_text_cleanup(raw, preserve_original_page_numbers=False)

        self.assertIn("Intro line\n# ARTEMIS FOWL", cleaned)
        self.assertIn("ARTEMIS FOWL\n\nNEVER BEFORE HAS A CRIMINAL MASTERMIND", cleaned)
        self.assertIn("NEVER BEFORE HAS A CRIMINAL MASTERMIND\n\nPENGUIN BOOKS", cleaned)

    def test_page_marker_cleanup_fills_missing_sequential_markers(self):
        raw = "[Original Page Number: 1]\nBody\n[Original Page Number: 4]"

        cleaned = _normalize_book_page_markers(raw)

        self.assertIn("[Original Page Number: 2]", cleaned)
        self.assertIn("[Original Page Number: 3]", cleaned)


if __name__ == "__main__":
    unittest.main()
