import unittest

from chronicle_app.services.runtime_policies import (
    DEFAULT_CLAUDE_MODEL,
    build_profile_selection_summary,
    get_model_vendor,
    get_pdf_chunk_pages,
    get_preferred_profile_model,
    get_processing_speed_warning,
    normalize_model_name,
    resolve_model_for_available_keys,
)
from chronicle_app.config import PROFILE_PRESETS


class RuntimePoliciesTest(unittest.TestCase):
    def test_get_processing_speed_warning_flags_slow_profiles_and_models(self):
        self.assertIn("much slower", get_processing_speed_warning("newspaper", "gemini-2.5-pro"))
        self.assertIn("slowest option", get_processing_speed_warning("standard", "gemini-2.5-pro"))
        self.assertEqual(get_processing_speed_warning("standard", "gemini-2.5-flash"), "")

    def test_get_pdf_chunk_pages_uses_single_page_slices_for_dense_newspapers(self):
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=8.9), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=4.0), 2)

    def test_get_pdf_chunk_pages_uses_single_page_slices_for_comics(self):
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "comic", 24), 1)
        self.assertEqual(get_pdf_chunk_pages(DEFAULT_CLAUDE_MODEL, "comic", 24), 1)

    def test_get_pdf_chunk_pages_caps_general_pdfs_at_two_pages(self):
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "standard", 10), 2)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-flash", "office", 10), 2)

    def test_get_pdf_chunk_pages_uses_gentler_chunking_for_long_legal_runs(self):
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "legal", 574), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "legal", 80), 2)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-flash", "government", 200), 1)

    def test_legal_profile_defaults_enable_reference_preservation(self):
        settings = PROFILE_PRESETS["legal"]
        self.assertTrue(settings["preserve_original_page_numbers"])
        self.assertTrue(settings["image_descriptions"])
        self.assertFalse(settings["modernize_punctuation"])

    def test_medical_profile_defaults_favor_conservative_clinical_reading(self):
        settings = PROFILE_PRESETS["medical"]
        self.assertEqual(settings["model_name"], "gemini-2.5-pro")
        self.assertTrue(settings["image_descriptions"])
        self.assertFalse(settings["modernize_punctuation"])
        self.assertFalse(settings["abbrev_expansion"])

    def test_comic_profile_defaults_favor_visual_story_recovery(self):
        settings = PROFILE_PRESETS["comic"]
        self.assertEqual(settings["model_name"], "gemini-2.5-pro")
        self.assertTrue(settings["image_descriptions"])
        self.assertTrue(settings["preserve_original_page_numbers"])
        self.assertTrue(settings["merge_files"])
        self.assertFalse(settings["modernize_punctuation"])

    def test_build_profile_selection_summary_includes_speed_warning_when_needed(self):
        summary = build_profile_selection_summary(
            "newspaper",
            "gemini-2.5-pro",
            profile_label_map={"newspaper": "Historical Newspapers / Press Layouts"},
            profile_presets={"standard": {"model_name": "gemini-2.5-flash"}, "newspaper": {"model_name": "gemini-2.5-pro"}},
        )
        self.assertIn("Historical Newspapers / Press Layouts", summary)
        self.assertIn("Warning:", summary)

    def test_get_model_vendor_maps_supported_engines_to_provider_keys(self):
        self.assertEqual(get_model_vendor("gemini-2.5-pro"), "gemini")
        self.assertEqual(get_model_vendor(DEFAULT_CLAUDE_MODEL), "claude")
        self.assertEqual(get_model_vendor("gpt-4o"), "openai")

    def test_normalize_model_name_maps_retired_claude_model(self):
        self.assertEqual(normalize_model_name("claude-3-5-sonnet-20241022"), DEFAULT_CLAUDE_MODEL)

    def test_get_preferred_profile_model_uses_override_when_present(self):
        model = get_preferred_profile_model(
            "newspaper",
            cfg={"model_override": "gpt-4o"},
            profile_presets={"standard": {"model_name": "gemini-2.5-flash"}, "newspaper": {"model_name": "gemini-2.5-pro"}},
        )
        self.assertEqual(model, "gpt-4o")

    def test_get_preferred_profile_model_uses_profile_recommendation_when_override_missing(self):
        model = get_preferred_profile_model(
            "newspaper",
            cfg={"model_override": ""},
            profile_presets={"standard": {"model_name": "gemini-2.5-flash"}, "newspaper": {"model_name": "gemini-2.5-pro"}},
        )
        self.assertEqual(model, "gemini-2.5-pro")

    def test_resolve_model_for_available_keys_falls_back_when_preferred_provider_missing(self):
        resolved = resolve_model_for_available_keys(
            "gemini-2.5-pro",
            has_vendor_key_fn=lambda vendor: vendor == "openai",
        )
        self.assertEqual(resolved, "gpt-4o")

    def test_resolve_model_for_available_keys_keeps_preferred_model_when_provider_exists(self):
        resolved = resolve_model_for_available_keys(
            "claude-3-5-sonnet-20241022",
            has_vendor_key_fn=lambda vendor: vendor in {"claude", "openai"},
        )
        self.assertEqual(resolved, DEFAULT_CLAUDE_MODEL)


if __name__ == "__main__":
    unittest.main()
