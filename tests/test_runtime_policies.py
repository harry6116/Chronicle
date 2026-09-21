import unittest

from chronicle_app.services.runtime_policies import (
    DEFAULT_CLAUDE_MODEL,
    OFFLINE_PRIVATE_MODEL,
    build_profile_selection_summary,
    estimate_run_effort,
    get_online_engine_settings,
    get_model_vendor,
    get_pdf_chunk_pages,
    get_preferred_profile_model,
    get_processing_speed_warning,
    is_offline_model,
    normalize_model_name,
    resolve_model_for_available_keys,
)
from chronicle_app.config import PROFILE_PRESETS


class RuntimePoliciesTest(unittest.TestCase):
    def test_get_processing_speed_warning_flags_slow_profiles_and_models(self):
        self.assertIn("much slower", get_processing_speed_warning("newspaper", "gemini-2.5-pro"))
        self.assertIn("Modern Newspapers", get_processing_speed_warning("modern_newspaper", "gemini-2.5-pro"))
        self.assertIn("slowest option", get_processing_speed_warning("standard", "gemini-2.5-pro"))
        self.assertEqual(get_processing_speed_warning("standard", "gemini-2.5-flash"), "")

    def test_online_engine_settings_accept_bounded_environment_overrides(self):
        settings = get_online_engine_settings(
            env={
                "CHRONICLE_API_MIN_REQUEST_INTERVAL_SEC": "0",
                "CHRONICLE_API_MAX_CONCURRENT_REQUESTS": "99",
                "CHRONICLE_API_MAX_RETRIES": "9",
                "CHRONICLE_STREAM_CHUNK_TIMEOUT_SEC": "720",
                "CHRONICLE_GEMINI_GENERATE_TIMEOUT_MS": "1200000",
            }
        )

        self.assertEqual(settings["api_min_request_interval_sec"], 0.25)
        self.assertEqual(settings["api_max_concurrent_requests"], 2)
        self.assertEqual(settings["api_max_retries"], 9)
        self.assertEqual(settings["stream_chunk_timeout_sec"], 720.0)
        self.assertEqual(settings["gemini_generate_timeout_ms"], 900_000)

    def test_online_engine_settings_ignore_invalid_environment_overrides(self):
        settings = get_online_engine_settings(
            env={
                "CHRONICLE_API_BACKOFF_BASE_SEC": "not-a-number",
                "CHRONICLE_API_REQUEST_QUEUE_POLL_SEC": "",
            }
        )

        self.assertEqual(settings["api_backoff_base_sec"], 8)
        self.assertEqual(settings["api_request_queue_poll_sec"], 0.25)

    def test_estimate_run_effort_flags_heavy_periodical_work(self):
        self.assertEqual(estimate_run_effort("standard", "gemini-2.5-flash", 2), "small")
        self.assertEqual(estimate_run_effort("magazine", "gemini-2.5-pro", 20), "long")
        self.assertEqual(estimate_run_effort("legal", "gemini-2.5-pro", 80), "very long")

    def test_get_pdf_chunk_pages_uses_single_page_slices_for_all_pdfs(self):
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=8.9), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 8, file_size_mb=4.0), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "newspaper", 36, file_size_mb=35.4), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "magazine", 8, file_size_mb=8.9), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "magazine", 36), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "modern_newspaper", 8, file_size_mb=8.9), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "modern_newspaper", 36), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "comic", 24), 1)
        self.assertEqual(get_pdf_chunk_pages(DEFAULT_CLAUDE_MODEL, "comic", 24), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "standard", 10), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-flash", "office", 10), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "legal", 574), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "legal", 80), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-flash", "government", 200), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-flash", "manual", 29), 1)
        self.assertEqual(get_pdf_chunk_pages("gemini-2.5-pro", "manual", 12), 1)

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

    def test_magazine_profile_defaults_favor_dense_periodical_recovery(self):
        settings = PROFILE_PRESETS["magazine"]
        self.assertEqual(settings["model_name"], "gemini-2.5-pro")
        self.assertTrue(settings["image_descriptions"])
        self.assertTrue(settings["preserve_original_page_numbers"])
        self.assertFalse(settings["merge_files"])

    def test_modern_newspaper_profile_defaults_avoid_historical_transforms(self):
        settings = PROFILE_PRESETS["modern_newspaper"]
        self.assertEqual(settings["model_name"], "gemini-2.5-pro")
        self.assertTrue(settings["image_descriptions"])
        self.assertTrue(settings["preserve_original_page_numbers"])
        self.assertTrue(settings["modernize_punctuation"])
        self.assertFalse(settings["unit_conversion"])
        self.assertFalse(settings["abbrev_expansion"])

    def test_transcript_profile_defaults_favor_script_fidelity(self):
        settings = PROFILE_PRESETS["transcript"]
        self.assertEqual(settings["model_name"], "gemini-2.5-pro")
        self.assertTrue(settings["image_descriptions"])
        self.assertTrue(settings["preserve_original_page_numbers"])
        self.assertTrue(settings["modernize_punctuation"])
        self.assertFalse(settings["abbrev_expansion"])

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
        self.assertEqual(get_model_vendor(OFFLINE_PRIVATE_MODEL), "offline")

    def test_offline_model_is_kept_without_provider_key_fallback(self):
        self.assertTrue(is_offline_model(OFFLINE_PRIVATE_MODEL))
        resolved = resolve_model_for_available_keys(
            OFFLINE_PRIVATE_MODEL,
            has_vendor_key_fn=lambda vendor: False,
        )
        self.assertEqual(resolved, OFFLINE_PRIVATE_MODEL)

    def test_normalize_model_name_maps_retired_claude_model(self):
        self.assertEqual(normalize_model_name("claude-3-5-sonnet-20241022"), DEFAULT_CLAUDE_MODEL)
        self.assertEqual(normalize_model_name("claude-sonnet-4-20250514"), DEFAULT_CLAUDE_MODEL)

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
