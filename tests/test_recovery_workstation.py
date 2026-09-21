import tempfile
import unittest
from pathlib import Path

from chronicle_app.services.recovery_workstation import (
    CAPABILITY_REGISTRY,
    build_corpus_project_manifest,
    build_profile_variant,
    build_workstation_plan,
    domain_pack_for_profile,
    format_workstation_plan_text,
    recommend_sensitive_mode,
    write_recovery_workstation_artifacts,
)


class _FixedTime:
    @staticmethod
    def strftime(_fmt):
        return "2026-09-15 10:30:00"


class RecoveryWorkstationTest(unittest.TestCase):
    def test_workstation_plan_covers_all_capability_areas(self):
        plan = build_workstation_plan(
            path="/tmp/source.pdf",
            output_path="/tmp/source.html",
            job_cfg={"doc_profile": "medical", "model_name": "gemini-2.5-pro"},
            fmt="html",
            selected_model="gemini-2.5-pro",
            total_units=55,
            routing={"difficulty": "hard"},
        )

        self.assertEqual(len(plan["capabilities"]), 15)
        self.assertEqual(len(CAPABILITY_REGISTRY), 15)
        self.assertTrue(plan["sensitive_mode"]["recommended"])
        self.assertEqual(plan["economics"]["effort"], "long")
        self.assertIn("medical abbreviations", plan["domain_pack"]["pack_items"])
        self.assertEqual(plan["export_persona"]["intent"], "Screen-reader review HTML")

    def test_format_workstation_plan_text_keeps_gui_formatting_in_service_lane(self):
        plan = build_workstation_plan(
            path="/tmp/source.pdf",
            output_path="/tmp/source.html",
            job_cfg={"doc_profile": "medical"},
            fmt="html",
            selected_model="gemini-2.5-pro",
            total_units=55,
            routing={"difficulty": "hard"},
        )

        text = format_workstation_plan_text(plan)

        self.assertIn("Recovery Workbench Plan", text)
        self.assertIn("Triage signals:", text)
        self.assertIn("Batch economics:", text)
        self.assertIn("Sensitive document mode:", text)
        self.assertIn("Implemented capability areas:", text)

    def test_sensitive_mode_is_recommended_for_private_profiles(self):
        self.assertTrue(recommend_sensitive_mode({"doc_profile": "legal"})["recommended"])
        self.assertFalse(recommend_sensitive_mode({"doc_profile": "comic"})["recommended"])

    def test_profile_variant_and_corpus_manifest_are_structured(self):
        variant = build_profile_variant("War Diary Strict", "military", {"abbrev_expansion": True})
        manifest = build_corpus_project_manifest(
            "Family Archive",
            output_dir="/tmp/out",
            profile_variant=variant,
            queue_rows=[{"path": "/tmp/a.pdf", "status": "Queued", "settings": {"doc_profile": "military"}}],
        )

        self.assertEqual(manifest["project_name"], "Family Archive")
        self.assertEqual(manifest["profile_variant"]["name"], "War Diary Strict")
        self.assertEqual(manifest["rows"][0]["settings"]["doc_profile"], "military")

    def test_domain_pack_defaults_to_general_accessibility(self):
        pack = domain_pack_for_profile("museum")
        self.assertIn("general accessibility cleanup", pack["pack_items"])

    def test_write_recovery_workstation_artifacts_creates_accessible_sidecars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "source.html"
            output.write_text("<html><body><main><h1>Title</h1><p>Body text.</p></main></body></html>", encoding="utf-8")

            artifacts = write_recovery_workstation_artifacts(
                source_path=str(Path(tmpdir) / "source.pdf"),
                output_path=str(output),
                fmt="html",
                job_cfg={"doc_profile": "book", "model_name": "gemini-2.5-pro"},
                file_name="source.pdf",
                engine_label="Gemini 2.5 Pro",
                total_units=12,
                time_module=_FixedTime,
            )

            receipt = Path(artifacts["receipt_path"])
            workbench = Path(artifacts["review_workbench_path"])
            receipt_json = Path(artifacts["json_path"])
            self.assertTrue(receipt.exists())
            self.assertTrue(workbench.exists())
            self.assertTrue(receipt_json.exists())
            self.assertIn("Chronicle Extraction Receipt", receipt.read_text(encoding="utf-8"))
            html = workbench.read_text(encoding="utf-8")
            self.assertIn('role="main"', html)
            self.assertIn("Skip to review content", html)
            self.assertIn("Recovery Workstation Capabilities", html)
            self.assertIn("does not copy extracted document text", html)
            self.assertNotIn("Body text.", html)
            self.assertNotIn(tmpdir, html)
            self.assertNotIn(tmpdir, receipt.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
