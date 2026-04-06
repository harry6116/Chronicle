import unittest
import sys
import types

from chronicle_core import get_newspaper_profile_rules


def _stub_module(name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


_stub_module("cv2")
pil_module = _stub_module("PIL")
pil_image_module = _stub_module("PIL.Image")
pil_module.Image = pil_image_module
_stub_module("pypdf", PdfReader=object, PdfWriter=object)
_stub_module("docx")
_stub_module("fpdf", FPDF=object)
google_module = _stub_module("google")
google_genai_module = _stub_module("google.genai")
google_module.genai = google_genai_module
_stub_module("openpyxl")
ebooklib_module = _stub_module("ebooklib")
ebooklib_epub_module = _stub_module("ebooklib.epub")
ebooklib_module.epub = ebooklib_epub_module

import chronicle


class NewspaperPromptRulesTest(unittest.TestCase):
    def test_core_newspaper_rules_are_format_aware(self):
        html_rules = get_newspaper_profile_rules("html")
        txt_rules = get_newspaper_profile_rules("txt")

        self.assertIn("Move top-to-bottom within a column", html_rules)
        self.assertIn("Do not read straight across the full page", html_rules)
        self.assertIn("valid HTML tables", html_rules)
        self.assertIn("plain-text rows and columns", txt_rules)

    def test_cli_prompt_uses_shared_newspaper_rules(self):
        prompt = chronicle.get_prompt(
            {
                "doc_profile": "newspaper",
                "format_type": "txt",
                "translate_mode": "none",
                "translate_target": "English",
                "modernize_punctuation": False,
                "unit_conversion": True,
                "image_descriptions": True,
                "abbrev_expansion": False,
            }
        )

        self.assertIn("Segment the page into masthead, article, advertisement", prompt)
        self.assertIn("Join a continued article only when the continuation marker is visible", prompt)
        self.assertIn("never interleave their text into nearby news stories", prompt)
        self.assertIn("plain-text rows and columns", prompt)


if __name__ == "__main__":
    unittest.main()
