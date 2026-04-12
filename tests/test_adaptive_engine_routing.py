import unittest

from chronicle_app.services.adaptive_engine_routing import (
    select_execution_model_for_job,
    should_use_automatic_engine,
)


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, texts):
        self.pages = [_FakePage(text) for text in texts]


class AdaptiveEngineRoutingTest(unittest.TestCase):
    def test_manual_override_disables_automatic_routing(self):
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "government", "model_override": "gpt-4o"},
            "gpt-4o",
            pdf_reader_factory=lambda path: _FakeReader(["hello world"]),
            normalize_pdf_page_scope_text_fn=lambda scope: "",
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
        )

        self.assertFalse(should_use_automatic_engine({"model_override": "gpt-4o"}))
        self.assertEqual(result["model_name"], "gpt-4o")
        self.assertEqual(result["routing_mode"], "manual")

    def test_auto_routing_prefers_flash_for_clean_government_pdf(self):
        clean_page = "Government report text " * 120
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "government", "model_override": ""},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader([clean_page, clean_page, clean_page, clean_page]),
            normalize_pdf_page_scope_text_fn=lambda scope: "",
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 2 * 1024 * 1024,
        )

        self.assertEqual(result["model_name"], "gemini-2.5-flash")
        self.assertEqual(result["auto_escalation_model"], "gemini-2.5-pro")
        self.assertIn("Gemini 2.5 Flash", result["routing_reason"])

    def test_auto_routing_keeps_comics_on_deep_engine_by_default(self):
        clean_page = "Speech balloon text " * 120
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "comic", "model_override": ""},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader([clean_page, clean_page]),
            normalize_pdf_page_scope_text_fn=lambda scope: "",
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 1 * 1024 * 1024,
        )

        self.assertEqual(result["model_name"], "gemini-2.5-pro")
        self.assertEqual(result["difficulty"], "hard")
        self.assertIn("comic profile stays on the deep engine", result["routing_reason"])

    def test_auto_routing_prefers_flash_for_clean_legal_pdf_with_strong_text_layer(self):
        clean_page = "Aged Care Bill 2024 clause text " * 120
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "legal", "model_override": ""},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader([clean_page, clean_page, clean_page]),
            normalize_pdf_page_scope_text_fn=lambda scope: "",
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 1 * 1024 * 1024,
        )

        self.assertEqual(result["model_name"], "gemini-2.5-flash")
        self.assertEqual(result["auto_escalation_model"], "gemini-2.5-pro")
        self.assertEqual(result["difficulty"], "mixed")
        self.assertIn("Chronicle will escalate hard pages", result["routing_reason"])
        self.assertIn("sampled pages", result["routing_reason"])

    def test_auto_routing_tolerates_front_matter_blank_in_legal_pdf(self):
        clean_page = "Aged Care Bill 2024 clause text " * 120
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "legal", "model_override": "", "pdf_page_scope": "1-100"},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader([clean_page[:200], "", clean_page, clean_page, clean_page]),
            normalize_pdf_page_scope_text_fn=lambda scope: scope,
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 1 * 1024 * 1024,
        )

        self.assertEqual(result["model_name"], "gemini-2.5-flash")
        self.assertEqual(result["auto_escalation_model"], "gemini-2.5-pro")

    def test_auto_routing_keeps_pro_for_scan_heavy_legal_pdf(self):
        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "legal", "model_override": ""},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader(["", "", ""]),
            normalize_pdf_page_scope_text_fn=lambda scope: "",
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 20 * 1024 * 1024,
        )

        self.assertEqual(result["model_name"], "gemini-2.5-pro")
        self.assertEqual(result["difficulty"], "hard")
        self.assertIn("deep path", result["routing_reason"])

    def test_auto_routing_samples_broadly_across_long_legal_scope(self):
        pages = [""] * 100
        strong = "Aged Care Bill 2024 clause text " * 120
        for idx in [2, 10, 25, 40, 55, 70, 85, 99]:
            pages[idx] = strong

        result = select_execution_model_for_job(
            "/tmp/a.pdf",
            ".pdf",
            {"doc_profile": "legal", "model_override": "", "pdf_page_scope": "1-100"},
            "gemini-2.5-pro",
            pdf_reader_factory=lambda path: _FakeReader(pages),
            normalize_pdf_page_scope_text_fn=lambda scope: scope,
            parse_pdf_page_scope_spec_fn=lambda scope, total: list(range(total)),
            getsize_fn=lambda path: 3 * 1024 * 1024,
        )

        self.assertIn("sampled pages", result["routing_reason"])


if __name__ == "__main__":
    unittest.main()
